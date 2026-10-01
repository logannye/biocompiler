"""Program-to-complete-RNA acceptance cases for supplied architecture search."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from biocompiler.cli import main
from examples.payload_architectures import make_architecture_request


def reasons(build):
    return [gap for alternative in build.alternatives for gap in alternative.gaps]


class PayloadArchitectureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = {case: make_architecture_request(case, variants=("one_rna",)) for case in "ABCDEF"}
        cls.builds = {case: bc.compile(request) for case, request in cls.requests.items()}

    def test_all_six_vertical_slices_compile_complete_rna_and_manifest(self):
        for case, build in self.builds.items():
            with self.subTest(case=case):
                self.assertEqual(build.status, "compiled")
                request = self.requests[case]
                receipt = bc.check_payload_architecture(build, expected_request=request)
                self.assertTrue(receipt.passed and receipt.translation_complete and receipt.construction_complete)
                self.assertFalse(receipt.search_verified)
                self.assertEqual(receipt.empirical_validation, "unknown")
                exported = bc.export_payload_architecture(build, expected_request=request)
                self.assertEqual(exported.fasta.count(">"), 4 if case in "DF" else 1)
                self.assertEqual(exported.manifest["request_fingerprint"], request.fingerprint)
                self.assertEqual(bc.PayloadArchitectureBuild.from_dict(exported.manifest["build"]).fingerprint, build.fingerprint)
                self.assertTrue(all(item.status == "implemented" for item in build.plan.ledger))

    def test_rna_count_constraint_changes_selected_architecture_and_fasta(self):
        single = make_architecture_request(exact_count=1)
        multiple = make_architecture_request(exact_count=2)
        first, second = bc.compile(single), bc.compile(multiple)
        self.assertEqual(first.status, "compiled")
        self.assertEqual(second.status, "compiled")
        self.assertNotEqual(first.plan.selected_refinement_ids, second.plan.selected_refinement_ids)
        self.assertEqual(bc.export_payload_architecture(first, expected_request=single).fasta.count(">"), 1)
        self.assertEqual(bc.export_payload_architecture(second, expected_request=multiple).fasta.count(">"), 2)

    def test_independent_shutdown_can_share_rna_but_needs_separate_controls(self):
        for variant, status in (("one_rna", "no_solution"), ("many_components_one_rna", "compiled"),
                                ("two_rna", "compiled"), ("one_component_two_rna", "no_solution")):
            with self.subTest(variant=variant):
                request = make_architecture_request(variants=(variant,), independent_shutdown=True)
                build = bc.compile(request)
                self.assertEqual(build.status, status)
                if status == "no_solution":
                    gap = next(item for item in reasons(build) if "independent_control_coupled" in item.code)
                    self.assertEqual(gap.category, "incompatible_composition")
                    self.assertIn("constraint:control:independent-output-shutdown", gap.requirement_ids)
                else:
                    self.assertIn("constraint:control:independent-output-shutdown", {item.id for item in build.plan.ledger})

    def test_exact_one_rna_and_independence_explain_supplied_library_conflict(self):
        request = make_architecture_request(variants=("one_rna", "two_rna"), exact_count=1,
                                            independent_shutdown=True)
        build = bc.compile(request)
        self.assertEqual(build.status, "no_solution")
        self.assertIsNone(build.molecules)
        self.assertTrue(any(item.code == "exact_rna_count" for item in reasons(build)))
        self.assertTrue(any("independent_control_coupled" in item.code for item in reasons(build)))
        conflict = set(build.diagnostics[-1].conflict_set)
        self.assertIn("constraint:exact_count", conflict)
        self.assertIn("constraint:control:independent-output-shutdown", conflict)
        self.assertIn("not claimed minimal", build.diagnostics[-1].message)

    def test_helpers_count_toward_delivered_count_and_size(self):
        request = make_architecture_request(variants=("one_rna_helper",), exact_count=1)
        rejected = bc.compile(request)
        self.assertEqual(rejected.status, "no_solution")
        self.assertTrue(any(item.code == "exact_rna_count" for item in reasons(rejected)))
        accepted_request = replace(request, constraints=replace(request.constraints, exact_count=2))
        accepted = bc.compile(accepted_request)
        self.assertEqual(accepted.status, "compiled")
        self.assertEqual(bc.export_payload_architecture(accepted, expected_request=accepted_request).fasta.count(">"), 2)
        short = replace(accepted_request, constraints=replace(accepted_request.constraints, max_total_bases=11))
        self.assertTrue(any(item.code == "maximum_rna_total_length" for item in reasons(bc.compile(short))))

    def test_same_recipient_helper_availability_is_not_population_membership(self):
        request = make_architecture_request(variants=("one_rna_helper",))
        groups = tuple(replace(item, same_recipient=False, mode="independent") for item in request.constraints.delivery_groups)
        changed = replace(request, constraints=replace(request.constraints, delivery_groups=groups))
        build = bc.compile(changed)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("co_delivery" in item.code or "same_recipient" in item.code for item in reasons(build)))

    def test_hard_requirements_precede_library_preference(self):
        request = make_architecture_request(exact_count=1)
        helper = next(item.id for item in request.library.refinements if item.id.endswith("one_rna_helper"))
        request = replace(request, constraints=replace(request.constraints, preferred_refinement_ids=(helper,)))
        build = bc.compile(request)
        self.assertEqual(build.status, "compiled")
        self.assertNotIn(helper, build.plan.selected_refinement_ids)

    def test_search_exhaustion_emits_no_optimistic_selected_set(self):
        request = make_architecture_request()
        request = replace(request, constraints=replace(request.constraints, max_combinations=1))
        build = bc.compile(request)
        self.assertEqual(build.status, "search_exhausted")
        self.assertIsNone(build.plan)
        self.assertIsNone(build.molecules)
        self.assertEqual(build.diagnostics[-1].category, "search_budget_exhausted")
        self.assertFalse(bc.check_payload_architecture(build, expected_request=request).search_verified)

    def test_physical_separation_uses_action_placements_not_control_domain_names(self):
        for variant, expected in (("many_components_one_rna", "no_solution"), ("two_rna", "compiled")):
            with self.subTest(variant=variant):
                request = make_architecture_request(variants=(variant,), independent_shutdown=True)
                refinement = request.library.refinements[0]
                actions = tuple(node.id for node in refinement.behavior.nodes if node.kind == "action.secrete")
                # This supplied partition assigns each output action to its own
                # controller material. Shared source scaffolding remains shared.
                bindings = tuple(replace(binding, behavior_node_ids=tuple(
                    node for node in binding.behavior_node_ids if node not in actions or node == actions[index]))
                    for index, binding in enumerate(refinement.bindings))
                refinement = replace(refinement, bindings=bindings)
                separation = bc.ControlRequirement("separate-output-rnas", "physical_separation", actions, "independent")
                request = replace(request, library=replace(request.library, refinements=(refinement,)),
                                  constraints=replace(request.constraints, control_requirements=(
                                      *request.constraints.control_requirements, separation)))
                build = bc.compile(request)
                self.assertEqual(build.status, expected)
                if expected == "no_solution":
                    self.assertTrue(any("physical_separation_violated" in item.code for item in reasons(build)))
                else:
                    self.assertTrue(bc.check_payload_architecture(build, expected_request=request).translation_complete)

    def test_changed_source_product_cannot_reuse_previous_contracts(self):
        request = make_architecture_request(source_product="different_requested_product")
        build = bc.compile(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any(item.code == "source_model_meaning_mismatch" and item.requirement_ids for item in reasons(build)))

    def test_stateful_and_numeric_supplementary_contracts_roundtrip_without_stateless_gap(self):
        for case in "BCF":
            request = self.requests[case]
            rebuilt = bc.PayloadArchitectureRequest.from_json(request.to_json())
            self.assertEqual(rebuilt.fingerprint, request.fingerprint)
            self.assertTrue(all(isinstance(item.behavior, bc.ExecutableCircuitBehavior) for item in rebuilt.circuit.requirements))
            self.assertFalse(self.builds[case].diagnostics)

    def test_export_replays_authority_and_retains_chemistry_roles_and_processing(self):
        request, build = self.requests["F"], self.builds["F"]
        exported = bc.export_payload_architecture(build, expected_request=request)
        self.assertEqual(bc.PayloadArchitectureExport.from_json(exported.to_json()).fingerprint, exported.fingerprint)
        self.assertTrue(exported.manifest["build"]["plan"]["placements"])
        self.assertTrue(exported.manifest["build"]["plan"]["helpers"])
        self.assertTrue(exported.manifest["build"]["plan"]["channels"])
        changed = replace(request, constraints=replace(request.constraints, exact_count=1))
        with self.assertRaises(bc.SerializationError):
            bc.export_payload_architecture(build, expected_request=changed)

    def test_public_cli_build_verify_export_and_inspect(self):
        request = self.requests["B"]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, candidate, exported = root / "request.json", root / "build.json", root / "export.json"
            source.write_text(request.to_json())
            for command in (
                ["architecture-build", "--request", str(source), "--output", str(candidate)],
                ["architecture-verify", str(candidate), "--expected-request", str(source)],
                ["architecture-export", str(candidate), "--expected-request", str(source), "--output", str(exported)],
                ["inspect", str(exported)],
            ):
                with self.subTest(command=command[0]), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    self.assertEqual(main(command), 0)
            bundle = bc.PayloadArchitectureExport.from_json(exported.read_text())
            self.assertEqual(bundle.fasta.count(">"), 1)
            self.assertEqual(bundle.manifest["verification"]["outcome"], "pass")


if __name__ == "__main__":
    unittest.main()
