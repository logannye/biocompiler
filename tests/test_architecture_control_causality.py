"""Channel transport is part of source control influence, including dynamic paths."""
from dataclasses import replace
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.ir.payload_architecture import ControlRequirement
from biocompiler.verification.payload_architecture import _causal_nodes
from examples.payload_architectures import make_architecture_request


def authored(name, *, coupled, pulse=False, stateful=False):
    therapy = bc.Therapy(name)
    sender = therapy.engineer("sender", cell_type="human_T_cell")
    receiver = therapy.engineer("receiver", cell_type="human_T_cell")
    channel = therapy.channel("alert", scope="local", type=bc.Level)
    context = sender.environment.signal("context").present()
    stop = sender.environment.signal("shutdown").present()
    emission = sender.emit(channel, value=1)
    if pulse:
        emission = emission.for_(bc.Duration(2))
    guard = context & ~stop if coupled else context
    if stateful:
        state = sender.state("mode", values=("active", "off"), initial="active")
        sender.when(stop).do(state.set("off"))
        guard = context & state.is_("active")
    sender.when(guard).do(emission)
    sender.when(context & ~stop).do(sender.secrete("artificial_alpha"))
    receiver_stop = receiver.environment.signal("shutdown").present()
    received = receiver.sense(channel)
    receiver.when((received > 0) & ~receiver_stop).do(receiver.secrete("artificial_beta"))
    return therapy.freeze()


def request_for(*, coupled, pulse=False, stateful=False):
    # Source and supplier graphs are authored independently; the same shape
    # makes the transport/control claim, not a mismatched model, the variable.
    source = authored("original_source", coupled=coupled, pulse=pulse, stateful=stateful)
    model = authored("supplied_model", coupled=coupled, pulse=pulse, stateful=stateful)
    with patch("examples.payload_architectures.source_program", return_value=source), \
         patch("examples.payload_architectures.contract_program", return_value=model):
        request = make_architecture_request("D")
    if pulse:
        refinement = request.library.refinements[0]
        pulse_id = next(node.id for node in model.nodes if node.kind == "action.pulse")
        refinement = replace(refinement, channels=tuple(
            replace(channel, sender_node_id=pulse_id) for channel in refinement.channels))
        request = replace(request, library=replace(request.library, refinements=(refinement,)))
    actions = tuple(node.id for node in source.nodes if node.kind == "action.secrete")
    requirement = ControlRequirement("independent-role-stops", "shutdown", actions, "independent")
    return replace(request, constraints=replace(request.constraints, control_requirements=(requirement,)))


class ArchitectureChannelControlCausalityTests(unittest.TestCase):
    def test_sender_shutdown_is_not_independent_of_the_receiver_it_signals(self):
        request = request_for(coupled=True)
        build = bc.compile_payload_architecture(request)
        self.assertEqual(build.status, "no_solution")
        gaps = tuple(gap for alternative in build.alternatives for gap in alternative.gaps)
        self.assertTrue(any("independent_control_cross_influence" in gap.code for gap in gaps), gaps)
        self.assertFalse(any("unsupported_control" in gap.code for gap in gaps), gaps)

    def test_independent_stops_across_roles_remain_possible_with_unrelated_transport_control(self):
        request = request_for(coupled=False)
        build = bc.compile_payload_architecture(request)
        self.assertEqual(build.status, "compiled", build.alternatives)
        self.assertTrue(bc.check_payload_architecture(build, expected_request=request).translation_complete)

    def test_pulse_sender_installation_and_dynamic_state_writes_are_causal(self):
        for pulse, stateful in ((True, False), (False, True)):
            with self.subTest(pulse=pulse, stateful=stateful):
                request = request_for(coupled=True, pulse=pulse, stateful=stateful)
                build = bc.compile_payload_architecture(request)
                self.assertEqual(build.status, "no_solution")
                gaps = tuple(gap for alternative in build.alternatives for gap in alternative.gaps)
                self.assertTrue(any("independent_control_cross_influence" in gap.code for gap in gaps), gaps)
                nodes = {node.id: node for node in request.source.intent.nodes}
                receiver = next(node.id for node in nodes.values()
                                if node.kind == "role" and node.attributes["name"] == "receiver")
                output = next(node.id for node in nodes.values() if node.kind == "action.secrete" and node.role == receiver)
                sender_stop = next(node.id for node in nodes.values() if node.kind == "signal"
                                   and node.attributes["name"] == "shutdown" and node.role != receiver)
                self.assertIn(sender_stop, _causal_nodes(nodes, (output,)))

    def test_causal_channel_feedback_terminates_and_includes_both_directions(self):
        therapy = bc.Therapy("feedback")
        left = therapy.engineer("left", cell_type="human_T_cell")
        right = therapy.engineer("right", cell_type="human_T_cell")
        forward = therapy.channel("forward", scope="local")
        reverse = therapy.channel("reverse", scope="local")
        stop = left.environment.signal("shutdown").present()
        left.when((left.sense(reverse) > 0) & ~stop).do(left.emit(forward, value=1))
        output = right.secrete("artificial")
        right.when(right.sense(forward) > 0).do(right.emit(reverse, value=1), output)
        nodes = {node.id: node for node in therapy.freeze().nodes}
        causal = _causal_nodes(nodes, (output.node_id,))
        self.assertTrue({stop.node_id, forward.node_id, reverse.node_id} <= causal)
        self.assertTrue(causal <= nodes.keys())


if __name__ == "__main__":
    unittest.main()
