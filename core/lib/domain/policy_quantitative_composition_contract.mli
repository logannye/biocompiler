(** Separate material state owners and explicit edge signals under a supplied
    single-prestate atomic writer. These contracts establish no physical transport. *)
open Bioc_wire
module N=Policy_quantitative_network_contract
val profile:string
val synchronization:string
type flow=private {transfer:string;boundary:string;model:Pinned_identity.t}
type write=private {transition:string;boundary:string}
type flow_input=private {transfer:string;boundary:string}
type owner_contract=private {id:string;compartment:string;state_node:string;state_model:Pinned_identity.t;
  snapshot_boundary:string;next_boundary:string;next_model:Pinned_identity.t;writes:write list;flows:flow_input list}
type coordinator_contract=private {id:string;network:N.local_contract;flows:flow list}
type role=Owner of owner_contract|Coordinator of coordinator_contract
type local_contract=private {raw:Json.t;role:role}
type owner=private {instance:string;component:Pinned_identity.t;contract:string;compartment:string;state:string}
type selection=private {raw:Json.t;network:N.selection;owners:owner list}
val local_of_json:?charge:(int->unit)->Json.t->local_contract
val selection_of_json:?charge:(int->unit)->Json.t->selection
val local_to_json:local_contract->Json.t
val selection_to_json:selection->Json.t
