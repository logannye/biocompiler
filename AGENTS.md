# Working on CellWeave

CellWeave implements Python intent authoring, immutable build/realization requests and intent/behavior graphs, authoritative lowering, checked passes, automatic combinational synthetic generation, abstract reference execution, and finite-trace checking against independent synthetic models. Exact CDS reference fixtures are curated separately from synthetic behavior. Molecular lowering, biological simulation, and sequence generation remain unimplemented.

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
