# OCaml core

This is the first native migration increment. It implements bounded strict JSON,
legacy Python-compatible canonical fingerprints and structural intent/type/literal
validation, plus independent frozen source-to-Behavior correspondence. A separate
internal library implements per-role reference execution for conformance. The
public protocol does not yet implement compilation, behavioral execution,
molecular verification, export acceptance or human-use admission. Capabilities
are explicit; unimplemented operations return `unsupported` without fallback.

The protocol is one UTF-8 request on stdin and one response on stdout. Both
executables use `biocompiler.core.v1` and identify their distinct executable role.
Nonzero exit codes accompany structured errors (2) and unsupported operations (3).
There is no Python semantic execution or runtime network request in either binary.

Libraries have explicit dependencies. `bioc_checker` only depends on immutable
domain/wire modules. `bioc_service` exposes that checker; the standalone verifier
has no dependency on a compiler, selector, matcher, assembler or emitter.
The shared JSON codec, canonicalizer, numeric conventions and domain validators
are part of the common trusted base, not independent execution evidence.

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
  declarations with their complete source authority. Deferred human behavior,
  deployment and acceptance wrappers yield explicit unsupported coverage; their
  nested BuildRequest is never substituted for the original wrapper.
- `Lowering_check` independently compares a supplied Behavior with a separately
  frozen BuildRequest, accounting for every operation, binding, requirement and
  source correspondence. Its abstract report binds full and semantic identities
  and carries all remaining execution, realization and acceptance obligations.
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

Request/coordinate declarations are internal library APIs. The explicitly scoped
`verify-lowering` operation exposes source-to-Behavior checking through both
executables and the opt-in Python process adapter; production Python routing
remains unchanged. Their hosted tests use the retained case B requests
and behaviors plus independent coordinate fixtures, in addition to literal and
mutation tests. Seven artificial Behavior documents cover all 38 legacy and four
extension operation kinds, with exact document/fingerprint and census checks.
The deterministic corpus can be checked with
`PYTHONPATH=src python3 tools/freeze_behavior_domains.py` (a source check only).
After `dune runtest`, the required CI job invokes:

```sh
core/_build/default/test/test_build_request.exe "$GITHUB_WORKSPACE/tests/conformance/case-b"
core/_build/default/test/test_behavior.exe "$GITHUB_WORKSPACE/tests/conformance/case-b" "$GITHUB_WORKSPACE/tests/conformance/behavior-domains-v1.json"
core/_build/default/test/test_molecule_coordinates.exe "$GITHUB_WORKSPACE/tests/conformance/molecule-coordinates-v1.json"
core/_build/default/test/test_circuit_request.exe "$GITHUB_WORKSPACE/tests/conformance/request-domains-v1.json"
core/_build/default/test/test_lowering_check.exe "$GITHUB_WORKSPACE/tests/conformance/case-b" "$GITHUB_WORKSPACE/tests/conformance/request-domains-v1.json"
core/_build/default/test/test_runtime_number.exe "$GITHUB_WORKSPACE/tests/conformance/runtime-numbers-v1.json"
core/_build/default/test/test_execution_data.exe "$GITHUB_WORKSPACE/tests/conformance/reference-execution-v1.json"
core/_build/default/test/test_reference.exe "$GITHUB_WORKSPACE/tests/conformance/reference-execution-v1.json"
```

The numeric corpus retains 1,948 CPython results and 28 independent literal
witnesses. Full reference traces retain source/requirement lineage, all action
and event fields, states, memories, timestamps and microsteps; intended evaluator
failures are separate from parser failures. Both corpora must pass on each native
platform before this batch is considered validated. Source fixture checks run
without any native build.

The case B architecture checker, coupled source execution, independent candidate
runtime, construction reconstruction and exact export acceptance remain to be
implemented before any production semantic authority can move to OCaml.
