open Bioc_wire
module Codec = Verification_exploration.Codec
let default_limits=Reference_manifest.default_limits
let require ?path condition message=Diagnostic.require ?path condition "reference_construct" message
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
    Codec.charge limits 1; Diagnostic.require (n<maximum) "reference_construct_limit" "Reference collection exceeds its node bound.";
    walk (n+1) (encode value::reverse) rest in walk 0 [] values
let legacy limits decode raw=let size=Codec.measure ~limits raw in Codec.charge limits (64*(size.bytes+size.nodes+1)); decode raw
let same limits left right=
  let left=Codec.encode ~limits left in
  let right=Codec.encode ~limits right in
  Codec.charge limits (String.length left+String.length right+1);String.equal left right
type orientation = Forward | Reverse
let orientation_name = function Forward->"forward"|Reverse->"reverse"
let orientation_of_json raw=match raw with Json.String "forward"->Forward|Json.String "reverse"->Reverse|_->Diagnostic.fail "reference_construct" "Invalid orientation."
type topology = Linear | Circular | Unspecified
let topology_name = function Linear->"linear"|Circular->"circular"|Unspecified->"unspecified"
let topology_of_json raw=match raw with Json.String "linear"->Linear|Json.String "circular"->Circular|Json.String "unspecified"->Unspecified|_->Diagnostic.fail "reference_construct" "Invalid topology."
type junction_kind = Direct | Overlap | Gap
let junction_kind_name = function Direct->"direct"|Overlap->"overlap"|Gap->"gap"
let junction_kind_of_json raw=match raw with Json.String "direct"->Direct|Json.String "overlap"->Overlap|Json.String "gap"->Gap|_->Diagnostic.fail "reference_construct" "Invalid junction kind."
type dependency_kind = Same_cell | Co_payload | Regulatory | Resource
let dependency_kind_name = function Same_cell->"same_cell"|Co_payload->"co_payload"|Regulatory->"regulatory"|Resource->"resource"
let dependency_kind_of_json raw=match raw with Json.String "same_cell"->Same_cell|Json.String "co_payload"->Co_payload|Json.String "regulatory"->Regulatory|Json.String "resource"->Resource|_->Diagnostic.fail "reference_construct" "Invalid construct dependency kind."
let source_of_json ?(limits=default_limits) ?(path="") raw=match raw with Json.Null->None|_->
  Codec.preflight ~limits ~path raw;
  require ~path (match raw with Json.Object _->true|_->false) "Source location must be an object.";
  record_fields ~path "source location" ["file";"line";"function"] raw;
  let file=named ~label:"Source file" (get "file" raw) in
  let function_name=named ~label:"Source function" (get "function" raw) in
  require (match get "line" raw with Json.Int value->Z.sign value>0|_->false) "Source line must be a positive integer.";
  let line=Json.integer (get "line" raw) in
  require ~path (Z.sign line>0) "Source line must be a positive integer.";
  Some {Behavior.file;line;function_name}
let source_to_json = function None->Json.Null|Some (value:Behavior.source_location)->obj ["file",str value.file;"line",Json.Int value.line;"function",str value.function_name]
let frame raw=option (fun value->require (match value with Json.Int n->Z.sign n>=0 && Z.compare n (Z.of_int 2)<=0|_->false) "A reading frame must be 0, 1, 2 or unspecified.";let n=Json.integer value in require (Z.sign n>=0 && Z.compare n (Z.of_int 2)<=0) "A reading frame must be 0, 1, 2 or unspecified.";Z.to_int n) raw
let alphabet raw=match raw with Json.String "DNA"->Reference_manifest.DNA|Json.String "RNA"->Reference_manifest.RNA|_->Diagnostic.fail "reference_construct" "Invalid construct alphabet."
let require_reference value=require (Pinned_identity.kind value=Pinned_identity.Reference) "A construct reference requires an exact pinned reference identity."
let require_provenance limits values=
  List.iter (fun value->require (List.mem (Pinned_identity.kind value) [Pinned_identity.Source;Pinned_identity.Evidence]) "Boundary provenance must identify a source or review evidence.") values;
  unique limits "provenance identities" (List.map Pinned_identity.fingerprint values)
let parse_text limits profile text =
  let bounds=Codec.limits_json limits in
  let max_bytes=Z.to_int (Json.integer (Json.field "max_bytes" (Json.object_fields bounds)))
  and max_nodes=Z.to_int (Json.integer (Json.field "max_nodes" (Json.object_fields bounds))) in
  Diagnostic.require (String.length text<=max_bytes) "reference_text_limit" "Reference JSON text exceeds its byte bound.";
  Codec.charge limits (16*String.length text+8*max_nodes);
  Legacy_json.parse ~max_bytes ~max_nodes ~profile text

module Sequence_range = struct
  type t={json:Json.t;identity:string;bytes:int;start:Z.t;end_:Z.t}
  let schema_version="biocompiler.sequence_range.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "SequenceRange" ["schema_version";"start";"end";"convention"] raw;
    require ~path (get "schema_version" raw=str schema_version && get "convention" raw=str "zero-based-half-open-reference-5prime-to-3prime.v1") "Unsupported sequence coordinate schema/convention.";
    require (match get "start" raw,get "end" raw with Json.Int start,Json.Int stop->Z.sign start>=0 && Z.compare start stop<=0|_->false) "Sequence coordinates require integers with 0 <= start <= end.";
    let start=Json.integer (get "start" raw) in
    let end_=Json.integer (get "end" raw) in
    require ~path (Z.sign start>=0 && Z.compare start end_<=0) "Sequence coordinates require integers with 0 <= start <= end.";
    let derived_convention=str "zero-based-half-open-reference-5prime-to-3prime.v1" in
    require ~path (same limits (get "convention" raw) derived_convention) "Unsupported sequence coordinate schema/convention.";
    let json=obj ["schema_version",str schema_version;"convention",derived_convention;"start",Json.Int start;"end",Json.Int end_] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;start;end_}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~start ~end_ () =
    let derived_convention=str "zero-based-half-open-reference-5prime-to-3prime.v1" in
    of_json ~limits (obj ["schema_version",str schema_version;"convention",derived_convention;"start",Json.Int start;"end",Json.Int end_])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let start (v:t)=v.start
  let end_ (v:t)=v.end_
  let length (v:t)=Z.sub v.end_ v.start
end
module Reference = struct
  type t={json:Json.t;identity:string;bytes:int;instance_id:string;selection:Reference_components.Selection.t}
  let schema_version="biocompiler.construct_reference.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "ConstructReference" ["schema_version";"instance_id";"selection"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported ConstructReference schema.";
    let selection=Reference_components.Selection.of_json ~limits (get "selection" raw) in
    let instance_id=named ~label:"Reference instance ID" (get "instance_id" raw) in
    let json=obj ["schema_version",str schema_version;"instance_id",str instance_id;"selection",Reference_components.Selection.to_json selection] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;instance_id;selection}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~instance_id ~selection () =
    of_json ~limits (obj ["schema_version",str schema_version;"instance_id",str instance_id;"selection",Reference_components.Selection.to_json selection])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let instance_id (v:t)=v.instance_id
  let selection (v:t)=v.selection
end
module Molecule = struct
  type t={json:Json.t;identity:string;bytes:int;id:string;alphabet:Reference_manifest.alphabet;artifact_class:string;length:Z.t;component_order:string list;topology:topology;completeness:string;unknown_features:string list;compartment:string}
  let schema_version="biocompiler.construct_molecule.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "ConstructMolecule" ["schema_version";"id";"alphabet";"artifact_class";"length";"component_order";"topology";"completeness";"unknown_features";"compartment"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported ConstructMolecule schema.";
    let id=named ~label:"id" (get "id" raw) in
    let artifact_class=named ~label:"artifact_class" (get "artifact_class" raw) in
    let completeness=named ~label:"completeness" (get "completeness" raw) in
    let compartment=named ~label:"compartment" (get "compartment" raw) in
    let alphabet=alphabet (get "alphabet" raw) in
    let topology=topology_of_json (get "topology" raw) in
    require (match get "length" raw with Json.Int value->Z.sign value>0|_->false) "Invalid molecule length.";
    let length=Json.integer (get "length" raw) in
    let component_order=names ~label:"component_order" limits (get "component_order" raw) in
    let unknown_features=names ~label:"unknown_features" limits (get "unknown_features" raw) in
    let json=obj ["schema_version",str schema_version;"id",str id;"alphabet",str (Reference_manifest.alphabet_name alphabet);"artifact_class",str artifact_class;"length",Json.Int length;"component_order",array limits str component_order;"topology",str (topology_name topology);"completeness",str completeness;"unknown_features",array limits str unknown_features;"compartment",str compartment] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;id;alphabet;artifact_class;length;component_order;topology;completeness;unknown_features;compartment}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~id ~alphabet ~artifact_class ~length ~component_order ~topology ~completeness ~unknown_features ~compartment () =
    of_json ~limits (obj ["schema_version",str schema_version;"id",str id;"alphabet",str (Reference_manifest.alphabet_name alphabet);"artifact_class",str artifact_class;"length",Json.Int length;"component_order",array limits str component_order;"topology",str (topology_name topology);"completeness",str completeness;"unknown_features",array limits str unknown_features;"compartment",str compartment])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let id (v:t)=v.id
  let alphabet (v:t)=v.alphabet
  let artifact_class (v:t)=v.artifact_class
  let length (v:t)=v.length
  let component_order (v:t)=v.component_order
  let topology (v:t)=v.topology
  let completeness (v:t)=v.completeness
  let unknown_features (v:t)=v.unknown_features
  let compartment (v:t)=v.compartment
end
module Placement = struct
  type t={json:Json.t;identity:string;bytes:int;instance_id:string;molecule_id:string;component:Component_registry.Component_lock.t;reference:Pinned_identity.t;source_range:Sequence_range.t;molecule_range:Sequence_range.t;orientation:orientation;reading_frame:int option;requirement_ids:string list;source:Behavior.source_location option}
  let schema_version="biocompiler.component_placement.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "ComponentPlacement" ["schema_version";"instance_id";"molecule_id";"component";"reference";"source_range";"molecule_range";"orientation";"reading_frame";"requirement_ids";"source"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported ComponentPlacement schema.";
    let component=legacy limits (fun raw->record_fields ~path:"" "ComponentLock" ["schema_version";"node_id";"component_id";"version";"content_fingerprint"] raw;Component_registry.Component_lock.of_json raw) (get "component" raw) in
    let reference=legacy limits (fun raw->record_fields ~path:"" "PinnedIdentity" ["schema_version";"kind";"id";"version";"content_fingerprint"] raw;Pinned_identity.of_json raw) (get "reference" raw) in
    let source_range=Sequence_range.of_json ~limits (get "source_range" raw) in
    let molecule_range=Sequence_range.of_json ~limits (get "molecule_range" raw) in
    let source=source_of_json ~limits (get "source" raw) in
    let instance_id=named ~label:"Placement instance ID" (get "instance_id" raw) in
    let molecule_id=named ~label:"Placement molecule ID" (get "molecule_id" raw) in
    require_reference reference;
    require ~path (Z.sign (Sequence_range.length source_range)>0 && Z.sign (Sequence_range.length molecule_range)>0) "Component placements require nonempty coordinate ranges.";
    require (List.mem (get "orientation" raw) [str "forward";str "reverse"]) "Invalid placement orientation.";
    let orientation=orientation_of_json (get "orientation" raw) in
    let reading_frame=frame (get "reading_frame" raw) in
    let requirement_ids=names ~label:"Requirement IDs" limits (get "requirement_ids" raw) in
    let json=obj ["schema_version",str schema_version;"instance_id",str instance_id;"molecule_id",str molecule_id;"component",Component_registry.Component_lock.to_json component;"reference",Pinned_identity.to_json reference;"source_range",Sequence_range.to_json source_range;"molecule_range",Sequence_range.to_json molecule_range;"orientation",str (orientation_name orientation);"reading_frame",option_json Json.int reading_frame;"requirement_ids",array limits str requirement_ids;"source",source_to_json source] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;instance_id;molecule_id;component;reference;source_range;molecule_range;orientation;reading_frame;requirement_ids;source}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~instance_id ~molecule_id ~component ~reference ~source_range ~molecule_range ~orientation ~reading_frame ~requirement_ids ~source () =
    of_json ~limits (obj ["schema_version",str schema_version;"instance_id",str instance_id;"molecule_id",str molecule_id;"component",Component_registry.Component_lock.to_json component;"reference",Pinned_identity.to_json reference;"source_range",Sequence_range.to_json source_range;"molecule_range",Sequence_range.to_json molecule_range;"orientation",str (orientation_name orientation);"reading_frame",option_json Json.int reading_frame;"requirement_ids",array limits str requirement_ids;"source",source_to_json source])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let instance_id (v:t)=v.instance_id
  let molecule_id (v:t)=v.molecule_id
  let component (v:t)=v.component
  let reference (v:t)=v.reference
  let source_range (v:t)=v.source_range
  let molecule_range (v:t)=v.molecule_range
  let orientation (v:t)=v.orientation
  let reading_frame (v:t)=v.reading_frame
  let requirement_ids (v:t)=v.requirement_ids
  let source (v:t)=v.source
end
module Feature = struct
  type t={json:Json.t;identity:string;bytes:int;id:string;molecule_id:string;kind:string;range:Sequence_range.t;source_reference:Pinned_identity.t;source_range:Sequence_range.t;source_locator:string;provenance:Pinned_identity.t list;orientation:orientation}
  let schema_version="biocompiler.construct_feature.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "ConstructFeature" ["schema_version";"id";"molecule_id";"kind";"range";"source_reference";"source_range";"source_locator";"provenance";"orientation"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported ConstructFeature schema.";
    let range=Sequence_range.of_json ~limits (get "range" raw) in
    let source_reference=legacy limits (fun raw->record_fields ~path:"" "PinnedIdentity" ["schema_version";"kind";"id";"version";"content_fingerprint"] raw;Pinned_identity.of_json raw) (get "source_reference" raw) in
    let source_range=Sequence_range.of_json ~limits (get "source_range" raw) in
    let provenance=List.map (legacy limits (fun raw->record_fields ~path:"" "PinnedIdentity" ["schema_version";"kind";"id";"version";"content_fingerprint"] raw;Pinned_identity.of_json raw)) (records_input "Construct" (get "provenance" raw)) in
    let id=named ~label:"id" (get "id" raw) in
    let molecule_id=named ~label:"molecule_id" (get "molecule_id" raw) in
    let kind=named ~label:"kind" (get "kind" raw) in
    let source_locator=named ~label:"source_locator" (get "source_locator" raw) in
    require ~path (Z.sign (Sequence_range.length range)>0 && Z.sign (Sequence_range.length source_range)>0) "Features require nonempty coordinate ranges.";
    require_reference source_reference;
    require (List.mem (get "orientation" raw) [str "forward";str "reverse"]) "Invalid feature orientation.";
    let orientation=orientation_of_json (get "orientation" raw) in
    require_provenance limits provenance;
    require ~path (provenance<>[]) "Feature boundaries require pinned provenance.";
    let json=obj ["schema_version",str schema_version;"id",str id;"molecule_id",str molecule_id;"kind",str kind;"range",Sequence_range.to_json range;"source_reference",Pinned_identity.to_json source_reference;"source_range",Sequence_range.to_json source_range;"source_locator",str source_locator;"provenance",array limits Pinned_identity.to_json provenance;"orientation",str (orientation_name orientation)] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;id;molecule_id;kind;range;source_reference;source_range;source_locator;provenance;orientation}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~id ~molecule_id ~kind ~range ~source_reference ~source_range ~source_locator ~provenance ~orientation () =
    of_json ~limits (obj ["schema_version",str schema_version;"id",str id;"molecule_id",str molecule_id;"kind",str kind;"range",Sequence_range.to_json range;"source_reference",Pinned_identity.to_json source_reference;"source_range",Sequence_range.to_json source_range;"source_locator",str source_locator;"provenance",array limits Pinned_identity.to_json provenance;"orientation",str (orientation_name orientation)])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let id (v:t)=v.id
  let molecule_id (v:t)=v.molecule_id
  let kind (v:t)=v.kind
  let range (v:t)=v.range
  let source_reference (v:t)=v.source_reference
  let source_range (v:t)=v.source_range
  let source_locator (v:t)=v.source_locator
  let provenance (v:t)=v.provenance
  let orientation (v:t)=v.orientation
end
module Junction = struct
  type t={json:Json.t;identity:string;bytes:int;id:string;molecule_id:string;left_instance:string;right_instance:string;kind:junction_kind;range:Sequence_range.t;choice:string;provenance:Pinned_identity.t list}
  let schema_version="biocompiler.construct_junction.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "ConstructJunction" ["schema_version";"id";"molecule_id";"left_instance";"right_instance";"kind";"range";"choice";"provenance"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported ConstructJunction schema.";
    let range=Sequence_range.of_json ~limits (get "range" raw) in
    let provenance=List.map (legacy limits (fun raw->record_fields ~path:"" "PinnedIdentity" ["schema_version";"kind";"id";"version";"content_fingerprint"] raw;Pinned_identity.of_json raw)) (records_input "Construct" (get "provenance" raw)) in
    let id=named ~label:"id" (get "id" raw) in
    let molecule_id=named ~label:"molecule_id" (get "molecule_id" raw) in
    let left_instance=named ~label:"left_instance" (get "left_instance" raw) in
    let right_instance=named ~label:"right_instance" (get "right_instance" raw) in
    let choice=named ~label:"choice" (get "choice" raw) in
    let kind=junction_kind_of_json (get "kind" raw) in
    require ~path ((kind=Direct)=(Z.sign (Sequence_range.length range)=0)) "Direct junctions require an empty range; overlaps/gaps require a span.";
    require_provenance limits provenance;
    let json=obj ["schema_version",str schema_version;"id",str id;"molecule_id",str molecule_id;"left_instance",str left_instance;"right_instance",str right_instance;"kind",str (junction_kind_name kind);"range",Sequence_range.to_json range;"choice",str choice;"provenance",array limits Pinned_identity.to_json provenance] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;id;molecule_id;left_instance;right_instance;kind;range;choice;provenance}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~id ~molecule_id ~left_instance ~right_instance ~kind ~range ~choice ~provenance () =
    of_json ~limits (obj ["schema_version",str schema_version;"id",str id;"molecule_id",str molecule_id;"left_instance",str left_instance;"right_instance",str right_instance;"kind",str (junction_kind_name kind);"range",Sequence_range.to_json range;"choice",str choice;"provenance",array limits Pinned_identity.to_json provenance])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let id (v:t)=v.id
  let molecule_id (v:t)=v.molecule_id
  let left_instance (v:t)=v.left_instance
  let right_instance (v:t)=v.right_instance
  let kind (v:t)=v.kind
  let range (v:t)=v.range
  let choice (v:t)=v.choice
  let provenance (v:t)=v.provenance
end
module Regulatory_relationship = struct
  type t={json:Json.t;identity:string;bytes:int;id:string;kind:string;regulator_instance:string;target_instance:string;provenance:Pinned_identity.t list;assumptions:string list}
  let schema_version="biocompiler.construct_regulation.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "RegulatoryRelationship" ["schema_version";"id";"kind";"regulator_instance";"target_instance";"provenance";"assumptions"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported RegulatoryRelationship schema.";
    let provenance=List.map (legacy limits (fun raw->record_fields ~path:"" "PinnedIdentity" ["schema_version";"kind";"id";"version";"content_fingerprint"] raw;Pinned_identity.of_json raw)) (records_input "Construct" (get "provenance" raw)) in
    let id=named ~label:"id" (get "id" raw) in
    let kind=named ~label:"kind" (get "kind" raw) in
    let regulator_instance=named ~label:"regulator_instance" (get "regulator_instance" raw) in
    let target_instance=named ~label:"target_instance" (get "target_instance" raw) in
    require_provenance limits provenance;
    let assumptions=names ~label:"Regulatory assumptions" limits (get "assumptions" raw) in
    let json=obj ["schema_version",str schema_version;"id",str id;"kind",str kind;"regulator_instance",str regulator_instance;"target_instance",str target_instance;"provenance",array limits Pinned_identity.to_json provenance;"assumptions",array limits str assumptions] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;id;kind;regulator_instance;target_instance;provenance;assumptions}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~id ~kind ~regulator_instance ~target_instance ~provenance ~assumptions () =
    of_json ~limits (obj ["schema_version",str schema_version;"id",str id;"kind",str kind;"regulator_instance",str regulator_instance;"target_instance",str target_instance;"provenance",array limits Pinned_identity.to_json provenance;"assumptions",array limits str assumptions])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let id (v:t)=v.id
  let kind (v:t)=v.kind
  let regulator_instance (v:t)=v.regulator_instance
  let target_instance (v:t)=v.target_instance
  let provenance (v:t)=v.provenance
  let assumptions (v:t)=v.assumptions
end
module Dependency = struct
  type t={json:Json.t;identity:string;bytes:int;id:string;consumer_molecule:string;provider_molecule:string;kind:dependency_kind;assumption:string;requirement_ids:string list}
  let schema_version="biocompiler.construct_dependency.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "ConstructDependency" ["schema_version";"id";"consumer_molecule";"provider_molecule";"kind";"assumption";"requirement_ids"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported ConstructDependency schema.";
    let id=named ~label:"id" (get "id" raw) in
    let consumer_molecule=named ~label:"consumer_molecule" (get "consumer_molecule" raw) in
    let provider_molecule=named ~label:"provider_molecule" (get "provider_molecule" raw) in
    let assumption=named ~label:"assumption" (get "assumption" raw) in
    let kind=dependency_kind_of_json (get "kind" raw) in
    let requirement_ids=names ~label:"Requirement IDs" limits (get "requirement_ids" raw) in
    let json=obj ["schema_version",str schema_version;"id",str id;"consumer_molecule",str consumer_molecule;"provider_molecule",str provider_molecule;"kind",str (dependency_kind_name kind);"assumption",str assumption;"requirement_ids",array limits str requirement_ids] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    {json;identity=Canonical.sha256 encoded;bytes=String.length encoded;id;consumer_molecule;provider_molecule;kind;assumption;requirement_ids}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~id ~consumer_molecule ~provider_molecule ~kind ~assumption ~requirement_ids () =
    of_json ~limits (obj ["schema_version",str schema_version;"id",str id;"consumer_molecule",str consumer_molecule;"provider_molecule",str provider_molecule;"kind",str (dependency_kind_name kind);"assumption",str assumption;"requirement_ids",array limits str requirement_ids])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let id (v:t)=v.id
  let consumer_molecule (v:t)=v.consumer_molecule
  let provider_molecule (v:t)=v.provider_molecule
  let kind (v:t)=v.kind
  let assumption (v:t)=v.assumption
  let requirement_ids (v:t)=v.requirement_ids
end
module Evidence_policy = struct
  type t={json:Json.t;identity:string;bytes:int;semantic_properties:string list;invalidated_analyses:string list}
  let schema_version="biocompiler.construct_evidence_policy.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "LayoutEvidencePolicy" ["schema_version";"semantic_properties";"invalidated_analyses"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported LayoutEvidencePolicy schema.";
    let semantic_properties=names ~label:"semantic_properties" limits (get "semantic_properties" raw) in
    let invalidated_analyses=names ~label:"invalidated_analyses" limits (get "invalidated_analyses" raw) in
    require ~path (semantic_properties=["membership";"order";"orientation";"boundaries";"junctions";"reading_frame";"regulation";"localization";"payload_partitioning"] && invalidated_analyses=["composition";"behavior"]) "Construct evidence invalidation policy cannot be weakened or replaced.";
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
  let default ?(limits=default_limits) ()=make ~limits ~semantic_properties:["membership";"order";"orientation";"boundaries";"junctions";"reading_frame";"regulation";"localization";"payload_partitioning"] ~invalidated_analyses:["composition";"behavior"] ()
end
module Request = struct
  type t={layout_identity:string;json:Json.t;identity:string;bytes:int;composition:Composition.t;references:Reference.t list;molecules:Molecule.t list;placements:Placement.t list;features:Feature.t list;junctions:Junction.t list;regulatory_relations:Regulatory_relationship.t list;dependencies:Dependency.t list;assumptions:string list;source_request_fingerprint:string option;evidence_policy:Evidence_policy.t}
  let schema_version="biocompiler.construct_request.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "ConstructRequest" ["schema_version";"composition";"references";"molecules";"placements";"features";"junctions";"regulatory_relations";"dependencies";"assumptions";"source_request_fingerprint";"evidence_policy";"target";"nodes"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported ConstructRequest schema.";
    let composition=legacy limits (fun raw->record_fields ~path:"" "CompositionRequest" ["schema_version";"target";"registry_lock";"instances";"connections";"providers";"dependency_bindings";"resource_pools";"resource_bindings";"requirement_ids"] raw;Composition.of_json raw) (get "composition" raw) in
    let references=List.map (Reference.of_json ~limits) (records_input "Construct" (get "references" raw)) in
    let molecules=List.map (Molecule.of_json ~limits) (records_input "Construct" (get "molecules" raw)) in
    let placements=List.map (Placement.of_json ~limits) (records_input "Construct" (get "placements" raw)) in
    let features=List.map (Feature.of_json ~limits) (records_input "Construct" (get "features" raw)) in
    let junctions=List.map (Junction.of_json ~limits) (records_input "Construct" (get "junctions" raw)) in
    let regulatory_relations=List.map (Regulatory_relationship.of_json ~limits) (records_input "Construct" (get "regulatory_relations" raw)) in
    let dependencies=List.map (Dependency.of_json ~limits) (records_input "Construct" (get "dependencies" raw)) in
    let evidence_policy=Evidence_policy.of_json ~limits (get "evidence_policy" raw) in
    unique limits "construct reference instance IDs" (List.map Reference.instance_id references);
    let source_request_fingerprint=option (hash ~label:"Source request") (get "source_request_fingerprint" raw) in
    unique limits "construct molecules IDs" (List.map Molecule.id molecules);
    unique limits "construct placements IDs" (List.map Placement.instance_id placements);
    unique limits "construct features IDs" (List.map Feature.id features);
    unique limits "construct junctions IDs" (List.map Junction.id junctions);
    unique limits "construct regulatory_relations IDs" (List.map Regulatory_relationship.id regulatory_relations);
    unique limits "construct dependencies IDs" (List.map Dependency.id dependencies);
    let assumptions=names ~label:"Assumptions" limits (get "assumptions" raw) in
    let derived_target=Build_request.Target.to_json (Composition.target composition) in
    require ~path (same limits (get "target" raw) derived_target) "Derived construct target differs from its authority.";
    let derived_nodes=array limits (fun item->obj ["id",str (Composition.Instance.id item);"kind",str "component_instance"]) (Composition.instances composition) in
    require ~path (same limits (get "nodes" raw) derived_nodes) "Derived construct nodes differs from its authority.";
    let json=obj ["schema_version",str schema_version;"composition",Composition.to_json composition;"references",array limits Reference.to_json references;"molecules",array limits Molecule.to_json molecules;"placements",array limits Placement.to_json placements;"features",array limits Feature.to_json features;"junctions",array limits Junction.to_json junctions;"regulatory_relations",array limits Regulatory_relationship.to_json regulatory_relations;"dependencies",array limits Dependency.to_json dependencies;"assumptions",array limits str assumptions;"source_request_fingerprint",option_json str source_request_fingerprint;"evidence_policy",Evidence_policy.to_json evidence_policy;"target",derived_target;"nodes",derived_nodes] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    let layout_identity=Codec.fingerprint ~limits (obj (List.map (fun key->key,get key json) ["molecules";"placements";"features";"junctions";"regulatory_relations";"dependencies";"assumptions";"evidence_policy"])) in
    {layout_identity;json;identity=Canonical.sha256 encoded;bytes=String.length encoded;composition;references;molecules;placements;features;junctions;regulatory_relations;dependencies;assumptions;source_request_fingerprint;evidence_policy}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~composition ~references ~molecules ~placements ~features ~junctions ~regulatory_relations ~dependencies ~assumptions ~source_request_fingerprint ~evidence_policy () =
    let derived_target=Build_request.Target.to_json (Composition.target composition) in
    let derived_nodes=array limits (fun item->obj ["id",str (Composition.Instance.id item);"kind",str "component_instance"]) (Composition.instances composition) in
    of_json ~limits (obj ["schema_version",str schema_version;"composition",Composition.to_json composition;"references",array limits Reference.to_json references;"molecules",array limits Molecule.to_json molecules;"placements",array limits Placement.to_json placements;"features",array limits Feature.to_json features;"junctions",array limits Junction.to_json junctions;"regulatory_relations",array limits Regulatory_relationship.to_json regulatory_relations;"dependencies",array limits Dependency.to_json dependencies;"assumptions",array limits str assumptions;"source_request_fingerprint",option_json str source_request_fingerprint;"evidence_policy",Evidence_policy.to_json evidence_policy;"target",derived_target;"nodes",derived_nodes])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let composition (v:t)=v.composition
  let references (v:t)=v.references
  let molecules (v:t)=v.molecules
  let placements (v:t)=v.placements
  let features (v:t)=v.features
  let junctions (v:t)=v.junctions
  let regulatory_relations (v:t)=v.regulatory_relations
  let dependencies (v:t)=v.dependencies
  let assumptions (v:t)=v.assumptions
  let source_request_fingerprint (v:t)=v.source_request_fingerprint
  let evidence_policy (v:t)=v.evidence_policy
  let layout_json (v:t)=obj (List.map (fun key->key,get key v.json) ["molecules";"placements";"features";"junctions";"regulatory_relations";"dependencies";"assumptions";"evidence_policy"])
  let layout_fingerprint (v:t)=v.layout_identity
  let target (v:t)=Composition.target v.composition
  let registry_lock (v:t)=Composition.registry_lock v.composition
end
module Candidate = struct
  type t={layout_identity:string;json:Json.t;identity:string;bytes:int;request_fingerprint:string;composition_fingerprint:string;registry_lock:Component_registry.Lock.t;molecules:Molecule.t list;placements:Placement.t list;features:Feature.t list;junctions:Junction.t list;regulatory_relations:Regulatory_relationship.t list;dependencies:Dependency.t list;assumptions:string list;evidence_policy:Evidence_policy.t}
  let schema_version="biocompiler.construct.v0.1"
  let of_json ?(limits=default_limits) ?(path="") raw=
    Codec.preflight ~limits ~path raw;
    record_fields ~path "ConstructCandidate" ["schema_version";"request_fingerprint";"composition_fingerprint";"registry_lock";"molecules";"placements";"features";"junctions";"regulatory_relations";"dependencies";"assumptions";"evidence_policy";"nodes"] raw;
    require ~path (get "schema_version" raw=str schema_version) "Unsupported ConstructCandidate schema.";
    let registry_lock=legacy limits (fun raw->record_fields ~path:"" "RegistryLock" ["schema_version";"registry_id";"registry_version";"registry_fingerprint";"components";"identities"] raw;Component_registry.Lock.of_json raw) (get "registry_lock" raw) in
    let molecules=List.map (Molecule.of_json ~limits) (records_input "Construct" (get "molecules" raw)) in
    let placements=List.map (Placement.of_json ~limits) (records_input "Construct" (get "placements" raw)) in
    let features=List.map (Feature.of_json ~limits) (records_input "Construct" (get "features" raw)) in
    let junctions=List.map (Junction.of_json ~limits) (records_input "Construct" (get "junctions" raw)) in
    let regulatory_relations=List.map (Regulatory_relationship.of_json ~limits) (records_input "Construct" (get "regulatory_relations" raw)) in
    let dependencies=List.map (Dependency.of_json ~limits) (records_input "Construct" (get "dependencies" raw)) in
    let evidence_policy=Evidence_policy.of_json ~limits (get "evidence_policy" raw) in
    let request_fingerprint=hash ~label:"Construct request" (get "request_fingerprint" raw) in
    let composition_fingerprint=hash ~label:"Composition request" (get "composition_fingerprint" raw) in
    unique limits "construct molecules IDs" (List.map Molecule.id molecules);
    unique limits "construct placements IDs" (List.map Placement.instance_id placements);
    unique limits "construct features IDs" (List.map Feature.id features);
    unique limits "construct junctions IDs" (List.map Junction.id junctions);
    unique limits "construct regulatory_relations IDs" (List.map Regulatory_relationship.id regulatory_relations);
    unique limits "construct dependencies IDs" (List.map Dependency.id dependencies);
    let assumptions=names ~label:"Assumptions" limits (get "assumptions" raw) in
    let derived_nodes=array limits (fun item->obj ["id",str (Placement.instance_id item);"kind",str "component_placement"]) placements in
    require ~path (same limits (get "nodes" raw) derived_nodes) "Derived construct nodes differs from its authority.";
    let json=obj ["schema_version",str schema_version;"request_fingerprint",str request_fingerprint;"composition_fingerprint",str composition_fingerprint;"registry_lock",Component_registry.Lock.to_json registry_lock;"molecules",array limits Molecule.to_json molecules;"placements",array limits Placement.to_json placements;"features",array limits Feature.to_json features;"junctions",array limits Junction.to_json junctions;"regulatory_relations",array limits Regulatory_relationship.to_json regulatory_relations;"dependencies",array limits Dependency.to_json dependencies;"assumptions",array limits str assumptions;"evidence_policy",Evidence_policy.to_json evidence_policy;"nodes",derived_nodes] in
    let encoded=Codec.encode ~limits json in Codec.charge limits (String.length encoded);
    let layout_identity=Codec.fingerprint ~limits (obj (List.map (fun key->key,get key json) ["molecules";"placements";"features";"junctions";"regulatory_relations";"dependencies";"assumptions";"evidence_policy"])) in
    {layout_identity;json;identity=Canonical.sha256 encoded;bytes=String.length encoded;request_fingerprint;composition_fingerprint;registry_lock;molecules;placements;features;junctions;regulatory_relations;dependencies;assumptions;evidence_policy}
  let of_json_text ?(limits=default_limits) ?(path="") text=of_json ~limits ~path (parse_text limits Legacy_json.Artifact text)
  let make ?(limits=default_limits) ~request_fingerprint ~composition_fingerprint ~registry_lock ~molecules ~placements ~features ~junctions ~regulatory_relations ~dependencies ~assumptions ~evidence_policy () =
    let derived_nodes=array limits (fun item->obj ["id",str (Placement.instance_id item);"kind",str "component_placement"]) placements in
    of_json ~limits (obj ["schema_version",str schema_version;"request_fingerprint",str request_fingerprint;"composition_fingerprint",str composition_fingerprint;"registry_lock",Component_registry.Lock.to_json registry_lock;"molecules",array limits Molecule.to_json molecules;"placements",array limits Placement.to_json placements;"features",array limits Feature.to_json features;"junctions",array limits Junction.to_json junctions;"regulatory_relations",array limits Regulatory_relationship.to_json regulatory_relations;"dependencies",array limits Dependency.to_json dependencies;"assumptions",array limits str assumptions;"evidence_policy",Evidence_policy.to_json evidence_policy;"nodes",derived_nodes])
  let to_json (v:t)=v.json
  let fingerprint (v:t)=v.identity
  let canonical_size (v:t)=v.bytes
  let request_fingerprint (v:t)=v.request_fingerprint
  let composition_fingerprint (v:t)=v.composition_fingerprint
  let registry_lock (v:t)=v.registry_lock
  let molecules (v:t)=v.molecules
  let placements (v:t)=v.placements
  let features (v:t)=v.features
  let junctions (v:t)=v.junctions
  let regulatory_relations (v:t)=v.regulatory_relations
  let dependencies (v:t)=v.dependencies
  let assumptions (v:t)=v.assumptions
  let evidence_policy (v:t)=v.evidence_policy
  let layout_json (v:t)=obj (List.map (fun key->key,get key v.json) ["molecules";"placements";"features";"junctions";"regulatory_relations";"dependencies";"assumptions";"evidence_policy"])
  let layout_fingerprint (v:t)=v.layout_identity
end
