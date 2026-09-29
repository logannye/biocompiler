"""A structural root requires fresh independent checks, not an imported receipt."""

from dataclasses import replace
import unittest

from cellweave.artifacts.provenance import SourceLink
from cellweave.compiler.passes import PassResult
from cellweave.compiler.pipeline import (
    CheckDecision,
    CheckSpec,
    ComponentInputContract,
    PassContract,
    PassManager,
    PipelineError,
    ScopedObligation,
)
from cellweave.errors import SerializationError
from cellweave.ir.serialization import fingerprint
from cellweave.ir.stages import Stage
from cellweave.semantics.context import PayloadFormat, TargetContext
from cellweave.verification.evidence import CheckOutcome, EvidenceKind


class ComponentAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.target = TargetContext("structural", "1", PayloadFormat.RNA)
        self.payload = {
            "schema_version": "selected.v1",
            "target": self.target.to_dict(),
            "nodes": [{"id": "part", "kind": "component_instance", "selected": 1}],
        }
        self.obligation = ScopedObligation(
            "selection",
            "reference_construct",
            EvidenceKind.EXACT,
            "Pinned selection verified.",
        )
        self.policy = ComponentInputContract(
            "admit",
            "1",
            "selected.v1",
            (CheckSpec("selection", EvidenceKind.EXACT, ("selection",)),),
            ("r",),
            (self.obligation,),
            ("registry",),
        )
        self.manager = self.make_manager()

    def make_manager(self, payload=None):
        return PassManager(
            target=self.target,
            dependencies={
                "request": fingerprint(self.payload if payload is None else payload),
                "registry": fingerprint("registry"),
            },
        )

    @staticmethod
    def verify(context):
        passed = context.input["nodes"][0]["selected"] == 1
        return CheckDecision(
            CheckOutcome.PASS if passed else CheckOutcome.FAIL,
            "Compared with independent selection.",
        )

    def admit(self, manager=None, payload=None, validator=None):
        manager = self.manager if manager is None else manager
        manager.register_component_input(
            self.policy, {"selection": validator or self.verify}
        )
        return manager.admit_component_input(
            "admit", "selected", self.payload if payload is None else payload
        )

    def test_structural_root_records_real_checks_and_discharge(self):
        record = self.admit()
        self.assertEqual(record.stage, Stage.COMPONENTS)
        self.assertIsNone(record.parent)
        self.assertTrue(record.accepted)
        self.assertEqual(record.discharged, ("selection",))
        self.assertEqual(
            record.provenance["authority"], "independently_checked_component_input"
        )
        self.assertEqual(self.manager.get("selected"), record)

    def test_original_root_api_still_refuses_later_stage(self):
        with self.assertRaises(SerializationError):
            self.manager.add_input("unsafe", self.payload, stage=Stage.COMPONENTS)

    def test_existing_root_cannot_skip_to_components(self):
        self.manager.add_input("intent", self.payload)
        with self.assertRaisesRegex(PipelineError, "new pipeline"):
            self.admit()

    def test_schema_target_identity_and_inventory_are_checked(self):
        changed = []
        for key, value in (
            ("schema_version", "other"),
            ("target", replace(self.target, context_version="2").to_dict()),
            ("nodes", []),
            ("nodes", [{"id": "part", "kind": "fake"}]),
            ("nodes", self.payload["nodes"] * 2),
        ):
            document = {**self.payload, key: value}
            changed.append(document)
        for document in changed:
            with self.subTest(document=document):
                with self.assertRaises(PipelineError):
                    self.admit(manager=self.make_manager(document), payload=document)
        other = {**self.payload, "extra": "changed"}
        with self.assertRaisesRegex(PipelineError, "identity"):
            self.admit(payload=other)

    def test_producer_success_flag_cannot_replace_independent_acceptance(self):
        forged = {
            **self.payload,
            "accepted": True,
            "nodes": [{"id": "part", "kind": "component_instance", "selected": 9}],
        }
        manager = self.make_manager(forged)
        record = self.admit(manager=manager, payload=forged)
        self.assertFalse(record.accepted)
        with self.assertRaisesRegex(PipelineError, "not passed"):
            manager.get("selected")

    def test_all_nonpassing_outcomes_block_consumption(self):
        for outcome in (
            CheckOutcome.FAIL,
            CheckOutcome.UNKNOWN,
            CheckOutcome.UNSUPPORTED,
        ):
            manager = self.make_manager()
            record = self.admit(
                manager=manager,
                validator=lambda context: CheckDecision(
                    outcome, "Unestablished selection."
                ),
            )
            self.assertFalse(record.accepted)
            with self.assertRaises(PipelineError):
                manager.get("selected")

    def test_missing_policy_provider_and_dependencies_cannot_pass(self):
        with self.assertRaises(PipelineError):
            self.manager.admit_component_input("absent", "selected", self.payload)
        with self.assertRaises(PipelineError):
            self.manager.register_component_input(self.policy, {})
        manager = PassManager(
            target=self.target, dependencies={"request": fingerprint(self.payload)}
        )
        with self.assertRaisesRegex(PipelineError, "dependencies"):
            self.admit(manager=manager)
        with self.assertRaises(SerializationError):
            replace(self.policy, checks=())
        with self.assertRaises(SerializationError):
            replace(
                self.policy,
                checks=(CheckSpec("check", EvidenceKind.EMPIRICAL, ("selection",)),),
            )

    def test_changed_callback_requires_version_and_invalidates_existing_root(self):
        self.admit()

        def new_validator(context):
            return CheckDecision(CheckOutcome.PASS, "New policy.")

        with self.assertRaisesRegex(PipelineError, "version"):
            self.manager.register_component_input(
                self.policy, {"selection": new_validator}
            )
        self.manager.register_component_input(
            replace(self.policy, version="2"), {"selection": new_validator}
        )
        with self.assertRaisesRegex(PipelineError, "Stale"):
            self.manager.get("selected")
        with self.assertRaisesRegex(PipelineError, "version"):
            self.manager.register_component_input(
                self.policy, {"selection": new_validator}
            )

    def test_changed_root_during_callback_cannot_leave_fresh_acceptance(self):
        def mutate(context):
            self.manager.set_dependency("registry", fingerprint("changed"))
            return CheckDecision(CheckOutcome.PASS, "This snapshot became stale.")

        with self.assertRaisesRegex(PipelineError, "Stale"):
            self.admit(validator=mutate)
        with self.assertRaisesRegex(PipelineError, "Stale"):
            self.manager.get("selected")

    def test_real_construct_pass_retains_root_and_rejects_transitive_staleness(self):
        self.admit()
        contract = PassContract(
            "assemble",
            "1",
            Stage.COMPONENTS,
            Stage.CONSTRUCT,
            "selected.v1",
            "construct.v1",
            "reference_construct",
            "1",
            ("component_placement",),
            (CheckSpec("layout", EvidenceKind.EXACT),),
        )

        def produce(context):
            return PassResult(
                {
                    "schema_version": "construct.v1",
                    "nodes": [{"id": "part", "kind": "component_placement"}],
                },
                (),
                (SourceLink("r", "part", "part", "assemble"),),
            )

        self.manager.register(
            contract,
            produce,
            {
                "layout": lambda context: CheckDecision(
                    CheckOutcome.PASS, "Layout verified."
                )
            },
        )
        self.manager.run("assemble", "selected", "construct")
        self.assertEqual(self.manager.get("construct").parent, "selected")
        self.manager.register_component_input(
            replace(self.policy, version="2"), {"selection": self.verify}
        )
        with self.assertRaisesRegex(PipelineError, "Stale"):
            self.manager.get("construct")


if __name__ == "__main__":
    unittest.main()
