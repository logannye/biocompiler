(** Exact observable comparison for the first exclusive source/graph family.
    This helper never executes a source or candidate and cannot grant bounded
    domain, requirement, material or export acceptance. Its caller must supply
    fresh executions over the same original causal input prefix. *)
open Bioc_wire
module F = Bioc_domain.Policy_operating_domain
module P = Bioc_candidate_runtime.Policy_primitives
module B = Bioc_checker.Policy_implementation_binding_check

val profile : string
val staged_profile : string
val multi_site_profile : string
type t
val create : B.checked_binding -> t

(** Translate only through the correspondence already fixed at earlier matched
    creation events. Old, completed and reset attempts remain addressable.
    This does not alter the source-owned domain or filter its choices. *)
val input : t -> F.input_batch -> P.input_batch

(** Compare all lifecycle events, ordered operational actions, settled evidence,
    scoped state and the complete retained attempt ledger in both directions.
    The initial profile requires exact tick and semantic microstep agreement;
    it has no producer-configurable hiding or latency tolerance. Only source
    requirement-monitor actions are excluded, for separate requirement checks.
    A mismatch leaves the predecessor immutable and raises a diagnostic. *)
val advance : t -> batch:F.input_batch -> source_frame:Json.t ->
  source_attempts:Json.t list -> source_creations:F.source_creation list ->
  candidate:P.frame -> t
val fingerprint : t -> string
val report : t -> Json.t

(** Strict lookups in the already fixed injective correspondence. *)
val candidate_event_to_source : t -> string -> string
val candidate_attempt_to_source : t -> string -> string

(** Compact identity preimage, excluding repeated immutable authority bodies.
    The full checked binding remains covered by its initial history digest. *)
val identity : t -> Json.t
