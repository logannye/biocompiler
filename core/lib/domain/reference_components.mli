(** Offline historical exact-reference adapter. A selection supplies independent
    pins; stored reference acceptance does not establish biological behavior. *)
module Codec = Verification_exploration.Codec
val adapter_version : string
val supported_reference_set : string
module Selection : sig
  type t
  val schema_version : string
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val of_json_text : ?limits:Codec.limits -> ?path:string -> string -> t
  val make : ?limits:Codec.limits -> manifest:Pinned_identity.t -> reference:Pinned_identity.t -> unit -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val manifest : t -> Pinned_identity.t
  val reference : t -> Pinned_identity.t
end
val adapt_reference_component : ?limits:Codec.limits -> Reference_manifest.t -> Selection.t -> Component.t
