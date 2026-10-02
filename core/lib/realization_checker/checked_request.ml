open Bioc_wire
open Bioc_domain
module R = Realization_request
module C = Realization_contract
module W = Bioc_checker.Work_budget
let implementation_version = "biocompiler.ocaml.checked_realization_request.v0.1"
let resource_profile = "biocompiler.checked_realization_request.resources.v1"
type t = { request : R.t; target : Build_request.Target.t; report : Bioc_checker.Lowering_check.report }
let check ?parent request =
  let budget = match parent with
    | None -> W.create ~profile:resource_profile ~error_code:"realization_request_work_limit" ~maximum:50_000_000 ()
    | Some parent -> W.nested ~parent ~profile:resource_profile ~error_code:"realization_request_work_limit" ~maximum:50_000_000 () in
  W.charge budget (R.canonical_size request);
  let target = match R.target request with Some value -> value | None ->
    Diagnostic.fail "realization_request_target" "Realization requests require an explicit target context." in
  let behavior = R.behavior request in
  let report = Bioc_checker.Lowering_check.check_with_budget ~parent:budget
      ~expected_request:(R.build_request request) ~behavior () in
  let contract = R.contract request and domain = R.domain request in
  Diagnostic.require (C.Behavior_contract.behavior_fingerprint contract = Behavior.fingerprint behavior)
    "realization_request_behavior_identity" "Contract must refer to this exact verified Behavior fingerprint.";
  Diagnostic.require (C.Behavior_contract.role contract = C.Operating_domain.role domain)
    "realization_request_role" "Contract and operating domain must bind the same role.";
  let role = C.Operating_domain.role domain in
  let found = List.fold_left (fun found node ->
      W.charge budget (1 + String.length (Identity.Node.to_string (Behavior.node_id node)));
      found || match Behavior.operation node with Behavior.Role _ -> Identity.Node.to_string (Behavior.node_id node) = role | _ -> false)
      false (Behavior.nodes behavior) in
  Diagnostic.require found "realization_request_unknown_role" "Operating domain must bind an existing Behavior role.";
  {request; target; report}
let of_json ?parent value = check ?parent (R.of_json value)
let make ?parent ~build_request ~behavior ~contract ~domain () =
  check ?parent (R.make ~build_request ~behavior ~contract ~domain)
let request (value : t) = value.request
let target (value : t) = value.target
let lowering_report (value : t) = value.report
let fingerprint (value : t) = R.fingerprint value.request
let artifact_fingerprint (value : t) = R.artifact_fingerprint value.request
let to_json (value : t) = R.to_json value.request
