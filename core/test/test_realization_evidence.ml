open Bioc_wire
open Bioc_domain
module E = Realization_evidence
module D = E.Dependency_snapshot
module C = E.Requirement_coverage
module R = E.Check_result
let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let set key value raw = obj ((key, value) :: List.remove_assoc key (Json.object_fields raw))
let rejected code action = match action () with
  | _ -> failwith ("Unexpected realization evidence success: " ^ code)
  | exception Diagnostic.Error error -> require (error.code = code)
      ("Expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message)
let hash_keys = ["behavior"; "behavior_artifact"; "contract"; "domain"; "target"; "mechanism"; "observation_map"; "history"]
let dependencies () =
  D.make_values (obj (List.mapi (fun index key -> key, str (String.make 64 (Char.chr (48 + index)))) hash_keys @ [
    "horizon", obj ["until", Json.Null; "effective", Json.Float (-0.)];
    "checker", str "checker.é"; "model_runner", str "runner😀"; "reference_evaluator", str "reference";
    "settings", obj ["threshold", Json.int 1; "float", Json.Float 1.; "zero", Json.Float (-0.);
      "escaped", str "\127\b\t\n\012\r\\\""]]))
let interval () = Measurement_contract.Interval.of_json (Json.parse
  {|{"kind":"interval","lower":{"canonical_value":0,"kind":"scalar","type":{"arguments":[],"dimensions":{},"kind":"scalar","name":"Level"},"unit":"1","value":0},"type":{"arguments":[{"arguments":[],"dimensions":{},"kind":"scalar","name":"Level"}],"dimensions":{},"kind":"interval","name":"Interval[Level]"},"upper":{"canonical_value":1.0,"kind":"scalar","type":{"arguments":[],"dimensions":{},"kind":"scalar","name":"Level"},"unit":"1","value":1.0}}|})
let () =
  (* These literals were obtained independently from the unchanged Python
     evidence classes, including SourceLocation and typed Interval decoding. *)
  let deps = dependencies () in
  require (D.fingerprint deps = "9c423f7a459de121d043e0134d5ae1e37eb5f3d8e80c798b76adfe8d1d2f0300") "Legacy dependency identity changed";
  require (D.canonical_size deps = 860) "Dependency ASCII size changed";
  let coverage = C.make ~requirement_id:"reqé" ~activation_deadlines_checked:(Z.of_int 2)
      ~inactive_deadlines_checked:Z.one ~cancelled_episode_count:(Z.of_int 3) () in
  let passed = R.make ~outcome:E.Pass ~dependencies:deps ~checked_requirement_ids:["reqé"] ~coverage:[coverage] () in
  require (R.fingerprint passed = "8e9187ae65f3ca76c7b1724625ff80a0d206e499add8dbed732402568d1b7597") "Full PASS identity changed";
  require (R.canonical_size passed = 1430 && R.passed passed && R.exercised_requirement_ids passed = ["reqé"])
    "PASS coverage or complete artifact size changed";
  let source = {Behavior.file = "café.py"; line = Z.of_int 7; function_name = "f😀"} in
  let diagnostic = E.Check_diagnostic.make ~code:"mismatch" ~message:"observed μ😀" ~requirement_id:"reqé" ~node_id:"node" ~source () in
  let counterexample = E.Counterexample.make ~requirement_id:"reqé" ~time:(Runtime_number.Real 2.) ~contact_id:"contacté"
      ~state:E.Inactive ~range:(interval ()) ~actual:(Runtime_number.Real (-0.)) ~rule_id:"rule" ~specification_id:"spec" ~source () in
  let failed = R.make ~outcome:E.Fail ~dependencies:deps ~checked_requirement_ids:["reqé"]
      ~diagnostics:[diagnostic] ~counterexamples:[counterexample] ~coverage:[coverage] () in
  require (R.fingerprint failed = "121a0f8ac9952098c7b2741def5b873207b3810450e3e16fb75e88ab5a389c80") "Complete failure identity changed";
  require (R.canonical_size failed = 2286 && not (R.passed failed)) "FAIL structural state changed";
  List.iter (fun (indent, bytes, hash) ->
    let text = R.to_json_text ~indent failed in
    require (String.length text = bytes && Canonical.sha256 text = hash) "Legacy text serialization changed";
    require (R.fingerprint (R.of_json_text text) = R.fingerprint failed) "Text roundtrip lost complete evidence")
    [None, 2437, "f95e6bfc06672b4190aebd93f8037d0dbd7edff630df54afd75f5d4a9f2612d6";
     Some 0, 2481, "cf43f1ccb74775c5f0b3759858142c9c9f9cdb8508a60a1b4d29a5d4e26e0e30";
     Some 2, 3309, "d643760c679f3cabfbce426def7b0308d8734bcd2ed4065e1e6b5e5d7a9508d3"];
  let unicode = obj ["\244\143\191\191", str "\127\194\128é😀\226\128\168";
    "a", arr [Json.Float (-0.); Json.int 1; Json.Float 1.]] in
  require (Legacy_ascii.encode unicode = {|{"a":[-0.0,1,1.0],"\udbff\udfff":"\u007f\u0080\u00e9\ud83d\ude00\u2028"}|})
    "ASCII scalar escaping, signed zero or numeric type was lost";
  require (Canonical.encode (str "é") = "\"é\"" && Legacy_ascii.encode (str "é") = {|"\u00e9"|}) "Default canonical profile changed";
  require (R.is_fresh failed deps && E.Freshness_report.status (R.freshness failed deps) = "fresh") "Identical dependencies became stale";
  (* Every dependency is authoritative; canonical type and sign changes count. *)
  List.iter (fun key ->
    let replacement = if List.mem key hash_keys then str (String.make 64 'f')
      else if key = "horizon" then obj ["until", Json.Null; "effective", Json.Float 0.]
      else if key = "settings" then set "threshold" (Json.Float 1.) (get "settings" (D.to_json deps))
      else str "updated" in
    let current = D.of_json (set key replacement (D.to_json deps)) in
    require (D.changed deps current = [key]) ("Missing freshness dependency: " ^ key);
    require (not (R.is_fresh failed current) && E.Freshness_report.status (R.freshness failed current) = "stale") "Stale evidence became fresh")
    (hash_keys @ ["horizon"; "settings"; "checker"; "model_runner"; "reference_evaluator"]);
  let changed = D.to_json deps |> set "settings" (obj ["different", Json.Bool true]) |> set "checker" (str "new") |> D.of_json in
  require (D.changed deps changed = ["checker"; "settings"]) "Freshness differences are not sorted";
  let report = E.Freshness_report.make ["z"; "a"; "z"] in
  require (E.Freshness_report.changed_dependencies (E.Freshness_report.of_json (E.Freshness_report.to_json report)) = ["z"; "a"; "z"])
    "Freshness construction reordered or deduplicated supplied changes";
  List.iter (fun outcome ->
    let result = R.make ~outcome ~dependencies:deps ~checked_requirement_ids:[] () in
    require (not (R.passed result) && R.exercised_requirement_ids result = []) "Non-PASS result gained exercised requirements")
    [E.Fail; E.Unknown; E.Unsupported];
  let raw = R.to_json passed in
  List.iter (fun (key, value) -> rejected "realization_evidence" (fun () -> R.of_json (set key value raw)))
    ["coverage", arr []; "checked_requirement_ids", arr []; "checked_requirement_ids", arr [str "reqé"; str "reqé"];
     "diagnostics", arr [E.Check_diagnostic.to_json diagnostic]; "counterexamples", arr [E.Counterexample.to_json counterexample];
     "evidence_kind", str "empirical"; "claim_scope", str "universal"];
  List.iter (fun (key, value) ->
    let invalid = set key value (C.to_json coverage) in
    rejected "realization_evidence" (fun () -> R.of_json (set "coverage" (arr [invalid]) raw)))
    ["activation_deadlines_checked", Json.int 0; "inactive_deadlines_checked", Json.int 0;
     "incomplete_episode_count", Json.int 1; "activation_deadlines_checked", Json.Float 2.;
     "activation_deadlines_checked", Json.Bool true; "cancelled_episode_count", Json.int (-1)];
  rejected "realization_evidence" (fun () -> R.make ~outcome:E.Fail ~dependencies:deps ~checked_requirement_ids:["other"] ~counterexamples:[counterexample] ());
  rejected "realization_evidence" (fun () -> R.make ~outcome:E.Unknown ~dependencies:deps ~checked_requirement_ids:["other"] ~diagnostics:[diagnostic] ());
  rejected "realization_evidence" (fun () -> R.make ~outcome:E.Fail ~dependencies:deps ~checked_requirement_ids:["reqé"] ~coverage:[coverage; coverage] ());
  rejected "realization_evidence" (fun () -> R.make ~outcome:E.Fail ~dependencies:deps ~checked_requirement_ids:[] ~coverage:[coverage] ());
  let partial = C.make ~requirement_id:"reqé" ~activation_deadlines_checked:Z.one ~inactive_deadlines_checked:Z.one ~incomplete_episode_count:Z.one () in
  let incomplete = R.make ~outcome:E.Unknown ~dependencies:deps ~checked_requirement_ids:["reqé"] ~coverage:[partial] () in
  require (R.exercised_requirement_ids incomplete = ["reqé"]) "Exercise property silently became acceptance";
  rejected "missing_field" (fun () -> R.of_json (obj (List.remove_assoc "coverage" (Json.object_fields raw))));
  rejected "unknown_field" (fun () -> R.of_json (set "approved" (Json.Bool true) raw));
  rejected "unsupported_schema" (fun () -> R.of_json (set "schema_version" (str "other") raw));
  rejected "duplicate_key" (fun () -> R.of_json (obj (("outcome", str "pass") :: Json.object_fields raw)));
  rejected "invalid_source" (fun () -> E.Check_diagnostic.make ~code:"x" ~message:"m" ~source:{source with line = Z.zero} ());
  List.iter (fun invalid -> rejected "realization_evidence" (fun () -> E.Counterexample.of_json
      (set "time" invalid (E.Counterexample.to_json counterexample)))) [Json.int (-1); Json.Bool true; Json.Int (Z.pow (Z.of_int 10) 400)];
  rejected "realization_evidence" (fun () -> E.Counterexample.of_json (set "actual" (Json.Bool false) (E.Counterexample.to_json counterexample)));
  rejected "nonfinite_number" (fun () -> E.Counterexample.make ~requirement_id:"r" ~time:(Runtime_number.Real nan)
      ~state:E.Active ~range:(interval ()) ~rule_id:"rule" ~specification_id:"spec" ());
  let missing_output = E.Counterexample.make ~requirement_id:"reqé" ~time:Runtime_number.zero ~state:E.Active ~range:(interval ()) ~rule_id:"rule" ~specification_id:"spec" () in
  require (E.Counterexample.actual missing_output = None) "Missing output lost null identity";
  let enormous_count = Z.pow (Z.of_int 10) 400 in
  require (Z.equal (C.activation_deadlines_checked (C.make ~requirement_id:"r" ~activation_deadlines_checked:enormous_count ())) enormous_count)
    "Finite-integer coverage incorrectly required a float conversion";
  (* Native boundary differences remain explicit: Python evidence constructors
     allow lone surrogates, while the wire and all native records reject them. *)
  rejected "invalid_utf8" (fun () -> E.Check_diagnostic.make ~code:"x" ~message:"invalid\237\160\128" ());
  rejected "invalid_json" (fun () -> Json.parse {|"\ud800"|});
  let rec cycle = Json.Object ["child", cycle] in
  rejected "realization_evidence_cycle" (fun () -> D.of_json (set "settings" cycle (D.to_json deps)));
  rejected "legacy_ascii_cycle" (fun () -> Legacy_ascii.encode cycle);
  let rec spine = "x" :: spine in
  rejected "realization_evidence_limit" (fun () -> E.Freshness_report.make spine);
  let rec diagnostics = diagnostic :: diagnostics in
  rejected "realization_evidence_limit" (fun () -> R.make ~outcome:E.Fail ~dependencies:deps ~checked_requirement_ids:["reqé"] ~diagnostics ());
  let rec nested depth = if depth = 0 then Json.Null else arr [nested (depth - 1)] in
  rejected "legacy_ascii_limit" (fun () -> Legacy_ascii.encode (nested (Limits.max_depth + 1)));
  rejected "legacy_ascii_limit" (fun () -> Legacy_ascii.encode (arr (List.init Limits.max_json_nodes (fun _ -> Json.Null))));
  rejected "legacy_ascii_limit" (fun () -> Legacy_ascii.encode (Json.Int (Z.pow (Z.of_int 10) Limits.max_number_chars)));
  rejected "realization_evidence_limit" (fun () -> E.Check_diagnostic.make ~code:"x" ~message:(String.make (Limits.max_string_bytes + 1) 'x') ());
  let unicode_large = String.init Limits.max_string_bytes (fun index -> if index mod 2 = 0 then '\195' else '\169') in
  let large = E.Check_diagnostic.make ~code:"x" ~message:unicode_large () in
  rejected "realization_evidence_limit" (fun () -> R.make ~outcome:E.Fail ~dependencies:deps ~checked_requirement_ids:[] ~diagnostics:[large; large; large] ());
  rejected "legacy_ascii_limit" (fun () -> Legacy_ascii.encode (arr [str unicode_large; str unicode_large; str unicode_large]));
  print_endline "realization evidence: six complete records, independent legacy ASCII identities, all dependency freshness, PASS invariants and cumulative native boundaries checked"
