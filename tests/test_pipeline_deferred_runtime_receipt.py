"""Offline foreign-runtime receipt controls; no native executable is invoked."""
from copy import deepcopy
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import check_pipeline_deferred_runtime_receipt as receipt


class PipelineDeferredRuntimeReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        oracle = receipt.runtime.original
        cls.frozen = json.loads(oracle.OUTPUT.read_bytes())
        cls.current = oracle.capture()
        cls.proof = receipt.runtime.compare_current(cls.frozen, cls.current)
        cls.proof["capture_authority"] = receipt.capture_authority()
        cls.version = platform.python_version()

    def check(self, current=None, proof=None, version=None):
        return receipt.validate_retained(self.frozen, self.current if current is None else current,
            self.proof if proof is None else proof, python_version=self.version if version is None else version)

    def test_offline_reconstruction_does_not_execute_an_interpreter_counterpart(self):
        with patch.object(receipt.runtime, "compare_current", side_effect=AssertionError("must not execute")), \
                patch.object(receipt.runtime.original, "capture", side_effect=AssertionError("must not execute")), \
                patch.object(receipt, "capture_authority", side_effect=AssertionError("must not execute")):
            actual = self.check()
        self.assertEqual(actual["comparison_capture"], self.proof["comparison_capture"])
        self.assertEqual(actual["expected_capture"], self.proof["expected_capture"])
        self.assertEqual(actual["frame_correspondences"], self.proof["frame_correspondences"])
        self.assertIn("hosted_producer", actual["execution_authority"])

    def test_absolute_script_and_sibling_import_preserve_external_search_path(self):
        source = Path(receipt.__file__).resolve()
        program = """import importlib, pathlib, runpy, sys
source = pathlib.Path(sys.argv[1])
assert str(source.parents[1]) not in sys.path
sys.path.insert(0, str(source.parent))
before = list(sys.path)
module = importlib.import_module(source.stem)
assert pathlib.Path(module.runtime.__file__).resolve() == source.with_name('check_pipeline_deferred_runtime.py')
assert sys.path == before
assert runpy.run_path(str(source), run_name='__main__')['SCHEMA'] == module.SCHEMA
assert sys.path == before
"""
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        with tempfile.TemporaryDirectory(prefix="biocompiler-runtime-import-") as external:
            result = subprocess.run([sys.executable, "-I", "-c", program, str(source)],
                cwd=external, env=environment, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_runtime_slot_and_complete_raw_evidence_are_mandatory(self):
        for mutation in ("runtime", "raw", "independent", "origin", "census"):
            proof = deepcopy(self.proof)
            if mutation == "runtime":
                proof["capture_authority"]["python_version"] = "3.14.999"
            elif mutation == "raw":
                proof["complete_raw_current"]["coverage"]["events"] -= 1
            elif mutation == "independent":
                proof["independent_raw_current"]["cases"].pop()
            elif mutation == "origin":
                proof["source_origins"]["src/biocompiler/compiler/pipeline.py"]["path"] += ".forged"
            else:
                proof["source_origins"]["src/biocompiler/compiler/pipeline.py"]["codes"][0]["bytecode_sha256"] = "f"*64
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                self.check(proof=proof)

    def test_fully_rehashed_source_and_bytecode_forgeries_cannot_replace_closed_pins(self):
        for mutation in ("original-source", "stdlib-source", "bytecode", "position-table", "code-census"):
            proof = deepcopy(self.proof)
            authority = proof["capture_authority"]
            if mutation in ("original-source", "stdlib-source"):
                logical = "src/biocompiler/compiler/pipeline.py" if mutation == "original-source" else "stdlib/_collections_abc.py"
                source = authority["sources"][logical]
                changed = bytes.fromhex(source["hex"]) + b"\n# independently forged source\n"
                source["hex"], source["sha256"] = changed.hex(), receipt.raw_digest(changed)
                if mutation == "stdlib-source":
                    proof["runtime_primitives"]["mapping"]["stdlib"]["sha256"] = source["sha256"]
                else:
                    proof["source_origins"][logical]["sha256"] = source["sha256"]
            elif mutation == "bytecode":
                code = authority["selected_code"]["mapping_iterator"]
                raw = bytes.fromhex(code["bytecode"])
                raw = bytes([raw[0] ^ 1]) + raw[1:]
                code["bytecode"] = raw.hex()
                proof["runtime_primitives"]["mapping"]["stdlib"]["code"]["bytecode_sha256"] = receipt.raw_digest(raw)
            elif mutation == "position-table":
                primitive = proof["runtime_primitives"]["obligations"]
                code = authority["selected_code"]["obligation_generator"]
                next(row for row in code["instructions"] if row["offset"] == primitive["instruction"]["offset"])["line"] += 1
                primitive["instruction"]["line"] += 1
                primitive["frame"]["line"] += 1
            else:
                logical = "src/biocompiler/compiler/pipeline.py"
                authority["source_code_census"][logical][0]["bytecode_sha256"] = "a"*64
                proof["source_origins"][logical]["codes"][0]["bytecode_sha256"] = "a"*64
            # Every mutable digest is updated above. Acceptance must still use
            # the registered table, not a digest supplied by this forged proof.
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                self.check(proof=proof)

    def test_supplied_projection_and_correspondence_are_reconstructed_not_trusted(self):
        for mutation in ("projection", "correspondence", "primitive-frames", "different-valid-instruction", "runtime-message"):
            proof = deepcopy(self.proof)
            if mutation == "projection":
                proof["comparison_capture"]["coverage"]["events"] -= 1
                proof["expected_capture"] = deepcopy(proof["comparison_capture"])
                for key in ("comparison_capture", "expected_capture"):
                    proof[key]["inventory_fingerprint"] = receipt.inventory(proof[key])
            elif mutation == "correspondence":
                proof["frame_correspondences"].append({"rule": "drop_all_tracebacks"})
            elif mutation == "primitive-frames":
                proof["runtime_primitives"]["mapping"]["raw_traceback"][-1]["line"] += 1
            elif mutation == "different-valid-instruction":
                previous = proof["runtime_primitives"]["mapping"]["instructions"][0]
                rows = proof["capture_authority"]["selected_code"]["freeze_json"]["instructions"]
                other = next(row for row in rows if row["line"] == previous["line"] and row["offset"] != previous["offset"])
                proof["runtime_primitives"]["mapping"]["instructions"][0] = {
                    key: value for key, value in other.items() if key not in ("opcode", "argument")}
            else:
                proof["runtime_primitive"]["message"] = "forged runtime error"
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                self.check(proof=proof)

    def test_rehashed_raw_user_behavior_cannot_be_hidden_by_matching_projections(self):
        current, proof = deepcopy(self.current), deepcopy(self.proof)
        case = next(case for case in current["cases"] if case["id"] == "callback:exception_reused")
        case["events"][1]["exception"]["same_marker_object"] = False
        current["inventory_fingerprint"] = receipt.inventory(current)
        proof["complete_raw_current"] = deepcopy(current)
        proof["independent_raw_current"] = deepcopy(current)
        with self.assertRaisesRegex(AssertionError, "outside the independently rebuilt"):
            self.check(current=current, proof=proof)


def load_tests(loader, tests, pattern):
    from tools.pipeline_original_counterpart import original_test_suite
    return original_test_suite(loader, tests, pattern, 'test_pipeline_deferred_runtime_receipt')


if __name__ == "__main__":
    unittest.main()
