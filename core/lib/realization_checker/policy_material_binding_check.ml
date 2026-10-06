open Bioc_wire
module C = Bioc_domain.Policy_material_contract
module K = Bioc_domain.Construction_content
module E = Bioc_domain.Construction_assessment
module P = Policy_preservation_check
module S = Bioc_checker.Policy_mrna_structure_check
module I = Bioc_domain.Policy_implementation
module B = Bioc_checker.Policy_implementation_binding_check
module A = Bioc_checker.Policy_realization_admission
module R = Bioc_domain.Policy_realization_request
module N = Bioc_domain.Molecule
module G = Bioc_domain.Molecule_coordinates
module M = Bioc_domain.Molecular_record
module PM = Bioc_domain.Policy_mrna_structure
module Pin = Bioc_domain.Pinned_identity
module W = Bioc_checker.Work_budget
let implementation_version="biocompiler.ocaml.policy_material_binding_check.v0.1"
let max_work=100000000
let str value=Json.String value
let obj values=Json.Object values
let arr values=Json.Array values
type checked_material_binding={contract_value:C.t;implementation_value:P.checked_implementation;
  structure_value:S.checked_structure;evidence_value:Json.t}
type result={outcome_value:E.outcome;report_value:Json.t;accepted_value:checked_material_binding option}
let outcome(value:result)=value.outcome_value
let report(value:result)=value.report_value
let accepted(value:result)=value.accepted_value
let contract(value:checked_material_binding)=value.contract_value
let implementation(value:checked_material_binding)=value.implementation_value
let structure(value:checked_material_binding)=value.structure_value
let evidence(value:checked_material_binding)=value.evidence_value
let check ?parent ?(maximum=max_work) ~contract ~implementation ~proposed ~candidate ()=
  Diagnostic.require(maximum>=0 && maximum<=max_work)"policy_material_binding_resource_limit""Material checker work exceeds its fixed ceiling.";
  let budget=match parent with
    |None->W.create ~profile:C.profile ~error_code:"policy_material_binding_resource_limit" ~maximum ()
    |Some parent->W.nested ~parent ~profile:C.profile ~error_code:"policy_material_binding_resource_limit" ~maximum ()in
  let charge amount=W.charge budget amount in charge 1;
  let equal a b=
    M.check_resources a;M.check_resources b;
    let a=Canonical.encode a and b=Canonical.encode b in charge(String.length a+String.length b);a=b in
  let checked_source=P.binding implementation in
  let actual=B.implementation checked_source in
  let original_request=A.request(B.admitted_inputs checked_source)in
  let contract_raw=C.to_json contract and proposed_raw=C.proposal_to_json proposed in
  M.check_resources contract_raw;M.check_resources proposed_raw;
  charge(String.length(Canonical.encode contract_raw)+String.length(Canonical.encode proposed_raw));
  let contract=C.of_json ~library:(R.implementation_library original_request)contract_raw in
  let proposed=C.proposal_of_json proposed_raw in
  let structure_result=S.check ~parent:budget ~authority:(C.structure_authority contract) ~candidate ()in
  let findings=ref []in
  let verify condition code=charge 1;if not condition then(
    Diagnostic.require(List.length !findings<4096)"policy_material_binding_resource_limit""Material finding inventory exceeds its bound.";
    findings:=code:: !findings)in
  verify(C.phase_profile=Bioc_candidate_runtime.Policy_primitives.profile)"fixed_primitive_execution_phases";
  verify(C.proposed_contract proposed=C.fingerprint contract)"original_material_contract_pin";
  let kernel=C.kernel contract and bindings=C.node_bindings proposed in
  let local_nodes=C.nodes kernel and actual_nodes=I.nodes actual in
  verify(C.library_digest contract=(I.authority actual).library_digest)"original_model_library";
  let actual_layout=I.slot_layout actual in
  verify(C.layout_id kernel=actual_layout.layout_id && C.slots kernel=actual_layout.slots)"complete_slot_layout";
  verify(List.map(fun(value:C.node_binding)->value.local_id)bindings=
    List.map(fun(value:C.local_node)->value.local_id)local_nodes)"ordered_total_local_node_bijection";
  verify(List.map(fun(value:C.node_binding)->value.node_id)bindings=
    List.map(fun(value:I.node)->value.node_id)actual_nodes)"ordered_total_actual_node_bijection";
  let rename id=match List.find_opt(fun(value:C.node_binding)->value.local_id=id)bindings with
    |Some value->value.node_id|None->""in
  let endpoint(value:I.endpoint) : I.endpoint={node_id=rename value.node_id;port_id=value.port_id}in
  List.iter(fun(local:C.local_node)->charge 1;
    match List.find_opt(fun(value:I.node)->value.node_id=rename local.local_id)actual_nodes with
    |None->verify false("unbound_primitive:"^local.local_id)
    |Some actual->
      verify(equal(Pin.to_json local.model.identity)(Pin.to_json actual.model.identity))("primitive_identity:"^local.local_id);
      verify(local.model.configuration_digest=actual.model.configuration_digest)("configuration_identity:"^local.local_id);
      verify(equal(I.model_body_to_json local.model)(I.model_body_to_json actual.model))("complete_primitive_configuration_replication:"^local.local_id))local_nodes;
  let renamed_wires=List.map(fun(value:I.wire)->charge 1;
    ({producer=endpoint value.producer;consumer=endpoint value.consumer}:I.wire))(C.wires kernel)in
  verify(renamed_wires=I.wires actual)"complete_ordered_wiring";
  let renamed_inputs=List.map(fun(value:I.external_input)->charge 1;
    ({input_id=value.input_id;input_kind=value.input_kind;consumer=endpoint value.consumer}:I.external_input))(C.inputs kernel)in
  verify(renamed_inputs=I.inputs actual)"complete_ordered_external_inputs";
  let renamed_groups=List.map(fun(value:I.atomic_group)->charge 1;
    ({group_id=value.group_id;arbiter=rename value.arbiter;commits=List.map rename value.commits}:I.atomic_group))(C.atomic_groups kernel)in
  verify(renamed_groups=I.atomic_groups actual)"complete_ordered_atomic_groups";
  verify(List.map endpoint(C.semantic_exports kernel)=I.semantic_exports actual)"complete_ordered_semantic_exports";
  let targets=C.target_inventory kernel in charge(List.length targets);
  verify(List.map(fun(value:C.carrier)->value.target)(C.carriers contract)=targets)"exhaustive_ordered_material_dispositions";
  let authority=C.structure_authority contract in
  (* Initial material profile has exactly one independently specified RNA and
     one product. Counts in the original source still require context checking. *)
  verify(List.length(PM.member_order authority)=1)"single_rna_material_profile";
  verify(List.map N.id(C.material_key contract)=PM.member_order authority)"material_key_member_order";
  (match S.checked_structure structure_result with
   |None->()
   |Some checked->
      let content=S.content checked in
      (match K.inventory content with
       |None->verify false "fresh_material_inventory_absent"
       |Some inventory->
          verify(equal(arr(List.map N.to_json(C.material_key contract)))
            (arr(List.map N.to_json(K.Inventory.molecules inventory))))"complete_exact_material_case_evaluation";
          List.iter(fun(carrier:C.carrier)->List.iter(fun(site:C.material_site)->
            charge 1;
            match List.find_opt(fun molecule->N.id molecule=site.member)(K.Inventory.molecules inventory)with
            |None->verify false("carrier_member:"^site.member)
            |Some molecule->
              match List.find_opt(fun feature->N.Feature.id feature=site.feature)(N.features molecule)with
              |None->verify false("carrier_feature:"^site.member^"/"^site.feature)
              |Some feature->
                (match N.Feature.path feature with
                 |None->verify false "carrier_feature_has_no_material_path"
                 |Some path->verify(equal(G.Path.to_json path)(G.Path.to_json site.path))"carrier_exact_feature_path");
                verify(G.Path.length site.path>0)"carrier_nonempty_material_path";
                (match G.Path.validate_for site.path(N.space molecule)with ()->()
                 |exception Diagnostic.Error _->verify false "carrier_path_outside_actual_member"))carrier.sites)(C.carriers contract)));
  let expected_products=List.filter_map(fun(node:C.local_node)->match node.model.primitive with
    |I.Product_constant symbol->Some(node.local_id,symbol)|_->None)local_nodes in
  verify(List.map(fun(value:C.product_binding)->value.node,value.symbol)(C.products contract)=expected_products)
    "complete_product_symbol_bindings";
  verify(expected_products<>[])"material_product_required";
  List.iter(fun(value:C.product_binding)->match List.find_opt(fun(member:PM.member)->member.id=value.member)(PM.members authority)with
    |None->verify false "encoded_product_member_absent"
    |Some member->verify(equal(Pin.to_json value.product)(Pin.to_json member.product.identity))"complete_encoded_product_identity")
    (C.products contract);
  let resources=C.resources contract in
  verify(List.map(fun(value:C.allocation)->value.demand_id)(C.allocations contract)=
    List.map(fun(value:C.resource_demand)->value.demand_id)resources)"exclusive_complete_resource_allocation_inventory";
  List.iter(fun(value:C.resource_demand)->verify(match value.owner with
    |C.Node id->List.exists(fun(node:C.local_node)->node.local_id=id)local_nodes
    |C.Input id->List.exists(fun(input:I.external_input)->input.input_id=id)(C.inputs kernel)
    |C.Layout->true)"resource_owner_absent")resources;
  verify(List.map(fun(value:C.input_witness)->value.input_id)(C.input_witnesses contract)=
    List.map(fun(value:I.external_input)->value.input_id)(C.inputs kernel))"complete_input_provider_witness_inventory";
  let findings=List.rev !findings in
  let outcome_value=if findings<>[]then E.Fail else S.outcome structure_result in
  let report_value=obj["schema_version",str "biocompiler.policy_material_binding_assessment.v0.1";
    "checker_version",str implementation_version;"profile",str C.profile;
    "contract_fingerprint",str(C.fingerprint contract);"implementation_fingerprint",str(I.fingerprint actual);
    "proposed_fingerprint",str(Canonical.fingerprint(C.proposal_to_json proposed));"candidate_fingerprint",str(K.fingerprint candidate);
    "outcome",str(E.outcome_name outcome_value);"diagnostics",arr(List.map str findings);
    "claim_scope",str "exact_supplied_whole_graph_material_case";
    "premise",str "supplied_conditional_model_to_sequence_contract";
    "structure",S.report structure_result;"preservation_evidence_fingerprint",str(Canonical.fingerprint(P.evidence implementation));
    "context",str "unassessed";"resource_capacity",str "unassessed";"input_compatibility",str "unassessed";
    "source_obligation_discharge",str "unassessed";"empirical",str "unassessed";"artifact",str "withheld";"export",str "withheld"]in
  M.check_resources report_value;charge(String.length(Canonical.encode report_value));
  let accepted_value=match outcome_value,S.checked_structure structure_result with
    |E.Pass,Some structure_value->Some{contract_value=contract;implementation_value=implementation;
      structure_value;evidence_value=report_value}
    |_->None in
  {outcome_value;report_value;accepted_value}
