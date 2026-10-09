# Bounded finite-machine policy realization v0.1

The finite-machine family translates a supplied encounter-scoped policy machine
into the existing exact primitive graph, checks source correspondence
independently, and can continue through prerequisite-closed component material
realization. It permits branches and retry cycles within explicit source and
resource bounds. It does not infer molecular mechanisms or prove termination,
unbounded correctness, biological function, or therapeutic efficacy.

## Explicit profile selection

The complete original realization request uses
`biocompiler.policy_realization_request.v0.5` with profile
`biocompiler.policy_finite_machine_inputs.v0.1`. Its fields remain the original
document, descriptors, operating domain, implementation library, catalog
bindings and exploration budgets. The domain constructor is
`Policy_realization_request.of_finite_machine_json`; the legacy constructor
continues to reject this profile. `requires_prerequisite_closure` is true.

The proposed source/graph binding uses
`biocompiler.policy_implementation_binding.v0.5` with profile
`biocompiler.policy_finite_machine_source_graph.v0.1`. It retains the existing
observation, effect, machine and transition anchor fields; independent rules and
stores are empty. Request and binding families must agree. Names and anchors
remain untrusted until independently reconstructed against the complete source
and actual graph.

The primitive library, graph and observable schemas retain their existing staged
profiles, `biocompiler.policy_staged_primitives.v0.1` and
`biocompiler.policy_staged_observables.v0.1`. No new primitive semantics are
introduced. The old staged binding continues to require the original five-state,
seven-transition, two-effect topology with two terminal states. Its schema,
profile and producer output are unchanged; a generic topology requires the new
explicit profile.

## Source and graph bounds

| Item | Supported finite-machine source |
| --- | --- |
| Machine | Exactly one, with 2–16 finite state labels |
| Transitions | 1–32, all belonging to that machine |
| Effects | 1–8, each with exactly one initiating transition |
| Transition actions | At most one effect request, no state assignments |
| Independent stores/rules | None |
| Parameters | One original fixed text product, used by every effect |
| Observation | One truth observation, event coverage, frame coherence |
| Ownership | One executor, one encounter subject and declaration, two distinct operating-domain encounter slots |
| Clock | One original logical/availability clock, atomic batches |
| Machine lifetime | Encounter-scoped, exclusive arbitration, rejected conflicts, no terminal-state outgoing transitions |
| Actual graph | At most 64 selected primitive nodes; existing wire, occurrence, codec and exploration limits also apply |

These bounds are conjunctive. A source with 32 transitions will not necessarily
fit the graph: every transition needs both a gate and commit, in addition to
evidence, machine, arbiter, attempt and expression nodes. Graph capacity, supplied
model availability, material instance limits and exploration budgets can reject
a source below its nominal state/transition ceiling.

Each effect must retain the original executor, subject and catalog operation.
Its sole `product` argument must refer to the original fixed product parameter.
Each lifecycle needs an explicit finite timeout, exact supported authorization
behavior and `on_loss="continue"`. Duration-to-clock conversion must produce a
positive integer of at most 10,000 ticks. The profile supplies no automatic stop
or cancellation implementation.

## Events, branches and retries

Transition triggers are a rising edge of a truth expression containing the
original observation, an explicit update event from that observation, or a
correlated `completed`, `failed` or `timed_out` event from an original effect.
Observation updates use the existing evidence bank event output and require the
exact original observation and subject identity. An update can carry unknown
truth; that sample event does not override a guard that defers on unknown. Observation predicates support truth literals,
negation, conjunction and disjunction. The original staged profiles retain their
previous trigger subset; `updated` is enabled only by the finite-machine family.
Arbitrary event phases, quantitative predicates and temporal expression operators are not added by this
profile. Unsupported expressions produce explicit diagnostics.

A transition gate reads the current source state, event and guard. Exclusive
arbitration connects one lane per original transition to its commit. There is no
implicit priority between competing branches. Existing source admission retains
explicit unknown handling (`defer`) and arbitration restrictions; missing or
unknown evidence does not become true.

The machine retains attempt identities per encounter. A transition starting a
new effect replaces that retained attempt; a nonterminal transition without a
request retains it; entering a terminal state clears it. Effect-event gates
require that retained attempt, so feedback from an older attempt cannot advance
a later retry. The existing runtime separately checks executor, subject,
encounter, effect and attempt identity. Merely returning to a same-named state
does not make stale feedback current.

Because each transition starts at most one effect, one retained-attempt slot is
sufficient. The producer derives this requirement from source request counts and
selects a supplied machine model with enough capacity. Attempt-bank capacity and
finite exploration budgets remain independently bounded. Retry cycles can
continue beyond a tested horizon; bounded exploration is not a universal
termination claim.

## Producer and independent reconstruction

The producer derives the ordered state alphabet, initial and terminal states,
transition writer count, arbiter lane count, effect banks, event selectors,
atomic commits and source occurrences from the actual admitted source. It
selects exact permitted primitive configurations from the independently supplied
library and catalog bridge. Missing configurations are diagnosed rather than
invented. Lowering a finite request with no required machine cannot fall back to
the unrelated rule profile.

The independent binding checker reconstructs source expressions, transition
topology, event correlation, input mappings, model identities, ports, wires,
atomic groups and the complete occurrence inventory from original authority.
It does not import the producer. Changing state labels, a destination, an effect
reference, feedback phase, lane, fixed product, source requirement or supplied
model requires fresh checking. Extra, omitted and misbound source occurrences
do not inherit acceptance from a binding label.

All requirements remain original obligations, including unsupported or
unresolved ones. Correspondence establishes a source/graph relationship under
the supplied primitive semantics; execution, bounded preservation and
requirement assessment remain separate checks. Work and publication accounting
use the existing bounded resource mechanisms, including charges for attempted
layouts and failed construction.

## Component material route

The component material request is
`biocompiler.policy_component_material_request.v0.7` with profile
`biocompiler.policy_finite_machine_component_mrna.v0.1`. Its original realization
request and component context must explicitly select the same finite-machine
family. It uses the existing staged instance composition machinery for one
original product, not the separate multi-product/multi-member family.

Supplied component libraries, instance bindings, composition rules, recipient
context, exact RNA material and original catalog prerequisites remain
independent authority. Prerequisites must close before accepted material or
export; the new graph topology cannot waive missing dependencies. The route
checks the actual selected primitive graph and complete material composition,
with fresh verification before export. A supplied artificial component fixture
provides software evidence only. Exact material identity and conditional
translation checks do not establish that a molecular system realizes these
semantics in human immune cells.

Native compilation and execution validation run on hosted infrastructure under
the workspace development protocol. Source review and pure Python fixture
construction alone do not validate the OCaml implementation or transfer
acceptance from earlier staged-profile revisions.
