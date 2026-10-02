open Bioc_wire
open Bioc_domain
module B = Behavior
module N = Runtime_number
module D = Execution_data
module Names = Map.Make (String)
module Name_set = Set.Make (String)

type budget = { max_work : int; max_frames : int; max_trace_items : int }
let make_budget ?(max_work = 10_000_000) ?(max_frames = 10_000) ?(max_trace_items = 100_000) () =
  Diagnostic.require (max_work > 0 && max_frames > 0 && max_trace_items > 0)
    "evaluation_budget" "Execution budgets must be positive integers.";
  { max_work; max_frames; max_trace_items }
let default_budget = make_budget ()
let budget_json value = Json.Object [
    "max_work", Json.int value.max_work; "max_frames", Json.int value.max_frames;
    "max_trace_items", Json.int value.max_trace_items;
    "max_json_values", Json.int Limits.max_json_nodes; "max_json_bytes", Json.int Limits.max_response_bytes]
let evaluator_version = "biocompiler.ocaml.reference.v0.1"
type usage = { work : int; frames : int; trace_items : int }
let id node = Identity.Node.to_string (B.node_id node)
let refs node = List.map Identity.Node.to_string (B.inputs node)
let owner node = Option.map Identity.Role.to_string (B.role node)
let requirement_ids node = List.map Identity.Requirement.to_string (B.requirement_ids node)
let fail = Diagnostic.fail
let require = Diagnostic.require
let node_error node code message = fail ~path:("/nodes/" ^ id node) code message
let contextual node code operation =
  match operation () with
  | result -> result
  | exception Diagnostic.Error diagnostic when List.mem diagnostic.code
      ["evaluation_numeric_type"; "evaluation_nonfinite"; "evaluation_overflow";
       "evaluation_division_by_zero"; "evaluation_nonadvancing_time"] ->
      node_error node code (diagnostic.code ^ ": " ^ diagnostic.message)
let output_record operation =
  match operation () with
  | result -> result
  | exception Diagnostic.Error diagnostic when diagnostic.code = "execution_data_limit" ->
      fail "evaluation_output_limit" "Complete execution trace exceeds its native data boundary."
let typed_state_equal left right = match left, right with
  | B.Text a, B.Text b -> a = b
  | B.Boolean a, B.Boolean b -> a = b
  | B.State_integer a, B.State_integer b -> Z.equal a b
  | B.State_real a, B.State_real b -> a = b
  | _ -> false

type expression = Numeric of N.t | Logical of bool
type binding = string option
type value_key = string * binding
type timer_key = string * string * binding
type session = {
  nodes : B.node Names.t;
  local : B.node list;
  rules : B.node list;
  memory_nodes : B.node list;
  state_nodes : B.node list;
  role : string;
  max_microsteps : int;
  budget : budget;
  mutable work : int;
  mutable trace_items : int;
  states : (string, B.state_value) Hashtbl.t;
  mutable memories : (string, bool) Hashtbl.t;
  mutable memory_working : (string, bool) Hashtbl.t option;
  previous : (timer_key, bool) Hashtbl.t;
  held : (value_key, N.t) Hashtbl.t;
  recent : (value_key, N.t) Hashtbl.t;
  first_events : (value_key, N.t list) Hashtbl.t;
  (* Preserve dictionary insertion order: equal mixed numeric deadlines must
     select the same first operand as Python's scheduler min(). *)
  mutable timers : (timer_key * N.t) list;
  pulses : (timer_key, N.t * N.t) Hashtbl.t;
  mutable input : D.Input_frame.t;
  mutable time : N.t;
  cache : (value_key, expression) Hashtbl.t;
  mutable events : D.Event.t list;
  required : (string * string list) list;
  integral_history : (string, (N.t * N.t) list) Hashtbl.t;
}
let charge session amount =
  require (amount >= 0 && amount <= session.budget.max_work - session.work)
    "evaluation_work_limit" "Cumulative reference execution work budget exhausted.";
  session.work <- session.work + amount
let trace_item (session : session) =
  require (session.trace_items < session.budget.max_trace_items)
    "evaluation_output_limit" "Cumulative action/event allocation budget exhausted.";
  session.trace_items <- session.trace_items + 1
let charge_json session document =
  let pending = ref [document] in
  while !pending <> [] do
    charge session 1;
    let current = List.hd !pending in pending := List.tl !pending;
    match current with
    | Json.String value -> charge session (String.length value)
    | Json.Array values -> charge session (List.length values); pending := values @ !pending
    | Json.Object fields ->
        List.iter (fun (key, _) -> charge session (String.length key + 1)) fields;
        pending := List.map snd fields @ !pending
    | _ -> ()
  done
let find session identity =
  charge session 1;
  match Names.find_opt identity session.nodes with
  | Some node -> node | None -> fail "evaluation_expression" "Unknown validated expression identity."
let reference node index = Identity.Node.to_string (List.nth (B.inputs node) index)
let executable_refs node = match B.operation node with
  | B.Signature _ -> [reference node 0] | _ -> refs node
let is_memory node = match B.operation node with B.Memory _ -> true | _ -> false
let is_observation node = match B.operation node with B.Signal _ | B.Channel_observation -> true | _ -> false
let is_rule node = match B.operation node with B.Rule _ -> true | _ -> false
let timer_remove session key =
  charge session (List.length session.timers + 1);
  session.timers <- List.remove_assoc key session.timers
let timer_set session key deadline =
  charge session (List.length session.timers + 1);
  let found = ref false in
  let timers = List.map (fun (old, value) ->
      if old = key then (found := true; old, deadline) else old, value) session.timers in
  session.timers <- if !found then timers else timers @ [key, deadline]
let deadline session node key duration =
  let value = contextual node "evaluation_timer" (fun () -> N.advance session.time duration) in
  timer_set session key value;
  value
let onset session kind identity binding value =
  charge session 1;
  let key = kind, identity, binding in
  let before = Option.value ~default:false (Hashtbl.find_opt session.previous key) in
  Hashtbl.replace session.previous key value;
  value && not before
let bindings session node =
  if B.contact_bound node then (
    charge session (List.length (D.Input_frame.contacts session.input));
    D.Input_frame.contacts session.input |> List.map fst
    |> List.sort (fun a b -> charge session 1; String.compare a b) |> List.map Option.some)
  else [None]
let samples session = function
  | None -> D.Input_frame.signals session.input
  | Some identity ->
      charge session (List.length (D.Input_frame.contacts session.input) + 1);
      Option.value ~default:[] (List.assoc_opt identity (D.Input_frame.contacts session.input))
let find_sample session reference samples =
  charge session (List.length samples + 1);
  List.assoc_opt reference samples
let band_name = function B.Present -> "present" | B.High -> "high" | B.Low -> "low"
let sample_band sample = function B.Present -> D.Sample.present sample | B.High -> D.Sample.high sample | B.Low -> D.Sample.low sample
let sample_has sample = function
  | "value" -> Option.is_some (D.Sample.value sample)
  | "present" -> Option.is_some (D.Sample.present sample)
  | "high" -> Option.is_some (D.Sample.high sample)
  | "low" -> Option.is_some (D.Sample.low sample)
  | _ -> assert false

let make_session program role max_microsteps budget =
  let all = B.nodes program in
  let nodes = List.fold_left (fun result node -> Names.add (id node) node result) Names.empty all in
  let initial_work = ref 0 in
  let work amount =
    require (amount >= 0 && amount <= budget.max_work - !initial_work)
      "evaluation_work_limit" "Reference execution graph preparation exceeds its work budget.";
    initial_work := !initial_work + amount in
  let live = ref Name_set.empty in
  let pending = ref (B.roots program |> List.map Identity.Node.to_string |> List.filter (fun identity ->
      let value = owner (Names.find identity nodes) in value = None || value = Some role)) in
  while !pending <> [] do
    work 1;
    let identity = List.hd !pending in pending := List.tl !pending;
    if not (Name_set.mem identity !live) then (
      live := Name_set.add identity !live;
      let inputs = executable_refs (Names.find identity nodes) in work (List.length inputs);
      pending := inputs @ !pending)
  done;
  let local = List.filter (fun node ->
      work 1; Name_set.mem (id node) !live && (owner node = None || owner node = Some role)) all in
  let memory_nodes = List.filter is_memory local in
  let dependencies node =
    let pending = ref (refs node) and seen = ref Name_set.empty and result = ref Name_set.empty in
    while !pending <> [] do
      work 1;
      let identity = List.hd !pending in pending := List.tl !pending;
      if not (Name_set.mem identity !seen) then (
        seen := Name_set.add identity !seen;
        let dependency = Names.find identity nodes in
        if is_memory dependency then result := Name_set.add identity !result
        else let inputs = executable_refs dependency in work (List.length inputs); pending := inputs @ !pending)
    done;
    Name_set.elements !result in
  let ordered = ref [] and visited = ref Name_set.empty and visiting = ref Name_set.empty in
  List.iter (fun start ->
      let pending = ref [id start, false] in
      while !pending <> [] do
        work 1;
        let identity, closing = List.hd !pending in pending := List.tl !pending;
        if closing then (
          visiting := Name_set.remove identity !visiting;
          visited := Name_set.add identity !visited;
          ordered := Names.find identity nodes :: !ordered)
        else if not (Name_set.mem identity !visited) then (
          require (not (Name_set.mem identity !visiting)) "evaluation_memory_cycle" "Memory controls contain a dependency cycle.";
          visiting := Name_set.add identity !visiting;
          let dependencies = dependencies (Names.find identity nodes) in
          pending := List.map (fun identity -> identity, false) dependencies @ ((identity, true) :: !pending))
      done) memory_nodes;
  let memory_nodes = List.rev !ordered in
  let states = Hashtbl.create 16 and memories = Hashtbl.create 16 in
  let state_nodes = List.filter (fun node -> match B.operation node with B.State _ -> true | _ -> false) local in
  List.iter (fun node -> match B.operation node with B.State value -> Hashtbl.add states (id node) value.initial | _ -> assert false) state_nodes;
  List.iter (fun node -> Hashtbl.add memories (id node) false) memory_nodes;
  let required = ref Names.empty in
  let add_required identity field =
    let fields = Option.value ~default:[] (Names.find_opt identity !required) in
    if not (List.mem field fields) then required := Names.add identity (fields @ [field]) !required in
  List.iter (fun node ->
      work 1;
      match B.operation node with
      | B.Qualitative band -> add_required (reference node 0) (band_name band)
      | B.Signature _ | B.Scope _ | B.Role _ -> ()
      | _ -> List.iter (fun identity -> work 1; if is_observation (Names.find identity nodes) then add_required identity "value") (refs node)) local;
  let integral_history = Hashtbl.create 8 in
  List.iter (fun node -> match B.operation node with
      | B.Integrated -> Hashtbl.replace integral_history (reference node 0) [] | _ -> ()) local;
  { nodes; local; rules = List.filter is_rule local; memory_nodes; state_nodes; role; max_microsteps; budget;
    work = !initial_work; trace_items = 0; states; memories; memory_working = None;
    previous = Hashtbl.create 32; held = Hashtbl.create 16; recent = Hashtbl.create 16;
    first_events = Hashtbl.create 16; timers = []; pulses = Hashtbl.create 16;
    input = D.Input_frame.make ~time:N.zero (); time = N.zero; cache = Hashtbl.create 32; events = [];
    required = Names.bindings !required; integral_history }

let update_input session frame =
  let contacts = List.map fst (D.Input_frame.contacts frame) |> Name_set.of_list in
  let disappeared = D.Input_frame.contacts session.input |> List.map fst |> Name_set.of_list
      |> fun old -> Name_set.diff old contacts in
  let gone = function None -> false | Some identity -> Name_set.mem identity disappeared in
  let clear mapping binding =
    let doomed = Hashtbl.fold (fun key _ result -> charge session 1; if gone (binding key) then key :: result else result) mapping [] in
    List.iter (Hashtbl.remove mapping) doomed in
  clear session.previous (fun (_, _, binding) -> binding);
  clear session.pulses (fun (_, _, binding) -> binding);
  clear session.held snd; clear session.recent snd; clear session.first_events snd;
  session.timers <- List.filter (fun ((_, _, binding), _) -> charge session 1; not (gone binding)) session.timers;
  let observations = (None, D.Input_frame.signals frame)
      :: List.map (fun (identity, samples) -> Some identity, samples) (D.Input_frame.contacts frame) in
  List.iter (fun (identity, samples) ->
      List.iter (fun (reference, _) ->
          charge session 1;
          let node = match Names.find_opt reference session.nodes with
            | Some node when is_observation node && owner node = Some session.role -> node
            | _ -> fail "evaluation_observation" "Unknown signal for the selected role." in
          if B.contact_bound node <> Option.is_some identity then
            node_error node "evaluation_scope" "Signal supplied in the wrong observation scope.") samples;
      List.iter (fun (reference, fields) ->
          charge session 1;
          let node = find session reference in
          if B.contact_bound node = Option.is_some identity then (
            let sample = match find_sample session reference samples with
              | Some sample -> sample | None -> node_error node "evaluation_observation" "Missing required observation." in
            List.iter (fun field ->
                if not (sample_has sample field) then node_error node "evaluation_observation" ("Missing explicit " ^ field ^ " observation.")) fields)) session.required) observations;
  let retained_histories = Hashtbl.fold (fun reference history result ->
      charge session 1; (reference, history) :: result) session.integral_history [] in
  List.iter (fun (reference, history) ->
      charge session 1;
      let node = find session reference in
      let amount = match find_sample session reference (D.Input_frame.signals frame) with
        | Some sample -> (match D.Sample.value sample with Some value -> value
            | None -> node_error node "evaluation_integration" "Rolling integration requires numeric observations.")
        | None -> node_error node "evaluation_integration" "Rolling integration requires numeric observations." in
      if N.compare amount N.zero < 0 then
        node_error node "evaluation_integration" "Rolling integration requires nonnegative observations.";
      (* Reverse chronological retention makes insertion bounded; iteration
         below restores the original Python summation order. *)
      Hashtbl.replace session.integral_history reference ((D.Input_frame.time frame, amount) :: history)) retained_histories;
  session.input <- frame

let normalize_binding node binding = if B.contact_bound node then binding else None
let expression_refs node = match B.operation node with
  | B.Integrated -> [reference node 1]
  | B.Signature _ | B.Not | B.Became_true -> [reference node 0]
  | B.And | B.Or | B.At_least _ | B.Arithmetic _ | B.Compare _
  | B.Held_for | B.Recently | B.Followed_by -> refs node
  | _ -> []
let value session identity binding =
  let pending = ref [identity, binding, false] in
  let cached reference binding =
    let node = find session reference in
    match Hashtbl.find_opt session.cache (reference, normalize_binding node binding) with
    | Some value -> value | None -> node_error node "evaluation_expression" "Expression dependency was not evaluated." in
  let numeric node = function Numeric value -> value | _ -> node_error node "evaluation_expression" "Expected a numeric expression." in
  let logical node = function Logical value -> value | _ -> node_error node "evaluation_expression" "Expected a condition or event." in
  while !pending <> [] do
    charge session 1;
    let identity, binding, closing = List.hd !pending in pending := List.tl !pending;
    let node = find session identity in
    let binding = normalize_binding node binding in
    let key = identity, binding in
    if not (Hashtbl.mem session.cache key) then (
      if B.contact_bound node && binding = None then
        node_error node "evaluation_expression" "A contacted-object binding is required.";
      if not closing then (
        let dependencies = expression_refs node in charge session (List.length dependencies);
        pending := List.map (fun reference -> reference, binding, false) dependencies @ ((identity, binding, true) :: !pending))
      else (
        let arg index = cached (reference node index) binding in
        let number index = numeric node (arg index) and boolean index = logical node (arg index) in
        let result = match B.operation node with
          | B.Literal value -> Numeric (B.binding_value value)
          | B.Parameter value -> Numeric (B.binding_value value.default)
          | B.Signal _ | B.Channel_observation ->
              (match Option.bind (find_sample session identity (samples session binding)) D.Sample.value with
               | Some value -> Numeric value | None -> node_error node "evaluation_observation" "Missing numeric observation.")
          | B.Integrated ->
              let result = contextual node "evaluation_integration" (fun () ->
                  let duration = number 1 in
                  let left = N.max N.zero (N.sub session.time duration) in
                  let history = Hashtbl.find session.integral_history (reference node 0) |> List.rev in
                  let rec areas acc = function
                    | [] -> List.rev acc
                    | (start, amount) :: remaining ->
                        charge session 1;
                        let finish = match remaining with (next, _) :: _ -> next | [] -> session.time in
                        let interval = N.sub (N.min finish session.time) (N.max start left) in
                        let acc = if N.compare interval N.zero > 0 then N.mul interval amount :: acc else acc in
                        areas acc remaining in
                  N.fsum (areas [] history)) in Numeric result
          | B.Qualitative band ->
              (match find_sample session (reference node 0) (samples session binding) with
               | Some sample -> (match sample_band sample band with Some value -> Logical value
                   | None -> node_error node "evaluation_observation" ("Missing explicit " ^ band_name band ^ " observation."))
               | None -> node_error node "evaluation_observation" "Missing qualitative observation.")
          | B.And | B.Or | B.At_least _ ->
              let values = List.map (fun reference -> logical node (cached reference binding)) (refs node) in
              Logical (match B.operation node with
                  | B.And -> List.for_all Fun.id values | B.Or -> List.exists Fun.id values
                  | B.At_least count -> List.fold_left (fun total value -> total + (if value then 1 else 0)) 0 values >= count
                  | _ -> assert false)
          | B.Not -> Logical (not (boolean 0))
          | B.Arithmetic operation ->
              Numeric (contextual node "evaluation_arithmetic" (fun () ->
                  match operation with
                  | B.Add -> N.add (number 0) (number 1) | B.Subtract -> N.sub (number 0) (number 1)
                  | B.Multiply -> N.mul (number 0) (number 1) | B.Divide -> N.div (number 0) (number 1)
                  | B.Negate -> N.neg (number 0)))
          | B.Compare operation ->
              let comparison = N.compare (number 0) (number 1) in
              Logical (match operation with B.Lt -> comparison < 0 | B.Le -> comparison <= 0
                  | B.Gt -> comparison > 0 | B.Ge -> comparison >= 0 | B.Eq -> comparison = 0 | B.Ne -> comparison <> 0)
          | B.Signature _ -> arg 0
          | B.State_is desired -> Logical (typed_state_equal (Hashtbl.find session.states (reference node 0)) desired)
          | B.Memory _ | B.Memory_is_set ->
              let memories = Option.value ~default:session.memories session.memory_working in
              Logical (Hashtbl.find memories (if is_memory node then identity else reference node 0))
          | B.Held_for ->
              let active, duration = boolean 0, number 1 in
              let timer_key = "held_for", identity, binding in
              if active then (
                if not (Hashtbl.mem session.held key) then (
                  Hashtbl.replace session.held key session.time;
                  ignore (deadline session node timer_key duration));
                let finish = contextual node "evaluation_timer" (fun () -> N.add (Hashtbl.find session.held key) duration) in
                let ready = N.compare session.time finish >= 0 in
                if ready then timer_remove session timer_key;
                Logical ready)
              else (Hashtbl.remove session.held key; timer_remove session timer_key; Logical false)
          | B.Recently ->
              let active, duration = boolean 0, number 1 in
              let timer_key = "recently", identity, binding in
              let previous_key = "recent_input", identity, binding in
              let was_active = Option.value ~default:false (Hashtbl.find_opt session.previous previous_key) in
              Hashtbl.replace session.previous previous_key active;
              if active then (
                Hashtbl.remove session.recent key; timer_remove session timer_key; Logical true)
              else (
                if was_active then Hashtbl.replace session.recent key (deadline session node timer_key duration);
                let finish = Option.value ~default:session.time (Hashtbl.find_opt session.recent key) in
                let active = N.compare session.time finish < 0 in
                if not active then timer_remove session timer_key;
                Logical active)
          | B.Became_true -> Logical (onset session "event" identity binding (boolean 0))
          | B.Followed_by ->
              let first, second, duration = boolean 0, boolean 1, number 2 in
              let earliest = contextual node "evaluation_timer" (fun () -> N.sub session.time duration) in
              let times = Option.value ~default:[] (Hashtbl.find_opt session.first_events key)
                  |> List.filter (fun time -> charge session 1; N.compare time earliest >= 0) in
              let occurred = second && List.exists (fun time -> charge session 1; N.compare time session.time < 0) times in
              let times = if first && (match List.rev times with [] -> true | latest :: _ -> not (N.equal latest session.time))
                then times @ [session.time] else times in
              Hashtbl.replace session.first_events key times;
              Logical occurred
          | B.Role _ | B.Scope _ | B.Channel _ | B.State _ | B.Secretion _ | B.Rule _
          | B.Action_state_set _ | B.Action_report _ | B.Action_pulse | B.Action_eliminate | B.Action_engulf
          | B.Action_secrete _ | B.Action_emit _ | B.Action_present _ | B.Action_retain _
          | B.Action_expand | B.Action_rest | B.Action_differentiate _ ->
              node_error node "evaluation_expression" "A declaration or action cannot be evaluated as an expression." in
        Hashtbl.replace session.cache key result;
        (match B.operation node, result with
         | (B.Became_true | B.Followed_by), Logical true ->
             trace_item session;
             charge_json session (B.node_json node);
             let event = output_record (fun () -> D.Event.make ~node_id:identity ?contact_id:binding
                 ~requirement_ids:(requirement_ids node) ?source:(B.source node) ()) in
             session.events <- event :: session.events
         | _ -> ())))
  done;
  cached identity binding
let numeric_value session identity binding = match value session identity binding with
  | Numeric value -> value | _ -> node_error (find session identity) "evaluation_expression" "Expected numeric value."
let condition_value session identity binding = match value session identity binding with
  | Logical value -> value | _ -> node_error (find session identity) "evaluation_expression" "Expected condition or event."

let update_memory session node updates =
  let inputs = match B.operation node with B.Memory memory -> List.combine memory.input_names (refs node) | _ -> assert false in
  let setting = find session (List.assoc B.Set_when inputs) in
  let setting_onset = ref false in
  List.iter (fun binding ->
      charge session 1;
      let current = condition_value session (id setting) binding in
      let edge = onset session "memory_set" (id node) binding current in
      setting_onset := edge || !setting_onset) (bindings session setting);
  let reset = match List.assoc_opt B.Reset_when inputs with
    | None -> false
    | Some identity ->
        let resetting = find session identity in
        let values = List.map (fun binding -> charge session 1; condition_value session identity binding) (bindings session resetting) in
        List.exists Fun.id values in
  let timer_key = "memory", id node, None in
  if reset then (Hashtbl.replace updates (id node) false; timer_remove session timer_key)
  else if !setting_onset then (
    Hashtbl.replace updates (id node) true;
    Option.iter (fun duration -> ignore (deadline session node timer_key (numeric_value session duration None)))
      (List.assoc_opt B.Duration_input inputs))
  else (
    charge session (List.length session.timers + 1);
    match List.assoc_opt timer_key session.timers with
    | Some finish when N.compare finish session.time <= 0 ->
        Hashtbl.replace updates (id node) false; timer_remove session timer_key
    | _ -> Hashtbl.replace updates (id node) (Hashtbl.find session.memories (id node)))
let memory_updates session =
  charge session (Hashtbl.length session.memories + 1);
  let updates = Hashtbl.copy session.memories in
  session.memory_working <- Some updates;
  Fun.protect ~finally:(fun () -> session.memory_working <- None) (fun () ->
      List.iter (fun node ->
          charge session 1; Hashtbl.clear session.cache; update_memory session node updates) session.memory_nodes);
  updates

let request session rule action binding ?started_at ?expires_at ?specification () =
  trace_item session;
  charge_json session (B.node_json action);
  charge_json session (B.node_json rule);
  let attributes = Json.object_fields (B.attributes action) in
  let attributes, values = match B.operation action with
    | B.Action_secrete _ ->
        let secretion = find session (reference action 0) in
        let product = match B.operation secretion with B.Secretion value -> value.product | _ -> assert false in
        let values = if List.length (B.inputs action) > 1 then
            ["rate", N.to_json (numeric_value session (reference action 1) binding)] else [] in
        ("product", Json.String product) :: ("secretion_id", Json.String (id secretion)) :: attributes, values
    | B.Action_emit _ ->
        let channel = find session (reference action 1) in
        let name = match B.operation channel with B.Channel value -> value.name | _ -> assert false in
        let values = if List.length (B.inputs action) = 3 then
            ["value", N.to_json (numeric_value session (reference action 2) binding)] else [] in
        ("channel_id", Json.String (id channel)) :: ("channel_name", Json.String name) :: attributes, values
    | _ -> attributes, [] in
  let requirements = requirement_ids rule @ requirement_ids action |> List.sort_uniq String.compare in
  charge session (List.length requirements + 1);
  let specification = Option.value ~default:action specification in
  charge_json session (B.node_json specification);
  output_record (fun () -> D.Action.make ~action_id:(id action) ~rule_id:(id rule) ~kind:(B.kind_name (B.operation action))
    ?contact_id:binding ~attributes:(Json.Object attributes) ~values:(Json.Object values)
    ~requirement_ids:requirements ?source:(B.source action) ?rule_source:(B.source rule)
    ?started_at ?expires_at ~specification_id:(id specification) ?specification_source:(B.source specification) ())
let ongoing = function
  | B.Action_eliminate | B.Action_engulf | B.Action_secrete _ | B.Action_emit _ | B.Action_present _
  | B.Action_retain _ | B.Action_expand | B.Action_rest | B.Action_differentiate _ | B.Action_pulse -> true
  | B.Action_state_set _ | B.Action_report _ -> false
  | _ -> false
let step session time =
  session.time <- time;
  session.events <- [];
  let reactions = ref [] and microstep = ref 0 and result = ref None in
  while !result = None && !microstep < session.max_microsteps do
    charge session 1;
    Hashtbl.clear session.cache;
    let updates = memory_updates session in
    let changed = List.exists (fun node ->
        charge session 1; Hashtbl.find updates (id node) <> Hashtbl.find session.memories (id node)) session.memory_nodes in
    if changed then (
      session.memories <- updates;
      incr microstep;
      require (!microstep < session.max_microsteps) "evaluation_nonconvergence"
        "Behavior exhausted its same-time microstep budget during memory settlement.");
    incr microstep;
    Hashtbl.clear session.cache;
    (* Every used condition/event is evaluated, even behind a false guard. *)
    List.iter (fun node ->
        charge session 1;
        match B.data_type node with
        | Some dtype when (Type_spec.kind dtype = Type_spec.Condition || Type_spec.kind dtype = Type_spec.Event) && not (is_memory node) ->
            List.iter (fun binding -> charge session 1; ignore (value session (id node) binding)) (bindings session node)
        | _ -> ()) session.local;
    let writes = Hashtbl.create 16 and active = ref [] in
    List.iter (fun rule ->
        charge session 1;
        let guard = find session (reference rule 1) in
        let guard_values = List.map (fun binding ->
            charge session 1; binding, condition_value session (id guard) binding) (bindings session guard) in
        let activations = Hashtbl.create 8 in
        let actions = match refs rule with _ :: _ :: actions -> actions | _ -> assert false in
        List.iter (fun identity ->
            let action = find session identity in
            List.iter (fun binding ->
                charge session 1;
                let enabled, trigger = match Hashtbl.find_opt activations binding with
                  | Some activation -> activation
                  | None ->
                      charge session (List.length guard_values + 1);
                      let enabled = if B.contact_bound guard && Option.is_some binding then
                          Option.value ~default:false (List.assoc_opt binding guard_values)
                        else List.exists snd guard_values in
                      let trigger = match B.operation rule with
                        | B.Rule { trigger = B.Event_trigger; _ } -> enabled
                        | B.Rule _ -> onset session "rule" (id rule) binding enabled
                        | _ -> assert false in
                      Hashtbl.add activations binding (enabled, trigger);
                      enabled, trigger in
                match B.operation action with
                | B.Action_state_set desired ->
                    if enabled then (
                      let state_id = reference action 0 in
                      (match Hashtbl.find_opt writes state_id with
                       | Some (previous, previous_rule) when not (typed_state_equal previous desired) ->
                           node_error action "evaluation_state_conflict"
                             ("Conflicting assignments to state " ^ state_id ^ " by rules " ^ previous_rule ^ " and " ^ id rule ^ ".")
                       | _ -> ());
                      Hashtbl.replace writes state_id (desired, id rule))
                | B.Action_pulse ->
                    let key = id rule, id action, binding in
                    let timer_key = "pulse", id rule ^ ":" ^ id action, binding in
                    if trigger then (
                      let duration = numeric_value session (reference action 1) binding in
                      let finish = deadline session action timer_key duration in
                      Hashtbl.replace session.pulses key (time, finish));
                    (match Hashtbl.find_opt session.pulses key with
                     | Some (start, finish) when N.compare time finish < 0 ->
                         let primitive = find session (reference action 0) in
                         active := request session rule primitive binding ~started_at:start ~expires_at:finish ~specification:action () :: !active
                     | Some _ -> Hashtbl.remove session.pulses key; timer_remove session timer_key
                     | None -> ())
                | operation when ongoing operation ->
                    if enabled then active := request session rule action binding () :: !active
                | B.Action_report _ ->
                    if trigger then reactions := request session rule action binding ~started_at:time () :: !reactions
                | _ -> node_error action "evaluation_expression" "Rule contains a non-action operation.")
              (bindings session action)) actions) session.rules;
    let changed = Hashtbl.fold (fun identity (desired, _) changed ->
        charge session 1;
        let different = not (typed_state_equal (Hashtbl.find session.states identity) desired) in
        changed || different) writes false in
    Hashtbl.iter (fun identity (desired, _) -> Hashtbl.replace session.states identity desired) writes;
    if not changed then (
      let states = List.map (fun node -> id node, Hashtbl.find session.states (id node)) session.state_nodes in
      let memories = List.map (fun node -> id node, Hashtbl.find session.memories (id node)) session.memory_nodes in
      result := Some (output_record (fun () -> D.Frame.make ~time ~actions:(List.rev !active) ~reactions:(List.rev !reactions)
          ~events:(List.rev session.events) ~states ~memories ~microsteps:!microstep)))
  done;
  match !result with Some frame -> frame
    | None -> fail "evaluation_nonconvergence" "Behavior did not converge within its same-time microstep budget."

let select_role program selected =
  let roles = List.filter (fun node -> match B.operation node with B.Role _ -> true | _ -> false) (B.nodes program) in
  match selected with
  | None -> (match roles with [node] -> id node
      | _ -> fail "evaluation_role" "Select a role explicitly unless the program has exactly one role.")
  | Some requested ->
      let matches = List.filter (fun node -> id node = requested
          || match B.operation node with B.Role value -> value.name = requested | _ -> false) roles in
      match matches with [node] -> id node
        | _ -> fail "evaluation_role" "Unknown or ambiguous role identity/name."

let evaluate_with_usage ?role ?until ?(max_microsteps = 1000) ?(budget = default_budget) program history =
  require (max_microsteps > 0) "evaluation_microsteps" "max_microsteps must be a positive integer.";
  require (List.length (B.nodes program) <= budget.max_work && List.length history <= budget.max_work)
    "evaluation_work_limit" "Input graph or history exceeds the reference execution work budget.";
  let selected = select_role program role in
  let last = match history with
    | [] -> fail "evaluation_history" "History requires at least one snapshot starting at zero."
    | first :: remaining ->
        require (N.equal (D.Input_frame.time first) N.zero) "evaluation_history" "History must start at numeric zero.";
        List.fold_left (fun previous current ->
            require (N.compare (D.Input_frame.time current) (D.Input_frame.time previous) > 0)
              "evaluation_history" "Input timestamps must be strictly increasing.";
            current) first remaining in
  let horizon = match until with None -> D.Input_frame.time last
    | Some value -> (match N.check_finite value with value -> value
        | exception Diagnostic.Error _ -> fail "evaluation_horizon" "Evaluation horizon must be finite.") in
  require (N.compare horizon N.zero >= 0) "evaluation_horizon" "Evaluation horizon must be nonnegative.";
  let session = make_session program selected max_microsteps budget in
  charge session (List.length history);
  let integral_step = if Hashtbl.length session.integral_history = 0 then None else (
      let policies = Json.object_fields (B.policies program) in
      let step = Json.field "integral_step" policies |> Json.object_fields |> Json.field "canonical_value" |> N.of_json in
      let count = try N.div horizon step with Diagnostic.Error _ ->
          fail "evaluation_integration_limit" "Declared integration grid exceeds its finite sample bound." in
      require (N.compare count (N.of_int (B.max_integral_samples - 1)) <= 0
               && List.length history <= B.max_integral_samples)
        "evaluation_integration_limit" "Declared integration grid exceeds its 10000-sample bound.";
      Some step) in
  let pending_inputs = ref history and results = ref [] and result_count = ref 0 in
  let grid_index = ref 1 and next_grid = ref integral_step and time = ref N.zero in
  (* Reserve a complete result envelope before retaining any frames. Output
     accounting includes every JSON value and every encoded byte cumulatively. *)
  let output_values = ref 128 and output_bytes = ref 1024 in
  let retain frame =
    let json = D.Frame.to_json frame in
    let pending = ref [json] in
    while !pending <> [] do
      charge session 1;
      require (!output_values < Limits.max_json_nodes) "evaluation_output_limit" "Complete trace exceeds the JSON value budget.";
      incr output_values;
      let current = List.hd !pending in pending := List.tl !pending;
      match current with
      | Json.Array items -> pending := items @ !pending
      | Json.Object fields ->
          let keys = List.length fields in
          require (keys <= Limits.max_json_nodes - !output_values)
            "evaluation_output_limit" "Complete trace exceeds the native JSON key/value budget.";
          output_values := !output_values + keys;
          pending := List.map snd fields @ !pending
      | _ -> ()
    done;
    let bytes = String.length (Canonical.encode json) + 1 in
    require (bytes <= Limits.max_response_bytes - !output_bytes)
      "evaluation_output_limit" "Complete trace exceeds the encoded byte budget.";
    output_bytes := !output_bytes + bytes;
    results := frame :: !results;
    incr result_count in
  let finished = ref false in
  while not !finished do
    charge session 1;
    if integral_step <> None then
      require (!result_count < B.max_integral_samples) "evaluation_integration_limit"
        "Combined integration input/timer/grid observations exceed the 10000-sample bound.";
    require (!result_count < budget.max_frames) "evaluation_output_limit" "Reference trace frame budget exhausted.";
    (match !pending_inputs with
     | frame :: remaining when N.equal (D.Input_frame.time frame) !time ->
         update_input session frame; pending_inputs := remaining
     | _ -> ());
    retain (step session !time);
    if N.equal !time horizon then finished := true
    else (
      let next = ref horizon in
      let consider value = next := N.min !next value in
      (match integral_step, !next_grid with
       | Some interval, Some grid ->
           if N.equal !time grid then (
             incr grid_index;
             let next = try N.mul (N.of_int !grid_index) interval with Diagnostic.Error _ ->
                 fail "evaluation_integration" "Integration grid time is not finite." in
             next_grid := Some next);
           (match !next_grid with Some grid when N.compare !time grid < 0 && N.compare grid horizon <= 0 -> consider grid | _ -> ())
       | _ -> ());
      (match !pending_inputs with
       | frame :: _ when N.compare (D.Input_frame.time frame) horizon <= 0 -> consider (D.Input_frame.time frame)
       | _ -> ());
      List.iter (fun (_, deadline) ->
          charge session 1;
          if N.compare !time deadline < 0 && N.compare deadline horizon <= 0 then consider deadline) session.timers;
      require (N.compare !next !time > 0) "evaluation_timer" "Scheduler must advance representable time.";
      time := !next)
  done;
  let result=output_record (fun () -> D.Result.make ~frames:(List.rev !results) ~role:selected ~horizon
    ~behavior_fingerprint:(B.fingerprint program) ~source_fingerprint:(B.source_fingerprint program)
    ~execution_profile:(Json.field "profile" (Json.object_fields (B.policies program)) |> Json.string)) in
  result,{work=session.work;frames= !result_count;trace_items=session.trace_items}

let evaluate ?role ?until ?max_microsteps ?budget program history =
  fst (evaluate_with_usage ?role ?until ?max_microsteps ?budget program history)
