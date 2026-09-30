# Verification independence and mutation audit

Acceptance uses frozen caller authority and separately defined response contracts
or reviewed reference records. No serialized PASS report grants fresh acceptance.
This audit distinguishes independent execution from shared schema, normalization
and provenance helpers; sharing a helper is not an additional independent check.

The current call graph has these boundaries:

| Boundary | Acceptance expectation | Shared implementation and limit |
| --- | --- | --- |
| Intent to Behavior | `verify_lowering` checks output bindings against the separately frozen `BuildRequest`, then retained operations, edges, types, sources and contact identities | The lowerer and verifier share attribute normalization, lineage and contact-binding helpers. Explicit expected bindings and semantic regression histories test those conventions; this structural pass does not independently prove their entire semantics. |
| Behavior to synthetic mechanism | `check_realization` executes `semantics.evaluator.evaluate` for requested actions and `models.synthetic.run_model` for candidate outputs, then monitors the declared response envelopes | The two runtimes share immutable types and artifact schemas, but neither invokes the other. Both are software models over supplied observations, with no biological parameter model. |
| Synthetic candidate provenance | `check_synthetic_candidate` checks request/catalog identities and invokes the independent finite-history checker | It replays `generate_synthetic` for deterministic source-map policy. That replay establishes only provenance correspondence; it does not supply expected output traces or discharge response obligations. |
| Synthetic component assembly | `check_component_assembly` checks explicit mechanism edges/input order and reruns `check_composition` | It shares the deterministic component adapter for expected records and provenance. The linker independently checks locked interfaces, domains, providers, cycles and resources; biological applicability remains conditional. |
| Components to Construct | `check_construct_request` recreates the expected reference contract from trusted reviewed pins and checks whole-CDS layout; `check_construct` compares the proposed candidate with that authority | The reference adapter is shared. Expected manifest/record fingerprints were curated independently of the assembler. The checker imports no construct generator. |
| Construct to Molecular | `check_molecular` rechecks Construct, compares every nucleotide with the selected reviewed record and translates against the separately frozen protein | Feature-status schema rules are shared with the emitter. Translation uses the reference translation implementation; the emitter only copies the selected nucleotide record. The checker imports no emitter. |
| Imported reference package | `verify_reference_package` requires an independently supplied request/build identity, reloads retained pinned evidence and reconstructs with current checkers | Archive hashes establish file integrity. Historical check records are compared with freshly reconstructed evidence, rather than promoted to acceptance. |
| Imported synthetic package | `verify_synthetic_package` requires an independent full synthetic-build request or expected build identity and reconstructs with current generation/execution/checking | Request authority binds history, horizon and profile/configuration as well as realization requirements. Regeneration is not another independent oracle; acceptance still executes separate runtimes and uses literal timeline regressions. |

The temporal generator is tested against the previously specified literal contact,
pulse and memory timelines. New literal runner expectations do not call the
Behavior evaluator. Mutants substitute inertial delay for sustained qualification
or move pulse expiry; response violations, rather than unrelated parse failures,
must identify the changed behavior. The profile's bounded dwell campaign uses 81
histories with three contact states at four variable timestamps and a declared
active/inactive suffix and horizon; this does not cover every possible history.

The runtime dependency audit in `tests/test_verification_mutations.py` checks that
the Behavior evaluator and synthetic runner have no direct execution dependency
on each other or synthesis. A separate test disables the lowerer, synthetic
generator, construct generator and nucleotide emitter after preparing the input
artifacts, then runs the base realization, construct and molecular acceptance
entry points. These tests enforce the stated boundaries; they do not claim that
all shared libraries or independently written algorithms are infallible.

The mutation campaign is an explicit inventory with positive controls and the
intended failure signature. A crash or an unrelated rejection does not count as
detection.

| Mutation | Intended check and evidence |
| --- | --- |
| Change both an output parameter value and its reported binding | `verify_lowering`: `authoritative_bindings`, against the original frozen value |
| Swap two distinct observation endpoints | `check_realization`: `input_endpoint`, before runtime coverage is reported |
| Aggregate contacts before conjoining their observations | `response_violation`: inactive response at 0.5 seconds for split objects; the correct same-object conjunction passes |
| Replace the required response with a silent output | `response_violation`: active response at 1.5 seconds, with source/requirement correspondence |
| Delay the output beyond the contractual deadline | `response_violation`: active response at 1.5 seconds, between supplied snapshots |
| Change the mechanism after obtaining a passing result | `freshness`: exactly the `mechanism` dependency becomes stale |
| Change component order and update the proposed request/candidate identities together | `check_construct`: `component_order`, from the independent supported-layout rule |
| Introduce a synonymous GCC-to-GCT nucleotide edit and recompute its hash | `check_molecular`: exact-reference comparison fails while canonical-hash and protein-translation comparisons pass |

The last row demonstrates why protein preservation cannot replace nucleotide
identity or preserve expression, structure and behavioral evidence. The reviewed
DNA, RNA and protein expectations remain separate from emitted output.

The realization checker policy is `biocompiler.realization_checker.v0.3`. M10.5
adds a fresh human admission gate and pins its policy alongside the existing
finite-history semantics. Human implementation contexts return UNSUPPORTED;
software-only model checks remain available. See [admission](human-admission-v0.1.md).
A passing
finite-history result now requires an exercised active deadline **and** an
exercised inactive deadline for every response requirement, with no incomplete
uncancelled episode. An active-only history previously passed the base public
checker; the synthetic wrapper already rejected it. The policy is now enforced
centrally for all callers, and the duplicate wrapper gate has been removed.

Coverage counts identify deadlines that were checked, not independent proof that
the response was successful. Observed violations still yield FAIL even when
other coverage is incomplete. Active-only or inactive-only histories yield
UNKNOWN, as do unfinished activation/deactivation deadlines. Missing input
observations, empty histories and histories without an initial zero-time snapshot
do not create coverage. Contact disappearance cancels that contact episode; it
does not manufacture active or inactive observations. The
`exercised_requirement_ids` property identifies requirements with both kinds of
deadline exercised; detailed incomplete and cancelled counts remain separate.

Current `CheckResult` import validation also rejects a PASS record whose inactive
coverage is zero. The artifact schema remains v0.1, but unsafe historical PASS
records cannot satisfy the stronger invariant. The checker-version/settings
dependency changes make earlier receipts stale when compared with current
inputs.

Evidence categories remain separate in the checked synthetic pipeline:

- Exact structural preservation discharges the frozen-request correspondence
  obligation.
- Model-conditional finite-history evidence discharges the exercised synthetic
  response obligation only.
- The empirical molecular-behavior obligation remains unresolved.

Changing a finite-history artifact's evidence category to exact or empirical is
rejected. Structural and sequence-reference success also establish no biological
refinement. Generated, metamorphic and bounded-exhaustive campaigns extend the
software evidence within their recorded bounds; none changes its category to
empirical evidence or a universal biological claim.
