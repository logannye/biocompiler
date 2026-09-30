"""Check that time, history, and cell populations retain distinct semantics."""

from __future__ import annotations

import unittest

import biocompiler as bc


class TemporalAndCooperationTests(unittest.TestCase):
    def setUp(self):
        self.therapy = bc.Therapy("history")
        self.cells = self.therapy.engineer("responders", cell_type="T_cell")
        self.disease = self.cells.environment.signal("disease").present()
        self.recovery = self.cells.environment.signal("recovery").high()
        self.window = self.therapy.parameter("window", type=bc.Duration)

    def test_memory_retains_setting_reset_expiry_and_role(self):
        memory = self.cells.memory(
            "primed",
            set_when=self.disease.held_for(self.window),
            reset_when=self.recovery,
            duration=self.window,
        )
        self.cells.when(memory.is_set()).do(self.cells.rest())
        program = self.therapy.freeze()
        (node,) = program.find(kind="memory")
        (role,) = program.find(kind="role")
        self.assertEqual(node.role, role.id)
        self.assertEqual(node.attributes["initial"], False)
        self.assertEqual(node.attributes["setting"], "onset")
        self.assertEqual(node.attributes["reset_priority"], True)
        self.assertEqual(node.attributes["expiry"], "latest_setting_onset")
        self.assertTrue(
            {"set_when", "reset_when", "duration"}.issubset(
                node.attributes["input_names"]
            )
        )

    def test_same_named_memories_belong_to_distinct_cells(self):
        other = self.therapy.engineer("other", cell_type="NK_cell")
        self.cells.memory("primed", set_when=self.disease)
        other.memory("primed", set_when=other.environment.signal("disease").present())
        memories = self.therapy.freeze().find(kind="memory")
        self.assertEqual(len(memories), 2)
        self.assertEqual(len({node.role for node in memories}), 2)
        with self.assertRaises(ValueError):
            other.memory("foreign", set_when=self.disease)

    def test_event_order_and_pulse_are_explicit_graph_nodes(self):
        before = self.disease.became_true()
        after = self.recovery.became_true()
        event = before.followed_by(after, within=self.window)
        self.cells.on(event).do(self.cells.secrete("factor").for_(self.window))
        program = self.therapy.freeze()
        (rule,) = program.find(kind="rule")
        by_id = {node.id: node for node in program.nodes}
        event_node = by_id[rule.inputs[1]]
        self.assertIn("follow", event_node.kind)
        self.assertGreaterEqual(len(event_node.inputs), 3)
        first_id, second_id = event_node.inputs[:2]
        self.assertNotEqual(first_id, second_id)
        self.assertIn("became_true", by_id[first_id].kind)
        self.assertIn("became_true", by_id[second_id].kind)
        attached = [by_id[node_id] for node_id in rule.inputs[2:]]
        self.assertEqual(len(attached), 1)
        pulse = attached[0]
        self.assertEqual(pulse.kind, "action.pulse")
        self.assertEqual(pulse.attributes["retrigger"], "extend_from_latest_trigger")
        self.assertEqual(by_id[pulse.inputs[0]].kind, "action.secrete")
        self.assertEqual(by_id[pulse.inputs[1]].attributes["name"], "window")

    def test_state_assignments_are_actions_observations_are_conditions(self):
        state = self.cells.state("phase", values=("idle", "active"), initial="idle")
        self.cells.when(state.is_("idle") & self.disease).do(state.set("active"))
        self.cells.when(state.is_("active") & self.recovery).do(state.set("idle"))
        program = self.therapy.freeze()
        (state_node,) = program.find(kind="state")
        self.assertEqual(state_node.attributes["initial"], "idle")
        assignments = [
            node
            for node in program.nodes
            if node.kind.startswith("action.") and state_node.id in node.inputs
        ]
        self.assertEqual(len(assignments), 2)
        self.assertEqual(len(program.find(kind="rule")), 2)

    def test_event_reactions_do_not_accept_pulse_duration(self):
        with self.assertRaises(TypeError):
            self.cells.report("onset").for_(self.window)
        state = self.cells.state("phase", values=("idle", "active"), initial="idle")
        with self.assertRaises(TypeError):
            state.set("active").for_(self.window)

    def test_channel_links_roles_without_sharing_observations(self):
        scouts = self.therapy.engineer("scouts", cell_type="macrophage")
        alert = self.therapy.channel("alert", scope="local", type=bc.Level)
        scouts.when(scouts.environment.signal("damage").high()).do(scouts.emit(alert))
        self.cells.when(self.cells.receives(alert)).do(
            self.cells.migrate_toward(self.cells.environment.gradient(alert))
        )
        self.cells.when(self.cells.sense(alert) > 0.5).do(self.cells.rest())
        program = self.therapy.freeze()
        (channel,) = program.find(kind="channel")
        references = [node for node in program.nodes if channel.id in node.inputs]
        self.assertGreaterEqual(len(references), 3)
        self.assertEqual(
            len({node.role for node in references if node.role is not None}), 2
        )
        self.assertEqual(len(program.find(kind="rule")), 3)

    def test_communication_values_obey_channel_dimension(self):
        channel = self.therapy.channel("factor", scope="local", type=bc.Concentration)
        self.cells.when(self.disease).do(
            self.cells.emit(channel, value=bc.Concentration(1, unit="nM"))
        )
        with self.assertRaises(TypeError):
            self.cells.emit(channel, value=1)

    def test_gradients_belong_to_the_environment(self):
        environmental = self.cells.environment.signal("attractant")
        self.cells.when(self.disease).do(
            self.cells.migrate_toward(self.cells.environment.gradient(environmental))
        )
        with self.assertRaises(ValueError):
            self.cells.environment.gradient(self.cells.internal.signal("activation"))
        with self.assertRaises(TypeError):
            self.cells.migrate_toward(environmental)


if __name__ == "__main__":
    unittest.main()
