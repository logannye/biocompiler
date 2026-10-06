open Bioc_wire
open Bioc_domain
module A = Policy_mrna_structure
module K = Construction_content
module E = Construction_assessment
module N = Molecule
module H = Molecule_chemistry
module P = Bioc_compiler.Construction_producer
module Check = Bioc_checker.Policy_mrna_structure_check
module W = Bioc_checker.Work_budget
let checks=ref 0
let require condition message=incr checks;if not condition then failwith message
let str value=Json.String value
let arr values=Json.Array values
let field key value=Json.field key(Json.object_fields value)
let set key value raw=Json.Object((key,value)::List.remove_assoc key(Json.object_fields raw))
let rec at path raw=match path with []->raw|key::rest->
  at rest(match raw with Json.Array values->List.nth values(int_of_string key)|_->field key raw)
let rec edit path change raw=match path with []->change raw|key::rest->
  match raw with
  |Json.Array values->arr(List.mapi(fun index value->if index=int_of_string key then edit rest change value else value)values)
  |_->set key(edit rest change(field key raw))raw
let put path value raw=edit path(fun _->value)raw
let rejected code run=incr checks;match run()with
  |_->failwith("Expected rejection: "^code)
  |exception Diagnostic.Error value->if value.code<>code then failwith("Expected "^code^"; got "^value.code)
let read path=let channel=open_in_bin path in
  Fun.protect ~finally:(fun()->close_in_noerr channel)(fun()->
    let size=in_channel_length channel in require(size<200000)"Artificial fixture exceeds read bound";
    Json.parse(really_input_string channel size))
let molecule_path=["template";"sources";"0";"molecule"]
let chemistry_path=molecule_path@["chemistry"]
let feature_path index=molecule_path@["features";string_of_int index]
let expected_path=["members";"1"]
let sync_chemistry raw=
  let chemistry=at chemistry_path raw in
  let chemistry=if at["terminal_tail";"path"]chemistry=Json.Null then chemistry else
    put["terminal_tail";"path";"space_id"](str "payload.output.frame")chemistry in
  put(expected_path@["chemistry"])chemistry raw
let produce raw=
  let authority=A.of_json raw in
  let candidate=P.construct_template ~member_order:(A.member_order authority)(A.template authority)in
  authority,candidate
let checked raw=
  let authority,candidate=produce raw in Check.check ~authority ~candidate ()
let has_code code result=List.exists(fun raw->field "code" raw=str code)(Json.array(field "diagnostics"(Check.report result)))
let expect label expected code raw=
  let result=checked raw in
  require(Check.outcome result=expected)(label^" has wrong outcome: "^E.outcome_name(Check.outcome result));
  require(has_code code result)(label^" lost its structural diagnostic: "^code);
  require(Check.checked_structure result=None)(label^" gained structural acceptance");result
let replace_claim name status raw=
  raw|>put(chemistry_path@[name;"status"])(str status)
  |>put(chemistry_path@[name;"identity"])Json.Null|>sync_chemistry
let tail_path=chemistry_path@["terminal_tail"]
let unknown_tail raw=raw|>put(tail_path@["status"])(str "unknown")
  |>put(tail_path@["placement"])Json.Null|>put(tail_path@["length"])Json.Null
  |>put(tail_path@["path"])Json.Null|>sync_chemistry
let absent_tail raw=raw|>put(tail_path@["placement"])(str "absent")
  |>put(tail_path@["length";"exact"])(Json.int 0)|>put(tail_path@["path"])Json.Null|>sync_chemistry
let core_tail mode raw=
  let length=H.Tail_length.to_json(H.Tail_length.make mode)in
  raw|>put(molecule_path@["sequence_extent"])(str "exact_core")
  |>put["template";"output_members";"0";"sequence_extent"](str "exact_core")
  |>put(tail_path@["placement"])(str "appended_terminal")
  |>put(tail_path@["length"])length|>put(tail_path@["path"])Json.Null|>sync_chemistry
let changed_product sequence raw=
  raw|>put(expected_path@["product";"sequence"])(str sequence)
  |>put(expected_path@["product";"identity";"content_fingerprint"])(str(Canonical.fingerprint(A.product_content_json sequence)))
let modify_sequence sequence raw=put(molecule_path@["sequence"])(str sequence)raw
let ()=
  let fixture=read Sys.argv.(1)in
  let original=field "authority" fixture in
  let authority=A.of_json original and candidate=K.of_json(field "literal_candidate" fixture)in
  require(str(A.fingerprint authority)=field "authority_digest" fixture)"Frozen original authority changed";
  require(str(K.fingerprint candidate)=field "candidate_digest" fixture)"Frozen independent candidate changed";
  require(A.member_order authority=["z-helper";"payload"])"Explicit ordered helper inventory changed";
  let generated=P.construct_template ~member_order:(A.member_order authority)(A.template authority)in
  require(Canonical.encode(K.to_json generated)=Canonical.encode(field "literal_candidate" fixture))
    "Producer differs from independently authored literal molecule content";
  let inventory=Option.get(K.inventory candidate)in
  require(List.map N.sequence(K.Inventory.molecules inventory)=["GGAUGGAAUGACCAAAAA";"CCAUGGCUUAAGGAAAA"])
    "Literal artificial RNA spellings differ";
  let result=Check.check ~authority ~candidate ()in
  require(Check.outcome result=E.Pass)"Complete literal structure did not pass";
  let report=Check.report result in
  require(field "content_outcome" report=str "pass" && field "structural_outcome" report=str "pass")
    "Content reconstruction and structural checks were not independently successful";
  require(List.map(field "translated_product")(Json.array(field "members" report))=[str "ME";str "MA"])
    "Independent ordinary-CDS translation differs from literal products";
  let accepted=Option.get(Check.checked_structure result)in
  require(A.fingerprint(Check.authority accepted)=A.fingerprint authority && K.fingerprint(Check.content accepted)=K.fingerprint candidate)
    "Opaque structural result lost original authority or exact content";
  require(Json.equal(Check.evidence accepted)report)"Opaque result lost its fresh assessment";
  List.iter(fun key->require(field key report=str "unassessed")("Unexpected wider claim: "^key))
    ["context_status";"implementation";"policy";"material_binding"];
  require(field "export" report=str "withheld")"Structural leaf granted export";
  require(field "unassessed_clauses" report=arr(List.map str["PM-01";"PM-08_external_component_binding";"PM-10";"PM-11";"PM-12"]))
    "Structural leaf erased withheld obligations";
  require(field "checked_clauses" report=arr(List.map str["PM-02";"PM-03";"PM-04";"PM-05";"PM-06";"PM-07";"PM-09"]))
    "Structural leaf broadened checked clauses";
  ignore(Check.replay ~authority ~candidate report);
  List.iter(fun(key,value)->rejected "policy_mrna_structure_assessment_mismatch"(fun()->
    Check.replay ~authority ~candidate(set key value report)))
    ["export",str "accepted";"implementation",str "pass";"authority_fingerprint",str(String.make 64 '0')];
  ignore(expect "Bounded appended tail" E.Unsupported "requires_complete_linear_delivered_rna"(core_tail(H.Tail_length.Bounded(4,8))original));
  ignore(expect "Unknown appended tail" E.Unsupported "positive_exact_represented_tail_required"(core_tail H.Tail_length.Unknown_length original));
  ignore(expect "Unknown represented completeness" E.Unknown "terminal_tail_unknown"(unknown_tail original));
  ignore(expect "Absent tail" E.Unsupported "positive_exact_represented_tail_required"(absent_tail original));
  ignore(expect "Unknown cap" E.Unknown "cap_unknown"(replace_claim "cap" "unknown" original));
  ignore(expect "Absent cap" E.Unsupported "cap_must_be_declared_present"(replace_claim "cap" "absent" original));
  ignore(expect "Unknown 5-prime end" E.Unknown "start_end_unknown"(replace_claim "start_end" "unknown" original));
  ignore(expect "Unknown 3-prime end" E.Unknown "finish_end_unknown"(replace_claim "finish_end" "unknown" original));
  ignore(expect "Unknown modification inventory" E.Unknown "modification_inventory_unknown"
    (original|>put(chemistry_path@["modification_inventory_status"])(str "unknown")|>sync_chemistry));
  let missing=edit(molecule_path@["features"])(fun raw->arr(List.tl(Json.array raw)))original in
  ignore(expect "Missing CDS" E.Fail "missing_region:cds" missing);
  ignore(expect "Repinned arbitrary region meaning" E.Fail "required_region_meaning:cds"
    (original|>put(feature_path 0@["kind"])(str "uninterpreted_annotation")
     |>put["template";"payload_structures";"0";"regions";"0";"kind"](str "uninterpreted_annotation")));
  let region label index key value=ignore(expect label E.Fail "ordered_complete_partition"
      (put(feature_path index@["path";"spans";"0";key])(Json.int value)original))in
  region "Gap before CDS" 3 "end" 1;
  region "UTR/CDS overlap" 3 "end" 3;
  region "Uncovered internal junction base" 2 "start" 12;
  ignore(expect "Empty UTR" E.Fail "nonempty_single_forward_region:utr5"
    (put(feature_path 3@["path";"spans";"0";"end"])(Json.int 0)original));
  ignore(expect "Reverse UTR" E.Fail "nonempty_single_forward_region:utr5"
    (put(feature_path 3@["path";"strand"])(str "-")original));
  ignore(expect "Unknown boundary" E.Unknown "region_boundary_unknown:utr5"(put(feature_path 3@["path"])Json.Null original));
  ignore(expect "Shifted CDS frame" E.Fail "region_reading_frame:cds"(put(feature_path 0@["reading_frame"])(Json.int 1)original));
  let extra=set "id"(str "uninterpreted.annotation")(at(feature_path 3)original)in
  ignore(expect "Extra annotation" E.Unsupported "additional_annotation_semantics_unimplemented"
    (edit(molecule_path@["features"])(fun raw->arr(extra::Json.array raw))original));
  ignore(expect "Wrong complete product" E.Fail "complete_product_spelling_mismatch"(changed_product "MF" original));
  ignore(expect "Stale product identity" E.Fail "product_content_pin_mismatch"
    (put(expected_path@["product";"identity";"content_fingerprint"])(str(String.make 64 '0'))original));
  ignore(expect "Internal stop" E.Fail "internal_stop"(modify_sequence "CCAUGUAAUAAGGAAAA" original));
  ignore(expect "Missing terminal stop" E.Fail "in_frame_terminal_stop_required"(modify_sequence "CCAUGGCUCAAGGAAAA" original));
  ignore(expect "Wrong start" E.Fail "explicit_aug_start"(modify_sequence "CCGUGGCUUAAGGAAAA" original));
  let recoding=Molecular_recoding.Codon_recoding.make ~codon_index:1 ~expected_triplet:"GCU" ~amino_acid:'A' ~condition:"supplied_condition"in
  let conditional=Molecular_recoding.Translation_policy.make ~profile:Molecular_recoding.Translation_policy.Conditional_cds ~recodings:[recoding] ()in
  ignore(expect "Recoded translation" E.Unsupported "ordinary_standard_code_without_recoding_required"
    (put(expected_path@["product";"translation_policy"])(Molecular_recoding.Translation_policy.to_json conditional)original));
  let provenance=Molecular_record.Provenance.of_json(at(molecule_path@["provenance"])original)in
  let chemical=H.Chemical_identity.make ~namespace:"software_fixture.chemical" ~accession:"artificial_modified_base" ~version:"1"in
  let modification id base scope positions=H.Modification.make ~id ~identity:chemical ~canonical_base:base ~scope ~positions ~provenance in
  let with_modification modification=original|>put(chemistry_path@["modifications"])(arr[H.Modification.to_json modification])|>sync_chemistry in
  ignore(expect "Modified CDS" E.Unsupported "modified_cds_uninterpreted"
    (with_modification(modification "cds-modification" 'U' H.Modification.Positions [3])));
  ignore(expect "All-matching modified CDS" E.Unsupported "modified_cds_uninterpreted"
    (with_modification(modification "all-u" 'U' H.Modification.All_matching_bases [])));
  let outside=checked(with_modification(modification "utr-modification" 'C' H.Modification.Positions [0]))in
  require(Check.outcome outside=E.Pass)"Known explicitly supplied non-CDS chemistry was rejected";
  let known_chemistry_change=put(expected_path@["chemistry";"cap";"identity";"version"])(str "2")original in
  ignore(expect "Different expected chemistry" E.Fail "original_full_chemistry_mismatch" known_chemistry_change);
  let unknown_provenance=Molecular_record.Provenance.make ~status:Molecular_record.Provenance.Unknown
      ~authority:[] ~locator:None ~reason:"Independent authority not supplied"in
  ignore(expect "Unknown original mapping provenance" E.Unknown "declared_pinned_provenance_required"
    (put(molecule_path@["assembly";"0";"provenance"])(Molecular_record.Provenance.to_json unknown_provenance)original));
  (* A helper has the same obligations as the requested member. *)
  ignore(expect "Helper wrong product" E.Fail "complete_product_spelling_mismatch"
    (original|>put["members";"0";"product";"sequence"](str "MA")
     |>put["members";"0";"product";"identity";"content_fingerprint"](str(Canonical.fingerprint(A.product_content_json "MA")))));
  let _,synonymous=produce(modify_sequence "CCAUGGCCUAAGGAAAA" original)in
  let forged=K.of_json(set "authority_fingerprint"(str(K.authority candidate))(K.to_json synonymous))in
  let mutation=Check.check ~authority ~candidate:forged ()in
  require(Check.outcome mutation=E.Fail && Check.checked_structure mutation=None)"Equal translation and recomputed candidate pins authorized a base edit";
  require(field "structural_outcome"(Check.report mutation)=str "pass" && field "content_outcome"(Check.report mutation)=str "fail")
    "Synonymous control did not isolate exact nucleotide authority from structural correctness";
  let no_helper=K.to_json candidate|>put["member_order"](arr[str "payload"])
    |>edit["inventory";"molecules"](fun values->arr(List.filter(fun raw->field "id" raw=str "payload")(Json.array values)))
    |>edit["inventory";"role_instances"](fun values->arr(List.filter(fun raw->field "subject_id" raw=str "payload")(Json.array values)))in
  let no_helper=Check.check ~authority ~candidate:(K.of_json no_helper)()in
  require(Check.outcome no_helper=E.Fail && has_code "missing_delivered_member" no_helper)"Missing helper acquired completeness";
  let rec reframe value=match value with
    |Json.String "z-helper.output.frame"->str "z-extra.output.frame"
    |Json.Object values->Json.Object(List.map(fun(key,value)->key,reframe value)values)
    |Json.Array values->arr(List.map reframe values)|_->value in
  let extra_member=at["inventory";"molecules";"0"](K.to_json candidate)|>reframe|>set "id"(str "z-extra")in
  let extra_candidate=K.to_json candidate|>put["member_order"](arr(List.map str["z-helper";"payload";"z-extra"]))
    |>edit["inventory";"molecules"](fun values->arr(Json.array values@[extra_member]))|>K.of_json in
  let extra_result=Check.check ~authority ~candidate:extra_candidate ()in
  require(Check.outcome extra_result=E.Fail && has_code "original_exact_member_order" extra_result)
    "Unauthorized extra delivered member acquired completeness";
  let reversed=P.construct_template ~member_order:["payload";"z-helper"](A.template authority)in
  require(Check.outcome(Check.check ~authority ~candidate:reversed ())=E.Fail)"Candidate-selected member order was accepted";
  let different=A.of_json(put["template";"id"](str "wrong-original-template")original)in
  require(Check.outcome(Check.check ~authority:different ~candidate ())=E.Fail)"Wrong original template accepted old content";
  rejected "invalid_policy_mrna_structure"(fun()->A.of_json(set "profile"(str "future_profile")original));
  rejected "invalid_policy_mrna_structure"(fun()->A.of_json(set "member_order"(arr[str "payload";str "payload"])original));
  rejected "invalid_policy_mrna_structure"(fun()->A.of_json(set "members"(arr(List.rev(Json.array(field "members" original))))original));
  rejected "invalid_molecular_provenance"(fun()->A.of_json(put(expected_path@["product";"provenance";"authority"])(arr[])original));
  rejected "invalid_chemistry"(fun()->A.of_json(put(chemistry_path@["modification_inventory_status"])(str "absent")original));
  rejected "invalid_chemistry"(fun()->A.of_json(with_modification(modification "wrong-parent" 'A' H.Modification.Positions [0])));
  rejected "policy_mrna_structure_resource_limit"(fun()->Check.check ~maximum:0 ~authority ~candidate ());
  let budget=W.create ~profile:"parent-test" ~error_code:"parent_work_exhausted" ~maximum:1 ()in
  incr checks;
  (match Check.check ~parent:budget ~authority ~candidate ()with
   |_->failwith "Parent exhaustion produced an assessment"
   |exception Diagnostic.Error error->require(error.code="parent_work_exhausted" && W.is_exhaustion budget error)
       "Parent resource provenance was swallowed or relabeled");
  let rec cyclic=Json.Array[cyclic]in
  rejected "molecular_cycle"(fun()->A.of_json cyclic);
  let rec nested count raw=if count=0 then raw else nested(count-1)(arr[raw])in
  rejected "molecular_resource_limit"(fun()->A.of_json(nested 100 Json.Null));
  Printf.printf "policy mRNA structure: %d literal and mutation checks\n" !checks
