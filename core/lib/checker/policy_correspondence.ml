open Bioc_wire
module O = Bioc_domain.Policy_operational
let str value = Json.String value
type fresh = { source_assessment_value:Json.t; report_value:Json.t }
let source_assessment value = value.source_assessment_value
let report value = value.report_value
let check_fresh ?(charge = Policy_generation_meter.no_charge) ~expected_document ~descriptors (candidate:O.behavior) =
  let module Meter = Policy_generation_meter.Make(struct let charge = charge end) in
  let module List = Meter.List in
  let module Json = Meter.Json in
  let module Canonical = Meter.Canonical in
  let module D = Meter.Document in
  let module O = Meter.Operational in
  let ( ^ ) = Meter.append_string in
  (* The checker imports no lowering producer, and reconstructs every expected
     instruction field directly from the original external source. *)
  let admitted=Policy_admission.admit_metered ~charge ~document:expected_document ~descriptors in
  let expected_document=Policy_admission.document admitted in
  let assessment=Policy_admission.source_assessment admitted in
  let equal path expected actual = Diagnostic.require ~path (Json.equal expected actual)
      "policy_correspondence" "Behavior differs from its complete independent source/operational authority." in
  equal "/candidate/source_document" (D.to_json expected_document) candidate.O.source_document;
  equal "/candidate/descriptor_bundle" (O.descriptors_to_json descriptors) (O.descriptors_to_json candidate.definitions);
  equal "/candidate/source_ledger" (O.get "declarations" assessment) candidate.source_ledger;
  equal "/candidate/requirements_ledger" (O.get "requirements" assessment) candidate.requirements_ledger;
  equal "/candidate/assumptions" (O.get "assumptions" assessment) (Json.Array (List.map str candidate.assumptions));
  equal "/candidate/unresolved_obligations" (O.get "unresolved_obligations" assessment) (Json.Array (List.map str candidate.unresolved_obligations));
  let source=D.declarations expected_document in
  Diagnostic.require ~path:"/candidate/nodes" (List.length source = List.length candidate.nodes)
    "policy_correspondence" "Behavior instruction ledger drops or adds source occurrences.";
  List.iteri (fun i ((declaration:D.declaration),(node:O.node)) ->
    let path="/candidate/nodes/"^string_of_int i in
    Diagnostic.require ~path (node.id = declaration.id && node.kind = O.text "$type" declaration.value
      && node.source_path = declaration.path) "policy_correspondence" "Behavior opcode, identity, occurrence order or source path differs.";
    let operands=Json.object_fields node.data in
    let source_fields=Json.object_fields declaration.value in
    Diagnostic.require ~path (List.length operands + 1 = List.length source_fields && not (List.mem_assoc "$type" operands))
      "policy_correspondence" "Behavior operands add or remove a supported semantic distinction.";
    List.iter (fun (name,value) -> if name <> "$type" then
      let actual=match List.assoc_opt name operands with Some value -> value | None ->
        Diagnostic.fail ~path:(path^"/data/"^name) "policy_correspondence" "Source operand is absent from candidate behavior." in
      equal (path^"/data/"^name) value actual) source_fields)
    (List.combine source candidate.nodes);
  let result = Json.Object ["schema_version",str "biocompiler.policy_correspondence.v0.1";"status",str "valid";
    "profile",str O.profile;"document_artifact_digest",str (D.artifact_digest expected_document);
    "descriptors_digest",str (O.descriptors_digest descriptors);
    "candidate_fingerprint",str (Canonical.fingerprint (O.behavior_to_json candidate));
    "source_assessment",assessment;"admission",Policy_admission.report admitted;
    "requirements",O.get "requirements" assessment;"assumptions",O.get "assumptions" assessment;
    "unresolved_obligations",O.get "unresolved_obligations" assessment;
    "target_status",str "unassessed";"artifact",str "withheld"] in
  Meter.preflight result;
  {source_assessment_value=assessment;report_value=result}

let check ?charge ~expected_document ~descriptors candidate =
  report(check_fresh ?charge ~expected_document ~descriptors candidate)
