# Case B: checker-led OCaml migration slice

Prepared 2026-10-01 from checkout `6156ed2841fd3308df833f1afe0e3f6af5d12bf6`
and the uncommitted language-foundation work. This is the dependency and acceptance
map for roadmap batch B1, followed by the same slice's producer in B2. It records
implementation preparation, not completed OCaml architecture validation.

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

The supplier carries activation and shutdown **declarations**, while
`constraints.control_requirements` is empty. Case B therefore does not exercise
all bounded functional-control proofs. In particular, context is an initiation
condition: losing context while the state is already `act` does not immediately
stop secretion. Do not turn the supplier's activation label into a claim that
context is a continuously necessary gate. Explicit additional control
requirements need their own implemented proofs or an unsupported result.

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

The following modules are proposed implementation targets, not current shipped
capabilities. Foundation libraries `bioc_wire`, `bioc_domain`, `bioc_checker` and
`bioc_service` already establish the packaging boundary; native conformance is a
separate required gate.

| Work item | Proposed owner | Needed before it |
| --- | --- | --- |
| B1.01 Raw request/candidate schema census and retained corpus | Conformance harness | Passing foundation codec/protocol tests |
| B1.02 BuildRequest, human target and circuit record validators | `bioc_domain.Build_request`, `Target`, `Circuit` | Existing intent/type/identity modules |
| B1.03 Closed Behavior operation variants, policy/profile validator, constant/type checks and lineage | `bioc_domain.Behavior`, `Behavior_policy` | B1.02 and exact numeric conventions |
| B1.04 Source/Behavior correspondence checker | `bioc_checker.Lowering_check` | B1.03; independent expected parameter bindings and permitted normalizations |
| B1.05 Reference execution for the complete supported pilot operation set | `bioc_semantics.Reference` | B1.03; independent literal timelines |
| B1.06 Component, refinement, output, binding, placement and constraint validators | `bioc_domain.Architecture`, `Component` | B1.02/B1.03 |
| B1.07 Molecular schemas, coordinate/chemistry checks and direct-root reconstruction | `bioc_domain.Molecule`, `Construction`; `bioc_checker.Construction_check` | Strict schemas plus primitive identities; can run alongside B1.04/05 |
| B1.08 Source-manifest/ledger and architecture reconstruction | `bioc_checker.Source_check`, `Architecture_check` | B1.04/B1.06/B1.07 |
| B1.09 Fresh acceptance and protocol exposure for the implemented capability | `bioc_checker.Acceptance`; producer-free service entry point | Every preceding pilot acceptance obligation and negative gate |
| B2.01 Producer, deterministic selection and namespacing for the same capability | Separate `bioc_compiler` modules | B1 checker accepted and unchanged by producer implementation |
| B2.02 Fresh paired RNA/manifest export | Canonical artifact content + Python atomic storage adapter | B2.01 and B1.09 |

Keep stage/schema/target requirements, scoped obligations and dependency
invalidation explicit when wiring this slice into the checked pass manager.
Do not move its acceptance bookkeeping into an untyped Python convenience
wrapper. The full existing PassManager migration remains a separate cross-profile
obligation; the pilot must not claim that every public pass API is migrated.

The architecture checker currently establishes exact supplied composite graph
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
operators, direct-root complete RNA construction and the specific supported
constraint fields. A structurally valid request containing any unsupported
operation, nonempty helper/channel/availability contract, execution-bearing
component operating-domain/resource requirement, requested
functional proof, construction transform or additional obligation must yield
explicit unsupported coverage and no accepted export. It cannot be made to
pass by dropping the field, substituting a default or checking only the
recognized subset.

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
- Exact output product/quantity/lifecycle contracts and complete architecture
  inventories, placements, assumptions, delivery membership and constraint
  ledger.
- Fresh independent direct-root construction, required regions, chemistry,
  metadata, every emitted base and every required member.
- No stale source, contract, template or checker identity; candidate status and
  stored construction assessment must agree with newly established results.
- Translation and construction complete, no unresolved translation obligation,
  `search_verified=false`, empirical validation `unknown`, human admission
  `not_admitted`.

The caller may retain unsupported/partial diagnostic reports for review, but
B1 does not treat them as complete pilot acceptance. A stored Python assessment
is never imported as an OCaml certificate. Record fresh OCaml execution identity
and bind the new result to the exact candidate and expected authority. Any
intentional version/receipt-field change needs an explicit comparison rule;
do not remove substantive fields to force Python/OCaml byte equality.

## 5. Required conformance and mutations

Reference timelines should be literal assertions, independently specified before
running either implementation. All input frames supply context, reset and
shutdown observations; horizons are explicit.

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
| Change both reported output parameter and candidate binding | Frozen caller binding authority |
| Pin component to another model hash | Complete composite model authority |
| Drop/duplicate runtime ownership, a placement or a ledger entry | Coverage and inventory reconstruction |
| Change output product, quantity, encoding or lifecycle | Supplementary output authority |
| Rehash modified emitted bases or feature coordinates | Independent root/template reconstruction |
| Remove required member or alter chemistry/completeness | Complete construction and required-region checks |
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
