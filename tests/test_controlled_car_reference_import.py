"""Artificial controls for offline literal import; no publication sequences bundled."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

TOOL = Path(__file__).resolve().parents[1] / "tools/import_controlled_car_reference.py"
SPEC = importlib.util.spec_from_file_location("controlled_car_reference_import", TOOL)
api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def artificial_entries():
    figures = {"schema": "biocompiler.car_controlled_reference.manual_figure_transcription.v0.1",
               "reference": api.REFERENCE, "source_sha256": api.digest(b"%PDF-artificial-figure"),
               "status": "artificial_test_fixture", "normalization": "Whitespace only, uppercase",
               "not_supplied": ["stop codons", "RNA context", "RNA chemistry", "full plasmid/vector"],
               "construct_block_order": copy.deepcopy(api.ORDER), "records": []}
    listing = {"schema": "biocompiler.car_controlled_reference.manual_listing_transcription.v0.1",
               "source": "US20150368342A1", "source_sha256": api.digest(b"%PDF-artificial-listing"),
               "status": "artificial_test_fixture", "independence_limit": "No publication evidence", "records": []}
    for n, length in api.LENGTHS.items():
        dna = ("ATG" if n in (1, 27) else "GCT") + "GCT" * (length // 3 - 1)
        protein = ("M" if n in (1, 27) else "A") + "A" * (length // 3 - 1)
        figures["records"].append({"id": str(n), "dna_seq_id": n, "protein_seq_id": n + 1,
            "pdf_page_one_based": 90, "figure": "artificial", "label": "artificial block",
            "dna_figure_text": dna.lower(), "protein_figure_text": protein.lower(), "dna": dna, "protein": protein})
        listing["records"].append({"dna_seq_id": n, "printed_length": length,
            "pdf_page_one_based": 93, "grouped_text": " ".join(dna[i:i + 3] for i in range(0, length, 3)), "dna": dna})
    for construct, dna in (("197", "TCTCTG"), ("206", "TCACTG")):
        figures["records"].append({"id": construct + "-short-linker", "dna_seq_id": None, "protein_seq_id": None,
            "pdf_page_one_based": 91, "figure": "artificial", "label": "artificial linker",
            "dna_figure_text": dna, "protein_figure_text": "SL", "dna": dna, "protein": "SL"})
    return figures, listing


class ControlledCarReferenceImportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        self.inventory = self.root / "inventory.json"
        self.figures, self.listing = artificial_entries()
        self.reset_inputs()

    def reset_inputs(self):
        rows = dict(zip(api.INPUTS, (b"%PDF-artificial-figure", b"%PDF-artificial-listing",
                                    encoded(self.figures), encoded(self.listing))))
        for name, raw in rows.items():
            (self.inputs / name).write_bytes(raw)
        self.pins = {name: {"size_bytes": len(raw), "sha256": api.digest(raw)} for name, raw in rows.items()}
        self.inventory_data = {
            "schema": "biocompiler.car_controlled_reference.source_inventory.v0.1",
            "selected_acquisition_reference": api.REFERENCE,
            "authorized_input_import_contract": {"original_authority": list(api.INPUTS)},
            "sources": [{"id": name, **self.pins[name]} for name in api.PDFS],
            "local_material_artifacts": [{"path": "generated/car-controlled-composition/reference-acquisition/" + name,
                                           **self.pins[name]} for name in api.ENTRIES],
            "material_check_result": {"status": "DO_NOT_TRUST_SAVED_PASS"}}
        self.inventory.write_bytes(encoded(self.inventory_data))

    def inspect(self):
        return api.inspect(self.inputs, inventory_path=self.inventory)

    def test_fresh_deterministic_receipt_preserves_boundaries_and_exact_spans(self):
        raw = self.inspect()
        self.assertEqual(raw, self.inspect())
        report = json.loads(raw)
        self.assertEqual([(p["construct"], p["dna_nt"], p["protein_aa"]) for p in report["products"]],
                         [("197", 1512, 504), ("206", 1779, 593)])
        self.assertEqual(len(report["components"]), 16)
        for product in report["products"]:
            self.assertFalse(product["stop_codon_present"])
            self.assertEqual(product["spans"][0]["dna_start_zero_based"], 0)
            self.assertEqual(product["spans"][-1]["dna_end_exclusive"], product["dna_nt"])
            self.assertEqual([s["block_id"] for s in product["spans"]], api.ORDER[product["construct"]])
            for left, right in zip(product["spans"], product["spans"][1:]):
                self.assertEqual(left["dna_end_exclusive"], right["dna_start_zero_based"])
            self.assertNotIn("dna", product)
            self.assertNotIn("protein", product)
        self.assertFalse(report["is_rna_design"])
        self.assertFalse(report["is_admitted_molecular_pack"])
        self.assertEqual(report["native_status"], "not_run")
        self.assertEqual(report["biological_status"], "unassessed")
        self.assertEqual(report["wu_publication_pair_identity"], "not_established")
        self.assertEqual(report["inventory_sha256"], api.digest(self.inventory.read_bytes()))
        self.assertIn("termination", report["missing_rna_design"])

    def test_changed_source_or_transcription_fails_before_json_decode(self):
        for name in api.INPUTS:
            with self.subTest(name=name):
                self.reset_inputs()
                target = self.inputs / name
                raw = target.read_bytes()
                target.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
                original_decode = api.decode
                with patch.object(api, "decode", wraps=original_decode) as decoded:
                    with self.assertRaisesRegex(api.ImportRejected, "pin differs"):
                        self.inspect()
                    self.assertEqual(decoded.call_count, 1)  # only independent inventory

    def test_saved_pass_cannot_replace_fresh_listing_agreement(self):
        record = self.figures["records"][1]
        record["dna"] = "GCC" + record["dna"][3:]
        record["dna_figure_text"] = record["dna"]
        self.reset_inputs()  # even newly pinned malformed material must fail replay
        self.assertEqual(api.translate(record["dna"]), record["protein"])
        with self.assertRaisesRegex(api.ImportRejected, "Figure/listing DNA"):
            self.inspect()

    def test_record_order_junction_translation_and_census_fail_closed(self):
        def remove_linker(figures, listing):
            figures["construct_block_order"]["197"].remove("197-short-linker")
        def collapse_linker(figures, listing):
            figures["records"][-1]["dna"] = figures["records"][-2]["dna"]
            figures["records"][-1]["dna_figure_text"] = figures["records"][-2]["dna"]
        def wrong_protein(figures, listing):
            figures["records"][0]["protein"] = "A" * 21
            figures["records"][0]["protein_figure_text"] = "A" * 21
        def add_stop(figures, listing):
            figures["records"][0]["dna"] += "TAA"
            figures["records"][0]["dna_figure_text"] = figures["records"][0]["dna"]
        def duplicate_record(figures, listing):
            listing["records"][1] = copy.deepcopy(listing["records"][0])
        def boolean_id(figures, listing):
            listing["records"][0]["dna_seq_id"] = True
        def unknown_field(figures, listing):
            figures["records"][0]["approved"] = True
        def wrong_pin(figures, listing):
            figures["source_sha256"] = "0" * 64
        def missing_declaration(figures, listing):
            figures["not_supplied"].remove("stop codons")
        for mutate in (remove_linker, collapse_linker, wrong_protein, add_stop, duplicate_record,
                       boolean_id, unknown_field, wrong_pin, missing_declaration):
            with self.subTest(mutation=mutate.__name__):
                self.figures, self.listing = artificial_entries()
                mutate(self.figures, self.listing)
                self.reset_inputs()
                with self.assertRaises(api.ImportRejected):
                    self.inspect()

    def test_missing_duplicate_or_traversing_inventory_pins_are_rejected(self):
        for mode in ("missing", "duplicate", "escape", "bool_size", "oversize", "extra_authority"):
            self.reset_inputs()
            value = self.inventory_data
            if mode == "missing":
                value["sources"].pop()
            elif mode == "duplicate":
                value["sources"].append(value["sources"][0])
            elif mode == "escape":
                value["local_material_artifacts"][0]["path"] = "../" + api.ENTRIES[0]
            elif mode == "bool_size":
                value["sources"][0]["size_bytes"] = True
            elif mode == "oversize":
                value["sources"][0]["size_bytes"] = api.MAX_BYTES + 1
            else:
                value["authorized_input_import_contract"]["original_authority"].append("extra")
            self.inventory.write_bytes(encoded(value))
            with self.subTest(mode=mode), self.assertRaises(api.ImportRejected):
                self.inspect()

    def test_missing_symlink_fifo_and_oversized_files_are_rejected(self):
        target = self.inputs / api.PDFS[0]
        saved = target.read_bytes()
        for mode in ("missing", "symlink", "fifo", "oversize", "empty"):
            target.unlink(missing_ok=True)
            if mode == "symlink":
                outside = self.root / "outside.pdf"
                outside.write_bytes(saved)
                target.symlink_to(outside)
            elif mode == "fifo":
                os.mkfifo(target)
            elif mode == "oversize":
                target.write_bytes(saved + b"extra")
            elif mode == "empty":
                target.write_bytes(b"")
            with self.subTest(mode=mode), self.assertRaises((api.ImportRejected, OSError)):
                self.inspect()
        target.unlink()
        target.write_bytes(saved)
        alias = self.root / "alias"
        alias.symlink_to(self.inputs, target_is_directory=True)
        with self.assertRaisesRegex(api.ImportRejected, "symbolic link"):
            api.inspect(alias, inventory_path=self.inventory)

    def test_duplicate_nonfinite_deep_and_oversized_json_rejected(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1.5}', b'{"a":"\\ud800"}',
                    b'[' * 22 + b'0' + b']' * 22, b' ' * (api.MAX_JSON_BYTES + 1)):
            with self.subTest(raw=raw[:50]), self.assertRaises(api.ImportRejected):
                api.decode(raw)

    def test_publication_is_atomic_never_overwrites_and_cleans_staging(self):
        output = self.root / "receipt.json"
        raw = self.inspect()
        api.publish(raw, output)
        self.assertEqual(output.read_bytes(), raw)
        with self.assertRaisesRegex(api.ImportRejected, "already exists"):
            api.publish(b"replacement", output)
        self.assertEqual(output.read_bytes(), raw)
        failure = self.root / "failure.json"
        with patch.object(api.os, "link", side_effect=OSError("simulated publication failure")):
            with self.assertRaises(OSError):
                api.publish(raw, failure)
        self.assertFalse(failure.exists())
        self.assertEqual(list(self.root.glob(".controlled-car-import-*")), [])
        link = self.root / "dangling.json"
        link.symlink_to(self.root / "absent")
        with self.assertRaisesRegex(api.ImportRejected, "already exists"):
            api.publish(raw, link)

    def test_cli_failure_does_not_create_output_or_call_native_processes(self):
        output = self.root / "receipt.json"
        with patch.object(api, "inspect", side_effect=api.ImportRejected("fixture failure")):
            self.assertEqual(api.main(["--inputs", str(self.inputs), "--output", str(output)]), 1)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
