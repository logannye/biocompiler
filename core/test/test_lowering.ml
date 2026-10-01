open Bioc_wire
module Domain = Bioc_domain
module Lowering = Bioc_compiler.Lowering
module Names = Set.Make (String)

let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let strings value = arr (List.map str value)
let field key value = Json.field key (Json.object_fields value)
let set key value document = obj ((key, value) :: List.remove_assoc key (Json.object_fields document))
let dtype = Json.parse {|{"kind":"scalar","name":"Level","dimensions":{},"arguments":[]}|}
let scalar value = obj ["kind", str "scalar"; "value", value; "unit", str "1"; "canonical_value", value; "type", dtype]
let source = Json.parse {|{"file":"literal/lowering.py","line":7,"function":"author"}|}
let node identity kind inputs attrs = obj [
    "id", str identity; "kind", str kind; "inputs", strings inputs; "attributes", obj attrs;
    "data_type", dtype; "role", Json.Null; "source", source]
let parameter value = node "parameter" "parameter" []
    ["name", str "amount"; "bound", Json.Bool true; "default", scalar value]
let intent ?(roots = []) nodes = obj ["schema_version", str "biocompiler.intent.v0.1"; "name", str "literal_lowering";
                                     "nodes", arr nodes; "roots", strings roots]
let metadata = Json.parse {|{"schema_version":"biocompiler.binding_metadata.v0.1","category":"user_selected","provenance":{},"allowed_variation":null}|}
let provenance = Json.parse {|{"schema_version":"biocompiler.elaboration_provenance.v0.1","source_identities":{},"dependency_identities":{},"external_inputs":{},"locations":{},"recorded_at":null}|}
let request ?(defaults = []) ?(overrides = []) ?(bindings = []) source = obj [
    "schema_version", str "biocompiler.build_request.v0.1"; "intent", source;
    "explicit_overrides", obj overrides; "resolved_defaults", obj defaults; "resolved_bindings", obj bindings;
    "target", Json.Null; "artifact_scope", str "abstract_behavior"; "behavior_profile", str "biocompiler.behavior.v0.1";
    "implementation_constraints", obj []; "preferences", obj [];
    "parameter_metadata", obj (List.map (fun (key, _) -> key, metadata) bindings); "provenance", provenance]
let rejected code operation =
  match operation () with
  | _ -> failwith ("Accepted invalid lowering; expected " ^ code)
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code = code) ("Wrong producer diagnostic " ^ diagnostic.code ^ "; expected " ^ code)
let unit_tests () =
  let original = intent ~roots:["parameter"] [parameter (Json.int 1)] in
  let binding = ["amount", scalar (Json.int 1)] in
  let authority = Domain.Build_request.of_json (request ~defaults:binding ~bindings:binding original) in
  let result = Lowering.lower authority in
  let emitted = parameter (Json.int 1) |> set "contact_bound" (Json.Bool false) |> set "requirement_ids" (arr []) in
  let expected = obj ["schema_version", str "biocompiler.behavior.v0.1"; "name", str "literal_lowering";
      "nodes", arr [emitted]; "roots", strings ["parameter"];
      "source_fingerprint", str (Domain.Intent.fingerprint (Domain.Intent.of_json original));
      "requirements", arr []; "source_links", obj ["parameter", strings ["parameter"]];
      "policies", Domain.Behavior.execution_policies Domain.Behavior.V0_1; "parameter_bindings", obj binding] in
  require (Json.equal (Domain.Behavior.to_json result) expected) "Literal complete parameter lowering differs";
  let override = ["amount", scalar (Json.Float 2.0)] in
  let override_authority = Domain.Build_request.of_json (request ~overrides:override ~bindings:override original) in
  let overridden = Lowering.lower override_authority in
  require (Json.equal (Domain.Behavior.parameter_bindings overridden |> obj) (obj override)) "Lost authoritative override or numeric kind";
  let forged_node = set "attributes" (obj ["name", str "amount"; "bound", Json.Bool true; "default", scalar (Json.int 9)]) emitted in
  let forged = expected |> set "nodes" (arr [forged_node]) |> set "parameter_bindings" (obj ["amount", scalar (Json.int 9)])
      |> Domain.Behavior.of_json in
  rejected "lowering_authoritative_bindings" (fun () ->
      Bioc_checker.Lowering_check.check ~expected_request:authority ~behavior:forged);
  let unknown = node "future" "future.operation" [] [] in
  let raw = request ~defaults:binding ~bindings:binding (intent ~roots:["parameter"] [parameter (Json.int 1); unknown]) in
  let unsupported = Domain.Build_request.of_json raw in
  rejected "unsupported_lowering_operation" (fun () -> Lowering.lower unsupported);
  let chain = List.init 710 (fun index ->
      if index = 0 then node "value:0" "literal" [] ["value", scalar (Json.int 1)]
      else node ("value:" ^ string_of_int index) "negate" ["value:" ^ string_of_int (index - 1)] []) in
  let large = Domain.Build_request.of_json (request (intent chain)) in
  rejected "lowering_lineage_limit" (fun () -> Lowering.lower large);
  Printf.printf "lowering literals: exact source/binding emission, independent corruption rejection, unknown source and bounded lineage passed\n"

let read_json path =
  require (not (Filename.is_relative path)) "Lowering corpus path must be absolute";
  let channel = open_in_bin path in
  let content = Fun.protect ~finally:(fun () -> close_in channel) (fun () ->
      let length = in_channel_length channel in
      require (length <= Limits.max_request_bytes) "Lowering fixture exceeds byte budget";
      really_input_string channel length) in
  Json.parse content
let corpus_tests path =
  let corpus = read_json path in
  require (field "schema_version" corpus = str "biocompiler.lowering_conformance.v1") "Wrong lowering corpus schema";
  let cases = Json.array (field "cases" corpus) and rejections = Json.array (field "rejections" corpus) in
  let coverage = field "coverage" corpus in
  require (List.length cases >= 31 && List.length rejections >= 32) "Missing mandatory lowering corpus cases";
  List.iter (fun (key, value) -> require (field key coverage = Json.int value) ("Wrong lowering census " ^ key))
    ["positive_count", List.length cases; "rejection_count", List.length rejections];
  let ids = List.map (fun case -> Json.string (field "id" case)) (cases @ rejections) in
  require (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate lowering corpus identity";
  let produced = Hashtbl.create 32 and kinds = ref Names.empty and profiles = Hashtbl.create 2 in
  let exact_prior = ref 0 and equivalent_prior = ref 0 in
  List.iter (fun case ->
      let authority = Domain.Build_request.of_json (field "request" case) in
      let behavior = Lowering.lower authority in
      let json = Domain.Behavior.to_json behavior in
      require (Json.equal json (field "expected_behavior" case))
        (Json.string (field "id" case) ^ ": complete producer output differs");
      List.iter (fun (key, expected) -> require (field key case = str expected) ("Wrong producer identity " ^ key))
        ["request_fingerprint", Domain.Build_request.fingerprint authority;
         "request_artifact_fingerprint", Domain.Build_request.artifact_fingerprint authority;
         "behavior_fingerprint", Domain.Behavior.fingerprint behavior;
         "behavior_artifact_fingerprint", Canonical.fingerprint json];
      require (Json.equal json (Domain.Behavior.to_json (Lowering.lower authority))) "Nondeterministic lowering";
      let report = Bioc_checker.Lowering_check.check ~expected_request:authority ~behavior in
      require (Bioc_checker.Lowering_check.passed report) "Independent correspondence did not pass";
      Hashtbl.add produced (Json.string (field "id" case)) json;
      let observed = Domain.Behavior.nodes behavior
          |> List.map (fun node -> Domain.Behavior.kind_name (Domain.Behavior.operation node)) |> Names.of_list in
      kinds := Names.union !kinds observed;
      let profile = Domain.Behavior.schema_version (Domain.Behavior.profile behavior) in
      let old = Option.value ~default:Names.empty (Hashtbl.find_opt profiles profile) in
      Hashtbl.replace profiles profile (Names.union old observed);
      match List.assoc_opt "prior_checker_candidate" (Json.object_fields case) with
      | None -> ()
      | Some prior ->
          if Json.boolean (field "exact_producer_bytes" prior) then (
            incr exact_prior;
            require (field "artifact_fingerprint" prior = str (Canonical.fingerprint json)) "Retained exact producer identity changed")
          else (
            incr equivalent_prior;
            require (field "id" prior = str "numeric_policy_equality"
                     && field "relation" prior = str "numeric_policy_mapping_equivalence_only"
                     && field "artifact_fingerprint" prior <> str (Canonical.fingerprint json))
              "Checker-compatible numeric spelling was mislabeled exact production")) cases;
  require (!exact_prior = 13 && !equivalent_prior = 1) "Lost retained checker-versus-producer identity distinction";
  require (Names.cardinal !kinds = 42 && strings (Names.elements !kinds) = field "covered_kinds" coverage
           && field "uncovered_kinds" coverage = arr []) "Incomplete producer operation coverage";
  require (Json.equal (obj (Hashtbl.fold (fun key values result -> (key, strings (Names.elements values)) :: result) profiles []))
           (field "by_profile" coverage)) "Producer profile census differs";
  let literals = Json.array (field "literal_expectations" corpus) in
  require (List.length literals >= 6) "Missing independently authored producer expectations";
  List.iter (fun literal ->
      let actual = Hashtbl.find produced (Json.string (field "case_id" literal)) in
      require (Json.equal actual (field "expected_behavior" literal)) "Independent literal producer output differs") literals;
  List.iter (fun case ->
      let code = Json.string (field "expected_code" case) in
      match Json.string (field "expected_stage" case) with
      | "request" -> rejected code (fun () -> Domain.Build_request.of_json (field "request" case))
      | "lowering" ->
          let authority = Domain.Build_request.of_json (field "request" case) in
          rejected code (fun () -> Lowering.lower authority)
      | _ -> failwith "Unknown lowering rejection stage") rejections;
  Printf.printf "lowering corpus: %d exact productions, %d intended failures, 6 independent literals, all 42 operations passed\n"
    (List.length cases) (List.length rejections)
let () = match Array.to_list Sys.argv with
  | [_] -> unit_tests ()
  | [_; corpus] -> corpus_tests corpus
  | _ -> failwith "usage: test_lowering.exe [<absolute-lowering-corpus.json>]"
