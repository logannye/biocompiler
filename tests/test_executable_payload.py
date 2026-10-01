"""Integrated source-to-RNA selection and construction using artificial controls."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from biocompiler.cli import main
from biocompiler.compiler.executable_payload import compile_payload, export_payload_fasta
from biocompiler.ir.component_contracts import DependencyRequirement
from biocompiler.ir.circuit_intent import CircuitProviderRequirement
from biocompiler.ir.executable_payload import PayloadBuild, PayloadCompilationRequest
from biocompiler.ir.payload_contracts import PayloadContractLibrary
from biocompiler.verification.executable_payload import check_payload_build
from examples.executable_payload import make_payload_request
from examples.circuit_molecules import make_molecule


def with_protein_helper(request, *, category):
    """Supply protein metadata while retaining its explicit member disposition."""
    contracts = []
    for contract in request.library.contracts:
        if contract.template is None or contract.component.implementation_role != "output":
            contracts.append(contract)
            continue
        template = contract.template
        sources = []
        for source in template.sources:
            if source.id == "helper.source":
                protein = make_molecule(source.molecule.id, "ACDEFG", form="mature_protein")
                source = replace(source, molecule=replace(protein, features=source.molecule.features))
            sources.append(source)
        template = replace(
            template,
            sources=tuple(sources),
            output_members=tuple(replace(member, form="mature_protein", coding_status="inapplicable")
                                 if member.id == "helper" else member for member in template.output_members),
            requirements=tuple(replace(item, category=category) if item.member_id == "helper" else item
                               for item in template.requirements),
        )
        contracts.append(replace(contract, template=template))
    return replace(request, library=replace(request.library, contracts=tuple(contracts)))


class ExecutablePayloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = make_payload_request()
        cls.build = compile_payload(cls.request)

    def test_source_guard_product_helpers_and_exact_rna_are_connected(self):
        build = self.build
        self.assertEqual(build.status, "compiled")
        self.assertEqual(build.requirements.source.to_dict(), self.request.source.to_dict())
        self.assertEqual({node.kind for node in build.mechanism.nodes}, {"input", "not", "and", "output"})
        self.assertEqual(build.requirements.outputs[0].product, "artificial_product")
        self.assertEqual(len(build.molecules.molecules), 4)
        self.assertEqual(sorted(item.sequence for item in build.molecules.molecules), ["ACGUAC"] * 3 + ["UGCAUG"])
        self.assertTrue(all(item.space.alphabet == "RNA" for item in build.molecules.molecules))
        self.assertTrue(any(item.purpose == "helper" for item in build.molecules.role_instances))
        self.assertTrue(all(item.chemistry.modification_inventory_status == "declared" for item in build.molecules.molecules))
        verification = check_payload_build(build, expected_request=self.request)
        self.assertTrue(verification.passed)
        self.assertTrue(verification.translation_complete and verification.construction_complete)
        self.assertEqual(verification.empirical_validation, "unknown")
        self.assertEqual(verification.human_therapeutic_admission, "not_admitted")

    def test_roundtrip_idempotence_and_fasta_has_every_rna_member(self):
        request = PayloadCompilationRequest.from_json(self.request.to_json())
        build = PayloadBuild.from_json(self.build.to_json())
        self.assertEqual(build.fingerprint, self.build.fingerprint)
        self.assertEqual(compile_payload(request), self.build)
        fasta = export_payload_fasta(build, expected_request=request)
        for molecule in build.molecules.molecules:
            self.assertIn(">" + molecule.id + " alphabet=RNA\n" + molecule.sequence + "\n", fasta)
        self.assertEqual(fasta.count(">"), len(build.molecules.molecules))

    def test_multiple_outputs_retain_both_products_and_helpers(self):
        request = make_payload_request(multi_output=True)
        build = compile_payload(request)
        self.assertEqual(build.status, "compiled")
        self.assertEqual(len(build.mechanism.outputs), 2)
        self.assertEqual({output.product for output in build.requirements.outputs},
                         {"artificial_product", "artificial_secondary_product"})
        self.assertEqual(len(build.molecules.molecules), 6)
        self.assertEqual(sum(item.purpose == "helper" for item in build.molecules.role_instances), 2)

    def test_temporal_memory_reset_and_shutdown_keep_source_semantics(self):
        for option, operation in (("temporal", "held_for"), ("memory", "memory"), ("pulse", "pulse")):
            with self.subTest(option=option):
                request = make_payload_request(**{option: True})
                build = compile_payload(request)
                self.assertEqual(build.status, "partial")
                self.assertTrue(build.mechanism.find(operation))
                self.assertTrue(build.mechanism.find("not"))
                check = check_payload_build(build, expected_request=request)
                self.assertTrue(check.passed)
                self.assertTrue(check.construction_complete)
                self.assertFalse(check.translation_complete)
                self.assertIn("unresolved:stateless_circuit_projection:response.0", build.diagnostics)

    def test_supplied_dna_member_cannot_be_emitted_by_rna_payload_path(self):
        contracts = []
        for contract in self.request.library.contracts:
            if contract.template is None or contract.component.implementation_role != "output":
                contracts.append(contract)
                continue
            template = contract.template
            sources = []
            for source in template.sources:
                if source.id != "helper.source":
                    sources.append(source)
                    continue
                molecule = make_molecule(source.molecule.id, "ACGTAC", form="delivered_dna", coding_status="noncoding")
                sources.append(replace(source, molecule=replace(molecule, features=source.molecule.features)))
            contracts.append(replace(contract, template=replace(template, sources=tuple(sources),
                output_members=tuple(replace(member, form="delivered_dna") if member.id == "helper" else member
                                     for member in template.output_members))))
        request = replace(self.request, library=replace(self.request.library, contracts=tuple(contracts)))
        build = compile_payload(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("unsupported_final_dna_member:rna_payload_only" in option.reasons
                            for option in build.alternatives))

    def test_delivered_protein_helper_is_outside_rna_payload_scope(self):
        request = with_protein_helper(self.request, category="delivered_helper")
        build = compile_payload(request)
        self.assertEqual(build.status, "no_solution")
        self.assertIsNone(build.molecules)
        helper_id = next(item.member_id for item in self.build.construction.request.requirements
                         if item.category == "delivered_helper")
        reason = "unsupported_delivered_member:rna_payload_only:" + helper_id
        self.assertTrue(any(reason in option.reasons for option in build.alternatives))

    def test_encoded_product_protein_metadata_remains_legal(self):
        request = with_protein_helper(self.request, category="encoded_product")
        build = compile_payload(request)
        self.assertEqual(build.status, "compiled")
        check = check_payload_build(build, expected_request=request)
        self.assertTrue(check.passed and check.translation_complete)
        product_id = next(item.member_id for item in build.construction.request.requirements
                          if item.category == "encoded_product")
        protein = next(item for item in build.molecules.molecules if item.id == product_id)
        self.assertEqual((protein.space.alphabet, protein.sequence), ("protein", "ACDEFG"))
        fasta = export_payload_fasta(build, expected_request=request)
        self.assertNotIn(">" + product_id, fasta)
        self.assertEqual(fasta.count(">"), 3)

    def test_empty_library_retains_precise_missing_implementation_reasons(self):
        request = replace(self.request, library=PayloadContractLibrary("empty", ()))
        build = compile_payload(request)
        self.assertEqual(build.status, "no_solution")
        self.assertIsNone(build.molecules)
        self.assertTrue(any(reason.startswith("no_compatible_contract:") for reason in build.diagnostics))

    def test_stale_product_library_cannot_implement_changed_source_output(self):
        changed = make_payload_request(product="different_artificial_product")
        request = replace(changed, library=self.request.library)
        build = compile_payload(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("source_action_or_product_mismatch" in alternative.reasons
                            for alternative in build.alternatives))

    def test_supplementary_output_kind_and_quantity_need_exact_declared_contract(self):
        requirement = self.request.circuit.requirements[0]
        changed_output = replace(requirement.behavior.output, kind=bc.ProductKind.RNA_PRODUCT,
                                 observation=replace(requirement.behavior.output.observation,
                                                     quantity=bc.QuantityKind.RNA_ABUNDANCE))
        changed = replace(requirement, behavior=replace(requirement.behavior, output=changed_output))
        request = replace(self.request, circuit=replace(self.request.circuit, requirements=(changed,)))
        build = compile_payload(request)
        self.assertEqual(build.status, "no_solution")
        self.assertIsNone(build.molecules)
        self.assertTrue(any(any("output" in reason for reason in option.reasons)
                            for option in build.alternatives))

    def test_unmapped_supplementary_provider_remains_partial_and_strict_emits_nothing(self):
        requirement = self.request.circuit.requirements[0]
        provider = CircuitProviderRequirement(
            "must_supply_helper", bc.ObservationEntity("fixture", "required_helper", "1", "unknown"),
            "co_delivered", "cytoplasm", "same_cell")
        changed = replace(requirement, behavior=replace(requirement.behavior, dependencies=(provider,)))
        request = replace(self.request, circuit=replace(self.request.circuit, requirements=(changed,)))
        build = compile_payload(request)
        self.assertEqual(build.status, "partial")
        self.assertIn("unresolved:circuit_provider_mapping:response.0:must_supply_helper", build.diagnostics)
        check = check_payload_build(build, expected_request=request)
        self.assertTrue(check.passed)
        self.assertFalse(check.translation_complete)
        self.assertTrue(any("circuit_provider_mapping" in item for item in check.unresolved))
        strict = replace(request, constraints=replace(request.constraints, require_complete=True))
        strict_build = compile_payload(strict)
        self.assertEqual(strict_build.status, "unsupported")
        self.assertIsNone(strict_build.molecules)

    def test_contradictory_boolean_mapping_rejected_before_construction(self):
        requirement = self.request.circuit.requirements[0]
        first, second = requirement.behavior.response.inputs
        bad = replace(requirement, behavior=replace(requirement.behavior, response=first | second))
        request = replace(self.request, circuit=replace(self.request.circuit, requirements=(bad,)))
        with self.assertRaisesRegex(bc.SerializationError, "contradicts"):
            compile_payload(request)

    def test_missing_dependency_and_preference_cannot_override_hard_requirements(self):
        contract = next(item for item in self.request.library.contracts if item.component.implementation_role == "output")
        dependency = DependencyRequirement("unprovided", "absent_capability", contract.component.ports[0].role,
                                           "cell", "cytoplasm")
        bad = replace(contract, id="preferred-invalid", component=replace(contract.component,
                      id="invalid-component", dependencies=(dependency,)))
        library = replace(self.request.library, contracts=(*self.request.library.contracts, bad))
        request = replace(self.request, library=library, constraints=replace(self.request.constraints,
                          preferred_contract_ids=(bad.id,)))
        build = compile_payload(request)
        self.assertEqual(build.status, "compiled")
        self.assertNotIn(bad.id, build.selected.values())
        self.assertTrue(any(any(reason.startswith("missing_dependency:") for reason in option.reasons)
                            for option in build.alternatives))

    def test_complete_set_budget_counts_helpers_and_retains_rejection(self):
        # Three payload members use 18 symbols; the required helper adds six.
        request = replace(self.request, constraints=replace(self.request.constraints, max_total_bases=18))
        build = compile_payload(request)
        self.assertEqual(build.status, "no_solution")
        self.assertTrue(any("complete_set_nucleotide_budget_exceeded" in option.reasons
                            for option in build.alternatives))

    def test_search_budget_never_presents_unexplored_alternative_as_optimal(self):
        output = next(item for item in self.request.library.contracts if item.component.implementation_role == "output")
        library = replace(self.request.library, contracts=(*self.request.library.contracts, replace(output, id="second-valid-output")))
        request = replace(self.request, library=library,
                          constraints=replace(self.request.constraints, max_combinations=1))
        build = compile_payload(request)
        self.assertEqual(build.status, "search_exhausted")
        self.assertIsNone(build.molecules)
        self.assertTrue(any(reason.startswith("search_budget_exhausted:") for reason in build.diagnostics))

    def test_reusable_internal_signal_names_do_not_depend_on_source_node_ids(self):
        meanings = {port.meaning for contract in self.request.library.contracts
                    if contract.component.implementation_role != "input"
                    for port in contract.component.ports if port.direction == "output"}
        rename = {meaning: "declared_signal_" + str(index) for index, meaning in enumerate(sorted(meanings))}
        contracts = tuple(replace(contract, component=replace(contract.component, ports=tuple(
            replace(port, meaning=rename.get(port.meaning, port.meaning)) for port in contract.component.ports)))
            for contract in self.request.library.contracts)
        request = replace(self.request, library=replace(self.request.library, contracts=contracts))
        self.assertEqual(compile_payload(request).status, "compiled")

    def test_dna_target_cannot_enter_rna_payload_compilation(self):
        target = replace(self.request.circuit.profile.target, payload_format=bc.PayloadFormat.DNA)
        source = replace(self.request.source, target=target)
        recipient = replace(self.request.circuit.profile.recipient, target_fingerprint=target.fingerprint)
        profile = replace(self.request.circuit.profile, target=target, recipient=recipient,
                          molecular_form=bc.PayloadFormat.DNA, source_request=source)
        circuit = replace(self.request.circuit, profile=profile, requested_form="delivered_dna")
        with self.assertRaisesRegex(bc.SerializationError, "RNA only"):
            replace(self.request, circuit=circuit)

    def test_cli_build_verify_and_fasta_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path, build_path = root / "request.json", root / "build.json"
            request_path.write_text(self.request.to_json(), encoding="utf-8")
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["payload-build", "--request", str(request_path), "--output", str(build_path)]), 0)
                self.assertEqual(main(["payload-verify", str(build_path), "--expected-request", str(request_path)]), 0)
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["payload-fasta", str(build_path), "--expected-request", str(request_path)]), 0)
            self.assertEqual(output.getvalue(), export_payload_fasta(self.build, expected_request=self.request))
            changed = replace(self.request, library=replace(self.request.library,
                              assumptions=(*self.request.library.assumptions, "Additional independent authority assumption.")))
            request_path.write_text(changed.to_json(), encoding="utf-8")
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["payload-verify", str(build_path), "--expected-request", str(request_path)]), 1)
            rejected_output = StringIO()
            with redirect_stdout(rejected_output), redirect_stderr(StringIO()):
                self.assertEqual(main(["payload-fasta", str(build_path), "--expected-request", str(request_path)]), 2)
            self.assertEqual(rejected_output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
