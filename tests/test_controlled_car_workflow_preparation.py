"""Inert workflow authorship checks; the material here is explicitly artificial."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.core_client import encode_json
from biocompiler.policy.controlled_workflow import ControlledWorkflowRequest
from biocompiler.policy.research_project import ResearchProject
from biocompiler.policy.serialization import from_data
from biocompiler.policy import model as p
from tools.controlled_car_workflow import PREFIX, SCENARIO, prepare_workflow

ROOT = Path(__file__).resolve().parents[1]


def artificial_material():
    """Exercise record authorship with the old MA/MG software-control material.

    Aliases select the helper's two slots; they do not establish patent fidelity.
    The actual public-input replay is a separate qualification activity.
    """
    original = json.loads((ROOT / "core/test/data/policy_controlled_request_v014.json").read_bytes())
    names = {"rna-a": "car197", "rna-b": "car206",
             "artificial-product-a": "WO2014127261A1.construct197",
             "artificial-product-b": "WO2014127261A1.construct206"}

    def alias(value):
        if type(value) is dict:
            return {key: alias(child) for key, child in value.items()}
        if type(value) is list:
            return [alias(child) for child in value]
        return names.get(value, value)

    return alias(original["material_authority"]), original["source_authority"]["project_context"]["sources"]


def contract():
    return json.loads((ROOT / "data/car_controlled_reference/controller-readout-contract.json").read_bytes())


def prepare():
    material, sources = artificial_material()
    return prepare_workflow(material_authority=material, source_records=sources, contract=contract())


class ControlledCarWorkflowPreparationTests(unittest.TestCase):
    def test_fresh_typed_source_and_project_are_inert_and_keep_complete_originals(self):
        with patch("subprocess.Popen", side_effect=AssertionError("Native execution is forbidden")):
            workflow = prepare()
            project = ResearchProject.from_controlled(workflow)
            self.assertEqual(workflow.native_status, "not_performed")
            self.assertEqual(project.controlled, workflow)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "project.json"
                project.dump(path)
                self.assertEqual(ResearchProject.load(path).controlled, workflow)
        original = workflow.behavior.original.to_request()
        self.assertEqual(original["material_authority"], artificial_material()[0])
        self.assertEqual(original["source_authority"]["project_context"]["sources"], artificial_material()[1])
        self.assertEqual(original["context"]["empirical_assertions"][0]["status"], "unassessed")
        self.assertEqual(original["source_authority"]["document"]["deployment"]["route"], "in_vivo")
        chassis = original["source_authority"]["document"]["deployment"]["bindings"][0]["chassis"]
        self.assertEqual((chassis["species"], chassis["lineage"], chassis["subtype"]), ("human", "T_cell", "CD8_T_cell"))
        self.assertEqual(chassis["activation_states"], ["assumed_expression_and_signaling_capable"])
        self.assertEqual(chassis["differentiation_states"], ["assumed_mature_CD8_T_cell"])
        self.assertEqual(original["resources"]["max_member_rna_nt"], 17)
        self.assertEqual(original["resources"]["max_total_rna_nt"], 34)

    def test_all_definition_references_are_fresh_and_no_artificial_source_is_relabeled(self):
        source = prepare().behavior.original.source_authority
        document = source.document
        self.assertEqual(document.program.id, PREFIX)
        definitions = {item.id: item for item in document.program.semantics.definitions}
        self.assertEqual(len(document.program.declarations), 15)
        self.assertEqual({item.declaration_id for item in document.program.source_map},
                         {item.id for item in document.program.declarations})
        self.assertTrue(all(item.file == "data/car_controlled_reference/controller-readout-contract.json"
                            and item.line > 0 and item.pattern.startswith("json:")
                            for item in document.program.source_map))
        used = set()

        def visit(value):
            if type(value) is dict:
                if value.get("$type") == "DefinitionRef":
                    identity = value["id"]
                    self.assertEqual(from_data(value, p.DefinitionRef), definitions[identity].ref)
                    used.add(identity)
                for child in value.values():
                    visit(child)
            elif type(value) is list:
                for child in value:
                    visit(child)

        visit(source.to_data()["document"])
        self.assertEqual(used, set(definitions))
        self.assertNotIn("artificial", encode_json(source.to_data()["document"]).decode())
        interpreted = [item for item in definitions.values() if item.clauses]
        self.assertEqual(len(interpreted), 12)
        self.assertTrue(all(item.clauses[0].expression.value.startswith("biocompiler.controlled_source.")
                            for item in interpreted))

    def test_model_products_pins_scope_and_assumptions_match_full_authority(self):
        original = prepare().behavior.original.to_request()
        model = original["mechanism_model"]
        self.assertEqual(model["identity"]["content_fingerprint"], hashlib.sha256(encode_json(model["body"])).hexdigest())
        self.assertEqual(model["body"]["assumptions"], contract()["assumptions"])
        definitions = original["source_authority"]["document"]["program"]["semantics"]["definitions"]
        descriptors = [item for item in definitions if item["parameters"]]
        self.assertEqual(len(descriptors), 2)
        for descriptor, material in zip(descriptors, original["material_authority"]["members"], strict=True):
            values = [parameter["value"] for parameter in descriptor["parameters"]]
            pin = material["product"]["identity"]
            self.assertEqual(values, [pin["id"], pin["version"], pin["content_fingerprint"]])
        self.assertEqual(original["context"]["controller"]["scope"], "executor")
        self.assertEqual(original["context"]["co_delivery"]["members"], ["car197", "car206"])
        self.assertEqual(original["assembly"]["helper_members"], [])

    def test_scenario_preserves_two_branches_and_distinct_actual_requested_timing(self):
        workflow = prepare()
        original = workflow.behavior.original.to_request()
        domain = original["operating_domain"]
        self.assertEqual(domain["physical_factors"], [{"input": "controller", "ticks": [2], "values": ["disabled"]}])
        self.assertEqual([row["tick"] for row in domain["fixed_inputs"]], [0, 1, 3, 4, 5, 6, 7, 8, 9, 10])
        self.assertEqual(domain["fixed_inputs"][4]["physical"]["antigen"], "absent")
        self.assertEqual(domain["fixed_inputs"][5]["physical"]["antigen"], "present")
        control = original["source_authority"]["control_contract"]
        self.assertEqual(control["actual_delays"], SCENARIO["actual_delays"])
        self.assertEqual(control["requested_deadlines"], SCENARIO["requested_deadlines"])
        self.assertEqual(len(workflow.behavior.to_request()["readout_evidence"]["samples"]), 11)
        self.assertEqual({row["freshness_ticks"] for row in domain["inputs"]}, {1})
        self.assertIn("uncalibrated", " ".join(original["source_authority"]["project_context"]["assumptions"]))

    def test_mutable_inputs_and_returned_values_cannot_rewrite_snapshot(self):
        material, sources = artificial_material()
        supplied = contract()
        workflow = prepare_workflow(material_authority=material, source_records=sources, contract=supplied)
        original = workflow.to_request()
        material["members"][0]["product"]["sequence"] = "MG"
        sources[0]["sha256"] = "0" * 64
        supplied["assumptions"].clear()
        detached = workflow.to_request()
        detached["behavior_request"]["original"]["context"]["empirical_assertions"].clear()
        self.assertEqual(workflow.to_request(), original)
        self.assertEqual(ControlledWorkflowRequest.from_request(original), workflow)

    def test_changed_pin_is_retained_and_changes_identity_without_claiming_acceptance(self):
        material, sources = artificial_material()
        initial = prepare_workflow(material_authority=material, source_records=sources, contract=contract())
        material["members"][0]["product"]["identity"]["content_fingerprint"] = "0" * 64
        changed = prepare_workflow(material_authority=material, source_records=sources, contract=contract())
        self.assertNotEqual(initial.sha256, changed.sha256)
        self.assertEqual(changed.native_status, "not_performed")
        descriptor = next(item for item in changed.behavior.original.source_authority.document.program.semantics.definitions
                          if item.id == PREFIX + ".product197")
        self.assertEqual(descriptor.parameters[2].value, "0" * 64)

    def test_unknown_or_silently_calibrated_scenarios_and_missing_assumptions_reject(self):
        material, sources = artificial_material()
        for key, value in (("clock_seconds_per_tick", True), ("horizon_tick", 11),
                           ("freshness_ticks", 2), ("extra", "discarded")):
            supplied = contract()
            supplied["scenario"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                prepare_workflow(material_authority=material, source_records=sources, contract=supplied)
        supplied = contract()
        supplied["scenario"]["actual_delays"]["onset_ticks"] = 2
        with self.assertRaises(ValueError):
            prepare_workflow(material_authority=material, source_records=sources, contract=supplied)
        for assumptions in ([], [""], "implicit", None):
            supplied = contract()
            supplied["assumptions"] = assumptions
            with self.subTest(assumptions=assumptions), self.assertRaises(ValueError):
                prepare_workflow(material_authority=material, source_records=sources, contract=supplied)

    def test_missing_source_fields_and_wrong_member_product_order_reject(self):
        for mutation in (lambda m, s: m["member_order"].reverse(),
                         lambda m, s: m["members"][0]["product"]["identity"].update(id="foreign"),
                         lambda m, s: s[0].pop("reuse_terms")):
            material, sources = artificial_material()
            mutation(material, sources)
            with self.assertRaises(ValueError):
                prepare_workflow(material_authority=material, source_records=sources, contract=contract())

    def test_contract_relabeling_or_empirical_promotion_cannot_enter_helper(self):
        material, sources = artificial_material()
        mutations = (lambda value: value.update(reference_identity="different_pair"),
                     lambda value: value["controller"].update(id="rapamycin"),
                     lambda value: value["readout"].update(id="measured_cytotoxicity"),
                     lambda value: value["readout"].update(background_means_zero_cytotoxicity=True),
                     lambda value: value["intended_target"].update(empirical_status="validated"),
                     lambda value: value["evidence_classification"]["measured_records"].append("invented"),
                     lambda value: value["validation_boundary"].update(conditional_check_establishes_empirical_function=True),
                     lambda value: value.update(empirical_status="validated"))
        for mutate in mutations:
            supplied = contract()
            mutate(supplied)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                prepare_workflow(material_authority=material, source_records=sources, contract=supplied)


if __name__ == "__main__":
    unittest.main()
