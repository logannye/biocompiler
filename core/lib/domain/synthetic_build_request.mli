(** Complete portable synthetic build authority. Structural decoding never
    grants pipeline/package acceptance. The producer service uses the explicit
    decoder hook to freshly check realization authority before history/config,
    preserving the original public constructor's error precedence. *)
type t
val schema_version : string
val history_schema_version : string
val of_json : ?limits:Verification_exploration.Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
val decode_with_realization : ?limits:Verification_exploration.Codec.limits -> ?path:string ->
  ?retain_history:(int -> unit) ->
  decode_realization:(path:string -> Bioc_wire.Json.t -> Realization_request.t) -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val canonical_size : t -> int
val realization : t -> Realization_request.t
val history : t -> Execution_data.Input_frame.t list
val until : t -> Runtime_number.t
val config : t -> Synthetic_authority.Config.t
val profile : t -> string
