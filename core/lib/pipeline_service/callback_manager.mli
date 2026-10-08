(** Trusted authoring callbacks over one live native manager. The service never
    imports accepted records; all checks and mutations run on the retained
    [Pass_manager.t]. Host identities only preserve authoring object semantics.
    Expected rejections contain canonical attributes and a fresh, ordered tree
    of those same attributes. Error publication uses the session's lifetime
    budget; failure to construct an error closes the channel. *)
val declaration : Bioc_wire.Json.t
type t
val create : io:Callback_channel.io -> unit -> t
val run : t -> unit
val is_closed : t -> bool

(* Read-only exact historical native Build capability for same-channel package
   extensions. No parsing, replay, latest-kind lookup or fresh manager query. *)
val molecular_build_capability : t -> channel:Callback_channel.t -> build_id:string ->
  Bioc_pipeline.Reference_molecular_pipeline.t
