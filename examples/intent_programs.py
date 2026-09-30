"""Executable, symbolic examples of biocompiler's complete authoring API.

Run ``PYTHONPATH=src python examples/intent_programs.py`` from the checkout.
These programs describe intent; they do not create therapeutic sequences.
"""

from __future__ import annotations

import biocompiler as bc


@bc.signature
def pathological(target):
    """A reusable recognition pattern bound to each contacted target."""
    return target.marker("A").high() & (
        target.marker("B").present() | target.marker("C").present()
    )


def contextual_clearance() -> bc.IntentProgram:
    therapy = bc.Therapy("context_aware_response")
    cells = therapy.engineer("responders", cell_type="T_cell")
    context = cells.environment.signal("disease_context").present()
    cells.when(pathological(cells.contact) & context, name="local_clearance").do(
        cells.eliminate(cells.contact),
        cells.secrete("local_support_factor"),
    )
    therapy.goal("reduce_local_pathology")
    return therapy.freeze()


def priming_and_phases() -> bc.IntentProgram:
    therapy = bc.Therapy("primed_response")
    cells = therapy.engineer("responders", cell_type="T_cell")
    dwell = therapy.parameter("priming_duration", type=bc.Duration)
    expiry = therapy.parameter("memory_duration", type=bc.Duration)
    disease = cells.environment.signal("disease_context").present()
    recovery = cells.environment.signal("recovery").high()
    primed = cells.memory(
        "primed",
        set_when=disease.held_for(dwell),
        reset_when=recovery,
        duration=expiry,
    )
    phase = cells.state(
        "phase", values=("searching", "active", "recovering"), initial="searching"
    )
    cells.when(phase.is_("searching") & primed.is_set()).do(phase.set("active"))
    cells.when(phase.is_("active") & recovery).do(phase.set("recovering"))
    cells.when(phase.is_("active") & pathological(cells.contact)).do(
        cells.eliminate(cells.contact)
    )
    cells.when(phase.is_("recovering")).do(cells.rest())
    return therapy.freeze()


def temporal_response() -> bc.IntentProgram:
    therapy = bc.Therapy("temporal_response")
    cells = therapy.engineer("responders", cell_type="T_cell")
    interval = therapy.parameter("observation_window", type=bc.Duration)
    pulse = therapy.parameter("pulse_duration", type=bc.Duration)
    context = cells.environment.signal("disease_context").present()
    recognition = cells.contact.marker("target_marker").present()
    ordered_encounter = context.became_true().followed_by(
        recognition.became_true(), within=interval
    )
    cells.on(ordered_encounter, name="pulse_after_priming").do(
        cells.secrete("pulse_factor").for_(pulse),
        cells.report("ordered_encounter"),
    )
    cells.when(context.recently(within=interval) & recognition).do(
        cells.eliminate(cells.contact)
    )
    return therapy.freeze()


def graded_response() -> bc.IntentProgram:
    therapy = bc.Therapy("graded_local_response")
    cells = therapy.engineer("regulators", cell_type="regulatory_T_cell")
    inflammation = cells.environment.signal("inflammation", type=bc.Level)
    response = therapy.parameter(
        "secretion_response", type=bc.Curve[bc.Level, bc.ProductionRate]
    )
    resolution = cells.secretion("resolution", product="resolution_factor")
    cells.when(inflammation.high()).do(resolution.produce(rate=response(inflammation)))
    return therapy.freeze()


def feedback_regulation() -> bc.IntentProgram:
    therapy = bc.Therapy("local_resolution")
    cells = therapy.engineer("regulators", cell_type="regulatory_T_cell")
    inflammation = cells.environment.signal("inflammation", type=bc.Level)
    desired = therapy.parameter("desired_inflammation", type=bc.Level, default=0.2)
    resolution = cells.secretion("resolution", product="resolution_factor")
    cells.regulate(
        "resolve_inflammation",
        observed=inflammation,
        target=desired,
        actuator=resolution.rate,
        effect="decrease_observed",
        when=cells.environment.signal("disease_context").present(),
    )
    therapy.goal("support_recovery")
    return therapy.freeze()


def coordinated_response() -> bc.IntentProgram:
    therapy = bc.Therapy("coordinated_response")
    scouts = therapy.engineer("scouts", cell_type="macrophage")
    responders = therapy.engineer("responders", cell_type="NK_cell")
    alert = therapy.channel("disease_alert", scope="local", type=bc.Level)
    scouts.when(
        scouts.environment.signal("tissue_damage").high(), name="announce_damage"
    ).do(scouts.emit(alert))
    responders.when(
        responders.receives(alert) & pathological(responders.contact),
        name="alerted_response",
    ).do(responders.eliminate(responders.contact))
    responders.when(responders.receives(alert), name="follow_alert").do(
        responders.migrate_toward(responders.environment.gradient(alert))
    )
    return therapy.freeze()


EXAMPLES = {
    "contextual_clearance": contextual_clearance,
    "priming_and_phases": priming_and_phases,
    "temporal_response": temporal_response,
    "graded_response": graded_response,
    "feedback_regulation": feedback_regulation,
    "coordinated_response": coordinated_response,
}


if __name__ == "__main__":
    for name, build in EXAMPLES.items():
        program = build()
        print(f"{name}: {len(program.nodes)} intent nodes")
