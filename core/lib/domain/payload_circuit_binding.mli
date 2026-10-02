(** Supplied legacy Boolean circuit correspondence. Import preserves declarations;
    it does not establish source correspondence or discharge implementation duties. *)
type t
val schema_version : string
val max_signals : int
val make : requirement_id:string -> rule_id:string -> action_id:string -> signals:(string * string) list -> t
val of_json : ?path:string -> Bioc_wire.Json.t -> t
val to_json : t -> Bioc_wire.Json.t
val fingerprint : t -> string
val requirement_id : t -> string
val rule_id : t -> string
val action_id : t -> string
val signals : t -> (string * string) list
