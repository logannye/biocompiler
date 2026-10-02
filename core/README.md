# OCaml core

The native migration implements bounded strict JSON, Python-compatible canonical
fingerprints, checked domains and independent frozen source-to-Behavior
correspondence. Internal libraries add per-role reference execution and fresh
Intent-to-Behavior lowering. Validated domains include shared content pins, component contract algebra,
molecular provenance and nominal chemistry. PR42 also validated complete
component records, human source wrappers, molecular sets and supplied deployment
windows. PR43 declarations and required-region checks and PR44 independent reconstruction/source checks passed complete PR validation; full architecture acceptance remains pending validation. The
public protocol does not yet implement compilation, behavioral execution,
molecular verification, export acceptance or human-use admission. Capabilities
are explicit; unimplemented operations return `unsupported` without fallback.

The protocol is one UTF-8 request on stdin and one response on stdout. Both
executables use `biocompiler.core.v1` and identify their distinct executable role.
Nonzero exit codes accompany structured errors (2) and unsupported operations (3).
There is no Python semantic execution or runtime network request in either binary.

Libraries have explicit dependencies. `bioc_checker` depends on immutable
domain/wire modules and the pinned Zarith numeric primitive. `bioc_service` exposes that checker; the standalone verifier
has no dependency on a compiler, selector, matcher, assembler or emitter.
The producer library `bioc_compiler` depends on the checker for its final
correspondence check; the checker has no reverse dependency. Reference execution
also remains separate. The shared JSON codec, canonicalizer, numeric conventions
and domain validators are part of the common trusted base, not independent
execution evidence.

PR37–40 are merged after complete required validation. PR40 source `e4846f0` passed [run 36935066451](https://github.com/logannye/biocompiler/actions/runs/36935066451), including 12 native suites, 936 protocol checks and 2,095 tests on each Python version. Its separate [post-merge main run](https://github.com/logannye/biocompiler/actions/runs/36936774523) also passed every required gate. PR41's lowering and domain batch is merged after all 17 native suites, 2,122 tests on each Python version and every required product gate passed. Its separate integrated-main run 36937189850 also passed every required gate. No production routing or public protocol operation is enabled by these internal domain increments.

## Hosted validation

Native builds run on the approved hosted validation environment. Do not install a
local toolchain or run native builds as a side effect of Python checks.

With OCaml 5.4.0 and dependencies from `biocompiler_core.opam` installed:

```sh
opam exec -- dune build --root core @all
opam exec -- dune runtest --root core
```

Build outputs are `core/_build/default/bin/core/main.exe` and
`core/_build/default/bin/verify/main.exe`. Installed executable names are
`biocompiler-core` and `biocompiler-verify`. Direct dependency versions are pinned;
the hosted solve must retain its full transitive opam lock and platform/build
receipt before a release is considered reproducible.

The wire parser preserves integer/floating-point/Boolean distinctions and
arbitrary-precision integers within the advertised lexical limit. It rejects
duplicate keys, invalid UTF-8 or surrogate escapes, nonfinite numbers, excessive
depth, string length, item counts and bytes. JSON item accounting counts values,
not object keys; root depth is zero. This stricter UTF-8 wire profile is explicit.

Canonicalization follows existing Python JSON representation rather than RFC
8785: integers remain integers; floats use shortest round-trip decimal spelling,
signed floating zero is retained, keys sort by Unicode scalar order and output is
UTF-8. Float digit selection uses exact rational decimal rounding, followed by a
binary64 round-trip check and Python's fixed/scientific thresholds. Cross-language
fixtures must confirm byte and hash parity before production promotion.

Intent validation checks the current intent document schema, graph references,
acyclicity, role targets, names, dimensional types, bound parameters, intervals,
curves, source locations and registered unit conversions. Unknown operation names
remain descriptions just as in the existing `IntentProgram`; this operation does
not validate their behavioral meaning. A successful structural report never
becomes a translation certificate.

## Domain migration

The internal domain and checker modules prepare the stateful architecture checker:

- `Build_request` freezes independently resolved parameters, target declarations,
  source provenance, constraints and preferences. Semantic identity excludes
  source locations and archival timestamps; artifact identity includes them.
  Target declarations and evidence references do not establish admission.
- `Behavior` represents v0.1/v0.2 operations as closed variants with hidden
  constructors. Import checks operation types, ownership, policies, constant
  expressions, contact binding and complete requirement/source lineage. It does
  not lower intent, execute a timeline or compare a molecular candidate.
- `Molecule_coordinates` validates nominal frames, alphabets, axes, topology,
  half-open spans and disjoint ordered paths. Bounded position enumeration
  preserves segment order and strand. It does not emit or transform symbols.
- `Type_spec.normalize_binding` reconstructs valid serialized bindings using
  the existing unit conventions, preserving integer/float and signed-zero forms.
- `Circuit_request` preserves circuit/profile/recipient and executable-output
  declarations with their complete source authority. The current structural increment preserves typed human behavior, deployment
  and acceptance wrappers in full, including their source/target/contract pins;
  downstream implementation and empirical obligations remain explicit. A
  projected nested BuildRequest never replaces complete wrapper authority.
- `Lowering_check` independently compares a supplied Behavior with a separately
  frozen BuildRequest, accounting for every operation, binding, requirement and
  source correspondence. Its abstract report binds full and semantic identities
  and carries all remaining execution, realization and acceptance obligations.
- `bioc_compiler.Lowering` produces a complete Behavior from a frozen
  BuildRequest. It implements its own policy rewrites, binding substitution,
  ancestry, contact and requirement derivation, then requires `Behavior`
  validation and independent `Lowering_check` against the original request.
  It does not select components or emit molecular candidates.
- `Pinned_identity` is the shared immutable model/reference/registry/source/
  evidence content pin. Parsing a pin establishes neither content availability
  nor support for a claim.
- `Component_contract` checks value domains, archived domain-check claims,
  operating domains and ports. Its Boolean/closed-interval/unknown algebra uses
  exact types and explicit units, checks initialization separately from runtime
  inclusion, and covers all 13 synthetic domain operations. Imported claims
  cannot construct the abstract fresh-assessment type. Complete component records passed PR42; architecture
  refinement/template reconstruction remains unfinished.
- `Diagnostic_text` fixes missing-coordinate diagnostic spelling to
  `python_repr_unicode14.v1`. See the deliberate compatibility exception below.
- `Molecular_record` applies molecular resource/text/serialization bounds and
  checks `Provenance` declarations using shared pins. Declared or unknown
  provenance remains supplied metadata, not independently established evidence.
- `Molecule_chemistry` checks chemical identities, claims, modifications, tail
  lengths, terminal tails and complete chemistry declarations. `validate_for`
  checks their consistency with supplied coordinates, alphabet, sequence and
  complete/exact-core extent. Nominal chemistry identity is distinct from
  provenance completeness, transformation correctness and empirical function.
- `Execution_data` provides abstract finite samples, input frames, actions,
  events and complete traces. Its strict internal codec rejects missing/unknown
  fields, duplicate mappings and excessive serialized inventories. This is a
  narrower native import boundary than the permissive Python trace dataclasses.
- `Runtime_number` preserves integer/float distinctions, exact mixed comparison,
  integer true division, signed zero and correctly rounded accurate summation.
  Like the existing evaluator, arithmetic must retain a finite binary64
  conversion; a positive timer duration must advance representable time.
- `bioc_semantics.Reference` evaluates both closed Behavior profiles in fresh
  sessions, with eager temporal evaluation, atomic state updates, causal memory
  settlement, contact identity, exact event/pulse boundaries and sampled
  integration. Cumulative work, frame, transient action/event and serialized
  output limits reject excess without a partial successful result. This library
  has no producer or candidate-runtime dependency and is not exposed by the
  service or standalone verifier. Declared channels remain supplied per-role
  observation/action endpoints; coupled transport is a later architecture layer.

PR42 validated these structural APIs:

- `Measurement_contract`, `Human_contract` and `Human_request` validate normalized
  measurements, complete behavior/deployment/acceptance declarations, their exact
  nested source correspondence and separate semantic/artifact identities. Circuit
  decoding preserves the whole typed source and checks original deployment and
  recipient identities. Structural validity does not implement an actuator,
  assess empirical evidence or make a symbolic human profile executable.
- `Component` retains all eight record families and the shared pin type. Complete
  synthetic models validate port census, role/scope, event timing, literal types
  and output-domain compatibility. Imported component declarations remain distinct
  from fresh local assessments and full architecture acceptance.
- `Molecule` checks covalent molecules, complete assembly partitions, features,
  complex constituents and role/form declarations. `Molecule_set` binds every
  member, coordinate frame, source request and role to its exact authority. Its
  nominal species/bundle identities preserve chemistry and role multiplicity;
  artifact metadata remains separate from experimental specification identity.
  These APIs inspect supplied records; construction and emitted-base checking
  remain later responsibilities.
- `Architecture_deployment.Time` preserves original numeric authority while
  comparing exact decimal seconds like `Fraction(str(value))` in the existing
  checker. Availability and requirement records retain unknown contextual
  outcomes such as empty common overlap. Their structural import is not a fresh
  deployment assessment.

The validated PR42 corpora retain 40 human-wrapper records, 244 staged rejections and four independent literals; 60 component records, 112 rejections and 42 fresh domain assessments; and 109 molecular records, 136 rejections and 16 identity relations. Deployment coverage adds 15 records, 78 rejections, 18 exact decimal ratios and six independent sum boundaries. The original wrapped eight-member molecular example and all nine case B root/set/final occurrences remain intact.

PR42 passed 22 native suites and 2,155 tests per Python version; [receipt](../protocol/migration-complete-domains-validation.json). Its separate integrated-main run 36940233185 also passed every required gate. In addition to the earlier
commands below, hosted CI must execute these complete new corpora:

```sh
core/_build/default/test/test_component.exe "$GITHUB_WORKSPACE/tests/conformance/components-v1.json"
core/_build/default/test/test_human_wrappers.exe "$GITHUB_WORKSPACE/tests/conformance/human-wrappers-v1.json"
core/_build/default/test/test_molecule.exe "$GITHUB_WORKSPACE/tests/conformance/molecules-v1.json"
core/_build/default/test/test_molecule_set.exe "$GITHUB_WORKSPACE/tests/conformance/molecules-v1.json"
core/_build/default/test/test_architecture_deployment.exe "$GITHUB_WORKSPACE/tests/conformance/architecture-deployment-v1.json"
```

The validated PR43 batch adds `Architecture_contract` (12 structural record types),
`Molecular_transition` and `Molecular_recoding` (eight closed declarations and
64 immutable codons), `Payload_structure`, `Construction` (30 schemas and 14
operation variants) and `Construction_artifact` (four unchecked record types).
`Circuit_request.Product`, `Lifecycle`, `Provider` and complete requirement
provider access expose the existing checked authority without narrowing it.
Parents reserve aggregate child representation before retaining expanded lists.

The independently implemented `bioc_checker.Payload_structure_check` compares
complete molecule sets with separately supplied required-region contracts. It
retains contradictions and unresolved obligations separately. Contract parsing,
region correspondence, complete construction, source behavior and empirical
acceptance remain different responsibilities. This checker imports no producer
and exposes no public protocol operation yet. Full construction reconstruction
and architecture acceptance remain open.

Frozen corpora retain 88 architecture positives/345 rejections/four literals; 153 transition and recoding positives/199 rejections/six literals; 14 payload-structure positives/44 rejections; 72 construction positives/245 rejections; 36 candidate-artifact positives/70 rejections/four literals; and 99 required-region checks, including 27 source-preserving mutations. All three original case B requests, candidates and region contracts remain represented. All 28 native suites and every required product gate passed in PR43, with 2,207 tests per Python version; [receipt](../protocol/migration-construction-domains-validation.json). Separate main run 36943390725 also passed every required gate.

That hosted gate includes 28 native suites, including these six
required corpus replays in addition to all prior gates:

```sh
core/_build/default/test/test_architecture_contract.exe "$GITHUB_WORKSPACE/tests/conformance/architecture-contracts-v1.json"
core/_build/default/test/test_molecular_transitions.exe "$GITHUB_WORKSPACE/tests/conformance/molecular-transitions-v1.json"
core/_build/default/test/test_payload_structure.exe "$GITHUB_WORKSPACE/tests/conformance/payload-structure-v1.json"
core/_build/default/test/test_construction.exe "$GITHUB_WORKSPACE/tests/conformance/construction-v1.json"
core/_build/default/test/test_construction_artifact.exe "$GITHUB_WORKSPACE/tests/conformance/construction-artifacts-v1.json"
core/_build/default/test/test_payload_structure_check.exe "$GITHUB_WORKSPACE/tests/conformance/payload-structure-check-v1.json"
```

The diagnostic profile is an intentional compatibility exception. Python repr
uses the host Unicode database; native missing-coordinate reasons use a complete,
fixed Unicode 14 printability table. Newly assigned Unicode 15/16 characters
therefore stay escaped, which can change reason text and fresh assessment hashes
relative to newer Python versions. Semantic status and raw identifiers are
unchanged; imported reason strings are preserved. Shared fixture characters must
still match exactly, and explicit newer/unassigned witnesses test the exception.
The [table](../protocol/unicode14-printability.json) records the official source
and source/range SHA-256 pins; the [Unicode license](../protocol/UNICODE-LICENSE.txt)
is retained. Regeneration reads checksum-pinned category data, never the host
Python Unicode database. Offline checking uses
`python3 tools/freeze_unicode14_printability.py --check`.

Request/coordinate declarations are internal library APIs. The explicitly scoped
`verify-lowering` operation exposes source-to-Behavior checking through both
executables and the opt-in Python process adapter; production Python routing
remains unchanged. Their hosted tests use the retained case B requests
and behaviors plus independent coordinate fixtures, in addition to literal and
mutation tests. Seven artificial Behavior documents cover all 38 legacy and four
extension operation kinds, with exact document/fingerprint and census checks.
The deterministic corpus can be checked with
`PYTHONPATH=src python3 tools/freeze_behavior_domains.py` (a source check only).
The configured hosted gate now contains 17 native suites, including five new
suites for lowering, pins, component contracts, molecular records and chemistry.
Pins have literal tests under `dune runtest`; the other four also have required
fixture-file replay. These are configured gates, not a claim that the current
batch has passed. After `dune runtest`, the required CI job invokes:

```sh
core/_build/default/test/test_build_request.exe "$GITHUB_WORKSPACE/tests/conformance/case-b"
core/_build/default/test/test_behavior.exe "$GITHUB_WORKSPACE/tests/conformance/case-b" "$GITHUB_WORKSPACE/tests/conformance/behavior-domains-v1.json"
core/_build/default/test/test_molecule_coordinates.exe "$GITHUB_WORKSPACE/tests/conformance/molecule-coordinates-v1.json"
core/_build/default/test/test_circuit_request.exe "$GITHUB_WORKSPACE/tests/conformance/request-domains-v1.json"
core/_build/default/test/test_lowering_check.exe "$GITHUB_WORKSPACE/tests/conformance/case-b" "$GITHUB_WORKSPACE/tests/conformance/request-domains-v1.json"
core/_build/default/test/test_runtime_number.exe "$GITHUB_WORKSPACE/tests/conformance/runtime-numbers-v1.json"
core/_build/default/test/test_execution_data.exe "$GITHUB_WORKSPACE/tests/conformance/reference-execution-v1.json"
core/_build/default/test/test_reference.exe "$GITHUB_WORKSPACE/tests/conformance/reference-execution-v1.json"
core/_build/default/test/test_lowering.exe "$GITHUB_WORKSPACE/tests/conformance/lowering-v1.json"
core/_build/default/test/test_component_contract.exe "$GITHUB_WORKSPACE/tests/conformance/component-contracts-v1.json"
core/_build/default/test/test_molecular_record.exe "$GITHUB_WORKSPACE/tests/conformance/molecule-chemistry-v1.json"
core/_build/default/test/test_molecule_chemistry.exe "$GITHUB_WORKSPACE/tests/conformance/molecule-chemistry-v1.json"
```

The new retained corpus census is:

| Area | Required cases |
| --- | --- |
| Fresh lowering | 31 exact positives and 32 intended rejections |
| Component contracts | 30 records, 35 malformed records, 77 algebra cases and three diagnostic-profile witnesses |
| Molecular chemistry | 47 records, 82 decode rejections and 29 coordinate/sequence validation cases |
| Molecular record boundaries | 10 text cases and 50 exact serialization-size cases |

Missing fixture paths, truncated inventories and unintended rejection categories
fail the native tests. Pure-Python regeneration checks need no native build:

```sh
python3 tools/freeze_lowering.py --check
python3 tools/freeze_component_contracts.py --check
python3 tools/freeze_unicode14_printability.py --check
python3 tools/freeze_molecule_chemistry.py
```

The numeric corpus retains 1,948 CPython results and 28 independent literal
witnesses. Full reference traces retain source/requirement lineage, all action
and event fields, states, memories, timestamps and microsteps; intended evaluator
failures are separate from parser failures. Both corpora must pass on each native
platform before this batch is considered validated. Source fixture checks run
without any native build.

The case B architecture checker, coupled source execution, independent candidate
runtime and exact export acceptance remain to be
implemented before any production semantic authority can move to OCaml.

PR44 validated checker-private construction reconstruction, fresh assessments/replay, complete architecture refinements/templates and source-manifest checking. All 34 native suites passed on both platforms, with exactly 2,244 Python tests per version and every required product gate in both PR run36945426505 and integrated-main run36946981717; [receipt](../protocol/migration-reconstruction-validation.json). Dune hides reconstruction modules; static guards reject producer imports and public interface leaks. Production routing remains Python.

The new source-manifest checker retains 34 historical records, 56 intended import rejections and 35 full source/manifest comparisons, including 17 candidate mutations. Native lowering discrepancies explicitly use `source_behavior:<native code>` under `biocompiler.ocaml.source_manifest_check.v0.1`; two corresponding Python-prose cases are retained separately. Other scoped diagnostic keys are unchanged. Transition checks preserve legacy projection limits and use the explicit native `biocompiler.transition_check.resources.v1` shared work budget; exhaustion yields no partial semantic report. Historical construction reports retain their policy/schema identity, while fresh native execution has a distinct implementation identity. These scopes passed complete PR44 validation. The next batch adds complete historical build/assessment imports, supplementary circuit correspondence, bounded control proofs, exact deployment interval checks and full architecture reconstruction. The checker explicitly links the already-pinned Zarith primitive for exact rational arithmetic; producer library dependencies remain prohibited.


The pending architecture batch keeps historical `Construction_build`,
`Architecture_build` and `Architecture_assessment` imports distinct from fresh
checking. Their corpus retains all three original case B builds, 48 complete
records and 117 intended import rejections. The supplementary circuit binding
campaign retains 53 complete source checks and 31 malformed imports. Controls
retain the existing bounded theorem profiles, explicit default versus frozen
parameter bindings, 112 complete cases and native expression-depth/source/controller ceilings; deployment checks retain 30 complete cases, use
exact decimal rationals and retain explicit recipient/clock/interval witnesses.
These new scopes remain pending full hosted validation.

Shared checker work budgets retain both local and ancestor limits. Resource
exhaustion returns no partial semantic report. Output reservations count JSON
keys, UTF-8 bytes and escaping before retaining expanded inventories or witnesses.
The architecture checker keeps namespace, ledger and construction reconstruction
private, with separate original request and candidate inputs. Python set-derived
diagnostic iteration will use explicitly documented deterministic native order;
unchanged field values and multiplicity remain part of conformance. No producer,
matcher or source evaluator is linked into the verifier.

The architecture campaign captures 293 complete fresh reports (217 PASS and
76 FAIL) from all 78 original methods in six checker-related test modules,
the 13 installed architecture examples and the three original case B builds.
Its 463 distinct documents retain complete resolved content identities. Full
baselines remain readable JSON; test-only, one-level delta files use compact
canonical JSON to keep the stored campaign within 16 MiB. Every delta resolves
against a complete same-kind baseline and is checked against the original full
document fingerprint and size. Delta chains, substituted or unused documents,
missing cases and unclassified diagnostic changes are rejected. This storage
format is confined to tests. Hosted validation of this campaign remains pending.

Two cases explicitly retain changed native diagnostic spelling: an empty
implemented-realization declaration uses `malformed_architecture:invalid_architecture_build`,
and a stale source uses `source_behavior:lowering_source_identity`. Their full
historical messages remain in the fixture. One model-pin mutation compares
set-derived missing-material diagnostics within its declared loop; a separate
literal requires the exact deterministic native order. Other report fields,
diagnostic multiplicity, outcomes and completeness claims remain exact.
