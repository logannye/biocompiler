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
module H = Bioc_domain.Policy_provider_prerequisites
module HM = Bioc_domain.Policy_helper_material
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
type checked_prerequisite_closure = {prerequisite_evidence_value:Json.t}
type checked_context = {request_value:R.t;context_value:X.t;assembly_value:A.checked_assembly;
  discharge_values:discharge list;evidence_value:Json.t;
  prerequisite_value:checked_prerequisite_closure option}
type result = {outcome_value:E.outcome;report_value:Json.t;accepted_value:checked_context option}
let request (value:checked_context) = value.request_value
let context (value:checked_context) = value.context_value
let assembly (value:checked_context) = value.assembly_value
let discharges (value:checked_context) = value.discharge_values
let evidence (value:checked_context) = value.evidence_value
let prerequisite_closure (value:checked_context) = value.prerequisite_value
let prerequisite_evidence (value:checked_prerequisite_closure) = value.prerequisite_evidence_value
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
    | I.Machine_bank {states;retained_capacity;_} ->
      let rec bits width bound=charge 1;if bound>=List.length states then max 1 width else bits (width+1) (bound*2) in
      add MC.Machine_state_bits MC.Per_encounter_slot owner (bits 0 1);
      add MC.Machine_correlation_records MC.Per_encounter_slot owner retained_capacity
    | I.Evidence_bank {freshness_ticks} -> maximum_delta:=max !maximum_delta freshness_ticks;
      let observation=match List.find_opt (fun (value:IB.observation) -> value.bank=node.node_id) (IB.observations binding) with
        | Some value -> value.source | None -> Diagnostic.fail "policy_component_context_fail" "evidence_resource_binding" in
      let _,total=rows observation in add MC.Evidence_records MC.Per_encounter_slot owner total;add MC.Timer_cells MC.Per_encounter_slot owner 1
    | I.Observed_rising -> incr edges;add MC.Edge_history_cells MC.Per_encounter_slot owner 1
    | I.Attempt_bank {capacity;timeout_ticks;_} -> maximum_delta:=max !maximum_delta timeout_ticks;
      add MC.Active_attempt_records MC.Per_encounter_slot owner capacity;
      add MC.Retained_correlation_records MC.Per_executor owner domain.logical_limits.max_source_attempts;
      add MC.Timer_cells MC.Per_encounter_slot owner capacity
    | I.Activation_gate | I.Transition_gate _ -> incr gates
    | I.Atomic_commit {writes;requests} -> commits:= !commits+writes+requests
    | I.Transition_commit {writes;requests;_} -> commits:= !commits+1+writes+requests
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
    (LC.provider_requirements (Rule.component rule slot))) (Rule.slots rule) @ [1;1;1] in
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
  let layout:X.record_layout={staged=Rule.is_staged rule;rule=Rule.identity rule;union_digest=Canonical.fingerprint union;domain_digest=F.digest domain;
    slots=List.length slots;generations=domain.logical_limits.max_generations_per_slot;attempts=domain.logical_limits.max_source_attempts;
    horizon=domain.horizon_ticks;maximum_tick=domain.horizon_ticks+ !maximum_delta;ordered_reasons;
    ordered_causes=max 1 (queue*(domain.horizon_ticks+1));identifier_bytes=max 128 (4* !max_text+128)} in
  demands,layout

let check ?parent ?(maximum=max_work) ~request ~assembly () =
  Diagnostic.require (maximum>=0 && maximum<=max_work) "policy_component_context_resource_limit" "Context work budget exceeds its closed ceiling.";
  let context_profile=if R.is_instanced request then X.context_profile (R.context request)
    else if Rule.is_staged(R.composition_rule request) then X.staged_profile else X.profile in
  let budget=match parent with None -> W.create ~profile:context_profile ~error_code:"policy_component_context_resource_limit" ~maximum ()
    | Some parent -> W.nested ~parent ~profile:context_profile ~error_code:"policy_component_context_resource_limit" ~maximum () in
  let charge value=W.charge budget value in charge 1;
  let request=R.of_json ~charge (R.to_json request) in
  let context=R.context request and rule=R.composition_rule request in
  let multi_member=R.is_multi_member request in
  let grounded_helper=R.is_grounded_helper request in
  let source=PC.binding (A.implementation assembly) in
  let admitted=IB.admitted_inputs source in
  let original=Admission.request admitted and behavior=Admission.behavior admitted and domain=F.specification (Admission.operating_domain admitted) in
  let document=D.to_json (S.document original) in
  let providers=X.providers context and recipient=X.recipient context and clock=X.clock context in
  let prerequisites=if R.requires_prerequisite_closure request then
      Some(H.derive ~charge ~original:(R.implementation_request request) ~context ()) else None in
  let derived=ref [] and resource_rows=ref [] and input_rows=ref [] and discharged=ref [] and minimum_layout=ref Json.Null in
  let member_rows=ref [] and pending_member_rows=ref [] and transport_rows=ref [] in
  let helper_rows=ref [] and pending_helper_row=ref Json.Null and helper_delivery=ref Json.Null in
  let equal left right = M.check_resources left;M.check_resources right;
    let left=Canonical.encode left and right=Canonical.encode right in charge (String.length left+String.length right);left=right in
  let attempt () =
    fail (equal (S.to_json (R.implementation_request request)) (S.to_json original) &&
      equal (S.to_json (A.original assembly)) (S.to_json original)) "unchanged_original_realization_request";
    fail (equal (L.to_json (R.component_library request)) (L.to_json (A.components assembly))) "unchanged_original_component_library";
    fail (equal (Rule.to_json rule) (Rule.to_json (A.rule assembly))) "unchanged_original_assembly_rule";
    fail (text "catalog_entry" (IB.report source)=(R.catalog_binding request).entry_id) "original_selected_catalog_entry";
    Option.iter (fun closure ->
      (* A graph is an inventory of the original obligations, never a supplied
         PASS. A known cycle fails, but a missing body can hide edges to supplied
         providers: an extra finding is conclusive only after reachability is
         complete. Unsupported source meaning still needs its own interpreter. *)
      let issues=H.issues closure in
      let first predicate=List.find_opt (fun (issue:H.issue) -> charge 1;predicate issue.kind) issues in
      (match first (function H.Cycle -> true | _ -> false) with
       |Some issue->fail false issue.code|None->());
      (match first (function H.Unsupported -> true | _ -> false) with
       |Some issue->supported false issue.code|None->());
      (match first (function H.Missing -> true | _ -> false) with
       |Some issue->Diagnostic.fail "policy_component_context_unknown" issue.code|None->());
      (match first (function H.Extra -> true | _ -> false) with
       |Some issue->fail false issue.code|None->());
      charge(List.length providers+List.length(H.reachable closure));
      fail(List.sort compare(List.map(fun(value:C.provider)->value.definition)providers)=
        List.sort compare(H.reachable closure))"complete_transitive_provider_closure") prerequisites;
    supported (if Rule.is_staged rule then
      behavior.rules=[] && behavior.stores=[] && List.length behavior.machines=1 &&
      List.length behavior.transitions=7 && List.length behavior.effects=2
      else List.length behavior.rules>=1 && List.length behavior.rules<=2 && behavior.machines=[] && List.length behavior.effects=1)
      "closed_component_context_family_required";
    fail(recipient.role=domain.executor_role && recipient.identity=domain.executor_identity)"executor_recipient_binding";
    fail(List.for_all(fun(value:F.encounter)->value.target<>recipient.identity)domain.encounters)"encounter_target_is_not_delivery_recipient";
    let deployment=get "deployment" document in
    supported(text "route" deployment="in_vivo")"in_vivo_required";
    let payload=get "payload" deployment in
    supported(text "format" payload="RNA")"rna_required";
    List.iter(fun(key,count)->supported(get key payload=Json.int count)("exact_source_count_required:"^key))
      ["design_count",1;"member_count",(if grounded_helper then 3 else if multi_member then 2 else 1);
       "helper_count",(if grounded_helper then 1 else 0);
       "orf_count",(if grounded_helper then 3 else if multi_member then 2 else 1);
       "product_count",(if grounded_helper then 3 else if multi_member then 2 else 1)];
    List.iter(fun key->supported(get key payload=Json.Null)("unimplemented_source_payload_field:"^key))
      ["copy_number";"dose";"payload_persistence";"effector_persistence"];
    let structures=Rule.material_authority rule in
    (if grounded_helper then (
      let selection=match Rule.helper rule with Some value->value
        |None->Diagnostic.fail "policy_component_context_fail" "grounded_helper_material_absent" in
      let helper=match X.helpers context with [value]->value
        |_->Diagnostic.fail "policy_component_context_fail" "exact_one_grounded_helper" in
      let template=PM.template structures and member_bindings=Rule.member_bindings rule in
      let inventory=Option.get(K.inventory(MS.content(A.structure assembly))) in
      let molecules=K.Inventory.molecules inventory and placements=X.placements context in
      let payload_members=List.map(fun(value:Rule.member_binding)->value.member_id)member_bindings in
      let members=payload_members@[selection.member_id] in
      charge(List.length member_bindings+List.length molecules+List.length placements);
      fail(List.length member_bindings=2 && PM.member_order structures=members &&
        List.map N.id molecules=members && List.map AC.Placement.member_id placements=members &&
        List.length(PM.members structures)=3 && List.length(T.output_members template)=3 &&
        T.steps template=[] && T.complex_members template=[] && T.amounts template=[])
        "exact_three_member_grounded_helper_inventory";
      let expected_requirements=List.map(fun member->Some member,CT.Member_requirement.Payload)payload_members @
        [Some selection.member_id,CT.Member_requirement.Delivered_helper] in
      fail(List.sort compare(List.map(fun row->CT.Member_requirement.member_id row,CT.Member_requirement.category row)(T.requirements template))=
        List.sort compare expected_requirements)
        "two_payloads_one_delivered_helper";
      let group=X.delivery_group context in
      List.iter2(fun member placement->charge 1;
        fail(AC.Placement.template_id placement=T.id template && AC.Placement.member_id placement=member &&
          Id.Role.to_string(AC.Placement.recipient_role placement)=recipient.role &&
          AC.Placement.compartment placement=recipient.compartment && AC.Placement.delivery_group placement=group.group_id)
          "placement_identity_or_compartment")members placements;
      let molecule_fingerprint molecule=let encoded=Canonical.encode(N.to_json molecule) in
        charge(2*String.length encoded);Canonical.sha256 encoded in
      List.iteri(fun index (binding:Rule.member_binding)->charge 1;
        fail(List.length(LC.products(Rule.component rule binding.slot))=1)"one_encoded_product_per_member";
        pending_member_rows:= !pending_member_rows@[obj["slot",str(Rule.slot_name binding.slot);"source",str binding.source_id;
          "member",str binding.member_id;"placement",AC.Placement.to_json(List.nth placements index);
          "molecule_fingerprint",str(molecule_fingerprint(List.nth molecules index))]])member_bindings;
      let placement=List.nth placements 2 and molecule=List.nth molecules 2 in
      supported(AC.Helper.availability helper=AC.Helper.Other_rna &&
        AC.Helper.initialization helper=AC.Helper.After_expression && AC.Helper.assumptions helper=[] &&
        AC.Helper.depends_on helper=[] && HM.prerequisites selection.material=[])
        "grounded_helper_source_independent_initialization";
      fail(AC.Helper.placement_id helper=Some(AC.Placement.id placement) &&
        Option.map Id.Component.to_string(AC.Helper.provider_component_id helper)=Some(Pin.id(HM.identity selection.material)) &&
        AC.Helper.capability helper=(HM.capability selection.material).definition_id &&
        Id.Role.to_string(AC.Helper.recipient_role helper)=recipient.role && AC.Helper.compartment helper=recipient.compartment)
        "grounded_helper_material_placement_or_recipient";
      let final_pin=molecule_fingerprint molecule in
      let root_raw=CT.Root_source.to_json(HM.root selection.material) in
      let root_encoded=Canonical.encode root_raw in charge(2*String.length root_encoded);
      let projection=obj["material",HM.to_json selection.material;"source",str selection.source_id;
        "member",str selection.member_id;"product",PM.product_to_json(HM.product selection.material);
        "root_fingerprint",str(Canonical.sha256 root_encoded);"molecule_fingerprint",str final_pin] in
      fail(equal(get "helper_projections"(A.evidence assembly))(arr[projection]))"checked_grounded_helper_projection";
      pending_helper_row:=obj["helper",AC.Helper.to_json helper;"material",Pin.to_json(HM.identity selection.material);
        "capability",MC.provider_ref_to_json(HM.capability selection.material);"source",str selection.source_id;
        "member",str selection.member_id;"placement",AC.Placement.to_json placement;"molecule_fingerprint",str final_pin];
      fail(group.recipient_roles=[recipient.role] && group.same_recipient)"same_concrete_executor_delivery";
      supported(group.mode=C.Co_delivered)"independent_delivery_group_unimplemented";
      supported(group.assumptions=[] && group.exact_count=Some 3 &&
        (match group.max_count with None->true|Some value->value>=3))"delivery_count_or_assumptions";
      Option.iter(fun maximum->let total=List.fold_left(fun count molecule->charge 1;
        count+String.length(N.sequence molecule))0 molecules in fail(total<=maximum)"delivery_sequence_length")group.max_total_bases;
      let roles=K.Inventory.role_instances inventory in
      charge(List.length roles);
      fail(List.length roles=3 && List.for_all(fun member->
        let matches=List.filter(fun(role:N.Role.t)->N.Role.subject_id role=member)roles in
        match matches with [role]->N.Role.compartment role=recipient.compartment &&
          N.Role.purpose role=(if member=selection.member_id then N.Role.Helper else N.Role.Requested_payload)
        |_->false)members)"grounded_helper_material_role_inventory"
    ) else if multi_member then (
      let template=PM.template structures and member_bindings=Rule.member_bindings rule in
      let inventory=Option.get(K.inventory(MS.content(A.structure assembly))) in
      let molecules=K.Inventory.molecules inventory and placements=X.placements context in
      let members=List.map(fun(value:Rule.member_binding)->value.member_id)member_bindings in
      charge(List.length member_bindings+List.length molecules+List.length placements);
      fail(List.length member_bindings=2 && PM.member_order structures=members &&
        List.map N.id molecules=members && List.map AC.Placement.member_id placements=members &&
        List.length(PM.members structures)=2 && List.length(T.output_members template)=2 &&
        T.steps template=[] && T.complex_members template=[] && T.amounts template=[])
        "exact_two_member_material_inventory";
      supported(get "helpers"(X.to_json context)=arr [])"delivered_helpers_unimplemented";
      fail(List.map CT.Member_requirement.member_id(T.requirements template)=List.map Option.some members &&
        List.for_all(fun value->CT.Member_requirement.category value=CT.Member_requirement.Payload)(T.requirements template))
        "two_payloads_no_external_helpers";
      let group=X.delivery_group context in
      List.iter2(fun (binding:Rule.member_binding) (placement,molecule)->
        charge 1;
        fail(AC.Placement.template_id placement=T.id template && AC.Placement.member_id placement=binding.member_id &&
          Id.Role.to_string(AC.Placement.recipient_role placement)=recipient.role &&
          AC.Placement.compartment placement=recipient.compartment && AC.Placement.delivery_group placement=group.group_id)
          "placement_identity_or_compartment";
        fail(List.length(LC.products(Rule.component rule binding.slot))=1)"one_encoded_product_per_member";
        let encoded=Canonical.encode(N.to_json molecule)in charge(2*String.length encoded);
        pending_member_rows:= !pending_member_rows@[obj["slot",str(Rule.slot_name binding.slot);"source",str binding.source_id;
          "member",str binding.member_id;"placement",AC.Placement.to_json placement;
          "molecule_fingerprint",str(Canonical.sha256 encoded)]])member_bindings(List.combine placements molecules);
      fail(group.recipient_roles=[recipient.role] && group.same_recipient)"same_concrete_executor_delivery";
      supported(group.mode=C.Co_delivered)"independent_delivery_group_unimplemented";
      supported(group.assumptions=[] && group.exact_count=Some 2 &&
        (match group.max_count with None->true|Some value->value>=2))"delivery_count_or_assumptions";
      Option.iter(fun maximum->
        let total=List.fold_left(fun count molecule->charge 1;count+String.length(N.sequence molecule))0 molecules in
        fail(total<=maximum)"delivery_sequence_length")group.max_total_bases;
      fail(List.for_all(fun(role:N.Role.t)->N.Role.purpose role=N.Role.Requested_payload &&
        N.Role.compartment role=recipient.compartment)(K.Inventory.role_instances inventory))"material_role_compartment"
    ) else (
    let member=match PM.member_order structures with [member]->member|_->Diagnostic.fail "policy_component_context_unsupported" "one_rna_required"in
    let template=PM.template structures in
    fail(List.length(T.output_members template)=1 && T.complex_members template=[] && T.amounts template=[])"exact_material_inventory";
    supported(get "helpers"(X.to_json context)=arr [])"delivered_helpers_unimplemented";
    let requirements=T.requirements template in
    fail(List.length requirements=1 && CT.Member_requirement.category(List.hd requirements)=CT.Member_requirement.Payload)
      "one_payload_no_external_helpers";
    let molecule=List.hd(K.Inventory.molecules(Option.get(K.inventory(MS.content(A.structure assembly)))))in
    fail(List.length(PM.members structures)=1 && List.length(List.concat_map (fun slot -> LC.products(Rule.component rule slot)) (Rule.slots rule))=1)"one_encoded_product";
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
      (K.Inventory.role_instances(Option.get(K.inventory(MS.content(A.structure assembly))))))"material_role_compartment"));
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
    if Option.is_none prerequisites then
      fail(List.sort compare(List.map(fun(value:C.provider)->value.definition)providers)=refs)"complete_original_provider_closure";
    let resolve reference=charge(List.length providers);match List.find_opt(fun(value:C.provider)->ref_equal value.definition reference)providers with
      |Some value->value|None->Diagnostic.fail
        (if Option.is_some prerequisites then "policy_component_context_unknown" else "policy_component_context_fail") "original_provider_absent"in
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
       |C.Transport value->
         supported multi_member "inter_member_transport_requires_multi_member_profile";
         fail(category="interface")"transport_definition_category";
         fail(equal value.original_clock original_clock)"transport_original_clock";
         (match(resolve value.environment).body with C.Environment _->()|_->fail false "transport_environment_body");
         supported(provider.capacities=[])"transport_resource_supply_unimplemented"
       |C.Helper value->
         supported grounded_helper "helper_provider_requires_grounded_helper_profile";
         let selection=Option.get(Rule.helper rule) in
         fail(category="capability" && ref_equal provider.definition(HM.capability selection.material))
           "grounded_helper_capability_definition";
         fail(equal(Pin.to_json value.material)(Pin.to_json(HM.identity selection.material)))
           "grounded_helper_complete_material_pin";
         (match(resolve value.environment).body with C.Environment _->()|_->fail false "helper_environment_body");
         fail(ref_equal value.delivery(MC.provider_ref_of_json(get "contract" delivery)))"helper_original_delivery_contract";
         let expression_latest=match(resolve value.delivery).body with C.Delivery phases->phases.expression.latest.seconds
           |_->Diagnostic.fail "policy_component_context_fail" "helper_independent_delivery_body" in
         supported(value.bootstrap.prerequisites=[])"helper_bootstrap_prerequisites_unimplemented";
         fail(Q.leq expression_latest value.bootstrap.completion.earliest.seconds &&
           Q.leq value.bootstrap.completion.latest.seconds provider.available.onset_min.seconds)
           "causal_expression_helper_completion_availability";
         fail(provider.capacities<>[])"grounded_helper_capacity_absent";
         List.iter(fun(capacity:C.capacity)->charge 1;
           fail(capacity.unit=MC.Retained_correlation_records && capacity.scope=MC.Per_executor && capacity.slots=[])
             "grounded_helper_capacity_type_scope";
           fail(Q.geq capacity.available.onset_max.seconds provider.available.onset_max.seconds &&
             Q.leq(Q.add capacity.available.onset_min.seconds capacity.available.duration_min.seconds)
               (Q.add provider.available.onset_min.seconds provider.available.duration_min.seconds))
             "helper_capacity_guarantee_outside_provider")provider.capacities
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
    (if multi_member then (
      (* The original delivery contract covers the complete payload together.
         Record that same checked inclusive window against each exact member;
         this profile does not invent separate or staggered member windows. *)
      let provider=resolve(MC.provider_ref_of_json(get "contract" delivery))in
      let body=C.provider_body_to_json provider in
      let delivery=obj["definition",MC.provider_ref_to_json provider.definition;"provider",Pin.to_json provider.identity;
        "body",body]in
      member_rows:=List.map(fun row->charge 1;obj(Json.object_fields row@["delivery",delivery])) !pending_member_rows;
      if grounded_helper then helper_delivery:=delivery
    ));
    List.iter(fun raw->match(resolve(MC.provider_ref_of_json raw)).body with C.Environment _->()|_->fail false "environment_body")
      (items "environment" chassis@items "environment" deployment);
    List.iter(fun raw->match(resolve(MC.provider_ref_of_json raw)).body with C.Interface _->()|_->fail false "capability_interface_body")
      (items "requires" role@items "capabilities" chassis@items "interfaces" chassis);
    (if multi_member then (
      let closure=Option.get prerequisites in
      let dependencies=H.dependencies closure and bridge=R.catalog_binding request in
      let links=Rule.links rule and carriers=Rule.link_carriers rule in
      let raw_links=items "links"(get "body"(Rule.to_json rule))in
      let link_projections=items "link_projections"(A.evidence assembly)in
      charge(List.length links+List.length carriers+List.length link_projections);
      fail(List.map(fun(value:Rule.link_carrier)->value.kind)carriers=List.map(fun(value:Rule.link)->value.kind)links &&
        List.map(text "link")link_projections=List.map(fun(value:Rule.link)->Rule.link_name value.kind)links)
        "complete_inter_member_transport_inventory";
      let used=ref []in
      List.iter2(fun (link:Rule.link) (carrier,projection)->
        charge 1;
        let transport=match Rule.carrier_transport carrier with Some value->value
          |None->Diagnostic.fail "policy_component_context_fail" "inter_member_transport_absent"in
        let producer=Rule.member_for_slot rule link.producer.slot and consumer=Rule.member_for_slot rule link.consumer.slot in
        fail(transport.producer_member=producer.member_id && transport.consumer_member=consumer.member_id &&
          producer.member_id<>consumer.member_id)"inter_member_transport_endpoint_ownership";
        fail(equal(get "transport" projection)(Rule.transport_to_json transport))"checked_transport_projection";
        charge(List.length dependencies);
        fail(List.exists(fun(value:H.pending_dependency)->value.entry_id=bridge.entry_id &&
          value.entry_digest=bridge.entry_digest && ref_equal value.definition transport.definition)dependencies)
          "transport_selected_catalog_dependency";
        let provider=resolve transport.definition in
        fail(equal(Pin.to_json provider.identity)(Pin.to_json transport.provider))"transport_complete_provider_pin";
        (match provider.body with C.Transport _->()|_->fail false "transport_provider_kind");
        used:=provider.definition:: !used;
        charge(List.length raw_links);
        let raw_link=List.find(fun raw->text "id" raw=Rule.link_name link.kind)raw_links in
        transport_rows:= !transport_rows@[obj["link",str(Rule.link_name link.kind);
          "producer_member",str producer.member_id;"consumer_member",str consumer.member_id;
          "provider",Pin.to_json provider.identity;"definition",MC.provider_ref_to_json provider.definition;
          "signal_type",get "signal_type" raw_link;"scope",get "scope" raw_link;
          "transport_profile",str C.transport_profile;"phase_profile",str C.transport_phase_profile;
          "available",C.availability_to_json provider.available]])links(List.combine carriers link_projections);
      let declared=List.filter_map(fun(provider:C.provider)->match provider.body with
        |C.Transport _->Some provider.definition|_->None)providers in
      charge(List.length declared+List.length !used);
      fail(List.sort compare declared=List.sort_uniq compare !used)"unused_original_transport_provider"
    ));
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
      fail(not(List.mem key !used_channels))"input_channel_alias";used_channels:=key:: !used_channels;
      if Option.is_some prerequisites then (
        charge 1;
        input_rows:= !input_rows@[obj ["input",str witness.input_id;"source",str witness.source;
          "provider",MC.provider_ref_to_json witness.provider;"channel",str witness.channel;
          "kind",str(match kind with C.Observation->"observation"|C.Feedback->"feedback");
          "observer",str observer;"subject",str subject;"available",C.availability_to_json channel.available]])) (R.input_bindings request);
    let all_channels=List.concat_map(fun(provider:C.provider)->match provider.body with
      |C.Interface value->List.map(fun(channel:C.channel)->Canonical.encode(MC.provider_ref_to_json provider.definition),channel.channel_id)value.channels|_->[])providers in
    fail(List.sort compare all_channels=List.sort compare !used_channels)"unused_original_input_channel";
    let demands,needed=derive ~charge source rule domain in
    derived:=List.map demand_json demands;minimum_layout:=X.record_layout_to_json needed;
    let declared=X.record_layout context in
    fail (declared.staged=needed.staged && Pin.fingerprint declared.rule=Pin.fingerprint needed.rule && declared.union_digest=needed.union_digest &&
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
    let helper_consumers=ref [] and helper_resources=ref [] in
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
      let row=obj ["demand",demand_json demand;"provider",MC.provider_ref_to_json provider.definition;
        "capacity",str capacity.capacity_id;"pool",str capacity.pool_id;"reserved",Json.int demand.quantity] in
      resource_rows:= !resource_rows@[row];
      (match provider.body with C.Helper _->
        fail(grounded_helper && demand.key.unit=MC.Retained_correlation_records && demand.key.scope=MC.Per_executor)
          "grounded_helper_bound_demand_type";
        let slot,node_id=match demand.key.owner with R.Node value->value.slot,value.node_id
          |_->Diagnostic.fail "policy_component_context_fail" "grounded_helper_requires_attempt_owner" in
        let nodes=List.combine(Rule.node_order rule)(I.nodes(IB.implementation source)) in
        charge(List.length nodes);
        let actual=match List.find_opt(fun((reference:Rule.node_ref),_)->reference.slot=slot && reference.node_id=node_id)nodes with Some(_,node)->node
          |None->Diagnostic.fail "policy_component_context_fail" "grounded_helper_actual_owner_absent" in
        (match actual.model.primitive with I.Attempt_bank _->()
          |_->fail false "grounded_helper_requires_attempt_bank");
        let instance=Rule.slot_name slot in
        if not(List.mem instance !helper_consumers)then helper_consumers:= !helper_consumers@[instance];
        helper_resources:= !helper_resources@[row]
      |_->())) bindings demands;
    List.iter (fun (provider:C.provider) -> List.iter (fun (capacity:C.capacity) ->
      fail (Hashtbl.mem usage capacity.pool_id) "unused_original_capacity") provider.capacities) providers;
    (if grounded_helper then (
      let selection=Option.get(Rule.helper rule) and helper=List.hd(X.helpers context) in
      let provider=resolve(HM.capability selection.material) in
      (match provider.body with C.Helper _->()|_->fail false "grounded_helper_provider_kind");
      let supplied=List.filter(fun(provider:C.provider)->match provider.body with C.Helper _->true|_->false)providers in
      fail(List.length supplied=1)"exact_one_grounded_helper_provider";
      let closure=Option.get prerequisites and bridge=R.catalog_binding request in
      let dependencies=H.dependencies closure in charge(List.length dependencies);
      fail(List.exists(fun(value:H.pending_dependency)->value.entry_id=bridge.entry_id &&
        value.entry_digest=bridge.entry_digest && ref_equal value.definition provider.definition)dependencies)
        "helper_selected_catalog_dependency";
      let consumers=List.map Id.Component.to_string(AC.Helper.consumer_component_ids helper) in
      charge(List.length consumers+List.length !helper_consumers);
      fail(!helper_resources<>[] && List.sort String.compare consumers=List.sort String.compare !helper_consumers)
        "grounded_helper_exact_consumer_inventory";
      let count=List.length !helper_consumers in
      fail(AC.Helper.capacity helper>=count && (match AC.Helper.sharing helper with
        |AC.Helper.Exclusive->count=1|AC.Helper.Shared->count>=1))"grounded_helper_consumer_capacity";
      fail(!pending_helper_row<>Json.Null && !helper_delivery<>Json.Null)"grounded_helper_allocation_evidence_absent";
      let body=C.provider_body_to_json provider in
      helper_rows:=[obj(Json.object_fields !pending_helper_row@[
        "provider",Pin.to_json provider.identity;"provider_body",body;"bootstrap",get "bootstrap" body;
        "delivery", !helper_delivery;"consumers",arr(List.map str !helper_consumers);
        "resource_allocations",arr !helper_resources])]
    ));
    let provider_evidence=arr (List.map (fun (provider:C.provider) -> Pin.to_json provider.identity) providers) in
    let names="chassis_capability_and_delivery_suitability"::List.map (fun (provider:C.provider) -> "semantic_definition:" ^ provider.definition.definition_id) providers in
    discharged:=List.filter_map (fun obligation -> if List.mem obligation names then Some {obligation;evidence=provider_evidence} else None) behavior.unresolved_obligations
  in
  let outcome_value,diagnostics=match attempt () with () -> E.Pass,[]
    | exception Diagnostic.Error error when error.code="policy_component_context_fail" -> E.Fail,[error.message]
    | exception Diagnostic.Error error when error.code="policy_component_context_unknown" -> E.Unknown,[error.message]
    | exception Diagnostic.Error error when error.code="policy_component_context_unsupported" -> E.Unsupported,[error.message] in
  let closure_evidence=Option.map (fun closure ->
    let fingerprint raw=M.check_resources raw;let encoded=Canonical.encode raw in
      charge(2*String.length encoded);Canonical.sha256 encoded in
    let selections=Rule.components rule in
    let instances=List.map(fun(value:Rule.component_selection)->charge 1;
      obj["slot",str(Rule.slot_name value.slot);"component",Pin.to_json value.identity])selections in
    let requirements=List.map(fun(value:Rule.component_selection)->charge 1;
      let body=get "body"(LC.to_json(Rule.component rule value.slot))in
      obj["slot",str(Rule.slot_name value.slot);"component",Pin.to_json value.identity;
        "requirements",get "provider_requirements" body])selections in
    let provider_pins=List.map(fun(value:C.provider)->charge 1;
      obj["definition",MC.provider_ref_to_json value.definition;"identity",Pin.to_json value.identity;
        "body_fingerprint",str(fingerprint(C.provider_body_to_json value))])providers in
    let requested=R.implementation_request request in
    obj(["schema_version",str (if grounded_helper then "biocompiler.policy_provider_prerequisite_closure.v0.3"
      else if multi_member then "biocompiler.policy_provider_prerequisite_closure.v0.2"
      else "biocompiler.policy_provider_prerequisite_closure.v0.1");
      "profile",str context_profile;"status",str(E.outcome_name outcome_value);"complete",Json.Bool(outcome_value=E.Pass);
      "original_request_fingerprint",str(R.fingerprint request);"assembly_fingerprint",str(fingerprint(A.evidence assembly));
      "source_catalog",get "implementations"(D.to_json(S.document requested));
      "pending_dependencies",arr(List.map H.pending_dependency_to_json(H.dependencies closure));
      "instances",arr instances;"local_requirements",arr requirements;"providers",arr provider_pins;
      "graph",H.to_json closure;"operating_domain_fingerprint",str(F.digest(S.operating_domain requested));
      "clock",get "clock"(X.to_json context);"recipient",C.recipient_to_json recipient;
      "input_allocations",arr !input_rows;"resource_allocations",arr !resource_rows;
      "diagnostics",arr(List.map str diagnostics);"empirical",str "unassessed"] @
      (if multi_member then ["member_allocations",arr !member_rows;"transport_allocations",arr !transport_rows] else []) @
      (if grounded_helper then ["helper_allocations",arr !helper_rows] else []))) prerequisites in
  let report_value=obj (["schema_version",str (if grounded_helper then "biocompiler.policy_component_context_assessment.v0.3"
    else if multi_member then "biocompiler.policy_component_context_assessment.v0.2"
    else "biocompiler.policy_component_context_assessment.v0.1");
    "profile",str context_profile;"implementation_version",str (if grounded_helper then
      "biocompiler.ocaml.policy_component_context_check.v0.6" else if multi_member then
      "biocompiler.ocaml.policy_component_context_check.v0.5" else if R.is_two_observation request then
      "biocompiler.ocaml.policy_component_context_check.v0.4" else if Option.is_some prerequisites then
      "biocompiler.ocaml.policy_component_context_check.v0.3" else if R.is_instanced request then
      "biocompiler.ocaml.policy_component_context_check.v0.2" else implementation_version);
    "request_fingerprint",str (R.fingerprint request);"context_fingerprint",str (X.fingerprint context);
    "assembly_fingerprint",str (Canonical.fingerprint (A.evidence assembly));
    "outcome",str (E.outcome_name outcome_value);"claim_scope",str "conditional_component_context_and_complete_record_capacity";
    "record_layout",X.record_layout_to_json (X.record_layout context);"minimum_record_layout", !minimum_layout;
    "derived_demands",arr !derived;"resource_allocations",arr !resource_rows;
    "source_obligations",arr (List.map (fun obligation -> obj ["id",str obligation;
      "context_status",str (if List.exists (fun (value:discharge) -> value.obligation=obligation) !discharged then "discharged" else "outside_stage")]) behavior.unresolved_obligations);
    "discharges",arr (List.map (fun (value:discharge) -> obj ["id",str value.obligation;"evidence",value.evidence]) !discharged);
    "diagnostics",arr (List.map str diagnostics);"source_receipt_status",str "unchanged";
    "biological_validity",str "unassessed";"human_use",str "unassessed";"artifact",str "withheld";"export",str "withheld"] @
    (match closure_evidence with None->[]|Some value->["prerequisite_closure",value]) @
    (if multi_member then ["member_allocations",arr !member_rows;"transport_allocations",arr !transport_rows] else []) @
    (if grounded_helper then ["helper_allocations",arr !helper_rows] else [])) in
  let output=W.create_output ~profile:context_profile ~error_code:"policy_component_context_resource_limit" ~max_bytes:M.max_json_bytes ~max_nodes:M.max_items () in
  W.reserve_json output report_value;charge (2*String.length (Canonical.encode report_value));
  Diagnostic.require (not (W.exhausted budget)) "policy_component_context_resource_limit" "Context work was exhausted.";
  {outcome_value;report_value;accepted_value=(if outcome_value=E.Pass then Some {request_value=request;context_value=context;
    assembly_value=assembly;discharge_values= !discharged;evidence_value=report_value;
    prerequisite_value=Option.map(fun prerequisite_evidence_value->{prerequisite_evidence_value})closure_evidence} else None)}
let replay ?parent ?maximum ~request ~assembly saved =
  M.check_resources saved;
  let fresh=check ?parent ?maximum ~request ~assembly () in
  Diagnostic.require (Json.equal saved (report fresh)) "policy_component_context_assessment_mismatch"
    "Composition context receipt differs from fresh checking.";
  fresh
