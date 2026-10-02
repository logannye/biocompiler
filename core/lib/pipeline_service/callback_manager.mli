(** Trusted authoring callbacks over one live native manager. The service never
    imports accepted records; all checks and mutations run on the retained
    [Pass_manager.t]. Host identities only preserve authoring object semantics. *)
val declaration : Bioc_wire.Json.t
type t
val create : io:Callback_channel.io -> unit -> t
val run : t -> unit
val is_closed : t -> bool
