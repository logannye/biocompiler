open Bioc_wire
open Bioc_policy_prerequisite_test_support.Literals
open Bioc_policy_prerequisite_test_support.Requests
module S = Bioc_service.Policy_component_material_service
module Service = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service

let call handler role operation payload =
  let request:Protocol.request={request_id="prerequisite-material-original";operation;payload} in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_->failwith("Registered prerequisite operation failed: "^operation)
let compile request limits=call Producer.handle Protocol.Core "compile-policy-component-material"
  (obj ["request",request;"limits",limits])
let invocation request candidate limits=obj ["request",request;"candidate",candidate;"limits",limits]
let checked result =
  let report=get "report" result in
  require(get "status" report=str "checked_component_material" &&
    get "all_original_obligations_discharged" report=Json.Bool true)
    ("Fresh prerequisite conjunction failed: "^Canonical.encode report);
  require(get "implementation" result=str "biocompiler.ocaml.policy_instance_prerequisite_material.v0.1" &&
    get "validation_scope" result=str "policy-instance-prerequisite-mrna-v0.1" &&
    get "schema_version" report=str "biocompiler.policy_component_material_assessment.v0.2" &&
    get "implementation" report=str "biocompiler.ocaml.policy_component_material_check.v0.3" &&
    get "profile" report=str material_profile && get "empirical" report=str "unassessed")
    "Prerequisite result changed its separate interpretation or empirical scope";
  report
let not_accepted label result =
  let report=get "report" result in
  require(get "status" report=str "not_accepted" && get "artifact" result=Json.Null &&
    get "all_original_obligations_discharged" report=Json.Bool false)
    ("Mutation retained complete acceptance: "^label);
  report
let check_closure ?(catalog_only=false) request report =
  let closure=get "prerequisites" report in
  let expected=expected_closure ~catalog_only request
    |> add "assembly_fingerprint"(str(Canonical.fingerprint(get "assembly" report))) in
  require(Json.equal closure expected &&
    Json.equal closure(at ["context";"prerequisite_closure"]report) &&
    get "prerequisite_status" report=str "pass")
    ("Closure differs from independently declared roots, owners, allocations or exact pins: "^
      Canonical.encode closure);
  let obligations=items "obligations" report in
  require(List.length obligations=24 && List.map(get "obligation")obligations=expected_obligations &&
    List.for_all(fun row->get "status" row=str "discharged")obligations)
    "Original twenty-four obligations were dropped, replaced or left unresolved";
  let pin=str(Canonical.fingerprint closure) in
  List.iter(fun row->if List.mem(get "stage" row)
    [str "declared_context";str "conditional_component_context_conjunction"] then
      require(at ["evidence";"prerequisites"]row=pin)
        "Contextual obligation omitted its exact freshly checked prerequisite evidence")obligations
let positive ?(catalog_only=false) fixture state_reading =
  let request,_=request_literal ~catalog_only fixture state_reading and limits=get "limits" fixture in
  let compiled=compile request limits in
  let candidate=get "candidate" compiled in
  let payload=invocation request candidate limits in
  let verified=call Service.handle Protocol.Verify "check-policy-component-material" payload in
  require(Json.equal compiled verified && get "artifact" compiled=Json.Null)
    "Producer and independent verifier disagree or compilation grants premature export";
  let report=checked verified in
  check_closure ~catalog_only request report;
  List.iter(fun(key,value)->require(at ["preservation";"coverage";key]report=Json.int value)
    ("Original finite causal census changed: "^key))expected_coverage;
  require(at ["preservation";"coverage";"complete"]report=Json.Bool true)
    "Incomplete exploration became accepted prerequisite material";
  let requirements=at ["preservation";"requirements"]report |> Json.array in
  require(List.map(get "id")requirements=List.map str expected_requirements &&
    List.for_all(fun row->get "status" row=str "pass" && at ["histories";"pass"]row=Json.int 9)requirements)
    "Original hard requirements changed with prerequisite admission";
  let carriers,links=expected_projections state_reading (original_library fixture) in
  let proposed=at ["assembly_proposal";"nodes"]candidate |> Json.array in
  let endpoint reference=
    let binding=List.find(fun row->get "slot" row=get "slot" reference &&
      get "node" row=get "node" reference)proposed in
    obj ["node",get "actual" binding;"port",get "port" reference] in
  let links=arr(List.map(fun row->row
    |> replace "producer_endpoint"(endpoint(get "producer_endpoint" row))
    |> replace "consumer_endpoint"(endpoint(get "consumer_endpoint" row)))(Json.array links)) in
  require(Json.equal(at ["assembly";"carrier_projections"]report)carriers &&
    Json.equal(at ["assembly";"link_projections"]report)links)
    "Prerequisite closure changed an original material carrier or typed link";
  require(Json.equal verified(call Service.handle Protocol.Verify "replay-policy-component-material"
    (add "report" verified payload))) "Fresh prerequisite replay failed";
  let exported=call Service.handle Protocol.Verify "export-policy-component-material" payload in
  let artifact=get "artifact" exported in
  let fasta=">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n" in
  require(get "fasta" artifact=str fasta && get "fasta_sha256" artifact=str(Canonical.sha256 fasta))
    "Prerequisite closure changed the independently specified exact seventeen-base RNA";
  let manifest=get "manifest" artifact in
  require(get "profile" manifest=str material_profile && Json.equal(get "request" manifest)request &&
    Json.equal(get "candidate" manifest)candidate && Json.equal(get "assessment" manifest)report &&
    Json.equal(get "limits" manifest)limits)
    "Paired prerequisite manifest omitted complete original authority";
  require(get "members" manifest=arr [obj ["fasta_id",str "rna_0001";"member_id",str "payload";
    "molecule",N.to_json(expected_molecule());"sequence_sha256",str(Canonical.sha256 expected_sequence)]])
    "Emitted prerequisite molecule differs in exact regions, product, chemistry, origin or sequence";
  require(get "manifest_sha256" artifact=str(Canonical.sha256(Canonical.encode manifest)))
    "Manifest hash does not bind the actual paired bytes";
  request,limits,compiled

let negative_controls request limits compiled =
  let candidate=get "candidate" compiled in
  let check request=S.check ~export:false ~request ~candidate ~limits in
  let reference=original_reference request in
  let context_failure status diagnostic label request =
    phase("context negative: "^label);
    let report=not_accepted label(check request) in
    require(get "assembly_status" report=str "pass" && get "context_status" report=str status &&
      get "prerequisite_status" report=str status &&
      at ["prerequisites";"complete"]report=Json.Bool false &&
      at ["prerequisites";"diagnostics"]report=arr [str diagnostic])
      ("Wrong fresh prerequisite rejection: "^label^": "^Canonical.encode report);
    rejected "policy_component_material_export_not_accepted" (label^" cannot export")
      (fun()->S.check ~export:true ~request ~candidate ~limits) in
  let missing=edit ["context";"providers"] (fun providers->arr(List.filter(fun provider->
    provider_definition_id provider<>str definition_id)(Json.array providers)))request in
  context_failure "unknown" "prerequisite_provider_missing" "missing transitive original provider" missing;
  List.iter(fun id->
    let direct_missing=edit ["context";"providers"] (fun providers->arr(List.filter(fun provider->
      provider_definition_id provider<>str id)(Json.array providers)))request in
    context_failure "unknown" "prerequisite_provider_missing" ("missing directly bound provider: "^id) direct_missing;
    if id="exclusion.interface" then (
      let report=get "report"(check direct_missing) in
      let issues=at ["prerequisites";"graph";"issues"]report |> Json.array in
      require(List.map(get "kind")issues=List.map str ["missing";"extra"])
        "A missing interface body fabricated an edge or concealed its unresolved downstream inventory"))
    ["exclusion.interface";"exclusion.chassis"];
  phase "context negative: unresolved bodies do not relax original binding pins";
  let absent id=edit ["context";"providers"] (fun providers->arr(List.filter(fun provider->
    provider_definition_id provider<>str id)(Json.array providers)))request in
  rejected "policy_component_material_request" "Missing provider cannot excuse a stale input DefinitionRef"
    (fun()->check(put ["input_bindings";"0";"provider";"digest"](str(String.make 64 '0'))(absent "exclusion.interface")));
  rejected "policy_component_material_request" "Missing provider cannot excuse a stale resource DefinitionRef"
    (fun()->check(put ["resource_bindings";"0";"provider";"digest"](str(String.make 64 '0'))(absent "exclusion.chassis")));
  let extra=repin_provider "exclusion.interface"
    (replace "environment"(reference "exclusion.environment"))request in
  context_failure "fail" "prerequisite_provider_extra" "extra unrequired original provider" extra;
  let cycle=request |> repin_provider "exclusion.interface"
    (replace "environment"(reference "exclusion.interface"))
    |> edit ["context";"providers"] (fun providers->arr(List.filter(fun provider->
      provider_definition_id provider<>str definition_id)(Json.array providers))) in
  context_failure "fail" "prerequisite_cycle" "cyclic provider premise" cycle;
  let delivery_body=get "body"(original_provider request "exclusion.delivery")
    |> replace "definition"(reference definition_id) in
  let wrong_type=modify_provider definition_id(fun provider->
    provider |> replace "body" delivery_body |> repin)request in
  context_failure "fail" "interface_environment_body" "wrong transitive provider body type" wrong_type;
  context_failure "fail" ("guaranteed_inclusive_availability:"^definition_id)
    "transitive provider is not guaranteed through the final tick"
    (repin_provider definition_id(put ["availability";"duration_min"](str "5"))request);
  context_failure "fail" "provider_executor_or_compartment" "transitive provider belongs to another recipient"
    (repin_provider definition_id(put ["recipient";"identity"](str "cell-2"))request);
  phase "context negative: stale provider content pin";
  rejected "policy_material_context" "Modified prerequisite body needs its exact original pin"
    (fun()->check(modify_provider definition_id
      (put ["body";"availability";"duration_min"](str "5"))request));
  phase "context negative: exact shared capacity ownership";
  let shared=request
    |> edit ["resource_bindings"] (fun rows->arr(List.map(fun row->
      if get "owner" row=owner_node "exclude_edge" "edge" then
        replace "capacity"(str "local.select_edge.edge_history_cells.per_encounter_slot")row
      else row)(Json.array rows)))
    |> edit ["context";"providers"] (fun rows->arr(List.map(fun provider->provider
      |> edit ["body";"capacities"] (fun capacities->arr(List.filter(fun capacity->
        get "id" capacity<>str "local.exclude_edge.edge_history_cells.per_encounter_slot")
        (Json.array capacities))) |> repin)(Json.array rows))) in
  context_failure "fail" "shared_capacity_sum_exceeded" "two owners overdraw one exact memory pool" shared;
  let funded=repin_provider "exclusion.chassis" (edit ["capacities"] (fun rows->arr(List.map(fun row->
    if get "id" row=str "local.select_edge.edge_history_cells.per_encounter_slot" then
      replace "quantity"(Json.int 2)row else row)(Json.array rows))))shared in
  let funded_report=checked(check funded) in
  require(at ["prerequisites";"complete"]funded_report=Json.Bool true)
    "Independently funded shared capacity could not discharge the complete closure";
  phase "source negative: uninterpreted provider clauses require fresh source checking";
  let clause=obj ["$type",str "ContractClause";"kind",str "postcondition";
    "description",str "Unimplemented prerequisite guarantee";"expression",Json.Null] in
  let unsupported=rewrite_definition request definition_id(replace "clauses"(arr [clause])) in
  let unsupported_report=not_accepted "uninterpreted prerequisite contract"(compile unsupported limits) in
  require(get "prerequisite_status" unsupported_report=str "unsupported" &&
    at ["prerequisites";"diagnostics"]unsupported_report=arr [str "unimplemented_original_provider_clauses"])
    "A source contract clause became a proven executable provider guarantee";
  phase "source negative: catalog evidence is not executable closure";
  let evidence=request |> put ["implementation_request";"document";"implementations";"implementations";"0";"evidence"]
      (arr [reference definition_id]) |> refresh_catalog in
  rejected "policy_realization_unsupported" "Empirical references cannot discharge provider prerequisites"
    (fun()->compile evidence limits);
  phase "source negative: old candidate and old profile are not new authority";
  let relocated=request |> put ["implementation_request";"document";"program";"source_map";"0";"file"]
    (str "prerequisite_source_relocated.py") in
  rejected "policy_correspondence" "Old candidate cannot bind freshly relocated original source"
    (fun()->check relocated);
  let fresh=compile relocated limits in
  ignore(checked fresh);
  require(get "request_fingerprint" fresh<>get "request_fingerprint" compiled)
    "Changed original source identity was erased";
  let legacy=request
    |> replace "schema_version"(str "biocompiler.policy_component_material_request.v0.2")
    |> replace "profile"(str "biocompiler.policy_instance_component_mrna.v0.1")
    |> put ["implementation_request";"schema_version"](str "biocompiler.policy_realization_request.v0.1")
    |> put ["implementation_request";"profile"](str "biocompiler.policy_realization_inputs.v0.1")
    |> put ["context";"profile"](str "biocompiler.policy_instance_component_mrna.v0.1") in
  rejected "policy_realization_unsupported" "Legacy admission cannot silently accept dependency semantics"
    (fun()->compile legacy limits);
  phase "negative: exhaustion and imported PASS cannot authorize export";
  let incomplete_limits=put ["monitor";"max_work"](Json.int 1)limits in
  let incomplete=not_accepted "exhausted original preservation"
    (S.check ~export:false ~request ~candidate ~limits:incomplete_limits) in
  require(at ["preservation";"status"]incomplete=str "incomplete" &&
    get "prerequisite_status" incomplete=str "unassessed" && get "prerequisites" incomplete=Json.Null)
    "Exhausted preservation minted accepted prerequisite evidence";
  rejected "policy_component_material_export_not_accepted" "Incomplete prerequisite request cannot export"
    (fun()->S.check ~export:true ~request ~candidate ~limits:incomplete_limits);
  let imported=compiled |> put ["report";"prerequisites";"complete"](Json.Bool false) in
  rejected "policy_component_material_replay" "Imported closure token cannot replace fresh checking"
    (fun()->call Service.handle Protocol.Verify "replay-policy-component-material"
      (add "report" imported(invocation request candidate limits)))

let () =
  try
    require(Array.length Sys.argv=3) "Supply the two complete original A/B inputs";
    let a=read Sys.argv.(1) and b=read Sys.argv.(2) in
    phase "service A: original transitive prerequisite";
    let request,limits,compiled=positive a false in
    phase "service B: original state-reading transitive prerequisite";
    ignore(positive b true);
    phase "service: catalog-only root has its own checked provider";
    ignore(positive ~catalog_only:true a false);
    negative_controls request limits compiled;
    Printf.printf "prerequisite material service: %d independent controls passed\n" !checks
  with Diagnostic.Error value->
    Printf.eprintf "Diagnostic.Error(code=%s,path=%s,message=%s)\n" value.code
      (match value.path with None->"<none>"|Some path->path)value.message;exit 1
