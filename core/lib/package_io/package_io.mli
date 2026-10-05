(** Single-owner raw archive leases over inherited descriptors. No pathname is
    opened. A digest/lease proves byte transport, never semantic acceptance. *)
module B = Bioc_artifact.Archive_budget
type descriptor = private { bytes : int; sha256 : string }
type t
val descriptor_of_json : max_bytes:int -> Bioc_wire.Json.t -> descriptor
val descriptor_to_json : descriptor -> Bioc_wire.Json.t
val with_fds : input:string -> output:string -> (t -> 'a) -> 'a
(** [input] is a canonical inherited descriptor number or [-]. Output must be
    a distinct, private, empty, writable regular file. Both duplicates close on
    every exit. Neither descriptor may alias stdin/stdout/stderr or each other. *)
val bind_owner : t -> B.t -> unit
(** Exactly once, before transport; the owner must have been configured when
    this package lifetime was created. Existing callback owners cannot expand. *)
val read_archive : t -> B.t -> descriptor -> string
val write_archive : t -> B.t -> string -> descriptor
(** Read and write are each single-use, including failures. A failed write may
    leave private partial output; it never yields a descriptor or retries. The
    caller must discard private output unless the complete bound reply succeeds. *)
val input_present : t -> bool
val output_written : t -> bool
