open Bioc_wire
module C = Realization_contract
let schema_version = "biocompiler.realization_request.v0.1"
let validation_scope = "structural_realization_request_only"
let resource_profile = "biocompiler.realization_request.resources.v1"
let str value = Json.String value
let preflight ?(path = "") value =
  try Measurement_contract.preflight ~path value with
  | Diagnostic.Error diagnostic when diagnostic.code = "human_record_limit" ->
      Diagnostic.fail ~path "realization_request_limit" "Realization request exceeds its native resource boundary."
  | Diagnostic.Error diagnostic when diagnostic.code = "human_record_cycle" ->
      Diagnostic.fail ~path "realization_request_cycle" "Cyclic realization request."
type t = { json : Json.t; fingerprint : string; artifact_fingerprint : string; size : int;
  build_request : Build_request.t; behavior : Behavior.t; contract : C.Behavior_contract.t;
  domain : C.Operating_domain.t; target : Build_request.Target.t option }
let encode ~build_request ~behavior ~contract ~domain =
  (* Child codecs retain immutable bounded records; the four-field envelope
     shares those JSON values. No list or recursive child expansion is added. *)
  let value = Json.Object ["schema_version", str schema_version;
      "build_request", Build_request.to_json build_request; "behavior", Behavior.to_json behavior;
      "contract", C.Behavior_contract.to_json contract; "domain", C.Operating_domain.to_json domain] in
  preflight value; value
let finish ~build_request ~behavior ~contract ~domain =
  let json = encode ~build_request ~behavior ~contract ~domain in
  let canonical = Canonical.encode json in
  let fingerprint = Canonical.fingerprint (Json.Object ["schema_version", str schema_version;
      "build_request", str (Build_request.fingerprint build_request);
      "behavior", str (Behavior.fingerprint behavior);
      "contract", str (C.Behavior_contract.fingerprint contract);
      "domain", str (C.Operating_domain.fingerprint domain)]) in
  {json; fingerprint; artifact_fingerprint = Canonical.sha256 canonical; size = String.length canonical;
   build_request; behavior; contract; domain;
   target = Option.map Build_request.Target.of_json (Build_request.target build_request)}
let of_json ?(path = "") value =
  preflight ~path value;
  let fields = Json.object_fields ~path value in
  Json.exact_fields ~path ["schema_version"; "build_request"; "behavior"; "contract"; "domain"] fields;
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  Diagnostic.require ~path (Json.string (get "schema_version") = schema_version)
    "unsupported_schema" "Unsupported realization request schema.";
  let build_request = Build_request.of_json (get "build_request") in
  let behavior = Behavior.of_json (get "behavior") in
  let contract = C.Behavior_contract.of_json ~path:(path ^ "/contract") (get "contract") in
  let domain = C.Operating_domain.of_json ~path:(path ^ "/domain") (get "domain") in
  finish ~build_request ~behavior ~contract ~domain
let make ~build_request ~behavior ~contract ~domain = finish ~build_request ~behavior ~contract ~domain
let to_json (value : t) = value.json
let fingerprint (value : t) = value.fingerprint
let artifact_fingerprint (value : t) = value.artifact_fingerprint
let canonical_size (value : t) = value.size
let build_request (value : t) = value.build_request
let behavior (value : t) = value.behavior
let contract (value : t) = value.contract
let domain (value : t) = value.domain
let target (value : t) = value.target
let upstream_request_fingerprint (value : t) = Build_request.fingerprint value.build_request
