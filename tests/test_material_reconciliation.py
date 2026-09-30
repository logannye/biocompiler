"""Partial source reconstruction must not become complete-material authority."""

import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from biocompiler.errors import SerializationError
from tools.check_material_reconciliation import BUNDLE, ROOT, check, reconstruct


class MaterialReconciliationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "relocated-checkout"
        self.directory = self.root / BUNDLE
        shutil.copytree(ROOT / BUNDLE, self.directory)
        self.authority = self.read("authority.json")
        self.candidate = self.read("candidates.json")

    def read(self, name):
        return json.loads((self.directory / name).read_text())

    def write(self, name, value):
        (self.directory / name).write_text(json.dumps(value, indent=2) + "\n")

    def repin_authority_for_test(self, value):
        """Exercise structural rules past the stale-authority gate, not real review."""
        self.write("authority.json", value)
        review = self.read("review.json")
        review["authority_sha256"] = hashlib.sha256(
            (self.directory / "authority.json").read_bytes()
        ).hexdigest()
        self.write("review.json", review)

    def test_reconstruction_and_relocation_preserve_identity(self):
        result = check(self.root)
        self.assertEqual(result, check(ROOT))
        self.assertEqual(result["status"], "PASS_SOURCE_LITERAL_RECONSTRUCTION_ONLY")
        self.assertFalse(result["complete_reference"])
        self.assertFalse(result["human_admission"])
        rows = {row["id"]: row for row in reconstruct(self.authority, self.directory)["rows"]}
        self.assertEqual(rows["allen-gal4uas"]["length"], 250)
        self.assertEqual(rows["allen-human-il2"]["length"], 153)

    def test_candidate_mutation_fails_even_with_recomputed_sequence_hash(self):
        candidate = copy.deepcopy(self.candidate)
        row = candidate["rows"][0]
        row["sequence"] = ("A" if row["sequence"][0] != "A" else "C") + row["sequence"][1:]
        row["sequence_sha256"] = hashlib.sha256(row["sequence"].encode()).hexdigest()
        self.write("candidates.json", candidate)
        with self.assertRaisesRegex(SerializationError, "reconstructed source authority"):
            check(self.root)

    def test_candidate_source_alphabet_role_and_mouse_substitutions_fail(self):
        for field, value in (("source_id", "different-study"), ("source_sha256", "0" * 64),
                             ("alphabet", "RNA"), ("role", "coding_dna"),
                             ("id", "allen-mouse-il2"), ("scope", "complete_molecule")):
            with self.subTest(field=field):
                candidate = copy.deepcopy(self.candidate)
                candidate["rows"][0][field] = value
                self.write("candidates.json", candidate)
                with self.assertRaises(SerializationError):
                    check(self.root)

    def test_authority_inventory_and_class_constraints_are_independent_of_pin(self):
        mutations = [
            lambda a: a["rows"].pop(),
            lambda a: a["rows"].__setitem__(1, copy.deepcopy(a["rows"][0])),
            lambda a: a["rows"][0].update(id="allen-mouse-il2"),
            lambda a: a["rows"][0].update(alphabet="protein"),
            lambda a: a["rows"][0].update(role="coding_dna"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                authority = copy.deepcopy(self.authority)
                mutate(authority)
                self.repin_authority_for_test(authority)
                with self.assertRaises(SerializationError):
                    check(self.root)

    def test_empty_nonascii_and_cross_row_concatenation_are_not_repaired(self):
        raw = self.directory / "raw/allen-gal4uas.txt"
        original = raw.read_bytes()
        other = (self.directory / "raw/allen-human-il2.txt").read_bytes()
        for altered in (b"", b" \n\t", original + "\u00a0".encode(), original + other,
                        original + b"26\n", original + original):
            with self.subTest(altered=altered[-12:]):
                raw.write_bytes(altered)
                with self.assertRaises(SerializationError):
                    check(self.root)

    def test_raw_mutation_and_rehashed_candidate_still_fail_review(self):
        raw = self.directory / "raw/allen-gal4uas.txt"
        content = raw.read_text()
        raw.write_text(("A" if content[0] != "A" else "C") + content[1:])
        self.write("candidates.json", reconstruct(self.authority, self.directory))
        with self.assertRaisesRegex(SerializationError, "Reviewed raw extraction changed"):
            check(self.root)

    def test_independent_normalized_expectation_is_checked(self):
        review = self.read("review.json")
        review["expected_sequence_sha256"]["allen-human-il2"] = "0" * 64
        self.write("review.json", review)
        with self.assertRaisesRegex(SerializationError, "Independent sequence expectation"):
            check(self.root)

    def test_correction_observation_or_locator_change_invalidates_review(self):
        for field in ("correction", "observations", "locator"):
            with self.subTest(field=field):
                authority = copy.deepcopy(self.authority)
                if field == "correction":
                    authority["source"][field] = "unreviewed source correction"
                elif field == "locator":
                    authority["rows"][0][field] = "different source table"
                else:
                    authority[field] = ["human secretion rate inferred from mouse assay"]
                self.write("authority.json", authority)
                with self.assertRaisesRegex(SerializationError, "Reviewed authority changed"):
                    check(self.root)

    def test_raw_paths_cannot_escape_or_alias_reviewed_inputs(self):
        for name in ("../outside.txt", "/tmp/outside.txt", "raw/../raw/allen-gal4uas.txt",
                     "raw/allen-human-il2.txt", "raw\\allen-gal4uas.txt"):
            with self.subTest(path=name):
                authority = copy.deepcopy(self.authority)
                authority["rows"][0]["raw_path"] = name
                self.repin_authority_for_test(authority)
                with self.assertRaises(SerializationError):
                    check(self.root)

    def test_context_shape_and_promotions_fail_even_with_updated_authority_pin(self):
        mutations = [
            lambda a: a.update(observations="x"),
            lambda a: a["source"].update(correction=True),
            lambda a: a.update(limitations="partial"),
            lambda a: a["correspondence"][0].update(exact_measured_preparation="verified"),
            lambda a: a["correspondence"][0].update(complete_nucleotide_record="complete"),
            lambda a: a["correspondence"][0].update(component_ids=["allen-gal4uas"]),
            lambda a: a["observations"][0].update(numeric_observations=[1.0]),
            lambda a: a["observations"][0].update(record_kind="per_cell_secretion_rate"),
            lambda a: a["observations"][0].update(exact_construct_join="allen-hil2"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                authority = copy.deepcopy(self.authority)
                mutate(authority)
                self.repin_authority_for_test(authority)
                with self.assertRaises(SerializationError):
                    check(self.root)

    def test_file_and_directory_symlinks_are_rejected(self):
        raw = self.directory / "raw/allen-gal4uas.txt"
        real = self.root / "same-bytes.txt"
        shutil.copyfile(raw, real)
        raw.unlink()
        raw.symlink_to(real)
        with self.assertRaisesRegex(SerializationError, "symlinks"):
            check(self.root)
        raw.unlink()
        shutil.copyfile(real, raw)
        raw_directory = self.directory / "raw"
        moved = self.root / "raw-real"
        raw_directory.rename(moved)
        raw_directory.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(SerializationError, "symlinks"):
            check(self.root)

    def test_complete_claims_and_numeric_false_are_rejected(self):
        for claim in self.candidate["claims"]:
            for value in (True, 0):
                with self.subTest(claim=claim, value=value):
                    candidate = copy.deepcopy(self.candidate)
                    candidate["claims"][claim] = value
                    self.write("candidates.json", candidate)
                    with self.assertRaisesRegex(SerializationError, "cannot promote"):
                        check(self.root)

    def test_duplicate_keys_nonfinite_values_and_unreviewed_status_fail(self):
        original = (self.directory / "candidates.json").read_text()
        for text in ('{"schema":"x","schema":"y"}', '{"value":NaN}'):
            (self.directory / "candidates.json").write_text(text)
            with self.assertRaises(SerializationError):
                check(self.root)
        (self.directory / "candidates.json").write_text(original)
        review = self.read("review.json")
        review["status"] = "pending_independent_review"
        self.write("review.json", review)
        with self.assertRaisesRegex(SerializationError, "Review pending"):
            check(self.root)


if __name__ == "__main__":
    unittest.main()
