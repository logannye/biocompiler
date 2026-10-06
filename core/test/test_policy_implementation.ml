open Bioc_wire
module I = Bioc_domain.Policy_implementation
module P = Bioc_domain.Pinned_identity

let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let items key value = Json.array (get key value)
let text key value = Json.string (get key value)
let replace key replacement value = obj (List.map (fun (name, item) ->
  name, (if key = name then replacement else item)) (Json.object_fields value))
let add key item value = obj ((key, item) :: Json.object_fields value)
let remove key value = obj (List.filter (fun (name, _) -> key <> name) (Json.object_fields value))
let change index transform values = List.mapi (fun i value -> if index = i then transform value else value) values
let change_item key index transform value = replace key (arr (change index transform (items key value))) value
let endpoint node port = obj ["node", str node; "port", str port]
let wire producer consumer = obj ["producer", producer; "consumer", consumer]
let rejection_count = ref 0
let rejects label action = match action () with
  | () -> failwith ("Implementation contract mutant accepted: " ^ label)
  | exception Diagnostic.Error _ -> incr rejection_count
let ingress_rejects label action = match action () with
  | () -> failwith ("Implementation ingress mutant accepted: " ^ label)
  | exception Diagnostic.Error diagnostic ->
      require (diagnostic.code = "policy_implementation_limit") (label ^ " escaped bounded ingress");
      incr rejection_count
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size = in_channel_length channel in
    require (size <= 2 * 1024 * 1024) "Implementation fixture exceeds test bound";
    Json.parse (really_input_string channel size))
let authority value : I.authority = {
  source_artifact_digest = text "source_artifact_digest" value;
  descriptors_digest = text "descriptors_digest" value;
  domain_digest = text "domain_digest" value;
  implementation_catalog_digest = text "implementation_catalog_digest" value;
  library_digest = text "library_digest" value }
let rehash_model value =
  let body = get "body" value in
  value |> replace "configuration_digest" (str (Canonical.fingerprint (get "configuration" body)))
    |> replace "identity" (replace "content_fingerprint" (str (Canonical.fingerprint body)) (get "identity" value))
let repin_library library candidate =
  replace "authority" (replace "library_digest" (str (Canonical.fingerprint library)) (get "authority" candidate)) candidate
let repin_node node model = node |> replace "model" (get "identity" model)
  |> replace "configuration_digest" (get "configuration_digest" model)
let occurrence path target = obj ["source_path", str path; "role", str "predicate";
  "disposition", str "executable"; "targets", arr [target]]

let run fixture =
  let library_raw = get "library" fixture and candidate = get "candidate" fixture in
  let library = I.library_of_json library_raw in
  let value = I.of_json ~library candidate in
  let expected = authority (get "expected_authority" fixture)
  and expected_inventory = List.map Json.string (items "expected_occurrences" fixture) in
  I.check_authority ~expected value;
  I.check_occurrence_inventory ~expected:expected_inventory value;
  require (Json.equal (I.library_to_json library) library_raw) "Library snapshot changed";
  require (Json.equal (I.to_json value) candidate) "Candidate snapshot changed";
  require (I.library_digest library = Canonical.fingerprint library_raw) "Library identity differs";
  require (I.fingerprint value = Canonical.fingerprint candidate) "Candidate identity differs";
  require (List.length (I.models library) = 9 && List.length (I.nodes value) = 9) "Literal primitive graph omitted a model or node";
  require (List.length (I.wires value) = 10 && List.length (I.inputs value) = 2) "Literal wiring changed";
  require (List.length (I.semantic_exports value) = 12 && List.length (I.atomic_groups value) = 1) "Literal semantic output inventory changed";
  require ((I.slot_layout value).slots = 2) "Distinct encounter slots collapsed";
  List.iter2 (fun (model : I.model) raw ->
    require (Json.equal (I.model_body_to_json model) (get "body" raw)) "Decoded primitive changed its body";
    require (P.content_fingerprint model.identity = Canonical.fingerprint (get "body" raw)) "Model pin differs from its complete body")
    (I.models library) (items "models" library_raw);
  let check raw = ignore (I.of_json ~library raw)
  and check_library raw = ignore (I.library_of_json raw) in
  List.iter (fun field ->
    rejects ("missing candidate field " ^ field) (fun () -> check (remove field candidate)))
    ["schema_version"; "profile"; "observable_profile"; "authority"; "slot_layout"; "nodes";
     "wires"; "inputs"; "atomic_groups"; "semantic_exports"; "occurrences"];
  rejects "extra candidate source interpreter" (fun () -> check (add "source_ast" (obj []) candidate));
  List.iter (fun field -> rejects ("unknown profile " ^ field) (fun () -> check (replace field (str "future") candidate)))
    ["schema_version"; "profile"; "observable_profile"];
  List.iter (fun field -> rejects ("missing library field " ^ field) (fun () -> check_library (remove field library_raw)))
    ["schema_version"; "profile"; "id"; "version"; "models"];
  rejects "extra library authority" (fun () -> check_library (add "accepted" (Json.Bool true) library_raw));
  rejects "duplicate library model id/version" (fun () -> check_library (replace "models"
    (arr (List.hd (items "models" library_raw) :: items "models" library_raw)) library_raw));
  rejects "empty model library" (fun () -> check_library (replace "models" (arr []) library_raw));
  rejects "too many models" (fun () -> check_library (replace "models"
    (arr (List.init 65 (fun _ -> List.hd (items "models" library_raw)))) library_raw));
  List.iter (fun digest -> rejects "malformed library model SHA" (fun () -> check_library
    (change_item "models" 0 (fun m -> replace "identity" (replace "content_fingerprint" (str digest) (get "identity" m)) m) library_raw)))
    [String.make 63 'a'; String.make 65 'a'; String.make 64 'g'; String.make 64 'A'];
  rejects "model wrong nominal kind" (fun () -> check_library (change_item "models" 0
    (fun m -> replace "identity" (replace "kind" (str "reference") (get "identity" m)) m) library_raw));
  rejects "changed concrete model body" (fun () -> check_library (change_item "models" 0
    (fun m -> replace "body" (replace "configuration" (obj ["freshness_ticks", Json.int 3]) (get "body" m)) m) library_raw));
  rejects "changed configuration digest" (fun () -> check_library (change_item "models" 0
    (replace "configuration_digest" (str (String.make 64 'b'))) library_raw));
  let body_mutant index transform = change_item "models" index
    (fun m -> rehash_model (replace "body" (transform (get "body" m)) m)) library_raw in
  let primitive_variant tag config = body_mutant 0 (fun body -> body
    |> replace "primitive" (str tag) |> replace "configuration" config) in
  List.iter (fun (tag, config) ->
    let raw = primitive_variant tag config in
    let model = List.hd (I.models (I.library_of_json raw)) in
    require (I.primitive_name model.primitive = tag) "Closed primitive decoder changed its tag";
    require (Json.equal (I.model_body_to_json model) (get "body" (List.hd (items "models" raw)))) "Closed primitive configuration changed";
    require (I.ports model.primitive <> []) "Closed primitive has no typed ports")
    ["truth_constant", obj ["value", str "unknown"];
     "truth_constant", obj ["value", str "false"];
     "truth_not", obj []; "truth_all", obj ["arity", Json.int 2];
     "truth_any", obj ["arity", Json.int 2]; "truth_equal", obj [];
     "truth_register", obj ["initial", str "unknown"; "writers", Json.int 0];
     "priority_arbiter", obj ["order", arr [Json.int 1; Json.int 0]];
     "attempt_bank", obj ["capacity", Json.int 1; "timeout_ticks", Json.int 1;
       "authorization", str "initiation"; "on_loss", str "continue"; "on_unknown", str "defer"]];
  List.iter (fun event -> check_library (primitive_variant "event_select" (obj ["event_kind", str event])))
    ["updated"; "rising"; "requested"; "initiated"; "completed"; "failed"; "timed_out"];
  List.iter (fun (tag, config) -> rejects ("unsupported primitive configuration " ^ tag)
    (fun () -> check_library (primitive_variant tag config)))
    ["truth_all", obj ["arity", Json.int 0]; "truth_any", obj ["arity", Json.int 65];
     "priority_arbiter", obj ["order", arr [Json.int 0; Json.int 0]];
     "priority_arbiter", obj ["order", arr [Json.int 1]];
     "event_select", obj ["event_kind", str "cancelled"]];
  List.iter (fun tag -> rejects ("primitive alias/interpreter " ^ tag) (fun () -> check_library
    (body_mutant 1 (replace "primitive" (str tag))))) ["rising"; "source_policy"; "python"; "opaque_model"];
  rejects "hidden source operand" (fun () -> check_library (body_mutant 1
    (replace "configuration" (obj ["expression", obj []]))));
  rejects "raw Boolean primitive truth alias" (fun () -> check_library (body_mutant 2
    (replace "configuration" (obj ["value", Json.Bool true]))));
  List.iter (fun index -> rejects "executor scope collapses encounter control/state" (fun () -> check_library
    (body_mutant index (replace "replication" (obj ["kind", str "executor"]))))) [0; 1; 4; 5; 6; 7; 8];
  rejects "unsupported cancellation semantics" (fun () -> check_library (body_mutant 8
    (fun body -> replace "configuration" (replace "on_loss" (str "cancel") (get "configuration" body)) body)));
  rejects "empty atomic commit" (fun () -> check_library (body_mutant 6
    (replace "configuration" (obj ["writes", Json.int 0; "requests", Json.int 0]))));
  rejects "unknown replication" (fun () -> check_library (body_mutant 0
    (replace "replication" (obj ["kind", str "broadcast_all"]))));
  rejects "wrong library pin" (fun () -> check (replace "authority"
    (replace "library_digest" (str (String.make 64 '1')) (get "authority" candidate)) candidate));
  List.iter (fun field ->
    let wrong = replace "authority" (replace field (str (String.make 64 '2')) (get "authority" candidate)) candidate in
    rejects ("independent authority mismatch " ^ field) (fun () -> I.check_authority ~expected (I.of_json ~library wrong)))
    ["source_artifact_digest"; "descriptors_digest"; "domain_digest"; "implementation_catalog_digest"];
  rejects "candidate missing complete selected model pin" (fun () -> check (change_item "nodes" 0
    (fun n -> replace "model" (remove "version" (get "model" n)) n) candidate));
  List.iter (fun field -> rejects ("id-only selected model alias " ^ field) (fun () -> check (change_item "nodes" 0
    (fun n -> replace "model" (replace field (str "unauthorized") (get "model" n)) n) candidate))) ["id"; "version"];
  rejects "selected model wrong configuration" (fun () -> check (change_item "nodes" 0
    (replace "configuration_digest" (str (String.make 64 '3'))) candidate));
  rejects "candidate supplied body override" (fun () -> check (change_item "nodes" 0 (add "body" (obj [])) candidate));
  rejects "duplicate node" (fun () -> check (replace "nodes" (arr (List.hd (items "nodes" candidate) :: items "nodes" candidate)) candidate));
  rejects "empty graph" (fun () -> check (replace "nodes" (arr []) candidate));
  List.iter (fun (field, replacement) -> rejects ("collapsed or renamed slot layout " ^ field) (fun () -> check
    (replace "slot_layout" (replace field replacement (get "slot_layout" candidate)) candidate)))
    ["slots", Json.int 1; "id", str "different-layout"];
  rejects "absent wire node" (fun () -> check (change_item "wires" 0
    (replace "producer" (endpoint "absent" "value")) candidate));
  rejects "absent wire port" (fun () -> check (change_item "wires" 0
    (replace "producer" (endpoint "evidence" "missing")) candidate));
  rejects "wire direction reversal" (fun () -> check (change_item "wires" 0
    (replace "producer" (endpoint "evidence" "samples")) candidate));
  rejects "wire signal mismatch" (fun () -> check (change_item "wires" 0
    (replace "producer" (endpoint "product" "out")) candidate));
  rejects "multiple input drivers" (fun () -> check (replace "wires" (arr (List.hd (items "wires" candidate) :: items "wires" candidate)) candidate));
  rejects "undriven input" (fun () -> check (replace "wires" (arr (List.tl (items "wires" candidate))) candidate));
  rejects "external kind mismatch" (fun () -> check (change_item "inputs" 0 (replace "kind" (str "feedback")) candidate));
  rejects "unknown external kind" (fun () -> check (change_item "inputs" 0 (replace "kind" (str "clock_override")) candidate));
  rejects "external driver alias" (fun () -> check (replace "inputs" (arr
    (items "inputs" candidate @ [replace "id" (str "alias") (List.hd (items "inputs" candidate))])) candidate));
  rejects "missing atomic ownership" (fun () -> check (replace "atomic_groups" (arr []) candidate));
  rejects "non-arbiter owner" (fun () -> check (change_item "atomic_groups" 0 (replace "arbiter" (str "gate")) candidate));
  rejects "lost atomic lane" (fun () -> check (change_item "atomic_groups" 0 (replace "commits" (arr [])) candidate));
  rejects "duplicate atomic group membership" (fun () -> check (replace "atomic_groups" (arr
    (items "atomic_groups" candidate @ [replace "id" (str "alias") (List.hd (items "atomic_groups" candidate))])) candidate));
  List.iter (fun (label, exports) -> rejects label (fun () -> check (replace "semantic_exports" (arr exports) candidate)))
    ["hidden output", List.tl (items "semantic_exports" candidate);
     "reordered semantic inventory", List.rev (items "semantic_exports" candidate);
     "aliased semantic inventory", items "semantic_exports" candidate @ [endpoint "true" "out"]];
  rejects "missing node occurrence" (fun () -> check (replace "occurrences" (arr
    (List.filter (fun o -> text "source_path" o <> "/program/declarations/8/assignments/0/value") (items "occurrences" candidate))) candidate));
  rejects "duplicate source occurrence" (fun () -> check (replace "occurrences" (arr
    (List.hd (items "occurrences" candidate) :: items "occurrences" candidate)) candidate));
  rejects "occurrence invented output" (fun () -> check (change_item "occurrences" 4
    (replace "targets" (arr [endpoint "evidence" "absent"])) candidate));
  rejects "occurrence input mistaken as output" (fun () -> check (change_item "occurrences" 4
    (replace "targets" (arr [endpoint "evidence" "samples"])) candidate));
  rejects "nonconstant executable erased as constant" (fun () -> check (change_item "occurrences" 4
    (replace "disposition" (str "constant")) candidate));
  rejects "requirement treated as executable primitive" (fun () -> check (change_item "occurrences" 11
    (fun o -> o |> replace "disposition" (str "executable") |> replace "targets" (arr [endpoint "true" "out"])) candidate));
  List.iter (fun path -> rejects "invalid occurrence pointer" (fun () -> check (change_item "occurrences" 0
    (replace "source_path" (str path)) candidate))) ["relative"; "/"; "/bad~2escape"];
  rejects "invented expected occurrence" (fun () -> I.check_occurrence_inventory ~expected:(expected_inventory @ ["/invented"]) value);
  rejects "missing expected occurrence" (fun () -> I.check_occurrence_inventory ~expected:(List.tl expected_inventory) value);
  rejects "reordered external occurrence inventory" (fun () -> I.check_occurrence_inventory ~expected:(List.rev expected_inventory) value);
  let rec cyclic_inventory = "/cycle" :: cyclic_inventory in
  rejects "cyclic external occurrence inventory" (fun () -> I.check_occurrence_inventory ~expected:cyclic_inventory value);
  (* Changing all local hashes can establish another structural contract, but
     cannot authorize it against the original independently fixed library. *)
  let changed_library = body_mutant 0 (replace "configuration" (obj ["freshness_ticks", Json.int 3])) in
  let changed_model = List.hd (items "models" changed_library) in
  let changed_candidate = repin_library changed_library candidate |> change_item "nodes" 0 (fun n -> repin_node n changed_model) in
  let changed_value = I.of_json ~library:(I.library_of_json changed_library) changed_candidate in
  rejects "self-consistent changed model under original library" (fun () -> check changed_candidate);
  rejects "self-consistent changed model under original authority" (fun () -> I.check_authority ~expected changed_value);
  let changed_uncertainty = body_mutant 8 (fun body -> replace "configuration"
    (replace "on_unknown" (str "continue") (get "configuration" body)) body) in
  let uncertainty_model = List.nth (items "models" changed_uncertainty) 8 in
  let uncertainty_candidate = repin_library changed_uncertainty candidate
    |> change_item "nodes" 8 (fun n -> repin_node n uncertainty_model) in
  let uncertainty_value = I.of_json ~library:(I.library_of_json changed_uncertainty) uncertainty_candidate in
  rejects "self-consistent changed uncertainty under original authority" (fun () -> I.check_authority ~expected uncertainty_value);
  (* The later semantic preservation checker must additionally reject this
     lifecycle change against the original source, even if both libraries are
     explicitly authorized alternatives in a supplied catalog. *)
  (* Two ordinary truth nodes form a well-typed but prohibited immediate cycle. *)
  let not_model = List.hd (items "models" library_raw)
    |> replace "identity" (replace "id" (str "fixture.primitive.not") (get "identity" (List.hd (items "models" library_raw))))
    |> (fun m -> replace "body" ((get "body" m) |> replace "primitive" (str "truth_not") |> replace "configuration" (obj [])) m)
    |> rehash_model in
  let cyclic_library_raw = replace "models" (arr (items "models" library_raw @ [not_model])) library_raw in
  let cyclic_library = I.library_of_json cyclic_library_raw in
  let new_node id = obj ["id", str id; "model", get "identity" not_model; "configuration_digest", get "configuration_digest" not_model] in
  let cyclic_candidate = repin_library cyclic_library_raw candidate
    |> replace "nodes" (arr (items "nodes" candidate @ [new_node "a"; new_node "b"]))
    |> replace "wires" (arr (items "wires" candidate @ [wire (endpoint "a" "out") (endpoint "b" "in"); wire (endpoint "b" "out") (endpoint "a" "in")]))
    |> replace "semantic_exports" (arr (items "semantic_exports" candidate @ [endpoint "a" "out"; endpoint "b" "out"]))
    |> replace "occurrences" (arr (items "occurrences" candidate @ [occurrence "/cycle/a" (endpoint "a" "out"); occurrence "/cycle/b" (endpoint "b" "out")])) in
  rejects "typed combinational scheduling cycle" (fun () -> ignore (I.of_json ~library:cyclic_library cyclic_candidate));
  let phase_candidate = repin_library cyclic_library_raw candidate
    |> replace "nodes" (arr (items "nodes" candidate @ [new_node "a"]))
    |> replace "wires" (arr ((change 5 (replace "producer" (endpoint "a" "out")) (items "wires" candidate)) @ [wire (endpoint "seen" "value") (endpoint "a" "in")]))
    |> replace "semantic_exports" (arr (items "semantic_exports" candidate @ [endpoint "a" "out"]))
    |> replace "occurrences" (arr (items "occurrences" candidate @ [occurrence "/phase/a" (endpoint "a" "out")])) in
  ignore (I.of_json ~library:cyclic_library phase_candidate);
  (* This accepts only the explicit register-write phase boundary, without
     claiming termination or behavioral equivalence of its eventual runtime. *)
  let deep = List.fold_left (fun v _ -> arr [v]) Json.Null (List.init 50 Fun.id) in
  ingress_rejects "deep candidate" (fun () -> check (add "deep" deep candidate));
  ingress_rejects "deep supplied library" (fun () -> check_library (add "deep" deep library_raw));
  ingress_rejects "oversized scalar" (fun () -> check (add "long" (str (String.make 65_537 'x')) candidate));
  ingress_rejects "node budget" (fun () -> check (add "nodes_extra" (arr (List.init 100_001 (fun _ -> Json.Null))) candidate));
  ingress_rejects "integer bit budget" (fun () -> check (add "large" (Json.Int (Z.shift_left Z.one 256)) candidate));
  ingress_rejects "encoded byte budget" (fun () -> check (add "large"
    (arr (List.init 36 (fun _ -> str (String.make 60_000 'x')))) candidate));
  let rec cyclic_json = Json.Array [cyclic_json] in
  ingress_rejects "cyclic programmatic JSON" (fun () -> check (add "cycle" cyclic_json candidate));
  let rec cyclic_spine = Json.Null :: cyclic_spine in
  ingress_rejects "cyclic programmatic array spine" (fun () -> check (add "cycle" (Json.Array cyclic_spine) candidate));
  rejects "raw float" (fun () -> check (add "float" (Json.Float 0.5) candidate));
  rejects "duplicate raw key" (fun () -> check (add "profile" (str I.profile) candidate));
  Printf.printf "policy implementation structural fixture: %d rejection controls; runtime and material acceptance unassessed\n" !rejection_count

let () =
  require (Array.length Sys.argv = 2) "Expected the frozen policy implementation fixture path";
  run (read Sys.argv.(1))
