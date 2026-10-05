open Bioc_wire
module B=Bioc_artifact.Archive_budget
module W=Bioc_checker.Work_budget
module IO=Bioc_package_io.Package_io
module V=Bioc_reference_package_check.Reference_package_check
module D=Bioc_reference_artifact.Reference_package_manifest
let profile="biocompiler.reference_package_verify.v1"
let argument="--verify-reference-package-fds-v1"
let protocol="biocompiler.core.v1"
let str value=Json.String value
let obj values=Json.Object values
let maximum_control=16_777_216
let maximum_reply=16_384
let limits_json (value:B.limits)=obj[
  "max_archive_bytes",Json.int value.max_archive_bytes;"max_member_bytes",Json.int value.max_member_bytes;
  "max_metadata_bytes",Json.int value.max_metadata_bytes;"max_entries",Json.int value.max_entries;
  "max_path_bytes",Json.int value.max_path_bytes;"max_json_nodes",Json.int value.max_json_nodes;
  "max_json_depth",Json.int value.max_json_depth;"max_retained_bytes",Json.int value.max_retained_bytes;
  "max_work",Json.int value.max_work]
let declaration=obj[
  "schema",str "biocompiler.reference_package_verify_declaration.v1";"profile",str profile;
  "argument",str argument;"protocol",str protocol;"operation",str "verify-reference-package";
  "max_control_bytes",Json.int maximum_control;"max_response_bytes",Json.int maximum_reply;
  "limits",limits_json B.defaults;
  "tool_ids",Json.Array(List.map str V.tool_ids);
  "authority_fields",Json.Array[str "package_version";str "tool_pins"];
  "runtime_profiles",Json.Array[str "python311";str "python314"];
  "archive",str "single_readonly_private_descriptor_exact_length_sha256_and_eof";
  "output",str "private_descriptor_must_remain_empty";
  "acceptance",str "fresh_producer_free_reference_stage_evidence_summary_and_export_check;Core_reconstruction_separately_required"]
let require value message=Diagnostic.require value "reference_package_protocol" message
let fields expected raw=let fields=Json.object_fields raw in Json.exact_fields expected fields;fields
let value key fields=Json.field key fields
let nullable encode=function None->Json.Null|Some value->encode value
let limits raw=
  if raw=Json.Null then B.defaults else
  let keys=List.map fst(Json.object_fields(limits_json B.defaults)) in
  let fields=fields keys raw in
  let number key=let raw=Json.integer(value key fields) in
    require(Z.fits_int raw)"Package limit exceeds the native integer range.";Z.to_int raw in
  B.make_limits ~max_archive_bytes:(number "max_archive_bytes") ~max_member_bytes:(number "max_member_bytes")
    ~max_metadata_bytes:(number "max_metadata_bytes") ~max_entries:(number "max_entries")
    ~max_path_bytes:(number "max_path_bytes") ~max_json_nodes:(number "max_json_nodes")
    ~max_json_depth:(number "max_json_depth") ~max_retained_bytes:(number "max_retained_bytes")
    ~max_work:(number "max_work")()
let reduced_work (limits:B.limits) maximum=B.make_limits
  ~max_archive_bytes:limits.max_archive_bytes ~max_member_bytes:limits.max_member_bytes
  ~max_metadata_bytes:limits.max_metadata_bytes ~max_entries:limits.max_entries
  ~max_path_bytes:limits.max_path_bytes ~max_json_nodes:limits.max_json_nodes
  ~max_json_depth:limits.max_json_depth ~max_retained_bytes:limits.max_retained_bytes ~max_work:maximum()
let response root owner bound status report diagnostics=
  let request_id,request_sha256,archive=bound in
  let used=B.defaults.max_work-W.remaining root in
  let retained=match owner with None->0|Some budget->B.retained budget in
  obj["protocol",str protocol;"profile",str profile;"executable",str "verify";"version",str "0.1.0";
    "request_id",nullable str request_id;"request_sha256",nullable str request_sha256;
    "operation",str "verify-reference-package";"archive",nullable IO.descriptor_to_json archive;
    "status",str status;"result",report;"diagnostics",Json.Array diagnostics;
    "usage",obj["work",Json.int used;"retained_bytes",Json.int retained]]
let diagnostic error=
  obj["code",str error.Diagnostic.code;"message",str error.message;"path",nullable str error.path]
let handle ~transport raw=
  let root=W.create ~profile ~error_code:"reference_package_work_limit" ~maximum:B.defaults.max_work() in
  let owner=ref None and bound=ref(None,None,None) in
  try
    require(String.length raw>0 && String.length raw<=maximum_control)"Package control request exceeds its byte bound.";
    W.charge root(String.length raw+1);
    let document=Json.parse_artifact ~on_node:(fun()->W.charge root 1) ~max_bytes:maximum_control
      ~max_nodes:250_000 raw in
    let request=fields["protocol";"profile";"declaration";"request_id";"operation";"archive";
      "authority";"expected_request";"expected_build_fingerprint";"limits";"runtime"]document in
    require(value "protocol" request=str protocol && value "profile" request=str profile &&
      value "operation" request=str "verify-reference-package" && Json.equal(value "declaration" request)declaration)
      "Incompatible independent package verification profile.";
    let runtime=match Json.string(value "runtime" request) with
      |"python311"->Bioc_artifact.Stored_zip.Python311|"python314"->Bioc_artifact.Stored_zip.Python314
      |_->Diagnostic.fail "reference_package_protocol" "Unsupported reference package Python runtime profile." in
    let request_id=Json.name(value "request_id" request) in
    require(String.length request_id<=128)"Package request identity exceeds its byte bound.";
    W.charge root(String.length raw+1);
    bound:=Some request_id,Some(Canonical.sha256 raw),None;
    let controls=limits(value "limits" request) in
    let used=B.defaults.max_work-W.remaining root in
    require(used<controls.max_work)"Package work reduction is smaller than the actual control parsing cost.";
    let budget=B.create_owner ~parent:root ~retain_bytes:(fun _->()) ~limits:(reduced_work controls(controls.max_work-used))() in
    owner:=Some budget;
    (* The full control parse was transiently bounded before reductions were
       known. Transfer it exactly once before any application capability exists. *)
    let measured=Bioc_domain.Verification_exploration.Codec.measure
      ~limits:(Bioc_domain.Verification_exploration.Codec.make_limits ~max_bytes:maximum_control
        ~max_nodes:250_000 ~charge:(B.charge budget)())document in
    B.reserve budget(String.length raw+measured.bytes+128*measured.nodes+maximum_reply+512);
    IO.bind_owner transport budget;
    let archive=IO.descriptor_of_json ~max_bytes:controls.max_archive_bytes(value "archive" request) in
    bound:=Some request_id,Some(Canonical.sha256 raw),Some archive;
    let metadata=fields["package_version";"tool_pins"](value "authority" request) in
    let tool_pins=List.map(D.Tool.of_json budget)(Json.array(value "tool_pins" metadata)) in
    let authority=V.authority_pins budget ~package_version:(Json.string(value "package_version" metadata)) ~tool_pins in
    let expected_request=match value "expected_request" request with Json.Null->None|raw->Some(D.Request.of_json budget raw) in
    let expected_build_fingerprint=match value "expected_build_fingerprint" request with Json.Null->None|raw->
      let hash=Json.string raw in require(String.length hash=64 && String.for_all(function '0'..'9'|'a'..'f'->true|_->false)hash)
        "Expected build identity must be a lowercase SHA-256.";Some hash in
    let data=IO.read_archive transport budget archive in
    let checked=V.verify ~runtime budget ~authority ?expected_request ?expected_build_fingerprint data in
    V.require_checked budget checked ~authority ?expected_request ?expected_build_fingerprint data;
    require(not(IO.output_written transport))"Independent Verify cannot publish producer output.";
    let result=response root !owner !bound "ok"(V.report checked)[] in
    require(String.length(Canonical.encode result)+1<=maximum_reply)"Package verification response exceeds its fixed reply reservation.";
    result
  with Diagnostic.Error error->
    let result=response root !owner !bound "error" Json.Null[diagnostic error] in
    if String.length(Canonical.encode result)+1<=maximum_reply then result else
      response root !owner !bound "error" Json.Null[diagnostic{
        Diagnostic.code="reference_package_diagnostic_limit";message="Package diagnostic exceeds the fixed terminal reply bound.";path=None}]
let run ~input ~output=
  let root=W.create ~profile ~error_code:"reference_package_work_limit" ~maximum:B.defaults.max_work() in
  let terminal error=response root None(None,None,None)"error"Json.Null[diagnostic error] in
  let reply=try IO.with_fds ~input ~output(fun transport->
    let bytes=Buffer.create 4096 and chunk=Bytes.create 4096 in
    let rec loop()=
      let count=Stdlib.input stdin chunk 0 (min 4096 (maximum_control+1-Buffer.length bytes)) in
      if count=0 then () else begin Buffer.add_subbytes bytes chunk 0 count;
        require(Buffer.length bytes<=maximum_control)"Package control request exceeds its byte bound.";loop()end in
    loop();handle ~transport(Buffer.contents bytes))
  with Diagnostic.Error error->terminal error in
  output_string stdout(Canonical.encode reply^"\n");flush stdout
