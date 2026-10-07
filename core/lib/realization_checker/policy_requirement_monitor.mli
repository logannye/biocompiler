(** Independent candidate-history checks against original requirements. This
    module never calls the source evaluator or reads a source requirement
    verdict. Fresh actual primitive frames and a checked original binding are
    required; imported reports cannot initialize or advance a monitor. *)
open Bioc_wire
module B = Bioc_checker.Policy_implementation_binding_check
module P = Bioc_candidate_runtime.Policy_primitives

val profile : string
type limits = { max_work : int; max_obligations : int; max_samples : int }
type usage = { steps : int; work : int; obligations : int; samples : int }
type t
val create : binding:B.checked_binding -> limits:limits -> t
val usage : t -> usage

(** Consume one consecutive tick. Triggers and responses are checked before
    activation, and responses again after atomic writes using the same ingress
    events. Safety is sampled after settling; deadlines close after responses.
    Reset/end closes pending old-generation obligations as unknown with an
    explicit reason. Failure leaves the predecessor immutable. Resource limits
    raise diagnostics and never supply a successful partial verdict. *)
val step : t -> P.frame -> t

(** Per-requirement statuses are [pass], [fail], [unknown], [not_exercised] and
    [unsupported]. [not_exercised] requires complete horizon coverage and no
    enabled or unknown-enabling trigger; it is distinct from uncertain evidence
    or a pending obligation. Global nonvacuity and whole-domain aggregation are
    explicitly unassessed. *)
val report : t -> Json.t

(** Compact identity preimage. Immutable original authority is pinned by a
    digest computed and charged at creation; current coverage, obligation
    ledger, slots, limits, usage and frame history are included. The caller can
    charge [Canonical.encode (identity t)] before hashing; this function does
    not serialize the original binding report. Report/identity serialization
    is caller-metered and does not mutate [usage]. *)
val identity : t -> Json.t
val fingerprint : t -> string


type verdict = Passed | Failed | Uncertain | Not_exercised | Unsupported_requirement
type requirement_summary = {
  id : string; kind : string; verdict : verdict; horizon_complete : bool;
  samples : int; true_samples : int; false_samples : int; unknown_samples : int;
  active : int; inactive : int; matched_triggers : int; enabled_triggers : int;
  disabled_triggers : int; unknown_enabling : int; passed_obligations : int;
  failed_obligations : int; unknown_obligations : int; pending_obligations : int;
}

(** Typed per-history evidence for separate whole-domain aggregation. Counts
    distinguish no enabling occurrence, an unknown enabling predicate, a pending
    response and an observed failure. None grants whole-domain acceptance. *)
val summaries : t -> requirement_summary list

(** Compatibility projection derived only from actual candidate evidence. The
    row keys match source execution requirement rows; candidate event/attempt IDs
    remain unchanged for an independent fixed correspondence to normalize.
    [not_exercised] becomes [unknown] only in this view. Exact times are decimal
    strings in original clock units. This function imports no source verdict. *)
val source_view : t -> Json.t list
