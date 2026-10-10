"""Typed authoring categories, ownership, wire equivalence and static failures."""
from dataclasses import FrozenInstanceError, replace
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

from biocompiler import policy as p
from biocompiler.policy import typed as t
from tests.typecheck.policy_typed_positive import complete_policy

ROOT = Path(__file__).resolve().parents[1]


class PolicyTypedTests(unittest.TestCase):
    def setUp(self):
        self.program = complete_policy()
        self.records = {item.id: item for item in self.program.declarations}
        self.observation = self.records["signal"]
        self.state = self.records["count"]
        self.effect = self.records["response"]

    def test_complete_example_is_ordinary_source_with_identical_rule(self):
        source = self.records["respond"]
        parameter = p.Expr("parameter", p.INTEGER, ref=p.ref(self.records["maximum"]))
        expected = p.Rule("respond", p.ref(self.records["executor"]), self.observation.updated,
            p.all_of(self.observation.expression, p.compare(self.state.expression, "lt", parameter)),
            "defer", (p.ref(self.effect),),
            (p.Assignment(p.ref(self.state), p.arithmetic(self.state.expression, "add", p.literal(1))),),
            p.Arbitration("exclusive", "reject", "reject", "forbidden", "none"))
        self.assertEqual(source, expected)
        report = p.check(self.program)
        self.assertEqual((report.status, report.semantic_status), ("complete", "unassessed"))
        self.assertEqual(p.to_data(p.loads(p.dumps(self.program))), p.to_data(self.program))
        altered = replace(self.program, declarations=tuple(expected if item.id == "respond" else item
                                                         for item in self.program.declarations))
        self.assertEqual(p.document_digest(self.program), p.document_digest(altered))

    def test_distinct_scalar_categories_and_exact_literals(self):
        self.assertIs(type(t.truth(True)), t.TruthExpr)
        self.assertIs(type(t.integer(1)), t.IntegerExpr)
        self.assertIs(type(t.text("one")), t.TextExpr)
        self.assertIs(type(t.quantity("1.20", p.SECOND)), t.QuantityExpr)
        self.assertEqual(t.quantity("1.20", p.SECOND).to_source().value.amount, "1.2")
        self.assertEqual(t.unknown().to_source(), p.UNKNOWN)
        for invoke in (lambda: t.integer(True), lambda: t.truth(1), lambda: t.text(1),
                       lambda: t.quantity(0.1, p.SECOND)):
            with self.subTest(invoke=invoke), self.assertRaises(TypeError):
                invoke()

    def test_python_truth_and_equality_never_silently_consume_symbols(self):
        value, event = t.truth(True), t.truth(True).rising()
        for expression in (value, t.integer(1), t.text("x"), t.quantity("1", p.SECOND), event):
            for invoke in (lambda: bool(expression), lambda: expression == expression, lambda: expression != expression):
                with self.subTest(category=type(expression).__name__), self.assertRaises(t.TypedAuthoringError):
                    invoke()
        self.assertEqual(value.eq(t.truth(False)).to_source().op, "eq")
        self.assertEqual(value.ne(t.truth(False)).to_source().op, "ne")

    def test_events_never_enter_scalar_logic_assignment_or_effect_arguments(self):
        event = t.truth_observation(self.observation).updated
        truth_state = t.truth_state(replace(self.state, value_type=p.TRUTH, initial=False))
        for invoke in (lambda: t.guard(event), lambda: t.trigger(t.truth(True)),
                       lambda: t.all_of(t.truth(True), event), lambda: t.rising(event),
                       lambda: t.argument("x", event), lambda: truth_state.assign(event),
                       lambda: truth_state.with_reset(event), lambda: t.TruthExpr(event.to_source()),
                       lambda: t.Observation(self.observation, t.EventExpr)):
            with self.subTest(invoke=invoke), self.assertRaises(TypeError):
                invoke()
        forged = p.Expr("eq", p.TRUTH, (event.to_source(), event.to_source()))
        with self.assertRaisesRegex(TypeError, "matching scalar"):
            t.TruthExpr(forged)
        with self.assertRaisesRegex(TypeError, "event value"):
            t.Effect(replace(self.effect, parameters=(p.Argument("bad", event.to_source()),)))

    def test_mixed_scalar_and_quantity_references_reject(self):
        for invoke in (lambda: t.integer(1).eq(t.truth(True)), lambda: t.integer(1) + t.text("x"),
                       lambda: t.quantity("1", p.SECOND).lt(t.integer(1))):
            with self.subTest(invoke=invoke), self.assertRaises(TypeError):
                invoke()
        rate = p.Unit("per_s", "count/time", "output_rate", reference="executor")
        variants = (replace(rate, dimension="count"), replace(rate, quantity_kind="event_rate"),
                    replace(rate, reference="population"))
        for unit in variants:
            with self.subTest(unit=unit), self.assertRaises(TypeError):
                t.quantity("1", rate).le(t.quantity("1", unit))
        summed = t.quantity("1", p.MINUTE) + t.quantity("1", p.SECOND)
        self.assertEqual(summed.unit, p.MINUTE)
        self.assertEqual(summed.to_source().args[1].value.unit, p.SECOND)
        for scale in ("0", "-1", "NaN", "Infinity", "1e2000"):
            with self.subTest(scale=scale), self.assertRaises((TypeError, ValueError)):
                t.quantity("1", replace(rate, scale=scale))

    def test_mutated_source_is_rechecked_before_traversal_or_builder_mutation(self):
        source = p.Expr("literal", p.TRUTH, value=True)
        truth = t.TruthExpr(source)
        event = t.truth(True).rising()
        object.__setattr__(source, "args", (source,))
        builder = p.ProgramBuilder("new", semantics=self.program.semantics)
        for invoke in (lambda: t.guard(truth), lambda: truth.to_source(),
                       lambda: t.rule(builder, "cyclic", executor=p.Role("executor", ()), on=event,
                           when=truth, unknown="defer", effects=(),
                           arbitration=p.Arbitration("exclusive", "reject", "reject", "forbidden", "none"))):
            with self.subTest(invoke=invoke), self.assertRaises(ValueError):
                invoke()
        self.assertEqual(builder.snapshot().declarations, ())
        scalar_source = p.literal(1)
        assignment = t.integer_state(self.state).assign(t.IntegerExpr(scalar_source))
        object.__setattr__(scalar_source, "value_type", p.EVENT)
        with self.assertRaises(TypeError):
            assignment.to_source()
        effect_source = replace(self.effect)
        effect = t.Effect(effect_source)
        object.__setattr__(effect_source, "parameters", (p.Argument("event", event.to_source()),))
        with self.assertRaises(TypeError):
            effect.to_source()

    def test_observation_state_and_parameter_handles_preserve_nominal_records(self):
        observed = t.truth_observation(self.observation)
        self.assertIs(observed.to_source(), self.observation)
        self.assertEqual(observed.value.to_source().ref, p.ref(self.observation))
        self.assertEqual(observed.updated.to_source(), self.observation.updated)
        counter = t.integer_state(self.state)
        self.assertIs(counter.to_source(), self.state)
        self.assertEqual(counter.assign(t.integer(2)).to_source(), p.Assignment(p.ref(self.state), p.literal(2)))
        maximum = t.integer_parameter(self.records["maximum"])
        self.assertEqual(maximum.value.to_source().ref, p.ref(self.records["maximum"]))
        for invoke in (lambda: t.truth_observation(self.state), lambda: t.text_state(self.state),
                       lambda: t.truth_parameter(self.records["maximum"]),
                       lambda: t.truth_state(replace(self.state, value_type=p.TRUTH, initial=1)),
                       lambda: t.integer_parameter(replace(self.records["maximum"], value="bad"))):
            with self.subTest(invoke=invoke), self.assertRaises(TypeError):
                invoke()

    def test_effect_lifecycle_phases_remain_explicit_events(self):
        handle = t.Effect(self.effect)
        self.assertIs(handle.to_source(), self.effect)
        for phase in ("requested", "initiated", "completed", "outcome", "failed", "timed_out",
                      "cancel_requested", "cancel_acknowledged", "ceased"):
            with self.subTest(phase=phase):
                self.assertEqual(handle.event(phase).to_source(), self.effect.event(phase))
        for value, phase in ((handle.requested, "requested"), (handle.initiated, "initiated"),
                             (handle.completed, "completed"), (handle.failed, "failed"),
                             (handle.timed_out, "timed_out")):
            self.assertEqual(value.to_source().value, phase)
        with self.assertRaises(TypeError):
            handle.event("succeeded")

    def test_distinct_subjects_and_builder_owners_cannot_be_combined(self):
        original = t.truth_observation(self.observation).value
        another = t.truth_observation(replace(self.observation, subject=p.Ref("other", "Subject"))).value
        with self.assertRaisesRegex(TypeError, "Mixed observed subjects"):
            original & another
        other_program = complete_policy()
        foreign = t.truth_observation(next(item for item in other_program.declarations if item.id == "signal")).value
        with self.assertRaisesRegex(TypeError, "different programs"):
            original & foreign
        self.assertIs(original.to_source().ref._policy_owner, self.observation._policy_owner)
        builder = p.ProgramBuilder("another", semantics=self.program.semantics)
        with self.assertRaises(p.AuthoringError):
            builder.add(p.Rule("foreign", p.ref(self.records["executor"]), self.observation.updated,
                               t.guard(original), "defer", (p.ref(self.effect),)))

    def test_immutable_reset_copy_preserves_ownership_and_original(self):
        handle = t.integer_state(self.state)
        reset = handle.with_reset(t.truth(True))
        self.assertIsNone(handle.to_source().reset)
        self.assertEqual(reset.to_source().reset, p.TRUE)
        self.assertIs(reset.to_source()._policy_owner, self.state._policy_owner)
        with self.assertRaises(FrozenInstanceError):
            handle._source = reset.to_source()
        with self.assertRaises(FrozenInstanceError):
            handle.value._source = p.literal(4)

    def test_wrapping_source_does_not_establish_contextual_access(self):
        # Evaluator access is preserved, never rewritten into cell access. Its
        # forbidden use in cellular behavior remains the full source check's job.
        external = replace(self.observation, access="external_evaluator")
        handle = t.truth_observation(external)
        self.assertEqual(handle.to_source().access, "external_evaluator")
        altered = replace(self.program, declarations=tuple(external if item.id == external.id else item
                                                          for item in self.program.declarations))
        report = p.check(altered)
        self.assertEqual(report.status, "invalid")
        self.assertIn("observation_access", {item.code for item in report.diagnostics})

    def test_invalid_rule_does_not_mutate_builder(self):
        builder = p.ProgramBuilder("new", semantics=self.program.semantics)
        executor = p.Role("executor", ())
        event = t.truth(True).rising()
        before = builder.snapshot()
        for invoke in (
            lambda: t.rule(builder, "wrong", executor=executor, on=t.truth(True), when=t.truth(True),
                unknown="defer", effects=(), arbitration=p.Arbitration("exclusive", "reject", "reject", "forbidden", "none")),
            lambda: t.rule(builder, "wrong", executor=executor, on=event, when=t.truth(True),
                unknown="defer", effects=(), arbitration=p.Arbitration("bad", "reject", "reject", "forbidden", "none")),
            lambda: t.rule(builder, "wrong", executor=self.effect, on=event, when=t.truth(True),
                unknown="defer", effects=(), arbitration=p.Arbitration("exclusive", "reject", "reject", "forbidden", "none")),
        ):
            with self.subTest(invoke=invoke), self.assertRaises((TypeError, ValueError)):
                invoke()
            self.assertEqual(builder.snapshot(), before)

    def test_rule_checks_effect_executor_and_affected_subject(self):
        builder = p.ProgramBuilder("new", semantics=self.program.semantics)
        arbitration = p.Arbitration("exclusive", "reject", "reject", "forbidden", "none")
        signal = t.truth_observation(self.observation)
        for effect in (replace(self.effect, executor=p.Ref("someone_else", "Role")),
                       replace(self.effect, subject=p.Ref("unrelated", "Subject"))):
            with self.subTest(effect=effect), self.assertRaises(TypeError):
                t.rule(builder, "wrong", executor=self.records["executor"], on=signal.updated,
                    when=signal.value, unknown="defer", effects=(t.Effect(effect),), arbitration=arbitration)
        self.assertEqual(builder.snapshot().declarations, ())

    def test_typed_transition_preserves_source_and_checks_endpoints(self):
        builder = p.ProgramBuilder("machine_example", semantics=self.program.semantics)
        machine = p.Machine("machine", p.Ref("executor", "Role"), p.Scope("executor", p.Ref("executor", "Role")),
            ("ready", "done", "unknown"), "ready", ("done",), "executor",
            p.Arbitration("exclusive", "reject", "reject", "forbidden", "none"))
        event = t.truth(True).rising()
        source = t.transition(builder, "step", machine=machine, source="ready", destination="done",
            on=event, when=t.unknown(), unknown="transition", unknown_target="unknown")
        self.assertEqual(source, p.Transition("step", p.ref(machine), "ready", "done", event.to_source(),
                                              p.UNKNOWN, "transition", unknown_target="unknown"))
        before = builder.snapshot()
        for arguments in ({"source": "missing", "destination": "done", "unknown": "defer"},
                          {"source": "ready", "destination": "done", "unknown": "transition", "unknown_target": "missing"}):
            with self.subTest(arguments=arguments), self.assertRaises(TypeError):
                t.transition(builder, "invalid", machine=machine, on=event, when=t.truth(True), **arguments)
        self.assertEqual(builder.snapshot(), before)


@unittest.skipUnless(importlib.util.find_spec("mypy") is not None, "mypy is optional local static tooling")
class PolicyTypedStaticTests(unittest.TestCase):
    def test_positive_program_and_exact_negative_diagnostic_census(self):
        environment = {**os.environ, "MYPYPATH": str(ROOT / "src")}
        command = [sys.executable, "-B", "-m", "mypy", "--strict", "--follow-imports=silent",
                   "--no-incremental", "--cache-dir=/dev/null", "--no-error-summary", "--no-pretty"]
        positive = subprocess.run([*command, "src/biocompiler/policy/typed.py", "tests/typecheck/policy_typed_positive.py"],
            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=60)
        self.assertEqual(positive.returncode, 0, positive.stdout + positive.stderr)
        negative_path = Path("tests/typecheck/policy_typed_negative.py")
        expected = []
        for line, text in enumerate((ROOT / negative_path).read_text().splitlines(), 1):
            marker = re.search(r"# E: ([a-z-]+)$", text)
            if marker:
                expected.append((line, marker.group(1)))
        self.assertEqual(len(expected), 17)
        negative = subprocess.run([*command, str(negative_path)], cwd=ROOT, env=environment,
                                  capture_output=True, text=True, timeout=60)
        self.assertEqual(negative.returncode, 1, negative.stdout + negative.stderr)
        found = []
        for diagnostic in negative.stdout.splitlines():
            match = re.fullmatch(re.escape(str(negative_path)) + r":(\d+): error: .*  \[([a-z-]+)\]", diagnostic)
            self.assertIsNotNone(match, diagnostic)
            found.append((int(match.group(1)), match.group(2)))
        self.assertEqual(found, expected, negative.stdout + negative.stderr)
        self.assertFalse(negative.stderr, negative.stderr)


if __name__ == "__main__":
    unittest.main()
