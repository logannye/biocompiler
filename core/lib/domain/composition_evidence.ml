open Bioc_wire
module N = Runtime_number
let checker_version = "biocompiler.component_linker.v0.3"
let claim_scope = "Structural component compatibility under the locked records and declared target, provider, lifecycle, model and resource assumptions only. This is not biological efficacy, sequence emission, or empirical validation."
let resource_profile = "biocompiler.composition_evidence.resources.v1"
let resource_limits = Json.Object ["profile", Json.String resource_profile;
  "max_bytes", Json.int Limits.max_response_bytes; "max_text_input_bytes", Json.int Limits.max_request_bytes;
  "max_nodes", Json.int Limits.max_json_nodes; "node_accounting", Json.String "values_and_object_keys";
  "max_depth", Json.int Limits.max_depth; "max_string_bytes", Json.int Limits.max_string_bytes;
  "max_number_chars", Json.int Limits.max_number_chars; "encoding", Json.String "canonical_utf8"]
type status = Realization_evidence.outcome = Pass | Fail | Unknown | Unsupported
let status_name = function Pass -> "pass" | Fail -> "fail" | Unknown -> "unknown" | Unsupported -> "unsupported"
let require ?path condition message = Diagnostic.require ?path condition "composition_evidence" message
let limit ?path condition = Diagnostic.require ?path condition "composition_evidence_limit"
    "Composition evidence exceeds its native resource boundary."
let str value = Json.String value
let obj value = Json.Object value
type size = { bytes : int; nodes : int }
type visit = Enter of Json.t * int | Leave of Json.t
let measure ?(path = "") value =
  let bytes = ref 0 and nodes = ref 0 and queued = ref 1 in
  let add amount = limit ~path (amount >= 0 && amount <= Limits.max_response_bytes - !bytes); bytes := !bytes + amount in
  let quoted text =
    limit ~path (String.length text <= Limits.max_string_bytes);
    add (String.length text + 2); Json.validate_utf8 text;
    String.iter (function '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> add 1
      | value when Char.code value < 32 -> add 5 | _ -> ()) text in
  let length maximum values =
    let rec visit count = function [] -> count | _ :: rest ->
      limit ~path (count < maximum); visit (count + 1) rest in visit 0 values in
  let pending = ref [Enter (value, 0)] and active = ref [] in
  while !pending <> [] do
    let item = List.hd !pending in pending := List.tl !pending;
    match item with
    | Leave value -> active := List.filter (fun item -> item != value) !active
    | Enter (value, depth) ->
        decr queued; incr nodes;
        limit ~path (!nodes <= Limits.max_json_nodes && depth <= Limits.max_depth);
        let enter children count =
          Diagnostic.require ~path (not (List.exists (fun item -> item == value) !active))
            "composition_evidence_cycle" "Cyclic composition evidence JSON.";
          active := value :: !active; pending := Leave value :: !pending;
          List.iter (fun child -> pending := Enter (child, depth + 1) :: !pending) children;
          queued := !queued + count in
        (match value with
        | Json.Null -> add 4 | Json.Bool value -> add (if value then 4 else 5)
        | Json.Int value ->
            limit ~path (Z.numbits value <= 4 * Limits.max_number_chars);
            let text = Z.to_string value in limit ~path (String.length text <= Limits.max_number_chars); add (String.length text)
        | Json.Float value ->
            Diagnostic.require ~path (Float.is_finite value) "nonfinite_number" "Nonfinite composition evidence number.";
            add (String.length (Canonical.float_string value))
        | Json.String value -> quoted value
        | Json.Array values ->
            let count = length (Limits.max_json_nodes - !nodes - !queued) values in
            add (2 + max 0 (count - 1)); enter values count
        | Json.Object fields ->
            let count = length ((Limits.max_json_nodes - !nodes - !queued) / 2) fields in
            nodes := !nodes + count;
            add (2 + count + max 0 (count - 1));
            let seen = Hashtbl.create 16 in
            List.iter (fun (key, _) -> quoted key;
              Diagnostic.require ~path (not (Hashtbl.mem seen key)) "duplicate_key" "Duplicate composition evidence field.";
              Hashtbl.add seen key ()) fields;
            enter (List.rev_map snd fields) count)
  done;
  {bytes = !bytes; nodes = !nodes}
type packed = { json : Json.t; size : size }
let pack ?path json = {json; size = measure ?path json}
let record ~path keys raw =
  ignore (measure ~path raw);
  let fields = Json.object_fields ~path raw in Json.exact_fields ~path keys fields; fields
let get path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let name path key fields = Json.name ~path:(path ^ "/" ^ key) (get path key fields)
let optional decode = function Json.Null -> None | value -> Some (decode value)
let option_json encode = function None -> Json.Null | Some value -> encode value
let names ~path raw =
  let seen = Hashtbl.create 16 in
  Json.array ~path raw |> List.mapi (fun index value ->
    let value = Json.name ~path:(path ^ "/" ^ string_of_int index) value in
    require ~path (not (Hashtbl.mem seen value)) "Requirement identifiers must be unique.";
    Hashtbl.add seen value (); value)
let status ~path message = function
  | Json.String "pass" -> Pass | Json.String "fail" -> Fail
  | Json.String "unknown" -> Unknown | Json.String "unsupported" -> Unsupported
  | _ -> Diagnostic.fail ~path "composition_evidence" message
let quantity ~path label = function
  | Json.Null -> None
  | Json.Int value when Z.sign value >= 0 && Float.is_finite (Z.to_float value) -> Some (N.Integer value)
  | Json.Float value when Float.is_finite value && value >= 0. -> Some (N.Real value)
  | _ -> Diagnostic.fail ~path "composition_evidence"
      (label ^ " must be a finite nonnegative quantity or an allowed unknown.")
let raw_number = function N.Integer value -> Json.Int value | N.Real value -> Json.Float value
let quantity_json label value =
  let raw = option_json raw_number value in ignore (quantity ~path:"" label raw); raw

(* Each constructor reserves all occurrences before allocating its containing
   array. Cyclic typed list spines exhaust this same cumulative reservation. *)
type budget = { mutable bytes : int; mutable nodes : int }
let reserve (budget : budget) (size : size) =
  limit (size.bytes <= Limits.max_response_bytes - budget.bytes && size.nodes <= Limits.max_json_nodes - budget.nodes);
  budget.bytes <- budget.bytes + size.bytes; budget.nodes <- budget.nodes + size.nodes
let leaf raw budget = reserve budget (measure raw); raw
let packed value budget = reserve budget value.size; value.json
let array encode values budget =
  reserve budget {bytes = 2; nodes = 1};
  let rec loop first result = function
    | [] -> Json.Array (List.rev result)
    | value :: rest ->
        if not first then reserve budget {bytes = 1; nodes = 0};
        let raw = encode value budget in loop false (raw :: result) rest in
  loop true [] values
let document fields =
  let budget : budget = {bytes = 2; nodes = 1} in
  let fields = List.mapi (fun index (key, encode) ->
    let size = measure (str key) in reserve budget {size with bytes = size.bytes + 1 + if index = 0 then 0 else 1};
    key, encode budget) fields in
  obj fields

module Link_diagnostic = struct
  type status = Fail | Unknown | Unsupported
  type t = { packed : packed; status : status; code : string; message : string;
    instance : string option; requirements : string list }
  let name_status (value : status) = match value with
    | Fail -> "fail" | Unknown -> "unknown" | Unsupported -> "unsupported"
  let of_json ?(path = "") raw =
    let fields = record ~path ["status"; "code"; "message"; "instance_id"; "requirement_ids"] raw in
    let status : status = match get path "status" fields with
      | Json.String "fail" -> Fail | Json.String "unknown" -> Unknown | Json.String "unsupported" -> Unsupported
      | _ -> Diagnostic.fail ~path "composition_evidence" "Invalid link diagnostic status." in
    let code = name path "code" fields and message = name path "message" fields in
    let instance = optional (Json.name ~path:(path ^ "/instance_id")) (get path "instance_id" fields) in
    let requirements = names ~path:(path ^ "/requirement_ids") (get path "requirement_ids" fields) in
    {packed = pack ~path raw; status; code; message; instance; requirements}
  let make ~status ~code ~message ?instance_id ?(requirement_ids = []) () =
    document ["status", leaf (str (name_status status)); "code", leaf (str code);
      "message", leaf (str message); "instance_id", leaf (option_json str instance_id);
      "requirement_ids", array (fun value -> leaf (str value)) requirement_ids] |> of_json
  let to_json value = value.packed.json
  let fingerprint value = Canonical.fingerprint value.packed.json
  let canonical_size value = value.packed.size.bytes
  let status value = value.status
  let status_name value = name_status value.status
  let code value = value.code
  let message value = value.message
  let instance_id value = value.instance
  let requirement_ids value = value.requirements
end

module Resolved_dependency = struct
  type provider_kind = Encoded_here | Co_payload | Host | External | Unresolved
  type t = { packed : packed; instance : string; requirement : string; provider : string option;
    kind : provider_kind; status : status }
  let name_kind = function Encoded_here -> "encoded_here" | Co_payload -> "co_payload"
    | Host -> "host" | External -> "external" | Unresolved -> "unresolved"
  let of_json ?(path = "") raw =
    let fields = record ~path ["instance_id"; "requirement_id"; "provider_id"; "provider_kind"; "status"] raw in
    let instance = name path "instance_id" fields and requirement = name path "requirement_id" fields in
    let provider = optional (Json.name ~path:(path ^ "/provider_id")) (get path "provider_id" fields) in
    let kind = match get path "provider_kind" fields with
      | Json.String "encoded_here" -> Encoded_here | Json.String "co_payload" -> Co_payload
      | Json.String "host" -> Host | Json.String "external" -> External | Json.String "unresolved" -> Unresolved
      | _ -> Diagnostic.fail ~path "composition_evidence" "Invalid provider category." in
    let status = status ~path "Invalid dependency status." (get path "status" fields) in
    {packed = pack ~path raw; instance; requirement; provider; kind; status}
  let make ~instance_id ~requirement_id ~provider_id ~provider_kind ~status =
    document ["instance_id", leaf (str instance_id); "requirement_id", leaf (str requirement_id);
      "provider_id", leaf (option_json str provider_id); "provider_kind", leaf (str (name_kind provider_kind));
      "status", leaf (str (status_name status))] |> of_json
  let to_json value = value.packed.json
  let fingerprint value = Canonical.fingerprint value.packed.json
  let canonical_size value = value.packed.size.bytes
  let instance_id value = value.instance
  let requirement_id value = value.requirement
  let provider_id value = value.provider
  let provider_kind value = value.kind
  let provider_kind_name value = name_kind value.kind
  let status value = value.status
end

module Resource_usage = struct
  type t = { packed : packed; pool : string; peak : N.t option; capacity : N.t option;
    unit : string; status : status }
  let of_json ?(path = "") raw =
    let fields = record ~path ["pool_id"; "peak_reservation"; "capacity"; "unit"; "status"] raw in
    let pool = name path "pool_id" fields and unit = name path "unit" fields in
    let peak = quantity ~path:(path ^ "/peak_reservation") "Peak reservation" (get path "peak_reservation" fields) in
    let capacity = quantity ~path:(path ^ "/capacity") "Capacity" (get path "capacity" fields) in
    let status = status ~path "Invalid resource status." (get path "status" fields) in
    {packed = pack ~path raw; pool; peak; capacity; unit; status}
  let make ~pool_id ~peak_reservation ~capacity ~unit ~status =
    let peak = quantity_json "Peak reservation" peak_reservation and capacity = quantity_json "Capacity" capacity in
    document ["pool_id", leaf (str pool_id); "peak_reservation", leaf peak;
      "capacity", leaf capacity; "unit", leaf (str unit); "status", leaf (str (status_name status))] |> of_json
  let to_json value = value.packed.json
  let fingerprint value = Canonical.fingerprint value.packed.json
  let canonical_size value = value.packed.size.bytes
  let pool_id value = value.pool
  let peak_reservation value = value.peak
  let capacity value = value.capacity
  let unit value = value.unit
  let status value = value.status
end

(* Freshness follows frozen Python structural equality, not canonical numeric
   spelling. Legal dependency leaves are currently strings; this explicit
   numeric rule prevents identity semantics being accidentally generalized to
   byte equality if additional checked numeric metadata is introduced. *)
let python_equal left right =
  let pending = ref [left, right] and same = ref true in
  let numeric = function Json.Bool value -> Some (Json.int (if value then 1 else 0))
    | (Json.Int _ | Json.Float _) as value -> Some value | _ -> None in
  while !same && !pending <> [] do
    let left, right = List.hd !pending in pending := List.tl !pending;
    match numeric left, numeric right, left, right with
    | Some left, Some right, _, _ -> same := Json.number_compare left right = 0
    | _, _, Json.Array left, Json.Array right ->
        if List.length left <> List.length right then same := false
        else pending := List.rev_append (List.combine left right) !pending
    | _, _, Json.Object left, Json.Object right ->
        if List.length left <> List.length right then same := false
        else List.iter (fun (key, value) -> match List.assoc_opt key right with None -> same := false
          | Some other -> pending := (value, other) :: !pending) left
    | _, _, Json.Null, Json.Null -> ()
    | _, _, Json.String left, Json.String right -> same := left = right
    | _ -> same := false
  done; !same

module Dependencies = struct
  type t = { packed : packed; request : string; registry : string; lock : string;
    target : string; identities : Pinned_identity.t list }
  let keys = ["request"; "registry"; "registry_lock"; "target"; "checker"; "identities"; "admission_policy"]
  let of_json ?(path = "") raw =
    let fields = record ~path keys raw in
    let hash key = match get path key fields with
      | Json.String value when String.length value = 64
          && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value -> value
      | _ -> Diagnostic.fail ~path "composition_evidence" "Invalid composition dependency hash." in
    let request = hash "request" and registry = hash "registry" and lock = hash "registry_lock" and target = hash "target" in
    require ~path (get path "checker" fields = str checker_version
      && get path "admission_policy" fields = str Admission.policy_version) "Unsupported checker version.";
    let identities = Json.array ~path:(path ^ "/identities") (get path "identities" fields)
      |> List.mapi (fun index value -> Pinned_identity.of_json ~path:(path ^ "/identities/" ^ string_of_int index) value) in
    let seen = Hashtbl.create 16 in
    List.iter (fun identity ->
      let key = Pinned_identity.kind identity, Pinned_identity.id identity, Pinned_identity.version identity in
      require ~path (not (Hashtbl.mem seen key)) "Duplicate dependency identities."; Hashtbl.add seen key ()) identities;
    {packed = pack ~path raw; request; registry; lock; target; identities}
  let make ~request ~registry ~registry_lock ~target ~identities =
    document ["request", leaf (str request); "registry", leaf (str registry); "registry_lock", leaf (str registry_lock);
      "target", leaf (str target); "checker", leaf (str checker_version); "admission_policy", leaf (str Admission.policy_version);
      "identities", array (fun value -> leaf (Pinned_identity.to_json value)) identities] |> of_json
  let to_json value = value.packed.json
  let fingerprint value = Canonical.fingerprint value.packed.json
  let canonical_size value = value.packed.size.bytes
  let request value = value.request
  let registry value = value.registry
  let registry_lock value = value.lock
  let target value = value.target
  let identities value = value.identities
  let changed previous current =
    let before = Json.object_fields previous.packed.json and after = Json.object_fields current.packed.json in
    List.sort String.compare keys |> List.filter (fun key ->
      not (python_equal (Json.field key before) (Json.field key after)))
end
let dependencies ~request ~registry =
  let lock = Composition.registry_lock request in
  Dependencies.make ~request:(Composition.fingerprint request) ~registry:(Component_registry.fingerprint registry)
    ~registry_lock:(Component_registry.Lock.fingerprint lock) ~target:(Build_request.Target.fingerprint (Composition.target request))
    ~identities:(Component_registry.Lock.identities lock)
let current_dependencies = dependencies

module Result = struct
  type t = { packed : packed; outcome : status; dependencies : Dependencies.t; checked : string list;
    diagnostics : Link_diagnostic.t list; resolved : Resolved_dependency.t list; usage : Resource_usage.t list }
  let schema_version = "biocompiler.component_link_result.v0.3"
  let of_json ?(path = "") raw =
    let fields = record ~path ["schema_version"; "outcome"; "dependencies"; "checked_requirement_ids";
      "diagnostics"; "resolved_dependencies"; "resource_usage"; "claim_scope"] raw in
    require ~path (get path "schema_version" fields = str schema_version) "Unsupported link result schema.";
    let outcome = status ~path "Invalid link outcome." (get path "outcome" fields) in
    (* Historical import decodes nested inventories before the result's own
       dependency/checked-ID predicates. Preserve that observable precedence. *)
    let array key = Json.array ~path:(path ^ "/" ^ key) (get path key fields) in
    let diagnostics_raw = array "diagnostics" and resolved_raw = array "resolved_dependencies" and usage_raw = array "resource_usage" in
    let diagnostics = List.mapi (fun index value -> Link_diagnostic.of_json ~path:(path ^ "/diagnostics/" ^ string_of_int index) value) diagnostics_raw in
    let resolved = List.mapi (fun index value -> Resolved_dependency.of_json ~path:(path ^ "/resolved_dependencies/" ^ string_of_int index) value) resolved_raw in
    let usage = List.mapi (fun index value -> Resource_usage.of_json ~path:(path ^ "/resource_usage/" ^ string_of_int index) value) usage_raw in
    let dependencies = Dependencies.of_json ~path:(path ^ "/dependencies") (get path "dependencies" fields) in
    let checked = names ~path:(path ^ "/checked_requirement_ids") (get path "checked_requirement_ids" fields) in
    require ~path (get path "claim_scope" fields = str claim_scope) "Invalid composition claim scope.";
    require ~path (outcome <> Pass || diagnostics = []) "Passing compositions cannot contain unresolved diagnostics.";
    require ~path (outcome <> Pass || List.for_all (fun item -> Resource_usage.status item = Pass) usage)
      "Passing compositions cannot contain unresolved resource accounting.";
    {packed = pack ~path raw; outcome; dependencies; checked; diagnostics; resolved; usage}
  let make ~outcome ~dependencies ~checked_requirement_ids ?(diagnostics = []) ?(resolved_dependencies = [])
      ?(resource_usage = []) ?(claim_scope = claim_scope) () =
    document ["schema_version", leaf (str schema_version); "outcome", leaf (str (status_name outcome));
      "dependencies", packed dependencies.Dependencies.packed;
      "checked_requirement_ids", array (fun value -> leaf (str value)) checked_requirement_ids;
      "diagnostics", array (fun value -> packed value.Link_diagnostic.packed) diagnostics;
      "resolved_dependencies", array (fun value -> packed value.Resolved_dependency.packed) resolved_dependencies;
      "resource_usage", array (fun value -> packed value.Resource_usage.packed) resource_usage;
      "claim_scope", leaf (str claim_scope)] |> of_json
  let of_json_text value = Json.parse value |> of_json
  let to_json value = value.packed.json
  let fingerprint value = Canonical.fingerprint value.packed.json
  let canonical_size value = value.packed.size.bytes
  let outcome value = value.outcome
  let dependencies value = value.dependencies
  let checked_requirement_ids value = value.checked
  let diagnostics value = value.diagnostics
  let resolved_dependencies value = value.resolved
  let resource_usage value = value.usage
  let passed value = value.outcome = Pass
  let freshness value ~request ~registry =
    let current = current_dependencies ~request ~registry in
    Realization_evidence.Freshness_report.make (Dependencies.changed value.dependencies current)
  let is_fresh value ~request ~registry = Realization_evidence.Freshness_report.fresh (freshness value ~request ~registry)
end
