"""Check human circuit scope using software-only declarations, without molecules."""

import argparse
from dataclasses import replace
import hashlib
from pathlib import Path

import biocompiler as bc

try:
    from examples.human_acceptance import make_human_acceptance
except ModuleNotFoundError:
    from human_acceptance import make_human_acceptance


def make_profile_requests():
    source = make_human_acceptance()
    target = source.target
    recipient = bc.ImmuneRecipientIdentity(
        bc.ImmuneLineage.T_CELL,
        target.fingerprint,
        target.human_target.cell_subtype.fingerprint,
    )
    product = bc.CircuitProfileRequest(
        purpose="human_immune_payload",
        mode="candidate_design",
        molecular_form=bc.PayloadFormat.RNA,
        boundary="planning",
        target=target,
        recipient=recipient,
        source_request=source,
    )
    fixture_text = b"Software-only human source context declaration; no experiment."
    experiment = bc.HumanExperimentContext(
        system="human_cell_line",
        immune_classification="nonimmune",
        cell_identity="illustrative_human_nonimmune_cell_context",
        cell_state="Unestablished; this is a software-only context fixture.",
        compartment="cytoplasm",
        delivery_mode="rna_delivery",
        sources=(
            bc.PinnedIdentity(
                "source",
                "software_fixture_no_experiment",
                "1",
                hashlib.sha256(fixture_text).hexdigest(),
            ),
        ),
        locator="In-memory fixture_text in examples/circuit_profile.py",
        assay_conditions=(
            "No experimental observations or biological material supplied.",
        ),
    )
    reference = bc.CircuitProfileRequest(
        purpose="human_reference",
        mode="exact_reproduction",
        molecular_form=bc.PayloadFormat.RNA,
        boundary="planning",
        source_experiment=experiment,
    )
    return {"product": product, "reference": reference}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    for label, request in make_profile_requests().items():
        assessment = bc.check_circuit_profile(request)
        bc.verify_circuit_profile(assessment, expected_request=request)
        (args.output / f"{label}.request.json").write_text(
            request.to_json() + "\n", encoding="utf-8"
        )
        (args.output / f"{label}.assessment.json").write_text(
            assessment.to_json() + "\n", encoding="utf-8"
        )
        for boundary in ("import", "selection", "verification", "export"):
            bounded = replace(request, boundary=boundary)
            checked = bc.check_circuit_profile(bounded)
            bc.verify_circuit_profile(checked, expected_request=bounded)
            assert checked.human_therapeutic_admission == "not_admitted"
        try:
            bc.compile(request)
        except bc.CompilationUnavailableError:
            pass
        else:
            raise AssertionError("A scope contract cannot compile a molecule.")
        print(f"{label}: {assessment.eligibility}; molecular compilation unsupported")


if __name__ == "__main__":
    main()
