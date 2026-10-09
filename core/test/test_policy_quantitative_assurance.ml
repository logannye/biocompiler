open Bioc_wire
module Service=Bioc_service.Service
module Producer=Bioc_producer_service.Producer_service
module R=Bioc_domain.Policy_quantitative_assurance_request
module Wire=Bioc_domain.Policy_coupled_wire
module Material=Bioc_service.Policy_component_material_service
let scenario=ref "fixture initialization"
let operation_context=ref "fixture initialization"
let ()=Printexc.register_printer(function Diagnostic.Error d->Some(d.code^": "^d.message^
  " [assurance test: "^ !operation_context^"; path: "^Option.value ~default:"<none>" d.path^"]")|_->None)
let s value=Json.String value
let o fields=Json.Object fields
let get key raw=Json.field key(Json.object_fields raw)
let text key raw=Json.string(get key raw)
let set key value raw=o(List.map(fun(name,old)->name,if name=key then value else old)(Json.object_fields raw))
let rec at keys raw=match keys with []->raw|key::rest->at rest(get key raw)
let rec edit keys f raw=match keys with []->f raw|key::rest->set key(edit rest f(get key raw))raw
let require condition message=if not condition then failwith(!operation_context^": "^message)
let optional key=function Json.Object fields->Option.value(List.assoc_opt key fields)~default:Json.Null|_->Json.Null
let selected names value=o(List.map(fun name->name,optional name value)names)
let failure_summary result=
  let report=optional "report" result in
  let material=optional "material" report in
  let preservation=optional "preservation" material in
  let brief value=o["status",optional "status" value;"outcome",optional "outcome" value;
    "diagnostics",optional "diagnostics" value;"issues",optional "issues" value;
    "graph_issues",optional "issues"(optional "graph" value);
    "stop_reason",optional "stop_reason" value;"diagnostic",optional "diagnostic" value;
    "usage",optional "usage" value]in
  let rows names predicate=function
    |Json.Array values->Json.Array(List.map(selected names)(List.filter predicate values))|_->Json.Null in
  let stopped=optional "stopped" preservation in
  let stop=match stopped with Json.Null->Json.Null|_->o[
    "category",optional "category" stopped;"diagnostic",optional "diagnostic" stopped;
    "history",optional "history" stopped;
    "source_execution",selected["status";"horizon";"usage"](optional "source_execution" stopped);
    "candidate_frame",optional "candidate_frame" stopped]in
  let summary=o["export_permitted",optional "export_permitted" report;
    "material",selected["status";"assembly_status";"context_status";"quantitative_status";
      "prerequisite_status";"all_original_obligations_discharged";"usage"]material;
    "assembly",brief(optional "assembly" material);"context",brief(optional "context" material);
    "prerequisites",brief(optional "prerequisites" material);"quantitative",brief(optional "quantitative" material);
    "approximation",brief(optional "approximation" report);"realization_evidence",brief(optional "realization_evidence" report);
    "preservation",o["status",optional "status" preservation;"preservation",optional "preservation" preservation;
      "assurance",optional "assurance" preservation;"program_coverage",selected[
        "nonvacuous";"created_attempts";"active_prefixes";"inactive_prefixes"](optional "program_coverage" preservation);
      "coverage",optional "coverage" preservation;"usage",optional "usage" preservation;
      "requirements",rows["id";"status";"nonvacuous";"coverage"]
        (fun row->optional "status" row<>s "pass" || optional "nonvacuous" row<>Json.Bool true)
        (optional "requirements" preservation);"stopped",stop];
    "obligations",rows["obligation";"status";"stage"]
      (fun row->optional "status" row<>s "discharged")(optional "obligations" material)]in
  (* Retain stage outcomes and the beginning of a mismatch/stop witness without
     reproducing original sources, full graphs or unbounded history records. *)
  let remaining=ref 256 in
  let rec take n=function []->[]|_ when n=0->[]|first::rest->first::take(n-1)rest in
  let rec preview depth value=
    if !remaining=0 || depth=0 then s "<bounded preview>"else(
      decr remaining;match value with
      |Json.String text when String.length text>128->s(String.sub text 0 128^"...")
      |Json.Int number when Z.numbits number>256->s "<large integer>"
      |Json.Array values->Json.Array(List.map(preview(depth-1))(take 4 values))
      |Json.Object fields->o(List.map(fun(key,value)->key,preview(depth-1)value)(take 16 fields))
      |_->value)in
  Canonical.encode_bounded ~max_bytes:65536(preview 8 summary)
let require_optional label key result=
  let report=optional "report" result in
  let value=optional key report in
  if not(optional "status"(optional "material" report)=s "checked_component_material" &&
    (match value with Json.Object _->true|_->false))then
    require false(label^": complete material/optional assurance was withheld: "^failure_summary result);
  value
let diagnostic_controls ()=
  let stopped=o["category",s "source_exhausted";"diagnostic",o[
    "code",s "policy_execution_work_limit";"message",s "inert diagnostic control";"path",Json.Null]]in
  let satisfied=o["id",s "satisfied";"status",s "pass";"nonvacuous",Json.Bool true]in
  let discharged=o["obligation",s "discharged";"status",s "discharged"]in
  let result=o["report",o["export_permitted",Json.Bool false;"approximation",Json.Null;
    "material",o["status",s "not_accepted";
      "context",o["outcome",s "unsupported";
        "diagnostics",Json.Array[s "closed_component_context_family_required"]];
      "prerequisites",o["status",s "unsupported";
        "diagnostics",Json.Array[s "closed_component_context_family_required"];
        "graph",o["issues",Json.Array[o["kind",s "unsupported";"code",s "inert_prerequisite_reason"]]]];
      "obligations",Json.Array(List.init 5(fun _->discharged)@[o["obligation",s "late_unresolved";"status",s "unresolved"]]);
      "preservation",o["status",s "incomplete";"stopped",stopped;
        "requirements",Json.Array(List.init 5(fun _->satisfied)@[o["id",s "late_failed";"status",s "fail";"nonvacuous",Json.Bool false]])]]]]in
  let has text needle=let rec scan offset=offset+String.length needle<=String.length text &&
    (String.sub text offset(String.length needle)=needle || scan(offset+1))in scan 0 in
  match require_optional "inert withheld material" "approximation" result with
  |_->failwith "Missing optional assurance was not diagnosed"
  |exception Failure message->require(has message "policy_execution_work_limit" && has message "source_exhausted" &&
      has message "not_accepted" && has message "late_failed" && has message "late_unresolved" &&
      has message "closed_component_context_family_required" && has message "inert_prerequisite_reason" && String.length message<65536)
      "Withheld-material diagnostic lost its stage or original stop reason"
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_artifact ~max_bytes:8388608 ~max_nodes:250000(really_input_string channel(in_channel_length channel)))
let call handler role operation payload=
  operation_context:= !scenario^"/"^operation;
  let original=get "request" payload in
  let material=if text "schema_version" original=R.schema_version then get "material_request" original else original in
  let coupled=Material.is_coupled_request material in
  let payload=if coupled then Wire.encode payload else payload in
  let request:Protocol.request={request_id="quantitative-assurance";operation;payload} in
  match handler role request with Protocol.Ok,Some result,[]->
    require(Wire.is_packet result=coupled)"Coupled transport selection changed a legacy response";
    if coupled then Wire.decode result else result
  |_,_,diagnostics->failwith(!operation_context^": "^String.concat "; "
      (List.map(fun(d:Diagnostic.t)->d.code^": "^d.message)diagnostics))
let rejected label action=match action()with
  |_->failwith("Assurance adversary accepted: "^label)
  |exception Diagnostic.Error _->()
let original material approximation evidence=o[
  "schema_version",s R.schema_version;"profile",s R.profile;"material_request",material;
  "approximation",approximation;"realization_evidence",evidence;"max_work",Json.int R.maximum_work]
let payload request candidate limits=o["request",request;"candidate",candidate;"limits",limits]
let check request candidate limits=call Service.handle Protocol.Verify "check-policy-quantitative-assurance"(payload request candidate limits)
let export request candidate limits=call Service.handle Protocol.Verify "export-policy-quantitative-assurance"(payload request candidate limits)
let export_census ~request ~limits ~checked ~material_export=
  (* Diagnostic arithmetic over already accepted immutable child results. This
     neither publishes a response nor replaces the real export call below. *)
  let original=get "artifact" material_export in
  let manifest=o["schema_version",s "biocompiler.policy_quantitative_assurance_manifest.v0.1";
    "request",request;"limits",limits;"assessment",get "report" checked;
    "assessment_fingerprint",get "report_fingerprint" checked;
    "material_manifest",get "manifest" original;"material_manifest_sha256",get "manifest_sha256" original;
    "fasta_sha256",get "fasta_sha256" original;
    "claim_scope",s "exact_material_and_scoped_mathematical_assurance_with_separate_supplied_evidence";
    "empirical_function",s "unassessed";"original_authority",s "retain_original_inputs_separately"]in
  let artifact=o["schema_version",s "biocompiler.policy_quantitative_assurance_export.v0.1";
    "fasta",get "fasta" original;"fasta_sha256",get "fasta_sha256" original;
    "manifest",manifest;"manifest_sha256",s(String.make 64 '0')]in
  (* Any lowercase SHA-256 has exactly the same JSON byte/node inventory. *)
  let result=set "artifact" artifact checked in
  let census raw=
    let remaining=ref(4*Wire.max_expanded_nodes)in
    let node()=require(!remaining>0)"Diagnostic census exceeded its independent visit bound";decr remaining in
    let rec visit depth value=
      require(depth<=128)"Diagnostic census exceeded its independent depth bound";node();
      let fields values initial=List.fold_left(fun(count,bytes,deepest)(key,child)->
        let child_count,child_bytes,child_depth=visit(depth+1)child in
        let key_count,key_bytes=match key with None->0,0|Some key->node();
          1,String.length(Canonical.encode(Json.String key))+1 in
        count+key_count+child_count,bytes+key_bytes+child_bytes,max deepest child_depth)
        initial values in
      match value with
      |Json.Array values->fields(List.map(fun value->None,value)values)
          (1,2+max 0(List.length values-1),depth)
      |Json.Object values->fields(List.map(fun(key,value)->Some key,value)values)
          (1,2+max 0(List.length values-1),depth)
      |scalar->1,String.length(Canonical.encode scalar),depth in
    let nodes,bytes,depth=visit 0 raw in
    o["nodes",Json.int nodes;"bytes",Json.int bytes;"depth",Json.int depth]in
  let values=["request",request;"candidate",get "candidate" checked;
    "material_assessment",at["report";"material"]checked;"assurance_assessment",get "report" checked;
    "material_manifest",get "manifest" original;"assurance_manifest",manifest;"complete_export_result",result]in
  Printf.printf "coupled assurance export exact census: %s\n%!"
    (Canonical.encode(o(List.map(fun(name,value)->name,census value)values)));
  result
let ()=
  diagnostic_controls();
  scenario:="approximation";
  require(Array.length Sys.argv=5)"Expected approximation, evidence, network and component-composition originals";
  let fixture=read Sys.argv.(1)and evidence_fixture=read Sys.argv.(2)and network=read Sys.argv.(3)in
  let material=get "material_request" fixture and approximation=get "approximation" fixture and limits=get "limits" fixture in
  let request=original material approximation Json.Null in
  let produced=call Producer.handle Protocol.Core "compile-policy-quantitative-assurance"(o["request",request;"limits",limits])in
  let candidate=get "candidate" produced in
  let checked=check request candidate limits in
  require(Json.equal produced checked)"Producer and independent original-authority checking disagree";
  ignore(require_optional "checked approximation" "approximation" checked);
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
  ignore(require_optional "failed numerical bound retains material" "approximation" failed);
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
  scenario:="realization evidence";
  let network_request=get "request" network and network_limits=get "limits" network in
  let evidence=get "contract" evidence_fixture in
  let request=original network_request Json.Null evidence in
  let produced=call Producer.handle Protocol.Core "compile-policy-quantitative-assurance"
    (o["request",request;"limits",network_limits])in
  let candidate=get "candidate" produced in
  ignore(require_optional "compiled realization evidence" "realization_evidence" produced);
  require(at["report";"realization_evidence";"status"]produced=s "supported" &&
    at["report";"empirical_function"]produced=s "unassessed" &&
    at["report";"material";"empirical"]produced=s "unassessed")
    "Supplied parameter compatibility was promoted to biological function";
  ignore(export request candidate network_limits);
  let missing=edit["realization_evidence";"dossier"](fun _->Json.Null)request in
  let required=edit["realization_evidence";"require_compatibility"](fun _->Json.Bool true)missing in
  let missing_result=check required candidate network_limits in
  ignore(require_optional "missing gated evidence retains material" "realization_evidence" missing_result);
  require(at["report";"realization_evidence";"status"]missing_result=s "unassessed" &&
    at["report";"export_permitted"]missing_result=Json.Bool false)
    "Missing measurements met an explicit evidence acceptance requirement";
  rejected "required absent evidence"(fun()->export required candidate network_limits);
  let advisory=edit["realization_evidence";"require_compatibility"](fun _->Json.Bool false)missing in
  let exported=export advisory candidate network_limits in
  require(at["report";"realization_evidence";"status"]exported=s "unassessed")
    "Advisory unassessed evidence disappeared from exported lineage";
  scenario:="coupled identity approximation";
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
  ignore(require_optional "compiled coupled approximation" "approximation" produced);
  require(at["report";"approximation";"outcome"]produced=s "pass" &&
    at["report";"export_permitted"]produced=Json.Bool true)
    "General quantitative component composition lost scoped approximation assurance";
  let coupled_candidate=get "candidate" produced in
  let insufficient=at["expected";"insufficient_monitor"]coupled in
  let previous_limits=get "limits" insufficient in
  require(text "request_fingerprint" insufficient=Canonical.fingerprint coupled_material &&
    at["monitor";"max_work"]previous_limits=Json.int 1_000_000 &&
    Json.equal(edit["monitor";"max_work"](fun _->Json.int 5_000_000)previous_limits)coupled_limits)
    "Monitor control changed an original source or another invocation allowance";
  let denied=check coupled_request coupled_candidate previous_limits in
  let denied_report=get "report" denied in
  let preservation=at["material";"preservation"]denied_report in
  require(get "export_permitted" denied_report=Json.Bool false &&
    get "approximation" denied_report=Json.Null && get "exact_refinement" denied_report=Json.Null &&
    get "realization_evidence" denied_report=Json.Null && get "artifact" denied=Json.Null &&
    at["material";"status"]denied_report=s "not_accepted" &&
    get "status" preservation=get "status" insufficient &&
    at["coverage";"complete"]preservation=Json.Bool false &&
    at["coverage";"transitions"]preservation=get "transitions" insufficient &&
    at["stopped";"diagnostic";"code"]preservation=get "diagnostic" insufficient &&
    at["usage";"monitor_work"]preservation=Json.int 1_000_000)
    "Inherited 1M monitor allowance did not remain an explicit incomplete, capability-free invocation";
  (match export coupled_request coupled_candidate previous_limits with
   |_->failwith "Incomplete monitor invocation exported a payload"
   |exception Diagnostic.Error diagnostic->require(diagnostic.code=text "export_diagnostic" insufficient)
       "Incomplete monitor export failed for a different reason");
  let coupled_checked=check coupled_request coupled_candidate coupled_limits in
  require(Json.equal produced coupled_checked)"Packed coupled producer and independent checking disagree";
  let coupled_replayed=call Service.handle Protocol.Verify "replay-policy-quantitative-assurance"
    (o["request",coupled_request;"candidate",coupled_candidate;"limits",coupled_limits;"report",coupled_checked])in
  require(Json.equal coupled_checked coupled_replayed)"Packed coupled replay changed complete logical evidence";
  let exact_material=call Service.handle Protocol.Verify "export-policy-component-material"
    (payload coupled_material coupled_candidate coupled_limits)in
  let counted=export_census ~request:coupled_request ~limits:coupled_limits
    ~checked:coupled_checked ~material_export:exact_material in
  let coupled_exported=export coupled_request coupled_candidate coupled_limits in
  let coupled_artifact=get "artifact" coupled_exported in
  let coupled_manifest=get "manifest" coupled_artifact in
  require(Json.equal counted(edit["artifact";"manifest_sha256"](fun _->s(String.make 64 '0'))coupled_exported))
    "Diagnostic export inventory differs from the complete production result";
  require(Json.equal(at["artifact";"manifest"]exact_material)(get "material_manifest" coupled_manifest) &&
    Json.equal(at["artifact";"fasta"]exact_material)(get "fasta" coupled_artifact) &&
    Canonical.fingerprint coupled_manifest=text "manifest_sha256" coupled_artifact &&
    Json.equal(get "request" coupled_manifest)coupled_request)
    "Packed assurance failed to preserve standalone exact material authority and RNA";
  rejected "packed retained PASS mutation"(fun()->call Service.handle Protocol.Verify "replay-policy-quantitative-assurance"
    (o["request",coupled_request;"candidate",coupled_candidate;"limits",coupled_limits;
       "report",set "artifact"(o[])coupled_checked]));
  print_endline "quantitative assurance: fresh compile/check/replay, exact RNA lineage, error bounds, separate evidence and conjunctive export checked"
