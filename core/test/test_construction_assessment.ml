open Bioc_wire
module E = Bioc_domain.Construction_assessment
module M = Bioc_domain.Molecular_record
let require condition message = if not condition then failwith message
let rejected code action = match action () with _ -> failwith "Accepted invalid historical construction assessment"
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code = code) ("Expected " ^ code ^ ", got " ^ diagnostic.code)
let literal outcome complete diagnostics = E.make ~request_fingerprint:(String.make 64 'a') ~candidate_fingerprint:(String.make 64 'b')
    ~reconstructed_fingerprint:(String.make 64 'c') ~outcome ~complete ~diagnostics
let inventory_literals () =
  let module I = E.Inventory in
  require (E.max_diagnostics = 4096 && E.max_diagnostic_bytes = 32_768 && E.max_retained_diagnostic_bytes = 1_000_000)
    "Fresh reporting limits changed";
  let inventory = I.create () in
  I.add inventory "unknown:z"; I.add inventory "fail:a"; I.add inventory "unknown:z";
  require (I.elements inventory = ["fail:a";"unknown:z"]) "Inventory did not sort and deduplicate text";
  List.iter (fun text -> rejected "invalid_construction_check" (fun () -> I.add inventory text))
    ["no-prefix";"pass:accepted";"warning:unknown";":empty"];
  rejected "invalid_utf8" (fun () -> I.add inventory "fail:\255");
  let count = I.create () in
  for index = 0 to E.max_diagnostics - 2 do I.add count (Printf.sprintf "unknown:retained:%04d" index) done;
  I.add count "unknown:retained:0000";
  require (List.length (I.elements count) = E.max_diagnostics - 1) "A duplicate consumed the reserved omission slot";
  I.add count "unknown:omitted"; I.add count "unsupported:omitted"; I.add count "fail:omitted";
  I.add count "unknown:later";
  let values = I.elements count in
  require (List.length values = E.max_diagnostics && List.hd values = "fail:assessment_diagnostic_budget")
    "Omitted failure severity disappeared at the count boundary";
  require (List.mem "unknown:retained:4094" values && not (List.mem "fail:omitted" values))
    "Count limit replaced previously retained text";
  ignore (literal E.Fail false values);
  let entry = I.create () in
  let maximum = "unknown:" ^ String.concat "" (List.init ((E.max_diagnostic_bytes - 8) / 2) (fun _ -> "é")) in
  require (String.length maximum = E.max_diagnostic_bytes) "UTF-8 diagnostic boundary literal is wrong";
  I.add entry maximum; I.add entry ("fail:" ^ String.make (E.max_diagnostic_bytes - 4) 'x');
  require (I.elements entry = ["fail:assessment_diagnostic_budget";maximum]) "Per-entry UTF-8 bytes or omitted severity differ";
  let bytes = I.create () in
  let retained = List.init 31 (fun index ->
      let prefix = Printf.sprintf "unknown:%02d:" index in prefix ^ String.make (32_000 - String.length prefix) 'x') in
  List.iter (I.add bytes) retained;
  let exact = "unknown:" ^ String.make 7992 'x' in I.add bytes exact;
  require (List.length (I.elements bytes) = 32) "Exact one-million-byte diagnostic inventory was rejected";
  I.add bytes exact; I.add bytes "fail:overflow";
  let values = I.elements bytes in
  require (List.length values = 33 && List.mem "fail:assessment_diagnostic_budget" values && List.mem exact values)
    "Aggregate byte omission lost prior entries or failure severity";
  ignore (literal E.Fail false values)
let literals () =
  inventory_literals ();
  let report = literal E.Pass true [] in
  require (E.passed report && E.complete report) "Historical report codec lost Boolean field";
  require (E.fingerprint report = E.fingerprint (E.of_json (E.to_json report))) "Assessment exact roundtrip differs";
  let failed = literal E.Fail false ["fail:z";"fail:a"] in
  require (E.diagnostics failed = ["fail:a";"fail:z"]) "Historical diagnostic inventory not canonical";
  ignore (literal E.Unknown false []); ignore (literal E.Unsupported false []);
  rejected "invalid_construction_assessment" (fun () -> literal E.Pass false []);
  rejected "invalid_construction_assessment" (fun () -> literal E.Pass true ["fail:forged"]);
  rejected "invalid_construction_assessment" (fun () -> literal E.Fail false ["fail:a";"fail:a"]);
  let rec diagnostics = "fail:cycle" :: diagnostics in
  rejected "molecular_resource_limit" (fun () -> literal E.Fail false diagnostics);
  let maximum = "fail:" ^ String.make (E.max_diagnostic_bytes - 5) 'x' in
  ignore (literal E.Fail false [maximum]);
  rejected "invalid_molecular_text" (fun () -> literal E.Fail false [maximum ^ "x"]);
  rejected "molecular_resource_limit" (fun () -> literal E.Fail false (List.init E.max_diagnostics (fun index -> string_of_int index ^ String.make 2000 'x')));
  let fields = Json.object_fields (E.to_json report) in
  List.iter (fun (key,_) -> rejected "missing_field" (fun () -> E.of_json (Json.Object (List.remove_assoc key fields)))) fields;
  List.iter (fun key -> rejected "invalid_construction_assessment" (fun () -> E.of_json (Json.Object ((key,Json.String "changed") :: List.remove_assoc key fields))))
    ["checker_version";"capability_version";"construction_profile";"admission_policy";"claim_scope";"biological_function";"empirical_validation";"human_therapeutic_admission"];
  require (M.max_json_bytes = 4_000_000) "Unexpected assessment publication bound";
  print_endline "construction assessment: strict historical identity, all claims/outcomes, mandatory fields and bounded diagnostics passed"
let () = match Array.to_list Sys.argv with [_] -> literals () | _ -> failwith "usage: test_construction_assessment.exe"
