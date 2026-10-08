open Bioc_wire
module X = Bioc_domain.Verification_exploration
module V = Bioc_domain.Verification_workflow
module R = Bioc_domain.Realization_request
module C = Bioc_domain.Synthetic_authority.Candidate
module E = Bioc_domain.Realization_evidence
module W = Bioc_checker.Work_budget
module B = Verification_workflow_budget
let implementation_version = "biocompiler.ocaml.synthetic_verification.v0.1"
let resource_profile = B.resource_profile
type limits = B.limits
let make_limits = B.make_limits
let default_limits = B.default_limits
let limits_json limits =
  let budget = B.create ~limits () in
  Json.Object ["workflow",B.limits_json limits;
    "artifacts",X.Codec.limits_json (B.report_codec budget);
    "realization",Realization_check.limits_json (B.realization_limits budget);
    "synthetic",Synthetic_candidate_check.limits_json (B.synthetic_limits budget)]
type usage = B.usage
let require condition message = Diagnostic.require condition "synthetic_verification" message
let decode_request_in ~budget ?(path="") raw =
  B.with_workspace budget (fun () -> V.Request.decode_with_realization ~limits:(B.input_codec budget) ~path
    ~decode_realization:(fun ~path raw ->
      X.Codec.preflight ~limits:(B.input_codec budget) ~path raw;
      let request = R.of_json ~path raw in
      Checked_request.request (Checked_request.check ~parent:(B.work budget) request)) raw)
let decode_record_in ~budget ?(path="") raw =
  B.with_workspace budget (fun () -> V.Record.decode_with_request ~limits:(B.input_codec budget) ~path
    ~decode_request:(fun ~path raw -> decode_request_in ~budget ~path raw) raw)
let option label = function Some value -> value | None -> Diagnostic.fail "synthetic_verification" label
let replace key value fields =
  if List.mem_assoc key fields then
    List.map (fun (name,previous) -> name,(if name=key then value else previous)) fields
  else fields @ [key,value]
let checker budget request checked ~parent ~until history =
  let realization = V.Request.realization request and candidate = V.Request.candidate request in
  let result = match V.Request.mode request with
    | V.Candidate -> Synthetic_candidate_check.check ~until ~limits:(B.synthetic_limits budget) ~parent realization candidate history
    | V.Model -> Realization_check.check ~until ~limits:(B.realization_limits budget) ~parent
        (R.behavior realization) (R.contract realization) (R.domain realization) (Checked_request.target checked)
        (C.mechanism candidate) (C.observation_map candidate) history in
  (* Cached complete leaf volume bounds the transformations before allocating the
     dependency replacement or invoking the legacy ASCII leaf constructor. *)
  B.with_workspace budget (fun () ->
  let parent = B.work budget in
  W.charge parent (8 * E.Check_result.canonical_size result + 4096);
  let limits = B.report_codec budget in
  let dependencies = Json.object_fields (E.Dependency_snapshot.to_json (E.Check_result.dependencies result)) in
  let settings = Json.object_fields (Json.field "settings" dependencies) in
  let additions = ["verification_workflow",Json.String V.workflow_version;
    "verification_mode",Json.String (match V.Request.mode request with V.Candidate->"candidate"|V.Model->"model");
    "verification_candidate",Json.String (C.fingerprint candidate);
    "verification_realization",Json.String (R.artifact_fingerprint realization)] in
  let settings = List.fold_left (fun fields (key,value) -> replace key value fields) settings additions in
  let dependencies = Json.Object (replace "settings" (Json.Object settings) dependencies) in
  let dependency_size = X.Codec.measure ~limits dependencies in
  (* The fixed native dependency envelope has <=20 settings, <=128 nodes and
     <8192 bytes. Cover entry, horizon and packing measurements before import. *)
  W.charge parent (3 * (X.Codec.work_bounds dependency_size).measure);
  let typed_dependencies = E.Dependency_snapshot.of_json dependencies in
  let raw = Json.Object (replace "dependencies" dependencies
      (Json.object_fields (E.Check_result.to_json result))) in
  let size = X.Codec.measure ~limits raw in
  W.charge parent (X.Codec.work_bounds size).measure;
  E.Check_result.with_dependencies result typed_dependencies)
let run_in ~budget request =
  B.charge budget (V.Request.canonical_size request);
  let checked = Checked_request.check ~parent:(B.work budget) (V.Request.realization request) in
  let evaluate = checker budget request checked in
  let result = match V.Request.operation request with
    | V.Check ->
        let until = option "Check operation needs an explicit finite horizon." (V.Request.until request) in
        let parent = B.evaluation budget in
        let result = B.with_retained budget (2 * Limits.max_json_nodes) (fun () -> evaluate ~parent ~until (V.Request.history request)) in
        B.charge budget (E.Check_result.canonical_size result);
        B.with_workspace budget (fun () -> X.validate_result ~limits:(B.report_codec budget) result (V.Request.history request) until);
        V.Checked result
    | V.Explore -> V.Explored (Verification_exploration.explore_in ~budget
        (option "Exploration needs explicit Boolean bounds." (V.Request.bounds request)) ~evaluate)
    | V.Reduce -> V.Reduced (Verification_exploration.reduce_in ~budget ~history:(V.Request.history request)
        ~until:(option "Reduction needs an explicit finite horizon." (V.Request.until request))
        ~signature:(option "Reduction needs an explicit selected failure." (V.Request.signature request))
        ~max_evaluations:(option "Invalid reduction evaluation budget." (V.Request.max_evaluations request)) ~evaluate) in
  let record = B.with_workspace budget (fun () -> V.Record.make ~limits:(B.report_codec budget) ~request ~result ()) in
  B.publish budget (V.Record.to_json record); record
let replay_in ~budget ?raw_record ~expected_request record =
  B.charge budget (V.Request.canonical_size expected_request + V.Record.canonical_size record);
  require (V.Request.fingerprint (V.Record.request record) = V.Request.fingerprint expected_request)
    "Verification operation differs from independent authority.";
  let rebuilt = run_in ~budget expected_request in
  require (V.Record.fingerprint rebuilt = V.Record.fingerprint record)
    "Verification evidence is stale, altered or unsupported by current tools.";
  Option.iter (fun raw ->
    require (B.equal_json budget raw (V.Record.to_json rebuilt))
      "Verification evidence is stale, altered or unsupported by current tools.") raw_record;
  rebuilt
let run_with_usage ?limits ?parent request =
  let budget = B.create ?limits ?parent () in
  B.reserve_request budget (V.Request.to_json request);
  let result = run_in ~budget request in result,B.usage budget
let run ?limits ?parent request = fst (run_with_usage ?limits ?parent request)
let replay_with_usage ?limits ?parent ~expected_request record =
  let budget = B.create ?limits ?parent () in
  B.reserve_request budget (V.Request.to_json expected_request);
  B.reserve_request budget (V.Record.to_json record);
  let result = replay_in ~budget ~expected_request record in result,B.usage budget
let replay ?limits ?parent ~expected_request record =
  fst (replay_with_usage ?limits ?parent ~expected_request record)
