"""Source-independent artificial edit and recoding declaration regressions."""

from dataclasses import FrozenInstanceError, replace
from itertools import product
import unittest

from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_recoding import (
    MAX_RECODINGS,
    STANDARD_GENETIC_CODE,
    STANDARD_RNA_CODON_TABLE,
    CanonicalBaseEdit,
    ChemicalBaseEdit,
    CodonRecoding,
    TranslationPolicy,
)
from biocompiler.ir.molecule_chemistry import BaseModification, ChemicalIdentity
from biocompiler.ir.molecule_records import DeclarationProvenance, MAX_RESIDUES
from biocompiler.registry.references import _CODONS


def chemical(accession="inosine", namespace="biocompiler.chemical", version="1"):
    return ChemicalIdentity(namespace, accession, version)


def recoding(index=1, triplet="UGA", amino_acid="U", condition="artificial_condition"):
    return CodonRecoding(index, triplet, amino_acid, condition)


class CircuitRecodingTests(unittest.TestCase):
    def records(self):
        return (
            CanonicalBaseEdit(0, "A", "C"),
            ChemicalBaseEdit(2, "A", None, chemical()),
            ChemicalBaseEdit(2, "A", chemical(), None),
            recoding(),
            TranslationPolicy("ordinary_cds"),
            TranslationPolicy("conditional_cds", recodings=(recoding(),)),
        )

    def test_strict_frozen_versioned_roundtrips(self):
        for item in self.records():
            with self.subTest(type=type(item).__name__):
                restored = type(item).from_json(item.to_json() + "\n")
                self.assertEqual(restored, item)
                self.assertEqual(restored.fingerprint, item.fingerprint)
                first_field = next(
                    key for key in item.to_dict() if key != "schema_version"
                )
                with self.assertRaises(FrozenInstanceError):
                    setattr(item, first_field, None)
                for key in item.to_dict():
                    data = item.to_dict()
                    del data[key]
                    with self.assertRaises(SerializationError):
                        type(item).from_dict(data)
                with self.assertRaises(SerializationError):
                    type(item).from_dict(item.to_dict() | {"extra": "unknown"})
                with self.assertRaises(SerializationError):
                    type(item).from_dict(item.to_dict() | {"schema_version": "future"})

    def test_canonical_edits_retain_exact_site_and_require_real_rna_change(self):
        for position in (0, MAX_RESIDUES - 1):
            for expected, replacement in product("ACGU", repeat=2):
                if expected == replacement:
                    with self.assertRaises(SerializationError):
                        CanonicalBaseEdit(position, expected, replacement)
                else:
                    edit = CanonicalBaseEdit(position, expected, replacement)
                    self.assertEqual(edit.position, position)
                    self.assertEqual(
                        (edit.expected, edit.replacement), (expected, replacement)
                    )
        first = CanonicalBaseEdit(0, "A", "G")
        self.assertNotEqual(first.fingerprint, replace(first, position=1).fingerprint)
        self.assertNotEqual(
            first.fingerprint, replace(first, replacement="U").fingerprint
        )

    def test_indices_reject_booleans_floats_and_out_of_bounds(self):
        for invalid in (-1, True, False, 0.0, None, "1", MAX_RESIDUES, 1 << 200):
            with self.subTest(index=invalid):
                with self.assertRaises(SerializationError):
                    CanonicalBaseEdit(invalid, "A", "G")
                with self.assertRaises(SerializationError):
                    ChemicalBaseEdit(invalid, "A", None, chemical())
        for invalid in (-1, True, False, 0.0, None, "1", MAX_RESIDUES // 3, 1 << 200):
            with self.assertRaises(SerializationError):
                recoding(index=invalid)
        self.assertEqual(
            recoding(index=MAX_RESIDUES // 3 - 1).codon_index, MAX_RESIDUES // 3 - 1
        )

    def test_rna_base_fields_never_normalize_dna_ambiguity_or_inosine_symbols(self):
        for invalid in ("T", "I", "N", "a", "AU", "", " A", "A\n", None, 1, ["A"]):
            with self.subTest(symbol=invalid):
                with self.assertRaises(SerializationError):
                    CanonicalBaseEdit(0, invalid, "G")
                with self.assertRaises(SerializationError):
                    CanonicalBaseEdit(0, "A", invalid)
                with self.assertRaises(SerializationError):
                    ChemicalBaseEdit(0, invalid, None, chemical())

    def test_chemical_changes_do_not_rewrite_canonical_parent_symbols(self):
        addition = ChemicalBaseEdit(0, "A", None, chemical())
        removal = ChemicalBaseEdit(0, "A", chemical(), None)
        substitution = ChemicalBaseEdit(
            1, "U", chemical("pseudouridine"), chemical("n1_methylpseudouridine")
        )
        self.assertEqual(addition.parent, "A")
        self.assertEqual(removal.parent, "A")
        self.assertNotEqual(addition.fingerprint, removal.fingerprint)
        self.assertEqual(substitution.parent, "U")
        self.assertNotEqual(
            addition.fingerprint, CanonicalBaseEdit(0, "A", "G").fingerprint
        )
        for before, after in ((None, None), (chemical(), chemical())):
            with self.assertRaises(SerializationError):
                ChemicalBaseEdit(0, "A", before, after)
        for before, after in ((chemical().to_dict(), None), (None, "inosine")):
            with self.assertRaises(SerializationError):
                ChemicalBaseEdit(0, "A", before, after)

    def test_builtin_parent_constraints_match_r3_for_both_sides(self):
        provenance = DeclarationProvenance(
            "unknown", (), None, "Artificial schema fixture only."
        )
        for accession, required in (
            ("inosine", "A"),
            ("pseudouridine", "U"),
            ("n1_methylpseudouridine", "U"),
        ):
            for parent in "ACGU":
                for before, after in (
                    (None, chemical(accession)),
                    (chemical(accession), None),
                ):
                    with self.subTest(
                        accession=accession, parent=parent, before=before
                    ):
                        if parent == required:
                            ChemicalBaseEdit(0, parent, before, after)
                            BaseModification(
                                "fixture",
                                chemical(accession),
                                parent,
                                "positions",
                                (0,),
                                provenance,
                            )
                        else:
                            with self.assertRaises(SerializationError):
                                ChemicalBaseEdit(0, parent, before, after)
                            with self.assertRaises(SerializationError):
                                BaseModification(
                                    "fixture",
                                    chemical(accession),
                                    parent,
                                    "positions",
                                    (0,),
                                    provenance,
                                )

    def test_unrecognized_identifiers_remain_nominal_without_ontology_inference(self):
        for identity in (
            chemical("inosine", namespace="fixture.chemical"),
            chemical("inosine", version="2"),
            chemical("artificial_identifier"),
            chemical("unknown", namespace="unknown", version="unknown"),
        ):
            item = ChemicalBaseEdit(0, "C", None, identity)
            self.assertEqual(item.after, identity)
        self.assertFalse(item.after.declared_nominal_complete)

    def test_codon_declarations_require_triplets_and_explicit_residue_or_stop(self):
        for triplet in ("AUG", "UAG", "GGC"):
            for amino_acid in ("M", "U", "O", "*"):
                item = recoding(triplet=triplet, amino_acid=amino_acid)
                self.assertEqual(item.expected_triplet, triplet)
                self.assertEqual(item.amino_acid, amino_acid)
        for triplet in (
            "ATG",
            "AIG",
            "NNN",
            "aug",
            "AU",
            "AUGA",
            " AUG",
            "AUG\n",
            None,
            1,
        ):
            with self.assertRaises(SerializationError):
                recoding(triplet=triplet)
        for amino_acid in ("X", "B", "J", "Z", "m", "Met", "UO", "", None, 1):
            with self.assertRaises(SerializationError):
                recoding(amino_acid=amino_acid)

    def test_condition_is_exact_bounded_text_and_changes_authority(self):
        item = recoding()
        self.assertNotEqual(
            item.fingerprint,
            replace(item, condition="different_assumption").fingerprint,
        )
        self.assertEqual(len(recoding(condition="a" * 4096).condition), 4096)
        for invalid in (
            "",
            " ",
            " condition",
            "condition ",
            "line\nline",
            "bad\x7f",
            "a" * 4097,
            "é" * 2049,
            "\ud800",
            None,
        ):
            with self.subTest(
                invalid=repr(invalid[:20]) if isinstance(invalid, str) else invalid
            ):
                with self.assertRaises(SerializationError):
                    recoding(condition=invalid)

    def test_translation_profiles_require_explicit_conditional_inventory(self):
        ordinary = TranslationPolicy("ordinary_cds")
        self.assertEqual(ordinary.genetic_code, STANDARD_GENETIC_CODE)
        self.assertEqual(ordinary.recodings, ())
        conditional = TranslationPolicy("conditional_cds", recodings=(recoding(),))
        self.assertEqual(conditional.recodings, (recoding(),))
        for call in (
            lambda: TranslationPolicy("ordinary_cds", recodings=(recoding(),)),
            lambda: TranslationPolicy("conditional_cds"),
            lambda: TranslationPolicy("infer_cds"),
            lambda: TranslationPolicy(
                "ordinary_cds", genetic_code="ncbi_mitochondrial"
            ),
            lambda: TranslationPolicy("ordinary_cds", genetic_code=1),
            lambda: TranslationPolicy(
                "conditional_cds", recodings=(recoding().to_dict(),)
            ),
        ):
            with self.assertRaises(SerializationError):
                call()

    def test_recodings_are_unique_canonical_and_snapshotted(self):
        items = [recoding(index=3, amino_acid="O"), recoding(index=1)]
        policy = TranslationPolicy("conditional_cds", recodings=items)
        items.clear()
        self.assertEqual(tuple(item.codon_index for item in policy.recodings), (1, 3))
        reverse = replace(policy, recodings=tuple(reversed(policy.recodings)))
        self.assertEqual(policy.fingerprint, reverse.fingerprint)
        for entries in (
            (recoding(), recoding()),
            (recoding(), recoding(amino_acid="O")),
        ):
            with self.assertRaises(SerializationError):
                TranslationPolicy("conditional_cds", recodings=entries)

    def test_recoding_limit_is_enforced_before_decoding_large_inventory(self):
        items = tuple(recoding(index=index) for index in range(MAX_RECODINGS))
        policy = TranslationPolicy("conditional_cds", recodings=items)
        self.assertEqual(len(policy.recodings), MAX_RECODINGS)
        with self.assertRaises(SerializationError):
            replace(policy, recodings=(*items, recoding(index=MAX_RECODINGS)))
        data = TranslationPolicy("conditional_cds", recodings=(recoding(),)).to_dict()
        data["recodings"] *= MAX_RECODINGS + 1
        with self.assertRaises(SerializationError):
            TranslationPolicy.from_dict(data)

    def test_hostile_imports_and_indentation_are_rejected(self):
        item = TranslationPolicy("conditional_cds", recodings=(recoding(),))
        cycle = item.to_dict()
        cycle["recodings"] = [cycle]
        with self.assertRaises(SerializationError):
            TranslationPolicy.from_dict(cycle)
        for indent in (True, -1, 9, 0.0, "  "):
            with self.assertRaises(SerializationError):
                item.to_json(indent=indent)
        for value in ('{"schema_version":NaN}', item.to_json() + "x", " " * 4_000_001):
            with self.assertRaises(SerializationError):
                TranslationPolicy.from_json(value)

    def test_standard_table_is_complete_immutable_and_matches_existing_profile(self):
        self.assertEqual(
            set(STANDARD_RNA_CODON_TABLE),
            {"".join(codon) for codon in product("ACGU", repeat=3)},
        )
        self.assertEqual(
            dict(STANDARD_RNA_CODON_TABLE),
            {codon.replace("T", "U"): residue for codon, residue in _CODONS.items()},
        )
        self.assertEqual(STANDARD_RNA_CODON_TABLE["AUG"], "M")
        self.assertEqual(
            {
                codon
                for codon, residue in STANDARD_RNA_CODON_TABLE.items()
                if residue == "*"
            },
            {"UAA", "UAG", "UGA"},
        )
        self.assertNotIn("U", STANDARD_RNA_CODON_TABLE.values())
        self.assertNotIn("O", STANDARD_RNA_CODON_TABLE.values())
        with self.assertRaises(TypeError):
            STANDARD_RNA_CODON_TABLE["UGA"] = "U"


if __name__ == "__main__":
    unittest.main()
