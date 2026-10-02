open Bioc_wire
module B = Bioc_realization_checker.Verification_workflow_budget
external duplicate_checked : int -> int -> bool -> Unix.file_descr = "bioc_artifact_duplicate_checked"
let max_control_bytes = 65_536
let maximum_record_bytes = 64 * 1024 * 1024
let maximum_record_nodes = 1_000_000
let operations = ["run-verification-workflow";"replay-verification-workflow"]
let profile = Json.Object [
  "profile",Json.String "biocompiler.core.artifact_transport.v1";
  "operations",Json.Array (List.map (fun x -> Json.String x) operations);
  "arguments",Json.String "--artifact-fds-v1 authority-fd retained-record-fd-or-dash output-fd";
  "input_kind",Json.String "read_only_regular_files";
  "output_kind",Json.String "private_empty_regular_file";
  "max_authority_bytes",Json.int Limits.max_request_bytes;
  "max_authority_nodes",Json.int Limits.max_json_nodes;
  "max_record_bytes",Json.int maximum_record_bytes;
  "max_record_nodes",Json.int maximum_record_nodes;
  "max_control_bytes",Json.int max_control_bytes;
  "max_depth",Json.int Limits.max_depth;
  "max_string_bytes",Json.int Limits.max_string_bytes;
  "max_number_chars",Json.int Limits.max_number_chars;
  "artifact_encoding",Json.String "python-json-v1";
  "node_accounting",Json.String "values_and_object_keys";
  "identity",Json.String "complete_bytes_sha256_and_length"]
let authority_profile = Json.Object (List.map (fun (key,value) -> key,
  (if key="profile" then Json.String "biocompiler.core.artifact_transport.authority.v1"
   else if key="operations" then Json.Array [Json.String "validate-verification-workflow-authority"]
   else value)) (Json.object_fields profile))
type descriptor = { bytes:int; sha256:string }
type input_file = { fd:Unix.file_descr; mutable consumed:bool }
type t = { authority:input_file; record:input_file option; output:Unix.file_descr;
  mutable written:bool; mutable input_bytes:int; mutable control_charged:bool; retained:B.scope list ref }
let require condition message = Diagnostic.require condition "artifact_transport" message
let io run = try run () with
  | Unix.Unix_error _ | Sys_error _ | Invalid_argument _ | Failure _ ->
      Diagnostic.fail "artifact_descriptor" "Invalid or unavailable inherited artifact descriptor."
let close fd = try Unix.close fd with Unix.Unix_error _ -> ()
let number text =
  let length = String.length text in
  require (length>0 && length<=10 && text.[0]>='1' && text.[0]<='9' &&
      String.for_all (fun c -> c>='0' && c<='9') text) "Descriptor arguments must be canonical positive decimal integers.";
  let value = try int_of_string text with Failure _ ->
      Diagnostic.fail "artifact_transport" "Descriptor argument is out of range." in
  require (value>2 && value<2_147_483_647) "Standard or out-of-range descriptors are forbidden.";
  value
let regular fd =
  let stat = Unix.fstat fd in
  require (stat.Unix.st_kind=Unix.S_REG) "Artifacts must use regular files.";
  stat
let same_file left right = left.Unix.st_dev=right.Unix.st_dev && left.Unix.st_ino=right.Unix.st_ino
let with_fds ~authority ~retained_record ~output run =
  let authority_number=number authority and output_number=number output in
  let record_number=if retained_record="-" then None else Some (number retained_record) in
  let numbers=authority_number::output_number::Option.to_list record_number in
  require (List.length (List.sort_uniq Int.compare numbers)=List.length numbers) "Artifact descriptors must be distinct.";
  let minimum=1+List.fold_left max 2 numbers in
  let opened=ref [] and retained=ref [] in
  Fun.protect ~finally:(fun () -> List.iter close !opened;
    List.iter B.release_scope !retained) (fun () ->
    let files=io (fun () ->
      let duplicate number writing =
        let fd=duplicate_checked number minimum writing in opened:=fd::!opened; fd in
      let authority=duplicate authority_number false in
      let record=Option.map (fun n -> duplicate n false) record_number in
      let output=duplicate output_number true in
      let authority_stat=regular authority and output_stat=regular output in
      let record_stat=Option.map regular record in
      require (output_stat.Unix.st_size=0) "Output artifact must be empty before use.";
      require (not (same_file authority_stat output_stat) &&
        Option.fold ~none:true ~some:(fun stat -> not (same_file stat authority_stat || same_file stat output_stat)) record_stat)
        "Artifact descriptors must not alias the same file.";
      {authority={fd=authority;consumed=false};record=Option.map (fun fd -> {fd;consumed=false}) record;
       output;written=false;input_bytes=0;control_charged=false;retained}) in
    run files)
let integer_field value name =
  let fields=Json.object_fields value in
  let number=Json.integer (Json.field name fields) in
  require (Z.fits_int number) "Artifact limit does not fit a native integer.";
  Z.to_int number
let reserve_raw files budget bytes =
  let maximum=integer_field (B.limits_json (B.limits budget)) "max_request_bytes" in
  require (bytes>=0 && files.input_bytes<=maximum && bytes<=maximum-files.input_bytes)
    "Complete raw input artifacts and control exceed the operation byte limit.";
  files.input_bytes<-files.input_bytes+bytes
let charge_control files ~budget bytes =
  require (not files.control_charged && bytes>0 && bytes<=max_control_bytes) "Invalid or repeated artifact control message.";
  files.control_charged<-true;
  reserve_raw files budget bytes;
  (* Parsing precedes selection of the caller's reduced budget; charge it here. *)
  B.charge budget (16*bytes+8*Limits.max_json_nodes)
let descriptor_of_json ~max_bytes value =
  let fields=Json.object_fields value in Json.exact_fields ["bytes";"sha256"] fields;
  let bytes=integer_field value "bytes" and sha256=Json.string (Json.field "sha256" fields) in
  require (bytes>0 && bytes<=max_bytes && String.length sha256=64 &&
    String.for_all (fun c -> (c>='0' && c<='9') || (c>='a' && c<='f')) sha256)
    "Malformed artifact byte descriptor.";
  {bytes;sha256}
let descriptor_json value = Json.Object ["bytes",Json.int value.bytes;"sha256",Json.String value.sha256]
let read_input files ~budget ~max_bytes ~max_nodes input expected = io (fun () ->
  require (not input.consumed) "Input artifact may be consumed only once.";
  input.consumed<-true;
  ignore (descriptor_of_json ~max_bytes (descriptor_json expected));
  reserve_raw files budget expected.bytes;
  let before=regular input.fd in
  require (before.Unix.st_size=expected.bytes) "Actual artifact size differs from its declared authority.";
  B.charge budget (8*expected.bytes+8*max_nodes);
  require (Unix.lseek input.fd 0 Unix.SEEK_SET=0) "Cannot reset artifact input offset.";
  let raw=Bytes.create expected.bytes in
  let offset=ref 0 in
  while !offset<expected.bytes do
    let count=Unix.read input.fd raw !offset (min 65_536 (expected.bytes- !offset)) in
    require (count>0) "Input artifact ended before its declared size.";
    offset:= !offset+count
  done;
  let extra=Bytes.create 1 in
  require (Unix.read input.fd extra 0 1=0 && (regular input.fd).Unix.st_size=expected.bytes)
    "Input artifact changed size during its single read.";
  let text=Bytes.to_string raw in
  require (Canonical.sha256 text=expected.sha256) "Actual artifact digest differs from its declared authority.";
  (* The charged parser counts keys before allocation as well as value nodes. *)
  let retained=B.create_scope budget in
  files.retained := retained::!(files.retained);
  let on_node () = B.retain_in_scope retained 1 in
  Json.parse_artifact ~on_node ~max_bytes ~max_nodes text)
let read_authority files ~budget expected =
  read_input files ~budget ~max_bytes:Limits.max_request_bytes ~max_nodes:Limits.max_json_nodes files.authority expected
let read_record files ~budget expected =
  match files.record,expected with
  | None,None -> None
  | Some input,Some descriptor -> Some (read_input files ~budget ~max_bytes:maximum_record_bytes
      ~max_nodes:maximum_record_nodes input descriptor)
  | _ ->
      Option.iter (fun input -> input.consumed<-true) files.record;
      Diagnostic.fail "artifact_transport" "Retained record descriptor presence differs from the control message."
let write_output files ~budget ~limit text = io (fun () ->
  require (not files.written) "Output artifact may be published only once.";
  files.written<-true;
  let size=String.length text in
  let budget_limit=integer_field (B.limits_json (B.limits budget)) "max_report_bytes" in
  require (limit>0 && limit<=maximum_record_bytes && size>0 && size<=limit && size<=budget_limit)
    "Complete artifact exceeds the selected publication limit.";
  require ((regular files.output).Unix.st_size=0) "Output artifact changed before publication.";
  B.charge budget (2*size);
  let digest=Canonical.sha256 text in
  require (Unix.lseek files.output 0 Unix.SEEK_SET=0) "Cannot reset artifact output offset.";
  let offset=ref 0 in
  while !offset<size do
    let count=Unix.single_write_substring files.output text !offset (min 65_536 (size- !offset)) in
    require (count>0) "Artifact output stopped before complete publication.";
    offset:= !offset+count
  done;
  require ((regular files.output).Unix.st_size=size) "Actual output length differs from the complete artifact.";
  {bytes=size;sha256=digest})
let read_control () =
  let buffer=Buffer.create 4096 and chunk=Bytes.create 4096 in
  let finished=ref false in
  while not !finished do
    let available=min (Bytes.length chunk) (max_control_bytes+1-Buffer.length buffer) in
    let count=input stdin chunk 0 available in
    if count=0 then finished:=true else (
      Buffer.add_subbytes buffer chunk 0 count;
      require (Buffer.length buffer<=max_control_bytes) "Artifact control message exceeds its byte limit.")
  done;
  Buffer.contents buffer
