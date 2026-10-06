open Bioc_wire
module I = Policy_implementation
module C = Policy_component_material
module L = Policy_component_library
module F = Policy_component_fragment
module M = Molecular_record
module P = Pinned_identity
module N = Molecule
module G = Molecule_coordinates
module H = Molecule_chemistry
module R = Molecular_recoding
module K = Construction
module T = Payload_template
module PM = Policy_mrna_structure
module MT = Molecular_transition

let schema_version = "biocompiler.policy_component_assembly_rule.v0.1"
let profile = "biocompiler.policy_exact_component_assembly.v0.1"
let transport_profile = "biocompiler.policy_identity_transport.v0.1"
type slot = Decision | Driver
type component_selection = { slot:slot; identity:P.t }
type node_ref = { slot:slot; node_id:string }
type endpoint_ref = { node:node_ref; port_id:string }
type boundary_ref = { slot:slot; boundary_id:string }
type link_kind = Product | Request | Authorization
type scope_relation = Same_encounter_slot | Immutable_executor_broadcast
type link = { kind:link_kind; producer:boundary_ref; consumer:boundary_ref;
  signal_type:I.signal_type; scope:scope_relation }
type wire_ref = Local_wire of {slot:slot; index:int} | Cross_link of link_kind
type input_ref = { slot:slot; external_slot:string; input_id:string }
type group_ref = { slot:slot; group_id:string }
type root_binding = { slot:slot; source_id:string }
type join = { join_id:string; step_id:string; port_id:string; left:slot; right:slot; offset:int }
type link_carrier = { kind:link_kind; producer_site:int; consumer_site:int; join_id:string }
type t = {
  identity_value:P.t; selections:component_selection list; selected:(slot * C.t) list;
  library_digest:string; model_digest:string; layout_value:F.slot_layout;
  link_values:link list; node_values:node_ref list; wire_values:wire_ref list;
  input_values:input_ref list; group_values:group_ref list; export_values:endpoint_ref list;
  root_values:root_binding list; join_value:join; carrier_values:link_carrier list;
  material_value:PM.t;
}
let str value = Json.String value
let obj values = Json.Object values
let arr encode values = Json.Array (List.map encode values)
let get key value = Json.field key (Json.object_fields value)
let exact keys value = Json.exact_fields keys (Json.object_fields value)
let fail message = Diagnostic.fail "policy_component_assembly_rule" message
let require condition message = Diagnostic.require condition "policy_component_assembly_rule" message
let equal left right = Canonical.encode left = Canonical.encode right
let name raw = let value = Json.name raw in
  require (String.length value <= 128) "Assembly rule local name exceeds its byte bound."; value
let rows maximum = M.array ~maximum
let index maximum = M.index ~maximum
let same_inventory actual expected =
  List.length actual = List.length expected && List.sort Stdlib.compare actual = List.sort Stdlib.compare expected
let unique message values = require (List.length values = List.length (List.sort_uniq Stdlib.compare values)) message
let preflight raw =
  M.check_resources raw;
  let rec no_float = function
    | Json.Float _ -> fail "Raw floats cannot enter an original assembly rule."
    | Json.Array values -> List.iter no_float values
    | Json.Object fields -> List.iter (fun (_,value) -> no_float value) fields
    | _ -> () in
  no_float raw
let slot_name = function Decision -> "decision" | Driver -> "driver"
let slot_of_json raw = match Json.string raw with
  | "decision" -> Decision | "driver" -> Driver | _ -> fail "Unknown component slot."
let kind_name = function Product -> "product" | Request -> "request" | Authorization -> "authorization"
let kind_of_json raw = match Json.string raw with
  | "product" -> Product | "request" -> Request | "authorization" -> Authorization
  | _ -> fail "Unknown assembly link kind."
let scope_name = function Same_encounter_slot -> "same_encounter_slot" | Immutable_executor_broadcast -> "immutable_executor_broadcast"
let scope_of_json raw = match Json.string raw with
  | "same_encounter_slot" -> Same_encounter_slot | "immutable_executor_broadcast" -> Immutable_executor_broadcast
  | _ -> fail "Unknown assembly scope relation."
let signal_name = function
  | I.Truth_value -> "truth_value" | I.Product_symbol -> "product_symbol"
  | I.Evidence_batch -> "evidence_batch" | I.Feedback_batch -> "feedback_batch"
  | I.Event_batch -> "event_batch" | I.Activation_batch -> "activation_batch"
  | I.Truth_write -> "truth_write" | I.Effect_request -> "effect_request" | I.Attempt_snapshot -> "attempt_snapshot"
let signal_of_json raw = match Json.string raw with
  | "truth_value" -> I.Truth_value | "product_symbol" -> I.Product_symbol
  | "evidence_batch" -> I.Evidence_batch | "feedback_batch" -> I.Feedback_batch
  | "event_batch" -> I.Event_batch | "activation_batch" -> I.Activation_batch
  | "truth_write" -> I.Truth_write | "effect_request" -> I.Effect_request | "attempt_snapshot" -> I.Attempt_snapshot
  | _ -> fail "Unknown assembly signal type."
let component value slot = List.assoc slot value.selected
let fragment value slot = C.fragment (component value slot)
let node value (reference:node_ref) =
  match List.find_opt (fun (node:F.node) -> node.node_id = reference.node_id) (F.nodes (fragment value reference.slot)) with
  | Some node -> node | None -> fail "Assembly reference names an absent component node."
let boundary value (reference:boundary_ref) =
  match List.find_opt (fun (port:F.boundary_port) -> port.boundary_id = reference.boundary_id)
    (F.boundary_ports (fragment value reference.slot)) with
  | Some port -> port | None -> fail "Assembly reference names an absent component boundary."
let endpoint slot (endpoint:I.endpoint) = {node={slot;node_id=endpoint.node_id};port_id=endpoint.port_id}
let boundary_endpoint value (reference:boundary_ref) = endpoint reference.slot (boundary value reference).endpoint
let selected_root value slot = C.root (component value slot)
let root_binding value slot = List.find (fun (row:root_binding) -> row.slot = slot) value.root_values
let link value kind = List.find (fun (row:link) -> row.kind = kind) value.link_values

let selection_json (value:component_selection) = obj ["slot",str (slot_name value.slot);"component",P.to_json value.identity]
let node_json (value:node_ref) = obj ["slot",str (slot_name value.slot);"node",str value.node_id]
let node_of_json raw = exact ["slot";"node"] raw; {slot=slot_of_json (get "slot" raw);node_id=name (get "node" raw)}
let boundary_json (value:boundary_ref) = obj ["slot",str (slot_name value.slot);"boundary",str value.boundary_id]
let boundary_of_json raw = exact ["slot";"boundary"] raw;
  {slot=slot_of_json (get "slot" raw);boundary_id=name (get "boundary" raw)}
let link_json (value:link) = obj ["id",str (kind_name value.kind);"producer",boundary_json value.producer;
  "consumer",boundary_json value.consumer;"signal_type",str (signal_name value.signal_type);"scope",str (scope_name value.scope)]
let link_of_json raw = exact ["id";"producer";"consumer";"signal_type";"scope"] raw;
  {kind=kind_of_json (get "id" raw);producer=boundary_of_json (get "producer" raw);
   consumer=boundary_of_json (get "consumer" raw);signal_type=signal_of_json (get "signal_type" raw);scope=scope_of_json (get "scope" raw)}
let wire_json = function
  | Local_wire {slot;index} -> obj ["kind",str "local";"slot",str (slot_name slot);"index",Json.int index]
  | Cross_link kind -> obj ["kind",str "link";"id",str (kind_name kind)]
let wire_of_json raw = match Json.string (get "kind" raw) with
  | "local" -> exact ["kind";"slot";"index"] raw; Local_wire {slot=slot_of_json (get "slot" raw);index=index 2047 (get "index" raw)}
  | "link" -> exact ["kind";"id"] raw; Cross_link (kind_of_json (get "id" raw))
  | _ -> fail "Unknown global wire reference."
let input_json (value:input_ref) = obj ["slot",str (slot_name value.slot);"external_slot",str value.external_slot;"id",str value.input_id]
let input_of_json raw = exact ["slot";"external_slot";"id"] raw;
  {slot=slot_of_json (get "slot" raw);external_slot=name (get "external_slot" raw);input_id=name (get "id" raw)}
let group_json (value:group_ref) = obj ["slot",str (slot_name value.slot);"group",str value.group_id]
let group_of_json raw = exact ["slot";"group"] raw; {slot=slot_of_json (get "slot" raw);group_id=name (get "group" raw)}
let endpoint_json (value:endpoint_ref) = obj ["slot",str (slot_name value.node.slot);"node",str value.node.node_id;"port",str value.port_id]
let endpoint_of_json raw = exact ["slot";"node";"port"] raw;
  {node={slot=slot_of_json (get "slot" raw);node_id=name (get "node" raw)};port_id=name (get "port" raw)}
let root_json (value:root_binding) = obj ["slot",str (slot_name value.slot);"source",str value.source_id]
let root_of_json raw = exact ["slot";"source"] raw; {slot=slot_of_json (get "slot" raw);source_id=name (get "source" raw)}
let join_json (value:join) = obj ["id",str value.join_id;"step",str value.step_id;"port",str value.port_id;
  "left",str (slot_name value.left);"right",str (slot_name value.right);"offset",Json.int value.offset]
let join_of_json raw = exact ["id";"step";"port";"left";"right";"offset"] raw;
  {join_id=name (get "id" raw);step_id=name (get "step" raw);port_id=name (get "port" raw);
   left=slot_of_json (get "left" raw);right=slot_of_json (get "right" raw);offset=index M.max_residues (get "offset" raw)}
let carrier_json (value:link_carrier) = obj ["link",str (kind_name value.kind);"producer_site",Json.int value.producer_site;
  "consumer_site",Json.int value.consumer_site;"join",str value.join_id]
let carrier_of_json raw = exact ["link";"producer_site";"consumer_site";"join"] raw;
  {kind=kind_of_json (get "link" raw);producer_site=index 3 (get "producer_site" raw);
   consumer_site=index 3 (get "consumer_site" raw);join_id=name (get "join" raw)}
let body_json value = obj ["primitive_profile",str I.profile;"observable_profile",str I.observable_profile;
  "phase_profile",str F.phase_profile;"transport_profile",str transport_profile;
  "slot_layout",obj ["id",str value.layout_value.layout_id;"slots",Json.int value.layout_value.slots];
  "components",arr selection_json value.selections;"links",arr link_json value.link_values;
  "node_order",arr node_json value.node_values;"wire_order",arr wire_json value.wire_values;
  "input_order",arr input_json value.input_values;"group_order",arr group_json value.group_values;
  "export_order",arr endpoint_json value.export_values;"root_bindings",arr root_json value.root_values;
  "join",join_json value.join_value;"link_carriers",arr carrier_json value.carrier_values;
  "material_authority",PM.to_json value.material_value]
let to_json value = obj ["schema_version",str schema_version;"profile",str profile;
  "identity",P.to_json value.identity_value;"body",body_json value]

let check_orders value =
  let expected_nodes = List.concat_map (fun slot -> List.map (fun (node:F.node) ->
    {slot;node_id=node.node_id}) (F.nodes (fragment value slot))) [Decision;Driver] in
  require (same_inventory value.node_values expected_nodes) "Global node order must own every selected local node exactly once.";
  List.iter (fun slot ->
    require (List.filter (fun (node:node_ref) -> node.slot=slot) value.node_values =
      List.filter (fun (node:node_ref) -> node.slot=slot) expected_nodes)
      "Global node order changes a component's local node order.";
    let actual = List.filter_map (function Local_wire row when row.slot=slot -> Some row.index | _ -> None) value.wire_values in
    require (actual = List.mapi (fun index _ -> index) (F.wires (fragment value slot)))
      "Global wire order must preserve every local wire once in local order.";
    let inputs = List.filter_map (fun (row:input_ref) -> if row.slot=slot then Some row.external_slot else None) value.input_values in
    require (inputs = List.map (fun (row:F.external_slot) -> row.slot_id) (F.external_slots (fragment value slot)))
      "Global input order must preserve every local external slot once.";
    let groups = List.filter_map (fun (row:group_ref) -> if row.slot=slot then Some row.group_id else None) value.group_values in
    require (groups = List.map (fun (row:I.atomic_group) -> row.group_id) (F.atomic_groups (fragment value slot)))
      "Global group order must preserve every complete local group once.") [Decision;Driver];
  require (List.filter_map (function Cross_link kind -> Some kind | _ -> None) value.wire_values = [Product;Request;Authorization])
    "Global wire order must preserve each original link once in link order.";
  unique "Global external input identities are duplicated." (List.map (fun (row:input_ref) -> row.input_id) value.input_values);
  unique "Global atomic group identities are duplicated." (List.map (fun (row:group_ref) -> row.group_id) value.group_values);
  let exports = List.concat_map (fun (reference:node_ref) ->
    List.filter_map (fun (port:I.port) -> if port.direction=I.Output then Some {node=reference;port_id=port.port_id} else None)
      (I.ports (node value reference).model.primitive)) value.node_values in
  require (value.export_values=exports) "Global exports must preserve every output in global node and primitive port order."

let check_links value =
  require (List.map (fun (row:link) -> row.kind) value.link_values = [Product;Request;Authorization])
    "Assembly requires exactly product, request and authorization links in order.";
  let boundaries = List.concat_map (fun slot -> List.map (fun (port:F.boundary_port) ->
    {slot;boundary_id=port.boundary_id}) (F.boundary_ports (fragment value slot))) [Decision;Driver] in
  require (same_inventory (List.concat_map (fun (row:link) -> [row.producer;row.consumer]) value.link_values) boundaries)
    "Assembly links must consume every selected boundary exactly once.";
  List.iter (fun (row:link) ->
    let output=boundary value row.producer and input=boundary value row.consumer in
    require (output.direction=I.Output && input.direction=I.Input && output.signal_type=row.signal_type && input.signal_type=row.signal_type)
      "Assembly link direction or full signal type differs from its actual ports.";
    let wanted_producer,wanted_consumer,wanted_signal,wanted_scope = match row.kind with
      | Product -> Driver,Decision,I.Product_symbol,Immutable_executor_broadcast
      | Request -> Decision,Driver,I.Effect_request,Same_encounter_slot
      | Authorization -> Decision,Driver,I.Truth_value,Same_encounter_slot in
    require (row.producer.slot=wanted_producer && row.consumer.slot=wanted_consumer &&
      row.signal_type=wanted_signal && row.scope=wanted_scope) "Assembly link kind has the wrong component ownership or scope relation.";
    match row.scope with
    | Same_encounter_slot -> require (match output.replication,input.replication with
        | I.Encounter_slots left,I.Encounter_slots right -> left.layout_id=right.layout_id && left.slots=right.slots
        | _ -> false) "Assembly link must preserve the same encounter layout and slot identity."
    | Immutable_executor_broadcast ->
        let producer=node value (boundary_endpoint value row.producer).node in
        require (output.replication=I.Executor && (match input.replication with I.Encounter_slots _ -> true | _ -> false) &&
          (match producer.model.primitive with I.Product_constant _ -> true | _ -> false))
          "Assembly product broadcast requires its actual immutable executor product constant.") value.link_values

let check_driver_and_authorization value =
  let driver=fragment value Driver and decision=fragment value Decision in
  let product,attempt = match F.nodes driver with
    | [product;attempt] when (match product.model.primitive,attempt.model.primitive with I.Product_constant _,I.Attempt_bank _ -> true | _ -> false) -> product,attempt
    | _ -> fail "Assembly driver requires exactly one product constant then one attempt bank." in
  require (F.wires driver=[] && F.atomic_groups driver=[] && List.for_all (fun (row:F.node) ->
    match row.model.primitive with I.Product_constant _|I.Attempt_bank _ -> false | _ -> true) (F.nodes decision))
    "Assembly cannot add another driver, product, attempt owner or driver-internal helper.";
  let product_link=link value Product and request_link=link value Request and authorization_link=link value Authorization in
  require (boundary_endpoint value product_link.producer = {node={slot=Driver;node_id=product.node_id};port_id="out"} &&
    boundary_endpoint value request_link.consumer = {node={slot=Driver;node_id=attempt.node_id};port_id="request"} &&
    boundary_endpoint value authorization_link.consumer = {node={slot=Driver;node_id=attempt.node_id};port_id="authorization"})
    "Assembly links do not name the driver's actual product, request and authorization ports.";
  (match F.external_slots driver,F.external_slots decision with
   | [feedback],[evidence] -> require (feedback.input_kind=I.Feedback_input &&
       feedback.consumer={I.node_id=attempt.node_id;port_id="feedback"} && evidence.input_kind=I.Evidence_input)
       "Assembly external slots require decision evidence and driver feedback."
   | _ -> fail "Assembly requires exactly one decision evidence slot and one driver feedback slot.");
  let request=boundary_endpoint value request_link.producer in
  let commit=node value request.node in
  require (request.port_id="request0" && (match commit.model.primitive with I.Atomic_commit {requests=1;_} -> true | _ -> false))
    "Assembly request must come from one actual atomic request output.";
  let group = match List.find_opt (fun (group:I.atomic_group) -> List.mem commit.node_id group.commits) (F.atomic_groups decision) with
    | Some group -> group | None -> fail "Assembly initiating commit lacks its original atomic group." in
  let rec position count = function
    | [] -> fail "Assembly initiating commit is absent from its atomic group."
    | id::_ when id=commit.node_id -> count | _::tail -> position (count+1) tail in
  let lane=position 0 group.commits in
  let incoming target = match List.find_opt (fun (wire:I.wire) -> wire.consumer=target) (F.wires decision) with
    | Some wire -> wire.producer | None -> fail "Assembly initiating guard route is not a complete local wire path." in
  let gate_endpoint=incoming {I.node_id=group.arbiter;port_id="in"^string_of_int lane} in
  let gate=node value {slot=Decision;node_id=gate_endpoint.node_id} in
  require (gate.model.primitive=I.Activation_gate && gate_endpoint.port_id="candidate")
    "Assembly initiating arbiter lane must retain its actual activation gate.";
  let guard=incoming {I.node_id=gate.node_id;port_id="guard"} in
  require (boundary_endpoint value authorization_link.producer = endpoint Decision guard)
    "Assembly authorization must retain the initiating gate's actual guard-producing endpoint."

let expected_product_json (value:PM.product) = obj ["identity",P.to_json value.identity;"sequence",str value.sequence;
  "translation_policy",R.Translation_policy.to_json value.translation_policy;"provenance",M.Provenance.to_json value.provenance]
let renamed_root source root = match K.Root_source.to_json root with
  | Json.Object fields -> obj (List.map (fun (key,value) -> key,if key="id" then str source else value) fields)
  | _ -> assert false
let check_material value =
  require (List.map (fun (row:root_binding) -> row.slot) value.root_values=[Decision;Driver])
    "Assembly root bindings must contain decision then driver exactly once.";
  unique "Assembly template root identities are duplicated." (List.map (fun (row:root_binding) -> row.source_id) value.root_values);
  let template=PM.template value.material_value in
  let sources=T.sources template in
  require (same_inventory (List.map K.Root_source.id sources) (List.map (fun (row:root_binding) -> row.source_id) value.root_values))
    "Assembly template must retain exactly the selected bound roots.";
  List.iter (fun (row:root_binding) ->
    let actual=List.find (fun source -> K.Root_source.id source=row.source_id) sources in
    require (equal (K.Root_source.to_json actual) (renamed_root row.source_id (selected_root value row.slot)))
      "Assembly template root differs from the exact selected component root beyond its declared source-ID rename.") value.root_values;
  let join=value.join_value in
  require (join.left=Decision && join.right=Driver && join.offset=String.length (N.sequence (K.Root_source.molecule (selected_root value Decision))))
    "Assembly join must place the complete decision root before the complete driver at their adjacent offset.";
  let step,port=match T.steps template with
    | [step] when K.Transform_step.id step=join.step_id ->
        (match K.Transform_step.ports step with [port] when K.Product_port.id port=join.port_id -> step,port
         | _ -> fail "Assembly join requires the sole declared product port.")
    | _ -> fail "Assembly join requires exactly one declared construction step." in
  let selected selection slot = K.Selection.path selection=None &&
    K.Value_ref.kind (K.Selection.value selection)=K.Value_ref.Root &&
    K.Value_ref.id (K.Selection.value selection)=(root_binding value slot).source_id in
  require (match K.Operation.specification (K.Transform_step.operation step) with
    | K.Operation.Concatenate [left;right] -> selected left Decision && selected right Driver | _ -> false)
    "Assembly construction must concatenate the two complete bound roots in declared order without slicing.";
  require (K.Product_port.alphabet port=G.Rna && K.Product_port.topology port=G.Linear &&
    T.complex_members template=[] && T.amounts template=[])
    "Assembly supports one linear RNA product without complexes or amount declarations.";
  let member,expected=match T.output_members template,PM.members value.material_value with
    | [member],[expected] -> member,expected | _ -> fail "Assembly requires exactly one original output member and mRNA expectation." in
  require (PM.member_order value.material_value=[K.Output_member.id member] && expected.id=K.Output_member.id member &&
    K.Value_ref.kind (K.Output_member.value member)=K.Value_ref.Product && K.Value_ref.id (K.Output_member.value member)=join.port_id &&
    K.Output_member.form member=N.Delivered_rna && K.Output_member.sequence_extent member=H.Complete && K.Output_member.coding_status member=N.Coding)
    "Assembly member must retain the sole complete coding RNA product and exact mRNA member identity.";
  require (match T.requirements template with
    | [requirement] -> K.Member_requirement.category requirement=K.Member_requirement.Payload &&
        K.Member_requirement.member_id requirement=Some (K.Output_member.id member)
    | _ -> false) "Assembly must retain one payload member requirement without a helper or concrete provider.";
  (match C.products (component value Driver),C.products (component value Decision) with
   | [product],[] -> require (equal (expected_product_json product.expected) (expected_product_json expected.product))
       "Assembly expected product differs from the complete selected driver product."
   | _ -> fail "Assembly requires exactly one driver product and no decision product.");
  let features=K.Product_port.feature_transition port in
  let expected_features=List.concat_map (fun source -> List.map (fun feature -> K.Root_source.id source,N.Feature.id feature)
    (N.features (K.Root_source.molecule source))) sources in
  require (MT.Feature.added features=[] && same_inventory
    (List.map (fun row -> MT.Feature_disposition.source_id row,MT.Feature_disposition.feature_id row) (MT.Feature.dispositions features)) expected_features)
    "Assembly feature transition must account for every original root feature exactly once without added annotations.";
  let chemistry=K.Product_port.chemistry_transition port in
  require (MT.Chemistry.mode chemistry=MT.Chemistry.Explicit_output)
    "Assembly concatenation requires explicit complete output chemistry.";
  List.iter (fun source -> let chemistry=N.chemistry (K.Root_source.molecule source) in
    require (H.modifications chemistry=[] && H.modification_inventory_status chemistry=H.Declared)
      "Assembly local profile requires declared empty root modification inventories.") sources;
  let facets=["cap";"start_end";"finish_end";"terminal_tail";"modification_inventory"] in
  let expected_facets=List.concat_map (fun source -> List.map (fun facet -> K.Root_source.id source,facet) facets) sources in
  require (same_inventory (List.map (fun row -> MT.Chemistry_disposition.source_id row,
    MT.Component.to_string (MT.Chemistry_disposition.component row)) (MT.Chemistry.dispositions chemistry)) expected_facets)
    "Assembly chemistry transition must account for all ten original root facets exactly once."

let check_carriers value =
  require (List.map (fun (row:link_carrier) -> row.kind) value.carrier_values=[Product;Request;Authorization])
    "Assembly requires an original carrier premise for every link exactly once in order.";
  List.iter (fun (row:link_carrier) ->
    require (row.join_id=value.join_value.join_id) "Assembly link carrier names a different authorized join.";
    let relation=link value row.kind in
    let site (reference:boundary_ref) position =
      match List.find_opt (fun (carrier:C.carrier) -> carrier.target=C.Boundary_port reference.boundary_id)
        (C.carriers (component value reference.slot)) with
      | Some carrier -> require (position<List.length carrier.sites) "Assembly link carrier names an absent actual boundary feature site."
      | None -> fail "Assembly link carrier lacks its original boundary disposition." in
    site relation.producer row.producer_site;site relation.consumer row.consumer_site) value.carrier_values

let of_json ~components raw =
  preflight raw;
  exact ["schema_version";"profile";"identity";"body"] raw;
  require (get "schema_version" raw=str schema_version && get "profile" raw=str profile) "Unsupported original assembly rule profile.";
  let identity_value=P.of_json (get "identity" raw) and body=get "body" raw in
  exact ["primitive_profile";"observable_profile";"phase_profile";"transport_profile";"slot_layout";"components";"links";
    "node_order";"wire_order";"input_order";"group_order";"export_order";"root_bindings";"join";"link_carriers";"material_authority"] body;
  require (P.kind identity_value=P.Model && P.content_fingerprint identity_value=Canonical.fingerprint body)
    "Original assembly identity must pin its complete supplied body.";
  require (get "primitive_profile" body=str I.profile && get "observable_profile" body=str I.observable_profile &&
    get "phase_profile" body=str F.phase_profile && get "transport_profile" body=str transport_profile)
    "Assembly requires the fixed primitive, observable, phase and identity-transport profiles.";
  let selections=List.map (fun raw -> exact ["slot";"component"] raw;
    {slot=slot_of_json (get "slot" raw);identity=P.of_json (get "component" raw)}) (rows 2 (get "components" body)) in
  require (List.map (fun (row:component_selection) -> row.slot) selections=[Decision;Driver])
    "Assembly requires exactly the decision and driver component slots in order.";
  let selected=List.map (fun (row:component_selection) -> match L.find components row.identity with
    | Some component -> row.slot,component | None -> fail "Assembly component is absent from the exact original component library.") selections in
  let layout=get "slot_layout" body in exact ["id";"slots"] layout;
  let layout_value={F.layout_id=name (get "id" layout);slots=index 2 (get "slots" layout)} in
  require (layout_value.slots=2 && List.for_all (fun (_,component) -> F.layout (C.fragment component)=layout_value) selected)
    "Assembly requires one shared original two-slot layout.";
  let value={identity_value;selections;selected;library_digest=L.fingerprint components;model_digest=L.model_library_digest components;layout_value;
    link_values=List.map link_of_json (rows 3 (get "links" body));node_values=List.map node_of_json (rows 256 (get "node_order" body));
    wire_values=List.map wire_of_json (rows 2048 (get "wire_order" body));input_values=List.map input_of_json (rows 64 (get "input_order" body));
    group_values=List.map group_of_json (rows 64 (get "group_order" body));export_values=List.map endpoint_of_json (rows 2048 (get "export_order" body));
    root_values=List.map root_of_json (rows 2 (get "root_bindings" body));join_value=join_of_json (get "join" body);
    carrier_values=List.map carrier_of_json (rows 3 (get "link_carriers" body));material_value=PM.of_json (get "material_authority" body)} in
  check_orders value;check_links value;check_driver_and_authorization value;check_material value;check_carriers value;
  require (equal raw (to_json value)) "Original assembly rule must preserve its complete canonical typed body without normalization.";
  preflight (to_json value);value
let fingerprint value = Canonical.fingerprint (to_json value)
let identity value = value.identity_value
let component_library_digest value = value.library_digest
let model_library_digest value = value.model_digest
let components value = value.selections
let layout value = value.layout_value
let links value = value.link_values
let node_order value = value.node_values
let wire_order value = value.wire_values
let input_order value = value.input_values
let group_order value = value.group_values
let export_order value = value.export_values
let root_bindings value = value.root_values
let join value = value.join_value
let link_carriers value = value.carrier_values
let material_authority value = value.material_value
