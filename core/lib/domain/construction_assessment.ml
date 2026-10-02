open Bioc_wire
module M = Molecular_record
type outcome = Pass | Fail | Unknown | Unsupported
type t = {request_fingerprint:string; candidate_fingerprint:string; reconstructed_fingerprint:string;
          outcome:outcome; complete:bool; diagnostics:string list}
let schema_version = "biocompiler.circuit_construction_assessment.v0.1"
let checker_version = "biocompiler.circuit_construction_checker.v0.1"
let capability_version = Construction.capability_profile_version
let construction_profile = Construction.profile_version
let admission_policy = "biocompiler.human_admission_policy.v0.1"
let claim_scope = "Exact correspondence of supplied sources, declared software operations, derived coordinates, chemistry and annotations; no biological processing, circuit implementation, independently reviewed source fidelity or human therapeutic admission is established."
let max_diagnostics = 4096
let max_diagnostic_bytes = 32_768
let max_retained_diagnostic_bytes = 1_000_000
let outcome_name = function Pass -> "pass" | Fail -> "fail" | Unknown -> "unknown" | Unsupported -> "unsupported"
let constants = ["checker_version",checker_version;"capability_version",capability_version;"construction_profile",construction_profile;
  "admission_policy",admission_policy;"claim_scope",claim_scope;"biological_function","unestablished";"empirical_validation","unknown";"human_therapeutic_admission","not_admitted"]
let to_json value = Json.Object (["schema_version",Json.String schema_version;"request_fingerprint",Json.String value.request_fingerprint;
    "candidate_fingerprint",Json.String value.candidate_fingerprint;"reconstructed_fingerprint",Json.String value.reconstructed_fingerprint;
    "outcome",Json.String (outcome_name value.outcome);"complete",Json.Bool value.complete;
    "diagnostics",Json.Array (List.map (fun value -> Json.String value) value.diagnostics)] @ List.map (fun (key,value) -> key,Json.String value) constants)
let require ?path value message = Diagnostic.require ?path value "invalid_construction_assessment" message
let hash ~path raw =
  let value = Json.string ~path raw in
  require ~path (String.length value = 64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value) "Expected a lowercase SHA-256 assessment identity.";
  value
let of_json ?(path = "") raw =
  let fields = M.record ~path schema_version (["request_fingerprint";"candidate_fingerprint";"reconstructed_fingerprint";"outcome";"complete";"diagnostics"] @ List.map fst constants) raw in
  let get key = Json.field ~path key fields in
  List.iter (fun (key,expected) -> require ~path (Json.string ~path (get key) = expected) "Construction report version, policy or claim scope differs.") constants;
  let outcome = match Json.string ~path (get "outcome") with "pass" -> Pass | "fail" -> Fail | "unknown" -> Unknown | "unsupported" -> Unsupported
    | _ -> Diagnostic.fail ~path "invalid_construction_assessment" "Unknown construction outcome." in
  let diagnostics = M.array ~path ~maximum:max_diagnostics (get "diagnostics") |> List.map (M.text ~path ~maximum:max_diagnostic_bytes) in
  let sorted = List.sort_uniq String.compare diagnostics in
  require ~path (List.length sorted = List.length diagnostics) "Duplicate construction assessment diagnostics.";
  let value = {request_fingerprint=hash ~path (get "request_fingerprint");candidate_fingerprint=hash ~path (get "candidate_fingerprint");
      reconstructed_fingerprint=hash ~path (get "reconstructed_fingerprint");outcome;complete=Json.boolean ~path (get "complete");diagnostics=sorted} in
  require ~path (value.complete = (outcome = Pass) && (outcome <> Pass || diagnostics = [])) "Construction completeness and diagnostics disagree with outcome.";
  M.check_resources ~path (to_json value); value
let make ~request_fingerprint ~candidate_fingerprint ~reconstructed_fingerprint ~outcome ~complete ~diagnostics =
  ignore (M.bounded_length ~maximum:max_diagnostics diagnostics);
  let bytes = ref 0 in List.iter (fun diagnostic ->
      bytes := !bytes + String.length diagnostic;
      Diagnostic.require (!bytes <= M.max_json_bytes) "molecular_resource_limit" "Assessment diagnostic serialization exceeds the molecular budget.") diagnostics;
  of_json (to_json {request_fingerprint;candidate_fingerprint;reconstructed_fingerprint;outcome;complete;diagnostics})
let fingerprint value = Canonical.fingerprint (to_json value)
let request_fingerprint value = value.request_fingerprint
let candidate_fingerprint value = value.candidate_fingerprint
let reconstructed_fingerprint value = value.reconstructed_fingerprint
let outcome value = value.outcome
let complete value = value.complete
let passed value = value.outcome = Pass
let diagnostics value = value.diagnostics

module Inventory = struct
  module Ids = Set.Make (String)
  type t = {mutable items : Ids.t; mutable bytes : int; mutable omitted : outcome option}
  let create () = {items=Ids.empty;bytes=0;omitted=None}
  let status diagnostic = match String.index_opt diagnostic ':' with
    | Some index -> String.sub diagnostic 0 index
    | None -> Diagnostic.fail "invalid_construction_check" "Internal construction diagnostic has no outcome prefix."
  let outcome = function "fail" -> Fail | "unsupported" -> Unsupported | "unknown" -> Unknown
    | _ -> Diagnostic.fail "invalid_construction_check" "Internal construction diagnostic has an invalid outcome prefix."
  let severity = function None -> 0 | Some Unknown -> 1 | Some Unsupported -> 2 | Some Fail -> 3 | Some Pass -> 0
  let add inventory diagnostic =
    Json.validate_utf8 diagnostic;
    let diagnostic_outcome = outcome (status diagnostic) in
    if not (Ids.mem diagnostic inventory.items) then
      let bytes = String.length diagnostic in
      if bytes > max_diagnostic_bytes || Ids.cardinal inventory.items >= max_diagnostics - 1 || inventory.bytes + bytes > max_retained_diagnostic_bytes then (
        let status = Some diagnostic_outcome in
        if severity status > severity inventory.omitted then inventory.omitted <- status
      ) else (inventory.items <- Ids.add diagnostic inventory.items; inventory.bytes <- inventory.bytes + bytes)
  let elements inventory = match inventory.omitted with None -> Ids.elements inventory.items
    | Some outcome -> Ids.add (outcome_name outcome ^ ":assessment_diagnostic_budget") inventory.items |> Ids.elements
end
