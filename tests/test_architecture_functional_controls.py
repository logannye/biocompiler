"""Functional labels require independent, nonvacuous source control proofs."""
from dataclasses import replace
import unittest

import biocompiler as bc
from biocompiler.compiler.behavior import lower_to_behavior
from biocompiler.compiler.request import BuildRequest
from biocompiler.semantics.evaluator import InputFrame, SignalSample, evaluate
from biocompiler.verification.architecture_controls import extended_control_targets, prove_extended_control
from biocompiler.verification.payload_architecture import _causal_nodes


def setup():
    therapy = bc.Therapy("artificial-control-proof")
    cells = therapy.engineer("responder", cell_type="human_T_cell")
    control = cells.environment.signal("control")
    context = cells.environment.signal("context")
    return therapy, cells, control, context


def proof(therapy, target, control, kind, *, nodes=None, bindings=None):
    nodes = nodes or {node.id: node for node in therapy.freeze().nodes}
    return prove_extended_control(nodes, target.node_id, {"controlling_node_ids": (control.node_id,)},
                                  kind, parameter_bindings=bindings)


def altered(therapy, handle, **attrs):
    nodes = {node.id: node for node in therapy.freeze().nodes}
    node = nodes[handle.node_id]
    nodes[node.id] = replace(node, attributes={**node.attributes, **attrs})
    return nodes


class MemoryControlProofTests(unittest.TestCase):
    def test_reset_dominates_simultaneous_set_and_positive_expiry(self):
        therapy, cells, control, context = setup()
        memory = cells.memory("licensed", set_when=context.present(), reset_when=control.present(),
                              duration=bc.Duration(3))
        memory_read = memory.is_set()
        cells.when(memory_read).do(cells.rest())
        for target in (memory, memory_read):
            self.assertIsNone(proof(therapy, target, control, "memory_reset"))
        self.assertEqual(proof(therapy, memory, control, "memory_reset",
                               nodes=altered(therapy, memory, reset_priority=False)),
                         "unsupported_memory_policy")
        result = evaluate(lower_to_behavior(therapy.freeze()), [
            InputFrame(time, {control.node_id: SignalSample(present=reset),
                              context.node_id: SignalSample(present=setting)})
            for time, reset, setting in ((0, False, True), (1, False, False), (2, True, True))])
        self.assertEqual([frame.memories[memory.node_id] for frame in result.frames], [True, True, False])

    def test_reset_label_and_unreachable_setting_are_not_proofs(self):
        therapy, cells, control, context = setup()
        reset = control.present()
        wrong = cells.memory("wrong", set_when=context.present(), reset_when=~reset)
        inert = cells.memory("inert", set_when=reset, reset_when=reset)
        missing = cells.memory("missing", set_when=context.present())
        self.assertEqual(proof(therapy, wrong, reset, "memory_reset"), "assertion_does_not_reset")
        self.assertEqual(proof(therapy, inert, reset, "memory_reset"), "memory_never_set_without_control")
        self.assertEqual(proof(therapy, missing, reset, "memory_reset"), "memory_reset_missing")

    def test_reset_must_be_nonvacuous_and_cell_local(self):
        therapy, cells, control, context = setup()
        c = control.present()
        always = c | ~c
        memory = cells.memory("memory", set_when=context.present(), reset_when=always)
        self.assertEqual(proof(therapy, memory, always, "memory_reset"), "vacuous_control_condition")
        contact = cells.contact.marker("switch").present()
        memory2 = cells.memory("contact-memory", set_when=context.present(), reset_when=contact)
        self.assertEqual(proof(therapy, memory2, contact, "memory_reset"), "non_cell_local_control")

    def test_exact_bound_controller_and_parameter_duration(self):
        therapy, cells, control, context = setup()
        duration = therapy.parameter("duration", type=bc.Duration, default=bc.Duration(3))
        memory = cells.memory("memory", set_when=context.present(), reset_when=control.present(), duration=duration)
        self.assertIsNone(proof(therapy, memory, control, "memory_reset", bindings={"duration": bc.Duration(1).to_dict()}))
        self.assertEqual(proof(therapy, memory, control, "memory_reset", bindings={}), "unbound_parameter")


class FiniteStateResetProofTests(unittest.TestCase):
    def state_program(self, *, competing=False, cycle=False):
        therapy, cells, control, context = setup()
        c, ready = control.present(), context.present()
        state = cells.state("phase", values=("idle", "primed", "active"), initial="idle")
        cells.when(c).do(state.set("idle"))
        cells.when((~c if not competing else c) & ready & state.is_("idle")).do(state.set("primed"))
        cells.when(~c & ready & state.is_("primed")).do(state.set("active"))
        if cycle:
            cells.when(~c & ready & state.is_("active")).do(state.set("idle"))
        return therapy, cells, control, context, state

    def test_reset_clears_all_prestates_and_reachable_stable_noninitial_state(self):
        therapy, _, control, context, state = self.state_program()
        self.assertIsNone(proof(therapy, state, control, "memory_reset"))
        self.assertIsNone(proof(therapy, state.is_("primed"), control, "memory_reset"))
        result = evaluate(lower_to_behavior(therapy.freeze()), [
            InputFrame(time, {control.node_id: SignalSample(present=reset),
                              context.node_id: SignalSample(present=ready)})
            for time, reset, ready in ((0, False, False), (1, False, True), (2, True, True))])
        self.assertEqual([frame.states[state.node_id] for frame in result.frames], ["idle", "active", "idle"])

    def test_competing_writer_cannot_hide_behind_reset_declaration(self):
        therapy, _, control, _, state = self.state_program(competing=True)
        self.assertEqual(proof(therapy, state, control, "memory_reset"), "conflicting_state_writers")

    def test_inactive_cycle_is_not_a_reachable_state_witness(self):
        therapy, _, control, _, state = self.state_program(cycle=True)
        self.assertEqual(proof(therapy, state, control, "memory_reset"), "nonsettling_state_writers")

    def test_reset_to_wrong_value_or_missing_prestate_is_rejected(self):
        for incomplete in (False, True):
            with self.subTest(incomplete=incomplete):
                therapy, cells, control, context = setup()
                c = control.present()
                state = cells.state("phase", values=("idle", "ready", "other"), initial="idle")
                cells.when(~c & context.present()).do(state.set("ready"))
                cells.when(c & state.is_("ready") if incomplete else c).do(state.set("idle" if incomplete else "ready"))
                self.assertEqual(proof(therapy, state, c, "memory_reset"), "assertion_does_not_reset_state")

    def test_typed_initial_false_does_not_equal_integer_zero(self):
        therapy, cells, control, context = setup()
        c = control.present()
        state = cells.state("typed", values=(False, 0, "ready"), initial=False)
        cells.when(~c & context.present()).do(state.set("ready"))
        wrong_reset = state.set(0)
        cells.when(c).do(wrong_reset)
        self.assertEqual(proof(therapy, state, c, "memory_reset"), "assertion_does_not_reset_state")
        self.assertIsNone(proof(therapy, state, c, "memory_reset",
                                nodes=altered(therapy, wrong_reset, value=False)))

    def test_temporal_and_other_store_writers_remain_explicitly_unsupported(self):
        for other_store in (False, True):
            with self.subTest(other_store=other_store):
                therapy, cells, control, context = setup()
                c = control.present()
                state = cells.state("phase", values=("idle", "ready"), initial="idle")
                other = cells.state("other", values=(False, True), initial=False)
                guard = other.is_(True) if other_store else context.present().held_for(bc.Duration(1))
                cells.when(~c & guard).do(state.set("ready"))
                cells.when(c).do(state.set("idle"))
                self.assertEqual(proof(therapy, state, c, "memory_reset"),
                                 "other_store_guard" if other_store else "unsupported_guard_expression")

    def test_reset_requires_change_witness_and_obeys_state_bound(self):
        therapy, cells, control, _ = setup()
        c = control.present()
        unused = cells.state("unused", values=("idle", "ready"), initial="idle")
        cells.when(c).do(unused.set("idle"))
        self.assertEqual(proof(therapy, unused, c, "memory_reset"), "state_never_changes_without_control")
        large = cells.state("large", values=tuple(range(17)), initial=0)
        cells.when(c).do(large.set(0))
        self.assertEqual(proof(therapy, large, c, "memory_reset"), "state_reset_proof_bound")


class ProductionAdjustmentProofTests(unittest.TestCase):
    def production(self, low=1, high=3):
        therapy, cells, control, context = setup()
        c = control.present()
        low_action = cells.secretion("basal", product="artificial_product").produce(rate=bc.ProductionRate(low))
        high_action = cells.secretion("boosted", product="artificial_product").produce(rate=bc.ProductionRate(high))
        cells.when(~c).do(low_action)
        cells.when(c).do(high_action)
        return therapy, cells, control, context, low_action, high_action

    def test_same_product_across_declarations_increase_and_decrease(self):
        for low, high in ((1, 3), (3, 1)):
            therapy, _, control, _, low_action, high_action = self.production(low, high)
            for action in (low_action, high_action):
                self.assertIsNone(proof(therapy, action, control, "production_adjustment"))
            result = evaluate(lower_to_behavior(therapy.freeze()), [
                InputFrame(time, {control.node_id: SignalSample(present=asserted)})
                for time, asserted in ((0, False), (1, True))])
            self.assertEqual([[action.values["rate"] for action in frame.actions]
                              for frame in result.frames], [[low], [high]])

    def test_constant_rate_is_not_production_adjustment(self):
        therapy, _, control, _, low_action, _ = self.production(2, 2)
        self.assertEqual(proof(therapy, low_action, control, "production_adjustment"), "production_rate_unchanged")

    def test_omitted_same_product_branch_or_reused_installation_is_detected(self):
        for reuse in (False, True):
            therapy, cells, control, context, low_action, high_action = self.production()
            extra = high_action if reuse else cells.secretion("hidden", product="artificial_product").produce(rate=bc.ProductionRate(99))
            cells.when(context.present()).do(extra)
            self.assertEqual(proof(therapy, low_action, control, "production_adjustment"), "overlapping_production_requests")

    def test_aggregate_targets_retain_hidden_context_control_influence(self):
        therapy, cells, control, context = setup()
        a, b = control.present(), context.present()
        named = cells.secretion("named", product="artificial_A").produce(rate=bc.ProductionRate(3))
        hidden = cells.secretion("hidden", product="artificial_A").produce(rate=bc.ProductionRate(1))
        other = cells.secrete("artificial_B", rate=bc.ProductionRate(4))
        cells.when(a).do(named)
        cells.when(~a & b).do(hidden)
        cells.when(b).do(other)
        # Both source adjustments are valid. Their product aggregates are not
        # independent: B's controller also changes A's inactive production.
        self.assertIsNone(proof(therapy, named, a, "production_adjustment"))
        self.assertIsNone(proof(therapy, other, b, "production_adjustment"))
        nodes = {node.id: node for node in therapy.freeze().nodes}
        aggregate = extended_control_targets(nodes, named.node_id, "production_adjustment")
        self.assertEqual(aggregate, (named.node_id, hidden.node_id))
        self.assertNotIn(context.node_id, _causal_nodes(nodes, (named.node_id,)))
        self.assertIn(context.node_id, _causal_nodes(nodes, aggregate))
        self.assertEqual(extended_control_targets(nodes, other.node_id, "production_adjustment"), (other.node_id,))

    def test_target_resolution_preserves_store_aliases_and_rejects_unknown_targets(self):
        therapy, cells, control, context = setup()
        memory = cells.memory("memory", set_when=context.present(), reset_when=control.present())
        read = memory.is_set()
        cells.when(read).do(cells.rest())
        nodes = {node.id: node for node in therapy.freeze().nodes}
        self.assertEqual(extended_control_targets(nodes, read.node_id, "memory_reset"), (memory.node_id,))
        self.assertEqual(extended_control_targets(nodes, "missing", "production_adjustment"), ())

    def test_complete_product_aggregate_does_not_include_other_role_or_product(self):
        therapy, cells, control, context, low_action, _ = self.production()
        cells.when(context.present()).do(cells.secrete("other_product"))
        other = therapy.engineer("other", cell_type="human_T_cell")
        other.when(other.environment.signal("on").present()).do(other.secrete("artificial_product"))
        self.assertIsNone(proof(therapy, low_action, control, "production_adjustment"))

    def test_parameter_binding_changes_proof_and_missing_binding_is_not_default(self):
        therapy, cells, control, _ = setup()
        c = control.present()
        rate = therapy.parameter("rate", type=bc.ProductionRate, default=bc.ProductionRate(3))
        off = cells.secrete("artificial", rate=bc.ProductionRate(1))
        on = cells.secrete("artificial", rate=rate * 2)
        cells.when(~c).do(off)
        cells.when(c).do(on)
        request = BuildRequest.freeze(therapy.freeze(), parameters={"rate": bc.ProductionRate(0.5)})
        self.assertIsNone(proof(therapy, on, c, "production_adjustment"))
        self.assertEqual(proof(therapy, on, c, "production_adjustment", bindings=request.resolved_bindings), "production_rate_unchanged")
        self.assertEqual(proof(therapy, on, c, "production_adjustment", bindings={}), "unbound_parameter")

    def test_units_and_negative_or_unspecified_rates(self):
        therapy, cells, control, _ = setup()
        c = control.present()
        off = cells.secrete("artificial", rate=bc.ProductionRate(60, unit="mol/min"))
        on = cells.secrete("artificial", rate=bc.ProductionRate(1, unit="mol/s"))
        cells.when(~c).do(off)
        cells.when(c).do(on)
        self.assertEqual(proof(therapy, on, c, "production_adjustment"), "production_rate_unchanged")
        for rate in (None, bc.ProductionRate(-1)):
            therapy, cells, control, _ = setup()
            on = cells.secrete("artificial", rate=rate)
            cells.when(control.present()).do(on)
            self.assertEqual(proof(therapy, on, control, "production_adjustment"),
                             "unspecified_production_rate" if rate is None else "negative_production_rate")

    def test_monotonicity_must_have_one_direction_for_every_other_observation(self):
        therapy, cells, control, context = setup()
        c, ctx = control.present(), context.present()
        target = None
        for guard, rate in ((~c & ctx, 1), (c & ctx, 3), (~c & ~ctx, 3), (c & ~ctx, 1)):
            action = cells.secrete("artificial", rate=bc.ProductionRate(rate))
            target = action
            cells.when(guard).do(action)
        self.assertEqual(proof(therapy, target, c, "production_adjustment"), "nonmonotone_production_adjustment")

    def test_compound_controller_cannot_hide_ambiguous_asserted_rates(self):
        therapy, cells, control, context = setup()
        a, b = control.present(), context.present()
        target = None
        for guard, rate in ((~a & ~b, 1), (a, 2), (~a & b, 3)):
            target = cells.secrete("artificial", rate=bc.ProductionRate(rate))
            cells.when(guard).do(target)
        controller = a | b
        cells.when(controller).do(cells.rest())
        self.assertEqual(proof(therapy, target, controller, "production_adjustment"), "ambiguous_production_control_state")

    def test_contact_exclusivity_cannot_establish_whole_cell_rate_exclusivity(self):
        therapy, cells, control, _ = setup()
        c = control.present()
        contact = cells.contact.marker("eligible").present()
        target = cells.secrete("artificial", rate=bc.ProductionRate(1))
        cells.when(c & contact).do(target)
        self.assertEqual(proof(therapy, target, c, "production_adjustment"), "non_cell_local_guard")

    def test_event_and_pulse_production_cannot_pass_as_instantaneous_adjustment(self):
        for pulse in (False, True):
            therapy, cells, control, _ = setup()
            c = control.present()
            target = cells.secrete("artificial", rate=bc.ProductionRate(1))
            cells.when(c).do(target)
            if pulse:
                cells.when(~c).do(target.for_(bc.Duration(3)))
            else:
                cells.on(c.became_true()).do(target)
            self.assertEqual(proof(therapy, target, c, "production_adjustment"), "persistent_or_event_installation")


class ActivityControlProofTests(unittest.TestCase):
    def test_explicit_effector_activity_with_contact_guard(self):
        for kind in ("eliminate", "engulf", "rest"):
            with self.subTest(kind=kind):
                therapy, cells, control, _ = setup()
                target = cells.contact
                c, marker = control.present(), target.marker("eligible").present()
                action = cells.rest() if kind == "rest" else getattr(cells, kind)(target)
                cells.when(c & marker).do(action)
                self.assertIsNone(proof(therapy, action, c, "activity_control"))
                # A second installation of the same action cannot bypass gating.
                cells.when(marker).do(action)
                self.assertEqual(proof(therapy, action, c, "activity_control"), "deassertion_does_not_gate_activity")

    def test_activity_is_distinct_from_production_and_is_nonvacuous(self):
        therapy, cells, control, _ = setup()
        c = control.present()
        secretion, rest = cells.secrete("artificial", rate=bc.ProductionRate(1)), cells.rest()
        cells.when(c).do(secretion)
        cells.when(c & ~c).do(rest)
        self.assertEqual(proof(therapy, secretion, c, "activity_control"), "target_not_explicit_activity_action")
        self.assertEqual(proof(therapy, rest, c, "activity_control"), "activity_never_enabled")

    def test_pulsed_reuse_cannot_pass_as_level_activity(self):
        therapy, cells, control, _ = setup()
        c, action = control.present(), cells.rest()
        cells.when(c).do(action)
        cells.when(c).do(action.for_(bc.Duration(2)))
        self.assertEqual(proof(therapy, action, c, "activity_control"), "persistent_or_event_installation")

    def test_ambiguous_raw_signal_and_opaque_controls_are_preserved(self):
        therapy, cells, control, _ = setup()
        c, action = control.present(), cells.rest()
        cells.when(c).do(action)
        cells.when(control.high()).do(cells.rest())
        self.assertEqual(proof(therapy, action, control, "activity_control"), "ambiguous_signal_predicate")
        self.assertIsNone(proof(therapy, action, c, "activity_control"))
        opaque = c.held_for(bc.Duration(2))
        cells.when(opaque).do(cells.rest())
        self.assertEqual(proof(therapy, action, opaque, "activity_control"), "unsupported_control_expression")

    def test_total_boolean_proof_bound_includes_guard_atoms(self):
        therapy, cells, control, _ = setup()
        c, action = control.present(), cells.rest()
        guard = c
        for index in range(8):
            guard &= cells.environment.signal(f"guard-{index}").present()
        cells.when(guard).do(action)
        self.assertEqual(proof(therapy, action, c, "activity_control"), "boolean_control_proof_bound")


if __name__ == "__main__":
    unittest.main()
