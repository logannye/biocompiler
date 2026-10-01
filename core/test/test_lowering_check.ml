open Bioc_wire
module Domain = Bioc_domain
module Check = Bioc_checker.Lowering_check

let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let strings value = arr (List.map str value)
let field key value = Json.field key (Json.object_fields value)
let set key value document = obj ((key, value) :: List.remove_assoc key (Json.object_fields document))
let get_path document path = List.fold_left (fun document key -> field key document) document path
let duration = Json.parse {|{"kind":"scalar","name":"Duration","dimensions":{"time":1},"arguments":[]}|}
let scalar value = obj ["kind", str "scalar"; "value", value; "canonical_value", value;
                        "unit", str "s"; "type", duration]
let location = obj ["file", str "literal/source.py"; "line", Json.int 7; "function", str "author"]
let node ?(inputs = []) ?(attributes = []) ?(dtype = Json.Null) ?(role = Json.Null) id kind =
  obj ["id", str id; "kind", str kind; "inputs", strings inputs; "attributes", obj attributes;
       "data_type", dtype; "role", role; "source", location]
let parameter ?(id = "parameter") value =
  node ~dtype:duration ~attributes:["name", str "dwell"; "bound", Json.Bool true; "default", value] id "parameter"
let source_program ?(name = "independent_source") ?(roots = []) nodes =
  obj ["schema_version", str "biocompiler.intent.v0.1"; "name", str name; "nodes", arr nodes; "roots", strings roots]
let metadata = Json.parse {|{"schema_version":"biocompiler.binding_metadata.v0.1","category":"user_selected","provenance":{},"allowed_variation":null}|}
let provenance = Json.parse {|{"schema_version":"biocompiler.elaboration_provenance.v0.1","source_identities":{},"dependency_identities":{},"external_inputs":{},"locations":{},"recorded_at":null}|}
let frozen_request ?(profile = Domain.Behavior.V0_1) ?(overrides = []) ?(defaults = [])
    ?(bindings = []) ?(constraints = []) ?(preferences = []) source =
  obj ["schema_version", str "biocompiler.build_request.v0.1"; "intent", source;
       "explicit_overrides", obj overrides; "resolved_defaults", obj defaults; "resolved_bindings", obj bindings;
       "target", Json.Null; "artifact_scope", str "abstract_behavior";
       "behavior_profile", str (Domain.Behavior.schema_version profile);
       "implementation_constraints", obj constraints; "preferences", obj preferences;
       "parameter_metadata", obj (List.map (fun (name, _) -> name, metadata) bindings); "provenance", provenance]
let behavior ?(profile = Domain.Behavior.V0_1) ?(step = Json.Null) ?(bindings = [])
    ?(requirements = []) ?(links = []) source nodes =
  let nodes = List.map (fun node ->
      let attributes = Json.object_fields node in
      let node = set "contact_bound" (Json.Bool false) node in
      if List.mem_assoc "requirement_ids" attributes then node else set "requirement_ids" (arr []) node) nodes in
  obj ["schema_version", str (Domain.Behavior.schema_version profile); "name", field "name" source;
       "nodes", arr nodes; "roots", field "roots" source;
       "source_fingerprint", str (Domain.Intent.fingerprint (Domain.Intent.of_json source));
       "requirements", arr requirements; "source_links", obj links;
       "policies", Domain.Behavior.execution_policies ~integral_step:step profile; "parameter_bindings", obj bindings]
let parameter_pair ?(override = false) value =
  let source = source_program ~roots:["parameter"] [parameter (scalar (Json.int 2))] in
  let binding = ["dwell", value] in
  let request = if override then frozen_request ~overrides:binding ~bindings:binding source
    else frozen_request ~defaults:binding ~bindings:binding source in
  request, behavior ~bindings:binding ~links:["parameter", strings ["parameter"]] source [parameter value]
let change_node identity transform document =
  set "nodes" (arr (List.map (fun node -> if field "id" node = str identity then transform node else node)
                     (Json.array (field "nodes" document)))) document
let change_attributes identity transform document =
  change_node identity (fun node -> set "attributes" (transform (field "attributes" node)) node) document

let accepted request candidate =
  Check.check ~expected_request:(Domain.Build_request.of_json request) ~behavior:(Domain.Behavior.of_json candidate)
let rejection_count = ref 0
let rejected request candidate expected_code =
  (* Import outside the assertion: malformed domain documents are not evidence
     that the independent source-correspondence checker detects a discrepancy. *)
  let expected_request = Domain.Build_request.of_json request in
  let behavior = Domain.Behavior.of_json candidate in
  match Check.check ~expected_request ~behavior with
  | _ -> failwith ("Accepted invalid lowering; expected " ^ expected_code)
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code = expected_code)
        ("Wrong lowering rejection: " ^ diagnostic.code ^ ", expected " ^ expected_code);
      incr rejection_count
let baseline_obligations = ["source_behavior_execution"; "molecular_realization"; "source_to_candidate_preservation";
                            "candidate_acceptance"; "empirical_component_function"; "human_therapeutic_admission"]
let expected_properties request =
  ["execution_profile"; "source_identity"; "complete_graph"; "parameter_inventory"; "authoritative_bindings"]
  @ (Json.array (get_path request ["intent"; "nodes"]) |> List.concat_map (fun node ->
      let identity = Json.string (field "id" node) in
      ["operation:" ^ identity; "semantics:" ^ identity; "source:" ^ identity]))
  @ ["requirements_and_lineage"; "identity_binding"]
let check_report request candidate report =
  let json = Check.to_json report in
  require (Check.passed report && field "passed" json = Json.Bool true) "Lowering report did not pass";
  List.iter (fun (key, value) -> require (field key json = str value) ("Wrong report " ^ key))
    ["schema_version", "biocompiler.lowering_verification.v0.1";
     "checker_version", "biocompiler.ocaml.lowering_check.v0.1";
     "validation_scope", "source-to-behavior-correspondence-v1";
     "claim_scope", "Exact frozen source-to-Behavior correspondence only; no source execution, molecular realization, empirical component function, human therapeutic admission, or complete architecture acceptance."];
  require (List.map Check.property (Check.checks report) = expected_properties request) "Missing or reordered preservation checks";
  require (List.for_all (fun check -> Check.detail check <> "") (Check.checks report)) "Empty preservation detail";
  let authority = Domain.Build_request.of_json request in
  let lowered = Domain.Behavior.of_json candidate in
  List.iter (fun (key, value) -> require (field key json = str value) ("Wrong report identity " ^ key))
    ["request_fingerprint", Domain.Build_request.fingerprint authority;
     "request_artifact_fingerprint", Domain.Build_request.artifact_fingerprint authority;
     "source_fingerprint", Domain.Intent.fingerprint (Domain.Build_request.intent authority);
     "behavior_fingerprint", Domain.Behavior.fingerprint lowered;
     "behavior_artifact_fingerprint", Canonical.fingerprint (Domain.Behavior.to_json lowered)];
  require (field "behavior_profile" json = field "schema_version" candidate) "Lost behavior profile";
  require (List.for_all (fun obligation -> List.mem obligation (Check.unimplemented_obligations report))
             baseline_obligations) "Overclaimed lowering acceptance";
  json

let unit_tests () =
  let request, candidate = parameter_pair (scalar (Json.int 2)) in
  let report = accepted request candidate in
  let original = check_report request candidate report in
  require (Check.unimplemented_obligations report = baseline_obligations) "Unexpected baseline obligations";
  let overridden_request, overridden_candidate = parameter_pair ~override:true (scalar (Json.int 3)) in
  ignore (check_report overridden_request overridden_candidate (accepted overridden_request overridden_candidate));
  rejected request overridden_candidate "lowering_authoritative_bindings";
  let _, float_candidate = parameter_pair ~override:true (scalar (Json.Float 2.0)) in
  rejected request float_candidate "lowering_authoritative_bindings";
  let renamed_id = "α:renamed-parameter" in
  let renamed_source = source_program ~name:"renamed_source" ~roots:[renamed_id]
      [parameter ~id:renamed_id (scalar (Json.int 2))] in
  let renamed_request = set "intent" renamed_source request in
  let renamed_candidate = behavior ~bindings:["dwell", scalar (Json.int 2)]
      ~links:[renamed_id, strings [renamed_id]] renamed_source [parameter ~id:renamed_id (scalar (Json.int 2))] in
  ignore (check_report renamed_request renamed_candidate (accepted renamed_request renamed_candidate));
  rejected request (set "name" (str "forged_name") candidate) "lowering_source_identity";
  let relocation = set "file" (str "relocated/source.py") location in
  let relocated_candidate = change_node "parameter" (set "source" relocation) candidate in
  rejected request relocated_candidate "lowering_source_location";
  let relocated_source = change_node "parameter" (set "source" relocation) (field "intent" request) in
  let relocated_request = set "intent" relocated_source request in
  let relocated = check_report relocated_request relocated_candidate (accepted relocated_request relocated_candidate) in
  List.iter (fun key -> require (field key original = field key relocated) ("Source relocation changed " ^ key))
    ["request_fingerprint"; "source_fingerprint"; "behavior_fingerprint"];
  List.iter (fun key -> require (field key original <> field key relocated) ("Source relocation lost artifact identity " ^ key))
    ["request_artifact_fingerprint"; "behavior_artifact_fingerprint"];
  let future_source = set "nodes" (arr [parameter (scalar (Json.int 2)); node "future" "future.operation"])
      (field "intent" request) in
  rejected (set "intent" future_source request) candidate "unsupported_lowering_operation";
  let empty = source_program [] in
  let sampled_request = frozen_request ~profile:Domain.Behavior.V0_2
      ~constraints:["execution", obj ["integral_step", scalar (Json.int 1)]] empty in
  let sampled_candidate = behavior ~profile:Domain.Behavior.V0_2 ~step:(scalar (Json.Float 1.0)) empty [] in
  ignore (check_report sampled_request sampled_candidate (accepted sampled_request sampled_candidate));
  rejected sampled_request (behavior ~profile:Domain.Behavior.V0_2 ~step:(scalar (Json.int 2)) empty [])
    "lowering_execution_profile";
  rejected (set "implementation_constraints" (obj ["execution", obj ["future", Json.Bool true]]) sampled_request)
    sampled_candidate "invalid_lowering_execution_policy";
  let unresolved = request |> set "implementation_constraints" (obj ["provider", str "unresolved"])
      |> set "preferences" (obj ["choice", str "unresolved"]) in
  require (Check.unimplemented_obligations (accepted unresolved candidate)
           = baseline_obligations @ ["implementation_constraint_enforcement"; "preference_evaluation"])
    "Dropped retained source obligations";
  let cell = node "cell" "role" ~attributes:["name", str "cell"; "cell_type", str "human_T_cell";
                                             "engineering", str "in_vivo"] in
  let phase = node "phase" "state" ~inputs:["cell"] ~role:(str "cell")
      ~attributes:["name", str "phase"; "values", arr [Json.Bool false]; "initial", Json.Bool false;
                   "observation", str "prior_state"; "arbitration", str "unspecified"] in
  let state_source = source_program ~roots:["cell"; "phase"] [cell; phase] in
  let state_request = frozen_request state_source in
  let phase = change_attributes "phase"
      (fun attrs -> attrs |> set "observation" (str "shared_pre_update_state")
                   |> set "arbitration" (str "coalesce_identical_else_error")) state_source
      |> field "nodes" |> Json.array |> List.rev |> List.hd in
  let requirement = obj ["id", str "requirement:phase"; "kind", str "state"; "source_node_id", str "phase";
                         "lineage", strings ["cell"; "phase"]; "source", location] in
  let state_candidate = behavior ~requirements:[requirement]
      ~links:["cell", strings ["cell"]; "phase", strings ["cell"; "phase"]] state_source
      (List.map (set "requirement_ids" (strings ["requirement:phase"])) [cell; phase]) in
  ignore (check_report state_request state_candidate (accepted state_request state_candidate));
  rejected state_request (change_attributes "phase"
      (fun attrs -> attrs |> set "values" (arr [Json.int 0]) |> set "initial" (Json.int 0)) state_candidate)
    "lowering_semantics";
  rejected (set "intent" (change_attributes "phase" (set "observation" (str "shared_pre_update_state")) state_source)
              state_request) state_candidate "unsupported_lowering_state_policy";
  (* Direct typed API can receive larger documents than a wire request. Reject
     before building a report census, even when all nodes are locally valid. *)
  let count = (((Limits.max_json_nodes - 256) / 4) - 7) / 3 + 1 in
  let large_source = source_program (List.init count (fun index ->
      node ("value:" ^ string_of_int index) "literal" ~dtype:duration
        ~attributes:["value", scalar (Json.int 1)])) in
  rejected (frozen_request large_source) candidate "lowering_report_limit";
  Printf.printf "lowering literal checks: defaults/overrides, numeric distinctions, source ownership, alpha renaming, and %d intended rejections passed\n"
    !rejection_count

let read_json path =
  require (not (Filename.is_relative path)) "Fixture path must be absolute";
  let channel = open_in_bin path in
  let content = Fun.protect ~finally:(fun () -> close_in channel)
      (fun () ->
        let length = in_channel_length channel in
        require (length <= Limits.max_request_bytes) "Retained fixture exceeds the request byte budget";
        really_input_string channel length) in
  Json.parse content
let case_b_tests directory =
  let oracle = read_json (Filename.concat directory "current-baseline-oracle.json") in
  require (field "acceptance_authority" oracle = Json.Bool false) "Python oracle cannot grant acceptance";
  List.iter (fun variant ->
      let request = read_json (Filename.concat directory (variant ^ "/request.json"))
          |> fun value -> get_path value ["circuit"; "profile"; "source_request"] in
      let candidate = read_json (Filename.concat directory (variant ^ "/candidate.json"))
          |> fun value -> get_path value ["execution"; "behavior"] in
      let report = check_report request candidate (accepted request candidate) in
      require (field "behavior_fingerprint" report = get_path oracle ["cases"; variant; "behavior_fingerprint"])
        (variant ^ ": retained Behavior identity changed"))
    ["base"; "parameter-default"; "parameter-override"];
  Printf.printf "lowering case B fixtures: 3 independent frozen source/candidate pairs passed\n"
let request_domain_tests path =
  let corpus = read_json path in
  require (field "schema_version" corpus = str "biocompiler.request_domains_conformance.v1") "Wrong request corpus schema";
  let cases = Json.array (field "lowering_cases" corpus) in
  let rejections = Json.array (field "lowering_rejections" corpus) in
  require (List.length cases >= 14 && List.length rejections >= 14) "Missing mandatory lowering corpus coverage";
  let ids = List.map (fun case -> Json.string (field "id" case)) (cases @ rejections) in
  require (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate lowering fixture ID";
  List.iter (fun case ->
      let request, candidate = field "request" case, field "behavior" case in
      let report = check_report request candidate (accepted request candidate) in
      List.iter (fun key -> require (field key report = field key case)
          (Json.string (field "id" case) ^ ": wrong retained " ^ key))
        ["request_fingerprint"; "request_artifact_fingerprint"; "behavior_fingerprint"; "behavior_artifact_fingerprint"]) cases;
  List.iter (fun case ->
      let code = Json.string (field "expected_code" case) in
      let expected_outcome = if String.starts_with ~prefix:"unsupported_" code then "unsupported" else "invalid" in
      require (field "expected_outcome" case = str expected_outcome) "Wrong retained diagnostic outcome";
      rejected (field "request" case) (field "behavior" case) code) rejections;
  Printf.printf "lowering request fixtures: %d exact pairs and %d intended correspondence/unsupported rejections passed\n"
    (List.length cases) (List.length rejections)
let () = match Array.to_list Sys.argv with
  | [_] -> unit_tests ()
  | [_; directory; corpus] -> case_b_tests directory; request_domain_tests corpus
  | _ -> failwith "usage: test_lowering_check.exe [<absolute-case-b-directory> <absolute-request-domains.json>]"
