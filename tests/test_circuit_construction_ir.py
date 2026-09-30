"""Frozen construction authority tests using tiny artificial software records."""

from dataclasses import FrozenInstanceError, replace
import json
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_construction import (
    MAX_ASSUMPTIONS,
    MAX_AMOUNT_DECLARATIONS,
    MAX_COMPLEX_MEMBERS,
    MAX_PROCESSING_PRODUCTS,
    MAX_SELECTIONS,
    MAX_SOURCES,
    MAX_TRANSLATION_BRANCHES,
    MAX_TRANSLATION_PRODUCTS,
    BaseEditingOperation,
    AmountDeclaration,
    CircularizationOperation,
    CircuitConstructionRequest,
    ConcatenateOperation,
    ComplexMemberConstituent,
    ComplexMemberPlan,
    ConditionalTranslationOperation,
    MemberRequirement,
    MultiORFTranslationOperation,
    OrientationOperation,
    OutputMember,
    PeptideProduct,
    ProductPort,
    ProcessingProduct,
    ProteinCleavageOperation,
    ProteinSplicingOperation,
    RNACleavageOperation,
    RNASplicingOperation,
    RibosomalSkippingOperation,
    RoleDeclaration,
    RootSource,
    SliceOperation,
    TranscriptionOperation,
    TransformStep,
    TranslationBranch,
    TranslationOperation,
    TranslationProduct,
    ValueRef,
    ValueSelection,
    operation_selections,
)
from biocompiler.ir.circuit_intent import CircuitProviderRequirement
from biocompiler.ir.circuit_observations import ObservationEntity
from biocompiler.ir.circuit_payloads import (
    MAX_PAYLOAD_CONTRACTS,
    PayloadStructureContract,
    RequiredPayloadRegion,
)
from biocompiler.ir.circuit_recoding import (
    CanonicalBaseEdit,
    ChemicalBaseEdit,
    CodonRecoding,
    TranslationPolicy,
)
from biocompiler.ir.circuit_transitions import (
    ChemistryDisposition,
    ChemistryTransition,
    FeatureDisposition,
    FeatureTransition,
)
from biocompiler.ir.molecule_chemistry import ChemicalIdentity
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan
from examples.circuit_intent import make_circuit_requests
from examples.circuit_molecules import fixture_provenance, make_molecule


def root(identity="source_A"):
    return RootSource(
        identity,
        make_molecule(identity + ".molecule", "ACGU", coding_status="noncoding"),
        fixture_provenance(identity),
    )


def port(identity="product_A"):
    provenance = fixture_provenance(identity)
    return ProductPort(
        identity,
        identity + ".frame",
        "RNA",
        "linear",
        ChemistryTransition("exact_inheritance", None, (), provenance),
        FeatureTransition((), (), provenance),
    )


def step(identity="step_A", input_id="source_A", kind="root", product_id="product_A"):
    return TransformStep(
        identity,
        SliceOperation(ValueSelection(ValueRef(kind, input_id))),
        (port(product_id),),
        (),
        fixture_provenance(identity),
    )


def output(identity="output_A", value_id="product_A", kind="product"):
    return OutputMember(
        identity,
        ValueRef(kind, value_id),
        identity + ".frame",
        "delivered_rna",
        "complete",
        "noncoding",
        fixture_provenance(identity),
    )


def member(identity="required_A", output_id="output_A", category="payload"):
    purpose = {
        "payload": "requested_payload",
        "delivered_helper": "helper",
        "encoded_product": "helper",
        "host_provider": "host_provider",
        "experimental_input": "external_input",
        "control": "assay_control",
        "assay_reference": "assay_control",
    }[category]
    return MemberRequirement(
        identity,
        category,
        output_id,
        None,
        None,
        (RoleDeclaration(identity + ".role", "fixture_role", purpose, "cytoplasm"),),
    )


def request():
    return CircuitConstructionRequest(
        "construction_fixture",
        make_circuit_requests()["product"],
        (root(),),
        (step(),),
        (output(),),
        (member(),),
        "strict",
    )


def processing_request(operation_type=RNACleavageOperation):
    original = request()
    selection = original.steps[0].operation.input
    frame_id = original.sources[0].molecule.space.id
    products = (
        ProcessingProduct(
            "product_A", CoordinatePath(frame_id, (IndexSpan(0, 2),), "+")
        ),
        ProcessingProduct(
            "product_B", CoordinatePath(frame_id, (IndexSpan(2, 4),), "+")
        ),
    )
    operation = operation_type(selection, products)
    return replace(
        original,
        steps=(
            replace(
                original.steps[0],
                operation=operation,
                ports=(port(), port("product_B")),
            ),
        ),
        output_members=(output(), output("output_B", "product_B")),
        requirements=(member(), member("required_B", "output_B", "control")),
    )


class CircuitConstructionIRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = request()

    def test_all_records_roundtrip_with_strict_versioned_fields(self):
        req = self.fixture
        selection = req.steps[0].operation.input
        records = (
            *req.sources,
            selection.value,
            selection,
            *req.steps[0].ports,
            req.steps[0].operation,
            ConcatenateOperation((selection, selection)),
            OrientationOperation(selection, "reverse_complement"),
            TranscriptionOperation(selection),
            *req.steps,
            *req.output_members,
            *req.requirements[0].roles,
            *req.requirements,
            req,
        )
        for record in records:
            with self.subTest(record=type(record).__name__):
                rebuilt = type(record).from_json(record.to_json())
                self.assertEqual(rebuilt, record)
                self.assertEqual(rebuilt.fingerprint, record.fingerprint)
                for edit in ("extra", "missing", "version"):
                    data = record.to_dict()
                    if edit == "extra":
                        data["unrecognized"] = None
                    elif edit == "missing":
                        del data[next(key for key in data if key != "schema_version")]
                    else:
                        data["schema_version"] += ".unsupported"
                    with self.assertRaises(SerializationError):
                        type(record).from_dict(data)

    def test_output_metadata_cannot_supply_expected_sequence_or_length(self):
        for record in (self.fixture.output_members[0], self.fixture.steps[0].ports[0]):
            for field in ("sequence", "length", "expected_sequence", "fingerprint"):
                with self.subTest(record=type(record).__name__, field=field):
                    data = record.to_dict()
                    data[field] = "ACGU"
                    with self.assertRaises(SerializationError):
                        type(record).from_dict(data)

    def test_operation_dispatch_is_explicit_and_limited(self):
        original = self.fixture.steps[0]
        selection = original.operation.input
        for operation in (
            SliceOperation(selection),
            ConcatenateOperation((selection, selection)),
            OrientationOperation(selection, "reverse"),
            TranscriptionOperation(selection),
        ):
            updated = replace(original, operation=operation)
            self.assertIsInstance(
                TransformStep.from_json(updated.to_json()).operation, type(operation)
            )
        data = original.to_dict()
        data["operation"]["schema_version"] = (
            "biocompiler.construction_unknown_transform.v0.1"
        )
        with self.assertRaisesRegex(
            SerializationError, "Unsupported construction operation"
        ):
            TransformStep.from_dict(data)
        with self.assertRaises(SerializationError):
            TranscriptionOperation(selection, "infer_template_strand")
        with self.assertRaises(SerializationError):
            OrientationOperation(selection, "infer")

    def test_frozen_record_snapshots_and_operation_order(self):
        req = self.fixture
        selections = [
            ValueSelection(ValueRef("root", "source_A")),
            ValueSelection(ValueRef("root", "source_B")),
        ]
        operation = ConcatenateOperation(selections)
        selections.reverse()
        self.assertEqual(
            [item.value.id for item in operation.inputs], ["source_A", "source_B"]
        )
        self.assertEqual(operation_selections(operation), operation.inputs)
        self.assertNotEqual(
            operation.fingerprint, ConcatenateOperation(selections).fingerprint
        )
        with self.assertRaises(FrozenInstanceError):
            req.mode = "diagnostic"
        sources = [root("source_B"), *req.sources]
        rebuilt = replace(req, sources=sources)
        sources.clear()
        self.assertEqual(
            [item.id for item in rebuilt.sources], ["source_A", "source_B"]
        )
        self.assertEqual(
            rebuilt.fingerprint,
            replace(req, sources=tuple(reversed(rebuilt.sources))).fingerprint,
        )

    def test_full_source_request_is_retained_and_changes_identity(self):
        req = self.fixture
        parsed = CircuitConstructionRequest.from_json(req.to_json())
        self.assertEqual(parsed.circuit, req.circuit)
        self.assertEqual(
            parsed.circuit.profile.source_request, req.circuit.profile.source_request
        )
        requirement = req.circuit.requirements[0]
        first, second = requirement.behavior.response.inputs
        circuit = replace(
            req.circuit,
            requirements=(
                replace(
                    requirement,
                    behavior=replace(requirement.behavior, response=first | second),
                ),
            ),
        )
        self.assertNotEqual(replace(req, circuit=circuit).fingerprint, req.fingerprint)

    def test_ordered_dag_chain_and_forward_reference_rejection(self):
        req = self.fixture
        second = step("step_B", "product_A", "product", "product_B")
        chained = replace(
            req,
            steps=(*req.steps, second),
            output_members=(
                replace(req.output_members[0], value=ValueRef("product", "product_B")),
            ),
        )
        self.assertEqual(
            CircuitConstructionRequest.from_dict(chained.to_dict()), chained
        )
        with self.assertRaisesRegex(SerializationError, "forward"):
            replace(chained, steps=tuple(reversed(chained.steps)))
        for reference in (
            ValueRef("product", "source_A"),
            ValueRef("product", "product_A"),
            ValueRef("root", "missing"),
        ):
            with self.subTest(reference=reference):
                invalid = replace(
                    req.steps[0], operation=SliceOperation(ValueSelection(reference))
                )
                with self.assertRaisesRegex(SerializationError, "reference"):
                    replace(req, steps=(invalid,))

    def test_executable_steps_must_contribute_to_output(self):
        req = self.fixture
        orphan = step("unused", product_id="unused_product")
        for mode in ("strict", "diagnostic"):
            with self.assertRaisesRegex(SerializationError, "contribute"):
                replace(req, steps=(*req.steps, orphan), mode=mode)
        # Extra supplied authority remains inspectable even when no operation uses it.
        self.assertEqual(
            len(replace(req, sources=(*req.sources, root("unused_source"))).sources), 2
        )

    def test_direct_root_output_needs_no_executable_step(self):
        req = self.fixture
        direct = replace(
            req,
            steps=(),
            output_members=(
                replace(req.output_members[0], value=ValueRef("root", "source_A")),
            ),
        )
        self.assertEqual(CircuitConstructionRequest.from_dict(direct.to_dict()), direct)

    def test_duplicate_value_and_step_ids_rejected(self):
        req = self.fixture
        with self.assertRaisesRegex(SerializationError, "globally unique"):
            replace(
                req,
                steps=(
                    replace(
                        req.steps[0],
                        ports=(replace(req.steps[0].ports[0], id="source_A"),),
                    ),
                ),
            )
        with self.assertRaisesRegex(SerializationError, "Duplicate construction step"):
            replace(req, steps=(*req.steps, req.steps[0]))
        duplicate_product = step("step_B", product_id="product_A")
        with self.assertRaisesRegex(SerializationError, "globally unique"):
            replace(req, steps=(*req.steps, duplicate_product))

    def test_root_and_ancestral_frames_are_reserved(self):
        req = self.fixture
        source = req.sources[0]
        other = replace(root("source_B"), molecule=source.molecule)
        with self.assertRaisesRegex(SerializationError, "distinct destination"):
            replace(req, sources=(*req.sources, other))
        frame_ids = (
            source.molecule.space.id,
            source.molecule.assembly[0].source_space.id,
        )
        for frame_id in frame_ids:
            with self.assertRaisesRegex(SerializationError, "uniquely reserved"):
                replace(
                    req,
                    steps=(
                        replace(
                            req.steps[0],
                            ports=(replace(req.steps[0].ports[0], space_id=frame_id),),
                        ),
                    ),
                )
            with self.assertRaisesRegex(SerializationError, "uniquely reserved"):
                replace(
                    req,
                    output_members=(replace(req.output_members[0], space_id=frame_id),),
                )

    def test_product_and_output_frames_are_reserved(self):
        req = self.fixture
        with self.assertRaisesRegex(SerializationError, "uniquely reserved"):
            replace(
                req,
                output_members=(
                    replace(
                        req.output_members[0], space_id=req.steps[0].ports[0].space_id
                    ),
                ),
            )
        duplicate = replace(output("output_B"), space_id=req.output_members[0].space_id)
        with self.assertRaisesRegex(SerializationError, "uniquely reserved"):
            replace(
                req,
                output_members=(*req.output_members, duplicate),
                requirements=(*req.requirements, member("required_B", "output_B")),
            )

    def test_conflicting_ancestral_frame_authority_rejected(self):
        req = self.fixture
        second = root("source_B")
        origin = second.molecule.assembly[0]
        identity = req.sources[0].molecule.assembly[0].source_space.id
        conflicting = replace(origin.source_space, id=identity, length=5)
        origin = replace(
            origin,
            source_space=conflicting,
            source_path=replace(origin.source_path, space_id=identity),
        )
        second = replace(second, molecule=replace(second.molecule, assembly=(origin,)))
        with self.assertRaisesRegex(
            SerializationError, "Conflicting source coordinate"
        ):
            replace(req, sources=(*req.sources, second))

    def test_root_path_bounds_checked_product_bounds_deferred(self):
        req = self.fixture
        selection = req.steps[0].operation.input
        frame_id = req.sources[0].molecule.space.id
        for coordinate in (
            CoordinatePath("unrelated", (IndexSpan(0, 1),), "+"),
            CoordinatePath(frame_id, (IndexSpan(0, 5),), "+"),
        ):
            invalid = replace(
                req.steps[0],
                operation=SliceOperation(replace(selection, path=coordinate)),
            )
            with self.assertRaises(SerializationError):
                replace(req, steps=(invalid,))
        second = step("step_B", "product_A", "product", "product_B")
        second = replace(
            second,
            operation=SliceOperation(
                ValueSelection(
                    ValueRef("product", "product_A"),
                    CoordinatePath("product_A.frame", (IndexSpan(0, 5),), "+"),
                )
            ),
        )
        # Parsing records the request; independent reconstruction must decide bounds.
        deferred = replace(
            req,
            steps=(*req.steps, second),
            output_members=(
                replace(req.output_members[0], value=ValueRef("product", "product_B")),
            ),
        )
        self.assertEqual(deferred.steps[1].operation.input.path.length, 5)

    def test_all_output_members_need_explicit_disposition(self):
        req = self.fixture
        with self.assertRaisesRegex(SerializationError, "absent output"):
            replace(
                req, requirements=(replace(req.requirements[0], member_id="missing"),)
            )
        with self.assertRaisesRegex(SerializationError, "Every output"):
            replace(req, output_members=(*req.output_members, output("output_B")))
        with self.assertRaisesRegex(SerializationError, "explicit payload"):
            replace(req, requirements=(member(category="control"),))
        shared = replace(
            req,
            requirements=(
                *req.requirements,
                member("also_control", category="control"),
            ),
        )
        self.assertEqual(len(shared.requirements), 2)
        self.assertEqual(len(shared.output_members), 1)

    def test_role_identity_purpose_and_compartment_are_preserved(self):
        req = self.fixture
        duplicate = replace(member("also_payload"), roles=req.requirements[0].roles)
        with self.assertRaisesRegex(SerializationError, "globally unique"):
            replace(req, requirements=(*req.requirements, duplicate))
        with self.assertRaisesRegex(SerializationError, "purpose disagree"):
            replace(
                req.requirements[0],
                roles=(replace(req.requirements[0].roles[0], purpose="helper"),),
            )
        with self.assertRaisesRegex(SerializationError, "target compartments"):
            replace(
                req,
                requirements=(
                    replace(
                        req.requirements[0],
                        roles=(
                            replace(
                                req.requirements[0].roles[0],
                                compartment="undeclared_compartment",
                            ),
                        ),
                    ),
                ),
            )
        with self.assertRaisesRegex(SerializationError, "physical compartment"):
            replace(req.requirements[0].roles[0], compartment="abstract")

    def test_external_provider_requires_exact_existing_authority(self):
        req = self.fixture
        provider = CircuitProviderRequirement(
            "fixture_provider",
            ObservationEntity("software_fixture", "provider", "1", "unknown"),
            "host",
            "cytoplasm",
            "fixture_group",
        )
        requirement = req.circuit.requirements[0]
        circuit = replace(
            req.circuit,
            requirements=(
                replace(
                    requirement,
                    behavior=replace(requirement.behavior, dependencies=(provider,)),
                ),
            ),
        )
        external = MemberRequirement(
            "required_provider",
            "host_provider",
            None,
            provider.id,
            provider.fingerprint,
            (
                RoleDeclaration(
                    "provider_role", "provider", "host_provider", "cytoplasm"
                ),
            ),
        )
        valid = replace(
            req, circuit=circuit, requirements=(*req.requirements, external)
        )
        self.assertEqual(CircuitConstructionRequest.from_json(valid.to_json()), valid)
        for changed in (
            replace(external, external_id="missing"),
            replace(external, external_fingerprint="0" * 64),
        ):
            with self.assertRaisesRegex(
                SerializationError, "original provider identity"
            ):
                replace(valid, requirements=(*req.requirements, changed))
        with self.assertRaisesRegex(SerializationError, "original provider identity"):
            replace(req, requirements=(*req.requirements, external))
        misclassified = replace(
            external,
            category="experimental_input",
            roles=(replace(external.roles[0], purpose="external_input"),),
        )
        with self.assertRaisesRegex(SerializationError, "original provider kind"):
            replace(valid, requirements=(*req.requirements, misclassified))
        misplaced = replace(
            external, roles=(replace(external.roles[0], compartment="nucleus"),)
        )
        with self.assertRaisesRegex(
            SerializationError, "original provider compartment"
        ):
            replace(valid, requirements=(*req.requirements, misplaced))
        control = replace(
            external,
            category="control",
            roles=(replace(external.roles[0], purpose="assay_control"),),
        )
        retained = replace(valid, requirements=(*req.requirements, control))
        self.assertEqual(
            retained.circuit.requirements[0].behavior.dependencies[0].availability,
            "unestablished",
        )

    def test_member_cannot_mix_external_and_materialized_or_omit_subject(self):
        requirement = self.fixture.requirements[0]
        with self.assertRaises(SerializationError):
            replace(requirement, external_id="provider", external_fingerprint="a" * 64)
        with self.assertRaises(SerializationError):
            replace(requirement, member_id=None)
        for category in ("payload", "delivered_helper", "encoded_product"):
            with self.subTest(category=category):
                original = member(category=category)
                with self.assertRaisesRegex(SerializationError, "materialized"):
                    replace(
                        original,
                        member_id=None,
                        external_id="provider",
                        external_fingerprint="a" * 64,
                    )

    def test_transition_dispositions_must_name_direct_operation_inputs(self):
        original = self.fixture.steps[0]
        product = original.ports[0]
        provenance = fixture_provenance("transition")
        chemistry = ChemistryTransition(
            "explicit_output",
            self.fixture.sources[0].molecule.chemistry,
            (ChemistryDisposition("unbound", "cap", "not_carried", (), provenance),),
            provenance,
        )
        feature = FeatureTransition(
            (
                FeatureDisposition(
                    "unbound", "annotation", "not_carried", (), provenance
                ),
            ),
            (),
            provenance,
        )
        for changed in (
            replace(product, chemistry_transition=chemistry),
            replace(product, feature_transition=feature),
        ):
            with self.assertRaisesRegex(SerializationError, "actual operation input"):
                replace(original, ports=(changed,))

    def test_bounded_arrays_reject_before_decoding_children(self):
        data = self.fixture.to_dict()
        data["sources"] = [None] * (MAX_SOURCES + 1)
        with self.assertRaisesRegex(SerializationError, "record array"):
            CircuitConstructionRequest.from_dict(data)
        data = ConcatenateOperation((self.fixture.steps[0].operation.input,)).to_dict()
        data["inputs"] = [None] * (MAX_SELECTIONS + 1)
        with self.assertRaisesRegex(SerializationError, "record array"):
            ConcatenateOperation.from_dict(data)
        with self.assertRaises(SerializationError):
            replace(
                self.fixture.steps[0],
                assumptions=tuple(str(index) for index in range(MAX_ASSUMPTIONS + 1)),
            )
        with self.assertRaises(SerializationError):
            replace(self.fixture.steps[0], ports=(port(), port("second")))

    def test_aggregate_source_limit_applies_to_direct_and_imported_requests(self):
        with patch("biocompiler.ir.circuit_construction.MAX_TOTAL_SOURCE_RESIDUES", 3):
            with self.assertRaisesRegex(SerializationError, "Total supplied source"):
                replace(self.fixture)
            with self.assertRaisesRegex(SerializationError, "Total supplied source"):
                CircuitConstructionRequest.from_dict(self.fixture.to_dict())

    def test_hostile_imports_cycles_depth_bytes_and_duplicate_keys(self):
        data = self.fixture.to_dict()
        data["unexpected"] = data
        with self.assertRaisesRegex(SerializationError, "Cyclic"):
            CircuitConstructionRequest.from_dict(data)
        nested = None
        for _ in range(100):
            nested = [nested]
        data = self.fixture.to_dict()
        data["unexpected"] = nested
        with self.assertRaisesRegex(SerializationError, "nesting"):
            CircuitConstructionRequest.from_dict(data)
        with self.assertRaisesRegex(SerializationError, "byte limit"):
            CircuitConstructionRequest.from_json(" " * 4_000_001)
        text = self.fixture.to_json()
        text = text.replace(
            '"mode": "strict"', '"mode": "strict", "mode": "diagnostic"'
        )
        with self.assertRaisesRegex(SerializationError, "Duplicate JSON key"):
            CircuitConstructionRequest.from_json(text)
        with self.assertRaises(SerializationError):
            ValueRef.from_json(
                '{"schema_version":"biocompiler.construction_value_ref.v0.1","kind":"root","id":NaN}'
            )

    def test_identifier_headroom_is_utf8_bounded(self):
        req = self.fixture
        self.assertEqual(replace(req, id="x" * 4080).id, "x" * 4080)
        self.assertEqual(replace(req.output_members[0], id="x" * 4080).id, "x" * 4080)
        for invalid in ("x" * 4081, "é" * 2041):
            with self.assertRaises(SerializationError):
                replace(req, id=invalid)
            with self.assertRaises(SerializationError):
                replace(req.output_members[0], id=invalid)

    def test_assumptions_canonical_and_duplicate_assumptions_rejected(self):
        original = self.fixture.steps[0]
        updated = replace(original, assumptions=["second", "first"])
        self.assertEqual(updated.assumptions, ("first", "second"))
        with self.assertRaisesRegex(
            SerializationError, "Duplicate construction assumptions"
        ):
            replace(original, assumptions=("same", "same"))

    def test_direct_construction_types_and_modes_are_strict(self):
        for changed in (
            {"mode": True},
            {"mode": "implicit"},
            {"steps": [None]},
            {"sources": []},
            {"output_members": []},
            {"requirements": []},
            {"circuit": self.fixture.circuit.to_dict()},
        ):
            with self.subTest(changed=tuple(changed)):
                with self.assertRaises(SerializationError):
                    replace(self.fixture, **changed)
        for changed in ({"kind": True}, {"kind": "step"}, {"id": 1}):
            with self.assertRaises(SerializationError):
                replace(self.fixture.steps[0].operation.input.value, **changed)
        self.assertEqual(json.loads(self.fixture.to_json())["mode"], "strict")


class CircuitProcessingIRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = processing_request()

    def test_distinct_processing_schemas_and_strict_roundtrips(self):
        original = self.fixture.steps[0].operation
        records = [original.products[0]]
        versions = set()
        for operation_type in (
            RNACleavageOperation,
            RNASplicingOperation,
            ProteinCleavageOperation,
            ProteinSplicingOperation,
        ):
            operation = operation_type(original.input, original.products)
            records.append(operation)
            versions.add(operation.schema_version)
            # Type/nominal declarations remain distinct; executor checks alphabets.
            transformed = replace(self.fixture.steps[0], operation=operation)
            self.assertIsInstance(
                TransformStep.from_json(transformed.to_json()).operation, operation_type
            )
            self.assertEqual(operation_selections(operation), (original.input,))
        self.assertEqual(len(versions), 4)
        records.append(CircularizationOperation(original.input, 0))
        for record in records:
            with self.subTest(record=type(record).__name__):
                self.assertEqual(type(record).from_json(record.to_json()), record)
                data = record.to_dict()
                data["expected_sequence"] = "ACGU"
                with self.assertRaises(SerializationError):
                    type(record).from_dict(data)
                data = record.to_dict()
                del data[next(key for key in data if key != "schema_version")]
                with self.assertRaises(SerializationError):
                    type(record).from_dict(data)
                data = record.to_dict()
                data["schema_version"] += ".unsupported"
                with self.assertRaises(SerializationError):
                    type(record).from_dict(data)

    def test_processing_and_circle_require_explicit_whole_input(self):
        original = self.fixture.steps[0].operation
        full_path = CoordinatePath(
            self.fixture.sources[0].molecule.space.id, (IndexSpan(0, 4),), "+"
        )
        selected = replace(original.input, path=full_path)
        for operation_type in (
            RNACleavageOperation,
            RNASplicingOperation,
            ProteinCleavageOperation,
            ProteinSplicingOperation,
        ):
            with self.assertRaisesRegex(SerializationError, "whole input"):
                operation_type(selected, original.products)
            with self.assertRaises(SerializationError):
                operation_type(original.input.to_dict(), original.products)
        with self.assertRaisesRegex(SerializationError, "whole input"):
            CircularizationOperation(selected, 0)

    def test_recipe_inventory_canonicalizes_but_path_order_is_exact(self):
        original = self.fixture.steps[0].operation
        recipe = list(reversed(original.products))
        parsed = RNASplicingOperation(original.input, recipe)
        recipe.clear()
        self.assertEqual(
            tuple(product.port_id for product in parsed.products),
            ("product_A", "product_B"),
        )
        frame = original.products[0].path.space_id
        path = CoordinatePath(frame, (IndexSpan(3, 4), IndexSpan(0, 2)), "+")
        reordered = replace(parsed, products=(ProcessingProduct("reordered", path),))
        self.assertEqual(
            reordered.products[0].path.spans, (IndexSpan(3, 4), IndexSpan(0, 2))
        )
        natural = replace(
            reordered,
            products=(
                ProcessingProduct(
                    "reordered", replace(path, spans=tuple(reversed(path.spans)))
                ),
            ),
        )
        self.assertNotEqual(reordered.fingerprint, natural.fingerprint)

    def test_cleavage_contiguous_forward_splicing_disjoint_forward(self):
        original = self.fixture.steps[0].operation
        first = original.products[0]
        negative = replace(first, path=replace(first.path, strand="-"))
        for operation_type in (
            RNACleavageOperation,
            RNASplicingOperation,
            ProteinCleavageOperation,
            ProteinSplicingOperation,
        ):
            with self.assertRaisesRegex(SerializationError, "forward traversal"):
                operation_type(original.input, (negative,))
        multispan = replace(
            first, path=replace(first.path, spans=(IndexSpan(0, 1), IndexSpan(2, 4)))
        )
        for operation_type in (RNACleavageOperation, ProteinCleavageOperation):
            with self.assertRaisesRegex(SerializationError, "contiguous"):
                operation_type(original.input, (multispan,))
        for operation_type in (RNASplicingOperation, ProteinSplicingOperation):
            self.assertEqual(
                operation_type(original.input, (multispan,)).products, (multispan,)
            )

    def test_recipe_port_ids_match_exact_step_inventory(self):
        original = self.fixture.steps[0]
        with self.assertRaisesRegex(SerializationError, "match exactly"):
            replace(original, ports=(original.ports[0],))
        with self.assertRaisesRegex(SerializationError, "match exactly"):
            replace(original, ports=(*original.ports, port("extra")))
        with self.assertRaisesRegex(
            SerializationError, "Duplicate processing products"
        ):
            replace(
                original.operation,
                products=(
                    original.operation.products[0],
                    original.operation.products[0],
                ),
            )
        renamed = replace(original.operation.products[0], port_id="unbound")
        with self.assertRaisesRegex(SerializationError, "match exactly"):
            replace(
                original,
                operation=replace(
                    original.operation,
                    products=(renamed, original.operation.products[1]),
                ),
            )

    def test_every_byproduct_port_must_reach_a_final_member(self):
        original = self.fixture
        with self.assertRaisesRegex(
            SerializationError, "Every executable product port"
        ):
            replace(
                original,
                output_members=(original.output_members[0],),
                requirements=(original.requirements[0],),
            )
        # Both products can reach one final member through an explicit next operation.
        selections = tuple(
            ValueSelection(ValueRef("product", product.id))
            for product in original.steps[0].ports
        )
        join = TransformStep(
            "rejoin",
            ConcatenateOperation(selections),
            (port("joined"),),
            (),
            fixture_provenance("rejoin"),
        )
        combined = replace(
            original,
            steps=(*original.steps, join),
            output_members=(output("output_A", "joined"),),
            requirements=(member(),),
        )
        self.assertEqual(
            CircuitConstructionRequest.from_json(combined.to_json()), combined
        )

    def test_recipe_paths_bind_input_frame(self):
        original = self.fixture
        operation = original.steps[0].operation
        wrong = replace(
            operation.products[0],
            path=replace(operation.products[0].path, space_id="unrelated_frame"),
        )
        with self.assertRaisesRegex(SerializationError, "bound input frame"):
            replace(
                original,
                steps=(
                    replace(
                        original.steps[0],
                        operation=replace(
                            operation, products=(wrong, operation.products[1])
                        ),
                    ),
                ),
            )

    def test_processing_product_bounds_and_partition_are_reconstruction_obligations(
        self,
    ):
        original = self.fixture
        operation = original.steps[0].operation
        # A parseable declaration is not a verified partition. Both overshoot and
        # cross-product overlaps must be evaluated against the actual input.
        overshoot = replace(
            operation.products[0],
            path=replace(operation.products[0].path, spans=(IndexSpan(0, 5),)),
        )
        unresolved = replace(
            original,
            steps=(
                replace(
                    original.steps[0],
                    operation=replace(
                        operation, products=(overshoot, operation.products[1])
                    ),
                ),
            ),
        )
        self.assertEqual(unresolved.steps[0].operation.products[0].path.length, 5)

    def test_processing_applies_to_reconstructed_product_frame(self):
        original = self.fixture
        initial = step("initial", product_id="whole_product")
        operation = original.steps[0].operation
        products = tuple(
            replace(product, path=replace(product.path, space_id="whole_product.frame"))
            for product in operation.products
        )
        operation = replace(
            operation,
            input=ValueSelection(ValueRef("product", "whole_product")),
            products=products,
        )
        chained = replace(
            original, steps=(initial, replace(original.steps[0], operation=operation))
        )
        self.assertEqual(
            CircuitConstructionRequest.from_dict(chained.to_dict()), chained
        )

    def test_processing_counts_are_bounded_before_child_decode(self):
        operation = self.fixture.steps[0].operation
        with self.assertRaises(SerializationError):
            replace(operation, products=())
        data = operation.to_dict()
        data["products"] = [None] * (MAX_PROCESSING_PRODUCTS + 1)
        with self.assertRaisesRegex(SerializationError, "record array"):
            RNACleavageOperation.from_dict(data)
        data = self.fixture.steps[0].to_dict()
        data["ports"] = [None] * (MAX_PROCESSING_PRODUCTS + 1)
        with self.assertRaisesRegex(SerializationError, "record array"):
            TransformStep.from_dict(data)

    def test_circularization_origin_is_explicit_exact_and_bounded(self):
        selection = self.fixture.steps[0].operation.input
        for origin in (0, 1, 1_000_000):
            operation = CircularizationOperation(selection, origin)
            self.assertEqual(
                CircularizationOperation.from_json(operation.to_json()).origin, origin
            )
            self.assertEqual(operation_selections(operation), (selection,))
        for origin in (None, True, False, 0.0, "0", -1, 1_000_001):
            with self.subTest(origin=origin):
                with self.assertRaises(SerializationError):
                    CircularizationOperation(selection, origin)
        self.assertNotEqual(
            CircularizationOperation(selection, 0).fingerprint,
            CircularizationOperation(selection, 4).fingerprint,
        )

    def test_circularization_has_one_port_and_no_implicit_output_topology(self):
        original = request()
        operation = CircularizationOperation(original.steps[0].operation.input, 1)
        transformed = replace(
            original.steps[0],
            operation=operation,
            ports=(replace(original.steps[0].ports[0], topology="circular"),),
        )
        parsed = replace(original, steps=(transformed,))
        self.assertEqual(CircuitConstructionRequest.from_json(parsed.to_json()), parsed)
        with self.assertRaisesRegex(SerializationError, "exactly one product"):
            replace(transformed, ports=(*transformed.ports, port("second")))
        # Topology mismatch is retained for independent execution diagnostics.
        unresolved = replace(
            transformed, ports=(replace(transformed.ports[0], topology="linear"),)
        )
        self.assertEqual(unresolved.ports[0].topology, "linear")


class CircuitRecodingOperationIRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = request()
        cls.policy = TranslationPolicy("ordinary_cds")
        cls.conditional_policy = TranslationPolicy(
            "conditional_cds",
            recodings=(CodonRecoding(0, "ACG", "U", "recoding_declared"),),
        )

    def selections(self):
        whole = self.fixture.steps[0].operation.input
        frame = self.fixture.sources[0].molecule.space.id
        return (
            whole,
            replace(whole, path=CoordinatePath(frame, (IndexSpan(0, 3),), "+")),
            replace(whole, path=CoordinatePath(frame, (IndexSpan(1, 4),), "+")),
        )

    def conditional(self, *, policy=None):
        whole, _, _ = self.selections()
        return ConditionalTranslationOperation(
            (
                TranslationBranch(
                    "on",
                    "on_declared",
                    whole,
                    self.policy if policy is None else policy,
                    "product_A",
                ),
                TranslationBranch("off", "off_declared", whole, None, None),
            )
        )

    def test_new_schemas_roundtrip_and_reject_unknown_or_missing_fields(self):
        whole, first, second = self.selections()
        product = TranslationProduct("product_A", first, self.policy)
        peptide = PeptideProduct("product_A", IndexSpan(0, 1))
        records = (
            BaseEditingOperation(whole, (CanonicalBaseEdit(0, "A", "G"),), ()),
            TranslationOperation(first, self.policy),
            product,
            MultiORFTranslationOperation(
                (product, TranslationProduct("product_B", second, self.policy))
            ),
            *self.conditional().branches,
            self.conditional(),
            peptide,
            RibosomalSkippingOperation(
                first, self.policy, (peptide,), "skipping_declared"
            ),
        )
        for record in records:
            with self.subTest(record=type(record).__name__):
                rebuilt = type(record).from_json(record.to_json())
                self.assertEqual(rebuilt, record)
                self.assertEqual(rebuilt.fingerprint, record.fingerprint)
                for field in ("expected_sequence", "assumed_valid", "length"):
                    data = record.to_dict()
                    data[field] = None
                    with self.assertRaises(SerializationError):
                        type(record).from_dict(data)
                data = record.to_dict()
                del data[next(key for key in data if key != "schema_version")]
                with self.assertRaises(SerializationError):
                    type(record).from_dict(data)
                data = record.to_dict()
                data["schema_version"] += ".unsupported"
                with self.assertRaises(SerializationError):
                    type(record).from_dict(data)

    def test_edit_operations_require_whole_input_and_actual_edit_inventory(self):
        whole, first, _ = self.selections()
        canonical = CanonicalBaseEdit(0, "A", "G")
        chemical = ChemicalBaseEdit(
            1, "C", None, ChemicalIdentity("software_fixture", "modified_C", "1")
        )
        operation = BaseEditingOperation(whole, (canonical,), (chemical,))
        self.assertEqual(operation_selections(operation), (whole,))
        with self.assertRaisesRegex(SerializationError, "whole input"):
            replace(operation, input=first)
        with self.assertRaisesRegex(SerializationError, "nonempty combined"):
            replace(operation, canonical_edits=(), chemical_edits=())
        with self.assertRaises(SerializationError):
            replace(operation, canonical_edits=None)
        with self.assertRaisesRegex(SerializationError, "Duplicate canonical_edits"):
            replace(
                operation,
                canonical_edits=(canonical, replace(canonical, replacement="U")),
            )
        with self.assertRaisesRegex(SerializationError, "Duplicate chemical_edits"):
            replace(operation, chemical_edits=(chemical, chemical))
        with self.assertRaisesRegex(SerializationError, "cannot overlap"):
            replace(operation, chemical_edits=(replace(chemical, position=0),))
        with patch("biocompiler.ir.circuit_construction.MAX_RECODINGS", 1):
            with self.assertRaisesRegex(SerializationError, "combined edit inventory"):
                replace(operation)

    def test_edit_positions_canonicalize_without_executing_preconditions(self):
        whole, _, _ = self.selections()
        edits = [CanonicalBaseEdit(3, "C", "G"), CanonicalBaseEdit(0, "U", "A")]
        operation = BaseEditingOperation(whole, edits, ())
        edits.clear()
        self.assertEqual(
            tuple(edit.position for edit in operation.canonical_edits), (0, 3)
        )
        # Exact spelling/preconditions are checked independently during execution.
        transformed = replace(self.fixture.steps[0], operation=operation)
        retained = replace(self.fixture, steps=(transformed,))
        self.assertEqual(retained.steps[0].operation.canonical_edits[0].expected, "U")

    def test_multi_orf_requires_same_value_and_explicit_individual_paths(self):
        whole, first, second = self.selections()
        first_product = TranslationProduct("product_A", first, self.policy)
        second_product = TranslationProduct("product_B", second, self.policy)
        operation = MultiORFTranslationOperation([second_product, first_product])
        self.assertEqual(operation_selections(operation), (first, second))
        self.assertEqual(operation.products[0].port_id, "product_A")
        # Overlapping ORF declarations are retained; no overlap prohibition is inferred.
        self.assertEqual(operation.products[0].input.path.spans[0].end, 3)
        self.assertEqual(operation.products[1].input.path.spans[0].start, 1)
        with self.assertRaisesRegex(SerializationError, "explicit individual ORF"):
            replace(operation, products=(replace(first_product, input=whole),))
        different = replace(second, value=ValueRef("root", "other_source"))
        with self.assertRaisesRegex(SerializationError, "same exact source"):
            replace(
                operation,
                products=(first_product, replace(second_product, input=different)),
            )
        with self.assertRaisesRegex(
            SerializationError, "Duplicate translation products"
        ):
            replace(operation, products=(first_product, first_product))

    def test_operation_selections_deduplicate_new_branches_not_concat_multiplicity(
        self,
    ):
        _, first, _ = self.selections()
        multi = MultiORFTranslationOperation(
            (
                TranslationProduct("first", first, self.policy),
                TranslationProduct("second", first, self.policy),
            )
        )
        self.assertEqual(operation_selections(multi), (first,))
        self.assertEqual(len(multi.products), 2)
        conditional = self.conditional()
        self.assertEqual(len(operation_selections(conditional)), 1)
        self.assertEqual(len(conditional.branches), 2)
        self.assertEqual(
            operation_selections(ConcatenateOperation((first, first))), (first, first)
        )

    def test_no_product_branch_pairing_and_unique_branch_authority(self):
        operation = self.conditional()
        no_product, producing = operation.branches
        self.assertEqual(no_product.id, "off")
        self.assertIsNone(no_product.policy)
        self.assertIsNone(no_product.port_id)
        with self.assertRaisesRegex(SerializationError, "both a policy"):
            replace(no_product, policy=self.policy)
        with self.assertRaisesRegex(SerializationError, "both a policy"):
            replace(no_product, port_id="product_B")
        with self.assertRaisesRegex(SerializationError, "at least one producing"):
            replace(operation, branches=(no_product,))
        with self.assertRaisesRegex(
            SerializationError, "Duplicate translation branches"
        ):
            replace(operation, branches=(producing, producing))
        with self.assertRaisesRegex(SerializationError, "conditions must be unique"):
            replace(
                operation,
                branches=(
                    no_product,
                    replace(producing, condition=no_product.condition),
                ),
            )
        duplicate_port = replace(producing, id="other", condition="other_condition")
        with self.assertRaisesRegex(
            SerializationError, "port identities must be unique"
        ):
            replace(operation, branches=(producing, duplicate_port))

    def test_branch_recoding_and_skipping_assumptions_bind_exact_strings(self):
        _, first, _ = self.selections()
        original = self.fixture.steps[0]
        conditional = self.conditional(policy=self.conditional_policy)
        skipping = RibosomalSkippingOperation(
            first,
            self.conditional_policy,
            (PeptideProduct("product_A", IndexSpan(0, 1)),),
            "skipping_declared",
        )
        cases = (
            (
                TranslationOperation(first, self.conditional_policy),
                ("recoding_declared",),
            ),
            (conditional, ("on_declared", "off_declared", "recoding_declared")),
            (skipping, ("skipping_declared", "recoding_declared")),
        )
        for operation, conditions in cases:
            with self.subTest(operation=type(operation).__name__):
                step_ = replace(original, operation=operation, assumptions=conditions)
                self.assertEqual(TransformStep.from_json(step_.to_json()), step_)
                for omitted in conditions:
                    with self.assertRaisesRegex(
                        SerializationError, "exact declared assumption"
                    ):
                        replace(
                            step_,
                            assumptions=tuple(
                                item for item in conditions if item != omitted
                            ),
                        )
                with self.assertRaisesRegex(
                    SerializationError, "exact declared assumption"
                ):
                    replace(
                        step_, assumptions=tuple(item.upper() for item in conditions)
                    )

    def test_conditional_no_product_input_stays_bound_and_validated(self):
        original = self.fixture
        operation = self.conditional()
        step_ = replace(
            original.steps[0],
            operation=operation,
            assumptions=("on_declared", "off_declared"),
        )
        valid = replace(original, steps=(step_,))
        self.assertEqual(CircuitConstructionRequest.from_json(valid.to_json()), valid)
        no_product, producing = operation.branches
        whole, first, _ = self.selections()
        bad_inputs = (
            replace(whole, value=ValueRef("root", "missing")),
            replace(first, path=replace(first.path, space_id="wrong_frame")),
            replace(first, path=replace(first.path, spans=(IndexSpan(0, 5),))),
        )
        for selection in bad_inputs:
            changed = replace(
                operation, branches=(replace(no_product, input=selection), producing)
            )
            with self.assertRaises(SerializationError):
                replace(original, steps=(replace(step_, operation=changed),))

    def test_conditional_branches_can_retain_separate_source_states(self):
        original = self.fixture
        operation = self.conditional()
        no_product, producing = operation.branches
        second = root("second_state")
        changed = replace(
            operation,
            branches=(
                replace(no_product, input=ValueSelection(ValueRef("root", second.id))),
                producing,
            ),
        )
        step_ = replace(
            original.steps[0],
            operation=changed,
            assumptions=("on_declared", "off_declared"),
        )
        valid = replace(original, sources=(*original.sources, second), steps=(step_,))
        self.assertEqual(
            {item.value.id for item in operation_selections(valid.steps[0].operation)},
            {"source_A", "second_state"},
        )

    def test_multi_and_branch_and_skipping_ports_match_exactly(self):
        _, first, second = self.selections()
        original = self.fixture.steps[0]
        multi = MultiORFTranslationOperation(
            (
                TranslationProduct("product_A", first, self.policy),
                TranslationProduct("product_B", second, self.policy),
            )
        )
        skipping = RibosomalSkippingOperation(
            first,
            self.policy,
            (
                PeptideProduct("product_A", IndexSpan(0, 1)),
                PeptideProduct("product_B", IndexSpan(1, 2)),
            ),
            "skipping_declared",
        )
        for operation in (multi, skipping):
            with self.assertRaisesRegex(SerializationError, "match exactly"):
                replace(
                    original, operation=operation, assumptions=("skipping_declared",)
                )
            valid = replace(
                original,
                operation=operation,
                ports=(port(), port("product_B")),
                assumptions=("skipping_declared",),
            )
            self.assertEqual(TransformStep.from_json(valid.to_json()), valid)
        with self.assertRaisesRegex(SerializationError, "match exactly"):
            replace(
                original,
                operation=self.conditional(),
                ports=(port(), port("product_B")),
                assumptions=("on_declared", "off_declared"),
            )

    def test_skipping_preserves_typed_residue_allocations_and_event_identity(self):
        _, first, _ = self.selections()
        operation = RibosomalSkippingOperation(
            first,
            self.policy,
            (
                PeptideProduct("second", IndexSpan(2, 5)),
                PeptideProduct("first", IndexSpan(0, 2)),
            ),
            "declared_event",
        )
        self.assertEqual(
            tuple(item.port_id for item in operation.products), ("first", "second")
        )
        self.assertEqual(
            tuple(item.residues.length for item in operation.products), (2, 3)
        )
        self.assertNotEqual(
            operation.fingerprint,
            replace(operation, event_id="different_event").fingerprint,
        )
        with self.assertRaises(SerializationError):
            replace(operation.products[0], residues={"start": 0, "end": 1})
        # Partition and translated length are checked later, without hidden loss.
        overlaps = replace(
            operation,
            products=(
                operation.products[0],
                replace(operation.products[1], residues=IndexSpan(1, 9)),
            ),
        )
        self.assertEqual(overlaps.products[1].residues.end, 9)

    def test_new_operation_array_bounds_precede_child_decoding(self):
        _, first, _ = self.selections()
        cases = (
            (
                MultiORFTranslationOperation(
                    (TranslationProduct("product_A", first, self.policy),)
                ),
                "products",
                MAX_TRANSLATION_PRODUCTS,
            ),
            (self.conditional(), "branches", MAX_TRANSLATION_BRANCHES),
            (
                RibosomalSkippingOperation(
                    first,
                    self.policy,
                    (PeptideProduct("product_A", IndexSpan(0, 1)),),
                    "event",
                ),
                "products",
                MAX_TRANSLATION_PRODUCTS,
            ),
        )
        for record, field, maximum in cases:
            data = record.to_dict()
            data[field] = [None] * (maximum + 1)
            with self.assertRaisesRegex(SerializationError, "record array"):
                type(record).from_dict(data)

    def test_new_operation_types_refuse_untyped_sources_and_policies(self):
        _, first, _ = self.selections()
        for bad in (None, self.policy.to_dict(), "ordinary_cds"):
            with self.assertRaises(SerializationError):
                TranslationOperation(first, bad)
        with self.assertRaises(SerializationError):
            TranslationOperation(first.to_dict(), self.policy)
        with self.assertRaises(SerializationError):
            TranslationBranch("off", "off_declared", first.to_dict(), None, None)


class CircuitComplexAmountIRTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = request()
        cls.provenance = fixture_provenance("complex_amount_declarations")

    def complex_plan(self):
        return ComplexMemberPlan(
            "complex_A",
            "rna_complex",
            (ComplexMemberConstituent("output_A", 2, self.provenance),),
            self.provenance,
        )

    def amount(
        self,
        identity="amount_A",
        subject="output_A",
        roles=("required_A.role",),
        quantity=1,
    ):
        return AmountDeclaration(
            identity,
            subject,
            "preparation_A",
            roles,
            quantity,
            "software_fixture_units",
            self.provenance,
        )

    def complex_request(self):
        return replace(
            self.fixture,
            complex_members=(self.complex_plan(),),
            requirements=(
                *self.fixture.requirements,
                member("complex_required", "complex_A", "control"),
            ),
        )

    def test_new_plan_schemas_strictly_roundtrip_without_generated_pins(self):
        complex_ = self.complex_plan()
        for record in (
            complex_.constituents[0],
            complex_,
            self.amount(),
            self.complex_request(),
        ):
            with self.subTest(record=type(record).__name__):
                rebuilt = type(record).from_json(record.to_json())
                self.assertEqual(rebuilt, record)
                self.assertEqual(rebuilt.fingerprint, record.fingerprint)
                data = record.to_dict()
                data["subject_fingerprint"] = "a" * 64
                with self.assertRaises(SerializationError):
                    type(record).from_dict(data)
                data = record.to_dict()
                del data[next(key for key in data if key != "schema_version")]
                with self.assertRaises(SerializationError):
                    type(record).from_dict(data)

    def test_new_request_fields_have_positional_compatible_defaults(self):
        self.assertEqual(self.fixture.complex_members, ())
        self.assertEqual(self.fixture.amounts, ())
        self.assertEqual(self.fixture.payload_structures, ())
        data = self.fixture.to_dict()
        self.assertEqual(data["complex_members"], [])
        self.assertEqual(data["amounts"], [])
        self.assertEqual(data["payload_structures"], [])
        for field in ("complex_members", "amounts", "payload_structures"):
            missing = dict(data)
            del missing[field]
            with self.assertRaises(SerializationError):
                CircuitConstructionRequest.from_dict(missing)

    def test_complex_stoichiometry_scalar_and_kind_rules(self):
        original = self.complex_plan()
        constituent = original.constituents[0]
        for count in (None, 1, 1_000_000):
            self.assertEqual(
                replace(constituent, stoichiometry=count).stoichiometry, count
            )
        for count in (False, True, 0, -1, 1.0, "2", 1_000_001):
            with self.assertRaises(SerializationError):
                replace(constituent, stoichiometry=count)
        with self.assertRaisesRegex(
            SerializationError, "at least two constituent copies"
        ):
            replace(original, constituents=(replace(constituent, stoichiometry=1),))
        self.assertIsNone(
            replace(original, constituents=(replace(constituent, stoichiometry=None),))
            .constituents[0]
            .stoichiometry
        )
        with self.assertRaises(SerializationError):
            replace(original, kind="implicit_assembly")
        with self.assertRaisesRegex(SerializationError, "two explicit single-copy"):
            replace(original, kind="dna_duplex")
        dna = replace(
            original,
            kind="dna_duplex",
            constituents=(
                replace(constituent, stoichiometry=1),
                replace(constituent, member_id="other_strand", stoichiometry=1),
            ),
        )
        self.assertEqual(len(dna.constituents), 2)

    def test_complex_constituents_bind_final_covalent_members_without_cycles(self):
        valid = self.complex_request()
        original = valid.complex_members[0]
        for identity in ("missing", "source_A", "product_A", "complex_A"):
            changed = replace(
                original,
                constituents=(replace(original.constituents[0], member_id=identity),),
            )
            with self.assertRaisesRegex(
                SerializationError, "final covalent output members"
            ):
                replace(valid, complex_members=(changed,))
        other = replace(
            original,
            id="complex_B",
            constituents=(replace(original.constituents[0], member_id="complex_A"),),
        )
        with self.assertRaisesRegex(
            SerializationError, "final covalent output members"
        ):
            replace(valid, complex_members=(*valid.complex_members, other))
        with self.assertRaisesRegex(SerializationError, "distinct identities"):
            replace(valid, complex_members=(replace(original, id="output_A"),))

    def test_every_complex_and_constituent_still_has_declared_member_role(self):
        valid = self.complex_request()
        self.assertEqual(CircuitConstructionRequest.from_dict(valid.to_dict()), valid)
        with self.assertRaisesRegex(
            SerializationError, "Every output member and complex"
        ):
            replace(valid, requirements=self.fixture.requirements)
        complex_payload = member("complex_payload", "complex_A")
        with self.assertRaisesRegex(
            SerializationError, "Every output member and complex"
        ):
            replace(valid, requirements=(complex_payload,))
        # A complex can be the payload while its covalent members carry other roles.
        repl = replace(
            valid, requirements=(member(category="encoded_product"), complex_payload)
        )
        self.assertEqual(
            {item.member_id for item in repl.requirements}, {"output_A", "complex_A"}
        )

    def test_amounts_bind_exact_covalent_or_complex_subject_and_roles(self):
        original = self.complex_request()
        covalent = self.amount()
        complex_ = self.amount(
            "complex_amount", "complex_A", ("complex_required.role",)
        )
        valid = replace(original, amounts=(complex_, covalent))
        self.assertEqual(CircuitConstructionRequest.from_json(valid.to_json()), valid)
        for bad in (
            replace(covalent, subject_id="missing"),
            replace(covalent, role_instance_ids=("missing_role",)),
            replace(covalent, role_instance_ids=("complex_required.role",)),
            replace(complex_, role_instance_ids=("required_A.role",)),
        ):
            with self.assertRaises(SerializationError):
                replace(original, amounts=(bad,))

    def test_amounts_never_derive_from_role_counts_or_stoichiometry(self):
        original = self.complex_request()
        additional = member("another_role", "complex_A", "delivered_helper")
        amount = self.amount(
            "unknown_complex_amount",
            "complex_A",
            ("complex_required.role", "another_role.role"),
            quantity=None,
        )
        valid = replace(
            original,
            requirements=(*original.requirements, additional),
            amounts=(amount,),
        )
        self.assertIsNone(valid.amounts[0].quantity)
        self.assertEqual(valid.complex_members[0].constituents[0].stoichiometry, 2)
        self.assertEqual(len(valid.amounts[0].role_instance_ids), 2)
        self.assertEqual(
            replace(valid, amounts=(replace(amount, quantity=0),)).amounts[0].quantity,
            0,
        )

    def test_amount_scalar_validation_matches_declared_experimental_amounts(self):
        original = self.amount()
        for quantity in (None, 0, 1, 1.5, (1 << 1023)):
            self.assertEqual(replace(original, quantity=quantity).quantity, quantity)
        for quantity in (
            True,
            False,
            -1,
            -0.1,
            float("nan"),
            float("inf"),
            float("-inf"),
            "1",
            1 << 1024,
        ):
            with self.subTest(quantity=type(quantity).__name__):
                with self.assertRaises(SerializationError):
                    replace(original, quantity=quantity)
        for unit in (None, "", " mass", "unit\n"):
            with self.assertRaises(SerializationError):
                replace(original, unit=unit)
        with self.assertRaisesRegex(SerializationError, "Duplicate amount role"):
            replace(original, role_instance_ids=("same", "same"))

    def test_same_subject_preparation_requires_one_shared_amount(self):
        first = self.amount()
        with self.assertRaisesRegex(SerializationError, "declared once"):
            replace(self.fixture, amounts=(first, replace(first, id="duplicate")))
        different_preparation = replace(
            first, id="another_preparation", preparation_id="preparation_B"
        )
        valid = replace(self.fixture, amounts=(first, different_preparation))
        self.assertEqual(len(valid.amounts), 2)

    def test_nominal_species_aliases_remain_a_constructed_record_check(self):
        # Distinct final declarations may reconstruct the same nominal species;
        # detecting that requires generated records, not authoring guesses.
        original = self.fixture
        alias = output("output_alias")
        valid = replace(
            original,
            output_members=(*original.output_members, alias),
            requirements=(
                *original.requirements,
                member("alias_role", alias.id, "control"),
            ),
            amounts=(
                self.amount(),
                self.amount("alias_amount", alias.id, ("alias_role.role",)),
            ),
        )
        self.assertEqual(len(valid.amounts), 2)

    def test_complex_and_amount_inventories_are_bounded_before_decode(self):
        data = self.fixture.to_dict()
        for field, maximum in (
            ("complex_members", MAX_COMPLEX_MEMBERS),
            ("amounts", MAX_AMOUNT_DECLARATIONS),
        ):
            bad = dict(data)
            bad[field] = [None] * (maximum + 1)
            with self.assertRaisesRegex(SerializationError, "record array"):
                CircuitConstructionRequest.from_dict(bad)
        duplicate = self.complex_plan()
        with self.assertRaisesRegex(
            SerializationError, "Duplicate complex member constituents"
        ):
            replace(
                duplicate,
                constituents=(duplicate.constituents[0], duplicate.constituents[0]),
            )

    def test_payload_contract_inventory_is_typed_frozen_and_canonical(self):
        first = PayloadStructureContract(
            "output_A",
            "delivered_rna",
            "linear",
            (RequiredPayloadRegion("declared_region", "software_fixture_region"),),
            self.provenance,
        )
        second = replace(first, member_id="output_B")
        inventory = [second, first]
        retained = replace(self.fixture, payload_structures=inventory)
        inventory.clear()
        self.assertEqual(
            tuple(item.member_id for item in retained.payload_structures),
            ("output_A", "output_B"),
        )
        self.assertEqual(
            CircuitConstructionRequest.from_json(retained.to_json()), retained
        )
        self.assertNotEqual(retained.fingerprint, self.fixture.fingerprint)
        changed = replace(
            first,
            regions=(
                RequiredPayloadRegion("different_region", "software_fixture_region"),
            ),
        )
        self.assertNotEqual(
            replace(self.fixture, payload_structures=(changed,)).fingerprint,
            replace(self.fixture, payload_structures=(first,)).fingerprint,
        )

    def test_payload_inventory_uniqueness_and_bounds_precede_semantic_check(self):
        contract = PayloadStructureContract(
            "output_A",
            "delivered_rna",
            "linear",
            (RequiredPayloadRegion("declared_region", "software_fixture_region"),),
            self.provenance,
        )
        with self.assertRaisesRegex(SerializationError, "Duplicate payload structure"):
            replace(self.fixture, payload_structures=(contract, contract))
        with self.assertRaises(SerializationError):
            replace(self.fixture, payload_structures=(contract.to_dict(),))
        data = self.fixture.to_dict()
        data["payload_structures"] = [None] * (MAX_PAYLOAD_CONTRACTS + 1)
        with self.assertRaisesRegex(SerializationError, "record array"):
            CircuitConstructionRequest.from_dict(data)
        # Request parsing preserves incomplete/wrong-subject declarations so the
        # independent checker can report exact payload-inventory correspondence.
        unresolved = replace(
            self.fixture,
            payload_structures=(replace(contract, member_id="unbound_member"),),
        )
        self.assertEqual(unresolved.payload_structures[0].member_id, "unbound_member")


if __name__ == "__main__":
    unittest.main()
