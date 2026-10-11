open Bioc_wire
module D = Policy_document
module P = Pinned_identity
module A = Policy_mrna_structure
module M = Molecular_record
let schema_version = "biocompiler.policy_expression_material_request.v0.1"
let profile = "biocompiler.policy_single_expression_mrna.v0.1"
let contract_schema = "biocompiler.policy_expression_contract.v0.1"
let resource_profile = "biocompiler.policy_expression_material_resources.v0.1"
let max_work = 100_000_000
let parameter_ids = ["product_id"; "product_version"; "product_sha256"; "localization"; "maximum_rna_nt"]
let str value = Json.String value
let get key value = Json.field key (Json.object_fields value)
let exact keys value = Json.exact_fields keys (Json.object_fields value)
let require condition message = Diagnostic.require condition "policy_expression_material_request" message
let text raw = M.text ~maximum:256 raw
let digest raw =
  let value = Json.string raw in
  require (String.length value = 64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value)
    "Expected lowercase SHA-256 content identity.";
  value
let integer ceiling raw =
  let value = Json.integer raw in
  require (Z.sign value > 0 && Z.leq value (Z.of_int ceiling)) "Expression resource allowance exceeds its fixed positive bound.";
  Z.to_int value
let descriptor id category meaning = Json.Object [
  "$type", str "SemanticDefinition"; "id", str id; "version", str "1";
  "category", str category; "meaning", str meaning; "parameters", Json.Array [];
  "result", Json.Null; "clauses", Json.Array []; "assumptions", Json.Array [];
  "executor_kind", Json.Null; "subject_kind", Json.Null]
let objective_definition () = descriptor "biocompiler.expression.objective.v1" "requirement"
  "Exact source-selected complete product encoding and supplied conditional localization for one declared human immune recipient; no empirical expression or therapeutic function is established."
let operation_definition () = descriptor "biocompiler.expression.encode.v1" "operation"
  "Construct one complete original mRNA encoding the exact supplied product under the explicit expression/localization contract; no runtime action or biological realization is inferred."
let translation_definition () = descriptor "biocompiler.expression.nominal_translation.v1" "model"
  "Decode the explicitly declared canonical parent RNA bases with the standard genetic code and the selected one or two consecutive terminal stop codons; this nominal correspondence does not establish physical translation of modified nucleotides or biological expression."
type definition_ref = { id:string; version:string; digest:string }
let definition_ref_of_json raw =
  exact ["$type"; "id"; "version"; "digest"] raw;
  require (get "$type" raw = str "DefinitionRef") "Expected complete source DefinitionRef.";
  {id=text (get "id" raw); version=text (get "version" raw); digest=digest (get "digest" raw)}
let definition_ref_to_json (value:definition_ref) = Json.Object [
  "$type", str "DefinitionRef"; "id", str value.id; "version", str value.version; "digest", str value.digest]
let definition_ref raw =
  {id=text (get "id" raw); version=text (get "version" raw); digest=D.document_digest raw}
type selection = { objective:string; recipient:string; implementation:P.t; member:string; cds:string }
type material = { structure_sha256:string; member:string; cds:string }
type translation = { terminal_stop_codons:int; model:definition_ref }
type expression_contract = {
  identity:P.t; body:Json.t; operation:definition_ref; realization:definition_ref;
  product:P.t; recipient:Json.t; deployment:Json.t; localization:Json.t;
  material:material; translation:translation;
  dependencies:definition_ref list; evidence:definition_ref list;
}
type budgets = { max_work:int; max_report_bytes:int; max_report_nodes:int }
type t = {
  raw:Json.t; identity:string; decoding_work_value:int; document_value:D.t;
  project_context_value:Json.t;
  selection_value:selection; contract_value:expression_contract;
  structure_value:A.t; structure_identity:string; budget_values:budgets;
}
let of_json ?(charge=fun _ -> ()) raw =
  let work = ref 0 and allowance = ref max_work in
  let spend amount =
    Diagnostic.require (amount >= 0 && amount <= !allowance - !work)
      "policy_expression_material_work_limit" "Expression request decoding exhausted its work allowance.";
    charge amount; work := !work + amount in
  let preflight value = Policy_material_request.preflight
    ~max_bytes:4_000_000 ~max_nodes:100_000 ~max_depth:64 ~charge:spend value in
  let decode decoder value = ignore (preflight value); decoder value in
  let fingerprint value =
    let size = preflight value in
    spend size;
    let encoded = Canonical.encode_bounded ~max_bytes:4_000_000 value in
    require (String.length encoded = size) "Canonical expression accounting mismatch.";
    spend size; Canonical.sha256 encoded in
  ignore (preflight raw);
  exact ["schema_version"; "profile"; "project_context"; "document"; "selection"; "expression_contract"; "structure_authority"; "budgets"] raw;
  require (get "schema_version" raw = str schema_version && get "profile" raw = str profile)
    "Unsupported original expression-material request profile.";
  let budget = get "budgets" raw in
  exact ["profile"; "max_work"; "max_report_bytes"; "max_report_nodes"] budget;
  require (get "profile" budget = str resource_profile) "Unsupported expression resource profile.";
  let budget_values = {
    max_work=integer max_work (get "max_work" budget);
    max_report_bytes=integer (Limits.max_response_bytes - 6 * Limits.max_string_bytes - 65536) (get "max_report_bytes" budget);
    max_report_nodes=integer (Limits.max_json_nodes - 32) (get "max_report_nodes" budget)} in
  allowance := budget_values.max_work; spend 0;
  (* Bibliographic/rights text is retained exactly as supplied. Shape and digest
     binding do not establish publication authenticity, permissions or biology. *)
  let context_text maximum value =
    let value = Json.string value in
    spend (2 * String.length value + 1);
    Json.validate_utf8 value;
    require (String.length value <= maximum && D.nonblank_text value)
      "Project metadata must contain bounded nonblank UTF-8 text.";
    value in
  let project_context_value = get "project_context" raw in
  exact ["project_id"; "title"; "sources"; "assumptions"] project_context_value;
  ignore (context_text 128 (get "project_id" project_context_value));
  ignore (context_text 4096 (get "title" project_context_value));
  let sources = M.array ~maximum:128 (get "sources" project_context_value) in
  require (sources <> []) "Project metadata requires its complete source-record inventory.";
  let ids = List.map (fun source ->
    spend 7;
    exact ["id"; "locator"; "version"; "sha256"; "role"; "reuse_terms"] source;
    List.iter (fun key -> ignore (context_text 4096 (get key source)))
      ["locator"; "version"; "role"; "reuse_terms"];
    ignore (digest (get "sha256" source));
    context_text 4096 (get "id" source)) sources in
  let widest_id = List.fold_left (fun maximum id -> max maximum (String.length id)) 0 ids in
  spend (List.length ids + List.length ids * List.length ids * widest_id);
  require (List.length (List.sort_uniq String.compare ids) = List.length ids)
    "Project source IDs must be unique.";
  List.iter (fun value -> ignore (context_text 4096 value))
    (M.array ~maximum:128 (get "assumptions" project_context_value));
  let document_value = decode (D.of_expression_json ~path:"/document") (get "document" raw) in
  let select = get "selection" raw in
  exact ["objective"; "recipient"; "implementation"; "member"; "cds"] select;
  let selection_value = {
    objective=text (get "objective" select); recipient=text (get "recipient" select);
    implementation=decode P.of_json (get "implementation" select);
    member=text (get "member" select); cds=text (get "cds" select)} in
  require (P.kind selection_value.implementation = P.Registry)
    "Selected original implementation entry requires a registry-kind complete-content pin.";
  let contract = get "expression_contract" raw in
  exact ["identity"; "body"] contract;
  let identity = decode P.of_json (get "identity" contract) and body = get "body" contract in
  exact ["schema_version"; "operation"; "realization"; "product"; "recipient"; "deployment";
         "localization"; "material"; "translation"; "dependencies"; "evidence"; "claim_scope"] body;
  require (get "schema_version" body = str contract_schema &&
    get "claim_scope" body = str "conditional_encoding_and_localization")
    "Unsupported expression contract or claim scope.";
  require (P.kind identity = P.Model && P.content_fingerprint identity = fingerprint body)
    "Expression model identity does not match the complete original contract body.";
  let material = get "material" body in
  exact ["structure_sha256"; "member"; "cds"] material;
  let translation = get "translation" body in
  exact ["interpretation"; "terminal_stop_codons"; "model"] translation;
  require (get "interpretation" translation = str "nominal_canonical_parent_bases")
    "Only the explicit conditional nominal parent-base interpretation is supported.";
  let translation = {terminal_stop_codons=integer 2 (get "terminal_stop_codons" translation);
    model=definition_ref_of_json (get "model" translation)} in
  let refs key = M.array ~maximum:32 (get key body) |> List.map definition_ref_of_json in
  let dependencies = refs "dependencies" and evidence = refs "evidence" in
  require (List.length dependencies + List.length evidence <= 32)
    "Expression dependency/evidence inventory exceeds its combined bound.";
  let recipient = get "recipient" body and deployment = get "deployment" body
  and localization = get "localization" body in
  exact ["$type"; "id"; "version"; "lineage"; "subtype"; "activation_states";
    "differentiation_states"; "capabilities"; "operational_model"; "environment";
    "interfaces"; "species"; "recipient_class"] recipient;
  exact ["$type"; "id"; "bindings"; "environment"; "delivery"; "payload"; "route"] deployment;
  exact ["$type"; "id"; "version"; "category"; "meaning"; "parameters"; "result";
    "clauses"; "assumptions"; "executor_kind"; "subject_kind"] localization;
  require (get "$type" recipient = str "ChassisProfile" &&
    get "$type" deployment = str "Deployment" && get "$type" localization = str "SemanticDefinition")
    "Expression contract must retain complete typed source context and localization bodies.";
  let contract_value = {
    identity; body; operation=definition_ref_of_json (get "operation" body);
    realization=definition_ref_of_json (get "realization" body);
    product=decode P.of_json (get "product" body); recipient; deployment; localization;
    material={structure_sha256=digest (get "structure_sha256" material);
      member=text (get "member" material); cds=text (get "cds" material)};
    translation; dependencies; evidence} in
  require (P.kind contract_value.product = P.Reference) "Expression product requires a reference-kind identity.";
  let structure_value = decode A.of_json (get "structure_authority" raw) in
  let structure_identity = fingerprint (A.to_json structure_value) in
  let identity = fingerprint raw in
  {raw; identity; decoding_work_value= !work; document_value; project_context_value; selection_value;
   contract_value; structure_value; structure_identity; budget_values}
let to_json value = value.raw
let fingerprint value = value.identity
let decoding_work value = value.decoding_work_value
let document value = value.document_value
let project_context value = value.project_context_value
let selection value = value.selection_value
let expression_contract value = value.contract_value
let structure_authority value = value.structure_value
let structure_fingerprint value = value.structure_identity
let budgets value = value.budget_values
