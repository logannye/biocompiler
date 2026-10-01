type kind = Scalar | Condition | Event | Interval | Curve
type t
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val kind : t -> kind
val compatible : t -> t -> bool
val validate_binding : ?path:string -> expected:t -> Bioc_wire.Json.t -> unit
