# Bounded machine-network implementation checkpoint

This checkpoint implements item 2 of the approved next-work roadmap in
`codex/dev-policy/semantic-foundation-v2`, following module-linking checkpoint
`d963785cb42bfc72814645219c4eeb2ab81c00d4`. Item 1 and the earlier five foundations
remain intact. These are local implementation and source-review results;
native execution and installed acceptance remain pending.

## Implemented boundary

The new explicit network profile admits multiple bounded controllers, independent
truth observation streams and single-writer encounter-local communication stores.
Complete priority policies determine arbitration groups. Separate groups may
commit simultaneously; a shared group chooses according to the declared order.
Guards and assignments observe the precommit snapshot. Retained effect attempts
remain tied to their initiating machine, encounter slot and generation.

A separate generic lowerer produces the existing staged primitives from supplied
models. The independent binding checker reconstructs source expressions, store
writers, machine writers, arbitration lanes, inputs, source occurrences and
whole-graph coverage. A private checked binding enters the existing preservation,
hard-requirement, component assembly, context and exact material pipeline.
Original hard requirements and fresh export checks remain conjunctive. The
existing exact refinement relations retain their meanings and premises.

The primary example has two controllers, two asynchronous observation streams,
a store owned by one controller and read by its peer, and a shared provider pool.
The pool's required quantity is the sum of the selected components' demands.
The module-linked route retains complete original modules and exact elaboration
lineage through paired RNA/manifest export. A second source shape uses two owned
busy flags, a shared priority group and an explicit capacity-one safety requirement.
This logical protocol remains separate from supplied physical provider capacity.

The full primary domain keeps one active encounter slot and a second known-False
isolation control, with reset branching only for the active slot. This bounds
exploration to at most 32 histories instead of potentially 1,024. Short selected
prefixes separately exercise concurrent request reservation and interleaved source
declaration order. The runtime work ceiling was corrected from a value already
below the source-derived output-reservation lower bound; actual native resource
usage must still be measured.

## Local validation

Focused checks use CPython 3.11.15 on macOS arm64 against the source tree. Native
transport peers in Python tests are inert or mocked. No dependency synchronization,
local OCaml/Rust compilation, executable native test or extension rebuild occurred.

- Language specification and semantic syntax inventory: 49 tests passed; all 45
  closed language records and 612 reviewed syntax distinctions remain unchanged.
- Runner and authenticated bundle accounting: 34 tests passed with inert commands.
  Complete suite dependencies and failure/timeout accounting remain enforced.
- Static checker/producer dependency boundary check passed.

- Network facade and adjacent transport/source checks: 89 tests passed, including
  15 network controls. All native responses in these tests were mocked.
- Material inventory: 62 controls passed. Final witness pins and the current
  inventory gate were rechecked after the native test helper's attempt ceiling
  was corrected to 16, above the original logical ceiling of 12. The inventory
  contains 32 component families, 133 source files and 146 witness files.
- Public API inventory: 56 controls passed; 1,297 entries across 50 files,
  262 exports, 29 native operations and 174 witnesses. The 18 new declarations
  are implementation dependencies; existing public entry points add an explicit
  network flag.
- Migration and fixture controls: 25 tests passed (20 migration and 5 fixture).
  The refreshed migration inventory contains 4,139 entries.
- Strict mypy passed for the six changed SDK files. Deterministic network fixture
  regeneration and final whitespace checks passed.
- Independent source review covered admission, lowerer, checker, primitive/source
  ordering, source/input correspondence, context/resource accounting, exact
  material and service routing, SDK validation, fixture bounds and inventories.
  No source-review blocker remains. The native suite contains 28 rejection
  controls plus handwritten trace, order, atomicity and exact-export assertions;
  these assertions have not executed.

The material inventory preserves all prior 31 component families, 131 source
classifications and 142 witnesses, and every original whole-kernel rule and its
183 source classifications. Public API projections preserve all prior 1,279
classifications and 174 witness meanings. Separate frozen metadata projections
reject changes to earlier meanings even if the current metadata pin is updated.
Source inventory acceptance supplies no native or biological acceptance.

## Deferred validation

No CI dispatch, push, PR, merge or package build was performed. The supported
focused development runner now contains 46 native suites; the complete Dune
census contains 186 suites, 194 executable entries and 30 JSON fixtures.
There are 68 suites with explicit ordered fixture dependencies. Existing hosted
SDK campaigns remain required and do not gain network-client acceptance through
source enrollment or mocked transport tests.

A coherent hosted run must compile and execute the new network lowerer, checker,
protocols and native regressions, including every semantic mutation, independently
specified trace, shared-provider boundary, logical-resource property and exact
module-linked payload export. Record actual work, prefix counts and timing.
Installed transport, full cross-platform/integration and fresh actual-main gates
remain required. Earlier checkpoints' pending native gates are not superseded.
The installed offline archive consumer remains outside the linked-manifest profile.

See [the network contract](policy-machine-network-v0.1.md) for precise bounds,
semantics, profile identities and the distinction between model-conditional
software assurance, empirical mechanism function and clinical evidence.
