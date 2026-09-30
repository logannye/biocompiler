"""Independent integration checks for complete declared circuit intent authority."""

from collections.abc import Mapping
from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir import circuit_intent as intent_ir
from biocompiler.ir import circuit_profile as profile_ir
from biocompiler.ir.circuit_intent import (
    CircuitBehavior,
    CircuitBehaviorExpectation,
    CircuitInputBinding,
    CircuitLifecycle,
    CircuitProviderRequirement,
    CircuitReferenceLock,
    CircuitRequest,
    CircuitRequirement,
    source_build_request,
    source_deployment,
)
from biocompiler.ir.circuit_logic import BooleanSpec, CircuitSignal
from biocompiler.ir.circuit_observations import (
    CircuitObservation,
    CircuitProduct,
    NumericInterval,
    ObservationEncoding,
    ObservationEntity,
    ObservationScope,
    ObservationWindow,
    ProductKind,
    QuantityKind,
)
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.intent import SourceLocation
from biocompiler.semantics.context import PayloadFormat
from examples.circuit_profile import make_profile_requests


REALIZATION = PinnedIdentity("reference", "software_boolean_fixture", "1", "c" * 64)
LOCATION = SourceLocation("tests/fixtures/software_circuit.py", 17, "define_circuit")


def observation(identity, **changes):
    values = {
        "id": identity,
        "entity": ObservationEntity("software_fixture", identity, "1", "unknown"),
        "quantity": QuantityKind.MIRNA_ACTIVITY,
        "compartment": "cytoplasm",
        "scope": ObservationScope.CELL_ACCESSIBLE,
        "window": ObservationWindow("software_origin", 1, 1, "h", "instant"),
        "encoding": ObservationEncoding("qualitative", "qualitative"),
    }
    values.update(changes)
    return CircuitObservation(**values)


def behavior(mask=8, **changes):
    inputs = (observation("A"), observation("B"))
    values = {
        "inputs": inputs,
        "response": BooleanSpec(
            tuple(CircuitSignal(item.id, item.fingerprint) for item in inputs),
            tuple(bool(mask & (1 << row)) for row in range(4)),
        ),
        "output": CircuitProduct(
            "reporter_requirement",
            ProductKind.REPORTER_FLUORESCENCE,
            observation("reporter_readout", quantity=QuantityKind.FLUORESCENCE),
        ),
        "lifecycle": CircuitLifecycle("readout"),
    }
    values.update(changes)
    return CircuitBehavior(**values)


def rebind_inputs(original, inputs):
    return replace(
        original,
        inputs=inputs,
        response=BooleanSpec(
            tuple(CircuitSignal(item.id, item.fingerprint) for item in inputs),
            original.response.outputs,
        ),
    )


def separate_output(requirement, identity):
    output = requirement.behavior.output
    return replace(
        requirement,
        id=identity,
        behavior=replace(
            requirement.behavior,
            output=replace(
                output,
                id=f"{identity}_product",
                observation=replace(output.observation, id=f"{identity}_observation"),
            ),
        ),
    )


def reference_lock(profile, requirements):
    return CircuitReferenceLock(
        tuple(
            CircuitBehaviorExpectation(item.id, item.behavior) for item in requirements
        ),
        REALIZATION,
        profile.source_experiment.sources,
        profile.source_experiment,
        "delivered_rna",
        "source_nominal",
    )


class CircuitIntentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profiles = make_profile_requests()

    def request(self, *, reference=False, exact=False, mask=8):
        profile = self.profiles["reference" if reference else "product"]
        if exact and not reference:
            profile = replace(
                profile,
                mode="exact_reproduction",
                source_experiment=self.profiles["reference"].source_experiment,
            )
        deployment = None if reference else source_deployment(profile.source_request)
        requirement = CircuitRequirement(
            "gate_requirement",
            behavior(mask),
            None if reference else deployment.recipient_role,
            () if reference else (deployment.recipient_role, "n000004", "n000008"),
            LOCATION,
            ()
            if reference
            else (
                CircuitInputBinding("B", "n000008"),
                CircuitInputBinding("A", "n000004"),
            ),
        )
        values = {
            "profile": profile,
            "requirements": (requirement,),
            "requested_form": "delivered_rna",
            "fidelity_scope": "source_nominal",
            "deployment_id": None if reference else deployment.id,
        }
        if reference or exact:
            values.update(
                selected_realization=REALIZATION,
                reference_lock=reference_lock(profile, (requirement,)),
            )
        return CircuitRequest(**values)

    def test_all_sixteen_truth_tables_roundtrip_as_product_and_reference_requests(self):
        for reference in (False, True):
            identities = set()
            for mask in range(16):
                with self.subTest(reference=reference, mask=mask):
                    request = self.request(reference=reference, mask=mask)
                    restored = CircuitRequest.from_json(request.to_json() + "\n")
                    self.assertEqual(restored.to_dict(), request.to_dict())
                    self.assertEqual(restored.fingerprint, request.fingerprint)
                    self.assertEqual(restored.requirements[0].id, "gate_requirement")
                    self.assertEqual(restored.requirements[0].source_location, LOCATION)
                    self.assertEqual(len(restored.requirements[0].behavior.inputs), 2)
                    identities.add(request.fingerprint)
            self.assertEqual(len(identities), 16)

    def test_product_retains_complete_original_acceptance_wrapper(self):
        request = self.request()
        original = self.profiles["product"].source_request
        self.assertEqual(request.profile.source_request.to_dict(), original.to_dict())
        self.assertEqual(request.profile.target.to_dict(), original.target.to_dict())
        restored = CircuitRequest.from_json(request.to_json())
        self.assertEqual(restored.profile.source_request.to_dict(), original.to_dict())
        self.assertEqual(restored.profile.recipient, self.profiles["product"].recipient)
        self.assertEqual(
            restored.deployment_id, original.deployment_request.deployment.id
        )
        self.assertEqual(
            restored.requirements[0].source_node_ids,
            (
                original.deployment_request.deployment.recipient_role,
                "n000004",
                "n000008",
            ),
        )

    def test_exact_lock_rejects_and_to_or_with_same_names_and_observations(self):
        for reference in (False, True):
            original = self.request(reference=reference, exact=True)
            changed = replace(original.requirements[0], behavior=behavior(mask=14))
            with self.assertRaisesRegex(SerializationError, "behavior differs"):
                replace(original, requirements=(changed,))
            data = original.to_dict()
            data["requirements"][0]["behavior"]["response"]["outputs"] = [
                False,
                True,
                True,
                True,
            ]
            with self.assertRaisesRegex(SerializationError, "behavior differs"):
                CircuitRequest.from_dict(data)

    def test_exact_lock_rejects_rebound_quantity_entity_compartment_unit_and_timing(
        self,
    ):
        original = self.request(reference=True)
        requirement = original.requirements[0]
        first, second = requirement.behavior.inputs
        variants = (
            replace(first, quantity=QuantityKind.RNA_ABUNDANCE),
            replace(first, entity=replace(first.entity, accession="different_entity")),
            replace(first, entity=replace(first.entity, version="unknown")),
            replace(first, entity=replace(first.entity, isoform="different_isoform")),
            replace(first, compartment="nucleus"),
            replace(first, window=replace(first.window, reference="another_origin")),
            replace(first, window=replace(first.window, start=1.0)),
        )
        for changed in variants:
            with self.subTest(observation=changed):
                new_behavior = rebind_inputs(requirement.behavior, (changed, second))
                with self.assertRaisesRegex(SerializationError, "behavior differs"):
                    replace(
                        original,
                        requirements=(replace(requirement, behavior=new_behavior),),
                    )

    def test_exact_lock_rejects_numeric_unit_or_threshold_edits(self):
        original = self.request(reference=True)
        requirement = original.requirements[0]
        low = NumericInterval(0, 1)
        high = NumericInterval(2, 3)
        encoding = ObservationEncoding("numeric", "fixture_units", low, high)
        inputs = (
            replace(requirement.behavior.inputs[0], encoding=encoding),
            requirement.behavior.inputs[1],
        )
        requirement = replace(
            requirement, behavior=rebind_inputs(requirement.behavior, inputs)
        )
        original = replace(
            original,
            requirements=(requirement,),
            reference_lock=reference_lock(original.profile, (requirement,)),
        )
        for changed_encoding in (
            replace(encoding, unit="different_units"),
            replace(encoding, high=NumericInterval(2.5, 3)),
        ):
            changed_behavior = rebind_inputs(
                requirement.behavior,
                (replace(inputs[0], encoding=changed_encoding), inputs[1]),
            )
            with self.assertRaisesRegex(SerializationError, "behavior differs"):
                replace(
                    original,
                    requirements=(replace(requirement, behavior=changed_behavior),),
                )

    def test_exact_lock_rejects_output_lifecycle_and_provider_edits(self):
        original = self.request(reference=True)
        requirement = original.requirements[0]
        old = requirement.behavior
        provider = CircuitProviderRequirement(
            "host_dependency",
            ObservationEntity("software_fixture", "cofactor", "1", "unknown"),
            "host",
            "cytoplasm",
            "software_group",
        )
        variants = (
            replace(
                old,
                output=replace(
                    old.output,
                    observation=replace(
                        old.output.observation,
                        entity=replace(
                            old.output.observation.entity, accession="reporter2"
                        ),
                    ),
                ),
            ),
            replace(
                old,
                lifecycle=replace(
                    old.lifecycle,
                    cessation=ObservationWindow("software_origin", 2, 3, "h", "all"),
                ),
            ),
            replace(old, dependencies=(provider,)),
        )
        for changed in variants:
            with self.assertRaisesRegex(SerializationError, "behavior differs"):
                replace(
                    original, requirements=(replace(requirement, behavior=changed),)
                )

    def test_exact_lock_pins_source_context_realization_form_and_fidelity(self):
        original = self.request(reference=True)
        variants = (
            {
                "selected_realization": replace(
                    REALIZATION, content_fingerprint="d" * 64
                )
            },
            {"selected_realization": replace(REALIZATION, id="another_realization")},
            {"selected_realization": None},
            {"requested_form": "processed_rna"},
            {"fidelity_scope": "base_identity"},
            {
                "profile": replace(
                    original.profile,
                    source_experiment=replace(
                        original.profile.source_experiment,
                        cell_state="changed declaration",
                    ),
                )
            },
        )
        for changes in variants:
            with self.subTest(changes=changes):
                with self.assertRaises(SerializationError):
                    replace(original, **changes)
        with self.assertRaisesRegex(SerializationError, "source pins"):
            replace(
                original.reference_lock,
                authority=(PinnedIdentity("source", "other", "1", "f" * 64),),
            )
        with self.assertRaisesRegex(SerializationError, "source/evidence"):
            replace(original.reference_lock, authority=(REALIZATION,))
        with self.assertRaisesRegex(SerializationError, "reference/model"):
            replace(original, selected_realization=original.reference_lock.authority[0])

    def test_reference_lock_covers_exactly_all_requirement_identities(self):
        original = self.request(reference=True)
        requirement = original.requirements[0]
        with self.assertRaisesRegex(SerializationError, "exactly all"):
            replace(original, requirements=(replace(requirement, id="renamed"),))
        with self.assertRaisesRegex(SerializationError, "exactly all"):
            replace(
                original,
                requirements=(requirement, separate_output(requirement, "additional")),
            )
        with self.assertRaises(SerializationError):
            replace(original.reference_lock, expected_behaviors=())

    def test_modes_do_not_silently_retain_or_create_reference_authority(self):
        candidate = self.request()
        exact = self.request(exact=True)
        with self.assertRaisesRegex(SerializationError, "cannot retain"):
            replace(candidate, reference_lock=exact.reference_lock)
        with self.assertRaisesRegex(
            SerializationError, "complete declared reference lock"
        ):
            replace(candidate, profile=exact.profile)
        with self.assertRaisesRegex(
            SerializationError, "complete declared reference lock"
        ):
            replace(exact, reference_lock=None)
        with self.assertRaisesRegex(SerializationError, "experiment context"):
            replace(exact, profile=replace(exact.profile, source_experiment=None))
        self.assertIsNone(candidate.reference_lock)
        self.assertIsNone(candidate.selected_realization)

    def test_target_modality_requested_form_and_fidelity_are_strict(self):
        candidate = self.request()
        for form in ("delivered_dna", "dna_expression_template", "unknown", [], None):
            with self.assertRaises(SerializationError):
                replace(candidate, requested_form=form)
        for fidelity in ("verified", "", [], None):
            with self.assertRaises(SerializationError):
                replace(candidate, fidelity_scope=fidelity)
        reference = self.request(reference=True)
        changed_profile = replace(reference.profile, molecular_form=PayloadFormat.DNA)
        with self.assertRaisesRegex(SerializationError, "modality"):
            replace(reference, profile=changed_profile)

    def test_product_requires_original_source_and_explicit_correct_deployment(self):
        original = self.request()
        with self.assertRaisesRegex(SerializationError, "original frozen source"):
            replace(original, profile=replace(original.profile, source_request=None))
        for identity in (None, "", "different_deployment"):
            with self.assertRaises(SerializationError):
                replace(original, deployment_id=identity)

    def test_product_role_and_source_nodes_must_match_authoritative_original(self):
        original = self.request()
        requirement = original.requirements[0]
        for role in (None, "missing_role", "n000002", "n000004"):
            with self.assertRaisesRegex(SerializationError, "in-vivo engineered role"):
                replace(original, requirements=(replace(requirement, role_id=role),))
        for refs in ((), ("n000004",), (requirement.role_id, "absent_node")):
            with self.assertRaises(SerializationError):
                replace(
                    original, requirements=(replace(requirement, source_node_ids=refs),)
                )

    def test_source_nodes_cannot_smuggle_a_different_role_declaration(self):
        original = self.request()
        source = source_build_request(original.profile.source_request)
        role = source.intent.nodes[0]
        second_role = replace(role, id="other_role")
        source = replace(
            source,
            intent=replace(source.intent, nodes=source.intent.nodes + (second_role,)),
        )
        profile = replace(original.profile, source_request=source)
        requirement = original.requirements[0]
        changed = replace(
            requirement,
            source_node_ids=(requirement.role_id, second_role.id),
            input_bindings=(),
        )
        with self.assertRaisesRegex(SerializationError, "different-role"):
            replace(original, profile=profile, requirements=(changed,))

    def test_input_source_correspondence_survives_roundtrip_and_swaps_change_identity(
        self,
    ):
        original = self.request()
        requirement = original.requirements[0]
        self.assertEqual(
            requirement.input_bindings,
            (CircuitInputBinding("A", "n000004"), CircuitInputBinding("B", "n000008")),
        )
        restored = CircuitRequest.from_json(original.to_json())
        self.assertEqual(
            restored.requirements[0].input_bindings, requirement.input_bindings
        )
        changed = replace(
            requirement,
            input_bindings=(
                CircuitInputBinding("A", "n000008"),
                CircuitInputBinding("B", "n000004"),
            ),
        )
        swapped = replace(original, requirements=(changed,))
        self.assertEqual(
            swapped.requirements[0].source_node_ids, requirement.source_node_ids
        )
        self.assertNotEqual(swapped.fingerprint, original.fingerprint)
        self.assertEqual(swapped.requirements[0].behavior, requirement.behavior)
        for subset in ((), (requirement.input_bindings[0],)):
            self.assertEqual(
                replace(requirement, input_bindings=subset).input_bindings, subset
            )

    def test_input_source_bindings_are_frozen_strict_bounded_unique_and_canonical(self):
        requirement = self.request().requirements[0]
        bindings = list(reversed(requirement.input_bindings))
        copied = replace(requirement, input_bindings=bindings)
        bindings.clear()
        self.assertEqual(copied.input_bindings, requirement.input_bindings)
        with self.assertRaises(FrozenInstanceError):
            copied.input_bindings[0].source_node_id = "different"
        for bindings in (
            None,
            ["not a binding"],
            [requirement.input_bindings[0]] * 2,
            [requirement.input_bindings[0]] * 9,
            (CircuitInputBinding("missing_observation", "n000004"),),
            (CircuitInputBinding("A", "missing_source_reference"),),
        ):
            with self.subTest(bindings=bindings):
                with self.assertRaises(SerializationError):
                    replace(requirement, input_bindings=bindings)
        for key in ("observation_id", "source_node_id"):
            for value in (None, "", True, [], "invalid\nidentity"):
                with self.assertRaises(SerializationError):
                    replace(requirement.input_bindings[0], **{key: value})
        data = requirement.to_dict()
        data["input_bindings"] *= 5
        with self.assertRaises(SerializationError):
            CircuitRequirement.from_dict(data)

    def test_input_binding_nodes_are_validated_against_original_product_graph(self):
        original = self.request()
        requirement = original.requirements[0]
        changed = replace(
            requirement,
            source_node_ids=(*requirement.source_node_ids, "absent_node"),
            input_bindings=(CircuitInputBinding("A", "absent_node"),),
        )
        with self.assertRaisesRegex(SerializationError, "source-node"):
            replace(original, requirements=(changed,))
        source = source_build_request(original.profile.source_request)
        second_role = replace(source.intent.nodes[0], id="other_role")
        source = replace(
            source,
            intent=replace(source.intent, nodes=source.intent.nodes + (second_role,)),
        )
        profile = replace(original.profile, source_request=source)
        changed = replace(
            requirement,
            source_node_ids=(*requirement.source_node_ids, second_role.id),
            input_bindings=(CircuitInputBinding("A", second_role.id),),
        )
        with self.assertRaisesRegex(SerializationError, "different-role"):
            replace(original, profile=profile, requirements=(changed,))

    def test_human_reference_cannot_carry_therapeutic_input_source_bindings(self):
        original = self.request(reference=True)
        requirement = replace(
            original.requirements[0],
            source_node_ids=("invented_node",),
            input_bindings=(CircuitInputBinding("A", "invented_node"),),
        )
        with self.assertRaisesRegex(SerializationError, "invented therapeutic roles"):
            replace(original, requirements=(requirement,))

    def test_input_output_and_provider_compartments_must_exist_in_target(self):
        original = self.request()
        requirement = original.requirements[0]
        old = requirement.behavior
        changed_input = rebind_inputs(
            old, (replace(old.inputs[0], compartment="nucleus"), old.inputs[1])
        )
        changed_output = replace(
            old,
            output=replace(
                old.output,
                observation=replace(old.output.observation, compartment="nucleus"),
            ),
        )
        changed_provider = replace(
            old,
            dependencies=(
                CircuitProviderRequirement(
                    "provider", old.inputs[0].entity, "host", "nucleus", "group"
                ),
            ),
        )
        for changed in (changed_input, changed_output, changed_provider):
            with self.assertRaisesRegex(SerializationError, "target compartment"):
                replace(
                    original, requirements=(replace(requirement, behavior=changed),)
                )

    def test_reference_cannot_invent_a_therapeutic_role_or_deployment(self):
        original = self.request(reference=True)
        requirement = original.requirements[0]
        with self.assertRaisesRegex(SerializationError, "deployment identity"):
            replace(original, deployment_id="invented")
        for changes in ({"role_id": "invented"}, {"source_node_ids": ("invented",)}):
            with self.assertRaisesRegex(
                SerializationError, "invented therapeutic roles"
            ):
                replace(original, requirements=(replace(requirement, **changes),))
        with self.assertRaises(SerializationError):
            replace(original.profile, target=self.profiles["product"].target)

    def test_behavior_requires_cell_accessible_complete_signal_bindings(self):
        original = behavior()
        first, second = original.inputs
        with self.assertRaisesRegex(SerializationError, "exactly the declared"):
            replace(original, inputs=(first,))
        with self.assertRaisesRegex(SerializationError, "different nominal"):
            replace(original, inputs=(replace(first, compartment="nucleus"), second))
        for scope in (ObservationScope.EVALUATOR, ObservationScope.EXTERNAL):
            with self.assertRaisesRegex(SerializationError, "cell-accessible"):
                rebind_inputs(original, (replace(first, scope=scope), second))
        for mask in (0, 15):
            self.assertEqual(len(behavior(mask).inputs), 2)
        constant = behavior(inputs=(), response=BooleanSpec.constant(True))
        self.assertEqual(constant.inputs, ())

    def test_feedback_aliases_and_output_lifecycle_category_errors_are_rejected(self):
        original = behavior()
        with self.assertRaisesRegex(SerializationError, "Feedback"):
            replace(
                original,
                output=replace(
                    original.output,
                    observation=replace(original.output.observation, id="A"),
                ),
            )
        for mode in ("production_control", "abundance_control", "activity_control"):
            with self.assertRaisesRegex(SerializationError, "lifecycle mode"):
                replace(original, lifecycle=CircuitLifecycle(mode))

    def test_same_role_duplicate_outputs_reject_opposing_boolean_obligations(self):
        original = self.request()
        first = replace(
            original.requirements[0], id="always_high", behavior=behavior(15)
        )
        second = replace(first, id="always_low", behavior=behavior(0))
        with self.assertRaisesRegex(SerializationError, "Output product IDs.*unique"):
            replace(original, requirements=(first, second))
        second = replace(
            second,
            behavior=replace(
                second.behavior,
                output=replace(second.behavior.output, id="another_product"),
            ),
        )
        with self.assertRaisesRegex(
            SerializationError, "Output observation IDs.*unique"
        ):
            replace(original, requirements=(first, second))
        first_reference = replace(
            first, role_id=None, source_node_ids=(), input_bindings=()
        )
        second_reference = replace(
            second, role_id=None, source_node_ids=(), input_bindings=()
        )
        reference = self.request(reference=True)
        with self.assertRaisesRegex(
            SerializationError, "Output observation IDs.*unique"
        ):
            replace(
                reference,
                requirements=(first_reference, second_reference),
                reference_lock=reference_lock(
                    reference.profile, (first_reference, second_reference)
                ),
            )

    def test_same_role_shared_inputs_require_identical_nominal_authority(self):
        original = self.request()
        first = original.requirements[0]
        second = separate_output(first, "second_requirement")
        accepted = replace(original, requirements=(first, second))
        self.assertEqual(
            accepted.requirements[0].behavior.inputs,
            accepted.requirements[1].behavior.inputs,
        )
        initial = second.behavior.inputs[0]
        for observation in (
            replace(
                initial, entity=replace(initial.entity, accession="another_entity")
            ),
            replace(initial, quantity=QuantityKind.RNA_ABUNDANCE),
            replace(initial, compartment="extracellular"),
            replace(initial, window=replace(initial.window, start=1.0)),
        ):
            second_behavior = rebind_inputs(
                second.behavior, (observation, second.behavior.inputs[1])
            )
            with self.assertRaisesRegex(
                SerializationError, "Shared input observation IDs"
            ):
                replace(
                    original,
                    requirements=(first, replace(second, behavior=second_behavior)),
                )

    def test_different_roles_may_reuse_local_input_and_output_identities(self):
        original = self.request()
        source = source_build_request(original.profile.source_request)
        second_role = replace(source.intent.nodes[0], id="second_role")
        source = replace(
            source,
            intent=replace(source.intent, nodes=source.intent.nodes + (second_role,)),
        )
        profile = replace(original.profile, source_request=source)
        first = original.requirements[0]
        changed_input = replace(
            first.behavior.inputs[0],
            entity=replace(
                first.behavior.inputs[0].entity, accession="role_specific_input"
            ),
        )
        second = replace(
            first,
            id="second_role_requirement",
            role_id=second_role.id,
            source_node_ids=(second_role.id,),
            input_bindings=(),
            behavior=rebind_inputs(
                first.behavior, (changed_input, first.behavior.inputs[1])
            ),
        )
        accepted = replace(original, profile=profile, requirements=(first, second))
        self.assertEqual(len(accepted.requirements), 2)
        self.assertEqual(first.behavior.output, second.behavior.output)
        self.assertNotEqual(first.behavior.inputs[0], second.behavior.inputs[0])
        self.assertEqual(CircuitRequest.from_json(accepted.to_json()), accepted)

    def test_records_are_frozen_canonical_and_snapshot_mutable_input_arrays(self):
        candidate = self.request()
        requirement = candidate.requirements[0]
        later = replace(
            separate_output(requirement, "z_requirement"),
            source_location=replace(LOCATION, line=27),
        )
        requirements = [later, requirement]
        changed = replace(candidate, requirements=requirements)
        requirements.clear()
        self.assertEqual(
            tuple(item.id for item in changed.requirements), (requirement.id, later.id)
        )
        self.assertEqual(CircuitRequest.from_json(changed.to_json()), changed)
        moved = replace(requirement, source_location=replace(LOCATION, line=18))
        self.assertEqual(moved.id, requirement.id)
        self.assertNotEqual(moved.fingerprint, requirement.fingerprint)
        for record, field in (
            (changed, "requirements"),
            (requirement, "id"),
            (requirement.behavior, "response"),
        ):
            with self.assertRaises(FrozenInstanceError):
                setattr(record, field, None)
        with self.assertRaisesRegex(SerializationError, "Duplicate"):
            replace(candidate, requirements=(requirement, requirement))

    def test_strict_roundtrips_for_every_new_artifact_schema(self):
        exact = self.request(reference=True)
        requirement = exact.requirements[0]
        provider = CircuitProviderRequirement(
            "host", requirement.behavior.inputs[0].entity, "host", "cytoplasm", "group"
        )
        records = (
            exact,
            exact.reference_lock,
            exact.reference_lock.expected_behaviors[0],
            requirement,
            requirement.behavior,
            requirement.behavior.lifecycle,
            provider,
            CircuitInputBinding("A", "n000004"),
        )
        for record in records:
            self.assertEqual(type(record).from_json(record.to_json()), record)
            for key in record.to_dict():
                data = record.to_dict()
                del data[key]
                with self.subTest(schema=type(record).__name__, missing=key):
                    with self.assertRaises(SerializationError):
                        type(record).from_dict(data)
            for extra in ({"schema_version": "unrecognized"}, {"extra": "field"}):
                with self.assertRaises(SerializationError):
                    type(record).from_dict(record.to_dict() | extra)

    def test_hostile_imports_and_record_counts_are_bounded_before_decoding(self):
        original = self.request()
        data = original.to_dict()
        data["requirements"] *= intent_ir.MAX_REQUIREMENTS + 1
        with self.assertRaises(SerializationError):
            CircuitRequest.from_dict(data)
        for field, value in (
            ("requirements", []),
            ("requirements", None),
            ("profile", None),
        ):
            with self.assertRaises(SerializationError):
                CircuitRequest.from_dict(original.to_dict() | {field: value})
        deep = None
        for _ in range(profile_ir.MAX_PROFILE_DEPTH + 2):
            deep = [deep]
        oversized = {"unused": [None] * profile_ir.MAX_PROFILE_ITEMS}
        for payload in (deep, oversized, {"unused": object()}, {1: True}):
            with patch.object(
                CircuitBehavior,
                "from_dict",
                side_effect=AssertionError("decoded too early"),
            ):
                with self.assertRaises(SerializationError):
                    CircuitRequest.from_dict(payload)
        with self.assertRaises(SerializationError):
            CircuitRequest.from_json(" " * (profile_ir.MAX_PROFILE_JSON_BYTES + 1))
        duplicate = original.to_json()[:-1] + ', "schema_version": "duplicate"}'
        with self.assertRaises(SerializationError):
            CircuitRequest.from_json(duplicate)
        for text in ("NaN", "Infinity", "\ud800"):
            with self.assertRaises(SerializationError):
                CircuitRequest.from_json(text)

    def test_huge_mapping_is_rejected_before_iteration(self):
        class HugeMapping(Mapping):
            def __len__(self):
                return profile_ir.MAX_PROFILE_ITEMS

            def __iter__(self):
                raise AssertionError("must reject size before iteration")

            def __getitem__(self, key):
                raise AssertionError("must reject size before iteration")

        with self.assertRaisesRegex(SerializationError, "item limit"):
            CircuitRequest.from_dict(HugeMapping())


if __name__ == "__main__":
    unittest.main()
