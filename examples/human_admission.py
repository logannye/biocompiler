"""Use admission is separate from a passing supplied-observation check."""

import argparse
from dataclasses import replace
from pathlib import Path

import biocompiler as bc
from biocompiler.registry.components import SelectionRequest
from biocompiler.registry.reference_builds import load_reference_inputs

if __package__:
    from .human_acceptance import make_human_acceptance, example_trace
else:
    from human_acceptance import make_human_acceptance, example_trace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    acceptance = make_human_acceptance()
    observations = bc.check_human_acceptance(acceptance, example_trace())
    assert observations.outcome == "pass"
    human = acceptance.behavior_request.build_request.target
    construct, _, registry = load_reference_inputs(
        "RNA", Path(__file__).resolve().parents[1] / "data/references/fap_car"
    )
    record = registry.components[0]
    software = bc.AdmissionRequest(
        construct.target, "software_test", "selection", (record,)
    )
    requested = bc.AdmissionRequest(human, "human_therapeutic", "selection", (record,))
    software_assessment = bc.assess_admission(software)
    human_assessment = bc.assess_admission(requested)
    assert software_assessment.decision == "software_only"
    assert human_assessment.decision == "not_admitted"
    selection = SelectionRequest(
        record.implementation_role, construct.target, record.supported_domain
    )
    software_selection = registry.select(selection)
    human_selection = registry.select(replace(selection, target=human))
    assert software_selection.outcome == "pass"
    assert human_selection.outcome == "unsupported"
    assert bc.verify_admission(requested, human_assessment)
    records = {
        "software-request": software,
        "human-request": requested,
        "software-assessment": software_assessment,
        "human-assessment": human_assessment,
        "software-selection": software_selection,
        "human-selection": human_selection,
        "acceptance-observations": observations,
    }
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        for name, record in records.items():
            (args.output / f"{name}.json").write_text(
                record.to_json() + "\n", encoding="utf-8"
            )
    print("Artificial supplied observations: pass")
    print("Pinned reference software selection: pass; intended_use=software_test")
    print("Human therapeutic selection: unsupported; admission=not_admitted")
    print("No human therapeutic profile is admitted by this policy version.")


if __name__ == "__main__":
    main()
