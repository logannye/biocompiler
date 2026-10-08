open Bioc_wire
open Bioc_policy_component_test_support.Literals

let slot_name = function A.Decision -> "decision" | A.Driver -> "driver"
  | A.Instance _ -> failwith "Unexpected named instance in legacy fixture"
let node_json (value:A.node_ref) = nr (slot_name value.slot) value.node_id
let endpoint_json (value:A.endpoint_ref) = er (slot_name value.node.slot) value.node.node_id value.port_id
let kind_name = function A.Product -> "product" | A.Request -> "request" | A.Authorization -> "authorization"
  | A.Stage_product _ | A.Stage_request _ | A.Stage_authorization _ | A.Stage_event _ -> failwith "Unexpected staged link in legacy fixture"
  | A.Named_link _ -> failwith "Unexpected named link in legacy fixture"
let wire_json = function
  | A.Local_wire {slot;index} -> obj ["kind",str "local";"slot",str (slot_name slot);"index",Json.int index]
  | A.Cross_link kind -> link_wire (kind_name kind)
let swap first second raw = match raw with
  | Json.Array values -> arr (List.mapi (fun index value ->
      if index = first then List.nth values second else if index = second then List.nth values first else value) values)
  | _ -> failwith "Mutation requires a declared ordered inventory"

let run first second =
  let model_a_raw = original_library first and model_b_raw = original_library second in
  let model_a = I.library_of_json model_a_raw and model_b = I.library_of_json model_b_raw in
  let driver_a = driver_component model_a_raw and driver_b = driver_component model_b_raw in
  let decision_a = decision_component model_a_raw false and decision_b = decision_component model_b_raw true in
  let library_a = L.of_json ~library:model_a (library [decision_a;driver_a])
  and library_b = L.of_json ~library:model_b (library [decision_b;driver_b]) in
  let raw_a = rule false decision_a driver_a and raw_b = rule true decision_b driver_b in
  List.iter (fun raw -> ignore (PM.of_json (at ["body";"material_authority"] raw))) [raw_a;raw_b];
  let a = A.of_json ~components:library_a raw_a and b = A.of_json ~components:library_b raw_b in
  require (Json.equal driver_a driver_b) "Shared complete driver input changed across families";
  require (C.fingerprint (A.component a A.Driver) = C.fingerprint (A.component b A.Driver))
    "Identical driver acquired source-dependent identity";
  require (A.model_library_digest a = I.library_digest model_a &&
           A.model_library_digest b = I.library_digest model_b &&
           A.component_library_digest a = L.fingerprint library_a &&
           A.component_library_digest b = L.fingerprint library_b)
    "Original component/model decoding contexts were lost";
  List.iter (fun (raw,value,state_reading,node_count,wire_count,export_count,offset,leader,leader_sequence) ->
    require (Json.equal raw (A.to_json value) && A.fingerprint value = Canonical.fingerprint raw)
      "Assembly rule did not preserve the complete supplied original";
    require (P.content_fingerprint (A.identity value) = Canonical.fingerprint (get "body" raw))
      "Rule Model identity does not bind the full material and ordered signal premise";
    require (List.map node_json (A.node_order value) = global_nodes state_reading &&
      List.length (A.node_order value) = node_count) "Literal global node interleaving differs";
    require (List.map wire_json (A.wire_order value) = global_wires state_reading &&
      List.length (A.wire_order value) = wire_count) "Literal global local/link wire order differs";
    require (List.map endpoint_json (A.export_order value) = global_exports state_reading &&
      List.length (A.export_order value) = export_count) "All outputs must retain the literal global order";
    require (List.map (fun (link:A.link) -> kind_name link.kind) (A.links value) =
      ["product";"request";"authorization"]) "Link ownership/order changed";
    require (List.map (fun (input:A.input_ref) -> input.input_id) (A.input_order value) = ["condition";"feedback"])
      "External evidence/feedback input identities or order changed";
    require (List.map (fun (group:A.group_ref) -> slot_name group.slot,group.group_id) (A.group_order value) =
      ["decision","exclusive_selection"]) "Atomic action ownership split or duplicated";
    require ((A.join value).offset = offset && (A.join value).left = A.Decision && (A.join value).right = A.Driver)
      "Declared adjacent placement changed";
    require (List.map (fun (binding:A.root_binding) -> slot_name binding.slot,binding.source_id)
      (A.root_bindings value) = ["decision",leader;"driver","driver_body"])
      "Local material root ownership changed";
    let authority = A.material_authority value in
    require (PM.member_order authority = ["payload"] && List.length (PM.members authority) = 1)
      "Original one-member product authority changed";
    require (List.map (fun source -> CT.Root_source.id source,N.sequence (CT.Root_source.molecule source))
      (PT.sources (PM.template authority)) = ["driver_body","AUGGCUUAAGGAAAA";leader,leader_sequence])
      "Exact local source bodies were replaced by a final output or same-peptide substitute";
    require (List.for_all (fun (carrier:A.link_carrier) -> carrier.producer_site = 0 &&
      carrier.consumer_site = 0 && carrier.join_id = "leader_to_driver") (A.link_carriers value))
      "Literal link carrier site/join relation changed")
    [raw_a,a,false,15,22,21,2,"leader_A","CC";
     raw_b,b,true,17,25,23,3,"leader_B","CGC"];
  require (List.map wire_json (List.filteri (fun index _ -> index >= 19) (A.wire_order b)) =
    [link_wire "product";link_wire "request";link_wire "authorization";local_wire 19;local_wire 20;local_wire 21])
    "B links must be interleaved before the three final internal state-dependent wires";
  (* The rule is original ordering authority. A different legal interleaving is
     a different declaration, not an automatic source/candidate correspondence. *)
  let other_interleaving = raw_b |> put ["body";"wire_order"]
    (arr (List.map local_wire [0;1;2;3;4;5;6;7;8;9;10;11;12;13;14;15;16;17;18;19;20;21] @
          List.map link_wire ["product";"request";"authorization"])) |> repin in
  let reordered = A.of_json ~components:library_b other_interleaving in
  require (A.fingerprint reordered <> A.fingerprint b &&
    Json.equal (A.to_json reordered) other_interleaving) "Changed legal global order was erased from original identity";
  let reject ?message label raw = rejected ?message "policy_component_assembly_rule" label
    (fun () -> A.of_json ~components:library_a raw) in
  let changed ?message label keys value = reject ?message label (raw_a |> put keys value |> repin) in
  reject ~message:"Original assembly identity must pin its complete supplied body."
    "Rule body mutated without refreshing original identity"
    (put ["body";"join";"offset"] (Json.int 3) raw_a);
  rejected ~message:"Assembly component is absent from the exact original component library."
    "policy_component_assembly_rule" "Family A selection under unrelated complete B library"
    (fun () -> A.of_json ~components:library_b raw_a);
  changed ~message:"Assembly component is absent from the exact original component library."
    "Stale complete component pin" ["body";"components";"0";"component";"content_fingerprint"] (str (String.make 64 '0'));
  changed "Duplicate component owner" ["body";"components";"1";"slot"] (str "decision");
  changed "Unmodeled helper component slot" ["body";"components";"1";"slot"] (str "helper");
  changed ~message:"Assembly link direction or full signal type differs from its actual ports."
    "Wrong cross-link signal" ["body";"links";"0";"signal_type"] (str "truth_value");
  changed ~message:"Assembly link kind has the wrong component ownership or scope relation."
    "Executor product is not encounter-scoped" ["body";"links";"0";"scope"] (str "same_encounter_slot");
  changed ~message:"Assembly link kind has the wrong component ownership or scope relation."
    "Encounter request cannot claim executor broadcast" ["body";"links";"1";"scope"] (str "immutable_executor_broadcast");
  reject ~message:"Assembly link direction or full signal type differs from its actual ports." "Direction-reversed request"
    (raw_a |> put ["body";"links";"1";"producer"] (br "driver" "request")
           |> put ["body";"links";"1";"consumer"] (br "decision" "request") |> repin);
  changed "Wrong exact authorization boundary" ["body";"links";"2";"producer"] (br "decision" "request");
  changed "Endpoint alias is not the named original boundary" ["body";"links";"2";"producer";"boundary"] (str "evidence");
  changed "Unknown same-slot conversion" ["body";"transport_profile"] (str "biocompiler.policy_buffered_transport.v0.1");
  changed "Lost layout identity" ["body";"slot_layout";"id"] (str "foreign-layout");
  changed "Different slot cardinality" ["body";"slot_layout";"slots"] (Json.int 1);
  List.iter (fun key ->
    let rows = items key (get "body" raw_a) in
    changed ("Missing complete " ^ key) ["body";key] (arr (List.tl rows));
    let duplicate = if List.length rows = 1 then List.hd rows :: rows else
      change (List.length rows - 1) (fun _ -> List.hd rows) rows in
    changed ("Duplicate complete " ^ key) ["body";key] (arr duplicate))
    ["components";"links";"node_order";"wire_order";"input_order";"group_order";"export_order";
     "root_bindings";"link_carriers"];
  reject "Changed local node order" (raw_a |> edit ["body";"node_order"] (swap 0 1) |> repin);
  reject "Changed local wire order" (raw_a |> edit ["body";"wire_order"] (swap 0 1) |> repin);
  reject "Changed local output order" (raw_a |> edit ["body";"export_order"] (swap 0 1) |> repin);
  changed "Duplicate external global identity" ["body";"input_order";"1";"id"] (str "condition");
  changed "Cross-component atomic ownership" ["body";"group_order";"0";"slot"] (str "driver");
  changed "Wrong bound source body" ["body";"root_bindings";"0";"source"] (str "driver_body");
  changed "Join offset uses a different root length" ["body";"join";"offset"] (Json.int 3);
  changed "Join points to absent transform" ["body";"join";"step"] (str "absent");
  changed "Join points to absent product port" ["body";"join";"port"] (str "absent");
  changed "Join orientation is reversed" ["body";"join";"left"] (str "driver");
  changed "Absent producer carrier site" ["body";"link_carriers";"0";"producer_site"] (Json.int 1);
  changed "Absent consumer carrier site" ["body";"link_carriers";"1";"consumer_site"] (Json.int 1);
  changed "Carrier refers to unrelated join" ["body";"link_carriers";"2";"join"] (str "other-join");
  (* These changed originals are valid PM declarations before rule-specific
     checks; a stale component premise must not gain new authority from rehashing. *)
  let material_changed message label change_material =
    let candidate = edit ["body";"material_authority"] change_material raw_a |> repin in
    ignore (PM.of_json (at ["body";"material_authority"] candidate));
    reject ~message label candidate in
  let root_mismatch = "Assembly template root differs from the exact selected component root beyond its declared source-ID rename." in
  material_changed root_mismatch "Synonymous full root body still differs from selected component"
    (put ["template";"sources";"0";"molecule";"sequence"] (str "AUGGCCUAAGGAAAA"));
  material_changed root_mismatch "Same bases with changed nominal root cap are a different original"
    (put ["template";"sources";"0";"molecule";"chemistry";"cap";"identity";"accession"] (str "different_cap"));
  material_changed root_mismatch "Same root sequence but altered feature authority"
    (put ["template";"sources";"0";"molecule";"features";"0";"kind"] (str "uninterpreted_region"));
  material_changed "Assembly construction must concatenate the two complete bound roots in declared order without slicing."
    "Reversed whole-root construction order"
    (edit ["template";"steps";"0";"operation";"inputs"] (swap 0 1));
  material_changed "Assembly expected product differs from the complete selected driver product."
    "Equal peptide does not replace the complete original product provenance"
    (put ["members";"0";"product";"provenance";"reason"] (str "Different supplied product authority"));
  material_changed "Assembly feature transition must account for every original root feature exactly once without added annotations."
    "Missing original feature disposition"
    (edit ["template";"steps";"0";"ports";"0";"feature_transition";"dispositions"]
      (fun value -> arr (List.tl (Json.array value))));
  material_changed "Assembly chemistry transition must account for all ten original root facets exactly once."
    "Missing original chemistry facet disposition"
    (edit ["template";"steps";"0";"ports";"0";"chemistry_transition";"dispositions"]
      (fun value -> arr (List.tl (Json.array value))));
  (* A valid newly pinned B component can expose evidence at the boundary, but
     it cannot make that endpoint the actual state-dependent gate guard. *)
  let wrong_guard_component = decision_b
    |> put ["body";"fragment";"boundary_ports";"2";"endpoint"] (endpoint "evidence" "value") |> repin in
  ignore (C.of_json ~library:model_b wrong_guard_component);
  let wrong_guard_library = L.of_json ~library:model_b (library [wrong_guard_component;driver_b]) in
  let wrong_guard_rule = rule true wrong_guard_component driver_b in
  rejected ~message:"Assembly authorization must retain the initiating gate's actual guard-producing endpoint."
    "policy_component_assembly_rule" "B boundary guard differs from the actual initiating gate guard"
    (fun () -> A.of_json ~components:wrong_guard_library wrong_guard_rule);
  (* Full component identity, including carrier authority, remains original.
     A current-model and current-root library is insufficient for an old pin. *)
  let changed_carrier_component = driver_a
    |> put ["body";"carriers";"7";"sites";"0"] (site "driver_body" "utr3" 9 11) |> repin in
  ignore (C.of_json ~library:model_a changed_carrier_component);
  let changed_carrier_library = L.of_json ~library:model_a (library [decision_a;changed_carrier_component]) in
  rejected ~message:"Assembly component is absent from the exact original component library."
    "policy_component_assembly_rule" "Same roots/models with changed product-boundary carrier cannot satisfy old component pin"
    (fun () -> A.of_json ~components:changed_carrier_library raw_a);
  List.iter (fun key ->
    rejected "unknown_field" ("Closed rule field: " ^ key) (fun () ->
      A.of_json ~components:library_a (add key Json.Null raw_a))) ["candidate";"source";"provider"];
  rejected "policy_component_assembly_rule" "Raw float before material/model traversal" (fun () ->
    A.of_json ~components:library_a (put ["body";"join";"offset"] (Json.Float 2.) raw_a));
  let rec cyclic = Json.Array [cyclic] in
  rejected "molecular_cycle" "Cyclic original rule" (fun () -> A.of_json ~components:library_a cyclic)

let () =
  try
    require (Array.length Sys.argv = 3) "Expected the two original A/B model-library fixtures";
    run (read Sys.argv.(1)) (read Sys.argv.(2));
    Printf.printf "component assembly rule: %d literal/source controls passed\n" !checks
  with Diagnostic.Error value ->
    Printf.eprintf "Diagnostic.Error(code=%s,path=%s,message=%s)\n" value.code
      (match value.path with None -> "<none>" | Some path -> path) value.message;
    exit 1
