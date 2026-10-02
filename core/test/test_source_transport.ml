open Bioc_wire
open Bioc_domain
module T=Bioc_source_adapter.Source_transport
module D=Bioc_source_adapter.Source_transport_data
module E=Execution_data
module R=Bioc_semantics.Reference
module W=Bioc_checker.Work_budget
let require value message=if not value then failwith message
let obj value=Json.Object value
let arr value=Json.Array value
let str value=Json.String value
let field key value=Json.field key (Json.object_fields value)
let text key value=Json.string (field key value)
let rejected label code action=match action () with
 | _->failwith (label ^ ": intended rejection accepted")
 | exception Diagnostic.Error error->require (error.code=code) (label ^ ": expected " ^ code ^ ", got " ^ error.code)
let literal_behavior ()=
 let node=Json.parse {|{"id":"role","kind":"role","inputs":[],"attributes":{"name":"recipient","cell_type":"human_T_cell","engineering":"in_vivo"},"data_type":null,"role":null,"source":null,"contact_bound":false,"requirement_ids":[]}|} in
 Behavior.of_json (obj ["schema_version",str "biocompiler.behavior.v0.1";"name",str "literal_transport_usage";
  "nodes",arr [node];"roots",arr [str "role"];"source_fingerprint",str (String.make 64 '0');
  "requirements",arr [];"source_links",obj ["role",arr [str "role"]];
  "policies",Behavior.execution_policies Behavior.V0_1;"parameter_bindings",obj []])
let literals ()=
 require (T.resource_profile="biocompiler.source_transport.resources.v1" && T.max_work=50000000 &&
  T.max_queued_deliveries=100000 && T.max_replayed_frames=100000 && T.max_replayed_trace_items=1000000)
  "Source transport resource profile changed";
 let behavior=literal_behavior () in
 let history=[E.Input_frame.make ~time:Runtime_number.zero ()] in
 let result,usage=R.evaluate_with_usage ~until:(Runtime_number.of_int 1) behavior history in
 require (usage.work>0 && usage.frames=2 && usage.trace_items=0) "Reference usage omits execution work or frame census";
 require (Json.equal (E.Result.to_json result) (E.Result.to_json (R.evaluate ~until:(Runtime_number.of_int 1) behavior history)))
  "Reference usage changed the legacy evaluate result";
 let exact=R.make_budget ~max_work:usage.work () in
 require (Json.equal (E.Result.to_json result) (E.Result.to_json (fst (R.evaluate_with_usage ~until:(Runtime_number.of_int 1) ~budget:exact behavior history))))
  "Exact consumed reference work cannot replay identical input";
 rejected "one below actual reference work" "evaluation_work_limit" (fun ()->R.evaluate_with_usage
  ~until:(Runtime_number.of_int 1) ~budget:(R.make_budget ~max_work:(usage.work-1) ()) behavior history);
 let input=D.Input.make ~histories:["role",history] ~until:(Json.int 1) ~step:(Json.Bool true) () in
 require (D.Input.step input=Json.Bool true) "Input codec silently normalized a Boolean time into numeric seconds";
 let frame=D.Channel_frame.make ~time:Z.zero ~receiver_values:["receiver",Runtime_number.Real (-0.)]
  ~sent:["channel",{D.Channel_frame.value=Runtime_number.of_int 1;delivery_time=Z.of_int 2}]
  ~failed_channel_ids:["a";"b"] in
 require (Json.equal (D.Channel_frame.to_json (D.Channel_frame.of_json (D.Channel_frame.to_json frame))) (D.Channel_frame.to_json frame))
  "Literal channel frame lost exact numeric representation";
 rejected "negative trace time" "source_transport_data" (fun ()->D.Channel_frame.make ~time:Z.minus_one ~receiver_values:[] ~sent:[] ~failed_channel_ids:[]);
 rejected "failure identity order" "source_transport_data" (fun ()->D.Channel_frame.make ~time:Z.zero ~receiver_values:[] ~sent:[] ~failed_channel_ids:["b";"a"]);
 rejected "duplicate input authority key" "source_transport_data" (fun ()->D.Input.make ~histories:["role",history;"role",history] ~until:(Json.int 0) ~step:(Json.int 1) ());
 let rec cyclic=Json.Null::cyclic in
 rejected "cyclic native option spine" "source_transport_output_limit" (fun ()->D.Input.make ~histories:[] ~until:(Json.Array cyclic) ~step:(Json.int 1) ());
 let rec frames=List.hd history::frames in
 rejected "cyclic typed frame spine" "source_transport_output_limit" (fun ()->D.Input.make ~histories:["role",frames] ~until:(Json.int 0) ~step:(Json.int 1) ());
 rejected "transport fixed ceiling" "invalid_work_budget" (fun ()->T.make_budget ~maximum:(T.max_work+1) ());
 let parent=W.create ~profile:"literal.parent" ~error_code:"parent_limit" ~maximum:7 () in
 let nested=T.make_budget ~parent () in require (T.remaining_work nested=7) "Transport parent allowance was reset";
 print_endline "source transport literals: exact reference usage, unchanged wrapper, typed records and cyclic native/resource boundaries passed"
let read path maximum=
 let channel=open_in_bin path in Fun.protect ~finally:(fun ()->close_in_noerr channel) (fun ()->
 let bytes=in_channel_length channel in require (bytes<=maximum) "Source transport fixture file exceeds bound";
 Json.parse (really_input_string channel bytes),bytes)
let hash value=require (String.length value=64 && String.for_all (function '0'..'9'|'a'..'f'->true|_->false) value) "Unsafe document identity";value
let int value=Json.integer value |> Z.to_int
let rec edit_at raw path replacement=match path with
 | []->(match replacement with Some value->value|None->failwith "Cannot remove root")
 | Json.String key::rest->
   let fields=Json.object_fields raw in
   if rest=[] then obj (match replacement with Some value->(key,value)::List.remove_assoc key fields
    | None->require (List.mem_assoc key fields) "Missing delta deletion";List.remove_assoc key fields)
   else (require (List.mem_assoc key fields) "Missing delta descent";
    obj (List.map (fun (name,value)->name,if name=key then edit_at value rest replacement else value) fields))
 | Json.Int index::rest->
   let values=Json.array raw in require (Z.sign index>=0 && Z.compare index (Z.of_int (List.length values))<0) "Invalid delta index";
   require (rest<>[] || replacement<>None) "Array deletion unsupported";
   List.mapi (fun i value->if i=Z.to_int index then edit_at value rest replacement else value) values |> arr
 | _->failwith "Invalid delta path"
let edits raw changes=List.fold_left (fun raw change->
 let replacement=match text "op" change with
  | "set"->Json.exact_fields ["op";"path";"value"] (Json.object_fields change);Some (field "value" change)
  | "remove"->Json.exact_fields ["op";"path"] (Json.object_fields change);None
  | _->failwith "Unknown delta operation" in
 let path=Json.array (field "path" change) in require (path<>[] && List.length path<=96) "Invalid delta depth";
 edit_at raw path replacement) raw changes
let normalize kind raw=match kind with
 | "request"->Architecture_request.of_json raw |> Architecture_request.to_json
 | "build"->Architecture_build.of_json raw |> Architecture_build.to_json
 | "input"->D.Input.of_json raw |> D.Input.to_json
 | "result"->D.Result.of_json raw |> D.Result.to_json
 | _->failwith "Unknown source transport document kind"
let retained path=
 require (not (Filename.is_relative path)) "Source transport corpus path must be absolute";
 let index,index_bytes=read path Limits.max_request_bytes in
 require (text "schema_version" index="biocompiler.source_transport_conformance.v1") "Wrong source transport corpus";
 let inventory=obj (List.remove_assoc "inventory_fingerprint" (Json.object_fields index)) in
 let pin="4da417dc6840da4d4ccdd60341996b72d4524a222e0c8763460d1e65dfaff3f5" in
 require (Canonical.fingerprint inventory=pin && text "inventory_fingerprint" index=pin) "Source transport complete inventory differs";
 let metadata=Json.array (field "documents" index) in
 require (List.length metadata=87) "Frozen source transport document census differs";
 let documents=Hashtbl.create (List.length metadata) and descriptors=Hashtbl.create (List.length metadata) and total=ref index_bytes in
 let directory=Filename.remove_extension path in
 List.iter (fun descriptor->
  Json.exact_fields ["id";"kind";"format";"base";"stored_fingerprint";"bytes";"resolved_bytes"] (Json.object_fields descriptor);
  let id=hash (text "id" descriptor) in require (not (Hashtbl.mem documents id)) "Duplicate transport document";
  let raw,bytes=read (Filename.concat directory (id ^ ".json")) Molecular_record.max_json_bytes in
  require (bytes=int (field "bytes" descriptor) && bytes<=Limits.max_request_bytes- !total) "Stored transport bytes differ";
  total:= !total+bytes;Molecular_record.check_resources raw;
  require (Canonical.fingerprint raw=hash (text "stored_fingerprint" descriptor)) "Stored transport document hash differs";
  Hashtbl.add documents id raw;Hashtbl.add descriptors id descriptor) metadata;
 let expected_files=List.map (fun value->text "id" value ^ ".json") metadata |> List.sort String.compare in
 require ((Array.to_list (Sys.readdir directory) |> List.sort String.compare)=expected_files) "Missing or extra source transport document";
 let lookup table id=match Hashtbl.find_opt table id with Some value->value|None->failwith "Missing transport document" in
 let resolve id=
  let descriptor=lookup descriptors id and raw=lookup documents id in
  let value=match text "format" descriptor with
   | "full"->require (field "base" descriptor=Json.Null) "Full document has base";raw
   | "delta"->
     let base=hash (text "base" descriptor) in let parent=lookup descriptors base in
     require (base<>id && text "format" parent="full" && field "base" parent=Json.Null && text "kind" parent=text "kind" descriptor) "Invalid transport delta baseline";
     Json.exact_fields ["schema_version";"base";"edits"] (Json.object_fields raw);
     require (text "schema_version" raw="biocompiler.test_document_delta.v1" && text "base" raw=base) "Transport delta authority differs";
     let changes=Json.array (field "edits" raw) in require (changes<>[]) "Empty delta";edits (lookup documents base) changes
   | _->failwith "Unknown transport document format" in
  Molecular_record.check_resources value;
  require (Canonical.fingerprint value=id && Molecular_record.pretty_size value+1=int (field "resolved_bytes" descriptor)) "Resolved transport authority differs";
  require (Json.equal (normalize (text "kind" descriptor) value) value) "Transport record is not normalized";value in
 let reachable=Hashtbl.create (List.length metadata) in
 let use kind id=
  let descriptor=lookup descriptors id in require (text "kind" descriptor=kind) "Wrong document kind";
  Hashtbl.replace reachable id ();
  (match field "base" descriptor with Json.Null->()|value->Hashtbl.replace reachable (Json.string value) ());resolve id in
 Hashtbl.iter (fun id _->ignore (resolve id)) descriptors;
 let cases=Json.array (field "cases" index) and identities=Hashtbl.create 64 and traces=Hashtbl.create 64 in
 require (List.length cases=51 && !total=2720809) "Frozen source transport case or byte census differs";
 let positives=ref 0 and negatives=ref 0 in
 List.iter (fun case->
  let id=text "id" case in require (not (Hashtbl.mem identities id)) "Duplicate source transport case";Hashtbl.add identities id case;
  let request=use "request" (text "request" case) |> Architecture_request.of_json in
  let build=use "build" (text "build" case) |> Architecture_build.of_json in
  let input=use "input" (text "input" case) |> D.Input.of_json in
  match field "expected" case with
   | Json.Null->incr negatives;rejected id (text "expected_code" case) (fun ()->T.evaluate ~expected_request:request build input)
   | expected_id->
     incr positives;
     let expected=use "result" (Json.string expected_id) in
     let budget=T.make_budget () in
     let result=T.evaluate ~budget ~expected_request:request build input in
     let raw=D.Result.to_json result in
     require (Json.equal raw expected) (id ^ ": complete transport trace differs; expected=" ^ Canonical.fingerprint expected ^ ", actual=" ^ Canonical.fingerprint raw);
     Hashtbl.add traces id raw;
     if id="literal/baseline" then (
       let consumed=T.max_work-T.remaining_work budget in
       require (consumed>0 && consumed<T.max_work) "Source transport did not account aggregate work";
       require (Json.equal raw (D.Result.to_json (T.evaluate ~budget:(T.make_budget ~maximum:consumed ()) ~expected_request:request build input)))
        "Exact cumulative replay budget failed";
       rejected "one below complete coupled replay" "source_transport_work_limit" (fun ()->T.evaluate ~budget:(T.make_budget ~maximum:(consumed-1) ()) ~expected_request:request build input);
       rejected "exhausted reused coupled budget" "source_transport_work_limit" (fun ()->T.evaluate ~budget:(T.make_budget ~maximum:0 ()) ~expected_request:request build input))) cases;
 List.iter (fun assertion->
  let id=text "case_id" assertion in let trace=match Hashtbl.find_opt traces id with Some value->value|None->failwith "Missing independent literal trace" in
  let frames=Json.array (field "channel_frames" trace) in
  let values=match text "projection" assertion with
   | "receiver_values"->List.map (fun frame->field (text "receiver" assertion) (field "receiver_values" frame)) frames
   | "delivery_times"->List.map (fun frame->match List.assoc_opt (text "channel" assertion) (Json.object_fields (field "sent" frame)) with
      None->Json.Null|Some value->field "delivery_time" value) frames
   | _->failwith "Unknown independent transport projection" in
  require (Json.equal (arr values) (field "expected" assertion)) (id ^ ": independent expected transport timeline differs")) (Json.array (field "literal_assertions" index));
 require (Hashtbl.length reachable=Hashtbl.length documents) "Unreachable transport document";
 let coverage=field "coverage" index in
 require (!positives=20 && !negatives=31 && int (field "cases" coverage)=List.length cases && int (field "documents" coverage)=List.length metadata &&
  int (field "positive" coverage)= !positives && int (field "negative" coverage)= !negatives) "Transport case census differs";
 let methods=Json.array (field "methods" coverage) in
 require (List.length methods=9 && List.for_all (fun method_->text "status" method_="source_assertions_executed") methods &&
  List.fold_left (fun total method_->total+int (field "retained_calls" method_)) 0 methods=15 &&
  int (field "original_calls" coverage)=15) "Original nine transport regressions missing";
 List.iter (fun method_->
  let prefix=text "method" method_ ^ "/" in
  require (int (field "retained_calls" method_)=List.length (List.filter (fun case->String.starts_with ~prefix (text "id" case)) cases))
   "Original transport capture-call inventory differs") methods;
 Printf.printf "source transport: %d complete traces, %d intended evaluation rejections, nine original assertion methods and independent transport timelines passed\n" !positives !negatives
let ()=match Array.to_list Sys.argv with
 | [_]->literals ()
 | [_;path]->literals ();retained path
 | _->failwith "usage: test_source_transport.exe [<absolute-source-transport-corpus.json>]"
