open Bioc_wire
module Contract = Bioc_domain.Policy_realization_evidence_contract
module Material = Policy_component_material_check
module R = Bioc_domain.Policy_component_material_request
module NC = Bioc_domain.Policy_quantitative_network_contract
module Rule = Bioc_domain.Policy_component_assembly_rule
module Local = Bioc_domain.Policy_component_material
module Pin = Bioc_domain.Pinned_identity
module W = Bioc_checker.Work_budget
type status = Supported | Incompatible | Unassessed
let status_name=function Supported->"supported"|Incompatible->"incompatible"|Unassessed->"unassessed"
let schema_version="biocompiler.policy_realization_evidence_assessment.v0.1"
let profile=Contract.profile
let implementation_version="biocompiler.ocaml.policy_realization_evidence_check.v0.1"
let max_work=64*1024*1024
let str value=Json.String value
let obj value=Json.Object value
type checked_evidence={material_value:Material.checked_material;contract_value:Contract.t;evidence_value:Json.t}
type result={report_value:Json.t;status_value:status;accepted_value:checked_evidence option;export_value:bool}
let report value=value.report_value
let status value=value.status_value
let accepted value=value.accepted_value
let export_permitted value=value.export_value
let material value=value.material_value
let contract value=value.contract_value
let evidence value=value.evidence_value
let combine statuses=if List.mem Incompatible statuses then Incompatible
  else if List.for_all((=)Supported)statuses then Supported else Unassessed

module Make(Charge:sig val charge:int->unit end)=struct
  module Meter=Bioc_checker.Policy_generation_meter.Make(Charge)
  module List=Meter.List
  module String=Meter.String
  let get key raw=Meter.Json.field key(Meter.Json.object_fields raw)
  let same=Meter.Json.equal
  let hash raw=Meter.preflight raw;Meter.Canonical.fingerprint raw
  let pins a b=same(Pin.to_json a)(Pin.to_json b)
  let applicability material=
    let raw=R.to_json(Material.request material)in Meter.preflight raw;
    let context=get "context" raw and original=get "implementation_request" raw in
    let providers=Meter.Json.array(get "providers" context)in
    obj["recipient_fingerprint",str(hash(get "recipient" context));
      "deployment_fingerprint",str(hash(get "deployment"(get "document" original)));
      "clock_fingerprint",str(hash(get "clock" context));
      "operating_domain_fingerprint",str(hash(get "operating_domain" original));
      "environment_fingerprints",Json.Array(List.filter_map(fun provider->
        let body=get "body" provider in
        if same(get "kind" body)(str "environment")then Some(str(hash body))else None)providers)]
  let interval raw (value:Contract.interval)=
    let quantity raw (value:Contract.quantity)=same(get "unit" raw)value.unit &&
      Q.equal(Bioc_domain.Policy_document.exact_decimal(Meter.Json.string(get "amount" raw)))value.amount in
    quantity(get "lower" raw)value.lower && quantity(get "upper" raw)value.upper
  let envelope (replicates:Contract.replicate list)=match replicates with []->None|first::rest->
    let low,high=List.fold_left(fun((low:Contract.quantity),(high:Contract.quantity))(row:Contract.replicate)->
      Charge.charge 1;
      (if Q.compare row.interval.lower.amount low.amount<0 then row.interval.lower else low),
      (if Q.compare row.interval.upper.amount high.amount>0 then row.interval.upper else high))
      (first.interval.lower,first.interval.upper)rest in
    Some(obj["lower",low.raw;"upper",high.raw])
  let execute material contract=
    let original=Material.request material in
    Meter.preflight(R.to_json original);Meter.preflight(Material.evidence material);
    Meter.preflight(Contract.to_json contract);
    let current=applicability material in
    let dossier=Contract.dossier contract in
    let protocols,datasets,analyses=match dossier with None->[],[],[]|Some value->
      value.protocols,value.datasets,value.analyses in
    let requirements=Contract.requirements contract in
    let global=ref []and global_states=ref []in
    List.iter(fun(value:Contract.dataset)->if not(List.exists(fun(r:Contract.requirement)->r.id=value.requirement)requirements)
      then (global:="dataset_without_declared_requirement"::!global;global_states:=Incompatible::!global_states))datasets;
    List.iter(fun(value:Contract.analysis)->if not(List.exists(fun(d:Contract.dataset)->pins d.identity value.dataset)datasets)
      then (global:="analysis_without_exact_dataset"::!global;global_states:=Unassessed::!global_states))analyses;
    let rows=List.map(fun(target:Contract.requirement)->
      let issues=ref []and states=ref []in
      let mark state reason=states:=state::!states;issues:=reason::!issues in
      let selected=R.network_quantitative original in
      (match selected with None->mark Unassessed "selected_mechanism_family_unassessed"|Some selection->
        let component=Rule.component(R.composition_rule original)(Rule.Instance selection.instance)in
        if target.instance<>selection.instance || not(pins target.component selection.component) ||
          not(pins target.component(Local.identity component)) then mark Incompatible "selected_component_identity_mismatch";
        if target.mechanism_fingerprint<>hash(NC.to_json selection.mechanism)then mark Incompatible "original_mechanism_identity_mismatch";
        (match List.find_opt(fun(edge:NC.transfer)->edge.id=target.transfer)selection.mechanism.transfers with
          |None->mark Incompatible "selected_parameter_absent"
          |Some edge->if not(same target.nominal.raw edge.amount.raw)then mark Incompatible "selected_nominal_parameter_mismatch");
        if not(same target.nominal.unit selection.mechanism.unit)then mark Incompatible "complete_parameter_unit_mismatch");
      if not(same target.applicability.raw current)then mark Incompatible "original_applicability_identity_mismatch";
      if not(same target.nominal.unit target.accepted.lower.unit) ||
        Q.compare target.nominal.amount target.accepted.lower.amount<0 || Q.compare target.nominal.amount target.accepted.upper.amount>0
        then mark Incompatible "nominal_outside_declared_criterion";
      let dataset=List.find_opt(fun(value:Contract.dataset)->value.requirement=target.id)datasets in
      let protocol,analysis,computed,count,origins=match dataset with
        |None->mark Unassessed "measurement_dataset_absent";None,None,None,0,[]
        |Some data->
          if not(same data.applicability.raw current)then mark Unassessed "measurement_environment_not_applicable";
          let protocol=List.find_opt(fun(value:Contract.protocol)->pins value.identity data.protocol)protocols in
          (match protocol,selected with
            |None,_->mark Unassessed "exact_measurement_protocol_absent"
            |Some protocol,Some selection->if not(same protocol.period.raw selection.mechanism.sample_period.raw)
              then mark Unassessed "measurement_sampling_period_not_applicable"
            |_->());
          let analysis=List.find_opt(fun(value:Contract.analysis)->pins value.dataset data.identity)analyses in
          let unit_ok=List.for_all(fun(row:Contract.replicate)->same row.interval.lower.unit target.nominal.unit)data.replicates in
          if not unit_ok then mark Incompatible "complete_measurement_unit_mismatch";
          let computed=if unit_ok then envelope data.replicates else None in
          (match analysis with None->mark Unassessed "independent_analysis_absent"|Some analysis->
            if analysis.replicate_ids<>List.map(fun(row:Contract.replicate)->row.id)data.replicates
              then mark Incompatible "analysis_replicate_inventory_mismatch";
            if not(match computed,analysis.envelope with None,None->true|Some raw,Some declared->interval raw declared|_->false)
              then mark Incompatible "independently_recomputed_envelope_mismatch");
          let count=List.length data.replicates in
          if count<target.minimum_replicates then mark Unassessed "insufficient_supplied_replicates";
          (* Only applicable measurements can contradict the scoped target.
             Unrelated environments do not become negative biological evidence. *)
          let applicable=same data.applicability.raw current && (match protocol,selected with
            |Some protocol,Some selection->same protocol.period.raw selection.mechanism.sample_period.raw|_->false)in
          if applicable && unit_ok then List.iter(fun(row:Contract.replicate)->
            if Q.compare row.interval.upper.amount target.accepted.lower.amount<0 ||
              Q.compare row.interval.lower.amount target.accepted.upper.amount>0 then mark Incompatible "measurement_disjoint_from_criterion"
            else if Q.compare row.interval.lower.amount target.accepted.lower.amount<0 ||
              Q.compare row.interval.upper.amount target.accepted.upper.amount>0 then mark Unassessed "measurement_overlaps_criterion_boundary")data.replicates;
          let origins=Contract.origin_name data.provenance.origin::
            (match protocol with None->[]|Some v->[Contract.origin_name v.provenance.origin])@
            (match analysis with None->[]|Some v->[Contract.origin_name v.provenance.origin])in
          protocol,analysis,computed,count,origins in
      let state=if !states=[]then Supported else combine !states in
      let optional encode=function None->Json.Null|Some value->encode value in
      state,obj["requirement",target.raw;"status",str(status_name state);
        "issues",Json.Array(List.map str(List.sort_uniq String.compare !issues));
        "protocol",optional(fun(value:Contract.protocol)->value.raw)protocol;
        "dataset",optional(fun(value:Contract.dataset)->value.raw)dataset;
        "analysis",optional(fun(value:Contract.analysis)->value.raw)analysis;
        "recomputed_envelope",(match computed with None->Json.Null|Some value->value);
        "replicates",Json.int count;"origins",Json.Array(List.map str(List.sort_uniq String.compare origins))])requirements in
    let statuses=List.map fst rows in
    let state=combine(statuses @ !global_states)in
    state,List.map snd rows,List.sort_uniq String.compare !global,current
end
let applicability material=
  let module Check=Make(struct let charge _=()end)in Check.applicability material
let check ?parent ?(maximum=max_work) ~material ~contract ()=
  Diagnostic.require(maximum>=0 && maximum<=max_work)"policy_realization_evidence_resource_limit"
    "Evidence work allowance exceeds its fixed ceiling.";
  let budget=match parent with None->W.create ~profile ~error_code:"policy_realization_evidence_resource_limit" ~maximum()
    |Some parent->W.nested ~parent ~profile ~error_code:"policy_realization_evidence_resource_limit" ~maximum()in
  let before=W.remaining budget in
  let module Check=Make(struct let charge=W.charge budget end)in
  let status_value,rows,issues,applicability=Check.execute material contract in
  let export_value=not(Contract.require_compatibility contract)||status_value=Supported in
  let fields=["schema_version",str schema_version;"profile",str profile;"implementation",str implementation_version;
    "status",str(status_name status_value);"claim_scope",str "supplied_parameter_interval_compatibility";
    "request_fingerprint",str(Check.hash(R.to_json(Material.request material)));
    "material_assessment_fingerprint",str(Check.hash(Material.evidence material));
    "contract_fingerprint",str(Check.hash(Contract.to_json contract));"applicability",applicability;
    "require_compatibility",Json.Bool(Contract.require_compatibility contract);"export_permitted",Json.Bool export_value;
    "requirements",Json.Array rows;"issues",Json.Array(List.map str issues);
    "empirical",str "unassessed";"authenticity",str "unassessed";"artifact_contents",str "unassessed";
    "statistical_coverage",str "not_inferred";"formal_prerequisites_discharged",Json.Array[]]in
  let usage amount=obj["unit",str "logical_data_visits_and_exact_interval_work";"charged_work",Json.int amount]in
  let reserved=obj(fields@["usage",usage maximum])in
  Check.Meter.preflight reserved;Check.Meter.serialization reserved;
  let output=W.create_output ~profile ~error_code:"policy_realization_evidence_publication_limit" ~max_bytes:2097152 ~max_nodes:65536()in
  W.reserve_json output reserved;
  let report_value=obj(fields@["usage",usage(before-W.remaining budget)])in
  Diagnostic.require(not(W.exhausted budget))"policy_realization_evidence_resource_limit""Evidence work was exhausted.";
  let accepted_value=if status_value=Supported then Some{material_value=material;contract_value=contract;evidence_value=report_value}else None in
  {report_value;status_value;accepted_value;export_value}
