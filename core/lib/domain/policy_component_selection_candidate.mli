(** Untrusted complete candidate census for a separately supplied original
    selection request. Decoding establishes shape, child-library binding and
    exact ID coverage only; it grants no eligibility or selection capability. *)
open Bioc_wire
module R = Policy_component_selection_request
module C = Policy_component_material_candidate
val schema_version : string
type alternative = private { id:string; candidate:C.t }
type t
val of_json : ?charge:(int -> unit) -> request:R.t -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string
val request_fingerprint : t -> string
val decoding_work : t -> int
val alternatives : t -> alternative list
val evaluation_order : t -> alternative list

(** This is the producer's proposal, including null for no proposed winner.
    A known ID may still be ineligible or incorrectly ranked. *)
val selected_id : t -> string option
