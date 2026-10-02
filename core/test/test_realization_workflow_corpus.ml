open Bioc_wire
open Bioc_domain
module S = Synthetic_authority
module C = Realization_contract
module E = Realization_evidence
module R = Bioc_realization_checker.Realization_check
module B = Bioc_realization_checker.Component_behavior_check
module Y = Bioc_realization_checker.Synthetic_candidate_check
module A = Bioc_realization_checker.Component_assembly_check
module G = Bioc_synthetic_producer.Generator
module P = Bioc_synthetic_producer.Selection
module K = Bioc_synthetic_producer.Components
module Q = Synthetic_selection
let require condition message = if not condition then failwith message
let field key value = Json.field key (Json.object_fields value)
let text key value = Json.string (field key value)
let array key value = Json.array (field key value)
let integer value = Z.to_int (Json.integer value)
let obj value = Json.Object value
let str value = Json.String value
let equal label left right = require (Canonical.encode left = Canonical.encode right) (label ^ ": full record or numeric identity differs")
let props fingerprint = Some (obj ["fingerprint", str fingerprint])
let horizon value = match field "until" value with Json.Null -> None | value -> Some (Runtime_number.of_json value)
let history value = array "history" value |> List.map Execution_data.Input_frame.of_json
let optional decode = function Json.Null -> None | value -> Some (decode value)
let option_json encode = function None -> Json.Null | Some value -> encode value
let alternative value = Q.Alternative.to_json value, Some (obj [
  "fingerprint",str (Q.Alternative.fingerprint value); "gate_count",option_json Json.int (Q.Alternative.gate_count value);
  "status",str (Q.Alternative.status value)])
let selection value = Q.Result.to_json value, Some (obj [
  "fingerprint",str (Q.Result.fingerprint value); "selected_strategy",option_json str (Q.Result.selected_strategy value);
  "candidate",option_json S.Candidate.to_json (Q.Result.candidate value); "outcome",str (Q.Result.outcome value);
  "checked_candidates",Json.int (Q.Result.checked_candidates value); "rejected_candidates",Json.int (Q.Result.rejected_candidates value)])
let candidate value = S.Candidate.to_json value, props (S.Candidate.fingerprint value)
let rec prerequisite operation value = match operation with
  | "SyntheticAlternative" -> alternative (Q.Alternative.of_json value)
  | "SyntheticSelectionResult" -> selection (Q.Result.of_json value)
  | "SyntheticAlternative.make" ->
      alternative (Q.Alternative.make ~strategy:(text "strategy" value)
        ?candidate:(optional S.Candidate.of_json (field "candidate" value))
        ~constraint_violations:(array "constraint_violations" value |> List.map Json.string)
        ?check:(optional E.Check_result.of_json (field "check" value))
        ?generation_error:(optional Json.string (field "generation_error" value)) ())
  | "SyntheticSelectionResult.make" ->
      selection (Q.Result.make ~request_fingerprint:(text "request_fingerprint" value)
        ~history_fingerprint:(text "history_fingerprint" value) ?until:(horizon value)
        ~config:(S.Config.of_json (field "config" value)) ~minimize:(text "minimize" value)
        (array "alternatives" value |> List.map Q.Alternative.of_json))
  | "_generate_synthetic" | "generate_synthetic" ->
      let request = Realization_request.of_json (field "request" value) in
      let config = optional S.Config.of_json (field "config" value) in
      candidate ((if operation = "generate_synthetic" then G.generate else G.propose) ?config request)
  | "select_synthetic" ->
      selection (P.select ?config:(optional S.Config.of_json (field "config" value)) ?until:(horizon value)
        (Realization_request.of_json (field "request" value)) (history value))
  | "adapt_synthetic_components" ->
      K.adapt ?until:(horizon value) (Realization_request.of_json (field "request" value))
        (S.Candidate.of_json (field "candidate" value)) (history value) |> K.to_json, None
  | "selection_producer_mutation" ->
      let authority = field "authority" value in
      require (List.mem (text "recipe" value) ["both_execution_failures";"faulty_demorgan"])
        "Unreviewed original producer mutation";
      let request = Realization_request.of_json (field "request" authority) in
      let proposals = array "proposals" value |> List.map S.Candidate.of_json |> Array.of_list in
      require (Array.length proposals = 2) "Incomplete original mutation proposal inventory";
      let count = ref 0 in
      let module Original_proposals = struct
        let propose ~config ~limits:_ ~parent actual_request =
          require (!count < 2 && Realization_request.fingerprint actual_request = Realization_request.fingerprint request)
            "Mutation proposer changed request or call count";
          let proposal = proposals.(!count) in incr count;
          require (S.Config.fingerprint config = S.Config.fingerprint (S.Candidate.generator_config proposal))
            "Mutation proposer changed configuration";
          Bioc_checker.Work_budget.charge parent (S.Candidate.canonical_size proposal);
          proposal
      end in
      let module Mutated_selection = P.Make (Original_proposals) in
      let result = Mutated_selection.select ?config:(optional S.Config.of_json (field "config" authority))
        ?until:(horizon authority) request (history authority) in
      require (!count = 2) "Both original mutated proposals must execute fresh acceptance";
      selection result
  | "checker_version_mutation" ->
      let api = text "api" value and version = text "checker_version" value in
      require (List.mem api ["realization_dependencies"; "check_realization"; "check_synthetic_candidate"]
        && List.mem version ["changed"; "changed.v999"]) "Unreviewed original checker-version mutation";
      let current, _ = prerequisite api (field "authority" value) in
      let dependencies result = if api = "realization_dependencies" then result else field "dependencies" result in
      let replace key replacement value = obj ((key, replacement) :: List.remove_assoc key (Json.object_fields value)) in
      let with_checker version result =
        let changed = replace "checker" (str version) (dependencies result) in
        if api = "realization_dependencies" then changed else replace "dependencies" changed result in
      require (text "checker" (dependencies current) = R.checker_version && version <> R.checker_version)
        "Current native checker identity differs";
      equal "Full current authority before original version mutation" current
        (with_checker R.checker_version (field "original_result" value));
      let mutated = with_checker version current in
      equal "Full original version mutant" mutated (field "original_result" value);
      require (E.Dependency_snapshot.changed (E.Dependency_snapshot.of_json (dependencies current))
        (E.Dependency_snapshot.of_json (dependencies mutated)) = ["checker"]) "Wrong checker-version invalidation";
      mutated, None
  | "check_realization" | "realization_dependencies" ->
      let behavior = Behavior.of_json (field "behavior" value) in
      let contract = C.Behavior_contract.of_json (field "contract" value) in
      let domain = C.Operating_domain.of_json (field "domain" value) in
      let target = Build_request.Target.of_json (field "target" value) in
      let mechanism = Mechanism.of_json (field "mechanism" value) in
      let observation_map = Observation_map.of_json (field "observation_map" value) in
      let history = history value and until = horizon value in
      if operation = "realization_dependencies" then
        R.dependencies ?until behavior contract domain target mechanism observation_map history
        |> E.Dependency_snapshot.to_json, None
      else R.check ?until behavior contract domain target mechanism observation_map history |> E.Check_result.to_json, None
  | "check_synthetic_candidate" | "check_component_assembly" | "check_component_behavior" ->
      let request = Realization_request.of_json (field "request" value) in
      let history = history value and until = horizon value in
      if operation = "check_component_behavior" then
        B.check ?until request (Component_assembly.of_json (field "assembly" value)) history |> E.Check_result.to_json, None
      else let candidate = S.Candidate.of_json (field "candidate" value) in
        if operation = "check_synthetic_candidate" then Y.check ?until request candidate history |> E.Check_result.to_json, None
        else A.check ?until request candidate (Component_assembly.of_json (field "assembly" value)) history
          |> Composition_evidence.Result.to_json, None
  | "SyntheticComponent" -> let value = S.Component.of_json value in
      S.Component.to_json value, props (S.Component.fingerprint value)
  | "SyntheticCatalog" -> let value = S.Catalog.of_json value in
      S.Catalog.to_json value, props (S.Catalog.fingerprint value)
  | "SyntheticGeneratorConfig" -> let value = S.Config.of_json value in
      S.Config.to_json value, props (S.Config.fingerprint value)
  | "SyntheticCandidate" -> let value = S.Candidate.of_json value in
      S.Candidate.to_json value, props (S.Candidate.fingerprint value)
  | "catalog_for_profile" -> let value = S.catalog_for_profile (text "profile" value) in
      S.Catalog.to_json value, props (S.Catalog.fingerprint value)
  | "SyntheticCatalog.for_operation" ->
      let catalog = S.Catalog.of_json (field "subject" value) in
      (match S.Catalog.for_operation catalog (text "operation" value) with
      | Some value -> S.Component.to_json value, props (S.Component.fingerprint value)
      | None -> Diagnostic.fail "synthetic_catalog_operation" "Synthetic catalog operation unavailable.")
  | "SyntheticCatalog.lock" ->
      let catalog = S.Catalog.of_json (field "subject" value) in
      let mechanism = Mechanism.of_json (field "mechanism" value) in
      Json.Array (S.Catalog.lock catalog mechanism |> List.map Component_registry.Component_lock.to_json), None
  | _ -> failwith ("Unimplemented synthetic producers corpus operation: " ^ operation)

module X = Verification_exploration
module V = Verification_workflow
module Engine = Bioc_realization_checker.Verification_exploration
module Workflow = Bioc_realization_checker.Synthetic_verification
let pin = "2f5e7636977f559e046776c1bb92bebf67c8f0e733ca463927f8d3a1aee3d77b"
let prior_pin = "2ed5860ac7143fe4a540c7b648eb5773c2fc52cd9bf43afd8913c3d99616566b"
let capture_pin = "5e7b74bd456a554dd3b1e3661f25ec42ff00a719b114d19cdd474d9c014b1015"
let maximum = 64 * 1024 * 1024
let parse text = Json.parse_bounded ~max_bytes:maximum ~max_nodes:1_000_000 text
let encode value = Canonical.encode_bounded ~max_bytes:maximum value
let fingerprint value = Canonical.sha256 (encode value)
let equal label left right = require (encode left = encode right) (label ^ ": complete content differs")
let get_opt key value = List.assoc_opt key (Json.object_fields value)
let replace key replacement value = obj ((key,replacement)::List.remove_assoc key (Json.object_fields value))
let schema value schema = replace "schema_version" (str schema) value
let number key value = Runtime_number.of_json (field key value)
let frames key value = X.frames_of_json (field key value)
let kind name = if name="BooleanInputConfig" || name="BooleanInputExplorationReport" then X.Bounds.Mixed else X.Bounds.Contact
let bounds value = X.Bounds.to_json value, Some (obj ["fingerprint",str (X.Bounds.fingerprint value);
  "state_count",Json.Int (X.Bounds.state_count value);"possible_histories",Json.Int (X.Bounds.possible_histories value)])
let report value =
  let raw = X.Report.to_json value in
  raw, Some (obj (("fingerprint",str (X.Report.fingerprint value)) :: List.map (fun key->key,field key raw)
    ["state_count";"possible_histories";"evaluated_histories";"complete";"all_passed";
     "outcome_counts";"coverage_totals";"shared_dependencies"]))
let signature value = X.Failure_signature.to_json value, props (X.Failure_signature.fingerprint value)
let reduction value = X.Reduction.to_json value, props (X.Reduction.fingerprint value)
let request value = V.Request.to_json value, props (V.Request.fingerprint value)
let record value = V.Record.to_json value, props (V.Record.fingerprint value)
let observation value = X.Observation.to_json value, props (X.Observation.fingerprint value)
let adversarial value = X.Adversarial_config.to_json value, props (X.Adversarial_config.fingerprint value)
let history_case value = X.History_case.to_json value, props (X.History_case.fingerprint value)
let domain name raw = match name with
  | "BooleanObservation" -> observation (X.Observation.of_json raw)
  | "BooleanContactConfig" -> bounds (X.Bounds.contact_of_json raw)
  | "BooleanInputConfig" -> bounds (X.Bounds.input_of_json raw)
  | "ExplorationReport" -> report (X.Report.contact_of_json raw)
  | "BooleanInputExplorationReport" -> report (X.Report.input_of_json raw)
  | "FailureSignature" -> signature (X.Failure_signature.of_json raw)
  | "ReductionResult" -> reduction (X.Reduction.of_json raw)
  | "AdversarialConfig" -> adversarial (X.Adversarial_config.of_json raw)
  | "HistoryCase" -> history_case (X.History_case.of_json raw)
  | "SyntheticVerificationRequest" -> request (V.Request.of_json raw)
  | "SyntheticVerificationRecord" -> record (V.Record.of_json raw)
  | _ -> failwith ("Unrepresented workflow record class: "^name)
let construct name value = match name with
  | "ExplorationReport" | "BooleanInputExplorationReport" ->
      report (X.Report.make ~kind:(kind name) ~config:(X.Bounds.of_json (field "config" value))
        ~results:(array "results" value |> List.map E.Check_result.of_json)
        ~explorer_version:(text "explorer_version" value) ~claim_scope:(text "claim_scope" value) ())
  | "ReductionResult" ->
      reduction (X.Reduction.make ~original_history:(frames "original_history" value) ~history:(frames "history" value)
        ~until:(number "until" value) ~signature:(X.Failure_signature.of_json (field "signature" value))
        ~original_result:(E.Check_result.of_json (field "original_result" value))
        ~result:(E.Check_result.of_json (field "result" value)) ~evaluations:(integer (field "evaluations" value))
        ~one_minimal:(Json.boolean (field "one_minimal" value)) ~reducer_version:(text "reducer_version" value) ())
  | "SyntheticVerificationRecord" ->
      record (V.Record.make ~request:(V.Request.of_json (field "request" value))
        ~result:(V.result_of_json (field "result" value)) ~workflow_version:(text "workflow_version" value)
        ~claim_scope:(text "claim_scope" value) ())
  | _ ->
      let version = match name with
        | "BooleanObservation" -> X.Observation.schema_version
        | "BooleanContactConfig" -> "biocompiler.boolean_contact_config.v0.1"
        | "BooleanInputConfig" -> "biocompiler.boolean_input_config.v0.1"
        | "FailureSignature" -> X.Failure_signature.schema_version
        | "AdversarialConfig" -> X.Adversarial_config.schema_version
        | "HistoryCase" -> X.History_case.schema_version
        | "SyntheticVerificationRequest" -> V.Request.schema_version
        | _ -> failwith ("Unknown workflow constructor: "^name) in
      domain name (schema value version)
let domain_operation api value = match String.split_on_char '.' api with
  | [name;"__init__"] -> construct name value
  | [name;"from_dict"] -> domain name (field "data" value)
  | [name;"from_json"] -> domain name (parse (text "text" value))
  | ["FailureSignature";"from_counterexample"] ->
      signature (X.Failure_signature.from_counterexample (E.Counterexample.of_json (field "item" value)))
  | ["FailureSignature";"from_diagnostic"] ->
      signature (X.Failure_signature.from_diagnostic (E.Check_diagnostic.of_json (field "item" value)))
  | ["FailureSignature";"matches"] ->
      Json.Bool (X.Failure_signature.matches (X.Failure_signature.of_json (field "self" value))
        (E.Check_result.of_json (field "result" value))),None
  | _ -> failwith ("Unknown workflow domain operation: "^api)

let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun ()->close_in_noerr channel) (fun ()->
    let bytes=in_channel_length channel in require (bytes<=maximum) "Workflow fixture exceeds 64 MiB";
    let payload=really_input_string channel bytes in
    let value=parse payload in require (encode value^"\n"=payload) "Noncanonical workflow fixture";
    value,bytes)
let hash value =
  require (String.length value=64 && String.for_all (function '0'..'9'|'a'..'f'->true|_->false) value)
    "Unsafe workflow fixture identity"; value
type documents = { values:(string,Json.t) Hashtbl.t }
let load_index path expected_pin docs =
  let index,initial=read path in
  require (text "inventory_fingerprint" index=expected_pin && fingerprint
    (obj (List.remove_assoc "inventory_fingerprint" (Json.object_fields index)))=expected_pin)
    "Complete conformance inventory changed";
  let directory=Filename.remove_extension path and total=ref initial in
  let descriptors=array "documents" index in
  let names=Hashtbl.create (List.length descriptors) in
  List.iter (fun descriptor->
    let id=hash (text "id" descriptor) in
    require (not (Hashtbl.mem names id)) "Duplicate fixture descriptor"; Hashtbl.add names id ();
    let value,bytes=read (Filename.concat directory (id^".json")) in
    require (bytes=integer (field "bytes" descriptor) && fingerprint value=id) "Complete fixture hash/bytes differ";
    require (bytes<=512*1024*1024- !total) "Workflow fixture inventory exceeds 512 MiB";
    total:= !total+bytes;
    (match Hashtbl.find_opt docs.values id with None->Hashtbl.add docs.values id value
    |Some previous->equal "Shared complete fixture" value previous)) descriptors;
  require ((Array.to_list (Sys.readdir directory) |> List.sort String.compare) =
    (List.map (fun descriptor->text "id" descriptor^".json") descriptors |> List.sort String.compare))
    "Missing or extra workflow fixture";
  index,!total
let use docs id = Hashtbl.find docs.values (hash id)
let referenced docs key value = use docs (text key value)
let increment table key = Hashtbl.replace table key (1+Option.value (Hashtbl.find_opt table key) ~default:0)
let expected_result docs call =
  let value=referenced docs "result" call in
  if text "result_format" call="python_json_text" then parse (Json.string value) else value
let compare_result docs label call (actual,properties) =
  equal (label^"/full-result") actual (expected_result docs call);
  match get_opt "properties" call,properties with
  |None,None->()
  |Some id,Some actual->equal (label^"/properties") actual (use docs (Json.string id))
  |_->failwith (label^": missing/extra complete derived properties")
let full_error call =
  let error=field "error" call in
  require (text "module" error="biocompiler.errors" && text "type" error="SerializationError")
    "Unreviewed workflow exception family";
  text "message" error
let workflow_code api message =
  match api,message with
  | "BooleanContactConfig.__init__","Contact IDs must be an array." -> "verification_exploration"
  | "BooleanContactConfig.__init__","Duplicate Boolean observation." -> "verification_exploration"
  | "BooleanContactConfig.__init__","Exploration needs one to sixteen variable times." -> "verification_exploration"
  | "BooleanContactConfig.__init__","Exploration text must be valid UTF-8." -> "verification_exploration"
  | "BooleanContactConfig.__init__","Exploration times must be finite nonnegative numbers." -> "verification_exploration"
  | "BooleanContactConfig.__init__","Invalid history evaluation cap." -> "verification_exploration"
  | "BooleanContactConfig.__init__","Snapshot contains contacts outside the Boolean bounds." -> "verification_exploration"
  | "BooleanContactConfig.__init__","Snapshot observations differ from the declared Boolean bounds." -> "verification_exploration"
  | "BooleanContactConfig.__init__","Variable lattice exceeds the horizon." -> "verification_exploration"
  | "BooleanContactConfig.__init__","Variable lattice must start at zero and strictly increase." -> "verification_exploration"
  | "BooleanContactConfig.from_dict","Contact IDs must be an array." -> "verification_exploration"
  | "BooleanContactConfig.from_dict","Exploration needs one to sixteen variable times." -> "verification_exploration"
  | "BooleanContactConfig.from_dict","Exploration records must be an array." -> "verification_exploration"
  | "BooleanContactConfig.from_dict","Exploration text must be valid UTF-8." -> "verification_exploration"
  | "BooleanContactConfig.from_dict","Invalid fields in InputFrame." -> "verification_exploration"
  | "BooleanContactConfig.from_json","Exploration text must be valid UTF-8." -> "verification_exploration"
  | "BooleanInputConfig.__init__","A signal cannot be both cell-local and contact-local." -> "verification_exploration"
  | "BooleanInputConfig.__init__","Duplicate Boolean cell observation." -> "verification_exploration"
  | "BooleanInputConfig.__init__","Mixed bounds need an observation." -> "verification_exploration"
  | "BooleanInputConfig.__init__","Snapshots require the complete declared signal inventory." -> "verification_exploration"
  | "BooleanInputExplorationReport.from_dict","Inconsistent exploration complete." -> "verification_exploration"
  | "BooleanObservation.__init__","Exploration text must be valid UTF-8." -> "verification_exploration"
  | "ExplorationReport.__init__","Evaluator changed checked requirement inventory." -> "verification_exploration"
  | "ExplorationReport.from_dict","Inconsistent exploration complete." -> "verification_exploration"
  | "ReductionResult.__init__","Reduction changed checked requirement inventory." -> "verification_exploration"
  | "ReductionResult.__init__","Unsupported reduction policy version." -> "verification_exploration"
  | "ReductionResult.from_dict","Reduction changed checked requirement inventory." -> "verification_exploration"
  | "ReductionResult.from_dict","Unsupported reduction policy version." -> "verification_exploration"
  | "ReductionResult.from_json","Reduction changed checked requirement inventory." -> "verification_exploration"
  | "ReductionResult.from_json","Unsupported reduction policy version." -> "verification_exploration"
  | "SyntheticVerificationRecord.from_dict","Inconsistent exploration complete." -> "verification_exploration"
  | "SyntheticVerificationRecord.from_dict","Verification result schema must be text." -> "verification_workflow"
  | "SyntheticVerificationRequest.__init__","A check cannot contain unused reduction controls." -> "verification_workflow"
  | "SyntheticVerificationRequest.__init__","Exploration times must be finite nonnegative numbers." -> "verification_exploration"
  | "SyntheticVerificationRequest.__init__","History must start at time zero." -> "verification_exploration"
  | "SyntheticVerificationRequest.__init__","Unsupported verification mode." -> "verification_workflow"
  | "SyntheticVerificationRequest.__init__","Unsupported verification operation." -> "verification_workflow"
  | "SyntheticVerificationRequest.from_dict","A check cannot contain unused reduction controls." -> "verification_workflow"
  | "SyntheticVerificationRequest.from_dict","Exploration times must be finite nonnegative numbers." -> "verification_exploration"
  | "SyntheticVerificationRequest.from_dict","History must start at time zero." -> "verification_exploration"
  | "SyntheticVerificationRequest.from_dict","Invalid fields in SyntheticVerificationRequest." -> "verification_workflow"
  | "SyntheticVerificationRequest.from_dict","Unsupported verification mode." -> "verification_workflow"
  | "SyntheticVerificationRequest.from_dict","Unsupported verification operation." -> "verification_workflow"
  | "explore_boolean_histories","Evaluator changed checked requirement inventory." -> "verification_exploration"
  | "explore_boolean_histories","Evaluator changed model, request, contract, domain, target or tool dependencies." -> "verification_exploration"
  | "explore_boolean_histories","Evaluator changed the explicit finite horizon." -> "verification_exploration"
  | "explore_boolean_histories","Evaluator returned stale or unrelated history evidence." -> "verification_exploration"
  | "explore_boolean_histories","Exploration text must be valid UTF-8." -> "verification_exploration"
  | "explore_boolean_histories","History evaluator must return a CheckResult." -> "verification_exploration"
  | "reduce_counterexample","Evaluator changed model, request, contract, domain, target or tool dependencies." -> "verification_exploration"
  | "reduce_counterexample","Evaluator returned stale or unrelated history evidence." -> "verification_exploration"
  | "reduce_counterexample","Initial history does not exhibit the selected FAIL signature." -> "verification_exploration"
  | "replay_synthetic_verification","Fresh replay needs independently trusted complete operation authority." -> "synthetic_verification"
  | "replay_synthetic_verification","Verification evidence is stale, altered or unsupported by current tools." -> "synthetic_verification"
  | "replay_synthetic_verification","Verification operation differs from independent authority." -> "synthetic_verification"
  | "run_synthetic_verification","Initial history does not exhibit the selected FAIL signature." -> "verification_exploration"
  | _ -> failwith "Unreviewed complete workflow rejection counterpart"

let mutation_context = "tests/test_synthetic_verification_workflow.py::SyntheticVerificationWorkflowTests.test_forged_results_and_stale_tool_dependencies_fail_fresh_replay"
let mutate_checker version value =
  let result=field "result" value in
  replace "result" (replace "dependencies" (replace "checker" (str version) (field "dependencies" result)) result) value
let nominal_type docs call path =
  let path=Json.Array (List.map str path) in
  referenced docs "python_types" call |> Json.array
  |> List.find_opt (fun descriptor->field "path" descriptor=path)
  |> Option.map (text "type")
let kernel_operation docs rows call_number label call value callback_used =
  let api=text "api" call in
  let transcript=match get_opt "callback_calls" call with None->[||]|Some values->Json.array values |> List.map integer |> Array.of_list in
  let cursor=ref 0 in
  let evaluate ~parent ~until history =
    require (!cursor<Array.length transcript) (label^": extra native callback");
    let position=transcript.(!cursor) in
    require (position>call_number && position<Array.length rows) "Invalid callback reference";
    let expected=rows.(position) in
    require (text "api" expected="workflow.callback" && integer (field "callback_parent" expected)=call_number)
      "Callback is attached to another operation";
    let raw=referenced docs "input" expected |> Json.string |> parse in
    equal (label^"/callback-input")
      (obj ["args",Json.Array [X.history_json history];"kwargs",obj ["until",Runtime_number.to_json until]]) raw;
    incr cursor; increment callback_used (label^"/callback/"^string_of_int position);
    require (text "outcome" expected="returned") "New callback exception requires an exact reviewed native counterpart";
    let raw=try expected_result docs expected with Diagnostic.Error error when error.code="invalid_json" || error.code="invalid_utf8"->
      Diagnostic.fail "verification_exploration" "Exploration text must be valid UTF-8." in
    (match raw with
    | Json.Object fields when List.assoc_opt "schema_version" fields=Some(str E.Check_result.schema_version)->
        let limits=X.Codec.make_limits ~charge:(Bioc_checker.Work_budget.charge parent) () in
        X.check_of_json ~limits raw
    |_->Diagnostic.fail "verification_exploration" "History evaluator must return a CheckResult.") in
  Fun.protect ~finally:(fun ()->require (!cursor=Array.length transcript) (label^": unconsumed original callback")) (fun ()->
    match api with
    |"boolean_config_from_dict"->bounds (X.Bounds.of_json (field "data" value))
    |"explore_boolean_histories"->report (Engine.explore (X.Bounds.of_json (field "config" value)) ~evaluate)
    |"reduce_counterexample"->reduction (Engine.reduce ~history:(frames "history" value) ~until:(number "until" value)
        ~signature:(X.Failure_signature.of_json (field "signature" value))
        ~max_evaluations:(integer (field "max_evaluations" value)) ~evaluate ())
    |"generate_adversarial_histories"->
        Json.Array (Engine.generate_adversarial_histories (X.Adversarial_config.of_json (field "config" value))
          |> List.map X.History_case.to_json),None
    |"run_synthetic_verification"->
        let current=Workflow.run (V.Request.of_json (field "request" value)) in
        (match get_opt "policy_override" call with
        |None->record current
        |Some policy->
            require (label=mutation_context^"/api/135" && text "checker_version" policy="changed.v999")
              "Unreviewed original workflow checker mutation";
            equal "Complete current wholeworkflow counterpart" (V.Record.to_json current)
              (mutate_checker R.checker_version (expected_result docs call));
            record (V.Record.of_json (mutate_checker "changed.v999" (V.Record.to_json current))))
    |"replay_synthetic_verification"->
        if nominal_type docs call ["kwargs";"expected_request"] <>
           Some "biocompiler.compiler.verification_workflow.SyntheticVerificationRequest" then Diagnostic.fail "synthetic_verification"
          "Fresh replay needs independently trusted complete operation authority.";
        let expected_request=V.Request.of_json (field "expected_request" value) in
        let historical=V.Record.of_json (field "record" value) in
        (match get_opt "policy_override" call with
        |None->record (Workflow.replay ~expected_request historical)
        |Some policy->
            require (label=mutation_context^"/api/134" && text "checker_version" policy="changed.v999")
              "Unreviewed original workflow replay mutation";
            let current=Workflow.replay ~expected_request historical in
            equal "Complete current replay counterpart" (V.Record.to_json current) (field "record" value);
            let stale=V.Record.of_json (mutate_checker "changed.v999" (V.Record.to_json current)) in
            record (Workflow.replay ~expected_request stale))
    |_->failwith ("Unknown complete workflow kernel: "^api))

let generator docs call value =
  let config=X.Bounds.of_json (field "config" value) in
  let count=Z.to_int (Z.min (X.Bounds.possible_histories config) (Z.of_int (X.Bounds.max_histories config))) in
  let yields=array "yields" call in
  require (List.length yields<=count) "Extra original generator yield";
  List.iteri (fun index id->equal "Complete ordered native generator history"
    (X.history_json (X.Bounds.history_at config (Z.of_int index))) (use docs (Json.string id))) yields;
  match text "iterator_state" call with
  |"exhausted"->require (List.length yields=count && referenced docs "return_value" call=Json.Null)
      "Native generator terminal inventory differs"
  |"suspended"->require (List.length yields>0 && List.length yields<=count) "Invalid partial original consumption"
  |_->failwith "New generator close/send/throw requires complete reviewed continuation replay"

let legacy_check docs label call native =
  let operation=text "operation" native and stage=text "native_stage" native in
  let execute () =
    let raw=referenced docs "input" native |> Json.string |> parse in
    try prerequisite operation raw with
    | G.Unsupported error->Diagnostic.fail "synthetic_generator_unsupported" (G.format_error error) in
  match field "expected_code" native with
  |Json.String code->
      (match execute () with
      |_->failwith (label^": prior expected rejection was accepted")
      |exception Diagnostic.Error error->
          require (error.code=code) (label^": expected "^code^", got "^error.code^": "^error.message);
          if code="synthetic_generator_unsupported" then require
            (error.message=text "message" (field "error" call)) "Complete original source-bearing exception differs")
  |Json.Null->
      let actual=execute () in
      (match get_opt "counterpart" call with
      |None->compare_result docs label call actual
      |Some counterpart->
          require (stage="python_type_boundary" && text "outcome" counterpart="returned")
            "Unreviewed prior Python nominal boundary";
          equal (label^"/typed-counterpart") (fst actual) (referenced docs "result" counterpart))
  |_->failwith "Invalid prior native diagnostic expectation"
let supplemental_check docs label call native =
  let operation=text "operation" native in
  let execute () = try prerequisite operation (referenced docs "input" native) with
    G.Unsupported error->Diagnostic.fail "synthetic_generator_unsupported" (G.format_error error) in
  match field "expected_code" native with
  |Json.Null->compare_result docs label call (execute ())
  |Json.String code->
      (match execute () with _->failwith (label^": additional rejection disappeared")
      |exception Diagnostic.Error error->require (error.code=code) (label^": additional rejection code differs"))
  |_->failwith "Invalid additional prerequisite diagnostic"
let cli_evidence docs call =
  let raw=referenced docs "input" call |> Json.string |> parse in
  let args=match array "args" raw with [value]->Json.array value |> List.map Json.string
    |_->failwith "Original CLI invocation shape changed" in
  require (args<>[] && List.mem (List.hd args)
    ["synthetic-check";"synthetic-explore";"synthetic-reduce";"synthetic-replay";"inspect"])
    "Unclassified original CLI command";
  require (text "outcome" call="returned" && List.mem (integer (expected_result docs call)) [0;1;2])
    "Original CLI exit semantics changed";
  List.iter (fun key->ignore (referenced docs key call |> Json.string)) ["stdout";"stderr"];
  List.iter (fun key->
    List.iter (fun (path,record)->
      require (String.starts_with ~prefix:"/tmp/biocompiler-workflow-conformance-v1/" path)
        "Original CLI file escaped its fixture-owned namespace";
      let content=text "text" record in
      require (String.length content=integer (field "bytes" record) && Canonical.sha256 content=text "sha256" record)
        "Complete original CLI file bytes differ") (Json.object_fields (referenced docs key call)))
    ["files_before";"files_after"];
  Option.iter (fun mutation->
    require (text "operation" mutation="os.replace" && text "message" (field "error" mutation)="disk unavailable")
      "Unreviewed CLI publication mutation";
    equal "Failed original atomic publication preserved complete files"
      (referenced docs "files_before" call) (referenced docs "files_after" call)) (get_opt "publication_override" call)

let run path =
  require (not (Filename.is_relative path)) "Absolute complete workflow corpus path required";
  let docs={values=Hashtbl.create 18000} in
  let index,total=load_index path pin docs in
  require (total=188830976 && List.length (array "documents" index)=11522) "Workflow complete byte/document census changed";
  require (text "schema_version" index="biocompiler.realization_workflow_conformance.v1"
    && text "original_capture_fingerprint" index=capture_pin) "Wrong complete workflow capture";
  let prior,_=load_index (Filename.concat (Filename.dirname path) "synthetic-producers-v1.json") prior_pin docs in
  let previous=Hashtbl.create 381 in
  List.iter (fun context->
    let id=text "id" context in
    Hashtbl.add previous id (referenced docs "ledger" context |> array "observations" |> Array.of_list)) (array "contexts" prior);
  let coverage=field "coverage" index in
  List.iter (fun (key,count)->require (integer (field key coverage)=count) ("Wrong workflow census: "^key))
    ["original_methods",376;"contexts",385;"api_calls",69236;"subprocess_invocations",2;
     "preserved_prior_occurrences",47901;"unclassified_observations",0];
  equal "Both unchanged actual subprocesses" (field "subprocesses" index) (field "subprocesses" prior);
  let contexts=array "contexts" index |> Array.of_list and locations=array "source_locations" index |> Array.of_list in
  let old_locations=array "source_locations" prior |> Array.of_list in
  let stages=Hashtbl.create 8 and apis=Hashtbl.create 80 and outcomes=Hashtbl.create 3 in
  let callback_used=Hashtbl.create 1100 and identities=Hashtbl.create 70000 in
  let count=ref 0 and prior_count=ref 0 and native_new=ref 0 and generators=ref 0 and cli_count=ref 0 in
  let failures=ref [] and campaign=ref false in
  let checked label action = try action () with error->
    let detail=match error with Diagnostic.Error error->error.code^": "^error.message|_->Printexc.to_string error in
    failures:=(label^": "^detail):: !failures;
    Printf.eprintf "workflow corpus failure: %s: %s\n%!" label detail in
  Array.iteri (fun context_number context->
    let context_id=text "id" context in
    require (text "assertion_status" context="passed") "Original workflow assertion failed";
    let rows=referenced docs "ledger" context |> Json.array |> Array.of_list in
    require (Array.length rows=integer (field "api_calls" context)) "Incomplete original workflow context";
    let original_positions=Hashtbl.create 10000 and old_seen=ref 0 in
    Array.iteri (fun number call->
      let native=field "native" call in
      if text "stage" native="pinned_prerequisite" then (
        require (integer (field "occurrence" native)= !old_seen) "Prior native occurrence order changed";
        Hashtbl.add original_positions number !old_seen; incr old_seen)) rows;
    (match Hashtbl.find_opt previous context_id with
    |None->require (!old_seen=0) "Invented old context"
    |Some old->require (!old_seen=Array.length old) "Missing prior original occurrence");
    Array.iteri (fun number call->
      incr count; let label=context_id^"/api/"^string_of_int number in
      require (not (Hashtbl.mem identities (context_number,number))) "Repeated workflow occurrence";
      Hashtbl.add identities (context_number,number) ();
      let api=text "api" call and native=field "native" call in
      let stage=text "stage" native in increment stages stage; increment apis api; increment outcomes (text "outcome" call);
      let location=integer (field "source" call) in
      require (location>=0 && location<Array.length locations) "Missing original workflow callsite";
      ignore (referenced docs "input" call |> Json.string);
      ignore (referenced docs "python_types" call |> Json.array);
      (match field "parent_call" call with Json.Null->()|value->
        let parent=integer value in require (parent>=0 && parent<number) "Invalid workflow parent");
      checked label (fun ()->match stage with
      |"pinned_prerequisite"->
          incr prior_count;
          require (text "corpus" native="synthetic-producers-v1" && text "inventory_fingerprint" native=prior_pin)
            "Prior prerequisite pin changed";
          let position=integer (field "occurrence" native) in
          let old=(Hashtbl.find previous context_id).(position) in
          List.iter (fun key->require (get_opt key call=get_opt key old) ("Complete prior field differs: "^key))
            ["api";"input";"python_types";"outcome";"result";"result_format";"error";"properties"];
          equal "Original prior source" locations.(location) old_locations.(integer (field "source" old));
          let rec original_parent raw=match raw with
            |Json.Null->Json.Null
            |value->let position=integer value in match Hashtbl.find_opt original_positions position with
              |Some number->Json.int number|None->original_parent (field "parent_call" rows.(position)) in
          equal "Original nearest prior parent" (original_parent (field "parent_call" call)) (field "parent" old);
          legacy_check docs label old (field "native" old)
      |"additional_prerequisite"->supplemental_check docs label call native
      |"workflow_domain"|"workflow_kernel"->
          incr native_new;
          let execute ()=
            let raw=referenced docs "input" native |> Json.string |> parse in
            if api="enumerate_boolean_histories" then (
              incr generators; generator docs call raw; Json.Null,None)
            else if stage="workflow_domain" then domain_operation api raw
            else kernel_operation docs rows number label call raw callback_used in
          if text "outcome" call="raised" then (
            let message=full_error call in
            match execute () with _->failwith "Expected complete original workflow rejection was accepted"
            |exception Diagnostic.Error error->
                if message="Exploration text must be valid UTF-8." &&
                   List.mem error.code ["invalid_json";"invalid_utf8"] then
                  let prefix="tests/test_verification_exploration.py::BooleanExplorationTests.test_lone_unicode_surrogates_are_rejected_in_configs_and_results/api/" in
                  require (List.mem label (List.map (fun n->prefix^string_of_int n) [0;3;6;7]))
                    "Unreviewed Python/native UTF-8 boundary"
                else require (error.code=workflow_code api message && error.message=message)
                  ("Original rejection differs: expected "^workflow_code api message^": "^message^
                    "; got "^error.code^": "^error.message))
          else if text "outcome" call="iterator" then ignore (execute ())
          else (
            let actual=execute () in compare_result docs label call actual;
            if api="explore_boolean_histories" && String.starts_with ~prefix:"tests/test_verification_campaign.py::" context_id then (
              require (integer (field "evaluated_histories" (fst actual))=625 &&
                List.length (array "results" (fst actual))=625 &&
                List.length (array "callback_calls" call)=625) "Complete 625-case native campaign was narrowed";
              campaign:=true))
      |"test_only_callback_transcript"->
          require (api="workflow.callback") "Wrong callback observation";
          let parent=integer (field "callback_parent" call) in
          let key=context_id^"/api/"^string_of_int parent^"/callback/"^string_of_int number in
          require (Hashtbl.find_opt callback_used key=Some 1) "Original callback not independently consumed exactly once"
      |"original_cli_publication"->incr cli_count; cli_evidence docs call
      |_->failwith ("Unclassified complete workflow observation: "^stage))) rows) contexts;
  let order=referenced docs "capture_call_order" index |> Json.array in
  let ordered=Hashtbl.create 70000 in
  List.iter (fun value->match Json.array value with
    |[context;number]->let key=integer context,integer number in
      require (Hashtbl.mem identities key && not (Hashtbl.mem ordered key)) "Missing/repeated complete captured call order";
      Hashtbl.add ordered key ()
    |_->failwith "Invalid complete workflow call-order entry") order;
  require (Hashtbl.length ordered=69236 && !count=69236 && !prior_count=47901 &&
    !native_new=874 && !generators=24 && !cli_count=16 && !campaign && Hashtbl.length callback_used=1030)
    "Incomplete full native workflow campaign/callback/generator census";
  List.iter (fun (name,counts)->
    let expected=Json.object_fields (field name coverage) in
    require (List.length expected=Hashtbl.length counts) "Unexpected native workflow family";
    List.iter (fun (key,value)->require (Hashtbl.find_opt counts key=Some(integer value))
      ("Complete native workflow census differs: "^key)) expected)
    ["native_stages",stages;"api_census",apis;"api_outcomes",outcomes];
  require (!failures=[]) (Printf.sprintf "%d complete workflow observations failed" (List.length !failures));
  Printf.printf "workflow corpus: 376 original methods / 385 contexts / 69,236 observations; all 874 new domain/kernel observations, 1,030 callbacks and the complete 625-case campaign replayed; original CLI evidence retained, installed CLI routing remains a separate gate\n%!"
let () =
  if Array.length Sys.argv<>2 then failwith "One absolute complete workflow corpus path is mandatory";
  run Sys.argv.(1)
