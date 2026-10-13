"""Preparation safeguards with synthetic coding fragments; no native execution."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.policy.car_reference import reference_data
from tests.test_controlled_car_reference_import import artificial_entries
from tools import prepare_controlled_car_reference as prepare


class ControlledCarReferencePreparationTests(unittest.TestCase):
    def setUp(self):
        figures, _ = artificial_entries()
        ids = (*prepare.SOURCE_IDS, "controlled.car197206.adaptation",
               "WO2025096878.sequence-listing", "WO2025096878A9")
        sources = [{"id": identity, "version": "1", "sha256": "a" * 64} for identity in ids]
        self.material = prepare.assemble_material(figures, reference_data(), sources)
        # Synthetic oracle: independent frozen region extents; derived identities
        # here isolate adversarial preparation behavior, not public-source fidelity.
        self.expected = {"members": []}
        for member, nt, aa, cds_end in zip(self.material["members"], (1830, 2097), (504, 593), (1594, 1861), strict=True):
            root = next(row for row in self.material["template"]["sources"] if row["id"] == member["id"] + ".input")
            rna = root["molecule"]["sequence"]
            bounds = (("five_prime_utr", 0, 79), ("orf_excluding_stop", 79, cds_end - 3),
                      ("single_stop", cds_end - 3, cds_end), ("three_prime_utr", cds_end, nt - 110),
                      ("encoded_poly_a", nt - 110, nt))
            self.expected["members"].append({"id": member["id"], "rna_nt": nt, "protein_aa": aa,
                "rna_sha256": prepare.sha(rna.encode()), "protein_sha256": prepare.sha(member["product"]["sequence"].encode()),
                "product_content_fingerprint": member["product"]["identity"]["content_fingerprint"],
                "regions": [{"role": role, "start": start, "end": end, "rna_sha256": prepare.sha(rna[start:end].encode())}
                            for role, start, end in bounds]})

    def test_complete_nominal_design_and_explicit_adaptation_provenance(self):
        prepare.check_expected(self.material, self.expected)
        self.assertEqual(self.material["member_order"], ["car197", "car206"])
        self.assertEqual(self.material["template"]["steps"], [])
        for source, member in zip(self.material["template"]["sources"], self.material["members"], strict=True):
            molecule = source["molecule"]
            self.assertIn("not reported", molecule["provenance"]["reason"])
            self.assertEqual(molecule["sequence_extent"], "complete")
            self.assertEqual(member["product"]["translation_policy"]["profile"], "ordinary_cds")
            self.assertEqual(len(molecule["sequence"]) - len(molecule["sequence"].rstrip("A")), 111)
            self.assertEqual(molecule["chemistry"]["terminal_tail"]["length"]["exact"], 110)
            self.assertIn("designer-specified", molecule["chemistry"]["cap"]["provenance"]["reason"])

    def test_unchanged_protein_does_not_authorize_changed_utr(self):
        changed = copy.deepcopy(self.material)
        molecule = changed["template"]["sources"][0]["molecule"]
        molecule["sequence"] = "C" + molecule["sequence"][1:]
        self.assertEqual(changed["members"][0]["product"], self.material["members"][0]["product"])
        with self.assertRaisesRegex(ValueError, "Complete RNA differs"):
            prepare.check_expected(changed, self.expected)

    def test_region_translation_and_member_mutations_reject(self):
        for mode in ("region", "kind", "frame", "recoding", "member_order", "root_identity", "product_pin"):
            changed = copy.deepcopy(self.material)
            root = changed["template"]["sources"][0]
            feature = next(row for row in root["molecule"]["features"] if row["id"] == "cds")
            if mode == "region": feature["path"]["spans"][0]["start"] += 3
            elif mode == "kind": feature["kind"] = "five_prime_utr"
            elif mode == "frame": feature["reading_frame"] = 1
            elif mode == "recoding": changed["members"][0]["product"]["translation_policy"]["recodings"] = ["invented"]
            elif mode == "member_order": changed["members"].reverse()
            elif mode == "root_identity": root["id"] = "other.input"
            else: changed["members"][0]["product"]["identity"]["content_fingerprint"] = "0" * 64
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                prepare.check_expected(changed, self.expected)

    def test_manifest_only_chemistry_changes_reject(self):
        for mode in ("cap", "terminal", "modification", "missing_modification", "tail", "tail_frame", "design_provenance"):
            changed = copy.deepcopy(self.material)
            chemistry = changed["members"][0]["chemistry"]
            if mode == "cap": chemistry["cap"]["identity"]["accession"] = "other_cap"
            elif mode == "terminal": chemistry["finish_end"]["identity"]["accession"] = "other_end"
            elif mode == "modification": chemistry["modifications"][0]["scope"] = "positions"
            elif mode == "missing_modification": chemistry["modifications"].pop()
            elif mode == "tail": chemistry["terminal_tail"]["length"]["exact"] = 111
            elif mode == "tail_frame": chemistry["terminal_tail"]["path"]["space_id"] = "wrong"
            else: chemistry["cap"]["provenance"]["authority"] = []
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                prepare.check_expected(changed, self.expected)

    def test_changed_original_cannot_be_repaired_only_in_acquisition_inventory(self):
        originals = {name: name.encode() for name in prepare.fragments.INPUTS}
        xml = b"independent XML stand-in"
        expected = {"original_input_pins": [{"name": key, "bytes": len(raw), "sha256": prepare.sha(raw)}
            for key, raw in {**originals, prepare.utr_check.XML_NAME: xml}.items()]}
        prepare.check_originals(expected, originals, xml)
        originals[prepare.fragments.PDFS[0]] += b"changed"
        with self.assertRaisesRegex(ValueError, "Original differs from independent"):
            prepare.check_originals(expected, originals, xml)

    def test_pinned_contract_change_rejects_before_acquisition_and_publication(self):
        with tempfile.TemporaryDirectory() as folder:
            contract = Path(folder) / "contract.json"
            value = json.loads(prepare.CONTRACT.read_bytes())
            value["scenario"]["actual_delays"]["cessation_ticks"] = 0
            contract.write_text(json.dumps(value))
            with patch.object(prepare, "CONTRACT", contract), patch.object(prepare.fragments, "load_inputs") as load:
                with self.assertRaisesRegex(ValueError, "Original source identity"):
                    prepare.prepare(inputs=folder, original_xml="missing", reference_pdf="missing", controller_catalog="missing", design=prepare.DESIGN)
                load.assert_not_called()

    def test_explicit_design_is_required(self):
        with self.assertRaisesRegex(ValueError, "Select the explicit"):
            prepare.prepare(inputs="missing", original_xml="missing", reference_pdf="missing", controller_catalog="missing", design="auto")


if __name__ == "__main__":
    unittest.main()
