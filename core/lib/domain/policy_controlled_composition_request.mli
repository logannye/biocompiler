(** Complete caller-supplied controlled authority. This is a bounded decoder,
    never a construction, behavioral or empirical acceptance token. *)
open Bioc_wire
module D = Policy_document
module Domain = Policy_controlled_domain
module Material = Policy_mrna_structure
type budgets = private { max_work:int; max_report_bytes:int; max_report_nodes:int }
type t
val schema_version : string
val profile : string
val resource_profile : string
val of_json : ?charge:(int -> unit) -> Json.t -> t
val to_json : t -> Json.t
val raw : t -> Json.t
val fingerprint : t -> string
val decoding_work : t -> int
val document : t -> D.controlled
val domain : t -> Domain.t
val material : t -> Material.t
val budgets : t -> budgets
