open Bioc_wire
module Codec = Verification_exploration.Codec
module M = Reference_manifest
module P = Pinned_identity
let adapter_version="biocompiler.reference_component.v0.1"
let supported_reference_set="wo2022081694a1.murine-fapcar.cds"
let require ?path condition message=Diagnostic.require ?path condition "reference_components" message
let str x=Json.String x
let parse_text limits profile text =
  let bounds=Codec.limits_json limits in
  let max_bytes=Z.to_int (Json.integer (Json.field "max_bytes" (Json.object_fields bounds)))
  and max_nodes=Z.to_int (Json.integer (Json.field "max_nodes" (Json.object_fields bounds))) in
  Diagnostic.require (String.length text<=max_bytes) "reference_text_limit" "Reference JSON text exceeds its byte bound.";
  Codec.charge limits (16*String.length text+8*max_nodes);
  Legacy_json.parse ~max_bytes ~max_nodes ~profile text

module Selection = struct
  type t={json:Json.t;identity:string;bytes:int;manifest:P.t;reference:P.t}
  let schema_version="biocompiler.reference_selection.v0.1"
  let of_json ?(limits=M.default_limits) ?(path="") raw =
    let size=Codec.measure ~limits ~path raw in Codec.charge limits (8*(size.bytes+size.nodes+1));
    let shape label keys raw=require ~path (match raw with Json.Object fields->List.length fields=List.length keys && List.for_all (fun key->List.mem_assoc key fields) keys|_->false) ("Invalid fields in "^label^".") in
    shape "ReferenceSelection" ["schema_version";"manifest";"reference"] raw;
    let fields=Json.object_fields raw in
    require ~path (Json.field "schema_version" fields=str schema_version) "Unsupported reference selection schema.";
    let pin raw=shape "PinnedIdentity" ["schema_version";"kind";"id";"version";"content_fingerprint"] raw;raw in
    let manifest=P.of_json ~path:(path^"/manifest") (pin (Json.field "manifest" fields)) in
    let reference=P.of_json ~path:(path^"/reference") (pin (Json.field "reference" fields)) in
    require ~path (P.kind manifest=P.Reference && P.kind reference=P.Reference) "Reference selection requires explicit manifest and record identities.";
    let json=Json.Object ["schema_version",str schema_version;"manifest",P.to_json manifest;"reference",P.to_json reference] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded); {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;manifest;reference}
  let of_json_text ?(limits=M.default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=M.default_limits) ~manifest ~reference () = of_json ~limits (Json.Object ["schema_version",str schema_version;"manifest",P.to_json manifest;"reference",P.to_json reference])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let manifest (v:t)=v.manifest
  let reference (v:t)=v.reference
end
let adapt_reference_component ?(limits=M.default_limits) manifest selection =
  Codec.charge limits (64*(M.canonical_size manifest+Selection.canonical_size selection+1));
  require (M.reference_set_id manifest=supported_reference_set) "Unsupported reference set for the FAP adapter.";
  let pin=P.make ~kind:P.Reference ~id:(M.reference_set_id manifest) ~version:(M.version manifest) ~content_fingerprint:(M.fingerprint manifest) in
  require (P.fingerprint pin=P.fingerprint (Selection.manifest selection)) "Reference manifest identity/version/content lock mismatch.";
  let record=M.record manifest (P.id (Selection.reference selection)) in
  let record_pin r=P.make ~kind:P.Reference ~id:(M.Record.reference_id r) ~version:(M.Record.version r) ~content_fingerprint:(M.Record.fingerprint r) in
  require (P.fingerprint (record_pin record)=P.fingerprint (Selection.reference selection)) "Selected reference identity/version/content lock mismatch.";
  require (M.Record.alphabet record<>M.Protein) "The component adapter selects an exact nucleotide CDS, not a protein payload.";
  let get key raw=Json.field key (Json.object_fields raw) in
  let text key raw=Json.string (get key raw) in
  let identities=Selection.manifest selection::List.map record_pin (M.records manifest) @
    List.map (fun source->P.make ~kind:P.Source ~id:(text "id" source) ~version:(text "publication_version" source) ~content_fingerprint:(text "sha256" source)) (M.sources manifest) in
  let evidence=List.filter_map (fun review->match get "evidence" review with Json.Null->None|item->Some (P.make ~kind:P.Evidence ~id:("review:"^text "reviewer" review) ~version:(text "reviewed_on" review) ~content_fingerprint:(text "sha256" item))) (M.reviews manifest) in
  let assumptions=["Reference adapter policy: "^adapter_version;"Coding-sequence boundaries only; no complete delivered payload is specified.";"No molecular dynamic contract, empirical behavior or host capacity is established."] @
    List.map (fun x->"Unknown feature: "^x) (M.Record.unknown_features record) @ List.map (fun x->"Evidence relationship: "^x) (M.Record.evidence_relationships record) in
  let guarantees=["completeness:"^M.Record.completeness record;"artifact_class:"^M.Record.artifact_class record;"alphabet:"^M.alphabet_name (M.Record.alphabet record);"orientation:"^M.Record.orientation record;"sequence_length:"^string_of_int (M.Record.length record);"sequence_sha256:"^M.Record.sequence_sha256 record;"selected_reference:"^M.Record.reference_id record;"source_locator:"^M.Record.source_locator record;"source_id:"^M.Record.source_id record;"translation:frame-zero-standard-code-terminal-stop-retained"] in
  let artifact_class=match M.Record.alphabet record with M.DNA->Component.Sequence_reference.Coding_dna|M.RNA->Component.Sequence_reference.Coding_rna|M.Protein->Component.Sequence_reference.Protein in
  let result=Component.make ~id:("reference."^M.Record.reference_id record) ~version:(M.Record.version record)
    ~classification:Component.Sequence_reference ~implementation_role:"exact_cds_reference" ~supported_targets:[M.alphabet_name (M.Record.alphabet record)]
    ~ports:[] ~supported_domain:(Component_contract.Operating_domain.make []) ~identities ~assumptions ~guarantees ~evidence
    ~parameters:[] ~dependencies:[] ~capabilities:[] ~resources:[] ~synthetic_model:None
    ~reference_metadata:(Some (Component.Sequence_reference.make ~artifact_class ~sequence_length:(Z.of_int (M.Record.length record)) ~unknown_features:(M.Record.unknown_features record))) in
  Codec.preflight ~limits (Component.to_json result); result
