open Bioc_wire
module C = Component_contract
module V = C.Value_domain
module O = C.Operating_domain
module P = C.Port
module N = Runtime_number
module Names = Map.Make (String)
module Pinned_identity = Pinned_identity
type scope = P.scope = Cell | Contact
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let require ?path condition message = Diagnostic.require ?path condition "component_record" message
let limit ?path condition = Diagnostic.require ?path condition "component_resource_limit" "Component declaration exceeds its native resource bound."
let scope_name = function Cell -> "cell" | Contact -> "contact"
let scope ~path value = match Json.string ~path value with
  | "cell" -> Cell | "contact" -> Contact | _ -> Diagnostic.fail ~path "component_record" "Component scope must be cell or contact."
let option_json encode = function None -> Json.Null | Some value -> encode value
let optional decode = function Json.Null -> None | value -> Some (decode value)
let bounded ~path value =
  let nodes = ref 0 and bytes = ref 0 in
  let add amount = limit ~path (amount <= Limits.max_response_bytes - !bytes); bytes := !bytes + amount in
  let node () = incr nodes; limit ~path (!nodes <= Limits.max_json_nodes) in
  let quoted text =
    limit ~path (String.length text <= Limits.max_string_bytes); add 2; add (String.length text);
    String.iter (function '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> add 1
      | value when Char.code value < 32 -> add 5 | _ -> ()) text;
    Json.validate_utf8 text in
  let rec visit depth value =
    limit ~path (depth <= Limits.max_depth); node ();
    match value with
    | Json.Null -> add 4 | Json.Bool value -> add (if value then 4 else 5)
    | Json.Int value ->
        limit ~path (Z.numbits value <= 4 * Limits.max_number_chars);
        let text = Z.to_string value in limit ~path (String.length text <= Limits.max_number_chars); add (String.length text)
    | Json.Float value ->
        Diagnostic.require ~path (Float.is_finite value) "nonfinite_number" "Nonfinite component declaration number.";
        add (String.length (Canonical.float_string value))
    | Json.String value -> quoted value
    | Json.Array values ->
        add 2; let first = ref true in
        List.iter (fun value -> if !first then first := false else add 1; visit (depth + 1) value) values
    | Json.Object values ->
        add 2; let seen = Hashtbl.create 16 and first = ref true in
        List.iter (fun (key, value) -> node (); quoted key;
            Diagnostic.require ~path (not (Hashtbl.mem seen key)) "duplicate_key" "Duplicate component declaration key.";
            Hashtbl.add seen key (); if !first then first := false else add 1;
            add 1; visit (depth + 1) value) values
  in visit 0 value
let record ~path schema keys value =
  bounded ~path value;
  let fields = Json.object_fields ~path value in
  Json.exact_fields ~path ("schema_version" :: keys) fields;
  Diagnostic.require ~path (Json.string (Json.field "schema_version" fields) = schema)
    "unsupported_schema" "Unsupported component declaration schema.";
  fields
let get ~path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let names ~path value =
  let values = Json.array ~path value |> List.map (Json.name ~path) in
  require ~path (List.length values = List.length (List.sort_uniq String.compare values)) "Duplicate component names.";
  values
let encoded_array encode values =
  let rec count remaining = function
    | [] -> () | _ :: rest -> limit (remaining > 0); count (remaining - 1) rest in
  count Limits.max_json_nodes values;
  arr (List.map encode values)
let strings = encoded_array str
let finite ~path value = match N.of_json ~path value with
  | value -> value
  | exception Diagnostic.Error _ -> Diagnostic.fail ~path "component_record" "Component quantity must be a finite number, not a Boolean."
let sorted_by_id ~path id values =
  let sorted = List.sort (fun a b -> String.compare (id a) (id b)) values in
  let rec unique = function
    | first :: ((second :: _) as rest) -> require ~path (id first <> id second) "Duplicate component inventory identity."; unique rest
    | _ -> () in
  unique sorted; sorted
(* Attribute normalization is compared like Python dict equality, preserving
   original numeric spellings after validation. Fingerprint equality is stricter. *)
let rec policy_equal a b = match a, b with
  | (Json.Int _ | Json.Float _), (Json.Int _ | Json.Float _) -> Json.number_compare a b = 0
  | Json.Array a, Json.Array b -> List.length a = List.length b && List.for_all2 policy_equal a b
  | Json.Object a, Json.Object b ->
      List.length a = List.length b && List.for_all (fun (key, value) ->
          match List.assoc_opt key b with None -> false | Some other -> policy_equal value other) a
  | _ -> Json.equal a b

module Synthetic_operator = struct
  type t = { operation : C.synthetic_operation; attributes : Json.t; input_ports : string list; output_port : string }
  let schema_version = "biocompiler.synthetic_operator_model.v0.1"
  let transition_policy = "biocompiler.synthetic_component_dynamics.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["operation"; "attributes"; "input_ports"; "output_port"; "policy"] value in
    let field key = get ~path key fields in
    let operation = match C.synthetic_operation_of_string (Json.string ~path (field "operation")) with
      | value -> value | exception Diagnostic.Error _ -> Diagnostic.fail ~path "component_record" "Unsupported synthetic component operation." in
    let attributes = field "attributes" in
    let expected = match operation with C.Constant -> ["value"] | C.Compare -> ["operator"]
      | C.Held_for | C.Pulse | C.Memory -> ["duration"] | _ -> [] in
    let attrs = Json.object_fields ~path attributes in
    require ~path (List.sort String.compare (List.map fst attrs) = List.sort String.compare expected) "Unexpected executable operator attributes.";
    let input_ports = names ~path:(path ^ "/input_ports") (field "input_ports") in
    let output_port = Json.name ~path:(path ^ "/output_port") (field "output_port") in
    require ~path (not (List.mem output_port input_ports)) "Operator ports must be distinct.";
    require ~path (field "policy" = str transition_policy) "Unsupported synthetic transition policy.";
    { operation; attributes; input_ports; output_port }
  let to_json value = obj ["schema_version", str schema_version; "operation", str (C.synthetic_operation_name value.operation);
    "attributes", value.attributes; "input_ports", strings value.input_ports; "output_port", str value.output_port; "policy", str transition_policy]
  let fingerprint value = Canonical.fingerprint (to_json value)
  let make ~operation ~attributes ~input_ports ~output_port = of_json (to_json { operation; attributes; input_ports; output_port })
  let operation value = value.operation
  let attributes value = value.attributes
  let input_ports value = value.input_ports
  let output_port value = value.output_port
  let policy _ = transition_policy
  let inventory ports =
    let rec collect count result = function
      | [] -> result
      | port :: rest ->
          limit (count < Limits.max_json_nodes);
          require (not (Names.mem (P.id port) result)) "Executable port IDs must be unique.";
          collect (count + 1) (Names.add (P.id port) port result) rest
    in collect 0 Names.empty ports
  let lookup map identity = match Names.find_opt identity map with Some value -> value
    | None -> Diagnostic.fail "component_record" "Executable operator refers to an absent port."
  let domain_checks value ~ports ~supported_domain =
    let map = inventory ports in
    let output = lookup map value.output_port in
    let incoming = List.map (lookup map) value.input_ports in
    let max_contacts = match List.assoc_opt "concurrent_contacts" (O.constraints supported_domain) with
      | Some domain when V.kind domain = V.Scalar_interval -> V.upper domain | _ -> None in
    List.filter_map (fun (initialization, getter) ->
        match C.synthetic_output_domain ~operation:value.operation ~attributes:value.attributes ~inputs:(List.map getter incoming)
            ~dtype:(P.dtype output) ~initialization ?max_contacts () with
        | None -> None | Some inferred -> Some (C.domain_subset ~required:inferred ~supported:(getter output)))
      [false, P.domain; true, P.initialization]
  let validate_ports value ~ports ~supported_domain =
    let map = inventory ports in
    require (List.for_all (fun port -> P.unit port = C.canonical_synthetic_unit (P.dtype port)) ports)
      "Executable synthetic ports require canonical units.";
    require (List.map fst (Names.bindings map) = List.sort String.compare (value.output_port :: value.input_ports))
      "Executable operator must cover exactly its declared ports.";
    let output = lookup map value.output_port and incoming = List.map (lookup map) value.input_ports in
    require (P.direction output = P.Output && List.for_all (fun port -> P.direction port = P.Input) incoming)
      "Executable port directions disagree.";
    let attrs = Json.object_fields value.attributes in
    let field key = Json.field key attrs in
    let binding expected raw =
      match Type_spec.normalize_binding ~expected raw with
      | normalized -> normalized
      | exception Diagnostic.Error _ -> Diagnostic.fail "component_record" "Invalid typed executable operator literal." in
    let normalized = match value.operation with
      | C.Constant ->
          let literal = field "value" in
          let normalized = if Type_spec.kind (P.dtype output) = Type_spec.Condition then (
              require (match literal with Json.Bool _ -> true | _ -> false) "Boolean output requires a Boolean literal."; literal)
            else binding (P.dtype output) literal in
          obj ["value", normalized]
      | C.Compare ->
          require (List.mem (field "operator") (List.map str ["lt"; "le"; "gt"; "ge"; "eq"; "ne"])) "Unknown comparison operator.";
          value.attributes
      | C.Held_for | C.Pulse | C.Memory ->
          let raw = field "duration" in
          if value.operation = C.Memory && raw = Json.Null then value.attributes
          else let duration = Type_spec.of_json (obj ["kind", str "scalar"; "name", str "Duration"; "dimensions", obj ["time", Json.int 1]]) in
            let normalized = binding duration raw in
            require (Json.number_compare (Json.field "canonical_value" (Json.object_fields normalized)) (Json.int 0) > 0)
              "Executable duration must be positive.";
            obj ["duration", normalized]
      | _ -> value.attributes in
    require (policy_equal normalized value.attributes) "Executable attributes must use complete canonical typed literals.";
    let count = match value.operation with
      | C.Input | C.Constant -> Some 0
      | C.Not | C.Output | C.Held_for | C.Onset | C.Pulse | C.Any_contact -> Some 1
      | C.Memory | C.Compare -> Some 2 | C.Select -> Some 3 | C.And | C.Or -> None in
    require (match count with None -> List.length incoming >= 2 | Some count -> List.length incoming = count) "Executable input count is incorrect.";
    List.iter (fun port ->
        require (P.role port = P.role output && P.compartment port = P.compartment output) "Executable operators cannot cross roles or compartments.";
        require (P.scope port <> Contact || P.scope output <> Cell || value.operation = C.Any_contact) "Contact-to-cell execution requires explicit aggregation.") incoming;
    if List.mem value.operation [C.And; C.Or; C.Not; C.Held_for; C.Onset; C.Pulse; C.Memory; C.Any_contact] then
      require (Type_spec.kind (P.dtype output) = Type_spec.Condition && List.for_all (fun port -> Type_spec.kind (P.dtype port) = Type_spec.Condition) incoming)
        "Logical and temporal operators require Boolean ports.";
    if value.operation = C.Memory then require (P.scope output = Cell) "Executable memory requires cell scope.";
    if value.operation = C.Any_contact then
      require (P.scope output = Cell && P.scope (List.hd incoming) = Contact) "Aggregation needs a contact input and cell output.";
    if value.operation = C.Compare then
      require (Type_spec.kind (P.dtype output) = Type_spec.Condition && List.for_all (fun port -> Type_spec.kind (P.dtype port) = Type_spec.Scalar) incoming
        && Type_spec.compatible (P.dtype (List.nth incoming 0)) (P.dtype (List.nth incoming 1))) "Comparison port types disagree.";
    if value.operation = C.Select then
      require (Type_spec.kind (P.dtype (List.hd incoming)) = Type_spec.Condition
        && List.for_all (fun port -> Type_spec.compatible (P.dtype output) (P.dtype port)) (List.tl incoming)) "Selection port types disagree.";
    if value.operation = C.Output then require (Type_spec.compatible (P.dtype output) (P.dtype (List.hd incoming))) "Output port types disagree.";
    let event_output = value.operation = C.Onset || (value.operation = C.Any_contact && P.timing (List.hd incoming) = P.Temporal_event) in
    let temporal = P.timing output <> P.Stateless in
    require (P.timing output = (if event_output then P.Temporal_event else if temporal then P.Temporal_level else P.Stateless))
      "Executable output event/level timing is inconsistent.";
    List.iteri (fun index port ->
        let expects_event = (List.mem value.operation [C.Pulse; C.Memory] && index = 0) || (value.operation = C.Any_contact && event_output) in
        require (P.timing port = (if expects_event then P.Temporal_event else if temporal then P.Temporal_level else P.Stateless))
          "Executable input event/level timing is inconsistent.") incoming;
    if List.mem value.operation [C.Held_for; C.Onset; C.Pulse; C.Memory] then require temporal "Stateful operators require temporal timing.";
    require (List.for_all (fun check -> C.status check <> C.Fail) (domain_checks value ~ports ~supported_domain))
      "Executable output domain excludes possible values."
end

module Parameter = struct
  type t = { id : string; value : V.t; source : Pinned_identity.t; method_name : string }
  let schema_version = "biocompiler.component_parameter.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["id"; "value"; "source"; "method"] value in
    let field key = get ~path key fields in
    { id = Json.name ~path (field "id"); value = V.of_json ~path:(path ^ "/value") (field "value");
      source = Pinned_identity.of_json ~path:(path ^ "/source") (field "source"); method_name = Json.name ~path (field "method") }
  let to_json value = obj ["schema_version", str schema_version; "id", str value.id; "value", V.to_json value.value;
    "source", Pinned_identity.to_json value.source; "method", str value.method_name]
  let make ~id ~value ~source ~method_name = of_json (to_json { id; value; source; method_name })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id value = value.id
  let value item = item.value
  let source value = value.source
  let method_name value = value.method_name
end
module Dependency = struct
  type t = { id : string; capability : string; role : string; scope : scope; compartment : string; required : bool }
  let schema_version = "biocompiler.component_dependency.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["id"; "capability"; "role"; "scope"; "compartment"; "required"] value in
    let field key = get ~path key fields in let name key = Json.name ~path (field key) in
    { id = name "id"; capability = name "capability"; role = name "role"; scope = scope ~path (field "scope");
      compartment = name "compartment"; required = Json.boolean ~path (field "required") }
  let to_json value = obj ["schema_version", str schema_version; "id", str value.id; "capability", str value.capability;
    "role", str value.role; "scope", str (scope_name value.scope); "compartment", str value.compartment; "required", Json.Bool value.required]
  let make ~id ~capability ~role ~scope ~compartment ~required = of_json (to_json { id; capability; role; scope; compartment; required })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id value = value.id
  let capability value = value.capability
  let role value = value.role
  let scope value = value.scope
  let compartment value = value.compartment
  let required value = value.required
end
module Capability = struct
  type t = { id : string; role : string; scope : scope; compartment : string }
  let schema_version = "biocompiler.component_capability.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["id"; "role"; "scope"; "compartment"] value in
    let field key = get ~path key fields in let name key = Json.name ~path (field key) in
    { id = name "id"; role = name "role"; scope = scope ~path (field "scope"); compartment = name "compartment" }
  let to_json value = obj ["schema_version", str schema_version; "id", str value.id; "role", str value.role;
    "scope", str (scope_name value.scope); "compartment", str value.compartment]
  let make ~id ~role ~scope ~compartment = of_json (to_json { id; role; scope; compartment })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id value = value.id
  let role value = value.role
  let scope value = value.scope
  let compartment value = value.compartment
end
module Resource = struct
  type t = { id : string; resource : string; amount : N.t option; unit : string; dtype : Type_spec.t;
    reusable : bool; role : string; scope : scope; compartment : string }
  let schema_version = "biocompiler.component_resource_reservation.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["id"; "resource"; "amount"; "unit"; "dtype"; "reusable"; "role"; "scope"; "compartment"] value in
    let field key = get ~path key fields in let name key = Json.name ~path (field key) in
    let dtype = Type_spec.of_json ~path:(path ^ "/dtype") (field "dtype") in
    require ~path (Type_spec.kind dtype = Type_spec.Scalar) "Resource quantities require scalar types.";
    let amount = optional (finite ~path:(path ^ "/amount")) (field "amount") in
    require ~path (Option.fold ~none:true ~some:(fun value -> N.compare value N.zero >= 0) amount) "Resource amount cannot be negative.";
    { id = name "id"; resource = name "resource"; amount; unit = name "unit"; dtype; reusable = Json.boolean ~path (field "reusable");
      role = name "role"; scope = scope ~path (field "scope"); compartment = name "compartment" }
  let to_json value = obj ["schema_version", str schema_version; "id", str value.id; "resource", str value.resource;
    "amount", option_json N.to_json value.amount; "unit", str value.unit; "dtype", Type_spec.to_json value.dtype;
    "reusable", Json.Bool value.reusable; "role", str value.role; "scope", str (scope_name value.scope); "compartment", str value.compartment]
  let make ~id ~resource ~amount ~unit ~dtype ~reusable ~role ~scope ~compartment =
    of_json (to_json { id; resource; amount; unit; dtype; reusable; role; scope; compartment })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let id value = value.id
  let resource value = value.resource
  let amount value = value.amount
  let unit value = value.unit
  let dtype value = value.dtype
  let reusable value = value.reusable
  let role value = value.role
  let scope value = value.scope
  let compartment value = value.compartment
end
module Sequence_reference = struct
  type artifact_class = Coding_dna | Coding_rna | Protein
  type t = { artifact_class : artifact_class; sequence_length : Z.t; unknown_features : string list }
  let schema_version = "biocompiler.component_sequence_reference.v0.1"
  let class_name = function Coding_dna -> "coding_dna" | Coding_rna -> "coding_rna" | Protein -> "protein"
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["artifact_class"; "sequence_length"; "unknown_features"; "completeness"] value in
    let field key = get ~path key fields in
    let artifact_class = match Json.string ~path (field "artifact_class") with
      | "coding_dna" -> Coding_dna | "coding_rna" -> Coding_rna | "protein" -> Protein
      | _ -> Diagnostic.fail ~path "component_record" "Unsupported reference artifact class." in
    let sequence_length = Json.integer ~path (field "sequence_length") in
    require ~path (Z.sign sequence_length > 0) "Reference length must be positive.";
    require ~path (field "completeness" = str "CDS-reference-only") "Only CDS reference scope is supported.";
    { artifact_class; sequence_length; unknown_features = names ~path (field "unknown_features") }
  let to_json value = obj ["schema_version", str schema_version; "artifact_class", str (class_name value.artifact_class);
    "sequence_length", Json.Int value.sequence_length; "unknown_features", strings value.unknown_features; "completeness", str "CDS-reference-only"]
  let make ~artifact_class ~sequence_length ~unknown_features = of_json (to_json { artifact_class; sequence_length; unknown_features })
  let fingerprint value = Canonical.fingerprint (to_json value)
  let artifact_class value = value.artifact_class
  let sequence_length value = value.sequence_length
  let unknown_features value = value.unknown_features
  let completeness _ = "CDS-reference-only"
end

type classification = Synthetic_model | Sequence_reference | Modeled_component
type t = { id : string; version : string; classification : classification; implementation_role : string;
  supported_targets : string list; ports : P.t list; supported_domain : O.t; identities : Pinned_identity.t list;
  assumptions : string list; guarantees : string list; evidence : Pinned_identity.t list; parameters : Parameter.t list;
  dependencies : Dependency.t list; capabilities : Capability.t list; resources : Resource.t list;
  reference_metadata : Sequence_reference.t option; synthetic_model : Synthetic_operator.t option }
let schema_version = "biocompiler.component_record.v0.2"
let classification_name = function Synthetic_model -> "synthetic_model" | Sequence_reference -> "sequence_reference" | Modeled_component -> "modeled_component"
let to_json value = obj ["schema_version", str schema_version; "id", str value.id; "version", str value.version;
  "classification", str (classification_name value.classification); "implementation_role", str value.implementation_role;
  "supported_targets", strings value.supported_targets; "ports", encoded_array P.to_json value.ports; "supported_domain", O.to_json value.supported_domain;
  "identities", encoded_array Pinned_identity.to_json value.identities; "assumptions", strings value.assumptions; "guarantees", strings value.guarantees;
  "evidence", encoded_array Pinned_identity.to_json value.evidence; "parameters", encoded_array Parameter.to_json value.parameters;
  "dependencies", encoded_array Dependency.to_json value.dependencies; "capabilities", encoded_array Capability.to_json value.capabilities;
  "resources", encoded_array Resource.to_json value.resources; "reference_metadata", option_json Sequence_reference.to_json value.reference_metadata;
  "synthetic_model", option_json Synthetic_operator.to_json value.synthetic_model]
let of_json ?(path = "") value =
  let fields = record ~path schema_version ["id"; "version"; "classification"; "implementation_role"; "supported_targets"; "ports"; "supported_domain";
    "identities"; "assumptions"; "guarantees"; "evidence"; "parameters"; "dependencies"; "capabilities"; "resources"; "reference_metadata"; "synthetic_model"] value in
  let field key = get ~path key fields in let name key = Json.name ~path (field key) in
  let inventory key decode id = Json.array ~path:(path ^ "/" ^ key) (field key)
    |> List.map (fun value -> decode value) |> sorted_by_id ~path:(path ^ "/" ^ key) id in
  let supported_targets = names ~path (field "supported_targets") in
  require ~path (supported_targets <> []) "Component requires a supported target.";
  let classification = match Json.string ~path (field "classification") with
    | "synthetic_model" -> Synthetic_model | "sequence_reference" -> Sequence_reference | "modeled_component" -> Modeled_component
    | _ -> Diagnostic.fail ~path "component_record" "Unsupported component classification." in
  let ports = inventory "ports" (fun value -> P.of_json value) P.id
  and identities = inventory "identities" (fun value -> Pinned_identity.of_json value) Pinned_identity.id
  and evidence = inventory "evidence" (fun value -> Pinned_identity.of_json value) Pinned_identity.id
  and parameters = inventory "parameters" (fun value -> Parameter.of_json value) Parameter.id
  and dependencies = inventory "dependencies" (fun value -> Dependency.of_json value) Dependency.id
  and capabilities = inventory "capabilities" (fun value -> Capability.of_json value) Capability.id
  and resources = inventory "resources" (fun value -> Resource.of_json value) Resource.id in
  let supported_domain = O.of_json ~path:(path ^ "/supported_domain") (field "supported_domain")
  and reference_metadata = optional (fun value -> Sequence_reference.of_json ~path:(path ^ "/reference_metadata") value) (field "reference_metadata")
  and synthetic_model = optional (fun value -> Synthetic_operator.of_json ~path:(path ^ "/synthetic_model") value) (field "synthetic_model") in
  let implementation_role = name "implementation_role" in
  Option.iter (fun model ->
      require ~path (classification = Synthetic_model) "Executable models require synthetic classification.";
      require ~path (implementation_role = C.synthetic_operation_name (Synthetic_operator.operation model)) "Implementation role disagrees with executable operation.";
      Synthetic_operator.validate_ports model ~ports ~supported_domain) synthetic_model;
  let has kind = List.exists (fun identity -> Pinned_identity.kind identity = kind) identities in
  (match classification with
   | Sequence_reference ->
       require ~path (has Pinned_identity.Reference && reference_metadata <> None) "Sequence reference requires its pin and coding metadata.";
       require ~path (not (has Pinned_identity.Model) && ports = [] && capabilities = [] && resources = [] && dependencies = [])
         "Sequence reference cannot declare dynamic interfaces or obligations."
   | Synthetic_model | Modeled_component ->
       require ~path (has Pinned_identity.Model && reference_metadata = None) "Modeled component needs a model pin and no reference metadata.");
  let result = { id = name "id"; version = name "version"; classification; implementation_role; supported_targets; ports; supported_domain; identities;
    assumptions = names ~path (field "assumptions"); guarantees = names ~path (field "guarantees"); evidence; parameters; dependencies; capabilities; resources;
    reference_metadata; synthetic_model } in
  bounded ~path (to_json result); result
let make ~id ~version ~classification ~implementation_role ~supported_targets ~ports ~supported_domain ~identities ~assumptions ~guarantees
    ~evidence ~parameters ~dependencies ~capabilities ~resources ~reference_metadata ~synthetic_model =
  of_json (to_json { id; version; classification; implementation_role; supported_targets; ports; supported_domain; identities; assumptions; guarantees;
    evidence; parameters; dependencies; capabilities; resources; reference_metadata; synthetic_model })
let fingerprint value = Canonical.fingerprint (to_json value)
let id value = value.id
let version value = value.version
let classification value = value.classification
let implementation_role value = value.implementation_role
let supported_targets value = value.supported_targets
let ports value = value.ports
let port value identity = List.find_opt (fun port -> P.id port = identity) value.ports
let supported_domain value = value.supported_domain
let identities value = value.identities
let assumptions value = value.assumptions
let guarantees value = value.guarantees
let evidence value = value.evidence
let parameters value = value.parameters
let dependencies value = value.dependencies
let capabilities value = value.capabilities
let resources value = value.resources
let reference_metadata value = value.reference_metadata
let synthetic_model value = value.synthetic_model
