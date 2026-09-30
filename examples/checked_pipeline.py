"""A frozen request, two checked passes, and a scoped synthetic result.

Run: PYTHONPATH=src python examples/checked_pipeline.py
The output is a software-model result, not a molecular build.
"""

import biocompiler as bc
from biocompiler.compiler.synthetic import run_synthetic_pipeline
from biocompiler.ir.serialization import fingerprint
from biocompiler.semantics.types import BOOLEAN


def build_request():
    therapy = bc.Therapy("checked_combinational_pipeline")
    cell = therapy.engineer("observer", cell_type="abstract_cell")
    a, b = cell.contact.marker("A"), cell.contact.marker("B")
    action = cell.rest()
    rule = cell.when(a.present() & b.present()).do(action)
    target = bc.TargetContext(
        "synthetic", "1", bc.PayloadFormat.RNA, capabilities=("synthetic_signal_graph",)
    )
    build = bc.BuildRequest.freeze(
        therapy.freeze(), target=target, artifact_scope="synthetic_realization"
    )
    behavior = bc.lower_to_behavior(build)
    response = bc.ResponseRequirement(
        "response",
        rule.node_id,
        action.node_id,
        bc.Observable("rest_readout", bc.Level, cell.role),
        bc.Interval(0.9, 1.1),
        bc.Interval(0, 0.1),
        bc.Duration(0.5),
        bc.Duration(0.5),
    )
    contract = bc.BehaviorContract("rest", behavior.fingerprint, (response,))
    domain = bc.OperatingDomain(
        "two_objects",
        "1",
        cell.role,
        tuple(
            bc.InputDomain(
                signal.node_id,
                "present",
                bc.Observable(label, BOOLEAN, cell.role, scope="contact"),
                (False, True),
            )
            for signal, label in ((a, "A"), (b, "B"))
        ),
        bc.Duration(7),
        max_contacts=2,
    )
    request = bc.RealizationRequest.freeze(build, behavior, contract, domain)

    def sample(first, second):
        return {
            a.node_id: bc.SignalSample(present=first),
            b.node_id: bc.SignalSample(present=second),
        }

    history = (
        bc.InputFrame(0, contacts={"x": sample(True, False), "y": sample(False, True)}),
        bc.InputFrame(1, contacts={"x": sample(True, True), "y": sample(False, True)}),
        bc.InputFrame(5, contacts={"x": sample(False, False)}),
    )
    return request, history


def main():
    request, history = build_request()
    build = run_synthetic_pipeline(request, history, until=7)
    print(f"Scope: {build.result.scope}; status: {build.result.status.value}")
    print(f"Request: {request.fingerprint}")
    print(f"Candidate: {build.candidate.fingerprint}")
    print(f"Locked synthetic components: {len(build.candidate.component_locks)}")
    print(
        "Unresolved: " + "; ".join(item.description for item in build.result.unresolved)
    )
    build.manager.set_dependency("catalog", fingerprint("changed catalog"))
    try:
        build.manager.result("mechanism", scope="synthetic_realization")
    except ValueError as exc:
        print(f"Dependency-change check: {exc}")


if __name__ == "__main__":
    main()
