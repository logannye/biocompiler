"""Supplied-library selection, exact search budgets and retained source changes."""

from dataclasses import replace
import unittest

from biocompiler.compiler.executable_payload import compile_payload, export_payload_fasta
from biocompiler.errors import SerializationError
from biocompiler.ir.executable_payload import PayloadSelectionConstraints
from biocompiler.ir.intent import thaw_json
from biocompiler.verification.executable_payload import check_payload_build
from examples.executable_payload import make_payload_request
from examples.circuit_molecules import make_molecule


def full_alternatives(build):
    identities = {node.id for node in build.requirements.mechanism.nodes}
    return tuple(item for item in build.alternatives if set(item.selections) == identities)


def replace_source(request, source):
    return replace(request, circuit=replace(request.circuit,
                                            profile=replace(request.circuit.profile, source_request=source)))


def longer_output_alternative(request, *, identity="preferred.long_output"):
    output = next(item for item in request.library.contracts if item.component.implementation_role == "output")
    def extend(source):
        if source.id != "payload.source":
            return source
        molecule = make_molecule(source.molecule.id + ".long", source.molecule.sequence + "AC", coding_status="noncoding")
        features = tuple(replace(feature, path=replace(feature.path, space_id=molecule.space.id))
                         for feature in source.molecule.features)
        return replace(source, molecule=replace(molecule, features=features))

    roots = tuple(extend(source) for source in output.template.sources)
    alternative = replace(output, id=identity, template=replace(output.template, id="longer.template", sources=roots))
    return alternative


class PayloadSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = make_payload_request()

    def test_missing_output_contract_records_every_local_rejection_and_no_sequence(self):
        request = replace(self.request, library=replace(self.request.library, contracts=tuple(
            item for item in self.request.library.contracts if item.component.implementation_role != "output")))
        build = compile_payload(request)
        self.assertEqual(build.status, "no_solution")
        self.assertIsNone(build.molecules)
        output_id = build.requirements.outputs[0].id
        self.assertIn("no_compatible_contract:" + output_id, build.diagnostics)
        rejected = [item for item in build.alternatives if set(item.selections) == {output_id}]
        self.assertEqual(len(rejected), len(request.library.contracts))
        self.assertTrue(all("operation_mismatch" in item.reasons for item in rejected))
        self.assertFalse(full_alternatives(build))
        with self.assertRaisesRegex(SerializationError, "fresh verified construction"):
            export_payload_fasta(build, expected_request=request)

    def test_complete_molecule_budget_includes_helpers(self):
        request = replace(self.request, constraints=PayloadSelectionConstraints(max_total_bases=23))
        build = compile_payload(request)
        self.assertEqual(build.status, "no_solution")
        self.assertIsNone(build.molecules)
        choices = full_alternatives(build)
        self.assertEqual(len(choices), 1)
        self.assertEqual(choices[0].reasons, ("complete_set_nucleotide_budget_exceeded",))
        admitted = compile_payload(replace(request, constraints=replace(request.constraints, max_total_bases=24)))
        self.assertEqual(admitted.status, "compiled")
        self.assertEqual(sum(len(member.sequence) for member in admitted.molecules.molecules), 24)
        self.assertTrue(any(member.id.endswith("helper") for member in admitted.molecules.molecules))

    def test_preference_never_overrides_hard_complete_set_budget(self):
        alternative = longer_output_alternative(self.request)
        request = replace(self.request, library=replace(self.request.library, contracts=(
            *self.request.library.contracts, alternative)), constraints=PayloadSelectionConstraints(
                max_total_bases=24, preferred_contract_ids=(alternative.id,)))
        build = compile_payload(request)
        choices = full_alternatives(build)
        self.assertEqual(len(choices), 2)
        self.assertEqual(build.status, "compiled")
        self.assertNotIn(alternative.id, build.selected.values())
        rejected = next(item for item in choices if alternative.id in item.selections.values())
        self.assertIn("complete_set_nucleotide_budget_exceeded", rejected.reasons)
        self.assertEqual(sum(len(member.sequence) for member in build.molecules.molecules), 24)
        unbounded = compile_payload(replace(request, constraints=replace(request.constraints, max_total_bases=None)))
        self.assertIn(alternative.id, unbounded.selected.values())
        self.assertEqual(sum(len(member.sequence) for member in unbounded.molecules.molecules), 26)

    def test_search_budget_reports_truncation_even_if_examined_candidate_is_feasible(self):
        alternative = longer_output_alternative(self.request)
        request = replace(self.request, library=replace(self.request.library, contracts=(
            *self.request.library.contracts, alternative)), constraints=PayloadSelectionConstraints(max_combinations=1))
        build = compile_payload(request)
        self.assertEqual(build.status, "search_exhausted")
        self.assertEqual(build.diagnostics, ("search_budget_exhausted:1_of_2",))
        choices = full_alternatives(build)
        self.assertEqual(len(choices), 1)
        self.assertTrue(choices[0].eligible)
        self.assertIsNone(build.molecules)
        self.assertFalse(build.selected)
        self.assertFalse(check_payload_build(build, expected_request=request).translation_complete)

    def test_rejected_preferred_contract_does_not_hide_a_later_feasible_candidate(self):
        alternative = longer_output_alternative(self.request, identity="aaa.expensive")
        request = replace(self.request, library=replace(self.request.library, contracts=(
            alternative, *self.request.library.contracts)), constraints=PayloadSelectionConstraints(
                max_total_bases=24, preferred_contract_ids=(alternative.id,)))
        build = compile_payload(request)
        choices = full_alternatives(build)
        self.assertEqual(build.status, "compiled")
        self.assertIn(alternative.id, choices[0].selections.values())
        self.assertFalse(choices[0].eligible)
        self.assertTrue(choices[1].eligible)

    def test_product_source_change_cannot_reuse_previous_sequence_contracts(self):
        changed = make_payload_request(product="different_artificial_product")
        request = replace(changed, library=self.request.library)
        build = compile_payload(request)
        self.assertEqual(build.status, "no_solution")
        output = build.requirements.outputs[0]
        self.assertEqual(output.product, "different_artificial_product")
        self.assertTrue(any("source_action_or_product_mismatch" in item.reasons for item in build.alternatives))
        self.assertIsNone(build.molecules)

    def test_source_guard_edit_demands_an_or_component_or_precise_rejection(self):
        changed = make_payload_request(guard="or")
        request = replace(changed, library=self.request.library)
        build = compile_payload(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(build.requirements.mechanism.find("or"))
        self.assertTrue(any(item.startswith("no_compatible_contract:") for item in build.diagnostics))
        self.assertIsNone(build.molecules)

    def test_source_constraints_survive_partial_translation_and_strict_mode(self):
        source = replace(self.request.source, implementation_constraints={"future_clearance_policy": "explicit_request"})
        request = replace_source(self.request, source)
        partial = compile_payload(request)
        self.assertEqual(partial.status, "partial")
        self.assertEqual(thaw_json(partial.requirements.build_request.implementation_constraints),
                         {"future_clearance_policy": "explicit_request"})
        self.assertIsNotNone(partial.molecules)
        self.assertFalse(check_payload_build(partial, expected_request=request).translation_complete)
        strict = replace(request, constraints=replace(request.constraints, require_complete=True))
        rejected = compile_payload(strict)
        self.assertEqual(rejected.status, "unsupported")
        self.assertIsNone(rejected.molecules)
        self.assertFalse(rejected.alternatives)
        self.assertTrue(any("uninterpreted_implementation_constraints" in item for item in rejected.diagnostics))

    def test_temporal_parameters_cannot_reuse_other_duration_contract(self):
        request = make_payload_request(temporal=True)
        source = request.source
        nodes = tuple(replace(node, attributes={"value": {**thaw_json(node.attributes["value"]),
                                                         "value": 5, "canonical_value": 5}})
                      if node.kind == "literal" else node for node in source.intent.nodes)
        changed = replace_source(request, replace(source, intent=replace(source.intent, nodes=nodes)))
        build = compile_payload(changed)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("operator_parameters_mismatch" in item.reasons for item in build.alternatives))
        self.assertEqual(build.requirements.mechanism.find("held_for")[0].attributes["duration"]["canonical_value"], 5)

    def test_rna_target_cannot_accept_dna_component_support_declaration(self):
        output = next(item for item in self.request.library.contracts if item.component.implementation_role == "output")
        dna = replace(output, component=replace(output.component, supported_targets=("DNA",)))
        request = replace(self.request, library=replace(self.request.library, contracts=tuple(
            dna if item.id == output.id else item for item in self.request.library.contracts)))
        build = compile_payload(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("unsupported_payload_format" in item.reasons for item in build.alternatives))
        self.assertIsNone(build.molecules)
        self.assertEqual(request.source.target.payload_format.value, "RNA")


    def test_capability_material_outside_target_compartment_is_rejected_before_search(self):
        from biocompiler.ir.component_contracts import ProvidedCapability
        from biocompiler.ir.payload_contracts import PayloadCapabilityBinding

        output = next(item for item in self.request.library.contracts if item.component.implementation_role == "output")
        role = output.component.ports[0].role
        requirements = tuple(replace(item, roles=(*item.roles, replace(
            item.roles[0], id="nuclear.material.role", compartment="nucleus")))
            if item.member_id == "payload" else item for item in output.template.requirements)
        changed = replace(output,
                          component=replace(output.component, capabilities=(ProvidedCapability("nuclear_control", role, "cell", "nucleus"),)),
                          template=replace(output.template, requirements=requirements),
                          capability_bindings=(PayloadCapabilityBinding("nuclear_control", "payload", "nucleus"),))
        request = replace(self.request, library=replace(self.request.library, contracts=tuple(
            changed if item.id == output.id else item for item in self.request.library.contracts)))
        build = compile_payload(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("undeclared_physical_compartment" in item.reasons for item in build.alternatives))
        self.assertFalse(full_alternatives(build))

    def test_declared_external_dependency_is_conditional_without_evidence_gate(self):
        from biocompiler.ir.component_contracts import DependencyRequirement, ProvidedCapability
        from biocompiler.ir.composition import Provider

        output = next(item for item in self.request.library.contracts if item.component.implementation_role == "output")
        role = output.component.ports[0].role
        changed = replace(output, component=replace(output.component, dependencies=(
            DependencyRequirement("supply", "declared_input", role, "cell", "cytoplasm"),)))
        contracts = tuple(changed if item.id == output.id else item for item in self.request.library.contracts)
        request = replace(self.request, library=replace(self.request.library, contracts=contracts))
        missing = compile_payload(request)
        self.assertEqual(missing.status, "no_solution")
        self.assertTrue(any(any(reason.startswith("missing_dependency:") for reason in alternative.reasons)
                            for alternative in full_alternatives(missing)))
        provider = Provider("supply", "external", (ProvidedCapability("declared_input", role, "cell", "cytoplasm"),), ("RNA",))
        request = replace(request, library=replace(request.library, providers=(provider,),
                                                   assumptions=(*request.library.assumptions,
                                                                "The nominated external input is supplied as declared.")))
        build = compile_payload(request)
        self.assertEqual(build.status, "compiled")
        self.assertIn("The nominated external input is supplied as declared.", build.assumptions)
        self.assertEqual(check_payload_build(build, expected_request=request).empirical_validation, "unknown")


    def test_missing_material_feature_rejects_preferred_candidate_and_selects_valid_alternative(self):
        output = next(item for item in self.request.library.contracts if item.component.implementation_role == "output")
        invalid = replace(output, id="aaa.invalid_material_binding", port_bindings=tuple(
            replace(binding, feature_id="absent-feature") if binding.port_id == "out" else binding
            for binding in output.port_bindings))
        request = replace(self.request, library=replace(self.request.library, contracts=(
            invalid, *self.request.library.contracts)), constraints=PayloadSelectionConstraints(
                preferred_contract_ids=(invalid.id,)))
        build = compile_payload(request)
        self.assertEqual(build.status, "compiled")
        self.assertIn(output.id, build.selected.values())
        self.assertNotIn(invalid.id, build.selected.values())
        choices = full_alternatives(build)
        self.assertEqual(len(choices), 2)
        rejected = next(item for item in choices if invalid.id in item.selections.values())
        self.assertTrue(any(reason.startswith("independent_check:") and "component_material_feature" in reason
                            for reason in rejected.reasons), rejected.reasons)
        self.assertTrue(check_payload_build(build, expected_request=request).passed)

    def test_missing_material_feature_without_valid_alternative_reports_no_solution(self):
        output = next(item for item in self.request.library.contracts if item.component.implementation_role == "output")
        invalid = replace(output, port_bindings=tuple(
            replace(binding, feature_id="absent-feature") if binding.port_id == "out" else binding
            for binding in output.port_bindings))
        request = replace(self.request, library=replace(self.request.library, contracts=tuple(
            invalid if item.id == output.id else item for item in self.request.library.contracts)))
        build = compile_payload(request)
        self.assertEqual(build.status, "no_solution")
        self.assertIsNone(build.molecules)
        choices = full_alternatives(build)
        self.assertEqual(len(choices), 1)
        self.assertTrue(any(reason.startswith("independent_check:") and "component_material_feature" in reason
                            for reason in choices[0].reasons), choices[0].reasons)


if __name__ == "__main__":
    unittest.main()
