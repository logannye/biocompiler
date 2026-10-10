open Bioc_wire
module N=Policy_quantitative_network_contract
module P=Pinned_identity
let profile="biocompiler.policy_atomic_component_transfer_network.v0.1"
let synchronization="one_prestate_one_atomic_commit"
type flow={transfer:string;boundary:string;model:P.t}
type write={transition:string;boundary:string}
type flow_input={transfer:string;boundary:string}
type owner_contract={id:string;compartment:string;state_node:string;state_model:P.t;
  snapshot_boundary:string;next_boundary:string;next_model:P.t;writes:write list;flows:flow_input list}
type coordinator_contract={id:string;network:N.local_contract;flows:flow list}
type role=Owner of owner_contract|Coordinator of coordinator_contract
type local_contract={raw:Json.t;role:role}
type owner={instance:string;component:P.t;contract:string;compartment:string;state:string}
type selection={raw:Json.t;network:N.selection;owners:owner list}
let get key raw=Json.field key(Json.object_fields raw)
let exact keys raw=Json.exact_fields keys(Json.object_fields raw)
let require condition message=Diagnostic.require condition "policy_quantitative_composition_contract" message
let name raw=let value=Json.name raw in require(String.length value<=256)"Composition identity exceeds its bound.";value
let pin raw=let value=P.of_json raw in require(P.kind value=P.Model)"Composition requires full supplied model pins.";value
let preflight charge raw=ignore(Policy_material_request.preflight ~max_bytes:262144 ~max_nodes:16384 ~max_depth:40 ~charge raw)
let unique label values=require(List.length values=List.length(List.sort_uniq String.compare values))("Duplicate "^label^" identity.")
let binary(law:N.mechanism)=require(List.for_all(fun(r:N.reservoir)->r.levels=2)law.reservoirs)
  "The composed profile requires two-to-four binary reservoirs with one quantum of capacity each."
let local_of_json ?(charge=fun _->()) raw=
  preflight charge raw;
  let role=match Json.string(get "role" raw)with
  |"coordinator"->
    exact["role";"id";"network";"flows"]raw;
    let network=N.local_of_json ~charge(get "network" raw)in binary network.mechanism;
    let flows=List.map(fun value->exact["transfer";"boundary";"model"]value;
      {transfer=name(get "transfer" value);boundary=name(get "boundary" value);model=pin(get "model" value)})
      (Molecular_record.array ~maximum:8(get "flows" raw))in
    require(List.map(fun(f:flow)->f.transfer)flows=List.map(fun(e:N.transfer)->e.id)network.mechanism.transfers)
      "Coordinator ports must cover every original edge in declared order.";
    unique "coordinator flow boundary"(List.map(fun(f:flow)->f.boundary)flows);
    let id=name(get "id" raw)in require(id=network.id)"Coordinator and network contract identities must agree.";
    Coordinator{id;network;flows}
  |"owner"->
    exact["role";"id";"compartment";"state";"snapshot_boundary";"next";"writes";"flows"]raw;
    let state=get "state" raw and next=get "next" raw in exact["node";"model"]state;exact["boundary";"model"]next;
    let writes=List.map(fun value->exact["transition";"boundary"]value;
      {transition=name(get "transition" value);boundary=name(get "boundary" value)})
      (Molecular_record.array ~maximum:32(get "writes" raw))in
    require(writes<>[])"Every reservoir must receive its complete atomic write inventory.";
    unique "owner transition"(List.map(fun(w:write)->w.transition)writes);
    unique "owner write boundary"(List.map(fun(w:write)->w.boundary)writes);
    let flows=List.map(fun value->exact["transfer";"boundary"]value;
      {transfer=name(get "transfer" value);boundary=name(get "boundary" value)})
      (Molecular_record.array ~maximum:8(get "flows" raw))in
    unique "owner flow"(List.map(fun(f:flow_input)->f.transfer)flows);
    unique "owner flow boundary"(List.map(fun(f:flow_input)->f.boundary)flows);
    Owner{id=name(get "id" raw);compartment=name(get "compartment" raw);state_node=name(get "node" state);
      state_model=pin(get "model" state);snapshot_boundary=name(get "snapshot_boundary" raw);
      next_boundary=name(get "boundary" next);next_model=pin(get "model" next);writes;flows}
  |_->Diagnostic.fail "policy_quantitative_composition_contract" "Unknown selected quantitative component role."in
  {raw;role}
let selection_of_json ?(charge=fun _->()) raw=
  preflight charge raw;exact["network";"owners";"synchronization"]raw;
  require(get "synchronization" raw=Json.String synchronization)
    "Composed state requires the explicit single-prestate atomic-commit coordination premise.";
  let network=N.selection_of_json ~charge(get "network" raw)in binary network.mechanism;
  let owners=List.map(fun value->exact["instance";"component";"contract";"compartment";"state"]value;
    {instance=name(get "instance" value);component=pin(get "component" value);contract=name(get "contract" value);
      compartment=name(get "compartment" value);state=name(get "state" value)})
    (Molecular_record.array ~maximum:4(get "owners" raw))in
  require(List.map(fun(o:owner)->o.compartment)owners=List.map(fun(r:N.reservoir)->r.compartment)network.mechanism.reservoirs)
    "Selected state owners must partition every reservoir in original coordinate order.";
  unique "state owner instance"(network.instance::List.map(fun(o:owner)->o.instance)owners);
  unique "original reservoir state"(List.map(fun(o:owner)->o.state)owners);
  {raw;network;owners}
let local_to_json(value:local_contract)=value.raw
let selection_to_json(value:selection)=value.raw
