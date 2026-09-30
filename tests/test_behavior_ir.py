"""Checked IR import and exact preservation tests, independent of execution."""

import copy
from dataclasses import FrozenInstanceError, replace
import unittest

from biocompiler import Duration, Level, Therapy, signature
from biocompiler.compiler.behavior import lower_to_behavior, verify_lowering
from biocompiler.errors import (
    LoweringVerificationError,
    SerializationError,
    UnsupportedBehaviorError,
)
from biocompiler.ir.behavior import BehaviorProgram
from biocompiler.ir.intent import IntentProgram


def basic_program():
    therapy = Therapy("abstract_contract")
    cells = therapy.engineer("observer", cell_type="abstract_cell")
    a = cells.contact.marker("A").present()
    b = cells.contact.marker("B").present()
    cells.when((a & b).held_for(Duration(2)), name="observe").do(cells.report("seen"))
    return therapy.freeze()


class BehaviorIRTests(unittest.TestCase):
    def test_exact_roundtrip_and_independent_export(self):
        original = basic_program()
        program = lower_to_behavior(original)
        decoded = BehaviorProgram.from_json(program.to_json())
        self.assertEqual(program, decoded)
        self.assertEqual(program.fingerprint, decoded.fingerprint)
        self.assertEqual(program.source_fingerprint, original.fingerprint)
        self.assertTrue(verify_lowering(original, decoded).passed)
        data = decoded.to_dict()
        data["policies"]["history"] = "changed"
        self.assertEqual(program.policies["history"], "since_initialization")
        with self.assertRaises(TypeError):
            program.policies["history"] = "changed"
        with self.assertRaises(FrozenInstanceError):
            program.name = "changed"

    def test_source_free_roundtrip_preserves_structural_fingerprint(self):
        program = lower_to_behavior(basic_program())
        decoded = BehaviorProgram.from_json(program.to_json(include_source=False))
        self.assertEqual(decoded.fingerprint, program.fingerprint)
        self.assertTrue(all(node.source is None for node in decoded.nodes))

    def test_requirements_cover_complete_rule_ancestry(self):
        original = basic_program()
        program = lower_to_behavior(original)
        requirement = program.requirements[0]
        rule = program.find(kind="rule")[0]
        self.assertEqual(requirement.source_node_id, rule.id)
        self.assertEqual(requirement.lineage, program.source_links[rule.id])
        self.assertEqual(set(requirement.lineage), {node.id for node in original.nodes})
        self.assertTrue(
            all(requirement.id in node.requirement_ids for node in program.nodes)
        )

    def test_import_rejects_policy_and_operation_mutations(self):
        original = lower_to_behavior(basic_program()).to_dict()
        modifications = [
            lambda d: d["policies"].update(initial_time=False),
            lambda d: d["policies"].update(history="prehistory"),
            lambda d: d.update(schema_version="future"),
            lambda d: d.update(roots=[]),
            lambda d: d.update(requirements=[]),
            lambda d: d.update(source_links={}),
            lambda d: d["requirements"][0].update(source={}),
            lambda d: next(n for n in d["nodes"] if n["kind"] == "held_for")[
                "attributes"
            ].update(requires_full_interval=1),
            lambda d: next(n for n in d["nodes"] if n["kind"] == "and").update(
                kind="unknown"
            ),
            lambda d: next(n for n in d["nodes"] if n["kind"] == "and").update(
                inputs=[]
            ),
            lambda d: next(n for n in d["nodes"] if n["kind"] == "and").update(
                contact_bound=False
            ),
            lambda d: next(n for n in d["nodes"] if n["kind"] == "rule")[
                "attributes"
            ].update(priority="first"),
            lambda d: next(n for n in d["nodes"] if n["kind"] == "qualitative")[
                "attributes"
            ].update(band="invented"),
        ]
        for mutate in modifications:
            with self.subTest(mutation=modifications.index(mutate)):
                data = copy.deepcopy(original)
                mutate(data)
                with self.assertRaises(SerializationError):
                    BehaviorProgram.from_dict(data)

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaises(SerializationError):
            BehaviorProgram.from_json('{"name":"one","name":"two"}')

    def test_checker_detects_semantic_change_even_with_same_nodes(self):
        source = basic_program()
        program = lower_to_behavior(source)
        data = program.to_dict()
        literal = next(n for n in data["nodes"] if n["kind"] == "literal")
        literal["attributes"]["value"]["value"] = 3
        literal["attributes"]["value"]["canonical_value"] = 3
        changed = BehaviorProgram.from_dict(data)
        self.assertEqual(len(changed.nodes), len(program.nodes))
        with self.assertRaises(LoweringVerificationError):
            verify_lowering(source, changed)

    def test_parameters_are_bound_typed_and_durations_constant(self):
        therapy = Therapy("parameters")
        cells = therapy.engineer("observer", cell_type="abstract_cell")
        wait = therapy.parameter("wait", type=Duration)
        ready = cells.external.signal("ready").present().held_for(wait)
        cells.when(ready).do(cells.report("ready"))
        source = therapy.freeze()
        with self.assertRaises(UnsupportedBehaviorError):
            lower_to_behavior(source)
        behavior = lower_to_behavior(source, parameters={"wait": Duration(2)})
        self.assertEqual(behavior.parameter_bindings["wait"]["canonical_value"], 2)
        self.assertTrue(
            verify_lowering(source, behavior, parameters={"wait": Duration(2)}).passed
        )
        with self.assertRaises(SerializationError):
            lower_to_behavior(source, parameters={"wait": Duration(-2)})

    def test_parameter_manifest_cannot_smuggle_boolean_as_number(self):
        therapy = Therapy("typed_manifest")
        therapy.parameter("amount", default=1)
        data = lower_to_behavior(therapy.freeze()).to_dict()
        data["parameter_bindings"]["amount"]["canonical_value"] = True
        with self.assertRaises(SerializationError):
            BehaviorProgram.from_dict(data)

    def test_consistent_node_and_manifest_tampering_cannot_authorize_binding(self):
        therapy = Therapy("binding_authority")
        therapy.parameter("amount", default=1)
        source = therapy.freeze()
        data = lower_to_behavior(source).to_dict()
        node = next(item for item in data["nodes"] if item["kind"] == "parameter")
        for value in (
            node["attributes"]["default"],
            data["parameter_bindings"]["amount"],
        ):
            value.update(value=9, canonical_value=9)
        changed = BehaviorProgram.from_dict(data)
        with self.assertRaisesRegex(
            LoweringVerificationError, "authoritative_bindings"
        ):
            verify_lowering(source, changed)
        self.assertTrue(
            verify_lowering(source, changed, parameters={"amount": 9}).passed
        )
        self.assertEqual(
            lower_to_behavior(source, parameters={"amount": 9}).fingerprint,
            changed.fingerprint,
        )

    def test_dynamic_duration_rejected_with_source(self):
        therapy = Therapy("dynamic_duration")
        cells = therapy.engineer("observer", cell_type="abstract_cell")
        wait = cells.external.signal("wait", type=Duration)
        condition = cells.external.signal("ready").present()
        cells.when(condition.held_for(wait)).do(cells.report("ready"))
        with self.assertRaises(UnsupportedBehaviorError) as raised:
            lower_to_behavior(therapy.freeze())
        self.assertIsNotNone(raised.exception.source)
        self.assertIsNotNone(raised.exception.node_id)

    def test_state_memory_and_signature_bindings_remain_local(self):
        therapy = Therapy("state_and_signatures")
        cells = therapy.engineer("observer", cell_type="abstract_cell")
        contact = cells.contact.marker("A").present()
        memory = cells.memory("seen", set_when=contact)
        state = cells.state("phase", values=("idle", "ready"), initial="idle")

        @signature
        def local_condition(unused_contact, condition):
            return condition

        guard = local_condition(cells.contact, memory.is_set() & state.is_("idle"))
        cells.when(guard).do(state.set("ready"), cells.report("ready"))
        program = lower_to_behavior(therapy.freeze())
        for kind in ("memory", "memory.is_set", "state", "state.is", "signature"):
            self.assertFalse(program.find(kind=kind)[0].contact_bound, kind)
        self.assertTrue(program.find(kind="qualitative")[0].contact_bound)
        self.assertEqual(len(program.requirements), 3)

    def test_source_policy_changes_are_not_silently_normalized(self):
        source = basic_program()
        nodes = tuple(
            replace(node, attributes={**node.attributes, "priority": "first"})
            if node.kind == "rule"
            else node
            for node in source.nodes
        )
        modified = IntentProgram(source.name, nodes, source.roots)
        with self.assertRaises(UnsupportedBehaviorError):
            lower_to_behavior(modified)

    def test_arithmetic_dimension_corruption_is_rejected(self):
        therapy = Therapy("arithmetic")
        cells = therapy.engineer("observer", cell_type="abstract_cell")
        amount = cells.internal.signal("amount", type=Level)
        cells.when((amount + 2) > 4).do(cells.report("ready"))
        data = lower_to_behavior(therapy.freeze()).to_dict()
        next(node for node in data["nodes"] if node["kind"] == "add")["data_type"] = (
            Duration._spec.to_dict()
        )
        with self.assertRaises(SerializationError):
            BehaviorProgram.from_dict(data)


if __name__ == "__main__":
    unittest.main()
