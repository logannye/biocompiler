(** Complete historical Boolean campaign and selected-failure records. Their
    structural invariants do not confer fresh acceptance or minimality. *)
module Codec : sig
  type limits
  type size = { bytes:int; nodes:int }
  val make_limits : ?max_bytes:int -> ?max_nodes:int -> ?charge:(int -> unit) -> unit -> limits
  val default_limits : limits
  val limits_json : limits -> Bioc_wire.Json.t
  val charge : limits -> int -> unit
  val measure : ?limits:limits -> ?path:string -> Bioc_wire.Json.t -> size
  val preflight : ?limits:limits -> ?path:string -> Bioc_wire.Json.t -> unit
  val encode : ?limits:limits -> Bioc_wire.Json.t -> string
  val fingerprint : ?limits:limits -> Bioc_wire.Json.t -> string
end
type number = Runtime_number.t
type frame = Execution_data.Input_frame.t
type check = Realization_evidence.Check_result.t
val exploration_version : string
val input_exploration_version : string
val claim_scope : string
val input_claim_scope : string
val frames_of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> frame list
val history_json : frame list -> Bioc_wire.Json.t
val history_fingerprint : ?limits:Codec.limits -> frame list -> string
val validate_history : ?limits:Codec.limits -> ?initial:bool -> frame list -> number -> unit
val stable_dependencies : check -> Bioc_wire.Json.t
val validate_result : ?limits:Codec.limits -> ?stable:Bioc_wire.Json.t -> check -> frame list -> number -> unit
module Observation : sig
  type t
  val schema_version : string
  val make : ?limits:Codec.limits -> signal_id:string -> ?field:string -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val signal_id : t -> string
  val field : t -> string
end
module Bounds : sig
  type kind = Contact | Mixed
  type t
  val make : ?limits:Codec.limits -> kind:kind -> contact_ids:string list -> observations:Observation.t list ->
    variable_times:number list -> until:number -> ?fixed_suffix:frame list -> ?max_histories:int ->
    ?cell_observations:Observation.t list -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val contact_of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val input_of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val kind : t -> kind
  val contact_ids : t -> string list
  val observations : t -> Observation.t list
  val cell_observations : t -> Observation.t list
  val variable_times : t -> number list
  val until : t -> number
  val fixed_suffix : t -> frame list
  val max_histories : t -> int
  val state_count : t -> Z.t
  val possible_histories : t -> Z.t
  val snapshot : ?limits:Codec.limits -> t -> time:number -> code:Z.t -> frame
  val history_at : ?limits:Codec.limits -> t -> Z.t -> frame list
end
module Report : sig
  type t
  val make : ?limits:Codec.limits -> kind:Bounds.kind -> config:Bounds.t -> results:check list ->
    ?explorer_version:string -> ?claim_scope:string -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val contact_of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val input_of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val kind : t -> Bounds.kind
  val config : t -> Bounds.t
  val results : t -> check list
  val explorer_version : t -> string
  val claim_scope : t -> string
  val state_count : t -> Z.t
  val possible_histories : t -> Z.t
  val evaluated_histories : t -> int
  val complete : t -> bool
  val all_passed : t -> bool
  val outcome_counts : t -> (Realization_evidence.outcome * int) list
  val coverage_totals : t -> Realization_evidence.Requirement_coverage.t list
  val shared_dependencies : t -> Bioc_wire.Json.t
end
module Failure_signature : sig
  type kind = Response | Diagnostic
  type t
  val schema_version : string
  val make : ?limits:Codec.limits -> kind:kind -> ?requirement_id:string -> ?code:string ->
    ?rule_id:string -> ?specification_id:string -> ?contact_id:string -> ?state:string -> ?node_id:string -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val kind : t -> kind
  val requirement_id : t -> string option
  val code : t -> string option
  val rule_id : t -> string option
  val specification_id : t -> string option
  val contact_id : t -> string option
  val state : t -> string option
  val node_id : t -> string option
  val from_counterexample : ?limits:Codec.limits -> Realization_evidence.Counterexample.t -> t
  val from_diagnostic : ?limits:Codec.limits -> Realization_evidence.Check_diagnostic.t -> t
  val matches : ?limits:Codec.limits -> t -> check -> bool
end
module Reduction : sig
  type t
  val schema_version : string
  val make : ?limits:Codec.limits -> original_history:frame list -> history:frame list -> until:number ->
    signature:Failure_signature.t -> original_result:check -> result:check -> evaluations:int ->
    one_minimal:bool -> ?reducer_version:string -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val original_history : t -> frame list
  val history : t -> frame list
  val until : t -> number
  val signature : t -> Failure_signature.t
  val original_result : t -> check
  val result : t -> check
  val evaluations : t -> int
  val one_minimal : t -> bool
  val reducer_version : t -> string
end
module Adversarial_config : sig
  type t
  val schema_version : string
  val make : ?limits:Codec.limits -> bounds:Bounds.t -> seed:Z.t -> ?random_cases:int -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val bounds : t -> Bounds.t
  val seed : t -> Z.t
  val random_cases : t -> int
end
module History_case : sig
  type t
  val schema_version : string
  val make : ?limits:Codec.limits -> id:string -> kind:string -> history:frame list -> until:number ->
    config_fingerprint:string -> ?intentionally_incomplete:bool -> unit -> t
  val of_json : ?limits:Codec.limits -> ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val id : t -> string
  val kind : t -> string
  val history : t -> frame list
  val until : t -> number
  val config_fingerprint : t -> string
  val intentionally_incomplete : t -> bool
end
