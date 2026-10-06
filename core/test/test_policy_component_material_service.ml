open Bioc_wire
open Bioc_policy_component_test_support.Literals
open Bioc_policy_component_test_support.Requests
module S = Bioc_service.Policy_component_material_service
module Service = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service
let text key raw=Json.string (get key raw)
let call handler role operation payload =
  let request:Protocol.request={request_id="component-material-literal";operation;payload} in
  match handler role request with
  | Protocol.Ok,Some result,[] -> result
  | _ -> failwith ("Registered component material operation failed: "^operation)
let compile request limits=call Producer.handle Protocol.Core "compile-policy-component-material" (obj ["request",request;"limits",limits])
let payload request candidate limits=obj ["request",request;"candidate",candidate;"limits",limits]
let independent_molecule state_reading =
  let offset,length,sequence=if state_reading then 3,18,"CGCAUGGCUUAAGGAAAA" else 2,17,"CCAUGGCUUAAGGAAAA" in
  let frame="payload.frame" in
  let provenance=M.Provenance.of_json provenance in
  N.make ~id:"payload" ~form:N.Delivered_rna ~space:(G.Space.of_json (space frame length))
    ~sequence ~sequence_extent:H.Complete ~coding_status:N.Coding
    ~assembly:[N.Assembly_origin.make ~id:"payload.origin" ~destination:(G.Path.of_json (path frame 0 length))
      ~source_space:(G.Space.of_json (space "join.frame" length)) ~source_path:(G.Path.of_json (path "join.frame" 0 length)) ~provenance]
    ~features:(List.map N.Feature.of_json [feature frame "cds" "coding_sequence" offset (offset+9) (Json.int 0);
      feature frame "poly_a" "poly_a_tail" (offset+11) length Json.Null;
      feature frame "utr3" "three_prime_utr" (offset+9) (offset+11) Json.Null;
      feature frame "utr5" "five_prime_utr" 0 offset Json.Null])
    ~chemistry:(H.of_json (chemistry frame true |> put ["terminal_tail";"path"] (path frame (offset+11) length))) ~provenance
let assertion_ledger expected report =
  let ledger=items "obligations" report in
  require (List.length ledger=23 && List.map (get "obligation") ledger=items "obligations" expected)
    "Complete original twenty-three obligations changed";
  require (get "all_original_obligations_discharged" report=Json.Bool true &&
    List.for_all (fun row -> get "status" row=str "discharged") ledger) "A leaf PASS replaced the complete conjunction";
  let context_ids=["chassis_capability_and_delivery_suitability";"semantic_definition:exclusion.chassis";
    "semantic_definition:exclusion.delivery";"semantic_definition:exclusion.environment";"semantic_definition:exclusion.interface"] in
  let conjunction_ids=["realizability_and_target_suitability";"implementation_catalog_applicability";
    "implementation_applicability:exclusion.response.primitives.resolved_chassis";"semantic_definition:fixture.realization.primitives"] in
  List.iter (fun row ->
    let id=text "obligation" row in
    let stage,evidence=if List.mem id context_ids then "declared_context",obj ["context",str (Canonical.fingerprint (get "context" report))]
      else if List.mem id conjunction_ids then "conditional_component_context_conjunction",obj [
        "preservation",str (Canonical.fingerprint (get "preservation" report));
        "assembly",str (Canonical.fingerprint (get "assembly" report));"context",str (Canonical.fingerprint (get "context" report))]
      else "bounded_implementation_preservation",obj ["preservation",str (Canonical.fingerprint (get "preservation" report))] in
    require (get "stage" row=str stage && Json.equal (get "evidence" row) evidence) ("Wrong independently checked obligation evidence: "^id)) ledger
let positive fixture state_reading =
  let request=fst (request_literal fixture state_reading) and limits=get "limits" fixture in
  let compiled=compile request limits in
  let candidate=get "candidate" compiled in
  let invocation=payload request candidate limits in
  let verified=call Service.handle Protocol.Verify "check-policy-component-material" invocation in
  require (Json.equal compiled verified && Json.equal verified (call Producer.handle Protocol.Core "check-policy-component-material" invocation))
    "Actual producer/Core and independent Verify changed complete fresh evidence";
  require (get "artifact" compiled=Json.Null) "Compilation exported without a fresh export request";
  require (get "schema_version" candidate=str "biocompiler.policy_component_material_candidate.v0.1" &&
    List.sort String.compare (List.map fst (Json.object_fields candidate))=
      ["assembly_proposal";"behavior";"binding";"construction";"implementation";"schema_version"])
    "Candidate omitted a complete independently checked layer";
  let report=get "report" compiled in
  require (get "status" report=str "checked_component_material" && get "assembly_status" report=str "pass" && get "context_status" report=str "pass")
    ("Fresh complete component conjunction did not pass: "^Canonical.encode report);
  require (get "claim_scope" report=str "bounded_conditional_policy_via_reusable_components_to_exact_mrna" &&
    get "premise" report=str "supplied_component_composition_and_provider_contracts") "Component result widened its model-conditional scope";
  List.iter (fun key -> require (get key report=str "withheld") ("Coordinator authorized "^key)) ["artifact";"export"];
  require (get "empirical" report=str "unassessed") "Formal material correspondence became empirical evidence";
  List.iter (fun (key,value) -> require (at ["preservation";"coverage";key] report=Json.int value) ("Complete original domain census: "^key))
    ["histories",9;"transitions",47;"prefixes_started",48;"matched_prefixes",48];
  require (at ["preservation";"coverage";"complete"] report=Json.Bool true) "Partial domain became accepted material";
  let requirements=items "requirements" (get "preservation" report) in
  require (List.map (get "id") requirements=List.map str ["request_progress";"initiation_progress";"exclusive_selection"] &&
    List.for_all (fun row -> get "status" row=str "pass" && at ["histories";"pass"] row=Json.int 9) requirements)
    "Original hard requirements were weakened or only partly checked";
  assertion_ledger (get "expected" fixture) report;
  require (Json.equal (at ["catalog";"original_binding"] report) (get "catalog_binding" request)) "Original catalog authority was replaced";
  List.iter (fun (key,expected) -> require (get key compiled=str expected) ("Whole wrapper identity: "^key))
    ["request_fingerprint",Canonical.fingerprint request;"candidate_fingerprint",Canonical.fingerprint candidate;
     "invocation_fingerprint",Canonical.fingerprint invocation;"report_fingerprint",Canonical.fingerprint report];
  require (Json.equal compiled (call Service.handle Protocol.Verify "replay-policy-component-material" (add "report" compiled invocation)))
    "Complete independent Verify replay changed fresh result";
  let exported=call Service.handle Protocol.Verify "export-policy-component-material" invocation in
  require (Json.equal exported (call Producer.handle Protocol.Core "export-policy-component-material" invocation)) "Core and Verify fresh exports disagree";
  require (Json.equal (get "report" exported) report) "Export changed the checked conjunction";
  let molecule=independent_molecule state_reading in
  let sequence=N.sequence molecule and artifact=get "artifact" exported in
  let fasta=">rna_0001 alphabet=RNA\n"^sequence^"\n" in
  let manifest=obj ["schema_version",str "biocompiler.policy_component_mrna_manifest.v0.1";
    "profile",str "biocompiler.policy_component_mrna.v0.1";
    "claim_scope",str "bounded_conditional_policy_via_reusable_components_to_exact_mrna";
    "premise",str "supplied_component_composition_and_provider_contracts";
    "request",request;"candidate",candidate;"limits",limits;"assessment",report;
    "bindings",obj ["request_fingerprint",str (Canonical.fingerprint request);"candidate_fingerprint",str (Canonical.fingerprint candidate);
      "invocation_fingerprint",str (Canonical.fingerprint invocation);"assessment_fingerprint",str (Canonical.fingerprint report)];
    "members",arr [obj ["fasta_id",str "rna_0001";"member_id",str "payload";"molecule",N.to_json molecule;
      "sequence_sha256",str (Canonical.sha256 sequence)]];
    "fasta_sha256",str (Canonical.sha256 fasta);"empirical",str "unassessed";"original_authority",str "retain_original_inputs_separately"] in
  require (Json.equal artifact (obj ["schema_version",str "biocompiler.policy_component_mrna_export.v0.1";
    "fasta",str fasta;"fasta_sha256",str (Canonical.sha256 fasta);"manifest",manifest;
    "manifest_sha256",str (Canonical.sha256 (Canonical.encode manifest))]))
    "Exact FASTA/full-manifest pair differs from independent base/feature/chemistry/origin literals and original authorities";
  require (at ["report";"usage";"charged_work"] compiled<>Json.int 0 &&
    Z.leq (Json.integer (at ["report";"usage";"charged_work"] compiled)) (Json.integer (at ["budgets";"max_work"] request)))
    "Complete conjunction bypassed aggregate work accounting";
  request,limits,compiled,exported
let no_accept expected result =
  let report=get "report" result in
  require (get "status" report=str "not_accepted" && get "all_original_obligations_discharged" report=Json.Bool false &&
    get "artifact" result=Json.Null && get "artifact" report=str "withheld" && get "export" report=str "withheld")
    "A failed/incomplete conjunction retained material or export acceptance";
  require (List.map (get "obligation") (items "obligations" report)=expected &&
    List.for_all (fun row -> get "status" row=str "unresolved" && get "evidence" row=Json.Null) (items "obligations" report))
    "Early failure lost original obligations or discharged them from passing leaves";
  report
let negative_controls fixture request limits compiled exported =
  let candidate=get "candidate" compiled and report=get "report" compiled in
  let invocation=payload request candidate limits in
  let replay saved=call Service.handle Protocol.Verify "replay-policy-component-material" (add "report" saved invocation) in
  List.iter (fun forged -> rejected "policy_component_material_replay" "full saved wrapper must match a fresh check" (fun () -> replay forged))
    [report;replace "implementation" (str "foreign") compiled;
     replace "invocation_fingerprint" (str (String.make 64 '0')) compiled;
     (let changed=replace "empirical" (str "validated") report in compiled |> replace "report" changed
       |> replace "report_fingerprint" (str (Canonical.fingerprint changed)));
     replace "artifact" (obj ["status",str "pass"]) compiled;exported];
  rejected "unknown_field" "export cannot use serialized acceptance as authority" (fun () -> S.handle
    ~operation:"export-policy-component-material" (add "report" compiled invocation));
  let expected=items "obligations" (get "expected" fixture) in
  let incomplete_limits=put ["monitor";"max_work"] (Json.int 1) limits in
  let incomplete=no_accept expected (S.check ~export:false ~request ~candidate ~limits:incomplete_limits) in
  require (at ["preservation";"status"] incomplete=str "incomplete" &&
    at ["preservation";"coverage";"histories"] incomplete=Json.int 0 &&
    get "assembly_status" incomplete=str "unassessed" && get "context_status" incomplete=str "unassessed")
    "Insufficient monitor work still ran later acceptance stages";
  rejected "policy_component_material_export_not_accepted" "changed limits cannot reuse accepted export" (fun () ->
    S.check ~export:true ~request ~candidate ~limits:incomplete_limits);
  let bad_capacity=request |> edit ["context";"providers";"0"] (fun provider ->
    provider |> put ["body";"capacities";"0";"quantity"] (Json.int 1) |> repin) in
  let capacity_report=no_accept expected (S.check ~export:false ~request:bad_capacity ~candidate ~limits) in
  require (get "assembly_status" capacity_report=str "pass" && get "context_status" capacity_report=str "fail" &&
    at ["context";"diagnostics"] capacity_report=arr [str "shared_capacity_sum_exceeded"])
    "Shared truth pool shortage missed fresh context checking";
  rejected "policy_component_material_export_not_accepted" "changed capacity cannot export" (fun () ->
    S.check ~export:true ~request:bad_capacity ~candidate ~limits);
  let bad_material=candidate |> put ["construction";"inventory";"molecules";"0";"sequence"] (str "ACAUGGCUUAAGGAAAA") in
  let bad_material=bad_material |> put ["construction";"inventory";"role_instances";"0";"subject_fingerprint"]
    (str (Canonical.fingerprint (at ["construction";"inventory";"molecules";"0"] bad_material))) in
  let material_report=no_accept expected (S.check ~export:false ~request ~candidate:bad_material ~limits) in
  require (get "assembly_status" material_report=str "fail" && get "context_status" material_report=str "unassessed")
    "Changed exact bases bypassed fresh independent construction/PM correspondence";
  rejected "policy_component_material_export_not_accepted" "changed bases cannot export" (fun () ->
    S.check ~export:true ~request ~candidate:bad_material ~limits);
  let bad_mapping=put ["assembly_proposal";"nodes";"0";"actual"] (str "unowned.node") candidate in
  let mapping_report=no_accept expected (S.check ~export:false ~request ~candidate:bad_mapping ~limits) in
  require (List.mem (str "ordered_total_actual_node_bijection") (at ["assembly";"diagnostics"] mapping_report |> Json.array))
    "Public checker failed to enforce complete local-to-actual ownership";
  rejected "policy_implementation_contract" "configuration pin cannot stand in for its model" (fun () ->
    S.check ~export:false ~request ~candidate:(put ["implementation";"nodes";"0";"configuration_digest"] (str (String.make 64 '0')) candidate) ~limits);
  List.iter (fun field -> rejected (if field="max_work" then "policy_component_material_work_limit" else "policy_component_material_publication_limit")
    ("fresh whole conjunction allowance: "^field) (fun () -> S.check ~export:true
      ~request:(put ["budgets";field] (Json.int 1) request) ~candidate ~limits)) ["max_work";"max_report_bytes";"max_report_nodes"];
  rejected "unknown_field" "producer does not accept a suggested candidate as source" (fun () ->
    compile (add "candidate" candidate request) limits);
  rejected "unknown_field" "producer input cannot carry a preselected candidate" (fun () ->
    call Producer.handle Protocol.Core "compile-policy-component-material"
      (obj ["request",request;"limits",limits;"candidate",candidate]))
let source_controls request limits compiled =
  let candidate=get "candidate" compiled in
  let relocated=put ["implementation_request";"document";"program";"source_map";"0";"file"] (str "relocated_original_component_policy.py") request in
  rejected "policy_correspondence" "old source candidate cannot transfer after location edit" (fun () -> S.check ~export:true ~request:relocated ~candidate ~limits);
  let fresh=compile relocated limits in
  require (at ["report";"status"] fresh=str "checked_component_material") "Location-only source change lost fresh complete derivation";
  let fresh_payload=payload relocated (get "candidate" fresh) limits in
  require (Json.equal fresh (call Service.handle Protocol.Verify "check-policy-component-material" fresh_payload)) "Relocated source lacks independent fresh check";
  rejected "policy_component_material_replay" "old wrapper cannot authorize freshly lowered changed source" (fun () ->
    call Service.handle Protocol.Verify "replay-policy-component-material" (add "report" compiled fresh_payload));
  let exported=call Service.handle Protocol.Verify "export-policy-component-material" fresh_payload in
  require (at ["artifact";"fasta"] exported=str ">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n" &&
    Json.equal (at ["artifact";"manifest";"request"] exported) relocated) "Identical RNA lost changed full original authority";
  List.iter (fun key -> require (get key fresh<>get key compiled) ("Source relocation reused stale "^key))
    ["request_fingerprint";"candidate_fingerprint";"invocation_fingerprint";"report_fingerprint"];
  let extra=at ["implementation_request";"document";"program";"semantics";"definitions";"0"] request
    |> replace "id" (str "extra.unresolved") |> replace "meaning" (str "Uninterpreted original premise without component or provider discharge.") in
  let unresolved=request |> edit ["implementation_request";"document";"program";"semantics";"definitions"]
    (fun rows -> arr (Json.array rows@[extra])) in
  let result=compile unresolved limits in
  let report=get "report" result in
  require (get "status" report=str "not_accepted" && get "assembly_status" report=str "pass" && get "context_status" report=str "pass" &&
    List.length (items "obligations" report)=24 && get "artifact" result=Json.Null)
    "Three passing leaves erased an additional original unresolved premise";
  require (List.map (get "obligation") (List.filter (fun row -> get "status" row=str "unresolved") (items "obligations" report))=
    [str "semantic_definition:extra.unresolved"]) "New original obligation was silently discharged or unrelated discharges changed";
  rejected "policy_component_material_export_not_accepted" "open original premise cannot export" (fun () ->
    S.check ~export:true ~request:unresolved ~candidate:(get "candidate" result) ~limits);
  let declarations=at ["implementation_request";"document";"program";"declarations"] request |> Json.array in
  let unknown=get "condition" (List.nth declarations 11) |> replace "value" (str "unknown") in
  let requirement=List.nth declarations 13 |> replace "id" (str "unresolved_truth") |> replace "condition" unknown in
  let location=at ["implementation_request";"document";"program";"source_map";"0"] request
    |> replace "declaration_id" (str "unresolved_truth") |> replace "line" (Json.int 1000) in
  let append value raw=arr (Json.array raw@[value]) in
  let unknown_request=request |> edit ["implementation_request";"document";"program";"declarations"] (append requirement)
    |> edit ["implementation_request";"document";"program";"source_map"] (append location)
    |> edit ["implementation_request";"document";"assurance";"requirements"] (append (str "unresolved_truth")) in
  let unknown_result=compile unknown_request limits in
  let unknown_report=get "report" unknown_result in
  require (get "status" unknown_report=str "not_accepted" && get "artifact" unknown_result=Json.Null &&
    get "assembly_status" unknown_report=str "unassessed" && get "context_status" unknown_report=str "unassessed" &&
    at ["preservation";"status"] unknown_report=str "requirements_not_satisfied")
    "Additional hard UNKNOWN source property crossed complete material acceptance";
  let row=List.find (fun row -> get "id" row=str "unresolved_truth") (at ["preservation";"requirements"] unknown_report |> Json.array) in
  require (get "status" row=str "unknown" && List.length (items "obligations" unknown_report)=24 &&
    List.for_all (fun row -> get "status" row=str "unresolved" && get "evidence" row=Json.Null) (items "obligations" unknown_report))
    "UNKNOWN property or full original obligation ledger was weakened";
  rejected "policy_component_material_export_not_accepted" "hard UNKNOWN source requirement cannot export" (fun () ->
    S.check ~export:true ~request:unknown_request ~candidate:(get "candidate" unknown_result) ~limits)
let routing_and_publication request limits =
  let operation="compile-policy-component-material" in
  let request:Protocol.request={request_id="verify-component-producer";operation;payload=obj ["request",request;"limits",limits]} in
  (match Service.handle Protocol.Verify request with Protocol.Unsupported,None,[diagnostic] ->
    require (diagnostic.code="unsupported_operation") "Verify compile returned an unrelated rejection"
   | _ -> failwith "Standalone Verify acquired a component producer");
  let capabilities=call Service.handle Protocol.Verify "capabilities" (obj []) in
  require (Json.equal (at ["profiles";"policy_component_material"] capabilities) S.profile &&
    not (List.mem_assoc "policy_component_material_producer" (Json.object_fields (get "profiles" capabilities))))
    "Standalone Verify capability scope changed";
  let core=call Producer.handle Protocol.Core "capabilities" (obj []) in
  require (Json.equal (at ["profiles";"policy_component_material_producer"] core) S.producer_profile)
    "Core omitted the separately versioned untrusted producer route";
  List.iter (fun value -> rejected "policy_component_material_service_publication_limit" "whole paired wrapper publication is bounded"
    (fun () -> S.validate_publication value))
    [arr (List.init Limits.max_json_nodes (fun _ -> Json.Null));str (String.make (9*1024*1024) 'x');
     List.fold_left (fun value _ -> arr [value]) Json.Null (List.init 129 Fun.id)]
let run first second =
  let request,limits,compiled,exported=positive first false in
  let request_b,limits_b,compiled_b,_=positive second true in
  negative_controls first request limits compiled exported;source_controls request limits compiled;
  rejected ~message:"Candidate names a different independently supplied library." "policy_implementation_contract"
    "A candidate cannot transfer across the original B model library" (fun () ->
    S.check ~export:true ~request:request_b ~candidate:(get "candidate" compiled) ~limits:limits_b);
  rejected "policy_component_material_replay" "A saved wrapper cannot transfer to B complete originals" (fun () ->
    call Service.handle Protocol.Verify "replay-policy-component-material"
      (add "report" compiled (payload request_b (get "candidate" compiled_b) limits_b)));
  routing_and_publication request limits;
  Printf.printf "component material public coordinator/service: %d independent checks passed\n" !checks
let () =
  Printexc.register_printer (function Diagnostic.Error value -> Some (Printf.sprintf "Diagnostic.Error(code=%s,path=%s,message=%s)"
    value.code (Option.value ~default:"<none>" value.path) value.message) | _ -> None);
  require (Array.length Sys.argv=3) "Supply independent A/B original material fixtures";
  run (read Sys.argv.(1)) (read Sys.argv.(2))
