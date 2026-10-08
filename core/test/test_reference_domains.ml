open Bioc_wire
open Bioc_domain
module M=Reference_manifest
module C=Reference_construct
module N=Reference_molecular
let require condition message=if not condition then failwith message
let expect code message run=try ignore(run());failwith ("Expected "^code) with
  | Diagnostic.Error error->require (error.code=code && error.message=message) ("Unexpected diagnostic: "^error.code^": "^error.message)
let record ~id ~alphabet ~raw ~links =
  let sequence,normalization=M.normalize_sequence raw alphabet in
  M.Record.make ~reference_id:id ~variant_id:"fixture" ~version:"1" ~alphabet
    ~artifact_class:(match alphabet with M.DNA->"coding_dna"|M.RNA->"coding_rna"|M.Protein->"protein")
    ~orientation:(if alphabet=M.Protein then "N-to-C" else "5prime-to-3prime") ~source_id:"source" ~source_locator:"fixture"
    ~raw_sequence_text:raw ~raw_text_sha256:(Canonical.sha256 raw) ~sequence ~sequence_sha256:(Canonical.sha256 sequence)
    ~length:(String.length sequence) ~normalization ~linked_reference_ids:links ~completeness:"CDS-reference-only"
    ~unknown_features:["delivered-context"] ~evidence_relationships:["exact-experimental-material-identity-unresolved"] ()
let identity_tests ()=
  let r=record ~id:"réf.🧬" ~alphabet:M.DNA ~raw:"atg taa\n" ~links:["rna";"protein"] in
  (* Literal from the original ReferenceRecord constructor and ASCII canonical
     profile; UTF-8 canonical encoding deliberately has a different identity. *)
  require (M.Record.fingerprint r="08df09f57393588dcfb60526ab4bfdcd5417c5878b8a649778344998b4c23356") "Original Unicode reference identity changed";
  require (M.Record.canonical_size r=758) "Original ASCII reference size changed";
  require (M.Record.fingerprint r<>Canonical.fingerprint (M.Record.to_json r)) "ASCII reference profile collapsed into UTF-8";
  require (M.Record.fingerprint (M.Record.of_json (M.Record.to_json r))=M.Record.fingerprint r) "Reference roundtrip changed";
  require (M.translate_cds "ATGTAA" M.DNA="M*" && M.translate_cds "AUGUAA" M.RNA="M*") "Explicit nucleotide translation changed";
  expect "reference_manifest" "CDS requires exactly one terminal stop, with no internal stops." (fun()->M.translate_cds "ATGTAGTAA" M.DNA);
  expect "reference_manifest" "Only ASCII sequence letters and layout whitespace are allowed." (fun()->M.normalize_sequence "ATG TAA" M.DNA);
  expect "reference_manifest" "Invalid DNA symbol in reference extraction; no correction applied." (fun()->M.normalize_sequence "ATG1TAA" M.DNA)
let manifest_tests ()=
  let dna=record ~id:"dna" ~alphabet:M.DNA ~raw:"ATGTAA" ~links:["rna";"protein"]
  and rna=record ~id:"rna" ~alphabet:M.RNA ~raw:"AUGUAA" ~links:["dna";"protein"]
  and protein=record ~id:"protein" ~alphabet:M.Protein ~raw:"M*" ~links:["dna";"rna"] in
  let sources=[Json.Object ["id",Json.String "source";"url",Json.String "https://example.invalid/reference";
    "publication",Json.String "historical fixture";"publication_version",Json.String "1";"retrieved_on",Json.String "2024-02-29";
    "media_type",Json.String "text/plain";"sha256",Json.String (String.make 64 'a');"local_path",Json.Null]] in
  let translation=Json.Object ["genetic_code",Json.int 1;"frame_zero_based",Json.int 0;"start_codon",Json.String "ATG/AUG";
    "stop_convention",Json.String "exactly-one-terminal-star-retained";"protein_length_includes_stop",Json.Bool true] in
  let redistribution=Json.Object (List.map (fun key->key,Json.String "fixture") ["attribution";"terms_url";"license_status";"note"]) in
  let make status=M.make ~reference_set_id:"fixture" ~version:"1" ~sources ~records:[dna;rna;protein] ~translation ~reviews:[] ~status ~unresolved_discrepancies:[] ~redistribution () in
  let candidate=make M.Candidate in require (M.discrepancies candidate=[]) "Consistent reference declared discrepant";
  require (M.Record.reference_id (M.record ~require_accepted:false candidate "dna")="dna") "Candidate declaration lookup failed";
  expect "reference_manifest" "Reference set is candidate; promotion is required before build use." (fun()->M.record candidate "dna");
  expect "reference_manifest" "Acceptance requires extraction and independent passing review." (fun()->make M.Accepted)
let rich_declaration_tests ()=
  let big=Z.shift_left Z.one 90 in
  let span=C.Sequence_range.make ~start:big ~end_:(Z.succ big) () in
  require (Z.equal (C.Sequence_range.length span) Z.one) "Coordinates lost arbitrary precision";
  let molecule=C.Molecule.make ~id:"rich" ~alphabet:M.RNA ~artifact_class:"candidate-only" ~length:(Z.of_int 2)
    ~component_order:["second";"first"] ~topology:C.Circular ~completeness:"unspecified" ~unknown_features:[] ~compartment:"unspecified" () in
  require (C.Molecule.topology molecule=C.Circular && C.Molecule.component_order molecule=["second";"first"]) "Unsupported layout declaration was silently narrowed";
  ignore(C.Junction.make ~id:"gap" ~molecule_id:"rich" ~left_instance:"first" ~right_instance:"second" ~kind:C.Gap ~range:span ~choice:"unresolved" ~provenance:[] ());
  let policy=N.Translation_policy.make ~genetic_code:(Z.of_int 2) ~start_codon:"unresolved" ~stop_convention:"unresolved" ~protein_length_includes_stop:false () in
  require (Z.equal (N.Translation_policy.genetic_code policy) (Z.of_int 2)) "Translation declaration incorrectly became acceptance";
  ignore(N.Change.make ~id:"proposal" ~record_id:"r" ~before_sequence_sha256:(String.make 64 'a') ~after_sequence_sha256:(String.make 64 'b') ~changed_properties:["sequence"] ~reason:"untrusted proposal" ~preservation_claims:["untrusted claim"] ());
  expect "reference_molecular" "Unknown/inapplicable features have no value." (fun()->N.Feature_status.make ~feature:"cap" ~status:N.Unknown ~scope:N.Delivered_molecule ~reason:"unknown" ~value:(Some "absent") ())
let range_order_tests ()=
  (* SequenceRange(0,1491).to_dict() preserves this original field order even
     though its canonical identity sorts keys. Compare the actual ordered tree. *)
  let expected=Json.Object ["schema_version",Json.String "biocompiler.sequence_range.v0.1";
    "convention",Json.String "zero-based-half-open-reference-5prime-to-3prime.v1";
    "start",Json.int 0;"end",Json.int 1491] in
  let imported=C.Sequence_range.of_json (Json.Object (List.rev (Json.object_fields expected))) in
  let made=C.Sequence_range.make ~start:Z.zero ~end_:(Z.of_int 1491) () in
  List.iter (fun span->
    require (C.Sequence_range.to_json span=expected) "Original SequenceRange field order changed";
    require (C.Sequence_range.fingerprint span="a4be12800ea5579fd80cb4f705ccf4c37a176281fd7ebbf6040b8a91c4d9872f")
      "Original SequenceRange canonical identity changed";
    require (Z.equal (C.Sequence_range.start span) Z.zero &&
      Z.equal (C.Sequence_range.end_ span) (Z.of_int 1491)) "Range values changed during ordered projection"
  ) [imported;made];
  let component=Component_registry.Component_lock.make ~node_id:"instance" ~component_id:"fixture" ~version:"1" ~content_fingerprint:(String.make 64 'a') in
  let reference=Pinned_identity.make ~kind:Pinned_identity.Reference ~id:"ref" ~version:"1" ~content_fingerprint:(String.make 64 'b') in
  let placement=C.Placement.make ~instance_id:"instance" ~molecule_id:"molecule" ~component ~reference
    ~source_range:imported ~molecule_range:made ~orientation:C.Forward ~reading_frame:(Some 0) ~requirement_ids:[] ~source:None () in
  let raw=C.Placement.to_json placement in
  List.iter (fun value->List.iter (fun name->
    require (Json.field name (Json.object_fields value)=expected) "Nested placement range field order changed"
  ) ["source_range";"molecule_range"]) [raw;C.Placement.to_json (C.Placement.of_json raw)]
let changed key value raw=Json.Object (List.map (fun (name,old)->name,if name=key then value else old) (Json.object_fields raw))
let validation_order_tests ()=
  let molecule=C.Molecule.make ~id:"rich" ~alphabet:M.RNA ~artifact_class:"candidate-only" ~length:(Z.of_int 2)
    ~component_order:["second";"first"] ~topology:C.Circular ~completeness:"unspecified" ~unknown_features:[] ~compartment:"unspecified" () in
  let raw=C.Molecule.to_json molecule in
  expect "reference_construct" "id must be a nonempty string." (fun()->C.Molecule.of_json
    (raw |> changed "id" (Json.String " ") |> changed "topology" (Json.String "broken")));
  expect "reference_construct" "completeness must be a nonempty string." (fun()->C.Molecule.of_json
    (raw |> changed "completeness" (Json.String " ") |> changed "alphabet" (Json.String "broken")));
  let feature=N.Feature_status.make ~feature:"cap" ~status:N.Unknown ~scope:N.Delivered_molecule ~reason:"unknown" ~value:None () in
  expect "reference_molecular" "Molecular feature must be a nonempty string." (fun()->N.Feature_status.of_json
    (N.Feature_status.to_json feature |> changed "feature" (Json.String " ") |> changed "status" (Json.String "broken")));
  let component=Component_registry.Component_lock.make ~node_id:"instance" ~component_id:"fixture" ~version:"1" ~content_fingerprint:(String.make 64 'a') in
  let reference=Pinned_identity.make ~kind:Pinned_identity.Reference ~id:"ref" ~version:"1" ~content_fingerprint:(String.make 64 'b') in
  let range=C.Sequence_range.make ~start:Z.zero ~end_:Z.one () in
  let placement=C.Placement.make ~instance_id:"instance" ~molecule_id:"molecule" ~component ~reference
    ~source_range:range ~molecule_range:range ~orientation:C.Forward ~reading_frame:(Some 0) ~requirement_ids:[] ~source:None () in
  let raw=C.Placement.to_json placement |> changed "instance_id" (Json.String " ") in
  (* Child decoders run in field order before the original scalar post-init
     checks, even when both input regions are malformed. *)
  expect "reference_construct" "Invalid fields in ComponentLock." (fun()->C.Placement.of_json (changed "component" (Json.Object []) raw));
  expect "reference_construct" "Source location must be an object." (fun()->C.Placement.of_json (changed "source" (Json.Bool false) raw))
let json_text_tests ()=
  expect "legacy_reference_json" "Invalid reference JSON: Duplicate JSON field: version."
    (fun()->M.of_json_text {|{"version":"1","version":"2"}|});
  expect "legacy_reference_json" "Invalid reference JSON: Invalid number: NaN"
    (fun()->M.of_json_text {|{"value":NaN}|});
  expect "legacy_artifact_json" "Duplicate JSON key: molecules."
    (fun()->C.Candidate.of_json_text {|{"molecules":[],"molecules":[]}|});
  expect "legacy_artifact_json" "Duplicate JSON key: records."
    (fun()->N.Artifact.of_json_text {|{"records":[],"records":[]}|});
  expect "reference_manifest" "Missing raw sequence text."
    (fun()->M.normalize_sequence_json ~raw_text:(Json.Bool true) ~alphabet:Json.Null ());
  let span=C.Sequence_range.make ~start:Z.zero ~end_:(Z.of_int 3) () in
  require (C.Sequence_range.fingerprint (C.Sequence_range.of_json_text (Canonical.encode (C.Sequence_range.to_json span)))=C.Sequence_range.fingerprint span)
    "Raw artifact parsing changed the typed declaration"
let budget_tests ()=
  let charged=ref 0 in
  let limits=M.Codec.make_limits ~charge:(fun amount->charged:= !charged+amount) () in
  ignore(M.normalize_sequence ~limits "a t g t a a" M.DNA); require (!charged>0) "Reference normalization escaped its ancestor";
  let limits=M.Codec.make_limits ~charge:(fun _->Diagnostic.fail "work_limit" "sentinel") () in
  expect "work_limit" "sentinel" (fun()->M.translate_cds ~limits "ATGTAA" M.DNA);
  let limits=M.Codec.make_limits ~max_bytes:4 () in
  (try ignore(M.normalize_sequence ~limits "ATGTAA" M.DNA);failwith "Reduced byte bound accepted" with Diagnostic.Error error->require (error.code="verification_exploration_limit") "Resource exhaustion was remapped to semantic rejection");
  let rec cyclic=Json.Array [cyclic] in
  (try C.bounded_json cyclic;failwith "Cyclic declaration accepted" with Diagnostic.Error error->require (error.code="verification_exploration_cycle") "Cycle diagnostic changed")
let ()=
  identity_tests();manifest_tests();rich_declaration_tests();range_order_tests();validation_order_tests();json_text_tests();budget_tests();
  print_endline "Reference domains: exact identities, rich declarations and resource boundaries passed."
