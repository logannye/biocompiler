open Bioc_wire
module R = Bioc_domain.Policy_component_material_request
module X = Bioc_domain.Policy_component_context
module A = Policy_component_assembly_check
module E = Bioc_domain.Construction_assessment
module C = Bioc_domain.Policy_material_context
module MC = Bioc_domain.Policy_material_contract
module LC = Bioc_domain.Policy_component_material
module Rule = Bioc_domain.Policy_component_assembly_rule
module L = Bioc_domain.Policy_component_library
module PC = Policy_preservation_check
module IB = Bioc_checker.Policy_implementation_binding_check
module Admission = Bioc_checker.Policy_realization_admission
module S = Bioc_domain.Policy_realization_request
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module F = Bioc_domain.Policy_operating_domain
module D = Bioc_domain.Policy_document
module N = Bioc_domain.Molecule
module K = Bioc_domain.Construction_content
module PM = Bioc_domain.Policy_mrna_structure
module MS = Bioc_checker.Policy_mrna_structure_check
module T = Bioc_domain.Payload_template
module CT = Bioc_domain.Construction
module AC = Bioc_domain.Architecture_contract
module Id = Bioc_domain.Identity
module Pin = Bioc_domain.Pinned_identity
module M = Bioc_domain.Molecular_record
module W = Bioc_checker.Work_budget
let implementation_version = "biocompiler.ocaml.policy_component_context_check.v0.1"
let max_work = 100000000
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let items key value = Json.array (get key value)
let text key value = Json.string (get key value)
let strings key value = List.map Json.string (items key value)
let ref_equal a b = Json.equal (MC.provider_ref_to_json a) (MC.provider_ref_to_json b)
let fail condition code = Diagnostic.require condition "policy_component_context_fail" code
let supported condition code = Diagnostic.require condition "policy_component_context_unsupported" code
type demand = {key:R.resource_key;quantity:int}
let demand_json (value:demand) = obj ["owner",R.resource_owner_to_json value.key.owner;
  "unit",str (MC.resource_unit_name value.key.unit);"scope",str (MC.resource_scope_name value.key.scope);
  "quantity",Json.int value.quantity]
type discharge = {obligation:string;evidence:Json.t}
type checked_context = {request_value:R.t;context_value:X.t;assembly_value:A.checked_assembly;
  discharge_values:discharge list;evidence_value:Json.t}
type result = {outcome_value:E.outcome;report_value:Json.t;accepted_value:checked_context option}
let request (value:checked_context) = value.request_value
let context (value:checked_context) = value.context_value
let assembly (value:checked_context) = value.assembly_value
let discharges (value:checked_context) = value.discharge_values
let evidence (value:checked_context) = value.evidence_value
let report (value:result) = value.report_value
let outcome (value:result) = value.outcome_value
let accepted (value:result) = value.accepted_value

(* Plain resource reasoning over the actual private implementation and its
   already-checked ordered bijection. No synthetic kernel or I.t is built. *)
let derive ~charge (binding:IB.checked_binding) rule (domain:F.t) =
  let actual=IB.implementation binding in
  let nodes=I.nodes actual and wires=I.wires actual and inputs=I.inputs actual in
  let ordered=List.combine (Rule.node_order rule) nodes in
  let local_owner id =
    charge (List.length ordered);
    match List.find_opt (fun (_, (node:I.node)) -> node.node_id=id) ordered with
    | Some ((reference:Rule.node_ref),_) -> R.Node {slot=reference.slot;node_id=reference.node_id}
    | None -> Diagnostic.fail "policy_component_context_fail" "resource_owner_absent" in
  let node id = charge (List.length nodes);
    match List.find_opt (fun (node:I.node) -> node.node_id=id) nodes with Some node -> node
    | None -> Diagnostic.fail "policy_component_context_fail" "resource_owner_absent" in
  let slots=List.map (fun (value:F.encounter) -> value.identity) domain.encounters in
  let observation_for input = match List.find_opt (fun (value:IB.observation) -> value.input=input) (IB.observations binding) with
    | Some value -> value.source | None -> Diagnostic.fail "policy_component_context_fail" "observation_input_binding" in
  let feedback_for input = match List.find_opt (fun (value:IB.effect_binding) -> value.feedback=input) (IB.effects binding) with
    | Some value -> value.source | None -> Diagnostic.fail "policy_component_context_fail" "feedback_input_binding" in
  let observation_at observation slot tick =
    charge (List.length domain.fixed_observations+List.length domain.observation_factors);
    List.fold_left (fun count (value:F.observation_input) ->
      if value.observation=observation && value.slot=slot && value.available_tick=tick then count+1 else count) 0 domain.fixed_observations +
    List.fold_left (fun count (value:F.observation_factor) ->
      charge (List.length value.slots+List.length value.ticks);
      if value.observation=observation && List.mem slot value.slots && List.mem tick value.ticks then count+value.max_rows_per_slot_tick else count) 0 domain.observation_factors in
  let rows observation =
    let maximum=ref 0 and total=ref 0 in
    List.iter (fun slot -> let slot_total=ref 0 in
      for tick=0 to domain.horizon_ticks do charge 1;
        let count=observation_at observation slot tick in maximum:=max !maximum count;slot_total:= !slot_total+count
      done;total:=max !total !slot_total) slots;
    !maximum,!total in
  let feedback_rows effect_id = charge (List.length domain.feedback_factors);
    List.fold_left (fun count (value:F.feedback_factor) -> if value.effect_id=effect_id then max count value.max_rows_per_attempt_tick else count)
      0 domain.feedback_factors * domain.logical_limits.max_source_attempts in
  let reason_cache=Hashtbl.create 64 in
  let rec reason_width active id = charge 1;
    match Hashtbl.find_opt reason_cache id with Some width -> width | None ->
    fail (not (List.mem id active)) "truth_width_cycle";
    let source port = charge (List.length wires);
      match List.find_opt (fun (wire:I.wire) -> wire.consumer.node_id=id && wire.consumer.port_id=port) wires with
      | Some wire -> reason_width (id::active) wire.producer.node_id
      | None -> Diagnostic.fail "policy_component_context_fail" "truth_width_unbound" in
    let width = match (node id).model.primitive with
      | I.Evidence_bank _ -> 1 | I.Truth_not -> source "in"
      | I.Truth_all count | I.Truth_any count -> List.init count (fun index -> source ("in" ^ string_of_int index)) |> List.fold_left (+) 0
      | I.Truth_equal -> source "left" + source "right" | _ -> 0 in
    supported (width<=4096) "ordered_reason_record_width_exceeds_profile";
    Hashtbl.add reason_cache id width;width in
  let ordered_reasons=max 1 (List.fold_left (fun width (node:I.node) -> max width (reason_width [] node.node_id)) 0 nodes) in
  let demands=ref [] in
  let add unit scope owner quantity = charge 1;
    supported (quantity<=1000000) "derived_resource_quantity_exceeds_profile";
    demands:={key={R.owner=owner;unit;scope};quantity=max 1 quantity}:: !demands in
  let evidence_max=ref 0 and feedback_max=ref 0 and edges=ref 0 and gates=ref 0 and commits=ref 0 and maximum_delta=ref 0 in
  List.iter (fun (input:I.external_input) -> match input.input_kind with
    | I.Evidence_input -> let count,_=rows (observation_for input.input_id) in evidence_max:= !evidence_max+count;
      add MC.Input_rows_per_tick MC.Per_encounter_slot (R.Input input.input_id) count
    | I.Feedback_input -> let count=feedback_rows (feedback_for input.input_id) in feedback_max:= !feedback_max+count;
      add MC.Input_rows_per_tick MC.Per_executor (R.Input input.input_id) count) inputs;
  List.iter (fun (node:I.node) -> let owner=local_owner node.node_id in
    match node.model.primitive with
    | I.Truth_register _ -> add MC.Truth_cells MC.Per_encounter_slot owner 1
    | I.Evidence_bank {freshness_ticks} -> maximum_delta:=max !maximum_delta freshness_ticks;
      let observation=match List.find_opt (fun (value:IB.observation) -> value.bank=node.node_id) (IB.observations binding) with
        | Some value -> value.source | None -> Diagnostic.fail "policy_component_context_fail" "evidence_resource_binding" in
      let _,total=rows observation in add MC.Evidence_records MC.Per_encounter_slot owner total;add MC.Timer_cells MC.Per_encounter_slot owner 1
    | I.Observed_rising -> incr edges;add MC.Edge_history_cells MC.Per_encounter_slot owner 1
    | I.Attempt_bank {capacity;timeout_ticks;_} -> maximum_delta:=max !maximum_delta timeout_ticks;
      add MC.Active_attempt_records MC.Per_encounter_slot owner capacity;
      add MC.Retained_correlation_records MC.Per_executor owner domain.logical_limits.max_source_attempts;
      add MC.Timer_cells MC.Per_encounter_slot owner capacity
    | I.Activation_gate -> incr gates
    | I.Atomic_commit {writes;requests} -> commits:= !commits+writes+requests
    | I.Priority_arbiter _ -> supported false "priority_material_context_unimplemented"
    | _ -> ()) nodes;
  add MC.Generation_counters MC.Per_encounter_slot R.Layout 1;
  add MC.Timer_cells MC.Per_executor R.Layout 1;
  let queue=List.length slots*(2+ !evidence_max+ !edges+ !gates+ !commits)+4*domain.logical_limits.max_source_attempts+ !feedback_max in
  add MC.Control_event_records MC.Per_executor R.Layout queue;
  let keys=R.resource_keys rule in
  fail (List.sort compare (List.map (fun (demand:demand) -> demand.key) !demands)=List.sort compare keys)
    "complete_derived_resource_inventory";
  let local_minima=List.concat_map (fun slot -> List.filter_map (function LC.Input _ -> None | LC.Capacity value -> Some value.minimum)
    (LC.provider_requirements (Rule.component rule slot))) [Rule.Decision;Rule.Driver] @ [1;1;1] in
  let demands=List.map2 (fun key minimum ->
    let demand=List.find (fun (demand:demand) -> demand.key=key) !demands in
    {key;quantity=max minimum demand.quantity}) keys local_minima in
  let max_text=ref 1 in
  let rec strings_in value = charge 1;match value with
    | Json.String text -> max_text:=max !max_text (String.length text)
    | Json.Array values -> List.iter strings_in values
    | Json.Object fields -> List.iter (fun (key,value) -> max_text:=max !max_text (String.length key);strings_in value) fields
    | _ -> () in
  let union=X.ordered_union_json rule in
  strings_in union;strings_in (F.to_json domain);
  List.iter (fun (node:I.node) -> strings_in (str node.node_id)) nodes;
  let layout:X.record_layout={rule=Rule.identity rule;union_digest=Canonical.fingerprint union;domain_digest=F.digest domain;
    slots=List.length slots;generations=domain.logical_limits.max_generations_per_slot;attempts=domain.logical_limits.max_source_attempts;
    horizon=domain.horizon_ticks;maximum_tick=domain.horizon_ticks+ !maximum_delta;ordered_reasons;
    ordered_causes=max 1 (queue*(domain.horizon_ticks+1));identifier_bytes=max 128 (4* !max_text+128)} in
  demands,layout

let check ?parent ?(maximum=max_work) ~request ~assembly () =
  Diagnostic.require (maximum>=0 && maximum<=max_work) "policy_component_context_resource_limit" "Context work budget exceeds its closed ceiling.";
  let budget=match parent with None -> W.create ~profile:X.profile ~error_code:"policy_component_context_resource_limit" ~maximum ()
    | Some parent -> W.nested ~parent ~profile:X.profile ~error_code:"policy_component_context_resource_limit" ~maximum () in
  let charge value=W.charge budget value in charge 1;
  let request=R.of_json ~charge (R.to_json request) in
  let context=R.context request and rule=R.composition_rule request in
  let source=PC.binding (A.implementation assembly) in
  let admitted=IB.admitted_inputs source in
  let original=Admission.request admitted and behavior=Admission.behavior admitted and domain=F.specification (Admission.operating_domain admitted) in
  let document=D.to_json (S.document original) in
  let providers=X.providers context and recipient=X.recipient context and clock=X.clock context in
  let derived=ref [] and resource_rows=ref [] and discharged=ref [] and minimum_layout=ref Json.Null in
  let equal left right = M.check_resources left;M.check_resources right;
    let left=Canonical.encode left and right=Canonical.encode right in charge (String.length left+String.length right);left=right in
  let attempt () =
    fail (equal (S.to_json (R.implementation_request request)) (S.to_json original) &&
      equal (S.to_json (A.original assembly)) (S.to_json original)) "unchanged_original_realization_request";
    fail (equal (L.to_json (R.component_library request)) (L.to_json (A.components assembly))) "unchanged_original_component_library";
    fail (equal (Rule.to_json rule) (Rule.to_json (A.rule assembly))) "unchanged_original_assembly_rule";
    fail (text "catalog_entry" (IB.report source)=(R.catalog_binding request).entry_id) "original_selected_catalog_entry";
    supported(List.length behavior.rules>=1 && List.length behavior.rules<=2 && behavior.machines=[] && List.length behavior.effects=1)
      "closed_truth_context_family_required";
    fail(recipient.role=domain.executor_role && recipient.identity=domain.executor_identity)"executor_recipient_binding";
    fail(List.for_all(fun(value:F.encounter)->value.target<>recipient.identity)domain.encounters)"encounter_target_is_not_delivery_recipient";
    let deployment=get "deployment" document in
    supported(text "route" deployment="in_vivo")"in_vivo_required";
    let payload=get "payload" deployment in
    supported(text "format" payload="RNA")"rna_required";
    List.iter(fun(key,count)->supported(get key payload=Json.int count)("exact_source_count_required:"^key))
      ["design_count",1;"member_count",1;"helper_count",0;"orf_count",1;"product_count",1];
    List.iter(fun key->supported(get key payload=Json.Null)("unimplemented_source_payload_field:"^key))
      ["copy_number";"dose";"payload_persistence";"effector_persistence"];
    let structures=Rule.material_authority rule in
    let member=match PM.member_order structures with [member]->member|_->Diagnostic.fail "policy_component_context_unsupported" "one_rna_required"in
    let template=PM.template structures in
    fail(List.length(T.output_members template)=1 && T.complex_members template=[] && T.amounts template=[])"exact_material_inventory";
    supported(get "helpers"(X.to_json context)=arr [])"delivered_helpers_unimplemented";
    let requirements=T.requirements template in
    fail(List.length requirements=1 && CT.Member_requirement.category(List.hd requirements)=CT.Member_requirement.Payload)
      "one_payload_no_external_helpers";
    let molecule=List.hd(K.Inventory.molecules(Option.get(K.inventory(MS.content(A.structure assembly)))))in
    fail(List.length(PM.members structures)=1 && List.length(LC.products(Rule.component rule Rule.Driver))=1)"one_encoded_product";
    let placement=X.placement context and group=X.delivery_group context in
    fail(AC.Placement.template_id placement=T.id template && AC.Placement.member_id placement=member &&
      Id.Role.to_string(AC.Placement.recipient_role placement)=recipient.role && AC.Placement.compartment placement=recipient.compartment &&
      AC.Placement.delivery_group placement=group.group_id)"placement_identity_or_compartment";
    fail(group.recipient_roles=[recipient.role] && group.same_recipient)
      "same_concrete_executor_delivery";
    supported(group.mode=C.Co_delivered)"independent_delivery_group_unimplemented";
    supported(group.assumptions=[] && group.exact_count=Some 1 &&
      (match group.max_count with None->true|Some value->value>=1))"delivery_count_or_assumptions";
    Option.iter(fun maximum->fail(String.length(N.sequence molecule)<=maximum)"delivery_sequence_length")group.max_total_bases;
    fail(List.for_all(fun(role:N.Role.t)->N.Role.purpose role=N.Role.Requested_payload && N.Role.compartment role=recipient.compartment)
      (K.Inventory.role_instances(Option.get(K.inventory(MS.content(A.structure assembly))))))"material_role_compartment";
    let bindings=items "bindings" deployment in
    supported(List.length bindings=1)"one_executor_chassis_required";
    let chassis_binding=List.hd bindings in
    fail(O.ref_id(get "role" chassis_binding)=recipient.role)"original_chassis_executor";
    let chassis=get "chassis" chassis_binding in
    supported(text "species" chassis="human" && text "recipient_class" chassis="immune")"human_immune_required";
    let entries=items "implementations"(get "implementations" document)in
    fail(List.for_all(fun entry->List.mem(text "id" chassis)(strings "chassis" entry)&&strings "payload_formats" entry=["RNA"])entries)
      "original_catalog_chassis_eligibility";
    let declaration kind id=match List.find_opt(fun(value:D.declaration)->value.kind=kind && value.id=id)(D.declarations(S.document original))with
      |Some value->value.value|None->Diagnostic.fail "policy_component_context_fail" "original_declaration_absent"in
    let original_clock=declaration D.Clock domain.clock in
    fail(Json.equal clock.original_clock original_clock && Q.equal clock.period.seconds(F.resolution(Admission.operating_domain admitted)))"original_exact_clock_relation";
    let start=clock.origin.seconds and finish=Q.add clock.origin.seconds(Q.mul(Q.of_int domain.horizon_ticks)clock.period.seconds)in
    let available label (value:C.availability)=charge 1;
      fail(Q.leq value.onset_max.seconds start && Q.geq(Q.add value.onset_min.seconds value.duration_min.seconds)finish)
        ("guaranteed_inclusive_availability:"^label)in
    let delivery=get "delivery" deployment in
    supported(items "assumptions" delivery=[] && List.mem(text "co_delivery" delivery)["none_required";"same_recipient"])
      "delivery_assumptions_or_group_semantics";
    fail(List.map O.ref_id(items "intended_recipients" delivery)=[recipient.role])"original_delivery_recipient";
    let role=declaration D.Role recipient.role in
    let references=get "operational_model" chassis::items "capabilities" chassis@items "interfaces" chassis@items "environment" chassis@
      items "environment" deployment@items "requires" role@List.map(fun key->get key delivery)["arrival";"expression";"activation";"contract"]in
    let refs=List.sort_uniq compare(List.map MC.provider_ref_of_json references)in
    fail(List.sort compare(List.map(fun(value:C.provider)->value.definition)providers)=refs)"complete_original_provider_closure";
    let resolve reference=charge(List.length providers);match List.find_opt(fun(value:C.provider)->ref_equal value.definition reference)providers with
      |Some value->value|None->Diagnostic.fail "policy_component_context_fail" "original_provider_absent"in
    let definitions=items "definitions"(get "semantics"(D.program(S.document original)))in
    let original_definition (reference:MC.provider_ref)=match List.find_opt(fun raw->text "id" raw=reference.definition_id)definitions with
      |Some raw->fail(text "version" raw=reference.definition_version && D.document_digest raw=reference.definition_digest)"original_definition_pin";raw
      |None->Diagnostic.fail "policy_component_context_fail" "original_definition_absent"in
    List.iter(fun(provider:C.provider)->
      fail(provider.recipient=recipient)"provider_executor_or_compartment";available provider.definition.definition_id provider.available;
      let definition=original_definition provider.definition in
      supported(items "parameters" definition=[] && items "clauses" definition=[] && items "assumptions" definition=[] &&
        get "result" definition=Json.Null && get "executor_kind" definition=Json.Null && get "subject_kind" definition=Json.Null)
        "unimplemented_original_provider_clauses";
      let category=text "category" definition in
      (match provider.body with
       |C.Chassis expected->fail(category="model" && Json.equal expected chassis && ref_equal provider.definition(MC.provider_ref_of_json(get "operational_model" chassis)))"complete_original_chassis_body"
       |C.Environment grammar->fail(category="environment" && Json.equal(F.to_json grammar)(F.to_json domain))"complete_original_environment_grammar"
       |C.Interface value->
         fail(List.mem category["interface";"capability"])"interface_definition_category";
         (match(resolve value.environment).body with C.Environment _->()|_->fail false "interface_environment_body");
         supported(provider.capacities=[])"interface_resource_supply_unimplemented"
       |C.Delivery phases->
         fail(category="delivery")"delivery_definition_category";
         fail(Q.leq phases.arrival.latest.seconds phases.expression.earliest.seconds &&
           Q.leq phases.expression.latest.seconds phases.activation.earliest.seconds && Q.leq phases.activation.latest.seconds start)
           "causal_arrival_expression_activation";
         supported(provider.capacities=[])"delivery_resource_supply_unimplemented");
      List.iter(fun(capacity:C.capacity)->available capacity.capacity_id capacity.available)provider.capacities)providers;
    List.iter(fun key->match(resolve(MC.provider_ref_of_json(get key delivery))).body with C.Delivery _->()|_->fail false("delivery_body:"^key))
      ["arrival";"expression";"activation";"contract"];
    let interval_equal (left:C.interval) (right:C.interval)=
      Q.equal left.earliest.seconds right.earliest.seconds && Q.equal left.latest.seconds right.latest.seconds in
    let same_phases left right=match left,right with
      |C.Delivery left,C.Delivery right->interval_equal left.arrival right.arrival && interval_equal left.expression right.expression && interval_equal left.activation right.activation
      |_->false in
    let declared_delivery=(resolve(MC.provider_ref_of_json(get "contract" delivery))).body in
    List.iter(fun key->fail(same_phases declared_delivery(resolve(MC.provider_ref_of_json(get key delivery))).body)
      "complete_original_delivery_phase_relation")["arrival";"expression";"activation"];
    List.iter(fun raw->match(resolve(MC.provider_ref_of_json raw)).body with C.Environment _->()|_->fail false "environment_body")
      (items "environment" chassis@items "environment" deployment);
    List.iter(fun raw->match(resolve(MC.provider_ref_of_json raw)).body with C.Interface _->()|_->fail false "capability_interface_body")
      (items "requires" role@items "capabilities" chassis@items "interfaces" chassis);
    let used_channels=ref []in
    List.iter(fun(witness:R.input_binding)->
      let provider=resolve witness.provider in
      let channels=match provider.body with C.Interface value->value.channels|_->Diagnostic.fail "policy_component_context_fail" "input_provider_kind"in
      let channel=match List.find_opt(fun(value:C.channel)->value.channel_id=witness.channel)channels with
        |Some value->value|None->Diagnostic.fail "policy_component_context_fail" "input_channel_absent"in
      let expected=match List.find_opt(fun(value:IB.observation)->value.input=witness.input_id)(IB.observations source)with
        |Some value->C.Observation,value.source,value.observer,value.subject
        |None->let value=match List.find_opt(fun(value:IB.effect_binding)->value.feedback=witness.input_id)(IB.effects source)with
            |Some value->value|None->Diagnostic.fail "policy_component_context_fail" "actual_input_absent"in
          let effect_spec=List.find(fun(item:O.effect_spec)->item.effect_id=value.source)behavior.effects in
          C.Feedback,value.source,effect_spec.executor,effect_spec.subject in
      let kind,declaration,observer,subject=expected in
      fail(witness.source=declaration && channel.kind=kind && channel.source=declaration && channel.observer=observer && channel.subject=subject)"complete_input_source_binding";
      available channel.channel_id channel.available;
      let key=Canonical.encode(MC.provider_ref_to_json provider.definition),channel.channel_id in
      fail(not(List.mem key !used_channels))"input_channel_alias";used_channels:=key:: !used_channels)(R.input_bindings request);
    let all_channels=List.concat_map(fun(provider:C.provider)->match provider.body with
      |C.Interface value->List.map(fun(channel:C.channel)->Canonical.encode(MC.provider_ref_to_json provider.definition),channel.channel_id)value.channels|_->[])providers in
    fail(List.sort compare all_channels=List.sort compare !used_channels)"unused_original_input_channel";
    let demands,needed=derive ~charge source rule domain in
    derived:=List.map demand_json demands;minimum_layout:=X.record_layout_to_json needed;
    let declared=X.record_layout context in
    fail (Pin.fingerprint declared.rule=Pin.fingerprint needed.rule && declared.union_digest=needed.union_digest &&
      declared.domain_digest=needed.domain_digest && declared.slots=needed.slots && declared.horizon=needed.horizon)
      "complete_finite_record_identity";
    (* This separately versioned profile permits larger declared record bounds.
       Capacity identity still covers the complete exact declaration. No larger
       bound changes the original finite domain or its preservation evidence. *)
    List.iter (fun (name,declared,minimum) -> fail (declared>=minimum) ("finite_record_bound:" ^ name))
      ["generations",declared.generations,needed.generations;"attempts",declared.attempts,needed.attempts;
       "maximum_tick",declared.maximum_tick,needed.maximum_tick;"ordered_reason_slots",declared.ordered_reasons,needed.ordered_reasons;
       "ordered_cause_slots",declared.ordered_causes,needed.ordered_causes;"identifier_bytes",declared.identifier_bytes,needed.identifier_bytes];
    let bindings=R.resource_bindings request in
    fail (List.map (fun (row:R.resource_binding) -> row.key) bindings=List.map (fun (row:demand) -> row.key) demands)
      "complete_derived_resource_inventory";
    let usage=Hashtbl.create 32 in
    List.iter2 (fun (allocation:R.resource_binding) (demand:demand) ->
      let provider=resolve allocation.provider in
      let capacity=match List.find_opt (fun (capacity:C.capacity) -> capacity.capacity_id=allocation.capacity_id) provider.capacities with
        | Some capacity -> capacity | None -> Diagnostic.fail "policy_component_context_fail" "capacity_absent" in
      fail (capacity.unit=demand.key.unit && capacity.scope=demand.key.scope && capacity.record_layout_digest=X.record_layout_fingerprint declared)
        "capacity_complete_type_scope_or_layout";
      let slots=match demand.key.scope with MC.Per_executor -> [] | MC.Per_encounter_slot -> List.map (fun (encounter:F.encounter) -> encounter.identity) domain.encounters in
      fail (capacity.slots=slots) "capacity_slot_inventory";
      let old=Option.value ~default:0 (Hashtbl.find_opt usage capacity.pool_id) in
      fail (demand.quantity<=capacity.quantity-old) "shared_capacity_sum_exceeded";
      Hashtbl.replace usage capacity.pool_id (old+demand.quantity);
      resource_rows:= !resource_rows@[obj ["demand",demand_json demand;"provider",MC.provider_ref_to_json provider.definition;
        "capacity",str capacity.capacity_id;"pool",str capacity.pool_id;"reserved",Json.int demand.quantity]]) bindings demands;
    List.iter (fun (provider:C.provider) -> List.iter (fun (capacity:C.capacity) ->
      fail (Hashtbl.mem usage capacity.pool_id) "unused_original_capacity") provider.capacities) providers;
    let provider_evidence=arr (List.map (fun (provider:C.provider) -> Pin.to_json provider.identity) providers) in
    let names="chassis_capability_and_delivery_suitability"::List.map (fun (provider:C.provider) -> "semantic_definition:" ^ provider.definition.definition_id) providers in
    discharged:=List.filter_map (fun obligation -> if List.mem obligation names then Some {obligation;evidence=provider_evidence} else None) behavior.unresolved_obligations
  in
  let outcome_value,diagnostics=match attempt () with () -> E.Pass,[]
    | exception Diagnostic.Error error when error.code="policy_component_context_fail" -> E.Fail,[error.message]
    | exception Diagnostic.Error error when error.code="policy_component_context_unsupported" -> E.Unsupported,[error.message] in
  let report_value=obj ["schema_version",str "biocompiler.policy_component_context_assessment.v0.1";
    "profile",str X.profile;"implementation_version",str implementation_version;
    "request_fingerprint",str (R.fingerprint request);"context_fingerprint",str (X.fingerprint context);
    "assembly_fingerprint",str (Canonical.fingerprint (A.evidence assembly));
    "outcome",str (E.outcome_name outcome_value);"claim_scope",str "conditional_component_context_and_complete_record_capacity";
    "record_layout",X.record_layout_to_json (X.record_layout context);"minimum_record_layout", !minimum_layout;
    "derived_demands",arr !derived;"resource_allocations",arr !resource_rows;
    "source_obligations",arr (List.map (fun obligation -> obj ["id",str obligation;
      "context_status",str (if List.exists (fun (value:discharge) -> value.obligation=obligation) !discharged then "discharged" else "outside_stage")]) behavior.unresolved_obligations);
    "discharges",arr (List.map (fun (value:discharge) -> obj ["id",str value.obligation;"evidence",value.evidence]) !discharged);
    "diagnostics",arr (List.map str diagnostics);"source_receipt_status",str "unchanged";
    "biological_validity",str "unassessed";"human_use",str "unassessed";"artifact",str "withheld";"export",str "withheld"] in
  let output=W.create_output ~profile:X.profile ~error_code:"policy_component_context_resource_limit" ~max_bytes:M.max_json_bytes ~max_nodes:M.max_items () in
  W.reserve_json output report_value;charge (2*String.length (Canonical.encode report_value));
  Diagnostic.require (not (W.exhausted budget)) "policy_component_context_resource_limit" "Context work was exhausted.";
  {outcome_value;report_value;accepted_value=(if outcome_value=E.Pass then Some {request_value=request;context_value=context;
    assembly_value=assembly;discharge_values= !discharged;evidence_value=report_value} else None)}
let replay ?parent ?maximum ~request ~assembly saved =
  M.check_resources saved;
  let fresh=check ?parent ?maximum ~request ~assembly () in
  Diagnostic.require (Json.equal saved (report fresh)) "policy_component_context_assessment_mismatch"
    "Composition context receipt differs from fresh checking.";
  fresh
