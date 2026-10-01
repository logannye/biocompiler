"""Generated correspondence is a proposal; pinned source/model authority decides."""

from dataclasses import replace
from functools import lru_cache
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.ir.serialization import fingerprint
from examples.payload_architectures import make_architecture_request


@lru_cache(maxsize=1)
def fixture():
    request = make_architecture_request(variants=("one_rna",))
    pattern = replace(request.library.refinements[0], source_bindings={},
                      match_policy=bc.ArchitectureMatchPolicy())
    request = replace(request, library=replace(request.library, refinements=(pattern,)))
    build = bc.compile(request)
    if build.status != "compiled":
        raise AssertionError([gap.code for item in build.alternatives for gap in item.gaps])
    return request, build


class IndependentMatchTests(unittest.TestCase):
    def test_distinct_source_ids_match_and_hard_helper_windows_override_preference(self):
        from examples.architecture_automation import make_automation_request
        request = make_automation_request()
        self.assertTrue(all(not item.source_bindings for item in request.library.refinements))
        build = bc.compile(request)
        self.assertEqual(build.status, "compiled")
        self.assertTrue(all(value.startswith("design.") for item in build.plan.instances
                            for value in item.source_bindings.values()))
        self.assertTrue(all(item.refinement_id not in request.constraints.preferred_refinement_ids
                            for item in build.plan.instances))
        self.assertTrue(any("deployment_onset_deadline" in gap.code
                            for alternative in build.alternatives for gap in alternative.gaps))
        self.assertTrue(bc.check_payload_architecture(build, expected_request=request).translation_complete)

    def test_checker_and_export_do_not_call_the_graph_matcher(self):
        request, build = fixture()
        with patch("biocompiler.compiler.architecture_matching.match_architecture_refinement",
                   side_effect=AssertionError("Producer matcher cannot establish correspondence")):
            checked = bc.check_payload_architecture(build, expected_request=request)
            self.assertTrue(checked.translation_complete)
            self.assertFalse(checked.search_verified)
            self.assertIn(">", bc.export_payload_architecture(build, expected_request=request).fasta)

    def test_plan_and_census_retain_complete_independently_checkable_maps(self):
        request, build = fixture()
        self.assertEqual(len(build.plan.instances), 1)
        instance = build.plan.instances[0]
        self.assertEqual(instance.refinement_id, request.library.refinements[0].id)
        self.assertIn(instance.id, build.plan.selected_refinement_ids)
        self.assertEqual(instance, next(item for item in build.match_instances if item.id == instance.id))
        self.assertEqual(set(instance.source_bindings), {node.id for node in request.library.refinements[0].behavior.nodes})
        restored = bc.PayloadArchitectureBuild.from_json(build.to_json())
        self.assertEqual(restored.fingerprint, build.fingerprint)

    def test_rehashed_false_correspondence_does_not_become_authority(self):
        request, build = fixture()
        pattern = request.library.refinements[0]
        instance = build.plan.instances[0]
        predicates = [node.id for node in pattern.behavior.nodes if node.kind == "qualitative"]
        self.assertGreaterEqual(len(predicates), 2)
        mapping = dict(instance.source_bindings)
        left, right = predicates[:2]
        mapping[left], mapping[right] = mapping[right], mapping[left]
        identity = pattern.id + ".match." + fingerprint({"refinement": pattern.fingerprint,
                                                        "source_bindings": mapping})
        invented = replace(instance, id=identity, source_bindings=mapping)
        plan = replace(build.plan, instances=(invented,), selected_refinement_ids=(identity,))
        forged = replace(build, plan=plan, match_instances=(invented,))
        checked = bc.check_payload_architecture(forged, expected_request=request)
        self.assertFalse(checked.passed)
        self.assertTrue(any("model_operation_mismatch" in item.code for item in checked.diagnostics))
        with self.assertRaises(bc.SerializationError):
            bc.export_payload_architecture(forged, expected_request=request)

    def test_missing_instance_or_census_is_rejected(self):
        request, build = fixture()
        for forged in (replace(build, match_instances=()),
                       replace(build, plan=replace(build.plan, instances=()))):
            checked = bc.check_payload_architecture(forged, expected_request=request)
            self.assertFalse(checked.translation_complete)
            self.assertFalse(checked.passed)

    def test_caller_supplied_anchor_cannot_be_erased_by_a_generated_match(self):
        request, build = fixture()
        pattern = request.library.refinements[0]
        predicates = [node.id for node in pattern.behavior.nodes if node.kind == "qualitative"]
        anchored = replace(pattern, source_bindings={predicates[0]: predicates[1]})
        authority = replace(request, library=replace(request.library, refinements=(anchored,)))
        forged = replace(build, request_fingerprint=authority.fingerprint)
        checked = bc.check_payload_architecture(forged, expected_request=authority)
        self.assertFalse(checked.passed)
        self.assertTrue(any("selected_instance_anchor_authority" in item.code for item in checked.diagnostics))

    def test_previous_schema_does_not_silently_drop_generated_correspondence(self):
        _, build = fixture()
        document = build.to_dict()
        document["schema_version"] = "biocompiler.payload_architecture_build.v0.1"
        document.pop("match_instances")
        with self.assertRaises(bc.SerializationError):
            bc.PayloadArchitectureBuild.from_dict(document)


if __name__ == "__main__":
    unittest.main()
