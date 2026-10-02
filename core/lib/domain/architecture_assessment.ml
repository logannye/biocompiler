open Bioc_wire
module M = Molecular_record
module G = Architecture_build.Gap
type outcome = Construction_assessment.outcome = Pass | Fail | Unknown | Unsupported
type t = {request_fingerprint:string; build_fingerprint:string; outcome:outcome;
  translation_complete:bool; construction_complete:bool; diagnostics:G.t list;
  unresolved:string list; assumptions:string list}
let schema_version = "biocompiler.payload_architecture_verification.v0.1"
let checker_version = "biocompiler.payload_architecture_checker.v0.3"
let claim_scope = "Exact source and supplied composite execution-contract correspondence, explicit functional requirements under bounded control proof profiles, declared RNA availability intervals, physical composition and complete RNA construction only. No empirical component function or human therapeutic admission is established."
let str value = Json.String value
let require ?path value message = Diagnostic.require ?path value "invalid_architecture_assessment" message
(* Match the import tree's conservative size measure before accumulating child
   representations. Pretty-printed publication has a separate byte contract. *)
let rec tree_size = function
  | Json.Object fields -> 2 + 2 * List.length fields + List.fold_left (fun n (key,value) -> n + String.length key + 2 + tree_size value) 0 fields
  | Json.Array values -> 2 + List.length values + List.fold_left (fun n value -> n + tree_size value) 0 values
  | Json.String value -> String.length value + 2
  | Json.Int value -> String.length (Z.to_string value)
  | Json.Float value -> String.length (Canonical.float_string value)
  | Json.Null | Json.Bool _ -> 5
let array maximum encode values =
  ignore (M.bounded_length ~maximum values);
  let bytes = ref 2 in
  let values = List.map (fun value -> let raw = encode value in M.bounded_tree raw;
      bytes := !bytes + tree_size raw + 1;
      Diagnostic.require (!bytes <= M.max_json_bytes) "molecular_resource_limit" "Architecture assessment exceeds cumulative inventory bounds.";
      raw) values in
  let raw = Json.Array values in M.bounded_tree raw; raw
let to_json value = Json.Object ["schema_version",str schema_version;
    "request_fingerprint",str value.request_fingerprint;"build_fingerprint",str value.build_fingerprint;
    "outcome",str (Construction_assessment.outcome_name value.outcome);
    "translation_complete",Json.Bool value.translation_complete;"construction_complete",Json.Bool value.construction_complete;
    "diagnostics",array 4096 G.to_json value.diagnostics;
    "unresolved",array M.max_items str value.unresolved;"assumptions",array M.max_items str value.assumptions;
    "checker_version",str checker_version;"claim_scope",str claim_scope;
    "search_verified",Json.Bool false;"empirical_validation",str "unknown";"human_therapeutic_admission",str "not_admitted"]
let hash ~path raw =
  let value = Json.string ~path raw in
  require ~path (String.length value = 64 && String.for_all (function '0'..'9' | 'a'..'f' -> true | _ -> false) value) "Expected lowercase SHA-256 architecture identity.";
  value
let names ~path raw =
  let values = M.array ~path ~maximum:M.max_items raw |> List.map (Json.name ~path) in
  require ~path (List.length values = List.length (List.sort_uniq String.compare values)) "Architecture report names must be unique.";
  values
let of_json ?(path="") raw =
  let fields = M.record ~path schema_version ["request_fingerprint";"build_fingerprint";"outcome";
      "translation_complete";"construction_complete";"diagnostics";"unresolved";"assumptions";
      "checker_version";"claim_scope";"search_verified";"empirical_validation";"human_therapeutic_admission"] raw in
  let get key = Json.field ~path:(path ^ "/" ^ key) key fields in
  require ~path (Json.string ~path (get "checker_version") = checker_version
      && Json.string ~path (get "claim_scope") = claim_scope
      && not (Json.boolean ~path (get "search_verified"))
      && Json.string ~path (get "empirical_validation") = "unknown"
      && Json.string ~path (get "human_therapeutic_admission") = "not_admitted") "Invalid checker claim scope.";
  let outcome = match Json.string ~path (get "outcome") with "pass" -> Pass | "fail" -> Fail | "unknown" -> Unknown | "unsupported" -> Unsupported
    | _ -> Diagnostic.fail ~path "invalid_architecture_assessment" "Unknown architecture outcome." in
  let diagnostics = M.array ~path:(path ^ "/diagnostics") ~maximum:4096 (get "diagnostics")
    |> List.mapi (fun i -> G.of_json ~path:(path ^ "/diagnostics/" ^ string_of_int i)) in
  let value = {request_fingerprint=hash ~path (get "request_fingerprint");build_fingerprint=hash ~path (get "build_fingerprint");
    outcome;translation_complete=Json.boolean ~path (get "translation_complete");
    construction_complete=Json.boolean ~path (get "construction_complete");diagnostics;
    unresolved=names ~path:(path ^ "/unresolved") (get "unresolved");assumptions=names ~path:(path ^ "/assumptions") (get "assumptions")} in
  require ~path (outcome <> Pass || diagnostics = []) "Passing architecture check cannot contain contradictions.";
  require ~path (not value.translation_complete || value.construction_complete && value.unresolved = []) "Complete translation cannot retain unresolved obligations.";
  M.bounded_tree ~path (to_json value); value
let make ~request_fingerprint ~build_fingerprint ~outcome ~translation_complete ~construction_complete ~diagnostics ~unresolved ~assumptions =
  of_json (to_json {request_fingerprint;build_fingerprint;outcome;translation_complete;construction_complete;diagnostics;unresolved;assumptions})
let fingerprint value = Canonical.fingerprint (to_json value)
let request_fingerprint value = value.request_fingerprint
let build_fingerprint value = value.build_fingerprint
let outcome value = value.outcome
let passed value = value.outcome = Pass
let translation_complete value = value.translation_complete
let construction_complete value = value.construction_complete
let diagnostics value = value.diagnostics
let unresolved value = value.unresolved
let assumptions value = value.assumptions
