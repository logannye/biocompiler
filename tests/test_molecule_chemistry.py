"""Artificial chemistry declarations preserve exact nominal meaning and unknowns."""

from dataclasses import FrozenInstanceError, replace
import unittest

from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.molecule_chemistry import (
    MAX_MODIFICATIONS,
    MAX_MODIFICATION_POSITIONS,
    BaseModification,
    ChemicalIdentity,
    ChemistryClaim,
    MoleculeChemistry,
    TailDeclaration,
    TailLength,
)
from biocompiler.ir.molecule_records import DeclarationProvenance, MAX_RESIDUES
from biocompiler.ir.serialization import fingerprint
from biocompiler.semantics.molecule_coordinates import (
    CoordinatePath,
    CoordinateSpace,
    IndexSpan,
)


def unknown_provenance():
    return DeclarationProvenance(
        "unknown", (), None, "Artificial fixture; no source supplied."
    )


def declared_provenance():
    return DeclarationProvenance(
        "declared",
        (PinnedIdentity("source", "software-fixture", "1", "a" * 64),),
        "fixture:chemistry",
        "Artificial software declaration; no experiment.",
    )


def chemical(accession):
    return ChemicalIdentity("biocompiler.chemical", accession, "1")


def claim(status="declared", accession="hydroxyl"):
    return ChemistryClaim(
        status,
        chemical(accession) if status == "declared" else None,
        unknown_provenance(),
    )


def no_tail(status="declared"):
    return TailDeclaration(
        status,
        "absent" if status == "declared" else None,
        TailLength("exact", exact=0) if status == "declared" else None,
        None,
        unknown_provenance(),
    )


def chemistry(**changes):
    values = dict(
        cap=claim("absent"),
        start_end=claim(),
        finish_end=claim(),
        modifications=(),
        modification_inventory_status="declared",
        modification_inventory_provenance=unknown_provenance(),
        terminal_tail=no_tail(),
    )
    values.update(changes)
    return MoleculeChemistry(**values)


def space(sequence="ACGUAAA", alphabet="RNA", topology="linear", id="molecule-space"):
    return CoordinateSpace(
        id,
        alphabet,
        len(sequence),
        topology,
        "N_to_C" if alphabet == "protein" else "5prime_to_3prime",
    )


def modification(
    id="mod", accession="inosine", base="A", scope="positions", positions=(0,)
):
    return BaseModification(
        id, chemical(accession), base, scope, positions, unknown_provenance()
    )


def exact_tail(coordinate_space=None):
    coordinate_space = space() if coordinate_space is None else coordinate_space
    return TailDeclaration(
        "declared",
        "represented_terminal",
        TailLength("exact", exact=3),
        CoordinatePath(coordinate_space.id, (IndexSpan(4, 7),), "+"),
        unknown_provenance(),
    )


class MoleculeChemistryTests(unittest.TestCase):
    def records(self):
        return (
            chemical("inosine"),
            claim(),
            modification(),
            TailLength("exact", exact=3),
            exact_tail(),
            chemistry(terminal_tail=exact_tail(), modifications=(modification(),)),
        )

    def test_strict_frozen_roundtrips_preserve_all_claims(self):
        for original in self.records():
            with self.subTest(kind=type(original).__name__):
                restored = type(original).from_json(original.to_json() + "\n")
                self.assertEqual(restored, original)
                self.assertEqual(restored.fingerprint, original.fingerprint)
                self.assertEqual(restored.nominal_dict(), original.nominal_dict())
                field = next(
                    key for key in original.to_dict() if key != "schema_version"
                )
                with self.assertRaises(FrozenInstanceError):
                    setattr(original, field, None)
                for removed in original.to_dict():
                    data = original.to_dict()
                    del data[removed]
                    with self.assertRaises(SerializationError):
                        type(original).from_dict(data)
                with self.assertRaises(SerializationError):
                    type(original).from_dict(original.to_dict() | {"extra": True})

    def test_complete_nominal_chemistry_does_not_require_invented_provenance(self):
        item = chemistry()
        item.validate_for(space(), "ACGUAAA", "complete")
        self.assertTrue(item.declared_nominal_complete)
        self.assertEqual(item.modification_inventory_provenance.status, "unknown")
        changed = replace(
            item,
            modification_inventory_provenance=declared_provenance(),
            cap=replace(item.cap, provenance=declared_provenance()),
        )
        self.assertNotEqual(item.fingerprint, changed.fingerprint)
        self.assertEqual(item.nominal_dict(), changed.nominal_dict())
        self.assertTrue(changed.declared_nominal_complete)

    def test_unknown_chemistry_and_inventory_are_not_complete(self):
        item = chemistry()
        cases = (
            replace(item, cap=claim("unknown")),
            replace(item, start_end=claim("unknown")),
            replace(item, finish_end=claim("unknown")),
            replace(item, terminal_tail=no_tail("unknown")),
            replace(item, modification_inventory_status="unknown"),
            replace(
                item,
                start_end=replace(
                    claim(), identity=replace(chemical("hydroxyl"), version="unknown")
                ),
            ),
        )
        for changed in cases:
            with self.subTest(changed=changed):
                changed.validate_for(space(), "ACGUAAA", "complete")
                self.assertFalse(changed.declared_nominal_complete)
                self.assertNotEqual(item.nominal_dict(), changed.nominal_dict())

    def test_unknown_inventory_can_preserve_known_modification_declarations(self):
        item = chemistry(
            modifications=(modification(),), modification_inventory_status="unknown"
        )
        item.validate_for(space(), "ACGUAAA", "complete")
        self.assertFalse(item.declared_nominal_complete)
        self.assertEqual(len(item.modifications), 1)

    def test_absent_unknown_and_inapplicable_caps_are_distinct(self):
        identities = {
            fingerprint(claim(status).nominal_dict())
            for status in ("absent", "unknown", "inapplicable")
        }
        self.assertEqual(len(identities), 3)
        with self.assertRaises(SerializationError):
            chemistry(cap=claim("inapplicable")).validate_for(
                space(), "ACGUAAA", "complete"
            )
        for status in ("absent", "inapplicable"):
            for end in ("start_end", "finish_end"):
                with self.assertRaises(SerializationError):
                    chemistry(**{end: claim(status)}).validate_for(
                        space(), "ACGUAAA", "complete"
                    )

    def test_circular_molecules_require_inapplicable_free_ends_cap_and_tail(self):
        circle = space(topology="circular")
        item = chemistry(
            cap=claim("inapplicable"),
            start_end=claim("inapplicable"),
            finish_end=claim("inapplicable"),
            terminal_tail=no_tail("inapplicable"),
        )
        item.validate_for(circle, "ACGUAAA", "complete")
        self.assertTrue(item.declared_nominal_complete)
        for field in ("cap", "start_end", "finish_end"):
            with self.assertRaises(SerializationError):
                replace(item, **{field: claim("unknown")}).validate_for(
                    circle, "ACGUAAA", "complete"
                )
        with self.assertRaises(SerializationError):
            replace(item, terminal_tail=no_tail()).validate_for(
                circle, "ACGUAAA", "complete"
            )

    def test_dna_and_protein_caps_and_rna_tails_are_inapplicable(self):
        item = chemistry(
            cap=claim("inapplicable"), terminal_tail=no_tail("inapplicable")
        )
        for sequence, alphabet in (("ACGT", "DNA"), ("MAG", "protein")):
            frame = space(sequence, alphabet)
            item.validate_for(frame, sequence, "complete")
            with self.assertRaises(SerializationError):
                replace(item, cap=claim("absent")).validate_for(
                    frame, sequence, "complete"
                )
            with self.assertRaises(SerializationError):
                replace(item, terminal_tail=no_tail()).validate_for(
                    frame, sequence, "complete"
                )
        with self.assertRaises(SerializationError):
            replace(item, modifications=(modification(),)).validate_for(
                space("MAG", "protein"), "MAG", "complete"
            )
        with self.assertRaises(SerializationError):
            replace(item, modification_inventory_status="inapplicable").validate_for(
                space("ACGT", "DNA"), "ACGT", "complete"
            )

    def test_builtin_parent_rules_and_distinct_uridine_modifications(self):
        for accession, expected in (
            ("inosine", "A"),
            ("pseudouridine", "U"),
            ("n1_methylpseudouridine", "U"),
        ):
            with self.assertRaisesRegex(SerializationError, "parent base"):
                modification(accession=accession, base="G")
            self.assertEqual(
                modification(accession=accession, base=expected).canonical_base,
                expected,
            )
        psi = chemistry(
            modifications=(
                modification(accession="pseudouridine", base="U", positions=(3,)),
            )
        )
        methyl = chemistry(
            modifications=(
                modification(
                    accession="n1_methylpseudouridine", base="U", positions=(3,)
                ),
            )
        )
        for item in (psi, methyl):
            item.validate_for(space(), "ACGUAAA", "complete")
        self.assertNotEqual(psi.nominal_dict(), methyl.nominal_dict())

    def test_protein_named_residues_u_and_o_are_literal_without_translation_inference(
        self,
    ):
        item = chemistry(
            cap=claim("inapplicable"), terminal_tail=no_tail("inapplicable")
        )
        sequence = "MUO"
        item.validate_for(space(sequence, "protein"), sequence, "complete")
        self.assertEqual(sequence, "MUO")
        for unsupported in ("MBZ", "MXX", "M**"):
            with self.assertRaises(SerializationError):
                item.validate_for(
                    space(unsupported, "protein"), unsupported, "complete"
                )

    def test_inosine_preserves_canonical_a_and_never_substitutes_i_or_g(self):
        sequence = "ACGUAAA"
        item = chemistry(modifications=(modification(),))
        item.validate_for(space(), sequence, "complete")
        self.assertEqual(sequence, "ACGUAAA")
        for altered in ("ICGUAAA", "GCGUAAA"):
            with self.assertRaises(SerializationError):
                item.validate_for(space(altered), altered, "complete")
        self.assertNotEqual(item.nominal_dict(), chemistry().nominal_dict())

    def test_nonbuiltin_identity_is_preserved_without_name_based_inference(self):
        item = modification(base="G", positions=(2,), accession="custom-label")
        changed = replace(
            item, identity=ChemicalIdentity("custom.software", "inosine", "v2")
        )
        chemistry(modifications=(changed,)).validate_for(space(), "ACGUAAA", "complete")
        self.assertEqual(changed.identity.namespace, "custom.software")
        self.assertEqual(changed.canonical_base, "G")

    def test_positions_are_sorted_bounded_and_parent_checked(self):
        item = modification(positions=[6, 0, 4])
        self.assertEqual(item.positions, (0, 4, 6))
        chemistry(modifications=(item,)).validate_for(space(), "ACGUAAA", "complete")
        for positions in (
            (0, 0),
            (-1,),
            (True,),
            (1.5,),
            (),
            (MAX_RESIDUES,),
            tuple(range(MAX_MODIFICATION_POSITIONS + 1)),
        ):
            with self.assertRaises(SerializationError):
                modification(positions=positions)
        for positions in ((7,), (1,)):
            with self.assertRaises(SerializationError):
                chemistry(
                    modifications=(modification(positions=positions),)
                ).validate_for(space(), "ACGUAAA", "complete")

    def test_all_matching_policy_remains_distinct_from_exact_positions(self):
        policy = modification(scope="all_matching_bases", positions=())
        explicit = modification(positions=(0, 4, 5, 6))
        for item in (policy, explicit):
            chemistry(modifications=(item,)).validate_for(
                space(), "ACGUAAA", "complete"
            )
        self.assertNotEqual(policy.nominal_dict(), explicit.nominal_dict())
        with self.assertRaises(SerializationError):
            modification(scope="all_matching_bases", positions=(0,))

    def test_conflicting_modification_scopes_are_rejected(self):
        pairs = (
            (modification("a"), modification("b")),
            (
                modification("a", scope="all_matching_bases", positions=()),
                modification("b"),
            ),
            (
                modification("b", scope="all_matching_bases", positions=()),
                modification("a"),
            ),
            (
                modification("a", scope="all_matching_bases", positions=()),
                modification("b", scope="all_matching_bases", positions=()),
            ),
        )
        for pair in pairs:
            with self.assertRaisesRegex(SerializationError, "overlap"):
                chemistry(modifications=pair).validate_for(
                    space(), "ACGUAAA", "complete"
                )
        with self.assertRaises(SerializationError):
            chemistry(modifications=(modification(), modification()))

    def test_modification_occurrence_ids_and_provenance_do_not_change_nominal_identity(
        self,
    ):
        original = modification()
        changed = replace(original, id="renamed", provenance=declared_provenance())
        self.assertNotEqual(original.fingerprint, changed.fingerprint)
        self.assertEqual(original.nominal_dict(), changed.nominal_dict())
        self.assertEqual(
            chemistry(modifications=(original,)).nominal_dict(),
            chemistry(modifications=(changed,)).nominal_dict(),
        )

    def test_exact_tail_requires_literal_forward_terminal_adenines(self):
        item = chemistry(terminal_tail=exact_tail())
        item.validate_for(space(), "ACGUAAA", "complete")
        self.assertTrue(item.declared_nominal_complete)
        for path in (
            CoordinatePath(space().id, (IndexSpan(4, 7),), "-"),
            CoordinatePath(space().id, (IndexSpan(0, 3),), "+"),
            CoordinatePath(space().id, (IndexSpan(4, 5), IndexSpan(5, 7)), "+"),
            CoordinatePath("other-space", (IndexSpan(4, 7),), "+"),
        ):
            with self.assertRaises(SerializationError):
                replace(
                    item, terminal_tail=replace(item.terminal_tail, path=path)
                ).validate_for(space(), "ACGUAAA", "complete")
        for sequence in ("ACGUAAG", "ACGUAAU"):
            with self.assertRaisesRegex(SerializationError, "adenines"):
                item.validate_for(space(), sequence, "complete")
        with self.assertRaises(SerializationError):
            replace(
                item,
                terminal_tail=replace(
                    item.terminal_tail, length=TailLength("exact", exact=2)
                ),
            ).validate_for(space(), "ACGUAAA", "complete")

    def test_nominal_tail_coordinates_exclude_only_space_labels(self):
        original = exact_tail()
        changed = replace(
            original,
            path=replace(original.path, space_id="renamed"),
            provenance=declared_provenance(),
        )
        self.assertNotEqual(original.fingerprint, changed.fingerprint)
        self.assertEqual(original.nominal_dict(), changed.nominal_dict())
        shifted = replace(
            original, path=replace(original.path, spans=(IndexSpan(3, 6),))
        )
        self.assertNotEqual(original.nominal_dict(), shifted.nominal_dict())

    def test_uncertain_appended_tail_requires_exact_core_without_invented_bases(self):
        sequence = "ACGU"
        for length in (TailLength("bounded", lower=1, upper=8), TailLength("unknown")):
            tail = TailDeclaration(
                "declared", "appended_terminal", length, None, unknown_provenance()
            )
            item = chemistry(terminal_tail=tail)
            item.validate_for(space(sequence), sequence, "exact_core")
            self.assertEqual(sequence, "ACGU")
            self.assertFalse(item.declared_nominal_complete)
            with self.assertRaises(SerializationError):
                item.validate_for(space(sequence), sequence, "complete")
        with self.assertRaises(SerializationError):
            chemistry().validate_for(space(sequence), sequence, "exact_core")

    def test_internal_poly_a_with_extension_is_not_a_terminal_tail(self):
        sequence = "CAAAUG"
        chemistry().validate_for(space(sequence), sequence, "complete")
        nonterminal = TailDeclaration(
            "declared",
            "represented_terminal",
            TailLength("exact", exact=3),
            CoordinatePath(space().id, (IndexSpan(1, 4),), "+"),
            unknown_provenance(),
        )
        with self.assertRaises(SerializationError):
            chemistry(terminal_tail=nonterminal).validate_for(
                space(sequence), sequence, "complete"
            )

    def test_tail_length_and_statuses_cannot_invent_or_mix_knowledge(self):
        for values in (
            dict(mode="exact", exact=-1),
            dict(mode="exact", exact=True),
            dict(mode="exact", exact=1, lower=0),
            dict(mode="bounded", lower=2, upper=2),
            dict(mode="bounded", lower=1, upper=2, exact=1),
            dict(mode="unknown", lower=0),
            dict(mode="exact", exact=MAX_RESIDUES + 1),
        ):
            with self.assertRaises(SerializationError):
                TailLength(**values)
        for tail in (no_tail("unknown"), no_tail("inapplicable")):
            with self.assertRaises(SerializationError):
                replace(tail, length=TailLength("unknown"))
        with self.assertRaises(SerializationError):
            replace(no_tail(), path=exact_tail().path)
        with self.assertRaises(SerializationError):
            replace(exact_tail(), placement="appended_terminal", path=None)

    def test_bounded_inventory_and_strict_json_reject_hostile_values(self):
        with self.assertRaises(SerializationError):
            chemistry(modifications=[modification()] * (MAX_MODIFICATIONS + 1))
        for record in self.records():
            for text in (
                "NaN",
                "Infinity",
                "{",
                record.to_json()[:-1] + ', "schema_version": "duplicate"}',
            ):
                with self.assertRaises(SerializationError):
                    type(record).from_json(text)
        for status in ([], None, "known", True):
            with self.assertRaises(SerializationError):
                claim(status)
        for value in ("I", "ACGTAAA", "ACGUAA", "acguaaa"):
            with self.assertRaises(SerializationError):
                chemistry().validate_for(space(), value, "complete")


if __name__ == "__main__":
    unittest.main()
