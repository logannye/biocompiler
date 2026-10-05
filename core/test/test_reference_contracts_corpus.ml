open Bioc_wire
open Bioc_domain

module R = Reference_manifest
module A = Reference_components
module C = Reference_construct
module M = Reference_molecular
module CE = Reference_construct_evidence
module ME = Reference_molecular_evidence
module CC = Bioc_checker.Reference_construct_check
module MC = Bioc_checker.Reference_molecular_check
module P = Bioc_compiler.Reference_construct_producer
module E = Bioc_compiler.Reference_sequence_emitter
module Codec = Verification_exploration.Codec

let require condition message = if not condition then failwith message
let field key value = Json.field key (Json.object_fields value)
let text key value = Json.string (field key value)
let array key value = Json.array (field key value)
let integer value = Z.to_int (Json.integer value)
let obj value = Json.Object value
let str value = Json.String value
let pin = "69c26f9329ec1d3a40e17a0a5f70d311611121d57b9b9f9962163678b1dc952c"
let physical_pin = "f0d3acadad15fbc29f195fc1a7dae875e8fb027565ec20fdbe1934fec7f3cf1b"
let test_ids_pin = "a4f7edc1534440136c798e4ec91443dc3c5c90dbef48413e8fa2b93cc4506ca0"
let document_count = 4000
let document_bytes = 34_923_274
let observation_count = 22_584
let method_count = 72
let source_count = 203

let hash value =
  require (String.length value = 64 && String.for_all (function
    | '0'..'9' | 'a'..'f' -> true | _ -> false) value) "Unsafe reference corpus identity";
  value

let read_raw ~maximum path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let bytes = in_channel_length channel in
    require (bytes > 0 && bytes <= maximum) "Reference source/document byte bound";
    really_input_string channel bytes)

let source_witness root path pin =
  let raw=read_raw ~maximum:1_000_000 (Filename.concat root path) in
  require(Canonical.sha256 raw=pin) "Reference finite source witness changed";
  Json.parse_artifact ~max_bytes:1_000_000 ~max_nodes:10_000 raw

let restore_source_lines current changes =
  let lines raw=if raw="" then [] else
    match List.rev(String.split_on_char '\n' raw) with
    | ""::rest->List.map(fun line->line^"\n")(List.rev rest)
    | _->failwith "Reference source fragment lacks its terminal newline" in
  let split count values=
    let rec take remaining prefix tail=if remaining=0 then List.rev prefix,tail else
      match tail with head::rest->take(remaining-1)(head::prefix)rest
      | []->failwith "Reference source witness span exceeds its complete module" in
    require(count>=0) "Reference source witness span is negative";take count [] values in
  List.fold_left(fun values change->
    let start=integer(field "new_start_line" change) and finish=integer(field "new_end_line" change) in
    let before=lines(text "before" change) and after=lines(text "after" change) in
    require(start>0 && finish>=start-1 && List.length after=finish-start+1 &&
      List.length before=integer(field "old_end_line" change)-integer(field "old_start_line" change)+1)
      "Reference source witness span lengths differ";
    let prefix,remaining=split(start-1) values in
    let actual,suffix=split(List.length after)remaining in
    require(actual=after) "Reference source witness replacement bytes differ";
    prefix@before@suffix)(lines current)(List.rev changes) |> String.concat ""

let reference_manager_view_original root name current =
  let previous_pin="f5c3410fb93d99182a1c5b9d8f3fa948990a0e1d4ce0b3b609c6b9f470d67bdd"
  and current_pin="44eeed2c22a9d07ff254dcd5b1e1edd26cf7e6bcfc29918ae20da39c2fbb544c" in
  require(name="src/biocompiler/core_pipeline_manager.py" &&
    Canonical.sha256 current=current_pin && String.length current=94893)
    "Unreviewed reference manager view source substitution";
  let witness=source_witness root "tests/conformance/reference-manager-source-counterpart-v5.json"
    "56e6f74417aab4de65eafdc4e7ca00a78db736c4b3ae8608be046a6340ce913d" in
  Json.exact_fields ["schema_version";"base_revision";"path";"original_sha256";"current_sha256";
    "original_bytes";"current_bytes";"changes";"scope";"predecessor"] (Json.object_fields witness);
  let predecessor=field "predecessor" witness in
  Json.exact_fields ["path";"sha256"] (Json.object_fields predecessor);
  require(text "schema_version" witness="biocompiler.reference_manager_source_counterpart.v5" &&
    text "base_revision" witness="0297d583d5774dc8991fda24c4f8fb39a277cc9a" &&
    text "path" witness=name && text "original_sha256" witness=previous_pin &&
    text "current_sha256" witness=current_pin && integer(field "original_bytes" witness)=93594 &&
    integer(field "current_bytes" witness)=94893 &&
    text "path" predecessor="tests/conformance/reference-manager-source-counterpart-v4.json" &&
    text "sha256" predecessor="7c17725b7d5e5843418dfea595b97aeb786ffc2ed2bf477d16db40012533c143" &&
    text "scope" witness="Exact historical source restoration only; current structural view validation is separate")
    "Reference manager view source witness lost its exact authority";
  let changes=array "changes" witness in
  let spans=List.map(fun change->
    Json.exact_fields ["old_start_line";"old_end_line";"new_start_line";"new_end_line";"before";"after"]
      (Json.object_fields change);
    integer(field "old_start_line" change),integer(field "old_end_line" change),
    integer(field "new_start_line" change),integer(field "new_end_line" change)) changes in
  require(spans=[112,117,112,139]) "Reference manager view exact source span census differs";
  let restored=restore_source_lines current changes in
  require(String.length restored=93594 && Canonical.sha256 restored=previous_pin)
    "Reference manager view whole preceding source differs";
  restored

let reference_manager_original root name expected current =
  let current=reference_manager_view_original root name current in
  let old_pin="40a08477c97a97159372d9723267df3cacf8335a59d6b00ada34bb56470e31f3"
  and previous_pin="0c0cfac138484cf71f1bb1303e66873b8b148ca236e07930fdbadd0b477a11be"
  and routed_pin="18ee9bd517524b4440bcf29292a5d834470603713d662198b83ca61373c7fd09"
  and merged_pin="562052f3848c27ccb3fd19f156bd019da44aed58abe8cd4a2c7bd922ba07fc5b"
  and current_pin="f5c3410fb93d99182a1c5b9d8f3fa948990a0e1d4ce0b3b609c6b9f470d67bdd"
  and witness_path="tests/conformance/reference-manager-source-counterpart-v1.json"
  and witness_pin="9f4406d46a7d18db944094ea6875a1daceb3d327b2da8e8029250e312ea833f8" in
  require(name="src/biocompiler/core_pipeline_manager.py" && expected=old_pin &&
    Canonical.sha256 current=current_pin) "Unreviewed original reference source substitution";
  let attempt=source_witness root "tests/conformance/reference-manager-source-counterpart-v4.json" "7c17725b7d5e5843418dfea595b97aeb786ffc2ed2bf477d16db40012533c143" in
  let attempt_predecessor=field "predecessor" attempt in
  require(text "schema_version" attempt="biocompiler.reference_manager_source_counterpart.v4" &&
    text "path" attempt=name && text "original_sha256" attempt=merged_pin && text "current_sha256" attempt=current_pin &&
    text "base_revision" attempt="7645c254b170846cca2289090111241e20c3769d" &&
    text "path" attempt_predecessor="tests/conformance/reference-manager-source-counterpart-v3.json" && text "sha256" attempt_predecessor="dd91ae7b9929f5806105245461a70874609781eb93a9dceffed53cfeffe13455")
    "Molecular attempt source update lost its exact predecessor";
  let attempt_changes=array "changes" attempt in
  require(List.length attempt_changes=1 && List.for_all(fun key->integer(field key(List.hd attempt_changes))=44)
    ["old_start_line";"old_end_line";"new_start_line";"new_end_line"])
    "Molecular attempt source update is not the exact declaration assignment";
  let current=restore_source_lines current attempt_changes in
  require(Canonical.sha256 current=merged_pin) "Molecular attempt whole source restoration differs";
  let merge=source_witness root "tests/conformance/reference-manager-source-counterpart-v3.json"
    "dd91ae7b9929f5806105245461a70874609781eb93a9dceffed53cfeffe13455" in
  let merge_predecessor=field "predecessor" merge in
  require(text "schema_version" merge="biocompiler.reference_manager_source_counterpart.v3" &&
    text "path" merge=name && text "original_sha256" merge=routed_pin &&
    text "current_sha256" merge=merged_pin &&
    text "base_revision" merge="28d2b2ceb119015e5743819bab695e02e4d6b9a9" &&
    text "path" merge_predecessor="tests/conformance/reference-manager-source-counterpart-v2.json" &&
    text "sha256" merge_predecessor="d19d7e706876ac234e2f3e5a45c66ebbf9625599a880c15dec64595c1bbed8e4")
    "Ordered merge source update lost its exact predecessor";
  let merge_changes=array "changes" merge in
  require(List.length merge_changes=4) "Ordered merge finite source change census differs";
  let routed=restore_source_lines current merge_changes in
  require(Canonical.sha256 routed=routed_pin) "Ordered merge whole source restoration differs";
  let update=source_witness root "tests/conformance/reference-manager-source-counterpart-v2.json"
    "d19d7e706876ac234e2f3e5a45c66ebbf9625599a880c15dec64595c1bbed8e4" in
  let predecessor=field "predecessor" update in
  require(text "schema_version" update="biocompiler.reference_manager_source_counterpart.v2" &&
    text "path" update=name && text "original_sha256" update=previous_pin &&
    text "current_sha256" update=routed_pin &&
    text "base_revision" update="e73743bc2f17597b57ac15869986255802289615" &&
    text "path" predecessor=witness_path && text "sha256" predecessor=witness_pin)
    "Reference manager source update lost its exact authority";
  let updates=array "changes" update in
  require(List.length updates=1) "Reference manager declaration update census differs";
  let change=List.hd updates in
  require(List.for_all(fun key->integer(field key change)=44)
    ["new_start_line";"new_end_line";"old_start_line";"old_end_line"] &&
    String.starts_with ~prefix:"_APPLICATION_JSON = " (text "before" change) &&
    String.starts_with ~prefix:"_APPLICATION_JSON = " (text "after" change))
    "Reference manager update is not its exact declaration assignment";
  let previous=restore_source_lines routed updates in
  require(Canonical.sha256 previous=previous_pin) "Reference preceding complete module differs";
  let witness=source_witness root witness_path witness_pin in
  require(text "schema_version" witness="biocompiler.reference_manager_source_counterpart.v1" &&
    text "path" witness=name && text "original_sha256" witness=old_pin &&
    text "current_sha256" witness=previous_pin &&
    text "base_revision" witness="a8cf5266963abfb5beae408c296a6f626e8f51fe")
    "Reference manager source witness lost its exact authority";
  let changes=array "changes" witness in
  require(List.length changes=6) "Reference manager finite source change census differs";
  restore_source_lines previous changes

let reference_routed_original root name expected current =
  require(List.mem name ["src/biocompiler/compiler/construct.py";"src/biocompiler/compiler/molecular.py"])
    "Unreviewed reference public source substitution";
  let witness=source_witness root "tests/conformance/reference-public-routing-source-counterpart-v1.json"
    "949bd00942bbaa8c6107c490692e38007e41309b0d8f22b0bccd4d8f8514f074" in
  require(text "schema" witness="biocompiler.reference_public_routing_source_counterpart.v1" &&
    text "base_revision" witness="e73743bc2f17597b57ac15869986255802289615")
    "Reference public source witness lost its exact authority";
  let row=field name (field "entrypoint_prefixes" witness) in
  require(text "original_sha256" row=expected && text "current_sha256" row=Canonical.sha256 current &&
    integer(field "current_bytes" row)=String.length current)
    "Reference public complete source differs";
  let insertion=field "insertion" row in
  let offset=integer(field "byte_offset" insertion) and added=text "text" insertion in
  let count=String.length added in
  require(offset>=0 && offset<=String.length current && count<=String.length current-offset &&
    String.sub current offset count=added &&
    integer(field "original_bytes" row)=String.length current-count)
    "Reference public five-line source prefix differs";
  String.sub current 0 offset ^ String.sub current (offset+count) (String.length current-offset-count)

let reference_callback_drain_original root name current =
  let previous_pin="96cf3c4c70231f3039e2e16c51efc06bc202c86208f94dbddd5f438996c1bb5a"
  and current_pin="d24cb3b78df7b7c85d0bbec5cd3c7634ca4756c5e8b0e113a8a3ba7258229a54" in
  require(name="src/biocompiler/core_pipeline_callback_session.py" &&
    Canonical.sha256 current=current_pin && String.length current=32785)
    "Unreviewed reference callback drain source substitution";
  let witness=source_witness root "tests/conformance/reference-callback-source-counterpart-v2.json"
    "878291d0b0e70db1f5e98611e103099d252ab3ffacf4995ae72ae73a9a9e16ce" in
  Json.exact_fields ["schema_version";"base_revision";"path";"original_sha256";"current_sha256";
    "original_bytes";"current_bytes";"changes";"scope";"predecessor"] (Json.object_fields witness);
  let predecessor=field "predecessor" witness in
  Json.exact_fields ["path";"sha256"] (Json.object_fields predecessor);
  require(text "schema_version" witness="biocompiler.reference_callback_source_counterpart.v2" &&
    text "base_revision" witness="4baaaf7e6e19ef9138372746495ef4e0fa51b71f" &&
    text "path" witness=name && text "original_sha256" witness=previous_pin &&
    text "current_sha256" witness=current_pin && integer(field "original_bytes" witness)=32588 &&
    integer(field "current_bytes" witness)=32785 &&
    text "path" predecessor="tests/conformance/reference-callback-source-counterpart-v1.json" &&
    text "sha256" predecessor="e3be989e0a76913f64ec959d4354bb4a352c70e0bf661ca58df68db15e544b5c" &&
    text "scope" witness="Exact historical source restoration only; current transport validation is separate")
    "Reference callback drain source witness lost its exact authority";
  let changes=array "changes" witness in
  let spans=List.map(fun change->
    Json.exact_fields ["old_start_line";"old_end_line";"new_start_line";"new_end_line";"before";"after"]
      (Json.object_fields change);
    integer(field "old_start_line" change),integer(field "old_end_line" change),
    integer(field "new_start_line" change),integer(field "new_end_line" change)) changes in
  require(spans=[355,355,355,358]) "Reference callback drain exact source span census differs";
  let restored=restore_source_lines current changes in
  require(String.length restored=32588 && Canonical.sha256 restored=previous_pin)
    "Reference callback drain whole preceding source differs";
  restored

let reference_callback_original root name expected current =
  let current=reference_callback_drain_original root name current in
  let old_pin="0ff388509eb9c123b87cf5decc1f35cf5eaca61a02d84a756beba7150de17018"
  and current_pin="96cf3c4c70231f3039e2e16c51efc06bc202c86208f94dbddd5f438996c1bb5a" in
  require(name="src/biocompiler/core_pipeline_callback_session.py" && expected=old_pin &&
    Canonical.sha256 current=current_pin) "Unreviewed reference callback source substitution";
  let witness=source_witness root "tests/conformance/reference-callback-source-counterpart-v1.json"
    "e3be989e0a76913f64ec959d4354bb4a352c70e0bf661ca58df68db15e544b5c" in
  Json.exact_fields ["schema_version";"base_revision";"path";"original_sha256";"current_sha256";
    "original_bytes";"current_bytes";"changes";"scope"] (Json.object_fields witness);
  require(text "schema_version" witness="biocompiler.reference_callback_source_counterpart.v1" &&
    text "base_revision" witness="b27f52447f49c749d33cac17f3bbb6fe772cbc24" &&
    text "path" witness=name && text "original_sha256" witness=old_pin &&
    text "current_sha256" witness=current_pin && integer(field "original_bytes" witness)=32312 &&
    integer(field "current_bytes" witness)=String.length current &&
    text "scope" witness="Exact historical source restoration only; current resource profile validation is separate")
    "Reference callback source witness lost its exact authority";
  let changes=array "changes" witness in
  let spans=List.map(fun change ->
    Json.exact_fields ["old_start_line";"old_end_line";"new_start_line";"new_end_line";"before";"after"]
      (Json.object_fields change);
    integer(field "old_start_line" change),integer(field "old_end_line" change),
    integer(field "new_start_line" change),integer(field "new_end_line" change)) changes in
  require(spans=[31,31,31,31;33,33,33,33;309,309,309,309;377,376,377,379;
    380,380,383,383;411,411,414,414;421,421,424,425;430,430,434,435])
    "Reference callback exact source span census differs";
  let restored=restore_source_lines current changes in
  require(String.length restored=integer(field "original_bytes" witness))
    "Reference callback whole source byte count differs";
  restored

let reference_session_original root name expected current =
  let original_pin="b0c744d8f3a38b1681805250ccf93884ba866678527cf366bcf08ff326da080d"
  and current_pin="8de06056804e4e58350fa562c438acf2b6306a462edd9df3a1da2070f298d169" in
  require(name="src/biocompiler/core_pipeline_session.py" && expected=original_pin &&
    Canonical.sha256 current=current_pin && String.length current=34104)
    "Unreviewed reference session source substitution";
  let witness=source_witness root "tests/conformance/reference-session-source-counterpart-v1.json"
    "0ad1db1de89c118f74d8b0237e9ecad7e09da28d02931362332ac520fc911250" in
  Json.exact_fields ["schema_version";"base_revision";"path";"original_sha256";"current_sha256";
    "original_bytes";"current_bytes";"changes";"scope"] (Json.object_fields witness);
  require(text "schema_version" witness="biocompiler.reference_session_source_counterpart.v1" &&
    text "base_revision" witness="0297d583d5774dc8991fda24c4f8fb39a277cc9a" &&
    text "path" witness=name && text "original_sha256" witness=original_pin &&
    text "current_sha256" witness=current_pin && integer(field "original_bytes" witness)=33907 &&
    integer(field "current_bytes" witness)=34104 &&
    text "scope" witness="Exact historical source restoration only; current session transport validation is separate")
    "Reference session source witness lost its exact authority";
  let changes=array "changes" witness in
  let spans=List.map(fun change->
    Json.exact_fields ["old_start_line";"old_end_line";"new_start_line";"new_end_line";"before";"after"]
      (Json.object_fields change);
    integer(field "old_start_line" change),integer(field "old_end_line" change),
    integer(field "new_start_line" change),integer(field "new_end_line" change)) changes in
  require(spans=[418,418,418,421]) "Reference session exact source span census differs";
  let restored=restore_source_lines current changes in
  require(String.length restored=33907 && Canonical.sha256 restored=original_pin)
    "Reference session whole original source differs";
  restored

(* Package integration is one additional finite source restoration layer.
   Its witnesses bind the whole current and preceding module; the historical
   reader below and all historical pins remain unchanged. *)
let reference_package_original root name current=
  let support_names=["src/biocompiler/core_pipeline_manager.py";"src/biocompiler/core_pipeline_callback_session.py"] in
  let public_names=["compiler/reference.py";"registry/reference_builds.py";"artifacts/sequences.py";
    "verification/components.py";"verification/construct.py";"verification/molecular.py"] in
  if List.mem name support_names then begin
    let witness=source_witness root "tests/conformance/reference-package-transport-source-counterpart-v1.json"
      "80573b86ff3e5f08bedacbf631a35d8d7c4a5598e5b80175debc4a74175b67e9" in
    require(text "schema_version" witness="biocompiler.reference_package_transport_counterpart.v1" &&
      text "base_revision" witness="573cfdf6504572cfc0fdd045bbd018c9e4d85320" &&
      List.map fst(Json.object_fields(field "files" witness))=support_names)
      "Package support restoration changed its exact scope";
    let entry=field name(field "files" witness) in
    require(Canonical.sha256 current=text "after_sha256" entry && String.length current=integer(field "after_bytes" entry))
      "Package support whole current source differs";
    let changes=Json.array(field "changes" entry) in
    require(List.length changes=(if name=List.hd support_names then 3 else 17))"Package support change census differs";
    let restored=List.fold_left(fun source change->
      let offset=integer(field "byte_offset" change) and before=text "before" change and after=text "after" change in
      require(offset>=0 && offset<=String.length source-String.length after && String.sub source offset(String.length after)=after)
        "Package support exact replacement span differs";
      String.sub source 0 offset^before^String.sub source(offset+String.length after)(String.length source-offset-String.length after))
      current(List.rev changes) in
    require(Canonical.sha256 restored=text "before_sha256" entry && String.length restored=integer(field "before_bytes" entry))
      "Package support whole preceding source differs";restored
  end else
  let prefix="src/biocompiler/" in
  let relative=if String.starts_with ~prefix name then String.sub name(String.length prefix)(String.length name-String.length prefix)else "" in
  if not(List.mem relative public_names)then current else begin
    let witness=source_witness root "protocol/reference-package-public-prefixes-v1.json"
      "2056c3a8f996646999bcbfc690e553c315a6c615a41484ed429b44b067ca7d96" in
    require(text "schema_version" witness="biocompiler.reference_package_public_prefixes.v1" &&
      text "base_revision" witness="573cfdf6504572cfc0fdd045bbd018c9e4d85320" &&
      List.map fst(Json.object_fields(field "files" witness))=public_names)
      "Package public restoration changed its exact scope";
    let entry=field relative(field "files" witness) in
    require(Canonical.sha256 current=text "after_sha256" entry)"Package public whole current source differs";
    let restored=List.fold_left(fun source change->
      let fragment=text "text" change in require(String.length fragment>0)"Empty public prefix";
      let count=String.length source-String.length fragment in
      let rec matches offset found=if offset>count then List.rev found else
        matches(offset+1)(if String.sub source offset(String.length fragment)=fragment then offset::found else found) in
      let offset=match matches 0 [] with [offset]->offset|_->failwith"Package public prefix occurrence differs" in
      String.sub source 0 offset^String.sub source(offset+String.length fragment)(String.length source-offset-String.length fragment))
      current(Json.array(field "prefixes" entry)) in
    require(Canonical.sha256 restored=text "before_sha256" entry)"Package public whole preceding source differs";restored
  end

let reference_original root name expected current =
  let current=reference_package_original root name current in
  let restored=if Canonical.sha256 current=expected then current else if name="src/biocompiler/core_pipeline_manager.py" then
    reference_manager_original root name expected current
    else if name="src/biocompiler/core_pipeline_callback_session.py" then
      reference_callback_original root name expected current
    else if name="src/biocompiler/core_pipeline_session.py" then
      reference_session_original root name expected current
    else reference_routed_original root name expected current in
  let archived=read_raw ~maximum:1_000_000(Filename.concat root
    ("tests/conformance/reference-original-sources-v1/"^expected^".blob")) in
  require(Canonical.sha256 restored=expected && Canonical.sha256 archived=expected && restored=archived)
    "Reference finite witness does not restore the whole original module";
  restored

let read_document path =
  let raw = read_raw ~maximum:1_000_001 path in
  let value = Json.parse_artifact ~max_bytes:1_000_001 ~max_nodes:1_000_000 raw in
  require (Canonical.encode value ^ "\n" = raw) "Noncanonical reference document bytes";
  value, String.length raw

let equal label actual expected =
  let actual = Canonical.encode actual and expected = Canonical.encode expected in
  require (actual = expected)
    (label ^ ": complete output/numeric identity differs (actual " ^ Canonical.sha256 actual ^
      ", expected " ^ Canonical.sha256 expected ^ ")")

type actual = {
  value : Json.t;
  fingerprint : string option;
  layout_fingerprint : string option;
  json : string option;
}

let bare value = { value; fingerprint=None; layout_fingerprint=None; json=None }
let represented ?layout_fingerprint ?(reference_manifest=false) value fingerprint =
  {value; fingerprint=Some fingerprint; layout_fingerprint;
   json=Some (if reference_manifest then Legacy_ascii.encode ~layout:(Legacy_ascii.Indented 2) value ^ "\n"
              else Legacy_json.pretty_utf8 value)}

module type RECORD = sig
  type t
  val of_json : ?limits:Codec.limits -> ?path:string -> Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val to_json : t -> Json.t
  val fingerprint : t -> string
end

let decode (type a) (module D : RECORD with type t = a) ~kind ~json_text
    ?(layout=(fun (_:a) -> None)) raw =
  let decoded = if json_text then D.of_json_text (Json.string raw) else D.of_json raw in
  let value = D.to_json decoded in
  if kind = "reference-record" then
    {value; fingerprint=Some (D.fingerprint decoded); layout_fingerprint=None; json=None}
  else represented ?layout_fingerprint:(layout decoded)
    ~reference_manifest:(kind="reference-manifest") value (D.fingerprint decoded)

let decode_domain kind json_text raw =
  match kind with
  | "reference-record" -> decode (module R.Record) ~kind ~json_text raw
  | "reference-manifest" -> decode (module R.Manifest) ~kind ~json_text raw
  | "reference-selection" -> decode (module A.Selection) ~kind ~json_text raw
  | "sequence-range" -> decode (module C.Sequence_range) ~kind ~json_text raw
  | "construct-reference" -> decode (module C.Reference) ~kind ~json_text raw
  | "construct-molecule" -> decode (module C.Molecule) ~kind ~json_text raw
  | "component-placement" -> decode (module C.Placement) ~kind ~json_text raw
  | "construct-feature" -> decode (module C.Feature) ~kind ~json_text raw
  | "construct-junction" -> decode (module C.Junction) ~kind ~json_text raw
  | "regulatory-relationship" -> decode (module C.Regulatory_relationship) ~kind ~json_text raw
  | "construct-dependency" -> decode (module C.Dependency) ~kind ~json_text raw
  | "layout-evidence-policy" -> decode (module C.Evidence_policy) ~kind ~json_text raw
  | "construct-request" -> decode (module C.Request) ~kind ~json_text
      ~layout:(fun value -> Some (C.Request.layout_fingerprint value)) raw
  | "construct-candidate" -> decode (module C.Candidate) ~kind ~json_text
      ~layout:(fun value -> Some (C.Candidate.layout_fingerprint value)) raw
  | "feature-status" -> decode (module M.Feature_status) ~kind ~json_text raw
  | "translation-policy" -> decode (module M.Translation_policy) ~kind ~json_text raw
  | "encoding-policy" -> decode (module M.Encoding_policy) ~kind ~json_text raw
  | "encoding-evidence-policy" -> decode (module M.Evidence_policy) ~kind ~json_text raw
  | "encoding-change" -> decode (module M.Change) ~kind ~json_text raw
  | "molecular-record" -> decode (module M.Record) ~kind ~json_text raw
  | "molecular-artifact" -> decode (module M.Artifact) ~kind ~json_text
      ~layout:(fun value -> Some (M.Artifact.layout_fingerprint value)) raw
  | "construct-result" -> decode (module CE.Result) ~kind ~json_text raw
  | "molecular-result" -> decode (module ME.Result) ~kind ~json_text raw
  | _ -> failwith ("Unimplemented reference domain kind: " ^ kind)

(* The original ordinary functions receive already typed objects. A failure
   while reconstructing one of those supplied objects is NOT an equivalent
   function rejection, even if its message happens to resemble the expectation. *)
exception Frontend_failure of string * Diagnostic.t
let frontend label decode raw =
  try decode raw with Diagnostic.Error error -> raise (Frontend_failure (label,error))

let optional_string = function Json.Null -> None | value -> Some (Json.string value)
let manifests raw = Json.object_fields raw |> List.map (fun (key,value) ->
  key, frontend ("manifests/" ^ key) R.of_json value)

let construct_request value = represented ~layout_fingerprint:(C.Request.layout_fingerprint value)
  (C.Request.to_json value) (C.Request.fingerprint value)
let construct_candidate value = represented ~layout_fingerprint:(C.Candidate.layout_fingerprint value)
  (C.Candidate.to_json value) (C.Candidate.fingerprint value)
let molecular_artifact value = represented ~layout_fingerprint:(M.Artifact.layout_fingerprint value)
  (M.Artifact.to_json value) (M.Artifact.fingerprint value)
let construct_result value = represented (CE.Result.to_json value) (CE.Result.fingerprint value)
let molecular_result value = represented (ME.Result.to_json value) (ME.Result.fingerprint value)

let execute operation inputs =
  let get key = field key inputs in
  let exact keys = Json.exact_fields keys (Json.object_fields inputs) in
  let request () = frontend "request" C.Request.of_json (get "request") in
  let candidate () = frontend "candidate" C.Candidate.of_json (get "candidate") in
  let construct () = frontend "construct" C.Candidate.of_json (get "construct") in
  let registry () = frontend "registry" Component_registry.of_json (get "registry") in
  let manifest () = frontend "manifest" R.of_json (get "manifest") in
  let all_manifests () = manifests (get "manifests") in
  if String.starts_with ~prefix:"decode-" operation then (
    let suffix = String.sub operation 7 (String.length operation - 7) in
    let json_text = String.ends_with ~suffix:"-json" suffix in
    let kind = if json_text then String.sub suffix 0 (String.length suffix - 5) else suffix in
    exact [if json_text then "text" else "data"];
    decode_domain kind json_text (get (if json_text then "text" else "data")))
  else match operation with
  | "normalize-sequence" ->
      exact ["raw_text";"alphabet"];
      let value,log = R.normalize_sequence_json ~raw_text:(get "raw_text") ~alphabet:(get "alphabet") () in
      bare (Json.Array [str value;log])
  | "translate-cds" ->
      exact ["sequence";"alphabet"];
      bare (str (R.translate_cds_json ~sequence:(get "sequence") ~alphabet:(get "alphabet") ()))
  | "adapt-reference-component" ->
      exact ["manifest";"selection"];
      let manifest = manifest () in
      let selection = frontend "selection" A.Selection.of_json (get "selection") in
      bare (Component.to_json (A.adapt_reference_component manifest selection))
  | "reference-feature-statuses" ->
      exact ["reference"];
      let reference = frontend "reference" R.Record.of_json (get "reference") in
      bare (Json.Array (List.map M.Feature_status.to_json (M.reference_feature_statuses reference)))
  | "prepare-reference-construct" ->
      exact ["manifest";"selection";"composition";"registry";"molecule_id";"source_request_fingerprint"];
      let manifest = manifest () in
      let selection = frontend "selection" A.Selection.of_json (get "selection") in
      let composition = frontend "composition" Composition.of_json (get "composition") in
      let registry = registry () in
      let molecule_id = Json.string (get "molecule_id") in
      let source_request_fingerprint = optional_string (get "source_request_fingerprint") in
      P.prepare ~manifest ~selection ~composition ~registry ~molecule_id ?source_request_fingerprint () |> construct_request
  | "generate-construct" ->
      exact ["request"];
      P.generate (request ()) |> construct_candidate
  | "emit-reference-sequence" ->
      exact ["request";"construct";"registry";"manifests"];
      let request = request () in let construct = construct () in
      let registry = registry () in let manifests = all_manifests () in
      E.emit ~request ~construct ~registry ~manifests () |> molecular_artifact
  | "check-construct-request" ->
      exact ["request";"registry";"manifests"];
      let request = request () in let registry = registry () in let manifests = all_manifests () in
      bare (Json.Array (CC.check_request ~request ~registry ~manifests () |> List.map CE.Diagnostic.to_json))
  | "check-construct" ->
      exact ["request";"candidate";"registry";"manifests"];
      let request = request () in let candidate = candidate () in
      let registry = registry () in let manifests = all_manifests () in
      CC.check ~request ~candidate ~registry ~manifests () |> construct_result
  | "check-molecular" ->
      exact ["request";"construct";"candidate";"registry";"manifests"];
      let request = request () in let construct = construct () in
      let candidate = frontend "candidate" M.Artifact.of_json (get "candidate") in
      let registry = registry () in let manifests = all_manifests () in
      MC.check ~request ~construct ~candidate ~registry ~manifests () |> molecular_result
  | _ -> failwith ("Unimplemented reference corpus operation: " ^ operation)

type execution = Returned of actual | Rejected of Diagnostic.t
let observe operation inputs =
  try Returned (execute operation inputs) with Diagnostic.Error error -> Rejected error

let run path =
  require (not (Filename.is_relative path)) "Absolute reference corpus path required";
  let raw = read_raw ~maximum:Limits.max_request_bytes path in
  require (Canonical.sha256 raw = physical_pin) "Reference corpus complete physical source differs";
  let index = Json.parse_artifact ~max_bytes:Limits.max_request_bytes ~max_nodes:1_000_000 raw in
  require (Canonical.encode_bounded ~max_bytes:Limits.max_request_bytes index ^ "\n" = raw)
    "Reference index canonical bytes differ";
  Json.exact_fields ["schema_version";"authority";"scope";"source_files";"test_modules";"test_ids";
    "test_outcomes";"operations";"operation_counts";"observations";"documents";"inventory_fingerprint"]
    (Json.object_fields index);
  require (text "schema_version" index = "biocompiler.reference_contract_conformance.v1") "Wrong reference corpus schema";
  require (text "authority" index = "unchanged_original_python_functions_and_test_bodies;native_outputs_never_expected")
    "Original reference authority changed";
  require (text "scope" index = "reference_domain_and_pure_producer_checker_foundation;no_retained_manager_or_archive_acceptance")
    "Reference foundation scope widened";
  require (text "inventory_fingerprint" index = pin &&
    Canonical.fingerprint (obj (List.remove_assoc "inventory_fingerprint" (Json.object_fields index))) = pin)
    "Reference complete inventory differs";
  let root = Filename.dirname (Filename.dirname (Filename.dirname path)) in
  let sources = Json.object_fields (field "source_files" index) in
  require (List.length sources = source_count) "Reference original source census differs";
  List.iter (fun (name,expected) ->
    require (Filename.is_relative name && not (List.mem ".." (String.split_on_char '/' name))) "Unsafe reference source path";
    let raw = read_raw ~maximum:Limits.max_request_bytes (Filename.concat root name) in
    let expected=hash(Json.string expected) in
    let original=if Canonical.sha256 raw=expected then raw else reference_original root name expected raw in
    require (Canonical.sha256 original = expected) ("Original reference source changed: " ^ name)) sources;
  let test_ids = array "test_ids" index |> List.map Json.string in
  require (List.length test_ids = method_count && List.length (List.sort_uniq String.compare test_ids) = method_count &&
    Canonical.fingerprint (field "test_ids" index) = test_ids_pin) "Incomplete original reference method census";
  equal "Original reference test outcomes" (field "test_outcomes" index)
    (Json.Array (List.map (fun id -> obj ["id",str id;"status",str "pass"]) test_ids));
  equal "Original reference modules" (field "test_modules" index) (Json.Array (List.map str
    ["test_references";"test_component_adapters";"test_construct_ir";"test_construct_assembly";
     "test_construct_audit";"test_construct_checker";"test_molecular_ir";"test_molecular_checker"]));
  let descriptors = Json.object_fields (field "documents" index) in
  require (List.length descriptors = document_count) "Incomplete reference document inventory";
  let docs = Hashtbl.create document_count and used = Hashtbl.create document_count in
  let directory = Filename.remove_extension path and total = ref 0 in
  List.iter (fun (id,descriptor) ->
    let id = hash id in
    require (not (Hashtbl.mem docs id)) "Duplicate reference document";
    Json.exact_fields ["path";"bytes"] (Json.object_fields descriptor);
    require (text "path" descriptor = "tests/conformance/reference-contracts-v1/" ^ id ^ ".json")
      "Reference document path differs";
    let value,bytes = read_document (Filename.concat directory (id ^ ".json")) in
    require (bytes = integer (field "bytes" descriptor) && bytes <= document_bytes - !total)
      "Reference complete byte inventory differs";
    require (Canonical.fingerprint value = id) "Reference content-addressed identity differs";
    total := !total + bytes; Hashtbl.add docs id value) descriptors;
  require (!total = document_bytes) "Reference document total bytes differ";
  require ((Array.to_list (Sys.readdir directory) |> List.sort String.compare) =
    (List.map (fun (id,_) -> id ^ ".json") descriptors |> List.sort String.compare))
    "Missing or extra reference documents";
  let use id =
    let id = hash id in Hashtbl.replace used id ();
    match Hashtbl.find_opt docs id with Some value -> value | None -> failwith "Missing complete reference document" in
  let rows = array "observations" index in
  require (List.length rows = observation_count) "Reference observation census differs";
  let ids = Hashtbl.create observation_count and ordinals = Hashtbl.create 3000 and counts = Hashtbl.create 50 in
  let returned = ref 0 and rejected = ref 0 and failed = ref 0 in
  let increment table key =
    let before = Option.value ~default:0 (Hashtbl.find_opt table key) in
    Hashtbl.replace table key (before+1); before in
  List.iter (fun row ->
    Json.exact_fields ["id";"context";"operation";"inputs";"outcome"] (Json.object_fields row);
    let id = text "id" row and context = text "context" row and operation = text "operation" row in
    require (not (Hashtbl.mem ids id)) "Duplicate reference observation";
    Hashtbl.add ids id ();
    let ordinal = increment ordinals (context,operation) in
    require (id = context ^ "/" ^ operation ^ "/" ^ string_of_int ordinal) "Reference observation ordering differs";
    ignore (increment counts operation);
    let inputs = obj (Json.object_fields (field "inputs" row) |> List.map (fun (key,id) -> key,use (Json.string id))) in
    (* Invoke actual production before retrieving any expected outcome value. *)
    let execution = try Ok (observe operation inputs) with error -> Error error in
    let expected = field "outcome" row in
    let expected_return = text "status" expected = "return" in
    if expected_return then incr returned else (
      require (text "status" expected = "raise") "Unknown original outcome"; incr rejected);
    let expected_value = if expected_return then Some (use (text "value" expected)) else None in
    let expected_json = match List.assoc_opt "json" (Json.object_fields expected) with
      None -> None | Some id -> Some (Json.string (use (Json.string id))) in
    let check () =
      match execution with
      | Error (Frontend_failure (slot,error)) -> failwith
          ("Typed supplied authority rejected before original function: " ^ slot ^ ": " ^ error.code ^ ": " ^ error.message)
      | Error error -> raise error
      | Ok (Rejected error) ->
          Json.exact_fields ["status";"module";"type";"message"] (Json.object_fields expected);
          require (not expected_return && text "module" expected = "biocompiler.errors" &&
            text "type" expected = "SerializationError") "Native rejection differs from original exception category";
          require (error.message = text "message" expected)
            ("Exact original exception differs: native " ^ error.code ^ ": " ^ error.message ^
              "; original " ^ text "message" expected)
      | Ok (Returned actual) ->
          let keys = ["status";"value"] @ (if Option.is_some actual.fingerprint then ["fingerprint"] else []) @
            (if Option.is_some actual.layout_fingerprint then ["layout_fingerprint"] else []) @
            (if Option.is_some actual.json then ["json"] else []) in
          Json.exact_fields keys (Json.object_fields expected);
          require expected_return "Native accepted an original rejection";
          (match expected_value with Some value -> equal "Reference actual return" actual.value value
           | None -> failwith "Missing complete expected return");
          Option.iter (fun value -> require (value = text "fingerprint" expected) "Original public fingerprint differs") actual.fingerprint;
          Option.iter (fun value -> require (value = text "layout_fingerprint" expected) "Original public layout fingerprint differs") actual.layout_fingerprint;
          require (actual.json = expected_json) "Complete original public JSON string differs" in
    (try check () with error ->
      incr failed;
      let detail = match error with Diagnostic.Error error -> error.code ^ ": " ^ error.message
        | _ -> Printexc.to_string error in
      Printf.eprintf "reference corpus failure %s: %s\n%!" id detail)) rows;
  require (!returned = 18_292 && !rejected = 4_292 && Hashtbl.length ids = observation_count)
    "Complete original reference outcome census differs";
  let expected_counts = Json.object_fields (field "operation_counts" index) in
  require (List.length expected_counts = 43 && Hashtbl.length counts = 43) "Reference operation family census differs";
  List.iter (fun (operation,count) -> require (Hashtbl.find_opt counts operation = Some (integer count))
    ("Reference operation count differs: " ^ operation)) expected_counts;
  equal "Reference operation names" (field "operations" index)
    (Json.Array (List.map (fun (key,_) -> str key) (List.sort (fun (left,_) (right,_) -> String.compare left right) expected_counts)));
  require (Hashtbl.length used = document_count) "Unclaimed complete reference authority/expectation document";
  require (!failed = 0) (Printf.sprintf "%d of %d complete reference observations failed" !failed observation_count);
  Printf.printf "reference contracts: all 72 original methods / 22584 complete domain, producer and checker observations passed; no manager/archive acceptance claim\n%!"

let () =
  require (Array.length Sys.argv = 2) "Expected one absolute reference-contract corpus path";
  run Sys.argv.(1)
