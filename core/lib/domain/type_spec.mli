type kind = Scalar | Condition | Event | Interval | Curve
type t
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val kind : t -> kind
val compatible : t -> t -> bool
val validate_binding : ?path:string -> expected:t -> Bioc_wire.Json.t -> unit
(* Reconstruct Python decode_binding(...).to_dict() after the same complete
   validation. This normalizes the binding's actual type, not its compatible
   expected type, and recomputes registered unit conversions. *)
val normalize_binding : ?path:string -> expected:t -> Bioc_wire.Json.t -> Bioc_wire.Json.t
