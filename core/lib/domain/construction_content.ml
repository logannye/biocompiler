open Bioc_wire
module M = Molecular_record
module N = Molecule
module G = Molecule_coordinates
module A = Construction_artifact
module S = Molecule_set
module Names = Map.Make (String)
let schema_version = "biocompiler.construction_content.v0.1"
let authority_schema = "biocompiler.construction_content_authority.v0.1"
let check ?path condition message = Diagnostic.require ?path condition "invalid_construction_content" message
let str value = Json.String value
let array maximum encode values =
  ignore (M.bounded_length ~maximum values);
  let size = ref 2 in
  Json.Array (List.map (fun value -> let raw = encode value in
      size := !size + M.pretty_size raw + 1;
      Diagnostic.require (!size <= M.max_json_bytes) "molecular_resource_limit" "Content children exceed publication limits.";
      raw) values)
let unique ~path key values =
  let names = List.map key values in
  check ~path (List.length names = List.length (List.sort_uniq String.compare names)) "Duplicate content inventory identity.";
  values
let records ~path ~maximum (decode : ?path:string -> Json.t -> 'a) raw = M.array ~path ~maximum raw
  |> List.mapi (fun i raw -> decode ~path:(path ^ "/" ^ string_of_int i) raw)
let texts ~path maximum raw = M.array ~path ~maximum raw |> List.map (M.text ~path) |> unique ~path Fun.id
let pin ~path raw =
  let value = Json.string ~path raw in
  check ~path (String.length value = 64 && String.for_all (function '0' .. '9' | 'a' .. 'f' -> true | _ -> false) value)
    "Content authority requires lowercase SHA-256 hex."; value
let authority_json ~template ~member_order =
  ignore (M.bounded_length ~maximum:Construction.max_output_members member_order);
  ignore (unique ~path:"/member_order" Fun.id member_order);
  let expected = List.map Construction.Output_member.id (Payload_template.output_members template) in
  check (List.sort String.compare member_order = List.sort String.compare expected)
    "Original member order must name every covalent template output exactly once.";
  let raw = Json.Object ["schema_version",str authority_schema;"template",Payload_template.to_json template;
      "member_order",array Construction.max_output_members str member_order] in
  M.check_resources raw; raw
let authority_fingerprint ~template ~member_order = Canonical.fingerprint (authority_json ~template ~member_order)

module Inventory = struct
  type subject = { digest:string; nominal:string; complete:bool }
  type t = { id:string; molecules:N.t list; complexes:N.Complex.t list;
    role_instances:N.Role.t list; form_mappings:N.Form_mapping.t list; subjects:subject Names.t }
  let schema_version = "biocompiler.molecular_content_inventory.v0.1"
  let to_json (value:t) = Json.Object ["schema_version",str schema_version;"id",str value.id;
      "molecules",array N.max_molecules N.to_json value.molecules;
      "complexes",array N.max_molecules N.Complex.to_json value.complexes;
      "role_instances",array N.max_roles N.Role.to_json value.role_instances;
      "form_mappings",array N.max_mappings N.Form_mapping.to_json value.form_mappings]
  let subject ~path values id = match Names.find_opt id values with Some value -> value
    | None -> Diagnostic.fail ~path "invalid_construction_content" "Missing molecular subject."
  let of_json ?(path="") raw =
    M.check_resources ~path raw;
    let fields = M.record ~path schema_version ["id";"molecules";"complexes";"role_instances";"form_mappings"] raw in
    let get key = Json.field ~path key fields in
    let molecules = records ~path:(path ^ "/molecules") ~maximum:N.max_molecules N.of_json (get "molecules") |> unique ~path N.id
    and complexes = records ~path:(path ^ "/complexes") ~maximum:N.max_molecules N.Complex.of_json (get "complexes") |> unique ~path N.Complex.id
    and role_instances = records ~path:(path ^ "/role_instances") ~maximum:N.max_roles N.Role.of_json (get "role_instances") |> unique ~path N.Role.id
    and form_mappings = records ~path:(path ^ "/form_mappings") ~maximum:N.max_mappings N.Form_mapping.of_json (get "form_mappings") |> unique ~path N.Form_mapping.id in
    check ~path (molecules <> []) "Materialized content requires a covalent member.";
    let by_id = List.fold_left (fun map value -> Names.add (N.id value) value map) Names.empty molecules in
    let frames = ref Names.empty in
    List.iter (fun value -> let space = N.space value in let id = G.Space_id.to_string (G.Space.id space) in
        check ~path (not (Names.mem id !frames)) "Duplicate destination coordinate identity.";
        frames := Names.add id (G.Space.fingerprint space) !frames) molecules;
    List.iter (fun value -> List.iter (fun origin -> let space = N.Assembly_origin.source_space origin in
        let id = G.Space_id.to_string (G.Space.id space) and digest = G.Space.fingerprint space in
        check ~path (match Names.find_opt id !frames with None -> true | Some previous -> previous = digest)
          "Conflicting source coordinate identity.";
        frames := Names.add id digest !frames) (N.assembly value)) molecules;
    ignore (List.fold_left (fun total value -> let total = total + String.length (N.sequence value) in
        check ~path (total <= M.max_residues) "Content residue inventory exceeds its bound."; total) 0 molecules);
    let subjects = List.fold_left (fun map value -> Names.add (N.id value)
        {digest=N.fingerprint value;nominal=N.declared_nominal_identity value;complete=N.declared_nominal_complete value} map) Names.empty molecules in
    let subjects = List.fold_left (fun map complex_ ->
        check ~path (not (Names.mem (N.Complex.id complex_) map)) "Covalent and complex identities collide.";
        let alphabet = match N.Complex.kind complex_ with N.Complex.Protein_complex -> G.Protein
          | N.Complex.Dna_duplex -> G.Dna | N.Complex.Rna_complex -> G.Rna in
        let complete = ref true and counts = ref Names.empty and unknowns = ref Names.empty in
        let increment map key count = Names.add key (count + Option.value ~default:0 (Names.find_opt key map)) map in
        List.iter (fun part -> let id = N.Constituent.molecule_id part in
            let molecule = match Names.find_opt id by_id with Some value -> value
              | None -> Diagnostic.fail ~path "invalid_construction_content" "Complex constituent is not a covalent content member." in
            let entry = subject ~path map id in
            check ~path (entry.digest = N.Constituent.molecule_fingerprint part) "Stale constituent identity.";
            check ~path (G.Space.alphabet (N.space molecule) = alphabet) "Complex polymer mismatch.";
            complete := !complete && entry.complete && N.Constituent.stoichiometry part <> None;
            match N.Constituent.stoichiometry part with
            | None -> unknowns := increment !unknowns entry.nominal 1
            | Some count -> counts := increment !counts entry.nominal count) (N.Complex.constituents complex_);
        let quantities map = Json.Object (Names.bindings map |> List.map (fun (id,count) -> id,Json.int count)) in
        let nominal = Canonical.fingerprint (Json.Object ["profile",str "declared_complex_species.v0.1";
            "kind",str (N.Complex.kind_name (N.Complex.kind complex_));"known_copies",quantities !counts;"unknown_terms",quantities !unknowns]) in
        Names.add (N.Complex.id complex_) {digest=N.Complex.fingerprint complex_;nominal;complete= !complete} map) subjects complexes in
    List.iter (fun role -> check ~path ((subject ~path subjects (N.Role.subject_id role)).digest = N.Role.subject_fingerprint role)
        "Stale role subject identity.") role_instances;
    List.iter (fun mapping ->
        let resolve id digest =
          let value = match Names.find_opt id by_id with Some value -> value
            | None -> Diagnostic.fail ~path "invalid_construction_content" "Form mapping lacks a covalent member." in
          check ~path ((subject ~path subjects id).digest = digest) "Stale form-mapping identity."; value in
        let source = resolve (N.Form_mapping.source_molecule_id mapping) (N.Form_mapping.source_molecule_fingerprint mapping)
        and destination = resolve (N.Form_mapping.destination_molecule_id mapping) (N.Form_mapping.destination_molecule_fingerprint mapping) in
        G.Path.validate_for (N.Form_mapping.source_path mapping) (N.space source);
        G.Path.validate_for (N.Form_mapping.destination_path mapping) (N.space destination)) form_mappings;
    let value = {id=M.text ~path (get "id");molecules;complexes;role_instances;form_mappings;subjects} in
    M.check_resources ~path (to_json value); value
  let make ~id ~molecules ~complexes ~role_instances ~form_mappings =
    of_json (to_json {id;molecules;complexes;role_instances;form_mappings;subjects=Names.empty})
  let molecules (value:t) = value.molecules
  let complexes (value:t) = value.complexes
  let role_instances (value:t) = value.role_instances
  let form_mappings (value:t) = value.form_mappings
  let subject_complete (value:t) id = (subject ~path:"" value.subjects id).complete
  let validate_amounts (value:t) amounts =
    ignore (M.bounded_length ~maximum:Construction.max_amount_declarations amounts);
    ignore (unique ~path:"/experimental_amounts" S.Amount.id amounts);
    let roles = List.fold_left (fun map role -> Names.add (N.Role.id role) role map) Names.empty value.role_instances in
    let preparations = Hashtbl.create 16 in
    List.iter (fun amount -> let id = S.Amount.subject_id amount in
        check ((subject ~path:"" value.subjects id).digest = S.Amount.subject_fingerprint amount) "Stale amount subject identity.";
        List.iter (fun role_id -> check (match Names.find_opt role_id roles with
            | Some role -> N.Role.subject_id role = id | None -> false) "Amount role binds a different subject.") (S.Amount.role_instance_ids amount);
        let key = S.Amount.preparation_id amount,(subject ~path:"" value.subjects id).nominal in
        check (not (Hashtbl.mem preparations key)) "Duplicate physical-species/preparation amount.";
        Hashtbl.add preparations key ()) amounts
end

type t = { authority_fingerprint:string; member_order:string list; values:A.Value.t list;
  inventory:Inventory.t option; missing_members:string list; diagnostics:string list;
  experimental_amounts:S.Amount.t list }
let to_json (value:t) = Json.Object ["schema_version",str schema_version;
    "authority_fingerprint",str value.authority_fingerprint;
    "member_order",array Construction.max_output_members str value.member_order;
    "values",array Construction.max_products A.Value.to_json value.values;
    "inventory",(match value.inventory with None -> Json.Null | Some item -> Inventory.to_json item);
    "missing_members",array 256 str value.missing_members;"diagnostics",array 1024 str value.diagnostics;
    "experimental_amounts",array Construction.max_amount_declarations S.Amount.to_json value.experimental_amounts]
let of_json ?(path="") raw =
  M.check_resources ~path raw;
  let fields = M.record ~path schema_version ["authority_fingerprint";"member_order";"values";"inventory";
      "missing_members";"diagnostics";"experimental_amounts"] raw in
  let get key = Json.field ~path key fields in
  let member_order = texts ~path:(path ^ "/member_order") Construction.max_output_members (get "member_order") in
  check ~path (member_order <> []) "Content authority requires a nonempty original member order.";
  let values = records ~path:(path ^ "/values") ~maximum:Construction.max_products A.Value.of_json (get "values")
      |> unique ~path A.Value.id |> List.sort (fun a b -> String.compare (A.Value.id a) (A.Value.id b)) in
  let frames = List.map (fun value -> G.Space_id.to_string (G.Space.id (A.Value.space value))) values in
  ignore (unique ~path Fun.id frames);
  ignore (List.fold_left (fun total value -> let total = total + G.Space.length (A.Value.space value) in
      check ~path (total <= M.max_residues) "Constructed content residue limit exceeded."; total) 0 values);
  let inventory = match get "inventory" with Json.Null -> None | value -> Some (Inventory.of_json ~path:(path ^ "/inventory") value) in
  let experimental_amounts = records ~path:(path ^ "/experimental_amounts") ~maximum:Construction.max_amount_declarations
      S.Amount.of_json (get "experimental_amounts") |> unique ~path S.Amount.id
      |> List.sort (fun a b -> String.compare (S.Amount.id a) (S.Amount.id b)) in
  (match inventory with None -> check ~path (experimental_amounts = []) "Absent content cannot bind amounts."
   | Some value ->
       check ~path (List.map N.id (Inventory.molecules value) = member_order) "Materialized inventory differs from its declared order.";
       Inventory.validate_amounts value experimental_amounts);
  let value = {authority_fingerprint=pin ~path (get "authority_fingerprint");member_order;values;inventory;experimental_amounts;
      missing_members=texts ~path:(path ^ "/missing_members") 256 (get "missing_members") |> List.sort String.compare;
      diagnostics=texts ~path:(path ^ "/diagnostics") 1024 (get "diagnostics") |> List.sort String.compare} in
  M.check_resources ~path (to_json value); value
let make ~authority_fingerprint ~member_order ~values ~inventory ~missing_members ~diagnostics ~experimental_amounts =
  of_json (to_json {authority_fingerprint;member_order;values;inventory;missing_members;diagnostics;experimental_amounts})
let fingerprint value = Canonical.fingerprint (to_json value)
let authority (value:t) = value.authority_fingerprint
let member_order (value:t) = value.member_order
let values (value:t) = value.values
let inventory (value:t) = value.inventory
let missing_members (value:t) = value.missing_members
let diagnostics (value:t) = value.diagnostics
let experimental_amounts (value:t) = value.experimental_amounts
