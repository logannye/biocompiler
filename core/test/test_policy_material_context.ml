open Bioc_wire
let ()=Printexc.register_printer(function
  |Diagnostic.Error value->Some(Printf.sprintf "Diagnostic.Error(code=%s, path=%s, message=%s)"
    value.code(Option.value ~default:"<none>" value.path)value.message)
  |_->None)
module C=Bioc_domain.Policy_material_context
module MC=Bioc_domain.Policy_material_contract
module D=Bioc_domain.Policy_document
module F=Bioc_domain.Policy_operating_domain
module R=Bioc_domain.Policy_realization_request
module I=Bioc_domain.Policy_implementation
module U=Bioc_domain.Policy_implementation_binding
module K=Bioc_domain.Construction_content
module E=Bioc_domain.Construction_assessment
module AC=Bioc_domain.Architecture_contract
module A=Bioc_checker.Policy_realization_admission
module P=Bioc_realization_checker.Policy_preservation_check
module B=Bioc_realization_checker.Policy_material_binding_check
module Check=Bioc_realization_checker.Policy_material_context_check
module W=Bioc_checker.Work_budget
let checks=ref 0
let require condition message=incr checks;if not condition then failwith message
let str value=Json.String value
let arr values=Json.Array values
let get key raw=Json.field key(Json.object_fields raw)
let fields raw=Json.object_fields raw
let set key value raw=Json.Object((key,value)::List.remove_assoc key(fields raw))
let rec at path raw=match path with []->raw|key::rest->at rest(match raw with Json.Array values->List.nth values(int_of_string key)|_->get key raw)
let rec edit path change raw=match path with []->change raw|key::rest->
  match raw with Json.Array values->arr(List.mapi(fun index value->if index=int_of_string key then edit rest change value else value)values)
  |_->set key(edit rest change(get key raw))raw
let put path value raw=edit path(fun _->value)raw
let repin raw=put["identity";"content_fingerprint"](str(Canonical.fingerprint(get "body" raw)))raw
let repin_providers raw=edit["providers"](fun values->arr(List.map repin(Json.array values)))raw
let rejected code run=incr checks;match run()with
  |_->failwith("Expected rejection: "^code)
  |exception Diagnostic.Error error->require(error.code=code)("Expected "^code^"; got "^error.code)
let read path=let channel=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
  Json.parse_bounded ~max_bytes:4000000 ~max_nodes:100000(really_input_string channel(in_channel_length channel)))
let ()=
  let fixture=read Sys.argv.(1)in
  let source=get "source_case" fixture and expectations=get "context_expectations" fixture in
  let limits=P.limits_of_json(get "limits" fixture)in
  let source_accept case=
    let request=R.of_json(get "request" case)in
    let document=R.document request and library=R.implementation_library request in
    let behavior=Bioc_compiler.Policy_lowering.lower(Bioc_checker.Policy_admission.admit
      ~document ~descriptors:(R.definitions request))in
    (* Metadata-only/new-domain controls receive a new complete original
       request identity; actual graph/configurations/source anchors are fixed. *)
    let implementation=get "implementation" case
      |>put["authority";"source_artifact_digest"](str(D.artifact_digest document))
      |>put["authority";"domain_digest"](str(F.digest(R.operating_domain request)))
      |>put["authority";"implementation_catalog_digest"](str(Canonical.fingerprint(get "implementations"(D.to_json document))))in
    let result=P.check ~request ~behavior ~implementation:(I.of_json ~library implementation)
      ~proposed:(U.of_json(get "proposed" case)) ~limits in
    match P.accepted result with Some accepted->request,accepted,P.report result
      |None->failwith("Original source/graph did not preserve: "^Canonical.encode(P.report result))in
  let request,implementation,preservation=source_accept source in
  require(str(R.fingerprint request)=get "source_request_digest" expectations)"Resolved original source request changed";
  require(at["coverage";"histories"]preservation=Json.int 9)"Original finite domain census changed";
  let contract_raw=get "contract" fixture and context_raw=get "context" fixture in
  let proposed=get "proposed" fixture and candidate=K.of_json(get "candidate" fixture)in
  let bind ?(implementation=implementation) ?(request=request) ?(proposed=proposed) raw=
    let contract=MC.of_json ~library:(R.implementation_library request)raw in
    let proposal=MC.proposal_of_json(put["contract_digest"](str(MC.fingerprint contract))proposed)in
    let result=B.check ~contract ~implementation ~proposed:proposal ~candidate ()in
    match B.accepted result with Some value->value|None->failwith("Expected independently valid material leaf: "^Canonical.encode(B.report result))in
  let binding=bind contract_raw in
  let context=C.of_json context_raw in
  require(C.delivery_group_schema="biocompiler.policy_delivery_group.v0.1" &&
    (C.delivery_group context).assumptions=[])"Policy delivery group lost its explicit empty assumption inventory";
  let legacy_group=get "delivery_group" context_raw|>set "schema_version"(str AC.Delivery_group.schema_version)in
  rejected "invalid_architecture_contract"(fun()->AC.Delivery_group.of_json legacy_group);
  ignore(AC.Delivery_group.of_json(set "assumptions"(arr[str "Legacy supplied premise"])legacy_group));
  rejected "policy_material_context"(fun()->C.of_json(set "delivery_group" legacy_group context_raw));
  require(str(C.fingerprint context)=get "context_digest" expectations)"Frozen context body changed";
  require(str(MC.fingerprint(B.contract binding))=get "material_contract_digest" expectations)"Frozen full resource/component authority changed";
  require(Canonical.encode(C.to_json context)=Canonical.encode context_raw)"Context codec lost original bytes";
  let result=Check.check ~context ~binding ()in
  require(Check.outcome result=E.Pass)("Complete original context failed: "^Canonical.encode(Check.report result));
  let accepted=Option.get(Check.accepted result)in
  let report=Check.report result in
  require(C.fingerprint(Check.context accepted)=C.fingerprint context && Json.equal(Check.evidence accepted)report)"Private context detached from original evidence";
  require(Json.equal(B.evidence(Check.binding accepted))(B.evidence binding))"Private context changed its upstream material result";
  require(List.map(fun(value:Check.discharge)->str value.obligation)(Check.discharges accepted)=Json.array(get "discharged_source_obligations" expectations))
    "Context discharged a different original obligation inventory";
  require(List.length(Json.array(get "derived_demands" report))=14 && List.length(Json.array(get "resource_allocations" report))=14)
    "Independent fourteen-demand census changed";
  let layout=C.record_layout context in
  require(layout.ordered_reasons=1 && layout.ordered_causes=238 && layout.maximum_tick=8 && layout.identifier_bytes=384)
    "Literal complete-record widths changed";
  List.iter(fun key->require(get key report=str "unassessed")("Unexpected broader claim: "^key))["biological_validity";"human_use"];
  require(get "source_receipt_status" report=str "unchanged" && get "export" report=str "withheld")"Context rewrote a source receipt or granted export";
  ignore(Check.replay ~context ~binding report);
  rejected "policy_material_context_assessment_mismatch"(fun()->Check.replay ~context ~binding(set "export"(str "accepted")report));
  let no_accept ?(binding=binding) label code raw=
    let result=Check.check ~context:(C.of_json(repin_providers raw)) ~binding ()in
    require(Check.outcome result<>E.Pass && Check.accepted result=None)(label^" gained context acceptance");
    require(List.mem(str code)(Json.array(get "diagnostics"(Check.report result))))(label^" lost diagnostic "^code)in
  (* Separate original definition identities may describe the same complete
     delivery relation. Every phase reference needs its own full provider;
     agreement of the selected phase alone cannot establish that relation. *)
  let phases=["arrival";"expression";"activation"]in
  let original_delivery=at["request";"document";"program";"semantics";"definitions";"7"]source in
  let delivery_rows=List.map(fun phase->
    let definition=set "id"(str("exclusion.delivery."^phase))original_delivery in
    let reference=at["request";"document";"deployment";"delivery";phase]source
      |>set "id"(get "id" definition)|>set "digest"(str(D.document_digest definition))in
    phase,definition,reference)phases in
  let distinct_source=List.fold_left(fun raw(phase,definition,reference)->raw
    |>edit["request";"document";"program";"semantics";"definitions"](fun values->arr(Json.array values@[definition]))
    |>put["request";"document";"deployment";"delivery";phase]reference)source delivery_rows in
  let distinct_request,distinct_implementation,distinct_preservation=source_accept distinct_source in
  require(R.fingerprint distinct_request<>R.fingerprint request)"Distinct original delivery references reused the original request identity";
  require(Json.equal(at["request";"document";"implementations"]distinct_source)
    (at["request";"document";"implementations"]source) &&
    Json.equal(at["request";"catalog_bindings"]distinct_source)(at["request";"catalog_bindings"]source))
    "Delivery-only authority changed the original implementation catalog or its membership pins";
  require(at["coverage";"histories"]distinct_preservation=Json.int 9)"Distinct delivery references changed the original finite histories";
  let distinct_binding=bind ~request:distinct_request ~implementation:distinct_implementation contract_raw in
  let distinct_providers=Json.array(get "providers" context_raw)@List.map(fun(phase,_,reference)->
    at["providers";"3"]context_raw|>put["identity";"id"](str("context.delivery."^phase))
      |>put["body";"definition"]reference)delivery_rows in
  let extended_available value=value|>set "duration_min"(str "8")|>set "duration_max"(str "8")in
  let interval tick=Json.Object["earliest",str tick;"latest",str tick]in
  let distinct_context=context_raw|>put["clock";"origin_seconds"](str "2")
    |>set "providers"(arr(List.map(fun provider->
      let provider=provider|>edit["body";"availability"]extended_available
        |>edit["body";"capacities"](fun values->arr(List.map(edit["availability"]extended_available)(Json.array values)))in
      let provider=if at["body";"kind"]provider=str "interface"then
        edit["body";"channels"](fun values->arr(List.map(edit["availability"]extended_available)(Json.array values)))provider
        else provider in
      let provider=if at["body";"kind"]provider=str "delivery"then provider
        |>put["body";"arrival"](interval "0")|>put["body";"expression"](interval "1")
        |>put["body";"activation"](interval "2")else provider in
      repin provider)distinct_providers))in
  let distinct_context_value=C.of_json distinct_context in
  require(List.length(C.providers distinct_context_value)=7)"Distinct delivery fixture lost its seven-provider closure";
  let distinct_result=Check.check ~context:distinct_context_value ~binding:distinct_binding ()in
  require(Check.outcome distinct_result=E.Pass && Option.is_some(Check.accepted distinct_result))
    ("Coherent distinct delivery providers failed: "^Canonical.encode(Check.report distinct_result));
  let distinct_report=Check.report distinct_result in
  require(List.length(Json.array(get "source_obligations" distinct_report))=26)
    "Three original delivery definitions did not retain three additional source obligations";
  require(List.map(get "id")(Json.array(get "discharges" distinct_report))=List.map str
    ["chassis_capability_and_delivery_suitability";"semantic_definition:exclusion.chassis";
     "semantic_definition:exclusion.delivery";"semantic_definition:exclusion.delivery.activation";
     "semantic_definition:exclusion.delivery.arrival";"semantic_definition:exclusion.delivery.expression";
     "semantic_definition:exclusion.environment";"semantic_definition:exclusion.interface"])
    "Distinct provider closure did not discharge the exact eight contextual source obligations";
  (* The expression reference's selected expression phase still agrees. Its
     changed arrival remains internally causal, but differs from the complete
     contract relation and must fail after fresh provider re-pinning. *)
  no_accept ~binding:distinct_binding "One phase differs in a distinct delivery provider"
    "complete_original_delivery_phase_relation"
    (put["providers";"5";"body";"arrival";"latest"](str "0.5")distinct_context);
  let renamed_gate=String.make 128 'g'in
  let rec rename_gate=function
    |Json.String "select_gate"->str renamed_gate
    |Json.Array values->arr(List.map rename_gate values)
    |Json.Object values->Json.Object(List.map(fun(key,value)->key,rename_gate value)values)
    |value->value in
  let renamed_source=source|>edit["implementation"]rename_gate|>edit["proposed"]rename_gate in
  let renamed_request,renamed_implementation,_=source_accept renamed_source in
  let renamed_binding=bind ~request:renamed_request ~implementation:renamed_implementation
    ~proposed:(rename_gate proposed)contract_raw in
  no_accept ~binding:renamed_binding "Actual gate identity missing from record derivation"
    "complete_finite_record_layout" context_raw;
  let renamed_context=put["record_layout";"identifier_bytes"](Json.int 640)context_raw in
  let layout_digest=Canonical.fingerprint(get "record_layout" renamed_context)in
  let renamed_context=renamed_context|>edit["providers"](fun raw->arr(List.map(fun provider->
    edit["body";"capacities"](fun capacities->arr(List.map(set "record_layout_digest"(str layout_digest))(Json.array capacities)))provider)
    (Json.array raw)))|>repin_providers in
  let renamed_result=Check.check ~context:(C.of_json renamed_context) ~binding:renamed_binding ()in
  require(Check.outcome renamed_result=E.Pass)
    ("Full alpha-renamed record capacity failed: "^Canonical.encode(Check.report renamed_result));
  List.iter(fun(name,histories,transitions,prefixes)->
    let variant=get name fixture in
    let request,implementation,receipt=source_accept(get "source_case" variant)in
    List.iter(fun(key,count)->require(at["coverage";key]receipt=Json.int count)(name^": changed independent finite census "^key))
      ["histories",histories;"transitions",transitions;"prefixes_started",prefixes];
    let binding=bind ~request ~implementation(get "contract" variant)in
    let raw=get "context" variant in
    let result=Check.check ~context:(C.of_json raw) ~binding ()in
    require(Check.outcome result=E.Pass)(name^": full declared grammar failed "^Canonical.encode(Check.report result));
    no_accept ~binding (name^": smaller environment") "complete_original_environment_grammar"
      (put["providers";"1";"body";"grammar"](at["providers";"1";"body";"grammar"]context_raw)raw))
    ["extended_evidence_case",54,227,228;"reset_feedback_case",27,87,88];
  no_accept "Wrong clock period" "original_exact_clock_relation"(put["clock";"period_seconds"](str "1.0000000000000000000001")context_raw);
  no_accept "Availability starts late" "guaranteed_inclusive_availability:exclusion.chassis"
    (context_raw|>put["providers";"0";"body";"availability";"onset_min"](str "0.0000000000000000000001")
      |>put["providers";"0";"body";"availability";"onset_max"](str "0.0000000000000000000001"));
  no_accept "Availability ends early" "guaranteed_inclusive_availability:exclusion.chassis"
    (put["providers";"0";"body";"availability";"duration_min"](str "5.9999999999999999999999")context_raw);
  no_accept "Shifted origin" "guaranteed_inclusive_availability:exclusion.chassis"(put["clock";"origin_seconds"](str "0.1")context_raw);
  no_accept "Causal expression before arrival" "causal_arrival_expression_activation"
    (put["providers";"3";"body";"arrival";"latest"](str "0.1")context_raw);
  no_accept "Delayed activation" "causal_arrival_expression_activation"
    (put["providers";"3";"body";"activation";"latest"](str "0.1")context_raw);
  no_accept "Different provider recipient" "provider_executor_or_compartment"(put["providers";"0";"body";"recipient";"identity"](str "target-1")context_raw);
  no_accept "Target-bound RNA" "executor_recipient_binding"(put["recipient";"identity"](str "target-1")context_raw);
  no_accept "Wrong compartment" "placement_identity_or_compartment"(put["placement";"compartment"](str "nucleus")context_raw);
  no_accept "Population instead of recipient" "same_concrete_executor_delivery"(put["delivery_group";"same_recipient"](Json.Bool false)context_raw);
  no_accept "Independent member delivery" "independent_delivery_group_unimplemented"(put["delivery_group";"mode"](str "independent")context_raw);
  no_accept "Undischarged delivery assumption" "delivery_count_or_assumptions"
    (put["delivery_group";"assumptions"](arr[str "Assume recipient compatibility"])context_raw);
  no_accept "Wrong chassis body" "complete_original_chassis_body"(put["providers";"0";"body";"chassis";"id"](str "fixture.human_immune")context_raw);
  no_accept "Narrowed environment" "complete_original_environment_grammar"
    (put["providers";"1";"body";"grammar";"feedback_factors";"0";"outcomes"](arr[str "completed"])context_raw);
  no_accept "Removed provider" "complete_original_provider_closure"
    (edit["providers"](fun values->arr(List.tl(Json.array values)))context_raw);
  no_accept "Wrong input target" "complete_input_source_binding"(put["providers";"2";"body";"channels";"0";"subject"](str "executor")context_raw);
  no_accept "Expired input" "guaranteed_inclusive_availability:condition"
    (put["providers";"2";"body";"channels";"0";"availability";"duration_min"](str "5")context_raw);
  no_accept "Missing generation slot" "capacity_slot_inventory"
    (put["providers";"0";"body";"capacities";"0";"slots"](arr[str "e1"])context_raw);
  no_accept "Shared truth pool used twice" "shared_capacity_sum_exceeded"
    (put["providers";"0";"body";"capacities";"0";"quantity"](Json.int 1)context_raw);
  no_accept "Wrong capacity type" "capacity_complete_type_scope_or_layout"
    (put["providers";"0";"body";"capacities";"0";"unit"](str "timer_cells")context_raw);
  no_accept "Wrong capacity scope" "capacity_complete_type_scope_or_layout"
    (put["providers";"0";"body";"capacities";"0";"scope"](str "per_executor")context_raw);
  no_accept "Capacity expires before the horizon" "guaranteed_inclusive_availability:shared.truth"
    (put["providers";"0";"body";"capacities";"0";"availability";"duration_min"](str "5")context_raw);
  no_accept "Truncated causal record" "complete_finite_record_layout"(put["record_layout";"ordered_cause_slots"](Json.int 1)context_raw);
  no_accept "Discarded ordered reasons" "complete_finite_record_layout"(put["record_layout";"ordered_reason_slots"](Json.int 0)context_raw);
  let new_contract change=repin(change contract_raw)|>bind in
  (* This profile has one observation and one feedback input. Their alias is
     rejected by the exact kind/source correspondence before the later generic
     same-channel uniqueness check; no larger input profile is fabricated. *)
  no_accept ~binding:(new_contract(put["body";"input_witnesses";"1";"channel"](str "condition")))
    "Observation and feedback alias one provider channel" "complete_input_source_binding" context_raw;
  let unused_channel=at["providers";"2";"body";"channels";"0"]context_raw|>set "id"(str "unused.condition")in
  no_accept "Supplied provider channel has no actual input witness" "unused_original_input_channel"
    (edit["providers";"2";"body";"channels"](fun values->arr(Json.array values@[unused_channel]))context_raw);
  no_accept ~binding:(new_contract(put["body";"resources";"2";"quantity"](Json.int 1)))
    "Undercounted evidence history" "declared_resource_below_derived_minimum" context_raw;
  no_accept ~binding:(new_contract(put["body";"resources";"7";"quantity"](Json.int 1)))
    "Forgotten prior attempt correlation" "declared_resource_below_derived_minimum" context_raw;
  let without_last raw=arr(List.rev(List.tl(List.rev(Json.array raw))))in
  no_accept ~binding:(new_contract(fun raw->raw|>edit["body";"resources"]without_last|>edit["body";"allocations"]without_last))
    "Missing declared resource and allocation" "complete_derived_resource_inventory" context_raw;
  let extra_resource raw=
    let demand=at["body";"resources";"0"]raw|>set "id"(str "extra.truth")
    and allocation=at["body";"allocations";"0"]raw|>set "demand_id"(str "extra.truth")in
    raw|>edit["body";"resources"](fun values->arr(Json.array values@[demand]))
      |>edit["body";"allocations"](fun values->arr(Json.array values@[allocation]))in
  no_accept ~binding:(new_contract extra_resource)
    "Extra declared resource and allocation" "complete_derived_resource_inventory" context_raw;
  no_accept ~binding:(new_contract(put["body";"resources";"0";"unit"](str "edge_history_cells")))
    "Wrong declared unit" "complete_derived_resource_inventory" context_raw;
  no_accept ~binding:(new_contract(put["body";"resources";"0";"owner";"id"](str "local.select_gate")))
    "Wrong declared owner" "complete_derived_resource_inventory" context_raw;
  no_accept ~binding:(new_contract(put["body";"resources";"0";"scope"](str "per_executor")))
    "Wrong declared scope" "complete_derived_resource_inventory" context_raw;
  let changed_source key value=
    let changed=put["request";"document";"deployment";"payload";key]value source in
    let request,implementation,_=source_accept changed in bind ~request ~implementation contract_raw in
  List.iter(fun key->no_accept ~binding:(changed_source key(Json.int 2))
      ("Different original count "^key)("exact_source_count_required:"^key)context_raw)
    ["design_count";"member_count";"helper_count";"orf_count";"product_count"];
  let quantity=at["request";"document";"assurance";"horizon"]source in
  List.iter(fun key->no_accept ~binding:(changed_source key quantity)("Ignored original "^key)
      ("unimplemented_source_payload_field:"^key)context_raw)["payload_persistence";"effector_persistence"];
  let wrong_request=get "request" source|>put["document";"implementations";"implementations";"0";"chassis"](arr[str "fixture.human_immune"])in
  let entry=at["document";"implementations";"implementations";"0"]wrong_request in
  let wrong_request=R.of_json(put["catalog_bindings";"0";"entry_digest"](str(Canonical.fingerprint entry))wrong_request)in
  let behavior=Bioc_compiler.Policy_lowering.lower(Bioc_checker.Policy_admission.admit
    ~document:(R.document wrong_request) ~descriptors:(R.definitions wrong_request))in
  rejected "policy_realization_chassis"(fun()->A.admit ~request:wrong_request ~behavior);
  rejected "policy_material_context"(fun()->C.of_json
    (context_raw|>put["providers";"0";"body";"capacities";"1";"pool_id"](at["providers";"0";"body";"capacities";"0";"pool_id"]context_raw)|>repin_providers));
  rejected "policy_material_context"(fun()->C.of_json(put["record_layout";"record_shapes";"truth_cells"](arr[str "three_valued_truth"])context_raw));
  rejected "policy_material_context_resource_limit"(fun()->Check.check ~maximum:0 ~context ~binding ());
  let parent=W.create ~profile:"test" ~error_code:"parent_capacity_work" ~maximum:1 ()in
  rejected "parent_capacity_work"(fun()->Check.check ~parent ~context ~binding ());
  let rec cyclic=Json.Array[cyclic]in rejected "molecular_cycle"(fun()->C.of_json cyclic);
  Printf.printf "policy material context: %d literal and fail-closed checks\n" !checks
