open Bioc_wire
open Bioc_domain
module B = Behavior
module C = Realization_contract
module E = Realization_evidence
module D = Execution_data
module M = Mechanism
module MD = Model_execution_data
module N = Runtime_number
module O = Observation_map
module Budget = Realization_budget
module Reference = Bioc_semantics.Reference
module Synthetic = Bioc_candidate_runtime.Synthetic
module Names = Set.Make (String)
module Pairs = Set.Make (struct type t = string * string let compare = Stdlib.compare end)
let checker_version = "biocompiler.realization_checker.v0.3"
let implementation_version = "biocompiler.ocaml.realization_checker.v0.1"
let reference_evaluator_version = "biocompiler.behavior.evaluator.v0.2"
let settings = Json.Object [
  "scope", Json.String "supplied_contracts_and_finite_history";
  "intended_use", Json.String "software_test";
  "human_admission_policy", Json.String Admission.policy_version;
  "time", Json.String "right_continuous_piecewise_constant";
  "response", Json.String "active_inactive_bands_after_transition_deadlines";
  "nonvacuity", Json.String "checked_active_and_inactive_deadlines_for_every_response_and_complete_uncancelled_episodes";
  "contact_loss", Json.String "cancel_contact_scoped_obligations";
  "coverage", Json.String "all_selected_role_ongoing_outputs"]
type limits = Budget.limits
let make_limits = Budget.make_limits
let default_limits = Budget.default_limits
let limits_json limits = Json.Object (
  ("max_translated_history_bytes", Json.int Limits.max_request_bytes) ::
  ("max_translated_history_nodes", Json.int Limits.max_json_nodes) ::
  ("translated_history_work", Json.String "same_shared_work_utf8_bytes_plus_key_value_nodes_before_import") ::
  Json.object_fields (Budget.limits_json limits))
type usage = { work_charged : int; reserved_failure_work : int; monitor_peak : int;
  request_bytes : int; report_bytes : int }
let usage budget =
  let value = Budget.usage budget in
  {work_charged = value.work_charged; reserved_failure_work = value.reserved_failure_work;
   monitor_peak = value.monitor_peak; request_bytes = value.request_bytes; report_bytes = value.report_bytes}
let node_id value = Identity.Node.to_string (B.node_id value)
let role value = Option.map Identity.Role.to_string (B.role value)
let refs value = List.map Identity.Node.to_string (B.inputs value)
let kind value = B.kind_name (B.operation value)
let tail_actions value = match refs value with _ :: _ :: rest -> rest | _ -> []
let attr key node = List.assoc_opt key (Json.object_fields (B.attributes node))
let ongoing node = attr "ongoing" node = Some (Json.Bool true)
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let number_text = function N.Integer value -> Z.to_string value | N.Real value -> Canonical.float_string value
let horizon frames until =
  let value = match until with Some value -> value | None ->
    List.fold_left (fun _ frame -> D.Input_frame.time frame) N.zero frames in
  let finite, nonnegative = match value with
    | N.Integer value -> Float.is_finite (Z.to_float value), Z.sign value >= 0
    | N.Real value -> Float.is_finite value, value >= 0. in
  Diagnostic.require (finite && nonnegative) "realization_horizon" "Evaluation horizon must be a nonnegative finite number.";
  value
type prepared = { frames : D.Input_frame.t list; horizon : N.t; dependencies : E.Dependency_snapshot.t }
let prepare budget ?until behavior contract domain target mechanism observation_map frames =
  let frames = Budget.bounded_list budget frames in
  let horizon = horizon frames until in
  (* Reserve each complete supplied record before retaining the full history
     array. Future snapshots count even when execution stops before them. *)
  let retain value = Budget.reserve_request budget value; value in
  ignore (retain (obj ["behavior", Json.Null; "contract", Json.Null; "domain", Json.Null;
    "target", Json.Null; "mechanism", Json.Null; "observation_map", Json.Null; "history", arr [];
    "until", (match until with None -> Json.Null | Some value -> N.to_json value)]));
  let behavior_json = retain (B.to_json behavior) in
  let contract_json = retain (C.Behavior_contract.to_json contract) in
  let domain_json = retain (C.Operating_domain.to_json domain) in
  let target_json = retain (Build_request.Target.to_json target) in
  let mechanism_json = retain (M.to_json mechanism) in
  let observations_json = retain (O.to_json observation_map) in
  let history = List.map (fun frame -> retain (D.Input_frame.to_json frame)) frames in
  let dependencies = E.Dependency_snapshot.make_values (obj [
    "behavior", str (B.fingerprint behavior); "behavior_artifact", str (Legacy_ascii.fingerprint behavior_json);
    "contract", str (Canonical.fingerprint contract_json); "domain", str (Canonical.fingerprint domain_json);
    "target", str (Canonical.fingerprint target_json); "mechanism", str (Canonical.fingerprint mechanism_json);
    "observation_map", str (Canonical.fingerprint observations_json); "history", str (Legacy_ascii.fingerprint (arr history));
    "horizon", obj ["until", (match until with None -> Json.Null | Some value -> N.to_json value); "effective", N.to_json horizon];
    "checker", str checker_version; "model_runner", str Synthetic.runner_version;
    "reference_evaluator", str reference_evaluator_version;
    "settings", obj (("max_microsteps", Json.int 1000) :: Json.object_fields settings)]) in
  {frames; horizon; dependencies}
let dependencies_with_usage ?until ?limits ?parent behavior contract domain target mechanism observation_map history =
  let budget = Budget.create ?parent ?limits () in
  let prepared = prepare budget ?until behavior contract domain target mechanism observation_map history in
  prepared.dependencies, usage budget
let dependencies ?until ?limits ?parent behavior contract domain target mechanism observation_map history =
  fst (dependencies_with_usage ?until ?limits ?parent behavior contract domain target mechanism observation_map history)
let names budget values = List.fold_left (fun result value -> Budget.charge budget 1; Names.add value result) Names.empty values
let pairs budget values = List.fold_left (fun result value -> Budget.charge budget 1; Pairs.add value result) Pairs.empty values
let table budget key values =
  let table = Hashtbl.create 16 in
  List.iter (fun value -> Budget.charge budget 1; Hashtbl.replace table (key value) value) values; table
let runtime_observations budget behavior selected nodes =
  let pending = ref (List.filter (fun id ->
    Budget.charge budget 1; let node = Hashtbl.find nodes id in role node = None || role node = Some selected)
    (List.map Identity.Node.to_string (B.roots behavior))) in
  let live = Hashtbl.create 32 and required = ref Pairs.empty in
  while !pending <> [] do
    Budget.charge budget 1;
    let id = List.hd !pending in pending := List.tl !pending;
    if not (Hashtbl.mem live id) then (
      Hashtbl.add live id (); let node = Hashtbl.find nodes id in
      let children = match B.operation node, refs node with B.Signature _, first :: _ -> [first] | B.Signature _, [] -> [] | _, values -> values in
      List.iter (fun id -> Budget.charge budget 1; pending := id :: !pending) children;
      if role node = None || role node = Some selected then (
        match B.operation node, refs node with
        | B.Qualitative band, signal :: _ ->
            let field = match band with B.Present -> "present" | B.High -> "high" | B.Low -> "low" in
            required := Pairs.add (signal, field) !required
        | (B.Signature _ | B.Scope _ | B.Role _), _ -> ()
        | _, inputs -> List.iter (fun id -> Budget.charge budget 1;
            if kind (Hashtbl.find nodes id) = "signal" then required := Pairs.add (id, "value") !required) inputs))
  done;
  !required
let boolean_type = Type_spec.of_json (obj ["kind", str "condition"; "name", str "Condition"; "dimensions", obj []; "arguments", arr []])
let sample field sample = match sample with
  | None -> C.Other
  | Some sample -> match field with
      | O.Value -> (match D.Sample.value sample with None -> C.Other | Some value -> C.Number value)
      | O.Present -> (match D.Sample.present sample with None -> C.Other | Some value -> C.Boolean value)
      | O.High -> (match D.Sample.high sample with None -> C.Other | Some value -> C.Boolean value)
      | O.Low -> (match D.Sample.low sample with None -> C.Other | Some value -> C.Boolean value)
let engine_sample = function C.Boolean value -> MD.Boolean value | C.Number value -> MD.Number value
  | C.Scalar _ | C.Other -> Diagnostic.fail "realization_translation" "Validated observation lost its numeric or Boolean sample."
let execution_message nodes (error : Diagnostic.t) =
  (* One explicit existing engine boundary has a different standalone message.
     Recover the historical checker text only for this exact typed failure and
     its checked source node; unrelated arithmetic errors keep their identity. *)
  if error.code = "evaluation_arithmetic" && error.message = "evaluation_division_by_zero: Division by zero during reference execution." then
    match error.path with
    | Some path when String.starts_with ~prefix:"/nodes/" path ->
        let id = String.sub path 7 (String.length path - 7) in
        (match Hashtbl.find_opt nodes id with
        | Some node when B.operation node = B.Arithmetic B.Divide ->
            "Division by zero during behavior evaluation [node " ^ id ^ "]" ^
              (match B.source node with None -> "" | Some source -> " (" ^ source.file ^ ":" ^ Z.to_string source.line ^ ")")
        | _ -> error.message)
    | _ -> error.message
  else error.message
exception Stop of E.Check_result.t
let check_with_usage ?until ?limits ?parent behavior contract domain target mechanism observation_map history =
  let budget = Budget.create ?parent ?limits () in
  let prepared = prepare budget ?until behavior contract domain target mechanism observation_map history in
  let frames = prepared.frames and horizon = prepared.horizon and dependencies = prepared.dependencies in
  let requirements = C.Behavior_contract.requirements contract in
  let ids = List.map C.Response.id requirements in
  Budget.reserve_report budget (E.Check_result.to_json
    (E.Check_result.make ~outcome:E.Unknown ~dependencies ~checked_requirement_ids:ids ()));
  let result ?requirement ?node outcome code message =
    let node_id = Option.map node_id node and source = Option.bind node B.source in
    let diagnostic = E.Check_diagnostic.make ~code ~message ?requirement_id:requirement ?node_id ?source () in
    Budget.reserve_report budget (E.Check_diagnostic.to_json diagnostic);
    let result = E.Check_result.make ~outcome ~dependencies ~checked_requirement_ids:ids ~diagnostics:[diagnostic] () in
    Budget.validate_report budget result; raise (Stop result) in
  let check () =
    let admission = Bioc_checker.Admission_check.for_target ~target ~boundary:Admission.Verification ~components:[] in
    if Admission.Assessment.decision admission <> Admission.Software_only then
      result E.Unsupported "human_profile_not_admitted" (String.concat "; " (Admission.Assessment.diagnostics admission));
    if C.Behavior_contract.behavior_fingerprint contract <> B.fingerprint behavior then
      result E.Fail "behavior_identity" "The response contract refers to a different BehaviorProgram.";
    let nodes = table budget node_id (B.nodes behavior) and model_nodes = table budget M.Node.id (M.nodes mechanism) in
    let selected = C.Operating_domain.role domain in
    if not (match Hashtbl.find_opt nodes selected with Some node -> kind node = "role" | None -> false) then
      result E.Fail "role_identity" "OperatingDomain.role must identify an exact behavior role node.";
    let domain_values = C.Operating_domain.inputs domain in
    let domain_key value = C.Input_domain.signal_id value, C.Input_domain.field_name value in
    let domain_inputs = table budget domain_key domain_values in
    let domain_keys = pairs budget (List.map domain_key domain_values) in
    if not (Pairs.equal domain_keys (runtime_observations budget behavior selected nodes)) then
      result E.Fail "input_domain_coverage" "Operating-domain inputs must cover exactly the selected role's runtime observations, excluding unused signature metadata.";
    let input_values = O.inputs observation_map in
    let input_key value = O.Input_binding.signal_id value, O.Input_binding.field_name value in
    let inputs = table budget input_key input_values in
    if Hashtbl.length inputs <> List.length input_values || not (Pairs.equal domain_keys (pairs budget (List.map input_key input_values))) then
      result E.Fail "input_binding_coverage" "Input bindings must cover the operating-domain observations exactly once.";
    let model_input_ids = M.nodes mechanism |> List.filter (fun node -> Budget.charge budget 1; M.Node.kind node = "input") |> List.map M.Node.id |> names budget in
    let mapped_input_ids = List.map O.Input_binding.mechanism_input_id input_values in
    let mapped_inputs = names budget mapped_input_ids in
    if Names.cardinal mapped_inputs <> List.length mapped_input_ids || not (Names.equal mapped_inputs model_input_ids) then
      result E.Fail "model_input_coverage" "Every model input must have one distinct observation binding.";
    List.iter (fun item ->
      Budget.charge budget 1;
      let source = match Hashtbl.find_opt nodes (C.Input_domain.signal_id item) with
        | Some source when kind source = "signal" && role source = Some selected -> source
        | _ -> result E.Fail "input_source" "Input domain does not identify a signal owned by the selected role." in
      let expected_type = match C.Input_domain.field item with O.Value ->
          (match B.data_type source with Some value -> value | None -> Diagnostic.fail "realization_source_type" "A checked numeric signal lacks its type.")
        | O.Present | O.High | O.Low -> boolean_type in
      let endpoint = C.Input_domain.observable item in
      let scope = if B.contact_bound source then C.Observable.Contact else C.Observable.Cell in
      if C.Observable.role endpoint <> selected || C.Observable.scope endpoint <> scope || not (Type_spec.compatible (C.Observable.dtype endpoint) expected_type) then
        result ~node:source E.Fail "input_semantics" "Input endpoint role, scope, or type differs from the authored observation.";
      let port = Hashtbl.find model_nodes (O.Input_binding.mechanism_input_id (Hashtbl.find inputs (domain_key item))) in
      if not (Json.equal (C.Observable.to_json endpoint) (C.Observable.to_json (M.Node.output port))) then
        result ~node:source E.Fail "input_endpoint" "Model input must match the domain's explicit endpoint identity, role, scope, compartment and type.") domain_values;
    let output_values = O.outputs observation_map in
    let outputs = table budget O.Output_binding.requirement_id output_values in
    let mapped_ids = List.map O.Output_binding.mechanism_output_id output_values in
    let mapped_set = names budget mapped_ids and requirement_set = names budget ids in
    if Hashtbl.length outputs <> List.length output_values || not (Names.equal (names budget (List.map O.Output_binding.requirement_id output_values)) requirement_set)
       || Names.cardinal mapped_set <> List.length mapped_ids || not (Names.equal mapped_set (names budget (M.outputs mechanism))) then
      result E.Fail "output_binding_coverage" "Output bindings must match every requirement and declared model output one-to-one.";
    List.iter (fun node -> Budget.charge budget 1;
      if not (Names.subset (names budget (M.Node.requirement_ids node)) requirement_set) then
        result E.Fail "unknown_model_requirement" ("Mechanism node " ^ Diagnostic_text.repr (M.Node.id node) ^ " refers to an unknown response requirement.")) (M.nodes mechanism);
    let response_pairs = ref Pairs.empty in
    List.iter (fun requirement ->
      Budget.charge budget 1;
      let requirement_id = C.Response.id requirement in
      let rule, specification = match Hashtbl.find_opt nodes (C.Response.rule_id requirement), Hashtbl.find_opt nodes (C.Response.specification_id requirement) with
        | Some rule, Some specification when kind rule = "rule" && role rule = Some selected && List.mem (node_id specification) (tail_actions rule) -> rule, specification
        | _ -> result ~requirement:requirement_id E.Fail "requirement_source" "Response requirement must identify an installed rule and its exact action specification." in
      let pair = node_id rule, node_id specification in
      if Pairs.mem pair !response_pairs then result ~requirement:requirement_id ~node:rule E.Fail "duplicate_response" "One action specification in one rule must have one response requirement.";
      response_pairs := Pairs.add pair !response_pairs;
      let primitive = if B.operation specification = B.Action_pulse then Hashtbl.find nodes (List.hd (refs specification)) else specification in
      if not (ongoing primitive) then result ~requirement:requirement_id ~node:specification E.Unsupported "instantaneous_response" "This profile checks ongoing requests and explicit pulses, not instantaneous reactions.";
      if B.operation primitive = B.Action_secrete B.Expression then result ~requirement:requirement_id ~node:specification E.Unsupported "quantitative_action_law" "A dynamic requested output rate needs a quantitative tracking contract beyond activation bands.";
      let endpoint = C.Response.observable requirement in
      let scope = if B.contact_bound specification then C.Observable.Contact else C.Observable.Cell in
      if C.Observable.role endpoint <> selected || C.Observable.scope endpoint <> scope then
        result ~requirement:requirement_id ~node:specification E.Fail "output_semantics" "Response endpoint role and scope must match the installed action.";
      let output = Hashtbl.find_opt model_nodes (O.Output_binding.mechanism_output_id (Hashtbl.find outputs requirement_id)) in
      let output = match output with Some output when M.Node.kind output = "output" && Json.equal (C.Observable.to_json endpoint) (C.Observable.to_json (M.Node.output output)) -> output
        | _ -> result ~requirement:requirement_id ~node:specification E.Fail "output_endpoint" "Model output must match the response's exact endpoint identity, role, scope, compartment and type." in
      if not (List.mem requirement_id (M.Node.requirement_ids output)) then
        result ~requirement:requirement_id ~node:specification E.Fail "missing_output_lineage" "Mapped model output must retain its response requirement identity.") requirements;
    let installed = ref Pairs.empty in
    List.iter (fun rule -> Budget.charge budget 1; if kind rule = "rule" && role rule = Some selected then
      List.iter (fun id -> Budget.charge budget 1; let action = Hashtbl.find nodes id in
        if ongoing action then installed := Pairs.add (node_id rule, id) !installed
        else if kind action <> "action.state_set" then result ~node:action E.Unsupported "instantaneous_output" "The selected role has instantaneous output requests outside this response profile.") (tail_actions rule)) (B.nodes behavior);
    if not (Pairs.equal !response_pairs !installed) then result E.Unsupported "uncontracted_outputs" "The contract must cover every installed ongoing output of the selected role; this profile does not silently accept partial output coverage.";
    let capabilities = Names.union (names budget (C.Operating_domain.required_capabilities domain)) (names budget (M.required_capabilities mechanism)) in
    let missing = Names.diff capabilities (names budget (Build_request.Target.capabilities target)) in
    if not (Names.is_empty missing) then result E.Fail "missing_capabilities" ("Target lacks declared capabilities: " ^ String.concat ", " (Names.elements missing));
    let compartments = names budget (List.map M.Node.compartment (M.nodes mechanism)) in
    if not (Names.subset compartments (names budget (Build_request.Target.compartments target))) then result E.Fail "missing_compartments" "Target does not declare every model endpoint compartment.";
    if List.exists (fun node -> Budget.charge budget 1; M.Node.role node <> selected) (M.nodes mechanism) then result E.Unsupported "multiple_model_roles" "This checker executes one engineered-cell role per finite trace.";
    (match frames with [] -> result E.Unknown "empty_history" "No input history was supplied; no response was exercised."
    | first :: rest ->
        let previous = ref (D.Input_frame.time first) in
        if not (N.equal !previous N.zero) || List.exists (fun frame -> Budget.charge budget 1;
          let current = D.Input_frame.time frame in let invalid = N.compare current !previous <= 0 in previous := current; invalid) rest then
          result E.Unknown "invalid_history" "Input snapshots must start at zero and have strictly increasing timestamps.");
    List.iter (fun frame -> Budget.charge budget 1; if N.compare (D.Input_frame.time frame) horizon <= 0 then (
      let contacts = D.Input_frame.contacts frame in
      (match C.Operating_domain.max_contacts domain with Some maximum when Z.compare (Z.of_int (List.length contacts)) maximum > 0 ->
         result E.Unknown "outside_domain" "Input history exceeds the domain's maximum simultaneous contacts." | _ -> ());
      List.iter (fun item -> Budget.charge budget 1;
        let samples = if C.Input_domain.scope item = C.Observable.Contact then List.map snd contacts else [D.Input_frame.signals frame] in
        List.iter (fun samples -> Budget.charge budget (1 + List.length samples);
          let observed = sample (C.Input_domain.field item) (List.assoc_opt (C.Input_domain.signal_id item) samples) in
          if not (C.Input_domain.contains item observed) then result ~node:(Hashtbl.find nodes (C.Input_domain.signal_id item)) E.Unknown "outside_domain"
            ("Missing or out-of-domain " ^ C.Input_domain.field_name item ^ " observation at time " ^ number_text (D.Input_frame.time frame) ^ ".")) samples) domain_values)) frames;
    (* Input identities can expand the translated history beyond the source
       snapshots. Reserve one cumulative UTF-8 byte/key-value-node scope before
       typed frame import, then charge construction to the same shared work.
       This derived inventory never changes original request identity/counters. *)
    let translated = Bioc_checker.Work_budget.create_output ~profile:Budget.resource_profile
      ~error_code:"realization_translation_limit" ~max_bytes:Limits.max_request_bytes
      ~max_nodes:Limits.max_json_nodes () in
    Bioc_checker.Work_budget.reserve_json translated (arr []);
    Budget.charge budget 3;
    let model_history = List.filter_map (fun frame -> Budget.charge budget 1;
      if N.compare (D.Input_frame.time frame) horizon > 0 then None else (
        let values = ref [] and contacts = List.map (fun (id, _) -> Budget.charge budget 1; id, ref []) (D.Input_frame.contacts frame) in
        List.iter (fun binding -> Budget.charge budget 1;
          let item = Hashtbl.find domain_inputs (input_key binding) in
          let signal = C.Input_domain.signal_id item and field = C.Input_domain.field item and target_id = O.Input_binding.mechanism_input_id binding in
          if C.Input_domain.scope item = C.Observable.Cell then (
            let samples = D.Input_frame.signals frame in Budget.charge budget (List.length samples);
            values := (target_id, engine_sample (sample field (List.assoc_opt signal samples))) :: !values)
          else List.iter (fun (id, samples) -> Budget.charge budget (1 + List.length samples + List.length contacts);
            let target = List.assoc id contacts in target := (target_id, engine_sample (sample field (List.assoc_opt signal samples))) :: !target) (D.Input_frame.contacts frame)) input_values;
        let values = List.rev !values and contacts = List.map (fun (id, values) -> id, List.rev !values) contacts in
        let mapping values = obj (List.map (fun (id, value) -> id, MD.value_to_json value) values) in
        let raw = obj ["time", N.to_json (D.Input_frame.time frame); "values", mapping values;
          "contacts", obj (List.map (fun (id, values) -> id, mapping values) contacts)] in
        (* The extra zero reserves a conservative separator byte/node. *)
        Bioc_checker.Work_budget.reserve_json translated (Json.int 0);
        Bioc_checker.Work_budget.reserve_json translated raw;
        let nodes = 7 + 2 * List.length values + 2 * List.length contacts
          + List.fold_left (fun count (_, values) -> count + 2 * List.length values) 0 contacts in
        Budget.charge budget (String.length (Canonical.encode raw) + nodes + 1);
        Some (MD.Input_frame.of_json raw))) frames in
    let engine maximum execute charge =
      (* Hold capacity in the same parent for a possible ordinary-failure
         diagnostic. It is charged only when actually published, never reset
         into an independent reporting budget or counted as completed work. *)
      let available = Budget.remaining budget - Budget.failure_finish_allowance budget in
      if available <= 0 then Budget.charge budget (Budget.remaining budget + 1);
      let allowance = min maximum available in
      match execute allowance with
      | value, consumed -> charge consumed; value
      | exception Diagnostic.Error error when Budget.is_resource_error budget error || List.mem error.code
          ["evaluation_work_limit"; "evaluation_output_limit"; "synthetic_work_limit";
           "synthetic_frame_limit"; "synthetic_trace_limit"; "synthetic_state_limit"] ->
          (* An engine exposes no partial usage on failure. Forfeit its full
             allocated allowance before reraising so a shared parent cannot
             repeatedly reuse unaccounted failed work. Integration-grid bounds
             are a source-language execution failure, not this resource list. *)
          Budget.burn_failure budget allowance;
          raise (Diagnostic.Error error)
      | exception Diagnostic.Error error ->
          Budget.burn_failure budget allowance;
          result E.Unknown "execution_unavailable" ("The supplied history could not be evaluated: " ^ execution_message nodes error) in
    let desired = engine 10_000_000 (fun allowance -> Reference.evaluate_with_usage ~role:selected ~until:horizon ~max_microsteps:1000
      ~budget:(Reference.make_budget ~max_work:allowance ()) behavior frames) (fun (usage : Reference.usage) -> Budget.charge budget usage.work) in
    let actual = engine 50_000_000 (fun allowance -> Synthetic.run_with_usage ~until:horizon
      ~limits:(Synthetic.make_limits ~max_work:allowance ()) mechanism model_history) (fun (usage : Synthetic.usage) -> Budget.charge budget usage.work) in
    Realization_monitor.check ~budget ~behavior ~contract ~domain ~observation_map ~history:frames ~desired ~actual ~dependencies ~horizon in
  let result = try check () with Stop result -> result in
  result, usage budget
let check ?until ?limits ?parent behavior contract domain target mechanism observation_map history =
  fst (check_with_usage ?until ?limits ?parent behavior contract domain target mechanism observation_map history)
