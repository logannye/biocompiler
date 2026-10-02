open Bioc_wire
open Bioc_domain
module W = Bioc_checker.Work_budget
module B = Bioc_realization_checker.Realization_budget
module R = Bioc_realization_checker.Realization_check
module S = Bioc_realization_checker.Synthetic_candidate_check
module C = Bioc_realization_checker.Component_behavior_check
module A = Bioc_realization_checker.Component_assembly_check
module E = Realization_evidence
module F = Execution_data.Input_frame
module Contract = Realization_contract
let implementation_version = "biocompiler.ocaml.realization_service.v0.1"
let resource_profile = "biocompiler.core.realization_protocol.resources.v1"
let get key raw = Json.field key (Json.object_fields raw)
let string value = Json.String value
(* Frozen capability declarations, independent of filesystem or producer state.
   Resource trees are always supplied by the actual public checker APIs. *)
let declarations = Json.parse {profiles|{"component_assembly":{"assessment_encoding":"python-json-v1","assessment_schema":"biocompiler.component_link_result.v0.3","authority_identity_fields":["request_fingerprint","request_artifact_fingerprint","history_ascii_fingerprint","candidate_fingerprint","assembly_fingerprint"],"claim_scope":"Fresh source, actual synthetic candidate, exact component correspondence, linking and finite-history acceptance only; no search completeness, sequence emission, empirical function or human-use admission.","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"dependency_encoding":"python-json-v1","dependency_schema_version_field":false,"history_codec":{"boundary_version":"biocompiler.native_execution_data.v0.1","frame_fields":["time","signals","contacts"],"numeric_sample_shorthand":true,"sample_fields":["value","present","high","low"],"schema_version_field":false},"implementation":"biocompiler.ocaml.component_assembly_checker.v0.1","input_schemas":{"assembly":["biocompiler.component_assembly.v0.2"],"candidate":["biocompiler.synthetic_candidate.v0.4"],"expected_request":["biocompiler.realization_request.v0.1"]},"limits_fields":["max_work","max_monitor_items","max_request_bytes","max_report_bytes","max_report_nodes"],"limits_null":"fixed_defaults","operations":["verify-component-assembly","replay-component-assembly"],"payload_fields":{"replay-component-assembly":["profile","limits","expected_request","candidate","assembly","history","until","assessment"],"verify-component-assembly":["profile","limits","expected_request","candidate","assembly","history","until"]},"profile":"biocompiler.core.component_assembly.v1","result_schemas":{"replay-component-assembly":"biocompiler.core.component_assembly_assessment.v1","verify-component-assembly":"biocompiler.core.component_assembly_assessment.v1"},"semantic_versions":{"component_linker":"biocompiler.component_linker.v0.3","component_reconstruction":"biocompiler.component_model_reconstruction.v0.1","human_admission_policy":"biocompiler.human_admission_policy.v0.1","model_runner":"biocompiler.synthetic.runner.v0.2","realization_checker":"biocompiler.realization_checker.v0.3","reference_evaluator":"biocompiler.behavior.evaluator.v0.2","synthetic_acceptance":"biocompiler.synthetic.acceptance.v0.5","synthetic_catalog":"biocompiler.synthetic.catalog.v0.2","synthetic_generator":"biocompiler.synthetic.generator.v0.4","synthetic_profiles":["biocompiler.synthetic.combinational.v0.1","biocompiler.synthetic.temporal.v0.1"]},"service_implementation":"biocompiler.ocaml.realization_service.v0.1","supplied_authority_encoding":"python-json-v1","supplied_authority_excluded_fields":["assessment"],"until_codec":"null_or_exact_integer_or_finite_binary64_without_early_numeric_coercion","validation_scope":"source-synthetic-component-correspondence-finite-history-v1","wire_encoding":"python-json-v1"},"component_behavior":{"assessment_encoding":"python-json-ascii-v1","assessment_schema":"biocompiler.realization_check.v0.1","authority_identity_fields":["request_fingerprint","request_artifact_fingerprint","history_ascii_fingerprint","assembly_fingerprint"],"claim_scope":"Fresh source lowering and actual locked component reconstruction/linking/finite-history acceptance only; no synthetic candidate correspondence, search completeness, empirical function or human-use admission.","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"dependency_encoding":"python-json-ascii-v1","dependency_schema_version_field":false,"history_codec":{"boundary_version":"biocompiler.native_execution_data.v0.1","frame_fields":["time","signals","contacts"],"numeric_sample_shorthand":true,"sample_fields":["value","present","high","low"],"schema_version_field":false},"implementation":"biocompiler.ocaml.component_behavior_checker.v0.1","input_schemas":{"assembly":["biocompiler.component_assembly.v0.2"],"expected_request":["biocompiler.realization_request.v0.1"]},"limits_fields":["max_work","max_monitor_items","max_request_bytes","max_report_bytes","max_report_nodes"],"limits_null":"fixed_defaults","operations":["verify-component-behavior","replay-component-behavior"],"payload_fields":{"replay-component-behavior":["profile","limits","expected_request","assembly","history","until","assessment"],"verify-component-behavior":["profile","limits","expected_request","assembly","history","until"]},"profile":"biocompiler.core.component_behavior.v1","result_schemas":{"replay-component-behavior":"biocompiler.core.component_behavior_assessment.v1","verify-component-behavior":"biocompiler.core.component_behavior_assessment.v1"},"semantic_versions":{"component_linker":"biocompiler.component_linker.v0.3","component_reconstruction":"biocompiler.component_model_reconstruction.v0.1","human_admission_policy":"biocompiler.human_admission_policy.v0.1","model_runner":"biocompiler.synthetic.runner.v0.2","realization_checker":"biocompiler.realization_checker.v0.3","reference_evaluator":"biocompiler.behavior.evaluator.v0.2"},"service_implementation":"biocompiler.ocaml.realization_service.v0.1","supplied_authority_encoding":"python-json-v1","supplied_authority_excluded_fields":["assessment"],"until_codec":"null_or_exact_integer_or_finite_binary64_without_early_numeric_coercion","validation_scope":"source-locked-component-finite-history-v1","wire_encoding":"python-json-v1"},"realization":{"assessment_encoding":"python-json-ascii-v1","assessment_schema":"biocompiler.realization_check.v0.1","authority_identity_fields":["behavior_fingerprint","behavior_artifact_ascii_fingerprint","contract_fingerprint","domain_fingerprint","target_fingerprint","mechanism_fingerprint","observation_map_fingerprint","history_ascii_fingerprint"],"claim_scope":"Direct supplied Behavior and model authority only; no source lowering, synthetic provenance, search completeness, empirical function or human-use admission.","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"dependency_claim_scope":"Only dependency identities were constructed from the supplied declarations and exact history/horizon; no model execution, acceptance, source lowering or biological claim is established.","dependency_encoding":"python-json-ascii-v1","dependency_schema_version_field":false,"dependency_validation_scope":"supplied-realization-dependencies-only-v1","history_codec":{"boundary_version":"biocompiler.native_execution_data.v0.1","frame_fields":["time","signals","contacts"],"numeric_sample_shorthand":true,"sample_fields":["value","present","high","low"],"schema_version_field":false},"implementation":"biocompiler.ocaml.realization_checker.v0.1","input_schemas":{"behavior":["biocompiler.behavior.v0.1","biocompiler.behavior.v0.2"],"contract":["biocompiler.behavior_contract.v0.1"],"domain":["biocompiler.operating_domain.v0.1"],"mechanism":["biocompiler.mechanism.synthetic.v0.2"],"observation_map":["biocompiler.observation_map.v0.1"],"target":["biocompiler.target.v0.1","biocompiler.human_target_context.v0.1"]},"limits_fields":["max_work","max_monitor_items","max_request_bytes","max_report_bytes","max_report_nodes"],"limits_null":"fixed_defaults","operations":["realization-dependencies","verify-realization","replay-realization"],"payload_fields":{"realization-dependencies":["profile","limits","behavior","contract","domain","target","mechanism","observation_map","history","until"],"replay-realization":["profile","limits","behavior","contract","domain","target","mechanism","observation_map","history","until","assessment"],"verify-realization":["profile","limits","behavior","contract","domain","target","mechanism","observation_map","history","until"]},"profile":"biocompiler.core.realization.v1","result_schemas":{"realization-dependencies":"biocompiler.core.realization_dependencies.v1","replay-realization":"biocompiler.core.realization_assessment.v1","verify-realization":"biocompiler.core.realization_assessment.v1"},"semantic_versions":{"human_admission_policy":"biocompiler.human_admission_policy.v0.1","model_runner":"biocompiler.synthetic.runner.v0.2","realization_checker":"biocompiler.realization_checker.v0.3","reference_evaluator":"biocompiler.behavior.evaluator.v0.2"},"service_implementation":"biocompiler.ocaml.realization_service.v0.1","supplied_authority_encoding":"python-json-v1","supplied_authority_excluded_fields":["assessment"],"until_codec":"null_or_exact_integer_or_finite_binary64_without_early_numeric_coercion","validation_scope":"supplied-behavior-finite-history-v1","wire_encoding":"python-json-v1"},"synthetic_candidate":{"assessment_encoding":"python-json-ascii-v1","assessment_schema":"biocompiler.realization_check.v0.1","authority_identity_fields":["request_fingerprint","request_artifact_fingerprint","history_ascii_fingerprint","candidate_fingerprint"],"claim_scope":"Fresh source lowering, synthetic provenance and supplied finite-history acceptance only; no component correspondence, search completeness, empirical function or human-use admission.","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"dependency_encoding":"python-json-ascii-v1","dependency_schema_version_field":false,"history_codec":{"boundary_version":"biocompiler.native_execution_data.v0.1","frame_fields":["time","signals","contacts"],"numeric_sample_shorthand":true,"sample_fields":["value","present","high","low"],"schema_version_field":false},"implementation":"biocompiler.ocaml.synthetic_candidate_checker.v0.1","input_schemas":{"candidate":["biocompiler.synthetic_candidate.v0.4"],"expected_request":["biocompiler.realization_request.v0.1"]},"limits_fields":["max_work","max_monitor_items","max_request_bytes","max_report_bytes","max_report_nodes"],"limits_null":"fixed_defaults","operations":["verify-synthetic-candidate","replay-synthetic-candidate"],"payload_fields":{"replay-synthetic-candidate":["profile","limits","expected_request","candidate","history","until","assessment"],"verify-synthetic-candidate":["profile","limits","expected_request","candidate","history","until"]},"profile":"biocompiler.core.synthetic_candidate.v1","result_schemas":{"replay-synthetic-candidate":"biocompiler.core.synthetic_candidate_assessment.v1","verify-synthetic-candidate":"biocompiler.core.synthetic_candidate_assessment.v1"},"semantic_versions":{"human_admission_policy":"biocompiler.human_admission_policy.v0.1","model_runner":"biocompiler.synthetic.runner.v0.2","realization_checker":"biocompiler.realization_checker.v0.3","reference_evaluator":"biocompiler.behavior.evaluator.v0.2","synthetic_acceptance":"biocompiler.synthetic.acceptance.v0.5","synthetic_catalog":"biocompiler.synthetic.catalog.v0.2","synthetic_generator":"biocompiler.synthetic.generator.v0.4","synthetic_profiles":["biocompiler.synthetic.combinational.v0.1","biocompiler.synthetic.temporal.v0.1"]},"service_implementation":"biocompiler.ocaml.realization_service.v0.1","supplied_authority_encoding":"python-json-v1","supplied_authority_excluded_fields":["assessment"],"until_codec":"null_or_exact_integer_or_finite_binary64_without_early_numeric_coercion","validation_scope":"source-synthetic-provenance-finite-history-v1","wire_encoding":"python-json-v1"}}|profiles}

type family = Realization | Synthetic_candidate | Component_behavior | Component_assembly
let family_name = function Realization -> "realization" | Synthetic_candidate -> "synthetic_candidate"
  | Component_behavior -> "component_behavior" | Component_assembly -> "component_assembly"
let declaration family = get (family_name family) declarations
let operations = ["realization-dependencies"; "verify-realization"; "replay-realization";
  "verify-synthetic-candidate"; "replay-synthetic-candidate";
  "verify-component-behavior"; "replay-component-behavior";
  "verify-component-assembly"; "replay-component-assembly"]
let validation_scopes = ["supplied-realization-dependencies-only-v1";
  "supplied-behavior-finite-history-v1"; "source-synthetic-provenance-finite-history-v1";
  "source-locked-component-finite-history-v1";
  "source-synthetic-component-correspondence-finite-history-v1"]
let route = function
  | "realization-dependencies" -> Realization, false, true
  | "verify-realization" -> Realization, false, false
  | "replay-realization" -> Realization, true, false
  | "verify-synthetic-candidate" -> Synthetic_candidate, false, false
  | "replay-synthetic-candidate" -> Synthetic_candidate, true, false
  | "verify-component-behavior" -> Component_behavior, false, false
  | "replay-component-behavior" -> Component_behavior, true, false
  | "verify-component-assembly" -> Component_assembly, false, false
  | "replay-component-assembly" -> Component_assembly, true, false
  | _ -> Diagnostic.fail "realization_protocol_operation" "Unknown realization protocol operation."
type controls = { max_work : int; max_monitor_items : int; max_request_bytes : int;
  max_report_bytes : int; max_report_nodes : int }
let defaults = {max_work=50_000_000; max_monitor_items=100_000;
  max_request_bytes=Limits.max_request_bytes; max_report_bytes=Limits.max_response_bytes;
  max_report_nodes=Limits.max_json_nodes}
let control_fields = ["max_work"; "max_monitor_items"; "max_request_bytes"; "max_report_bytes"; "max_report_nodes"]
let controls = function
  | Json.Null -> defaults
  | Json.Object fields ->
      Json.exact_fields ~path:"payload.limits" control_fields fields;
      let value key ceiling = match Json.field key fields with
        | Json.Int value when Z.sign value > 0 && Z.compare value (Z.of_int ceiling) <= 0 -> Z.to_int value
        | _ -> Diagnostic.fail ~path:("payload.limits." ^ key) "realization_limits"
            "Realization limits must be positive integer reductions of the native profile." in
      let max_work = value "max_work" defaults.max_work in
      let max_monitor_items = value "max_monitor_items" defaults.max_monitor_items in
      let max_request_bytes = value "max_request_bytes" defaults.max_request_bytes in
      let max_report_bytes = value "max_report_bytes" defaults.max_report_bytes in
      let max_report_nodes = value "max_report_nodes" defaults.max_report_nodes in
      {max_work;max_monitor_items;max_request_bytes;max_report_bytes;max_report_nodes}
  | _ -> Diagnostic.fail ~path:"payload.limits" "realization_limits"
      "Realization limits must be null or an exact object of five integer reductions."
let common_limits x = B.make_limits ~max_work:x.max_work ~max_monitor_items:x.max_monitor_items
  ~max_request_bytes:x.max_request_bytes ~max_report_bytes:x.max_report_bytes ~max_report_nodes:x.max_report_nodes ()
let realization_limits x = R.make_limits ~max_work:x.max_work ~max_monitor_items:x.max_monitor_items
  ~max_request_bytes:x.max_request_bytes ~max_report_bytes:x.max_report_bytes ~max_report_nodes:x.max_report_nodes ()
let synthetic_limits x = S.make_limits ~max_work:x.max_work ~max_monitor_items:x.max_monitor_items
  ~max_request_bytes:x.max_request_bytes ~max_report_bytes:x.max_report_bytes ~max_report_nodes:x.max_report_nodes ()
let behavior_limits x = C.make_limits ~max_work:x.max_work ~max_monitor_items:x.max_monitor_items
  ~max_request_bytes:x.max_request_bytes ~max_report_bytes:x.max_report_bytes ~max_report_nodes:x.max_report_nodes ()
let assembly_limits x = A.make_limits ~max_work:x.max_work ~max_monitor_items:x.max_monitor_items
  ~max_request_bytes:x.max_request_bytes ~max_report_bytes:x.max_report_bytes ~max_report_nodes:x.max_report_nodes ()
let protocol_resources x = Json.Object ["profile",string resource_profile;
  "max_work",Json.int x.max_work; "max_monitor_items",Json.int x.max_monitor_items;
  "max_request_bytes",Json.int x.max_request_bytes; "max_request_nodes",Json.int Limits.max_json_nodes;
  "max_report_bytes",Json.int x.max_report_bytes; "max_report_nodes",Json.int x.max_report_nodes;
  "max_depth",Json.int Limits.max_depth; "max_string_bytes",Json.int Limits.max_string_bytes;
  "max_number_chars",Json.int Limits.max_number_chars;
  "node_accounting",string "values_and_object_keys";
  "request_scope",string "complete_payload_including_profile_limits_and_replay_assessment";
  "request_encoding",string "compact_utf8_plus_one_separator";
  "work_accounting",string "single_ancestor_for_import_authority_hash_fresh_check_replay_and_publication";
  "report_scope",string "complete_result_and_final_protocol_response";
  "report_encoding",string "compact_ensure_ascii_true_conservative_outer_reservation_then_utf8_wire"]
let resources family x =
  let checker = match family with Realization -> R.limits_json (realization_limits x)
    | Synthetic_candidate -> S.limits_json (synthetic_limits x)
    | Component_behavior -> C.limits_json (behavior_limits x)
    | Component_assembly -> A.limits_json (assembly_limits x) in
  Json.Object ["protocol",protocol_resources x; "checker",checker]
let profiles = List.map (fun family -> family_name family,
    Json.Object (("resources",resources family defaults) :: Json.object_fields (declaration family)))
    [Realization; Synthetic_candidate; Component_behavior; Component_assembly]

(* This fixed transport pass precedes control decoding and terminates even for
   in-process cyclic JSON or cyclic list spines. It charges the same ancestor
   used by every later phase. The chosen reduction subtracts this prefix rather
   than granting a new allowance after parsing controls. Wire values, unlike
   checker inventories, exclude object keys from their 250k value ceiling. *)
type pending = Value of Json.t * int | Array_tail of Json.t list * int
  | Object_tail of (string * Json.t) list * int
let preflight_transport work raw =
  let bytes = ref 0 and values = ref 0 in
  let add amount =
    Diagnostic.require (amount <= Limits.max_request_bytes - !bytes) "request_too_large"
      "Complete realization request exceeds the fixed transport byte limit.";
    W.charge work amount; bytes := !bytes + amount in
  let quoted value =
    Diagnostic.require (String.length value <= Limits.max_string_bytes) "string_limit"
      "A request string exceeds its fixed byte limit.";
    add (String.length value + 2); Json.validate_utf8 value;
    String.iter (function '"' | '\\' -> add 1
      | '\b' | '\012' | '\n' | '\r' | '\t' -> add 1
      | c when Char.code c < 32 -> add 5 | _ -> ()) value in
  let rec visit = function
    | [] -> ()
    | Value (raw,depth) :: rest ->
        Diagnostic.require (depth <= Limits.max_depth) "nesting_limit" "Request nesting exceeds its fixed limit.";
        Diagnostic.require (!values < Limits.max_json_nodes) "node_limit" "Request value count exceeds its fixed limit.";
        incr values; W.charge work 1;
        (match raw with
         | Json.String value -> quoted value; visit rest
         | Json.Object fields -> add 2; visit (Object_tail (fields,depth+1) :: rest)
         | Json.Array items -> add 2; visit (Array_tail (items,depth+1) :: rest)
         | Json.Int value ->
             Diagnostic.require (Z.numbits value <= 4 * Limits.max_number_chars) "number_limit"
               "A request integer exceeds its fixed token limit.";
             W.charge work (1 + Z.numbits value / 3);
             let text = Z.to_string value in
             Diagnostic.require (String.length text <= Limits.max_number_chars) "number_limit"
               "A request integer exceeds its fixed token limit.";
             add (String.length text); visit rest
         | value -> W.charge work 32; add (String.length (Canonical.encode value)); visit rest)
    | Array_tail ([],_) :: rest | Object_tail ([],_) :: rest -> visit rest
    | Array_tail (value :: values,depth) :: rest ->
        (match values with [] -> () | _ -> add 1);
        visit (Value (value,depth) :: Array_tail (values,depth) :: rest)
    | Object_tail ((key,value) :: fields,depth) :: rest ->
        W.charge work 1; quoted key; add 1;
        (match fields with [] -> () | _ -> add 1);
        visit (Value (value,depth) :: Object_tail (fields,depth) :: rest) in
  visit [Value (raw,0)]
let until = function Json.Null -> None | Json.Int value -> Some (Runtime_number.Integer value)
  | Json.Float value -> Some (Runtime_number.Real value)
  | _ -> Diagnostic.fail ~path:"payload.until" "invalid_type" "Expected null or an exact numeric horizon."
let history budget raw =
  let frames = B.bounded_list budget (Json.array ~path:"payload.history" raw) in
  B.retain_monitor budget (List.length frames);
  List.mapi (fun index raw -> F.of_json ~path:("payload.history[" ^ string_of_int index ^ "]") raw) frames
let history_fingerprint budget frames =
  B.charge budget (List.length frames);
  let raw = Json.Array (List.map F.to_json frames) in
  let measured = Legacy_ascii.measure raw in
  B.charge budget (measured.bytes + measured.nodes);
  Legacy_ascii.fingerprint raw
let request_identities budget request frames =
  ["request_fingerprint",string (Realization_request.fingerprint request);
   "request_artifact_fingerprint",string (Realization_request.artifact_fingerprint request);
   "history_ascii_fingerprint",string (history_fingerprint budget frames)]
let report_bytes budget ~ascii raw =
  B.reserve_report budget raw;
  let size = Legacy_ascii.measure raw in
  (* Include both canonical construction and hashing/comparison in the ancestor. *)
  B.charge budget (2 * size.bytes + size.nodes);
  if ascii then Legacy_ascii.encode raw else Canonical.encode raw
let historical budget family replay fields =
  if not replay then None else (
    let raw = Json.field "assessment" fields in
    let ascii = family <> Component_assembly in
    let bytes = report_bytes budget ~ascii raw in
    B.charge budget (String.length bytes);
    let normalized = match family with
      | Component_assembly -> Composition_evidence.Result.of_json ~path:"payload.assessment" raw
          |> Composition_evidence.Result.to_json
      | _ -> E.Check_result.of_json ~path:"payload.assessment" raw |> E.Check_result.to_json in
    let normalized_bytes = report_bytes budget ~ascii normalized in
    Some (bytes,normalized_bytes))
let compare_replay historical bytes fingerprint = match historical with
  | None -> ()
  | Some (raw,normalized) -> Diagnostic.require
      (String.equal raw normalized && String.equal normalized bytes &&
       String.equal (Canonical.sha256 raw) fingerprint)
      "realization_assessment_mismatch"
      "The complete historical assessment differs from fresh checking of the supplied authority."
type usage = { work_charged : int; request_bytes : int; report_bytes : int; retained_peak : int }
let handle_with_usage ?parent ~executable ~request_id ~operation payload =
  let family,replay,dependency_only = route operation in
  let ancestor = match parent with
    | None -> W.create ~profile:resource_profile ~error_code:"realization_work_limit" ~maximum:defaults.max_work ()
    | Some parent -> W.nested ~parent ~profile:resource_profile ~error_code:"realization_work_limit"
        ~maximum:defaults.max_work () in
  let initial = W.remaining ancestor in
  W.charge ancestor 1;
  let incoming = Json.Object ["protocol",string Protocol.version; "request_id",string request_id;
    "operation",string operation; "payload",payload] in
  preflight_transport ancestor incoming;
  let fields = Json.object_fields ~path:"payload" payload in
  let metadata = declaration family in
  let required = get operation (get "payload_fields" metadata) |> Json.array |> List.map Json.string in
  Json.exact_fields ~path:"payload" required fields;
  let supplied_profile = Json.string ~path:"payload.profile" (Json.field "profile" fields) in
  Diagnostic.require (supplied_profile = Json.string (get "profile" metadata))
    "realization_protocol_profile" "The requested profile does not match the realization operation family.";
  let control = controls (Json.field "limits" fields) in
  let prefix = initial - W.remaining ancestor in
  Diagnostic.require (prefix <= control.max_work) "realization_work_limit"
    "Realization request framing already exceeds the selected operation work limit.";
  let reduced = W.nested ~parent:ancestor ~profile:resource_profile ~error_code:"realization_work_limit"
      ~maximum:(control.max_work - prefix) () in
  let budget = B.create ~parent:reduced ~limits:(common_limits control) () in
  B.reserve_request budget payload;
  let input_bytes = (B.usage budget).request_bytes in
  (* Prospective structural import and raw authority hashing charges. Typed
     import is bounded by the complete raw payload before it can allocate. *)
  B.charge budget (2 * input_bytes);
  let authority = Json.Object (List.filter (fun (key,_) -> key <> "assessment") fields) in
  let authority_fingerprint = Canonical.fingerprint authority in
  let parent = B.work budget in
  let identities,assessment,historical = match family with
    | Realization ->
        let behavior = Behavior.of_json (Json.field "behavior" fields) in
        let contract = Contract.Behavior_contract.of_json ~path:"payload.contract" (Json.field "contract" fields) in
        let domain = Contract.Operating_domain.of_json ~path:"payload.domain" (Json.field "domain" fields) in
        let target = Build_request.Target.of_json ~path:"payload.target" (Json.field "target" fields) in
        let mechanism = Mechanism.of_json ~path:"payload.mechanism" (Json.field "mechanism" fields) in
        let observation_map = Observation_map.of_json ~path:"payload.observation_map" (Json.field "observation_map" fields) in
        let frames = history budget (Json.field "history" fields) in
        let until = until (Json.field "until" fields) in
        let historical = historical budget family replay fields in
        B.charge budget input_bytes;
        let behavior_raw = Behavior.to_json behavior in
        let size = Legacy_ascii.measure behavior_raw in
        B.charge budget (size.bytes + size.nodes);
        let identities = ["behavior_fingerprint",string (Behavior.fingerprint behavior);
          "behavior_artifact_ascii_fingerprint",string (Legacy_ascii.fingerprint behavior_raw);
          "contract_fingerprint",string (Contract.Behavior_contract.fingerprint contract);
          "domain_fingerprint",string (Contract.Operating_domain.fingerprint domain);
          "target_fingerprint",string (Build_request.Target.fingerprint target);
          "mechanism_fingerprint",string (Mechanism.fingerprint mechanism);
          "observation_map_fingerprint",string (Observation_map.fingerprint observation_map);
          "history_ascii_fingerprint",string (history_fingerprint budget frames)] in
        let limits = realization_limits control in
        let result = if dependency_only then R.dependencies ?until ~limits ~parent behavior contract domain target mechanism
            observation_map frames |> E.Dependency_snapshot.to_json
          else R.check ?until ~limits ~parent behavior contract domain target mechanism observation_map frames
            |> E.Check_result.to_json in
        identities,result,historical
    | Synthetic_candidate ->
        let request = Realization_request.of_json ~path:"payload.expected_request" (Json.field "expected_request" fields) in
        let candidate = Synthetic_authority.Candidate.of_json ~path:"payload.candidate" (Json.field "candidate" fields) in
        let frames = history budget (Json.field "history" fields) in
        let until = until (Json.field "until" fields) in
        let historical = historical budget family replay fields in
        let identities = request_identities budget request frames @
          ["candidate_fingerprint",string (Synthetic_authority.Candidate.fingerprint candidate)] in
        let result = S.check ?until ~limits:(synthetic_limits control) ~parent request candidate frames in
        identities,E.Check_result.to_json result,historical
    | Component_behavior ->
        let request = Realization_request.of_json ~path:"payload.expected_request" (Json.field "expected_request" fields) in
        let assembly = Component_assembly.of_json ~path:"payload.assembly" (Json.field "assembly" fields) in
        let frames = history budget (Json.field "history" fields) in
        let until = until (Json.field "until" fields) in
        let historical = historical budget family replay fields in
        let identities = request_identities budget request frames @
          ["assembly_fingerprint",string (Component_assembly.fingerprint assembly)] in
        let result = C.check ?until ~limits:(behavior_limits control) ~parent request assembly frames in
        identities,E.Check_result.to_json result,historical
    | Component_assembly ->
        let request = Realization_request.of_json ~path:"payload.expected_request" (Json.field "expected_request" fields) in
        let candidate = Synthetic_authority.Candidate.of_json ~path:"payload.candidate" (Json.field "candidate" fields) in
        let assembly = Component_assembly.of_json ~path:"payload.assembly" (Json.field "assembly" fields) in
        let frames = history budget (Json.field "history" fields) in
        let until = until (Json.field "until" fields) in
        let historical = historical budget family replay fields in
        let identities = request_identities budget request frames @
          ["candidate_fingerprint",string (Synthetic_authority.Candidate.fingerprint candidate);
           "assembly_fingerprint",string (Component_assembly.fingerprint assembly)] in
        let result = A.check ?until ~limits:(assembly_limits control) ~parent request candidate assembly frames in
        identities,Composition_evidence.Result.to_json result,historical in
  let bytes = report_bytes budget ~ascii:(family <> Component_assembly) assessment in
  let fingerprint = Canonical.sha256 bytes in
  compare_replay historical bytes fingerprint;
  let validation_key,claim_key,report_key,fingerprint_key = if dependency_only then
      "dependency_validation_scope","dependency_claim_scope","dependencies","dependencies_fingerprint"
    else "validation_scope","claim_scope","assessment","assessment_fingerprint" in
  let result = Json.Object ["schema_version",get operation (get "result_schemas" metadata);
    "profile",get "profile" metadata; "implementation",get "implementation" metadata;
    "service_implementation",string implementation_version; "resource_profile",string resource_profile;
    "resources",resources family control; "validation_scope",get validation_key metadata;
    "claim_scope",get claim_key metadata; "supplied_authority_fingerprint",string authority_fingerprint;
    "authority_identities",Json.Object identities; report_key,assessment; fingerprint_key,string fingerprint] in
  B.reserve_report budget result;
  let request = {Protocol.request_id;operation;payload} in
  let response = Protocol.response ~executable ~request:(Some request) ~status:Protocol.Ok ~result:(Some result) [] in
  (* Publication includes the actual request ID, role, operation and framing,
     not an estimated envelope. Reserve before the caller encodes its response. *)
  B.reserve_report budget response;
  let size = Legacy_ascii.measure response in
  B.charge budget (size.bytes + size.nodes);
  let usage = B.usage budget in
  result,{work_charged=initial - W.remaining ancestor;request_bytes=usage.request_bytes;
    report_bytes=usage.report_bytes;retained_peak=usage.monitor_peak}
let handle ?parent ~executable ~request_id ~operation payload =
  fst (handle_with_usage ?parent ~executable ~request_id ~operation payload)
