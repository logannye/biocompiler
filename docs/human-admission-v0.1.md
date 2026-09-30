# Human-profile admission v0.1

M10.5 makes use eligibility a fresh compiler gate. The current policy admits
**zero human therapeutic profiles**. It keeps existing reference reproduction and
synthetic execution available as explicitly labeled software workflows. A passing
observation, composition, sequence or structural check cannot authorize a human
payload. General intent-to-sequence `compile()` remains unavailable.

This implements the admission machinery. A supported biological profile still
requires the M11 evidence audit and subsequent mechanism, delivery, molecule and
independent validation work in the roadmap.

## Authority and decisions

`AdmissionRequest` freezes a complete target, intended use, gate boundary and
component records. `intended_use` is `software_test` or `human_therapeutic`;
`boundary` is `planning`, `selection`, `verification` or `export`. Components
are sorted by ID/version. Repeated identical records are coalesced because a
composition can instantiate one component several times; conflicting records
with the same ID/version are rejected.

`assess_admission(request)` returns an immutable `AdmissionAssessment` containing
request/target fingerprints, component fingerprints, the declared evidence
inventory, decision, reasons and the policy version. The current outcomes are:

| Target and requested use | Decision | Meaning |
| --- | --- | --- |
| Generic `TargetContext`, software use | `software_only` | Eligibility for a scoped software workflow; its other checks still apply. |
| Generic target, human use | `not_admitted` | Missing human target authority and unavailable supported profile. |
| `HumanTargetContext`, human use | `not_admitted` | Declared context is retained; independent applicability and implementation admission are unavailable. |
| Human target, software use | `not_admitted` | A human implementation request cannot bypass admission through a software label. |

The legacy target wire representation is unchanged. Workflow gates derive use
from its strictly parsed type: generic contexts can enter software workflows;
human contexts require human admission. Context names and capability strings
cannot grant human admission. This is a contract and artifact-claim boundary,
not a claim that software can infer a caller's unstated real-world intent.

Every assessment fixes `human_therapeutic_admission=not_admitted`,
`evidence_status=declared_not_independently_validated`, and a claim scope limited
to use eligibility. Strict import rejects missing fields, extra fields, unknown
versions and attempted promotion. `is_current()` compares request identity only.
`verify_admission()` recomputes the policy from current independent authority and
compares the entire result. An imported assessment is historical data, not a
permission token, even when its request fingerprint matches.

## Enforcement boundaries

| Boundary | Enforcement |
| --- | --- |
| Planning | Plans contain an admission assessment. Human plans and compilation diagnostics retain unavailable-profile and missing-evidence reasons. |
| Registry selection | Each candidate is checked before ranking; preferences cannot override non-admission. Human results are `unsupported`, including an empty registry. |
| Fresh verification | The component linker checks current target and resolved records even when callers bypass selection and supply exact locks. Construct and molecular checks rerun it. Direct synthetic generation and realization checking also reject human implementation requests. |
| Export | Sequence export, reference package construction, fresh archive reconstruction and atomic publication require current software-use eligibility. Gates run before emission/export or archive reconstruction can accept human authority. |

Unsupported human selection means the implementation profile is unavailable;
it is not a proof of biological infeasibility or an exhaustive mechanism search.
Existing software selection retains failed-constraint versus unknown-domain
outcomes. Later stages retain independently discovered structural failures too.

An M10.2–M10.4 checker may still return PASS for finite, supplied human-contract
observations. These checkers evaluate declarations and traces without selecting
or admitting an implementation. Their biological and actuator obligations stay
unresolved. The admission example demonstrates both results together.

## Evidence categories remain distinct

The full `TargetEvidence` records survive unchanged in the assessment, including
source pins, taxon IDs, locators, source contexts and limitations. The policy
keeps `nonhuman_in_vivo`, `nonhuman_cells`, `human_cell_line`,
`primary_human_cells`, `human_in_vivo`, `cell_free` and `software_fixture`
distinct. Human categories require taxon 9606; nonhuman categories require a
different organism; cell-free/software categories do not imply a recipient.

No category label constitutes independent evidence review. In particular,
human cell-line data cannot establish primary-cell or in-vivo applicability,
primary-cell data cannot establish an in-vivo deployment context, and a record
labeled human-in-vivo does not establish therapeutic implementation admission.
Reclassification, changed source context, limitations, taxon or pins changes
the authority identity and invalidates its earlier assessment.

The bundled murine FAP CDS is explicitly rejected as a human implementation.
Synthetic models remain software fixtures. A generic `modeled_component` is
also unavailable for human use without an independently admitted profile.
Renaming records, changing their classification or removing a familiar ID
cannot bypass the global unavailable-profile decision.

Recipient species, experimental system and the biological origin of an encoded
element are separate facts. This policy does not invent a rule that every
sequence element must originate in humans. Future profiles need contextual
evidence about the complete proposed implementation, including its recipient,
cell state, exposure, delivery and limitations.

## Artifacts, freshness and migration

Release `0.1.0.dev12` adds fixed `intended_use=software_test` and
`human_therapeutic_admission=not_admitted` fields to molecular artifacts,
synthetic candidates, reference manifests and package summaries. FASTA headers
include `use=software_test human_admission=not_admitted`. These fields participate
in artifact/file identity. Sequence-content hashes and independently retained
DNA, RNA and protein reference pins are unchanged.

The registry, selection result, composition result, construct result, molecular
result/artifact, synthetic candidate, build manifest and reference summary use
v0.2 schemas; plans use v0.3. Changed checkers, generation/export policies and
reference-build tools have revised versions. Admission policy identity is
included in fresh verification dependencies, pass-manager dependencies and the
package toolchain. Old policy identities invalidate affected results.

Pre-M10.5 artifacts are not relabeled into current authority. Recreate software
artifacts from independently retained requests and references with current
tools. Old schemas/policy receipts are rejected where their contracts changed;
an old PASS cannot authorize export. Inspection alone remains historical.

```sh
PYTHONPATH=src python3 examples/human_admission.py --output generated/admission
PYTHONPATH=src python3 -m biocompiler inspect generated/admission/human-assessment.json
```

`tests/test_human_admission.py` covers all gates, declared-evidence category
retention, reidentified records, matching forged request/candidate hashes,
rehashed archives with saved PASS evidence, atomic-output preservation and
software-use labels. It does not supply biological validation.
