"""Reference curation checks use frozen source expectations, never an emitter."""

import copy
from dataclasses import FrozenInstanceError, replace
import hashlib
from html.parser import HTMLParser
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.errors import SerializationError
from biocompiler.registry.references import (
    ReferenceManifest,
    ReferenceRecord,
    load_reference_manifest,
    normalize_sequence,
    translate_cds,
)

FIXTURE = Path(__file__).resolve().parents[1] / "data/references/fap_car/manifest.json"
SEQUENCE_HASHES = {
    "protein": "ca35f562908d00ac249b9c7b8d6694ff5dc910e0a2ed4f7ddf4346162e91fec8",
    "DNA": "04738ea1bec87847cce856152550621551af9d4f73a3e0bbeb929cb89dcbc643",
    "RNA": "90b1d6267fa865806bf73f384125d55d009207e65aac5328045ae7b8e0e4e9d6",
}


class SourceParagraphs(HTMLParser):
    """An HTML parser, separate from the original regex extraction procedure."""

    def __init__(self):
        super().__init__()
        self.paragraphs = {}
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and attrs.get("id", "").startswith("p"):
            self.current = int(attrs["id"][1:])
            self.paragraphs[self.current] = ""

    def handle_data(self, data):
        if self.current is not None:
            self.paragraphs[self.current] += data

    def handle_endtag(self, tag):
        if tag == "div":
            self.current = None


def edited_record(record, sequence):
    data = record.to_dict()
    seq, log = normalize_sequence(sequence, record.alphabet)
    data.update(
        raw_sequence_text=sequence,
        sequence=seq,
        length=len(seq),
        raw_text_sha256=hashlib.sha256(sequence.encode()).hexdigest(),
        sequence_sha256=hashlib.sha256(seq.encode()).hexdigest(),
        normalization=log,
    )
    return ReferenceRecord.from_dict(data)


def json_paths(value, path=()):
    """Every nested JSON position, including the root, for import mutations."""
    yield path
    if isinstance(value, dict):
        for key, child in value.items():
            yield from json_paths(child, path + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from json_paths(child, path + (index,))


class ReferenceTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_reference_manifest(FIXTURE)
        self.records = {r.alphabet: r for r in self.manifest.records}

    def test_frozen_independent_expected_hashes_and_translation(self):
        self.assertEqual(self.manifest.discrepancies, ())
        for alphabet, record in self.records.items():
            self.assertEqual(record.sequence_sha256, SEQUENCE_HASHES[alphabet])
            self.assertEqual(record.length, 497 if alphabet == "protein" else 1491)
        self.assertEqual(
            self.records["DNA"].sequence.replace("T", "U"), self.records["RNA"].sequence
        )
        for alphabet in ("DNA", "RNA"):
            self.assertEqual(
                translate_cds(self.records[alphabet].sequence, alphabet),
                self.records["protein"].sequence,
            )
        self.assertEqual(translate_cds("ATGGCCTAA"), "MA*")
        self.assertEqual(translate_cds("AUGGCCUAA", "RNA"), "MA*")

    def test_independent_parser_recovers_each_raw_expected_record(self):
        parser = SourceParagraphs()
        parser.feed((FIXTURE.parent / "source-excerpts.html").read_text())
        for alphabet, start, end in (
            ("protein", 77, 77),
            ("DNA", 78, 91),
            ("RNA", 93, 110),
        ):
            raw = "\n".join(parser.paragraphs[i] for i in range(start, end + 1)).split(
                " (SEQ ID"
            )[0]
            self.assertEqual(raw, self.records[alphabet].raw_sequence_text)
            independent = raw.translate(str.maketrans("", "", " \t\r\n\v\f")).upper()
            self.assertEqual(independent, self.records[alphabet].sequence)

    def test_roundtrip_and_deep_immutability(self):
        manifest = ReferenceManifest.from_json(self.manifest.to_json())
        self.assertEqual(manifest.fingerprint, self.manifest.fingerprint)
        external = manifest.to_dict()
        external["records"][0]["unknown_features"].append("changed")
        self.assertNotIn("changed", manifest.records[0].unknown_features)
        with self.assertRaises(TypeError):
            manifest.records[0].normalization["policy"] = "changed"
        with self.assertRaises(FrozenInstanceError):
            manifest.status = "accepted"
        with self.assertRaises(TypeError):
            manifest.reviews[0]["record_fingerprints"][
                manifest.records[0].reference_id
            ] = "changed"

    def test_candidate_requires_independent_review_before_promotion(self):
        candidate = replace(
            self.manifest,
            status="candidate",
            reviews=tuple(
                r for r in self.manifest.reviews if r["role"] == "extraction"
            ),
        )
        with self.assertRaisesRegex(SerializationError, "promotion"):
            candidate.record(candidate.records[0].reference_id)
        self.assertEqual(
            candidate.record(candidate.records[0].reference_id, require_accepted=False),
            candidate.records[0],
        )
        with self.assertRaisesRegex(SerializationError, "independent passing review"):
            replace(candidate, status="accepted")
        data = candidate.to_dict()
        independent = copy.deepcopy(data["reviews"][0])
        independent.update(
            reviewer="independent-test-reviewer", role="independent-review"
        )
        data["reviews"].append(independent)
        data["status"] = "accepted"
        accepted = ReferenceManifest.from_dict(data)
        self.assertEqual(
            accepted.record(accepted.records[0].reference_id), accepted.records[0]
        )

    def test_promotion_requires_distinct_extractor_and_reviewer_identities(self):
        data = self.manifest.to_dict()
        self.assertEqual(data["status"], "accepted")
        self.assertEqual(
            {review["role"] for review in data["reviews"]},
            {"extraction", "independent-review"},
        )
        self.assertEqual(len({r["reviewer"] for r in data["reviews"]}), 2)
        data["reviews"][1]["reviewer"] = data["reviews"][0]["reviewer"]
        with self.assertRaisesRegex(SerializationError, "duplicate reviewer identity"):
            ReferenceManifest.from_dict(data)

    def test_recursive_json_type_mutations_report_only_serialization_errors(self):
        """Malformed imports never leak raw Python lookup/type exceptions.

        Some substitutions are valid (for example a different provenance note).
        The invariant concerns the public failure type, not rejecting valid edits.
        """
        cases = [(ReferenceManifest.from_dict, self.manifest.to_dict())]
        cases.extend(
            (ReferenceRecord.from_dict, r.to_dict()) for r in self.manifest.records
        )
        mutations = (None, [], {}, False, True, 0, 1, "", "unexpected")
        for decode, original in cases:
            for path in json_paths(original):
                for replacement in mutations:
                    data = copy.deepcopy(original)
                    if path:
                        parent = data
                        for segment in path[:-1]:
                            parent = parent[segment]
                        parent[path[-1]] = replacement
                    else:
                        data = replacement
                    with self.subTest(
                        decoder=decode.__qualname__, path=path, replacement=replacement
                    ):
                        try:
                            decode(data)
                        except SerializationError:
                            pass
                        except Exception as error:
                            self.fail(f"Unexpected {type(error).__name__}: {error}")

    def test_synonymous_change_preserves_protein_but_invalidates_identity(self):
        original = self.records["DNA"]
        changed = edited_record(
            original, original.sequence[:3] + "GCT" + original.sequence[6:]
        )
        self.assertEqual(
            translate_cds(changed.sequence), self.records["protein"].sequence
        )
        self.assertNotEqual(changed.sequence_sha256, original.sequence_sha256)
        self.assertNotEqual(changed.fingerprint, original.fingerprint)
        with self.assertRaisesRegex(SerializationError, "stale record"):
            replace(
                self.manifest,
                records=tuple(
                    changed if r.alphabet == "DNA" else r for r in self.manifest.records
                ),
            )
        blocked = replace(
            self.manifest,
            status="blocked",
            reviews=(),
            records=tuple(
                changed if r.alphabet == "DNA" else r for r in self.manifest.records
            ),
        )
        self.assertTrue(any("DNA/RNA differ" in d for d in blocked.discrepancies))
        with self.assertRaises(SerializationError):
            replace(blocked, status="accepted")

    def test_missense_frame_and_termination_discrepancies_block_promotion(self):
        dna = self.records["DNA"]
        variants = [
            dna.sequence[:3] + "GAT" + dna.sequence[6:],
            dna.sequence[:-1],
            dna.sequence[:3] + "TAA" + dna.sequence[6:],
            dna.sequence[:-3] + "GCC",
        ]
        for sequence in variants:
            with self.subTest(sequence=sequence[:10], length=len(sequence)):
                changed = edited_record(dna, sequence)
                records = tuple(
                    changed if r.alphabet == "DNA" else r for r in self.manifest.records
                )
                blocked = replace(
                    self.manifest, records=records, reviews=(), status="blocked"
                )
                self.assertTrue(any(d.startswith("DNA") for d in blocked.discrepancies))
                with self.assertRaises(SerializationError):
                    replace(blocked, status="candidate")

    def test_wrong_alphabets_and_ocr_correction_are_rejected(self):
        for raw, alphabet in (
            ("ATGU", "DNA"),
            ("AUGT", "RNA"),
            ("ATGN", "DNA"),
            ("ATG1", "DNA"),
            ("ATG\u00a0", "DNA"),
            ("MA?*", "protein"),
            ("Mß*", "protein"),
        ):
            with self.subTest(raw=raw), self.assertRaises(SerializationError):
                normalize_sequence(raw, alphabet)
        self.assertEqual(normalize_sequence("a t\ng\t", "DNA")[0], "ATG")

    def test_strict_serialization_and_declared_scope(self):
        mutations = [
            lambda d: d.update(schema_version="future"),
            lambda d: d.update(extra=True),
            lambda d: d.update(status=[]),
            lambda d: d["records"][0].update(alphabet=[]),
            lambda d: d["records"][0].update(length=True),
            lambda d: d["records"][0].update(sequence_sha256="0" * 64),
            lambda d: d["records"][0].update(artifact_class="full_transcript"),
            lambda d: d["records"][0].update(completeness="full-payload"),
            lambda d: d["records"][0].update(orientation="reverse"),
            lambda d: d["records"][0].update(linked_reference_ids=[]),
            lambda d: d["translation"].update(frame_zero_based=True),
            lambda d: d["sources"][0].update(retrieved_on="yesterday"),
            lambda d: d["sources"][0].update(local_path="../outside"),
            lambda d: d["reviews"][0].update(source_hashes={}),
            lambda d: d["reviews"][0].update(role=[]),
        ]
        for mutate in mutations:
            data = self.manifest.to_dict()
            mutate(data)
            with (
                self.subTest(mutate=mutations.index(mutate)),
                self.assertRaises(SerializationError),
            ):
                ReferenceManifest.from_dict(data)
        with self.assertRaises(SerializationError):
            ReferenceManifest.from_json('{"version":"1","version":"2"}')
        with self.assertRaises(SerializationError):
            ReferenceManifest.from_json('{"x":NaN}')

    def test_unknown_record_and_explicit_source_discrepancy_fail_closed(self):
        with self.assertRaisesRegex(SerializationError, "Unknown reference"):
            self.manifest.record("adjacent-variant-seq4")
        blocked = replace(
            self.manifest,
            status="blocked",
            reviews=(),
            unresolved_discrepancies=(
                "Source listing and description disagree at base 42.",
            ),
        )
        self.assertIn("base 42", blocked.discrepancies[0])
        with self.assertRaisesRegex(SerializationError, "promotion"):
            blocked.record(blocked.records[0].reference_id)
        with self.assertRaisesRegex(SerializationError, "cannot be accepted"):
            replace(blocked, status="accepted")

    def test_independent_review_evidence_integrity_and_symlink_containment(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "copy"
            shutil.copytree(FIXTURE.parent, target)
            evidence = target / "independent-audit.json"
            evidence.write_text("corrupt")
            with self.assertRaisesRegex(
                SerializationError, "Review evidence hash mismatch"
            ):
                load_reference_manifest(target / "manifest.json")
            evidence.unlink()
            evidence.symlink_to(FIXTURE.parent / "independent-audit.json")
            with self.assertRaisesRegex(
                SerializationError, "escapes reference directory"
            ):
                load_reference_manifest(target / "manifest.json")

    def test_offline_relocation_file_integrity_and_manifest_locks(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "copy"
            shutil.copytree(FIXTURE.parent, target)
            with patch(
                "socket.create_connection",
                side_effect=AssertionError("network prohibited"),
            ):
                relocated = load_reference_manifest(
                    target / "manifest.json",
                    expected_fingerprint=self.manifest.fingerprint,
                )
            self.assertEqual(relocated.fingerprint, self.manifest.fingerprint)
            with self.assertRaisesRegex(SerializationError, "lock mismatch"):
                load_reference_manifest(
                    target / "manifest.json", expected_fingerprint="0" * 64
                )
            (target / "source-excerpts.html").write_text("corrupt")
            with self.assertRaisesRegex(SerializationError, "hash mismatch"):
                load_reference_manifest(target / "manifest.json")


if __name__ == "__main__":
    unittest.main()
