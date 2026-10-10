open Bioc_wire
module Contract=Bioc_domain.Policy_approximation_contract
module Check=Bioc_realization_checker.Policy_approximation_check
module Material=Bioc_service.Policy_component_material_service
module MC=Bioc_realization_checker.Policy_component_material_check
module Outcome=Bioc_domain.Construction_assessment
module Producer=Bioc_producer_service.Producer_service
module W=Bioc_checker.Work_budget
let s value=Json.String value
let o fields=Json.Object fields
let a values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let rows key value=Json.array(get key value)
let rec at path value=match path with []->value|key::rest->at rest(get key value)
let set key item value=o(List.map(fun(name,value)->name,if name=key then item else value)(Json.object_fields value))
let rec edit path f value=match path with []->f value|key::rest->set key(edit rest f(get key value))value
let require condition message=if not condition then failwith message
let accepted label=function Some value->value|None->failwith(label^" withheld its private capability")
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_artifact ~max_bytes:(8*1024*1024) ~max_nodes:400000(really_input_string channel(in_channel_length channel)))
let call operation payload=
  let request:Protocol.request={request_id="approximation-literal";operation;payload}in
  match Producer.handle Protocol.Core request with
  |Protocol.Ok,Some result,[]->result
  |_,_,diagnostics->failwith(operation^": "^String.concat "; "(List.map(fun(d:Diagnostic.t)->d.code^": "^d.message)diagnostics))
let controls=ref 0
let rejects label action=match action()with
  |_->failwith("Approximation malformed original accepted: "^label)
  |exception Diagnostic.Error _->incr controls
let first f=edit["links"](fun values->match Json.array values with first::rest->a(f first::rest)|_->assert false)
let rational unit n=o["numerator",s(string_of_int n);"denominator",s "1";"unit",unit]
let ()=Printexc.register_printer(function Diagnostic.Error error->Some(error.code^": "^error.message)|_->None)
let ()=
  require(Array.length Sys.argv=2)"Expected the independent nine-state approximation fixture";
  let fixture=read Sys.argv.(1)in
  require(get "schema_version" fixture=s "biocompiler.policy_approximation_literals.v0.1")"Wrong approximation originals";
  let request=get "material_request" fixture and limits=get "limits" fixture in
  let produced=call "compile-policy-component-material"(o["request",request;"limits",limits])in
  let _,checked_result=Material.fresh_check ~request ~candidate:(get "candidate" produced) ~limits in
  let material=accepted "Exact material"(MC.accepted checked_result)in
  require(at["quantitative";"outcome"](MC.report checked_result)=s "pass")"Approximation bypassed exact quantitative material";
  let original=get "approximation" fixture in
  let parsed=Contract.of_json original in
  let result=Check.check ~material ~contract:parsed ()in
  let checked=accepted "Fresh bounded approximation"(Check.accepted result)in
  let report=Check.report result in
  require(Check.outcome result=Outcome.Pass && Json.equal(Check.evidence checked)report &&
    Json.equal(Contract.to_json(Check.contract checked))original && Check.material checked==material)
    "Approximation capability lost its freshly checked originals";
  require(get "schema_version" report=s Check.schema_version && get "implementation" report=s Check.implementation_version &&
    get "empirical" report=s "unassessed" && get "artifact" report=s "withheld" && get "export" report=s "withheld")
    "Model-conditional approximation promoted empirical or material export authority";
  let unit=get "unit" original in
  let one=rational unit 1 and zero=rational unit 0 in
  let links=rows "links" report in
  let first_report=List.hd links and last_report=List.nth links 1 in
  require(get "case_count" first_report=Json.int 4 && get "case_count" last_report=Json.int 1)
    "Closed uncertainty intervals were sampled or clipped";
  let cases=Contract.cases(List.hd parsed.links)in
  let quanta mechanism=let raw=Bioc_domain.Policy_quantitative_network_contract.to_json mechanism in
    at["amount";"amount"](List.hd(rows "transfers" raw)),at["initial";"amount"](List.hd(rows "reservoirs" raw))in
  require(List.map quanta cases=[s "1",s "1";s "1",s "2";s "2",s "1";s "2",s "2"])
    "The complete interval Cartesian product changed order or omitted a parameter case";
  List.iter(fun link->require(get "request_labels" link=s "exact_on_all_checked_synchronized_transitions")
    "Numeric error budget weakened exact request-label agreement")links;
  let composition=get "composition" report in
  let expected_envelope=a(List.init 14(fun round->o["round",Json.int round;
    "coordinates",a(if round=0 then [one;zero]else[one;one])]))in
  require(Json.equal(get "envelope" first_report)expected_envelope &&
    Json.equal(get "envelope" composition)expected_envelope && get "maximum_error" composition=one &&
    get "coordinate_bounds" composition=a[one;one] && get "maximum_error" last_report=zero)
    "Prefix errors differ from the independent one-quantum literal oracle";
  require(get "contract_fingerprint" report=s(Canonical.fingerprint original) &&
    get "material_request_fingerprint" report=s(Canonical.fingerprint request) &&
    get "material_report_fingerprint" report=s(Canonical.fingerprint(MC.report checked_result)) &&
    get "inputs" composition=a(List.map(fun link->s(Canonical.fingerprint link))links))
    "Composed evidence detached a complete original or fresh child report";
  let fails label value=
    let outcome=Check.check ~material ~contract:(Contract.of_json value)()in
    require(Check.outcome outcome=Outcome.Fail && Check.accepted outcome=None &&
      get "links"(Check.report outcome)=a[] && get "composition"(Check.report outcome)=Json.Null &&
      rows "issues"(Check.report outcome)<>[])("Unjustified approximation accepted: "^label);incr controls in
  fails "zero whole-chain error"(set "maximum_error" zero original);
  fails "zero child error"(first(set "maximum_error" zero)original);
  fails "truncated material horizon"(set "horizon_steps"(Json.int 12)original);
  fails "different material horizon"(set "horizon_steps"(Json.int 14)original);
  fails "request changed despite numeric tolerance"
    (first(edit["source";"mechanism";"threshold";"amount";"amount"](fun _->s "2"))original);
  (* An identity-to-identity chain still pays both intermediate error bounds:
     error cannot cancel when evidence is composed through a different model. *)
  let declarations=rows "links" original in
  let first_original=List.hd declarations in
  let actual=get "target" first_original and intermediate=get "source" first_original in
  let link id source target=o["id",s id;"source",source;"target",target;"maximum_error",one;"uncertainty",a[]]in
  let cancellation=set "links"(a[link "down" actual intermediate;link "up" intermediate actual])original in
  fails "nonmonotone error cancellation" cancellation;
  let sum=Check.check ~material ~contract:(Contract.of_json(set "maximum_error"(rational unit 2)cancellation))()in
  require(Option.is_some(Check.accepted sum) && at["composition";"maximum_error"](Check.report sum)=rational unit 2)
    "Fresh triangle composition did not sum both independently established errors";
  let changed_final=set "links"(a[link "wrong_material" actual intermediate])original in
  fails "unselected final mechanism" changed_final;
  let malformed label value=rejects label(fun()->Contract.of_json value)in
  malformed "unnormalized rational"(edit["maximum_error";"denominator"](fun _->s "2")
    (edit["maximum_error";"numerator"](fun _->s "2")original));
  malformed "zero denominator"(edit["maximum_error";"denominator"](fun _->s "0")original);
  malformed "negative budget"(edit["maximum_error";"numerator"](fun _->s "-1")original);
  malformed "float budget"(edit["maximum_error";"numerator"](fun _->Json.int 1)original);
  malformed "unknown fields"(o(("sampling_hint",s "endpoints_only")::Json.object_fields original));
  malformed "uncertainty without nominal"(first(edit["uncertainty"](fun _->a[o[
    "parameter",s "transfer_amount";"id",s "forward";"lower_quanta",Json.int 2;"upper_quanta",Json.int 2]]))original);
  malformed "uncertainty over complete case bound"(first(edit["uncertainty"](fun _->a(List.map(fun id->o[
    "parameter",s "initial";"id",s id;"lower_quanta",Json.int 0;"upper_quanta",Json.int 2])["a";"b"])))original);
  malformed "continuous uncertainty"(first(edit["uncertainty"](fun values->a(List.map(set "parameter"(s "continuous"))(Json.array values))))original);
  malformed "middle map splice"(edit["links"](fun values->a(List.mapi(fun index value->
    if index=1 then edit["source";"observation"](fun _->a[s "b";s "a"])value else value)(Json.array values)))original);
  malformed "off-grid uncertainty nominal"(first(edit["source";"mechanism";"transfers"](fun values->a(List.mapi(fun index value->
    if index=0 then edit["amount";"amount"](fun _->s "0.5")value else value)(Json.array values))))original);
  rejects "zero local work"(fun()->Check.check ~maximum:0 ~material ~contract:parsed ());
  let parent=W.create ~profile:"approximation-test" ~error_code:"approximation_parent_limit" ~maximum:0()in
  rejects "zero cumulative work"(fun()->Check.check ~parent ~material ~contract:parsed ());
  Printf.printf "PASS bounded approximation: four complete cases, literal envelopes, exact requests, monotone chain; %d rejection controls\n" !controls
