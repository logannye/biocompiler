# Working on CellWeave

CellWeave implements Python intent authoring, immutable build/realization requests and intent/behavior graphs, authoritative lowering, checked passes, automatic combinational synthetic generation, abstract reference execution, finite-trace checking against independent synthetic models, typed component contracts, offline composition linking, single-CDS reference construct assembly and independently checked exact-reference DNA/RNA emission with reproducible offline reference packaging. Exact CDS reference fixtures are curated separately from synthetic behavior. General molecular mechanism selection, biological simulation and complete-payload generation remain unimplemented.

- Preserve the distinction between exact artifact identity, model-conditional claims, and empirical evidence. Never label an unresolved biological claim as verified.
- Python authoring will construct typed descriptions. Python control flow must not silently stand in for cellular runtime behavior.
- Carry requirement identities, target context, assumptions, and source correspondence through each compiler pass. Unsupported semantics should produce explicit diagnostics.
- Treat DNA and RNA as distinct compilation targets. Sequence optimization must recheck the higher-level properties it can affect.
- Keep the runtime dependency surface small. Introduce dependencies when a concrete implementation requires them.
- Keep generated build artifacts and scratch work out of version control. Do not add patient data, credentials, or proprietary biological libraries.
- Update the architecture and roadmap when an implementation changes their assumptions.

- Follow `docs/behavior-semantics-v0.1.md` for the executable semantic profile and `docs/toolchain-contracts.md` for downstream obligations. Behavior execution is a language reference, not a biological simulator.
- Follow `docs/realization-checking-v0.1.md` for model checks. Keep candidate execution independent from the behavior evaluator. Preserve non-vacuous coverage and all dependency identities; change tool/profile versions when their semantics change. Never broaden a finite-trace result into a universal or empirical claim.

## Native build storage

The initial implementation is Python-only. If Rust is introduced, keep editing and static work local, and run compilation, executable native tests, extension rebuilds, and packaging on hosted CI by default. Local Rust compilation, including implicit builds through package managers, requires explicit authorization for the work. Do not silently fall back to local native builds. Record the tested revision and platform and preserve required validation gates.

- Follow `docs/component-contracts-v0.1.md` and `docs/component-linking-v0.1.md` for component changes. Keep model/reference identities locked, providers and resource assumptions explicit, and sequence-only references free of dynamic claims. Component compatibility does not upgrade finite-history evidence.

- Follow `docs/construct-ir-v0.1.md` and `docs/construct-checking-v0.1.md` for assembly. Compare candidates against frozen layout authority and independent reference pins; never use output claims as expected values. Layout changes invalidate affected composition and behavior evidence. The supported reference construct remains one whole CDS with unknown delivered context; multi-molecule acceptance is unsupported; sequence emission is a separate checked exact-CDS stage.

- Follow `docs/molecular-ir-v0.1.md`, `docs/molecular-checking-v0.1.md` and `docs/exact-cds-pipeline-v0.1.md` for emission. DNA and RNA reproduce their own independently pinned records. Exact nucleotide equality, linked-reference consistency and protein translation are separate checks. Optimization is disabled. Keep unknown delivered-molecule features explicit, and recheck current authoritative inputs before export.

- Follow `docs/build-manifest-v0.1.md` and `docs/reference-build-v0.1.md` for packaging. Keep run metadata outside canonical build identity, require independent request/build authority for fresh verification, reconstruct with current checkers and publish one validated archive atomically. Imported PASS labels and self-supplied hashes never establish authority.

- Follow `docs/semantic-regression-matrix-v0.1.md`, `docs/verification-exploration-v0.1.md` and `docs/verification-independence-v0.1.md` when extending verification. State explored state/time bounds and fixed suffixes, keep UNKNOWN distinct from failure, preserve a selected failure during reduction and require both active and inactive response coverage. Bounded model checks never become empirical or universal claims.
