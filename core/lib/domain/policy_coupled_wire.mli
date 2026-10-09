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

(** Validate the complete logical JSON, including keys, cycles, scalar limits,
    depth and canonical byte size. Return that exact byte size. *)
val preflight : ?charge:(int -> unit) -> Json.t -> int

(** Encode deterministic sorted-object, ordered-array DFS postorder with exact
    typed-node interning. Check the ordinary physical packet limits too. *)
val encode : ?charge:(int -> unit) -> Json.t -> Json.t

(** Validate the closed packet and prove expanded bounds before constructing
    immutable logical JSON. Check full expanded canonical SHA-256 freshly. *)
val decode : ?charge:(int -> unit) -> Json.t -> Json.t
