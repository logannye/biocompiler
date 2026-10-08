open Bioc_wire
open Literals
let retained row=get "unit" row=str "retained_correlation_records"
let helper_provider fixture alternate request layout=
  let capacity=obj["id",str "helper.retained_records";"pool_id",str "helper.shared.records";
    "unit",str "retained_correlation_records";"scope",str "per_executor";"slots",arr [];
    "quantity",Json.int 8;"availability",helper_availability;"record_layout_digest",str(Canonical.fingerprint layout)]in
  let body=obj["kind",str "helper";"definition",helper_reference;
    "recipient",at["context";"recipient"]request;"availability",helper_availability;"capacities",arr[capacity];
    "material",get "identity"(helper_material fixture alternate);
    "environment",Previous.provider_ref request "exclusion.environment";
    "delivery",Previous.provider_ref request "exclusion.delivery";
    "capacity_profile",str "biocompiler.policy_supplied_grounded_helper_capacity.v0.1";
    "bootstrap",obj["profile",str "biocompiler.policy_source_independent_expression_completion.v0.1";
      "completion",obj["earliest",str "1";"latest",str "1"];"prerequisites",arr []]]in
  named "grounded_helper.provider" body |> add "schema_version"(str "biocompiler.policy_material_provider.v0.3")
let request_literal fixture alternate=
  let shifted=shifted_fixture fixture in
  let previous,union=Previous.request_literal shifted false in
  let original=source_literal fixture in
  let material=helper_material fixture alternate in
  let rule=get "composition_rule" previous |> replace "schema_version"(str "biocompiler.policy_component_assembly_rule.v0.4")
    |> replace "profile"(str assembly_profile)
    |> edit["body"](fun body->body |> add "helper"(obj["source",str helper_source;"member",str helper_member;"material",material])
        |> replace "material_authority"(material_authority fixture alternate(get "material_authority" body))) |> repin in
  let layout=at["context";"record_layout"]previous |> replace "rule"(get "identity" rule)in
  let providers=at["context";"providers"]previous |> Json.array |> List.map(fun provider->
    provider |> edit["body";"capacities"](fun raw->arr(List.filter_map(fun capacity->
      if retained capacity then None else Some(replace "record_layout_digest"(str(Canonical.fingerprint layout))capacity))(Json.array raw))) |> repin)in
  let helper_provider=helper_provider fixture alternate previous layout in
  let helper_placement=at["context";"placements";"0"]previous |> replace "id"(str "helper_rna.placement")
    |> replace "member_id"(str helper_member)in
  let context=get "context" previous |> replace "schema_version"(str "biocompiler.policy_component_context.v0.3")
    |> replace "profile"(str material_profile) |> replace "record_layout" layout
    |> replace "providers"(arr(providers@[helper_provider])) |> replace "helpers"(arr[helper_declaration])
    |> edit["placements"](fun raw->arr(Json.array raw@[helper_placement]))
    |> edit["delivery_group"](fun row->row |> replace "exact_count"(Json.int 3) |> replace "max_count"(Json.int 3)
        |> replace "max_total_bases"(Json.int 51))in
  let entry=at["document";"implementations";"implementations";"0"]original in
  let bridge=get "catalog_binding" previous |> replace "rule"(get "identity" rule)
    |> replace "entry_digest"(str(Canonical.fingerprint entry))in
  let bindings=items "resource_bindings" previous |> List.map(fun row->if retained row then row
    |> replace "provider" helper_reference |> replace "capacity"(str "helper.retained_records") else row)in
  previous |> replace "schema_version"(str "biocompiler.policy_component_material_request.v0.6")
    |> replace "profile"(str material_profile) |> replace "implementation_request" original
    |> replace "composition_rule" rule |> replace "catalog_binding" bridge |> replace "context" context
    |> replace "resource_bindings"(arr bindings),union
let expected_molecules fixture alternate=arr(List.map(fun slot->molecule_literal fixture slot false ~output:true)slots @
  [helper_molecule fixture alternate ~output:true])
let expected_projections fixture _alternate request=Previous.expected_projections(shifted_fixture fixture)false request
let expected_helper_projections fixture alternate=
  let material=helper_material fixture alternate in
  arr[obj["material",material;"source",str helper_source;"member",str helper_member;"product",helper_product fixture alternate;
    "root_fingerprint",str(Canonical.fingerprint(at["body";"root"]material));
    "molecule_fingerprint",str(Canonical.fingerprint(helper_molecule fixture alternate ~output:true))]]
let provider=Previous.provider
let provider_ref=Previous.provider_ref
let expected_pending request=
  let first=List.hd(Json.array(Previous.expected_pending request))in
  arr[first;first |> replace "dependency_index"(Json.int 1) |> replace "definition" helper_reference]
let expected_graph request=
  let previous=Previous.expected_graph request in
  let pending=List.nth(Json.array(expected_pending request))1 in
  let catalog=obj["origin",obj["kind",str "catalog_dependency";"entry_id",get "entry_id" pending;
    "entry_digest",get "entry_digest" pending;"dependency_index",Json.int 1];"definition",helper_reference]in
  let edge relation id=obj["source",helper_reference;"relation",str relation;"index",Json.int 0;
    "target",provider_ref request id]in
  previous |> replace "schema_version"(str "biocompiler.policy_provider_dependency_graph.v0.3")
    |> replace "pending_dependencies"(expected_pending request)
    |> edit["roots"](fun raw->arr(Json.array raw@[catalog]))
    |> edit["nodes"](fun raw->arr(Json.array raw@[obj["definition",helper_reference;
        "provider",get "identity"(provider request "fixture.grounded_helper_capacity")]]))
    |> edit["edges"](fun raw->arr(Json.array raw@[edge "helper_environment" "exclusion.environment";
        edge "helper_delivery" "exclusion.delivery"]))
let expected_resource_allocations request=
  (* Unchanged literal demand census. Exactly the two independently owned
     Attempt-bank retained-record demands reserve four units each in one pool. *)
  let quantities=[1;4;2;1;3;1;1;4;4;4;4;4;4;4;1;1;64]in
  arr(List.map2(fun binding quantity->let is_helper=retained binding in
    obj["demand",obj["owner",get "owner" binding;"unit",get "unit" binding;"scope",get "scope" binding;"quantity",Json.int quantity];
      "provider",(if is_helper then helper_reference else provider_ref request "exclusion.chassis");
      "capacity",(if is_helper then str "helper.retained_records" else get "capacity" binding);
      "pool",str(if is_helper then "helper.shared.records"else "staged.pool."^text "capacity" binding);
      "reserved",Json.int quantity])(items "resource_bindings" request)quantities)
let expected_helper_allocation fixture alternate request=
  let provider=provider request "fixture.grounded_helper_capacity" and delivery=provider request "exclusion.delivery"in
  let allocations=Json.array(expected_resource_allocations request)in
  obj["helper",helper_declaration;"material",get "identity"(helper_material fixture alternate);"capability",helper_reference;
    "source",str helper_source;"member",str helper_member;"placement",at["context";"placements";"2"]request;
    "molecule_fingerprint",str(Canonical.fingerprint(helper_molecule fixture alternate ~output:true));
    "provider",get "identity" provider;"provider_body",get "body" provider;"bootstrap",at["body";"bootstrap"]provider;
    "delivery",obj["definition",provider_ref request "exclusion.delivery";"provider",get "identity" delivery;"body",get "body" delivery];
    "consumers",arr(List.map str slots);"resource_allocations",arr[List.nth allocations 8;List.nth allocations 12]]
let expected_closure fixture alternate request=
  let only_payloads=request |> edit["context";"placements"](fun raw->arr[at["0"]raw;at["1"]raw])in
  let previous=Previous.expected_closure(shifted_fixture fixture)false only_payloads in
  previous |> replace "schema_version"(str "biocompiler.policy_provider_prerequisite_closure.v0.3")
    |> replace "profile"(str material_profile) |> replace "original_request_fingerprint"(str(Canonical.fingerprint request))
    |> replace "pending_dependencies"(expected_pending request) |> replace "graph"(expected_graph request)
    |> edit["providers"](fun raw->let helper=provider request "fixture.grounded_helper_capacity"in
        arr(Json.array raw@[obj["definition",helper_reference;"identity",get "identity" helper;
          "body_fingerprint",str(Canonical.fingerprint(get "body" helper))]]))
    |> edit["input_allocations"](fun raw->arr(List.map(replace "available" full_availability)(Json.array raw)))
    |> replace "resource_allocations"(expected_resource_allocations request)
    |> add "helper_allocations"(arr[expected_helper_allocation fixture alternate request])
let expected_obligations=List.sort compare(str "semantic_definition:fixture.grounded_helper_capacity"::Previous.expected_obligations)
let case fixture id alternate=
  let request,union=request_literal fixture alternate in
  let carriers,links=expected_projections fixture alternate request in
  obj["id",str id;"request",request;"limits",invocation_limits fixture;
    "expected",obj["sequences",arr(List.map(fun slot->str(sequence slot false))slots@[str(helper_sequence alternate)]);
      "molecules",expected_molecules fixture alternate;"ordered_union",union;
      "carrier_projections",carriers;"link_projections",links;"helper_projections",expected_helper_projections fixture alternate;
      "histories",Json.int 25;"transitions",Json.int 86;"prefixes_started",Json.int 87;
      "obligations",arr expected_obligations;"prerequisite_closure",expected_closure fixture alternate request]]
