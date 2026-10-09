open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module O = Bioc_domain.Policy_operational
module F = Bioc_domain.Policy_operating_domain
module I = Bioc_domain.Policy_implementation
module P = Bioc_domain.Pinned_identity
module H = Bioc_domain.Policy_provider_prerequisites

type admitted_inputs = {
  request_value:R.t; behavior_value:O.behavior; domain_value:F.validated;
  model_values:P.t list; dependency_values:H.pending_dependency list; report_value:Json.t; charge_value:int -> unit;
}
module Make (Charge : sig val charge : int -> unit end) = struct
module Meter = Policy_generation_meter.Make(Charge)
module List = Meter.List
module String = Meter.String
module Json = Meter.Json
module Canonical = Meter.Canonical
module D = Meter.Document
module O = Meter.Operational
module Names = Meter.Names
let ( @ ) = List.append
let get = O.get
let text = O.text
let items = O.list
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let require ?path condition code message = Diagnostic.require ?path condition code message
let sorted values = List.sort_uniq String.compare values
let strings key value = List.map Json.string(items key value)
let unique values = List.length values=List.length(sorted values)
let pin_equal left right = Json.equal(P.to_json left)(P.to_json right)
let source_definitions document =
  List.fold_left (fun index value -> Names.add(text "id" value) value index) Names.empty
    (items "definitions" (get "semantics" (D.program document)))
let resolve_definition definitions pin =
  let definition=match Names.find_opt(text "id" pin) definitions with
    | Some value->value
    | None->Diagnostic.fail "policy_realization_definition" "Catalog definition body is absent from original authority." in
  require (text "version" pin=text "version" definition && text "digest" pin=D.document_digest definition)
    "policy_realization_definition" "Catalog DefinitionRef differs from its complete original body.";
  definition

let check_assurance document assessment (behavior:O.behavior) domain =
  let raw=D.to_json document in
  let assurance=get "assurance" raw in
  let supported condition message = require condition "policy_realization_assurance" message in
  supported(text "level" assurance="bounded") "This admission profile supports bounded assurance only; structural and proof requests need their own interpretations.";
  supported(items "assumptions" assessment=[] && items "assumptions" assurance=[])
    "This profile cannot discharge or use source assumptions to restrict its finite domain.";
  supported(items "tolerances" assurance=[]) "This exact observable profile supports no assurance tolerance overrides.";
  let horizon=get "horizon" assurance in
  supported(match horizon with Json.Object _->true|_->false) "Unbounded assurance cannot be admitted to a finite-domain profile.";
  let required_horizon=O.duration horizon in
  let domain_horizon=Q.mul (Q.of_int (F.specification domain).horizon_ticks) (F.resolution domain) in
  supported(Q.sign required_horizon>0 && Q.equal required_horizon domain_horizon)
    "Assurance and operating-domain horizons must match exactly on the supplied clock.";
  let requirements=behavior.requirements in
  supported(requirements<>[]) "Bounded realization inputs require an explicit nonempty hard-requirement inventory.";
  List.iter (fun (requirement:O.requirement) ->
    supported(List.mem requirement.kind ["safety";"progress"])
      "This profile admits safety/progress hard requirements only; preferences and other requirement interpretations are unsupported.";
    supported(match requirement.horizon with Some value->Q.equal value required_horizon|None->false)
      "Every original hard requirement needs the same explicit finite horizon as the assurance request.";
    supported(requirement.assumptions=[])
      "Requirement assumptions cannot silently narrow the supplied operating domain.") requirements;
  let requested=strings "requirements" assurance
  and hard=List.map(fun (requirement:O.requirement)->requirement.requirement_id)requirements in
  supported(unique requested && sorted requested=sorted hard)
    "Assurance must retain every original hard requirement exactly once.";
  requested

let check_catalog request document =
  let raw=D.to_json document in
  let catalog=get "implementations" raw in
  let entries=items "implementations" catalog and bridges=R.catalog_bindings request in
  let catalog_check condition message=require condition "policy_realization_catalog" message in
  catalog_check(entries<>[] && List.length entries<=128)
    "A supplied model library needs a nonempty bounded original implementation catalog; no model can supply missing source authorization.";
  catalog_check(List.length entries=List.length bridges)
    "Every original catalog entry requires exactly one external membership bridge.";
  let definitions=source_definitions document in
  let deployment=get "deployment" raw in
  let chassis=List.map(fun binding->text "id" (get "chassis" binding))(items "bindings" deployment) in
  require(text "route" deployment="in_vivo" && text "format" (get "payload" deployment)="RNA")
    "policy_realization_chassis" "The original deployment must retain its explicit in-vivo RNA context.";
  let effect_contracts=List.filter_map(fun (declaration:D.declaration)->
    if declaration.kind=D.Effect then Some(get "contract" declaration.value)else None)(D.declarations document) in
  catalog_check(effect_contracts<>[]) "This source/domain/model profile requires an explicit source effect operation.";
  let models=I.models(R.implementation_library request) in
  let authorized=ref [] in
  List.iter (fun (bridge:R.catalog_binding) ->
    let entry=match List.find_opt(fun entry->text "id" entry=bridge.entry_id)entries with
      | Some value->value
      | None->Diagnostic.fail "policy_realization_catalog" "Membership bridge names an absent original catalog entry." in
    catalog_check(text "version" entry=bridge.entry_version && Canonical.fingerprint entry=bridge.entry_digest)
      "Membership bridge does not pin the complete original catalog entry.";
    catalog_check(Json.equal (get "operation" entry) bridge.operation && Json.equal(get "realization" entry)bridge.realization)
      "Membership bridge changes the source operation or realization DefinitionRef.";
    ignore(resolve_definition definitions bridge.operation);
    let realization=resolve_definition definitions bridge.realization in
    catalog_check(List.exists(Json.equal bridge.operation)effect_contracts)
      "Only original source effect operations are catalog roots in this profile.";
    require(text "category" realization="model" && items "parameters" realization=[] &&
      get "result" realization=Json.Null && items "clauses" realization=[] &&
      get "executor_kind" realization=Json.Null && get "subject_kind" realization=Json.Null)
      "policy_realization_unsupported" "Realization declarations must be plain model identities; richer source contracts need a supplied executable interpretation.";
    let supported_chassis=strings "chassis" entry and formats=strings "payload_formats" entry in
    require(supported_chassis<>[] && unique supported_chassis &&
      List.for_all(fun identity->List.mem identity supported_chassis)chassis && formats=["RNA"])
      "policy_realization_chassis" "Catalog entry does not explicitly support the complete original chassis/RNA deployment.";
    List.iter(fun key->List.iter(fun reference->ignore(resolve_definition definitions reference))(items key entry))
      ["dependencies";"evidence"];
    (if R.requires_prerequisite_closure request then
      require(items "evidence" entry=[])
        "policy_realization_unsupported" "Empirical evidence references cannot discharge executable provider prerequisites."
    else require(items "dependencies" entry=[] && items "evidence" entry=[])
      "policy_realization_unsupported" "Implementation dependency/evidence closure is not executable in this profile; source pins cannot infer carriers or establish supporting claims.");
    List.iter(fun pin->
      require(List.exists(fun(model:I.model)->pin_equal model.identity pin)models)
        "policy_realization_model" "Catalog bridge selects a model absent from the independently supplied library.";
      if not(List.exists(pin_equal pin)!authorized)then authorized:= !authorized@[pin])bridge.models) bridges;
  List.iter(fun operation->catalog_check(List.exists(fun entry->Json.equal(get "operation" entry)operation)entries)
    "A source effect operation has no original catalog implementation binding.")effect_contracts;
  require(List.length !authorized=List.length models && List.for_all(fun(model:I.model)->
    List.exists(pin_equal model.identity)!authorized)models) "policy_realization_model"
    "Every supplied library model must be explicitly authorized by the original catalog bridge in this initial profile.";
  !authorized,Canonical.fingerprint catalog

let check_network_source request document (behavior:O.behavior) =
  let network ?path condition message=require ?path condition "policy_realization_network" message in
  let bounded low high values=let count=List.length values in count>=low && count<=high in
  network(List.length behavior.roles=1 && List.length behavior.encounters=1 &&
    List.length behavior.subjects=1 && List.length behavior.clocks=1 && List.length behavior.parameters=1 &&
    bounded 2 4 behavior.observations && bounded 2 4 behavior.machines && bounded 0 4 behavior.stores &&
    bounded 1 32 behavior.transitions && bounded 1 8 behavior.effects && behavior.rules=[] &&
    List.length(R.catalog_bindings request)=1)
    "Network inputs require one executor/encounter/subject/clock/product/catalog bridge, 2-4 observations/machines, up to four stores, 1-32 transitions and 1-8 effects.";
  let declarations=D.declarations document in
  let declaration id=List.find(fun(value:D.declaration)->String.equal value.id id)declarations in
  let raw id=(declaration id).value and path id=(declaration id).path in
  let role=List.hd behavior.roles and encounter=List.hd behavior.encounters
  and subject=List.hd behavior.subjects and clock=List.hd behavior.clocks and product=List.hd behavior.parameters in
  let absent p fields value=List.iter(fun key->network ~path:p (get key value=Json.Null)
    "Network source field requires another executable interpretation.")fields in
  let value_type p kind value=network ~path:p
    (text "kind" value=kind && get "unit" value=Json.Null && get "entity_kind" value=Json.Null)
    "Network expressions require exact truth/event/fixed-product types." in
  let reference kind id=Json.Object["$type",str "Ref";"kind",str kind;"id",str id]in
  let ref_equal value field kind id=Json.equal(get field value)(reference kind id)in
  let positive_ticks p duration=let ticks=Q.div duration clock.resolution in
    network ~path:p (Q.sign ticks>0 && Z.equal(Q.den ticks)Z.one && Z.compare(Q.num ticks)(Z.of_int 10000)<=0)
      "Network freshness and timeout durations require bounded positive integral original-clock ticks."in
  network(encounter.executor=role.role_id && encounter.target=subject.subject_id && encounter.termination="explicit_event" &&
    subject.executor=Some role.role_id && subject.encounter=Some encounter.encounter_id)
    "Network declarations must retain the same original executor, encounter and subject.";
  absent(path subject.subject_id)["domain"](raw subject.subject_id);
  network ~path:(path clock.clock_id) (text "simultaneous"(raw clock.clock_id)="atomic_batch" &&
    List.mem(text "basis"(raw clock.clock_id))["logical";"availability"])
    "Network inputs require one logical/availability clock with atomic batches.";
  List.iter(fun(observation:O.observation)->let p=path observation.observation_id in
    network ~path:p (observation.value_type=O.Truth_type && observation.observer=role.role_id &&
      observation.subject=subject.subject_id && observation.clock=clock.clock_id && observation.coverage="event")
      "Network observations must retain independent encounter-local truth evidence on the original clock.";
    value_type p "truth"(get "value_type"(raw observation.observation_id));positive_ticks p observation.freshness)behavior.observations;
  network(unique(List.map(fun(observation:O.observation)->observation.coherence)behavior.observations))
    "Network observations require distinct original coherence groups.";
  let own_transitions id=List.filter(fun(transition:O.transition)->String.equal transition.machine id)behavior.transitions in
  List.iter(fun(machine:O.machine)->network ~path:(path machine.machine_id)
    (bounded 2 16 machine.states && own_transitions machine.machine_id<>[] && machine.executor=role.role_id &&
      machine.scope=O.Encounter encounter.encounter_id && machine.lifetime="encounter" &&
      machine.arbitration.mode="priority" && machine.arbitration.tie="declared_order" && machine.arbitration.write_conflict="reject")
    "Network machines need bounded states, owned transitions and explicit priority with rejected conflicting writes.")behavior.machines;
  let policies=List.map(fun(machine:O.machine)->machine.machine_id,
    Canonical.encode(get "arbitration"(raw machine.machine_id)))behavior.machines in
  List.iter(fun(machine:O.machine)->let key=List.assoc machine.machine_id policies in
    let governed=List.filter(fun(transition:O.transition)->String.equal(List.assoc transition.machine policies)key)behavior.transitions in
    network ~path:(path machine.machine_id)
      (List.equal String.equal (List.sort String.compare machine.arbitration.order)
        (List.sort String.compare(List.map(fun(transition:O.transition)->transition.transition_id)governed)))
      "A network priority order must name exactly the complete transition group sharing that policy.")behavior.machines;
  List.iter(fun(store:O.state_store)->let p=path store.state_id and source=raw store.state_id in
    let owners=List.filter_map(fun(transition:O.transition)->
      if List.exists(fun(assignment:O.assignment)->String.equal assignment.state store.state_id)transition.assignments
      then Some transition.machine else None)behavior.transitions|>sorted in
    network ~path:p (List.length owners=1 && store.value_type=O.Truth_type &&
      store.scope=O.Encounter encounter.encounter_id && store.lifetime="encounter" && store.reset=None && store.capacity>=2 &&
      text "overflow" source="reject" && text "inheritance" source="not_applicable" &&
      (match store.initial with O.Truth(O.True|O.False)->true|_->false))
      "Network stores require a known initial Boolean, one writer machine and bounded encounter lifetime without predicate resets.";
    value_type p "truth"(get "value_type" source);absent p ["duration";"coordination";"contract"]source)behavior.stores;
  let product_raw=raw product.parameter_id in
  network ~path:(path product.parameter_id) (text "selection" product_raw="fixed" && (match product.value with O.Text _->true|_->false))
    "Network effects require one original fixed text product.";
  value_type(path product.parameter_id)"text"(get "value_type" product_raw);
  absent(path product.parameter_id)["lower";"upper"]product_raw;
  let common p value=absent p ["contract";"duration";"clock";"coverage";"binding"]value in
  let pure p value=absent p ["ref";"scope";"value"]value in
  let observed p value=let id=O.ref_id(get "ref" value)in
    network ~path:p (List.exists(fun(observation:O.observation)->String.equal observation.observation_id id)behavior.observations &&
      items "args" value=[] && get "value" value=Json.Null && ref_equal value "ref" "Observation" id &&
      ref_equal value "scope" "Subject" subject.subject_id)"Network evidence reference must preserve its original observation and subject." in
  let rec truth_expression p observations_only value=
    Charge.charge 1;common p value;value_type p "truth"(get "value_type" value);
    let args=items "args" value in
    match text "op" value with
    |"literal"->absent p ["ref";"scope"]value;
      network ~path:p (args=[] && (match (O.expression_of_json value).value with Some(O.Truth _)->true|_->false))
        "Network literal must be a truth value without operands."
    |"observe"->observed p value
    |"state"->let id=O.ref_id(get "ref" value)in
      network ~path:p (not observations_only && args=[] && get "value" value=Json.Null &&
        List.exists(fun(store:O.state_store)->String.equal store.state_id id)behavior.stores &&
        ref_equal value "ref" "StateStore" id && ref_equal value "scope" "Encounter" encounter.encounter_id)
        "Network state reads require original encounter truth storage and cannot supply observed-edge memory."
    |"not"|"all"|"any" as operator->pure p value;
      network ~path:p (if operator="not"then List.length args=1 else bounded 1 64 args)
        "Network truth operation has unsupported arity.";
      List.iteri(fun index value->truth_expression(Meter.append_string p ("/args/"^string_of_int index)) observations_only value)args
    |_->network ~path:p false "Expression has no interpretation in the network truth profile."in
  let initiators=List.map(fun(effect_value:O.effect_spec)->
    let values=List.filter(fun(transition:O.transition)->List.mem effect_value.effect_id transition.effects)behavior.transitions in
    network ~path:(path effect_value.effect_id) (List.length values=1 && (List.hd values).effects=[effect_value.effect_id])
      "Each network effect must have exactly one single-effect initiating transition.";
    effect_value.effect_id,(List.hd values).machine)behavior.effects in
  List.iter(fun(effect_value:O.effect_spec)->let p=path effect_value.effect_id and source=raw effect_value.effect_id in
    network ~path:p (effect_value.executor=role.role_id && effect_value.subject=subject.subject_id && effect_value.lifecycle.on_loss="continue" &&
      Json.equal(get "contract" source)(List.hd(R.catalog_bindings request)).operation)
      "Network effects must retain the original operation, executor and subject.";
    (match effect_value.lifecycle.timeout with Some timeout->positive_ticks p timeout|None->network ~path:p false "Network effects need explicit finite timeouts.");
    network ~path:p (List.length(items "parameters" source)=1)"Network effects require exactly one fixed-product argument.";
    let argument=List.hd(items "parameters" source)in let value=get "value" argument in
    common p value;value_type p "text"(get "value_type" value);
    network ~path:p (text "name" argument="product" && text "op" value="parameter" && items "args" value=[] &&
      get "scope" value=Json.Null && get "value" value=Json.Null && ref_equal value "ref" "Parameter" product.parameter_id)
      "Network effect argument must retain the original fixed-product parameter.")behavior.effects;
  List.iter(fun(transition:O.transition)->let p=path transition.transition_id and source=raw transition.transition_id in
    let machine=List.find(fun(machine:O.machine)->String.equal machine.machine_id transition.machine)behavior.machines in
    network ~path:p (not(List.mem transition.source machine.terminal) && List.length transition.effects<=1 &&
      bounded 0 4 transition.assignments && unique(List.map(fun(assignment:O.assignment)->assignment.state)transition.assignments))
      "Network transitions forbid terminal departures and duplicate or unbounded atomic actions.";
    truth_expression(Meter.append_string p "/when")false(get "when" source);
    List.iteri(fun index value->truth_expression(Meter.append_string p ("/assignments/"^string_of_int index^"/value"))false(get "value" value))
      (items "assignments" source);
    let event=get "on" source and event_path=Meter.append_string p "/on"in
    common event_path event;value_type event_path "event"(get "value_type" event);
    match text "op" event with
    |"updated"->observed event_path event
    |"rising"->pure event_path event;network ~path:event_path (List.length(items "args" event)=1)"Network rising needs one observed truth predicate.";
      let predicate=List.hd(items "args" event)in truth_expression(Meter.append_string event_path "/args/0")true predicate;
      let rec has_observation value=Charge.charge 1;text "op" value="observe" || List.exists has_observation(items "args" value)in
      network ~path:event_path (has_observation predicate)"Network rising must contain an original observation."
    |"effect_event"->let id=O.ref_id(get "ref" event)in
      network ~path:event_path (items "args" event=[] && List.mem_assoc id initiators &&
        String.equal(List.assoc id initiators)transition.machine && ref_equal event "ref" "Effect" id &&
        ref_equal event "scope" "Subject" subject.subject_id && List.mem(text "value" event)["completed";"failed";"timed_out"])
        "Network feedback requires a supported outcome from the same machine's retained effect attempt."
    |_->network ~path:event_path false "Network transition event requires an observation update/edge or correlated effect outcome.")behavior.transitions;
  List.iter(fun(declaration:D.declaration)->network ~path:declaration.path
    (List.mem declaration.kind[D.Role;D.Subject;D.Encounter;D.Clock;D.Observation;D.State_store;D.Parameter;D.Effect;D.Machine;D.Transition;D.Requirement])
    "Declaration is outside the network source profile.")declarations

let admit ~request ~(behavior:O.behavior) =
  let document=R.document request and descriptors=R.definitions request in
  let assessment,correspondence=if R.is_coupled request then (
    (* Correspondence independently admits this same immutable original source
       before comparing every behavior field. Reuse only its freshly produced
       assessment data within this invocation, avoiding a second identical
       admission; callers cannot supply a saved report or an admitted source. *)
    let fresh=Policy_correspondence.check_fresh ~charge:Charge.charge
      ~expected_document:document ~descriptors behavior in
    Policy_correspondence.source_assessment fresh,Policy_correspondence.report fresh)
  else (
    let source=Policy_admission.admit_metered ~charge:Charge.charge ~document ~descriptors in
    let correspondence=Policy_correspondence.check ~charge:Charge.charge ~expected_document:document ~descriptors behavior in
    Policy_admission.source_assessment source,correspondence)in
  (if R.is_two_observation request then
    match behavior.observations with
    | [left;right] ->
      require (behavior.machines=[] && behavior.transitions=[] &&
        left.value_type=O.Truth_type && right.value_type=O.Truth_type &&
        String.equal left.observer right.observer && String.equal left.subject right.subject &&
        String.equal left.clock right.clock && String.equal left.coverage "event" &&
        String.equal right.coverage "event" && not (String.equal left.coherence right.coherence))
        "policy_realization_two_observation"
        "Two-observation inputs require independent truth evidence on one executor, encounter subject and clock, without frame joining or machine semantics."
    | _ -> require false "policy_realization_two_observation"
        "The two-observation family requires exactly two original observations.");
  (if R.is_multi_product request then
    require (List.length behavior.parameters=2 && List.length behavior.effects=2 &&
      List.length behavior.observations=1 && List.length behavior.machines=1 &&
      List.length behavior.transitions=7 && behavior.rules=[] && behavior.stores=[])
      "policy_realization_multi_product"
      "Multi-product inputs require two original fixed products and two effects in the bounded staged machine family.");
  (if R.is_finite_machine request then (
    let finite condition message=require condition "policy_realization_finite_machine" message in
    finite (List.length behavior.roles=1 && List.length behavior.encounters=1 &&
      List.length behavior.subjects=1 && List.length behavior.clocks=1 &&
      List.length behavior.parameters=1 && List.length behavior.observations=1 &&
      List.length behavior.machines=1 && behavior.rules=[] &&
      (if R.is_coupled request then List.length behavior.stores>=2 && List.length behavior.stores<=4 else behavior.stores=[]) &&
      List.length behavior.effects>=1 && List.length behavior.effects<=8 &&
      List.length behavior.transitions>=1 && List.length behavior.transitions<=32)
      "Finite-machine inputs require one executor, encounter, clock, truth observation, fixed product and machine, one to eight effects and one to thirty-two transitions without separate rules/stores.";
    let machine=List.hd behavior.machines in
    finite (List.length machine.states>=2 && List.length machine.states<=16 &&
      (List.hd behavior.observations).value_type=O.Truth_type &&
      (match (List.hd behavior.parameters).value with O.Text _->true|_->false))
      "Finite-machine inputs require two to sixteen ordered states, truth evidence and a fixed text product.";
    finite (List.for_all(fun(transition:O.transition)->
      String.equal transition.machine machine.machine_id &&
      (if R.is_coupled request then List.map(fun(a:O.assignment)->a.state)transition.assignments=
        List.map(fun(s:O.state_store)->s.state_id)behavior.stores else transition.assignments=[]) &&
      List.length transition.effects<=1 && not(List.mem transition.source machine.terminal) &&
      List.mem transition.on.op ["rising";"updated";"effect_event"])behavior.transitions &&
      List.for_all(fun(effect_value:O.effect_spec)->
        let count=List.length(List.filter(fun(transition:O.transition)->List.mem effect_value.effect_id transition.effects)behavior.transitions)in
        if R.is_multi_site request then count>=1 else count=1)
        behavior.effects)
      (if R.is_multi_site request then
        "Multi-site transitions retain their sole machine, exclusive event arbitration and at most one request; every effect has at least one original initiating transition."
       else "Finite-machine transitions retain their sole machine and event triggers, forbid terminal reentry and assignments, and give every effect exactly one initiating transition.")));
  (if R.is_network request then check_network_source request document behavior);
  (* Only externally checked source behavior reaches environment compatibility.
     Neither decoder nor caller-supplied candidate claims can replace this step. *)
  let domain_value=F.validate_for ~charge:Charge.charge ~behavior (R.operating_domain request) in
  (if R.is_finite_machine request then
    require (List.length (F.specification domain_value).encounters=2)
      "policy_realization_finite_machine" "Finite-machine inputs require exactly two original encounter slots.");
  (if R.is_network request then
    require (List.length (F.specification domain_value).encounters=2)
      "policy_realization_network" "Network inputs require exactly two original encounter slots.");
  let requested=check_assurance document assessment behavior domain_value in
  let model_values,catalog_digest=check_catalog request document in
  let prerequisite_closure=R.requires_prerequisite_closure request in
  let dependency_values=if prerequisite_closure then H.pending_dependencies ~charge:Charge.charge request else [] in
  let report_fields=[
    "schema_version",str (if prerequisite_closure then "biocompiler.policy_realization_admission.v0.2" else "biocompiler.policy_realization_admission.v0.1");
    "profile",str (R.request_profile request);"resource_profile",str R.resource_profile;"status",str "admitted_inputs";
    "request_fingerprint",str(R.fingerprint request);
    "source_artifact_digest",str(D.artifact_digest document);"document_digest",str(D.fingerprint document);
    "descriptors_digest",str(O.descriptors_digest descriptors);
    "operating_domain_digest",str(F.digest(R.operating_domain request));
    "implementation_catalog_digest",str catalog_digest;
    "implementation_library_digest",str(I.library_digest(R.implementation_library request));
    "catalog_bindings_digest",str(R.catalog_bindings_digest request);
    "source_assessment",assessment;"source_correspondence",correspondence;
    "requested_requirements",arr(List.map str requested);
    "authorized_models",arr(List.map P.to_json model_values);
    "assurance",get "assurance" (D.to_json document);"budgets",get "budgets" (R.to_json request);
    "exploration",str "not_performed";"preservation",str "unassessed";
    "requirements",str "unassessed";"target_status",str "unassessed";
    "material",str "unassessed";"export",str "withheld";"artifact",str "withheld";
    "unresolved_obligations",arr(List.map str ["complete_finite_domain_exploration";
      "independent_implementation_execution";"source_implementation_preservation";
      "whole_domain_hard_requirements";"original_assurance_satisfaction";
      "deployment_and_material_carriers";"material_correspondence";"fresh_export_acceptance"])] in
  let report_value=obj (if prerequisite_closure then report_fields @
    ["pending_dependencies",arr(List.map H.pending_dependency_to_json dependency_values)] else report_fields) in
  Meter.preflight report_value;
  {request_value=request;behavior_value=behavior;domain_value;model_values;dependency_values;report_value;charge_value=Charge.charge}
end
let admit_metered ~charge ~request ~behavior =
  let module Admission = Make(struct let charge = charge end) in
  Admission.admit ~request ~behavior
let admit ~request ~behavior = admit_metered ~charge:Policy_generation_meter.no_charge ~request ~behavior
let request value = value.request_value
let behavior value = value.behavior_value
let operating_domain value = value.domain_value
let authorized_models value = value.model_values
let pending_dependencies value = value.dependency_values
let require_model value ~entry_id pin =
  let module Meter = Policy_generation_meter.Make(struct let charge = value.charge_value end) in
  let module List = Meter.List in
  let pin_equal left right = Meter.Json.equal(P.to_json left)(P.to_json right) in
  let require condition code message = Diagnostic.require condition code message in
  let bridge=List.find_opt(fun (bridge:R.catalog_binding)->bridge.entry_id=entry_id)
    (R.catalog_bindings value.request_value) in
  require(match bridge with Some bridge->List.exists(pin_equal pin)bridge.models|None->false)
    "policy_realization_model" "Model is not authorized by this admitted original catalog entry."
let report value = value.report_value
