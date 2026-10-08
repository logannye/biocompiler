(** Bounded original provider-dependency derivation. This is syntax, identity and
    reachability only: it never checks availability, resources, source semantics,
    preservation or material acceptance, and exposes no accepted value. *)
open Bioc_wire
module R = Policy_realization_request
module X = Policy_component_context
module C = Policy_material_contract
module P = Pinned_identity
val schema_version : string
val transport_schema_version : string
val max_dependencies : int
val max_roots : int
val max_nodes : int
val max_edges : int
type pending_dependency = private {
  entry_id:string; entry_digest:string; dependency_index:int; definition:C.provider_ref;
}
val pending_dependency_to_json : pending_dependency -> Json.t

(** Resolve exact original catalog and definition pins, retaining every original
    dependency occurrence in bridge/index order. Evidence remains unsupported. *)
val pending_dependencies : ?charge:(int -> unit) -> R.t -> pending_dependency list
type origin = Original_path of string | Catalog of pending_dependency
type root = private {origin:origin; definition:C.provider_ref}
type relation = Interface_environment | Chassis_capability | Chassis_interface | Chassis_environment | Transport_environment
type edge = private {source:C.provider_ref; target:C.provider_ref; relation:relation; index:int}
type issue_kind = Missing | Cycle | Extra | Unsupported
type issue = private {kind:issue_kind; code:string; references:C.provider_ref list}
type t

(** Source roots precede catalog roots. Nodes and edges preserve deterministic
    first-encounter DFS order. A missing body is a finding, not a new premise.
    The chassis operational_model checks identity and is never a graph edge. *)
val derive : ?charge:(int -> unit) -> original:R.t -> context:X.t -> unit -> t
val dependencies : t -> pending_dependency list
val roots : t -> root list
val reachable : t -> C.provider_ref list
val edges : t -> edge list
val issues : t -> issue list
val to_json : t -> Json.t
