"""Artificial required-region inventories, without regulatory-function evidence."""

from dataclasses import FrozenInstanceError, replace
from functools import lru_cache
import unittest

from biocompiler.compiler.request import BuildRequest
from biocompiler.errors import SerializationError
from biocompiler.frontend.api import Therapy
from biocompiler.ir.circuit_intent import CircuitRequirement
from biocompiler.ir.circuit_molecules import (
    CircuitMoleculeSet,
    ComplexConstituent,
    MolecularComplex,
    MoleculeFeature,
    MoleculeRoleInstance,
)
from biocompiler.ir.circuit_payloads import (
    MAX_PAYLOAD_CONTRACTS,
    MAX_REQUIRED_PAYLOAD_REGIONS,
    PAYLOAD_MODALITY_CAPABILITIES,
    PAYLOAD_STRUCTURE_CLAIM,
    PayloadStructureContract,
    RequiredPayloadRegion,
)
from biocompiler.ir.circuit_profile import ImmuneRecipientIdentity
from biocompiler.ir.molecule_chemistry import (
    ChemistryClaim,
    TailDeclaration,
    TailLength,
)
from biocompiler.ir.molecule_records import DeclarationProvenance
from biocompiler.semantics.context import PayloadFormat
from biocompiler.semantics.molecule_coordinates import CoordinatePath, IndexSpan
from biocompiler.verification.circuit_payloads import check_payload_structures
from examples.circuit_intent import make_circuit_requests
from examples.circuit_molecules import fixture_provenance, make_molecule


def unknown_provenance():
    return DeclarationProvenance(
        "unknown", (), None, "No boundary source supplied for this software fixture."
    )


@lru_cache(maxsize=6)
def form_request(form):
    """Complete artificial human authority, retaining its explicit DNA/RNA target."""
    template = make_circuit_requests()["product"]
    modality = (
        PayloadFormat.DNA
        if form in {"delivered_dna", "dna_expression_template"}
        else PayloadFormat.RNA
    )
    target = replace(template.profile.target, payload_format=modality)
    therapy = Therapy("payload_region_fixture")
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
        "region_requirement",
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
        deployment_id="declared_region_deployment",
    )


def region(molecule, id, kind, spans, *, provenance=None, strand="+"):
    return MoleculeFeature(
        id,
        kind,
        CoordinatePath(
            molecule.space.id, tuple(IndexSpan(*span) for span in spans), strand
        ),
        fixture_provenance("artificial_boundary") if provenance is None else provenance,
    )


def molecule(id="payload", form="delivered_rna", topology="linear"):
    literal = (
        "ACGTAC" if form in {"delivered_dna", "dna_expression_template"} else "ACGUAC"
    )
    item = make_molecule(
        id, literal, form=form, topology=topology, coding_status="noncoding"
    )
    return replace(
        item,
        features=(
            region(item, "first", "artificial_control_region", ((0, 4),)),
            region(item, "second", "artificial_control_region", ((2, 6),)),
        ),
    )


def role(subject, id=None, purpose="requested_payload"):
    return MoleculeRoleInstance(
        id or subject.id + ".role",
        subject.id,
        subject.fingerprint,
        "declared_fixture_role",
        purpose,
        "cytoplasm",
    )


def bundle(*molecules, complexes=(), roles=None, requested_form=None):
    if not molecules:
        molecules = (molecule(),)
    return CircuitMoleculeSet(
        "artificial_payload_bundle",
        form_request(molecules[0].form if requested_form is None else requested_form),
        molecules,
        complexes,
        tuple(role(item) for item in molecules) if roles is None else roles,
        (),
    )


def contract(subject, *, provenance=None, regions=None):
    return PayloadStructureContract(
        subject.id,
        subject.form,
        subject.space.topology,
        tuple(RequiredPayloadRegion(item.id, item.kind) for item in subject.features)
        if regions is None
        else regions,
        fixture_provenance("required_regions") if provenance is None else provenance,
    )


class CircuitPayloadTests(unittest.TestCase):
    def test_strict_frozen_roundtrips_canonical_regions_and_full_authority(self):
        value = contract(molecule())
        for item in (value, value.regions[0]):
            with self.subTest(type=type(item).__name__):
                self.assertEqual(type(item).from_json(item.to_json() + "\n"), item)
                first = next(key for key in item.to_dict() if key != "schema_version")
                with self.assertRaises(FrozenInstanceError):
                    setattr(item, first, None)
                for key in item.to_dict():
                    data = item.to_dict()
                    del data[key]
                    with self.assertRaises(SerializationError):
                        type(item).from_dict(data)
                with self.assertRaises(SerializationError):
                    type(item).from_dict(item.to_dict() | {"extra": True})
        self.assertEqual(
            value.fingerprint,
            replace(value, regions=tuple(reversed(value.regions))).fingerprint,
        )
        for changed in (
            replace(value, member_id="different"),
            replace(value, form="delivered_dna"),
            replace(value, topology="circular"),
            replace(value, regions=(RequiredPayloadRegion("first", "different_kind"),)),
            replace(value, provenance=unknown_provenance()),
        ):
            self.assertNotEqual(value.fingerprint, changed.fingerprint)

    def test_contracts_are_nonempty_bounded_and_do_not_accept_template_forms(self):
        value = contract(molecule())
        for call in (
            lambda: replace(value, regions=()),
            lambda: replace(value, regions=(value.regions[0], value.regions[0])),
            lambda: replace(
                value, regions=value.regions * (MAX_REQUIRED_PAYLOAD_REGIONS + 1)
            ),
            lambda: replace(value, form="dna_expression_template"),
            lambda: replace(value, form="primary_rna"),
            lambda: replace(value, form="mature_protein"),
            lambda: replace(value, topology="unknown"),
            lambda: replace(value, provenance=None),
            lambda: RequiredPayloadRegion("", "anything"),
            lambda: RequiredPayloadRegion("feature", "bad\x7f"),
            lambda: RequiredPayloadRegion("feature", "a" * 4097),
        ):
            with self.assertRaises(SerializationError):
                call()
        entries = list(value.regions)
        snapshot = replace(value, regions=entries)
        entries.clear()
        self.assertEqual(snapshot.regions, value.regions)

    def test_modality_map_is_immutable_and_four_nominal_combinations_pass(self):
        self.assertEqual(len(PAYLOAD_MODALITY_CAPABILITIES), 4)
        self.assertEqual(
            PAYLOAD_STRUCTURE_CLAIM, "correspondence_to_declared_payload_regions"
        )
        with self.assertRaises(TypeError):
            PAYLOAD_MODALITY_CAPABILITIES["primary_rna", "linear"] = "RNA"
        for (form, topology), alphabet in PAYLOAD_MODALITY_CAPABILITIES.items():
            with self.subTest(form=form, topology=topology):
                subject = molecule(form=form, topology=topology)
                current = bundle(subject)
                before = current.request.fingerprint
                self.assertEqual(subject.space.alphabet, alphabet)
                self.assertEqual(
                    check_payload_structures((contract(subject),), bundle=current),
                    ((), ()),
                )
                self.assertEqual(current.request.fingerprint, before)
                self.assertEqual(
                    current.request.profile.target.human_target.fingerprint,
                    form_request(form).profile.target.human_target.fingerprint,
                )

    def test_overlap_reverse_and_cross_origin_paths_need_no_universal_order(self):
        circle = molecule(topology="circular")
        circle = replace(
            circle,
            features=(
                region(circle, "zeta", "invented_regulatory_label", ((5, 6), (0, 3))),
                region(
                    circle, "alpha", "invented_regulatory_label", ((1, 5),), strand="-"
                ),
            ),
        )
        expected = contract(circle)
        self.assertEqual(
            tuple(item.feature_id for item in expected.regions), ("alpha", "zeta")
        )
        self.assertEqual(
            check_payload_structures((expected,), bundle=bundle(circle)), ((), ())
        )

    def test_unknown_contract_and_feature_boundary_authority_stay_unsupported(self):
        subject = molecule()
        current = bundle(subject)
        diagnostics, unsupported = check_payload_structures(
            (contract(subject, provenance=unknown_provenance()),), bundle=current
        )
        self.assertEqual(diagnostics, ())
        self.assertIn("payload_authority_undeclared:payload", unsupported)
        changed = replace(
            subject,
            features=(
                replace(subject.features[0], provenance=unknown_provenance()),
                subject.features[1],
            ),
        )
        diagnostics, unsupported = check_payload_structures(
            (contract(changed),), bundle=bundle(changed)
        )
        self.assertEqual(diagnostics, ())
        self.assertIn(
            "payload_boundary_authority_undeclared:payload/first", unsupported
        )

    def test_missing_contracts_are_unsupported_but_extra_and_duplicates_fail(self):
        first, second = molecule("first_payload"), molecule("second_payload")
        current = bundle(first, second)
        for missing in (None, (), []):
            diagnostics, unsupported = check_payload_structures(missing, bundle=current)
            self.assertEqual(diagnostics, ())
            self.assertIn("payload_authority_missing", unsupported)
        diagnostics, unsupported = check_payload_structures(
            (contract(first),), bundle=current
        )
        self.assertEqual(diagnostics, ())
        self.assertIn("payload_authority_missing:second_payload", unsupported)
        diagnostics, _ = check_payload_structures(
            (
                contract(first),
                contract(second),
                replace(contract(first), member_id="extra"),
            ),
            bundle=current,
        )
        self.assertIn("payload_contract_extra:extra", diagnostics)
        diagnostics, _ = check_payload_structures(
            (contract(first), contract(first)), bundle=current
        )
        self.assertIn("payload_contract_inventory_invalid", diagnostics)

    def test_one_contract_per_distinct_payload_subject_not_per_role_or_helper(self):
        payload, helper = molecule(), molecule("helper")
        current = bundle(
            payload,
            helper,
            roles=(
                role(payload, "one"),
                role(payload, "two"),
                role(helper, purpose="helper"),
            ),
        )
        self.assertEqual(
            check_payload_structures((contract(payload),), bundle=current), ((), ())
        )
        diagnostics, _ = check_payload_structures(
            (contract(payload), contract(helper)), bundle=current
        )
        self.assertIn("payload_contract_extra:helper", diagnostics)

    def test_exact_form_topology_region_identity_and_kind_are_required(self):
        subject = molecule()
        current = bundle(subject)
        expected = contract(subject)
        for change, code in (
            (replace(expected, form="delivered_dna"), "payload_form_mismatch:payload"),
            (
                replace(expected, topology="circular"),
                "payload_topology_mismatch:payload",
            ),
            (
                replace(
                    expected,
                    regions=(
                        RequiredPayloadRegion("absent", "artificial_control_region"),
                    ),
                ),
                "payload_region_missing:payload/absent",
            ),
            (
                replace(
                    expected, regions=(RequiredPayloadRegion("first", "different"),)
                ),
                "payload_region_kind_mismatch:payload/first",
            ),
        ):
            diagnostics, _ = check_payload_structures((change,), bundle=current)
            self.assertIn(code, diagnostics)

    def test_unknown_empty_and_unrequired_annotation_boundaries_are_distinct(self):
        subject = molecule()
        expected = contract(subject)
        unknown = replace(
            subject,
            features=(replace(subject.features[0], path=None), subject.features[1]),
        )
        diagnostics, unsupported = check_payload_structures(
            (expected,), bundle=bundle(unknown)
        )
        self.assertEqual(diagnostics, ())
        self.assertIn("payload_region_coordinates_unknown:payload/first", unsupported)
        boundary = replace(
            subject,
            features=(
                region(subject, "first", subject.features[0].kind, ((2, 2),)),
                subject.features[1],
            ),
        )
        diagnostics, _ = check_payload_structures((expected,), bundle=bundle(boundary))
        self.assertIn("payload_region_empty:payload/first", diagnostics)
        required_second = replace(expected, regions=(expected.regions[1],))
        self.assertEqual(
            check_payload_structures((required_second,), bundle=bundle(unknown)),
            ((), ()),
        )

    def test_complete_extent_and_nominal_chemistry_are_separate_obligations(self):
        subject = molecule()
        unknown = replace(
            subject,
            chemistry=replace(
                subject.chemistry,
                cap=ChemistryClaim("unknown", None, unknown_provenance()),
            ),
        )
        diagnostics, unsupported = check_payload_structures(
            (contract(unknown),), bundle=bundle(unknown)
        )
        self.assertEqual(diagnostics, ())
        self.assertIn("payload_chemistry_incomplete:payload", unsupported)
        tail = TailDeclaration(
            "declared",
            "appended_terminal",
            TailLength("unknown"),
            None,
            unknown_provenance(),
        )
        core = replace(
            subject,
            sequence_extent="exact_core",
            chemistry=replace(subject.chemistry, terminal_tail=tail),
        )
        diagnostics, unsupported = check_payload_structures(
            (contract(core),), bundle=bundle(core)
        )
        self.assertEqual(diagnostics, ())
        self.assertIn("payload_extent_incomplete:payload", unsupported)
        self.assertIn("payload_chemistry_incomplete:payload", unsupported)

    def test_other_final_forms_remain_unsupported_and_cannot_substitute_delivered_payload(
        self,
    ):
        for form in ("dna_expression_template", "primary_rna", "processed_rna"):
            subject = molecule(form=form)
            diagnostics, unsupported = check_payload_structures(
                (), bundle=bundle(subject)
            )
            self.assertEqual(diagnostics, ())
            self.assertIn("payload_modality_unsupported:payload", unsupported)
            substituted = PayloadStructureContract(
                subject.id,
                "delivered_dna" if subject.space.alphabet == "DNA" else "delivered_rna",
                subject.space.topology,
                (RequiredPayloadRegion("first", subject.features[0].kind),),
                fixture_provenance(),
            )
            diagnostics, unsupported = check_payload_structures(
                (substituted,), bundle=bundle(subject)
            )
            self.assertIn("payload_form_mismatch:payload", diagnostics)
            self.assertIn("payload_modality_unsupported:payload", unsupported)

    def test_declared_nucleotide_complexes_require_every_covalent_component_once(self):
        for form, kind in (
            ("delivered_rna", "rna_complex"),
            ("delivered_dna", "dna_duplex"),
        ):
            first, second = molecule("one", form=form), molecule("two", form=form)
            complex_ = MolecularComplex(
                "assembly",
                kind,
                (
                    ComplexConstituent(
                        first.id, first.fingerprint, 1, fixture_provenance()
                    ),
                    ComplexConstituent(
                        second.id, second.fingerprint, 1, fixture_provenance()
                    ),
                ),
                fixture_provenance(),
            )
            current = bundle(
                first,
                second,
                complexes=(complex_,),
                roles=(role(complex_), role(first, "also_direct")),
            )
            expected = (contract(first), contract(second))
            self.assertEqual(
                check_payload_structures(expected, bundle=current), ((), ())
            )
            diagnostics, unsupported = check_payload_structures(
                expected[:1], bundle=current
            )
            self.assertEqual(diagnostics, ())
            self.assertIn("payload_authority_missing:two", unsupported)
            diagnostics, _ = check_payload_structures(
                (*expected, replace(expected[0], member_id=complex_.id)), bundle=current
            )
            self.assertIn("payload_contract_extra:assembly", diagnostics)

    def test_unknown_complex_stoichiometry_cannot_gain_strict_structure_readiness(self):
        subject = molecule()
        complex_ = MolecularComplex(
            "assembly",
            "rna_complex",
            (
                ComplexConstituent(
                    subject.id, subject.fingerprint, None, fixture_provenance()
                ),
            ),
            fixture_provenance(),
        )
        current = bundle(subject, complexes=(complex_,), roles=(role(complex_),))
        diagnostics, unsupported = check_payload_structures(
            (contract(subject),), bundle=current
        )
        self.assertEqual(diagnostics, ())
        self.assertIn(
            "payload_complex_stoichiometry_unknown:assembly/payload", unsupported
        )
        known = replace(
            complex_, constituents=(replace(complex_.constituents[0], stoichiometry=2),)
        )
        self.assertEqual(
            check_payload_structures(
                (contract(subject),),
                bundle=bundle(subject, complexes=(known,), roles=(role(known),)),
            ),
            ((), ()),
        )

    def test_protein_complex_helper_cannot_be_relabelled_as_nucleotide_payload(self):
        payload = molecule()
        protein = make_molecule("protein", "AC", form="mature_protein")
        complex_ = MolecularComplex(
            "protein_assembly",
            "protein_complex",
            (
                ComplexConstituent(
                    protein.id, protein.fingerprint, 2, fixture_provenance()
                ),
            ),
            fixture_provenance(),
        )
        current = bundle(
            payload,
            protein,
            complexes=(complex_,),
            roles=(role(payload), role(complex_, purpose="helper")),
        )
        self.assertEqual(
            check_payload_structures((contract(payload),), bundle=current),
            ((), ()),
        )
        helper = next(
            instance
            for instance in current.role_instances
            if instance.subject_id == complex_.id
        )
        object.__setattr__(helper, "purpose", "requested_payload")
        diagnostics, _ = check_payload_structures((contract(payload),), bundle=current)
        self.assertIn("payload_bundle_invalid", diagnostics)

    def test_hostile_imports_inventory_bounds_and_schema_bypass_are_rejected(self):
        subject = molecule()
        expected = contract(subject)
        data = expected.to_dict()
        data["regions"] = [data]
        with self.assertRaises(SerializationError):
            PayloadStructureContract.from_dict(data)
        for indent in (True, -1, 9, 1.5, "  "):
            with self.assertRaises(SerializationError):
                expected.to_json(indent=indent)
        for invalid in (
            (expected,) * (MAX_PAYLOAD_CONTRACTS + 1),
            (expected.to_dict(),),
            {expected.member_id: expected},
        ):
            diagnostics, _ = check_payload_structures(invalid, bundle=bundle(subject))
            self.assertIn("payload_contract_inventory_invalid", diagnostics)
        current = bundle(subject)
        object.__setattr__(
            current.molecules[0].features[0].path, "space_id", "wrong_frame"
        )
        diagnostics, _ = check_payload_structures((expected,), bundle=current)
        self.assertIn("payload_bundle_invalid", diagnostics)


if __name__ == "__main__":
    unittest.main()
