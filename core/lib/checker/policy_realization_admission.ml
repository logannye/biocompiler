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

let admit ~request ~(behavior:O.behavior) =
  let document=R.document request and descriptors=R.definitions request in
  let source=Policy_admission.admit_metered ~charge:Charge.charge ~document ~descriptors in
  let correspondence=Policy_correspondence.check ~charge:Charge.charge ~expected_document:document ~descriptors behavior in
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
      List.length behavior.machines=1 && behavior.rules=[] && behavior.stores=[] &&
      List.length behavior.effects>=1 && List.length behavior.effects<=8 &&
      List.length behavior.transitions>=1 && List.length behavior.transitions<=32)
      "Finite-machine inputs require one executor, encounter, clock, truth observation, fixed product and machine, one to eight effects and one to thirty-two transitions without separate rules/stores.";
    let machine=List.hd behavior.machines in
    finite (List.length machine.states>=2 && List.length machine.states<=16 &&
      (List.hd behavior.observations).value_type=O.Truth_type &&
      (match (List.hd behavior.parameters).value with O.Text _->true|_->false))
      "Finite-machine inputs require two to sixteen ordered states, truth evidence and a fixed text product.";
    finite (List.for_all(fun(transition:O.transition)->
      String.equal transition.machine machine.machine_id && transition.assignments=[] &&
      List.length transition.effects<=1 && not(List.mem transition.source machine.terminal) &&
      List.mem transition.on.op ["rising";"updated";"effect_event"])behavior.transitions &&
      List.for_all(fun(effect:O.effect_spec)->
        List.length(List.filter(fun(transition:O.transition)->List.mem effect.effect_id transition.effects)behavior.transitions)=1)
        behavior.effects)
      "Finite-machine transitions retain their sole machine and event triggers, forbid terminal reentry and assignments, and give every effect exactly one initiating transition."));
  (* Only externally checked source behavior reaches environment compatibility.
     Neither decoder nor caller-supplied candidate claims can replace this step. *)
  let domain_value=F.validate_for ~charge:Charge.charge ~behavior (R.operating_domain request) in
  (if R.is_finite_machine request then
    require (List.length (F.specification domain_value).encounters=2)
      "policy_realization_finite_machine" "Finite-machine inputs require exactly two original encounter slots.");
  let assessment=Policy_admission.source_assessment source in
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
