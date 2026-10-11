open Bioc_wire
module R = Bioc_domain.Policy_expression_material
module D = Bioc_domain.Policy_document
module K = Bioc_domain.Construction_content
module M = Bioc_domain.Molecule
module Pin = Bioc_domain.Pinned_identity
module A = Policy_expression_source_admission
module S = Policy_expression_structure_check
module W = Work_budget
let candidate_schema = "biocompiler.policy_expression_material_candidate.v0.1"
let implementation_version = "biocompiler.ocaml.policy_expression_material_check.v0.1"
let str value = Json.String value
let obj values = Json.Object values
let arr values = Json.Array values
let get key raw = Json.field key (Json.object_fields raw)
let text key raw = Json.string (get key raw)
type checked_expression_material = {
  request_value:R.t; source_value:A.t; structure_value:S.checked_structure; evidence_value:Json.t;
}
type result = {report_value:Json.t; accepted_value:checked_expression_material option; budget_value:W.t}
let budget (value:result) = value.budget_value
let report (value:result) = value.report_value
let accepted (value:result) = value.accepted_value
let request (value:checked_expression_material) = value.request_value
let source (value:checked_expression_material) = value.source_value
let structure (value:checked_expression_material) = value.structure_value
let evidence (value:checked_expression_material) = value.evidence_value
let measure budget raw = Bioc_domain.Policy_material_request.preflight
  ~max_bytes:4_000_000 ~max_nodes:100_000 ~max_depth:64 ~charge:(W.charge budget) raw
let fingerprint budget raw =
  let size = measure budget raw in
  W.charge budget size;
  let bytes = Canonical.encode_bounded ~max_bytes:4_000_000 raw in
  Diagnostic.require (size = String.length bytes) "policy_expression_accounting" "Canonical input size changed during expression checking.";
  W.charge budget size; Canonical.sha256 bytes
let check ~request:original ~candidate:proposed =
  let allowances = R.budgets original in
  let budget = W.create ~profile:R.resource_profile ~error_code:"policy_expression_material_work_limit"
    ~maximum:allowances.max_work () in
  W.charge budget (R.decoding_work original);
  (* Fresh source decoding and assessment use the complete original document.
     There is no acceptance-bearing input in this invocation. *)
  let request = R.of_json ~charge:(W.charge budget) (R.to_json original) in
  let source = A.admit ~charge:(W.charge budget) request in
  let candidate_raw = obj ["schema_version",str candidate_schema; "construction",K.to_json proposed] in
  ignore (measure budget candidate_raw);
  let candidate = K.of_json (get "construction" candidate_raw) in
  let structural = S.check ~parent:budget ~source ~candidate () in
  let selected = R.selection request and contract = R.expression_contract request in
  let maximum = A.maximum_rna_nt source in
  let inventory = match K.inventory candidate with
    | None -> [] | Some inventory -> K.Inventory.molecules inventory in
  let actual_length = match inventory with [value] -> Some (String.length (M.sequence value)) | _ -> None in
  W.charge budget (1 + List.length inventory);
  let bound_ok = match actual_length with Some length -> length <= maximum | None -> false in
  let structure_ok = Option.is_some (S.checked_structure structural) in
  let objective_ok = structure_ok && bound_ok in
  let source_pin = fingerprint budget (A.report source)
  and structure_pin = fingerprint budget (S.report structural) in
  let definitions = Json.array (get "definitions" (get "semantics" (D.program (A.document source)))) in
  let defined_ids = List.map (text "id") definitions in
  let suffix prefix value = if String.starts_with ~prefix value then
    Some (String.sub value (String.length prefix) (String.length value - String.length prefix)) else None in
  let premise_pins = obj ["source",str source_pin; "structure",str structure_pin;
    "contract",Pin.to_json contract.identity] in
  let disposition obligation =
    W.charge budget (String.length obligation + List.length defined_ids);
    (* The closed source admission proves absence of temporal/state/effect
       declarations. Their generic vocabulary obligations are explicitly N/A,
       never claims about execution, cancellation or physical persistence. *)
    match obligation with
    | "policy_execution_and_lowering" | "temporal_and_uncertainty_semantics"
    | "persistent_encounter_identity_lifetime" | "state_lifetime_capacity_and_inheritance"
    | "effect_authorization_feedback_and_cancellation" | "arbitration_fairness_and_conflict_resolution" ->
        "not_applicable", "closed_static_source_admission", obj ["source",str source_pin]
    | "safety_and_progress_satisfaction" | "requested_assurance_not_established"
    | "expression_material_correspondence" ->
        (if objective_ok then "discharged" else "unresolved"), "exact_static_encoding_and_length", premise_pins
    | "realizability_and_target_suitability" | "implementation_catalog_applicability"
    | "chassis_capability_and_delivery_suitability" ->
        (if objective_ok then "conditional" else "unresolved"), "supplied_expression_localization_and_recipient_premises", premise_pins
    | _ ->
      match suffix "requirement_satisfaction:" obligation with
      | Some id when id = A.objective_id source ->
          (if objective_ok then "discharged" else "unresolved"), "exact_static_encoding_and_length", premise_pins
      | _ -> match suffix "implementation_applicability:" obligation with
        | Some id when id = Pin.id selected.implementation ->
            (if objective_ok then "conditional" else "unresolved"), "complete_supplied_implementation_contract", premise_pins
        | _ -> match suffix "semantic_definition:" obligation with
          | Some id when List.mem id defined_ids ->
              let definition=List.find(fun value->text "id" value=id)definitions in
              let normative=[R.objective_definition();R.operation_definition();R.translation_definition()]in
              let definition_bytes=measure budget definition in
              List.iter(fun value->ignore(measure budget value);W.charge budget definition_bytes)normative;
              (* Canonical semantic digest traverses the complete definition;
                 reserve semantic projection, encoding and SHA before calling. *)
              W.charge budget(3*definition_bytes);
              let interpreted=List.exists(Json.equal definition)normative in
              (if interpreted then "discharged" else "conditional"),
              (if interpreted then "closed_normative_static_interpretation" else "resolved_original_context_or_component_premise"),
              obj ["source",str source_pin;"definition",R.definition_ref_to_json(R.definition_ref definition);
                "body",definition;"contract",Pin.to_json contract.identity]
          | _ -> "unresolved", "unimplemented_obligation", Json.Null in
  let obligations = A.unresolved_obligations source in
  let ledger = List.map (fun obligation -> let status,stage,evidence = disposition obligation in
    obj ["obligation",str obligation; "status",str status; "stage",str stage; "evidence",evidence]) obligations in
  let ledger_closed = List.for_all (fun row -> text "status" row <> "unresolved") ledger in
  let complete = objective_ok && ledger_closed in
  let candidate_pin = fingerprint budget candidate_raw in
  let invocation_pin = fingerprint budget (obj ["request",R.to_json request; "candidate",candidate_raw]) in
  let requirement = obj ["id",str (A.objective_id source); "path",str (A.objective_path source);
    "status",str (if objective_ok then "pass" else "fail");
    "product",Pin.to_json (A.product source); "member",str selected.member; "cds",str selected.cds;
    "maximum_rna_nt",Json.int maximum;
    "actual_rna_nt",(match actual_length with Some value -> Json.int value | None -> Json.Null);
    "length_status",str (if bound_ok then "pass" else "fail");
    "localization",A.localization source; "localization_status",str "supplied_premise";
    "diagnostics",arr (if bound_ok then [] else [obj ["code",str "expression_rna_length_requirement";
      "path",str (A.objective_path source); "message",str "The exact original RNA exceeds the source length bound or has no single complete member."]])] in
  let fields = ["schema_version",str "biocompiler.policy_expression_material_assessment.v0.1";
    "profile",str R.profile; "implementation",str implementation_version; "resource_profile",str R.resource_profile;
    "request_fingerprint",str (R.fingerprint request); "candidate_fingerprint",str candidate_pin;
    "invocation_fingerprint",str invocation_pin;
    "status",str (if complete then "checked_expression_material" else "not_accepted");
    "claim_scope",str "conditional_encoding_and_localization";
    "premise",str "supplied_expression_localization_recipient_and_nominal_translation_contracts";
    "source_admission",A.report source; "structure",S.report structural;
    "requirements",arr [requirement]; "obligations",arr ledger;
    "all_original_obligations_dispositioned",Json.Bool ledger_closed;
    "budgets",get "budgets" (R.to_json request);
    "empirical",str "unassessed"; "human_use",str "unassessed";
    "artifact",str "withheld"; "export",str "withheld"] in
  let usage work = obj ["unit",str "logical_data_visits_and_child_semantic_work";
    "charged_work",Json.int work; "request_decoding_work",Json.int (R.decoding_work request)] in
  let reserved = obj (fields @ ["usage",usage allowances.max_work]) in
  let output = W.create_output ~profile:R.resource_profile ~error_code:"policy_expression_publication_limit"
    ~max_bytes:allowances.max_report_bytes ~max_nodes:allowances.max_report_nodes () in
  let bytes = measure budget reserved in
  W.charge budget bytes; W.reserve_json output reserved;
  let report_value = obj (fields @ ["usage",usage (allowances.max_work - W.remaining budget)]) in
  let accepted_value = match complete,S.checked_structure structural with
    | true,Some structure_value -> Some {request_value=request; source_value=source; structure_value; evidence_value=report_value}
    | _ -> None in
  {report_value; accepted_value; budget_value=budget}
