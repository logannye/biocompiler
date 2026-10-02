open Bioc_wire
open Bioc_domain
module E = Composition_evidence
module D = E.Link_diagnostic
module R = E.Resolved_dependency
module U = E.Resource_usage
module S = E.Dependencies
module T = E.Result
module N = Runtime_number
let checks = ref 0
let check condition message = incr checks; if not condition then failwith message
let reject code run =
  incr checks;
  match run () with
  | _ -> failwith ("Composition evidence accepted invalid input: " ^ code)
  | exception Diagnostic.Error error ->
      if error.code <> code then failwith ("Expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message)
let str value = Json.String value
let obj values = Json.Object values
let arr values = Json.Array values
let get key value = Json.field key (Json.object_fields value)
let set key item value = obj ((key, item) :: List.remove_assoc key (Json.object_fields value))
let remove key value = obj (List.remove_assoc key (Json.object_fields value))
let hash character = String.make 64 character
let pin kind id version character = Pinned_identity.make ~kind ~id ~version ~content_fingerprint:(hash character)
let model = pin Pinned_identity.Model "β" "2" 'e'
let evidence = pin Pinned_identity.Evidence "é" "1" 'f'
let dependencies = S.make ~request:(hash 'a') ~registry:(hash 'b') ~registry_lock:(hash 'c')
    ~target:(hash 'd') ~identities:[model; evidence]
let diagnostic = D.make ~status:D.Unknown ~code:"β:gap" ~message:"Declared\ncondition \"unresolved\""
    ~instance_id:"i.β" ~requirement_ids:["z"; "é"; "a"] ()
let resolved = R.make ~instance_id:"i.β" ~requirement_id:"dependency" ~provider_id:None
    ~provider_kind:R.Unresolved ~status:E.Pass
let usage = U.make ~pool_id:"pool" ~peak_reservation:(Some (N.Integer (Z.of_string "9007199254740993")))
    ~capacity:(Some (N.Real (-0.))) ~unit:"1" ~status:E.Fail
let complete () = T.make ~outcome:E.Unknown ~dependencies ~checked_requirement_ids:["z"; "é"; "a"]
    ~diagnostics:[diagnostic; diagnostic] ~resolved_dependencies:[resolved; resolved] ~resource_usage:[usage; usage] ()
let minimal ?(outcome = E.Pass) ?(diagnostics = []) ?(resolved_dependencies = []) ?(resource_usage = []) () =
  T.make ~outcome ~dependencies ~checked_requirement_ids:[] ~diagnostics ~resolved_dependencies ~resource_usage ()

let literals () =
  (* These complete UTF-8 identities and byte sizes were computed independently
     by the original four Python constructors, with no checker invocation. *)
  List.iter (fun (actual, expected) -> check (actual = expected) "Independent composition evidence fingerprint changed")
    [D.fingerprint diagnostic, "84197dfc57af8f0652f9c66a129632c69c7f23e1d16c8a54a75d57fd78ec26a0";
     R.fingerprint resolved, "c51c0c0fa45c91424f61c7a16d4138f2ff6bf0d0496531d97dd343ce256daaa8";
     U.fingerprint usage, "f041c6ebe4342d12471b8f0f2a0ae8f4233577696590a6c7d7fc24e459822df5";
     S.fingerprint dependencies, "c7f428424c7da89c417de1fd2e9ae61eef387cd46e5c2c5ab68c7798ce2adccb"];
  let result = complete () in
  check (T.fingerprint result = "8297422b6cfa10813e315fefe84d9d93a0d1a06ea353436996ea6e5b476b24fa")
    "Complete historical report identity changed";
  List.iter (fun (raw, actual, expected) ->
    check (actual = expected && actual = String.length (Canonical.encode raw)) "Cached exact UTF-8 byte count changed")
    [D.to_json diagnostic, D.canonical_size diagnostic, 137;
     R.to_json resolved, R.canonical_size resolved, 116;
     U.to_json usage, U.canonical_size usage, 97;
     S.to_json dependencies, S.canonical_size dependencies, 810;
     T.to_json result, T.canonical_size result, 1945];
  check (Json.equal (T.to_json (T.of_json (T.to_json result))) (T.to_json result)) "Report roundtrip lost authority";
  check (T.fingerprint (T.of_json_text (Canonical.encode (T.to_json result))) = T.fingerprint result)
    "Text import changed complete identity";
  check (D.requirement_ids diagnostic = ["z"; "é"; "a"] && T.checked_requirement_ids result = ["z"; "é"; "a"])
    "Requirement order was sorted";
  check (List.length (T.diagnostics result) = 2 && List.length (T.resolved_dependencies result) = 2
         && List.length (T.resource_usage result) = 2) "Historical duplicate report entries were discarded";
  check (List.map Pinned_identity.id (S.identities (T.dependencies result)) = ["β"; "é"])
    "Dependency pins were reordered";
  check (D.status diagnostic = D.Unknown && D.code diagnostic = "β:gap" && D.instance_id diagnostic = Some "i.β"
         && D.message diagnostic = "Declared\ncondition \"unresolved\"") "Diagnostic accessors lost declarations";
  check (R.instance_id resolved = "i.β" && R.requirement_id resolved = "dependency"
         && R.provider_id resolved = None && R.provider_kind resolved = R.Unresolved && R.status resolved = E.Pass)
    "Resolved dependency was silently interpreted as acceptance";
  check (U.peak_reservation usage = Some (N.Integer (Z.of_string "9007199254740993"))
         && U.unit usage = "1" && U.pool_id usage = "pool" && U.status usage = E.Fail)
    "Exact integral resource quantity lost precision";
  check (Canonical.encode (get "capacity" (U.to_json usage)) = "-0.0") "Signed real zero was normalized away"

let historical_scope () =
  List.iter (fun outcome ->
    let result = minimal ~outcome () in
    check (T.outcome result = outcome && T.passed result = (outcome = E.Pass)) "Historical outcome changed")
    [E.Pass; E.Fail; E.Unknown; E.Unsupported];
  List.iter (fun status ->
    let diagnostic = D.make ~status ~code:"declared" ~message:"Declared" () in
    check (D.status diagnostic = status && D.requirement_ids diagnostic = [] && D.instance_id diagnostic = None)
      "Diagnostic status/default changed") [D.Fail; D.Unknown; D.Unsupported];
  List.iter (fun provider_kind -> List.iter (fun status ->
    let value = R.make ~instance_id:"i" ~requirement_id:"r" ~provider_id:None ~provider_kind ~status in
    check (R.status value = status && R.provider_kind value = provider_kind) "Dependency category/status was strengthened")
    [E.Pass; E.Fail; E.Unknown; E.Unsupported]) [R.Encoded_here; R.Co_payload; R.Host; R.External; R.Unresolved];
  let pass_usage = U.make ~pool_id:"pool" ~peak_reservation:(Some (N.of_int 10))
      ~capacity:(Some (N.of_int 1)) ~unit:"declared" ~status:E.Pass in
  let result = minimal ~resolved_dependencies:[resolved] ~resource_usage:[pass_usage] () in
  check (T.passed result && T.checked_requirement_ids result = [])
    "Domain import improperly rechecked the historical peak/capacity or unresolved-provider declaration";
  let unknown_usage = U.make ~pool_id:"pool" ~peak_reservation:None ~capacity:None ~unit:"1" ~status:E.Unknown in
  check (U.peak_reservation unknown_usage = None && U.capacity unknown_usage = None)
    "Unknown resource quantities were converted to zero";
  let flipped = T.to_json (complete ()) |> set "diagnostics"
      (arr [D.to_json (D.make ~status:D.Fail ~code:"other" ~message:"Other" ()); D.to_json diagnostic]) |> T.of_json in
  check (List.map D.code (T.diagnostics flipped) = ["other"; "β:gap"] && T.fingerprint flipped <> T.fingerprint (complete ()))
    "Diagnostic order is part of full report identity";
  let reversed = S.to_json dependencies |> set "identities" (arr [Pinned_identity.to_json evidence; Pinned_identity.to_json model]) |> S.of_json in
  check (S.changed dependencies reversed = ["identities"] && S.fingerprint reversed <> S.fingerprint dependencies)
    "Ordered dependency identities were treated as a set"

let freshness () =
  let module C = Composition in
  let module G = Component_registry in
  let registry = G.make ~id:"fixture" ~version:"1" ~components:[] in
  (* This lock deliberately cannot resolve against the registry. Freshness is
     identity-only; independent linking must reject it in the checker layer. *)
  let lock = G.Lock.make ~registry_id:"unresolved" ~registry_version:"1" ~registry_fingerprint:(hash 'a')
      ~components:[] ~identities:[] in
  let component = G.Component_lock.make ~node_id:"node" ~component_id:"missing" ~version:"1" ~content_fingerprint:(hash 'b') in
  let instance = C.Instance.make ~id:"node" ~component ~required_domain:(Component_contract.Operating_domain.make []) () in
  let target_json = Json.parse {|{"schema_version":"biocompiler.target.v0.1","context_id":"fixture","context_version":"1","payload_format":"RNA","capabilities":[],"compartments":["abstract"],"resources":{}}|} in
  let target = Build_request.Target.of_json target_json in
  let request = C.make ~target ~registry_lock:lock ~instances:[instance] () in
  let deps = E.dependencies ~request ~registry in
  let result = T.make ~outcome:E.Pass ~dependencies:deps ~checked_requirement_ids:[] ~resolved_dependencies:[resolved] () in
  List.iter (fun (actual, expected) -> check (actual = expected) "Independent freshness fixture identity changed")
    [C.fingerprint request, "2fb7818ab657622fd1ec34eb0c51dd46704868248d3cbc5ef91f9e1753916a0a";
     G.fingerprint registry, "791ba4ab012619db96f1186d0c9e9b34d8031512ea57b3d1554ffce958471ff9";
     S.fingerprint deps, "8e5d7a34a8cedf961c966476ea0f44d25a1d3033da3340e3fb4e58893734bd67";
     T.fingerprint result, "77b6c6aece56fc275daeae333dcac3ea976554563120f4dbf8c1cc1858b6de6b"];
  check (T.is_fresh result ~request ~registry && Realization_evidence.Freshness_report.fresh (T.freshness result ~request ~registry))
    "Freshness performed linking or admission";
  let changed_registry = G.make ~id:"fixture" ~version:"2" ~components:[] in
  check (Realization_evidence.Freshness_report.changed_dependencies (T.freshness result ~request ~registry:changed_registry) = ["registry"])
    "Registry identity change was not isolated";
  let target = Build_request.Target.of_json (set "context_version" (str "2") target_json) in
  let changed_request = C.make ~target ~registry_lock:lock ~instances:[instance] () in
  check (Realization_evidence.Freshness_report.changed_dependencies (T.freshness result ~request:changed_request ~registry)
         = ["request"; "target"]) "Freshness did not bind complete original target authority";
  List.iter (fun key ->
    let changed = S.to_json deps |> set key (str (hash 'f')) |> S.of_json in
    check (S.changed deps changed = [key]) "Dependency change inventory is incomplete")
    ["request"; "registry"; "registry_lock"; "target"]

let invalid_records () =
  let raw = T.to_json (complete ()) in
  reject "missing_field" (fun () -> T.of_json (remove "diagnostics" raw));
  reject "unknown_field" (fun () -> T.of_json (set "hidden" Json.Null raw));
  List.iter (fun value -> reject "composition_evidence" (fun () -> T.of_json (set "schema_version" value raw))) [str "future"; Json.Null];
  List.iter (fun value -> reject "composition_evidence" (fun () -> T.of_json (set "outcome" value raw))) [str "error"; Json.Bool true; arr []];
  reject "composition_evidence" (fun () -> T.of_json (set "claim_scope" (str "Accepted biology") raw));
  List.iter (fun key -> reject "invalid_type" (fun () -> T.of_json (set key Json.Null raw)))
    ["diagnostics"; "resolved_dependencies"; "resource_usage"; "checked_requirement_ids"];
  reject "composition_evidence" (fun () -> T.of_json (set "checked_requirement_ids" (arr [str "same"; str "same"]) raw));
  reject "invalid_name" (fun () -> T.of_json (set "checked_requirement_ids" (arr [str "\194\160"]) raw));
  reject "composition_evidence" (fun () -> minimal ~diagnostics:[diagnostic] ());
  reject "composition_evidence" (fun () -> minimal ~resource_usage:[usage] ());
  let deps = S.to_json dependencies in
  List.iter (fun key -> reject "composition_evidence" (fun () -> S.of_json (set key (str "changed") deps))) ["checker"; "admission_policy"];
  List.iter (fun key -> List.iter (fun value -> reject "composition_evidence" (fun () -> S.of_json (set key value deps)))
      [str (String.make 64 'A'); str "short"; Json.Bool false]) ["request"; "registry"; "registry_lock"; "target"];
  reject "invalid_type" (fun () -> S.of_json (set "identities" Json.Null deps));
  reject "missing_field" (fun () -> S.of_json (set "identities" (arr [obj ["schema_version", str "unknown"]]) deps));
  let different_hash = pin Pinned_identity.Model "β" "2" 'a' in
  reject "composition_evidence" (fun () -> S.make ~request:(hash 'a') ~registry:(hash 'b') ~registry_lock:(hash 'c')
      ~target:(hash 'd') ~identities:[model; different_hash]);
  let d = D.to_json diagnostic in
  List.iter (fun value -> reject "composition_evidence" (fun () -> D.of_json (set "status" value d))) [str "pass"; arr []; Json.Null];
  reject "composition_evidence" (fun () -> D.make ~status:D.Fail ~code:"x" ~message:"m" ~requirement_ids:["a"; "a"] ());
  reject "invalid_name" (fun () -> D.make ~status:D.Fail ~code:"" ~message:"m" ());
  reject "invalid_type" (fun () -> D.of_json (set "instance_id" (Json.int 0) d));
  let r = R.to_json resolved in
  reject "composition_evidence" (fun () -> R.of_json (set "provider_kind" (str "future") r));
  reject "composition_evidence" (fun () -> R.of_json (set "status" (str "future") r));
  reject "invalid_name" (fun () -> R.of_json (set "provider_id" (str "\n") r));
  let u = U.to_json usage in
  List.iter (fun key -> List.iter (fun value -> reject "composition_evidence" (fun () -> U.of_json (set key value u)))
      [Json.Bool true; Json.int (-1); Json.Float (-0.1); str "1"; Json.Int (Z.pow (Z.of_int 10) 1000)])
    ["peak_reservation"; "capacity"];
  List.iter (fun value -> reject "composition_evidence" (fun () -> U.make ~pool_id:"p" ~peak_reservation:(Some value)
      ~capacity:None ~unit:"1" ~status:E.Unknown)) [N.Real nan; N.Real infinity; N.of_int (-1)];
  reject "nonfinite_number" (fun () -> U.of_json (set "capacity" (Json.Float infinity) u));
  (* Nested-record decoding precedes the enclosing dependency validation. *)
  let two_faults = raw |> set "dependencies" Json.Null |> set "diagnostics" (arr [set "status" (str "pass") d]) in
  reject "composition_evidence" (fun () -> T.of_json two_faults);
  reject "invalid_type" (fun () -> T.of_json (set "resource_usage" Json.Null two_faults))

let native_boundaries () =
  let rec cycle = Json.Array [cycle] in
  reject "composition_evidence_cycle" (fun () -> T.of_json cycle);
  let rec values = Json.Null :: values in
  reject "composition_evidence_limit" (fun () -> T.of_json (arr values));
  let rec fields = ("x", Json.Null) :: fields in
  reject "composition_evidence_limit" (fun () -> T.of_json (obj fields));
  let rec diagnostics = diagnostic :: diagnostics in
  reject "composition_evidence_limit" (fun () -> T.make ~outcome:E.Unknown ~dependencies ~checked_requirement_ids:[] ~diagnostics ());
  let rec identities = model :: identities in
  reject "composition_evidence_limit" (fun () -> S.make ~request:(hash 'a') ~registry:(hash 'b') ~registry_lock:(hash 'c')
      ~target:(hash 'd') ~identities);
  let rec ids = "same" :: ids in
  reject "composition_evidence_limit" (fun () -> D.make ~status:D.Unknown ~code:"c" ~message:"m" ~requirement_ids:ids ());
  let d = D.to_json diagnostic in
  reject "duplicate_key" (fun () -> D.of_json (obj (("code", str "different") :: Json.object_fields d)));
  reject "invalid_utf8" (fun () -> D.make ~status:D.Unknown ~code:"x" ~message:"\255" ());
  let nested = ref Json.Null in
  for _ = 1 to Limits.max_depth + 1 do nested := arr [!nested] done;
  reject "composition_evidence_limit" (fun () -> T.of_json !nested);
  let maximum = String.make Limits.max_string_bytes 'x' in
  let large = D.make ~status:D.Unknown ~code:"large" ~message:maximum () in
  check (String.length (D.message large) = Limits.max_string_bytes) "Exact native string boundary rejected";
  reject "composition_evidence_limit" (fun () -> D.make ~status:D.Unknown ~code:"large" ~message:(maximum ^ "x") ());
  let small = D.make ~status:D.Unknown ~code:"a" ~message:"b" () in
  let empty = T.make ~outcome:E.Unknown ~dependencies ~checked_requirement_ids:[] () in
  let exact_message_bytes = Limits.max_response_bytes - T.canonical_size empty
      - 8 * (D.canonical_size small - 1) - 7 in
  let last = exact_message_bytes - 7 * Limits.max_string_bytes in
  check (last > 0 && last <= Limits.max_string_bytes) "Bad independent exact-byte boundary fixture";
  let near = D.make ~status:D.Unknown ~code:"a" ~message:maximum () in
  let final = D.make ~status:D.Unknown ~code:"a" ~message:(String.make last 'x') () in
  let report = T.make ~outcome:E.Unknown ~dependencies ~checked_requirement_ids:[]
      ~diagnostics:(List.init 7 (fun _ -> near) @ [final]) () in
  check (T.canonical_size report = Limits.max_response_bytes) "Exact 32 MiB report boundary rejected or miscounted";
  let over = D.make ~status:D.Unknown ~code:"a" ~message:(String.make (last + 1) 'x') () in
  reject "composition_evidence_limit" (fun () -> T.make ~outcome:E.Unknown ~dependencies ~checked_requirement_ids:[]
      ~diagnostics:(List.init 7 (fun _ -> near) @ [over]) ());
  reject "composition_evidence_limit" (fun () -> T.make ~outcome:E.Unknown ~dependencies ~checked_requirement_ids:[]
      ~diagnostics:(List.init 25000 (fun _ -> small)) ());
  reject "request_too_large" (fun () -> T.of_json_text (String.make (Limits.max_request_bytes + 1) ' '))

let () = literals (); historical_scope (); freshness (); invalid_records (); native_boundaries ();
  Printf.printf "Composition evidence: %d literal/identity/resource checks passed\n" !checks
