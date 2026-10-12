(** RC3 joins complete original source, model, molecular and deployment authority.
    A token means static correspondence and complete bounded domain enumeration;
    it grants no construction, behavioral or empirical acceptance. *)
open Bioc_wire
module R = Bioc_domain.Policy_controlled_composition_request
module Domain = Bioc_domain.Policy_controlled_domain
type t
val admit : charge:(int -> unit) -> R.t -> t
val report : t -> Json.t
val domain : t -> Domain.validated
