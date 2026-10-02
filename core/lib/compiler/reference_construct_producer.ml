open Bioc_wire
open Bioc_domain
module B = Reference_producer_budget
module C = Reference_construct
module R = Reference_manifest
module A = Reference_components
module Names = Set.Make(String)

let generator_version = "biocompiler.reference_construct_generator.v0.1"
type limits = B.limits
let make_limits = B.make_limits
let default_limits = B.default_limits
let limits_json = B.limits_json
let require condition message = Diagnostic.require condition "reference_construct_producer" message
let single_message = "The reference construct profile supports one component on one molecule."
let single = function [value] -> value | _ -> Diagnostic.fail "reference_construct_producer" single_message
let rec height count = if count<=1 then 1 else 1+height (count/2)
let names budget values =
  let factor=1+height (List.length values) in
  List.fold_left (fun result value -> B.charge_product budget (String.length value+1) factor;
    Names.add value result) Names.empty values
let require_name budget value =
  B.charge budget (String.length value+1);
  (* Python str.strip() recognizes Unicode White_Space plus U+001C..001F.
     This is a declaration check, without trimming or rewriting the ID. *)
  let whitespace n = (n>=9 && n<=13) || (n>=28 && n<=32) ||
    (n>=0x2000 && n<=0x200a) ||
    List.mem n [0x85;0xa0;0x1680;0x2028;0x2029;0x202f;0x205f;0x3000] in
  let rec named offset =
    if offset>=String.length value then false else
      let decoded=String.get_utf_8_uchar value offset in
      not (whitespace (Uchar.to_int (Uchar.utf_decode_uchar decoded))) ||
      named (offset+Uchar.utf_decode_length decoded) in
  require (named 0) "Molecule ID must be a nonempty string."
let no_composition_extras composition =
  Composition.connections composition=[] && Composition.providers composition=[] &&
  Composition.dependency_bindings composition=[] && Composition.resource_pools composition=[] &&
  Composition.resource_bindings composition=[]

let prepare ?(limits=default_limits) ?parent ?(molecule_id="reference_cds")
    ?source_request_fingerprint ~manifest ~selection ~composition ~registry () =
  let budget=B.create ?parent limits in
  List.iter (B.input budget) [R.to_json manifest;A.Selection.to_json selection;
    Composition.to_json composition;Component_registry.to_json registry;
    Json.Object ["molecule_id",Json.String molecule_id;"source_request_fingerprint",
      (match source_request_fingerprint with None->Json.Null|Some value->Json.String value)]];
  require_name budget molecule_id;
  require (source_request_fingerprint=None || source_request_fingerprint=Some (Composition.fingerprint composition))
    "Reference constructs use the current composition as source authority.";
  let instance=single (Composition.instances composition) in
  require (no_composition_extras composition)
    "The reference construct profile does not support additional dependencies or resources.";
  require (Composition.Instance.placement instance=Composition.Instance.Encoded_here)
    "The reference construct profile does not support co-payload assembly.";
  require (Names.equal (names budget (Composition.Instance.requirement_ids instance))
      (names budget (Composition.requirement_ids composition)))
    "The selected reference component must retain every source requirement.";
  let expected=A.adapt_reference_component ~limits:(B.codec budget) manifest selection in
  (* Resolution traverses the complete registry and lock. Reserve conservative
     comparison work before its identity checks, independently of its result. *)
  B.charge_product budget (Component_registry.canonical_size registry+
    Component_registry.Lock.canonical_size (Composition.registry_lock composition)+1)
    (2+height (List.length (Component_registry.components registry)));
  let records=Component_registry.resolve registry (Composition.registry_lock composition) in
  let instance_id=Composition.Instance.id instance in
  let same_record=match records with
    | [id,record] -> id=instance_id && Component.fingerprint record=Component.fingerprint expected
    | _ -> false in
  let same_lock=match Component_registry.Lock.components (Composition.registry_lock composition) with
    | [lock] -> Component_registry.Component_lock.fingerprint lock=
        Component_registry.Component_lock.fingerprint (Composition.Instance.component instance)
    | _ -> false in
  require (same_record && same_lock)
    "The selected component must exactly match the independently pinned CDS reference.";
  let record=R.record manifest (Pinned_identity.id (A.Selection.reference selection)) in
  require (Build_request.Target.payload_format (Composition.target composition)=R.alphabet_name (R.Record.alphabet record))
    "Reference alphabet must match the frozen target modality.";
  require (Component_contract.Operating_domain.constraints (Composition.Instance.required_domain instance)=[])
    "The CDS reference supplies no molecular operating-domain contract.";
  let codec=B.codec budget in
  let molecule=C.Molecule.make ~limits:codec ~id:molecule_id ~alphabet:(R.Record.alphabet record)
      ~artifact_class:(R.Record.artifact_class record) ~length:(Z.of_int (R.Record.length record))
      ~component_order:[instance_id] ~topology:C.Unspecified ~completeness:(R.Record.completeness record)
      ~unknown_features:(R.Record.unknown_features record) ~compartment:"unspecified" () in
  let range=C.Sequence_range.make ~limits:codec ~start:Z.zero ~end_:(Z.of_int (R.Record.length record)) () in
  let placement=C.Placement.make ~limits:codec ~instance_id ~molecule_id
      ~component:(Composition.Instance.component instance) ~reference:(A.Selection.reference selection)
      ~source_range:range ~molecule_range:range ~orientation:C.Forward ~reading_frame:(Some 0)
      ~requirement_ids:(Composition.Instance.requirement_ids instance) ~source:(Composition.Instance.source instance) () in
  let request=C.Request.make ~limits:codec ~composition
      ~references:[C.Reference.make ~limits:codec ~instance_id ~selection ()]
      ~molecules:[molecule] ~placements:[placement] ~features:[] ~junctions:[]
      ~regulatory_relations:[] ~dependencies:[] ~assumptions:(Component.assumptions expected)
      ~source_request_fingerprint:(Some (Composition.fingerprint composition))
      ~evidence_policy:(C.Evidence_policy.default ~limits:codec ()) () in
  B.output budget (C.Request.to_json request);request

let generate ?(limits=default_limits) ?parent request =
  let budget=B.create ?parent limits in
  B.input budget (C.Request.to_json request);
  let molecule=single (C.Request.molecules request) and placement=single (C.Request.placements request) in
  ignore (single (C.Request.references request));
  let composition=C.Request.composition request in
  let instance=single (Composition.instances composition) in
  require (C.Request.features request=[] && C.Request.junctions request=[] &&
      C.Request.regulatory_relations request=[] && C.Request.dependencies request=[] &&
      no_composition_extras composition)
    "Subfeatures, junctions, regulatory layouts and co-payloads require a separate assembly profile.";
  let full_range range=Z.equal (C.Sequence_range.start range) Z.zero &&
      Z.equal (C.Sequence_range.end_ range) (C.Molecule.length molecule) in
  require (full_range (C.Placement.source_range placement) && full_range (C.Placement.molecule_range placement) &&
      C.Placement.orientation placement=C.Forward && C.Placement.reading_frame placement=Some 0 &&
      C.Molecule.component_order molecule=[C.Placement.instance_id placement] &&
      C.Molecule.topology molecule=C.Unspecified && C.Molecule.completeness molecule="CDS-reference-only" &&
      C.Molecule.compartment molecule="unspecified")
    "The reference construct profile requires one complete forward CDS in frame zero with unknown delivered context.";
  require (Composition.Instance.placement instance=Composition.Instance.Encoded_here &&
      (C.Request.source_request_fingerprint request=None ||
       C.Request.source_request_fingerprint request=Some (Composition.fingerprint composition)))
    "Reference constructs must retain their encoded component source authority.";
  let candidate=C.Candidate.make ~limits:(B.codec budget)
      ~request_fingerprint:(C.Request.fingerprint request) ~composition_fingerprint:(Composition.fingerprint composition)
      ~registry_lock:(Composition.registry_lock composition) ~molecules:(C.Request.molecules request)
      ~placements:(C.Request.placements request) ~features:(C.Request.features request)
      ~junctions:(C.Request.junctions request) ~regulatory_relations:(C.Request.regulatory_relations request)
      ~dependencies:(C.Request.dependencies request) ~assumptions:(C.Request.assumptions request)
      ~evidence_policy:(C.Request.evidence_policy request) () in
  B.output budget (C.Candidate.to_json candidate);candidate
