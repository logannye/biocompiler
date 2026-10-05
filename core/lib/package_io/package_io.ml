open Bioc_wire
module B = Bioc_artifact.Archive_budget
external duplicate_checked : int -> int -> bool -> Unix.file_descr = "bioc_package_duplicate_checked"
type descriptor = { bytes:int; sha256:string }
type input_file = { fd:Unix.file_descr; mutable consumed:bool }
type t = { input:input_file option; output:Unix.file_descr; mutable owner:B.t option;
  mutable written:bool; mutable closed:bool }
let require condition message=Diagnostic.require condition "package_transport" message
let close fd=try Unix.close fd with Unix.Unix_error _->()
let io operation=try operation() with Unix.Unix_error _|Sys_error _|Invalid_argument _|Failure _ ->
  Diagnostic.fail "package_descriptor" "Invalid or unavailable inherited package descriptor."
let number raw=
  require(String.length raw>0 && String.length raw<=10 && raw.[0]>='1' && raw.[0]<='9' &&
    String.for_all(fun c->c>='0' && c<='9')raw)"Package descriptor must be a canonical positive integer.";
  let value=try int_of_string raw with Failure _->Diagnostic.fail "package_transport" "Package descriptor is out of range." in
  require(value>2 && value<2_147_483_647)"Standard or out-of-range package descriptors are forbidden.";value
let regular fd=let value=Unix.fstat fd in require(value.Unix.st_kind=Unix.S_REG)"Package descriptors must be regular files.";value
let same left right=left.Unix.st_dev=right.Unix.st_dev && left.Unix.st_ino=right.Unix.st_ino
let with_fds ~input ~output operation=
  let input_number=if input="-" then None else Some(number input) and output_number=number output in
  require(input_number<>Some output_number)"Package descriptors must be distinct.";
  let minimum=1+max output_number(Option.value input_number ~default:2) in
  let opened=ref [] and lease=ref None in
  Fun.protect ~finally:(fun()->Option.iter(fun state->state.closed<-true)!lease;List.iter close !opened)(fun()->
    let state=io(fun()->
      let duplicate source writing=let fd=duplicate_checked source minimum writing in opened:=fd::!opened;fd in
      let input=Option.map(fun source->duplicate source false)input_number in
      let output=duplicate output_number true in
      let output_stat=regular output in
      require(output_stat.Unix.st_size=0)"Package output must be empty before use.";
      require(output_stat.Unix.st_perm land 0o077=0 && output_stat.Unix.st_nlink<=1)
        "Package output must be a private file without another hard link.";
      List.iter(fun standard->
        let observed=try Some(Unix.fstat standard)with Unix.Unix_error(Unix.EBADF,_,_)->None in
        Option.iter(fun stat->if stat.Unix.st_kind=Unix.S_REG then begin
          require(not(same stat output_stat))"Package output must not alias a standard descriptor.";
          Option.iter(fun fd->require(not(same stat(regular fd)))
            "Package input must not alias a standard descriptor.")input
        end)observed)[Unix.stdin;Unix.stdout;Unix.stderr];
      Option.iter(fun fd->require(not(same(regular fd)output_stat))"Package descriptors must not alias the same file.")input;
      {input=Option.map(fun fd->{fd;consumed=false})input;output;owner=None;written=false;closed=false}) in
    lease:=Some state;operation state)
let bind_owner state owner=
  require(not state.closed && state.owner=None && B.owns_retention owner)"Package lease requires exactly one configured owner.";
  B.reserve owner 256;state.owner<-Some owner
let owned state owner=
  require(not state.closed && Option.fold ~none:false ~some:(fun actual->actual==owner)state.owner)
    "Package descriptor belongs to a different or closed owner.";B.guard owner
let descriptor_of_json ~max_bytes raw=
  let fields=Json.object_fields raw in Json.exact_fields ["bytes";"sha256"]fields;
  let count=Json.integer(Json.field "bytes" fields) and sha256=Json.string(Json.field "sha256" fields) in
  require(Z.fits_int count)"Package descriptor length is out of range.";
  let bytes=Z.to_int count in
  require(bytes>0 && bytes<=max_bytes && String.length sha256=64 &&
    String.for_all(fun c->(c>='0' && c<='9')||(c>='a' && c<='f'))sha256)"Invalid package byte descriptor.";
  {bytes;sha256}
let descriptor_to_json value=Json.Object["bytes",Json.int value.bytes;"sha256",Json.String value.sha256]
let read_archive state owner expected=
  owned state owner;
  let source=match state.input with Some source->source|None->Diagnostic.fail "package_transport" "Package input descriptor is absent." in
  require(not source.consumed)"Package input may be consumed only once.";source.consumed<-true;
  ignore(descriptor_of_json ~max_bytes:(B.limits owner).max_archive_bytes(descriptor_to_json expected));
  (* Bound and reserve both the mutable read buffer and immutable owned bytes
     before allocation. This deliberately overcharges the temporary buffer. *)
  B.product owner expected.bytes 4;B.reserve owner(2*expected.bytes+256);
  io(fun()->
    require((regular source.fd).Unix.st_size=expected.bytes)"Package input length differs from its descriptor.";
    require(Unix.lseek source.fd 0 Unix.SEEK_SET=0)"Cannot reset package input offset.";
    let raw=Bytes.create expected.bytes and offset=ref 0 in
    while !offset<expected.bytes do
      let count=Unix.read source.fd raw !offset(min 65_536(expected.bytes- !offset)) in
      require(count>0)"Package input ended before its declared length.";offset:= !offset+count
    done;
    let extra=Bytes.create 1 in
    require(Unix.read source.fd extra 0 1=0 && (regular source.fd).Unix.st_size=expected.bytes)
      "Package input changed length during its single read.";
    let result=Bytes.to_string raw in
    require(String.equal(Canonical.sha256 result)expected.sha256)"Package input digest differs from its descriptor.";result)
let write_archive state owner data=
  owned state owner;require(not state.written)"Package output may be written only once.";state.written<-true;
  let bytes=String.length data in
  require(bytes>0 && bytes<=(B.limits owner).max_archive_bytes)"Package output exceeds its publication bound.";
  B.product owner bytes 2;B.reserve owner 256;
  io(fun()->
    require((regular state.output).Unix.st_size=0)"Package output changed before publication.";
    let sha256=Canonical.sha256 data in
    require(Unix.lseek state.output 0 Unix.SEEK_SET=0)"Cannot reset package output offset.";
    let offset=ref 0 in
    while !offset<bytes do
      let count=Unix.single_write_substring state.output data !offset(min 65_536(bytes- !offset)) in
      require(count>0)"Package output stopped before complete publication.";offset:= !offset+count
    done;
    require((regular state.output).Unix.st_size=bytes)"Package output length differs from the complete artifact.";
    {bytes;sha256})
let input_present state=Option.is_some state.input
let output_written state=state.written
