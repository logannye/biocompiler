(* Standalone Verify transport over actual inherited file descriptors.  These
   original package bytes are candidate input; current metadata and expected
   request/build authority arrive separately.  No producer library is linked. *)
open Bioc_wire
open Bioc_domain
module B = Bioc_artifact.Archive_budget
module W = Bioc_checker.Work_budget
module IO = Bioc_package_io.Package_io
module S = Bioc_reference_package_verify.Reference_package_verify
module V = Bioc_reference_package_check.Reference_package_check

let require condition message = if not condition then failwith message
let str value = Json.String value
let obj values = Json.Object values
let get key raw = Json.field key (Json.object_fields raw)
let text key raw = Json.string (get key raw)
let number key raw = Z.to_int (Json.integer (get key raw))
let set key value raw = obj (List.map (fun (name,old) -> name,if name=key then value else old) (Json.object_fields raw))
let without key raw = obj (List.remove_assoc key (Json.object_fields raw))
let unhex raw =
  require (String.length raw mod 2=0) "Invalid original archive hex";
  let nibble = function
    | '0'..'9' as value -> Char.code value-48
    | 'a'..'f' as value -> Char.code value-87
    | _ -> failwith "Noncanonical original archive hex" in
  String.init (String.length raw/2) (fun i -> Char.chr (16*nibble raw.[2*i]+nibble raw.[2*i+1]))
let data row = unhex (text "data" (get "value" (get "outcome" row)))
let descriptor raw = obj ["bytes",Json.int (String.length raw);"sha256",str (Canonical.sha256 raw)]
let metadata row =
  let input=get "input" row in
  let versions = [
    "reference_build","biocompiler.reference_build.v0.2";
    "human_admission_policy",Admission.policy_version;
    "reference_inputs",Bioc_reference_input.Reference_inputs.inputs_version;
    "archive","biocompiler.reference_archive.v0.4";
    "sequence_export",Bioc_reference_export.Reference_sequence_codec.export_version;
    "sequence_emitter","biocompiler.reference_sequence_emitter.v0.2";
    "construct_pipeline","biocompiler.reference_construct_pipeline.v0.2";
    "molecular_pipeline","biocompiler.exact_cds_pipeline.v0.1";
    "reference_adapter",Reference_components.adapter_version;
    "construct_generator","biocompiler.reference_construct_generator.v0.1";
    "component_checker",Composition_evidence.checker_version;
    "construct_checker",Reference_construct_evidence.checker_version;
    "molecular_checker",(if get "changed_tool" input=Json.Bool true
      then "fixture-current-checker" else Reference_molecular_evidence.checker_version)] in
  require (List.map fst versions=V.tool_ids) "Independent complete tool census changed";
  obj ["package_version",get "package_version" input;
       "tool_pins",Json.Array (List.map (fun (id,version) -> obj [
         "schema_version",str "biocompiler.tool_pin.v0.1";"id",str id;"version",str version;
         "content_fingerprint",str (Canonical.fingerprint (str version))]) versions)]
let control row = obj [
  "protocol",str "biocompiler.core.v1";"profile",str S.profile;"declaration",S.declaration;
  "request_id",str "package-verifier-test";"operation",str "verify-reference-package";
  "archive",descriptor (data row);"authority",metadata row;
  "expected_request",get "request" (get "input" row);
  "expected_build_fingerprint",Json.Null;"limits",Json.Null;"runtime",str "python314"]

external descriptor_number : Unix.file_descr -> int = "%identity"
let argument fd =
  let value=descriptor_number fd in require (value>2) "Fixture aliases a standard descriptor";string_of_int value
let with_path bytes action =
  let path=Filename.temp_file "bioc-package-verify-" ".bin" in
  Fun.protect ~finally:(fun () -> Unix.unlink path) (fun () ->
    let output=open_out_bin path in
    Fun.protect ~finally:(fun () -> close_out_noerr output) (fun () -> output_string output bytes);
    action path)
let with_open path flags action =
  let fd=Unix.openfile path flags 0o600 in
  Fun.protect ~finally:(fun () -> Unix.close fd) (fun () -> action fd)
let contents path =
  let input=open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr input)
    (fun () -> really_input_string input (in_channel_length input))
let with_archive raw action =
  with_path raw (fun input_path -> with_open input_path [Unix.O_RDONLY] (fun input ->
    with_path "" (fun output_path -> with_open output_path [Unix.O_RDWR] (fun output ->
      IO.with_fds ~input:(argument input) ~output:(argument output) (fun transport ->
        (* The service must read the complete archive, independent of the
           caller's current offset, without replacing either actual file. *)
        ignore (Unix.lseek input 1 Unix.SEEK_SET);
        let returned=action transport in
        require (not (IO.output_written transport)) "Verify published an output archive";
        require (contents output_path="") "Verify modified its private output descriptor";
        require (contents input_path=raw) "Verify changed candidate input bytes";
        returned)))))

type binding = Unbound | Request_bound | Archive_bound of Json.t
let common ~raw ~binding reply =
  Json.exact_fields ["protocol";"profile";"executable";"version";"request_id";"request_sha256";
    "operation";"archive";"status";"result";"diagnostics";"usage"] (Json.object_fields reply);
  require (text "protocol" reply="biocompiler.core.v1" && text "profile" reply=S.profile &&
    text "operation" reply="verify-reference-package" && text "executable" reply="verify" &&
    text "version" reply="0.1.0") "Reply role, operation or exact profile changed";
  let request_id,request_sha256,archive=match binding with
    | Unbound -> Json.Null,Json.Null,Json.Null
    | Request_bound -> str "package-verifier-test",str (Canonical.sha256 raw),Json.Null
    | Archive_bound descriptor -> str "package-verifier-test",str (Canonical.sha256 raw),descriptor in
  require (get "request_id" reply=request_id && get "request_sha256" reply=request_sha256 &&
    Json.equal (get "archive" reply) archive) "Reply detached from its actual control/archive binding";
  let usage=get "usage" reply in
  Json.exact_fields ["work";"retained_bytes"] (Json.object_fields usage);
  require (number "work" usage>=0 && number "work" usage<=B.defaults.max_work &&
    number "retained_bytes" usage>=0 && number "retained_bytes" usage<=B.defaults.max_retained_bytes)
    "Reply reports impossible default lifetime usage";
  require (String.length (Canonical.encode reply)+1<=number "max_response_bytes" S.declaration)
    "Reply exceeds its negotiated terminal bound"
let error ?code reply =
  require (text "status" reply="error" && get "result" reply=Json.Null) "Rejected input acquired an acceptance report";
  match Json.array (get "diagnostics" reply) with
  | [diagnostic] ->
    Json.exact_fields ["code";"message";"path"] (Json.object_fields diagnostic);
    require (String.length (text "code" diagnostic)>0 && String.length (text "message" diagnostic)>0)
      "Rejected input lost its exact diagnostic";
    Option.iter (fun expected -> require (text "code" diagnostic=expected)
      ("Unexpected verifier diagnostic: "^text "code" diagnostic)) code
  | _ -> failwith "Expected one bounded rejection diagnostic"
let success row request reply =
  require (text "status" reply="ok" && get "diagnostics" reply=Json.Array []) "Actual package verification failed";
  let original=get "value" (get "outcome" row) in
  let expected=obj ["schema_version",str V.profile;"outcome",str "pass";
    "archive_sha256",get "archive_sha256" original;"build_fingerprint",get "build_fingerprint" original;
    "request_fingerprint",get "request_fingerprint" (get "manifest" original);
    "metadata_authority",str (Canonical.fingerprint (get "authority" request));
    "claim_scope",str "Exact reference package, stage evidence and sequence consistency for software use; no biological or therapeutic claim.";
    "core_reconstruction_required",Json.Bool true] in
  require (Json.equal (get "result" reply) expected) "Complete verifier report differs from source authority and scope";
  require (number "work" (get "usage" reply)>0 && number "retained_bytes" (get "usage" reply)>0)
    "Successful verification reported no lifetime resources"
let execute ?bytes request row =
  let raw=Canonical.encode request in
  let actual=Option.value bytes ~default:(data row) in
  with_archive actual (fun transport -> S.handle ~transport raw),raw
let reject ?code ~binding request row =
  let reply,raw=execute request row in common ~raw ~binding reply;error ?code reply

let positives cases =
  List.iter (fun row -> let request=control row in let reply,raw=execute request row in
    common ~raw ~binding:(Archive_bound (get "archive" request)) reply;success row request reply) cases;
  let row=List.hd cases in
  let build=get "build_fingerprint" (get "value" (get "outcome" row)) in
  List.iter (fun request -> let reply,raw=execute request row in
    common ~raw ~binding:(Archive_bound (get "archive" request)) reply;success row request reply)
    [set "expected_build_fingerprint" build (set "expected_request" Json.Null (control row));
     set "expected_build_fingerprint" build (control row)]
let authority_failures row =
  let request=control row in
  let archive=Archive_bound (get "archive" request) in
  List.iter (fun changed -> reject ~code:"reference_package_check" ~binding:archive changed row)
    [set "expected_request" Json.Null request;
     set "expected_build_fingerprint" (str (Canonical.sha256 "another independent build")) request;
     set "expected_request" (set "fasta_line_width" (Json.int 79) (get "expected_request" request)) request;
     set "authority" (set "package_version" (str "another independently pinned SDK") (metadata row)) request;
     set "authority" (set "tool_pins" (Json.Array []) (metadata row)) request];
  let tools=Json.array (get "tool_pins" (metadata row)) in
  let changed=List.map (fun value -> if get "id" value=str "molecular_checker" then
    set "version" (str "stale-current-tool") value else value) tools in
  reject ~code:"reference_package_check" ~binding:archive
    (set "authority" (set "tool_pins" (Json.Array changed) (metadata row)) request) row;
  reject ~code:"reference_package_protocol" ~binding:archive
    (set "expected_build_fingerprint" (str "not-a-lowercase-hash") request) row
let descriptor_failures row =
  let request=control row and candidate=data row in
  List.iter (fun supplied -> let changed=set "archive" supplied request in
    reject ~code:"package_transport" ~binding:(Archive_bound supplied) changed row)
    [set "sha256" (str (Canonical.sha256 "different candidate")) (descriptor candidate);
     set "bytes" (Json.int (String.length candidate+1)) (descriptor candidate)];
  List.iter (fun supplied -> reject ~code:"package_transport" ~binding:Request_bound
    (set "archive" supplied request) row)
    [set "bytes" (Json.int 0) (descriptor candidate);
     set "sha256" (str (String.make 64 'F')) (descriptor candidate)];
  let truncated=String.sub candidate 0 (String.length candidate-1) in
  let reply,raw=execute ~bytes:truncated request row in
  common ~raw ~binding:(Archive_bound (get "archive" request)) reply;error ~code:"package_transport" reply;
  let damaged="not an archive" in
  let request=set "archive" (descriptor damaged) request in
  let reply,raw=execute ~bytes:damaged request row in
  common ~raw ~binding:(Archive_bound (descriptor damaged)) reply;error reply
let controls row =
  let request=control row in
  List.iter (fun changed -> reject ~code:"reference_package_protocol" ~binding:Unbound changed row)
    [set "protocol" (str "other-protocol") request;set "profile" (str "other-profile") request;
     set "operation" (str "build-reference-package") request;
     set "declaration" (set "output" (str "publish anything") S.declaration) request;
     set "request_id" (str (String.make 129 'x')) request];
  List.iter (fun changed -> reject ~binding:Unbound changed row)
    [without "authority" request;obj (("extra",Json.Bool true)::Json.object_fields request)];
  List.iter (fun raw -> with_archive (data row) (fun transport ->
    let reply=S.handle ~transport raw in common ~raw ~binding:Unbound reply;error reply))
    ["";"{";"{\"protocol\":1,\"protocol\":2}";
     String.make (number "max_control_bytes" S.declaration+1) ' '];
  let limits=get "limits" S.declaration in
  List.iter (fun (key,reduction) -> let reduced=set "limits" (set key (Json.int reduction) limits) request in
    reject ~binding:Request_bound reduced row)
    ["max_archive_bytes",String.length (data row)-1;"max_retained_bytes",1;"max_work",1]
let ownership row =
  let request=control row in let raw=Canonical.encode request in
  with_archive (data row) (fun transport ->
    let first=S.handle ~transport raw in
    common ~raw ~binding:(Archive_bound (get "archive" request)) first;success row request first;
    let second=S.handle ~transport raw in
    common ~raw ~binding:Request_bound second;error ~code:"package_transport" second);
  with_archive (data row) (fun transport ->
    let parent=W.create ~profile:"package.verify.foreign" ~error_code:"fixture_work" ~maximum:B.defaults.max_work () in
    let owner=B.create_owner ~parent ~retain_bytes:(fun _ -> ()) () in
    IO.bind_owner transport owner;
    let reply=S.handle ~transport raw in
    common ~raw ~binding:Request_bound reply;error ~code:"package_transport" reply;
    require (IO.read_archive transport owner (IO.descriptor_of_json ~max_bytes:B.defaults.max_archive_bytes
      (get "archive" request))=data row) "Foreign-owner rejection consumed or changed the existing owner's input");
  with_path "" (fun output_path -> with_open output_path [Unix.O_RDWR] (fun output ->
    IO.with_fds ~input:"-" ~output:(argument output) (fun transport ->
      let reply=S.handle ~transport raw in
      common ~raw ~binding:(Archive_bound (get "archive" request)) reply;error ~code:"package_transport" reply;
      require (not (IO.output_written transport) && contents output_path="") "Missing input published Verify output")))
let literals path =
  let channel=open_in_bin path in
  let raw=Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size=in_channel_length channel in require (size>0 && size<=8_388_608) "Original package witness byte ceiling";
    really_input_string channel size) in
  require (Canonical.sha256 raw="a867677f97540fcab473cbde9be813b42c139a06c4aa2fd0009e7cde9ed9f135")
    "Complete original Python package witness changed";
  let value=Json.parse_artifact ~max_bytes:8_388_608 ~max_nodes:500_000 raw in
  require (text "schema" value="biocompiler.reference_package_workflow_literals.v1") "Original package schema changed";
  let cases=Json.array (get "cases" value) in
  require (List.map (text "id") cases=["DNA:default";"RNA:default";"DNA:width1";"RNA:width10000";
    "DNA:run-metadata";"DNA:current-sdk";"RNA:current-tool";"DNA:unsupported-layout"])
    "Complete original package case census changed";
  let successful=List.filter (fun row -> text "status" (get "outcome" row)="return") cases in
  require (List.length successful=7 && text "status" (get "outcome" (List.nth cases 7))="raise")
    "Original successful archive census changed";
  (* The unsupported-layout row has no archive. Its producer rejection belongs
     to the original workflow suite; no native archive or PASS is invented. *)
  successful
let () =
  Printexc.record_backtrace true;
  require (Array.length Sys.argv=2) "Usage: test_reference_package_verify REFERENCE_PACKAGES_314";
  let cases=literals Sys.argv.(1) in
  let first=List.hd cases in
  positives cases;authority_failures first;descriptor_failures first;controls first;ownership first;
  print_endline "Standalone package Verify: original archives, independent authority, exact FD/control binding and empty output passed"
