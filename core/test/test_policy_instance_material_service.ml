open Bioc_wire
open Bioc_policy_instance_test_support.Literals
open Bioc_policy_instance_test_support.Requests
module S = Bioc_service.Policy_component_material_service
module Service = Bioc_service.Service
module Producer = Bioc_producer_service.Producer_service

let phase label=Printf.eprintf "instance material service: %s\n%!" label
let call handler role operation payload =
  let request:Protocol.request={request_id="instance-material-literal";operation;payload} in
  match handler role request with
  | Protocol.Ok,Some result,[]->result
  | _->failwith("Registered instance operation failed: "^operation)
let compile request limits=call Producer.handle Protocol.Core "compile-policy-component-material"
  (obj ["request",request;"limits",limits])
let invocation request candidate limits=obj ["request",request;"candidate",candidate;"limits",limits]
let checked result =
  let report=get "report" result in
  require(get "status" report=str "checked_component_material" &&
    get "all_original_obligations_discharged" report=Json.Bool true)
    ("Fresh instance conjunction failed: "^Canonical.encode report);
  require(get "profile" report=str "biocompiler.policy_instance_component_mrna.v0.1" &&
    get "empirical" report=str "unassessed") "Instance result changed its scope or empirical status";
  report
let check_obligations fixture report =
  let rows=items "obligations" report in
  require(List.length rows=23 && List.map(get "obligation")rows=(at ["expected";"obligations"] fixture |> Json.array))
    "Original twenty-three obligations were dropped or replaced";
  require(List.for_all(fun row->get "status" row=str "discharged")rows)
    "An unresolved obligation was treated as complete"
let positive fixture state_reading =
  let request,_=request_literal fixture state_reading and limits=get "limits" fixture in
  let compiled=compile request limits in
  let candidate=get "candidate" compiled in
  let payload=invocation request candidate limits in
  let verified=call Service.handle Protocol.Verify "check-policy-component-material" payload in
  require(Json.equal compiled verified) "Producer and producer-free verifier disagree on instance acceptance";
  require(get "artifact" compiled=Json.Null) "Compilation granted premature export";
  let report=checked verified in
  check_obligations fixture report;
  List.iter(fun(key,value)->require(at ["preservation";"coverage";key]report=Json.int value)
    ("Original finite causal census changed: "^key))expected_coverage;
  require(at ["preservation";"coverage";"complete"]report=Json.Bool true)
    "Incomplete exploration became accepted material";
  let requirements=at ["preservation";"requirements"]report |> Json.array in
  require(List.map(get "id")requirements=List.map str expected_requirements &&
    List.for_all(fun row->get "status" row=str "pass" && at ["histories";"pass"]row=Json.int 9)requirements)
    "Complete original hard requirements changed";
  let carriers,links=expected_projections state_reading (original_library fixture) in
  let proposed=at ["assembly_proposal";"nodes"]candidate |> Json.array in
  (* The independent oracle names original instance endpoints. Actual node
     spelling is only a proposal convention; check its separately verified map
     when comparing report presentation, never when deriving behavior/material. *)
  let endpoint reference=
    let binding=List.find(fun row->get "slot" row=get "slot" reference &&
      get "node" row=get "node" reference)proposed in
    obj ["node",get "actual" binding;"port",get "port" reference] in
  let links=arr(List.map(fun row->row
    |> replace "producer_endpoint"(endpoint(get "producer_endpoint" row))
    |> replace "consumer_endpoint"(endpoint(get "consumer_endpoint" row)))(Json.array links)) in
  require(Json.equal(at ["assembly";"carrier_projections"]report)carriers &&
    Json.equal(at ["assembly";"link_projections"]report)links)
    "Exact independent carrier, join or endpoint projection changed";
  let actual slot=List.find(fun row->get "slot" row=str slot && get "node" row=str "edge")proposed |> get "actual" in
  require(actual "select_edge"<>actual "exclude_edge") "Repeated stateful fragments share one actual memory owner";
  require(List.length proposed=(if state_reading then 17 else 15)) "Total instance-to-actual ownership changed";
  require(Json.equal verified(call Service.handle Protocol.Verify "replay-policy-component-material"(add "report" verified payload)))
    "Fresh producer-free replay failed";
  let exported=call Service.handle Protocol.Verify "export-policy-component-material" payload in
  let artifact=get "artifact" exported in
  let fasta=">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n" in
  require(get "fasta" artifact=str fasta && get "fasta_sha256" artifact=str(Canonical.sha256 fasta))
    "Three supplied roots did not emit the independently specified exact RNA";
  let manifest=get "manifest" artifact in
  require(get "profile" manifest=str "biocompiler.policy_instance_component_mrna.v0.1" &&
    Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "assessment" manifest)report && Json.equal(get "limits" manifest)limits)
    "Paired manifest does not retain complete original-bound authority";
  require(get "members" manifest=arr [obj ["fasta_id",str "rna_0001";"member_id",str "payload";
    "molecule",N.to_json(expected_molecule());"sequence_sha256",str(Canonical.sha256 expected_sequence)]])
    "Emitted molecule differs in literal regions, product, chemistry, origin or sequence";
  require(get "manifest_sha256" artifact=str(Canonical.sha256(Canonical.encode manifest)))
    "Manifest hash does not bind the actual paired bytes";
  request,limits,compiled

let not_accepted label result =
  let report=get "report" result in
  require(get "status" report=str "not_accepted" && get "artifact" result=Json.Null &&
    get "all_original_obligations_discharged" report=Json.Bool false)
    ("Mutation retained complete acceptance: "^label);
  report

let instance_rename_control fixture request limits compiled =
  let _,original_union=request_literal fixture false in
  let names=["select_edge","edge_left";"control","controller";"exclude_edge","edge_right"] in
  let features=List.map(fun(slot,local)->feature_id slot local,feature_id(List.assoc slot names)local)
    ["select_edge","utr5";"control","cds";"exclude_edge","utr3";"exclude_edge","poly_a"] in
  let rec renamed = function
    | Json.String value->str(Option.value ~default:value(List.assoc_opt value(names@features)))
    | Json.Array values->arr(List.map renamed values)
    | Json.Object fields->obj(List.map(fun(key,value)->key,renamed value)fields)
    | value->value in
  (* Renaming changes the lexical order of qualified feature identities.
     Re-author the original material through its typed domain constructor so
     unordered region inventories retain their canonical representation. This
     uses only the independently declared authority, never producer output. *)
  let changed_rule=renamed(get "composition_rule" request)
    |> edit ["body";"material_authority"] (fun material->PM.to_json(PM.of_json material))
    |> repin in
  let layout=at ["context";"record_layout"]request
    |> replace "rule"(get "identity" changed_rule)
    |> replace "union_digest"(str(Canonical.fingerprint(renamed original_union))) in
  let context=get "context" request |> replace "record_layout" layout
    |> edit ["providers"] (fun providers->arr(List.map(fun provider->provider
      |> edit ["body";"capacities"] (fun capacities->arr(List.map
        (replace "record_layout_digest"(str(Canonical.fingerprint layout)))(Json.array capacities)))
      |> repin)(Json.array providers))) in
  let catalog=get "catalog_binding" request
    |> replace "rule"(get "identity" changed_rule)
    |> replace "components"(at ["body";"components"]changed_rule) in
  let changed=request |> replace "composition_rule" changed_rule |> replace "context" context
    |> replace "catalog_binding" catalog |> edit ["resource_bindings"] renamed in
  phase "rename: reject stale mapping";
  ignore(not_accepted "old instance mapping under freshly renamed authority"
    (S.check ~export:false ~request:changed ~candidate:(get "candidate" compiled) ~limits));
  phase "rename: compile and export fresh mapping";
  let fresh=compile changed limits in
  ignore(checked fresh);
  let exported=call Service.handle Protocol.Verify "export-policy-component-material"
    (invocation changed(get "candidate" fresh)limits) in
  require(at ["artifact";"fasta"]exported=str ">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n")
    "Consistent instance renaming changed the independently specified RNA";
  require(Json.equal(at ["artifact";"manifest";"members";"0";"molecule"]exported)
    (N.to_json(N.of_json(renamed(N.to_json(expected_molecule()))))))
    "Fresh instance renaming failed to preserve exact material apart from qualified annotations";
  require(get "request_fingerprint" fresh<>get "request_fingerprint" compiled)
    "Instance rename erased changed authority identity"

let negative_controls request limits compiled =
  phase "negative: state ownership alias";
  let candidate=get "candidate" compiled in
  let check candidate=S.check ~export:false ~request ~candidate ~limits in
  let proposed=at ["assembly_proposal";"nodes"]candidate |> Json.array in
  let leading=List.find(fun row->get "slot" row=str "select_edge")proposed |> get "actual" in
  let aliased=candidate |> edit ["assembly_proposal";"nodes"] (fun rows->arr(List.map(fun row->
    if get "slot" row=str "exclude_edge" then replace "actual" leading row else row)(Json.array rows))) in
  let alias_report=not_accepted "repeated state ownership alias"(check aliased) in
  require(get "assembly_status" alias_report=str "fail") "Aliased repeated state did not fail assembly ownership";
  phase "negative: altered bases and chemistry";
  let bad_sequence=candidate |> put ["construction";"inventory";"molecules";"0";"sequence"] (str "CCAUGGCCUAAGGAAAA") in
  let bad_sequence=bad_sequence |> put ["construction";"inventory";"role_instances";"0";"subject_fingerprint"]
    (str(Canonical.fingerprint(at ["construction";"inventory";"molecules";"0"]bad_sequence))) in
  let altered=not_accepted "same peptide does not authorize different bases"(check bad_sequence) in
  require(get "assembly_status" altered=str "fail") "Synonymous mutation bypassed exact root/material authority";
  let changed_chemistry=candidate |> put ["construction";"inventory";"molecules";"0";"chemistry";"cap";"identity";"accession"] (str "different_cap") in
  let changed_chemistry=changed_chemistry |> put ["construction";"inventory";"role_instances";"0";"subject_fingerprint"]
    (str(Canonical.fingerprint(at ["construction";"inventory";"molecules";"0"]changed_chemistry))) in
  ignore(not_accepted "same sequence does not authorize different chemistry"(check changed_chemistry));
  phase "negative: shared memory overdraw";
  (* The shared authority declares one pool for the two distinct owners. Drop
     the superseded private pool, since complete context checking also rejects
     unused original capacities. The funded control below changes only this
     shared pool's quantity, from one cell to two. *)
  let shared=request
    |> edit ["resource_bindings"] (fun rows->arr(List.map(fun row->
      if get "owner" row=owner_node "exclude_edge" "edge" then
        replace "capacity"(str "local.select_edge.edge_history_cells.per_encounter_slot")row else row)(Json.array rows)))
    |> edit ["context";"providers"] (fun rows->arr(List.map(fun provider->
      provider |> edit ["body";"capacities"] (fun capacities->arr(List.filter(fun capacity->
        get "id" capacity<>str "local.exclude_edge.edge_history_cells.per_encounter_slot")
        (Json.array capacities))) |> repin)(Json.array rows))) in
  let overcommit=not_accepted "two edge instances overdraw one memory pool"
    (S.check ~export:false ~request:shared ~candidate ~limits) in
  require(get "assembly_status" overcommit=str "pass" && get "context_status" overcommit=str "fail" &&
    List.mem(str "shared_capacity_sum_exceeded")(at ["context";"diagnostics"]overcommit |> Json.array))
    "Instance resource ownership did not reach aggregate capacity checking";
  phase "negative: funded shared memory control";
  let funded=shared |> edit ["context";"providers"] (fun rows->arr(List.map(fun provider->
    provider |> edit ["body";"capacities"] (fun capacities->arr(List.map(fun capacity->
      if get "id" capacity=str "local.select_edge.edge_history_cells.per_encounter_slot" then
        replace "quantity"(Json.int 2)capacity else capacity)(Json.array capacities))) |> repin)(Json.array rows))) in
  ignore(checked(S.check ~export:false ~request:funded ~candidate ~limits));
  phase "negative: exhausted preservation";
  let incomplete_limits=put ["monitor";"max_work"] (Json.int 1)limits in
  let incomplete=not_accepted "exhausted exploration"(S.check ~export:false ~request ~candidate ~limits:incomplete_limits) in
  require(at ["preservation";"status"]incomplete=str "incomplete" && get "assembly_status" incomplete=str "unassessed")
    "Exhausted preservation reached an accepted assembly";
  rejected "policy_component_material_export_not_accepted" "Incomplete instance cannot export"(fun()->
    S.check ~export:true ~request ~candidate ~limits:incomplete_limits);
  phase "negative: imported report and relocated source";
  let payload=invocation request candidate limits in
  rejected "policy_component_material_replay" "Imported PASS cannot replace fresh checking"(fun()->
    call Service.handle Protocol.Verify "replay-policy-component-material"
      (add "report"(replace "report_fingerprint"(str(String.make 64 '0'))compiled)payload));
  let relocated=request |> put ["implementation_request";"document";"program";"source_map";"0";"file"]
    (str "instance_source_relocated.py") in
  rejected "policy_correspondence" "Old graph cannot bind relocated original source"(fun()->
    S.check ~export:true ~request:relocated ~candidate ~limits);
  let fresh=compile relocated limits in
  ignore(checked fresh);
  require(get "request_fingerprint" fresh<>get "request_fingerprint" compiled)
    "Fresh original source identity was erased"

let () =
  try
    require(Array.length Sys.argv=3) "Supply the two complete original A/B inputs";
    let a=read Sys.argv.(1) and b=read Sys.argv.(2) in
    phase "A: original positive";
    let request,limits,compiled=positive a false in
    phase "B: original positive";
    ignore(positive b true);
    phase "rename: author canonical renamed originals";
    instance_rename_control a request limits compiled;
    phase "negative: begin controls";
    negative_controls request limits compiled;
    Printf.printf "instance material service: %d independent controls passed\n" !checks
  with Diagnostic.Error value->
    Printf.eprintf "Diagnostic.Error(code=%s,path=%s,message=%s)\n" value.code
      (match value.path with None->"<none>"|Some path->path)value.message;exit 1
