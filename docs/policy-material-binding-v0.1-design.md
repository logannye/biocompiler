# Policy material binding v0.1: proposed implementation design

This note specifies the next SM-05/06 work in the
[semantic mRNA development plan](semantic-mrna-development-plan.md). It is a
design, not an implemented or accepted material route. The neutral construction
leaf and the implementation-preservation work have separate hosted acceptance
gates. Neither their source presence nor this document closes those gates.

The target is one complete, deliberately narrow path from an immutable Python
`BuildRequest` to exact RNA bytes and a complete manifest under supplied
executable and molecular contracts. Studio, conversational authoring, mechanism
discovery and biological viability are outside this work. A supplied contract
may be a premise of the software claim; the checker must still execute its
specified interpretation and establish every correspondence below. Whether that
contract holds in cells remains a separate empirical status.

## 1. First complete vertical profile

Proposed profile: `biocompiler.policy_truth_mrna.v0.1`.

Use the existing truth-policy family admitted by
[`Policy_implementation_binding_check`](../core/lib/checker/policy_implementation_binding_check.mli):
one executor, one encounter declaration with multiple distinct finite slots, one
truth observation, finite encounter truth stores, one or two exclusive rules,
and one initiating rule for the fixed product effect. Evidence, definedness,
ordered uncertainty reasons, atomic writes, rising edges, attempt correlation,
reset, end, freshness and timeouts retain their current primitive semantics.
Machines and every other unsupported source form remain unsupported.

The first accepted artificial witness should be a separately resolved version of
the exclusion policy, with the original source property and full finite domain
preserved. The original empty-catalog source fixtures and the original witness
whose hard property can be unknown remain rejection controls. Do not prune
unknown histories, weaken the property or install a material library into an
already assessed empty catalog.

The material subset is:

- Exactly one supplied composite component instance owning the entire actual
  primitive graph, including constants, state, evidence, arbitration and attempts.
- Exactly one supplied complete RNA template, one covalent delivered RNA member,
  one frame-zero ordinary CDS and one independently specified complete product.
- No delivered helper, extra ORF, complex, form-mapping branch, dose or copy-number
  calculation. Host/environment resources and observation/feedback boundaries
  remain explicit supplied contracts and do not count as delivered RNA.
- Exactly one material case in the initial material library. Selection is a
  checked bounded census of one; no optimization or general architecture-search
  claim follows. Multiple alternatives and helper-bearing compositions require
  a later profile with their complete checks.
- One exact clock relation and a component available from initialization through
  the entire inclusive checked horizon. No added observable latency, deferred
  bootstrap, asynchronous channel or inferred cancellation.
- All molecular members satisfy
  [PM-01–12](policy-mrna-completeness-v0.1.md), with stage ownership described
  below. The first fixture explicitly requests design/member/helper/ORF/product
  counts `1/1/0/1/1`; absent or wider count configurations are not silently
  equated with that request.

One component may own many primitives. The two encounter slots require two
independent state instances in the component model; they do not imply two RNA
members, two RNA copies or two delivery recipients. Encounter targets are not
automatically RNA recipients. This profile delivers its RNA to the original
executor role and checks the observation/effect target bindings separately.

## 2. Authority, candidates and identity domains

The material request is a new immutable external envelope:

```text
schema_version = biocompiler.policy_material_request.v0.1
profile = biocompiler.policy_truth_mrna.v0.1
realization_request       complete Policy_realization_request
material_library          complete supplied composite/material contract bodies
catalog_material_bindings complete original-entry-to-component relations
deployment_contracts      typed bodies for exact original DefinitionRefs
mrna_structure_authority  independent template/order/region/product/chemistry inputs
member_order              original ordered covalent member IDs
material_limits           decoding, reconstruction and publication work ceilings
```

The existing realization request already preserves the complete source document,
descriptor bundle, operating domain, primitive library, catalog bridges and
exploration budgets. Embed it unchanged. A material envelope must not replace
its domain, source map, assurance requirements, assumptions or budget declarations.

A material candidate is separate:

```text
schema_version = biocompiler.policy_material_candidate.v0.1
request_fingerprint
implementation            untrusted actual primitive graph
source_binding            untrusted original-source/graph anchors
component_instance        selected component/case identity and local-to-graph map
placements                actual selected member/recipient/compartment assignment
resource_bindings         proposed demand-to-provider allocations
product_bindings          proposed effect-symbol-to-encoded-product locations
content                   Construction_content candidate
```

The candidate contains no expected model, expected sequence, expected deployment
contract, accepted projection, or authoritative requirement outcome. Optional
saved reports are archival attachments only; replay reconstructs fresh reports.

Use full versioned identity records, never ID-only lookup. A source
`DefinitionRef` pins a `SemanticDefinition`; a `Pinned_identity` pins a model,
template, registry or other supplied body. These are different digest domains.
Every bridge retains the complete original catalog entry digest and its exact
operation and realization references, plus exact component/model/template pins.
It resolves all bodies and checks their categories and contents. Equal names or
equal digest strings over different schemas are not a correspondence.

The initial catalog-material relation extends the existing *external* catalog
bridge; it does not reinterpret the original catalog schema. Its closed fields
are `entry_id`, `entry_version`, `entry_digest`, `operation`, `realization`,
`component_identity`, `material_case_identity`, and `model_identities`. The model
set must equal the models authorized for this component by the original
realization bridge. A material row alone never grants host, environment or
delivery capabilities. Their exact original references need separate typed
deployment-contract bodies.

Reject unresolved or conflicting pins, duplicate identities, unknown fields and
unsupported clause interpretations. Preserve every dependency/evidence reference.
The existing realization admission rejects nonempty catalog dependency/evidence
closures; the first material profile keeps that restriction rather than silently
claiming to implement them. New physical-resource premises belong to the supplied
deployment/material body and must be mapped to the original chassis/environment
references. They cannot erase or bypass any original source dependency.

## 3. A component contains executable structure, not a source interpreter

Proposed schema: `biocompiler.policy_material_component.v0.1`.

```text
identity                  complete pinned identity for this supplied body
primitive_profile         exact current primitive transition profile
local_graph:
  nodes                   local IDs + complete resolved primitive model bodies
  wires                   ordered actual producer/consumer endpoint pairs
  external_inputs         local evidence/feedback boundaries
  atomic_groups           explicit arbiter and ordered commit membership
  semantic_exports        complete output-port inventory
  replication             exact executor/encounter layout, slot count and order
material_case             one exact supplied case identity
resource_demands          closed typed storage/timer/queue/input demands
product_contract          effect symbol and encoded product relation
context_requirements      exact chassis/environment/delivery body references
assumptions               retained conditional premises with stage disposition
```

Reuse the closed primitive and port types from
[`Policy_implementation`](../core/lib/domain/policy_implementation.mli). Extract
a source-independent graph-body representation if needed; do not embed a dummy
`Policy_implementation` authority, source AST, rule evaluator or `Behavior` in the
component. A local primitive model is the complete configured transition
definition, not merely its port signature or model digest.

The first correspondence requires an ordered bijection between component-local
nodes and the accepted implementation nodes. No operation is omitted, duplicated,
folded away or shared differently. Check full primitive configuration, model
identity, replication, every port, every wire, external boundaries, atomic groups
and scheduling-relevant list order. Register initial values, writer counts,
arbiter lanes/order, product constants, freshness, capacity, timeout and lifecycle
modes are all semantic fields. The global phase and observable profiles must
match exactly. The candidate cannot declare hidden output ports.

This exact graph reconstruction supplies a narrow compositional argument: both
graphs denote the same closed transition system under the checked renaming and
the same primitive version. If a future material component changes topology,
state encoding, sharing or latency, graph identity is insufficient; run independent
preservation on that actual reconstructed assembly before acceptance. Do not
quietly generalize this profile's bijection into an optimizer proof.

The checker obtains the accepted original implementation by freshly calling
[`Policy_preservation_check.check`](../core/lib/realization_checker/policy_preservation_check.mli)
and requiring its private `checked_implementation`. A copied evidence JSON or
the candidate's occurrence inventory cannot substitute for that value.

## 4. Executable material cases and complete carrier coverage

Proposed schema: `biocompiler.policy_material_case.v0.1`, with the closed mode
`exact_nominal_template_case`.

The first material interpretation is an independently supplied finite table with
one row. It is intentionally small enough to reconstruct fully. A row contains:

```text
identity
template                  full Payload_template, not a locator
member_order              exact original ordered member inventory
material_key              full independently supplied complete molecular records
decoded_graph             complete local primitive/configuration/wiring body
carriers                  typed coverage of all graph distinctions
product                    symbolic effect value + exact encoded-product authority
deployment_body_refs       exact required modeled-input/resource/context bodies
```

`material_key` contains exact complete molecule data, including spelling, nominal
chemistry, coordinates, required features and the expected member identities.
The checker first reconstructs actual content from the independent template and
then compares it to the material key. It evaluates the closed case table on that
actual reconstructed content and supplied deployment inputs. Exactly one row
must match. Zero matches means no supplied realization; multiple matches are
ambiguous authority and fail. Neither a template fingerprint nor an asserted
component name can skip that lookup or supply its returned graph.

The returned `decoded_graph` is fully typed and is then independently compared
to the accepted implementation as in section 3. This is a conditional executable
model-to-material interpretation supplied by the caller. It does not derive a
molecular mechanism from letters, predict expression or establish that the
declared transition system occurs in cells. The initial row is an artificial
software fixture, clearly labeled as such.

A carrier target is a closed sum, not a free-form path exemption:

```ocaml
type target =
  | Primitive_operation of local_node
  | Configuration_field of local_node * configuration_field
  | Replication_layout of local_node
  | Connection of local_endpoint * local_endpoint
  | Atomic_group of local_group
  | External_input of local_input

type material_site = {
  member : member_id;
  feature : feature_id;
  path : exact_coordinate_path;
}
type witness =
  | Material_case_field of case_identity * typed_case_field * material_site list
  | Modeled_resource_field of provider_identity * resource_field
  | Modeled_input_boundary of interface_identity * input_field
```

The checker derives the required target inventory by traversing actual typed
nodes/configurations/wires/groups/inputs. It compares that derived inventory to
the supplied carrier relation with exact coverage and unique ownership. The
candidate cannot define which fields matter. A material-case witness must resolve
to an actual field of the graph returned by the matching row; its value and
endpoints must agree. Its nonempty site inventory names actual supplied member
features with exactly matching coordinate paths in the reconstructed content.
Feature reuse across targets is explicit in the supplied relation, not inferred
from names. A resource/input witness must resolve to a typed supplied
body whose interpretation produces that exact value or boundary. There is no
`metadata`, `assumed_implemented` or generic `host_supplies_everything` escape.

Fixed primitive logic and fixed internal wiring may share the whole-component
case as their material witness. Their complete returned operations, parameters
and endpoint pairs are still checked individually. This permits many operations
per RNA without inventing a separate RNA fragment for every Boolean gate.

Fine-grained sequence encodings can be added later as a separate closed witness
mode: exact supplied feature path plus a bounded codebook from actual bases and
nominal chemistry to a typed configuration value. Do not add a generic user
callback, Python evaluator, arbitrary expression interpreter or unconstrained
manifest field to this first decoder.

Changing a timeout while retaining the old RNA and original case must fail:
evaluation returns the old timeout. An identical RNA may acquire different
conditional behavior only under a new independently supplied material/context
authority whose typed interpretation actually supplies the new value. That is a
new complete request and requires fresh source, implementation, context and
material checks; recomputing candidate hashes does not authorize it.

## 5. Product, deployment, time and resources

### Product identity

The source product parameter is a text symbol such as `fixture.product.alpha`;
it is not automatically an amino-acid spelling. The supplied product body binds
the exact original effect operation, parameter name and symbol to one encoded
product identity, one member/CDS feature and an independently specified complete
protein spelling. The checker derives the effective symbol from the accepted
actual `Product_constant`, checks its original source binding and independently
checks CDS translation through the mRNA structure leaf.

Requested/initiated/completed/failed/timed-out remain distinct attempt events.
An initiation event is not proof that a physical protein was synthesized, and
selection/exclusion flags do not stop an existing attempt or clear its product.
The supplied component contract must preserve the full current lifecycle. An
unimplemented output, secretion, clearance or persistence promise remains an
explicit unmet obligation; it is never replaced by the presence of a CDS.

### Context and recipient closure

Proposed schema: `biocompiler.policy_material_deployment.v0.1`. Each body is keyed
by its full original `DefinitionRef` and has one closed interpretation: chassis
resource supply, observation/feedback boundary, finite environment compatibility,
or delivery/availability contract. Check the full original chassis ID/version,
human immune classification, operational-model reference, capabilities,
interfaces, environment and delivery arrival/expression/activation/contract
references. Prose meaning, an evidence label or lineage name does not supply an
executable interpretation.

The body specifies exact executor role, compartment, available resources and
input boundaries. Its finite observation/feedback interface must cover the
original domain's known/missing/invalid/conflicting/silent histories, observation
age, reset/end and late feedback; it cannot filter a hard history out of the
already checked domain. Target identities and slot/generation separation remain
those of the original domain. Evidence about an encounter target must not be
rebound to the RNA recipient merely because both are represented as strings.

Use the existing typed
[`Placement`, `Helper`, `Delivery_group`](../core/lib/domain/architecture_contract.mli)
leaves. For the first profile, all placements name the single executor and member,
helpers are empty, and any `same_recipient` obligation is checked directly.
Unknown recipient binding, same-population-only substitution for same-recipient,
unresolved external helper, and delayed or cyclic bootstrap remain unsupported.
Do not mutate the source assessment's unresolved-obligation list. The new report
adds a discharge ledger mapping each original obligation to fresh stage evidence;
remaining non-empirical obligations prevent complete material acceptance.

### Exact clock relation and availability

The policy clock is not automatically the legacy deployment clock
`declared_exposure_start`. Require a supplied relation containing the original
clock reference, its exact rational period in seconds, an explicit origin in the
deployment clock, and an exact mapping of every checked tick. Validate it against
`Policy_operating_domain.resolution`; callers cannot choose a different period.

Use closed decimal-string fields decoded directly to `Q.t` for the policy
origin, period and availability bounds. The legacy
[`Architecture_deployment.Time`](../core/lib/domain/architecture_deployment.mli)
decoder accepts JSON numbers and therefore cannot represent every exact policy
decimal without possible loss. Perform all conversion/comparison in `Q.t`;
never convert policy time through binary floating point or round deadlines.
The old deployment checker requires an
`Architecture_request`; extract the small source-neutral interval core or write
the policy interval check against these typed leaves. Never synthesize an old
architecture request solely to call it.

The initial profile requires guaranteed availability at every tick from 0 through
the inclusive domain horizon. Using the declared interval semantics, worst-case
onset must be no later than tick 0 and earliest permitted expiry must be no
earlier than the final required tick. Check the same relation for each resource
and input boundary. The supplied arrival/expression/activation bodies justify
initial availability conditionally; the compiler cannot infer it from sequence.
Payload/effector persistence fields are not ignored: initially reject non-null
ones unless their exact lifetime interpretation is implemented and checked.

### Formal resource ledger

The initial resource schema uses exact nonnegative integer capacities with
versioned units and explicit executor/encounter scope. At minimum, derive demands
for truth-register cells, evidence-row records, rising-history cells, generation
counters, active-attempt records, retained-correlation records, timers and bounded
control-event queues. Derivation comes from the actual graph and original finite
domain, not candidate totals. The resource profile must define every formula and
its overflow bound before a checker admits that unit.

For example, one encounter register consumes one truth cell per slot. Attempt
bank capacity is simultaneous active attempts **per bank and slot**; cumulative
allocations and retained correlation are separate. Reset/end does not permit old
attempt identity reuse or free a correlation record still required for late
feedback. Preserve all distinctions in the supplied component storage model.

Bind every derived demand to a concrete component-internal allocation or a
supplied host/environment resource. Check scope, recipient, compartment, lifetime,
capacity and sharing. For the first profile, allocations are exclusive unless a
closed immutable-resource rule explicitly permits sharing. A supplied resource
capacity is a conditional model premise, not empirical evidence of cell capacity.

Runtime work limits, retained diagnostic traces and report byte budgets are
compiler verification resources. They are not biological memory, RNA copies,
doses, or evidence of a physical timer. Conversely, a clock or state field used
by runtime execution cannot disappear merely because software memory is available.

### Counts and lengths

Keep each source count as its own checked quantity. The first profile requires
explicit source values `design_count=1`, `member_count=1`, `helper_count=0`,
`orf_count=1`, `product_count=1`, and an original material request containing that
exact ordered inventory. Count one declared RNA design, one delivered member,
zero delivered helpers, one checked CDS and one independently identified encoded
product. Do not count attempt multiplicity, encounter slots, host providers or
RNA copies as any of those values. Copy number and dose remain unsupported when
present. Additional maximum-length constraints supplied with the material request
are checked independently and cannot relax an original constraint.

Before accepting larger inventories, freeze general counting semantics, helper
and product sharing, alternative design counts and every applicable exact/max
limit in a new profile. The narrow rules above are not aliases for those broader
concepts.

## 6. Fresh independent checking algorithm

1. Bounded-decode the complete external request and separate candidate. Resolve
   every supplied body by full identity; reject unknown schemas, conflicting
   duplicates, missing source bindings and unsupported profile cases.
2. Repeat native source/operational correspondence, catalog admission, independent
   graph binding and complete-domain preservation/requirement checking. Obtain a
   private checked implementation only after all requested hard requirements and
   nonvacuity conditions pass. Exhaustion never supplies this value.
3. Resolve the one original catalog/material case and its supplied component.
   Derive and check the complete component-local graph correspondence. Reject
   an interface-compatible component whose transition body differs.
4. Derive the semantic resource, product, input and clock obligations from that
   actual component/implementation. Check all original deployment fields and the
   typed supplied context bodies, recipient assignments and availability. Retain
   empirical premises without upgrading their evidence status.
5. Call the neutral
   [`Construction_check.check_template`](../core/lib/checker/construction_check.mli)
   on the independently supplied template and original member order. Require its
   private exact-content success. The candidate's own template/pins are never the
   expected arguments. Its `context_status` and `payload_completeness` remain
   `unassessed`; a later stage cannot rewrite that leaf receipt into a larger claim.
6. Evaluate the material case on the reconstructed complete content and checked
   context inputs. Reconstruct its returned typed graph and every carrier target;
   compare them against step 3. Validate exact node/config/wire/group/input
   coverage, product correspondence and allocation ownership. This is the
   material-to-model direction that prevents a graph label from substituting for
   material realization.
7. Freshly run the mRNA structure checker for PM-02–09 using independently supplied
   required regions, products and nominal chemistry. That checker also repeats
   neutral content correspondence. Independently require its authority's template,
   member order, region/product/chemistry records to equal the selected original
   material case; do not accept an unrelated structurally valid RNA.
8. Enforce PM-01, PM-10 and PM-11 at the policy material boundary. Check the exact
   original ordered member/helper inventory, full configuration/carrier coverage,
   all original counts/limits and unresolved-obligation discharge. Require that
   all original non-empirical obligations are accounted for.
9. Emit an opaque checked-material result and a fully pinned report. Acceptance
   for export still requires SM-07's full-request replay and publication checks
   for PM-12. A decoder or imported report cannot construct the private result.

The checker library must not link a lowering, component-selection, assembly or
export producer. It may share typed records, primitive semantic definitions and
canonical arithmetic with producers; it does not call them to compute expected
graphs, content, carrier coverage or result labels.

## 7. APIs and reuse boundaries

Proposed new modules are `Policy_material_request`, `Policy_material_contract`,
`Policy_material_candidate`, `Policy_material_context_check` and
`Policy_material_check`. Keep the component/case/resource declarations in one
small closed module initially rather than introducing an unrestricted generic IR.

The first independent leaf is `Policy_material_binding_check` in
`realization_checker`, because it consumes the private preservation result;
placing it in the lower `checker` library would introduce a dependency cycle.
It also consumes a fresh private result from
[`Policy_mrna_structure_check`](../core/lib/checker/policy_mrna_structure_check.mli).
Its original structural authority is
[`Policy_mrna_structure`](../core/lib/domain/policy_mrna_structure.mli), including
the full template, member order and independently spelled/pinned product. These
inputs must match the selected original material case exactly.

For this first whole-graph leaf, a new private local-kernel record can resolve
its model bodies through the original supplied primitive library and retain all
graph lists without changing `Policy_implementation`. Its decoder establishes
bounded shape only. A total ordered bijection to the private checked implementation
establishes the existing port, cycle, scheduling and replication invariants.
No unmatched local kernel executes or gains graph-validity authority. A future
component runtime or non-bijective composition can justify extracting a common
source-neutral graph validator; this narrow leaf does not need a partial second
validator or a dummy source-bearing implementation.

The public checker boundary should resemble:

```ocaml
type result
type checked_material
val check : request:Policy_material_request.t ->
  behavior:Policy_operational.behavior ->
  candidate:Policy_material_candidate.t -> result
val report : result -> Json.t
val accepted : result -> checked_material option
val content : checked_material -> Construction_content.t
val replay : request:Policy_material_request.t ->
  behavior:Policy_operational.behavior ->
  candidate:Policy_material_candidate.t -> saved:Json.t -> result
```

`accepted` here means complete conditional material correspondence for this
profile, not public export permission or empirical/human-use admission. The
report must state that distinction. A final SM-07 checked-build type owns export.

Existing leaves to reuse:

| Leaf | Role and boundary |
| --- | --- |
| `Policy_realization_request`, `Policy_realization_admission`, `Policy_preservation_check` | Original source/domain/model authority and fresh checked implementation. Existing claims remain unchanged. |
| `Payload_template`, `Construction` root/step/member/requirement records | Complete supplied molecular recipe; no generated source authority. |
| `Construction_content`, `Construction_producer.construct_template`, `Construction_check.check_template` | Source-neutral content proposal and independent reconstruction. No dummy `Circuit_request`; no contextual acceptance from the leaf. |
| `Molecule`, `Molecule_chemistry`, `Molecule_coordinates`, `Molecular_transition` | Exact full molecular records and nominal chemistry/coordinate consistency. Wider decoded forms do not satisfy the narrower mRNA profile. |
| `Transition_check` | Independent declared chemistry/feature transitions over reconstructed inputs. |
| `Architecture_contract.Placement`, `Helper`, `Delivery_group`; `Architecture_deployment` | Typed contextual declarations. Existing full architecture wrappers require legacy source types and are not the policy entry point. |
| `Component.Dependency`, `Capability`, `Resource` | Reusable metadata where units/scope match exactly. Legacy Boolean/scalar port domains must not replace rich truth/definedness/event/attempt ports. |

The old `Architecture_refinement` owns a full `Behavior` and the old architecture
checker rejects unmapped component resources/operating domains. Preserve those
checks. Do not relax legacy admission to make the new policy path fit.

## 8. Distinguishing tests and phase order

Freeze independently authored positive source, domain, component case, complete
mRNA template, expected decoded graph and exact molecular records before writing
the material producer. An early structural-only positive retains unassessed
implementation/material/export statuses until the complete chain is executed.

| Control | Required distinction |
| --- | --- |
| Empty original catalog plus supplied model/material library | No source authorization; reject. |
| Same component interface, different truth/definedness/lifecycle transition | Reject actual graph correspondence. |
| Changed deadline/capacity/initial truth with unchanged old material case | Reject configuration-to-material correspondence, even with all candidate hashes recomputed. |
| Deleted/extra/misrouted wire, atomic group or external input | Reject independently derived carrier/graph inventory. |
| Two encounters collapsed into one state allocation | Reject replication/resource/scope mapping. |
| Nominal target and RNA-recipient identities swapped | Reject role/subject correspondence. |
| Changed source product symbol; unchanged CDS | Reject product relation unless a new original contract supplies and validates it. |
| Same protein after a synonymous nucleotide substitution | Reject exact nucleotide/recipe authority. |
| Changed source root plus recomputed candidate pins | Independent reconstruction must reject old content. |
| Wrong clock origin/period; availability starts after tick 0 or ends early | Reject contextual timing. |
| Same-population co-delivery substituted for same-recipient | Reject original delivery obligation. |
| Insufficient active attempts, retained correlations, rows or truth cells | Reject resource capacity; do not prune domain branches. |
| Host provider counted as RNA; hidden helper; extra member/ORF/product | Reject exact distinct inventories and source counts. |
| Core-only extent; missing cap; unknown ends/modification inventory; bounded tail | Reject the complete-mRNA profile. |
| Shifted/reversed/overlapping/gapped regions; wrong CDS frame or product | Reject PM geometry/translation. |
| Modification within the ordinary CDS; recoding; internal stop | Reject the first translation profile. |
| Correct RNA under another original request/material case | Reject full authority correspondence. |
| Saved PASS, stale binary identity, altered manifest or withheld FASTA member | Fresh export cannot succeed. |
| Work/byte/alternative budget exhausted | Incomplete/resource result; no checked material or export. |

Recommended implementation batches:

1. **Material authority and negative admission:** strict schemas, full-ref closure,
   exact single-case inventory, product-symbol binding and original field
   coverage. Add source-independent component/case literals and malformed controls.
2. **Independent reconstruction:** decode the actual material case, prove ordered
   graph correspondence, derive complete carrier targets and all formal resource
   demands, and check typed deployment/clock/recipient constraints. No producer
   is needed to test these checks.
3. **Molecular conjunction:** connect fresh neutral construction, fresh PM-02–09,
   contextual PM-01/10/11 and full authority cross-checks. Produce a private
   checked-material result only after the complete conjunction passes.
4. **Untrusted material producer:** select the sole admitted supplied case,
   construct with the neutral producer, emit proposed mappings and independently
   check them. It cannot add a sequence, context premise or material contract.
5. **SM-07 integration:** versioned native compile/check/replay/export operations,
   thin immutable Python SDK/CLI routing, full original manifests, and atomic
   FASTA-plus-manifest publication after fresh verification. Test with producers
   absent and no Python semantic fallback.
6. **Hosted acceptance and later expansion:** complete exact-revision native and
   installed campaigns; then add bounded alternatives, helpers and broader
   counts/semantics through new complete profiles. Record open work rather than
   broadening the first profile's claim.

All native compilation, execution and packaging remain hosted. Existing empirical
statuses and legacy profile results retain their meanings throughout these batches.
