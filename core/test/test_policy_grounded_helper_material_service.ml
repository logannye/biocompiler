open Bioc_wire
open Bioc_policy_grounded_helper_test_support.Literals
open Bioc_policy_grounded_helper_test_support.Requests
module Service=Bioc_service.Service
module Producer=Bioc_producer_service.Producer_service
module R=Bioc_domain.Policy_component_material_request
module A=Bioc_domain.Policy_component_assembly_rule
let ()=Printexc.register_printer(function Diagnostic.Error d->Some("Diagnostic.Error("^d.code^", "^d.message^")")|_->None)
let phase value=Printf.eprintf "grounded-helper witness: %s\n%!" value
exception Service_rejection of string
let call handler role operation payload=
  let request:Protocol.request={request_id="grounded-helper-independent-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_,_,diagnostics->raise(Service_rejection(operation^": "^String.concat "; "(List.map(fun(d:Diagnostic.t)->d.code^": "^d.message)diagnostics)))
let invocation request candidate limits=obj["request",request;"candidate",candidate;"limits",limits]
let compile request limits=call Producer.handle Protocol.Core "compile-policy-component-material"(obj["request",request;"limits",limits])
let checked result=
  let report=get "report" result in
  require(get "status" report=str "checked_component_material" && get "all_original_obligations_discharged" report=Json.Bool true)
    ("Complete grounded-helper conjunction rejected: "^Canonical.encode report);
  require(get "implementation" result=str "biocompiler.ocaml.policy_grounded_helper_prerequisite_material.v0.1" &&
    get "validation_scope" result=str "policy-grounded-helper-prerequisite-mrna-v0.1" &&
    get "schema_version" report=str "biocompiler.policy_component_material_assessment.v0.4" &&
    get "implementation" report=str "biocompiler.ocaml.policy_component_material_check.v0.6" && get "profile" report=str material_profile &&
    at["assembly";"checker_version"]report=str "biocompiler.ocaml.policy_component_assembly_check.v0.4" &&
    at["context";"schema_version"]report=str "biocompiler.policy_component_context_assessment.v0.3" &&
    at["preservation";"binding";"profile"]report=str "biocompiler.policy_multi_product_staged_source_graph.v0.1" &&
    get "empirical" report=str "unassessed")"Grounded-helper interpretation used legacy evidence or widened its empirical scope";
  report
let rejected_count=ref 0
let reject label action=
  phase("negative "^label);
  match action()with
  |result->require(at["report";"status"]result=str "not_accepted" && get "artifact" result=Json.Null &&
      at["report";"all_original_obligations_discharged"]result=Json.Bool false)("Mutation accepted: "^label);incr rejected_count
  |exception Diagnostic.Error _->incr rejected_count
  |exception Service_rejection _->incr rejected_count
let rejected_decode label action=
  match action()with _->failwith("Malformed original decoded: "^label)
  |exception Diagnostic.Error _->incr rejected_count
let proposal candidate=at["assembly_proposal";"nodes"]candidate |> Json.array
let actual candidate reference=get "actual"(List.find(fun row->get "slot" row=get "slot" reference && get "node" row=get "node" reference)(proposal candidate))
let endpoint candidate reference=obj["node",actual candidate reference;"port",get "port" reference]
let check_graph union candidate=
  let expected=items "nodes" union and proposed=proposal candidate in
  require(List.map(fun row->get "slot" row,get "node" row)proposed=List.map(fun row->get "slot" row,get "node" row)expected &&
    List.length(List.sort_uniq compare(List.map(get "actual")proposed))=29)"Original-to-actual mapping is not a complete ordered bijection";
  let nodes=List.map(fun row->let model=get "model" row in obj["id",actual candidate row;
    "model",get "identity" model;"configuration_digest",get "configuration_digest" model])expected in
  let wires=List.map(fun row->obj["producer",endpoint candidate(get "producer" row);"consumer",endpoint candidate(get "consumer" row)])(items "wires" union)in
  let inputs=List.map(fun row->replace "consumer"(endpoint candidate(get "consumer" row))row)(items "inputs" union)in
  let groups=List.map(fun row->obj["id",get "id" row;"arbiter",actual candidate(get "arbiter" row);
    "commits",arr(List.map(actual candidate)(items "commits" row))])(items "atomic_groups" union)in
  let graph=get "implementation" candidate in
  require(List.length nodes=29 && List.length wires=55 && List.length groups=1 &&
    List.length(items "commits"(List.hd groups))=7 &&
    Json.equal(get "nodes" graph)(arr nodes) && Json.equal(get "wires" graph)(arr wires) &&
    Json.equal(get "inputs" graph)(arr inputs) && Json.equal(get "atomic_groups" graph)(arr groups) &&
    Json.equal(get "semantic_exports" graph)(arr(List.map(endpoint candidate)(items "semantic_exports" union))))
    "Actual graph differs from independent complete node/model/wire/input/export/atomic-group authority"
let check_projections fixture alternate request candidate report=
  let carriers,links=expected_projections fixture alternate request in
  let links=arr(List.map(fun row->row |> replace "producer_endpoint"(endpoint candidate(get "producer_endpoint" row))
    |> replace "consumer_endpoint"(endpoint candidate(get "consumer_endpoint" row)))(Json.array links))in
  require(Json.equal(at["assembly";"carrier_projections"]report)carriers && Json.equal(at["assembly";"link_projections"]report)links)
    "Member geometry, product carriers or explicit noncovalent transport differ from independent original authority";
  require(Json.equal(at["assembly";"helper_projections"]report)(expected_helper_projections fixture alternate))
    "Helper projection differs from complete independent material and final molecule authority"
let check_closure fixture alternate request report=
  let expected=expected_closure fixture alternate request |> add "assembly_fingerprint"(str(Canonical.fingerprint(get "assembly" report)))in
  let closure=get "prerequisites" report in
  require(Json.equal closure expected && Json.equal closure(at["context";"prerequisite_closure"]report) && get "prerequisite_status" report=str "pass")
    ("Grounded-helper closure differs from complete original roots, owners, transport or shared-window allocations: "^Canonical.encode closure);
  require(Json.equal(at["context";"helper_allocations"]report)(arr[expected_helper_allocation fixture alternate request]))
    "Helper bootstrap, ownership or exact shared allocations changed";
  let obligations=items "obligations" report in
  require(List.map(get "obligation")obligations=expected_obligations && List.length obligations=24 &&
    List.for_all(fun row->get "status" row=str "discharged")obligations)"Original24 obligations changed or were left unresolved";
  List.iter(fun row->if List.mem(get "stage" row)[str "declared_context";str "conditional_component_context_conjunction"]then
    require(at["evidence";"prerequisites"]row=str(Canonical.fingerprint closure))"Contextual obligation lost private prerequisite closure")obligations
let positive fixture alternate=
  phase(if alternate then "B: independently changed helper material"else "A: complete original two-payload and helper request");
  let request,union=request_literal fixture alternate and limits=invocation_limits fixture in
  let decoded=R.of_json request in
  require(Json.equal request(R.to_json decoded) && Json.equal union(Bioc_domain.Policy_component_context.ordered_union_json(R.composition_rule decoded)))
    "Original request or independently authored ordered union changed during decoding";
  let produced=compile request limits in
  let candidate=get "candidate" produced in
  let report=checked produced in
  check_graph union candidate;check_projections fixture alternate request candidate report;check_closure fixture alternate request report;
  require(get "artifact" produced=Json.Null)"Compilation bypassed fresh export";
  List.iter(fun(key,count)->require(at["preservation";"coverage";key]report=Json.int count)("Finite-domain census changed: "^key))
    ["histories",25;"transitions",86;"prefixes_started",87;"matched_prefixes",87];
  require(at["preservation";"coverage";"complete"]report=Json.Bool true)"Incomplete finite exploration granted material acceptance";
  let requirements=at["preservation";"requirements"]report |> Json.array in
  require(List.map(get "id")requirements=List.map str["first_initiation";"second_initiation"] &&
    List.for_all(fun row->get "status" row=str "pass" && get "nonvacuous" row=Json.Bool true)requirements)
    "Two-product source requirements became weakened or vacuous";
  require(Json.equal(at["construction";"inventory";"molecules"]candidate)(expected_molecules fixture alternate))
    "Emitted molecules differ in exact original regions, products, chemistry, origin or sequence";
  let payload=invocation request candidate limits in
  let fresh=call Service.handle Protocol.Verify "check-policy-component-material" payload in
  require(Json.equal fresh produced)"Producer and independent verifier disagree";
  require(Json.equal fresh(call Service.handle Protocol.Verify "replay-policy-component-material"(add "report" fresh payload)))"Fresh replay changed acceptance";
  let exported=call Service.handle Protocol.Verify "export-policy-component-material" payload in
  require(Json.equal exported(call Producer.handle Protocol.Core "export-policy-component-material" payload))"Core/Verify fresh exports disagree";
  let artifact=get "artifact" exported in
  let fasta=">rna_0001 alphabet=RNA\n"^sequence "controller_a" false^"\n>rna_0002 alphabet=RNA\n"^sequence "stage_b" false^"\n>rna_0003 alphabet=RNA\n"^helper_sequence alternate^"\n"in
  require(get "fasta" artifact=str fasta && get "fasta_sha256" artifact=str(Canonical.sha256 fasta))"Ordered three-RNA FASTA differs from original sequences";
  let manifest=get "manifest" artifact in
  require(Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "limits" manifest)limits && Json.equal(get "assessment" manifest)report &&
    get "manifest_sha256" artifact=str(Canonical.sha256(Canonical.encode manifest)))"Fresh manifest drops complete original authority or assessment";
  let members=List.mapi(fun index slot->obj["fasta_id",str(Printf.sprintf "rna_%04d"(index+1));"member_id",str(member_id slot);
    "molecule",molecule_literal fixture slot false ~output:true;"sequence_sha256",str(Canonical.sha256(sequence slot false))])slots @ [obj["fasta_id",str "rna_0003";"member_id",str helper_member;
    "molecule",helper_molecule fixture alternate ~output:true;"sequence_sha256",str(Canonical.sha256(helper_sequence alternate))]]in
  require(Json.equal(get "members" manifest)(arr members))"Manifest did not retain exact ordered material members";
  request,candidate,limits,produced
let rewrite_provider id transform request=edit["context";"providers"](fun raw->arr(List.map(fun provider->
  if at["body";"definition";"id"]provider=str id then provider |> edit["body"]transform |> repin else provider)(Json.array raw)))request
let negatives request candidate limits produced=
  let check ?(export=false) request candidate=call Service.handle Protocol.Verify
    (if export then "export-policy-component-material"else "check-policy-component-material")(invocation request candidate limits)in
  let mutant label transform=reject label(fun()->check request(transform candidate))in
  mutant "helper material deleted"(edit["construction";"inventory";"molecules"](fun raw->arr[at["0"]raw;at["1"]raw]));
  mutant "helper sequence substituted"(put["construction";"inventory";"molecules";"2";"sequence"](str(helper_sequence true)));
  mutant "helper feature identity rewritten"(put["construction";"inventory";"molecules";"2";"features";"0";"id"](str "foreign_cds"));
  mutant "helper final chemistry substituted"(put["construction";"inventory";"molecules";"2";"chemistry";"modification_inventory_status"](str "unknown"));
  mutant "helper renamed as payload"(put["construction";"member_order";"2"](str "payload_a"));
  let original=R.of_json request in
  let bad_rule label transform=rejected_decode label(fun()->A.of_json ~components:(R.component_library original)
    (get "composition_rule" request |> transform |> repin))in
  bad_rule "helper masquerades as Payload"(put["body";"material_authority";"template";"requirements";"2";"category"](str "payload"));
  bad_rule "payload masquerades as Delivered_helper"(put["body";"material_authority";"template";"requirements";"0";"category"](str "delivered_helper"));
  bad_rule "helper role purpose masquerades as payload"(put["body";"material_authority";"template";"requirements";"2";"roles";"0";"purpose"](str "requested_payload"));
  bad_rule "helper source aliases payload"(put["body";"helper";"source"](str "source_a"));
  bad_rule "helper acquires behavioral slot"(edit["body";"components"](fun raw->arr(Json.array raw@[at["0"]raw |> replace "slot"(str "helper_slot")])));
  bad_rule "P4 profile cannot admit helper"(fun raw->raw |> replace "schema_version"(str "biocompiler.policy_component_assembly_rule.v0.3")
    |> replace "profile"(str "biocompiler.policy_multi_member_component_assembly.v0.1"));
  let semantic code label changed=
    phase("semantic context negative "^label);
    let result=check changed candidate in
    require(at["report";"status"]result=str "not_accepted" && get "artifact" result=Json.Null &&
      List.mem(str code)(at["report";"context";"diagnostics"]result |> Json.array))
      ("Helper negative failed to reach intended guard: "^label^": "^Canonical.encode(get "report" result));
    incr rejected_count in
  let change transform=rewrite_provider "fixture.grounded_helper_capacity" transform request in
  semantic "grounded_helper_complete_material_pin" "stale helper material provider pin"
    (change(put["material";"id"](str "foreign.helper.material")));
  semantic "provider_executor_or_compartment" "foreign helper recipient"
    (change(put["recipient";"identity"](str "foreign-cell")));
  semantic "causal_expression_helper_completion_availability" "completion after availability"
    (change(put["bootstrap";"completion"](obj["earliest",str "2";"latest",str "2"])));
  let early=change(put["bootstrap";"completion"](obj["earliest",str "0";"latest",str "1"]))
    |> rewrite_provider "exclusion.delivery"(fun body->body
      |> replace "expression"(obj["earliest",str "1";"latest",str "1"])
      |> replace "activation"(obj["earliest",str "1";"latest",str "1"]))in
  semantic "causal_expression_helper_completion_availability" "completion before independent expression" early;
  semantic "guaranteed_inclusive_availability:fixture.grounded_helper_capacity" "positive completion at origin zero"
    (put["context";"clock";"origin_seconds"](str "0")request);
  semantic "guaranteed_inclusive_availability:fixture.grounded_helper_capacity" "short helper availability"
    (change(put["availability";"duration_min"](str "5")));
  semantic "guaranteed_inclusive_availability:fixture.grounded_helper_capacity" "late helper availability"
    (change(put["availability"](obj["onset_min",str "3";"onset_max",str "3";"duration_min",str "4";"duration_max",str "4"])));
  semantic "helper_capacity_guarantee_outside_provider" "capacity before helper availability"
    (change(put["capacities";"0";"availability"]full_availability));
  semantic "unused_original_capacity" "unused helper pool"
    (change(edit["capacities"](fun raw->arr(Json.array raw@[at["0"]raw
      |> replace "id"(str "unused.helper.capacity") |> replace "pool_id"(str "unused.helper.pool")]))));
  semantic "grounded_helper_exact_consumer_inventory" "missing distinct helper consumer"
    (put["context";"helpers";"0";"consumer_component_ids"](arr[str "controller_a"])request);
  semantic "grounded_helper_consumer_capacity" "insufficient distinct consumer capacity"
    (put["context";"helpers";"0";"capacity"](Json.int 1)request);
  semantic "grounded_helper_consumer_capacity" "exclusive helper shared by two instances"
    (put["context";"helpers";"0";"sharing"](str "exclusive")request);
  let overdraw=change(put["capacities";"0";"quantity"](Json.int 7))in
  semantic "shared_capacity_sum_exceeded" "sum-minus-one shared record capacity" overdraw;
  reject "overdraw cannot export"(fun()->check ~export:true overdraw candidate);
  let funded=change(put["capacities";"0";"quantity"](Json.int 8))in
  ignore(checked(check funded candidate));
  let missing=edit["context";"providers"](fun raw->arr(List.filter(fun row->at["body";"kind"]row<>str "helper")(Json.array raw)))request in
  let unknown=check missing candidate in
  require(at["report";"prerequisite_status"]unknown=str "unknown" && get "artifact" unknown=Json.Null)
    "Missing helper provider did not remain unknown and nonexportable";
  incr rejected_count;reject "missing helper cannot export"(fun()->check ~export:true missing candidate);
  rejected_decode "duplicated helper consumers"(fun()->R.of_json(put["context";"helpers";"0";"consumer_component_ids"]
    (arr[str "controller_a";str "controller_a"])request));
  semantic "grounded_helper_source_independent_initialization" "consumer-triggered helper initialization"
    (put["context";"helpers";"0";"initialization"](str "after_trigger")request);
  reject "helper bootstrap circular prerequisite"(fun()->check(change(put["bootstrap";"prerequisites"](arr[helper_reference])))candidate);
  semantic "prerequisite_cycle" "helper environment self-support cycle" (change(replace "environment" helper_reference));
  let absent=edit["implementation_request";"document";"implementations";"implementations";"0";"dependencies"]
    (fun _->arr[transport_reference])request in
  let entry=at["implementation_request";"document";"implementations";"implementations";"0"]absent in
  let absent=absent |> put["implementation_request";"catalog_bindings";"0";"entry_digest"](str(Canonical.fingerprint entry))
    |> put["catalog_binding";"entry_digest"](str(Canonical.fingerprint entry))in
  reject "helper absent selected catalog dependency"(fun()->compile absent limits);
  reject "helper cannot bypass exhaustion"(fun()->call Service.handle Protocol.Verify "export-policy-component-material"
    (invocation request candidate(replace "max_step_work"(Json.int 1)limits)));
  reject "forged helper replay allocation"(fun()->call Service.handle Protocol.Verify "replay-policy-component-material"
    (add "report"(put["report";"prerequisites";"helper_allocations"](arr [])produced)(invocation request candidate limits)));
  reject "earlier outer profile cannot admit helper"(fun()->check(request
    |> replace "schema_version"(str "biocompiler.policy_component_material_request.v0.5")
    |> replace "profile"(str "biocompiler.policy_multi_member_prerequisite_mrna.v0.1"))candidate)
let ()=
  let channel=open_in_bin Sys.argv.(1)in
  let raw=really_input_string channel(in_channel_length channel)in close_in channel;
  let fixture=Json.parse_artifact ~max_bytes:4_000_000 ~max_nodes:400000 raw in
  let request,candidate,limits,produced=positive fixture false in
  negatives request candidate limits produced;
  let request_b,candidate_b,_,_=positive fixture true in
  require(Json.equal(get "implementation_request" request)(get "implementation_request" request_b) &&
    Json.equal(get "implementation" candidate)(get "implementation" candidate_b) &&
    Json.equal(at["construction";"inventory";"molecules";"0"]candidate)(at["construction";"inventory";"molecules";"0"]candidate_b) &&
    Json.equal(at["construction";"inventory";"molecules";"1"]candidate)(at["construction";"inventory";"molecules";"1"]candidate_b) &&
    at["construction";"inventory";"molecules";"2";"sequence"]candidate<>at["construction";"inventory";"molecules";"2";"sequence"]candidate_b)
    "Helper-only original edit changed therapeutic source, graph or payloads, or did not change helper RNA";
  reject "stale candidate after helper material edit"(fun()->call Service.handle Protocol.Verify "export-policy-component-material"(invocation request_b candidate limits));
  require(!rejected_count=36)"Incomplete grounded-helper negative control census";
  Printf.printf "grounded_helper_material: independent three-RNA originals, unchanged25-history therapeutic domain; %d negative controls\n" !rejected_count
