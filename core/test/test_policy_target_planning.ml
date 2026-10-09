open Bioc_wire
module Service = Bioc_producer_service.Producer_service
module Planner = Bioc_producer_service.Policy_target_planning
module Source = Bioc_checker.Policy_check
module Document = Bioc_domain.Policy_document

let ()=Printexc.register_printer(function Diagnostic.Error error->
  Some(Printf.sprintf "Diagnostic.Error(%s, %s, %s)" error.code
    (Option.value ~default:"<none>" error.path) error.message)|_->None)
let s value=Json.String value
let a values=Json.Array values
let o fields=Json.Object fields
let get key value=Json.field key(Json.object_fields value)
let rows key value=Json.array(get key value)
let text key value=Json.string(get key value)
let rec at path value=match path with []->value|key::rest->at rest(get key value)
let set key replacement value=o((key,replacement)::List.remove_assoc key(Json.object_fields value))
let rec edit path transform value=match path with []->transform value
  |key::rest->set key(edit rest transform(get key value))value
let require condition message=if not condition then failwith message
let read path=let channel=open_in_bin path in
  Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
    Json.parse_artifact ~max_bytes:(8*1024*1024) ~max_nodes:400000
      (really_input_string channel(in_channel_length channel)))
let controls=ref 0
let reject code label action=match action()with
  |_->failwith("Planning adversary returned a partial or accepted report: "^label)
  |exception Diagnostic.Error error->
    require(error.code=code)(label^": expected "^code^", received "^error.code);incr controls
let call role operation payload=
  let request:Protocol.request={request_id="target-planning-literal";operation;payload}in
  Service.handle role request
let successful operation payload=match call Protocol.Core operation payload with
  |Protocol.Ok,Some result,[]->result
  |_,_,diagnostics->failwith(operation^": "^String.concat "; "
    (List.map(fun(error:Diagnostic.t)->error.code^": "^error.message)diagnostics))
let source_edit identity transform raw=edit["document";"program";"declarations"]
  (fun values->a(List.map(fun value->if text "id" value=identity then transform value else value)(Json.array values)))raw
let source_valid raw=require(get "status"(Source.check(Document.of_json(get "document" raw)))=s "valid")
  "Planning semantic control must be independently source-valid"

let limits=o["max_work",Json.int 100000000;"max_report_bytes",Json.int 2097152;
  "max_report_nodes",Json.int 100000]
let envelope ?(definitions=Json.Null) ?(realization=Json.Null) ?(material=Json.Null) target document=
  o["schema_version",s "biocompiler.policy_target_plan_request.v0.1";"target",s target;
    "document",document;"definitions",definitions;"realization_request",realization;
    "material_request",material;"limits",limits]
let implementation_request target original=envelope ~definitions:(get "definitions" original)
  ~realization:original target(get "document" original)
let material_request target original=let realization=get "implementation_request" original in
  envelope ~definitions:(get "definitions" realization) ~realization ~material:original target(get "document" realization)
let plan request=successful "plan-policy-target"(o["request",request])
let replay request report=Planner.handle ~operation:"replay-policy-target-plan"(o["request",request;"report",report])
let stages=["source_contracts";"operational_admission";"realization_inputs";"model_lowering";
  "source_binding";"component_arrangement";"provider_dependencies"]
let stage name report=List.find(fun value->text "stage" value=name)(rows "stages" report)|>text "status"
let claims=o["planning",s "diagnostic_only";"diagnostic_completeness",s "first_blocker";
  "execution",s "not_performed";"preservation",s "unassessed";"requirements",s "unassessed";
  "resource_feasibility",s "unassessed";"material",s "unassessed";"empirical",s "unassessed";
  "artifact",s "withheld";"export",s "withheld"]
let check_wrapper request wrapper=
  Json.exact_fields["schema_version";"implementation";"validation_scope";"resource_profile";
    "request_fingerprint";"report_fingerprint";"report"](Json.object_fields wrapper);
  require(get "schema_version" wrapper=s "biocompiler.core.policy_target_plan.v1" &&
    get "implementation" wrapper=s "biocompiler.ocaml.policy_target_planning.v0.1" &&
    get "validation_scope" wrapper=s "policy-target-planning-v0.1" &&
    get "resource_profile" wrapper=s "biocompiler.policy_target_planning_resources.v0.1")
    "Planning service changed its explicit diagnostic profile";
  let report=get "report" wrapper in
  require(get "request_fingerprint" wrapper=s(Canonical.fingerprint request) &&
    get "report_fingerprint" wrapper=s(Canonical.fingerprint report) &&
    get "request_fingerprint" report=get "request_fingerprint" wrapper &&
    get "document_fingerprint" report=s(Canonical.fingerprint(get "document" request)))
    "Planning detached its exact complete original authority or report bytes";
  require(get "schema_version" report=s "biocompiler.policy_target_plan.v0.1" &&
    Json.equal(get "claims" report)claims &&
    List.map(text "stage")(rows "stages" report)=stages)
    "Planning promoted acceptance or omitted a diagnostic stage";
  List.iter(fun field->let original=get field request in
    require(get(field^"_fingerprint")report=(if original=Json.Null then Json.Null else s(Canonical.fingerprint original)))
      "Planning invented or detached optional input authority")["realization_request";"material_request"];
  require(get "target" report=Bioc_domain.Policy_target_capabilities.target(text "target" request) &&
    get "catalog_fingerprint" report=s Bioc_domain.Policy_target_capabilities.catalog_fingerprint)
    "Planning target descriptor differs from its exact installed vocabulary";
  require(List.for_all(fun value->get "status" value=s "unassessed")(rows "requirements" report) &&
    List.for_all(fun value->get "status" value=s "required" && get "stage" value=s "full_pipeline")(rows "obligations" report))
    "Planning discharged a requirement or a compilation/export obligation";
  require(Z.sign(Json.integer(at["usage";"work"]report))>0 &&
    at["usage";"max_work"]report=at["limits";"max_work"]request)
    "Planning did not retain its actual positive owned work accounting";
  report
let expected_census original report=
  let values=rows "declarations"(at["document";"program"]original)in
  let expected=List.mapi(fun index value->o["id",get "id" value;"kind",get "$type" value;
    "path",s("/document/program/declarations/"^string_of_int index)])values in
  require(get "declarations" report=a expected)"Planning lost ordered source occurrence identities";
  let requirements=List.mapi(fun index value->index,value)values|>List.filter_map(fun(index,value)->
    if get "$type" value=s "Requirement"then Some(o["id",get "id" value;
      "path",s("/document/program/declarations/"^string_of_int index);"source",value;"status",s "unassessed"])else None)in
  require(get "requirements" report=a requirements)"Planning omitted or changed an original hard requirement";
  let source=get "source_assessment" report in
  require(Json.equal source(Source.check(Document.of_json(get "document" original))))
    "Planning did not retain the fresh complete source assessment";
  require(List.map(get "id")(rows "obligations" report)=rows "deferred_stages"(get "target" report))
    "Planning changed the complete target obligation inventory"
let expect_status expected blocked request=
  let wrapper=plan request in let report=check_wrapper request wrapper in
  require(get "status" report=s expected && stage blocked report="blocked" && rows "diagnostics" report<>[])
    ("Planning category or first blocking stage changed: "^expected^"/"^blocked);
  List.iter(fun row->require(get "category" row=s expected && get "stage" row=s blocked)
    "Planning diagnostic disagrees with its exact first blocker")(rows "diagnostics" report);
  incr controls;wrapper,report
let selected_models original expected report=
  let selected=rows "selected_models" report in
  require(List.length selected=expected && List.length(List.sort_uniq String.compare(List.map(text "node")selected))=expected)
    "Planned model node census differs from independently expected source graph";
  let models=rows "models"(get "implementation_library" original)in
  List.iter(fun row->let found=List.filter(fun value->Json.equal(get "identity" value)(get "model" row))models in
    require(List.length found=1)"Planned model has no unique original body";
    let model=List.hd found in
    require(get "configuration_digest" row=get "configuration_digest" model &&
      get "primitive" row=at["body";"primitive"]model &&
      at["identity";"content_fingerprint"]model=s(Canonical.fingerprint(get "body" model)))
      "Planned model changed the independently supplied configuration")selected
let completed_implementation expected original target=
  let request=implementation_request target original in let wrapper=plan request in
  let report=check_wrapper request wrapper in
  require(get "status" report=s "planned" && rows "diagnostics" report=[] && rows "missing_inputs" report=[] &&
    List.for_all(fun name->stage name report="completed")["source_contracts";"operational_admission";
      "realization_inputs";"model_lowering";"source_binding"] &&
    stage "component_arrangement" report="not_applicable" && stage "provider_dependencies" report="not_applicable" &&
    get "selected_components" report=a[] && get "provider_dependencies" report=Json.Null)
    "Exact implementation preflight unexpectedly executed or granted material acceptance";
  expected_census original report;selected_models original expected report;
  request,wrapper

(* These controls update actual model bodies and original catalog pins. A stale
   fingerprint must not mask missing concrete source-required configurations. *)
let change_register original transform=
  let models=rows "models"(get "implementation_library" original)in
  let old=List.find(fun model->at["body";"primitive"]model=s "truth_register")models in
  let body=edit["configuration"]transform(get "body" old)in
  let identity=set "content_fingerprint"(s(Canonical.fingerprint body))(get "identity" old)in
  let replacement=old|>set "body" body|>set "identity" identity
    |>set "configuration_digest"(s(Canonical.fingerprint(get "configuration" body)))in
  original|>edit["implementation_library";"models"](fun values->a(List.map(fun model->
    if get "identity" model=get "identity" old then replacement else model)(Json.array values)))
    |>edit["catalog_bindings"](fun values->a(List.map(edit["models"](fun pins->a(List.map(fun pin->
      if pin=get "identity" old then identity else pin)(Json.array pins))))(Json.array values)))
let remove_register original=
  let old=List.find(fun model->at["body";"primitive"]model=s "truth_register")
    (rows "models"(get "implementation_library" original))in
  original|>edit["implementation_library";"models"](fun values->a(List.filter(fun model->get "identity" model<>get "identity" old)(Json.array values)))
    |>edit["catalog_bindings"](fun values->a(List.map(edit["models"](fun pins->a(List.filter((<>) (get "identity" old))(Json.array pins))))(Json.array values)))
let resource_deficit material=edit["context";"providers"](fun values->a(List.map(fun provider->
  let body=get "body" provider in let capacities=rows "capacities" body in
  if not(List.exists(fun capacity->text "unit" capacity="active_attempt_records")capacities)then provider else
  let body=set "capacities"(a(List.map(fun capacity->if text "unit" capacity="active_attempt_records"then
    set "quantity"(Json.int 23)capacity else capacity)capacities))body in
  provider|>set "body" body|>edit["identity";"content_fingerprint"](fun _->s(Canonical.fingerprint body)))(Json.array values)))material

let ()=
  require(Array.length Sys.argv=3)"Expected independent network and finite-machine fixtures";
  let network=read Sys.argv.(1)and finite=read Sys.argv.(2)in
  let material=get "request" network in let original=get "implementation_request" material in
  let document=get "document" original and definitions=get "definitions" original in
  let catalog=Bioc_domain.Policy_target_capabilities.catalog in
  let expected_targets=["implementation";"finite_machine_implementation";"network_implementation";
    "component_material";"instance_material";"prerequisite_material";"two_observation_material";
    "multi_member_material";"grounded_helper_material";"finite_machine_material";"quantitative_material";"network_material";"multi_site_implementation";"step_quantitative_material";"transfer_pair_material";"transfer_network_material";"coupled_implementation";"coupled_quantitative_material"]in
  require(List.map(text "target")(rows "targets" catalog)=expected_targets &&
    Bioc_domain.Policy_target_capabilities.catalog_fingerprint=Canonical.fingerprint catalog &&
    Canonical.fingerprint catalog="fe414a3f60668dd1466f4a6b1999067f196936aa85df4c2b6747f7190e20d765")
    "Installed planning catalog omitted or relabeled an existing exact target";
  let partial=envelope "network_implementation" document in
  let partial_wrapper,partial_report=expect_status "missing_inputs" "operational_admission" partial in
  require(List.mem(s "definitions")(rows "missing_inputs" partial_report))"Absent descriptors were not identified as required supplied inputs";
  expected_census original partial_report;
  List.iter(fun document->let _,report=expect_status "invalid_source" "source_contracts"
    (envelope "network_implementation" document)in
    require(get "source_assessment" report=Json.Null && rows "declarations" report=[] &&
      rows "requirements" report=[] && rows "selected_models" report=[])
      "Undecodable raw source acquired an invented source census")
    [Json.Null;o["$type",s "FuturePolicyProgram";"status",s "pass"]];
  ignore(expect_status "missing_inputs" "realization_inputs"(set "definitions" definitions partial));
  let request,wrapper=completed_implementation 35 original "network_implementation"in
  require(Json.equal(replay request wrapper)wrapper)"Exact replay changed freshly recomputed diagnostic planning";
  List.iter(fun row->let material=get "request" row in let original=get "implementation_request" material in
    ignore(completed_implementation(Z.to_int(Json.integer(at["expected";"node_count"]row)))original "finite_machine_implementation"))
    (rows "cases" finite);
  let material_envelope=material_request "network_material" material in
  let material_wrapper=plan material_envelope in let material_report=check_wrapper material_envelope material_wrapper in
  require(get "status" material_report=s "planned" && stage "component_arrangement" material_report="completed" &&
    stage "provider_dependencies" material_report="completed" &&
    get "selected_components" material_report=at["catalog_binding";"components"]material &&
    rows "issues"(get "provider_dependencies" material_report)=[])
    "Complete supplied component arrangement or diagnostic provider closure was lost";
  expected_census original material_report;selected_models original 35 material_report;
  let _,missing_material=expect_status "missing_inputs" "component_arrangement"
    (implementation_request "network_material" original)in
  require(List.mem(s "material_request")(rows "missing_inputs" missing_material))
    "Material target failed to identify missing original component authority";
  selected_models original 35 missing_material;
  let inconsistent_material=edit["implementation_request";"budgets";"max_prefixes"](fun _->Json.int 1)material in
  ignore(expect_status "incompatible_inputs" "component_arrangement"
    (set "material_request" inconsistent_material material_envelope));
  let missing_provider=edit["context";"providers"](fun values->a(List.filter(fun provider->
    at["identity";"id"]provider<>s "context.environment")(Json.array values)))material in
  let missing_provider_envelope=material_request "network_material" missing_provider in
  let missing_provider_report=check_wrapper missing_provider_envelope(plan missing_provider_envelope)in
  require(get "status" missing_provider_report=s "missing_inputs" &&
    stage "provider_dependencies" missing_provider_report="completed" &&
    List.exists(fun issue->get "kind" issue=s "missing" && get "code" issue=s "prerequisite_provider_missing")
      (rows "issues"(get "provider_dependencies" missing_provider_report)))
    "A completed provider graph must retain its missing supplied prerequisite";
  incr controls;
  let deficit_envelope=material_request "network_material"(resource_deficit material)in
  let deficit_report=check_wrapper deficit_envelope(plan deficit_envelope)in
  require(get "status" deficit_report=s "planned" && at["claims";"resource_feasibility"]deficit_report=s "unassessed")
    "Advisory arrangement silently became physical capacity checking";
  incr controls;
  let deferred=original|>edit["budgets";"max_prefixes"](fun _->Json.int 1)
    |>edit["budgets";"max_work"](fun _->Json.int 1)in
  ignore(completed_implementation 35 deferred "network_implementation");
  incr controls;
  let invalid=source_edit "alpha/launch_a"(edit["when";"ref";"id"](fun _->s "absent_observation"))original in
  let _,invalid_report=expect_status "invalid_source" "source_contracts"(implementation_request "network_implementation" invalid)in
  require(List.exists(fun row->get "declaration_id" row=s "alpha/launch_a" &&
    match get "path" row with Json.String value->String.starts_with ~prefix:"/document/program/declarations/10/" value|_->false)
    (rows "diagnostics" invalid_report))"Invalid-source diagnostic lost its exact original declaration and path";
  let unsupported=source_edit "beta/complete_b"(edit["on";"ref";"id"](fun _->s "alpha/response_a"))original in
  source_valid unsupported;
  ignore(expect_status "unsupported_target" "realization_inputs"(implementation_request "network_implementation" unsupported));
  ignore(expect_status "incompatible_inputs" "realization_inputs"(set "document"
    (edit["program";"id"](fun _->s "different_original")document)request));
  ignore(expect_status "incompatible_inputs" "realization_inputs"(set "target"(s "finite_machine_implementation")request));
  let bad_domain=edit["operating_domain";"clock"](fun _->s "absent_clock")original in
  ignore(expect_status "incompatible_inputs" "realization_inputs"(implementation_request "network_implementation" bad_domain));
  let empty_models=edit["implementation_library";"models"](fun _->a[])original in
  ignore(expect_status "incompatible_inputs" "realization_inputs"(implementation_request "network_implementation" empty_models));
  List.iter(fun changed->source_valid changed;ignore(expect_status "missing_inputs" "model_lowering"
    (implementation_request "network_implementation" changed)))
    [remove_register original;change_register original(set "initial"(s "true"))];
  let false_literal=o["$type",s "Expr";"op",s "literal";"value_type",o["$type",s "TypeSpec";
    "kind",s "truth";"unit",Json.Null;"entity_kind",Json.Null];"args",a[];"ref",Json.Null;
    "value",Json.Bool false;"scope",Json.Null;"contract",Json.Null;"duration",Json.Null;
    "clock",Json.Null;"coverage",Json.Null;"binding",Json.Null]in
  let impossible=source_edit "alpha/initiation_a"(fun value->value|>set "kind"(s "safety")
    |>set "condition" false_literal|>set "trigger" Json.Null|>set "response" Json.Null
    |>set "deadline" Json.Null|>set "clock" Json.Null)original in
  source_valid impossible;
  let _,unexecuted=completed_implementation 35 impossible "network_implementation"in
  require(List.exists(fun value->get "id" value=s "alpha/initiation_a" &&
    at["source";"condition";"value"]value=Json.Bool false && get "status" value=s "unassessed")
    (rows "requirements"(get "report" unexecuted)))
    "Planning turned an unexecuted false requirement into a pass/fail verdict";
  let moved=edit["document";"program";"source_map"](fun values->a(List.mapi(fun index value->
    if index=0 then set "line"(Json.int 100)value else value)(Json.array values)))partial in
  let _,moved_report=expect_status "missing_inputs" "operational_admission" moved in
  require(get "document_fingerprint" moved_report<>get "document_fingerprint" partial_report &&
    at["source_assessment";"artifact_digest"]moved_report<>at["source_assessment";"artifact_digest"]partial_report)
    "Source-map edits inherited a retained artifact identity";
  let reordered=edit["document";"program";"declarations"](fun values->match Json.array values with
    |left::right::rest->a(right::left::rest)|_->failwith "Source fixture needs two declarations")partial in
  let _,reordered_report=expect_status "missing_inputs" "operational_admission" reordered in
  require(get "declarations" reordered_report<>get "declarations" partial_report)
    "Declaration reordering collapsed distinct source occurrences";
  List.iter(fun(label,changed)->
    let changed=set "report_fingerprint"(s(Canonical.fingerprint(get "report" changed)))changed in
    reject "policy_target_plan_replay" label(fun()->replay partial changed))
    ["forged plan status",edit["report";"status"](fun _->s "planned")partial_wrapper;
     "forged discharged obligation",edit["report";"obligations"](fun values->a(List.map(set "status"(s "discharged"))(Json.array values)))partial_wrapper;
     "forged model inventory",edit["report";"selected_models"](fun _->get "selected_models"(get "report" wrapper))partial_wrapper;
     "forged work count",edit["report";"usage";"work"](fun _->Json.int 0)partial_wrapper];
  reject "policy_target_plan_replay" "changed source map replay"(fun()->replay moved partial_wrapper);
  reject "policy_target_plan_replay" "changed declaration order replay"(fun()->replay reordered partial_wrapper);
  reject "unknown_field" "supplied pass injected as planning authority"(fun()->Planner.handle ~operation:"plan-policy-target"
    (o["request",partial;"report",o["status",s "pass"]]));
  reject "policy_target_unknown" "unknown target"(fun()->plan(set "target"(s "future_unbounded_target")partial));
  reject "policy_target_plan_resource_limit" "owned planning work exhausted"(fun()->plan(edit["limits";"max_work"](fun _->Json.int 1)partial));
  List.iter(fun field->reject "policy_target_plan_publication_limit" ("planning "^field^" exhausted")
    (fun()->plan(edit["limits";field](fun _->Json.int 1)partial)))["max_report_bytes";"max_report_nodes"];
  List.iter(fun operation->match call Protocol.Verify operation(o["request",request;"report",wrapper])with
    |Protocol.Unsupported,None,[diagnostic]->require(diagnostic.code="unsupported_operation")"Verifier returned wrong planning diagnostic";incr controls
    |_->failwith "Standalone verifier acquired a producer planning operation")["plan-policy-target";"replay-policy-target-plan"];
  require(!controls=32)"Planning adversarial control census is incomplete";
  Printf.printf "policy_target_planning: exact source/target/model/component identities, first blockers, deferred obligations and %d adversarial controls\n" !controls
