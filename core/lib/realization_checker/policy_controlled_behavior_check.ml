open Bioc_wire
module R = Bioc_domain.Policy_controlled_behavior_request
module Original = Bioc_domain.Policy_controlled_composition_request
module C = Bioc_domain.Policy_controlled_behavior_candidate
module I = Bioc_domain.Policy_controlled_activity_implementation
module Sample = Bioc_domain.Policy_controlled_activity_sample
module Domain = Bioc_domain.Policy_controlled_domain
module A = Bioc_checker.Policy_controlled_composition_admission
module Source = Bioc_checker.Policy_controlled_source
module Monitor = Bioc_checker.Policy_controlled_source_monitor
module Runtime = Bioc_candidate_runtime.Policy_controlled_activity
module Reference = Bioc_semantics.Policy_controlled_model_reference
module W = Bioc_checker.Work_budget
module Input = Bioc_domain.Policy_material_request
let schema_version = "biocompiler.policy_controlled_behavior_assessment.v0.1"
let implementation_version = "biocompiler.ocaml.policy_controlled_behavior_check.v0.1"
let str s = Json.String s
let obj f = Json.Object f
let arr a = Json.Array a
let get key raw = Json.field key (Json.object_fields raw)
type checked_controlled_behavior = { original:R.t; proposal:C.t; assessment:Json.t }
type result = { owner:W.t; assessment:Json.t; checked:checked_controlled_behavior option;
  request_identity:string; candidate_identity:string; invocation_identity:string }
let budget (r:result) = r.owner
let report (r:result) = r.assessment
let accepted (r:result) = r.checked
let request_fingerprint (r:result) = r.request_identity
let candidate_fingerprint (r:result) = r.candidate_identity
let invocation_fingerprint (r:result) = r.invocation_identity
let request (r:checked_controlled_behavior) = r.original
let candidate (r:checked_controlled_behavior) = r.proposal
let evidence (r:checked_controlled_behavior) = r.assessment
let measure owner raw = Input.preflight ~max_bytes:8_323_072 ~max_nodes:249_968
  ~max_depth:128 ~charge:(W.charge owner) raw
let encode owner raw =
  let bytes = measure owner raw in
  W.charge owner bytes;
  let encoded = Canonical.encode_bounded ~max_bytes:8_323_072 raw in
  Diagnostic.require (String.length encoded = bytes) "controlled_behavior_accounting"
    "Controlled behavior canonical accounting disagrees.";
  encoded
let fingerprint owner raw = let encoded = encode owner raw in
  W.charge owner (String.length encoded); Canonical.sha256 encoded

(* This reconstruction is intentionally local to the checker. It has no import
   of producer code, graph builder, candidate evaluator or candidate outcome.
   Fresh admission has independently resolved all original definition bodies,
   component/member/localization identities and the exact five-port interface. *)
let reconstruct owner original =
  let raw = Original.raw original in
  let model = get "mechanism_model" raw in
  let delays = get "delays" (get "body" model) in
  let authority = get "source_authority" raw in
  let primitives = [
    obj ["id",str "encounter";"op",str "encounter_live"];
    obj ["id",str "antigen";"op",str "physical_input";"key",str "antigen"];
    obj ["id",str "controller";"op",str "physical_input";"key",str "controller"];
    obj ["id",str "protein-a";"op",str "physical_input";"key",str "protein_a"];
    obj ["id",str "protein-b";"op",str "physical_input";"key",str "protein_b"];
    obj ["id",str "gate";"op",str "all"];
    obj ["id",str "activity";"op",str "delayed_reversible";
      "onset_ticks",get "onset_ticks" delays;"cessation_ticks",get "cessation_ticks" delays;
      "reactivation_ticks",get "reactivation_ticks" delays;
      "initial_band",str "background";"timer_scope",str "executor";
      "activation_scope",str "encounter_generation"];
    obj ["id",str "readout";"op",str "activity_band"]] in
  let wires = List.map (fun (from_,to_,input) ->
    obj ["from",str from_;"to",str to_;"input",str input]) [
      "encounter","gate","live";"antigen","gate","antigen";
      "controller","gate","controller";"protein-a","gate","protein_a";
      "protein-b","gate","protein_b";"gate","activity","enabled";
      "activity","readout","band"] in
  let expected = obj ["schema_version",str "biocompiler.policy_controlled_activity_implementation.v0.1";
    "mechanism_model",model;"control_contract",get "control_contract" authority;
    "semantics",get "semantics" (get "program" (get "document" authority));
    "catalog_binding",get "catalog_binding" raw;"assembly",get "assembly" raw;
    "context",get "context" raw;"resources",get "resources" raw;
    "primitives",arr primitives;"wires",arr wires] in
  ignore (measure owner expected); expected

let coverage_keys = ["active";"background";"antigen_absent_controller_enabled";
  "controller_disabled_antigen_present";"reversible_cycle"]
let fresh = function Domain.Fresh Domain.Valid -> true | _ -> false
let usage_json (u:Domain.usage) = obj ["prefixes",Json.int u.prefixes;
  "transitions",Json.int u.transitions;"histories",Json.int u.histories;"work",Json.int u.work]
let check ?parent ?(cancelled=fun () -> false) ~request:original_request ~candidate:proposal () =
  let limits = R.budgets original_request in
  let owner = match parent with
    | None -> W.create ~profile:R.resource_profile ~error_code:"controlled_behavior_work_limit"
        ~maximum:limits.max_work ()
    | Some parent -> W.nested ~parent ~profile:R.resource_profile
        ~error_code:"controlled_behavior_work_limit" ~maximum:limits.max_work () in
  let charge amount =
    Diagnostic.require (not (cancelled ())) "controlled_behavior_cancelled"
      "Cancelled behavior checking grants no capability.";
    W.charge owner amount in
  charge 1;
  Diagnostic.require (not (W.exhausted owner)) "controlled_behavior_work_limit"
    "Previously exhausted work cannot enter behavior checking.";
  let request = R.of_json ~charge (R.to_json original_request) in
  let candidate = C.of_json ~charge (C.to_json proposal) in
  let request_identity = R.fingerprint request and candidate_identity = C.fingerprint candidate in
  Diagnostic.require (C.request_fingerprint candidate = request_identity)
    "controlled_behavior_request_binding" "Behavior candidate belongs to different complete original authority.";
  let original = R.original request in
  let admitted = A.admit ~charge original in
  let source = Source.admit ~charge ~document:(Original.document original) in
  let typed = Source.typed source in
  let domain = A.domain admitted in
  let expected = reconstruct owner original in
  let actual = I.to_json (C.implementation candidate) in
  let expected_bytes = encode owner expected and actual_bytes = encode owner actual in
  charge (String.length expected_bytes + String.length actual_bytes);
  Diagnostic.require (expected_bytes = actual_bytes) "controlled_behavior_assembly_binding"
    "Candidate graph, complete module bodies, ports, resources or dependencies differ from independently reconstructed originals.";
  let covered = Hashtbl.create 5 in
  List.iter (fun key -> Hashtbl.add covered key false) coverage_keys;
  let requirement_counts = List.map (fun (o:Source.obligation) -> o,Array.make 4 0) typed.obligations in
  let histories = ref 0 and model_pass = ref true and source_fail = ref false
  and unresolved = ref false and pending_at_horizon = ref false in
  let availability = Array.init 2 (fun _ -> Array.make 4 0) in
  let counterexample = ref None in
  let on_history history =
    charge (1 + List.length history);
    incr histories;
    let runtime = ref (Runtime.initialize ~charge ~implementation:(C.implementation candidate) ~domain)
    and reference = ref (Reference.initialize ~charge ~original ~domain)
    and monitor = ref (Monitor.create ~charge ~source ~domain) in
    let trace = ref [] and corresponding = ref true and deployment_unknown = ref false in
    List.iter (fun (input:Domain.input_batch) ->
      charge 1;
      let next,activity = Runtime.step ~charge !runtime input in runtime := next;
      let next,expected_activity = Reference.step ~charge !reference input in reference := next;
      let actual_json = Sample.to_json activity and expected_json = Sample.to_json expected_activity in
      ignore (measure owner actual_json); ignore (measure owner expected_json);
      let matches = Json.equal actual_json expected_json in
      corresponding := !corresponding && matches;
      monitor := Monitor.step ~charge !monitor ~input ~activity ~readout:(R.readout request input.tick);
      List.iteri (fun index (rna,protein,rna_present,protein_present) ->
        charge 1;
        if not rna_present then availability.(index).(0) <- availability.(index).(0) + 1;
        if not protein_present then availability.(index).(1) <- availability.(index).(1) + 1;
        if not (fresh (Domain.effective_evidence domain input rna)) then (
          availability.(index).(2) <- availability.(index).(2) + 1; deployment_unknown := true);
        if not (fresh (Domain.effective_evidence domain input protein)) then
          availability.(index).(3) <- availability.(index).(3) + 1)
        [Domain.Rna_a,Domain.Protein_a,input.physical.rna_a,input.physical.protein_a;
         Domain.Rna_b,Domain.Protein_b,input.physical.rna_b,input.physical.protein_b];
      let frame = obj ["input",Domain.batch_to_json input;"candidate",actual_json;
        "model_reference",expected_json;"corresponds",Json.Bool matches] in
      (* At most H+1 full frames are retained per history, regardless of domain
         size. No successful or unknown branch is removed from exploration. *)
      ignore (measure owner frame); trace := frame :: !trace) history;
    let monitored = Monitor.finish ~charge !monitor in
    let rows = Json.array (get "requirements" monitored) in
    Diagnostic.require (List.length rows = List.length requirement_counts)
      "controlled_behavior_monitor_inventory" "Monitor lost an original source requirement.";
    List.iter2 (fun ((o:Source.obligation),counts) row ->
      charge 1;
      Diagnostic.require (get "id" row = str o.symbol.id && get "source_path" row = str o.symbol.path &&
          get "kind" row = str (Source.obligation_tag o.kind))
        "controlled_behavior_monitor_inventory" "Monitor reordered or substituted a source obligation.";
      let index = match Json.string (get "status" row) with
        | "pass" -> 0 | "fail" -> source_fail := true; 1
        | "unknown" -> unresolved := true; 2 | "not_exercised" -> 3
        | _ -> Diagnostic.fail "controlled_behavior_monitor_inventory" "Unknown monitor assessment." in
      counts.(index) <- counts.(index) + 1) requirement_counts rows;
    List.iter (fun (key,value) ->
      Diagnostic.require (List.mem key coverage_keys) "controlled_behavior_monitor_inventory" "Unknown coverage witness.";
      if value then Hashtbl.replace covered key true) (Monitor.coverage !monitor);
    source_fail := !source_fail || Monitor.failed !monitor;
    let pending = Runtime.pending !runtime || Reference.pending !reference || Monitor.pending !monitor in
    pending_at_horizon := !pending_at_horizon || pending;
    model_pass := !model_pass && !corresponding;
    unresolved := !unresolved || Monitor.unknown !monitor || !deployment_unknown;
    if !counterexample = None &&
        (not !corresponding || not (Monitor.satisfied !monitor) || pending || !deployment_unknown) then (
      let retained = obj ["history_index",Json.int !histories;
        "reduction",str "none_complete_original_history";
        "model_correspondence",Json.Bool !corresponding;"pending_at_horizon",Json.Bool pending;
        "deployment_evidence_unknown",Json.Bool !deployment_unknown;
        "source_monitor",monitored;"trace",arr (List.rev !trace)] in
      ignore (measure owner retained); counterexample := Some retained)
  in
  let enumeration = Domain.enumerate ~charge ~cancelled ~on_history domain in
  let completion,usage = match enumeration with
    | Domain.Complete usage -> "complete",usage
    | Domain.Exhausted usage -> "exhausted",usage
    | Domain.Cancelled usage -> "cancelled",usage in
  let all_covered = List.for_all (Hashtbl.find covered) coverage_keys in
  let complete = completion = "complete" && !histories = usage.histories && usage.histories > 0 in
  let failed = !source_fail || not !model_pass || !pending_at_horizon || (complete && not all_covered) in
  let pass = complete && all_covered && not failed && not !unresolved in
  let raw = Original.raw original in
  let assumptions = get "assumptions" (get "project_context" (get "source_authority" raw)) in
  let bindings = Json.array (get "product_bindings" (get "assembly" raw)) in
  let modules = List.mapi (fun index binding ->
    obj ["member_id",get "member_id" binding;"product_parameter",get "product_parameter" binding;
      "assumptions",get "context" raw;
      "input",str (if index = 0 then "protein_a" else "protein_b");
      "guarantee",str "identity_projection_of_supplied_functional_availability";
      "biological_realization",str "unassessed"]) bindings in
  let composition = obj ["rule",str "two_executor_owned_availability_projections_into_one_reversible_activity";
    "modules",arr modules;"wires",get "wires" expected;
    "controller_records",Json.int 1;"observation_records",Json.int 2;
    "timer_cells",Json.int 3;"state_bits",Json.int 4;
    "dependency_reconstruction",str "pass";
    "whole_program_crosscheck",str (if complete && !model_pass then "pass" else "not_accepted");
    "executable_authority",str "complete_supplied_deterministic_delay_model";
    "component_definition_role",str "declared_realization_dependencies_not_independent_executors"] in
  let availability_json = List.mapi (fun index binding -> let counts = availability.(index) in
    obj ["member_id",get "member_id" binding;"scope",str "executor";
      "rna_absent_frames",Json.int counts.(0);"protein_absent_frames",Json.int counts.(1);
      "rna_unknown_evidence_frames",Json.int counts.(2);"protein_unknown_evidence_frames",Json.int counts.(3);
      "deployment_assumptions",str "admitted_conditional_premises";
      "physical_loss",str (if counts.(0)+counts.(1)>0 then "observed_in_domain" else "not_observed");
      "evidence_status",str (if counts.(2)+counts.(3)>0 then "unknown" else "resolved")]) bindings in
  let requirements = List.map (fun ((o:Source.obligation),counts) ->
    obj ["id",str o.symbol.id;"source_path",str o.symbol.path;
      "kind",str (Source.obligation_tag o.kind);"original",o.symbol.original;
      "contract",o.contract.body;"pass",Json.int counts.(0);"fail",Json.int counts.(1);
      "unknown",Json.int counts.(2);"not_exercised",Json.int counts.(3)]) requirement_counts in
  let invocation_identity = fingerprint owner (obj ["request_fingerprint",str request_identity;
    "candidate_fingerprint",str candidate_identity]) in
  let assessment = obj ["schema_version",str schema_version;"profile",str R.profile;
    "implementation",str implementation_version;"stage",str "behavior";
    "status",str (if pass then "checked_controlled_behavior" else "not_accepted");
    "outcome",str (if pass then "pass" else if failed then "fail" else "unknown");
    "claim_scope",str "conditional_supplied_model_and_source_requirements_in_complete_finite_domain";
    "request_fingerprint",str request_identity;"candidate_fingerprint",str candidate_identity;
    "invocation_fingerprint",str invocation_identity;"admission",A.report admitted;
    "source_correspondence",Source.correspondence source;"composition",composition;
    "domain",obj ["completion",str completion;"counters",usage_json usage;
      "assessed_histories",Json.int !histories;"pending_at_horizon",Json.Bool !pending_at_horizon];
    "requirements",arr requirements;
    "coverage",obj (List.map (fun key -> key,Json.Bool (Hashtbl.find covered key)) coverage_keys);
    "model_correspondence",str (if not complete then "incomplete" else if !model_pass then "pass" else "fail");
    "evidence_status",str (if !unresolved then "unknown" else "resolved");
    "availability",arr availability_json;
    "counterexample",(match !counterexample with None -> Json.Null | Some value -> value);
    "context",get "context" raw;"assumptions",assumptions;"resources",get "resources" raw;
    "budgets",get "budgets" raw;"material_status",str "not_joined";
    "empirical_status",str "unassessed";"human_use",str "unassessed";
    "therapeutic_export",str "withheld"] in
  ignore (measure owner assessment);
  let output = W.create_output ~profile:R.resource_profile ~error_code:"controlled_behavior_publication_limit"
    ~max_bytes:limits.max_report_bytes ~max_nodes:limits.max_report_nodes () in
  W.reserve_json output assessment;
  charge 1;
  Diagnostic.require (not (W.exhausted owner)) "controlled_behavior_work_limit"
    "Exhausted checking cannot produce behavior authority.";
  let checked = if pass then Some {original=request;proposal=candidate;assessment} else None in
  {owner;assessment;checked;request_identity;candidate_identity;invocation_identity}
let replay ?parent ~request ~candidate saved =
  let fresh = check ?parent ~request ~candidate () in
  let expected = encode fresh.owner (report fresh) and observed = encode fresh.owner saved in
  W.charge fresh.owner (String.length expected + String.length observed);
  Diagnostic.require (expected = observed) "controlled_behavior_assessment_mismatch"
    "Saved evidence differs from complete fresh behavioral checking.";
  Diagnostic.require (not (W.exhausted fresh.owner)) "controlled_behavior_work_limit"
    "Exhausted replay cannot return behavioral authority.";
  fresh
