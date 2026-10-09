open Bioc_wire
module R = Bioc_domain.Policy_component_material_request
module Qc = Bioc_domain.Policy_quantitative_network_contract
module Cc = Bioc_domain.Policy_quantitative_composition_contract
module LC = Bioc_domain.Policy_component_material
module F = Bioc_domain.Policy_component_fragment
module Rule = Bioc_domain.Policy_component_assembly_rule
module D = Bioc_domain.Policy_document
module S = Bioc_domain.Policy_realization_request
module O = Bioc_domain.Policy_operational
module Domain = Bioc_domain.Policy_operating_domain
module I = Bioc_domain.Policy_implementation
module Pin = Bioc_domain.Pinned_identity
module C = Policy_component_context_check
module A = Policy_component_assembly_check
module P = Policy_preservation_check
module B = Bioc_checker.Policy_implementation_binding_check
module Admission = Bioc_checker.Policy_realization_admission
module W = Bioc_checker.Work_budget
module E = Bioc_domain.Construction_assessment
let schema_version="biocompiler.policy_quantitative_assessment.v0.5"
let profile=Cc.profile
let implementation_version="biocompiler.ocaml.policy_quantitative_check.v0.5"
let max_work=128*1024*1024
let str value=Json.String value
let obj value=Json.Object value
type checked_composition={request_value:R.t;evidence_value:Json.t}
type result={report_value:Json.t;outcome_value:E.outcome;accepted_value:checked_composition option}
let report value=value.report_value
let outcome value=value.outcome_value
let accepted value=value.accepted_value
let request value=value.request_value
let evidence value=value.evidence_value

module Make(Charge:sig val charge:int->unit end)=struct
  module Meter=Bioc_checker.Policy_generation_meter.Make(Charge)
  module List=Meter.List
  module String=Meter.String
  let get key value=Meter.Json.field key(Meter.Json.object_fields value)
  let fail condition message=Diagnostic.require condition "policy_quantitative_composition_fail" message
  let same=Meter.Json.equal
  let hash raw=Meter.preflight raw;Meter.Canonical.fingerprint raw
  let one message=function [value]->value|_->Diagnostic.fail "policy_quantitative_composition_fail" message
  let find message predicate values=match List.find_opt predicate values with
    |Some value->value|None->Diagnostic.fail "policy_quantitative_composition_fail" message
  let pin_equal left right=same(Pin.to_json left)(Pin.to_json right)
  let execute request context (composition:Cc.selection)=
    let selected=composition.network in
    Meter.preflight(R.to_json request);Meter.preflight(C.evidence context);
    fail(same(R.to_json request)(R.to_json(C.request context)))"fresh_context_original_request";
    fail(R.is_quantitative_composition request && R.is_multi_site request && R.is_finite_machine request)"quantitative_finite_request_family";
    let assembly=C.assembly context in
    let preservation=A.implementation assembly in
    let binding=P.binding preservation in
    let admitted=B.admitted_inputs binding in
    let original=Admission.request admitted and behavior=Admission.behavior admitted in
    Meter.preflight(O.behavior_to_json behavior);
    let rule=R.composition_rule request and slot=Rule.Instance selected.instance in
    let component=Rule.component rule slot in
    fail(pin_equal selected.component(LC.identity component))"selected_complete_component_identity";
    let coordinator=match (one "one_selected_coordinator_contract"(LC.composition_contracts component)).role with
      |Cc.Coordinator value->value|_->Diagnostic.fail "policy_quantitative_composition_fail" "selected_component_not_coordinator"in
    let local=coordinator.network in
    fail(String.equal selected.contract local.id && same(Qc.to_json selected.mechanism)(Qc.to_json local.mechanism))
      "independent_original_and_selected_mechanism";
    let law=selected.mechanism in
    let machine=one "one_source_machine" behavior.machines
    and observation=one "one_source_observation" behavior.observations
    and effect_value=one "one_source_effect" behavior.effects in
    fail(String.equal machine.machine_id selected.machine && String.equal observation.observation_id selected.observation &&
      String.equal effect_value.effect_id selected.effect_value)"complete_nominal_source_bindings";
    fail(machine.states=List.map(fun(value:Qc.state_value)->value.state)local.values && machine.terminal=[] &&
      machine.lifetime="encounter" && behavior.rules=[] &&
      List.map(fun(s:O.state_store)->s.state_id)behavior.stores=List.map(fun(o:Cc.owner)->o.state)composition.owners)
      "complete_nonterminal_encounter_grid";
    let initial=find "initial_state_absent"(fun(value:Qc.state_value)->String.equal value.state machine.initial)local.values in
    fail(List.for_all2(fun(value:Qc.quantity)(reservoir:Qc.reservoir)->
      Charge.charge 1;Q.equal value.amount reservoir.initial.amount)initial.amounts law.reservoirs)
      "exact_initial_network_vector_and_reset";
    let document=S.document original in
    let declaration kind identity=find "original_declaration_absent"
      (fun(value:D.declaration)->value.kind=kind && String.equal value.id identity)(D.declarations document)in
    let clock=declaration D.Clock observation.clock in
    fail(same(get "resolution" clock.value)law.sample_period.raw)"complete_original_sample_clock";
    fail(observation.value_type=O.Truth_type && Q.equal observation.freshness(O.duration law.sample_period.raw))
      "one_tick_fresh_truth_observation";
    let domain=Domain.specification(Admission.operating_domain admitted) in
    (* Count the complete possible multiplicity, including overlapping factors
       and fixed rows. A factor's own ceiling is not a global sampling bound. *)
    let occupied=ref [] in
    let reserve sample_slot tick rows=
      Charge.charge 1;
      let matches ((other,other_tick),_)=String.equal sample_slot other && tick=other_tick in
      let old=match List.find_opt matches !occupied with Some(_,value)->value|None->0 in
      fail(rows>=0 && old+rows<=1)"at_most_one_fresh_sample_per_slot_tick";
      occupied:=((sample_slot,tick),old+rows)::List.filter(fun row->not(matches row))!occupied in
    List.iter(fun(value:Domain.observation_input)->
      fail(String.equal value.observation selected.observation && value.available_tick=value.observed_tick)
        "fixed_sample_complete_identity_and_zero_age";
      reserve value.slot value.available_tick 1)domain.fixed_observations;
    List.iter(fun(value:Domain.observation_factor)->
      fail(String.equal value.observation selected.observation && value.age_ticks=[0] && value.max_rows_per_slot_tick<=1)
        "factored_sample_complete_identity_and_zero_age";
      List.iter(fun sample_slot->List.iter(fun tick->reserve sample_slot tick value.max_rows_per_slot_tick)value.ticks)value.slots)
      domain.observation_factors;
    let fragment=LC.fragment component in
    let local_node identity=find "local_quantitative_node_absent"
      (fun(value:F.node)->String.equal value.node_id identity)(F.nodes fragment)in
    let bank=local_node local.state_node and input=local_node local.input_node in
    fail(pin_equal bank.model.identity local.state_model && pin_equal input.model.identity local.input_model)
      "complete_local_state_and_input_model_pins";
    fail((match bank.model.primitive with I.Machine_bank value->value.states=machine.states &&
      value.initial=machine.initial && value.terminal=[] |_->false) &&
      input.model.primitive=I.Evidence_bank{freshness_ticks=1} &&
      local.value_port="value" && local.updated_port="updated")"selected_local_quantitative_model_shapes";
    let actual=B.implementation binding in
    let order=Rule.node_order rule and actual_nodes=I.nodes actual in
    fail(List.length order=List.length actual_nodes)"fresh_assembly_ordered_node_bijection";
    let relocated=List.map2(fun(reference:Rule.node_ref)(node:I.node)->reference,node)order actual_nodes in
    let relocate identity=
      let _,node=find "selected_local_node_relocation_absent"
        (fun((reference:Rule.node_ref),_)->reference.slot=slot && String.equal reference.node_id identity)relocated in
      node in
    let actual_bank=relocate local.state_node and actual_input=relocate local.input_node in
    fail(pin_equal actual_bank.model.identity local.state_model && pin_equal actual_input.model.identity local.input_model)
      "complete_actual_state_and_input_model_pins";
    let machine_binding=one "one_bound_machine"(B.machines binding)
    and observation_binding=one "one_bound_observation"(B.observations binding) in
    fail(machine_binding.source=selected.machine && machine_binding.bank=actual_bank.node_id &&
      observation_binding.source=selected.observation && observation_binding.bank=actual_input.node_id)
      "original_source_to_selected_local_state_and_input";
    let updated(expression:O.expression)=expression.op="updated" && expression.args=[] &&
      expression.reference=Some selected.observation && expression.scope=Some observation.subject in
    let positive(expression:O.expression)=expression.op="observe" && expression.args=[] &&
      expression.value_type=Some O.Truth_type && expression.reference=Some selected.observation &&
      expression.scope=Some observation.subject in
    let polarity(expression:O.expression)=if positive expression then Some true else match expression.op,expression.args with
      |"not",[value] when positive value->Some false|_->None in
    List.iter(fun(transition:O.transition)->fail(transition.machine=selected.machine && updated transition.on &&
      List.map(fun(a:O.assignment)->a.state)transition.assignments=List.map(fun(o:Cc.owner)->o.state)composition.owners &&
      Option.is_some(polarity transition.guard))"closed_sampled_transition_form")behavior.transitions;
    let endpoint node_id port_id:I.endpoint={node_id;port_id}in
    let actual_node identity=find "coupled_actual_node_absent"(fun(n:I.node)->n.node_id=identity)actual_nodes in
    let incoming consumer=one "one_coupled_input_driver"(List.filter(fun(w:I.wire)->w.consumer=consumer)(I.wires actual))in
    let relocate_at owner identity=
      let _,node=find "coupled_local_relocation_absent"
        (fun((reference:Rule.node_ref),_)->reference.slot=Rule.Instance owner && reference.node_id=identity)relocated in node in
    let boundary_of fragment id=one "one_declared_coupled_boundary"
      (List.filter(fun(b:F.boundary_port)->b.boundary_id=id)(F.boundary_ports fragment))in
    let actual_boundary owner fragment id=
      let boundary=boundary_of fragment id in
      boundary,endpoint (relocate_at owner boundary.endpoint.node_id).node_id boundary.endpoint.port_id in
    let flow_endpoints=List.map(fun(flow:Cc.flow)->
      let boundary,actual_endpoint=actual_boundary selected.instance fragment flow.boundary in
      fail(boundary.direction=I.Output && boundary.signal_type=I.Truth_value &&
        pin_equal (actual_node actual_endpoint.node_id).model.identity flow.model)
        "complete_selected_transfer_signal_model_and_boundary";
      flow.transfer,actual_endpoint)coordinator.flows in
    let owner_endpoints=List.map2(fun(owner:Cc.owner)(reservoir:Qc.reservoir)->
      let owner_component=Rule.component rule(Rule.Instance owner.instance)in
      fail(pin_equal owner.component(LC.identity owner_component))"complete_selected_reservoir_component_pin";
      let contract=match(one "one_selected_reservoir_contract"(LC.composition_contracts owner_component)).role with
        |Cc.Owner value->value|_->Diagnostic.fail "policy_quantitative_composition_fail" "selected_component_not_state_owner"in
      fail(contract.id=owner.contract && contract.compartment=owner.compartment && owner.compartment=reservoir.compartment)
        "nominal_partitioned_reservoir_ownership";
      let owner_fragment=LC.fragment owner_component in
      let register=relocate_at owner.instance contract.state_node in
      let original_store=find "coupled_source_store_absent"(fun(s:O.state_store)->s.state_id=owner.state)behavior.stores in
      let expected_initial=if Q.equal reservoir.initial.amount Q.zero then I.False else I.True in
      fail((match original_store.initial with O.Truth value->(match value with O.True->I.True|O.False->I.False|O.Unknown->I.Unknown)=expected_initial|_->false) &&
        original_store.lifetime="encounter" && original_store.reset=None &&
        register.model.primitive=I.Truth_register{initial=expected_initial;writers=List.length behavior.transitions} &&
        pin_equal register.model.identity contract.state_model)
        "exact_private_reservoir_initial_reset_and_writers";
      let state_binding=one "one_original_private_state_binding"(List.filter(fun(s:B.state)->s.source=owner.state)(B.states binding))in
      fail(state_binding.register=register.node_id)"original_store_to_selected_private_register";
      let snapshot_boundary,snapshot=actual_boundary owner.instance owner_fragment contract.snapshot_boundary in
      let next_boundary,next=actual_boundary owner.instance owner_fragment contract.next_boundary in
      fail(snapshot_boundary.direction=I.Output && snapshot_boundary.signal_type=I.Truth_value &&
        snapshot=endpoint register.node_id "value" && next_boundary.direction=I.Output && next_boundary.signal_type=I.Truth_value &&
        pin_equal(actual_node next.node_id).model.identity contract.next_model)
        "exact_owner_snapshot_and_next_signal_models";
      let relevant=List.filter(fun(e:Qc.transfer)->e.source=owner.compartment || e.destination=owner.compartment)law.transfers in
      fail(List.map(fun(f:Cc.flow_input)->f.transfer)contract.flows=List.map(fun(e:Qc.transfer)->e.id)relevant)
        "complete_owner_transport_incidence_inventory";
      List.iter(fun(flow:Cc.flow_input)->
        let boundary,consumer=actual_boundary owner.instance owner_fragment flow.boundary in
        let wanted=List.assoc flow.transfer flow_endpoints in
        fail(boundary.direction=I.Input && boundary.signal_type=I.Truth_value && (incoming consumer).producer=wanted)
          "one_original_reserved_signal_drives_both_edge_owners")contract.flows;
      fail(List.map(fun(w:Cc.write)->w.transition)contract.writes=List.map(fun(t:O.transition)->t.transition_id)behavior.transitions)
        "complete_owner_atomic_write_inventory";
      List.iteri(fun index(write:Cc.write)->
        let boundary,consumer=actual_boundary owner.instance owner_fragment write.boundary in
        let transition_binding=find "coupled_write_transition_absent"(fun(t:B.transition)->t.source=write.transition)(B.transitions binding)in
        let coordinate=let rec position n=function []->assert false|(o:Cc.owner)::rest->if o.compartment=owner.compartment then n else position(n+1)rest in position 0 composition.owners in
        fail(boundary.direction=I.Input && boundary.signal_type=I.Truth_write && consumer=endpoint register.node_id("write"^string_of_int index) &&
          (incoming consumer).producer=endpoint transition_binding.commit("write"^string_of_int coordinate) &&
          (incoming(endpoint transition_binding.commit("value"^string_of_int coordinate))).producer=next)
          "same_atomic_commit_uses_owner_next_and_writes_exact_private_state")contract.writes;
      fail(List.for_all(fun(b:F.boundary_port)->
        b.direction<>I.Input || b.signal_type<>I.Truth_write ||
        List.exists(fun(w:Cc.write)->w.boundary=b.boundary_id)contract.writes)(F.boundary_ports owner_fragment) &&
        F.atomic_groups owner_fragment=[])
        "private_state_writes_have_only_the_declared_atomic_coordinator";
      owner,register.node_id,next)composition.owners law.reservoirs in
    let eval before input_value endpoint_value=
      let cache=Hashtbl.create 64 in
      let rec visit active (ep:I.endpoint)=
        Charge.charge 16;
        let key=ep.node_id^"/"^ep.port_id in
        fail(not(List.mem key active))"acyclic_selected_combinational_transport";
        match Hashtbl.find_opt cache key with Some value->value|None->
        let node=actual_node ep.node_id in
        let operand port=visit(key::active)(incoming(endpoint ep.node_id port)).producer in
        let negate=function I.True->I.False|I.False->I.True|I.Unknown->I.Unknown in
        let values count=List.init count(fun n->operand("in"^string_of_int n))in
        let value=match node.model.primitive with
        |I.Truth_register _->
          fail(ep.port_id="value")"reservoir_snapshot_value_port";
          let rec lookup index=function []->Diagnostic.fail "policy_quantitative_composition_fail" "unselected_private_state_dependency"
            |(_,register,_)::rest->if register=ep.node_id then (if Q.sign(List.nth before index)>0 then I.True else I.False)else lookup(index+1)rest in lookup 0 owner_endpoints
        |I.Evidence_bank _->fail(ep.node_id=actual_input.node_id && ep.port_id="value")"original_sample_signal_dependency";
          (match input_value with Some true->I.True|Some false->I.False|None->I.Unknown)
        |I.Truth_constant value->fail(ep.port_id="out")"constant_output";value
        |I.Truth_not->fail(ep.port_id="out")"not_output";negate(operand "in")
        |I.Truth_all count->fail(ep.port_id="out")"all_output";let vs=values count in
          if List.mem I.False vs then I.False else if List.mem I.Unknown vs then I.Unknown else I.True
        |I.Truth_any count->fail(ep.port_id="out")"any_output";let vs=values count in
          if List.mem I.True vs then I.True else if List.mem I.Unknown vs then I.Unknown else I.False
        |I.Truth_equal->fail(ep.port_id="out")"equal_output";let a=operand "left"and b=operand "right"in
          if a=I.Unknown || b=I.Unknown then I.Unknown else if a=b then I.True else I.False
        |_->Diagnostic.fail "policy_quantitative_composition_fail" "unsupported_selected_combinational_dependency"in
        Hashtbl.add cache key value;value in
      visit [] endpoint_value in
    let crossings=ref []and moving=ref 0 in
    let minimum left right=if Q.compare left right<=0 then left else right in
    let quanta amount=
      let count=Q.div amount law.quantum.amount in
      fail(Z.equal(Q.den count)Z.one && Q.sign count>=0 && Q.compare count(Q.of_int 15)<=0)
        "exact_network_quantum_grid";
      Z.to_int(Q.num count)in
    let vector amounts=Json.Array(List.map(fun amount->Json.int(quanta amount))amounts)in
    let indexed=List.mapi(fun index(reservoir:Qc.reservoir)->reservoir.compartment,index)law.reservoirs in
    let coordinate identity=snd(find "network_compartment_coordinate_absent"(fun(id,_)->id=identity)indexed)in
    let target=coordinate law.threshold.compartment in
    let capacities=Array.of_list(List.map(fun(reservoir:Qc.reservoir)->reservoir.capacity.amount)law.reservoirs)in
    let edges=List.map(fun(edge:Qc.transfer)->edge,coordinate edge.source,coordinate edge.destination)law.transfers in
    let table=List.concat_map(fun(value:Qc.state_value)->List.map(fun input_value->
      Charge.charge 96;
      let before=List.map(fun(amount:Qc.quantity)->amount.amount)value.amounts in
      let snapshot=Array.of_list before in
      let outgoing=Array.make(Array.length snapshot)Q.zero and incoming=Array.make(Array.length snapshot)Q.zero in
      (* Reservations read the immutable prestate. Incoming stock and outgoing
         freed room never become available to another edge in this sample. *)
      let allocations=List.map(fun((edge:Qc.transfer),source,destination)->
        Charge.charge 16;
        let amount=if input_value<>Some edge.enabled_when then Q.zero else (
          let stock=Q.sub snapshot.(source) outgoing.(source)
          and room=Q.sub(Q.sub capacities.(destination) snapshot.(destination))incoming.(destination)in
          fail(Q.sign stock>=0 && Q.sign room>=0)"nonnegative_unreserved_stock_and_room";
          minimum edge.amount.amount(minimum stock room))in
        outgoing.(source)<-Q.add outgoing.(source)amount;
        incoming.(destination)<-Q.add incoming.(destination)amount;
        edge,amount)edges in
      let after=List.mapi(fun index amount->
        Charge.charge 4;
        let next=Q.add(Q.sub amount outgoing.(index))incoming.(index)in
        fail(Q.sign next>=0 && Q.compare next capacities.(index)<=0)"reserved_atomic_vector_capacity";
        next)before in
      List.iter(fun((edge:Qc.transfer),amount)->
        let observed=eval before input_value(List.assoc edge.id flow_endpoints)in
        fail((match input_value with None->observed<>I.True|Some _->observed=(if Q.sign amount>0 then I.True else I.False)))
          "actual_selected_edge_signal_matches_independent_prestate_reservation")allocations;
      (match input_value with None->()|Some _->List.iteri(fun index(_,_,next)->
        fail(eval before input_value next=(if Q.sign(List.nth after index)>0 then I.True else I.False))
          "actual_selected_owner_next_matches_reserved_conserved_vector")owner_endpoints);
      let sum values=List.fold_left Q.add Q.zero values in
      fail(Q.equal(sum before)(sum after))"accepted_sample_exact_network_conservation";
      let destination=find "computed_product_grid_value_absent"
        (fun(candidate:Qc.state_value)->List.for_all2(fun(amount:Qc.quantity)expected->Charge.charge 1;Q.equal amount.amount expected)
          candidate.amounts after)local.values in
      let request=input_value<>None && Q.compare snapshot.(target) law.threshold.amount.amount<0 &&
        Q.compare(List.nth after target)law.threshold.amount.amount>=0 in
      let allocated=List.exists(fun(_,amount)->Q.sign amount>0)allocations in
      (match input_value with None->()|Some truth->
        let transitions=List.filter(fun(transition:O.transition)->transition.source=value.state &&
          polarity transition.guard=Some truth)behavior.transitions in
        if not allocated then
          fail(transitions=[])"zero_allocation_samples_require_implicit_holds"
        else (
          incr moving;
          let transition=one "one_transition_for_each_allocating_sample" transitions in
          fail(transition.destination=destination.state && transition.effects=(if request then[selected.effect_value]else[]))
            "exact_reserved_network_and_crossing_request";
          if request then crossings:=(transition,truth):: !crossings));
      obj["source",str value.state;"input",str(match input_value with None->"unknown"|Some true->"true"|Some false->"false");
        "destination",str destination.state;"request",Json.Bool request;
        "before",vector before;"after",vector after;
        "flows",Json.Array(List.map(fun((edge:Qc.transfer),amount)->
          obj["transfer",str edge.id;"quanta",Json.int(quanta amount)])allocations)]) [Some true;Some false;None])local.values in
    fail(List.length behavior.transitions= !moving)"complete_sparse_network_transition_inventory";
    let effect_binding=one "one_bound_effect"(B.effects binding)in
    fail(effect_binding.source=selected.effect_value)"crossing_request_original_effect_identity";
    let crossings=List.rev !crossings in
    fail(crossings<>[] && List.length crossings=List.length local.outputs &&
      List.length crossings=List.length effect_binding.request_sites)
      "complete_quantitative_crossing_site_inventory";
    let bank=find "quantitative_attempt_bank_absent"
      (fun(value:I.node)->value.node_id=effect_binding.bank)actual_nodes in
    fail((match bank.model.primitive with I.Attempt_bank_sites value->value.sites=List.length crossings|_->false))
      "shared_multisite_attempt_bank_shape";
    let sites=List.mapi(fun index(site:B.effect_site)->site.initiating_rule,index)effect_binding.request_sites in
    fail(List.length(List.sort_uniq compare(List.map fst sites))=List.length sites)
      "unique_quantitative_request_site_identity";
    let crossing_sites=List.map2(fun ((crossing:O.transition),truth)(output:Qc.output_site)->
      fail(output.source_state=crossing.source && output.input=truth)"ordered_complete_crossing_output_inventory";
      let transition_binding=find "crossing_transition_binding_absent"
        (fun(value:B.transition)->value.source=crossing.transition_id)(B.transitions binding)in
      let _,index=find "crossing_request_site_binding_absent"(fun(id,_)->id=crossing.transition_id)sites in
      let boundary=find "quantitative_request_boundary_absent"
        (fun(value:F.boundary_port)->value.boundary_id=output.boundary)(F.boundary_ports fragment)in
      let output_node=local_node boundary.endpoint.node_id and actual_output=relocate boundary.endpoint.node_id in
      fail(pin_equal output_node.model.identity output.model && pin_equal actual_output.model.identity output.model &&
        boundary.direction=I.Output && boundary.signal_type=I.Effect_request &&
        boundary.endpoint.port_id="request0" && actual_output.node_id=transition_binding.commit)
        "complete_crossing_commit_model_and_request_endpoint";
      let attempt_port="request"^string_of_int index in
      let connected=List.filter(fun(wire:I.wire)->wire.consumer.node_id=effect_binding.bank &&
        wire.consumer.port_id=attempt_port)(I.wires actual)in
      let wire=one "one_crossing_request_bank_connection" connected in
      fail(wire.producer.node_id=actual_output.node_id && wire.producer.port_id=boundary.endpoint.port_id)
        "crossing_request_site_actual_bank_port";
      obj["transition",str crossing.transition_id;"source_state",str crossing.source;"input",Json.Bool truth;
        "request_endpoint",obj["node",str actual_output.node_id;"port",str boundary.endpoint.port_id];
        "model",Pin.to_json output.model;"attempt_port",str attempt_port])crossings local.outputs in
    let bindings=obj["machine_bank",str actual_bank.node_id;"observation_bank",str actual_input.node_id;
      "observation_input",str observation_binding.input;"attempt_bank",str effect_binding.bank;
      "crossing_sites",Json.Array crossing_sites;
      "owners",Json.Array(List.map(fun((owner:Cc.owner),register,next)->obj["instance",str owner.instance;"component",Pin.to_json owner.component;
        "contract",str owner.contract;"compartment",str owner.compartment;"source_state",str owner.state;"register",str register;
        "next",obj["node",str next.node_id;"port",str next.port_id]])owner_endpoints);
      "transfers",Json.Array(List.map(fun(id,(ep:I.endpoint))->obj["transfer",str id;"endpoint",obj["node",str ep.node_id;"port",str ep.port_id]])flow_endpoints)]in
    let conservation=obj["scope",str "accepted_samples_within_encounter_generation";
      "quantity",str "sum_all_reservoirs";"reset",str "restore_declared_initial_vector";
      "checked_rows",Json.int(List.length table)]in
    bindings,table,conservation
end

let check ?parent ?(maximum=max_work) ~request ~context ()=
  Diagnostic.require(maximum>=0 && maximum<=max_work)"policy_quantitative_composition_resource_limit"
    "Quantitative network work allowance exceeds its fixed ceiling.";
  let composition=match R.composed_quantitative request with Some value->value|None->
    Diagnostic.fail "policy_quantitative_composition_request""Network checking requires the explicit original transfer-network request."in
  let selected=composition.network in
  let budget=match parent with None->W.create ~profile ~error_code:"policy_quantitative_composition_resource_limit" ~maximum()
    |Some parent->W.nested ~parent ~profile ~error_code:"policy_quantitative_composition_resource_limit" ~maximum()in
  let before=W.remaining budget in
  let module Check=Make(struct let charge=W.charge budget end)in
  let bindings,table,conservation,issues,outcome_value=match Check.execute request context composition with
    |bindings,table,conservation->bindings,table,conservation,[],E.Pass
    |exception Diagnostic.Error error when error.code="policy_quantitative_composition_fail"->
      Json.Null,[],Json.Null,[error.message],E.Fail in
  let raw=Qc.selection_to_json selected in
  let fields=["schema_version",str schema_version;"profile",str profile;"implementation",str implementation_version;
    "outcome",str(E.outcome_name outcome_value);"claim_scope",str "exact_atomic_component_transfer_network_under_supplied_coordination_contract";
    "request_fingerprint",str(R.fingerprint request);"mechanism_fingerprint",str(Check.hash(Qc.to_json selected.mechanism));
    "selection",Check.get "selection" raw;"composition",Cc.selection_to_json composition;"source",Check.get "source" raw;"bindings",bindings;"table",Json.Array table;
    "conservation",conservation;
    "arbitration",str(Qc.arbitration_name selected.mechanism.arbitration);
    "ownership",str "partitioned_reservoir_storage_single_atomic_writer";
    "synchronization",str Cc.synchronization;
    "transport_scope",str "selected_boolean_allocation_signals_under_supplied_component_contracts";
    "sampling",obj["sample_period",selected.mechanism.sample_period.raw;"max_rows_per_slot_tick",Json.int 1;
      "observed_age_ticks",Json.int 0;"no_update",str "hold";"unknown",str "hold_without_request";
      "reset",str "initial";"reservation",str "existing_atomic_reservation"];
    "issues",Json.Array(List.map str issues);"empirical",str "unassessed"]in
  let usage amount=obj["unit",str "logical_data_visits_and_exact_finite_table_work";"charged_work",Json.int amount]in
  let reserved=obj(fields@["usage",usage maximum])in
  Check.Meter.preflight reserved;Check.Meter.serialization reserved;
  let output=W.create_output ~profile ~error_code:"policy_quantitative_composition_publication_limit" ~max_bytes:262144 ~max_nodes:16384()in
  W.reserve_json output reserved;
  let report_value=obj(fields@["usage",usage(before-W.remaining budget)])in
  Diagnostic.require(not(W.exhausted budget))"policy_quantitative_composition_resource_limit""Quantitative network work was exhausted.";
  let accepted_value=if outcome_value=E.Pass then Some{request_value=request;evidence_value=report_value}else None in
  {report_value;outcome_value;accepted_value}
