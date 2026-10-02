open Bioc_wire
open Bioc_domain
module W = Bioc_checker.Work_budget
module B = Bioc_realization_checker.Realization_budget
module G = Bioc_synthetic_producer.Generator
module S = Bioc_synthetic_producer.Selection
module C = Bioc_synthetic_producer.Components
module A = Synthetic_authority
module F = Execution_data.Input_frame
let implementation_version = "biocompiler.ocaml.synthetic_producer_service.v0.1"
let resource_profile = "biocompiler.core.synthetic_producer_protocol.resources.v1"
let get key raw = Json.field key (Json.object_fields raw)
let string value = Json.String value
let declarations = Json.parse {profiles|{"synthetic_components":{"authority_identity_fields":["request_fingerprint","request_artifact_fingerprint","history_ascii_fingerprint","candidate_fingerprint"],"claim_scope":"Complete registry and composition from a freshly accepted supplied synthetic candidate and finite history only; no component linking, molecular construction, empirical function or human-use admission.","config_null":"default_synthetic_generator_config","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"generation_error_fields":["message","node_id","source","formatted"],"generation_error_source_fields":["file","line","function"],"history_codec":{"boundary_version":"biocompiler.native_execution_data.v0.1","frame_fields":["time","signals","contacts"],"numeric_sample_shorthand":true,"sample_fields":["value","present","high","low"],"schema_version_field":false},"implementation":"biocompiler.synthetic_components.v0.2","input_schemas":{"candidate":["biocompiler.synthetic_candidate.v0.4"],"request":["biocompiler.realization_request.v0.1"]},"limits_fields":["max_monitor_items","max_report_bytes","max_report_nodes","max_request_bytes","max_work"],"limits_null":"fixed_defaults","operations":["adapt-synthetic-components"],"outcomes":["produced","unsupported"],"payload_fields":{"adapt-synthetic-components":["profile","limits","request","candidate","history","until"]},"profile":"biocompiler.core.synthetic_components.v1","record_encoding":"python-json-v1","record_fields":["registry","composition","acceptance"],"record_schema":null,"resource_profile":"biocompiler.core.synthetic_producer_protocol.resources.v1","result_schema":"biocompiler.core.synthetic_production.v1","role":"bioc-core","service_implementation":"biocompiler.ocaml.synthetic_producer_service.v0.1","supplied_authority_encoding":"python-json-v1","supplied_authority_excluded_fields":[],"unsupported_transport":"ok_with_complete_structured_generation_error","until_codec":"null_or_exact_integer_or_finite_binary64_without_early_numeric_coercion","validation_scope":"fresh-synthetic-component-adaptation-only-v1","wire_encoding":"python-json-v1"},"synthetic_generation":{"authority_identity_fields":["request_fingerprint","request_artifact_fingerprint","config_fingerprint"],"claim_scope":"Complete deterministic software proposal and hard-policy checking only; no finite-history acceptance, search completeness, empirical function or human-use admission.","config_null":"default_synthetic_generator_config","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"generation_error_fields":["message","node_id","source","formatted"],"generation_error_source_fields":["file","line","function"],"implementation":"biocompiler.synthetic.generator.v0.4","input_schemas":{"config":["biocompiler.synthetic_generator_config.v0.3"],"request":["biocompiler.realization_request.v0.1"]},"limits_fields":["max_monitor_items","max_report_bytes","max_report_nodes","max_request_bytes","max_work"],"limits_null":"fixed_defaults","operations":["generate-synthetic"],"outcomes":["produced","unsupported"],"payload_fields":{"generate-synthetic":["profile","limits","request","config"]},"profile":"biocompiler.core.synthetic_generation.v1","record_encoding":"python-json-v1","record_fields":null,"record_schema":"biocompiler.synthetic_candidate.v0.4","resource_profile":"biocompiler.core.synthetic_producer_protocol.resources.v1","result_schema":"biocompiler.core.synthetic_production.v1","role":"bioc-core","service_implementation":"biocompiler.ocaml.synthetic_producer_service.v0.1","supplied_authority_encoding":"python-json-v1","supplied_authority_excluded_fields":[],"unsupported_transport":"ok_with_complete_structured_generation_error","until_codec":"null_or_exact_integer_or_finite_binary64_without_early_numeric_coercion","validation_scope":"deterministic-synthetic-proposal-only-v1","wire_encoding":"python-json-v1"},"synthetic_selection":{"authority_identity_fields":["request_fingerprint","request_artifact_fingerprint","config_fingerprint","history_ascii_fingerprint"],"claim_scope":"Complete native and de_morgan strategy proposals, hard-policy rejections, fresh finite-history checks and deterministic ranking only; no search completeness, empirical function or human-use admission.","config_null":"default_synthetic_generator_config","default_limits":{"max_monitor_items":100000,"max_report_bytes":33554432,"max_report_nodes":250000,"max_request_bytes":16777216,"max_work":50000000},"generation_error_fields":["message","node_id","source","formatted"],"generation_error_source_fields":["file","line","function"],"history_codec":{"boundary_version":"biocompiler.native_execution_data.v0.1","frame_fields":["time","signals","contacts"],"numeric_sample_shorthand":true,"sample_fields":["value","present","high","low"],"schema_version_field":false},"implementation":"biocompiler.ocaml.synthetic_selection.v0.1","input_schemas":{"config":["biocompiler.synthetic_generator_config.v0.3"],"request":["biocompiler.realization_request.v0.1"]},"limits_fields":["max_monitor_items","max_report_bytes","max_report_nodes","max_request_bytes","max_work"],"limits_null":"fixed_defaults","operations":["select-synthetic"],"outcomes":["produced","unsupported"],"payload_fields":{"select-synthetic":["profile","limits","request","config","history","until"]},"profile":"biocompiler.core.synthetic_selection.v1","record_encoding":"python-json-v1","record_fields":null,"record_schema":"biocompiler.synthetic_selection_result.v0.1","resource_profile":"biocompiler.core.synthetic_producer_protocol.resources.v1","result_schema":"biocompiler.core.synthetic_production.v1","role":"bioc-core","service_implementation":"biocompiler.ocaml.synthetic_producer_service.v0.1","supplied_authority_encoding":"python-json-v1","supplied_authority_excluded_fields":[],"unsupported_transport":"ok_with_complete_structured_generation_error","until_codec":"null_or_exact_integer_or_finite_binary64_without_early_numeric_coercion","validation_scope":"two-strategy-synthetic-selection-finite-history-v1","wire_encoding":"python-json-v1"}}|profiles}
type family = Generation | Selection | Components
let family_name = function Generation -> "synthetic_generation" | Selection -> "synthetic_selection" | Components -> "synthetic_components"
let declaration family = get (family_name family) declarations
let families = [Generation;Selection;Components]
let operations = ["generate-synthetic";"select-synthetic";"adapt-synthetic-components"]
let validation_scopes = List.map (fun family -> Json.string (get "validation_scope" (declaration family))) families
let route = function
  | "generate-synthetic" -> Generation
  | "select-synthetic" -> Selection
  | "adapt-synthetic-components" -> Components
  | _ -> Diagnostic.fail "synthetic_producer_operation" "Unknown synthetic producer operation."
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
        | _ -> Diagnostic.fail ~path:("payload.limits." ^ key) "synthetic_producer_limits"
            "Synthetic producer limits must be positive integer reductions of the native profile." in
      let max_work = value "max_work" defaults.max_work in
      let max_monitor_items = value "max_monitor_items" defaults.max_monitor_items in
      let max_request_bytes = value "max_request_bytes" defaults.max_request_bytes in
      let max_report_bytes = value "max_report_bytes" defaults.max_report_bytes in
      let max_report_nodes = value "max_report_nodes" defaults.max_report_nodes in
      {max_work;max_monitor_items;max_request_bytes;max_report_bytes;max_report_nodes}
  | _ -> Diagnostic.fail ~path:"payload.limits" "synthetic_producer_limits"
      "Synthetic producer limits must be null or an exact object of five integer reductions."
let common_limits x = B.make_limits ~max_work:x.max_work ~max_monitor_items:x.max_monitor_items
  ~max_request_bytes:x.max_request_bytes ~max_report_bytes:x.max_report_bytes ~max_report_nodes:x.max_report_nodes ()
let generator_limits x = G.make_limits ~max_work:x.max_work ~max_monitor_items:x.max_monitor_items
  ~max_request_bytes:x.max_request_bytes ~max_report_bytes:x.max_report_bytes ~max_report_nodes:x.max_report_nodes ()
let selection_limits x = S.make_limits ~max_work:x.max_work ~max_monitor_items:x.max_monitor_items
  ~max_request_bytes:x.max_request_bytes ~max_report_bytes:x.max_report_bytes ~max_report_nodes:x.max_report_nodes ()
let components_limits x = C.make_limits ~max_work:x.max_work ~max_monitor_items:x.max_monitor_items
  ~max_request_bytes:x.max_request_bytes ~max_report_bytes:x.max_report_bytes ~max_report_nodes:x.max_report_nodes ()
let protocol_resources x = Json.Object ["profile",string resource_profile;
  "max_work",Json.int x.max_work; "max_monitor_items",Json.int x.max_monitor_items;
  "max_request_bytes",Json.int x.max_request_bytes; "max_request_nodes",Json.int Limits.max_json_nodes;
  "max_report_bytes",Json.int x.max_report_bytes; "max_report_nodes",Json.int x.max_report_nodes;
  "max_depth",Json.int Limits.max_depth; "max_string_bytes",Json.int Limits.max_string_bytes;
  "max_number_chars",Json.int Limits.max_number_chars;
  "node_accounting",string "values_and_object_keys";
  "request_scope",string "complete_payload_including_profile_and_limits";
  "request_encoding",string "compact_utf8_plus_one_separator";
  "work_accounting",string "single_ancestor_for_framing_import_authority_hash_production_and_publication";
  "report_scope",string "complete_result_and_final_protocol_response";
  "report_encoding",string "compact_ensure_ascii_true_conservative_outer_reservation_then_utf8_wire"]
let resources family x =
  let producer = match family with Generation -> G.limits_json (generator_limits x)
    | Selection -> S.limits_json (selection_limits x)
    | Components -> C.limits_json (components_limits x) in
  Json.Object ["protocol",protocol_resources x;"producer",producer]
let profiles = List.map (fun family -> family_name family,
  Json.Object (("resources",resources family defaults) :: Json.object_fields (declaration family))) families
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
      "Complete synthetic producer request exceeds the fixed transport byte limit.";
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
let optional encode = function None -> Json.Null | Some value -> encode value
let source_json (source:Behavior.source_location) = Json.Object ["file",string source.file;
  "line",Json.Int source.line;"function",string source.function_name]
let error_json (error:G.error) = Json.Object ["message",string error.message;
  "node_id",optional string error.node_id;"source",optional source_json error.source;
  "formatted",string (G.format_error error)]
type usage = { work_charged:int;request_bytes:int;report_bytes:int;retained_peak:int }
let handle_with_usage ?parent ~executable ~request_id ~operation payload =
  Diagnostic.require (executable=Protocol.Core) "unsupported_operation"
    "Synthetic production is available only in the producer executable.";
  let family = route operation in
  let ancestor = match parent with
    | None -> W.create ~profile:resource_profile ~error_code:"synthetic_producer_work_limit" ~maximum:defaults.max_work ()
    | Some parent -> W.nested ~parent ~profile:resource_profile ~error_code:"synthetic_producer_work_limit" ~maximum:defaults.max_work () in
  let initial = W.remaining ancestor in
  W.charge ancestor 1;
  let incoming = Json.Object ["protocol",string Protocol.version;"request_id",string request_id;
    "operation",string operation;"payload",payload] in
  preflight_transport ancestor incoming;
  let fields = Json.object_fields ~path:"payload" payload in
  let metadata = declaration family in
  let required = get operation (get "payload_fields" metadata) |> Json.array |> List.map Json.string in
  Json.exact_fields ~path:"payload" required fields;
  Diagnostic.require (Json.string ~path:"payload.profile" (Json.field "profile" fields) = Json.string (get "profile" metadata))
    "synthetic_producer_profile" "The requested profile does not match this producer operation.";
  let control = controls (Json.field "limits" fields) in
  let prefix = initial - W.remaining ancestor in
  Diagnostic.require (prefix <= control.max_work) "synthetic_producer_work_limit"
    "Synthetic producer framing exceeds the selected work limit.";
  let reduced = W.nested ~parent:ancestor ~profile:resource_profile ~error_code:"synthetic_producer_work_limit"
    ~maximum:(control.max_work-prefix) () in
  let budget = B.create ~parent:reduced ~limits:(common_limits control) () in
  B.reserve_request budget payload;
  let input_bytes = (B.usage budget).request_bytes in
  B.charge budget (2 * input_bytes);
  let supplied_authority = Canonical.fingerprint payload in
  let request = Realization_request.of_json ~path:"payload.request" (Json.field "request" fields) in
  let base_identities = ["request_fingerprint",string (Realization_request.fingerprint request);
    "request_artifact_fingerprint",string (Realization_request.artifact_fingerprint request)] in
  let config = match family with Components -> None | Generation | Selection ->
    Some (match Json.field "config" fields with Json.Null -> A.Config.make ()
      | raw -> A.Config.of_json ~path:"payload.config" raw) in
  let frames,horizon = match family with Generation -> [],None | Selection | Components ->
    history budget (Json.field "history" fields),until (Json.field "until" fields) in
  let candidate = match family with Components ->
      Some (A.Candidate.of_json ~path:"payload.candidate" (Json.field "candidate" fields))
    | Generation | Selection -> None in
  let identities = base_identities @
    (match config with None -> [] | Some config -> ["config_fingerprint",string (A.Config.fingerprint config)]) @
    (match family with Generation -> [] | Selection | Components ->
      ["history_ascii_fingerprint",string (history_fingerprint budget frames)]) @
    (match candidate with None -> [] | Some candidate -> ["candidate_fingerprint",string (A.Candidate.fingerprint candidate)]) in
  let parent = B.work budget in
  let retained = (B.usage budget).monitor_peak in
  Diagnostic.require (retained < control.max_monitor_items) "realization_monitor_limit"
    "No producer retention capacity remains after history import.";
  let child_control = {control with max_monitor_items=control.max_monitor_items-retained} in
  let record,generation_error,child_retained =
    try match family with
      | Generation -> let record,usage = G.generate_with_usage ?config ~limits:(generator_limits child_control) ~parent request in
          Some (A.Candidate.to_json record),None,usage.retained_peak
      | Selection -> let record,usage = S.select_with_usage ?config ?until:horizon ~limits:(selection_limits child_control) ~parent request frames in
          Some (Synthetic_selection.Result.to_json record),None,usage.retained_peak
      | Components ->
          let candidate = match candidate with Some candidate -> candidate | None -> assert false in
          let record,usage = C.adapt_with_usage ?until:horizon ~limits:(components_limits child_control) ~parent request candidate frames in
          Some (C.to_json record),None,usage.retained_peak
    with G.Unsupported error -> None,Some (error_json error),0 in
  let retained = (B.usage budget).monitor_peak in
  Diagnostic.require (child_retained <= control.max_monitor_items-retained) "realization_monitor_limit"
    "Producer and protocol retained items exceed their shared limit.";
  let record_fingerprint = match record with None -> Json.Null | Some record ->
    B.reserve_report budget record;
    let size = Legacy_ascii.measure record in
    B.charge budget (2 * size.bytes + size.nodes);
    string (Canonical.fingerprint record) in
  Option.iter (B.reserve_report budget) generation_error;
  let result = Json.Object ["schema_version",get "result_schema" metadata;
    "profile",get "profile" metadata;"implementation",get "implementation" metadata;
    "service_implementation",string implementation_version;"resource_profile",string resource_profile;
    "resources",resources family control;"validation_scope",get "validation_scope" metadata;
    "claim_scope",get "claim_scope" metadata;"supplied_authority_fingerprint",string supplied_authority;
    "authority_identities",Json.Object identities;"outcome",string (if Option.is_some record then "produced" else "unsupported");
    "record",optional Fun.id record;"record_fingerprint",record_fingerprint;
    "generation_error",optional Fun.id generation_error] in
  B.reserve_report budget result;
  let request = {Protocol.request_id;operation;payload} in
  let response = Protocol.response ~executable ~request:(Some request) ~status:Protocol.Ok ~result:(Some result) [] in
  B.reserve_report budget response;
  let size = Legacy_ascii.measure response in
  B.charge budget (size.bytes + size.nodes);
  let usage = B.usage budget in
  result,{work_charged=initial-W.remaining ancestor;request_bytes=usage.request_bytes;
    report_bytes=usage.report_bytes;retained_peak=retained+child_retained}
let handle ?parent ~executable ~request_id ~operation payload =
  fst (handle_with_usage ?parent ~executable ~request_id ~operation payload)
