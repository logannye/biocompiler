open Bioc_wire
module R = Bioc_domain.Policy_component_material_request
module S = Bioc_domain.Policy_realization_request
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module U = Bioc_domain.Policy_implementation_binding
module Q = Bioc_domain.Policy_component_assembly_proposal
module K = Bioc_domain.Construction_content
module C = Bioc_domain.Policy_material_contract
module LC = Bioc_domain.Policy_component_material
module L = Bioc_domain.Policy_component_library
module Rule = Bioc_domain.Policy_component_assembly_rule
module Pin = Bioc_domain.Pinned_identity
module Input = Bioc_domain.Policy_material_request
module Admission = Bioc_checker.Policy_realization_admission
module B = Bioc_checker.Policy_implementation_binding_check
module W = Bioc_checker.Work_budget
module P = Policy_preservation_check
module A = Policy_component_assembly_check
module X = Policy_component_context_check
let profile = R.profile
let implementation_version = "biocompiler.ocaml.policy_component_material_check.v0.1"
let candidate_schema = "biocompiler.policy_component_material_candidate.v0.1"
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let text key value = Json.string (get key value)
let items key value = Json.array (get key value)
type checked_material = {request_value:R.t;context_value:X.checked_context;evidence_value:Json.t}
type result = {report_value:Json.t;accepted_value:checked_material option}
let report (value:result) = value.report_value
let accepted (value:result) = value.accepted_value
let request (value:checked_material) = value.request_value
let context (value:checked_material) = value.context_value
let evidence (value:checked_material) = value.evidence_value
let require condition message = Diagnostic.require condition "policy_component_material_catalog_binding" message
let measure budget raw =
  Input.preflight ~max_bytes:8388608 ~max_nodes:250000 ~max_depth:128 ~charge:(W.charge budget) raw
let fingerprint budget raw =
  let bytes=measure budget raw in W.charge budget bytes;
  let encoded=Canonical.encode_bounded ~max_bytes:8388608 raw in
  Diagnostic.require (String.length encoded=bytes) "policy_component_material_accounting"
    "Composition preflight byte inventory differs from the actual encoding.";
  W.charge budget bytes;Canonical.sha256 encoded
let catalog_check budget request checked =
  let original=R.implementation_request request and bridge=R.catalog_binding request in
  let admitted=Admission.request (B.admitted_inputs checked) in
  require (S.fingerprint original=S.fingerprint admitted) "Composition catalog must retain the exact freshly admitted original request.";
  let entry=text "catalog_entry" (B.report checked) in
  let selected=match S.catalog_bindings original with [value] -> value
    | _ -> Diagnostic.fail "policy_component_material_catalog_binding" "The component profile requires one complete original catalog root." in
  W.charge budget 1;
  require (entry=bridge.entry_id && selected.entry_id=bridge.entry_id && selected.entry_version=bridge.entry_version && selected.entry_digest=bridge.entry_digest)
    "Composition is not bound to the complete freshly selected original catalog entry.";
  require (Json.equal (C.provider_ref_to_json bridge.operation) selected.operation && Json.equal (C.provider_ref_to_json bridge.realization) selected.realization)
    "Composition bridge changes the original operation or realization DefinitionRef.";
  let rule=R.composition_rule request in
  require (Json.equal (Pin.to_json bridge.rule) (Pin.to_json (Rule.identity rule))) "Composition bridge does not pin the complete original rule.";
  let count=if R.is_instanced request then List.length (Rule.slots rule) else 2 in
  require (List.length bridge.components=count && List.length (Rule.components rule)=count &&
    List.for_all2 (fun (left:R.component_binding) (right:Rule.component_selection) ->
      W.charge budget 1;left.slot=right.slot && Json.equal (Pin.to_json left.component) (Pin.to_json right.identity) &&
      Json.equal (Pin.to_json left.component) (Pin.to_json (LC.identity (Rule.component rule right.slot)))) bridge.components (Rule.components rule))
    (if R.is_instanced request then "Composition bridge does not pin all complete selected instances in order."
     else "Composition bridge does not pin both complete selected component bodies in order.");
  obj ["status",str "pass";"original_binding",get "catalog_binding" (R.to_json request);"selected_catalog_entry",str entry;
    "component_library_fingerprint",str (fingerprint budget (L.to_json (R.component_library request)));
    "rule_fingerprint",str (fingerprint budget (Rule.to_json rule));
    "premise",str "supplied_conditional_component_composition_and_provider_contracts"]

let obligation_ledger budget request (implementation:P.checked_implementation) (checked:X.checked_context) =
  let binding=P.binding implementation in
  let admitted=B.admitted_inputs binding in
  let original=Admission.request admitted in
  let source=get "source_assessment" (Admission.report admitted) in
  let obligations=List.map Json.string (items "unresolved_obligations" source) in
  let requirements=items "requirements" (P.evidence implementation) in
  let implementation_pin=fingerprint budget (P.evidence implementation)
  and assembly_pin=fingerprint budget (A.evidence (X.assembly checked))
  and context_pin=fingerprint budget (X.evidence checked) in
  let prerequisite_pins = if R.requires_prerequisite_closure request then
    match X.prerequisite_closure checked with
    | None -> Diagnostic.fail "policy_component_material_prerequisite_closure"
        "The prerequisite profile requires a fresh private checked closure before any obligation discharge."
    | Some closure ->
      let evidence=X.prerequisite_evidence closure in
      require (Json.equal (get "original_request_fingerprint" evidence) (str (R.fingerprint request)))
        "Prerequisite closure belongs to a different original material request.";
      ["prerequisites",str (fingerprint budget evidence)]
    else [] in
  let origin=R.catalog_binding request and descriptors=O.descriptors (S.definitions original) in
  let contextual=X.discharges checked in
  let condition value=if value then Some "bounded_implementation_preservation" else None in
  let staged_machine_evidence () =
    let report=P.evidence implementation and behavior=Admission.behavior admitted in
    let coverage=get "coverage" report in
    (* The generic source ledger label does not assert universal termination.
       Discharge only its exact bounded operational interpretation: every
       permitted prefix preserves finite states, terminal behavior and retained
       attempts, and every explicit original hard requirement is satisfied. *)
    text "profile"(B.report binding)=(if R.is_multi_member request then U.multi_product_profile else U.staged_profile) && List.length(B.machines binding)=1 &&
    List.length(B.transitions binding)=7 && text "preservation" report="pass" &&
    get "complete" coverage=Json.Bool true &&
    Json.equal(get "prefixes_started" coverage)(get "matched_prefixes" coverage) &&
    Z.sign(Json.integer(get "histories" coverage))>0 &&
    requirements<>[] && List.map(fun(r:O.requirement)->r.requirement_id)behavior.requirements=List.map(text "id")requirements &&
    List.for_all(fun row->text "status" row="pass" && get "nonvacuous" row=Json.Bool true)requirements in
  let stage obligation =
    if List.exists (fun (value:X.discharge) -> value.obligation=obligation) contextual then Some "declared_context"
    else match obligation with
    | "policy_execution_and_lowering" | "temporal_and_uncertainty_semantics"
    | "persistent_encounter_identity_lifetime" | "state_lifetime_capacity_and_inheritance"
    | "effect_authorization_feedback_and_cancellation" | "arbitration_fairness_and_conflict_resolution"
    | "safety_and_progress_satisfaction" | "requested_assurance_not_established" -> Some "bounded_implementation_preservation"
    | "machine_reachability_termination_and_progress" ->
        if staged_machine_evidence () then Some "bounded_machine_semantics_and_declared_requirements" else None
    | "realizability_and_target_suitability" | "implementation_catalog_applicability" -> Some "conditional_component_context_conjunction"
    | _ ->
      let suffix prefix = if String.starts_with ~prefix obligation then
        Some (String.sub obligation (String.length prefix) (String.length obligation-String.length prefix)) else None in
      match suffix "requirement_satisfaction:" with
      | Some id -> condition (List.exists (fun row -> text "id" row=id && text "status" row="pass") requirements)
      | None -> match suffix "implementation_applicability:" with
        | Some id -> if id=origin.entry_id then Some "conditional_component_context_conjunction" else None
        | None -> match suffix "semantic_definition:" with
          | None -> None
          | Some id ->
            if id=origin.realization.definition_id then Some "conditional_component_context_conjunction"
            else condition (List.exists (fun (value:O.descriptor) -> value.definition.definition_id=id &&
              value.semantics<>O.Capability_deferred) descriptors) in
  let ledger=List.map (fun obligation -> W.charge budget 1;
    match stage obligation with
    | None -> obj ["obligation",str obligation;"status",str "unresolved";"stage",Json.Null;"evidence",Json.Null]
    | Some stage -> let pins=match stage with
      | "bounded_implementation_preservation" -> ["preservation",str implementation_pin]
      | "bounded_machine_semantics_and_declared_requirements" -> ["preservation",str implementation_pin;
          "machine_binding",str(fingerprint budget (B.report binding));
          "state_and_terminal_semantics",str "exact_bounded_source_correspondence";
          "prefixes",str "complete_original_domain";"retained_attempt_identity",str "creation_fixed_injective";
          "universal_termination",str "not_claimed";"progress",str "declared_requirements_only"]
      | "declared_context" -> ["context",str context_pin] @ prerequisite_pins
      | _ -> ["preservation",str implementation_pin;"assembly",str assembly_pin;"context",str context_pin] @ prerequisite_pins in
      obj ["obligation",str obligation;"status",str "discharged";"stage",str stage;"evidence",obj pins]) obligations in
  (* Preserve the exact source inventory, including unknown future obligations.
     A deferred definition needs its specific checked context or catalog stage;
     merely carrying its ID or receiving another stage's PASS cannot discharge it. *)
  ledger,List.for_all (fun row -> text "status" row="discharged") ledger

let check ~request ~behavior ~implementation ~proposed ~assembly_proposal ~candidate ~limits =
  let raw=R.to_json request and allowances=R.budgets request in
  let budget=W.create ~profile:R.resource_profile ~error_code:"policy_component_material_work_limit" ~maximum:allowances.max_work () in
  let request=R.of_json ~charge:(W.charge budget) raw in
  let candidate_raw=obj ["schema_version",str candidate_schema;"behavior",O.behavior_to_json behavior;
    "implementation",I.to_json implementation;"binding",U.to_json proposed;
    "assembly_proposal",Q.to_json assembly_proposal;"construction",K.to_json candidate] in
  let limits_raw=P.limits_to_json limits in
  List.iter (fun raw -> ignore (measure budget raw)) [candidate_raw;limits_raw];
  let original=R.implementation_request request in
  let reserve_preservation () =
    Diagnostic.require ((S.budgets original).max_work<=W.remaining budget) "policy_component_material_work_limit"
      "Composition invocation cannot fund the complete original preservation allowance." in
  let startup_charge phase raw =
    let bytes=measure budget raw in
    (match phase with P.Input -> () | P.Identity -> W.charge budget bytes;W.charge budget bytes);
    reserve_preservation () in
  reserve_preservation ();
  let preservation=P.check_with_startup_charge ~startup_charge ~request:original ~behavior ~implementation ~proposed ~limits in
  let preservation_report=P.report preservation in
  W.charge budget (Z.to_int (Json.integer (get "work" (get "usage" preservation_report))));
  let original_source=get "source_assessment" (get "source_admission" (get "binding" preservation_report)) in
  let unresolved=List.map (fun obligation -> W.charge budget 1;
    obj ["obligation",obligation;"status",str "unresolved";"stage",Json.Null;"evidence",Json.Null])
    (items "unresolved_obligations" original_source) in
  let catalog,assembly_result,context_result,ledger,complete,accepted_context =
    match P.accepted preservation with
    | None -> Json.Null,Json.Null,Json.Null,unresolved,false,None
    | Some checked ->
      let catalog=catalog_check budget request (P.binding checked) in
      let assembly=A.check ~parent:budget ~original ~components:(R.component_library request) ~rule:(R.composition_rule request)
        ~implementation:checked ~proposed:assembly_proposal ~candidate () in
      match A.accepted assembly with
      | None -> catalog,A.report assembly,Json.Null,unresolved,false,None
      | Some assembly ->
        let contextual=X.check ~parent:budget ~request ~assembly () in
        match X.accepted contextual with
        | None -> catalog,A.evidence assembly,X.report contextual,unresolved,false,None
        | Some accepted_context ->
          let ledger,complete=obligation_ledger budget request checked accepted_context in
          catalog,A.evidence assembly,X.report contextual,ledger,complete,Some accepted_context in
  let request_pin=R.fingerprint request and candidate_pin=fingerprint budget candidate_raw in
  let invocation_pin=fingerprint budget (obj ["request",raw;"candidate",candidate_raw;"limits",limits_raw]) in
  let stage value=if value=Json.Null then str "unassessed" else get "outcome" value in
  let prerequisite_profile=R.requires_prerequisite_closure request in
  let prerequisites=if prerequisite_profile && context_result<>Json.Null
    then get "prerequisite_closure" context_result else Json.Null in
  let status=if complete then "checked_component_material" else "not_accepted" in
  let report_base=["schema_version",str (if R.is_multi_member request then "biocompiler.policy_component_material_assessment.v0.3"
    else if prerequisite_profile then "biocompiler.policy_component_material_assessment.v0.2"
    else "biocompiler.policy_component_material_assessment.v0.1");
    "profile",str (R.request_profile request);"implementation",str (if R.is_multi_member request then "biocompiler.ocaml.policy_component_material_check.v0.5"
      else if R.is_two_observation request then "biocompiler.ocaml.policy_component_material_check.v0.4"
      else if prerequisite_profile then "biocompiler.ocaml.policy_component_material_check.v0.3"
      else if R.is_instanced request then "biocompiler.ocaml.policy_component_material_check.v0.2" else implementation_version);"resource_profile",str R.resource_profile;
    "request_fingerprint",str request_pin;"candidate_fingerprint",str candidate_pin;"invocation_fingerprint",str invocation_pin;
    "status",str status;"claim_scope",str "bounded_conditional_policy_via_reusable_components_to_exact_mrna";
    "premise",str "supplied_component_composition_and_provider_contracts";
    "preservation",preservation_report;"catalog",catalog;"assembly",assembly_result;"context",context_result;
    "assembly_status",stage assembly_result;"context_status",stage context_result;
    "obligations",arr ledger;"all_original_obligations_discharged",Json.Bool complete;
    "limits",limits_raw;"budgets",get "budgets" raw;
    "empirical",str "unassessed";"artifact",str "withheld";"export",str "withheld"] @
    (if prerequisite_profile then ["prerequisites",prerequisites;
      "prerequisite_status",(if prerequisites=Json.Null then str "unassessed" else get "status" prerequisites)] else []) in
  let before=allowances.max_work-W.remaining budget in
  let usage value=obj ["unit",str "logical_data_visits_and_child_semantic_work";"charged_work",Json.int value;
    "request_decoding_work",Json.int (R.decoding_work request)] in
  let reserved=obj (report_base@["usage",usage allowances.max_work]) in
  let output=W.create_output ~profile:R.resource_profile ~error_code:"policy_component_material_publication_limit"
    ~max_bytes:allowances.max_report_bytes ~max_nodes:allowances.max_report_nodes () in
  let publication_bytes=measure budget reserved in
  W.charge budget publication_bytes;W.reserve_json output reserved;
  let charged=allowances.max_work-W.remaining budget in
  Diagnostic.require (charged>=before && not (W.exhausted budget)) "policy_component_material_work_limit"
    "Composition aggregate work was exhausted or overflowed.";
  let report_value=obj (report_base@["usage",usage charged]) in
  let accepted_value=match complete,accepted_context with
    | true,Some context_value -> Some {request_value=request;context_value;evidence_value=report_value}
    | _ -> None in
  {report_value;accepted_value}
