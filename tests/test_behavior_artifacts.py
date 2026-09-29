"""Execution records identify their exact graph and installed action specifications."""

import json
import unittest

import cellweave as cw


class BehaviorArtifactTests(unittest.TestCase):
    def test_two_pulses_of_one_action_retain_distinct_specification_identities(self):
        therapy = cw.Therapy("pulse_provenance")
        cell = therapy.engineer("observer", cell_type="abstract_cell")
        signal = cell.environment.signal("A")
        base = cell.rest()
        short = base.for_(cw.Duration(2))
        long = base.for_(cw.Duration(3))
        cell.when(signal.present()).do(short, long)
        intent = therapy.freeze()
        behavior = cw.lower_to_behavior(intent)
        result = cw.evaluate(
            behavior,
            [cw.InputFrame(0, {signal.node_id: cw.SignalSample(present=True)})],
            until=4,
        )
        initial = result.frames[0].actions
        self.assertEqual({item.action_id for item in initial}, {base.node_id})
        self.assertEqual(
            {item.specification_id for item in initial}, {short.node_id, long.node_id}
        )
        for item in initial:
            self.assertEqual(
                item.specification_source, behavior.get(item.specification_id).source
            )
        at_two = next(frame for frame in result.frames if frame.time == 2)
        self.assertEqual(
            [item.specification_id for item in at_two.actions], [long.node_id]
        )
        self.assertFalse(result.frames[-1].actions)

    def test_saved_trace_is_immutable_and_tied_to_exact_source_and_behavior(self):
        therapy = cw.Therapy("trace_identity")
        cell = therapy.engineer("observer", cell_type="abstract_cell")
        signal = cell.environment.signal("A")
        cell.when(signal.present()).do(cell.report("observed"))
        intent = therapy.freeze()
        behavior = cw.lower_to_behavior(intent)
        result = cw.evaluate(
            behavior,
            [cw.InputFrame(0, {signal.node_id: cw.SignalSample(present=True)})],
        )
        data = json.loads(result.to_json())
        self.assertEqual(data["behavior_fingerprint"], behavior.fingerprint)
        self.assertEqual(data["source_fingerprint"], intent.fingerprint)
        self.assertEqual(data["execution_profile"], behavior.policies["profile"])
        data["frames"][0]["reactions"][0]["attributes"]["label"] = "changed"
        self.assertEqual(result.frames[0].reactions[0].attributes["label"], "observed")
        with self.assertRaises(TypeError):
            result.frames[0].reactions[0].attributes["label"] = "changed"
        with self.assertRaises(TypeError):
            result.frames[0].states["made_up"] = True


if __name__ == "__main__":
    unittest.main()
