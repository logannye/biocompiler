open Bioc_wire
open Bioc_policy_multi_member_test_support.Literals
open Bioc_policy_multi_member_test_support.Requests
module Service=Bioc_service.Service
module Producer=Bioc_producer_service.Producer_service
module R=Bioc_domain.Policy_component_material_request
module A=Bioc_domain.Policy_component_assembly_rule
let ()=Printexc.register_printer(function Diagnostic.Error d->Some("Diagnostic.Error("^d.code^", "^d.message^")")|_->None)
let phase value=Printf.eprintf "multi-member witness: %s\n%!" value
exception Service_rejection of string
let call handler role operation payload=
  let request:Protocol.request={request_id="multi-member-independent-literal";operation;payload}in
  match handler role request with
  |Protocol.Ok,Some result,[]->result
  |_,_,diagnostics->raise(Service_rejection(operation^": "^String.concat "; "(List.map(fun(d:Diagnostic.t)->d.code^": "^d.message)diagnostics)))
let invocation request candidate limits=obj["request",request;"candidate",candidate;"limits",limits]
let compile request limits=call Producer.handle Protocol.Core "compile-policy-component-material"(obj["request",request;"limits",limits])
let checked result=
  let report=get "report" result in
  require(get "status" report=str "checked_component_material" && get "all_original_obligations_discharged" report=Json.Bool true)
    ("Complete multi-member conjunction rejected: "^Canonical.encode report);
  require(get "implementation" result=str "biocompiler.ocaml.policy_multi_member_prerequisite_material.v0.1" &&
    get "validation_scope" result=str "policy-multi-member-prerequisite-mrna-v0.1" &&
    get "schema_version" report=str "biocompiler.policy_component_material_assessment.v0.3" &&
    get "implementation" report=str "biocompiler.ocaml.policy_component_material_check.v0.5" && get "profile" report=str material_profile &&
    at["assembly";"checker_version"]report=str "biocompiler.ocaml.policy_component_assembly_check.v0.3" &&
    at["context";"schema_version"]report=str "biocompiler.policy_component_context_assessment.v0.2" &&
    at["preservation";"binding";"profile"]report=str "biocompiler.policy_multi_product_staged_source_graph.v0.1" &&
    get "empirical" report=str "unassessed")"Multi-member interpretation used legacy evidence or widened its empirical scope";
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
    "Member geometry, product carriers or explicit noncovalent transport differ from independent original authority"
let check_closure fixture alternate request report=
  let expected=expected_closure fixture alternate request |> add "assembly_fingerprint"(str(Canonical.fingerprint(get "assembly" report)))in
  let closure=get "prerequisites" report in
  require(Json.equal closure expected && Json.equal closure(at["context";"prerequisite_closure"]report) && get "prerequisite_status" report=str "pass")
    ("Two-member closure differs from complete original roots, owners, transport or shared-window allocations: "^Canonical.encode closure);
  let obligations=items "obligations" report in
  require(List.map(get "obligation")obligations=expected_obligations && List.length obligations=23 &&
    List.for_all(fun row->get "status" row=str "discharged")obligations)"Original23 obligations changed or were left unresolved";
  List.iter(fun row->if List.mem(get "stage" row)[str "declared_context";str "conditional_component_context_conjunction"]then
    require(at["evidence";"prerequisites"]row=str(Canonical.fingerprint closure))"Contextual obligation lost private prerequisite closure")obligations
let positive fixture alternate=
  phase(if alternate then "B: independently changed second product"else "A: complete original two-member request");
  let request,union=request_literal fixture alternate and limits=get "limits" fixture in
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
  let fasta=">rna_0001 alphabet=RNA\n"^sequence "controller_a" alternate^"\n>rna_0002 alphabet=RNA\n"^sequence "stage_b" alternate^"\n"in
  require(get "fasta" artifact=str fasta && get "fasta_sha256" artifact=str(Canonical.sha256 fasta))"Ordered two-RNA FASTA differs from original sequences";
  let manifest=get "manifest" artifact in
  require(Json.equal(get "request" manifest)request && Json.equal(get "candidate" manifest)candidate &&
    Json.equal(get "limits" manifest)limits && Json.equal(get "assessment" manifest)report &&
    get "manifest_sha256" artifact=str(Canonical.sha256(Canonical.encode manifest)))"Fresh manifest drops complete original authority or assessment";
  let members=List.mapi(fun index slot->obj["fasta_id",str(Printf.sprintf "rna_%04d"(index+1));"member_id",str(member_id slot);
    "molecule",molecule_literal fixture slot alternate ~output:true;"sequence_sha256",str(Canonical.sha256(sequence slot alternate))])slots in
  require(Json.equal(get "members" manifest)(arr members))"Manifest did not retain exact ordered material members";
  request,candidate,limits,produced
let rewrite_provider id transform request=edit["context";"providers"](fun raw->arr(List.map(fun provider->
  if at["body";"definition";"id"]provider=str id then provider |> edit["body"]transform |> repin else provider)(Json.array raw)))request
(* A coherent ORIGINAL context edit must reach the intended semantic guard,
   rather than reject only an obsolete transport pin. Graph and molecular roots
   are unchanged, so candidate authority changes only in its rule correspondence. *)
let repin_transport request candidate transform=
  let request=rewrite_provider "fixture.inter_member_transport" transform request in
  let transport=provider request "fixture.inter_member_transport"in
  let rule=get "composition_rule" request |> edit["body";"link_carriers"](fun raw->
    arr(List.map(put["transport";"provider"](get "identity" transport))(Json.array raw))) |> repin in
  let layout=at["context";"record_layout"]request |> replace "rule"(get "identity" rule)in
  let request=request |> replace "composition_rule" rule |> put["catalog_binding";"rule"](get "identity" rule)
    |> put["context";"record_layout"]layout
    |> edit["context";"providers"](fun raw->arr(List.map(fun provider->provider
      |> edit["body";"capacities"](fun raw->arr(List.map(fun capacity->
        replace "record_layout_digest"(str(Canonical.fingerprint layout))capacity)(Json.array raw))) |> repin)(Json.array raw)))in
  request,put["assembly_proposal";"rule"](get "identity" rule)candidate
let negatives fixture request candidate limits produced=
  let check ?(export=false) request candidate=call Service.handle Protocol.Verify
    (if export then "export-policy-component-material"else "check-policy-component-material")(invocation request candidate limits)in
  let mutant label transform=reject label(fun()->check request(transform candidate))in
  mutant "duplicate actual ownership"(put["assembly_proposal";"nodes";"1";"actual"](at["assembly_proposal";"nodes";"0";"actual"]candidate));
  mutant "second sequence substituted"(put["construction";"inventory";"molecules";"1";"sequence"](str(sequence "controller_a" false)));
  mutant "one RNA omitted"(edit["construction";"inventory";"molecules"](fun raw->arr[List.hd(Json.array raw)]));
  mutant "member order reversed"(edit["construction";"member_order"](fun raw->arr(List.rev(Json.array raw))));
  mutant "missing atomic machine write"(edit["implementation";"wires"](fun raw->arr(List.filter(fun row->
    at["producer";"port"]row<>str "machine_write" || at["consumer";"port"]row<>str "write0")(Json.array raw))));
  let product_a=actual candidate(nr "controller_a" "product_a") and product_b=actual candidate(nr "stage_b" "product_b")in
  mutant "cross-member product substitution"(edit["implementation";"wires"](fun raw->arr(List.map(fun row->
    if at["producer";"node"]row=product_b then put["producer";"node"]product_a row else row)(Json.array raw))));
  let original=R.of_json request in
  let bad_rule label transform=rejected_decode label(fun()->A.of_json ~components:(R.component_library original)
    (get "composition_rule" request |> transform |> repin))in
  bad_rule "aliased output ownership"(put["body";"member_bindings";"1";"member"](str "payload_a"));
  bad_rule "transport endpoints reversed"(put["body";"link_carriers";"0";"transport";"producer_member"](str "payload_a"));
  bad_rule "implicit empty join path"(edit["body";"link_carriers";"0"](fun row->remove "transport" row |> add "joins"(arr [])));
  bad_rule "legacy profile on direct roots"(fun raw->raw
    |> replace "schema_version"(str "biocompiler.policy_component_assembly_rule.v0.2")
    |> replace "profile"(str "biocompiler.policy_instance_component_assembly.v0.1"));
  let missing=edit["context";"providers"](fun raw->arr(List.filter(fun row->at["body";"kind"]row<>str "transport")(Json.array raw)))request in
  let denied=check missing candidate in
  require(at["report";"prerequisite_status"]denied=str "unknown" && get "artifact" denied=Json.Null)"Missing transport provider did not remain unknown and nonexportable";
  incr rejected_count;reject "missing transport export"(fun()->check ~export:true missing candidate);
  List.iter(fun(field,value)->reject("transport "^field)(fun()->check(rewrite_provider "fixture.inter_member_transport"(replace field value)request)candidate))
    ["delay_ticks",Json.int 1;"loss",str "possible";"duplication",str "possible";"ordering",str "arbitrary";"records",str "values_only"];
  let stale=edit["context";"providers"](fun raw->arr(List.map(fun provider->
    if at["body";"kind"]provider=str "transport" then put["identity";"id"](str "different.transport.identity")provider else provider)(Json.array raw)))request in
  let assert_context code label request candidate=
    phase("semantic context negative "^label);
    let result=check request candidate in
    require(at["report";"status"]result=str "not_accepted" && get "artifact" result=Json.Null &&
      List.mem(str code)(at["report";"context";"diagnostics"]result |> Json.array))
      ("Context negative failed to reach its intended guard: "^label^": "^Canonical.encode(get "report" result));
    incr rejected_count in
  assert_context "transport_complete_provider_pin" "transport stale pin" stale candidate;
  let changed,changed_candidate=repin_transport request candidate(put["recipient";"identity"](str "foreign-cell"))in
  assert_context "provider_executor_or_compartment" "coherently pinned foreign transport recipient" changed changed_candidate;
  let changed,changed_candidate=repin_transport request candidate(put["availability";"duration_min"](str "4"))in
  assert_context "guaranteed_inclusive_availability:fixture.inter_member_transport" "coherently pinned short transport window" changed changed_candidate;
  reject "second placement compartment"(fun()->check(put["context";"placements";"1";"compartment"](str "nucleus")request)candidate);
  let deficient=rewrite_provider "exclusion.chassis"(edit["capacities"](fun raw->arr(List.map(fun row->
    if get "unit" row=str "machine_state_bits" then replace "quantity"(Json.int 2)row else row)(Json.array raw))))request in
  reject "insufficient shared machine capacity"(fun()->check deficient candidate);
  reject "capacity cannot export"(fun()->check ~export:true deficient candidate);
  reject "exhausted preservation cannot export"(fun()->call Service.handle Protocol.Verify "export-policy-component-material"
    (invocation request candidate(replace "max_step_work"(Json.int 1)limits)));
  reject "forged transport replay evidence"(fun()->call Service.handle Protocol.Verify "replay-policy-component-material"
    (add "report"(put["report";"prerequisites";"transport_allocations"](arr [])produced)(invocation request candidate limits)));
  let completion=edit["implementation_request";"document";"program";"declarations"](fun raw->arr(List.map(fun declaration->
    if get "id" declaration=str "second_initiation" then put["response";"value"](str "completed")declaration else declaration)(Json.array raw)))request in
  reject "external completion not guaranteed"(fun()->compile completion limits);
  let candidate_ids=List.map(text "actual")(proposal candidate)in
  let rec rename=function
    |Json.String value when List.mem value candidate_ids->str("renamed/"^value)
    |Json.Array values->arr(List.map rename values)|Json.Object fields->obj(List.map(fun(key,value)->key,rename value)fields)|value->value in
  let renamed=rename candidate in
  phase "harmless complete actual-node renaming";
  let result=check request renamed in
  let report=checked result in
  let _,union=request_literal fixture false in
  check_graph union renamed;check_projections fixture false request renamed report
let ()=
  let channel=open_in_bin Sys.argv.(1)in
  let raw=really_input_string channel(in_channel_length channel)in close_in channel;
  let fixture=Json.parse_artifact ~max_bytes:4_000_000 ~max_nodes:400000 raw in
  let request,candidate,limits,produced=positive fixture false in
  negatives fixture request candidate limits produced;
  let request_b,candidate_b,_,_=positive fixture true in
  require(at["implementation_request";"document"]request<>at["implementation_request";"document"]request_b &&
    at["construction";"inventory";"molecules";"1";"sequence"]candidate<>at["construction";"inventory";"molecules";"1";"sequence"]candidate_b)
    "Independent original product edit did not change its own RNA member";
  reject "stale candidate after source-product edit"(fun()->call Service.handle Protocol.Verify "export-policy-component-material"(invocation request_b candidate limits));
  Printf.printf "multi_member_material: independently authored A/B two-product/two-RNA25-history conjunction; %d negative controls\n" !rejected_count
