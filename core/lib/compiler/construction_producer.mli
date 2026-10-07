(** Deterministic untrusted proposals from complete supplied construction
    authority. No private checker reconstruction is reused. *)
val implementation_version : string
module Limits : sig
  type t
  (* Optional reductions support explicitly bounded producer runs. No ceiling
     can exceed the legacy residue limits or the native fixed work limit. *)
  val make : ?produced_residues:int -> ?final_residues:int -> ?work:int -> unit -> t
end
val construct : ?parent:Bioc_checker.Work_budget.t -> ?charge:(int -> unit) -> ?limits:Limits.t -> Bioc_domain.Construction.Request.t -> Bioc_domain.Construction_artifact.t

(** Propose molecular content from an independently supplied template and exact
    original covalent-member order. Context and payload completeness remain
    unassessed; no original circuit or policy request is synthesized. *)
val construct_template : ?parent:Bioc_checker.Work_budget.t -> ?charge:(int -> unit) -> ?limits:Limits.t ->
  member_order:string list -> Bioc_domain.Payload_template.t -> Bioc_domain.Construction_content.t

(** Charge the complete typed content before allocating its serialized children. *)
val content_json : ?charge:(int -> unit) -> Bioc_domain.Construction_content.t -> Bioc_wire.Json.t
