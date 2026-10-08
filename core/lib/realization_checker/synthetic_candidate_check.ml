open Bioc_wire
open Bioc_domain
module B = Realization_budget
module W = Bioc_checker.Work_budget
module Q = Checked_request
module S = Synthetic_authority
module C = S.Candidate
module E = Realization_evidence
module P = Synthetic_provenance
module R = Realization_check
module Names = Set.Make (String)
module By_name = Map.Make (String)
let checker_version = S.checker_version
let implementation_version = "biocompiler.ocaml.synthetic_candidate_checker.v0.1"
type limits = { common : B.limits; realization : R.limits }
let make_limits ?max_work ?max_monitor_items ?max_request_bytes ?max_report_bytes ?max_report_nodes () =
  {common=B.make_limits ?max_work ?max_monitor_items ?max_request_bytes ?max_report_bytes ?max_report_nodes ();
   realization=R.make_limits ?max_work ?max_monitor_items ?max_request_bytes ?max_report_bytes ?max_report_nodes ()}
let default_limits = make_limits ()
let limits_json limits = Json.Object ["profile", Json.String "biocompiler.synthetic_candidate_checker.resources.v1";
  "shared", B.limits_json limits.common; "realization", R.limits_json limits.realization]
type usage = { work_charged : int }
let str value = Json.String value
let field key value = Json.field key (Json.object_fields value)
(* Python mapping unpack/update preserves existing positions and appends new
   settings. This local recipe does not reorder unrelated imported mappings. *)
let replace key value raw =
  let fields = Json.object_fields raw in
  Json.Object (if List.mem_assoc key fields then
    List.map (fun (name,previous) -> name,(if name=key then value else previous)) fields
    else fields @ [key,value])
let rec levels count = if count <= 1 then 1 else 1 + levels (count / 2)
let charge_string budget multiplier value = B.charge budget (multiplier * (String.length value + 1))
let names budget values =
  let count = List.length values in
  B.retain_monitor budget count;
  let multiplier = 1 + levels count in
  List.fold_left (fun result value -> charge_string budget multiplier value; Names.add value result) Names.empty values
let same_map budget left right =
  let ordered values =
    let count = List.length values in
    B.retain_monitor budget count;
    let multiplier = 1 + levels count in
    List.fold_left (fun result (key, items) ->
      charge_string budget multiplier key;
      List.iter (charge_string budget 2) items;
      By_name.add key items result) By_name.empty values in
  let left = ordered left and right = ordered right in
  By_name.equal ( = ) left right
let source_json (source : Behavior.source_location) = Json.Object [
  "file", str source.file; "line", Json.Int source.line; "function", str source.function_name]
let check_with_usage ?until ?(limits=default_limits) ?parent request candidate history =
  let budget = B.create ?parent ~limits:limits.common () in
  let work = B.work budget and request_json = Realization_request.to_json request in
  let initial = W.remaining work in
  B.reserve_request budget (Json.Object ["request", Json.Null; "candidate", Json.Null;
      "history", Json.Array []; "until", (match until with None -> Json.Null | Some value -> Runtime_number.to_json value)]);
  B.reserve_request budget request_json;
  B.reserve_request budget (C.to_json candidate);
  let history = B.bounded_list budget history in
  List.iter (fun frame -> B.reserve_request budget (Execution_data.Input_frame.to_json frame)) history;
  let request = Q.check ~parent:work request in
  let raw_request = Q.request request in
  let behavior = Realization_request.behavior raw_request
  and contract = Realization_request.contract raw_request
  and domain = Realization_request.domain raw_request
  and target = Q.target request in
  let configuration = C.generator_config candidate in
  let catalog = S.catalog_for_profile (S.Config.profile_version configuration) in
  (* Preserve the original precedence: full history and horizon dependency
     construction precedes request identity and every semantic rejection. *)
  let base = R.dependencies ?until ~limits:limits.realization ~parent:work
      behavior contract domain target (C.mechanism candidate) (C.observation_map candidate) history in
  let raw_dependencies = E.Dependency_snapshot.to_json base in
  let settings = List.fold_left (fun result (key, value) -> replace key (str value) result)
      (field "settings" raw_dependencies)
      ["synthetic_acceptance", checker_version;
       "synthetic_profile", S.Config.profile_version configuration;
       "synthetic_candidate", C.fingerprint candidate;
       "realization_request", Q.fingerprint request;
       "generator_configuration", S.Config.fingerprint configuration;
       "catalog", S.Catalog.fingerprint catalog;
       "required_coverage", "active_and_inactive_deadlines_for_every_response"] in
  let raw_dependencies = replace "settings" settings raw_dependencies in
  B.reserve_report budget raw_dependencies;
  let requirements = Realization_contract.Behavior_contract.requirements contract in
  B.retain_monitor budget (List.length requirements);
  let checked_ids = List.map (fun response ->
      let id = Realization_contract.Response.id response in charge_string budget 1 id; str id) requirements in
  let publish raw = B.reserve_report budget raw; E.Check_result.of_json raw in
  let failure ?node_id ?source outcome code message =
    let diagnostic = Json.Object ["code", str code; "message", str message;
      "requirement_id", Json.Null; "node_id", (match node_id with None -> Json.Null | Some value -> str value);
      "source", (match source with None -> Json.Null | Some value -> source_json value)] in
    let raw = Json.Object ["schema_version", str E.Check_result.schema_version;
      "outcome", str outcome; "dependencies", raw_dependencies;
      "checked_requirement_ids", Json.Array checked_ids;
      "diagnostics", Json.Array [diagnostic]; "counterexamples", Json.Array [];
      "evidence_kind", str "model_conditional"; "claim_scope", str E.claim_scope;
      "coverage", Json.Array []] in
    publish raw in
  let lineage () =
    B.retain_monitor budget (List.length (Behavior.nodes behavior) + List.length (Behavior.requirements behavior));
    let nodes = List.map (fun node -> Identity.Node.to_string (Behavior.node_id node)) (Behavior.nodes behavior)
    and requirements = List.map (fun value -> Identity.Requirement.to_string (Behavior.requirement_id value))
      (Behavior.requirements behavior) in
    let known_nodes = names budget nodes and known_requirements = names budget requirements in
    let node_levels = 1 + levels (List.length nodes)
    and requirement_levels = 1 + levels (List.length requirements) in
    let requirements_map = C.behavior_requirement_ids candidate in
    let mapping_count = List.length requirements_map in
    B.retain_monitor budget mapping_count;
    let mapping = List.fold_left (fun result (key, values) ->
        charge_string budget (1 + levels mapping_count) key;
        By_name.add key values result) By_name.empty requirements_map in
    let known = List.for_all (fun (key, values) ->
        charge_string budget (1 + levels mapping_count) key;
        let requirements = By_name.find key mapping in
        List.for_all (fun value -> charge_string budget node_levels value;
            Names.mem value known_nodes) values &&
        List.for_all (fun value -> charge_string budget requirement_levels value;
            Names.mem value known_requirements) requirements) (C.source_map candidate) in
    if not known then Some (failure "fail" "candidate_lineage"
      "The candidate refers to unknown Behavior sources or requirements.") else (
    B.retain_monitor budget (List.length requirements);
    let carried = List.fold_left (fun result (_, values) -> List.fold_left (fun result value ->
        charge_string budget requirement_levels value;
        Names.add value result) result values) Names.empty (C.behavior_requirement_ids candidate) in
    List.iter (charge_string budget 2) requirements;
    if not (Names.equal carried known_requirements) then Some (failure "fail" "candidate_lineage"
      "The candidate does not retain every Behavior requirement.") else None) in
  let actual_execution () = match lineage () with Some result -> result | None ->
    let result = R.check ?until ~limits:limits.realization ~parent:work behavior contract domain target
        (C.mechanism candidate) (C.observation_map candidate) history in
    publish (replace "dependencies" raw_dependencies (E.Check_result.to_json result)) in
  let component_locks () =
    let nodes = Mechanism.nodes (C.mechanism candidate) in
    B.retain_monitor budget (List.length nodes);
    B.charge budget (C.canonical_size candidate);
    let lock_size = List.fold_left (fun size lock -> size + String.length
      (Canonical.encode (Component_registry.Component_lock.to_json lock))) 0 (C.component_locks candidate) in
    (* Includes sorted node IDs, fixed catalog lookup and complete lock encoding.
       All input declarations have already passed the aggregate request bound. *)
    B.charge budget ((lock_size + List.length nodes + 1) * (3 + levels (List.length nodes)));
    let expected = try Some (S.Catalog.lock catalog (C.mechanism candidate)) with
      | Diagnostic.Error error when error.code = "synthetic_catalog_operation" -> None in
    match expected with
    | None -> failure "fail" "candidate_component"
        "The candidate contains an operation outside its pinned synthetic catalog."
    | Some expected ->
        let json locks = Json.Array (List.map Component_registry.Component_lock.to_json locks) in
        if not (Json.equal (json (C.component_locks candidate)) (json expected)) then
          failure "fail" "candidate_component" "The candidate's component versions or content identities are stale."
        else actual_execution () in
  let provenance policy =
    let violations = P.violations ~budget policy (C.mechanism candidate) in
    if violations <> [] then failure "fail" "candidate_hard_constraints" (String.concat "; " violations) else
    match (try Ok (P.derive ~budget request configuration) with P.Unsupported error -> Error error) with
    | Error error -> failure ?node_id:error.node_id ?source:error.source "unsupported"
        "unsupported_generation_profile" (P.format_error error)
    | Ok expected ->
        if not (same_map budget (C.source_map candidate) (P.source_map expected) &&
                same_map budget (C.behavior_requirement_ids candidate) (P.behavior_requirement_ids expected)) then
          failure "fail" "candidate_lineage"
            "Source correspondence or requirement lineage differs from the declared generation profile."
        else component_locks () in
  let result = if C.request_fingerprint candidate <> Q.fingerprint request then
      failure "fail" "candidate_request_identity" "The candidate belongs to a different frozen realization request."
    else match (try Ok (P.parse_policy ~budget request ~profile:(S.Config.profile_version configuration))
                with P.Unsupported error -> Error error) with
    | Error error -> failure "unsupported" "unsupported_selection_policy" (P.format_error error)
    | Ok policy -> provenance policy in
  result, {work_charged=initial - W.remaining work}
let check ?until ?limits ?parent request candidate history =
  fst (check_with_usage ?until ?limits ?parent request candidate history)
