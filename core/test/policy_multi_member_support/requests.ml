open Bioc_wire
open Literals
let link_rows fixture=
  at["request";"composition_rule";"body";"links"]fixture |> Json.array
  |> List.filter(fun row->String.starts_with ~prefix:"stage1."(text "id" row))
  |> List.map(fun row->List.fold_left(fun row field->edit[field;"slot"](function
    |Json.String "decision"->str "controller_a"|Json.String "driver"->str "stage_b"|value->value)row)row["producer";"consumer"])
let global_nodes fixture original=List.concat_map(fun slot->List.map(fun node->nr slot(text "id" node))(node_models fixture original slot))slots
let global_exports fixture original=List.concat_map(fun slot->List.map(fun row->add "slot"(str slot)row)(items "semantic_exports"(fragment fixture original slot)))slots
let global_wires fixture=List.concat_map(fun slot->List.mapi(fun index _->obj["kind",str "local";"slot",str slot;"index",Json.int index])(local_wires fixture slot))slots @
  List.map(fun row->obj["kind",str "link";"id",get "id" row])(link_rows fixture)
let global_inputs=[obj["slot",str "controller_a";"external_slot",str "condition";"id",str "condition"];
  obj["slot",str "controller_a";"external_slot",str "first_feedback";"id",str "first_feedback"];
  obj["slot",str "stage_b";"external_slot",str "second_feedback";"id",str "second_feedback"]]
let global_groups fixture=List.map(fun row->obj["slot",str "controller_a";"group",get "id" row])(items "atomic_groups"(old_fragment fixture 0))
let selections components=List.map2(fun slot value->obj["slot",str slot;"component",get "identity" value])slots components
let member_bindings=List.map(fun slot->obj["slot",str slot;"source",str(source_id slot);"member",str(member_id slot)])slots
let material_authority fixture alternate=
  let old=at["request";"composition_rule";"body";"material_authority"]fixture in
  let template=get "template" old in
  let outputs=List.map(fun slot->List.hd(items "output_members" template)
    |> replace "id"(str(member_id slot)) |> replace "space_id"(str(member_id slot^".frame"))
    |> edit["value"](fun value->value |> replace "kind"(str "root") |> replace "id"(str(source_id slot))))slots in
  let requirements=List.map(fun slot->List.hd(items "requirements" template)
    |> replace "id"(str(member_id slot)) |> replace "member_id"(str(member_id slot))
    |> edit["roles"](fun raw->arr(List.map(fun role->replace "id"(str(member_id slot^".role"))role)(Json.array raw))))slots in
  let template=template |> replace "id"(str "multi_member.direct_roots") |> replace "steps"(arr [])
    |> replace "sources"(arr(List.map(fun slot->root fixture slot alternate |> replace "id"(str(source_id slot)))slots))
    |> replace "output_members"(arr outputs) |> replace "requirements"(arr requirements)
    |> replace "payload_structures"(arr(List.map(fun slot->List.hd(items "payload_structures" template)
        |> replace "member_id"(str(member_id slot)))slots))in
  old |> replace "template" template |> replace "member_order"(arr(List.map(fun slot->str(member_id slot))slots))
  |> replace "members"(arr(List.map(fun slot->List.hd(items "members" old) |> replace "id"(str(member_id slot))
    |> replace "product"(product fixture slot alternate)
    |> replace "chemistry"(get "chemistry"(molecule_literal fixture slot alternate ~output:true)))slots))
let transport_provider fixture=
  let context=at["request";"context"]fixture in
  let environment=List.find(fun row->at["body";"kind"]row=str "environment")(items "providers" context)in
  let body=obj["kind",str "transport";"definition",transport_reference;"recipient",get "recipient" context;
    "availability",at["body";"availability"]environment;"capacities",arr [];
    "environment",at["body";"definition"]environment;"original_clock",at["clock";"original_clock"]context;
    "transport_profile",str "biocompiler.policy_complete_signal_identity_transport.v0.1";
    "phase_profile",str "biocompiler.policy_staged_primitive_execution.v0.1";
    "delay_ticks",Json.int 0;"loss",str "none";"duplication",str "none";"ordering",str "preserved";
    "records",str "complete_signal_identity"]in
  named "multi_member.transport.provider" body |> add "schema_version"(str "biocompiler.policy_material_provider.v0.2")
let transport_row fixture link=
  obj["definition",transport_reference;"provider",get "identity"(transport_provider fixture);
    "producer_member",str(member_id(text "slot"(get "producer" link)));
    "consumer_member",str(member_id(text "slot"(get "consumer" link)))]
let rule_literal fixture original alternate components=
  let old=at["request";"composition_rule";"body"]fixture in
  let body=old |> replace "components"(arr(selections components)) |> replace "links"(arr(link_rows fixture))
    |> replace "node_order"(arr(global_nodes fixture original)) |> replace "wire_order"(arr(global_wires fixture))
    |> replace "input_order"(arr global_inputs) |> replace "group_order"(arr(global_groups fixture))
    |> replace "export_order"(arr(global_exports fixture original))
    |> replace "root_bindings"(arr(List.map(fun slot->obj["slot",str slot;"source",str(source_id slot)])slots))
    |> remove "join" |> add "joins"(arr []) |> add "member_bindings"(arr member_bindings)
    |> replace "link_carriers"(arr(List.map(fun link->obj["link",get "id" link;"producer_site",Json.int 0;
      "consumer_site",Json.int 0;"transport",transport_row fixture link])(link_rows fixture)))
    |> replace "material_authority"(material_authority fixture alternate)in
  named "multi_member.supplied_assembly" body |> add "schema_version"(str "biocompiler.policy_component_assembly_rule.v0.3")
    |> add "profile"(str assembly_profile)
let endpoint_at fixture original boundary=
  let slot=text "slot" boundary in
  let row=List.find(fun row->get "id" row=get "boundary" boundary)(items "boundary_ports"(fragment fixture original slot))in
  add "slot"(str slot)(get "endpoint" row)
let union_literal fixture original rule=
  let nodes=List.concat_map(fun slot->List.map(fun node->obj["slot",str slot;"node",get "id" node;"model",get "model" node])
    (node_models fixture original slot))slots in
  let wires=List.concat_map(fun slot->List.map(fun row->obj["producer",add "slot"(str slot)(get "producer" row);
    "consumer",add "slot"(str slot)(get "consumer" row)])(local_wires fixture slot))slots @
    List.map(fun row->obj["producer",endpoint_at fixture original(get "producer" row);
      "consumer",endpoint_at fixture original(get "consumer" row)])(link_rows fixture)in
  let inputs=[obj["id",str "condition";"kind",str "evidence";"consumer",er "controller_a" "evidence" "samples"];
    obj["id",str "first_feedback";"kind",str "feedback";"consumer",er "controller_a" "first" "feedback"];
    obj["id",str "second_feedback";"kind",str "feedback";"consumer",er "stage_b" "second" "feedback"]]in
  let groups=List.map(fun row->obj["slot",str "controller_a";"id",get "id" row;
    "arbiter",nr "controller_a"(text "arbiter" row);
    "commits",arr(List.map(fun id->nr "controller_a"(Json.string id))(items "commits" row))])(items "atomic_groups"(old_fragment fixture 0))in
  obj["schema_version",str "biocompiler.policy_instance_ordered_union.v0.1";
    "primitive_profile",str "biocompiler.policy_staged_primitives.v0.1";
    "observable_profile",str "biocompiler.policy_staged_observables.v0.1";
    "phase_profile",str "biocompiler.policy_staged_primitive_execution.v0.1";
    "transport_profile",str "biocompiler.policy_identity_transport.v0.1";
    "slot_layout",at["body";"slot_layout"]rule;"nodes",arr nodes;"wires",arr wires;"inputs",arr inputs;
    "atomic_groups",arr groups;"semantic_exports",arr(global_exports fixture original);"links",arr(link_rows fixture)]
let resource_bindings fixture=
  let old=at["request";"resource_bindings"]fixture |> Json.array in
  let local=List.concat_map(fun slot->local_requirements fixture slot |> List.filter_map(fun row->
    if get "kind" row=str "input" then None else
    let owner=get "owner" row in
    let wanted=if text "kind" owner="external_slot" then obj["kind",str "input";"id",get "id" owner]
      else obj["kind",str "node";"slot",str(if List.mem(text "id" owner)first_nodes || List.mem(text "id" owner)second_nodes then "driver" else "decision");"node",get "id" owner]in
    let binding=List.find(fun binding->Json.equal(get "owner" binding)wanted && get "unit" binding=get "unit" row && get "scope" binding=get "scope" row)old in
    Some(if text "kind" owner="node" then put["owner";"slot"](str slot)binding else binding)))slots in
  local @ List.filter(fun row->at["owner";"kind"]row=str "layout")old
let request_literal fixture alternate=
  let original=source_literal fixture alternate in
  let components=List.map(fun slot->component fixture original slot alternate)slots in
  let rule=rule_literal fixture original alternate components in
  let union=union_literal fixture original rule in
  let old=at["request";"context"]fixture in
  let layout=get "record_layout" old |> replace "rule"(get "identity" rule)
    |> replace "union_digest"(str(Canonical.fingerprint union))in
  let providers=items "providers" old |> List.map(fun provider->provider
    |> edit["body";"capacities"](fun raw->arr(List.map(fun capacity->replace "record_layout_digest"(str(Canonical.fingerprint layout))capacity)(Json.array raw))) |> repin)in
  let placements=List.map(fun slot->get "placement" old |> replace "id"(str(member_id slot^".placement"))
    |> replace "member_id"(str(member_id slot)) |> replace "template_id"(str "multi_member.direct_roots"))slots in
  let context=old |> replace "schema_version"(str "biocompiler.policy_component_context.v0.2")
    |> replace "profile"(str material_profile) |> remove "placement" |> add "placements"(arr placements)
    |> replace "record_layout" layout |> replace "providers"(arr(providers @ [transport_provider fixture]))
    |> edit["delivery_group"](fun group->group |> replace "exact_count"(Json.int 2) |> replace "max_count"(Json.int 2)
      |> replace "max_total_bases"(Json.int 34))in
  let bridge=at["catalog_bindings";"0"]original in
  let outer=at["request";"catalog_binding"]fixture |> replace "entry_id"(get "entry_id" bridge)
    |> replace "entry_digest"(get "entry_digest" bridge) |> replace "components"(arr(selections components)) |> replace "rule"(get "identity" rule)in
  let request=get "request" fixture |> replace "schema_version"(str "biocompiler.policy_component_material_request.v0.5")
    |> replace "profile"(str material_profile) |> replace "implementation_request" original
    |> edit["component_library";"components"](fun _->arr components) |> replace "composition_rule" rule
    |> replace "catalog_binding" outer |> replace "context" context |> replace "resource_bindings"(arr(resource_bindings fixture))in
  request,union
let expected_molecules fixture alternate=arr(List.map(fun slot->molecule_literal fixture slot alternate ~output:true)slots)
let expected_projections fixture alternate request=
  let original=get "implementation_request" request in
  let site slot=
    let raw=at["body";"carriers";"0";"sites";"0"](component fixture original slot alternate)in
    obj["slot",str slot;"root",str(root_id slot);"source",str(source_id slot);"feature",str "cds";
      "local_path",get "path" raw;"member",str(member_id slot);"path",reframe(member_id slot^".frame")(get "path" raw);"final_feature",str "cds"]in
  let carriers=List.concat_map(fun slot->targets(fragment fixture original slot) |> List.map(fun target->
    obj["slot",str slot;"target",target;"sites",arr[site slot]]))slots in
  let links=List.map(fun link->
    let endpoint boundary=endpoint_at fixture original boundary in
    obj["link",get "id" link;"transport",transport_row fixture link;
      "producer_endpoint",endpoint(get "producer" link);"consumer_endpoint",endpoint(get "consumer" link);
      "producer",site(text "slot"(get "producer" link));"consumer",site(text "slot"(get "consumer" link))])(link_rows fixture)in
  arr carriers,arr links
let provider request id=List.find(fun row->at["body";"definition";"id"]row=str id)(at["context";"providers"]request |> Json.array)
let provider_ref request id=at["body";"definition"](provider request id)
let expected_pending request=
  let entry=at["implementation_request";"document";"implementations";"implementations";"0"]request in
  arr[obj["entry_id",str "multi_member.staged.primitives";"entry_digest",str(Canonical.fingerprint entry);
    "dependency_index",Json.int 0;"definition",transport_reference]]
let expected_graph request=
  let reference=provider_ref request in
  let source path id=obj["origin",obj["kind",str "source";"path",str path];"definition",reference id]in
  let roots=List.map(fun(path,id)->source path id)[
    "/deployment/bindings/0/chassis/operational_model","exclusion.chassis";
    "/deployment/bindings/0/chassis/capabilities/0","staged.interface";
    "/deployment/bindings/0/chassis/interfaces/0","staged.interface";
    "/deployment/bindings/0/chassis/environment/0","exclusion.environment";
    "/deployment/environment/0","exclusion.environment";
    "/program/declarations/0/requires/0","staged.interface";
    "/deployment/delivery/arrival","exclusion.delivery";
    "/deployment/delivery/expression","exclusion.delivery";
    "/deployment/delivery/activation","exclusion.delivery";
    "/deployment/delivery/contract","exclusion.delivery"]in
  let pending=List.hd(Json.array(expected_pending request))in
  let catalog=obj["origin",obj["kind",str "catalog_dependency";"entry_id",get "entry_id" pending;
    "entry_digest",get "entry_digest" pending;"dependency_index",Json.int 0];"definition",transport_reference]in
  let nodes=List.map(fun id->obj["definition",reference id;"provider",get "identity"(provider request id)])
    ["exclusion.chassis";"staged.interface";"exclusion.environment";"exclusion.delivery";"fixture.inter_member_transport"]in
  let edge source relation target=obj["source",reference source;"relation",str relation;"index",Json.int 0;"target",reference target]in
  obj["schema_version",str "biocompiler.policy_provider_dependency_graph.v0.2";
    "pending_dependencies",expected_pending request;"roots",arr(roots@[catalog]);"nodes",arr nodes;
    "edges",arr[edge "exclusion.chassis" "chassis_capability" "staged.interface";
      edge "staged.interface" "interface_environment" "exclusion.environment";
      edge "exclusion.chassis" "chassis_interface" "staged.interface";
      edge "exclusion.chassis" "chassis_environment" "exclusion.environment";
      edge "fixture.inter_member_transport" "transport_environment" "exclusion.environment"];
    "issues",arr []]
let expected_resource_allocations request=
  (* Literal demand census, independently derived from 2 evidence records, a
     5-state machine, two4-record attempts,4 feedback rows per input and the
     original 64-event queue; never read quantities from supplied capacities. *)
  let quantities=[1;4;2;1;3;1;1;4;4;4;4;4;4;4;1;1;64]in
  arr(List.map2(fun binding quantity->obj[
    "demand",obj["owner",get "owner" binding;"unit",get "unit" binding;"scope",get "scope" binding;"quantity",Json.int quantity];
    "provider",provider_ref request "exclusion.chassis";"capacity",get "capacity" binding;
    "pool",str("staged.pool."^text "capacity" binding);"reserved",Json.int quantity])
    (items "resource_bindings" request)quantities)
let expected_input_allocations request=
  let available=obj["onset_min",str "0";"onset_max",str "0";"duration_min",str "5";"duration_max",str "5"]in
  arr(List.map(fun(input,source,kind)->obj["input",str input;"source",str source;
    "provider",provider_ref request "staged.interface";"channel",str input;"kind",str kind;
    "observer",str "executor";"subject",str "encounter/target";"available",available])
    ["condition","condition","observation";"first_feedback","stage_one","feedback";"second_feedback","stage_two","feedback"])
let expected_member_allocations fixture alternate request=
  let delivery=provider request "exclusion.delivery"in
  let witness=obj["definition",provider_ref request "exclusion.delivery";"provider",get "identity" delivery;"body",get "body" delivery]in
  arr(List.map2(fun slot placement->obj["slot",str slot;"source",str(source_id slot);"member",str(member_id slot);
    "placement",placement;"molecule_fingerprint",str(Canonical.fingerprint(molecule_literal fixture slot alternate ~output:true));
    "delivery",witness])slots(at["context";"placements"]request |> Json.array))
let expected_transport_allocations fixture request=
  let transport=provider request "fixture.inter_member_transport"in
  arr(List.map(fun link->obj["link",get "id" link;
    "producer_member",str(member_id(text "slot"(get "producer" link)));
    "consumer_member",str(member_id(text "slot"(get "consumer" link)));
    "provider",get "identity" transport;"definition",transport_reference;"signal_type",get "signal_type" link;
    "scope",get "scope" link;"transport_profile",str "biocompiler.policy_complete_signal_identity_transport.v0.1";
    "phase_profile",str "biocompiler.policy_staged_primitive_execution.v0.1";
    "available",at["body";"availability"]transport])(link_rows fixture))
let expected_closure fixture alternate request=
  let components=at["component_library";"components"]request |> Json.array in
  let selections=selections components in
  obj["schema_version",str "biocompiler.policy_provider_prerequisite_closure.v0.2";"profile",str material_profile;
    "status",str "pass";"complete",Json.Bool true;"original_request_fingerprint",str(Canonical.fingerprint request);
    "source_catalog",at["implementation_request";"document";"implementations"]request;
    "pending_dependencies",expected_pending request;"instances",arr selections;
    "local_requirements",arr(List.map2(fun selection component->add "requirements"(at["body";"provider_requirements"]component)selection)selections components);
    "providers",arr(List.map(fun id->let row=provider request id in obj["definition",at["body";"definition"]row;
      "identity",get "identity" row;"body_fingerprint",str(Canonical.fingerprint(get "body" row))])
      ["exclusion.chassis";"exclusion.environment";"staged.interface";"exclusion.delivery";"fixture.inter_member_transport"]);
    "graph",expected_graph request;"operating_domain_fingerprint",str(Canonical.fingerprint(at["implementation_request";"operating_domain"]request));
    "clock",at["context";"clock"]request;"recipient",at["context";"recipient"]request;
    "input_allocations",expected_input_allocations request;"resource_allocations",expected_resource_allocations request;
    "member_allocations",expected_member_allocations fixture alternate request;
    "transport_allocations",expected_transport_allocations fixture request;"diagnostics",arr [];"empirical",str "unassessed"]
let expected_obligations=List.map str [
  "arbitration_fairness_and_conflict_resolution";"chassis_capability_and_delivery_suitability";
  "effect_authorization_feedback_and_cancellation";"implementation_applicability:multi_member.staged.primitives";
  "implementation_catalog_applicability";"machine_reachability_termination_and_progress";
  "policy_execution_and_lowering";"realizability_and_target_suitability";"requested_assurance_not_established";
  "requirement_satisfaction:first_initiation";"requirement_satisfaction:second_initiation";"safety_and_progress_satisfaction";
  "semantic_definition:exclusion.chassis";"semantic_definition:exclusion.delivery";"semantic_definition:exclusion.environment";
  "semantic_definition:fixture.inter_member_transport";"semantic_definition:fixture.realization.primitives";
  "semantic_definition:staged.encounter";"semantic_definition:staged.interface";"semantic_definition:staged.lifecycle";
  "semantic_definition:staged.observation";"semantic_definition:staged.operation";"temporal_and_uncertainty_semantics"]
let case fixture id alternate=
  let request,union=request_literal fixture alternate in
  let carriers,links=expected_projections fixture alternate request in
  obj["id",str id;"request",request;"limits",get "limits" fixture;
    "expected",obj["sequences",arr(List.map(fun slot->str(sequence slot alternate))slots);
      "molecules",expected_molecules fixture alternate;"ordered_union",union;
      "carrier_projections",carriers;"link_projections",links;"histories",Json.int 25;"transitions",Json.int 86;
      "prefixes_started",Json.int 87;"obligations",arr expected_obligations;
      "prerequisite_closure",expected_closure fixture alternate request]]
