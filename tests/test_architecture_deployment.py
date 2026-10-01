"""Independent worst-case timing checks include every delivered helper RNA."""

from dataclasses import replace
from functools import lru_cache
import unittest

import biocompiler as bc
from biocompiler.ir.intent import thaw_json
from biocompiler.verification.architecture_deployment import check_deployment_requirements
from examples.payload_architectures import make_architecture_request


ASSUMPTION = "Artificial timing authority; no claim about expression in human cells."


def timed_request():
    request = make_architecture_request(variants=("one_rna_helper",))
    refinement = request.library.refinements[0]
    availability = tuple(bc.RNAAvailabilityContract("window." + item.id, item.id,
        2, 4, 10, 12, (ASSUMPTION,)) for item in refinement.placements)
    refinement = replace(refinement, availability=availability)
    group = request.constraints.delivery_groups[0]
    requirement = bc.RNADeploymentRequirement("execute-window", group.id,
        group.recipient_roles[0], "cytoplasm", 4, 12, (ASSUMPTION,), unavailable_after_seconds=16)
    return replace(request, library=replace(request.library, refinements=(refinement,)),
        constraints=replace(request.constraints, deployment_requirements=(requirement,)))


@lru_cache(maxsize=1)
def fixture():
    request = timed_request()
    build = bc.compile(request)
    if build.status != "compiled":
        raise AssertionError([gap.code for item in build.alternatives for gap in item.gaps])
    return request, build


def diagnostics(build):
    return [gap for item in build.alternatives for gap in item.gaps]


class DeploymentWindowTests(unittest.TestCase):
    def test_typed_windows_roundtrip_and_reject_undefined_bounds(self):
        request = timed_request()
        contract = request.library.refinements[0].availability[0]
        self.assertEqual(bc.RNAAvailabilityContract.from_json(contract.to_json()), contract)
        requirement = request.constraints.deployment_requirements[0]
        self.assertEqual(bc.RNADeploymentRequirement.from_json(requirement.to_json()), requirement)
        for change in ({"onset_min_seconds": True}, {"duration_max_seconds": float("inf")},
                       {"duration_min_seconds": 0}, {"onset_min_seconds": 5},
                       {"clock": "behavior_start"}, {"assumptions": ()}):
            with self.subTest(change=change), self.assertRaises(bc.SerializationError):
                replace(contract, **change)
        with self.assertRaises(bc.SerializationError):
            replace(requirement, unavailable_after_seconds=11)
        with self.assertRaises(bc.SerializationError):
            replace(requirement, required_until_seconds=4)

    def test_complete_payload_and_helper_windows_are_retained_and_rechecked(self):
        request, build = fixture()
        self.assertEqual(len(build.plan.availability), len(build.plan.placements))
        self.assertGreater(len(build.plan.placements), 1)
        self.assertTrue(bc.check_payload_architecture(build, expected_request=request).translation_complete)
        self.assertIn("constraint:deployment:execute-window", {item.id for item in build.plan.ledger})
        exported = bc.export_payload_architecture(build, expected_request=request)
        self.assertEqual(len(exported.manifest["build"]["plan"]["availability"]), len(build.plan.placements))
        self.assertIn(ASSUMPTION, exported.manifest["verification"]["assumptions"])

    def test_earliest_end_not_latest_onset_determines_guaranteed_overlap(self):
        request = timed_request()
        requirement = replace(request.constraints.deployment_requirements[0], required_until_seconds=13)
        request = replace(request, constraints=replace(request.constraints, deployment_requirements=(requirement,)))
        build = bc.compile(request)
        self.assertEqual(build.status, "no_solution")
        self.assertIsNone(build.molecules)
        failures = [item for item in diagnostics(build) if "deployment_common_window_insufficient" in item.code]
        self.assertTrue(failures)
        self.assertIn("constraint:deployment:execute-window", failures[0].requirement_ids)

    def test_latest_onset_and_latest_end_are_both_checked(self):
        for change, code in (({"required_from_seconds": 3}, "deployment_onset_deadline"),
                             ({"unavailable_after_seconds": 15}, "deployment_unavailability_deadline")):
            with self.subTest(change=change):
                request = timed_request()
                requirement = replace(request.constraints.deployment_requirements[0], **change)
                request = replace(request, constraints=replace(request.constraints, deployment_requirements=(requirement,)))
                self.assertTrue(any(code in item.code for item in diagnostics(bc.compile(request))))

    def test_missing_helper_window_cannot_pass_on_payload_window_alone(self):
        request = timed_request()
        refinement = request.library.refinements[0]
        helper = next(item for item in refinement.helpers if item.placement_id is not None)
        refinement = replace(refinement, availability=tuple(item for item in refinement.availability
                             if item.placement_id != helper.placement_id))
        request = replace(request, library=replace(request.library, refinements=(refinement,)))
        build = bc.compile(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("deployment_availability_missing" in item.code for item in diagnostics(build)))

    def test_recipient_and_destination_constraints_are_not_aliases(self):
        request, build = fixture()
        inventories = {key: getattr(build.plan, key) for key in ("placements", "availability")}
        for change, code in (({"recipient_role": "absent-role"}, "deployment_recipient_mismatch"),
                             ({"compartment": "abstract"}, "deployment_compartment_unknown"),
                             ({"delivery_group_id": "absent-group"}, "deployment_group_missing")):
            with self.subTest(change=change):
                requirement = replace(request.constraints.deployment_requirements[0], **change)
                changed = replace(request, constraints=replace(request.constraints, deployment_requirements=(requirement,)))
                self.assertTrue(any(code in item for item in check_deployment_requirements(changed, inventories)))

    def test_same_recipient_overlap_requires_declared_co_delivery(self):
        request, build = fixture()
        groups = tuple(replace(item, mode="independent", same_recipient=False)
                       for item in request.constraints.delivery_groups)
        request = replace(request, constraints=replace(request.constraints, delivery_groups=groups))
        inventories = {key: getattr(build.plan, key) for key in ("placements", "availability")}
        self.assertTrue(any("deployment_same_recipient_unproven" in item
                            for item in check_deployment_requirements(request, inventories)))

    def test_forged_plan_window_fails_independent_authority_and_export(self):
        request, build = fixture()
        windows = thaw_json(build.plan.availability)
        windows[0]["onset_max_seconds"] = 0
        forged = replace(build, plan=replace(build.plan, availability=tuple(windows)))
        receipt = bc.check_payload_architecture(forged, expected_request=request)
        self.assertFalse(receipt.passed)
        self.assertIn("plan_availability", [item.code for item in receipt.diagnostics])
        with self.assertRaises(bc.SerializationError):
            bc.export_payload_architecture(forged, expected_request=request)

    def test_decimal_second_boundaries_do_not_depend_on_binary_rounding(self):
        request, build = fixture()
        requirement = replace(request.constraints.deployment_requirements[0],
            required_from_seconds=0.1, required_until_seconds=0.3, unavailable_after_seconds=0.3)
        request = replace(request, constraints=replace(request.constraints, deployment_requirements=(requirement,)))
        windows = thaw_json(build.plan.availability)
        for item in windows:
            item.update(onset_min_seconds=0.1, onset_max_seconds=0.1,
                        duration_min_seconds=0.2, duration_max_seconds=0.2)
        inventories = {"placements": build.plan.placements, "availability": windows}
        self.assertEqual(check_deployment_requirements(request, inventories), [])


if __name__ == "__main__":
    unittest.main()
