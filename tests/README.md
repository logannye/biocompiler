# Test boundaries

M10.3 tests preserve delivery/recognition separation, target and recipient
identity, modality, physical compartments and evidence references. Deployment
window checks use the latest onset and earliest expression loss, retain unknown
bounds and reject unsupported co-payload dependencies. A compatibility pass
remains a declaration check with biological applicability unestablished and
human mechanism selection blocked. See the
[deployment profile](../docs/deployment-contract-v0.1.md).

M10.2 tests cover source-preserving goal/predicate refinement, exact product and
endpoint identity, cell versus evaluator access, units, evidence references and
strict request imports. The secretion trace tests independently specify expected
outcomes at activation/recovery deadlines, initialization, persistence violations,
cancelled triggers, retriggering and the finite horizon. Silent outputs fail when
activation is required; unexercised or out-of-domain traces remain unknown. The
[profile](../docs/human-behavior-contract-v0.1.md) checks supplied piecewise-constant
observations, not a molecular model or a therapeutic outcome.

M10.1 tests preserve legacy target identities while checking required human
applicability declarations, species/engineering constraints, evidence categories,
immutable inventories, compartments, nested request identity and strict imports.
Citations and software fixtures leave biological applicability unresolved in the
planner and CLI. These checks implement the
[target contract](../docs/human-target-contract-v0.1.md), not biological admission.

M9 correspondence tests rerun source/CDS acceptance and distinguish exact linkage from biological UNKNOWN. Independent admission mutations cover forged calibration/material labels, named adapters, endpoint units, omitted outputs and stale evidence. Payload tests use explicitly artificial source/review records to exercise complete-molecule boundaries, exact sequence/translation, topology, end chemistry and authority tampering; structural PASS cannot promote a real reference or admit a complete-payload compiler build. Planning tests retain specific unsupported extension obligations. See [molecular contracts](../docs/molecular-behavior-v0.1.md), [payload readiness](../docs/payload-profiles-v0.1.md) and [M9 evidence](../docs/m9-evidence-review.md).

The standard-library `unittest` suite exercises the authoring API and its serialized
intent graph, checked lowering, and abstract execution histories. Run from the repository root with Python 3.11 or later:

```sh
PYTHONPATH=src python -m unittest discover -s tests -v
```

Tests cover complete programs, role and target associations, temporal and state
semantics, quantitative typing, communication, inert actions, declaration conflicts,
immutable snapshots, deterministic serialization, and the explicit boundary between
an intent plan and sequence generation.

These tests validate the software representation of authored intent. They do not
validate molecular realization, biological behavior, or clinical performance. Exact-reference DNA/RNA backends are exercised separately from general
molecular realization, which remains unsupported.

Behavior tests exercise identity-preserving contact binding, exact temporal boundaries, concurrent updates, memory and repeated triggers, serialization and source correspondence. Malformed IR, unsupported lowering and incomplete histories must fail explicitly.

Realization tests independently execute synthetic candidates, exercise active and inactive output contracts, and reject silent, late, wrongly scoped or incorrectly mapped candidates. Coverage tests distinguish unexercised or unfinished responses from success. Artifact and freshness tests check strict serialization, immutability, context/parameter changes, and dependency completeness. Synthetic signal-graph correctness does not validate molecular performance.

Build-request tests cover coordinated binding tampering, strict round trips, input immutability and two-phase identities. Pipeline tests cover provider contracts, source/observation maps, scoped completeness and transitive invalidation. Reference tests compare independently frozen sequence records with retained sources and mutation failures. Generation tests include 256 bounded two-object Boolean transitions; this does not assert universal or empirical correctness.

Component tests exercise typed/semantic interface mismatches, directional domain inclusion, initialization, missing and ambiguous providers, circular dependencies, shared resource capacities and lifecycle reuse, exact registry/model/reference locks, deterministic hard-constraint selection, reference-only classification, graph tampering and transitive pipeline invalidation. Provider and capacity declarations are test assumptions, not biological measurements.

Construct tests reject changed membership, swapped versions/references, reversed orientation, frame errors, off-by-one coverage, invented features, unsupported junctions/multi-molecule assembly and weakened unknown-feature metadata. They mutate authority and candidate together to ensure matching producer claims cannot establish their own validity. Admission and pipeline tests cover forged fingerprints/receipts, source maps, complete-scope limits, dependency changes and layout evidence invalidation.

Molecular tests compare independent DNA/RNA/protein expectations, distinguish synonymous nucleotide mismatch from protein consistency, and reject missense edits, truncation, wrong alphabets, frame/termination errors, invented features and stale locks. Export checks distinguish canonical sequence hashes from wrapped FASTA/JSON file hashes and reject corrupted or mismatched content. Scoped pipeline tests retain unresolved full-payload and empirical obligations.

M7 tests cover portable request/manifest schemas, canonical ZIP inventory and hashes, safe import bounds, independent offline reconstruction, forged evidence, dependency freshness, relocated/repeated-run determinism, run-metadata separation and atomic failure preservation. These checks establish exact CDS packaging, not molecular biological refinement.

M8 adds a cross-operator semantic matrix and metamorphic tests with explicit preconditions, deterministic adversarial histories, bounded exhaustive exploration with recorded state/time bounds, failure-preserving deletion reduction and an auditable mutation/independence matrix. The shared finite-trace checker requires active and inactive deadlines for every passing requirement. See [verification exploration](../docs/verification-exploration-v0.1.md), [semantic matrix](../docs/semantic-regression-matrix-v0.1.md) and [independence audit](../docs/verification-independence-v0.1.md).
