"""Literal authoring expansions only; no policy execution or module linking."""
from dataclasses import replace
import inspect
import unittest

import biocompiler.policy as p
from biocompiler.policy import patterns


# This is an explicit public-pattern census, not a discovered expected result.
PATTERNS = {
    "context_gate": ("respond",),
    "once_per_scope": ("seen", "respond"),
    "ordered_effects": ("stages", "start", "handoff", "completed", "first_failed", "second_failed"),
    "bounded_response": ("count", "respond"),
    "persistence_gate": ("respond",),
    "population_handoff": ("send", "receive"),
}
SECOND = p.Unit("s", "time", "duration", "1")
ARBITRATION = p.Arbitration("exclusive", "reject", "reject", "forbidden", "none")


def semantic_bundle():
    return p.SemanticBundle("pattern_literals", "1", (
        p.SemanticDefinition("literal.interface", "1", "interface", "Supplied executor interface."),
        p.SemanticDefinition("literal.encounter", "1", "encounter", "Explicit encounter identity."),
        p.SemanticDefinition("literal.observation", "1", "observation", "Supplied truth evidence.", result=p.TRUTH),
        p.SemanticDefinition("literal.effect", "1", "operation", "Abstract attempt with separate feedback."),
        p.SemanticDefinition("literal.lifecycle", "1", "lifecycle", "Correlated attempt outcomes."),
        p.SemanticDefinition("literal.transport", "1", "transport", "Supplied addressed message contract."),
    ))


def inputs(prefix, pattern, *, lifetime="encounter"):
    """Original authored inputs, made afresh for actual and manual programs."""
    contracts = {definition.id: definition.ref for definition in semantic_bundle().definitions}
    executor = p.Ref(prefix + "/executor", "Role")
    encounter_target = p.Ref(prefix + "/target", "Subject")
    target = p.Ref(prefix + "/stable_target", "Subject") if lifetime == "persistent" else encounter_target
    encounter = p.Ref(prefix + "/encounter", "Encounter")
    clock = p.Ref(prefix + "/clock", "Clock")
    signal = p.Ref(prefix + "/signal", "Observation")
    exclusion = p.Ref(prefix + "/exclusion", "Observation")
    lifecycle = p.EffectLifecycle("initiation", "continue", "defer", "unsupported",
        "feedback", "feedback", contracts["literal.lifecycle"], p.Quantity("9", SECOND))
    first = p.Effect(prefix + "/first", contracts["literal.effect"], executor, target, lifecycle)
    second = p.Effect(prefix + "/second", contracts["literal.effect"], executor, target, lifecycle)
    declarations = (
        p.Role(executor.id, (contracts["literal.interface"],)),
        p.Subject(encounter_target.id, "cell", "encounter", executor, encounter),
        p.Encounter(encounter.id, executor, encounter_target, contracts["literal.encounter"], "explicit_event"),
        p.Clock(clock.id, "logical", p.Quantity("0.25", SECOND)),
        p.Observation(signal.id, executor, target, p.TRUTH, contracts["literal.observation"],
            clock, "cell", "continuous", prefix + "/frame", p.Quantity("2", SECOND)),
        p.Observation(exclusion.id, executor, target, p.TRUTH, contracts["literal.observation"],
            clock, "cell", "continuous", prefix + "/frame", p.Quantity("2", SECOND)),
        first, second,
    )
    scope = p.Scope("encounter", encounter)
    if pattern == "bounded_response" or lifetime == "executor":
        scope = p.Scope("executor", executor)
    elif lifetime == "persistent":
        stable = p.Ref(prefix + "/stable_target", "Subject")
        declarations += (p.Subject(stable.id, "cell", "stable", executor),)
        scope = p.Scope("target", stable)
    result = dict(executor=executor, target=target, clock=clock, scope=scope,
        first=first, second=second, effect=p.Ref(first.id, "Effect"),
        on=p.Expr("updated", p.EVENT, ref=signal, scope=target),
        permitted=p.Expr("observe", p.TRUTH, ref=signal, scope=target),
        exclusion=p.Expr("observe", p.TRUTH, ref=exclusion, scope=target))
    if pattern == "population_handoff":
        population = p.Ref(prefix + "/population", "Subject")
        receiver = p.Ref(prefix + "/receiver", "Role")
        channel = p.Ref(prefix + "/channel", "Channel")
        # Correlation intentionally differs from the message subject.
        message = p.Message(prefix + "/message", channel, executor, target, encounter,
            p.Expr("literal", p.TEXT, value="ready"))
        receiver_effect = p.Ref(prefix + "/receiver_effect", "Effect")
        declarations += (
            p.Subject(population.id, "population", "aggregate"),
            p.Role(receiver.id, (contracts["literal.interface"],), population),
            p.Channel(channel.id, executor, (receiver,), p.TEXT, contracts["literal.transport"],
                p.Scope("population", population), "fifo", "permitted", "deduplicate",
                "required", "bounded", 3, p.Quantity("5", SECOND)),
            message,
            p.Effect(receiver_effect.id, contracts["literal.effect"], receiver, target,
                lifecycle, relationship=contracts["literal.transport"]),
        )
        result.update(receiver=receiver, message=message, receiver_effect=receiver_effect)
    return declarations, result


def manual_expansion(pattern, prefix, *, maximum=3, lifetime="encounter", duration="2.5", sender_count=1, arbitration=ARBITRATION, pattern_name="pattern"):
    """Expected records are literal specifications, never builder/helper output.

    In particular, no logic/time/ref or event convenience method is used here.
    The six branches state the intended declarations and ordering explicitly.
    """
    _, source = inputs(prefix, pattern, lifetime=lifetime)
    name = prefix + "/" + pattern_name + "/"
    executor, on, permitted = source["executor"], source["on"], source["permitted"]
    effect, scope = source["effect"], source["scope"]
    true = p.Expr("literal", p.TRUTH, value=True)
    if pattern == "context_gate":
        return (p.Rule(name + "respond", executor, on,
            p.Expr("all", p.TRUTH, (permitted, p.Expr("not", p.TRUTH, (source["exclusion"],)))),
            "defer", (effect,), (), arbitration),)
    if pattern == "once_per_scope":
        seen = p.Ref(name + "seen", "StateStore")
        return (
            p.StateStore(seen.id, p.TRUTH, scope, False, 1, "reject", lifetime, None, "reset"),
            p.Rule(name + "respond", executor, on, p.Expr("all", p.TRUTH, (permitted,
                p.Expr("not", p.TRUTH, (p.Expr("state", p.TRUTH, ref=seen, scope=scope.subject),)))),
                "defer", (effect,), (p.Assignment(seen, true),), arbitration),
        )
    if pattern == "ordered_effects":
        machine = p.Ref(name + "stages", "Machine")
        second = p.Ref(prefix + "/second", "Effect")
        target = source["target"]
        return (
            p.Machine(machine.id, executor, scope, ("ready", "first", "second", "completed", "failed"),
                "ready", ("completed", "failed"), "executor", arbitration),
            p.Transition(name + "start", machine, "ready", "first", on, permitted, "defer", (effect,)),
            p.Transition(name + "handoff", machine, "first", "second",
                p.Expr("effect_event", p.EVENT, value="completed", ref=effect, scope=target),
                permitted, "defer", (second,)),
            p.Transition(name + "completed", machine, "second", "completed",
                p.Expr("effect_event", p.EVENT, value="completed", ref=second, scope=target), true, "defer"),
            p.Transition(name + "first_failed", machine, "first", "failed",
                p.Expr("effect_event", p.EVENT, value="failed", ref=effect, scope=target), true, "defer"),
            p.Transition(name + "second_failed", machine, "second", "failed",
                p.Expr("effect_event", p.EVENT, value="failed", ref=second, scope=target), true, "defer"),
        )
    if pattern == "bounded_response":
        count = p.Ref(name + "count", "StateStore")
        value = p.Expr("state", p.INTEGER, ref=count, scope=scope.subject)
        return (
            p.StateStore(count.id, p.INTEGER, scope, 0, maximum, "reject", "executor", None, "reset"),
            p.Rule(name + "respond", executor, on, p.Expr("all", p.TRUTH, (permitted,
                p.Expr("lt", p.TRUTH, (value, p.Expr("literal", p.INTEGER, value=maximum))))),
                "defer", (effect,), (p.Assignment(count,
                    p.Expr("add", p.INTEGER, (value, p.Expr("literal", p.INTEGER, value=1)))),), arbitration),
        )
    if pattern == "persistence_gate":
        return (p.Rule(name + "respond", executor, on, p.Expr("holds", p.TRUTH, (permitted,),
            duration=p.Quantity(duration, SECOND), clock=source["clock"], coverage="continuous"),
            "defer", (effect,), (), arbitration),)
    if pattern == "population_handoff":
        sender_effects = (effect, p.Ref(prefix + "/second", "Effect"))[:sender_count]
        message = p.Ref(prefix + "/message", "Message")
        return (
            p.Rule(name + "send", executor, on, permitted, "defer", sender_effects,
                (), arbitration, emissions=(message,)),
            p.Rule(name + "receive", source["receiver"],
                p.Expr("message_event", p.EVENT, value="received", ref=message, scope=source["target"]),
                true, "defer", (source["receiver_effect"],), (), arbitration),
        )
    raise AssertionError("Unspecified public pattern: " + pattern)


def expand(builder, pattern, source, *, maximum=3, lifetime="encounter", duration="2.5", sender_count=1, arbitration=ARBITRATION, pattern_name="pattern"):
    common = dict(executor=source["executor"], on=source["on"], arbitration=arbitration)
    if pattern == "context_gate":
        return patterns.context_gate(builder, pattern_name, **common, evidence=source["permitted"],
            exclusion=source["exclusion"], effect=source["effect"])
    if pattern == "once_per_scope":
        return patterns.once_per_scope(builder, pattern_name, **common, scope=source["scope"],
            permitted=source["permitted"], effect=source["effect"], lifetime=lifetime)
    if pattern == "ordered_effects":
        return patterns.ordered_effects(builder, pattern_name, **common, scope=source["scope"],
            permitted=source["permitted"], first=source["first"], second=source["second"])
    if pattern == "bounded_response":
        return patterns.bounded_response(builder, pattern_name, **common, scope=source["scope"],
            permitted=source["permitted"], effect=source["effect"], maximum=maximum)
    if pattern == "persistence_gate":
        return patterns.persistence_gate(builder, pattern_name, **common, permitted=source["permitted"],
            effect=source["effect"], duration=p.Quantity(duration, SECOND), clock=source["clock"])
    if pattern == "population_handoff":
        return patterns.population_handoff(builder, pattern_name, sender=source["executor"],
            receiver=source["receiver"], on=source["on"], permitted=source["permitted"],
            message=source["message"], receiver_effect=source["receiver_effect"], arbitration=arbitration,
            sender_effects=(source["effect"], p.Ref(source["second"].id, "Effect"))[:sender_count])
    raise AssertionError("Unspecified public pattern: " + pattern)


def references(value, path=()):
    """All typed references, including their positions and complete wire fields."""
    rows = []
    if isinstance(value, dict):
        if value.get("$type") in {"Ref", "DefinitionRef"}:
            rows.append((path, value))
        for key, child in value.items():
            rows.extend(references(child, path + (key,)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(references(child, path + (index,)))
    return rows


class PolicyPatternTests(unittest.TestCase):
    def test_public_pattern_inventory_is_exact(self):
        public = {name for name, value in vars(patterns).items()
                  if not name.startswith("_") and inspect.isfunction(value)
                  and value.__module__ == patterns.__name__}
        self.assertEqual(public, set(PATTERNS))
        self.assertEqual(len(public), 6)

    def assert_expansion(self, pattern, prefixes=("one",), **options):
        builder = p.ProgramBuilder("literal_pattern", semantics=semantic_bundle())
        manual = []
        generated_origins = {}
        for prefix in prefixes:
            original, source = inputs(prefix, pattern, lifetime=options.get("lifetime", "encounter"))
            for declaration in original:
                builder.add(declaration)
            prior = builder.snapshot()
            with builder.namespace(prefix):
                returned = expand(builder, pattern, source, **options)
            expected_base, _ = inputs(prefix, pattern, lifetime=options.get("lifetime", "encounter"))
            expected = manual_expansion(pattern, prefix, **options)
            origin = prefix + "/" + options.get("pattern_name", "pattern")
            generated_origins.update({item.id: origin for item in expected})
            self.assertEqual(tuple(item.id for item in expected),
                tuple(origin + "/" + name for name in PATTERNS[pattern]))
            self.assertEqual(builder.snapshot().declarations, prior.declarations + expected)
            self.assertEqual(prior.declarations[-len(original):], expected_base)
            expected_return = (expected if pattern == "population_handoff" else
                expected[0] if pattern in {"context_gate", "ordered_effects", "persistence_gate"} else expected[1])
            self.assertEqual(returned, expected_return)
            manual.extend(expected_base + expected)
        actual = builder.freeze()
        expected_program = p.PolicyProgram("literal_pattern", semantic_bundle(), tuple(manual))
        self.assertEqual(replace(actual, source_map=()), expected_program)
        self.assertEqual(p.document_digest(actual), p.document_digest(expected_program))
        restored = p.loads(p.dumps(actual), p.PolicyProgram)
        self.assertEqual(restored, actual)
        self.assertEqual(p.dumps(restored), p.dumps(actual))
        self.assertEqual(references(p.to_data(restored)), references(p.to_data(expected_program)))
        self.assertEqual([span.declaration_id for span in restored.source_map],
            [declaration.id for declaration in expected_program.declarations])
        for span in restored.source_map:
            expected_pattern = generated_origins.get(span.declaration_id)
            self.assertEqual(span.pattern, expected_pattern)
            self.assertTrue(span.file.endswith("test_policy_patterns.py"))
            self.assertGreater(span.line, 0)
        for program in (actual, expected_program):
            report = p.check(program)
            self.assertEqual(report.status, "complete", report.diagnostics)
            self.assertEqual((report.semantic_status, report.target_status), ("unassessed", "unassessed"))
        return actual

    def test_context_gate_literal_expansion(self):
        self.assert_expansion("context_gate")

    def test_once_per_scope_literal_expansion(self):
        self.assert_expansion("once_per_scope")

    def test_ordered_effects_literal_machine_and_all_five_transitions(self):
        self.assert_expansion("ordered_effects")

    def test_bounded_response_literal_counter_guard_and_write(self):
        self.assert_expansion("bounded_response")

    def test_persistence_gate_literal_clock_duration_and_coverage(self):
        self.assert_expansion("persistence_gate")

    def test_population_handoff_literal_sender_receiver_and_message(self):
        self.assert_expansion("population_handoff")

    def test_every_pattern_keeps_two_instance_reference_graphs_disjoint(self):
        for pattern in PATTERNS:
            with self.subTest(pattern=pattern):
                program = self.assert_expansion(pattern, ("left", "right"))
                ids = [declaration.id for declaration in program.declarations]
                self.assertEqual(len(ids), len(set(ids)))
                for prefix in ("left", "right"):
                    instance = [item for item in program.declarations if item.id.startswith(prefix + "/")]
                    refs = [ref for item in instance for _, ref in references(p.to_data(item)) if ref["$type"] == "Ref"]
                    self.assertTrue(refs)
                    self.assertTrue(all(ref["id"].startswith(prefix + "/") for ref in refs))
                    for ref in refs:
                        target = next(item for item in instance if item.id == ref["id"])
                        self.assertEqual(type(target).__name__, ref["kind"])
                # Equal operation contracts never intern distinct effect instances.
                effects = [item for item in program.declarations if isinstance(item, p.Effect)]
                self.assertEqual(len({item.contract for item in effects}), 1)
                self.assertEqual(len({item.id for item in effects}), len(effects))

    def test_repeated_instance_name_rejects_without_rebinding_existing_declarations(self):
        for pattern in PATTERNS:
            with self.subTest(pattern=pattern):
                builder = p.ProgramBuilder("duplicate", semantics=semantic_bundle())
                original, source = inputs("same", pattern)
                for declaration in original:
                    builder.add(declaration)
                with builder.namespace("same"):
                    expand(builder, pattern, source)
                    before = p.to_data(builder.snapshot())
                    with self.assertRaisesRegex(p.AuthoringError, "duplicate declaration identity"):
                        expand(builder, pattern, source)
                    self.assertEqual(p.to_data(builder.snapshot()), before)

    def test_every_pattern_preserves_an_alternate_supplied_name(self):
        for pattern in PATTERNS:
            with self.subTest(pattern=pattern):
                self.assert_expansion(pattern, pattern_name="alternate/gate")

    def test_every_pattern_retains_supplied_nondefault_arbitration(self):
        arbitration = p.Arbitration("concurrent", "nondeterministic", "identical_only", "forbidden", "weak")
        for pattern in PATTERNS:
            with self.subTest(pattern=pattern):
                self.assert_expansion(pattern, arbitration=arbitration)

    def test_bounded_response_preserves_supplied_integer_bound(self):
        for maximum in (1, 7):
            with self.subTest(maximum=maximum):
                self.assert_expansion("bounded_response", maximum=maximum)

    def test_once_per_scope_preserves_all_three_declared_lifetimes_and_scopes(self):
        for lifetime in ("encounter", "executor", "persistent"):
            with self.subTest(lifetime=lifetime):
                self.assert_expansion("once_per_scope", lifetime=lifetime)

    def test_persistence_gate_preserves_exact_supplied_duration(self):
        for duration in ("0.125", "17"):
            with self.subTest(duration=duration):
                self.assert_expansion("persistence_gate", duration=duration)

    def test_population_handoff_preserves_empty_and_ordered_sender_effects(self):
        for count in (0, 2):
            with self.subTest(sender_count=count):
                self.assert_expansion("population_handoff", sender_count=count)

    def test_invalid_bound_and_lifetime_are_rejected_before_any_expansion(self):
        cases = [("bounded_response", {"maximum": value}, "positive integer")
                 for value in (0, -1, True, 1.5, "3", None)]
        cases += [("once_per_scope", {"lifetime": value}, "lifetime")
                  for value in ("duration", "unknown", None)]
        for pattern, options, message in cases:
            with self.subTest(pattern=pattern, options=options):
                builder = p.ProgramBuilder("invalid", semantics=semantic_bundle())
                original, source = inputs("one", pattern)
                for declaration in original:
                    builder.add(declaration)
                before = p.to_data(builder.snapshot())
                with self.assertRaisesRegex(ValueError, message):
                    expand(builder, pattern, source, **options)
                self.assertEqual(p.to_data(builder.snapshot()), before)


if __name__ == "__main__":
    unittest.main()
