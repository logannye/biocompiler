(** Independent execution of actual supplied primitive graphs. No source AST,
    source evaluator, lowering producer or source-identity map is accepted.
    Structural and runtime admissibility do not establish source preservation,
    hard requirements, material realization or export permission. *)
open Bioc_wire
module I = Bioc_domain.Policy_implementation

val profile : string
val staged_execution_profile : string
val execution_profile : I.t -> string
type reason = Missing | Stale | Invalid | Conflicting
type truth_signal = { value : I.truth option; reasons : reason list }
type binding = { slot : string option; generation : int }
type concrete_slot = { slot_id : string; target : string; start_tick : int }
type environment = { executor : string; slots : concrete_slot list; horizon_ticks : int }
type limits = { max_work : int; max_events : int; max_attempts : int; max_microsteps : int }
(* [max_events] counts all retained event/action/port records and expanded
   nested payload entries. Work includes conservative serialized output costs.
   Each tick also has an independent conservative 8 MiB output ceiling. *)
type evidence = Known of bool | Missing_evidence | Invalid_evidence | Conflicting_evidence
type observation = { observation_id : string; input_id : string; slot_id : string;
  observed_tick : int; observer : string; subject : string; evidence : evidence }
type outcome = Complete | Fail
type feedback = { feedback_id : string; input_id : string; attempt_id : string;
  executor : string; subject : string; slot_id : string; outcome : outcome }
type lifecycle = Reset | End
type input_batch = { tick : int; lifecycle : (string * lifecycle) list;
  observations : observation list; feedback : feedback list }
type event_kind = Primitive_event of I.event_kind | Encounter_started
  | Encounter_reset | Encounter_ended | Attempt_reset | Attempt_ended
type event = { event_id : string; origin : I.endpoint option; kind : event_kind;
  binding : binding; attempt_id : string option; tick : int; microstep : int }
type activation = { gate : string; guard : I.endpoint; binding : binding; causes : string list }
type attempt_status = Active | Completed | Failed | Timed_out | Reset_invalidated | End_invalidated
type attempt = { attempt_id : string; ordinal : int; bank : string; binding : binding;
  executor : string; subject : string; gate : string; guard : I.endpoint;
  causes : string list; product : string; started_tick : int; deadline_tick : int;
  ended_tick : int option; status : attempt_status; authorization : I.truth; machine : string option }
type truth_write = { commit : string; destination : string; binding : binding; value : I.truth }
type request = { commit : string; bank : string; activation : activation; product : string }
type machine_snapshot = { bank : string; binding : binding; state : string; retained_attempts : string list }
type machine_write = { commit : string; destination : string; binding : binding; state : string }
type machine_transition = { bank : string; gate : string; commit : string; binding : binding;
  destination : string; retained_attempts : string list }
type signal = Truth of truth_signal | Product of string | Events of event list
  | Activations of activation list | Writes of truth_write list
  | Requests of request list | Attempts of attempt list
  | Machine of machine_snapshot | Machine_writes of machine_write list
type port_value = { endpoint : I.endpoint; binding : binding; signal : signal }
type evidence_snapshot = { bank : string; binding : binding; signal : truth_signal;
  observed_tick : int option; available_tick : int option; occurrences : string list }
type action_kind = Deferred of activation * reason list
  | Undefined_commit of activation | Suppressed of activation * string
  | Authorization_changed of string * I.truth * reason list * string
  | Feedback_accepted of string * string | Feedback_rejected of string * string * string
  | Observation_batch of { bank : string; binding : binding; input_ids : string list;
      retained_ids : string list; evidence : evidence; observed_tick : int }
  | State_written of truth_write | Effect_requested of attempt | Machine_transition of machine_transition
type action = { microstep : int; detail : action_kind }
type round = { microstep : int; ports : port_value list }
type slot_snapshot = { slot_id : string; generation : int; active : bool }
type frame = { tick : int; rounds : round list; outputs : port_value list;
  events : event list; actions : action list; creations : attempt list;
  attempts : attempt list; evidence : evidence_snapshot list; slots : slot_snapshot list;
  machines : machine_snapshot list; execution_profile : string }
type state
type usage = { work : int; retained : int; allocations : int }

(** Validates the closed runtime shape: direct gate/arbiter/commit
    control, one initiating gate and exact guard channel per attempt bank,
    evidence-only observed edges, and no cross-scope mutable state. A staged
    gate reads the exact machine bank targeted by its transition commit.
    Retained-attempt gates consume explicit outcome selectors. State and
    correlation filters never become the retained source guard; a false or
    Unknown transition guard is silently inactive, as in source execution.
    Machine lineage is replaced by a newly requested batch, preserved when
    no requests start, and cleared on entry to a terminal state. All capacity
    checks precede state/request commits; predecessor states are immutable. *)
val initialize : implementation:I.t -> environment:environment -> limits:limits -> state
val next_tick : state -> int
val usage : state -> usage

(** Requires the next consecutive inclusive tick. A failed step returns no
    partial successor. The predecessor remains usable for independent branches.
    Each bank/slot capacity limits active attempts; allocation and trace/work
    limits are separate and never discard effects or old correlation records.
    Optional positive per-call delta guards only restrict available resources;
    they do not alter the original limits, environment or state identity. *)
val step : ?max_step_work:int -> ?max_step_retained:int -> state -> input_batch -> state * frame
val creations : frame -> attempt list
val frame_to_json : frame -> Json.t
val state_fingerprint : state -> string
