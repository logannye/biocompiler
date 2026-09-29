# Molecular implementation correspondence v0.1

M9 introduces an explicit, independently checked request connecting frozen
Behavior inputs and responses to selected exact-CDS components. The implemented
profile is `cellweave.molecular_correspondence.v0.1`. It establishes requested
correspondence and exact artifact linkage; it supplies no calibrated biological
adapter or molecular execution semantics. A valid request therefore has
`linkage_outcome: pass` and molecular behavior `outcome: unknown`.

## Authority and immutable records

`MolecularImplementationContract.freeze(...)` binds independently supplied
`RealizationRequest`, `ConstructRequest` and `MolecularArtifact` identities. It
also records selected component locks, the exact target and operating domain,
requested observation bindings, assumptions, parameter declarations, evidence
citations, a model-profile name and an optional pinned adapter proposal.

`MolecularInputBinding` names a source signal and observation field, an exact
`Observable`, and a selected component instance. `MolecularResponseBinding`
names the response requirement, rule, action specification, exact observable and
selected instance. These are **requested measurements**, not newly established
ports or guarantees on a sequence-only component. Optional adapter port names
require an explicit pinned model identity. Naming that identity does not load or
validate a provider.

All operating-domain observations must be mapped exactly once. The domain must
itself cover all live runtime observations of the selected role. Every installed
ongoing output of that role needs a response requirement and corresponding
mapping. Role, contact scope, endpoint identity, compartment, type, source IDs,
component selection and target capability declarations are checked explicitly.
An omitted response cannot disappear by deleting both its mapping and contract
entry. Instantaneous outputs and quantitative secretion laws require additional
response semantics and receive `unsupported` diagnostics.

Parameter records separate `unestablished`, `assumed`, `fitted` and `measured`
declarations. Values use explicit scalar types and units; optional uncertainty
is a compatible closed interval containing the declared value. Nonempty values
need a pinned source and a method. An unestablished parameter has no value,
uncertainty or fabricated provenance. Fitting and measurement labels are caller
declarations, not independently validated calibration results.

`MolecularEvidence` records a pinned source, exact target-context identity,
claim text, category and material relationship. Categories distinguish sequence
identity, material identity, parameter fitting, model validation, uncertainty
and therapeutic outcomes. Relationships distinguish an associated reference,
asserted exact material and an unestablished relationship. All cited claims
remain unvalidated by this profile, including a caller-supplied
`exact_material` or `model_validation` label. A hash binds cited content; it does
not establish the truth or applicability of a citation.

The profile requires explicit unestablished claims for observation mapping,
context applicability, parameter calibration, model validation, uncertainty,
therapeutic outcomes, exact experimental-material identity and auxiliary
coding/processing context. These cannot be deleted to obtain acceptance.

## Independent admission

Call:

```python
result = check_molecular_implementation(
    contract,
    realization_request,
    construct_request,
    construct,
    molecular,
    registry,
    manifests,
)
```

The checker reruns authoritative `BuildRequest` → Behavior preservation and the
independent molecular checker. The latter rechecks construct assembly, component
linking and exact nucleotide/protein reference obligations. It compares contract
pins against the separately supplied current inputs, not a candidate's claimed
PASS label. A sequence mutation remains a failure even when the candidate and
contract are updated with its new hash.

`linkage_outcome` describes only this exact correspondence check. The main
`outcome` describes the unresolved molecular claim:

| Condition | Linkage | Molecular behavior |
| --- | --- | --- |
| Valid requested correspondence and exact current CDS | `pass` | `unknown` |
| Changed authority, sequence, source mapping or target | `fail` | `fail` |
| Omitted ongoing output or unsupported output semantics | `unsupported` | `unsupported` |
| Proposed model profile or adapter without a provider | May pass | `unsupported` |
| Citation asserts validation or therapeutic success | May pass | `unknown` |

There is no molecular-behavior PASS in this implementation.
`MolecularBehaviorResult.passed` remains false. No compiler completion profile is
promoted, and neither the existing `exact_cds` completion scope nor reference
packaging acquires biological claims. Synthetic gate/delay fixtures are not
calibrated biological adapters; assigning their identity to a CAR cannot make a
request executable.

## Serialization and freshness

All new records have strict versioned JSON. Imports reject unknown fields,
unknown schema versions, malformed optional records, duplicate bindings,
inconsistent result outcomes, omitted dependency keys, unsupported checker
versions and invalid UTF-8 strings. Parameter uncertainty and all nested typed
records are checked on import. Importing a result is historical inspection only.

Results bind the contract, realization request and archival source artifact,
BuildRequest, Behavior, target, domain, construct request, construct, molecular
candidate, registry, reference manifests, downstream checker inputs and checker
version. Changing parameters, provenance, assumptions, cited evidence, adapter
identity or model profile changes the contract dependency. Changes to references,
layout, encoding or downstream policies change the appropriate exact
identities. `result.freshness(...)` compares the complete current inventory; a
fresh comparison is not a new acceptance receipt. Rerun the checker before reuse.

The admission checker shares the existing structural live-observation inventory
helper with finite-trace verification. It does not invoke the synthetic model
runner, reference Behavior evaluator, synthesis or sequence emitter. The
independent exact-CDS checker remains the sequence authority.

## Evidence limits and next profiles

The FAP reference's established sequence facts remain distinct from the
experimental payload and its effects. Any auxiliary coding sequence, processing
context or actual delivered-molecule boundary must be reconciled from evidence
before it supports a material or behavioral claim. This milestone does not
supply missing bases, join CDS records by analogy, or promote the reference to a
complete payload. See [reference promotion gates](reference-benchmarks.md#extending-to-a-complete-payload)
and [exact-CDS checking](molecular-checking-v0.1.md).

A future adapter requires its own versioned semantics, concrete applicability
context, independently pinned implementation and evidence, parameter fitting and
validation boundaries, uncertainty characterization, observation mapping, and
positive and adversarial checks against authored response obligations.
Quantitative tracking, continuous dynamics, population uncertainty, spatial
behavior and feedback require separate semantic/model profiles. Merely naming a
new profile produces `unsupported`; the broad authoring API does not imply its
molecular compilation is available. Full-payload promotion and any optimization
or SBOL/SBML integration retain their separate gates.

## Regression evidence

`tests/test_molecular_behavior.py` checks DNA/RNA positive exact linkage with
biological UNKNOWN, independent checker invocation without generation,
authoritative pin mutation, sequence mutation with self-updated hashes,
endpoint/source/scope/component identity, full input/output coverage,
unimplemented adapters/profiles, cited validation and material labels, typed
parameters, evidence/provenance freshness and strict historical imports.
`tests/test_m9_admission_audit.py` independently exercises evidence-label
promotion, adapter proposals, units/source IDs and forged result promotion.
