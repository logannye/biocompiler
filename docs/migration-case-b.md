# Case B: checker-led OCaml migration slice

Initially prepared 2026-10-01 from checkout `6156ed2841fd3308df833f1afe0e3f6af5d12bf6`
and the uncommitted language-foundation work. This is the dependency and acceptance
map for roadmap batch B1, followed by the same slice's producer in B2. It records
validated internal checkpoints and remaining acceptance work, not completed OCaml architecture validation.

The foundation passed all hosted gates and was merged in PR37. The subsequent
domain batch passed every hosted gate and was merged in PR38. It implements
internal OCaml BuildRequest, Behavior and molecular coordinate decoders. Its retained-request tests compare full/semantic identities
and reject altered declarations. These checks do not execute the case B timeline,
reconstruct candidate behavior or certify its sequence and architecture. The
remaining acceptance responsibilities below still apply in full. PR39 subsequently
validated circuit declarations and independent source-to-Behavior correspondence,
including both original-source and supplied-model case B pairs. Its
[receipt](../protocol/migration-source-correspondence-validation.json) binds the
exact source, tested merge, native platforms and integrated main validation.

PR40 B1.05 is merged with the full per-role reference evaluator for all 38 v0.1 and four v0.2 operation kinds. [Run 36935066451](https://github.com/logannye/biocompiler/actions/runs/36935066451) passed all required gates, including 2,095 tests on each Python version and 12 native suites on both platforms. The retained corpus covers 66 programs, 86 complete traces, 23 evaluator failures, 16 parser failures and all 24 case B variants; independent literals and 1,948 numeric cases supplement it. The [receipt](../protocol/migration-reference-execution-validation.json) records exact identities. The separate [post-merge run](https://github.com/logannye/biocompiler/actions/runs/36936774523) also passed every required gate. This completes per-role source execution, not candidate reconstruction, coupled transport or RNA acceptance.

### Scoped checkpoint status

Reread this map with the [roadmap checklist](language-migration-roadmap.md#scoped-implementation-checkpoints) before each batch; check only a validated scope.

- [x] PR37 foundation: merged, full CI and integrated main validated; [receipt](../protocol/migration-foundation-validation.json).
- [x] PR38 BuildRequest/target, Behavior declarations and coordinates: merged, full CI and integrated main validated; [receipt](../protocol/migration-domain-validation.json).
- [x] PR39 circuit declarations and independent source correspondence: merged, full CI and integrated main validated; [receipt](../protocol/migration-source-correspondence-validation.json). Complete human wrappers subsequently passed full PR42 validation; their downstream obligations remain unresolved.
- [x] PR40 B1.05 per-role reference execution: merged after complete exact-revision CI; 2,095 tests per Python and 12 native suites per platform.
- [x] PR40 integrated-main validation: [run 36936774523](https://github.com/logannye/biocompiler/actions/runs/36936774523) passed at integrated revision `10382dd5c662c924a460a5113cbd5d58b3dffe48`.
- [x] Fresh `bioc_compiler.Lowering`: 31 productions, 32 intended failures and six literals passed full PR41 validation; merged.
- [x] B1.06 pins/component-contract/Unicode prerequisites: all records, algebra and diagnostic witnesses passed full PR41 validation; merged.
- [x] B1.07 molecular provenance and chemistry prerequisites: all record, rejection, context and resource checks passed full PR41 validation; merged.
- [x] PR42 complete B1.02 wrapped authority, B1.06 component subset and B1.07 molecules/sets/artifacts, plus exact decimal declarations; [receipt](../protocol/migration-complete-domains-validation.json).
- [x] PR42 separate integrated-main run 36940233185 passed every required gate.
- [x] PR43 architecture leaf/construction declarations and independent required-region checker passed complete PR validation; [receipt](../protocol/migration-construction-domains-validation.json).
- [x] PR43 integrated-main validation, run 36943390725, passed every required gate.
- [ ] Remaining full B1.06 architecture authority, full B1.07 independent reconstruction and B1.08 source-manifest checking are implemented in the next batch, pending hosted validation.
- [ ] B1.08 manifest/ledger/architecture reconstruction, B1.08a independent candidate execution if claimed, and B1.09 acceptance/protocol exposure.
- [ ] B2 complete producer and paired RNA/manifest export, followed by the remaining product migration gates.

The validated domain batch checks explicit-unit contracts and nominal chemistry.
PR42 validated complete component models, human source wrappers and molecular records/sets through all required PR gates. PR43 validated architecture leaves, transitions, construction records and required-region checking. Refinement templates,
construction operations and architecture reconstruction remain open. A supplied pin or provenance
record remains a declaration. Imported domain-check claims cannot become fresh
local assessments. Lowering derives its own output and requires the independent
source checker before returning; it is not the architecture producer.

`Diagnostic_text` deliberately fixes missing-coordinate reasons to
`python_repr_unicode14.v1`, with a checksum-pinned official Unicode 14 table and
retained license. Newly assigned characters can change diagnostic text and fresh
assessment hashes relative to newer Python repr; raw authority and semantic
statuses are preserved. This is an explicit diagnostic exception, not a general
canonicalization normalization. The [core guide](../core/README.md#domain-migration)
lists the hosted direct commands, all 17 configured native suites and corpus
counts. The [PR41 receipt](../protocol/migration-lowering-contracts-validation.json) records complete hosted PR and integrated-main validation; full architecture and construction remain open.

The language decision is fixed. The immediate objective is to accept or reject an
existing Python-produced stateful RNA architecture candidate against separately
supplied complete authority using a standalone OCaml checker. No Python compiler,
matcher, source-manifest producer, assembler or semantic checker may supply the
OCaml checker's answer.

## 1. The actual fixture

Use `make_architecture_request("B")` in
[payload_architectures.py](../examples/payload_architectures.py). The source and
supplier model are authored in separate functions, `source_program` and
`contract_program`. The supplier function does not consume the source artifact.

The Python reference path was exercised during preparation using the existing
pure-Python implementation, with no native build. Its outcome was `compiled`,
translation and construction complete, no unresolved translation obligations,
`search_verified=false`, empirical validation `unknown`, and human admission
`not_admitted`. This observation is baseline inventory, not an OCaml validation
receipt or a substitute for the required hosted gates.

| Property | Actual case B |
| --- | --- |
| Request | `biocompiler.payload_architecture_request.v0.1`, ID `artificial-architecture-b` |
| Build | `biocompiler.payload_architecture_build.v0.2` |
| Source | `BuildRequest` wrapping `architecture_source_B` intent |
| Behavior profile | **`biocompiler.behavior.v0.2`**, with `integral_step=null`; no integral or channel operations are used |
| Source size | 33 nodes, 8 roots, 1 role, 5 rules, 1 finite state, 6 behavior requirements |
| Source execution | 5 installed outputs, including 4 state assignments; 1 retained state record; 34 source-ledger entries |
| Plan | 47 ledger entries; one selected explicit refinement and instance, `b.one_rna` |
| Runtime ownership | 11 nodes: one state, five rules, four state-setting actions and one secretion action |
| Components/material | One composite component, one template, one root, one output RNA, one placement |
| Construction | Strict mode; no transformation steps, complexes or experimental amounts |
| Optional architecture contracts | No helpers, channels, connections, availability records, deployment requirements or requested functional-control requirements |
| Material fixture | Artificial six-symbol noncoding RNA control; no therapeutic sequence or empirical mechanism claim |

The reference source semantic fingerprint is
`07d7e859c0e6c291a1b93dc37244fdea270328e69a47d057b2c5cea9c720f9ff`;
the source Behavior fingerprint is
`c065e54650b218dfcebe4129c7012c45ca056b13aa618184ddf46eec623eff9e`.
These are useful fixture assertions, never an allowlist that replaces validation.
The generated full request/build contain source locations, including checkout
paths. Freeze corpus documents and their byte identities deliberately; do not
silently strip paths from authority or compare newly regenerated full documents
as though their byte identity were necessarily unchanged.

### Source operation inventory

| Operation | Count | Required meaning |
| --- | ---: | --- |
| `role` | 1 | Human T-cell recipient, in-vivo engineering, owned local state |
| `scope` | 1 | Environment observations for that recipient |
| `signal` / `qualitative` | 3 / 3 | Explicit Boolean `present` observations for context, reset and shutdown |
| `state` / `state.is` | 1 / 2 | Declared `prime`, `act`, `recover`; initial `prime`; exact typed state equality |
| `and` / `not` | 6 / 3 | Boolean guards preserving ordered inputs and role identity |
| `literal` / `held_for` | 1 / 1 | Positive two-second design-time duration, full uninterrupted qualification |
| `action.state_set` | 4 | Idempotent assignments with simultaneous-write conflict rules |
| `secretion` / `action.secrete` | 1 / 1 | Ongoing abstract request for the declared product; unspecified rate remains unspecified |
| `rule` | 5 | Concurrent rules, no declaration-order priority, shared pre-update state and atomic same-time settling |

The five rules are:

1. `prime AND context AND NOT reset AND NOT shutdown` assigns `act`.
2. `held_for(act, 2 seconds) AND NOT reset AND NOT shutdown` assigns `recover`.
3. `reset AND NOT shutdown` assigns `prime`.
4. `shutdown` assigns `recover`.
5. `act AND NOT reset AND NOT shutdown` requests ongoing secretion.

The full v0.2 policy document remains authority even though this fixture exercises
only a subset of its operations. Do not relabel it v0.1 or discard the unused
v0.2 policy fields to simplify the port.

### Constraint and label traps

The default request has `require_complete=false`, but its actual candidate is
complete. B1 must independently derive completeness rather than require the flag
to be true or trust the candidate's `compiled` status. Add a separate positive
variant with `require_complete=true` after establishing parity.

Material count/size limits are null. The one delivery group declares co-delivery
and same-recipient assumptions. Search limits are 256 combinations, 100,000 match
states and 256 match instances. Exact source bindings are supplied; automatic
matching is not used, but the build still contains the explicit instance record.

B1 must also support the deterministic nonnull material-limit fields:
`constraints.exact_count`, `max_count`, `max_member_bases` and `max_total_bases`,
plus each delivery group's `exact_count`, `max_count` and `max_total_bases`.
Validate their exact integer/null types and consistency, then check them against
the independently reconstructed delivered RNA identities and sequence lengths.
Count each delivered member identity once even if bindings reference it more
than once; group totals use actual placement/group membership. Do not count
components, features or supplier declarations as molecules. The original case's
null limits are not coverage of these checks.

The supplier carries activation and shutdown **declarations**, while
`constraints.control_requirements` is empty. Case B therefore does not exercise
all bounded functional-control proofs. In particular, context is an initiation
condition: losing context while the state is already `act` does not immediately
stop secretion. Do not turn the supplier's activation label into a claim that
context is a continuously necessary gate. Explicit additional control
requirements need their own implemented proofs or an unsupported result.

Empty requested functional-control requirements do not disable validation of
the supplied control declarations. Independently establish that each declared
controlling node is causal for its controlled runtime nodes, following installed
state-writer edges as well as expression dependencies. Its declared components
must be bound to the controlled nodes and include a component pinned to the
supplied executable model. Controls sharing a `(kind, domain_id)` must have the
same controlling-node authority. These are always-on correspondence checks;
they do not prove that context continuously gates secretion. Preserve the
`control_input_not_causal`, `control_material_correspondence` and
`shared_control_input_contradiction` rejection families from the existing checker.

### Required positive parameter variant

The original case B has no `parameter` nodes. Before counting binding-authority
mutation coverage, retain a separate positive case B variant that replaces its
literal dwell duration with a typed design-time `Duration` parameter. Include
both a default-bound request and an explicitly overridden request with a
correspondingly supplied independent component model. The supported pilot
operation set therefore includes `parameter` in addition to the operations in
the original fixture table. Validate parameter inventories, declared types,
defaults, frozen overrides, resolved bindings and the permitted normalized
Behavior attributes against the original request. A request-only override with
an unchanged incompatible supplier model must fail model correspondence.

Freeze literal timelines for both parameter values before executing either
engine. Only after both positive variants pass may a mutant that changes both
the candidate's reported parameter binding and its normalized node attributes
count as the frozen-binding-authority test. An unsupported `parameter` rejection
does not satisfy that test. Retained default/override request and source-correspondence
positives have PR38/39 native evidence; their reference timelines have complete PR40 validation. Architecture binding/model mutations
remain unexecuted acceptance descriptors.

## 2. Independent inputs and reconstructed outputs

The checker receives two distinct top-level inputs: the candidate build and the
full expected `PayloadArchitectureRequest`. The latter is caller authority and
contains the original BuildRequest, human target, circuit requirements, complete
supplier library and construction roots. The candidate's embedded copies are
objects to compare, not a source of expected values.

| Authority path | Must establish |
| --- | --- |
| `request.circuit.profile.source_request` | Complete original intent, resolved bindings/defaults/overrides, semantic profile, target, source constraints and provenance |
| `request.circuit.profile` | Human immune RNA target, declared recipient identity and target pins; no promotion of unestablished target claims |
| `request.circuit.requirements` | Supplementary executable behavior, exact action group, output identity/quantity/observation encoding and lifecycle |
| `request.library.refinements[*].behavior` | Independently supplied typed Behavior and complete source mapping, including operations, edges, parameters, roles and policies |
| `...components` | Model identities pin the supplied complete composite Behavior; ports, alphabet, context and declarations remain compatible |
| `...templates` | Exact root molecule, all metadata/chemistry/coordinates, output-member requirement and required feature |
| `...bindings`, `placements`, `controls`, `owned_node_ids` | Exactly one runtime owner; actual component/material/recipient associations; declaration inventories |
| `request.constraints` | Hard limits, complete delivery-group assumptions, requested completeness and any newly requested obligation |

Reconstruct the source execution manifest independently. Retain all 33 source
nodes, all five installed actions (not just the secretion output), each state
writer and its installing rule, original role inventories, complete source
lineage and the `source:complete_authority` ledger entry. The source manifest's
producer, `derive_source_execution`, must not be called by this checker.

Independently derive the selected refinement instance and deterministic material
namespaces. The current fixture yields one namespaced component, one placement
and one RNA member; matching-looking IDs are not evidence of correspondence.
Reconstruct every plan inventory and all 47 current ledger entries, with exact
assumptions and unresolved reasons. A count comparison cannot replace comparing
the complete records.

The template uses a direct root-to-output reference. The output has a new
coordinate frame and assembly origin referring back to the supplied root frame.
It retains its required `artificial_contract_region`, complete/noncoding status,
RNA alphabet, linear topology, declared end chemistry, absent cap, explicit
modification inventory and absent terminal tail. Check every base and these
relationships against the external template. An empty `steps` array does not
make the construction a hash-only check.

## 3. Internal modules and dependency order

The table spans validated internal modules, the pending construction/architecture-leaf batch and
planned acceptance modules. The checkpoint list above identifies their status;
none establishes a shipped OCaml architecture acceptance capability. Foundation
libraries `bioc_wire`, `bioc_domain`, `bioc_checker` and `bioc_service` establish
the packaging boundary; each new batch needs complete hosted validation.

| Work item | Proposed owner | Needed before it |
| --- | --- | --- |
| B1.01 Raw request/candidate schema census and retained corpus | Conformance harness | Passing foundation codec/protocol tests |
| B1.02 BuildRequest, human target and circuit record validators | `bioc_domain.Build_request`, `Build_request.Target`, `Circuit_request` | Existing intent/type/identity modules |
| B1.03 Closed Behavior operation variants, including the positive typed-parameter variant, policy/profile validator, constant/type/binding checks and lineage | `bioc_domain.Behavior` | B1.02 and exact numeric conventions |
| B1.04 Source/Behavior correspondence checker | `bioc_checker.Lowering_check` | B1.03; independent expected parameter bindings and permitted normalizations |
| B1.05 Per-role reference execution for all 42 supported operation kinds | `bioc_semantics.Reference` | B1.03; independent literal timelines |
| B1.06 Component, refinement, output, binding, placement and constraint validators | Validated `Pinned_identity`, `Component_contract`, `Diagnostic_text`, `Component`, `Architecture_deployment`; validated `Architecture_contract`; pending validation: complete refinements/templates/library/request | B1.02/B1.03 and B1.07 template leaf types |
| B1.07 Molecular schemas, coordinate/chemistry checks and direct-root reconstruction | Validated `Molecule_coordinates`, `Molecular_record`, `Molecule_chemistry`, `Molecule`, `Molecule_set`; validated transition/recoding, `Payload_structure`, `Construction`, `Construction_artifact`, required-region checker; pending validation: `Construction_check` | Strict schemas plus primitive identities; can run alongside B1.04/05 |
| B1.08 Source-manifest/ledger and architecture reconstruction | `bioc_checker.Source_check`, `Architecture_check` | B1.04/B1.06/B1.07 |
| B1.08a Optional finite-trace candidate execution | Separate `bioc_candidate_runtime` | Reconstructed candidate authority, B1.05 literal timelines; required before claiming independent candidate execution, not implied by graph correspondence |
| B1.09 Fresh acceptance and protocol exposure for the implemented capability | `bioc_checker.Acceptance`; producer-free service entry point | Every required pilot acceptance obligation and negative gate; B1.08a only if execution is claimed |
| B2.01 Producer, deterministic selection and namespacing for the same capability | Internal `bioc_compiler.Lowering` validated; architecture producer still remaining | B1 checker accepted and unchanged by producer implementation |
| B2.02 Fresh paired RNA/manifest export | Canonical artifact content + Python atomic storage adapter | B2.01 and B1.09 |

Keep stage/schema/target requirements, scoped obligations and dependency
invalidation explicit when wiring this slice into the checked pass manager.
Do not move its acceptance bookkeeping into an untyped Python convenience
wrapper. The full existing PassManager migration remains a separate cross-profile
obligation; the pilot must not claim that every public pass API is migrated.

The existing Python architecture checker establishes exact supplied composite graph
correspondence, not an independently executed biological model. Preserve that
claim. Reference execution parity is required to port the language correctly;
it does not turn exact graph correspondence into empirical evidence. If finite
trace comparison is added, candidate execution must be a separate
`bioc_candidate_runtime` with no dependency on the source reference evaluator.

## 4. Minimum honest acceptance boundary

Do not hardcode the fixture name, node IDs, hashes, counts or artificial bases as
the implementation. Define a capability in terms of supported operations,
schemas and material/contract features. Parameterize its checks over actual
identities, values, graphs and independently supplied material.

A first complete slice may support one role, explicit source correspondence,
one selected composite refinement, the listed stateful Boolean/temporal
operators plus typed design-time `parameter` binding, direct-root complete RNA
construction and the count/size, delivery and completeness constraints described
above. A structurally valid request containing any unsupported
operation, nonempty helper/channel/availability contract, execution-bearing
component operating-domain/resource requirement, requested
functional proof, construction transform or additional obligation must yield
explicit unsupported coverage and no accepted export. It cannot be made to
pass by dropping the field, substituting a default or checking only the
recognized subset.

Before implementation, make this a closed field-level capability predicate,
including the following existing obligation paths. A parsed but unsupported
record remains attached to the complete caller authority and receives an
explicit reason; it is not erased to create a supported request.

| Additional authority | B1 disposition |
| --- | --- |
| A source wrapper carrying deployment, acceptance or other obligations beyond the plain `BuildRequest` | Unresolved/unsupported `wrapped_source_obligations`; unwrapping is not discharge |
| Source implementation constraints other than the already interpreted v0.2 `execution` policy | Unresolved/unsupported `uninterpreted_implementation_constraints` |
| Nonempty source `preferences` | Unresolved/unsupported `uninterpreted_source_preferences`; preserve the original request |
| Nonempty `ExecutableCircuitBehavior.inputs` or `CircuitRequirement.input_bindings` | Unresolved/unsupported `executable_input_observation_mapping`; a valid observation record alone does not prove its source correspondence |
| Supplementary behavior provider dependencies | Unresolved/unsupported `circuit_provider_mapping`, with each provider identity retained |
| Nonempty component required dependencies without a supported provider/grounding proof | Unsupported dependency coverage or the existing ungrounded-dependency contradiction; empty `helpers` does not establish satisfaction |
| Automatic match policy or unsupported constituent connections | Unsupported capability; selected explicit-instance verification does not replay matching or invent connection semantics |
| Nonempty template transforms, complexes, experimental amounts or payload-structure obligations outside direct-root construction | Unsupported capability, including well-formed additional records |

Keep source `preferences` distinct from architecture
`constraints.preferred_refinement_ids`. The latter and the architecture search
budgets remain validated and retained ranking/search authority; B1 verifies the
selected instance and candidate, not search completeness or optimality, and
keeps `search_verified=false`. A constraint-ledger record is not independent
evidence that the producer exhausted a search or respected a ranking policy.

The target's existing unestablished host-dependency and operating-condition
descriptions are still present in case B. They are distinct from unsupported
execution-bearing component resource contracts and must remain explicitly
unestablished rather than be dropped or treated as a positive capability.

All fields present in the current fixture must still be parsed and checked:
target claims, provenance, observation contracts, unused-empty inventories,
constraint declarations and historical assessment labels are not a license to
accept arbitrary unvalidated JSON subtrees. Schema validity alone also cannot
discharge the correspondence checks above.

For a complete accepted pilot, require all of the following:

- Complete request and target/profile compatibility with no unimplemented
  requested semantic obligation.
- Exact source lowering/correspondence, requirements, lineage and source
  execution manifest, including state assignments.
- Complete supplier-model correspondence, pinned component identities and
  exactly one owner for each installed runtime operation.
- Causal and material correspondence of every supplied control declaration and
  consistent shared control domains, even when no functional proof is requested.
- Exact output product/quantity/lifecycle contracts and complete architecture
  inventories, placements, assumptions, delivery membership and constraint
  ledger.
- Fresh independent direct-root construction, required regions, chemistry,
  metadata, every emitted base and every required member.
- No stale source, contract, template or checker identity; compare the stored
  construction assessment with fresh reconstruction under its declared schema
  and the explicitly reviewed cross-implementation receipt comparison rule.
- Derive completeness independently of the producer's build-status label. Keep
  the existing rule that a `compiled` build without complete translation fails.
  A structurally valid build labeled `partial` can still receive a fresh complete
  result when every obligation is independently discharged; the Python checker
  already permits this. Do not require `status == "compiled"` as acceptance
  authority or silently tighten this behavior during migration.
- Translation and construction complete, no unresolved translation obligation,
  `search_verified=false`, empirical validation `unknown`, human admission
  `not_admitted`.

The caller may retain unsupported/partial diagnostic reports for review, but
B1 does not treat a fresh unsupported/partial checker result as complete pilot
acceptance. The producer's `partial` status alone is not such a result. Retain a
positive complete candidate with only its producer status changed to `partial`,
and require the same freshly derived completeness with its own candidate
fingerprint. Search/alternative diagnostics remain outside the receipt's
certified search scope. A stored Python assessment is never imported as an
OCaml certificate. Record fresh OCaml execution identity
and bind the new result to the exact candidate and expected authority. Any
intentional version/receipt-field change needs an explicit comparison rule;
do not remove substantive fields to force Python/OCaml byte equality.

## 5. Required conformance and mutations

Reference timelines should be literal assertions, independently specified before
running either implementation. All input frames supply context, reset and
shutdown observations; horizons are explicit.

Positive cases must demonstrate generality within the declared capability, not
only recognition of the original fixture. In addition to the original,
`require_complete=true`, typed-parameter default/override and complete candidates
with producer status `partial`, retain both of these independently specified positives:

- Alpha-rename the source and supplier node/role identities with a corresponding
  explicit mapping, and consistently rename component, template, member,
  coordinate, construction and ledger identities. Reconstruct source/Behavior
  correspondence, runtime ownership and material namespaces from those
  authorities; do not compare against the original IDs or fingerprints.
- Change the independently supplied artificial RNA root to another valid
  noncoding RNA spelling, retain its valid complete chemistry/coordinate/feature
  contract, and provide the correctly reconstructed candidate. Check against
  that separately supplied root. The original fixture's bases are neither an
  acceptance allowlist nor a source from which the new expectation is derived.

These positives add no empirical function or biological capability claim. Their
literal identities/expected results and negative counterparts must be retained
before native execution. A changed candidate with the original independent root
still fails; changing only one side of an alpha correspondence still fails.

For every supported global and delivery-group material limit, retain an
exact-boundary positive and a violated-bound negative. The original single
six-symbol member gives a count-one/length-six positive; derive these numbers
from independent retained material authority in the parameterized harness.
Count-conflict and one-below-length variants must reach the relevant material
constraint rejection. Update the request-associated candidate and historical
assessment identities consistently for these tests so a stale request hash
cannot substitute for checking the constraint. Retain contradictory
`exact_count > max_count` and Boolean-as-integer cases separately as schema
rejections, with their own intended failure signatures.

| Timeline | Literal expectation |
| --- | --- |
| Context true at initialization, reset/shutdown false | Settles to `act` at time zero; ongoing output starts in the settled frame; timer at two seconds transitions to `recover` and ends output |
| Context falls after entry into `act` | Output continues until reset, shutdown or the two-second state dwell expires; context is not an instantaneous output veto |
| Reset asserted during `act`, shutdown false | State becomes `prime` and output stops at that timestamp; a later valid re-entry starts a fresh dwell interval |
| Reset and shutdown asserted together | Shutdown rule assigns `recover`; reset rule is disabled; output stops without relying on declaration order |
| Reset asserted exactly at the dwell deadline | The new external snapshot disables the timeout guard and assigns `prime`; no obsolete timer effect overrides it |
| Horizon before pending dwell deadline | Evaluation stops explicitly; no invented post-horizon recovery frame |

Add typed-state conflict, identical-write coalescing, missing observation,
nonconvergent microstep and wrong-duration-unit cases from the existing general
semantic suite. Keep source and supplier edits separate in mutations.

| Mutation | Intended rejection/check |
| --- | --- |
| Remove one retained state assignment | `source_manifest_states` correspondence, not only parse failure |
| Change `and` to `or` and refresh candidate/model hashes | Actual model operation correspondence |
| Change timer constant, reset/shutdown guard or ordered input edge | Independent original-source/model comparison and affected literal timeline |
| Change both reported parameter binding and normalized candidate attributes after the default/override parameter variants pass | Frozen caller binding authority; unsupported `parameter` is not the intended rejection |
| Pin component to another model hash | Complete composite model authority |
| Relabel a control input as an unrelated source node | Always-on causal correspondence, including state-writer dependencies |
| Bind a control to a component not implementing its controlled nodes | Always-on control/material correspondence |
| Give controls the same kind/domain identity but conflicting input sets | Shared-control declaration contradiction, even with no requested functional proof |
| Drop/duplicate runtime ownership, a placement or a ledger entry | Coverage and inventory reconstruction |
| Change output product, quantity, encoding or lifecycle | Supplementary output authority |
| Rehash modified emitted bases or feature coordinates | Independent root/template reconstruction |
| Remove required member or alter chemistry/completeness | Complete construction and required-region checks |
| Violate a global count/member-length/total-length limit with otherwise current authority | `exact_rna_count`, `maximum_rna_count`, `maximum_rna_member_length` or `maximum_rna_total_length`, as applicable |
| Violate a delivery-group count/total-length limit with otherwise current authority | `delivery_group_exact_count`, `delivery_group_maximum_count` or `delivery_group_maximum_length`, as applicable |
| Substitute a new request/library while keeping an old build | Request authority/freshness |
| Attach unsupported helper/channel/transform/control requirements | Explicit unsupported capability; no partial acceptance |
| Forge `compiled`, PASS or admission fields | Fresh complete acceptance and fixed claim scope |
| Disable all producer modules | Valid candidate still verifies; source/template mutants still fail |

Existing tests to extend or port, retaining their intended rejection reasons:

- [test_payload_architecture.py](../tests/test_payload_architecture.py): all six
  slices, stateful supplementary roundtrip, changed product, fresh export and
  public CLI replay.
- [test_payload_architecture_verification.py](../tests/test_payload_architecture_verification.py):
  producer-disabled replay; missing state assignment; changed operator/model pin;
  wrong product quantity; stale receipt; changed bases; missing placement/ledger;
  hidden state/action ownership; same-recipient authority.
- [test_behavior_execution.py](../tests/test_behavior_execution.py): timer
  deadlines, shared prestate, atomic assignments, nonconvergence and typed values.
- [test_circuit_construction_checking.py](../tests/test_circuit_construction_checking.py)
  and [test_circuit_construction_edges.py](../tests/test_circuit_construction_edges.py):
  direct-root reconstruction and malicious coordinates/chemistry/inventories.
- [test_circuit_checker_independence.py](../tests/test_circuit_checker_independence.py),
  [test_verification_mutations.py](../tests/test_verification_mutations.py) and the
  new OCaml dependency audit: enforce actual dependency separation, not labels.
- [test_pipeline.py](../tests/test_pipeline.py): stage authority, invalidation,
  stale ancestors, changing dependencies and scoped completeness.

## 6. Pilot completion record

B1 is complete only after hosted native builds and exact-revision conformance
pass on the supported validation platforms, with full positive/negative/mutation
accounting, installed standalone replay outside the checkout, and dependency
isolation evidence. Record corpus byte hashes, request/source/model identities,
core binary/toolchain receipts and the supported capability predicate. The normal
Python product remains explicitly authoritative for unmigrated operations.

B2 additionally requires Python authoring through the OCaml producer and
independent checker to paired exact RNA/manifest output, fresh verification of
that output and failure-safe publication. Completing B1 alone does not complete
B2, Behavior v0.2 as a whole, all construction operations or system migration.
