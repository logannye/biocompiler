"""Run an abstract input trace through the checked behavior layer.

All inputs and outputs are generic symbols. This is a language-semantics example,
not a molecular model, sequence generator, or therapeutic design.
Run ``PYTHONPATH=src python examples/behavior_trace.py`` from the checkout.
"""

from __future__ import annotations

import biocompiler as bc
from biocompiler.compiler.behavior import lower_to_behavior, verify_lowering
from biocompiler.semantics.evaluator import InputFrame, SignalSample, evaluate


def run_example():
    therapy = bc.Therapy("abstract_behavior_trace")
    cells = therapy.engineer("responder", cell_type="abstract_cell")
    a, b = cells.contact.marker("A"), cells.contact.marker("B")
    matched = (a.present() & b.present()).held_for(bc.Duration(2, unit="s"))
    memory = cells.memory("matched", set_when=matched, duration=bc.Duration(4))
    phase = cells.state("phase", values=("searching", "ready"), initial="searching")
    cells.when(memory.is_set()).do(phase.set("ready"))
    cells.on(phase.is_("ready").became_true()).do(
        cells.report("ready"), cells.rest().for_(bc.Duration(3))
    )

    intent = therapy.freeze()
    behavior = lower_to_behavior(intent)
    report = verify_lowering(intent, behavior)
    history = [
        InputFrame(
            0,
            contacts={
                "first": {
                    a.node_id: SignalSample(present=True),
                    b.node_id: SignalSample(present=False),
                },
                "second": {
                    a.node_id: SignalSample(present=False),
                    b.node_id: SignalSample(present=True),
                },
            },
        ),
        InputFrame(
            1,
            contacts={
                "first": {
                    a.node_id: SignalSample(present=True),
                    b.node_id: SignalSample(present=True),
                },
            },
        ),
        InputFrame(4),
    ]
    result = evaluate(behavior, history, until=8)
    return intent, behavior, report, result, phase.node_id, memory.node_id


def main():
    intent, behavior, report, result, phase_id, memory_id = run_example()
    print(f"Intent: {intent.name}")
    print(f"Behavior profile: {behavior.policies['profile']}")
    print(f"Lowering preservation checks passed: {report.passed}")
    print(" time  phase       remembered  ongoing requests  reactions")
    for frame in result.frames:
        ongoing = (
            ", ".join(action.kind.removeprefix("action.") for action in frame.actions)
            or "-"
        )
        reactions = (
            ", ".join(
                action.attributes.get("label", action.kind)
                for action in frame.reactions
            )
            or "-"
        )
        print(
            f"{frame.time:5g}  {frame.states[phase_id]:10}  {str(frame.memories[memory_id]):10}  {ongoing:16}  {reactions}"
        )
    print("A and B on separate objects do not match. The joint match begins at 1 s;")
    print("the 2 s dwell completes at 3 s without an extra input snapshot.")
    print("The local pulse ends at 6 s; memory expires at 7 s after contact is lost.")


if __name__ == "__main__":
    main()
