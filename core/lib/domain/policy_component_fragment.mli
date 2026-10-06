(** Closed structural descriptions of partial primitive graphs. Decoding checks
    local wiring and complete supplied model membership only. It establishes no
    source correspondence, complete assembly, execution, material realization,
    requirement satisfaction or export authority.

    Every primitive input has exactly one local wire, boundary input or external
    slot. Every output remains observable in fixed node/port order. Atomic groups
    remain wholly local. A boundary output describes an endpoint, not a transport
    implementation; later original assembly authority must supply every link and
    its scope relation. Immutable executor constants may broadcast; arbitrary
    executor logic may not. Global cycles, bank destinations and writer-group
    ownership must be checked again on the complete reconstructed graph.

    Structural layouts admit 1..16 slots; this does not broaden a composed
    acceptance profile's independently declared slot bounds. No source, provider,
    material or whole-library identity enters the serialized fragment. *)
open Bioc_wire

val schema_version : string
val profile : string
val primitive_profile : string
val observable_profile : string
val phase_profile : string
val resource_profile : string

type slot_layout = { layout_id : string; slots : int }
type node = private { node_id : string; model : Policy_implementation.model }
type boundary_port = private {
  boundary_id : string;
  direction : Policy_implementation.direction;
  signal_type : Policy_implementation.signal_type;
  endpoint : Policy_implementation.endpoint;
  replication : Policy_implementation.replication;
}
type external_slot = private {
  slot_id : string;
  input_kind : Policy_implementation.external_kind;
  consumer : Policy_implementation.endpoint;
  replication : Policy_implementation.replication;
}
type t

(** Exact full model bodies resolve against the independently supplied library.
    Raw ingress is bounded before traversal: 2 MiB canonical JSON, 100000 nodes,
    depth 48, no floats or duplicate object keys, and bounded UTF-8 strings. *)
val of_json : library:Policy_implementation.library -> Json.t -> t
val to_json : t -> Json.t
val fingerprint : t -> string

(** Context of this decoding, excluded from the fragment's serialized identity.
    Equal fragments can be checked under two different original libraries, but
    membership in one library never establishes membership in the other. *)
val model_library_digest : t -> string
val id : t -> string
val version : t -> string
val layout : t -> slot_layout
val nodes : t -> node list
val wires : t -> Policy_implementation.wire list
val boundary_ports : t -> boundary_port list
val external_slots : t -> external_slot list
val atomic_groups : t -> Policy_implementation.atomic_group list
val semantic_exports : t -> Policy_implementation.endpoint list
