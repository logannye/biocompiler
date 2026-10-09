# Native module-linking implementation checkpoint

The four approved next milestones were recorded at `702c8a7ea`, after the five
foundation increments ending at `0c0b79d151718b7efc6508dc35ea93dc4d023443`.
This checkpoint implements the first milestone on
`codex/dev-policy/semantic-foundation-v2`. Items 2–4 remain to do. These are local
implementation and source-review results; native acceptance is pending.

## Implemented boundary

The versioned module bundle preserves complete templates, nominal typed ports,
explicit private state/effects, instance bindings, semantic definitions,
assumptions, guarantees and source maps. The Python facade snapshots that bundle
and proposes ordinary source. An independent OCaml checker reconstructs the
source and checks every field, access permission, ownership and relocation before
creating an opaque checked-linkage value. Declaration diagnostics identify the
original template/context and instance. This is exact elaboration; assumptions
are retained and separate module behavioral verification is not claimed.

The linked material producer/checker/replay/export operations retain the original
bundle and freshly checked lineage alongside the unchanged complete component
material result. Export binds the original material manifest and exact FASTA.
All prior whole-program, component, context and material checks still run.
Existing raw routes retain their meanings. The new export manifest is not yet
supported by the existing installed offline archive consumer.

The independent three-module fixture uses sensing, a controller and an effector
within the existing single-machine profile. It supplies the literal source and
artificial RNA expectation independently of both linkers. Handwritten native
source cases cover repeated private state, complete assumptions, nominal units,
lexical definitions and multiple source spans. The native suite includes 54
rejection controls for altered interfaces, private escapes, conflicting writes,
assumptions, pins, diagnostics, budgets, proposed source and linked export.
Those native controls are written and source-reviewed; they have not executed.

## Local validation

Python checks use CPython 3.11.15 on macOS arm64 with the existing source tree.
No dependency synchronization, native compilation or extension rebuilding was
performed. Test peers for native transport are inert/mocked Python processes.

| Check | Result and scope |
| --- | --- |
| New module authoring and transport | 16 tests passed; complete codec, independent source, snapshots, negotiation, lineage, nested material and publication rejection controls |
| Adjacent module/source/finite/refinement/quantitative/material tests | 94 tests passed; pure Python and mocked transport |
| Runner/fixture wiring | 31 tests passed; inert execution accounting only |
| Material coverage inventory | 59 tests passed; 31 component families, 131 sources, 142 witnesses, plus unchanged 62 original whole-kernel rules |
| Public API inventory | 54 controls validated: 53 passed in the combined run, then the corrected expected-count control passed a targeted rerun; 50 files, 1,279 entries, 262 exports, 29 native operations and 174 witnesses |
| Migration inventory | 20 tests passed; 4,121 entries, both new interfaces remain Python authoring/transport with fresh native authority |
| Strict typing | Both new Python implementation files passed strict mypy |
| Static syntax inventory correction | 32 tests passed on each of CPython 3.11.15 and 3.14.6; all 612 distinctions and their reviewed syntax hashes remain unchanged |
| Source contracts and dependency boundaries | 45 closed language records unchanged; module fixture regeneration check and checker/producer boundary check passed |
| Independent source review | Native domain/checker, services, fixtures, diagnostics and additive coverage reviewed; no remaining source-review blocker |

The material inventory independently preserves all prior 30 component families,
120 source classifications and 137 witnesses, and all 172 original whole-kernel
source classifications. Updating the new metadata pin cannot weaken these frozen
projections. Public API coverage likewise preserves its previous 1,187
classifications and 164 witness meanings. Inventory acceptance is source evidence,
never proof of execution or semantics.

The final syntax gate also exposed an earlier inventory bug: unrelated typed
facade classes sharing names with wire records were classified as records.
The scanner now follows actual class identities and explicit aliases, with
regressions for namesakes, real duplicate records, qualified/reexported bases
and shadowing; wildcard imports fail closed as unsupported inventory syntax.
The language and its 612 reviewed syntax distinctions remain
unchanged; this correction grants no semantic admission.

## Deferred validation

No CI run, push, PR, merge, package build, native executable test or installed
acceptance was performed for this checkpoint. The native suite is enrolled in
the supported 45-suite development runner and the full 185-suite Dune census,
with its original JSON dependency in the authenticated native bundle. The full
bundle now has 193 executable entries and 29 JSON fixtures; 67 suites have
explicit fixture dependencies. Existing 260 hosted SDK observations remain
mandatory and do not acquire module-client coverage from this enrollment.

A coherent hosted native run must compile and execute the new linker, protocols
and 54 rejection controls, and measure their actual resource usage. Installed
Python/Core/Verify transport validation for the new route and the required full
cross-platform/integration and fresh actual-main gates remain open. Exact source,
run, attempt and artifact identities must be recorded when those checks execute.
The earlier five increments' native acceptance is also pending; this checkpoint
does not inherit acceptance from an unrelated worktree or historical run.

See [the normative interface](policy-module-linking-v0.1.md) for wire fields,
claim scope, Python usage and the current diagnostic/export limitations.
