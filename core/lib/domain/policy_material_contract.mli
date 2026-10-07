(** Independently supplied, finite whole-graph-to-material cases. Decoding only
    establishes closed bounded shape and content identities. The exact supplied
    case is a conditional model-to-sequence premise, never biological evidence.
    Local kernels acquire no executable authority until an independent checker
    establishes their total ordered bijection to a checked implementation. *)
open Bioc_wire
module I = Policy_implementation
val schema_version : string
val profile : string
val phase_profile : string
val kernel_schema : string
val proposal_schema : string

type provider_ref = private {
  definition_id:string; definition_version:string; definition_digest:string;
}
val provider_ref_of_json : Json.t -> provider_ref
val provider_ref_to_json : provider_ref -> Json.t

type resource_unit = Truth_cells | Evidence_records | Edge_history_cells
  | Generation_counters | Active_attempt_records | Retained_correlation_records
  | Timer_cells | Control_event_records | Input_rows_per_tick
type resource_scope = Per_executor | Per_encounter_slot
type resource_owner = Node of string | Input of string | Layout
type resource_demand = {
  demand_id:string; unit:resource_unit; scope:resource_scope;
  quantity:int; owner:resource_owner;
}
type allocation = { demand_id:string; provider:provider_ref; capacity_id:string }
type input_witness = { input_id:string; provider:provider_ref; channel:string }
val resource_unit_name : resource_unit -> string
val resource_unit_of_json : Json.t -> resource_unit
val resource_scope_name : resource_scope -> string
val resource_scope_of_json : Json.t -> resource_scope

(* Quantities are per named scope, never software work/trace budgets, dosage or
   RNA copy number. Active attempts and retained historical correlations are
   distinct units. Capacity records live in the ORIGINAL provider body, with
   matching unit/scope and integer quantity. Allocations have exclusive demand
   ownership; a context checker must sum shared capacities, derive actual graph
   and finite-domain lower bounds, and check the entire original input grammar.
   This domain and the material leaf do not establish those obligations. *)
type local_node = { local_id:string; model:I.model }
type kernel
val nodes : kernel -> local_node list
val wires : kernel -> I.wire list
val inputs : kernel -> I.external_input list
val atomic_groups : kernel -> I.atomic_group list
val semantic_exports : kernel -> I.endpoint list
val layout_id : kernel -> string
val slots : kernel -> int
val kernel_to_json : kernel -> Json.t

type target = Primitive of string | Configuration of string | Replication of string
  | Wire of int | External_input of string | Atomic_group of string
  | Semantic_export of int | Slot_layout
type material_site = { member:string; feature:string; path:Molecule_coordinates.Path.t }
type carrier = { target:target; sites:material_site list }
type product_binding = { node:string; symbol:string; member:string; product:Pinned_identity.t }
val target_to_json : target -> Json.t
val target_inventory : kernel -> target list

type t
val of_json : library:I.library -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val identity : t -> Pinned_identity.t
val kernel : t -> kernel
val library_digest : t -> string
val structure_authority : t -> Policy_mrna_structure.t
val material_key : t -> Molecule.t list
val carriers : t -> carrier list
val resources : t -> resource_demand list
val allocations : t -> allocation list
val input_witnesses : t -> input_witness list
val products : t -> product_binding list

(* A proposal renames node IDs only. List order, external input names, layout,
   group IDs, port names, every complete model/configuration, wires and exports
   must remain exact. It cannot choose phases, hidden outputs or material keys. *)
type node_binding = { local_id:string; node_id:string }
type proposal
val proposal_of_json : Json.t -> proposal
val proposal_to_json : proposal -> Json.t
val proposed_contract : proposal -> string
val node_bindings : proposal -> node_binding list
