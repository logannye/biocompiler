open Bioc_wire
open Bioc_domain
module M = Bioc_compiler.Pass_manager
module C = Pipeline_contract
module W = Bioc_checker.Work_budget
module U = Reference_construct_pipeline
module R = Reference_construct
module Q = Reference_molecular
module E = Reference_molecular_evidence
module Emit_native = Bioc_compiler.Reference_sequence_emitter
module Check = Bioc_checker.Reference_molecular_check
module Link = Bioc_checker.Composition_check
module X = Verification_exploration.Codec

let implementation_version = "biocompiler.ocaml.reference_molecular_pipeline.v0.1"
let pipeline_version = "biocompiler.exact_cds_pipeline.v0.1"
let resource_profile = "biocompiler.reference_molecular_pipeline.resources.v1"
let str value = Json.String value
let resource_limits = Json.Object [
  "profile",str resource_profile;
  "work",str "one_upstream_owned_lifetime_ancestor_including_all_fresh_checks";
  "manager",M.limits_json M.default_limits;
  "emitter",Emit_native.limits_json Emit_native.default_limits;
  "molecular_checker",Check.limits_json Check.default_limits;
  "composition_checker",Link.limits_json Link.default_limits;
  "record_codecs",C.resource_limits;
  "reference_codecs",X.limits_json R.default_limits;
  "source_correspondence",str "sorted_complete_four_field_tuples_preserving_duplicates";
  "host_execution",str "trusted_callbacks_and_opaque_host_captures_outside_native_cpu_and_json_proof" ]

type provider_role = Emit | Sequence_identity | Encoding_composition
type provider_observer = W.t -> M.t -> M.provider -> provider_role -> unit
type emitted = Native_artifact of Q.Artifact.t | Host_artifact of M.host_value
type emitter = W.t -> input:Json.t -> request:R.Request.t -> construct:R.Candidate.t ->
  registry:Component_registry.t -> manifests:(string * Reference_manifest.t) list -> emitted
type emitter_bridge = {emit:emitter;
  host_proposal:W.t -> output:M.host_value -> source_links:C.Source_link.t list -> M.host_value}
type host_links_equal = W.t -> actual:M.host_value list -> expected:C.Source_link.t list -> bool
type authority = {request:R.Request.t;registry:Component_registry.t;
  manifests:(string * Reference_manifest.t) list}
type final_source_bridge = {check_construct:W.t -> R.Candidate.t;
  return_construct:W.t -> M.host_value}
type prepared = {upstream_value:U.t;authority_value:authority;dependencies_value:(string * string) list}
type profiled = {prepared:prepared;completion:C.Completion_profile.t}
type registration = {profiled:profiled;contract_value:C.Pass_contract.t;
  emit:M.provider;check:M.provider;check_linkage:M.provider;host_links:host_links_equal option}
type t = {upstream_value:U.t;authority_value:authority;returned_construct_value:M.host_value option;candidate_value:Q.Artifact.t;
  checked:E.Result.t;record_value:C.Stage_record.t;result_value:C.Pipeline_result.t}
type failure = {error:exn;manager:M.t}
type attempt = Completed of t | Failed of failure
let upstream (value:t) = value.upstream_value
let construct (value:t) = U.candidate value.upstream_value
let returned_construct (value:t) = value.returned_construct_value
let prepared_authority (value:prepared) = value.authority_value
let build_authority (value:t) = value.authority_value
let candidate (value:t) = value.candidate_value
let check_result (value:t) = value.checked
let record (value:t) = value.record_value
let result (value:t) = value.result_value
let manager (value:t) = U.manager value.upstream_value
let fail message = Diagnostic.fail "pipeline_error" message
let phase_budget budget upstream =
  Diagnostic.require (budget==U.budget upstream) "reference_molecular_pipeline_budget"
    "Molecular continuation received a foreign lifetime budget."
let document_bounds upstream =
  let fields=Json.object_fields(M.limits_json(U.manager_limits upstream)) in
  Z.to_int(Json.integer(Json.field "max_document_bytes" fields)),
  Z.to_int(Json.integer(Json.field "max_document_nodes" fields))
let codec budget upstream =
  let max_bytes,max_nodes=document_bounds upstream in
  C.Codec.make_limits ~max_bytes ~max_nodes ~charge:(W.charge budget) ()
let domain_codec budget upstream =
  let max_bytes,max_nodes=document_bounds upstream in
  let defaults=Json.object_fields(X.limits_json R.default_limits) in
  let ceiling key=Z.to_int(Json.integer(Json.field key defaults)) in
  X.make_limits ~max_bytes:(min max_bytes(ceiling "max_bytes"))
    ~max_nodes:(min max_nodes(ceiling "max_nodes")) ~charge:(W.charge budget) ()
let checker_limits upstream =
  let max_bytes,max_nodes=document_bounds upstream in
  Check.make_limits ~max_input_bytes:(min Limits.max_request_bytes max_bytes)
    ~max_report_bytes:(min Limits.max_response_bytes max_bytes)
    ~max_report_nodes:(min Limits.max_json_nodes max_nodes) ~max_items:(min 100_000 max_nodes) ()
let linkage_limits upstream =
  let max_bytes,max_nodes=document_bounds upstream in
  Link.make_limits ~max_input_bytes:(min Limits.max_request_bytes max_bytes)
    ~max_report_bytes:(min Limits.max_response_bytes max_bytes)
    ~max_report_nodes:(min Limits.max_json_nodes max_nodes) ~max_items:(min 100_000 max_nodes) ()
let emitter_limits upstream =
  let max_bytes,max_nodes=document_bounds upstream in
  Emit_native.make_limits ~max_input_bytes:(min 33_554_432 max_bytes)
    ~max_input_nodes:(min 1_000_000 max_nodes) ~max_output_bytes:(min 16_777_216 max_bytes)
    ~max_output_nodes:(min 1_000_000 max_nodes) ()
let charge_product budget left right =
  if right>0 && left>W.remaining budget/right then W.charge budget(W.remaining budget+1);
  W.charge budget(left*right)
let rec levels count = if count<=1 then 1 else 1+levels(count/2)
let prepare ~budget ?authority upstream =
  phase_budget budget upstream;
  let authority_value=match authority with
    |None->{request=U.request upstream;registry=U.registry upstream;manifests=U.manifests upstream}
    |Some (value:authority)->
        let limits=domain_codec budget upstream in
        ignore(X.measure ~limits(R.Request.to_json value.request));
        ignore(X.measure ~limits(Component_registry.to_json value.registry));
        let _,maximum=document_bounds upstream in
        let count=ref 0 in
        List.iter(fun(key,manifest)->W.charge budget(String.length key+1);
          Diagnostic.require(!count<maximum) "reference_molecular_pipeline_limit"
            "Molecular authority map exceeds its native resource boundary.";
          incr count;ignore(X.measure ~limits(Reference_manifest.to_json manifest)))value.manifests;
        value in
  let limits=codec budget upstream in
  let fingerprint value=C.Codec.fingerprint ~limits value in
  let target=R.Request.target authority_value.request in
  let encoding=Q.Encoding_policy.default ~limits:(domain_codec budget upstream) () in
  let dependencies_value=[
    "human_admission_policy",fingerprint(str Admission.policy_version);
    "molecular_emitter",fingerprint(str Emit_native.emitter_version);
    "molecular_checker",fingerprint(str Check.checker_version);
    "molecular_profile",fingerprint(str(Build_request.Target.payload_format target^"-CDS"));
    "encoding_policy",Q.Encoding_policy.fingerprint encoding;
    "molecular_pipeline",fingerprint(str pipeline_version)] in
  {upstream_value=upstream;authority_value;dependencies_value}
let dependencies (value:prepared) = value.dependencies_value
let prepare_profile ~budget (prepared:prepared) =
  phase_budget budget prepared.upstream_value;
  let completion=C.Completion_profile.make ~limits:(codec budget prepared.upstream_value)
      ~scope:"exact_cds" ~stage:C.Molecular ~schema:Q.Artifact.schema_version
      ~obligations:["reference_authority";"component_linkage";"construct_layout";"emitted_sequence_identity"] () in
  {prepared;completion}
let completion_profile (value:profiled) = value.completion

let source_links budget upstream source pass_name =
  let limits=codec budget upstream in
  let max_bytes,max_nodes=document_bounds upstream in
  let bytes=ref 2 and nodes=ref 1 and count=ref 0 in
  let reverse=List.fold_left(fun links placement ->
    W.charge budget 1;
    List.fold_left(fun links requirement_id ->
      W.charge budget 1;
      let instance_id=R.Placement.instance_id placement in
      let link=C.Source_link.make ~limits ~requirement_id ~source_node_id:instance_id
        ~target_node_id:instance_id ~pass_name () in
      let size=C.Codec.measure ~limits(C.Source_link.to_json link) in
      let separator=if !count=0 then 0 else 1 in
      Diagnostic.require (size.bytes+separator<=max_bytes- !bytes && size.nodes<=max_nodes- !nodes)
        "reference_molecular_pipeline_limit" "Molecular source correspondence exceeds its native resource boundary.";
      bytes:= !bytes+size.bytes+separator;nodes:= !nodes+size.nodes;incr count;
      link::links) links (R.Placement.requirement_ids placement)) [] (R.Candidate.placements source) in
  List.rev reverse

(* Match Python's sorted list of complete four-field tuples, including duplicate
   multiplicity. Sorting canonical SourceLink objects or making a set would use
   the wrong field order or erase a malformed duplicate correspondence. *)
let sorted_links budget limits links =
  let bytes=ref 0 in
  let rows=List.map(fun value ->
    W.charge budget 1;
    ignore(C.Codec.measure ~limits(C.Source_link.to_json value));
    let row=C.Source_link.requirement_id value,C.Source_link.source_node_id value,
      C.Source_link.target_node_id value,C.Source_link.pass_name value in
    let a,b,c,d=row in
    let size=String.length a+String.length b+String.length c+String.length d+4 in
    W.charge budget size;bytes:= !bytes+size;row) links in
  charge_product budget (!bytes+1) (4*(1+levels(List.length rows)));
  let compare (a,b,c,d) (w,x,y,z) =
    let first=String.compare a w in if first<>0 then first else
    let second=String.compare b x in if second<>0 then second else
    let third=String.compare c y in if third<>0 then third else String.compare d z in
  List.sort compare rows
let links_equal budget limits actual expected =
  (* Both complete traversals occur before the original list inequality. *)
  let expected=sorted_links budget limits expected in
  let actual=sorted_links budget limits actual in
  let rec same left right=match left,right with
    | [],[]->true
    | (a,b,c,d)::xs,(w,x,y,z)::ys->
        W.charge budget(String.length a+String.length b+String.length c+String.length d+
          String.length w+String.length x+String.length y+String.length z+8);
        a=w && b=x && c=y && d=z && same xs ys
    | _->false in
  same actual expected
let require_current_providers work dependencies context =
  let actual=C.Pass_context.dependencies context in
  let rec lookup key = function
    | []->None
    | (name,value)::rest->
        W.charge work(String.length key+String.length name+1);
        if key=name then Some value else lookup key rest in
  let rec current = function
    | []->()
    | (key,expected)::rest->
        W.charge work(String.length expected+1);
        (match lookup key actual with
         | Some value->W.charge work(String.length value+1);
             if value<>expected then fail
               "Molecular provider or policy identity changed; rebuild the pipeline with current providers."
         | None->fail "Molecular provider or policy identity changed; rebuild the pipeline with current providers.");
        current rest in
  current dependencies

let prepare_registration ~budget ?provider_observer ?emitter_bridge ?host_links_equal (profiled:profiled) =
  let prepared=profiled.prepared in
  let upstream=prepared.upstream_value in
  phase_budget budget upstream;
  let request=prepared.authority_value.request and registry=prepared.authority_value.registry
  and manifests=prepared.authority_value.manifests in
  let owner=U.manager upstream and limits=codec budget upstream in
  let contract_value=C.Pass_contract.make ~limits ~id:"construct_to_molecular"
      ~version:Emit_native.emitter_version ~input_stage:C.Construct ~output_stage:C.Molecular
      ~input_schema:R.Candidate.schema_version ~output_schema:Q.Artifact.schema_version
      ~profile:"exact_cds" ~profile_version:pipeline_version ~supported_operations:["cds_record"]
      ~checks:[C.Check_spec.make ~limits ~id:"sequence_identity" ~evidence_kind:Realization_evidence.Exact
          ~discharges:["emitted_sequence_identity";"construct_layout"] ();
        C.Check_spec.make ~limits ~id:"encoding_composition" ~evidence_kind:Realization_evidence.Model_conditional
          ~discharges:["component_linkage"] ()]
      ~dependency_keys:(List.map fst prepared.dependencies_value)
      ~consumes_requirements:(Composition.requirement_ids(R.Request.composition request))
      ~changed_properties:["sequence_spelling";"molecular_feature_declarations"]
      ~invalidated_analyses:["construct_layout";"component_linkage";"molecular_behavior"] () in
  let current work context=
    phase_budget work upstream;
    require_current_providers work prepared.dependencies_value context in
  let emit work context =
    current work context;
    let construct=R.Candidate.of_json ~limits:(domain_codec work upstream)(C.Pass_context.input context) in
    let artifact=match emitter_bridge with
      | None->Native_artifact(Emit_native.emit ~parent:work ~limits:(emitter_limits upstream)
          ~request ~construct ~registry ~manifests ())
      | Some (bridge:emitter_bridge)->bridge.emit work ~input:(C.Pass_context.input context) ~request ~construct ~registry ~manifests in
    let links=source_links work upstream construct (C.Pass_contract.id contract_value) in
    match artifact,emitter_bridge with
    | Native_artifact artifact,_->M.Proposal(C.Pass_result.make ~limits:(codec work upstream)
        ~output:(Some(Q.Artifact.to_json artifact)) ~obligations:[] ~source_links:links ())
    | Host_artifact artifact,Some bridge->M.Host_return(bridge.host_proposal work ~output:artifact ~source_links:links)
    | Host_artifact _,None->fail "A host molecular output requires its original proposal builder." in
  let check work context =
    current work context;
    let limits=codec work upstream in
    let construct=R.Candidate.of_json ~limits:(domain_codec work upstream)(C.Pass_context.input context) in
    let expected=source_links work upstream construct (C.Pass_contract.id contract_value) in
    let same=match M.callback_source_links owner with
      | None->links_equal work limits (C.Pass_context.source_links context) expected
      | Some actual->(match host_links_equal with
          | Some compare->compare work ~actual ~expected
          | None->fail "Native validators cannot yet consume deferred host source correspondence.") in
    if not same || Json.object_fields(C.Pass_context.observation_map context)<>[] then
      fail "Molecular emission changed source correspondence or introduced unestablished observations.";
    let raw=match C.Pass_context.output context with Some value->value | None->Json.Null in
    let artifact=Q.Artifact.of_json ~limits:(domain_codec work upstream) raw in
    let checked=Check.check ~parent:work ~limits:(checker_limits upstream)
      ~request ~construct ~candidate:artifact ~registry ~manifests () in
    M.Decision(C.Check_decision.make ~limits ~outcome:(E.Result.outcome checked)
      ~detail:E.claim_scope ~evidence:(E.Result.to_json checked) ()) in
  let check_linkage work context =
    current work context;
    let checked=Link.check ~parent:work ~limits:(linkage_limits upstream)
      ~request:(R.Request.composition request) ~registry () in
    M.Decision(C.Check_decision.make ~limits:(codec work upstream)
      ~outcome:(Composition_evidence.Result.outcome checked)
      ~detail:Composition_evidence.claim_scope ~evidence:(Composition_evidence.Result.to_json checked) ()) in
  Option.iter(fun observe->
    observe budget owner emit Emit;
    observe budget owner check Sequence_identity;
    observe budget owner check_linkage Encoding_composition) provider_observer;
  {profiled;contract_value;emit;check;check_linkage;host_links=host_links_equal}
let contract (value:registration) = value.contract_value
let producer (value:registration) = value.emit
let validators (value:registration) = ["sequence_identity",value.check;"encoding_composition",value.check_linkage]
let allow_host_source_links (value:registration) =
  let manager=U.manager value.profiled.prepared.upstream_value in
  Option.iter(fun _->M.allow_host_source_links manager value.check)value.host_links;
  M.allow_host_source_links manager value.check_linkage
let finish ~budget ?final_source_bridge (registration:registration) ~record ~result =
  let upstream=registration.profiled.prepared.upstream_value in
  phase_budget budget upstream;
  let candidate_value=Q.Artifact.of_json ~limits:(domain_codec budget upstream)(C.Stage_record.payload record) in
  let authority_value=registration.profiled.prepared.authority_value in
  let construct=match final_source_bridge with
    |None->U.candidate upstream
    |Some (bridge:final_source_bridge)->W.charge budget 1;bridge.check_construct budget in
  let checked=Check.check ~parent:budget ~limits:(checker_limits upstream)
    ~request:authority_value.request ~construct ~candidate:candidate_value
    ~registry:authority_value.registry ~manifests:authority_value.manifests () in
  let returned_construct_value=Option.map(fun (bridge:final_source_bridge)->
    W.charge budget 1;bridge.return_construct budget)final_source_bridge in
  {upstream_value=upstream;authority_value;returned_construct_value;candidate_value;checked;record_value=record;result_value=result}
let run_internal ~budget ?authority ?provider_observer ?emitter_bridge ?host_links_equal ?register_fixed ?final_source_bridge upstream =
  let prepared=prepare ~budget ?authority upstream in
  let manager=U.manager upstream in
  List.iter(fun(key,value)->M.set_dependency manager key value)(dependencies prepared);
  let profiled=prepare_profile ~budget prepared in
  M.register_completion_profile manager(completion_profile profiled);
  let registration=prepare_registration ~budget ?provider_observer ?emitter_bridge ?host_links_equal profiled in
  (match register_fixed with
   | None->M.register manager(contract registration) ~producer:(producer registration) ~validators:(validators registration)
   | Some register->register budget manager(contract registration) ~producer:(producer registration) ~validators:(validators registration));
  allow_host_source_links registration;
  let record=M.run manager ~pass_id:(C.Pass_contract.id(contract registration)) ~input_id:"construct" ~output_id:"molecular" () in
  let result=M.result manager ~identity:"molecular" ~scope:"exact_cds" in
  finish ~budget ?final_source_bridge registration ~record ~result
let attempt ~budget ?authority ?provider_observer ?emitter_bridge ?host_links_equal ?register_fixed ?final_source_bridge upstream =
  try Completed(run_internal ~budget ?authority ?provider_observer ?emitter_bridge ?host_links_equal ?register_fixed ?final_source_bridge upstream) with
  | (Diagnostic.Error _ | M.No_candidate_found _) as error->Failed{error;manager=U.manager upstream}
let run ~budget ?authority ?provider_observer ?emitter_bridge ?host_links_equal ?register_fixed ?final_source_bridge upstream =
  match attempt ~budget ?authority ?provider_observer ?emitter_bridge ?host_links_equal ?register_fixed ?final_source_bridge upstream with
  | Completed value->value
  | Failed failure->raise failure.error
