"""Exact-CDS linkage must never promote requested molecular behavior to PASS."""

from dataclasses import replace
import hashlib
import unittest
from unittest.mock import patch

import cellweave as cw
from cellweave.compiler.molecular import run_molecular_pipeline
from cellweave.errors import SerializationError, TypeMismatchError
from cellweave.ir.component_contracts import PinnedIdentity
from cellweave.ir.serialization import fingerprint
from cellweave.semantics.molecular_behavior import (
    MolecularEvidence,
    MolecularImplementationContract,
    MolecularInputBinding,
    MolecularParameter,
    MolecularResponseBinding,
)
from cellweave.semantics.types import BOOLEAN, DURATION
from cellweave.verification.evidence import CheckOutcome
from cellweave.verification.molecular_behavior import (
    MolecularBehaviorResult,
    check_molecular_implementation,
)
from examples.reference_construct import reference_request


def molecular_fixture(alphabet="RNA", *, extra_action=False):
    construct_request, manifest, registry = reference_request(alphabet)
    manifests = {manifest.reference_set_id: manifest}
    built = run_molecular_pipeline(construct_request, registry, manifests)
    therapy = cw.Therapy("molecular_correspondence_fixture")
    cell = therapy.engineer("effector", cell_type="requested_cell")
    marker = cell.contact.marker("requested_marker")
    action = cell.eliminate(cell.contact)
    rule = cell.when(marker.present()).do(action)
    if extra_action:
        cell.when(marker.present()).do(cell.rest())
    build_request = cw.BuildRequest.freeze(
        therapy.freeze(), target=construct_request.target, artifact_scope="exact_cds"
    )
    behavior = cw.lower_to_behavior(build_request)
    response = cw.ResponseRequirement(
        "requested_response",
        rule.node_id,
        action.node_id,
        cw.Observable("requested_measurement", cw.Level, cell.role, scope="contact"),
        cw.Interval(0.9, 1.1),
        cw.Interval(0, 0.1),
        cw.Duration(2),
        cw.Duration(2),
    )
    domain = cw.OperatingDomain(
        "requested_domain",
        "1",
        cell.role,
        (
            cw.InputDomain(
                marker.node_id,
                "present",
                cw.Observable(
                    "marker_observation", BOOLEAN, cell.role, scope="contact"
                ),
                (False, True),
            ),
        ),
        cw.Duration(5),
        max_contacts=1,
    )
    realization = cw.RealizationRequest.freeze(
        build_request,
        behavior,
        cw.BehaviorContract("requested_response", behavior.fingerprint, (response,)),
        domain,
    )
    contract = MolecularImplementationContract.freeze(
        "requested_molecular_implementation",
        realization,
        construct_request,
        built.candidate,
        input_bindings=(
            MolecularInputBinding(
                marker.node_id, "present", "fap_cds", domain.inputs[0].observable
            ),
        ),
        response_bindings=(
            MolecularResponseBinding(
                response.id,
                rule.node_id,
                action.node_id,
                "fap_cds",
                response.observable,
            ),
        ),
        assumptions=(
            "Response bands and times are requested design requirements, not biological observations.",
        ),
        parameters=(MolecularParameter("response_time", DURATION),),
    )
    return (
        contract,
        realization,
        construct_request,
        built.construct,
        built.candidate,
        registry,
        manifests,
    )


class MolecularBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = molecular_fixture()

    def check(self, **changes):
        keys = (
            "contract",
            "realization_request",
            "construct_request",
            "construct",
            "molecular",
            "registry",
            "manifests",
        )
        return check_molecular_implementation(
            *(changes.get(key, value) for key, value in zip(keys, self.inputs))
        )

    def test_exact_dna_rna_linkage_is_positive_but_biology_is_unknown(self):
        for alphabet in ("DNA", "RNA"):
            inputs = self.inputs if alphabet == "RNA" else molecular_fixture(alphabet)
            result = check_molecular_implementation(*inputs)
            self.assertEqual(result.linkage_outcome, CheckOutcome.PASS)
            self.assertEqual(result.outcome, CheckOutcome.UNKNOWN)
            self.assertFalse(result.passed)
            self.assertIn(
                "unestablished:exact_experimental_material",
                {item.code for item in result.diagnostics},
            )
            self.assertIn(
                "unestablished:auxiliary_coding_processing_context",
                {item.code for item in result.diagnostics},
            )
            self.assertEqual(
                MolecularBehaviorResult.from_json(result.to_json()), result
            )
            self.assertEqual(
                MolecularImplementationContract.from_json(inputs[0].to_json()),
                inputs[0],
            )

    def test_independent_checkers_run_and_generators_are_not_required(self):
        with (
            patch(
                "cellweave.compiler.molecular.emit_reference_sequence",
                side_effect=AssertionError("must not emit"),
            ),
            patch(
                "cellweave.synthesis.synthetic.generate_synthetic",
                side_effect=AssertionError("must not generate"),
            ),
        ):
            result = self.check()
        self.assertEqual(result.linkage_outcome, CheckOutcome.PASS)
        with patch(
            "cellweave.verification.molecular_behavior.verify_lowering",
            side_effect=AssertionError("authority rechecked"),
        ):
            with self.assertRaisesRegex(AssertionError, "authority rechecked"):
                self.check()
        with patch(
            "cellweave.verification.molecular_behavior.check_molecular",
            side_effect=AssertionError("sequence rechecked"),
        ):
            with self.assertRaisesRegex(AssertionError, "sequence rechecked"):
                self.check()

    def test_independent_authority_pins_cannot_be_replaced_by_claimed_success(self):
        contract = self.inputs[0]
        for field in (
            "realization_request_fingerprint",
            "construct_request_fingerprint",
            "molecular_fingerprint",
            "target_fingerprint",
            "domain_fingerprint",
        ):
            with self.subTest(field=field):
                result = self.check(contract=replace(contract, **{field: "0" * 64}))
                self.assertEqual(result.outcome, CheckOutcome.FAIL)
                self.assertIn(field, {item.code for item in result.diagnostics})
        lock = replace(contract.selected_components[0], version="different")
        self.assertEqual(
            self.check(contract=replace(contract, selected_components=(lock,))).outcome,
            CheckOutcome.FAIL,
        )

    def test_sequence_mutation_and_updated_contract_hash_still_fail(self):
        contract, _, _, _, molecular, _, _ = self.inputs
        record = molecular.records[0]
        sequence = (
            record.sequence[:30]
            + ("A" if record.sequence[30] != "A" else "C")
            + record.sequence[31:]
        )
        mutated = replace(
            molecular,
            records=(
                replace(
                    record,
                    sequence=sequence,
                    sequence_sha256=hashlib.sha256(sequence.encode()).hexdigest(),
                ),
            ),
        )
        result = self.check(
            contract=replace(contract, molecular_fingerprint=mutated.fingerprint),
            molecular=mutated,
        )
        self.assertEqual(result.linkage_outcome, CheckOutcome.FAIL)
        self.assertIn(
            "molecular_acceptance", {item.code for item in result.diagnostics}
        )

    def test_input_response_identity_type_scope_source_and_instance_are_exact(self):
        contract = self.inputs[0]
        item = contract.input_bindings[0]
        mutations = [
            replace(item, signal_id="absent"),
            replace(item, instance_id="absent"),
            replace(item, observable=replace(item.observable, id="different")),
            replace(item, observable=replace(item.observable, scope="cell")),
        ]
        for item in mutations:
            self.assertEqual(
                self.check(contract=replace(contract, input_bindings=(item,))).outcome,
                CheckOutcome.FAIL,
            )
        item = contract.response_bindings[0]
        mutations = [
            replace(item, requirement_id="absent"),
            replace(item, rule_id="absent"),
            replace(item, specification_id="absent"),
            replace(item, instance_id="absent"),
            replace(item, observable=replace(item.observable, compartment="elsewhere")),
        ]
        for item in mutations:
            self.assertEqual(
                self.check(
                    contract=replace(contract, response_bindings=(item,))
                ).outcome,
                CheckOutcome.FAIL,
            )
        with self.assertRaises(SerializationError):
            replace(contract, input_bindings=())
        with self.assertRaises(SerializationError):
            replace(contract, response_bindings=())
        with self.assertRaises(SerializationError):
            replace(contract, input_bindings=contract.input_bindings * 2)
        with self.assertRaises(SerializationError):
            replace(contract, response_bindings=contract.response_bindings * 2)

    def test_domain_and_response_source_must_themselves_correspond_to_behavior(self):
        contract, realization, *_ = self.inputs
        domain = replace(
            realization.domain,
            inputs=(replace(realization.domain.inputs[0], signal_id="absent"),),
        )
        changed = replace(realization, domain=domain)
        changed_contract = replace(
            contract,
            realization_request_fingerprint=changed.fingerprint,
            domain_fingerprint=domain.fingerprint,
            input_bindings=(replace(contract.input_bindings[0], signal_id="absent"),),
        )
        result = self.check(contract=changed_contract, realization_request=changed)
        self.assertEqual(result.linkage_outcome, CheckOutcome.FAIL)
        self.assertIn("domain_coverage", {item.code for item in result.diagnostics})
        response = replace(
            realization.contract.requirements[0], specification_id="absent"
        )
        changed = replace(
            realization,
            contract=replace(realization.contract, requirements=(response,)),
        )
        changed_contract = replace(
            contract,
            realization_request_fingerprint=changed.fingerprint,
            response_bindings=(
                replace(contract.response_bindings[0], specification_id="absent"),
            ),
        )
        result = self.check(contract=changed_contract, realization_request=changed)
        self.assertIn("requirement_source", {item.code for item in result.diagnostics})

    def test_omitting_an_authored_output_from_both_contract_and_mapping_is_unsupported(
        self,
    ):
        result = check_molecular_implementation(*molecular_fixture(extra_action=True))
        self.assertEqual(result.linkage_outcome, CheckOutcome.UNSUPPORTED)
        self.assertEqual(result.outcome, CheckOutcome.UNSUPPORTED)
        self.assertIn(
            "uncontracted_outputs", {item.code for item in result.diagnostics}
        )

    def test_proposed_adapters_and_new_semantics_remain_unsupported(self):
        contract = self.inputs[0]
        adapter = PinnedIdentity(
            "model", "synthetic_delay_assigned_to_car", "1", fingerprint("unvalidated")
        )
        result = self.check(
            contract=replace(
                contract,
                adapter=adapter,
                input_bindings=(
                    replace(contract.input_bindings[0], adapter_input="input"),
                ),
                response_bindings=(
                    replace(contract.response_bindings[0], adapter_output="response"),
                ),
            )
        )
        self.assertEqual(result.linkage_outcome, CheckOutcome.PASS)
        self.assertEqual(result.outcome, CheckOutcome.UNSUPPORTED)
        self.assertIn("adapter_provider", {item.code for item in result.diagnostics})
        for profile in (
            "quantitative_tracking.v0.1",
            "continuous.v0.1",
            "uncertain_population.v0.1",
            "spatial.v0.1",
            "feedback.v0.1",
        ):
            self.assertEqual(
                self.check(contract=replace(contract, model_profile=profile)).outcome,
                CheckOutcome.UNSUPPORTED,
            )

    def test_citations_and_fitted_parameters_do_not_validate_model_or_material(self):
        contract = self.inputs[0]
        source = PinnedIdentity(
            "evidence", "declared_evidence", "1", fingerprint("cited content")
        )
        parameter = MolecularParameter(
            "response_time",
            DURATION,
            "fitted",
            cw.Duration(2),
            source,
            "Explicit test fixture fit",
            cw.Interval(cw.Duration(1), cw.Duration(3), type=cw.Duration),
        )
        for category in (
            "sequence_identity",
            "material_identity",
            "parameter_fitting",
            "model_validation",
            "uncertainty",
            "therapeutic_outcome",
        ):
            evidence = MolecularEvidence(
                "declaration",
                category,
                source,
                contract.target_fingerprint,
                "exact_material",
                "A caller assertion is not acceptance.",
            )
            result = self.check(
                contract=replace(
                    contract, parameters=(parameter,), evidence=(evidence,)
                )
            )
            self.assertEqual(result.outcome, CheckOutcome.UNKNOWN)
            self.assertIn(
                "unvalidated_evidence:declaration",
                {item.code for item in result.diagnostics},
            )
        wrong_context = replace(evidence, context_fingerprint="0" * 64)
        self.assertEqual(
            self.check(contract=replace(contract, evidence=(wrong_context,))).outcome,
            CheckOutcome.FAIL,
        )
        with self.assertRaises(SerializationError):
            replace(contract, unestablished_claims=())
        with self.assertRaises(TypeMismatchError):
            replace(parameter, value=cw.Level(2))
        with self.assertRaises(SerializationError):
            replace(parameter, category="unestablished")
        self.assertEqual(MolecularParameter.from_json(parameter.to_json()), parameter)

    def test_all_semantic_and_evidence_changes_invalidate_historical_result(self):
        (
            contract,
            realization,
            construct_request,
            construct,
            molecular,
            registry,
            manifests,
        ) = self.inputs
        result = self.check()
        self.assertTrue(result.freshness(*self.inputs).fresh)
        variants = [
            replace(contract, assumptions=("changed assumption",)),
            replace(contract, model_profile="other.v0.1"),
            replace(
                contract,
                parameters=(
                    MolecularParameter("different_missing_parameter", DURATION),
                ),
            ),
        ]
        for changed in variants:
            self.assertIn(
                "contract",
                result.freshness(changed, *self.inputs[1:]).changed_dependencies,
            )
        self.assertIn(
            "registry",
            result.freshness(
                contract,
                realization,
                construct_request,
                construct,
                molecular,
                replace(registry, version="new"),
                manifests,
            ).changed_dependencies,
        )
        self.assertIn(
            "references",
            result.freshness(
                contract,
                realization,
                construct_request,
                construct,
                molecular,
                registry,
                {},
            ).changed_dependencies,
        )
        source = PinnedIdentity("evidence", "fit", "1", fingerprint("first source"))
        first = replace(
            contract,
            parameters=(
                MolecularParameter(
                    "response_time", DURATION, "fitted", cw.Duration(2), source
                ),
            ),
        )
        first_result = self.check(contract=first)
        changed_parameter = replace(
            first.parameters[0],
            source=replace(source, content_fingerprint=fingerprint("different data")),
        )
        second = replace(first, parameters=(changed_parameter,))
        self.assertFalse(first_result.freshness(second, *self.inputs[1:]).fresh)

    def test_strict_imports_reject_forged_pass_missing_dependencies_and_optional_shapes(
        self,
    ):
        result = self.check()
        for field, value in (
            ("outcome", "pass"),
            ("claim_scope", "verified biology"),
            ("linkage_outcome", "fail"),
        ):
            data = result.to_dict()
            data[field] = value
            with self.subTest(field=field), self.assertRaises(SerializationError):
                MolecularBehaviorResult.from_dict(data)
        data = result.to_dict()
        del data["dependencies"]["molecular_check_inputs"]
        with self.assertRaises(SerializationError):
            MolecularBehaviorResult.from_dict(data)
        for value in ({}, [], 0, False, ""):
            data = self.inputs[0].to_dict()
            data["adapter"] = value
            with self.assertRaises(SerializationError):
                MolecularImplementationContract.from_dict(data)
            data = MolecularParameter("x", DURATION).to_dict()
            data["source"] = value
            with self.assertRaises(SerializationError):
                MolecularParameter.from_dict(data)
        data = self.inputs[0].to_dict()
        data["extra"] = True
        with self.assertRaises(SerializationError):
            MolecularImplementationContract.from_dict(data)
        with self.assertRaises(SerializationError):
            replace(self.inputs[0], id="\ud800")


if __name__ == "__main__":
    unittest.main()
