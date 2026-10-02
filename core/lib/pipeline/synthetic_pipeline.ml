open Bioc_wire
open Bioc_domain
module C = Pipeline_contract
module X = C.Codec
module W = Bioc_checker.Work_budget
module M = Bioc_compiler.Pass_manager
module A = Synthetic_authority
module R = Realization_request
module E = Realization_evidence
module G = Bioc_synthetic_producer.Generator
module S = Bioc_synthetic_producer.Selection
module Q = Bioc_realization_checker.Checked_request
module K = Bioc_realization_checker.Synthetic_candidate_check
module RC = Bioc_realization_checker.Realization_check
let implementation_version = "biocompiler.ocaml.synthetic_pipeline.v0.1"
let resource_profile = "biocompiler.synthetic_pipeline.resources.v1"
let str value = Json.String value
let obj fields = Json.Object fields
let resource_limits = obj ["profile",str resource_profile;
  "max_document_bytes",Json.int Limits.max_request_bytes;
  "max_document_nodes",Json.int Limits.max_json_nodes;
  "max_source_links",Json.int Limits.max_json_nodes;
  "structural_import_full_traversals",Json.int 128;
  "work",str "one_caller_owned_lifetime_ancestor_including_all_native_leaves";
  "manager",M.limits_json M.default_limits;
  "generator",G.limits_json G.default_limits;
  "selection",S.limits_json S.default_limits;
  "checker",K.limits_json K.default_limits]
type t = {candidate_value:A.Candidate.t;result_value:C.Pipeline_result.t;
  manager_value:M.t;selection_value:Synthetic_selection.Result.t option}
type failure = {error:exn;manager:M.t option}
type attempt = Completed of t | Failed of failure
let candidate value = value.candidate_value
let result value = value.result_value
let manager value = value.manager_value
let selection_result value = value.selection_value
let fail message = Diagnostic.fail "pipeline_error" message
let charge budget amount = W.charge budget amount
let codec budget = X.make_limits ~max_bytes:Limits.max_request_bytes
  ~max_nodes:Limits.max_json_nodes ~charge:(charge budget) ()
let measure budget raw = X.measure ~limits:(codec budget) raw
let fingerprint budget raw = X.fingerprint ~limits:(codec budget) raw
let bounded budget values =
  let rec visit count = function
    | [] -> values
    | _::rest -> charge budget 1;
      Diagnostic.require (count<Limits.max_json_nodes) "synthetic_pipeline_limit"
        "Synthetic pipeline inventory exceeds its native resource boundary.";
      visit (count+1) rest in
  visit 0 values
let map budget f values = List.map (fun value -> charge budget 1;f value) (bounded budget values)
let field key raw = Json.field key (Json.object_fields raw)
(* These existing immutable leaf codecs have no charge argument. Before their
   structural imports, pay a conservative complete-volume traversal envelope
   including bounded canonical ordering, Unicode and numeric conversion. The
   fixed callbacks import their actual manager input/output documents; accepted
   flags and captured expected answers are never substituted for these inputs. *)
let imported budget decode raw =
  let charged=ref 0 in
  let metered=X.make_limits ~max_bytes:Limits.max_request_bytes ~max_nodes:Limits.max_json_nodes
      ~charge:(fun amount -> charge budget amount;charged:= !charged+amount) () in
  (* Meter one complete real encoding, then reserve the remaining 127 complete
     traversals before entering the legacy decoder. No numeric-kind estimate,
     independent allowance, refund or successful-result-only charge is used. *)
  ignore (X.encode ~limits:metered raw);
  if !charged>W.remaining budget/127 then charge budget (W.remaining budget+1);
  charge budget (127 * !charged);
  decode raw
let history_json budget frames =
  let rec collect count bytes nodes reversed = function
    | [] -> Json.Array (List.rev reversed)
    | frame::rest ->
      charge budget 1;
      Diagnostic.require (count<Limits.max_json_nodes) "synthetic_pipeline_limit"
        "Synthetic history exceeds its native resource boundary.";
      let raw=Execution_data.Input_frame.to_json frame in
      let size=measure budget raw in
      let separator=if count=0 then 0 else 1 in
      Diagnostic.require (size.bytes+separator<=Limits.max_request_bytes-bytes &&
        size.nodes<=Limits.max_json_nodes-nodes) "synthetic_pipeline_limit"
        "Synthetic history exceeds its native resource boundary.";
      collect (count+1) (bytes+size.bytes+separator) (nodes+size.nodes) (raw::reversed) rest in
  collect 0 2 1 [] frames
let rebound budget request behavior =
  let build_request=R.build_request request and contract=R.contract request and domain=R.domain request in
  let raw=obj ["schema_version",str R.schema_version;"build_request",Build_request.to_json build_request;
    "behavior",Behavior.to_json behavior;"contract",Realization_contract.Behavior_contract.to_json contract;
    "domain",Realization_contract.Operating_domain.to_json domain] in
  let request=imported budget (fun _ -> R.make ~build_request ~behavior ~contract ~domain) raw in
  Q.request (Q.check ~parent:budget request)
let require_output context = match C.Pass_context.output context with
  | Some value -> value | None -> fail "A successful search must supply a candidate."
let source_links budget candidate pass_name =
  let memberships=A.Candidate.behavior_requirement_ids candidate in
  let bytes=ref 2 and nodes=ref 1 and count=ref 0 and reversed=ref [] in
  let lookup key =
    let rec find = function
      | [] -> Diagnostic.fail "synthetic_pipeline_correspondence" "Candidate has no requirement correspondence for its node."
      | (other,value)::rest ->
        charge budget (String.length key+String.length other+1);
        if key=other then value else find rest in
    find memberships in
  List.iter (fun (node_id,origins) ->
    List.iter (fun requirement_id ->
      List.iter (fun source ->
        Diagnostic.require (!count<Limits.max_json_nodes) "synthetic_pipeline_limit"
          "Synthetic source correspondence exceeds its native resource boundary.";
        let link=C.Source_link.make ~limits:(codec budget) ~requirement_id ~source_node_id:source
          ~target_node_id:node_id ~pass_name () in
        let size=measure budget (C.Source_link.to_json link) in
        let separator=if !count=0 then 0 else 1 in
        Diagnostic.require (size.bytes+separator<=Limits.max_request_bytes- !bytes &&
          size.nodes<=Limits.max_json_nodes- !nodes) "synthetic_pipeline_limit"
          "Synthetic source correspondence exceeds its native resource boundary.";
        bytes:= !bytes+size.bytes+separator;nodes:= !nodes+size.nodes;incr count;
        reversed:=link::!reversed) (bounded budget origins))
      (bounded budget (lookup node_id))) (bounded budget (A.Candidate.source_map candidate));
  List.rev !reversed
let supported_behavior = List.sort String.compare [
  "role";"scope";"signal";"qualitative";"literal";"parameter";
  "and";"or";"not";"at_least";"add";"subtract";"multiply";"divide";"negate";"compare";
  "held_for";"recently";"became_true";"followed_by";"memory";"memory.is_set";"state";"state.is";
  "signature";"secretion";"rule";"action.state_set";"action.report";"action.pulse";
  "action.eliminate";"action.engulf";"action.secrete";"action.present";"action.retain";
  "action.expand";"action.rest";"action.differentiate"]
let run_internal manager_state ~budget ?manager_limits ?validator_equivalent ?observer ?until ?config request frames =
  charge budget 1;
  let build_request=R.build_request request in
  if Build_request.artifact_scope build_request<>Build_request.Synthetic_realization then
    fail "The request must explicitly select synthetic_realization scope.";
  ignore (measure budget (R.to_json request));
  let requested_config=match config with Some value -> value | None -> A.Config.make () in
  ignore (measure budget (A.Config.to_json requested_config));
  let history=history_json budget frames in
  (* Unlike the original Python class, the native envelope is structural-only.
     Re-establish its original frozen-request invariant from complete authority. *)
  let checked=Q.check ~parent:budget request in
  let selection=if Build_request.implementation_constraints build_request<>[] ||
      Build_request.preferences build_request<>[] then
    Some (S.select ~parent:budget ?until ~config:requested_config request frames) else None in
  let config=match selection with
    | None -> requested_config
    | Some selection -> (match Synthetic_selection.Result.candidate selection with
      | Some candidate -> A.Candidate.generator_config candidate
      | None -> fail ("Bounded synthetic selection returned "^Synthetic_selection.Result.outcome selection^
          "; no independently passing candidate was selected. Inspect select_synthetic "^
          "for exact alternatives and rejection reasons; this is not general infeasibility.")) in
  let catalog=A.catalog_for_profile (A.Config.profile_version config) in
  ignore (measure budget (A.Catalog.to_json catalog));
  let text_identity value=fingerprint budget (str value) in
  let dependencies=[
    "human_admission_policy",text_identity Admission.policy_version;
    "request",Build_request.fingerprint build_request;
    "request_artifact",Build_request.artifact_fingerprint build_request;
    "realization_request",R.fingerprint request;
    "realization_artifact",R.artifact_fingerprint request;
    "catalog",A.Catalog.fingerprint catalog;
    "generator",fingerprint budget (A.Config.to_json config);
    "requested_generator",A.Config.fingerprint requested_config;
    "model",text_identity A.model_runner_version;
    "checker",text_identity RC.checker_version;
    "synthetic_acceptance",text_identity K.checker_version;
    "evaluator",text_identity RC.reference_evaluator_version;
    (* Pipeline roots use the original compact UTF-8 identity. The selection
       report's own independently retained ASCII history identity is separate. *)
    "history",fingerprint budget history;
    "horizon",fingerprint budget (match until with None -> Json.Null | Some value -> Runtime_number.to_json value)] in
  let dependencies=dependencies@(match selection with None -> [] | Some value ->
    ["synthetic_selection",Synthetic_selection.Result.fingerprint value;"selection_policy",text_identity S.selection_version]) in
  let limits=codec budget in
  let obligation id scope evidence_kind description=C.Scoped_obligation.make ~limits ~id ~scope ~evidence_kind ~description () in
  let preservation=obligation "behavior_preservation" "synthetic_realization" E.Exact
      "Behavior preserves the independently frozen request." in
  let response=obligation "finite_history_response" "synthetic_realization" E.Model_conditional
      "Synthetic response meets authored contracts on the exercised finite history." in
  let biology=obligation "molecular_behavior" "complete_payload" E.Empirical
      "A molecular implementation and biological applicability remain unestablished." in
  let manager=M.create ~budget ?limits:manager_limits ?validator_equivalent ?observer ~target:(Q.target checked) ~dependencies
      ~completion_profiles:[C.Completion_profile.make ~limits ~scope:"synthetic_realization"
        ~stage:C.Mechanism ~schema:A.Candidate.schema_version
        ~obligations:[C.Scoped_obligation.id preservation;C.Scoped_obligation.id response] ()] () in
  manager_state:=Some manager;
  let requirements=map budget (fun item -> Identity.Requirement.to_string (Behavior.requirement_id item))
      (Behavior.requirements (R.behavior request)) in
  ignore (M.add_build_request manager ~identity:"request" ~requirements ~obligations:[preservation;biology] build_request);
  let lowering=C.Pass_contract.make ~limits ~id:"intent_to_behavior" ~version:"biocompiler.checked_lowering.v0.2"
      ~input_stage:C.Intent ~output_stage:C.Behavior ~input_schema:Build_request.schema_version
      ~output_schema:(Behavior.schema_version Behavior.V0_1) ~profile:"abstract_behavior"
      ~profile_version:(match Build_request.behavior_profile build_request with
        | Build_request.V1 -> Behavior.schema_version Behavior.V0_1 | Build_request.V2 -> Behavior.schema_version Behavior.V0_2)
      ~supported_operations:supported_behavior
      ~checks:[C.Check_spec.make ~limits ~id:"preservation" ~evidence_kind:E.Exact
        ~discharges:[C.Scoped_obligation.id preservation] ()] ~consumes_requirements:requirements () in
  let lower work context =
    let input=imported work Build_request.of_json (C.Pass_context.input context) in
    let behavior=Bioc_compiler.Lowering.lower_with_budget ~parent:work input in
    let links=map work (fun item ->
      let source=Identity.Node.to_string (Behavior.requirement_source_node item) in
      C.Source_link.make ~limits:(codec work) ~requirement_id:(Identity.Requirement.to_string (Behavior.requirement_id item))
        ~source_node_id:source ~target_node_id:source ~pass_name:(C.Pass_contract.id lowering) ())
      (Behavior.requirements behavior) in
    M.Proposal (C.Pass_result.make ~limits:(codec work) ~output:(Some (Behavior.to_json behavior))
      ~obligations:[] ~source_links:links ()) in
  let verify work context =
    let input=imported work Build_request.of_json (C.Pass_context.input context) in
    let behavior=imported work Behavior.of_json (require_output context) in
    let report=Bioc_checker.Lowering_check.check_with_budget ~parent:work ~expected_request:input ~behavior () in
    M.Decision (C.Check_decision.make ~limits:(codec work) ~outcome:E.Pass
      ~detail:"Authoritative request and complete source correspondence verified."
      ~evidence:(obj ["input_request",str (Build_request.fingerprint build_request);
        "behavior",field "behavior_fingerprint" (Bioc_checker.Lowering_check.to_json report)]) ()) in
  M.register manager lowering ~producer:lower ~validators:["preservation",verify];
  M.allow_host_source_links manager verify;
  ignore (M.run manager ~pass_id:(C.Pass_contract.id lowering) ~input_id:"request" ~output_id:"behavior" ());
  let generation=C.Pass_contract.make ~limits ~id:"behavior_to_synthetic" ~version:A.generator_version
      ~input_stage:C.Behavior ~output_stage:C.Mechanism ~input_schema:(Behavior.schema_version Behavior.V0_1)
      ~output_schema:A.Candidate.schema_version ~profile:"synthetic_digital" ~profile_version:(A.Config.profile_version config)
      ~supported_operations:(map budget A.Component.operation (A.Catalog.components catalog))
      ~checks:[C.Check_spec.make ~limits ~id:"finite_history" ~evidence_kind:E.Model_conditional
        ~discharges:[C.Scoped_obligation.id response] ()]
      ~dependency_keys:["realization_request";"catalog";"generator";"model";"checker";"synthetic_acceptance";"history";"horizon"]
      ~required_capabilities:["synthetic_signal_graph"] ~consumes_requirements:requirements ~introduces:[response]
      ~requires_observation_map:true ~operation_path:["mechanism"] () in
  let generate work context =
    let behavior=imported work Behavior.of_json (C.Pass_context.input context) in
    let bound=rebound work request behavior in
    let candidate=G.generate ~parent:work ~config bound in
    (match selection with
     | None -> ()
     | Some selected -> (match Synthetic_selection.Result.candidate selected with
       | Some previous when A.Candidate.fingerprint previous=A.Candidate.fingerprint candidate -> ()
       | _ -> fail "Selected implementation changed during checked generation."));
    let links=source_links work candidate (C.Pass_contract.id generation) in
    M.Proposal (C.Pass_result.make ~limits:(codec work) ~output:(Some (A.Candidate.to_json candidate))
      ~obligations:[] ~source_links:links ~observation_map:(Observation_map.to_json (A.Candidate.observation_map candidate)) ()) in
  let check work context =
    let candidate=imported work A.Candidate.of_json (require_output context) in
    let behavior=imported work Behavior.of_json (C.Pass_context.input context) in
    let bound=rebound work request behavior in
    let result=K.check ~parent:work ?until bound candidate frames in
    let raw=E.Check_result.to_json result in
    M.Decision (C.Check_decision.make ~limits:(codec work) ~outcome:(E.Check_result.outcome result)
      ~detail:(Json.string (field "claim_scope" raw)) ~evidence:raw ()) in
  M.register manager generation ~producer:generate ~validators:["finite_history",check];
  M.allow_host_source_links manager check;
  let record=M.run manager ~pass_id:(C.Pass_contract.id generation) ~input_id:"behavior" ~output_id:"mechanism"
      ~configuration:(A.Config.to_json config) () in
  let result=M.result manager ~identity:"mechanism" ~scope:"synthetic_realization" in
  let candidate=imported budget A.Candidate.of_json (C.Stage_record.payload record) in
  {candidate_value=candidate;result_value=result;manager_value=manager;selection_value=selection}
let attempt ~budget ?manager_limits ?validator_equivalent ?observer ?until ?config request frames =
  let manager_state=ref None in
  try Completed (run_internal manager_state ~budget ?manager_limits ?validator_equivalent ?observer ?until ?config request frames) with
  | (Diagnostic.Error _ | G.Unsupported _ | M.No_candidate_found _) as error ->
      Failed {error;manager= !manager_state}
let run ~budget ?manager_limits ?validator_equivalent ?observer ?until ?config request frames =
  match attempt ~budget ?manager_limits ?validator_equivalent ?observer ?until ?config request frames with
  | Completed value -> value
  | Failed failure -> raise failure.error
