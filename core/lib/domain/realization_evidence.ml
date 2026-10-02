open Bioc_wire
module N = Runtime_number
let resource_profile = "biocompiler.realization_evidence.resources.v1"
let resource_limits = Json.Object ["profile", Json.String resource_profile;
  "max_bytes", Json.int Limits.max_response_bytes; "max_nodes", Json.int Limits.max_json_nodes;
  "max_text_input_bytes", Json.int Limits.max_request_bytes;
  "max_depth", Json.int Limits.max_depth; "max_string_bytes", Json.int Limits.max_string_bytes;
  "max_number_chars", Json.int Limits.max_number_chars]
let claim_scope = "Only the listed contract requirements, supplied input history, operating domain, and finite evaluation horizon were checked; this is not whole-program or universal biological refinement."
type outcome = Pass | Fail | Unknown | Unsupported
type evidence_kind = Exact | Model_conditional | Empirical | Unresolved
type expected_state = Active | Inactive
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let require ?path condition message = Diagnostic.require ?path condition "realization_evidence" message
let limit ?path condition = Diagnostic.require ?path condition "realization_evidence_limit"
    "Realization evidence exceeds its native resource budget."
let measure ?path value =
  try Legacy_ascii.measure ?path value with
  | Diagnostic.Error error when error.code = "legacy_ascii_limit" ->
      Diagnostic.fail ?path "realization_evidence_limit" error.message
  | Diagnostic.Error error when error.code = "legacy_ascii_cycle" ->
      Diagnostic.fail ?path "realization_evidence_cycle" error.message
type packed = { json : Json.t; size : Legacy_ascii.size }
let pack ?path json = {json; size = measure ?path json}
let record ~path names value =
  ignore (measure ~path value);
  let fields = Json.object_fields ~path value in Json.exact_fields ~path names fields; fields
let get path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let name path key fields = Json.name ~path:(path ^ "/" ^ key) (get path key fields)
let optional decode = function Json.Null -> None | value -> Some (decode value)
let option_json encode = function None -> Json.Null | Some value -> encode value
let raw_number = function N.Integer value -> Json.Int value | N.Real value -> Json.Float value
let number ~path ~nonnegative ~message value =
  let numeric = match value with
    | Json.Int value when Float.is_finite (Z.to_float value) -> Some (N.Integer value)
    | Json.Float value when Float.is_finite value -> Some (N.Real value)
    | _ -> None in
  match numeric with
  | Some value when not nonnegative || N.compare value N.zero >= 0 -> value
  | _ -> Diagnostic.fail ~path "realization_evidence" message
let source_json (value : Behavior.source_location) = obj ["file", str value.file;
  "line", Json.Int value.line; "function", str value.function_name]
let source ~path value =
  let fields = record ~path ["file"; "line"; "function"] value in
  let line = Json.integer ~path:(path ^ "/line") (get path "line" fields) in
  Diagnostic.require ~path (Z.sign line > 0) "invalid_source" "Source line must be positive.";
  {Behavior.file = name path "file" fields; line; function_name = name path "function" fields}

(* Constructors count repeated children cumulatively before any collection is
   mapped into its containing JSON. Cyclic OCaml list spines exhaust the same
   finite node budget; raw recursive JSON is detected by the wire preflight. *)
type budget = { mutable nodes : int; mutable bytes : int }
let budget () = {nodes = 0; bytes = 0}
let reserve budget (size : Legacy_ascii.size) =
  limit (size.nodes <= Limits.max_json_nodes - budget.nodes && size.bytes <= Limits.max_response_bytes - budget.bytes);
  budget.nodes <- budget.nodes + size.nodes; budget.bytes <- budget.bytes + size.bytes
let reserve_json budget value = reserve budget (measure value)
let reserve_list budget size values =
  let rec loop = function [] -> () | value :: rest ->
    (* Each occurrence consumes a node even if it shares a record object. *)
    reserve budget (size value); loop rest in loop values
let names ~path value = Json.array ~path value |> List.mapi (fun index value ->
  Json.name ~path:(path ^ "/" ^ string_of_int index) value)
let unique ~path message values =
  let seen = Hashtbl.create 16 in
  List.iter (fun value -> require ~path (not (Hashtbl.mem seen value)) message; Hashtbl.add seen value ()) values;
  seen

module Dependency_snapshot = struct
  type t = packed
  let keys = ["behavior"; "behavior_artifact"; "contract"; "domain"; "target"; "mechanism";
    "observation_map"; "history"; "horizon"; "checker"; "model_runner"; "reference_evaluator"; "settings"]
  let hashes = ["behavior"; "behavior_artifact"; "contract"; "domain"; "target"; "mechanism"; "observation_map"; "history"]
  let of_json ?(path = "") value =
    let fields = record ~path keys value in
    List.iter (fun key ->
      let value = Json.string ~path:(path ^ "/" ^ key) (get path key fields) in
      require ~path (String.length value = 64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value)
        ("Dependency " ^ key ^ " must be a SHA-256 fingerprint.")) hashes;
    List.iter (fun key -> ignore (name path key fields)) ["checker"; "model_runner"; "reference_evaluator"];
    let settings = Json.object_fields ~path:(path ^ "/settings") (get path "settings" fields) in
    require ~path (settings <> []) "Checker settings must be recorded.";
    let horizon = record ~path:(path ^ "/horizon") ["until"; "effective"] (get path "horizon" fields) in
    List.iter (fun (key, value) -> if key <> "until" || value <> Json.Null then
      ignore (number ~path:(path ^ "/horizon/" ^ key) ~nonnegative:true ~message:"Invalid recorded evaluation horizon." value)) horizon;
    pack ~path value
  let make_values value = of_json value
  let to_json value = value.json
  let fingerprint value = Legacy_ascii.fingerprint value.json
  let canonical_size value = value.size.bytes
  let changed left right =
    let left = Json.object_fields left.json and right = Json.object_fields right.json in
    List.sort String.compare keys |> List.filter (fun key ->
      Legacy_ascii.encode (Json.field key left) <> Legacy_ascii.encode (Json.field key right))
end

module Freshness_report = struct
  type t = {packed : packed; changed : string list}
  let of_json ?(path = "") value =
    let fields = record ~path ["changed_dependencies"] value in
    let changed = names ~path:(path ^ "/changed_dependencies") (get path "changed_dependencies" fields) in
    {packed = pack ~path value; changed}
  let make changed =
    let budget = budget () in reserve_list budget (fun value -> measure (str value)) changed;
    of_json (obj ["changed_dependencies", arr (List.map str changed)])
  let to_json value = value.packed.json
  let changed_dependencies value = value.changed
  let fresh value = value.changed = []
  let status value = if fresh value then "fresh" else "stale"
end

module Check_diagnostic = struct
  type t = {packed : packed; code : string; message : string; requirement : string option;
    node : string option; source : Behavior.source_location option}
  let of_json ?(path = "") value =
    let fields = record ~path ["code"; "message"; "requirement_id"; "node_id"; "source"] value in
    let source = optional (source ~path:(path ^ "/source")) (get path "source" fields) in
    let code = name path "code" fields and message = name path "message" fields in
    let requirement = optional (Json.name ~path:(path ^ "/requirement_id")) (get path "requirement_id" fields) in
    let node = optional (Json.name ~path:(path ^ "/node_id")) (get path "node_id" fields) in
    {packed = pack ~path value; code; message; requirement; node; source}
  let to_json value = value.packed.json
  let canonical_size value = value.packed.size.bytes
  let make ~code ~message ?requirement_id ?node_id ?source () = of_json (obj ["code", str code;
    "message", str message; "requirement_id", option_json str requirement_id; "node_id", option_json str node_id;
    "source", option_json source_json source])
  let code value = value.code
  let message value = value.message
  let requirement_id value = value.requirement
  let node_id value = value.node
  let source value = value.source
end

module Counterexample = struct
  type t = {packed : packed; requirement : string; time : N.t; contact : string option;
    state : expected_state; range : Measurement_contract.Interval.t; actual : N.t option;
    rule : string; specification : string; source : Behavior.source_location option}
  let of_json ?(path = "") value =
    let fields = record ~path ["requirement_id"; "time"; "contact_id"; "expected"; "actual";
      "rule_id"; "specification_id"; "source"] value in
    let source = optional (source ~path:(path ^ "/source")) (get path "source" fields) in
    let requirement = name path "requirement_id" fields and rule = name path "rule_id" fields
    and specification = name path "specification_id" fields in
    let time = number ~path:(path ^ "/time") ~nonnegative:true ~message:"Invalid counterexample time." (get path "time" fields) in
    let contact = optional (Json.name ~path:(path ^ "/contact_id")) (get path "contact_id" fields) in
    let expected = record ~path:(path ^ "/expected") ["state"; "range"] (get path "expected" fields) in
    let state = match Json.string ~path:(path ^ "/expected/state") (get (path ^ "/expected") "state" expected) with
      | "active" -> Active | "inactive" -> Inactive
      | _ -> Diagnostic.fail ~path "realization_evidence" "Counterexample state must be active or inactive." in
    let raw_range = get (path ^ "/expected") "range" expected in
    let range_fields = Json.object_fields ~path:(path ^ "/expected/range") raw_range in
    let dtype = Type_spec.of_json ~path:(path ^ "/expected/range/type")
      (Option.value (List.assoc_opt "type" range_fields) ~default:Json.Null) in
    require ~path (Type_spec.kind dtype = Type_spec.Interval) "Counterexample range must be a typed scalar interval.";
    let range = Measurement_contract.Interval.of_json ~path:(path ^ "/expected/range") raw_range in
    let actual = optional (number ~path:(path ^ "/actual") ~nonnegative:false
      ~message:"Counterexample actual must be a finite canonical scalar or null for a missing output.") (get path "actual" fields) in
    let expected = obj ["state", str (match state with Active -> "active" | Inactive -> "inactive");
      "range", Measurement_contract.Interval.to_json range] in
    let json = obj (("expected", expected) :: List.remove_assoc "expected" fields) in
    {packed = pack ~path json; requirement; time; contact; state; range; actual; rule; specification; source}
  let to_json value = value.packed.json
  let canonical_size value = value.packed.size.bytes
  let make ~requirement_id ~time ?contact_id ~state ~range ?actual ~rule_id ~specification_id ?source () =
    of_json (obj ["requirement_id", str requirement_id; "time", raw_number time;
      "contact_id", option_json str contact_id; "expected", obj ["state", str (match state with Active -> "active" | Inactive -> "inactive");
      "range", Measurement_contract.Interval.to_json range]; "actual", option_json raw_number actual;
      "rule_id", str rule_id; "specification_id", str specification_id; "source", option_json source_json source])
  let requirement_id value = value.requirement
  let time value = value.time
  let contact_id value = value.contact
  let state value = value.state
  let range value = value.range
  let actual value = value.actual
  let rule_id value = value.rule
  let specification_id value = value.specification
  let source value = value.source
end

module Requirement_coverage = struct
  type t = {packed : packed; requirement : string; activation : Z.t; inactive : Z.t;
    incomplete : Z.t; cancelled : Z.t}
  let of_json ?(path = "") value =
    let fields = record ~path ["requirement_id"; "activation_deadlines_checked"; "inactive_deadlines_checked";
      "incomplete_episode_count"; "cancelled_episode_count"] value in
    let requirement = name path "requirement_id" fields in
    let count key = match get path key fields with
      | Json.Int value when Z.sign value >= 0 -> value
      | _ -> Diagnostic.fail ~path:(path ^ "/" ^ key) "realization_evidence" "Coverage counts must be nonnegative integers." in
    let activation = count "activation_deadlines_checked" and inactive = count "inactive_deadlines_checked"
    and incomplete = count "incomplete_episode_count" and cancelled = count "cancelled_episode_count" in
    {packed = pack ~path value; requirement; activation; inactive; incomplete; cancelled}
  let to_json value = value.packed.json
  let canonical_size value = value.packed.size.bytes
  let make ~requirement_id ?(activation_deadlines_checked = Z.zero) ?(inactive_deadlines_checked = Z.zero)
      ?(incomplete_episode_count = Z.zero) ?(cancelled_episode_count = Z.zero) () = of_json (obj [
        "requirement_id", str requirement_id; "activation_deadlines_checked", Json.Int activation_deadlines_checked;
        "inactive_deadlines_checked", Json.Int inactive_deadlines_checked; "incomplete_episode_count", Json.Int incomplete_episode_count;
        "cancelled_episode_count", Json.Int cancelled_episode_count])
  let requirement_id value = value.requirement
  let activation_deadlines_checked value = value.activation
  let inactive_deadlines_checked value = value.inactive
  let incomplete_episode_count value = value.incomplete
  let cancelled_episode_count value = value.cancelled
  let exercised value = Z.sign value.activation > 0 && Z.sign value.inactive > 0
end

let outcome_string = function Pass -> "pass" | Fail -> "fail" | Unknown -> "unknown" | Unsupported -> "unsupported"
let evidence_string = function Exact -> "exact" | Model_conditional -> "model_conditional" | Empirical -> "empirical" | Unresolved -> "unresolved"
module Check_result = struct
  type t = {packed : packed; outcome : outcome; dependencies : Dependency_snapshot.t; checked : string list;
    diagnostics : Check_diagnostic.t list; counterexamples : Counterexample.t list; coverage : Requirement_coverage.t list}
  let schema_version = "biocompiler.realization_check.v0.1"
  let of_json ?(path = "") value =
    let fields = record ~path ["schema_version"; "outcome"; "evidence_kind"; "claim_scope"; "dependencies";
      "checked_requirement_ids"; "diagnostics"; "counterexamples"; "coverage"] value in
    let diagnostic_values = Json.array ~path:(path ^ "/diagnostics") (get path "diagnostics" fields) in
    let counterexample_values = Json.array ~path:(path ^ "/counterexamples") (get path "counterexamples" fields) in
    let coverage_values = Json.array ~path:(path ^ "/coverage") (get path "coverage" fields) in
    let outcome = match Json.string ~path:(path ^ "/outcome") (get path "outcome" fields) with
      | "pass" -> Pass | "fail" -> Fail | "unknown" -> Unknown | "unsupported" -> Unsupported
      | _ -> Diagnostic.fail ~path "realization_evidence" "Invalid check outcome." in
    let dependencies = Dependency_snapshot.of_json ~path:(path ^ "/dependencies") (get path "dependencies" fields) in
    let decode key decode values = List.mapi (fun index value -> decode ~path:(path ^ "/" ^ key ^ "/" ^ string_of_int index) value) values in
    let diagnostics = decode "diagnostics" (fun ~path value -> Check_diagnostic.of_json ~path value) diagnostic_values in
    let counterexamples = decode "counterexamples" (fun ~path value -> Counterexample.of_json ~path value) counterexample_values in
    let evidence = Json.string ~path:(path ^ "/evidence_kind") (get path "evidence_kind" fields) in
    require ~path (List.mem evidence ["exact"; "model_conditional"; "empirical"; "unresolved"]) "Invalid evidence kind.";
    let coverage = decode "coverage" (fun ~path value -> Requirement_coverage.of_json ~path value) coverage_values in
    require ~path (evidence = "model_conditional") "This checker only reports model-conditional evidence.";
    Diagnostic.require ~path (Json.string (get path "schema_version" fields) = schema_version)
      "unsupported_schema" "Unsupported realization check schema.";
    require ~path (Json.string (get path "claim_scope" fields) = claim_scope) "Invalid check schema or scope.";
    let checked = names ~path:(path ^ "/checked_requirement_ids") (get path "checked_requirement_ids" fields) in
    let known = unique ~path "Duplicate checked requirements." checked in
    require ~path (counterexamples = [] || outcome = Fail) "Counterexamples require a failed outcome.";
    require ~path (outcome <> Pass || checked <> []) "A passing check must identify checked requirements.";
    require ~path (List.for_all (fun item -> Hashtbl.mem known (Counterexample.requirement_id item)) counterexamples)
      "Counterexample refers to an unknown requirement.";
    require ~path (List.for_all (fun item -> match Check_diagnostic.requirement_id item with
      None -> true | Some id -> Hashtbl.mem known id) diagnostics) "Diagnostic refers to an unknown requirement.";
    let coverage_ids = List.map Requirement_coverage.requirement_id coverage in
    ignore (unique ~path "Invalid requirement coverage references." coverage_ids);
    require ~path (List.for_all (Hashtbl.mem known) coverage_ids) "Invalid requirement coverage references.";
    if outcome = Pass then (
      require ~path (diagnostics = [] && counterexamples = []) "A passing result cannot contain unresolved diagnostics or counterexamples.";
      require ~path (List.length coverage_ids = List.length checked && List.for_all (fun item ->
        Requirement_coverage.exercised item && Z.equal (Requirement_coverage.incomplete_episode_count item) Z.zero) coverage)
        "A passing result requires exercised active and inactive deadlines and complete response coverage.");
    let json = obj (fields |> Measurement_contract.replace "counterexamples" (arr (List.map Counterexample.to_json counterexamples))) in
    {packed = pack ~path json; outcome; dependencies; checked; diagnostics; counterexamples; coverage}
  let to_json value = value.packed.json
  let to_json_text ?(indent = Some 2) value =
    let layout = match indent with None -> Legacy_ascii.Spaced | Some width -> Legacy_ascii.Indented (max 0 width) in
    Legacy_ascii.encode ~layout value.packed.json
  let of_json_text text = of_json (Json.parse text)
  let fingerprint value = Legacy_ascii.fingerprint value.packed.json
  let canonical_size value = value.packed.size.bytes
  let make ~outcome ~dependencies ~checked_requirement_ids ?(diagnostics = []) ?(counterexamples = [])
      ?(evidence_kind = Model_conditional) ?(claim_scope = claim_scope) ?(schema_version = schema_version) ?(coverage = []) () =
    let budget = budget () in
    reserve budget dependencies.size;
    reserve_json budget (str claim_scope); reserve_json budget (str schema_version);
    reserve_list budget (fun value -> measure (str value)) checked_requirement_ids;
    reserve_list budget (fun (value : Check_diagnostic.t) -> value.packed.size) diagnostics;
    reserve_list budget (fun (value : Counterexample.t) -> value.packed.size) counterexamples;
    reserve_list budget (fun (value : Requirement_coverage.t) -> value.packed.size) coverage;
    of_json (obj ["schema_version", str schema_version; "outcome", str (outcome_string outcome);
      "evidence_kind", str (evidence_string evidence_kind); "claim_scope", str claim_scope;
      "dependencies", Dependency_snapshot.to_json dependencies; "checked_requirement_ids", arr (List.map str checked_requirement_ids);
      "diagnostics", arr (List.map Check_diagnostic.to_json diagnostics); "counterexamples", arr (List.map Counterexample.to_json counterexamples);
      "coverage", arr (List.map Requirement_coverage.to_json coverage)])
  let outcome value = value.outcome
  let dependencies value = value.dependencies
  let checked_requirement_ids value = value.checked
  let diagnostics value = value.diagnostics
  let counterexamples value = value.counterexamples
  let coverage value = value.coverage
  let passed value = value.outcome = Pass
  let exercised_requirement_ids value = List.filter_map (fun item ->
    if Requirement_coverage.exercised item then Some (Requirement_coverage.requirement_id item) else None) value.coverage
  let freshness value current = Freshness_report.make (Dependency_snapshot.changed value.dependencies current)
  let is_fresh value current = Freshness_report.fresh (freshness value current)
end
