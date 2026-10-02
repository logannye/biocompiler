open Bioc_wire
open Bioc_domain
module B = Bioc_realization_checker.Realization_budget
module Checked = Bioc_realization_checker.Checked_request
module W = Bioc_checker.Work_budget
module A = Synthetic_authority
module H = Behavior
module M = Mechanism
module C = Realization_contract
module O = Measurement_contract.Observable
module R = Measurement_contract.Response
module SM = Map.Make (String)

let resource_profile = "biocompiler.synthetic_generator.resources.v1"
type error = { message : string; node_id : string option; source : H.source_location option }
exception Unsupported of error
let format_error error = error.message ^
  (match error.node_id with None -> "" | Some id -> " [" ^ id ^ "]") ^
  (match error.source with None -> "" | Some source -> " at " ^ source.file ^ ":" ^ Z.to_string source.line)
let reject ?node message =
  raise (Unsupported {message; node_id = Option.map (fun node -> Identity.Node.to_string (H.node_id node)) node;
    source = (match node with None -> None | Some node -> H.source node)})
type limits = B.limits
let make_limits = B.make_limits
let default_limits = B.default_limits
let limits_json limits = Json.Object ["profile", Json.String resource_profile; "shared", B.limits_json limits;
  "derived_fragments", Json.String "cumulative_report_bytes_nodes_and_shared_work"]
type usage = { work_charged : int; request_bytes : int; report_bytes : int; retained_peak : int }
let str value = Json.String value
let rec height n = if n <= 1 then 1 else 1 + height (n / 2)
let charge_product budget n factor =
  if n > B.remaining budget / factor then B.charge budget (B.remaining budget + 1);
  B.charge budget (n * factor)
let reserve_list budget values =
  let values = B.bounded_list budget values in
  B.retain_monitor budget (List.length values); values
let map budget f values = List.map f (reserve_list budget values)
let array budget f values = Json.Array (map budget f values)
type 'a index = { mutable entries : 'a SM.t; mutable count : int }
let index () = {entries = SM.empty; count = 0}
let lookup budget table key =
  charge_product budget (1 + String.length key) (1 + height table.count);
  SM.find_opt key table.entries
let put budget table key value =
  let fresh = lookup budget table key = None in
  if fresh then B.retain_monitor budget 1;
  charge_product budget (1 + String.length key) (1 + height table.count);
  table.entries <- SM.add key value table.entries;
  if fresh then table.count <- table.count + 1
let bindings budget table =
  B.charge budget table.count; B.retain_monitor budget table.count; SM.bindings table.entries
let get budget table key = match lookup budget table key with Some value -> value | None ->
  Diagnostic.fail "synthetic_generator_reference" ("Missing validated generation reference: " ^ key)
let strings budget values =
  let table = index () in
  List.iter (fun value -> put budget table value ()) (B.bounded_list budget values);
  map budget fst (bindings budget table)
let union budget left right =
  let table = index () in
  List.iter (fun value -> put budget table value ()) (B.bounded_list budget left);
  List.iter (fun value -> put budget table value ()) (B.bounded_list budget right);
  map budget fst (bindings budget table)
let node_id node = Identity.Node.to_string (H.node_id node)
let node_inputs budget node = map budget Identity.Node.to_string (H.inputs node)
let node_requirements budget node = map budget Identity.Requirement.to_string (H.requirement_ids node)
let scope node = if H.contact_bound node then O.Contact else O.Cell
let field key raw = Json.field key (Json.object_fields raw)
let boolean = Type_spec.of_json (Json.Object ["kind",str "condition";"name",str "Condition"])

type policy = { allowed : unit index; maximum : Z.t option; preference : string }
let minimize value = value.preference
let policy_for_request ~budget checked ~profile =
  let build = Realization_request.build_request (Checked.request checked) in
  let constraints = Build_request.implementation_constraints build
  and preferences = Build_request.preferences build in
  B.charge budget (Realization_request.canonical_size (Checked.request checked));
  if List.exists (fun (key, _) -> not (List.mem key ["allowed_operators"; "max_gate_count"])) constraints
  then reject "Unsupported synthetic implementation-constraint fields.";
  if List.exists (fun (key, _) -> key <> "minimize") preferences
  then reject "Unsupported synthetic preference fields.";
  let available = index () in
  List.iter (fun component -> put budget available (A.Component.operation component) ())
    (B.bounded_list budget (A.Catalog.components (A.catalog_for_profile profile)));
  let allowed = index () in
  (match List.assoc_opt "allowed_operators" constraints with
   | None -> List.iter (fun (key, ()) -> put budget allowed key ()) (bindings budget available)
   | Some (Json.Array values) -> List.iter (function
       | Json.String key when lookup budget allowed key = None && lookup budget available key <> None -> put budget allowed key ()
       | _ -> reject "allowed_operators must be unique names in the selected synthetic catalog.")
       (B.bounded_list budget values)
   | Some _ -> reject "allowed_operators must be unique names in the selected synthetic catalog.");
  let maximum = match List.assoc_opt "max_gate_count" constraints with
    | None -> None
    | Some (Json.Int value) when Z.sign value >= 0 -> Some value
    | Some _ -> reject "max_gate_count must be a nonnegative integer." in
  let preference = match List.assoc_opt "minimize" preferences with
    | None -> "gate_count"
    | Some (Json.String ("gate_count" | "none" as value)) -> value
    | Some _ -> reject "Synthetic minimize preference must be gate_count or none." in
  {allowed; maximum; preference}
let violations ~budget policy mechanism =
  let forbidden = index () and count = ref 0 in
  List.iter (fun node -> let kind = M.Node.kind node in
      if lookup budget policy.allowed kind = None then put budget forbidden kind ();
      if not (List.mem kind ["input"; "constant"; "output"]) then incr count)
    (B.bounded_list budget (M.nodes mechanism));
  let result = if forbidden.count = 0 then [] else begin
      let names = map budget fst (bindings budget forbidden) in
      let bytes = List.fold_left (fun total name -> total + String.length name + 1) 24 names in
      B.charge budget (2 * bytes); B.retain_monitor budget 1;
      ["operator_not_allowed:" ^ String.concat "," names]
    end in
  match policy.maximum with
  | Some maximum when Z.compare (Z.of_int !count) maximum > 0 ->
      (* Decimal spelling is shorter than bit width plus one. Charge before
         materializing it, including when a caller supplies a huge integer. *)
      B.charge budget (Z.numbits maximum + 65);
      let maximum_text = Z.to_string maximum and count_text = string_of_int !count in
      B.charge budget (2 * (32 + String.length maximum_text + String.length count_text));
      B.retain_monitor budget 2;
      result @ ["gate_count_exceeded:" ^ count_text ^ ">" ^ maximum_text]
  | _ -> result

(* Continuations are explicit data. Neither source graph depth, alias depth nor
   operand count consumes the OCaml call stack. Children run in Python order. *)
type task =
  | Evaluate of string
  | Alias of H.node * bool
  | Operands of H.node * string list * string list * int
  | Operand_done of H.node * string * string list * string list * int
  | Unary_done of H.node
  | Memory_set_done of H.node * (H.memory_input * string) list
  | Memory_reset_done of H.node * (H.memory_input * string) list * string * string

let produce budget checked config =
  let request = Checked.request checked in
  let behavior = Realization_request.behavior request and contract = Realization_request.contract request
  and domain = Realization_request.domain request and target = Checked.target checked in
  let profile = A.Config.profile_version config in
  let temporal = profile = A.temporal_profile in
  let catalog = A.catalog_for_profile profile in
  let source_nodes = index () and source_links = index () in
  List.iter (fun node -> put budget source_nodes (node_id node) node) (B.bounded_list budget (H.nodes behavior));
  List.iter (fun (key, values) -> put budget source_links (Identity.Node.to_string key)
      (map budget Identity.Node.to_string values)) (B.bounded_list budget (H.source_links behavior));
  let source id = get budget source_nodes id in
  B.charge budget (Realization_request.canonical_size request);
  let admission = Bioc_checker.Admission_check.for_target ~target ~boundary:Admission.Selection ~components:[] in
  if Admission.Assessment.decision admission <> Admission.Software_only then
    reject ("Human therapeutic use is not admitted: " ^ String.concat "; " (Admission.Assessment.diagnostics admission));
  if Build_request.artifact_scope (Realization_request.build_request request) <> Build_request.Synthetic_realization
  then reject "Synthetic generation requires the explicit synthetic_realization artifact scope.";
  ignore (policy_for_request ~budget checked ~profile);
  let roles = List.fold_left (fun count node -> B.charge budget 1;
      match H.operation node with H.Role _ -> count + 1 | _ -> count) 0 (H.nodes behavior) in
  if roles <> 1 || C.Operating_domain.role domain <> C.Behavior_contract.role contract then
    reject "The synthetic profile requires exactly one executing role.";
  if C.Operating_domain.max_contacts domain = None then
    reject "The synthetic profile requires an explicit finite max_contacts bound.";
  let capabilities = Build_request.Target.capabilities target in
  if not (List.mem "synthetic_signal_graph" capabilities) then
    reject "Synthetic generation requires a target with synthetic_signal_graph capability.";
  if not (List.mem "abstract" (Build_request.Target.compartments target)) then
    reject "Synthetic generation requires the abstract compartment.";
  let capability_set = index () in
  List.iter (fun key -> put budget capability_set key ()) (B.bounded_list budget capabilities);
  if List.exists (fun key -> lookup budget capability_set key = None) (C.Operating_domain.required_capabilities domain) then
    reject "The target does not provide all operating-domain capabilities.";
  List.iter (fun node ->
      let supported = match H.operation node with
        | H.Role _ | H.Scope _ | H.Signal _ | H.Qualitative _ | H.Literal _ | H.Parameter _
        | H.And | H.Or | H.Not | H.Compare _ | H.Signature _ | H.Rule _
        | H.Action_rest | H.Action_eliminate | H.Action_engulf -> true
        | H.Held_for | H.Became_true | H.Memory _ | H.Memory_is_set | H.Action_pulse -> temporal
        | _ -> false in
      B.charge budget 1;
      if not supported then reject ~node ("Operation " ^ Diagnostic_text.repr (H.kind_name (H.operation node)) ^
        " is unsupported by " ^ profile ^ "; temporal/state semantics are never approximated.");
      match H.operation node with
      | H.Rule {trigger = H.Event_trigger; _} ->
          if not temporal then reject ~node "The combinational synthetic profile requires condition-triggered rules.";
          let actions = match node_inputs budget node with _ :: _ :: rest -> rest | _ -> assert false in
          if List.exists (fun ref -> H.operation (source ref) <> H.Action_pulse) actions then
            reject ~node "Synthetic event rules require explicit-duration pulses."
      | _ -> ()) (H.nodes behavior);
  let installed = index () and required = index () in
  let pair left right =
    B.charge budget (6 * (String.length left + String.length right) + 8);
    Canonical.encode (Json.Array [str left; str right]) in
  List.iter (fun node -> match H.operation node with H.Rule _ ->
      let actions = match node_inputs budget node with _ :: _ :: rest -> rest | _ -> assert false in
      List.iter (fun action -> put budget installed (pair (node_id node) action) ()) actions
    | _ -> ()) (H.nodes behavior);
  let requirements = B.bounded_list budget (C.Behavior_contract.requirements contract) in
  List.iter (fun item -> put budget required (pair (R.rule_id item) (R.specification_id item)) ()) requirements;
  if installed.count <> required.count ||
      List.exists (fun (key, ()) -> lookup budget required key = None) (bindings budget installed)
  then reject "A response contract must cover every installed action exactly once.";
  if C.Behavior_contract.behavior_fingerprint contract <> H.fingerprint behavior then
    reject "The response contract identifies a different Behavior artifact.";
  List.iter (fun item -> if O.compartment (C.Input_domain.observable item) <> "abstract" then
      reject "Synthetic components support only the abstract compartment.") (C.Operating_domain.inputs domain);
  List.iter (fun item -> if O.compartment (R.observable item) <> "abstract" then
      reject "Synthetic components support only the abstract compartment.") requirements;
  let generated = index () and sources = index () and requirement_map = index () in
  let input_map = index () and domain_inputs = index () and cache = index () and responses = index () in
  List.iter (fun item -> put budget domain_inputs
      (pair (C.Input_domain.signal_id item) (C.Input_domain.field_name item)) item)
    (B.bounded_list budget (C.Operating_domain.inputs domain));
  (* Invert the source-to-response membership once. Each subsequent add unions
     exactly the memberships of its explicit source arguments. *)
  List.iter (fun item -> List.iter (fun ancestor ->
      let previous = Option.value (lookup budget responses ancestor) ~default:[] in
      B.retain_monitor budget 1; put budget responses ancestor (R.id item :: previous))
      (get budget source_links (R.rule_id item))) requirements;
  let union_sources select ids =
    let result = ref [] in
    List.iter (fun id -> result := union budget !result (select id)) ids; !result in
  let add ?(inputs = []) ?(attributes = Json.Object []) ?output ?response_ids ref kind dtype scope ids =
    let lineage = union_sources (get budget source_links) ids in
    let response_ids = match response_ids with
      | Some values -> strings budget values
      | None -> union_sources (fun id -> Option.value (lookup budget responses id) ~default:[]) ids in
    let behavior_ids = union_sources (fun id -> node_requirements budget (source id)) ids in
    let output_raw = match output with Some value -> O.to_json value | None ->
      Json.Object ["schema_version",str O.schema_version;"id",str ("synthetic." ^ ref);
        "dtype",Type_spec.to_json dtype;"role",str (C.Operating_domain.role domain);
        "scope",str (match scope with O.Cell -> "cell" | O.Contact -> "contact");"compartment",str "abstract"] in
    let raw = Json.Object ["id",str ref;"kind",str kind;"output",output_raw;
      "inputs",array budget str inputs;"attributes",attributes;"requirement_ids",array budget str response_ids] in
    B.reserve_report budget raw;
    let node = M.Node.of_json raw in
    put budget generated ref node; put budget sources ref lineage; put budget requirement_map ref behavior_ids; ref in
  let emitted id = get budget generated id in
  let aggregate ref output ids = if M.Node.scope (emitted ref) = O.Cell then ref else
      add ~inputs:[ref] output "any_contact" boolean O.Cell ids in
  let observe signal_id field_name source_id =
    let key = pair signal_id field_name in
    let item = match lookup budget domain_inputs key with Some value -> value | None ->
      reject ~node:(source source_id) ("Missing explicit operating-domain observation (" ^
        Diagnostic_text.repr signal_id ^ ", " ^ Diagnostic_text.repr field_name ^ ").") in
    let node = source signal_id in
    let dtype = if field_name = "value" then Option.get (H.data_type node) else boolean in
    if O.scope (C.Input_domain.observable item) <> scope node ||
      not (Type_spec.compatible (O.dtype (C.Input_domain.observable item)) dtype)
    then reject ~node "The operating-domain observation has incorrect type or contact scope.";
    match lookup budget input_map key with
    | None ->
        let ref = add ~output:(C.Input_domain.observable item) ("input:" ^ signal_id ^ ":" ^ field_name)
            "input" dtype (scope node) [source_id] in
        put budget input_map key (signal_id, C.Input_domain.field item, ref); ref
    | Some (_, _, ref) ->
        put budget sources ref (union budget (get budget sources ref) (get budget source_links source_id));
        put budget requirement_map ref (union budget (get budget requirement_map ref) (node_requirements budget (source source_id)));
        let previous = emitted ref in
        let response_ids = union budget (M.Node.requirement_ids previous)
            (Option.value (lookup budget responses source_id) ~default:[]) in
        let raw = Json.Object (Measurement_contract.replace "requirement_ids" (array budget str response_ids)
            (Json.object_fields (M.Node.to_json previous))) in
        B.reserve_report budget raw; put budget generated ref (M.Node.of_json raw); ref in
  let duration ref =
    let node = source ref in
    let binding = match H.operation node with H.Literal value -> H.binding_json value
      | H.Parameter {default; _} -> H.binding_json default
      | _ -> reject ~node "Synthetic durations must be bound design-time constants." in
    B.reserve_report budget binding;
    let value = Measurement_contract.Scalar.of_json ~expected:Measurement_contract.duration_type binding in
    if Runtime_number.compare (Measurement_contract.Scalar.canonical value) Runtime_number.zero <= 0 then
      reject ~node "Synthetic durations must be positive.";
    Measurement_contract.Scalar.to_json value in
  let finish node result = put budget cache (node_id node) result in
  let cached id = get budget cache id in
  let first_input node = match node_inputs budget node with value :: _ -> value | [] -> assert false in
  let finish_memory node controls setting resetting =
    let duration = match List.assoc_opt H.Duration_input controls with None -> Json.Null | Some ref -> duration ref in
    finish node (add ~inputs:[setting; resetting] ~attributes:(Json.Object ["duration",duration])
      ("expression:" ^ node_id node) "memory" boolean O.Cell [node_id node]) in
  let expression root =
    let tasks = ref [] in
    let push task = B.retain_monitor budget 1; B.charge budget 1; tasks := task :: !tasks in
    push (Evaluate root);
    while !tasks <> [] do
      let task = List.hd !tasks in tasks := List.tl !tasks; B.release_monitor budget 1; B.charge budget 1;
      match task with
      | Evaluate ref when lookup budget cache ref <> None -> ()
      | Evaluate ref ->
          let node = source ref in
          (match H.operation node with
           | H.Qualitative band -> finish node (observe (first_input node)
               (match band with H.Present -> "present" | H.High -> "high" | H.Low -> "low") ref)
           | H.Signal _ -> finish node (observe ref "value" ref)
           | H.Signature _ -> push (Alias (node, false)); push (Evaluate (first_input node))
           | H.Memory_is_set -> push (Alias (node, true)); push (Evaluate (first_input node))
           | H.Literal binding | H.Parameter {default = binding; _} ->
               finish node (add ~attributes:(Json.Object ["value",H.binding_json binding])
                 ("expression:" ^ ref) "constant" (Option.get (H.data_type node)) O.Cell [ref])
           | H.And | H.Or | H.Not | H.Compare _ -> push (Operands (node, node_inputs budget node, [], 0))
           | H.Held_for | H.Became_true -> push (Unary_done node); push (Evaluate (first_input node))
           | H.Memory {input_names; _} ->
               B.charge budget (List.length input_names); B.retain_monitor budget (List.length input_names);
               let controls = List.combine input_names (node_inputs budget node) in
               push (Memory_set_done (node, controls)); push (Evaluate (List.assoc H.Set_when controls))
           | _ -> reject ~node ("Unsupported synthetic expression " ^ Diagnostic_text.repr (H.kind_name (H.operation node)) ^ "."))
      | Alias (node, memory) ->
          let result = cached (first_input node) in
          put budget sources result (union budget (get budget sources result) (get budget source_links (node_id node)));
          if memory then put budget requirement_map result
              (union budget (get budget requirement_map result) (node_requirements budget node));
          finish node result
      | Operands (node, next :: rest, values, ordinal) ->
          push (Operand_done (node, next, rest, values, ordinal)); push (Evaluate next)
      | Operand_done (node, child, rest, values, ordinal) ->
          let result = cached child in
          let result = if H.operation node = H.And && A.Config.conjunction_strategy config = "de_morgan" then
              add ~inputs:[result] ("expression:" ^ node_id node ^ ":not:" ^ string_of_int ordinal)
                "not" boolean (scope node) [node_id node] else result in
          B.retain_monitor budget 1;
          push (Operands (node, rest, result :: values, ordinal + 1))
      | Operands (node, [], values, _) ->
          let inputs = List.rev (reserve_list budget values) in
          let ref = "expression:" ^ node_id node in
          let result = if H.operation node = H.And && A.Config.conjunction_strategy config = "de_morgan" then
              let joined = add ~inputs (ref ^ ":or") "or" boolean (scope node) [node_id node] in
              add ~inputs:[joined] ref "not" boolean (scope node) [node_id node]
            else
              let attributes = match H.operation node with H.Compare _ ->
                  Json.Object ["operator",field "operator" (H.attributes node)] | _ -> Json.Object [] in
              add ~inputs ~attributes ref (H.kind_name (H.operation node)) boolean (scope node) [node_id node] in
          finish node result
      | Unary_done node ->
          let inputs = node_inputs budget node in
          let attributes, kind = match H.operation node, inputs with
            | H.Held_for, _ :: time :: _ -> Json.Object ["duration", duration time], "held_for"
            | H.Became_true, _ -> Json.Object [], "onset"
            | _ -> assert false in
          finish node (add ~inputs:[cached (List.hd inputs)] ~attributes ("expression:" ^ node_id node)
              kind boolean (scope node) [node_id node])
      | Memory_set_done (node, controls) ->
          let setting = cached (List.assoc H.Set_when controls) in
          let event = add ~inputs:[setting] ("memory_onset:" ^ node_id node)
              "onset" boolean (M.Node.scope (emitted setting)) [node_id node] in
          let setting = aggregate event ("memory_set:" ^ node_id node) [node_id node] in
          (match List.assoc_opt H.Reset_when controls with
           | Some reset -> push (Memory_reset_done (node, controls, setting, reset)); push (Evaluate reset)
           | None -> let resetting = add ~attributes:(Json.Object ["value",Json.Bool false])
                 ("memory_reset:" ^ node_id node) "constant" boolean O.Cell [node_id node] in
               finish_memory node controls setting resetting)
      | Memory_reset_done (node, controls, setting, resetting) ->
          let resetting = aggregate (cached resetting) ("memory_reset:" ^ node_id node) [node_id node] in
          finish_memory node controls setting resetting
    done;
    cached root in
  List.iter (fun node -> match H.operation node with H.Memory _ -> ignore (expression (node_id node)) | _ -> ())
    (H.nodes behavior);
  let outputs = ref [] and output_bindings = ref [] in
  List.iter (fun requirement ->
      let rule = source (R.rule_id requirement) and action = source (R.specification_id requirement) in
      let output = R.observable requirement and output_scope = scope action in
      if O.role output <> C.Operating_domain.role domain || O.scope output <> output_scope then
        reject ~node:action "The response observable does not preserve its action's role/contact scope.";
      let guard_ref = match node_inputs budget rule with _ :: guard :: _ -> guard | _ -> assert false in
      let guard = expression guard_ref in
      let id = R.id requirement in
      let add_response ?inputs ?attributes ?output ref kind dtype scope ids =
        add ?inputs ?attributes ?output ~response_ids:[id] ref kind dtype scope ids in
      let guard = if M.Node.scope (emitted guard) = O.Contact && output_scope = O.Cell then
          add_response ~inputs:[guard] ("aggregate:" ^ id) "any_contact" boolean O.Cell [node_id rule] else guard in
      let guard = if H.operation action = H.Action_pulse then begin
          let guard = match H.operation rule with H.Rule {trigger = H.Condition_trigger; _} ->
              add_response ~inputs:[guard] ("pulse_onset:" ^ id) "onset" boolean output_scope [node_id rule; node_id action]
            | _ -> guard in
          let time = match node_inputs budget action with _ :: time :: _ -> time | _ -> assert false in
          add_response ~inputs:[guard] ~attributes:(Json.Object ["duration",duration time])
            ("pulse:" ^ id) "pulse" boolean output_scope [node_id rule; node_id action]
        end else guard in
      let constant state band = add_response
          ~attributes:(Json.Object ["value",Measurement_contract.Scalar.to_json (Measurement_contract.Interval.lower_scalar band)])
          (state ^ ":" ^ id) "constant" (O.dtype output) output_scope [node_id rule; node_id action] in
      let active = constant "active" (R.active requirement) in
      let inactive = constant "inactive" (R.inactive requirement) in
      let selected = add_response ~inputs:[guard; active; inactive] ("select:" ^ id) "select"
          (O.dtype output) output_scope [node_id rule; node_id action] in
      let result = add_response ~inputs:[selected] ~output ("output:" ^ id) "output"
          (O.dtype output) output_scope [node_id rule; node_id action] in
      B.retain_monitor budget 2; outputs := result :: !outputs;
      output_bindings := Json.Object ["requirement_id",str id;"mechanism_output_id",str result] :: !output_bindings) requirements;
  if input_map.count <> domain_inputs.count then
    reject "Operating-domain inputs must cover exactly the supported runtime observations; extra observations are not silently ignored.";
  let nodes = map budget snd (bindings budget generated) in
  let mechanism_raw = Json.Object ["schema_version",str M.schema_version;"name",str (H.name behavior ^ ".synthetic");
    "nodes",array budget M.Node.to_json nodes;"outputs",array budget str (List.rev (reserve_list budget !outputs));
    "required_capabilities",Json.Array [str "synthetic_signal_graph"]] in
  B.reserve_report budget mechanism_raw;
  (* Typed graph validation includes adjacency, ready layers and event walks.
     Reserve the source/edge volume times the bounded graph height first. *)
  charge_product budget (List.fold_left (fun total node -> total + 1 + List.length (M.Node.inputs node)) 0 nodes)
    (1 + height generated.count);
  let mechanism = M.of_json mechanism_raw in
  let input_bindings = map budget (fun (_, (signal_id, field, ref)) ->
      Json.Object ["signal_id",str signal_id;"field",str (Observation_map.field_name field);"mechanism_input_id",str ref])
      (bindings budget input_map) in
  let observation_raw = Json.Object ["schema_version",str Observation_map.schema_version;
    "inputs",Json.Array input_bindings;"outputs",Json.Array (List.rev (reserve_list budget !output_bindings))] in
  B.reserve_report budget observation_raw;
  let observation_map = Observation_map.of_json observation_raw in
  let locks = map budget (fun node ->
      B.charge budget (A.Catalog.canonical_size catalog);
      let component = Option.get (A.Catalog.for_operation catalog (M.Node.kind node)) in
      let raw = Json.Object ["schema_version",str Component_registry.Component_lock.schema_version;
        "node_id",str (M.Node.id node);"component_id",str (A.Component.id component);
        "version",str (A.Component.version component);"content_fingerprint",str (A.Component.fingerprint component)] in
      B.reserve_report budget raw; raw) nodes in
  let encode_map table = Json.Object (map budget (fun (key, values) -> key, array budget str values) (bindings budget table)) in
  let candidate_raw = Json.Object ["schema_version",str A.Candidate.schema_version;
    "intended_use",str "software_test";"human_therapeutic_admission",str "not_admitted";
    "request_fingerprint",str (Checked.fingerprint checked);"mechanism",M.to_json mechanism;
    "observation_map",Observation_map.to_json observation_map;"source_map",encode_map sources;
    "behavior_requirement_ids",encode_map requirement_map;"component_locks",Json.Array locks;
    "generator_config",A.Config.to_json config] in
  B.reserve_report budget candidate_raw;
  A.Candidate.of_json candidate_raw

let run ~hard ?config ?(limits = default_limits) ?parent request =
  let budget = B.create ?parent ~limits () in
  let start = W.remaining (B.work budget) in
  B.reserve_request budget (Json.Object ["request",Json.Null;"config",Json.Null]);
  B.reserve_request budget (Realization_request.to_json request);
  let config = match config with Some value -> value | None -> A.Config.make () in
  B.reserve_request budget (A.Config.to_json config);
  let checked = Checked.check ~parent:(B.work budget) request in
  let candidate = produce budget checked config in
  if hard then begin
    let policy = policy_for_request ~budget checked ~profile:(A.Config.profile_version config) in
    match violations ~budget policy (A.Candidate.mechanism candidate) with
    | [] -> ()
    | values -> reject ("Synthetic proposal violates hard constraints: " ^ String.concat "; " values)
  end;
  let used = B.usage budget in
  candidate, {work_charged = start - W.remaining (B.work budget);request_bytes = used.request_bytes;
    report_bytes = used.report_bytes;retained_peak = used.monitor_peak}
let propose_with_usage ?config ?limits ?parent request = run ~hard:false ?config ?limits ?parent request
let propose ?config ?limits ?parent request = fst (propose_with_usage ?config ?limits ?parent request)
let generate_with_usage ?config ?limits ?parent request = run ~hard:true ?config ?limits ?parent request
let generate ?config ?limits ?parent request = fst (generate_with_usage ?config ?limits ?parent request)
