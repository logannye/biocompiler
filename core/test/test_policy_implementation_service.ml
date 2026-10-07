open Bioc_wire
module S = Bioc_service.Policy_implementation_service
module Service = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service
let require condition message=if not condition then failwith message
let obj fields=Json.Object fields
let arr values=Json.Array values
let str value=Json.String value
let get name value=Json.field name(Json.object_fields value)
let text name value=Json.string(get name value)
let items name value=Json.array(get name value)
let replace key replacement value=obj(List.map(fun(name,item)->name,if name=key then replacement else item)(Json.object_fields value))
let rec set path replacement value=match path,value with
  |[],_->replacement
  |key::rest,Json.Object fields->require(List.mem_assoc key fields)("Absent field "^key);
      obj(List.map(fun(name,item)->name,if name=key then set rest replacement item else item)fields)
  |index::rest,Json.Array values->arr(List.mapi(fun i item->if i=int_of_string index then set rest replacement item else item)values)
  |_->failwith "Mutation outside literal fixture"
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:(4*1024*1024) ~max_nodes:200000(really_input_string channel(in_channel_length channel)))
let rejects label codes action=match action()with
  |_->failwith("Service accepted "^label)
  |exception Diagnostic.Error diagnostic->require(List.mem diagnostic.code codes)(label^": wrong diagnostic "^diagnostic.code)
let run handler role operation payload=
  let request:Protocol.request={request_id="implementation-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_->failwith "Registered implementation operation failed"
let ()=
  require(Array.length Sys.argv=2)"Supply independently authored policy implementation request fixture";
  let fixture=read Sys.argv.(1)in
  require(text "schema_version" fixture="biocompiler.policy_implementation_request_fixture.v0.1")"Wrong source fixture profile";
  let request=get "request" fixture and limits=get "limits" fixture in
  let compiled=run Producer.handle Protocol.Core "compile-policy-implementation"(obj["request",request;"limits",limits])in
  let candidate=get "candidate" compiled in
  let payload=obj["request",request;"candidate",candidate;"limits",limits]in
  let checked=run Service.handle Protocol.Verify "check-policy-implementation"payload in
  require(Json.equal checked compiled)"Producer and standalone service changed complete evidence";
  require(Json.equal checked(run Producer.handle Protocol.Core "check-policy-implementation"payload))
    "Core and standalone Verify checking changed complete evidence";
  require(text "request_fingerprint" compiled=Canonical.fingerprint request)"Request identity is not the original full envelope";
  require(text "candidate_fingerprint" compiled=Canonical.fingerprint candidate)"Candidate identity omitted a stage";
  require(text "invocation_fingerprint" compiled=Canonical.fingerprint payload)"Invocation omitted candidate or limits";
  let report=get "report" compiled in
  require(text "report_fingerprint" compiled=Canonical.fingerprint report)"Evidence fingerprint mismatch";
  require(text "status" report="checked_implementation")"Small complete exclusion domain failed fresh acceptance";
  let coverage=get "coverage" report in
  require(get "histories" coverage=Json.int 9 && get "transitions" coverage=Json.int 47 &&
    get "prefixes_started" coverage=Json.int 48)"Service changed independent nine-history census";
  List.iter(fun(id,expected)->let row=List.find(fun row->text "id" row=id)(items "requirements" report)in
    require(Json.equal(get "status" row)expected)("Service changed original hard requirement "^id))
    (Json.object_fields(get "requirements"(get "expected" fixture)));
  List.iter(fun(key,expected)->require(text key report=expected)("Service promoted "^key))[
    "material","unassessed";"target_status","unassessed";"artifact","withheld";"export","withheld"];
  let replay saved=run Service.handle Protocol.Verify "replay-policy-implementation"
    (obj(Json.object_fields payload@["report",saved]))in
  require(Json.equal compiled(replay compiled))"Full-wrapper replay changed fresh evidence";
  List.iter(fun(label,forged)->rejects label["policy_implementation_replay"](fun()->replay forged))[
    "inner report used as wrapper",report;
    "wrapper implementation",replace "implementation"(str "foreign")compiled;
    "wrapper invocation",replace "invocation_fingerprint"(str(String.make 64 '0'))compiled;
    "rehash changed evidence",(let changed=replace "material"(str "produced")report in
      compiled|>replace "report"changed|>replace "report_fingerprint"(str(Canonical.fingerprint changed)));
    "Boolean/integer evidence",set["report";"coverage";"complete"](Json.int 1)compiled];
  rejects "unexpected producer payload authority" ["unknown_field"]
    (fun()->run Producer.handle Protocol.Core "compile-policy-implementation"(obj["request",request;"limits",limits;"candidate",candidate]));
  rejects "producer operation in verifier service" ["unsupported_operation"]
    (fun()->S.handle ~operation:"compile-policy-implementation"(obj["request",request;"limits",limits]));
  let producer_request:Protocol.request={request_id="verify-producer-control";operation="compile-policy-implementation";
    payload=obj["request",request;"limits",limits]}in
  (match Service.handle Protocol.Verify producer_request with
   |Protocol.Unsupported,None,_::_->()
   |_->failwith "Standalone Verify acquired implementation producer authority");
  let capabilities=run Service.handle Protocol.Verify "capabilities"(obj[])in
  require(Json.equal(get "policy_implementation"(get "profiles" capabilities))S.profile)"Missing exact checker capability profile";
  require(not(List.mem_assoc "policy_implementation_producer"(Json.object_fields(get "profiles" capabilities))))
    "Standalone Verify advertises production";
  let limited=set["budgets";"max_prefixes"](Json.int 1)request in
  let incomplete=S.check ~request:limited ~candidate ~limits in
  require(text "status"(get "report" incomplete)="incomplete" &&
    text "assurance"(get "report" incomplete)="not_established")"Resource exhaustion acquired acceptance";
  rejects "old wrapper under new original budget" ["policy_implementation_replay"](fun()->
    S.handle ~operation:"replay-policy-implementation"(obj["request",limited;"candidate",candidate;"limits",limits;"report",compiled]));
  rejects "changed source metadata" ["policy_correspondence"](fun()->
    S.check ~request:(set["document";"program";"source_map";"0";"file"](str "other.py")request) ~candidate ~limits);
  let altered=set["implementation";"authority";"domain_digest"](str(String.make 64 '0'))candidate in
  rejects "altered actual graph authority" ["policy_implementation_contract"](fun()->S.check ~request ~candidate:altered ~limits);
  let unknown_request=get "request"(get "unknown_control" fixture)in
  let unknown=run Producer.handle Protocol.Core "compile-policy-implementation"(obj["request",unknown_request;"limits",limits])in
  let unknown_report=get "report" unknown in
  require(text "status" unknown_report="requirements_not_satisfied" && text "preservation" unknown_report="pass")
    "Original UNKNOWN safety was promoted or mistaken for behavior divergence";
  let unknown_rows=items "requirements" unknown_report in
  require(text "status"(List.find(fun row->text "id" row="scoped_memory")unknown_rows)="unknown")
    "Original unknown hard property disappeared";
  let unknown_checked=run Service.handle Protocol.Verify "check-policy-implementation"
    (obj["request",unknown_request;"candidate",get "candidate" unknown;"limits",limits])in
  require(Json.equal unknown unknown_checked)"Original UNKNOWN control changed through standalone verification";
  rejects "whole wrapper nodes" ["policy_implementation_publication_limit"](fun()->
    S.validate_publication(arr(List.init Limits.max_json_nodes(fun _->Json.Null))));
  rejects "whole wrapper bytes" ["policy_implementation_publication_limit"](fun()->
    S.validate_publication(str(String.make(9*1024*1024)'x')));
  let nested=List.fold_left(fun value _->arr[value])Json.Null(List.init 129 Fun.id)in
  rejects "whole wrapper depth" ["policy_implementation_publication_limit"](fun()->S.validate_publication nested);
  print_endline "Policy implementation compile/check/full-wrapper replay: original authority and bounded publication controls; no material export."
