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
module MT = Bioc_domain.Molecular_transition
module N = Bioc_domain.Molecule
module G = Bioc_domain.Molecule_coordinates
module H = Bioc_domain.Molecule_chemistry
module M = Bioc_domain.Molecular_record
module Pin = Bioc_domain.Pinned_identity
module W = Bioc_checker.Work_budget
let implementation_version = "biocompiler.ocaml.policy_component_assembly_check.v0.1"
let max_work = 100000000
let str value = Json.String value
let obj values = Json.Object values
let arr values = Json.Array values
let slot_name = function A.Decision -> "decision" | A.Driver -> "driver"
let link_name = function A.Product -> "product" | A.Request -> "request" | A.Authorization -> "authorization"
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
  let budget = match parent with
    | None -> W.create ~profile:A.profile ~error_code:"policy_component_assembly_resource_limit" ~maximum ()
    | Some parent -> W.nested ~parent ~profile:A.profile ~error_code:"policy_component_assembly_resource_limit" ~maximum () in
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
  let original = R.of_json original_raw in
  let checked_binding = P.binding implementation in
  let actual = B.implementation checked_binding in
  let bound_original = RA.request (B.admitted_inputs checked_binding) in
  verify (equal original_raw (R.to_json bound_original)) "unchanged_original_realization_request";
  (* Fresh membership checks use the untouched original model library. No new
     source-bearing implementation or replacement v1 material request exists. *)
  let components = L.of_json ~library:(R.implementation_library original) library_raw in
  let rule = A.of_json ~components rule_raw and proposed = Q.of_json proposal_raw in
  verify (equal (Pin.to_json (Q.rule proposed)) (Pin.to_json (A.identity rule))) "original_assembly_rule_pin";
  verify (A.model_library_digest rule = (I.authority actual).library_digest) "original_model_library";
  verify (A.component_library_digest rule = L.fingerprint components) "original_component_library";
  verify (F.phase_profile = Bioc_candidate_runtime.Policy_primitives.profile) "fixed_primitive_execution_phases";
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
  let template = PM.template authority and join = A.join rule in
  let step = List.hd (PT.steps template) in
  let port = List.hd (CT.Transform_step.ports step) in
  let port_space = CT.Product_port.space_id port in
  let output_member = List.hd (PT.output_members template) in
  let member_id = CT.Output_member.id output_member in
  let member_space = CT.Output_member.space_id output_member in
  let root slot = CT.Root_source.molecule (C.root (A.component rule slot)) in
  let source slot = (List.find (fun (row:A.root_binding) -> row.slot=slot) (A.root_bindings rule)).source_id in
  let offset = function A.Decision -> 0 | A.Driver -> join.offset in
  let feature_transition = CT.Product_port.feature_transition port in
  let feature_dispositions = MT.Feature.dispositions feature_transition in
  let local_features = List.concat_map (fun slot -> List.map (fun feature -> slot,feature) (N.features (root slot))) [A.Decision;A.Driver] in
  verify (List.length local_features=4 && List.length feature_dispositions=4 && MT.Feature.added feature_transition=[])
    "exact_four_original_feature_dispositions";
  List.iter (fun (slot,feature) ->
    let feature_id = N.Feature.id feature in
    let row = find (fun row -> MT.Feature_disposition.source_id row=source slot &&
      MT.Feature_disposition.feature_id row=feature_id) feature_dispositions in
    let code = "exact_feature_projection:" ^ slot_name slot ^ "/" ^ feature_id in
    match row,project_feature ~offset:(offset slot) ~space:port_space feature with
    | Some row,Some expected -> verify (MT.Feature_disposition.decision row=MT.Feature_disposition.Exact &&
        equal (arr (List.map N.Feature.to_json (MT.Feature_disposition.outputs row))) (arr [expected])) code
    | _ -> verify false code) local_features;
  let chemistry_transition = CT.Product_port.chemistry_transition port in
  let chemical_dispositions = MT.Chemistry.dispositions chemistry_transition in
  let facets = ["cap";"start_end";"finish_end";"terminal_tail";"modification_inventory"] in
  verify (MT.Chemistry.mode chemistry_transition=MT.Chemistry.Explicit_output && List.length chemical_dispositions=10)
    "exact_ten_original_chemistry_dispositions";
  let copied slot facet = match slot,facet with
    | A.Decision,("cap"|"start_end"|"modification_inventory")
    | A.Driver,("finish_end"|"terminal_tail"|"modification_inventory") -> true | _ -> false in
  List.iter (fun slot -> List.iter (fun facet ->
    let row = find (fun row -> MT.Chemistry_disposition.source_id row=source slot &&
      MT.Component.to_string (MT.Chemistry_disposition.component row)=facet) chemical_dispositions in
    verify (match row with None -> false | Some row ->
      MT.Chemistry_disposition.decision row=(if copied slot facet then MT.Chemistry_disposition.Mapped_copy else MT.Chemistry_disposition.Not_carried) &&
      List.map MT.Component.to_string (MT.Chemistry_disposition.destination_components row)=
        (if copied slot facet then [facet] else [])) ("exact_chemistry_disposition:" ^ slot_name slot ^ "/" ^ facet)) facets) [A.Decision;A.Driver];
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
         ("exact_chemistry_projection:" ^ slot_name slot ^ "/" ^ facet)) facets) [A.Decision;A.Driver]);
  let carrier_projections = ref [] and link_projections = ref [] in
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
         List.iter (fun (slot,feature) -> match project_feature ~offset:(offset slot) ~space:member_space feature with
           | None -> verify false "original_feature_path_absent"
           | Some expected -> match find (fun actual -> N.Feature.id actual=N.Feature.id feature) (N.features molecule) with
             | None -> verify false "projected_feature_absent"
             | Some actual -> verify (equal expected (N.Feature.to_json actual)) "complete_final_feature_projection") local_features;
         List.iter (fun slot -> List.iter (fun facet -> if copied slot facet then
           verify (equal (facet_json ~shift:(offset slot) ~space:member_space (N.chemistry (root slot)) facet)
             (facet_json ~shift:0 ~space:member_space (N.chemistry molecule) facet))
             ("complete_final_chemistry_projection:" ^ slot_name slot ^ "/" ^ facet)) facets) [A.Decision;A.Driver];
         let project_site slot (site:C.site) =
           charge 1;
           let expected_path = project_path ~offset:(offset slot) ~space:member_space site.path in
           let feature = find (fun value -> N.Feature.id value=site.feature_id) (N.features molecule) in
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
           obj ["slot",str (slot_name slot);"root",str site.root_id;"source",str (source slot);
             "feature",str site.feature_id;"local_path",G.Path.to_json site.path;
             "member",str member_id;"path",expected_path] in
         List.iter (fun slot -> List.iter (fun (carrier:C.carrier) ->
           let sites = List.map (project_site slot) carrier.sites in
           carrier_projections := obj ["slot",str (slot_name slot);"target",C.target_to_json carrier.target;
             "sites",arr sites] :: !carrier_projections) (C.carriers (A.component rule slot))) [A.Decision;A.Driver];
         List.iter (fun (carrier:A.link_carrier) ->
           let link = List.find (fun (value:A.link) -> value.kind=carrier.kind) (A.links rule) in
           let site (boundary:A.boundary_ref) index =
             let row = List.find (fun (row:C.carrier) -> row.target=C.Boundary_port boundary.boundary_id)
               (C.carriers (A.component rule boundary.slot)) in
             List.nth row.sites index in
           let producer_site=site link.producer carrier.producer_site and consumer_site=site link.consumer carrier.consumer_site in
           verify (carrier.join_id=join.join_id && link.producer.slot<>link.consumer.slot &&
             String.length (N.sequence (root A.Decision))=join.offset &&
             String.length (N.sequence molecule)=join.offset+String.length (N.sequence (root A.Driver)))
             "cross_link_adjacent_original_join";
           let encode_endpoint (value:I.endpoint) = obj ["node",str value.node_id;"port",str value.port_id] in
           link_projections := obj ["link",str (link_name carrier.kind);"join",str join.join_id;
             "offset",Json.int join.offset;"producer_endpoint",encode_endpoint (boundary_endpoint link.producer);
             "consumer_endpoint",encode_endpoint (boundary_endpoint link.consumer);
             "producer",project_site link.producer.slot producer_site;
             "consumer",project_site link.consumer.slot consumer_site] :: !link_projections) (A.link_carriers rule));
  let findings = List.rev !findings in
  let outcome_value = if findings<>[] then E.Fail else S.outcome structure_result in
  let report_value = obj ["schema_version",str "biocompiler.policy_component_assembly_assessment.v0.1";
    "checker_version",str implementation_version;"profile",str A.profile;
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
    "empirical",str "unassessed";"artifact",str "withheld";"export",str "withheld"] in
  ignore (encoded report_value);
  (* Sticky parent/child exhaustion cannot be converted into a private leaf. *)
  Diagnostic.require (not (W.exhausted budget)) "policy_component_assembly_resource_limit" "Assembly work was exhausted.";
  let accepted_value = match outcome_value,S.checked_structure structure_result with
    | E.Pass,Some structure_value -> Some {original_value=original;components_value=components;rule_value=rule;
        implementation_value=implementation;structure_value;evidence_value=report_value}
    | _ -> None in
  {outcome_value;report_value;accepted_value}
