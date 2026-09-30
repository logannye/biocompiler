"""Adversarial checks of the manager boundary used by reference construction."""

from dataclasses import replace
import unittest
from unittest.mock import Mock

from biocompiler.compiler.pipeline import (
    CheckDecision,
    CheckSpec,
    ComponentInputContract,
    PassManager,
    PipelineError,
    ScopedObligation,
)
from biocompiler.ir.serialization import fingerprint
from biocompiler.semantics.context import PayloadFormat, TargetContext
from biocompiler.verification.evidence import CheckOutcome, EvidenceKind


def admission_fixture():
    target = TargetContext("reviewed_reference", "1", PayloadFormat.DNA)
    document = {
        "schema_version": "audit.component_input.v0.1",
        "target": target.to_dict(),
        "nodes": [{"id": "selected_cds", "kind": "component_instance"}],
        "selected_layout": "trusted_layout",
    }
    manager = PassManager(
        target=target,
        dependencies={"request": fingerprint(document), "reference": "1" * 64},
    )
    obligation = ScopedObligation(
        "authority",
        "reference_construct",
        EvidenceKind.EXACT,
        "Authoritative selection.",
    )
    contract = ComponentInputContract(
        "reference_admission",
        "1",
        document["schema_version"],
        (CheckSpec("selection", EvidenceKind.EXACT, (obligation.id,)),),
        ("preserve_reference",),
        (obligation,),
        ("request", "reference"),
    )
    return manager, document, contract


class ConstructAdmissionAuditTests(unittest.TestCase):
    def test_payload_cannot_spoof_its_authoritative_fingerprint(self):
        manager, document, contract = admission_fixture()
        trusted = fingerprint(document)
        changed = {**document, "selected_layout": "different_layout"}

        class SpoofedPayload:
            fingerprint = trusted

            def to_dict(self):
                return changed

        validator = Mock(return_value=CheckDecision(CheckOutcome.PASS, "Checked."))
        manager.register_component_input(contract, {"selection": validator})
        with self.assertRaisesRegex(PipelineError, "authoritative request identity"):
            manager.admit_component_input(contract.id, "components", SpoofedPayload())
        validator.assert_not_called()

    def test_dependency_changed_during_validation_cannot_grant_a_reusable_root(self):
        manager, document, contract = admission_fixture()

        def change_reference(context):
            manager.set_dependency("reference", "2" * 64)
            return CheckDecision(CheckOutcome.PASS, "Stale checker snapshot.")

        manager.register_component_input(contract, {"selection": change_reference})
        with self.assertRaisesRegex(PipelineError, "Stale artifact"):
            manager.admit_component_input(contract.id, "components", document)
        with self.assertRaisesRegex(PipelineError, "Stale artifact"):
            manager.get("components")

    def test_callback_cannot_be_changed_by_revisiting_an_old_policy_version(self):
        manager, document, contract = admission_fixture()

        def original(context):
            return CheckDecision(CheckOutcome.PASS, "First checker.")

        def changed(context):
            return CheckDecision(CheckOutcome.PASS, "Changed checker.")

        manager.register_component_input(contract, {"selection": original})
        manager.admit_component_input(contract.id, "components", document)
        manager.register_component_input(
            replace(contract, version="2"), {"selection": changed}
        )
        with self.assertRaisesRegex(
            PipelineError, "component admission policy changed"
        ):
            manager.get("components")
        with self.assertRaisesRegex(PipelineError, "increment the contract version"):
            manager.register_component_input(contract, {"selection": changed})

    def test_unknown_and_unsupported_admissions_never_become_accepted_roots(self):
        for outcome in (CheckOutcome.UNKNOWN, CheckOutcome.UNSUPPORTED):
            with self.subTest(outcome=outcome):
                manager, document, contract = admission_fixture()
                manager.register_component_input(
                    contract,
                    {
                        "selection": lambda context, outcome=outcome: CheckDecision(
                            outcome, "Not established."
                        )
                    },
                )
                record = manager.admit_component_input(
                    contract.id, "components", document
                )
                self.assertFalse(record.accepted)
                self.assertFalse(record.discharged)
                with self.assertRaisesRegex(PipelineError, "acceptance checks"):
                    manager.get("components")

    def test_component_admission_cannot_skip_an_existing_input_graph(self):
        manager, document, contract = admission_fixture()
        manager.add_input("intent", document)
        manager.register_component_input(
            contract,
            {"selection": lambda context: CheckDecision(CheckOutcome.PASS, "Checked.")},
        )
        with self.assertRaisesRegex(PipelineError, "new pipeline"):
            manager.admit_component_input(contract.id, "components", document)


if __name__ == "__main__":
    unittest.main()
