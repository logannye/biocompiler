open Bioc_wire
open Bioc_domain
module M = Bioc_compiler.Pass_manager
module C = Pipeline_contract
module W = Bioc_checker.Work_budget
module S = Synthetic_authority.Candidate
module A = Component_assembly
module Adapter = Bioc_synthetic_producer.Components
module Assembly_check = Bioc_realization_checker.Component_assembly_check
module Behavior_check = Bioc_realization_checker.Component_behavior_check
module Link_check = Bioc_checker.Composition_check
module E = Realization_evidence
module L = Composition_evidence
let implementation_version = "biocompiler.ocaml.component_pipeline.v0.1"
let resource_profile = "biocompiler.component_pipeline.resources.v1"
let str value = Json.String value
let obj values = Json.Object values
let resource_limits = obj [
  "profile",str resource_profile;
  "work",str "one_caller_owned_lifetime_ancestor_including_upstream_and_all_fresh_checks";
  "synthetic_pipeline",Synthetic_pipeline.resource_limits;
  "manager",M.limits_json M.default_limits;
  "adapter",Adapter.limits_json Adapter.default_limits;
  "assembly_checker",Assembly_check.limits_json Assembly_check.default_limits;
  "behavior_checker",Behavior_check.limits_json Behavior_check.default_limits;
  "composition_checker",Link_check.limits_json Link_check.default_limits;
  "record_codecs",C.resource_limits;
  "structural_import_full_traversals",Json.int 128;
  "structural_conversion",str "complete_document_preflight_and_precharged_legacy_decoding" ]
type t = {candidate_value:S.t;assembly_value:A.t;link_value:L.Result.t;
  result_value:C.Pipeline_result.t;manager_value:M.t;
  behavior_value:E.Check_result.t;selection_value:Synthetic_selection.Result.t option}
type failure = {error:exn;manager:M.t option}
type attempt = Completed of t | Failed of failure
let candidate value = value.candidate_value
let assembly value = value.assembly_value
let link_result value = value.link_value
let result value = value.result_value
let manager value = value.manager_value
let behavior_result value = value.behavior_value
let selection_result value = value.selection_value
let fail message = Diagnostic.fail "pipeline_error" message
let rec levels count = if count<=1 then 1 else 1+levels (count/2)
let charge_product budget left right =
  if left>0 && right>W.remaining budget/left then W.charge budget (W.remaining budget+1);
  W.charge budget (left*right)
let codec budget manager_limits =
  let fields=Json.object_fields (M.limits_json manager_limits) in
  C.Codec.make_limits
    ~max_bytes:(Z.to_int (Json.integer (Json.field "max_document_bytes" fields)))
    ~max_nodes:(Z.to_int (Json.integer (Json.field "max_document_nodes" fields)))
    ~charge:(W.charge budget) ()
let decode budget limits decoder raw =
  let fields=Json.object_fields (C.Codec.limits_json limits) in
  let charged=ref 0 in
  let metered=C.Codec.make_limits
      ~max_bytes:(Z.to_int (Json.integer (Json.field "max_bytes" fields)))
      ~max_nodes:(Z.to_int (Json.integer (Json.field "max_nodes" fields)))
      ~charge:(fun amount -> W.charge budget amount;charged:= !charged+amount) () in
  (* Existing opaque domain codecs predate shared work callbacks. Reserve their
     full traversal, canonicalization, bounded registry resolution and sorting
     before entering them. Meter one complete encoding under this same caller,
     then reserve 127 more traversals with the actual scalar/sort costs. *)
  ignore (C.Codec.encode ~limits:metered raw);
  charge_product budget !charged 127;
  decoder raw
let strings limits values =
  List.map (fun value -> C.Codec.charge limits (String.length value+1);str value) values
let source_map limits values =
  obj (List.map (fun (key,values) ->
    C.Codec.charge limits (String.length key+1);
    key,Json.Array (strings limits values)) values)
let source_links limits source pass_id =
  let fields=Json.object_fields (C.Codec.limits_json limits) in
  let maximum_bytes=Z.to_int (Json.integer (Json.field "max_bytes" fields))
  and maximum_nodes=Z.to_int (Json.integer (Json.field "max_nodes" fields)) in
  let bytes=ref 2 and nodes=ref 1 and count=ref 0 in
  List.fold_left (fun links (node_id,requirements) ->
    C.Codec.charge limits (String.length node_id+1);
    List.fold_left (fun links requirement_id ->
      let link=C.Source_link.make ~limits ~requirement_id ~source_node_id:node_id
        ~target_node_id:node_id ~pass_name:pass_id () in
      let size=C.Codec.measure ~limits (C.Source_link.to_json link) in
      let separator=if !count=0 then 0 else 1 in
      Diagnostic.require (size.bytes+separator<=maximum_bytes- !bytes &&
        size.nodes<=maximum_nodes- !nodes) "component_pipeline_limit"
        "Component source correspondence exceeds its native resource boundary.";
      bytes:= !bytes+size.bytes+separator;nodes:= !nodes+size.nodes;incr count;
      link::links) links requirements)
    [] (S.behavior_requirement_ids source) |> List.rev
let make_assembly budget limits request source adapted =
  let composition=Adapter.composition adapted in
  let nodes=List.map (fun instance ->
    let id=Composition.Instance.id instance in
    C.Codec.charge limits (String.length id+32);
    obj ["id",str id;"kind",str "component_instance"]) (Composition.instances composition) in
  let raw=obj ["schema_version",str A.schema_version;
    "registry",Component_registry.to_json (Adapter.registry adapted);
    "composition",Composition.to_json composition;
    "request_fingerprint",str (Realization_request.fingerprint request);
    "candidate_fingerprint",str (S.fingerprint source);
    "behavior_sources",source_map limits (S.source_map source);
    "observation_map",Observation_map.to_json (S.observation_map source);
    "nodes",Json.Array nodes] in
  decode budget limits (fun raw -> A.of_json raw) raw
let link_set budget limits links =
  let encoded=List.map (fun link -> C.Codec.encode ~limits (C.Source_link.to_json link)) links in
  let bytes=List.fold_left (fun count value -> count+String.length value+1) 0 encoded in
  charge_product budget (bytes+1) (1+levels (List.length encoded));
  List.sort_uniq String.compare encoded
let check_assembly ?until ~budget request source assembly frames =
  try Assembly_check.check ?until ~parent:budget request source assembly frames with
  | Diagnostic.Error error when error.code="component_assembly" ->
    (* These independent-checker correspondence failures are PipelineError in
       the original fixed pipeline. Structural imports occur before this call
       and retain their own codec diagnostics. Resource failures remain intact. *)
    fail error.message
let check_behavior ?until ~budget request assembly frames =
  try Behavior_check.check ?until ~parent:budget request assembly frames with
  | Diagnostic.Error error when error.code="component_behavior" -> fail error.message

let run_internal manager_state ~budget ?(manager_limits=M.default_limits) ?until ?config request frames =
  let upstream=match Synthetic_pipeline.attempt ~budget ~manager_limits ?until ?config request frames with
    | Synthetic_pipeline.Completed value -> value
    | Synthetic_pipeline.Failed failure -> manager_state:=failure.manager;raise failure.error in
  let manager_value=Synthetic_pipeline.manager upstream in
  manager_state:=Some manager_value;
  let candidate_value=Synthetic_pipeline.candidate upstream in
  let adapted=Adapter.adapt ?until ~parent:budget request candidate_value frames in
  let limits=codec budget manager_limits in
  let fingerprint raw=C.Codec.fingerprint ~limits raw in
  let dependencies=[
    "human_admission_policy",fingerprint (str Admission.policy_version);
    "component_registry",Component_registry.fingerprint (Adapter.registry adapted);
    "component_lock",Component_registry.Lock.fingerprint (Composition.registry_lock (Adapter.composition adapted));
    "composition_request",Composition.fingerprint (Adapter.composition adapted);
    "component_adapter",fingerprint (str Adapter.adapter_version);
    (* Registry schema and registry policy are the same original v0.2 constant. *)
    "component_registry_policy",fingerprint (str Component_registry.schema_version);
    "component_checker",fingerprint (str Link_check.checker_version);
    "component_model",fingerprint (str Bioc_candidate_runtime.Components.reconstruction_version)] in
  List.iter (fun (key,value) -> M.set_dependency manager_value key value) dependencies;
  let linkage=C.Scoped_obligation.make ~limits ~id:"component_linkage"
      ~scope:"synthetic_components" ~evidence_kind:E.Model_conditional
      ~description:"Locked components preserve the accepted synthetic graph and satisfy declared composition contracts." () in
  let completion=C.Completion_profile.make ~limits ~scope:"synthetic_components" ~stage:C.Components
      ~schema:A.schema_version ~obligations:["behavior_preservation";"finite_history_response";C.Scoped_obligation.id linkage] () in
  M.register_completion_profile manager_value completion;
  let requirements=List.map (fun item ->
    let id=Identity.Requirement.to_string (Behavior.requirement_id item) in
    W.charge budget (String.length id+1);id) (Behavior.requirements (Realization_request.behavior request)) in
  let contract=C.Pass_contract.make ~limits ~id:"synthetic_to_components"
      ~version:Adapter.adapter_version ~input_stage:C.Mechanism ~output_stage:C.Components
      ~input_schema:S.schema_version ~output_schema:A.schema_version
      ~profile:"synthetic_components" ~profile_version:Adapter.adapter_version
      ~supported_operations:["component_instance"]
      ~checks:[C.Check_spec.make ~limits ~id:"composition" ~evidence_kind:E.Model_conditional
        ~discharges:[C.Scoped_obligation.id linkage] ()]
      ~dependency_keys:(List.map fst dependencies) ~consumes_requirements:requirements
      ~required_capabilities:["synthetic_signal_graph"] ~introduces:[linkage]
      ~requires_observation_map:true () in
  let generate work context =
    let limits=codec work manager_limits in
    let source=decode work limits (fun raw -> S.of_json raw) (C.Pass_context.input context) in
    let assembly=make_assembly work limits request source adapted in
    let links=source_links limits source (C.Pass_contract.id contract) in
    M.Proposal (C.Pass_result.make ~limits ~output:(Some (A.to_json assembly)) ~obligations:[]
      ~source_links:links ~observation_map:(Observation_map.to_json (S.observation_map source)) ()) in
  let verify work context =
    let limits=codec work manager_limits in
    let source=decode work limits (fun raw -> S.of_json raw) (C.Pass_context.input context) in
    let expected_links=source_links limits source (C.Pass_contract.id contract) in
    let actual_links=C.Pass_context.source_links context in
    if List.length actual_links<>List.length expected_links ||
       link_set work limits actual_links<>link_set work limits expected_links ||
       C.Codec.fingerprint ~limits (C.Pass_context.observation_map context)<>
       C.Codec.fingerprint ~limits (Observation_map.to_json (S.observation_map source)) then
      fail "Component pass provenance changed authoritative source links or observations.";
    let raw=match C.Pass_context.output context with
      | Some raw -> raw | None -> fail "Component pass requires a candidate assembly." in
    let assembly=decode work limits (fun raw -> A.of_json raw) raw in
    let checked=check_assembly ?until ~budget:work request source assembly frames in
    M.Decision (C.Check_decision.make ~limits ~outcome:(L.Result.outcome checked)
      ~detail:"Declared component contracts checked; finite-history scope retained."
      ~evidence:(L.Result.to_json checked) ()) in
  M.register manager_value contract ~producer:generate ~validators:["composition",verify];
  let record=M.run manager_value ~pass_id:(C.Pass_contract.id contract)
      ~input_id:"mechanism" ~output_id:"components" () in
  let result_value=M.result manager_value ~identity:"components" ~scope:"synthetic_components" in
  let assembly_value=decode budget limits (fun raw -> A.of_json raw) (C.Stage_record.payload record) in
  let link_value=Link_check.check ~parent:budget ~request:(A.composition assembly_value)
      ~registry:(A.registry assembly_value) () in
  let behavior_value=check_behavior ?until ~budget request assembly_value frames in
  {candidate_value;assembly_value;link_value;result_value;manager_value;behavior_value;
   selection_value=Synthetic_pipeline.selection_result upstream}
let attempt ~budget ?manager_limits ?until ?config request frames =
  let manager_state=ref None in
  try Completed (run_internal manager_state ~budget ?manager_limits ?until ?config request frames) with
  | (Diagnostic.Error _ | Bioc_synthetic_producer.Generator.Unsupported _ | M.No_candidate_found _) as error ->
      Failed {error;manager= !manager_state}
let run ~budget ?manager_limits ?until ?config request frames =
  match attempt ~budget ?manager_limits ?until ?config request frames with
  | Completed value -> value
  | Failed failure -> raise failure.error
