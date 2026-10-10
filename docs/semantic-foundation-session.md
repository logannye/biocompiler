# Ordered semantic foundation implementation

This record covers the original five increments. Subsequent work is tracked in
the [next four milestones](semantic-next-roadmap-2026-10-09.md), beginning with
the [native module-linking checkpoint](semantic-module-linking-checkpoint-2026-10-09.md).
Statements below describe the earlier checkpoints at their recorded revisions.

This session implements the five user-requested architecture increments in order.
The working branch is `codex/dev-policy/semantic-foundation-v2`, initially based on
`6e4067f17820c472e0ee54f7a96215fbb084b5d2`. That source belongs to the independently
owned PR99 integration candidate. Its running validation is preserved; this
branch does not inherit its acceptance or modify its checkout.

## Completion conditions

Each increment requires implementation in the real public/native path, positive
and rejection controls, compatible preservation of defined existing exact paths,
focused local static/Python checks, independent source review and fresh hosted
native evidence before acceptance. Following the user's explicit direction to
avoid CI during iteration, implementation proceeds in order using focused local
Python/static feedback and independent review. Native validation is deferred to
the combined candidate; pending validation is never called passed. Existing
unrelated healthy runs remain untouched. The combined
integration candidate additionally requires the complete cross-platform and
installed-package gate, followed by fresh actual-main validation after normal
integration. Development evidence is not release acceptance.

| Order | Increment | Required observable result | Status |
| --- | --- | --- | --- |
| 1 | Stable specification and strongly typed admitted IR | Versioned language authority independent of Python dataclass layout; SDK/schema conformance; closed, resolved semantic types actually consumed after admission; exact existing wire/source correspondence preserved. | Implemented and source-reviewed; native validation pending |
| 2 | Typed Python facade and semantic modules | Distinct expression/reference categories, explicit module ports and private state/effects, hygienic instantiation, checked interfaces and conflicting-composition rejection through the public source path. | Implemented and source-reviewed; focused Python and typing checks pass |
| 3 | Generic finite-machine lowering and composition | Multiple materially different finite-machine shapes use common lowering/checking and component composition; complete source, attempt identity, atomicity, requirements and material correspondence survive. | Implemented and source-reviewed; focused local checks pass; native validation pending |
| 4 | Named refinement relations and composable evidence | Explicit relation kinds and source/target/assumption/bound identities; independently checked composition; old exact relations retain their original meaning and cannot be weakened by a producer. | Implemented and source-reviewed; focused Python/static/typing checks pass; native validation pending |
| 5 | Quantitative mechanism-to-payload profile | Explicit quantitative dynamics, units, domain and observation map connected to selected supplied components, independent behavior/requirement checks and exact paired molecular export; mutations change output or reject. | Implemented and source-reviewed; focused Python/static/typing checks pass; native validation pending |

Finite supported domains and model-to-material premises remain explicit. No
increment claims arbitrary biological realization or empirical therapeutic
validation. Unsupported meanings must remain visible and prevent a complete
artifact claim. The quantitative profile must be connected end to end rather
than become a separate simulator.

## Engineering boundaries

- All native OCaml/Rust compilation, execution and packaging stay hosted.
- Local work uses pure Python, typing, static inventories and source review.
- New source checks preserve original inventories and semantic classifications;
  changed source pins require review of the actual diff.
- Keep changes within this owned checkout. Do not reset, cancel, merge or alter
  unrelated active work or its evidence.
- Keep exact source/run/attempt provenance and retain useful failure records.
- Record any incomplete implementation or validation accurately; a facade, schema
  or stored passing result alone does not complete an increment.

## Current checkpoint

The original alpha was published before this session. At session start, main was
refreshed as `e253ed5b3370af9a7d8b9ba96af2e7f8f025798a`. PR99 was open at the base
source above, with its separate fresh run active. These are initial session
observations, not a later acceptance claim. Item 1 is implemented in this isolated checkout. Its local feedback includes
31 inert wiring/development-runner tests, 94 language/coverage tests and 17
language tests on Python 3.11.15 (the other checks used Python 3.14.6). The
language generator and native dependency boundaries pass static checks.
Original 62 material families and 27 component families retain their reviewed
meaning, witness identities and open gaps under explicit additive projections.

The admitted scalar/event separation intentionally rejects event-as-value
comparisons and effect arguments earlier, including dormant occurrences. Those
positions lacked runtime value semantics; source requirements and ordinary event
triggers remain retained. The correction is documented in the typed-IR contract.

No CI was dispatched for this step following the user's iteration preference.
Native compilation/execution and integration acceptance remain pending. Item 2
is implemented in `policy.typed` and `policy.modules`. A combined 121-test local
run on Python 3.11.15 passes, including strict mypy on the facade and complete
positive example, exactly 17 expected negative diagnostics, all 29 module tests,
44 public API inventory controls and existing authoring compatibility controls.
The module implementation separately passes strict mypy and its 29 tests on
Python 3.14.6. Both documentation examples execute locally as source-only
programs. The additive API inventory preserves all original 905 classifications
and 138 witness meanings; new entries distinguish focused shared controls from
untested individual declarations. Module privacy and interface checks are an
authoring guarantee: flattened source retains no native module provenance proof.

Item 3 implements explicit finite-machine realization, binding and material
profiles without changing legacy profile meanings. Three independently supplied
artificial shapes exercise retry cycles, guarded branching and observation-update
forks through named component composition and exact paired RNA export. The
native suite includes four handwritten source/candidate traces and more than 30
rejection controls; it has been source-reviewed but not compiled or executed.
A combined 90-test Python 3.11.15 run passes across finite-machine controls,
existing implementation/component/material transport and API coverage. The
local Python tests use mock transport and independently retained source,
fragment, identity and sequence expectations. Forty-nine focused material coverage controls and 31 inert native wiring/development-runner controls pass;
these controls do not execute native tests. No CI was dispatched.

The supported family has one machine (2-16 states, 1-32 transitions), 1-8 effects
with unique initiating transitions, one truth observation, one fixed product and
two encounter slots, subject to the existing 64-node graph bound. Original finite
domain, requirements, provider closure and exact material remain independently
checked. Universal termination and biological realization are not claimed.
Item 4 follows this checkpoint. No native or release acceptance is claimed for
this branch.

Item 4 adds a closed vocabulary and private evidence capabilities derived from
fresh admission, binding, preservation, assembly, context and material tokens.
Ten named claims retain eighteen exact original/checking premises. Three explicit
directional rules support composition; conjunction cannot erase scopes or splice
different artifacts, requests, limits or assumptions. The separate refinement
check/replay service preserves legacy material reports and export paths. Evidence
construction and supplementary hashing have their own bounded work accounting.
The native suite contains 18 source-reviewed rejection controls and is pending
execution. The Python interface exposes immutable descriptive views and fresh
native calls; constructing those views grants no acceptance capability. The
additional 31 inert wiring/development-runner checks pass locally. No CI has been
dispatched and no native compilation or execution has occurred.

Item 4 local inventory validation also includes 53 material-coverage controls and
19 migration-inventory controls, all passing. The additive API inventory retains
all 1,083 previous classifications and 152 witness meanings; 74 new AST entries
include 23 private dependencies, 22 declarations with focused shared controls and
29 source-only declarations. Eight new witness descriptions remain limited to
inert transport/view validation. All 28 prior component-family meanings and the
original 62-family inventory classifications remain frozen under explicit
projections. The current source census is not native acceptance.

The final Item 4 SDK controls pass: 13 refinement tests, 49 API inventory tests
and strict mypy on both new SDK modules (Python 3.11.15). Earlier checks also
confirmed the unchanged source-context slice with 31 local controls. The migration
inventory contains 4,052 entries. Item 5 begins after this checkpoint.

Item 5 implements a separate sampled-reservoir material profile. The independent
law uses complete nominal units and an exact 2-16-state quantity grid. True adds
one quantum, False subtracts one, and saturation follows the combined update.
Unknown and absent updates hold; an upward threshold crossing requests the one
declared effect. The profile checks one-tick freshness, zero-age samples, complete
sampling multiplicity, reset state and the exact original clock. Existing atomic
reservation and effect lifecycle contracts remain applicable.

The selected component carries its own law, state map and complete local model
pins. A fresh quantitative capability binds them to the original source and
checked assembly, including the actual threshold request endpoint. Material
acceptance requires this capability, and every discharged obligation pins the
quantitative report. Existing compile/check/replay/export operations negotiate the
new explicit profile. Old profiles keep their report shapes and cannot silently
consume a quantitative component. Named refinement keeps its ten relations and
eighteen premises; the complete material premise includes the new checked stage.

The artificial four-level fixture has an independent twelve-row truth table and
two handwritten source/candidate trajectories covering saturation, decay, Unknown,
missing input, repeated crossing and reset. Native rejection controls mutate
units, clocks, original/local laws, state maps, sampling, selected pins and payload
construction. Semantic mutants repin the complete component, rule and contextual
authority so rejection cannot be attributed merely to stale fingerprints. These
native controls have been source-reviewed, not compiled or executed. Review also
corrected a finite-profile producer census omission in the native protocol test;
no prior native execution was claimed for that source.

Item 5 local validation passes on Python 3.11.15: 60 focused quantitative and
existing transport controls; 65 quantitative/public-API controls; 56 material
inventory controls; 31 inert native-wiring/development-runner controls; 19 migration
inventory controls; and 17 language-specification controls. These overlapping
slices are not summed into a unique-test total. Strict mypy passes on all five
modified quantitative SDK/facade modules. Fixture regeneration, native dependency
boundaries and source inventory checks also pass. Wiring tests simulate native
processes and provide no native execution evidence.

The final API inventory has 1,187 entries in 48 files and 164 witness descriptions;
the preceding 1,157 classifications and 160 meanings remain exactly preserved.
The original 62 material-family meanings and all 29 preceding component-family
meanings remain frozen under explicit projections. The additive component
inventory has 30 families, 120 source files and 137 witness sources. The migration
inventory has 4,074 entries. Inventory pins establish reviewed source identity,
not successful execution or biological realization.

All five requested implementation increments are now present in order. No CI was
dispatched, no OCaml/Rust build or native executable was run, and no package was
rebuilt or published during this session. Native and installed-package acceptance
remain pending for the combined source; these local checks do not qualify a
release. The [architecture overview](semantic-architecture.md) describes the
resulting boundaries and subsequent extensions without widening these claims.
