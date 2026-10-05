(** Standalone Verify transport; dependency closure contains no compiler,
    pipeline, callback application service or reconstruction producer. One raw
    archive input is checked against independently supplied request/build and
    complete current metadata authority. The private output FD remains empty. *)
val profile : string
val argument : string
val declaration : Bioc_wire.Json.t
val handle : transport:Bioc_package_io.Package_io.t -> string -> Bioc_wire.Json.t
val run : input:string -> output:string -> unit
