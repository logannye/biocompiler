open Bioc_wire
module Target = Build_request.Target
module Evidence = Build_request.Target_evidence
type use = Software_test | Human_therapeutic
type boundary = Planning | Selection | Verification | Export
type decision = Software_only | Not_admitted
let policy_version = "biocompiler.human_admission_policy.v0.1"
let resource_profile = "biocompiler.admission.resources.v1"
let use_name = function Software_test -> "software_test" | Human_therapeutic -> "human_therapeutic"
let boundary_name = function Planning -> "planning" | Selection -> "selection" | Verification -> "verification" | Export -> "export"
let decision_name = function Software_only -> "software_only" | Not_admitted -> "not_admitted"
let require ?path condition message = Diagnostic.require ?path condition "admission_record" message
let limit ?path condition = Diagnostic.require ?path condition "admission_limit" "Admission record exceeds its native resource boundary."
let str value = Json.String value
let use_of_json ?(path = "") value = match Json.string ~path value with
  | "software_test" -> Software_test | "human_therapeutic" -> Human_therapeutic
  | _ -> Diagnostic.fail ~path "admission_record" "Invalid intended use."
let boundary_of_json ?(path = "") value = match Json.string ~path value with
  | "planning" -> Planning | "selection" -> Selection | "verification" -> Verification | "export" -> Export
  | _ -> Diagnostic.fail ~path "admission_record" "Invalid admission boundary."
let decision_of_json ?(path = "") value = match Json.string ~path value with
  | "software_only" -> Software_only | "not_admitted" -> Not_admitted
  | _ -> Diagnostic.fail ~path "admission_record" "Unsupported admission decision."
let preflight ?(path = "") value =
  try Measurement_contract.preflight ~path value with
  | Diagnostic.Error diagnostic when diagnostic.code = "human_record_limit" -> limit ~path false
  | Diagnostic.Error diagnostic when diagnostic.code = "human_record_cycle" ->
      Diagnostic.fail ~path "admission_cycle" "Cyclic admission record."
let bounded values =
  let rec loop count = function [] -> values | _ :: rest ->
    limit (count < Limits.max_json_nodes); loop (count + 1) rest in loop 0 values
let weight value =
  preflight value;
  let pending = ref [value] and nodes = ref 0 in
  while !pending <> [] do
    let value = List.hd !pending in pending := List.tl !pending; incr nodes;
    match value with
    | Json.Array values -> List.iter (fun value -> pending := value :: !pending) values
    | Json.Object fields -> List.iter (fun (_, value) -> pending := value :: !pending) fields
    | _ -> ()
  done;
  String.length (Canonical.encode value), !nodes
type budget = { mutable bytes : int; mutable nodes : int }
let reserve budget value =
  let bytes, nodes = weight value in
  limit (bytes <= Limits.max_request_bytes - budget.bytes && nodes <= Limits.max_json_nodes - budget.nodes);
  budget.bytes <- budget.bytes + bytes; budget.nodes <- budget.nodes + nodes; value
let array budget encode values =
  let first = ref true in
  Json.Array (List.map (fun value ->
      if !first then first := false else begin limit (budget.bytes < Limits.max_request_bytes); budget.bytes <- budget.bytes + 1 end;
      reserve budget (encode value)) (bounded values))
let get path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let record ~path schema keys value =
  preflight ~path value;
  let fields = Json.object_fields ~path value in Json.exact_fields ~path ("schema_version" :: keys) fields;
  Diagnostic.require ~path (Json.string (get path "schema_version" fields) = schema) "unsupported_schema" "Unsupported admission schema.";
  fields
let hash ~path value =
  let value = Json.string ~path value in
  require ~path (String.length value = 64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value)
    "Expected SHA-256 identity."; value
let names ~path value =
  let values = Json.array ~path value |> List.map (Json.name ~path) in
  let sorted = List.sort String.compare values in
  require ~path (List.length sorted = List.length (List.sort_uniq String.compare sorted)) "Admission names must be unique.";
  sorted
(* Python dataclass equality compares nested numeric values rather than their
   JSON spellings. Equal repeated components retain the last declared record. *)
let record_equal left right =
  let numeric = function Json.Bool value -> Some (Json.int (if value then 1 else 0))
    | (Json.Int _ | Json.Float _) as value -> Some value | _ -> None in
  let pending = ref [left, right] and equal = ref true in
  while !equal && !pending <> [] do
    let left, right = List.hd !pending in pending := List.tl !pending;
    match numeric left, numeric right with
    | Some left, Some right -> equal := Json.number_compare left right = 0
    | _ -> (match left, right with
        | Json.Null, Json.Null -> ()
        | Json.String left, Json.String right -> equal := left = right
        | Json.Array left, Json.Array right ->
            if List.length left <> List.length right then equal := false
            else List.iter2 (fun left right -> pending := (left, right) :: !pending) left right
        | Json.Object left, Json.Object right ->
            if List.length left <> List.length right then equal := false else begin
              let order = List.sort (fun (a, _) (b, _) -> String.compare a b) in
              List.iter2 (fun (a, left) (b, right) -> if a <> b then equal := false else pending := (left, right) :: !pending)
                (order left) (order right)
            end
        | _ -> equal := false)
  done; !equal
module Request = struct
  type t = { json : Json.t; fingerprint : string; size : int; target : Target.t;
             intended_use : use; boundary : boundary; components : Component.t list }
  let schema_version = "biocompiler.admission_request.v0.1"
  let encode ~target ~intended_use ~boundary ~components =
    let budget = { bytes = 0; nodes = 0 } in
    let skeleton = ["schema_version", str schema_version; "target", Target.to_json target;
      "intended_use", str (use_name intended_use); "boundary", str (boundary_name boundary); "components", Json.Array []] in
    ignore (reserve budget (Json.Object skeleton));
    Json.Object (("components", array budget Component.to_json components) :: List.remove_assoc "components" skeleton)
  let of_json ?(path = "") value =
    let fields = record ~path schema_version ["target"; "intended_use"; "boundary"; "components"] value in
    let field key = get path key fields in
    let target = Target.of_json ~path:(path ^ "/target") (field "target") in
    let components = Json.array ~path:(path ^ "/components") (field "components")
      |> List.mapi (fun i value -> Component.of_json ~path:(path ^ "/components/" ^ string_of_int i) value) in
    let intended_use = use_of_json ~path:(path ^ "/intended_use") (field "intended_use") in
    let boundary = boundary_of_json ~path:(path ^ "/boundary") (field "boundary") in
    let key item = Component.id item, Component.version item in
    let sorted = List.stable_sort (fun a b -> Stdlib.compare (key a) (key b)) components in
    let components = List.fold_left (fun unique item -> match unique with
        | previous :: rest when key previous = key item ->
            require ~path (record_equal (Component.to_json previous) (Component.to_json item)) "Ambiguous admission component identities.";
            item :: rest
        | _ -> item :: unique) [] sorted |> List.rev in
    let json = encode ~target ~intended_use ~boundary ~components in preflight ~path json;
    let canonical = Canonical.encode json in
    { json; fingerprint = Canonical.sha256 canonical; size = String.length canonical; target; intended_use; boundary; components }
  let make ~target ~intended_use ~boundary ~components = of_json (encode ~target ~intended_use ~boundary ~components)
  let to_json value = value.json
  let fingerprint value = value.fingerprint
  let canonical_size value = value.size
  let target value = value.target
  let intended_use value = value.intended_use
  let boundary value = value.boundary
  let components value = value.components
end
module Assessment = struct
  type t = { json : Json.t; fingerprint : string; size : int; request_fingerprint : string; target_fingerprint : string;
             intended_use : use; boundary : boundary; decision : decision; diagnostics : string list;
             component_fingerprints : string list; evidence : Evidence.t list }
  let schema_version = "biocompiler.admission_assessment.v0.1"
  let fixed = ["policy", str policy_version; "human_therapeutic_admission", str "not_admitted";
    "claim_scope", str "use_eligibility_only_no_biological_validation"; "evidence_status", str "declared_not_independently_validated"]
  let encode ~request_fingerprint ~target_fingerprint ~intended_use ~boundary ~decision ~diagnostics ~component_fingerprints ~evidence =
    let budget = { bytes = 0; nodes = 0 } in
    let skeleton = fixed @ ["schema_version", str schema_version; "request_fingerprint", str request_fingerprint;
      "target_fingerprint", str target_fingerprint; "intended_use", str (use_name intended_use); "boundary", str (boundary_name boundary);
      "decision", str (decision_name decision); "diagnostics", Json.Array []; "component_fingerprints", Json.Array []; "evidence", Json.Array []] in
    ignore (reserve budget (Json.Object skeleton));
    let diagnostics = array budget str diagnostics in
    let component_fingerprints = array budget str component_fingerprints in
    let evidence = array budget Evidence.to_json evidence in
    Json.Object (["diagnostics", diagnostics; "component_fingerprints", component_fingerprints; "evidence", evidence] @
      List.filter (fun (key, _) -> not (List.mem key ["diagnostics"; "component_fingerprints"; "evidence"])) skeleton)
  let of_json ?(path = "") value =
    let fields = record ~path schema_version (["request_fingerprint"; "target_fingerprint"; "intended_use"; "boundary";
      "decision"; "diagnostics"; "component_fingerprints"; "evidence"] @ List.map fst fixed) value in
    let field key = get path key fields in
    List.iter (fun (key, expected) -> require ~path:(path ^ "/" ^ key) (Json.equal (field key) expected) ("Invalid " ^ key ^ ".")) fixed;
    let evidence = Json.array ~path:(path ^ "/evidence") (field "evidence")
      |> List.mapi (fun i value -> Evidence.of_json ~path:(path ^ "/evidence/" ^ string_of_int i) value) in
    let request_fingerprint = hash ~path:(path ^ "/request_fingerprint") (field "request_fingerprint") in
    let target_fingerprint = hash ~path:(path ^ "/target_fingerprint") (field "target_fingerprint") in
    let intended_use = use_of_json ~path:(path ^ "/intended_use") (field "intended_use") in
    let boundary = boundary_of_json ~path:(path ^ "/boundary") (field "boundary") in
    let decision = decision_of_json ~path:(path ^ "/decision") (field "decision") in
    require ~path (decision <> Software_only || intended_use = Software_test) "Software use cannot authorize a human therapeutic build.";
    let diagnostics = names ~path:(path ^ "/diagnostics") (field "diagnostics") in
    let component_fingerprints = names ~path:(path ^ "/component_fingerprints") (field "component_fingerprints") in
    require ~path (diagnostics <> []) "Admission decisions need explicit scope/reasons.";
    List.iter (fun value -> ignore (hash ~path:(path ^ "/component_fingerprints") (str value))) component_fingerprints;
    let evidence = List.sort (fun a b -> String.compare (Evidence.id a) (Evidence.id b)) evidence in
    let seen = Hashtbl.create 16 in
    List.iter (fun item -> let id = Evidence.id item in require ~path (not (Hashtbl.mem seen id)) "Duplicate evidence IDs."; Hashtbl.add seen id ()) evidence;
    let json = encode ~request_fingerprint ~target_fingerprint ~intended_use ~boundary ~decision ~diagnostics ~component_fingerprints ~evidence in
    preflight ~path json; let canonical = Canonical.encode json in
    { json; fingerprint = Canonical.sha256 canonical; size = String.length canonical; request_fingerprint; target_fingerprint;
      intended_use; boundary; decision; diagnostics; component_fingerprints; evidence }
  let make ~request_fingerprint ~target_fingerprint ~intended_use ~boundary ~decision ~diagnostics ~component_fingerprints ~evidence =
    of_json (encode ~request_fingerprint ~target_fingerprint ~intended_use ~boundary ~decision ~diagnostics ~component_fingerprints ~evidence)
  let to_json value = value.json
  let fingerprint value = value.fingerprint
  let canonical_size value = value.size
  let request_fingerprint value = value.request_fingerprint
  let target_fingerprint value = value.target_fingerprint
  let intended_use value = value.intended_use
  let boundary value = value.boundary
  let decision value = value.decision
  let diagnostics value = value.diagnostics
  let component_fingerprints value = value.component_fingerprints
  let evidence value = value.evidence
  let is_current value request = value.request_fingerprint = Request.fingerprint request
end
