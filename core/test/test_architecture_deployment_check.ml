open Bioc_wire
module C = Bioc_checker.Architecture_deployment_check
module W = Bioc_checker.Work_budget
module T = Bioc_domain.Architecture_deployment.Time
let checks=ref 0
let require yes message = incr checks;if not yes then failwith message
let str v=Json.String v
let obj v=Json.Object v
let arr v=Json.Array v
let field k v=Json.field k (Json.object_fields v)
let rejected label code run = incr checks;match run () with _->failwith (label ^ ": accepted")
  | exception Diagnostic.Error e -> if e.code<>code then failwith (label ^ ": " ^ e.code)
let literals () =
  let tenth=T.of_json (Json.Float 0.1) and fifth=T.of_json (Json.Float 0.2) and three_tenths=T.of_json (Json.Float 0.3) in
  require (T.compare_sum tenth fifth three_tenths=0) "Independent exact decimal sum failed";
  require (T.compare_sum tenth fifth (T.of_json (Json.Float 0.30000000000000004))<0) "A real decimal gap disappeared";
  let n,d=T.ratio three_tenths in require (Z.equal n (Z.of_int 3) && Z.equal d (Z.of_int 10)) "Decimal witness ratio changed";
  let placement=obj ["id",str "p";"delivery_group",str "g";"recipient_role",str "r";"compartment",str "cytoplasm";"retained",Json.Bool true] in
  let window=obj ["placement_id",str "p";"clock",str "opaque_clock";"onset_min_seconds",Json.int 2;"onset_max_seconds",Json.int 1;
    "duration_min_seconds",Json.int 0;"duration_max_seconds",Json.int 0;"cached_end",Json.int 999] in
  let input=C.Inventory.make ~placements:[placement;placement] ~availability:[window;window] in
  require (Json.equal (C.Inventory.to_json input) (obj ["placements",arr [placement;placement];"availability",arr [window;window]]))
    "Historical inventory mapping or multiplicity was silently tightened";
  let rec values=placement::values in
  rejected "native cyclic inventory spine" "source_manifest_limit" (fun ()->C.Inventory.make ~placements:values ~availability:[]);
  let rec raw=Json.Array [raw] in rejected "raw cyclic inventory" "source_manifest_limit" (fun ()->C.Inventory.of_json raw);
  rejected "duplicate inventory key" "duplicate_key" (fun ()->C.Inventory.of_json (obj ["placements",arr [];"placements",arr [];"availability",arr []]));
  rejected "nonfinite input" "nonfinite_number" (fun ()->C.Inventory.of_json (Json.Float Float.infinity));
  rejected "missing fields" "missing_field" (fun ()->C.Inventory.make ~placements:[obj []] ~availability:[]);
  rejected "unbounded work override" "architecture_deployment_limit" (fun ()->C.make_budget ~maximum:(C.max_work+1) ());
  Printf.printf "architecture deployment: %d independent decimal/mapping/runtime checks passed\n" !checks
let inventory c=Canonical.fingerprint (obj (List.map (fun k->k,field k c) ["cases";"coverage";"native_boundary"]))
let result_json (result:C.result)=obj ["failures",arr (List.map str result.failures);"witnesses",arr result.witnesses]
let retained path =
  require (not (Filename.is_relative path)) "Deployment corpus requires absolute path";
  let ch=open_in_bin path in
  let corpus=Fun.protect ~finally:(fun ()->close_in_noerr ch) (fun ()->let size=in_channel_length ch in
      require (size<=Limits.max_request_bytes) "Deployment corpus read budget";Json.parse (really_input_string ch size)) in
  require (field "schema_version" corpus=str "biocompiler.architecture_proofs_conformance.v1" && field "kind" corpus=str "deployment") "Wrong deployment corpus";
  let digest="a602b00a7dbb7f614dd6f577fa32b1da4215ffdf93d1e0dcd5452134f711e001" in
  require (inventory corpus=digest && field "inventory_sha256" corpus=str digest) "Deployment full input/result/witness inventory changed";
  let docs=Json.object_fields (field "documents" corpus) and cases=Json.array (field "cases" corpus) in
  require (List.length docs=36 && List.length cases=30) "Truncated deployment corpus";
  List.iter (fun (sha,raw)->require (Canonical.fingerprint raw=sha) "Changed full deployment authority") docs;
  let used=Hashtbl.create 64 and ids=Hashtbl.create 64 in
  let document sha = let sha=Json.string sha in Hashtbl.replace used sha ();Json.field sha docs in
  List.iter (fun case ->
      let id=Json.string (field "id" case) in require (not (Hashtbl.mem ids id)) "Duplicate deployment case";Hashtbl.add ids id ();
      let request=document (field "request" case) and inventory=document (field "inventory" case) in
      let actual=C.check_json ~request ~inventory () in
      require (Json.equal (result_json actual) (field "expected" case)) (id ^ ": exact interval result differs: " ^ Canonical.encode (result_json actual));
      require (Json.equal (result_json actual) (result_json (C.check_json ~request ~inventory ()))) (id ^ ": nondeterministic interval witnesses");
      require (Canonical.fingerprint request=Json.string (field "request" case) && Canonical.fingerprint inventory=Json.string (field "inventory" case)) "Deployment checking mutated supplied authority") cases;
  require (Hashtbl.length used=List.length docs) "Unreferenced deployment document";
  let find id=List.find (fun x->field "id" x=str id) cases in
  let check_case id failures = let case=find id in
    let request=document (field "request" case) and inventory=document (field "inventory" case) in
    require ((C.check_json ~request ~inventory ()).failures=failures) (id ^ ": independent literal failures differ") in
  check_case "decimal_exact" [];
  check_case "decimal_real_gap" ["deployment_common_window_insufficient:execute-window:role0.rna0.helper.delivery";
    "deployment_common_window_insufficient:execute-window:role0.rna0.payload.delivery"];
  check_case "missing_helper_window" ["deployment_availability_missing:execute-window:role0.rna0.helper.delivery"];
  check_case "wrong_clock" ["deployment_clock_mismatch:execute-window:role0.rna0.helper.delivery"];
  let case=find "literal/exact_integer_boundaries" in let request=document (field "request" case) and inventory=document (field "inventory" case) in
  let tiny=C.make_budget ~maximum:1 () in
  rejected "local deployment work bound" "architecture_deployment_limit" (fun ()->C.check_json ~budget:tiny ~request ~inventory ());
  let parent=W.create ~profile:"shared test" ~error_code:"architecture_resource_limit" ~maximum:1 () in
  rejected "parent deployment work bound" "architecture_resource_limit" (fun ()->C.check_json ~budget:(C.make_budget ~parent ()) ~request ~inventory ());
  let set key value raw = obj ((key,value)::List.remove_assoc key (Json.object_fields raw)) in
  let constraints=field "constraints" request in
  let requirement=List.hd (Json.array (field "deployment_requirements" constraints)) in
  let many=List.init 256 (fun index->set "id" (str ("bounded_" ^ string_of_int index)) requirement) in
  let amplified=set "constraints" (set "deployment_requirements" (arr many) constraints) request in
  let placement=List.hd (Json.array (field "placements" inventory)) in
  let placement=set "id" (str (String.make 200_000 'x')) placement in
  let missing=obj ["placements",arr [placement];"availability",arr []] in
  rejected "diagnostic amplification shares aggregate output budget" "source_manifest_limit"
    (fun ()->C.check_json ~request:amplified ~inventory:missing ());
  Printf.printf "architecture deployment: %d complete-authority interval results/witnesses and seven independent result/budget checks passed\n" (List.length cases)
let ()=match Array.to_list Sys.argv with [_]->literals () | [_;path]->literals ();retained path
  | _->failwith "Usage: test_architecture_deployment_check.exe [<absolute-corpus.json>]"
