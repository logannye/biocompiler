"""New functional meanings remain connected from source to checked RNA export."""
from dataclasses import replace
import unittest

import biocompiler as bc
from examples.architecture_control_designs import CASES, make_control_request


def gaps(build):
    return tuple(item for alternative in build.alternatives for item in alternative.gaps)


class ArchitectureControlPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = {case: make_control_request(case) for case in CASES}
        cls.builds = {case: bc.compile_payload_architecture(request) for case, request in cls.requests.items()}

    def test_all_four_source_contract_rna_paths_verify_and_export(self):
        for case in CASES:
            with self.subTest(case=case):
                request, build = self.requests[case], self.builds[case]
                self.assertEqual(build.status, "compiled", gaps(build))
                receipt = bc.check_payload_architecture(build, expected_request=request)
                self.assertTrue(receipt.passed and receipt.translation_complete and receipt.construction_complete,
                                receipt.diagnostics)
                self.assertEqual(receipt.empirical_validation, "unknown")
                self.assertEqual(receipt.human_therapeutic_admission, "not_admitted")
                exported = bc.export_payload_architecture(build, expected_request=request)
                self.assertEqual(exported.fasta.count(">"), 1)
                self.assertEqual(exported.manifest["request_fingerprint"], request.fingerprint)
                self.assertTrue(any(row.id == "constraint:control:source-control-" + case
                                    and row.status == "implemented" for row in build.plan.ledger))
                self.assertEqual(bc.PayloadArchitectureBuild.from_dict(exported.manifest["build"]).fingerprint,
                                 build.fingerprint)
                self.assertEqual(bc.PayloadArchitectureRequest.from_json(request.to_json()).fingerprint,
                                 request.fingerprint)

    def test_coherent_source_and_supplier_false_labels_are_not_functional_proofs(self):
        expected = {
            "memory_reset": "assertion_does_not_reset",
            "state_reset": "assertion_does_not_reset_state",
            "production_adjustment": "production_rate_unchanged",
            "activity_control": "deassertion_does_not_gate_activity",
        }
        for case, reason in expected.items():
            with self.subTest(case=case):
                request = make_control_request(case, false_control=True)
                build = bc.compile_payload_architecture(request)
                self.assertEqual(build.status, "no_solution", gaps(build))
                self.assertTrue(any(reason in item.code for item in gaps(build)), gaps(build))
                self.assertFalse(any("source_model_meaning_mismatch" in item.code for item in gaps(build)), gaps(build))
                self.assertIsNone(build.molecules)

    def test_production_material_declaration_must_cover_every_same_product_branch(self):
        request = make_control_request("production_adjustment", omit_aggregate=True)
        build = bc.compile_payload_architecture(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("control_production_aggregate_unbound" in item.code for item in gaps(build)), gaps(build))

    def test_context_conditioned_aggregate_branch_breaks_claimed_independence(self):
        separate = make_control_request("production_independence")
        separate_build = bc.compile_payload_architecture(separate)
        self.assertEqual(separate_build.status, "compiled", gaps(separate_build))
        self.assertTrue(bc.check_payload_architecture(separate_build, expected_request=separate).translation_complete)
        coupled = make_control_request("production_independence", coupled=True)
        coupled_build = bc.compile_payload_architecture(coupled)
        self.assertEqual(coupled_build.status, "no_solution", gaps(coupled_build))
        self.assertTrue(any("independent_control_cross_influence" in item.code for item in gaps(coupled_build)),
                        gaps(coupled_build))
        self.assertFalse(any("unsupported_functional_control" in item.code for item in gaps(coupled_build)),
                         gaps(coupled_build))

    def test_complete_product_scope_cannot_hide_shared_branch_material(self):
        request = make_control_request("production_independence")
        original = request.library.refinements[0]
        hidden = original.controls[0].behavior_node_ids[1]
        moved = {hidden, *(node.id for node in original.behavior.nodes
                          if node.kind == "rule" and hidden in node.inputs[2:])}
        first, second = original.bindings
        bindings = (
            replace(first, behavior_node_ids=tuple(ref for ref in first.behavior_node_ids if ref not in moved)),
            replace(second, behavior_node_ids=(*second.behavior_node_ids, *sorted(moved))),
        )
        # The complete claimed action inventory and distinct controller labels
        # remain unchanged, but A's hidden branch now shares B's component.
        changed = replace(original, bindings=bindings)
        request = replace(request, library=replace(request.library, refinements=(changed,)))
        build = bc.compile_payload_architecture(request)
        self.assertEqual(build.status, "no_solution", gaps(build))
        self.assertTrue(any("independent_control" in item.code for item in gaps(build)), gaps(build))

    def test_activity_product_and_lifecycle_authority_are_required(self):
        request = self.requests["activity_control"]
        original = request.library.refinements[0]
        output = original.output_contracts[0]
        self.assertEqual(output.product.kind, "biological_activity")
        self.assertEqual(output.lifecycle.mode, "activity_control")
        changed = replace(original, output_contracts=(replace(output, lifecycle=bc.CircuitLifecycle("production_control")),))
        request = replace(request, library=replace(request.library, refinements=(changed,)))
        build = bc.compile_payload_architecture(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("activity_control_not_realized" in item.code for item in gaps(build)), gaps(build))

    def test_source_edit_does_not_rewrite_supplier_model_or_authorize_stale_export(self):
        original = self.requests["memory_reset"]
        changed = make_control_request("memory_reset", false_control=True)
        changed = replace(changed, library=original.library)
        build = bc.compile_payload_architecture(changed)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("source_model_meaning_mismatch" in item.code for item in gaps(build)), gaps(build))
        with self.assertRaises(bc.SerializationError):
            bc.export_payload_architecture(self.builds["memory_reset"], expected_request=changed)


if __name__ == "__main__":
    unittest.main()
