"""Record an illustrative human target without claiming supported biology."""

import argparse
from pathlib import Path

import biocompiler as bc


def make_human_target():
    def pending(description):
        return bc.TargetClaim(
            description=description,
            basis="unestablished",
            evidence_ids=(),
            limitations="Illustrative requirement only; applicable evidence has not been supplied.",
        )

    contract = bc.HumanTargetContract(
        cell_subtype=pending(
            "Human CD8-positive T-cell recipients; subtype refinement remains open."
        ),
        cell_state=pending(
            "Required recipient activation/differentiation state remains unspecified."
        ),
        tissue_context=pending("Intended human tissue context remains to be selected."),
        disease_context=pending("Intended disease context remains to be selected."),
        population_inclusion=pending(
            "Eligible human population and inclusion criteria remain unresolved."
        ),
        population_exclusion=pending(
            "Population exclusions require an explicit applicability review."
        ),
        host_dependencies=(
            bc.HumanHostDependency(
                "translation",
                "host_translation",
                "cytoplasm",
                pending("Host translation support requires context-matched evidence."),
            ),
        ),
        operating_conditions=(
            bc.HumanOperatingCondition(
                "resource_availability",
                "available_translation_resources",
                "cytoplasm",
                bc.ValueDomain.unknown(
                    reason="No supported resource operating range is established."
                ),
                pending(
                    "Supported intracellular resource conditions remain unresolved."
                ),
            ),
        ),
        evidence=(),
    )
    return bc.HumanTargetContext(
        "illustrative_human_target",
        "1",
        bc.PayloadFormat.RNA,
        compartments=("cytoplasm",),
        human_target=contract,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    target = make_human_target()
    restored = bc.TargetContext.from_json(target.to_json())
    assert restored == target
    print("Human in-vivo target specification: recorded")
    print("Biological applicability: unestablished")
    print(
        "Unresolved evidence obligations:", len(target.human_target.unresolved_evidence)
    )
    print("Payload compilation and clinical admission: unavailable")
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "human-target.json").write_text(
            target.to_json() + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
