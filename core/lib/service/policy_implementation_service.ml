open Bioc_wire
module R = Bioc_domain.Policy_realization_request
module O = Bioc_domain.Policy_operational
module I = Bioc_domain.Policy_implementation
module U = Bioc_domain.Policy_implementation_binding
module C = Bioc_realization_checker.Policy_preservation_check
module W = Bioc_checker.Work_budget
let str value=Json.String value
let obj fields=Json.Object fields
let operations=["check-policy-implementation";"replay-policy-implementation"]
let validation_scope="bounded-policy-implementation-v0.1"
let implementation="biocompiler.ocaml.policy_implementation.v0.1"
let resource_profile="biocompiler.policy_preservation_resources.v0.1"
let schema_version="biocompiler.core.policy_implementation.v1"
let candidate_schema="biocompiler.policy_implementation_candidate.v0.1"
(* A legal protocol request identity can occupy max_string_bytes and encode as
   six ASCII bytes per scalar byte. Reserve this worst case and fixed framing;
   the result itself never consumes the complete protocol allowance. *)
let max_result_bytes=Limits.max_response_bytes-6*Limits.max_string_bytes-65536
let max_result_nodes=Limits.max_json_nodes-32
let profile=obj[
  "operations",Json.Array(List.map str operations);"request_schema",str R.schema_version;
  "candidate_schema",str candidate_schema;"schema_version",str schema_version;
  "implementation",str implementation;"resource_profile",str resource_profile;
  "validation_scope",str validation_scope;"max_result_bytes",Json.int max_result_bytes;
  "max_result_nodes",Json.int max_result_nodes;
  "artifact",str "withheld";"target_status",str "unassessed";
  "material",str "unassessed";"export",str "withheld"]
let producer_profile=obj["operations",Json.Array[str "compile-policy-implementation"];
  "implementation",str implementation;"validation_scope",str validation_scope]
let validate_publication value=
  let output=W.create_output ~profile:validation_scope ~error_code:"policy_implementation_publication_limit"
    ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes ()in
  (* The extra level accounts for the actual protocol result envelope. *)
  let framed=obj["result",value]in
  W.reserve_json output framed;
  let encoded=Canonical.encode_bounded ~max_bytes:max_result_bytes framed in
  ignore(Json.parse_artifact ~max_bytes:max_result_bytes ~max_nodes:max_result_nodes encoded)
let check ~request:raw_request ~candidate:raw_candidate ~limits:raw_limits=
  let request=R.of_json raw_request in
  let fields=Json.object_fields ~path:"/payload/candidate" raw_candidate in
  Json.exact_fields ~path:"/payload/candidate" ["schema_version";"behavior";"implementation";"binding"]fields;
  Diagnostic.require(Json.string(Json.field "schema_version" fields)=candidate_schema)
    "policy_implementation_candidate" "Unknown implementation candidate envelope schema.";
  let behavior=O.behavior_of_json(Json.field "behavior" fields)
  and actual=I.of_json ~library:(R.implementation_library request)(Json.field "implementation" fields)
  and proposed=U.of_json(Json.field "binding" fields)
  and limits=C.limits_of_json raw_limits in
  let checked=C.check ~request ~behavior ~implementation:actual ~proposed ~limits in
  let report=C.report checked in
  let result=obj[
    "schema_version",str schema_version;"implementation",str implementation;
    "resource_profile",str resource_profile;"validation_scope",str validation_scope;
    "request_fingerprint",str(R.fingerprint request);
    "candidate_fingerprint",str(Canonical.fingerprint raw_candidate);
    "invocation_fingerprint",str(Canonical.fingerprint(obj[
      "request",raw_request;"candidate",raw_candidate;"limits",raw_limits]));
    "report_fingerprint",str(Canonical.fingerprint report);
    "candidate",raw_candidate;"report",report]in
  validate_publication result;result
let handle ~operation payload=
  Diagnostic.require(List.mem operation operations)"unsupported_operation"
    "This implementation service checks or replays supplied candidates only.";
  let replay=operation="replay-policy-implementation"in
  let fields=Json.object_fields ~path:"/payload" payload in
  Json.exact_fields ~path:"/payload"(["request";"candidate";"limits"]@(if replay then["report"]else[]))fields;
  let result=check ~request:(Json.field "request" fields) ~candidate:(Json.field "candidate" fields)
    ~limits:(Json.field "limits" fields)in
  if replay then Diagnostic.require ~path:"/payload/report"(Json.equal result(Json.field "report" fields))
    "policy_implementation_replay" "Saved wrapper differs from full fresh implementation checking and evidence.";
  result
