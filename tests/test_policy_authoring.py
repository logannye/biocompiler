"""Public authoring contracts with independent expected declaration structure."""
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext
import json
import subprocess
import sys
import unittest

import biocompiler.policy as bp
from biocompiler.policy.examples import NAMES, build_example, build_request, semantic_bundle


class PolicyAuthoringTests(unittest.TestCase):
    def test_all_examples_are_structural_only(self):
        for name in NAMES:
            with self.subTest(name=name):
                program = build_example(name)
                report = bp.check(program)
                self.assertEqual(report.status, "complete")
                self.assertEqual(report.semantic_status, "unassessed")
                self.assertEqual(report.target_status, "unassessed")
                self.assertIn("safety_and_progress_satisfaction", report.deferred_obligations)
                self.assertEqual(bp.loads(bp.dumps(program)), program)
                request = build_request(name)
                self.assertEqual(bp.check(request).status, "complete")
                submission = bp.prepare_submission(request)
                self.assertEqual(submission.backend_execution, "not_performed")

    def test_gated_expression_expected_shape(self):
        program = build_example("context_gated_response")
        rule = next(x for x in program.declarations if isinstance(x, bp.Rule))
        guard = bp.to_data(rule.when)
        self.assertEqual(guard["op"], "all")
        self.assertEqual(guard["args"][0]["ref"], {"$type": "Ref", "id": "disease", "kind": "Observation"})
        self.assertEqual(guard["args"][1]["op"], "not")
        self.assertEqual(guard["args"][1]["args"][0]["ref"]["id"], "exclusion")
        self.assertEqual(rule.unknown, "defer")
        self.assertEqual(rule.effects, (bp.Ref("effect", "Effect"),))

    def test_symbolic_truth_rejects_python_control_flow(self):
        for expression in (bp.TRUE, bp.FALSE, bp.UNKNOWN, bp.all_of(bp.TRUE, bp.UNKNOWN)):
            with self.subTest(expression=expression.op):
                with self.assertRaisesRegex(TypeError, "symbolic"):
                    bool(expression)
                with self.assertRaises(TypeError):
                    all([expression])

    def test_exact_quantities_have_independent_expected_wire(self):
        value = bp.quantity("01.5000", bp.SECOND)
        expected = {"$type": "Quantity", "amount": "1.5", "unit": {"$type": "Unit", "id": "s", "dimension": "time", "quantity_kind": "duration", "scale": "1", "reference": None}}
        self.assertEqual(bp.to_data(value), expected)
        with localcontext() as context:
            context.prec = 2
            self.assertEqual(bp.quantity("1234.5678", bp.SECOND).amount, "1234.5678")
        for bad in (1.5, True):
            with self.assertRaises(TypeError):
                bp.quantity(bad, bp.SECOND)
        self.assertEqual(bp.from_float(0.5, bp.SECOND), bp.quantity("0.5", bp.SECOND))
        with self.assertRaises(ValueError):
            bp.quantity("1e1024", bp.SECOND)

    def test_semantic_quantity_kind_is_not_only_dimension(self):
        a = bp.literal(bp.quantity(2, bp.Unit("a", "count", "target_count")))
        b = bp.literal(bp.quantity(2, bp.Unit("b", "count", "executor_count")))
        with self.assertRaises(TypeError):
            bp.compare(a, "eq", b)

    def test_unit_scale_obeys_numeric_wire_bounds(self):
        for spelling in ("0" * 256 + "1", "1_000", "NaN", "1e1025"):
            with self.subTest(scale=spelling):
                with self.assertRaises(bp.PolicySerializationError):
                    bp.dumps(bp.Unit("scaled", "time", "duration", spelling))

    def test_literal_bounds_compare_exact_declared_scales(self):
        parameter = bp.Parameter("duration", bp.TypeSpec("quantity", bp.SECOND),
                                 bp.quantity(30, bp.SECOND), lower=bp.quantity(1, bp.MINUTE),
                                 upper=bp.quantity(45, bp.SECOND))
        program = bp.PolicyProgram("bounds", bp.SemanticBundle("empty", "1"), (parameter,))
        report = bp.check(program)
        self.assertEqual(report.status, "invalid")
        self.assertTrue({"parameter_bound_value", "bound_order"} <= {x.code for x in report.errors})

    def test_event_and_guard_types_remain_separate(self):
        event = bp.Expr("rising", bp.EVENT, (bp.TRUE,))
        with self.assertRaises(TypeError):
            bp.all_of(event, bp.TRUE)
        with self.assertRaises(TypeError):
            bp.time.followed_by(bp.TRUE, event, within=bp.quantity(1, bp.SECOND), clock=bp.Ref("c", "Clock"))

    def test_temporal_fields_preserve_coverage_and_anchor(self):
        clock = bp.Ref("c", "Clock")
        continuous = bp.time.holds(bp.TRUE, bp.quantity(2, bp.SECOND), clock=clock, coverage="continuous")
        sampled = bp.time.holds(bp.TRUE, bp.quantity(2, bp.SECOND), clock=clock, coverage="sampled")
        self.assertNotEqual(bp.document_digest(continuous), bp.document_digest(sampled))
        event = bp.rising(bp.TRUE)
        deadline = bp.time.within(event, event, bp.quantity(3, bp.SECOND), clock=clock)
        self.assertEqual(deadline.args, (event, event))
        self.assertEqual(deadline.duration.amount, "3")

    def test_draft_holes_require_explicit_resolution(self):
        p = bp.ProgramBuilder("draft", semantics=bp.SemanticBundle("empty", "1"))
        p.hole("state", expected="Parameter", question="Select the explicit bound.")
        snapshot = p.snapshot()
        self.assertEqual(bp.check(snapshot).status, "incomplete")
        with self.assertRaises(bp.AuthoringError):
            p.freeze()
        p.resolve("state", bp.Parameter("state", bp.INTEGER, 3))
        self.assertEqual(bp.check(p.freeze()).status, "complete")
        self.assertEqual(len(snapshot.holes), 1)

    def test_list_inputs_are_frozen_and_effects_are_not_interned(self):
        declarations = [bp.Parameter("x", bp.INTEGER, 1)]
        p = bp.PolicyProgram("immutable", bp.SemanticBundle("empty", "1"), declarations)
        declarations.clear()
        self.assertEqual(len(p.declarations), 1)
        with self.assertRaises(FrozenInstanceError):
            p.id = "changed"
        example = build_example("context_gated_response")
        effect = next(x for x in example.declarations if isinstance(x, bp.Effect))
        second = replace(effect, id="effect_again")
        self.assertNotEqual(bp.document_digest(effect), bp.document_digest(second))
        both = replace(example, declarations=example.declarations + (second,))
        self.assertEqual(len([x for x in bp.loads(bp.dumps(both)).declarations if isinstance(x, bp.Effect)]), 2)

    def test_same_named_cross_program_references_are_rejected(self):
        a = bp.ProgramBuilder("a", semantics=bp.SemanticBundle("empty", "1"))
        b = bp.ProgramBuilder("b", semantics=bp.SemanticBundle("empty", "1"))
        role_a = a.executor("executor", requires=())
        b.executor("executor", requires=())
        with self.assertRaisesRegex(bp.AuthoringError, "Cross-program"):
            b.subject("target", entity_kind="cell", identity_scope="stable", executor=role_a)
        with self.assertRaisesRegex(bp.AuthoringError, "Cross-program"):
            b.add(role_a)

    def test_namespace_ids_and_pattern_origins(self):
        p = bp.ProgramBuilder("names", semantics=bp.SemanticBundle("empty", "1"))
        with p.namespace("left"):
            role = p.executor("executor", requires=())
        self.assertEqual(role.id, "left/executor")
        self.assertEqual(p.snapshot().source_map[0].pattern, "left")
        with self.assertRaises(bp.AuthoringError):
            p.add(bp.Role("left/executor", ()))

    def test_memory_scopes_differ(self):
        a = build_example("encounter_sentinel")
        b = build_example("target_sentinel")
        left = next(x for x in a.declarations if isinstance(x, bp.StateStore))
        right = next(x for x in b.declarations if isinstance(x, bp.StateStore))
        self.assertEqual((left.scope.kind, left.lifetime), ("encounter", "encounter"))
        self.assertEqual((right.scope.kind, right.lifetime), ("target", "persistent"))

    def test_terminal_outcomes_and_coordination_are_explicit(self):
        staged = build_example("staged_cleanup_repair")
        machine = next(x for x in staged.declarations if isinstance(x, bp.Machine))
        self.assertEqual(machine.terminal, ("completed", "failed"))
        coordinated = build_example("coordinated_populations")
        channel = next(x for x in coordinated.declarations if isinstance(x, bp.Channel))
        self.assertEqual((channel.acknowledgment, channel.retry, channel.max_attempts), ("required", "bounded", 3))
        send = next(x for x in coordinated.declarations if isinstance(x, bp.Rule) and x.emissions)
        self.assertEqual(send.emissions, (bp.Ref("message", "Message"),))

    def test_doc_digest_is_deterministic_across_processes(self):
        script = "from biocompiler.policy.examples import build_example; from biocompiler.policy import document_digest; print(document_digest(build_example('context_gated_response')))"
        outputs = [subprocess.check_output([sys.executable, "-c", script], text=True).strip() for _ in range(2)]
        self.assertEqual(outputs[0], outputs[1])

    def test_source_map_does_not_change_behavior_document_digest(self):
        p = build_example("context_gated_response")
        other = replace(p, source_map=tuple(replace(s, file="different.py", line=s.line + 5) for s in p.source_map))
        self.assertEqual(bp.document_digest(p), bp.document_digest(other))
        self.assertNotEqual(bp.dumps(p), bp.dumps(other))

    def test_wire_extension_cannot_register_executable_python(self):
        with self.assertRaisesRegex(TypeError, "closed registry"):
            type("Callback", (bp.Record,), {"__module__": "untrusted_plugin"})


if __name__ == "__main__":
    unittest.main()
