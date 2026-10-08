# Expressive therapeutic policy authoring v0.1

`biocompiler.policy` is the recommended Python surface for new, rich therapeutic
policy specifications. It constructs portable declarations for human immune cells
engineered in vivo with RNA payloads. It does not execute those declarations,
select molecular implementations, emit sequences or establish acceptance.

The document profile is `biocompiler.policy.v0.1`. This is a new authoring family;
it does not change Behavior v0.1/v0.2 or extend their executable capabilities.
Studio and conversational authoring remain deferred clients of this same format.
Layer 3 owns these authoring records and diagnostics. OCaml layers 4 onward will
independently validate their meaning and implement lowering and checking.

## Getting started

The package has no runtime dependencies and supports Python 3.11 and newer.
An installed package can author, inspect and export policies without OCaml,
Rust, network access or a compiler installation.

```python
import biocompiler.policy as bp
from biocompiler.policy.examples import build_example, build_request

program = build_example("context_gated_response")
report = bp.check(program)
assert report.status == "complete"  # authoring structure only
assert report.semantic_status == "unassessed"

bp.dump(program, "response.policy.json")
reopened = bp.load("response.policy.json", bp.PolicyProgram)
request = build_request("context_gated_response")
bp.dump(request, "response.request.json")
submission = bp.prepare_submission(request)
assert submission.backend_execution == "not_performed"
```

All bundled definitions, profiles and numeric values are abstract software
examples. They are neither therapeutic parameter suggestions nor molecular
implementations. Start with explicit, supplied semantic definitions when writing
a new policy.

## The object lifecycle

`ProgramBuilder` holds mutable construction state. `snapshot()` returns an
immutable `PolicyDraft`, including typed `Hole` declarations for unanswered
design questions. `resolve()` replaces a named hole with an explicit declaration.
`freeze()` performs structural checking and returns an immutable `PolicyProgram`.
It rejects invalid declarations and unresolved design slots. It does not prove
that the program has an implementation or satisfies a requirement.

`BuildRequest` binds a program to `Deployment`, `ImplementationCatalogLock` and
`AssuranceRequest`. It is distinct from the existing compiler's BuildRequest.
`prepare_submission()` requires this complete request and returns an immutable
`CompilationSubmission`. There is no automatic conversion to legacy requests.

Explicit assumptions, unrefined objectives, custom-operation meaning and
unproved requirements survive freezing. The authoring report lists deferred
obligations rather than manufacturing semantic PASS labels.

## Constructing a policy

The following example uses the same supplied abstract definitions as the shipped
examples. The field values are illustrative authoring inputs.

```python
import biocompiler.policy as bp
from biocompiler.policy.examples import semantic_bundle

definitions = semantic_bundle()
contracts = {d.id: d.ref for d in definitions.definitions}
p = bp.ProgramBuilder("example", semantics=definitions)
executor = p.executor("executor", requires=(contracts["example.interface"],))
clock = p.clock("time", basis="availability", resolution=bp.quantity("0.1", bp.SECOND))
encounter = p.encounter("encounter", executor=executor,
                        contract=contracts["example.encounter"])
observation = p.observe(
    "condition", observer=executor, subject=encounter.target,
    value_type=bp.TRUTH, contract=contracts["example.observation"],
    clock=clock, access="cell", coverage="continuous",
    coherence="contact_frame", freshness=bp.quantity("1", bp.SECOND),
)
lifecycle = bp.EffectLifecycle(
    authorization="continuous", on_loss="request_stop",
    on_unknown="request_stop", cancellation="acknowledged",
    completion="feedback", failure="feedback",
    contract=contracts["example.lifecycle"],
)
effect = p.effect("response", executor=executor, subject=encounter.target,
                  contract=contracts["example.response"], lifecycle=lifecycle)
p.rule("respond", executor=executor, on=observation.updated,
       when=observation.expression, unknown="defer", effects=(bp.ref(effect),),
       arbitration=bp.Arbitration("exclusive", "reject", "reject", "forbidden", "none"))
program = p.freeze()
```

Use the builder for common declarations and `p.add(typed_record)` for the complete
vocabulary. `p.state`, `p.channel` and `p.require` accept their typed records.
`p.namespace("pattern_instance")` creates deterministic named expansion scopes
and records the pattern origin in source correspondence.

Python conditions are symbolic. Use `all_of`, `any_of`, `not_`, `compare`, or the
symbolic `&`, `|`, `~` operators. `if`, `and`, `or`, `not`, `all` and `any` cannot
consume a policy expression. Expression `==` is Python record comparison; use
`compare(left, "eq", right)` for a policy comparison. Event triggers and truth
guards are different types. Python loops generate declarations; runtime loops
must be represented by state, rules or machine transitions.

## Normative interpretation contract

These definitions specify what later semantic implementations must preserve.
They are not descriptions of a currently implemented policy interpreter.

### Identity, observations and correlation

An executor, observer, observed subject and affected subject are independent
nominal references. A contact encounter has its own identity and a target bound
to that encounter. A stable target identity and an encounter identity are not
interchangeable. Entity identity is not determined by equal observation values.

An observation declares its type, units, observer interface, subject, clock,
access, coverage, coherence group, freshness and interpretation contract. The
contract must define how observed-time intervals map to availability on the
declared clock. A shared coherence name identifies a requested frame relationship;
it is not evidence that observations actually overlap. Clock mapping, latency,
freshness, coherence and observation validity remain realization obligations.

`cell` access is available to policy execution. `external_evaluator` access is
reserved for evaluating requirements and cannot drive cellular behavior. Missing,
stale, invalid and conflicting observation statuses remain distinguishable.
Malformed observation types are errors rather than uncertain negative results.

Direct conjunction across different subjects requires an explicit relationship
through quantification or a supplied operation contract. Nested Boolean syntax
cannot bypass this requirement. Effects authorized by evidence about a different
subject require a pinned relationship contract; merely supplying it does not
prove that redirection is justified.

Quantifiers bind an explicit `Subject(identity="bound", domain=...)` to a
population or region. `exists`, `forall` and `count` require `binding=ref(subject)`.
The predicate must use that binding, and it cannot escape its lexical quantifier.
Domain membership and observation coverage remain explicit obligations. A count
is exact only for a completely observed finite domain; incomplete membership
cannot silently become a smaller count.

### Truth and uncertainty

The declared truth algebra is Strong Kleene:

| A | B | A AND B | A OR B |
|---|---|---|---|
| true | true | true | true |
| true | false | false | true |
| true | unknown | unknown | true |
| false | false | false | false |
| false | unknown | false | unknown |
| unknown | unknown | unknown | unknown |

The operators are commutative for truth values. Negation swaps true/false and
preserves unknown. Comparisons with unavailable evidence are unknown, not false.
`UNKNOWN` is a symbolic truth constant. An unanswered design `Hole`, a runtime
unknown observation and an unproved requirement are different concepts.

Rules declare their unknown branch. `defer` withholds the new effect or update;
it is not a claim that ongoing activity stops. Ongoing effects follow their own
authorization-loss and uncertainty lifecycle contract.
For a machine, `transition` enters its explicitly named unknown target without
starting the ordinary transition's effects or applying its assignments.
`request_stop` requests cessation of the listed effects' active attempts and
starts no new attempt; cessation still needs correlated feedback. Continuous
authorization re-evaluates the originating request's guard in its bound scope;
freshness loss and unknown evidence take the declared lifecycle branch.

### Time

Durations are positive exact quantities with both time dimension and duration
kind. Clock resolution is explicit. Observed timestamps and timestamps at which
information becomes available cannot be interchanged without a mapping contract.

| Construct | Required interpretation |
|---|---|
| `holds(C, d)` | C over `[t-d, t]`; complete continuous coverage is required for a continuous claim |
| `recently(C, d)` | C holds at some covered time in `(t-d, t]` |
| `followed_by(A, B, within=d)` | B strictly follows A on the named clock, with `0 < tB-tA <= d` |
| `after(A, B)` | B strictly follows A; simultaneous events do not count |
| `within(anchor, completion, d)` | Correlated completion occurs at or after the anchor and no later than its deadline |
| `until(activity, stop)` | Activity is required up to the first true stop condition; unknown stop evidence does not establish stopping |
| `rising(C)` | An observed false-to-true transition; unknown history does not establish an edge |
| `integrate(signal, d)` | A sampled accumulation over the declared window, with explicit result units; reconstruction and quadrature remain obligations |

For `holds`, an observed false interval refutes the claim; otherwise incomplete
coverage leaves it unknown. For `recently`, a true witness establishes the claim;
false requires complete negative coverage. Sampled coverage remains sampled and
cannot satisfy a continuous requirement by changing its label. Timers, expiry
and deadlines remain obligations even without a new observation update.

### State, concurrency and lifecycle

State scope is executor, encounter, target, population, lineage, region or whole
program. Initialization, capacity, overflow, lifetime, reset and inheritance are
declared separately. A request for unbounded capacity is representable and remains
an unresolved support obligation. Population state requires an explicit channel
or supplied coordination contract. Persistent state bound to an ephemeral
encounter identity needs an explicit lifetime/identity interpretation.

Events at one logical instant form an atomic batch. Guards and update expressions
read the shared pre-update state. Resulting writes are committed under the
declared conflict policy. Python declaration order grants no priority. Explicit
priority order, tie handling, preemption and fairness are part of the document.
An exclusive declaration creates an exclusivity obligation; the authoring checker
does not solve guards to prove that obligation.

Effect call-site identity, executor, subject and each dynamic request attempt
remain separate. Every request creates an attempt identity. Feedback must carry
the matching attempt/executor/subject correlation specified by
`feedback_identity="attempt_executor_subject"`. A machine waiting for its started
effect binds that attempt; a standalone notification retains the event's attempt
identity. Old or unrelated feedback cannot complete a new attempt.

Request, initiation, completion and modeled outcome are different events, as are
failure, timeout, cancellation request, cancellation acknowledgment and cessation.
Cancellation does not imply reversal of downstream consequences. Lifetime of RNA,
an effector, memory and an enduring consequence are independent.

### Coordination and quantitative behavior

A `Message` declares its sender, subject, channel, payload and correlation identity.
It is sent only when a rule or transition explicitly lists it in `emissions`.
Each emission gets a new dynamic message identity, retained across retries of
that emission. Static subject correlation and identical payload content cannot
deduplicate a different emission or authorize an old acknowledgment to satisfy
a new send. This distinction is explicit in `Message.identity_policy`.
`received` notifications belong to channel recipients; sent, acknowledged and
expired notifications belong to the sender. Transport ordering, loss, duplication,
acknowledgment, retry bounds and latency remain distinct contract fields. Declaring
a channel does not establish physical communication or same-recipient delivery.

Quantities are exact decimal values plus nominal units, quantity kinds and
reference scopes. `quantity("1.5", unit)` has no binary-float conversion. Use
`from_float` to deliberately preserve a float's exact value. Addition/comparison
requires compatible quantity kinds and reference scopes; multiplication/division
declare a result type whose derived-unit correctness remains a semantic obligation.
No numeric policy is inferred from a disease name or chassis category.

### Requirements and deployment

Safety, progress, bounds, observability, external control and approximation are
formal requirement categories. Assumptions, preferences and unrefined objectives
remain separate. Progress must retain enabling conditions, response and relevant
time/coverage assumptions; inactivity cannot be relabeled as successful response.
Timed requirements declare a trigger event and clock. The deadline is measured
from that trigger, with a supplied condition acting as its enabling guard.
Responses retain the trigger's attempt/message/subject correlation. Requirements
with no deadline can still describe unbounded progress; unsupported proof domains
remain explicit. Patterns retain mandatory event/guard behavior as well as
completion requirements; an absent request does not implement an enabled rule.
Selecting assurance for only some requirements does not waive the remaining hard
source requirements. A future accepted build must discharge its applicable source
obligations independently of authoring status.

Chassis profiles describe human immune lineages or immune progenitors, subtype,
states, interfaces, capability contracts, environments and operational-model pins.
Capability requirement, supplied capability and realization are separate records.
Profiles make no empirical claims merely by being structurally complete.

Delivery distinguishes intended recipients, arrival, expression, activation and
co-delivery. The intended recipient is not the same concept as a recognized or
affected target; a therapeutic target need not itself be an immune cell.
RNA design count, delivered-member count including helpers, helper count, copies,
ORFs, products and dose are separate constraints. `None` means unconstrained in
this request, not zero or a guessed default. Same-population arrival does not
establish same-recipient co-delivery.

## Catalog and extension authoring

`SemanticDefinition` provides a versioned meaning, parameter/result signature,
typed clauses and assumptions. `definition.ref` pins its complete body by digest.
Every referenced definition must be supplied in the bundle. New operations use
these records and explicit call signatures, not imported code or callbacks.

`ImplementationBinding` associates semantic operations with supplied realization
references, chassis, RNA targets, dependencies and evidence. Empty catalogs are
valid declarations with unresolved realization obligations. No search or admission
is performed. `patterns` provides ordinary Python expansions that preserve their
typed source declarations; it does not perform hidden optimization or lowering.

## File, identity and handoff contracts

JSON uses the closed `$type` discriminator, exact named fields and explicit
profile versions. Unknown/missing fields, duplicate keys, raw floats, executable
objects and unknown record types are rejected. Lists become immutable tuples.
The default decoder limits are 2 MiB, 64 nesting levels, 100,000 visited nodes,
262,144 bytes per string and 256 characters per numeric spelling. Quantity
canonical spellings are also bounded to 256 characters. Limits are configurable
through `SerializationLimits`; a larger input cannot bypass scalar construction
bounds. Submission packaging uses the same 2 MiB document limit.

Document digests use deterministic sorted-key UTF-8 JSON and SHA-256, excluding
`source_map` and provenance fields. Ordered arrays remain ordered. Digests bind
declarations, not semantic equivalence. Program, deployment, catalog, assurance
and definition bodies remain distinct identities; changing request context changes
the request digest. Source maps retain filenames, lines, columns and pattern
origins but do not prove arbitrary Python authoring code correct.

Builder ownership catches accidental cross-program references even when local
IDs match. That in-process ownership token is not serialized and does not alter
deterministic digests. Explicit import of declarative data re-establishes local
reference closure through structural checking.

The `state`, `channel` and `require` helpers check the input record's ownership
before making a namespaced copy. A record already owned by another builder needs
explicit declarative import, just as it does for `add`. Encounter construction
checks both the generated target and encounter before adding either; a rejected
expansion leaves the declarations and source map unchanged.

`dump(..., overwrite=False)` uses atomic no-clobber publication. Loading performs
no dynamic imports, dependency downloads or backend discovery. Schema export is
derived from the reviewed closed registry. Wire changes require an explicit
version decision; imports never silently upgrade old documents.

`BackendCapabilities` is an explicit caller-supplied declaration.
`assess_capabilities()` compares profile/feature coverage only. Even
`declared_compatible` means neither native execution nor semantic validation.
There is deliberately no new-profile compile dispatch until a native consumer
implements and validates this contract. No fallback to the old Python compiler
can discard unsupported meanings.

The opt-in [native source front end](policy-native-front-end-v0.1.md) now exposes
`policy.native.assess()` and `biocompiler policy assess-native` for complete
frozen programs, requests and submissions. It performs OCaml source-contract
checks and fresh replay while reporting execution, lowering and realization
as unsupported. Source-valid reports do not authorize molecular artifacts.

## CLI and notebook usage

```sh
biocompiler policy check response.policy.json --json
biocompiler policy inspect response.policy.json --json
biocompiler policy diff before.policy.json after.policy.json --json
biocompiler policy export-schema --output policy.schema.json
biocompiler policy export-request response.request.json --output submission.json
```

Output files refuse replacement unless `--replace` is supplied. Outputs cannot
alias inputs. Checks return 0 for structurally complete declarations, 1 for
invalid/incomplete documents, and 2 for invocation or I/O errors. Diff returns 0
for no differences, 1 for differences and 2 for errors. Export commands can also
write JSON to stdout. These commands never execute an uploaded authoring script.

Notebook objects render inert escaped HTML with declaration summaries, diagnostic
source locations, assumptions and deferred obligations. `inspect` provides the
same data without HTML. `graph` exposes occurrence-addressed declaration and
definition nodes with reference field paths, preserving missing and ambiguous
matches. The notebook preview displays a bounded, escaped dependency table;
the API retains the complete bounded graph. `diff` reports declaration changes, meaningful order,
deployment/catalog context and provenance separately. Neither asserts semantic
equivalence or requirement satisfaction.

## Examples, validation and remaining compiler work

`policy.examples.NAMES` lists eight installed examples: context-gated response,
regulated secretion, staged cleanup/repair, encounter sentinel, persistent-target
sentinel, local restraint, coordinated populations and lineage/bounded response.
Run `examples/expressive_policies.py` against an installed package to inspect all
eight. They contain supplied abstract definitions and no molecular sequences.

Focused tests cover independent expected declarations, wrong subjects/owners,
uncertainty, exact numbers, timing fields, lifecycles, quantifier bindings, scopes,
serialization rejection, immutable handoff, CLI and installed import isolation.
`tools/mypy-policy.ini` defines strict typing for the complete new package.
`tools/check_policy_install.py` checks an existing installation outside the source
checkout without loading compiler/native modules.

Two additional static ledgers make the reviewed source boundary inspectable.
`protocol/policy-public-api-coverage-v0.1.json` inventories authored declarations,
builder/pattern expansions, exports and submission input keys with distinct
witness roles; rows marked `source_only` have no claimed behavioral witness.
`protocol/policy-source-context-coverage-v0.1.json` indexes the reviewed source
unit/scope rules and their caller contexts, retaining differences between Python
authoring and native source assessment. Their corresponding
`tools/check_policy_public_api_coverage.py` and
`tools/check_policy_source_context_coverage.py` commands check closed identities,
source drift and reviewed metadata without importing the policy package.
Neither ledger establishes executed semantics, whole-stack coverage or material
acceptance. The normal unit suite retains their adversarial drift controls.

Still required in later layers: authoritative semantics and units; reference
execution; temporal/uncertainty interpretation; quantified domains and observation
coverage; arbitration and attempt correlation; target capability analysis;
realization search; preservation obligations; independent checking and acceptance.
The authoring check reports these as unassessed rather than treating source
expressivity as executable target support. All existing migration cutover gates
remain separate.
