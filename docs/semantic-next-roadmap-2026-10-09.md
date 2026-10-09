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
2. **Bounded networks of interacting machines and observations — to do.**
   Support independently owned controllers, asynchronous observations, explicit
   communication and shared resource constraints. First exercise two controllers
   and two observation streams sharing a bounded resource, including simultaneous
   transitions, Unknown, reset and effect-attempt correlation. Preserve complete
   whole-program checking before introducing independently justified compositional
   verification.
3. **Explicit target capabilities and obligation planning — to do.**
   Explain supported constructs, required supplied components and outstanding
   compilation/export obligations before expensive work. Distinguish invalid
   source, unsupported realization, failed requirements and exhausted resources.
   Declaration-level diagnostics begin with item 1; broader capability planning
   follows without granting acceptance from a planning report.
4. **Broader quantitative semantics and realization evidence — to do.**
   Extend exact sampled mechanisms into composable quantitative programs, then
   introduce uncertainty and approximation through named refinement relations.
   Explicitly resolve multiple effect-request sites before generalizing threshold
   crossings. Component contracts should retain measured parameters, uncertainty,
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
