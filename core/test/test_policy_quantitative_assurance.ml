open Bioc_wire
module Service=Bioc_service.Service
module Producer=Bioc_producer_service.Producer_service
module R=Bioc_domain.Policy_quantitative_assurance_request
let ()=Printexc.register_printer(function Diagnostic.Error d->Some(d.code^": "^d.message)|_->None)
let s value=Json.String value
let o fields=Json.Object fields
let get key raw=Json.field key(Json.object_fields raw)
let text key raw=Json.string(get key raw)
let set key value raw=o(List.map(fun(name,old)->name,if name=key then value else old)(Json.object_fields raw))
let rec at keys raw=match keys with []->raw|key::rest->at rest(get key raw)
let rec edit keys f raw=match keys with []->f raw|key::rest->set key(edit rest f(get key raw))raw
let require condition message=if not condition then failwith message
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_artifact ~max_bytes:8388608 ~max_nodes:250000(really_input_string channel(in_channel_length channel)))
let call handler role operation payload=
  let request:Protocol.request={request_id="quantitative-assurance";operation;payload} in
  match handler role request with Protocol.Ok,Some result,[]->result|_->failwith("Failed "^operation)
let rejected label action=match action()with
  |_->failwith("Assurance adversary accepted: "^label)
  |exception Diagnostic.Error _->()
let original material approximation evidence=o[
  "schema_version",s R.schema_version;"profile",s R.profile;"material_request",material;
  "approximation",approximation;"realization_evidence",evidence;"max_work",Json.int R.maximum_work]
let payload request candidate limits=o["request",request;"candidate",candidate;"limits",limits]
let check request candidate limits=call Service.handle Protocol.Verify "check-policy-quantitative-assurance"(payload request candidate limits)
let export request candidate limits=call Service.handle Protocol.Verify "export-policy-quantitative-assurance"(payload request candidate limits)
let ()=
  require(Array.length Sys.argv=5)"Expected approximation, evidence, network and component-composition originals";
  let fixture=read Sys.argv.(1)and evidence_fixture=read Sys.argv.(2)and network=read Sys.argv.(3)in
  let material=get "material_request" fixture and approximation=get "approximation" fixture and limits=get "limits" fixture in
  let request=original material approximation Json.Null in
  let produced=call Producer.handle Protocol.Core "compile-policy-quantitative-assurance"(o["request",request;"limits",limits])in
  let candidate=get "candidate" produced in
  let checked=check request candidate limits in
  require(Json.equal produced checked)"Producer and independent original-authority checking disagree";
  require(at["report";"export_permitted"]checked=Json.Bool true &&
    at["report";"approximation";"outcome"]checked=s "pass")"Requested approximation withheld acceptance";
  require(List.length(Json.array(at["report";"exact_refinement";"claims"]checked))=10)
    "Approximation replaced or weakened an existing exact relation";
  let replayed=call Service.handle Protocol.Verify "replay-policy-quantitative-assurance"
    (o["request",request;"candidate",candidate;"limits",limits;"report",checked])in
  require(Json.equal replayed checked)"Fresh complete replay changed its evidence";
  rejected "tampered replay"(fun()->call Service.handle Protocol.Verify "replay-policy-quantitative-assurance"
    (o["request",request;"candidate",candidate;"limits",limits;"report",set "artifact"(o[])checked]));
  let exported=export request candidate limits in
  let artifact=get "artifact" exported in
  let manifest=get "manifest" artifact in
  require(Canonical.fingerprint manifest=text "manifest_sha256" artifact &&
    Canonical.sha256(text "fasta" artifact)=text "fasta_sha256" artifact &&
    Json.equal(get "request" manifest)request &&
    Json.equal(at["material_manifest";"assessment"]manifest)(at["report";"material"]checked))
    "Assurance export lost exact RNA, material assessment or complete original authority";
  let legacy=call Service.handle Protocol.Verify "export-policy-component-material"(payload material candidate limits)in
  require(Json.equal(get "fasta"(get "artifact" legacy))(get "fasta" artifact) &&
    Json.equal(get "manifest"(get "artifact" legacy))(get "material_manifest" manifest))
    "Assurance changed the existing exact material export";
  let zero=edit["approximation";"maximum_error";"numerator"](fun _->s "0")request in
  let failed=check zero candidate limits in
  require(at["report";"export_permitted"]failed=Json.Bool false &&
    at["report";"approximation";"outcome"]failed=s "fail" &&
    at["report";"material";"status"]failed=s "checked_component_material")
    "Failed numerical assurance changed exact material or acquired export";
  rejected "exceeded requested error bound"(fun()->export zero candidate limits);
  rejected "assurance budget"(fun()->check(set "max_work"(Json.int 1)request)candidate limits);
  rejected "report-as-authority"(fun()->R.of_json(o(("saved_pass",Json.Bool true)::Json.object_fields request)));
  let verify_request:Protocol.request={request_id="role";operation="compile-policy-quantitative-assurance";
    payload=o["request",request;"limits",limits]}in
  let status,_,_=Producer.handle Protocol.Verify verify_request in
  require(status=Protocol.Unsupported)"Verifier acquired a producer capability";
  let network_request=get "request" network and network_limits=get "limits" network in
  let evidence=get "contract" evidence_fixture in
  let request=original network_request Json.Null evidence in
  let produced=call Producer.handle Protocol.Core "compile-policy-quantitative-assurance"
    (o["request",request;"limits",network_limits])in
  let candidate=get "candidate" produced in
  require(at["report";"realization_evidence";"status"]produced=s "supported" &&
    at["report";"empirical_function"]produced=s "unassessed" &&
    at["report";"material";"empirical"]produced=s "unassessed")
    "Supplied parameter compatibility was promoted to biological function";
  ignore(export request candidate network_limits);
  let missing=edit["realization_evidence";"dossier"](fun _->Json.Null)request in
  let required=edit["realization_evidence";"require_compatibility"](fun _->Json.Bool true)missing in
  let missing_result=check required candidate network_limits in
  require(at["report";"realization_evidence";"status"]missing_result=s "unassessed" &&
    at["report";"export_permitted"]missing_result=Json.Bool false)
    "Missing measurements met an explicit evidence acceptance requirement";
  rejected "required absent evidence"(fun()->export required candidate network_limits);
  let advisory=edit["realization_evidence";"require_compatibility"](fun _->Json.Bool false)missing in
  let exported=export advisory candidate network_limits in
  require(at["report";"realization_evidence";"status"]exported=s "unassessed")
    "Advisory unassessed evidence disappeared from exported lineage";
  let coupled=read Sys.argv.(4)in
  let coupled_material=get "request" coupled and coupled_limits=get "limits" coupled in
  let mechanism=at["quantitative";"network";"mechanism"]coupled_material in
  let coordinates=Json.Array(List.map(fun row->get "compartment" row)(Json.array(get "reservoirs" mechanism)))in
  let endpoint=o["mechanism",mechanism;"observation",coordinates]in
  let zero=o["numerator",s "0";"denominator",s "1";"unit",get "unit" mechanism]in
  let horizon=Z.to_int(Json.integer(at["implementation_request";"operating_domain";"horizon_ticks"]coupled_material))+1 in
  let exact_approximation=o["schema_version",s "biocompiler.policy_approximation_contract.v0.1";
    "profile",s "biocompiler.policy_bounded_sampled_network_approximation.v0.1";
    "horizon_steps",Json.int horizon;"metric",s "coordinatewise_absolute_prefix_error";
    "coordinates",coordinates;"unit",get "unit" mechanism;"maximum_error",zero;
    "links",Json.Array[o["id",s "coupled_identity";"source",endpoint;"target",endpoint;
      "uncertainty",Json.Array[];"maximum_error",zero]]]in
  let coupled_request=original coupled_material exact_approximation Json.Null in
  let produced=call Producer.handle Protocol.Core "compile-policy-quantitative-assurance"
    (o["request",coupled_request;"limits",coupled_limits])in
  require(at["report";"approximation";"outcome"]produced=s "pass" &&
    at["report";"export_permitted"]produced=Json.Bool true)
    "General quantitative component composition lost scoped approximation assurance";
  ignore(export coupled_request(get "candidate" produced)coupled_limits);
  print_endline "quantitative assurance: fresh compile/check/replay, exact RNA lineage, error bounds, separate evidence and conjunctive export checked"
