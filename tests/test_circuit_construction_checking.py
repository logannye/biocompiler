"""Independent construction checks against tiny, literal software fixtures."""

from dataclasses import replace
import unittest
from unittest.mock import patch

from biocompiler.backends.circuit_construction import construct_circuit_candidate
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_construction import (
    AmountDeclaration,
    BaseEditingOperation,
    CircuitConstructionRequest,
    CircularizationOperation,
    ComplexMemberConstituent,
    ComplexMemberPlan,
    ConcatenateOperation,
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
    TranslationBranch,
    TranslationOperation,
    TranslationProduct,
    TransformStep,
    ValueRef,
    ValueSelection,
)
from biocompiler.ir.circuit_recoding import (
    CanonicalBaseEdit,
    ChemicalBaseEdit,
    CodonRecoding,
    TranslationPolicy,
)
from biocompiler.ir.circuit_transitions import (
    CHEMISTRY_FACETS,
    ChemistryDisposition,
    ChemistryTransition,
    FeatureDisposition,
    FeatureTransition,
)
from biocompiler.ir.circuit_molecules import MoleculeFeature
from biocompiler.ir.circuit_payloads import (
    PayloadStructureContract,
    RequiredPayloadRegion,
)
from biocompiler.ir.molecule_chemistry import (
    BaseModification,
    ChemicalIdentity,
    ChemistryClaim,
)
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan
from biocompiler.verification.circuit_construction import (
    CircuitConstructionAssessment,
    check_circuit_construction,
    reconstruct_for_check,
    verify_circuit_construction_assessment,
)
from biocompiler.verification.evidence import CheckOutcome
from examples.circuit_intent import make_circuit_requests
from examples.circuit_molecules import (
    fixture_chemistry,
    fixture_provenance,
    make_molecule,
)


def payload_contract(member_id="payload", form="delivered_rna", topology="linear"):
    return PayloadStructureContract(
        member_id,
        form,
        topology,
        (RequiredPayloadRegion("payload_region", "nominal_test_region"),),
        fixture_provenance("required-region-contract"),
    )


def payload_source(source):
    feature = MoleculeFeature(
        "payload_region",
        "nominal_test_region",
        CoordinatePath(source.space.id, (IndexSpan(0, 1),), "+"),
        fixture_provenance("declared-region"),
    )
    return replace(source, features=source.features + (feature,))


def named_port(port, identity):
    space_id = identity + ".space"
    features = tuple(
        replace(
            feature,
            path=None
            if feature.path is None
            else replace(feature.path, space_id=space_id),
        )
        for feature in port.feature_transition.added
    )
    return replace(
        port,
        id=identity,
        space_id=space_id,
        feature_transition=replace(port.feature_transition, added=features),
    )


def fixture_request(
    operation=None,
    *,
    source=None,
    alphabet="RNA",
    topology="linear",
    inherit=False,
    output_chemistry=None,
    helper=False,
):
    provenance = fixture_provenance("construction-checker")
    source = source or make_molecule("source", "ACGUAC", coding_status="noncoding")
    operation = operation or SliceOperation(ValueSelection(ValueRef("root", "root")))
    chemistry = output_chemistry or fixture_chemistry(alphabet, topology)
    transition = ChemistryTransition(
        "exact_inheritance" if inherit else "explicit_output",
        None if inherit else chemistry,
        ()
        if inherit
        else tuple(
            ChemistryDisposition(
                "root",
                component,
                "declared_replacement",
                (component,)
                + tuple("modification:" + item.id for item in chemistry.modifications)
                if component == "modification_inventory"
                else (component,),
                provenance,
            )
            for component in sorted(CHEMISTRY_FACETS)
        )
        + tuple(
            ChemistryDisposition(
                "root", "modification:" + modification.id, "not_carried", (), provenance
            )
            for modification in source.chemistry.modifications
        ),
        provenance,
    )
    port = ProductPort(
        "derived",
        "derived.space",
        alphabet,
        topology,
        transition,
        FeatureTransition(
            tuple(
                FeatureDisposition("root", feature.id, "not_carried", (), provenance)
                for feature in source.features
            ),
            (
                MoleculeFeature(
                    "payload_region",
                    "nominal_test_region",
                    CoordinatePath("derived.space", (IndexSpan(0, 1),), "+"),
                    provenance,
                ),
            ),
            provenance,
        ),
    )
    member = OutputMember(
        "payload",
        ValueRef("product", "derived"),
        "payload.space",
        "delivered_rna",
        "complete",
        "noncoding",
        provenance,
    )
    requirement = MemberRequirement(
        "payload_requirement",
        "payload",
        member.id,
        None,
        None,
        (RoleDeclaration("payload_role", "payload", "requested_payload", "cytoplasm"),),
    )
    members, requirements = (member,), (requirement,)
    if helper:
        members += (replace(member, id="helper", space_id="helper.space"),)
        requirements += (
            MemberRequirement(
                "helper_requirement",
                "delivered_helper",
                "helper",
                None,
                None,
                (RoleDeclaration("helper_role", "helper", "helper", "cytoplasm"),),
            ),
        )
    return CircuitConstructionRequest(
        "artificial_construction",
        make_circuit_requests()["product"],
        (RootSource("root", source, provenance),),
        (TransformStep("step", operation, (port,), (), provenance),),
        members,
        requirements,
        "strict",
        payload_structures=(payload_contract(topology=topology),),
    )


def selection(*spans, strand="+"):
    return ValueSelection(
        ValueRef("root", "root"),
        CoordinatePath(
            "source.space", tuple(IndexSpan(start, end) for start, end in spans), strand
        ),
    )


def processing_request(operation_type, recipes, *, protein=False):
    source = (
        make_molecule("source", "ACDEFG", form="protein_precursor")
        if protein
        else make_molecule("source", "ACGUAC", coding_status="noncoding")
    )
    request = fixture_request(source=source, alphabet="protein" if protein else "RNA")
    prototype = request.steps[0]
    ports = tuple(named_port(prototype.ports[0], identity) for identity in recipes)
    operation = operation_type(
        ValueSelection(ValueRef("root", "root")),
        tuple(
            ProcessingProduct(
                identity,
                CoordinatePath(
                    source.space.id, tuple(IndexSpan(*span) for span in spans), "+"
                ),
            )
            for identity, spans in recipes.items()
        ),
    )
    members, requirements = [], []
    for index, identity in enumerate(recipes):
        member = OutputMember(
            identity + "_member",
            ValueRef("product", identity),
            identity + ".final_space",
            "mature_protein" if protein else "delivered_rna",
            "complete",
            "inapplicable" if protein else "noncoding",
            prototype.provenance,
        )
        payload = not protein and index == 0
        members.append(member)
        requirements.append(
            MemberRequirement(
                identity + "_requirement",
                "payload" if payload else "encoded_product",
                member.id,
                None,
                None,
                (
                    RoleDeclaration(
                        identity + "_role",
                        identity,
                        "requested_payload" if payload else "helper",
                        "cytoplasm",
                    ),
                ),
            )
        )
    sources = request.sources
    if protein:
        rna = payload_source(
            make_molecule("rna_payload_source", "ACGUAC", coding_status="noncoding")
        )
        sources += (RootSource("payload_root", rna, prototype.provenance),)
        members.append(
            replace(request.output_members[0], value=ValueRef("root", "payload_root"))
        )
        requirements += list(request.requirements)
    return replace(
        request,
        sources=sources,
        steps=(replace(prototype, operation=operation, ports=ports),),
        output_members=tuple(members),
        requirements=tuple(requirements),
        payload_structures=(
            payload_contract("payload" if protein else next(iter(recipes)) + "_member"),
        ),
    )


def translation_request(
    operation=None,
    *,
    sequence="AUGGCUUAA",
    source=None,
    port_ids=("translated",),
    assumptions=(),
):
    source = payload_source(source or make_molecule("source", sequence))
    request = fixture_request(source=source, alphabet="protein")
    step = request.steps[0]
    operation = operation or TranslationOperation(
        ValueSelection(ValueRef("root", "root")), TranslationPolicy("ordinary_cds")
    )
    ports = tuple(named_port(step.ports[0], identity) for identity in port_ids)
    payload = replace(
        request.output_members[0],
        value=ValueRef("root", "root"),
        coding_status="coding",
    )
    members = [payload]
    requirements = list(request.requirements)
    for identity in port_ids:
        member = OutputMember(
            identity + "_member",
            ValueRef("product", identity),
            identity + ".final_space",
            "mature_protein",
            "complete",
            "inapplicable",
            step.provenance,
        )
        members.append(member)
        requirements.append(
            MemberRequirement(
                identity + "_requirement",
                "encoded_product",
                member.id,
                None,
                None,
                (RoleDeclaration(identity + "_role", identity, "helper", "cytoplasm"),),
            )
        )
    return replace(
        request,
        steps=(
            replace(step, operation=operation, ports=ports, assumptions=assumptions),
        ),
        output_members=tuple(members),
        requirements=tuple(requirements),
    )


def with_inosine(source, positions):
    identity = ChemicalIdentity("biocompiler.chemical", "inosine", "1")
    modification = BaseModification(
        "inosine_sites",
        identity,
        "A",
        "positions",
        positions,
        fixture_provenance("chemical-sites"),
    )
    return replace(
        source, chemistry=replace(source.chemistry, modifications=(modification,))
    )


def with_protein_complex(request, *, stoichiometry=2):
    provenance = fixture_provenance("complex-membership")
    plan = ComplexMemberPlan(
        "complex",
        "protein_complex",
        (ComplexMemberConstituent("translated_member", stoichiometry, provenance),),
        provenance,
    )
    requirement = MemberRequirement(
        "complex_requirement",
        "encoded_product",
        "complex",
        None,
        None,
        (RoleDeclaration("complex_role", "dimer", "helper", "cytoplasm"),),
    )
    return replace(
        request,
        complex_members=(plan,),
        requirements=request.requirements + (requirement,),
    )


class CircuitConstructionCheckingTests(unittest.TestCase):
    def checked(self, request):
        candidate = construct_circuit_candidate(request)
        result = check_circuit_construction(candidate, expected_request=request)
        self.assertEqual(result.outcome, CheckOutcome.PASS, result.diagnostics)
        self.assertTrue(result.complete)
        return candidate, result

    def test_literal_whole_copy_preserves_source_request_and_checked_derivation(self):
        request = fixture_request(inherit=True)
        candidate, result = self.checked(request)
        self.assertEqual(candidate.values[0].sequence, "ACGUAC")
        self.assertEqual(candidate.bundle.molecules[0].sequence, "ACGUAC")
        segment = candidate.values[0].segments[0]
        self.assertEqual(segment.source_id, "root")
        self.assertEqual(segment.source_path.spans, (IndexSpan(0, 6),))
        self.assertEqual(segment.destination, IndexSpan(0, 6))
        self.assertEqual(segment.rule, "copy")
        member = candidate.bundle.molecules[0]
        self.assertEqual(member.assembly[0].source_space.id, "derived.space")
        self.assertNotEqual(member.space.id, member.assembly[0].source_space.id)
        self.assertEqual(candidate.bundle.request.to_dict(), request.circuit.to_dict())
        self.assertEqual(result.biological_function, "unestablished")
        self.assertEqual(result.human_therapeutic_admission, "not_admitted")
        restored = CircuitConstructionAssessment.from_json(result.to_json())
        self.assertEqual(restored.fingerprint, result.fingerprint)

    def test_literal_disjoint_slice_keeps_declared_segment_order(self):
        request = fixture_request(SliceOperation(selection((0, 2), (4, 6))))
        candidate, _ = self.checked(request)
        self.assertEqual(candidate.values[0].sequence, "ACAC")
        self.assertEqual(
            candidate.values[0].segments[0].source_path.spans,
            (IndexSpan(0, 2), IndexSpan(4, 6)),
        )

    def test_literal_concatenation_retains_each_occurrence_and_junction(self):
        request = fixture_request(
            ConcatenateOperation((selection((0, 2)), selection((3, 6))))
        )
        candidate, _ = self.checked(request)
        self.assertEqual(candidate.values[0].sequence, "ACUAC")
        self.assertEqual(
            tuple(item.destination for item in candidate.values[0].segments),
            (IndexSpan(0, 2), IndexSpan(2, 5)),
        )

    def test_literal_reverse_and_reverse_complement_are_distinct(self):
        for action, expected, rule in (
            ("reverse", "CAUCA", "copy"),
            ("reverse_complement", "GUAGU", "complement"),
        ):
            with self.subTest(action=action):
                request = fixture_request(
                    OrientationOperation(selection((0, 2), (3, 6)), action)
                )
                candidate, _ = self.checked(request)
                value = candidate.values[0]
                self.assertEqual(value.sequence, expected)
                self.assertEqual(value.segments[0].rule, rule)
                self.assertEqual(value.segments[0].source_path.strand, "-")
                self.assertEqual(
                    value.segments[0].source_path.spans,
                    (IndexSpan(3, 6), IndexSpan(0, 2)),
                )

    def test_literal_explicit_coding_strand_transcription(self):
        dna = make_molecule("source", "ATCGTA", form="delivered_dna")
        request = fixture_request(
            TranscriptionOperation(ValueSelection(ValueRef("root", "root"))),
            source=dna,
        )
        candidate, _ = self.checked(request)
        self.assertEqual(candidate.values[0].sequence, "AUCGUA")
        self.assertEqual(candidate.values[0].segments[0].rule, "dna_coding_to_rna.v1")
        self.assertEqual(request.sources[0].molecule.sequence, "ATCGTA")

    def test_transcription_rejects_reverse_and_disjoint_coding_paths(self):
        dna = make_molecule("source", "ATCGTA", form="delivered_dna")
        for selected in (selection((0, 6), strand="-"), selection((0, 2), (4, 6))):
            with self.subTest(path=selected.path):
                request = fixture_request(TranscriptionOperation(selected), source=dna)
                candidate = construct_circuit_candidate(request)
                result = check_circuit_construction(candidate, expected_request=request)
                self.assertEqual(result.outcome, CheckOutcome.UNSUPPORTED)
                self.assertFalse(result.complete)
                self.assertIn(
                    "step:step:unsupported_transcription_path", candidate.diagnostics
                )

    def test_wrong_alphabet_is_explicitly_unsupported_and_missing(self):
        request = fixture_request(
            TranscriptionOperation(ValueSelection(ValueRef("root", "root")))
        )
        candidate = construct_circuit_candidate(request)
        result = check_circuit_construction(candidate, expected_request=request)
        self.assertEqual(result.outcome, CheckOutcome.UNSUPPORTED)
        self.assertIsNone(candidate.bundle)
        self.assertEqual(candidate.missing_members, ("payload",))
        self.assertFalse(result.complete)

    def test_changed_base_with_recomputed_identity_fails_sequence_comparison(self):
        request = fixture_request()
        candidate, _ = self.checked(request)
        changed = replace(
            candidate, values=(replace(candidate.values[0], sequence="ACGAAC"),)
        )
        self.assertNotEqual(changed.fingerprint, candidate.fingerprint)
        result = check_circuit_construction(changed, expected_request=request)
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertIn("fail:value:derived:sequence", result.diagnostics)

    def test_forged_source_traversal_fails_derivation_comparison(self):
        request = fixture_request()
        candidate, _ = self.checked(request)
        value = candidate.values[0]
        segment = replace(
            value.segments[0],
            source_path=replace(value.segments[0].source_path, strand="-"),
        )
        changed = replace(candidate, values=(replace(value, segments=(segment,)),))
        result = check_circuit_construction(changed, expected_request=request)
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertIn("fail:value:derived:segments", result.diagnostics)

    def test_missing_generated_value_cannot_hide_behind_a_complete_bundle(self):
        request = fixture_request()
        candidate, _ = self.checked(request)
        result = check_circuit_construction(
            replace(candidate, values=()), expected_request=request
        )
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertIn("fail:constructed_value_inventory", result.diagnostics)

    def test_omitted_required_helper_cannot_leave_a_complete_payload_claim(self):
        request = fixture_request(helper=True)
        candidate, _ = self.checked(request)
        changed_bundle = replace(
            candidate.bundle,
            molecules=tuple(
                item for item in candidate.bundle.molecules if item.id == "payload"
            ),
            role_instances=tuple(
                item
                for item in candidate.bundle.role_instances
                if item.subject_id == "payload"
            ),
        )
        result = check_circuit_construction(
            replace(candidate, bundle=changed_bundle), expected_request=request
        )
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertIn("fail:final_molecule_inventory_or_authority", result.diagnostics)

    def test_saved_diagnostics_cannot_be_removed_to_promote_unsupported_output(self):
        request = fixture_request(
            TranscriptionOperation(ValueSelection(ValueRef("root", "root")))
        )
        candidate = construct_circuit_candidate(request)
        result = check_circuit_construction(
            replace(candidate, diagnostics=()), expected_request=request
        )
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertIn("fail:construction_diagnostic_inventory", result.diagnostics)

    def test_checker_works_with_disabled_producer(self):
        request = fixture_request()
        candidate, _ = self.checked(request)
        with patch(
            "biocompiler.backends.circuit_construction.construct_circuit_candidate",
            side_effect=AssertionError("producer must not supply checker expectations"),
        ):
            self.assertTrue(
                check_circuit_construction(candidate, expected_request=request).passed
            )

    def test_replay_requires_complete_independent_request_and_assessment_identity(self):
        request = fixture_request()
        candidate, result = self.checked(request)
        self.assertEqual(
            verify_circuit_construction_assessment(
                result, candidate, expected_request=request
            ),
            result,
        )
        changed_request = replace(request, mode="diagnostic")
        changed_result = check_circuit_construction(
            candidate, expected_request=changed_request
        )
        self.assertEqual(changed_result.outcome, CheckOutcome.FAIL)
        with self.assertRaisesRegex(SerializationError, "fresh complete replay"):
            verify_circuit_construction_assessment(
                result, candidate, expected_request=changed_request
            )
        with self.assertRaises(SerializationError):
            replace(result, human_therapeutic_admission="admitted")

    def test_unknown_cap_cannot_gain_complete_nominal_handoff(self):
        chemistry = fixture_chemistry()
        chemistry = replace(
            chemistry,
            cap=ChemistryClaim("unknown", None, fixture_provenance("unknown-cap")),
        )
        request = fixture_request(output_chemistry=chemistry)
        candidate = construct_circuit_candidate(request)
        result = check_circuit_construction(candidate, expected_request=request)
        self.assertFalse(result.complete)
        self.assertIn(result.outcome, (CheckOutcome.UNKNOWN, CheckOutcome.UNSUPPORTED))
        self.assertIn("member:payload:nominal_incomplete", candidate.diagnostics)
        self.assertIsNotNone(candidate.bundle)

    def test_output_budget_is_checked_before_any_residue_reconstruction(self):
        request = fixture_request()
        with (
            patch(
                "biocompiler.verification.circuit_construction.MAX_CUMULATIVE_PRODUCED_RESIDUES",
                1,
            ),
            patch(
                "biocompiler.verification.circuit_construction._read_path",
                side_effect=AssertionError("must not allocate output"),
            ),
        ):
            candidate = reconstruct_for_check(request)
        self.assertEqual(candidate.values, ())
        self.assertIn("step:step:residue_budget", candidate.diagnostics)

    def test_schema_bypass_is_reparsed_before_acceptance(self):
        request = fixture_request()
        candidate, _ = self.checked(request)
        malformed = replace(candidate)
        object.__setattr__(malformed, "request_fingerprint", "forged")
        with self.assertRaises(SerializationError):
            check_circuit_construction(malformed, expected_request=request)

    def test_ordered_intermediate_reconstruction_keeps_every_step_and_root(self):
        dna = make_molecule("source", "ATCGTA", form="delivered_dna")
        request = fixture_request(
            TranscriptionOperation(ValueSelection(ValueRef("root", "root"))),
            source=dna,
        )
        original = request.steps[0]
        port = original.ports[0]
        second_port = replace(
            named_port(port, "oriented"),
            chemistry_transition=replace(
                port.chemistry_transition,
                dispositions=tuple(
                    replace(item, source_id="derived")
                    for item in port.chemistry_transition.dispositions
                ),
            ),
            feature_transition=replace(
                named_port(port, "oriented").feature_transition,
                dispositions=(
                    FeatureDisposition(
                        "derived",
                        "payload_region",
                        "not_carried",
                        (),
                        original.provenance,
                    ),
                ),
            ),
        )
        second = replace(
            original,
            id="orientation_step",
            operation=OrientationOperation(
                ValueSelection(ValueRef("product", "derived")), "reverse_complement"
            ),
            ports=(second_port,),
        )
        request = replace(
            request,
            steps=(original, second),
            output_members=(
                replace(
                    request.output_members[0], value=ValueRef("product", "oriented")
                ),
            ),
        )
        candidate, _ = self.checked(request)
        values = {item.id: item for item in candidate.values}
        self.assertEqual(values["derived"].sequence, "AUCGUA")
        self.assertEqual(values["oriented"].sequence, "UACGAU")
        self.assertEqual(values["oriented"].segments[0].source_id, "derived")
        self.assertEqual(values["oriented"].step_id, "orientation_step")
        self.assertEqual(candidate.bundle.molecules[0].sequence, "UACGAU")

    def test_supplied_root_can_be_finalized_without_fabricating_a_step(self):
        request = fixture_request(
            source=payload_source(make_molecule("source", "ACGUAC"))
        )
        request = replace(
            request,
            steps=(),
            output_members=(
                replace(request.output_members[0], value=ValueRef("root", "root")),
            ),
        )
        candidate, _ = self.checked(request)
        self.assertEqual(candidate.values, ())
        self.assertEqual(candidate.bundle.molecules[0].sequence, "ACGUAC")
        self.assertEqual(
            candidate.bundle.molecules[0].assembly[0].source_space.id, "source.space"
        )

    def test_whole_circle_preserves_topology_and_explicit_slice_is_linear(self):
        circle = make_molecule("source", "ACGUAC", topology="circular")
        whole = fixture_request(source=circle, topology="circular", inherit=True)
        whole_candidate, _ = self.checked(whole)
        self.assertEqual(whole_candidate.values[0].space.topology, "circular")
        self.assertEqual(whole_candidate.values[0].sequence, "ACGUAC")
        sliced = fixture_request(
            SliceOperation(selection((4, 6), (0, 2))), source=circle
        )
        sliced_candidate, _ = self.checked(sliced)
        self.assertEqual(sliced_candidate.values[0].space.topology, "linear")
        self.assertEqual(sliced_candidate.values[0].sequence, "ACAC")

    def test_rna_cleavage_preserves_all_literal_products(self):
        request = processing_request(
            RNACleavageOperation, {"main": ((0, 2),), "released": ((2, 6),)}
        )
        candidate, _ = self.checked(request)
        self.assertEqual(
            {value.id: value.sequence for value in candidate.values},
            {"main": "AC", "released": "GUAC"},
        )
        self.assertEqual(len(candidate.bundle.molecules), 2)

    def test_rna_splicing_preserves_removed_sequence_as_an_explicit_product(self):
        request = processing_request(
            RNASplicingOperation,
            {"main": ((0, 2), (4, 6)), "released": ((2, 4),)},
        )
        candidate, _ = self.checked(request)
        self.assertEqual(
            {value.id: value.sequence for value in candidate.values},
            {"main": "ACAC", "released": "GU"},
        )
        self.assertEqual(
            candidate.values[0].segments[0].source_path.spans,
            (IndexSpan(0, 2), IndexSpan(4, 6)),
        )

    def test_protein_cleavage_and_splicing_preserve_literal_residues(self):
        for kind, recipes, expected in (
            (
                ProteinCleavageOperation,
                {"main": ((0, 2),), "released": ((2, 6),)},
                {"main": "AC", "released": "DEFG"},
            ),
            (
                ProteinSplicingOperation,
                {"main": ((0, 2), (4, 6)), "released": ((2, 4),)},
                {"main": "ACFG", "released": "DE"},
            ),
        ):
            with self.subTest(operation=kind.__name__):
                request = processing_request(kind, recipes, protein=True)
                candidate, _ = self.checked(request)
                self.assertEqual(
                    {value.id: value.sequence for value in candidate.values}, expected
                )
                self.assertEqual(len(candidate.bundle.molecules), 3)
                self.assertEqual(
                    {value.space.alphabet for value in candidate.values}, {"protein"}
                )

    def test_processing_rejects_gaps_overlap_and_reordered_splice_segments(self):
        for recipes in (
            {"main": ((0, 2),), "released": ((3, 6),)},
            {"main": ((0, 3),), "released": ((2, 6),)},
            {"main": ((4, 6), (0, 2)), "released": ((2, 4),)},
        ):
            with self.subTest(recipes=recipes):
                request = processing_request(RNASplicingOperation, recipes)
                candidate = construct_circuit_candidate(request)
                result = check_circuit_construction(candidate, expected_request=request)
                self.assertEqual(result.outcome, CheckOutcome.FAIL)
                self.assertEqual(candidate.values, ())
                self.assertIn(
                    "step:step:invalid_processing_partition", candidate.diagnostics
                )

    def test_a_missing_released_product_cannot_be_a_complete_processing_recipe(self):
        request = processing_request(RNACleavageOperation, {"main": ((0, 2),)})
        candidate = construct_circuit_candidate(request)
        result = check_circuit_construction(candidate, expected_request=request)
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertIn("step:step:invalid_processing_partition", candidate.diagnostics)
        self.assertIsNone(candidate.bundle)

    def test_processing_nominal_failure_is_atomic_across_product_ports(self):
        request = processing_request(
            RNACleavageOperation, {"main": ((0, 2),), "released": ((2, 6),)}
        )
        step = request.steps[0]
        second = step.ports[1]
        second = replace(
            second,
            chemistry_transition=replace(
                second.chemistry_transition, output=fixture_chemistry("RNA", "circular")
            ),
        )
        request = replace(
            request, steps=(replace(step, ports=(step.ports[0], second)),)
        )
        candidate = construct_circuit_candidate(request)
        result = check_circuit_construction(candidate, expected_request=request)
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertEqual(candidate.values, ())
        self.assertEqual(candidate.missing_members, ("main_member", "released_member"))
        self.assertIn("step:step:invalid_operation", candidate.diagnostics)

    def test_processing_budget_counts_all_products_before_reconstruction(self):
        request = processing_request(
            RNACleavageOperation, {"main": ((0, 2),), "released": ((2, 6),)}
        )
        with (
            patch(
                "biocompiler.verification.circuit_construction.MAX_CUMULATIVE_PRODUCED_RESIDUES",
                5,
            ),
            patch(
                "biocompiler.verification.circuit_construction._read_path",
                side_effect=AssertionError("all product lengths must be checked first"),
            ),
        ):
            candidate = reconstruct_for_check(request)
        self.assertEqual(candidate.values, ())
        self.assertIn("step:step:residue_budget", candidate.diagnostics)

    def test_circularization_preserves_the_explicit_origin_and_source_path(self):
        for origin, expected, spans in (
            (0, "ACGUAC", (IndexSpan(0, 6),)),
            (2, "GUACAC", (IndexSpan(2, 6), IndexSpan(0, 2))),
        ):
            with self.subTest(origin=origin):
                request = fixture_request(
                    CircularizationOperation(
                        ValueSelection(ValueRef("root", "root")), origin
                    ),
                    topology="circular",
                )
                candidate, _ = self.checked(request)
                self.assertEqual(candidate.values[0].sequence, expected)
                self.assertEqual(candidate.values[0].space.topology, "circular")
                self.assertEqual(
                    candidate.values[0].segments[0].source_path.spans, spans
                )
                self.assertEqual(candidate.values[0].segments[0].rule, "copy")

    def test_circularization_does_not_normalize_an_out_of_bounds_origin(self):
        request = fixture_request(
            CircularizationOperation(ValueSelection(ValueRef("root", "root")), 6),
            topology="circular",
        )
        candidate = construct_circuit_candidate(request)
        result = check_circuit_construction(candidate, expected_request=request)
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertIn("step:step:invalid_selection", candidate.diagnostics)

    def test_canonical_edit_changes_only_the_declared_unmodified_base(self):
        operation = BaseEditingOperation(
            ValueSelection(ValueRef("root", "root")),
            (CanonicalBaseEdit(0, "A", "G"),),
            (),
        )
        request = fixture_request(operation)
        candidate, _ = self.checked(request)
        self.assertEqual(candidate.values[0].sequence, "GCGUAC")
        self.assertEqual(candidate.values[0].segments[0].rule, "rna_editing.v1")
        self.assertEqual(request.sources[0].molecule.sequence, "ACGUAC")

    def test_chemical_edit_retains_canonical_a_and_exact_inosine_identity(self):
        identity = ChemicalIdentity("biocompiler.chemical", "inosine", "1")
        operation = BaseEditingOperation(
            ValueSelection(ValueRef("root", "root")),
            (),
            (ChemicalBaseEdit(0, "A", None, identity),),
        )
        output = with_inosine(
            make_molecule("output_chemistry", "ACGUAC"), (0,)
        ).chemistry
        request = fixture_request(operation, output_chemistry=output)
        candidate, _ = self.checked(request)
        self.assertEqual(candidate.values[0].sequence, "ACGUAC")
        self.assertEqual(
            candidate.values[0].chemistry.modifications[0].identity, identity
        )
        self.assertNotIn("I", candidate.values[0].sequence)

    def test_edit_rejects_wrong_expected_symbol_and_modified_canonical_site(self):
        operation = BaseEditingOperation(
            ValueSelection(ValueRef("root", "root")),
            (CanonicalBaseEdit(0, "A", "G"),),
            (),
        )
        for source in (
            make_molecule("source", "CCGUAC"),
            with_inosine(make_molecule("source", "ACGUAC"), (0,)),
        ):
            with self.subTest(source=source.sequence):
                request = fixture_request(operation, source=source)
                candidate = construct_circuit_candidate(request)
                result = check_circuit_construction(candidate, expected_request=request)
                self.assertEqual(result.outcome, CheckOutcome.FAIL)
                self.assertIn("step:step:invalid_edit", candidate.diagnostics)

    def test_edit_rejects_undeclared_chemical_changes_and_changed_cap(self):
        identity = ChemicalIdentity("biocompiler.chemical", "inosine", "1")
        operation = BaseEditingOperation(
            ValueSelection(ValueRef("root", "root")),
            (),
            (ChemicalBaseEdit(0, "A", None, identity),),
        )
        authorized = with_inosine(make_molecule("chemistry", "ACGUAC"), (0,)).chemistry
        offsite = with_inosine(make_molecule("chemistry", "ACGUAC"), (0, 4)).chemistry
        cap_change = replace(
            authorized,
            cap=ChemistryClaim(
                "declared",
                ChemicalIdentity("artificial", "different_cap", "1"),
                fixture_provenance("changed-cap"),
            ),
        )
        for chemistry in (offsite, cap_change):
            with self.subTest(chemistry=chemistry.fingerprint):
                request = fixture_request(operation, output_chemistry=chemistry)
                candidate = construct_circuit_candidate(request)
                result = check_circuit_construction(candidate, expected_request=request)
                self.assertEqual(result.outcome, CheckOutcome.FAIL)
                self.assertIn("step:step:invalid_edit", candidate.diagnostics)

    def test_edit_unknown_modification_inventory_is_unsupported(self):
        source = make_molecule("source", "ACGUAC")
        source = replace(
            source,
            chemistry=replace(
                source.chemistry, modification_inventory_status="unknown"
            ),
        )
        operation = BaseEditingOperation(
            ValueSelection(ValueRef("root", "root")),
            (CanonicalBaseEdit(0, "A", "G"),),
            (),
        )
        request = fixture_request(operation, source=source)
        candidate = construct_circuit_candidate(request)
        result = check_circuit_construction(candidate, expected_request=request)
        self.assertEqual(result.outcome, CheckOutcome.UNSUPPORTED)
        self.assertIn("step:step:unsupported_edit_chemistry", candidate.diagnostics)

    def test_ordinary_translation_keeps_terminal_stop_out_of_the_protein(self):
        request = translation_request()
        candidate, _ = self.checked(request)
        value = candidate.values[0]
        self.assertEqual(value.sequence, "MA")
        self.assertNotIn("*", value.sequence)
        self.assertEqual(value.segments[0].destination, IndexSpan(0, 2))
        self.assertEqual(value.segments[0].source_path.spans, (IndexSpan(0, 6),))
        self.assertEqual(value.segments[0].rule, "translation_codon.v1")
        self.assertEqual(value.consumed[0].source_path.spans, (IndexSpan(6, 9),))
        self.assertEqual(value.consumed[0].reason, "terminal_stop")

    def test_translation_stop_correspondence_cannot_be_removed(self):
        request = translation_request()
        candidate, _ = self.checked(request)
        changed = replace(
            candidate, values=(replace(candidate.values[0], consumed=()),)
        )
        result = check_circuit_construction(changed, expected_request=request)
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertIn("fail:value:translated:consumed", result.diagnostics)

    def test_translation_rejects_frame_start_terminal_and_internal_stop_changes(self):
        for sequence in ("AUGGCUUA", "GUGGCUUAA", "AUGGCUAAA", "AUGUAGUAA"):
            with self.subTest(sequence=sequence):
                request = translation_request(sequence=sequence)
                candidate = construct_circuit_candidate(request)
                result = check_circuit_construction(candidate, expected_request=request)
                self.assertEqual(result.outcome, CheckOutcome.FAIL)
                self.assertIn("step:step:invalid_translation", candidate.diagnostics)

    def test_conditional_codon_policy_uses_exact_declared_triplet_and_assumption(self):
        policy = TranslationPolicy(
            "conditional_cds",
            recodings=(CodonRecoding(1, "UAG", "G", "declared_readthrough"),),
        )
        operation = TranslationOperation(
            ValueSelection(ValueRef("root", "root")), policy
        )
        request = translation_request(
            operation, sequence="AUGUAGUAA", assumptions=("declared_readthrough",)
        )
        candidate, _ = self.checked(request)
        self.assertEqual(candidate.values[0].sequence, "MG")
        mismatch = replace(
            policy, recodings=(replace(policy.recodings[0], expected_triplet="UGA"),)
        )
        changed = replace(
            request,
            steps=(
                replace(
                    request.steps[0], operation=replace(operation, policy=mismatch)
                ),
            ),
        )
        result = check_circuit_construction(
            construct_circuit_candidate(changed), expected_request=changed
        )
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertIn("fail:step:step:invalid_translation", result.diagnostics)

    def test_modified_codon_requires_explicit_readout_without_i_to_g_inference(self):
        source = with_inosine(make_molecule("source", "AUGACUUAA"), (3,))
        request = translation_request(source=source)
        candidate = construct_circuit_candidate(request)
        result = check_circuit_construction(candidate, expected_request=request)
        self.assertEqual(result.outcome, CheckOutcome.UNSUPPORTED)
        self.assertIn(
            "step:step:unsupported_translation_chemistry", candidate.diagnostics
        )
        policy = TranslationPolicy(
            "conditional_cds",
            recodings=(CodonRecoding(1, "ACU", "T", "declared_readout"),),
        )
        request = translation_request(
            TranslationOperation(ValueSelection(ValueRef("root", "root")), policy),
            source=source,
            assumptions=("declared_readout",),
        )
        candidate, _ = self.checked(request)
        self.assertEqual(candidate.values[0].sequence, "MT")
        self.assertEqual(request.sources[0].molecule.sequence, "AUGACUUAA")

    def test_multiple_orfs_reconstruct_each_named_product_from_its_own_path(self):
        policy = TranslationPolicy("ordinary_cds")
        operation = MultiORFTranslationOperation(
            (
                TranslationProduct("first", selection((0, 9)), policy),
                TranslationProduct("second", selection((9, 18)), policy),
            )
        )
        request = translation_request(
            operation, sequence="AUGGCUUAAAUGUUUUAA", port_ids=("first", "second")
        )
        candidate, _ = self.checked(request)
        self.assertEqual(
            {value.id: value.sequence for value in candidate.values},
            {"first": "MA", "second": "MF"},
        )
        self.assertEqual(
            {
                value.id: value.consumed[0].source_path.spans
                for value in candidate.values
            },
            {"first": (IndexSpan(6, 9),), "second": (IndexSpan(15, 18),)},
        )

    def test_declared_no_product_branch_does_not_establish_biological_absence(self):
        whole = ValueSelection(ValueRef("root", "root"))
        operation = ConditionalTranslationOperation(
            (
                TranslationBranch(
                    "on_branch",
                    "on",
                    whole,
                    TranslationPolicy("ordinary_cds"),
                    "translated",
                ),
                TranslationBranch("off_branch", "off", whole, None, None),
            )
        )
        request = translation_request(operation, assumptions=("on", "off"))
        candidate = construct_circuit_candidate(request)
        result = check_circuit_construction(candidate, expected_request=request)
        self.assertEqual(candidate.values[0].sequence, "MA")
        self.assertEqual(result.outcome, CheckOutcome.UNSUPPORTED)
        self.assertIn(
            "unsupported:step:step:no_product_branch_semantics:off_branch",
            result.diagnostics,
        )
        self.assertFalse(result.complete)

    def test_ribosomal_skipping_retains_product_residues_without_a_precursor(self):
        operation = RibosomalSkippingOperation(
            ValueSelection(ValueRef("root", "root")),
            TranslationPolicy("ordinary_cds"),
            (
                PeptideProduct("first", IndexSpan(0, 2)),
                PeptideProduct("second", IndexSpan(2, 3)),
            ),
            "declared_skipping",
        )
        request = translation_request(
            operation,
            sequence="AUGGCUUUUUAA",
            port_ids=("first", "second"),
            assumptions=("declared_skipping",),
        )
        candidate, _ = self.checked(request)
        self.assertEqual(
            {value.id: value.sequence for value in candidate.values},
            {"first": "MA", "second": "F"},
        )
        self.assertEqual(
            {
                value.id: value.segments[0].source_path.spans
                for value in candidate.values
            },
            {"first": (IndexSpan(0, 6),), "second": (IndexSpan(6, 9),)},
        )
        self.assertTrue(
            all(
                value.consumed[0].source_path.spans == (IndexSpan(9, 12),)
                for value in candidate.values
            )
        )
        self.assertFalse(any(value.sequence == "MAF" for value in candidate.values))

    def test_skipping_cannot_omit_or_duplicate_a_translated_residue(self):
        for spans in (
            (IndexSpan(0, 1), IndexSpan(2, 3)),
            (IndexSpan(0, 2), IndexSpan(1, 3)),
        ):
            with self.subTest(spans=spans):
                operation = RibosomalSkippingOperation(
                    ValueSelection(ValueRef("root", "root")),
                    TranslationPolicy("ordinary_cds"),
                    (
                        PeptideProduct("first", spans[0]),
                        PeptideProduct("second", spans[1]),
                    ),
                    "declared_skipping",
                )
                request = translation_request(
                    operation,
                    sequence="AUGGCUUUUUAA",
                    port_ids=("first", "second"),
                    assumptions=("declared_skipping",),
                )
                candidate = construct_circuit_candidate(request)
                result = check_circuit_construction(candidate, expected_request=request)
                self.assertEqual(result.outcome, CheckOutcome.FAIL)
                self.assertIn(
                    "step:step:invalid_skipping_partition", candidate.diagnostics
                )

    def test_complex_is_separately_pinned_membership_without_covalent_concatenation(
        self,
    ):
        request = with_protein_complex(translation_request())
        candidate, _ = self.checked(request)
        molecules = {item.id: item for item in candidate.bundle.molecules}
        complex_ = candidate.bundle.complexes[0]
        self.assertEqual(molecules["translated_member"].sequence, "MA")
        self.assertFalse(any(item.sequence == "MAMA" for item in molecules.values()))
        self.assertEqual(complex_.constituents[0].stoichiometry, 2)
        self.assertEqual(
            complex_.constituents[0].molecule_fingerprint,
            molecules["translated_member"].fingerprint,
        )
        changed = replace(
            request,
            complex_members=(
                replace(
                    request.complex_members[0],
                    constituents=(
                        replace(
                            request.complex_members[0].constituents[0], stoichiometry=3
                        ),
                    ),
                ),
            ),
        )
        self.assertEqual(
            check_circuit_construction(candidate, expected_request=changed).outcome,
            CheckOutcome.FAIL,
        )

    def test_unknown_complex_stoichiometry_is_retained_and_not_complete(self):
        request = with_protein_complex(translation_request(), stoichiometry=None)
        candidate = construct_circuit_candidate(request)
        result = check_circuit_construction(candidate, expected_request=request)
        self.assertEqual(result.outcome, CheckOutcome.UNKNOWN)
        self.assertIsNone(candidate.bundle.complexes[0].constituents[0].stoichiometry)
        self.assertIn("unknown:member:complex:nominal_incomplete", result.diagnostics)

    def test_unavailable_constituent_marks_complex_missing_as_well(self):
        request = with_protein_complex(translation_request(sequence="AUGGCU"))
        candidate = construct_circuit_candidate(request)
        result = check_circuit_construction(candidate, expected_request=request)
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertEqual(candidate.missing_members, ("complex", "translated_member"))
        self.assertIn("member:complex:unavailable_value", candidate.diagnostics)
        self.assertIsNone(candidate.bundle)

    def test_amount_replay_binds_actual_subject_pins_preparations_and_unknown_quantity(
        self,
    ):
        for quantity in (None, 0, 3.25):
            with self.subTest(quantity=quantity):
                request = with_protein_complex(translation_request())
                declaration = AmountDeclaration(
                    "amount",
                    "complex",
                    "preparation",
                    ("complex_role",),
                    quantity,
                    "arbitrary_fixture_units",
                    fixture_provenance("amount"),
                )
                request = replace(request, amounts=(declaration,))
                candidate, _ = self.checked(request)
                amount = candidate.experimental_amounts[0]
                self.assertEqual(amount.quantity, quantity)
                self.assertEqual(
                    amount.subject_fingerprint,
                    candidate.bundle.complexes[0].fingerprint,
                )
                self.assertEqual(amount.preparation_id, "preparation")
                for changed in (
                    replace(candidate, experimental_amounts=()),
                    replace(
                        candidate,
                        experimental_amounts=(
                            replace(amount, preparation_id="another"),
                        ),
                    ),
                ):
                    assessment = check_circuit_construction(
                        changed, expected_request=request
                    )
                    self.assertEqual(assessment.outcome, CheckOutcome.FAIL)
                    self.assertIn(
                        "fail:experimental_amount_authority", assessment.diagnostics
                    )

    def test_nominal_alias_amount_conflict_drops_final_bundle_and_amounts_atomically(
        self,
    ):
        request = fixture_request(helper=True)
        provenance = fixture_provenance("amount")
        declarations = (
            AmountDeclaration(
                "payload_amount",
                "payload",
                "one_preparation",
                ("payload_role",),
                1,
                "fixture_units",
                provenance,
            ),
            AmountDeclaration(
                "helper_amount",
                "helper",
                "one_preparation",
                ("helper_role",),
                2,
                "fixture_units",
                provenance,
            ),
        )
        request = replace(request, amounts=declarations)
        candidate = construct_circuit_candidate(request)
        result = check_circuit_construction(candidate, expected_request=request)
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertIn("bundle:invalid_inventory", candidate.diagnostics)
        self.assertIsNone(candidate.bundle)
        self.assertEqual(candidate.experimental_amounts, ())
        separate = replace(
            request,
            amounts=(
                declarations[0],
                replace(declarations[1], preparation_id="second_preparation"),
            ),
        )
        separate_candidate, _ = self.checked(separate)
        self.assertEqual(len(separate_candidate.experimental_amounts), 2)

    def test_payload_contract_authority_is_required_and_replayed(self):
        request = fixture_request()
        missing = replace(request, payload_structures=())
        result = check_circuit_construction(
            construct_circuit_candidate(missing), expected_request=missing
        )
        self.assertEqual(result.outcome, CheckOutcome.UNSUPPORTED)
        self.assertTrue(
            any("payload_authority_missing" in item for item in result.diagnostics)
        )
        changed = replace(
            request,
            payload_structures=(
                replace(
                    request.payload_structures[0],
                    regions=(RequiredPayloadRegion("missing", "nominal_test_region"),),
                ),
            ),
        )
        result = check_circuit_construction(
            construct_circuit_candidate(changed), expected_request=changed
        )
        self.assertEqual(result.outcome, CheckOutcome.FAIL)

    def test_assessment_diagnostic_limit_preserves_omitted_failure_severity(self):
        request = fixture_request()
        candidate = construct_circuit_candidate(request)
        with (
            patch(
                "biocompiler.verification.circuit_construction.MAX_ASSESSMENT_DIAGNOSTICS",
                2,
            ),
            patch(
                "biocompiler.verification.circuit_payloads.check_payload_structures",
                return_value=(
                    ("first_failure", "second_failure", "third_failure"),
                    ("unsupported_detail",),
                ),
            ),
        ):
            result = check_circuit_construction(candidate, expected_request=request)
            self.assertEqual(result.outcome, CheckOutcome.FAIL)
            self.assertEqual(
                result.diagnostics,
                ("fail:assessment_diagnostic_budget", "fail:first_failure"),
            )
            self.assertFalse(result.complete)

    def test_assessment_diagnostic_byte_limit_rejects_large_reports_before_encoding(
        self,
    ):
        request = fixture_request()
        candidate = construct_circuit_candidate(request)
        with (
            patch(
                "biocompiler.verification.circuit_construction.MAX_ASSESSMENT_DIAGNOSTIC_BYTES",
                8,
            ),
            patch(
                "biocompiler.verification.circuit_payloads.check_payload_structures",
                return_value=(("large_failure",), ()),
            ),
        ):
            result = check_circuit_construction(candidate, expected_request=request)
            self.assertEqual(result.outcome, CheckOutcome.FAIL)
            self.assertEqual(result.diagnostics, ("fail:assessment_diagnostic_budget",))


if __name__ == "__main__":
    unittest.main()
