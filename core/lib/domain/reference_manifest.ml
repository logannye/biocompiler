open Bioc_wire
module Codec = Verification_exploration.Codec
let default_limits = Codec.make_limits ~max_bytes:Limits.max_request_bytes ~max_nodes:Limits.max_json_nodes ()
let schema_version = "biocompiler.reference.v0.1"
let normalization_version = "ascii-layout-whitespace-and-uppercase.v1"
let require ?path condition message = Diagnostic.require ?path condition "reference_manifest" message
let str value = Json.String value
let obj value = Json.Object value
let get key value = Json.field key (Json.object_fields value)
let text key value = Json.string (get key value)
let fields ?(label="reference manifest") path keys raw =
  require ~path (match raw with Json.Object pairs->List.length pairs=List.length keys && List.for_all (fun key->List.mem_assoc key pairs) keys|_->false) ("Invalid "^label^" fields.")
let is_named = function Json.String value ->
  let rec walk i=if i>=String.length value then false else
    let decoded=String.get_utf_8_uchar value i in let n=Uchar.to_int (Uchar.utf_decode_uchar decoded) in
    let whitespace=(n>=9 && n<=13)||(n>=28 && n<=32)||List.mem n [0x85;0xa0;0x1680;0x2028;0x2029;0x202f;0x205f;0x3000]||(n>=0x2000 && n<=0x200a) in
    not whitespace || walk (i+Uchar.utf_decode_length decoded) in walk 0
  | _->false
let names limits label raw =
  require (match raw with Json.Array values->List.for_all is_named values|_->false) ("Invalid "^label^".");
  let values=Json.array raw |> List.map Json.string in
  let seen=Hashtbl.create 16 in
  List.iter (fun value->Codec.charge limits (String.length value+1);
    require (not (Hashtbl.mem seen value)) ("Duplicate "^label^"."); Hashtbl.add seen value ()) values;
  values
let array limits encode values =
  let maximum=Z.to_int (Json.integer (get "max_nodes" (Codec.limits_json limits))) in
  let rec walk count reverse = function [] -> Json.Array (List.rev reverse)
    | value::rest -> Codec.charge limits 1; Diagnostic.require (count<maximum) "reference_manifest_limit" "Reference collection exceeds its bound.";
      walk (count+1) (encode value::reverse) rest in
  walk 0 [] values
let ascii limits raw =
  let size=Codec.measure ~limits raw in
  Codec.charge limits ((size.bytes+size.nodes+1)*32);
  let maximum=Z.to_int (Json.integer (get "max_bytes" (Codec.limits_json limits))) in
  let ascii_size=Legacy_ascii.measure raw in
  Diagnostic.require (ascii_size.bytes<=maximum) "reference_manifest_limit" "Reference identity exceeds its encoded byte bound.";
  Legacy_ascii.encode raw
let hash value = String.length value=64 && String.for_all (function '0'..'9'|'a'..'f'->true|_->false) value
let equal limits left right = ascii limits left=ascii limits right

type alphabet = DNA | RNA | Protein
let alphabet_name = function DNA->"DNA" | RNA->"RNA" | Protein->"protein"
let alphabet_of_json raw = match raw with Json.String "DNA"->DNA|Json.String "RNA"->RNA|Json.String "protein"->Protein|_->Diagnostic.fail "reference_manifest" "Unsupported sequence alphabet."
type status = Candidate | Blocked | Accepted
let status_name = function Candidate->"candidate"|Blocked->"blocked"|Accepted->"accepted"
let status_of_json raw = match raw with Json.String "candidate"->Candidate|Json.String "blocked"->Blocked|Json.String "accepted"->Accepted|_->Diagnostic.fail "reference_manifest" "Invalid reference status."
let whitespace = function ' '| '\t' | '\r' | '\n' | '\011' | '\012' -> true | _ -> false
let symbol alphabet c = String.contains (match alphabet with DNA->"ACGT"|RNA->"ACGU"|Protein->"ACDEFGHIKLMNPQRSTVWY*") c
let sequence_bound limits raw =
  ignore (Codec.measure ~limits (str raw)); Codec.charge limits (4*(String.length raw+1))
let normalize_sequence ?(limits=default_limits) raw alphabet =
  sequence_bound limits raw;
  require (raw<>"") "Missing raw sequence text.";
  require (String.for_all (fun c->Char.code c<128) raw) "Only ASCII sequence letters and layout whitespace are allowed.";
  let removed=ref 0 and uppercased=ref 0 in
  let buffer=Buffer.create (String.length raw) in
  String.iter (fun c-> if c>='a' && c<='z' then incr uppercased;
    if whitespace c then incr removed else Buffer.add_char buffer (Char.uppercase_ascii c)) raw;
  let sequence=Buffer.contents buffer in
  require (sequence<>"" && String.for_all (symbol alphabet) sequence)
    ("Invalid "^alphabet_name alphabet^" symbol in reference extraction; no correction applied.");
  sequence,obj ["policy",str normalization_version;"removed_ascii_whitespace",Json.int !removed;"uppercased_characters",Json.int !uppercased]
let translate_cds ?(limits=default_limits) sequence alphabet =
  sequence_bound limits sequence;
  require (alphabet=DNA || alphabet=RNA) "Translation requires DNA or RNA.";
  require (sequence<>"" && String.for_all (symbol alphabet) sequence) "Invalid translation alphabet.";
  require (String.length sequence mod 3=0) "CDS length is not divisible by three.";
  require (String.starts_with ~prefix:(if alphabet=DNA then "ATG" else "AUG") sequence) "CDS does not start with the required ATG/AUG.";
  let index = function 'T'|'U'->0|'C'->1|'A'->2|'G'->3|_->assert false in
  let codons="FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG" in
  let protein=String.init (String.length sequence/3) (fun i->codons.[16*index sequence.[3*i]+4*index sequence.[3*i+1]+index sequence.[3*i+2]]) in
  require (protein.[String.length protein-1]='*' &&
    (let okay=ref true in for i=0 to String.length protein-2 do if protein.[i]='*' then okay:=false done; !okay))
    "CDS requires exactly one terminal stop, with no internal stops.";
  protein


let normalize_sequence_json ?(limits=default_limits) ~raw_text ~alphabet () =
  Codec.preflight ~limits (Json.Array [raw_text;alphabet]);
  require (match raw_text with Json.String value->value<>""|_->false) "Missing raw sequence text.";
  let alphabet=alphabet_of_json alphabet in
  normalize_sequence ~limits (Json.string raw_text) alphabet
let translate_cds_json ?(limits=default_limits) ~sequence ~alphabet () =
  Codec.preflight ~limits (Json.Array [sequence;alphabet]);
  let alphabet=match alphabet with Json.String "DNA"->DNA|Json.String "RNA"->RNA|_->Diagnostic.fail "reference_manifest" "Translation requires DNA or RNA." in
  require (match sequence with Json.String value->value<>"" && String.for_all (symbol alphabet) value|_->false) "Invalid translation alphabet.";
  translate_cds ~limits (Json.string sequence) alphabet

let parse_text limits profile text =
  let bounds=Codec.limits_json limits in
  let max_bytes=Z.to_int (Json.integer (Json.field "max_bytes" (Json.object_fields bounds)))
  and max_nodes=Z.to_int (Json.integer (Json.field "max_nodes" (Json.object_fields bounds))) in
  Diagnostic.require (String.length text<=max_bytes) "reference_text_limit" "Reference JSON text exceeds its byte bound.";
  Codec.charge limits (16*String.length text+8*max_nodes);
  Legacy_json.parse ~max_bytes ~max_nodes ~profile text

module Record = struct
  type t = {json:Json.t;identity:string;bytes:int;alphabet:alphabet;length:int;
    linked:string list;unknown:string list;evidence:string list}
  let keys=["reference_id";"variant_id";"version";"alphabet";"artifact_class";"orientation";"source_id";"source_locator";"raw_sequence_text";"raw_text_sha256";"sequence";"sequence_sha256";"length";"normalization";"linked_reference_ids";"completeness";"unknown_features";"evidence_relationships"]
  let of_json ?(limits=default_limits) ?(path="") raw =
    Codec.preflight ~limits ~path raw; fields ~label:"reference record" path keys raw;
    List.iter (fun key->require (is_named (get key raw)) ("Invalid "^key^".")) ["reference_id";"variant_id";"version";"source_id";"source_locator"];
    let alphabet=alphabet_of_json (get "alphabet" raw) in
    require ~path (get "artifact_class" raw=str (match alphabet with DNA->"coding_dna"|RNA->"coding_rna"|Protein->"protein")) "Artifact class disagrees with declared alphabet.";
    require ~path (get "orientation" raw=str (if alphabet=Protein then "N-to-C" else "5prime-to-3prime")) "Unsupported reference orientation.";
    require (match get "raw_sequence_text" raw with Json.String value->value<>""|_->false) "Missing raw sequence text.";
    let source=text "raw_sequence_text" raw in
    let sequence,log=normalize_sequence ~limits source alphabet in
    require ~path (get "sequence" raw=str sequence) "Normalized sequence differs from raw extraction.";
    require ~path (get "raw_text_sha256" raw=str (Canonical.sha256 source)) "Raw text hash mismatch.";
    require ~path (get "sequence_sha256" raw=str (Canonical.sha256 sequence)) "Canonical sequence hash mismatch.";
    let length=String.length sequence in
    require ~path (get "length" raw=Json.int length) "Sequence length mismatch.";
    require ~path ((match get "normalization" raw with Json.Object _->true|_->false) && equal limits (get "normalization" raw) log) "Normalization log mismatch.";
    let linked=names limits "linked_reference_ids" (get "linked_reference_ids" raw) in
    let unknown=names limits "unknown_features" (get "unknown_features" raw) in
    let evidence=names limits "evidence_relationships" (get "evidence_relationships" raw) in
    require ~path (get "completeness" raw=str "CDS-reference-only") "Unsupported completeness claim.";
    require ~path (unknown<>[]) "CDS-only unknown features must remain explicit.";
    require ~path (List.mem "exact-experimental-material-identity-unresolved" evidence) "Reference must distinguish exact experimental material identity.";
    let json=obj (List.map (fun key->key,get key raw) keys) in
    let encoded=ascii limits json in {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;alphabet;length;linked;unknown;evidence}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~reference_id ~variant_id ~version ~alphabet ~artifact_class ~orientation ~source_id ~source_locator ~raw_sequence_text ~raw_text_sha256 ~sequence ~sequence_sha256 ~length ~normalization ~linked_reference_ids ~completeness ~unknown_features ~evidence_relationships () =
    of_json ~limits (obj ["reference_id",str reference_id;"variant_id",str variant_id;"version",str version;"alphabet",str (alphabet_name alphabet);"artifact_class",str artifact_class;"orientation",str orientation;"source_id",str source_id;"source_locator",str source_locator;"raw_sequence_text",str raw_sequence_text;"raw_text_sha256",str raw_text_sha256;"sequence",str sequence;"sequence_sha256",str sequence_sha256;"length",Json.int length;"normalization",normalization;"linked_reference_ids",array limits str linked_reference_ids;"completeness",str completeness;"unknown_features",array limits str unknown_features;"evidence_relationships",array limits str evidence_relationships])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let reference_id v=text "reference_id" v.json
  let variant_id v=text "variant_id" v.json
  let version v=text "version" v.json
  let alphabet (v:t)=v.alphabet
  let artifact_class v=text "artifact_class" v.json
  let orientation v=text "orientation" v.json
  let source_id v=text "source_id" v.json
  let source_locator v=text "source_locator" v.json
  let raw_sequence_text v=text "raw_sequence_text" v.json
  let raw_text_sha256 v=text "raw_text_sha256" v.json
  let sequence v=text "sequence" v.json
  let sequence_sha256 v=text "sequence_sha256" v.json
  let length (v:t)=v.length
  let normalization v=get "normalization" v.json
  let linked_reference_ids (v:t)=v.linked
  let completeness v=text "completeness" v.json
  let unknown_features (v:t)=v.unknown
  let evidence_relationships (v:t)=v.evidence
end
let date label raw =
  let message="Invalid "^label^" date." in
  require (match raw with Json.String _->true|_->false) message;
  let value=Json.string raw in
  let digit i = value.[i]>='0' && value.[i]<='9' in
  require (String.length value=10 && value.[4]='-' && value.[7]='-' && List.for_all digit [0;1;2;3;5;6;8;9]) message;
  let year=int_of_string (String.sub value 0 4) and month=int_of_string (String.sub value 5 2) and day=int_of_string (String.sub value 8 2) in
  require (year>=1 && month>=1 && month<=12) message;
  let days=match month with 2->if year mod 4=0 && (year mod 100<>0 || year mod 400=0) then 29 else 28|4|6|9|11->30|_->31 in
  require (day>=1 && day<=days) message
let local_path ?(needs_name=false) raw =
  let value=match raw with Json.String value->value|_->"" in
  let parts=String.split_on_char '/' value |> List.filter (fun x->x<>"" && x<>".") in
  value<>"" && not (String.starts_with ~prefix:"/" value) && not (String.contains value '\\') && not (List.mem ".." parts) && (not needs_name || parts<>[])
module Manifest = struct
  type t={json:Json.t;identity:string;bytes:int;records:Record.t list;status:status;unresolved:string list}
  let discrepancies ?(limits=default_limits) (v:t) =
    let size=Codec.measure ~limits v.json in Codec.charge limits (8*(size.bytes+size.nodes+1));
    let find alphabet=List.find (fun r->Record.alphabet r=alphabet) v.records in
    let dna=find DNA and rna=find RNA and protein=find Protein in
    let result=ref v.unresolved in
    Codec.charge limits (2*(Record.length dna+Record.length rna+Record.length protein+1));
    if String.map (fun c->if c='T' then 'U' else c) (Record.sequence dna)<>Record.sequence rna then
      result:= !result@["DNA/RNA differ under the explicit T-to-U correspondence check."];
    List.iter (fun alphabet->try
      if translate_cds ~limits (Record.sequence (find alphabet)) alphabet<>Record.sequence protein then
        result:= !result@[alphabet_name alphabet^" translation differs from independently extracted protein."]
      with Diagnostic.Error error when error.code="reference_manifest" -> result:= !result@[alphabet_name alphabet^": "^error.message]) [DNA;RNA];
    !result
  let of_json ?(limits=default_limits) ?(path="") raw =
    Codec.preflight ~limits ~path raw;
    fields path ["schema_version";"reference_set_id";"version";"sources";"records";"translation";"reviews";"status";"unresolved_discrepancies";"redistribution"] raw;
    require (match get "records" raw with Json.Array _->true|_->false) "Reference records must be an array.";
    let records=Json.array (get "records" raw) |> List.map (Record.of_json ~limits ~path) in
    require ~path (get "schema_version" raw=str schema_version) "Unsupported reference schema version.";
    require (is_named (get "reference_set_id" raw) && is_named (get "version" raw)) "Invalid reference set identity.";
    let status=status_of_json (get "status" raw) in
    require ~path (match get "sources" raw with Json.Array (_::_)->true|_->false) "Missing source artifacts.";
    let sources=Json.array (get "sources" raw) in
    let ids=Hashtbl.create 16 in
    List.iter (fun source->fields ~label:"source artifact" path ["id";"url";"publication";"publication_version";"retrieved_on";"media_type";"sha256";"local_path"] source;
      require (List.for_all (fun key->is_named (get key source)) ["id";"url";"publication";"publication_version";"media_type"]) "Invalid source artifact identity.";
      require (String.starts_with ~prefix:"https://" (text "url" source) && (match get "sha256" source with Json.String value->hash value|_->false)) "Invalid source URL/hash.";
      date "retrieval" (get "retrieved_on" source);
      require (get "local_path" source=Json.Null || local_path (get "local_path" source)) "Source paths must stay within the reference directory.";
      let id=text "id" source in Codec.charge limits (String.length id+1);
      require (not (Hashtbl.mem ids id)) "Duplicate source artifact identity."; Hashtbl.add ids id ()) sources;
    require (List.length records=3 && List.for_all (fun a->List.length (List.filter (fun r->Record.alphabet r=a) records)=1) [DNA;RNA;Protein]) "A CDS reference set requires independently extracted DNA, RNA and protein.";
    let record_ids=List.map Record.reference_id records in
    Codec.charge limits (8*List.fold_left (fun n r->n+String.length (Record.reference_id r)+String.length (Record.variant_id r)) 1 records);
    require (List.length (List.sort_uniq String.compare record_ids)=3 && List.length (List.sort_uniq String.compare (List.map Record.variant_id records))=1) "Duplicate reference or inconsistent variant identity.";
    List.iter (fun r->require (Hashtbl.mem ids (Record.source_id r)) "Unknown record source.";
      require (List.sort String.compare (Record.linked_reference_ids r)=List.sort String.compare (List.filter ((<>) (Record.reference_id r)) record_ids)) "Reference links must name the other records in the set.") records;
    let translation=obj ["genetic_code",Json.int 1;"frame_zero_based",Json.int 0;"start_codon",str "ATG/AUG";"stop_convention",str "exactly-one-terminal-star-retained";"protein_length_includes_stop",Json.Bool true] in
    require (equal limits (get "translation" raw) translation) "Unsupported translation convention.";
    let unresolved=names limits "discrepancies" (get "unresolved_discrepancies" raw) in
    let redistribution=get "redistribution" raw in fields ~label:"redistribution" path ["attribution";"terms_url";"license_status";"note"] redistribution;
    require (List.for_all (fun (_,v)->is_named v) (Json.object_fields redistribution)) "Invalid redistribution record.";
    require (match get "reviews" raw with Json.Array _->true|_->false) "Invalid review evidence.";
    let reviews=Json.array (get "reviews" raw) and reviewers=Hashtbl.create 16 in
    let record_hashes=obj (List.map (fun r->Record.reference_id r,str (Record.fingerprint r)) records) in
    let source_hashes=obj (List.map (fun s->text "id" s,get "sha256" s) sources) in
    List.iter (fun review->fields ~label:"review evidence" path ["reviewer";"role";"reviewed_on";"method";"record_fingerprints";"source_hashes";"outcome";"evidence"] review;
      require (is_named (get "reviewer" review) && is_named (get "method" review)) "Invalid/duplicate reviewer identity.";
      let reviewer=Json.string (get "reviewer" review) in
      Codec.charge limits (String.length reviewer+1); require (not (Hashtbl.mem reviewers reviewer)) "Invalid/duplicate reviewer identity."; Hashtbl.add reviewers reviewer ();
      (match get "evidence" review with Json.Null->()|evidence->fields ~label:"review evidence artifact" path ["local_path";"sha256"] evidence; require (local_path ~needs_name:true (get "local_path" evidence) && (match get "sha256" evidence with Json.String value->hash value|_->false)) "Invalid review evidence path/hash.");
      require (List.mem (get "role" review) [str "extraction";str "independent-review"] && List.mem (get "outcome" review) [str "pass";str "blocked"]) "Invalid review role/outcome.";
      date "review" (get "reviewed_on" review);
      require (equal limits (get "record_fingerprints" review) record_hashes) "Review uses stale record identities.";
      require (equal limits (get "source_hashes" review) source_hashes) "Review uses stale source identities.") reviews;
    let json=obj ["schema_version",str schema_version;"reference_set_id",get "reference_set_id" raw;"version",get "version" raw;"sources",Json.Array sources;"records",array limits Record.to_json records;"translation",get "translation" raw;"reviews",Json.Array reviews;"status",str (status_name status);"unresolved_discrepancies",get "unresolved_discrepancies" raw;"redistribution",redistribution] in
    let provisional={json;identity="";bytes=0;records;status;unresolved} in
    let differences=discrepancies ~limits provisional in
    if status=Accepted then (
      require (differences=[]) "Inconsistent references cannot be accepted.";
      require (List.for_all (fun r->text "outcome" r="pass") reviews && List.for_all (fun role->List.exists (fun r->text "role" r=role) reviews) ["extraction";"independent-review"]) "Acceptance requires extraction and independent passing review.");
    require (differences=[] || status=Blocked) "Inconsistent reference set must remain blocked.";
    let encoded=ascii limits json in {provisional with identity=Canonical.sha256 encoded;bytes=String.length encoded}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Reference text)
  let make ?(limits=default_limits) ~reference_set_id ~version ~sources ~records ~translation ~reviews ~status ~unresolved_discrepancies ~redistribution () =
    of_json ~limits (obj ["schema_version",str schema_version;"reference_set_id",str reference_set_id;"version",str version;"sources",array limits Fun.id sources;"records",array limits Record.to_json records;"translation",translation;"reviews",array limits Fun.id reviews;"status",str (status_name status);"unresolved_discrepancies",array limits str unresolved_discrepancies;"redistribution",redistribution])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let reference_set_id (v:t)=text "reference_set_id" v.json
  let version (v:t)=text "version" v.json
  let sources (v:t)=Json.array (get "sources" v.json)
  let records (v:t)=v.records
  let translation (v:t)=get "translation" v.json
  let reviews (v:t)=Json.array (get "reviews" v.json)
  let status (v:t)=v.status
  let unresolved_discrepancies (v:t)=v.unresolved
  let redistribution (v:t)=get "redistribution" v.json
  let record ?(require_accepted=true) (v:t) id =
    require (not require_accepted || v.status=Accepted) ("Reference set is "^status_name v.status^"; promotion is required before build use.");
    match List.filter (fun r->Record.reference_id r=id) v.records with [value]->value|_->Diagnostic.fail "reference_manifest" ("Unknown reference record: "^id^".")
end
include Manifest
