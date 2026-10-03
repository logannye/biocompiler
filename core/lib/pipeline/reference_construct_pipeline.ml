open Bioc_wire
open Bioc_domain
module M=Bioc_compiler.Pass_manager
module C=Pipeline_contract
module W=Bioc_checker.Work_budget
module R=Reference_construct
module F=Reference_manifest
module E=Reference_construct_evidence
module Q=Bioc_checker.Reference_construct_check
module Link=Bioc_checker.Composition_check
module G=Bioc_compiler.Reference_construct_producer
module Ev=Realization_evidence
let pipeline_version="biocompiler.reference_construct_pipeline.v0.2"
let implementation_version="biocompiler.ocaml.reference_construct_pipeline.v0.1"
let resource_profile="biocompiler.reference_construct_pipeline.resources.v1"
let str value=Json.String value
let obj fields=Json.Object fields
let resource_limits=obj ["profile",str resource_profile;
  "work",str "one_caller_owned_lifetime_ancestor_including_admission_generation_and_final_check";
  "manager",M.limits_json M.default_limits;
  "generator",G.limits_json G.default_limits;
  "checker",Q.limits_json Q.default_limits;
  "composition_checker",Link.limits_json Link.default_limits;
  "records",C.resource_limits;
  "host_execution",str "trusted_callbacks_and_opaque_host_captures_outside_native_cpu_and_json_proof"]
type provider_role=Authority_validator|Linkage_validator|Construct_producer|Layout_validator
type provider_observer=W.t->M.t->M.provider->provider_role->unit
type manager_created=W.t->M.t->unit
type input_registration_hook=W.t->M.t->C.Component_input_contract.t->validators:(string*M.provider) list->unit
type registration_hook=W.t->M.t->C.Pass_contract.t->producer:M.provider->validators:(string*M.provider) list->unit
type generated=Native_candidate of R.Candidate.t|Host_candidate of M.host_value
type generator=W.t->input:Json.t->R.Request.t->generated
type generator_bridge={generate:generator;host_proposal:W.t->output:M.host_value->source_links:C.Source_link.t list->M.host_value}
type host_links_equal=W.t->actual:M.host_value list->expected:C.Source_link.t list->bool
let fail message=Diagnostic.fail "pipeline_error" message
let setting limits key=Z.to_int (Json.integer (Json.field key (Json.object_fields (M.limits_json limits))))
let codec budget limits=C.Codec.make_limits ~max_bytes:(setting limits "max_document_bytes")
  ~max_nodes:(setting limits "max_document_nodes") ~charge:(W.charge budget) ()
let domain_codec budget limits=R.Codec.make_limits ~max_bytes:(setting limits "max_document_bytes")
  ~max_nodes:(setting limits "max_document_nodes") ~charge:(W.charge budget) ()
let checker_limits limits=Q.make_limits
  ~max_input_bytes:(min Limits.max_request_bytes (setting limits "max_document_bytes"))
  ~max_report_bytes:(min Limits.max_response_bytes (setting limits "max_document_bytes"))
  ~max_report_nodes:(min Limits.max_json_nodes (setting limits "max_document_nodes"))
  ~max_items:(min 100_000 (setting limits "max_document_nodes")) ()
let linkage_limits limits=Link.make_limits
  ~max_input_bytes:(min Limits.max_request_bytes (setting limits "max_document_bytes"))
  ~max_report_bytes:(min Limits.max_response_bytes (setting limits "max_document_bytes"))
  ~max_report_nodes:(min Limits.max_json_nodes (setting limits "max_document_nodes"))
  ~max_items:(min 100_000 (setting limits "max_document_nodes")) ()
let generator_limits limits=G.make_limits
  ~max_input_bytes:(min 33_554_432 (setting limits "max_document_bytes"))
  ~max_input_nodes:(min 1_000_000 (setting limits "max_document_nodes"))
  ~max_output_bytes:(min 16_777_216 (setting limits "max_document_bytes"))
  ~max_output_nodes:(min 1_000_000 (setting limits "max_document_nodes")) ()
type prepared={budget_value:W.t;limits_value:M.limits;request_value:R.Request.t;
  registry_value:Component_registry.t;manifests_value:(string*F.t) list;
  dependencies_value:(string*string) list;authority:C.Scoped_obligation.t;
  linkage:C.Scoped_obligation.t;layout:C.Scoped_obligation.t;sequence:C.Scoped_obligation.t;
  payload:C.Scoped_obligation.t;biology:C.Scoped_obligation.t;completion:C.Completion_profile.t}
type initialized={prepared:prepared;owner:M.t}
type admission={initialized:initialized;admission_value:C.Component_input_contract.t;
  verify_authority:M.provider;verify_linkage:M.provider}
type registration={admission:admission;contract_value:C.Pass_contract.t;assemble:M.provider;
  verify_layout:M.provider;host_comparison:bool}
type t={registration:registration;candidate_value:R.Candidate.t;check_value:E.Result.t;
  result_value:C.Pipeline_result.t;record_value:C.Stage_record.t}
type failure={error:exn;manager:M.t option}
type attempt=Completed of t|Failed of failure
let phase_budget budget (prepared:prepared)=Diagnostic.require (budget==prepared.budget_value)
  "reference_construct_pipeline_budget" "Reference construct phase received a foreign lifetime budget."
let copy_manifests budget limits manifests=
  let maximum=setting limits "max_document_nodes" and seen=Hashtbl.create 8 in
  let rec copy count reversed=function
    | []->List.rev reversed
    | (key,value)::rest->
        W.charge budget (String.length key+1);
        Diagnostic.require (count<maximum) "reference_construct_pipeline_limit" "Reference manifest inventory exceeds its native bound.";
        Diagnostic.require (not (Hashtbl.mem seen key)) "reference_construct_pipeline" "Reference manifest keys must be unique.";
        Hashtbl.add seen key ();copy (count+1) ((key,value)::reversed) rest in
  copy 0 [] manifests
let prepare ~budget ?(manager_limits=M.default_limits) ~request ~registry ~manifests ()=
  let manifests=copy_manifests budget manager_limits manifests in
  let limits=codec budget manager_limits in
  C.Codec.preflight ~limits (obj ["request",R.Request.to_json request;"registry",Component_registry.to_json registry;
    "manifests",obj (List.map (fun (key,value)->key,F.to_json value) manifests)]);
  let fingerprint value=C.Codec.fingerprint ~limits value in
  let references=obj (List.map (fun (key,value)->W.charge budget (String.length key+65);key,str(F.fingerprint value)) manifests) in
  let composition=R.Request.composition request in
  let dependencies=[
    "human_admission_policy",fingerprint(str Admission.policy_version);
    "request",R.Request.fingerprint request;
    "composition",Composition.fingerprint composition;
    "component_registry",Component_registry.fingerprint registry;
    "component_lock",Component_registry.Lock.fingerprint (Composition.registry_lock composition);
    "layout",R.Request.layout_fingerprint request;
    "references",fingerprint references;
    "reference_adapter",fingerprint(str Reference_components.adapter_version);
    "component_checker",fingerprint(str Link.checker_version);
    "construct_checker",fingerprint(str Q.checker_version);
    "construct_generator",fingerprint(str G.generator_version);
    "construct_pipeline",fingerprint(str pipeline_version)] in
  let obligation id scope evidence_kind description=C.Scoped_obligation.make ~limits ~id ~scope ~evidence_kind ~description () in
  let authority=obligation "reference_authority" "reference_construct" Ev.Exact
    "Selected component and supported layout agree with independently pinned reference records." in
  let linkage=obligation "component_linkage" "reference_construct" Ev.Model_conditional
    "Current selected components satisfy their declared composition contracts." in
  let layout=obligation "construct_layout" "reference_construct" Ev.Exact
    "Construct preserves exact selected membership, reference coordinates and source requirements." in
  let sequence=obligation "emitted_sequence_identity" "exact_cds" Ev.Exact
    "Emit the selected nucleotide spelling and independently verify its exact reference identity." in
  let payload=obligation "complete_payload_features" "complete_payload" Ev.Exact
    "Delivered molecule boundaries, regulatory context and other unknown payload features remain unresolved." in
  let biology=obligation "molecular_behavior" "complete_payload" Ev.Empirical
    "Molecular behavior and same-cell coexistence are not established by a reference layout." in
  let completion=C.Completion_profile.make ~limits ~scope:"reference_construct" ~stage:C.Construct
    ~schema:R.Candidate.schema_version ~obligations:[C.Scoped_obligation.id authority;C.Scoped_obligation.id linkage;C.Scoped_obligation.id layout] () in
  {budget_value=budget;limits_value=manager_limits;request_value=request;registry_value=registry;manifests_value=manifests;
   dependencies_value=dependencies;authority;linkage;layout;sequence;payload;biology;completion}
let dependencies (value:prepared)=value.dependencies_value
let obligations (value:prepared)=[value.authority;value.linkage;value.layout;value.sequence;value.payload;value.biology]
let completion_profile (value:prepared)=value.completion
let create ~budget ?validator_equivalent ?observer ?manager_created (prepared:prepared)=
  phase_budget budget prepared;
  let owner=M.create ~budget ~limits:prepared.limits_value ?validator_equivalent ?observer
    ~target:(R.Request.target prepared.request_value) ~dependencies:prepared.dependencies_value
    ~completion_profiles:[prepared.completion] () in
  Option.iter (fun publish->publish budget owner) manager_created;
  {prepared;owner}
let initialized_manager (value:initialized)=value.owner
let prepare_admission ~budget ?provider_observer (initialized:initialized)=
  let prepared=initialized.prepared in phase_budget budget prepared;
  let limits=codec budget prepared.limits_value in
  let requirements=Composition.requirement_ids (R.Request.composition prepared.request_value) in
  let check id evidence_kind discharges=C.Check_spec.make ~limits ~id ~evidence_kind ~discharges () in
  let admission_value=C.Component_input_contract.make ~limits ~id:"reference_components" ~version:pipeline_version
    ~schema:R.Request.schema_version
    ~checks:[check "reference_authority" Ev.Exact [C.Scoped_obligation.id prepared.authority];
      check "component_linkage" Ev.Model_conditional [C.Scoped_obligation.id prepared.linkage]]
    ~requirements ~obligations:[prepared.authority;prepared.linkage;prepared.sequence;prepared.payload;prepared.biology]
    ~dependency_keys:(List.map fst prepared.dependencies_value) () in
  let verify_authority work context=
    phase_budget work prepared;
    let bound=R.Request.of_json ~limits:(domain_codec work prepared.limits_value) (C.Pass_context.input context) in
    W.charge work (R.Request.canonical_size bound+C.Pass_context.canonical_size context+1);
    if Composition.requirement_ids (R.Request.composition bound)<>C.Pass_context.requirements context then
      fail "Component admission changed its source requirements.";
    let diagnostics=Q.check_request ~parent:work ~limits:(checker_limits prepared.limits_value)
      ~request:bound ~registry:prepared.registry_value ~manifests:prepared.manifests_value () in
    let outcome=List.fold_left (fun result item->W.charge work 1;
      match result,E.Diagnostic.status item with
      | Ev.Fail,_|_,Ev.Fail->Ev.Fail|Ev.Unsupported,_|_,Ev.Unsupported->Ev.Unsupported
      | Ev.Unknown,_|_,Ev.Unknown->Ev.Unknown|Ev.Pass,Ev.Pass->Ev.Pass) Ev.Pass diagnostics in
    M.Decision(C.Check_decision.make ~limits:(codec work prepared.limits_value) ~outcome
      ~detail:"Checked frozen reference selection and supported layout authority."
      ~evidence:(obj ["diagnostics",Json.Array(List.map E.Diagnostic.to_json diagnostics)]) ()) in
  let verify_linkage work context=
    phase_budget work prepared;
    let bound=R.Request.of_json ~limits:(domain_codec work prepared.limits_value) (C.Pass_context.input context) in
    let checked=Link.check ~parent:work ~limits:(linkage_limits prepared.limits_value)
      ~request:(R.Request.composition bound) ~registry:prepared.registry_value () in
    let evidence=Composition_evidence.Result.to_json checked in
    let detail=Json.string(Json.field "claim_scope" (Json.object_fields evidence)) in
    M.Decision(C.Check_decision.make ~limits:(codec work prepared.limits_value)
      ~outcome:(Composition_evidence.Result.outcome checked) ~detail ~evidence ()) in
  Option.iter (fun observe->observe budget initialized.owner verify_authority Authority_validator;
    observe budget initialized.owner verify_linkage Linkage_validator) provider_observer;
  {initialized;admission_value;verify_authority;verify_linkage}
let admission_contract (value:admission)=value.admission_value
let admission_validators (value:admission)=["reference_authority",value.verify_authority;"component_linkage",value.verify_linkage]
let allow_admission_host_source_links (value:admission)=
  M.allow_host_source_links value.initialized.owner value.verify_authority;
  M.allow_host_source_links value.initialized.owner value.verify_linkage
let source_links budget limits bound pass_name=
  let maximum_bytes=setting limits "max_document_bytes" and maximum_nodes=setting limits "max_document_nodes" in
  let bytes=ref 2 and nodes=ref 1 and count=ref 0 in
  let codec=codec budget limits in
  List.fold_left (fun reversed instance->
    let id=Composition.Instance.id instance in W.charge budget (String.length id+1);
    List.fold_left (fun reversed requirement_id->
      let link=C.Source_link.make ~limits:codec ~requirement_id ~source_node_id:id ~target_node_id:id ~pass_name () in
      let raw=C.Source_link.to_json link in
      let size=C.Codec.measure ~limits:codec raw in
      let separator=if !count=0 then 0 else 1 in
      Diagnostic.require (size.bytes+separator<=maximum_bytes- !bytes && size.nodes<=maximum_nodes- !nodes)
        "reference_construct_pipeline_limit" "Construct source correspondence exceeds its native resource boundary.";
      bytes:= !bytes+size.bytes+separator;nodes:= !nodes+size.nodes;incr count;
      link::reversed)
      reversed (Composition.Instance.requirement_ids instance)) []
    (Composition.instances (R.Request.composition bound)) |> List.rev
let sorted_links budget limits values=
  let tuples=List.map (fun link->let parts=[C.Source_link.requirement_id link;C.Source_link.source_node_id link;
      C.Source_link.target_node_id link;C.Source_link.pass_name link] in
    C.Codec.charge limits (List.fold_left (fun n value->n+String.length value+1) 1 parts);parts) values in
  let rec levels n=if n<=1 then 1 else 1+levels(n/2) in
  let bytes=List.fold_left (fun n parts->List.fold_left (fun n value->n+String.length value+1) n parts) 1 tuples in
  let factor=4*(1+levels(List.length tuples)) in
  if bytes>W.remaining budget/factor then W.charge budget (W.remaining budget+1);
  W.charge budget (bytes*factor);
  (* OCaml list comparison of UTF-8 strings has the same scalar lexical order
     here; all fields were structurally validated strings. Duplicates remain. *)
  List.sort (List.compare String.compare) tuples
let links_equal budget limits actual expected=
  let expected=sorted_links budget limits expected in
  let actual=sorted_links budget limits actual in
  let rec same left right=match left,right with
    | [],[]->true
    | a::xs,b::ys->
        let size values=List.fold_left (fun n value->n+String.length value+1) 1 values in
        W.charge budget (size a+size b);
        a=b && same xs ys
    | _->false in
  same actual expected
let prepare_registration ~budget ?provider_observer ?generator_bridge ?host_links_equal (admission:admission) ~admitted=
  let initialized=admission.initialized in let prepared=initialized.prepared in phase_budget budget prepared;
  Diagnostic.require (C.Stage_record.id admitted="components" && C.Stage_record.stage admitted=C.Components)
    "reference_construct_pipeline_phase" "Construct registration requires its actual component admission return.";
  let limits=codec budget prepared.limits_value in
  let contract_value=C.Pass_contract.make ~limits ~id:"components_to_construct" ~version:G.generator_version
    ~input_stage:C.Components ~output_stage:C.Construct ~input_schema:R.Request.schema_version ~output_schema:R.Candidate.schema_version
    ~profile:"reference_construct" ~profile_version:pipeline_version ~supported_operations:["component_placement"]
    ~checks:[C.Check_spec.make ~limits ~id:"layout" ~evidence_kind:Ev.Exact ~discharges:[C.Scoped_obligation.id prepared.layout] ();
      C.Check_spec.make ~limits ~id:"layout_composition" ~evidence_kind:Ev.Model_conditional ~discharges:[C.Scoped_obligation.id prepared.linkage] ()]
    ~dependency_keys:(List.map fst prepared.dependencies_value)
    ~consumes_requirements:(Composition.requirement_ids(R.Request.composition prepared.request_value))
    ~introduces:[prepared.layout] ~changed_properties:["layout";"molecule_membership";"orientation";"regulatory_context"]
    ~invalidated_analyses:[C.Scoped_obligation.id prepared.linkage;C.Scoped_obligation.id prepared.biology] () in
  let assemble work context=
    phase_budget work prepared;
    let bound=R.Request.of_json ~limits:(domain_codec work prepared.limits_value) (C.Pass_context.input context) in
    let output=match generator_bridge with
      | None->Native_candidate(G.generate ~parent:work ~limits:(generator_limits prepared.limits_value) bound)
      | Some bridge->bridge.generate work ~input:(C.Pass_context.input context) bound in
    let links=source_links work prepared.limits_value bound (C.Pass_contract.id contract_value) in
    match output with
    | Native_candidate candidate->M.Proposal(C.Pass_result.make ~limits:(codec work prepared.limits_value)
        ~output:(Some(R.Candidate.to_json candidate)) ~obligations:[] ~source_links:links ())
    | Host_candidate candidate->(match generator_bridge with
        | Some bridge->M.Host_return(bridge.host_proposal work ~output:candidate ~source_links:links)
        | None->fail "Host construction requires its configured candidate bridge.") in
  let verify_layout work context=
    phase_budget work prepared;
    let bound=R.Request.of_json ~limits:(domain_codec work prepared.limits_value) (C.Pass_context.input context) in
    let expected=source_links work prepared.limits_value bound (C.Pass_contract.id contract_value) in
    let limits=codec work prepared.limits_value in
    let links_match=match M.callback_source_links initialized.owner with
      | None->links_equal work limits (C.Pass_context.source_links context) expected
      | Some actual->(match host_links_equal with Some compare->compare work ~actual ~expected
          | None->fail "Construct validator has no exact host source-link comparison capability.") in
    if not links_match || Json.object_fields(C.Pass_context.observation_map context)<>[] then
      fail "Construct pass changed authoritative provenance or introduced unestablished observations.";
    let raw=match C.Pass_context.output context with Some value->value|None->Json.Null in
    let candidate=R.Candidate.of_json ~limits:(domain_codec work prepared.limits_value) raw in
    let checked=Q.check ~parent:work ~limits:(checker_limits prepared.limits_value)
      ~request:bound ~candidate ~registry:prepared.registry_value ~manifests:prepared.manifests_value () in
    let evidence=E.Result.to_json checked in
    let detail=Json.string(Json.field "claim_scope" (Json.object_fields evidence)) in
    M.Decision(C.Check_decision.make ~limits ~outcome:(E.Result.outcome checked) ~detail ~evidence ()) in
  Option.iter (fun observe->observe budget initialized.owner assemble Construct_producer;
    observe budget initialized.owner verify_layout Layout_validator) provider_observer;
  {admission;contract_value;assemble;verify_layout;host_comparison=Option.is_some host_links_equal}
let contract (value:registration)=value.contract_value
let producer (value:registration)=value.assemble
let validators (value:registration)=["layout",value.verify_layout;"layout_composition",value.admission.verify_linkage]
let allow_host_source_links (value:registration)=
  if value.host_comparison then M.allow_host_source_links value.admission.initialized.owner value.verify_layout;
  M.allow_host_source_links value.admission.initialized.owner value.admission.verify_linkage
let finish ~budget (registration:registration) ~record ~result=
  let prepared=registration.admission.initialized.prepared in phase_budget budget prepared;
  let candidate_value=R.Candidate.of_json ~limits:(domain_codec budget prepared.limits_value) (C.Stage_record.payload record) in
  let check_value=Q.check ~parent:budget ~limits:(checker_limits prepared.limits_value)
    ~request:prepared.request_value ~candidate:candidate_value ~registry:prepared.registry_value ~manifests:prepared.manifests_value () in
  {registration;candidate_value;check_value;result_value=result;record_value=record}
let run_internal owner ~budget ?manager_limits ?validator_equivalent ?observer ?provider_observer ?manager_created
    ?register_input ?register_fixed ?generator_bridge ?host_links_equal ~request ~registry ~manifests ()=
  let prepared=prepare ~budget ?manager_limits ~request ~registry ~manifests () in
  let publish work manager=owner:=Some manager;Option.iter (fun callback->callback work manager) manager_created in
  let initialized=create ~budget ?validator_equivalent ?observer ~manager_created:publish prepared in
  let manager=initialized.owner in
  let admission=prepare_admission ~budget ?provider_observer initialized in
  (match register_input with
   | None->M.register_component_input manager (admission_contract admission) ~validators:(admission_validators admission)
   | Some register->register budget manager (admission_contract admission) ~validators:(admission_validators admission));
  allow_admission_host_source_links admission;
  ignore(M.admit_component_input manager ~contract_id:(C.Component_input_contract.id(admission_contract admission))
    ~identity:"components" (R.Request.to_json request));
  let admitted=M.get manager "components" in
  let registration=prepare_registration ~budget ?provider_observer ?generator_bridge ?host_links_equal admission ~admitted in
  (match register_fixed with
   | None->M.register manager (contract registration) ~producer:(producer registration) ~validators:(validators registration)
   | Some register->register budget manager (contract registration) ~producer:(producer registration) ~validators:(validators registration));
  allow_host_source_links registration;
  let record=M.run manager ~pass_id:(C.Pass_contract.id(contract registration)) ~input_id:"components" ~output_id:"construct" () in
  let result=M.result manager ~identity:"construct" ~scope:"reference_construct" in
  finish ~budget registration ~record ~result
let attempt ~budget ?manager_limits ?validator_equivalent ?observer ?provider_observer ?manager_created
    ?register_input ?register_fixed ?generator_bridge ?host_links_equal ~request ~registry ~manifests ()=
  let owner=ref None in
  try Completed(run_internal owner ~budget ?manager_limits ?validator_equivalent ?observer ?provider_observer ?manager_created
      ?register_input ?register_fixed ?generator_bridge ?host_links_equal ~request ~registry ~manifests ()) with
  | (Diagnostic.Error _|M.No_candidate_found _) as error->Failed {error;manager= !owner}
let run ~budget ?manager_limits ?validator_equivalent ?observer ?provider_observer ?manager_created
    ?register_input ?register_fixed ?generator_bridge ?host_links_equal ~request ~registry ~manifests ()=
  match attempt ~budget ?manager_limits ?validator_equivalent ?observer ?provider_observer ?manager_created
      ?register_input ?register_fixed ?generator_bridge ?host_links_equal ~request ~registry ~manifests () with
  | Completed value->value|Failed failure->raise failure.error
let prepared (value:t)=value.registration.admission.initialized.prepared
let manager (value:t)=value.registration.admission.initialized.owner
let candidate (value:t)=value.candidate_value
let check_result (value:t)=value.check_value
let result (value:t)=value.result_value
let record (value:t)=value.record_value
let request value=(prepared value).request_value
let registry value=(prepared value).registry_value
let manifests value=(prepared value).manifests_value
let budget value=(prepared value).budget_value
let manager_limits value=(prepared value).limits_value
