"""Independent literal API expansions, not operational or material execution."""
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import inspect
import unittest

import biocompiler.policy as p


BUNDLE = p.SemanticBundle("builder_literals", "1")
SECOND = p.Unit("s", "time", "duration", "1")
CONTRACT = p.DefinitionRef("supplied.contract", "1", "a" * 64)
ARBITRATION = p.Arbitration("exclusive", "reject", "reject", "forbidden", "none")
ROLE = p.Ref("executor", "Role")
TARGET = p.Ref("target", "Subject")
EVENT = p.Expr("updated", p.EVENT, ref=p.Ref("signal", "Observation"), scope=TARGET)
TRUE = p.Expr("literal", p.TRUTH, value=True)
LIFECYCLE = p.EffectLifecycle("initiation", "continue", "defer", "unsupported", "feedback", "feedback", CONTRACT)


class PolicyBuilderLiteralTests(unittest.TestCase):
    def test_constructor_namespace_mutation_and_snapshot_authority(self):
        builder = p.ProgramBuilder("original", semantics=BUNDLE)
        self.assertEqual(builder.snapshot(), p.PolicyDraft("original", BUNDLE, (), (), ()))
        snapshot = builder.snapshot()
        builder.name = "renamed"
        builder.semantics = p.SemanticBundle("second", "2")
        self.assertEqual(snapshot, p.PolicyDraft("original", BUNDLE, (), (), ()))
        self.assertEqual(builder.snapshot(), p.PolicyDraft("renamed", p.SemanticBundle("second", "2"), ()))
        with builder.namespace("outer"):
            self.assertEqual(builder.qualified("value"), "outer/value")
            with self.assertRaisesRegex(RuntimeError, "leave nested scope"):
                with builder.namespace("inner"):
                    self.assertEqual(builder.qualified("value"), "outer/inner/value")
                    raise RuntimeError("leave nested scope")
            self.assertEqual(builder.qualified("value"), "outer/value")
        self.assertEqual(builder.qualified("value"), "value")
        for invalid in ("", "1leading", "has space"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                p.ProgramBuilder(invalid, semantics=BUNDLE)
        with self.assertRaises(ValueError):
            with builder.namespace("bad name"):
                self.fail("Invalid namespace entered")
        self.assertEqual(builder.qualified("value"), "value")

    def test_named_convenience_defaults_and_encounter_order(self):
        builder = p.ProgramBuilder("defaults", semantics=BUNDLE)
        with builder.namespace("scope"):
            executor_line = inspect.currentframe().f_lineno + 1
            executor = builder.executor("executor", requires=(CONTRACT,))
            subject_line = inspect.currentframe().f_lineno + 1
            subject = builder.subject("stable", entity_kind="cell", identity_scope="stable", executor=executor)
            encounter_line = inspect.currentframe().f_lineno + 1
            encounter = builder.encounter("encounter", executor=executor, contract=CONTRACT)
            clock_line = inspect.currentframe().f_lineno + 1
            clock = builder.clock("clock", basis="logical", resolution=p.Quantity("0.25", SECOND))
            observed_line = inspect.currentframe().f_lineno + 1
            observed = builder.observe("signal", observer=executor, subject=subject, value_type=p.TRUTH,
                contract=CONTRACT, clock=clock, access="cell", coverage="sampled", coherence="frame", freshness=p.Quantity("2", SECOND))
            effect_line = inspect.currentframe().f_lineno + 1
            effect = builder.effect("effect", contract=CONTRACT, executor=executor, subject=subject, lifecycle=LIFECYCLE)
            rule_line = inspect.currentframe().f_lineno + 1
            rule = builder.rule("rule", executor=executor, on=EVENT, when=TRUE, unknown="defer", effects=(), arbitration=ARBITRATION)
            machine_line = inspect.currentframe().f_lineno + 1
            machine = builder.machine("machine", executor=executor, scope=p.Scope("executor", p.Ref("scope/executor", "Role")),
                states=("ready", "done"), initial="ready", terminal=("done",), lifetime="executor", arbitration=ARBITRATION)
            transition_line = inspect.currentframe().f_lineno + 1
            transition = builder.transition("advance", machine=machine, source="ready", destination="done", on=EVENT)
        # Every default, reference and expansion order is authored here; no helper
        # under test is called to build these expected records.
        er = p.Ref("scope/executor", "Role")
        sr = p.Ref("scope/stable", "Subject")
        expected = (
            p.Role("scope/executor", (CONTRACT,), None, False),
            p.Subject("scope/stable", "cell", "stable", er, None, None),
            p.Subject("scope/encounter/target", "cell", "encounter", er, p.Ref("scope/encounter", "Encounter"), None),
            p.Encounter("scope/encounter", er, p.Ref("scope/encounter/target", "Subject"), CONTRACT, "contact_loss"),
            p.Clock("scope/clock", "logical", p.Quantity("0.25", SECOND), "atomic_batch"),
            p.Observation("scope/signal", er, sr, p.TRUTH, CONTRACT, p.Ref("scope/clock", "Clock"), "cell", "sampled", "frame",
                p.Quantity("2", SECOND), None, ("missing", "stale", "invalid", "conflicting")),
            p.Effect("scope/effect", CONTRACT, er, sr, LIFECYCLE, (), None, None, ()),
            p.Rule("scope/rule", er, EVENT, TRUE, "defer", (), (), ARBITRATION, None, ()),
            p.Machine("scope/machine", er, p.Scope("executor", er), ("ready", "done"), "ready", ("done",), "executor", ARBITRATION),
            p.Transition("scope/advance", p.Ref("scope/machine", "Machine"), "ready", "done", EVENT, TRUE, "defer", (), (), None, ()),
        )
        self.assertEqual(builder.snapshot().declarations, expected)
        self.assertEqual((executor, subject, encounter, clock, observed, effect, rule, machine, transition),
                         (expected[0], expected[1], expected[3], *expected[4:]))
        spans = builder.snapshot().source_map
        self.assertEqual(tuple(s.declaration_id for s in spans), tuple(d.id for d in expected))
        self.assertEqual(spans[2:4], (p.SourceSpan("scope/encounter/target", __file__, encounter_line, 0, "scope"),
                                     p.SourceSpan("scope/encounter", __file__, encounter_line, 0, "scope")))
        self.assertEqual(spans, tuple(p.SourceSpan(declaration.id, __file__, line, 0, "scope")
            for declaration, line in zip(expected, (executor_line, subject_line, encounter_line, encounter_line,
                clock_line, observed_line, effect_line, rule_line, machine_line, transition_line))))

    def test_optional_authority_fields_are_preserved_literal(self):
        builder = p.ProgramBuilder("options", semantics=BUNDLE)
        spatial, population = p.Ref("region", "SpatialScope"), p.Ref("population", "Subject")
        effect_ref, message = p.Ref("effect", "Effect"), p.Ref("message", "Message")
        assignment = p.Assignment(p.Ref("memory", "StateStore"), TRUE)
        parameters = (p.Argument("product", p.Expr("literal", p.TEXT, value="cargo")),)
        executor_line = inspect.currentframe().f_lineno + 1
        executor = builder.executor("executor", requires=(), population=population, lineage_role=True)
        subject_line = inspect.currentframe().f_lineno + 1
        subject = builder.subject("bound", entity_kind="cell", identity_scope="bound", executor=ROLE, domain=population)
        encounter_line = inspect.currentframe().f_lineno + 1
        encounter = builder.encounter("encounter", executor=ROLE, contract=CONTRACT, termination="explicit_event")
        observation_line = inspect.currentframe().f_lineno + 1
        observation = builder.observe("signal", observer=ROLE, subject=TARGET, value_type=p.TRUTH, contract=CONTRACT,
            clock=p.Ref("clock", "Clock"), access="external_evaluator", coverage="event", coherence="separate", freshness=p.Quantity("3", SECOND), spatial_scope=spatial)
        effect_line = inspect.currentframe().f_lineno + 1
        effect = builder.effect("effect", contract=CONTRACT, executor=ROLE, subject=TARGET, lifecycle=LIFECYCLE,
            parameters=parameters, spatial_scope=spatial, relationship=CONTRACT, resources=(CONTRACT,))
        rule_line = inspect.currentframe().f_lineno + 1
        rule = builder.rule("rule", executor=ROLE, on=EVENT, when=TRUE, unknown="transition", effects=(effect_ref,),
            arbitration=ARBITRATION, assignments=(assignment,), unknown_target="hold", emissions=(message,))
        transition_line = inspect.currentframe().f_lineno + 1
        transition = builder.transition("transition", machine=p.Ref("machine", "Machine"), source="start", destination="stop",
            on=EVENT, when=p.Expr("literal", p.TRUTH, value="unknown"), unknown="transition", effects=(effect_ref,),
            assignments=(assignment,), unknown_target="hold", emissions=(message,))
        expected = (
            p.Role("executor", (), population, True), p.Subject("bound", "cell", "bound", ROLE, None, population),
            p.Encounter("encounter", ROLE, p.Ref("encounter/target", "Subject"), CONTRACT, "explicit_event"),
            p.Observation("signal", ROLE, TARGET, p.TRUTH, CONTRACT, p.Ref("clock", "Clock"), "external_evaluator", "event", "separate", p.Quantity("3", SECOND), spatial),
            p.Effect("effect", CONTRACT, ROLE, TARGET, LIFECYCLE, parameters, spatial, CONTRACT, (CONTRACT,)),
            p.Rule("rule", ROLE, EVENT, TRUE, "transition", (effect_ref,), (assignment,), ARBITRATION, "hold", (message,)),
            p.Transition("transition", p.Ref("machine", "Machine"), "start", "stop", EVENT, p.Expr("literal", p.TRUTH, value="unknown"), "transition", (effect_ref,), (assignment,), "hold", (message,)),
        )
        self.assertEqual((executor, subject, encounter, observation, effect, rule, transition), expected)
        self.assertEqual(builder.snapshot().declarations, expected[:2] +
                         (p.Subject("encounter/target", "cell", "encounter", ROLE, p.Ref("encounter", "Encounter")),) + expected[2:])
        ordered = expected[:2] + (p.Subject("encounter/target", "cell", "encounter", ROLE, p.Ref("encounter", "Encounter")),) + expected[2:]
        self.assertEqual(builder.snapshot().source_map, tuple(p.SourceSpan(item.id, __file__, line, 0, None)
            for item, line in zip(ordered, (executor_line, subject_line, encounter_line, encounter_line,
                observation_line, effect_line, rule_line, transition_line))))
        # Literal expansion can preserve unsupported/unresolved declarations;
        # construction here is deliberately not a source or runtime acceptance.

    def test_copying_methods_only_change_own_id(self):
        builder = p.ProgramBuilder("copies", semantics=BUNDLE)
        state = p.StateStore("memory", p.TRUTH, p.Scope("executor", ROLE), "unknown", 2, "reject", "executor", TRUE, "reset", contract=CONTRACT)
        channel = p.Channel("channel", ROLE, (p.Ref("receiver", "Role"),), p.TEXT, CONTRACT, p.Scope("executor", ROLE),
            "causal", "permitted", "deduplicate", "required", "bounded", 3, p.Quantity("2", SECOND), p.Ref("region", "SpatialScope"))
        requirement = p.Requirement("safety", "safety", "Retain all fields", p.Scope("executor", ROLE), TRUE, horizon=p.Quantity("5", SECOND),
            assumptions=("supplied",), applies_to=(ROLE,), contract=CONTRACT, trigger=EVENT, clock=p.Ref("clock", "Clock"))
        with builder.namespace("nested"):
            line = inspect.currentframe().f_lineno + 1
            actual = (builder.state(state), builder.channel(channel), builder.require(requirement))
        expected = (
            p.StateStore("nested/memory", p.TRUTH, p.Scope("executor", ROLE), "unknown", 2, "reject", "executor", TRUE, "reset", None, CONTRACT, None),
            p.Channel("nested/channel", ROLE, (p.Ref("receiver", "Role"),), p.TEXT, CONTRACT, p.Scope("executor", ROLE), "causal", "permitted", "deduplicate", "required", "bounded", 3, p.Quantity("2", SECOND), p.Ref("region", "SpatialScope")),
            p.Requirement("nested/safety", "safety", "Retain all fields", p.Scope("executor", ROLE), TRUE, None, None, None, None, p.Quantity("5", SECOND), ("supplied",), (ROLE,), CONTRACT, EVENT, p.Ref("clock", "Clock")),
        )
        self.assertEqual(actual, expected)
        self.assertEqual(builder.snapshot().declarations, expected)
        self.assertEqual(builder.snapshot().source_map, tuple(p.SourceSpan(item.id, __file__, line, 0, "nested") for item in expected))
        self.assertEqual((state.id, channel.id, requirement.id), ("memory", "channel", "safety"))
        self.assertEqual(actual[0].scope.subject, ROLE)  # No invented nested/executor reference.
        self.assertEqual(actual[1].sender, ROLE)
        self.assertEqual(actual[2].applies_to, (ROLE,))
        self.assertNotEqual(actual, (state, channel, requirement))

    def test_add_ref_ownership_errors_are_atomic(self):
        builder = p.ProgramBuilder("add", semantics=BUNDLE)
        value = p.Role("literal_id", ())
        with builder.namespace("does_not_rewrite_add"):
            line = inspect.currentframe().f_lineno + 1
            self.assertIs(builder.add(value), value)
        self.assertEqual(builder.snapshot().declarations, (p.Role("literal_id", ()),))
        self.assertEqual(builder.snapshot().source_map, (p.SourceSpan("literal_id", __file__, line, 0, "does_not_rewrite_add"),))
        reference = p.ref(value)
        self.assertEqual(reference, p.Ref("literal_id", "Role"))
        self.assertIs(p.ref(reference), reference)
        self.assertNotIn("_policy_owner", p.to_data(reference))
        before = builder.snapshot()
        for bad in (p.Role("literal_id", ()), p.Role("bad name", ())):
            with self.assertRaises(p.AuthoringError):
                builder.add(bad)
            self.assertEqual(builder.snapshot(), before)
        with self.assertRaises(TypeError):
            builder.add(p.SourceSpan("literal_id", __file__, 1))
        self.assertEqual(builder.snapshot(), before)
        other = p.ProgramBuilder("other", semantics=BUNDLE)
        for bad in (value, p.Subject("foreign", "cell", "stable", reference)):
            with self.assertRaisesRegex(p.AuthoringError, "Cross-program"):
                other.add(bad)
            self.assertEqual(other.snapshot(), p.PolicyDraft("other", BUNDLE, ()))
        with self.assertRaisesRegex(TypeError, "Only named"):
            p.ref(TRUE)
        # Explicit data import is a fresh declaration, not implicit ownership transfer.
        restored = p.from_data(p.to_data(value), p.Role)
        self.assertEqual(restored, value)
        self.assertIs(other.add(restored), restored)
        with self.assertRaises(FrozenInstanceError):
            restored.id = "changed"

    def test_hole_resolve_has_no_implicit_rebinding(self):
        builder = p.ProgramBuilder("holes", semantics=BUNDLE)
        with builder.namespace("outer"):
            slot = builder.hole("slot", expected="Role", question="Which executor?")
        self.assertEqual(slot, p.Hole("outer/slot", "Role", "Which executor?"))
        snapshot = builder.snapshot()
        with self.assertRaises(KeyError):
            builder.resolve("slot", p.Role("unused", ()))
        self.assertEqual(builder.snapshot(), snapshot)
        with self.assertRaisesRegex(p.AuthoringError, "Cannot freeze incomplete"):
            builder.freeze()
        with self.assertRaises(p.AuthoringError):
            with builder.namespace("outer"):
                builder.hole("slot", expected="Role", question="Duplicate")
        with self.assertRaises(p.AuthoringError):
            builder.resolve("outer/slot", p.Role("bad name", ()))
        self.assertEqual(builder.snapshot(), snapshot)
        # Resolve uses the selected hole identity, then add's literal declaration
        # identity. It does not rename the supplied declaration or rewrite refs.
        line = inspect.currentframe().f_lineno + 1
        builder.resolve("outer/slot", p.Role("chosen_executor", ()))
        self.assertEqual(builder.snapshot().holes, ())
        self.assertEqual(builder.snapshot().declarations, (p.Role("chosen_executor", ()),))
        self.assertEqual(snapshot.holes, (slot,))
        self.assertEqual(builder.snapshot().source_map, (p.SourceSpan("chosen_executor", __file__, line, 0, None),))

    def test_freeze_keeps_exact_declarations_and_caller_source(self):
        builder = p.ProgramBuilder("frozen", semantics=BUNDLE)
        line = inspect.currentframe().f_lineno + 1
        builder.executor("executor", requires=())
        expected_span = p.SourceSpan("executor", __file__, line, 0, None)
        expected = p.PolicyProgram("frozen", BUNDLE, (p.Role("executor", ()),), (expected_span,))
        self.assertEqual(builder.snapshot(), p.PolicyDraft("frozen", BUNDLE, expected.declarations, (), (expected_span,)))
        frozen = builder.freeze()
        self.assertEqual(frozen, expected)
        self.assertEqual(p.loads(p.dumps(frozen), p.PolicyProgram), expected)
        report = p.check(frozen)
        self.assertEqual((report.status, report.semantic_status, report.target_status), ("complete", "unassessed", "unassessed"))
        builder.name = "later"
        builder.add(p.Parameter("parameter", p.INTEGER, 4))
        self.assertEqual(frozen, expected)
        self.assertEqual(len(builder.snapshot().declarations), 2)

    def test_compare_protocol_and_exact_value_stages(self):
        one = p.Expr("literal", p.INTEGER, value=1)
        two = p.Expr("literal", p.INTEGER, value=2)
        expected = p.Expr("lt", p.TRUTH, (one, two))
        self.assertEqual(one.compare("lt", 2), expected)
        self.assertEqual(p.compare(one, "lt", 2), expected)
        incompatible = one.compare("eq", "text")  # Construction deliberately retains typed source.
        self.assertEqual(incompatible, p.Expr("eq", p.TRUTH, (one, p.Expr("literal", p.TEXT, value="text"))))
        with self.assertRaisesRegex(TypeError, "Comparison requires matching"):
            p.compare(one, "eq", "text")
        original = p.PolicyProgram("comparison", BUNDLE, (p.Role("executor", ()),
            p.Requirement("comparison", "safety", "Declared comparison", p.Scope("executor", ROLE), incompatible)))
        errors = p.check(original).errors
        self.assertEqual([(e.code, e.path) for e in errors], [("incompatible_operands", "/declarations/1/condition")])
        self.assertIs(one == p.Expr("literal", p.INTEGER, value=1), True)  # Python record equality.
        for condition in (p.TRUE, p.FALSE, p.UNKNOWN):
            with self.subTest(condition=condition), self.assertRaises(TypeError):
                bool(condition)
        self.assertEqual(p.TRUE & p.UNKNOWN, p.Expr("all", p.TRUTH, (TRUE, p.Expr("literal", p.TRUTH, value="unknown"))))
        self.assertEqual(p.FALSE | p.TRUE, p.Expr("any", p.TRUTH, (p.Expr("literal", p.TRUTH, value=False), TRUE)))
        self.assertEqual(~p.TRUE, p.Expr("not", p.TRUTH, (TRUE,)))
        self.assertEqual(p.quantity(Decimal("0.1250"), SECOND), p.Quantity("0.125", SECOND))
        self.assertEqual(p.from_float(0.125, SECOND), p.Quantity("0.125", SECOND))
        for wrong in (True, 0.125):
            with self.subTest(wrong=wrong), self.assertRaises(TypeError):
                p.quantity(wrong, SECOND)
        milliseconds = p.Unit("ms", "time", "duration", "0.001")
        self.assertTrue(p.values.compatible(p.TypeSpec("quantity", SECOND), p.TypeSpec("quantity", milliseconds)))
        self.assertFalse(p.values.compatible(p.TypeSpec("quantity", SECOND), p.TypeSpec("quantity", replace(milliseconds, reference="other"))))


if __name__ == "__main__":
    unittest.main()
