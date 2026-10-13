open Bioc_wire
module A = Bioc_domain.Policy_mrna_structure
module K = Bioc_domain.Construction_content
module E = Bioc_domain.Construction_assessment
module M = Bioc_domain.Molecular_record
module N = Bioc_domain.Molecule
module H = Bioc_domain.Molecule_chemistry
module G = Bioc_domain.Molecule_coordinates
module C = Bioc_domain.Construction
module P = Bioc_domain.Payload_structure
module T = Bioc_domain.Payload_template
module R = Bioc_domain.Molecular_recoding
module Pin = Bioc_domain.Pinned_identity
module Request = Bioc_domain.Policy_controlled_composition_request
module Admission = Policy_controlled_composition_admission
module Document = Bioc_domain.Policy_document
(* Separate capability and profile: ordinary-CDS acceptance remains unchanged.
   This source-bound interpretation only projects the one recognized modified U
   to its declared canonical parent, without asserting physical translation. *)
let implementation_version="biocompiler.ocaml.policy_controlled_nominal_structure_check.v0.1"
let profile="biocompiler.policy_controlled_nominal_structure.v0.1"
let max_work=50000000
let str value=Json.String value
let arr values=Json.Array values
let obj values=Json.Object values
let get key raw=Json.field key(Json.object_fields raw)
let translation_definition ()=obj[
  "$type",str "SemanticDefinition";"id",str "biocompiler.controlled.nominal_translation.v1";
  "version",str "1";"category",str "model";
  "meaning",str "Decode canonical parent RNA bases with the standard genetic code and one terminal stop; declared N1-methylpseudouridine at canonical U positions is projected to U for nominal sequence correspondence only. Physical translation of modified nucleotides, processing and biological expression remain unmeasured assumptions.";
  "parameters",arr[];"result",Json.Null;"clauses",arr[];"assumptions",arr[];
  "executor_kind",Json.Null;"subject_kind",Json.Null]
let requests_nominal_translation ~charge ~admitted ~request =
  let raw=Request.raw request in
  ignore(Bioc_domain.Policy_material_request.preflight
    ~max_bytes:8_323_072 ~max_nodes:249_968 ~max_depth:128 ~charge raw);
  Diagnostic.require(get "request_fingerprint"(Admission.report admitted)=str(Request.fingerprint request))
    "controlled_nominal_translation_premise" "Nominal translation requires fresh admission of this exact original request.";
  let source=get "document"(get "source_authority" raw)in
  let dependencies=Json.array(get "dependencies"(get "entry"(get "catalog_binding" raw)))in
  let definition=translation_definition()in
  charge(List.length dependencies);
  let pins=List.filter(fun pin->get "id" pin=get "id" definition)dependencies in
  match pins with
  |[]->false
  |[pin]->
      let definitions=Json.array(get "definitions"(get "semantics"(get "program" source)))in
      charge(List.length definitions);
      let bodies=List.filter(fun body->get "id" body=get "id" definition)definitions in
      let bytes=Bioc_domain.Policy_material_request.preflight ~charge definition in
      charge(3*bytes);
      let reference=obj["$type",str "DefinitionRef";"id",get "id" definition;
        "version",str "1";"digest",str(Document.document_digest definition)]in
      Diagnostic.require((match bodies with [body]->Json.equal body definition|_->false) && Json.equal pin reference)
        "controlled_nominal_translation_premise" "Nominal translation requires the complete exact supported source definition and selected dependency.";
      true
  |_->Diagnostic.fail "controlled_nominal_translation_premise" "Nominal translation dependency must occur exactly once."
type finding={clause:string;member:string option;severity:string;code:string}
type checked_structure={authority_value:A.t;content_value:K.t;evidence_value:Json.t}
type result={outcome_value:E.outcome;report_value:Json.t;checked_value:checked_structure option}
let report(value:result)=value.report_value
let outcome(value:result)=value.outcome_value
let checked_structure(value:result)=value.checked_value
let authority(value:checked_structure)=value.authority_value
let content(value:checked_structure)=value.content_value
let evidence(value:checked_structure)=value.evidence_value
let outcome_of_findings values=
  if List.exists(fun(value:finding)->value.severity="fail")values then E.Fail
  else if List.exists(fun(value:finding)->value.severity="unsupported")values then E.Unsupported
  else if values<>[]then E.Unknown else E.Pass
let combine a b=match a,b with E.Fail,_|_,E.Fail->E.Fail|E.Unsupported,_|_,E.Unsupported->E.Unsupported
  |E.Unknown,_|_,E.Unknown->E.Unknown|_->E.Pass
let check ?parent ?(maximum=max_work) ~admitted ~request ~candidate ()=
  let authority=Request.material request in
  Diagnostic.require(maximum>=0 && maximum<=max_work)"policy_controlled_nominal_structure_resource_limit""Structural work budget exceeds its fixed ceiling.";
  let budget=match parent with None->Work_budget.create ~profile ~error_code:"policy_controlled_nominal_structure_resource_limit" ~maximum ()
    |Some parent->Work_budget.nested ~parent ~profile ~error_code:"policy_controlled_nominal_structure_resource_limit" ~maximum ()in
  let charge amount=Work_budget.charge budget amount in
  charge 1;
  Diagnostic.require(requests_nominal_translation ~charge ~admitted ~request)
    "controlled_nominal_translation_premise" "The original selected implementation does not supply the nominal translation premise.";
  let original=A.to_json authority and proposed=K.to_json candidate in
  M.check_resources original;M.check_resources proposed;
  let input_bytes=Canonical.encode original and candidate_bytes=Canonical.encode proposed in
  charge(String.length input_bytes+String.length candidate_bytes);
  let authority=A.of_json original and candidate=K.of_json proposed in
  let template=A.template authority and order=A.member_order authority in
  let reconstruction=Construction_check.check_template ~parent:budget ~expected_template:template ~expected_member_order:order candidate in
  let findings=ref []in
  let add ?member clause severity code=
    charge(String.length code+String.length clause+1);
    Diagnostic.require(List.length !findings<4096)"policy_controlled_nominal_structure_resource_limit""Structural finding inventory exceeds its bound.";
    findings:={clause;member;severity;code}:: !findings in
  let verify ?member clause condition code=if not condition then add ?member clause "fail" code in
  let unresolved ?member clause condition code=if not condition then add ?member clause "unknown" code in
  let supported ?member clause condition code=if not condition then add ?member clause "unsupported" code in
  let provenance ?member clause value=
    charge 1;
    unresolved ?member clause(M.Provenance.status value=M.Provenance.Declared && M.Provenance.authority value<>[])"declared_pinned_provenance_required" in
  let rec declared_tree value=
    charge 1;match value with
    |Json.Object fields->
        if List.assoc_opt "schema_version" fields=Some(str M.Provenance.schema_version)then
          provenance "PM-08"(M.Provenance.of_json value)
        else List.iter(fun(_,value)->declared_tree value)fields
    |Json.Array values->List.iter declared_tree values
    |_->()in
  declared_tree original;
  let expected_members=A.members authority in
  let contracts=T.payload_structures template in
  charge(List.length contracts+List.length expected_members);
  verify "PM-03"(List.sort String.compare(List.map P.member_id contracts)=List.sort String.compare order)"required_region_contract_inventory";
  (* Step assumptions are not executable premises in this structural leaf. *)
  List.iter(fun step->supported "PM-09"(C.Transform_step.assumptions step=[])"construction_assumptions_uninterpreted")(T.steps template);
  let results=ref []in
  let inspect (expected:A.member) (molecule:N.t)=
    let member=expected.id and sequence=N.sequence molecule and space=N.space molecule in
    let verify clause=verify ~member clause and supported clause=supported ~member clause and unresolved clause=unresolved ~member clause in
    charge(String.length sequence+List.length(N.features molecule));
    supported "PM-02"(N.form molecule=N.Delivered_rna && G.Space.alphabet space=G.Rna && G.Space.topology space=G.Linear &&
      G.Space.axis space=G.Five_prime_to_three_prime && N.sequence_extent molecule=H.Complete)"requires_complete_linear_delivered_rna";
    verify "PM-02"(String.length sequence=G.Space.length space && String.for_all(String.contains "ACGU")sequence)"canonical_rna_spelling_or_length";
    supported "PM-04"(N.coding_status molecule=N.Coding)"explicit_coding_member_required";
    provenance ~member "PM-08"(N.provenance molecule);
    let regions=["utr5",expected.regions.utr5;"cds",expected.regions.cds;"utr3",expected.regions.utr3;"poly_a",expected.regions.poly_a]in
    let ids=List.map snd regions and features=N.features molecule in
    supported "PM-03"(List.for_all(fun feature->List.mem(N.Feature.id feature)ids)features)"additional_annotation_semantics_unimplemented";
    let contract=List.find_opt(fun contract->P.member_id contract=member)contracts in
    (match contract with None->()|Some contract->
      verify "PM-03"(P.form contract=P.Delivered_rna && P.topology contract=G.Linear)"required_region_modality";
      verify "PM-03"(List.sort String.compare(List.map P.Region.feature_id(P.regions contract))=List.sort String.compare ids)"four_required_regions_only";
      provenance ~member "PM-08"(P.provenance contract));
    let boundaries=List.map(fun(label,id)->
      match List.find_opt(fun feature->N.Feature.id feature=id)features with
      |None->add ~member "PM-03" "fail"("missing_region:"^label);None
      |Some feature->
        provenance ~member "PM-08"(N.Feature.provenance feature);
        let required_kind=List.assoc label["utr5","five_prime_utr";"cds","coding_sequence";
          "utr3","three_prime_utr";"poly_a","poly_a_tail"]in
        verify "PM-03"(N.Feature.kind feature=required_kind)("required_region_meaning:"^label);
        (match contract with None->()|Some contract->
          match List.find_opt(fun region->P.Region.feature_id region=id)(P.regions contract)with
          |None->()|Some region->verify "PM-03"(N.Feature.kind feature=P.Region.kind region)("region_kind:"^label));
        verify "PM-04"(N.Feature.reading_frame feature=(if label="cds"then Some 0 else None))("region_reading_frame:"^label);
        match N.Feature.path feature with
        |None->add ~member "PM-08" "unknown"("region_boundary_unknown:"^label);None
        |Some path->
          (match G.Path.validate_for path space with ()->()|exception Diagnostic.Error _->add ~member "PM-03" "fail"("invalid_region_coordinates:"^label));
          match G.Path.spans path with
          |[span] when G.Path.strand path=G.Forward && G.Span.length span>0->Some(path,G.Span.start span,G.Span.stop span)
          |_->add ~member "PM-03" "fail"("nonempty_single_forward_region:"^label);None)regions in
    let coordinates=if List.for_all Option.is_some boundaries then Some(List.map Option.get boundaries)else None in
    let protein=ref None in
    (match coordinates with
     |Some[(_,a,b);(_,c,d);(_,e,f);(tail_path,g,h)]->
       verify "PM-03"(a=0 && b=c && d=e && f=g && h=String.length sequence)"ordered_complete_partition";
       let policy=expected.product.translation_policy in
       let ordinary=R.Translation_policy.profile policy=R.Translation_policy.Ordinary_cds &&
         R.Translation_policy.genetic_code policy=R.standard_genetic_code && R.Translation_policy.recodings policy=[]in
       supported "PM-04" ordinary "ordinary_standard_code_without_recoding_required";
       if ordinary && c>=0 && d<=String.length sequence && d>c then(
         let length=d-c in charge length;
         if length<6 || length mod 3<>0 then add ~member "PM-04" "fail" "whole_cds_codon_extent"
         else(
           verify "PM-04"(String.sub sequence c 3="AUG")"explicit_aug_start";
           let amino=Buffer.create(length/3)and complete=ref true in
           for offset=0 to length/3-1 do
             let triplet=String.sub sequence(c+3*offset)3 in
             let residue=List.assoc_opt triplet R.standard_rna_codon_table in charge 65;
             match residue with
             |None->complete:=false;add ~member "PM-04" "fail" "untranslatable_codon"
             |Some residue when offset=length/3-1->if residue<>'*'then(complete:=false;add ~member "PM-04" "fail" "in_frame_terminal_stop_required")
             |Some '*'->complete:=false;add ~member "PM-04" "fail" "internal_stop"
             |Some residue->Buffer.add_char amino residue
           done;
           if !complete then(let spelling=Buffer.contents amino in protein:=Some spelling;
             verify "PM-04"(spelling=expected.product.sequence)"complete_product_spelling_mismatch")));
       let chemistry=N.chemistry molecule in
       List.iter(fun modification->
         let positions=match H.Modification.scope modification with
           |H.Modification.Positions->H.Modification.positions modification
           |H.Modification.All_matching_bases->charge(String.length sequence);List.init(String.length sequence)Fun.id|>List.filter(fun position->sequence.[position]=H.Modification.canonical_base modification)in
         charge(List.length positions);
         let affects_cds=List.exists(fun position->position>=c && position<d)positions in
         let identity=H.Modification.identity modification in
         let recognized=H.Chemical_identity.namespace identity="biocompiler.chemical" &&
           H.Chemical_identity.accession identity="n1_methylpseudouridine" &&
           H.Chemical_identity.version identity="1" && H.Modification.canonical_base modification='U' in
         supported "PM-06"(not affects_cds || recognized)"modified_cds_uninterpreted";
         verify "PM-06"(List.for_all(fun position->position>=0 && position<String.length sequence &&
           sequence.[position]=H.Modification.canonical_base modification)positions)"nominal_parent_base_correspondence") (H.modifications chemistry);
       let tail=H.terminal_tail chemistry in
       (match H.Tail.status tail with
        |H.Unknown->unresolved "PM-07" false "terminal_tail_unknown"
        |H.Inapplicable|H.Absent->supported "PM-07" false "positive_exact_represented_tail_required"
        |H.Declared->
          supported "PM-07"(H.Tail.placement tail=Some H.Tail.Represented_terminal)"positive_exact_represented_tail_required";
          (match H.Tail.length tail with
           |Some length->(match H.Tail_length.mode length with
             |H.Tail_length.Exact amount->
               supported "PM-07"(amount>0)"positive_exact_represented_tail_required";
               if amount>0 then verify "PM-07"(amount=h-g)"tail_region_correspondence"
             |H.Tail_length.Bounded _->supported "PM-07" false "positive_exact_represented_tail_required"
             |H.Tail_length.Unknown_length->unresolved "PM-07" false "terminal_tail_length_unknown")
           |None->unresolved "PM-07" false "terminal_tail_length_unknown");
          (match H.Tail.path tail with
           |Some path->verify "PM-07"(path=tail_path)"tail_region_correspondence"
           |None->if H.Tail.placement tail=Some H.Tail.Represented_terminal then unresolved "PM-07" false "terminal_tail_path_unknown"));
       if g>=0 && h<=String.length sequence && h>g then verify "PM-07"(String.for_all((=)'A')(String.sub sequence g(h-g)))"terminal_region_is_not_poly_a"
     |Some _->assert false|None->());
    let chemistry=N.chemistry molecule in
    verify "PM-05"(Json.equal(H.to_json chemistry)(H.to_json expected.chemistry))"original_full_chemistry_mismatch";
    List.iter(fun(name,claim)->
      (match H.Claim.status claim with H.Unknown->unresolved "PM-05" false(name^"_unknown")
       |H.Declared->verify "PM-05"(H.Claim.declared_nominal_complete claim)(name^"_identity_incomplete")
       |H.Absent|H.Inapplicable->supported "PM-05" false(name^"_must_be_declared_present"));
      provenance ~member "PM-08"(H.Claim.provenance claim))
      ["cap",H.cap chemistry;"start_end",H.start_end chemistry;"finish_end",H.finish_end chemistry];
    (match H.modification_inventory_status chemistry with H.Unknown->unresolved "PM-06" false "modification_inventory_unknown"
     |H.Declared->()|H.Absent|H.Inapplicable->supported "PM-06" false "complete_modification_inventory_required");
    List.iter(fun modification->
      verify "PM-06"(H.Chemical_identity.declared_nominal_complete(H.Modification.identity modification))"modification_identity_incomplete";
      provenance ~member "PM-08"(H.Modification.provenance modification))(H.modifications chemistry);
    provenance ~member "PM-08"(H.modification_inventory_provenance chemistry);
    provenance ~member "PM-08"(H.Tail.provenance(H.terminal_tail chemistry));
    (match H.validate_for chemistry space ~sequence ~sequence_extent:(N.sequence_extent molecule)with
     |()->()|exception Diagnostic.Error _->add ~member "PM-06" "fail" "chemistry_coordinates_or_parent_bases");
    verify "PM-04"(Pin.content_fingerprint expected.product.identity=Canonical.fingerprint(A.product_content_json expected.product.sequence))"product_content_pin_mismatch";
    provenance ~member "PM-08" expected.product.provenance;
    results:= !results@[obj["member",str member;"molecule_fingerprint",str(N.fingerprint molecule);
      "product_identity",Pin.to_json expected.product.identity;"expected_product",str expected.product.sequence;
      "translated_product",(match !protein with None->Json.Null|Some value->str value)]]in
  (match K.inventory candidate with
   |None->add "PM-09" "fail" "missing_materialized_inventory"
   |Some inventory->
       let molecules=K.Inventory.molecules inventory in
       verify "PM-02"(List.map N.id molecules=order)"original_exact_member_order";
       List.iter(fun expected->match List.find_opt(fun molecule->N.id molecule=expected.A.id)molecules with
         |None->add ~member:expected.id "PM-02" "fail" "missing_delivered_member"|Some molecule->inspect expected molecule)expected_members);
  let findings=List.sort_uniq compare !findings in
  let structure_outcome=outcome_of_findings findings in
  let content_outcome=Construction_check.content_outcome reconstruction in
  let outcome_value=combine content_outcome structure_outcome in
  let report_value=obj["schema_version",str "biocompiler.policy_controlled_nominal_structure_assessment.v0.1";
    "profile",str profile;"implementation_version",str implementation_version;
    "claim_scope",str "exact_supplied_mrna_structure_under_explicit_controlled_nominal_translation_premise";
    "source_request_fingerprint",str(Request.fingerprint request);
    "nominal_translation_definition",translation_definition();"physical_translation_status",str "unassessed";
    "authority_fingerprint",str(A.fingerprint authority);"candidate_fingerprint",str(K.fingerprint candidate);
    "content_reconstruction",Construction_check.content_report reconstruction;
    "content_outcome",str(E.outcome_name content_outcome);"structural_outcome",str(E.outcome_name structure_outcome);
    "outcome",str(E.outcome_name outcome_value);"checked_clauses",arr(List.map str["PM-02";"PM-03";"PM-04";"PM-05";"PM-06";"PM-07";"PM-09"]);
    "PM-08_scope",str "supplied_construction_region_chemistry_product_declaration_provenance_only";
    "unassessed_clauses",arr(List.map str["PM-01";"PM-08_external_component_binding";"PM-10";"PM-11";"PM-12"]);
    "members",arr !results;"diagnostics",arr(List.map(fun(finding:finding)->obj["clause",str finding.clause;
      "member",(match finding.member with None->Json.Null|Some value->str value);"severity",str finding.severity;"code",str finding.code])findings);
    "context_status",str "unassessed";"implementation",str "unassessed";"policy",str "unassessed";
    "material_binding",str "unassessed";"export",str "withheld"]in
  let output=Work_budget.create_output ~profile ~error_code:"policy_controlled_nominal_structure_resource_limit" ~max_bytes:M.max_json_bytes ~max_nodes:M.max_items ()in
  Work_budget.reserve_json output report_value;charge(2*String.length(Canonical.encode report_value));
  let checked_value=if outcome_value=E.Pass then(match Construction_check.checked_content reconstruction with
    |Some content_value->Some{authority_value=authority;content_value;evidence_value=report_value}|None->None)else None in
  {outcome_value;report_value;checked_value}
