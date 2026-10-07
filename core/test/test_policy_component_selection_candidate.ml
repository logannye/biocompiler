open Bioc_wire
open Bioc_policy_component_test_support.Literals
open Bioc_policy_component_test_support.Requests
module Originals = Bioc_policy_component_test_support.Selection_requests
module Selection = Bioc_domain.Policy_component_selection_request
module Candidate = Bioc_domain.Policy_component_selection_candidate
module Child = Bioc_domain.Policy_component_material_candidate
module O = Bioc_domain.Policy_operational
module D = Bioc_domain.Policy_document

(* Original fixture graph/binding/construction parts are literal data. The
   intentionally empty behavior ledger below is shape-valid but unproved.
   Neither producer nor checker execution supplies expected codec values. *)
let inner_literal fixture request =
  let original=RR.of_json (get "implementation_request" request) in
  let document=RR.document original and definitions=RR.definitions original in
  let behavior=obj ["schema_version",str "biocompiler.policy_behavior.v0.1";
    "profile",str "biocompiler.policy_operational.v0.1";
    "source_document",D.to_json document;"descriptor_bundle",O.descriptors_to_json definitions;
    "source_artifact_digest",str (D.artifact_digest document);
    "descriptors_digest",str (O.descriptors_digest definitions);
    "nodes",arr [];"source_ledger",arr [];"requirements_ledger",arr [];
    "assumptions",arr [];"unresolved_obligations",arr [str "literal_selection_candidate_requires_fresh_check"]] in
  let assembly=obj ["schema_version",str "biocompiler.policy_component_assembly_proposal.v0.1";
    "profile",str "biocompiler.policy_exact_component_assembly.v0.1";
    "rule",at ["composition_rule";"identity"] request;
    "nodes",arr (List.map (fun reference -> add "actual" (get "node" reference) reference) (global_nodes false))] in
  let parts=get "candidate_parts" fixture in
  let implementation=get "implementation" parts
    |> put ["authority";"library_digest"] (str (I.library_digest (RR.implementation_library original))) in
  obj ["schema_version",str "biocompiler.policy_component_material_candidate.v0.1";
    "behavior",behavior;"implementation",implementation;"binding",get "binding" parts;
    "assembly_proposal",assembly;"construction",get "construction" parts]
let outer_literal fixture request =
  obj ["schema_version",str "biocompiler.policy_component_selection_candidate.v0.1";
    "alternatives",arr (List.map (fun (row:Selection.alternative) ->
      obj ["id",str row.id;"candidate",inner_literal fixture (R.to_json row.request)]) (Selection.alternatives request));
    "selected_id",str "long"]
let names rows=List.map (fun (row:Candidate.alternative) -> row.id) rows
let omit key raw=obj (List.filter (fun (name,_) -> name<>key) (Json.object_fields raw))

let positive fixture =
  let original=Originals.selection_literal fixture in
  let request=Selection.of_json original in
  let raw=outer_literal fixture request in
  let charged=ref 0 in
  let value=Candidate.of_json ~charge:(fun amount -> charged := !charged+amount) ~request raw in
  require (Candidate.to_json value=raw && Candidate.fingerprint value=Canonical.fingerprint raw &&
    Candidate.request_fingerprint value=Selection.fingerprint request)
    "Candidate codec lost raw spelling or either complete input identity";
  require (!charged>0 && !charged=Candidate.decoding_work value)
    "Candidate codec omitted child traversal/encoding from caller work";
  require (names (Candidate.alternatives value)=["short";"long"] &&
    names (Candidate.evaluation_order value)=["long";"short"])
    "Candidate input order must be retained separately from ASCII evaluation order";
  require (Candidate.selected_id value=Some "long")
    "Shape decoding must retain a known proposed winner even when it violates the outer seventeen-base predicate";
  List.iter2 (fun (row:Candidate.alternative) original ->
    require (Child.to_json row.candidate=get "candidate" original) "Child candidate raw value was replaced";
    let behavior=Child.behavior row.candidate in
    require (behavior.nodes=[] && behavior.unresolved_obligations=["literal_selection_candidate_requires_fresh_check"])
      "Domain codec supplied behavioral proof or removed unresolved authority")
    (Candidate.alternatives value) (items "alternatives" raw);
  let none=Candidate.of_json ~request (replace "selected_id" Json.Null raw) in
  require (Candidate.selected_id none=None) "Null proposal requires a fresh checker, not parser rejection";
  let short=Candidate.of_json ~request (replace "selected_id" (str "short") raw) in
  require (Candidate.selected_id short=Some "short") "Another known ID cannot be silently selected/replaced";
  let reversed=edit ["alternatives"] (fun rows -> arr (List.rev (Json.array rows))) raw in
  let reordered=Candidate.of_json ~request reversed in
  require (Candidate.to_json reordered=reversed && Candidate.fingerprint reordered<>Candidate.fingerprint value &&
    names (Candidate.evaluation_order reordered)=["long";"short"])
    "Reordered input erased identity or changed canonical candidate evaluation";
  let field_order=obj (List.rev (Json.object_fields raw)) in
  require (Candidate.to_json (Candidate.of_json ~request field_order)=field_order &&
    Candidate.fingerprint (Candidate.of_json ~request field_order)=Candidate.fingerprint value)
    "Raw field order must survive while canonical object identity stays unchanged";
  let reordered_request=Selection.of_json (edit ["alternatives"] (fun rows -> arr (List.rev (Json.array rows))) original) in
  let rebound=Candidate.of_json ~request:reordered_request raw in
  require (Candidate.fingerprint rebound=Candidate.fingerprint value &&
    Candidate.request_fingerprint rebound=Selection.fingerprint reordered_request &&
    Candidate.request_fingerprint rebound<>Candidate.request_fingerprint value)
    "Candidate decoding lost the separately supplied original request fingerprint";
  request,raw

let controls request raw =
  let reject code label transform=rejected code label (fun () -> Candidate.of_json ~request (transform raw)) in
  List.iter (fun key -> reject "missing_field" ("Missing outer candidate "^key) (omit key))
    ["schema_version";"alternatives";"selected_id"];
  List.iter (fun key -> reject "unknown_field" ("Serialized "^key^" cannot grant selection authority")
    (add key (Json.Bool true))) ["accepted";"report";"checked_token";"request"];
  reject "duplicate_key" "Duplicate selected ID field" (add "selected_id" Json.Null);
  reject "policy_component_selection_candidate" "Unknown candidate schema" (replace "schema_version" (str "future"));
  reject "policy_component_selection_candidate" "Missing losing child" (edit ["alternatives"] (fun rows -> arr (List.tl (Json.array rows))));
  reject "policy_component_selection_candidate" "Empty child census" (replace "alternatives" (arr []));
  reject "policy_component_selection_candidate" "Extra child outside original census"
    (edit ["alternatives"] (fun rows -> let values=Json.array rows in arr (values@[List.hd values])));
  reject "policy_component_selection_candidate" "Duplicate child ID hides another original"
    (put ["alternatives";"1";"id"] (str "short"));
  reject "policy_component_selection_candidate" "Foreign ID cannot select a child library by position"
    (put ["alternatives";"0";"id"] (str "foreign"));
  reject "policy_component_selection_candidate" "Unknown proposed winner" (replace "selected_id" (str "foreign"));
  List.iter (fun value -> reject "invalid_type" "Proposed winner is only an original string ID or null"
    (replace "selected_id" value)) [Json.Bool true;Json.int 0;Json.Float 1.;arr []];
  reject "invalid_type" "Numeric alternative identity" (put ["alternatives";"0";"id"] (Json.int 1));
  List.iter (fun key -> reject "missing_field" ("Missing complete child "^key) (edit ["alternatives";"0"] (omit key)))
    ["id";"candidate"];
  reject "unknown_field" "Child acceptance flag cannot confer capability" (edit ["alternatives";"0"] (add "accepted" (Json.Bool true)));
  reject "duplicate_key" "Duplicate child candidate field" (edit ["alternatives";"0"] (add "candidate" Json.Null));
  reject "missing_field" "Opaque child digest is not the original six-field candidate"
    (put ["alternatives";"0";"candidate"] (obj ["fingerprint",str (String.make 64 '0')]));
  reject "policy_component_material_candidate" "Nested candidate schema remains independently closed"
    (put ["alternatives";"1";"candidate";"schema_version"] (str "future"));
  reject "policy_implementation_contract" "Nested implementation remains bound to the supplied child library"
    (put ["alternatives";"1";"candidate";"implementation";"authority";"library_digest"] (str (String.make 64 '0')));
  rejected "literal_candidate_charge" "Outer decoding obeys caller work denial before full child traversal" (fun () ->
    let left=ref 1 in Candidate.of_json ~request ~charge:(fun amount ->
      if amount> !left then Diagnostic.fail "literal_candidate_charge" "One unit is insufficient.";
      left := !left-amount) raw);
  let rec cyclic=Json.Array [cyclic] in
  rejected "policy_material_input_limit" "Cyclic outer candidate is bounded before typed traversal"
    (fun () -> Candidate.of_json ~request cyclic)

let child_library_controls fixture =
  (* A different library container version is structurally decodable. This does
     not assert the common-meaning relation; that is an independent check. *)
  let raw_request=Originals.selection_literal fixture
    |> put ["alternatives";"1";"request";"implementation_request";"implementation_library";"version"] (str "2") in
  let request=Selection.of_json raw_request in
  let raw=outer_literal fixture request in
  let first=at ["alternatives";"0";"candidate";"implementation";"authority";"library_digest"] raw
  and second=at ["alternatives";"1";"candidate";"implementation";"authority";"library_digest"] raw in
  require (first<>second) "Per-child library control needs two distinct complete original library identities";
  ignore (Candidate.of_json ~request raw);
  let wrong=put ["alternatives";"1";"candidate";"implementation";"authority";"library_digest"] first raw in
  rejected "policy_implementation_contract" "First child's library cannot validate the second original"
    (fun () -> Candidate.of_json ~request wrong);
  let wrong_ids=raw |> put ["alternatives";"0";"id"] (str "long")
    |> put ["alternatives";"1";"id"] (str "short") in
  rejected "policy_implementation_contract" "Child libraries follow original IDs, not candidate array positions"
    (fun () -> Candidate.of_json ~request wrong_ids)

let () =
  try
    require (Array.length Sys.argv=2) "Supply the A original fixture with independent literal candidate parts";
    let fixture=read Sys.argv.(1) in
    let request,raw=positive fixture in controls request raw;child_library_controls fixture;
    Printf.printf "component selection candidate: %d independent census/codec controls passed\n" !checks
  with Diagnostic.Error value ->
    Printf.eprintf "Diagnostic.Error(code=%s,path=%s,message=%s)\n" value.code
      (Option.value ~default:"<none>" value.path) value.message; exit 1
