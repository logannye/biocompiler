"""Cross-module R3 declarations using small, explicitly artificial fixtures.

Expected spellings, coordinate coverage and nominal identity relationships are
specified independently. No source retrieval, sequence emitter, transformation
pipeline or biological model supplies expected test results.
"""

from dataclasses import replace
import unittest

from biocompiler.artifacts.circuit_molecules import (
    CircuitMoleculeRecord,
    ExperimentalAmount,
)
from biocompiler.compiler.request import BuildRequest
from biocompiler.errors import SerializationError
from biocompiler.frontend.api import Therapy
from biocompiler.ir.circuit_intent import CircuitInputBinding, CircuitRequirement
from biocompiler.ir.circuit_molecules import (
    AssemblyOrigin,
    CircuitMolecule,
    CircuitMoleculeSet,
    ComplexConstituent,
    FormCoordinateMapping,
    MolecularComplex,
    MoleculeFeature,
    MoleculeRoleInstance,
)
from biocompiler.ir.circuit_profile import ImmuneRecipientIdentity
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.molecule_chemistry import (
    BaseModification,
    ChemicalIdentity,
    ChemistryClaim,
    MoleculeChemistry,
    TailDeclaration,
    TailLength,
)
from biocompiler.ir.molecule_records import DeclarationProvenance
from biocompiler.semantics.context import PayloadFormat
from biocompiler.semantics.molecule_coordinates import (
    CoordinatePath,
    CoordinateSpace,
    IndexSpan,
)
from examples.circuit_intent import make_circuit_requests


def provenance(label="fixture"):
    return DeclarationProvenance(
        "declared",
        (PinnedIdentity("source", "artificial_fixture", "1", "a" * 64),),
        "tests/artificial_declarations/" + label,
        "Invented software declaration only; no biological experiment or source extraction.",
    )


def chemical(accession):
    return ChemicalIdentity("biocompiler.chemical", accession, "1")


def path(space, start=0, end=None):
    return CoordinatePath(
        space.id, (IndexSpan(start, space.length if end is None else end),), "+"
    )


def chemistry(space):
    source = provenance("chemistry")
    inapplicable = ChemistryClaim("inapplicable", None, source)
    terminal_tail = TailDeclaration("inapplicable", None, None, None, source)
    if space.topology == "circular":
        cap = start = finish = inapplicable
    else:
        cap = (
            ChemistryClaim("absent", None, source)
            if space.alphabet == "RNA"
            else inapplicable
        )
        start = ChemistryClaim("declared", chemical("fixture_start_group"), source)
        finish = ChemistryClaim("declared", chemical("fixture_finish_group"), source)
        if space.alphabet == "RNA":
            terminal_tail = TailDeclaration(
                "declared", "absent", TailLength("exact", exact=0), None, source
            )
    return MoleculeChemistry(
        cap,
        start,
        finish,
        (),
        "inapplicable" if space.alphabet == "protein" else "declared",
        source,
        terminal_tail,
    )


def molecule(
    identity="rna",
    sequence="ACGU",
    *,
    alphabet="RNA",
    form="delivered_rna",
    topology="linear",
    coding_status="unknown",
):
    space = CoordinateSpace(
        "coordinates_" + identity,
        alphabet,
        len(sequence),
        topology,
        "N_to_C" if alphabet == "protein" else "5prime_to_3prime",
    )
    source_space = replace(space, id="source_" + identity)
    origin = AssemblyOrigin(
        "origin_" + identity,
        path(space),
        source_space,
        path(source_space),
        provenance("origin"),
    )
    return CircuitMolecule(
        identity,
        form,
        space,
        sequence,
        "complete",
        coding_status,
        (origin,),
        (),
        chemistry(space),
        provenance("molecule"),
    )


def form_request(form):
    """A separate simple fixture request, retaining its complete authored source."""
    template = make_circuit_requests()["product"]
    modality = (
        PayloadFormat.DNA
        if form in {"delivered_dna", "dna_expression_template"}
        else PayloadFormat.RNA
    )
    target = replace(template.profile.target, payload_format=modality)
    therapy = Therapy("molecular_form_fixture")
    cells = therapy.engineer("recipient", cell_type="declared human T cells")
    source = BuildRequest.freeze(therapy.freeze(), target=target)
    profile = replace(
        template.profile,
        target=target,
        molecular_form=modality,
        recipient=ImmuneRecipientIdentity(
            template.profile.recipient.lineage,
            target.fingerprint,
            target.human_target.cell_subtype.fingerprint,
        ),
        source_request=source,
    )
    requirement = CircuitRequirement(
        "form_requirement",
        template.requirements[0].behavior,
        cells.role,
        (cells.role,),
        None,
    )
    return replace(
        template,
        profile=profile,
        requirements=(requirement,),
        requested_form=form,
        deployment_id="declared_form_deployment",
    )


def role(
    subject, identity="payload", purpose="requested_payload", label="circuit_member"
):
    return MoleculeRoleInstance(
        identity, subject.id, subject.fingerprint, label, purpose, "cytoplasm"
    )


def bundle(molecules=None, *, request=None, complexes=(), roles=None, mappings=()):
    records = (molecule(),) if molecules is None else molecules
    if roles is None:
        roles = tuple(
            role(
                item,
                "payload" if index == 0 else "helper_" + item.id,
                "requested_payload" if index == 0 else "helper",
            )
            for index, item in enumerate(records)
        ) + tuple(role(item, "complex_" + item.id, "helper") for item in complexes)
    return CircuitMoleculeSet(
        "artificial_circuit_members",
        make_circuit_requests()["product"] if request is None else request,
        records,
        complexes,
        roles,
        mappings,
    )


class CircuitMoleculeIntegrationTests(unittest.TestCase):
    def test_full_circuit_source_wrappers_and_input_links_round_trip(self):
        request = make_circuit_requests()["product"]
        original = request.profile.source_request
        signal = original.build_request.intent.find(kind="signal")[0]
        requirement = request.requirements[0]
        bound = replace(
            requirement,
            source_node_ids=tuple(
                dict.fromkeys((*requirement.source_node_ids, signal.id))
            ),
            input_bindings=(CircuitInputBinding("A", signal.id),),
        )
        request = replace(request, requirements=(bound,))
        first, second = molecule("first"), molecule("second", "UGCA")
        declared = bundle((first, second), request=request)
        restored = CircuitMoleculeSet.from_json(declared.to_json())
        self.assertEqual(restored.request.to_dict(), request.to_dict())
        self.assertEqual(
            restored.request.profile.source_request.to_dict(), original.to_dict()
        )
        self.assertEqual(
            restored.request.requirements[0].input_bindings, bound.input_bindings
        )
        self.assertEqual(
            tuple(item.sequence for item in restored.molecules), ("ACGU", "UGCA")
        )

    def test_overlapping_annotations_do_not_duplicate_assembly_coverage(self):
        declared = molecule(sequence="AAUUAGCCU", coding_status="coding")
        space = declared.space
        features = (
            MoleculeFeature("orf", "cds", path(space), provenance("orf"), 0),
            MoleculeFeature(
                "regulator",
                "regulatory_feature",
                path(space, 1, 7),
                provenance("regulator"),
            ),
            MoleculeFeature(
                "conditional",
                "conditional_stop",
                path(space, 3, 6),
                provenance("conditional"),
            ),
        )
        declared = replace(declared, features=features)
        restored = CircuitMoleculeSet.from_json(
            bundle((declared,)).to_json()
        ).molecules[0]
        positions = tuple(
            index
            for item in restored.assembly
            for index in item.destination.positions(space)
        )
        self.assertEqual(positions, (0, 1, 2, 3, 4, 5, 6, 7, 8))
        self.assertEqual(restored.sequence, "AAUUAGCCU")
        self.assertEqual(len(restored.features), 3)
        self.assertEqual(restored.sequence[3:6], "UAG")

    def test_partition_gaps_overlap_and_empty_origins_reject(self):
        declared = molecule(sequence="ACGUACGU")
        original = declared.assembly[0]
        for intervals in (((0, 3), (4, 8)), ((0, 5), (4, 8)), ((0, 0), (0, 8))):
            with self.subTest(intervals=intervals):
                with self.assertRaises(SerializationError):
                    origins = tuple(
                        replace(
                            original,
                            id=f"part_{index}",
                            destination=path(declared.space, start, end),
                            source_path=path(original.source_space, start, end),
                        )
                        for index, (start, end) in enumerate(intervals)
                    )
                    replace(declared, assembly=origins)

    def test_multiple_orfs_and_unknown_boundaries_are_declarations_not_repairs(self):
        declared = molecule(sequence="AAUUAGCCU", coding_status="coding")
        features = (
            MoleculeFeature("main", "CDS", path(declared.space), provenance("main"), 0),
            MoleculeFeature(
                "upstream",
                "uORF",
                path(declared.space, 0, 6),
                provenance("upstream"),
                1,
            ),
            MoleculeFeature(
                "second", "ORF", path(declared.space, 3, 9), provenance("second"), 0
            ),
            MoleculeFeature(
                "uncertain",
                "regulatory_feature",
                None,
                DeclarationProvenance(
                    "unknown", (), None, "Boundary was not supplied."
                ),
            ),
        )
        declared = replace(declared, features=features)
        self.assertEqual(
            CircuitMolecule.from_json(declared.to_json()).sequence, "AAUUAGCCU"
        )
        self.assertEqual(len(declared.features), 4)
        self.assertTrue(declared.declared_nominal_complete)
        with self.assertRaises(SerializationError):
            replace(declared, coding_status="noncoding")

    def test_repeated_features_and_shared_species_roles_retain_multiplicity(self):
        first = molecule("first", "ACGUACGU")
        first = replace(
            first,
            features=(
                MoleculeFeature(
                    "repeat_one",
                    "repeated_motif",
                    path(first.space, 0, 4),
                    provenance("repeat1"),
                ),
                MoleculeFeature(
                    "repeat_two",
                    "repeated_motif",
                    path(first.space, 4, 8),
                    provenance("repeat2"),
                ),
            ),
        )
        second = molecule("second", "ACGUACGU")
        self.assertEqual(
            first.declared_nominal_identity, second.declared_nominal_identity
        )
        roles = (
            role(first),
            role(first, "second_role", "helper", "alternate_role"),
            role(second, "separate_member", "helper"),
        )
        declared = bundle((first, second), roles=roles)
        self.assertEqual(len(declared.molecules), 2)
        self.assertEqual(len(declared.role_instances), 3)
        self.assertEqual(len(declared.molecules[0].features), 2)
        removed = replace(declared, role_instances=roles[:-1])
        self.assertNotEqual(
            declared.declared_nominal_bundle_identity,
            removed.declared_nominal_bundle_identity,
        )

    def test_post_polya_extension_is_preserved_and_not_a_terminal_tail(self):
        declared = molecule(sequence="CGAAAAUC", coding_status="noncoding")
        features = (
            MoleculeFeature(
                "internal_A",
                "internal_polyA",
                path(declared.space, 2, 6),
                provenance("internalA"),
            ),
            MoleculeFeature(
                "extension",
                "post_polyA_extension",
                path(declared.space, 6, 8),
                provenance("extension"),
            ),
        )
        declared = replace(declared, features=features)
        restored = CircuitMolecule.from_json(declared.to_json())
        self.assertEqual(restored.sequence, "CGAAAAUC")
        self.assertEqual(restored.chemistry.terminal_tail.placement, "absent")
        false_tail = TailDeclaration(
            "declared",
            "represented_terminal",
            TailLength("exact", exact=4),
            path(declared.space, 2, 6),
            provenance("false_tail"),
        )
        with self.assertRaises(SerializationError):
            replace(
                declared,
                chemistry=replace(declared.chemistry, terminal_tail=false_tail),
            )

    def test_circle_preserves_origin_and_has_separate_base_rotation_identity(self):
        first = molecule(
            "circle_a", "AACCGU", topology="circular", coding_status="noncoding"
        )
        second = molecule(
            "circle_b", "CGUAAC", topology="circular", coding_status="noncoding"
        )
        crossing = CoordinatePath(
            first.space.id, (IndexSpan(4, 6), IndexSpan(0, 2)), "+"
        )
        first = replace(
            first,
            features=(
                MoleculeFeature(
                    "cross_origin",
                    "regulatory_feature",
                    crossing,
                    provenance("crossing"),
                ),
            ),
        )
        self.assertEqual(crossing.positions(first.space), (4, 5, 0, 1))
        self.assertNotEqual(first.spelling_identity, second.spelling_identity)
        self.assertNotEqual(
            first.declared_nominal_identity, second.declared_nominal_identity
        )
        self.assertEqual(first.base_rotation_identity, second.base_rotation_identity)
        self.assertEqual(CircuitMolecule.from_json(first.to_json()).sequence, "AACCGU")
        valid = bundle((first,), request=form_request("circular_rna"))
        self.assertEqual(valid.molecules[0].form, "delivered_rna")
        with self.assertRaises(SerializationError):
            bundle(
                (molecule("linear", "AACCGU"),), request=form_request("circular_rna")
            )

    def test_base_cap_modification_and_tail_have_distinct_identity_effects(self):
        original = molecule(sequence="ACGUAA")
        changed_base = molecule(sequence="ACGCAA")
        self.assertNotEqual(original.spelling_identity, changed_base.spelling_identity)
        cap = ChemistryClaim("declared", chemical("fixture_cap"), provenance("cap"))
        capped = replace(original, chemistry=replace(original.chemistry, cap=cap))
        self.assertEqual(original.spelling_identity, capped.spelling_identity)
        self.assertNotEqual(
            original.declared_nominal_identity, capped.declared_nominal_identity
        )
        modified = []
        for name in ("pseudouridine", "n1_methylpseudouridine"):
            modification = BaseModification(
                "site", chemical(name), "U", "positions", (3,), provenance(name)
            )
            modified.append(
                replace(
                    original,
                    chemistry=replace(
                        original.chemistry, modifications=(modification,)
                    ),
                )
            )
        self.assertEqual(modified[0].spelling_identity, modified[1].spelling_identity)
        self.assertNotEqual(
            modified[0].declared_nominal_identity, modified[1].declared_nominal_identity
        )
        tails = []
        for count in (1, 2):
            tail = TailDeclaration(
                "declared",
                "represented_terminal",
                TailLength("exact", exact=count),
                path(original.space, 6 - count, 6),
                provenance("tail"),
            )
            tails.append(
                replace(
                    original, chemistry=replace(original.chemistry, terminal_tail=tail)
                )
            )
        self.assertEqual(tails[0].spelling_identity, tails[1].spelling_identity)
        # Reannotating which already-represented terminal adenines are called
        # tail does not change the covalent species, but exact source authority
        # still retains the declared boundary.
        self.assertEqual(
            tails[0].declared_nominal_identity, tails[1].declared_nominal_identity
        )
        self.assertNotEqual(tails[0].fingerprint, tails[1].fingerprint)
        added_base = molecule(sequence="ACGUAAA")
        self.assertNotEqual(original.spelling_identity, added_base.spelling_identity)
        self.assertNotEqual(
            original.declared_nominal_identity, added_base.declared_nominal_identity
        )

    def test_inosine_is_not_a_canonical_guanosine_substitution(self):
        original = molecule(sequence="AACU", form="edited_rna")
        modification = BaseModification(
            "edited_site",
            chemical("inosine"),
            "A",
            "positions",
            (0,),
            provenance("inosine"),
        )
        inosine = replace(
            original,
            chemistry=replace(original.chemistry, modifications=(modification,)),
        )
        guanosine = molecule(sequence="GACU", form="edited_rna")
        self.assertEqual(inosine.sequence, "AACU")
        self.assertEqual(inosine.spelling_identity, original.spelling_identity)
        self.assertNotEqual(
            inosine.declared_nominal_identity, guanosine.declared_nominal_identity
        )

    def test_unknown_chemistry_and_inexact_tail_do_not_gain_complete_identity(self):
        original = molecule()
        unknown = ChemistryClaim("unknown", None, provenance("unknown_cap"))
        uncertain = replace(
            original, chemistry=replace(original.chemistry, cap=unknown)
        )
        self.assertFalse(uncertain.declared_nominal_complete)
        self.assertIsNone(uncertain.complete_nominal_identity)
        tail = TailDeclaration(
            "declared",
            "appended_terminal",
            TailLength("bounded", lower=2, upper=5),
            None,
            provenance("uncertain_tail"),
        )
        core = replace(
            original,
            sequence_extent="exact_core",
            chemistry=replace(original.chemistry, terminal_tail=tail),
        )
        self.assertEqual(core.sequence, "ACGU")
        self.assertFalse(core.declared_nominal_complete)
        self.assertIsNone(core.complete_nominal_identity)
        declared = bundle((core,))
        self.assertFalse(declared.declared_nominal_complete)

    def test_unknown_function_or_provenance_is_not_unknown_chemical_composition(self):
        original = molecule(coding_status="unknown")
        self.assertTrue(original.declared_nominal_complete)
        no_source = DeclarationProvenance(
            "unknown", (), None, "No independent source authority is supplied."
        )
        changed = replace(original, provenance=no_source)
        self.assertEqual(
            original.declared_nominal_identity, changed.declared_nominal_identity
        )
        self.assertTrue(changed.declared_nominal_complete)
        self.assertNotEqual(original.fingerprint, changed.fingerprint)

    def test_complete_tail_species_identity_ignores_coordinate_labels(self):
        first = molecule("first", "CGAAA")
        second = molecule("second", "CGAAA")
        tailed = []
        for item in (first, second):
            tail = TailDeclaration(
                "declared",
                "represented_terminal",
                TailLength("exact", exact=3),
                path(item.space, 2, 5),
                provenance("tail"),
            )
            tailed.append(
                replace(item, chemistry=replace(item.chemistry, terminal_tail=tail))
            )
        self.assertEqual(
            tailed[0].declared_nominal_identity, tailed[1].declared_nominal_identity
        )
        self.assertNotEqual(tailed[0].fingerprint, tailed[1].fingerprint)

    def test_alphabet_is_part_of_identity_even_when_letters_are_shared(self):
        rna = molecule("rna", "ACG")
        dna = molecule(
            "dna",
            "ACG",
            alphabet="DNA",
            form="delivered_dna",
            coding_status="unknown",
        )
        self.assertNotEqual(rna.spelling_identity, dna.spelling_identity)
        self.assertNotEqual(
            rna.declared_nominal_identity, dna.declared_nominal_identity
        )

    def test_form_changes_archival_authority_without_rewriting_physical_species(self):
        delivered = molecule()
        primary = replace(delivered, form="primary_rna")
        self.assertEqual(
            delivered.declared_nominal_identity, primary.declared_nominal_identity
        )
        self.assertNotEqual(delivered.fingerprint, primary.fingerprint)
        with self.assertRaises(SerializationError):
            bundle((primary,))

    def test_every_requested_payload_must_match_form_and_helpers_do_not_substitute(
        self,
    ):
        rna = molecule("rna")
        template = molecule("template", form="primary_rna")
        with self.assertRaises(SerializationError):
            bundle((rna, template), roles=(role(rna), role(template, "wrong_payload")))
        with self.assertRaises(SerializationError):
            bundle((rna,), roles=(role(rna, "only_helper", "helper"),))
        with self.assertRaises(SerializationError):
            bundle((rna,), roles=(role(rna, "only_control", "assay_control"),))

    def test_stale_subject_pins_and_duplicate_coordinate_spaces_reject(self):
        first = molecule("first")
        second = molecule("second")
        with self.assertRaises(SerializationError):
            bundle(
                (first,), roles=(replace(role(first), subject_fingerprint="b" * 64),)
            )
        with self.assertRaises(SerializationError):
            bundle((first, replace(second, space=first.space)))

    def test_declared_form_mapping_preserves_geometry_without_transform_proof(self):
        primary = molecule("primary", "ACGUAC", form="primary_rna")
        delivered = molecule("delivered", "UGA")
        mapping = FormCoordinateMapping(
            "declared_processing",
            primary.id,
            primary.fingerprint,
            delivered.id,
            delivered.fingerprint,
            path(primary.space, 1, 5),
            path(delivered.space),
            "rna_processing",
            provenance("mapping"),
        )
        declared = bundle(
            (primary, delivered),
            roles=(role(delivered), role(primary, "precursor", "helper")),
            mappings=(mapping,),
        )
        restored = CircuitMoleculeSet.from_json(declared.to_json())
        self.assertEqual(restored.form_mappings[0].source_path.length, 4)
        self.assertEqual(restored.form_mappings[0].destination_path.length, 3)
        self.assertEqual(
            {item.id: item.sequence for item in restored.molecules},
            {"primary": "ACGUAC", "delivered": "UGA"},
        )
        with self.assertRaises(SerializationError):
            replace(
                declared,
                form_mappings=(replace(mapping, source_molecule_fingerprint="b" * 64),),
            )
        with self.assertRaises(SerializationError):
            replace(
                declared,
                form_mappings=(replace(mapping, destination_path=path(primary.space)),),
            )

    def test_non_covalent_complex_retains_members_and_stoichiometry(self):
        payload = molecule()
        first = molecule(
            "peptide_a",
            "ACD",
            alphabet="protein",
            form="protein_precursor",
            coding_status="inapplicable",
        )
        second = molecule(
            "peptide_b",
            "EFG",
            alphabet="protein",
            form="mature_protein",
            coding_status="inapplicable",
        )
        complex_record = MolecularComplex(
            "complex",
            "protein_complex",
            (
                ComplexConstituent(first.id, first.fingerprint, 1, provenance("first")),
                ComplexConstituent(
                    second.id, second.fingerprint, 2, provenance("second")
                ),
            ),
            provenance("complex"),
        )
        declared = bundle((payload, first, second), complexes=(complex_record,))
        self.assertNotIn("sequence", complex_record.to_dict())
        self.assertEqual(
            tuple(item.stoichiometry for item in complex_record.constituents), (1, 2)
        )
        self.assertTrue(declared.subject_complete(complex_record.id))
        unknown = replace(
            complex_record,
            constituents=(
                replace(complex_record.constituents[0], stoichiometry=None),
                complex_record.constituents[1],
            ),
        )
        uncertain = bundle((payload, first, second), complexes=(unknown,))
        self.assertFalse(uncertain.subject_complete(unknown.id))
        self.assertFalse(uncertain.declared_nominal_complete)

    def test_dna_duplex_records_both_strands_without_inferred_complement(self):
        # Identical literal strands intentionally supply no complementarity proof.
        first = molecule(
            "strand_a",
            "AAC",
            alphabet="DNA",
            form="delivered_dna",
            coding_status="unknown",
        )
        second = molecule(
            "strand_b",
            "AAC",
            alphabet="DNA",
            form="delivered_dna",
            coding_status="unknown",
        )
        duplex = MolecularComplex(
            "duplex",
            "dna_duplex",
            (
                ComplexConstituent(
                    first.id, first.fingerprint, 1, provenance("strand_a")
                ),
                ComplexConstituent(
                    second.id, second.fingerprint, 1, provenance("strand_b")
                ),
            ),
            provenance("duplex"),
        )
        declared = bundle(
            (first, second),
            request=form_request("delivered_dna"),
            complexes=(duplex,),
            roles=(role(duplex),),
        )
        self.assertEqual(len(declared.molecules), 2)
        self.assertEqual(
            first.declared_nominal_identity, second.declared_nominal_identity
        )
        self.assertEqual(
            tuple(item.sequence for item in declared.molecules), ("AAC", "AAC")
        )
        with self.assertRaises(SerializationError):
            wrong = replace(
                duplex,
                constituents=(
                    replace(duplex.constituents[0], stoichiometry=2),
                    duplex.constituents[1],
                ),
            )
            bundle(
                (first, second),
                request=form_request("delivered_dna"),
                complexes=(wrong,),
                roles=(role(wrong),),
            )

    def test_single_copy_complex_cannot_create_a_second_species_amount(self):
        subject = molecule()
        constituent = ComplexConstituent(
            subject.id, subject.fingerprint, 1, provenance("constituent")
        )
        # Reject the alias before it can receive a second amount for the same
        # preparation. A wrapper does not add another covalent strand.
        for kind in ("rna_complex", "protein_complex"):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(SerializationError, "single-copy"):
                    MolecularComplex(
                        "monomer_alias", kind, (constituent,), provenance("complex")
                    )

        homomer = MolecularComplex(
            "homomer",
            "rna_complex",
            (replace(constituent, stoichiometry=2),),
            provenance("complex"),
        )
        imported = homomer.to_dict()
        imported["constituents"][0]["stoichiometry"] = 1
        with self.assertRaisesRegex(SerializationError, "single-copy"):
            MolecularComplex.from_dict(imported)

    def test_two_copy_homomer_retains_distinct_species_and_preparation_amount(self):
        subject = molecule()
        homomer = MolecularComplex(
            "homomer",
            "rna_complex",
            (
                ComplexConstituent(
                    subject.id, subject.fingerprint, 2, provenance("constituent")
                ),
            ),
            provenance("complex"),
        )
        declared = bundle((subject,), complexes=(homomer,))
        self.assertTrue(declared.subject_complete(homomer.id))
        self.assertNotEqual(
            declared.subject_nominal_identity(subject.id),
            declared.subject_nominal_identity(homomer.id),
        )
        amounts = tuple(
            ExperimentalAmount(
                identity,
                member.id,
                member.fingerprint,
                "shared_preparation",
                (),
                1,
                "artificial_unit",
                provenance("amount"),
            )
            for identity, member in (("free_strand", subject), ("dimer", homomer))
        )
        record = CircuitMoleculeRecord(declared, amounts, {})
        restored = CircuitMoleculeRecord.from_json(record.to_json())
        self.assertEqual(len(restored.experimental_amounts), 2)
        self.assertEqual(restored.bundle.complexes[0].constituents[0].stoichiometry, 2)

    def test_unknown_homomer_stoichiometry_stays_unresolved(self):
        subject = molecule()
        unknown = MolecularComplex(
            "unknown_homomer",
            "rna_complex",
            (
                ComplexConstituent(
                    subject.id, subject.fingerprint, None, provenance("constituent")
                ),
            ),
            provenance("complex"),
        )
        declared = bundle((subject,), complexes=(unknown,))
        restored = CircuitMoleculeSet.from_json(declared.to_json())
        self.assertIsNone(restored.complexes[0].constituents[0].stoichiometry)
        self.assertTrue(restored.subject_complete(subject.id))
        self.assertFalse(restored.subject_complete(unknown.id))
        self.assertFalse(restored.declared_nominal_complete)

    def test_amount_and_run_identities_do_not_change_nominal_bundle(self):
        declared = bundle()
        subject = declared.molecules[0]
        amount = ExperimentalAmount(
            "amount",
            subject.id,
            subject.fingerprint,
            "preparation",
            ("payload",),
            1,
            "fixture_unit",
            provenance("amount"),
        )
        first = CircuitMoleculeRecord(declared, (amount,), {"run_id": "one"})
        next_run = replace(first, run_metadata={"run_id": "two"})
        changed_amount = replace(
            first, experimental_amounts=(replace(amount, quantity=2),)
        )
        self.assertEqual(
            first.nominal_bundle_identity, next_run.nominal_bundle_identity
        )
        self.assertEqual(
            first.experimental_specification_identity,
            next_run.experimental_specification_identity,
        )
        self.assertNotEqual(first.fingerprint, next_run.fingerprint)
        self.assertEqual(
            first.nominal_bundle_identity, changed_amount.nominal_bundle_identity
        )
        self.assertNotEqual(
            first.experimental_specification_identity,
            changed_amount.experimental_specification_identity,
        )

    def test_shared_species_roles_use_one_explicit_preparation_amount(self):
        subject = molecule()
        declared = bundle(
            (subject,), roles=(role(subject), role(subject, "helper_role", "helper"))
        )
        amount = ExperimentalAmount(
            "amount",
            subject.id,
            subject.fingerprint,
            "preparation",
            ("payload", "helper_role"),
            1,
            "fixture_unit",
            provenance("amount"),
        )
        record = CircuitMoleculeRecord(declared, (amount,), {})
        self.assertEqual(len(record.experimental_amounts), 1)
        with self.assertRaises(SerializationError):
            replace(
                record, experimental_amounts=(amount, replace(amount, id="duplicate"))
            )

    def test_source_obligation_change_affects_experimental_authority_not_species(self):
        original = CircuitMoleculeRecord(bundle(), (), {})
        data = original.bundle.request.to_dict()
        data["profile"]["source_request"]["acceptance"]["shutdown"]["controllability"][
            "limitations"
        ] = "Distinct unresolved actuator declaration."
        request = type(original.bundle.request).from_dict(data)
        changed = replace(original, bundle=replace(original.bundle, request=request))
        self.assertEqual(
            original.nominal_bundle_identity, changed.nominal_bundle_identity
        )
        self.assertNotEqual(
            original.experimental_specification_identity,
            changed.experimental_specification_identity,
        )

    def test_record_claim_promotion_and_stale_amount_pin_are_rejected(self):
        declared = bundle()
        subject = declared.molecules[0]
        amount = ExperimentalAmount(
            "amount",
            subject.id,
            subject.fingerprint,
            "preparation",
            (),
            1,
            "fixture_unit",
            provenance("amount"),
        )
        record = CircuitMoleculeRecord(declared, (amount,), {})
        for key in ("empirical_validation", "human_therapeutic_admission", "verified"):
            with self.subTest(key=key):
                data = record.to_dict()
                data[key] = "verified"
                with self.assertRaises(SerializationError):
                    CircuitMoleculeRecord.from_dict(data)
        with self.assertRaises(SerializationError):
            replace(
                record,
                experimental_amounts=(replace(amount, subject_fingerprint="b" * 64),),
            )

    def test_all_source_and_destination_coordinate_identities_are_consistent(self):
        first = molecule("first")
        # One ID cannot simultaneously identify a length4 destination and a
        # length5 source, even though the selected source span fits both.
        wrong_source = replace(first.space, length=5)
        with self.assertRaises(SerializationError):
            origin = replace(
                first.assembly[0],
                source_space=wrong_source,
                source_path=path(wrong_source, 0, 4),
            )
            bundle((replace(first, assembly=(origin,)),))
        second = molecule("second")
        shared_source = first.assembly[0].source_space
        conflicting = replace(shared_source, topology="circular")
        changed_origin = replace(
            second.assembly[0], source_space=conflicting, source_path=path(conflicting)
        )
        with self.assertRaises(SerializationError):
            bundle((first, replace(second, assembly=(changed_origin,))))

    def test_archival_aliases_do_not_change_species_inventory_but_roles_keep_multiplicity(
        self,
    ):
        first, alias = molecule("first"), molecule("alias")
        original_role = role(first, "original_label")
        original = bundle((first,), roles=(original_role,))
        renamed_role = replace(
            original, role_instances=(replace(original_role, id="new_label"),)
        )
        extra_alias = bundle((first, alias), roles=(original_role,))
        duplicated_role = replace(
            original,
            role_instances=(
                original_role,
                replace(original_role, id="second_occurrence"),
            ),
        )
        self.assertEqual(
            original.declared_nominal_bundle_identity,
            renamed_role.declared_nominal_bundle_identity,
        )
        self.assertEqual(
            original.declared_nominal_bundle_identity,
            extra_alias.declared_nominal_bundle_identity,
        )
        self.assertNotEqual(original.fingerprint, renamed_role.fingerprint)
        self.assertNotEqual(original.fingerprint, extra_alias.fingerprint)
        self.assertNotEqual(
            original.declared_nominal_bundle_identity,
            duplicated_role.declared_nominal_bundle_identity,
        )

    def test_record_aliases_cannot_duplicate_one_species_preparation_amount(self):
        first, alias = molecule("first"), molecule("alias")
        declared = bundle((first, alias))
        amount = ExperimentalAmount(
            "first_amount",
            first.id,
            first.fingerprint,
            "same_preparation",
            (),
            1,
            "fixture_unit",
            provenance("amount"),
        )
        aliased_amount = replace(
            amount,
            id="alias_amount",
            subject_id=alias.id,
            subject_fingerprint=alias.fingerprint,
        )
        with self.assertRaises(SerializationError):
            CircuitMoleculeRecord(declared, (amount, aliased_amount), {})
        separate = replace(aliased_amount, preparation_id="separate_preparation")
        self.assertEqual(
            len(
                CircuitMoleculeRecord(
                    declared, (amount, separate), {}
                ).experimental_amounts
            ),
            2,
        )

    def test_tail_reannotation_cannot_duplicate_a_species_preparation_amount(self):
        records = []
        for identity, count in (("first", 1), ("alias", 2)):
            item = molecule(identity, "CGAAA")
            tail = TailDeclaration(
                "declared",
                "represented_terminal",
                TailLength("exact", exact=count),
                path(item.space, 5 - count, 5),
                provenance("tail"),
            )
            records.append(
                replace(item, chemistry=replace(item.chemistry, terminal_tail=tail))
            )
        first, alias = records
        self.assertEqual(
            first.declared_nominal_identity, alias.declared_nominal_identity
        )
        declared = bundle(tuple(records))
        amount = ExperimentalAmount(
            "first_amount",
            first.id,
            first.fingerprint,
            "same_preparation",
            (),
            1,
            "fixture_unit",
            provenance("amount"),
        )
        duplicate = replace(
            amount,
            id="second_amount",
            subject_id=alias.id,
            subject_fingerprint=alias.fingerprint,
        )
        with self.assertRaisesRegex(SerializationError, "species/preparation"):
            CircuitMoleculeRecord(declared, (amount, duplicate), {})

    def test_unknown_amount_is_distinct_from_zero_and_invalid_values_reject(self):
        declared = bundle()
        subject = declared.molecules[0]
        amount = ExperimentalAmount(
            "amount",
            subject.id,
            subject.fingerprint,
            "preparation",
            (),
            None,
            "fixture_unit",
            provenance("amount"),
        )
        unknown = CircuitMoleculeRecord(declared, (amount,), {})
        zero = replace(unknown, experimental_amounts=(replace(amount, quantity=0),))
        self.assertIsNone(
            CircuitMoleculeRecord.from_json(unknown.to_json())
            .experimental_amounts[0]
            .quantity
        )
        self.assertNotEqual(
            unknown.experimental_specification_identity,
            zero.experimental_specification_identity,
        )
        self.assertEqual(unknown.nominal_bundle_identity, zero.nominal_bundle_identity)
        for value in (True, False, -1, float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(SerializationError):
                    replace(amount, quantity=value)

    def test_circle_requires_complete_circumference_but_can_retain_unknown_chemistry(
        self,
    ):
        circle = molecule("circle", "AACCGU", topology="circular")
        with self.assertRaises(SerializationError):
            replace(circle, sequence_extent="exact_core")
        unknown = replace(
            circle,
            chemistry=replace(
                circle.chemistry, modification_inventory_status="unknown"
            ),
        )
        self.assertEqual(unknown.sequence, "AACCGU")
        self.assertFalse(unknown.declared_nominal_complete)
        self.assertIsNone(unknown.complete_nominal_identity)

    def test_complete_modification_groupings_and_policies_share_species_identity(self):
        original = molecule(sequence="AACU")
        grouped = BaseModification(
            "group", chemical("inosine"), "A", "positions", (0, 1), provenance("group")
        )
        split = (
            replace(grouped, id="left", positions=(0,)),
            replace(grouped, id="right", positions=(1,)),
        )
        policy = replace(grouped, id="policy", scope="all_matching_bases", positions=())
        variants = tuple(
            replace(
                original, chemistry=replace(original.chemistry, modifications=records)
            )
            for records in ((grouped,), split, (policy,))
        )
        self.assertEqual(len({item.declared_nominal_identity for item in variants}), 1)
        self.assertEqual(len({item.fingerprint for item in variants}), 3)
        site_zero = replace(
            original, chemistry=replace(original.chemistry, modifications=(split[0],))
        )
        site_one = replace(
            original, chemistry=replace(original.chemistry, modifications=(split[1],))
        )
        self.assertNotEqual(
            site_zero.declared_nominal_identity, site_one.declared_nominal_identity
        )
        self.assertNotEqual(
            site_zero.declared_nominal_identity, variants[0].declared_nominal_identity
        )

    def test_exact_core_preserves_unrepresented_substitution_policy(self):
        original = molecule(sequence="AACU")
        tail = TailDeclaration(
            "declared",
            "appended_terminal",
            TailLength("bounded", lower=2, upper=5),
            None,
            provenance("tail"),
        )
        core = replace(
            original,
            sequence_extent="exact_core",
            chemistry=replace(original.chemistry, terminal_tail=tail),
        )
        explicit = BaseModification(
            "sites", chemical("inosine"), "A", "positions", (0, 1), provenance("sites")
        )
        policy = replace(
            explicit, id="policy", scope="all_matching_bases", positions=()
        )
        sites_only = replace(
            core, chemistry=replace(core.chemistry, modifications=(explicit,))
        )
        all_a = replace(
            core, chemistry=replace(core.chemistry, modifications=(policy,))
        )
        self.assertEqual(sites_only.spelling_identity, all_a.spelling_identity)
        self.assertNotEqual(
            sites_only.declared_nominal_identity, all_a.declared_nominal_identity
        )
        self.assertFalse(sites_only.declared_nominal_complete)
        self.assertFalse(all_a.declared_nominal_complete)

    def test_complete_policy_with_no_matching_sites_does_not_invent_chemistry(self):
        original = molecule(sequence="AACC")
        policy = BaseModification(
            "no_sites",
            chemical("pseudouridine"),
            "U",
            "all_matching_bases",
            (),
            provenance("policy"),
        )
        changed = replace(
            original, chemistry=replace(original.chemistry, modifications=(policy,))
        )
        self.assertEqual(
            original.declared_nominal_identity, changed.declared_nominal_identity
        )
        self.assertNotEqual(original.fingerprint, changed.fingerprint)


if __name__ == "__main__":
    unittest.main()
