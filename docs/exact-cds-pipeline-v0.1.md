# Checked exact-CDS pipeline v0.1

`run_molecular_pipeline(request, registry, manifests)` extends the checked
[reference construct pipeline](reference-construct-pipeline-v0.1.md) with a real
Construct → Molecular pass. The frozen `ConstructRequest` selects an independently
pinned whole DNA or RNA coding reference. General intent compilation and complete
payload realization remain separate future profiles.

```python
import biocompiler as bc
from examples.reference_construct import reference_request

request, manifest, registry = reference_request("RNA")
manifests = {manifest.reference_set_id: manifest}
build = bc.run_molecular_pipeline(request, registry, manifests)
assert build.result.scope == "exact_cds"
assert build.check_result.passed

export = bc.export_reference_sequence(
    request, build.construct, build.candidate, registry, manifests
)
assert bc.verify_sequence_export(export, build.candidate)
```

The example helper loads retained source files with independently recorded trusted
fingerprints. Applications supply their own reviewed `ConstructRequest`, registry
and manifest snapshots; expectations must never be derived from the emitted
candidate. Run `PYTHONPATH=src python examples/reference_sequences.py` for both
supported modalities and their distinct canonical sequence and file identities.

## Acceptance and remaining obligations

The pipeline admits the authoritative components, generates and checks Construct
IR, emits the selected reference spelling and runs an independent molecular
checker. The emitter cannot provide its own acceptance receipt. The pass checks
source/requirement correspondence, rejects unestablished observation mappings and
rechecks composition and layout after encoding. It preserves the original target,
reference authority and upstream request identity.

`MolecularBuild` returns the accepted construct, molecular candidate, molecular
check, scoped pipeline result and pass manager. Completion of `exact_cds` requires
current reference authority, component linkage, construct layout and emitted
sequence identity. `complete_payload_features` and `molecular_behavior` remain
unresolved. Completion establishes no cap, nucleotide chemistry, complete
transcript boundaries, delivery topology, expression or therapeutic performance.

DNA-CDS copies the separately pinned DNA record and RNA-CDS copies the separately
pinned RNA record. The independent checker compares nucleotide identity,
translation to the linked protein and T/U consistency separately. A synonymous
change can preserve protein translation while failing exact-reference acceptance.
Optimization remains disabled. See [Molecular IR](molecular-ir-v0.1.md) and
[independent checking](molecular-checking-v0.1.md) for fields and diagnostics.

The pass manager tracks all upstream roots plus emitter/checker/profile, encoding
policy and pipeline versions. Callers must update changed roots before reusing
`manager.result("molecular", scope="exact_cds")`; its original `build.result` is a
historical snapshot. Changing a dependency invalidates downstream reuse. A change
to an emitter, checker or molecular policy requires a new pipeline with the
corresponding providers; rerunning an old closure cannot claim that new identity. Supplied
manifests are frozen once for the complete run. They do not watch files: reload
retained sources with the trusted loader before reuse when local files change.
Imported JSON and CLI inspection also provide historical content, not acceptance.

## Deterministic file exports

`export_reference_sequence` runs a fresh independent check against current inputs,
then returns immutable FASTA and structured molecular JSON in `SequenceExport`.
It never trusts an imported PASS label. `verify_sequence_export` parses those
encodings and verifies their fidelity to the supplied artifact; by itself it does
not establish reference acceptance.

The FASTA header uses a percent-encoded reference ID, alphabet, CDS-only scope,
and fixed `use=software_test human_admission=not_admitted` labels. M10.5 export
policy v0.2 requires current [use admission](human-admission-v0.1.md) before the
independent molecular check. Molecular JSON uses schema v0.2 with equivalent fixed
labels. Rebuild affected exports from independent authority; sequence-content
hashes remain unchanged.
It excludes local paths and caller-selected molecule names. Nucleotides are exact
uppercase symbols with LF newlines, a declared line width (80 by default) and one
terminal newline. No whitespace or alphabet repair occurs during verification.
JSON uses sorted keys, two-space indentation, UTF-8 and one terminal newline; it
preserves the full artifact, including source provenance. Write `fasta_bytes` and
`specification_bytes` in binary mode to preserve these bytes across platforms.

`sequence_sha256` hashes only canonical nucleotide symbols. `fasta_sha256` and
`specification_sha256` hash their complete file bytes. Changing FASTA wrapping
changes the file hash while preserving the sequence hash. Artifact identity also
includes lineage, scope and features; absolute source provenance may affect that
identity. The separate [reference-build profile](reference-build-v0.1.md) now provides portable
build identity, a complete reference manifest and atomic single-archive publication.
It requires logical core source paths and stores host paths in separate run metadata.
These lower-level export functions continue to produce content in memory.
