"""Adversarial checks against independent source, composition and base authority."""

from dataclasses import replace
from functools import lru_cache
import unittest
from unittest.mock import patch

from biocompiler.compiler.payload_architecture import compile_payload_architecture
from biocompiler.ir.architecture_build import PayloadArchitectureBuild
from biocompiler.ir.intent import thaw_json
from biocompiler.verification.payload_architecture import (
    PayloadArchitectureVerification, check_payload_architecture, verify_payload_architecture,
)
from examples.payload_architectures import make_architecture_request


@lru_cache(maxsize=8)
def fixture(case="A", independent=False):
    request = make_architecture_request(case, variants=("many_components_one_rna",) if independent else ("one_rna",),
                                        independent_shutdown=independent)
    build = compile_payload_architecture(request)
    if build.status != "compiled":
        raise AssertionError([(alternative.refinement_ids, [gap.code for gap in alternative.gaps])
                              for alternative in build.alternatives])
    return request, build


def changed_library(request, build, change):
    selected = set(build.plan.selected_refinement_ids)
    refinements = tuple(change(item) if item.id in selected else item for item in request.library.refinements)
    request = replace(request, library=replace(request.library, refinements=refinements))
    return request, replace(build, request_fingerprint=request.fingerprint)


def coherent_control_program_change(request, transform, change_controls=lambda controls: controls):
    """Edit source and independently authored supplier intent, with fresh pins."""
    from biocompiler.compiler.behavior import lower_to_behavior
    from examples.payload_architectures import _freeze, contract_program

    source = replace(request.source, intent=transform(request.source.intent))
    supplier = _freeze(transform(contract_program("A")), "A")
    model = lower_to_behavior(supplier)
    source_behavior = lower_to_behavior(source)
    circuit = replace(request.circuit, profile=replace(request.circuit.profile, source_request=source),
        requirements=tuple(replace(requirement,
            source_node_ids=tuple(node.id for node in source.intent.nodes),
            behavior=replace(requirement.behavior, response=source_behavior))
            for requirement in request.circuit.requirements))
    refinement = request.library.refinements[0]
    owned = tuple(node.id for node in model.nodes
                  if node.kind in {"rule", "state", "memory"} or node.kind.startswith("action."))
    refinement = replace(refinement, behavior=model,
        source_bindings={node.id: node.id for node in model.nodes}, owned_node_ids=owned,
        components=tuple(replace(component, identities=tuple(
            replace(pin, content_fingerprint=model.fingerprint) if pin.kind == "model" else pin
            for pin in component.identities)) for component in refinement.components),
        bindings=tuple(replace(binding, behavior_node_ids=owned) for binding in refinement.bindings),
        controls=change_controls(refinement.controls))
    return replace(request, circuit=circuit, library=replace(request.library, refinements=(refinement,)))


def dependency_request():
    """Two separately supplied helper providers share one RNA, not one dependency."""
    from biocompiler.ir.component_contracts import DependencyRequirement
    from biocompiler.ir.payload_architecture import ArchitectureBinding, ArchitectureHelper, ControlRequirement
    from examples.payload_architectures import ASSUMPTION, _component

    request = make_architecture_request("A", variants=("many_components_one_rna",))
    refinement = request.library.refinements[0]
    nodes = {node.id: node for node in refinement.behavior.nodes}
    rules = [node for node in nodes.values() if node.kind == "rule"]
    role = rules[0].role
    groups = [(rule.id, rule.inputs[2]) for rule in rules]
    bindings, providers, helpers = [], [], []
    components = {item.id: item for item in refinement.components}
    placement = refinement.placements[0]
    for index, binding in enumerate(refinement.bindings):
        component_id = binding.component_ids[0]
        components[component_id] = replace(components[component_id], dependencies=(
            DependencyRequirement("requires_helper", "artificial_helper", role, "cell", "cytoplasm"),))
        bindings.append(replace(binding, behavior_node_ids=groups[index]))
        provider = _component("provider." + str(index), refinement.behavior, role, helper=True)
        providers.append(provider)
        bindings.append(ArchitectureBinding("provider.binding." + str(index), groups[index], (provider.id,),
                                             (placement.template_id,), (placement.id,)))
        helpers.append(ArchitectureHelper("helper." + str(index), "artificial_helper", (component_id,),
            role, "cytoplasm", "same_rna", "available_at_start", "exclusive", 1,
            (ASSUMPTION,), placement.id, provider.id))
    refinement = replace(refinement, components=(*components.values(), *providers), bindings=tuple(bindings),
                         helpers=tuple(helpers))
    constraint = ControlRequirement("dependency-separation", "dependency_disjointness",
                                    tuple(rule.inputs[2] for rule in rules), "independent")
    return replace(request, library=replace(request.library, refinements=(refinement,)),
                   constraints=replace(request.constraints, control_requirements=(constraint,)))


class PayloadArchitectureVerificationTests(unittest.TestCase):
    def rejected(self, request, build, code):
        receipt = check_payload_architecture(build, expected_request=request)
        self.assertFalse(receipt.passed)
        self.assertFalse(receipt.translation_complete)
        self.assertTrue(any(code in item.code for item in receipt.diagnostics), receipt.diagnostics)
        return receipt

    def test_fresh_verifier_does_not_call_any_producer(self):
        request, build = fixture()
        with patch("biocompiler.compiler.payload_architecture.compile_payload_architecture", side_effect=AssertionError), \
             patch("biocompiler.semantics.payload_execution.derive_source_execution", side_effect=AssertionError), \
             patch("biocompiler.compiler.behavior.lower_to_behavior", side_effect=AssertionError), \
             patch("biocompiler.compiler.circuit_construction.build_circuit_construction", side_effect=AssertionError):
            receipt = check_payload_architecture(build, expected_request=request)
        self.assertTrue(receipt.passed, receipt.diagnostics)
        self.assertTrue(receipt.translation_complete)
        self.assertTrue(receipt.construction_complete)
        self.assertFalse(receipt.search_verified)
        self.assertEqual(receipt.empirical_validation, "unknown")
        restored = PayloadArchitectureVerification.from_dict(receipt.to_dict())
        self.assertEqual(verify_payload_architecture(restored, build, expected_request=request), receipt)

    def test_roundtrip_full_general_state_and_multicell_artifacts(self):
        for case in "ABCDEF":
            with self.subTest(case=case):
                request, build = fixture(case)
                restored = PayloadArchitectureBuild.from_dict(build.to_dict())
                checked = check_payload_architecture(restored, expected_request=request)
                self.assertTrue(checked.translation_complete, checked.diagnostics)

    def test_coherent_or_guards_cannot_be_certified_as_shutdown(self):
        from biocompiler.semantics.evaluator import InputFrame, SignalSample, evaluate
        request = make_architecture_request("A", variants=("many_components_one_rna",), independent_shutdown=True)
        request = coherent_control_program_change(request, lambda program: replace(program, nodes=tuple(
            replace(node, kind="or") if node.kind == "and" else node for node in program.nodes)))
        frame = InputFrame(0, {node.id: SignalSample(present=True) for node in request.source.intent.nodes
                               if node.kind == "signal"})
        trace = evaluate(request.circuit.requirements[0].behavior.response, (frame,))
        self.assertEqual(len(trace.frames[0].actions), 2)
        build = compile_payload_architecture(request)
        self.assertEqual(build.status, "no_solution", build.alternatives)
        gaps = [gap for alternative in build.alternatives for gap in alternative.gaps]
        self.assertTrue(any("unsupported_functional_control_requirement:independent-output-shutdown"
                            in gap.code and "assertion_does_not_veto" in gap.code for gap in gaps), gaps)
        self.assertFalse(check_payload_architecture(build, expected_request=request).translation_complete)

    def test_explicit_active_low_boolean_condition_is_a_shutdown_veto(self):
        request = make_architecture_request("A", variants=("many_components_one_rna",), independent_shutdown=True)

        def active_low(program):
            nodes = {node.id: node for node in program.nodes}
            result = []
            for node in program.nodes:
                if node.kind == "and":
                    asserted = nodes[node.inputs[1]]
                    gate = replace(asserted, id="gate." + asserted.id, inputs=(asserted.id,))
                    result.append(gate)
                    node = replace(node, inputs=(node.inputs[0], gate.id))
                result.append(node)
            return replace(program, nodes=tuple(result))

        def controls(records):
            predicates = {"n000005": "n000009", "n000007": "n000014"}
            return tuple(replace(item, controlling_node_ids=(predicates[item.controlling_node_ids[0]],))
                         if item.kind == "shutdown" else item for item in records)

        request = coherent_control_program_change(request, active_low, controls)
        build = compile_payload_architecture(request)
        self.assertEqual(build.status, "compiled", build.alternatives)
        self.assertTrue(check_payload_architecture(build, expected_request=request).translation_complete)

    def test_shared_activation_is_a_necessary_source_gate(self):
        from biocompiler.ir.payload_architecture import ControlRequirement
        request = make_architecture_request("A", variants=("one_rna",))
        actions = tuple(node.id for node in request.source.intent.nodes if node.kind == "action.secrete")
        required = ControlRequirement("shared-activation", "activation", actions, "shared")
        request = replace(request, constraints=replace(request.constraints, control_requirements=(required,)))
        build = compile_payload_architecture(request)
        self.assertEqual(build.status, "compiled", build.alternatives)
        request = coherent_control_program_change(request, lambda program: replace(program, nodes=tuple(
            replace(node, kind="or") if node.kind == "and" else node for node in program.nodes)))
        rejected = compile_payload_architecture(request)
        self.assertEqual(rejected.status, "no_solution")
        self.assertTrue(any("shared-activation" in gap.code and "deassertion_does_not_gate" in gap.code
                            for candidate in rejected.alternatives for gap in candidate.gaps))

    def test_ambiguous_raw_signal_control_has_no_assumed_boolean_band(self):
        request = make_architecture_request("A", variants=("many_components_one_rna",), independent_shutdown=True)

        def extra_band(program):
            original = next(node for node in program.nodes if node.id == "n000006")
            return replace(program, nodes=(*program.nodes, replace(original, id="second.band",
                                                                    attributes={"band": "high"})))

        request = coherent_control_program_change(request, extra_band)
        build = compile_payload_architecture(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("ambiguous_signal_predicate" in gap.code
                            for candidate in build.alternatives for gap in candidate.gaps))

    def test_shutdown_must_cover_every_installation_and_cannot_cancel_persistence(self):
        import biocompiler as bc
        from biocompiler.ir.intent import IntentNode

        for mode in ("bypass", "pulse", "event"):
            with self.subTest(mode=mode):
                request = make_architecture_request("A", variants=("many_components_one_rna",), independent_shutdown=True)

                def extra_use(program):
                    rule = next(node for node in program.nodes if node.id == "n000013")
                    additions = []
                    if mode == "bypass":
                        second = replace(rule, id="second.installation", inputs=(rule.inputs[0], "n000004", rule.inputs[2]))
                    else:
                        span = bc.Duration(2).to_dict()
                        duration = IntentNode("pulse.duration", "literal", attributes={"value": span}, data_type=span["type"])
                        pulse = IntentNode("persistent.action", "action.pulse", (rule.inputs[2], duration.id),
                            {"ongoing": True, "retrigger": "extend_from_latest_trigger"}, role=rule.role)
                        additions.extend((duration, pulse))
                        second = replace(rule, id="second.installation", inputs=(*rule.inputs[:2], pulse.id))
                    if mode == "event":
                        event = IntentNode("event.trigger", "became_true", (rule.inputs[1],),
                                           attributes={"initially_true_emits": True},
                                           data_type={"kind": "event", "name": "Event", "dimensions": {}, "arguments": []},
                                           role=rule.role)
                        additions.append(event)
                        second = replace(second, inputs=(rule.inputs[0], event.id, pulse.id),
                            attributes={**rule.attributes, "trigger": "event", "ongoing_duration": "explicit_or_design_choice"})
                    return replace(program, nodes=(*program.nodes, *additions, second),
                                   roots=(*program.roots, second.id))

                request = coherent_control_program_change(request, extra_use)
                build = compile_payload_architecture(request)
                self.assertEqual(build.status, "no_solution", build.alternatives)
                reason = "assertion_does_not_veto" if mode == "bypass" else "persistent_or_event_installation"
                self.assertTrue(any(reason in gap.code for candidate in build.alternatives for gap in candidate.gaps),
                                build.alternatives)

    def test_production_adjustment_requires_explicit_source_rates(self):
        request = make_architecture_request("A", variants=("many_components_one_rna",), independent_shutdown=True)
        required = replace(request.constraints.control_requirements[0],
                           id="independent-production", kind="production_adjustment")
        refinement = request.library.refinements[0]
        refinement = replace(refinement, controls=tuple(replace(item, kind="production_adjustment")
            if item.kind == "shutdown" else item for item in refinement.controls))
        request = replace(request, constraints=replace(request.constraints, control_requirements=(required,)),
                          library=replace(request.library, refinements=(refinement,)))
        build = compile_payload_architecture(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("unspecified_production_rate" in gap.code
                            for candidate in build.alternatives for gap in candidate.gaps))

    def test_contact_predicate_assertion_has_no_implicit_universal_scope(self):
        request = make_architecture_request("A", variants=("many_components_one_rna",), independent_shutdown=True)

        def contact_scope(program):
            return replace(program, nodes=tuple(replace(node, attributes={**node.attributes,
                "scope": "contact", **({"name": "contact"} if node.kind == "scope" else {})})
                if node.kind in {"scope", "signal"} else node for node in program.nodes))

        request = coherent_control_program_change(request, contact_scope)
        build = compile_payload_architecture(request)
        self.assertEqual(build.status, "no_solution", build.alternatives)
        self.assertTrue(any("non_cell_local_control" in gap.code
                            for candidate in build.alternatives for gap in candidate.gaps))

    def test_state_and_numeric_guards_can_have_boolean_veto_without_becoming_controls(self):
        from biocompiler.ir.payload_architecture import ControlRequirement
        for case, expression_kind in (("B", "state.is"), ("C", "compare")):
            with self.subTest(case=case):
                request = make_architecture_request(case, variants=("one_rna",))
                refinement = request.library.refinements[0]
                output = next(item for item in refinement.controls if item.kind == "shutdown")
                required = ControlRequirement("declared-veto", "shutdown", output.behavior_node_ids, "shared")
                request = replace(request, constraints=replace(request.constraints, control_requirements=(required,)))
                build = compile_payload_architecture(request)
                self.assertEqual(build.status, "compiled", build.alternatives)
                self.assertTrue(check_payload_architecture(build, expected_request=request).translation_complete)
                from biocompiler.verification.payload_architecture import _causal_nodes
                nodes = {node.id: node for node in request.source.intent.nodes}
                ancestry = _causal_nodes(nodes, output.behavior_node_ids)
                expression = next(node.id for node in nodes.values()
                                  if node.kind == expression_kind and node.id in ancestry)
                refinement = replace(refinement, controls=tuple(replace(item, controlling_node_ids=(expression,))
                    if item.id == output.id else item for item in refinement.controls))
                request = replace(request, library=replace(request.library, refinements=(refinement,)))
                rejected = compile_payload_architecture(request)
                self.assertEqual(rejected.status, "no_solution")
                self.assertTrue(any("unsupported_control_expression" in gap.code
                                    for candidate in rejected.alternatives for gap in candidate.gaps))

    def test_previous_checker_policy_receipt_is_not_current_authority(self):
        from biocompiler.errors import SerializationError
        request, build = fixture()
        receipt = check_payload_architecture(build, expected_request=request).to_dict()
        self.assertEqual(receipt["checker_version"], "biocompiler.payload_architecture_checker.v0.3")
        receipt["checker_version"] = "biocompiler.payload_architecture_checker.v0.2"
        with self.assertRaises(SerializationError):
            PayloadArchitectureVerification.from_dict(receipt)

    def test_source_output_true_to_one_is_not_equal(self):
        request, build = fixture()
        output = build.execution.outputs[0]
        semantics = thaw_json(output.semantics)
        self.assertIs(semantics["primitive_action"]["attributes"]["ongoing"], True)
        semantics["primitive_action"]["attributes"]["ongoing"] = 1
        outputs = (replace(output, semantics=semantics), *build.execution.outputs[1:])
        mutant = replace(build, execution=replace(build.execution, outputs=outputs))
        self.rejected(request, mutant, "source_manifest_outputs")

    def test_missing_retained_state_assignment_is_detected(self):
        request, build = fixture("B")
        states = thaw_json(build.execution.states)
        states[0]["assignments"] = states[0]["assignments"][:-1]
        mutant = replace(build, execution=replace(build.execution, states=states))
        self.rejected(request, mutant, "source_manifest_states")

    def test_relabeling_source_model_does_not_prove_changed_operator(self):
        request, build = fixture()

        def change(refinement):
            target = next(node.id for node in refinement.behavior.nodes if node.kind == "and")
            behavior = replace(refinement.behavior, nodes=tuple(replace(node, kind="or") if node.id == target else node
                                                                for node in refinement.behavior.nodes))
            components = tuple(replace(component, identities=tuple(
                replace(pin, content_fingerprint=behavior.fingerprint) if pin.kind == "model" else pin
                for pin in component.identities)) for component in refinement.components)
            return replace(refinement, behavior=behavior, components=components)

        changed, mutant = changed_library(request, build, change)
        self.rejected(changed, mutant, "model_operation_mismatch")

    def test_component_model_pin_cannot_name_unrelated_graph(self):
        request, build = fixture()

        def change(refinement):
            component = refinement.components[0]
            pins = tuple(replace(pin, content_fingerprint="0" * 64) if pin.kind == "model" else pin
                         for pin in component.identities)
            return replace(refinement, components=(replace(component, identities=pins), *refinement.components[1:]))

        changed, mutant = changed_library(request, build, change)
        self.rejected(changed, mutant, "component_model_authority")

    def test_omitted_plan_placement_and_false_ledger_are_detected(self):
        request, build = fixture("D")
        missing = replace(build, plan=replace(build.plan, placements=build.plan.placements[:-1]))
        self.rejected(request, missing, "plan_placements")
        entry = build.plan.ledger[0]
        forged = replace(build, plan=replace(build.plan, ledger=(replace(entry, reasons=("invented",)), *build.plan.ledger[1:])))
        self.rejected(request, forged, "plan_requirement_ledger")

    def test_helper_capacity_cannot_be_waived_by_stored_plan(self):
        request = make_architecture_request("A", variants=("one_rna_helper",))
        build = compile_payload_architecture(request)
        self.assertEqual(build.status, "compiled")

        def change(refinement):
            helper = refinement.helpers[0]
            # One declared user is the only legal exclusive allocation; a second
            # independently modeled component makes the capacity violation real.
            extra = refinement.components[-1].id
            users = tuple(dict.fromkeys((*helper.consumer_component_ids, extra)))
            return replace(refinement, helpers=(replace(helper, consumer_component_ids=users, capacity=1),))

        changed, mutant = changed_library(request, build, change)
        self.rejected(changed, mutant, "helper_capacity")

    def test_helper_cyclic_bootstrap_is_rejected(self):
        request, build = fixture("D")

        def change(refinement):
            helper = refinement.helpers[0]
            return replace(refinement, helpers=(replace(helper, depends_on=(helper.id,)), *refinement.helpers[1:]))

        changed, mutant = changed_library(request, build, change)
        self.rejected(changed, mutant, "helper_initialization_ungrounded")

    def test_external_helper_needs_an_explicit_observation_bridge(self):
        request, build = fixture("D")

        def change(refinement):
            helper = refinement.helpers[0]
            return replace(refinement, helpers=(replace(helper, availability="external", placement_id=None),
                                                 *refinement.helpers[1:]))

        changed, mutant = changed_library(request, build, change)
        self.rejected(changed, mutant, "helper_external_observation_unbound")

    def test_channel_sender_receiver_and_initial_type_are_independent_authority(self):
        request, build = fixture("D")

        def change(refinement):
            channel = refinement.channels[0]
            return replace(refinement, channels=(replace(channel, sender_node_id=channel.receiver_node_id),))

        changed, mutant = changed_library(request, build, change)
        self.rejected(changed, mutant, "channel_source_correspondence")
        changed, mutant = changed_library(request, build, lambda item: replace(item, channels=(
            replace(item.channels[0], initial_value=True),)))
        self.rejected(changed, mutant, "channel_initial_value")

    def test_forged_separate_domains_cannot_share_shutdown_input(self):
        request, build = fixture(independent=True)

        def change(refinement):
            context = next(item.controlling_node_ids for item in refinement.controls if item.kind == "activation")
            return replace(refinement, controls=tuple(replace(item, controlling_node_ids=context)
                if item.kind == "shutdown" else item for item in refinement.controls))

        changed, mutant = changed_library(request, build, change)
        self.rejected(changed, mutant, "independent_control_inputs_coupled")

    def test_distinct_inputs_do_not_prove_independence_when_one_controls_both(self):
        request, build = fixture(independent=True)

        def change(refinement):
            context = next(item.controlling_node_ids for item in refinement.controls if item.kind == "activation")
            first = next(item.id for item in refinement.controls if item.kind == "shutdown")
            return replace(refinement, controls=tuple(replace(item, controlling_node_ids=context)
                if item.id == first else item for item in refinement.controls))

        changed, mutant = changed_library(request, build, change)
        self.rejected(changed, mutant, "independent_control_cross_influence")

    def test_missing_output_quantity_authority_is_not_preserved_by_model_match(self):
        request, build = fixture()
        from biocompiler.ir.circuit_observations import ProductKind, QuantityKind
        requirement = request.circuit.requirements[0]
        product = requirement.behavior.output
        changed_product = replace(product, kind=ProductKind.RNA_PRODUCT,
                                  observation=replace(product.observation, quantity=QuantityKind.RNA_ABUNDANCE))
        requirement = replace(requirement, behavior=replace(requirement.behavior, output=changed_product))
        changed = replace(request, circuit=replace(request.circuit, requirements=(requirement, *request.circuit.requirements[1:])))
        mutant = replace(build, request_fingerprint=changed.fingerprint)
        self.rejected(changed, mutant, "supplementary_output_authority")

    def test_imported_pass_receipt_is_replayed(self):
        request, build = fixture()
        receipt = check_payload_architecture(build, expected_request=request)
        mutated = replace(receipt, assumptions=(*receipt.assumptions, "fabricated"))
        from biocompiler.errors import SerializationError
        with self.assertRaises(SerializationError):
            verify_payload_architecture(mutated, build, expected_request=request)

    def test_self_consistent_changed_bases_need_original_template_authority(self):
        from biocompiler.compiler.circuit_construction import build_circuit_construction
        request, build = fixture()
        authority = build.construction.request
        root = authority.sources[0]
        changed = replace(root, molecule=replace(root.molecule, sequence="UGCAUG"))
        changed_authority = replace(authority, sources=(changed, *authority.sources[1:]))
        independently_rebuilt = build_circuit_construction(changed_authority)
        self.assertTrue(independently_rebuilt.assessment.passed)
        mutant = replace(build, construction=independently_rebuilt)
        self.rejected(request, mutant, "construction_template_authority")

    def test_delivered_helpers_count_toward_rna_partition_limits(self):
        request, build = fixture("D")
        actual_count = len(build.molecules.molecules)
        self.assertEqual(actual_count, 4)
        changed = replace(request, constraints=replace(request.constraints, max_count=2))
        mutant = replace(build, request_fingerprint=changed.fingerprint)
        self.rejected(changed, mutant, "maximum_rna_count")

    def test_co_delivery_cannot_be_replaced_by_independent_delivery(self):
        request, build = fixture("D")
        groups = tuple(replace(item, mode="independent", same_recipient=False)
                       for item in request.constraints.delivery_groups)
        changed = replace(request, constraints=replace(request.constraints, delivery_groups=groups))
        mutant = replace(build, request_fingerprint=changed.fingerprint)
        self.rejected(changed, mutant, "helper_co_delivery_missing")

    def test_production_control_is_not_existing_activity_control(self):
        request, build = fixture()

        def change(refinement):
            control = next(item for item in refinement.controls if item.kind == "shutdown")
            return replace(refinement, controls=tuple(replace(item, kind="activity_control")
                           if item.id == control.id else item for item in refinement.controls))

        changed, mutant = changed_library(request, build, change)
        self.rejected(changed, mutant, "activity_control_not_realized")

    def test_partial_independent_models_compose_a_complete_exact_cover(self):
        import biocompiler as bc
        from biocompiler.compiler.behavior import lower_to_behavior
        from biocompiler.compiler.request import BuildRequest
        from biocompiler.ir.payload_architecture import (
            ArchitectureBinding, ArchitectureOutputBinding, ArchitecturePlacement,
            PayloadArchitectureLibrary, PayloadArchitectureRefinement,
        )
        from examples.executable_payload import artificial_template
        from examples.payload_architectures import ASSUMPTION, _component, _output_product

        request = make_architecture_request("A", variants=("one_rna",), exact_count=2)
        refinements = []
        # Supplier fragments are authored independently. Their explicit source
        # maps are checked as claims, never used to generate the supplier models.
        maps = ((1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13),
                (1, 2, 3, 4, 7, 8, 14, 15, 16, 17, 18))
        for index, label in enumerate(("alpha", "beta")):
            program = bc.Therapy("independent_supplier_fragment_" + label)
            cell = program.engineer("recipient", cell_type="human_T_cell")
            active = cell.environment.signal("context").present()
            stop = cell.environment.signal("stop_" + label).present()
            cell.when(active & ~stop).do(cell.secrete("artificial_" + label))
            model = lower_to_behavior(BuildRequest.freeze(program.freeze(), target=request.source.target,
                                                          behavior_profile=request.source.behavior_profile))
            self.assertEqual(len(model.nodes), 11)
            mapping = {f"n{offset:06d}": f"n{source:06d}"
                       for offset, source in enumerate(maps[index], 1)}
            owned = tuple(node.id for node in model.nodes
                          if node.kind == "rule" or node.kind.startswith("action."))
            component = _component("component." + label, model, "n000001")
            template = artificial_template("fragment", "n000001", helper=False)
            placement = ArchitecturePlacement("rna", template.id, "payload", "n000001", "cytoplasm",
                                               "delivery.n000001")
            binding = ArchitectureBinding("binding", owned, (component.id,), (template.id,), (placement.id,))
            output = ArchitectureOutputBinding("output", "response." + str(index), ("n000010",),
                                                _output_product("artificial_" + label, index),
                                                bc.CircuitLifecycle("production_control"))
            refinements.append(PayloadArchitectureRefinement(
                "fragment." + label, "1", model, mapping, owned, (component,), (template,),
                (binding,), (placement,), (ASSUMPTION,), output_contracts=(output,)))
        request = replace(request, library=PayloadArchitectureLibrary("independent-partial-models", tuple(refinements)))
        build = compile_payload_architecture(request)
        checked = check_payload_architecture(build, expected_request=request)
        self.assertEqual(build.status, "compiled", build.alternatives)
        self.assertTrue(checked.translation_complete, checked.diagnostics)
        self.assertEqual(build.plan.selected_refinement_ids, ("fragment.alpha", "fragment.beta"))
        self.assertEqual(len(build.molecules.molecules), 2)
        self.assertEqual(sum(item.eligible for item in build.alternatives), 1)
        context = next(item for item in build.plan.ledger if item.id == "source:n000003")
        self.assertEqual(context.refinement_ids, ("fragment.alpha", "fragment.beta"))

    def test_local_store_cannot_be_relabelled_as_unimplemented_boundary(self):
        request, build = fixture("B")

        def change(refinement):
            state = next(node.id for node in refinement.behavior.nodes if node.kind == "state")
            return replace(refinement, owned_node_ids=tuple(item for item in refinement.owned_node_ids if item != state))

        changed, mutant = changed_library(request, build, change)
        self.rejected(changed, mutant, "unowned_executable_state")

    def test_installed_action_cannot_hide_behind_ownership_label(self):
        request, build = fixture()

        def change(refinement):
            action = next(node.id for node in refinement.behavior.nodes if node.kind == "action.secrete")
            return replace(refinement, owned_node_ids=tuple(item for item in refinement.owned_node_ids if item != action))

        changed, mutant = changed_library(request, build, change)
        self.rejected(changed, mutant, "unowned_executable_action.secrete")

    def test_startup_labels_do_not_bootstrap_mutually_dependent_helper_providers(self):
        from biocompiler.ir.component_contracts import DependencyRequirement, ProvidedCapability

        request = make_architecture_request("A", variants=("one_rna_helper",))
        refinement = request.library.refinements[0]
        helper = refinement.helpers[0]
        consumer = helper.consumer_component_ids[0]
        components = tuple(
            replace(component, dependencies=(DependencyRequirement("needs_second", "second_helper",
                helper.recipient_role, "cell", helper.compartment),))
            if component.id == helper.provider_component_id else
            replace(component, capabilities=(ProvidedCapability("second_helper", helper.recipient_role,
                "cell", helper.compartment),)) if component.id == consumer else component
            for component in refinement.components)
        placement = next(item for item in refinement.placements if item.member_id == "payload")
        second = replace(helper, id="second_helper", capability="second_helper",
                         consumer_component_ids=(helper.provider_component_id,),
                         placement_id=placement.id, provider_component_id=consumer)
        self.assertEqual(helper.initialization, "available_at_start")
        self.assertEqual(second.initialization, "available_at_start")
        self.assertEqual(helper.depends_on, ())
        self.assertEqual(second.depends_on, ())
        refinement = replace(refinement, components=components, helpers=(helper, second))
        request = replace(request, library=replace(request.library, refinements=(refinement,)))
        build = compile_payload_architecture(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("component_dependency_ungrounded" in gap.code
                            for candidate in build.alternatives for gap in candidate.gaps))

    def test_distinct_helper_providers_on_one_rna_are_functionally_disjoint(self):
        request = dependency_request()
        build = compile_payload_architecture(request)
        self.assertEqual(build.status, "compiled", build.alternatives)
        self.assertEqual(len(build.molecules.molecules), 1)
        self.assertTrue(check_payload_architecture(build, expected_request=request).translation_complete)

    def test_aliased_helper_labels_do_not_hide_shared_provider(self):
        request = dependency_request()
        refinement = request.library.refinements[0]
        first, second = refinement.helpers
        refinement = replace(refinement, helpers=(first, replace(second,
                                         provider_component_id=first.provider_component_id)))
        request = replace(request, library=replace(request.library, refinements=(refinement,)))
        build = compile_payload_architecture(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("forbidden_shared_dependency:dependency-separation" in gap.code
                            for candidate in build.alternatives for gap in candidate.gaps))

    def test_transitive_helper_prerequisite_remains_a_shared_dependency(self):
        from biocompiler.ir.component_contracts import ProvidedCapability
        from biocompiler.ir.payload_architecture import ArchitectureBinding, ArchitectureHelper
        from examples.payload_architectures import ASSUMPTION, _component

        request = dependency_request()
        refinement = request.library.refinements[0]
        first, second = refinement.helpers
        provider = _component("shared.provider", refinement.behavior, first.recipient_role)
        provider = replace(provider, capabilities=(ProvidedCapability("shared_capability", first.recipient_role,
                                                                      "cell", "cytoplasm"),))
        first_action = request.constraints.control_requirements[0].behavior_node_ids[0]
        placement = refinement.placements[0]
        binding = ArchitectureBinding("shared.provider.binding", (first_action,), (provider.id,),
                                      (placement.template_id,), (placement.id,))
        common = ArchitectureHelper("shared.helper", "shared_capability", first.consumer_component_ids,
            first.recipient_role, "cytoplasm", "same_rna", "available_at_start", "shared", 1,
            (ASSUMPTION,), placement.id, provider.id)
        refinement = replace(refinement, components=(*refinement.components, provider),
                             bindings=(*refinement.bindings, binding),
                             helpers=(replace(first, depends_on=(common.id,)),
                                      replace(second, depends_on=(common.id,)), common))
        request = replace(request, library=replace(request.library, refinements=(refinement,)))
        build = compile_payload_architecture(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("forbidden_shared_dependency:dependency-separation" in gap.code
                            for candidate in build.alternatives for gap in candidate.gaps))

    def test_executable_supplementary_observations_are_retained_as_unresolved(self):
        from biocompiler.ir.circuit_intent import CircuitInputBinding
        from examples.circuit_intent import observation

        request, _ = fixture()
        requirement = request.circuit.requirements[0]
        supplied = observation("additional_sensor_declaration")
        requirement = replace(requirement, behavior=replace(requirement.behavior, inputs=(supplied,)),
                              input_bindings=(CircuitInputBinding(supplied.id, "n000003"),))
        request = replace(request, circuit=replace(request.circuit,
                          requirements=(requirement, *request.circuit.requirements[1:])))
        build = compile_payload_architecture(request)
        checked = check_payload_architecture(build, expected_request=request)
        self.assertEqual(build.status, "partial")
        self.assertTrue(checked.passed, checked.diagnostics)
        self.assertFalse(checked.translation_complete)
        self.assertIn("executable_input_observation_mapping:response.0", checked.unresolved)

    def test_antigen_identity_cannot_be_changed_by_supplementary_product_pin(self):
        import biocompiler as bc
        from types import SimpleNamespace
        from biocompiler.compiler.behavior import lower_to_behavior
        from biocompiler.compiler.request import BuildRequest
        from biocompiler.ir.circuit_intent import CircuitRequirement, ExecutableCircuitBehavior
        from biocompiler.ir.payload_architecture import ArchitectureOutputBinding
        from biocompiler.verification.payload_architecture import _supplementary_checks
        from examples.payload_architectures import _output_product

        original, _ = fixture()
        therapy = bc.Therapy("independent_antigen_identity")
        cell = therapy.engineer("recipient", cell_type="human_T_cell")
        cell.when(cell.environment.signal("context").present()).do(cell.present("declared_antigen"))
        source = BuildRequest.freeze(therapy.freeze(), target=original.source.target,
                                     behavior_profile=original.source.behavior_profile)
        behavior = lower_to_behavior(source)
        action = next(node.id for node in behavior.nodes if node.kind == "action.present")
        product = _output_product("different_antigen", 0)
        lifecycle = bc.CircuitLifecycle("production_control")
        required = ExecutableCircuitBehavior((), behavior, product, lifecycle, action_ids=(action,))
        requirement = CircuitRequirement("response", required, behavior.get(action).role,
                                         tuple(node.id for node in behavior.nodes), None)
        contract = ArchitectureOutputBinding("output", "response", (action,), product, lifecycle)
        selected = SimpleNamespace(output_contracts=(contract,),
                                   source_bindings={node.id: node.id for node in behavior.nodes},
                                   owned_node_ids=(action,))
        failures, _ = _supplementary_checks(SimpleNamespace(source=source,
                                 circuit=SimpleNamespace(requirements=(requirement,))), (selected,))
        self.assertIn("supplementary_source_product:response", failures)

    def test_duplicate_transport_edge_and_inconsistent_baseline_are_rejected(self):
        import biocompiler as bc
        request, build = fixture("D")

        def duplicate(refinement):
            channel = refinement.channels[0]
            return replace(refinement, channels=(channel, replace(channel, id="duplicate.transport")))

        changed, mutant = changed_library(request, build, duplicate)
        self.rejected(changed, mutant, "duplicate_channel_transport_edge")

        def different_baseline(refinement):
            channel = refinement.channels[0]
            return replace(refinement, channels=(channel, replace(channel, id="second.transport",
                                                                   initial_value=bc.Level(1).to_dict())))

        changed, mutant = changed_library(request, build, different_baseline)
        self.rejected(changed, mutant, "inconsistent_channel_receiver_contract")


if __name__ == "__main__":
    unittest.main()
