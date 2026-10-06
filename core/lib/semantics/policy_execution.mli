(** A bounded language reference for admitted rich policy IR. This evaluator is
    not an implementation, molecular model, realization checker, or evidence of
    biological activity. Callers must independently check correspondence against
    the external source before passing a candidate here. *)
val schema_version : string
val timeline_profile : string

(** Exact finite decimal serialization used by source timeline adapters. No
    floating-point conversion or rounding; the caller supplies nonnegative
    time. The existing bounded representation failure remains explicit. *)
val time_json : Q.t -> Bioc_wire.Json.t

(** Execute a closed timeline. All time strings are exact nonnegative decimals
    in base units and must align with the single source clock. The full closed
    timeline has fields [profile, executor, horizon, encounters, observations,
    feedback, bounds]. Concrete executor and encounter IDs are separate from
    declaration IDs. Every input occurrence ID is unique across both input
    arrays. Bounds explicitly include [max_ticks, max_inputs, max_encounters,
    max_attempts, max_work, max_trace_items, max_microsteps].

    Encounter records: [id, declaration, target, start, end, resets]. Observation
    records: [id, available_at, observed_at, observer, subject, encounter,
    observation, status, value]. Status is [valid], [missing], [invalid] or
    [conflicting]; only [valid] carries a non-null, well-typed value. Feedback
    records: [id, available_at, executor, subject, encounter, effect, attempt,
    outcome], with [completed] or [failed]. Encounter is nullable for executor
    scope. An encounter has a unique concrete ID throughout the entire run;
    resetting increments its generation rather than reusing attempt identities.

    At a tick: terminate/reset encounters; atomically apply available evidence;
    accept correlated feedback; apply timeouts; settle events with atomic state
    writes and explicit arbitration; then close requirement deadlines. Feedback
    and responses at their deadline are accepted. Freshness is stale at equality.
    Rising requires an observed false-to-true edge; missing-to-true is no edge.
    The tick scheduler visits silent ticks, including expiry and deadlines.
    All failures raise [Bioc_wire.Diagnostic.Error] with no partial acceptance.
    Resource exhaustion is an error, not a failed requirement or infeasibility. *)
val execute : Bioc_domain.Policy_operational.behavior -> Bioc_wire.Json.t -> Bioc_wire.Json.t
