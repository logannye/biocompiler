"""Build separate pinned DNA/RNA whole-CDS layouts without emitting sequences.

Run: PYTHONPATH=src python examples/reference_construct.py
"""

from pathlib import Path

from cellweave.compiler.construct import run_construct_pipeline
from cellweave.ir.component_contracts import PinnedIdentity
from cellweave.ir.composition import CompositionInstance, CompositionRequest
from cellweave.registry.components import ComponentRegistry
from cellweave.registry.reference_components import (
    ReferenceSelection,
    adapt_reference_component,
)
from cellweave.registry.references import load_reference_manifest
from cellweave.semantics.component_contracts import OperatingDomain
from cellweave.semantics.context import PayloadFormat, TargetContext
from cellweave.synthesis.construct import prepare_reference_construct

# Independent reviewed expectations, not hashes calculated from candidate output.
MANIFEST_PIN = PinnedIdentity(
    "reference",
    "wo2022081694a1.murine-fapcar.cds",
    "1",
    "8d26e8d3e960d8dc0996e1f0582372ddfc9685795ed54131557f101be8849a41",
)
REFERENCE_PINS = {
    "DNA": PinnedIdentity(
        "reference",
        "wo2022081694a1.murine-fapcar.seq2",
        "1",
        "be64d2c4e6a5887a78c193be6f3aa747460487fa3e0a3a479784a95f58bcad90",
    ),
    "RNA": PinnedIdentity(
        "reference",
        "wo2022081694a1.murine-fapcar.seq3",
        "1",
        "8c4deb2c377aa04b1586abdef9eda951418ea3dc04b3146dba2a2bef5b40a5d5",
    ),
}


def reference_request(alphabet):
    path = Path(__file__).resolve().parents[1] / "data/references/fap_car/manifest.json"
    manifest = load_reference_manifest(
        path, expected_fingerprint=MANIFEST_PIN.content_fingerprint
    )
    selection = ReferenceSelection(MANIFEST_PIN, REFERENCE_PINS[alphabet])
    component = adapt_reference_component(manifest, selection)
    registry = ComponentRegistry("reviewed-cds", "1", (component,))
    lock = registry.lock({"fap_cds": component})
    requirements = ("preserve_selected_cds",)
    composition = CompositionRequest(
        TargetContext("reference", "1", PayloadFormat(alphabet)),
        lock,
        (
            CompositionInstance(
                "fap_cds",
                lock.components[0],
                OperatingDomain(),
                requirement_ids=requirements,
            ),
        ),
        requirement_ids=requirements,
    )
    request = prepare_reference_construct(manifest, selection, composition, registry)
    return request, manifest, registry


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
