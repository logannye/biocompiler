"""Cell-scoped circuit authoring preserves complete original graph authority."""

from dataclasses import FrozenInstanceError, replace
import unittest
from unittest.mock import patch

from biocompiler.compiler.request import BuildRequest
from biocompiler.errors import SerializationError
from biocompiler.frontend.api import Therapy
from biocompiler.frontend.circuits import CircuitBuilder
from biocompiler.ir.circuit_intent import (
    CircuitBehaviorExpectation,
    CircuitInputBinding,
    CircuitLifecycle,
    CircuitReferenceLock,
    CircuitRequest,
)
from biocompiler.ir.circuit_logic import CircuitSignal
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
from biocompiler.ir.circuit_profile import (
    CircuitProfileRequest,
    ImmuneLineage,
    ImmuneRecipientIdentity,
)
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.intent import SourceLocation
from biocompiler.semantics.context import PayloadFormat
from examples.circuit_profile import make_profile_requests
from examples.human_target import make_human_target


def source_fixture():
    therapy = Therapy("software-source")
    cells = therapy.engineer("worker", cell_type="human_T_cell")
    cue = cells.internal.signal("cue")
    rule = cells.when(cue > 0).do(cells.report("software-rule"))
    return therapy, cells, cue, rule


def profile_for(therapy):
    target = make_human_target()
    source = BuildRequest.freeze(therapy.freeze(), target=target)
    return CircuitProfileRequest(
        "human_immune_payload",
        "candidate_design",
        PayloadFormat.RNA,
        "planning",
        target=target,
        recipient=ImmuneRecipientIdentity(
            ImmuneLineage.T_CELL,
            target.fingerprint,
            target.human_target.cell_subtype.fingerprint,
        ),
        source_request=source,
    )


def observation(id="A", quantity=QuantityKind.MIRNA_ACTIVITY):
    return CircuitObservation(
        id,
        ObservationEntity("software_fixture", id, "1", "unknown"),
        quantity,
        "cytoplasm",
        ObservationScope.CELL_ACCESSIBLE,
        ObservationWindow("unknown", None, None, "unknown", "unknown"),
        ObservationEncoding("qualitative", "qualitative"),
    )


def product():
    return CircuitProduct(
        "software-output",
        ProductKind.REPORTER_FLUORESCENCE,
        observation("output", QuantityKind.FLUORESCENCE),
    )


def freeze(builder, profile=None, **kwargs):
    values = dict(
        requested_form="delivered_rna",
        fidelity_scope="source_nominal",
        deployment_id="software-deployment",
    )
    values.update(kwargs)
    return builder.freeze(profile, **values)


class CircuitFrontendTests(unittest.TestCase):
    def test_cell_and_frozen_builders_produce_equivalent_authority_without_graph_mutation(
        self,
    ):
        therapy, cells, cue, rule = source_fixture()
        profile = profile_for(therapy)
        before = therapy.freeze().to_dict()
        live = CircuitBuilder.for_cells(cells, "authoring-label")
        frozen = CircuitBuilder("authoring-label", profile, role_id=cells.role)
        location = SourceLocation("software_fixture.py", 1, "author")
        with patch(
            "biocompiler.frontend.circuits.capture_source", return_value=location
        ):
            for builder, reference, source in (
                (live, cue, rule),
                (frozen, cue.node_id, rule.node_id),
            ):
                signal = builder.observe(observation(), source=reference)
                result = builder.require(
                    "response",
                    signal,
                    product(),
                    lifecycle=CircuitLifecycle("readout"),
                    source=(source,),
                )
                self.assertEqual(result.source_location, location)
                self.assertEqual(
                    set(result.source_node_ids), {cells.role, cue.node_id, rule.node_id}
                )
                self.assertEqual(
                    result.input_bindings, (CircuitInputBinding("A", cue.node_id),)
                )
        self.assertEqual(therapy.freeze().to_dict(), before)
        live_result = freeze(live, profile)
        frozen_result = freeze(frozen)
        self.assertEqual(live_result.to_dict(), frozen_result.to_dict())
        self.assertEqual(live_result.fingerprint, frozen_result.fingerprint)
        self.assertEqual(CircuitRequest.from_json(live_result.to_json()), live_result)
        self.assertEqual(therapy.freeze().to_dict(), before)

    def test_swapped_source_associations_change_frozen_identity(self):
        therapy, cells, cue_a, _ = source_fixture()
        cue_b = cells.internal.signal("second-cue")
        cells.when(cue_b > 0).do(cells.report("second-software-rule"))
        profile = profile_for(therapy)
        original_graph = therapy.freeze().to_dict()
        requests = []
        location = SourceLocation("software_fixture.py", 1, "author")
        with patch(
            "biocompiler.frontend.circuits.capture_source", return_value=location
        ):
            for first, second in ((cue_a, cue_b), (cue_b, cue_a)):
                builder = CircuitBuilder.for_cells(cells, "circuit")
                a = builder.observe(observation("A"), source=first)
                b = builder.observe(observation("B"), source=second)
                requirement = builder.require(
                    "response", a & ~b, product(), lifecycle=CircuitLifecycle("readout")
                )
                self.assertEqual(
                    requirement.input_bindings,
                    (
                        CircuitInputBinding("A", first.node_id),
                        CircuitInputBinding("B", second.node_id),
                    ),
                )
                request = freeze(builder, profile)
                restored = CircuitRequest.from_json(request.to_json())
                self.assertEqual(restored.to_dict(), request.to_dict())
                self.assertEqual(
                    restored.requirements[0].input_bindings, requirement.input_bindings
                )
                requests.append(request)
        self.assertEqual(
            requests[0].requirements[0].source_node_ids,
            requests[1].requirements[0].source_node_ids,
        )
        self.assertEqual(
            requests[0].requirements[0].behavior, requests[1].requirements[0].behavior
        )
        self.assertEqual(
            requests[0].requirements[0].source_location,
            requests[1].requirements[0].source_location,
        )
        self.assertNotEqual(requests[0].fingerprint, requests[1].fingerprint)
        self.assertEqual(therapy.freeze().to_dict(), original_graph)

    def test_cell_program_public_circuit_method(self):
        therapy, cells, cue, _ = source_fixture()
        before = therapy.freeze().to_dict()
        builder = cells.circuit("public-authoring")
        self.assertIsInstance(builder, CircuitBuilder)
        signal = builder.observe(observation(), source=cue)
        builder.require(
            "response", signal, product(), lifecycle=CircuitLifecycle("readout")
        )
        result = freeze(builder, profile_for(therapy))
        self.assertEqual(result.requirements[0].role_id, cells.role)
        self.assertEqual(
            result.requirements[0].input_bindings,
            (CircuitInputBinding("A", cue.node_id),),
        )
        self.assertEqual(therapy.freeze().to_dict(), before)

    def test_source_location_is_captured_at_requirement_call(self):
        therapy, cells, _, _ = source_fixture()
        builder = CircuitBuilder.for_cells(cells, "circuit")
        signal = builder.observe(observation())
        requirement = builder.require(
            "response", signal, product(), lifecycle=CircuitLifecycle("readout")
        )
        self.assertTrue(
            requirement.source_location.file.endswith("test_circuit_frontend.py")
        )
        self.assertEqual(
            requirement.source_location.function,
            "test_source_location_is_captured_at_requirement_call",
        )
        self.assertEqual(requirement.source_node_ids, (cells.role,))
        freeze(builder, profile_for(therapy))

    def test_registered_obligations_retained_even_after_boolean_simplification(self):
        therapy, cells, cue, _ = source_fixture()
        builder = CircuitBuilder.for_cells(cells, "circuit")
        signal = builder.observe(observation(), source=cue)
        result = builder.require(
            "always", signal & False, product(), lifecycle=CircuitLifecycle("readout")
        )
        self.assertEqual(result.behavior.inputs, (observation(),))
        self.assertEqual(result.behavior.response.inputs, (signal,))
        self.assertIn(cue.node_id, result.source_node_ids)
        freeze(builder, profile_for(therapy))

    def test_frozen_profile_substitution_and_live_missing_profile_rejected(self):
        therapy, cells, _, _ = source_fixture()
        profile = profile_for(therapy)
        frozen = CircuitBuilder("circuit", profile, role_id=cells.role)
        signal = frozen.observe(observation())
        frozen.require(
            "response", signal, product(), lifecycle=CircuitLifecycle("readout")
        )
        self.assertEqual(freeze(frozen).profile, profile)
        self.assertEqual(
            freeze(frozen, CircuitProfileRequest.from_json(profile.to_json())).profile,
            profile,
        )
        with self.assertRaisesRegex(SerializationError, "substitute"):
            freeze(frozen, replace(profile, boundary="verification"))
        live = CircuitBuilder.for_cells(cells, "circuit")
        with self.assertRaisesRegex(SerializationError, "profile at freeze"):
            freeze(live)

    def test_live_graph_edits_after_original_freeze_are_rejected(self):
        therapy, cells, _, _ = source_fixture()
        profile = profile_for(therapy)
        builder = CircuitBuilder.for_cells(cells, "circuit")
        signal = builder.observe(observation())
        builder.require(
            "response", signal, product(), lifecycle=CircuitLifecycle("readout")
        )
        therapy.goal("new-obligation")
        with self.assertRaisesRegex(SerializationError, "Live graph differs"):
            freeze(builder, profile)

    def test_graph_source_location_only_edits_are_not_silently_accepted(self):
        therapy, cells, _, _ = source_fixture()
        profile = profile_for(therapy)
        builder = CircuitBuilder.for_cells(cells, "circuit")
        signal = builder.observe(observation())
        builder.require(
            "response", signal, product(), lifecycle=CircuitLifecycle("readout")
        )
        node = therapy._graph.get(cells.node_id)
        therapy._graph._nodes[cells.node_id] = replace(
            node, source=SourceLocation("elsewhere.py", 99)
        )
        self.assertEqual(
            therapy.freeze().fingerprint, profile.source_request.intent.fingerprint
        )
        with self.assertRaisesRegex(SerializationError, "including source locations"):
            freeze(builder, profile)

    def test_other_graph_other_role_and_unrooted_source_handles_rejected(self):
        therapy, cells, cue, _ = source_fixture()
        other = therapy.engineer("other", cell_type="human_T_cell")
        other_cue = other.internal.signal("other-cue")
        _, _, foreign_cue, _ = source_fixture()
        builder = CircuitBuilder.for_cells(cells, "circuit")
        for source in (other, other_cue, foreign_cue, cue.node_id, object()):
            with self.subTest(source=repr(source)):
                with self.assertRaises(SerializationError):
                    builder.observe(observation(), source=source)
        unrooted = cells.internal.signal("not-part-of-original")
        profile = profile_for(therapy)
        signal = builder.observe(observation(), source=unrooted)
        builder.require(
            "response", signal, product(), lifecycle=CircuitLifecycle("readout")
        )
        with self.assertRaisesRegex(SerializationError, "source-node"):
            freeze(builder, profile)

    def test_frozen_source_links_must_be_original_node_identities(self):
        therapy, cells, cue, _ = source_fixture()
        other = therapy.engineer("other", cell_type="human_T_cell")
        profile = profile_for(therapy)
        builder = CircuitBuilder("circuit", profile, role_id=cells.role)
        for source in ("missing", cue, other.node_id):
            with self.subTest(source=repr(source)):
                with self.assertRaises(SerializationError):
                    builder.observe(observation(), source=source)
        self.assertEqual(builder.observe(observation(), source=cue.node_id).id, "A")

    def test_duplicate_registration_requirements_and_source_links_rejected_atomically(
        self,
    ):
        therapy, cells, cue, _ = source_fixture()
        builder = CircuitBuilder.for_cells(cells, "circuit")
        signal = builder.observe(observation())
        with self.assertRaisesRegex(
            SerializationError, "Duplicate circuit observation"
        ):
            builder.observe(observation())
        with self.assertRaisesRegex(SerializationError, "Duplicate explicit source"):
            builder.require(
                "response",
                signal,
                product(),
                lifecycle=CircuitLifecycle("readout"),
                source=(cue, cue),
            )
        self.assertEqual(builder.requirements, ())
        result = builder.require(
            "response", signal, product(), lifecycle=CircuitLifecycle("readout")
        )
        snapshot = builder.requirements
        with self.assertRaisesRegex(
            SerializationError, "Duplicate circuit requirement"
        ):
            builder.require(
                "response", signal, product(), lifecycle=CircuitLifecycle("readout")
            )
        self.assertEqual(snapshot, (result,))
        with self.assertRaises(FrozenInstanceError):
            result.id = "changed"
        second_product = replace(
            product(),
            id="second-software-output",
            observation=observation("second_output", QuantityKind.FLUORESCENCE),
        )
        builder.require(
            "second", signal, second_product, lifecycle=CircuitLifecycle("readout")
        )
        self.assertEqual(snapshot, (result,))
        self.assertEqual(len(builder.requirements), 2)
        freeze(builder, profile_for(therapy))

    def test_unregistered_and_changed_response_bindings_are_rejected(self):
        _, cells, _, _ = source_fixture()
        builder = CircuitBuilder.for_cells(cells, "circuit")
        registered = builder.observe(observation())
        for response in (
            CircuitSignal("missing", "a" * 64),
            CircuitSignal(registered.id, "b" * 64),
            True,
        ):
            with self.assertRaises(SerializationError):
                builder.require(
                    "response",
                    response,
                    product(),
                    lifecycle=CircuitLifecycle("readout"),
                )
        self.assertEqual(builder.requirements, ())

    def test_reference_builder_uses_lock_and_has_no_therapeutic_source(self):
        profile = make_profile_requests()["reference"]
        builder = CircuitBuilder("software-reference", profile)
        signal = builder.observe(observation())
        requirement = builder.require(
            "response", signal, product(), lifecycle=CircuitLifecycle("readout")
        )
        self.assertIsNone(requirement.role_id)
        self.assertEqual(requirement.source_node_ids, ())
        realization = PinnedIdentity("reference", "software-realization", "1", "a" * 64)
        lock = CircuitReferenceLock(
            (CircuitBehaviorExpectation(requirement.id, requirement.behavior),),
            realization,
            profile.source_experiment.sources,
            profile.source_experiment,
            "delivered_rna",
            "source_nominal",
        )
        result = freeze(
            builder,
            deployment_id=None,
            selected_realization=realization,
            reference_lock=lock,
        )
        self.assertEqual(result.reference_lock, lock)
        with self.assertRaisesRegex(SerializationError, "cannot invent"):
            CircuitBuilder("reference", profile, role_id="invented")
        with self.assertRaisesRegex(SerializationError, "therapeutic source"):
            builder.observe(observation("B"), source="invented")
        with self.assertRaises(SerializationError):
            freeze(builder, deployment_id=None)

    def test_product_builder_requires_full_source_and_explicit_existing_role(self):
        therapy, cells, _, _ = source_fixture()
        profile = profile_for(therapy)
        for role in (None, "missing"):
            with self.assertRaises(SerializationError):
                CircuitBuilder("circuit", profile, role_id=role)
        with self.assertRaisesRegex(SerializationError, "original source"):
            CircuitBuilder(
                "circuit", replace(profile, source_request=None), role_id=cells.role
            )
        with self.assertRaises(SerializationError):
            CircuitBuilder.for_cells(object(), "circuit")


if __name__ == "__main__":
    unittest.main()
