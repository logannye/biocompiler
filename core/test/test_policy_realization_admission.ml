open Bioc_wire
module D = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module R = Bioc_domain.Policy_realization_request
module I = Bioc_domain.Policy_implementation
module P = Bioc_domain.Pinned_identity
module A = Bioc_checker.Policy_admission
module C = Bioc_checker.Policy_realization_admission
module L = Bioc_compiler.Policy_lowering
module E = Bioc_semantics.Policy_execution

let require condition message = if not condition then failwith message
let str value = Json.String value
let arr value = Json.Array value
let obj value = Json.Object value
let get = O.get
let text = O.text
let items = O.list
let named identity values = List.find(fun value->text "id" value=identity)values
let rec at path value = match path,value with
  | [],_->value
  | key::rest,Json.Object _->at rest(get key value)
  | index::rest,Json.Array values->at rest(List.nth values(int_of_string index))
  | _->failwith "Test path is outside its literal source"
let rec set path replacement value = match path,value with
  | [],_->replacement
  | key::rest,Json.Object fields->
      require(List.mem_assoc key fields)("Missing test field "^key);
      obj(List.map(fun(name,value)->name,(if name=key then set rest replacement value else value))fields)
  | index::rest,Json.Array values->
      let index=int_of_string index in
      require(index>=0 && index<List.length values)"Invalid test array index";
      arr(List.mapi(fun i value->if i=index then set rest replacement value else value)values)
  | _->failwith "Mutation path is outside its literal source"
let append path value raw = set path (arr(Json.array(at path raw)@[value]))raw
let read path =
  let channel=open_in_bin path in
  Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
    let size=in_channel_length channel in
    require(size<=2*1024*1024)"Admission fixture exceeds its byte bound";
    Json.parse_bounded ~max_bytes:(2*1024*1024) ~max_nodes:100000(really_input_string channel size))
let controls=ref 0
let rejects label code action =
  incr controls;
  match action()with
  | _->failwith("Admission control accepted: "^label)
  | exception Diagnostic.Error diagnostic->require(diagnostic.code=code)
      (label^": wrong rejection "^diagnostic.code^", expected "^code)
let source_behavior request = L.lower(A.admit ~document:(R.document request) ~descriptors:(R.definitions request))
let fresh raw = let request=R.of_json raw in C.admit ~request ~behavior:(source_behavior request)
let reject_fresh label code raw = rejects label code(fun()->fresh raw)
let repin_entry raw =
  let entry=at ["document";"implementations";"implementations";"0"]raw in
  set ["catalog_bindings";"0";"entry_digest"](str(Canonical.fingerprint entry))raw
let check_scope report =
  require(text "status" report="admitted_inputs")"Input admission has been renamed accepted compilation";
  List.iter(fun(key,value)->require(text key report=value)("Admission upgraded "^key))
    ["exploration","not_performed";"preservation","unassessed";"requirements","unassessed";
     "target_status","unassessed";"material","unassessed";"export","withheld";"artifact","withheld"];
  require(List.mem(str "requested_assurance_not_established")
    (items "unresolved_obligations" (get "source_assessment" report)))"Admission erased original assurance obligation"

let () =
  require(Array.length Sys.argv=3)"Supply resolved realization request and unchanged original source fixture";
  let raw=read Sys.argv.(1)and original=read Sys.argv.(2)in
  let request=R.of_json raw in
  require(Json.equal(R.to_json request)raw)"Request decoder changed full external authority";
  require(R.fingerprint request=Canonical.fingerprint raw)"Request identity excludes authority fields";
  let behavior=source_behavior request in
  let admitted=C.admit ~request ~behavior in
  let report=C.report admitted in check_scope report;
  require(R.fingerprint(C.request admitted)=R.fingerprint request)"Admitted input lost original root";
  require(Json.equal(O.behavior_to_json(C.behavior admitted))(O.behavior_to_json behavior))"Admitted input replaced checked behavior";
  require(text "request_fingerprint" report=R.fingerprint request &&
    text "source_artifact_digest" report=D.artifact_digest(R.document request))"Admission lost full request/source pins";
  require(List.length(C.authorized_models admitted)=List.length(I.models(R.implementation_library request)))
    "Admission left library models unauthorized";
  List.iter(C.require_model admitted ~entry_id:"fixture.response.primitives")(C.authorized_models admitted);
  List.iter(fun path->require(Json.equal(at("document"::path)raw)(at("document"::path)original))
    "Resolved request weakened an original declaration or assurance")[["program";"declarations"];["assurance"];["deployment"]];
  require(items "implementations" (at["document";"implementations"]original)=[])
    "Original source-only fixture was silently resolved";
  require(D.artifact_digest(R.document request)<>D.artifact_digest(D.of_json(get "document" original)))
    "Resolved request retained an obsolete source identity";
  let uncertain=named "invalid_before_response" (items "timelines" original)in
  let execution=E.execute behavior(get "timeline" uncertain)in
  require(text "status" (named "scoped_memory" (items "requirements" execution))="unknown")
    "Admission weakened or proved the original uncertain hard property";
  check_scope(C.report admitted);

  let entry_path=["document";"implementations";"implementations";"0"]in
  let bridge_path=["catalog_bindings";"0"]in
  let assurance_path=["document";"assurance"]in
  let model_pin=List.hd(C.authorized_models admitted)in
  let zero=str(String.make 64 '0')in
  reject_fresh "original empty catalog cannot authorize supplied models" "policy_realization_catalog"
    (set ["document";"implementations";"implementations"](arr[])raw);
  reject_fresh "missing catalog bridge" "policy_realization_catalog" (set["catalog_bindings"](arr[])raw);
  reject_fresh "foreign catalog entry" "policy_realization_catalog" (set(bridge_path@["entry_id"])(str "absent")raw);
  reject_fresh "stale full entry digest" "policy_realization_catalog" (set(bridge_path@["entry_digest"])zero raw);
  reject_fresh "stale catalog entry version" "policy_realization_catalog" (set(bridge_path@["entry_version"])(str "2")raw);
  reject_fresh "same entry ID changed body" "policy_realization_catalog" (set(entry_path@["version"])(str "2")raw);
  reject_fresh "operation bridge substitution" "policy_realization_catalog"
    (set(bridge_path@["operation"])(at(bridge_path@["realization"])raw)raw);
  reject_fresh "realization bridge substitution" "policy_realization_catalog"
    (set(bridge_path@["realization"])(at(bridge_path@["operation"])raw)raw);
  rejects "duplicate bridge" "policy_realization_request" (fun()->R.of_json(append["catalog_bindings"](at bridge_path raw)raw));
  rejects "empty model authorization" "policy_realization_request" (fun()->R.of_json(set(bridge_path@["models"])(arr[])raw));
  rejects "duplicate model pin" "policy_realization_request"
    (fun()->R.of_json(append(bridge_path@["models"])(P.to_json model_pin)raw));
  reject_fresh "foreign supplied model" "policy_realization_model"
    (set(bridge_path@["models";"0";"id"])(str "foreign.model")raw);
  reject_fresh "same model ID changed fingerprint" "policy_realization_model"
    (set(bridge_path@["models";"0";"content_fingerprint"])zero raw);
  reject_fresh "unaccounted library alternative" "policy_realization_model"
    (set(bridge_path@["models"])(arr(List.tl(Json.array(at(bridge_path@["models"])raw))))raw);
  rejects "model authorization is entry scoped" "policy_realization_model"
    (fun()->C.require_model admitted ~entry_id:"absent" model_pin);
  let foreign=P.make ~kind:P.Model ~id:"foreign.model" ~version:"1"
    ~content_fingerprint:(String.make 64 '0')in
  rejects "future candidate cannot select foreign model" "policy_realization_model"
    (fun()->C.require_model admitted ~entry_id:"fixture.response.primitives" foreign);
  let library_models=items "models" (get "implementation_library" raw)in
  let attempt_index=List.find(fun(_,value)->text "primitive" (get "body" value)="attempt_bank")
    (List.mapi(fun i value->i,value)library_models)|>fst|>string_of_int in
  let model_path=["implementation_library";"models";attempt_index]in
  let alternative=set(model_path@["body";"configuration";"on_unknown"])(str "continue")raw in
  let alternative=set(model_path@["configuration_digest"])
    (str(Canonical.fingerprint(at(model_path@["body";"configuration"])alternative)))alternative in
  let alternative=set(model_path@["identity";"content_fingerprint"])
    (str(Canonical.fingerprint(at(model_path@["body"])alternative)))alternative in
  reject_fresh "self-consistent model edit lacks original membership" "policy_realization_model" alternative;
  let new_pin=at(model_path@["identity"])alternative in
  let alternative=set(bridge_path@["models";attempt_index])new_pin alternative in
  let alternate_request=R.of_json alternative in
  require(R.fingerprint alternate_request<>R.fingerprint request)"Fresh model authorization reused old root identity";
  (* Explicitly authorizing another model is a new input, not a demonstration
     that its changed uncertainty semantics preserves the original source. *)
  check_scope(C.report(C.admit ~request:alternate_request ~behavior));
  reject_fresh "wrong original chassis" "policy_realization_chassis"
    (repin_entry(set(entry_path@["chassis"])(arr[str "another.chassis"])raw));
  reject_fresh "absent RNA authorization" "policy_realization_chassis"
    (repin_entry(set(entry_path@["payload_formats"])(arr[])raw));
  reject_fresh "duplicate RNA authorization" "policy_realization_chassis"
    (repin_entry(set(entry_path@["payload_formats"])(arr[str "RNA";str "RNA"])raw));
  List.iter(fun key->
    let pinned=repin_entry(set(entry_path@[key])(arr[at(bridge_path@["realization"])raw])raw)in
    reject_fresh("unsupported "^key^" closure")"policy_realization_unsupported" pinned;
    let stale=repin_entry(set(entry_path@[key;"0";"digest"])zero pinned)in
    rejects("stale "^key^" definition")"policy_operational_source_invalid"
      (fun()->C.admit ~request:(R.of_json stale) ~behavior)) ["dependencies";"evidence"];

  List.iter(fun level->reject_fresh("stronger/different assurance "^level)"policy_realization_assurance"
    (set(assurance_path@["level"])(str level)raw))["proof";"structural"];
  let referenced_horizon=set(assurance_path@["horizon";"unit";"reference"])
    (str "recipient-relative-time")raw in
  let referenced_request=R.of_json referenced_horizon in
  require(text "status"(Bioc_checker.Policy_check.check(R.document referenced_request))="valid")
    "Nominal assurance time-reference control lost generic source validity";
  require(R.fingerprint referenced_request<>R.fingerprint request)
    "Original assurance reference failed to change the complete request pin";
  reject_fresh "nominal assurance time reference" "policy_operational_unsupported" referenced_horizon;
  rejects "old behavior cannot admit a referenced original assurance horizon" "policy_operational_unsupported"
    (fun()->C.admit ~request:referenced_request ~behavior);
  let milliseconds=raw |> set(assurance_path@["horizon";"amount"])(str "4000")
    |>set(assurance_path@["horizon";"unit";"id"])(str "ms")
    |>set(assurance_path@["horizon";"unit";"scale"])(str "0.001")in
  let millisecond_admitted=fresh milliseconds in
  check_scope(C.report millisecond_admitted);
  require(Json.equal(R.to_json(C.request millisecond_admitted))milliseconds &&
    R.fingerprint(C.request millisecond_admitted)<>R.fingerprint request)
    "Equivalent assurance units lost their complete original spelling or identity";
  reject_fresh "unbounded assurance" "policy_realization_assurance"
    (set(assurance_path@["horizon"])(str "unbounded_requested")raw);
  List.iter(fun amount->reject_fresh("assurance horizon "^amount)"policy_realization_assurance"
    (set(assurance_path@["horizon";"amount"])(str amount)raw))["3";"5";"4.5"];
  reject_fresh "producer shortened domain" "policy_realization_assurance"
    (set["operating_domain";"horizon_ticks"](Json.int 3)raw);
  reject_fresh "producer omitted hard requirement" "policy_realization_assurance"
    (set(assurance_path@["requirements"])(arr[str "request_progress";str "initiation_progress";str "request_authorization"])raw);
  rejects "unknown requested requirement" "policy_operational_source_invalid"
    (fun()->C.admit ~request:(R.of_json(append(assurance_path@["requirements"])(str "absent")raw)) ~behavior);
  rejects "duplicate requested requirement" "policy_operational_source_invalid"
    (fun()->C.admit ~request:(R.of_json(append(assurance_path@["requirements"])(str "scoped_memory")raw)) ~behavior);
  reject_fresh "new assurance premise" "policy_realization_assurance"
    (set(assurance_path@["assumptions"])(arr[str "every requested attempt completes"])raw);
  let condition=at["document";"program";"declarations";"10";"condition"]raw in
  reject_fresh "new tolerance" "policy_realization_assurance"
    (set(assurance_path@["tolerances"])(arr[obj["$type",str "Argument";"name",str "latency";"value",condition]])raw);

  let declarations=items "declarations" (at["document";"program"]raw)in
  let requirement_index=List.find(fun(_,value)->text "id" value="scoped_memory")(List.mapi(fun i value->i,value)declarations)|>fst|>string_of_int in
  reject_fresh "shorter individual hard horizon" "policy_realization_assurance"
    (set["document";"program";"declarations";requirement_index;"horizon";"amount"](str "3")raw);
  let changed_map=set["document";"program";"source_map";"0";"file"](str "independent_changed_location.py")raw in
  let new_request=R.of_json changed_map in
  require(D.fingerprint(R.document new_request)=D.fingerprint(R.document request))"Metadata-only source edit changed semantic document identity";
  require(D.artifact_digest(R.document new_request)<>D.artifact_digest(R.document request) &&
    R.fingerprint new_request<>R.fingerprint request)"Metadata edit failed full authority invalidation";
  rejects "old behavior after source map edit" "policy_correspondence" (fun()->C.admit ~request:new_request ~behavior);
  check_scope(C.report(fresh changed_map));
  let changed_budget=set["budgets";"max_prefixes"](Json.int 1)raw in
  let budget_request=R.of_json changed_budget in
  require(R.fingerprint budget_request<>R.fingerprint request)"Budget edit escaped root identity";
  check_scope(C.report(C.admit ~request:budget_request ~behavior));
  let tiny=R.budgets budget_request in require(tiny.max_prefixes=1)"Decoder silently increased requested traversal budget";
  let changed_behavior=O.behavior_to_json behavior |> set["nodes";"4";"data";"freshness";"amount"](str "1") |> O.behavior_of_json in
  rejects "tampered separately supplied behavior" "policy_correspondence" (fun()->C.admit ~request ~behavior:changed_behavior);
  reject_fresh "wrong domain executor" "policy_domain_source"
    (set["operating_domain";"executor";"role"](str "foreign.executor")raw);
  rejects "stale descriptor reference" "policy_operational_unsupported"
    (fun()->C.admit ~request:(R.of_json(set["definitions";"definitions";"0";"definition";"digest"]zero raw)) ~behavior);

  rejects "bare source program" "policy_realization_request"
    (fun()->R.of_json(set["document"](at["document";"program"]raw)raw));
  rejects "embedded candidate is not authority" "unknown_field"
    (fun()->R.of_json(obj(Json.object_fields raw@["candidate",O.behavior_to_json behavior])));
  rejects "serialized admission cannot reconstruct authority" "missing_field" (fun()->R.of_json report);
  rejects "unknown request profile" "policy_realization_request"
    (fun()->R.of_json(set["profile"](str "future")raw));
  rejects "duplicate native object key" "policy_document"
    (fun()->R.of_json(obj(Json.object_fields raw@["profile",str R.profile])));
  rejects "raw float in traversal budget" "policy_document"
    (fun()->R.of_json(set["budgets";"max_work"](Json.Float 1.)raw));
  rejects "Boolean is not integer budget" "invalid_type"
    (fun()->R.of_json(set["budgets";"max_work"](Json.Bool true)raw));
  rejects "unbounded traversal budget" "policy_realization_request"
    (fun()->R.of_json(set["budgets";"max_work"](Json.int 100_000_001)raw));
  rejects "zero traversal budget" "policy_realization_request"
    (fun()->R.of_json(set["budgets";"max_trace_items"](Json.int 0)raw));
  rejects "oversized native integer" "policy_document_limit"
    (fun()->R.of_json(set["budgets";"max_work"](Json.Int(Z.shift_left Z.one 2000))raw));
  let rec cyclic = Json.Null::cyclic in
  rejects "native cyclic array is bounded before decoding" "policy_document_limit"
    (fun()->R.of_json(set["catalog_bindings"](arr cyclic)raw));
  (* 45 literal controls plus 4 dependency/evidence, 2 assurance-level and
     3 horizon controls. The former 52 omitted the added nominal assurance
     reference and old-behavior/reference rejection controls. *)
  require(!controls=54)("Admission negative-control inventory changed: expected 54, received "^string_of_int !controls);
  print_endline("Source/domain/model inputs admitted with "^string_of_int !controls^
    " rejection controls; preservation, hard requirements, material and export remain unestablished")
