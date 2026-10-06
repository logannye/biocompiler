open Bioc_wire
module Document = Bioc_domain.Policy_document
module O = Bioc_domain.Policy_operational
module Correspondence = Bioc_checker.Policy_correspondence

let str value = Json.String value
let operations = ["check-policy-lowering"; "execute-policy"; "replay-policy-execution"]
let validation_scope = "bounded-policy-operational-v0.1"
let implementation = "biocompiler.ocaml.policy_operational.v0.1"
let resource_profile = "biocompiler.policy_operational.resources.v0.1"
let schema_version = "biocompiler.core.policy_operational.v1"
let profile = Json.Object [
  "operations", Json.Array (List.map str operations);
  "document_profile", str Document.profile;
  "schema_version", str schema_version;
  "implementation", str implementation;
  "resource_profile", str resource_profile;
  "validation_scope", str validation_scope;
  "artifact", str "withheld";
  "target_status", str "unassessed"]
let producer_profile = Json.Object [
  "operations", Json.Array [str "compile-policy"];
  "implementation", str implementation;
  "validation_scope", str validation_scope]

let wrap ~payload ~candidate ~report =
  let authority = Json.Object (List.filter (fun (key, _) -> key <> "report")
      (Json.object_fields payload)) in
  Json.Object [
    "schema_version", str schema_version;
    "implementation", str implementation;
    "resource_profile", str resource_profile;
    "validation_scope", str validation_scope;
    "request_fingerprint", str (Canonical.fingerprint authority);
    "candidate_fingerprint", str (Canonical.fingerprint candidate);
    "report_fingerprint", str (Canonical.fingerprint report);
    "candidate", candidate; "report", report]

let lowering_report ~document ~correspondence = Json.Object [
  "schema_version", str "biocompiler.policy_lowering_report.v0.1";
  "source_assessment", Bioc_checker.Policy_check.check document;
  "correspondence", correspondence;
  "artifact", str "withheld";
  "target_status", str "unassessed";
  "realization", str "unassessed"]

let handle ~operation payload =
  let fields = Json.object_fields ~path:"/payload" payload in
  let execution = operation <> "check-policy-lowering" in
  let replay = operation = "replay-policy-execution" in
  Diagnostic.require (List.mem operation operations) "unsupported_operation"
    "Unknown operational-policy operation.";
  Json.exact_fields ~path:"/payload"
    (["document"; "definitions"; "candidate"] @
     (if execution then ["timeline"] else []) @ (if replay then ["report"] else [])) fields;
  let document = Document.of_json ~path:"/document" (Json.field "document" fields) in
  let definitions = O.descriptors_of_json (Json.field "definitions" fields) in
  let raw_candidate = Json.field "candidate" fields in
  let candidate = O.behavior_of_json raw_candidate in
  (* Only external authority admits candidate execution. A digest or retained
     report never bypasses fresh source admission and complete correspondence. *)
  let correspondence = Correspondence.check ~expected_document:document
      ~descriptors:definitions candidate in
  let base_report = lowering_report ~document ~correspondence in
  let report = if execution then Json.Object (Json.object_fields base_report @ [
      "execution", Bioc_semantics.Policy_execution.execute candidate (Json.field "timeline" fields)])
    else base_report in
  if replay then Diagnostic.require ~path:"/payload/report"
      (Json.equal report (Json.field "report" fields)) "policy_execution_replay"
      "Retained operational execution differs from complete fresh checking and execution.";
  wrap ~payload ~candidate:raw_candidate ~report
