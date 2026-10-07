# Bounded policy realization contracts, v0.1 foundations

This document records the SM-02/03 contract foundations of the
[semantic mRNA plan](semantic-mrna-development-plan.md). The initial implementation
is a closed operating-domain representation and a separately supplied primitive
library and candidate graph. Decoding these representations establishes neither
source preservation nor material acceptance. Native validation and the executable
preservation checker remain separate gates.

The current source assessment and operational execution profiles keep their
existing meanings. In particular, a passing supplied timeline does not establish
all-history requirements, authorize an implementation, or permit RNA export.

## Original authority and trust boundaries

The complete original `BuildRequest`, definition descriptors, operating domain,
implementation catalog bindings, primitive library and eventual material library
are external inputs to realization checking. Candidates cannot replace them.
The identity of the full source artifact includes source maps and provenance;
declaration-content identity is retained separately.

`ImplementationCatalogLock` is allowed to be empty by source assessment. It is
not allowed to authorize a nonempty implementation merely because a separate
model library was provided. A realization binding must resolve an actual original
catalog entry, its exact operation and realization `DefinitionRef`s, and the
independently supplied implementation models. A semantic-definition digest and
a primitive-model digest hash different objects; name equality or equality of
unrelated digest strings cannot substitute for that relation.

The initial source fixtures deliberately retain their empty catalogs. A resolved
request is a new complete input with a new identity, never a silent patch to an
already assessed request. The catalog-binding request envelope and its admission
checker are separate from the structural graph:

| Native boundary | Claim after success |
| --- | --- |
| [`Policy_realization_request.of_json`](../core/lib/domain/policy_realization_request.mli) | Strictly decoded external authority; no candidate embedded |
| [`Policy_realization_admission.admit`](../core/lib/checker/policy_realization_admission.mli) | Fresh source/correspondence, domain compatibility, original catalog membership and supported assurance shape |
| `admitted_inputs` report | Preservation, requirements, target and material unassessed; artifact/export withheld |

The closed request contains schema/profile, document, descriptors, operating
domain, implementation library, catalog bindings and traversal budgets. Its full
identity includes source maps, membership and budgets. Each catalog row pins the
complete original entry, its operation/realization references and a nonempty set
of exact model identities. This first profile requires every supplied library
model and original catalog entry to be accounted for. Realization declarations
are plain model identities; richer clauses and dependency/evidence closures are
explicitly unsupported here. A binding must match the original chassis and RNA
format. These checks do not establish deployment suitability or material carriers.

Initial admission requires bounded assurance, an explicit positive horizon equal
to the domain and each safety/progress requirement horizon, every hard requirement
requested exactly once, and empty assumptions/tolerances. It retains the source
assessment's unresolved obligations. Admission can succeed for a source whose
hard property later fails or is unknown; it cannot issue an accepted artifact.

The trusted base comprises bounded decoders, exact arithmetic, canonicalization,
source semantics, primitive semantics and the explicitly supplied contracts.
Producer output, report labels, occurrence maps and hashes are not behavioral
proofs. The candidate runtime must not import the source evaluator or producer.

## Finite causal operating domain

[`Policy_operating_domain`](../core/lib/domain/policy_operating_domain.mli)
defines a truth-only profile with one exact clock and executor, a finite set of
nominal encounter slots, an inclusive horizon, fixed observations and finite
observation, lifecycle and feedback factors. Compatibility checking against an
operational behavior is distinct from checking that behavior against its original
source and descriptors.

Observation ingress has five cases: known true, known false, missing, invalid and
conflicting. Only known evidence carries a Boolean value. Unknown is an expression
or state value; it is not a sixth valid Boolean measurement. Staleness follows from
observation age and the source freshness contract, including equality at expiry.
Available time and observed time remain distinct. Silence is a real choice, so
expiry, timeouts and deadlines still occur without new observations.

For each active factor, enumerate every ordered batch up to its declared
multiplicity bound, including empty batches. Combine factors by Cartesian product
without merging equal-valued occurrences or changing their order. Lifecycle
reset/end precedes that tick's observations and feedback. A reset creates a new
generation of the same nominal encounter; it cannot reuse an old attempt identity.

Feedback choices depend only on prior source creation events. They include old
attempts after completion, timeout, reset or end, not just currently active
attempts. Newly created attempts become eligible at the next tick. The first
domain schema supports correlated addressing; foreign and wrong-address factors
are explicitly unsupported. Thus exhaustive coverage of this profile is not a
claim about arbitrary malformed feedback. Existing operational negative controls
retain their separate coverage.

The environment cursor accepts caller-supplied source creation records only as
bookkeeping. Those records are not certified observations. The preservation
checker must obtain and validate the complete ordered creation list from the
independently executed source, then couple the candidate through an already fixed
identity correspondence. Candidate outputs must never determine which source
histories are admissible.

Every reachable prefix must have a continuation or a declared end. A source
error or exceeded logical source-output limit on a permitted branch prevents
acceptance; it cannot be pruned from the domain. A candidate error is a failure of
the candidate under that branch. Contradictory domain constraints are rejected.
Finite-value, generation, encounter and attempt limits describe the semantic
domain. Traversal work, retained traces and report-size budgets are separate:
exhausting them leaves exploration incomplete, never passing.

## Independently supplied primitive graph

[`Policy_implementation`](../core/lib/domain/policy_implementation.mli) separates
concrete library model bodies from candidate instances. The initial primitive
set contains truth/product constants, evidence banks, truth operators, registers,
observed rising edges, event selection, activation, arbitration, atomic commit
and correlated attempt banks. It has no opaque source-program executor.

Each model pins its full primitive configuration and replication layout.
Candidate nodes reference those supplied models; they cannot override freshness,
timeouts, capacities, products or initial values. A changed configuration needs
an eligible independently supplied model or a rejection. Graph checks cover
typed ports, complete input ownership, layouts, wires, atomic groups and closed
inventories. Their success is structural evidence only.

Truth signals preserve definedness, true/false/unknown and ordered reason codes.
For example, an unavailable raw observation has no value, while `not(missing)`
has a defined unknown value with the missing reason. Assignment and parameter
preflight must preserve that distinction. Truth operators cannot silently replace
missing evidence with false or discard invalidity reasons.

Replication cannot collapse distinct encounters or generations into shared
mutable state. Registers, evidence, rising history and attempts require the
declared independent storage. Fixed phase semantics must reproduce encounter
lifecycle, evidence update, feedback before equal-deadline timeout, shared-state
reads, atomic writes, arbitration and settled-tick requirement observation.
Candidate-configured phase ordering is not part of this profile.

The structural graph exports a complete node/port inventory. This inventory is
not yet the semantic projection: the preservation checker must independently
derive the externally meaningful mapping from original source and supplied
contracts. A producer cannot hide an additional request or effect by omitting a
port, renaming an output or labeling it internal. Machines and richer source
forms remain unsupported until their complete primitive semantics and binding
are implemented.

## Preservation relation to implement

For every complete admitted input history, compare the independently executed
source with the implementation reconstructed from its actual graph and library.
The first profile requires exact logical-time observable equivalence in both
directions, not one-way trace inclusion. It has zero observable latency tolerance.

The observation map must account for source evidence and named state, encounter
generations, rule/transition initiators, attempt creation and parameters, lifecycle
events, authorization, deadlines and terminal outcomes. It preserves ordering and
multiplicity where source semantics makes them meaningful. Arbitrary producer
debug actions and raw internal microstep counts need not match source debug
actions, but hiding them cannot hide an observable change.

Generated identities may differ only through an injective correspondence fixed
when matching creation events occur. Match declaration, scope, generation,
initiator, causes, parameters, time and ordered occurrence before extending the
map. The extension cannot be revised in response to future feedback. Feed each
later environmental feedback occurrence to the already paired identities.
Missing, additional, reordered or ambiguously paired creations are counterexamples.

Internal settling is allowed only under an independently fixed classification
and a finite bound or ranking argument. Internal steps cannot consume logical
time, create hidden effects or continue indefinitely. A combinational cycle is
not authorized merely because a trace budget eventually stops it.

| Literal distinction | Required checker outcome |
| --- | --- |
| Source requests at tick 1; candidate requests at tick 2 | Reject even if both eventually initiate |
| Two distinct targets have equal Boolean observations | Retain two identities, stores and attempt lineages |
| Missing raw evidence versus defined unknown predicate | Preserve definedness and reasons at every relevant use |
| Feedback arrives exactly at the timeout tick | Apply the specified feedback-before-timeout order |
| Reset followed by late feedback for the prior generation | Preserve old lineage; never complete a new attempt |
| Source creates two equal-valued requests; candidate creates one | Reject lost multiplicity |
| Candidate adds an unrequested effect through another output | Reject extra observable behavior |
| Candidate takes finite silent steps at the same logical time | Allow only under the checked projection and settling bound |
| Candidate never settles | Reject/incomplete according to the verified bound; never PASS |
| Traversal budget stops after matching some histories | Incomplete coverage; no preservation acceptance |

These are acceptance obligations for the upcoming executable checker, not claims
that such checking is already implemented by the two structural modules.

## Requirement and assurance aggregation

Preservation and source requirements are separate: faithfully implementing a
policy that violates a hard property is insufficient for accepted compilation.
Check every original hard requirement, then the exact requested assurance IDs,
strength, horizon, assumptions and tolerances. A bounded proof cannot discharge
an unbounded request. Unsupported assumptions must not be used to prune histories.

The bounded-domain monitor must distinguish a history with no eligible trigger
from uncertain evidence or an unresolved response. The existing per-timeline
UNKNOWN result cannot simply be relabeled PASS. Reconstruct trigger/obligation
coverage, check every eligible response, and retain nonvacuous trigger witnesses
across the complete domain. Safety is sampled at the source profile's settled
tick boundary, with required active/inactive witnesses retained separately.

The original realization witness intentionally includes histories where
`scoped_memory` is unknown before any response. That is a hard-property gap for
those histories. The separate exclusion witness uses two defined registers and
checks `not(all(selected, excluded))`; it does not weaken or replace the original
requirement. Its negative branch does not cancel an already active attempt under
`on_loss=continue`.

## Material and artifact boundary

A checked implementation still requires complete component, configuration,
connection, resource and RNA-member bindings. Every executable value needs a
declared carrier: an encoded feature, template selection, modeled input or supplied
resource checked against deployment. A timer or connection present only in a
manifest is unresolved.

The [complete-mRNA predicate](policy-mrna-completeness-v0.1.md) governs eventual
material acceptance. Source and implementation fixtures contain no sequence
authority and cannot pass that gate. Changes to source, domain, models, bindings,
templates or checker profiles invalidate dependent acceptance. Fresh verification
must bind exact RNA bytes and the full manifest together under original inputs.
