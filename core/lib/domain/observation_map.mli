(** Structural source-to-model observation bindings. Tuple order and duplicate
    IDs are retained; completeness belongs to the contextual checker/runtime. *)
type field = Value | Present | High | Low
val field_name : field -> string
val resource_profile : string
module Input_binding : sig
  type t
  val make : signal_id:string -> field:field -> mechanism_input_id:string -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val signal_id : t -> string
  val field : t -> field
  val field_name : t -> string
  val mechanism_input_id : t -> string
end
module Output_binding : sig
  type t
  val make : requirement_id:string -> mechanism_output_id:string -> t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val requirement_id : t -> string
  val mechanism_output_id : t -> string
end
type t
val schema_version : string
val make : inputs:Input_binding.t list -> outputs:Output_binding.t list -> t
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val canonical_size : t -> int
val inputs : t -> Input_binding.t list
val outputs : t -> Output_binding.t list
