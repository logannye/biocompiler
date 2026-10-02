open Bioc_wire
open Bioc_domain
module N = Runtime_number
module M = Mechanism
module D = Model_execution_data
module O = Measurement_contract.Observable
module Names = Set.Make (String)
module Ordered = Map.Make (Int)

let implementation_version = "biocompiler.ocaml.synthetic.v0.1"
let runner_version = "biocompiler.synthetic.runner.v0.2"
let resource_profile = "biocompiler.synthetic.resources.v1"
type limits = { max_work : int; max_frames : int; max_trace_items : int;
  max_trace_bytes : int; max_state_items : int }
let make_limits ?(max_work=50_000_000) ?(max_frames=10_000) ?(max_trace_items=100_000)
    ?(max_trace_bytes=Limits.max_response_bytes) ?(max_state_items=100_000) () =
  List.iter (fun (actual,maximum) -> Diagnostic.require (actual >= 0 && actual <= maximum)
      "synthetic_invalid_limits" "Synthetic limits can only reduce the fixed native resource profile.")
    [max_work,50_000_000;max_frames,10_000;max_trace_items,100_000;
     max_trace_bytes,Limits.max_response_bytes;max_state_items,100_000];
  {max_work;max_frames;max_trace_items;max_trace_bytes;max_state_items}
let default_limits = make_limits ()
let limits_json (limits : limits) = Json.Object ["resource_profile",Json.String resource_profile;
    "max_work",Json.int limits.max_work;"max_frames",Json.int limits.max_frames;
    "max_trace_items",Json.int limits.max_trace_items;"max_trace_bytes",Json.int limits.max_trace_bytes;
    "max_state_items",Json.int limits.max_state_items]
type usage = { work : int; frames : int; trace_items : int; trace_bytes : int }
type budget = { limits : limits; mutable work : int; mutable frames : int;
  mutable trace_items : int; mutable trace_bytes : int; mutable state_items : int;
  mutable temporary_items : int; mutable snapshot_items : int }
let bounded code label current maximum amount =
  Diagnostic.require (amount >= 0 && amount <= maximum - current) code
    ("Synthetic " ^ label ^ " limit exceeded under " ^ resource_profile ^ ".")
let charge (budget : budget) amount =
  bounded "synthetic_work_limit" "cumulative work" budget.work budget.limits.max_work amount;
  budget.work <- budget.work + amount
let reserve (budget : budget) ~items ~bytes =
  bounded "synthetic_trace_limit" "trace item" budget.trace_items budget.limits.max_trace_items items;
  bounded "synthetic_trace_limit" "encoded trace byte" budget.trace_bytes budget.limits.max_trace_bytes bytes;
  charge budget (items + bytes);
  budget.trace_items <- budget.trace_items + items;
  budget.trace_bytes <- budget.trace_bytes + bytes
let reserve_state (budget : budget) =
  bounded "synthetic_state_limit" "retained state" (budget.state_items + budget.temporary_items + budget.snapshot_items)
    budget.limits.max_state_items 1;
  budget.state_items <- budget.state_items + 1
let reserve_temporary (budget : budget) =
  bounded "synthetic_state_limit" "settlement state" (budget.state_items + budget.temporary_items + budget.snapshot_items)
    budget.limits.max_state_items 1;
  budget.temporary_items <- budget.temporary_items + 1

(* Preserve Python's insertion order within each timer family. Equal numeric
   deadlines can have distinct integer/float representations; the first minimum
   wins, after the horizon and the next external frame. *)
type key = int * string option
type 'a store = { entries : (key, int * 'a) Hashtbl.t; mutable order : key Ordered.t;
  mutable next : int }
let store () = {entries=Hashtbl.create 16;order=Ordered.empty;next=0}
let find table key = Option.map snd (Hashtbl.find_opt table.entries key)
let contains table key = Hashtbl.mem table.entries key
let put (budget : budget) table key value =
  match Hashtbl.find_opt table.entries key with
  | Some (position,_) -> Hashtbl.replace table.entries key (position,value)
  | None ->
      reserve_state budget;
      let position = table.next in
      table.next <- position + 1;
      Hashtbl.add table.entries key (position,value);
      table.order <- Ordered.add position key table.order
let remove (budget : budget) table key =
  match Hashtbl.find_opt table.entries key with
  | None -> ()
  | Some (position,_) ->
      Hashtbl.remove table.entries key;
      table.order <- Ordered.remove position table.order;
      budget.state_items <- budget.state_items - 1
let iter (budget : budget) table f =
  Ordered.iter (fun _ key -> charge budget 1; f key (snd (Hashtbl.find table.entries key))) table.order
let discard_contacts (budget : budget) table live =
  (* Map iteration visits an immutable snapshot, so removals cannot skip entries. *)
  iter budget table (fun ((_,binding) as key) _ -> match binding with
      | Some identity when not (Names.mem identity live) -> remove budget table key
      | _ -> ())

let literal = function
  | M.Boolean value -> D.Boolean value
  | M.Scalar value -> D.Number (Measurement_contract.Scalar.canonical value)
let boolean = function D.Boolean value -> value | D.Number _ ->
  Diagnostic.fail "synthetic_internal" "A checked Boolean operation received a scalar."
let number = function D.Number value -> value | D.Boolean _ ->
  Diagnostic.fail "synthetic_internal" "A checked scalar operation received a Boolean."
let equal left right = match left,right with
  | D.Boolean left,D.Boolean right -> left = right
  | D.Number left,D.Number right -> N.equal left right
  | _ -> false
let number_type = function D.Boolean _ -> "bool" | D.Number (N.Integer _) -> "int"
  | D.Number (N.Real _) -> "float"
let deadline time duration label =
  let result = try N.add time (Measurement_contract.Scalar.canonical duration) with
    | Diagnostic.Error _ -> Diagnostic.fail "synthetic_deadline" (label ^ " deadline must be finite.") in
  Diagnostic.require (N.compare result time > 0) "synthetic_deadline"
    ("A " ^ label ^ " duration must advance the representable model time.");
  result
let string_size value =
  let size = ref (String.length value + 2) in
  String.iter (function '"' | '\\' | '\b' | '\012' | '\n' | '\r' | '\t' -> incr size
    | c when Char.code c < 32 -> size := !size + 5 | _ -> ()) value;
  !size
let value_size value = String.length (Canonical.encode (D.value_to_json value))
let scalar_size value = String.length (Canonical.encode (N.to_json value))
let repr_names values = "[" ^ String.concat ", " (List.map Diagnostic_text.repr values) ^ "]"
let input_inventory_error (budget : budget) identity missing extra =
  let estimate = List.fold_left (fun total name -> total + 6 * String.length name + 4) 128 (missing @ extra)
      + (match identity with None -> 4 | Some text -> 6 * String.length text + 2) in
  bounded "synthetic_trace_limit" "diagnostic byte" 0 Limits.max_response_bytes estimate;
  charge budget estimate;
  Diagnostic.fail "synthetic_input_inventory"
    ("Input snapshot for contact " ^ (match identity with None -> "None" | Some value -> Diagnostic_text.repr value)
     ^ " has missing " ^ repr_names missing ^ " or unknown/wrong-scope " ^ repr_names extra ^ " ports.")

type prepared = { node : M.Node.t; index : int; inputs : int array; contact : bool }
type session = { graph : prepared array;
  by_index : prepared array; input_types : (string,bool) Hashtbl.t;
  cell_inputs : Names.t; contact_inputs : Names.t; outputs : (string * int * bool) list;
  mutable cell : (string,D.value) Hashtbl.t;
  mutable contacts : (string,(string,D.value) Hashtbl.t) Hashtbl.t;
  mutable identities : string list;
  delayed : D.value store; pending : (N.t * D.value) store; held : N.t store;
  previous : bool store; pulses : N.t store; memories : N.t option store }
let prepare (budget : budget) program =
  charge budget (M.canonical_size program);
  let nodes = M.nodes program in
  let by_id = Hashtbl.create 16 in
  List.iteri (fun index node -> charge budget 1; Hashtbl.add by_id (M.Node.id node) index) nodes;
  let prepared = List.mapi (fun index node ->
      let inputs = M.Node.inputs node in
      charge budget (1 + List.length inputs);
      {node;index;inputs=Array.of_list (List.map (Hashtbl.find by_id) inputs);
       contact=M.Node.scope node = O.Contact}) nodes |> Array.of_list in
  let graph = M.topological_nodes program |> List.map (fun node -> prepared.(Hashtbl.find by_id (M.Node.id node))) |> Array.of_list in
  let input_types = Hashtbl.create 16 in
  let cell_inputs,contact_inputs = Array.fold_left (fun (cell,contact) current ->
      match M.Node.operation current.node with
      | M.Input ->
          let id = M.Node.id current.node in
          Hashtbl.add input_types id (Type_spec.kind (M.Node.dtype current.node) = Type_spec.Condition);
          if current.contact then cell,Names.add id contact else Names.add id cell,contact
      | _ -> cell,contact) (Names.empty,Names.empty) prepared in
  let outputs = List.map (fun id -> charge budget 1;
      let index = Hashtbl.find by_id id in id,index,prepared.(index).contact) (M.outputs program) in
  {graph;by_index=prepared;input_types;cell_inputs;contact_inputs;outputs;
   cell=Hashtbl.create 1;contacts=Hashtbl.create 1;identities=[];
   delayed=store ();pending=store ();held=store ();previous=store ();pulses=store ();memories=store ()}
let validate_snapshot (budget : budget) session identity values =
  let expected = match identity with None -> session.cell_inputs | Some _ -> session.contact_inputs in
  let actual = List.fold_left (fun names (id,_) -> charge budget 1; Names.add id names) Names.empty values in
  if not (Names.equal actual expected) then
    input_inventory_error budget identity (Names.elements (Names.diff expected actual)) (Names.elements (Names.diff actual expected));
  List.iter (fun (id,value) ->
      charge budget 1;
      let wants_boolean = Hashtbl.find session.input_types id in
      if wants_boolean <> (match value with D.Boolean _ -> true | D.Number _ -> false) then
        Diagnostic.fail "synthetic_input_type" ("Input " ^ Diagnostic_text.repr id ^ " requires " ^
          (if wants_boolean then "a Boolean" else "a canonical scalar") ^ ", not " ^ number_type value ^ ".")) values
let update (budget : budget) session frame =
  validate_snapshot budget session None (D.Input_frame.values frame);
  List.iter (fun (identity,values) -> validate_snapshot budget session (Some identity) values) (D.Input_frame.contacts frame);
  let snapshot_items = List.length (D.Input_frame.values frame) +
    List.fold_left (fun total (_,values) -> total + 1 + List.length values) 0 (D.Input_frame.contacts frame) in
  bounded "synthetic_state_limit" "snapshot state" 0 budget.limits.max_state_items snapshot_items;
  let identities = List.map fst (D.Input_frame.contacts frame) |> List.sort String.compare in
  let live = List.fold_left (fun names id -> Names.add id names) Names.empty identities in
  discard_contacts budget session.delayed live; discard_contacts budget session.pending live;
  discard_contacts budget session.held live; discard_contacts budget session.previous live;
  discard_contacts budget session.pulses live;
  bounded "synthetic_state_limit" "snapshot and temporal state" budget.state_items budget.limits.max_state_items snapshot_items;
  budget.snapshot_items <- snapshot_items;
  session.cell <- Hashtbl.create 1;
  session.contacts <- Hashtbl.create 1;
  let table values = let result = Hashtbl.create 16 in
    List.iter (fun (key,value) -> charge budget 1; Hashtbl.add result key value) values; result in
  let contacts = Hashtbl.create 16 in
  List.iter (fun (identity,values) -> charge budget 1; Hashtbl.add contacts identity (table values)) (D.Input_frame.contacts frame);
  session.cell <- table (D.Input_frame.values frame);
  session.contacts <- contacts;
  session.identities <- identities
let output_frame (budget : budget) session time values =
  bounded "synthetic_frame_limit" "frame" budget.frames budget.limits.max_frames 1;
  if budget.frames > 0 then reserve budget ~items:0 ~bytes:1;
  let start_bytes = budget.trace_bytes in
  let retain ~items ~bytes =
    bounded "synthetic_trace_limit" "encoded frame byte" (budget.trace_bytes - start_bytes)
      Limits.max_request_bytes bytes;
    reserve budget ~items ~bytes in
  (* Account for the whole Trace envelope separately. Add this frame's empty
     object/map structure first, then each member before constructing its list. *)
  retain ~items:7 ~bytes:(String.length "{\"contacts\":{},\"time\":,\"values\":{}}" + scalar_size time);
  let entries contact binding =
    let count = ref 0 in
    List.filter_map (fun (id,index,is_contact) ->
        charge budget 1;
        if is_contact <> contact then None else (
          let value = Hashtbl.find values (index,binding) in
          retain ~items:2 ~bytes:(string_size id + 1 + value_size value + if !count = 0 then 0 else 1);
          incr count; Some (id,value))) session.outputs in
  let cell = entries false None in
  let contact_count = ref 0 in
  let contacts = List.map (fun identity ->
      retain ~items:2 ~bytes:(string_size identity + 3 + if !contact_count = 0 then 0 else 1);
      incr contact_count;
      identity,entries true (Some identity)) session.identities in
  let result = D.Frame.make ~time ~values:cell ~contacts () in
  budget.frames <- budget.frames + 1;
  result
let step (budget : budget) session time =
  budget.temporary_items <- 0;
  let values = Hashtbl.create 16 in
  Array.iter (fun current ->
      let evaluate binding =
          charge budget 1; reserve_temporary budget;
          let key = current.index,binding in
          let get index =
            charge budget 1;
            let ref = current.inputs.(index) in
            Hashtbl.find values (ref,if session.by_index.(ref).contact then binding else None) in
          let value = match M.Node.operation current.node with
            | M.Input ->
                let table = match binding with None -> session.cell | Some id -> Hashtbl.find session.contacts id in
                Hashtbl.find table (M.Node.id current.node)
            | M.Constant value -> literal value
            | M.Any_contact -> D.Boolean (List.exists (fun id -> charge budget 1;
                  boolean (Hashtbl.find values (current.inputs.(0),Some id))) session.identities)
            | M.And | M.Or as operation ->
                (* Python eagerly reads every operand before all/any. *)
                let result = ref (operation = M.And) in
                for index = 0 to Array.length current.inputs - 1 do
                  let operand = boolean (get index) in
                  result := if operation = M.And then !result && operand else !result || operand
                done;
                D.Boolean !result
            | M.Not -> D.Boolean (not (boolean (get 0)))
            | M.Compare operation ->
                let order = N.compare (number (get 0)) (number (get 1)) in
                D.Boolean (match operation with M.Lt -> order < 0 | M.Le -> order <= 0 | M.Gt -> order > 0
                    | M.Ge -> order >= 0 | M.Eq -> order = 0 | M.Ne -> order <> 0)
            | M.Select -> get (if boolean (get 0) then 1 else 2)
            | M.Output -> get 0
            | M.Held_for duration ->
                if not (boolean (get 0)) then (remove budget session.held key;D.Boolean false)
                else (
                  let expiry = match find session.held key with
                    | Some expiry -> expiry
                    | None -> let expiry = deadline time duration "held_for" in put budget session.held key expiry;expiry in
                  D.Boolean (N.compare time expiry >= 0))
            | M.Onset ->
                let value = boolean (get 0) in
                let previous = Option.value (find session.previous key) ~default:false in
                put budget session.previous key value;
                D.Boolean (value && not previous)
            | M.Pulse duration ->
                if boolean (get 0) then put budget session.pulses key (deadline time duration "pulse")
                else (match find session.pulses key with Some expiry when N.compare expiry time <= 0 -> remove budget session.pulses key | _ -> ());
                D.Boolean (contains session.pulses key)
            | M.Memory duration ->
                if boolean (get 1) then remove budget session.memories key
                else if boolean (get 0) then put budget session.memories key (Option.map (fun value -> deadline time value "memory") duration)
                else (match find session.memories key with Some (Some expiry) when N.compare expiry time <= 0 -> remove budget session.memories key | _ -> ());
                D.Boolean (contains session.memories key)
            | M.Delay {duration;initial} ->
                let desired = get 0 in
                let current = match find session.delayed key with
                  | Some current -> current
                  | None -> let current = literal initial in put budget session.delayed key current;current in
                let result = if equal desired current then (remove budget session.pending key;current)
                  else match find session.pending key with
                    | Some (expiry,pending) when equal desired pending ->
                        if N.compare expiry time <= 0 then (
                          put budget session.delayed key desired;remove budget session.pending key;desired) else current
                    | _ -> put budget session.pending key (deadline time duration "delay",desired);current in
                result in
          Hashtbl.add values key value in
      if current.contact then List.iter (fun identity -> evaluate (Some identity)) session.identities
      else evaluate None) session.graph;
  let result = output_frame budget session time values in
  budget.temporary_items <- 0;
  result
let next_time (budget : budget) session now horizon next_external =
  let next = ref horizon in
  let consider value = charge budget 1;
    if N.compare now value < 0 && N.compare value horizon <= 0 && N.compare value !next < 0 then next := value in
  Option.iter consider next_external;
  iter budget session.pending (fun _ (time,_) -> consider time);
  iter budget session.held (fun _ time -> consider time);
  iter budget session.pulses (fun _ time -> consider time);
  iter budget session.memories (fun _ time -> Option.iter consider time);
  !next
let run_with_usage ?until ?(limits=default_limits) program history =
  let budget : budget = {limits;work=0;frames=0;trace_items=0;trace_bytes=0;state_items=0;temporary_items=0;snapshot_items=0} in
  let rec history_preflight previous count = function
    | [] -> previous
    | frame :: rest ->
        charge budget 1;
        bounded "synthetic_frame_limit" "input history" count default_limits.max_frames 1;
        charge budget (D.Input_frame.canonical_size frame);
        let time = D.Input_frame.time frame in
        (match previous with
         | None -> Diagnostic.require (N.equal time N.zero) "synthetic_history"
             "Model history must start at zero with strictly increasing times."
         | Some previous -> Diagnostic.require (N.compare previous time < 0) "synthetic_history"
             "Model history must start at zero with strictly increasing times.");
        history_preflight (Some time) (count + 1) rest in
  let last = history_preflight None 0 history in
  let last = match last with Some last -> last | None -> Diagnostic.fail "synthetic_history"
      "Model history requires ModelInputFrame records starting at zero." in
  let horizon = match until with None -> last | Some value ->
      (try N.check_finite value with Diagnostic.Error _ -> Diagnostic.fail "synthetic_horizon" "Model horizon must be finite.") in
  Diagnostic.require (N.compare horizon N.zero >= 0) "synthetic_horizon" "Model horizon must be nonnegative.";
  let session = prepare budget program in
  let fingerprint = M.fingerprint program in
  let envelope = Json.Object ["schema_version",Json.String D.Trace.schema_version;"frames",Json.Array [];
      "horizon",N.to_json horizon;"program_fingerprint",Json.String fingerprint;"model_version",Json.String runner_version] in
  reserve budget ~items:11 ~bytes:(String.length (Canonical.encode envelope));
  let rec loop now pending frames =
    charge budget 1;
    let pending = match pending with
      | frame :: rest when N.equal (D.Input_frame.time frame) now -> update budget session frame;rest
      | _ -> pending in
    let frame = step budget session now in
    let frames = frame :: frames in
    if N.equal now horizon then List.rev frames else
      let external_time = match pending with [] -> None | frame :: _ -> Some (D.Input_frame.time frame) in
      loop (next_time budget session now horizon external_time) pending frames in
  let frames = loop N.zero history [] in
  let trace = D.Trace.make ~frames ~horizon ~program_fingerprint:fingerprint () in
  let usage : usage = {work=budget.work;frames=budget.frames;trace_items=budget.trace_items;trace_bytes=budget.trace_bytes} in
  trace,usage
let run ?until ?limits program history = fst (run_with_usage ?until ?limits program history)
