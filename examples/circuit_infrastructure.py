"""Inspect and track artificial construction, binding and evidence metadata.

The six-symbol fixture exercises software bookkeeping only. Nominal associations
do not implement a molecular mechanism. The external record below is an explicit
artificial metadata fixture with no measured observations or published evidence.
No model is executed and human therapeutic admission remains unavailable.
"""

import argparse
from dataclasses import replace
import json
from pathlib import Path

from biocompiler.artifacts.circuit_inspection import (
    diff_circuit_constructions,
    inspect_circuit_construction,
)
from biocompiler.compiler.circuit_construction import build_circuit_construction
from biocompiler.ir.circuit_bindings import CircuitBindingRequest, CircuitEntityBinding
from biocompiler.ir.circuit_construction import AmountDeclaration
from biocompiler.ir.circuit_evidence import (
    CircuitEvidenceObservationBinding,
    CircuitEvidenceRequest,
    CircuitEvidenceSource,
)
from biocompiler.ir.circuit_intent import CircuitLifecycle
from biocompiler.ir.circuit_observations import ProductKind, QuantityKind
from biocompiler.ir.serialization import fingerprint
from biocompiler.verification.circuit_bindings import (
    check_circuit_bindings,
    verify_circuit_binding_assessment,
)
from biocompiler.verification.circuit_evidence import (
    capture_circuit_evidence,
    check_circuit_evidence,
    verify_circuit_evidence_assessment,
)

try:
    from examples.circuit_construction import make_construction_request
    from examples.circuit_molecules import fixture_provenance
except ModuleNotFoundError:
    from circuit_construction import make_construction_request
    from circuit_molecules import fixture_provenance


ARTIFICIAL_EXTERNAL_RECORD = {
    "kind": "artificial_software_metadata_fixture",
    "version": 1,
    "scope": "No measured observations, publication evidence or model predictions.",
}


def make_infrastructure_requests():
    """Declare nominal bindings only, using existing artificial construction parts."""
    construction = make_construction_request()
    requirement = construction.circuit.requirements[0]
    output = replace(
        requirement.behavior.output,
        kind=ProductKind.RNA_PRODUCT,
        observation=replace(
            requirement.behavior.output.observation,
            quantity=QuantityKind.RNA_ABUNDANCE,
        ),
    )
    behavior = replace(
        requirement.behavior,
        output=output,
        lifecycle=CircuitLifecycle("production_control"),
        dependencies=(),
    )
    construction = replace(
        construction,
        circuit=replace(
            construction.circuit,
            requirements=(replace(requirement, behavior=behavior),),
        ),
    )
    provenance = fixture_provenance("artificial-infrastructure-software-fixture")
    # These supplied associations deliberately assert no entity equivalence,
    # sensing mechanism, source fidelity or physical function.
    bindings = CircuitBindingRequest(
        "artificial-infrastructure-bindings",
        construction,
        tuple(
            CircuitEntityBinding(
                "nominal-" + source_id,
                requirement.id,
                kind,
                source_id,
                "required-payload",
                "payload-role",
                "RNA",
                provenance,
            )
            for kind, source_id in (
                *(("input_observation", item.id) for item in behavior.inputs),
                ("output_product", output.id),
            )
        ),
        (
            "Artificial software associations; molecular implementation is unestablished.",
        ),
    )
    evidence = CircuitEvidenceRequest(
        construction,
        (
            CircuitEvidenceSource(
                "artificial-external-reference",
                "reference",
                "1",
                fingerprint(ARTIFICIAL_EXTERNAL_RECORD),
                "reference_only",
                None,
                (
                    CircuitEvidenceObservationBinding(
                        requirement.id, output.observation.id
                    ),
                ),
                provenance,
            ),
        ),
    )
    return construction, bindings, evidence


def run_infrastructure_example():
    """Return deterministic inspection and freshly checked metadata artifacts."""
    construction, bindings, evidence = make_infrastructure_requests()
    build = build_circuit_construction(construction)
    inspection = inspect_circuit_construction(build, expected_request=construction)
    binding_assessment = check_circuit_bindings(
        build.candidate, expected_request=bindings
    )
    verify_circuit_binding_assessment(
        binding_assessment, build.candidate, expected_request=bindings
    )
    receipt = capture_circuit_evidence(build, expected_request=evidence)
    assessment = check_circuit_evidence(receipt, build, expected_request=evidence)
    verify_circuit_evidence_assessment(
        assessment, receipt, build, expected_request=evidence
    )

    corrected_record = {**ARTIFICIAL_EXTERNAL_RECORD, "version": 2}
    corrected_evidence = replace(
        evidence,
        sources=(
            replace(
                evidence.sources[0],
                version="2",
                record_fingerprint=fingerprint(corrected_record),
            ),
        ),
    )
    stale_assessment = check_circuit_evidence(
        receipt, build, expected_request=corrected_evidence
    )

    # A declared amount changes experiment identity without editing any bases.
    # The diff remains an artifact comparison, never a physical dose claim.
    changed_construction = replace(
        construction,
        amounts=(
            AmountDeclaration(
                "artificial-amount",
                construction.output_members[0].id,
                "artificial-preparation",
                (),
                1,
                "software_fixture_unit",
                fixture_provenance("artificial-amount-declaration"),
            ),
        ),
    )
    changed_build = build_circuit_construction(changed_construction)
    changed_evidence = replace(evidence, construction=changed_construction)
    stale_material = check_circuit_evidence(
        receipt, changed_build, expected_request=changed_evidence
    )
    difference = diff_circuit_constructions(
        build,
        changed_build,
        expected_before=construction,
        expected_after=changed_construction,
    )
    return {
        "request.json": construction,
        "build.json": build,
        "candidate.json": build.candidate,
        "hostile-label.build.json": build_circuit_construction(
            replace(construction, id='<img src=x onerror="window.injected=true">')
        ),
        "inspection.json": inspection,
        "binding-request.json": bindings,
        "binding-assessment.json": binding_assessment,
        "evidence-request.json": evidence,
        "evidence-receipt.json": receipt,
        "evidence-assessment.json": assessment,
        "artificial-external-record.json": ARTIFICIAL_EXTERNAL_RECORD,
        "corrected-artificial-external-record.json": corrected_record,
        "corrected-evidence-request.json": corrected_evidence,
        "stale-evidence-assessment.json": stale_assessment,
        "comparison-request.json": changed_construction,
        "comparison-build.json": changed_build,
        "comparison-evidence-request.json": changed_evidence,
        "stale-material-assessment.json": stale_material,
        "difference.json": difference,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    artifacts = run_infrastructure_example()
    if args.output is not None:
        args.output.mkdir(parents=True, exist_ok=True)
        for filename, artifact in artifacts.items():
            data = artifact.to_dict() if hasattr(artifact, "to_dict") else artifact
            (args.output / filename).write_text(
                json.dumps(
                    data, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
                )
                + "\n",
                encoding="utf-8",
            )
    print(
        "Nominal software bindings:", artifacts["binding-assessment.json"].outcome.value
    )
    print(
        "Evidence dependency identities:",
        artifacts["evidence-assessment.json"].freshness,
    )
    print(
        "After external metadata correction:",
        artifacts["stale-evidence-assessment.json"].freshness,
    )
    print(
        "Prediction: unsupported; empirical validation: unknown; human admission: not_admitted."
    )
    print("Artificial fixtures establish no published or biological evidence.")


if __name__ == "__main__":
    main()
