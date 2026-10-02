open Bioc_wire
open Bioc_domain
module N = Runtime_number
module R = Realization_contract
module E = Realization_evidence
module D = Execution_data
module M = Model_execution_data
module Budget = Realization_budget
module Times = Map.Make (struct type t = N.t let compare = N.compare end)
type episode = { enabled : bool; deadline : N.t option; mutable checked : bool }
type counts = { mutable active : int; mutable inactive : int;
  mutable incomplete : int; mutable cancelled : int }
type 'a cursor = { mutable current : 'a; mutable rest : 'a list }
let cursor = function
  | [] -> Diagnostic.fail "realization_monitor_input" "Fresh monitor traces and history must be nonempty."
  | current :: rest -> {current; rest}
let at budget time_of cursor time =
  let rec advance () = match cursor.rest with
    | next :: rest ->
        Budget.charge budget 1;
        if N.compare (time_of next) time <= 0 then (
          cursor.current <- next; cursor.rest <- rest; advance ())
    | [] -> () in
  advance (); cursor.current
let assoc budget key values =
  let rec find = function [] -> None | (candidate, value) :: rest ->
    Budget.charge budget (1 + String.length key + String.length candidate);
    if candidate = key then Some value else find rest in find values
let contains interval value = match value with
  | Some (M.Number value) -> N.compare (Measurement_contract.Interval.lower interval) value <= 0
      && N.compare value (Measurement_contract.Interval.upper interval) <= 0
  | Some (M.Boolean _) | None -> false
let number = function
  | None -> None | Some (M.Number value) -> Some value
  | Some (M.Boolean _) -> Diagnostic.fail "realization_evidence"
      "Counterexample actual must be a finite number or None."
let add_deadline time delay =
  match time, delay with
  | N.Integer time, N.Integer delay ->
      let sum = Z.add time delay in
      (* Python's math.isfinite(integer) raises on conversion overflow outside
         the ordinary engine failure handler; floating infinity instead yields
         the historical numeric_resolution monitor diagnostic. *)
      Diagnostic.require (Float.is_finite (Z.to_float sum)) "realization_deadline_overflow"
        "int too large to convert to float";
      Some (N.Integer sum)
  | _ ->
      let sum = N.to_float time +. N.to_float delay in
      if Float.is_finite sum then Some (N.Real sum) else None
let check ~budget ~behavior ~contract ~domain ~observation_map ~history ~desired ~actual ~dependencies ~horizon =
  let requirements = R.Behavior_contract.requirements contract in
  let nodes = Hashtbl.create 16 in
  List.iter (fun node -> Budget.charge budget (1 + String.length (Identity.Node.to_string (Behavior.node_id node)));
    Budget.retain_monitor budget 1;
    Hashtbl.add nodes (Identity.Node.to_string (Behavior.node_id node)) node) (Behavior.nodes behavior);
  let outputs = Hashtbl.create 16 in
  List.iter (fun binding -> Budget.charge budget (1 + String.length (Observation_map.Output_binding.requirement_id binding)
      + String.length (Observation_map.Output_binding.mechanism_output_id binding)); Budget.retain_monitor budget 1;
    Hashtbl.replace outputs (Observation_map.Output_binding.requirement_id binding)
      (Observation_map.Output_binding.mechanism_output_id binding)) (Observation_map.outputs observation_map);
  let base = ref Times.empty in
  let add_base time =
    Budget.charge budget 1;
    if not (Times.mem time !base) then (
      Budget.retain_monitor budget 1; base := Times.add time time !base) in
  (* Explicit membership preserves the first number representation for equal
     integer/real keys, including numeric zero, as Python's set does. *)
  add_base N.zero; add_base horizon;
  List.iter (fun frame -> add_base (D.Frame.time frame)) (D.Result.frames desired);
  List.iter (fun frame -> add_base (M.Frame.time frame)) (M.Trace.frames actual);
  List.iter (fun frame -> Budget.charge budget 1;
    if N.compare (D.Input_frame.time frame) horizon <= 0 then add_base (D.Input_frame.time frame)) history;
  let diagnostics = ref [] and counterexamples = ref [] and coverages = ref [] in
  let diagnostic ?requirement ?node code message =
    let source = Option.bind node (fun identity ->
      match Hashtbl.find_opt nodes identity with None -> None | Some value -> Behavior.source value) in
    let value = E.Check_diagnostic.make ~code ~message ?requirement_id:requirement ?node_id:node ?source () in
    Budget.reserve_report budget (E.Check_diagnostic.to_json value);
    diagnostics := value :: !diagnostics in
  if N.compare horizon (Measurement_contract.Scalar.canonical (R.Operating_domain.minimum_horizon domain)) < 0 then
    diagnostic "short_horizon"
      "The supplied horizon is shorter than the operating domain's required observation interval.";
  let outcomes = ref [] in
  List.iter (fun requirement ->
    Budget.charge budget 1;
    let id = R.Response.id requirement and specification = R.Response.specification_id requirement in
    let rule = R.Response.rule_id requirement in
    Budget.charge budget (String.length id + String.length specification + String.length rule);
    let source = match Hashtbl.find_opt nodes specification with Some node -> Behavior.source node
      | None -> Diagnostic.fail "realization_monitor_input" "A checked response specification disappeared." in
    let output = match Hashtbl.find_opt outputs id with Some value -> value
      | None -> Diagnostic.fail "realization_monitor_input" "A checked response output binding disappeared." in
    let counts = {active = 0; inactive = 0; incomplete = 0; cancelled = 0} in
    let episodes = Hashtbl.create 16 and times = ref !base and processed = ref Times.empty in
    let base_count = Times.cardinal !base in
    Budget.retain_monitor budget base_count;
    let inputs = cursor history and source_frames = cursor (D.Result.frames desired)
      and model_frames = cursor (M.Trace.frames actual) in
    let pending time =
      Budget.charge budget 1;
      if not (Times.mem time !processed) && not (Times.mem time !times) then (
        Budget.retain_monitor budget 1; times := Times.add time time !times) in
    while not (Times.is_empty !times) do
      Budget.charge budget 1;
      let key, time = Times.min_binding !times in
      times := Times.remove key !times;
      (* A queued time becomes a processed time, retaining the same one item. *)
      processed := Times.add time time !processed;
      let input = at budget D.Input_frame.time inputs time in
      let bindings = match R.Observable.scope (R.Response.observable requirement) with
        | R.Observable.Cell -> Budget.retain_monitor budget 2; [None]
        | R.Observable.Contact ->
            List.iter (fun _ -> Budget.charge budget 1; Budget.retain_monitor budget 2) (D.Input_frame.contacts input);
            List.map (fun (identity, _) -> Some identity) (D.Input_frame.contacts input)
            |> List.sort (fun left right -> match left, right with
              | Some left, Some right -> Budget.charge budget (1 + String.length left + String.length right);
                  String.compare left right
              | None, None -> 0 | None, Some _ -> -1 | Some _, None -> 1) in
      let present = Hashtbl.create 16 in
      let binding_size = function None -> 0 | Some value -> String.length value in
      List.iter (fun binding -> Budget.charge budget (1 + binding_size binding); Hashtbl.add present binding ()) bindings;
      let vanished = ref [] in
      Hashtbl.iter (fun binding episode ->
        Budget.charge budget (1 + binding_size binding);
        if not (Hashtbl.mem present binding) then (
          if not episode.checked then counts.cancelled <- counts.cancelled + 1;
          Budget.retain_monitor budget 1; vanished := binding :: !vanished)) episodes;
      List.iter (fun binding -> Budget.charge budget (1 + binding_size binding);
        Hashtbl.remove episodes binding; Budget.release_monitor budget 2) !vanished;
      let requests = D.Frame.actions (at budget D.Frame.time source_frames time) in
      let model_frame = at budget M.Frame.time model_frames time in
      List.iter (fun binding ->
        Budget.charge budget (1 + binding_size binding);
        let enabled = List.exists (fun action -> Budget.charge budget (1 + String.length rule + String.length specification
            + String.length (D.Action.rule_id action) + String.length (D.Action.specification_id action)
            + binding_size binding + binding_size (D.Action.contact_id action));
          D.Action.rule_id action = rule && D.Action.specification_id action = specification
          && D.Action.contact_id action = binding) requests in
        let previous = Hashtbl.find_opt episodes binding in
        let episode = match previous with
          | Some episode when episode.enabled = enabled -> episode
          | _ ->
              (match previous with Some previous when not previous.checked ->
                counts.incomplete <- counts.incomplete + 1 | _ -> ());
              let delay = Measurement_contract.Scalar.canonical
                  (if enabled then R.Response.activation requirement else R.Response.deactivation requirement) in
              let deadline = add_deadline time delay in
              let deadline = match deadline with
                | Some deadline when N.compare delay N.zero <= 0 || N.compare deadline time > 0 -> Some deadline
                | _ ->
                    diagnostic ~requirement:id ~node:specification "numeric_resolution"
                      "A response delay cannot be represented as a finite later deadline at this timestamp.";
                    None in
              let episode = {enabled; deadline; checked = false} in
              if previous = None then Budget.retain_monitor budget 1;
              Hashtbl.replace episodes binding episode;
              (match deadline with Some deadline when N.compare deadline horizon <= 0 -> pending deadline | _ -> ());
              episode in
        match episode.deadline with
        | None -> ()
        | Some deadline when N.compare time deadline < 0 -> ()
        | Some _ ->
            let interval = if enabled then R.Response.active requirement else R.Response.inactive requirement in
            let values = match binding with None -> M.Frame.values model_frame
              | Some identity -> Option.value ~default:[] (assoc budget identity (M.Frame.contacts model_frame)) in
            let value = assoc budget output values in
            if not episode.checked then (
              if enabled then counts.active <- counts.active + 1 else counts.inactive <- counts.inactive + 1;
              episode.checked <- true);
            if not (contains interval value) then (
              let example = E.Counterexample.make ~requirement_id:id ~time ?contact_id:binding
                ~state:(if enabled then E.Active else E.Inactive) ~range:interval ?actual:(number value)
                ~rule_id:rule ~specification_id:specification ?source () in
              Budget.reserve_report budget (E.Counterexample.to_json example);
              counterexamples := example :: !counterexamples)) bindings;
      Budget.release_monitor budget (2 * List.length bindings)
    done;
    Hashtbl.iter (fun _ episode -> Budget.charge budget 1;
      if not episode.checked then counts.incomplete <- counts.incomplete + 1) episodes;
    Budget.release_monitor budget (Times.cardinal !processed + Hashtbl.length episodes);
    let coverage = E.Requirement_coverage.make ~requirement_id:id
      ~activation_deadlines_checked:(Z.of_int counts.active)
      ~inactive_deadlines_checked:(Z.of_int counts.inactive)
      ~incomplete_episode_count:(Z.of_int counts.incomplete)
      ~cancelled_episode_count:(Z.of_int counts.cancelled) () in
    Budget.reserve_report budget (E.Requirement_coverage.to_json coverage);
    coverages := coverage :: !coverages;
    Budget.retain_monitor budget 1;
    outcomes := (requirement, counts) :: !outcomes) requirements;
  let outcome = if !counterexamples <> [] then (
      diagnostic "response_violation"
        "Independent model outputs violate one or more response envelopes after their deadlines.";
      E.Fail)
    else (
      List.iter (fun (requirement, counts) ->
        Budget.charge budget 1;
        let requirement_id = R.Response.id requirement and node = R.Response.specification_id requirement in
        if counts.active = 0 then diagnostic ~requirement:requirement_id ~node "unexercised_response"
          "No active response deadline was exercised for this requirement.";
        if counts.inactive = 0 then diagnostic ~requirement:requirement_id ~node "unexercised_inactive_response"
          "No inactive response deadline was exercised for this requirement.";
        if counts.incomplete > 0 then diagnostic ~requirement:requirement_id ~node "incomplete_episode"
          "A response episode ended or the horizon was reached before its response deadline could be checked.") (List.rev !outcomes);
      if !diagnostics = [] then E.Pass else E.Unknown) in
  Budget.release_monitor budget (Hashtbl.length nodes + Hashtbl.length outputs + Times.cardinal !base + List.length !outcomes);
  let result = E.Check_result.make ~outcome ~dependencies
      ~checked_requirement_ids:(List.map R.Response.id requirements)
      ~diagnostics:(List.rev !diagnostics) ~counterexamples:(List.rev !counterexamples)
      ~coverage:(List.rev !coverages) () in
  Budget.validate_report budget result; result
