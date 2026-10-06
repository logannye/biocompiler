open Bioc_wire
let ()=Printexc.register_printer(function
  |Diagnostic.Error value->Some(Printf.sprintf "Diagnostic.Error(code=%s, path=%s, message=%s)"
    value.code(Option.value ~default:"<none>" value.path)value.message)
  |_->None)
module R=Bioc_domain.Policy_material_request
module S=Bioc_domain.Policy_realization_request
module D=Bioc_domain.Policy_document
module O=Bioc_domain.Policy_operational
module I=Bioc_domain.Policy_implementation
module U=Bioc_domain.Policy_implementation_binding
module C=Bioc_domain.Policy_material_contract
module K=Bioc_domain.Construction_content
module P=Bioc_realization_checker.Policy_preservation_check
module L=Bioc_realization_checker.Policy_material_binding_check
module X=Bioc_realization_checker.Policy_material_context_check
module Check=Bioc_realization_checker.Policy_material_check
module W=Bioc_checker.Work_budget
let checks=ref 0
let require condition message=incr checks;if not condition then failwith message
let str value=Json.String value
let obj values=Json.Object values
let arr values=Json.Array values
let get key raw=Json.field key(Json.object_fields raw)
let text key raw=Json.string(get key raw)
let items key raw=Json.array(get key raw)
let set key value raw=obj((key,value)::List.remove_assoc key(Json.object_fields raw))
let rec at path raw=match path with []->raw|key::rest->at rest(match raw with
  |Json.Array values->List.nth values(int_of_string key)|_->get key raw)
let rec edit path change raw=match path with []->change raw|key::rest->match raw with
  |Json.Array values->let index=int_of_string key in
      require(index>=0 && index<List.length values)"Mutation escaped literal array";
      arr(List.mapi(fun i value->if i=index then edit rest change value else value)values)
  |_->set key(edit rest change(get key raw))raw
let put path value raw=edit path(fun _->value)raw
let append value raw=arr(Json.array raw@[value])
let rejected code run=incr checks;match run()with
  |_->failwith("Expected diagnostic "^code)
  |exception Diagnostic.Error value->require(value.code=code)("Expected "^code^", received "^value.code)
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:4000000 ~max_nodes:100000(really_input_string channel(in_channel_length channel)))
let lower request=
  let original=R.implementation_request request in
  Bioc_compiler.Policy_lowering.lower(Bioc_checker.Policy_admission.admit
    ~document:(S.document original) ~descriptors:(S.definitions original))
let source_obligations request=
  let original=R.implementation_request request in
  items "unresolved_obligations"(Bioc_checker.Policy_check.check(S.document original))
let repin_source request parts=
  let original=R.implementation_request request in
  parts|>put["implementation";"authority";"source_artifact_digest"](str(D.artifact_digest(S.document original)))
    |>put["implementation";"authority";"descriptors_digest"](str(O.descriptors_digest(S.definitions original)))
let ()=
  require(Array.length Sys.argv=2)"Supply complete original material request fixture";
  let fixture=read Sys.argv.(1)in
  let raw=get "request" fixture and parts=get "candidate_parts" fixture and expected=get "expected" fixture in
  let request=R.of_json raw and limits=P.limits_of_json(get "limits" fixture)in
  let behavior=lower request in
  let implementation parts request=I.of_json ~library:(S.implementation_library(R.implementation_request request))
    (get "implementation" parts)in
  let run ?(request=request) ?(parts=parts) ?(behavior=behavior) ?(limits=limits) ()=
    Check.check ~request ~behavior ~implementation:(implementation parts request)
      ~proposed:(U.of_json(get "binding" parts)) ~material_binding:(C.proposal_of_json(get "material_binding" parts))
      ~candidate:(K.of_json(get "construction" parts)) ~limits in
  let candidate_raw=obj["schema_version",str Check.candidate_schema;"behavior",O.behavior_to_json behavior;
    "implementation",get "implementation" parts;"binding",get "binding" parts;
    "material_binding",get "material_binding" parts;"construction",get "construction" parts]in
  require(Json.equal(R.to_json request)raw)"Material request codec changed full original authority";
  require(str(R.fingerprint request)=get "request_fingerprint" expected)"Frozen complete original request changed";
  require(str(S.fingerprint(R.implementation_request request))=get "source_request_digest" expected)
    "Material request substituted a different source/domain/library root";
  require(source_obligations request=items "obligations" expected)"Literal 24-obligation original census changed";
  let decoded_work=ref 0 in
  let charged_request=R.of_json ~charge:(fun amount->decoded_work:= !decoded_work+amount)raw in
  require(!decoded_work=R.decoding_work charged_request && !decoded_work=R.decoding_work request && !decoded_work>0)
    "Original decoding work is absent, callback-dependent or incorrectly retained";
  require(Json.int !decoded_work=get "request_decoding_work" expected)
    "Independent complete-original logical decoder census changed";
  require(R.fingerprint charged_request=R.fingerprint request)"Count callback changed original authority";
  let exact_decoder=W.create ~profile:"test" ~error_code:"test_original_decode" ~maximum:480657 ()in
  ignore(R.of_json ~charge:(W.charge exact_decoder)raw);
  require(W.remaining exact_decoder=0)"Exact original decoding allowance was not fully charged";
  let short_decoder=W.create ~profile:"test" ~error_code:"test_original_decode" ~maximum:480656 ()in
  rejected "test_original_decode"(fun()->R.of_json ~charge:(W.charge short_decoder)raw);
  let positive=run()in
  let report=Check.report positive in
  require(text "status" report="checked_material")("Complete conditional conjunction failed: "^Canonical.encode report);
  let accepted=match Check.accepted positive with Some value->value|None->failwith "Conjunction lacks private accepted value"in
  require(R.fingerprint(Check.request accepted)=R.fingerprint request && Json.equal(Check.evidence accepted)report)
    "Private acceptance detached from exact original request or evidence";
  List.iter(fun key->require(get key report=get key expected)("Conditional claim changed: "^key))
    ["status";"claim_scope";"material_status";"context_status";"empirical";"artifact";"export"];
  require(get "all_original_obligations_discharged" report=Json.Bool true)"Private acceptance omitted an original obligation";
  require(List.map(get "obligation")(items "obligations" report)=items "obligations" expected)
    "Coordinator replaced the original obligation inventory";
  require(List.for_all(fun row->text "status" row="discharged" && get "evidence" row<>Json.Null)(items "obligations" report))
    "Original obligation is falsely discharged without evidence";
  let preservation=get "preservation" report in
  List.iter(fun key->require(at["coverage";key]preservation=get key expected)("Independent finite census changed: "^key))
    ["histories";"transitions";"prefixes_started"];
  require(List.for_all(fun row->text "status" row="pass")(items "requirements" preservation))
    "Accepted conjunction failed to retain every passing original requirement";
  require(get "candidate_fingerprint" report=str(Canonical.fingerprint candidate_raw))
    "Material candidate identity omits the schema or a complete candidate part";
  require(get "invocation_fingerprint" report=str(Canonical.fingerprint(obj["request",raw;"candidate",candidate_raw;
    "limits",get "limits" fixture])))"Invocation identity omits original request, full candidate or limits";
  let content=Bioc_checker.Policy_mrna_structure_check.content(L.structure(X.binding(Check.context accepted)))in
  let actual_molecules=at["inventory";"molecules"](K.to_json content)in
  require(Json.equal actual_molecules(get "molecules" expected))"Private accepted content differs from independent full molecular literal";
  require(at["0";"sequence"]actual_molecules=get "sequence" expected)"Exact RNA spelling differs from independent literal";
  require(text "unit"(get "usage" report)="logical_data_visits_and_child_semantic_work")"Misstated work unit";
  let total=Z.to_int(Json.integer(at["usage";"charged_work"]report))in
  require(total> !decoded_work && total<=(R.budgets request).max_work &&
    at["usage";"request_decoding_work"]report=Json.int !decoded_work)"Aggregate omitted original parsing or exceeded allowance";
  (* The startup hook supplements, but never changes, the original preservation
     report. Its callback sees immutable external roots and cannot skip checks. *)
  let original=R.implementation_request request in
  let invoke_preservation check=check ~request:original ~behavior ~implementation:(implementation parts request)
    ~proposed:(U.of_json(get "binding" parts)) ~limits in
  let phases=ref []in
  let hooked=invoke_preservation(P.check_with_startup_charge ~startup_charge:(fun phase value->
    phases:=phase:: !phases;ignore(R.preflight ~charge:(fun _->())value)))in
  require(List.length(List.filter((=)P.Input)!phases)=6 && List.length(List.filter((=)P.Identity)!phases)=3)
    "Startup admission/initialization/identity pass inventory changed";
  require(Json.equal(P.report hooked)preservation && Json.equal(P.report(invoke_preservation P.check))preservation)
    "Startup accounting changed default preservation evidence";
  rejected "test_startup_budget"(fun()->invoke_preservation(P.check_with_startup_charge
    ~startup_charge:(fun _ _->Diagnostic.fail "test_startup_budget" "No original admission allowance")));
  (* Literal accounting includes distinct keys, values, edges, ancestors and
     scalar bytes. Escaped bytes affect publication size, not source string size. *)
  let tiny=obj["a",arr[Json.Bool true;Json.int 12;str "x\n"]]in
  let exact=W.create ~profile:"test" ~error_code:"test_preflight" ~maximum:16 ()in
  require(R.preflight ~charge:(W.charge exact)tiny=21 && W.remaining exact=0)
    "Literal logical-work/canonical-byte census changed";
  let short=W.create ~profile:"test" ~error_code:"test_preflight" ~maximum:15 ()in
  rejected "test_preflight"(fun()->R.preflight ~charge:(W.charge short)tiny);
  rejected "policy_material_input_limit"(fun()->R.preflight ~max_nodes:1 ~charge:(fun _->())tiny);
  let rec cycle=Json.Array[cycle]in
  rejected "policy_material_input_limit"(fun()->R.preflight ~charge:(fun _->())cycle);
  let no_work=W.create ~profile:"test" ~error_code:"test_original_decode" ~maximum:0 ()in
  rejected "test_original_decode"(fun()->R.of_json ~charge:(W.charge no_work)raw);
  List.iter(fun maximum->rejected "policy_material_work_limit"(fun()->run
    ~request:(R.of_json(put["budgets";"max_work"](Json.int maximum)raw))()))[1;!decoded_work-1];
  List.iter(fun field->rejected "policy_material_publication_limit"(fun()->run
    ~request:(R.of_json(put["budgets";field](Json.int 1)raw))()))["max_report_bytes";"max_report_nodes"];
  let smaller_budget=R.of_json(put["budgets";"max_work"](Json.int 499999999)raw)in
  let smaller=run ~request:smaller_budget ()in
  require(Option.is_some(Check.accepted smaller) &&
    get "request_fingerprint"(Check.report smaller)<>get "request_fingerprint" report &&
    get "invocation_fingerprint"(Check.report smaller)<>get "invocation_fingerprint" report)
    "Edited original work budget reused old acceptance identity";
  (* A forged, rehashed report is merely data. No constructor accepts it; fresh
     evaluation ignores it and a request cannot carry it as hidden authority. *)
  let forged=report|>set "export"(str "released")|>set "empirical"(str "validated")in
  let forged=obj["report",forged;"report_fingerprint",str(Canonical.fingerprint forged)]in
  rejected "unknown_field"(fun()->R.of_json(set "saved_report" forged raw));
  require(Json.equal(Check.report(run()))report)"Saved/rehashable data contaminated fresh evaluation";
  let guard=items "wires"(get "implementation" parts)|>List.find(fun wire->
    at["consumer";"node"]wire=str "exclude_gate" && at["consumer";"port"]wire=str "guard")|>get "producer"in
  let wrong_guard=edit["implementation";"wires"](fun values->arr(List.map(fun wire->
    if at["consumer";"node"]wire=str "select_gate" && at["consumer";"port"]wire=str "guard"
    then set "producer" guard wire else wire)(Json.array values)))parts in
  rejected "policy_implementation_source_binding"(fun()->run ~parts:wrong_guard ());
  let changed_source=R.of_json(put["implementation_request";"document";"program";"source_map";"0";"file"]
    (str "different_original_source.py")raw)in
  rejected "policy_correspondence"(fun()->run ~request:changed_source ());
  let wrong_bridge=R.of_json(put["catalog_binding";"entry_digest"](str(String.make 64 '0'))raw)in
  rejected "policy_material_catalog_binding"(fun()->run ~request:wrong_bridge ());
  let no_accept label ?(all_unresolved=true) request result=
    let report=Check.report result in
    require(Check.accepted result=None && text "status" report="not_accepted" &&
      get "all_original_obligations_discharged" report=Json.Bool false)(label^" produced private acceptance");
    let ledger=items "obligations" report in
    require(List.map(get "obligation")ledger=source_obligations request)(label^" dropped original obligations");
    if all_unresolved then require(List.for_all(fun row->text "status" row="unresolved" && get "evidence" row=Json.Null)ledger)
      (label^" converted a failed stage into discharge");
    require(get "artifact" report=str "withheld" && get "export" report=str "withheld" && get "empirical" report=str "unassessed")
      (label^" widened its claim");report in
  let tiny_monitor=P.limits_of_json(put["monitor";"max_work"](Json.int 1)(get "limits" fixture))in
  let monitor_incomplete=no_accept "Insufficient monitor startup work" request(run ~limits:tiny_monitor ())in
  require(at["preservation";"status"]monitor_incomplete=str "incomplete" &&
    at["preservation";"coverage";"histories"]monitor_incomplete=Json.int 0 &&
    get "material_status" monitor_incomplete=str "unassessed")
    "Tiny monitor budget generated complete or accepted material evidence";
  let wrong_sequence=put["construction";"inventory";"molecules";"0";"sequence"](str "GCAUGGCUUAAGGAAAA")parts in
  let wrong_sequence=put["construction";"inventory";"role_instances";"0";"subject_fingerprint"]
    (str(Canonical.fingerprint(at["construction";"inventory";"molecules";"0"]wrong_sequence)))wrong_sequence in
  let material_failed=no_accept "Edited exact bases" request(run ~parts:wrong_sequence ())in
  require(get "material_status" material_failed=str "fail" && get "context_status" material_failed=str "unassessed")
    "Bad exact material incorrectly ran context acceptance";
  let wrong_context=R.of_json(put["context";"recipient";"identity"](str "target-1")raw)in
  let context_failed=no_accept "Wrong concrete recipient" wrong_context(run ~request:wrong_context ())in
  require(get "material_status" context_failed=str "pass" && get "context_status" context_failed=str "fail")
    "Recipient mismatch escaped independent context checking";
  (* Add a new hard UNKNOWN property without weakening any original requirement
     or narrowing the supplied input domain. New source occurrences are literal. *)
  let declarations=at["implementation_request";"document";"program";"declarations"]raw|>Json.array in
  let unknown=get "condition"(List.nth declarations 11)|>set "value"(str "unknown")in
  let extra=List.nth declarations 13|>set "id"(str "unresolved_truth")|>set "condition" unknown
    |>set "description"(str "Additional hard UNKNOWN control; every original property remains required.")in
  let span=at["implementation_request";"document";"program";"source_map";"0"]raw
    |>set "declaration_id"(str "unresolved_truth")|>set "line"(Json.int 1000)in
  let unknown_raw=raw
    |>edit["implementation_request";"document";"program";"declarations"](append extra)
    |>edit["implementation_request";"document";"program";"source_map"](append span)
    |>edit["implementation_request";"document";"assurance";"requirements"](append(str "unresolved_truth"))in
  let unknown_request=R.of_json unknown_raw in
  let path="/document/program/declarations/"^string_of_int(List.length declarations)in
  let occurrence path=obj["source_path",str path;"role",str "requirement";"disposition",str "obligation";"targets",arr[]]in
  let unknown_parts=repin_source unknown_request parts|>edit["implementation";"occurrences"](fun values->
    arr(List.sort(fun a b->String.compare(text "source_path" a)(text "source_path" b))
      (Json.array values@[occurrence path;occurrence(path^"/condition")])))in
  let unknown_report=no_accept "Additional UNKNOWN hard requirement" unknown_request
    (run ~request:unknown_request ~parts:unknown_parts ~behavior:(lower unknown_request)())in
  require(at["preservation";"status"]unknown_report=str "requirements_not_satisfied" &&
    get "material_status" unknown_report=str "unassessed" && get "context_status" unknown_report=str "unassessed")
    "UNKNOWN hard source property crossed material acceptance";
  let unknown_row=List.find(fun row->text "id" row="unresolved_truth")
    (items "requirements"(get "preservation" unknown_report))in
  require(text "status" unknown_row="unknown")"UNKNOWN source truth was silently made false or proven true";
  let false_request=R.of_json(put["implementation_request";"document";"program";"declarations";
    string_of_int(List.length declarations);"condition";"value"](Json.Bool false)unknown_raw)in
  let false_report=no_accept "Additional false hard requirement" false_request
    (run ~request:false_request ~parts:(repin_source false_request unknown_parts) ~behavior:(lower false_request)())in
  let false_row=List.find(fun row->text "id" row="unresolved_truth")
    (items "requirements"(get "preservation" false_report))in
  require(text "status" false_row="fail" && get "material_status" false_report=str "unassessed")
    "False original hard requirement crossed material acceptance";
  (* An additional original definition has no executable interpretation or
     declared provider. Even with three passing leaves its obligation is open. *)
  let definition=at["implementation_request";"document";"program";"semantics";"definitions";"0"]raw
    |>set "id"(str "extra.unresolved")|>set "meaning"(str "Uninterpreted supplied definition; no provider or material discharge.")in
  let extra_request=R.of_json(edit["implementation_request";"document";"program";"semantics";"definitions"](append definition)raw)in
  let extra_report=no_accept "Unrecognized original semantic obligation" ~all_unresolved:false extra_request
    (run ~request:extra_request ~parts:(repin_source extra_request parts) ~behavior:(lower extra_request)())in
  require(get "material_status" extra_report=str "pass" && get "context_status" extra_report=str "pass")
    "Unrecognized-obligation control did not reach the complete conjunction";
  let pending=List.filter(fun row->text "status" row="unresolved")(items "obligations" extra_report)in
  require(List.map(get "obligation")pending=[str "semantic_definition:extra.unresolved"])
    "Unknown semantic definition was discarded, or changed unrelated discharges";
  Printf.printf "policy material coordinator: %d literal, full-authority and bounded-accounting checks\n" !checks
