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

(* Trusted embedding for the closed package application. The resource owner is
   installed by the package channel before hello success. Ordinary [create]
   remains unchanged. A finite extension returns [None] for existing manager
   commands; it cannot replace their checks or import manager state. *)
val create_package : io:Callback_channel.io -> application:Bioc_wire.Json.t ->
  extension:(t -> Callback_channel.t -> Callback_channel.command -> Callback_channel.reply option) -> unit -> t
(* Exact results of real completed façade operations, not new queries. Sequence
   is the actual channel command identity and may complete out of order during
   reentrant callbacks. Same owner, operation arguments and live channel are
   mandatory; stored records or content-equal result imports cannot substitute. *)
val get_return_capability : t -> channel:Callback_channel.t -> manager:Bioc_compiler.Pass_manager.t ->
  sequence:int -> invocation:int -> identity:string -> Bioc_domain.Pipeline_contract.Stage_record.t
val result_return_capability : t -> channel:Callback_channel.t -> manager:Bioc_compiler.Pass_manager.t ->
  sequence:int -> invocation:int -> identity:string -> scope:string -> Bioc_domain.Pipeline_contract.Pipeline_result.t

val manager_capability : t -> channel:Callback_channel.t -> Bioc_compiler.Pass_manager.t
