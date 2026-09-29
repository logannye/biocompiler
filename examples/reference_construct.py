"""Build separate pinned DNA/RNA whole-CDS layouts without emitting sequences.

Run: PYTHONPATH=src python examples/reference_construct.py
"""

from pathlib import Path

from cellweave.compiler.construct import run_construct_pipeline
from cellweave.registry.reference_builds import (
    MANIFEST_PIN as MANIFEST_PIN,
    REFERENCE_PINS as REFERENCE_PINS,
    load_reference_inputs,
)


def reference_request(alphabet):
    directory = Path(__file__).resolve().parents[1] / "data/references/fap_car"
    return load_reference_inputs(alphabet, directory)


def main():
    for alphabet in ("DNA", "RNA"):
        request, manifest, registry = reference_request(alphabet)
        build = run_construct_pipeline(
            request, registry, {manifest.reference_set_id: manifest}
        )
        molecule = build.candidate.molecules[0]
        print(f"{alphabet} checked construct: {build.candidate.fingerprint}")
        print(
            f"Acceptance: {build.check_result.outcome.value}; status: {build.result.status.value}"
        )
        print(
            f"Scope: {molecule.completeness}; reference coordinates: [0, {molecule.length})"
        )
        print(
            f"Molecule topology: {molecule.topology}; component order: {molecule.component_order}"
        )
        print("Unknown features: " + ", ".join(molecule.unknown_features))
        print(
            "Unresolved: "
            + "; ".join(item.description for item in build.result.unresolved)
        )
        print(
            "No nucleotide sequence emitted; the CDS layout is the accepted artifact."
        )


if __name__ == "__main__":
    main()
