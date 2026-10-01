open Bioc_wire
module B = Bioc_domain.Behavior
module N = Bioc_domain.Runtime_number
module D = Bioc_domain.Execution_data
module R = Bioc_semantics.Reference
module Names = Set.Make (String)

let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let strings value = arr (List.map str value)
let field key value = Json.field key (Json.object_fields value)
let integer value = Json.integer value |> Z.to_int
let zero_fingerprint = String.make 64 '0'
let expect_json label actual expected =
  if not (Json.equal actual expected) then (
    let rec difference path actual expected =
      match actual, expected with
      | Json.Object actual, Json.Object expected ->
          let keys = List.map fst actual @ List.map fst expected |> List.sort_uniq String.compare in
          let key = List.find (fun key ->
              match List.assoc_opt key actual, List.assoc_opt key expected with
              | Some a, Some b -> not (Json.equal a b) | None, None -> false | _ -> true) keys in
          (match List.assoc_opt key actual, List.assoc_opt key expected with
           | Some a, Some b -> difference (path ^ "/" ^ key) a b
           | _ -> path ^ "/" ^ key ^ ": missing or unexpected object field")
      | Json.Array actual, Json.Array expected when List.length actual = List.length expected ->
          let pairs = List.combine actual expected |> List.mapi (fun index pair -> index, pair) in
          let index, (a, b) = List.find (fun (_, (a, b)) -> not (Json.equal a b)) pairs in
          difference (path ^ "/" ^ string_of_int index) a b
      | _ -> path ^ ": expected " ^ Canonical.encode expected ^ ", got " ^ Canonical.encode actual
    in
    failwith (label ^ ": " ^ difference "" actual expected))
let literal_program () =
  let condition = Json.parse {|{"kind":"condition","name":"Condition","dimensions":{},"arguments":[]}|} in
  let level = Json.parse {|{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]}|} in
  let node ?(dtype = Json.Null) ?(role = str "cell") identity kind inputs attributes =
    obj ["id", str identity; "kind", str kind; "inputs", strings inputs; "attributes", obj attributes;
         "data_type", dtype; "role", role; "source", Json.Null; "contact_bound", Json.Bool false;
         "requirement_ids", strings ["requirement:rule"]] in
  let nodes = [
    node ~role:Json.Null "cell" "role" [] ["name", str "selected"; "cell_type", str "human_T_cell"; "engineering", str "in_vivo"];
    node "environment" "scope" ["cell"] ["name", str "environment"; "scope", str "environment"];
    node ~dtype:level "signal" "signal" ["environment"]
      ["name", str "flag"; "scope", str "environment"; "observation", str "signal"];
    node ~dtype:condition "high" "qualitative" ["signal"] ["band", str "high"];
    node "report" "action.report" ["cell"] ["ongoing", Json.Bool false; "label", str "seen"];
    node "rule" "rule" ["cell"; "high"; "report"] [
      "trigger", str "condition"; "execution", str "concurrent"; "priority", str "none";
      "ongoing_activation", str "level"; "impulse_activation", str "onset"; "state_assignment", str "level"]] in
  let lineage = ["cell"; "environment"; "high"; "report"; "rule"; "signal"] in
  obj ["schema_version", str "biocompiler.behavior.v0.1"; "name", str "literal_report";
       "nodes", arr nodes; "roots", strings ["cell"; "rule"]; "source_fingerprint", str zero_fingerprint;
       "requirements", arr [obj ["id", str "requirement:rule"; "kind", str "rule"; "source_node_id", str "rule";
                                 "lineage", strings lineage; "source", Json.Null]];
       "source_links", obj ["cell", strings ["cell"]; "environment", strings ["cell"; "environment"];
         "signal", strings ["cell"; "environment"; "signal"]; "high", strings ["cell"; "environment"; "high"; "signal"];
         "report", strings ["cell"; "report"]; "rule", strings lineage];
       "policies", B.execution_policies B.V0_1; "parameter_bindings", obj []]
  |> B.of_json
let input time high =
  D.Input_frame.make ~time:(N.of_int time) ~signals:["signal", D.Sample.make ~high ()] ()
let rejected expected_code operation =
  match operation () with
  | _ -> failwith ("Reference accepted invalid input; expected " ^ expected_code)
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code = expected_code)
        ("Wrong reference diagnostic " ^ diagnostic.code ^ "; expected " ^ expected_code)
let unit_tests () =
  let program = literal_program () in
  let history = [input 0 true; input 1 true; input 2 false; input 3 true] in
  let result = R.evaluate program history |> D.Result.to_json in
  (* Hand-authored complete primitive request/frame shapes. No evaluator or
     fixture producer supplies these expectations. *)
  let reaction time = obj [
      "action_id", str "report"; "rule_id", str "rule"; "kind", str "action.report"; "contact_id", Json.Null;
      "attributes", obj ["label", str "seen"; "ongoing", Json.Bool false]; "values", obj [];
      "requirement_ids", strings ["requirement:rule"]; "source", Json.Null; "rule_source", Json.Null;
      "started_at", Json.int time; "expires_at", Json.Null; "specification_id", str "report";
      "specification_source", Json.Null] in
  let frame time reactions = obj ["time", Json.int time; "actions", arr []; "reactions", arr reactions;
      "events", arr []; "states", obj []; "memories", obj []; "microsteps", Json.int 1] in
  let expected = obj ["role", str "cell"; "horizon", Json.int 3; "behavior_fingerprint", str (B.fingerprint program);
      "source_fingerprint", str zero_fingerprint;
      "execution_profile", field "profile" (B.execution_policies B.V0_1);
      "frames", arr [frame 0 [reaction 0]; frame 1 []; frame 2 []; frame 3 [reaction 3]]] in
  require (Json.equal result expected) "Literal complete onset/reaction trace differs";
  require (Json.equal result (R.evaluate program history |> D.Result.to_json)) "Reference reused session state across calls";
  require (Json.equal result (R.evaluate ~role:"selected" program history |> D.Result.to_json)) "Role-name selection changed trace";
  let truncated = R.evaluate ~until:N.zero program history |> D.Result.to_json in
  expect_json "Explicit horizon did not truncate later supplied history"
    (field "frames" truncated) (arr [frame 0 [reaction 0]]);
  rejected "evaluation_role" (fun () -> R.evaluate ~role:"missing" program history);
  rejected "evaluation_history" (fun () -> R.evaluate program []);
  rejected "evaluation_history" (fun () -> R.evaluate program [input 1 true]);
  rejected "evaluation_history" (fun () -> R.evaluate program [input 0 true; input 0 false]);
  rejected "evaluation_horizon" (fun () -> R.evaluate ~until:(N.of_int (-1)) program history);
  rejected "evaluation_microsteps" (fun () -> R.evaluate ~max_microsteps:0 program history);
  rejected "evaluation_observation" (fun () -> R.evaluate program [D.Input_frame.make ~time:N.zero ()]);
  rejected "evaluation_observation" (fun () -> R.evaluate program [
      D.Input_frame.make ~time:N.zero ~signals:["signal", D.Sample.make ~value:(N.of_int 1) ()] ()]);
  rejected "evaluation_scope" (fun () -> R.evaluate program [
      D.Input_frame.make ~time:N.zero ~signals:["signal", D.Sample.make ~high:true ()]
        ~contacts:["target", ["signal", D.Sample.make ~high:true ()]] ()]);
  rejected "evaluation_work_limit" (fun () -> R.evaluate ~budget:(R.make_budget ~max_work:1 ()) program history);
  rejected "evaluation_output_limit" (fun () -> R.evaluate ~budget:(R.make_budget ~max_frames:1 ()) program history);
  rejected "evaluation_output_limit" (fun () -> R.evaluate ~budget:(R.make_budget ~max_trace_items:1 ()) program history);
  require (field "max_work" (R.budget_json R.default_budget) = Json.int 10_000_000) "Unrecorded default work budget";
  Printf.printf "reference literals: complete reaction trace, role selection, fresh-session isolation, and 12 intended failures passed\n"

let read_json path =
  require (not (Filename.is_relative path)) "Reference corpus path must be absolute";
  let channel = open_in_bin path in
  let content = Fun.protect ~finally:(fun () -> close_in channel) (fun () ->
      let length = in_channel_length channel in
      require (length <= Limits.max_request_bytes) "Reference corpus exceeds request byte budget";
      really_input_string channel length) in
  Json.parse content
let optional decoder = function Json.Null -> None | value -> Some (decoder value)
let case_inputs programs case =
  let key = Json.string (field "program_id" case) in
  let program = match List.assoc_opt key programs with Some value -> value | None -> failwith ("Missing reference program " ^ key) in
  let history = Json.array (field "history" case) |> List.map D.Input_frame.of_json in
  let role = optional Json.string (field "role" case) in
  let until = optional N.of_json (field "until" case) in
  let microsteps = field "max_microsteps" case in
  program, history, role, until, microsteps
let run_case program history role until microsteps =
  (* The public native API takes an int. Validate the serialized test option
     here so the Python-only Boolean option rejection remains a checked
     boundary case, never a claim that a Boolean inhabited the OCaml API. *)
  let max_microsteps = match microsteps with
    | Json.Int value when Z.fits_int value -> Z.to_int value
    | _ -> Diagnostic.fail "evaluation_microsteps" "max_microsteps must be an integer." in
  R.evaluate ?role ?until ~max_microsteps program history
let reachable program selected =
  let nodes = B.nodes program |> List.map (fun node -> Bioc_domain.Identity.Node.to_string (B.node_id node), node) in
  let owner node = Option.map Bioc_domain.Identity.Role.to_string (B.role node) in
  let pending = ref (B.roots program |> List.map Bioc_domain.Identity.Node.to_string
      |> List.filter (fun identity -> let role = owner (List.assoc identity nodes) in role = None || role = Some selected)) in
  let visited = ref Names.empty and kinds = ref Names.empty in
  while !pending <> [] do
    let identity = List.hd !pending in pending := List.tl !pending;
    if not (Names.mem identity !visited) then (
      visited := Names.add identity !visited;
      let node = List.assoc identity nodes in
      if owner node = None || owner node = Some selected then kinds := Names.add (B.kind_name (B.operation node)) !kinds;
      let inputs = List.map Bioc_domain.Identity.Node.to_string (B.inputs node) in
      let inputs = match B.operation node with B.Signature _ -> [List.hd inputs] | _ -> inputs in
      pending := inputs @ !pending)
  done;
  !kinds
let corpus_tests path =
  let corpus = read_json path in
  require (field "schema_version" corpus = str "biocompiler.reference_execution_conformance.v1") "Wrong reference corpus schema";
  let cases = Json.array (field "cases" corpus)
  and rejections = Json.array (field "rejections" corpus)
  and parser_rejections = Json.array (field "parser_rejections" corpus) in
  let coverage = field "coverage" corpus in
  List.iter (fun (key, count) -> require (field key coverage = Json.int count) ("Incorrect reference census " ^ key))
    ["positive_count", List.length cases; "evaluation_rejection_count", List.length rejections;
     "parser_rejection_count", List.length parser_rejections];
  require (List.length cases >= 86 && List.length rejections >= 23 && List.length parser_rejections >= 16)
    "Missing mandatory retained reference coverage";
  require (field "case_b_count" coverage = Json.int 24 && field "uncovered_kinds" coverage = arr [])
    "Missing case B timelines or operation responsibilities";
  require (List.length (List.filter (fun case ->
      String.starts_with ~prefix:"case_b/" (Json.string (field "id" case))) cases) = 24)
    "Case B coverage census lacks its 24 retained executions";
  let programs = Json.array (field "programs" corpus) |> List.map (fun item ->
      let raw = field "behavior" item in
      let identity = Json.string (field "id" item) in
      require (identity = Canonical.fingerprint raw) "Program artifact hash changed";
      let program = B.of_json raw in
      require (field "behavior_fingerprint" item = str (B.fingerprint program)) "Program semantic fingerprint changed";
      require (Json.equal raw (B.to_json program)) "Program import changed retained source/policy authority";
      identity, program) in
  require (List.length programs = integer (field "program_count" coverage)) "Incorrect program census";
  let unique values label =
    require (List.length values = List.length (List.sort_uniq String.compare values)) ("Duplicate " ^ label) in
  unique (List.map fst programs) "retained program identity";
  unique (List.map (fun item -> Json.string (field "id" item)) (cases @ rejections @ parser_rejections)) "reference case identity";
  let observed = ref Names.empty and emitted = ref Names.empty and traces = Hashtbl.create 128 in
  let by_profile = Hashtbl.create 2 and witnesses = Hashtbl.create 128 in
  List.iter (fun case ->
      let program, history, role, until, max_microsteps = case_inputs programs case in
      let result = run_case program history role until max_microsteps in
      let json = D.Result.to_json result in
      Hashtbl.add traces (Json.string (field "id" case)) json;
      expect_json (Json.string (field "id" case) ^ ": complete reference trace differs")
        json (field "expected_trace" case);
      require (str (Canonical.fingerprint json) = field "trace_fingerprint" case)
        (Json.string (field "id" case) ^ ": trace hash differs");
      require (Json.equal json (run_case program history role until max_microsteps |> D.Result.to_json))
        (Json.string (field "id" case) ^ ": repeat execution retained session state");
      let kinds = reachable program (D.Result.role result) in
      observed := Names.union !observed kinds;
      Hashtbl.add witnesses (Json.string (field "id" case)) kinds;
      let profile = B.schema_version (B.profile program) in
      let old = Option.value ~default:Names.empty (Hashtbl.find_opt by_profile profile) in
      Hashtbl.replace by_profile profile (Names.union old kinds);
      List.iter (fun frame ->
          List.iter (fun action -> emitted := Names.add (D.Action.kind action) !emitted)
            (D.Frame.actions frame @ D.Frame.reactions frame)) (D.Result.frames result)) cases;
  require (strings (Names.elements !observed) = field "reachable_kinds" coverage) "Reachable operation census differs";
  let declared = Json.array (field "supported_kinds" coverage) @ Json.array (field "extension_kinds" coverage)
      |> List.map Json.string |> Names.of_list in
  require (Names.equal !observed declared && Names.cardinal declared = 42) "A supported operation lacks execution coverage";
  require (strings (Names.elements !emitted) = field "emitted_action_kinds" coverage) "Primitive action responsibility census differs";
  require (Json.equal (obj (Hashtbl.fold (fun profile kinds result ->
      (profile, strings (Names.elements kinds)) :: result) by_profile [])) (field "by_profile" coverage))
    "Profile-specific operation responsibility census differs";
  require (Names.equal declared (Json.object_fields (field "operation_witnesses" coverage)
      |> List.map fst |> Names.of_list)) "Missing operation witness inventory";
  List.iter (fun (kind, listed) ->
      let actual = Hashtbl.fold (fun identity kinds result ->
          if Names.mem kind kinds then identity :: result else result) witnesses [] |> List.sort String.compare in
      require (strings actual = listed) ("Operation witness set differs for " ^ kind))
    (Json.object_fields (field "operation_witnesses" coverage));
  let literals = Json.array (field "literal_expectations" corpus) in
  let projections = Json.array (field "literal_assertions" corpus) in
  require (List.length literals >= 3 && List.length projections >= 3) "Missing independent execution literals";
  List.iter (fun literal ->
      let trace = Hashtbl.find traces (Json.string (field "case_id" literal)) in
      require (Json.equal trace (field "expected_trace" literal)) "Independent complete-trace literal differs") literals;
  List.iter (fun literal ->
      let trace = Hashtbl.find traces (Json.string (field "case_id" literal)) in
      let frames = Json.array (field "frames" trace) in
      let actual = match Json.string (field "projection" literal) with
        | "reaction_times" -> arr (List.concat_map (fun frame ->
            List.map (fun _ -> field "time" frame) (Json.array (field "reactions" frame))) frames)
        | "first_action_rate" ->
            let actions = List.concat_map (fun frame -> Json.array (field "actions" frame)) frames in
            field "rate" (field "values" (List.hd actions))
        | _ -> failwith "Unknown independent numeric projection" in
      require (Json.equal actual (field "expected" literal)) "Independent numerical projection differs") projections;
  let case_b = Json.array (field "case_b_assertions" corpus) in
  require (List.length case_b >= 9) "Missing original independently authored case B timeline assertions";
  List.iter (fun literal ->
      let trace = Hashtbl.find traces (Json.string (field "case_id" literal)) in
      let state = Json.string (field "state_id" literal) in
      let actual = Json.array (field "frames" trace) |> List.map (fun frame ->
          let count = Json.array (field "actions" frame)
              |> List.filter (fun action -> field "kind" action = str "action.secrete") |> List.length in
          obj ["time", field "time" frame; "state", field state (field "states" frame); "secretion_count", Json.int count]) in
      require (Json.equal (arr actual) (field "expected" literal)) "Independent original case B timeline differs") case_b;
  List.iter (fun case ->
      (* Imports precede the rejection assertion; structural failures cannot
         substitute for intended runtime errors. *)
      let program, history, role, until, max_microsteps = case_inputs programs case in
      require (field "expected_stage" case = str "evaluation") "Wrong runtime rejection stage";
      rejected (Json.string (field "expected_code" case))
        (fun () -> run_case program history role until max_microsteps)) rejections;
  List.iter (fun case ->
      let code = Json.string (field "expected_code" case) in
      let input = Json.string (field "input_json" case) in
      match Json.string (field "expected_stage" case) with
      | "json" -> rejected code (fun () -> Json.parse input)
      | "decode" ->
          let raw = Json.parse input in
          rejected code (fun () ->
          match Json.string (field "record_kind" case) with
          | "input_frame" -> ignore (D.Input_frame.of_json raw)
          | "sample" -> ignore (D.Sample.of_json raw)
          | _ -> failwith "Unknown retained execution-data record kind")
      | _ -> failwith "Unknown parser rejection stage") parser_rejections;
  Printf.printf "reference corpus: %d complete traces, %d evaluation failures, %d parser failures, all 42 operations passed\n"
    (List.length cases) (List.length rejections) (List.length parser_rejections)
let () = match Array.to_list Sys.argv with
  | [_] -> unit_tests ()
  | [_; corpus] -> corpus_tests corpus
  | _ -> failwith "usage: test_reference.exe [<absolute-reference-corpus.json>]"
