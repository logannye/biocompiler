open Bioc_wire

module Document = Bioc_domain.Policy_document
module Checker = Bioc_checker.Policy_check

let operations = ["assess-policy"; "replay-policy-assessment"]
let validation_scope = "policy-source-contracts-v0.1"
let implementation = "biocompiler.ocaml.policy_check.v0.1"
let resource_profile = "biocompiler.policy_frontend.resources.v0.1"
let str value = Json.String value
let profile = Json.Object [
    "operations", Json.Array (List.map str operations);
    "document_profile", str "biocompiler.policy.v0.1";
    "assessment_schema", str "biocompiler.policy_assessment.v0.1";
    "implementation", str implementation;
    "resource_profile", str resource_profile;
    "validation_scope", str validation_scope;
    "max_document_bytes", Json.int (2 * 1024 * 1024);
    "max_depth", Json.int 64;
    "max_nodes", Json.int 100_000;
    "stages", Json.Object [
      "representation", str "implemented";
      "source_contracts", str "implemented";
      "execution", str "unsupported";
      "lowering", str "unsupported";
      "realization", str "unsupported"]
  ]

let handle ~operation payload =
  let fields = Json.object_fields ~path:"/payload" payload in
  let raw = match operation with
    | "assess-policy" ->
        Json.exact_fields ~path:"/payload" ["document"] fields;
        Json.field "document" fields
    | "replay-policy-assessment" ->
        Json.exact_fields ~path:"/payload" ["expected_document"; "assessment"] fields;
        Json.field "expected_document" fields
    | _ -> Diagnostic.fail "unsupported_operation" "Unsupported policy assessment operation."
  in
  (* Stable document-relative paths make fresh replay independent of envelope keys. *)
  let document = Document.of_json ~path:"/document" raw in
  let assessment = Checker.check document in
  if operation = "replay-policy-assessment" then
    Diagnostic.require ~path:"/payload/assessment"
      (Json.equal assessment (Json.field "assessment" fields))
      "policy_assessment_mismatch"
      "Supplied policy assessment differs from fresh independent source checking.";
  Json.Object [
    "schema_version", str "biocompiler.core.policy_assessment.v1";
    "implementation", str implementation;
    "resource_profile", str resource_profile;
    "validation_scope", str validation_scope;
    "supplied_document_fingerprint", str (Canonical.fingerprint raw);
    "assessment_fingerprint", str (Canonical.fingerprint assessment);
    "assessment", assessment
  ]
