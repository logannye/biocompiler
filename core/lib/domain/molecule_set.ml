open Bioc_wire
module M = Molecular_record
module P = M.Provenance
module G = Molecule_coordinates
module N = Molecule
module Names = Map.Make (String)
module Keys = Set.Make (struct type t = string * string let compare = Stdlib.compare end)
let str value = Json.String value
let obj value = Json.Object value
let arr f values = Json.Array (List.map f values)
let require = Diagnostic.require
let finish ~path json value = M.check_resources ~path json; value
let hash ~path value =
  let value = Json.string ~path value in
  require ~path (String.length value = 64 && String.for_all (function '0' .. '9' | 'a' .. 'f' -> true | _ -> false) value)
    "invalid_molecular_fingerprint" "Molecular record pin requires lowercase SHA-256 hex.";
  value
let unique ~path ~code key values =
  let result = List.sort (fun left right -> String.compare (key left) (key right)) values in
  let rec check = function
    | first :: (second :: _ as tail) ->
        require ~path (key first <> key second) code "Duplicate molecular inventory identity."; check tail
    | _ -> () in
  check result; result
let records ~path ~maximum (decoder : ?path:string -> Json.t -> 'a) value =
  M.array ~path ~maximum value |> List.mapi (fun index -> decoder ~path:(path ^ "/" ^ string_of_int index))
type subject = Covalent of N.t | Association of N.Complex.t
type identity = {subject : subject; artifact : string; nominal : string; complete : bool}
type t = {id : string; request : Circuit_request.t; molecules : N.t list; complexes : N.Complex.t list;
          role_instances : N.Role.t list; form_mappings : N.Form_mapping.t list; subjects : identity Names.t}
let schema_version = "biocompiler.circuit_molecule_set.v0.1"
let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id;
    "request", Circuit_request.to_json value.request; "molecules", arr N.to_json value.molecules;
    "complexes", arr N.Complex.to_json value.complexes; "role_instances", arr N.Role.to_json value.role_instances;
    "form_mappings", arr N.Form_mapping.to_json value.form_mappings]
let subject ~path value identity = match Names.find_opt identity value with
  | Some result -> result | None -> Diagnostic.fail ~path "invalid_molecule_set" "Missing molecular subject."
let matches_form molecule requested =
  if requested = "circular_rna" then N.form molecule = N.Delivered_rna && G.Space.topology (N.space molecule) = G.Circular
  else N.form_name (N.form molecule) = requested
let of_json ?(path = "") value =
  let fields = M.record ~path schema_version ["id"; "request"; "molecules"; "complexes"; "role_instances"; "form_mappings"] value in
  let get key = Json.field ~path key fields in
  let request = match Circuit_request.of_json (get "request") with
    | Circuit_request.Decoded request -> request
    | Circuit_request.Unsupported unsupported -> Diagnostic.fail ~path:(path ^ "/request") "unsupported_molecule_request"
        ("Molecule sets require complete validated request authority: " ^ String.concat "; " (Circuit_request.unsupported_reasons unsupported)) in
  let molecules = records ~path:(path ^ "/molecules") ~maximum:N.max_molecules N.of_json (get "molecules")
      |> unique ~path ~code:"invalid_molecule_set" N.id in
  let complexes = records ~path:(path ^ "/complexes") ~maximum:N.max_molecules N.Complex.of_json (get "complexes")
      |> unique ~path ~code:"invalid_molecule_set" N.Complex.id in
  let role_instances = records ~path:(path ^ "/role_instances") ~maximum:N.max_roles N.Role.of_json (get "role_instances")
      |> unique ~path ~code:"invalid_molecule_set" N.Role.id in
  let form_mappings = records ~path:(path ^ "/form_mappings") ~maximum:N.max_mappings N.Form_mapping.of_json (get "form_mappings")
      |> unique ~path ~code:"invalid_molecule_set" N.Form_mapping.id in
  require ~path (molecules <> [] && role_instances <> []) "invalid_molecule_set" "Molecules and roles must be nonempty.";
  let molecule_map = List.fold_left (fun map item -> Names.add (N.id item) item map) Names.empty molecules in
  List.iter (fun item -> require ~path (not (Names.mem (N.Complex.id item) molecule_map))
      "invalid_molecule_set" "Molecules and complexes must have distinct record identities.") complexes;
  let spaces = ref Names.empty in
  List.iter (fun item -> let space = N.space item in
      let key = G.Space.id space |> G.Space_id.to_string in
      require ~path (not (Names.mem key !spaces)) "invalid_molecule_set" "Molecule destination frames must be unique.";
      spaces := Names.add key (G.Space.fingerprint space) !spaces) molecules;
  List.iter (fun molecule -> List.iter (fun origin ->
      let space = N.Assembly_origin.source_space origin in
      let key = G.Space.id space |> G.Space_id.to_string and digest = G.Space.fingerprint space in
      require ~path (match Names.find_opt key !spaces with None -> true | Some old -> old = digest)
        "invalid_molecule_set" "Conflicting coordinate-space identity across molecules.";
      spaces := Names.add key digest !spaces) (N.assembly molecule)) molecules;
  require ~path (List.fold_left (fun sum item -> sum + String.length (N.sequence item)) 0 molecules <= M.max_residues)
    "molecular_resource_limit" "Molecule set total supplied residue budget exceeded.";
  (* Bound normalized publication before performing species hash scans. *)
  let preliminary = {id = M.text ~path:(path ^ "/id") (get "id"); request; molecules; complexes; role_instances; form_mappings; subjects = Names.empty} in
  M.check_resources ~path (to_json preliminary);
  let subjects = List.fold_left (fun map item ->
      Names.add (N.id item) {subject = Covalent item; artifact = N.fingerprint item;
          nominal = N.declared_nominal_identity item; complete = N.declared_nominal_complete item} map) Names.empty molecules in
  let subjects = List.fold_left (fun subjects complex_ ->
      let expected = match N.Complex.kind complex_ with
        | N.Complex.Protein_complex -> G.Protein | N.Complex.Dna_duplex -> G.Dna | N.Complex.Rna_complex -> G.Rna in
      let counts = ref Names.empty and unknowns = ref Names.empty and complete = ref true in
      let increment map key count = Names.add key (count + Option.value ~default:0 (Names.find_opt key map)) map in
      List.iter (fun constituent ->
          let entry = subject ~path subjects (N.Constituent.molecule_id constituent) in
          let molecule = match entry.subject with Covalent value -> value
            | Association _ -> Diagnostic.fail ~path "invalid_molecule_set" "Complex constituents must be covalent molecules." in
          require ~path (entry.artifact = N.Constituent.molecule_fingerprint constituent)
            "invalid_molecule_set" "Stale complex constituent fingerprint.";
          require ~path (G.Space.alphabet (N.space molecule) = expected)
            "invalid_molecule_set" "Complex kind and constituent polymer disagree.";
          complete := !complete && entry.complete && N.Constituent.stoichiometry constituent <> None;
          match N.Constituent.stoichiometry constituent with
          | None -> unknowns := increment !unknowns entry.nominal 1
          | Some count -> counts := increment !counts entry.nominal count) (N.Complex.constituents complex_);
      let quantities map = obj (Names.bindings map |> List.map (fun (key, count) -> key, Json.int count)) in
      let nominal = Canonical.fingerprint (obj ["profile", str "declared_complex_species.v0.1";
          "kind", str (N.Complex.kind_name (N.Complex.kind complex_)); "known_copies", quantities !counts; "unknown_terms", quantities !unknowns]) in
      Names.add (N.Complex.id complex_) {subject = Association complex_; artifact = N.Complex.fingerprint complex_; nominal; complete = !complete} subjects)
      subjects complexes in
  let requested = ref 0 in
  List.iter (fun role ->
      let entry = subject ~path subjects (N.Role.subject_id role) in
      require ~path (entry.artifact = N.Role.subject_fingerprint role) "invalid_molecule_set" "Stale molecular role subject fingerprint.";
      Option.iter (fun target -> require ~path (List.mem (N.Role.compartment role) (Build_request.Target.compartments target))
          "invalid_molecule_set" "Molecular role must retain a declared target compartment.")
        (Circuit_request.Profile.target (Circuit_request.profile request));
      if N.Role.purpose role = N.Role.Requested_payload then (
        incr requested;
        let members = match entry.subject with
          | Covalent molecule -> [molecule]
          | Association complex_ -> List.map (fun item -> Names.find (N.Constituent.molecule_id item) molecule_map) (N.Complex.constituents complex_) in
        require ~path (List.for_all (fun molecule -> matches_form molecule (Circuit_request.requested_form request)) members)
          "invalid_molecule_set" "Every requested payload member must preserve the requested molecular form.")) role_instances;
  require ~path (!requested > 0) "invalid_molecule_set" "At least one requested-payload role is required.";
  List.iter (fun mapping ->
      let resolve id digest =
        let item = match Names.find_opt id molecule_map with Some value -> value
          | None -> Diagnostic.fail ~path "invalid_molecule_set" "Form mapping binds a missing covalent molecule." in
        require ~path ((subject ~path subjects id).artifact = digest) "invalid_molecule_set" "Stale form mapping molecule fingerprint.";
        item in
      let source = resolve (N.Form_mapping.source_molecule_id mapping) (N.Form_mapping.source_molecule_fingerprint mapping)
      and destination = resolve (N.Form_mapping.destination_molecule_id mapping) (N.Form_mapping.destination_molecule_fingerprint mapping) in
      G.Path.validate_for (N.Form_mapping.source_path mapping) (N.space source);
      G.Path.validate_for (N.Form_mapping.destination_path mapping) (N.space destination)) form_mappings;
  {preliminary with subjects}
let make ~id ~request ~molecules ~complexes ~role_instances ~form_mappings =
  ignore (M.bounded_length ~maximum:N.max_molecules molecules); ignore (M.bounded_length ~maximum:N.max_molecules complexes);
  ignore (M.bounded_length ~maximum:N.max_roles role_instances); ignore (M.bounded_length ~maximum:N.max_mappings form_mappings);
  of_json (to_json {id; request; molecules; complexes; role_instances; form_mappings; subjects = Names.empty})
let fingerprint value = Canonical.fingerprint (to_json value)
let id (value : t) = value.id
let request (value : t) = value.request
let molecules (value : t) = value.molecules
let complexes (value : t) = value.complexes
let role_instances (value : t) = value.role_instances
let form_mappings (value : t) = value.form_mappings
let find_subject value identity = match Names.find_opt identity value.subjects with Some result -> result
  | None -> Diagnostic.fail "unknown_molecular_subject" "Unknown molecular subject."
let subject_nominal_identity value identity = (find_subject value identity).nominal
let subject_complete value identity = (find_subject value identity).complete
let declared_nominal_complete value = Names.for_all (fun _ subject -> subject.complete) value.subjects
let declared_nominal_bundle_identity value =
  let records = Names.bindings value.subjects |> List.map (fun (_, entry) -> entry.nominal) |> List.sort_uniq String.compare in
  let roles = List.map (fun role ->
      let json = obj ["species", str (subject_nominal_identity value (N.Role.subject_id role)); "role", str (N.Role.role role);
          "purpose", str (N.Role.purpose_name (N.Role.purpose role)); "compartment", str (N.Role.compartment role)] in
      Canonical.fingerprint json, json) value.role_instances
      |> List.stable_sort (fun (left, _) (right, _) -> String.compare left right) |> List.map snd in
  Canonical.fingerprint (obj ["profile", str "declared_molecular_bundle.v0.1"; "records", arr str records; "roles", Json.Array roles])

module Amount = struct
  type quantity = Unknown | Integer of Z.t | Real of float
  type t = {id : string; subject_id : string; subject_fingerprint : string; preparation_id : string;
            role_instance_ids : string list; quantity : quantity; unit : string; provenance : P.t}
  let schema_version = "biocompiler.molecular_experimental_amount.v0.1"
  let quantity_json = function Unknown -> Json.Null | Integer value -> Json.Int value | Real value -> Json.Float value
  let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id; "subject_id", str value.subject_id;
      "subject_fingerprint", str value.subject_fingerprint; "preparation_id", str value.preparation_id;
      "role_instance_ids", arr str value.role_instance_ids; "quantity", quantity_json value.quantity;
      "unit", str value.unit; "provenance", P.to_json value.provenance]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["id"; "subject_id"; "subject_fingerprint"; "preparation_id"; "role_instance_ids"; "quantity"; "unit"; "provenance"] value in
    let get key = Json.field ~path key fields in
    let text key = M.text ~path:(path ^ "/" ^ key) (get key) in
    let role_instance_ids = M.array ~path ~maximum:N.max_roles (get "role_instance_ids") |> List.map (M.text ~path)
        |> unique ~path ~code:"invalid_experimental_amount" Fun.id in
    let quantity = match get "quantity" with
      | Json.Null -> Unknown
      | Json.Int value ->
          require ~path (Z.sign value >= 0 && Z.numbits value <= 1024) "invalid_experimental_amount" "Amount requires a nonnegative integer of at most 1024 bits.";
          Integer value
      | Json.Float value ->
          require ~path (Float.is_finite value && value >= 0.) "invalid_experimental_amount" "Amount must be finite and nonnegative.";
          Real value
      | _ -> Diagnostic.fail ~path "invalid_type" "Amount must be an integer, float or explicit unknown." in
    let result = {id = text "id"; subject_id = text "subject_id"; subject_fingerprint = hash ~path (get "subject_fingerprint");
                  preparation_id = text "preparation_id"; role_instance_ids; quantity; unit = text "unit";
                  provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json result) result
  let make ~id ~subject_id ~subject_fingerprint ~preparation_id ~role_instance_ids ~quantity ~unit ~provenance =
    ignore (M.bounded_length ~maximum:N.max_roles role_instance_ids);
    of_json (to_json {id; subject_id; subject_fingerprint; preparation_id; role_instance_ids; quantity; unit; provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let subject_id (value : t) = value.subject_id
  let subject_fingerprint (value : t) = value.subject_fingerprint
  let preparation_id (value : t) = value.preparation_id
  let role_instance_ids (value : t) = value.role_instance_ids
  let quantity (value : t) = value.quantity
  let unit (value : t) = value.unit
  let provenance (value : t) = value.provenance
end

module Artifact = struct
  type bundle = t
  let bundle_of_json = of_json
  let bundle_to_json = to_json
  type t = {bundle : bundle; experimental_amounts : Amount.t list; run_metadata : (string * Json.t) list}
  let schema_version = "biocompiler.circuit_molecule_record.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "bundle", bundle_to_json value.bundle;
      "experimental_amounts", arr Amount.to_json value.experimental_amounts; "run_metadata", obj value.run_metadata]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["bundle"; "experimental_amounts"; "run_metadata"] value in
    let get key = Json.field ~path key fields in
    let bundle = bundle_of_json ~path:(path ^ "/bundle") (get "bundle") in
    let experimental_amounts = records ~path:(path ^ "/experimental_amounts") ~maximum:128 Amount.of_json (get "experimental_amounts")
        |> unique ~path ~code:"invalid_molecule_artifact" Amount.id in
    let roles = List.fold_left (fun map item -> Names.add (N.Role.id item) item map) Names.empty bundle.role_instances in
    let preparations = ref Keys.empty in
    List.iter (fun amount ->
        let entry = match Names.find_opt (Amount.subject_id amount) bundle.subjects with
          | Some value -> value | None -> Diagnostic.fail ~path "invalid_molecule_artifact" "Missing amount subject." in
        require ~path (entry.artifact = Amount.subject_fingerprint amount) "invalid_molecule_artifact" "Stale experimental amount subject fingerprint.";
        let key = Amount.preparation_id amount, entry.nominal in
        require ~path (not (Keys.mem key !preparations)) "invalid_molecule_artifact" "A physical species/preparation amount can be declared only once.";
        preparations := Keys.add key !preparations;
        List.iter (fun identity ->
            let role = match Names.find_opt identity roles with Some value -> value
              | None -> Diagnostic.fail ~path "invalid_molecule_artifact" "Missing amount role." in
            require ~path (N.Role.subject_id role = Amount.subject_id amount && N.Role.subject_fingerprint role = Amount.subject_fingerprint amount)
              "invalid_molecule_artifact" "Amount role must refer to the same exact physical subject declaration.") (Amount.role_instance_ids amount)) experimental_amounts;
    let run_metadata = Json.object_fields ~path:(path ^ "/run_metadata") (get "run_metadata") in
    ignore (M.bounded_length ~path ~maximum:128 run_metadata);
    M.bounded_tree ~path (obj run_metadata);
    let result = {bundle; experimental_amounts; run_metadata} in
    finish ~path (to_json result) result
  let make ~bundle ~experimental_amounts ~run_metadata =
    ignore (M.bounded_length ~maximum:128 experimental_amounts); ignore (M.bounded_length ~maximum:128 run_metadata);
    M.bounded_tree (obj run_metadata);
    of_json (to_json {bundle; experimental_amounts; run_metadata})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let bundle (value : t) = value.bundle
  let experimental_amounts (value : t) = value.experimental_amounts
  let run_metadata (value : t) = value.run_metadata
  let nominal_bundle_identity value = declared_nominal_bundle_identity value.bundle
  let experimental_specification_identity value = Canonical.fingerprint (obj ["profile", str "declared_molecular_experiment.v0.1";
      "bundle", bundle_to_json value.bundle; "amounts", arr Amount.to_json value.experimental_amounts])
  let artifact_fingerprint = fingerprint
end
