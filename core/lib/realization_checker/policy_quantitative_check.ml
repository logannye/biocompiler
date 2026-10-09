open Bioc_wire
module R = Bioc_domain.Policy_component_material_request
module Qc = Bioc_domain.Policy_quantitative_contract
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
module Transfer = Policy_quantitative_transfer_check
module Network = Policy_quantitative_network_check
let schema_version="biocompiler.policy_quantitative_assessment.v0.1"
let profile=Qc.profile
let implementation_version="biocompiler.ocaml.policy_quantitative_check.v0.1"
let step_schema_version="biocompiler.policy_quantitative_assessment.v0.2"
let step_implementation_version="biocompiler.ocaml.policy_quantitative_check.v0.2"
let max_work=128*1024*1024
let str value=Json.String value
let obj value=Json.Object value
type checked_quantitative={request_value:R.t;evidence_value:Json.t}
type result={report_value:Json.t;outcome_value:E.outcome;accepted_value:checked_quantitative option}
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
  let fail condition message=Diagnostic.require condition "policy_quantitative_fail" message
  let same=Meter.Json.equal
  let hash raw=Meter.preflight raw;Meter.Canonical.fingerprint raw
  let one message=function [value]->value|_->Diagnostic.fail "policy_quantitative_fail" message
  let find message predicate values=match List.find_opt predicate values with
    |Some value->value|None->Diagnostic.fail "policy_quantitative_fail" message
  let pin_equal left right=same(Pin.to_json left)(Pin.to_json right)
  let execute request context (selected:Qc.selection)=
    Meter.preflight(R.to_json request);Meter.preflight(C.evidence context);
    fail(same(R.to_json request)(R.to_json(C.request context)))"fresh_context_original_request";
    fail(R.is_quantitative request && R.is_finite_machine request)"quantitative_finite_request_family";
    let assembly=C.assembly context in
    let preservation=A.implementation assembly in
    let binding=P.binding preservation in
    let admitted=B.admitted_inputs binding in
    let original=Admission.request admitted and behavior=Admission.behavior admitted in
    Meter.preflight(O.behavior_to_json behavior);
    let rule=R.composition_rule request and slot=Rule.Instance selected.instance in
    let component=Rule.component rule slot in
    fail(pin_equal selected.component(LC.identity component))"selected_complete_component_identity";
    let local=one "one_selected_quantitative_contract"(LC.quantitative_contracts component) in
    fail(String.equal selected.contract local.id && same(Qc.to_json selected.mechanism)(Qc.to_json local.mechanism))
      "independent_original_and_selected_mechanism";
    let law=selected.mechanism in
    fail(R.is_multi_site request=law.multi_site)"explicit_quantitative_request_site_family";
    let machine=one "one_source_machine" behavior.machines
    and observation=one "one_source_observation" behavior.observations
    and effect=one "one_source_effect" behavior.effects in
    fail(String.equal machine.machine_id selected.machine && String.equal observation.observation_id selected.observation &&
      String.equal effect.effect_id selected.effect)"complete_nominal_source_bindings";
    fail(machine.states=List.map(fun(value:Qc.state_value)->value.state)local.values && machine.terminal=[] &&
      machine.lifetime="encounter" && behavior.stores=[] && behavior.rules=[])
      "complete_nonterminal_encounter_grid";
    let initial=find "initial_state_absent"(fun(value:Qc.state_value)->String.equal value.state machine.initial)local.values in
    fail(Q.equal initial.quantity.amount law.initial.amount)"exact_initial_quantity_and_reset";
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
    fail(List.length behavior.transitions=2*law.levels)"exact_two_sampled_transitions_per_level";
    List.iter(fun(transition:O.transition)->fail(transition.machine=selected.machine && updated transition.on &&
      transition.assignments=[] && Option.is_some(polarity transition.guard))"closed_sampled_transition_form")behavior.transitions;
    let crossings=ref [] in
    let table=List.concat_map(fun(value:Qc.state_value)->List.map(fun input_value->
      Charge.charge 64;
      let next=match input_value with None->value.quantity.amount|Some truth->
        (* Production and consumption are combined before either saturation.
           True at capacity therefore holds capacity, rather than decaying. *)
        let changed=if law.multi_site then
          if truth then Q.add value.quantity.amount law.rise.amount else Q.sub value.quantity.amount law.fall.amount
          else let production=if truth then Q.mul(Q.of_int 2)law.quantum.amount else Q.zero in
            Q.sub(Q.add value.quantity.amount production)law.quantum.amount in
        if Q.sign changed<0 then Q.zero else if Q.compare changed law.capacity.amount>0 then law.capacity.amount else changed in
      let destination=find "computed_grid_value_absent"(fun(candidate:Qc.state_value)->Q.equal candidate.quantity.amount next)local.values in
      let request=input_value<>None && Q.compare value.quantity.amount law.threshold.amount<0 &&
        Q.compare next law.threshold.amount>=0 in
      (match input_value with None->()|Some truth->
        let transitions=List.filter(fun(transition:O.transition)->transition.source=value.state && polarity transition.guard=Some truth)
          behavior.transitions in
        let transition=one "one_transition_for_each_known_sample" transitions in
        fail(transition.destination=destination.state && transition.effects=(if request then[selected.effect]else[]))
          "exact_saturating_law_and_unique_crossing_request";
        if request then crossings:=(transition,truth):: !crossings);
      obj["source",str value.state;"input",str(match input_value with None->"unknown"|Some true->"true"|Some false->"false");
        "destination",str destination.state;"request",Json.Bool request]) [Some true;Some false;None])local.values in
    let effect_binding=one "one_bound_effect"(B.effects binding) in
    fail(effect_binding.source=selected.effect)"crossing_request_original_effect_identity";
    let check_output boundary model (transition_binding:B.transition)=
      let output=find "quantitative_request_boundary_absent"
        (fun(value:F.boundary_port)->value.boundary_id=boundary)(F.boundary_ports fragment) in
      let output_node=local_node output.endpoint.node_id and actual_output=relocate output.endpoint.node_id in
      fail(pin_equal output_node.model.identity model && pin_equal actual_output.model.identity model &&
        output.direction=I.Output && output.signal_type=I.Effect_request &&
        output.endpoint.port_id="request0" && actual_output.node_id=transition_binding.commit)
        "complete_crossing_commit_model_and_request_endpoint";
      actual_output,output.endpoint.port_id in
    if law.multi_site then (
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
        fail(output.source_state=crossing.source && output.input=truth)
          "ordered_complete_crossing_output_inventory";
        let transition_binding=find "crossing_transition_binding_absent"
          (fun(value:B.transition)->value.source=crossing.transition_id)(B.transitions binding)in
        let _,index=find "crossing_request_site_binding_absent"(fun(id,_)->id=crossing.transition_id)sites in
        let actual_output,port=check_output output.boundary output.model transition_binding in
        let attempt_port="request"^string_of_int index in
        let connected=List.filter(fun(wire:I.wire)->wire.consumer.node_id=effect_binding.bank &&
          wire.consumer.port_id=attempt_port)(I.wires actual)in
        let wire=one "one_crossing_request_bank_connection" connected in
        fail(wire.producer.node_id=actual_output.node_id && wire.producer.port_id=port)
          "crossing_request_site_actual_bank_port";
        obj["transition",str crossing.transition_id;"source_state",str crossing.source;"input",Json.Bool truth;
          "request_endpoint",obj["node",str actual_output.node_id;"port",str port];
          "model",Pin.to_json output.model;"attempt_port",str attempt_port])crossings local.outputs in
      obj["machine_bank",str actual_bank.node_id;"observation_bank",str actual_input.node_id;
        "observation_input",str observation_binding.input;"attempt_bank",str effect_binding.bank;
        "crossing_sites",Json.Array crossing_sites],table)
    else (
    let crossing,_=one "exactly_one_upward_threshold_initiator" !crossings in
    let transition_binding=find "crossing_transition_binding_absent"
      (fun(value:B.transition)->value.source=crossing.transition_id)(B.transitions binding) in
    fail(effect_binding.source=selected.effect && effect_binding.initiating_rule=crossing.transition_id)
      "crossing_request_original_effect_identity";
    let actual_output,port=check_output local.output_boundary local.output_model transition_binding in
    obj["machine_bank",str actual_bank.node_id;"observation_bank",str actual_input.node_id;
      "observation_input",str observation_binding.input;"crossing_transition",str crossing.transition_id;
      "request_endpoint",obj["node",str actual_output.node_id;"port",str port]],table)
end

let check ?parent ?(maximum=max_work) ~request ~context ()=
  if R.is_transfer_network request then (
    let result=Network.check ?parent ~maximum ~request ~context ()in
    let report_value=Network.report result and outcome_value=Network.outcome result in
    let accepted_value=Option.map(fun checked->
      {request_value=Network.request checked;evidence_value=Network.evidence checked})(Network.accepted result)in
    {report_value;outcome_value;accepted_value}
  )else if R.is_transfer_pair request then (
    let result=Transfer.check ?parent ~maximum ~request ~context ()in
    let report_value=Transfer.report result and outcome_value=Transfer.outcome result in
    let accepted_value=Option.map(fun checked->{request_value=Transfer.request checked;
      evidence_value=Transfer.evidence checked})(Transfer.accepted result)in
    {report_value;outcome_value;accepted_value})
  else (
  Diagnostic.require(maximum>=0 && maximum<=max_work)"policy_quantitative_resource_limit""Quantitative work allowance exceeds its fixed ceiling.";
  let selected=match R.quantitative request with Some value->value|None->Diagnostic.fail "policy_quantitative_request""Quantitative checking requires the explicit original quantitative request."in
  let profile=if selected.mechanism.multi_site then Qc.step_profile else profile in
  let budget=match parent with None->W.create ~profile ~error_code:"policy_quantitative_resource_limit" ~maximum()
    |Some parent->W.nested ~parent ~profile ~error_code:"policy_quantitative_resource_limit" ~maximum()in
  let before=W.remaining budget in
  let module Check=Make(struct let charge=W.charge budget end)in
  let bindings,table,issues,outcome_value=match Check.execute request context selected with
    |bindings,table->bindings,table,[],E.Pass
    |exception Diagnostic.Error error when error.code="policy_quantitative_fail"->Json.Null,[],[error.message],E.Fail in
  let raw=Qc.selection_to_json selected in
  let fields=["schema_version",str(if selected.mechanism.multi_site then step_schema_version else schema_version);
    "profile",str profile;"implementation",str(if selected.mechanism.multi_site then step_implementation_version else implementation_version);
    "outcome",str(E.outcome_name outcome_value);"claim_scope",str(if selected.mechanism.multi_site then
      "exact_sampled_step_reservoir_under_supplied_contract" else "exact_sampled_reservoir_under_supplied_contract");
    "request_fingerprint",str(R.fingerprint request);"mechanism_fingerprint",str(Check.hash(Qc.to_json selected.mechanism));
    "selection",Check.get "selection" raw;"source",Check.get "source" raw;"bindings",bindings;"table",Json.Array table;
    "sampling",obj["sample_period",selected.mechanism.sample_period.raw;"max_rows_per_slot_tick",Json.int 1;
      "observed_age_ticks",Json.int 0;"no_update",str "hold";"unknown",str "hold_without_request";
      "reset",str "initial";"reservation",str "existing_atomic_reservation"];
    "issues",Json.Array(List.map str issues);"empirical",str "unassessed"]in
  let usage amount=obj["unit",str "logical_data_visits_and_exact_finite_table_work";"charged_work",Json.int amount]in
  let reserved=obj(fields@["usage",usage maximum])in
  Check.Meter.preflight reserved;Check.Meter.serialization reserved;
  let output=W.create_output ~profile ~error_code:"policy_quantitative_publication_limit" ~max_bytes:262144 ~max_nodes:16384()in
  W.reserve_json output reserved;
  let report_value=obj(fields@["usage",usage(before-W.remaining budget)])in
  Diagnostic.require(not(W.exhausted budget))"policy_quantitative_resource_limit""Quantitative work was exhausted.";
  let accepted_value=if outcome_value=E.Pass then Some{request_value=request;evidence_value=report_value}else None in
  {report_value;outcome_value;accepted_value})
