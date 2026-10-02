module Codec = Bioc_domain.Verification_exploration.Codec
type limits
val make_limits : ?max_work:int -> ?max_items:int -> ?max_input_bytes:int ->
  ?max_report_bytes:int -> ?max_report_nodes:int -> unit -> limits
val default_limits : limits
val limits_json : limits -> Bioc_wire.Json.t
type t
val create : ?parent:Work_budget.t -> limits -> t
val work : t -> Work_budget.t
val settings : t -> limits
val codec : t -> Codec.limits
val charge : t -> int -> unit
val keep : t -> int -> unit
val prepare : t -> (int * Bioc_wire.Json.t) list -> unit
val reserve : t -> Bioc_wire.Json.t -> unit
val fingerprint : t -> Bioc_wire.Json.t -> string
val equal : t -> Bioc_wire.Json.t -> Bioc_wire.Json.t -> bool
val manifests : t -> (string * Bioc_domain.Reference_manifest.t) list -> Bioc_wire.Json.t
val str : string -> Bioc_wire.Json.t
val field : string -> Bioc_wire.Json.t -> Bioc_wire.Json.t
val array : string -> Bioc_wire.Json.t -> Bioc_wire.Json.t list
val text : string -> Bioc_wire.Json.t -> string
val strings : string -> Bioc_wire.Json.t -> string list
val same_set : t -> string list -> string list -> bool
val priority : Bioc_domain.Realization_evidence.outcome list -> Bioc_domain.Realization_evidence.outcome

val manifest : t -> string -> (string * Bioc_domain.Reference_manifest.t) list -> Bioc_domain.Reference_manifest.t option
