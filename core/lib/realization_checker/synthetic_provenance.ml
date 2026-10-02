open Bioc_wire
open Bioc_domain
module B = Realization_budget
module Q = Checked_request
module H = Behavior
module R = Realization_contract
module O = R.Observable
module M = Mechanism
module S = Set.Make (String)
module Index = Map.Make (String)
module Key = struct type t = string * string let compare = Stdlib.compare end
module Keys = Set.Make (Key)
module Inputs = Map.Make (Key)
module A = Synthetic_authority
type error = { message : string; node_id : string option; source : H.source_location option }
exception Unsupported of error
let format_error (error:error) =
  error.message ^ (match error.node_id with None -> "" | Some id -> " [" ^ id ^ "]") ^
  (match error.source with None -> "" | Some source -> " at " ^ source.file ^ ":" ^ Z.to_string source.line)
let unsupported ?node message =
  let node_id,source = match node with None -> None,None
    | Some node -> Some (Identity.Node.to_string (H.node_id node)),H.source node in
  raise (Unsupported {message;node_id;source})
let str value = Json.String value
let node_id node = Identity.Node.to_string (H.node_id node)
let inputs node = List.map Identity.Node.to_string (H.inputs node)
let rec levels count = if count <= 1 then 1 else 1 + levels (count / 2)
let text budget value = B.charge budget (String.length value + 1)
let access budget key = B.charge budget ((String.length key + 1) * levels Limits.max_json_nodes)
let add_set budget value set =
  access budget value; B.retain_monitor budget 1; S.add value set
let member budget value set = access budget value; S.mem value set
let set_of_list budget values = List.fold_left (fun result value -> add_set budget value result) S.empty values
let union_list budget set values = List.fold_left (fun result value -> add_set budget value result) set values
let elements budget set = S.fold (fun value result -> B.charge budget 2; value :: result) set [] |> List.rev
let find budget key index = access budget key; Index.find key index
let find_opt budget key index = access budget key; Index.find_opt key index
let put budget key value index =
  access budget key; B.retain_monitor budget 1; Index.add key value index
let key_access budget (signal,field) = access budget signal; access budget field
let boolean = Type_spec.of_json (Json.parse {|{"kind":"condition","name":"Condition","dimensions":{},"arguments":[]}|})
type policy = { allowed : S.t; maximum : Z.t option; preference : string }
let allowed_operators value = S.elements value.allowed
let max_gate_count value = value.maximum
let minimize value = value.preference
let parse_policy ~budget checked ~profile =
  let envelope = Q.request checked in
  B.charge budget (Realization_request.canonical_size envelope);
  let request = Realization_request.build_request envelope in
  let constraints = Build_request.implementation_constraints request and preferences = Build_request.preferences request in
  List.iter (fun (key,value) -> text budget key; B.charge budget (String.length (Canonical.encode value))) (constraints @ preferences);
  if List.exists (fun (key,_) -> not (List.mem key ["allowed_operators";"max_gate_count"])) constraints then
    unsupported "Unsupported synthetic implementation-constraint fields.";
  if List.exists (fun (key,_) -> key <> "minimize") preferences then unsupported "Unsupported synthetic preference fields.";
  let catalog = A.catalog_for_profile profile in
  let available = A.Catalog.components catalog |> List.map A.Component.operation |> set_of_list budget in
  let allowed = match List.assoc_opt "allowed_operators" constraints with
    | None -> available
    | Some (Json.Array values) ->
        let result = ref S.empty in
        List.iter (fun value ->
          B.charge budget 1;
          match value with
          | Json.String value when not (member budget value !result) && member budget value available ->
              result := add_set budget value !result
          | _ -> unsupported "allowed_operators must be unique names in the selected synthetic catalog.") values;
        !result
    | Some _ -> unsupported "allowed_operators must be unique names in the selected synthetic catalog." in
  let maximum = match List.assoc_opt "max_gate_count" constraints with
    | None -> None
    | Some (Json.Int value) when Z.sign value >= 0 -> Some value
    | Some _ -> unsupported "max_gate_count must be a nonnegative integer." in
  let preference = match List.assoc_opt "minimize" preferences with
    | None -> "gate_count"
    | Some (Json.String ("gate_count" | "none" as value)) -> value
    | Some _ -> unsupported "Synthetic minimize preference must be gate_count or none." in
  {allowed;maximum;preference}
let count_gates ~budget mechanism =
  List.fold_left (fun count node -> B.charge budget 1;
    count + (if List.mem (M.Node.kind node) ["input";"constant";"output"] then 0 else 1)) 0 (M.nodes mechanism)
let violations ~budget policy mechanism =
  let forbidden = List.fold_left (fun result node ->
    let kind = M.Node.kind node in
    if member budget kind policy.allowed then result else add_set budget kind result) S.empty (M.nodes mechanism) in
  let result = if S.is_empty forbidden then [] else
    ["operator_not_allowed:" ^ String.concat "," (elements budget forbidden)] in
  let cost = count_gates ~budget mechanism in
  match policy.maximum with
  | Some maximum ->
      B.charge budget (Z.numbits maximum + 1);
      if Z.compare (Z.of_int cost) maximum > 0 then
        result @ ["gate_count_exceeded:" ^ string_of_int cost ^ ">" ^ Z.to_string maximum]
      else result
  | None -> result

type t = { sources : (string * string list) list; requirements : (string * string list) list;
  nodes : int; gates : int }
let source_map value = value.sources
let behavior_requirement_ids value = value.requirements
let node_count value = value.nodes
let gate_count value = value.gates
type task = Eval of string | Alias of H.node | Simple of H.node
  | Morgan_next of H.node * int * string list * string list
  | Morgan_after of H.node * int * string * string list * string list
  | Memory_set of H.node | Memory_reset of H.node * string
let comparison = function H.Lt -> "lt" | H.Le -> "le" | H.Gt -> "gt" | H.Ge -> "ge" | H.Eq -> "eq" | H.Ne -> "ne"
let band = function H.Present -> "present" | H.High -> "high" | H.Low -> "low"
let source_name = function H.Owner -> "owner" | H.Set_when -> "set_when" | H.Reset_when -> "reset_when" | H.Duration_input -> "duration"
let derive ~budget checked config =
  let request = Q.request checked in
  (* Caller reserves its whole external envelope once. These typed values have
     already passed bounded codecs; this charges all repeated authority scans,
     including fresh admission's canonical reconstruction, before doing them. *)
  B.charge budget (10 * Realization_request.canonical_size request + A.Config.canonical_size config);
  let behavior = Realization_request.behavior request and contract = Realization_request.contract request
  and domain = Realization_request.domain request and target = Q.target checked in
  let responses = R.Behavior_contract.requirements contract in
  let profile = A.Config.profile_version config in
  let temporal = profile = A.temporal_profile in
  let admission = Bioc_checker.Admission_check.for_target ~target ~boundary:Admission.Selection ~components:[] in
  if Admission.Assessment.decision admission <> Admission.Software_only then
    unsupported ("Human therapeutic use is not admitted: " ^ String.concat "; " (Admission.Assessment.diagnostics admission));
  if Build_request.artifact_scope (Realization_request.build_request request) <> Build_request.Synthetic_realization then
    unsupported "Synthetic generation requires the explicit synthetic_realization artifact scope.";
  let policy = parse_policy ~budget checked ~profile in
  let role_count = List.fold_left (fun count node -> B.charge budget 1;
    match H.operation node with H.Role _ -> count + 1 | _ -> count) 0 (H.nodes behavior) in
  if role_count <> 1 || R.Operating_domain.role domain <> R.Behavior_contract.role contract then
    unsupported "The synthetic profile requires exactly one executing role.";
  if R.Operating_domain.max_contacts domain = None then
    unsupported "The synthetic profile requires an explicit finite max_contacts bound.";
  let capabilities = set_of_list budget (Build_request.Target.capabilities target) in
  if not (member budget "synthetic_signal_graph" capabilities) then
    unsupported "Synthetic generation requires a target with synthetic_signal_graph capability.";
  if not (List.mem "abstract" (Build_request.Target.compartments target)) then
    unsupported "Synthetic generation requires the abstract compartment.";
  if List.exists (fun capability -> not (member budget capability capabilities)) (R.Operating_domain.required_capabilities domain) then
    unsupported "The target does not provide all operating-domain capabilities.";
  let nodes = List.fold_left (fun result node -> B.retain_monitor budget 1;
    put budget (node_id node) node result) Index.empty (H.nodes behavior) in
  let source_links = List.fold_left (fun result (id,links) ->
    B.retain_monitor budget (List.length links + 1);
    put budget (Identity.Node.to_string id) (List.map Identity.Node.to_string links) result) Index.empty (H.source_links behavior) in
  let lookup id = find budget id nodes in
  let supported node = match H.operation node with
    | H.Role _ | H.Scope _ | H.Signal _ | H.Qualitative _ | H.Literal _ | H.Parameter _
    | H.And | H.Or | H.Not | H.Compare _ | H.Signature _ | H.Rule _
    | H.Action_rest | H.Action_eliminate | H.Action_engulf -> true
    | H.Held_for | H.Became_true | H.Memory _ | H.Memory_is_set | H.Action_pulse -> temporal
    | _ -> false in
  List.iter (fun node ->
    B.charge budget 1;
    if not (supported node) then unsupported ~node
      ("Operation '" ^ H.kind_name (H.operation node) ^ "' is unsupported by " ^ profile ^ "; temporal/state semantics are never approximated.");
    (match H.operation node with
    | H.Rule {trigger=H.Event_trigger;_} ->
        if not temporal then unsupported ~node "The combinational synthetic profile requires condition-triggered rules.";
        let actions = List.tl (List.tl (inputs node)) in
        if List.exists (fun ref -> H.operation (lookup ref) <> H.Action_pulse) actions then
          unsupported ~node "Synthetic event rules require explicit-duration pulses."
    | _ -> ())) (H.nodes behavior);
  let installed = List.fold_left (fun result node -> match H.operation node with
    | H.Rule _ -> List.fold_left (fun result action ->
        key_access budget (node_id node,action); Keys.add (node_id node,action) result)
        result (List.tl (List.tl (inputs node)))
    | _ -> result) Keys.empty (H.nodes behavior) in
  let required = List.fold_left (fun result response ->
    let key = R.Response.rule_id response,R.Response.specification_id response in
    key_access budget key; Keys.add key result) Keys.empty responses in
  B.charge budget (Keys.cardinal installed + Keys.cardinal required);
  if not (Keys.equal installed required) then unsupported "A response contract must cover every installed action exactly once.";
  if R.Behavior_contract.behavior_fingerprint contract <> H.fingerprint behavior then
    unsupported "The response contract identifies a different Behavior artifact.";
  List.iter (fun observable -> if O.compartment observable <> "abstract" then
    unsupported "Synthetic components support only the abstract compartment.")
    (List.map R.Input_domain.observable (R.Operating_domain.inputs domain) @ List.map R.Response.observable responses);
  let domain_inputs = List.fold_left (fun result item ->
    let key = R.Input_domain.signal_id item,R.Input_domain.field_name item in
    key_access budget key;
    Inputs.add key item result) Inputs.empty (R.Operating_domain.inputs domain) in
  let response_sources = List.map (fun response -> R.Response.id response,
    set_of_list budget (find budget (R.Response.rule_id response) source_links)) responses in
  let generated = ref Index.empty and sources = ref Index.empty and requirements = ref Index.empty
  and expression_cache = ref Index.empty and input_map = ref Inputs.empty and observed = ref Keys.empty in
  let source_ancestors direct = List.fold_left (fun result source ->
    union_list budget result (find budget source source_links)) S.empty direct |> elements budget in
  let direct_requirements direct = List.fold_left (fun result source ->
    let ids = H.requirement_ids (lookup source) |> List.map Identity.Requirement.to_string in
    union_list budget result ids) S.empty direct |> elements budget in
  let response_ids direct = List.fold_left (fun result (id,ancestors) ->
    if List.exists (fun source -> member budget source ancestors) direct then add_set budget id result else result)
    S.empty response_sources |> elements budget in
  let store_node raw =
    B.reserve_report budget raw;
    B.retain_monitor budget 1;
    let node = M.Node.of_json raw in
    generated := put budget (M.Node.id node) node !generated in
  let add ?(inputs=[]) ?(attributes=Json.Object []) ?output ?response_ids:explicit ref kind dtype scope direct =
    let lineage = source_ancestors direct in
    let carried = direct_requirements direct in
    let responses = match explicit with None -> response_ids direct | Some ids -> elements budget (set_of_list budget ids) in
    B.retain_monitor budget (List.length lineage + List.length carried + List.length responses + List.length inputs + 2);
    let output = match output with Some value -> value | None ->
      text budget ref;
      O.make ~id:("synthetic." ^ ref) ~dtype ~role:(R.Operating_domain.role domain) ~scope () in
    let raw = Json.Object ["id",str ref;"kind",str kind;"output",O.to_json output;
      "inputs",Json.Array (List.map str inputs);"attributes",attributes;"requirement_ids",Json.Array (List.map str responses)] in
    store_node raw;
    B.reserve_report budget (Json.Object ["source_map",Json.Object [ref,Json.Array (List.map str lineage)];
      "behavior_requirement_ids",Json.Object [ref,Json.Array (List.map str carried)]]);
    sources := put budget ref lineage !sources; requirements := put budget ref carried !requirements; ref in
  let generated_node ref = find budget ref !generated in
  let update_map index ref additions =
    let values = union_list budget (set_of_list budget (find budget ref !index)) additions |> elements budget in
    B.retain_monitor budget (List.length values);
    B.reserve_report budget (Json.Object [ref,Json.Array (List.map str values)]);
    index := put budget ref values !index in
  let observe signal_id field source_id =
    let key = signal_id,field in
    key_access budget key;
    let item = match Inputs.find_opt key domain_inputs with Some item -> item | None ->
      text budget signal_id; text budget field;
      unsupported ~node:(lookup source_id)
        ("Missing explicit operating-domain observation (" ^ Diagnostic_text.repr signal_id ^ ", " ^ Diagnostic_text.repr field ^ ").") in
    let node = lookup signal_id in
    let dtype = if field = "value" then Option.get (H.data_type node) else boolean in
    let scope = if H.contact_bound node then O.Contact else O.Cell in
    if O.scope (R.Input_domain.observable item) <> scope || not (Type_spec.compatible (O.dtype (R.Input_domain.observable item)) dtype) then
      unsupported ~node "The operating-domain observation has incorrect type or contact scope.";
    key_access budget key; observed := Keys.add key !observed;
    key_access budget key;
    match Inputs.find_opt key !input_map with
    | None ->
        let ref = add ~output:(R.Input_domain.observable item) ("input:" ^ signal_id ^ ":" ^ field) "input" dtype scope [source_id] in
        input_map := Inputs.add key ref !input_map; ref
    | Some ref ->
        update_map sources ref (find budget source_id source_links);
        update_map requirements ref (H.requirement_ids (lookup source_id) |> List.map Identity.Requirement.to_string);
        let node = generated_node ref in
        let ids = union_list budget (set_of_list budget (M.Node.requirement_ids node)) (response_ids [source_id]) |> elements budget in
        let raw = M.Node.to_json node |> Json.object_fields in
        store_node (Json.Object (("requirement_ids",Json.Array (List.map str ids)) :: List.remove_assoc "requirement_ids" raw)); ref in
  let duration ref =
    let node = lookup ref in
    let value = match H.operation node with
      | H.Literal value -> H.binding_json value
      | H.Parameter {default;_} -> H.binding_json default
      | _ -> unsupported ~node "Synthetic durations must be bound design-time constants." in
    let normalized = Type_spec.normalize_binding ~expected:Measurement_contract.duration_type value in
    let duration = Measurement_contract.Scalar.of_json ~expected:Measurement_contract.duration_type normalized in
    if Runtime_number.compare (Measurement_contract.Scalar.canonical duration) Runtime_number.zero <= 0 then
      unsupported ~node "Synthetic durations must be positive.";
    Measurement_contract.Scalar.to_json duration in
  let aggregate ref output_id direct = if M.Node.scope (generated_node ref) = O.Cell then ref
    else add ~inputs:[ref] output_id "any_contact" boolean O.Cell direct in
  let cached ref = find budget ref !expression_cache in
  let cache id result = B.retain_monitor budget 1; expression_cache := put budget id result !expression_cache in
  let controls node = match H.operation node with
    | H.Memory {input_names;_} -> List.combine (List.map source_name input_names) (inputs node)
    | _ -> assert false in
  let finish_memory node setting resetting =
    let id = node_id node in
    let duration = match List.assoc_opt "duration" (controls node) with None -> Json.Null | Some ref -> duration ref in
    let result = add ~inputs:[setting;resetting] ~attributes:(Json.Object ["duration",duration])
      ("expression:" ^ id) "memory" boolean O.Cell [id] in cache id result in
  let expression root_id =
    let pending = ref [] in
    let push task = B.charge budget 1; B.retain_monitor budget 1; pending := task :: !pending in
    push (Eval root_id);
    while !pending <> [] do
      B.charge budget 1; B.release_monitor budget 1;
      let task = List.hd !pending in pending := List.tl !pending;
      match task with
      | Eval id ->
          (match find_opt budget id !expression_cache with Some _ -> () | None ->
            let node = lookup id in
            (match H.operation node with
            | H.Qualitative value -> cache id (observe (List.hd (inputs node)) (band value) id)
            | H.Signal _ -> cache id (observe id "value" id)
            | H.Signature _ | H.Memory_is_set -> push (Alias node); push (Eval (List.hd (inputs node)))
            | H.Literal value | H.Parameter {default=value;_} ->
                let result = add ~attributes:(Json.Object ["value",H.binding_json value])
                  ("expression:" ^ id) "constant" (Option.get (H.data_type node)) O.Cell [id] in cache id result
            | H.And when A.Config.conjunction_strategy config = "de_morgan" ->
                push (Morgan_next (node,0,inputs node,[]))
            | H.And | H.Or | H.Not | H.Compare _ ->
                push (Simple node); List.iter (fun ref -> push (Eval ref)) (List.rev (inputs node))
            | H.Held_for | H.Became_true -> push (Simple node); push (Eval (List.hd (inputs node)))
            | H.Memory _ -> push (Memory_set node); push (Eval (List.assoc "set_when" (controls node)))
            | _ -> unsupported ~node ("Unsupported synthetic expression '" ^ H.kind_name (H.operation node) ^ "'.")))
      | Alias node ->
          let id = node_id node in
          let result = cached (List.hd (inputs node)) in
          update_map sources result (find budget id source_links);
          (match H.operation node with H.Memory_is_set ->
            update_map requirements result (H.requirement_ids node |> List.map Identity.Requirement.to_string) | _ -> ());
          cache id result
      | Simple node ->
          let id = node_id node and scope = if H.contact_bound node then O.Contact else O.Cell in
          let kind,refs,attributes = match H.operation node with
            | H.And -> "and",List.map cached (inputs node),Json.Object []
            | H.Or -> "or",List.map cached (inputs node),Json.Object []
            | H.Not -> "not",List.map cached (inputs node),Json.Object []
            | H.Compare operator -> "compare",List.map cached (inputs node),Json.Object ["operator",str (comparison operator)]
            | H.Held_for -> "held_for",[cached (List.hd (inputs node))],Json.Object ["duration",duration (List.nth (inputs node) 1)]
            | H.Became_true -> "onset",[cached (List.hd (inputs node))],Json.Object []
            | _ -> assert false in
          cache id (add ~inputs:refs ~attributes ("expression:" ^ id) kind boolean scope [id])
      | Morgan_next (node,index,remaining,negated) ->
          (match remaining with
          | operand :: rest -> push (Morgan_after (node,index,operand,rest,negated)); push (Eval operand)
          | [] ->
              let id = node_id node and scope = if H.contact_bound node then O.Contact else O.Cell in
              let union = add ~inputs:(List.rev negated) ("expression:" ^ id ^ ":or") "or" boolean scope [id] in
              cache id (add ~inputs:[union] ("expression:" ^ id) "not" boolean scope [id]))
      | Morgan_after (node,index,operand,remaining,negated) ->
          let id = node_id node and scope = if H.contact_bound node then O.Contact else O.Cell in
          let next = add ~inputs:[cached operand] ("expression:" ^ id ^ ":not:" ^ string_of_int index) "not" boolean scope [id] in
          push (Morgan_next (node,index+1,remaining,next::negated))
      | Memory_set node ->
          let id = node_id node in
          let setting = cached (List.assoc "set_when" (controls node)) in
          let event = add ~inputs:[setting] ("memory_onset:" ^ id) "onset" boolean (M.Node.scope (generated_node setting)) [id] in
          let setting = aggregate event ("memory_set:" ^ id) [id] in
          (match List.assoc_opt "reset_when" (controls node) with
          | Some ref -> push (Memory_reset (node,setting)); push (Eval ref)
          | None -> let resetting = add ~attributes:(Json.Object ["value",Json.Bool false])
              ("memory_reset:" ^ id) "constant" boolean O.Cell [id] in finish_memory node setting resetting)
      | Memory_reset (node,setting) ->
          let id = node_id node in
          let resetting = aggregate (cached (List.assoc "reset_when" (controls node))) ("memory_reset:" ^ id) [id] in
          finish_memory node setting resetting
    done;
    cached root_id in
  List.iter (fun node -> match H.operation node with H.Memory _ -> ignore (expression (node_id node)) | _ -> ()) (H.nodes behavior);
  let outputs = ref [] and bindings = ref [] in
  List.iter (fun response ->
    let rule = lookup (R.Response.rule_id response) and action = lookup (R.Response.specification_id response) in
    let scope = if H.contact_bound action then O.Contact else O.Cell in
    if O.role (R.Response.observable response) <> R.Operating_domain.role domain || O.scope (R.Response.observable response) <> scope then
      unsupported ~node:action "The response observable does not preserve its action's role/contact scope.";
    let response_id = R.Response.id response in
    let guard = expression (List.nth (inputs rule) 1) in
    let guard = if M.Node.scope (generated_node guard) = O.Contact && scope = O.Cell then
      add ~inputs:[guard] ~response_ids:[response_id] ("aggregate:" ^ response_id) "any_contact" boolean O.Cell [node_id rule]
      else guard in
    let guard = if H.operation action = H.Action_pulse then begin
      let guard = match H.operation rule with
        | H.Rule {trigger=H.Condition_trigger;_} -> add ~inputs:[guard] ~response_ids:[response_id]
            ("pulse_onset:" ^ response_id) "onset" boolean scope [node_id rule;node_id action]
        | _ -> guard in
      add ~inputs:[guard] ~attributes:(Json.Object ["duration",duration (List.nth (inputs action) 1)])
        ~response_ids:[response_id] ("pulse:" ^ response_id) "pulse" boolean scope [node_id rule;node_id action]
      end else guard in
    let dtype = O.dtype (R.Response.observable response) in
    let values = List.map (fun (state,band) ->
      add ~attributes:(Json.Object ["value",Measurement_contract.Scalar.to_json (Measurement_contract.Interval.lower_scalar band)])
        ~response_ids:[response_id] (state ^ ":" ^ response_id) "constant" dtype scope [node_id rule;node_id action])
      ["active",R.Response.active response;"inactive",R.Response.inactive response] in
    let selected = add ~inputs:(guard::values) ~response_ids:[response_id] ("select:" ^ response_id)
      "select" dtype scope [node_id rule;node_id action] in
    let output = add ~inputs:[selected] ~output:(R.Response.observable response) ~response_ids:[response_id]
      ("output:" ^ response_id) "output" dtype scope [node_id rule;node_id action] in
    outputs := output :: !outputs;
    bindings := Observation_map.Output_binding.make ~requirement_id:response_id ~mechanism_output_id:output :: !bindings) responses;
  B.charge budget (Keys.cardinal !observed + Inputs.cardinal domain_inputs);
  if Keys.cardinal !observed <> Inputs.cardinal domain_inputs then
    unsupported "Operating-domain inputs must cover exactly the supported runtime observations; extra observations are not silently ignored.";
  let declared = Index.bindings !generated |> List.map snd in
  B.charge budget (Index.cardinal !generated);
  let mechanism_raw = Json.Object ["schema_version",str M.schema_version;"name",str (H.name behavior ^ ".synthetic");
    "nodes",Json.Array (List.map M.Node.to_json declared);"outputs",Json.Array (List.map str (List.rev !outputs));
    "required_capabilities",Json.Array [str "synthetic_signal_graph"]] in
  B.reserve_report budget mechanism_raw;
  let mechanism = M.of_json mechanism_raw in
  let inputs = Inputs.bindings !input_map |> List.map (fun ((signal_id,field),mechanism_input_id) ->
    let field = match field with "value" -> Observation_map.Value | "present" -> Observation_map.Present
      | "high" -> Observation_map.High | "low" -> Observation_map.Low | _ -> assert false in
    Observation_map.Input_binding.make ~signal_id ~field ~mechanism_input_id) in
  let mapping = Observation_map.make ~inputs ~outputs:(List.rev !bindings) in
  B.reserve_report budget (Observation_map.to_json mapping);
  let source_map = Index.bindings !sources and behavior_requirement_ids = Index.bindings !requirements in
  let catalog = A.catalog_for_profile profile in
  let component_locks = List.map (fun node ->
    B.charge budget 32; B.retain_monitor budget 1;
    let component = match A.Catalog.for_operation catalog (M.Node.kind node) with
      | Some component -> component
      | None -> Diagnostic.fail "synthetic_catalog_operation" (M.Node.kind node) in
    let raw = Json.Object ["schema_version",str Component_registry.Component_lock.schema_version;
      "node_id",str (M.Node.id node);"component_id",str (A.Component.id component);
      "version",str (A.Component.version component);"content_fingerprint",str (A.Component.fingerprint component)] in
    B.reserve_report budget raw;
    Component_registry.Component_lock.of_json raw) (M.nodes mechanism) in
  let mapping_json values = Json.Object (List.map (fun (key,values) -> key,Json.Array (List.map str values)) values) in
  let candidate_raw = Json.Object ["schema_version",str A.Candidate.schema_version;
    "intended_use",str "software_test";"human_therapeutic_admission",str "not_admitted";
    "request_fingerprint",str (Q.fingerprint checked);"mechanism",M.to_json mechanism;
    "observation_map",Observation_map.to_json mapping;"source_map",mapping_json source_map;
    "behavior_requirement_ids",mapping_json behavior_requirement_ids;
    "component_locks",Json.Array (List.map Component_registry.Component_lock.to_json component_locks);
    "generator_config",A.Config.to_json config] in
  B.reserve_report budget candidate_raw;
  ignore (A.Candidate.of_json candidate_raw);
  (* Complete constructors retain ID collision/graph validation responsibility.
     Only the maps survive this private witness; its graph never executes. *)
  let violations = violations ~budget policy mechanism in
  if violations <> [] then unsupported ("Synthetic proposal violates hard constraints: " ^ String.concat "; " violations);
  B.charge budget (Index.cardinal !sources + Index.cardinal !requirements);
  {sources=source_map;requirements=behavior_requirement_ids;nodes=List.length declared;gates=count_gates ~budget mechanism}
