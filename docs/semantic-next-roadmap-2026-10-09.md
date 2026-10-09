# Next semantic compiler milestones

Recorded from the user's approved next-work list on 2026-10-09. This follows the
five implementation increments at `0c0b79d151718b7efc6508dc35ea93dc4d023443` on
`codex/dev-policy/semantic-foundation-v2`. Those increments passed their recorded
local checks; native execution and installed-package acceptance remain pending.

1. **Native module representation and independently checked linking — implemented locally; native validation pending.**
   Preserve complete templates, typed ports, instance bindings, private state and
   effects, requirements and semantic definitions in versioned source data. An
   independent OCaml checker reconstructs the flattened source, verifies interface
   access and ownership, and binds checked linkage to both original modules and
   resulting source. Retain lineage through material checking and export. Include
   source-level diagnostics. The first complete example uses sensing, controller
   and effector modules within the existing executable profile. Altered bindings,
   private references, units, lifecycles, requirements and flattened declarations
   must reject. This establishes exact elaboration, not separate behavioral
   verification or discharge of acknowledged assumptions.
2. **Bounded networks of interacting machines and observations — implemented locally; native validation pending.**
   Support independently owned controllers, asynchronous observations, explicit
   communication and shared resource constraints. First exercise two controllers
   and two observation streams sharing a bounded resource, including simultaneous
   transitions, Unknown, reset and effect-attempt correlation. Preserve complete
   whole-program checking before introducing independently justified compositional
   verification.
3. **Explicit target capabilities and obligation planning — implemented locally; native validation pending.**
   Explain supported constructs, required supplied components and outstanding
   compilation/export obligations before expensive work. Distinguish invalid
   source, unsupported realization, failed requirements and exhausted resources.
   Declaration-level diagnostics begin with item 1; broader capability planning
   follows without granting acceptance from a planning report.
4. **Broader quantitative semantics and realization evidence — first three increments implemented locally; native validation pending.**
   Extend exact sampled mechanisms into composable quantitative programs, then
   introduce uncertainty and approximation through named refinement relations.
   The first increment supplies multiple effect-request sites with shared capacity
   and exact sampled rise/fall laws with every threshold crossing independently
   bound to selected components and exact material. The second increment adds a
   conservative two-reservoir transfer law under a checked joint component
   contract. The third increment adds bounded networks with explicit ordered
   reservation of shared stock and headroom under one atomic state owner.
   Decomposition across separate component owners and uncertainty/evidence
   interfaces remain queued. Component contracts should retain measured parameters, uncertainty,
   applicable environments and experimental provenance; supplied model agreement
   and empirical function remain separate claims.

## Working cadence

Keep the inner loop local: focused Python tests, typing, deterministic fixtures,
static dependency/inventory controls and independent source review. Batch native
validation at coherent checkpoints; do not dispatch CI for each edit. No local
OCaml/Rust compilation or native execution is authorized. Preserve the existing
full integration and fresh actual-main gates and all unrelated worktrees/runs.

Item 1's interface is recorded in [the module-linking contract](policy-module-linking-v0.1.md).
Its [implementation checkpoint](semantic-module-linking-checkpoint-2026-10-09.md)
separates passed local checks from the pending native and installed gates.

Item 2's explicit network profile is recorded in [the machine-network contract](policy-machine-network-v0.1.md).
Its [implementation checkpoint](semantic-machine-network-checkpoint-2026-10-09.md)
records bounded interaction, shared-resource and exact material scope, passed local
checks and the pending native and installed gates.

Item 3's diagnostic-only interface is recorded in [the target-planning contract](policy-target-planning-v0.1.md).
Its [implementation checkpoint](semantic-target-planning-checkpoint-2026-10-09.md)
records the installed target catalog, fresh bounded preflight, preserved obligations
and local validation scope.

Item 4's first increment is recorded in [the sampled step contract](policy-quantitative-step-v0.1.md)
and its [implementation checkpoint](semantic-quantitative-step-checkpoint-2026-10-09.md).
It preserves exact existing paths while adding multiple request sites; broader
quantitative composition and empirical evidence interfaces remain future work.

Item 4's second increment is recorded in [the transfer-pair contract](policy-quantitative-transfer-v0.1.md)
and its [implementation checkpoint](semantic-quantitative-transfer-checkpoint-2026-10-09.md).
It checks exact coupling and conservation under one supplied joint component;
separate molecular realization and empirical evidence remain distinct obligations.

Item 4's third increment is recorded in [the transfer-network contract](policy-quantitative-network-v0.1.md)
and its [implementation checkpoint](semantic-quantitative-network-checkpoint-2026-10-09.md).
It composes named reservoirs and directed transfers with exact prestate
reservations; distributed molecular coordination and empirical realization
evidence remain explicit follow-ups.
