open Bioc_wire
module Check = Bioc_realization_checker.Policy_controlled_workflow_check
module R = Bioc_domain.Policy_controlled_workflow_request
module C = Bioc_domain.Policy_controlled_workflow_candidate
let str value = Json.String value
let obj fields = Json.Object fields
let get key raw = Json.field key (Json.object_fields raw)
let fingerprint ~charge raw =
  let bytes = Bioc_domain.Policy_material_request.preflight ~max_bytes:8_323_072
    ~max_nodes:249_968 ~max_depth:128 ~charge raw in
  charge bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:8_323_072 raw in
  Diagnostic.require (String.length encoded = bytes) "controlled_workflow_format_accounting"
    "Joined publication size differs from its original reservation.";
  charge bytes; Canonical.sha256 encoded
let render ~charge checked =
  let request = Check.request checked and candidate = Check.candidate checked in
  let report = Check.evidence checked in
  (* Reuse the checked-only exact renderer. Its material manifest is not exported
     as joined authority; the complete fresh child report remains in our report. *)
  let structural = Policy_controlled_material_format.render ~charge (Check.material checked) in
  let manifest = obj ["schema_version",str "biocompiler.policy_controlled_workflow_manifest.v0.1";
    "stage",str "joined";"request",R.to_json request;"limits",R.limits request;
    "candidate",C.to_json candidate;"report",report;
    "request_fingerprint",str (R.fingerprint request);"candidate_fingerprint",str (C.fingerprint candidate);
    "invocation_fingerprint",get "invocation_fingerprint" report;
    "report_fingerprint",str (fingerprint ~charge report);
    "members",get "members" (get "manifest" structural);
    "empirical_status",str "unassessed";"human_use",str "unassessed";"therapeutic_export",str "withheld"] in
  let limits = R.budgets request in
  let output = Bioc_checker.Work_budget.create_output ~profile:R.resource_profile
    ~error_code:"controlled_workflow_publication_limit" ~max_bytes:limits.max_report_bytes
    ~max_nodes:limits.max_report_nodes () in
  Bioc_checker.Work_budget.reserve_json output manifest;
  obj ["fasta",get "fasta" structural;"fasta_sha256",get "fasta_sha256" structural;
    "manifest",manifest;"manifest_sha256",str (fingerprint ~charge manifest)]
