# Independent synthetic and component source authority

Read-only implementation audit, 2026-10-02. This document is a plan, not a
validation or completion receipt. It follows `AGENTS.md` and the
[language migration roadmap](language-migration-roadmap.md). The existing synthetic
fixtures preserve historical software behavior only; they do not introduce a
new organism target or biological evidence. Native builds remain hosted.

## What remains after the component acceptance batch

The current native checker can freshly check BuildRequest-to-Behavior authority,
execute independent source and candidate models, check finite response histories,
link complete component contracts and execute actual locked component assemblies.
It cannot yet accept a SyntheticCandidate's declared generation provenance or a
ComponentAssembly's correspondence to that accepted candidate.

Python implements those checks in `synthesis/synthetic.py:734` and
`compiler/components.py:93`. Both still call producers:

* Synthetic acceptance calls `generate_synthetic` at line 803, retaining only
  its source and requirement maps. Nevertheless this call also performs all
  supported-source checks, constructor checks and hard-policy checks on the
  deterministic generated graph. Replacing it with a map-membership check loses
  observable responsibilities.
* Assembly acceptance calls `adapt_synthetic_components` at line 103. The adapter
  first reruns full synthetic acceptance, requires PASS, derives complete
  declarations, then constructs a registry and composition. Assembly mismatch
  checks happen only after all of this work.

The native replacement must independently derive those authorities. It must not
call either future native producer, deserialize an expected artifact supplied by
the candidate, invoke Python, or accept a cached PASS. It must also preserve the
important permissiveness of synthetic acceptance: the expected synthetic graph's
edges, operators and response values are **not** compared with the candidate's
edges, operators and values. Coherent candidate changes are checked by actual
execution; some changes within authored response bands can legitimately pass.

## Proposed module and API boundary

Use immutable domain modules for complete SyntheticComponent, SyntheticCatalog,
SyntheticGeneratorConfig and SyntheticCandidate codecs. Catalog lookup returns
the entire pinned built-in record, not an operation-name whitelist. Reuse the
existing Component_registry.Component_lock codec. Keep configuration import
structural/current-policy validation distinct from an accepted candidate type.

Add the following modules to `bioc_realization_checker`:

* Private `Synthetic_provenance`: independently check source-profile eligibility
  and derive expected maps and deterministic proposal policy obligations from a
  `Checked_request.t` and validated configuration. It has no producer dependency.
* Public `Synthetic_candidate_check`: `check`, `check_with_usage` and, if needed,
  an explicitly fresh `replay` taking full request, candidate, exact history,
  optional horizon, reduction-only limits and optional parent Work_budget.
  Return the complete Realization_evidence.Check_result, not just a bool.
* Private `Synthetic_component_authority`: independently derive complete expected
  registry and composition from fresh request/candidate authority. Internal
  typed declarations may be materialized for comparison, but are never exported
  as a producer endpoint or accepted without the enclosing fresh check.
* Public `Component_assembly_check`: `check`/`check_with_usage` with complete
  request, candidate, assembly, exact history and horizon; return the complete
  Composition_evidence.Result or the precise rejection. This API does not
  replace Component_behavior_check: that existing API deliberately does not
  require synthetic source provenance.

Avoid an importable boolean/certificate granting authority. An optional abstract
fresh-candidate value can be private and invocation-local; never serialize it or
reuse it across history/horizon/policy changes. Checked_request validates source
lowering once at the entry boundary. An internal typed entry point may pass the
fresh value through nested checks so that duplication is bounded and explicit.

Keep `bioc_candidate_runtime` isolated from source semantics and both checker
libraries. Its reconstruction remains the independent actual-assembly executor.
Keep `bioc_realization_checker` independent of `bioc_compiler` and any synthetic
generator/adapter producer. Add the new authority modules to Dune private_modules
and update the exact private module inventory in `tools/check_core_boundaries.py`, with its
existing dependency-boundary regression tests.
Share only previously validated domain codecs, identity/canonical primitives,
scalar algebra and Component_contract.synthetic_output_domain. State this
residual sharing; it is not two wholly independent implementations of every leaf.

## Synthetic acceptance: exact order and results

Use the following order after bounded wire/typed import and fresh source checking.
Python's RealizationRequest already establishes source authority during its
construction; the native structural request envelope alone does not.

1. Validate request/candidate API types, materialize the history, select the exact
   catalog from candidate configuration. Build complete realization_dependencies
   from the **actual candidate** mechanism and observation map, not expected
   graph authority. History frame errors and invalid horizon therefore precede
   wrong candidate-request identity and all semantic result diagnostics.
2. Extend settings with all seven exact fields:
   `synthetic_acceptance=biocompiler.synthetic.acceptance.v0.5`,
   `synthetic_profile`, `synthetic_candidate`, `realization_request`,
   `generator_configuration`, `catalog`, and
   `required_coverage=active_and_inactive_deadlines_for_every_response`.
   Preserve every base dependency field, including source artifact coordinates,
   actual history, explicit-versus-effective horizon, current tool settings and
   independent runner versions. DependencySnapshot uses ASCII canonical JSON.
3. A request semantic fingerprint mismatch returns FAIL with exactly
   `candidate_request_identity` and the existing complete message. Its checked
   IDs are every contract response ID, in contract order. No execution occurs.
4. Parse current hard policy, catching only its UnsupportedBehaviorError analogue
   into UNSUPPORTED/`unsupported_selection_policy`. Check the **actual** mechanism
   and return FAIL/`candidate_hard_constraints` if any violation exists.
5. Independently derive provenance plus the deterministic proposal's policy
   obligations. Only unsupported source/profile errors become
   UNSUPPORTED/`unsupported_generation_profile`, including node ID and full
   source location. Preserve `str(error)` formatting: original message, then
   ` [node_id]`, then ` at file:line`, as applicable; source function remains in
   the separate diagnostic source object. Ordinary serialization/type failures
   during generated declaration validation are not caught by this branch.
6. Compare exact expected source_map and behavior_requirement_ids. Map keys and
   ordered value sequences all matter; no sorting of candidate values to forgive
   a change. Mismatch returns `candidate_lineage` with the generation-profile
   message. This branch precedes candidate catalog lock checking.
7. Lock the actual candidate graph against the fixed catalog. An unavailable
   operation returns `candidate_component` with the out-of-catalog message;
   unequal full sorted locks return the stale-version/content message. Do not
   equate these cases or accept a relabeled content hash.
8. Verify every source node and every behavior requirement reference is known,
   then the union of all carried behavior requirement IDs equals the complete
   original behavior requirement set. Preserve the two different lineage
   messages. These checks remain even if a correct provenance derivation makes
   them redundant on ordinary generated examples.
9. Run Realization_check on the actual candidate, exact supplied history and
   horizon. Replace only its dependencies with the complete synthetic snapshot.
   Preserve outcome, coverage, diagnostics, counterexamples and checked IDs.

No UNKNOWN is upgraded by provenance, linking, finite enumeration or a complete
inventory. Human requests still fail current admission inside source-profile
checking. A reidentified human candidate typically returns UNSUPPORTED with the
generation-profile diagnostic; do not invent human-use admission.

## Hard policy and configuration variants

Both profiles are supported: combinational.v0.1 and temporal.v0.1. Their catalogs
are v0.2, component versions are `2`, and generator is v0.4. Combinational has nine
operators: input, constant, and, or, not, compare, select, any_contact, output.
Temporal adds held_for, onset, pulse and memory. Delay exists in Mechanism but
is outside both catalogs. Catalog text, assumptions, guarantees, profile and
model version are identity-bearing; temporal versions of common operators have
different guarantees and consequently different fingerprints.

Configuration v0.3 requires exactly the current generator, current selected
catalog fingerprint, `closed_band_lower_endpoint` and strategy `native` or
`de_morgan`. An absent constructor catalog pin gets the selected catalog pin;
serialized import requires an explicit SHA-256 pin. Do not treat constructor
defaults as import defaults or permit arbitrary caller catalogs as authority.

Hard-policy parsing is ordered: reject extra implementation constraint keys;
reject extra preference keys; validate `allowed_operators`; validate
`max_gate_count`; validate minimize. Allowed operators defaults to the sorted
catalog inventory and must be an array of distinct strings within that catalog.
An empty allowed array is valid policy. An explicitly present gate bound must be
a nonnegative mathematical integer, never bool or null; preserve arbitrary
integer precision. Missing bound means unbounded. Minimize defaults to gate_count
and also accepts none; it influences later selection, never relaxes constraints.

Violation order is forbidden unique operation names sorted lexicographically,
then gate-count excess. Input/constant/output cost zero; **every other actual
operation costs one**, including delay if separately inspected. Use strict `>`
for the bound. Format `operator_not_allowed:a,b` and
`gate_count_exceeded:actual>maximum` exactly. Actual violation messages use `; `;
the deterministic provenance proposal's violations use the same list prefixed
`Synthetic proposal violates hard constraints: ` and become unsupported profile.
That second hard-policy check cannot be dropped merely because the candidate
itself passes policy.

## Independent provenance derivation

Implement an explicit stack/task traversal over typed Behavior operations with
bounded memoization, rather than unbounded OCaml recursion or importing a
producer helper. An internal table can hold expected node descriptors sufficient
for source maps, scope decisions, identities, operation costs and constructor
validation. It is a specification-driven checker witness, never the executed
candidate. Where Python generation validates complete generated Mechanism
declarations, retain equivalent validation through shared typed constructors;
otherwise ID collisions or malformed expected graph shapes could silently become
accepted. Do not compare this witness graph to the candidate's full graph.

Source-profile preflight order is observable:

1. Current selection admission must be software_only.
2. Explicit artifact scope must be synthetic_realization.
3. Parse current policy.
4. Exactly one Behavior role and equal operating/contract role.
5. Explicit finite max_contacts (zero is allowed).
6. Target supplies synthetic_signal_graph, then abstract compartment, then all
   operating-domain capabilities.
7. Iterate Behavior nodes in original declaration order. Common supported kinds
   are role/scope/signal/qualitative/literal/parameter/and/or/not/compare/signature/
   rule/action.rest/action.eliminate/action.engulf. Temporal additionally admits
   held_for/became_true/memory/memory.is_set/action.pulse. Reject other kinds with
   the exact unsupported-kind message and source. Combinational rejects
   non-condition rules; every event rule must contain only explicit pulses.
8. Installed `(rule ID, action ID)` set equals the contract's same pair set, then
   contract behavior identity matches. Preserve original set comparison;
   constructor guarantees handle uniqueness rather than strengthening this test.
9. Every operating input and response observable uses abstract compartment.

Build direct Behavior-node and source-link indexes, operating inputs by
`(signal_id, field)`, expression memo, observed-key set and response_sources where
each response maps to the set of Behavior.source_links for its rule.

For an expected `add(ref, operation, sources, ...)`, derive source_map as sorted
union of `behavior.source_links[source]`; derive behavior_requirement_ids as
sorted union of each **direct source node's** requirement_ids. Mechanism response
IDs default to responses whose response_sources intersect the direct sources;
explicit response ID arguments override this. These are three different lineage
relations. Do not substitute full source ancestors for direct sources in the
response or behavior requirement calculations.

Expression rules and required generated IDs:

| Behavior expression | Checker witness / metadata consequence |
| --- | --- |
| qualitative | Observe its signal and named band, using qualitative node as direct source. |
| signal | Observe value, using signal itself as direct source. |
| literal/parameter | `expression:<id>` constant, original literal/default typed value, cell scope. |
| signature | Alias child's expression result; union wrapper source links into source_map only. Deliberately do **not** add wrapper behavior requirements or response IDs here. |
| and/native, or, not, compare | `expression:<id>`, recursively retain original input order, typed Boolean and original comparison operator. |
| and/de_morgan | `expression:<id>:not:<index>` for every operand, then `expression:<id>:or`, then `expression:<id>` not; all retain original binding scope and direct source `<id>`. Do not existentially aggregate individual operands. |
| held_for | `expression:<id>` with one expression input and bound positive duration. |
| became_true | `expression:<id>` onset with one expression input. |
| memory.is_set | Alias memory result; union wrapper source links and direct behavior requirement IDs, but not response IDs. |
| memory | See exact ordering below. |

Observation requires an exact authored `(signal, field)` key. Value uses signal
data type; qualitative uses Boolean. Scope comes from the signal's contact_bound,
not the request observable. Validate exact declared scope and compatible type.
First use adds `input:<signal>:<field>`, using the declared operating observable
as output. Later uses union source links, direct behavior requirement IDs and
responses whose response_sources contain this direct source. Reuse expression
cache before visiting again; repeated wrappers and shared observations must
reproduce these asymmetric updates exactly.

Duration references must be literal or parameter; decode their value/default as
DURATION and require canonical value > 0. Keep original scalar representation in
the generated descriptor's attributes; do not substitute a naked float. The
duration node's source is used on an unsupported-duration error.

For each memory, map original input_names to original inputs. Evaluate set_when;
create `memory_onset:<id>` in setting scope, then existentially reduce to
`memory_set:<id>` only if contact-scoped. This order means each new qualifying
contact may refresh memory even while another stays true. Evaluate reset_when
and reduce to `memory_reset:<id>` only when contact-scoped; if absent, create a
cell false constant with that ID. Create cell `expression:<id>` memory with
setting/resetting inputs and optional bound duration. Iterate **all memory
declarations before outputs**, including unused declarations, in Behavior order.

For each contract response in original order: check response role and action
contact scope; evaluate rule guard; if contact guard serves a cell response,
create `aggregate:<response>` any_contact with rule as direct source. For an
action.pulse under a condition rule, add `pulse_onset:<response>` after this
aggregate; an event rule adds no second onset. Add `pulse:<response>` with authored
duration. Add active/inactive constants from the respective closed band's lower
endpoint, then select, then output, using IDs `active:`, `inactive:`, `select:`,
`output:` plus response ID. Their direct sources are rule and action and explicit
response inventory is the singleton current response. Output keeps the exact
authored response observable. Preserve output order and exact observation map
binding order (input keys sorted; responses in contract order).

Finally require observed keys equal all operating input keys, rejecting extras.
Validate expected mechanism with nodes sorted by generated ID, name
`<behavior name>.synthetic` and synthetic_signal_graph capability. Count the
final descriptor inventory, not allocations or memo hits, for hard policy. This
matters for aliases/shared inputs and any legal identifier collision behavior.
Then compare only the two expected lineage maps during synthetic acceptance.

## Independent component declaration authority

The declaration recipe uses the **accepted actual candidate**. Rebuilding the
default generated graph here would reject coherent passing candidate changes.

1. Run Synthetic_candidate_check freshly and require outcome PASS. The exact
   rejection is the SerializationError analogue with message `Component
   adaptation requires passing synthetic acceptance for the current request,
   candidate and history.` Do this before reading supplied assembly provenance.
2. Convert authored input domains to Component_contract.Value_domain: Boolean
   enumeration unchanged; scalar interval uses canonical lower/upper values,
   authored dtype and canonical_synthetic_unit. Index by observation key, then
   map actual candidate observation inputs to mechanism input IDs.
3. Traverse actual mechanism topologically twice, for runtime and initialization
   domains. Input nodes get the mapped authored domain; every other operation
   uses validated synthetic_output_domain, actual attributes and ordered input
   domains, passing exact max_contacts. Initial held_for is false, onset/pulse
   initial domains follow their input, memory initial domain derives set and
   reset together. Unknown operands and scalar units remain explicit.
4. Traverse topologically to derive the exact event set: onset nodes, plus
   any_contact whose single predecessor is already an event. Do not propagate
   event timing through arbitrary output/not/select nodes just because values
   are Boolean.
5. Required component operating domain contains every coordinate
   `observation:<signal>:<field>` and `concurrent_contacts=[0,max_contacts]`.
   The latter is default scalar/dimensionless unit `1`. Every record and instance
   gets the complete required domain, not just its incident observations.
6. Common exact pins: source/realization_request/request schema/request semantic
   fingerprint; model/synthetic.program/model runner version/**actual** mechanism
   fingerprint; registry/synthetic.catalog/catalog version/current catalog pin.
   Each record also pins source/<actual operator ID>/<version>/<full operator
   fingerprint>. Catalog assumptions/guarantees must come from independent fixed
   authority, never from supplied component records.
7. For actual node `<id>`, create record `synthetic.instance:<id>`, version `1`,
   classification synthetic_model, implementation_role actual kind, and sole
   supported target equal to request target payload format. Ports: own out first,
   then `in:<index>` for actual ordered inputs. Each input copies its producer's
   exact output meaning/type/unit/role/scope/compartment/init/runtime domain.
   Combinational timing is STATELESS; temporal timing is EVENT exactly for the
   event set, otherwise LEVEL. Empty resources/dependencies/capabilities/evidence
   remain empty; no resource or biology inference is permitted.
8. Constant parameter `value` uses its inferred singleton domain and request pin.
   Method is authored_bound_literal iff node ID starts `expression:`, otherwise
   contract_band_lower_endpoint_witness. This includes false memory-reset
   constants: do not improve their historical label based on operator intent.
   Held_for/pulse/memory with non-null duration get parameter `duration`, singleton
   canonical seconds with DURATION type, same request pin and method
   authored_bound_duration. Indefinite memory has no duration parameter.
9. Exact assumptions are operator assumptions plus `Adapter policy:
   biocompiler.synthetic_components.v0.2` and `No biological resource demand or
   capacity is declared by this software profile.` Guarantees equal operator
   guarantees. SyntheticOperatorModel retains actual operation, complete actual
   attributes, input port order and default out/transition policy.
10. Registry ID is `synthetic.components:<candidate full fingerprint>` and
    version is adapter v0.2. Construct complete typed records and exact registry
    locks. Instance ID equals actual node ID. Its requirements are sorted union
    of node response IDs and candidate behavior_requirement_ids. Source location
    is the **first non-null** Behavior source in that node's ordered source_map;
    never sort by location, choose the direct node automatically, or use current
    source files as authority. Preserve default placement/lifetime.
11. Composition target is full independent request target; exact connections
    are `(input ID,out,node ID,in:index)` in actual node/input order, normalized
    only by the existing typed constructors. Complete request requirements are
    sorted union of Behavior requirement IDs and contract response IDs. All
    provider/resource/binding collections stay empty as the adapter specifies.

## Assembly acceptance: exact order after declaration derivation

First check supplied assembly type (before consuming history); then materialize
history and derive the expected declarations as above. Compare, in one ordered
short-circuit condition: supplied request semantic pin, candidate full pin,
registry fingerprint, composition fingerprint, canonical fingerprint of full
behavior_sources versus candidate source_map, and observation map structural
equality. Mismatch raises `Component assembly changed its authoritative source
correspondence.` Do not replace full fingerprint comparisons with numeric
semantic equality; pins intentionally distinguish representation.

Independently compare exact edge tuple sets and instance ID sets with the actual
candidate graph, raising `Component assembly changed the mechanism graph.` Then
independently reconstruct actual assembly via candidate_runtime.Components, and
for every candidate node compare actual kind, output structural equality,
ordered inputs and canonical attribute fingerprint. Raise `Component assembly
changed source operation parameters or wiring.` These checks are deliberately
retained even when complete expected declaration identity makes them redundant
in ordinary valid cases; they protect against a faulty authority derivation.

Run full generic Composition_check. A nonpassing result is returned intact, not
turned into an exception and not merged with the prior synthetic acceptance.
Only when linking passes run Component_behavior_check on the actual assembly.
If that result does not pass, raise `Reconstructed component behavior did not
pass: <outcome>`. Otherwise return the original complete link result. This path
executes actual component behavior and linking again through the existing wrapper;
reuse must not silently remove a required fresh gate. Any future deduplication
needs an invocation-local exact-authority API and its own equivalence evidence.

## Resource and exception requirements

Use one shared parent Work_budget from the outermost call across input traversal,
fresh request checks, dependencies, policy, provenance, expected declaration
construction, synthetic realization, actual reconstruction, composition and
actual behavior. Child limits can only reduce it. Do not give every phase a fresh
50M allowance. Preserve existing request/report byte and node limits; reserve
complete envelopes including optional until. Derived maps, graph tasks, locks,
records, port expansion and generated source lists also need cumulative retained
item/byte limits, charged before allocation/sort/traversal.

Bound lineage unions against their real product (sources × responses × ancestors)
or use indexed charged set operations. Fanout can make full port/domain copies
quadratic even when mechanism node count is small. Bound repeated canonical
serialization and comparison; cached sizes and hashes are useful only when the
typed authority is immutable. No input-list cycles, deep recursive expressions
or adversarial JSON structure may bypass the existing bounded traversal rules.

For candidate-runtime reconstruction, continue the successful-work charge / full
failure-allocation burn contract used by Component_behavior_check. Resource
exhaustion must propagate as the resource diagnostic, never unsupported profile,
candidate failure, UNKNOWN, or a partial report. Catch exactly the source-policy
unsupported error and catalog-missing operation cases that Python catches.
Reserve and validate the complete final report for all early FAIL/UNSUPPORTED
paths as well as ordinary realization returns. Exact-limit/one-under tests cover
both local and parent allowance, failure then retry, and repeated nested phases.

## Existing test and capture obligations

The current component acceptance corpus has 373 original methods, 380 contexts,
4,539 observed API calls and 52 explicitly deferred check_component_assembly
calls. Preserve that corpus untouched as prior evidence; add full acceptance
observations and precisely classify every deferred call in the new corpus. The
current realization corpus's 137 deferred calls are the same 52 assembly calls
plus 85 actual-component behavior calls; the latter have their separate native
implementation now. Counts are observed-source facts, not completion claims.

Relevant current source cohorts, AST method counts:

| Cohort | Methods | Required evidence |
| --- | ---: | --- |
| synthetic_generation | 17 | Both maps/pins, exact source rejection, coherent wrong model, contact binding, 256 transition pairs, short/empty histories. |
| temporal_generation | 15 | Literal contact/pulse/dependent-memory matrices, all 81 dwell histories, both pulse triggers, contact refresh, no-duration memory, catalog/profile mutations. |
| synthetic_selection | 15 | Both strategies actually checked, malformed policy, hard constraints before ranking, mutated producer outputs, exhaustion versus unknown. |
| component_adapters | 5 | Full exact declarations, numeric domains, parameters, rejected acceptance; preserve two historical reference-adapter cases without new scope. |
| component_pipeline / audit | 9 / 7 | Complete assembly acceptance, changed literal provenance that still links, changed graphs, history/horizon, source links and dependency freshness. |
| temporal_components | 15 | Independent reconstruction, changed duration/wiring, event/level confusion, initialization and reset/expiry, full parameter/model identities. |
| synthetic_verification_workflow | 10 | Fresh exact operation authority, bounded campaigns, reduction, complete dependencies and version mutation. |
| synthetic_build / design_workflows | 11 / 8 | Installed artifacts and CLI, independent reconstructive export, exact history/horizon/mode/budgets and package tampering. |
| human_admission | 33 | Selection/verification/export gates, reidentified human candidate remains unsupported, historical version mutation retained. |
| realization_checker / integration | 31 / 6 | Existing full monitor/source/model and checked pass behavior remain gates. |
| component_admission / component_pipeline_manager / pipeline | 10 / 2 / 21 | Distinct root/pass authority, source links, freshness and changing dependencies; these are not solved by the new direct API alone. |

Capture all imported aliases and nested calls, raw constructors/imports/defaults,
full successes and exception type/message/stage, full external authority and
actual child processes. Producer-patch tests must keep original assertions and
capture resulting actual candidate data; an instrumented checker calling a
patched generator is not evidence of native independence. Retain baseline versus
instrumented execution and exact recapture identity. Version-policy monkeypatch
cases must be narrowly enumerated with full unchanged authority, never broadly
normalized or removed. Never infer a native expected result from the native
producer/checker itself.

## New independent literals and fault tests

Add complete independently computed Python report/declaration literals, not only
status assertions, for every branch above. Include these extra holes beyond the
existing happy paths:

* Signature and memory.is_set aliases with shared inputs, multiple responses and
  unused memory declarations; prove their different map-update rules.
* Both conjunction strategies under constraints; actual graph within policy but
  deterministic provenance graph outside policy; policy parsing before source
  rejection; wrong-request before malformed policy; bad horizon before either.
* Correct lineage plus a coherent changed active constant that remains inside
  the authored band: synthetic acceptance and independently corresponding
  assembly may pass. This proves no exact-generated-value equality shortcut.
* Correct lineage plus coherent wrong AND/OR, output wiring, pulse duration and
  reset wiring: finite realization must decide, retaining counterexample times,
  active/inactive coverage and actual model identity.
* Correct lineage plus actual out-of-catalog delay; stale locks plus changed
  lineage to pin error precedence; extra/missing behavior requirements.
* Both profile catalog full-byte fingerprints and operator pin differences;
  configuration constructor defaults versus strict imports; all policy variants.
* Zero max_contacts; canonical dimensional inputs; integer/float representation
  changes where structural equality and exact fingerprints intentionally differ;
  non-ASCII file/observable IDs to separate UTF-8 artifact identity from ASCII
  DependencySnapshot identity.
* Event set propagation through onset/any_contact but not generic Boolean
  operators; condition pulse onset after cell aggregation; contact event before
  memory aggregation; memory reset dominance and expiry-refresh boundaries.
* Provenance-only parameter method/source/value changes with fully recomputed
  registry/locks/composition that still link and execute identically. All fail
  assembly correspondence. Also add unrelated registry records, assumptions,
  guarantees, target resources/evidence, placement/lifetime, observation mapping,
  source-coordinate changes and missing/extra/reordered wiring.
* Source coordinate relocation keeps semantic request identity where specified
  but changes complete authority/dependencies and instance source. Expected
  declarations must derive the new coordinate, not a cached old location.
* Original assembly plus short/empty/new history or earlier horizon fails
  adaptation acceptance before any forged-assembly correspondence error.
* Independent synthetic checker is runnable with producer libraries unavailable;
  mutation of a test-only producer must not affect its authority derivation.
  Dependency graph test adds direct and transitive producer edges and rejects
  both. Candidate runtime remains runnable without source evaluator/checker.
* Exact/one-under work, request, report and derived-inventory budgets; giant
  fanout, lineage expansion, deep aliases, failed reconstruction then retry; no
  successful receipt after exhausting any parent scope.

After hosted Linux/macOS and complete Python 3.11/3.14 gates pass on the exact
revision, record source/tested/integrated tree identities and complete corpus
inventory. Only then mark the direct synthetic and assembly acceptance items.
Native deterministic generation/adaptation, bounded selection workflow,
PassManager/installed protocol/public Python routing, packages and final default
cutover remain separate roadmap obligations until actually implemented and
validated. No declaration or acceptance change here establishes empirical
therapeutic validity.
