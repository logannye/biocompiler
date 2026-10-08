open Bioc_wire
open Bioc_domain
module B = Reference_producer_budget
module C = Reference_construct
module M = Reference_molecular
module R = Reference_manifest
module E = Reference_construct_evidence

let emitter_version = "biocompiler.reference_sequence_emitter.v0.2"
type limits = B.limits
let make_limits = B.make_limits
let default_limits = B.default_limits
let limits_json = B.limits_json
let fail message = Diagnostic.fail "reference_sequence_emitter" message
let one = function [value] -> value | _ -> fail "Checked reference emission lost its single-CDS layout."
let emit ?(limits=default_limits) ?parent ~request ~construct ~registry ~manifests () =
  let budget=B.create ?parent limits in
  List.iter (B.input budget) [C.Request.to_json request;C.Candidate.to_json construct;
    Component_registry.to_json registry];
  let seen=Hashtbl.create 8 in
  (* Charge and reserve before each list step, so even a cyclic native list
     cannot escape the same finite lifetime budget. No manifest is promoted. *)
  let rec reserve_manifests = function
    | [] -> ()
    | (id,manifest)::rest ->
        B.charge budget (String.length id+1);
        B.input budget (Json.Object [id,R.to_json manifest]);
        Diagnostic.require (not (Hashtbl.mem seen id)) "reference_sequence_emitter"
          "Reference manifest keys must be unique.";
        Hashtbl.add seen id manifest;reserve_manifests rest in
  reserve_manifests manifests;
  let checked=Bioc_checker.Reference_construct_check.check ~parent:(B.work budget)
      ~limits:(B.checker_limits limits)
      ~request ~candidate:construct ~registry ~manifests () in
  if not (E.Result.passed checked) then begin
    let codes=List.map E.Diagnostic.code (E.Result.diagnostics checked) in
    B.charge budget (E.Result.canonical_size checked+1);
    fail ("Exact reference emission requires a currently passing construct check: "^
      String.concat "; " codes)
  end;
  let selection=C.Reference.selection (one (C.Request.references request)) in
  let selected_id=Pinned_identity.id (Reference_components.Selection.manifest selection) in
  let manifest=match Hashtbl.find_opt seen selected_id with
    | Some value -> value | None -> fail "Checked reference emission lost its selected manifest." in
  let reference=R.record manifest (Pinned_identity.id (Reference_components.Selection.reference selection)) in
  let molecule=one (C.Candidate.molecules construct) and placement=one (C.Candidate.placements construct) in
  let sequence=R.Record.sequence reference in
  B.charge budget (String.length sequence+1);
  let sequence_sha256=Canonical.sha256 sequence in
  let codec=B.codec budget in
  let record=M.Record.make ~limits:codec ~id:(C.Molecule.id molecule)
      ~instance_id:(C.Placement.instance_id placement) ~molecule_id:(C.Molecule.id molecule)
      ~alphabet:(R.Record.alphabet reference) ~artifact_class:(R.Record.artifact_class reference)
      ~sequence ~sequence_sha256 ~component:(C.Placement.component placement) ~reference_selection:selection
      ~source_range:(C.Placement.source_range placement) ~molecule_range:(C.Placement.molecule_range placement)
      ~features:(C.Candidate.features construct) ~feature_statuses:(M.reference_feature_statuses ~limits:codec reference)
      ~orientation:(C.Placement.orientation placement) ~reading_frame:(C.Placement.reading_frame placement)
      ~translation_policy:(M.Translation_policy.default ~limits:codec ())
      ~completeness:(R.Record.completeness reference) ~unknown_features:(R.Record.unknown_features reference)
      ~evidence_relationships:(R.Record.evidence_relationships reference)
      ~requirement_ids:(C.Placement.requirement_ids placement) ~source:(C.Placement.source placement) () in
  let profile=match R.Record.alphabet reference with
    | R.DNA -> M.Dna_cds | R.RNA -> M.Rna_cds
    | R.Protein -> fail "Checked reference emission selected a protein instead of a nucleotide CDS." in
  let artifact=M.Artifact.make ~limits:codec ~request_fingerprint:(C.Request.fingerprint request)
      ~construct_fingerprint:(C.Candidate.fingerprint construct) ~layout_fingerprint:(C.Candidate.layout_fingerprint construct)
      ~registry_lock:(C.Candidate.registry_lock construct) ~profile ~records:[record]
      ~encoding_policy:(M.Encoding_policy.default ~limits:codec ())
      ~evidence_policy:(M.Evidence_policy.default ~limits:codec ()) ~changes:[]
      ~source_request_fingerprint:(C.Request.source_request_fingerprint request) ~artifact_scope:"exact_cds" () in
  B.output budget (M.Artifact.to_json artifact);artifact
