"""Link checked synthetic components and inspect a separately pinned CDS record.

Run: PYTHONPATH=src python examples/component_linking.py
The two selections remain distinct; no molecular sequence is emitted here.
"""

from pathlib import Path

import cellweave as cw
from cellweave.registry.references import load_reference_manifest

if __package__:
    from .checked_pipeline import build_request
else:
    from checked_pipeline import build_request


def main():
    request, history = build_request()
    build = cw.run_component_pipeline(request, history, until=7)
    print(f"Scope: {build.result.scope}; status: {build.result.status.value}")
    print(f"Component instances: {len(build.assembly.composition.instances)}")
    print(f"Registry lock: {build.assembly.composition.registry_lock.fingerprint}")
    print(f"Link result: {build.link_result.outcome.value}")
    print(
        "Unresolved: " + "; ".join(item.description for item in build.result.unresolved)
    )

    # This review pin is independent of the manifest being opened. The loader
    # verifies retained source and review files before reference adaptation.
    trusted = "8d26e8d3e960d8dc0996e1f0582372ddfc9685795ed54131557f101be8849a41"
    path = Path(__file__).resolve().parents[1] / "data/references/fap_car/manifest.json"
    manifest = load_reference_manifest(path, expected_fingerprint=trusted)
    reference = manifest.record("wo2022081694a1.murine-fapcar.seq3")
    component = cw.adapt_reference_component(
        manifest,
        cw.ReferenceSelection(
            cw.PinnedIdentity(
                "reference", manifest.reference_set_id, manifest.version, trusted
            ),
            cw.PinnedIdentity(
                "reference",
                reference.reference_id,
                reference.version,
                reference.fingerprint,
            ),
        ),
    )
    registry = cw.ComponentRegistry("reviewed-cds", "1", (component,))
    selected = registry.select(
        cw.SelectionRequest(
            "exact_cds_reference",
            cw.TargetContext("reference", "1", cw.PayloadFormat.RNA),
            cw.ComponentOperatingDomain(),
            classification="sequence_reference",
            component_id=component.id,
            component_version=component.version,
        )
    )
    print(f"Separate reference: {selected.selected.component_id}")
    print(f"Reference scope: {component.reference_metadata.completeness}")
    print("Dynamic ports: " + str(len(component.ports)))
    print(
        "Unknown features: " + ", ".join(component.reference_metadata.unknown_features)
    )


if __name__ == "__main__":
    main()
