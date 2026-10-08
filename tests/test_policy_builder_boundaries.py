"""Authoring failures preserve drafts and never silently import foreign records."""
import inspect
import unittest

import biocompiler.policy as p


CONTACT = p.SemanticDefinition("contact", "1", "encounter", "Supplied contact identity.")
TRANSPORT = p.SemanticDefinition("transport", "1", "transport", "Supplied addressed transport.")
BUNDLE = p.SemanticBundle("builder_boundaries", "1", (CONTACT, TRANSPORT))


def populated(name):
    builder = p.ProgramBuilder(name, semantics=BUNDLE)
    builder.executor("worker", requires=())
    builder.executor("recipient", requires=())
    return builder


def declarations():
    # References are deliberately unowned literal data. This isolates the
    # containing declaration's ownership from the existing nested-ref defense.
    return (
        ("state", p.StateStore("record", p.TRUTH, p.Scope("executor", p.Ref("worker", "Role")),
                               False, 1, "reject", "executor", None, "not_applicable")),
        ("channel", p.Channel("record", p.Ref("worker", "Role"), (p.Ref("recipient", "Role"),),
                              p.TRUTH, TRANSPORT.ref, p.Scope("program"),
                              "fifo", "permitted", "deduplicate", "none", "none")),
        ("require", p.Requirement("record", "safety", "Supplied constant condition.",
                                  p.Scope("executor", p.Ref("worker", "Role")),
                                  condition=p.Expr("literal", p.TRUTH, value=True))),
    )


class PolicyBuilderBoundaryTests(unittest.TestCase):
    def test_encounter_second_identity_collision_keeps_complete_draft(self):
        builder = populated("collision")
        builder.add(p.Parameter("meeting", p.INTEGER, 1))
        before = builder.snapshot()
        self.assertEqual(p.check(before).status, "complete")
        with self.assertRaisesRegex(p.AuthoringError, "duplicate declaration identity: meeting$"):
            builder.encounter("meeting", executor=p.Ref("worker", "Role"), contract=CONTACT.ref)
        self.assertEqual(builder.snapshot(), before)
        self.assertEqual(p.dumps(builder.snapshot()), p.dumps(before))
        self.assertEqual(builder.freeze().declarations, before.declarations)
        # The failed call did not reserve its generated target identity.
        builder.add(p.Parameter("meeting/target", p.INTEGER, 2))
        self.assertEqual(p.check(builder.snapshot()).status, "complete")

    def test_encounter_target_identity_collision_keeps_complete_draft(self):
        builder = populated("target_collision")
        builder.add(p.Parameter("meeting/target", p.INTEGER, 1))
        before = builder.snapshot()
        self.assertEqual(p.check(before).status, "complete")
        with self.assertRaisesRegex(p.AuthoringError, "duplicate declaration identity: meeting/target$"):
            builder.encounter("meeting", executor=p.Ref("worker", "Role"), contract=CONTACT.ref)
        self.assertEqual(builder.snapshot(), before)
        builder.add(p.Parameter("meeting", p.INTEGER, 2))
        self.assertEqual(p.check(builder.snapshot()).status, "complete")

    def test_encounter_invalid_second_record_does_not_add_target(self):
        builder = populated("bad_contract")
        before = builder.snapshot()
        # An opaque field is an ingress failure, not a source-valid semantic case.
        with self.assertRaisesRegex(TypeError, "Non-declarative value"):
            builder.encounter("meeting", executor=p.Ref("worker", "Role"), contract=object())
        self.assertEqual(builder.snapshot(), before)
        self.assertEqual(builder.freeze().declarations, before.declarations)

    def test_encounter_pair_preserves_literal_order_source_and_owned_target(self):
        builder = populated("pair")
        with builder.namespace("nested"):
            line = inspect.currentframe().f_lineno + 1
            encounter = builder.encounter("meeting", executor=p.Ref("worker", "Role"), contract=CONTACT.ref)
        expected = (
            p.Subject("nested/meeting/target", "cell", "encounter", p.Ref("worker", "Role"),
                      p.Ref("nested/meeting", "Encounter")),
            p.Encounter("nested/meeting", p.Ref("worker", "Role"), p.Ref("nested/meeting/target", "Subject"),
                        CONTACT.ref, "contact_loss"),
        )
        self.assertEqual(builder.snapshot().declarations[-2:], expected)
        self.assertEqual(encounter, expected[1])
        self.assertEqual(builder.snapshot().source_map[-2:], (
            p.SourceSpan("nested/meeting/target", __file__, line, 0, "nested"),
            p.SourceSpan("nested/meeting", __file__, line, 0, "nested"),
        ))
        self.assertEqual(p.check(builder.freeze()).status, "complete")
        foreign = populated("foreign")
        before = foreign.snapshot()
        # Reusing either a declaration or its returned target ref must preserve
        # the preexisting in-process guard before structural scope checking.
        for value in (encounter, p.Observation("foreign_target", p.Ref("worker", "Role"),
                      encounter.target, p.TRUTH, CONTACT.ref, p.Ref("clock", "Clock"),
                      "cell", "sampled", "frame", p.Quantity("1", p.SECOND))):
            with self.assertRaisesRegex(p.AuthoringError, "Cross-program"):
                foreign.add(value)
            self.assertEqual(foreign.snapshot(), before)

    def test_copy_helpers_reject_foreign_outer_ownership_without_mutation(self):
        for method, declaration in declarations():
            with self.subTest(method=method):
                origin = populated("origin_" + method)
                destination = populated("destination_" + method)
                owned = getattr(origin, method)(declaration)
                source = origin.freeze()
                before = destination.snapshot()
                self.assertEqual(p.check(before).status, "complete")
                for add in (destination.add, getattr(destination, method)):
                    with self.assertRaisesRegex(p.AuthoringError, "Cross-program"):
                        add(owned)
                    self.assertEqual(destination.snapshot(), before)
                with destination.namespace("other"):
                    with self.assertRaisesRegex(p.AuthoringError, "Cross-program"):
                        getattr(destination, method)(owned)
                self.assertEqual(destination.snapshot(), before)
                self.assertEqual(origin.freeze(), source)

    def test_copy_helpers_accept_same_builder_namespace_and_explicit_data_import(self):
        for method, declaration in declarations():
            with self.subTest(method=method):
                origin = populated("origin_" + method)
                owned = getattr(origin, method)(declaration)
                with origin.namespace("copy"):
                    copied = getattr(origin, method)(owned)
                self.assertEqual((owned.id, copied.id), ("record", "copy/record"))
                self.assertIsNot(owned, copied)
                self.assertEqual(p.check(origin.freeze()).status, "complete")
                imported = p.loads(p.dumps(owned), type(owned))
                destination = populated("destination_" + method)
                accepted = getattr(destination, method)(imported)
                self.assertEqual(accepted, owned)
                self.assertIsNot(accepted, owned)
                self.assertEqual(p.check(destination.freeze()).status, "complete")


if __name__ == "__main__":
    unittest.main()
