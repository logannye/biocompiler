open Bioc_wire
module I = Bioc_domain.Policy_implementation
module C = Bioc_domain.Policy_component_material
module L = Bioc_domain.Policy_component_library
module P = Bioc_domain.Pinned_identity
module A = Bioc_domain.Policy_component_assembly_rule
module CT = Bioc_domain.Construction
module G = Bioc_domain.Molecule_coordinates
module H = Bioc_domain.Molecule_chemistry
module M = Bioc_domain.Molecular_record
module N = Bioc_domain.Molecule
module T = Bioc_domain.Molecular_transition
module PT = Bioc_domain.Payload_template
module PS = Bioc_domain.Payload_structure
module PM = Bioc_domain.Policy_mrna_structure

(* These complete source literals are copied from the independently authored
   local-material controls, not produced from a graph or assembled molecule.
   Global rule ordering, material joins and carrier expectations below are
   independently declared and do not use decoder output as expected data. *)
let checks = ref 0
let require condition message = incr checks; if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let items key value = Json.array (get key value)
let replace key replacement value = obj (List.map (fun (name, item) ->
  name, (if key = name then replacement else item)) (Json.object_fields value))
let change index transform values = List.mapi (fun i value -> if index = i then transform value else value) values
let add key item value = obj ((key, item) :: Json.object_fields value)
let endpoint node port = obj ["node", str node; "port", str port]
let wire source output target input = obj ["producer", endpoint source output; "consumer", endpoint target input]
let boundary id direction signal_type node port = obj ["id", str id;
  "direction", str direction; "signal_type", str signal_type; "endpoint", endpoint node port]
let external_slot id kind node port = obj ["id", str id; "kind", str kind; "consumer", endpoint node port]
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size = in_channel_length channel in
    require (size <= 4_000_000) "Original fixture exceeds bounded input";
    Json.parse (really_input_string channel size))

(* Only original model declarations are borrowed. Node, wire, interface, group
   and output expectations below are hand-authored, never candidate-derived. *)
let original_library fixture = get "implementation_library" (get "implementation_request" (get "request" fixture))
let model library id = match List.find_opt (fun value ->
    get "id" (get "identity" value) = str id) (items "models" library) with
  | Some value -> value
  | None -> failwith ("Original model absent: " ^ id)
let node library id model_id = obj ["id", str id; "model", model library model_id]
let fragment id nodes wires boundary_ports external_slots atomic_groups semantic_exports = obj [
  "schema_version", str "biocompiler.policy_component_fragment.v0.1";
  "profile", str "biocompiler.policy_exact_fragment.v0.1";
  "primitive_profile", str "biocompiler.policy_truth_primitives.v0.1";
  "observable_profile", str "biocompiler.policy_truth_observables.v0.1";
  "phase_profile", str "biocompiler.policy_primitive_execution.v0.1";
  "id", str id; "version", str "1";
  "slot_layout", obj ["id", str "encounters"; "slots", Json.int 2];
  "nodes", arr nodes; "wires", arr wires; "boundary_ports", arr boundary_ports;
  "external_slots", arr external_slots; "atomic_groups", arr atomic_groups;
  "semantic_exports", arr semantic_exports]

let driver library = fragment "fixture.driver"
  [node library "product" "exclusion.primitive.product";
   node library "attempt" "exclusion.primitive.attempt"] []
  [boundary "product" "output" "product_symbol" "product" "out";
   boundary "request" "input" "effect_request" "attempt" "request";
   boundary "authorization" "input" "truth_value" "attempt" "authorization"]
  [external_slot "feedback" "feedback" "attempt" "feedback"] []
  [endpoint "product" "out"; endpoint "attempt" "events"; endpoint "attempt" "snapshot"]

let decision library state_reading =
  let specifications = [
    "evidence", "exclusion.primitive.evidence";
    "select_edge", "exclusion.primitive.edge"; "not", "exclusion.primitive.not";
    "exclude_edge", "exclusion.primitive.edge";
    "true", "exclusion.primitive.true"; "false", "exclusion.primitive.false";
    "select_gate", "exclusion.primitive.gate"; "exclude_gate", "exclusion.primitive.gate";
    "arbiter", "exclusion.primitive.arbiter";
    "select_commit", "exclusion.primitive.select_commit";
    "exclude_commit", "exclusion.primitive.exclude_commit";
    "selected", "exclusion.primitive.register"; "excluded", "exclusion.primitive.register"] @
    (if state_reading then ["selected_not", "exclusion.primitive.not"; "select_guard", "state.primitive.all2"] else []) in
  let nodes = List.map (fun (id, model_id) -> node library id model_id) specifications in
  let guard_node, guard_port = if state_reading then "select_guard", "out" else "evidence", "value" in
  let false_node, false_port = if state_reading then "selected", "value" else "false", "out" in
  let wires = [
    wire "evidence" "value" "select_edge" "in";
    wire "evidence" "value" "not" "in";
    wire "not" "out" "exclude_edge" "in";
    wire "select_edge" "events" "select_gate" "on";
    wire "exclude_edge" "events" "exclude_gate" "on";
    wire guard_node guard_port "select_gate" "guard";
    wire "not" "out" "exclude_gate" "guard";
    wire "select_gate" "candidate" "arbiter" "in0";
    wire "arbiter" "out0" "select_commit" "grant";
    wire "true" "out" "select_commit" "value0";
    wire "select_commit" "write0" "selected" "write0";
    wire false_node false_port "select_commit" "value1";
    wire "select_commit" "write1" "excluded" "write0";
    wire "exclude_gate" "candidate" "arbiter" "in1";
    wire "arbiter" "out1" "exclude_commit" "grant";
    wire "false" "out" "exclude_commit" "value0";
    wire "exclude_commit" "write0" "selected" "write1";
    wire "true" "out" "exclude_commit" "value1";
    wire "exclude_commit" "write1" "excluded" "write1"] @
    (if state_reading then [wire "selected" "value" "selected_not" "in";
       wire "evidence" "value" "select_guard" "in0";
       wire "selected_not" "out" "select_guard" "in1"] else []) in
  let exports = [endpoint "evidence" "value"; endpoint "evidence" "updated";
    endpoint "select_edge" "events"; endpoint "not" "out"; endpoint "exclude_edge" "events";
    endpoint "true" "out"; endpoint "false" "out";
    endpoint "select_gate" "candidate"; endpoint "exclude_gate" "candidate";
    endpoint "arbiter" "out0"; endpoint "arbiter" "out1";
    endpoint "select_commit" "write0"; endpoint "select_commit" "write1"; endpoint "select_commit" "request0";
    endpoint "exclude_commit" "write0"; endpoint "exclude_commit" "write1";
    endpoint "selected" "value"; endpoint "excluded" "value"] @
    (if state_reading then [endpoint "selected_not" "out"; endpoint "select_guard" "out"] else []) in
  fragment (if state_reading then "fixture.decision.state" else "fixture.decision.exclusion") nodes wires
    [boundary "product" "input" "product_symbol" "select_commit" "product0";
     boundary "request" "output" "effect_request" "select_commit" "request0";
     boundary "authorization" "output" "truth_value" guard_node guard_port]
    [external_slot "condition" "evidence" "evidence" "samples"]
    [obj ["id", str "exclusive_selection"; "arbiter", str "arbiter";
       "commits", arr [str "select_commit"; str "exclude_commit"]]] exports

(* Original artificial material declarations. No finished RNA or producer output
   supplies these roots, sites, geometry, chemistry or expected product. *)
let pin kind id digest = obj ["schema_version", str "biocompiler.component_identity.v0.1";
  "kind", str kind; "id", str id; "version", str "1"; "content_fingerprint", str digest]
let notice = str "Artificial local component fixture; supplied software premise, not empirical evidence."
let provenance = obj ["schema_version", str "biocompiler.molecular_declaration_provenance.v0.1";
  "status", str "declared";
  "authority", arr [pin "source" "fixture.local-material.notice" (Canonical.fingerprint notice)];
  "locator", str "independent native test literal"; "reason", notice]
let span first last = obj ["schema_version", str "biocompiler.molecule_index_span.v0.1";
  "start", Json.int first; "end", Json.int last]
let path space first last = obj ["schema_version", str "biocompiler.molecule_coordinate_path.v0.1";
  "space_id", str space; "spans", arr [span first last]; "strand", str "+"]
let space id length = obj ["schema_version", str "biocompiler.molecule_coordinate_space.v0.1";
  "id", str id; "alphabet", str "RNA"; "axis", str "5prime_to_3prime";
  "topology", str "linear"; "length", Json.int length]
let chemical accession = obj ["schema_version", str "biocompiler.chemical_identity.v0.1";
  "namespace", str "software_fixture.chemical"; "accession", str accession; "version", str "1"]
let claim accession = obj ["schema_version", str "biocompiler.chemistry_claim.v0.1";
  "status", str "declared"; "identity", chemical accession; "provenance", provenance]
let chemistry frame driver_root =
  let tail = obj ["schema_version", str "biocompiler.tail_declaration.v0.1";
    "status", str "declared";
    "placement", str (if driver_root then "represented_terminal" else "absent");
    "length", obj ["schema_version", str "biocompiler.tail_length.v0.1";
      "mode", str "exact"; "exact", Json.int (if driver_root then 4 else 0);
      "lower", Json.Null; "upper", Json.Null];
    "path", (if driver_root then path frame 11 15 else Json.Null); "provenance", provenance] in
  obj ["schema_version", str "biocompiler.molecule_chemistry.v0.1";
    "cap", claim "artificial_cap"; "start_end", claim "hydroxyl";
    "finish_end", claim "hydroxyl"; "modifications", arr [];
    "modification_inventory_status", str "declared";
    "modification_inventory_provenance", provenance; "terminal_tail", tail]
let feature frame id kind first last reading_frame =
  obj ["schema_version", str "biocompiler.molecule_feature.v0.1"; "id", str id;
    "kind", str kind; "path", path frame first last; "provenance", provenance;
    "reading_frame", reading_frame]
let root id sequence driver_root =
  let frame = id ^ ".frame" and length = String.length sequence in
  let geometry = space frame length in
  let features = if driver_root then [
      feature frame "cds" "coding_sequence" 0 9 (Json.int 0);
      feature frame "poly_a" "poly_a_tail" 11 15 Json.Null;
      feature frame "utr3" "three_prime_utr" 9 11 Json.Null]
    else [feature frame "utr5" "five_prime_utr" 0 length Json.Null] in
  obj ["schema_version", str "biocompiler.construction_root_source.v0.1";
    "id", str id; "provenance", provenance;
    "molecule", obj ["schema_version", str "biocompiler.circuit_molecule.v0.1";
      "id", str (id ^ ".molecule"); "form", str "primary_rna";
      "space", geometry; "sequence", str sequence; "sequence_extent", str "complete";
      "coding_status", str (if driver_root then "coding" else "noncoding");
      "assembly", arr [obj ["schema_version", str "biocompiler.assembly_origin.v0.1";
        "id", str (id ^ ".self"); "destination", path frame 0 length;
        "source_space", geometry; "source_path", path frame 0 length; "provenance", provenance]];
      "features", arr features; "chemistry", chemistry frame driver_root; "provenance", provenance]]
let expected_product = obj [
  "identity", pin "source" "payload.artificial.product"
    "c7434883f345ffc2100dd9e3750afbbee436ba7535cf5fb26b9be706ce413c9b";
  "sequence", str "MA";
  "translation_policy", obj ["schema_version", str "biocompiler.translation_policy.v0.1";
    "profile", str "ordinary_cds"; "genetic_code", str "ncbi_standard_v1"; "recodings", arr []];
  "provenance", provenance]
let target kind id = obj ["kind", str kind; "id", str id]
let indexed kind index = obj ["kind", str kind; "index", Json.int index]
let triple id = [target "primitive" id; target "configuration" id; target "replication" id]
let driver_targets = List.concat [triple "product"; triple "attempt"] @ [
  target "external_slot" "feedback"; target "boundary_port" "product";
  target "boundary_port" "request"; target "boundary_port" "authorization";
  indexed "semantic_export" 0; indexed "semantic_export" 1; indexed "semantic_export" 2;
  obj ["kind", str "slot_layout"]]
let decision_targets state_reading =
  List.concat_map triple (["evidence"; "select_edge"; "not"; "exclude_edge"; "true"; "false";
    "select_gate"; "exclude_gate"; "arbiter"; "select_commit"; "exclude_commit"; "selected"; "excluded"] @
    if state_reading then ["selected_not"; "select_guard"] else []) @
  List.map (indexed "local_wire") ([0;1;2;3;4;5;6;7;8;9;10;11;12;13;14;15;16;17;18] @
    if state_reading then [19;20;21] else []) @
  [target "external_slot" "condition"; target "boundary_port" "product";
   target "boundary_port" "request"; target "boundary_port" "authorization";
   target "atomic_group" "exclusive_selection"] @
  List.map (indexed "semantic_export") ([0;1;2;3;4;5;6;7;8;9;10;11;12;13;14;15;16;17] @
    if state_reading then [18;19] else []) @ [obj ["kind", str "slot_layout"]]
let site root_id feature_id first last = obj ["root", str root_id;
  "feature", str feature_id; "path", path (root_id ^ ".frame") first last]
let driver_carriers = List.mapi (fun index disposition ->
  let material_site = if index < 3 || index = 7 || index = 10 then site "driver_body" "cds" 0 9
    else site "driver_body" "utr3" 9 11 in
  obj ["target", disposition; "sites", arr [material_site]]) driver_targets
let input id external_slot = obj ["kind", str "input"; "id", str id; "external_slot", str external_slot]
let capacity id owner_kind owner unit scope minimum = obj ["kind", str "capacity";
  "id", str id; "owner", obj ["kind", str owner_kind; "id", str owner];
  "unit", str unit; "scope", str scope; "minimum", Json.int minimum]
let driver_prerequisites = [input "feedback_input" "feedback";
  capacity "feedback_rows" "external_slot" "feedback" "input_rows_per_tick" "per_executor" 1;
  capacity "active" "node" "attempt" "active_attempt_records" "per_encounter_slot" 8;
  capacity "retained" "node" "attempt" "retained_correlation_records" "per_executor" 1;
  capacity "attempt_timers" "node" "attempt" "timer_cells" "per_encounter_slot" 8]
let decision_prerequisites = [input "condition_input" "condition";
  capacity "condition_rows" "external_slot" "condition" "input_rows_per_tick" "per_encounter_slot" 1;
  capacity "samples" "node" "evidence" "evidence_records" "per_encounter_slot" 1;
  capacity "freshness_timer" "node" "evidence" "timer_cells" "per_encounter_slot" 1;
  capacity "select_edge_memory" "node" "select_edge" "edge_history_cells" "per_encounter_slot" 1;
  capacity "exclude_edge_memory" "node" "exclude_edge" "edge_history_cells" "per_encounter_slot" 1;
  capacity "selected_memory" "node" "selected" "truth_cells" "per_encounter_slot" 1;
  capacity "excluded_memory" "node" "excluded" "truth_cells" "per_encounter_slot" 1]
let component id fragment local_root carriers products prerequisites =
  let body = obj ["fragment", fragment; "root", local_root; "carriers", arr carriers;
    "products", arr products; "provider_requirements", arr prerequisites] in
  obj ["schema_version", str "biocompiler.policy_component_material.v0.1";
    "profile", str "biocompiler.policy_exact_local_material.v0.1";
    "identity", pin "model" id (Canonical.fingerprint body); "body", body]
let driver_component library = component "fixture.driver.material" (driver library)
  (root "driver_body" "AUGGCUUAAGGAAAA" true) driver_carriers
  [obj ["node", str "product"; "symbol", str "fixture.product.alpha";
    "root", str "driver_body"; "cds_feature", str "cds"; "expected", expected_product]] driver_prerequisites
let decision_component library state_reading =
  let id, sequence = if state_reading then "leader_B", "CGC" else "leader_A", "CC" in
  let carriers = List.map (fun disposition -> obj ["target", disposition;
    "sites", arr [site id "utr5" 0 (String.length sequence)]]) (decision_targets state_reading) in
  component (if state_reading then "fixture.decision.state.material" else "fixture.decision.exclusion.material")
    (decision library state_reading) (root id sequence false) carriers [] decision_prerequisites

let rec at keys raw = match keys with [] -> raw | key :: tail ->
  at tail (match raw with Json.Array values -> List.nth values (int_of_string key) | _ -> get key raw)
let rec edit keys transform raw = match keys with [] -> transform raw | key :: tail ->
  match raw with Json.Array values -> arr (change (int_of_string key) (edit tail transform) values)
  | _ -> replace key (edit tail transform (get key raw)) raw
let put keys value = edit keys (fun _ -> value)
let repin raw = edit ["identity"; "content_fingerprint"]
  (fun _ -> str (Canonical.fingerprint (get "body" raw))) raw
let rejected ?message code label run =
  incr checks;
  match run () with
  | _ -> failwith ("Mutation accepted: " ^ label)
  | exception Diagnostic.Error value ->
      if value.code <> code || (match message with None -> false | Some expected -> value.message <> expected)
      then failwith ("Wrong rejection: " ^ label ^ ": " ^ value.code ^ ": " ^ value.message)

let library components = obj ["schema_version", str "biocompiler.policy_component_library.v0.1";
  "profile", str "biocompiler.policy_exact_component_library.v0.1"; "components", arr components]

(* One supplied concatenate premise. Leaf constructors only encode these
   independently declared selections/fates; no material producer is imported. *)
let material_authority state_reading =
  let leader, sequence, offset = if state_reading then "leader_B", "CGC", 3 else "leader_A", "CC", 2 in
  let p = M.Provenance.of_json provenance in
  let output_chemistry frame = chemistry frame true
    |> put ["terminal_tail"; "path"] (path frame (offset + 11) (offset + 15)) in
  let facets = ["cap"; "start_end"; "finish_end"; "terminal_tail"; "modification_inventory"] in
  let dispositions source copied = List.map (fun facet ->
    let component = T.Component.of_string facet and carry = List.mem facet copied in
    T.Chemistry_disposition.make ~source_id:source ~component
      ~decision:(if carry then T.Chemistry_disposition.Mapped_copy else T.Chemistry_disposition.Not_carried)
      ~destination_components:(if carry then [component] else []) ~provenance:p) facets in
  let chemistry_transition = T.Chemistry.make ~mode:T.Chemistry.Explicit_output
    ~output:(Some (H.of_json (output_chemistry "join.frame")))
    ~dispositions:(dispositions leader ["cap"; "start_end"; "modification_inventory"] @
      dispositions "driver_body" ["finish_end"; "terminal_tail"; "modification_inventory"])
    ~provenance:p in
  let placed source id kind first last reading_frame =
    T.Feature_disposition.make ~source_id:source ~feature_id:id ~decision:T.Feature_disposition.Exact
      ~outputs:[N.Feature.of_json (feature "join.frame" id kind first last reading_frame)] ~provenance:p in
  let feature_transition = T.Feature.make ~dispositions:[
    placed leader "utr5" "five_prime_utr" 0 offset Json.Null;
    placed "driver_body" "cds" "coding_sequence" offset (offset + 9) (Json.int 0);
    placed "driver_body" "utr3" "three_prime_utr" (offset + 9) (offset + 11) Json.Null;
    placed "driver_body" "poly_a" "poly_a_tail" (offset + 11) (offset + 15) Json.Null]
    ~added:[] ~provenance:p in
  let whole id = CT.Selection.make (CT.Value_ref.make ~kind:CT.Value_ref.Root ~id) in
  let step = CT.Transform_step.make ~id:"join" ~operation:(CT.Operation.make
    (CT.Operation.Concatenate [whole leader; whole "driver_body"]))
    ~ports:[CT.Product_port.make ~id:"joined" ~space_id:"join.frame" ~alphabet:G.Rna ~topology:G.Linear
      ~chemistry_transition ~feature_transition] ~assumptions:[] ~provenance:p in
  let output = CT.Output_member.make ~id:"payload" ~value:(CT.Value_ref.make ~kind:CT.Value_ref.Product ~id:"joined")
    ~space_id:"payload.frame" ~form:N.Delivered_rna ~sequence_extent:H.Complete ~coding_status:N.Coding ~provenance:p in
  let requirement = CT.Member_requirement.make ~id:"payload" ~category:CT.Member_requirement.Payload
    ~subject:(CT.Member_requirement.Materialized "payload")
    ~roles:[CT.Role.make ~id:"payload.role" ~role:"payload" ~purpose:N.Role.Requested_payload ~compartment:"cytoplasm"] in
  let structure = PS.make ~member_id:"payload" ~form:PS.Delivered_rna ~topology:G.Linear
    ~regions:(List.map (fun (id,kind) -> PS.Region.make ~feature_id:id ~kind)
      ["utr5","five_prime_utr"; "cds","coding_sequence"; "utr3","three_prime_utr"; "poly_a","poly_a_tail"])
    ~provenance:p in
  let template = PT.make ~id:(if state_reading then "fixture.join.B" else "fixture.join.A")
    ~sources:[CT.Root_source.of_json (root leader sequence false);
              CT.Root_source.of_json (root "driver_body" "AUGGCUUAAGGAAAA" true)]
    ~steps:[step] ~output_members:[output] ~requirements:[requirement] ~payload_structures:[structure] () in
  obj ["schema_version", str "biocompiler.policy_mrna_structure_authority.v0.1";
    "profile", str "biocompiler.policy_mrna_completeness.v0.1"; "template", PT.to_json template;
    "member_order", arr [str "payload"]; "members", arr [obj ["id",str "payload";
      "regions",obj ["utr5",str "utr5";"cds",str "cds";"utr3",str "utr3";"poly_a",str "poly_a"];
      "product",expected_product;"chemistry",output_chemistry "payload.frame"]]]

let nr slot node = obj ["slot",str slot;"node",str node]
let er slot node port = obj ["slot",str slot;"node",str node;"port",str port]
let br slot boundary = obj ["slot",str slot;"boundary",str boundary]
let local_wire index = obj ["kind",str "local";"slot",str "decision";"index",Json.int index]
let link_wire id = obj ["kind",str "link";"id",str id]
let global_nodes state_reading =
  List.map (nr "decision") ["evidence";"select_edge";"not";"exclude_edge";"true";"false"] @
  [nr "driver" "product"] @
  List.map (nr "decision") ["select_gate";"exclude_gate";"arbiter";"select_commit";"exclude_commit";"selected";"excluded"] @
  [nr "driver" "attempt"] @
  (if state_reading then [nr "decision" "selected_not";nr "decision" "select_guard"] else [])
let global_wires state_reading =
  List.map local_wire [0;1;2;3;4;5;6;7;8;9;10;11;12;13;14;15;16;17;18] @
  List.map link_wire ["product";"request";"authorization"] @
  (if state_reading then List.map local_wire [19;20;21] else [])
let global_exports state_reading =
  List.map (fun (node,port) -> er "decision" node port)
    ["evidence","value";"evidence","updated";"select_edge","events";"not","out";
     "exclude_edge","events";"true","out";"false","out"] @
  [er "driver" "product" "out"] @
  List.map (fun (node,port) -> er "decision" node port)
    ["select_gate","candidate";"exclude_gate","candidate";"arbiter","out0";"arbiter","out1";
     "select_commit","write0";"select_commit","write1";"select_commit","request0";
     "exclude_commit","write0";"exclude_commit","write1";"selected","value";"excluded","value"] @
  [er "driver" "attempt" "events";er "driver" "attempt" "snapshot"] @
  (if state_reading then [er "decision" "selected_not" "out";er "decision" "select_guard" "out"] else [])
let rule state_reading decision_raw driver_raw =
  let link id source destination signal_type scope = obj ["id",str id;
    "producer",br source id;"consumer",br destination id;"signal_type",str signal_type;"scope",str scope] in
  let body = obj [
    "primitive_profile",str "biocompiler.policy_truth_primitives.v0.1";
    "observable_profile",str "biocompiler.policy_truth_observables.v0.1";
    "phase_profile",str "biocompiler.policy_primitive_execution.v0.1";
    "transport_profile",str "biocompiler.policy_identity_transport.v0.1";
    "slot_layout",obj ["id",str "encounters";"slots",Json.int 2];
    "components",arr [obj ["slot",str "decision";"component",get "identity" decision_raw];
                      obj ["slot",str "driver";"component",get "identity" driver_raw]];
    "links",arr [link "product" "driver" "decision" "product_symbol" "immutable_executor_broadcast";
                  link "request" "decision" "driver" "effect_request" "same_encounter_slot";
                  link "authorization" "decision" "driver" "truth_value" "same_encounter_slot"];
    "node_order",arr (global_nodes state_reading);"wire_order",arr (global_wires state_reading);
    "input_order",arr [obj ["slot",str "decision";"external_slot",str "condition";"id",str "condition"];
                       obj ["slot",str "driver";"external_slot",str "feedback";"id",str "feedback"]];
    "group_order",arr [obj ["slot",str "decision";"group",str "exclusive_selection"]];
    "export_order",arr (global_exports state_reading);
    "root_bindings",arr [obj ["slot",str "decision";"source",str (if state_reading then "leader_B" else "leader_A")];
                         obj ["slot",str "driver";"source",str "driver_body"]];
    "join",obj ["id",str "leader_to_driver";"step",str "join";"port",str "joined";
      "left",str "decision";"right",str "driver";"offset",Json.int (if state_reading then 3 else 2)];
    "link_carriers",arr (List.map (fun id -> obj ["link",str id;"producer_site",Json.int 0;
      "consumer_site",Json.int 0;"join",str "leader_to_driver"]) ["product";"request";"authorization"]);
    "material_authority",material_authority state_reading] in
  obj ["schema_version",str "biocompiler.policy_component_assembly_rule.v0.1";
    "profile",str "biocompiler.policy_exact_component_assembly.v0.1";
    "identity",pin "model" (if state_reading then "fixture.rule.B" else "fixture.rule.A") (Canonical.fingerprint body);
    "body",body]

let slot_name = function A.Decision -> "decision" | A.Driver -> "driver"
let node_json (value:A.node_ref) = nr (slot_name value.slot) value.node_id
let endpoint_json (value:A.endpoint_ref) = er (slot_name value.node.slot) value.node.node_id value.port_id
let kind_name = function A.Product -> "product" | A.Request -> "request" | A.Authorization -> "authorization"
let wire_json = function
  | A.Local_wire {slot;index} -> obj ["kind",str "local";"slot",str (slot_name slot);"index",Json.int index]
  | A.Cross_link kind -> link_wire (kind_name kind)
let swap first second raw = match raw with
  | Json.Array values -> arr (List.mapi (fun index value ->
      if index = first then List.nth values second else if index = second then List.nth values first else value) values)
  | _ -> failwith "Mutation requires a declared ordered inventory"
let without key value = obj (List.remove_assoc key (Json.object_fields value))

let run first second =
  let model_a_raw = original_library first and model_b_raw = original_library second in
  let model_a = I.library_of_json model_a_raw and model_b = I.library_of_json model_b_raw in
  let driver_a = driver_component model_a_raw and driver_b = driver_component model_b_raw in
  let decision_a = decision_component model_a_raw false and decision_b = decision_component model_b_raw true in
  let library_a = L.of_json ~library:model_a (library [decision_a;driver_a])
  and library_b = L.of_json ~library:model_b (library [decision_b;driver_b]) in
  let raw_a = rule false decision_a driver_a and raw_b = rule true decision_b driver_b in
  List.iter (fun raw -> ignore (PM.of_json (at ["body";"material_authority"] raw))) [raw_a;raw_b];
  let a = A.of_json ~components:library_a raw_a and b = A.of_json ~components:library_b raw_b in
  require (Json.equal driver_a driver_b) "Shared complete driver input changed across families";
  require (C.fingerprint (A.component a A.Driver) = C.fingerprint (A.component b A.Driver))
    "Identical driver acquired source-dependent identity";
  require (A.model_library_digest a = I.library_digest model_a &&
           A.model_library_digest b = I.library_digest model_b &&
           A.component_library_digest a = L.fingerprint library_a &&
           A.component_library_digest b = L.fingerprint library_b)
    "Original component/model decoding contexts were lost";
  List.iter (fun (raw,value,state_reading,node_count,wire_count,export_count,offset,leader,leader_sequence) ->
    require (Json.equal raw (A.to_json value) && A.fingerprint value = Canonical.fingerprint raw)
      "Assembly rule did not preserve the complete supplied original";
    require (P.content_fingerprint (A.identity value) = Canonical.fingerprint (get "body" raw))
      "Rule Model identity does not bind the full material and ordered signal premise";
    require (List.map node_json (A.node_order value) = global_nodes state_reading &&
      List.length (A.node_order value) = node_count) "Literal global node interleaving differs";
    require (List.map wire_json (A.wire_order value) = global_wires state_reading &&
      List.length (A.wire_order value) = wire_count) "Literal global local/link wire order differs";
    require (List.map endpoint_json (A.export_order value) = global_exports state_reading &&
      List.length (A.export_order value) = export_count) "All outputs must retain the literal global order";
    require (List.map (fun (link:A.link) -> kind_name link.kind) (A.links value) =
      ["product";"request";"authorization"]) "Link ownership/order changed";
    require (List.map (fun (input:A.input_ref) -> input.input_id) (A.input_order value) = ["condition";"feedback"])
      "External evidence/feedback input identities or order changed";
    require (List.map (fun (group:A.group_ref) -> slot_name group.slot,group.group_id) (A.group_order value) =
      ["decision","exclusive_selection"]) "Atomic action ownership split or duplicated";
    require ((A.join value).offset = offset && (A.join value).left = A.Decision && (A.join value).right = A.Driver)
      "Declared adjacent placement changed";
    require (List.map (fun (binding:A.root_binding) -> slot_name binding.slot,binding.source_id)
      (A.root_bindings value) = ["decision",leader;"driver","driver_body"])
      "Local material root ownership changed";
    let authority = A.material_authority value in
    require (PM.member_order authority = ["payload"] && List.length (PM.members authority) = 1)
      "Original one-member product authority changed";
    require (List.map (fun source -> CT.Root_source.id source,N.sequence (CT.Root_source.molecule source))
      (PT.sources (PM.template authority)) = ["driver_body","AUGGCUUAAGGAAAA";leader,leader_sequence])
      "Exact local source bodies were replaced by a final output or same-peptide substitute";
    require (List.for_all (fun (carrier:A.link_carrier) -> carrier.producer_site = 0 &&
      carrier.consumer_site = 0 && carrier.join_id = "leader_to_driver") (A.link_carriers value))
      "Literal link carrier site/join relation changed")
    [raw_a,a,false,15,22,21,2,"leader_A","CC";
     raw_b,b,true,17,25,23,3,"leader_B","CGC"];
  require (List.map wire_json (List.filteri (fun index _ -> index >= 19) (A.wire_order b)) =
    [link_wire "product";link_wire "request";link_wire "authorization";local_wire 19;local_wire 20;local_wire 21])
    "B links must be interleaved before the three final internal state-dependent wires";
  (* The rule is original ordering authority. A different legal interleaving is
     a different declaration, not an automatic source/candidate correspondence. *)
  let other_interleaving = raw_b |> put ["body";"wire_order"]
    (arr (List.map local_wire [0;1;2;3;4;5;6;7;8;9;10;11;12;13;14;15;16;17;18;19;20;21] @
          List.map link_wire ["product";"request";"authorization"])) |> repin in
  let reordered = A.of_json ~components:library_b other_interleaving in
  require (A.fingerprint reordered <> A.fingerprint b &&
    Json.equal (A.to_json reordered) other_interleaving) "Changed legal global order was erased from original identity";
  let reject ?message label raw = rejected ?message "policy_component_assembly_rule" label
    (fun () -> A.of_json ~components:library_a raw) in
  let changed ?message label keys value = reject ?message label (raw_a |> put keys value |> repin) in
  reject ~message:"Original assembly identity must pin its complete supplied body."
    "Rule body mutated without refreshing original identity"
    (put ["body";"join";"offset"] (Json.int 3) raw_a);
  rejected ~message:"Assembly component is absent from the exact original component library."
    "policy_component_assembly_rule" "Family A selection under unrelated complete B library"
    (fun () -> A.of_json ~components:library_b raw_a);
  changed ~message:"Assembly component is absent from the exact original component library."
    "Stale complete component pin" ["body";"components";"0";"component";"content_fingerprint"] (str (String.make 64 '0'));
  changed "Duplicate component owner" ["body";"components";"1";"slot"] (str "decision");
  changed "Unmodeled helper component slot" ["body";"components";"1";"slot"] (str "helper");
  changed ~message:"Assembly link direction or full signal type differs from its actual ports."
    "Wrong cross-link signal" ["body";"links";"0";"signal_type"] (str "truth_value");
  changed ~message:"Assembly link kind has the wrong component ownership or scope relation."
    "Executor product is not encounter-scoped" ["body";"links";"0";"scope"] (str "same_encounter_slot");
  changed ~message:"Assembly link kind has the wrong component ownership or scope relation."
    "Encounter request cannot claim executor broadcast" ["body";"links";"1";"scope"] (str "immutable_executor_broadcast");
  reject ~message:"Assembly link direction or full signal type differs from its actual ports." "Direction-reversed request"
    (raw_a |> put ["body";"links";"1";"producer"] (br "driver" "request")
           |> put ["body";"links";"1";"consumer"] (br "decision" "request") |> repin);
  changed "Wrong exact authorization boundary" ["body";"links";"2";"producer"] (br "decision" "request");
  changed "Endpoint alias is not the named original boundary" ["body";"links";"2";"producer";"boundary"] (str "evidence");
  changed "Unknown same-slot conversion" ["body";"transport_profile"] (str "biocompiler.policy_buffered_transport.v0.1");
  changed "Lost layout identity" ["body";"slot_layout";"id"] (str "foreign-layout");
  changed "Different slot cardinality" ["body";"slot_layout";"slots"] (Json.int 1);
  List.iter (fun key ->
    let rows = items key (get "body" raw_a) in
    changed ("Missing complete " ^ key) ["body";key] (arr (List.tl rows));
    let duplicate = if List.length rows = 1 then List.hd rows :: rows else
      change (List.length rows - 1) (fun _ -> List.hd rows) rows in
    changed ("Duplicate complete " ^ key) ["body";key] (arr duplicate))
    ["components";"links";"node_order";"wire_order";"input_order";"group_order";"export_order";
     "root_bindings";"link_carriers"];
  reject "Changed local node order" (raw_a |> edit ["body";"node_order"] (swap 0 1) |> repin);
  reject "Changed local wire order" (raw_a |> edit ["body";"wire_order"] (swap 0 1) |> repin);
  reject "Changed local output order" (raw_a |> edit ["body";"export_order"] (swap 0 1) |> repin);
  changed "Duplicate external global identity" ["body";"input_order";"1";"id"] (str "condition");
  changed "Cross-component atomic ownership" ["body";"group_order";"0";"slot"] (str "driver");
  changed "Wrong bound source body" ["body";"root_bindings";"0";"source"] (str "driver_body");
  changed "Join offset uses a different root length" ["body";"join";"offset"] (Json.int 3);
  changed "Join points to absent transform" ["body";"join";"step"] (str "absent");
  changed "Join points to absent product port" ["body";"join";"port"] (str "absent");
  changed "Join orientation is reversed" ["body";"join";"left"] (str "driver");
  changed "Absent producer carrier site" ["body";"link_carriers";"0";"producer_site"] (Json.int 1);
  changed "Absent consumer carrier site" ["body";"link_carriers";"1";"consumer_site"] (Json.int 1);
  changed "Carrier refers to unrelated join" ["body";"link_carriers";"2";"join"] (str "other-join");
  (* These changed originals are valid PM declarations before rule-specific
     checks; a stale component premise must not gain new authority from rehashing. *)
  let material_changed message label change_material =
    let candidate = edit ["body";"material_authority"] change_material raw_a |> repin in
    ignore (PM.of_json (at ["body";"material_authority"] candidate));
    reject ~message label candidate in
  let root_mismatch = "Assembly template root differs from the exact selected component root beyond its declared source-ID rename." in
  material_changed root_mismatch "Synonymous full root body still differs from selected component"
    (put ["template";"sources";"0";"molecule";"sequence"] (str "AUGGCCUAAGGAAAA"));
  material_changed root_mismatch "Same bases with changed nominal root cap are a different original"
    (put ["template";"sources";"0";"molecule";"chemistry";"cap";"identity";"accession"] (str "different_cap"));
  material_changed root_mismatch "Same root sequence but altered feature authority"
    (put ["template";"sources";"0";"molecule";"features";"0";"kind"] (str "uninterpreted_region"));
  material_changed "Assembly construction must concatenate the two complete bound roots in declared order without slicing."
    "Reversed whole-root construction order"
    (edit ["template";"steps";"0";"operation";"inputs"] (swap 0 1));
  material_changed "Assembly expected product differs from the complete selected driver product."
    "Equal peptide does not replace the complete original product provenance"
    (put ["members";"0";"product";"provenance";"reason"] (str "Different supplied product authority"));
  material_changed "Assembly feature transition must account for every original root feature exactly once without added annotations."
    "Missing original feature disposition"
    (edit ["template";"steps";"0";"ports";"0";"feature_transition";"dispositions"]
      (fun value -> arr (List.tl (Json.array value))));
  material_changed "Assembly chemistry transition must account for all ten original root facets exactly once."
    "Missing original chemistry facet disposition"
    (edit ["template";"steps";"0";"ports";"0";"chemistry_transition";"dispositions"]
      (fun value -> arr (List.tl (Json.array value))));
  (* A valid newly pinned B component can expose evidence at the boundary, but
     it cannot make that endpoint the actual state-dependent gate guard. *)
  let wrong_guard_component = decision_b
    |> put ["body";"fragment";"boundary_ports";"2";"endpoint"] (endpoint "evidence" "value") |> repin in
  ignore (C.of_json ~library:model_b wrong_guard_component);
  let wrong_guard_library = L.of_json ~library:model_b (library [wrong_guard_component;driver_b]) in
  let wrong_guard_rule = rule true wrong_guard_component driver_b in
  rejected ~message:"Assembly authorization must retain the initiating gate's actual guard-producing endpoint."
    "policy_component_assembly_rule" "B boundary guard differs from the actual initiating gate guard"
    (fun () -> A.of_json ~components:wrong_guard_library wrong_guard_rule);
  (* Full component identity, including carrier authority, remains original.
     A current-model and current-root library is insufficient for an old pin. *)
  let changed_carrier_component = driver_a
    |> put ["body";"carriers";"7";"sites";"0"] (site "driver_body" "utr3" 9 11) |> repin in
  ignore (C.of_json ~library:model_a changed_carrier_component);
  let changed_carrier_library = L.of_json ~library:model_a (library [decision_a;changed_carrier_component]) in
  rejected ~message:"Assembly component is absent from the exact original component library."
    "policy_component_assembly_rule" "Same roots/models with changed product-boundary carrier cannot satisfy old component pin"
    (fun () -> A.of_json ~components:changed_carrier_library raw_a);
  List.iter (fun key ->
    rejected "unknown_field" ("Closed rule field: " ^ key) (fun () ->
      A.of_json ~components:library_a (add key Json.Null raw_a))) ["candidate";"source";"provider"];
  rejected "policy_component_assembly_rule" "Raw float before material/model traversal" (fun () ->
    A.of_json ~components:library_a (put ["body";"join";"offset"] (Json.Float 2.) raw_a));
  let rec cyclic = Json.Array [cyclic] in
  rejected "molecular_cycle" "Cyclic original rule" (fun () -> A.of_json ~components:library_a cyclic)

let () =
  try
    require (Array.length Sys.argv = 3) "Expected the two original A/B model-library fixtures";
    run (read Sys.argv.(1)) (read Sys.argv.(2));
    Printf.printf "component assembly rule: %d literal/source controls passed\n" !checks
  with Diagnostic.Error value ->
    Printf.eprintf "Diagnostic.Error(code=%s,path=%s,message=%s)\n" value.code
      (match value.path with None -> "<none>" | Some path -> path) value.message;
    exit 1
