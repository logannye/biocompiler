open Bioc_wire
module R=Bioc_domain.Policy_material_request
module S=Bioc_domain.Policy_realization_request
module O=Bioc_domain.Policy_operational
module I=Bioc_domain.Policy_implementation
module U=Bioc_domain.Policy_implementation_binding
module C=Bioc_domain.Policy_material_contract
module K=Bioc_domain.Construction_content
module Pin=Bioc_domain.Pinned_identity
module A=Bioc_checker.Policy_realization_admission
module B=Bioc_checker.Policy_implementation_binding_check
module W=Bioc_checker.Work_budget
module P=Policy_preservation_check
module L=Policy_material_binding_check
module X=Policy_material_context_check
let profile=R.profile
let implementation_version="biocompiler.ocaml.policy_material_check.v0.1"
let candidate_schema="biocompiler.policy_material_candidate.v0.1"
let str value=Json.String value
let obj values=Json.Object values
let arr values=Json.Array values
let get key value=Json.field key(Json.object_fields value)
let text key value=Json.string(get key value)
let items key value=Json.array(get key value)
type checked_material={request_value:R.t;context_value:X.checked_context;evidence_value:Json.t}
type result={report_value:Json.t;accepted_value:checked_material option}
let report(value:result)=value.report_value
let accepted(value:result)=value.accepted_value
let request(value:checked_material)=value.request_value
let context(value:checked_material)=value.context_value
let evidence(value:checked_material)=value.evidence_value
let require condition message=Diagnostic.require condition "policy_material_catalog_binding" message
let measure budget raw=
  R.preflight ~max_bytes:8388608 ~max_nodes:250000 ~max_depth:128 ~charge:(W.charge budget) raw
let fingerprint budget raw=
  let bytes=measure budget raw in
  W.charge budget bytes;
  let encoded=Canonical.encode_bounded ~max_bytes:8388608 raw in
  Diagnostic.require(String.length encoded=bytes)"policy_material_accounting"
    "Preflight canonical byte inventory differs from the actual encoding.";
  W.charge budget bytes;Canonical.sha256 encoded
let catalog_check budget request checked=
  let original=R.implementation_request request and bridge=R.catalog_binding request in
  let entry=text "catalog_entry"(B.report checked)in
  let bindings=S.catalog_bindings original in
  require(List.length bindings=1)"The initial complete material profile supports one original catalog root and one supplied case.";
  let selected=List.hd bindings in
  W.charge budget 1;
  require(entry=bridge.entry_id && selected.entry_id=bridge.entry_id && selected.entry_version=bridge.entry_version &&
    selected.entry_digest=bridge.entry_digest)"Material case is not bound to the complete original selected catalog entry.";
  require(Json.equal(C.provider_ref_to_json bridge.operation)selected.operation &&
    Json.equal(C.provider_ref_to_json bridge.realization)selected.realization)
    "Material bridge changes the source operation or realization definition.";
  require(Json.equal(Pin.to_json bridge.material_contract)(Pin.to_json(C.identity(R.material_contract request))))
    "Original material bridge does not pin the complete supplied case.";
  let raw=get "catalog_binding"(R.to_json request)in
  obj["status",str "pass";"original_binding",raw;"selected_catalog_entry",str entry;
    "contract_fingerprint",str(fingerprint budget(C.to_json(R.material_contract request)));
    "premise",str "supplied_conditional_model_to_sequence_contract"]

let obligation_ledger budget request (implementation:P.checked_implementation) (checked:X.checked_context)=
  let binding=P.binding implementation in
  let admitted=B.admitted_inputs binding in
  let original=A.request admitted in
  let source=get "source_assessment"(A.report admitted)in
  let obligations=List.map Json.string(items "unresolved_obligations" source)in
  let requirements=items "requirements"(P.evidence implementation)in
  let implementation_pin=fingerprint budget(P.evidence implementation)
  and material_pin=fingerprint budget(L.evidence(X.binding checked))
  and context_pin=fingerprint budget(X.evidence checked)in
  let origin=R.catalog_binding request in
  let descriptors=O.descriptors(S.definitions original)in
  let contextual=X.discharges checked in
  let check condition=if condition then Some "bounded_implementation_preservation"else None in
  let stage obligation=
    if List.exists(fun(value:X.discharge)->value.obligation=obligation)contextual then Some "declared_context"
    else match obligation with
    |"policy_execution_and_lowering"|"temporal_and_uncertainty_semantics"|
     "persistent_encounter_identity_lifetime"|"state_lifetime_capacity_and_inheritance"|
     "effect_authorization_feedback_and_cancellation"|"arbitration_fairness_and_conflict_resolution"|
     "safety_and_progress_satisfaction"|"requested_assurance_not_established"->Some "bounded_implementation_preservation"
    |"realizability_and_target_suitability"|"implementation_catalog_applicability"->Some "conditional_material_context_conjunction"
    |_->
      let suffix prefix=if String.starts_with ~prefix obligation then
        Some(String.sub obligation(String.length prefix)(String.length obligation-String.length prefix))else None in
      match suffix "requirement_satisfaction:" with
      |Some id->check(List.exists(fun row->text "id" row=id && text "status" row="pass")requirements)
      |None->match suffix "implementation_applicability:" with
        |Some id->if id=origin.entry_id then Some "conditional_material_context_conjunction"else None
        |None->match suffix "semantic_definition:" with
          |None->None
          |Some id->
            if id=origin.realization.definition_id then Some "conditional_material_context_conjunction"
            else check(List.exists(fun(value:O.descriptor)->value.definition.definition_id=id &&
              value.semantics<>O.Capability_deferred)descriptors)in
  let ledger=List.map(fun obligation->W.charge budget 1;
    match stage obligation with
    |None->obj["obligation",str obligation;"status",str "unresolved";"stage",Json.Null;"evidence",Json.Null]
    |Some stage->let pins=match stage with
      |"bounded_implementation_preservation"->["preservation",str implementation_pin]
      |"declared_context"->["context",str context_pin]
      |_->["preservation",str implementation_pin;"material",str material_pin;"context",str context_pin]in
      obj["obligation",str obligation;"status",str "discharged";"stage",str stage;"evidence",obj pins])obligations in
  (* The complete original inventory remains present. Unknown future obligations
     cannot become acceptance merely because the preceding leaves returned PASS. *)
  ledger,List.for_all(fun row->text "status" row="discharged")ledger

let check ~request ~behavior ~implementation ~proposed ~material_binding ~candidate ~limits=
  let raw=R.to_json request in
  let allowances=R.budgets request in
  let budget=W.create ~profile:R.resource_profile ~error_code:"policy_material_work_limit"
    ~maximum:allowances.max_work ()in
  let request=R.of_json ~charge:(W.charge budget) raw in
  let candidate_raw=obj["schema_version",str candidate_schema;
    "behavior",O.behavior_to_json behavior;"implementation",I.to_json implementation;
    "binding",U.to_json proposed;"material_binding",C.proposal_to_json material_binding;"construction",K.to_json candidate]in
  let limits_raw=P.limits_to_json limits in
  List.iter(fun raw->ignore(measure budget raw))[candidate_raw;limits_raw];
  let original=R.implementation_request request in
  (* Preservation keeps its own original authority/budgets. Reserve its complete
     declared work ceiling before running; account actual charged work afterward.
     No parent limit changes the semantic domain or silently edits child inputs. *)
  let reserve_preservation()=
    Diagnostic.require((S.budgets original).max_work<=W.remaining budget)"policy_material_work_limit"
      "Material invocation cannot fund the complete original preservation allowance."in
  let startup_charge phase raw=
    let bytes=measure budget raw in
    (match phase with P.Input->()|P.Identity->
      (* These two passes are actually performed by the child: canonical
         encoding then SHA-256. Reserve exact bytes before either one. *)
      W.charge budget bytes;W.charge budget bytes);
    reserve_preservation()in
  reserve_preservation();
  let preservation=P.check_with_startup_charge ~startup_charge ~request:original ~behavior ~implementation ~proposed ~limits in
  let preservation_report=P.report preservation in
  let source_work=Z.to_int(Json.integer(get "work"(get "usage" preservation_report)))in
  W.charge budget source_work;
  let original_source=get "source_assessment"(get "source_admission"(get "binding" preservation_report))in
  let unresolved=List.map(fun obligation->W.charge budget 1;
    obj["obligation",obligation;"status",str "unresolved";"stage",Json.Null;"evidence",Json.Null])
    (items "unresolved_obligations" original_source)in
  let catalog,material,context_result,ledger,complete,accepted_context=
    match P.accepted preservation with
    |None->Json.Null,Json.Null,Json.Null,unresolved,false,None
    |Some checked->
      let catalog=catalog_check budget request(P.binding checked)in
      let material=L.check ~parent:budget ~contract:(R.material_contract request) ~implementation:checked
        ~proposed:material_binding ~candidate ()in
      match L.accepted material with
      |None->catalog,L.report material,Json.Null,unresolved,false,None
      |Some binding->
        let contextual=X.check ~parent:budget ~context:(R.context request) ~binding ()in
        match X.accepted contextual with
        |None->catalog,L.report material,X.report contextual,unresolved,false,None
        |Some accepted_context->
          let ledger,complete=obligation_ledger budget request checked accepted_context in
          catalog,L.report material,X.report contextual,ledger,complete,Some accepted_context in
  let request_pin=R.fingerprint request and candidate_pin=fingerprint budget candidate_raw in
  let invocation_pin=fingerprint budget(obj["request",raw;"candidate",candidate_raw;"limits",limits_raw])in
  let stage value=if value=Json.Null then str "unassessed"else get "outcome" value in
  let status=if complete then "checked_material"else "not_accepted"in
  let report_base=["schema_version",str "biocompiler.policy_material_assessment.v0.1";
    "profile",str profile;"implementation",str implementation_version;"resource_profile",str R.resource_profile;
    "request_fingerprint",str request_pin;"candidate_fingerprint",str candidate_pin;
    "invocation_fingerprint",str invocation_pin;
    "status",str status;"claim_scope",str "bounded_conditional_policy_to_exact_mrna";
    "premise",str "supplied_model_to_sequence_and_provider_contracts";
    "preservation",preservation_report;"catalog",catalog;"material",material;"context",context_result;
    "material_status",stage material;"context_status",stage context_result;
    "obligations",arr ledger;"all_original_obligations_discharged",Json.Bool complete;
    "limits",limits_raw;"budgets",get "budgets" raw;
    "empirical",str "unassessed";"artifact",str "withheld";"export",str "withheld"]in
  let before=allowances.max_work-W.remaining budget in
  (* The fixed upper-bound placeholder reserves final counter publication without
     a self-referential byte count; no evidence is trimmed to satisfy the limit. *)
  let usage value=obj["unit",str "logical_data_visits_and_child_semantic_work";"charged_work",Json.int value;
    "request_decoding_work",Json.int(R.decoding_work request)]in
  let reserved=obj(report_base@["usage",usage allowances.max_work])in
  let output=W.create_output ~profile:R.resource_profile ~error_code:"policy_material_publication_limit"
    ~max_bytes:allowances.max_report_bytes ~max_nodes:allowances.max_report_nodes ()in
  let publication_bytes=measure budget reserved in
  W.charge budget publication_bytes;W.reserve_json output reserved;
  let charged=allowances.max_work-W.remaining budget in
  Diagnostic.require(charged>=before)"policy_material_work_limit""Material accounting overflow.";
  let report_value=obj(report_base@["usage",usage charged])in
  let accepted_value=match complete,accepted_context with
    |true,Some context_value->Some{request_value=request;context_value;evidence_value=report_value}
    |_->None in
  {report_value;accepted_value}
