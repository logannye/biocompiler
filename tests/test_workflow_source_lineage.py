"""Exact bytes and fixed AST route additions cannot hide default-path edits."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import workflow_source_lineage as lineage
from tools import check_workflow_routed_recapture as recapture


class WorkflowSourceLineageTests(unittest.TestCase):
    def setUp(self):
        self.witness = lineage.load_witness()

    def altered(self, path, raw):
        entry = deepcopy(self.witness[path])
        entry.update(routed_source=raw.decode(), routed_sha256=lineage.sha(raw))
        return lineage.verify_extension(entry, raw, entry["historical_sha256"])

    def test_complete_historical_and_current_bytes_and_default_ast_are_retained(self):
        from tools.realization_source_lineage import verify_captured_source
        for path, entry in self.witness.items():
            raw = (lineage.ROOT / path).read_bytes()
            if path == lineage.CLI:
                from tools import synthetic_selection_cli_source_lineage as later
                parent = later.load_witness()["historical_source"].encode()
                self.assertEqual(parent, entry["routed_source"].encode())
                checked = lineage.verify_extension(entry, parent, entry["historical_sha256"])
                current = verify_captured_source(lineage.ROOT, {"path": path, "sha256": entry["historical_sha256"]})
                self.assertEqual(current["lineage"][0], checked)
                self.assertEqual(current["current_sha256"], lineage.sha(raw))
                self.assertEqual(current["lineage"][1]["historical_sha256"], entry["routed_sha256"])
                self.assertEqual(checked["current_sha256"], entry["routed_sha256"])
                self.assertEqual(checked["witness_sha256"], lineage.WITNESS_SHA256)
                self.assertEqual(lineage.sha(entry["historical_source"].encode()), lineage.HISTORICAL[path])
                continue
            self.assertEqual(raw, entry["routed_source"].encode())
            self.assertEqual(lineage.sha(entry["historical_source"].encode()), lineage.HISTORICAL[path])
            checked = lineage.verify_source(lineage.ROOT, path, entry["historical_sha256"])
            self.assertEqual(checked["current_sha256"], entry["routed_sha256"])
            self.assertEqual(checked["witness_sha256"], lineage.WITNESS_SHA256)
            self.assertEqual(verify_captured_source(lineage.ROOT, {
                "path": path, "sha256": entry["historical_sha256"]}), checked)

    def test_sdk_guard_signature_placement_and_exact_delegate_are_independently_checked(self):
        raw = self.witness[lineage.WORKFLOW]["routed_source"].encode()
        mutations = (
            (b"core=None", b"core=True"),
            (b"if core is not None:", b"if core:"),
            (b"return run_record(request, core=core)", b"return run_record(request, core=None)"),
            (b"return run_record(request, core=core)", b"return run_record(request, core=core)\n        print('changed')"),
            (b"Expected complete verification request.", b"Changed diagnostic."),
        )
        for old, new in mutations:
            with self.subTest(old=old), self.assertRaises(ValueError):
                self.altered(lineage.WORKFLOW, raw.replace(old, new, 1))
        with self.assertRaisesRegex(ValueError, "implementation AST differs"):
            self.altered(lineage.WORKFLOW, raw + b"\nimport os\n")

    def test_cli_exact_flags_branch_and_registration_census_are_checked(self):
        raw = self.witness[lineage.CLI]["routed_source"].encode()
        mutations = (
            (b'help=argparse.SUPPRESS', b'help="new usage"'),
            (b'"core_executable", "verify_executable", "core_sha256", "core_timeout"', b'"core_executable"'),
            (b'_workflow_core_arguments(replay)', b'_workflow_core_arguments(workflow)'),
            (b'bounded_text=_bounded_text', b'bounded_text=None'),
            (b'"--expected-request", type=Path, required=True', b'"--expected-request", type=Path, required=False'),
        )
        for old, new in mutations:
            changed = raw.replace(old, new, 1)
            self.assertNotEqual(changed, raw)
            with self.subTest(old=old), self.assertRaises(ValueError):
                self.altered(lineage.CLI, changed)

    def test_witness_and_current_pins_missing_sources_and_unchanged_paths_fail_closed(self):
        for path, entry in self.witness.items():
            raw = entry["routed_source"].encode()
            with self.assertRaisesRegex(ValueError, "Current workflow route bytes differ"):
                lineage.verify_extension(entry, raw + b"\n", entry["historical_sha256"])
            with self.assertRaisesRegex(ValueError, "Unreviewed historical"):
                lineage.verify_extension(entry, raw, "0" * 64)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            witness = root / "witness.json"
            witness.write_bytes(lineage.WITNESS.read_bytes() + b"\n")
            with patch.object(lineage, "WITNESS", witness), self.assertRaisesRegex(ValueError, "witness bytes differ"):
                lineage.load_witness()
            with self.assertRaisesRegex(ValueError, "Missing or linked"):
                lineage.verify_source(root, lineage.CLI, lineage.HISTORICAL[lineage.CLI])
            source = root / "unreviewed.py"
            source.write_bytes(b"value=1\n")
            self.assertEqual(lineage.verify_source(root, source.name, lineage.sha(source.read_bytes()))["kind"], "identical_bytes")
            with self.assertRaisesRegex(ValueError, "Captured source bytes differ"):
                lineage.verify_source(root, source.name, "0" * 64)

    def binding(self, name, *, native=False):
        kwargs = {"expected_request": {"authority": "independent"}} if name.startswith("replay") else {}
        if native:
            kwargs["core"] = None
        raw = {"args": [{"full": "original input"}], "kwargs": kwargs}
        text = json.dumps(raw)
        call = {"api": name, "id": "original/api/1", "input": "full-input-document"}
        documents = {call["input"]: {"value": text, "kind": "raw_arguments"}}
        key = "record" if name.startswith("replay") else "request"
        actual = {key: raw["args"][0], **kwargs, "core": None}
        return call, documents, actual

    def test_derived_signature_projection_retains_full_actual_and_raw_arguments(self):
        for name in lineage.FUNCTIONS:
            call, documents, actual = self.binding(name)
            before = deepcopy(actual)
            original, evidence = recapture.project_binding(call, documents, actual, lambda value: value)
            self.assertEqual(actual, before)
            self.assertNotIn("core", original)
            self.assertEqual(evidence["actual_bound_arguments"], actual)
            self.assertEqual(evidence["raw_arguments_text"], documents[call["input"]]["value"])
            self.assertEqual(evidence["historical_bound_arguments"], original)
            self.assertEqual({**original, "core": None}, actual)

    def test_explicit_native_keyword_and_any_other_bound_change_cannot_be_projected(self):
        for name in lineage.FUNCTIONS:
            call, documents, actual = self.binding(name, native=True)
            with self.assertRaisesRegex(ValueError, "supplied a native route argument"):
                recapture.project_binding(call, documents, actual, lambda value: value)
            call, documents, actual = self.binding(name)
            for altered in ({**actual, "core": "native"}, {**actual, "extra": None},
                            {key: value for key, value in actual.items() if key != "core"}):
                with self.assertRaisesRegex(ValueError, "differs beyond"):
                    recapture.project_binding(call, documents, altered, lambda value: value)
            changed = deepcopy(actual)
            changed["record" if name.startswith("replay") else "request"] = {"forged": True}
            with self.assertRaisesRegex(ValueError, "differs beyond"):
                recapture.project_binding(call, documents, changed, lambda value: value)


if __name__ == "__main__":
    unittest.main()
