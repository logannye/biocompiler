# Examples

[human_acceptance.py](human_acceptance.py) combines required secretion and prohibited
observations in one request. Run `PYTHONPATH=src python examples/human_acceptance.py --output generated/acceptance`
for artificial pass/fail/unknown/unsupported cases covering healthy-context activity,
peak and duration limits, cell input loss and shutdown. It asserts no biological
bounds, sensor or supported actuator. See the [acceptance contract](../docs/human-acceptance-contract-v0.1.md).

[human_deployment.py](human_deployment.py) freezes delivery requirements around
the human behavior request. It demonstrates unknown, compatible, conflicting and
unsupported co-payload declarations with artificial values. Run
`PYTHONPATH=src python examples/human_deployment.py --output generated/deployment`.
The example retains its platform fixture bytes and all request/assessment pairs;
it chooses no delivery system or therapeutic regimen. See the
[deployment contract](../docs/deployment-contract-v0.1.md).

[human_behavior.py](human_behavior.py) defines reversible conditional secretion
for one human-targeted role. It preserves the source goal and predicate, records
measurement units and access, and checks artificial traces with pass/fail/unknown
outcomes. Run `PYTHONPATH=src python examples/human_behavior.py --output generated/human-behavior`.
All numerical values are software fixtures, not supported biological requirements.
See the [bounded observation contract](../docs/human-behavior-contract-v0.1.md).

[human_target.py](human_target.py) records an illustrative human in-vivo target
with mandatory applicability fields and explicit missing evidence. Run
`PYTHONPATH=src python examples/human_target.py --output generated/human-target`,
then inspect the resulting `human-target.json`. No biological profile, delivery
system or therapeutic payload is admitted. See the
[human target contract](../docs/human-target-contract-v0.1.md).

[intent_programs.py](intent_programs.py) builds six complete programs: contextual
clearance, priming and phases, temporal response, graded secretion, feedback
regulation, and cooperation between cell roles. Each function returns an immutable
`IntentProgram` for inspection or serialization.

From the repository root, with Python 3.11 or later:

```sh
PYTHONPATH=src python examples/intent_programs.py
```

All biological names and parameters are symbolic. These examples construct intent
graphs; they do not choose molecular mechanisms or generate therapeutic sequences.
See the [v0.1 API reference](../docs/intent-api-v0.1.md) for the vocabulary and its
meaning.

[behavior_trace.py](behavior_trace.py) lowers a generic authored program and evaluates its abstract output requests against contacted-object histories. Internal timers execute between input snapshots. Run `PYTHONPATH=src python examples/behavior_trace.py`; no molecular model is involved.

[realization_check.py](realization_check.py) binds an explicit output contract to the behavior and automatically generates a combinational candidate and checks it with an independent runner. It demonstrates passing behavior, silent and late counterexamples, and stale evidence after a model change. Run `PYTHONPATH=src python examples/realization_check.py`. This fixture tests the checker; it provides no biological evidence or sequences.

[checked_pipeline.py](checked_pipeline.py) freezes build authority, runs two checked passes, checks a generated candidate and demonstrates automatic transitive invalidation. Run `PYTHONPATH=src python examples/checked_pipeline.py`. Its completion scope is a synthetic finite history; molecular obligations remain unresolved.

[temporal_pipeline.py](temporal_pipeline.py) generates sustained qualification,
cell/contact pulses and bounded resettable memory under an explicit temporal
profile. Run `PYTHONPATH=src python examples/temporal_pipeline.py`. Internal
timers execute between snapshots, and the independent checker preserves
contact episodes, trigger scope and exact deadline precedence.

[synthetic_build.py](synthetic_build.py) freezes the temporal request, input
history, horizon and generator configuration, builds a portable software-model
archive and reconstructs it against independent authority. Run
`PYTHONPATH=src python examples/synthetic_build.py --output generated/synthetic`.
See the [synthetic build/verify CLI](../docs/synthetic-build-v0.1.md).

[synthetic_design.py](synthetic_design.py) runs the integrated offline design loop:
author an operator constraint, select a passing alternate graph, reconstruct a
temporal component package and check 100 mixed cell/contact histories. Run
`PYTHONPATH=src python examples/synthetic_design.py --output generated/design`.
The retained request, selected implementation, package and campaign can be
rechecked with installed `synthetic-select`, `synthetic-build`, `synthetic-verify`,
`synthetic-explore` and `synthetic-replay` commands.

[synthetic_selection.py](synthetic_selection.py) demonstrates native versus
De Morgan conjunction, a constraint forcing the alternate implementation and
bounded search exhaustion. Gate counts are software costs, not molecular costs.

[synthetic_verification.py](synthetic_verification.py) retains passing checks,
bounded mixed-input exploration and a wrong-reset diagnostic failure reduced from
five to three frames. Run `PYTHONPATH=src python examples/synthetic_verification.py --output generated/verification`.
All records include complete independent operation requests for fresh replay;
failed and unknown reports remain separate from accepted packages.

[component_linking.py](component_linking.py) extends the synthetic pipeline to locked component contracts and separately inspects a pinned FAP RNA-CDS reference. Run `PYTHONPATH=src python examples/component_linking.py`. It preserves finite-history evidence and CDS-only scope; no molecular sequence is emitted.

[reference_construct.py](reference_construct.py) independently selects DNA and RNA CDS records and runs checked single-component construct assembly for each. Run `PYTHONPATH=src python examples/reference_construct.py`. The complete reference layout retains unknown payload context and unresolved emission/biological obligations.

[reference_sequences.py](reference_sequences.py) runs the exact-CDS pipeline separately for DNA and RNA, prints scoped identities and checks FASTA/JSON exports. Run `PYTHONPATH=src python examples/reference_sequences.py`. It emits each selected reference spelling without optimization or complete-payload/biological claims.

[molecular_design.py](molecular_design.py) freezes four artificial RNA fragments,
assembles and independently checks a complete 17-base structural specification,
packages its provenance/chemistry/handoff, and reconstructs it offline. It also
builds an explicitly authorized synonymous alternative and retains rejection of
that same edit under the original authority. Run
`PYTHONPATH=src python examples/molecular_design.py --output generated/molecular-design`.
Use installed `molecular-design-build`, `molecular-design-inspect` and
`molecular-design-verify` to repeat the [workflow](../docs/molecular-design-v0.1.md).
Region names are annotations of nonfunctional test fragments. No upstream
behavioral implementation, biological reference or human admission is claimed.

- `reference_build.py`: build DNA/RNA `.bcb` packages, publish atomically and independently reconstruct offline. See [reference builds](../docs/reference-build-v0.1.md).

- `verification_campaign.py`: bounded exhaustive presence-aware contact histories, seeded adversarial cases and failure-preserving deletion reduction; optional JSON evidence output. These are software-model checks, not universal or empirical claims.

- [molecular_contract.py](molecular_contract.py): bind a requested FAP contact response to the selected CDS, independently recheck its correspondence and retain biological UNKNOWN. The illustrative response bands/deadlines are design obligations, not calibrated measurements. General complete-payload compilation remains unavailable. Use `--output DIRECTORY` to save the contract, authoritative realization request and result.

- [payload_readiness.py](payload_readiness.py): exercise structural RNA/DNA molecule profiles with explicitly artificial software fixtures, independent retained source/review bytes and sequence mutations. A structural PASS grants neither biological reference promotion nor compiler admission. Use `--output DIRECTORY` to retain inspectable evidence.

- [human_admission.py](human_admission.py): show a finite supplied-observation PASS beside rejected human implementation admission, preserve software-only reference selection and save immutable admission requests/assessments. Use `--output DIRECTORY` for CLI inspection. See [M10.5](../docs/human-admission-v0.1.md).

- [human_profile_cases.py](human_profile_cases.py): ten M10.6 requests spanning positive, negative, conflicting, underspecified and unsupported cases; separate admission/compilation status, bounded artificial-trace search and a conditional rate-constraint contradiction. Use `--output DIRECTORY` to save evidence and `--verify DIRECTORY` to recompute it against current example authority. See [proposed profile and completion scope](../docs/human-profile-v0.1.md).
