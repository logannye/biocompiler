"""Exact chained source identities and additive-only public producer routes."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import synthetic_producer_source_lineage as lineage
from tools import check_synthetic_producer_routed_recapture as recapture


class SyntheticProducerSourceLineageTests(unittest.TestCase):
    def setUp(self):
        self.witness = lineage.load_witness()

    def changed(self, path, raw):
        entry = deepcopy(self.witness[path])
        entry.update(routed_source=raw.decode(), routed_sha256=lineage.sha(raw))
        return lineage.verify_extension(entry, raw, entry["historical_sha256"])

    def test_exact_parent_and_current_whole_files_and_default_ast_are_retained(self):
        from tools.realization_source_lineage import verify_captured_source
        for path, entry in self.witness.items():
            raw = (lineage.ROOT / path).read_bytes()
            self.assertEqual(raw, entry["routed_source"].encode())
            self.assertEqual(lineage.sha(entry["historical_source"].encode()), lineage.HISTORICAL[path])
            proof = lineage.verify_source(lineage.ROOT, path, entry["historical_sha256"])
            self.assertEqual(proof["current_sha256"], entry["routed_sha256"])
            self.assertEqual(proof["witness_sha256"], lineage.WITNESS_SHA256)
            self.assertEqual(proof, verify_captured_source(lineage.ROOT, {"path": path, "sha256": entry["historical_sha256"]}))

    def test_preexisting_realization_and_workflow_witnesses_remain_exact_and_chain_contiguously(self):
        from tools import realization_source_lineage as realization, workflow_source_lineage as workflow
        self.assertEqual(lineage.sha(workflow.WITNESS.read_bytes()), workflow.WITNESS_SHA256)
        for path, previous in ((lineage.SYNTHETIC, realization),):
            older = previous.load_witness()[path]
            parent = self.witness[path]["historical_source"].encode()
            self.assertEqual(lineage.sha(parent), older["routed_sha256"])
            proof = lineage.verify_source(lineage.ROOT, path, older["historical_sha256"])
            self.assertEqual(len(proof["lineage"]), 2)
            self.assertEqual(proof["lineage"][0]["witness_sha256"], previous.WITNESS_SHA256)
            self.assertEqual(proof["lineage"][0]["current_sha256"], proof["lineage"][1]["historical_sha256"])
            self.assertEqual(proof["historical_sha256"], older["historical_sha256"])
            self.assertEqual(proof["current_sha256"], self.witness[path]["routed_sha256"])

    def test_every_sdk_route_rejects_rehashed_default_or_delegate_changes(self):
        for path, (_name, helper, _arguments) in lineage.ROUTES.items():
            raw = self.witness[path]["routed_source"].encode()
            mutations = (
                raw.replace(b"core=None", b"core=True", 1),
                raw.replace(b"if core is not None:", b"if core:", 1),
                raw.replace(("return " + helper + "(").encode(), ("return missing_" + helper + "(").encode(), 1),
                raw.replace(b"    if core is not None:\n", b"    print('changed-default')\n    if core is not None:\n", 1),
                raw + b"\nimport os\n",
            )
            for mutated in mutations:
                self.assertNotEqual(mutated, raw)
                with self.subTest(path=path), self.assertRaises(ValueError):
                    self.changed(path, mutated)

    def test_wrong_parent_current_or_witness_bytes_fail_closed(self):
        for path, entry in self.witness.items():
            raw = entry["routed_source"].encode()
            with self.assertRaisesRegex(ValueError, "Current producer route bytes differ"):
                lineage.verify_extension(entry, raw + b"\n", entry["historical_sha256"])
            bad = deepcopy(entry)
            bad["historical_source"] += "\n"
            with self.assertRaisesRegex(ValueError, "Historical producer route bytes differ"):
                lineage.verify_extension(bad, raw, entry["historical_sha256"])
            with self.assertRaisesRegex(ValueError, "Historical source bytes differ|Unreviewed historical"):
                lineage.verify_source(lineage.ROOT, path, "0" * 64)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "witness.json"
            path.write_bytes(lineage.WITNESS.read_bytes() + b"\n")
            with patch.object(lineage, "WITNESS", path), self.assertRaisesRegex(ValueError, "witness bytes differ"):
                lineage.load_witness()
            with self.assertRaisesRegex(ValueError, "Missing or linked"):
                lineage.verify_source(Path(directory), lineage.SYNTHETIC, lineage.HISTORICAL[lineage.SYNTHETIC])

    def binding(self, name):
        args = [{"request": "complete original"}]
        if name == "adapt_synthetic_components":
            args.append({"candidate": "complete original"})
        if name != "generate_synthetic":
            args.append([{"time": 1.0}])
        raw = {"args": args, "kwargs": {}}
        call = {"api": name, "id": "original/api/1", "input": "exact-input-document"}
        documents = {call["input"]: {"kind": "raw_arguments", "value": json.dumps(raw)}}
        bound = recapture.historical_signature(name).bind(*args)
        bound.apply_defaults()
        return call, documents, {**dict(bound.arguments), "core": None}

    def test_full_original_and_actual_bindings_preserved_with_only_added_none_projected(self):
        for name in lineage.FUNCTIONS:
            call, documents, actual = self.binding(name)
            before = deepcopy(actual)
            original, evidence = recapture.project_binding(call, documents, actual, lambda value: value)
            self.assertEqual(actual, before)
            self.assertEqual({**original, "core": None}, actual)
            self.assertEqual(evidence["actual_bound_arguments"], actual)
            self.assertEqual(evidence["historical_bound_arguments"], original)
            self.assertEqual(evidence["raw_arguments_text"], documents[call["input"]]["value"])
            for changed in ({**actual, "core": False}, {**actual, "unexpected": None},
                            {key: value for key, value in actual.items() if key != "core"}):
                with self.assertRaisesRegex(ValueError, "differs beyond"):
                    recapture.project_binding(call, documents, changed, lambda value: value)
            raw = json.loads(documents[call["input"]]["value"])
            raw["kwargs"]["core"] = None
            documents[call["input"]]["value"] = json.dumps(raw)
            with self.assertRaisesRegex(ValueError, "supplied a native route argument"):
                recapture.project_binding(call, documents, actual, lambda value: value)

    def test_all_nine_original_source_corpora_keep_every_exact_or_chained_identity(self):
        from tools.realization_source_lineage import verify_captured_source
        names = ("candidate-runtime", "component-runtime", "realization-foundation", "realization-checks",
                 "component-acceptance", "synthetic-authority", "synthetic-acceptance", "synthetic-producers", "realization-workflow")
        count = 0
        for name in names:
            value = json.loads((lineage.ROOT / "tests/conformance" / (name + "-v1.json")).read_bytes())
            for entry in value["source_files"]:
                proof = verify_captured_source(lineage.ROOT, entry)
                self.assertEqual(proof["historical_sha256"], entry["sha256"])
                self.assertEqual(proof["current_sha256"], lineage.sha((lineage.ROOT / entry["path"]).read_bytes()))
                count += 1
        self.assertEqual(count, 2132)


if __name__ == "__main__":
    unittest.main()
