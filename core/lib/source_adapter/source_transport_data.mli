(** Bounded source-transport inputs and historical results. These codecs preserve
    complete Python trace fields; import does not establish fresh correspondence
    or candidate execution. Native structural boundaries are explicitly versioned. *)
val boundary_version : string
val transport_profile : string
val policies : max_samples:int -> Bioc_wire.Json.t
module Input : sig
  type t
  val make : histories:(string * Bioc_domain.Execution_data.Input_frame.t list) list ->
    until:Bioc_wire.Json.t -> step:Bioc_wire.Json.t -> ?max_samples:Bioc_wire.Json.t ->
    ?failed_channels:(string * Bioc_wire.Json.t list) list -> unit -> t
  val of_json : Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val histories : t -> (string * Bioc_domain.Execution_data.Input_frame.t list) list
  val until : t -> Bioc_wire.Json.t
  val step : t -> Bioc_wire.Json.t
  val max_samples : t -> Bioc_wire.Json.t
  val failed_channels : t -> (string * Bioc_wire.Json.t list) list
end
module Channel_frame : sig
  type sent = { value : Bioc_domain.Runtime_number.t; delivery_time : Z.t }
  type t
  val make : time:Z.t -> receiver_values:(string * Bioc_domain.Runtime_number.t) list ->
    sent:(string * sent) list -> failed_channel_ids:string list -> t
  val of_json : Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val time : t -> Z.t
  val receiver_values : t -> (string * Bioc_domain.Runtime_number.t) list
  val sent : t -> (string * sent) list
  val failed_channel_ids : t -> string list
end
module Result : sig
  type t
  val make : request_fingerprint:string -> build_fingerprint:string -> step_seconds:Z.t ->
    horizon_seconds:Z.t -> histories:(string * Bioc_domain.Execution_data.Input_frame.t list) list ->
    results:(string * Bioc_domain.Execution_data.Result.t) list -> channel_frames:Channel_frame.t list ->
    channels:Bioc_domain.Architecture_contract.Channel.t list -> failed_channels:(string * Z.t list) list ->
    assumptions:string list -> max_samples:int -> t
  val of_json : Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val histories : t -> (string * Bioc_domain.Execution_data.Input_frame.t list) list
  val results : t -> (string * Bioc_domain.Execution_data.Result.t) list
  val channel_frames : t -> Channel_frame.t list
end
