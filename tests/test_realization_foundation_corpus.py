"""Complete unchanged realization observations, with explicit acceptance gaps."""
from __future__ import annotations
import ast
from collections import Counter
from dataclasses import MISSING, fields
import hashlib
import inspect
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/realization-foundation-v1.json"
PIN = "ac1499688ec6f0eca41398134b9421de9f95ffe9405422332c2bf43b04db32f8"
CAPTURE_PIN = "152a87971fcaa3d6a47eb0320b1c2ed9081f61032511e3179faba22b4fdb59a2"
DEFERRED = {"check_realization", "realization_dependencies", "check_component_behavior", "check_component_assembly"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def fingerprint(value): return hashlib.sha256(canonical(value)).hexdigest()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError("duplicate_key")
            result[key] = value
        return result
    def invalid(_): raise ValueError("invalid_json")
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    canonical(value)
    return value


def plain(value):
    from collections.abc import Mapping
    if hasattr(value, "to_dict"): return plain(value.to_dict())
    if hasattr(value, "changed_dependencies"): return {"changed_dependencies": plain(value.changed_dependencies)}
    if isinstance(value, Mapping): return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)): return [plain(item) for item in value]
    return value


def load():
    payload = CORPUS.read_bytes(); index = strict_json(payload)
    if index["inventory_fingerprint"] != PIN or fingerprint({k: v for k, v in index.items() if k != "inventory_fingerprint"}) != PIN:
        raise ValueError("Realization corpus pin differs")
    if canonical(index) + b"\n" != payload: raise ValueError("Noncanonical corpus")
    descriptors = {item["id"]: item for item in index["documents"]}; directory = CORPUS.with_suffix("")
    if len(descriptors) != 19458 or len(descriptors) != len(index["documents"]): raise ValueError("Document census differs")
    if {path.name for path in directory.iterdir()} != {key + ".json" for key in descriptors}: raise ValueError("Extra or missing fixture")
    docs = {}; total = len(payload)
    def bounds(value):
        pending = [(value, 0)]; count = 0
        while pending:
            value, depth = pending.pop(); count += 1
            if depth > 128 or count > 250000: raise ValueError("Native JSON tree bound exceeded")
            if isinstance(value, dict): pending.extend((item, depth + 1) for item in value.values())
            elif isinstance(value, list): pending.extend((item, depth + 1) for item in value)
    bounds(index)
    for key, descriptor in descriptors.items():
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key): raise ValueError("Unsafe content address")
        payload = (directory / (key + ".json")).read_bytes(); total += len(payload)
        if len(payload) != descriptor["bytes"] or len(payload) > 16 * 1024 * 1024: raise ValueError("Fixture bytes differ")
        value = strict_json(payload); bounds(value)
        if canonical(value) + b"\n" != payload or fingerprint(value) != key: raise ValueError("Fixture content differs")
        docs[key] = value
    if total != 103174628 or total > 256 * 1024 * 1024: raise ValueError("Complete storage census differs")
    return index, descriptors, docs


class RealizationFoundationCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index, cls.descriptors, cls.docs = load()
        cls.calls = {context["id"] + "/api/" + str(number): call
            for context in cls.index["contexts"]
            for number, call in enumerate(cls.docs[context["ledger"]]["observations"])}

    def test_complete_source_assertion_call_and_stage_census(self):
        from tools.freeze_realization_acceptance import FILES, METHOD_COUNTS
        expected = []
        for path, count in zip(FILES, METHOD_COUNTS):
            tree = ast.parse((ROOT / path).read_text())
            methods = [path + "::" + cls.name + "." + method.name
                for cls in sorted((n for n in tree.body if isinstance(n, ast.ClassDef)), key=lambda x: x.name)
                for method in sorted((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")), key=lambda x: x.name)]
            self.assertEqual(len(methods), count); expected.extend(methods)
        self.assertEqual([c["id"] for c in self.index["contexts"] if c["kind"] == "original_method"], expected)
        coverage = self.index["coverage"]
        self.assertEqual((len(expected), len(self.index["contexts"]), len(self.calls)), (324, 332, 70019))
        self.assertEqual(coverage["per_module_methods"], METHOD_COUNTS)
        self.assertEqual(Counter(c["api"] for c in self.calls.values()), coverage["api_census"])
        self.assertEqual(Counter(c["outcome"] for c in self.calls.values()), {"returned": 67895, "raised": 2124})
        self.assertEqual(Counter(c["native"]["operation"] for c in self.calls.values()), coverage["native_operations"])
        self.assertEqual(Counter(c["native"]["native_stage"] for c in self.calls.values()), {
            "domain": 60996, "admission": 5744, "method": 63, "wire": 14,
            "python_type_boundary": 1, "python_wire_boundary": 3, "deferred_acceptance": 3198})
        self.assertEqual(coverage["unclassified_observations"], 0)
        for entry in self.index["source_files"]:
            self.assertEqual(hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest(), entry["sha256"], entry["path"])
        self.assertEqual(len(self.index["subprocesses"]), 2)
        self.assertEqual({item["invocation"]["hash_seed"] for item in self.index["subprocesses"]}, {"1", "37"})
        for child in self.index["subprocesses"]:
            self.assertEqual(child["invocation"]["returncode"], 0)
            self.assertTrue(child["invocation"]["script"] and child["invocation"]["stdout"])
            self.assertTrue(all(c["kind"] == "subprocess" and c["api_calls"] for c in child["contexts"]))

    def test_native_inputs_independently_rebuild_complete_arguments_defaults_and_types(self):
        from tools.freeze_realization_acceptance import CLASSES, FUNCTIONS
        classes = {cls.__name__: cls for cls in CLASSES}; functions = {f.__name__: f for f in FUNCTIONS}
        used = {self.index["capture_call_order"]}
        def use(identity, kind):
            self.assertEqual(self.descriptors[identity]["kind"], kind); used.add(identity); return self.docs[identity]
        encoded = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=True)
        for context in self.index["contexts"]:
            self.assertEqual(context["assertion_status"], "passed")
            rows = use(context["ledger"], "api_ledger")["observations"]
            self.assertEqual(len(rows), context["api_calls"])
            for number, call in enumerate(rows):
                raw = json.loads(use(call["input"], "raw_arguments")); types = use(call["python_types"], "python_types")
                if call["parent"] is not None: self.assertLess(call["parent"], number)
                self.assertLess(call["source"], len(self.index["source_locations"]))
                if call["outcome"] == "returned": use(call["result"], call["result_format"])
                else: self.assertEqual(set(call["error"]), {"module", "type", "message"})
                if "properties" in call: use(call["properties"], "record")
                native = call["native"]; api = call["api"]
                if api in DEFERRED:
                    self.assertEqual(native, {"operation": api, "source_stage": "deferred_acceptance", "native_stage": "deferred_acceptance",
                        "obligation": "independent_complete_finite_history_acceptance_not_implemented_by_foundation"})
                    continue
                if "." not in api:
                    bound = inspect.signature(functions[api]).bind(*raw["args"], **raw["kwargs"]); bound.apply_defaults()
                    expected = plain(dict(bound.arguments))
                else:
                    name, method = api.split(".")
                    if method == "__init__":
                        cls = classes[name]; bound = inspect.signature(cls).bind(*raw["args"], **raw["kwargs"]); bound.apply_defaults()
                        expected = plain(dict(bound.arguments))
                        if name == "DependencySnapshot": expected = expected["values"]
                        else:
                            for item in fields(cls):
                                if item.name in expected: continue
                                if item.default is not MISSING: expected[item.name] = plain(item.default)
                                elif item.default_factory is not MISSING: expected[item.name] = plain(item.default_factory())
                                else: self.fail("Missing original constructor argument")
                            if hasattr(cls, "schema_version") and "schema_version" not in expected: expected["schema_version"] = cls.schema_version
                            expected.update(getattr(cls, "_fixed_fields", {}))
                    elif method in ("from_dict", "from_json"):
                        self.assertEqual(raw["kwargs"], {}); self.assertEqual(len(raw["args"]), 1)
                        expected = raw["args"][0]
                        if method == "from_json":
                            self.assertEqual(use(native["input"], native["input_format"]), expected)
                            continue
                    elif method in ("contains", "accepts"):
                        scalar = any(t["path"] == ["args", 1] and t["type"] == "biocompiler.semantics.types.ScalarLiteral" for t in types)
                        expected = {"subject": raw["args"][0], "value": raw["args"][1], "value_kind": "scalar_literal" if scalar else "json", **raw["kwargs"]}
                    else:
                        self.assertIn(method, ("changed", "freshness", "is_fresh", "is_current"))
                        expected = {"subject": raw["args"][0], "current": raw["args"][1]}
                actual = json.loads(use(native["input"], native["input_format"]))
                self.assertEqual(encoded(actual), encoded(expected), api)
                if "counterpart" in call:
                    counterpart = call["counterpart"]
                    self.assertEqual(native["native_stage"], "python_type_boundary")
                    if counterpart["outcome"] == "returned": use(counterpart["result"], "record")
        self.assertEqual(used, set(self.docs))

    def test_capture_reconstructs_byte_exact_including_children_properties_and_failures(self):
        contexts = self.index["contexts"]
        order = self.docs[self.index["capture_call_order"]]
        self.assertEqual(len(order), 70019); self.assertEqual(len({tuple(item) for item in order}), 70019)
        original = []
        for context_number, number in order:
            context = contexts[context_number]; row = self.docs[context["ledger"]]["observations"][number]
            call = {"id": context["id"] + "/api/" + str(number), "source_test": context["id"], "api": row["api"],
                "parent_call": None if row["parent"] is None else context["id"] + "/api/" + str(row["parent"]),
                "source": self.index["source_locations"][row["source"]], "input": row["input"],
                "python_types": self.docs[row["python_types"]], "outcome": row["outcome"]}
            for key in ("result", "result_format", "error", "properties"):
                if key in row: call[key] = row[key]
            original.append(call)
        capture = {"schema_version": "biocompiler.realization_acceptance_baseline_capture.v1",
            "source_files": self.index["source_files"],
            "contexts": [{k: v for k, v in c.items() if k not in ("ledger", "api_calls")} |
                {"api_calls": [c["id"] + "/api/" + str(i) for i in range(c["api_calls"])]} for c in contexts],
            "subprocesses": self.index["subprocesses"], "api_calls": original,
            "documents": {key: {"kind": self.descriptors[key]["kind"], "value": self.docs[key]} for key in self.index["original_documents"]},
            "coverage": {k: v for k, v in self.index["coverage"].items() if k not in ("native_stages", "native_operations", "unclassified_observations")}}
        self.assertEqual(fingerprint(capture), CAPTURE_PIN)
        self.assertEqual(self.index["original_capture_fingerprint"], CAPTURE_PIN)

    def test_all_implemented_records_methods_and_admission_outputs_replay_fully(self):
        from tools.freeze_realization_acceptance import python_decode
        stages = Counter()
        for identity, call in self.calls.items():
            native = call["native"]; stage = native["native_stage"]; stages[stage] += 1
            if stage == "deferred_acceptance": continue
            raw = self.docs[native["input"]]
            if stage in ("wire", "python_wire_boundary"):
                with self.assertRaises((ValueError, UnicodeEncodeError), msg=identity): strict_json(raw)
                if stage == "python_wire_boundary": self.assertEqual(call["outcome"], "returned")
                continue
            expected = call.get("counterpart", call)
            if "serialized_error" in call:
                self.assertEqual(native["source_stage"], "constructor")
                self.assertEqual(call["outcome"], "raised")
                self.assertNotEqual(call["serialized_error"], call["error"])
                expected = {**call, "error": call["serialized_error"]}
            try: result = python_decode(native["operation"], strict_json(raw))
            except Exception as error:
                self.assertEqual(expected["outcome"], "raised", identity)
                self.assertEqual({"module": type(error).__module__, "type": type(error).__qualname__, "message": str(error)}, expected["error"], identity)
            else:
                self.assertEqual(expected["outcome"], "returned", identity)
                self.assertEqual(canonical(plain(result)), canonical(self.docs[expected["result"]]), identity)
                if "properties" in call and stage != "python_type_boundary":
                    actual = {key: plain(getattr(result, key)) for key in self.docs[call["properties"]]}
                    self.assertEqual(canonical(actual), canonical(self.docs[call["properties"]]), identity)
        self.assertEqual(stages, self.index["coverage"]["native_stages"])


if __name__ == "__main__": unittest.main()
