open Bioc_wire
open Bioc_domain
module B=Bioc_artifact.Archive_budget
module P=Bioc_artifact.Utf8_pretty
module Q=Reference_molecular
module C=Verification_exploration.Codec
let export_version="biocompiler.sequence_export.v0.2"
let fasta_policy="single-reference-software-use-percent-encoded-id-uppercase-lf-terminal-newline.v2"
let json_policy="molecular-specification-software-use-sorted-keys-indent-2-utf8-lf-terminal-newline.v2"
let require condition message=Diagnostic.require condition "reference_sequence_export" message
let width n=require(n>=1 && n<=10000)"FASTA line width must be an integer from 1 to 10000."
let hash label value=require(String.length value=64 && String.for_all(function '0'..'9'|'a'..'f'->true|_->false)value)
  ("Invalid "^label^" fingerprint.")
let bounded_text budget value=
  B.charge budget(String.length value+1);
  Diagnostic.require(String.length value<=(B.limits budget).max_member_bytes)"reference_export_byte_limit"
    "Sequence export text exceeds its native member byte limit.";
  B.reserve budget(String.length value+64)
let codec budget=let limits=B.limits budget in C.make_limits
  ~max_bytes:(min Limits.max_request_bytes limits.max_member_bytes)
  ~max_nodes:(min Limits.max_json_nodes limits.max_json_nodes) ~charge:(B.charge budget)()
let depth budget raw=
  (* Called only after bounded Codec.measure has rejected cycles and oversized
     lists. This additional walk implements the caller's reduced depth cap. *)
  let rec walk level value=B.charge budget 1;
    Diagnostic.require(level<=(B.limits budget).max_json_depth)"reference_export_depth_limit"
      "Reference export JSON exceeds its depth limit.";
    match value with Json.Array values->List.iter(walk(level+1))values
    |Json.Object values->List.iter(fun(_,value)->walk(level+1)value)values|_->() in walk 0 raw
let artifact budget value=
  let size=C.measure ~limits:(codec budget)(Q.Artifact.to_json value) in
  depth budget(Q.Artifact.to_json value);
  B.reserve budget(128*size.bytes+512*size.nodes+8192)
type t={fasta:string;specification:string;line_width:int;sequence_sha256:string;molecular_fingerprint:string}
let make budget ~fasta ~specification ~line_width ~sequence_sha256 ~molecular_fingerprint ()=
  B.charge budget 1;width line_width;hash "canonical sequence" sequence_sha256;hash "molecular artifact" molecular_fingerprint;
  bounded_text budget fasta;bounded_text budget specification;B.reserve budget 128;
  {fasta;specification;line_width;sequence_sha256;molecular_fingerprint}
let line_width_of_json budget raw=
  B.charge budget 1;
  require(match raw with Json.Int n->Z.compare n Z.one>=0 && Z.compare n(Z.of_int 10000)<=0|_->false)
    "FASTA line width must be an integer from 1 to 10000.";
  Z.to_int(Json.integer raw)
let of_json budget raw=
  let size=C.measure ~limits:(codec budget) raw in
  depth budget raw;
  B.reserve budget(size.bytes+64*size.nodes+128);
  let shape=match raw with Json.Object fields->List.length fields=5 &&
    List.for_all(fun key->List.mem_assoc key fields)["fasta";"specification";"line_width";"sequence_sha256";"molecular_fingerprint"]|_->false in
  B.charge budget 1;require shape "Invalid sequence export fields.";
  let get key=Json.field key(Json.object_fields raw) in
  let text key message=match get key with Json.String value->value|_->Diagnostic.fail "reference_sequence_export" message in
  let fasta=text "fasta" "FASTA export must be text." in
  let specification=text "specification" "Molecular specification must be text." in
  let line_width=line_width_of_json budget(get "line_width") in
  let identity key label=let raw=get key in
    require(match raw with Json.String value->String.length value=64 &&
      String.for_all(function '0'..'9'|'a'..'f'->true|_->false)value|_->false)("Invalid "^label^" fingerprint.");Json.string raw in
  let sequence_sha256=identity "sequence_sha256" "canonical sequence" in
  let molecular_fingerprint=identity "molecular_fingerprint" "molecular artifact" in
  make budget ~fasta ~specification ~line_width ~sequence_sha256 ~molecular_fingerprint()
let safe=function 'a'..'z'|'A'..'Z'|'0'..'9'|'-'|'.'|'_'|'~'->true|_->false
let quoted budget value=
  B.product budget(String.length value+1)4;B.reserve budget(6*String.length value+128);
  let size=String.fold_left(fun total c->total+(if safe c then 1 else 3))0 value in
  Diagnostic.require(size<=(B.limits budget).max_member_bytes)"reference_export_byte_limit" "Encoded reference identity exceeds its byte limit.";
  let result=Bytes.create size and at=ref 0 and hex="0123456789ABCDEF" in
  String.iter(fun c->if safe c then(Bytes.set result !at c;incr at)else begin
    Bytes.set result !at '%';Bytes.set result(!at+1)hex.[Char.code c lsr 4];Bytes.set result(!at+2)hex.[Char.code c land 15];at:= !at+3 end)value;
  Bytes.unsafe_to_string result
let unquoted budget value=
  B.product budget(String.length value+1)4;B.reserve budget(2*String.length value+128);
  let result=Bytes.create(String.length value) and at=ref 0 in
  let hex=function '0'..'9' as c->Char.code c-48|'a'..'f' as c->Char.code c-87|'A'..'F' as c->Char.code c-55|_-> -1 in
  let rec loop index=if index<String.length value then
    if value.[index]='%' && index+2<String.length value && hex value.[index+1]>=0 && hex value.[index+2]>=0 then begin
      Bytes.set result !at(Char.chr(16*hex value.[index+1]+hex value.[index+2]));incr at;loop(index+3)
    end else begin Bytes.set result !at value.[index];incr at;loop(index+1)end in loop 0;
  let text=Bytes.sub_string result 0 !at in
  (try Json.validate_utf8 text with Diagnostic.Error error when error.code="invalid_utf8"->
    Diagnostic.fail "reference_sequence_export" "Invalid encoded FASTA reference identity.");text
let digest budget value=B.charge budget(String.length value+1);Canonical.sha256 value
let verify budget (bundle:t) candidate=
  B.charge budget 1;artifact budget candidate;bounded_text budget bundle.fasta;bounded_text budget bundle.specification;
  require(List.length(Q.Artifact.records candidate)=1)"Sequence export supports one CDS record.";
  require(bundle.molecular_fingerprint=Q.Artifact.fingerprint candidate)"Export identifies a different molecular artifact.";
  let record=List.hd(Q.Artifact.records candidate) and text=bundle.fasta in
  require(String.for_all(fun c->Char.code c<128)text && String.ends_with ~suffix:"\n" text && not(String.contains text '\r'))
    "FASTA requires ASCII symbols, LF newlines and one terminal newline.";
  B.reserve budget(64*(String.length text+1));let lines=String.split_on_char '\n' text in
  require(List.length lines>=3)"FASTA requires a header and sequence.";
  let header=List.hd lines in let reverse=List.rev(List.tl lines) in
  require(List.hd reverse="")"FASTA requires a header and sequence.";
  let sequence_lines=List.rev(List.tl reverse) in
  require(String.starts_with ~prefix:">" header)"FASTA is missing its record header.";
  let header=String.sub header 1(String.length header-1) in
  let tokens=String.split_on_char ' ' header in
  require(List.length tokens=5)"FASTA header must identify reference, alphabet, scope, software use and non-admission.";
  let reference_id=unquoted budget(List.hd tokens) in
  let expected=Pinned_identity.id(Reference_components.Selection.reference(Q.Record.reference_selection record)) in
  let alphabet=Reference_manifest.alphabet_name(Q.Record.alphabet record) in
  require(quoted budget reference_id=List.hd tokens && reference_id=expected && List.nth tokens 1="alphabet="^alphabet &&
    List.nth tokens 2="scope=CDS-reference-only" && List.nth tokens 3="use=software_test" && List.nth tokens 4="human_admission=not_admitted")
    "FASTA header changed reference identity, alphabet, scope or encoding.";
  let rec wrapping=function []->false|[last]->String.length last>0 && String.length last<=bundle.line_width|
    value::rest->String.length value=bundle.line_width && wrapping rest in
  require(wrapping sequence_lines)"FASTA wrapping differs from its declared line-width policy.";
  let symbols=if Q.Record.alphabet record=Reference_manifest.DNA then "ACGT"else "ACGU" in
  require(List.for_all(fun line->String.for_all(fun c->String.contains symbols c)line)sequence_lines)
    "FASTA contains invalid symbols or an additional record; no normalization is applied.";
  B.reserve budget(String.length text+64);let sequence=String.concat "" sequence_lines in
  let identity=digest budget sequence in
  require(sequence=Q.Record.sequence record && identity=Q.Record.sequence_sha256 record && identity=bundle.sequence_sha256)
    "FASTA canonical sequence differs from the molecular artifact.";
  B.reserve budget(128*String.length bundle.specification+8192);
  let decoded=Q.Artifact.of_json_text ~limits:(codec budget) bundle.specification in
  require(Q.Artifact.fingerprint decoded=Q.Artifact.fingerprint candidate)"Structured export changed molecular content or provenance.";
  let canonical=P.encode budget ~max_bytes:(B.limits budget).max_member_bytes(Q.Artifact.to_json candidate) in
  B.charge budget(String.length canonical+String.length bundle.specification+1);
  require(bundle.specification=canonical)"Structured export differs from the canonical JSON file policy.";true
let encode budget ~line_width candidate=
  B.charge budget 1;width line_width;artifact budget candidate;
  require(List.length(Q.Artifact.records candidate)=1)"Sequence export supports one CDS record.";
  let record=List.hd(Q.Artifact.records candidate) in
  let reference=Pinned_identity.id(Reference_components.Selection.reference(Q.Record.reference_selection record)) in
  let reference=quoted budget reference and alphabet=Reference_manifest.alphabet_name(Q.Record.alphabet record) in
  let sequence=Q.Record.sequence record in
  B.reserve budget(String.length reference+256);
  let header=">"^reference^" alphabet="^alphabet^" scope=CDS-reference-only use=software_test human_admission=not_admitted\n" in
  let lines=(String.length sequence+line_width-1)/line_width in
  let size=String.length header+String.length sequence+max 1 lines in
  Diagnostic.require(size<=(B.limits budget).max_member_bytes)"reference_export_byte_limit" "FASTA output exceeds its native member byte limit.";
  B.product budget(size+1)4;B.reserve budget(size+128);
  let output=Bytes.create size in Bytes.blit_string header 0 output 0(String.length header);
  let position=ref(String.length header) in
  for i=0 to lines-1 do let start=i*line_width in let length=min line_width(String.length sequence-start) in
    Bytes.blit_string sequence start output !position length;position:= !position+length;Bytes.set output !position '\n';incr position done;
  if lines=0 then(Bytes.set output !position '\n';incr position);
  require(!position=size)"FASTA output preflight differs.";
  let fasta=Bytes.unsafe_to_string output in
  let specification=P.encode budget ~max_bytes:(B.limits budget).max_member_bytes(Q.Artifact.to_json candidate) in
  let bundle=make budget ~fasta ~specification ~line_width ~sequence_sha256:(Q.Record.sequence_sha256 record)
    ~molecular_fingerprint:(Q.Artifact.fingerprint candidate)() in
  ignore(verify budget bundle candidate);bundle
let fasta (value:t)=value.fasta
let specification (value:t)=value.specification
let line_width (value:t)=value.line_width
let sequence_sha256 (value:t)=value.sequence_sha256
let molecular_fingerprint (value:t)=value.molecular_fingerprint
let fasta_sha256 budget (value:t)=digest budget value.fasta
let specification_sha256 budget (value:t)=digest budget value.specification
