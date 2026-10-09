open Bioc_wire
module Contract=Bioc_domain.Policy_approximation_contract
module Network=Bioc_domain.Policy_quantitative_network_contract
module M=Bioc_domain.Policy_component_material_request
module R=Bioc_domain.Policy_realization_request
module F=Bioc_domain.Policy_operating_domain
module Library=Bioc_domain.Policy_component_library
module Local=Bioc_domain.Policy_component_material
module Coupled=Bioc_domain.Policy_quantitative_composition_contract
module K=Bioc_domain.Construction_content
module E=Bioc_domain.Construction_assessment
module Material=Policy_component_material_check
module Context=Policy_component_context_check
module Assembly=Policy_component_assembly_check
module Structure=Bioc_checker.Policy_mrna_structure_check
module W=Bioc_checker.Work_budget
let schema_version="biocompiler.policy_approximation_assessment.v0.1"
let profile=Contract.profile
let implementation_version="biocompiler.ocaml.policy_approximation_check.v0.1"
let max_work=128*1024*1024
let str value=Json.String value
let obj fields=Json.Object fields
let arr values=Json.Array values
type checked_approximation={contract_value:Contract.t;material_value:Material.checked_material;evidence_value:Json.t}
type result={report_value:Json.t;outcome_value:E.outcome;accepted_value:checked_approximation option}
let report value=value.report_value
let outcome value=value.outcome_value
let accepted value=value.accepted_value
let evidence value=value.evidence_value
let contract value=value.contract_value
let material value=value.material_value

module Make(Charge:sig val charge:int->unit end)=struct
  module Meter=Bioc_checker.Policy_generation_meter.Make(Charge)
  module List=Meter.List
  let fail condition message=Diagnostic.require condition "policy_approximation_fail" message
  let hash value=Meter.preflight value;Meter.Canonical.fingerprint value
  let get key value=Meter.Json.field key(Meter.Json.object_fields value)
  let qmax left right=if Q.compare left right>=0 then left else right
  let maximum values=List.fold_left qmax Q.zero values
  let position name reservoirs=
    let rec find index=function
      |[]->Diagnostic.fail "policy_approximation_fail" "An observation or transfer lost its original reservoir."
      |(value:Network.reservoir)::rest->Charge.charge 1;if value.compartment=name then index else find(index+1)rest in
    find 0 reservoirs
  let vectors (mechanism:Network.mechanism)=
    List.init mechanism.levels(fun ordinal->
      let divisor=ref mechanism.levels in
      Array.of_list(List.map(fun(value:Network.reservoir)->divisor:= !divisor/value.levels;(ordinal/ !divisor)mod value.levels)mechanism.reservoirs))
  let locate states vector=
    let rec find index=function
      |[]->Diagnostic.fail "policy_approximation_fail" "A reserved update escaped the complete original finite grid."
      |value::rest->Charge.charge(Array.length vector);if value=vector then index else find(index+1)rest in find 0 states
  let initials mechanism states=
    let values=Array.of_list(List.map(fun(value:Network.reservoir)->Z.to_int(Q.num(Q.div value.initial.amount mechanism.Network.quantum.amount)))mechanism.Network.reservoirs)in
    locate states values
  let advance (mechanism:Network.mechanism) states state sample=
    Charge.charge 1;
    match sample with None->state,false|Some truth->
    let before=List.nth states state in
    let size=Array.length before in
    Charge.charge(3*size);
    let outgoing=Array.make size 0 and incoming=Array.make size 0 in
    List.iter(fun(edge:Network.transfer)->
      let source=position edge.source mechanism.reservoirs and destination=position edge.destination mechanism.reservoirs in
      let receiver=List.nth mechanism.reservoirs destination in
      let maximum=Z.to_int(Q.num(Q.div edge.amount.amount mechanism.quantum.amount))in
      let amount=if truth=edge.enabled_when then min maximum(min(before.(source)-outgoing.(source))
        (receiver.levels-1-before.(destination)-incoming.(destination)))else 0 in
      fail(amount>=0)"A reservation exceeded its prestate donor or receiver bound.";
      outgoing.(source)<-outgoing.(source)+amount;incoming.(destination)<-incoming.(destination)+amount)mechanism.transfers;
    let after=Array.init size(fun index->before.(index)-outgoing.(index)+incoming.(index))in
    let threshold_index=position mechanism.threshold.compartment mechanism.reservoirs in
    let threshold=Z.to_int(Q.num(Q.div mechanism.threshold.amount.amount mechanism.quantum.amount))in
    locate states after,(before.(threshold_index)<threshold && after.(threshold_index)>=threshold)
  let observed (endpoint:Contract.endpoint) mechanism states state=
    let vector=List.nth states state in
    List.map(fun name->Q.mul mechanism.Network.quantum.amount(Q.of_int vector.(position name mechanism.Network.reservoirs)))endpoint.observation
  let differences left right=List.map2(fun x y->Charge.charge 1;Q.abs(Q.sub x y))left right
  let combine left right=List.map2 qmax left right
  let rational unit value=Contract.rational_to_json ~unit value
  let envelope_json unit envelope=arr(Array.to_list(Array.mapi(fun round errors->
    obj["round",Json.int round;"coordinates",arr(List.map(rational unit)errors)])envelope))
  let check_link (contract:Contract.t) (link:Contract.link)=
    let cases=Contract.cases ~charge:Charge.charge link in
    let zeros=List.map(fun _->Q.zero)contract.coordinates in
    let envelope=Array.make(contract.horizon_steps+1)zeros in
    let right=link.target.mechanism in
    let right_states=vectors right in
    let right_initial=initials right right_states in
    let rows=List.mapi(fun case_index left->
      let left_states=vectors left in
      let left_initial=initials left left_states in
      let initial_pair=left_initial,right_initial in
      let reachable=ref[initial_pair]in
      let peak=ref zeros and transitions=ref 0 and pairs=ref 1 in
      let observe (x,y)=
        let values=differences(observed link.source left left_states x)(observed link.target right right_states y)in
        peak:=combine !peak values in
      observe initial_pair;envelope.(0)<-combine envelope.(0) !peak;
      for round=1 to contract.horizon_steps do
        Charge.charge 256;
        let seen=Array.make 256 false and next=ref[]in
        List.iter(fun pair->List.iter(fun reset->
          let x,y=if reset then initial_pair else pair in
          List.iter(fun sample->
            let next_x,request_x=advance left left_states x sample
            and next_y,request_y=advance right right_states y sample in
            incr transitions;
            fail(request_x=request_y)("Exact request labels differ in link "^link.id^", case "^string_of_int case_index^", round "^string_of_int round^".");
            let next_pair=next_x,next_y in observe next_pair;
            let key=next_x*16+next_y in
            if not seen.(key)then(seen.(key)<-true;next:=next_pair:: !next))
            [Some true;Some false;None;None])[false;true]) !reachable;
        reachable:=List.rev !next;pairs:= !pairs+List.length !reachable;
        envelope.(round)<-combine envelope.(round) !peak
      done;
      obj["mechanism_fingerprint",str(hash(Network.to_json left));"visited_pair_rounds",Json.int !pairs;
        "checked_transition_rows",Json.int !transitions])cases in
    let bounds=envelope.(contract.horizon_steps)in
    fail(Q.compare(maximum bounds)link.maximum_error.value<=0)("Derived error exceeds the original budget for link "^link.id^".");
    let scope=obj["horizon_steps",Json.int contract.horizon_steps;"metric",str "coordinatewise_absolute_prefix_error";
      "coordinates",arr(List.map str contract.coordinates);"unit",contract.unit;
      "sample_period",link.source.mechanism.sample_period.raw]in
    let summary=obj["id",str link.id;"relation",str "bounded_sampled_observation_error";
      "source_fingerprint",str(hash link.source.raw);"target_fingerprint",str(hash link.target.raw);
      "scope",scope;"uncertainty_cases",arr rows;"case_count",Json.int(List.length rows);
      "envelope",envelope_json contract.unit envelope;"coordinate_bounds",arr(List.map(rational contract.unit)bounds);
      "maximum_error",rational contract.unit(maximum bounds);"declared_maximum_error",link.maximum_error.raw;
      "request_labels",str "exact_on_all_checked_synchronized_transitions"]in
    summary,envelope
  let execute checked (contract:Contract.t)=
    let request=Material.request checked in
    Meter.preflight(M.to_json request);Meter.preflight(Contract.to_json contract);
    Meter.preflight(Material.evidence checked);
    fail(M.is_transfer_network request || M.is_quantitative_composition request)
      "Approximation requires an exact reserved-network material profile.";
    let selected=match M.network_quantitative request with Some value->value|None->assert false in
    fail(Option.is_some(Material.quantitative checked))"Approximation requires a fresh accepted quantitative material capability.";
    let domain=R.operating_domain(M.implementation_request request)in
    fail(contract.horizon_steps=domain.F.horizon_ticks+1)
      "Approximation must cover exactly the complete inclusive material-domain horizon.";
    let last=List.hd(List.rev contract.links)in
    fail(Meter.Json.equal(Network.to_json last.target.mechanism)(Network.to_json selected.mechanism))
      "The final approximation law differs from the selected exact material mechanism.";
    let local=match Library.find(M.component_library request)selected.component with
      |Some component->
        let contracts=Local.transfer_network_contracts component @ List.filter_map(fun(value:Coupled.local_contract)->
          match value.role with Coupled.Coordinator coordinator->Some coordinator.network|Coupled.Owner _->None)
          (Local.composition_contracts component)in
        (match List.find_opt(fun(value:Network.local_contract)->value.id=selected.contract)contracts with
        |Some value->value|None->Diagnostic.fail "policy_approximation_fail" "The selected network contract is absent from its original component.")
      |None->Diagnostic.fail "policy_approximation_fail" "The selected approximation component is absent."in
    fail(Meter.Json.equal(Network.to_json local.mechanism)(Network.to_json last.target.mechanism))
      "Approximation lost the complete selected component's exact mechanism identity.";
    let checked_links=List.map(check_link contract)contract.links in
    let zeros=List.map(fun _->Q.zero)contract.coordinates in
    let composed=Array.make(contract.horizon_steps+1)zeros in
    List.iter(fun(_,envelope)->Array.iteri(fun index bounds->Charge.charge(List.length bounds);
      composed.(index)<-List.map2 Q.add composed.(index)bounds)envelope)checked_links;
    let bounds=composed.(contract.horizon_steps)in
    fail(Q.compare(maximum bounds)contract.maximum_error.value<=0)
      "The monotone triangle sum exceeds the original complete-chain error budget.";
    let first=List.hd contract.links in
    let content=Structure.content(Assembly.structure(Context.assembly(Material.context checked)))in
    let scope=obj["operating_domain_fingerprint",str(hash(F.to_json domain));"horizon_steps",Json.int contract.horizon_steps;
      "metric",str "coordinatewise_absolute_prefix_error";"coordinates",arr(List.map str contract.coordinates);"unit",contract.unit;
      "sample_period",selected.mechanism.sample_period.raw;
      "samples",arr(List.map str["true";"false";"unknown";"no_update"]);
      "lifecycle",str "synchronized_reset_before_each_sample_or_keep";
      "uncertainty",str "all_closed_grid_cases_fixed_within_each_encounter_generation"]in
    let reports=List.map fst checked_links in
    let composition=obj["relation",str "conditional_approximate_source_material_correspondence";
      "rule",str "monotone_triangle_error_chain_with_exact_material";
      "source_fingerprint",str(hash first.source.raw);"target_fingerprint",str(hash(K.to_json content));
      "material_request_fingerprint",str(hash(M.to_json request));"material_report_fingerprint",str(hash(Material.evidence checked));
      "selected_mechanism_fingerprint",str(hash(Network.to_json selected.mechanism));
      "selection",get "selection"(Network.selection_to_json selected);"source",get "source"(Network.selection_to_json selected);
      "scope",scope;"inputs",arr(List.map(fun value->str(hash value))reports);
      "envelope",envelope_json contract.unit composed;"coordinate_bounds",arr(List.map(rational contract.unit)bounds);
      "maximum_error",rational contract.unit(maximum bounds);"declared_maximum_error",contract.maximum_error.raw]in
    reports,composition
end

let check ?parent ?(maximum=max_work) ~material ~contract ()=
  Diagnostic.require(maximum>=0 && maximum<=max_work)"policy_approximation_resource_limit" "Approximation work allowance is outside its fixed ceiling.";
  let budget=match parent with None->W.create ~profile ~error_code:"policy_approximation_resource_limit" ~maximum()
    |Some parent->W.nested ~parent ~profile ~error_code:"policy_approximation_resource_limit" ~maximum()in
  let before=W.remaining budget in
  let module Check=Make(struct let charge=W.charge budget end)in
  let links,composition,issues,outcome_value=match Check.execute material contract with
    |links,composition->links,composition,[],E.Pass
    |exception Diagnostic.Error error when error.code="policy_approximation_fail"->[],Json.Null,[error.message],E.Fail in
  let request=Material.request material in
  let fields=["schema_version",str schema_version;"profile",str profile;"implementation",str implementation_version;
    "outcome",str(E.outcome_name outcome_value);"contract_fingerprint",str(Check.hash(Contract.to_json contract));
    "material_request_fingerprint",str(Check.hash(M.to_json request));"material_report_fingerprint",str(Check.hash(Material.evidence material));
    "claim_scope",str "bounded_model_conditional_observation_error_and_exact_request_labels";
    "links",arr links;"composition",composition;"issues",arr(List.map str issues);
    "empirical",str "unassessed";"artifact",str "withheld";"export",str "withheld"]in
  let usage amount=obj["unit",str "logical_data_visits_and_synchronized_product_work";"charged_work",Json.int amount]in
  let reserved=obj(fields@["usage",usage maximum])in
  Check.Meter.preflight reserved;Check.Meter.serialization reserved;
  let output=W.create_output ~profile ~error_code:"policy_approximation_publication_limit" ~max_bytes:1048576 ~max_nodes:65536()in
  W.reserve_json output reserved;
  let report_value=obj(fields@["usage",usage(before-W.remaining budget)])in
  Diagnostic.require(not(W.exhausted budget))"policy_approximation_resource_limit" "Approximation work was exhausted.";
  let accepted_value=if outcome_value=E.Pass then Some{contract_value=contract;material_value=material;evidence_value=report_value}else None in
  {report_value;outcome_value;accepted_value}
