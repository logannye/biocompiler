"""Emit and independently check separate exact DNA-CDS and RNA-CDS references.

Run: PYTHONPATH=src python examples/reference_sequences.py
The example prints identities and scope, without dumping nucleotide sequences.
"""

from cellweave.artifacts.sequences import (
    export_reference_sequence,
    verify_sequence_export,
)
from cellweave.compiler.molecular import run_molecular_pipeline

if __package__:
    from .reference_construct import reference_request
else:
    from reference_construct import reference_request


def main():
    for alphabet in ("DNA", "RNA"):
        request, manifest, registry = reference_request(alphabet)
        manifests = {manifest.reference_set_id: manifest}
        build = run_molecular_pipeline(request, registry, manifests)
        record = build.candidate.records[0]
        exported = export_reference_sequence(
            request, build.construct, build.candidate, registry, manifests
        )
        print(
            f"{build.candidate.profile}: {build.result.status.value}; check: {build.check_result.outcome.value}"
        )
        print(f"Reference: {record.reference.id}; length: {record.length}")
        print(
            f"Scope: {record.completeness}; optimization: {build.candidate.encoding_policy.optimization}"
        )
        print(f"Canonical sequence SHA-256: {record.sequence_sha256}")
        print(f"FASTA file SHA-256: {exported.fasta_sha256}")
        print(f"JSON specification SHA-256: {exported.specification_sha256}")
        print(f"Export roundtrip: {verify_sequence_export(exported, build.candidate)}")
        print(
            "Unresolved: "
            + "; ".join(item.description for item in build.result.unresolved)
        )


if __name__ == "__main__":
    main()
