open Bioc_wire
module I=Bioc_package_io.Package_io
module B=Bioc_artifact.Archive_budget
module W=Bioc_checker.Work_budget
let require condition message=if not condition then failwith message
let rejected label action=match action()with _->failwith("Accepted "^label)|exception Diagnostic.Error _->()
external descriptor_number : Unix.file_descr -> int = "%identity"
let argument fd=let value=descriptor_number fd in require(value>2)"Fixture uses standard descriptor";string_of_int value
let with_path data run=
  let path=Filename.temp_file "bioc-package-fd-" ".bin" in
  Fun.protect ~finally:(fun()->Unix.unlink path)(fun()->
    let output=open_out_bin path in
    Fun.protect ~finally:(fun()->close_out_noerr output)(fun()->output_string output data);
    run path)
let with_open path flags run=let fd=Unix.openfile path flags 0o600 in
  Fun.protect ~finally:(fun()->Unix.close fd)(fun()->run fd)
let pair data run=with_path data(fun input_path->with_open input_path[Unix.O_RDONLY](fun input->
  with_path ""(fun output_path->with_open output_path[Unix.O_RDWR](fun output->
    run input_path input output_path output))))
let owner ?limits ()=let maximum=match limits with None->B.defaults.max_work|Some value->value.B.max_work in
  let root=W.create ~profile:"package-io-test" ~error_code:"package-io-test-work" ~maximum () in
  B.create_owner ~parent:root ~retain_bytes:(fun _->()) ?limits ()
let descriptor data=I.descriptor_of_json ~max_bytes:67108864
  (Json.Object["bytes",Json.int(String.length data);"sha256",Json.String(Canonical.sha256 data)])
let raw path=let input=open_in_bin path in Fun.protect ~finally:(fun()->close_in_noerr input)
  (fun()->really_input_string input(in_channel_length input))
let run ?limits data=
  pair data(fun _ input path output->I.with_fds ~input:(argument input)~output:(argument output)(fun lease->
    let budget=owner ?limits () in I.bind_owner lease budget;
    require(I.input_present lease && not(I.output_written lease))"Initial lease state differs";
    ignore(Unix.lseek input 1 Unix.SEEK_SET);
    let received=I.read_archive lease budget(descriptor data) in require(received=data)"Raw bytes changed";
    let published=I.write_archive lease budget received in
    require(Json.equal(I.descriptor_to_json published)(I.descriptor_to_json(descriptor data)))"Descriptor changed";
    require(raw path=data && I.output_written lease)"Published raw bytes changed";
    rejected "repeat read"(fun()->I.read_archive lease budget(descriptor data));
    rejected "repeat write"(fun()->I.write_archive lease budget data);
    B.retained budget,(B.limits budget).max_work-W.remaining(B.work budget)))
let ownership ()=
  pair "PK\000\255\r\n"(fun _ input path output->
    let retained=ref None and first=owner() in
    I.with_fds ~input:(argument input)~output:(argument output)(fun lease->
      retained:=Some lease;
      rejected "unbound input"(fun()->I.read_archive lease first(descriptor "PK\000\255\r\n"));
      I.bind_owner lease first;
      rejected "owner replacement"(fun()->I.bind_owner lease(owner()));
      rejected "foreign input owner"(fun()->I.read_archive lease(owner())(descriptor "PK\000\255\r\n"));
      ignore(I.read_archive lease first(descriptor "PK\000\255\r\n"));
      rejected "foreign output owner"(fun()->I.write_archive lease(owner())"bytes");
      require(raw path="")"Foreign owner wrote output");
    let lease=Option.get !retained in
    rejected "released lease"(fun()->I.write_archive lease first"bytes"));
  pair "input"(fun _ _ path output->I.with_fds ~input:"-"~output:(argument output)(fun lease->
    let budget=owner() in I.bind_owner lease budget;
    require(not(I.input_present lease))"Absent input became present";
    rejected "missing input"(fun()->I.read_archive lease budget(descriptor "input"));
    ignore(I.write_archive lease budget"native output");require(raw path="native output")"Inputless output differs"))
let failures ()=
  List.iter(fun bad->pair "abc"(fun _ input path output->
    rejected "invalid descriptor number"(fun()->I.with_fds ~input:bad~output:(argument output)(fun _->()));
    require(raw path="")"Rejected lease changed output";ignore input))
    ["0";"1";"2";"03";"+3";"-1";" 3";"3 ";"/dev/fd/3";"2147483647"];
  pair "abc"(fun input_path input path output->
    rejected "same number"(fun()->I.with_fds ~input:(argument input)~output:(argument input)(fun _->()));
    with_open input_path[Unix.O_RDWR](fun writable->
      rejected "writable input"(fun()->I.with_fds ~input:(argument writable)~output:(argument output)(fun _->())));
    with_open path[Unix.O_RDONLY](fun readonly->
      rejected "readonly output"(fun()->I.with_fds ~input:(argument input)~output:(argument readonly)(fun _->())));
    with_open path[Unix.O_WRONLY;Unix.O_APPEND](fun append->
      rejected "append output"(fun()->I.with_fds ~input:(argument input)~output:(argument append)(fun _->())));
    Unix.chmod path 0o644;
    rejected "public output"(fun()->I.with_fds ~input:(argument input)~output:(argument output)(fun _->()));
    Unix.chmod path 0o600;
    require(raw path="")"Access checks changed output");
  pair "abc"(fun _ input path output->I.with_fds ~input:(argument input)~output:(argument output)(fun lease->
    let budget=owner() in I.bind_owner lease budget;
    rejected "wrong hash"(fun()->I.read_archive lease budget(descriptor "abd"));
    rejected "failed read reused"(fun()->I.read_archive lease budget(descriptor "abc"));
    require(raw path="")"Failed input wrote output"));
  pair "abc"(fun _ input path output->I.with_fds ~input:(argument input)~output:(argument output)(fun lease->
    let budget=owner() in I.bind_owner lease budget;
    let changed=open_out_bin path in output_string changed"changed";close_out changed;
    rejected "changed private output"(fun()->I.write_archive lease budget"accepted bytes");
    require(raw path="changed")"Write failure truncated existing bytes";
    rejected "failed write reused"(fun()->I.write_archive lease budget"accepted bytes")))
let resources ()=
  let data="PK\003\004"^String.make 10000 '\255' in
  let retained,work=run data in
  ignore(run ~limits:(B.make_limits ~max_retained_bytes:retained~max_work:work())data);
  rejected "one-short owner retention"(fun()->run ~limits:(B.make_limits ~max_retained_bytes:(retained-1)())data);
  rejected "one-short shared work"(fun()->run ~limits:(B.make_limits ~max_work:(work-1)())data);
  pair data(fun _ input path output->I.with_fds ~input:(argument input)~output:(argument output)(fun lease->
    let budget=owner ~limits:(B.make_limits ~max_archive_bytes:(String.length data-1)())() in
    I.bind_owner lease budget;
    rejected "reduced input size"(fun()->I.read_archive lease budget(descriptor data));
    require(raw path="")"Resource failure published output"))
let ()=ownership();failures();resources();print_endline "Raw package FD ownership, identity and resources passed"
