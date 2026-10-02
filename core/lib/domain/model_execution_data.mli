(** Candidate-specific immutable snapshots and historical traces. These records
    neither execute the source reference model nor certify graph correspondence.
    Imports and constructors are bounded: input/frame records use 16 MiB and
    traces 32 MiB; wire value-node, depth, string and integer ceilings apply. *)
type number = Runtime_number.t
type value = Boolean of bool | Number of number
val boundary_version : string
val value_of_json : ?path:string -> Bioc_wire.Json.t -> value
val value_to_json : value -> Bioc_wire.Json.t

module Input_frame : sig
  type t
  val make : time:number -> ?values:(string * value) list ->
    ?contacts:(string * (string * value) list) list -> unit -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val canonical_size : t -> int
  val time : t -> number
  val values : t -> (string * value) list
  val contacts : t -> (string * (string * value) list) list
end
module Frame : sig
  type t
  val make : time:number -> ?values:(string * value) list ->
    ?contacts:(string * (string * value) list) list -> unit -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val canonical_size : t -> int
  val time : t -> number
  val values : t -> (string * value) list
  val contacts : t -> (string * (string * value) list) list
end
module Trace : sig
  type t
  val schema_version : string
  val model_version : string
  val make : frames:Frame.t list -> horizon:number -> program_fingerprint:string ->
    ?model_version:string -> unit -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val frames : t -> Frame.t list
  val horizon : t -> number
  val program_fingerprint : t -> string
end
