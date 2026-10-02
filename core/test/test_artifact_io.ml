open Bioc_wire
module A = Bioc_service.Artifact_io
module B = Bioc_realization_checker.Verification_workflow_budget
module W = Bioc_checker.Work_budget

let require condition message = if not condition then failwith message
let rejected label action = match action () with
  | _ -> failwith ("Artifact transport accepted " ^ label)
  | exception Diagnostic.Error _ -> ()
let descriptor text : A.descriptor = {bytes=String.length text;sha256=Canonical.sha256 text}
(* Test-only representation conversion for the supported POSIX runtimes
   (Linux and macOS), where Unix.file_descr is an OCaml integer. Reading the
   actual descriptor preserves alias tests without relying on /dev/fd stat
   identities, which differ between Linux procfs and macOS devfs. *)
external raw_fd_number : Unix.file_descr -> int = "%identity"
let number_of_fd ?(excluded=[]) fd =
  let number=raw_fd_number fd in
  require (number>2) "Test artifact descriptor used a standard stream";
  require (not (List.mem number excluded)) "Test artifact descriptors were not distinct";
  number
let write_all fd text =
  let bytes=Bytes.of_string text in
  let rec write offset = if offset<Bytes.length bytes then (
    let count=Unix.write fd bytes offset (Bytes.length bytes-offset) in
    require (count>0) "Test file write did not progress"; write (offset+count)) in
  write 0
let read_all fd =
  ignore (Unix.lseek fd 0 Unix.SEEK_SET);
  let buffer=Bytes.create 65536 and result=Buffer.create 64 in
  let rec read () = let count=Unix.read fd buffer 0 (Bytes.length buffer) in
    if count>0 then (Buffer.add_subbytes result buffer 0 count;read ()) in
  read (); Buffer.contents result
let with_path text action =
  let path=Filename.temp_file "biocompiler-native-artifact-" ".json" in
  Fun.protect ~finally:(fun () -> Unix.unlink path) (fun () ->
    let fd=Unix.openfile path [Unix.O_WRONLY;Unix.O_TRUNC] 0o600 in
    Fun.protect ~finally:(fun () -> Unix.close fd) (fun () -> write_all fd text);
    action path)
let with_open path flags action =
  let fd=Unix.openfile path flags 0o600 in
  Fun.protect ~finally:(fun () -> Unix.close fd) (fun () -> action fd)
let with_file text flags action = with_path text (fun path -> with_open path flags (fun fd -> action path fd))
let with_pair authority action =
  with_file authority [Unix.O_RDONLY] (fun authority_path source ->
    let source_number=number_of_fd source in
    with_file "" [Unix.O_RDWR] (fun output_path output ->
      let output_number=number_of_fd output in
      action authority_path source (string_of_int source_number) output_path output (string_of_int output_number)))
let with_channel authority output action =
  A.with_fds ~authority ~retained_record:"-" ~output action
let empty fd = require ((Unix.fstat fd).Unix.st_size=0) "Rejected operation modified output"
let unchanged fd original = require (read_all fd=original) "Descriptor validation modified caller-owned input"
let assert_transport_error label ~authority ~record ~output =
  rejected label (fun () -> A.with_fds ~authority ~retained_record:record ~output (fun _ -> ()))

let independent_profile () =
  let expected=Json.parse {profile|{"arguments":"--artifact-fds-v1 authority-fd retained-record-fd-or-dash output-fd","artifact_encoding":"python-json-v1","identity":"complete_bytes_sha256_and_length","input_kind":"read_only_regular_files","max_authority_bytes":16777216,"max_authority_nodes":250000,"max_control_bytes":65536,"max_depth":128,"max_number_chars":4300,"max_record_bytes":67108864,"max_record_nodes":1000000,"max_string_bytes":4194304,"node_accounting":"values_and_object_keys","operations":["run-verification-workflow","replay-verification-workflow"],"output_kind":"private_empty_regular_file","profile":"biocompiler.core.artifact_transport.v1"}|profile} in
  require (Json.equal A.profile expected) "Native transport profile differs from the independently frozen Python contract";
  require (Canonical.sha256 "{}"="44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a") "Independent complete-byte SHA256 witness changed";
  require (A.descriptor_of_json ~max_bytes:2 (A.descriptor_json (descriptor "{}"))=descriptor "{}") "Descriptor roundtrip changed";
  List.iter (fun raw -> rejected "malformed control descriptor" (fun () -> A.descriptor_of_json ~max_bytes:2 raw))
    [Json.Object ["bytes",Json.Bool true;"sha256",Json.String (Canonical.sha256 "{}")];
     Json.Object ["bytes",Json.int 2;"sha256",Json.String (String.make 64 'A')];
     Json.Object ["bytes",Json.int 2;"sha256",Json.String (Canonical.sha256 "{}");"extra",Json.Null]]

let descriptor_validation () =
  with_pair "{}" (fun _ source authority _ output output_arg ->
    List.iter (fun bad -> assert_transport_error ("descriptor argument " ^ bad)
        ~authority:bad ~record:"-" ~output:output_arg)
      ["";"0";"1";"2";"-1";"+3";" 3";"3 ";"03";"3.0";"/dev/fd/3";
       "2147483648";"999999999999999999999999999999999999999999999999"];
    assert_transport_error "repeated authority/output" ~authority ~record:"-" ~output:authority;
    assert_transport_error "repeated authority/record" ~authority ~record:authority ~output:output_arg;
    assert_transport_error "record dash variant" ~authority ~record:"--" ~output:output_arg;
    unchanged source "{}";empty output);
  with_pair "{}" (fun path source authority _ output output_arg ->
    with_open path [Unix.O_RDONLY] (fun second ->
      let other=string_of_int (number_of_fd ~excluded:[int_of_string authority] second) in
      assert_transport_error "separately opened input inode alias" ~authority ~record:other ~output:output_arg);
    unchanged source "{}";empty output);
  with_file "" [Unix.O_RDONLY] (fun path source ->
    let authority=string_of_int (number_of_fd source) in
    with_open path [Unix.O_RDWR] (fun output ->
      let output_arg=string_of_int (number_of_fd ~excluded:[int_of_string authority] output) in
      assert_transport_error "independently opened input/output inode alias" ~authority ~record:"-" ~output:output_arg;
      empty output));
  with_pair "{}" (fun path source authority _ output output_arg ->
    let alias=Filename.temp_file "biocompiler-native-artifact-alias-" ".json" in
    Unix.unlink alias;
    Fun.protect ~finally:(fun () -> Unix.unlink alias) (fun () ->
      Unix.link path alias;
      with_open alias [Unix.O_RDONLY] (fun second ->
        let other=string_of_int (number_of_fd ~excluded:[int_of_string authority] second) in
        assert_transport_error "hard-link input alias" ~authority ~record:other ~output:output_arg));
    unchanged source "{}";empty output);
  List.iter (fun flags -> with_file "{}" flags (fun _ source ->
    let authority=string_of_int (number_of_fd source) in
    with_file "" [Unix.O_RDWR] (fun _ output ->
      assert_transport_error "writable input" ~authority ~record:"-" ~output:(string_of_int (number_of_fd output));
      empty output))) [[Unix.O_RDWR];[Unix.O_WRONLY]];
  List.iter (fun flags -> with_pair "{}" (fun _ source authority path _ original_arg ->
    with_open path flags (fun output ->
      let second=number_of_fd ~excluded:[int_of_string original_arg] output in
      assert_transport_error "read-only or append output" ~authority ~record:"-" ~output:(string_of_int second));
    unchanged source "{}")) [[Unix.O_RDONLY];[Unix.O_WRONLY;Unix.O_APPEND]];
  with_pair "{}" (fun _ source authority _ output _ ->
    with_file "do not truncate" [Unix.O_RDWR] (fun _ nonempty ->
      assert_transport_error "nonempty output" ~authority ~record:"-" ~output:(string_of_int (number_of_fd nonempty));
      unchanged nonempty "do not truncate");
    unchanged source "{}";empty output);
  with_pair "{}" (fun _ source authority _ output _ ->
    with_path "" (fun path ->
      let closed=Unix.openfile path [Unix.O_RDWR] 0o600 in
      let closed_arg=string_of_int (number_of_fd closed) in
      Unix.close closed;
      assert_transport_error "closed output reused during input duplication" ~authority ~record:"-" ~output:closed_arg);
    unchanged source "{}";empty output);
  with_pair "{}" (fun _ source authority _ output output_arg ->
    let input_pipe,output_pipe=Unix.pipe () in
    Fun.protect ~finally:(fun () -> Unix.close input_pipe;Unix.close output_pipe) (fun () ->
      let pipe_arg=string_of_int (number_of_fd input_pipe) in
      assert_transport_error "pipe input" ~authority:pipe_arg ~record:"-" ~output:output_arg;
      assert_transport_error "pipe output" ~authority ~record:"-" ~output:pipe_arg);
    with_open "." [Unix.O_RDONLY] (fun directory ->
      assert_transport_error "directory input" ~authority:(string_of_int (number_of_fd directory)) ~record:"-" ~output:output_arg);
    unchanged source "{}";empty output)

let roundtrip ?limits ?parent authority_raw record_raw =
  with_pair authority_raw (fun _ source authority _ output output_arg ->
    let budget=B.create ?limits ?parent () in
    let run record_arg expected_record =
      A.with_fds ~authority ~retained_record:record_arg ~output:output_arg (fun channel ->
        A.charge_control channel ~budget 13;
        let raw=A.read_authority channel ~budget (descriptor authority_raw) in
        let record=A.read_record channel ~budget expected_record in
        let selected=match record with None -> raw | Some value -> value in
        let encoded=B.encode_report budget selected in
        let receipt=A.write_output channel ~budget ~limit:(String.length encoded) encoded in
        require (receipt=descriptor encoded) "Output receipt did not bind exact bytes";
        require (read_all output=encoded) "Published output differed from complete canonical bytes";
        unchanged source authority_raw;
        B.usage budget,encoded) in
    match record_raw with
    | None -> run "-" None
    | Some text -> with_file text [Unix.O_RDONLY] (fun _ record ->
        let answer=run (string_of_int (number_of_fd record)) (Some (descriptor text)) in
        unchanged record text;answer))

let complete_and_accounted () =
  let exact="{\"é\":[-0.0,1.0,1,9007199254740993,true,null]}" in
  let usage,encoded=roundtrip exact None in
  require (encoded=exact) "Unicode/numeric exact representation changed";
  require (usage.work_charged>String.length exact) "Artifact work was not charged";
  let maximum=usage.work_charged in
  ignore (roundtrip ~parent:(W.create ~profile:"test.artifact.parent" ~error_code:"test_artifact_parent" ~maximum ()) exact None);
  rejected "one-under shared ancestor" (fun () ->
    roundtrip ~parent:(W.create ~profile:"test.artifact.parent" ~error_code:"test_artifact_parent" ~maximum:(maximum-1) ()) exact None);
  ignore (roundtrip ~limits:(B.make_limits ~max_work:maximum ()) exact None);
  rejected "one-under operation allowance" (fun () ->
    roundtrip ~limits:(B.make_limits ~max_work:(maximum-1) ()) exact None);
  let record="{\"complete\":[1,1.0,-0.0],\"outcome\":\"FAIL\"}" in
  let _,actual=roundtrip " { \"independent\" : true } " (Some record) in
  require (actual=record) "Replay artifact was not complete";
  let chunk="\"" ^ String.make (3*1024*1024) 'x' ^ "\"" in
  let large="[" ^ String.concat "," (List.init 12 (fun _ -> chunk)) ^ "]" in
  require (String.length large>Limits.max_response_bytes) "Large fixture did not exceed the old v1 envelope";
  let _,actual=roundtrip "{}" (Some large) in
  require (actual=large) "Complete 36 MiB record changed"

let reads_and_failures () =
  List.iter (fun raw -> with_pair raw (fun _ _ authority _ output output_arg ->
    with_channel authority output_arg (fun channel ->
      let budget=B.create () in
      rejected "malformed artifact JSON" (fun () -> A.read_authority channel ~budget (descriptor raw));
      rejected "repeated failed read" (fun () -> A.read_authority channel ~budget (descriptor raw)));
    empty output)) ["";"{\"k\":1,\"k\":2}";"NaN";"1e999";"[}";"{} {}";"\"\255\"";"\"\\ud800\""];
  List.iter (fun change -> with_pair "{}" (fun _ source authority _ output output_arg ->
    with_channel authority output_arg (fun channel ->
      let budget=B.create () in
      rejected "changed declared artifact identity" (fun () -> A.read_authority channel ~budget (change (descriptor "{}")));
      rejected "repeated rejected identity read" (fun () -> A.read_authority channel ~budget (descriptor "{}")));
    unchanged source "{}";empty output))
    [(fun (x:A.descriptor) -> {x with bytes=1});(fun x -> {x with bytes=3});
     (fun x -> {x with bytes=0});(fun x -> {x with bytes=Limits.max_request_bytes+1});
     (fun x -> {x with sha256=String.make 64 '0'});(fun x -> {x with sha256="bad"})];
  with_pair "{}" (fun _ source authority _ output output_arg ->
    ignore (Unix.lseek source 1 Unix.SEEK_SET);
    with_channel authority output_arg (fun channel ->
      let budget=B.create () in
      require (Json.equal (A.read_authority channel ~budget (descriptor "{}")) (Json.Object [])) "Inherited offset changed complete read";
      rejected "repeated successful read" (fun () -> A.read_authority channel ~budget (descriptor "{}"));
      require (A.read_record channel ~budget None=None) "Absent record unexpectedly appeared");
    unchanged source "{}";empty output);
  with_pair "{}" (fun _ _ authority _ output output_arg ->
    with_channel authority output_arg (fun channel ->
      rejected "record identity without descriptor" (fun () -> A.read_record channel ~budget:(B.create ()) (Some (descriptor "{}"))));
    empty output);
  with_pair "{}" (fun _ _ authority _ output output_arg ->
    with_file "{}" [Unix.O_RDONLY] (fun _ record ->
      A.with_fds ~authority ~retained_record:(string_of_int (number_of_fd record)) ~output:output_arg (fun channel ->
        rejected "record descriptor without identity" (fun () -> A.read_record channel ~budget:(B.create ()) None)));
    empty output);
  with_pair "{}" (fun _ _ authority _ output output_arg ->
    with_channel authority output_arg (fun channel ->
      let budget=B.create () in
      A.charge_control channel ~budget 65536;
      rejected "control charged twice" (fun () -> A.charge_control channel ~budget 1));
    empty output);
  with_pair "{}" (fun _ _ authority _ output output_arg ->
    with_channel authority output_arg (fun channel ->
      rejected "oversized control" (fun () -> A.charge_control channel ~budget:(B.create ()) 65537));
    empty output)

let inventory_and_mutation () =
  let read raw action = with_pair raw (fun _ _ authority _ output output_arg ->
    with_channel authority output_arg (fun channel -> action (fun () ->
      A.read_authority channel ~budget:(B.create ()) (descriptor raw)));
    empty output) in
  let fields count = String.concat "," (List.init count (fun index ->
    "\"k" ^ string_of_int index ^ "\":0")) in
  let exact="[{" ^ fields 124999 ^ "}]" in
  read exact (fun action -> ignore (action ()));
  let one_over="{" ^ fields 125000 ^ "}" in
  read one_over (fun action -> rejected "object keys above authority node ceiling" action);
  let nested count=String.make count '[' ^ "0" ^ String.make count ']' in
  read (nested 128) (fun action -> ignore (action ()));
  read (nested 129) (fun action -> rejected "artifact depth ceiling" action);
  read (String.make 4301 '9') (fun action -> rejected "artifact numeric token ceiling" action);
  read ("\"" ^ String.make (Limits.max_string_bytes+1) 'x' ^ "\"")
    (fun action -> rejected "artifact decoded string ceiling" action);
  List.iter (fun changed -> with_pair "{}" (fun path _ authority _ output output_arg ->
    with_channel authority output_arg (fun channel ->
      with_open path [Unix.O_WRONLY;Unix.O_TRUNC] (fun writer -> write_all writer changed);
      rejected "input changed after descriptor validation" (fun () ->
        A.read_authority channel ~budget:(B.create ()) (descriptor "{}")));
    empty output)) ["{";"{} ";"[]"];
  with_pair "{}" (fun _ source authority _ output output_arg ->
    (match with_channel authority output_arg (fun _ -> failwith "artifact callback sentinel") with
     | _ -> failwith "Callback sentinel unexpectedly returned"
     | exception Failure message -> require (message="artifact callback sentinel") "Caller exception changed");
    unchanged source "{}";empty output;
    with_channel authority output_arg (fun channel ->
      ignore (A.read_authority channel ~budget:(B.create ()) (descriptor "{}"))))

let publication () =
  with_pair "{}" (fun _ _ authority _ output output_arg ->
    with_channel authority output_arg (fun channel ->
      let budget=B.create () in
      let receipt=A.write_output channel ~budget ~limit:2 "{}" in
      require (receipt=descriptor "{}") "Exact publication boundary changed";
      rejected "second publication" (fun () -> A.write_output channel ~budget ~limit:2 "{}"));
    require (read_all output="{}") "Second publication changed original output");
  List.iter (fun limit -> with_pair "{}" (fun _ _ authority _ output output_arg ->
    with_channel authority output_arg (fun channel ->
      let budget=B.create () in
      rejected "reduced publication limit" (fun () -> A.write_output channel ~budget ~limit "{}");
      rejected "repeated rejected publication" (fun () -> A.write_output channel ~budget ~limit:2 "{}"));
    empty output)) [0;1;64*1024*1024+1];
  with_pair "{}" (fun _ _ authority _ output output_arg ->
    with_channel authority output_arg (fun channel ->
      write_all output "concurrent change";
      rejected "output changed after descriptor validation" (fun () -> A.write_output channel ~budget:(B.create ()) ~limit:2 "{}"));
    require (read_all output="concurrent change") "Publication truncated changed output");
  with_pair "{}" (fun _ _ authority _ output output_arg ->
    with_channel authority output_arg (fun channel ->
      rejected "exhausted publication ancestor" (fun () -> A.write_output channel
        ~budget:(B.create ~parent:(W.create ~profile:"test.artifact.empty" ~error_code:"test_artifact_empty" ~maximum:0 ()) ())
        ~limit:2 "{}"));
    empty output);
  ignore (roundtrip "{}" None)

let scoped_inventory () =
  let ceiling=2_000_003 in
  let budget=B.create ~limits:(B.make_limits ~max_monitor_items:ceiling ()) () in
  let scope=B.create_scope budget in
  B.retain_in_scope scope 3;
  let before_failed=(B.usage budget).work_charged in
  rejected "oversized incremental scope reservation" (fun () -> B.retain_in_scope scope (ceiling-2));
  require ((B.usage budget).work_charged=before_failed) "Failed scope reservation consumed work";
  B.publish budget Json.Null;
  B.release budget 1;
  rejected "publication refunded active raw inventory" (fun () -> B.release budget 1);
  let charged=(B.usage budget).work_charged in
  B.release_scope scope;
  require ((B.usage budget).work_charged=charged) "Scope release refunded work";
  rejected "double scope release" (fun () -> B.release_scope scope);
  rejected "closed scope reuse" (fun () -> B.retain_in_scope scope 0);
  B.retain budget ceiling;B.release budget ceiling;
  let exhausted=B.create ~parent:(W.create ~profile:"test.scope.parent" ~error_code:"test_scope_parent" ~maximum:1 ()) () in
  let empty_scope=B.create_scope exhausted in
  rejected "parent failure during scoped retention" (fun () -> B.retain_in_scope empty_scope 1);
  B.release_scope empty_scope;
  let maximum=B.create () in
  let raw=B.create_scope maximum in
  B.retain_in_scope raw 1_250_000;
  B.retain maximum 4_000_000;
  B.with_retained maximum 500_000 (fun () -> B.with_workspace maximum (fun () ->
    require ((B.usage maximum).retained_peak=7_750_000) "Conservative full workflow overlap changed"));
  B.release maximum 4_000_000;B.release_scope raw;
  B.retain maximum 8_000_000;B.release maximum 8_000_000;
  with_pair "{}" (fun _ _ authority _ output output_arg ->
    let budget=B.create ~limits:(B.make_limits ~max_monitor_items:2_000_001 ()) () in
    with_channel authority output_arg (fun channel ->
      ignore (A.read_authority channel ~budget (descriptor "{}")));
    B.retain budget 2_000_001;B.release budget 2_000_001;
    empty output);
  with_pair "{}" (fun _ _ authority _ output output_arg ->
    let budget=B.create ~limits:(B.make_limits ~max_monitor_items:2_000_001 ()) () in
    with_channel authority output_arg (fun channel ->
      ignore (A.read_authority channel ~budget (descriptor "{}")));
    (* A separate channel demonstrates publication while the raw parse scope
       remains open, followed by exact lifetime cleanup. *)
    with_channel authority output_arg (fun channel ->
      ignore (A.read_authority channel ~budget (descriptor "{}"));
      B.publish budget Json.Null;
      B.release budget 1;
      rejected "transport raw scope lost through final publication" (fun () -> B.release budget 1));
    B.retain budget 2_000_001;B.release budget 2_000_001;
    empty output);
  List.iter (fun raw -> with_pair raw (fun _ _ authority _ output output_arg ->
    let budget=B.create () in
    rejected "exception while retaining parsed input" (fun () ->
      with_channel authority output_arg (fun channel ->
        ignore (A.read_authority channel ~budget (descriptor raw));
        Diagnostic.fail "test_artifact_scope" "Discard parsed input."));
    B.retain budget 8_000_000;B.release budget 8_000_000;
    empty output)) ["{}";"{\"k\":1,\"k\":2}"]

let resource_reductions () =
  ignore (roundtrip ~limits:(B.make_limits ~max_request_bytes:15 ()) "{}" None);
  rejected "one-under aggregate raw input bytes" (fun () ->
    roundtrip ~limits:(B.make_limits ~max_request_bytes:14 ()) "{}" None);
  ignore (roundtrip ~limits:(B.make_limits ~max_request_bytes:17 ()) "{}" (Some "{}"));
  rejected "retained record omitted from aggregate raw bytes" (fun () ->
    roundtrip ~limits:(B.make_limits ~max_request_bytes:16 ()) "{}" (Some "{}"));
  ignore (roundtrip ~limits:(B.make_limits ~max_report_bytes:2 ()) "{}" None);
  rejected "one-under workflow publication bytes" (fun () ->
    roundtrip ~limits:(B.make_limits ~max_report_bytes:1 ()) "{}" None);
  ignore (roundtrip ~limits:(B.make_limits ~max_report_nodes:3 ()) "{\"k\":1}" None);
  rejected "one-under workflow publication nodes" (fun () ->
    roundtrip ~limits:(B.make_limits ~max_report_nodes:2 ()) "{\"k\":1}" None)

let () =
  independent_profile ();descriptor_validation ();complete_and_accounted ();reads_and_failures ();inventory_and_mutation ();publication ();scoped_inventory ();resource_reductions ();
  print_endline "artifact_io: inherited descriptor validation, complete bytes, one shared budget and bounded publication checked"
