open Bioc_wire
module E = Bioc_domain.Policy_expression_material
module D = Bioc_domain.Policy_document
module P = Bioc_domain.Pinned_identity
module A = Bioc_domain.Policy_mrna_structure
type t = {
  request_value:E.t; document_value:D.t; assessment_value:Json.t; report_value:Json.t;
  objective_value:Json.t; objective_identity:string; objective_location:string;
  recipient_value:Json.t; deployment_value:Json.t; implementation_value:Json.t;
  localization_value:Json.t; product_value:P.t; maximum_rna_nt_value:int;
  obligation_values:string list;
}
let request value = value.request_value
let document value = value.document_value
let source_assessment value = value.assessment_value
let report value = value.report_value
let objective value = value.objective_value
let objective_id value = value.objective_identity
let objective_path value = value.objective_location
let recipient value = value.recipient_value
let deployment value = value.deployment_value
let implementation value = value.implementation_value
let localization value = value.localization_value
let product value = value.product_value
let maximum_rna_nt value = value.maximum_rna_nt_value
let unresolved_obligations value = value.obligation_values

module Make (Charge : sig val charge : int -> unit end) = struct
module Meter = Policy_generation_meter.Make(Charge)
module List = Meter.List
module Json = Meter.Json
module String = Meter.String
module Canonical = Meter.Canonical
module Document = Meter.Document
module Seen = Meter.Seen
let ( ^ ) = Meter.append_string
let ( @ ) = List.append
let get key value = Json.field key (Json.object_fields value)
let text key value = Json.string (get key value)
let list key value = Json.array (get key value)
let str value = Json.String value
let obj fields = Json.Object fields
let arr values = Json.Array values
let unsupported path condition message = Diagnostic.require ~path condition
  "policy_expression_source_unsupported" message
let binding path condition message = Diagnostic.require ~path condition
  "policy_expression_source_binding" message
let same path left right = binding path (Json.equal left right)
  "Supplied expression authority differs from the complete independently resolved original source."
let ref_json kind id = obj ["$type",str "Ref"; "id",str id; "kind",str kind]
let source_type kind = obj ["$type",str "TypeSpec"; "kind",str kind; "unit",Json.Null; "entity_kind",Json.Null]
let admit original =
  let document_value = E.document original in
  (* E.of_json uses only the explicit D.of_expression_json decoder. The abstract
     immutable domain value retains that original source; no saved assessment
     or operational admission is consumed. *)
  let assessment_value = Policy_check.check ~charge:Charge.charge document_value in
  Diagnostic.require ~path:"/document" (get "status" assessment_value = str "valid")
    "policy_expression_source_invalid" "Expression admission requires a fresh valid native source assessment.";
  let raw = D.to_json document_value and program = D.program document_value in
  let selection = E.selection original and contract = E.expression_contract original in
  let declarations = D.declarations document_value in
  List.iter (fun (node:D.declaration) -> unsupported node.path
    (List.mem node.kind [D.Role; D.Parameter; D.Requirement])
    "Runtime, temporal and additional source declarations are unsupported by the static expression profile.") declarations;
  let one kind path =
    match List.filter (fun (node:D.declaration) -> node.kind = kind) declarations with
    | [value] -> value
    | _ :: extra :: _ -> Diagnostic.fail ~path:extra.path "policy_expression_source_unsupported"
        ("Additional source declaration is outside the single-objective profile: " ^ extra.id)
    | _ -> Diagnostic.fail ~path "policy_expression_source_unsupported" "The source declaration census differs from the single-objective profile." in
  let role = one D.Role "/document/program/declarations" in
  let objective = one D.Requirement "/document/program/declarations" in
  unsupported "/document/program/declarations" (List.length declarations = 7)
    "The static profile requires exactly one recipient, five fixed parameters and one objective.";
  binding "/selection/recipient" (role.id = selection.recipient) "Selection does not name the original recipient role.";
  binding "/selection/objective" (objective.id = selection.objective) "Selection does not name the original objective.";
  unsupported role.path (get "population" role.value = Json.Null && get "lineage_role" role.value = Json.Bool false)
    "Population and lineage semantics require their own implementation.";
  let definitions = list "definitions" (get "semantics" program) in
  unsupported "/document/program/semantics/definitions" (List.length definitions <= 64)
    "Expression source exceeds its semantic-definition bound.";
  let find_definition path id = match List.find_opt (fun raw -> text "id" raw = id) definitions with
    | Some value -> value
    | None -> Diagnostic.fail ~path "policy_expression_source_binding" "Referenced complete semantic definition is absent." in
  let resolve path (pin:E.definition_ref) =
    let definition = find_definition path pin.id in
    binding path (text "version" definition = pin.version && Document.document_digest definition = pin.digest)
      "Semantic DefinitionRef does not match its complete original definition and semantic digest.";
    definition in
  let refs path expected raw =
    same path (arr (List.map E.definition_ref_to_json expected)) raw;
    List.iteri (fun index pin -> ignore (resolve (path ^ "/" ^ string_of_int index) pin)) expected in
  unsupported (objective.path ^ "/contract") (get "contract" objective.value <> Json.Null)
    "The static objective needs the complete recognized normative definition.";
  let objective_pin = E.definition_ref_of_json (get "contract" objective.value) in
  unsupported (objective.path ^ "/contract")
    (Json.equal (resolve (objective.path ^ "/contract") objective_pin) (E.objective_definition ()))
    "The objective definition has no interpretation in this closed static profile.";
  unsupported "/expression_contract/body/operation"
    (Json.equal (resolve "/expression_contract/body/operation" contract.operation) (E.operation_definition ()))
    "The selected operation has no interpretation in this closed static profile.";
  ignore (resolve "/expression_contract/body/realization" contract.realization);
  unsupported "/expression_contract/body/translation/model"
    (Json.equal (resolve "/expression_contract/body/translation/model" contract.translation.model)
      (E.translation_definition ())) "The translation model has no interpretation in this closed static profile.";
  binding "/expression_contract/body/dependencies"
    (List.exists (fun pin -> Json.equal (E.definition_ref_to_json pin)
      (E.definition_ref_to_json contract.translation.model)) contract.dependencies)
    "The nominal translation model must remain an explicit original implementation dependency.";
  unsupported objective.path (get "kind" objective.value = str "objective")
    "Only the exact static expression objective is supported.";
  same (objective.path ^ "/scope") (get "scope" objective.value)
    (obj ["$type",str "Scope"; "kind",str "executor"; "subject",ref_json "Role" role.id]);
  List.iter (fun key -> unsupported (objective.path ^ "/" ^ key) (get key objective.value = Json.Null)
    "Temporal, dynamic and quantitative objective fields need an implemented interpretation.")
    ["condition"; "response"; "trigger"; "clock"; "deadline"; "lower"; "upper"; "horizon"];
  unsupported (objective.path ^ "/assumptions") (get "assumptions" objective.value = arr [])
    "Additional objective assumptions are unsupported.";
  same (objective.path ^ "/applies_to") (get "applies_to" objective.value)
    (arr (ref_json "Role" role.id :: List.map (ref_json "Parameter") E.parameter_ids));
  let parameters = List.filter (fun (node:D.declaration) -> node.kind = D.Parameter) declarations in
  unsupported "/document/program/declarations" (List.sort String.compare (List.map (fun (node:D.declaration) -> node.id) parameters)
    = List.sort String.compare E.parameter_ids) "The fixed source parameter inventory differs from the profile.";
  let parameter id kind =
    let node = List.find (fun (node:D.declaration) -> node.id = id) parameters in
    same (node.path ^ "/value_type") (get "value_type" node.value) (source_type kind);
    unsupported node.path (get "selection" node.value = str "fixed" &&
      get "lower" node.value = Json.Null && get "upper" node.value = Json.Null)
      "Source parameters must be fixed exact values, without unimplemented refinement bounds.";
    get "value" node.value in
  let product_value = P.make ~kind:P.Reference ~id:(Json.string (parameter "product_id" "text"))
    ~version:(Json.string (parameter "product_version" "text"))
    ~content_fingerprint:(Json.string (parameter "product_sha256" "text")) in
  same "/expression_contract/body/product" (P.to_json product_value) (P.to_json contract.product);
  let localization_id = Json.string (parameter "localization" "text") in
  let localization_value = find_definition "/expression_contract/body/localization" localization_id in
  same "/expression_contract/body/localization" localization_value contract.localization;
  unsupported "/expression_contract/body/localization/category" (get "category" localization_value = str "spatial")
    "Localization requires an explicitly supplied spatial semantic definition.";
  let maximum = Json.integer (parameter "maximum_rna_nt" "integer") in
  let maximum_node = List.find (fun (node:D.declaration) -> node.id = "maximum_rna_nt") parameters in
  unsupported (maximum_node.path ^ "/value") (Z.sign maximum > 0 &&
    Z.leq maximum (Z.of_int Bioc_domain.Molecular_record.max_residues))
    "Maximum RNA length must be a positive exact integer within the molecular residue ceiling.";
  let maximum_rna_nt_value = Z.to_int maximum in
  let deployment_value = get "deployment" raw in
  same "/expression_contract/body/deployment" deployment_value contract.deployment;
  unsupported "/document/deployment/route" (get "route" deployment_value = str "in_vivo")
    "Only the declared human in-vivo recipient route is supported.";
  let recipient_value = match list "bindings" deployment_value with
    | [value] -> same "/document/deployment/bindings/0/role" (get "role" value) (ref_json "Role" role.id); get "chassis" value
    | _ -> Diagnostic.fail ~path:"/document/deployment/bindings" "policy_expression_source_unsupported" "Exactly one recipient binding is required." in
  same "/expression_contract/body/recipient" recipient_value contract.recipient;
  unsupported "/document/deployment/bindings/0/chassis" (get "species" recipient_value = str "human" &&
    List.mem (text "recipient_class" recipient_value) ["immune"; "immune_progenitor"])
    "This profile is restricted to the supplied human immune recipient.";
  same "/document/deployment/delivery/intended_recipients" (get "intended_recipients" (get "delivery" deployment_value))
    (arr [ref_json "Role" role.id]);
  let payload = get "payload" deployment_value in
  unsupported "/document/deployment/payload/format" (get "format" payload = str "RNA") "RNA payload format is required.";
  List.iter (fun key -> unsupported ("/document/deployment/payload/" ^ key) (get key payload = Json.int 1)
    "One complete RNA, ORF and product are required.") ["design_count"; "member_count"; "orf_count"; "product_count"];
  unsupported "/document/deployment/payload/helper_count" (get "helper_count" payload = Json.int 0)
    "Helper RNAs require an implemented composition profile.";
  List.iter (fun key -> unsupported ("/document/deployment/payload/" ^ key) (get key payload = Json.Null)
    "Dose, copy-number and persistence constraints are not implemented by static encoding.")
    ["copy_number"; "dose"; "payload_persistence"; "effector_persistence"];
  let implementation_value = match list "implementations" (get "implementations" raw) with
    | [value] -> value
    | _ -> Diagnostic.fail ~path:"/document/implementations" "policy_expression_source_unsupported" "Exactly one complete original implementation entry is required." in
  binding "/selection/implementation" (P.id selection.implementation = text "id" implementation_value &&
    P.version selection.implementation = text "version" implementation_value &&
    P.content_fingerprint selection.implementation = Canonical.fingerprint implementation_value)
    "Selected implementation does not match the complete original entry identity/content.";
  same "/document/implementations/operation" (get "operation" implementation_value) (E.definition_ref_to_json contract.operation);
  same "/document/implementations/realization" (get "realization" implementation_value) (E.definition_ref_to_json contract.realization);
  same "/document/implementations/chassis" (get "chassis" implementation_value) (arr [get "id" recipient_value]);
  same "/document/implementations/payload_formats" (get "payload_formats" implementation_value) (arr [str "RNA"]);
  refs "/document/implementations/dependencies" contract.dependencies (get "dependencies" implementation_value);
  refs "/document/implementations/evidence" contract.evidence (get "evidence" implementation_value);
  (* Only original contract/context definitions reachable from this exact source
     objective can become named conditional premises. Unused definitions cannot
     smuggle unimplemented semantic demands into a generic premise bucket. *)
  let consumed_definitions = ref (Seen.singleton localization_id) in
  let rec visit_references path value =
    Charge.charge 1;
    match value with
    | Json.Object fields ->
        if List.assoc_opt "$type" fields = Some (str "DefinitionRef") then (
          let pin = E.definition_ref_of_json value in
          let definition = resolve path pin in
          if not (Seen.mem pin.id !consumed_definitions) then (
            consumed_definitions := Seen.add pin.id !consumed_definitions;
            visit_references path definition))
        else List.iter (fun (key,child) -> visit_references (path ^ "/" ^ key) child) fields
    | Json.Array values -> List.iteri (fun index child -> visit_references (path ^ "/" ^ string_of_int index) child) values
    | _ -> () in
  List.iter (fun (path,value) -> visit_references path value)
    [role.path,role.value; objective.path,objective.value;
     "/document/deployment",deployment_value; "/document/implementations/implementations/0",implementation_value;
     "/expression_contract/body/localization",localization_value];
  List.iteri (fun index definition ->
    unsupported ("/document/program/semantics/definitions/" ^ string_of_int index)
      (Seen.mem (text "id" definition) !consumed_definitions)
      "A semantic definition is not consumed by this objective or its exact supplied context/dependency closure.") definitions;
  let assurance = get "assurance" raw in
  same "/document/assurance/requirements" (get "requirements" assurance) (arr [str objective.id]);
  unsupported "/document/assurance" (get "level" assurance = str "structural" &&
    get "horizon" assurance = str "not_applicable" && get "assumptions" assurance = arr [] &&
    get "tolerances" assurance = arr []) "Static assurance must be structural and explicitly timeless without omitted additional demands.";
  binding "/expression_contract/body/material" (contract.material.structure_sha256 = E.structure_fingerprint original &&
    contract.material.member = selection.member && contract.material.cds = selection.cds)
    "Expression material identity differs from the complete original structural authority and selected location.";
  let member = match A.members (E.structure_authority original) with
    | [value] -> value
    | _ -> Diagnostic.fail ~path:"/structure_authority/members" "policy_expression_source_unsupported" "One complete original RNA member is required." in
  binding "/selection/member" (member.id = selection.member && member.regions.cds = selection.cds)
    "Selected member/CDS differs from the original structural authority.";
  same "/structure_authority/members/0/product/identity" (P.to_json member.product.identity) (P.to_json product_value);
  let obligation_values = List.sort_uniq String.compare
    ("expression_material_correspondence" :: List.map Json.string (list "unresolved_obligations" assessment_value)) in
  let report_value = obj [
    "schema_version",str "biocompiler.policy_expression_source_admission.v0.1";
    "status",str "admitted_static_expression_source"; "request_fingerprint",str (E.fingerprint original);
    "source_artifact_digest",str (D.artifact_digest document_value); "source_semantic_digest",str (D.fingerprint document_value);
    "objective",str objective.id; "objective_path",str objective.path;
    "product",P.to_json product_value; "maximum_rna_nt",Json.int maximum_rna_nt_value;
    "unresolved_obligations",arr (List.map str obligation_values);
    "source_assessment",assessment_value; "temporal_execution",str "not_requested_by_supported_objective";
    "expression_claim",str "withheld"; "empirical_realization",str "unassessed";
    "human_use",str "unassessed"; "export",str "withheld"] in
  Meter.preflight report_value;
  {request_value=original; document_value; assessment_value; report_value;
   objective_value=objective.value; objective_identity=objective.id; objective_location=objective.path;
   recipient_value; deployment_value; implementation_value; localization_value; product_value;
   maximum_rna_nt_value; obligation_values}
end
let admit ?(charge=Policy_generation_meter.no_charge) request =
  let consumed = ref (E.decoding_work request) in
  let maximum = (E.budgets request).max_work in
  let spend amount =
    Diagnostic.require (amount >= 0 && amount <= maximum - !consumed)
      "policy_expression_source_work_limit" "Expression source admission exhausted its request work allowance.";
    charge amount; consumed := !consumed + amount in
  let module Admission = Make(struct let charge = spend end) in
  Admission.admit request
