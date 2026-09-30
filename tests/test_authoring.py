"""Behavior-oriented checks for the public intent language."""

from __future__ import annotations

import unittest

import biocompiler as bc


class AuthoringTests(unittest.TestCase):
    def setUp(self):
        self.therapy = bc.Therapy("example")
        self.cells = self.therapy.engineer("responders", cell_type="T_cell")
        self.present = self.cells.contact.marker("target").present()

    def test_condition_and_actions_share_contact_and_role(self):
        self.cells.when(self.present, name="clearance").do(
            self.cells.eliminate(self.cells.contact),
            self.cells.secrete("support"),
        )
        program = self.therapy.freeze()
        (role,) = program.find(kind="role")
        (rule,) = program.find(kind="rule")
        (action,) = program.find(kind="action.eliminate")
        self.assertEqual(rule.role, role.id)
        self.assertEqual(action.role, role.id)
        self.assertIn(action.id, rule.inputs)
        self.assertEqual(rule.attributes["execution"], "concurrent")
        contact = next(
            node
            for node in program.find(kind="scope")
            if node.attributes.get("kind", node.attributes.get("scope")) == "contact"
        )
        self.assertIn(contact.id, action.inputs)

    def test_actions_are_inert_until_attached(self):
        baseline = self.therapy.freeze()
        self.cells.eliminate(self.cells.contact)
        self.cells.report("unused")
        after = self.therapy.freeze()
        self.assertEqual(baseline.fingerprint, after.fingerprint)
        self.assertFalse(after.find(kind="rule"))
        self.assertFalse(after.find(kind="action.eliminate"))

    def test_declarations_survive_without_rules(self):
        self.therapy.parameter("dwell", type=bc.Duration)
        self.therapy.channel("alert", scope="local")
        self.therapy.goal("support_recovery")
        self.cells.state("phase", values=("searching", "active"), initial="searching")
        self.cells.memory("primed", set_when=self.present)
        self.cells.secretion("output", product="support")
        program = self.therapy.freeze()
        for kind in (
            "role",
            "parameter",
            "channel",
            "goal",
            "state",
            "memory",
            "secretion",
        ):
            with self.subTest(kind=kind):
                self.assertTrue(program.find(kind=kind))
        self.assertFalse(program.find(kind="rule"))

    def test_same_role_declaration_is_idempotent_but_conflicts_fail(self):
        self.therapy.engineer("responders", cell_type="T_cell")
        self.assertEqual(len(self.therapy.freeze().find(kind="role")), 1)
        with self.assertRaises(ValueError):
            self.therapy.engineer("responders", cell_type="NK_cell")

    def test_named_output_conflicts_do_not_replace_previous_declaration(self):
        self.cells.secretion("support", product="factor_a")
        baseline = self.therapy.freeze()
        with self.assertRaises(ValueError):
            self.cells.secretion("support", product="factor_b")
        self.assertEqual(baseline.fingerprint, self.therapy.freeze().fingerprint)

    def test_named_rule_conflict_does_not_replace_original(self):
        self.cells.when(self.present, name="decision").do(self.cells.rest())
        baseline = self.therapy.freeze()
        with self.assertRaises(ValueError):
            self.cells.when(~self.present, name="decision").do(self.cells.expand())
        self.assertEqual(baseline.fingerprint, self.therapy.freeze().fingerprint)

    def test_rule_requires_at_least_one_action(self):
        with self.assertRaises((TypeError, ValueError)):
            self.cells.when(self.present).do()
        self.assertFalse(self.therapy.freeze().find(kind="rule"))

    def test_when_and_on_cannot_silently_interchange(self):
        with self.assertRaises(TypeError):
            self.cells.when(self.present.became_true())
        with self.assertRaises(TypeError):
            self.cells.on(self.present)
        self.cells.when(self.present).do(self.cells.rest())
        self.cells.on(self.present.became_true()).do(self.cells.report("onset"))
        triggers = {
            n.attributes["trigger"] for n in self.therapy.freeze().find(kind="rule")
        }
        self.assertEqual(triggers, {"condition", "event"})

    def test_cross_role_guard_action_and_target_are_rejected(self):
        other = self.therapy.engineer("other", cell_type="NK_cell")
        with self.assertRaises(ValueError):
            other.when(self.present)
        with self.assertRaises(ValueError):
            self.cells.when(self.present).do(other.rest())
        with self.assertRaises(ValueError):
            self.cells.eliminate(other.contact)

    def test_cross_therapy_objects_are_rejected_even_with_matching_names(self):
        other_therapy = bc.Therapy("example")
        other = other_therapy.engineer("responders", cell_type="T_cell")
        foreign_condition = other.contact.marker("target").present()
        with self.assertRaises(ValueError):
            self.cells.when(foreign_condition)
        with self.assertRaises(ValueError):
            self.present & foreign_condition
        foreign_channel = other_therapy.channel("alert", scope="local")
        with self.assertRaises(ValueError):
            self.cells.emit(foreign_channel)

    def test_role_namespaces_allow_independent_same_named_state(self):
        other = self.therapy.engineer("other", cell_type="NK_cell")
        self.cells.state("phase", values=("idle", "active"), initial="idle")
        other.state("phase", values=("idle", "active"), initial="idle")
        states = self.therapy.freeze().find(kind="state")
        self.assertEqual(len(states), 2)
        self.assertEqual(len({state.role for state in states}), 2)

    def test_state_requires_valid_initial_and_assignment_values(self):
        with self.assertRaises((TypeError, ValueError)):
            self.cells.state("bad", values=("idle", "active"), initial="missing")
        state = self.cells.state("phase", values=("idle", "active"), initial="idle")
        with self.assertRaises((TypeError, ValueError)):
            state.set("missing")
        with self.assertRaises((TypeError, ValueError)):
            state.is_("missing")

    def test_signature_rebinds_observations_to_each_role(self):
        @bc.signature
        def recognized(target):
            return target.marker("A").high() & target.marker("B").present()

        other = self.therapy.engineer("other", cell_type="NK_cell")
        self.cells.when(recognized(self.cells.contact)).do(self.cells.rest())
        other.when(recognized(other.contact)).do(other.rest())
        program = self.therapy.freeze()
        roles = {node.id for node in program.find(kind="role")}
        signals = program.find(kind="signal")
        self.assertEqual({node.role for node in signals}, roles)
        for role in roles:
            self.assertEqual(len([node for node in signals if node.role == role]), 2)

    def test_signature_must_return_a_condition(self):
        @bc.signature
        def invalid(target):
            return target.marker("A")

        with self.assertRaises(TypeError):
            invalid(self.cells.contact)

    def test_all_action_vocabulary_can_be_attached(self):
        alert = self.therapy.channel("alert", scope="local")
        self.cells.when(self.present).do(
            self.cells.eliminate(self.cells.contact),
            self.cells.engulf(self.cells.contact),
            self.cells.secrete("factor"),
            self.cells.present("antigen"),
            self.cells.emit(alert),
            self.cells.migrate_toward(self.cells.environment.gradient(alert)),
            self.cells.retain("local_tissue"),
            self.cells.expand(),
            self.cells.rest(),
            self.cells.differentiate("surveillance"),
            self.cells.report("engaged"),
        )
        program = self.therapy.freeze()
        (rule,) = program.find(kind="rule")
        attached_actions = [
            node
            for node in program.nodes
            if node.kind.startswith("action.") and node.id in rule.inputs
        ]
        self.assertEqual(len(attached_actions), 11)

    def test_shorthand_secretion_reuses_output_and_explicit_names_remain_distinct(self):
        named = self.cells.secretion("factor", product="factor")
        self.cells.when(self.present).do(self.cells.secrete("factor"), named.produce())
        self.cells.when(~self.present).do(self.cells.secrete("factor"))
        program = self.therapy.freeze()
        self.assertEqual(len(program.find(kind="secretion")), 2)
        secretion_actions = program.find(kind="action.secrete")
        self.assertEqual(len({action.inputs[0] for action in secretion_actions}), 2)


if __name__ == "__main__":
    unittest.main()
