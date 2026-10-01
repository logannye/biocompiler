(** Internal, bounded execution-data records. These preserve Python evaluator
    [to_dict] field shapes and numeric kinds, but introduce a strict native JSON
    import boundary: exact fields, unique map keys and finite bounded content.
    Bounds are the wire response byte limit, JSON depth/node/string/number
    limits, with keys counted as nodes. These apply to raw and normalized data
    and typed constructors. Trace timestamps are nonnegative, source locations
    checked, microsteps positive machine integers, and fingerprints lowercase
    SHA-256. Python's permissive trace constructors do not define this stricter
    native import contract. No schema field is added to Python trace shapes.
    The records establish neither graph correspondence nor successful execution. *)
type number = Behavior.number
type state_value = Behavior.state_value
type source_location = Behavior.source_location

val boundary_version : string

module Sample : sig
  type t
  val make : ?value:number -> ?present:bool -> ?high:bool -> ?low:bool -> unit -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val value : t -> number option
  val present : t -> bool option
  val high : t -> bool option
  val low : t -> bool option
end

module Input_frame : sig
  type t
  val make : time:number -> ?signals:(string * Sample.t) list ->
    ?contacts:(string * (string * Sample.t) list) list -> unit -> t
  (* Exact time/signals/contacts fields. Samples use the full four-field shape;
      a numeric shorthand is additionally normalized to Sample.make ~value. *)
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val time : t -> number
  val signals : t -> (string * Sample.t) list
  val contacts : t -> (string * (string * Sample.t) list) list
end

module Action : sig
  type t
  val make : action_id:string -> rule_id:string -> kind:string ->
    ?contact_id:string -> attributes:Bioc_wire.Json.t -> values:Bioc_wire.Json.t ->
    requirement_ids:string list -> ?source:source_location ->
    ?rule_source:source_location -> ?started_at:number -> ?expires_at:number ->
    ?specification_id:string -> ?specification_source:source_location -> unit -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val action_id : t -> string
  val rule_id : t -> string
  val kind : t -> string
  val contact_id : t -> string option
  val attributes : t -> Bioc_wire.Json.t
  val values : t -> Bioc_wire.Json.t
  val requirement_ids : t -> string list
  val source : t -> source_location option
  val rule_source : t -> source_location option
  val started_at : t -> number option
  val expires_at : t -> number option
  val specification_id : t -> string
  val specification_source : t -> source_location option
end

module Event : sig
  type t
  val make : node_id:string -> ?contact_id:string -> requirement_ids:string list ->
    ?source:source_location -> unit -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val node_id : t -> string
  val contact_id : t -> string option
  val requirement_ids : t -> string list
  val source : t -> source_location option
end

module Frame : sig
  type t
  val make : time:number -> actions:Action.t list -> reactions:Action.t list ->
    events:Event.t list -> states:(string * state_value) list ->
    memories:(string * bool) list -> microsteps:int -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val time : t -> number
  val actions : t -> Action.t list
  val reactions : t -> Action.t list
  val events : t -> Event.t list
  val states : t -> (string * state_value) list
  val memories : t -> (string * bool) list
  val microsteps : t -> int
end

module Result : sig
  type t
  val make : frames:Frame.t list -> role:string -> horizon:number ->
    behavior_fingerprint:string -> source_fingerprint:string ->
    execution_profile:string -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val frames : t -> Frame.t list
  val role : t -> string
  val horizon : t -> number
  val behavior_fingerprint : t -> string
  val source_fingerprint : t -> string
  val execution_profile : t -> string
end
