# Independent policy primitive execution and exact prefix correspondence

This is the source specification for SM-03 and the first SM-04 bridge. Hosted
validation is required. None of these interfaces establishes complete-domain
preservation, hard-requirement satisfaction, material correspondence or export.

## Independent execution

`Policy_primitives` belongs to `bioc_candidate_runtime`. Its link boundary
contains only wire/domain primitives and exact arithmetic. It takes the actual
decoded implementation graph, concrete ordered encounter slots and explicit
resource limits. It accepts no source AST, source evaluator, expected trace,
producer callback or source identity map.

The runtime reconstructs constants, evidence banks, truth gates/registers,
observed-edge memory, activation, arbitration, atomic commits and attempt banks
from supplied model identities, configurations and wires. Mutable/control nodes
are replicated by distinct encounter slot and generation. Original attempt
identities remain allocated after completion, timeout, reset or end so delayed
feedback can still be rejected against the correct old attempt.

Each consecutive inclusive tick applies encounter lifecycle changes, ordered
observation batches, correlated feedback, equal-deadline timeouts, continuous
authorization and observed rising edges. Feedback precedes timeout. Rising
history refreshes once per tick. Atomic settling reads a common pre-state,
prepares all selected writes and requests, preflights capacity, and commits the
batch. A request event is created before its initiation event, explicitly
sequenced rather than relying on host-language list evaluation order.

Unavailable raw evidence differs from a defined three-valued `Unknown`.
Predicate operations retain ordered uncertainty reasons. An unavailable
assignment defers the complete activation; writing a defined truth clears
evidence provenance from the stored value. Continuous authorization changes do
not invent cancellation or cessation.

All primitive outputs, phase-tagged actions, actual events, settled evidence,
scoped state and retained attempts are inspectable. The finite runtime rejects
unsupported control paths and scope sharing. Active bank capacity, cumulative
allocation, work, retained output and same-tick settling are separate limits.
Exceeding any limit returns no partial successor. Immutable predecessors support
independent exploration branches. Expanded signal payloads are charged, including
duplicated reason/cause lists, and tick serialization has a fixed finite cap.

## Source replay and graph binding

`Policy_domain_reference` transports the domain's causal batches into the
existing source evaluator. It replays each complete prefix, checks earlier
frames and immutable attempt metadata, and advances the domain using only
actual new source creations. Every silent tick remains executable. Failed,
ended and reset attempts remain in the feedback alphabet. Source violations,
executor exhaustion and source errors are distinct outcomes, with the permitted
input and any completed execution retained.

Replay accounting distinguishes reserved capacity from consumed work. Successful
calls charge their full reported work; an unreported failure consumes its full
reservation. Tree traversal must sum per-call deltas, including repeated replay
of prior source prefixes. A caller cannot count only the final frame or treat a
stopped branch as explored.

`Policy_implementation_binding_check` reconstructs the initial one/two-rule
exclusive family against full original admitted request authority. It walks
source expressions through actual endpoints, checks exact typed model
configuration and catalog membership, and accounts for every node, wire, input,
atomic group and source occurrence. Anchors merely propose locations. Source
labels and occurrence maps never define candidate behavior. Nondefault or
unsupported source fields reject explicitly. Requirements remain obligations.

The initial family has one executor, one encounter declaration replicated over
the declared slots, one truth observation, one product effect, one or two truth
stores, and evidence-rising rules with one effect initiator. Machines, predicate
resets, additional mutable scopes and requirement-only edge memory require later
profiles. The independently checked result is named `source_graph_bound`.

## Fixed observable comparison

`Policy_trace_correspondence` fixes an injective attempt/event correspondence at
matching creation events. It translates subsequent feedback only through that
existing map, including feedback for old generations. It retains the original
source-owned domain cursor; a batch from a different domain or prefix is invalid.
Candidate behavior never determines which source inputs are eligible.

The initial exact profile compares event kind, declaration, order, multiplicity,
timestamp, semantic microstep, binding and attempt correlation; ordered
operational actions; settled scoped state and evidence with uncertainty reasons;
and every retained attempt's origin, guard, parameters, causes, identity,
authorization, deadline and lifecycle. Creation records must agree with the
immutable portion of their retained ledger. Encounter activity and generations
are checked against the original input lifecycle. Extra and missing observables
both reject. Pure intermediate port values are fixed runtime internals, not a
producer-selectable hiding scheme.

This first profile requires exact semantic microstep correspondence. It has no
latency tolerance or stuttering relaxation. A later implementation that inserts
additional internal steps needs a separately defined and checked projection.
Source requirement-monitor bookkeeping is excluded from operational actions and
must be checked by the separate requirement-monitor stage. It cannot be silently
promoted to PASS by a matching operational trace.

Receipts bind the complete checked source/graph authority and a cumulative digest
of the actual batches and both executed traces. Their claim is only
`matched_prefix_only`. Requirements, whole-domain coverage and material remain
unassessed; export remains withheld. Fresh full-domain execution is still needed
before this becomes an accepted implementation bridge.

## Controls

Native tests use independently frozen one-rule and exclusion graphs, literal
primitive histories, original source replay and altered candidate outputs. They
cover uncertainty, silent expiry, target isolation, repeated/stale feedback,
feedback/deadline precedence, reset/end, priority suppression ordering, undefined
atomic operands, capacity, resource exhaustion and immutable branching. Trace
mutations target omitted/extra/reordered events, wrong identities, parameters,
guards, times, state, evidence, creation metadata and attempt ordinals.

Static dependency checks enforce that the runtime cannot link the source
evaluator or producer. Static checks are not native execution or release
acceptance. Full hosted native and installed gates retain their existing scope.
