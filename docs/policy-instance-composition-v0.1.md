# Bounded policy instance composition

Status: implementation checkpoint, 2026-10-08. Hosted native and integration
validation are pending. This is priority 1 of the
[core architecture plan](core-architecture-session-priorities-2026-10-08.md),
covering SM-05/SM-06/SM-09 and their SM-01/SM-08 witnesses.

## Contract

An original assembly selects two to eight named instances of immutable component
definitions. Each instance owns its local primitive nodes, state and resource
demands. Explicit typed links connect original boundary ports; complete ordered
node, wire, input, atomic-group and export inventories remain authoritative.
Every original boundary must be used, each input boundary has one producer,
and encounter links preserve layout and slot identity. Only immutable executor
constants may broadcast into encounter-local inputs. Atomic groups stay wholly
inside a fragment; their declared group names must remain globally distinct.

The profile retains the existing primitive execution and source semantics.
Whole-program preservation checks the complete original finite operating domain
after reconstruction. Decoding, linking, a locally valid fragment, or matching
pins cannot grant accepted compilation. The private checked-value chain still
requires preservation, assembly, context and all original material obligations.

Material assembly concatenates complete supplied roots in declared instance
order in one construction step. Every adjacent pair has one exact join. Each
cross-instance link carries the full ordered path of crossed joins, including
their original offsets. Final feature identities are canonical JSON encodings
of `[instance, local_feature]`, with bounded lengths. The independent checker
derives offsets, feature projections, exact bases and chemistry from originals.
It does not reuse the producer or domain offset helper as its geometry oracle.

All per-instance resource requirements enter the existing independent global
context calculation. Shared capacities sum demand; state-bearing records retain
instance identity and original domain/layout pins. Renaming an instance changes
authority and requires fresh checks even when emitted nucleotide bytes match.

## Version and compatibility boundary

| Surface | New identity |
| --- | --- |
| Original material request | `biocompiler.policy_component_material_request.v0.2` |
| Material profile | `biocompiler.policy_instance_component_mrna.v0.1` |
| Original assembly / proposal schemas | `biocompiler.policy_component_assembly_rule.v0.2` / `biocompiler.policy_component_assembly_proposal.v0.2` |
| Assembly profile | `biocompiler.policy_instance_component_assembly.v0.1` |
| Ordered union | `biocompiler.policy_instance_ordered_union.v0.1` |
| Service implementation | `biocompiler.ocaml.policy_instance_component_material.v0.1` |
| Capabilities | `policy_instance_material`, `policy_instance_material_producer` |
| Validation scope | `policy-instance-component-mrna-v0.1` |

Existing component operation names are reused. Python's immutable request
builder opts in with `instanced=True`; native Core/Verify validate the complete
schema/profile combination. Capability negotiation fails closed without the new
role and profile. Old two-slot schemas, projections, reports and resource-charge
branches remain unchanged. The original finite component-selection profile
explicitly rejects instance requests; automatic instance-library selection is
not implemented by this increment.

## Independent witness and distinguishing controls

The original A/B programs reuse one exact stateful edge fragment in two distinct
instances, `select_edge` and `exclude_edge`, around `control`. Their complete
material definitions are different. Both produce the independently declared
17-base RNA `CCAUGGCUUAAGGAAAA`. A/B differ in source state-reading behavior;
the reusable edge definitions remain unchanged. Expected molecules and carrier
projections are declared independently of generated candidates.

Each complete check retains the original 23 obligations and finite exploration
of 9 histories, 47 transitions and 48 started/matched prefixes. Native controls
cover missing/aliased ownership, link and join mutation, exact bases and chemistry,
source edits, consistent instance renaming with fresh authority, shared-capacity
overcommit and recovery, stale reports, and exhaustion without export.
The public SDK campaign retains all 26 existing component lifecycle observations
against the new independently supplied fixture, including producer-free Verify
and paired exact export. Mocked Python tests exercise version/role separation
and complete projection corruption controls without executing native programs.

The domain-only fixture exporter is private test infrastructure. It links no
producer or acceptance checker, and exports source declarations with
`acceptance: false`. Development feedback is separate from cross-platform,
installed-package and actual-main release validation.

The additive installed campaign reuses the exact supplied wheels and the existing
post-reinstall environment on Linux x86_64 and macOS ARM64, each on Python 3.11
and 3.14. A separately versioned fixture-provenance packet binds the private
exporter and five original source files. Each installed run retains 26 complete
protocol observations, two paired RNA/manifest ZIPs, complete package origins,
external native pins and its own command/log ledger. The comparison rechecks
original authority and every observation and ZIP across all four runtimes.
It preserves the earlier material/component/staged/researcher campaign receipts
and their mandatory release checks. No existing release receipt inherits the new
instance scope. These installed routes are source-written at this checkpoint;
successful execution is still pending.

## Validation checkpoints

- `a25f1428c`: focused Python transport and runner checks, strict core/policy
  typing, dependency boundaries and source inventories passed locally.
  [Hosted run 37785940459](https://github.com/logannye/biocompiler/actions/runs/37785940459)
  failed compilation because the new fixture-support library omitted its direct
  `zarith` dependency. It supplies no completed native acceptance.
- `2b998bd76`: corrected the fixture dependency and exact static link inventory.
  [Hosted run 37786545218](https://github.com/logannye/biocompiler/actions/runs/37786545218)
  is pending at this documentation checkpoint. Installed integration source work
  follows this commit and must be tested on its own final revision.

## Deliberate limits and subsequent work

- One RNA, one product, exactly four material features, and no delivered helpers.
  The instance-count bound is not a demonstration that every size or partition
  is materially realizable under this envelope.
- Complete-root ordered concatenation only; no slicing, rearrangement, new
  transforms or molecular-mechanism discovery.
- The witness exercises repeated stateful graph-fragment ownership. Its native
  execution remains pending. Repeating the same complete material definition
  twice in an accepted RNA is outside the demonstrated scope.
- The positive witness uses adjacent-root links. Longer crossed paths have
  structural and mutation controls, not a separate end-to-end positive witness.
- The versioned domain supports existing truth or staged primitive profiles;
  the new end-to-end witness exercises the truth family only.
- Global atomic-group names remain unique; arbitrary repeated grouped modules
  need a further source/ownership contract.
- Checking is whole-program and bounded. This is compositional construction,
  not an assume–guarantee theorem or cached proof reuse.

Priority 2 extends executable prerequisite closure. Priority 3 expands source
composition, priority 4 expands material members/helpers, and priority 5 adds
measured modular assurance only under a separately justified checking rule.
None follows merely from admitting a larger instance list. Model-to-material
contracts remain supplied premises; empirical function remains unassessed.
