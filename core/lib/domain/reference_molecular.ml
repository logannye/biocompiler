open Bioc_wire
module Codec = Verification_exploration.Codec
let default_limits=Reference_manifest.default_limits
let require ?path condition message=Diagnostic.require ?path condition "reference_molecular" message
let str value=Json.String value
let obj value=Json.Object value
let get key raw=Json.field key (Json.object_fields raw)
let bounded_json ?(limits=default_limits) ?(path="") raw=Codec.preflight ~limits ~path raw
let is_named = function Json.String value ->
  let rec walk i=if i>=String.length value then false else
    let decoded=String.get_utf_8_uchar value i in
    let n=Uchar.to_int (Uchar.utf_decode_uchar decoded) in
    let whitespace=(n>=9 && n<=13)||(n>=28 && n<=32)||List.mem n [0x85;0xa0;0x1680;0x2028;0x2029;0x202f;0x205f;0x3000]||(n>=0x2000 && n<=0x200a) in
    not whitespace || walk (i+Uchar.utf_decode_length decoded) in walk 0
  | _->false
let named ?(label="Declaration") raw=require (is_named raw) (label^" must be a nonempty string.");Json.string raw
let record_fields ~path label keys raw=
  let valid=match raw with Json.Object fields->List.length fields=List.length keys && List.for_all (fun key->List.mem_assoc key fields) keys|_->false in
  require ~path valid ("Invalid fields in "^label^".")
let hash ?(label="Identity") raw=let valid=match raw with Json.String value->String.length value=64 && String.for_all (function '0'..'9'|'a'..'f'->true|_->false) value|_->false in
  require valid (label^" must be a SHA-256 fingerprint.");Json.string raw
let option decode = function Json.Null->None|raw->Some (decode raw)
let option_json encode = function None->Json.Null|Some value->encode value
let unique limits label values=
  let seen=Hashtbl.create 16 in List.iter (fun value->Codec.charge limits (String.length value+1);
    require (not (Hashtbl.mem seen value)) ("Duplicate "^label^"."); Hashtbl.add seen value ()) values
let names ?(label="Names") limits raw=
  require (match raw with Json.Array _->true|_->false) (label^" must be an array.");
  let values=List.map (named ~label) (Json.array raw) in
  let seen=Hashtbl.create 16 in List.iter (fun value->Codec.charge limits (String.length value+1);require (not (Hashtbl.mem seen value)) (label^" must be unique.");Hashtbl.add seen value ()) values; values
let records_input family raw=require (match raw with Json.Array _->true|_->false) (family^" records must be arrays.");Json.array raw
let array limits encode values=
  let maximum=Z.to_int (Json.integer (get "max_nodes" (Codec.limits_json limits))) in
  let rec walk n reverse=function []->Json.Array (List.rev reverse)|value::rest->
    Codec.charge limits 1; Diagnostic.require (n<maximum) "reference_molecular_limit" "Reference collection exceeds its node bound.";
    walk (n+1) (encode value::reverse) rest in walk 0 [] values
let legacy limits decode raw=let size=Codec.measure ~limits raw in Codec.charge limits (64*(size.bytes+size.nodes+1)); decode raw
let same limits left right=
  let left=Codec.encode ~limits left in
  let right=Codec.encode ~limits right in
  Codec.charge limits (String.length left+String.length right+1);String.equal left right
type feature_status = Known | Unknown | Inapplicable
let feature_status_name = function Known->"known"|Unknown->"unknown"|Inapplicable->"inapplicable"
let feature_status_of_json raw=match raw with Json.String "known"->Known|Json.String "unknown"->Unknown|Json.String "inapplicable"->Inapplicable|_->Diagnostic.fail "reference_molecular" "Invalid feature status."
type feature_scope = Cds_record | Delivered_molecule
let feature_scope_name = function Cds_record->"cds_record"|Delivered_molecule->"delivered_molecule"
let feature_scope_of_json raw=match raw with Json.String "cds_record"->Cds_record|Json.String "delivered_molecule"->Delivered_molecule|_->Diagnostic.fail "reference_molecular" "Invalid feature scope."
type profile = Dna_cds | Rna_cds
let profile_name = function Dna_cds->"DNA-CDS"|Rna_cds->"RNA-CDS"
let profile_of_json raw=match raw with Json.String "DNA-CDS"->Dna_cds|Json.String "RNA-CDS"->Rna_cds|_->Diagnostic.fail "reference_molecular" "Invalid molecular profile."
let orientation raw=match raw with Json.String "forward"->Reference_construct.Forward|Json.String "reverse"->Reference_construct.Reverse|_->Diagnostic.fail "reference_molecular" "Invalid molecular orientation."
let frame raw=option (fun value->require (match value with Json.Int n->Z.sign n>=0 && Z.compare n (Z.of_int 2)<=0|_->false) "A reading frame must be 0, 1, 2 or unspecified.";let n=Json.integer value in require (Z.sign n>=0 && Z.compare n (Z.of_int 2)<=0) "A reading frame must be 0, 1, 2 or unspecified.";Z.to_int n) raw
let alphabet raw=match raw with Json.String "DNA"->Reference_manifest.DNA|Json.String "RNA"->Reference_manifest.RNA|_->Diagnostic.fail "reference_molecular" "Invalid molecular alphabet."
let canonical_sequence_sha256 ?(limits=default_limits) sequence alphabet=
  ignore (Codec.measure ~limits (str sequence)); Codec.charge limits (4*(String.length sequence+1));
  require (alphabet=Reference_manifest.DNA || alphabet=Reference_manifest.RNA) "Invalid molecular alphabet.";
  require (sequence<>"" && String.for_all (fun c->String.contains (if alphabet=Reference_manifest.DNA then "ACGT" else "ACGU") c) sequence) "Molecular sequence must contain canonical uppercase alphabet symbols only.";
  Canonical.sha256 sequence
let parse_text limits profile text =
  let bounds=Codec.limits_json limits in
  let max_bytes=Z.to_int (Json.integer (Json.field "max_bytes" (Json.object_fields bounds)))
  and max_nodes=Z.to_int (Json.integer (Json.field "max_nodes" (Json.object_fields bounds))) in
  Diagnostic.require (String.length text<=max_bytes) "reference_text_limit" "Reference JSON text exceeds its byte bound.";
  Codec.charge limits (16*String.length text+8*max_nodes);
  Legacy_json.parse ~max_bytes ~max_nodes ~profile text

module Feature_status = struct
  type t={json:Json.t;identity:string;bytes:int;feature:string;status:feature_status;scope:feature_scope;reason:string;value:string option}
  let schema_version="biocompiler.molecular_feature_status.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "FeatureStatus" ["schema_version";"feature";"status";"scope";"reason";"value"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported FeatureStatus schema.";
    let feature=named ~label:"Molecular feature" (get "feature" raw) in
    let reason=named ~label:"Feature status reason" (get "reason" raw) in
    let status=feature_status_of_json (get "status" raw) in
    let scope=feature_scope_of_json (get "scope" raw) in
    require ((status=Known && is_named (get "value" raw)) || (status<>Known && get "value" raw=Json.Null)) (if status=Known then "Known feature value must be a nonempty string." else "Unknown/inapplicable features have no value.");
    let value=option Json.string (get "value" raw) in
    let json=obj ["schema_version",str schema_version;"feature",str feature;"status",str (feature_status_name status);"scope",str (feature_scope_name scope);"reason",str reason;"value",option_json str value] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;feature;status;scope;reason;value}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~feature ~status ~scope ~reason ~value () =
    of_json ~limits (obj ["schema_version",str schema_version;"feature",str feature;"status",str (feature_status_name status);"scope",str (feature_scope_name scope);"reason",str reason;"value",option_json str value])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let feature (v:t)=v.feature
  let status (v:t)=v.status
  let scope (v:t)=v.scope
  let reason (v:t)=v.reason
  let value (v:t)=v.value
end
module Translation_policy = struct
  type t={json:Json.t;identity:string;bytes:int;genetic_code:Z.t;start_codon:string;stop_convention:string;protein_length_includes_stop:bool}
  let schema_version="biocompiler.translation_policy.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "TranslationPolicy" ["schema_version";"genetic_code";"start_codon";"stop_convention";"protein_length_includes_stop"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported TranslationPolicy schema.";
    require (match get "genetic_code" raw with Json.Int n->Z.sign n>0|_->false) "Genetic code must be a positive integer.";
    let genetic_code=Json.integer (get "genetic_code" raw) in
    let start_codon=named ~label:"Start codon convention" (get "start_codon" raw) in
    let stop_convention=named ~label:"Termination convention" (get "stop_convention" raw) in
    require (match get "protein_length_includes_stop" raw with Json.Bool _->true|_->false) "Protein length convention must be Boolean.";
    let protein_length_includes_stop=Json.boolean (get "protein_length_includes_stop" raw) in
    require ~path (Z.sign genetic_code>0) "Genetic code must be a positive integer.";
    let json=obj ["schema_version",str schema_version;"genetic_code",Json.Int genetic_code;"start_codon",str start_codon;"stop_convention",str stop_convention;"protein_length_includes_stop",Json.Bool protein_length_includes_stop] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;genetic_code;start_codon;stop_convention;protein_length_includes_stop}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~genetic_code ~start_codon ~stop_convention ~protein_length_includes_stop () =
    of_json ~limits (obj ["schema_version",str schema_version;"genetic_code",Json.Int genetic_code;"start_codon",str start_codon;"stop_convention",str stop_convention;"protein_length_includes_stop",Json.Bool protein_length_includes_stop])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let genetic_code (v:t)=v.genetic_code
  let start_codon (v:t)=v.start_codon
  let stop_convention (v:t)=v.stop_convention
  let protein_length_includes_stop (v:t)=v.protein_length_includes_stop
  let default ?(limits=default_limits) ()=make ~limits ~genetic_code:Z.one ~start_codon:"ATG/AUG" ~stop_convention:"exactly-one-terminal-star-retained" ~protein_length_includes_stop:true ()
end
module Encoding_policy = struct
  type t={json:Json.t;identity:string;bytes:int;mode:string;optimization:string;transformations:string list}
  let schema_version="biocompiler.encoding_policy.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "EncodingPolicy" ["schema_version";"mode";"optimization";"transformations"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported EncodingPolicy schema.";
    let transformations=names ~label:"Transformations" limits (get "transformations" raw) in
    require (get "mode" raw=str "exact_reference" && get "optimization" raw=str "disabled" && transformations=[]) "Exact-reference encoding requires disabled optimization and no transformations.";
    let mode=Json.string (get "mode" raw) in
    let optimization=Json.string (get "optimization" raw) in
    require ~path (mode="exact_reference" && optimization="disabled" && transformations=[]) "Exact-reference encoding requires disabled optimization and no transformations.";
    let json=obj ["schema_version",str schema_version;"mode",str mode;"optimization",str optimization;"transformations",array limits str transformations] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;mode;optimization;transformations}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~mode ~optimization ~transformations () =
    of_json ~limits (obj ["schema_version",str schema_version;"mode",str mode;"optimization",str optimization;"transformations",array limits str transformations])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let mode (v:t)=v.mode
  let optimization (v:t)=v.optimization
  let transformations (v:t)=v.transformations
  let default ?(limits=default_limits) ()=make ~limits ~mode:"exact_reference" ~optimization:"disabled" ~transformations:[] ()
end
module Evidence_policy = struct
  type t={json:Json.t;identity:string;bytes:int;semantic_properties:string list;invalidated_analyses:string list}
  let schema_version="biocompiler.encoding_evidence_policy.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "EncodingEvidencePolicy" ["schema_version";"semantic_properties";"invalidated_analyses"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported EncodingEvidencePolicy schema.";
    let semantic_properties=names ~label:"semantic_properties" limits (get "semantic_properties" raw) in
    let invalidated_analyses=names ~label:"invalidated_analyses" limits (get "invalidated_analyses" raw) in
    require ~path (semantic_properties=["sequence";"chemistry";"end_features";"topology";"boundaries"] && invalidated_analyses=["construct";"composition";"molecular";"structure";"expression";"behavior"]) "Encoding evidence invalidation policy cannot be weakened or replaced.";
    let json=obj ["schema_version",str schema_version;"semantic_properties",array limits str semantic_properties;"invalidated_analyses",array limits str invalidated_analyses] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;semantic_properties;invalidated_analyses}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~semantic_properties ~invalidated_analyses () =
    of_json ~limits (obj ["schema_version",str schema_version;"semantic_properties",array limits str semantic_properties;"invalidated_analyses",array limits str invalidated_analyses])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let semantic_properties (v:t)=v.semantic_properties
  let invalidated_analyses (v:t)=v.invalidated_analyses
  let default ?(limits=default_limits) ()=make ~limits ~semantic_properties:["sequence";"chemistry";"end_features";"topology";"boundaries"] ~invalidated_analyses:["construct";"composition";"molecular";"structure";"expression";"behavior"] ()
end
module Change = struct
  type t={json:Json.t;identity:string;bytes:int;id:string;record_id:string;before_sequence_sha256:string;after_sequence_sha256:string;changed_properties:string list;reason:string;preservation_claims:string list}
  let schema_version="biocompiler.encoding_change.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "EncodingChange" ["schema_version";"id";"record_id";"before_sequence_sha256";"after_sequence_sha256";"changed_properties";"reason";"preservation_claims"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported EncodingChange schema.";
    let id=named ~label:"id" (get "id" raw) in
    let record_id=named ~label:"record_id" (get "record_id" raw) in
    let reason=named ~label:"reason" (get "reason" raw) in
    let before_sequence_sha256=hash ~label:"before_sequence_sha256" (get "before_sequence_sha256" raw) in
    let after_sequence_sha256=hash ~label:"after_sequence_sha256" (get "after_sequence_sha256" raw) in
    let changed_properties=names ~label:"changed_properties" limits (get "changed_properties" raw) in
    let preservation_claims=names ~label:"preservation_claims" limits (get "preservation_claims" raw) in
    require ~path (changed_properties<>[] && List.for_all (fun p->List.mem p ["sequence";"chemistry";"end_features";"topology";"boundaries"]) changed_properties) "Encoding change requires explicit supported changed properties.";
    let json=obj ["schema_version",str schema_version;"id",str id;"record_id",str record_id;"before_sequence_sha256",str before_sequence_sha256;"after_sequence_sha256",str after_sequence_sha256;"changed_properties",array limits str changed_properties;"reason",str reason;"preservation_claims",array limits str preservation_claims] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;id;record_id;before_sequence_sha256;after_sequence_sha256;changed_properties;reason;preservation_claims}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~id ~record_id ~before_sequence_sha256 ~after_sequence_sha256 ~changed_properties ~reason ~preservation_claims () =
    of_json ~limits (obj ["schema_version",str schema_version;"id",str id;"record_id",str record_id;"before_sequence_sha256",str before_sequence_sha256;"after_sequence_sha256",str after_sequence_sha256;"changed_properties",array limits str changed_properties;"reason",str reason;"preservation_claims",array limits str preservation_claims])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let id (v:t)=v.id
  let record_id (v:t)=v.record_id
  let before_sequence_sha256 (v:t)=v.before_sequence_sha256
  let after_sequence_sha256 (v:t)=v.after_sequence_sha256
  let changed_properties (v:t)=v.changed_properties
  let reason (v:t)=v.reason
  let preservation_claims (v:t)=v.preservation_claims
end
module Record = struct
  type t={json:Json.t;identity:string;bytes:int;id:string;instance_id:string;molecule_id:string;alphabet:Reference_manifest.alphabet;artifact_class:string;sequence:string;sequence_sha256:string;component:Component_registry.Component_lock.t;reference_selection:Reference_components.Selection.t;source_range:Reference_construct.Sequence_range.t;molecule_range:Reference_construct.Sequence_range.t;features:Reference_construct.Feature.t list;feature_statuses:Feature_status.t list;orientation:Reference_construct.orientation;reading_frame:int option;translation_policy:Translation_policy.t;completeness:string;unknown_features:string list;evidence_relationships:string list;requirement_ids:string list;source:Behavior.source_location option}
  let schema_version="biocompiler.molecular_record.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "MolecularRecord" ["schema_version";"id";"instance_id";"molecule_id";"alphabet";"artifact_class";"sequence";"sequence_sha256";"component";"reference_selection";"source_range";"molecule_range";"features";"feature_statuses";"orientation";"reading_frame";"translation_policy";"completeness";"unknown_features";"evidence_relationships";"requirement_ids";"source";"length"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported MolecularRecord schema.";
    let component=legacy limits (fun raw->record_fields ~path:"" "ComponentLock" ["schema_version";"node_id";"component_id";"version";"content_fingerprint"] raw;Component_registry.Component_lock.of_json raw) (get "component" raw) in
    let reference_selection=Reference_components.Selection.of_json ~limits (get "reference_selection" raw) in
    let source_range=Reference_construct.Sequence_range.of_json ~limits (get "source_range" raw) in
    let molecule_range=Reference_construct.Sequence_range.of_json ~limits (get "molecule_range" raw) in
    let features=List.map (Reference_construct.Feature.of_json ~limits) (records_input "Molecular" (get "features" raw)) in
    let feature_statuses=List.map (Feature_status.of_json ~limits) (records_input "Molecular" (get "feature_statuses" raw)) in
    let translation_policy=Translation_policy.of_json ~limits (get "translation_policy" raw) in
    let source=Reference_construct.source_of_json ~limits (get "source" raw) in
    let id=named ~label:"id" (get "id" raw) in
    let instance_id=named ~label:"instance_id" (get "instance_id" raw) in
    let molecule_id=named ~label:"molecule_id" (get "molecule_id" raw) in
    let artifact_class=named ~label:"artifact_class" (get "artifact_class" raw) in
    let completeness=named ~label:"completeness" (get "completeness" raw) in
    let alphabet=alphabet (get "alphabet" raw) in
    require (match get "sequence" raw with Json.String value->value<>"" && String.for_all (fun c->String.contains (if alphabet=Reference_manifest.DNA then "ACGT" else "ACGU") c) value|_->false) "Molecular sequence must contain canonical uppercase alphabet symbols only.";
    let sequence=Json.string (get "sequence" raw) in
    ignore (canonical_sequence_sha256 ~limits sequence alphabet);
    let sequence_sha256=hash ~label:"Canonical sequence identity" (get "sequence_sha256" raw) in
    require ~path (Z.sign (Reference_construct.Sequence_range.length source_range)>0 && Z.sign (Reference_construct.Sequence_range.length molecule_range)>0) "Molecular records require nonempty coordinate ranges.";
    unique limits "molecular feature IDs" (List.map Reference_construct.Feature.id features);
    unique limits "scoped molecular feature statuses" (List.map (fun item->Codec.encode ~limits (Json.Array [str (feature_scope_name (Feature_status.scope item));str (Feature_status.feature item)])) feature_statuses);
    let orientation=orientation (get "orientation" raw) in
    let reading_frame=frame (get "reading_frame" raw) in
    let unknown_features=names ~label:"unknown_features" limits (get "unknown_features" raw) in
    let evidence_relationships=names ~label:"evidence_relationships" limits (get "evidence_relationships" raw) in
    let requirement_ids=names ~label:"requirement_ids" limits (get "requirement_ids" raw) in
    let derived_length=Json.int (String.length sequence) in
    require ~path (same limits (get "length" raw) derived_length) "Derived molecular length differs from its authority.";
    let json=obj ["schema_version",str schema_version;"id",str id;"instance_id",str instance_id;"molecule_id",str molecule_id;"alphabet",str (Reference_manifest.alphabet_name alphabet);"artifact_class",str artifact_class;"sequence",str sequence;"sequence_sha256",str sequence_sha256;"component",Component_registry.Component_lock.to_json component;"reference_selection",Reference_components.Selection.to_json reference_selection;"source_range",Reference_construct.Sequence_range.to_json source_range;"molecule_range",Reference_construct.Sequence_range.to_json molecule_range;"features",array limits Reference_construct.Feature.to_json features;"feature_statuses",array limits Feature_status.to_json feature_statuses;"orientation",str (Reference_construct.orientation_name orientation);"reading_frame",option_json Json.int reading_frame;"translation_policy",Translation_policy.to_json translation_policy;"completeness",str completeness;"unknown_features",array limits str unknown_features;"evidence_relationships",array limits str evidence_relationships;"requirement_ids",array limits str requirement_ids;"source",Reference_construct.source_to_json source;"length",derived_length] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;id;instance_id;molecule_id;alphabet;artifact_class;sequence;sequence_sha256;component;reference_selection;source_range;molecule_range;features;feature_statuses;orientation;reading_frame;translation_policy;completeness;unknown_features;evidence_relationships;requirement_ids;source}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~id ~instance_id ~molecule_id ~alphabet ~artifact_class ~sequence ~sequence_sha256 ~component ~reference_selection ~source_range ~molecule_range ~features ~feature_statuses ~orientation ~reading_frame ~translation_policy ~completeness ~unknown_features ~evidence_relationships ~requirement_ids ~source () =
    let derived_length=Json.int (String.length sequence) in
    of_json ~limits (obj ["schema_version",str schema_version;"id",str id;"instance_id",str instance_id;"molecule_id",str molecule_id;"alphabet",str (Reference_manifest.alphabet_name alphabet);"artifact_class",str artifact_class;"sequence",str sequence;"sequence_sha256",str sequence_sha256;"component",Component_registry.Component_lock.to_json component;"reference_selection",Reference_components.Selection.to_json reference_selection;"source_range",Reference_construct.Sequence_range.to_json source_range;"molecule_range",Reference_construct.Sequence_range.to_json molecule_range;"features",array limits Reference_construct.Feature.to_json features;"feature_statuses",array limits Feature_status.to_json feature_statuses;"orientation",str (Reference_construct.orientation_name orientation);"reading_frame",option_json Json.int reading_frame;"translation_policy",Translation_policy.to_json translation_policy;"completeness",str completeness;"unknown_features",array limits str unknown_features;"evidence_relationships",array limits str evidence_relationships;"requirement_ids",array limits str requirement_ids;"source",Reference_construct.source_to_json source;"length",derived_length])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let id (v:t)=v.id
  let instance_id (v:t)=v.instance_id
  let molecule_id (v:t)=v.molecule_id
  let alphabet (v:t)=v.alphabet
  let artifact_class (v:t)=v.artifact_class
  let sequence (v:t)=v.sequence
  let sequence_sha256 (v:t)=v.sequence_sha256
  let component (v:t)=v.component
  let reference_selection (v:t)=v.reference_selection
  let source_range (v:t)=v.source_range
  let molecule_range (v:t)=v.molecule_range
  let features (v:t)=v.features
  let feature_statuses (v:t)=v.feature_statuses
  let orientation (v:t)=v.orientation
  let reading_frame (v:t)=v.reading_frame
  let translation_policy (v:t)=v.translation_policy
  let completeness (v:t)=v.completeness
  let unknown_features (v:t)=v.unknown_features
  let evidence_relationships (v:t)=v.evidence_relationships
  let requirement_ids (v:t)=v.requirement_ids
  let source (v:t)=v.source
  let length (v:t)=String.length v.sequence
  let reference (v:t)=Reference_components.Selection.reference v.reference_selection
end
module Artifact = struct
  type t={json:Json.t;identity:string;bytes:int;request_fingerprint:string;construct_fingerprint:string;layout_fingerprint:string;registry_lock:Component_registry.Lock.t;profile:profile;records:Record.t list;encoding_policy:Encoding_policy.t;evidence_policy:Evidence_policy.t;changes:Change.t list;source_request_fingerprint:string option;artifact_scope:string}
  let schema_version="biocompiler.molecular.v0.2"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "MolecularArtifact" ["schema_version";"request_fingerprint";"construct_fingerprint";"layout_fingerprint";"registry_lock";"profile";"records";"encoding_policy";"evidence_policy";"changes";"source_request_fingerprint";"artifact_scope";"intended_use";"human_therapeutic_admission";"nodes"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported MolecularArtifact schema.";
    let registry_lock=legacy limits (fun raw->record_fields ~path:"" "RegistryLock" ["schema_version";"registry_id";"registry_version";"registry_fingerprint";"components";"identities"] raw;Component_registry.Lock.of_json raw) (get "registry_lock" raw) in
    let records=List.map (Record.of_json ~limits) (records_input "Molecular" (get "records" raw)) in
    let encoding_policy=Encoding_policy.of_json ~limits (get "encoding_policy" raw) in
    let evidence_policy=Evidence_policy.of_json ~limits (get "evidence_policy" raw) in
    let changes=List.map (Change.of_json ~limits) (records_input "Molecular" (get "changes" raw)) in
    let request_fingerprint=hash ~label:"request_fingerprint" (get "request_fingerprint" raw) in
    let construct_fingerprint=hash ~label:"construct_fingerprint" (get "construct_fingerprint" raw) in
    let layout_fingerprint=hash ~label:"layout_fingerprint" (get "layout_fingerprint" raw) in
    let source_request_fingerprint=option (hash ~label:"Source request identity") (get "source_request_fingerprint" raw) in
    let profile=profile_of_json (get "profile" raw) in
    require (get "artifact_scope" raw=str "exact_cds") "Unsupported molecular scope.";
    let artifact_scope=Json.string (get "artifact_scope" raw) in
    unique limits "molecular records IDs" (List.map Record.id records);
    unique limits "molecular changes IDs" (List.map Change.id changes);
    unique limits "molecular source instance IDs" (List.map Record.instance_id records);
    let derived_intended_use=str "software_test" in
    require ~path (same limits (get "intended_use" raw) derived_intended_use) "Derived molecular intended_use differs from its authority.";
    let derived_human_therapeutic_admission=str "not_admitted" in
    require ~path (same limits (get "human_therapeutic_admission" raw) derived_human_therapeutic_admission) "Derived molecular human_therapeutic_admission differs from its authority.";
    let derived_nodes=array limits (fun item->obj ["id",str (Record.instance_id item);"kind",str "cds_record"]) records in
    require ~path (same limits (get "nodes" raw) derived_nodes) "Derived molecular nodes differs from its authority.";
    let json=obj ["schema_version",str schema_version;"request_fingerprint",str request_fingerprint;"construct_fingerprint",str construct_fingerprint;"layout_fingerprint",str layout_fingerprint;"registry_lock",Component_registry.Lock.to_json registry_lock;"profile",str (profile_name profile);"records",array limits Record.to_json records;"encoding_policy",Encoding_policy.to_json encoding_policy;"evidence_policy",Evidence_policy.to_json evidence_policy;"changes",array limits Change.to_json changes;"source_request_fingerprint",option_json str source_request_fingerprint;"artifact_scope",str artifact_scope;"intended_use",derived_intended_use;"human_therapeutic_admission",derived_human_therapeutic_admission;"nodes",derived_nodes] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;request_fingerprint;construct_fingerprint;layout_fingerprint;registry_lock;profile;records;encoding_policy;evidence_policy;changes;source_request_fingerprint;artifact_scope}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~request_fingerprint ~construct_fingerprint ~layout_fingerprint ~registry_lock ~profile ~records ~encoding_policy ~evidence_policy ~changes ~source_request_fingerprint ~artifact_scope () =
    let derived_intended_use=str "software_test" in
    let derived_human_therapeutic_admission=str "not_admitted" in
    let derived_nodes=array limits (fun item->obj ["id",str (Record.instance_id item);"kind",str "cds_record"]) records in
    of_json ~limits (obj ["schema_version",str schema_version;"request_fingerprint",str request_fingerprint;"construct_fingerprint",str construct_fingerprint;"layout_fingerprint",str layout_fingerprint;"registry_lock",Component_registry.Lock.to_json registry_lock;"profile",str (profile_name profile);"records",array limits Record.to_json records;"encoding_policy",Encoding_policy.to_json encoding_policy;"evidence_policy",Evidence_policy.to_json evidence_policy;"changes",array limits Change.to_json changes;"source_request_fingerprint",option_json str source_request_fingerprint;"artifact_scope",str artifact_scope;"intended_use",derived_intended_use;"human_therapeutic_admission",derived_human_therapeutic_admission;"nodes",derived_nodes])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let request_fingerprint (v:t)=v.request_fingerprint
  let construct_fingerprint (v:t)=v.construct_fingerprint
  let layout_fingerprint (v:t)=v.layout_fingerprint
  let registry_lock (v:t)=v.registry_lock
  let profile (v:t)=v.profile
  let records (v:t)=v.records
  let encoding_policy (v:t)=v.encoding_policy
  let evidence_policy (v:t)=v.evidence_policy
  let changes (v:t)=v.changes
  let source_request_fingerprint (v:t)=v.source_request_fingerprint
  let artifact_scope (v:t)=v.artifact_scope
end
let reference_feature_statuses ?(limits=default_limits) reference=
  let module R=Reference_manifest.Record in
  Codec.charge limits (16*(R.canonical_size reference+1));
  require (R.alphabet reference<>Reference_manifest.Protein) "Expected a nucleotide reference.";
  let known=["alphabet",Reference_manifest.alphabet_name (R.alphabet reference);"sequence-orientation",R.orientation reference;
    "coding-boundaries","0:"^string_of_int (R.length reference);"reading-frame","0";"genetic-code","1";
    "termination","exactly-one-terminal-star-retained";"completeness",R.completeness reference;"canonical-sequence-sha256",R.sequence_sha256 reference] in
  List.map (fun (feature,value)->Feature_status.make ~limits ~feature ~status:Known ~scope:Cds_record
    ~reason:"Pinned CDS reference record and standard-code policy." ~value:(Some value) ()) known @
  List.map (fun feature->Feature_status.make ~limits ~feature ~status:Unknown
    ~scope:(if feature="domain-feature-coordinates" then Cds_record else Delivered_molecule)
    ~reason:"The reviewed reference does not establish this feature." ~value:None ()) (R.unknown_features reference) @
  List.map (fun feature->Feature_status.make ~limits ~feature ~status:Inapplicable ~scope:Cds_record
    ~reason:"An exact CDS spelling does not specify a delivered molecule." ~value:None ())
    ["cap";"nucleotide-modifications";"poly(A)-tail";"UTRs";"regulatory-context";"delivered-molecule-topology";"full-delivered-molecule-boundaries"]
