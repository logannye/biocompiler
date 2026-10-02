open Bioc_wire
module S = Bioc_domain.Source_execution_manifest
module H = Bioc_domain.Human_request
module C = Bioc_checker.Source_check
let require condition message = if not condition then failwith message
let str value = Json.String value
let field key value = Json.field key (Json.object_fields value)
let result_json (result : C.result) = Json.Object ["failures", Json.Array (List.map str result.failures); "unresolved", Json.Array (List.map str result.unresolved)]
let rec change raw path replacement = match path, raw with
  | [], _ -> (match replacement with Some value -> value | None -> failwith "Cannot delete whole source authority")
  | Json.String key :: rest, Json.Object fields ->
      let present = List.mem_assoc key fields in
      if not present then (
        require (rest = [] && Option.is_some replacement) "Mutation path missing";
        Json.Object ((key, Option.get replacement) :: fields))
      else Json.Object (List.filter_map (fun (name, value) -> if name <> key then Some (name,value)
          else if rest = [] && replacement = None then None
          else Some (name, change value rest replacement)) fields)
  | Json.Int raw_index :: rest, Json.Array values ->
      let index = Z.to_int raw_index in require (index >= 0 && index < List.length values) "Mutation index missing";
      Json.Array (List.filter_map (fun (position,value) -> if position <> index then Some value
          else if rest = [] && replacement = None then None else Some (change value rest replacement)) (List.mapi (fun i value -> i,value) values))
  | _ -> failwith "Invalid mutation path"
let edits raw edits = List.fold_left (fun raw edit ->
    let fields = Json.object_fields edit in
    let replacement = if List.assoc_opt "delete" fields = Some (Json.Bool true) then None else Some (Json.field "value" fields) in
    change raw (Json.array (Json.field "path" fields)) replacement) raw edits
let inventory corpus = Canonical.fingerprint (Json.Object (List.map (fun key -> key,field key corpus)
    ["records";"rejections";"checks";"literal_expectations";"compatibility"]))
let retained path =
  require (not (Filename.is_relative path)) "Source checker corpus needs absolute path";
  let channel = open_in_bin path in
  let corpus = Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
      let size = in_channel_length channel in require (size <= Limits.max_request_bytes) "Source checker corpus too large";
      Json.parse (really_input_string channel size)) in
  require (field "schema_version" corpus = str "biocompiler.source_manifest_conformance.v1") "Unknown source checker corpus";
  let digest = "ba237e1adcbcb6e1853edd138f06edb7aaa1d729cfb2b31d61d8127d03d11d32" in
  require (inventory corpus = digest && field "inventory_sha256" corpus = str digest) "Source checker full inventory changed";
  let documents = Json.object_fields (field "documents" corpus) and checks = Json.array (field "checks" corpus) in
  require (List.length documents = 49 && List.length checks = 35) "Incomplete source checker census";
  List.iter (fun (identity, raw) -> require (Canonical.fingerprint raw = identity) "Substituted source document") documents;
  let document key = Json.field (Json.string key) documents in
  let mutations = ref 0 and exceptions = ref 0 in
  List.iter (fun case ->
      let id = Json.string (field "id" case) in
      let authority = document (field "authority" case) in
      let original = document (field "manifest" case) in
      let changes = Json.array (field "edits" case) in
      let raw = edits original changes in
      if changes <> [] then (incr mutations; require (not (Json.equal raw original)) (id ^ ": mutation is no-op"));
      let candidate = S.of_json raw and source = H.of_json authority in
      require (S.fingerprint candidate = Json.string (field "mutated_fingerprint" case)) (id ^ ": candidate identity differs");
      let before = Canonical.fingerprint authority in
      let expected = field "expected" case in
      let actual = C.check ~expected_source:source ~manifest:candidate |> result_json in
      require (Json.equal expected actual) (id ^ ": independent typed check differs: " ^ Canonical.encode actual);
      require (Json.equal expected (C.check_json ~expected_source:authority ~manifest:raw |> result_json)) (id ^ ": serialized check differs");
      require (Canonical.fingerprint authority = before && S.fingerprint candidate = Json.string (field "mutated_fingerprint" case)) (id ^ ": mutated authority");
      if not (Json.equal expected (field "legacy_expected" case)) then (
        incr exceptions; require (List.mem id ["mutation/behavior_identity"; "mutation/source_authority"]) "Unreviewed semantic diagnostic exception";
        let expected_failures = if id = "mutation/behavior_identity" then ["source_behavior:lowering_source_identity"]
          else ["source_authority"; "source_manifest_ledger"; "source_behavior:lowering_source_identity"] in
        require (field "failures" expected = Json.Array (List.map str expected_failures)) "Native lowering exception changed")) checks;
  require (!mutations = 17 && !exceptions = 2) "Source mutation or compatibility census changed";
  let find id = List.find (fun item -> field "id" item = str id) checks in
  let check_case id failures unresolved =
    let case = find id in
    let result = C.check_json ~expected_source:(document (field "authority" case)) ~manifest:(document (field "manifest" case)) in
    require (result.failures = failures && result.unresolved = unresolved) (id ^ ": independent literal result differs") in
  check_case "literal/unavailable" [] ["source_execution_unavailable"];
  check_case "case_b/base" [] [];
  check_case "architecture/D" [] [];
  check_case "empty_role" [] [];
  let case = find "empty_role" in
  let authority = document (field "authority" case) in
  let intent = field "intent" authority in
  let node = List.hd (Json.array (field "nodes" intent)) in
  let nodes = List.init 1025 (fun index -> change node [str "id"] (Some (str ("role_" ^ string_of_int index)))) in
  let large = change authority [str "intent";str "nodes"] (Some (Json.Array nodes)) in
  let large = change large [str "intent";str "roots"] (Some (Json.Array (List.map (field "id") nodes))) in
  (match C.check_json ~expected_source:large ~manifest:(document (field "manifest" case)) with
   | _ -> failwith "Accepted over-budget native source reconstruction"
   | exception Diagnostic.Error error -> require (error.code = "source_manifest_limit") "Wrong native source work-limit rejection");
  Printf.printf "source checker: %d exact source pairs, %d meaningful candidate mutations, two explicit diagnostic exceptions and five independent literals passed\n" (List.length checks) !mutations
let () = match Array.to_list Sys.argv with
  | [_] -> require (C.checker_version = "biocompiler.ocaml.source_manifest_check.v0.1") "Source checker identity differs"
  | [_;path] -> retained path
  | _ -> failwith "Usage: test_source_check.exe [<absolute-corpus.json>]"
