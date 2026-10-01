"""Independent source, component and complete-molecule authority mutations."""

from dataclasses import replace
from functools import lru_cache
import unittest
from unittest.mock import patch

from biocompiler.compiler.circuit_construction import build_circuit_construction
from biocompiler.compiler.executable_payload import compile_payload
from biocompiler.errors import SerializationError
from biocompiler.ir.intent import thaw_json
from biocompiler.verification.executable_payload import (
    PayloadVerification, _source_symbols, check_payload_build, verify_payload_build,
)
from examples.executable_payload import make_payload_request


@lru_cache(maxsize=4)
def fixture(kind="ordinary"):
    request = make_payload_request(multi_output=kind == "multiple", memory=kind == "memory")
    return request, compile_payload(request)


class ExecutablePayloadVerificationTests(unittest.TestCase):
    def test_scope_valued_retention_cannot_be_reduced_to_activation(self):
        import biocompiler as bc
        from biocompiler.compiler.request import BuildRequest
        therapy = bc.Therapy("retention_authority")
        cell = therapy.engineer("recipient", cell_type="declared human T cell")
        cell.when(cell.internal.signal("on").present()).do(cell.retain(cell.environment))
        with self.assertRaisesRegex(SerializationError, "action-target"):
            _source_symbols(BuildRequest.freeze(therapy.freeze()))

    def test_supplementary_product_kind_and_quantity_need_exact_output_contract(self):
        from biocompiler.ir.circuit_observations import ProductKind, QuantityKind
        request, build = fixture()
        requirement = request.circuit.requirements[0]
        product = requirement.behavior.output
        changed_product = replace(product, kind=ProductKind.RNA_PRODUCT,
                                  observation=replace(product.observation, quantity=QuantityKind.RNA_ABUNDANCE))
        changed_requirement = replace(requirement, behavior=replace(requirement.behavior, output=changed_product))
        changed = replace(request, circuit=replace(request.circuit, requirements=(changed_requirement,)))
        construction = build_circuit_construction(replace(build.construction.request, circuit=changed.circuit))
        mutant = replace(build, request_fingerprint=changed.fingerprint, construction=construction)
        self.check_rejected(mutant, changed, "fail:component_circuit_output:response.0")

    def test_supplementary_lifecycle_window_needs_exact_output_contract(self):
        from biocompiler.ir.circuit_observations import ObservationWindow
        request, build = fixture()
        requirement = request.circuit.requirements[0]
        lifecycle = replace(requirement.behavior.lifecycle,
                            onset=ObservationWindow("activation", 0, 0, "s", "instant"))
        changed_requirement = replace(requirement, behavior=replace(requirement.behavior, lifecycle=lifecycle))
        changed = replace(request, circuit=replace(request.circuit, requirements=(changed_requirement,)))
        construction = build_circuit_construction(replace(build.construction.request, circuit=changed.circuit))
        mutant = replace(build, request_fingerprint=changed.fingerprint, construction=construction, status="partial")
        self.check_rejected(mutant, changed, "fail:component_circuit_lifecycle:response.0")

    def test_circuit_provider_obligation_cannot_be_silently_discharged(self):
        from biocompiler.ir.circuit_intent import CircuitProviderRequirement
        from biocompiler.ir.executable_payload import PayloadSelectionConstraints
        request, _ = fixture()
        requirement = request.circuit.requirements[0]
        provider = CircuitProviderRequirement("declared_host_supply", requirement.behavior.output.observation.entity,
                                              "host", "cytoplasm", "declared_colocation", "declared")
        changed_requirement = replace(requirement, behavior=replace(requirement.behavior, dependencies=(provider,)))
        changed = replace(request, circuit=replace(request.circuit, requirements=(changed_requirement,)))
        build = compile_payload(changed)
        result = check_payload_build(build, expected_request=changed)
        self.assertTrue(result.passed)
        self.assertFalse(result.translation_complete)
        self.assertEqual(build.status, "partial")
        self.assertIn("unsupported:circuit_provider_mapping:response.0:declared_host_supply", result.unresolved)
        self.check_rejected(replace(build, status="compiled", diagnostics=()), changed,
                            "fail:unsupported_complete_translation_claim")
        strict = replace(changed, constraints=PayloadSelectionConstraints(require_complete=True))
        strict_build = compile_payload(strict)
        self.assertIsNone(strict_build.molecules)

    def test_unused_optional_dependency_does_not_require_a_new_target_compartment(self):
        from biocompiler.ir.component_contracts import DependencyRequirement
        request, build = fixture()
        output_id = build.mechanism.outputs[0]
        contract_id = build.selected[output_id]
        optional = DependencyRequirement("unused_optional", "unavailable_capability",
                                         build.mechanism.get(output_id).role, "cell", "nucleus", required=False)
        contracts = tuple(replace(contract, component=replace(contract.component, dependencies=(optional,)))
                          if contract.id == contract_id else contract for contract in request.library.contracts)
        changed = replace(request, library=replace(request.library, contracts=contracts))
        compiled = compile_payload(changed)
        checked = check_payload_build(compiled, expected_request=changed)
        self.assertTrue(checked.passed)
        self.assertTrue(checked.translation_complete)

    def check_rejected(self, build, request, code):
        result = check_payload_build(build, expected_request=request)
        self.assertFalse(result.passed, result.to_dict())
        self.assertIn(code, result.diagnostics)
        return result

    def test_replay_does_not_call_compiler_selector_namespace_or_emitter(self):
        request, build = fixture()
        targets = (
            "biocompiler.compiler.executable_payload.compile_payload",
            "biocompiler.compiler.executable_payload._selected_mechanism",
            "biocompiler.compiler.executable_payload._construction",
            "biocompiler.compiler.behavior.lower_to_behavior",
            "biocompiler.semantics.payload_requirements.extract_payload_requirements",
            "biocompiler.ir.payload_contracts.namespace_payload_template",
            "biocompiler.ir.payload_contracts.merge_payload_templates",
            "biocompiler.backends.circuit_construction.construct_circuit_candidate",
        )
        from contextlib import ExitStack
        with ExitStack() as stack:
            for target in targets:
                stack.enter_context(patch(target, side_effect=AssertionError("Producer used as oracle")))
            result = check_payload_build(build, expected_request=request)
        self.assertTrue(result.passed)
        self.assertTrue(result.translation_complete)
        self.assertTrue(result.construction_complete)
        self.assertEqual(PayloadVerification.from_json(result.to_json()), result)
        self.assertEqual(verify_payload_build(result, build, expected_request=request), result)

    def test_different_independent_source_cannot_reuse_old_payload(self):
        _, build = fixture()
        independent = make_payload_request(guard="or")
        self.check_rejected(build, independent, "fail:original_source_authority")

    def test_self_consistent_guard_change_still_compares_original_source(self):
        request, build = fixture()
        guard = next(node for node in build.mechanism.nodes if node.kind == "and")
        def changed(graph):
            return replace(graph, nodes=tuple(replace(node, kind="or") if node.id == guard.id else node
                                               for node in graph.nodes))
        requirements = replace(build.requirements, mechanism=changed(build.requirements.mechanism))
        mutant = replace(build, requirements=requirements, mechanism=changed(build.mechanism))
        self.check_rejected(mutant, request, "fail:source_executable_output_semantics")

    def test_swapped_source_input_binding_cannot_preserve_observation_identity(self):
        request, build = fixture()
        original = build.requirements.observation_map
        first, second = original.inputs
        observation_map = replace(original, inputs=(replace(first, signal_id=second.signal_id),
                                                     replace(second, signal_id=first.signal_id)))
        mutant = replace(build, requirements=replace(build.requirements, observation_map=observation_map))
        self.check_rejected(mutant, request, "fail:source_executable_output_semantics")

    def test_full_source_requirement_inventory_cannot_drop_non_output_nodes(self):
        request, build = fixture()
        mutant = replace(build, requirements=replace(build.requirements,
                         requirements=build.requirements.requirements[1:]))
        self.check_rejected(mutant, request, "fail:complete_source_requirement_inventory")

    def test_complete_source_lineage_cannot_be_replaced_by_one_node(self):
        request, build = fixture()
        lineage = dict(build.requirements.source_map)
        output = build.mechanism.outputs[0]
        lineage[output] = (build.requirements.outputs[0].action_id,)
        mutant = replace(build, requirements=replace(build.requirements, source_map=lineage))
        self.check_rejected(mutant, request, "fail:source_activation_lineage")

    def test_source_primitive_action_contract_cannot_change_product(self):
        request, build = fixture()
        identity = build.selected[build.mechanism.outputs[0]]
        contracts = tuple(replace(item, effect={**thaw_json(item.effect), "product": "different_product"})
                          if item.id == identity else item for item in request.library.contracts)
        changed = replace(request, library=replace(request.library, contracts=contracts))
        mutant = replace(build, request_fingerprint=changed.fingerprint)
        self.check_rejected(mutant, changed, "fail:component_action_effect:" + build.mechanism.outputs[0])

    def test_selected_model_parameters_cannot_change_memory_expiry(self):
        request, build = fixture("memory")
        memory = next(node for node in build.mechanism.nodes if node.kind == "memory")
        attributes = thaw_json(memory.attributes)
        attributes["duration"]["value"] = 7
        attributes["duration"]["canonical_value"] = 7
        changed = replace(build.mechanism, nodes=tuple(
            replace(node, attributes=attributes) if node.id == memory.id else node
            for node in build.mechanism.nodes))
        self.check_rejected(replace(build, mechanism=changed), request, "fail:source_automatic_memory_semantics")

    def test_partial_temporal_projection_does_not_become_complete(self):
        request, build = fixture("memory")
        result = check_payload_build(build, expected_request=request)
        self.assertTrue(result.passed)
        self.assertFalse(result.translation_complete)
        self.assertTrue(result.construction_complete)
        self.assertIn("unsupported:circuit_temporal_or_input_refinement:response.0", result.unresolved)
        self.check_rejected(replace(build, status="compiled", diagnostics=()), request,
                            "fail:unsupported_complete_translation_claim")

    def test_component_assumptions_cannot_disappear(self):
        request, build = fixture()
        self.check_rejected(replace(build, assumptions=()), request, "fail:complete_contract_assumptions")

    def test_self_consistent_missing_helper_fails_independent_template_authority(self):
        request, build = fixture()
        authority = build.construction.request
        helper = next(item for item in authority.output_members if item.id.endswith("helper"))
        changed = replace(authority,
                          output_members=tuple(item for item in authority.output_members if item.id != helper.id),
                          requirements=tuple(item for item in authority.requirements if item.member_id != helper.id))
        rebuilt = build_circuit_construction(changed)
        self.assertTrue(rebuilt.assessment.passed)
        self.check_rejected(replace(build, construction=rebuilt), request,
                            "fail:selected_template_construction_authority")

    def test_exact_supplied_bases_are_authoritative_even_with_same_model(self):
        request, build = fixture()
        authority = build.construction.request
        root = authority.sources[0]
        molecule = replace(root.molecule, sequence="UGCAUG")
        changed = replace(authority, sources=(replace(root, molecule=molecule), *authority.sources[1:]))
        rebuilt = build_circuit_construction(changed)
        self.assertTrue(rebuilt.assessment.passed)
        self.check_rejected(replace(build, construction=rebuilt), request,
                            "fail:selected_template_construction_authority")

    def test_circuit_output_binding_cannot_change_original_input_correspondence(self):
        request, build = fixture()
        binding = request.circuit_bindings[0]
        keys = tuple(binding.signals)
        changed_binding = replace(binding, signals={keys[0]: binding.signals[keys[1]],
                                                    keys[1]: binding.signals[keys[0]]})
        changed = replace(request, circuit_bindings=(changed_binding,))
        self.check_rejected(replace(build, request_fingerprint=changed.fingerprint), changed,
                            "fail:circuit_original_input_binding:response.0")

    def test_fresh_receipt_cannot_keep_success_from_another_artifact(self):
        request, build = fixture()
        result = check_payload_build(build, expected_request=request)
        with self.assertRaisesRegex(SerializationError, "fresh|replay"):
            verify_payload_build(result, replace(build, assumptions=()), expected_request=request)

    def test_unsuccessful_search_does_not_certify_search_and_still_checks_source_graph(self):
        request, build = fixture()
        empty = replace(build, selected={}, mechanism=None, construction=None, status="no_solution")
        result = check_payload_build(empty, expected_request=request)
        self.assertTrue(result.passed)
        self.assertFalse(result.search_verified)
        self.assertFalse(result.translation_complete)
        self.assertIn("unsupported:search_outcome_not_independently_replayed", result.unresolved)
        graph = empty.requirements.mechanism
        mutated_graph = replace(graph, nodes=tuple(replace(node, kind="or") if node.kind == "and" else node
                                                   for node in graph.nodes))
        self.check_rejected(replace(empty, requirements=replace(empty.requirements, mechanism=mutated_graph)),
                            request, "fail:source_activation_graph_semantics")

    def test_unread_state_obligation_cannot_disappear_from_diagnostics(self):
        import biocompiler as bc
        request, _ = fixture()
        source = request.source
        therapy = bc.Therapy("state_authoring_fixture")
        cell = therapy.engineer("recipient", cell_type="declared human T cell")
        cell.state("unused", values=("idle", "ready"), initial="idle")
        state = therapy.freeze().find(kind="state")[0]
        role = source.intent.find(kind="role")[0].id
        state = replace(state, id="unused_future_state", inputs=(role,), role=role)
        changed_source = replace(source, intent=replace(source.intent, nodes=(*source.intent.nodes, state),
                                                        roots=(*source.intent.roots, state.id)))
        changed_request = replace(request, circuit=replace(request.circuit,
                                  profile=replace(request.circuit.profile, source_request=changed_source)))
        build = compile_payload(changed_request)
        self.assertEqual(build.status, "partial")
        mutant = replace(build, diagnostics=(), status="compiled", requirements=replace(build.requirements,
                         diagnostics=tuple(item for item in build.requirements.diagnostics
                                           if state.id not in item.source_node_ids)))
        self.check_rejected(mutant, changed_request,
                            "fail:omitted_source_unsupported_obligation:" + state.id)


if __name__ == "__main__":
    unittest.main()
