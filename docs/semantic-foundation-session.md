# Ordered semantic foundation implementation

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
| 2 | Typed Python facade and semantic modules | Distinct expression/reference categories, explicit module ports and private state/effects, hygienic instantiation, checked interfaces and conflicting-composition rejection through the public source path. | Pending |
| 3 | Generic finite-machine lowering and composition | Multiple materially different finite-machine shapes use common lowering/checking and component composition; complete source, attempt identity, atomicity, requirements and material correspondence survive. | Pending |
| 4 | Named refinement relations and composable evidence | Explicit relation kinds and source/target/assumption/bound identities; independently checked composition; old exact relations retain their original meaning and cannot be weakened by a producer. | Pending |
| 5 | Quantitative mechanism-to-payload profile | Explicit quantitative dynamics, units, domain and observation map connected to selected supplied components, independent behavior/requirement checks and exact paired molecular export; mutations change output or reject. | Pending |

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

The original alpha was published before this session. Main was refreshed as
`e253ed5b3370af9a7d8b9ba96af2e7f8f025798a`. PR99 remains open at the base source
above, with its separate fresh run active. Item 1 is implemented in this isolated checkout. Its local feedback includes
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
now follows this implementation checkpoint. No acceptance is claimed for this
branch.
