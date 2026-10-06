open Bioc_wire
module I = Policy_implementation
module M = Molecular_record
module Pin = Pinned_identity
module Names = Set.Make(String)
let schema_version="biocompiler.policy_material_contract.v0.1"
let profile="biocompiler.policy_truth_mrna_material.v0.1"
let phase_profile="biocompiler.policy_primitive_execution.v0.1"
let kernel_schema="biocompiler.policy_material_kernel.v0.1"
let proposal_schema="biocompiler.policy_material_binding.v0.1"
let str value=Json.String value
let obj values=Json.Object values
let arr values=Json.Array values
let get name value=Json.field name(Json.object_fields value)
let exact names value=Json.exact_fields names(Json.object_fields value)
let require condition message=Diagnostic.require condition "policy_material_contract" message
let name value=let value=Json.name value in require(String.length value<=256)"Material identifier exceeds 256 bytes.";value
let sha value=let value=Json.string value in
  require(String.length value=64 && String.for_all(function '0'..'9'|'a'..'f'->true|_->false)value)
    "A full lowercase SHA-256 identity is required.";value
let integer ?(minimum=0) maximum value=let value=M.index ~maximum value in
  require(value>=minimum)"Material integer is below its declared bound.";value
let rows maximum value=M.array ~maximum value
let unique label values=ignore(List.fold_left(fun seen value->
  require(not(Names.mem value seen))("Duplicate "^label^" identity.");Names.add value seen)Names.empty values)
let equal_json a b=Canonical.encode a=Canonical.encode b
type provider_ref={definition_id:string;definition_version:string;definition_digest:string}
let provider_ref_to_json (value:provider_ref)=obj["$type",str "DefinitionRef";"id",str value.definition_id;
  "version",str value.definition_version;"digest",str value.definition_digest]
let provider_ref_of_json value=
  M.check_resources value;
  exact["$type";"id";"version";"digest"]value;
  require(get "$type" value=str "DefinitionRef")"Provider requires the complete original DefinitionRef.";
  {definition_id=name(get "id" value);definition_version=name(get "version" value);definition_digest=sha(get "digest" value)}
type resource_unit=Truth_cells|Evidence_records|Edge_history_cells|Generation_counters
  |Active_attempt_records|Retained_correlation_records|Timer_cells|Control_event_records|Input_rows_per_tick
type resource_scope=Per_executor|Per_encounter_slot
type resource_owner=Node of string|Input of string|Layout
type resource_demand={demand_id:string;unit:resource_unit;scope:resource_scope;quantity:int;owner:resource_owner}
type allocation={demand_id:string;provider:provider_ref;capacity_id:string}
type input_witness={input_id:string;provider:provider_ref;channel:string}
let resource_unit_name=function Truth_cells->"truth_cells"|Evidence_records->"evidence_records"
  |Edge_history_cells->"edge_history_cells"|Generation_counters->"generation_counters"
  |Active_attempt_records->"active_attempt_records"|Retained_correlation_records->"retained_correlation_records"
  |Timer_cells->"timer_cells"|Control_event_records->"control_event_records"|Input_rows_per_tick->"input_rows_per_tick"
let resource_unit_of_json value=match Json.string value with
  |"truth_cells"->Truth_cells|"evidence_records"->Evidence_records|"edge_history_cells"->Edge_history_cells
  |"generation_counters"->Generation_counters|"active_attempt_records"->Active_attempt_records
  |"retained_correlation_records"->Retained_correlation_records|"timer_cells"->Timer_cells
  |"control_event_records"->Control_event_records|"input_rows_per_tick"->Input_rows_per_tick
  |_->Diagnostic.fail "policy_material_contract" "Unknown material resource unit."
let resource_scope_name=function Per_executor->"per_executor"|Per_encounter_slot->"per_encounter_slot"
let resource_scope_of_json value=match Json.string value with
  |"per_executor"->Per_executor|"per_encounter_slot"->Per_encounter_slot
  |_->Diagnostic.fail "policy_material_contract" "Unknown material resource scope."
let owner_json=function Node id->obj["kind",str "node";"id",str id]
  |Input id->obj["kind",str "input";"id",str id]|Layout->obj["kind",str "layout"]
let owner_of_json value=match Json.string(get "kind" value)with
  |"node"->exact["kind";"id"]value;Node(name(get "id" value))
  |"input"->exact["kind";"id"]value;Input(name(get "id" value))
  |"layout"->exact["kind"]value;Layout
  |_->Diagnostic.fail "policy_material_contract" "Unknown resource owner."
let resource_json(value:resource_demand)=obj["id",str value.demand_id;"unit",str(resource_unit_name value.unit);
  "scope",str(resource_scope_name value.scope);"quantity",Json.int value.quantity;"owner",owner_json value.owner]
let allocation_json(value:allocation)=obj["demand_id",str value.demand_id;
  "provider",provider_ref_to_json value.provider;"capacity_id",str value.capacity_id]
let input_witness_json(value:input_witness)=obj["input_id",str value.input_id;
  "provider",provider_ref_to_json value.provider;"channel",str value.channel]
type local_node={local_id:string;model:I.model}
type kernel={node_values:local_node list;wire_values:I.wire list;input_values:I.external_input list;
  group_values:I.atomic_group list;export_values:I.endpoint list;layout_value:string;slot_count:int;library_pin:string}
let endpoint_json(value:I.endpoint)=obj["node",str value.node_id;"port",str value.port_id]
let endpoint_of_json value : I.endpoint=exact["node";"port"]value;
  {node_id=name(get "node" value);port_id=name(get "port" value)}
let wire_json(value:I.wire)=obj["from",endpoint_json value.producer;"to",endpoint_json value.consumer]
let input_json(value:I.external_input)=obj["id",str value.input_id;
  "kind",str(match value.input_kind with I.Evidence_input->"evidence"|I.Feedback_input->"feedback");
  "to",endpoint_json value.consumer]
let group_json(value:I.atomic_group)=obj["id",str value.group_id;"arbiter",str value.arbiter;
  "commits",arr(List.map str value.commits)]
let model_json(value:I.model)=obj["identity",Pin.to_json value.identity;
  "configuration_digest",str value.configuration_digest;"body",I.model_body_to_json value]
let kernel_to_json(value:kernel)=obj["schema_version",str kernel_schema;"profile",str I.profile;
  "phase_profile",str phase_profile;"observable_profile",str I.observable_profile;"library_digest",str value.library_pin;
  "layout",obj["layout_id",str value.layout_value;"slots",Json.int value.slot_count];
  "nodes",arr(List.map(fun(node:local_node)->obj["local_id",str node.local_id;"model",model_json node.model])value.node_values);
  "wires",arr(List.map wire_json value.wire_values);"inputs",arr(List.map input_json value.input_values);
  "atomic_groups",arr(List.map group_json value.group_values);"semantic_exports",arr(List.map endpoint_json value.export_values)]
let kernel_of_json ~library value=
  exact["schema_version";"profile";"phase_profile";"observable_profile";"library_digest";"layout";"nodes";"wires";"inputs";"atomic_groups";"semantic_exports"]value;
  require(get "schema_version" value=str kernel_schema && get "profile" value=str I.profile &&
    get "phase_profile" value=str phase_profile &&
    get "observable_profile" value=str I.observable_profile)"Unsupported material kernel, phase or observable profile.";
  let library_pin=sha(get "library_digest" value)in
  require(library_pin=I.library_digest library)"Material kernel does not name the original complete model library.";
  let layout=get "layout" value in exact["layout_id";"slots"]layout;
  let node_values=rows 256(get "nodes" value)|>List.map(fun value->
    exact["local_id";"model"]value;let model=get "model" value in
    exact["identity";"configuration_digest";"body"]model;
    let pin=Pin.of_json(get "identity" model)in
    let resolved=match List.find_opt(fun(model:I.model)->equal_json(Pin.to_json model.identity)(Pin.to_json pin))(I.models library)with
      |Some model->model|None->Diagnostic.fail "policy_material_contract" "Material kernel model is absent from the independent original library." in
    require(sha(get "configuration_digest" model)=resolved.configuration_digest &&
      equal_json(get "body" model)(I.model_body_to_json resolved))"Material kernel changed a complete model or configuration body.";
    {local_id=name(get "local_id" value);model=resolved})in
  require(node_values<>[])"A composite kernel cannot be empty.";unique "local node"(List.map(fun(node:local_node)->node.local_id)node_values);
  let wire_values=rows 8192(get "wires" value)|>List.map(fun value->exact["from";"to"]value;
    ({producer=endpoint_of_json(get "from" value);consumer=endpoint_of_json(get "to" value)}:I.wire))in
  let input_values=rows 256(get "inputs" value)|>List.map(fun value->exact["id";"kind";"to"]value;
    let input_kind=match Json.string(get "kind" value)with "evidence"->I.Evidence_input|"feedback"->I.Feedback_input
      |_->Diagnostic.fail "policy_material_contract" "Unknown external kernel input kind." in
    ({input_id=name(get "id" value);input_kind;consumer=endpoint_of_json(get "to" value)}:I.external_input))in
  unique "external input"(List.map(fun(input:I.external_input)->input.input_id)input_values);
  let group_values=rows 256(get "atomic_groups" value)|>List.map(fun value->exact["id";"arbiter";"commits"]value;
    ({group_id=name(get "id" value);arbiter=name(get "arbiter" value);
      commits=List.map name(rows 256(get "commits" value))}:I.atomic_group))in
  unique "atomic group"(List.map(fun(group:I.atomic_group)->group.group_id)group_values);
  {node_values;wire_values;input_values;group_values;
    export_values=List.map endpoint_of_json(rows 16384(get "semantic_exports" value));
    layout_value=name(get "layout_id" layout);slot_count=integer ~minimum:1 16(get "slots" layout);library_pin}
let nodes(value:kernel)=value.node_values
let wires(value:kernel)=value.wire_values
let inputs(value:kernel)=value.input_values
let atomic_groups(value:kernel)=value.group_values
let semantic_exports(value:kernel)=value.export_values
let layout_id(value:kernel)=value.layout_value
let slots(value:kernel)=value.slot_count
type target=Primitive of string|Configuration of string|Replication of string|Wire of int
  |External_input of string|Atomic_group of string|Semantic_export of int|Slot_layout
type material_site={member:string;feature:string;path:Molecule_coordinates.Path.t}
type carrier={target:target;sites:material_site list}
type product_binding={node:string;symbol:string;member:string;product:Pin.t}
let target_to_json=function
  |Primitive id->obj["kind",str "primitive";"id",str id]|Configuration id->obj["kind",str "configuration";"id",str id]
  |Replication id->obj["kind",str "replication";"id",str id]|Wire index->obj["kind",str "wire";"index",Json.int index]
  |External_input id->obj["kind",str "external_input";"id",str id]|Atomic_group id->obj["kind",str "atomic_group";"id",str id]
  |Semantic_export index->obj["kind",str "semantic_export";"index",Json.int index]|Slot_layout->obj["kind",str "slot_layout"]
let target_of_json value=let kind=Json.string(get "kind" value)in
  let id()=exact["kind";"id"]value;name(get "id" value)in
  let index()=exact["kind";"index"]value;integer 16383(get "index" value)in
  match kind with "primitive"->Primitive(id())|"configuration"->Configuration(id())|"replication"->Replication(id())
    |"wire"->Wire(index())|"external_input"->External_input(id())|"atomic_group"->Atomic_group(id())
    |"semantic_export"->Semantic_export(index())|"slot_layout"->exact["kind"]value;Slot_layout
    |_->Diagnostic.fail "policy_material_contract" "Unknown material carrier target."
let target_inventory(value:kernel)=
  List.concat_map(fun(node:local_node)->[Primitive node.local_id;Configuration node.local_id;Replication node.local_id])value.node_values@
  List.mapi(fun index _->Wire index)value.wire_values@
  List.map(fun(input:I.external_input)->External_input input.input_id)value.input_values@
  List.map(fun(group:I.atomic_group)->Atomic_group group.group_id)value.group_values@
  List.mapi(fun index _->Semantic_export index)value.export_values@[Slot_layout]
let site_json(value:material_site)=obj["member",str value.member;"feature",str value.feature;"path",Molecule_coordinates.Path.to_json value.path]
let carrier_json(value:carrier)=obj["target",target_to_json value.target;"sites",arr(List.map site_json value.sites)]
let product_json(value:product_binding)=obj["node",str value.node;"symbol",str value.symbol;
  "member",str value.member;"product",Pin.to_json value.product]
type t={identity_value:Pin.t;kernel_value:kernel;structure_value:Policy_mrna_structure.t;
  material_values:Molecule.t list;carrier_values:carrier list;resource_values:resource_demand list;
  allocation_values:allocation list;input_witness_values:input_witness list;product_values:product_binding list}
let body_to_json(value:t)=obj["kernel",kernel_to_json value.kernel_value;
  "structure_authority",Policy_mrna_structure.to_json value.structure_value;
  "material_key",arr(List.map Molecule.to_json value.material_values);
  "carriers",arr(List.map carrier_json value.carrier_values);"resources",arr(List.map resource_json value.resource_values);
  "allocations",arr(List.map allocation_json value.allocation_values);"input_witnesses",arr(List.map input_witness_json value.input_witness_values);
  "products",arr(List.map product_json value.product_values)]
let to_json(value:t)=obj["schema_version",str schema_version;"profile",str profile;
  "identity",Pin.to_json value.identity_value;"body",body_to_json value]
let of_json ~library raw=
  M.check_resources raw;exact["schema_version";"profile";"identity";"body"]raw;
  require(get "schema_version" raw=str schema_version && get "profile" raw=str profile)"Unsupported whole-graph material case profile.";
  let identity_value=Pin.of_json(get "identity" raw)and body=get "body" raw in
  exact["kernel";"structure_authority";"material_key";"carriers";"resources";"allocations";"input_witnesses";"products"]body;
  require(Pin.kind identity_value=Pin.Model && Pin.content_fingerprint identity_value=Canonical.fingerprint body)
    "Material case identity must pin its complete supplied body.";
  let carrier_values=rows 32768(get "carriers" body)|>List.map(fun value->exact["target";"sites"]value;
    let sites=rows 64(get "sites" value)|>List.map(fun value->exact["member";"feature";"path"]value;
      {member=name(get "member" value);feature=name(get "feature" value);path=Molecule_coordinates.Path.of_json(get "path" value)})in
    require(sites<>[])"Every material disposition requires a nonempty actual feature/path witness.";
    {target=target_of_json(get "target" value);sites})in
  unique "carrier target"(List.map(fun(value:carrier)->Canonical.encode(target_to_json value.target))carrier_values);
  let resource_values=rows 4096(get "resources" body)|>List.map(fun value->
    exact["id";"unit";"scope";"quantity";"owner"]value;
    {demand_id=name(get "id" value);unit=resource_unit_of_json(get "unit" value);scope=resource_scope_of_json(get "scope" value);
      quantity=integer ~minimum:1 1000000(get "quantity" value);owner=owner_of_json(get "owner" value)})in
  unique "resource demand"(List.map(fun(value:resource_demand)->value.demand_id)resource_values);
  let allocation_values=rows 4096(get "allocations" body)|>List.map(fun value->exact["demand_id";"provider";"capacity_id"]value;
    {demand_id=name(get "demand_id" value);provider=provider_ref_of_json(get "provider" value);capacity_id=name(get "capacity_id" value)})in
  unique "allocation demand"(List.map(fun(value:allocation)->value.demand_id)allocation_values);
  let input_witness_values=rows 256(get "input_witnesses" body)|>List.map(fun value->exact["input_id";"provider";"channel"]value;
    {input_id=name(get "input_id" value);provider=provider_ref_of_json(get "provider" value);channel=name(get "channel" value)})in
  unique "input witness"(List.map(fun(value:input_witness)->value.input_id)input_witness_values);
  let product_values=rows 256(get "products" body)|>List.map(fun value->exact["node";"symbol";"member";"product"]value;
    {node=name(get "node" value);symbol=name(get "symbol" value);member=name(get "member" value);product=Pin.of_json(get "product" value)})in
  unique "product node"(List.map(fun(value:product_binding)->value.node)product_values);
  let value={identity_value;kernel_value=kernel_of_json ~library(get "kernel" body);
    structure_value=Policy_mrna_structure.of_json(get "structure_authority" body);
    material_values=List.map(fun raw->Molecule.of_json raw)(rows Policy_mrna_structure.max_members(get "material_key" body));
    carrier_values;resource_values;allocation_values;input_witness_values;product_values}in
  require(equal_json raw(to_json value))"Material case must preserve its complete canonical typed body without decoder normalization.";
  M.check_resources(to_json value);value
let fingerprint value=Canonical.fingerprint(to_json value)
let identity(value:t)=value.identity_value
let kernel(value:t)=value.kernel_value
let library_digest(value:t)=value.kernel_value.library_pin
let structure_authority(value:t)=value.structure_value
let material_key(value:t)=value.material_values
let carriers(value:t)=value.carrier_values
let resources(value:t)=value.resource_values
let allocations(value:t)=value.allocation_values
let input_witnesses(value:t)=value.input_witness_values
let products(value:t)=value.product_values
type node_binding={local_id:string;node_id:string}
type proposal={contract_pin:string;bindings:node_binding list}
let proposal_of_json raw=
  M.check_resources raw;exact["schema_version";"contract_digest";"nodes"]raw;
  require(get "schema_version" raw=str proposal_schema)"Unsupported material binding proposal.";
  let bindings=rows 256(get "nodes" raw)|>List.map(fun value->exact["local_id";"node_id"]value;
    {local_id=name(get "local_id" value);node_id=name(get "node_id" value)})in
  unique "proposed local node"(List.map(fun(value:node_binding)->value.local_id)bindings);
  unique "proposed implementation node"(List.map(fun(value:node_binding)->value.node_id)bindings);
  {contract_pin=sha(get "contract_digest" raw);bindings}
let proposal_to_json(value:proposal)=obj["schema_version",str proposal_schema;"contract_digest",str value.contract_pin;
  "nodes",arr(List.map(fun(value:node_binding)->obj["local_id",str value.local_id;"node_id",str value.node_id])value.bindings)]
let proposed_contract(value:proposal)=value.contract_pin
let node_bindings(value:proposal)=value.bindings
