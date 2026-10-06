(** Transport from a causal finite input domain to the existing source evaluator.
    This module does not evaluate policy expressions or grant source admission,
    preservation, requirement acceptance or export authority. *)
open Bioc_wire
module F = Bioc_domain.Policy_operating_domain

val profile : string
type execution_bounds

(** Closed positive integer bounds, with the adapter's explicit v0.1 finite
    caps. No defaults are supplied. This is adapter preflight, not a shared
    decoder: [Policy_execution.execute] remains authoritative on every replay. *)
val execution_bounds_of_json : Json.t -> execution_bounds
val execution_bounds_to_json : execution_bounds -> Json.t

type accounting = {
  replay_calls : Z.t;
  reserved_work : Z.t;
  charged_work : Z.t;
  reported_work : Z.t;
  reported_trace_items : Z.t;
  unreported_calls : Z.t;
  timeline_bytes : Z.t;
}
type t

(** The caller must first check the behavior against the original external
    source and descriptors. Creation checks domain compatibility only. The
    domain, behavior and explicit bounds remain fixed for this entire state
    tree. The executor attempt ceiling must exceed the logical source-attempt
    bound, so a permitted input can expose a violation instead of being pruned. *)
val create :
  behavior:Bioc_domain.Policy_operational.behavior ->
  domain:F.t -> bounds:execution_bounds -> t
val choices : t -> F.input_batch Seq.t
val finished : t -> bool
val cursor_digest : t -> string
val accounting : t -> accounting

(** Reserve this much evaluator work before calling [step]. An explorer must
    also bound its own enumeration, serialization and retained memory. *)
val next_work_reservation : t -> Z.t

type receipt = {
  timeline : Json.t;
  execution : Json.t option;
  delta : accounting;
  cumulative : accounting;
}
type failure_kind = Source_bound | Exhausted | Source_error
type failure = {
  kind : failure_kind;
  diagnostic : Diagnostic.t;
  receipt : receipt;
}
type advanced = {
  next : t;
  receipt : receipt;
  frame : Json.t;
  creations : F.source_creation list;
}
type outcome = Advanced of advanced | Stopped of failure

(** Replay the complete closed prefix through [Policy_execution.execute]. All
    earlier frames and immutable attempt metadata must remain identical.
    Only freshly observed source creations advance the environment cursor;
    candidate outputs are never accepted here. Input occurrence IDs are stable
    ordered transport IDs; source declaration, event and attempt IDs are kept.

    [Stopped] retains the permitted input and any complete execution report. It
    never supplies a continuation obtained by dropping the offending branch.
    [reserved_work] is the sum of historical per-call reservations, not the
    consumed exploration budget. [charged_work] sums reported work on success
    and the full ceiling for each unreported failed call. Neither the failed
    charge nor the reservation claims measured actual work. An explorer checks
    remaining capacity against the reservation before each call, then consumes
    that call's charge; unused successful reservation may be released.
    Sum [delta], not path [cumulative], when traversing a branching tree.
    Cursor mismatch/internal prefix inconsistency raises a diagnostic. A lazy
    [choices] contradiction also prevents complete-domain acceptance and must
    never be caught merely to skip that branch. *)
val step : t -> F.input_batch -> outcome
