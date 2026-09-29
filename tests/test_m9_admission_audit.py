"""Independent mutations cannot turn declared correspondence into acceptance."""

from dataclasses import replace
import hashlib
import json
import unittest

import cellweave as cw
from cellweave.compiler.request import BuildRequest, RealizationRequest
from cellweave.errors import SerializationError
from cellweave.ir.component_contracts import PinnedIdentity
from cellweave.semantics.molecular_behavior import (
    MolecularEvidence,
    MolecularImplementationContract,
    MolecularInputBinding,
    MolecularParameter,
    MolecularResponseBinding,
)
from cellweave.semantics.types import BOOLEAN, DURATION
from cellweave.verification.molecular_behavior import (
    MolecularBehaviorResult,
    check_molecular_implementation,
)
from cellweave.verification.payload import check_payload
from test_molecular_checker import fixture as exact_fixture
from test_payload_profiles import fixture as payload_fixture


def correspondence_fixture():
    """Declare artificial observations over a source-only CDS without a model."""
    downstream = exact_fixture("RNA")
    construct_request, _, molecular, _, _ = downstream
    therapy = cw.Therapy("admission-audit")
    cell = therapy.engineer("cell", cell_type="abstract_cell")
    signal = cell.contact.marker("fixture-marker")
    action = cell.rest()
    rule = cell.when(signal.present()).do(action)
    build = BuildRequest.freeze(therapy.freeze(), target=construct_request.target)
    behavior = cw.lower_to_behavior(build)
    observable = cw.Observable("fixture-output", cw.Level, cell.role)
    response = cw.ResponseRequirement(
        "fixture-response",
        rule.node_id,
        action.node_id,
        observable,
        cw.Interval(0.9, 1.1),
        cw.Interval(0, 0.1),
        cw.Duration(1),
        cw.Duration(1),
    )
    measured = cw.Observable("fixture-input", BOOLEAN, cell.role, scope="contact")
    domain = cw.OperatingDomain(
        "fixture-domain",
        "1",
        cell.role,
        (cw.InputDomain(signal.node_id, "present", measured, (False, True)),),
        cw.Duration(10),
        max_contacts=1,
    )
    request = RealizationRequest.freeze(
        build,
        behavior,
        cw.BehaviorContract("fixture-contract", behavior.fingerprint, (response,)),
        domain,
    )
    instance = construct_request.registry_lock.components[0].node_id
    contract = MolecularImplementationContract.freeze(
        "audit-correspondence",
        request,
        construct_request,
        molecular,
        input_bindings=(
            MolecularInputBinding(signal.node_id, "present", instance, measured),
        ),
        response_bindings=(
            MolecularResponseBinding(
                response.id, rule.node_id, action.node_id, instance, observable
            ),
        ),
    )
    return contract, request, *downstream


class M9AdmissionAuditTests(unittest.TestCase):
    def setUp(self):
        self.inputs = correspondence_fixture()
        self.contract = self.inputs[0]
        self.control = check_molecular_implementation(*self.inputs)
        self.assertEqual(self.control.linkage_outcome, cw.CheckOutcome.PASS)
        self.assertEqual(self.control.outcome, cw.CheckOutcome.UNKNOWN)
        self.assertFalse(self.control.passed)

    def check(self, contract):
        return check_molecular_implementation(contract, *self.inputs[1:])

    def test_self_asserted_empirical_labels_cannot_promote_correspondence(self):
        evidence = tuple(
            MolecularEvidence(
                category,
                category,
                PinnedIdentity("evidence", "untrusted-" + category, "1", "a" * 64),
                self.inputs[1].target.fingerprint,
                "exact_material",
                "Caller assertion only; no independent validator has accepted it.",
            )
            for category in (
                "material_identity",
                "parameter_fitting",
                "model_validation",
                "uncertainty",
                "therapeutic_outcome",
            )
        )
        parameter = MolecularParameter(
            "claimed-time",
            DURATION,
            category="measured",
            value=cw.Duration(1),
            source=evidence[0].source,
        )
        altered = replace(self.contract, evidence=evidence, parameters=(parameter,))
        result = self.check(altered)
        self.assertEqual(result.linkage_outcome, cw.CheckOutcome.PASS)
        self.assertEqual(result.outcome, cw.CheckOutcome.UNKNOWN)
        self.assertFalse(result.passed)
        codes = {item.code for item in result.diagnostics}
        for item in evidence:
            self.assertIn("unvalidated_evidence:" + item.id, codes)
        self.assertEqual(result.checked_requirement_ids, ("fixture-response",))
        self.assertFalse(self.control.freshness(altered, *self.inputs[1:]).fresh)

    def test_pinned_adapter_and_ports_do_not_register_an_executable_provider(self):
        proposal = replace(
            self.contract,
            adapter=PinnedIdentity("model", "claimed-calibrated-model", "1", "b" * 64),
            input_bindings=(
                replace(self.contract.input_bindings[0], adapter_input="x"),
            ),
            response_bindings=(
                replace(self.contract.response_bindings[0], adapter_output="y"),
            ),
        )
        result = self.check(proposal)
        self.assertEqual(result.outcome, cw.CheckOutcome.UNSUPPORTED)
        self.assertFalse(result.passed)
        self.assertIn("adapter_provider", {item.code for item in result.diagnostics})

    def test_response_units_and_requirement_ids_are_checked_against_authority(self):
        original = self.contract.response_bindings[0]
        for binding in (
            replace(original, requirement_id="invented-requirement"),
            replace(original, observable=replace(original.observable, dtype=DURATION)),
        ):
            with self.subTest(binding=binding):
                result = self.check(
                    replace(self.contract, response_bindings=(binding,))
                )
                self.assertEqual(result.outcome, cw.CheckOutcome.FAIL)
                self.assertEqual(result.linkage_outcome, cw.CheckOutcome.FAIL)
                self.assertFalse(result.passed)
                self.assertEqual(result.checked_requirement_ids, ("fixture-response",))

    def test_result_import_cannot_upgrade_status_or_remove_evidence_boundary(self):
        altered = self.control.to_dict()
        altered["outcome"] = "pass"
        with self.assertRaises(SerializationError):
            MolecularBehaviorResult.from_dict(altered)
        altered = self.control.to_dict()
        altered["diagnostics"] = [
            item
            for item in altered["diagnostics"]
            if item["code"] != "no_calibrated_adapter"
        ]
        with self.assertRaises(SerializationError):
            MolecularBehaviorResult.from_dict(altered)
        restored = MolecularBehaviorResult.from_json(self.control.to_json())
        self.assertFalse(restored.passed)
        self.assertEqual(restored.outcome, cw.CheckOutcome.UNKNOWN)


class PayloadAdmissionAuditTests(unittest.TestCase):
    def setUp(self):
        self.candidate, self.reference, self.retained = payload_fixture()
        control = self.check(self.reference, self.retained)
        self.assertTrue(control.passed)
        self.assertFalse(control.compiler_admission)
        self.assertEqual(control.reference_promotion, "not_promoted")

    def check(self, reference, retained):
        return check_payload(
            self.candidate,
            reference,
            expected_reference_fingerprint=reference.fingerprint,
            retained_sources=retained,
        )

    def test_review_classification_cannot_be_changed_without_bound_attestations(self):
        altered = replace(self.reference, source_kind="externally_reviewed")
        result = self.check(altered, self.retained)
        self.assertEqual(result.outcome, cw.CheckOutcome.FAIL)
        self.assertIn("payload_review_statement", {x.code for x in result.diagnostics})
        self.assertFalse(result.compiler_admission)
        self.assertEqual(result.reference_promotion, "not_promoted")

    def test_duplicate_review_decision_is_rejected_even_with_current_byte_hash(self):
        review = self.reference.reviews[1]
        statement = json.loads(self.retained[review.source.id])
        # Ordinary JSON parsers would retain the last, accepting decision.
        duplicated = ('{"decision":"reject",' + json.dumps(statement)[1:]).encode(
            "utf-8"
        )
        self.assertEqual(json.loads(duplicated)["decision"], "accept")
        updated_review = replace(
            review,
            source=replace(
                review.source, sha256=hashlib.sha256(duplicated).hexdigest()
            ),
        )
        altered = replace(
            self.reference, reviews=(self.reference.reviews[0], updated_review)
        )
        result = self.check(altered, self.retained | {review.source.id: duplicated})
        self.assertEqual(result.outcome, cw.CheckOutcome.FAIL)
        codes = {x.code for x in result.diagnostics}
        self.assertIn("payload_review_statement", codes)
        self.assertNotIn("payload_source_hash", codes)
        self.assertNotIn("payload_authority_pin", codes)
        self.assertFalse(result.compiler_admission)


if __name__ == "__main__":
    unittest.main()
