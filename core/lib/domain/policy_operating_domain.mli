(** Closed finite environment inputs. Decoding and [validate_for] establish no
    independent source acceptance, preservation proof or requirement verdict.
    This module imports neither a source evaluator nor a candidate runtime. *)
open Bioc_wire

val schema_version : string
val profile : string

type evidence = Known of bool | Missing | Invalid | Conflicting
type outcome = Completed | Failed
type lifecycle_action = Keep | Reset | End
type context = Executor | Encounter_slot of string
type encounter = {
  identity : string; declaration : string; target : string; start_tick : int;
}
type observation_input = {
  slot : string; observation : string; available_tick : int;
  observed_tick : int; evidence : evidence;
}
type observation_factor = {
  slots : string list; observation : string; ticks : int list;
  age_ticks : int list; max_rows_per_slot_tick : int;
}
type lifecycle_factor = {
  slots : string list; ticks : int list; actions : lifecycle_action list;
}
type feedback_factor = {
  effect_id : string; ticks : int list; outcomes : outcome list;
  max_rows_per_attempt_tick : int;
}
type logical_limits = {
  max_live_encounters : int; max_generations_per_slot : int;
  max_source_attempts : int;
}
type t = private {
  raw : Json.t; clock : string; executor_role : string; executor_identity : string;
  horizon_ticks : int; encounters : encounter list;
  fixed_observations : observation_input list;
  observation_factors : observation_factor list;
  lifecycle_factors : lifecycle_factor list;
  feedback_factors : feedback_factor list;
  logical_limits : logical_limits;
}
type validated

val of_json : Json.t -> t
val to_json : t -> Json.t
val digest : t -> string

(** Compatibility with the supplied behavior only. The caller must separately
    establish its external source/descriptor correspondence. Initial values and
    finite machine states remain those of that original source. *)
val validate_for : ?charge:(int -> unit) -> behavior:Policy_operational.behavior -> t -> validated
val specification : validated -> t
val resolution : validated -> Q.t

type attempt_key = {
  context : context; generation : int; effect_id : string;
  (** One-based global source creation order across all effects and slots. *)
  creation_ordinal : int;
}
type source_creation = {
  key : attempt_key; source_attempt_id : string; created_tick : int;
}
type feedback_input = { attempt : source_creation; outcome : outcome }
type input_batch = private {
  tick : int;
  lifecycle : (string * lifecycle_action) list;
  observations : observation_input list;
  feedback : feedback_input list;
  origin : string;
}
type cursor

val initial : validated -> cursor
val cursor_tick : cursor -> int
val finished : validated -> cursor -> bool

(** Lazy exhaustive choices for this prefix. Every factor combines by Cartesian
    product, including silence. No candidate state or requirement result enters
    choice eligibility. Observation batches enumerate all ordered rows up to
    their multiplicity bound. Staleness is derived by the source from age;
    [Known Unknown] and externally asserted stale evidence do not exist here.

    The declared causal grammar permits sample ages only within the slot's
    current generation, and reset only while the declared generation count can
    increase. Ended slots have only keep/no-observation choices. These rules are
    structural input eligibility, applied before execution; they never discard
    a history because of a source/candidate verdict. A fixed observation that
    conflicts with a permitted end/reset prefix instead raises a contradiction.

    Lifecycle reset/end precedes observations and feedback. Feedback ranges over
    ALL previously created attempts, including attempts already ended/reset or
    completed; it never filters for active attempts. Current-tick creations are
    visible only to subsequent ticks. Wrong/foreign addressing is unsupported.

    The caller must bound traversal/work separately. A stopped sequence is not
    complete exploration. Logical limits never stand in for such a budget. *)
val choices : validated -> cursor -> input_batch Seq.t

(** Supply the complete ordered list of freshly observed source creations for
    this tick. This function checks identity, generation and finite bounds; it
    does not prove that the source emitted the supplied records. Exceeding a
    source-output bound raises a diagnostic and must not prune an input branch.
    Candidate outputs must never be supplied to this environment cursor. *)
val advance :
  validated -> cursor -> input_batch ->
  source_creations:source_creation list -> cursor

(** Exact identities for retained enumeration receipts, not proof certificates. *)
val batch_to_json : input_batch -> Json.t
val cursor_digest : cursor -> string
