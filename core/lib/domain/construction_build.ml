open Bioc_wire
module M = Molecular_record
type t = {request:Construction.Request.t; candidate:Construction_artifact.t; assessment:Construction_assessment.t}
let schema_version = "biocompiler.circuit_construction_build.v0.1"
let to_json value = Json.Object ["schema_version",Json.String schema_version;
    "request",Construction.Request.to_json value.request; "candidate",Construction_artifact.to_json value.candidate;
    "assessment",Construction_assessment.to_json value.assessment]
let of_json ?(path = "") raw =
  let fields = M.record ~path schema_version ["request";"candidate";"assessment"] raw in
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  let request = Construction.Request.of_json ~path:(path ^ "/request") (get "request")
  and candidate = Construction_artifact.of_json ~path:(path ^ "/candidate") (get "candidate")
  and assessment = Construction_assessment.of_json ~path:(path ^ "/assessment") (get "assessment") in
  Diagnostic.require ~path (Construction.Request.fingerprint request = Construction_artifact.request_fingerprint candidate
      && Construction.Request.fingerprint request = Construction_assessment.request_fingerprint assessment)
    "invalid_construction_build" "Historical construction authority identities disagree.";
  Diagnostic.require ~path (Construction_artifact.fingerprint candidate = Construction_assessment.candidate_fingerprint assessment)
    "invalid_construction_build" "Historical construction candidate identity changed.";
  let value = {request;candidate;assessment} in M.check_resources ~path (to_json value); value
let make ~request ~candidate ~assessment = of_json (to_json {request;candidate;assessment})
let fingerprint value = Canonical.fingerprint (to_json value)
let request value = value.request
let candidate value = value.candidate
let assessment value = value.assessment
