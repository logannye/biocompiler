# Supplied RNA architecture compilation v0.1

Implemented in package `0.1.0.dev29`. The product invariant is **therapeutic
program design → corresponding exact RNA payload specifications for human immune
cells engineered in vivo**. This profile checks translation under explicit,
independently supplied executable and material contracts. Biological evidence is
not a prerequisite for those software checks. Whether a supplied RNA fulfills its
declared contract in a human cell remains a separate empirical question.

## Four distinct representations

The original typed Python intent and frozen `BuildRequest` specify behavior.
`SourceExecutionManifest` retains every source node, installed action, state
assignment, role, channel and wrapped obligation. The existing `BehaviorProgram`
provides executable meaning; no alternate therapeutic language is introduced.

`PayloadArchitectureLibrary` supplies composite `PayloadArchitectureRefinement`
records. Each contains an independently authored Behavior graph, either an
injective model-node → original-source-node mapping or an explicit exact matching
policy with optional source anchors, explicit runtime ownership, locked
`ComponentRecord` records and exact `PayloadTemplate` construction authority.
The checker compares actual operations, edges, types, roles, parameters and
versioned execution policies. A claimed family name or coverage list is not proof.
Execution-bearing modeled components must pin the full supplied composite
Behavior fingerprint. An unrelated intrinsic digital operator cannot establish a
composite contract; sequence-reference constituents alone cannot implement owned
runtime behavior.

`ArchitectureBinding` records the many-to-many relationship between behavior
nodes, components, templates and exact member placements. One RNA can encode
several functions; several RNAs can realize one function. Component count, output
count, RNA count and recipient-role count are independent. Constituent wiring uses
explicit typed component ports and `ArchitectureConnection` records.

`ArchitecturePlacement` assigns each emitted member to a recipient role,
compartment and delivery group. Behavior-related IDs in supplied contracts are
local model IDs and are remapped through the declared source correspondence.
Source-side control requirements and delivery groups use original source IDs.
Molecule, template, component and helper identities are local to each refinement.

The selector considers supplied graph blocks and RNA partitions together. It
never emits one RNA per source node by default or splits a completed sequence to
satisfy a later count constraint. A template shared within one composite is an
explicit material choice. Distinct selected refinements are namespaced and never
deduplicated because their sequences happen to match. Installed rules, actions,
state and memory require exactly one owner across selected refinements.
Pure input scaffolding can be shared across supplied subgraphs. A model cannot
relabel its executable state, memory or installed actions as an imported boundary;
shared-state import contracts are not implemented in this profile.

## Reusable refinement matching

Set `match_policy=bc.ArchitectureMatchPolicy()` and use `source_bindings={}` or a
partial map of required anchors to reuse a supplied graph without knowing all
source node IDs. The supported policy is `exact_semantic_subgraph`: operation,
attributes, ordered input edges, type, contact scope, role edges, execution
version and policies must agree exactly. Biological names and parameter values
remain literal authority. The matcher performs no Boolean rewriting, symbol
wildcarding or molecular mechanism discovery. Without a matching policy, the
existing complete explicit correspondence remains required.

Each `ArchitectureRefinementInstance` retains the complete injective mapping and
the original library refinement identity. Several instances can reuse one
supplied model for distinct source subgraphs; runtime ownership and composition
checks still apply. Selected instances receive separate material namespaces.
Output requirement identities, products, lifecycles and exact installed action
inventories constrain matching instead of being renamed to fit a candidate.
The independent checker reconstructs selected instances from complete library
authority and source semantics without importing the matcher.

## Output and control contracts

`ExecutableCircuitBehavior` retains the complete existing Behavior graph and the
original actions implementing each supplementary output. Multiple mutually
exclusive rate branches may bind the same output. `ArchitectureOutputBinding`
pins those actions to the complete `CircuitProduct` and `CircuitLifecycle`,
including quantity, readout encoding and lifecycle declarations. A state update
is retained as runtime behavior without inventing an extracellular product.

Control requirements distinguish:

- Shared or independent activation.
- Production adjustment and activity control.
- Memory reset and shutdown.
- Physical RNA separation and dependency disjointness.

Each supplied `ArchitectureControl` identifies its controlled actions, causal
inputs, component implementations, physical control domain and assumptions.
Independence is checked using those declarations and their actual source/model
correspondence. Independent shutdown is a different requirement from separate
RNAs. Distinct control components can occupy one supplied RNA; two RNAs can still
share a controller or helper. Switching production off does not establish
clearance or inactivation of an already produced effector. Such lifecycle meaning
requires its own supplied contract and source behavior.

Checker policy `biocompiler.payload_architecture_checker.v0.3` proves
the functional meaning of explicitly requested activation and shutdown. One
cell-local Boolean condition per control denotes assertion: shutdown assertion
must force every installed ongoing rule for the target action off; activation
deassertion must do the same. The original source guards supply this proof,
independently of the control's label and component model pin. Active-low controls
must name an explicit negated Boolean condition. Raw signal references are accepted
only when exactly one source qualitative predicate declares their Boolean meaning.
The bounded proof supports Boolean expressions over at most eight explicit
qualitative observations and treats other guard expressions as unknown; an outer
Boolean veto can therefore constrain a state, numeric or temporal guard without
inventing its value. Both assertion states must be attainable. Ambiguous or
contact-scoped controls, pulse/event persistence, and unproved gates remain
unsupported. Additional bounded proofs retain distinct meanings:

- `memory_reset` on a source memory requires assertion to force its declared
  reset condition true, with reset priority over concurrent setting. A valuation
  with the controller off must permit setting without reset. The source's false
  initial value, onset setting policy and any positive constant expiry remain
  explicit. A reset label without these properties is insufficient.
- `memory_reset` on a finite state requires assertion to force its declared
  initial value from every typed prestate, considering every installed writer
  and simultaneous-write conflict. At most 16 states are supported. Inactive
  transitions must settle, and a stable noninitial state must be reachable from
  the initial state. Guards may use Boolean observations and predicates on that
  target state; event, temporal, numeric and other-store dependencies remain
  unsupported by this proof even when the execution language supports them.
- `production_adjustment` covers every installed secretion action for the exact
  same recipient role and product, across all secretion declarations. It
  requires finite nonnegative typed constant rates, resolved from independent
  frozen bindings, and disjoint cell-local Boolean branches. With other
  observations fixed, each controller state must have one unambiguous requested
  rate. The change must have one consistent direction, increasing or decreasing,
  with at least one strict change. No active request counts as zero requested
  rate; it says nothing about residual biological secretion. Runtime numeric
  rate laws, pulse/event persistence, overlapping requests and ambiguous control
  states are unsupported by this proof.
- `activity_control` gates every installed use of explicitly modeled ongoing
  `rest`, `eliminate` or `engulf` actions when the controller is false. Every
  controlled action needs an enabled witness when true. Boolean contact
  predicates may constrain activity guards, while the controller stays
  cell-local. Exact output authority must declare `biological_activity` and an
  `activity_control` lifecycle. A secretion action cannot stand in for this
  contract, and persistent pulse/event effects remain unsupported.

These additional proofs enumerate at most eight explicit qualitative observation
atoms in total, including guard observations, and require both controller states
to be attainable. Different qualitative bands remain independent observations;
no biological relation between them is invented. Production control declarations
must explicitly cover the complete product action group. Independence checks use
that group's full causal ancestry and material owners, as well as declared
controller components and domains. Dependencies include both effect owners and
controller components. A descriptive record alone never certifies a requested
functional property; failures retain source-linked reasons.

## Helpers, recipients and complete material

`ArchitectureHelper` declares its exact capability and consumers, placement,
recipient role, compartment, initialization, prerequisites, sharing policy and
nominal consumer capacity. Availability distinguishes the same RNA, another RNA
and a declared host capability. Bootstrap cycles cannot create their own starting
supply. `available_at_start` is an explicit conditional assumption about when the
program clock begins, not evidence of expression kinetics.

A delivered helper is part of the complete RNA set and every applicable count or
size limit. `RecipientDeliveryGroup` states co-delivery and same-recipient
assumptions explicitly. Membership in one patient or one cell population does not
establish that helper and consumer occur in the same recipient cell. Channels
connect roles explicitly instead of using implicit cross-role signal access.

`RNAArchitectureConstraints` can require an exact or maximum RNA count, maximum
member length, total nucleotide count and delivery-group count/size limits.
Control requirements are hard constraints; preferences rank only eligible sets.
Construction reuses `CircuitConstructionRequest` and its existing independent
checker. Supplied roots, transformations, regulatory annotations, processing
relationships, chemistry and every required member remain authoritative. Final
delivered genetic members, including helpers and complex constituents, must be
RNA. DNA roots/intermediates remain legal shared construction infrastructure;
encoded protein products can remain non-delivered metadata.

## Declared RNA availability and deployment windows

`RNAAvailabilityContract` supplies onset and duration bounds for one exact
material placement. `RNADeploymentRequirement` requires a common execution
window for every selected member in a delivery group and recipient role,
including helper and complex-member placements. Destination compartments and
any requested same-recipient co-delivery are checked independently. All times
use seconds from `declared_exposure_start`; the clock and assumptions are
explicit, and values are bounded by 31,536,000 seconds.

For independently bounded onset `[o_min, o_max]` and duration `[d_min, d_max]`,
the guaranteed availability interval is `[o_max, o_min + d_min]`; it can be
empty. A requested interval `[start, end]` therefore requires `o_max <= start`
and `o_min + d_min >= end`. An optional `unavailable_after_seconds` additionally
requires `o_max + d_max` not to exceed that deadline. The checker uses exact
decimal-second arithmetic over serialized numeric values. Missing member
windows, late helpers and incompatible destinations reject the candidate.

These are supplied expression-contract availability assumptions. They do not
establish delivery probability, expression kinetics, RNA clearance, or removal
of previously produced effectors. The older wrapped clinical deployment and
acceptance obligations remain separate and are not discharged by these records.
Availability checks use the request-supplied execution window; they do not
infer or reset the abstract evaluator clock or derive a full clinical deployment
wrapper, and helper bootstrap's `available_at_start` assumption remains distinct.

## Bounded executable semantics

The source selects its execution profile explicitly. Existing Behavior v0.1
retains its semantics. Behavior v0.2 adds numeric receiver-local channel
observations, emitted channel values and a restricted rolling integral of a
direct, nonnegative cell-local numeric signal or channel observation. Its window
must be a positive design-time constant. The integral uses exact piecewise-constant
area within that window, but guards consume it at the frozen sample grid and
input/timer events, with a 10,000-observation execution bound. It does not certify a continuous-time exposure ceiling.

For integration, freeze `behavior_profile="biocompiler.behavior.v0.2"` and an
`implementation_constraints["execution"]["integral_step"]` serialized typed
`Duration`, for example `bc.Duration(1).to_dict()`.
The sample step participates in source and model identity. State, reset, timeout,
shutdown priority and mutually exclusive quantitative branches are authored with
the existing API and preserved exactly; the compiler invents no priority or
biological parameters.

`evaluate_payload_architecture` freshly checks a complete selected build before
executing its original per-role Behavior with declared channel transport. The
transport profile samples settled emitted actions on an explicit finite grid,
queues them for declared latency and supplies receiver-local numeric values.
Persistence, aggregation, initial value and failure behavior are supplied
contracts. The current executor uses integer-second grid multiples, strictly
positive latency, positive grid-aligned persistence when finite, at most 1,000
samples and at most 10,000 role evaluations.
Zero-latency feedback and undeclared qualitative channel encodings are unsupported.
This execution is conditional on the selected architecture, not a physiological
prediction derived from nucleotide spelling.

## Search, verification and limits

The bounded selector retains alternatives and precise diagnostics for unsupported
semantics, missing implementations, incompatible composition, contradictory
requirements, missing sequence authority and budget exhaustion. A `no_solution`
result refers to the supplied alternatives. Budget exhaustion is a distinct
result and emits no selected molecule set. Neither establishes biological
infeasibility; the independent checker does not certify search optimality or
exhaustiveness.

Automatic matching has request-wide budgets separate from subset selection:
`max_match_states` defaults to 100,000 node-pair checks and cannot exceed
1,000,000; `max_match_instances` defaults to and cannot exceed 256. Anchor
checks, edge propagation and rejected node pairs consume work. Hitting a work,
instance or retained-record bound returns `search_exhausted` and emits no
selected payload, preserving complete mappings already retained. The selected
mapping is independently checked; the search census is not certified exhaustive.

Retained candidate explanations also have a finite output budget: at most 50,000
JSON items and 1 MB, reduced when the original source receipt needs more space.
Exhaustion preserves accepted records, identifies the next unretained candidate
and reports the number examined. A selected construction that cannot fit the
bounded build receipt likewise returns explicit exhaustion without an optimistic
selected payload.

The checker takes the complete independently supplied request. It reconstructs
source meaning, supplied model correspondence, runtime coverage, controls,
helpers, recipient/channel assignments, template authority and emitted molecules
without importing the architecture selector or template merger. A retained PASS
label or a candidate's own hashes cannot supply expected authority. Request,
source, contract, sequence or placement edits invalidate dependent results.

Implemented bounds remain explicit:

- Automatic exact matching and explicitly mapped supplied graph refinements are
  supported; unrestricted molecular discovery,
  synthesized sequence parts and arbitrary biological adapters are not.
- External helpers without a source-observation binder are rejected. Nonempty
  component operating-domain/resource declarations remain unsupported in this
  architecture profile, even though the shared typed records retain them.
- Wrapped deployment/acceptance obligations, uninterpreted source constraints,
  supplementary executable-circuit observation mappings and unsupported
  lifecycle/provider mappings remain unresolved. Strict completeness
  withholds output; any permitted partial result retains its exact gaps.
- Sampled integration/transport, finite-state execution and rate expressions are
  language contracts. Continuous physiology, stochastic populations, delivery
  probabilities and empirical kinetics remain outside this profile.
- Translation completeness, complete molecule construction, search claims,
  empirical function and human-use admission are separate dimensions.

## Python, CLI and artifacts

The [A–F example](../examples/payload_architectures.py) independently authors its
source and supplied models. It uses only artificial six-symbol RNA controls.

| Case | Connected design slice |
| --- | --- |
| A | Two outputs, shared activation, separate shutdown inputs, explicit control domains and alternative RNA partitions/helpers. |
| B | Prime → act → recover state, timeout, reset and source-authored shutdown. |
| C | Mutually exclusive clamped rate branches with a sampled cumulative-activity budget. |
| D | Sender/receiver roles, explicit delayed channel, separate recipient groups and all helper RNAs. |
| E | One component over several RNAs or several components on one RNA, using supplied alternative material. |
| F | Coupled roles combining channel activation, state, timeout, reset, shutdown and numeric activity budget. |

```sh
PYTHONPATH=src python3 -m examples.payload_architectures --case all --output generated/architectures
PYTHONPATH=src python3 -m biocompiler architecture-build --request generated/architectures/a/request.json --output generated/architectures/a/rebuilt.json
PYTHONPATH=src python3 -m biocompiler architecture-verify generated/architectures/a/rebuilt.json --expected-request generated/architectures/a/request.json
PYTHONPATH=src python3 -m biocompiler architecture-export generated/architectures/a/rebuilt.json --expected-request generated/architectures/a/request.json --output generated/architectures/a/export.json
```

```python
import biocompiler as bc
from examples.payload_architectures import make_architecture_request

request = make_architecture_request("A", variants=("many_components_one_rna",),
                                    exact_count=1, independent_shutdown=True)
build = bc.compile(request)
check = bc.check_payload_architecture(build, expected_request=request)
exported = bc.export_payload_architecture(build, expected_request=request)
```

The example writes `request.json`, `build.json`, `payloads.fasta` and
`manifest.json` per case. The CLI `architecture-export` publishes one JSON object
containing both `fasta` and its complete companion `manifest`. Preserve the
independent request separately. FASTA alone cannot retain source/model meaning,
helpers, chemistry, processing, placements, assumptions or unresolved obligations.

The [control examples](../examples/architecture_control_designs.py) add connected
`memory_reset`, `state_reset`, `production_adjustment` and `activity_control`
cases. Each authors source and supplier behavior separately and compiles through
material selection, fresh verification and paired RNA/manifest export:

```sh
PYTHONPATH=src python3 -m examples.architecture_control_designs --case all --output generated/controls
PYTHONPATH=src python3 -m biocompiler architecture-verify generated/controls/state_reset/build.json --expected-request generated/controls/state_reset/request.json
PYTHONPATH=src python3 -m biocompiler architecture-export generated/controls/state_reset/build.json --expected-request generated/controls/state_reset/request.json --output generated/controls/state_reset/export.json
```

The [automatic matching and deployment example](../examples/architecture_automation.py)
changes source node identities while keeping supplier graphs unchanged. It
matches without source anchors and rejects a preferred helper architecture whose
declared onset misses the requested common window:

```sh
PYTHONPATH=src python3 -m examples.architecture_automation
```

In Python, `make_control_request(case)` and `make_automation_request()` return
complete `PayloadArchitectureRequest` objects for the same public compile,
verify and export APIs above. Availability contracts and match instances are
retained in the complete build manifest.

The earlier [per-operator payload profile](executable-rna-payload-v0.1.md) remains
available with its own supported source subset and artifact schemas.
