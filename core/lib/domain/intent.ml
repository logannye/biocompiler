open Bioc_wire

module Names = Map.Make (String)
module Name_set = Set.Make (String)

type node = {
  id : Identity.Node.t;
  kind : string;
  inputs : Identity.Node.t list;
  attributes : (string * Json.t) list;
  data_type : Json.t;
  role : Identity.Role.t option;
  source : Json.t;
}

type t = { name : string; nodes : node list; roots : Identity.Node.t list }

let schema_version = "biocompiler.intent.v0.1"
let validation_scope = "intent-structure-types-bindings-v1"
let require = Diagnostic.require

let source ~path = function
  | Json.Null -> Json.Null
  | value ->
      let fields = Json.object_fields ~path value in
      Json.exact_fields ~path ["file"; "line"; "function"] fields;
      ignore (Json.name ~path (Json.field "file" fields));
      ignore (Json.name ~path (Json.field "function" fields));
      let line = Json.integer ~path (Json.field "line" fields) in
      require ~path (Z.compare line Z.zero > 0) "invalid_source" "Source line must be a positive integer.";
      value

let node ~index value =
  let path = "/nodes/" ^ string_of_int index in
  let fields = Json.object_fields ~path value in
  Json.allowed_fields ~path ~required:["id"; "kind"; "inputs"; "attributes"; "data_type"; "role"] ~optional:["source"] fields;
  let id = Identity.Node.of_string (Json.name ~path (Json.field "id" fields)) in
  let kind = Json.name ~path (Json.field "kind" fields) in
  let inputs = Json.array ~path (Json.field "inputs" fields)
    |> List.map (fun value -> Identity.Node.of_string (Json.name ~path value)) in
  let attributes = Json.object_fields ~path (Json.field "attributes" fields) in
  let data_type = Json.field "data_type" fields in
  let typed = match data_type with
    | Json.Null -> None
    | value -> Some (Type_spec.of_json ~path:(path ^ "/data_type") value)
  in
  if kind = "literal" || kind = "parameter" then (
    let declared = match typed with
      | Some value -> value
      | None -> Diagnostic.fail ~path "missing_type" "Literals and parameters require declared types."
    in
    let value_key, bound =
      if kind = "parameter" then (
        ignore (Json.name ~path (Json.field "name" attributes));
        let bound = Json.boolean ~path (Json.field "bound" attributes) in
        require ~path (bound = List.mem_assoc "default" attributes) "invalid_parameter"
          "Parameter bound flag and presence of a default must agree.";
        "default", bound)
      else "value", true
    in
    if bound then Type_spec.validate_binding ~path:(path ^ "/attributes/" ^ value_key)
      ~expected:declared (Json.field ~path value_key attributes));
  let role = match Json.field "role" fields with
    | Json.Null -> None
    | value -> Some (Identity.Role.of_string (Json.name ~path value))
  in
  let source = match List.assoc_opt "source" fields with
    | None -> Json.Null
    | Some value -> source ~path:(path ^ "/source") value
  in
  { id; kind; inputs; attributes; data_type; role; source }

let of_json value =
  let fields = Json.object_fields ~path:"" value in
  Json.exact_fields ~path:"" ["schema_version"; "name"; "nodes"; "roots"] fields;
  require (Json.string (Json.field "schema_version" fields) = schema_version)
    "unsupported_schema" "Unsupported intent schema.";
  let name = Json.name (Json.field "name" fields) in
  let raw_nodes = Json.array ~path:"/nodes" (Json.field "nodes" fields) in
  require (List.length raw_nodes <= Limits.max_intent_nodes) "intent_node_limit" "Intent graph exceeds its node limit.";
  let nodes = List.mapi (fun index value -> node ~index value) raw_nodes in
  let roots = Json.array ~path:"/roots" (Json.field "roots" fields)
    |> List.map (fun value -> Identity.Node.of_string (Json.name ~path:"/roots" value)) in
  let node_map = List.fold_left (fun result node ->
    let identity = Identity.Node.to_string node.id in
    require (not (Names.mem identity result)) "duplicate_node" "Duplicate node identity.";
    Names.add identity node result) Names.empty nodes in
  let root_set = List.fold_left (fun seen root ->
    let identity = Identity.Node.to_string root in
    require (not (Name_set.mem identity seen)) "duplicate_root" "Duplicate root identity.";
    require (Names.mem identity node_map) "dangling_root" "Root refers to a missing node.";
    Name_set.add identity seen) Name_set.empty roots in
  ignore root_set;
  let parameters = ref Name_set.empty in
  let pending = Hashtbl.create (List.length nodes)
  and dependents = Hashtbl.create (List.length nodes) in
  let edges = ref 0 in
  List.iter (fun node ->
    let identity = Identity.Node.to_string node.id in
    if node.kind = "parameter" then (
      let parameter_name = Json.name (Json.field "name" node.attributes) in
      require (not (Name_set.mem parameter_name !parameters)) "duplicate_parameter" "Duplicate parameter name.";
      parameters := Name_set.add parameter_name !parameters);
    let references = List.fold_left (fun refs input -> Name_set.add (Identity.Node.to_string input) refs)
      Name_set.empty node.inputs in
    let references = match node.role with
      | None -> references
      | Some role ->
          let role_id = Identity.Role.to_string role in
          require (match Names.find_opt role_id node_map with Some role -> role.kind = "role" | None -> false)
            "invalid_role" "Node role does not identify a role node.";
          Name_set.add role_id references
    in
    edges := !edges + List.length node.inputs + (if Option.is_some node.role then 1 else 0);
    require (!edges <= Limits.max_graph_edges) "graph_edge_limit" "Intent graph exceeds its edge limit.";
    Hashtbl.add pending identity (Name_set.cardinal references);
    Name_set.iter (fun reference ->
      require (Names.mem reference node_map) "dangling_reference" "Node input refers to a missing node.";
      let current = Option.value ~default:[] (Hashtbl.find_opt dependents reference) in
      Hashtbl.replace dependents reference (identity :: current)) references) nodes;
  let ready = Queue.create () in
  Hashtbl.iter (fun identity count -> if count = 0 then Queue.add identity ready) pending;
  let visited = ref 0 in
  while not (Queue.is_empty ready) do
    let identity = Queue.take ready in
    incr visited;
    List.iter (fun dependent ->
      let remaining = Hashtbl.find pending dependent - 1 in
      Hashtbl.replace pending dependent remaining;
      if remaining = 0 then Queue.add dependent ready)
      (Option.value ~default:[] (Hashtbl.find_opt dependents identity))
  done;
  require (!visited = List.length nodes) "cyclic_graph" "Intent graph has cyclic structural references.";
  { name; nodes; roots }

let node_json ~include_source node =
  let fields = [
    "id", Json.String (Identity.Node.to_string node.id);
    "kind", Json.String node.kind;
    "inputs", Json.Array (List.map (fun value -> Json.String (Identity.Node.to_string value)) node.inputs);
    "attributes", Json.Object node.attributes;
    "data_type", node.data_type;
    "role", (match node.role with None -> Json.Null | Some role -> Json.String (Identity.Role.to_string role))
  ] in
  Json.Object (if include_source then fields @ ["source", node.source] else fields)

let document ~include_source value = Json.Object [
    "schema_version", Json.String schema_version;
    "name", Json.String value.name;
    "nodes", Json.Array (List.map (node_json ~include_source) value.nodes);
    "roots", Json.Array (List.map (fun value -> Json.String (Identity.Node.to_string value)) value.roots)
  ]

let to_json value = document ~include_source:true value
let fingerprint value = Canonical.fingerprint (document ~include_source:false value)

let summary value =
  let counts = List.fold_left (fun counts node ->
    let current = Option.value ~default:0 (Names.find_opt node.kind counts) in
    Names.add node.kind (current + 1) counts) Names.empty value.nodes in
  let count name = Json.int (Option.value ~default:0 (Names.find_opt name counts)) in
  Json.Object [
    "name", Json.String value.name;
    "schema_version", Json.String schema_version;
    "node_count", Json.int (List.length value.nodes);
    "roles", count "role"; "rules", count "rule"; "channels", count "channel";
    "kinds", Json.Object (Names.bindings counts |> List.map (fun (name, count) -> name, Json.int count));
    "fingerprint", Json.String (fingerprint value)
  ]
