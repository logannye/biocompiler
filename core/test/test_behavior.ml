open Bioc_wire
module Behavior = Bioc_domain.Behavior
module Identity = Bioc_domain.Identity

let require condition message = if not condition then failwith message
let str value = Json.String value
let obj fields = Json.Object fields
let arr values = Json.Array values
let strings values = arr (List.map str values)
let fields = Json.object_fields
let field key value = Json.field key (fields value)
let set key value source = obj ((key, value) :: List.remove_assoc key (fields source))
let remove key source = obj (List.remove_assoc key (fields source))
let scalar_type name dimensions = obj ["kind", str "scalar"; "name", str name;
                                       "dimensions", obj dimensions; "arguments", arr []]
let duration = scalar_type "Duration" ["time", Json.int 1]
let level = scalar_type "Level" []
let condition = Json.parse {|{"kind":"condition","name":"Condition","dimensions":{},"arguments":[]}|}
let event = Json.parse {|{"kind":"event","name":"Event","dimensions":{},"arguments":[]}|}
let scalar ?(dtype = duration) ?(unit_name = "s") value =
  obj ["kind", str "scalar"; "value", value; "canonical_value", value; "unit", str unit_name; "type", dtype]
let source = obj ["file", str "literal/behavior.py"; "line", Json.int 1; "function", str "author"]
let node ?(inputs = []) ?(attributes = []) ?(dtype = Json.Null) ?(role = Json.Null)
    ?(contact = false) id kind =
  obj ["id", str id; "kind", str kind; "inputs", strings inputs; "attributes", obj attributes;
       "data_type", dtype; "role", role; "source", source; "contact_bound", Json.Bool contact;
       "requirement_ids", arr []]

(* This fixture builder reconstructs literal test metadata without invoking any
   production domain helper. Actual retained Python fixtures are read separately
   below and must match their independent literal fingerprint expectations. *)
let program ?(profile = Behavior.V0_1) ?(integral_step = Json.Null) nodes =
  let kind node = Json.string (field "kind" node) in
  let identity node = Json.string (field "id" node) in
  let table = List.map (fun node -> identity node, node) nodes in
  let rec lineage seen identity =
    if List.mem identity seen then seen else
      let node = List.assoc identity table in
      let refs = Json.array (field "inputs" node) |> List.map Json.string in
      let refs = match field "role" node with Json.Null -> refs | value -> Json.string value :: refs in
      List.fold_left lineage (identity :: seen) refs
  in
  let lineages = List.map (fun node -> identity node, List.sort String.compare (lineage [] (identity node))) nodes in
  let requirements = List.filter (fun node -> List.mem (kind node) ["rule"; "state"; "memory"]) nodes
      |> List.map (fun node -> obj ["id", str ("requirement:" ^ identity node); "kind", field "kind" node;
          "source_node_id", field "id" node; "lineage", strings (List.assoc (identity node) lineages);
          "source", field "source" node]) in
  let nodes = List.map (fun node ->
      let ids = List.filter (fun requirement ->
          List.mem (field "id" node) (Json.array (field "lineage" requirement))) requirements
          |> List.map (field "id") in
      set "requirement_ids" (arr ids) node) nodes in
  let roots = List.filter (fun node -> List.mem (kind node) ["role"; "parameter"; "memory"; "state"; "secretion"; "rule"; "channel"]) nodes
      |> List.map (field "id") in
  let parameters = List.filter (fun node -> kind node = "parameter") nodes
      |> List.map (fun node -> let attributes = field "attributes" node in
                   Json.string (field "name" attributes), field "default" attributes) in
  obj ["schema_version", str (Behavior.schema_version profile); "name", str "literal_behavior";
       "nodes", arr nodes; "roots", arr roots; "source_fingerprint", str (String.make 64 '0');
       "requirements", arr requirements; "source_links", obj (List.map (fun (id, lineage) -> id, strings lineage) lineages);
       "policies", Behavior.execution_policies ~integral_step profile; "parameter_bindings", obj parameters]

let accepted value = Behavior.of_json value
let rejection_count = ref 0
let rejected value code =
  match Behavior.of_json value with
  | _ -> failwith ("Accepted invalid Behavior; expected " ^ code)
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code = code) ("Wrong Behavior rejection: " ^ diagnostic.code ^ ", expected " ^ code);
      incr rejection_count
let change_node identity transform document =
  set "nodes" (arr (Json.array (field "nodes" document) |> List.map (fun node ->
      if field "id" node = str identity then transform node else node))) document
let change_attributes identity transform document = change_node identity (fun node -> set "attributes" (transform (field "attributes" node)) node) document

let role id = node id "role" ~attributes:["name", str id; "cell_type", str "human_T_cell"; "engineering", str "in_vivo"]
let scope id role name = node ~inputs:[role] ~role:(str role) ~contact:(name = "contact") id "scope"
    ~attributes:["name", str name; "scope", str name]
let literal id value = node id "literal" ~dtype:duration ~attributes:["value", scalar value]
let state_node values initial = node "state" "state" ~inputs:["cell"] ~role:(str "cell")
    ~attributes:["name", str "phase"; "values", arr values; "initial", initial;
                 "observation", str "shared_pre_update_state"; "arbitration", str "coalesce_identical_else_error"]

let broad_operation_nodes timer_nodes =
  let local ?(contact = false) ?(dtype = Json.Null) ?(attributes = []) id kind inputs =
    node ~inputs ~role:(str "cell") ~contact ~dtype ~attributes id kind in
  let numeric = node "level" "literal" ~dtype:level ~attributes:["value", scalar ~dtype:level ~unit_name:"1" (Json.int 2)] in
  let rate = scalar_type "ProductionRate" ["amount", Json.int 1; "time", Json.int (-1)] in
  let rate_literal = node "rate" "literal" ~dtype:rate ~attributes:["value", scalar ~dtype:rate ~unit_name:"mol/s" (Json.int 1)] in
  let temporal = ["history", str "since_initialization"] in
  let action ?(contact = false) ?(extra = []) id kind inputs =
    local ~contact ~attributes:(("ongoing", Json.Bool true) :: extra) id kind inputs in
  timer_nodes @ [
    numeric; rate_literal; scope "contact" "cell" "contact";
    local ~contact:true ~dtype:level ~attributes:["name", str "marker"; "scope", str "contact"; "observation", str "marker"] "marker" "signal" ["contact"];
    local ~contact:true ~dtype:condition ~attributes:["band", str "high"] "recognition" "qualitative" ["marker"];
    local ~contact:true ~dtype:condition "both" "and" ["condition"; "recognition"];
    local ~contact:true ~dtype:condition "either" "or" ["condition"; "recognition"];
    local ~contact:true ~dtype:condition "inverse" "not" ["recognition"];
    local ~contact:true ~dtype:condition ~attributes:["count", Json.int 1] "threshold" "at_least" ["condition"; "recognition"];
    local ~dtype:level "sum" "add" ["signal"; "level"];
    local ~dtype:level "difference" "subtract" ["signal"; "level"];
    local ~dtype:duration "product" "multiply" ["signal"; "duration"];
    local ~dtype:duration "quotient" "divide" ["duration"; "level"];
    local ~dtype:level "negative" "negate" ["signal"];
    local ~dtype:condition ~attributes:["operator", str "ge"] "comparison" "compare" ["signal"; "level"];
    local ~contact:true ~dtype:condition ~attributes:(temporal @ ["includes_present", Json.Bool true]) "recent" "recently" ["recognition"; "duration"];
    local ~dtype:event ~attributes:["initially_true_emits", Json.Bool true] "first_event" "became_true" ["condition"];
    local ~contact:true ~dtype:event ~attributes:["initially_true_emits", Json.Bool true] "second_event" "became_true" ["recognition"];
    local ~contact:true ~dtype:event ~attributes:(temporal @ ["emits_at", str "second_event"]) "ordered" "followed_by" ["first_event"; "second_event"; "duration"];
    local ~dtype:condition ~attributes:["name", str "seen"; "input_names", strings ["owner"; "set_when"; "reset_when"; "duration"];
        "initial", Json.Bool false; "setting", str "onset"; "initial_true_is_onset", Json.Bool true;
        "reset_priority", Json.Bool true; "expiry", str "latest_setting_onset"] "memory" "memory" ["cell"; "recognition"; "condition"; "duration"];
    local ~dtype:condition "remembered" "memory.is_set" ["memory"];
    local ~dtype:condition ~attributes:["definition", obj ["name", str "test"; "module", str "fixture"; "qualname", str "test"];
        "bindings", obj ["observation", obj ["input", Json.int 1]; "literal", obj ["literal", arr [Json.int 1; Json.Bool true]];
                         "nested", arr [obj ["object", obj ["input", Json.int 1]]]]]
      "signature" "signature" ["condition"; "recognition"];
    local ~attributes:["name", str "product"; "product", str "artificial"; "default", Json.Bool false;
                       "activity", str "requires_rule_or_controller"] "secretion" "secretion" ["cell"];
    action ~extra:["rate", str "expression"] "production" "action.secrete" ["secretion"; "rate"];
    action ~contact:true "eliminate" "action.eliminate" ["cell"; "contact"];
    action ~contact:true "engulf" "action.engulf" ["cell"; "contact"];
    action ~extra:["antigen", str "artificial"] "present" "action.present" ["cell"];
    action ~contact:true "retain_scope" "action.retain" ["cell"; "contact"];
    action ~extra:["location", str "local"] "retain_location" "action.retain" ["cell"];
    action "expand" "action.expand" ["cell"];
    action "rest" "action.rest" ["cell"];
    action ~extra:["phenotype", str "artificial"] "differentiate" "action.differentiate" ["cell"]]

let unit_tests () =
  let empty = program [] in
  ignore (accepted empty);
  rejected (set "name" (str "\255") empty) "invalid_utf8";
  rejected (set "parameter_bindings" (obj ["x", Json.Float nan]) empty) "nonfinite_number";
  rejected (set "parameter_bindings" (obj ["x", Json.int 1; "x", Json.int 1]) empty) "duplicate_key";
  rejected (set "schema_version" (str "biocompiler.behavior.v9") empty) "unsupported_behavior_profile";
  rejected (set "source_fingerprint" (str (String.make 64 'A')) empty) "behavior_source_fingerprint";
  rejected (set "policies" (set "state_writes" (str "last_writer_wins") (field "policies" empty)) empty) "behavior_policy";
  rejected (set "policies" (set "initial_time" (Json.Float 0.) (field "policies" empty)) empty) "behavior_policy";
  rejected (set "policies" (set "integral_step" Json.Null (field "policies" empty)) empty) "behavior_policy";
  let a = literal "a" (Json.int 2) and b = literal "b" (Json.int 3) in
  let difference = node "difference" "subtract" ~inputs:["b"; "a"] ~dtype:duration in
  let arithmetic = accepted (program [a; b; difference]) in
  require (Behavior.constant_value arithmetic (Identity.Node.of_string "difference") = Some (Behavior.Integer Z.one)) "Integer subtraction lost exactness";
  rejected (change_node "difference" (set "inputs" (strings ["a"])) (program [a; b; difference])) "behavior_operation";
  rejected (change_node "difference" (set "data_type" condition) (program [a; b; difference])) "behavior_type";
  rejected (change_node "difference" (set "kind" (str "future.operation")) (program [a; b; difference])) "unsupported_behavior_operation";
  let quotient = node "quotient" "divide" ~inputs:["a"; "b"] ~dtype:level in
  let divide = accepted (program [a; b; quotient]) in
  require (match Behavior.constant_value divide (Identity.Node.of_string "quotient") with
      | Some (Behavior.Real value) -> value = 2. /. 3. | _ -> false) "Integer true division changed";
  rejected (program [a; literal "b" (Json.int 0); quotient]) "behavior_constant";
  let sum = node "sum" "add" ~inputs:["a"; "b"] ~dtype:duration in
  rejected (program [literal "a" (Json.Float 1e308); literal "b" (Json.Float 1e308); sum]) "numeric_overflow";
  let zero_divide = accepted (program [literal "a" (Json.int 0); literal "b" (Json.int (-3)); quotient]) in
  require (match Behavior.constant_value zero_divide (Identity.Node.of_string "quotient") with
      | Some (Behavior.Real value) -> Int64.bits_of_float value = Int64.bits_of_float (-0.) | _ -> false) "Integer division lost negative zero";
  let typed_state = program [role "cell"; state_node [Json.Bool true; Json.int 1; Json.Float 1.; str "1"] (Json.Bool true)] in
  ignore (accepted typed_state);
  rejected (change_attributes "state" (set "values" (arr [Json.Float 0.; Json.Float (-0.)])) typed_state) "behavior_operation";
  rejected (change_attributes "state" (set "initial" (Json.Bool false)) typed_state) "behavior_operation";
  rejected (change_attributes "state" (set "observation" (str "prior_state")) typed_state) "behavior_operation";
  rejected (set "requirements" (arr []) typed_state) "behavior_requirements";
  rejected (set "roots" (strings ["cell"]) typed_state) "behavior_roots";
  rejected (change_node "cell" (set "requirement_ids" (arr [])) typed_state) "behavior_requirements";
  rejected (set "source_links" (obj ["cell", strings ["cell"]; "state", strings ["state"]]) typed_state) "behavior_lineage";
  let mismatched_assignment = node "assignment" "action.state_set" ~inputs:["state"] ~role:(str "cell")
      ~attributes:["value", Json.Bool true; "idempotent", Json.Bool true; "ongoing", Json.Bool false] in
  rejected (program [role "cell"; state_node [Json.int 1] (Json.int 1); mismatched_assignment]) "behavior_operation";
  let parameter = node "parameter" "parameter" ~dtype:duration
      ~attributes:["name", str "duration"; "bound", Json.Bool true; "default", scalar (Json.int 2)] in
  let parameter_program = program [parameter] in
  ignore (accepted parameter_program);
  rejected (set "parameter_bindings" (obj ["duration", scalar (Json.int 3)]) parameter_program) "behavior_bindings";
  rejected (change_node "parameter" (set "role" (str "cell")) (program [role "cell"; parameter])) "behavior_operation";
  let signal = node "signal" "signal" ~inputs:["environment"] ~role:(str "cell") ~dtype:level
      ~attributes:["name", str "drive"; "scope", str "environment"; "observation", str "signal"] in
  let condition_node = node "condition" "qualitative" ~inputs:["signal"] ~role:(str "cell") ~dtype:condition ~attributes:["band", str "present"] in
  let held = node "held" "held_for" ~inputs:["condition"; "duration"] ~role:(str "cell") ~dtype:condition
      ~attributes:["history", str "since_initialization"; "requires_full_interval", Json.Bool true] in
  let timer_nodes = [role "cell"; scope "environment" "cell" "environment"; signal; condition_node; literal "duration" (Json.int 2); held] in
  let timer = program timer_nodes in
  ignore (accepted timer);
  rejected (change_attributes "duration" (set "value" (scalar (Json.int 0))) timer) "behavior_duration";
  rejected (change_node "held" (set "contact_bound" (Json.Bool true)) timer) "behavior_contact";
  rejected (program (role "other" :: List.map (fun item -> if field "id" item = str "held" then set "role" (str "other") item else item) timer_nodes)) "behavior_operation";
  let broad = program (broad_operation_nodes timer_nodes) in
  let broad_checked = accepted broad in
  require (List.length (Behavior.nodes broad_checked) = 38) "Broad v0.1 operation inventory changed";
  require (List.length (Behavior.requirements broad_checked) = 1) "Memory requirement was omitted";
  rejected (change_attributes "memory" (set "reset_priority" (Json.Bool false)) broad) "behavior_operation";
  rejected (change_node "memory" (set "contact_bound" (Json.Bool true)) broad) "behavior_contact";
  rejected (change_node "signature" (set "contact_bound" (Json.Bool true)) broad) "behavior_contact";
  rejected (change_attributes "signature" (set "bindings" (obj ["x", obj ["input", Json.int 2]])) broad) "behavior_operation";
  rejected (change_attributes "signature" (set "bindings" (obj ["x", Json.int 1])) broad) "behavior_operation";
  rejected (change_attributes "signature" (set "bindings" (obj ["x", obj ["literal", Json.Float nan]])) broad) "nonfinite_number";
  rejected (change_attributes "threshold" (set "count" (Json.Bool true)) broad) "invalid_type";
  rejected (change_node "product" (set "data_type" level) broad) "behavior_type";
  rejected (change_attributes "production" (set "ongoing" (Json.Bool false)) broad) "behavior_operation";
  rejected (change_node "eliminate" (set "inputs" (strings ["cell"; "environment"])) broad) "behavior_operation";
  let event_node = node "event" "became_true" ~inputs:["condition"] ~role:(str "cell") ~dtype:event ~attributes:["initially_true_emits", Json.Bool true] in
  let report = node "report" "action.report" ~inputs:["cell"] ~role:(str "cell") ~attributes:["ongoing", Json.Bool false; "label", str "observed"] in
  let event_rule = node "rule" "rule" ~inputs:["cell"; "event"; "report"] ~role:(str "cell")
      ~attributes:["trigger", str "event"; "execution", str "concurrent"; "priority", str "none";
                   "ongoing_activation", str "explicit_duration"; "impulse_activation", str "event";
                   "state_assignment", str "event"; "ongoing_duration", str "explicit"] in
  let event_program = program (timer_nodes @ [event_node; report; event_rule]) in
  ignore (accepted event_program);
  rejected (change_attributes "rule" (remove "ongoing_duration") event_program) "behavior_operation";
  let primitive = node "primitive" "action.rest" ~inputs:["cell"] ~role:(str "cell") ~attributes:["ongoing", Json.Bool true] in
  let pulse = node "pulse" "action.pulse" ~inputs:["primitive"; "duration"] ~role:(str "cell")
      ~attributes:["ongoing", Json.Bool true; "retrigger", str "extend_from_latest_trigger"] in
  let pulse_program = program (timer_nodes @ [event_node; primitive; pulse; set "inputs" (strings ["cell"; "event"; "pulse"]) event_rule]) in
  ignore (accepted pulse_program);
  rejected (change_node "rule" (set "inputs" (strings ["cell"; "event"; "primitive"])) pulse_program) "behavior_operation";
  let channel = node "channel" "channel" ~dtype:level ~attributes:["name", str "alert"; "scope", str "local"] in
  let observation = node "channel_input" "channel_observation" ~inputs:["environment"; "channel"] ~role:(str "cell") ~dtype:level
      ~attributes:["scope", str "receiver_local"; "delivery", str "biological_signal"] in
  let integrated = node "integral" "integrated" ~inputs:["channel_input"; "duration"] ~role:(str "cell") ~dtype:duration
      ~attributes:["window", str "rolling"; "history", str "since_initialization"] in
  let emission = node "emission" "action.emit" ~inputs:["cell"; "channel"; "signal"] ~role:(str "cell")
      ~attributes:["ongoing", Json.Bool true; "value", str "expression"] in
  let v2_nodes = timer_nodes @ [channel; observation; integrated; emission] in
  let v2 = program ~profile:Behavior.V0_2 ~integral_step:(scalar (Json.int 1)) v2_nodes in
  ignore (accepted v2);
  rejected (program v2_nodes) "unsupported_behavior_profile";
  rejected (program ~profile:Behavior.V0_2 v2_nodes) "behavior_policy";
  rejected (set "policies" (set "integral_step" (set "canonical_value" (Json.Float 1.) (scalar (Json.int 1))) (field "policies" v2)) v2) "behavior_policy";
  let normalized = accepted v2 in
  require (Behavior.profile normalized = Behavior.V0_2) "Behavior profile was relabeled";
  require (Json.equal (Behavior.to_json normalized) v2) "Behavior JSON roundtrip dropped fields";
  let relocated = set "nodes" (arr (Json.array (field "nodes" v2) |> List.map (remove "source"))) v2 in
  (* v2 contains no rule/state/memory requirements, so source omission is local. *)
  require (Behavior.fingerprint (accepted relocated) = Behavior.fingerprint normalized) "Source coordinates changed semantic fingerprint";
  Printf.printf "behavior literals: %d intended rejections; profile/type/state/contact/constant/obligation checks passed\n" !rejection_count

let read_json path =
  let channel = open_in_bin path in
  let content = Fun.protect ~finally:(fun () -> close_in channel) (fun () -> really_input_string channel (in_channel_length channel)) in
  Json.parse content
let get_path document path = List.fold_left (fun document key -> field key document) document path
let fixture_tests directory =
  require (not (Filename.is_relative directory)) "Case B corpus path must be absolute";
  let oracle = read_json (Filename.concat directory "current-baseline-oracle.json") in
  require (field "acceptance_authority" oracle = Json.Bool false) "Python baseline must not grant native acceptance";
  let literals = read_json (Filename.concat directory "expectations.json") in
  let count = ref 0 in
  List.iter (fun variant ->
      let candidate = read_json (Filename.concat directory (variant ^ "/candidate.json")) in
      let request = read_json (Filename.concat directory (variant ^ "/request.json")) in
      let behavior = get_path candidate ["execution"; "behavior"] in
      let checked = accepted behavior in
      require (Json.equal (Behavior.to_json checked) behavior) (variant ^ ": Behavior roundtrip changed retained JSON");
      let expected = get_path oracle ["cases"; variant; "behavior_fingerprint"] |> Json.string in
      require (Behavior.fingerprint checked = expected) (variant ^ ": Behavior fingerprint differs from Python baseline");
      require (List.length (Behavior.nodes checked) = 33 && List.length (Behavior.requirements checked) = 6) "Lost retained node/requirement inventory";
      require (Behavior.profile checked = Behavior.V0_2) "Case B lost its v0.2 policy authority";
      if variant = "base" then require (expected = Json.string (get_path literals ["base_identities"; "behavior"])) "Independent literal Behavior fingerprint differs";
      let supplier = get_path request ["library"; "refinements"] |> Json.array |> List.hd |> field "behavior" in
      ignore (accepted supplier);
      incr count;
      let state = List.find (fun node -> field "kind" node = str "state") (Json.array (field "nodes" behavior)) in
      let state_id = Json.string (field "id" state) in
      rejected (change_attributes state_id (set "arbitration" (str "last_writer_wins")) behavior) "behavior_operation";
      rejected (change_node state_id (set "requirement_ids" (arr [])) behavior) "behavior_requirements";
      rejected (set "requirements" (arr (List.tl (Json.array (field "requirements" behavior)))) behavior) "behavior_requirements";
      let rule = List.find (fun node -> field "kind" node = str "rule") (Json.array (field "nodes" behavior)) in
      rejected (change_node (Json.string (field "id" rule)) (set "contact_bound" (Json.Bool true)) behavior) "behavior_contact";
      let changed_source = set "nodes" (arr (Json.array (field "nodes" behavior) |> List.map (fun node -> set "source" Json.Null node))) behavior in
      rejected changed_source "behavior_requirements";
      let all_sources_removed = set "requirements" (arr (Json.array (field "requirements" changed_source) |> List.map (fun requirement -> set "source" Json.Null requirement))) changed_source in
      require (Behavior.fingerprint (accepted all_sources_removed) = expected) "Coherent source relocation changed Behavior identity")
    ["base"; "parameter-default"; "parameter-override"];
  require (!count = 3) "Missing mandatory Behavior fixture variant";
  Printf.printf "behavior retained fixtures: %d source/supplier pairs, intended mutants and literal baseline identities passed\n" !count

let broad_fixture_tests path =
  require (not (Filename.is_relative path)) "Broad Behavior corpus path must be absolute";
  let corpus = read_json path in
  require (field "schema_version" corpus = str "biocompiler.behavior_domains_conformance.v1") "Unknown broad Behavior corpus schema";
  let cases = Json.array (field "cases" corpus) in
  require (List.length cases >= 7) "Broad Behavior corpus is missing required profile cases";
  let ids = List.map (fun case -> Json.string (field "id" case)) cases in
  require (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate broad Behavior fixture ID";
  let observed = ref [] and by_profile = Hashtbl.create 2 in
  List.iter (fun case ->
      let identity = Json.string (field "id" case) in
      let raw = field "behavior" case in
      let behavior = accepted raw in
      let summary = Behavior.summary behavior in
      require (Json.equal raw (Behavior.to_json behavior)) (identity ^ ": broad Behavior document changed on import");
      require (field "fingerprint" case = str (Behavior.fingerprint behavior)) (identity ^ ": broad Behavior fingerprint differs");
      require (field "source_fingerprint" case = str (Behavior.source_fingerprint behavior)) (identity ^ ": source identity differs");
      require (Json.equal (field "operation_counts" case) (field "kinds" summary)) (identity ^ ": operation census differs");
      let kinds = List.map (fun node -> Behavior.kind_name (Behavior.operation node)) (Behavior.nodes behavior) in
      observed := kinds @ !observed;
      let profile = Behavior.schema_version (Behavior.profile behavior) in
      Hashtbl.replace by_profile profile (kinds @ Option.value ~default:[] (Hashtbl.find_opt by_profile profile))) cases;
  let sorted values = List.sort_uniq String.compare values in
  let supported = sorted ["role"; "scope"; "signal"; "qualitative"; "literal"; "parameter";
      "and"; "or"; "not"; "at_least"; "add"; "subtract"; "multiply"; "divide"; "negate"; "compare";
      "held_for"; "recently"; "became_true"; "followed_by"; "memory"; "memory.is_set"; "state"; "state.is";
      "signature"; "secretion"; "rule"; "action.state_set"; "action.report"; "action.pulse";
      "action.eliminate"; "action.engulf"; "action.secrete"; "action.present"; "action.retain";
      "action.expand"; "action.rest"; "action.differentiate"] in
  let extensions = sorted ["integrated"; "channel"; "channel_observation"; "action.emit"] in
  let coverage = field "coverage" corpus in
  require (field "supported_kinds" coverage = strings supported) "Legacy operation inventory changed without a domain test update";
  require (field "extension_kinds" coverage = strings extensions) "Extension operation inventory changed without a domain test update";
  require (sorted !observed = sorted (supported @ extensions)) "Broad Behavior fixture leaves a declared operation untested";
  require (field "covered_kinds" coverage = strings (sorted !observed) && field "uncovered_kinds" coverage = arr [])
    "Broad Behavior coverage claims disagree with parsed cases";
  let actual_profiles = Hashtbl.fold (fun profile kinds result -> (profile, strings (sorted kinds)) :: result) by_profile [] in
  require (Hashtbl.length by_profile = 2 && Json.equal (field "by_profile" coverage) (obj actual_profiles))
    "Broad Behavior profile coverage differs";
  Printf.printf "behavior broad fixtures: %d exact documents/fingerprints, both profiles and %d operations passed\n"
    (List.length cases) (List.length (sorted !observed))

let () =
  match Array.to_list Sys.argv with
  | [_] -> unit_tests ()
  | [_; directory] -> fixture_tests directory
  | [_; directory; broad] -> fixture_tests directory; broad_fixture_tests broad
  | _ -> failwith "usage: test_behavior.exe [absolute-case-b-corpus-directory [absolute-behavior-corpus-json]]"

let () =
  let reverse value = obj (List.rev (fields value)) in
  let raw = program [role "cell"; state_node [str "a";str "b"] (str "a")] in
  let reordered = raw
    |> set "nodes" (arr (List.map reverse (Json.array (field "nodes" raw))))
    |> set "requirements" (arr (List.map reverse (Json.array (field "requirements" raw)))) in
  let actual = Behavior.to_json (Behavior.of_json reordered) in
  List.iter (fun value -> require (List.map fst (fields value) =
    ["id";"kind";"inputs";"attributes";"data_type";"role";"source";"contact_bound";"requirement_ids"])
    "Behavior node extensions displaced original Intent field order") (Json.array (field "nodes" actual));
  let requirements = Json.array (field "requirements" actual) in
  require (List.length requirements = 1) "Ordered Behavior control lost its actual requirement";
  require (List.map fst (fields (List.hd requirements)) = ["id";"kind";"source_node_id";"lineage";"source"])
    "Requirement source metadata displaced original public fields";
  require (Canonical.encode actual = Canonical.encode (Behavior.to_json (Behavior.of_json raw)))
    "Behavior ordering changed validated values"
