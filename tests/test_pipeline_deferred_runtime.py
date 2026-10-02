"""Installed-layout and interpreter-frame proof for the unchanged Python oracle."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import FunctionType
import unittest

from tools import capture_pipeline_deferred_semantics as oracle
from tools import check_pipeline_deferred_runtime as runtime


def resign(value):
    value["inventory_fingerprint"] = oracle.sha(oracle.canonical({key: item for key, item in value.items()
        if key != "inventory_fingerprint"}))
    return value


class PipelineDeferredRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frozen = json.loads(oracle.OUTPUT.read_bytes())
        cls.current = oracle.capture()
        cls.proof = runtime.compare_current(cls.frozen, cls.current)

    def test_full_raw_captures_and_existing_primitive_allowance_are_preserved(self):
        self.assertEqual(self.proof["complete_raw_current"], self.current)
        self.assertEqual(self.proof["independent_raw_current"], self.current)
        self.assertEqual(self.proof["comparison_capture"], self.proof["expected_capture"])
        self.assertEqual(len(self.current["cases"]), 47)
        self.assertEqual(self.current["coverage"], self.frozen["coverage"])
        self.assertEqual(self.frozen["inventory_fingerprint"], runtime.PIN)
        self.assertEqual(self.proof["exact_paths"], self.frozen["runtime_counterparts"][0])
        self.assertEqual(self.frozen, json.loads(oracle.OUTPUT.read_bytes()))

    def test_only_closed_source_and_instruction_correspondences_are_recorded(self):
        rules = {"verified_installed_source_path", "independent_mapping_iteration", "independent_generator_instruction"}
        for entry in self.proof["frame_correspondences"]:
            self.assertIn(entry["rule"], rules)
            if entry["rule"] == "verified_installed_source_path":
                self.assertIn(entry["source"], runtime.SOURCE_PATHS.values())
                self.assertEqual(entry["actual"]["function"], entry["captured"]["function"])
                self.assertEqual(entry["actual"]["line"], entry["captured"]["line"])
            else:
                self.assertEqual(entry["field"], "original_traceback")
                self.assertEqual((entry["event"], entry["index"]), (1, 3))
                self.assertEqual(entry["case"], "proposal:mapping_raises" if entry["primitive"] == "mapping"
                    else "proposal:obligation_exhaustion_raises")
        runtime_entries = [entry for entry in self.proof["frame_correspondences"]
            if entry["rule"] != "verified_installed_source_path"]
        mapping = self.proof["runtime_primitives"]["mapping"]["segment"]
        mapping_changed = len(mapping) != 2 or mapping[-1]["line"] != 883
        generator_changed = self.proof["runtime_primitives"]["obligations"]["frame"]["line"] != 822
        self.assertEqual(len(runtime_entries), int(mapping_changed) + int(generator_changed))

    def test_mapping_and_generator_witnesses_execute_source_bound_instructions(self):
        primitives = self.proof["runtime_primitives"]
        mapping = primitives["mapping"]
        self.assertGreater(len(mapping["raw_traceback"]), len(mapping["segment"]))
        self.assertEqual(mapping["stdlib"]["sha256"], oracle.sha(Path(mapping["stdlib"]["path"]).read_bytes()))
        self.assertEqual(mapping["segment"][-1]["function"], "__iter__")
        self.assertEqual(mapping["segment"][-1]["line"], mapping["instructions"][-1]["line"])
        generator = primitives["obligations"]
        self.assertIn(generator["frame"], generator["raw_traceback"])
        self.assertEqual(generator["instruction"]["opname"], "FOR_ITER")
        self.assertEqual(generator["frame"]["line"], generator["instruction"]["line"])
        for logical, origin in self.proof["source_origins"].items():
            self.assertEqual(origin["sha256"], self.frozen["source_files"][logical])
            self.assertEqual(origin["sha256"], oracle.sha(Path(origin["path"]).read_bytes()))

    def test_forged_frame_or_exception_cannot_use_a_runtime_correspondence(self):
        for mutation in ("installed-path", "user-line", "stdlib-line", "generator-line", "marker", "cause"):
            forged = deepcopy(self.current)
            cases = {case["id"]: case for case in forged["cases"]}
            error = cases["proposal:mapping_raises"]["events"][1]["exception"]
            if mutation == "installed-path":
                error["original_traceback"][2]["file"] = "another_package/pipeline.py"
            elif mutation == "user-line":
                error["required_user_traceback_tail"][-1]["line"] += 1
            elif mutation == "stdlib-line":
                next(frame for frame in error["original_traceback"] if frame["function"] == "__iter__")["line"] += 1
            elif mutation == "generator-line":
                cases["proposal:obligation_exhaustion_raises"]["events"][1]["exception"]["original_traceback"][3]["line"] += 1
            elif mutation == "marker":
                error["same_marker_object"] = False
            else:
                error["cause"] = "forged-exception"
            with self.subTest(mutation=mutation), self.assertRaisesRegex(AssertionError, "independent same-runtime"):
                runtime.compare_current(self.frozen, resign(forged))

    def test_loaded_code_must_match_exact_same_runtime_source_compilation(self):
        from biocompiler.ir.intent import freeze_json
        previous = freeze_json.__code__
        try:
            freeze_json.__code__ = previous.replace(co_stacksize=previous.co_stacksize + 1)
            with self.assertRaisesRegex(AssertionError, "same-runtime source compilation"):
                runtime.source_authority(self.frozen, oracle)
        finally:
            freeze_json.__code__ = previous

    def test_independent_capture_and_trace_observers_cannot_be_replaced(self):
        for name in ("capture", "trace_frames"):
            previous = getattr(oracle, name)
            try:
                setattr(oracle, name, lambda *args: self.current)
                with self.subTest(name=name), self.assertRaisesRegex(AssertionError, "Loaded oracle function"):
                    runtime.compare_current(self.frozen, self.current)
            finally:
                setattr(oracle, name, previous)

    def test_original_code_with_substituted_globals_cannot_manufacture_fresh_cases(self):
        previous = oracle.capture
        cases = {case["id"]: case for case in self.current["cases"]}
        substituted = dict(vars(oracle))
        for category in ("proposal", "input", "callback", "admission", "equality"):
            substituted[category + "_case"] = lambda name, category=category: cases[category + ":" + name]
        try:
            oracle.capture = FunctionType(previous.__code__, substituted)
            self.assertEqual(oracle.capture(), self.current)
            with self.assertRaisesRegex(AssertionError, "Loaded oracle function"):
                runtime.compare_current(self.frozen, self.current)
        finally:
            oracle.capture = previous
        from biocompiler.ir import intent
        previous = intent.freeze_json
        try:
            intent.freeze_json = FunctionType(previous.__code__, dict(vars(intent)))
            with self.assertRaisesRegex(AssertionError, "substituted module globals"):
                runtime.source_authority(self.frozen, oracle)
        finally:
            intent.freeze_json = previous

    def test_installed_source_layout_retains_all_raw_filename_differences(self):
        # Reproduce CI's installed-before-oracle import order without building
        # a wheel, compiling an extension, or changing the frozen source files.
        with tempfile.TemporaryDirectory(prefix="biocompiler-deferred-layout-") as directory:
            package = Path(directory) / "site-packages"
            shutil.copytree(oracle.ROOT / "src/biocompiler", package / "biocompiler",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            source = '''import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from biocompiler.compiler import pipeline
from biocompiler.ir import intent
from tools import capture_pipeline_deferred_semantics as oracle
from tools import check_pipeline_deferred_runtime as runtime
frozen=json.loads(oracle.OUTPUT.read_bytes()); current=oracle.capture()
proof=runtime.compare_current(frozen,current)
paths=[item for item in proof['frame_correspondences'] if item['rule']=='verified_installed_source_path']
assert proof['complete_raw_current']==current
assert proof['comparison_capture']==proof['expected_capture']
assert any(item['field']=='required_user_traceback_tail' for item in paths)
assert all(item['actual']['file'] in ('pipeline.py','intent.py') for item in paths)
assert all(Path(origin['path']).is_relative_to(Path(sys.argv[1]).resolve()) for origin in proof['source_origins'].values())
print(json.dumps({'cases':len(current['cases']),'paths':len(paths),'runtime':list(sys.version_info[:2])}))
'''
            env = dict(os.environ)
            env.pop("PYTHONPATH", None)
            result = subprocess.run([sys.executable, "-B", "-c", source, str(package)], cwd=oracle.ROOT,
                env=env, capture_output=True, text=True, timeout=30, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["cases"], 47)
            self.assertEqual(report["paths"], 55 if sys.version_info[:2] == (3, 11) else 54)


if __name__ == "__main__":
    unittest.main()
