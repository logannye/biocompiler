(** Neutral codec for a complete untrusted component material candidate.
    Typed decoding grants no correspondence, preservation, material, context or
    export acceptance. No producer or acceptance checker is a dependency. *)
open Bioc_wire
module O = Policy_operational
module I = Policy_implementation
module U = Policy_implementation_binding
module Q = Policy_component_assembly_proposal
module K = Construction_content

val schema_version : string
type t

(** Decode against the independently supplied original model library. The
    optional count-only callback bounds enclosing work without changing data.
    The six-field schema and /payload/candidate diagnostic path follow the
    existing component service. Every original candidate field is retained. *)
val of_json : ?charge:(int -> unit) -> library:I.library -> Json.t -> t
val to_json : t -> Json.t
val decoding_work : t -> int
val behavior : t -> O.behavior
val implementation : t -> I.t
val binding : t -> U.t
val assembly_proposal : t -> Q.t
val construction : t -> K.t
