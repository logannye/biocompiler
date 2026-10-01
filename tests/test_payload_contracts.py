"""Executable realization authority is exact, immutable and molecule-complete."""

from dataclasses import FrozenInstanceError, replace
import unittest

from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_construction import (
    MemberRequirement, OutputMember, ProductPort, ProcessingProduct,
    RNACleavageOperation, RoleDeclaration, RootSource, TransformStep, ValueRef,
    ValueSelection,
)
from biocompiler.ir.circuit_transitions import ChemistryTransition, FeatureTransition
from biocompiler.ir.component_contracts import (
    ComponentRecord, PinnedIdentity, ProvidedCapability, SyntheticOperatorModel,
)
from biocompiler.ir.composition import Provider
from biocompiler.ir.payload_contracts import (
    PayloadCapabilityBinding, PayloadComponentContract, PayloadContractLibrary,
    PayloadPortBinding, PayloadTemplate, merge_payload_templates,
    namespace_payload_template,
)
from biocompiler.semantics.component_contracts import (
    OperatingDomain, PortContract, STATELESS_TIMING, ValueDomain,
)
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan
from biocompiler.semantics.types import BOOLEAN
from examples.circuit_intent import make_circuit_requests
from examples.circuit_molecules import fixture_provenance, make_molecule


def payload_template():
    source = RootSource("source", make_molecule("tiny", "ACGU", coding_status="noncoding"),
                        fixture_provenance("root"))
    member = OutputMember("payload", ValueRef("root", "source"), "payload.frame",
                          "delivered_rna", "complete", "noncoding", fixture_provenance("output"))
    requirement = MemberRequirement("required", "payload", "payload", None, None,
                                    (RoleDeclaration("role", "cell", "requested_payload", "cytoplasm"),))
    return PayloadTemplate("template", (source,), (), (member,), (requirement,))


def executable_component(operation="output"):
    inputs = () if operation == "input" else ("in",)
    ports = tuple(PortContract(
        identity, direction, "signal", BOOLEAN, "1", "cell", "cell", "cytoplasm",
        STATELESS_TIMING, ValueDomain.boolean(), ValueDomain.boolean())
        for identity, direction in ((*((identity, "input") for identity in inputs), ("out", "output"))))
    return ComponentRecord(
        "component", "1", "synthetic_model", operation, ("human",), ports,
        OperatingDomain(), (PinnedIdentity("model", "declared-model", "1", "a" * 64),),
        synthetic_model=SyntheticOperatorModel(operation, input_ports=inputs))


def payload_contract():
    return PayloadComponentContract(
        "contract", executable_component(), payload_template(),
        (PayloadPortBinding("in", "payload", "cytoplasm"),
         PayloadPortBinding("out", "payload", "cytoplasm")),
        ("The supplied artificial sequence is assumed to realize the declared software model.",),
        effect={"kind": "secrete", "attributes": {"ongoing": True}, "product": "fixture_product"})


class PayloadContractTests(unittest.TestCase):
    def test_roundtrip_identity_and_nested_immutability(self):
        contract = payload_contract()
        library = PayloadContractLibrary("library", (contract,))
        for artifact in (contract.template, *contract.port_bindings, contract, library):
            with self.subTest(artifact=type(artifact).__name__):
                restored = type(artifact).from_json(artifact.to_json())
                self.assertEqual(restored, artifact)
                self.assertEqual(restored.fingerprint, artifact.fingerprint)
                with self.assertRaises(FrozenInstanceError):
                    artifact.id = "other"
        with self.assertRaises(TypeError):
            contract.effect["attributes"]["ongoing"] = False
        data = contract.to_dict()
        data["effect"]["attributes"]["ongoing"] = False
        self.assertTrue(contract.effect["attributes"]["ongoing"])

    def test_template_keeps_every_member_and_processing_relationship(self):
        original = payload_template()
        provenance = fixture_provenance("processing")
        ports = tuple(ProductPort(identity, identity + ".frame", "RNA", "linear",
                                  ChemistryTransition("exact_inheritance", None, (), provenance),
                                  FeatureTransition((), (), provenance))
                      for identity in ("left", "right"))
        paths = tuple(CoordinatePath(original.sources[0].molecule.space.id, (IndexSpan(start, start + 2),), "+")
                      for start in (0, 2))
        step = TransformStep("cleave", RNACleavageOperation(ValueSelection(ValueRef("root", "source")),
                             tuple(ProcessingProduct(port.id, path) for port, path in zip(ports, paths))),
                             ports, ("Declared processing only.",), provenance)
        members = tuple(replace(original.output_members[0], id=identity,
                                value=ValueRef("product", identity), space_id=identity + ".final")
                        for identity in ("left", "right"))
        requirements = (
            replace(original.requirements[0], member_id="left"),
            MemberRequirement("helper", "delivered_helper", "right", None, None,
                              (RoleDeclaration("helper.role", "cell", "helper", "cytoplasm"),)))
        template = replace(original, steps=(step,), output_members=members, requirements=requirements)
        namespaced = namespace_payload_template(template, "p000_")
        request = namespaced.to_construction_request(make_circuit_requests()["product"])
        self.assertEqual({item.member_id for item in request.requirements}, {"p000_left", "p000_right"})
        self.assertEqual(request.steps[0].operation.products[0].path.space_id, "p000_tiny.space")
        self.assertEqual(request.steps[0].operation.products[0].port_id, "p000_left")
        with self.assertRaisesRegex(SerializationError, "contribute to an output"):
            replace(template, output_members=members[:1], requirements=requirements[:1])

    def test_materialization_uses_existing_full_source_authority(self):
        template = payload_template()
        circuit = make_circuit_requests()["product"]
        request = template.to_construction_request(circuit, id="compiled")
        self.assertEqual(request.circuit, circuit)
        self.assertEqual(PayloadTemplate.from_construction_request(request, id=template.id), template)
        self.assertEqual(request.sources[0].molecule.sequence, "ACGU")

    def test_namespacing_preserves_exact_bases_and_provenance(self):
        template = payload_template()
        instance = namespace_payload_template(template, "p003_")
        self.assertEqual(instance.sources[0].id, "p003_source")
        self.assertEqual(instance.output_members[0].value.id, "p003_source")
        self.assertEqual(instance.sources[0].molecule.sequence, template.sources[0].molecule.sequence)
        self.assertEqual(instance.sources[0].molecule.chemistry, template.sources[0].molecule.chemistry)
        self.assertEqual(instance.sources[0].molecule.provenance, template.sources[0].molecule.provenance)
        self.assertEqual(instance.sources[0].molecule.assembly[0].source_space,
                         template.sources[0].molecule.assembly[0].source_space)
        self.assertEqual(instance.sources[0].molecule.assembly[0].destination.space_id, "p003_tiny.space")
        self.assertEqual(instance.requirements[0].roles[0].id, "p003_role")
        self.assertEqual(instance.requirements[0].roles[0].role, "cell")

    def test_merge_retains_repeated_component_copies(self):
        template = payload_template()
        request = merge_payload_templates(
            [namespace_payload_template(template, "p000_"), namespace_payload_template(template, "p001_")],
            make_circuit_requests()["product"], id="complete")
        self.assertEqual(len(request.output_members), 2)
        self.assertEqual({source.molecule.sequence for source in request.sources}, {"ACGU"})
        with self.assertRaisesRegex(SerializationError, "Duplicate"):
            merge_payload_templates([template, template], request.circuit, id="collision")

    def test_binding_requires_exact_model_ports_and_compartments(self):
        contract = payload_contract()
        for bindings in (
            contract.port_bindings[:1],
            (*contract.port_bindings, PayloadPortBinding("extra", "payload", "cytoplasm")),
            (replace(contract.port_bindings[0], compartment="nucleus"), contract.port_bindings[1]),
            (replace(contract.port_bindings[0], member_id="absent"), contract.port_bindings[1]),
        ):
            with self.subTest(bindings=bindings), self.assertRaises(SerializationError):
                replace(contract, port_bindings=bindings)

    def test_only_external_observation_adapter_can_omit_bases(self):
        component = executable_component("input")
        binding = PayloadPortBinding("out", None, "cytoplasm", external_id="signal")
        adapter = PayloadComponentContract("adapter", component, None, (binding,), ("Input access is assumed.",))
        self.assertIsNone(adapter.template)
        with self.assertRaisesRegex(SerializationError, "exact executable port meaning"):
            replace(adapter, port_bindings=(replace(binding, external_id="different-signal"),))
        contract = payload_contract()
        with self.assertRaises(SerializationError):
            replace(contract, template=None)
        with self.assertRaisesRegex(SerializationError, "material binding"):
            replace(contract, port_bindings=tuple(replace(item, member_id=None, external_id="signal")
                                                 for item in contract.port_bindings))
        for arguments in (("out", None, "cytoplasm"), ("out", "payload", "cytoplasm", None, "signal")):
            with self.assertRaises(SerializationError):
                PayloadPortBinding(*arguments)

    def test_capabilities_require_material_coverage(self):
        contract = payload_contract()
        capability = ProvidedCapability("helper_activity", "cell", "cell", "cytoplasm")
        component = replace(contract.component, capabilities=(capability,))
        with self.assertRaisesRegex(SerializationError, "every provided capability"):
            replace(contract, component=component)
        bound = replace(contract, component=component,
                        capability_bindings=(PayloadCapabilityBinding("helper_activity", "payload", "cytoplasm"),))
        self.assertEqual(bound.component.capabilities[0], capability)
        with self.assertRaisesRegex(SerializationError, "absent template member"):
            replace(bound, capability_bindings=(replace(bound.capability_bindings[0], member_id="absent"),))

    def test_exact_effect_and_assumptions_are_part_of_authority(self):
        contract = payload_contract()
        self.assertNotEqual(contract.fingerprint, replace(contract, effect={**contract.effect, "product": "different"}).fingerprint)
        with self.assertRaisesRegex(SerializationError, "explicit assumptions"):
            replace(contract, assumptions=())
        with self.assertRaisesRegex(SerializationError, "exact kind, attributes and product"):
            replace(contract, effect={"kind": "secrete", "attributes": {}})
        with self.assertRaisesRegex(SerializationError, "Only an output"):
            PayloadComponentContract("bad", executable_component("input"), None,
                                     (PayloadPortBinding("out", None, "cytoplasm", external_id="signal"),),
                                     ("Explicit input assumption.",), effect=contract.effect)

    def test_supplementary_output_authority_is_typed_paired_and_exact(self):
        contract = payload_contract()
        behavior = make_circuit_requests()["product"].requirements[0].behavior
        with self.assertRaisesRegex(SerializationError, "both a product and lifecycle"):
            replace(contract, output_product=behavior.output)
        bound = replace(contract, output_product=behavior.output, output_lifecycle=behavior.lifecycle)
        self.assertEqual(PayloadComponentContract.from_json(bound.to_json()), bound)
        self.assertNotEqual(bound.fingerprint, contract.fingerprint)
        with self.assertRaisesRegex(SerializationError, "Only an output"):
            PayloadComponentContract("input", executable_component("input"), None,
                                     (PayloadPortBinding("out", None, "cytoplasm", external_id="signal"),),
                                     ("Explicit input assumption.",), output_product=behavior.output,
                                     output_lifecycle=behavior.lifecycle)

    def test_conflicting_same_identity_component_authority_rejected(self):
        contract = payload_contract()
        alternative = replace(contract, id="alternative", assumptions=("Distinct template alternative.",))
        self.assertEqual(len(PayloadContractLibrary("library", (contract, alternative)).contracts), 2)
        changed = replace(alternative, component=replace(contract.component, assumptions=("Changed component model authority.",)))
        with self.assertRaisesRegex(SerializationError, "Conflicting component authority"):
            PayloadContractLibrary("library", (contract, changed))

    def test_provider_prerequisites_remain_explicit(self):
        provider = Provider("external", "host", (), ("human",), depends_on=("missing",))
        with self.assertRaisesRegex(SerializationError, "absent provider"):
            PayloadContractLibrary("library", (), (provider,))
        library = PayloadContractLibrary("library", (), (replace(provider, depends_on=()),))
        self.assertEqual(PayloadContractLibrary.from_json(library.to_json()), library)

    def test_template_rejects_dangling_members_and_uncovered_helpers(self):
        template = payload_template()
        with self.assertRaisesRegex(SerializationError, "absent construction value"):
            replace(template, output_members=(replace(template.output_members[0], value=ValueRef("root", "missing")),))
        with self.assertRaisesRegex(SerializationError, "explicit requirement disposition"):
            replace(template, output_members=(*template.output_members,
                    replace(template.output_members[0], id="omitted_helper", space_id="helper.frame")))

    def test_strict_schema_and_resource_limits(self):
        artifact = payload_contract()
        for mutate in (
            lambda data: data.update(extra=True),
            lambda data: data.update(schema_version="future"),
            lambda data: data.update(port_bindings="bad"),
            lambda data: data.update(component=[]),
        ):
            data = artifact.to_dict()
            mutate(data)
            with self.assertRaises(SerializationError):
                PayloadComponentContract.from_dict(data)
        with self.assertRaises(SerializationError):
            PayloadContractLibrary("library", (artifact,) * 257)


if __name__ == "__main__":
    unittest.main()
