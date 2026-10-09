open Bioc_wire
module N = Bioc_domain.Policy_refinement
module R = Bioc_domain.Policy_realization_request
module D = Bioc_domain.Policy_document
module F = Bioc_domain.Policy_operating_domain
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module L = Bioc_domain.Policy_component_library
module Rule = Bioc_domain.Policy_component_assembly_rule
module M = Bioc_domain.Policy_component_material_request
module X = Bioc_domain.Policy_component_context
module K = Bioc_domain.Construction_content
module PM = Bioc_domain.Policy_mrna_structure
module RA = Bioc_checker.Policy_realization_admission
module B = Bioc_checker.Policy_implementation_binding_check
module St = Bioc_checker.Policy_mrna_structure_check
module P = Policy_preservation_check
module A = Policy_component_assembly_check
module C = Policy_component_context_check
module Material = Policy_component_material_check
module W = Bioc_checker.Work_budget

let resource_profile = "biocompiler.policy_refinement_resources.v0.1"
let max_work = 128 * 1024 * 1024
let max_claims = 32
let max_premises = 32
let max_inputs = 16
let max_depth = 32
let max_evidence_bytes = 256 * 1024
let max_evidence_nodes = 16384

(* Neither this record nor a constructor from serialized evidence is exposed.
   Cached JSON and its digest are immutable summaries owned by this capability.
   No saved report, domain claim record or caller-supplied fingerprint mints it. *)
type t = {
  claims_value:N.claim list;
  premises_value:N.premise list;
  scope_value:N.scope;
  depth_value:int;
  raw:Json.t;
  digest:string;
}
let to_json value = value.raw
let fingerprint value = value.digest
let claims value = value.claims_value
let premises value = value.premises_value
let scope value = value.scope_value

module Make (Charge:sig val charge:int -> unit end) = struct
  module Meter = Bioc_checker.Policy_generation_meter.Make(Charge)
  module List = Meter.List
  module String = Meter.String
  let require condition message =
    Diagnostic.require condition "policy_refinement_identity" message
  let get key value = Meter.Json.field key (Meter.Json.object_fields value)
  let bounded raw =
    let output=W.create_output ~profile:resource_profile
      ~error_code:"policy_refinement_resource_limit"
      ~max_bytes:Limits.max_response_bytes ~max_nodes:Limits.max_json_nodes () in
    Meter.preflight raw; W.reserve_json output raw
  let hash raw = bounded raw; Meter.Canonical.fingerprint raw
  let endpoint stage raw : N.endpoint = {stage;fingerprint=hash raw}
  let premise kind fingerprint : N.premise = {kind;fingerprint}
  let claim relation source target scope : N.claim = {relation;source;target;scope}
  let same_string left right = String.equal left right
  let merge_optional left right = match left,right with
    | None,value | value,None -> value
    | Some left,Some right ->
      require (same_string left right) "Refinement evidence has conflicting nonempty scope identities.";
      Some left
  let merge_scope (left:N.scope) (right:N.scope) =
    require (same_string left.implementation_request_fingerprint right.implementation_request_fingerprint &&
      same_string left.operating_domain_fingerprint right.operating_domain_fingerprint)
      "Refinement evidence belongs to different original requests or operating domains.";
    {left with limits_fingerprint=merge_optional left.limits_fingerprint right.limits_fingerprint;
      material_request_fingerprint=merge_optional left.material_request_fingerprint right.material_request_fingerprint}
  let bounded_inputs values =
    let rec walk count = function
      | [] -> ()
      | _::rest ->
        Charge.charge 1;
        Diagnostic.require (count<max_inputs) "policy_refinement_resource_limit"
          "A refinement derivation exceeds its bounded input count.";
        walk (count+1) rest in
    walk 0 values;
    require (values<>[]) "A refinement conjunction needs at least one checked premise."
  let merge_claims values =
    List.fold_left (fun acc (item:N.claim) ->
      let expected_source,expected_target=N.stages item.relation in
      require (item.source.stage=expected_source && item.target.stage=expected_target)
        "A named refinement relation has incompatible endpoint stages.";
      List.iter (fun (previous:N.claim) ->
        List.iter (fun (first:N.endpoint) ->
          List.iter (fun (second:N.endpoint) ->
            if first.stage=second.stage then
              require (same_string first.fingerprint second.fingerprint)
                "Refinement composition would splice different artifacts at the same stage.")
            [previous.source;previous.target]) [item.source;item.target]) acc;
      match List.find_opt (fun (previous:N.claim)->previous.relation=item.relation) acc with
      | Some previous ->
        require (Meter.Json.equal (N.claim_to_json previous) (N.claim_to_json item))
          "A named relation has conflicting endpoint or scope evidence.";
        acc
      | None ->
        Diagnostic.require (List.length acc<max_claims) "policy_refinement_resource_limit"
          "Refinement claim inventory exceeds its closed bound.";
        item::acc) [] values
    |> List.sort (fun (left:N.claim) (right:N.claim)->compare left.relation right.relation)
  let merge_premises values =
    List.fold_left (fun acc (item:N.premise) ->
      match List.find_opt (fun (previous:N.premise)->previous.kind=item.kind) acc with
      | Some previous ->
        require (same_string previous.fingerprint item.fingerprint)
          "Refinement composition would replace an original authority or checked premise.";
        acc
      | None ->
        Diagnostic.require (List.length acc<max_premises) "policy_refinement_resource_limit"
          "Refinement premise inventory exceeds its closed bound.";
        item::acc) [] values
    |> List.sort (fun (left:N.premise) (right:N.premise)->compare left.kind right.kind)
  let make ~rule ~inputs ~scope ~claims ~premises =
    let depth=1+List.fold_left (fun largest input->max largest input.depth_value) 0 inputs in
    Diagnostic.require (depth<=max_depth) "policy_refinement_resource_limit"
      "Refinement derivation depth exceeds its explicit bound.";
    let claims_value=merge_claims claims and premises_value=merge_premises premises in
    let raw=Json.Object [
      "schema_version",Json.String N.schema_version;
      "claims",Json.Array(List.map N.claim_to_json claims_value);
      "premises",Json.Array(List.map N.premise_to_json premises_value);
      "derivation",Json.Object ["rule",Json.String(N.rule_name rule);
        "inputs",Json.Array(List.map (fun input->Json.String input.digest) inputs)]] in
    let output=W.create_output ~profile:resource_profile ~error_code:"policy_refinement_resource_limit"
      ~max_bytes:max_evidence_bytes ~max_nodes:max_evidence_nodes () in
    Meter.preflight raw; W.reserve_json output raw;
    let digest=Meter.Canonical.fingerprint raw in
    {claims_value;premises_value;scope_value=scope;depth_value=depth;raw;digest}
  let conjoin values =
    bounded_inputs values;
    let first=List.hd values in
    let scope=List.fold_left (fun accumulated value->merge_scope accumulated value.scope_value)
      first.scope_value (List.tl values) in
    make ~rule:N.Conjunction ~inputs:values ~scope
      ~claims:(List.concat_map (fun value->value.claims_value) values)
      ~premises:(List.concat_map (fun value->value.premises_value) values)
  let compose left right =
    let scope=merge_scope left.scope_value right.scope_value in
    (* Only these three directional entailments exist. In particular, exact
       wiring or exact material alone cannot yield behavioral preservation. *)
    let permitted first second = match first,second with
      | N.Exact_source_occurrence,N.Source_graph_binding ->
        Some(N.Exact_source_graph_correspondence,N.Source_graph_chain)
      | N.Exact_source_occurrence,N.Bounded_observable_correspondence ->
        Some(N.Bounded_source_observable_correspondence,N.Source_behavior_chain)
      | N.Bounded_source_observable_correspondence,N.Supplied_component_material_correspondence ->
        Some(N.Conditional_source_material_correspondence,N.Source_material_chain)
      | _ -> None in
    let alternatives=List.concat_map (fun (first:N.claim) ->
      List.filter_map (fun (second:N.claim) ->
        match permitted first.relation second.relation with
        | None -> None
        | Some(relation,rule) ->
          require (first.target.stage=second.source.stage &&
            same_string first.target.fingerprint second.source.fingerprint)
            "Refinement chain endpoints do not identify the same complete artifact.";
          Some(claim relation first.source second.target scope,rule))
        right.claims_value) left.claims_value in
    let derived,rule=match alternatives with
      | [one] -> one
      | _ -> Diagnostic.fail "policy_refinement_composition"
        "No unique closed refinement composition rule applies to these checked relations." in
    make ~rule ~inputs:[left;right] ~scope
      ~claims:(derived::List.append left.claims_value right.claims_value)
      ~premises:(List.append left.premises_value right.premises_value)
  let admitted_parts admitted =
    let request=RA.request admitted in
    let source=endpoint N.Source_document (D.to_json(R.document request))
    and behavior=endpoint N.Operational_behavior (O.behavior_to_json(RA.behavior admitted)) in
    let domain=hash(F.to_json(R.operating_domain request)) in
    let scope:N.scope={
      implementation_request_fingerprint=hash(R.to_json request);
      operating_domain_fingerprint=domain;limits_fingerprint=None;material_request_fingerprint=None} in
    let report=RA.report admitted in
    let premises=[
      premise N.Original_source source.fingerprint;
      premise N.Semantic_definitions (hash(O.descriptors_to_json(R.definitions request)));
      premise N.Operating_domain domain;
      premise N.Implementation_catalog (Json.string(get "implementation_catalog_digest" report));
      premise N.Implementation_models (hash(I.library_to_json(R.implementation_library request)));
      premise N.Source_admission (hash report)] in
    source,behavior,scope,premises
  let binding_parts checked =
    let source,behavior,scope,premises=admitted_parts(B.admitted_inputs checked) in
    let graph=endpoint N.Implementation_graph (I.to_json(B.implementation checked)) in
    source,behavior,graph,scope,List.append premises [premise N.Implementation_binding (hash(B.report checked))]
  let preservation_parts checked =
    let source,behavior,graph,scope,premises=binding_parts(P.binding checked) in
    let report=P.evidence checked in
    let limits=hash(get "limits" report) in
    source,behavior,graph,{scope with limits_fingerprint=Some limits},
      List.append premises [premise N.Checker_limits limits;premise N.Bounded_preservation(hash report)]
  let assembly_parts checked =
    let source,behavior,graph,scope,premises=preservation_parts(A.implementation checked) in
    let structure=A.structure checked in
    let content=endpoint N.Construction_content (K.to_json(St.content structure)) in
    source,behavior,graph,content,scope,List.append premises [
      premise N.Component_library (hash(L.to_json(A.components checked)));
      premise N.Composition_rule (hash(Rule.to_json(A.rule checked)));
      premise N.Material_authority (hash(PM.to_json(St.authority structure)));
      premise N.Component_assembly (hash(A.evidence checked));
      premise N.Mrna_structure (hash(St.evidence structure))]
  let context_parts checked =
    let source,behavior,graph,content,scope,premises=assembly_parts(C.assembly checked) in
    let context=endpoint N.Deployment_context (X.to_json(C.context checked)) in
    let request=hash(M.to_json(C.request checked)) in
    source,behavior,graph,content,context,{scope with material_request_fingerprint=Some request},
      List.append premises [premise N.Deployment_context_contract context.fingerprint;
        premise N.Material_request request;premise N.Component_context(hash(C.evidence checked))]
  let of_admission admitted =
    let source,behavior,scope,premises=admitted_parts admitted in
    make ~rule:N.Checked_admission ~inputs:[] ~scope
      ~claims:[claim N.Exact_source_occurrence source behavior scope] ~premises
  let of_binding checked =
    let _,behavior,graph,scope,premises=binding_parts checked in
    make ~rule:N.Checked_binding ~inputs:[] ~scope
      ~claims:[claim N.Source_graph_binding behavior graph scope] ~premises
  let of_preservation checked =
    let _,behavior,graph,scope,premises=preservation_parts checked in
    make ~rule:N.Checked_preservation ~inputs:[] ~scope
      ~claims:[claim N.Bounded_observable_correspondence behavior graph scope;
        claim N.Original_hard_requirements behavior graph scope] ~premises
  let of_assembly checked =
    let _,_,graph,content,scope,premises=assembly_parts checked in
    make ~rule:N.Checked_assembly ~inputs:[] ~scope
      ~claims:[claim N.Supplied_component_material_correspondence graph content scope] ~premises
  let of_context checked =
    let _,_,_,content,context,scope,premises=context_parts checked in
    make ~rule:N.Checked_context ~inputs:[] ~scope
      ~claims:[claim N.Conditional_deployment_context content context scope] ~premises
  let of_material checked =
    let context=Material.context checked in
    let assembly=C.assembly context in
    let preservation=A.implementation assembly in
    let binding=P.binding preservation in
    let source=of_admission(B.admitted_inputs binding) in
    let exact=compose source (of_binding binding) in
    let bounded=compose exact (of_preservation preservation) in
    let material=conjoin [of_assembly assembly;of_context context] in
    let linked=compose bounded material in
    let original,_,_,content,_,scope,premises=context_parts context in
    let final=make ~rule:N.Checked_material ~inputs:[] ~scope
      ~claims:[claim N.Complete_original_obligations original content scope]
      ~premises:(List.append premises [premise N.Complete_material_check(hash(Material.evidence checked))]) in
    conjoin [linked;final]
end

let budget maximum =
  Diagnostic.require (maximum>=0 && maximum<=max_work) "policy_refinement_resource_limit"
    "Refinement construction allowance is outside the fixed resource profile.";
  W.create ~profile:resource_profile ~error_code:"policy_refinement_resource_limit" ~maximum ()
let of_admission ?(maximum=max_work) checked =
  let budget=budget maximum in
  let module Builder=Make(struct let charge=W.charge budget end) in Builder.of_admission checked
let of_binding ?(maximum=max_work) checked =
  let budget=budget maximum in
  let module Builder=Make(struct let charge=W.charge budget end) in Builder.of_binding checked
let of_preservation ?(maximum=max_work) checked =
  let budget=budget maximum in
  let module Builder=Make(struct let charge=W.charge budget end) in Builder.of_preservation checked
let of_assembly ?(maximum=max_work) checked =
  let budget=budget maximum in
  let module Builder=Make(struct let charge=W.charge budget end) in Builder.of_assembly checked
let of_context ?(maximum=max_work) checked =
  let budget=budget maximum in
  let module Builder=Make(struct let charge=W.charge budget end) in Builder.of_context checked
let of_material ?(maximum=max_work) checked =
  let budget=budget maximum in
  let module Builder=Make(struct let charge=W.charge budget end) in Builder.of_material checked
let conjoin ?(maximum=max_work) values =
  let budget=budget maximum in
  let module Builder=Make(struct let charge=W.charge budget end) in Builder.conjoin values
let compose ?(maximum=max_work) left right =
  let budget=budget maximum in
  let module Builder=Make(struct let charge=W.charge budget end) in Builder.compose left right
