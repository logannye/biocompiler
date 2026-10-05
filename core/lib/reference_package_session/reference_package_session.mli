(** Closed package operations on one explicitly configured package channel.
    Host callbacks preserve public lookup/read order. They can supply declarations
    and observations but cannot import acceptance. Every retained build/get/result
    is resolved through the same live callback manager's native capability table. *)
module Ch = Bioc_pipeline_service.Callback_channel
val profile : string
val declaration : Bioc_wire.Json.t
val create : io:Ch.io -> files:Bioc_package_io.Package_io.t -> unit -> Bioc_pipeline_service.Callback_manager.t

val run : input:string -> output:string -> unit
