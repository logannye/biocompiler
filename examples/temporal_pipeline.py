"""Generate and check dwell, pulse and resettable-memory software mechanisms.

Run: PYTHONPATH=src python examples/temporal_pipeline.py
The authored seconds and readout bands describe this digital fixture only.
"""

from dataclasses import replace
from pathlib import Path

import biocompiler as bc
from biocompiler.compiler.synthetic import run_synthetic_pipeline
from biocompiler.registry.synthetic import TEMPORAL_PROFILE_VERSION
from biocompiler.semantics.types import BOOLEAN
from biocompiler.synthesis.synthetic import SyntheticGeneratorConfig


def build_request():
    therapy = bc.Therapy("checked_temporal_pipeline")
    cell = therapy.engineer("observer", cell_type="abstract_cell")
    a, b = cell.contact.marker("A"), cell.contact.marker("B")
    reset = cell.environment.signal("reset")
    qualified = (a.present() & b.present()).held_for(bc.Duration(2))
    memory = cell.memory(
        "qualified_contact",
        set_when=qualified,
        reset_when=reset.present(),
        duration=bc.Duration(4),
    )
    local = cell.rest().for_(bc.Duration(3))
    contact = cell.eliminate(cell.contact).for_(bc.Duration(3))
    remembered = cell.rest()
    pulse_rule = cell.when(qualified).do(local, contact)
    memory_rule = cell.when(memory.is_set()).do(remembered)
    target = bc.TargetContext(
        "synthetic",
        "1",
        bc.PayloadFormat.RNA,
        capabilities=("synthetic_signal_graph",),
    )
    intent = therapy.freeze()
    # Freeze logical paths during authoring so the example can be packaged;
    # do not rewrite provenance on an imported frozen request.
    repository = Path(__file__).resolve().parents[1]
    intent = replace(
        intent,
        nodes=tuple(
            replace(
                node,
                source=replace(
                    node.source,
                    file=Path(node.source.file)
                    .resolve()
                    .relative_to(repository)
                    .as_posix(),
                ),
            )
            if node.source is not None
            else node
            for node in intent.nodes
        ),
    )
    build = bc.BuildRequest.freeze(
        intent, target=target, artifact_scope="synthetic_realization"
    )
    behavior = bc.lower_to_behavior(build)
    requirements = tuple(
        bc.ResponseRequirement(
            label,
            rule.node_id,
            action.node_id,
            bc.Observable(label, bc.Level, cell.role, scope=scope),
            bc.Interval(1, 1),
            bc.Interval(0, 0),
            bc.Duration(0),
            bc.Duration(0),
        )
        for label, rule, action, scope in (
            ("local_pulse", pulse_rule, local, "cell"),
            ("contact_pulse", pulse_rule, contact, "contact"),
            ("memory_readout", memory_rule, remembered, "cell"),
        )
    )
    contract = bc.BehaviorContract(
        "temporal_readouts", behavior.fingerprint, requirements
    )
    domain = bc.OperatingDomain(
        "bounded_contacts",
        "1",
        cell.role,
        tuple(
            bc.InputDomain(
                signal.node_id,
                "present",
                bc.Observable(label, BOOLEAN, cell.role, scope=scope),
                (False, True),
            )
            for signal, label, scope in (
                (a, "A", "contact"),
                (b, "B", "contact"),
                (reset, "reset", "cell"),
            )
        ),
        bc.Duration(9),
        max_contacts=2,
    )
    request = bc.RealizationRequest.freeze(build, behavior, contract, domain)

    def frame(time, contacts, resetting=False):
        return bc.InputFrame(
            time,
            {reset.node_id: bc.SignalSample(present=resetting)},
            {
                identity: {
                    a.node_id: bc.SignalSample(present=first),
                    b.node_id: bc.SignalSample(present=second),
                }
                for identity, (first, second) in contacts.items()
            },
        )

    history = (
        frame(0, {"x": (True, False), "y": (False, True)}),
        frame(1, {"x": (True, True), "y": (False, False)}),
        frame(4, {"x": (False, False), "y": (False, False)}),
        frame(5, {"x": (False, False), "y": (False, False)}, True),
        frame(7, {"x": (False, False), "y": (False, False)}),
    )
    return request, history


def main():
    request, history = build_request()
    build = run_synthetic_pipeline(
        request,
        history,
        until=9,
        config=SyntheticGeneratorConfig(profile_version=TEMPORAL_PROFILE_VERSION),
    )
    print(f"Scope: {build.result.scope}; status: {build.result.status.value}")
    print(f"Profile: {build.candidate.generator_config.profile_version}")
    print(f"Request: {request.fingerprint}")
    print(f"Candidate: {build.candidate.fingerprint}")
    print(
        "Unresolved: " + "; ".join(item.description for item in build.result.unresolved)
    )


if __name__ == "__main__":
    main()
