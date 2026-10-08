open Bioc_wire
module B=Bioc_artifact.Archive_budget
module Codec=Bioc_domain.Verification_exploration.Codec
module R=Bioc_domain.Reference_construct
let require condition message=Diagnostic.require condition "reference_package_manifest" message
let get key raw=Json.field key(Json.object_fields raw)
let str value=Json.String value
let obj values=Json.Object values
let required_files=["request.json","request";"inputs/registry.json","registry";
  "stages/components.json","components-stage";"stages/construct.json","construct-stage";
  "stages/molecular.json","molecular-stage";"molecular.json","molecular-specification";
  "sequence.fasta","sequence";"result.json","build-summary";"checks/construct.json","construct-check";
  "checks/molecular.json","molecular-check";"checks/composition.json","composition-check"]
let codec budget=let limits=B.limits budget in
  Codec.make_limits ~max_bytes:(min limits.max_member_bytes Limits.max_request_bytes)
    ~max_nodes:(min limits.max_json_nodes Limits.max_json_nodes) ~charge:(B.charge budget)()
let preflight budget raw=
  let size=Codec.measure ~limits:(codec budget) raw in
  (* Closed record imports retain normalized records and their cached JSON.
     Prepay before any decoder, list sorting, or canonical string allocation. *)
  let rec depth at value=
    B.charge budget 1;Diagnostic.require(at<=(B.limits budget).max_json_depth)
      "reference_package_depth_limit" "Reference package JSON exceeds its depth bound.";
    match value with Json.Array values->List.iter(depth(at+1))values
    |Json.Object values->List.iter(fun(_,v)->depth(at+1)v)values|_->() in
  depth 0 raw;
  B.product budget(size.bytes+size.nodes+1)128;
  B.reserve budget(128*size.bytes+512*size.nodes+8192)
let fields label expected raw=
  require(match raw with Json.Object pairs->List.length pairs=List.length expected &&
    List.for_all(fun key->List.mem_assoc key pairs)expected|_->false)("Invalid fields in "^label^".")
let schema label version raw=require(get "schema_version" raw=str version)("Unsupported "^label^" schema.")
let unicode label value=try Json.validate_utf8 value with Diagnostic.Error error when error.code="invalid_utf8"->
  Diagnostic.fail "reference_package_manifest"(label^" must contain valid UTF-8 Unicode.")
let whitespace n=(n>=9 && n<=13)||(n>=28 && n<=32)||(n>=0x2000 && n<=0x200a)||
  List.mem n[0x85;0xa0;0x1680;0x2028;0x2029;0x202f;0x205f;0x3000]
let plain budget label raw=
  B.charge budget 1;
  let named=match raw with Json.String value->
    let rec loop at=if at>=String.length value then false else
      let decoded=String.get_utf_8_uchar value at in
      not(whitespace(Uchar.to_int(Uchar.utf_decode_uchar decoded)))||loop(at+Uchar.utf_decode_length decoded) in loop 0
    |_->false in
  require named(label^" must be a nonempty string.");let value=Json.string raw in
  B.charge budget(String.length value+1);unicode label value;
  require(not(String.exists(fun c->Char.code c<32||Char.code c=127)value))(label^" cannot contain control characters.");value
let logical budget label raw=
  let value=plain budget label raw in
  require(not(String.contains value '\\') && not(String.contains value ':') && value.[0]<>'/' &&
    (let start=ref 0 and valid=ref true in
     let part stop=let n=stop- !start in if n=0 || (n=1 && value.[!start]='.') ||
       (n=2 && value.[!start]='.' && value.[!start+1]='.') then valid:=false in
     String.iteri(fun at c->if c='/' then(part at;start:=at+1))value;part(String.length value);!valid))
    (label^" must be a canonical relative POSIX path without traversal.");value
let validate_package_path budget ?(allow_reserved=false) raw=
  let value=logical budget "Package path" raw in
  require(allow_reserved || (value<>"manifest.json" && value<>"run.json"))
    "Manifest and run metadata are not package inventory files.";value
let hash label raw=
  require(match raw with Json.String value->String.length value=64 &&
    String.for_all(function '0'..'9'|'a'..'f'->true|_->false)value|_->false)(label^" must be a SHA-256 fingerprint.");Json.string raw
let array raw=require(match raw with Json.Array _->true|_->false)"Manifest records must be arrays.";Json.array raw
let mapped budget encode values=
  let maximum=(B.limits budget).max_json_nodes in
  let rec loop count reverse=function []->B.reserve budget(32*count);List.rev reverse
    |value::tail->B.charge budget 1;Diagnostic.require(count<maximum)"reference_package_collection_limit"
      "Reference package collection exceeds its node bound.";
      B.reserve budget 64;let value=encode value in loop(count+1)(value::reverse)tail in
  loop 0 [] values
let array_json budget encode values=Json.Array(mapped budget encode values)
let string_equal budget left right=B.charge budget(String.length left+String.length right+1);left=right
let member budget key values=List.exists(fun value->string_equal budget key value)values
let unique budget message values=
  ignore(List.fold_left(fun seen value->require(not(member budget value seen))message;value::seen)[]values)
let sort budget key values=
  let n=List.length values in let bytes=List.fold_left(fun sum value->sum+String.length(key value))0 values in
  let rec levels n result=if n<=1 then result else levels(n/2)(result+1) in
  B.product budget(n+bytes+1)(4*levels n 1);B.reserve budget(128*n+128);
  List.sort(fun a b->String.compare(key a)(key b))values
let parse_text budget text=
  let limits=B.limits budget in
  Diagnostic.require(String.length text<=limits.max_member_bytes)"reference_package_text_limit" "Reference package JSON exceeds its byte bound.";
  B.product budget(String.length text+1)32;B.reserve budget(64*String.length text+128);
  Legacy_json.parse ~on_node:(fun()->B.charge budget 1) ~max_bytes:limits.max_member_bytes
    ~max_nodes:(min limits.max_json_nodes Limits.max_json_nodes) ~profile:Legacy_json.Artifact text
let rec portable budget raw=
  B.charge budget 1;
  match raw with
  |Json.Object values->
    if List.length values=3 && List.for_all(fun key->List.mem_assoc key values)["file";"line";"function"] then
      ignore(logical budget "Logical source location"(List.assoc "file" values));
    List.iter(fun(key,value)->B.charge budget(String.length key+1);unicode "Reference request key" key;portable budget value)values
  |Json.Array values->List.iter(portable budget)values
  |Json.String value->B.charge budget(String.length value+1);unicode "Reference request text" value
  |_->()
type packed={json:Json.t;identity:string;bytes:int}
let pack budget json=
  let limits=codec budget in let size=Codec.measure ~limits json in
  B.reserve budget(size.bytes+128);let encoded=Codec.encode ~limits json in
  B.charge budget(String.length encoded+1);{json;identity=Canonical.sha256 encoded;bytes=String.length encoded}
let utc budget profile value=
  B.reserve budget(32*String.length value+128);
  let reverse=ref [] in let rec scan at=if at<String.length value then
    let unit=String.get_utf_8_uchar value at in reverse:=Uchar.to_int(Uchar.utf_decode_uchar unit)::!reverse;
    scan(at+Uchar.utf_decode_length unit) in scan 0;
  let values=Array.of_list(List.rev !reverse) in let size=Array.length values in
  let ascii at char=values.(at)=Char.code char in
  let digit at=Manifest_unicode.decimal profile values.(at) in
  let positions=[0;1;2;3;5;6;8;9;11;12;14;15;17;18] in
  let shape=size>=20 && size<=27 && ascii 4 '-' && ascii 7 '-' && ascii 10 'T' &&
    ascii 13 ':' && ascii 16 ':' && ascii(size-1)'Z' && List.for_all digit positions &&
    (size=20 || (size>=22 && ascii 19 '.' &&
      (let valid=ref true in for at=20 to size-2 do if not(digit at)then valid:=false done;!valid))) in
  require shape "Run timestamp must use an explicit UTC ISO-8601 Z representation.";
  require(Array.for_all(fun c->c<128)values)"Invalid UTC run timestamp.";
  let number at width=let n=ref 0 in for i=at to at+width-1 do n:=10* !n+values.(i)-48 done;!n in
  let year=number 0 4 and month=number 5 2 and day=number 8 2 in
  let leap=year mod 4=0 && (year mod 100<>0 || year mod 400=0) in
  let max_day=match month with 2->if leap then 29 else 28|4|6|9|11->30|_->31 in
  let hour=number 11 2 and minute=number 14 2 and second=number 17 2 in
  let fraction_zero=let okay=ref true in for i=20 to size-2 do if values.(i)<>48 then okay:=false done;!okay in
  let midnight=profile=Bioc_artifact.Stored_zip.Python314 && hour=24 && minute=0 && second=0 && fraction_zero &&
    not(year=9999 && month=12 && day=31) in
  require(year>=1 && month>=1 && month<=12 && day>=1 && day<=max_day &&
    (hour<24 || midnight) && minute<60 && second<60)"Invalid UTC run timestamp."
let absolute budget profile value=
  if value.[0]='/' then true else begin
    B.reserve budget(4*String.length value+128);
    let path=String.map(fun c->if c='\\' then '/' else c)value in
    let n=String.length path in
    match profile with
    |Bioc_artifact.Stored_zip.Python314->
      (* ntpath.isabs indexes Unicode characters, not UTF-8 bytes: 3.14 accepts
         any single scalar drive followed by colon+separator. 3.11 below still
         restricts its drive letter to ASCII, matching that older parser. *)
      let first=Uchar.utf_decode_length(String.get_utf_8_uchar path 0) in
      (n>=first+2 && path.[first]=':' && path.[first+1]='/') || String.starts_with ~prefix:"//" path
    |Bioc_artifact.Stored_zip.Python311->
      let prefix,path=if String.starts_with ~prefix:"//?/" path then
        let rest=String.sub path 4(n-4) in
        true,(if String.starts_with ~prefix:"UNC/" rest then "/"^String.sub rest 3(String.length rest-3)else rest)
        else false,path in
      let n=String.length path in
      let at index char=index<n && path.[index]=char in
      let unc=if at 0 '/' && at 1 '/' && not(at 2 '/') then
        match String.index_from_opt path 2 '/' with
        |None->false|Some first->(match String.index_from_opt path(first+1)'/' with
          |None->true|Some second->second<>first+1)
        else false in
      let drive=n>=2 && at 1 ':' && ((path.[0]>='a'&&path.[0]<='z')||(path.[0]>='A'&&path.[0]<='Z')) in
      unc || ((prefix || drive) && (if drive then at 2 '/' else at 0 '/'))
  end
module Request=struct
  type t={packed:packed;construct:R.Request.t;fasta_line_width:int}
  let schema_version="biocompiler.reference_build_request.v0.1"
  let of_json budget raw=
    preflight budget raw;fields "ReferenceBuildRequest" ["schema_version";"construct";"profile";"artifact_scope";"fasta_line_width"]raw;
    schema "ReferenceBuildRequest" schema_version raw;
    let construct=R.Request.of_json ~limits:(codec budget)(get "construct" raw) in
    require(get "profile" raw=str "reference_cds")"Unsupported reference build profile.";
    require(get "artifact_scope" raw=str "exact_cds")"Unsupported reference build scope.";
    let width=get "fasta_line_width" raw in
    require(match width with Json.Int n->Z.compare n Z.one>=0 && Z.compare n(Z.of_int 10000)<=0|_->false)
      "FASTA line width must be an integer from 1 to 10000.";
    let fasta_line_width=Z.to_int(Json.integer width) in
    portable budget(R.Request.to_json construct);
    let packed=pack budget(obj["schema_version",str schema_version;"construct",R.Request.to_json construct;
      "profile",str "reference_cds";"artifact_scope",str "exact_cds";"fasta_line_width",Json.int fasta_line_width]) in
    {packed;construct;fasta_line_width}
  let of_json_text budget text=of_json budget(parse_text budget text)
  let make budget ~construct ?(fasta_line_width=80) ()=B.reserve budget 512;of_json budget(obj["schema_version",str schema_version;
    "construct",R.Request.to_json construct;"profile",str "reference_cds";"artifact_scope",str "exact_cds";"fasta_line_width",Json.int fasta_line_width])
  let to_json (v:t)=v.packed.json
  let fingerprint (v:t)=v.packed.identity
  let canonical_size (v:t)=v.packed.bytes
  let construct (v:t)=v.construct
  let fasta_line_width (v:t)=v.fasta_line_width
end
module Run_metadata=struct
  type t={packed:packed;timestamp_utc:string;machine_label:string;locations:(string*string)list}
  let schema_version="biocompiler.run_metadata.v0.1"
  let of_json ?(runtime=Bioc_artifact.Stored_zip.Python314) budget raw=
    preflight budget raw;fields "RunMetadata" ["schema_version";"timestamp_utc";"machine_label";"locations"]raw;
    schema "RunMetadata" schema_version raw;
    let timestamp_utc=plain budget "Run timestamp"(get "timestamp_utc" raw) in utc budget runtime timestamp_utc;
    let machine_label=plain budget "Machine label"(get "machine_label" raw) in
    let raw_locations=get "locations" raw in
    require(match raw_locations with Json.Object _->true|_->false)"Run locations must be a mapping.";
    let locations=List.map(fun(key,value)->
      let key=logical budget "Logical source location"(str key) in
      let value=plain budget "Run source location" value in
      require(absolute budget runtime value)"Run locations must contain explicit absolute host paths.";key,value)(Json.object_fields raw_locations) in
    let packed=pack budget(obj["schema_version",str schema_version;"timestamp_utc",str timestamp_utc;
      "machine_label",str machine_label;"locations",obj(mapped budget(fun(key,value)->key,str value)locations)]) in
    {packed;timestamp_utc;machine_label;locations}
  let of_json_text ?runtime budget text=of_json ?runtime budget(parse_text budget text)
  let make ?runtime budget ~timestamp_utc ~machine_label ?(locations=[]) ()=
    B.reserve budget 512;of_json ?runtime budget(obj["schema_version",str schema_version;"timestamp_utc",str timestamp_utc;
      "machine_label",str machine_label;"locations",obj(mapped budget(fun(key,value)->key,str value)locations)])
  let to_json (v:t)=v.packed.json
  let fingerprint (v:t)=v.packed.identity
  let canonical_size (v:t)=v.packed.bytes
  let timestamp_utc (v:t)=v.timestamp_utc
  let machine_label (v:t)=v.machine_label
  let locations (v:t)=v.locations
end
module File=struct
  type t={packed:packed;path:string;role:string;sha256:string;byte_length:Z.t}
  let schema_version="biocompiler.package_file.v0.1"
  let of_json budget raw=
    preflight budget raw;fields "PackageFile" ["schema_version";"path";"role";"sha256";"byte_length"]raw;
    schema "PackageFile" schema_version raw;
    let path=validate_package_path budget(get "path" raw) in
    let role=plain budget "Package file role"(get "role" raw) in
    let sha256=hash "Package file content"(get "sha256" raw) in
    let length=get "byte_length" raw in
    require(match length with Json.Int n->Z.sign n>=0|_->false)"Invalid package file byte length.";
    let byte_length=Json.integer length in
    if role="reference-input" then begin
      let parts=String.split_on_char '/' path in
      require(List.length parts>=3 && List.hd parts="references")
        "Reference inputs must be under references/<reference-set>/<file>."
    end else require(List.assoc_opt path required_files=Some role)
      "Package file path/role is not part of the reference-build profile.";
    let packed=pack budget(obj["schema_version",str schema_version;"path",str path;"role",str role;
      "sha256",str sha256;"byte_length",Json.Int byte_length]) in {packed;path;role;sha256;byte_length}
  let of_json_text budget text=of_json budget(parse_text budget text)
  let make budget ~path ~role ~sha256 ~byte_length ()=B.reserve budget 512;of_json budget(obj["schema_version",str schema_version;
    "path",str path;"role",str role;"sha256",str sha256;"byte_length",Json.Int byte_length])
  let to_json (v:t)=v.packed.json
  let fingerprint (v:t)=v.packed.identity
  let canonical_size (v:t)=v.packed.bytes
  let path (v:t)=v.path
  let role (v:t)=v.role
  let sha256 (v:t)=v.sha256
  let byte_length (v:t)=v.byte_length
end
module Accepted_stage=struct
  type stage=Components|Construct|Molecular
  type t={packed:packed;stage:stage;artifact_fingerprint:string;record_fingerprint:string;artifact_schema:string}
  let schema_version="biocompiler.accepted_stage.v0.1"
  let name=function Components->"components"|Construct->"construct"|Molecular->"molecular"
  let of_json budget raw=
    preflight budget raw;fields "AcceptedStage" ["schema_version";"stage";"artifact_fingerprint";"record_fingerprint";"artifact_schema"]raw;
    schema "AcceptedStage" schema_version raw;
    let stage=match get "stage" raw with Json.String "components"->Components|Json.String "construct"->Construct|Json.String "molecular"->Molecular
      |_->Diagnostic.fail "reference_package_manifest" "Invalid accepted stage." in
    let artifact_fingerprint=hash "Stage payload"(get "artifact_fingerprint" raw) in
    let record_fingerprint=hash "Stage record"(get "record_fingerprint" raw) in
    let artifact_schema=plain budget "Stage payload schema"(get "artifact_schema" raw) in
    require(artifact_schema=(match stage with Components->"biocompiler.construct_request.v0.1"|
      Construct->"biocompiler.construct.v0.1"|Molecular->"biocompiler.molecular.v0.2"))
      "Stage payload schema does not match the reference-build profile.";
    let packed=pack budget(obj["schema_version",str schema_version;"stage",str(name stage);
      "artifact_fingerprint",str artifact_fingerprint;"record_fingerprint",str record_fingerprint;"artifact_schema",str artifact_schema]) in
    {packed;stage;artifact_fingerprint;record_fingerprint;artifact_schema}
  let of_json_text budget text=of_json budget(parse_text budget text)
  let make budget ~stage ~artifact_fingerprint ~record_fingerprint ~artifact_schema ()=
    B.reserve budget 512;of_json budget(obj["schema_version",str schema_version;"stage",str(name stage);
      "artifact_fingerprint",str artifact_fingerprint;"record_fingerprint",str record_fingerprint;"artifact_schema",str artifact_schema])
  let to_json (v:t)=v.packed.json
  let fingerprint (v:t)=v.packed.identity
  let canonical_size (v:t)=v.packed.bytes
  let stage (v:t)=v.stage
  let artifact_fingerprint (v:t)=v.artifact_fingerprint
  let record_fingerprint (v:t)=v.record_fingerprint
  let artifact_schema (v:t)=v.artifact_schema
end
module Tool=struct
  type t={packed:packed;id:string;version:string;content_fingerprint:string}
  let schema_version="biocompiler.tool_pin.v0.1"
  let of_json budget raw=
    preflight budget raw;fields "ToolPin" ["schema_version";"id";"version";"content_fingerprint"]raw;
    schema "ToolPin" schema_version raw;
    let id=plain budget "Tool ID"(get "id" raw) in
    let version=plain budget "Tool version"(get "version" raw) in
    let content_fingerprint=hash "Tool content"(get "content_fingerprint" raw) in
    let packed=pack budget(obj["schema_version",str schema_version;"id",str id;"version",str version;
      "content_fingerprint",str content_fingerprint]) in {packed;id;version;content_fingerprint}
  let of_json_text budget text=of_json budget(parse_text budget text)
  let make budget ~id ~version ~content_fingerprint ()=B.reserve budget 512;of_json budget(obj["schema_version",str schema_version;
    "id",str id;"version",str version;"content_fingerprint",str content_fingerprint])
  let to_json (v:t)=v.packed.json
  let fingerprint (v:t)=v.packed.identity
  let canonical_size (v:t)=v.packed.bytes
  let id (v:t)=v.id
  let version (v:t)=v.version
  let content_fingerprint (v:t)=v.content_fingerprint
end
module Manifest=struct
  type t={packed:packed;request_fingerprint:string;files:File.t list;accepted_stages:Accepted_stage.t list;toolchain:Tool.t list;package_version:string}
  let schema_version="biocompiler.build_manifest.v0.2"
  let of_json budget raw=
    preflight budget raw;fields "BuildManifest" ["schema_version";"request_fingerprint";"files";"accepted_stages";"toolchain";
      "package_version";"profile";"status";"scope";"intended_use";"human_therapeutic_admission"]raw;
    schema "BuildManifest" schema_version raw;
    (* Python's dataclass argument decoders run before __post_init__. *)
    let files=List.map(File.of_json budget)(array(get "files" raw)) in
    let accepted_stages=List.map(Accepted_stage.of_json budget)(array(get "accepted_stages" raw)) in
    let toolchain=List.map(Tool.of_json budget)(array(get "toolchain" raw)) in
    require(get "intended_use" raw=str "software_test" && get "human_therapeutic_admission" raw=str "not_admitted")
      "Reference manifests are software-only; human therapeutic use is not admitted.";
    let request_fingerprint=hash "Reference build request"(get "request_fingerprint" raw) in
    let package_version=plain budget "Package version"(get "package_version" raw) in
    require(get "profile" raw=str "reference_cds" && get "status" raw=str "complete" && get "scope" raw=str "exact_cds")
      "Unsupported build manifest profile/status/scope.";
    let paths=List.map File.path files in unique budget "Duplicate package paths." paths;
    List.iter(fun path->String.iteri(fun at c->if c='/' then begin
      B.reserve budget(at+32);let prefix=String.sub path 0 at in
      require(not(member budget prefix paths))"Package file paths cannot overlap directory prefixes."
    end)path)paths;
    require(List.for_all(fun(path,role)->List.exists(fun file->string_equal budget path(File.path file) &&
      string_equal budget role(File.role file))files)required_files)"Reference build manifest is missing a required file role.";
    require(List.exists(fun file->File.role file="reference-input")files)"Reference build manifest requires offline reference inputs.";
    let files=sort budget File.path files in
    require(List.map Accepted_stage.stage accepted_stages=[Accepted_stage.Components;Accepted_stage.Construct;Accepted_stage.Molecular])
      "Accepted stages must be exactly components, construct, molecular in order.";
    require(toolchain<>[])"Build manifests must pin their toolchain.";
    unique budget "Duplicate tool IDs."(List.map Tool.id toolchain);
    let toolchain=sort budget Tool.id toolchain in
    let packed=pack budget(obj["schema_version",str schema_version;"request_fingerprint",str request_fingerprint;
      "files",array_json budget File.to_json files;"accepted_stages",array_json budget Accepted_stage.to_json accepted_stages;
      "toolchain",array_json budget Tool.to_json toolchain;"package_version",str package_version;"profile",str "reference_cds";
      "status",str "complete";"scope",str "exact_cds";"intended_use",str "software_test";"human_therapeutic_admission",str "not_admitted"]) in
    {packed;request_fingerprint;files;accepted_stages;toolchain;package_version}
  let of_json_text budget text=of_json budget(parse_text budget text)
  let make budget ~request_fingerprint ~files ~accepted_stages ~toolchain ~package_version ()=
    B.reserve budget 512;of_json budget(obj["schema_version",str schema_version;"request_fingerprint",str request_fingerprint;
      "files",array_json budget File.to_json files;"accepted_stages",array_json budget Accepted_stage.to_json accepted_stages;
      "toolchain",array_json budget Tool.to_json toolchain;"package_version",str package_version;"profile",str "reference_cds";
      "status",str "complete";"scope",str "exact_cds";"intended_use",str "software_test";"human_therapeutic_admission",str "not_admitted"])
  let to_json (v:t)=v.packed.json
  let fingerprint (v:t)=v.packed.identity
  let canonical_size (v:t)=v.packed.bytes
  let request_fingerprint (v:t)=v.request_fingerprint
  let files (v:t)=v.files
  let accepted_stages (v:t)=v.accepted_stages
  let toolchain (v:t)=v.toolchain
  let package_version (v:t)=v.package_version
end
