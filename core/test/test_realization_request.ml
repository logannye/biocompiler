open Bioc_wire
open Bioc_domain
module R = Realization_request
module C = Bioc_realization_checker.Checked_request
module L = Bioc_checker.Lowering_check
module W = Bioc_checker.Work_budget
let count = ref 0
let check condition message = incr count; if not condition then failwith message
let reject code run =
  incr count;
  match run () with
  | _ -> failwith ("Expected request rejection: " ^ code)
  | exception Diagnostic.Error error ->
      if error.code <> code then failwith ("Expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message)
let obj fields = Json.Object fields
let str value = Json.String value
let field key value = Json.field key (Json.object_fields value)
let set key item value = obj ((key, item) :: List.remove_assoc key (Json.object_fields value))
let modify key f value = set key (f (field key value)) value
let array_map f = function Json.Array values -> Json.Array (List.map f values) | _ -> assert false
(* Independently constructed literal source and Behavior, checked by original
   Python request semantics. Missing runtime mappings deliberately remain later
   realization obligations; request freezing alone does not check them. *)
let raw = Json.parse {|{"behavior":{"name":"literal/request/β","nodes":[{"attributes":{"cell_type":"abstract_cell","engineering":"in_vivo","name":"cell"},"contact_bound":false,"data_type":null,"id":"cell","inputs":[],"kind":"role","requirement_ids":[],"role":null,"source":{"file":"literal/request.py","function":"author","line":7}}],"parameter_bindings":{},"policies":{"condition_impulses":"onset","condition_ongoing":"level","contact_binding":"same_object_before_existential_aggregation","contact_disappearance":"clear_episode_history_and_contact_pulses","event_ongoing":"explicit_duration_required","followed_by":"strictly_later_inclusive_window_nonconsuming","held_for":"full_continuous_interval","history":"since_initialization","initial_time":0,"initial_true":"rising_event","local_action_binding":"existential_aggregate_then_onset","memory_binding":"any_contact_onset_sets_cell_local_memory","memory_dependencies":"causal_topological_settlement","memory_initial":false,"memory_precedence":"reset_then_new_onset_then_expiry","memory_setting":"onset_latest_refresh","memory_visibility":"settled_controls_before_rule_effects","observation_missing":"error","outputs":"abstract_requests_no_input_side_effects","profile":"abstract_single_cell.v0.1","pulse_interval":"closed_start_open_end","pulse_retrigger":"extend_from_latest_trigger","qualitative_observations":"explicit_boolean","recently":"includes_present_excludes_expiry","simultaneous_inputs":"atomic_snapshot","state_propagation":"atomic_microsteps_until_stable","state_reads":"shared_pre_update_state","state_writes":"coalesce_identical_else_error","targeted_action_binding":"per_contact_object","time":"nonnegative_seconds_piecewise_constant","timer_input_precedence":"external_snapshot_before_due_timers"},"requirements":[],"roots":["cell"],"schema_version":"biocompiler.behavior.v0.1","source_fingerprint":"a77ea73dd57177b3141e6350f0bbada4b09af8f029b49a77b892a2381a848360","source_links":{"cell":["cell"]}},"build_request":{"artifact_scope":"abstract_behavior","behavior_profile":"biocompiler.behavior.v0.1","explicit_overrides":{},"implementation_constraints":{},"intent":{"name":"literal/request/β","nodes":[{"attributes":{"cell_type":"abstract_cell","engineering":"in_vivo","name":"cell"},"data_type":null,"id":"cell","inputs":[],"kind":"role","role":null,"source":{"file":"literal/request.py","function":"author","line":7}}],"roots":["cell"],"schema_version":"biocompiler.intent.v0.1"},"parameter_metadata":{},"preferences":{},"provenance":{"dependency_identities":{},"external_inputs":{},"locations":{},"recorded_at":null,"schema_version":"biocompiler.elaboration_provenance.v0.1","source_identities":{}},"resolved_bindings":{},"resolved_defaults":{},"schema_version":"biocompiler.build_request.v0.1","target":{"capabilities":[],"compartments":["abstract"],"context_id":"host","context_version":"1","payload_format":"RNA","resources":{},"schema_version":"biocompiler.target.v0.1"}},"contract":{"behavior_fingerprint":"9d15dd99fbcfb3d01ef3b8540f49c47485b5502655994119b59cae8e5b1bb5b4","id":"contract","requirements":[{"active_range":{"kind":"interval","lower":{"canonical_value":1,"kind":"scalar","type":{"arguments":[],"dimensions":{},"kind":"scalar","name":"Level"},"unit":"1","value":1},"type":{"arguments":[{"arguments":[],"dimensions":{},"kind":"scalar","name":"Level"}],"dimensions":{},"kind":"interval","name":"Interval[Level]"},"upper":{"canonical_value":2,"kind":"scalar","type":{"arguments":[],"dimensions":{},"kind":"scalar","name":"Level"},"unit":"1","value":2}},"id":"response","inactive_range":{"kind":"interval","lower":{"canonical_value":0,"kind":"scalar","type":{"arguments":[],"dimensions":{},"kind":"scalar","name":"Level"},"unit":"1","value":0},"type":{"arguments":[{"arguments":[],"dimensions":{},"kind":"scalar","name":"Level"}],"dimensions":{},"kind":"interval","name":"Interval[Level]"},"upper":{"canonical_value":0.2,"kind":"scalar","type":{"arguments":[],"dimensions":{},"kind":"scalar","name":"Level"},"unit":"1","value":0.2}},"max_activation_delay":{"canonical_value":1,"kind":"scalar","type":{"arguments":[],"dimensions":{"time":1},"kind":"scalar","name":"Duration"},"unit":"s","value":1},"max_deactivation_delay":{"canonical_value":0,"kind":"scalar","type":{"arguments":[],"dimensions":{"time":1},"kind":"scalar","name":"Duration"},"unit":"s","value":0},"observable":{"compartment":"abstract","dtype":{"arguments":[],"dimensions":{},"kind":"scalar","name":"Level"},"id":"output","role":"cell","schema_version":"biocompiler.observable.v0.1","scope":"cell"},"rule_id":"unbound-rule","schema_version":"biocompiler.response_requirement.v0.1","specification_id":"unbound-action"}],"schema_version":"biocompiler.behavior_contract.v0.1"},"domain":{"id":"domain","inputs":[{"allowed":[false,true],"field":"present","observable":{"compartment":"abstract","dtype":{"arguments":[],"dimensions":{},"kind":"condition","name":"Condition"},"id":"input","role":"cell","schema_version":"biocompiler.observable.v0.1","scope":"cell"},"schema_version":"biocompiler.input_domain.v0.1","signal_id":"unbound-signal"}],"max_contacts":null,"minimum_horizon":{"canonical_value":1,"kind":"scalar","type":{"arguments":[],"dimensions":{"time":1},"kind":"scalar","name":"Duration"},"unit":"s","value":1},"required_capabilities":[],"role":"cell","schema_version":"biocompiler.operating_domain.v0.1","version":"1"},"schema_version":"biocompiler.realization_request.v0.1"}|}
let baseline = R.of_json raw
let checked () = C.check baseline
let parent maximum = W.create ~profile:"literal.parent" ~error_code:"literal_parent_exhausted" ~maximum ()
let source_file file value = modify "nodes" (array_map (modify "source" (set "file" (str file)))) value
let change_roles role value = value
  |> modify "domain" (fun domain -> domain |> set "role" (str role)
      |> modify "inputs" (array_map (modify "observable" (set "role" (str role)))))
  |> modify "contract" (modify "requirements" (array_map (modify "observable" (set "role" (str role)))))
let literals () =
  check (R.fingerprint baseline = "4ee8d8d1892a02fb08286e006bc34367a8abc60db8726781b441d1a6c08d2b5e") "Semantic request identity differs";
  check (R.artifact_fingerprint baseline = "b9e3eeb652880795b84a16c388a8362331ea1a7da27acd673ba2bfdc323198bf") "Full artifact identity differs";
  check (R.upstream_request_fingerprint baseline = "2d5be0aaf8d2f541f0e470f0841f6a50fbdc14d09dc337b070e73b3b4f4dae90") "Upstream identity differs";
  check (R.canonical_size baseline = 5416) "Request canonical byte count differs";
  let value = checked () in
  check (Json.equal (C.to_json value) (R.to_json baseline) && C.fingerprint value = R.fingerprint baseline
         && C.artifact_fingerprint value = R.artifact_fingerprint baseline) "Checked envelope changed canonical request";
  check (L.passed (C.lowering_report value) && List.mem "candidate_acceptance" (L.unimplemented_obligations (C.lowering_report value)))
    "Request correspondence became realization acceptance";
  check (Build_request.Target.fingerprint (C.target value) = Build_request.Target.fingerprint (Option.get (R.target baseline)))
    "Checked target is not full original target";
  let rebuilt = R.make ~build_request:(R.build_request baseline) ~behavior:(R.behavior baseline)
      ~contract:(R.contract baseline) ~domain:(R.domain baseline) in
  check (Json.equal (R.to_json rebuilt) raw) "Typed request constructor changed normalized document";
  ignore (C.make ~build_request:(R.build_request baseline) ~behavior:(R.behavior baseline)
      ~contract:(R.contract baseline) ~domain:(R.domain baseline) ());
  let other_scope = raw |> modify "build_request" (set "artifact_scope" (str "exact_cds")) |> C.of_json in
  check (C.fingerprint other_scope <> C.fingerprint value) "Request imposed a later synthetic-only scope gate";
  let changed_domain = raw |> modify "domain" (set "version" (str "2")) |> C.of_json in
  check (C.fingerprint changed_domain <> C.fingerprint value
         && R.upstream_request_fingerprint (C.request changed_domain) = R.upstream_request_fingerprint baseline)
    "Downstream contract changed upstream authority";
  let relocation = raw |> modify "build_request" (modify "intent" (source_file "relocated/β.py"))
      |> modify "behavior" (source_file "relocated/β.py") |> C.of_json in
  check (C.fingerprint relocation = C.fingerprint value && C.artifact_fingerprint relocation <> C.artifact_fingerprint value)
    "Coordinated source relocation lost semantic/artifact distinction"
let semantics () =
  let missing_target = raw |> modify "build_request" (set "target" Json.Null) in
  check (R.target (R.of_json missing_target) = None) "Structural decoder claimed contextual target acceptance";
  reject "realization_request_target" (fun () -> C.of_json missing_target);
  let wrong_behavior = raw |> modify "behavior" (set "name" (str "forged")) in
  ignore (R.of_json wrong_behavior);
  reject "lowering_source_identity" (fun () -> C.of_json wrong_behavior);
  let wrong_contract = raw |> modify "contract" (set "behavior_fingerprint" (str (String.make 64 'a'))) in
  ignore (R.of_json wrong_contract);
  reject "realization_request_behavior_identity" (fun () -> C.of_json wrong_contract);
  reject "realization_request_target" (fun () -> C.of_json
      (wrong_behavior |> modify "build_request" (set "target" Json.Null)));
  reject "lowering_source_identity" (fun () -> C.of_json
      (wrong_behavior |> modify "contract" (set "behavior_fingerprint" (str (String.make 64 'a')))));
  let role = raw |> modify "domain" (fun domain -> domain |> set "role" (str "absent")
      |> modify "inputs" (array_map (modify "observable" (set "role" (str "absent"))))) in
  reject "realization_request_role" (fun () -> C.of_json role);
  reject "realization_request_unknown_role" (fun () -> C.of_json (change_roles "absent" raw));
  reject "lowering_source_location" (fun () -> C.of_json (raw |> modify "behavior" (source_file "one-sided.py")));
  reject "unsupported_lowering_operation" (fun () -> C.of_json (raw |> modify "build_request"
      (modify "intent" (modify "nodes" (array_map (set "kind" (str "future.operation")))))));
  reject "unsupported_schema" (fun () -> C.of_json (set "schema_version" (str "future") raw));
  reject "unknown_field" (fun () -> R.of_json (set "accepted" (Json.Bool true) raw));
  reject "missing_field" (fun () -> R.of_json (obj (List.remove_assoc "domain" (Json.object_fields raw))));
  reject "invalid_type" (fun () -> R.of_json (set "domain" Json.Null raw))
let resources () =
  let rec cycle = Json.Array [cycle] in reject "realization_request_cycle" (fun () -> R.of_json cycle);
  let rec spine = Json.Null :: spine in reject "realization_request_limit" (fun () -> R.of_json (Json.Array spine));
  reject "realization_request_limit" (fun () -> R.of_json (Json.String (String.make (Limits.max_string_bytes + 1) 'x')));
  reject "duplicate_key" (fun () -> R.of_json (obj ["x",Json.Null;"x",Json.Null]));
  let large = str (String.make Limits.max_string_bytes 'x') in
  let large_build = field "build_request" raw |> modify "provenance" (set "external_inputs" (obj ["a",large;"b",large;"c",large]))
      |> Build_request.of_json in
  let large_contract = field "contract" raw |> modify "requirements" (array_map (modify "observable" (set "id" large)))
      |> Realization_contract.Behavior_contract.of_json in
  reject "realization_request_limit" (fun () -> R.make ~build_request:large_build ~behavior:(R.behavior baseline)
      ~contract:large_contract ~domain:(R.domain baseline));
  let generous = parent 100_000_000 in
  let result = C.check ~parent:generous baseline in
  let used = 100_000_000 - W.remaining generous in
  check (used > R.canonical_size baseline) "Fresh lowering escaped shared request work accounting";
  let exact = parent used in ignore (C.check ~parent:exact baseline);
  check (W.remaining exact = 0) "Exact request work allowance differs";
  reject "literal_parent_exhausted" (fun () -> C.check ~parent:(parent (used - 1)) baseline);
  let repeated = parent (2 * used) in ignore (C.check ~parent:repeated baseline); ignore (C.check ~parent:repeated baseline);
  check (W.remaining repeated = 0) "Repeated checks reset shared accounting";
  reject "literal_parent_exhausted" (fun () -> C.check ~parent:repeated baseline);
  let authority = R.build_request baseline and behavior = R.behavior baseline in
  let original = L.check ~expected_request:authority ~behavior in
  let lowering_parent = parent 100_000_000 in
  let bounded = L.check_with_budget ~parent:lowering_parent ~expected_request:authority ~behavior () in
  check (Json.equal (L.to_json original) (L.to_json bounded)) "Lowering work envelope changed historical report";
  let used = 100_000_000 - W.remaining lowering_parent in
  ignore (L.check_with_budget ~parent:(parent used) ~expected_request:authority ~behavior ());
  reject "literal_parent_exhausted" (fun () -> L.check_with_budget ~parent:(parent (used - 1)) ~expected_request:authority ~behavior ());
  check (C.fingerprint result = C.fingerprint (checked ())) "Failed resource charge mutated later checked authority"
let () =
  if Array.length Sys.argv <> 1 then failwith "test_realization_request accepts no arguments";
  literals (); semantics (); resources ();
  Printf.printf "Realization request: %d structural, fresh authority, identity and budget literals passed\n" !count
