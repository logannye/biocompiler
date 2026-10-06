open Bioc_wire
module F = Bioc_domain.Policy_component_fragment
module I = Bioc_domain.Policy_implementation
module C = Bioc_domain.Policy_component_material
module L = Bioc_domain.Policy_component_library
module P = Bioc_domain.Pinned_identity
module N = Bioc_domain.Molecule
module R = Bioc_domain.Construction.Root_source
module MC = Bioc_domain.Molecule_coordinates
module MR = Bioc_domain.Molecular_record
module PM = Bioc_domain.Policy_mrna_structure

let checks = ref 0
let require condition message = incr checks; if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let arr value = Json.Array value
let get key value = Json.field key (Json.object_fields value)
let items key value = Json.array (get key value)
let replace key replacement value = obj (List.map (fun (name, item) ->
  name, (if key = name then replacement else item)) (Json.object_fields value))
let change index transform values = List.mapi (fun i value -> if index = i then transform value else value) values
let add key item value = obj ((key, item) :: Json.object_fields value)
let endpoint node port = obj ["node", str node; "port", str port]
let wire source output target input = obj ["producer", endpoint source output; "consumer", endpoint target input]
let boundary id direction signal_type node port = obj ["id", str id;
  "direction", str direction; "signal_type", str signal_type; "endpoint", endpoint node port]
let external_slot id kind node port = obj ["id", str id; "kind", str kind; "consumer", endpoint node port]
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size = in_channel_length channel in
    require (size <= 4_000_000) "Original fixture exceeds bounded input";
    Json.parse (really_input_string channel size))

(* Only original model declarations are borrowed. Node, wire, interface, group
   and output expectations below are hand-authored, never candidate-derived. *)
let original_library fixture = get "implementation_library" (get "implementation_request" (get "request" fixture))
let model library id = match List.find_opt (fun value ->
    get "id" (get "identity" value) = str id) (items "models" library) with
  | Some value -> value
  | None -> failwith ("Original model absent: " ^ id)
let node library id model_id = obj ["id", str id; "model", model library model_id]
let fragment id nodes wires boundary_ports external_slots atomic_groups semantic_exports = obj [
  "schema_version", str "biocompiler.policy_component_fragment.v0.1";
  "profile", str "biocompiler.policy_exact_fragment.v0.1";
  "primitive_profile", str "biocompiler.policy_truth_primitives.v0.1";
  "observable_profile", str "biocompiler.policy_truth_observables.v0.1";
  "phase_profile", str "biocompiler.policy_primitive_execution.v0.1";
  "id", str id; "version", str "1";
  "slot_layout", obj ["id", str "encounters"; "slots", Json.int 2];
  "nodes", arr nodes; "wires", arr wires; "boundary_ports", arr boundary_ports;
  "external_slots", arr external_slots; "atomic_groups", arr atomic_groups;
  "semantic_exports", arr semantic_exports]

let driver library = fragment "fixture.driver"
  [node library "product" "exclusion.primitive.product";
   node library "attempt" "exclusion.primitive.attempt"] []
  [boundary "product" "output" "product_symbol" "product" "out";
   boundary "request" "input" "effect_request" "attempt" "request";
   boundary "authorization" "input" "truth_value" "attempt" "authorization"]
  [external_slot "feedback" "feedback" "attempt" "feedback"] []
  [endpoint "product" "out"; endpoint "attempt" "events"; endpoint "attempt" "snapshot"]

let decision library state_reading =
  let specifications = [
    "evidence", "exclusion.primitive.evidence";
    "select_edge", "exclusion.primitive.edge"; "not", "exclusion.primitive.not";
    "exclude_edge", "exclusion.primitive.edge";
    "true", "exclusion.primitive.true"; "false", "exclusion.primitive.false";
    "select_gate", "exclusion.primitive.gate"; "exclude_gate", "exclusion.primitive.gate";
    "arbiter", "exclusion.primitive.arbiter";
    "select_commit", "exclusion.primitive.select_commit";
    "exclude_commit", "exclusion.primitive.exclude_commit";
    "selected", "exclusion.primitive.register"; "excluded", "exclusion.primitive.register"] @
    (if state_reading then ["selected_not", "exclusion.primitive.not"; "select_guard", "state.primitive.all2"] else []) in
  let nodes = List.map (fun (id, model_id) -> node library id model_id) specifications in
  let guard_node, guard_port = if state_reading then "select_guard", "out" else "evidence", "value" in
  let false_node, false_port = if state_reading then "selected", "value" else "false", "out" in
  let wires = [
    wire "evidence" "value" "select_edge" "in";
    wire "evidence" "value" "not" "in";
    wire "not" "out" "exclude_edge" "in";
    wire "select_edge" "events" "select_gate" "on";
    wire "exclude_edge" "events" "exclude_gate" "on";
    wire guard_node guard_port "select_gate" "guard";
    wire "not" "out" "exclude_gate" "guard";
    wire "select_gate" "candidate" "arbiter" "in0";
    wire "arbiter" "out0" "select_commit" "grant";
    wire "true" "out" "select_commit" "value0";
    wire "select_commit" "write0" "selected" "write0";
    wire false_node false_port "select_commit" "value1";
    wire "select_commit" "write1" "excluded" "write0";
    wire "exclude_gate" "candidate" "arbiter" "in1";
    wire "arbiter" "out1" "exclude_commit" "grant";
    wire "false" "out" "exclude_commit" "value0";
    wire "exclude_commit" "write0" "selected" "write1";
    wire "true" "out" "exclude_commit" "value1";
    wire "exclude_commit" "write1" "excluded" "write1"] @
    (if state_reading then [wire "selected" "value" "selected_not" "in";
       wire "evidence" "value" "select_guard" "in0";
       wire "selected_not" "out" "select_guard" "in1"] else []) in
  let exports = [endpoint "evidence" "value"; endpoint "evidence" "updated";
    endpoint "select_edge" "events"; endpoint "not" "out"; endpoint "exclude_edge" "events";
    endpoint "true" "out"; endpoint "false" "out";
    endpoint "select_gate" "candidate"; endpoint "exclude_gate" "candidate";
    endpoint "arbiter" "out0"; endpoint "arbiter" "out1";
    endpoint "select_commit" "write0"; endpoint "select_commit" "write1"; endpoint "select_commit" "request0";
    endpoint "exclude_commit" "write0"; endpoint "exclude_commit" "write1";
    endpoint "selected" "value"; endpoint "excluded" "value"] @
    (if state_reading then [endpoint "selected_not" "out"; endpoint "select_guard" "out"] else []) in
  fragment (if state_reading then "fixture.decision.state" else "fixture.decision.exclusion") nodes wires
    [boundary "product" "input" "product_symbol" "select_commit" "product0";
     boundary "request" "output" "effect_request" "select_commit" "request0";
     boundary "authorization" "output" "truth_value" guard_node guard_port]
    [external_slot "condition" "evidence" "evidence" "samples"]
    [obj ["id", str "exclusive_selection"; "arbiter", str "arbiter";
       "commits", arr [str "select_commit"; str "exclude_commit"]]] exports

(* Original artificial material declarations. No finished RNA or producer output
   supplies these roots, sites, geometry, chemistry or expected product. *)
let pin kind id digest = obj ["schema_version", str "biocompiler.component_identity.v0.1";
  "kind", str kind; "id", str id; "version", str "1"; "content_fingerprint", str digest]
let notice = str "Artificial local component fixture; supplied software premise, not empirical evidence."
let provenance = obj ["schema_version", str "biocompiler.molecular_declaration_provenance.v0.1";
  "status", str "declared";
  "authority", arr [pin "source" "fixture.local-material.notice" (Canonical.fingerprint notice)];
  "locator", str "independent native test literal"; "reason", notice]
let span first last = obj ["schema_version", str "biocompiler.molecule_index_span.v0.1";
  "start", Json.int first; "end", Json.int last]
let path space first last = obj ["schema_version", str "biocompiler.molecule_coordinate_path.v0.1";
  "space_id", str space; "spans", arr [span first last]; "strand", str "+"]
let space id length = obj ["schema_version", str "biocompiler.molecule_coordinate_space.v0.1";
  "id", str id; "alphabet", str "RNA"; "axis", str "5prime_to_3prime";
  "topology", str "linear"; "length", Json.int length]
let chemical accession = obj ["schema_version", str "biocompiler.chemical_identity.v0.1";
  "namespace", str "software_fixture.chemical"; "accession", str accession; "version", str "1"]
let claim accession = obj ["schema_version", str "biocompiler.chemistry_claim.v0.1";
  "status", str "declared"; "identity", chemical accession; "provenance", provenance]
let chemistry frame driver_root =
  let tail = obj ["schema_version", str "biocompiler.tail_declaration.v0.1";
    "status", str "declared";
    "placement", str (if driver_root then "represented_terminal" else "absent");
    "length", obj ["schema_version", str "biocompiler.tail_length.v0.1";
      "mode", str "exact"; "exact", Json.int (if driver_root then 4 else 0);
      "lower", Json.Null; "upper", Json.Null];
    "path", (if driver_root then path frame 11 15 else Json.Null); "provenance", provenance] in
  obj ["schema_version", str "biocompiler.molecule_chemistry.v0.1";
    "cap", claim "artificial_cap"; "start_end", claim "hydroxyl";
    "finish_end", claim "hydroxyl"; "modifications", arr [];
    "modification_inventory_status", str "declared";
    "modification_inventory_provenance", provenance; "terminal_tail", tail]
let feature frame id kind first last reading_frame =
  obj ["schema_version", str "biocompiler.molecule_feature.v0.1"; "id", str id;
    "kind", str kind; "path", path frame first last; "provenance", provenance;
    "reading_frame", reading_frame]
let root id sequence driver_root =
  let frame = id ^ ".frame" and length = String.length sequence in
  let geometry = space frame length in
  let features = if driver_root then [
      feature frame "cds" "coding_sequence" 0 9 (Json.int 0);
      feature frame "poly_a" "poly_a_tail" 11 15 Json.Null;
      feature frame "utr3" "three_prime_utr" 9 11 Json.Null]
    else [feature frame "utr5" "five_prime_utr" 0 length Json.Null] in
  obj ["schema_version", str "biocompiler.construction_root_source.v0.1";
    "id", str id; "provenance", provenance;
    "molecule", obj ["schema_version", str "biocompiler.circuit_molecule.v0.1";
      "id", str (id ^ ".molecule"); "form", str "primary_rna";
      "space", geometry; "sequence", str sequence; "sequence_extent", str "complete";
      "coding_status", str (if driver_root then "coding" else "noncoding");
      "assembly", arr [obj ["schema_version", str "biocompiler.assembly_origin.v0.1";
        "id", str (id ^ ".self"); "destination", path frame 0 length;
        "source_space", geometry; "source_path", path frame 0 length; "provenance", provenance]];
      "features", arr features; "chemistry", chemistry frame driver_root; "provenance", provenance]]
let expected_product = obj [
  "identity", pin "source" "payload.artificial.product"
    "c7434883f345ffc2100dd9e3750afbbee436ba7535cf5fb26b9be706ce413c9b";
  "sequence", str "MA";
  "translation_policy", obj ["schema_version", str "biocompiler.translation_policy.v0.1";
    "profile", str "ordinary_cds"; "genetic_code", str "ncbi_standard_v1"; "recodings", arr []];
  "provenance", provenance]
let target kind id = obj ["kind", str kind; "id", str id]
let indexed kind index = obj ["kind", str kind; "index", Json.int index]
let triple id = [target "primitive" id; target "configuration" id; target "replication" id]
let driver_targets = List.concat [triple "product"; triple "attempt"] @ [
  target "external_slot" "feedback"; target "boundary_port" "product";
  target "boundary_port" "request"; target "boundary_port" "authorization";
  indexed "semantic_export" 0; indexed "semantic_export" 1; indexed "semantic_export" 2;
  obj ["kind", str "slot_layout"]]
let decision_targets state_reading =
  List.concat_map triple (["evidence"; "select_edge"; "not"; "exclude_edge"; "true"; "false";
    "select_gate"; "exclude_gate"; "arbiter"; "select_commit"; "exclude_commit"; "selected"; "excluded"] @
    if state_reading then ["selected_not"; "select_guard"] else []) @
  List.map (indexed "local_wire") ([0;1;2;3;4;5;6;7;8;9;10;11;12;13;14;15;16;17;18] @
    if state_reading then [19;20;21] else []) @
  [target "external_slot" "condition"; target "boundary_port" "product";
   target "boundary_port" "request"; target "boundary_port" "authorization";
   target "atomic_group" "exclusive_selection"] @
  List.map (indexed "semantic_export") ([0;1;2;3;4;5;6;7;8;9;10;11;12;13;14;15;16;17] @
    if state_reading then [18;19] else []) @ [obj ["kind", str "slot_layout"]]
let site root_id feature_id first last = obj ["root", str root_id;
  "feature", str feature_id; "path", path (root_id ^ ".frame") first last]
let driver_carriers = List.mapi (fun index disposition ->
  let material_site = if index < 3 || index = 7 || index = 10 then site "driver_body" "cds" 0 9
    else site "driver_body" "utr3" 9 11 in
  obj ["target", disposition; "sites", arr [material_site]]) driver_targets
let input id external_slot = obj ["kind", str "input"; "id", str id; "external_slot", str external_slot]
let capacity id owner_kind owner unit scope minimum = obj ["kind", str "capacity";
  "id", str id; "owner", obj ["kind", str owner_kind; "id", str owner];
  "unit", str unit; "scope", str scope; "minimum", Json.int minimum]
let driver_prerequisites = [input "feedback_input" "feedback";
  capacity "feedback_rows" "external_slot" "feedback" "input_rows_per_tick" "per_executor" 1;
  capacity "active" "node" "attempt" "active_attempt_records" "per_encounter_slot" 8;
  capacity "retained" "node" "attempt" "retained_correlation_records" "per_executor" 1;
  capacity "attempt_timers" "node" "attempt" "timer_cells" "per_encounter_slot" 8]
let decision_prerequisites = [input "condition_input" "condition";
  capacity "condition_rows" "external_slot" "condition" "input_rows_per_tick" "per_encounter_slot" 1;
  capacity "samples" "node" "evidence" "evidence_records" "per_encounter_slot" 1;
  capacity "freshness_timer" "node" "evidence" "timer_cells" "per_encounter_slot" 1;
  capacity "select_edge_memory" "node" "select_edge" "edge_history_cells" "per_encounter_slot" 1;
  capacity "exclude_edge_memory" "node" "exclude_edge" "edge_history_cells" "per_encounter_slot" 1;
  capacity "selected_memory" "node" "selected" "truth_cells" "per_encounter_slot" 1;
  capacity "excluded_memory" "node" "excluded" "truth_cells" "per_encounter_slot" 1]
let component id fragment local_root carriers products prerequisites =
  let body = obj ["fragment", fragment; "root", local_root; "carriers", arr carriers;
    "products", arr products; "provider_requirements", arr prerequisites] in
  obj ["schema_version", str "biocompiler.policy_component_material.v0.1";
    "profile", str "biocompiler.policy_exact_local_material.v0.1";
    "identity", pin "model" id (Canonical.fingerprint body); "body", body]
let driver_component library = component "fixture.driver.material" (driver library)
  (root "driver_body" "AUGGCUUAAGGAAAA" true) driver_carriers
  [obj ["node", str "product"; "symbol", str "fixture.product.alpha";
    "root", str "driver_body"; "cds_feature", str "cds"; "expected", expected_product]] driver_prerequisites
let decision_component library state_reading =
  let id, sequence = if state_reading then "leader_B", "CGC" else "leader_A", "CC" in
  let carriers = List.map (fun disposition -> obj ["target", disposition;
    "sites", arr [site id "utr5" 0 (String.length sequence)]]) (decision_targets state_reading) in
  component (if state_reading then "fixture.decision.state.material" else "fixture.decision.exclusion.material")
    (decision library state_reading) (root id sequence false) carriers [] decision_prerequisites

let rec at keys raw = match keys with [] -> raw | key :: tail ->
  at tail (match raw with Json.Array values -> List.nth values (int_of_string key) | _ -> get key raw)
let rec edit keys transform raw = match keys with [] -> transform raw | key :: tail ->
  match raw with Json.Array values -> arr (change (int_of_string key) (edit tail transform) values)
  | _ -> replace key (edit tail transform (get key raw)) raw
let put keys value = edit keys (fun _ -> value)
let repin raw = edit ["identity"; "content_fingerprint"]
  (fun _ -> str (Canonical.fingerprint (get "body" raw))) raw
let rejected ?message code label run =
  incr checks;
  match run () with
  | _ -> failwith ("Mutation accepted: " ^ label)
  | exception Diagnostic.Error value ->
      if value.code <> code || (match message with None -> false | Some expected -> value.message <> expected)
      then failwith ("Wrong rejection: " ^ label ^ ": " ^ value.code ^ ": " ^ value.message)

let library components = obj ["schema_version", str "biocompiler.policy_component_library.v0.1";
  "profile", str "biocompiler.policy_exact_component_library.v0.1"; "components", arr components]
let run first second =
  let a_raw = original_library first and b_raw = original_library second in
  let a = I.library_of_json a_raw and b = I.library_of_json b_raw in
  let da_raw = driver_component a_raw and db_raw = driver_component b_raw in
  let aa_raw = decision_component a_raw false and bb_raw = decision_component b_raw true in
  (* Standalone prerequisites are positively decoded outside every expected
     component rejection; malformed molecules are not carrier evidence. *)
  List.iter (fun raw ->
    let original = at ["body"; "root"] raw in
    require (Json.equal (R.to_json (R.of_json original)) original) "Literal root normalization changed authority";
    ignore (F.of_json ~library:(if raw = bb_raw then b else a) (at ["body"; "fragment"] raw)))
    [da_raw; aa_raw; bb_raw];
  let da = C.of_json ~library:a da_raw and db = C.of_json ~library:b db_raw in
  let aa = C.of_json ~library:a aa_raw and bb = C.of_json ~library:b bb_raw in
  require (Json.equal da_raw db_raw && C.fingerprint da = C.fingerprint db)
    "Complete driver material definition changed between original families";
  require (I.library_digest a <> I.library_digest b &&
    C.model_library_digest da = I.library_digest a && C.model_library_digest db = I.library_digest b)
    "Contextual model membership was lost or contaminated reusable identity";
  List.iter (fun (value, original, count, targets, sequence) ->
    require (Json.equal (C.to_json value) original && C.fingerprint value = Canonical.fingerprint original)
      "Complete component roundtrip changed supplied authority";
    require (List.length (C.carriers value) = count &&
      List.map (fun (row:C.carrier) -> C.target_to_json row.target) (C.carriers value) = targets)
      "Independent literal target inventory changed";
    require (N.sequence (R.molecule (C.root value)) = sequence) "Independent local spelling changed")
    [da,da_raw,14,driver_targets,"AUGGCUUAAGGAAAA";
     aa,aa_raw,82,decision_targets false,"CC"; bb,bb_raw,93,decision_targets true,"CGC"];
  require (List.map N.Feature.id (N.features (R.molecule (C.root da))) = ["cds";"poly_a";"utr3"])
    "Local feature identity order changed";
  require (List.map (fun (value:C.product) -> value.node_id,value.symbol,value.root_id,value.cds_feature)
    (C.products da) = ["product","fixture.product.alpha","driver_body","cds"] &&
    C.products aa = [] && C.products bb = []) "Product declaration inventory changed";
  let product = (List.hd (C.products da)).expected in
  require (product.sequence = "MA" && P.kind product.identity = P.Source &&
    Json.equal (P.to_json product.identity) (get "identity" expected_product)) "Complete Source product pin changed";
  require (P.content_fingerprint product.identity = Canonical.fingerprint (obj [
    "schema_version",str "biocompiler.policy_mrna_product_content.v0.1";
    "alphabet",str "protein";"sequence_extent",str "complete";"sequence",str "MA"]))
    "Independent MA content identity changed";
  require (List.length (C.provider_requirements da) = 5 &&
    List.length (C.provider_requirements aa) = 8 && List.length (C.provider_requirements bb) = 8)
    "Literal static prerequisites changed";
  List.iter (fun value -> match value with
    | C.Input {id;external_slot} -> require (id="feedback_input" && external_slot="feedback") "Wrong driver input prerequisite"
    | C.Capacity {id;scope;minimum;_} ->
        let expected = List.assoc id ["feedback_rows",("per_executor",1);"active",("per_encounter_slot",8);
          "retained",("per_executor",1);"attempt_timers",("per_encounter_slot",8)] in
        require ((Bioc_domain.Policy_material_contract.resource_scope_name scope,minimum)=expected)
          "Resource scope was incorrectly derived from encounter replication") (C.provider_requirements da);
  let la_raw = library [aa_raw;da_raw] and lb_raw = library [bb_raw;db_raw] in
  let la = L.of_json ~library:a la_raw and lb = L.of_json ~library:b lb_raw in
  require (Json.equal (L.to_json la) la_raw && Json.equal (L.to_json lb) lb_raw &&
    L.fingerprint la <> L.fingerprint lb) "Original libraries lost exact distinct ordered identities";
  require (List.map (fun value -> P.id (C.identity value)) (L.components la) =
    ["fixture.decision.exclusion.material";"fixture.driver.material"]) "Library component order changed";
  require (L.model_library_digest la = I.library_digest a && L.model_library_digest lb = I.library_digest b)
    "Library decoding context changed";
  (match L.find la (C.identity da), L.find lb (C.identity da) with
   | Some left, Some right -> require (C.fingerprint left=C.fingerprint right) "Exact driver lookup changed between originals"
   | _ -> failwith "Exact shared driver pin was not found");
  let check raw = ignore (C.of_json ~library:a raw) in
  let bad ?message label raw = rejected ?message "policy_component_material" label (fun () -> check (repin raw)) in
  let carrier index transform = edit ["body";"carriers";string_of_int index] transform da_raw in
  bad ~message:"Local material carriers must preserve the exhaustive ordered target inventory."
    "missing configuration carrier" (edit ["body";"carriers"] (fun raw ->
    arr (List.filteri (fun index _ -> index<>4) (Json.array raw))) da_raw);
  bad "extra duplicated target" (edit ["body";"carriers"] (fun raw -> arr (List.hd (Json.array raw)::Json.array raw)) da_raw);
  bad "wrong valid target order" (edit ["body";"carriers"] (fun raw -> match Json.array raw with
    | x::y::tail -> arr (y::x::tail) | _ -> assert false) da_raw);
  bad "absent target node" (carrier 4 (put ["target";"id"] (str "missing")));
  bad "boundary name is not external slot" (carrier 8 (put ["target";"kind"] (str "external_slot")));
  bad "out-of-range local wire" (edit ["body";"carriers";"39";"target"]
    (fun _ -> indexed "local_wire" 19) aa_raw);
  bad "out-of-range export" (carrier 10 (put ["target";"index"] (Json.int 3)));
  bad "empty sites" (carrier 0 (replace "sites" (arr [])));
  bad "duplicate same site" (carrier 0 (edit ["sites"] (fun raw -> arr [List.hd (Json.array raw);List.hd (Json.array raw)])));
  bad "absent root site" (carrier 0 (put ["sites";"0";"root"] (str "absent")));
  bad "absent feature site" (carrier 0 (put ["sites";"0";"feature"] (str "absent")));
  bad ~message:"Local material site must equal the complete actual feature path."
    "in-bounds subset instead of exact feature" (carrier 0 (put ["sites";"0";"path";"spans";"0";"end"] (Json.int 8)));
  bad "wrong space identity" (carrier 0 (put ["sites";"0";"path";"space_id"] (str "leader_A.frame")));
  bad "reversed carrier path" (carrier 0 (put ["sites";"0";"path";"strand"] (str "-")));
  rejected "unknown_field" "provider cannot replace a feature carrier" (fun () -> check (repin
    (carrier 0 (add "provider" (str "memory")))));
  let two_sites = carrier 0 (replace "sites" (arr [site "driver_body" "cds" 0 9;site "driver_body" "utr3" 9 11])) |> repin in
  ignore (C.of_json ~library:a two_sites);
  require (C.fingerprint (C.of_json ~library:a two_sites) <> C.fingerprint da)
    "Distinct original local sites collapsed";
  bad "missing driver product" (put ["body";"products"] (arr []) da_raw);
  bad "extra decision product" (put ["body";"products"] (at ["body";"products"] da_raw) aa_raw);
  List.iter (fun (field,value) -> bad ("wrong product "^field)
    (put ["body";"products";"0";field] (str value) da_raw))
    ["node","attempt";"symbol","different.product";"root","leader_A";"cds_feature","utr3"];
  let frame_one = put ["body";"root";"molecule";"features";"0";"reading_frame"] (Json.int 1) da_raw in
  ignore (R.of_json (at ["body";"root"] frame_one));
  bad ~message:"Local product requires a coding-sequence feature with reading frame zero."
    "source-valid nonzero product reading frame" frame_one;
  List.iter (fun (status,expected) ->
    let changed = put ["body";"root";"molecule";"coding_status"] (str status) da_raw in
    let molecular = R.of_json (at ["body";"root"] changed) in
    require (N.coding_status (R.molecule molecular)=expected &&
      N.Feature.kind (List.hd (N.features (R.molecule molecular)))="coding_sequence")
      "Noncoding/unknown molecular positive did not reach the intended local boundary";
    bad ~message:"Local product requires an explicitly coding root."
      ("declared product on "^status^" root") changed) ["noncoding",N.Noncoding;"unknown",N.Unknown];
  bad "stale complete product content" (put ["body";"products";"0";"expected";"identity";"content_fingerprint"]
    (str (String.make 64 '0')) da_raw);
  rejected ~message:"Unsupported declared genetic code." "invalid_translation_policy"
    "nonstandard translation code rejects at its original molecular boundary" (fun () -> check (repin
      (put ["body";"products";"0";"expected";"translation_policy";"genetic_code"] (str "unreviewed_code") da_raw)));
  bad "missing external input prerequisite" (edit ["body";"provider_requirements"] (fun raw -> arr (List.tl (Json.array raw))) da_raw);
  bad "duplicate provider prerequisite" (edit ["body";"provider_requirements"] (fun raw -> arr (List.hd (Json.array raw)::Json.array raw)) da_raw);
  bad "boundary is not external provider slot" (put ["body";"provider_requirements";"0";"external_slot"] (str "request") da_raw);
  bad "missing mandatory static active demand" (edit ["body";"provider_requirements"] (fun raw ->
    arr (List.filteri (fun index _ -> index<>2) (Json.array raw))) da_raw);
  List.iter (fun index -> bad ~message:"Local capacity minimum is below its static primitive requirement."
    "configured active/timer capacity cannot be seven"
    (put ["body";"provider_requirements";string_of_int index;"minimum"] (Json.int 7) da_raw)) [2;4];
  let higher = da_raw |> put ["body";"provider_requirements";"2";"minimum"] (Json.int 9)
    |> put ["body";"provider_requirements";"4";"minimum"] (Json.int 9) |> repin in
  ignore (C.of_json ~library:a higher);
  require (C.fingerprint (C.of_json ~library:a higher) <> C.fingerprint da) "Stricter original prerequisites collapsed";
  List.iter (fun (index,scope) -> bad
    ~message:"Local provider prerequisites must preserve the complete ordered owner, unit and scope inventory."
    "explicit unit scope is not replication scope"
    (put ["body";"provider_requirements";string_of_int index;"scope"] (str scope) da_raw))
    [1,"per_encounter_slot";2,"per_executor";3,"per_encounter_slot";4,"per_executor"];
  bad "wrong capacity owner" (put ["body";"provider_requirements";"2";"owner";"id"] (str "product") da_raw);
  bad "zero symbolic minimum" (put ["body";"provider_requirements";"2";"minimum"] (Json.int 0) da_raw);
  (* A different, coherently pinned original is not rejected merely because its
     peptide expectation agrees. Exact lookup under the old original must fail. *)
  let synonymous = put ["body";"root";"molecule";"sequence"] (str "AUGGCCUAAGGAAAA") da_raw in
  rejected "policy_component_material" "new spelling under old material pin" (fun () -> check synonymous);
  let changed = C.of_json ~library:a (repin synonymous) in
  require (C.fingerprint changed<>C.fingerprint da && L.find la (C.identity changed)=None &&
    (List.hd (C.products changed)).expected.sequence="MA") "Equal peptide transferred exact material authority";
  List.iter (fun mutated -> let changed = C.of_json ~library:a (repin mutated) in
    require (C.fingerprint changed<>C.fingerprint da && L.find la (C.identity changed)=None)
      "Changed complete material authority reused original library selection")
    [put ["body";"root";"molecule";"chemistry";"cap";"identity";"accession"] (str "different_cap") da_raw;
     put ["body";"root";"provenance";"locator"] (str "different independently supplied location") da_raw];
  let wrong_peptide = da_raw |> put ["body";"products";"0";"expected";"sequence"] (str "MG")
    |> put ["body";"products";"0";"expected";"identity";"content_fingerprint"]
      (str (Canonical.fingerprint (PM.product_content_json "MG"))) |> repin in
  ignore (C.of_json ~library:a wrong_peptide);
  require (C.fingerprint (C.of_json ~library:a wrong_peptide)<>C.fingerprint da)
    "Shape-only local declaration falsely became translation acceptance";
  let without_attempt = replace "models" (arr (List.filter (fun raw ->
    get "id" (get "identity" raw) <> str "exclusion.primitive.attempt") (items "models" a_raw))) a_raw in
  let incomplete_library = I.library_of_json without_attempt in
  rejected ~message:"Fragment model is absent from the independently supplied library."
    "policy_component_fragment" "prior membership cannot transfer into another library"
    (fun () -> C.of_json ~library:incomplete_library (C.to_json da));
  let changed_model = model a_raw "exclusion.primitive.attempt" |> put ["body";"configuration";"timeout_ticks"] (Json.int 5) in
  let changed_model = changed_model
    |> put ["configuration_digest"] (str (Canonical.fingerprint (at ["body";"configuration"] changed_model)))
    |> put ["identity";"content_fingerprint"] (str (Canonical.fingerprint (get "body" changed_model))) in
  let changed_library_raw = replace "models" (arr (List.map (fun raw ->
    if get "id" (get "identity" raw)=str "exclusion.primitive.attempt" then changed_model else raw)
      (items "models" a_raw))) a_raw in
  let changed_library = I.library_of_json changed_library_raw in
  let changed_driver = da_raw |> put ["body";"fragment";"nodes";"1";"model"] changed_model |> repin in
  rejected ~message:"Fragment model is absent from the independently supplied library."
    "policy_component_fragment" "coherently repinned foreign model remains outside original library"
    (fun () -> check changed_driver);
  let changed = C.of_json ~library:changed_library changed_driver in
  require (C.fingerprint changed<>C.fingerprint da && L.find la (C.identity changed)=None)
    "Different supplied model body silently reused the original component";
  let sixteen = List.init 16 (fun index -> put ["identity";"id"] (str ("independent.driver."^string_of_int index)) da_raw) in
  let full = L.of_json ~library:a (library sixteen) in
  require (List.length (L.components full)=16) "Literal sixteen-entry structural library bound changed";
  rejected "molecular_resource_limit" "seventeen entries" (fun () -> L.of_json ~library:a (library (da_raw::sixteen)));
  rejected ~message:"Duplicate component kind, name and version identity." "policy_component_library"
    "duplicate full component identity" (fun () -> L.of_json ~library:a (library [da_raw;da_raw]));
  rejected ~message:"Duplicate component kind, name and version identity." "policy_component_library"
    "same name/version with altered body" (fun () -> L.of_json ~library:a (library [da_raw;repin synonymous]));
  let reverse = L.of_json ~library:a (library [da_raw;aa_raw]) in
  require (L.fingerprint reverse<>L.fingerprint la &&
    List.map (fun value -> P.id (C.identity value)) (L.components reverse) =
      ["fixture.driver.material";"fixture.decision.exclusion.material"]) "Library order was silently sorted";
  let noncanonical = edit ["body";"root";"molecule";"features"]
    (fun value -> arr (List.rev (Json.array value))) da_raw in
  ignore (R.of_json (at ["body";"root"] noncanonical));
  rejected ~message:"Local material must preserve its complete canonical typed body without normalization."
    "policy_component_material" "existing molecular sorting must not erase original authority"
    (fun () -> check (repin noncanonical));
  let four_features = edit ["body";"root";"molecule";"features"] (fun value ->
    arr (feature "driver_body.frame" "aux" "local_annotation" 0 1 Json.Null :: Json.array value)) da_raw in
  let four_sites = [site "driver_body" "aux" 0 1;site "driver_body" "cds" 0 9;
    site "driver_body" "poly_a" 11 15;site "driver_body" "utr3" 9 11] in
  let four = four_features |> put ["body";"carriers";"0";"sites"] (arr four_sites) |> repin in
  let four_decoded = C.of_json ~library:a four in
  require (List.length (List.hd (C.carriers four_decoded)).sites=4 &&
    List.length (N.features (R.molecule (C.root four_decoded)))=4)
    "Declared four-feature/four-distinct-site structural bound changed";
  rejected "molecular_resource_limit" "five sites exceed structural bound" (fun () -> check (repin
    (put ["body";"carriers";"0";"sites"] (arr (List.hd four_sites::four_sites)) four)));
  let five_features = edit ["body";"root";"molecule";"features"] (fun value -> arr
    (feature "driver_body.frame" "aaa" "local_annotation" 1 2 Json.Null :: Json.array value)) four in
  ignore (R.of_json (at ["body";"root"] five_features));
  bad "five local features exceed component profile" five_features;
  require (MC.Path.length (List.hd (List.hd (C.carriers da)).sites).path=9)
    "Carrier path must retain its complete local extent";
  require (MR.pretty_size da_raw + 1 <= 4_000_000) "Positive fixture exceeds original pretty-byte bound";
  List.iter (fun key -> rejected "unknown_field" ("closed original field "^key)
    (fun () -> check (add key (str "untrusted") da_raw)))
    ["source_artifact_digest";"model_library_digest";"provider";"accepted";"export"];
  List.iter (fun (keys,key) -> let changed = edit keys (fun raw ->
    obj (List.filter (fun (name,_) -> name<>key) (Json.object_fields raw))) da_raw in
    rejected "missing_field" ("missing required original "^key) (fun () -> check changed))
    [[] ,"profile"; ["body"],"root"];
  rejected "unknown_field" "concrete provider cannot enter symbolic capacity" (fun () -> check (repin
    (edit ["body";"provider_requirements";"2"] (add "provider" (str "request-bound")) da_raw)));
  rejected "duplicate_key" "duplicate outer key" (fun () -> check (add "body" (get "body" da_raw) da_raw));
  rejected "policy_component_material" "raw float preflight" (fun () -> check (add "float" (Json.Float 1.) da_raw));
  rejected "molecular_resource_limit" "aggregate list node budget" (fun () -> check
    (add "oversized" (arr (List.init 100_001 (fun _ -> Json.Bool false))) da_raw));
  let rec deep count value = if count=0 then value else deep (count-1) (arr [value]) in
  rejected "molecular_resource_limit" "outer depth budget" (fun () -> check (deep 97 da_raw));
  rejected "molecular_resource_limit" "pretty escaped bytes budget" (fun () -> check
    (add "oversized" (str (String.make 700_000 '\001')) da_raw));
  let rec cycle = Json.Array [cycle] in
  rejected "molecular_cycle" "cyclic programmatic input" (fun () -> check cycle);
  Printf.printf "policy component material: %d checks\n" !checks

let () = match run (read Sys.argv.(1)) (read Sys.argv.(2)) with
  | () -> ()
  | exception Diagnostic.Error value ->
      failwith ("Unexpected component diagnostic: " ^ value.code ^ ": " ^ value.message)
