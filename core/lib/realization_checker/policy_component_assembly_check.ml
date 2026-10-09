open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module L = Bioc_domain.Policy_component_library
module A = Bioc_domain.Policy_component_assembly_rule
module Q = Bioc_domain.Policy_component_assembly_proposal
module P = Policy_preservation_check
module K = Bioc_domain.Construction_content
module E = Bioc_domain.Construction_assessment
module S = Bioc_checker.Policy_mrna_structure_check
module B = Bioc_checker.Policy_implementation_binding_check
module RA = Bioc_checker.Policy_realization_admission
module I = Bioc_domain.Policy_implementation
module C = Bioc_domain.Policy_component_material
module F = Bioc_domain.Policy_component_fragment
module CT = Bioc_domain.Construction
module PT = Bioc_domain.Payload_template
module PM = Bioc_domain.Policy_mrna_structure
module HM = Bioc_domain.Policy_helper_material
module MT = Bioc_domain.Molecular_transition
module N = Bioc_domain.Molecule
module G = Bioc_domain.Molecule_coordinates
module H = Bioc_domain.Molecule_chemistry
module M = Bioc_domain.Molecular_record
module Pin = Bioc_domain.Pinned_identity
module W = Bioc_checker.Work_budget
let implementation_version = "biocompiler.ocaml.policy_component_assembly_check.v0.1"
let instance_implementation_version = "biocompiler.ocaml.policy_component_assembly_check.v0.2"
let multi_member_implementation_version = "biocompiler.ocaml.policy_component_assembly_check.v0.3"
let grounded_helper_implementation_version = "biocompiler.ocaml.policy_component_assembly_check.v0.4"
let max_work = 100000000
let str value = Json.String value
let obj values = Json.Object values
let arr values = Json.Array values
let slot_name = A.slot_name
let link_name = A.link_name
let replace key replacement raw = obj (List.map (fun (name,value) ->
  name,(if name=key then replacement else value)) (Json.object_fields raw))
let project_path ~offset ~space path =
  let spans = List.map (fun span -> G.Span.to_json span
    |> replace "start" (Json.int (G.Span.start span+offset))
    |> replace "end" (Json.int (G.Span.stop span+offset))) (G.Path.spans path) in
  G.Path.to_json path |> replace "space_id" (str space) |> replace "spans" (arr spans)
let project_feature ~offset ~space feature =
  match N.Feature.path feature with
  | None -> None
  | Some path -> Some (N.Feature.to_json feature |> replace "path" (project_path ~offset ~space path))
type checked_assembly = { original_value:R.t; components_value:L.t; rule_value:A.t;
  implementation_value:P.checked_implementation; structure_value:S.checked_structure; evidence_value:Json.t }
type result = { outcome_value:E.outcome; report_value:Json.t; accepted_value:checked_assembly option }
let outcome (value:result) = value.outcome_value
let report (value:result) = value.report_value
let accepted (value:result) = value.accepted_value
let original (value:checked_assembly) = value.original_value
let components (value:checked_assembly) = value.components_value
let rule (value:checked_assembly) = value.rule_value
let implementation (value:checked_assembly) = value.implementation_value
let structure (value:checked_assembly) = value.structure_value
let evidence (value:checked_assembly) = value.evidence_value
let check ?parent ?(maximum=max_work) ~original ~components ~rule ~implementation ~proposed ~candidate () =
  Diagnostic.require (maximum>=0 && maximum<=max_work) "policy_component_assembly_resource_limit"
    "Assembly checker work exceeds its fixed ceiling.";
  let instanced = A.is_instanced rule in
  let multi_member = A.is_multi_member rule in
  let grounded_helper = A.is_grounded_helper rule in
  let profile = if grounded_helper then A.grounded_helper_profile else if multi_member then A.multi_member_profile else if instanced then A.instance_profile else A.profile in
  let budget = match parent with
    | None -> W.create ~profile ~error_code:"policy_component_assembly_resource_limit" ~maximum ()
    | Some parent -> W.nested ~parent ~profile ~error_code:"policy_component_assembly_resource_limit" ~maximum () in
  let charge amount = W.charge budget amount in charge 1;
  let encoded raw = M.check_resources raw; let bytes = Canonical.encode raw in charge (String.length bytes); bytes in
  let equal left right = encoded left = encoded right in
  let find predicate values = charge (List.length values); List.find_opt predicate values in
  let findings = ref [] in
  let verify condition code = charge 1; if not condition then (
    Diagnostic.require (List.length !findings<4096) "policy_component_assembly_resource_limit"
      "Assembly finding inventory exceeds its bound.";
    findings := code :: !findings) in
  let original_raw = R.to_json original and library_raw = L.to_json components
  and rule_raw = A.to_json rule and proposal_raw = Q.to_json proposed in
  List.iter (fun raw -> ignore (encoded raw)) [original_raw;library_raw;rule_raw;proposal_raw];
  let original = (if R.is_finite_machine original then R.of_finite_machine_json
    else if R.is_multi_product original then R.of_multi_product_json
    else if R.is_two_observation original then R.of_two_observation_json
    else if R.requires_prerequisite_closure original then R.of_prerequisite_json
    else R.of_json) original_raw in
  let checked_binding = P.binding implementation in
  let actual = B.implementation checked_binding in
  let bound_original = RA.request (B.admitted_inputs checked_binding) in
  verify (equal original_raw (R.to_json bound_original)) "unchanged_original_realization_request";
  (* Fresh membership checks use the untouched original model library. No new
     source-bearing implementation or replacement v1 material request exists. *)
  let components = L.of_json ~library:(R.implementation_library original) library_raw in
  let rule = A.of_json ~components rule_raw and proposed = Q.of_json proposal_raw in
  if instanced || Q.is_instanced proposed then
    verify (instanced=Q.is_instanced proposed) "instance_proposal_profile";
  if multi_member || Q.is_multi_member proposed || R.is_multi_product original then (
    verify (multi_member=Q.is_multi_member proposed) "multi_member_proposal_profile";
    verify (multi_member=R.is_multi_product original) "multi_member_original_source_profile");
  if grounded_helper || Q.is_grounded_helper proposed then
    verify (grounded_helper=Q.is_grounded_helper proposed) "grounded_helper_proposal_profile";
  if R.is_finite_machine original then
    verify (instanced && A.is_staged rule && not multi_member && not grounded_helper)
      "finite_machine_named_single_member_assembly";
  verify (equal (Pin.to_json (Q.rule proposed)) (Pin.to_json (A.identity rule))) "original_assembly_rule_pin";
  verify (A.model_library_digest rule = (I.authority actual).library_digest) "original_model_library";
  verify (A.component_library_digest rule = L.fingerprint components) "original_component_library";
  verify ((if A.is_staged rule then F.staged_phase_profile else F.phase_profile) =
    Bioc_candidate_runtime.Policy_primitives.execution_profile actual &&
    I.implementation_profile actual=(if A.is_staged rule then I.staged_profile else I.profile))
    "fixed_primitive_execution_phases";
  let bindings = Q.nodes proposed and actual_nodes = I.nodes actual in
  verify (List.map (fun (row:Q.node_binding) -> row.slot,row.node_id) bindings =
    List.map (fun (row:A.node_ref) -> row.slot,row.node_id) (A.node_order rule)) "ordered_total_local_node_bijection";
  verify (List.map (fun (row:Q.node_binding) -> row.actual_id) bindings =
    List.map (fun (node:I.node) -> node.node_id) actual_nodes) "ordered_total_actual_node_bijection";
  let rename slot node = match find (fun (row:Q.node_binding) -> row.slot=slot && row.node_id=node) bindings with
    | None -> "" | Some row -> row.actual_id in
  let fragment slot = C.fragment (A.component rule slot) in
  let endpoint slot (value:I.endpoint) : I.endpoint = {node_id=rename slot value.node_id;port_id=value.port_id} in
  let boundary (reference:A.boundary_ref) =
    List.find (fun (port:F.boundary_port) -> port.boundary_id=reference.boundary_id) (F.boundary_ports (fragment reference.slot)) in
  let boundary_endpoint (reference:A.boundary_ref) = endpoint reference.slot (boundary reference).endpoint in
  let layout = A.layout rule and actual_layout = I.slot_layout actual in
  verify (layout.layout_id=actual_layout.layout_id && layout.slots=actual_layout.slots) "complete_slot_layout";
  List.iter (fun (reference:A.node_ref) ->
    let local = List.find (fun (node:F.node) -> node.node_id=reference.node_id) (F.nodes (fragment reference.slot)) in
    let label = slot_name reference.slot ^ "/" ^ reference.node_id in
    match find (fun (node:I.node) -> node.node_id=rename reference.slot reference.node_id) actual_nodes with
    | None -> verify false ("unbound_primitive:" ^ label)
    | Some actual ->
      verify (equal (Pin.to_json local.model.identity) (Pin.to_json actual.model.identity)) ("primitive_identity:" ^ label);
      verify (local.model.configuration_digest=actual.model.configuration_digest) ("configuration_identity:" ^ label);
      verify (equal (I.model_body_to_json local.model) (I.model_body_to_json actual.model))
        ("complete_primitive_configuration_replication:" ^ label)) (A.node_order rule);
  let wires = List.map (function
    | A.Local_wire {slot;index} -> let wire = List.nth (F.wires (fragment slot)) index in
      ({producer=endpoint slot wire.producer;consumer=endpoint slot wire.consumer}:I.wire)
    | A.Cross_link kind -> let link = List.find (fun (row:A.link) -> row.kind=kind) (A.links rule) in
      ({producer=boundary_endpoint link.producer;consumer=boundary_endpoint link.consumer}:I.wire)) (A.wire_order rule) in
  charge (List.length wires); verify (wires=I.wires actual) "complete_ordered_wiring";
  let inputs = List.map (fun (row:A.input_ref) ->
    let slot = List.find (fun (value:F.external_slot) -> value.slot_id=row.external_slot) (F.external_slots (fragment row.slot)) in
    ({input_id=row.input_id;input_kind=slot.input_kind;consumer=endpoint row.slot slot.consumer}:I.external_input)) (A.input_order rule) in
  charge (List.length inputs); verify (inputs=I.inputs actual) "complete_ordered_external_inputs";
  let groups = List.map (fun (row:A.group_ref) ->
    let group = List.find (fun (value:I.atomic_group) -> value.group_id=row.group_id) (F.atomic_groups (fragment row.slot)) in
    ({group_id=group.group_id;arbiter=rename row.slot group.arbiter;commits=List.map (rename row.slot) group.commits}:I.atomic_group)) (A.group_order rule) in
  charge (List.length groups); verify (groups=I.atomic_groups actual) "complete_ordered_atomic_groups";
  let exports = List.map (fun (row:A.endpoint_ref) ->
    ({node_id=rename row.node.slot row.node.node_id;port_id=row.port_id}:I.endpoint)) (A.export_order rule) in
  charge (List.length exports); verify (exports=I.semantic_exports actual) "complete_ordered_semantic_exports";
  let authority = A.material_authority rule in
  let structure_result = S.check ~parent:budget ~authority ~candidate () in
  let template = PM.template authority in
  let carrier_projections = ref [] and link_projections = ref [] and helper_projections = ref [] in
  if multi_member then (
    let slots=A.slots rule and members=A.member_bindings rule in
    let helper=A.helper rule in
    let source_ids=List.map (fun (row:A.member_binding) -> row.source_id) members @
      (match helper with None -> [] | Some row -> [row.source_id]) in
    let member_ids=List.map (fun (row:A.member_binding) -> row.member_id) members @
      (match helper with None -> [] | Some row -> [row.member_id]) in
    let root slot=CT.Root_source.molecule (C.root (A.component rule slot)) in
    let binding slot=List.find (fun (row:A.member_binding) -> row.slot=slot) members in
    let output (row:A.member_binding)=List.find (fun value -> CT.Output_member.id value=row.member_id) (PT.output_members template) in
    verify (List.length slots=2 && List.map (fun (row:A.member_binding) -> row.slot) members=slots &&
      List.map (fun (row:A.member_binding) -> row.source_id) members=List.map (fun (row:A.root_binding) -> row.source_id) (A.root_bindings rule))
      "complete_ordered_two_member_ownership";
    verify (PT.steps template=[] && A.joins rule=[] && PT.complex_members template=[] && PT.amounts template=[])
      "direct_root_members_without_covalent_transforms";
    let inventory actual expected=if Option.is_some helper then
      List.sort compare actual=List.sort compare expected else actual=expected in
    verify (inventory (List.map CT.Root_source.id (PT.sources template)) source_ids &&
      inventory (List.map CT.Output_member.id (PT.output_members template)) member_ids &&
      PM.member_order authority=member_ids)
      "exact_original_member_order";
    let projected_chemistry ~space chemistry =
      let tail=H.terminal_tail chemistry in
      let tail_json=match H.Tail.path tail with None -> H.Tail.to_json tail
        | Some path -> replace "path" (project_path ~offset:0 ~space path) (H.Tail.to_json tail) in
      replace "terminal_tail" tail_json (H.to_json chemistry) in
    let expected_product_json (value:PM.product)=obj ["identity",Pin.to_json value.identity;"sequence",str value.sequence;
      "translation_policy",Bioc_domain.Molecular_recoding.Translation_policy.to_json value.translation_policy;
      "provenance",M.Provenance.to_json value.provenance] in
    List.iter (fun (row:A.member_binding) ->
      let member=output row in
      let source=List.find (fun value -> CT.Root_source.id value=row.source_id) (PT.sources template) in
      verify (equal (CT.Root_source.to_json source)
        (replace "id" (str row.source_id) (CT.Root_source.to_json (C.root (A.component rule row.slot)))))
        "complete_original_member_root_authority";
      verify (CT.Value_ref.kind (CT.Output_member.value member)=CT.Value_ref.Root &&
        CT.Value_ref.id (CT.Output_member.value member)=row.source_id)
        "member_owns_exact_original_root";
      let expected=List.find (fun (value:PM.member) -> value.id=row.member_id) (PM.members authority) in
      match C.products (A.component rule row.slot) with
      | [product] ->
        verify (product.cds_feature=expected.regions.cds &&
          equal (expected_product_json product.expected) (expected_product_json expected.product))
          "complete_member_product_and_cds_ownership";
        let node=rename row.slot product.node_id in
        charge (List.length (B.expressions checked_binding));
        verify (List.exists (fun (expression:B.expression) -> expression.endpoint.node_id=node &&
          expression.endpoint.port_id="out") (B.expressions checked_binding))
          "member_product_has_checked_source_expression"
      | _ -> verify false "exactly_one_original_product_per_member") members;
    Option.iter (fun (helper:A.helper_selection) ->
      let member=List.find (fun output -> CT.Output_member.id output=helper.member_id) (PT.output_members template) in
      let source=List.find (fun source -> CT.Root_source.id source=helper.source_id) (PT.sources template) in
      let expected=List.find (fun (value:PM.member) -> value.id=helper.member_id) (PM.members authority) in
      verify (equal (CT.Root_source.to_json source)
        (replace "id" (str helper.source_id) (CT.Root_source.to_json (HM.root helper.material))))
        "complete_original_helper_root_authority";
      verify (CT.Value_ref.kind (CT.Output_member.value member)=CT.Value_ref.Root &&
        CT.Value_ref.id (CT.Output_member.value member)=helper.source_id)
        "helper_owns_exact_original_root";
      verify (expected.regions=HM.regions helper.material &&
        equal (expected_product_json expected.product) (expected_product_json (HM.product helper.material)))
        "complete_original_helper_regions_and_product";
      verify (equal (projected_chemistry ~space:(CT.Output_member.space_id member) (HM.chemistry helper.material))
        (H.to_json expected.chemistry)) "complete_helper_expected_chemistry_projection";
      let requirements=PT.requirements template in
      let expected_requirements=List.map (fun (row:A.member_binding) -> Some row.member_id,CT.Member_requirement.Payload) members @
        [Some helper.member_id,CT.Member_requirement.Delivered_helper] in
      verify (List.sort compare (List.map (fun row -> CT.Member_requirement.member_id row,CT.Member_requirement.category row) requirements)=
        List.sort compare expected_requirements)
        "complete_payload_and_delivered_helper_categories";
      List.iter (fun requirement ->
        let roles=CT.Member_requirement.roles requirement in
        verify (roles<>[] && List.for_all (fun role -> CT.Role.purpose role=
          CT.Member_requirement.category_purpose (CT.Member_requirement.category requirement)) roles)
          "complete_payload_and_helper_role_purposes") requirements) helper;
    (match S.checked_structure structure_result with
     | None -> ()
     | Some checked ->
       match K.inventory (S.content checked) with
       | None -> verify false "fresh_material_inventory_absent"
       | Some inventory ->
         let molecules=K.Inventory.molecules inventory in
         verify (List.map N.id molecules=member_ids)
           "complete_final_member_inventory";
         List.iter (fun (row:A.member_binding) ->
           let original_root=root row.slot and member=output row in
           let space=CT.Output_member.space_id member in
           match find (fun molecule -> N.id molecule=row.member_id) molecules with
           | None -> verify false "original_material_member_absent"
           | Some molecule ->
             verify (String.length (N.sequence original_root)=String.length (N.sequence molecule)) "complete_member_root_length";
             charge (String.length (N.sequence original_root)+String.length (N.sequence molecule));
             verify (N.sequence original_root=N.sequence molecule) "complete_member_root_bases";
             verify (List.length (N.features original_root)=4 && List.length (N.features molecule)=4)
               "exact_four_original_features_per_member";
             List.iter (fun feature -> match project_feature ~offset:0 ~space feature with
               | None -> verify false "original_feature_path_absent"
               | Some expected -> match find (fun actual -> N.Feature.id actual=N.Feature.id feature) (N.features molecule) with
                 | None -> verify false "projected_feature_absent"
                 | Some actual -> verify (equal expected (N.Feature.to_json actual)) "complete_final_feature_projection") (N.features original_root);
             verify (equal (projected_chemistry ~space (N.chemistry original_root)) (H.to_json (N.chemistry molecule)))
               "complete_final_member_chemistry_projection") members;
         Option.iter (fun (helper:A.helper_selection) ->
           let original=HM.root helper.material in
           let original_root=CT.Root_source.molecule original in
           let member=List.find (fun output -> CT.Output_member.id output=helper.member_id) (PT.output_members template) in
           let space=CT.Output_member.space_id member in
           match find (fun molecule -> N.id molecule=helper.member_id) molecules with
           | None -> verify false "original_helper_member_absent"
           | Some molecule ->
             charge (String.length (N.sequence original_root)+String.length (N.sequence molecule));
             verify (N.sequence original_root=N.sequence molecule) "complete_helper_root_bases";
             verify (List.length (N.features original_root)=4 && List.length (N.features molecule)=4)
               "exact_four_original_helper_features";
             List.iter (fun feature -> match project_feature ~offset:0 ~space feature with
               | None -> verify false "original_helper_feature_path_absent"
               | Some expected -> match find (fun actual -> N.Feature.id actual=N.Feature.id feature) (N.features molecule) with
                 | None -> verify false "projected_helper_feature_absent"
                 | Some actual -> verify (equal expected (N.Feature.to_json actual))
                     "complete_final_helper_feature_projection") (N.features original_root);
             verify (equal (H.to_json (N.chemistry original_root)) (H.to_json (HM.chemistry helper.material)))
               "complete_original_helper_chemistry";
             verify (equal (projected_chemistry ~space (HM.chemistry helper.material)) (H.to_json (N.chemistry molecule)))
               "complete_final_helper_chemistry_projection";
             helper_projections:=obj ["material",HM.to_json helper.material;"source",str helper.source_id;
               "member",str helper.member_id;"product",expected_product_json (HM.product helper.material);
               "root_fingerprint",str (Canonical.fingerprint (CT.Root_source.to_json original));
               "molecule_fingerprint",str (Canonical.fingerprint (N.to_json molecule))]:: !helper_projections) helper;
         let project_site slot (site:C.site) =
           charge 1;
           let row=binding slot in
           let member=output row in
           let molecule=List.find (fun molecule -> N.id molecule=row.member_id) molecules in
           let expected_path=project_path ~offset:0 ~space:(CT.Output_member.space_id member) site.path in
           let feature=find (fun feature -> N.Feature.id feature=site.feature_id) (N.features molecule) in
           verify (match feature with Some value -> (match N.Feature.path value with
             | Some path -> equal expected_path (G.Path.to_json path) | None -> false) | None -> false)
             "carrier_exact_final_feature_path";
           let local=N.sequence (root slot) and actual=N.sequence molecule in
           List.iter (fun span -> let start=G.Span.start span and length=G.Span.length span in
             charge length;
             verify (start>=0 && length>0 && start+length<=String.length local && start+length<=String.length actual &&
               String.sub local start length=String.sub actual start length) "carrier_exact_final_bases") (G.Path.spans site.path);
           obj ["slot",str (slot_name slot);"root",str site.root_id;"source",str row.source_id;
             "feature",str site.feature_id;"local_path",G.Path.to_json site.path;"member",str row.member_id;
             "path",expected_path;"final_feature",str site.feature_id] in
         List.iter (fun slot -> List.iter (fun (carrier:C.carrier) ->
           let sites=List.map (project_site slot) carrier.sites in
           carrier_projections:=obj ["slot",str (slot_name slot);"target",C.target_to_json carrier.target;"sites",arr sites]:: !carrier_projections)
           (C.carriers (A.component rule slot))) slots;
         List.iter (fun (carrier:A.link_carrier) ->
           let link=List.find (fun (row:A.link) -> row.kind=carrier.kind) (A.links rule) in
           let site (boundary:A.boundary_ref) index =
             let row=List.find (fun (row:C.carrier) -> row.target=C.Boundary_port boundary.boundary_id)
               (C.carriers (A.component rule boundary.slot)) in List.nth row.sites index in
           match A.carrier_transport carrier with
           | None -> verify false "original_inter_member_transport_absent"
           | Some transport ->
             verify (transport.producer_member=(binding link.producer.slot).member_id &&
               transport.consumer_member=(binding link.consumer.slot).member_id &&
               transport.producer_member<>transport.consumer_member && A.carrier_joins carrier=[] && carrier.join_id="")
               "cross_link_exact_original_transport_ownership";
             let endpoint_json (value:I.endpoint)=obj ["node",str value.node_id;"port",str value.port_id] in
             link_projections:=obj ["link",str (link_name carrier.kind);"transport",A.transport_to_json transport;
               "producer_endpoint",endpoint_json (boundary_endpoint link.producer);
               "consumer_endpoint",endpoint_json (boundary_endpoint link.consumer);
               "producer",project_site link.producer.slot (site link.producer carrier.producer_site);
               "consumer",project_site link.consumer.slot (site link.consumer carrier.consumer_site)]:: !link_projections)
           (A.link_carriers rule))
  ) else (
  let step = List.hd (PT.steps template) in
  let port = List.hd (CT.Transform_step.ports step) in
  let port_space = CT.Product_port.space_id port in
  let output_member = List.hd (PT.output_members template) in
  let member_id = CT.Output_member.id output_member in
  let member_space = CT.Output_member.space_id output_member in
  let root slot = CT.Root_source.molecule (C.root (A.component rule slot)) in
  let source slot = (List.find (fun (row:A.root_binding) -> row.slot=slot) (A.root_bindings rule)).source_id in
  let slots = A.slots rule in
  (* Derive instance positions independently from the complete original roots.
     The domain decoder's offset helper is not the geometry oracle. *)
  let offsets = if instanced then
    let _, rows = List.fold_left (fun (cursor, rows) slot ->
      charge 1;
      cursor + String.length (N.sequence (root slot)), (slot, cursor) :: rows) (0, []) slots in
    List.rev rows
    else [A.Decision,0;A.Driver,(A.join rule).offset] in
  let offset slot = List.assoc slot offsets in
  let final_feature_id slot local = if instanced then
    Canonical.encode (arr [str (slot_name slot);str local]) else local in
  let projected_feature slot ~space feature =
    match project_feature ~offset:(offset slot) ~space feature with
    | Some raw when instanced -> Some (replace "id" (str (final_feature_id slot (N.Feature.id feature))) raw)
    | result -> result in
  let joins = A.joins rule in
  if instanced then (
    let rec adjacent = function
      | left::(right::_ as rest) -> (left,right)::adjacent rest
      | _ -> [] in
    let expected = adjacent slots in
    verify (List.length joins=List.length expected) "complete_adjacent_join_inventory";
    List.iteri (fun index (left,right) ->
      match List.nth_opt joins index with
      | None -> verify false "original_adjacent_join_absent"
      | Some (join:A.join) ->
        verify (join.left=left && join.right=right && join.offset=offset right &&
          join.step_id=CT.Transform_step.id step && join.port_id=CT.Product_port.id port)
          "exact_original_adjacent_join") expected);
  let feature_transition = CT.Product_port.feature_transition port in
  let feature_dispositions = MT.Feature.dispositions feature_transition in
  let local_features = List.concat_map (fun slot -> List.map (fun feature -> slot,feature) (N.features (root slot))) slots in
  verify (List.length local_features=4 && List.length feature_dispositions=4 && MT.Feature.added feature_transition=[])
    "exact_four_original_feature_dispositions";
  List.iter (fun (slot,feature) ->
    let feature_id = N.Feature.id feature in
    let row = find (fun row -> MT.Feature_disposition.source_id row=source slot &&
      MT.Feature_disposition.feature_id row=feature_id) feature_dispositions in
    let code = "exact_feature_projection:" ^ slot_name slot ^ "/" ^ feature_id in
    match row,projected_feature slot ~space:port_space feature with
    | Some row,Some expected -> verify (MT.Feature_disposition.decision row=MT.Feature_disposition.Exact &&
        equal (arr (List.map N.Feature.to_json (MT.Feature_disposition.outputs row))) (arr [expected])) code
    | _ -> verify false code) local_features;
  let chemistry_transition = CT.Product_port.chemistry_transition port in
  let chemical_dispositions = MT.Chemistry.dispositions chemistry_transition in
  let facets = ["cap";"start_end";"finish_end";"terminal_tail";"modification_inventory"] in
  verify (MT.Chemistry.mode chemistry_transition=MT.Chemistry.Explicit_output &&
    List.length chemical_dispositions=5*List.length slots)
    (if instanced then "complete_original_chemistry_dispositions" else "exact_ten_original_chemistry_dispositions");
  let first_slot=List.hd slots and last_slot=List.hd (List.rev slots) in
  let copied slot facet = match facet with
    | "cap"|"start_end" -> slot=first_slot
    | "finish_end"|"terminal_tail" -> slot=last_slot
    | "modification_inventory" -> true
    | _ -> false in
  List.iter (fun slot -> List.iter (fun facet ->
    let row = find (fun row -> MT.Chemistry_disposition.source_id row=source slot &&
      MT.Component.to_string (MT.Chemistry_disposition.component row)=facet) chemical_dispositions in
    verify (match row with None -> false | Some row ->
      MT.Chemistry_disposition.decision row=(if copied slot facet then MT.Chemistry_disposition.Mapped_copy else MT.Chemistry_disposition.Not_carried) &&
      List.map MT.Component.to_string (MT.Chemistry_disposition.destination_components row)=
        (if copied slot facet then [facet] else [])) ("exact_chemistry_disposition:" ^ slot_name slot ^ "/" ^ facet)) facets) slots;
  let facet_json ~shift ~space chemistry facet = match facet with
    | "cap" -> H.Claim.nominal_json (H.cap chemistry)
    | "start_end" -> H.Claim.nominal_json (H.start_end chemistry)
    | "finish_end" -> H.Claim.nominal_json (H.finish_end chemistry)
    | "terminal_tail" -> let tail = H.terminal_tail chemistry in
      let raw = H.Tail.nominal_json tail in
      (match H.Tail.path tail with None -> raw | Some path -> replace "path" (project_path ~offset:shift ~space path) raw)
    | _ -> obj ["status",str (H.status_name (H.modification_inventory_status chemistry));
      "modifications",arr (List.map H.Modification.nominal_json (H.modifications chemistry))] in
  (match MT.Chemistry.output chemistry_transition with
   | None -> verify false "explicit_output_chemistry_absent"
   | Some chemistry -> List.iter (fun slot -> List.iter (fun facet -> if copied slot facet then
       verify (equal (facet_json ~shift:(offset slot) ~space:port_space (N.chemistry (root slot)) facet)
         (facet_json ~shift:0 ~space:port_space chemistry facet))
         ("exact_chemistry_projection:" ^ slot_name slot ^ "/" ^ facet)) facets) slots);
  (match S.checked_structure structure_result with
   | None -> ()
   | Some checked ->
     match K.inventory (S.content checked) with
     | None -> verify false "fresh_material_inventory_absent"
     | Some inventory ->
       match find (fun molecule -> N.id molecule=member_id) (K.Inventory.molecules inventory) with
       | None -> verify false "original_material_member_absent"
       | Some molecule ->
         verify (List.length (N.features molecule)=4) "exact_four_final_features";
         List.iter (fun (slot,feature) -> match projected_feature slot ~space:member_space feature with
           | None -> verify false "original_feature_path_absent"
           | Some expected -> match find (fun actual -> N.Feature.id actual=final_feature_id slot (N.Feature.id feature)) (N.features molecule) with
             | None -> verify false "projected_feature_absent"
             | Some actual -> verify (equal expected (N.Feature.to_json actual)) "complete_final_feature_projection") local_features;
         List.iter (fun slot -> List.iter (fun facet -> if copied slot facet then
           verify (equal (facet_json ~shift:(offset slot) ~space:member_space (N.chemistry (root slot)) facet)
             (facet_json ~shift:0 ~space:member_space (N.chemistry molecule) facet))
             ("complete_final_chemistry_projection:" ^ slot_name slot ^ "/" ^ facet)) facets) slots;
         let project_site slot (site:C.site) =
           charge 1;
           let expected_path = project_path ~offset:(offset slot) ~space:member_space site.path in
           let feature = find (fun value -> N.Feature.id value=final_feature_id slot site.feature_id) (N.features molecule) in
           let actual_path = match feature with None -> None | Some feature -> N.Feature.path feature in
           verify (match actual_path with Some path -> equal expected_path (G.Path.to_json path) | None -> false)
             "carrier_exact_final_feature_path";
           (* Site geometry and exact source spelling are both preserved; PM's
              reconstruction independently checks every emitted base. *)
           List.iter (fun span -> let start=G.Span.start span and length=G.Span.length span in
             charge length;
             let final_start=start+offset slot in
             let local_sequence=N.sequence (root slot) and final_sequence=N.sequence molecule in
             verify (start>=0 && length>0 && start+length<=String.length local_sequence &&
               final_start>=0 && final_start+length<=String.length final_sequence &&
               String.sub local_sequence start length=String.sub final_sequence final_start length)
               "carrier_exact_final_bases") (G.Path.spans site.path);
           let fields = ["slot",str (slot_name slot);"root",str site.root_id;"source",str (source slot);
             "feature",str site.feature_id;"local_path",G.Path.to_json site.path;
             "member",str member_id;"path",expected_path] in
           obj (if instanced then fields @ ["final_feature",str (final_feature_id slot site.feature_id)] else fields) in
         List.iter (fun slot -> List.iter (fun (carrier:C.carrier) ->
           let sites = List.map (project_site slot) carrier.sites in
           carrier_projections := obj ["slot",str (slot_name slot);"target",C.target_to_json carrier.target;
             "sites",arr sites] :: !carrier_projections) (C.carriers (A.component rule slot))) slots;
         List.iter (fun (carrier:A.link_carrier) ->
           let link = List.find (fun (value:A.link) -> value.kind=carrier.kind) (A.links rule) in
           let site (boundary:A.boundary_ref) index =
             let row = List.find (fun (row:C.carrier) -> row.target=C.Boundary_port boundary.boundary_id)
               (C.carriers (A.component rule boundary.slot)) in
             List.nth row.sites index in
           let producer_site=site link.producer carrier.producer_site and consumer_site=site link.consumer carrier.consumer_site in
           let encode_endpoint (value:I.endpoint) = obj ["node",str value.node_id;"port",str value.port_id] in
           if instanced then (
             (* A connection spanning an intermediate root must retain every
                crossed original junction, regardless of signal direction. *)
             charge (List.length slots+List.length joins);
             let rec position index sought = function
               | slot::_ when slot=sought -> index
               | _::rest -> position (index+1) sought rest
               | [] -> Diagnostic.fail "policy_component_assembly_instance"
                   "Link endpoint has no original material instance." in
             let producer_position=position 0 link.producer.slot slots
             and consumer_position=position 0 link.consumer.slot slots in
             let first=min producer_position consumer_position and last=max producer_position consumer_position in
             let crossed=List.filteri (fun index _ -> first<=index && index<last) joins in
             let total_length=List.fold_left (fun length slot -> length+String.length (N.sequence (root slot))) 0 slots in
             verify (producer_position<>consumer_position &&
               A.carrier_joins carrier=List.map (fun (join:A.join) -> join.join_id) crossed &&
               String.length (N.sequence molecule)=total_length)
               "cross_link_complete_original_join_path";
             link_projections := obj ["link",str (link_name carrier.kind);
               "joins",arr (List.map (fun (join:A.join) -> str join.join_id) crossed);
               "offsets",arr (List.map (fun (join:A.join) -> Json.int join.offset) crossed);
               "producer_endpoint",encode_endpoint (boundary_endpoint link.producer);
               "consumer_endpoint",encode_endpoint (boundary_endpoint link.consumer);
               "producer",project_site link.producer.slot producer_site;
               "consumer",project_site link.consumer.slot consumer_site] :: !link_projections)
           else (
             let join=A.join rule in
             verify (carrier.join_id=join.join_id && link.producer.slot<>link.consumer.slot &&
               String.length (N.sequence (root A.Decision))=join.offset &&
               String.length (N.sequence molecule)=join.offset+String.length (N.sequence (root A.Driver)))
               "cross_link_adjacent_original_join";
             link_projections := obj ["link",str (link_name carrier.kind);"join",str join.join_id;
               "offset",Json.int join.offset;"producer_endpoint",encode_endpoint (boundary_endpoint link.producer);
               "consumer_endpoint",encode_endpoint (boundary_endpoint link.consumer);
               "producer",project_site link.producer.slot producer_site;
               "consumer",project_site link.consumer.slot consumer_site] :: !link_projections)) (A.link_carriers rule)));
  let findings = List.rev !findings in
  let outcome_value = if findings<>[] then E.Fail else S.outcome structure_result in
  let report_value = obj (["schema_version",str "biocompiler.policy_component_assembly_assessment.v0.1";
    "checker_version",str (if grounded_helper then grounded_helper_implementation_version else if multi_member then multi_member_implementation_version else if instanced then instance_implementation_version else implementation_version);"profile",str profile;
    "original_fingerprint",str (R.fingerprint original);"components_fingerprint",str (L.fingerprint components);
    "rule_fingerprint",str (A.fingerprint rule);"implementation_fingerprint",str (I.fingerprint actual);
    "proposed_fingerprint",str (Q.fingerprint proposed);"candidate_fingerprint",str (K.fingerprint candidate);
    "outcome",str (E.outcome_name outcome_value);"diagnostics",arr (List.map str findings);
    "claim_scope",str "exact_supplied_component_graph_and_material_correspondence";
    "premise",str "supplied_conditional_model_to_sequence_composition_rule";
    "structure",S.report structure_result;"carrier_projections",arr (List.rev !carrier_projections);
    "link_projections",arr (List.rev !link_projections);
    "preservation_evidence_fingerprint",str (Canonical.fingerprint (P.evidence implementation));
    "catalog_authorization",str "unassessed";"context",str "unassessed";"resource_capacity",str "unassessed";
    "input_compatibility",str "unassessed";"source_obligation_discharge",str "unassessed";
    "empirical",str "unassessed";"artifact",str "withheld";"export",str "withheld"] @
    (if grounded_helper then ["helper_projections",arr (List.rev !helper_projections)] else [])) in
  ignore (encoded report_value);
  (* Sticky parent/child exhaustion cannot be converted into a private leaf. *)
  Diagnostic.require (not (W.exhausted budget)) "policy_component_assembly_resource_limit" "Assembly work was exhausted.";
  let accepted_value = match outcome_value,S.checked_structure structure_result with
    | E.Pass,Some structure_value -> Some {original_value=original;components_value=components;rule_value=rule;
        implementation_value=implementation;structure_value;evidence_value=report_value}
    | _ -> None in
  {outcome_value;report_value;accepted_value}
