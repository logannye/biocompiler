open Bioc_wire
module M = Molecular_record
module P = M.Provenance
module G = Molecule_coordinates
module C = Molecule_chemistry
module Names = Map.Make (String)
let max_molecules = 64
let max_features = 256
let max_origins = 256
let max_roles = 256
let max_mappings = 256
let str value = Json.String value
let obj value = Json.Object value
let arr f values = Json.Array (List.map f values)
let optional f = function None -> Json.Null | Some value -> f value
let option f = function Json.Null -> None | value -> Some (f value)
let require = Diagnostic.require
let finish ~path json value = M.check_resources ~path json; value
let hash ~path value =
  let result = Json.string ~path value in
  require ~path (String.length result = 64 && String.for_all (function '0' .. '9' | 'a' .. 'f' -> true | _ -> false) result)
    "invalid_molecular_fingerprint" "Molecular record pins require lowercase SHA-256 fingerprints.";
  result
let unique ~path ~code key values =
  let sorted = List.sort (fun left right -> String.compare (key left) (key right)) values in
  let rec check = function
    | first :: (second :: _ as remaining) ->
        require ~path (key first <> key second) code "Duplicate molecular occurrence identity.";
        check remaining
    | _ -> () in
  check sorted; sorted
let records ~path ~maximum (decoder : ?path:string -> Json.t -> 'a) value =
  M.array ~path ~maximum value |> List.mapi (fun index -> decoder ~path:(path ^ "/" ^ string_of_int index))
let alphabet_name = function G.Dna -> "DNA" | G.Rna -> "RNA" | G.Protein -> "protein"
let topology_name = function G.Linear -> "linear" | G.Circular -> "circular"
let axis_name = function G.Five_prime_to_three_prime -> "5prime_to_3prime" | G.N_to_c -> "N_to_C"
let extent_name = function C.Complete -> "complete" | C.Exact_core -> "exact_core"

type form = Deposited_template_record | Dna_expression_template | Delivered_dna
  | Primary_rna | Delivered_rna | Processed_rna | Edited_rna | Protein_precursor | Mature_protein
type coding_status = Coding | Noncoding | Unknown | Inapplicable
let form_name = function
  | Deposited_template_record -> "deposited_template_record" | Dna_expression_template -> "dna_expression_template"
  | Delivered_dna -> "delivered_dna" | Primary_rna -> "primary_rna" | Delivered_rna -> "delivered_rna"
  | Processed_rna -> "processed_rna" | Edited_rna -> "edited_rna"
  | Protein_precursor -> "protein_precursor" | Mature_protein -> "mature_protein"
let form_of_json ~path value = match Json.string ~path value with
  | "deposited_template_record" -> Deposited_template_record | "dna_expression_template" -> Dna_expression_template
  | "delivered_dna" -> Delivered_dna | "primary_rna" -> Primary_rna | "delivered_rna" -> Delivered_rna
  | "processed_rna" -> Processed_rna | "edited_rna" -> Edited_rna
  | "protein_precursor" -> Protein_precursor | "mature_protein" -> Mature_protein
  | _ -> Diagnostic.fail ~path "invalid_molecule" "Unknown molecular form."
let coding_status_name = function Coding -> "coding" | Noncoding -> "noncoding" | Unknown -> "unknown" | Inapplicable -> "inapplicable"
let coding_of_json ~path value = match Json.string ~path value with
  | "coding" -> Coding | "noncoding" -> Noncoding | "unknown" -> Unknown | "inapplicable" -> Inapplicable
  | _ -> Diagnostic.fail ~path "invalid_molecule" "Unknown molecular coding declaration."

module Assembly_origin = struct
  type t = {id : string; destination : G.Path.t; source_space : G.Space.t; source_path : G.Path.t; provenance : P.t}
  let schema_version = "biocompiler.assembly_origin.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id;
      "destination", G.Path.to_json value.destination; "source_space", G.Space.to_json value.source_space;
      "source_path", G.Path.to_json value.source_path; "provenance", P.to_json value.provenance]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["id"; "destination"; "source_space"; "source_path"; "provenance"] value in
    let get key = Json.field ~path key fields in
    let destination = G.Path.of_json ~path:(path ^ "/destination") (get "destination")
    and source_space = G.Space.of_json ~path:(path ^ "/source_space") (get "source_space")
    and source_path = G.Path.of_json ~path:(path ^ "/source_path") (get "source_path") in
    G.Path.validate_for source_path source_space;
    require ~path (G.Path.length destination = G.Path.length source_path && G.Path.length source_path > 0)
      "invalid_molecule" "Assembly origin requires equal positive source and destination coordinate counts.";
    let result = {id = M.text ~path:(path ^ "/id") (get "id"); destination; source_space; source_path;
                  provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json result) result
  let make ~id ~destination ~source_space ~source_path ~provenance = of_json (to_json {id; destination; source_space; source_path; provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let destination (value : t) = value.destination
  let source_space (value : t) = value.source_space
  let source_path (value : t) = value.source_path
  let provenance (value : t) = value.provenance
end

module Feature = struct
  type t = {id : string; kind : string; path : G.Path.t option; provenance : P.t; reading_frame : int option}
  let schema_version = "biocompiler.molecule_feature.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id; "kind", str value.kind;
      "path", optional G.Path.to_json value.path; "provenance", P.to_json value.provenance;
      "reading_frame", optional Json.int value.reading_frame]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["id"; "kind"; "path"; "provenance"; "reading_frame"] value in
    let get key = Json.field ~path key fields in
    let reading_frame = option (fun value ->
        let number = Json.integer ~path:(path ^ "/reading_frame") value in
        require ~path (Z.sign number >= 0 && Z.compare number (Z.of_int 2) <= 0)
          "invalid_molecule" "Reading frame must be zero, one, two, or explicit unknown.";
        Z.to_int number) (get "reading_frame") in
    let result = {id = M.text ~path:(path ^ "/id") (get "id"); kind = M.text ~path:(path ^ "/kind") (get "kind");
        path = option (G.Path.of_json ~path:(path ^ "/path")) (get "path");
        provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance"); reading_frame} in
    finish ~path (to_json result) result
  let make ?reading_frame ~id ~kind ~path ~provenance () = of_json (to_json {id; kind; path; provenance; reading_frame})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let kind (value : t) = value.kind
  let path (value : t) = value.path
  let provenance (value : t) = value.provenance
  let reading_frame (value : t) = value.reading_frame
end

type t = {id : string; form : form; space : G.Space.t; sequence : string; sequence_extent : C.sequence_extent;
          coding_status : coding_status; assembly : Assembly_origin.t list; features : Feature.t list; chemistry : C.t; provenance : P.t}
let schema_version = "biocompiler.circuit_molecule.v0.1"
let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id; "form", str (form_name value.form);
    "space", G.Space.to_json value.space; "sequence", str value.sequence; "sequence_extent", str (extent_name value.sequence_extent);
    "coding_status", str (coding_status_name value.coding_status); "assembly", arr Assembly_origin.to_json value.assembly;
    "features", arr Feature.to_json value.features; "chemistry", C.to_json value.chemistry; "provenance", P.to_json value.provenance]
let of_json ?(path = "") value =
  let fields = M.record ~path schema_version ["id"; "form"; "space"; "sequence"; "sequence_extent"; "coding_status";
      "assembly"; "features"; "chemistry"; "provenance"] value in
  let get key = Json.field ~path key fields in
  let id = M.text ~path:(path ^ "/id") (get "id") and form = form_of_json ~path:(path ^ "/form") (get "form") in
  let space = G.Space.of_json ~path:(path ^ "/space") (get "space") in
  let sequence = Json.string ~path:(path ^ "/sequence") (get "sequence") in
  require ~path (M.valid_sequence (G.Space.alphabet space) sequence && G.Space.length space = String.length sequence)
    "invalid_molecule" "Supplied canonical sequence must match its alphabet and coordinate length.";
  let sequence_extent = match Json.string ~path (get "sequence_extent") with
    | "complete" -> C.Complete | "exact_core" -> C.Exact_core
    | _ -> Diagnostic.fail ~path "invalid_molecule" "Unknown sequence extent." in
  require ~path (G.Space.topology space <> G.Circular || sequence_extent = C.Complete)
    "invalid_molecule" "Circular coordinates require complete supplied circumference.";
  let coding_status = coding_of_json ~path:(path ^ "/coding_status") (get "coding_status") in
  let expected = match form with
    | Protein_precursor | Mature_protein -> G.Protein
    | Deposited_template_record | Dna_expression_template | Delivered_dna -> G.Dna
    | _ -> G.Rna in
  require ~path (G.Space.alphabet space = expected) "invalid_molecule" "Molecular form and canonical alphabet disagree.";
  require ~path ((coding_status = Inapplicable) = (expected = G.Protein))
    "invalid_molecule" "Protein coding status is inapplicable; nucleotide coding annotations remain explicit.";
  let assembly = records ~path:(path ^ "/assembly") ~maximum:max_origins Assembly_origin.of_json (get "assembly") in
  require ~path (assembly <> []) "invalid_molecule" "Assembly partition cannot be empty.";
  ignore (unique ~path ~code:"invalid_molecule" Assembly_origin.id assembly);
  let cursor = ref 0 and spaces = ref (Names.singleton (G.Space.id space |> G.Space_id.to_string) (G.Space.fingerprint space)) in
  List.iter (fun origin ->
      let destination = Assembly_origin.destination origin and source = Assembly_origin.source_space origin in
      G.Path.validate_for destination space;
      require ~path (G.Space.alphabet source = expected) "invalid_molecule" "Assembly cannot imply an alphabet conversion.";
      (match G.Path.strand destination, G.Path.spans destination with
       | G.Forward, [span] ->
           require ~path (G.Span.start span = !cursor && G.Span.stop span > G.Span.start span)
             "invalid_molecule" "Assembly must partition supplied residues exactly once in order.";
           cursor := G.Span.stop span
       | _ -> Diagnostic.fail ~path "invalid_molecule" "Assembly destinations require one forward contiguous span.");
      let key = G.Space.id source |> G.Space_id.to_string and digest = G.Space.fingerprint source in
      require ~path (match Names.find_opt key !spaces with None -> true | Some old -> old = digest)
        "invalid_molecule" "Conflicting assembly source coordinate identity.";
      spaces := Names.add key digest !spaces) assembly;
  require ~path (!cursor = String.length sequence) "invalid_molecule" "Assembly does not cover the complete supplied spelling.";
  let features = records ~path:(path ^ "/features") ~maximum:max_features Feature.of_json (get "features")
      |> unique ~path ~code:"invalid_molecule" Feature.id in
  List.iter (fun feature ->
      Option.iter (fun coordinates -> G.Path.validate_for coordinates space) (Feature.path feature);
      require ~path (expected <> G.Protein || Feature.reading_frame feature = None)
        "invalid_molecule" "Protein annotations have no nucleotide reading frame.";
      require ~path (coding_status <> Noncoding || not (List.mem (Feature.kind feature) ["CDS"; "cds"; "ORF"; "orf"; "uORF"; "uorf"]))
        "invalid_molecule" "Noncoding declaration conflicts with a coding annotation.") features;
  let chemistry = C.of_json ~path:(path ^ "/chemistry") (get "chemistry") in
  C.validate_for chemistry space ~sequence ~sequence_extent;
  let result = {id; form; space; sequence; sequence_extent; coding_status; assembly; features; chemistry;
                provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
  finish ~path (to_json result) result
let make ~id ~form ~space ~sequence ~sequence_extent ~coding_status ~assembly ~features ~chemistry ~provenance =
  ignore (M.bounded_length ~maximum:max_origins assembly); ignore (M.bounded_length ~maximum:max_features features);
  of_json (to_json {id; form; space; sequence; sequence_extent; coding_status; assembly; features; chemistry; provenance})
let fingerprint value = Canonical.fingerprint (to_json value)
let id (value : t) = value.id
let form (value : t) = value.form
let space (value : t) = value.space
let sequence (value : t) = value.sequence
let sequence_extent (value : t) = value.sequence_extent
let coding_status (value : t) = value.coding_status
let assembly (value : t) = value.assembly
let features (value : t) = value.features
let chemistry (value : t) = value.chemistry
let provenance (value : t) = value.provenance
let spelling_identity value = Canonical.fingerprint (obj ["profile", str "canonical_spelling.v0.1";
    "alphabet", str (alphabet_name (G.Space.alphabet value.space)); "sequence", str value.sequence])
let nominal_json value =
  let explicit = Hashtbl.create 128 and policies = Hashtbl.create 5 in
  List.iter (fun modification ->
      let token = obj ["chemical", C.Chemical_identity.to_json (C.Modification.identity modification);
                       "canonical_parent", str (String.make 1 (C.Modification.canonical_base modification))]
          |> Canonical.encode |> Digestif.SHA256.digest_string |> Digestif.SHA256.to_raw_string in
      match C.Modification.scope modification with
      | C.Modification.All_matching_bases -> Hashtbl.add policies (C.Modification.canonical_base modification) token
      | C.Modification.Positions -> List.iter (fun position -> Hashtbl.add explicit position token) (C.Modification.positions modification))
    (C.modifications value.chemistry);
  let coverage = ref (Digestif.SHA256.feed_string Digestif.SHA256.empty "biocompiler.positioned_chemistry.v0.1\000") in
  let position_bytes = Bytes.create 8 in
  String.iteri (fun position symbol ->
      let token = match Hashtbl.find_opt explicit position with Some token -> Some token | None -> Hashtbl.find_opt policies symbol in
      Option.iter (fun token ->
          let index = Int64.of_int position in
          for byte = 0 to 7 do
            Bytes.set position_bytes byte (Char.chr (Int64.to_int (Int64.logand 255L (Int64.shift_right_logical index ((7 - byte) * 8)))))
          done;
          coverage := Digestif.SHA256.feed_string !coverage (Bytes.to_string position_bytes);
          coverage := Digestif.SHA256.feed_string !coverage token) token) value.sequence;
  let core_policies = if value.sequence_extent = C.Complete then [] else
      C.modifications value.chemistry |> List.filter (fun item -> C.Modification.scope item = C.Modification.All_matching_bases)
      |> List.map (fun item -> let json = C.Modification.nominal_json item in Canonical.fingerprint json, json)
      |> List.stable_sort (fun (left, _) (right, _) -> String.compare left right) |> List.map snd in
  let chemistry = Json.object_fields (C.nominal_json value.chemistry) in
  let chemistry = ("modifications", obj ["known_coverage_identity", str (Digestif.SHA256.get !coverage |> Digestif.SHA256.to_hex);
      "unresolved_core_policies", Json.Array core_policies]) :: List.remove_assoc "modifications" chemistry in
  let chemistry = if value.sequence_extent = C.Complete && C.Tail.status (C.terminal_tail value.chemistry) = C.Declared then
      ("terminal_tail", obj ["status", str "declared"; "physical_extent", str "included_in_supplied_spelling"])
      :: List.remove_assoc "terminal_tail" chemistry else chemistry in
  obj ["profile", str "declared_covalent_species.v0.1"; "alphabet", str (alphabet_name (G.Space.alphabet value.space));
       "axis", str (axis_name (G.Space.axis value.space)); "topology", str (topology_name (G.Space.topology value.space));
       "sequence", str value.sequence; "sequence_extent", str (extent_name value.sequence_extent); "chemistry", obj chemistry]
let declared_nominal_identity value = Canonical.fingerprint (nominal_json value)
let declared_nominal_complete value = value.sequence_extent = C.Complete && C.declared_nominal_complete value.chemistry
let complete_nominal_identity value = if declared_nominal_complete value then Some (declared_nominal_identity value) else None
let least_rotation sequence =
  let n = String.length sequence in
  let i = ref 0 and j = ref 1 and matched = ref 0 in
  while !i < n && !j < n && !matched < n do
    let left = sequence.[(!i + !matched) mod n] and right = sequence.[(!j + !matched) mod n] in
    if left = right then incr matched else (
      if left > right then (i := !i + !matched + 1; if !i <= !j then i := !j + 1)
      else (j := !j + !matched + 1; if !j <= !i then j := !i + 1);
      matched := 0)
  done;
  let start = min !i !j in
  String.sub sequence start (n - start) ^ String.sub sequence 0 start
let base_rotation_identity value = match G.Space.topology value.space with
  | G.Linear -> None
  | G.Circular -> Some (Canonical.fingerprint (obj ["profile", str "base_only_circular_rotation.v0.1";
      "alphabet", str (alphabet_name (G.Space.alphabet value.space)); "sequence", str (least_rotation value.sequence)]))

module Constituent = struct
  type t = {molecule_id : string; molecule_fingerprint : string; stoichiometry : int option; provenance : P.t}
  let schema_version = "biocompiler.complex_constituent.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "molecule_id", str value.molecule_id;
      "molecule_fingerprint", str value.molecule_fingerprint; "stoichiometry", optional Json.int value.stoichiometry;
      "provenance", P.to_json value.provenance]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["molecule_id"; "molecule_fingerprint"; "stoichiometry"; "provenance"] value in
    let get key = Json.field ~path key fields in
    let stoichiometry = option (fun raw ->
        let value = Json.integer ~path raw in
        require ~path (Z.sign value > 0 && Z.compare value (Z.of_int M.max_residues) <= 0)
          "invalid_molecular_complex" "Stoichiometry must be a positive bounded integer or explicit unknown.";
        Z.to_int value) (get "stoichiometry") in
    let result = {molecule_id = M.text ~path:(path ^ "/molecule_id") (get "molecule_id");
        molecule_fingerprint = hash ~path:(path ^ "/molecule_fingerprint") (get "molecule_fingerprint"); stoichiometry;
        provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json result) result
  let make ~molecule_id ~molecule_fingerprint ~stoichiometry ~provenance = of_json (to_json {molecule_id; molecule_fingerprint; stoichiometry; provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let molecule_id (value : t) = value.molecule_id
  let molecule_fingerprint (value : t) = value.molecule_fingerprint
  let stoichiometry (value : t) = value.stoichiometry
  let provenance (value : t) = value.provenance
end

module Complex = struct
  type kind = Protein_complex | Dna_duplex | Rna_complex
  type t = {id : string; kind : kind; constituents : Constituent.t list; provenance : P.t}
  let schema_version = "biocompiler.molecular_complex.v0.1"
  let kind_name = function Protein_complex -> "protein_complex" | Dna_duplex -> "dna_duplex" | Rna_complex -> "rna_complex"
  let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id; "kind", str (kind_name value.kind);
      "constituents", arr Constituent.to_json value.constituents; "provenance", P.to_json value.provenance]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["id"; "kind"; "constituents"; "provenance"] value in
    let get key = Json.field ~path key fields in
    let kind = match Json.string ~path (get "kind") with
      | "protein_complex" -> Protein_complex | "dna_duplex" -> Dna_duplex | "rna_complex" -> Rna_complex
      | _ -> Diagnostic.fail ~path "invalid_molecular_complex" "Unknown complex kind." in
    let constituents = records ~path:(path ^ "/constituents") ~maximum:max_molecules Constituent.of_json (get "constituents")
        |> unique ~path ~code:"invalid_molecular_complex" Constituent.molecule_id in
    require ~path (constituents <> []) "invalid_molecular_complex" "Complex constituents cannot be empty.";
    if List.for_all (fun item -> Constituent.stoichiometry item <> None) constituents then
      require ~path (List.fold_left (fun sum item -> sum + Option.get (Constituent.stoichiometry item)) 0 constituents >= 2)
        "invalid_molecular_complex" "A single-copy wrapper cannot declare another molecular species.";
    require ~path (kind <> Dna_duplex || List.length constituents = 2 && List.for_all (fun item -> Constituent.stoichiometry item = Some 1) constituents)
      "invalid_molecular_complex" "A DNA duplex requires two explicit single-copy strand records.";
    let result = {id = M.text ~path:(path ^ "/id") (get "id"); kind; constituents;
                  provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json result) result
  let make ~id ~kind ~constituents ~provenance =
    ignore (M.bounded_length ~maximum:max_molecules constituents);
    of_json (to_json {id; kind; constituents; provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let kind (value : t) = value.kind
  let constituents (value : t) = value.constituents
  let provenance (value : t) = value.provenance
end

module Role = struct
  type purpose = Requested_payload | Helper | Host_provider | Assay_control | External_input
  type t = {id : string; subject_id : string; subject_fingerprint : string; role : string; purpose : purpose; compartment : string}
  let schema_version = "biocompiler.molecule_role_instance.v0.1"
  let purpose_name = function Requested_payload -> "requested_payload" | Helper -> "helper" | Host_provider -> "host_provider"
    | Assay_control -> "assay_control" | External_input -> "external_input"
  let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id; "subject_id", str value.subject_id;
      "subject_fingerprint", str value.subject_fingerprint; "role", str value.role; "purpose", str (purpose_name value.purpose);
      "compartment", str value.compartment]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["id"; "subject_id"; "subject_fingerprint"; "role"; "purpose"; "compartment"] value in
    let get key = Json.field ~path key fields in
    let text key = M.text ~path:(path ^ "/" ^ key) (get key) in
    let purpose = match Json.string ~path (get "purpose") with
      | "requested_payload" -> Requested_payload | "helper" -> Helper | "host_provider" -> Host_provider
      | "assay_control" -> Assay_control | "external_input" -> External_input
      | _ -> Diagnostic.fail ~path "invalid_molecular_role" "Unknown molecular role purpose." in
    let compartment = text "compartment" in
    require ~path (compartment <> "abstract") "invalid_molecular_role" "Molecular role requires a physical compartment.";
    let result = {id = text "id"; subject_id = text "subject_id"; subject_fingerprint = hash ~path (get "subject_fingerprint");
                  role = text "role"; purpose; compartment} in
    finish ~path (to_json result) result
  let make ~id ~subject_id ~subject_fingerprint ~role ~purpose ~compartment = of_json (to_json {id; subject_id; subject_fingerprint; role; purpose; compartment})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let subject_id (value : t) = value.subject_id
  let subject_fingerprint (value : t) = value.subject_fingerprint
  let role (value : t) = value.role
  let purpose (value : t) = value.purpose
  let compartment (value : t) = value.compartment
end

module Form_mapping = struct
  type relation = Declared_correspondence | Slice | Orientation | Transcription | Rna_processing | Base_editing
    | Translation | Protein_cleavage | Protein_splicing | Circularization | Ribosomal_skipping
  type t = {id : string; source_molecule_id : string; source_molecule_fingerprint : string;
            destination_molecule_id : string; destination_molecule_fingerprint : string;
            source_path : G.Path.t; destination_path : G.Path.t; relation : relation; provenance : P.t}
  let schema_version = "biocompiler.form_coordinate_mapping.v0.1"
  let relation_name = function
    | Declared_correspondence -> "declared_correspondence" | Slice -> "slice" | Orientation -> "orientation"
    | Transcription -> "transcription" | Rna_processing -> "rna_processing" | Base_editing -> "base_editing"
    | Translation -> "translation" | Protein_cleavage -> "protein_cleavage" | Protein_splicing -> "protein_splicing"
    | Circularization -> "circularization" | Ribosomal_skipping -> "ribosomal_skipping"
  let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id;
      "source_molecule_id", str value.source_molecule_id; "source_molecule_fingerprint", str value.source_molecule_fingerprint;
      "destination_molecule_id", str value.destination_molecule_id; "destination_molecule_fingerprint", str value.destination_molecule_fingerprint;
      "source_path", G.Path.to_json value.source_path; "destination_path", G.Path.to_json value.destination_path;
      "relation", str (relation_name value.relation); "provenance", P.to_json value.provenance]
  let of_json ?(path = "") value =
    let fields = M.record ~path schema_version ["id"; "source_molecule_id"; "source_molecule_fingerprint";
        "destination_molecule_id"; "destination_molecule_fingerprint"; "source_path"; "destination_path"; "relation"; "provenance"] value in
    let get key = Json.field ~path key fields in
    let relation = match Json.string ~path (get "relation") with
      | "declared_correspondence" -> Declared_correspondence | "slice" -> Slice | "orientation" -> Orientation
      | "transcription" -> Transcription | "rna_processing" -> Rna_processing | "base_editing" -> Base_editing
      | "translation" -> Translation | "protein_cleavage" -> Protein_cleavage | "protein_splicing" -> Protein_splicing
      | "circularization" -> Circularization | "ribosomal_skipping" -> Ribosomal_skipping
      | _ -> Diagnostic.fail ~path "invalid_form_mapping" "Unknown declared form-coordinate relation." in
    let result = {id = M.text ~path:(path ^ "/id") (get "id");
        source_molecule_id = M.text ~path (get "source_molecule_id"); source_molecule_fingerprint = hash ~path (get "source_molecule_fingerprint");
        destination_molecule_id = M.text ~path (get "destination_molecule_id"); destination_molecule_fingerprint = hash ~path (get "destination_molecule_fingerprint");
        source_path = G.Path.of_json ~path:(path ^ "/source_path") (get "source_path");
        destination_path = G.Path.of_json ~path:(path ^ "/destination_path") (get "destination_path"); relation;
        provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json result) result
  let make ~id ~source_molecule_id ~source_molecule_fingerprint ~destination_molecule_id ~destination_molecule_fingerprint ~source_path ~destination_path ~relation ~provenance =
    of_json (to_json {id; source_molecule_id; source_molecule_fingerprint; destination_molecule_id; destination_molecule_fingerprint; source_path; destination_path; relation; provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let source_molecule_id (value : t) = value.source_molecule_id
  let source_molecule_fingerprint (value : t) = value.source_molecule_fingerprint
  let destination_molecule_id (value : t) = value.destination_molecule_id
  let destination_molecule_fingerprint (value : t) = value.destination_molecule_fingerprint
  let source_path (value : t) = value.source_path
  let destination_path (value : t) = value.destination_path
  let relation (value : t) = value.relation
  let provenance (value : t) = value.provenance
end
