"""Complete immutable observations for the independent candidate runtime."""
from __future__ import annotations
import ast
from collections import Counter
from copy import deepcopy
import hashlib
import inspect
from dataclasses import MISSING, fields
import json
from pathlib import Path
import unittest

from tools.realization_source_lineage import verify_captured_source

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/candidate-runtime-v1.json"
EXPECTED_PIN = "e29da7150c3a80621967d332f8bb03065b07ebcb30b58b30fc8029e296393599"
FILES = ("tests/test_synthetic_model.py", "tests/test_synthetic_temporal_model.py",
         "tests/test_payload_requirements.py", "tests/test_temporal_generation.py",
         "tests/test_temporal_components.py", "tests/test_synthetic_generation.py",
         "tests/test_realization_checker.py", "tests/test_realization_integration.py")
COUNTS = [23, 27, 21, 15, 15, 17, 31, 6]
PRIMARY_PINS = {"api_calls": "ec523f966b17acc2444c8514a30a61724a562e388a5b83c355f0b82e83c04f05",
                "runs": "2792d14c94ee0530943e990d0a306bfbe2fa1dadb2fc27a9678d440c5af55fa9",
                "source_tests": "a64141cffc9b3734303caca5320a5c9b42b75e45319684744838a6d008e8d81f"}
KINDS = sorted(("input", "constant", "and", "or", "not", "compare", "select", "delay",
                "held_for", "onset", "pulse", "memory", "output", "any_contact"))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def fingerprint(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError("Duplicate JSON key")
            result[key] = value
        return result
    def invalid(value): raise ValueError("Nonfinite JSON token: " + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def load(path=CORPUS, pin=EXPECTED_PIN):
    index = strict_json(path.read_bytes())
    if index.get("inventory_fingerprint") != pin or fingerprint({k: v for k, v in index.items() if k != "inventory_fingerprint"}) != pin:
        raise ValueError("Corpus inventory identity")
    descriptors = {entry["id"]: entry for entry in index["documents"]}
    if len(descriptors) != len(index["documents"]): raise ValueError("Duplicate document")
    if {p.name for p in path.with_suffix("").iterdir()} != {key + ".json" for key in descriptors}: raise ValueError("Document inventory")
    documents = {}; total = path.stat().st_size
    for identity, entry in descriptors.items():
        if len(identity) != 64 or any(x not in "0123456789abcdef" for x in identity): raise ValueError("Unsafe document identity")
        payload = (path.with_suffix("") / (identity + ".json")).read_bytes()
        total += len(payload)
        if len(payload) != entry["bytes"] or len(payload) > 16 * 1024 * 1024: raise ValueError("Document byte bound")
        raw = strict_json(payload)
        if fingerprint(raw) != identity or canonical(raw) + b"\n" != payload: raise ValueError("Document identity")
        pending = [(raw, 0)]; count = 0
        while pending:
            value, depth = pending.pop(); count += 1
            if count > 250000 or depth > 128: raise ValueError("Document tree bound")
            if isinstance(value, dict): pending.extend((item, depth + 1) for item in value.values())
            elif isinstance(value, list): pending.extend((item, depth + 1) for item in value)
        documents[identity] = raw
    if total > 32 * 1024 * 1024: raise ValueError("Corpus total bound")
    return index, descriptors, documents


class CandidateRuntimeCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index, cls.descriptors, cls.documents = load()
        cls.calls = [call for context in cls.index["contexts"] for call in cls.documents[context["ledger"]]]

    def test_exact_inventory_census_and_every_original_method(self):
        coverage = self.index["coverage"]
        self.assertEqual(coverage["per_module_methods"], COUNTS)
        self.assertEqual((coverage["original_methods"], coverage["contexts"], coverage["api_calls"], coverage["run_calls"]), (155, 158, 12487, 549))
        self.assertEqual(coverage["domain_outcomes"], {"returned": 11809, "raised": 129})
        self.assertEqual(coverage["run_outcomes"], {"returned": 537, "raised": 12})
        self.assertEqual(coverage["native_stages"], {"domain": 11933, "runtime": 549, "wire": 5})
        self.assertEqual(coverage["native_operations"], {"frame": 12, "input_frame": 2705, "node": 7855, "program": 815, "run_model": 549, "trace": 551})
        self.assertEqual(coverage["unclassified_observations"], 0)
        expected = []
        for path, count in zip(FILES, COUNTS):
            tree = ast.parse((ROOT / path).read_text())
            methods = [path + "::" + cls.name + "." + method.name
                       for cls in sorted((n for n in tree.body if isinstance(n, ast.ClassDef)), key=lambda x: x.name)
                       for method in sorted((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")), key=lambda x: x.name)]
            self.assertEqual(len(methods), count); expected.extend(methods)
        actual = [c["id"] for c in self.index["contexts"] if c["kind"] == "original_method"]
        self.assertEqual(actual, expected)
        for record in self.index["source_files"]:
            verify_captured_source(ROOT, record)

    def test_complete_ledgers_are_reachable_and_runtime_arguments_are_identical(self):
        from biocompiler.ir.mechanism import MechanismNode, MechanismProgram
        from biocompiler.models.synthetic import ModelInputFrame, ModelFrame, ModelTrace
        classes = {cls.__name__: cls for cls in (MechanismNode, MechanismProgram, ModelInputFrame, ModelFrame, ModelTrace)}
        used = set(); call_ids = set(); contexts = {c["id"]: c for c in self.index["contexts"]}
        runs = {r["api_call"]: r for r in self.index["runs"]}
        def use(identity, kind):
            self.assertEqual(self.descriptors[identity]["kind"], kind); used.add(identity)
            return self.documents[identity]
        for context in contexts.values():
            self.assertEqual(context["assertion_status"], "passed")
            ledger = use(context["ledger"], "api_ledger")
            self.assertEqual(len(ledger), context["api_calls"])
            for number, call in enumerate(ledger):
                self.assertEqual(call["id"], context["id"] + "/api/" + str(number))
                self.assertNotIn(call["id"], call_ids)
                if call["parent_call"] is not None: self.assertIn(call["parent_call"], call_ids)
                call_ids.add(call["id"])
                raw = json.loads(use(call["input"], "raw_arguments"))
                if call["outcome"] == "returned": use(call["result"], "record")
                else: self.assertEqual(set(call["error"]), {"module", "type", "message"})
                if call["api"] == "run_model":
                    run = runs[call["id"]]
                    self.assertEqual(call["native"], {"operation": "run_model", "runtime_case": call["id"]})
                    self.assertEqual(run["source_test"], context["id"])
                    program = use(run["program"], "record"); data = use(run["input"], "runtime_input")
                    self.assertEqual(canonical(raw["args"]), canonical([program, data["history"]]))
                    self.assertEqual(canonical(raw["kwargs"]), canonical({"until": data["until"]} if data["until_supplied"] else {}))
                    self.assertEqual(run["outcome"], call["outcome"])
                    if run["expected"] is not None:
                        self.assertEqual(run["expected"], call["result"])
                        trace = use(run["expected"], "record")
                        self.assertEqual(trace["program_fingerprint"], run["program"])
                    else:
                        self.assertEqual(run["error"], call["error"]); self.assertTrue(run["expected_code"])
                else:
                    native_text = use(call["native"]["input"], "json_text")
                    class_name, method = call["api"].split(".")
                    if method == "__init__":
                        cls = classes[class_name]
                        bound = inspect.signature(cls).bind(*raw["args"], **raw["kwargs"])
                        original_fields = dict(bound.arguments)
                        for item in fields(cls):
                            if item.name in original_fields: continue
                            if item.default is not MISSING: original_fields[item.name] = item.default
                            elif item.default_factory is not MISSING: original_fields[item.name] = item.default_factory()
                            else: self.fail("Unretained required constructor parameter: " + item.name)
                        if class_name == "ModelTrace": original_fields["schema_version"] = cls.schema_version
                        exact_input = json.dumps(original_fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=True)
                    else:
                        self.assertEqual(len(raw["args"]), 1); self.assertEqual(raw["kwargs"], {})
                        if method == "from_json": exact_input = raw["args"][0]
                        else:
                            self.assertEqual(method, "from_dict")
                            exact_input = json.dumps(raw["args"][0], sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=True)
                    self.assertEqual(native_text, exact_input, call["id"])
                    self.assertEqual(call["native"]["expected_code"] is None, call["outcome"] == "returned")
        self.assertEqual(used, set(self.documents))
        self.assertEqual(len(runs), 549); self.assertEqual(len(call_ids), 12487)

    def test_original_fifty_method_capture_is_preserved_byte_for_byte(self):
        actual = {"api_calls": [], "runs": [], "source_tests": []}
        for context in self.index["contexts"]:
            if context["id"].split("::")[0] not in FILES[:2]: continue
            ledger = self.documents[context["ledger"]]
            actual["source_tests"].append({"id": context["id"], "assertion_status": context["assertion_status"],
                                           "api_calls": [c["id"] for c in ledger], "run_calls": context["run_calls"]})
            for original in ledger:
                call = deepcopy(original); call.pop("native")
                call["input_json"] = self.documents[call.pop("input")]
                if call["outcome"] == "returned":
                    call["result_fingerprint"] = call["result"]; call["result"] = self.documents[call["result"]]
                actual["api_calls"].append(call)
        for original in self.index["runs"]:
            if original["source_test"].split("::")[0] not in FILES[:2]: continue
            run = deepcopy(original); run["program_id"] = run.pop("program"); run.update(self.documents[run.pop("input")])
            run.pop("expected_code"); expected = run.pop("expected")
            if expected is not None: run.update(trace_fingerprint=expected, trace=self.documents[expected])
            actual["runs"].append(run)
        for key, pin in PRIMARY_PINS.items(): self.assertEqual(fingerprint(actual[key]), pin, key)
        self.assertEqual(self.index["coverage"]["original_primary_pins"], PRIMARY_PINS)

    def test_every_operation_has_successful_complete_runtime_witness(self):
        kinds = set(); programs = set()
        for run in self.index["runs"]:
            programs.add(run["program"])
            if run["expected"] is not None:
                kinds.update(n["kind"] for n in self.documents[run["program"]]["nodes"])
        self.assertEqual(sorted(kinds), KINDS); self.assertEqual(len(programs), 73)
        self.assertEqual(self.index["coverage"]["successful_run_kinds"], KINDS)
        for child in self.index["subprocesses"]:
            self.assertEqual(child["returncode"], 0); self.assertEqual(child["stderr"], "")
            self.assertEqual(set(json.loads(child["stdout"])), {"responsive", "silent", "late"})
        self.assertEqual([c["hash_seed"] for c in self.index["subprocesses"]], ["1", "37"])
        self.assertEqual(self.index["subprocesses"][0]["stdout"], self.index["subprocesses"][1]["stdout"])

    def test_original_runtime_inputs_replay_with_exact_trace_or_diagnostic(self):
        from biocompiler.ir.mechanism import MechanismProgram
        from biocompiler.models.synthetic import ModelInputFrame, run_model
        for case in self.index["runs"]:
            data = self.documents[case["input"]]
            program = MechanismProgram.from_dict(self.documents[case["program"]])
            frames = [ModelInputFrame.from_dict(value) for value in data["history"]]
            try: actual = run_model(program, frames, **({"until": data["until"]} if data["until_supplied"] else {}))
            except Exception as error:
                self.assertIsNone(case["expected"], case["id"])
                self.assertEqual({"module": type(error).__module__, "type": type(error).__qualname__, "message": str(error)}, case["error"])
            else:
                self.assertIsNotNone(case["expected"], case["id"])
                self.assertEqual(canonical(actual.to_dict()), canonical(self.documents[case["expected"]]), case["id"])

    def test_every_serializable_domain_observation_replays_with_original_result(self):
        from biocompiler.ir.mechanism import MechanismNode, MechanismProgram
        from biocompiler.models.synthetic import ModelInputFrame, ModelFrame, ModelTrace
        classes = {"node": MechanismNode, "program": MechanismProgram, "input_frame": ModelInputFrame, "frame": ModelFrame, "trace": ModelTrace}
        for call in self.calls:
            native = call["native"]
            if native["operation"] == "run_model": continue
            text = self.documents[native["input"]]
            try: actual = classes[native["operation"]].from_dict(strict_json(text))
            except Exception:
                self.assertEqual(call["outcome"], "raised", call["id"])
            else:
                self.assertEqual(call["outcome"], "returned", call["id"])
                self.assertEqual(canonical(actual.to_dict()), canonical(self.documents[call["result"]]), call["id"])

    def test_nonfinite_and_monkeypatch_boundaries_are_explicit(self):
        differences = [c for c in self.calls if c["native"].get("compatibility") == "nonfinite_python_values_rejected_at_strict_json_boundary"]
        self.assertEqual(len(differences), 4)
        self.assertEqual(Counter(c["native"]["source_stage"] for c in differences), {"constructor": 3, "json_import": 1})
        for call in differences:
            self.assertEqual(call["native"]["native_stage"], "wire")
            self.assertEqual(call["native"]["expected_code"], "invalid_json")
            with self.assertRaises(ValueError): strict_json(self.documents[call["native"]["input"]])
        patches = self.index["source_ledger"]["monkeypatches"]
        self.assertEqual(len(patches), 6)
        self.assertTrue(all(p["disposition"].startswith("original_") for p in patches))
        self.assertEqual(self.index["claim_scope"], "independent_synthetic_candidate_execution_only_no_biological_evidence")
        self.assertNotEqual(canonical([False, 0, 0.0, -0.0]), canonical([0, False, -0.0, 0.0]))
