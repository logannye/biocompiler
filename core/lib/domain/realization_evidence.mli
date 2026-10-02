(** Imported finite-history evidence. Structural consistency and freshness do
    not confer acceptance; only independent execution can establish a new check. *)
val resource_profile : string
val resource_limits : Bioc_wire.Json.t
val claim_scope : string
type outcome = Pass | Fail | Unknown | Unsupported
type evidence_kind = Exact | Model_conditional | Empirical | Unresolved
type expected_state = Active | Inactive

module Dependency_snapshot : sig
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val make_values : Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val changed : t -> t -> string list
end
module Freshness_report : sig
  type t
  val make : string list -> t
  (* Native observation envelope; Python exposes these properties rather than
      a serialized artifact. Supplied order and duplicates are retained. *)
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val changed_dependencies : t -> string list
  val fresh : t -> bool
  val status : t -> string
end
module Check_diagnostic : sig
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val canonical_size : t -> int
  val make : code:string -> message:string -> ?requirement_id:string -> ?node_id:string ->
    ?source:Behavior.source_location -> unit -> t
  val code : t -> string
  val message : t -> string
  val requirement_id : t -> string option
  val node_id : t -> string option
  val source : t -> Behavior.source_location option
end
module Counterexample : sig
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val canonical_size : t -> int
  val make : requirement_id:string -> time:Runtime_number.t -> ?contact_id:string ->
    state:expected_state -> range:Measurement_contract.Interval.t -> ?actual:Runtime_number.t ->
    rule_id:string -> specification_id:string -> ?source:Behavior.source_location -> unit -> t
  val requirement_id : t -> string
  val time : t -> Runtime_number.t
  val contact_id : t -> string option
  val state : t -> expected_state
  val range : t -> Measurement_contract.Interval.t
  val actual : t -> Runtime_number.t option
  val rule_id : t -> string
  val specification_id : t -> string
  val source : t -> Behavior.source_location option
end
module Requirement_coverage : sig
  type t
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  val canonical_size : t -> int
  val make : requirement_id:string -> ?activation_deadlines_checked:Z.t ->
    ?inactive_deadlines_checked:Z.t -> ?incomplete_episode_count:Z.t ->
    ?cancelled_episode_count:Z.t -> unit -> t
  val requirement_id : t -> string
  val activation_deadlines_checked : t -> Z.t
  val inactive_deadlines_checked : t -> Z.t
  val incomplete_episode_count : t -> Z.t
  val cancelled_episode_count : t -> Z.t
end
module Check_result : sig
  type t
  val schema_version : string
  val of_json : ?path:string -> Bioc_wire.Json.t -> t
  val to_json : t -> Bioc_wire.Json.t
  (* Replace already validated historical dependencies, preserving the complete
     validated body and recomputing its bounded inventory. No freshness claim. *)
  val with_dependencies : t -> Dependency_snapshot.t -> t
  (* Python's text serializer: default indent=2; [None] uses spaced separators.
      Fingerprints always use the compact ASCII profile. *)
  val to_json_text : ?indent:int option -> t -> string
  (* Text import retains the wire's 16 MiB request ceiling; records and exported
     text have the separately declared 32 MiB response ceiling. *)
  val of_json_text : string -> t
  val fingerprint : t -> string
  val canonical_size : t -> int
  val make : outcome:outcome -> dependencies:Dependency_snapshot.t -> checked_requirement_ids:string list ->
    ?diagnostics:Check_diagnostic.t list -> ?counterexamples:Counterexample.t list ->
    ?evidence_kind:evidence_kind -> ?claim_scope:string -> ?schema_version:string ->
    ?coverage:Requirement_coverage.t list -> unit -> t
  val outcome : t -> outcome
  val dependencies : t -> Dependency_snapshot.t
  val checked_requirement_ids : t -> string list
  val diagnostics : t -> Check_diagnostic.t list
  val counterexamples : t -> Counterexample.t list
  val coverage : t -> Requirement_coverage.t list
  val passed : t -> bool
  val exercised_requirement_ids : t -> string list
  val freshness : t -> Dependency_snapshot.t -> Freshness_report.t
  val is_fresh : t -> Dependency_snapshot.t -> bool
end
