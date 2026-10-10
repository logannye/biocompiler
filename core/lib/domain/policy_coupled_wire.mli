open Bioc_wire

(** Lossless transport for explicitly selected coupled operations. A packet is
    data, never an admission or checking capability. Expanded logical identity
    and all downstream semantic checks remain unchanged. *)
val schema_version : string
val profile : Json.t
val max_expanded_nodes : int
val max_expanded_bytes : int
val max_packet_nodes : int
val is_packet : Json.t -> bool
val export_schema_version : string
val export_profile : Json.t
val max_export_nodes : int
val max_export_bytes : int
val is_export_packet : Json.t -> bool

(** Validate the complete logical JSON, including keys, cycles, scalar limits,
    depth and canonical byte size. Return that exact byte size. *)
val preflight : ?charge:(int -> unit) -> Json.t -> int

(** Encode deterministic sorted-object, ordered-array DFS postorder with exact
    typed-node interning. Check the ordinary physical packet limits too. *)
val encode : ?charge:(int -> unit) -> Json.t -> Json.t

(** Validate the closed packet and prove expanded bounds before constructing
    immutable logical JSON. Check full expanded canonical SHA-256 freshly. *)
val decode : ?charge:(int -> unit) -> Json.t -> Json.t

(** Response-only paired assurance export. Require the closed export response
    shape, and independently bound its artifact and its base result with a
    null artifact by the original logical limits. The aggregate bounds are
    derived from that pair; physical packet, depth and scalar limits remain
    unchanged. Preflight visits the logical value once; decoding establishes
    both partitions from postorder size metadata before building JSON. Base
    encode/decode do not select or accept this additive packet schema. *)
val preflight_export : ?charge:(int -> unit) -> Json.t -> int
val encode_export : ?charge:(int -> unit) -> Json.t -> Json.t
val decode_export : ?charge:(int -> unit) -> Json.t -> Json.t
