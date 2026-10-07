open Bioc_wire
open Bioc_policy_component_test_support.Literals
open Bioc_policy_component_test_support.Requests
module Selection = Bioc_domain.Policy_component_selection_request

(* These are domain-only controls. Complete supplied child requests come from
   the independently authored A/B originals; decoding establishes no common
   program, eligibility, preservation, material or export capability. *)
let alternative id rank request = obj ["id",str id;"rank",Json.int rank;"request",request]
let request alternatives = obj [
  "schema_version",str "biocompiler.policy_component_selection_request.v0.1";
  "profile",str "biocompiler.policy_component_material_selection.v0.1";
  "alternatives",arr alternatives;"predicate",obj ["max_total_nt",Json.int 17];
  "budgets",obj ["profile",str "biocompiler.policy_component_selection_resources.v0.1";
    "max_work",Json.Int (Z.of_string "17000000000");
    "max_report_bytes",Json.int 8323072;"max_report_nodes",Json.int 249968]]
let omit key raw = obj (List.filter (fun (name,_) -> name<>key) (Json.object_fields raw))
let names rows = List.map (fun (row:Selection.alternative) -> row.id) rows
let base fixture state_reading = fst (request_literal fixture state_reading)
  |> put ["context";"delivery_group";"max_total_bases"] (Json.int 18)
let positive child other =
  let raw=request [alternative "z-last" 0 child;alternative "A-first" 2147483647 child;
    alternative "a-later" 1 child] in
  let charged=ref 0 in
  let decoded=Selection.of_json ~charge:(fun amount -> charged := !charged+amount) raw in
  require (Json.equal (Selection.to_json decoded) raw && Selection.fingerprint decoded=Canonical.fingerprint raw)
    "Selection erased complete original request spelling or fingerprint";
  require (!charged>0 && !charged=Selection.decoding_work decoded)
    "Selection decoding charge omits outer or complete child work";
  require (names (Selection.alternatives decoded)=["z-last";"A-first";"a-later"])
    "Input alternative order was replaced by evaluation/preference order";
  require (names (Selection.evaluation_order decoded)=["A-first";"a-later";"z-last"] &&
    (Selection.anchor decoded).id="A-first") "Evaluation/anchor must use ASCII ID order, independently of ranks";
  require (List.map (fun (row:Selection.alternative) -> row.rank) (Selection.alternatives decoded)=[0;2147483647;1])
    "Ranks were normalized or reordered";
  List.iter (fun (row:Selection.alternative) -> require (Json.equal (R.to_json row.request) child)
    "Alternative retained only an opaque child pin") (Selection.alternatives decoded);
  require ((Selection.predicate decoded).max_total_nt=17 &&
    (Selection.budgets decoded).max_work=17000000000 &&
    (Selection.budgets decoded).max_report_bytes=8323072 &&
    (Selection.budgets decoded).max_report_nodes=249968) "Exact independent selection ceilings changed";
  let reordered=edit ["alternatives"] (fun rows -> arr (List.rev (Json.array rows))) raw |> Selection.of_json in
  require (Selection.fingerprint reordered<>Selection.fingerprint decoded &&
    names (Selection.alternatives reordered)=["a-later";"A-first";"z-last"] &&
    names (Selection.evaluation_order reordered)=names (Selection.evaluation_order decoded) &&
    (Selection.anchor reordered).id="A-first") "Reordering lost original identity or changed canonical evaluation";
  let reranked=raw |> put ["alternatives";"0";"rank"] (Json.int 2147483647)
    |> put ["alternatives";"1";"rank"] (Json.int 0) |> Selection.of_json in
  require (Selection.fingerprint reranked<>Selection.fingerprint decoded &&
    names (Selection.evaluation_order reranked)=["A-first";"a-later";"z-last"] &&
    (Selection.anchor reranked).id="A-first") "Ranks improperly changed authority anchor/evaluation order";
  let singleton=Selection.of_json (request [alternative "0" 0 child]) in
  require (names (Selection.alternatives singleton)=["0"] && (Selection.anchor singleton).id="0")
    "Single alternative or digit-leading ASCII ID was rejected";
  let ascii=Selection.of_json (request [alternative "a" 0 child;alternative "2" 0 child;
    alternative "A" 0 child;alternative "10" 0 child]) in
  require (names (Selection.evaluation_order ascii)=["10";"2";"A";"a"])
    "IDs were compared numerically, case-folded or locale-sorted";
  let boundary=Selection.of_json (request (List.init 16 (fun index ->
    alternative (Printf.sprintf "id.%02d_suffix" index) index child))) in
  require (List.length (Selection.alternatives boundary)=16) "Exact sixteen-alternative bound was narrowed";
  let long_id="A"^String.make 127 'x' in
  require ((Selection.anchor (Selection.of_json (request [alternative long_id 0 child]))).id=long_id)
    "Exact128-byte ID was narrowed";
  List.iter (fun limit -> let value=raw |> put ["predicate";"max_total_nt"] (Json.int limit) |> Selection.of_json in
    require ((Selection.predicate value).max_total_nt=limit) "Outer predicate boundary was narrowed") [0;1000000];
  let mixed=request [alternative "A" 0 child;alternative "B" 0 other] in
  let mixed_decoded=Selection.of_json mixed in
  require (Json.equal mixed (Selection.to_json mixed_decoded) &&
    R.fingerprint (List.hd (Selection.alternatives mixed_decoded)).request <>
      R.fingerprint (List.nth (Selection.alternatives mixed_decoded) 1).request)
    "Shape decoding must retain different complete originals for later common-base checking";
  raw
let controls raw child =
  let reject code label transform = rejected code label (fun () -> Selection.of_json (transform raw)) in
  List.iter (fun field -> reject "missing_field" ("Missing selection "^field) (omit field))
    ["schema_version";"profile";"alternatives";"predicate";"budgets"];
  List.iter (fun (key,value) -> reject "unknown_field" ("Unknown selection "^key) (add key value))
    ["tie_order",str "locale";"accepted",Json.Bool true;"winner",str "z-last"];
  reject "duplicate_key" "Duplicate top-level authority" (add "profile" (get "profile" raw));
  List.iter (fun field -> reject "policy_component_selection_request" ("Unsupported "^field)
    (replace field (str "future"))) ["schema_version";"profile"];
  reject "policy_component_selection_request" "Wrong resource profile"
    (put ["budgets";"profile"] (str "biocompiler.policy_component_material_resources.v0.1"));
  reject "policy_component_selection_request" "Empty alternative catalog" (replace "alternatives" (arr []));
  reject "policy_component_selection_request" "Seventeenth alternative exceeds finite profile"
    (replace "alternatives" (arr (List.init 17 (fun i -> alternative (string_of_int i) 0 child))));
  reject "policy_component_selection_request" "Duplicate ID cannot hide a complete losing alternative"
    (put ["alternatives";"1";"id"] (str "z-last"));
  List.iter (fun id -> reject "policy_component_selection_request" ("Noncanonical ASCII ID: "^id)
    (put ["alternatives";"0";"id"] (str id)))
    ["";" ";"-first";".first";"_first";"a b";"a/b";"a:b";"a\\b";"a\n";"a\000b";"é";"Ａ";String.make 129 'a'];
  List.iter (fun value -> reject "invalid_type" "Mixed JSON ID form cannot normalize to ASCII text"
    (put ["alternatives";"0";"id"] value)) [Json.int 1;Json.Bool true;Json.Float 1.];
  List.iter (fun value -> reject "invalid_type" "Rank remains a JSON integer"
    (put ["alternatives";"0";"rank"] value)) [Json.Bool true;Json.Float 1.;str "1";Json.Null];
  List.iter (fun value -> reject "policy_component_selection_request" "Rank outside bounded nonnegative range"
    (put ["alternatives";"0";"rank"] value)) [Json.int (-1);Json.Int (Z.of_string "2147483648")];
  List.iter (fun field -> reject "missing_field" ("Incomplete alternative "^field)
    (edit ["alternatives";"0"] (omit field))) ["id";"rank";"request"];
  reject "unknown_field" "Per-alternative predicate cannot weaken the common constraint"
    (edit ["alternatives";"0"] (add "predicate" (obj ["max_total_nt",Json.int 18])));
  reject "duplicate_key" "Repeated rank cannot shadow original preference"
    (edit ["alternatives";"0"] (add "rank" (Json.int 1)));
  reject "missing_field" "Opaque child fingerprint is not complete supplied authority"
    (put ["alternatives";"0";"request"] (obj ["fingerprint",str (Canonical.fingerprint child)]));
  reject "unknown_field" "Child saved acceptance cannot become original request"
    (edit ["alternatives";"0";"request"] (add "accepted" (Json.Bool true)));
  reject "missing_field" "Common predicate cannot be omitted" (edit ["predicate"] (omit "max_total_nt"));
  reject "unknown_field" "Additional unimplemented predicate" (edit ["predicate"] (add "minimum_nt" (Json.int 1)));
  List.iter (fun value -> reject "invalid_type" "Predicate uses exact integers"
    (put ["predicate";"max_total_nt"] value)) [Json.Bool false;Json.Float 17.;str "17"];
  List.iter (fun value -> reject "policy_component_selection_request" "Predicate exceeds declared finite bounds"
    (put ["predicate";"max_total_nt"] (Json.int value))) [-1;1000001];
  List.iter (fun field -> reject "missing_field" ("Complete outer budget "^field)
    (edit ["budgets"] (omit field))) ["profile";"max_work";"max_report_bytes";"max_report_nodes"];
  List.iter (fun (field,value) -> reject "policy_component_selection_request" ("Outer budget exceeds fixed bound: "^field)
    (put ["budgets";field] value)) ["max_work",Json.Int (Z.of_string "17000000001");
      "max_report_bytes",Json.int 8323073;"max_report_nodes",Json.int 249969];
  List.iter (fun field -> reject "invalid_type" ("Boolean budget: "^field)
    (put ["budgets";field] (Json.Bool true))) ["max_work";"max_report_bytes";"max_report_nodes"];
  List.iter (fun field -> reject "policy_component_selection_request" ("Zero outer allowance: "^field)
    (put ["budgets";field] (Json.int 0))) ["max_work";"max_report_bytes";"max_report_nodes"];
  rejected "literal_charge_denied" "External work owner can deny before complete decoding" (fun () ->
    let remaining=ref 1 in Selection.of_json ~charge:(fun amount ->
      if amount> !remaining then Diagnostic.fail "literal_charge_denied" "One unit is insufficient.";
      remaining := !remaining-amount) raw);
  let rec cyclic=Json.Array [cyclic] in
  rejected "policy_material_input_limit" "Cyclic input cannot bypass finite preflight" (fun () -> Selection.of_json cyclic)
let () =
  try
    require (Array.length Sys.argv=3) "Supply independent A/B original request fixtures";
    let a=base (read Sys.argv.(1)) false and b=base (read Sys.argv.(2)) true in
    let raw=positive a b in controls raw a;
    Printf.printf "component selection request: %d independent source/shape controls passed\n" !checks
  with Diagnostic.Error value ->
    Printf.eprintf "Diagnostic.Error(code=%s,path=%s,message=%s)\n" value.code
      (Option.value ~default:"<none>" value.path) value.message; exit 1
