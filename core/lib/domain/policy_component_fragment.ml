open Bioc_wire
module I = Policy_implementation
module Pin = Pinned_identity
module Names = Set.Make (String)

let schema_version = "biocompiler.policy_component_fragment.v0.1"
let profile = "biocompiler.policy_exact_fragment.v0.1"
let staged_profile = "biocompiler.policy_staged_fragment.v0.1"
let staged_phase_profile = "biocompiler.policy_staged_primitive_execution.v0.1"
let primitive_profile = I.profile
let observable_profile = I.observable_profile
let phase_profile = "biocompiler.policy_primitive_execution.v0.1"
let resource_profile = "biocompiler.policy_component_fragment.resources.v0.1"

type slot_layout = { layout_id : string; slots : int }
type node = { node_id : string; model : I.model }
type boundary_port = {
  boundary_id : string; direction : I.direction; signal_type : I.signal_type;
  endpoint : I.endpoint; replication : I.replication;
}
type external_slot = {
  slot_id : string; input_kind : I.external_kind; consumer : I.endpoint;
  replication : I.replication;
}
type t = {
  raw : Json.t; library_pin : string; fragment_id : string; fragment_version : string;
  layout_value : slot_layout; node_values : node list; wire_values : I.wire list;
  boundary_values : boundary_port list; external_values : external_slot list;
  group_values : I.atomic_group list; export_values : I.endpoint list;
}

let fail message = Diagnostic.fail "policy_component_fragment" message
let require condition message = if not condition then fail message
let get key value = Json.field key (Json.object_fields value)
let text key value = Json.string (get key value)
let exact keys value = Json.exact_fields keys (Json.object_fields value)
let name value =
  let result = Json.name value in
  require (String.length result <= 128) "Fragment identifier exceeds 128 bytes.";
  result
let integer ~minimum ~maximum value =
  let result = Json.integer value in
  require (Z.compare result (Z.of_int minimum) >= 0 &&
    Z.compare result (Z.of_int maximum) <= 0) "Fragment integer is outside its finite contract.";
  Z.to_int result
let rows maximum value =
  let result = Json.array value in
  require (List.length result <= maximum) "Fragment array exceeds its declared bound.";
  result
let unique label values =
  let seen = ref Names.empty in
  List.iter (fun value ->
    require (not (Names.mem value !seen)) ("Duplicate fragment " ^ label ^ " identity.");
    seen := Names.add value !seen) values
let measure raw =
  let maximum = 2 * 1024 * 1024 and count = ref 0 and bytes = ref 0 in
  let limit condition = Diagnostic.require condition "policy_component_fragment_limit"
    "Fragment exceeds its 2 MiB/100000-node/48-depth resource profile." in
  let visit depth = incr count; limit (!count <= 100_000 && depth <= 48) in
  let charge n = limit (n <= maximum - !bytes); bytes := !bytes + n in
  let string value =
    limit (String.length value <= 65_536); Json.validate_utf8 value;
    charge (String.length value) in
  let rec walk depth = function
    | Json.Null -> visit depth; charge 4
    | Json.Bool value -> visit depth; charge (if value then 4 else 5)
    | Json.Int value ->
        visit depth; limit (Z.numbits value <= 256); charge (String.length (Z.to_string value))
    | Json.Float _ -> fail "Raw floats cannot enter an exact fragment contract."
    | Json.String value -> visit depth; string value
    | Json.Array values -> visit depth; List.iter (walk (depth + 1)) values
    | Json.Object fields ->
        visit depth;
        let seen = Hashtbl.create 16 in
        List.iter (fun (key, value) ->
          visit (depth + 1); string key;
          require (not (Hashtbl.mem seen key)) "Duplicate fragment object key.";
          Hashtbl.add seen key (); walk (depth + 1) value) fields in
  walk 0 raw;
  ignore (Canonical.encode_bounded ~max_bytes:maximum raw)
let endpoint_of_json value : I.endpoint =
  exact ["node"; "port"] value;
  { node_id = name (get "node" value); port_id = name (get "port" value) }
let endpoint_key (value : I.endpoint) =
  Canonical.encode (Json.Array [Json.String value.node_id; Json.String value.port_id])
let signal_of_json value = match Json.string value with
  | "truth_value" -> I.Truth_value | "product_symbol" -> I.Product_symbol
  | "evidence_batch" -> I.Evidence_batch | "feedback_batch" -> I.Feedback_batch
  | "event_batch" -> I.Event_batch | "activation_batch" -> I.Activation_batch
  | "truth_write" -> I.Truth_write | "effect_request" -> I.Effect_request
  | "attempt_snapshot" -> I.Attempt_snapshot
  | "machine_snapshot" -> I.Machine_snapshot | "machine_write" -> I.Machine_write
  | _ -> fail "Unknown fragment boundary signal type."
let direction_of_json value = match Json.string value with
  | "input" -> I.Input | "output" -> I.Output
  | _ -> fail "Unknown fragment boundary direction."
let model_of_json ~library value =
  exact ["identity"; "configuration_digest"; "body"] value;
  let identity = Pin.of_json (get "identity" value) in
  let model = match List.find_opt (fun (model : I.model) ->
    Json.equal (Pin.to_json model.identity) (Pin.to_json identity)) (I.models library) with
    | Some model -> model
    | None -> fail "Fragment model is absent from the independently supplied library." in
  require (get "configuration_digest" value = Json.String model.configuration_digest &&
    Json.equal (get "body" value) (I.model_body_to_json model))
    "Fragment changed a complete model or configuration body.";
  model
let index_nodes values =
  let index = Hashtbl.create 32 in
  List.iter (fun (value : node) -> Hashtbl.add index value.node_id value) values;
  index
let find_node index identity : node = match Hashtbl.find_opt index identity with
  | Some value -> value
  | None -> fail "Fragment endpoint names an absent local node."
let find_port index direction (endpoint : I.endpoint) : I.port =
  let node = find_node index endpoint.node_id in
  match List.find_opt (fun (port : I.port) -> port.port_id = endpoint.port_id)
    (I.ports node.model.primitive) with
  | Some port when port.direction = direction -> port
  | _ -> fail "Fragment endpoint names an absent port or reverses its direction."
let arbiter_lanes = function
  | I.Exclusive_arbiter count -> Some count
  | I.Priority_arbiter order -> Some (List.length order)
  | _ -> None

let validate_graph (value : t) =
  let index = index_nodes value.node_values in
  let node = find_node index and port = find_port index in
  let drivers = Hashtbl.create 32 and consumers = Hashtbl.create 32 in
  let boundary_outputs = Hashtbl.create 16 in
  let drive (endpoint : I.endpoint) =
    let key = endpoint_key endpoint in
    require (not (Hashtbl.mem drivers key)) "Fragment input has multiple suppliers.";
    Hashtbl.add drivers key () in
  List.iter (fun (wire : I.wire) ->
    let producer_port = port I.Output wire.producer and consumer_port = port I.Input wire.consumer in
    require (producer_port.signal_type = consumer_port.signal_type) "Fragment wire signal types differ.";
    let producer = node wire.producer.node_id and consumer = node wire.consumer.node_id in
    require (producer.model.replication = consumer.model.replication ||
      (producer.model.replication = I.Executor &&
        (match producer.model.primitive with I.Truth_constant _ | I.Product_constant _ -> true | _ -> false)))
      "Fragment wire scope differs; only immutable constants may broadcast to encounter slots.";
    drive wire.consumer;
    let key = endpoint_key wire.producer in
    Hashtbl.replace consumers key
      (wire.consumer :: Option.value (Hashtbl.find_opt consumers key) ~default:[])) value.wire_values;
  List.iter (fun (boundary : boundary_port) -> match boundary.direction with
    | I.Input -> drive boundary.endpoint
    | I.Output -> Hashtbl.add boundary_outputs (endpoint_key boundary.endpoint) ()) value.boundary_values;
  List.iter (fun (slot : external_slot) -> drive slot.consumer) value.external_values;
  List.iter (fun (node : node) -> List.iter (fun (port : I.port) ->
    if port.direction = I.Input then
      require (Hashtbl.mem drivers (endpoint_key { I.node_id = node.node_id; port_id = port.port_id }))
        "Fragment input lacks a wire, boundary input or external slot.")
    (I.ports node.model.primitive)) value.node_values;
  let expected_exports = List.concat_map (fun (node : node) ->
    List.filter_map (fun (port : I.port) -> if port.direction = I.Output then
      Some { I.node_id = node.node_id; port_id = port.port_id } else None)
      (I.ports node.model.primitive)) value.node_values in
  require (value.export_values = expected_exports)
    "Fragment semantic exports must contain every output in fixed node/port order.";
  let member_groups = Hashtbl.create 16 in
  List.iter (fun (group : I.atomic_group) ->
    let arbiter = node group.arbiter in
    let lanes = match arbiter_lanes arbiter.model.primitive with
      | Some count -> count | None -> fail "Fragment atomic group does not name an arbiter." in
    require (List.length group.commits = lanes) "Fragment atomic group must own every arbiter lane.";
    List.iter (fun identity ->
      require (not (Hashtbl.mem member_groups identity)) "Fragment atomic node belongs to multiple groups.";
      Hashtbl.add member_groups identity group.group_id) (group.arbiter :: group.commits);
    List.iteri (fun lane identity ->
      let commit = node identity in
      require (commit.model.replication = arbiter.model.replication) "Fragment atomic group has inconsistent scope.";
      let writes, requests = match commit.model.primitive with
        | I.Atomic_commit { writes; requests } | I.Transition_commit { writes; requests; _ } -> writes, requests
        | _ -> fail "Fragment atomic group member is not a commit." in
      let output = { I.node_id = group.arbiter; port_id = "out" ^ string_of_int lane } in
      let expected = { I.node_id = identity; port_id = "grant" } in
      require (Option.value (Hashtbl.find_opt consumers (endpoint_key output)) ~default:[] = [expected] &&
        not (Hashtbl.mem boundary_outputs (endpoint_key output)))
        "Fragment arbiter lane must drive exactly its local corresponding commit.";
      let destinations = ref [] in
      List.iter (fun (prefix, count) -> for position = 0 to count - 1 do
        let key = endpoint_key { I.node_id = identity; port_id = prefix ^ string_of_int position } in
        let local = Option.value (Hashtbl.find_opt consumers key) ~default:[] in
        match local, Hashtbl.mem boundary_outputs key with
        | [destination], false -> destinations := destination.I.node_id :: !destinations
        | [], true -> ()
        | _ -> fail "Fragment atomic action needs one local destination or one boundary continuation."
      done) ["write", writes; "request", requests];
      (match commit.model.primitive with
       | I.Transition_commit _ ->
         let key=endpoint_key {I.node_id=identity;port_id="machine_write"} in
         (match Option.value (Hashtbl.find_opt consumers key) ~default:[], Hashtbl.mem boundary_outputs key with
          | [destination],false -> destinations:=destination.I.node_id:: !destinations
          | _ -> fail "Fragment transition must write exactly one local machine bank.")
       | _ -> ());
      unique "atomic destination" !destinations) group.commits) value.group_values;
  List.iter (fun (node : node) -> match node.model.primitive with
    | I.Exclusive_arbiter _ | I.Priority_arbiter _ | I.Atomic_commit _ | I.Transition_commit _ ->
        require (Hashtbl.mem member_groups node.node_id) "Fragment atomic node lacks local group ownership."
    | I.Truth_register _ | I.Attempt_bank _ | I.Machine_bank _ ->
        let groups = value.wire_values |> List.filter_map (fun (wire : I.wire) ->
          if wire.consumer.node_id = node.node_id &&
            (match (find_node index wire.producer.node_id).model.primitive with I.Atomic_commit _ | I.Transition_commit _ -> true | _ -> false)
          then Hashtbl.find_opt member_groups wire.producer.node_id else None)
          |> List.sort_uniq String.compare in
        require (List.length groups <= 1) "Fragment local bank writers require one common arbitration group."
    | _ -> ()) value.node_values;
  let instantaneous = List.filter (fun (wire : I.wire) ->
    match (node wire.consumer.node_id).model.primitive with
    | I.Truth_register _ | I.Machine_bank _ -> false
    | I.Attempt_bank _ when wire.consumer.port_id = "request" -> false
    | _ -> true) value.wire_values in
  let visited = ref Names.empty in
  let rec order remaining = match remaining with
    | [] -> ()
    | _ ->
        let ready, blocked = List.partition (fun (node : node) ->
          List.for_all (fun (wire : I.wire) -> wire.consumer.node_id <> node.node_id ||
            Names.mem wire.producer.node_id !visited) instantaneous) remaining in
        require (ready <> []) "Fragment contains an instantaneous local scheduling cycle.";
        List.iter (fun (node : node) -> visited := Names.add node.node_id !visited) ready;
        order blocked in
  order value.node_values

let of_json ~library raw =
  measure raw;
  exact ["schema_version"; "profile"; "primitive_profile"; "observable_profile"; "phase_profile";
    "id"; "version"; "slot_layout"; "nodes"; "wires"; "boundary_ports"; "external_slots";
    "atomic_groups"; "semantic_exports"] raw;
  let staged=text "profile" raw=staged_profile in
  require (text "schema_version" raw = schema_version &&
    (text "profile" raw = profile || staged) &&
    text "primitive_profile" raw = (if staged then I.staged_profile else primitive_profile) &&
    text "observable_profile" raw = (if staged then I.staged_observable_profile else observable_profile) &&
    text "phase_profile" raw = (if staged then staged_phase_profile else phase_profile))
    "Unknown fragment, primitive, observable or phase profile.";
  let fragment_id = name (get "id" raw) and fragment_version = name (get "version" raw) in
  let raw_layout = get "slot_layout" raw in
  exact ["id"; "slots"] raw_layout;
  let layout_value = { layout_id = name (get "id" raw_layout);
    slots = integer ~minimum:1 ~maximum:16 (get "slots" raw_layout) } in
  let node_values = List.map (fun value ->
    exact ["id"; "model"] value;
    let node_id = name (get "id" value) and model = model_of_json ~library (get "model" value) in
    require (staged || I.profile_for_primitive model.primitive=I.profile)
      "Legacy fragments cannot contain staged primitives.";
    (match model.replication with
    | I.Executor -> ()
    | I.Encounter_slots { layout_id; slots } ->
        require (layout_id = layout_value.layout_id && slots = layout_value.slots)
          "Fragment model replication differs from its local slot layout.");
    { node_id; model }) (rows 256 (get "nodes" raw)) in
  require (node_values <> []) "Fragment graph cannot be empty.";
  unique "node" (List.map (fun (node : node) -> node.node_id) node_values);
  let index = index_nodes node_values in
  let wire_values = List.map (fun value ->
    exact ["producer"; "consumer"] value;
    ({ producer = endpoint_of_json (get "producer" value);
       consumer = endpoint_of_json (get "consumer" value) } : I.wire)) (rows 2048 (get "wires" raw)) in
  let boundary_values = List.map (fun value ->
    exact ["id"; "direction"; "signal_type"; "endpoint"] value;
    let boundary_id = name (get "id" value) and direction = direction_of_json (get "direction" value)
    and signal_type = signal_of_json (get "signal_type" value)
    and endpoint = endpoint_of_json (get "endpoint" value) in
    let port = find_port index direction endpoint in
    require (signal_type = port.signal_type) "Fragment boundary type differs from its actual port.";
    let replication = (find_node index endpoint.node_id).model.replication in
    { boundary_id; direction; signal_type; endpoint; replication }) (rows 256 (get "boundary_ports" raw)) in
  unique "boundary port" (List.map (fun (port : boundary_port) -> port.boundary_id) boundary_values);
  unique "boundary endpoint" (List.map (fun (port : boundary_port) -> endpoint_key port.endpoint) boundary_values);
  let external_values = List.map (fun value ->
    exact ["id"; "kind"; "consumer"] value;
    let slot_id = name (get "id" value) and consumer = endpoint_of_json (get "consumer" value) in
    let input_kind = match text "kind" value with
      | "evidence" -> I.Evidence_input | "feedback" -> I.Feedback_input
      | _ -> fail "Unknown fragment external slot kind." in
    let port = find_port index I.Input consumer in
    require (port.signal_type = (match input_kind with I.Evidence_input -> I.Evidence_batch | I.Feedback_input -> I.Feedback_batch))
      "Fragment external slot kind differs from its actual receiving port.";
    let replication = (find_node index consumer.node_id).model.replication in
    { slot_id; input_kind; consumer; replication }) (rows 64 (get "external_slots" raw)) in
  unique "external slot" (List.map (fun (slot : external_slot) -> slot.slot_id) external_values);
  let group_values = List.map (fun value ->
    exact ["id"; "arbiter"; "commits"] value;
    let commits = List.map name (rows 64 (get "commits" value)) in
    unique "atomic commit" commits;
    ({ group_id = name (get "id" value); arbiter = name (get "arbiter" value); commits } : I.atomic_group))
      (rows 64 (get "atomic_groups" raw)) in
  unique "atomic group" (List.map (fun (group : I.atomic_group) -> group.group_id) group_values);
  let export_values = List.map endpoint_of_json (rows 16384 (get "semantic_exports" raw)) in
  let value = { raw; library_pin = I.library_digest library; fragment_id; fragment_version;
    layout_value; node_values; wire_values; boundary_values; external_values; group_values; export_values } in
  validate_graph value;
  value

let to_json (value : t) = value.raw
let fingerprint (value : t) = Canonical.fingerprint value.raw
let model_library_digest (value : t) = value.library_pin
let id (value : t) = value.fragment_id
let version (value : t) = value.fragment_version
let layout (value : t) = value.layout_value
let nodes (value : t) = value.node_values
let wires (value : t) = value.wire_values
let boundary_ports (value : t) = value.boundary_values
let external_slots (value : t) = value.external_values
let atomic_groups (value : t) = value.group_values
let semantic_exports (value : t) = value.export_values
