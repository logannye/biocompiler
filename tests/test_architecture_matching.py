"""Reusable supplied patterns preserve meaning without source-ID coupling."""

from dataclasses import replace
import unittest

import biocompiler as bc
from biocompiler.compiler.architecture_matching import (
    architecture_instance_id, instantiate_architecture_refinement,
    match_architecture_refinement,
)
from biocompiler.compiler.behavior import lower_to_behavior
from biocompiler.errors import SerializationError
from biocompiler.ir.architecture_build import PayloadArchitectureBuild
from biocompiler.ir.payload_architecture import (
    ArchitectureMatchPolicy, ArchitectureRefinementInstance,
    PayloadArchitectureRefinement, RNAArchitectureConstraints,
)
from biocompiler.ir.serialization import fingerprint
from biocompiler.semantics.payload_execution import derive_source_execution
from examples.payload_architectures import make_architecture_request
from examples.architecture_automation import make_automatic_case
from test_payload_architecture_ir import refinement


def automatic_pattern():
    return replace(refinement(), source_bindings={}, match_policy=ArchitectureMatchPolicy())


def independent_source(*, copies=1, padding=False, product="artificial_alpha", band="present",
                       ordered_guard=False, reverse=False):
    """Author source separately from the supplied model fixture."""
    program = bc.Therapy("independently_authored_source")
    if padding:
        program.engineer("unrelated", cell_type="human_T_cell")
    cell = program.engineer("recipient", cell_type="human_T_cell")
    for _ in range(copies):
        guard = getattr(cell.environment.signal("context"), band)()
        if ordered_guard:
            other = cell.environment.signal("other").present()
            guard = (other & guard) if reverse else (guard & other)
        cell.when(guard).do(cell.secrete(product), cell.secrete("artificial_beta"))
    return lower_to_behavior(program.freeze())


class ArchitectureMatchingTests(unittest.TestCase):
    def test_identity_independent_model_finds_separately_authored_source(self):
        pattern = automatic_pattern()
        source = independent_source(padding=True)
        result = match_architecture_refinement(pattern, source)
        self.assertFalse(result.exhausted)
        self.assertEqual(len(result.instances), 1)
        instance = result.instances[0]
        self.assertNotEqual(dict(instance.source_bindings), dict(refinement().source_bindings))
        self.assertEqual(set(instance.source_bindings), {node.id for node in pattern.behavior.nodes})
        for node in pattern.behavior.nodes:
            actual = source.get(instance.source_bindings[node.id])
            self.assertEqual(actual.kind, node.kind)
            self.assertEqual(actual.attributes, node.attributes)
            self.assertEqual(actual.inputs, tuple(instance.source_bindings[ref] for ref in node.inputs))
        restored = instantiate_architecture_refinement(pattern, instance)
        self.assertIsNone(restored.match_policy)
        self.assertEqual(restored.behavior.fingerprint, pattern.behavior.fingerprint)
        self.assertEqual(restored.components, pattern.components)
        self.assertEqual(restored.templates, pattern.templates)

    def test_ambiguity_retains_distinct_complete_correspondences(self):
        pattern = automatic_pattern()
        result = match_architecture_refinement(pattern, independent_source(copies=2))
        self.assertFalse(result.exhausted)
        self.assertEqual(len(result.instances), 2)
        local_rule = next(node.id for node in pattern.behavior.nodes if node.kind == "rule")
        self.assertEqual(len({instance.source_bindings[local_rule] for instance in result.instances}), 2)
        self.assertEqual(tuple(item.id for item in result.instances), tuple(sorted(item.id for item in result.instances)))

    def test_partial_anchor_resolves_ambiguity_without_changing_meaning(self):
        pattern = automatic_pattern()
        source = independent_source(copies=2)
        rule = next(node.id for node in pattern.behavior.nodes if node.kind == "rule")
        requested = next(node.id for node in reversed(source.nodes) if node.kind == "rule")
        anchored = replace(pattern, source_bindings={rule: requested})
        result = match_architecture_refinement(anchored, source)
        self.assertEqual(len(result.instances), 1)
        self.assertEqual(result.instances[0].source_bindings[rule], requested)

    def test_unknown_and_semantically_wrong_anchors_do_not_match(self):
        pattern = automatic_pattern()
        source = independent_source()
        rule = next(node.id for node in pattern.behavior.nodes if node.kind == "rule")
        wrong = next(node.id for node in source.nodes if node.kind == "role")
        for value in ("absent", wrong):
            with self.subTest(anchor=value):
                result = match_architecture_refinement(replace(pattern, source_bindings={rule: value}), source)
                self.assertEqual(result.instances, ())
                self.assertFalse(result.exhausted)

    def test_product_and_qualitative_meaning_are_not_wildcards(self):
        pattern = automatic_pattern()
        for source in (independent_source(product="different_product"), independent_source(band="high")):
            result = match_architecture_refinement(pattern, source)
            self.assertEqual(result.instances, ())
            self.assertFalse(result.exhausted)

    def test_ordered_inputs_do_not_receive_an_unproved_commutativity_rewrite(self):
        original = automatic_pattern()
        model = independent_source(ordered_guard=True)
        component = replace(original.components[0], identities=(replace(
            original.components[0].identities[0], content_fingerprint=model.fingerprint),))
        owned = tuple(node.id for node in model.nodes if node.kind == "rule" or node.kind.startswith("action."))
        role = next(node.id for node in model.nodes if node.kind == "role")
        pattern = replace(original, behavior=model, components=(component,), owned_node_ids=owned,
            bindings=(replace(original.bindings[0], behavior_node_ids=owned),),
            placements=(replace(original.placements[0], recipient_role=role),))
        result = match_architecture_refinement(pattern, independent_source(ordered_guard=True, reverse=True))
        self.assertEqual(result.instances, ())
        self.assertFalse(result.exhausted)

    def test_distinct_installed_effects_cannot_collapse_to_one_source_instance(self):
        original = automatic_pattern()
        model = independent_source(copies=2)
        component = replace(original.components[0], identities=(replace(
            original.components[0].identities[0], content_fingerprint=model.fingerprint),))
        owned = tuple(node.id for node in model.nodes if node.kind == "rule" or node.kind.startswith("action."))
        pattern = replace(original, behavior=model, components=(component,), owned_node_ids=owned,
                          bindings=(replace(original.bindings[0], behavior_node_ids=owned),))
        result = match_architecture_refinement(pattern, independent_source(copies=1))
        self.assertEqual(result.instances, ())
        self.assertFalse(result.exhausted)

    def test_work_exhaustion_is_distinct_from_no_match(self):
        result = match_architecture_refinement(automatic_pattern(), independent_source(), max_states=1)
        self.assertTrue(result.exhausted)
        self.assertEqual(result.states_examined, 1)
        self.assertIn("architecture_matching_work_budget_exhausted", result.diagnostics)

    def test_result_bound_does_not_silently_choose_first_ambiguous_match(self):
        pattern, source = automatic_pattern(), independent_source(copies=2)
        result = match_architecture_refinement(pattern, source, max_instances=1)
        self.assertTrue(result.exhausted)
        self.assertEqual(len(result.instances), 1)
        self.assertIn("architecture_matching_instance_budget_exhausted", result.diagnostics)
        complete = match_architecture_refinement(pattern, source, max_instances=2)
        self.assertEqual(len(complete.instances), 2)
        self.assertFalse(complete.exhausted)

    def test_instance_identity_is_deterministic_and_pins_full_authority(self):
        pattern, source = automatic_pattern(), independent_source()
        instance = match_architecture_refinement(pattern, source).instances[0]
        self.assertEqual(instance.id, pattern.id + ".match." + fingerprint({
            "refinement": pattern.fingerprint, "source_bindings": dict(instance.source_bindings)}))
        self.assertEqual(match_architecture_refinement(pattern, source).instances[0], instance)
        changed = replace(pattern, assumptions=(*pattern.assumptions, "Additional explicitly supplied assumption."))
        self.assertNotEqual(architecture_instance_id(changed, instance.source_bindings), instance.id)
        self.assertEqual(ArchitectureRefinementInstance.from_json(instance.to_json()), instance)
        with self.assertRaises(TypeError):
            instance.source_bindings["new"] = "new"

    def test_long_pattern_identity_stays_within_resolved_record_bounds(self):
        pattern = replace(automatic_pattern(), id="p" * 4000)
        instance = match_architecture_refinement(pattern, independent_source()).instances[0]
        resolved = instantiate_architecture_refinement(pattern, instance)
        self.assertEqual(resolved.id, instance.id)
        self.assertLessEqual(len(resolved.id.encode("utf-8")), 4096)

    def test_all_existing_design_slices_match_independent_authority(self):
        for case in "ABCDEF":
            with self.subTest(case=case):
                request = make_architecture_request(case, variants=("one_rna",))
                pattern = replace(request.library.refinements[0], source_bindings={},
                                  match_policy=ArchitectureMatchPolicy())
                result = match_architecture_refinement(pattern, derive_source_execution(request.source).behavior,
                                                      circuit=request.circuit)
                self.assertFalse(result.exhausted)
                self.assertEqual(len(result.instances), 1)

    def test_output_requirement_identity_and_contract_are_pinned(self):
        request = make_architecture_request("A", variants=("one_rna",))
        pattern = replace(request.library.refinements[0], source_bindings={}, match_policy=ArchitectureMatchPolicy())
        source = derive_source_execution(request.source).behavior
        binding = pattern.output_contracts[0]
        missing = replace(pattern, output_contracts=(replace(binding, requirement_id="unrelated-output"),
                                                      *pattern.output_contracts[1:]))
        result = match_architecture_refinement(missing, source, circuit=request.circuit)
        self.assertEqual(result.instances, ())
        self.assertTrue(any("matching_output_requirement_absent" in code for code in result.diagnostics))
        changed_product = replace(binding.product, id="another_product")
        changed = replace(pattern, output_contracts=(replace(binding, product=changed_product),
                                                      *pattern.output_contracts[1:]))
        result = match_architecture_refinement(changed, source, circuit=request.circuit)
        self.assertEqual(result.instances, ())
        self.assertTrue(any("matching_output_contract_mismatch" in code for code in result.diagnostics))

    def test_schema_policy_and_bounds_are_explicit(self):
        pattern = automatic_pattern()
        self.assertEqual(PayloadArchitectureRefinement.from_json(pattern.to_json()), pattern)
        self.assertEqual(pattern.schema_version, "biocompiler.payload_architecture_refinement.v0.2")
        with self.assertRaises(SerializationError):
            replace(pattern, match_policy=None)
        with self.assertRaises(SerializationError):
            replace(pattern, source_bindings={"unmodeled": "n000001"})
        for arguments in ({"max_match_states": True}, {"max_match_states": 1_000_001},
                          {"max_match_instances": 257}, {"max_match_instances": 0}):
            with self.subTest(arguments=arguments), self.assertRaises(SerializationError):
                RNAArchitectureConstraints(**arguments)
        old = pattern.to_dict()
        old["schema_version"] = "biocompiler.payload_architecture_refinement.v0.1"
        with self.assertRaises(SerializationError):
            PayloadArchitectureRefinement.from_dict(old)


class AutomaticArchitectureCompilationTests(unittest.TestCase):
    def request(self, **constraints):
        original = make_architecture_request("A", variants=("many_components_one_rna",),
                                             independent_shutdown=True)
        pattern = replace(original.library.refinements[0], source_bindings={}, match_policy=ArchitectureMatchPolicy())
        return replace(original, library=replace(original.library, refinements=(pattern,)),
                       constraints=replace(original.constraints, **constraints))

    def test_automatic_mapping_runs_through_construction_and_fresh_verification(self):
        request = self.request()
        build = bc.compile(request)
        self.assertEqual(build.status, "compiled")
        self.assertEqual(len(build.match_instances), 1)
        self.assertEqual(build.plan.instances, build.match_instances)
        self.assertEqual(PayloadArchitectureBuild.from_json(build.to_json()), build)
        receipt = bc.check_payload_architecture(build, expected_request=request)
        self.assertTrue(receipt.passed)
        self.assertTrue(receipt.translation_complete)
        exported = bc.export_payload_architecture(build, expected_request=request)
        self.assertIn("alphabet=RNA", exported.fasta)

    def test_matching_exhaustion_emits_no_selected_molecule(self):
        request = self.request(max_match_states=1)
        build = bc.compile(request)
        self.assertEqual(build.status, "search_exhausted")
        self.assertIsNone(build.plan)
        self.assertIsNone(build.construction)
        self.assertTrue(any(item.code == "architecture_matching_work_budget_exhausted" for item in build.diagnostics))
        self.assertTrue(bc.check_payload_architecture(build, expected_request=request).passed)

    def test_matching_instance_bound_is_shared_across_the_library(self):
        request = self.request(max_match_instances=1)
        first = request.library.refinements[0]
        second = replace(first, id="second-supplied-pattern")
        request = replace(request, library=replace(request.library, refinements=(first, second)))
        build = bc.compile(request)
        self.assertEqual(build.status, "search_exhausted")
        self.assertEqual(len(build.match_instances), 1)
        self.assertIsNone(build.plan)
        self.assertTrue(any(item.code == "architecture_matching_instance_budget_exhausted"
                            for item in build.diagnostics))

    def test_matching_work_bound_is_shared_across_the_library(self):
        request = self.request()
        first = request.library.refinements[0]
        result = match_architecture_refinement(first, derive_source_execution(request.source).behavior,
                                              circuit=request.circuit)
        second = replace(first, id="second-supplied-pattern")
        request = replace(request, library=replace(request.library, refinements=(first, second)),
                          constraints=replace(request.constraints, max_match_states=result.states_examined))
        build = bc.compile(request)
        self.assertEqual(build.status, "search_exhausted")
        self.assertEqual(len(build.match_instances), 1)
        self.assertIsNone(build.construction)
        self.assertTrue(any(item.code == "architecture_matching_work_budget_exhausted"
                            for item in build.diagnostics))

    def test_retained_alternatives_resolve_to_complete_instance_census(self):
        request = self.request()
        first = request.library.refinements[0]
        second = replace(first, id="alternative-supplied-pattern")
        request = replace(request, library=replace(request.library, refinements=(first, second)),
                          constraints=replace(request.constraints, preferred_refinement_ids=(first.id,)))
        build = bc.compile(request)
        self.assertEqual(build.status, "compiled")
        self.assertEqual(len(build.match_instances), 2)
        inventory = {item.id: item for item in build.match_instances}
        self.assertEqual(build.plan.instances[0].refinement_id, first.id)
        for alternative in build.alternatives:
            self.assertTrue(set(alternative.refinement_ids) <= inventory.keys())
        self.assertEqual(len([item for item in build.alternatives if item.eligible]), 2)

    def test_generated_instance_cannot_collide_with_explicit_library_identity(self):
        request = self.request()
        automatic = request.library.refinements[0]
        matched = match_architecture_refinement(automatic,
            derive_source_execution(request.source).behavior, circuit=request.circuit)
        self.assertEqual(len(matched.instances), 1)
        instance = matched.instances[0]
        explicit = replace(automatic, id=instance.id, match_policy=None,
                           source_bindings=instance.source_bindings)
        request = replace(request,
            library=replace(request.library, refinements=(automatic, explicit)))
        build = bc.compile(request)
        self.assertEqual(build.status, "unsupported")
        self.assertIsNone(build.plan)
        self.assertIsNone(build.construction)
        self.assertEqual(len(build.match_instances), 1)
        self.assertIn("architecture_instance_identity_collision", {item.code for item in build.diagnostics})
        self.assertTrue(bc.check_payload_architecture(build, expected_request=request).passed)
        self.assertEqual(bc.PayloadArchitectureBuild.from_json(build.to_json()).to_dict(), build.to_dict())

    def test_automatic_state_and_combined_cases_verify_export_and_execute(self):
        from biocompiler.semantics.architecture_execution import evaluate_payload_architecture
        from test_architecture_execution import histories, output_active, receiver_frames

        for case in ("B", "F"):
            with self.subTest(case=case):
                request = make_automatic_case(case)
                self.assertTrue(all(not item.source_bindings for item in request.library.refinements))
                build = bc.compile(request)
                self.assertEqual(build.status, "compiled", build.diagnostics)
                checked = bc.check_payload_architecture(build, expected_request=request)
                self.assertTrue(checked.passed)
                self.assertTrue(checked.translation_complete)
                exported = bc.export_payload_architecture(build, expected_request=request)
                self.assertEqual(exported.fasta.count(">"), 1 if case == "B" else 4)
                self.assertEqual(exported.manifest["request_fingerprint"], request.fingerprint)
                if case == "F":
                    initial = {role: (frames[0],) for role, frames in histories(request, combined=True).items()}
                    result = evaluate_payload_architecture(build, request, initial, until=3, step=1)
                    frames = receiver_frames(result, build)
                    self.assertEqual([time for time, frame in frames.items() if output_active(frame)], [1])
                    state = request.source.intent.find(kind="state")[0].id
                    self.assertEqual([frames[time].states[state] for time in range(4)],
                                     ["prime", "act", "act", "recover"])


if __name__ == "__main__":
    unittest.main()
