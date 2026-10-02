(* Checker-private expected declarations. These values must never be exposed
   through a public checker signature or imported by a producer. *)
type node = { id : string; kind : string; inputs : string list; role : string option;
              attributes : Bioc_wire.Json.t; data_type : Bioc_wire.Json.t;
              contact_bound : bool; semantics : Bioc_wire.Json.t }
type graph
val source_graph : budget:Work_budget.t -> Bioc_domain.Human_request.t -> graph
val behavior_graph : budget:Work_budget.t -> Bioc_domain.Behavior.t -> graph
val nodes : graph -> node list
val lookup : graph -> string -> node
val find : graph -> string -> node option
val lineage : graph -> string -> string list
val causal_nodes : graph -> string list -> string list
val runtime : node -> bool
val input : node -> int -> string
type channel = { channel_id : string; sender_ids : string list; receiver_ids : string list }
val source_channels : graph -> channel list
val selected_instances : budget:Work_budget.t -> Bioc_domain.Architecture_build.t -> Bioc_domain.Architecture_request.t ->
  Bioc_domain.Architecture_refinement.t list * string list
type inventories = { placements : Bioc_wire.Json.t list; helpers : Bioc_wire.Json.t list;
                     channels : Bioc_wire.Json.t list; control_domains : Bioc_wire.Json.t list;
                     availability : Bioc_wire.Json.t list }
val inventories : budget:Work_budget.t -> Bioc_domain.Architecture_refinement.t list -> inventories * Bioc_wire.Json.t list
val expected_construction : budget:Work_budget.t -> Bioc_domain.Architecture_request.t -> Bioc_wire.Json.t list -> Bioc_domain.Construction.Request.t
val assumptions : Bioc_domain.Architecture_request.t -> Bioc_domain.Architecture_refinement.t list -> string list
val expected_ledger : budget:Work_budget.t -> Bioc_domain.Architecture_request.t -> graph ->
  Bioc_domain.Architecture_refinement.t list -> assumptions:string list -> source_complete:bool ->
  Bioc_domain.Architecture_build.Requirement_realization.t list * (string * string list) list
val charge_json : Work_budget.t -> Bioc_wire.Json.t -> unit
