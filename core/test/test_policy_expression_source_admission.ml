(* Artificial source, independent literal material and service controls. The
   native suite must run hosted; these fixtures supply no biological evidence. *)
open Bioc_wire
open Bioc_domain
module E = Policy_expression_material
module Check = Bioc_checker.Policy_expression_source_admission
module D = Policy_document
module P = Pinned_identity
module A = Policy_mrna_structure
module K = Construction_content
module N = Molecule
module H = Molecule_chemistry
module Material = Bioc_checker.Policy_expression_material_check
module Structure = Bioc_checker.Policy_expression_structure_check
module Legacy = Bioc_checker.Policy_mrna_structure_check
module W = Bioc_checker.Work_budget
module Service = Bioc_service.Policy_expression_material_service
module Producer = Bioc_producer_service.Policy_expression_material_producer
let checks = ref 0
let require condition message = incr checks; if not condition then failwith message
let str value = Json.String value
let obj fields = Json.Object fields
let arr values = Json.Array values
let get key raw = Json.field key (Json.object_fields raw)
let set key value raw = obj ((key,value) :: List.remove_assoc key (Json.object_fields raw))
let rec at path raw = match path with [] -> raw | key :: rest ->
  at rest (match raw with Json.Array values -> List.nth values (int_of_string key) | _ -> get key raw)
let rec edit path change raw = match path with [] -> change raw | key :: rest ->
  match raw with
  | Json.Array values -> arr (List.mapi (fun index value -> if index = int_of_string key then edit rest change value else value) values)
  | _ -> set key (edit rest change (get key raw)) raw
let put path value = edit path (fun _ -> value)
let rejected label action = incr checks; match action () with
  | _ -> failwith ("Unexpected admission: " ^ label)
  | exception Diagnostic.Error _ -> ()
let rejected_code code action = incr checks; match action () with
  | _ -> failwith ("Expected rejection: " ^ code)
  | exception Diagnostic.Error diagnostic -> require (diagnostic.code = code)
      ("Expected " ^ code ^ "; got " ^ diagnostic.code)
let read path =
  let channel = open_in_bin path in
  Fun.protect ~finally:(fun () -> close_in_noerr channel) (fun () ->
    let size = in_channel_length channel in
    require (size > 0 && size < 1_000_000) "Artificial fixture read bound";
    Json.parse (really_input_string channel size))
let reference kind id = obj ["$type",str "Ref"; "id",str id; "kind",str kind]
let definition id category = obj ["$type",str "SemanticDefinition"; "id",str id; "version",str "1";
  "category",str category; "meaning",str "Artificial conditional software premise; biological function unassessed.";
  "parameters",arr []; "result",Json.Null; "clauses",arr []; "assumptions",arr [];
  "executor_kind",Json.Null; "subject_kind",Json.Null]
let pin definition = E.definition_ref_to_json (E.definition_ref definition)
let content_pin kind id body = P.to_json (P.make ~kind ~id ~version:"1" ~content_fingerprint:(Canonical.fingerprint body))
let parameter id kind value = obj ["$type",str "Parameter"; "id",str id;
  "value_type",obj ["$type",str "TypeSpec"; "kind",str kind; "unit",Json.Null; "entity_kind",Json.Null];
  "value",value; "lower",Json.Null; "upper",Json.Null; "selection",str "fixed"]
let repin_contract raw =
  let body = at ["expression_contract";"body"] raw in
  put ["expression_contract";"identity";"content_fingerprint"] (str (Canonical.fingerprint body)) raw
let repin_entry raw =
  let entry = at ["document";"implementations";"implementations";"0"] raw in
  put ["selection";"implementation";"content_fingerprint"] (str (Canonical.fingerprint entry)) raw
let fixture authority =
  let product = content_pin P.Reference "artificial.complete.product" (Policy_mrna_structure.product_content_json "MA") in
  let authority = put ["members";"0";"product";"identity"] product authority in
  let objective_def = E.objective_definition () and operation_def = E.operation_definition ()
  and translation_def = E.translation_definition () in
  let realization = definition "artificial.expression" "model"
  and localization = definition "artificial.surface" "spatial"
  and environment = definition "artificial.environment" "environment"
  and delivery_def = definition "artificial.delivery" "delivery"
  and chassis_model = definition "artificial.chassis_model" "model"
  and capability = definition "artificial.capability" "capability" in
  let role = obj ["$type",str "Role"; "id",str "recipient"; "requires",arr [pin capability];
    "population",Json.Null; "lineage_role",Json.Bool false] in
  let parameters = [parameter "product_id" "text" (get "id" product);
    parameter "product_version" "text" (get "version" product);
    parameter "product_sha256" "text" (get "content_fingerprint" product);
    parameter "localization" "text" (get "id" localization);
    parameter "maximum_rna_nt" "integer" (Json.int 1000)] in
  let objective = obj ["$type",str "Requirement"; "id",str "encode"; "kind",str "objective";
    "description",str "Artificial exact encoding objective, not a biological claim.";
    "scope",obj ["$type",str "Scope"; "kind",str "executor"; "subject",reference "Role" "recipient"];
    "condition",Json.Null; "response",Json.Null; "deadline",Json.Null; "lower",Json.Null;
    "upper",Json.Null; "horizon",Json.Null; "assumptions",arr [];
    "applies_to",arr (reference "Role" "recipient" :: List.map (reference "Parameter") E.parameter_ids);
    "contract",pin objective_def; "trigger",Json.Null; "clock",Json.Null] in
  let program = obj ["$type",str "PolicyProgram"; "id",str "artificial.expression.source";
    "semantics",obj ["$type",str "SemanticBundle"; "id",str "artificial.definitions"; "version",str "1";
      "definitions",arr [objective_def;operation_def;translation_def;realization;localization;
        environment;delivery_def;chassis_model;capability]; "profile",str D.profile];
    "declarations",arr (role :: parameters @ [objective]); "source_map",arr []; "profile",str D.profile] in
  let chassis = obj ["$type",str "ChassisProfile"; "id",str "artificial.human_immune"; "version",str "1";
    "lineage",str "immune"; "subtype",str "artificial"; "activation_states",arr [];
    "differentiation_states",arr []; "capabilities",arr [pin capability]; "operational_model",pin chassis_model;
    "environment",arr [pin environment]; "interfaces",arr []; "species",str "human"; "recipient_class",str "immune"] in
  let deployment = obj ["$type",str "Deployment"; "id",str "artificial.deployment";
    "bindings",arr [obj ["$type",str "RoleBinding"; "role",reference "Role" "recipient"; "chassis",chassis]];
    "environment",arr [pin environment]; "delivery",obj ["$type",str "DeliveryContract";
      "id",str "artificial.delivery_contract"; "intended_recipients",arr [reference "Role" "recipient"];
      "arrival",pin delivery_def; "expression",pin delivery_def; "activation",pin delivery_def;
      "co_delivery",str "none_required"; "contract",pin delivery_def; "assumptions",arr []];
    "payload",obj ["$type",str "RNAConstraints"; "design_count",Json.int 1; "member_count",Json.int 1;
      "helper_count",Json.int 0; "copy_number",Json.Null; "dose",Json.Null; "orf_count",Json.int 1;
      "product_count",Json.int 1; "payload_persistence",Json.Null; "effector_persistence",Json.Null; "format",str "RNA"];
    "route",str "in_vivo"] in
  let entry = obj ["$type",str "ImplementationBinding"; "id",str "artificial.expression.entry"; "version",str "1";
    "operation",pin operation_def; "realization",pin realization; "chassis",arr [get "id" chassis];
    "payload_formats",arr [str "RNA"]; "dependencies",arr [pin translation_def]; "evidence",arr []] in
  let document = obj ["$type",str "BuildRequest"; "program",program; "deployment",deployment;
    "implementations",obj ["$type",str "ImplementationCatalogLock"; "id",str "artificial.catalog";
      "version",str "1"; "implementations",arr [entry]];
    "assurance",obj ["$type",str "AssuranceRequest"; "requirements",arr [str "encode"];
      "level",str "structural"; "horizon",str "not_applicable"; "assumptions",arr []; "tolerances",arr []];
    "profile",str D.expression_source_profile] in
  let body = obj ["schema_version",str E.contract_schema; "operation",pin operation_def;
    "realization",pin realization; "product",product; "recipient",chassis; "deployment",deployment;
    "localization",localization; "material",obj ["structure_sha256",str (Canonical.fingerprint authority);
      "member",str "payload"; "cds",str "cds"];
    "translation",obj ["interpretation",str "nominal_canonical_parent_bases"; "terminal_stop_codons",Json.int 1;
      "model",pin translation_def]; "dependencies",arr [pin translation_def]; "evidence",arr [];
    "claim_scope",str "conditional_encoding_and_localization"] in
  obj ["schema_version",str E.schema_version; "profile",str E.profile; "document",document;
    "project_context",obj ["project_id",str "artificial.expression.project";
      "title",str "Artificial expression software control";
      "sources",arr [obj ["id",str "artificial.source"; "locator",str "fixture:artificial-expression";
        "version",str "1"; "sha256",str (Canonical.sha256 "artificial-source-bytes");
        "role",str "software-control"; "reuse_terms",str "artificial fixture"]];
      "assumptions",arr [str "Biological function is unassessed."]];
    "selection",obj ["objective",str "encode"; "recipient",str "recipient";
      "implementation",content_pin P.Registry "artificial.expression.entry" entry; "member",str "payload"; "cds",str "cds"];
    "expression_contract",obj ["identity",content_pin P.Model "artificial.expression.contract" body; "body",body];
    "structure_authority",authority; "budgets",obj ["profile",str E.resource_profile; "max_work",Json.int E.max_work;
      "max_report_bytes",Json.int 1_000_000; "max_report_nodes",Json.int 100_000]]
let admit raw = Check.admit (E.of_json raw)

(* M1 O01--O23 native contract oracle. Status/stage/path expectations below are
   literal normative test authority, independent of producer disposition code.
   Child checkers supply separately replayed dependency bytes, never row meanings. *)
type m1_evidence = M1_source | M1_join | M1_definition of string
let m1_contract_rows = [
  "policy_execution_and_lowering", "not_applicable", "not_applicable", "closed_static_source_admission", "/document/program", M1_source;
  "temporal_and_uncertainty_semantics", "not_applicable", "not_applicable", "closed_static_source_admission", "/document/program", M1_source;
  "safety_and_progress_satisfaction", "not_applicable", "not_applicable", "closed_static_source_admission", "/document/program", M1_source;
  "realizability_and_target_suitability", "conditional", "unresolved", "supplied_expression_localization_and_recipient_premises", "/document/deployment", M1_join;
  "chassis_capability_and_delivery_suitability", "conditional", "unresolved", "supplied_expression_localization_and_recipient_premises", "/document/deployment", M1_join;
  "implementation_catalog_applicability", "conditional", "unresolved", "supplied_expression_localization_and_recipient_premises", "/document/implementations", M1_join;
  "requested_assurance_not_established", "conditional", "unresolved", "supplied_expression_localization_and_recipient_premises", "/document/assurance", M1_join;
  "implementation_applicability:artificial.expression.entry", "conditional", "unresolved", "complete_supplied_implementation_contract", "/document/implementations/implementations/0", M1_join;
  "requirement_satisfaction:encode", "discharged", "unresolved", "exact_static_encoding_and_length", "/document/program/declarations/6", M1_join;
  "expression_material_correspondence", "conditional", "unresolved", "supplied_expression_localization_and_recipient_premises", "/document", M1_join;
  "semantic_definition:biocompiler.expression.objective.v1", "discharged", "discharged", "closed_normative_static_interpretation", "/document/program/semantics/definitions/0", M1_definition "biocompiler.expression.objective.v1";
  "semantic_definition:biocompiler.expression.encode.v1", "discharged", "discharged", "closed_normative_static_interpretation", "/document/program/semantics/definitions/1", M1_definition "biocompiler.expression.encode.v1";
  "semantic_definition:biocompiler.expression.nominal_translation.v1", "discharged", "discharged", "closed_normative_static_interpretation", "/document/program/semantics/definitions/2", M1_definition "biocompiler.expression.nominal_translation.v1";
  "semantic_definition:artificial.expression", "conditional", "conditional", "resolved_original_context_or_component_premise", "/document/program/semantics/definitions/3", M1_definition "artificial.expression";
  "semantic_definition:artificial.surface", "conditional", "conditional", "resolved_original_context_or_component_premise", "/document/program/semantics/definitions/4", M1_definition "artificial.surface";
  "semantic_definition:artificial.environment", "conditional", "conditional", "resolved_original_context_or_component_premise", "/document/program/semantics/definitions/5", M1_definition "artificial.environment";
  "semantic_definition:artificial.delivery", "conditional", "conditional", "resolved_original_context_or_component_premise", "/document/program/semantics/definitions/6", M1_definition "artificial.delivery";
  "semantic_definition:artificial.chassis_model", "conditional", "conditional", "resolved_original_context_or_component_premise", "/document/program/semantics/definitions/7", M1_definition "artificial.chassis_model";
  "semantic_definition:artificial.capability", "conditional", "conditional", "resolved_original_context_or_component_premise", "/document/program/semantics/definitions/8", M1_definition "artificial.capability"
]
let m1_items key value = Json.array (get key value)
let m1_named id values = List.find (fun value -> get "id" value = str id) values
let m1_index id values =
  match List.filter_map (fun (index,value) -> if get "id" value = str id then Some index else None)
    (List.mapi (fun index value -> index,value) values) with
  | [index] -> index
  | _ -> failwith ("M1 oracle requires exactly one original ID: " ^ id)
let m1_definition_ref body = obj ["$type",str "DefinitionRef"; "id",get "id" body;
  "version",get "version" body; "digest",str (D.document_digest body)]
let m1_definitions raw = Json.array (at ["document";"program";"semantics";"definitions"] raw)
let m1_sort_rows values = List.sort (fun left right ->
  String.compare (Json.string (get "obligation" left)) (Json.string (get "obligation" right))) values
let m1_ids rows = List.map (fun row -> Json.string (get "obligation" row)) rows
let m1_extra = "derived_quantity_operation_semantics"
let m1_extra_row = obj ["obligation",str m1_extra; "path",str "/document";
  "status",str "unresolved"; "stage",str "unimplemented_obligation"; "evidence",Json.Null]
let m1_envelope literal = obj ["schema_version",str "biocompiler.policy_expression_material_candidate.v0.1";
  "construction",literal]
let m1_expect ~success ~extra raw literal report =
  let original = E.of_json raw and candidate = K.of_json literal in
  require (get "request_fingerprint" report = str (E.fingerprint original) &&
    get "candidate_fingerprint" report = str (Canonical.fingerprint (m1_envelope literal)) &&
    get "invocation_fingerprint" report = str (Canonical.fingerprint
      (obj ["request",raw; "candidate",m1_envelope literal]))) "M1 report lost exact invocation bindings";
  let source = Check.admit original in
  let source_report = Check.report source in
  let structural = Structure.check ~source ~candidate () in
  let structure_report = Structure.report structural in
  require (Json.equal (get "source_admission" report) source_report &&
    Json.equal (get "structure" report) structure_report) "M1 child reports differ from fresh independent checking";
  let source_pin = str (Canonical.fingerprint source_report)
  and structure_pin = str (Canonical.fingerprint structure_report)
  and contract = at ["expression_contract";"identity"] raw in
  let definitions = m1_definitions raw in
  require (List.length definitions = 9 &&
    List.length (List.sort_uniq String.compare (List.map (fun row -> Json.string (get "id" row)) definitions)) = 9)
    "M1 artificial oracle definition inventory changed";
  let entries = Json.array (at ["document";"implementations";"implementations"] raw) in
  require (List.length entries = 1) "M1 oracle needs exactly one original implementation";
  let entry = List.hd entries in
  let selected = at ["selection";"implementation"] raw in
  require (get "id" entry = str "artificial.expression.entry" && get "id" selected = get "id" entry &&
    get "version" selected = get "version" entry &&
    get "content_fingerprint" selected = str (Canonical.fingerprint entry)) "M1 original implementation identity mismatch";
  let declarations = Json.array (at ["document";"program";"declarations"] raw) in
  let expected = List.map (fun (id,passed,failed,stage,path,kind) ->
    let path,evidence = match kind with
    | M1_source -> path,obj ["source",source_pin]
    | M1_join ->
        let path = if id = "requirement_satisfaction:encode" then
          "/document/program/declarations/" ^ string_of_int (m1_index "encode" declarations) else path in
        path,obj ["source",source_pin; "structure",structure_pin; "contract",contract]
    | M1_definition id ->
        let index = m1_index id definitions and body = m1_named id definitions in
        "/document/program/semantics/definitions/" ^ string_of_int index,
        obj ["source",source_pin; "definition",m1_definition_ref body; "body",body; "contract",contract] in
    obj ["obligation",str id; "path",str path; "status",str (if success then passed else failed);
      "stage",str stage; "evidence",evidence]) m1_contract_rows in
  let expected = m1_sort_rows (expected @ (if extra then [m1_extra_row] else [])) in
  require (Json.equal (get "obligations" report) (arr expected))
    "M1 complete independently specified ledger differs (status, stage, path, evidence, order or exact keys)";
  let ids = m1_ids expected in
  let original_ids = List.filter ((<>) "expression_material_correspondence") ids in
  require (get "unresolved_obligations" (Check.source_assessment source) = arr (List.map str original_ids) &&
    get "unresolved_obligations" source_report = arr (List.map str ids)) "M1 original/admission ledger census mismatch";
  require (get "schema_version" report = str "biocompiler.policy_expression_material_assessment.v0.2" &&
    get "implementation" report = str "biocompiler.ocaml.policy_expression_material_check.v0.2")
    "M1 corrected interpretation must carry v0.2 assessment/checker identities";
  require (get "all_original_obligations_dispositioned" report = Json.Bool (success && not extra) &&
    get "status" report = str (if success && not extra then "checked_expression_material" else "not_accepted") &&
    at ["requirements";"0";"status"] report = str (if success then "pass" else "fail"))
    "M1 objective result was confused with complete conditional acceptance";
  List.iter (fun key -> require (get key report = str "unassessed") "M1 promoted biological/human claims") ["empirical";"human_use"];
  require (get "claim_scope" report = str "conditional_encoding_and_localization" &&
    get "premise" report = str "supplied_expression_localization_recipient_and_nominal_translation_contracts" &&
    get "physical_translation" structure_report = str "unassessed" &&
    get "artifact" report = str "withheld" && get "export" report = str "withheld") "M1 lost conditional or publication boundaries";
  let count status = List.length (List.filter (fun row -> get "status" row = str status) expected) in
  require ((count "not_applicable",count "discharged",count "conditional",count "unresolved") =
    (if success then (3,4,12,(if extra then 1 else 0)) else (3,3,6,7))) "M1 literal disposition census changed"
let m1_repin_definition id replacement raw =
  let rec replace = function
    | Json.Object fields ->
        (match List.assoc_opt "$type" fields,List.assoc_opt "id" fields with
        | Some (Json.String "SemanticDefinition"),Some (Json.String found) when found = id -> replacement
        | Some (Json.String "DefinitionRef"),Some (Json.String found) when found = id -> m1_definition_ref replacement
        | _ -> obj (List.map (fun (key,value) -> key,replace value) fields))
    | Json.Array values -> arr (List.map replace values)
    | value -> value in
  replace raw |> repin_entry |> repin_contract
let m1_expr op kind args value = obj ["$type",str "Expr"; "op",str op;
  "value_type",obj ["$type",str "TypeSpec"; "kind",str kind; "unit",Json.Null; "entity_kind",Json.Null];
  "args",arr args; "value",value; "ref",Json.Null; "scope",Json.Null; "contract",Json.Null;
  "duration",Json.Null; "clock",Json.Null; "coverage",Json.Null; "binding",Json.Null]
let m1_generic raw = Bioc_checker.Policy_check.check (D.of_expression_json (get "document" raw))
let m1_valid raw =
  let result = m1_generic raw in
  require (get "status" result = str "valid") ("M1 source probe is not generically valid: " ^ Canonical.encode result)
let m1_rehash wrapper = set "report_fingerprint" (str (Canonical.fingerprint (get "report" wrapper))) wrapper
let m1_rebind_source wrapper =
  let source_pin = str (Canonical.fingerprint (at ["report";"source_admission"] wrapper)) in
  wrapper |> edit ["report";"obligations"] (fun rows -> arr (List.map (fun row ->
    match get "evidence" row with
    | Json.Object fields when List.mem_assoc "source" fields -> edit ["evidence"] (set "source" source_pin) row
    | _ -> row) (Json.array rows))) |> m1_rehash
let m1_row id report = List.find (fun row -> get "obligation" row = str id) (m1_items "obligations" report)
let m1_edit_row id change = edit ["report";"obligations"] (fun rows ->
  arr (List.map (fun row -> if get "obligation" row = str id then change row else row) (Json.array rows)))
let m1_replay_reject raw wrapped saved =
  require (get "report_fingerprint" saved = str (Canonical.fingerprint (get "report" saved)))
    "M1 replay attack has a stale outer report hash";
  rejected_code "policy_expression_replay" (fun () -> Service.handle ~operation:"replay-policy-expression-material"
    (obj ["request",raw; "candidate",wrapped; "report",saved]))
let m1_mutate_inventory change_ids change_rows saved =
  saved |> edit ["report";"source_admission";"source_assessment";"unresolved_obligations"]
    (fun ids -> arr (change_ids (Json.array ids)))
  |> edit ["report";"source_admission";"unresolved_obligations"] (fun ids -> arr (change_ids (Json.array ids)))
  |> edit ["report";"obligations"] (fun rows -> arr (change_rows (Json.array rows))) |> m1_rebind_source
let m1_native_controls raw literal =
  let wrapped = m1_envelope literal in
  let check request content = Material.check ~request:(E.of_json request) ~candidate:(K.of_json content) in
  let export request content = Service.check ~export:true ~request ~candidate:(m1_envelope content) in
  let with_bound count = put ["document";"program";"declarations";"5";"value"] (Json.int count) raw in
  require (get "schema_version" raw = str "biocompiler.policy_expression_material_request.v0.1" &&
    get "profile" raw = str "biocompiler.policy_single_expression_mrna.v0.1" &&
    at ["document";"profile"] raw = str "biocompiler.policy_expression_source.v0.1" &&
    at ["budgets";"profile"] raw = str "biocompiler.policy_expression_material_resources.v0.1" &&
    at ["expression_contract";"body";"schema_version"] raw = str "biocompiler.policy_expression_contract.v0.1")
    "O19 M1 changed an original request/source/resource/contract version";
  (* O01: literal success, private acceptance token and independent child evidence. *)
  let passed = check raw literal in
  m1_expect ~success:true ~extra:false raw literal (Material.report passed);
  require (Option.is_some (Material.accepted passed)) "O01 lost conditional acceptance token";
  let saved = Service.check ~export:false ~request:raw ~candidate:wrapped in
  require (get "implementation" saved = str "biocompiler.ocaml.policy_expression_material.v0.2" &&
    get "schema_version" saved = str "biocompiler.core.policy_expression_material.v1" &&
    get "validation_scope" saved = str "policy-single-expression-mrna-v0.1" &&
    get "artifact" saved = Json.Null) "O01 service identity or check-only publication changed";
  List.iter (fun advertised -> require (get "implementation" advertised = str "biocompiler.ocaml.policy_expression_material.v0.2")
    "O19 service capability advertises obsolete interpretation") [Service.profile;Service.producer_profile];
  (* O02--O03: exact supported bound; failure does not create safety obligations. *)
  let exact = with_bound 17 and short = with_bound 16 in
  m1_expect ~success:true ~extra:false exact literal (Material.report (check exact literal));
  let failed = check short literal in
  m1_expect ~success:false ~extra:false short literal (Material.report failed);
  require (Material.accepted failed = None && at ["requirements";"0";"actual_rna_nt"] (Material.report failed) = Json.int 17 &&
    at ["requirements";"0";"length_status"] (Material.report failed) = str "fail" &&
    at ["requirements";"0";"diagnostics";"0";"code"] (Material.report failed) = str "expression_rna_length_requirement" &&
    at ["requirements";"0";"diagnostics";"0";"path"] (Material.report failed) = str "/document/program/declarations/6")
    "O03 lost exact bound diagnostic or withheld token";
  rejected_code "policy_expression_export_not_accepted" (fun () -> export short literal);
  let failed_saved = Service.check ~export:false ~request:short ~candidate:wrapped in
  (* O04: changed MA -> ME bases, with only untrusted molecule pins refreshed. *)
  let changed_literal = put ["inventory";"molecules";"0";"sequence"] (str "CCAUGGAAUAAGGAAAA") literal in
  let molecule = N.of_json (at ["inventory";"molecules";"0"] changed_literal) in
  let changed_literal = put ["inventory";"role_instances";"0";"subject_fingerprint"] (str (N.fingerprint molecule)) changed_literal in
  let changed_checked = check raw changed_literal in
  m1_expect ~success:false ~extra:false raw changed_literal (Material.report changed_checked);
  require (Material.accepted changed_checked = None &&
    at ["structure";"content_outcome"] (Material.report changed_checked) = str "fail") "O04 source-unauthorized product mutation accepted";
  rejected_code "policy_expression_export_not_accepted" (fun () -> export raw changed_literal);
  (* O05--O06: real original mutations; unsupported probes pass generic checking. *)
  List.iter (fun path -> let edited = put path (str "different.product") raw |> repin_contract in
    m1_valid edited; rejected_code "policy_expression_source_binding" (fun () -> admit edited))
    [["expression_contract";"body";"product";"id"];["document";"program";"declarations";"1";"value"]];
  let yes = m1_expr "literal" "truth" [] (Json.Bool true) in
  List.iter (fun kind ->
    let requirement = at ["document";"program";"declarations";"6"] raw
      |> set "id" (str ("actual." ^ kind)) |> set "kind" (str kind) |> set "contract" Json.Null
      |> set "condition" yes |> set "response" (if kind = "progress" then yes else Json.Null) in
    let edited = edit ["document";"program";"declarations"] (fun values -> arr (Json.array values @ [requirement])) raw in
    m1_valid edited; rejected_code "policy_expression_source_unsupported" (fun () -> admit edited)) ["safety";"progress"];
  let temporal = put ["document";"program";"declarations";"6";"horizon"] (str "unbounded_requested") raw in
  m1_valid temporal; rejected_code "policy_expression_source_unsupported" (fun () -> admit temporal);
  (* O07: dynamic locators are resolved from originals, never descriptor positions. *)
  let reordered = raw |> edit ["document";"program";"declarations"] (fun rows -> arr (List.rev (Json.array rows)))
    |> edit ["document";"program";"semantics";"definitions"] (fun rows -> arr (List.rev (Json.array rows))) in
  let reordered_report = Material.report (check reordered literal) in
  m1_expect ~success:true ~extra:false reordered literal reordered_report;
  require (get "request_fingerprint" reordered_report <> get "request_fingerprint" (Material.report passed) &&
    at ["source_admission";"source_artifact_digest"] reordered_report <>
    at ["source_admission";"source_artifact_digest"] (Material.report passed)) "O07 reordered original artifact retained stale identity";
  (* O08--O09: complete, consistently repinned normative and supplied bodies. *)
  List.iter (fun id ->
    let body = m1_named id (m1_definitions raw) |> set "meaning" (str "Changed complete normative descriptor") in
    let edited = m1_repin_definition id body raw in
    m1_valid edited; rejected_code "policy_expression_source_unsupported" (fun () -> admit edited))
    ["biocompiler.expression.objective.v1";"biocompiler.expression.encode.v1";"biocompiler.expression.nominal_translation.v1"];
  let supplied_body = m1_named "artificial.environment" (m1_definitions raw)
    |> set "meaning" (str "Changed explicitly supplied environment premise")
    |> set "assumptions" (arr [str "Retained artificial assumption; empirical status remains unassessed."]) in
  let supplied = m1_repin_definition "artificial.environment" supplied_body raw in
  m1_expect ~success:true ~extra:false supplied literal (Material.report (check supplied literal));
  let unconsumed = edit ["document";"program";"semantics";"definitions"]
    (fun values -> arr (Json.array values @ [definition "m1.unconsumed" "environment"])) raw in
  m1_valid unconsumed; rejected_code "policy_expression_source_unsupported" (fun () -> admit unconsumed);
  (* O10: negative defense against the separately recorded M2 admission gap.
     No regression requires continued acceptance of unused formal parameters. *)
  let integer value = m1_expr "literal" "integer" [] (Json.int value) in
  let arithmetic = m1_expr "eq" "truth" [m1_expr "multiply" "integer" [integer 2;integer 3] Json.Null;integer 6] Json.Null in
  let extra_body = m1_named "artificial.environment" (m1_definitions raw) |> set "clauses"
    (arr [obj ["$type",str "ContractClause"; "kind",str "assumption";
      "description",str "Artificial arithmetic demand retained for unresolved-obligation checking."; "expression",arithmetic]]) in
  let extra_request = m1_repin_definition "artificial.environment" extra_body raw in
  m1_valid extra_request;
  let extra_checked = check extra_request literal in
  m1_expect ~success:true ~extra:true extra_request literal (Material.report extra_checked);
  require (Material.accepted extra_checked = None) "O10 genuine unknown source obligation received a private token";
  rejected_code "policy_expression_export_not_accepted" (fun () -> export extra_request literal);
  let extra_saved = Service.check ~export:false ~request:extra_request ~candidate:wrapped in
  let ordinary_ids = m1_ids (get "report" saved |> m1_items "obligations") in
  (* O11: coherent deletion of every required row from all returned inventories. *)
  List.iter (fun id ->
    m1_mutate_inventory (List.filter ((<>) (str id)))
      (List.filter (fun row -> get "obligation" row <> str id)) saved |> m1_replay_reject raw wrapped) ordinary_ids;
  (* O12: phantom runtime/arbitrary obligations cannot acquire a fallback premise. *)
  List.iter (fun id -> List.iter (fun status ->
    let phantom = obj ["obligation",str id; "path",str "/document"; "status",str status;
      "stage",str "closed_static_source_admission"; "evidence",obj ["source",str "placeholder"]] in
    m1_mutate_inventory (fun ids -> List.sort compare (str id :: ids))
      (fun rows -> m1_sort_rows (phantom :: rows)) saved |> m1_replay_reject raw wrapped)
    ["not_applicable";"conditional";"discharged"])
    ["persistent_encounter_identity_lifetime";"state_lifetime_capacity_and_inheritance";
     "effect_authorization_feedback_and_cancellation";"arbitration_fairness_and_conflict_resolution";"m1.arbitrary"];
  (* O13--O15: duplicates, every status category, every exact reason and path. *)
  List.iter (fun id ->
    let row = m1_row id (get "report" saved) in
    m1_mutate_inventory (fun ids -> if List.mem (str id) ids then List.sort compare (str id :: ids) else ids)
      (fun rows -> m1_sort_rows (row :: rows)) saved |> m1_replay_reject raw wrapped;
    let different = if get "status" row = str "discharged" then "conditional" else "discharged" in
    saved |> m1_edit_row id (set "status" (str different)) |> m1_rehash |> m1_replay_reject raw wrapped;
    List.iter (fun (key,value) -> saved |> m1_edit_row id (set key value) |> m1_rehash |> m1_replay_reject raw wrapped)
      ["stage",str "m1.changed_reason"; "path",str (if get "path" row = str "/document/assurance" then "/document/program" else "/document/assurance")]) ordinary_ids;
  let duplicate_id = "semantic_definition:artificial.environment" in
  m1_mutate_inventory (fun ids -> List.sort compare (str duplicate_id :: ids))
    (fun rows -> m1_sort_rows (m1_row duplicate_id (get "report" failed_saved) :: rows)) failed_saved
    |> m1_replay_reject short wrapped;
  (* O16: remove/substitute every required dependency key, with fresh outer hash. *)
  List.iter (fun id ->
    let evidence = get "evidence" (m1_row id (get "report" saved)) in
    List.iter (fun (key,_) ->
      saved |> m1_edit_row id (edit ["evidence"] (fun value -> obj (List.remove_assoc key (Json.object_fields value))))
        |> m1_rehash |> m1_replay_reject raw wrapped;
      let replacement = match key with
        | "source" | "structure" -> str (String.make 64 '0')
        | "contract" -> set "content_fingerprint" (str (String.make 64 '0')) (get key evidence)
        | "definition" -> set "digest" (str (String.make 64 '0')) (get key evidence)
        | "body" -> set "meaning" (str "Contradictory supplied descriptor") (get key evidence)
        | _ -> failwith "Unexpected oracle evidence key" in
      let substitute row = if key = "body" then row
        |> put ["evidence";"body"] replacement
        |> put ["evidence";"definition"] (m1_definition_ref replacement)
        else edit ["evidence"] (set key replacement) row in
      saved |> m1_edit_row id substitute |> m1_rehash |> m1_replay_reject raw wrapped)
      (Json.object_fields evidence)) ordinary_ids;
  failed_saved |> m1_edit_row "requirement_satisfaction:encode"
    (put ["evidence";"source"] (str (Canonical.fingerprint (at ["report";"source_admission"] saved))))
    |> m1_rehash |> m1_replay_reject short wrapped;
  let changed_saved = Service.check ~export:false ~request:raw ~candidate:(m1_envelope changed_literal) in
  changed_saved |> m1_edit_row "expression_material_correspondence"
    (put ["evidence";"structure"] (str (Canonical.fingerprint (at ["report";"structure"] saved))))
    |> m1_rehash |> m1_replay_reject raw (m1_envelope changed_literal);
  (* O17--O18: genuine extra cannot disappear or be promoted by report surgery. *)
  extra_saved |> edit ["report";"source_admission";"unresolved_obligations"]
    (fun ids -> arr (List.filter ((<>) (str m1_extra)) (Json.array ids)))
    |> edit ["report";"obligations"] (fun rows -> arr (List.filter (fun row -> get "obligation" row <> str m1_extra) (Json.array rows)))
    |> m1_rebind_source |> m1_replay_reject extra_request wrapped;
  List.iter (fun promote -> extra_saved |> promote |> m1_rehash |> m1_replay_reject extra_request wrapped)
    [put ["report";"status"] (str "checked_expression_material");
     put ["report";"all_original_obligations_dispositioned"] (Json.Bool true);
     m1_edit_row m1_extra (set "status" (str "conditional"));
     (fun value -> value |> put ["report";"status"] (str "checked_expression_material")
       |> put ["report";"all_original_obligations_dispositioned"] (Json.Bool true)
       |> m1_edit_row m1_extra (set "status" (str "conditional")))];
  (* O19: all seven old/current version mixtures, plus the coherent old ledger. *)
  let old_versions = [(["report";"schema_version"],"biocompiler.policy_expression_material_assessment.v0.1");
    (["report";"implementation"],"biocompiler.ocaml.policy_expression_material_check.v0.1");
    (["implementation"],"biocompiler.ocaml.policy_expression_material.v0.1")] in
  List.iter (fun mask ->
    let edited = List.fold_left (fun value (index,(path,version)) ->
      if mask land (1 lsl index) <> 0 then put path (str version) value else value)
      saved (List.mapi (fun index value -> index,value) old_versions) in
    edited |> m1_rehash |> m1_replay_reject raw wrapped) [1;2;3;4;5;6;7];
  let old_ledger = saved |> edit ["report";"obligations"] (fun rows -> arr (List.map (fun row ->
    let row = obj (List.remove_assoc "path" (Json.object_fields row)) in
    if List.mem (Json.string (get "obligation" row)) ["safety_and_progress_satisfaction";
      "requested_assurance_not_established";"expression_material_correspondence"] then
      row |> set "status" (str "discharged") |> set "stage" (str "exact_static_encoding_and_length")
      |> set "evidence" (get "evidence" (m1_row "requirement_satisfaction:encode" (get "report" saved))) else row)
      (Json.array rows))) in
  let old_ledger = List.fold_left (fun value (path,version) -> put path (str version) value) old_ledger old_versions in
  old_ledger |> m1_rehash |> m1_replay_reject raw wrapped;
  (* O20 native slice: exact paired export and embedded v0.2 assessment. Archive,
     ResearchProject reopen and CAR peers remain the separate SDK/campaign suite. *)
  let fasta = ">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n" in
  List.iter (fun request ->
    let exported = export request literal in
    let artifact = get "artifact" exported and report = get "report" exported in
    let manifest = get "manifest" artifact in
    m1_expect ~success:true ~extra:false request literal report;
    require (get "schema_version" artifact = str "biocompiler.policy_expression_mrna_export.v0.1" &&
      get "schema_version" manifest = str "biocompiler.policy_expression_mrna_manifest.v0.1" &&
      Json.equal (get "bindings" manifest) (obj [
        "request_fingerprint",str (E.fingerprint (E.of_json request));
        "candidate_fingerprint",str (Canonical.fingerprint wrapped);
        "invocation_fingerprint",str (Canonical.fingerprint (obj ["request",request; "candidate",wrapped]));
        "assessment_fingerprint",str (Canonical.fingerprint report)])) "O20 manifest binding/version boundary differs";
    require (get "fasta" artifact = str fasta && get "fasta_sha256" artifact = str (Canonical.sha256 fasta) &&
      get "fasta_sha256" manifest = str (Canonical.sha256 fasta) &&
      get "manifest_sha256" artifact = str (Canonical.fingerprint manifest) &&
      Json.equal (get "request" manifest) request && Json.equal (get "candidate" manifest) wrapped &&
      Json.equal (get "assessment" manifest) report &&
      at ["bindings";"assessment_fingerprint"] manifest = str (Canonical.fingerprint report) &&
      Json.equal (at ["members";"0";"molecule"] manifest) (at ["inventory";"molecules";"0"] literal))
      "O20 exact paired export lost original authority or RNA/chemistry bytes";
    List.iter (fun key -> require (get key manifest = str "unassessed") "O20 export upgraded evidence") ["empirical";"human_use"])
    [raw;exact];
  require (E.fingerprint (E.of_json raw) <> E.fingerprint (E.of_json exact)) "O02 supported bound failed to rebind originals";
  (* O21: reserved correspondence must not originate in the generic child, even
     while final union cardinality and all visible ledger rows remain unchanged. *)
  List.iter (fun (request,saved) -> saved |> edit ["report";"source_admission";"source_assessment";"unresolved_obligations"]
    (fun ids -> arr (List.sort compare (str "expression_material_correspondence" :: Json.array ids)))
    |> m1_rebind_source |> m1_replay_reject request wrapped) [raw,saved;short,failed_saved];
  (* O22: actual original catalog census and exact selected identity mismatches. *)
  let entry = at ["document";"implementations";"implementations";"0"] raw in
  List.iter (fun entries -> let edited = put ["document";"implementations";"implementations"] (arr entries) raw in
    m1_valid edited; rejected_code "policy_expression_source_unsupported" (fun () -> admit edited))
    [[];[entry;set "id" (str "second.entry") entry]];
  List.iter (fun (field,value) -> let edited = put ["selection";"implementation";field] value raw in
    m1_valid edited; rejected_code "policy_expression_source_binding" (fun () -> admit edited))
    ["id",str "different.entry";"version",str "2";"content_fingerprint",str (String.make 64 '0')];
  (* O23: full original duplicate IDs, before any set or path-map construction. *)
  let duplicate = m1_named "artificial.environment" (m1_definitions raw) in
  List.iter (fun duplicate ->
    let edited = edit ["document";"program";"semantics";"definitions"] (fun rows -> arr (Json.array rows @ [duplicate])) raw in
    let generic = m1_generic edited in
    require (get "status" generic = str "invalid" &&
      List.exists (fun diagnostic -> get "code" diagnostic = str "duplicate_definition") (m1_items "diagnostics" generic))
      "O23 duplicate original definition was hidden by set construction";
    rejected_code "policy_expression_source_invalid" (fun () -> admit edited))
    [duplicate;duplicate |> set "version" (str "2") |> set "meaning" (str "Conflicting duplicate original body")]

let run fixture_path =
  let material_fixture = read fixture_path in
  let raw = fixture (at ["request";"material_contract";"body";"structure_authority"] material_fixture) in
  let original = E.of_json raw in
  require (Json.equal (E.to_json original) raw) "Original request was normalized or lost";
  require (E.decoding_work original > 0) "Request decoding work was omitted";
  rejected "ordinary v0.1 source decoder" (fun () -> D.of_json (get "document" raw));
  let admitted = Check.admit original in
  require (Check.maximum_rna_nt admitted = 1000 && Check.objective_id admitted = "encode") "Wrong source resolution";
  require (Check.objective_path admitted = "/document/program/declarations/6") "Lost exact source location";
  let source = Check.source_assessment admitted in
  require (get "status" source = str "valid") "Fresh generic source check did not pass";
  let obligations = Check.unresolved_obligations admitted in
  List.iter (fun value -> require (List.mem (Json.string value) obligations) "Generic obligation was dropped")
    (Json.array (get "unresolved_obligations" source));
  require (List.mem "expression_material_correspondence" obligations) "New correspondence obligation was omitted";
  require (get "export" (Check.report admitted) = str "withheld" &&
    get "expression_claim" (Check.report admitted) = str "withheld" &&
    get "empirical_realization" (Check.report admitted) = str "unassessed") "Source admission promoted a material/biological claim";
  let changed = put ["document";"program";"declarations";"5";"value"] (Json.int 999) raw in
  require (Check.maximum_rna_nt (admit changed) = 999) "Supported exact constraint edit was ignored";
  require (E.fingerprint (E.of_json changed) <> E.fingerprint original) "Source constraint edit did not change binding";
  let reordered = admit (edit ["document";"program";"declarations"]
    (fun values -> arr (List.rev (Json.array values))) raw) in
  require (Check.objective_path reordered = "/document/program/declarations/0" &&
    Check.maximum_rna_nt reordered = 1000) "Declaration order became an implicit semantic dependency";
  let two_stops = E.of_json (repin_contract
    (put ["expression_contract";"body";"translation";"terminal_stop_codons"] (Json.int 2) raw)) in
  require ((E.expression_contract two_stops).translation.terminal_stop_codons = 2)
    "Explicit two-stop model was lost during decoding";
  require (get "export" (Check.report (Check.admit two_stops)) = str "withheld")
    "Source-only two-stop admission granted unchecked sequence acceptance";
  List.iter (fun (path,value) -> rejected "closed/malformed request" (fun () -> admit (put path value raw))) [
    ["schema_version"],str "unknown"; ["profile"],str "unknown";
    ["selection";"implementation";"kind"],str "source";
    ["expression_contract";"identity";"content_fingerprint"],str (String.make 64 '0');
    ["expression_contract";"body";"translation";"terminal_stop_codons"],Json.int 0;
    ["expression_contract";"body";"translation";"terminal_stop_codons"],Json.int 3;
    ["budgets";"max_work"],Json.int 1];
  rejected "extra stored assessment" (fun () -> admit (set "assessment" (Check.report admitted) raw));
  List.iter (fun (path,value) -> rejected_code "policy_expression_source_binding"
    (fun () -> admit (repin_contract (put path value raw)))) [
    ["selection";"member"],str "foreign"; ["selection";"cds"],str "foreign";
    ["expression_contract";"body";"recipient";"subtype"],str "different";
    ["expression_contract";"body";"product";"id"],str "different.product";
    ["expression_contract";"body";"localization";"meaning"],str "Changed unproved localization"];
  rejected_code "policy_expression_source_unsupported" (fun () -> admit
    (put ["document";"program";"declarations";"5";"value"] (Json.int 0) raw));
  let unknown_objective = put ["document";"program";"semantics";"definitions";"0";"meaning"]
    (str "Different unsupported objective meaning") raw in
  let unknown_objective = put ["document";"program";"declarations";"6";"contract"]
    (pin (at ["document";"program";"semantics";"definitions";"0"] unknown_objective)) unknown_objective in
  rejected_code "policy_expression_source_unsupported" (fun () -> admit unknown_objective);
  let missing_dependency = raw
    |> put ["document";"implementations";"implementations";"0";"dependencies"] (arr [])
    |> put ["expression_contract";"body";"dependencies"] (arr []) |> repin_entry |> repin_contract in
  rejected_code "policy_expression_source_binding" (fun () -> admit missing_dependency);
  let extra = set "id" (str "unsupported.second.objective") (at ["document";"program";"declarations";"6"] raw) in
  rejected_code "policy_expression_source_unsupported" (fun () -> admit (edit ["document";"program";"declarations"]
    (fun values -> arr (Json.array values @ [extra])) raw));
  rejected_code "policy_expression_source_unsupported" (fun () -> admit (edit ["document";"program";"semantics";"definitions"]
    (fun values -> arr (Json.array values @ [definition "unconsumed.model" "model"])) raw));
  let source_map = arr [obj ["$type",str "SourceSpan"; "declaration_id",str "encode";
    "file",str "independent.py"; "line",Json.int 1; "column",Json.int 0; "pattern",Json.Null]] in
  let mapped = E.of_json (put ["document";"program";"source_map"] source_map raw) in
  ignore (Check.admit mapped);
  require (D.fingerprint (E.document mapped) = D.fingerprint (E.document original) &&
    D.artifact_digest (E.document mapped) <> D.artifact_digest (E.document original) &&
    E.fingerprint mapped <> E.fingerprint original) "Semantic digest was confused with complete artifact identity";
  rejected_code "forced_meter" (fun () -> Check.admit ~charge:(fun _ -> Diagnostic.fail "forced_meter" "Stop before more work") original);
  require (Json.equal (E.project_context original) (get "project_context" raw)) "Original project metadata was lost";
  List.iter (fun (path,value) ->
    let edited = put path value raw in
    ignore (admit edited);
    require (E.fingerprint (E.of_json edited) <> E.fingerprint original)
      "Original project metadata edit escaped request identity") [
    ["project_context";"project_id"],str "different.project";
    ["project_context";"title"],str "Different title";
    ["project_context";"sources";"0";"locator"],str "fixture:changed";
    ["project_context";"sources";"0";"version"],str "2";
    ["project_context";"sources";"0";"reuse_terms"],str "Unresolved rights declaration";
    ["project_context";"assumptions"],arr [str "Changed original assumption"]];
  let spaced = put ["project_context";"title"] (str "  retained exactly  ") raw in
  require (get "title" (E.project_context (E.of_json spaced)) = str "  retained exactly  ")
    "Project text was silently trimmed";
  List.iter (fun (path,value) -> rejected "malformed project context" (fun () -> E.of_json (put path value raw))) [
    ["project_context";"project_id"],str (String.make 129 'x');
    ["project_context";"title"],str "\194\160";
    ["project_context";"title"],str (String.make 4097 'x');
    ["project_context";"sources"],arr [];
    ["project_context";"sources";"0";"sha256"],str (String.make 64 'A');
    ["project_context";"assumptions"],arr (List.init 129 (fun _ -> str "x"))];
  rejected "duplicate source IDs" (fun () -> E.of_json (edit ["project_context";"sources"]
    (fun values -> arr (Json.array values @ Json.array values)) raw));
  let source_inventory count = arr (List.init count (fun index ->
    set "id" (str ("source." ^ string_of_int index)) (at ["project_context";"sources";"0"] raw))) in
  ignore (E.of_json (put ["project_context";"sources"] (source_inventory 128) raw));
  rejected "source inventory bound" (fun () -> E.of_json (put ["project_context";"sources"] (source_inventory 129) raw));
  rejected "extra source field" (fun () -> E.of_json (edit ["project_context";"sources";"0"]
    (set "publication_verified" (Json.Bool true)) raw));
  rejected "extra project authority" (fun () -> E.of_json (edit ["project_context"] (set "accepted" (Json.Bool true)) raw));
  rejected "missing original project context" (fun () -> E.of_json (obj (List.remove_assoc "project_context" (Json.object_fields raw))));
  (* The candidate below is separately retained literal data. No expected bases,
     geometry, molecule chemistry or product are obtained from the producer. *)
  let literal = at ["candidate_parts";"construction"] material_fixture in
  m1_native_controls raw literal;
  let candidate = K.of_json literal in
  let envelope candidate = obj ["schema_version",str Material.candidate_schema; "construction",candidate] in
  let wrapped = envelope literal in
  let checked = Material.check ~request:original ~candidate in
  let report = Material.report checked in
  require (Option.is_some (Material.accepted checked) && get "status" report = str "checked_expression_material")
    "Complete independent literal source/material pair was not accepted";
  require (at ["requirements";"0";"actual_rna_nt"] report = Json.int 17 &&
    at ["structure";"members";"0";"translated_product"] report = str "MA")
    "Independent literal RNA length/product mismatch";
  require (get "all_original_obligations_dispositioned" report = Json.Bool true &&
    List.sort String.compare (List.map (fun row -> Json.string (get "obligation" row)) (Json.array (get "obligations" report))) =
    List.sort String.compare obligations) "Original obligation census was not preserved by material conjunction";
  let chassis = List.find (fun row -> get "obligation" row = str "chassis_capability_and_delivery_suitability")
    (Json.array (get "obligations" report)) in
  require (get "status" chassis = str "conditional" && get "empirical" report = str "unassessed" &&
    get "human_use" report = str "unassessed" && at ["structure";"physical_translation"] report = str "unassessed")
    "Conditional material checking upgraded biological or recipient premises";
  let generated = Producer.compile (obj ["request",raw]) in
  require (Json.equal (get "candidate" generated) wrapped)
    "Untrusted producer differs from independently authored complete literal candidate";
  let service = Service.check ~export:false ~request:raw ~candidate:wrapped in
  require (Json.equal generated service && get "artifact" service = Json.Null)
    "Producer bypassed fresh independent checking or published an unchecked artifact";
  let replay request candidate report = Service.handle ~operation:"replay-policy-expression-material"
    (obj ["request",request; "candidate",candidate; "report",report]) in
  require (Json.equal (replay raw wrapped service) service) "Fresh full service replay was not stable";
  List.iter (fun (path,value) -> rejected_code "policy_expression_replay" (fun () ->
    replay raw wrapped (put path value service))) [
    ["report";"status"],str "accepted"; ["artifact"],obj [];
    ["request_fingerprint"],str (String.make 64 '0');
    ["usage";"total_charged_work"],Json.int 1];
  rejected_code "policy_expression_replay" (fun () -> replay changed wrapped service);
  rejected_code "policy_expression_replay" (fun () -> replay
    (put ["project_context";"sources";"0";"version"] (str "2") raw) wrapped service);
  let exported = Service.check ~export:true ~request:raw ~candidate:wrapped in
  let artifact = get "artifact" exported in
  let fasta = ">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n" in
  require (get "fasta" artifact = str fasta && get "fasta_sha256" artifact = str (Canonical.sha256 fasta))
    "Export changed the independently supplied exact RNA bytes";
  let manifest = get "manifest" artifact in
  require (Json.equal (get "request" manifest) raw && Json.equal (get "candidate" manifest) wrapped &&
    Json.equal (at ["members";"0";"molecule"] manifest) (at ["inventory";"molecules";"0"] literal) &&
    get "manifest_sha256" artifact = str (Canonical.fingerprint manifest))
    "Export lost complete project authority, original chemistry or artifact byte identity";
  require (get "empirical" manifest = str "unassessed" && get "human_use" manifest = str "unassessed")
    "Manifest upgraded software material correspondence into human/biological evidence";
  let total result = Json.integer (at ["usage";"total_charged_work"] result) in
  require (Z.gt (total service) (Json.integer (at ["usage";"checker_charged_work"] service)) &&
    Z.gt (total exported) (total service)) "Service/export publication work escaped the live invocation budget";
  (* A supported source edit must change admission: the exact boundary passes,
     while one nucleotide less retains the source diagnostic and withholds export. *)
  let bound maximum = put ["document";"program";"declarations";"5";"value"] (Json.int maximum) raw in
  let exact_bound = Service.check ~export:true ~request:(bound 17) ~candidate:wrapped in
  require (at ["artifact";"fasta"] exact_bound = str fasta &&
    get "request_fingerprint" exact_bound <> get "request_fingerprint" exported)
    "Supported source bound edit did not freshly check and rebind unchanged exact material";
  let too_long = Material.check ~request:(E.of_json (bound 16)) ~candidate in
  require (Material.accepted too_long = None &&
    at ["requirements";"0";"diagnostics";"0";"code"] (Material.report too_long) = str "expression_rna_length_requirement" &&
    at ["requirements";"0";"diagnostics";"0";"path"] (Material.report too_long) = str (Check.objective_path admitted))
    "Rejected source length edit lost its original objective diagnostic";
  rejected_code "policy_expression_export_not_accepted" (fun () -> Service.check ~export:true ~request:(bound 16) ~candidate:wrapped);
  (* Only untrusted content pins are recomputed after literal mutations. The
     separately supplied original source/authority remains authoritative. *)
  let repin_literal authority value =
    let molecule = N.of_json (at ["inventory";"molecules";"0"] value) in
    value |> put ["authority_fingerprint"] (str (K.authority_fingerprint ~template:(A.template authority) ~member_order:(A.member_order authority)))
      |> put ["inventory";"role_instances";"0";"subject_fingerprint"] (str (N.fingerprint molecule)) in
  let synonymous = repin_literal (E.structure_authority original)
    (put ["inventory";"molecules";"0";"sequence"] (str "CCAUGGCCUAAGGAAAA") literal) in
  let tampered = Material.check ~request:original ~candidate:(K.of_json synonymous) in
  require (Material.accepted tampered = None &&
    at ["structure";"structural_outcome"] (Material.report tampered) = str "pass" &&
    at ["structure";"content_outcome"] (Material.report tampered) = str "fail")
    "Equal translation and self-consistent content hashes authorized a source-unauthorized base edit";
  rejected_code "policy_expression_export_not_accepted" (fun () -> Service.check ~export:true ~request:raw ~candidate:(envelope synonymous));
  rejected_code "policy_expression_replay" (fun () -> replay raw (envelope synonymous) service);
  let repin_structure request authority = request |> put ["structure_authority"] authority
    |> put ["expression_contract";"body";"material";"structure_sha256"] (str (Canonical.fingerprint authority)) |> repin_contract in
  (* Explicit literal insertion of UAG after UAA: coordinates shift only for
     the declared molecule space/span types, not arbitrary source integers. *)
  let rec with_second_stop value = match value with
    | Json.String "CCAUGGCUUAAGGAAAA" -> str "CCAUGGCUUAAUAGGGAAAA"
    | Json.Array values -> arr (List.map with_second_stop values)
    | Json.Object fields ->
        let value = obj (List.map (fun (key,value) -> key,with_second_stop value) fields) in
        (match List.assoc_opt "schema_version" fields with
         | Some (Json.String "biocompiler.molecule_coordinate_space.v0.1") -> set "length" (Json.int 20) value
         | Some (Json.String "biocompiler.molecule_index_span.v0.1") ->
             List.fold_left (fun value key -> let index = Z.to_int (Json.integer (get key value)) in
               if index >= 11 then set key (Json.int (index+3)) value else value) value ["start";"end"]
         | _ -> value)
    | _ -> value in
  let two_authority = with_second_stop (get "structure_authority" raw) in
  let two_request = repin_structure raw two_authority
    |> put ["expression_contract";"body";"translation";"terminal_stop_codons"] (Json.int 2) |> repin_contract in
  let two_literal = repin_literal (A.of_json two_authority) (with_second_stop literal) in
  let two_checked = Material.check ~request:(E.of_json two_request) ~candidate:(K.of_json two_literal) in
  require (Option.is_some (Material.accepted two_checked) &&
    at ["structure";"members";"0";"translated_product"] (Material.report two_checked) = str "MA" &&
    at ["requirements";"0";"actual_rna_nt"] (Material.report two_checked) = Json.int 20)
    "Two declared terminal stops did not preserve the independent complete MA product";
  require (Json.equal (get "candidate" (Producer.compile (obj ["request",two_request]))) (envelope two_literal))
    "Two-stop producer differs from independently transformed literal geometry/sequence";
  let one_for_two = repin_contract (put ["expression_contract";"body";"translation";"terminal_stop_codons"] (Json.int 1) two_request) in
  require (Material.accepted (Material.check ~request:(E.of_json one_for_two) ~candidate:(K.of_json two_literal)) = None &&
    Material.accepted (Material.check ~request:two_stops ~candidate) = None)
    "One/two-stop translation premises were interchangeable";
  (* A supplied modification is represented exactly, with an explicit nominal
     parent-base premise. The legacy structural profile must still reject it. *)
  let molecule_path = ["template";"sources";"0";"molecule"] in
  let provenance = Molecular_record.Provenance.of_json (at (molecule_path @ ["provenance"]) (get "structure_authority" raw)) in
  let chemical = H.Chemical_identity.make ~namespace:"software_fixture.chemical" ~accession:"artificial_modified_u" ~version:"1" in
  let modification scope positions = H.Modification.to_json (H.Modification.make ~id:"modified-u"
    ~identity:chemical ~canonical_base:'U' ~scope ~positions ~provenance) in
  List.iter (fun modified ->
    let authority = get "structure_authority" raw
      |> put (molecule_path @ ["chemistry";"modifications"]) (arr [modified])
      |> put ["members";"0";"chemistry";"modifications"] (arr [modified]) in
    let modified_request = repin_structure raw authority in
    let modified_literal = literal |> put ["inventory";"molecules";"0";"chemistry";"modifications"] (arr [modified])
      |> repin_literal (A.of_json authority) in
    let content = K.of_json modified_literal in
    let result = Material.check ~request:(E.of_json modified_request) ~candidate:content in
    require (Option.is_some (Material.accepted result) &&
      at ["structure";"physical_translation"] (Material.report result) = str "unassessed")
      "Explicit nominal modified-base correspondence was lost or promoted to biological translation";
    require (Json.equal (get "candidate" (Producer.compile (obj ["request",modified_request]))) (envelope modified_literal))
      "Nominal modification producer changed independent literal chemistry";
    let legacy = Legacy.check ~authority:(A.of_json authority) ~candidate:content () in
    require (Legacy.checked_structure legacy = None && Legacy.outcome legacy = Construction_assessment.Unsupported)
      "New modified-base profile weakened legacy structural acceptance";
    let export = Service.check ~export:true ~request:modified_request ~candidate:(envelope modified_literal) in
    require (at ["artifact";"manifest";"members";"0";"molecule";"chemistry";"modifications"] export = arr [modified])
      "Export erased the exact nominal modified nucleotide declaration")
    [modification H.Modification.Positions [3]; modification H.Modification.All_matching_bases []];
  let wrong_parent = put ["canonical_base"] (str "A") (modification H.Modification.Positions [3]) in
  rejected "wrong declared canonical parent" (fun () -> E.of_json (repin_structure raw
    (get "structure_authority" raw |> put (molecule_path @ ["chemistry";"modifications"]) (arr [wrong_parent])
      |> put ["members";"0";"chemistry";"modifications"] (arr [wrong_parent]))));
  let structural = Structure.check ~source:admitted ~candidate () in
  ignore (Structure.replay ~source:admitted ~candidate (Structure.report structural));
  rejected_code "policy_expression_structure_assessment_mismatch" (fun () -> Structure.replay ~source:admitted ~candidate
    (set "physical_translation" (str "pass") (Structure.report structural)));
  let parent = W.create ~profile:"expression-parent-control" ~error_code:"expression_parent_exhausted" ~maximum:1 () in
  rejected_code "expression_parent_exhausted" (fun () -> Structure.check ~parent ~source:admitted ~candidate ());
  let decode_only = put ["budgets";"max_work"] (Json.int (E.decoding_work original)) raw in
  rejected_code "policy_expression_material_work_limit" (fun () -> Material.check
    ~request:(E.of_json decode_only) ~candidate);
  (* An allowance sufficient for the actual checker is still insufficient for
     the larger service wrapper. Publication cannot borrow an unmetered PASS. *)
  let publication_bound = put ["budgets";"max_work"] (at ["usage";"checker_charged_work"] service) raw in
  require (Option.is_some (Material.accepted (Material.check ~request:(E.of_json publication_bound) ~candidate)))
    "Publication-bound control no longer isolates completed material checking";
  rejected_code "policy_expression_material_work_limit" (fun () -> Service.check
    ~export:false ~request:publication_bound ~candidate:wrapped);
  rejected_code "policy_expression_publication_limit" (fun () -> Material.check
    ~request:(E.of_json (put ["budgets";"max_report_bytes"] (Json.int 1) raw)) ~candidate);
  rejected_code "policy_expression_publication_limit" (fun () -> Material.check
    ~request:(E.of_json (put ["budgets";"max_report_nodes"] (Json.int 1) raw)) ~candidate);
  Printf.printf "Expression source/material/service controls: %d; artificial conditional software evidence only.\n" !checks
