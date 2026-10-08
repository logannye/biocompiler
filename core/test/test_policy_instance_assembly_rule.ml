open Bioc_wire
open Bioc_policy_instance_test_support.Literals
open Bioc_policy_instance_test_support.Requests
module R = Bioc_domain.Policy_component_material_request
module X = Bioc_domain.Policy_component_context

let run fixture state_reading =
  let models=original_library fixture in
  let model_library=I.library_of_json models in
  let originals=components models state_reading in
  let component_library=L.of_json ~library:model_library (library originals) in
  let original=rule models state_reading in
  let value=A.of_json ~components:component_library original in
  require(Json.equal(A.to_json value)original) "Original named-instance rule changed during decoding";
  require(List.length(A.components value)=3 && List.length(A.node_order value)=(if state_reading then 17 else 15))
    "Named instance/node inventory changed";
  require(List.length(A.links value)=4 && List.length(A.wire_order value)=(if state_reading then 25 else 22))
    "Complete local/cross-link union differs from independent declared counts";
  require(List.length(A.export_order value)=(if state_reading then 23 else 21))
    "An observable primitive output was hidden";
  let leading=List.nth originals 0 and trailing=List.nth originals 2 in
  require(Json.equal(at ["body";"fragment"] leading)(at ["body";"fragment"] trailing))
    "Two independently owned edge instances no longer reuse the exact graph fragment";
  require(get "identity" leading<>get "identity" trailing)
    "Different complete material definitions were conflated with reusable graph identity";
  require(C.fingerprint(C.of_json ~library:model_library leading)<>C.fingerprint(C.of_json ~library:model_library trailing))
    "Different material bodies lost separate component identity";
  require(N.sequence(expected_molecule())="CCAUGGCUUAAGGAAAA" && List.length(N.features(expected_molecule()))=4)
    "Independent complete material oracle changed";
  let request,union=request_literal fixture state_reading in
  ignore(R.of_json request);
  require(Json.equal(X.ordered_union_json value)union)
    "Authoritative ordered union differs from the independent node/wire/input/group literal";
  ignore(expected_projections state_reading models);
  let reject label raw=rejected "policy_component_assembly_rule" label
    (fun()->A.of_json ~components:component_library raw) in
  let changed label keys replacement=reject label(original |> put keys replacement |> repin) in
  changed "Duplicate named instance" ["body";"components";"2";"slot"] (str "select_edge");
  changed "Stale component definition" ["body";"components";"0";"component";"content_fingerprint"] (str(String.make 64 '0'));
  changed "Missing stateful instance node" ["body";"node_order"] (arr(List.tl(global_nodes state_reading)));
  changed "Aliased edge instance ownership" ["body";"node_order";"3";"slot"] (str "select_edge");
  changed "Wrong cross-link signal type" ["body";"links";"0";"signal_type"] (str "event_batch");
  changed "Encounter signal cannot broadcast as executor constant" ["body";"links";"0";"scope"] (str "immutable_executor_broadcast");
  changed "Dangling cross-link endpoint" ["body";"links";"0";"consumer";"boundary"] (str "absent");
  changed "Duplicate consumed input boundary" ["body";"links";"1";"consumer"] (br "select_edge" "truth");
  changed "Cross-instance atomic ownership" ["body";"group_order";"0";"slot"] (str "select_edge");
  changed "Orphan observable export" ["body";"export_order"] (arr(List.tl(global_exports state_reading)));
  changed "Misplaced first join" ["body";"joins";"0";"offset"] (Json.int 1);
  changed "Misplaced second join" ["body";"joins";"1";"offset"] (Json.int 12);
  changed "Skipped middle root" ["body";"joins";"0";"right"] (str "exclude_edge");
  changed "Carrier uses wrong join" ["body";"link_carriers";"0";"joins"] (arr [str "cds_trailer"]);
  changed "Carrier omits join" ["body";"link_carriers";"0";"joins"] (arr []);
  changed "Carrier names absent feature site" ["body";"link_carriers";"0";"producer_site"] (Json.int 1);
  changed "Root binding crosses material ownership" ["body";"root_bindings";"0";"source"] (str "edge_trailer");
  List.iter(fun key->let rows=items key(get "body" original) in
    changed("Incomplete ordered "^key)["body";key](arr(List.tl rows)))
    ["joins";"link_carriers";"root_bindings";"input_order";"group_order";"wire_order"];
  require(A.fingerprint value=Canonical.fingerprint original) "Rule content identity differs from original bytes";
  originals

let () =
  try
    require(Array.length Sys.argv=3) "Supply the two existing original policy/model fixtures";
    let first=run(read Sys.argv.(1))false and second=run(read Sys.argv.(2))true in
    List.iter(fun index->require(Json.equal(List.nth first index)(List.nth second index))
      "Reusable complete edge component acquired a policy/context dependent identity")[0;2];
    require(not(Json.equal(List.nth first 1)(List.nth second 1))) "Distinct control programs reused a material contract identity";
    Printf.printf "instance component rule: %d independent controls passed\n" !checks
  with Diagnostic.Error value->
    Printf.eprintf "Diagnostic.Error(code=%s,message=%s)\n" value.code value.message;exit 1
