# Bounded conditional policy-to-mRNA acceptance

This is a source checkpoint for SM-06 through SM-09 in the
[semantic mRNA development plan](semantic-mrna-development-plan.md). The material
coordinator, native services, Python transport, paired publication and hosted
campaign have source implementations. Their complete hosted material acceptance
has not been established. No task checkbox is closed by this document, an authored
fixture, a mock transport test or a successful earlier implementation-only run.

The claim is internal semantic correspondence under explicitly supplied finite
domains, primitive models, model-to-sequence contracts and provider contracts.
It is not a claim that those contracts describe biological behavior. Empirical
validation, cellular viability and therapeutic efficacy remain outside this
profile; exported manifests retain `empirical: unassessed`.

## Complete original authority and closed schemas

The original material request contains these exact fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | `biocompiler.policy_material_request.v0.1` |
| `profile` | `biocompiler.policy_truth_mrna.v0.1` |
| `implementation_request` | Complete original `biocompiler.policy_realization_request.v0.1`: Python-authored BuildRequest, operational definitions, finite operating domain, supplied primitive library, exact catalog-to-model bridges and original exploration budgets |
| `material_contract` | Independently supplied whole-graph material case, `biocompiler.policy_material_contract.v0.1`, profile `biocompiler.policy_truth_mrna_material.v0.1` |
| `context` | Original recipient, clock, placement, delivery and provider/capacity authority, `biocompiler.policy_material_context.v0.1` |
| `catalog_binding` | Exact original entry ID/version/digest and operation/realization DefinitionRefs, plus the complete material-contract model identity |
| `budgets` | `biocompiler.policy_material_resources.v0.1`, with `max_work`, `max_report_bytes` and `max_report_nodes` |

The material bridge does not authorize primitive models on its own. Source
admission still requires the original nonempty catalog, exact entry bodies,
original chassis/RNA eligibility and explicit authorization of every supplied
library model. The current material conjunction supports one original catalog
root and one supplied whole-graph case. An empty catalog or a self-authored
candidate fingerprint cannot supply missing authority.

Delivery grouping uses the distinct nested schema
`biocompiler.policy_delivery_group.v0.1`. It retains explicit recipient roles,
co-delivery mode, same-recipient identity, counts and length bounds. Its empty
assumption inventory is meaningful: this profile has no interpretation for
additional opaque assumptions and rejects them. The legacy architecture group
requires a nonempty assumption list and keeps that behavior; its schema is not
silently reinterpreted by this new profile. Native controls cover both boundaries.

The separate, untrusted candidate uses
`biocompiler.policy_material_candidate.v0.1` and exactly:
`schema_version`, `behavior`, `implementation`, `binding`, `material_binding`,
`construction`. The operational behavior is checked against the external original
source; its embedded source is not allowed to replace that original. The graph
binding uses `biocompiler.policy_implementation_binding.v0.1`; the material node
bijection uses `biocompiler.policy_material_binding.v0.1`. Source-neutral
construction content is checked under the exact supplied template roots, rather
than being granted a fabricated legacy circuit authority.

Per-invocation preservation `limits` remain separately supplied and use
`biocompiler.policy_preservation_resources.v0.1`. They bound source execution,
candidate execution, the independent requirement monitor, per-step work/retention
and complete report publication. They never shorten the original domain or
weaken its assurance horizon.

The [request decoder](../core/lib/domain/policy_material_request.mli),
[material contract](../core/lib/domain/policy_material_contract.mli) and
[context decoder](../core/lib/domain/policy_material_context.mli) define these
closed representations. Decoding establishes bounded shape and identities, not
accepted compilation.

## Independent checking and the original obligation inventory

The [coordinator](../core/lib/realization_checker/policy_material_check.ml)
re-decodes the original request and requires the following conjunction:

1. Fresh source admission and source-to-behavior correspondence, followed by
   independently reconstructed source-to-graph bindings. Actual ports, wires,
   configurations, scopes, rule order and source occurrences are checked; source
   path labels are not proof.
2. Exhaustive traversal of the original finite causal input domain. Source and
   candidate runtimes execute independently, exact ordered observable traces are
   compared through creation-time identity correspondence, and a separate monitor
   checks every original hard requirement. Complete coverage and real effect,
   active and inactive witnesses are required. Failure, UNKNOWN, unsupported
   requirements or incomplete traversal cannot produce a checked implementation.
3. The original catalog-to-material bridge and a total ordered bijection between
   the actual graph and supplied material kernel. Complete models, configurations,
   replication, wires, inputs, atomic groups, semantic exports and slot layout
   must match. Every corresponding material target requires a disposition under
   the supplied case.
4. Fresh construction reconstruction and mRNA structural checks, followed by
   exact whole-molecule comparison to the case's independent material key. The
   supported structural profile requires complete linear coding RNA, the four
   required regions, ordinary standard-code translation with supplied product
   authority, exact represented terminal tail, declared chemistry and checked
   coordinates/derivation. Unknown or unsupported material content is not complete.
5. Original context checking: concrete executor recipient and compartment,
   exact clock relation, complete original provider references, input grammar,
   causal delivery/activation, inclusive availability, exact payload cardinality
   and sufficient complete-record resource capacities.
6. A disposition for every obligation from the fresh original source assessment.
   Each discharge retains the applicable preservation, material and/or context
   evidence fingerprint. An unknown additional obligation remains unresolved even
   when all earlier leaves pass.

Only the coordinator can construct its private `checked_material` value. Every
failed or incomplete stage that returns a report retains the full original
obligation inventory with unresolved dispositions. Malformed authority and
resource exhaustion may instead raise a diagnostic without returning a report
or accepted value. Neither route may turn a missing obligation into success.

The report schema is `biocompiler.policy_material_assessment.v0.1`. Its status is
`checked_material` only after the full conjunction; otherwise it is
`not_accepted`. Stage outcomes remain separately visible as `pass`, `fail`,
`unknown`, `unsupported` or `unassessed`, as applicable. The report's claim is
`bounded_conditional_policy_to_exact_mrna`, with premise
`supplied_model_to_sequence_and_provider_contracts`. Even a checked report keeps
`artifact: withheld` and `export: withheld`; only a new export invocation may
produce an artifact.

The [producer](../core/lib/producer_service/policy_material_producer.ml) lowers
source, selects exactly authorized model configurations, proposes a bounded
complete graph arrangement and constructs template content. It then invokes the
same checking service. Standalone Verify does not link this producer. A producer's
search exhaustion is not evidence of global impossibility, and a plausible graph
arrangement does not bypass source order or independent material checking.

## Resource meaning and work accounting

Formal component capacities are distinct from software execution allowances.
The context profile counts truth cells, evidence records, edge-history cells,
generation counters, active-attempt records, retained historical correlations,
timers, control-event records and input rows per tick. Each demand is scoped per
executor or per concrete encounter slot. Shared capacity pools are summed;
separate allocations cannot consume the same pool as though it were unshared.

Records retain their complete semantic contents, including three-valued truth,
ordered reasons with duplicates, subject/generation identity, complete evidence
timestamps, correlated attempt state, authorization, causal events and products.
The independently checked record layout pins the kernel/domain, slots,
generations, attempt bound, horizon and maximum tick, ordered reason/cause widths
and identifier bytes. Capacity is not just the number of containers. It is also
not RNA copy number, dosage, a software trace limit or empirical memory capacity.
The [context checker](../core/lib/realization_checker/policy_material_context_check.ml)
derives demands from the actual graph and the entire original input grammar.

The candidate interpreter also retains validation bookkeeping. Its global sets
of seen observation/feedback occurrence IDs serve only duplicate-input guards
and diagnostic fingerprints. For the admitted domain, the independent source
and candidate adapters generate disjoint `domain/observation/<tick>/<index>` and
`domain/feedback/<tick>/<index>` identities. Each cursor advances once per tick,
so IDs remain unique across reset generations and repeated feedback. These sets
cannot change admitted observable behavior and are not material state demands.
This argument does not apply to arbitrary external timelines or a later input
grammar. Work/retention accounting is likewise software validation state;
exhaustion remains incomplete. Event ordinals, attempt allocation, logical time,
encounter generations and retained correlations remain semantic state and keep
their explicit material dispositions.

The coordinator's explicit work unit is
`logical_data_visits_and_child_semantic_work`. It comprises:

- Bounded preflight JSON value/key, list-edge and ancestor-identity visits, plus
  scalar string and decimal-spelling bytes.
- Explicit canonical encoding, hashing and publication byte passes at the
  coordinator boundary.
- The child checkers' own declared semantic work, including fresh preservation
  traversal and nested material/context work.

This is an aggregate logical-work metric, not an estimate or ceiling on native
CPU instructions. Original decoder and per-stage hard limits remain active.
Protocol ingress and producer search retain their own limits; this report does
not claim that all process overhead is measured by the coordinator's counter.

The material budget exists before the coordinator's fresh `R.of_json` decode.
The decoder preflights its full original input and each child decoder input,
charges exact original encoding/hash bytes, and exposes `decoding_work`.
`Policy_preservation_check.check_with_startup_charge` adds enclosing preflights
before admission, graph binding, runtime/reference initialization and initial
identity passes. Default `check` retains its existing signature, behavior and
report. The coordinator reserves the entire original preservation allowance,
rechecks that reservation after startup charges, and charges actual child work
afterward. The allowance does not change the source request.

Original request decoding retains the fixed 4,000,000-byte, 100,000-node and
96-depth limits. General coordinator preflight can explicitly use the protocol
ceiling of 8,388,608 bytes, 250,000 nodes and depth 128. Final material service
publication is tighter: 8,323,072 bytes and 249,968 nodes, including its result
framing. Complete evidence is reserved and checked; it is never truncated to fit.
Private acceptance is constructed only after the coordinator's publication
reservation succeeds. The service also checks the complete candidate/report and,
when exporting, full manifest/FASTA wrapper.

The report records `usage.unit`, `usage.charged_work` and
`usage.request_decoding_work`. The frozen complete-original fixture has an
independently calculated decoder census of **480,645 logical units**. Native
controls require that exact allowance to succeed and 480,644 to fail. A separate
literal `{"a":[true,12,"x\n"]}` has 16 logical units and 21 canonical bytes.
These are fixture/accounting calibrations, not hosted execution receipts.
The census was 480,657 before the context delivery-group codec correction.
The context-owned `biocompiler.policy_delivery_group.v0.1` schema retains the
same fields and modes while permitting an empty assumptions list. The context
checker still rejects opaque nonempty assumptions. The legacy delivery-group
codec is unchanged; its nonempty-assumptions requirement cannot represent this
context profile. Only the schema text, context/request identities and the exact
12-unit accounting difference changed in the complete request fixture.

The Python transport retains the complete original context-obligation inventory,
its disposition and all original provider pins in discharge evidence. A passing
context report must retain every original allocation, in order, with its demand,
provider, capacity, pool and reserved quantity. Its derived demands must preserve
the original unit/scope/owner inventory, with positive quantities within the
supplied reservations; Python does not recalculate the native lower bounds.
Failed checks may retain partial demands and an allocation prefix; their full
source ledger remains outside this stage and no
context discharges are claimed. These are evidence-retention checks; capacity
sufficiency and operational semantics remain independently checked in OCaml.

## Public operations, identities and fresh paired export

Negotiation requires exact `policy_material` and, for compilation,
`policy_material_producer` profiles. The validation scope is
`policy-truth-mrna-v0.1`, service implementation
`biocompiler.ocaml.policy_material.v0.1`, and result schema
`biocompiler.core.policy_material.v1`.

| Native operation | Executables | Exact payload |
| --- | --- | --- |
| `compile-policy-material` | Core | `request`, `limits` |
| `check-policy-material` | Core, Verify | `request`, `candidate`, `limits` |
| `replay-policy-material` | Core, Verify | `request`, `candidate`, `limits`, `report` |
| `export-policy-material` | Core, Verify | `request`, `candidate`, `limits` |

Replay's `report` is the entire saved non-export result wrapper, not its inner
assessment. Replay recomputes the complete wrapper and requires canonical
equality, including profile, authority, candidate and evidence. An export wrapper
is not a check receipt. Export takes no saved report or serialized acceptance.

Four distinct fingerprints are retained: complete original request; complete
candidate including its schema; invocation `{request,candidate,limits}`; and
complete report. Declaration-content identity remains separate from full source
artifact identity. Source-map or provenance edits may preserve declaration
meaning but still change the original authority and invalidate old behavior,
graph bindings and receipts. Rehashing an edited claim cannot make it accepted.

Fresh export reconstructs the complete conjunction again, obtains the private
accepted content, and returns `biocompiler.policy_mrna_export.v0.1`. Its exact RNA
FASTA uses stable `rna_0001`-style identifiers, ordered members, 80-column wrapping
and explicit newlines. The `biocompiler.policy_mrna_manifest.v0.1` contains the
entire original request, complete candidate, limits, fresh assessment, four
identity bindings, complete molecular records and sequence/FASTA hashes. The
outer export hashes exact canonical manifest bytes; no self-hash is embedded.
Original authority must still be supplied independently for future checking.

The [immutable SDK](../src/biocompiler/core_policy_material.py) snapshots request
bytes before negotiation/calls and checks exact profiles, identities, full
obligation/stage consistency and the exact artifact pair. It performs transport
and consistency checking, not Python policy execution. Missing/wrong binaries,
unsupported profiles, timeout, cancellation and protocol failures have no Python
semantic fallback. `prepare_request` in the
[inert public helper](../src/biocompiler/policy/material.py) only freezes authority.

The CLI exposes `compile-material-native`, `check-material-native`,
`replay-material-native` and `export-material-native`. All take the original
request path and `--limits`; checking/export also require `--candidate`, replay
also requires `--report`. An explicit `--core` or supported `--verify` is required;
Verify cannot compile. Export requires a `.zip` `--output` for one inseparable
`program.fasta`/`manifest.json` pair. Existing destinations require `--replace`.

Publication stages a stored ZIP in the destination directory with fixed member
order, names, timestamps and permissions, flushes/fsyncs it, then reads back the
bounded archive and verifies complete bytes and metadata. It rejects input
aliases, symlinks and changed destinations. An atomic exclusive link publishes a
new output; explicit replacement uses an atomic rename. Prepublication failure
preserves prior output and removes the staging file. This is atomic paired
publication, not a claim of directory-fsync crash durability.

## Current witness, unsupported scope and acceptance gates

The [complete request fixture](../core/test/data/policy_material_request_v01.json)
has request fingerprint
`754a3a30752855c3e9458c0b657a2e7ac850d6aebb27e260009e331296341e36`.
It independently retains the resolved exclusion source, catalog, domain, graph,
material/context authority, complete molecule and 23 original obligations. Only
its untrusted operational behavior is produced natively. Its authored positive
census is nine histories, 47 transitions, 48 prefixes, 15 graph nodes and 92
material dispositions. Context controls include 14 demands over 13 capacity
records and one shared truth pool. These are expected values, not a PASS receipt.

The original source with unresolved/UNKNOWN safety remains a separate negative
family. The coordinator also adds a hard UNKNOWN or false requirement without
removing an old requirement or narrowing the domain; neither can cross material
acceptance. An extra unrecognized semantic definition must leave its obligation
open even if preservation, material and context individually pass.

A hosted implementation-domain regression exposed a monitor initialization
allowance of 100,000 that could not encode the complete binding report before
exploration. The positive fixtures now explicitly supply 1,000,000. Source,
domain and requirements are unchanged; tiny-monitor controls remain and must
return incomplete coverage with no acceptance. The allowance correction alone
does not establish acceptance.

The integration owner subsequently verified the early Linux and macOS suites in
[run 37418186608](https://github.com/logannye/biocompiler/actions/runs/37418186608),
source `d982d58642d94f9d9c798f20bc672fcc69d1f04f`: source/source-graph checks,
trace correspondence, lowering, independent monitor, whole-domain preservation
(nine histories, 47 transitions, 48 prefixes and 22 negative controls), and the
implementation service passed. The suites then stopped at a construction-test
expectation: the producer correctly reported earlier
`member:payload:unavailable_value` and `step:step:residue_budget` diagnostics,
rather than the later bundle-residue diagnostic. Test-only correction
`1eeb05817ce73a27a3ef5df109336ddb70d35de7` pins those exact earlier failures and
adds a separate two-member `6 + 6 > 6` aggregate-bound control. No production
semantics changed in that correction. Its hosted validation and all subsequent
material/context/coordinator/service/export gates remain pending here. These
partial native results cannot stand in for the complete run or material release.

Subsequent hosted runs passed all earlier focused suites, including 47
construction/legacy-equivalence checks, 129 mRNA structural checks and 32 material
binding controls. The first context run then exposed the legacy delivery-group
decoder's incompatible empty-assumption rule. Its exact diagnostic was retained
from source `994c9247c8c6371802608efc371f012054b36110`, run `37419361828`.
The separate nested policy schema above fixes the new context boundary while
preserving legacy decoding. The complete original fixture and its fingerprints
and decoding calibration are updated together; source/domain/material authority
is unchanged. This correction still requires fresh hosted validation.

The earlier installed implementation campaign reached its malformed-replay
control but omitted the CLI's `--json` option while requiring a JSON diagnostic.
The campaign now requests that format explicitly. Installed log artifacts are
retained before the longer campaigns so future failures expose their exact
cause promptly. The full original campaign remains required.

Retained-output validation additionally requires the export CLI's publication
helper origin and complete context obligation, provider-discharge, derived-demand
and allocation inventories. Inert adversaries update all four slot fingerprints,
wrapper/manifest identities and ZIP bytes after truncating those inventories;
the missing evidence must still be rejected. These are transport-completeness
checks, not Python reimplementations of native capacity or policy semantics.

The installed campaign now rebuilds the original policy through the reviewed
Python `ProgramBuilder` witness, attaches separately supplied realization and
catalog records, and uses both public request-preparation helpers. It requires
exact equality with the separately retained full original request before the
native semantic execution guard is installed. The authoring receipt identifies
the recipe, adapter and complete source/request contents. Construction-time
structural checks do not supply runtime semantics or native acceptance.

At source `46fb5a5c9fded877866d333f0e1e8aef75a9fe5b`, hosted run
`37420548147` passed the focused suites through all 124 context controls on
both platforms, then failed the coordinator's literal obligation census.
Independent review of both source validators shows 23 original obligations:
the fixture incorrectly included `persistent_encounter_identity_lifetime`,
which is emitted for persistent state associated with an encounter. This
source has encounter-lifetime stores. The correction removes only that extra
expected fixture entry; it preserves every original request field, checker
obligation and the 480,645-unit decoding census. Full native coordinator,
service and installed material acceptance remain pending.

Source `5e26a18d999328932dbc78cd1182b648d73b38ee`, hosted run `37421588095`,
subsequently passed all 100 coordinator controls on both native platforms.
The service test then failed an order-sensitive OCaml equality comparison of
JSON molecule objects. Its corrected comparison uses canonical JSON equality,
preserving every value and ordered array while ignoring object-key order.
Service completion still requires fresh hosted execution.

The next correction also rejects unsupported nominal references on durations
before bounded operational admission. Generic source units retain their
nominal reference field; the bounded clock cannot silently discard it during
amount/scale conversion. Equivalent exact seconds/milliseconds remain a
required positive control. A source-location-only service control requires old
candidate/report rejection and fresh accepted export with unchanged FASTA but
changed full request, candidate and manifest identities. Native execution of
these added controls remains hosted work.

ZIP publication now verifies every byte of the fixed stored archive, including
local headers, against the native FASTA and manifest. It does not rely on the
ZIP parser's central-directory metadata to validate local timestamps, versions
or CRCs. Pure-Python corruption controls preserve prior output and remove the
unpublished stage. The nested transport fixture also registers cleanup with
its owning test, preventing patched assessments from leaking to later tests.

The first-profile witness audit uses coherent source/model/material families
for authorization and uncertainty alternatives before timeout, compound
`all`/`any` guards with explicit Unknown state, and distinct delivery providers
with matching full phase relations. Re-pinned near-neighbor mutations must fail
at the relevant semantic checks. Primitive-only tests and rejected stale pins
do not close these SM-08 coverage obligations.

The Verify-only consumer campaign stages unmodified installed transport modules,
one pinned verifier and separate original/proposal/expectation files. It runs
Python with isolated/no-site flags, denies other imports and executable launches,
checks the complete staged byte inventory, and freshly checks, replays and exports
before comparing complete evidence. Core and producer modules are absent from
the staged directory; the host filesystem is explicitly not isolated. Linux
uses an inherited kernel syscall filter and macOS an inherited sandbox network
policy, each with IPv4/IPv6 denial probes. Required mode fails if enforcement is
unavailable. Explicit deferred mode cannot pass the four-slot offline gate.
This new campaign is source-ready and requires hosted execution on both systems.

Additional native witness sources now cover distinct delivery providers with
the same complete phase relation, re-pinned phase disagreement and channel
conflicts. Four complete lifecycle cases cover initiation/continuous
authorization crossed with continue/defer uncertainty response. Each supplies
its own exact material case under one authorized model library, retains all
original hard requirements and independently enumerates 54 histories, 176
transitions and 177 prefixes. Literal histories distinguish missing, invalid,
conflicting, stale and false evidence while attempts remain active, correlated
feedback and quiet-time timeout. Cross-case material substitution must reject
even when every RNA base is identical. These controls passed on both native
platforms at source `3044e9d62a4c16cc294e4110ab521b019537298d`, run
`37423025439`: 137 context controls, 100 coordinator controls, the complete
service/replay/export suite and 1,519 lifecycle assertions. This is partial
hosted evidence; it does not establish the full release gate.

A further source-ready compound family supplies two complete graph/material
cases with nested `all`/`any` guards and assignments. Both begin with explicitly
defined Unknown state; evidence absence retains its separate representation.
The cases preserve one versus two ordered uncertainty reasons, including repeated
reasons from repeated expression occurrences. Each retains the original three
hard requirements and the independently counted 54 histories/176 transitions/
177 prefixes. Literal state, assignments, authorization, resource minima and
record widths are checked independently. Operator/operand/state mutations,
lost reasons, insufficient re-pinned storage and substitution of a different
fully pinned graph case must reject even with identical RNA. These additional
native tests remain hosted-pending.

The initial family remains narrow: one executor, explicitly named finite
encounters, one truth observation, one or two encounter-scoped truth stores,
one or two exclusive rules and one fixed product-bearing effect bank. The
material/context route supports one exact complete RNA/product, no delivered
helper, exact supplied human immune in-vivo RNA context, and a single supplied
whole-graph case. Supplied context is a formal premise. No disease response,
biological state transition or therapeutic effect is inferred from these labels.

Review after the passing partial run found that abstract-effect formal
parameters were structurally type-checked but exempt from executable admission
restrictions. Their design/measured/uncertain selection or non-null default was
not interpreted. The bounded profile is being closed to signature-only formals:
fixed selection and null value/lower/upper. Generic source authoring remains
expressive. Source-valid mutations with all affected definition identities
refreshed must reject at the new admission guard, rather than at a stale pin.
At source `2349d8ad9fdf5209f241ab22bb48bf87600f3f9f`, hosted run
`37429106811` passed these 20 formal-parameter controls, 23 additional original
source/admission/domain controls, native compilation and all preceding material
and lifecycle suites on both platforms. The following compound suite exposed
a fixture serialization error: material-kernel wires used implementation-wire
keys instead of the material contract's required `from`/`to` keys. Its correction
retains the original policy, actual graph, RNA and every native assertion, while
refreshing the affected material/provider/context/request identities. That
correction and the complete release gate still require fresh hosted validation.

Three additional full original material requests extend the public compile,
independent check, replay and fresh-export witness coverage. They retain the
original three hard requirements and independently enumerated evidence or
lifecycle choices: 54 histories/227 transitions/228 prefixes for extended
evidence, 27/87/88 for reset/end plus old feedback, and 486/995/996 for reset
followed by a new attempt. The final family retains all old-attempt feedback
choices and checks new-generation correlation, completion, failure and quiet
timeout. Fixed occurrence identities and complete resource dispositions are
checked explicitly. These are tests of already admitted meaning under supplied
contracts; native execution remains pending.

The same batch adds twelve source-valid contextual rejection controls and six
requirement-monitor controls. Fresh source admission, occurrence accounting and
graph correspondence precede the latter checks; each original requirement is
retained and its exact unsupported reason is checked initially and through the
declared horizon. The contextual inventory now indexes 23 witness files across
62 rule families and preserves 16 explicitly partial families. Broader
operational coverage and unindexed first-profile branches remain visible; this
static inventory is not an execution receipt.

Additional numeric/quantity domains, machines, predicate resets, coordination,
quantification, inheritance, complex spatial relationships, broader arbitration,
multiple initiating gates per bank, independent delivery, helper closure,
multiple RNA/product architectures, recoding/modified-CDS semantics and general
component composition need explicit vertical extensions. Uninterpreted source
assumptions/tolerances, dependency/evidence closure and payload-dose/persistence
fields cannot silently become supported. General search or mechanism discovery
is not implemented by the single-case arrangement producer.

All four release gates remain pending for this material increment:

| Gate | Required evidence |
| --- | --- |
| Complete checks | Required source-authority, protocol, library-boundary, Python/type/static and native mutation suites, with no dropped legacy tests |
| Hosted native | Exact-source Linux x86_64 and macOS arm64 compilation, executable tests and actual Core/Verify identities |
| Installed four-slot | Both platforms × Python 3.11/3.14 outside the checkout, semantic fallbacks forbidden, full SDK/CLI/check/replay/export cases and independent complete-output/artifact comparison |
| Aggregate/integration | Successful exact-revision aggregate and required integration/main gates, preserving source commit, tested checkout/tree, run/attempt, platform/toolchain and binary provenance |

The [installed material campaign](../tools/check_policy_material.py) and workflow
wiring are source implementations. Receipt comparison must reject missing,
duplicate, stale, failed or altered slots and must compare complete retained
semantic outputs and artifact bytes. Existing source-only, operational and
implementation-only profiles keep their own claims and acceptance records.
The reference-package route already has source implementations in its preserved
continuation; compatibility/hosted acceptance remain with its owner.

SM-08.7 now reuses the distribution foundation from continuation revision
`b7a176dd5c75e700b9aa86ac8006b70fcb3eaf57`, with per-file provenance in
[`policy-material-distribution-foundation-provenance-v1.json`](../protocol/policy-material-distribution-foundation-provenance-v1.json).
The initial foundation adaptation corrects the reviewed SDK entrypoint expectation
to `biocompiler.entrypoint:main`. A subsequent source-acquisition correction adds
a byte-pinned GMP mirror and bounded network retries, with retained attempt
diagnostics; original archive hashes, sizes and notices remain unchanged.
The resolver remains opt-in. The material lane does
not invoke the copied migration pipeline's legacy installed/aggregate campaigns.

Hosted validation will prepare locked static dependencies, compile and test the
actual binaries, audit their final linkage/material closure, and package those
same bytes. One SDK wheel binds both platform manifests. Four fresh wheel-only
install slots check owned RECORD/release identities, explicit material profile
negotiation, full SDK/CLI compilation and required offline standalone verification.
Installation-specific mutations and uninstall/missing/reinstall controls must
reject or restore exact ownership as specified. An independent comparator binds
complete original material/consumer receipts to the supplied wheels and source
revision. Producer and consumer run attempts are retained separately; only an
already successful earlier attempt of the exact same run/source may be reused.
Every new job and slot is mandatory in the existing aggregate gate. These are
source implementations awaiting hosted packaging and installed acceptance.

Immediate next work is to run the coherent material batch on hosted native
targets, repair any failures without weakening original authority or controls,
complete the four installed campaigns/comparator, and record exact aggregate
evidence. Then verify packaged/offline routing and fresh export outside the
checkout before closing any SM-06/07/08 exit. Each SM-09 expansion must extend
source semantics, graph lowering/runtime, preservation, material/context
contracts and public profiles together, with new accepted/rejected witnesses.

Implementation/test entry points:

- [Preservation startup/accounting](../core/lib/realization_checker/policy_preservation_check.mli),
  [material leaf](../core/lib/realization_checker/policy_material_binding_check.mli),
  [mRNA structure](../core/lib/checker/policy_mrna_structure_check.mli).
- [Fresh native service](../core/lib/service/policy_material_service.ml),
  [coordinator controls](../core/test/test_policy_material_check.ml),
  [service/export controls](../core/test/test_policy_material_service.ml).
- [Context controls](../core/test/test_policy_material_context.ml),
  [transport controls](../tests/test_core_policy_material.py),
  [atomic/readback controls](../tests/test_policy_material.py),
  [CLI controls](../tests/test_policy_material_cli.py).
- [Hosted validation rules](development-validation.md) and
  [workflow](../.github/workflows/ci.yml). All native compilation, execution and
  packaging remain hosted; local static/Python checks do not validate changed
  native source.
