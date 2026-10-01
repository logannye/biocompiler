open Bioc_wire
module A = Bioc_domain.Construction_artifact
module S = Bioc_domain.Molecule_set
let require value message = if not value then failwith message
let str value = Json.String value
let obj value = Json.Object value
let field key value = Json.field key (Json.object_fields value)
let rejected label code run = match run () with
  | _ -> failwith (label ^ ": intended failure accepted")
  | exception Diagnostic.Error error -> require (error.code = code) (label ^ ": expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message)
let empty = Json.parse {|{"schema_version":"biocompiler.circuit_construction_candidate.v0.1","request_fingerprint":"0000000000000000000000000000000000000000000000000000000000000000","values":[],"bundle":null,"missing_members":[],"diagnostics":[],"experimental_amounts":[]}|}
let make ?(values = []) ?(bundle = None) ?(missing_members = []) ?(diagnostics = []) ?(experimental_amounts = []) () =
  A.make ~request_fingerprint:(String.make 64 '0') ~values ~bundle ~missing_members ~diagnostics ~experimental_amounts
let literals () =
  let value = make () in
  require (Json.equal (A.to_json value) empty && A.bundle value = None && A.values value = []) "Independent empty unchecked candidate changed";
  let unresolved = make ~missing_members:["z";"a"] ~diagnostics:["unresolved:z";"unresolved:a"] () in
  require (A.missing_members unresolved = ["a";"z"] && A.diagnostics unresolved = ["unresolved:a";"unresolved:z"]) "Candidate uncertainty inventory order differs";
  let maximum = make ~missing_members:(List.init 256 string_of_int) ~diagnostics:(List.init 1024 string_of_int) () in
  require (List.length (A.missing_members maximum) = 256 && List.length (A.diagnostics maximum) = 1024) "Exact text inventory limits rejected";
  rejected "missing-member limit" "molecular_resource_limit" (fun () -> make ~missing_members:(List.init 257 string_of_int) ());
  rejected "diagnostic limit" "molecular_resource_limit" (fun () -> make ~diagnostics:(List.init 1025 string_of_int) ());
  rejected "diagnostic duplicates" "invalid_construction_artifact" (fun () -> make ~diagnostics:["same";"same"] ());
  let rec missing = "x" :: missing in
  rejected "cyclic missing members" "molecular_resource_limit" (fun () -> make ~missing_members:missing ());
  rejected "cyclic diagnostics" "molecular_resource_limit" (fun () -> make ~diagnostics:missing ());
  let rec raw = Json.Array [raw] in
  rejected "raw candidate cycle" "molecular_cycle" (fun () -> A.of_json raw);
  rejected "duplicate native key" "duplicate_key" (fun () -> A.of_json (obj (("bundle",Json.Null) :: Json.object_fields empty)));
  rejected "native nonfinite" "nonfinite_number" (fun () -> A.of_json (obj (("extra",Json.Float infinity) :: Json.object_fields empty)));
  print_endline "construction artifacts: independent missing-candidate literal, exact text inventories and native cycle guards passed"
let inspect kind = match kind with
  | "derived" -> (fun value -> A.Derived_segment.of_json value |> A.Derived_segment.to_json)
  | "consumed" -> (fun value -> A.Consumed_segment.of_json value |> A.Consumed_segment.to_json)
  | "value" -> (fun value -> A.Value.of_json value |> A.Value.to_json)
  | "candidate" -> (fun value -> A.of_json value |> A.to_json)
  | _ -> failwith "Unknown construction artifact family"
let rec replace_at value path replacement = match path with
  | [] -> (match replacement with Some value -> value | None -> failwith "Cannot remove artifact fixture root")
  | Json.String key :: tail ->
      let fields = Json.object_fields value in
      if tail = [] then obj (match replacement with
          | None -> require (List.mem_assoc key fields) "Missing fixture removal key"; List.remove_assoc key fields
          | Some value -> (key,value) :: List.remove_assoc key fields)
      else (
        require (List.mem_assoc key fields) "Missing fixture descent key";
        obj (List.map (fun (name,child) -> name,if name=key then replace_at child tail replacement else child) fields))
  | Json.Int index :: tail ->
      let index = Z.to_int index and values = Json.array value in
      require (index >= 0 && index < List.length values) "Fixture edit index outside array";
      Json.Array (List.mapi (fun current child -> if current=index then
        (if tail=[] && replacement=None then None else Some (replace_at child tail replacement)) else Some child) values |> List.filter_map Fun.id)
  | _ -> failwith "Invalid artifact fixture patch path"
let edits document edits = List.fold_left (fun value edit ->
    let replacement = match Json.string (field "op" edit) with "set" -> Some (field "value" edit)
      | "remove" -> None | _ -> failwith "Unknown artifact fixture edit operation" in
    replace_at value (Json.array (field "path" edit)) replacement) document (Json.array edits)
let read_json path =
  require (not (Filename.is_relative path)) "Required artifact corpus path must be absolute";
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size = in_channel_length channel in require (size <= Limits.max_request_bytes) "Artifact corpus read bound";
    Json.parse (really_input_string channel size))
let retained path =
  let corpus = read_json path in
  require (field "schema_version" corpus = str "biocompiler.construction_artifacts_conformance.v1") "Unknown artifact corpus schema";
  let records = Json.array (field "records" corpus) and failures = Json.array (field "rejections" corpus) in
  require (List.length records = 36 && List.length failures = 70) "Missing artifact cases";
  let ids = List.map (fun item -> Json.string (field "id" item)) (records @ failures) in
  require (List.length ids = List.length (List.sort_uniq String.compare ids)) "Duplicate artifact fixture identity";
  let inventory keys items = List.sort (fun left right -> String.compare (Json.string (field "id" left)) (Json.string (field "id" right))) items
      |> List.map (fun item -> Json.Array (List.map (fun key -> field key item) keys)) |> fun items -> Json.Array items in
  let inventory = obj ["records",inventory ["id";"kind"] records;"rejections",inventory ["id";"kind";"expected_code"] failures] in
  let expected_inventory = "f5af9ec95ba99e66827a374fa46b11dadc20104dba839374eedde4dca286ece4" in
  require (Canonical.fingerprint inventory = expected_inventory && field "inventory_sha256" corpus = str expected_inventory) "Artifact inventory or intended diagnostics changed";
  List.iter (fun (key,expected) -> require (Canonical.fingerprint (field key corpus) = expected) (key ^ ": independent artifact expectations changed"))
    ["literal_expectations","eb0bc157ec497c183cb98fa6b169c1b31b317c3c98a99c8771d7f278eae36fdb";
     "runtime_cases","2cd4fea219e92734cd2824a6218174fe420a6ecd6a824decbf510465a923b7bb";
     "relations","2c1bfe7a50f011f8c3c02d792d689116e7608acc0a5d47d3802885c162116bd5"];
  let documents = field "documents" corpus in
  List.iter (fun (key,value) -> require (Canonical.fingerprint value = key) "Retained artifact document pin changed") (Json.object_fields documents);
  let doc item = field (Json.string (field "document_id" item)) documents in
  let by_id identity = List.find (fun item -> field "id" item = str identity) records in
  List.iter (fun item ->
      let label = Json.string (field "id" item) and kind = Json.string (field "kind" item) in
      let actual = inspect kind (edits (doc item) (field "edits" item)) in
      require (Json.equal actual (doc item)) (label ^ ": full unchecked artifact changed");
      require (str (Canonical.fingerprint actual) = field "fingerprint" item) (label ^ ": artifact fingerprint changed");
      require (Json.equal actual (inspect kind actual)) (label ^ ": repeated import changed authority")) records;
  List.iter (fun item ->
      let label = Json.string (field "id" item) and raw = edits (doc item) (field "edits" item) in
      if List.mem label ["candidate/amount_without_bundle";"candidate/duplicate_amount_identity";"candidate/amount_stale";"candidate/amount_missing_subject";"candidate/amount_wrong_role";"candidate/amount_missing_role";"candidate/alias_preparation"] then (
        List.iter (fun raw -> ignore (S.Amount.of_json raw)) (Json.array (field "experimental_amounts" raw));
        match field "bundle" raw with Json.Null -> () | raw -> ignore (S.of_json raw));
      rejected label (Json.string (field "expected_code" item)) (fun () -> inspect (Json.string (field "kind" item)) raw)) failures;
  List.iter (fun item ->
      let source = by_id (Json.string (field "id" item)) in
      require (Json.equal (inspect (Json.string (field "kind" source)) (doc source)) (field "normalized" item)) "Independent complete artifact literal changed")
    (Json.array (field "literal_expectations" corpus));
  List.iter (fun relation ->
      let left = by_id (Json.string (field "left" relation)) and right = by_id (Json.string (field "right" relation)) in
      require ((field "fingerprint" left = field "fingerprint" right) = Json.boolean (field "equal" relation)) "Ordered correspondence or normalized inventory identity changed")
    (Json.array (field "relations" corpus));
  let template = doc (by_id "literal/value") in
  List.iter (fun item ->
      let lengths = Json.array (field "lengths" item) |> List.map (fun value -> Json.integer value |> Z.to_int) in
      let values = List.mapi (fun index length ->
          let set path replacement raw = replace_at raw path (Some replacement) in
          template |> set [str "id"] (str ("value_" ^ string_of_int index))
          |> set [str "space";str "id"] (str ("space_" ^ string_of_int index))
          |> set [str "space";str "length"] (Json.int length)
          |> set [str "sequence"] (str (String.make length 'A'))
          |> set [str "segments";Json.int 0;str "destination";str "end"] (Json.int length)
          |> set [str "segments";Json.int 0;str "source_path";str "spans";Json.int 0;str "end"] (Json.int length)
          |> A.Value.of_json) lengths in
      match field "expected_code" item with
      | Json.Null -> let actual = make ~values () in require (str (A.fingerprint actual) = field "fingerprint" item) "Exact cumulative boundary artifact changed"
      | code -> rejected (Json.string (field "id" item)) (Json.string code) (fun () -> make ~values ()))
    (Json.array (field "runtime_cases" corpus));
  let value = A.Value.of_json template and amount = A.of_json (doc (by_id "candidate/amount")) |> A.experimental_amounts |> List.hd in
  let rec values = value :: values in
  let rec amounts = amount :: amounts in
  rejected "cyclic values" "molecular_resource_limit" (fun () -> make ~values ());
  rejected "cyclic amounts" "molecular_resource_limit" (fun () -> make ~experimental_amounts:amounts ());
  let rec segments = List.hd (A.Value.segments value) :: segments in
  rejected "cyclic derived segments" "molecular_resource_limit" (fun () -> A.Value.make ~id:"cycle" ~space:(A.Value.space value) ~sequence:(A.Value.sequence value)
      ~chemistry:(A.Value.chemistry value) ~features:[] ~segments ~step_id:"unchecked" ~sequence_extent:(A.Value.sequence_extent value) ~consumed:[]);
  Printf.printf "construction artifacts: %d complete records, %d intended failures, four independent literals, three original case-B candidates and exact cumulative boundaries passed\n" (List.length records) (List.length failures)
let () = match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_; path] -> literals (); retained path
  | _ -> failwith "Usage: test_construction_artifact.exe [<absolute-construction-artifacts-v1.json>]"
