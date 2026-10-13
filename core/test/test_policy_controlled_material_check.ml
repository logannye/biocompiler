(* Literal, source-bound RC4 material controls. This test imports no producer;
   all candidates originate in the separately frozen artificial content fixture. *)
open Bioc_wire
module R = Bioc_domain.Policy_controlled_composition_request
module C = Bioc_domain.Policy_controlled_material_candidate
module K = Bioc_domain.Construction_content
module M = Bioc_domain.Policy_mrna_structure
module N = Bioc_domain.Molecule
module E = Bioc_domain.Construction_assessment
module Check = Bioc_checker.Policy_controlled_material_check
module Nominal = Bioc_checker.Policy_controlled_structure_check
module Admission = Bioc_checker.Policy_controlled_composition_admission
module Document = Bioc_domain.Policy_document
module W = Bioc_checker.Work_budget
let checks = ref 0
let require condition message = incr checks; if not condition then failwith message
let str value = Json.String value
let arr values = Json.Array values
let get key raw = Json.field key (Json.object_fields raw)
let set key value raw = Json.Object ((key,value) :: List.remove_assoc key (Json.object_fields raw))
let rec at path raw = match path with [] -> raw | key::rest ->
  at rest (match raw with Json.Array values -> List.nth values (int_of_string key) | _ -> get key raw)
let rec edit path change raw = match path with [] -> change raw | key::rest ->
  match raw with
  | Json.Array values -> arr (List.mapi (fun index value ->
      if index = int_of_string key then edit rest change value else value) values)
  | _ -> set key (edit rest change (get key raw)) raw
let put path value = edit path (fun _ -> value)
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let bytes = in_channel_length channel in
    require (bytes > 0 && bytes < 1_000_000) "Independent literal fixture read bound";
    Json.parse (really_input_string channel bytes))
let rejected code action =
  incr checks;
  match action () with
  | _ -> failwith ("Expected rejection: " ^ code)
  | exception Diagnostic.Error diagnostic ->
      if diagnostic.code <> code then failwith ("Expected " ^ code ^ "; got " ^ diagnostic.code)
let rejected_any label action =
  incr checks;
  match action () with _ -> failwith ("Expected rejection: " ^ label)
  | exception Diagnostic.Error _ -> ()
let material_path = ["construction";"inventory";"molecules"]
let molecule_path index = material_path @ [string_of_int index]
let root_path index = ["material_authority";"template";"sources";string_of_int index;"molecule"]
let rebind_roles raw =
  let molecules = Json.array (at material_path raw) |> List.map (fun raw -> N.of_json raw) in
  edit ["construction";"inventory";"role_instances"] (fun roles ->
    arr (List.filter_map (fun role ->
      let id = Json.string (get "subject_id" role) in
      match List.find_opt (fun (molecule:N.t) -> N.id molecule = id) molecules with
      | None -> None
      | Some molecule -> Some (set "subject_fingerprint" (str (N.fingerprint molecule)) role))
      (Json.array roles))) raw
let bind request raw =
  let authority = R.material request in
  raw |> set "request_fingerprint" (str (R.fingerprint request))
      |> put ["construction";"authority_fingerprint"]
          (str (K.authority_fingerprint ~template:(M.template authority)
            ~member_order:(M.member_order authority)))
let run_check request raw = Check.check ~request ~candidate:(C.of_json raw) ()
let no_material label request raw =
  let result = run_check request raw in
  require (Check.outcome result <> E.Pass && Check.accepted result = None)
    (label ^ " acquired checked material");
  require (get "status" (Check.report result) = str "not_accepted")
    (label ^ " lost rejection status"); result
let structure_code code result =
  Json.array (get "diagnostics" (get "structure" (Check.report result)))
  |> List.exists (fun row -> get "code" row = str code)
let rec replace_text before after raw = match raw with
  | Json.String text when text = before -> str after
  | Json.Object fields -> Json.Object (List.map (fun (key,value) -> key,replace_text before after value) fields)
  | Json.Array values -> arr (List.map (replace_text before after) values)
  | _ -> raw
(* This independently supplied literal premise is not copied from the checker.
   Its exact body and selected dependency are original interpretation authority. *)
let nominal_definition () = Json.Object [
  "$type",str "SemanticDefinition";"id",str "biocompiler.controlled.nominal_translation.v1";
  "version",str "1";"category",str "model";
  "meaning",str "Decode canonical parent RNA bases with the standard genetic code and one terminal stop; declared N1-methylpseudouridine at canonical U positions is projected to U for nominal sequence correspondence only. Physical translation of modified nucleotides, processing and biological expression remain unmeasured assumptions.";
  "parameters",arr [];"result",Json.Null;"clauses",arr [];"assumptions",arr [];
  "executor_kind",Json.Null;"subject_kind",Json.Null]
let with_nominal_definition definition original =
  let pin = Json.Object ["$type",str "DefinitionRef";"id",get "id" definition;
    "version",get "version" definition;"digest",str (Document.document_digest definition)] in
  let append value values = arr (Json.array values @ [value]) in
  original
  |> edit ["source_authority";"document";"program";"semantics";"definitions"] (append definition)
  |> edit ["source_authority";"document";"implementations";"implementations";"0";"dependencies"] (append pin)
  |> edit ["catalog_binding";"entry";"dependencies"] (append pin)
let with_modification modification original literal =
  let modifications = arr [modification] in
  let original = List.fold_left (fun raw index -> raw
    |> put (root_path index @ ["chemistry";"modifications"]) modifications
    |> put ["material_authority";"members";string_of_int index;"chemistry";"modifications"] modifications)
    original [0;1] in
  let literal = List.fold_left (fun raw index ->
    put (molecule_path index @ ["chemistry";"modifications"]) modifications raw) literal [0;1] in
  let request = R.of_json original in
  request, literal |> rebind_roles |> bind request
let run () =
  if Array.length Sys.argv <> 3 then failwith "Expected original request and independent material literal fixture";
  let original = read Sys.argv.(1) and fixture = read Sys.argv.(2) in
  let request = R.of_json original and literal = get "literal_candidate" fixture in
  let candidate = C.of_json literal in
  require (str (R.fingerprint request) = get "request_sha256" fixture) "Independent original request pin changed";
  require (str (C.fingerprint candidate) = get "candidate_sha256" fixture) "Independent literal candidate pin changed";
  require (get "schema_version" fixture = str "biocompiler.policy_controlled_material_literals.v0.1") "Literal schema changed";
  let content = C.construction candidate in
  let molecules = K.Inventory.molecules (Option.get (K.inventory content)) in
  require (K.member_order content = ["rna-a";"rna-b"]) "Literal RNA order changed";
  require (List.map N.sequence molecules = ["CCAUGGCUUAAGGAAAA";"CCAUGGGUUAAGGAAAA"])
    "Independent exact RNA originals changed";
  let result = Check.check ~request ~candidate () in
  let report = Check.report result in
  require (Check.outcome result = E.Pass) "Literal exact pair did not pass";
  let accepted = Option.get (Check.accepted result) in
  require (R.fingerprint (Check.request accepted) = R.fingerprint request &&
    C.fingerprint (Check.candidate accepted) = C.fingerprint candidate &&
    K.fingerprint (Check.content accepted) = K.fingerprint content &&
    Json.equal (Check.evidence accepted) report) "Abstract material capability lost exact original authority";
  require (Json.equal (Check.structure_evidence (Check.structure accepted)) (get "structure" report))
    "Material capability lost independent structural evidence";
  require (get "stage" report = str "material" && get "status" report = str "checked_controlled_material" &&
    get "claim_scope" report = str "exact_supplied_two_member_rna_structure_only") "Material scope changed";
  require (get "behavior_status" report = str "not_performed" && get "empirical_status" report = str "unassessed" &&
    get "human_use" report = str "unassessed" && get "therapeutic_export" report = str "withheld")
    "Material checkpoint fabricated behavioral or therapeutic acceptance";
  require (at ["admission";"construction_status"] report = str "not_performed" &&
    at ["admission";"behavior_status"] report = str "not_performed") "Original admission report was rewritten";
  require (List.map (get "translated_product") (Json.array (at ["structure";"members"] report)) = [str "MA";str "MG"])
    "Independent complete product translation changed";
  require (at ["material_limits";"total_rna_nt"] report = Json.int 34 &&
    at ["material_limits";"outcome"] report = str "pass") "Pair length accounting changed";
  require (Json.equal (get "bindings" report) (at ["assembly";"product_bindings"] original) &&
    Json.equal (get "context" report) (get "context" original) &&
    Json.equal (get "resources" report) (get "resources" original)) "Material evidence trimmed original context or bindings";
  let invocation = Canonical.fingerprint (Json.Object [
    "request_fingerprint",str (R.fingerprint request); "candidate_fingerprint",str (C.fingerprint candidate)]) in
  require (Check.request_fingerprint result = R.fingerprint request &&
    Check.candidate_fingerprint result = C.fingerprint candidate &&
    Check.invocation_fingerprint result = invocation && get "invocation_fingerprint" report = str invocation)
    "Invocation did not bind complete request and candidate identities";
  ignore (Check.replay ~request ~candidate report);
  List.iter (fun (key,value) -> rejected "controlled_material_assessment_mismatch"
    (fun () -> Check.replay ~request ~candidate (set key value report)))
    ["status",str "accepted"; "behavior_status",str "checked";
     "request_fingerprint",str (String.make 64 '0')];
  rejected "controlled_material_request_binding" (fun () -> run_check request
    (set "request_fingerprint" (str (String.make 64 '0')) literal));
  let changed_project = R.of_json (put ["source_authority";"project_context";"title"]
    (str "Another independent original project") original) in
  rejected "controlled_material_request_binding" (fun () -> Check.check ~request:changed_project ~candidate ());
  let fresh_project = C.of_json (bind changed_project literal) in
  require (Check.outcome (Check.check ~request:changed_project ~candidate:fresh_project ()) = E.Pass)
    "Fresh exact material under changed complete authority was incorrectly forbidden";
  rejected "controlled_material_assessment_mismatch" (fun () ->
    Check.replay ~request:changed_project ~candidate:fresh_project report);
  (* Changed molecular material remains foreign after both local wrapper and
     construction authority hashes are rebound to the independent destination. *)
  List.iter (fun (label,sequence) ->
    let foreign_request = R.of_json (put (root_path 0 @ ["sequence"]) (str sequence) original) in
    let foreign = literal |> put (molecule_path 0 @ ["sequence"]) (str sequence)
      |> rebind_roles |> bind foreign_request in
    require (Check.outcome (run_check foreign_request foreign) = E.Pass)
      (label ^ " independent foreign original was not a valid exact structure");
    let result = no_material (label ^ " repinned substitution") request (bind request foreign) in
    require (at ["structure";"content_outcome"] (Check.report result) = str "fail" &&
      at ["structure";"structural_outcome"] (Check.report result) = str "pass")
      (label ^ " did not isolate independent exact material authority"))
    ["same-protein synonymous CDS","CCAUGGCCUAAGGAAAA";
     "same-protein UTR","GCAUGGCUUAAGGAAAA"];
  let wrong_product = literal |> put (molecule_path 0 @ ["sequence"]) (str "CCAUGGGUUAAGGAAAA") |> rebind_roles in
  let wrong = no_material "wrong full translated product" request wrong_product in
  require (structure_code "complete_product_spelling_mismatch" wrong) "Product mismatch diagnostic missing";
  List.iter (fun (label,sequence,code) ->
    let result = no_material label request
      (literal |> put (molecule_path 0 @ ["sequence"]) (str sequence) |> rebind_roles) in
    require (structure_code code result) (label ^ " lost ordinary translation diagnostic"))
    ["internal stop","CCAUGUAAUAAGGAAAA","internal_stop";
     "missing terminal stop","CCAUGGCUCAAGGAAAA","in_frame_terminal_stop_required";
     "wrong initiation","CCGUGGCUUAAGGAAAA","explicit_aug_start"];
  rejected "invalid_chemistry" (fun () ->
    run_check request (literal |> put (molecule_path 0 @ ["sequence"])
      (str "CCAUGGCUUAAGGAAAC") |> rebind_roles));
  let changed_cap = literal |> put (molecule_path 0 @ ["chemistry";"cap";"identity";"accession"])
    (str "different_supplied_cap") |> rebind_roles in
  let chemistry = no_material "full cap identity changed" request changed_cap in
  require (structure_code "original_full_chemistry_mismatch" chemistry) "Full chemistry mismatch was ignored";
  let foreign_provenance = literal |> put (molecule_path 0 @ ["provenance";"locator"])
    (str "Different retained material declaration") |> rebind_roles in
  let provenance = no_material "same-sequence foreign material provenance" request foreign_provenance in
  require (at ["structure";"content_outcome"] (Check.report provenance) = str "fail" &&
    at ["structure";"structural_outcome"] (Check.report provenance) = str "pass")
    "Exact original provenance was reduced to declared status or sequence identity";
  let modification = Json.Object [
    "schema_version",str "biocompiler.base_modification.v0.1";"id",str "all-u";
    "identity",Json.Object ["schema_version",str "biocompiler.chemical_identity.v0.1";
      "namespace",str "biocompiler.chemical";"accession",str "n1_methylpseudouridine";"version",str "1"];
    "canonical_base",str "U";"scope",str "all_matching_bases";"positions",arr [];
    "provenance",at (root_path 0 @ ["provenance"]) original] in
  let unpremised,unpremised_literal = with_modification modification original literal in
  let unsupported = no_material "modified CDS without nominal premise" unpremised unpremised_literal in
  require (Check.outcome unsupported = E.Unsupported && structure_code "modified_cds_uninterpreted" unsupported)
    "Recognized chemistry silently enabled a nominal translation premise";
  let nominal_original = with_nominal_definition (nominal_definition ()) original in
  let nominal,nominal_literal = with_modification modification nominal_original literal in
  let nominal_result = run_check nominal nominal_literal in
  require (Check.outcome nominal_result = E.Pass && Option.is_some (Check.accepted nominal_result))
    "Explicit source-bound nominal parent-U projection did not pass";
  let nominal_report = Check.report nominal_result in
  require (at ["structure";"profile"] nominal_report = str "biocompiler.policy_controlled_nominal_structure.v0.1" &&
    at ["structure";"physical_translation_status"] nominal_report = str "unassessed" &&
    at ["structure";"source_request_fingerprint"] nominal_report = str (R.fingerprint nominal))
    "Nominal structural evidence lost its explicit source or empirical boundary";
  require (Json.equal (Check.structure_evidence (Check.structure (Option.get (Check.accepted nominal_result))))
    (get "structure" nominal_report)) "Nominal material token lost independent structural evidence";
  require (List.map (get "translated_product") (Json.array (at ["structure";"members"] nominal_report)) = [str "MA";str "MG"])
    "Nominal parent-base translation changed exact expected products";
  ignore (Check.replay ~request:nominal ~candidate:(C.of_json nominal_literal) nominal_report);
  rejected "controlled_material_assessment_mismatch" (fun () ->
    Check.replay ~request:nominal ~candidate:(C.of_json nominal_literal) report);
  let positional = modification |> set "scope" (str "positions") |> set "positions" (arr [Json.int 3]) in
  let positional_request,positional_literal = with_modification positional nominal_original literal in
  require (Check.outcome (run_check positional_request positional_literal) = E.Pass)
    "Recognized explicit-position nominal parent-U projection did not pass";
  List.iter (fun (label,path,value) ->
    let changed = put path (str value) modification in
    let changed_request,changed_literal = with_modification changed nominal_original literal in
    let result = no_material label changed_request changed_literal in
    require (Check.outcome result = E.Unsupported && structure_code "modified_cds_uninterpreted" result)
      (label ^ " escaped the closed nominal chemistry identity"))
    ["foreign modification namespace",["identity";"namespace"],"software_fixture.chemical";
     "uninterpreted modified residue",["identity";"accession"],"uninterpreted_modified_u";
     "uninterpreted chemistry version",["identity";"version"],"2"];
  let altered_definition = nominal_definition () |> set "meaning" (str "Source asserts measured physical translation") in
  let altered_original = with_nominal_definition altered_definition original in
  let altered_request,altered_literal = with_modification modification altered_original literal in
  rejected "controlled_nominal_translation_premise" (fun () -> run_check altered_request altered_literal);
  let admitted_nominal = Admission.admit ~charge:(fun _ -> ()) nominal in
  rejected "controlled_nominal_translation_premise" (fun () -> Nominal.check
    ~admitted:admitted_nominal ~request ~candidate:(C.construction candidate) ());
  let admitted_unpremised = Admission.admit ~charge:(fun _ -> ()) unpremised in
  rejected "controlled_nominal_translation_premise" (fun () -> Nominal.check
    ~admitted:admitted_unpremised ~request:unpremised ~candidate:(C.construction (C.of_json unpremised_literal)) ());
  let wrong_nominal = nominal_literal |> put (molecule_path 0 @ ["sequence"])
    (str "CCAUGGGUUAAGGAAAA") |> rebind_roles in
  let wrong_nominal_result = no_material "nominal premise with wrong protein" nominal wrong_nominal in
  require (structure_code "complete_product_spelling_mismatch" wrong_nominal_result)
    "Nominal projection weakened full product correspondence";
  let nominal_chemistry_loss = nominal_literal |> put (molecule_path 0 @ ["chemistry";"modifications"])
    (arr []) |> rebind_roles in
  let lost_chemistry = no_material "nominal candidate removes declared chemistry" nominal nominal_chemistry_loss in
  require (structure_code "original_full_chemistry_mismatch" lost_chemistry)
    "Nominal projection erased declared chemical identity";
  let shortened = literal |> put ["construction";"member_order"] (arr [str "rna-a"])
    |> edit material_path (fun values -> arr [List.hd (Json.array values)]) |> rebind_roles in
  ignore (no_material "missing complete second member" request shortened);
  let swapped = literal |> edit ["construction";"member_order"] (fun values -> arr (List.rev (Json.array values)))
    |> edit material_path (fun values -> arr (List.rev (Json.array values))) in
  let ordering = no_material "swapped complete member order" request swapped in
  require (structure_code "original_exact_member_order" ordering) "Explicit order was silently normalized";
  let extra = at (molecule_path 1) literal |> set "id" (str "rna-extra")
    |> replace_text "rna-b.output.frame" "rna-extra.output.frame" in
  let extra_pair = literal |> edit ["construction";"member_order"]
    (fun values -> arr (Json.array values @ [str "rna-extra"]))
    |> edit material_path (fun values -> arr (Json.array values @ [extra])) in
  ignore (no_material "unrequested helper member" request extra_pair);
  let no_inventory = literal |> put ["construction";"inventory"] Json.Null in
  ignore (no_material "missing output inventory" request no_inventory);
  let exact_bounds = R.of_json (original |> put ["resources";"max_member_rna_nt"] (Json.int 17)
    |> put ["resources";"max_total_rna_nt"] (Json.int 34)) in
  require (Check.outcome (run_check exact_bounds (bind exact_bounds literal)) = E.Pass)
    "Exact inclusive member/total bounds failed";
  List.iter (fun (key,value) ->
    let limited = R.of_json (put ["resources";key] (Json.int value) original) in
    rejected "controlled_authority_admission" (fun () -> run_check limited (bind limited literal)))
    ["max_member_rna_nt",16;"max_total_rna_nt",33];
  rejected_any "unsupported model port alteration" (fun () ->
    let changed = R.of_json (put ["mechanism_model";"body";"ports";"4";"scope"]
      (str "encounter_generation") original) in run_check changed (bind changed literal));
  (* Admission alone fits this ceiling, while the complete material report does
     not. A previously valid structural body must not escape its original
     report allowance when the higher-level evidence is retained. *)
  let admission_size = String.length (Canonical.encode (get "admission" report)) in
  let report_limited = R.of_json (put ["budgets";"max_report_bytes"]
    (Json.int (admission_size + 256)) original) in
  rejected "controlled_material_publication_limit" (fun () ->
    run_check report_limited (bind report_limited literal));
  rejected "controlled_authority_request" (fun () ->
    R.of_json (put ["budgets";"max_work"] (Json.int 1) original));
  (* A complete typed request cannot carry a budget that already fails its own
     decoder. Leave enough for that decode, but not the next complete candidate
     decode, to exercise the checker's standalone live work owner separately. *)
  let checker_allowance = R.decoding_work request + 1024 in
  let work_limited = R.of_json (put ["budgets";"max_work"] (Json.int checker_allowance) original) in
  let work_candidate = C.of_json (bind work_limited literal) in
  let remaining_after_request = checker_allowance - R.decoding_work work_limited in
  require (remaining_after_request > 0 && C.decoding_work work_candidate > remaining_after_request)
    "Standalone checker exhaustion does not isolate the candidate decode budget";
  rejected "controlled_material_work_limit" (fun () ->
    Check.check ~request:work_limited ~candidate:work_candidate ());
  let allowance:R.budgets = R.budgets request in
  let parent = W.create ~profile:"controlled-material-test" ~error_code:"original_parent_exhausted"
    ~maximum:allowance.max_work () in
  W.charge parent 37;
  let fresh = Check.check ~parent ~request ~candidate () in
  require (Json.equal report (Check.report fresh)) "Prior producer work changed material evidence";
  require (W.remaining parent < allowance.max_work - 37) "Child semantic work escaped the live owner";
  let small = W.create ~profile:"controlled-material-test" ~error_code:"original_parent_exhausted" ~maximum:1 () in
  rejected "original_parent_exhausted" (fun () -> Check.check ~parent:small ~request ~candidate ());
  require (W.exhausted small) "Parent exhaustion was not sticky";
  rejected "controlled_material_work_limit" (fun () -> Check.check ~parent:small ~request ~candidate ());
  let cancelled = W.create ~retain_bytes:(fun _ -> raise Exit) ~profile:"controlled-cancel"
    ~error_code:"controlled-cancel" ~maximum:allowance.max_work () in
  let cancellation_propagated = try W.retain cancelled 1; false with Exit -> true in
  require cancellation_propagated "Caller cancellation was swallowed";
  let failed_again = try ignore (Check.check ~parent:cancelled ~request ~candidate ()); false with Exit -> true in
  require failed_again "Cancelled live owner produced material evidence";
  Printf.printf "controlled material checker: %d literal and independent adversarial checks\n" !checks
let () =
  try run () with Diagnostic.Error diagnostic ->
    let bounded limit value =
      if String.length value <= limit then str value else str "<diagnostic field exceeds logging bound>" in
    let detail = Json.Object [
      "event",str "unexpected_controlled_material_checker_diagnostic";
      "completed_checks",Json.int !checks;
      "code",bounded 256 diagnostic.code;
      "message",bounded 4096 diagnostic.message;
      "path",(match diagnostic.path with None -> Json.Null | Some value -> bounded 1024 value)] in
    Printf.eprintf "%s\n%!" (Canonical.encode detail);
    raise (Diagnostic.Error diagnostic)
