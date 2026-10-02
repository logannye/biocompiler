open Bioc_wire
open Bioc_domain
module M = Source_execution_manifest
module O = M.Output
module D = M.Diagnostic_record
let require condition message = if not condition then failwith message
let str value = Json.String value
let obj value = Json.Object value
let field key value = Json.field key (Json.object_fields value)
let rejected label code run = match run () with
  | _ -> failwith (label ^ ": intended failure accepted")
  | exception Diagnostic.Error error -> require (error.code=code) (label ^ ": expected " ^ code ^ ", got " ^ error.code ^ ": " ^ error.message)
let diagnostic_literal=Json.parse {|{"code":"unresolved","category":"missing_refinement","source_node_ids":["a","a"],"message":"Declared only."}|}
let output_literal=Json.parse {|{"id":"output:r:a","rule_id":"r","action_id":"a","guard_id":"g","role_id":"role","action_kind":"supplied.kind","lineage":["z","","z"],"trigger":"event","activation":"explicit_duration","product":"","semantics":{"amount":9007199254740993,"fraction":-0.0,"empty":null}}|}
let output ?(lineage=[]) ?(semantics=obj []) () = O.make ~id:"declared" ~rule_id:"r" ~action_id:"a" ~guard_id:"g" ~role_id:"role"
  ~action_kind:"supplied.kind" ~lineage ~trigger:O.Event ~activation:O.Explicit_duration ~product:(Some "") ~semantics
let literals () =
  let diagnostic=D.make ~code:"unresolved" ~category:D.Missing_refinement ~source_node_ids:["a";"a"] ~message:"Declared only." in
  require (Json.equal (D.to_json diagnostic) diagnostic_literal && D.code diagnostic="unresolved" && D.source_node_ids diagnostic=["a";"a"]
    && D.message diagnostic="Declared only." && D.category diagnostic=D.Missing_refinement) "Independent complete diagnostic literal differs";
  let value=O.of_json output_literal in
  require (Json.equal (O.to_json value) output_literal && O.id value="output:r:a" && O.rule_id value="r" && O.action_id value="a" && O.guard_id value="g"
    && O.role_id value="role" && O.action_kind value="supplied.kind" && O.lineage value=["z";"";"z"] && O.product value=Some ""
    && O.trigger value=O.Event && O.activation value=O.Explicit_duration && Json.equal (O.semantics value) (field "semantics" output_literal))
    "Output literal lost nominal IDs, duplicate lineage, integer kind or signed zero";
  let reordered=O.of_json (obj (("lineage",Json.Array [str "";str "z";str "z"])::List.remove_assoc "lineage" (Json.object_fields output_literal))) in
  require (O.fingerprint reordered<>O.fingerprint value) "Ordered output declaration conflated";
  let rec identities="x"::identities in
  rejected "cyclic diagnostic identities" "invalid_source_manifest" (fun () -> D.make ~code:"x" ~category:D.Contradiction ~source_node_ids:identities ~message:"x");
  rejected "cyclic output lineage" "invalid_source_manifest" (fun () -> output ~lineage:identities ());
  let rec cycle=Json.Array [cycle] in
  rejected "cyclic retained JSON" "source_manifest_limit" (fun () -> output ~semantics:(obj ["retained",cycle]) ());
  let rec spine=Json.Null::spine in
  rejected "cyclic JSON list spine" "source_manifest_limit" (fun () -> output ~semantics:(obj ["retained",Json.Array spine]) ());
  rejected "duplicate retained keys" "duplicate_key" (fun () -> output ~semantics:(obj ["same",Json.Null;"same",Json.Null]) ());
  rejected "native nonfinite" "nonfinite_number" (fun () -> output ~semantics:(obj ["value",Json.Float infinity]) ());
  rejected "native malformed UTF8" "invalid_utf8" (fun () -> D.make ~code:"x" ~category:D.Contradiction ~source_node_ids:[] ~message:(String.make 1 (Char.chr 255)));
  rejected "native string bound" "source_manifest_limit" (fun () -> output ~semantics:(obj ["value",str (String.make (Limits.max_string_bytes+1) 'x')]) ());
  let nested count=let value=ref Json.Null in for _=1 to count do value:=Json.Array [!value] done; !value in
  M.reserve_json (M.create_resource_budget ()) (nested Limits.max_depth);
  rejected "native depth boundary" "source_manifest_limit" (fun () -> M.reserve_json (M.create_resource_budget ()) (nested (Limits.max_depth+1)));
  M.reserve_json (M.create_resource_budget ()) (Json.Array (List.init (Limits.max_json_nodes-1) (fun _ -> Json.Null)));
  rejected "native node boundary" "source_manifest_limit" (fun () -> M.reserve_json (M.create_resource_budget ()) (Json.Array (List.init Limits.max_json_nodes (fun _ -> Json.Null))));
  let shared=M.create_resource_budget () and chunk=str (String.make (Limits.max_response_bytes/8-2) 'x') in
  for _=1 to 8 do M.reserve_json shared chunk done;
  rejected "cumulative compact byte boundary" "source_manifest_limit" (fun () -> M.reserve_json shared Json.Null);
  print_endline "source manifest literals: complete historical leaves, retained order/number kinds, bounded cycles, UTF8, exact native depth/node/shared byte limits passed"
let inspect kind raw = match kind with
  | "output" -> O.of_json raw |> O.to_json
  | "diagnostic" -> D.of_json raw |> D.to_json
  | "manifest" -> M.of_json raw |> M.to_json
  | _ -> failwith "Unknown source-manifest fixture kind"
let rec edit_at value path replacement = match path with
  | [] -> failwith "Cannot mutate source-manifest fixture root"
  | Json.String key :: tail ->
    let fields=Json.object_fields value in
    if tail=[] then obj (match replacement with
      | None -> require (List.mem_assoc key fields) "Missing fixture deletion key"; List.remove_assoc key fields
      | Some replacement -> (key,replacement)::List.remove_assoc key fields)
    else (require (List.mem_assoc key fields) "Missing fixture descent key";
      obj (List.map (fun (name,child) -> name,if name=key then edit_at child tail replacement else child) fields))
  | Json.Int index :: tail ->
    let index=Z.to_int index and values=Json.array value in
    require (index>=0 && index<List.length values) "Fixture edit index out of range";
    Json.Array (List.mapi (fun current child -> if current=index then
        (if tail=[] then replacement else Some (edit_at child tail replacement)) else Some child) values |> List.filter_map Fun.id)
  | _ -> failwith "Invalid source-manifest fixture patch path"
let edited raw edits = List.fold_left (fun raw edit ->
    let fields=Json.object_fields edit in
    let replacement=if List.assoc_opt "delete" fields=Some (Json.Bool true) then None else Some (field "value" edit) in
    edit_at raw (Json.array (field "path" edit)) replacement) raw (Json.array edits)
let read_json path =
  require (not (Filename.is_relative path)) "Source manifest corpus requires an absolute path";
  let channel=open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size=in_channel_length channel in require (size<=Limits.max_request_bytes) "Source manifest corpus read budget"; Json.parse (really_input_string channel size))
let retained path =
  let corpus=read_json path in
  require (field "schema_version" corpus=str "biocompiler.source_manifest_conformance.v1") "Wrong source-manifest corpus schema";
  let records=Json.array (field "records" corpus) and failures=Json.array (field "rejections" corpus) in
  require (List.length records=34 && List.length failures=56 && List.length (Json.array (field "checks" corpus))=35) "Source manifest census changed";
  let full_inventory=obj (List.map (fun key -> key,field key corpus) ["records";"rejections";"checks";"literal_expectations";"compatibility"]) in
  let expected="ba237e1adcbcb6e1853edd138f06edb7aaa1d729cfb2b31d61d8127d03d11d32" in
  require (Canonical.fingerprint full_inventory=expected && field "inventory_sha256" corpus=str expected) "Source manifest complete inventory or intended diagnostics changed";
  let inventory keys rows=List.sort (fun left right -> String.compare (Json.string (field "id" left)) (Json.string (field "id" right))) rows
      |> List.map (fun row -> Json.Array (List.map (fun key -> field key row) keys)) |> fun values -> Canonical.fingerprint (Json.Array values) in
  require (inventory ["id";"kind"] records="a3c23d6913756b2ef8a07f04d26f146846a7d5c820dc5c83a821d1e65d4621cf") "Source manifest family inventory changed";
  require (inventory ["id";"kind";"expected_code"] failures="f275c6700c1c6a520dec46cf1abd3273c4dc1a1ed1621005e0d8d6a90e4ec341") "Source manifest rejection signature changed";
  require (Canonical.fingerprint (field "literal_expectations" corpus)="e12c054d13d8403d3e393c6cf4742e8e24c3496a0010711dcb01e9b5365653e5") "Independent source manifest literals changed";
  List.iter (fun rows -> let ids=List.map (fun row -> Json.string (field "id" row)) rows in
    require (List.length ids=List.length (List.sort_uniq String.compare ids)) "Duplicate source-manifest case identity") [records;failures];
  let documents=field "documents" corpus in
  List.iter (fun (digest,raw) -> require (Canonical.fingerprint raw=digest) "Source-manifest retained document pin changed") (Json.object_fields documents);
  let doc key item=field (Json.string (field key item)) documents in
  List.iter (fun item ->
    let kind=Json.string (field "kind" item) in
    let actual=inspect kind (doc "document" item) in
    require (Json.equal actual (doc "normalized" item)) (Json.string (field "id" item) ^ ": complete historical record differs");
    require (str (Canonical.fingerprint actual)=field "fingerprint" item) "Historical record fingerprint differs";
    require (Json.equal actual (inspect kind actual)) "Historical record import not idempotent";
    if kind="manifest" then (
      let value=M.of_json actual in
      require (Json.Bool (M.complete value)=field "complete" item && str (M.source_fingerprint value)=field "source_fingerprint" item) "Stored completeness/source identity differs";
      require (Json.equal (Human_request.to_json (M.source value)) (field "source" actual)) "Full wrapped authority was projected away";
      require (Build_request.fingerprint (M.build_request value)=Build_request.fingerprint (Human_request.build_request (M.source value))) "Explicit traversal projection differs")) records;
  List.iter (fun item -> rejected (Json.string (field "id" item)) (Json.string (field "expected_code" item))
      (fun () -> inspect (Json.string (field "kind" item)) (edited (doc "document" item) (field "edits" item)))) failures;
  List.iter (fun item -> require (Json.equal (inspect (Json.string (field "kind" item)) (field "expected" item)) (field "expected" item))
      "Independent full historical declaration differs") (Json.array (field "literal_expectations" corpus));
  let base=List.find (fun item -> field "id" item=str "empty_role") records |> doc "normalized" |> M.of_json in
  let make ?(outputs=[]) ?(diagnostics=[]) ?(roles=[]) ?(ledger=[]) ?(role_nodes=obj []) ?(states=[]) ?(channels=[]) () =
    M.make ~source:(M.source base) ~behavior:(M.behavior base) ~roles ~outputs ~ledger ~role_nodes ~states ~channels ~diagnostics in
  let output=output () and diagnostic=D.of_json diagnostic_literal in
  let maximum=make ~outputs:(List.init 4096 (fun _ -> output)) () in
  require (List.length (M.outputs maximum)=4096 && M.complete maximum) "Exact 4096 historical outputs rejected or treated as source correspondence";
  rejected "4097 historical outputs" "invalid_source_manifest" (fun () -> make ~outputs:(List.init 4097 (fun _ -> output)) ());
  let rec outputs=output::outputs in
  rejected "cyclic historical outputs" "invalid_source_manifest" (fun () -> make ~outputs ());
  let rec diagnostics=diagnostic::diagnostics in
  rejected "cyclic historical diagnostics" "invalid_source_manifest" (fun () -> make ~diagnostics ());
  let rec roles=""::roles in
  rejected "cyclic historical roles" "invalid_source_manifest" (fun () -> make ~roles ());
  let rec ledger=obj []::ledger in
  rejected "cyclic historical ledger" "invalid_source_manifest" (fun () -> make ~ledger ());
  let historical=make ~roles:["";"same";"same"] ~ledger:[obj ["retained",Json.Bool true]] ~role_nodes:(obj ["arbitrary",str "unresolved"])
    ~states:[obj []] ~channels:[obj []] ~diagnostics:[diagnostic] () in
  require (M.roles historical=["";"same";"same"] && M.ledger historical=[obj ["retained",Json.Bool true]] && M.states historical=[obj []]
    && M.channels historical=[obj []] && Json.equal (M.role_nodes historical) (obj ["arbitrary",str "unresolved"]) && not (M.complete historical))
    "Historical arbitrary inventories were interpreted or discarded";
  Printf.printf "source manifest domains: %d complete records, %d intended failures, full literal/source identities, ordered historical inventories and generated 4096/4097-output boundary passed\n" (List.length records) (List.length failures)
let () = match Array.to_list Sys.argv with
  | [_] -> literals ()
  | [_;path] -> literals (); retained path
  | _ -> failwith "Usage: test_source_manifest.exe [<absolute-source-manifest-v1.json>]"
