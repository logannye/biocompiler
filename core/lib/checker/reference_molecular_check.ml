open Bioc_wire
open Bioc_domain
module R=Reference_check_support
module C=Reference_construct
module Q=Reference_molecular
module E=Reference_molecular_evidence
module F=Reference_manifest
module M=Map.Make(String)
type limits=R.limits
let make_limits=R.make_limits
let default_limits=R.default_limits
let limits_json=R.limits_json
let checker_version=E.checker_version
let implementation_version="biocompiler.ocaml.reference_molecular_check.v0.1"
let str=R.str
let field=R.field
let text=R.text
let construct_limits limits=
  let raw=limits_json limits in
  let n key=Z.to_int(Json.integer(field key raw)) in
  Reference_construct_check.make_limits ~max_work:(n "max_work") ~max_items:(n "max_retained_intermediate_items")
    ~max_input_bytes:(n "max_input_bytes") ~max_report_bytes:(n "max_report_bytes") ~max_report_nodes:(n "max_report_nodes") ()
let prepare budget request construct candidate registry manifests=
  let references=R.manifests budget manifests in
  R.prepare budget [C.Request.canonical_size request,C.Request.to_json request;
    C.Candidate.canonical_size construct,C.Candidate.to_json construct;
    Q.Artifact.canonical_size candidate,Q.Artifact.to_json candidate;
    Component_registry.canonical_size registry,Component_registry.to_json registry;
    List.fold_left(fun n(_,value)->n+F.canonical_size value)0 manifests,
      Json.Object(List.map(fun(key,value)->key,F.to_json value)manifests)];references
let dependency_values budget request construct candidate registry references=
  let composition=C.Request.composition request and raw=Q.Artifact.to_json candidate in
  E.Dependencies.of_json ~limits:(R.codec budget)(Json.Object[
    "request",str(C.Request.fingerprint request);"construct",str(C.Candidate.fingerprint construct);
    "layout",str(C.Candidate.layout_fingerprint construct);"candidate",str(Q.Artifact.fingerprint candidate);
    "registry",str(Component_registry.fingerprint registry);"registry_lock",str(Component_registry.Lock.fingerprint(Composition.registry_lock composition));
    "target",str(Build_request.Target.fingerprint(Composition.target composition));
    "profile",str(R.fingerprint budget(Json.Object(List.map(fun key->key,field key raw)["schema_version";"profile";"artifact_scope"])));
    "encoding_policy",str(Q.Encoding_policy.fingerprint(Q.Artifact.encoding_policy candidate));
    "evidence_policy",str(Q.Evidence_policy.fingerprint(Q.Artifact.evidence_policy candidate));"references",references;
    "checker",str checker_version;"admission_policy",str "biocompiler.human_admission_policy.v0.1";
    "construct_checker",str Reference_construct_check.checker_version])
let dependencies ?parent ?(limits=default_limits) ~request ~construct ~candidate ~registry ~manifests ()=
  let budget=R.create ?parent limits in let refs=prepare budget request construct candidate registry manifests in
  let result=dependency_values budget request construct candidate registry refs in R.reserve budget(E.Dependencies.to_json result);result
let map budget key values=List.fold_left(fun result value->R.keep budget 1;let id=key value in
    R.charge budget((String.length id+1)*(M.cardinal result+1));M.add id value result)M.empty values
let check ?parent ?(limits=default_limits) ~request ~construct ~candidate ~registry ~manifests ()=
  let budget=R.create ?parent limits in let refs=prepare budget request construct candidate registry manifests in
  let dependencies=dependency_values budget request construct candidate registry refs in
  let upstream=Reference_construct_check.check ~parent:(R.work budget) ~limits:(construct_limits limits)
    ~request ~candidate:construct ~registry ~manifests () in
  let diagnostics=ref [] and checks=ref [] in
  List.iter(fun value->
    let raw=Reference_construct_evidence.Diagnostic.to_json value in
    let fields=Json.object_fields raw|>List.map(fun(key,value)->if key="code" then key,str("construct:"^Json.string value) else key,value) in
    let diagnostic=E.Diagnostic.of_json ~limits:(R.codec budget)(Json.Object(("record_id",Json.Null)::fields)) in
    R.keep budget 1;R.reserve budget(E.Diagnostic.to_json diagnostic);diagnostics:=diagnostic::!diagnostics)
    (Reference_construct_evidence.Result.diagnostics upstream);
  let placements=map budget C.Placement.instance_id(C.Candidate.placements construct)
  and selections=map budget C.Reference.instance_id(C.Request.references request)
  and molecules=map budget C.Molecule.id(C.Candidate.molecules construct) in
  let requirement_ids=Composition.requirement_ids(C.Request.composition request) in
  let diagnostic status code message record=
    let placement=Option.bind record(fun value->M.find_opt(Q.Record.instance_id value)placements) in
    let requirements=match placement with Some value->C.Placement.requirement_ids value|None->requirement_ids in
    let value=E.Diagnostic.make ~limits:(R.codec budget) ~status ~code ~message
      ?record_id:(Option.map Q.Record.id record) ?instance_id:(Option.map Q.Record.instance_id record)
      ?molecule_id:(Option.map Q.Record.molecule_id record) ~requirement_ids:requirements
      ?source:(Option.bind placement C.Placement.source) () in
    R.reserve budget(E.Diagnostic.to_json value);R.keep budget 1;diagnostics:=value::!diagnostics in
  let comparison record check passed expected_fingerprint actual_fingerprint message=
    let value=E.Comparison.make ~limits:(R.codec budget) ~record_id:(Q.Record.id record) ~check
      ~outcome:(if passed then E.Pass else E.Fail) ~expected_fingerprint ~actual_fingerprint ~message () in
    R.reserve budget(E.Comparison.to_json value);R.keep budget 1;checks:=value::!checks;
    if not passed then diagnostic E.Fail check message(Some record) in
  let raw=Q.Artifact.to_json candidate and request_raw=C.Request.to_json request in
  List.iter(fun(code,actual,expected)->if not(R.equal budget actual expected) then diagnostic E.Fail code
    ("Molecular artifact changed its authoritative "^String.map(function '_'->' '|c->c)code^".")None)
    ["request_identity",field "request_fingerprint" raw,str(C.Request.fingerprint request);
     "construct_identity",field "construct_fingerprint" raw,str(C.Candidate.fingerprint construct);
     "layout_identity",field "layout_fingerprint" raw,str(C.Candidate.layout_fingerprint construct);
     "registry_lock",field "registry_lock" raw,Component_registry.Lock.to_json(C.Request.registry_lock request);
     "source_request",field "source_request_fingerprint" raw,field "source_request_fingerprint" request_raw];
  if text "profile" raw<>Build_request.Target.payload_format(C.Request.target request)^"-CDS" || text "artifact_scope" raw<>"exact_cds"
  then diagnostic E.Fail "output_profile" "The molecular profile must reproduce only the selected target's coding reference." None;
  if Q.Artifact.changes candidate<>[] then diagnostic E.Unsupported "encoding_changes"
    "Exact-reference reproduction disables sequence optimization and all encoding transformations; a change record does not preserve prior acceptance." None;
  if List.length(Q.Artifact.records candidate)<>1 || not(R.same_set budget(List.map Q.Record.instance_id(Q.Artifact.records candidate))(List.map fst(M.bindings placements)))
  then diagnostic E.Fail "record_inventory" "Molecular records must cover exactly the accepted single selected CDS instance." None;
  List.iter(fun record->R.charge budget 1;
    let raw=Q.Record.to_json record and instance_id=Q.Record.instance_id record in
    match M.find_opt instance_id placements,M.find_opt instance_id selections,M.find_opt(Q.Record.molecule_id record)molecules with
    |Some placement,Some selected,Some molecule->
      let diagnostic status code message=diagnostic status code message(Some record) in
      let placed=C.Placement.to_json placement and selection=C.Reference.selection selected in
      if Q.Record.id record<>C.Molecule.id molecule || Q.Record.molecule_id record<>C.Placement.molecule_id placement then
        diagnostic E.Fail "record_membership" "Record identity and molecule membership must identify the accepted construct molecule.";
      if not(R.equal budget(field "component" raw)(field "component" placed))
        || not(R.equal budget(field "reference_selection" raw)(Reference_components.Selection.to_json selection)) then
        diagnostic E.Fail "selected_identity" "The molecular record changed the selected component or trusted reference manifest/record identity.";
      if List.exists(fun key->not(R.equal budget(field key raw)(field key placed)))
          ["source_range";"molecule_range";"orientation";"reading_frame"] then diagnostic E.Fail "construct_coordinates"
        "Source/destination ranges, orientation and reading frame must preserve the accepted placement.";
      if Q.Record.orientation record<>C.Forward || Q.Record.reading_frame record<>Some 0 then diagnostic E.Fail "reference_orientation_or_frame"
        "The reference reproduction profile requires forward 5prime-to-3prime spelling and frame zero.";
      if List.exists(fun key->not(R.equal budget(field key raw)(field key placed)))["requirement_ids";"source"] then diagnostic E.Fail "source_correspondence"
        "The molecular record changed source or requirement correspondence.";
      if not(R.equal budget(field "features" raw)(field "features"(C.Candidate.to_json construct))) then diagnostic E.Fail "feature_coordinates"
        "The molecular record introduced or changed feature-boundary assertions absent from the accepted construct.";
      (match R.manifest budget(Pinned_identity.id(Reference_components.Selection.manifest selection))manifests with
      |None->diagnostic E.Unknown "missing_reference" "The selected frozen offline reference manifest is missing."
      |Some manifest->
        let reference=try Some(F.record manifest(Pinned_identity.id(Reference_components.Selection.reference selection)))
          with Diagnostic.Error error when error.code="reference_manifest"->diagnostic E.Fail "selected_reference" error.message;None in
        match reference with None->()|Some reference->
          let expected=F.Record.to_json reference in
          if List.exists(fun key->not(R.equal budget(field key raw)(field key expected)))
              ["alphabet";"artifact_class";"completeness";"unknown_features";"evidence_relationships"] then diagnostic E.Fail "reference_metadata"
            "Molecular alphabet, artifact class, coding-only scope, unknown features and evidence relationships must match the independently pinned reference.";
          if Q.Record.alphabet record<>C.Molecule.alphabet molecule || not(Z.equal(Z.of_int(Q.Record.length record))(C.Molecule.length molecule))
            || Q.Record.length record<>F.Record.length reference then diagnostic E.Fail "sequence_length_or_alphabet"
            "The emitted sequence length and alphabet must agree with both the accepted construct and frozen reference.";
          let statuses=Q.reference_feature_statuses ~limits:(R.codec budget) reference in
          if not(R.equal budget(field "feature_statuses" raw)(Json.Array(List.map Q.Feature_status.to_json statuses))) then diagnostic E.Fail "feature_statuses"
            "Known, unknown and inapplicable feature declarations must preserve the exact scoped reference-CDS profile; delivered-payload features cannot become known.";
          let without key value=Json.Object(List.filter(fun(name,_)->name<>key)(Json.object_fields value)) in
          if not(R.equal budget(without "schema_version"(field "translation_policy" raw))(without "frame_zero_based"(F.translation manifest))) then
            diagnostic E.Fail "translation_policy" "Translation must use the independently frozen standard-code start, frame-zero and terminal-stop conventions.";
          let sequence=Q.Record.sequence record and expected_sequence=F.Record.sequence reference in
          let sha value=R.charge budget(String.length value+1);Canonical.sha256 value in
          let actual_hash=sha sequence in
          let hash_matches=Q.Record.sequence_sha256 record=actual_hash in
          comparison record "canonical_hash" hash_matches (Some actual_hash)(Some(Q.Record.sequence_sha256 record))
            (if hash_matches then "Declared canonical sequence hash agrees with the emitted symbols." else "Declared canonical sequence hash differs from the emitted symbols.");
          R.charge budget(String.length sequence+String.length expected_sequence+1);
          let exact=sequence=expected_sequence in
          let message=if exact then "Every emitted nucleotide equals the independently frozen selected reference." else (
            let limit=min(String.length sequence)(String.length expected_sequence) and index=ref 0 in
            while !index<limit && sequence.[!index]=expected_sequence.[!index] do incr index done;
            let at value=if !index<String.length value then String.make 1 value.[!index] else "<end>" in
            "Exact reference mismatch at zero-based nucleotide "^string_of_int !index^": expected "^
            Diagnostic_text.repr(at expected_sequence)^", observed "^Diagnostic_text.repr(at sequence)^".") in
          comparison record "exact_reference" exact (Some(F.Record.sequence_sha256 reference))(Some actual_hash)message;
          let linked=List.fold_left(fun map item->R.charge budget(F.Record.canonical_size item+1);
            if List.mem(F.Record.reference_id item)(F.Record.linked_reference_ids reference)
            then M.add(F.alphabet_name(F.Record.alphabet item))item map else map)M.empty(F.records manifest) in
          let counterpart_alphabet=if F.Record.alphabet reference=F.DNA then "RNA" else "DNA" in
          (match M.find_opt "protein" linked,M.find_opt counterpart_alphabet linked with
          |Some protein,Some counterpart->
            (match (try Ok(F.translate_cds ~limits:(R.codec budget) sequence(Q.Record.alphabet record))
              with Diagnostic.Error error when error.code="reference_manifest"->Error error.message) with
            |Error message->comparison record "translation_reference" false (Some(F.Record.sequence_sha256 protein))None
                ("Emitted CDS fails the independent translation convention: "^message)
            |Ok translated->
              R.charge budget(String.length translated+F.Record.length protein+1);
              let same=translated=F.Record.sequence protein in
              comparison record "translation_reference" same (Some(F.Record.sequence_sha256 protein))(Some(sha translated))
                (if same then "Independent standard-code translation matches the frozen protein, retaining the terminal stop."
                 else "Independent standard-code translation differs from the separately frozen protein reference."));
            R.charge budget(String.length sequence+F.Record.length counterpart+1);
            let transformed=String.map(fun char->if F.Record.alphabet reference=F.DNA && char='T' then 'U'
              else if F.Record.alphabet reference<>F.DNA && char='U' then 'T' else char)sequence in
            let consistent=transformed=F.Record.sequence counterpart in
            comparison record "dna_rna_correspondence" consistent (Some(F.Record.sequence_sha256 counterpart))(Some(sha transformed))
              (if consistent then "Emitted spelling agrees with the independently frozen counterpart under T/U correspondence; this makes no delivered-modality equivalence claim."
               else "Emitted spelling differs from the independently frozen counterpart under the separate T/U consistency check.")
          |_->diagnostic E.Fail "linked_reference_inventory" "The selected CDS lacks its independently frozen protein or counterpart nucleotide reference."))
    |_->diagnostic E.Fail "record_correspondence"
        "The molecular record names no authoritative selected placement, reference or molecule." (Some record))
    (Q.Artifact.records candidate);
  let diagnostics=List.rev !diagnostics and checks=List.rev !checks in
  let result=E.Result.make ~limits:(R.codec budget) ~outcome:(R.priority(List.map E.Diagnostic.status diagnostics))
    ~dependencies ~checked_requirement_ids:requirement_ids ~diagnostics ~checks () in
  R.reserve budget(E.Result.to_json result);result
let freshness ?parent ?(limits=default_limits) ~request ~construct ~candidate ~registry ~manifests result=
  let budget=R.create ?parent limits in R.prepare budget [E.Result.canonical_size result,E.Result.to_json result];
  let current=dependencies ~parent:(R.work budget) ~limits ~request ~construct ~candidate ~registry ~manifests () in
  let freshness=E.Result.freshness ~limits:(R.codec budget) result current in
  R.reserve budget(Realization_evidence.Freshness_report.to_json freshness);freshness
let replay ?parent ?(limits=default_limits) ~request ~construct ~candidate ~registry ~manifests result=
  let budget=R.create ?parent limits in R.charge budget(E.Result.canonical_size result+1);
  let actual=check ~parent:(R.work budget) ~limits ~request ~construct ~candidate ~registry ~manifests () in
  R.equal budget(E.Result.to_json result)(E.Result.to_json actual)
