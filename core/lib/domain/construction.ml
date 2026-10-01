open Bioc_wire
module M = Molecular_record
module P = M.Provenance
module G = Molecule_coordinates
module N = Molecule
module Names = Map.Make (String)
module Ids = Set.Make (String)
module type Record = sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Json.t -> t
  val to_json : t -> Json.t
  val fingerprint : t -> string
end
let profile_version = "biocompiler.circuit_construction.v0.1"
let capability_profile_version = "biocompiler.circuit_transform_capabilities.v0.1"
let transcription_mapping_profile = "dna_coding_to_rna.v1"
let max_sources = 64
let max_steps = 256
let max_selections = 128
let max_products = 256
let max_processing_products = 16
let max_translation_products = 16
let max_translation_branches = 16
let max_output_members = 64
let max_complex_members = 64
let max_amount_declarations = 128
let max_member_requirements = 256
let max_role_declarations = 256
let max_assumptions = 32
let max_total_source_residues = M.max_residues
let max_cumulative_produced_residues = M.max_residues
let str value = Json.String value
let obj value = Json.Object value
let emission_budget () = ref 1, ref 2
let reserve_json ?path (nodes, bytes) value =
  let rec count = function
    | Json.Array values -> incr nodes; List.iter count values
    | Json.Object fields -> incr nodes; List.iter (fun (_, value) -> incr nodes; count value) fields
    | _ -> incr nodes in
  count value;
  bytes := !bytes + M.pretty_size value;
  Diagnostic.require ?path (!nodes <= M.max_items && !bytes <= M.max_json_bytes)
    "molecular_resource_limit" "Aggregate construction emission exceeds the molecular budget."
let array encode values =
  let budget = emission_budget () in
  Json.Array (List.map (fun value -> let json = encode value in reserve_json budget json; json) values)
let preflight_children encode values budget = List.iter (fun value -> reserve_json budget (encode value)) values
let optional encode = function None -> Json.Null | Some value -> encode value
let option decode = function Json.Null -> None | value -> Some (decode value)
let require ?path condition message = Diagnostic.require ?path condition "invalid_construction" message
let finish ~path json value = M.check_resources ~path json; value
let hash ~path raw =
  let value = Json.string ~path raw in
  require ~path (String.length value = 64 && String.for_all (function '0' .. '9' | 'a' .. 'f' -> true | _ -> false) value)
    "Expected a lowercase SHA-256 authority pin.";
  value
let records ~path ~maximum (decode : ?path:string -> Json.t -> 'a) value =
  M.array ~path ~maximum value |> List.mapi (fun index -> decode ~path:(path ^ "/" ^ string_of_int index))
let sorted ~path ?(nonempty = false) key values =
  require ~path (not nonempty || values <> []) "Required construction inventory is empty.";
  let values = List.sort (fun a b -> Stdlib.compare (key a) (key b)) values in
  let rec unique = function
    | first :: (second :: _ as tail) -> require ~path (key first <> key second) "Duplicate construction inventory identity."; unique tail
    | _ -> () in
  unique values; values
let texts ~path ~maximum raw = M.array ~path ~maximum raw |> List.map (M.text ~path) |> sorted ~path Fun.id
let alphabet_name = function G.Dna -> "DNA" | G.Rna -> "RNA" | G.Protein -> "protein"
let topology_name = function G.Linear -> "linear" | G.Circular -> "circular"
let alphabet ~path raw = match Json.string ~path raw with
  | "DNA" -> G.Dna | "RNA" -> G.Rna | "protein" -> G.Protein
  | _ -> Diagnostic.fail ~path "invalid_construction" "Unknown construction alphabet."
let topology ~path raw = match Json.string ~path raw with
  | "linear" -> G.Linear | "circular" -> G.Circular
  | _ -> Diagnostic.fail ~path "invalid_construction" "Unknown construction topology."
let form ~path raw = match Json.string ~path raw with
  | "deposited_template_record" -> N.Deposited_template_record | "dna_expression_template" -> N.Dna_expression_template
  | "delivered_dna" -> N.Delivered_dna | "primary_rna" -> N.Primary_rna | "delivered_rna" -> N.Delivered_rna
  | "processed_rna" -> N.Processed_rna | "edited_rna" -> N.Edited_rna
  | "protein_precursor" -> N.Protein_precursor | "mature_protein" -> N.Mature_protein
  | _ -> Diagnostic.fail ~path "invalid_construction" "Unknown construction molecular form."
let extent ~path raw = match Json.string ~path raw with
  | "complete" -> Molecule_chemistry.Complete | "exact_core" -> Molecule_chemistry.Exact_core
  | _ -> Diagnostic.fail ~path "invalid_construction" "Unknown construction sequence extent."
let extent_name = function Molecule_chemistry.Complete -> "complete" | Molecule_chemistry.Exact_core -> "exact_core"
let coding ~path raw = match Json.string ~path raw with
  | "coding" -> N.Coding | "noncoding" -> N.Noncoding | "unknown" -> N.Unknown | "inapplicable" -> N.Inapplicable
  | _ -> Diagnostic.fail ~path "invalid_construction" "Unknown construction coding declaration."
let purpose ~path raw = match Json.string ~path raw with
  | "requested_payload" -> N.Role.Requested_payload | "helper" -> N.Role.Helper | "host_provider" -> N.Role.Host_provider
  | "assay_control" -> N.Role.Assay_control | "external_input" -> N.Role.External_input
  | _ -> Diagnostic.fail ~path "invalid_construction" "Unknown construction role purpose."

module Root_source = struct
  type t = {id : string; molecule : N.t; provenance : P.t}
  let schema_version = "biocompiler.construction_root_source.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id;
      "molecule", N.to_json value.molecule; "provenance", P.to_json value.provenance]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "molecule"; "provenance"] raw in
    let get key = Json.field ~path key fields in
    let value = {id = M.text ~path (get "id"); molecule = N.of_json ~path:(path ^ "/molecule") (get "molecule");
                 provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json value) value
  let make ~id ~molecule ~provenance = of_json (to_json {id; molecule; provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let molecule (value : t) = value.molecule
  let provenance (value : t) = value.provenance
end

module Value_ref = struct
  type kind = Root | Product
  type t = {kind : kind; id : string}
  let schema_version = "biocompiler.construction_value_ref.v0.1"
  let kind_name = function Root -> "root" | Product -> "product"
  let to_json (value : t) = obj ["schema_version", str schema_version; "kind", str (kind_name value.kind); "id", str value.id]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["kind"; "id"] raw in
    let kind = match Json.string ~path (Json.field "kind" fields) with
      | "root" -> Root | "product" -> Product | _ -> Diagnostic.fail ~path "invalid_construction" "Unknown construction reference kind." in
    let value = {kind; id = M.text ~path (Json.field "id" fields)} in
    finish ~path (to_json value) value
  let make ~kind ~id = of_json (to_json {kind; id})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let kind (value : t) = value.kind
  let id (value : t) = value.id
  let equal a b = a.kind = b.kind && a.id = b.id
end

module Selection = struct
  type t = {value : Value_ref.t; path : G.Path.t option}
  let schema_version = "biocompiler.construction_value_selection.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "value", Value_ref.to_json value.value;
                               "path", optional G.Path.to_json value.path]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["value"; "path"] raw in
    let value = {value = Value_ref.of_json ~path:(path ^ "/value") (Json.field "value" fields);
                 path = option (G.Path.of_json ~path:(path ^ "/path")) (Json.field "path" fields)} in
    finish ~path (to_json value) value
  let make ?path value = of_json (to_json {value; path})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let value (item : t) = item.value
  let path (item : t) = item.path
  let equal a b = Json.equal (to_json a) (to_json b)
end

module Output_member = struct
  type t = {id : string; value : Value_ref.t; space_id : string; form : N.form;
            sequence_extent : Molecule_chemistry.sequence_extent; coding_status : N.coding_status; provenance : P.t}
  let schema_version = "biocompiler.construction_output_member.v0.1"
  let to_json (item : t) = obj ["schema_version", str schema_version; "id", str item.id; "value", Value_ref.to_json item.value;
      "space_id", str item.space_id; "form", str (N.form_name item.form); "sequence_extent", str (extent_name item.sequence_extent);
      "coding_status", str (N.coding_status_name item.coding_status); "provenance", P.to_json item.provenance]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "value"; "space_id"; "form"; "sequence_extent"; "coding_status"; "provenance"] raw in
    let get key = Json.field ~path key fields in
    let value = {id = M.text ~path ~maximum:4080 (get "id"); value = Value_ref.of_json ~path:(path ^ "/value") (get "value");
        space_id = M.text ~path (get "space_id"); form = form ~path (get "form"); sequence_extent = extent ~path (get "sequence_extent");
        coding_status = coding ~path (get "coding_status"); provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json value) value
  let make ~id ~value ~space_id ~form ~sequence_extent ~coding_status ~provenance = of_json (to_json {id; value; space_id; form; sequence_extent; coding_status; provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (item : t) = item.id
  let value (item : t) = item.value
  let space_id (item : t) = item.space_id
  let form (item : t) = item.form
  let sequence_extent (item : t) = item.sequence_extent
  let coding_status (item : t) = item.coding_status
  let provenance (item : t) = item.provenance
end

module Role = struct
  type t = {id : string; role : string; purpose : N.Role.purpose; compartment : string}
  let schema_version = "biocompiler.construction_role_declaration.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id; "role", str value.role;
      "purpose", str (N.Role.purpose_name value.purpose); "compartment", str value.compartment]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "role"; "purpose"; "compartment"] raw in
    let get key = Json.field ~path key fields in
    let value = {id = M.text ~path (get "id"); role = M.text ~path (get "role"); purpose = purpose ~path (get "purpose");
                 compartment = M.text ~path (get "compartment")} in
    require ~path (value.compartment <> "abstract") "Construction roles require a physical compartment.";
    finish ~path (to_json value) value
  let make ~id ~role ~purpose ~compartment = of_json (to_json {id; role; purpose; compartment})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let role (value : t) = value.role
  let purpose (value : t) = value.purpose
  let compartment (value : t) = value.compartment
end

module Member_requirement = struct
  type category = Payload | Delivered_helper | Encoded_product | Host_provider | Experimental_input | Control | Assay_reference
  type subject = Materialized of string | External of {id : string; fingerprint : string}
  type t = {id : string; category : category; subject : subject; roles : Role.t list}
  let schema_version = "biocompiler.construction_member_requirement.v0.1"
  let category_name = function Payload -> "payload" | Delivered_helper -> "delivered_helper" | Encoded_product -> "encoded_product"
    | Host_provider -> "host_provider" | Experimental_input -> "experimental_input" | Control -> "control" | Assay_reference -> "assay_reference"
  let category_purpose = function Payload -> N.Role.Requested_payload | Delivered_helper | Encoded_product -> N.Role.Helper
    | Host_provider -> N.Role.Host_provider | Experimental_input -> N.Role.External_input | Control | Assay_reference -> N.Role.Assay_control
  let to_json (value : t) =
    let member, external_id, fingerprint = match value.subject with
      | Materialized id -> str id, Json.Null, Json.Null | External value -> Json.Null, str value.id, str value.fingerprint in
    obj ["schema_version", str schema_version; "id", str value.id; "category", str (category_name value.category);
         "member_id", member; "external_id", external_id; "external_fingerprint", fingerprint; "roles", array Role.to_json value.roles]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "category"; "member_id"; "external_id"; "external_fingerprint"; "roles"] raw in
    let get key = Json.field ~path key fields in
    let category = match Json.string ~path (get "category") with
      | "payload" -> Payload | "delivered_helper" -> Delivered_helper | "encoded_product" -> Encoded_product
      | "host_provider" -> Host_provider | "experimental_input" -> Experimental_input | "control" -> Control | "assay_reference" -> Assay_reference
      | _ -> Diagnostic.fail ~path "invalid_construction" "Unknown construction member category." in
    let subject = match get "member_id" with
      | Json.Null ->
          require ~path (not (List.mem category [Payload; Delivered_helper; Encoded_product])) "This category requires a materialized member.";
          External {id = M.text ~path (get "external_id"); fingerprint = hash ~path (get "external_fingerprint")}
      | value ->
          require ~path (get "external_id" = Json.Null && get "external_fingerprint" = Json.Null) "Materialized members cannot also declare external authority.";
          Materialized (M.text ~path value) in
    let roles = records ~path:(path ^ "/roles") ~maximum:max_role_declarations Role.of_json (get "roles")
        |> sorted ~path ~nonempty:true Role.id in
    require ~path (List.for_all (fun role -> Role.purpose role = category_purpose category) roles) "Member category and role purpose disagree.";
    let value = {id = M.text ~path (get "id"); category; subject; roles} in
    finish ~path (to_json value) value
  let make ~id ~category ~subject ~roles =
    ignore (M.bounded_length ~maximum:max_role_declarations roles);
    of_json (to_json {id; category; subject; roles})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let category (value : t) = value.category
  let subject (value : t) = value.subject
  let member_id (value : t) = match value.subject with Materialized id -> Some id | External _ -> None
  let roles (value : t) = value.roles
end

module Complex_constituent = struct
  type t = {member_id : string; stoichiometry : int option; provenance : P.t}
  let schema_version = "biocompiler.construction_complex_constituent.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "member_id", str value.member_id;
      "stoichiometry", optional Json.int value.stoichiometry; "provenance", P.to_json value.provenance]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["member_id"; "stoichiometry"; "provenance"] raw in
    let get key = Json.field ~path key fields in
    let stoichiometry = option (fun raw -> let value = Json.integer ~path raw in
        require ~path (Z.sign value > 0 && Z.compare value (Z.of_int M.max_residues) <= 0) "Complex count must be a positive bounded integer or explicit unknown.";
        Z.to_int value) (get "stoichiometry") in
    let value = {member_id = M.text ~path (get "member_id"); stoichiometry; provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json value) value
  let make ~member_id ~stoichiometry ~provenance = of_json (to_json {member_id; stoichiometry; provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let member_id (value : t) = value.member_id
  let stoichiometry (value : t) = value.stoichiometry
  let provenance (value : t) = value.provenance
end

module Complex_member = struct
  type t = {id : string; kind : N.Complex.kind; constituents : Complex_constituent.t list; provenance : P.t}
  let schema_version = "biocompiler.construction_complex_member.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id;
      "kind", str (N.Complex.kind_name value.kind); "constituents", array Complex_constituent.to_json value.constituents;
      "provenance", P.to_json value.provenance]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "kind"; "constituents"; "provenance"] raw in
    let get key = Json.field ~path key fields in
    let kind = match Json.string ~path (get "kind") with
      | "protein_complex" -> N.Complex.Protein_complex | "dna_duplex" -> N.Complex.Dna_duplex | "rna_complex" -> N.Complex.Rna_complex
      | _ -> Diagnostic.fail ~path "invalid_construction" "Unknown construction complex kind." in
    let constituents = records ~path:(path ^ "/constituents") ~maximum:max_output_members Complex_constituent.of_json (get "constituents")
        |> sorted ~path ~nonempty:true Complex_constituent.member_id in
    if List.for_all (fun item -> Complex_constituent.stoichiometry item <> None) constituents then
      require ~path (List.fold_left (fun sum item -> sum + Option.get (Complex_constituent.stoichiometry item)) 0 constituents >= 2)
        "A noncovalent complex requires at least two constituent copies.";
    require ~path (kind <> N.Complex.Dna_duplex || List.length constituents = 2 && List.for_all (fun item -> Complex_constituent.stoichiometry item = Some 1) constituents)
      "A DNA duplex plan requires two explicit single-copy strands.";
    let value = {id = M.text ~path (get "id"); kind; constituents; provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json value) value
  let make ~id ~kind ~constituents ~provenance =
    ignore (M.bounded_length ~maximum:max_output_members constituents);
    of_json (to_json {id; kind; constituents; provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let kind (value : t) = value.kind
  let constituents (value : t) = value.constituents
  let provenance (value : t) = value.provenance
end

module Amount_declaration = struct
  type quantity = Unknown | Integer of Z.t | Real of float
  type t = {id : string; subject_id : string; preparation_id : string; role_instance_ids : string list;
            quantity : quantity; unit : string; provenance : P.t}
  let schema_version = "biocompiler.construction_amount_declaration.v0.1"
  let quantity_json = function Unknown -> Json.Null | Integer value -> Json.Int value | Real value -> Json.Float value
  let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id; "subject_id", str value.subject_id;
      "preparation_id", str value.preparation_id; "role_instance_ids", array str value.role_instance_ids;
      "quantity", quantity_json value.quantity; "unit", str value.unit; "provenance", P.to_json value.provenance]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "subject_id"; "preparation_id"; "role_instance_ids"; "quantity"; "unit"; "provenance"] raw in
    let get key = Json.field ~path key fields in
    let text key = M.text ~path (get key) in
    let quantity = match get "quantity" with
      | Json.Null -> Unknown
      | Json.Int value -> require ~path (Z.sign value >= 0 && Z.numbits value <= 1024) "Amount integer must be nonnegative with at most 1024 bits."; Integer value
      | Json.Float value -> require ~path (Float.is_finite value && value >= 0.) "Amount must be finite and nonnegative."; Real value
      | _ -> Diagnostic.fail ~path "invalid_type" "Amount requires an integer, float or explicit unknown." in
    let value = {id = text "id"; subject_id = text "subject_id"; preparation_id = text "preparation_id";
        role_instance_ids = texts ~path ~maximum:max_role_declarations (get "role_instance_ids"); quantity; unit = text "unit";
        provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json value) value
  let make ~id ~subject_id ~preparation_id ~role_instance_ids ~quantity ~unit ~provenance =
    ignore (M.bounded_length ~maximum:max_role_declarations role_instance_ids);
    of_json (to_json {id; subject_id; preparation_id; role_instance_ids; quantity; unit; provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let subject_id (value : t) = value.subject_id
  let preparation_id (value : t) = value.preparation_id
  let role_instance_ids (value : t) = value.role_instance_ids
  let quantity (value : t) = value.quantity
  let unit (value : t) = value.unit
  let provenance (value : t) = value.provenance
end

module T = Molecular_transition
module R = Molecular_recoding
module Product_port = struct
  type t = {id : string; space_id : string; alphabet : G.alphabet; topology : G.topology;
            chemistry_transition : T.Chemistry.t; feature_transition : T.Feature.t}
  let schema_version = "biocompiler.construction_product_port.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id; "space_id", str value.space_id;
      "alphabet", str (alphabet_name value.alphabet); "topology", str (topology_name value.topology);
      "chemistry_transition", T.Chemistry.to_json value.chemistry_transition; "feature_transition", T.Feature.to_json value.feature_transition]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "space_id"; "alphabet"; "topology"; "chemistry_transition"; "feature_transition"] raw in
    let get key = Json.field ~path key fields in
    let value = {id = M.text ~path (get "id"); space_id = M.text ~path (get "space_id"); alphabet = alphabet ~path (get "alphabet");
        topology = topology ~path (get "topology"); chemistry_transition = T.Chemistry.of_json ~path:(path ^ "/chemistry_transition") (get "chemistry_transition");
        feature_transition = T.Feature.of_json ~path:(path ^ "/feature_transition") (get "feature_transition")} in
    finish ~path (to_json value) value
  let make ~id ~space_id ~alphabet ~topology ~chemistry_transition ~feature_transition =
    of_json (to_json {id; space_id; alphabet; topology; chemistry_transition; feature_transition})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let space_id (value : t) = value.space_id
  let alphabet (value : t) = value.alphabet
  let topology (value : t) = value.topology
  let chemistry_transition (value : t) = value.chemistry_transition
  let feature_transition (value : t) = value.feature_transition
end
module Processing_product = struct
  type t = {port_id : string; path : G.Path.t}
  let schema_version = "biocompiler.construction_processing_product.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "port_id", str value.port_id; "path", G.Path.to_json value.path]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["port_id"; "path"] raw in
    let value = {port_id = M.text ~path (Json.field ~path "port_id" fields); path = G.Path.of_json ~path:(path ^ "/path") (Json.field ~path "path" fields)} in
    finish ~path (to_json value) value
  let make ~port_id ~path = of_json (to_json {port_id; path})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let port_id (value : t) = value.port_id
  let path (value : t) = value.path
end
module Translation_product = struct
  type t = {port_id : string; input : Selection.t; policy : R.Translation_policy.t}
  let schema_version = "biocompiler.construction_translation_product.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "port_id", str value.port_id; "input", Selection.to_json value.input;
      "policy", R.Translation_policy.to_json value.policy]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["port_id"; "input"; "policy"] raw in
    let get key = Json.field ~path key fields in
    let value = {port_id = M.text ~path (get "port_id"); input = Selection.of_json ~path:(path ^ "/input") (get "input");
        policy = R.Translation_policy.of_json ~path:(path ^ "/policy") (get "policy")} in
    finish ~path (to_json value) value
  let make ~port_id ~input ~policy = of_json (to_json {port_id; input; policy})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let port_id (value : t) = value.port_id
  let input (value : t) = value.input
  let policy (value : t) = value.policy
end
module Translation_branch = struct
  type t = {id : string; condition : string; input : Selection.t; policy : R.Translation_policy.t option; port_id : string option}
  let schema_version = "biocompiler.construction_translation_branch.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id; "condition", str value.condition;
      "input", Selection.to_json value.input; "policy", optional R.Translation_policy.to_json value.policy; "port_id", optional str value.port_id]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "condition"; "input"; "policy"; "port_id"] raw in
    let get key = Json.field ~path key fields in
    let value = {id = M.text ~path (get "id"); condition = M.text ~path (get "condition");
        input = Selection.of_json ~path:(path ^ "/input") (get "input"); policy = option (R.Translation_policy.of_json ~path:(path ^ "/policy")) (get "policy");
        port_id = option (M.text ~path) (get "port_id")} in
    require ~path (Option.is_some value.policy = Option.is_some value.port_id) "A translation branch requires both a policy and product port, or neither.";
    finish ~path (to_json value) value
  let make ~id ~condition ~input ~policy ~port_id = of_json (to_json {id; condition; input; policy; port_id})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let condition (value : t) = value.condition
  let input (value : t) = value.input
  let policy (value : t) = value.policy
  let port_id (value : t) = value.port_id
end
module Peptide_product = struct
  type t = {port_id : string; residues : G.Span.t}
  let schema_version = "biocompiler.construction_peptide_product.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "port_id", str value.port_id; "residues", G.Span.to_json value.residues]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["port_id"; "residues"] raw in
    let value = {port_id = M.text ~path (Json.field ~path "port_id" fields); residues = G.Span.of_json ~path:(path ^ "/residues") (Json.field ~path "residues" fields)} in
    finish ~path (to_json value) value
  let make ~port_id ~residues = of_json (to_json {port_id; residues})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let port_id (value : t) = value.port_id
  let residues (value : t) = value.residues
end
module Operation = struct
  type orientation = Reverse | Reverse_complement
  type specification =
    | Slice of Selection.t
    | Concatenate of Selection.t list
    | Orientation of {input : Selection.t; action : orientation}
    | Transcription of Selection.t
    | Rna_cleavage of {input : Selection.t; products : Processing_product.t list}
    | Rna_splicing of {input : Selection.t; products : Processing_product.t list}
    | Protein_cleavage of {input : Selection.t; products : Processing_product.t list}
    | Protein_splicing of {input : Selection.t; products : Processing_product.t list}
    | Circularization of {input : Selection.t; origin : int}
    | Base_editing of {input : Selection.t; canonical_edits : R.Canonical_edit.t list; chemical_edits : R.Chemical_edit.t list}
    | Translation of {input : Selection.t; policy : R.Translation_policy.t}
    | Multi_orf_translation of Translation_product.t list
    | Conditional_translation of Translation_branch.t list
    | Ribosomal_skipping of {input : Selection.t; policy : R.Translation_policy.t; products : Peptide_product.t list; event_id : string}
  type t = specification
  let name = function Slice _ -> "slice" | Concatenate _ -> "concatenate" | Orientation _ -> "orientation" | Transcription _ -> "transcription"
    | Rna_cleavage _ -> "rna_cleavage" | Rna_splicing _ -> "rna_splicing" | Protein_cleavage _ -> "protein_cleavage" | Protein_splicing _ -> "protein_splicing"
    | Circularization _ -> "circularization" | Base_editing _ -> "base_editing" | Translation _ -> "translation" | Multi_orf_translation _ -> "multi_orf_translation"
    | Conditional_translation _ -> "conditional_translation" | Ribosomal_skipping _ -> "ribosomal_skipping"
  let schema_version value = "biocompiler.construction_" ^ name value ^ ".v0.1"
  let schema_versions = List.map (fun value -> "biocompiler.construction_" ^ value ^ ".v0.1")
      ["slice"; "concatenate"; "orientation"; "transcription"; "rna_cleavage"; "rna_splicing"; "protein_cleavage"; "protein_splicing";
       "circularization"; "base_editing"; "translation"; "multi_orf_translation"; "conditional_translation"; "ribosomal_skipping"]
  let processing input products = ["input", Selection.to_json input; "products", array Processing_product.to_json products]
  let to_json value =
    let fields = match value with
      | Slice input -> ["input", Selection.to_json input]
      | Concatenate inputs -> ["inputs", array Selection.to_json inputs]
      | Orientation {input; action} -> ["input", Selection.to_json input; "action", str (match action with Reverse -> "reverse" | Reverse_complement -> "reverse_complement")]
      | Transcription input -> ["input", Selection.to_json input; "mapping_profile", str transcription_mapping_profile]
      | Rna_cleavage {input; products} | Rna_splicing {input; products} | Protein_cleavage {input; products} | Protein_splicing {input; products} -> processing input products
      | Circularization {input; origin} -> ["input", Selection.to_json input; "origin", Json.Int (Z.of_int origin)]
      | Base_editing {input; canonical_edits; chemical_edits} -> ["input", Selection.to_json input; "canonical_edits", array R.Canonical_edit.to_json canonical_edits;
          "chemical_edits", array R.Chemical_edit.to_json chemical_edits]
      | Translation {input; policy} -> ["input", Selection.to_json input; "policy", R.Translation_policy.to_json policy]
      | Multi_orf_translation products -> ["products", array Translation_product.to_json products]
      | Conditional_translation branches -> ["branches", array Translation_branch.to_json branches]
      | Ribosomal_skipping {input; policy; products; event_id} -> ["input", Selection.to_json input; "policy", R.Translation_policy.to_json policy;
          "products", array Peptide_product.to_json products; "event_id", str event_id] in
    obj (("schema_version", str (schema_version value)) :: fields)
  let whole ~path input = require ~path (Selection.path input = None) "This operation requires a whole input; select a segment in a prior slice."
  let of_json ?(path = "") raw =
    M.bounded_tree ~path raw;
    let schema = Json.string ~path (Json.field ~path "schema_version" (Json.object_fields ~path raw)) in
    let fields keys = M.record ~path schema keys raw in
    let input fields = Selection.of_json ~path:(path ^ "/input") (Json.field ~path "input" fields) in
    let policy fields = R.Translation_policy.of_json ~path:(path ^ "/policy") (Json.field ~path "policy" fields) in
    let value = match schema with
      | "biocompiler.construction_slice.v0.1" -> Slice (input (fields ["input"]))
      | "biocompiler.construction_concatenate.v0.1" ->
          let fields = fields ["inputs"] in
          let inputs = records ~path:(path ^ "/inputs") ~maximum:max_selections Selection.of_json (Json.field "inputs" fields) in
          require ~path (inputs <> []) "Concatenation requires a nonempty ordered selection inventory."; Concatenate inputs
      | "biocompiler.construction_orientation.v0.1" ->
          let fields = fields ["input"; "action"] in
          let action = match Json.string ~path (Json.field "action" fields) with "reverse" -> Reverse | "reverse_complement" -> Reverse_complement
            | _ -> Diagnostic.fail ~path "invalid_construction" "Unknown orientation action." in
          Orientation {input = input fields; action}
      | "biocompiler.construction_transcription.v0.1" ->
          let fields = fields ["input"; "mapping_profile"] in
          require ~path (Json.string ~path (Json.field "mapping_profile" fields) = transcription_mapping_profile) "Unsupported transcription mapping profile.";
          Transcription (input fields)
      | ("biocompiler.construction_rna_cleavage.v0.1" | "biocompiler.construction_rna_splicing.v0.1"
        | "biocompiler.construction_protein_cleavage.v0.1" | "biocompiler.construction_protein_splicing.v0.1") ->
          let fields = fields ["input"; "products"] in
          let input = input fields in whole ~path input;
          let products = records ~path:(path ^ "/products") ~maximum:max_processing_products Processing_product.of_json (Json.field "products" fields)
            |> sorted ~path ~nonempty:true Processing_product.port_id in
          let cleavage = schema = "biocompiler.construction_rna_cleavage.v0.1" || schema = "biocompiler.construction_protein_cleavage.v0.1" in
          List.iter (fun product -> let product_path = Processing_product.path product in
              require ~path (G.Path.strand product_path = G.Forward) "Processing products require forward traversal.";
              require ~path (not cleavage || List.length (G.Path.spans product_path) = 1) "Cleavage products require a contiguous span.") products;
          if schema = "biocompiler.construction_rna_cleavage.v0.1" then Rna_cleavage {input; products}
          else if schema = "biocompiler.construction_rna_splicing.v0.1" then Rna_splicing {input; products}
          else if schema = "biocompiler.construction_protein_cleavage.v0.1" then Protein_cleavage {input; products}
          else Protein_splicing {input; products}
      | "biocompiler.construction_circularization.v0.1" ->
          let fields = fields ["input"; "origin"] in let input = input fields in whole ~path input;
          Circularization {input; origin = M.index ~path ~maximum:M.max_residues (Json.field "origin" fields)}
      | "biocompiler.construction_base_editing.v0.1" ->
          let fields = fields ["input"; "canonical_edits"; "chemical_edits"] in let input = input fields in whole ~path input;
          let canonical_edits = records ~path:(path ^ "/canonical_edits") ~maximum:R.max_recodings R.Canonical_edit.of_json (Json.field "canonical_edits" fields)
            |> sorted ~path R.Canonical_edit.position in
          let chemical_edits = records ~path:(path ^ "/chemical_edits") ~maximum:R.max_recodings R.Chemical_edit.of_json (Json.field "chemical_edits" fields)
            |> sorted ~path R.Chemical_edit.position in
          let count = List.length canonical_edits + List.length chemical_edits in
          require ~path (count >= 1 && count <= R.max_recodings) "Editing requires a bounded nonempty combined edit inventory.";
          List.iter (fun chemical -> require ~path (not (List.exists (fun canonical -> R.Canonical_edit.position canonical = R.Chemical_edit.position chemical) canonical_edits))
              "Canonical and chemical edits cannot overlap.") chemical_edits;
          Base_editing {input; canonical_edits; chemical_edits}
      | "biocompiler.construction_translation.v0.1" ->
          let fields = fields ["input"; "policy"] in Translation {input = input fields; policy = policy fields}
      | "biocompiler.construction_multi_orf_translation.v0.1" ->
          let fields = fields ["products"] in
          let products = records ~path:(path ^ "/products") ~maximum:max_translation_products Translation_product.of_json (Json.field "products" fields)
            |> sorted ~path ~nonempty:true Translation_product.port_id in
          let first = List.hd products |> Translation_product.input |> Selection.value in
          List.iter (fun product -> let selection = Translation_product.input product in
              require ~path (Value_ref.equal first (Selection.value selection)) "Multi-ORF products must bind the same source value.";
              require ~path (Option.is_some (Selection.path selection)) "Multi-ORF products require individual ORF paths.") products;
          Multi_orf_translation products
      | "biocompiler.construction_conditional_translation.v0.1" ->
          let fields = fields ["branches"] in
          let branches = records ~path:(path ^ "/branches") ~maximum:max_translation_branches Translation_branch.of_json (Json.field "branches" fields)
            |> sorted ~path ~nonempty:true Translation_branch.id in
          ignore (sorted ~path Translation_branch.condition branches);
          ignore (List.filter_map Translation_branch.port_id branches |> sorted ~path ~nonempty:true Fun.id);
          Conditional_translation branches
      | "biocompiler.construction_ribosomal_skipping.v0.1" ->
          let fields = fields ["input"; "policy"; "products"; "event_id"] in
          let products = records ~path:(path ^ "/products") ~maximum:max_translation_products Peptide_product.of_json (Json.field "products" fields)
            |> sorted ~path ~nonempty:true Peptide_product.port_id in
          Ribosomal_skipping {input = input fields; policy = policy fields; products; event_id = M.text ~path (Json.field "event_id" fields)}
      | _ -> Diagnostic.fail ~path "unsupported_schema" "Unsupported construction operation schema." in
    finish ~path (to_json value) value
  let make value =
    (match value with
     | Concatenate values -> ignore (M.bounded_length ~maximum:max_selections values)
     | Rna_cleavage {products; _} | Rna_splicing {products; _} | Protein_cleavage {products; _} | Protein_splicing {products; _} ->
         ignore (M.bounded_length ~maximum:max_processing_products products)
     | Base_editing {canonical_edits; chemical_edits; _} ->
         ignore (M.bounded_length ~maximum:R.max_recodings canonical_edits); ignore (M.bounded_length ~maximum:R.max_recodings chemical_edits)
     | Multi_orf_translation products -> ignore (M.bounded_length ~maximum:max_translation_products products)
     | Conditional_translation branches -> ignore (M.bounded_length ~maximum:max_translation_branches branches)
     | Ribosomal_skipping {products; _} -> ignore (M.bounded_length ~maximum:max_translation_products products)
     | Slice _ | Orientation _ | Transcription _ | Circularization _ | Translation _ -> ());
    of_json (to_json value)
  let specification value = value
  let fingerprint value = Canonical.fingerprint (to_json value)
  let distinct_selections values = List.fold_left (fun result value -> if List.exists (Selection.equal value) result then result else value :: result) [] values |> List.rev
  let selections = function
    | Concatenate values -> values
    | Multi_orf_translation values -> List.map Translation_product.input values |> distinct_selections
    | Conditional_translation values -> List.map Translation_branch.input values |> distinct_selections
    | Slice input | Transcription input | Orientation {input; _} | Rna_cleavage {input; _} | Rna_splicing {input; _}
    | Protein_cleavage {input; _} | Protein_splicing {input; _} | Circularization {input; _} | Base_editing {input; _}
    | Translation {input; _} | Ribosomal_skipping {input; _} -> [input]
  let conditions value =
    let policies = match value with
      | Translation {policy; _} | Ribosomal_skipping {policy; _} -> [policy]
      | Multi_orf_translation values -> List.map Translation_product.policy values
      | Conditional_translation values -> List.filter_map Translation_branch.policy values
      | _ -> [] in
    let conditions = List.fold_left (fun set policy -> List.fold_left (fun set recoding -> Ids.add (R.Codon_recoding.condition recoding) set)
        set (R.Translation_policy.recodings policy)) Ids.empty policies in
    let conditions = match value with
      | Conditional_translation values -> List.fold_left (fun set branch -> Ids.add (Translation_branch.condition branch) set) conditions values
      | Ribosomal_skipping {event_id; _} -> Ids.add event_id conditions
      | _ -> conditions in
    Ids.elements conditions
  let product_ids = function
    | Rna_cleavage {products; _} | Rna_splicing {products; _} | Protein_cleavage {products; _} | Protein_splicing {products; _} -> Some (List.map Processing_product.port_id products)
    | Multi_orf_translation products -> Some (List.map Translation_product.port_id products)
    | Conditional_translation branches -> Some (List.filter_map Translation_branch.port_id branches)
    | Ribosomal_skipping {products; _} -> Some (List.map Peptide_product.port_id products)
    | _ -> None
  let processing_products = function
    | Rna_cleavage {input; products} | Rna_splicing {input; products} | Protein_cleavage {input; products} | Protein_splicing {input; products} -> Some (input, products)
    | _ -> None
end
let operation_selections = Operation.selections
module Transform_step = struct
  type t = {id : string; operation : Operation.t; ports : Product_port.t list; assumptions : string list; provenance : P.t}
  let schema_version = "biocompiler.construction_transform_step.v0.1"
  let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id; "operation", Operation.to_json value.operation;
      "ports", array Product_port.to_json value.ports; "assumptions", array str value.assumptions; "provenance", P.to_json value.provenance]
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "operation"; "ports"; "assumptions"; "provenance"] raw in
    let get key = Json.field ~path key fields in
    let operation = Operation.of_json ~path:(path ^ "/operation") (get "operation") in
    let ports = records ~path:(path ^ "/ports") ~maximum:max_processing_products Product_port.of_json (get "ports") |> sorted ~path ~nonempty:true Product_port.id in
    (match Operation.product_ids operation with
     | None -> require ~path (List.length ports = 1) "This operation requires exactly one product port."
     | Some expected -> require ~path (Ids.equal (Ids.of_list expected) (Ids.of_list (List.map Product_port.id ports))) "Recipe ports must exactly match the step product ports.");
    let assumptions = texts ~path:(path ^ "/assumptions") ~maximum:max_assumptions (get "assumptions") in
    require ~path (Ids.subset (Ids.of_list (Operation.conditions operation)) (Ids.of_list assumptions)) "Every conditional, recoding and skipping event requires an exact declared assumption.";
    let sources = Operation.selections operation |> List.map (fun selection -> Value_ref.id (Selection.value selection)) |> Ids.of_list in
    List.iter (fun port ->
        List.iter (fun item -> require ~path (Ids.mem (T.Chemistry_disposition.source_id item) sources) "Chemistry dispositions must bind operation inputs.")
          (T.Chemistry.dispositions (Product_port.chemistry_transition port));
        List.iter (fun item -> require ~path (Ids.mem (T.Feature_disposition.source_id item) sources) "Feature dispositions must bind operation inputs.")
          (T.Feature.dispositions (Product_port.feature_transition port))) ports;
    let value = {id = M.text ~path (get "id"); operation; ports; assumptions; provenance = P.of_json ~path:(path ^ "/provenance") (get "provenance")} in
    finish ~path (to_json value) value
  let make ~id ~operation ~ports ~assumptions ~provenance =
    ignore (M.bounded_length ~maximum:max_processing_products ports); ignore (M.bounded_length ~maximum:max_assumptions assumptions);
    let budget = emission_budget () in
    reserve_json budget (Operation.to_json operation); preflight_children Product_port.to_json ports budget;
    of_json (to_json {id; operation; ports; assumptions; provenance})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let operation (value : t) = value.operation
  let ports (value : t) = value.ports
  let assumptions (value : t) = value.assumptions
  let provenance (value : t) = value.provenance
end

module Request = struct
  type mode = Strict | Diagnostic
  type t = {id : string; circuit : Circuit_request.t; sources : Root_source.t list; steps : Transform_step.t list;
            output_members : Output_member.t list; requirements : Member_requirement.t list; mode : mode;
            complex_members : Complex_member.t list; amounts : Amount_declaration.t list; payload_structures : Payload_structure.t list}
  type available = Source of G.Space.t | Product of Product_port.t
  let schema_version = "biocompiler.circuit_construction_request.v0.1"
  let mode_name = function Strict -> "strict" | Diagnostic -> "diagnostic"
  let to_json (value : t) = obj ["schema_version", str schema_version; "id", str value.id; "circuit", Circuit_request.to_json value.circuit;
      "sources", array Root_source.to_json value.sources; "steps", array Transform_step.to_json value.steps;
      "output_members", array Output_member.to_json value.output_members; "requirements", array Member_requirement.to_json value.requirements;
      "mode", str (mode_name value.mode); "complex_members", array Complex_member.to_json value.complex_members;
      "amounts", array Amount_declaration.to_json value.amounts; "payload_structures", array Payload_structure.to_json value.payload_structures]
  let frame_id = function Source frame -> G.Space.id frame |> G.Space_id.to_string | Product port -> Product_port.space_id port
  let resolve ~path available reference =
    match Names.find_opt (Value_ref.id reference) available, Value_ref.kind reference with
    | Some (Source _ as value), Value_ref.Root | Some (Product _ as value), Value_ref.Product -> value
    | _ -> Diagnostic.fail ~path "invalid_construction" "Missing, forward or wrong-kind construction value reference."
  let validate ~path value =
    require ~path (List.fold_left (fun count source -> count + String.length (N.sequence (Root_source.molecule source))) 0 value.sources <= max_total_source_residues)
      "Total supplied source residue limit exceeded.";
    require ~path (List.fold_left (fun count step -> count + List.length (Transform_step.ports step)) 0 value.steps <= max_products)
      "Construction product inventory limit exceeded.";
    let frames = ref Names.empty and root_frames = ref Ids.empty and available = ref Names.empty in
    let register frame =
      let id = G.Space.id frame |> G.Space_id.to_string and fingerprint = G.Space.fingerprint frame in
      (match Names.find_opt id !frames with None -> () | Some previous -> require ~path (previous = fingerprint) "Conflicting source coordinate-space authority.");
      frames := Names.add id fingerprint !frames in
    List.iter (fun source ->
        let molecule = Root_source.molecule source in let frame = N.space molecule in
        let id = G.Space.id frame |> G.Space_id.to_string in
        require ~path (not (Ids.mem id !root_frames)) "Root molecules require distinct destination coordinate spaces.";
        root_frames := Ids.add id !root_frames; register frame;
        List.iter (fun origin -> register (N.Assembly_origin.source_space origin)) (N.assembly molecule);
        available := Names.add (Root_source.id source) (Source frame) !available) value.sources;
    let reserved = ref (Names.fold (fun id _ set -> Ids.add id set) !frames Ids.empty) in
    List.iter (fun step ->
        let operation = Transform_step.operation step in
        List.iter (fun selection ->
            let frame = resolve ~path !available (Selection.value selection) in
            Option.iter (fun selection_path ->
                require ~path ((G.Path.space_id selection_path |> G.Space_id.to_string) = frame_id frame) "Selection path names a different source or product frame.";
                match frame with Source frame -> G.Path.validate_for selection_path frame | Product _ -> ()) (Selection.path selection))
          (Operation.selections operation);
        Option.iter (fun (input, products) ->
            let frame = resolve ~path !available (Selection.value input) in
            List.iter (fun product -> require ~path ((G.Path.space_id (Processing_product.path product) |> G.Space_id.to_string) = frame_id frame)
                "Processing product paths must name the whole bound input frame.") products) (Operation.processing_products operation);
        List.iter (fun port ->
            require ~path (not (Names.mem (Product_port.id port) !available)) "Root and product value identities must be globally unique.";
            require ~path (not (Ids.mem (Product_port.space_id port) !reserved)) "Product frames must be new coordinate identities.";
            reserved := Ids.add (Product_port.space_id port) !reserved;
            available := Names.add (Product_port.id port) (Product port) !available) (Transform_step.ports step)) value.steps;
    let members = List.map Output_member.id value.output_members |> Ids.of_list
    and complexes = List.map Complex_member.id value.complex_members |> Ids.of_list in
    require ~path (Ids.is_empty (Ids.inter members complexes)) "Covalent and complex members require distinct identities.";
    List.iter (fun complex -> List.iter (fun constituent -> require ~path (Ids.mem (Complex_constituent.member_id constituent) members)
          "Complex constituents must reference final covalent output members.") (Complex_member.constituents complex)) value.complex_members;
    let subjects = Ids.union members complexes in
    List.iter (fun member ->
        ignore (resolve ~path !available (Output_member.value member));
        require ~path (not (Ids.mem (Output_member.space_id member) !reserved)) "Final output frames must be new coordinate identities.";
        reserved := Ids.add (Output_member.space_id member) !reserved) value.output_members;
    let demanded = ref (List.fold_left (fun set member -> let reference = Output_member.value member in
        if Value_ref.kind reference = Value_ref.Product then Ids.add (Value_ref.id reference) set else set) Ids.empty value.output_members) in
    List.iter (fun step ->
        List.iter (fun port -> require ~path (Ids.mem (Product_port.id port) !demanded) "Every executable product port must contribute to an output member.") (Transform_step.ports step);
        List.iter (fun selection -> let reference = Selection.value selection in if Value_ref.kind reference = Value_ref.Product then
              demanded := Ids.add (Value_ref.id reference) !demanded) (Operation.selections (Transform_step.operation step))) (List.rev value.steps);
    let providers = Circuit_request.requirements value.circuit |> List.concat_map Circuit_request.Requirement.dependencies in
    let provider_pins = List.map (fun provider -> (Circuit_request.Provider.id provider, Circuit_request.Provider.fingerprint provider), provider) providers in
    let target = Circuit_request.Profile.target (Circuit_request.profile value.circuit) in
    let target_compartments = Option.map (fun target -> Build_request.Target.compartments target |> Ids.of_list) target in
    let covered = ref Ids.empty and role_subjects = ref Names.empty and total_roles = ref 0 in
    List.iter (fun requirement ->
        (match Member_requirement.subject requirement with
         | Member_requirement.Materialized id -> require ~path (Ids.mem id subjects) "Required member refers to an absent output member."; covered := Ids.add id !covered
         | Member_requirement.External {id; fingerprint} ->
             let provider = match List.assoc_opt (id, fingerprint) provider_pins with Some value -> value
               | None -> Diagnostic.fail ~path "invalid_construction" "External requirement must retain a complete original provider identity." in
             let expected_kind = match Member_requirement.category requirement with Member_requirement.Host_provider -> Some "host"
               | Member_requirement.Experimental_input -> Some "external_input" | _ -> None in
             Option.iter (fun kind -> require ~path (Circuit_request.Provider.kind provider = kind) "External category must retain the original provider kind.") expected_kind;
             List.iter (fun role -> require ~path (Role.compartment role = Circuit_request.Provider.compartment provider)
                 "External roles must retain the provider compartment.") (Member_requirement.roles requirement));
        List.iter (fun role ->
            require ~path (not (Names.mem (Role.id role) !role_subjects)) "Role declaration IDs must be globally unique.";
            role_subjects := Names.add (Role.id role) (Member_requirement.member_id requirement) !role_subjects;
            incr total_roles; require ~path (!total_roles <= max_role_declarations) "Construction role inventory limit exceeded.";
            Option.iter (fun compartments -> require ~path (Ids.mem (Role.compartment role) compartments) "Construction roles must retain target compartments.") target_compartments)
          (Member_requirement.roles requirement)) value.requirements;
    require ~path (Ids.equal !covered subjects) "Every output member and complex needs an explicit required-member disposition.";
    require ~path (List.exists (fun requirement -> Member_requirement.category requirement = Member_requirement.Payload) value.requirements) "Construction requires an explicit payload member.";
    let preparations = Hashtbl.create max_amount_declarations in
    List.iter (fun amount ->
        require ~path (Ids.mem (Amount_declaration.subject_id amount) subjects) "Amount must reference a final covalent or complex member.";
        List.iter (fun id -> require ~path (Names.find_opt id !role_subjects = Some (Some (Amount_declaration.subject_id amount)))
            "Amount role must refer to the same declared subject.") (Amount_declaration.role_instance_ids amount);
        let key = Amount_declaration.preparation_id amount, Amount_declaration.subject_id amount in
        require ~path (not (Hashtbl.mem preparations key)) "Subject/preparation amount must be declared once with all shared roles.";
        Hashtbl.add preparations key ()) value.amounts
  let of_json ?(path = "") raw =
    let fields = M.record ~path schema_version ["id"; "circuit"; "sources"; "steps"; "output_members"; "requirements"; "mode"; "complex_members"; "amounts"; "payload_structures"] raw in
    let get key = Json.field ~path key fields in
    let circuit = match Circuit_request.of_json (get "circuit") with Circuit_request.Decoded value -> value
      | Circuit_request.Unsupported _ -> Diagnostic.fail ~path "unsupported_construction_authority" "Construction requires complete supported circuit authority." in
    let mode = match Json.string ~path (get "mode") with "strict" -> Strict | "diagnostic" -> Diagnostic
      | _ -> Diagnostic.fail ~path "invalid_construction" "Unknown construction mode." in
    let sources = records ~path:(path ^ "/sources") ~maximum:max_sources Root_source.of_json (get "sources") |> sorted ~path ~nonempty:true Root_source.id in
    let steps = records ~path:(path ^ "/steps") ~maximum:max_steps Transform_step.of_json (get "steps") in
    ignore (sorted ~path Transform_step.id steps);
    let output_members = records ~path:(path ^ "/output_members") ~maximum:max_output_members Output_member.of_json (get "output_members") |> sorted ~path ~nonempty:true Output_member.id in
    let requirements = records ~path:(path ^ "/requirements") ~maximum:max_member_requirements Member_requirement.of_json (get "requirements") |> sorted ~path ~nonempty:true Member_requirement.id in
    let complex_members = records ~path:(path ^ "/complex_members") ~maximum:max_complex_members Complex_member.of_json (get "complex_members") |> sorted ~path Complex_member.id in
    let amounts = records ~path:(path ^ "/amounts") ~maximum:max_amount_declarations Amount_declaration.of_json (get "amounts") |> sorted ~path Amount_declaration.id in
    let payload_structures = records ~path:(path ^ "/payload_structures") ~maximum:Payload_structure.max_contracts Payload_structure.of_json (get "payload_structures") |> sorted ~path Payload_structure.member_id in
    let value = {id = M.text ~path ~maximum:4080 (get "id"); circuit; sources; steps; output_members; requirements; mode; complex_members; amounts; payload_structures} in
    validate ~path value; finish ~path (to_json value) value
  let make ?(complex_members = []) ?(amounts = []) ?(payload_structures = []) ~id ~circuit ~sources ~steps ~output_members ~requirements ~mode () =
    ignore (M.bounded_length ~maximum:max_sources sources); ignore (M.bounded_length ~maximum:max_steps steps);
    ignore (M.bounded_length ~maximum:max_output_members output_members); ignore (M.bounded_length ~maximum:max_member_requirements requirements);
    ignore (M.bounded_length ~maximum:max_complex_members complex_members); ignore (M.bounded_length ~maximum:max_amount_declarations amounts);
    ignore (M.bounded_length ~maximum:Payload_structure.max_contracts payload_structures);
    let budget = emission_budget () in
    reserve_json budget (Circuit_request.to_json circuit);
    preflight_children Root_source.to_json sources budget; preflight_children Transform_step.to_json steps budget;
    preflight_children Output_member.to_json output_members budget; preflight_children Member_requirement.to_json requirements budget;
    preflight_children Complex_member.to_json complex_members budget; preflight_children Amount_declaration.to_json amounts budget;
    preflight_children Payload_structure.to_json payload_structures budget;
    of_json (to_json {id; circuit; sources; steps; output_members; requirements; mode; complex_members; amounts; payload_structures})
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id (value : t) = value.id
  let circuit (value : t) = value.circuit
  let sources (value : t) = value.sources
  let steps (value : t) = value.steps
  let output_members (value : t) = value.output_members
  let requirements (value : t) = value.requirements
  let mode (value : t) = value.mode
  let complex_members (value : t) = value.complex_members
  let amounts (value : t) = value.amounts
  let payload_structures (value : t) = value.payload_structures
end
