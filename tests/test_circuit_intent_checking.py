"""Independent source-retention, lock-mutation and claim-boundary regressions."""

import ast
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.compiler.request import BuildRequest
from biocompiler.frontend.api import Therapy
from biocompiler.ir.circuit_intent import (
    CircuitBehavior,
    CircuitBehaviorExpectation,
    CircuitInputBinding,
    CircuitLifecycle,
    CircuitProviderRequirement,
    CircuitReferenceLock,
    CircuitRequest,
    CircuitRequirement,
)
from biocompiler.ir.circuit_logic import BooleanSpec, CircuitSignal
from biocompiler.ir.circuit_observations import (
    CircuitObservation,
    CircuitProduct,
    ObservationEncoding,
    ObservationEntity,
    ObservationScope,
    ObservationWindow,
    ProductKind,
    QuantityKind,
)
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.intent import SourceLocation
from biocompiler.ir.serialization import fingerprint
from biocompiler.verification import circuit_intent as checker
from biocompiler.verification.circuit_intent import (
    CircuitIntentAssessment,
    check_circuit_intent,
    verify_circuit_intent,
)
from biocompiler.verification.evidence import CheckOutcome
from examples.circuit_profile import make_profile_requests


def _observation(identity, quantity=QuantityKind.MIRNA_ACTIVITY):
    return CircuitObservation(
        identity,
        ObservationEntity("software_fixture", identity, "1", "unknown"),
        quantity,
        "cytoplasm",
        ObservationScope.CELL_ACCESSIBLE,
        ObservationWindow("unknown", None, None, "unknown", "unknown"),
        ObservationEncoding("qualitative", "qualitative"),
    )


def _behavior(outputs=(False, False, False, True)):
    inputs = (_observation("A"), _observation("B"))
    table = BooleanSpec(
        tuple(CircuitSignal(item.id, item.fingerprint) for item in inputs), outputs
    )
    return CircuitBehavior(
        inputs,
        table,
        CircuitProduct(
            "reporter_requirement",
            ProductKind.REPORTER_FLUORESCENCE,
            _observation("readout", QuantityKind.FLUORESCENCE),
        ),
        CircuitLifecycle("readout"),
        (
            CircuitProviderRequirement(
                "co_input",
                ObservationEntity("software_fixture", "provider", "1", "unknown"),
                "co_delivered",
                "cytoplasm",
                "same_cell",
            ),
        ),
    )


def product_request():
    profile = make_profile_requests()["product"]
    source = profile.source_request
    role = source.deployment_request.deployment.recipient_role
    requirement = CircuitRequirement(
        "logic_requirement",
        _behavior(),
        role,
        tuple(item.id for item in source.build_request.intent.nodes),
        SourceLocation("tests/software_fixture.py", 12, "author"),
    )
    return CircuitRequest(
        profile,
        (requirement,),
        "delivered_rna",
        "source_nominal",
        source.deployment_request.deployment.id,
    )


def reference_request(outputs=(False, False, False, True)):
    profile = make_profile_requests()["reference"]
    behavior = _behavior(outputs)
    requirement = CircuitRequirement("logic_requirement", behavior, None, (), None)
    realization = PinnedIdentity("reference", "artificial_lock", "1", "b" * 64)
    lock = CircuitReferenceLock(
        (CircuitBehaviorExpectation(requirement.id, behavior),),
        realization,
        profile.source_experiment.sources,
        profile.source_experiment,
        "delivered_rna",
        "source_nominal",
    )
    return CircuitRequest(
        profile,
        (requirement,),
        "delivered_rna",
        "source_nominal",
        None,
        realization,
        lock,
    )


def mapped_product_request():
    profile = make_profile_requests()["product"]
    therapy = Therapy("bound_input_source_fixture")
    cells = therapy.engineer("recipient", cell_type="declared human T cells")
    first = cells.internal.signal("first")
    second = cells.internal.signal("second")
    cells.when(first.high() | second.high()).do(cells.report("software_event"))
    source = BuildRequest.freeze(therapy.freeze(), target=profile.target)
    requirement = CircuitRequirement(
        "mapped_requirement",
        _behavior(),
        cells.role,
        tuple(item.id for item in source.intent.nodes),
        None,
        (
            CircuitInputBinding("A", first.node_id),
            CircuitInputBinding("B", second.node_id),
        ),
    )
    return CircuitRequest(
        replace(profile, source_request=source),
        (requirement,),
        "delivered_rna",
        "source_nominal",
        "declared_deployment_fixture",
    )


class CircuitIntentCheckingTests(unittest.TestCase):
    def setUp(self):
        self.request = product_request()
        self.assessment = check_circuit_intent(self.request)

    def test_all_original_nodes_locations_and_wrappers_are_receipted(self):
        source = self.request.profile.source_request
        nodes = source.build_request.intent.nodes
        self.assertEqual(
            tuple(item.id for item in self.assessment.source_inventory),
            tuple(item.id for item in nodes),
        )
        self.assertEqual(
            tuple(item.node_fingerprint for item in self.assessment.source_inventory),
            tuple(fingerprint(item.to_dict()) for item in nodes),
        )
        contracts = {
            item.path: item.contract_fingerprint
            for item in self.assessment.contract_inventory
        }
        self.assertEqual(contracts["acceptance"], source.acceptance.fingerprint)
        self.assertEqual(
            contracts["deployment"], source.deployment_request.deployment.fingerprint
        )
        self.assertEqual(
            contracts["behavior.contract"], source.behavior_request.contract.fingerprint
        )
        self.assertEqual(contracts["build_request.target"], source.target.fingerprint)
        self.assertIn("build_request.context", contracts)
        self.assertIn("build_request.intent_structure", contracts)
        self.assertIn("circuit.deployment_identity", contracts)
        self.assertEqual(
            self.assessment.request.profile.source_request.to_dict(), source.to_dict()
        )
        for item in nodes:
            self.assertIn(
                f"source_node:{item.id}:{item.kind}:implementation_unresolved",
                self.assessment.diagnostics,
            )

    def test_round_trip_is_immutable_and_replay_remains_unsupported(self):
        saved = CircuitIntentAssessment.from_json(self.assessment.to_json())
        checked = verify_circuit_intent(saved, expected_request=self.request)
        self.assertEqual(checked.to_dict(), self.assessment.to_dict())
        self.assertEqual(checked.outcome, CheckOutcome.UNSUPPORTED)
        self.assertEqual(checked.intent_consistency, "consistent")
        self.assertEqual(checked.molecular_implementation, "unimplemented")
        self.assertEqual(checked.empirical_validation, "unknown")
        self.assertEqual(checked.human_therapeutic_admission, "not_admitted")
        with self.assertRaises(FrozenInstanceError):
            checked.request = None
        with self.assertRaises(TypeError):
            checked.dependencies["checker"] = "forged"

    def test_reference_inventory_has_no_invented_therapeutic_source(self):
        request = reference_request()
        checked = check_circuit_intent(request)
        self.assertEqual(checked.source_inventory, ())
        self.assertEqual(
            tuple(item.path for item in checked.contract_inventory),
            ("source_experiment",),
        )
        self.assertIsNone(checked.request.profile.target)
        self.assertIn(
            "reference_lock_consistency_is_not_source_or_mechanism_validation",
            checked.diagnostics,
        )

    def test_all_sixteen_two_input_tables_retain_exact_lock_authority(self):
        # Literal independent tables in 00, 01, 10, 11 order. No gate generator
        # or software evaluator determines the expected rows for these checks.
        tables = (
            (False, False, False, False),
            (False, False, False, True),
            (False, False, True, False),
            (False, False, True, True),
            (False, True, False, False),
            (False, True, False, True),
            (False, True, True, False),
            (False, True, True, True),
            (True, False, False, False),
            (True, False, False, True),
            (True, False, True, False),
            (True, False, True, True),
            (True, True, False, False),
            (True, True, False, True),
            (True, True, True, False),
            (True, True, True, True),
        )
        fingerprints = set()
        for table in tables:
            with self.subTest(table=table):
                request = reference_request(table)
                checked = check_circuit_intent(request)
                self.assertEqual(
                    checked.request.requirements[0].behavior.response.outputs, table
                )
                self.assertEqual(
                    checked.request.reference_lock.expected_behaviors[
                        0
                    ].behavior.response.outputs,
                    table,
                )
                fingerprints.add(checked.requirement_inventory[0].logic_fingerprint)
        self.assertEqual(len(fingerprints), 16)

    def test_and_to_or_edit_with_original_lock_rejects(self):
        request = reference_request()
        data = request.to_dict()
        data["requirements"][0]["behavior"]["response"]["outputs"] = [
            False,
            True,
            True,
            True,
        ]
        with self.assertRaises(SerializationError):
            CircuitRequest.from_dict(data)

    def test_independent_lock_check_rejects_bypassed_schema_validation(self):
        # Corrupt an object after construction, then bypass the schema reparse to
        # demonstrate that the checker makes its own lock acceptance decision.
        request = reference_request()
        object.__setattr__(
            request.requirements[0], "behavior", _behavior((False, True, True, True))
        )
        with patch.object(CircuitRequest, "from_dict", return_value=request):
            with self.assertRaisesRegex(SerializationError, "locked nominal"):
                check_circuit_intent(request)

    def test_independent_binding_check_rejects_bypassed_schema_validation(self):
        request = product_request()
        object.__setattr__(
            request.requirements[0].behavior.response.inputs[0],
            "observation_fingerprint",
            "c" * 64,
        )
        with patch.object(CircuitRequest, "from_dict", return_value=request):
            with self.assertRaisesRegex(SerializationError, "complete observation"):
                check_circuit_intent(request)

    def test_independent_lifecycle_check_rejects_bypassed_schema_validation(self):
        request = product_request()
        object.__setattr__(
            request.requirements[0].behavior.lifecycle, "mode", "production_control"
        )
        with patch.object(CircuitRequest, "from_dict", return_value=request):
            with self.assertRaisesRegex(SerializationError, "lifecycle requirements"):
                check_circuit_intent(request)

    def test_independent_accessibility_check_rejects_bypassed_schema_validation(self):
        request = product_request()
        behavior = request.requirements[0].behavior
        object.__setattr__(behavior.inputs[0], "scope", ObservationScope.EVALUATOR)
        object.__setattr__(
            behavior.response.inputs[0],
            "observation_fingerprint",
            behavior.inputs[0].fingerprint,
        )
        with patch.object(CircuitRequest, "from_dict", return_value=request):
            with self.assertRaisesRegex(SerializationError, "cell-accessible"):
                check_circuit_intent(request)

    def test_independent_form_check_rejects_bypassed_schema_validation(self):
        request = product_request()
        object.__setattr__(request, "requested_form", "delivered_dna")
        with patch.object(CircuitRequest, "from_dict", return_value=request):
            with self.assertRaisesRegex(SerializationError, "DNA/RNA modality"):
                check_circuit_intent(request)

    def test_independent_source_pin_check_rejects_bypassed_schema_validation(self):
        request = reference_request()
        object.__setattr__(request.reference_lock, "authority", ())
        with patch.object(CircuitRequest, "from_dict", return_value=request):
            with self.assertRaisesRegex(SerializationError, "authority pins"):
                check_circuit_intent(request)

    def test_per_input_source_mapping_preserved_and_swaps_invalidate_replay(self):
        request = mapped_product_request()
        assessment = check_circuit_intent(request)
        requirement = request.requirements[0]
        original = requirement.input_bindings
        self.assertEqual(
            assessment.request.requirements[0].input_bindings,
            original,
        )
        swapped = replace(
            requirement,
            input_bindings=(
                CircuitInputBinding("A", original[1].source_node_id),
                CircuitInputBinding("B", original[0].source_node_id),
            ),
        )
        changed = replace(request, requirements=(swapped,))
        self.assertEqual(requirement.behavior.fingerprint, swapped.behavior.fingerprint)
        with self.assertRaisesRegex(
            SerializationError, "independent complete authority"
        ):
            verify_circuit_intent(assessment, expected_request=changed)
        self.assertNotEqual(
            assessment.requirement_inventory[0].requirement_fingerprint,
            check_circuit_intent(changed)
            .requirement_inventory[0]
            .requirement_fingerprint,
        )

    def test_independent_input_binding_checks_reject_bypassed_schema(self):
        for field, value in (
            ("observation_id", "undeclared"),
            ("source_node_id", "missing"),
        ):
            with self.subTest(field=field):
                request = mapped_product_request()
                object.__setattr__(
                    request.requirements[0].input_bindings[0], field, value
                )
                with patch.object(CircuitRequest, "from_dict", return_value=request):
                    with self.assertRaisesRegex(
                        SerializationError, "input binding differs"
                    ):
                        check_circuit_intent(request)

    def test_reference_cannot_invent_input_source_bindings(self):
        request = reference_request()
        object.__setattr__(
            request.requirements[0],
            "input_bindings",
            (CircuitInputBinding("A", "invented"),),
        )
        with patch.object(CircuitRequest, "from_dict", return_value=request):
            with self.assertRaises(SerializationError):
                check_circuit_intent(request)

    def test_absent_input_source_correspondence_stays_explicit(self):
        for observation in self.request.requirements[0].behavior.inputs:
            self.assertIn(
                f"requirement:logic_requirement:input:{observation.id}:source_correspondence_unspecified",
                self.assessment.diagnostics,
            )

    def test_independent_same_output_guard_rejects_bypassed_schema(self):
        request = product_request()
        other = replace(request.requirements[0], id="second_requirement")
        object.__setattr__(request, "requirements", (*request.requirements, other))
        with patch.object(CircuitRequest, "from_dict", return_value=request):
            with self.assertRaisesRegex(SerializationError, "unique output"):
                check_circuit_intent(request)

    def test_independent_shared_input_guard_rejects_bypassed_schema(self):
        request = product_request()
        initial = request.requirements[0]
        original = initial.behavior
        altered = replace(
            original.inputs[0],
            entity=replace(original.inputs[0].entity, isoform="other"),
        )
        observations = (altered, original.inputs[1])
        behavior = replace(
            original,
            inputs=observations,
            response=BooleanSpec(
                tuple(
                    CircuitSignal(item.id, item.fingerprint) for item in observations
                ),
                original.response.outputs,
            ),
            output=replace(
                original.output,
                id="other_product",
                observation=replace(original.output.observation, id="other_output"),
            ),
        )
        other = replace(initial, id="second_requirement", behavior=behavior)
        object.__setattr__(request, "requirements", (initial, other))
        with patch.object(CircuitRequest, "from_dict", return_value=request):
            with self.assertRaisesRegex(SerializationError, "shared circuit input"):
                check_circuit_intent(request)

    def test_physical_cross_requirement_satisfiability_remains_unestablished(self):
        self.assertIn(
            "cross_requirement_physical_satisfiability_unestablished",
            self.assessment.diagnostics,
        )

    def test_full_schema_length_ids_fit_receipts_and_composed_diagnostics(self):
        request = product_request()
        requirement = request.requirements[0]
        behavior = replace(
            requirement.behavior,
            dependencies=(
                replace(requirement.behavior.dependencies[0], id="p" * 16_384),
            ),
        )
        requirement = replace(requirement, id="r" * 16_384, behavior=behavior)
        request = replace(request, requirements=(requirement,))
        result = check_circuit_intent(request)
        self.assertTrue(any(len(item) > 2 * 16_384 for item in result.diagnostics))
        self.assertEqual(result.requirement_inventory[0].id, requirement.id)
        verify_circuit_intent(result, expected_request=request)

    def test_entity_quantity_compartment_and_output_edits_invalidate_authority(self):
        mutations = (
            (
                "input_entity",
                lambda data: data["requirements"][0]["behavior"]["inputs"][0][
                    "entity"
                ].update(isoform="changed"),
            ),
            (
                "quantity",
                lambda data: data["requirements"][0]["behavior"]["inputs"][0].update(
                    quantity="rna_abundance"
                ),
            ),
            (
                "compartment",
                lambda data: data["requirements"][0]["behavior"]["inputs"][0].update(
                    compartment="nucleus"
                ),
            ),
            (
                "output",
                lambda data: data["requirements"][0]["behavior"]["output"][
                    "observation"
                ]["entity"].update(accession="changed"),
            ),
        )
        for label, mutate in mutations:
            with self.subTest(label=label):
                data = reference_request().to_dict()
                mutate(data)
                with self.assertRaises(SerializationError):
                    CircuitRequest.from_dict(data)

    def test_full_source_location_edit_invalidates_saved_assessment(self):
        data = self.request.to_dict()
        build = data["profile"]["source_request"]["deployment_request"][
            "behavior_request"
        ]["build_request"]
        build["intent"]["nodes"][0]["source"]["line"] += 1
        changed = CircuitRequest.from_dict(data)
        self.assertEqual(
            changed.profile.source_request.fingerprint,
            self.request.profile.source_request.fingerprint,
        )
        with self.assertRaisesRegex(
            SerializationError, "independent complete authority"
        ):
            verify_circuit_intent(self.assessment, expected_request=changed)

    def test_original_shutdown_contract_edit_invalidates_saved_assessment(self):
        data = self.request.to_dict()
        data["profile"]["source_request"]["acceptance"]["shutdown"]["controllability"][
            "limitations"
        ] = "Changed unresolved actuator requirement."
        changed = CircuitRequest.from_dict(data)
        with self.assertRaisesRegex(
            SerializationError, "independent complete authority"
        ):
            verify_circuit_intent(self.assessment, expected_request=changed)

    def test_forged_or_omitted_source_receipts_reject_on_fresh_replay(self):
        for attack in (
            "omit_node",
            "omit_contract",
            "change_node_pin",
            "omit_diagnostic",
            "change_requirement_pin",
        ):
            with self.subTest(attack=attack):
                data = self.assessment.to_dict()
                if attack == "omit_node":
                    data["source_inventory"].pop()
                elif attack == "omit_contract":
                    data["contract_inventory"].pop()
                elif attack == "change_node_pin":
                    data["source_inventory"][0]["node_fingerprint"] = "a" * 64
                elif attack == "change_requirement_pin":
                    data["requirement_inventory"][0]["behavior_fingerprint"] = "a" * 64
                else:
                    data["diagnostics"].pop()
                saved = CircuitIntentAssessment.from_dict(data)
                with self.assertRaisesRegex(
                    SerializationError, "current independent checks"
                ):
                    verify_circuit_intent(saved, expected_request=self.request)

    def test_claim_promotion_and_extra_fields_reject_at_import(self):
        for field, value in (
            ("outcome", "pass"),
            ("molecular_implementation", "implemented"),
            ("empirical_validation", "verified"),
            ("human_therapeutic_admission", "admitted"),
            ("verified", True),
        ):
            with self.subTest(field=field):
                data = self.assessment.to_dict()
                data[field] = value
                with self.assertRaises(SerializationError):
                    CircuitIntentAssessment.from_dict(data)

    def test_old_checker_or_policy_version_requires_fresh_replay(self):
        for field in ("checker", "admission_policy", "request_schema"):
            with self.subTest(field=field):
                data = self.assessment.to_dict()
                data["dependencies"][field] = "historical.version"
                historical = CircuitIntentAssessment.from_dict(data)
                with self.assertRaisesRegex(
                    SerializationError, "current independent checks"
                ):
                    verify_circuit_intent(historical, expected_request=self.request)

    def test_complete_authority_is_required_not_hash_alone(self):
        with self.assertRaises(SerializationError):
            verify_circuit_intent(
                self.assessment, expected_request=self.request.fingerprint
            )

    def test_deployment_and_cell_accessibility_cannot_be_replaced(self):
        with self.assertRaises(SerializationError):
            replace(self.request, deployment_id="other_deployment")
        data = self.request.to_dict()
        data["requirements"][0]["behavior"]["inputs"][0]["scope"] = "evaluator"
        with self.assertRaises(SerializationError):
            CircuitRequest.from_dict(data)

    def test_checker_imports_no_producer_frontend_or_molecular_path(self):
        tree = ast.parse(Path(checker.__file__).read_text())
        modules = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        forbidden = (
            "biocompiler.compiler",
            "biocompiler.frontend",
            "biocompiler.ir.molecular",
            "biocompiler.semantics.evaluator",
        )
        self.assertFalse(any(module.startswith(forbidden) for module in modules))

    def test_record_resource_limits_and_duplicate_fields(self):
        with self.assertRaises(SerializationError):
            CircuitIntentAssessment.from_json('{"schema_version":1,"schema_version":2}')
        with self.assertRaises(SerializationError):
            CircuitIntentAssessment.from_json(
                " " * (checker.MAX_ASSESSMENT_JSON_BYTES + 1)
            )
        data = self.assessment.to_dict()
        data["source_inventory"] *= checker.MAX_RECEIPTS + 1
        with self.assertRaises(SerializationError):
            CircuitIntentAssessment.from_dict(data)

    def test_aggregate_import_rejects_before_any_json_encoder(self):
        data = self.assessment.to_dict()
        data["diagnostics"] = [
            "x" * checker.MAX_DIAGNOSTIC_TEXT_BYTES
        ] * checker.MAX_DIAGNOSTICS
        with patch(
            "biocompiler.ir.serialization.json.dumps",
            side_effect=AssertionError("Encoder must not run"),
        ):
            with self.assertRaisesRegex(SerializationError, "aggregate byte limit"):
                CircuitIntentAssessment.from_dict(data)

    def test_constructor_preflight_rejects_before_aggregate_json_encoding(self):
        # Unique strings pass per-field parsing but exceed the aggregate budget.
        diagnostics = tuple(f"{index}:" + "x" * 32000 for index in range(130))
        with patch.object(
            CircuitIntentAssessment,
            "to_json",
            side_effect=AssertionError("Aggregate encoder must not run"),
        ):
            with self.assertRaisesRegex(SerializationError, "aggregate byte limit"):
                replace(self.assessment, diagnostics=diagnostics)

    def test_aggregate_preflight_rejects_cycles_and_pending_explosion(self):
        cycle = {}
        cycle["self"] = cycle
        with self.assertRaisesRegex(SerializationError, "cyclic"):
            CircuitIntentAssessment.from_dict(cycle)
        too_many = {"items": [None] * checker.MAX_ASSESSMENT_ITEMS}
        with self.assertRaisesRegex(SerializationError, "pending item limit"):
            CircuitIntentAssessment.from_dict(too_many)


if __name__ == "__main__":
    unittest.main()
