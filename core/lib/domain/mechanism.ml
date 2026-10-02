open Bioc_wire
module M = Measurement_contract
module N = Runtime_number
module O = M.Observable
module Strings = Set.Make (String)

type literal = Boolean of bool | Scalar of M.Scalar.t
type comparison = Lt | Le | Gt | Ge | Eq | Ne
type operation =
  | Input | Constant of literal | And | Or | Not | Compare of comparison | Select
  | Delay of { duration : M.Scalar.t; initial : literal }
  | Held_for of M.Scalar.t | Onset | Pulse of M.Scalar.t | Memory of M.Scalar.t option
  | Output | Any_contact

let schema_version = "biocompiler.mechanism.synthetic.v0.2"
let resource_profile = "biocompiler.mechanism.resources.v1"
let supported_kinds = ["and"; "any_contact"; "compare"; "constant"; "delay"; "held_for";
                       "input"; "memory"; "not"; "onset"; "or"; "output"; "pulse"; "select"]
let str value = Json.String value
let require ?path condition message = Diagnostic.require ?path condition "invalid_mechanism" message
let preflight ?(path = "") value =
  try M.preflight ~path value with
  | Diagnostic.Error diagnostic when diagnostic.code = "human_record_limit" ->
      Diagnostic.fail ~path "mechanism_limit" "Mechanism record exceeds the native resource limit."
  | Diagnostic.Error diagnostic when diagnostic.code = "human_record_cycle" ->
      Diagnostic.fail ~path "mechanism_json_cycle" "Cyclic mechanism JSON record."
let bounded values =
  let rec loop count = function
    | [] -> values
    | _ :: rest ->
        Diagnostic.require (count < Limits.max_json_nodes) "mechanism_limit" "Mechanism collection exceeds its native bound.";
        loop (count + 1) rest in
  loop 0 values
let array encode values = Json.Array (List.map encode (bounded values))
let field path key fields = Json.field ~path:(path ^ "/" ^ key) key fields
let names ~path ~unique value =
  let seen = Hashtbl.create 16 in
  Json.array ~path value |> List.mapi (fun index value ->
      let path = path ^ "/" ^ string_of_int index in
      let value = Json.name ~path value in
      require ~path (not unique || not (Hashtbl.mem seen value)) "Duplicate mechanism name.";
      Hashtbl.replace seen value (); value)
let literal_to_json = function Boolean value -> Json.Bool value | Scalar value -> M.Scalar.to_json value
let comparison_name = function Lt -> "lt" | Le -> "le" | Gt -> "gt" | Ge -> "ge" | Eq -> "eq" | Ne -> "ne"
let operation_kind = function Input -> "input" | Constant _ -> "constant" | And -> "and" | Or -> "or"
  | Not -> "not" | Compare _ -> "compare" | Select -> "select" | Delay _ -> "delay"
  | Held_for _ -> "held_for" | Onset -> "onset" | Pulse _ -> "pulse" | Memory _ -> "memory"
  | Output -> "output" | Any_contact -> "any_contact"
let attributes = function
  | Constant value -> ["value", literal_to_json value]
  | Compare operator -> ["operator", str (comparison_name operator)]
  | Delay {duration; initial} -> ["duration", M.Scalar.to_json duration; "initial", literal_to_json initial]
  | Held_for duration | Pulse duration -> ["duration", M.Scalar.to_json duration]
  | Memory duration -> ["duration", (match duration with None -> Json.Null | Some value -> M.Scalar.to_json value)]
  | Input | And | Or | Not | Select | Onset | Output | Any_contact -> []

let literal ~path dtype value =
  if Type_spec.kind dtype = Type_spec.Condition then Boolean (Json.boolean ~path value)
  else
    let binding = match value with
      | Json.Object _ -> value
      | _ ->
          let type_json = Type_spec.to_json dtype in
          let dimensions = Json.field "dimensions" (Json.object_fields type_json) |> Json.object_fields in
          Diagnostic.require ~path (dimensions = []) "invalid_mechanism_node" "Dimensional scalar values require a typed literal with units.";
          let number = N.of_json ~path value |> N.to_json in
          Json.Object ["kind", str "scalar"; "type", type_json; "value", number;
                       "unit", str "1"; "canonical_value", number] in
    Scalar (M.Scalar.of_json ~path ~expected:dtype binding)

let parse_operation ~path dtype kind attributes =
  let fields = Json.object_fields ~path attributes in
  let expected = match kind with
    | "constant" -> ["value"] | "compare" -> ["operator"] | "delay" -> ["duration"; "initial"]
    | "held_for" | "pulse" | "memory" -> ["duration"] | _ -> [] in
  Diagnostic.require ~path (List.mem kind supported_kinds) "invalid_mechanism_node" "Unsupported synthetic operation.";
  Json.exact_fields ~path expected fields;
  let get key = field path key fields in
  let duration () = M.Scalar.duration ~path:(path ^ "/duration") ~positive:true (get "duration") in
  match kind with
  | "input" -> Input | "and" -> And | "or" -> Or | "not" -> Not | "select" -> Select
  | "onset" -> Onset | "output" -> Output | "any_contact" -> Any_contact
  | "constant" -> Constant (literal ~path:(path ^ "/value") dtype (get "value"))
  | "compare" -> Compare (match Json.string ~path (get "operator") with
      | "lt" -> Lt | "le" -> Le | "gt" -> Gt | "ge" -> Ge | "eq" -> Eq | "ne" -> Ne
      | _ -> Diagnostic.fail ~path "invalid_mechanism_node" "Unknown comparison operator.")
  | "delay" -> let duration = duration () in
      Delay {duration; initial = literal ~path:(path ^ "/initial") dtype (get "initial")}
  | "held_for" -> Held_for (duration ()) | "pulse" -> Pulse (duration ())
  | "memory" -> Memory (match get "duration" with Json.Null -> None | _ -> Some (duration ()))
  | _ -> assert false

module Node = struct
  type t = { json : Json.t; id : string; operation : operation; output : O.t;
             inputs : string list; requirements : string list }
  let of_json ?(path = "") value =
    preflight ~path value;
    let fields = Json.object_fields ~path value in
    Json.exact_fields ~path ["id"; "kind"; "output"; "inputs"; "attributes"; "requirement_ids"] fields;
    let get key = field path key fields in
    let id = Json.name ~path:(path ^ "/id") (get "id") in
    let kind = Json.string ~path:(path ^ "/kind") (get "kind") in
    let output = O.of_json ~path:(path ^ "/output") (get "output") in
    let inputs = names ~path:(path ^ "/inputs") ~unique:false (get "inputs") in
    let requirements = names ~path:(path ^ "/requirement_ids") ~unique:true (get "requirement_ids") in
    let operation = parse_operation ~path:(path ^ "/attributes") (O.dtype output) kind (get "attributes") in
    let json = Json.Object ["id", str id; "kind", str kind; "output", O.to_json output;
        "inputs", array str inputs; "attributes", Json.Object (attributes operation);
        "requirement_ids", array str requirements] in
    preflight ~path json;
    {json; id; operation; output; inputs; requirements}
  let make ~id ~operation ~output ?(inputs = []) ?(requirement_ids = []) () =
    of_json (Json.Object ["id", str id; "kind", str (operation_kind operation); "output", O.to_json output;
        "inputs", array str inputs; "attributes", Json.Object (attributes operation);
        "requirement_ids", array str requirement_ids])
  let to_json value = value.json
  let id value = value.id
  let operation value = value.operation
  let kind value = operation_kind value.operation
  let output value = value.output
  let inputs value = value.inputs
  let requirement_ids value = value.requirements
  let dtype value = O.dtype value.output
  let role value = O.role value.output
  let scope value = O.scope value.output
  let compartment value = O.compartment value.output
end

(* Event classification follows only onset and single-input any_contact chains.
   An iterative memoized walk preserves cycle -> false semantics without making
   graph depth consume the native call stack or repeatedly traversing ancestry. *)
let event_table nodes declared =
  let events = Hashtbl.create (List.length declared) in
  List.iter (fun node ->
      if not (Hashtbl.mem events (Node.id node)) then begin
        let seen = Hashtbl.create 16 and visited = ref [] in
        let current = ref (Some node) and result = ref false in
        while !current <> None do
          match !current with
          | None -> ()
          | Some node ->
              let id = Node.id node in
              (match Hashtbl.find_opt events id with
               | Some value -> result := value; current := None
               | None when Hashtbl.mem seen id -> current := None
               | None ->
                   Hashtbl.add seen id (); visited := id :: !visited;
                   match Node.operation node, Node.inputs node with
                   | Onset, _ -> result := true; current := None
                   | Any_contact, [input] -> current := Hashtbl.find_opt nodes input
                   | _ -> current := None)
        done;
        List.iter (fun id -> Hashtbl.replace events id !result) !visited
      end) declared;
  events

let validate_node ~path lookup events node =
  let label = Node.id node ^ " (" ^ Node.kind node ^ "): " in
  let check condition message = require ~path condition (label ^ message) in
  check (List.for_all (Hashtbl.mem lookup) (Node.inputs node)) "Unknown input reference.";
  let inputs = List.map (Hashtbl.find lookup) (Node.inputs node) in
  let boolean node = Type_spec.kind (Node.dtype node) = Type_spec.Condition in
  let scalar node = Type_spec.kind (Node.dtype node) = Type_spec.Scalar in
  let compatible other = Type_spec.compatible (Node.dtype node) (Node.dtype other) in
  let event node = Hashtbl.find events (Node.id node) in
  List.iteri (fun index other ->
      if event other then check (index = 0 && List.mem (Node.kind node) ["pulse"; "memory"; "any_contact"])
          "Event values require a pulse/memory trigger or any_contact aggregation; they cannot serve as continuous level signals.";
      check (Node.role other = Node.role node) "Cross-role edges require an unimplemented transport model.";
      check (Node.compartment other = Node.compartment node) "Cross-compartment edges require an unimplemented transport model.";
      if Node.scope other = O.Contact && Node.scope node = O.Cell then
        check (Node.kind node = "any_contact") "Contact-to-cell flow requires explicit any_contact aggregation.") inputs;
  let count expected message = check (List.length inputs = expected) message in
  match Node.operation node with
  | Input | Constant _ -> check (inputs = []) "Expected no input edges."
  | And | Or -> check (List.length inputs >= 2) "Expected at least two input edges.";
      check (boolean node && List.for_all boolean inputs) "Logical operators require Boolean ports."
  | Not -> count 1 "Expected one input edge.";
      check (boolean node && boolean (List.hd inputs)) "Logical negation requires Boolean ports."
  | Compare _ -> count 2 "Expected two input edges.";
      check (boolean node && List.for_all scalar inputs) "Comparison requires scalar operands and a Boolean result.";
      check (Type_spec.compatible (Node.dtype (List.nth inputs 0)) (Node.dtype (List.nth inputs 1)))
        "Comparison operands have incompatible dimensions."
  | Select -> count 3 "Expected condition, true value and false value.";
      check (boolean (List.nth inputs 0) && compatible (List.nth inputs 1) && compatible (List.nth inputs 2))
        "Select condition or branch types disagree with its output."
  | Delay _ | Output -> count 1 "Expected one input edge.";
      check (compatible (List.hd inputs)) "Input and output types must agree."
  | Held_for _ | Onset | Pulse _ | Memory _ ->
      let memory = Node.kind node = "memory" in
      let expected = if memory then 2 else 1 in
      count expected ("Expected " ^ string_of_int expected ^ " input edges.");
      check (boolean node && List.for_all boolean inputs) "Temporal operators require Boolean ports.";
      if memory then check (Node.scope node = O.Cell) "Memory requires cell scope.";
      if memory || Node.kind node = "pulse" then
        check (event (List.hd inputs)) "Trigger requires onset or explicit any_contact aggregation of onsets."
  | Any_contact -> count 1 "Expected one input edge.";
      check (Node.scope node = O.Cell && Node.scope (List.hd inputs) = O.Contact)
        "any_contact requires a contact input and a cell output.";
      check (boolean node && boolean (List.hd inputs)) "any_contact requires Boolean ports."

let topological ~path lookup declared =
  let incoming = Hashtbl.create (List.length declared) and consumers = Hashtbl.create (List.length declared) in
  let ready = ref [] in
  List.iter (fun node ->
      let dependencies = List.fold_left (fun set id -> Strings.add id set) Strings.empty (Node.inputs node) in
      Hashtbl.add incoming (Node.id node) (Strings.cardinal dependencies);
      if Strings.is_empty dependencies then ready := Node.id node :: !ready;
      Strings.iter (fun id -> Hashtbl.replace consumers id
          (Node.id node :: Option.value (Hashtbl.find_opt consumers id) ~default:[])) dependencies) declared;
  let result = ref [] and count = ref 0 in
  while !ready <> [] do
    let layer = List.sort String.compare !ready in ready := [];
    List.iter (fun id -> incr count; result := Hashtbl.find lookup id :: !result) layer;
    List.iter (fun id -> List.iter (fun consumer ->
          let left = Hashtbl.find incoming consumer - 1 in Hashtbl.replace incoming consumer left;
          if left = 0 then ready := consumer :: !ready)
        (Option.value (Hashtbl.find_opt consumers id) ~default:[])) layer
  done;
  require ~path (!count = List.length declared) "Mechanism graph contains a dependency cycle.";
  List.rev !result

type t = { json : Json.t; fingerprint : string; canonical_size : int; name : string;
           nodes : Node.t list; ordered : Node.t list; outputs : string list;
           capabilities : string list; role : string; lookup : (string, Node.t) Hashtbl.t }
let of_json ?(path = "") value =
  preflight ~path value;
  let fields = Json.object_fields ~path value in
  Json.exact_fields ~path ["schema_version"; "name"; "nodes"; "outputs"; "required_capabilities"] fields;
  let get key = field path key fields in
  let name = Json.name ~path:(path ^ "/name") (get "name") in
  Diagnostic.require ~path (Json.string (get "schema_version") = schema_version) "unsupported_schema" "Unsupported mechanism schema version.";
  let nodes = Json.array ~path:(path ^ "/nodes") (get "nodes")
    |> List.mapi (fun index -> Node.of_json ~path:(path ^ "/nodes/" ^ string_of_int index)) in
  require ~path (nodes <> []) "A mechanism program requires a nonempty node array.";
  let lookup = Hashtbl.create (List.length nodes) in
  List.iter (fun node -> require ~path (not (Hashtbl.mem lookup (Node.id node))) "Duplicate mechanism node IDs.";
      Hashtbl.add lookup (Node.id node) node) nodes;
  let role = Node.role (List.hd nodes) in
  require ~path (List.for_all (fun node -> Node.role node = role) nodes)
    "The synthetic profile represents one executing cell role per program.";
  let events = event_table lookup nodes in
  List.iteri (fun index -> validate_node ~path:(path ^ "/nodes/" ^ string_of_int index) lookup events) nodes;
  let outputs = names ~path:(path ^ "/outputs") ~unique:true (get "outputs") in
  require ~path (outputs <> []) "A mechanism program requires at least one output.";
  require ~path (List.for_all (fun id -> match Hashtbl.find_opt lookup id with
      | Some node -> Node.kind node = "output" | None -> false) outputs) "Program outputs must name output operations.";
  let capabilities = names ~path:(path ^ "/required_capabilities") ~unique:true (get "required_capabilities") in
  let ordered = topological ~path lookup nodes in
  let json = Json.Object ["schema_version", str schema_version; "name", str name;
      "nodes", array Node.to_json nodes; "outputs", array str outputs; "required_capabilities", array str capabilities] in
  preflight ~path json;
  let canonical = Canonical.encode json in
  {json; fingerprint = Canonical.sha256 canonical; canonical_size = String.length canonical;
   name; nodes; ordered; outputs; capabilities; role; lookup}
let make ~name ~nodes ~outputs ?(required_capabilities = []) () =
  of_json (Json.Object ["schema_version", str schema_version; "name", str name;
      "nodes", array Node.to_json nodes; "outputs", array str outputs;
      "required_capabilities", array str required_capabilities])
let to_json value = value.json
let fingerprint value = value.fingerprint
let canonical_size value = value.canonical_size
let name value = value.name
let nodes value = value.nodes
let topological_nodes value = value.ordered
let outputs value = value.outputs
let required_capabilities value = value.capabilities
let role value = value.role
let get value id = Hashtbl.find_opt value.lookup id
