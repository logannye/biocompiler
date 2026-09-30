"""Select actual digital graph alternatives under frozen authored constraints.

Run: PYTHONPATH=src python examples/synthetic_selection.py
No biological efficiency or molecular implementation is modeled here.
"""

from dataclasses import replace
import json

import biocompiler as bc
from biocompiler.registry.synthetic import TEMPORAL_CATALOG, TEMPORAL_PROFILE_VERSION
from biocompiler.synthesis.selection import select_synthetic
from biocompiler.synthesis.synthetic import SyntheticGeneratorConfig

if __package__:
    from .temporal_pipeline import build_request
else:
    from temporal_pipeline import build_request


def prepare_request(*, forbid_and=False, max_gate_count=None):
    original, history = build_request()
    constraints = {}
    if forbid_and:
        constraints["allowed_operators"] = [
            item.operation
            for item in TEMPORAL_CATALOG.components
            if item.operation != "and"
        ]
    if max_gate_count is not None:
        constraints["max_gate_count"] = max_gate_count
    # These choices become input authority before lowering and contract binding.
    build = replace(
        original.build_request,
        implementation_constraints=constraints,
        preferences={"minimize": "gate_count"},
    )
    behavior = bc.lower_to_behavior(build)
    contract = replace(original.contract, behavior_fingerprint=behavior.fingerprint)
    return bc.RealizationRequest.freeze(
        build, behavior, contract, original.domain
    ), history


def main():
    for label, arguments in (
        ("least software gates", {}),
        ("AND forbidden", {"forbid_and": True}),
        ("empty bounded feasible set", {"max_gate_count": 0}),
    ):
        request, history = prepare_request(**arguments)
        result = select_synthetic(
            request,
            history,
            until=9,
            config=SyntheticGeneratorConfig(profile_version=TEMPORAL_PROFILE_VERSION),
        )
        print(
            json.dumps(
                {
                    "case": label,
                    "outcome": result.outcome,
                    "selected_strategy": result.selected_strategy,
                    "request_fingerprint": result.request_fingerprint,
                    "checked_candidates": result.checked_candidates,
                    "alternatives": [
                        {
                            "strategy": item.strategy,
                            "gate_count": item.gate_count,
                            "status": item.status,
                            "constraint_violations": list(item.constraint_violations),
                        }
                        for item in result.alternatives
                    ],
                    "search_scope": "two whole-program conjunction strategies only",
                    "intended_use": "software_test",
                    "human_therapeutic_admission": "not_admitted",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
