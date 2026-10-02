(** Invocation-local independent source-profile authority. This private checker
    never executes or exports its ephemeral declaration witness. *)
type error = { message : string; node_id : string option;
  source : Bioc_domain.Behavior.source_location option }
exception Unsupported of error
val format_error : error -> string
type policy
val parse_policy : budget:Realization_budget.t -> Checked_request.t -> profile:string -> policy
val allowed_operators : policy -> string list
val max_gate_count : policy -> Z.t option
val minimize : policy -> string
val violations : budget:Realization_budget.t -> policy -> Bioc_domain.Mechanism.t -> string list
type t
val derive : budget:Realization_budget.t -> Checked_request.t -> Bioc_domain.Synthetic_authority.Config.t -> t
val source_map : t -> (string * string list) list
val behavior_requirement_ids : t -> (string * string list) list
val node_count : t -> int
val gate_count : t -> int
