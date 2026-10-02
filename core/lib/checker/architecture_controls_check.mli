(** Independent bounded source theorems. A successful theorem does not establish
    material control, product authority, independence, empirical function or
    architecture acceptance. Full original authority is retained by [Input]. *)
val checker_version : string
type budget
val max_work : int
val make_budget : ?parent:Work_budget.t -> ?maximum:int -> unit -> budget
module Input : sig
  type bindings = Defaults | Frozen of Bioc_wire.Json.t
  type t
  val make : source:Bioc_domain.Human_request.t -> target:string -> controlling_node_ids:string list ->
    kind:Bioc_domain.Architecture_contract.control_kind -> bindings:bindings -> t
  val of_json : Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
end
type outcome = Proved | Not_proved of string
type result = { outcome : outcome; targets : string list; witnesses : Bioc_wire.Json.t list; work : int }
val prove : ?budget:budget -> Input.t -> result
val reason : result -> string option
(* The authoritative integration entry point uses the original request's frozen
   resolved bindings. Explicit Defaults/Frozen inputs are separate theorem inputs. *)
val prove_source : ?budget:budget -> source:Bioc_domain.Human_request.t -> target:string -> controlling_node_ids:string list ->
  kind:Bioc_domain.Architecture_contract.control_kind -> unit -> result
val extended_targets : ?budget:budget -> source:Bioc_domain.Human_request.t -> target:string ->
  kind:Bioc_domain.Architecture_contract.control_kind -> unit -> string list
