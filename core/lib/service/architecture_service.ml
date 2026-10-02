open Bioc_wire
open Bioc_domain
module Checker = Bioc_checker.Architecture_check

let validation_scope = "supplied-architecture-correspondence-v1"
let str value = Json.String value
let profile = Json.Object [
    "operations", Json.Array [str "verify-architecture"; str "replay-architecture"];
    "request_schema", str Architecture_request.schema_version;
    "build_schema", str Architecture_build.schema_version;
    "assessment_schema", str Architecture_assessment.schema_version;
    "implementation", str Checker.implementation_version;
    "resource_profile", str Checker.resource_profile;
    "validation_scope", str validation_scope
  ]

let wrap ~raw_request ~raw_build assessment =
  Json.Object [
    "schema_version", str "biocompiler.core.architecture_assessment.v1";
    "implementation", str Checker.implementation_version;
    "resource_profile", str Checker.resource_profile;
    "validation_scope", str validation_scope;
    (* Wire identity and normalized domain identity are deliberately distinct.
       The assessment carries the latter; these pins bind the exact supplied
       documents even if a valid import normalizes inventory ordering. *)
    "supplied_request_fingerprint", str (Canonical.fingerprint raw_request);
    "supplied_build_fingerprint", str (Canonical.fingerprint raw_build);
    "assessment_fingerprint", str (Architecture_assessment.fingerprint assessment);
    "assessment", Architecture_assessment.to_json assessment
  ]

let verify ~replay payload =
  let fields = Json.object_fields payload in
  Json.exact_fields (if replay then ["expected_request"; "build"; "assessment"] else ["expected_request"; "build"]) fields;
  let raw_request = Json.field "expected_request" fields and raw_build = Json.field "build" fields in
  let expected_request = Architecture_request.of_json ~path:"/payload/expected_request" raw_request in
  let build = Architecture_build.of_json ~path:"/payload/build" raw_build in
  let assessment =
    if replay then
      Checker.replay ~expected_request ~build
        (Architecture_assessment.of_json ~path:"/payload/assessment" (Json.field "assessment" fields))
    else Checker.check ~expected_request build in
  wrap ~raw_request ~raw_build assessment
