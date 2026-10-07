(** Original policy, implementation, material and context authority. This closed
    first profile supplies exactly one whole-graph material case. Decoding and
    content identities grant no acceptance; the checker must reconstruct every
    boundary using these external inputs. *)
open Bioc_wire
module R = Policy_realization_request
module C = Policy_material_contract
module X = Policy_material_context
val schema_version : string
val profile : string
val resource_profile : string
type catalog_binding = private {
  entry_id:string; entry_version:string; entry_digest:string;
  operation:C.provider_ref; realization:C.provider_ref;
  material_contract:Pinned_identity.t;
}
type budgets = private { max_work:int; max_report_bytes:int; max_report_nodes:int }
type t

(** Bounded iterative accounting preflight. Charges one unit per JSON value/key,
    list edge and ancestor identity visit, plus string/decimal scalar bytes;
    returns the exact canonical encoded byte count. Fixed byte/node/depth limits
    still apply with a no-op charge callback. Defaults are the original request
    limits; explicit limits cannot exceed the fixed protocol ceiling. This is a logical data-work metric,
    not a ceiling on native CPU instructions. *)
val preflight : ?max_bytes:int -> ?max_nodes:int -> ?max_depth:int -> charge:(int -> unit) -> Json.t -> int

(** Preflight each original decoder input before traversing it; charge exact
    canonical encoding and hashing bytes before those passes. The optional
    count-only callback lets a checker debit its enclosing work allowance. *)
val of_json : ?charge:(int -> unit) -> Json.t -> t
val decoding_work : t -> int
val to_json : t -> Json.t
val fingerprint : t -> string
val implementation_request : t -> R.t
val material_contract : t -> C.t
val context : t -> X.t
val catalog_binding : t -> catalog_binding
val budgets : t -> budgets
