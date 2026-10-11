"""Pure source-record controls; synthetic XML never establishes authenticity.

The complete original WIPO XML is deliberately not vendored. Its positive CLI
check is run separately against supplied original bytes. These tests exercise
the independent content pins and hostile parser inputs without network access.
"""

from __future__ import annotations

import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from tools import check_car_rm61461_reference as reference


ROOT = Path(__file__).resolve().parents[1]
PACK_PATH = ROOT / "src/biocompiler/policy/data/car_rm61461_reference_v01.json"


def synthetic_xml(rows: list[tuple[int, str, str]], *, declaration: str = "") -> bytes:
    entries = []
    for identity, moltype, literal in rows:
        length = "" if moltype == "omitted" else str(len(literal))
        kind = "" if moltype == "omitted" else moltype
        entries.append(
            f'<SequenceData sequenceIDNumber="{identity}"><INSDSeq>'
            f'<INSDSeq_length>{length}</INSDSeq_length>'
            f'<INSDSeq_moltype>{kind}</INSDSeq_moltype>'
            f'<INSDSeq_sequence>{literal}</INSDSeq_sequence>'
            '</INSDSeq></SequenceData>'
        )
    return (declaration + '<ST26SequenceListing><SequenceTotalQuantity>' + str(len(rows))
            + '</SequenceTotalQuantity>' + ''.join(entries)
            + '</ST26SequenceListing>').encode("utf-8")


def scalar_paths(value, prefix=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from scalar_paths(child, prefix + (key,))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from scalar_paths(child, prefix + (index,))
    else:
        yield prefix, value


class CARReferenceTests(unittest.TestCase):
    def setUp(self):
        self.pack = reference.load_pack(PACK_PATH.read_bytes())
        self.sequences = {
            int(key): (record["moltype"], record["original_literal"])
            for key, record in self.pack["source_records"].items()
        }

    def rejected(self, code, function, *args):
        with self.assertRaises(reference.ReferenceError) as result:
            function(*args)
        self.assertEqual(result.exception.code, code)

    def test_complete_content_has_fixed_independent_original_identities(self):
        # This returns no report/capability and does not authenticate a full XML.
        self.assertIsNone(reference._check_pack_contents(self.pack, self.sequences))
        self.assertEqual(sorted(self.sequences), [2, 11, 34, 65, 101, 151])
        self.assertEqual(self.pack["listing_inventory"], {
            "entry_count": 401, "sequence_count": 397,
            "omitted_sequence_ids": [9, 10, 244, 296],
        })
        self.assertEqual(self.pack["source_records"]["151"]["rna_sha256"],
                         "7a0e872d51987d1c0064accb5197e605943d90ea2c20104d86e9f41f12617335")
        self.assertEqual(self.pack["source_records"]["2"]["original_literal_sha256"],
                         "833bd17e675e9595d01865a0109c9c795d2ba8b78481ab06f12da043019e404d")
        self.assertEqual(self.pack["nominal_chemistry"]["three_prime_end"]["identity"], None)
        self.assertEqual(set(self.pack["acceptance"].values()), {False})

    def test_every_complete_identity_coordinate_claim_and_provenance_leaf_is_checked(self):
        count = 0
        for path, original in scalar_paths(self.pack):
            changed = copy.deepcopy(self.pack)
            parent = changed
            for key in path[:-1]:
                parent = parent[key]
            if type(original) is bool:
                mutation = not original
            elif type(original) is int:
                mutation = original + 1
            elif original is None:
                mutation = "invented"
            else:
                mutation = original + "!"
            parent[path[-1]] = mutation
            with self.subTest(path=path):
                self.rejected("reference_mismatch", reference._check_pack_contents,
                              changed, self.sequences)
            count += 1
        self.assertEqual(count, 162)

    def test_missing_extra_and_reordered_records_do_not_change_authority(self):
        for key in self.pack:
            changed = copy.deepcopy(self.pack)
            del changed[key]
            self.rejected("reference_mismatch", reference._check_pack_contents,
                          changed, self.sequences)
        changed = copy.deepcopy(self.pack)
        changed["saved_consistent_report"] = {"status": "consistent"}
        self.rejected("reference_mismatch", reference._check_pack_contents, changed, self.sequences)
        changed = copy.deepcopy(self.pack)
        changed["transcript"]["regions"].reverse()
        self.rejected("reference_mismatch", reference._check_pack_contents, changed, self.sequences)
        reordered = dict(reversed(list(self.pack.items())))
        self.assertIsNone(reference._check_pack_contents(reordered, self.sequences))

    def test_repinning_each_original_record_cannot_forge_the_independent_pin(self):
        for key, (moltype, original) in self.sequences.items():
            changed = dict(self.sequences)
            changed[key] = (moltype, ("A" if moltype == "AA" else "t") + original[1:])
            if changed[key][1] == original:
                changed[key] = (moltype, ("G" if moltype == "AA" else "g") + original[1:])
            repinned = copy.deepcopy(self.pack)
            record = repinned["source_records"][str(key)]
            record["original_literal"] = changed[key][1]
            record["original_literal_sha256"] = reference.sha256(changed[key][1].encode())
            with self.subTest(sequence_id=key):
                self.rejected("sequence_identity", reference._check_pack_contents, repinned, changed)
        for key in self.sequences:
            missing = dict(self.sequences)
            del missing[key]
            self.rejected("sequence_identity", reference._check_pack_contents, self.pack, missing)

    def test_original_lowercase_spelling_is_not_silently_normalized(self):
        changed = dict(self.sequences)
        changed[151] = ("RNA", changed[151][1].upper())
        self.rejected("sequence_identity", reference._check_pack_contents, self.pack, changed)
        original = self.pack["source_records"]["151"]
        self.assertEqual(original["rna_sequence"], original["original_literal"].upper().replace("T", "U"))

    def test_tail_boundary_double_stop_and_standard_code_are_independent(self):
        records = reference._selected_records(self.sequences)
        full = records["151"]["original_literal"].upper()
        self.assertEqual(full[1540:1666], records["34"]["original_literal"].upper())
        self.assertEqual(len(full[1666:]), 110)
        self.assertEqual(len(full) - len(full.rstrip("A")), 111)
        self.assertEqual(full[:2], "AG")
        self.assertEqual(reference.CODON_TABLE[full[1534:1537]], "*")
        self.assertEqual(reference.CODON_TABLE[full[1537:1540]], "*")
        self.assertEqual({codon for codon, aa in reference.CODON_TABLE.items() if aa == "*"},
                         {"TAA", "TAG", "TGA"})
        self.assertEqual(reference.CODON_TABLE["ATG"], "M")
        self.assertEqual(reference.CODON_TABLE["TGG"], "W")
        with mock.patch.dict(reference.CODON_TABLE, {"ATG": "I"}):
            self.rejected("genetic_code_identity", reference._check_arithmetic, records)
        changed = copy.deepcopy(records)
        changed["151"]["original_literal"] = full[:1534] + "AAAAAA" + full[1540:]
        self.rejected("sequence_correspondence", reference._check_arithmetic, changed)

    def test_synthetic_listing_never_qualifies_as_original_complete_xml(self):
        raw = synthetic_xml([(key, *value) for key, value in self.sequences.items()])
        self.assertEqual(reference.parse_listing(raw), self.sequences)
        self.rejected("xml_identity", reference.check_reference, self.pack, raw)
        self.rejected("xml_identity", reference.check_reference, self.pack, raw + b"\n")
        # Repinning metadata in the submitted pack cannot replace original XML authority.
        changed = copy.deepcopy(self.pack)
        changed["sources"]["xml"].update(bytes=len(raw), sha256=reference.sha256(raw))
        self.rejected("xml_identity", reference.check_reference, changed, raw)

    def test_exact_omitted_placeholder_and_safe_known_doctype(self):
        raw = synthetic_xml([(9, "omitted", "000"), (151, "RNA", "ag")],
                            declaration=reference.DOCTYPE)
        self.assertEqual(reference.parse_listing(raw), {9: ("omitted", "000"), 151: ("RNA", "ag")})
        self.rejected("xml_shape", reference.parse_listing,
                      raw.replace(b"<INSDSeq_moltype></INSDSeq_moltype>", b"<INSDSeq_moltype>RNA</INSDSeq_moltype>"))

    def test_entities_external_dtd_and_processing_instructions_are_rejected(self):
        raw = synthetic_xml([(1, "RNA", "ag")])
        bad_prefixes = [
            '<!DOCTYPE x SYSTEM "file:///etc/passwd">',
            '<!DOCTYPE x [<!ENTITY payload SYSTEM "https://example.invalid/data">]>',
            '<!DOCTYPE x [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]>',
            '<?fetch url="https://example.invalid/"?>',
            reference.DOCTYPE + reference.DOCTYPE,
        ]
        for prefix in bad_prefixes:
            with self.subTest(prefix=prefix), self.assertRaises(reference.ReferenceError):
                reference.parse_listing(prefix.encode() + raw)
        for value in (b"&payload;", b"&#65;", b"&#x41;"):
            self.rejected("xml_entities", reference.parse_listing, raw.replace(b">ag<", b">" + value + b"<"))

    def test_duplicate_missing_malformed_fields_and_counts_reject(self):
        self.rejected("xml_duplicate", reference.parse_listing,
                      synthetic_xml([(1, "RNA", "ag"), (1, "RNA", "ag")]))
        raw = synthetic_xml([(1, "RNA", "ag")])
        for bad in [raw.replace(b"<INSDSeq_sequence>ag</INSDSeq_sequence>", b""),
                    raw.replace(b"</INSDSeq>", b"<INSDSeq_length>2</INSDSeq_length></INSDSeq>"),
                    raw.replace(b"<INSDSeq_length>2", b"<INSDSeq_length>3"),
                    raw.replace(b"<SequenceTotalQuantity>1", b"<SequenceTotalQuantity>2"),
                    raw.replace(b"</ST26SequenceListing>", b""), b"\xff"]:
            with self.subTest(raw=bad[:80]), self.assertRaises(reference.ReferenceError):
                reference.parse_listing(bad)

    def test_xml_and_json_resource_bounds(self):
        self.rejected("xml_limit", reference.parse_listing, b" " * (reference.MAX_XML_BYTES + 1))
        self.rejected("xml_limit", reference.parse_listing, b"<x>" * 17 + b"</x>" * 17)
        self.rejected("xml_limit", reference.parse_listing,
                      b"<root>" + b"<x/>" * reference.MAX_XML_NODES + b"</root>")
        self.rejected("xml_limit", reference.parse_listing, synthetic_xml([(1, "RNA", "a" * 20_001)]))
        self.rejected("reference_limit", reference.load_pack, b" " * (reference.MAX_PACK_BYTES + 1))
        self.rejected("reference_limit", reference.canonical, [None] * reference.MAX_JSON_NODES)
        deep = None
        for _ in range(18):
            deep = [deep]
        self.rejected("reference_limit", reference.canonical, deep)

    def test_json_duplicate_keys_scalar_types_and_nonfinite_numbers_reject(self):
        self.rejected("reference_json", reference.load_pack, b'{"x":1,"x":2}')
        self.rejected("reference_json", reference.load_pack, b'{"x":NaN}')
        for value in (float("nan"), float("inf"), object(), {1: "x"}):
            self.rejected("reference_json", reference.canonical, value)
        changed = copy.deepcopy(self.pack)
        changed["source_records"]["151"]["sequence_id"] = 151.0
        self.rejected("reference_mismatch", reference._check_pack_contents, changed, self.sequences)
        changed = copy.deepcopy(self.pack)
        changed["sources"]["xml"]["verified_by_this_checker"] = 1
        self.rejected("reference_mismatch", reference._check_pack_contents, changed, self.sequences)

    def test_cli_rejection_keeps_acceptance_false_and_preserves_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            xml = path / "synthetic.xml"
            xml.write_bytes(synthetic_xml([(1, "RNA", "ag")]))
            output = path / "report.json"
            original = xml.read_bytes()
            code = reference.main(["--pack", str(PACK_PATH), "--xml", str(xml), "--output", str(output)])
            self.assertEqual(code, 1)
            report = json.loads(output.read_bytes())
            self.assertEqual(report["code"], "xml_identity")
            self.assertTrue(all(report[key] is False for key in report if key.endswith("_acceptance")))
            self.assertEqual(xml.read_bytes(), original)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                reference.main(["--pack", str(PACK_PATH), "--xml", str(xml), "--output", str(xml)])
            self.assertEqual(xml.read_bytes(), original)
            alias = path / "alias.xml"
            os.link(xml, alias)
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                reference.main(["--pack", str(PACK_PATH), "--xml", str(xml), "--output", str(alias)])
            self.assertEqual(xml.read_bytes(), original)

    def test_path_reader_rejects_fifo_symlink_and_oversize_without_blocking(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            regular = path / "original.xml"
            regular.write_bytes(b"small")
            self.assertEqual(reference._read(regular, 5), b"small")
            self.rejected("input_limit", reference._read, regular, 4)
            fifo = path / "fifo"
            os.mkfifo(fifo)
            self.rejected("input_limit", reference._read, fifo, 5)
            alias = path / "symlink"
            alias.symlink_to(regular)
            with self.assertRaises(OSError):
                reference._read(alias, 5)


if __name__ == "__main__":
    unittest.main()
