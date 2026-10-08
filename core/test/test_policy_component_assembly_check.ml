open Bioc_wire
open Bioc_policy_component_test_support.Literals
module Q = Bioc_domain.Policy_component_assembly_proposal
module Check = Bioc_realization_checker.Policy_component_assembly_check
module V = Bioc_realization_checker.Policy_preservation_check
module RR = Bioc_domain.Policy_realization_request
module O = Bioc_domain.Policy_operational
module U = Bioc_domain.Policy_implementation_binding
module SA = Bioc_checker.Policy_admission
module RA = Bioc_checker.Policy_realization_admission
module SL = Bioc_compiler.Policy_lowering
module GL = Bioc_compiler.Policy_implementation_lowering
module CL = Bioc_compiler.Policy_component_lowering
module CP = Bioc_compiler.Construction_producer
module K = Bioc_domain.Construction_content
module Artifact = Bioc_domain.Construction_artifact
module E = Bioc_domain.Construction_assessment
module W = Bioc_checker.Work_budget

(* Literal expected covalent material, independently declared from the two
   original roots. These names are wire conventions, not producer output. *)
let output_features state_reading frame =
  let offset = if state_reading then 3 else 2 in
  List.map N.Feature.of_json [
    feature frame "cds" "coding_sequence" offset (offset+9) (Json.int 0);
    feature frame "poly_a" "poly_a_tail" (offset+11) (offset+15) Json.Null;
    feature frame "utr3" "three_prime_utr" (offset+9) (offset+11) Json.Null;
    feature frame "utr5" "five_prime_utr" 0 offset Json.Null]
let output_chemistry state_reading frame =
  let offset = if state_reading then 3 else 2 in
  H.of_json (chemistry frame true |> put ["terminal_tail";"path"] (path frame (offset+11) (offset+15)))
let literal_sequence = function false -> "CCAUGGCUUAAGGAAAA" | true -> "CGCAUGGCUUAAGGAAAA"
let literal_molecule state_reading =
  let sequence = literal_sequence state_reading in
  let length = if state_reading then 18 else 17 in
  let p = M.Provenance.of_json provenance in
  N.make ~id:"payload" ~form:N.Delivered_rna ~space:(G.Space.of_json (space "payload.frame" length))
    ~sequence ~sequence_extent:H.Complete ~coding_status:N.Coding
    ~assembly:[N.Assembly_origin.make ~id:"payload.origin"
      ~destination:(G.Path.of_json (path "payload.frame" 0 length))
      ~source_space:(G.Space.of_json (space "join.frame" length))
      ~source_path:(G.Path.of_json (path "join.frame" 0 length)) ~provenance:p]
    ~features:(output_features state_reading "payload.frame")
    ~chemistry:(output_chemistry state_reading "payload.frame") ~provenance:p
let literal_content state_reading authority =
  let leader,offset,length = if state_reading then "leader_B",3,18 else "leader_A",2,17 in
  let segment source first last local_last = Artifact.Derived_segment.make
    ~destination:(G.Span.of_json (span first last)) ~source_id:source
    ~source_path:(G.Path.of_json (path (source^".frame") 0 local_last)) ~rule:Artifact.Derived_segment.Copy in
  let value = Artifact.Value.make ~id:"joined" ~space:(G.Space.of_json (space "join.frame" length))
    ~sequence:(literal_sequence state_reading) ~chemistry:(output_chemistry state_reading "join.frame")
    ~features:(output_features state_reading "join.frame")
    ~segments:[segment leader 0 offset offset;segment "driver_body" offset length 15]
    ~step_id:"join" ~sequence_extent:H.Complete ~consumed:[] in
  let molecule = literal_molecule state_reading in
  let inventory = K.Inventory.make ~id:(if state_reading then "fixture.join.B.molecules" else "fixture.join.A.molecules")
    ~molecules:[molecule] ~complexes:[] ~role_instances:[N.Role.make ~id:"payload.role" ~subject_id:"payload"
      ~subject_fingerprint:(N.fingerprint molecule) ~role:"payload" ~purpose:N.Role.Requested_payload ~compartment:"cytoplasm"]
    ~form_mappings:[] in
  K.make ~authority_fingerprint:(K.authority_fingerprint ~template:(PM.template authority) ~member_order:["payload"])
    ~member_order:["payload"] ~values:[value] ~inventory:(Some inventory)
    ~missing_members:[] ~diagnostics:[] ~experimental_amounts:[]

(* Graph production supplies only an untrusted candidate. The complete
   independently authored wire inventory must already agree before rearranging
   it to the original rule's observable order. Fresh preservation follows. *)
let rec rename names = function
  | Json.String value -> str (Option.value ~default:value (List.assoc_opt value names))
  | Json.Array values -> arr (List.map (rename names) values)
  | Json.Object fields -> obj (List.map (fun (key,value) -> key,rename names value) fields)
  | value -> value
let allocation state_reading = [
  "observation/0","evidence";"state/0","selected";"state/1","excluded";
  "attempt/0","attempt";"arbitration/0","arbiter";
  "rule/0/gate","select_gate";"rule/0/commit","select_commit";
  "rule/1/gate","exclude_gate";"rule/1/commit","exclude_commit";
  "evidence/0","condition";"feedback/0","feedback";"exclusive/0","exclusive_selection"] @
  (if state_reading then ["expression/0","select_edge";"expression/1","selected_not";
    "expression/2","select_guard";"expression/3","true";"expression/4","product";
    "expression/5","not";"expression/6","exclude_edge";"expression/7","false"]
   else ["expression/0","select_edge";"expression/1","true";"expression/2","false";
     "expression/3","product";"expression/4","not";"expression/5","exclude_edge"])
let sorted_json values = List.sort String.compare (List.map Canonical.encode values)
let expected_wires state_reading models =
  let local = items "wires" (decision models state_reading) in
  let links = [wire "product" "out" "select_commit" "product0";
    wire "select_commit" "request0" "attempt" "request";
    wire (if state_reading then "select_guard" else "evidence") (if state_reading then "out" else "value")
      "attempt" "authorization"] in
  List.filteri (fun i _ -> i<19) local @ links @ List.filteri (fun i _ -> i>=19) local
let prepare fixture state_reading =
  let request = RR.of_json (get "implementation_request" (get "request" fixture)) in
  let behavior = SL.lower (SA.admit ~document:(RR.document request) ~descriptors:(RR.definitions request)) in
  let admitted = RA.admit ~request ~behavior in
  let produced = GL.lower ~admitted ~library:(RR.implementation_library request) in
  let graph = rename (allocation state_reading) (I.to_json produced.implementation) in
  let binding = U.of_json (rename (allocation state_reading) (U.to_json produced.binding)) in
  let names = List.map (get "node") (global_nodes state_reading) in
  let produced_nodes = items "nodes" graph in
  require (sorted_json names=sorted_json (List.map (get "id") produced_nodes)) "Unexpected source producer node allocation";
  let nodes = List.map (fun id -> List.find (fun row -> get "id" row=id) produced_nodes) names in
  let wires = expected_wires state_reading (original_library fixture) in
  require (sorted_json wires=sorted_json (items "wires" graph)) "Source producer disagrees with literal full union wiring";
  let exports = List.map (fun row -> endpoint (Json.string (get "node" row)) (Json.string (get "port" row)))
      (global_exports state_reading) in
  require (sorted_json exports=sorted_json (items "semantic_exports" graph)) "Source producer disagrees with literal exports";
  let graph = graph |> replace "nodes" (arr nodes) |> replace "wires" (arr wires)
    |> replace "semantic_exports" (arr exports) in
  let implementation = I.of_json ~library:(RR.implementation_library request) graph in
  request,behavior,implementation,binding,V.limits_of_json (get "limits" fixture)
let preserved request behavior implementation binding limits =
  let result = V.check ~request ~behavior ~implementation ~proposed:binding ~limits in
  let report = V.report result in
  let coverage = get "coverage" report in
  require (get "complete" coverage=Json.Bool true && get "preservation" report=str "pass")
    ("Independent finite preservation failed: "^Canonical.encode report);
  List.iter (fun (key,expected) -> require (get key coverage=Json.int expected) ("Finite domain census: "^key))
    ["histories",9;"transitions",47;"prefixes_started",48;"matched_prefixes",48];
  let requirements = items "requirements" report in
  require (List.map (get "id") requirements=List.map str ["request_progress";"initiation_progress";"exclusive_selection"])
    "Original ordered requirement inventory changed";
  List.iter (fun row -> require (get "status" row=str "pass") "Original hard requirement failed";
    require (get "pass" (get "histories" row)=Json.int 9) "Requirement history census changed") requirements;
  match V.accepted result with Some value -> value | None -> failwith "Complete preserved source yielded no private implementation"
let proposal state_reading rule = obj ["schema_version",str Q.schema_version;"profile",str Q.profile;
  "rule",P.to_json (A.identity rule);"nodes",arr (List.map (fun row ->
    add "actual" (get "node" row) row) (global_nodes state_reading))]
let result_failed label code result =
  require (Check.outcome result=E.Fail && Option.is_none (Check.accepted result)) ("Assembly mutation accepted: "^label);
  require (List.mem (str code) (items "diagnostics" (Check.report result))) ("Assembly mutation missed exact boundary: "^label)
let scope report =
  List.iter (fun key -> require (get key report=str "unassessed") ("Leaf promoted "^key))
    ["catalog_authorization";"context";"resource_capacity";"input_compatibility";"source_obligation_discharge";"empirical"];
  List.iter (fun key -> require (get key report=str "withheld") ("Leaf authorized "^key)) ["artifact";"export"];
  require (get "claim_scope" report=str "exact_supplied_component_graph_and_material_correspondence") "Leaf claim changed"
let accepted label result =
  require (Check.outcome result=E.Pass) (label^": "^Canonical.encode (Check.report result));
  scope (Check.report result);
  match Check.accepted result with Some value -> value | None -> failwith (label^": no private assembly")
let expected_site state_reading slot local =
  let offset = if slot="driver" then (if state_reading then 3 else 2) else 0 in
  let local_path = get "path" local in
  let projected = local_path |> replace "space_id" (str "payload.frame")
    |> edit ["spans"] (fun raw -> arr (List.map (fun span ->
      let shifted key = Json.int (int_of_string (Canonical.encode (get key span))+offset) in
      span |> replace "start" (shifted "start") |> replace "end" (shifted "end")) (Json.array raw))) in
  obj ["slot",str slot;"root",get "root" local;"source",get "root" local;
    "feature",get "feature" local;"local_path",local_path;"member",str "payload";"path",projected]
let expected_carriers state_reading =
  let leader,length = if state_reading then "leader_B",3 else "leader_A",2 in
  List.map (fun target -> obj ["slot",str "decision";"target",target;
    "sites",arr [expected_site state_reading "decision" (site leader "utr5" 0 length)]]) (decision_targets state_reading) @
  List.map (fun row -> obj ["slot",str "driver";"target",get "target" row;
    "sites",arr (List.map (expected_site state_reading "driver") (items "sites" row))]) driver_carriers
let expected_links state_reading =
  let leader,length = if state_reading then "leader_B",3 else "leader_A",2 in
  let decision_site = expected_site state_reading "decision" (site leader "utr5" 0 length) in
  let driver_site feature first last = expected_site state_reading "driver" (site "driver_body" feature first last) in
  let link id producer_endpoint consumer_endpoint producer consumer = obj ["link",str id;
    "join",str "leader_to_driver";"offset",Json.int length;"producer_endpoint",producer_endpoint;
    "consumer_endpoint",consumer_endpoint;"producer",producer;"consumer",consumer] in
  [link "product" (endpoint "product" "out") (endpoint "select_commit" "product0") (driver_site "cds" 0 9) decision_site;
   link "request" (endpoint "select_commit" "request0") (endpoint "attempt" "request") decision_site (driver_site "utr3" 9 11);
   link "authorization" (endpoint (if state_reading then "select_guard" else "evidence") (if state_reading then "out" else "value"))
     (endpoint "attempt" "authorization") decision_site (driver_site "utr3" 9 11)]

type fixture_case = { state_reading:bool; request:RR.t; behavior:O.behavior;
  graph:I.t; binding:U.t; limits:V.limits; preserved:V.checked_implementation;
  components:L.t; assembly_rule:A.t; proposed:Q.t; content:K.t }
let make_case fixture state_reading =
  let request,behavior,graph,binding,limits = prepare fixture state_reading in
  let preserved = preserved request behavior graph binding limits in
  let models = original_library fixture in
  let decision_raw = decision_component models state_reading and driver_raw = driver_component models in
  let components = L.of_json ~library:(RR.implementation_library request) (library [decision_raw;driver_raw]) in
  let assembly_rule = A.of_json ~components (rule state_reading decision_raw driver_raw) in
  let proposed = Q.of_json (proposal state_reading assembly_rule) in
  let content = literal_content state_reading (A.material_authority assembly_rule) in
  {state_reading;request;behavior;graph;binding;limits;preserved;components;assembly_rule;proposed;content}
let check case = Check.check ~original:case.request ~components:case.components ~rule:case.assembly_rule
  ~implementation:case.preserved ~proposed:case.proposed ~candidate:case.content ()
let with_graph case graph binding =
  let graph = I.of_json ~library:(RR.implementation_library case.request) graph in
  let binding = U.of_json binding in
  {case with graph;binding;preserved=preserved case.request case.behavior graph binding case.limits}
let with_rule case raw =
  let assembly_rule = A.of_json ~components:case.components (repin raw) in
  {case with assembly_rule;proposed=Q.of_json (proposal case.state_reading assembly_rule)}
let rebind_content authority raw =
  raw |> replace "authority_fingerprint" (str (K.authority_fingerprint ~template:(PM.template authority) ~member_order:["payload"]))
let change_molecule transform raw =
  let molecule = N.of_json (transform (at ["inventory";"molecules";"0"] raw)) in
  raw |> put ["inventory";"molecules";"0"] (N.to_json molecule)
    |> put ["inventory";"role_instances";"0";"subject_fingerprint"] (str (N.fingerprint molecule))
let material_failed label result =
  require (Check.outcome result=E.Fail && Option.is_none (Check.accepted result)) ("Material mutation accepted: "^label);
  require (get "outcome" (get "structure" (Check.report result))=str "fail") ("Material negative missed fresh PM: "^label)
let positive case =
  let result = check case in
  let checked = accepted "literal complete assembly" result in
  let report = Check.report result in
  require (Json.equal (RR.to_json (Check.original checked)) (RR.to_json case.request)) "Private assembly lost original source authority";
  require (Json.equal (L.to_json (Check.components checked)) (L.to_json case.components)) "Private assembly lost original component bodies";
  require (A.fingerprint (Check.rule checked)=A.fingerprint case.assembly_rule) "Private assembly replaced original rule";
  require (Json.equal (V.evidence (Check.implementation checked)) (V.evidence case.preserved)) "Private assembly replaced preservation";
  require (Json.equal (Check.evidence checked) report) "Private evidence differs from exact result";
  let material = Bioc_checker.Policy_mrna_structure_check.content (Check.structure checked) in
  require (Json.equal (K.to_json material) (K.to_json case.content)) "Fresh reconstruction did not retain complete literal content";
  let inventory = Option.get (K.inventory material) in
  let molecule = List.hd (K.Inventory.molecules inventory) in
  require (List.length (K.Inventory.molecules inventory)=1 && Json.equal (N.to_json molecule) (N.to_json (literal_molecule case.state_reading)))
    "Full molecule, feature, chemistry or original provenance differs from independent literal";
  require (N.sequence molecule=literal_sequence case.state_reading && String.length (N.sequence molecule)=(if case.state_reading then 18 else 17))
    "Wrong exact joined base sequence";
  let rows = items "carrier_projections" report in
  require (List.length rows=(if case.state_reading then 107 else 96) && Json.equal (arr rows) (arr (expected_carriers case.state_reading)))
    "Complete ordered local carrier receipts differ from independent geometry";
  require (Json.equal (get "link_projections" report) (arr (expected_links case.state_reading))) "Every cross-link must carry exact original endpoint and material sites";
  List.iter (fun (key,expected) -> require (get key report=str expected) ("Original receipt pin: "^key))
    ["original_fingerprint",RR.fingerprint case.request;"components_fingerprint",L.fingerprint case.components;
     "rule_fingerprint",A.fingerprint case.assembly_rule;"implementation_fingerprint",I.fingerprint case.graph;
     "proposed_fingerprint",Q.fingerprint case.proposed;"candidate_fingerprint",K.fingerprint case.content;
     "preservation_evidence_fingerprint",Canonical.fingerprint (V.evidence case.preserved)];
  let fresh = check case in
  require (Json.equal (Check.report fresh) report) "Fresh full assembly check changed exact evidence";
  report
let proposal_controls case =
  let raw = Q.to_json case.proposed in
  let negative label code mutate =
    let proposed = Q.of_json (mutate raw) in
    result_failed label code (check {case with proposed}) in
  negative "missing local node" "ordered_total_local_node_bijection"
    (edit ["nodes"] (fun rows -> arr (List.tl (Json.array rows))));
  negative "duplicate local node" "ordered_total_local_node_bijection"
    (edit ["nodes";"1"] (fun _ -> at ["nodes";"0"] raw));
  negative "local owner crossing" "ordered_total_local_node_bijection" (put ["nodes";"0";"slot"] (str "driver"));
  negative "extra actual owner" "ordered_total_actual_node_bijection" (put ["nodes";"0";"actual"] (str "unowned"));
  negative "duplicate actual owner" "ordered_total_actual_node_bijection" (put ["nodes";"1";"actual"] (str "evidence"));
  negative "mapping changes local order" "ordered_total_local_node_bijection"
    (edit ["nodes"] (fun rows -> let rows=Json.array rows in arr (List.nth rows 1::List.hd rows::List.tl (List.tl rows))));
  negative "stale whole rule" "original_assembly_rule_pin" (put ["rule";"id"] (str "another.original.rule"));
  rejected "unknown_field" "saved PASS is not an assembly proposal" (fun () -> Q.of_json (add "outcome" (str "pass") raw));
  rejected "policy_component_assembly_proposal" "unknown proposal slot" (fun () -> Q.of_json (put ["nodes";"0";"slot"] (str "helper") raw));
  rejected "policy_component_assembly_proposal" "unknown proposal profile" (fun () -> Q.of_json (replace "profile" (str "future") raw));
  rejected "molecular_resource_limit" "bounded proposal inventory" (fun () -> Q.of_json (replace "nodes" (arr (List.init 257 (fun _ -> at ["nodes";"0"] raw))) raw))
(* Alpha conversion changes node references only. Local node names deliberately
   collide with the evidence kind and product link ID; those are not aliases. *)
let rename_fields names keys raw =
  List.fold_left (fun value key -> edit [key] (rename names) value) raw keys
let map_rows key transform = edit [key] (fun rows -> arr (List.map transform (Json.array rows)))
let alpha_graph names raw =
  let node = rename_fields names ["node"] in
  raw |> map_rows "nodes" (rename_fields names ["id"])
    |> map_rows "wires" (fun row -> row |> edit ["producer"] node |> edit ["consumer"] node)
    |> map_rows "inputs" (edit ["consumer"] node)
    |> map_rows "atomic_groups" (fun row -> row |> rename_fields names ["arbiter"]
      |> edit ["commits"] (fun values -> arr (List.map (rename names) (Json.array values))))
    |> map_rows "semantic_exports" node
    |> map_rows "occurrences" (map_rows "targets" node)
let alpha_binding names raw =
  raw |> map_rows "observations" (rename_fields names ["bank"])
    |> map_rows "states" (rename_fields names ["register"])
    |> map_rows "effects" (rename_fields names ["bank"])
    |> map_rows "rules" (rename_fields names ["gate";"arbiter";"commit"])
let alpha_links names rows = arr (List.map (fun row -> row
  |> edit ["producer_endpoint"] (rename_fields names ["node"])
  |> edit ["consumer_endpoint"] (rename_fields names ["node"])) rows)
let graph_controls case =
  let names = List.map (fun (node:I.node) -> node.node_id,"alpha."^node.node_id) (I.nodes case.graph) in
  let graph = alpha_graph names (I.to_json case.graph) in
  require (List.map (get "kind") (items "inputs" graph)=[str "evidence";str "feedback"])
    "Alpha conversion changed an external input kind";
  require (get "authority" graph=get "authority" (I.to_json case.graph) &&
    List.map (get "model") (items "nodes" graph)=List.map (get "model") (items "nodes" (I.to_json case.graph)))
    "Alpha conversion changed original authority or configured model identities";
  let renamed = with_graph case graph (alpha_binding names (U.to_json case.binding)) in
  let proposed = Q.of_json (edit ["nodes"] (fun rows -> arr (List.map (fun row ->
    replace "actual" (rename names (get "actual" row)) row) (Json.array rows))) (Q.to_json case.proposed)) in
  let renamed_result = check {renamed with proposed} in
  let report = Check.report renamed_result in
  ignore (accepted "complete independently preserved alpha-renaming" renamed_result);
  require (Json.equal (get "carrier_projections" report) (arr (expected_carriers case.state_reading))) "Graph alpha rename changed molecular ownership";
  require (Json.equal (get "link_projections" report) (alpha_links names (expected_links case.state_reading))) "Graph alpha rename lost exact cross-links";
  result_failed "old mapping cannot authorize renamed graph" "ordered_total_actual_node_bijection" (check renamed);
  let swapped = edit ["wires"] (fun rows -> let rows=Json.array rows in arr (List.nth rows 1::List.hd rows::List.tl (List.tl rows))) (I.to_json case.graph) in
  let reordered = with_graph case swapped (U.to_json case.binding) in
  result_failed "semantically preserved alternate wire listing" "complete_ordered_wiring" (check reordered);
  let reordered_input = with_graph case (edit ["inputs"] (fun rows -> arr (List.rev (Json.array rows))) (I.to_json case.graph)) (U.to_json case.binding) in
  result_failed "preserved alternate input listing" "complete_ordered_external_inputs" (check reordered_input);
  let renamed_group = with_graph case (put ["atomic_groups";"0";"id"] (str "another.atomic.group") (I.to_json case.graph)) (U.to_json case.binding) in
  result_failed "preserved group alias cannot replace original ownership" "complete_ordered_atomic_groups" (check renamed_group);
  let original = RR.of_json (put ["budgets";"max_work"] (Json.int 99999999) (RR.to_json case.request)) in
  result_failed "private implementation belongs to complete original request" "unchanged_original_realization_request" (check {case with request=original});
  let synthetic_original = RR.of_json (put ["document";"implementations";"id"] (str "synthetic.inner.catalog") (RR.to_json case.request)) in
  result_failed "synthetic replacement catalog cannot authorize original source" "unchanged_original_realization_request"
    (check {case with request=synthetic_original})
let model_control case change_capacity =
  let raw = RR.to_json case.request in
  let original_model = model (get "implementation_library" raw) "exclusion.primitive.attempt" in
  let changed = if change_capacity then put ["body";"configuration";"capacity"] (Json.int 9) original_model else original_model in
  let changed = changed |> put ["identity";"id"] (str (if change_capacity then "fixture.attempt.capacity9" else "fixture.attempt.alias"))
    |> put ["identity";"content_fingerprint"] (str (Canonical.fingerprint (get "body" changed)))
    |> replace "configuration_digest" (str (Canonical.fingerprint (at ["body";"configuration"] changed))) in
  let raw = raw |> edit ["implementation_library";"models"] (fun rows -> arr (Json.array rows@[changed]))
    |> edit ["catalog_bindings";"0";"models"] (fun rows -> arr (Json.array rows@[get "identity" changed])) in
  let request = RR.of_json raw in
  let models = RR.implementation_library request in
  let graph = I.to_json case.graph |> put ["authority";"library_digest"] (str (I.library_digest models))
    |> edit ["nodes"] (fun rows -> arr (List.map (fun row -> if get "id" row=str "attempt" then
      row |> replace "model" (get "identity" changed) |> replace "configuration_digest" (get "configuration_digest" changed) else row) (Json.array rows))) in
  let graph = I.of_json ~library:models graph in
  let preserved = preserved request case.behavior graph case.binding case.limits in
  let components = L.of_json ~library:models (L.to_json case.components) in
  let assembly_rule = A.of_json ~components (A.to_json case.assembly_rule) in
  let result = check {case with request;graph;preserved;components;assembly_rule} in
  result_failed "authorized preserved alternate model cannot stand in for original component" "primitive_identity:driver/attempt" result;
  if change_capacity then (
    result_failed "conservative capacity change still changes exact configured model" "configuration_identity:driver/attempt" result;
    result_failed "full configuration authority retained" "complete_primitive_configuration_replication:driver/attempt" result)
let material_controls case =
  let raw = K.to_json case.content in
  let negative label mutate =
    let content = K.of_json (mutate raw) in
    material_failed label (check {case with content}) in
  negative "same-length base substitution" (change_molecule (replace "sequence"
    (str (if case.state_reading then "AGCAUGGCUUAAGGAAAA" else "ACAUGGCUUAAGGAAAA"))));
  negative "same peptide is not exact root reproduction" (fun raw -> raw
    |> put ["values";"0";"sequence"] (str (if case.state_reading then "CGCAUGGCCUAAGGAAAA" else "CCAUGGCCUAAGGAAAA"))
    |> change_molecule (replace "sequence" (str (if case.state_reading then "CGCAUGGCCUAAGGAAAA" else "CCAUGGCCUAAGGAAAA"))));
  negative "complete chemistry is not sequence-only" (change_molecule (put ["chemistry";"cap";"identity";"accession"] (str "foreign_cap")));
  negative "exact feature provenance" (change_molecule (put ["features";"0";"provenance";"locator"] (str "changed feature authority")));
  negative "full assembly origin" (change_molecule (put ["assembly";"0";"id"] (str "foreign.origin")));
  negative "source segment identity" (put ["values";"0";"segments";"0";"source_id"] (str "another.root"));
  negative "intermediate value retained" (replace "values" (arr []));
  negative "missing delivered inventory" (replace "inventory" Json.Null);
  negative "candidate cannot grant its own authority" (replace "authority_fingerprint" (str (String.make 64 '0')));
  let rule_raw = A.to_json case.assembly_rule in
  let port_path = ["body";"material_authority";"template";"steps";"0";"ports";"0"] in
  (* These are coherent new original transition declarations, accepted by the
     shape decoder. The independent leaf must enforce the exact selected-root
     composition relation rather than accepting their self-reported fates. *)
  let wrong_fate = with_rule case (put (port_path@["feature_transition";"dispositions";"0";"decision"]) (str "partial") rule_raw) in
  result_failed "repinned feature fate" "exact_feature_projection:driver/cds"
    (check {wrong_fate with content=K.of_json (rebind_content (A.material_authority wrong_fate.assembly_rule) raw)});
  let chemistry_path = port_path@["chemistry_transition"] in
  let dispositions = Json.array (at (chemistry_path@["dispositions"]) rule_raw) in
  let leader = if case.state_reading then "leader_B" else "leader_A" in
  let cap_index = let rec find i = function
    | row::_ when get "source_id" row=str leader && get "component" row=str "cap" -> i
    | _::rest -> find (i+1) rest | [] -> failwith "Literal leader cap fate absent" in find 0 dispositions in
  let changed_fate = with_rule case (put (chemistry_path@["dispositions";string_of_int cap_index;"decision"]) (str "declared_replacement") rule_raw) in
  result_failed "repinned chemistry fate" "exact_chemistry_disposition:decision/cap"
    (check {changed_fate with content=K.of_json (rebind_content (A.material_authority changed_fate.assembly_rule) raw)});
  let foreign_cap = with_rule case (rule_raw
    |> put (chemistry_path@["output";"cap";"identity";"accession"]) (str "foreign_cap")
    |> put ["body";"material_authority";"members";"0";"chemistry";"cap";"identity";"accession"] (str "foreign_cap")) in
  let content = raw |> put ["values";"0";"chemistry";"cap";"identity";"accession"] (str "foreign_cap")
    |> change_molecule (put ["chemistry";"cap";"identity";"accession"] (str "foreign_cap"))
    |> rebind_content (A.material_authority foreign_cap.assembly_rule) |> K.of_json in
  let result = check {foreign_cap with content} in
  result_failed "self-consistent output chemistry still differs from component" "exact_chemistry_projection:decision/cap" result;
  require (get "structural_outcome" (get "structure" (Check.report result))=str "pass")
    "Nominally complete foreign cap should distinguish composition from mRNA structure"
let original_relation_controls case =
  let raw = A.to_json case.assembly_rule in
  let reject label message mutate = rejected ~message "policy_component_assembly_rule" label (fun () ->
    A.of_json ~components:case.components (repin (mutate raw))) in
  reject "cross-link scope cannot be silently rebroadcast"
    "Assembly link kind has the wrong component ownership or scope relation."
    (put ["body";"links";"1";"scope"] (str "immutable_executor_broadcast"));
  reject "join offset is original base authority"
    "Assembly join must place the complete decision root before the complete driver at their adjacent offset."
    (put ["body";"join";"offset"] (Json.int 1));
  reject "carrier cannot refer to an invented join"
    "Assembly link carrier names a different authorized join."
    (put ["body";"link_carriers";"1";"join"] (str "another.join"));
  let driver = List.nth (items "components" (L.to_json case.components)) 1 in
  let changed_driver = driver |> put ["body";"carriers";"7";"sites";"0"] (site "driver_body" "utr3" 9 11) |> repin in
  let library_raw = edit ["components";"1"] (fun _ -> changed_driver) (L.to_json case.components) in
  let components = L.of_json ~library:(RR.implementation_library case.request) library_raw in
  rejected ~message:"Assembly component is absent from the exact original component library." "policy_component_assembly_rule" "changed full carrier body cannot satisfy old rule pin" (fun () -> A.of_json ~components raw);
  let changed_rule = raw |> put ["body";"components";"1";"component"] (get "identity" changed_driver) |> repin in
  let assembly_rule = A.of_json ~components changed_rule in
  result_failed "different admitted carrier premise invalidates old proposal" "original_assembly_rule_pin"
    (check {case with components;assembly_rule});
  let proposed = Q.of_json (proposal case.state_reading assembly_rule) in
  let changed = check {case with components;assembly_rule;proposed} in
  ignore (accepted "explicit coherent alternative carrier premise" changed);
  let report = Check.report changed in
  require (get "link_projections" report<>arr (expected_links case.state_reading)) "New original carrier premise was ignored";
  require (get "candidate_fingerprint" report=str (K.fingerprint case.content)) "Carrier premise test unexpectedly changed exact RNA"
let resource_controls case =
  rejected "policy_component_assembly_resource_limit" "zero work has no acceptance" (fun () ->
    Check.check ~maximum:0 ~original:case.request ~components:case.components ~rule:case.assembly_rule
      ~implementation:case.preserved ~proposed:case.proposed ~candidate:case.content ());
  rejected "policy_component_assembly_resource_limit" "work ceiling cannot expand" (fun () ->
    Check.check ~maximum:100000001 ~original:case.request ~components:case.components ~rule:case.assembly_rule
      ~implementation:case.preserved ~proposed:case.proposed ~candidate:case.content ());
  let budget = W.create ~profile:"literal.parent" ~error_code:"literal_parent_limit" ~maximum:1 () in
  rejected "literal_parent_limit" "enclosing work exhaustion" (fun () -> Check.check ~parent:budget
    ~original:case.request ~components:case.components ~rule:case.assembly_rule
    ~implementation:case.preserved ~proposed:case.proposed ~candidate:case.content ());
  require (W.exhausted budget) "Nested resource exhaustion was not sticky";
  let report = Check.report (check case) in
  let forged = report |> replace "artifact" (str "accepted") |> replace "export" (str "accepted")
    |> replace "catalog_authorization" (str "pass") in
  require (not (Json.equal forged (Check.report (check case)))) "Untrusted report rewrote fresh checker authority";
  rejected "missing_field" "receipt cannot be deserialized as a proposal" (fun () -> Q.of_json forged)
let producer_controls case other =
  let library = RR.implementation_library case.request in
  let admitted = RA.admit ~request:case.request ~behavior:case.behavior in
  let lowered = GL.lower ~admitted ~library in
  let original_graph = I.to_json lowered.implementation and original_binding = U.to_json lowered.binding in
  let arranged = CL.arrange ~library ~rule:case.assembly_rule lowered in
  (* The reviewed literal allocation fixes expected names independently of the
     matching producer. Only typed node references change; enums and input IDs
     retain their original spelling. *)
  let names = List.map (fun (node:I.node) ->
    let actual = fst (List.find (fun (_,local) -> local=node.node_id) (allocation case.state_reading)) in
    node.node_id,actual) (I.nodes case.graph) in
  let expected_graph = alpha_graph names (I.to_json case.graph) in
  let expected_binding = alpha_binding names (U.to_json case.binding) in
  let expected_proposal = edit ["nodes"] (fun rows -> arr (List.map (fun row ->
    replace "actual" (rename names (get "actual" row)) row) (Json.array rows))) (Q.to_json case.proposed) in
  require (Json.equal (I.to_json arranged.implementation) expected_graph)
    "Actual component producer differs from the complete literal ordered union";
  require (Json.equal (U.to_json arranged.binding) expected_binding &&
    Json.equal (Q.to_json arranged.assembly) expected_proposal)
    "Actual producer lost exact source occurrences, node ownership or input correspondence";
  require (Json.equal (get "authority" (I.to_json arranged.implementation)) (get "authority" original_graph) &&
    Json.equal (get "occurrences" (I.to_json arranged.implementation)) (get "occurrences" original_graph))
    "Arrangement replaced original source authority or occurrence inventory";
  require (Json.equal original_graph (I.to_json lowered.implementation) &&
    Json.equal original_binding (U.to_json lowered.binding)) "Arrangement mutated its source-produced inputs";
  let again = CL.arrange ~library ~rule:case.assembly_rule lowered in
  require (Json.equal (I.to_json arranged.implementation) (I.to_json again.implementation) &&
    Json.equal (U.to_json arranged.binding) (U.to_json again.binding) &&
    Json.equal (Q.to_json arranged.assembly) (Q.to_json again.assembly))
    "Fresh component arrangement is not deterministic";
  let authority = A.material_authority case.assembly_rule in
  let content = CP.construct_template ~member_order:["payload"] (PM.template authority) in
  require (Json.equal (K.to_json content) (K.to_json case.content))
    "Actual construction differs from independently authored full17/18-base material";
  let content_again = CP.construct_template ~member_order:["payload"] (PM.template authority) in
  require (Json.equal (K.to_json content_again) (K.to_json content)) "Fresh construction changed exact derived material";
  let preserved = preserved case.request case.behavior arranged.implementation arranged.binding case.limits in
  let produced_case = {case with graph=arranged.implementation;binding=arranged.binding;
    proposed=arranged.assembly;preserved;content} in
  let result = check produced_case in
  let checked = accepted "actual source-to-component arrangement and construction" result in
  require (Json.equal (RR.to_json (Check.original checked)) (RR.to_json case.request) &&
    A.fingerprint (Check.rule checked)=A.fingerprint case.assembly_rule &&
    L.fingerprint (Check.components checked)=L.fingerprint case.components)
    "Fresh produced assembly replaced untouched original request/component/rule authority";
  let report = Check.report result in
  require (Json.equal (get "carrier_projections" report) (arr (expected_carriers case.state_reading)) &&
    Json.equal (get "link_projections" report) (alpha_links names (expected_links case.state_reading)))
    "Produced assembly omitted a literal local carrier or original cross-link projection";
  require (Json.equal report (Check.report (check produced_case))) "Fresh produced assembly check changed complete evidence";
  rejected ~message:"The original component union and source-produced graph need equal bounded primitive inventories."
    "policy_component_lowering_unsupported" "different source family cannot borrow an original rule"
    (fun () -> CL.arrange ~library ~rule:other.assembly_rule lowered)
let run first second =
  let a = make_case first false and b = make_case second true in
  require (C.fingerprint (A.component a.assembly_rule A.Driver)=C.fingerprint (A.component b.assembly_rule A.Driver))
    "Reusable original driver changed across independently preserved source families";
  let report_a = positive a and report_b = positive b in
  require (get "candidate_fingerprint" report_a<>get "candidate_fingerprint" report_b) "Distinct full original roots collapsed material identity";
  List.iter (fun case -> proposal_controls case;graph_controls case;material_controls case;original_relation_controls case) [a;b];
  model_control a false;model_control a true;
  material_failed "A exact artifact cannot transfer to B original" (check {b with content=a.content});
  result_failed "A preservation cannot transfer to B source" "unchanged_original_realization_request" (check {b with preserved=a.preserved});
  resource_controls a;
  producer_controls a b;producer_controls b a;
  Printf.printf "component assembly checker: %d independent checks passed\n" !checks
let () =
  Printexc.register_printer (function
    | Diagnostic.Error value -> Some (Printf.sprintf "Diagnostic.Error(code=%s, path=%s, message=%s)"
        value.code (Option.value ~default:"<none>" value.path) value.message)
    | _ -> None);
  require (Array.length Sys.argv=3) "Supply full independent exclusion and state-reading material request fixtures";
  run (read Sys.argv.(1)) (read Sys.argv.(2))
