# Core architecture: implementation priorities for this session

Planning snapshot: 2026-10-08. User priority: develop the compiler architecture
for correctness and compositionality. Researcher usability remains a product
goal, but CLI packaging, agent integrations and laboratory orchestration are
secondary to this session's core work.

This refines the [product vision](product-vision-and-integration-roadmap.md) and
continues the SM tasks in the [semantic development plan](semantic-mrna-development-plan.md).
It records proposed work, not implemented capabilities or new acceptance.

Implementation checkpoint: the user authorized execution after this plan.
Priority 1 now has a [versioned contract](policy-instance-composition-v0.1.md),
domain/producer/checker/service changes and independent witnesses. The development
revision `c0366fc92` passed its hosted native build and all 33 focused native suites;
all six SDK campaigns also passed in run `37788462656` (156 retained observations).
Integration is on `codex/core-instance-composition`; complete installed/cross-platform
and actual-main validation remain pending. Priority 2 was explicitly selected as
a separate bounded increment while those gates run, in
`codex/dev-policy/prerequisite-closure`; its [contract](policy-prerequisite-closure-v0.1.md)
and implementation are in progress. Priorities 2–5 must not inherit priority 1's
acceptance. Priorities 3–5 remain unimplemented follow-on work.

## Assessment and recommendation

Biocompiler already has a substantial independently checked compilation path.
The largest architectural gap is the generality of the programs, component
assemblies and contracts that can pass through that entire path. The next
increment should make reusable components compose correctly beyond the current
fixed topology, while retaining the existing semantic and material checks.

**Recommended session objective: implement one bounded, instance-based component
composition profile, demonstrated by three supplied fragments implementing an
already supported program and producing one complete RNA.** Keep the source
semantics and finite operating domain fixed so that the increment isolates
composition correctness. Complete this vertical slice before expanding products,
helpers, source semantics or proof strategies.

This is compositional construction with whole-program verification. It does not
yet establish that separately verified components can be combined without
checking their complete interaction.

## Reviewed baseline and existing strengths

The review inspected released source `b81d4ee4dcc97c77f549b98a2994ddd7877839c9`
and main `e253ed5b3370af9a7d8b9ba96af2e7f8f025798a`, whose change over that
release is README-only. The
[researcher alpha](https://github.com/logannye/biocompiler/releases/tag/researcher-alpha-1)
is published. Older pending-release paragraphs in development plans are historical,
not evidence that the release must be repeated before planning new work.

The following mechanisms exist and should be extended:

- Independent source and candidate execution, complete exploration of the
  admitted finite domain, exact observable correspondence and nonvacuous hard
  requirements: [preservation checker](../core/lib/realization_checker/policy_preservation_check.mli).
- Typed local fragments, complete ports/wires/atomic groups, exact model pins and
  explicit external inputs: [component fragment](../core/lib/domain/policy_component_fragment.mli).
- Independent reconstruction of the component union, material carriers, exact
  sequence, coordinates and chemistry:
  [assembly checker](../core/lib/realization_checker/policy_component_assembly_check.ml).
- Original deployment/provider binding and aggregate resource accounting:
  [context checker](../core/lib/realization_checker/policy_component_context_check.ml).
- Private checked values joining preservation, assembly and context acceptance,
  followed by discharge of every original obligation. Unknown obligations stay
  unresolved: [material coordinator](../core/lib/realization_checker/policy_component_material_check.ml).
- Fresh producer-free verification and original-bound paired FASTA/manifest
  export; stored reports cannot mint acceptance.

The review found no confirmed soundness defect in this sampled path. This was
source inspection, not exhaustive auditing or a new execution-based validation.
Producer independence and regression coverage do not constitute a formal proof
of checker soundness. Supplied model-to-material contracts remain premises.

## Ranked core gaps

| Priority | Existing boundary | Implementation direction and value |
| --- | --- | --- |
| 1. Instance-based component composition | Assembly uses literal `Decision` and `Driver` slots, prescribed links, a special driver shape and one two-root join. | Separate reusable definition identity from instance identity; check a bounded explicit connection and material-assembly graph. Enables reuse inside a program without conflating state, resources or material. |
| 2. Executable prerequisites and contract closure | Model catalog dependencies/evidence must be empty; richer model/provider clauses and source assumptions are rejected. Existing typed provider and capacity checks cover a narrower contract. | Admit a small closed vocabulary of prerequisites, connect each to original context or an independently checked provider, and reject missing or circular justification. Enables meaningful conditional composition. |
| 3. Broader source composition through one complete semantic family | Staged lowering/binding fixes one observation, one product parameter, one five-state machine, seven transitions and two effects. | First candidate: two independent truth observations on the same encounter subject, preserving separate identity, freshness and unknown states through material binding. Then expand finite machines one explicit profile at a time. |
| 4. Multiple products, RNA members and delivered helpers | The newer policy material context requires one RNA, one ORF, one product and zero helpers. | Extend the source-effect-to-product-to-member relation, dependency closure and deployment checks to one bounded multi-member case. Makes composed therapeutic actions materially representable. |
| 5. Scalable compositional verification | Preservation freshly explores the full finite causal domain; local acceptance is not a reusable proof of safe interaction. | After measuring limits, introduce a checked state abstraction or a narrowly specified assume–guarantee rule. This is a new assurance mechanism, not a cache of passing reports. |

Evidence for these boundaries is in the
[assembly-rule interface](../core/lib/domain/policy_component_assembly_rule.mli),
[assembly-rule checks](../core/lib/domain/policy_component_assembly_rule.ml),
[realization admission](../core/lib/checker/policy_realization_admission.ml),
[staged lowering](../core/lib/compiler/policy_staged_lowering.ml),
[independent binding checker](../core/lib/checker/policy_implementation_binding_check.ml)
and [context checker](../core/lib/realization_checker/policy_component_context_check.ml).
These restrictions are explicit scope boundaries, not correctness bugs to remove
without replacement semantics.

Some broader material architecture already exists under the older `Behavior`
representation: many-to-many bindings, helper grounding, capacity, placements
and availability. Reuse the
[architecture contracts and checks](payload-architecture-v0.1.md) through an
explicit policy mapping where their meaning fits. Their existence does not
establish support in the newer policy-to-material path. Similarly,
`Policy_mrna_structure` already represents multiple members; changing a count
check alone would not implement complete multi-member acceptance.

## Priority 1: the bounded session deliverable

### Define the contract and witnesses before the producer

Introduce a separately versioned assembly profile with a finite declared instance
limit. An instance references an immutable component definition and owns qualified
local node, port, state and resource identities. Links explicitly identify both
endpoints, signal types, replication/scope and supplied material carriers.

Limit this profile's material construction to bounded ordered concatenation of
complete supplied roots, such as three roots and two joins. Retain the current
chemistry and feature-disposition rules; arbitrary slicing, rearrangement or new
construction transforms are outside this increment.

Keep the existing primitive semantics, exact clock, observation projection and
supported source family. Retain the original operating domain and assurance
request. The producer cannot invent premises, hide an observable operation or
change the domain to make an assembly pass. Atomic groups remain wholly local
unless a separately specified cross-component execution contract is implemented.

Freeze an independently authored three-fragment assembly, full original material
authority, expected behavior and exact RNA. Demonstrate reuse across more than
one composition; add a repeated-definition instance witness where the existing
source graph permits it. If repeated stateful instances need new source semantics,
record that as a subsequent vertical profile rather than broadening this one
implicitly. A fragment count alone does not demonstrate safe instance reuse.

### Build independent checking before automatic arrangement

Generalize the existing original assembly authority and checked interfaces;
do not create a competing source representation or synthesize authority from
the producer's proposal. Independently reconstruct:

1. Every selected instance, primitive, configuration, external input and boundary.
2. Total local-to-global correspondence, wires, exports and atomic groups, with
   no missing, duplicated or extra behavior.
3. State/writer/attempt ownership, feedback correlation and permitted global
   dependency structure under the current execution rules.
4. Every material root, join, carrier, feature, base, coordinate and chemistry
   declaration, still yielding one complete RNA and one product.
5. Provider bindings, per-instance demand and shared capacity, including record
   widths affected by qualified identifiers.

Then use the existing independent whole-program preservation and requirement
checks over the complete original finite domain. Retain the private acceptance
chain and complete obligation ledger. Structural typing alone is insufficient:
two locally valid components can still interact incorrectly or overdraw a shared
resource.

The lowering producer can subsequently arrange these admitted fragments. Thin
SDK and native profile-routing changes are part of making the core path usable
and testable; a new CLI or agent transport is not part of this slice.

### Acceptance evidence

Require a complete positive source-to-material witness and distinguishing
negative controls, with independently fixed expectations:

- Consistent instance renaming preserves meaning after fresh checks; identity
  changes still receive new artifacts and any changed capacity calculation.
- Missing/extra nodes, duplicate writers, input aliasing, crossed encounter or
  attempt feedback and altered atomic ownership cannot be accepted.
- Incorrect wiring, incompatible scope, stale component pins, missing carriers,
  bad junctions and changed sequence/chemistry fail at the intended check.
- Shared resource overcommit rejects; sufficient original capacity accepts.
- Changed source or component authority requires fresh reconstruction; unchanged
  RNA bytes do not preserve old acceptance.
- Resource exhaustion remains incomplete, and failed or incomplete checking
  cannot reach accepted export.
- Existing two-slot profiles preserve their meaning. Fresh standalone Verify
  reproduces the new result from independent original authority and publishes
  the exact paired artifact only on complete acceptance.

Map the work to SM-05, SM-06 and SM-09, with the relevant SM-01/SM-08 witness
entries. Do not turn the entire historical syntax census into an unrelated
prerequisite, or count source-written tests as executed evidence.

## Subsequent core increments

**Priority 2: typed prerequisite closure.** Begin with a finite acyclic dependency
graph and a small vocabulary of interface, resource and availability requirements.
Each obligation retains its declaring component, original context, scope and
exact dependency pins. Leaves must resolve to supplied environmental premises
or independently checked guarantees; a component cannot justify its assumption
with its own promised behavior. Unknown, unmet, contradictory and unsupported
contracts remain distinct. Do not interpret prose assumptions as predicates,
allow predicates to exclude bad candidate outputs, or treat empirical evidence
references as proof that a biological contract holds. Extend current checks and
private values rather than adding a parallel report-only proof graph.

**Priority 3: one source-family expansion.** Two truth observations are a useful
first test of whether the new composition architecture is reusable. Preserve
distinct input channels, subjects, timestamps, freshness and missing/stale/conflicting
evidence. Exercise same-subject conjunction, discordant timing and swapped or
cross-subject bindings over an explicitly bounded domain. Implement source
admission, lowering, primitive behavior, independent correspondence, resources,
material carriers and verification together. Later general machine topology,
priority arbitration, cancellation or quantitative values each need the same
complete treatment. A primitive-runtime feature alone is not material support.

**Priority 4: complete multi-member implementation.** Start with two explicitly
bound products/members in one declared recipient context, then one grounded
helper dependency. Preserve source effect, implementation instance, product and
member identities separately. Reuse existing construction and architecture
predicates while checking every member, dependency, bootstrap condition,
availability window, recipient/compartment, shared capacity and co-delivery
premise. Added executable helper behavior needs its own checked observation and
preservation relation; it cannot be hidden in a manifest. Software dependency
closure and actual biological availability remain separate claims.

**Priority 5: modular assurance.** First measure where full exploration limits
useful composition. For a small supported rule, specify exactly what a component
guarantees, what the environment must provide and which interference is excluded.
Prove or independently check the rule before using it to avoid global exploration;
compare it against exhaustive small cases as a regression check. Retain explicit
bounds and dependency invalidation. Neither tests nor matching hashes establish
an unbounded composition theorem.

## Execution boundaries for this session

Make priority 1 the core implementation objective. If it exceeds one coherent
batch, checkpoint the precise implemented and validated scope; do not label
schemas or a standalone linker as a completed therapeutic compilation profile.
Proceed to priority 2 only after completing that slice or explicitly selecting
a separate fully bounded increment. Priorities 3–5 are ordered follow-on work,
not a promise to complete all five in this session.

Existing typed-authoring and feedback work is already present on development
branches (`a64662fe7`, `23abe3e14`), with further encoding work at `439fae8a4` and
active local changes. Preserve their owners and reuse compatible work when
needed. None is a reason to recreate authoring infrastructure, take over those
checkouts, or transfer their historical test acceptance to a new core revision.

Use an isolated implementation checkout and refresh main/branch state before
editing. Keep local feedback to pure-Python, formatting, typing and static checks.
Run OCaml/Rust compilation and native tests on hosted infrastructure. Batch one
coherent development scope, then complete the required installed/cross-platform
integration and fresh actual-main gates when integrating. Follow
[development validation](development-validation.md); report the exact revision,
platform and scope actually tested.

CLI polish, new agent protocols, lab schedulers, active-learning services,
empirical component qualification and performance-only encoding work remain
separate tracks. Empirical work is essential to eventual usefulness, but it does
not block building a correct compiler under explicitly supplied contracts.
