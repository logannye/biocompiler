(* In-process framed package application. The peer supplies only retained source
   bytes and original declarations; no producer process or imported PASS exists. *)
open Bioc_wire
module Ch=Bioc_pipeline_service.Callback_channel
module CM=Bioc_pipeline_service.Callback_manager
module S=Bioc_reference_package_session.Reference_package_session
module IO=Bioc_package_io.Package_io
let require condition message=if not condition then failwith message
let obj fields=Json.Object fields
let str value=Json.String value
let get key raw=Json.field key(Json.object_fields raw)
let text key raw=Json.string(get key raw)
let set key value raw=obj((key,value)::List.remove_assoc key(Json.object_fields raw))
let encode raw=Canonical.encode_bounded ~max_bytes:33_554_432 raw
let parse raw=Json.parse_artifact ~max_bytes:33_554_432 ~max_nodes:1_000_000 raw
let framed raw=let bytes=encode raw in Printf.sprintf "%08x\n%s"(String.length bytes)bytes
let identity="deadc0de-1234-5678-9012-000000000001"
let common kind sequence=["protocol",str Ch.protocol;"profile",str Ch.package_profile;
  "session_id",str identity;"kind",str kind;"sequence",Json.int sequence]
external descriptor_number : Unix.file_descr -> int = "%identity"
let fixture path=
 let channel=open_in_bin path in
 let bytes=Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
   let count=in_channel_length channel in require(count<=8_388_608)"Package witness exceeds its fixture bound";
   really_input_string channel count) in
 require(Canonical.sha256 bytes="a867677f97540fcab473cbde9be813b42c139a06c4aa2fd0009e7cde9ed9f135")"Original package witness changed";
 let rows=Json.array(get"cases"(parse bytes)) in
 List.find(fun row->text"id"row="DNA:default")rows
let run source=
 let input=ref "" and outputs=ref [] and next=ref 1 and phase=ref 0 and prepared=ref Json.Null in
 let reads=ref [] in
 let enqueue raw=input:= !input^framed raw in
 let consume count=let count=min count(String.length !input) in
   let value=String.sub !input 0 count in input:=String.sub !input count(String.length !input-count);value in
 let sequence()=let value= !next in incr next;value in
 let command operation arguments=enqueue(obj(common "command"(sequence())@[
   "parent_invocation",Json.Null;"operation",str operation;"arguments",arguments])) in
 let close()=enqueue(obj(common "close"(sequence())@["parent_invocation",Json.Null])) in
 let files=List.map(function Json.Array[Json.String path;Json.String hex]->path,hex
   |_->failwith"Original source pair changed")(Json.array(get"files"source)) in
 enqueue(obj(common "hello" 0@["declaration",Ch.package_declaration;"application",S.declaration;"limits",Json.Null]));
 let io:Ch.io={read_header=(fun()->if !input="" then None else Some(consume 9));read_body=consume;
   write=(fun frame->
     require(String.length frame>=10 && frame.[8]='\n')"Incomplete native frame";
     let body=String.sub frame 9(String.length frame-9) in
     require(int_of_string("0x"^String.sub frame 0 8)=String.length body)"Incorrect native frame length";
     let raw=parse body in outputs:=raw::!outputs;
     match text"kind"raw with
     |"invoke"->
       require(text"action"raw="package-read")"Unexpected package source callback";
       let arguments=get"arguments"raw in let kind=text"kind"arguments and path=text"path"arguments in
       reads:= !reads@[kind^":"^path];
       enqueue(obj(common "continue"(sequence())@["invocation_id",get"invocation_id"raw;
         "invocation_sha256",str(Canonical.sha256 body);"outcome",obj[
           "status",str"return";"value",str(List.assoc path files)]]))
     |"reply"->
       let outcome=get"outcome"raw in require(text"status"outcome="ok")"Package command rejected original inputs";
       let value=get"value"outcome in
       (match !phase with
       |0->phase:=1;command "package-inputs"(obj["alphabet",str"DNA"])
       |1->prepared:=value;phase:=2;command "package-prepare"(obj["inputs",get"capability"value;"line_width",Json.int 80])
       |2->require(Json.equal value(get"request"source))"Prepared complete original request changed";
         phase:=3;command "package-import-inputs"(obj["request",get"request" !prepared;
           "reference",get"reference" !prepared;"registry",get"registry" !prepared])
       |3->require(Json.equal(get"request"value)(get"request" !prepared))"Actual supplied triple changed";
         phase:=4;command "package-prepare"(obj["inputs",get"capability"value;"line_width",Json.int 79])
       |4->require(Json.equal value(set"fasta_line_width"(Json.int 79)(get"request"source)))"Imported triple preparation changed its request";
         phase:=5;command "package-import-files"(obj["files",Json.Array[Json.Array[str"marker.txt";str"66697874757265"]]])
       |5->require(String.starts_with ~prefix:"files/"(text"capability"value))"Actual collection failed to acquire owner capability";
         phase:=6;close()
       |6->require(get"closed"raw=Json.Bool true)"Package application did not close";phase:=7
       |_->failwith"Unexpected additional package reply")
     |_->failwith"Package session failed while processing original source") } in
 let path=Filename.temp_file "bioc-package-session-" ".bin" in
 Fun.protect ~finally:(fun()->Unix.unlink path)(fun()->
   let output=Unix.openfile path[Unix.O_RDWR]0o600 in
   Fun.protect ~finally:(fun()->Unix.close output)(fun()->
     IO.with_fds ~input:"-" ~output:(string_of_int(descriptor_number output))(fun files->
       CM.run(S.create ~io ~files());require(not(IO.output_written files))"Preparation published an archive")));
 require(!phase=7 && !input="")"Package framed continuation did not complete";
 require(List.hd !reads="manifest-first:manifest.json" && List.mem"manifest-second:manifest.json" !reads)
   "Package transport collapsed the independent source reads";
 require(List.length !outputs>7)"Expected real framed byte callbacks were absent"
let unhex bytes=
 let digit=function '0'..'9' as c->Char.code c-48|'a'..'f' as c->Char.code c-87|_->failwith"Bad fixture hex" in
 require(String.length bytes mod 2=0)"Odd fixture hex";
 String.init(String.length bytes/2)(fun i->Char.chr(16*digit bytes.[2*i]+digit bytes.[2*i+1]))
let checker_calls row ~stale=
 let source=get"input"row and value=get"value"(get"outcome"row) in
 let files=List.map(function Json.Array[Json.String path;Json.String hex]->path,unhex hex
   |_->failwith"Original package member pair changed")(Json.array(get"files"value)) in
 let document path=parse(List.assoc path files) in
 let request=get"construct"(get"request"source) and construct=get"payload"(document"stages/construct.json") in
 let candidate=document"molecular.json" and registry=document"inputs/registry.json" in
 let manifest=document"references/wo2022081694a1.murine-fapcar.cds/manifest.json" in
 let manifests=Json.Array[Json.Array[get"reference_set_id"manifest;manifest]] in
 let arguments=obj["request",request;"construct",construct;"artifact",candidate;"registry",registry;
   "manifests",manifests;"line_width",Json.int 80] in
 let evaluation=obj["request",request;"construct",construct;"candidate",candidate;"registry",registry;"manifests",manifests] in
 let input=ref "" and next=ref 1 and phase=ref 0 and pending=ref None and check_id=ref "" and ended=ref false in
 let observed=ref [] in
 let enqueue raw=input:= !input^framed raw in
 let consume count=let count=min count(String.length !input) in
   let value=String.sub !input 0 count in input:=String.sub !input count(String.length !input-count);value in
 let sequence()=let value= !next in incr next;value in
 let command ?(parent=Json.Null) operation arguments=enqueue(obj(common "command"(sequence())@[
   "parent_invocation",parent;"operation",str operation;"arguments",arguments])) in
 let respond raw body value=enqueue(obj(common "continue"(sequence())@[
   "invocation_id",get"invocation_id"raw;"invocation_sha256",str(Canonical.sha256 body);
   "outcome",obj["status",str"return";"value",value]])) in
 let evaluate changed=
   let raw,_=Option.get !pending in command ~parent:(get"invocation_id"raw) "package-check-evaluate"
     (obj["check_id",str(if stale then "check/stale"else !check_id);"name",str"molecular";"arguments",changed]) in
 enqueue(obj(common "hello" 0@["declaration",Ch.package_declaration;"application",S.declaration;"limits",Json.Null]));
 let io:Ch.io={read_header=(fun()->if !input="" then None else Some(consume 9));read_body=consume;
   write=(fun frame->
     let body=String.sub frame 9(String.length frame-9) in
     require(int_of_string("0x"^String.sub frame 0 8)=String.length body)"Incorrect checker frame length";
     let raw=parse body in
     match text"kind"raw with
     |"invoke"->(match text"action"raw with
       |"package-check"->
         require(!phase=1)"Export checker invoked outside its original callpoint";
         let args=get"arguments"raw in require(text"name"args="export-molecular")"Wrong export checker name";
         pending:=Some(raw,body);check_id:=text"check_id"args;phase:=2;
         command ~parent:(get"invocation_id"raw) "package-check-native"(obj["check_id",str !check_id])
       |"package-report-export"->observed:= !observed@["report-export"];
         require(!phase=6 && get"arguments"raw=obj["report",str"actual-current-report"])
           "Export report observation was not its actual callback result";
         respond raw body(obj["passed",Json.Bool true;"diagnostics",Json.Array[]])
       |_->failwith"Unexpected native export callback")
     |"reply"->
       let outcome=get"outcome"raw in require(text"status"outcome="ok")"Export/checker command failed";
       let value=get"value"outcome in
       (match !phase with
       |0->phase:=1;command "package-export" arguments
       |2->require(Json.equal value(document"checks/molecular.json"))"Memoized checker changed original complete report";
         phase:=3;evaluate evaluation
       |3->require(Json.equal value(document"checks/molecular.json"))"Repeated checker changed original complete report";
         phase:=4;evaluate evaluation
       |4->require(Json.equal value(document"checks/molecular.json"))"Second repeated checker changed original complete report";
         phase:=5;evaluate(set"registry"(set"components"(Json.Array[])registry)evaluation)
       |5->require(get"outcome"value<>str"pass")"Altered checker authority inherited original PASS";
         phase:=6;let raw,body=Option.get !pending in
         respond raw body(obj["kind",str"host";"value",obj["report",str"actual-current-report"]])
       |6->require(get"fasta"(get"value"value)=str(List.assoc"sequence.fasta"files))"Export bytes changed after repeated/altered checks";
         phase:=7;enqueue(obj(common "close"(sequence())@["parent_invocation",Json.Null]))
       |7->require(get"closed"raw=Json.Bool true)"Export session did not close";ended:=true
       |_->failwith"Unexpected checker reply")
     |"fatal"->require stale "Actual current checker unexpectedly failed";ended:=true
     |_->failwith"Unexpected checker frame kind") } in
 let path=Filename.temp_file "bioc-package-checker-" ".bin" in
 Fun.protect ~finally:(fun()->Unix.unlink path)(fun()->
   let output=Unix.openfile path[Unix.O_RDWR]0o600 in
   Fun.protect ~finally:(fun()->Unix.close output)(fun()->
     IO.with_fds ~input:"-" ~output:(string_of_int(descriptor_number output))(fun files->
       CM.run(S.create ~io ~files());require(not(IO.output_written files))"Sequence export wrote archive output")));
 require !ended "Checker framed continuation did not complete";
 if stale then require(!phase=3 && !observed=[])"Stale checker reached later export callbacks"
 else require(!phase=7 && !observed=["report-export"])"Export report was duplicated or reordered"
let ()=
 require(Array.length Sys.argv=2)"Expected original complete package corpus";
 let row=fixture Sys.argv.(1) in run(get"input"row);checker_calls row ~stale:false;checker_calls row ~stale:true;
 print_endline"Framed native package source reads, prepared and supplied declarations, collection, repeated/altered checker defaults, stale rejection and lifetime closure passed"
