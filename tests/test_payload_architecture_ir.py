"""Bounded immutable composite authority, without implementation inference."""

from dataclasses import replace
import unittest

import biocompiler as bc
from biocompiler.compiler.behavior import lower_to_behavior
from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.payload_architecture import (
    ArchitectureBinding, ArchitectureChannel, ArchitectureConnection, ArchitectureControl,
    ArchitectureHelper, ArchitecturePlacement, ControlRequirement,
    PayloadArchitectureLibrary, PayloadArchitectureRefinement,
    RecipientDeliveryGroup, RNAArchitectureConstraints,
)
from examples.executable_payload import artificial_template
from test_payload_contracts import executable_component


def refinement():
    therapy = bc.Therapy("independent_supplied_model")
    cell = therapy.engineer("recipient", cell_type="human_T_cell")
    trigger = cell.environment.signal("context").present()
    cell.when(trigger).do(cell.secrete("artificial_alpha"), cell.secrete("artificial_beta"))
    behavior = lower_to_behavior(therapy.freeze())
    owned = tuple(node.id for node in behavior.nodes if node.kind == "rule" or node.kind.startswith("action."))
    component = replace(executable_component(), id="composite", classification="modeled_component",
                        implementation_role="composite_behavior", synthetic_model=None,
                        identities=(PinnedIdentity("model", "composite", "1", behavior.fingerprint),))
    template = artificial_template("one-rna", cell.node_id)
    return PayloadArchitectureRefinement(
        "whole-pattern", "1", behavior, {node.id: node.id for node in behavior.nodes}, owned,
        (component,), (template,), (ArchitectureBinding("binding", owned, (component.id,), (template.id,), ("delivery",)),),
        (ArchitecturePlacement("delivery", template.id, "payload", cell.node_id, "cytoplasm", "same-cell"),),
        ("Artificial material is conditionally assumed to implement the full supplied model.",))


class ArchitectureContractTests(unittest.TestCase):
    def test_roundtrip_complete_model_and_many_outputs_one_rna(self):
        original = refinement()
        restored = PayloadArchitectureRefinement.from_json(original.to_json())
        self.assertEqual(restored, original)
        self.assertEqual(restored.fingerprint, original.fingerprint)
        self.assertEqual(len([node for node in original.behavior.nodes if node.kind == "action.secrete"]), 2)
        self.assertEqual(len(original.templates[0].output_members), 1)
        with self.assertRaises(TypeError):
            original.source_bindings[original.owned_node_ids[0]] = "different"

    def test_one_function_can_own_multiple_component_and_rna_records(self):
        original = refinement()
        component = replace(original.components[0], id="second-component")
        template = replace(original.templates[0], id="second-rna")
        expanded = replace(original, components=(*original.components, component),
                           templates=(*original.templates, template),
                           bindings=(replace(original.bindings[0],
                               component_ids=("composite", component.id), template_ids=("one-rna", template.id),
                               placement_ids=("delivery", "second-delivery")),),
                           placements=(*original.placements, replace(original.placements[0],
                               id="second-delivery", template_id=template.id)))
        self.assertEqual(len(expanded.bindings[0].component_ids), 2)
        self.assertEqual(len(expanded.bindings[0].template_ids), 2)

    def test_bindings_require_exact_member_placements(self):
        original = refinement()
        with self.assertRaisesRegex(SerializationError, "placement_ids"):
            replace(original.bindings[0], placement_ids=())
        with self.assertRaisesRegex(SerializationError, "Binding placements"):
            replace(original, bindings=(replace(original.bindings[0], placement_ids=("absent",)),))

    def test_source_bindings_are_total_and_injective(self):
        original = refinement()
        values = dict(original.source_bindings)
        values.pop(next(iter(values)))
        with self.assertRaisesRegex(SerializationError, "Every model node"):
            replace(original, source_bindings=values)
        values = dict(original.source_bindings)
        keys = tuple(values)
        values[keys[0]] = values[keys[1]]
        with self.assertRaisesRegex(SerializationError, "injective"):
            replace(original, source_bindings=values)

    def test_orphan_material_or_unknown_members_cannot_disappear(self):
        original = refinement()
        with self.assertRaisesRegex(SerializationError, "Every supplied component"):
            replace(original, components=(*original.components, replace(original.components[0], id="orphan")))
        with self.assertRaisesRegex(SerializationError, "absent member"):
            replace(original, placements=(replace(original.placements[0], member_id="absent"),))
        with self.assertRaisesRegex(SerializationError, "local model role"):
            replace(original, placements=(replace(original.placements[0], recipient_role="population-name"),))

    def test_owned_effect_requires_material_correspondence(self):
        original = refinement()
        with self.assertRaisesRegex(SerializationError, "Every owned behavior"):
            replace(original, bindings=(replace(original.bindings[0], behavior_node_ids=(original.owned_node_ids[0],)),))

    def test_controls_are_typed_and_independent_from_rna_count(self):
        original = refinement()
        actions = tuple(node.id for node in original.behavior.nodes if node.kind.startswith("action."))
        control = ArchitectureControl("stop", "shutdown", actions, (), ("composite",),
                                      "shared-domain", ("One declared physical shutdown control.",))
        updated = replace(original, controls=(control,))
        constraints = RNAArchitectureConstraints(exact_count=1, control_requirements=(
            ControlRequirement("independent-stops", "shutdown", actions, "independent", ("shared-helper",)),))
        self.assertEqual(updated.controls[0].domain_id, "shared-domain")
        self.assertEqual(RNAArchitectureConstraints.from_json(constraints.to_json()), constraints)
        with self.assertRaises(SerializationError):
            replace(control, kind="universal_independence")

    def test_helper_cycles_and_capacity_are_retained_for_eligibility_rejection(self):
        original = refinement()
        helper = ArchitectureHelper("helper", "formal_helper", ("composite",),
                                    original.placements[0].recipient_role, "cytoplasm", "same_rna",
                                    "after_expression", "shared", 1, ("Explicit artificial helper contract.",),
                                    "delivery", "composite", ("helper",))
        updated = replace(original, helpers=(helper,))
        self.assertEqual(updated.helpers[0].depends_on, ("helper",))
        with self.assertRaisesRegex(SerializationError, "material placement"):
            replace(helper, availability="host")
        with self.assertRaisesRegex(SerializationError, "capacity"):
            replace(helper, capacity=True)

    def test_explicit_wiring_must_resolve_direction_and_unique_driver(self):
        original = refinement()
        valid = ArchitectureConnection("wire", "composite", "out", "composite", "in")
        self.assertEqual(replace(original, connections=(valid,)).connections, (valid,))
        with self.assertRaisesRegex(SerializationError, "producer output"):
            replace(original, connections=(replace(valid, producer_port_id="in"),))
        with self.assertRaisesRegex(SerializationError, "multiple drivers"):
            replace(original, connections=(valid, replace(valid, id="wire2")))

    def test_delivery_requires_same_recipient_declaration_and_assumptions(self):
        group = RecipientDeliveryGroup("delivery", ("source-role",), "co_delivered", True,
                                       ("All named members are assumed present in the same recipient.",), exact_count=2)
        self.assertEqual(RecipientDeliveryGroup.from_json(group.to_json()), group)
        with self.assertRaises(SerializationError):
            replace(group, same_recipient=1)
        with self.assertRaises(SerializationError):
            replace(group, assumptions=())
        with self.assertRaises(SerializationError):
            replace(group, max_count=1)

    def test_transport_declarations_are_bounded_and_immutable(self):
        channel = ArchitectureChannel("link", "model-channel", "sender-role", "receiver-role",
                                      "emit", "sense", 1, 2, "clear", "single_sender",
                                      {"value": 0, "unit": "1"}, ("Declared transport only.",))
        self.assertEqual(ArchitectureChannel.from_json(channel.to_json()), channel)
        with self.assertRaises(TypeError):
            channel.initial_value["value"] = 1
        for updates in ({"latency_seconds": float("nan")}, {"persistence_seconds": -1},
                        {"failure_mode": "magical_recovery"}, {"aggregation": "guess"}):
            with self.subTest(updates=updates), self.assertRaises(SerializationError):
                replace(channel, **updates)

    def test_limits_and_complete_authority_change_identity(self):
        original = refinement()
        library = PayloadArchitectureLibrary("library", (original,))
        changed = replace(original, assumptions=("A different supplied assumption.",))
        self.assertNotEqual(library.fingerprint,
                            replace(library, refinements=(changed,)).fingerprint)
        for kwargs in ({"exact_count": -1}, {"max_count": True}, {"max_combinations": 4097},
                       {"max_total_bases": 1_000_001}, {"exact_count": 2, "max_count": 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(SerializationError):
                RNAArchitectureConstraints(**kwargs)

    def test_library_rejects_contradictory_component_identity(self):
        original = refinement()
        other = replace(original, id="other", components=(replace(original.components[0],
                        guarantees=("Contradictory reused identity.",)),))
        with self.assertRaisesRegex(SerializationError, "contradictory architecture authority"):
            PayloadArchitectureLibrary("library", (original, other))


if __name__ == "__main__":
    unittest.main()
