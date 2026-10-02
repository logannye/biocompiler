"""Complete original locked-component observations and independently checked inputs."""
from __future__ import annotations
import ast
from collections import Counter
from dataclasses import MISSING, fields
import hashlib
import inspect
import json
from pathlib import Path
import unittest

from tools.realization_source_lineage import verify_captured_source

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/component-runtime-v1.json"
PIN = "aea8309d6efa172777f550d4a91cd3ebb7b40c301234fc7e90636fb4f466fcbf"
CAPTURE_PIN = "de5a18829b1d624262dddc12488e52c7b1898d1191ce09df53de13aa6d3c6114"
FILES = ("tests/test_component_pipeline.py", "tests/test_component_pipeline_audit.py",
    "tests/test_temporal_components.py", "tests/test_synthetic_design_workflows.py",
    "tests/test_component_registry.py", "tests/test_component_linker.py", "tests/test_component_audit.py",
    "tests/test_component_adapters.py", "tests/test_synthetic_build.py", "tests/test_human_admission.py",
    "tests/test_construct_assembly.py", "tests/test_construct_checker.py")
COUNTS = [9, 7, 15, 8, 11, 30, 12, 5, 11, 33, 10, 12]
KINDS = sorted(("input", "constant", "and", "or", "not", "compare", "select", "any_contact",
                "output", "held_for", "onset", "pulse", "memory"))


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
    def nonfinite(token): raise ValueError("Nonfinite JSON: " + token)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def plain(value):
    from collections.abc import Mapping
    if hasattr(value, "to_dict"): return plain(value.to_dict())
    if isinstance(value, Mapping): return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)): return [plain(item) for item in value]
    return value


def load():
    payload = CORPUS.read_bytes(); index = strict_json(payload)
    if index["inventory_fingerprint"] != PIN or fingerprint({k: v for k, v in index.items() if k != "inventory_fingerprint"}) != PIN:
        raise ValueError("Component corpus identity changed")
    if canonical(index) + b"\n" != payload: raise ValueError("Noncanonical corpus index")
    directory = CORPUS.with_suffix("")
    descriptors = {entry["id"]: entry for entry in index["documents"]}
    if len(descriptors) != len(index["documents"]): raise ValueError("Duplicate retained document")
    if {p.name for p in directory.iterdir()} != {identity + ".json" for identity in descriptors}: raise ValueError("Complete document inventory differs")
    documents = {}; total = len(payload)
    for identity, descriptor in descriptors.items():
        if len(identity) != 64 or any(c not in "0123456789abcdef" for c in identity): raise ValueError("Unsafe document identity")
        payload = (directory / (identity + ".json")).read_bytes(); total += len(payload)
        if len(payload) != descriptor["bytes"] or len(payload) > 16 * 1024 * 1024: raise ValueError("Document byte bound")
        value = strict_json(payload)
        if canonical(value) + b"\n" != payload or fingerprint(value) != identity: raise ValueError("Document content identity differs")
        pending = [(value, 0)]; count = 0
        while pending:
            node, depth = pending.pop(); count += 1
            if count > 250000 or depth > 128: raise ValueError("Document exceeds native JSON tree bound")
            if isinstance(node, dict): pending.extend((v, depth + 1) for v in node.values())
            elif isinstance(node, list): pending.extend((v, depth + 1) for v in node)
        documents[identity] = value
    if total != 64530645 or total > 64 * 1024 * 1024: raise ValueError("Complete corpus storage census differs")
    return index, descriptors, documents


class ComponentRuntimeCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index, cls.descriptors, cls.docs = load()
        cls.calls = {}
        for context in cls.index["contexts"]:
            for number, row in enumerate(cls.docs[context["ledger"]]["observations"]):
                identity = context["id"] + "/api/" + str(number)
                cls.calls[identity] = row

    def native_input(self, call, *, strict=True):
        native = call["native"]; value = self.docs[native["input"]]
        if native["input_format"] == "record": return value
        self.assertEqual(native["input_format"], "json_text")
        return strict_json(value) if strict else json.loads(value)

    def classes(self):
        from biocompiler.ir.components import ComponentLock
        from biocompiler.registry.components import RegistryLock, ComponentRegistry
        from biocompiler.ir.composition import (LifecycleInterval, CompositionInstance, Connection, Provider,
            DependencyBinding, ResourcePool, ResourceBinding, CompositionRequest)
        from biocompiler.verification.realization import InputBinding, OutputBinding, ObservationMap
        from biocompiler.ir.component_assembly import ComponentAssembly
        return {cls.__name__: cls for cls in (ComponentLock, RegistryLock, ComponentRegistry, LifecycleInterval,
            CompositionInstance, Connection, Provider, DependencyBinding, ResourcePool, ResourceBinding,
            CompositionRequest, InputBinding, OutputBinding, ObservationMap, ComponentAssembly)}

    def test_exact_original_method_source_and_call_census(self):
        expected = []
        for path, count in zip(FILES, COUNTS):
            tree = ast.parse((ROOT / path).read_text())
            methods = [path + "::" + cls.name + "." + method.name
                for cls in sorted((n for n in tree.body if isinstance(n, ast.ClassDef)), key=lambda x: x.name)
                for method in sorted((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")), key=lambda x: x.name)]
            self.assertEqual(len(methods), count); expected.extend(methods)
        self.assertEqual([c["id"] for c in self.index["contexts"] if c["kind"] == "original_method"], expected)
        coverage = self.index["coverage"]
        self.assertEqual((coverage["original_methods"], coverage["contexts"], coverage["api_calls"]), (163, 167, 52476))
        self.assertEqual(coverage["per_module_methods"], COUNTS)
        self.assertEqual(coverage["api_outcomes"], {"returned": 51495, "raised": 981})
        self.assertEqual(coverage["native_stages"], {"domain": 50597, "reconstruction": 134, "registry": 1650, "runtime": 93, "wire": 2})
        self.assertEqual(coverage["execution_outcomes"], {"reconstruct_component_mechanism": {"returned": 131, "raised": 3},
            "run_component_model": {"returned": 4}, "run_locked_mechanism": {"returned": 89}})
        self.assertEqual(Counter(c["api"] for c in self.calls.values()), coverage["api_census"])
        self.assertEqual(Counter(c["native"]["operation"] for c in self.calls.values()), coverage["native_operations"])
        self.assertEqual(coverage["unclassified_observations"], 0)
        self.assertEqual(len(self.descriptors), 4934)
        for source in self.index["source_files"]:
            verify_captured_source(ROOT, source)

    def test_every_native_input_is_derived_independently_from_complete_raw_arguments(self):
        classes = self.classes(); used = set(); seen = set()
        def use(identity, kind):
            self.assertEqual(self.descriptors[identity]["kind"], kind); used.add(identity); return self.docs[identity]
        for context in self.index["contexts"]:
            self.assertEqual(context["assertion_status"], "passed")
            rows = use(context["ledger"], "api_ledger")["observations"]
            self.assertEqual(len(rows), context["api_calls"])
            for number, call in enumerate(rows):
                identity = context["id"] + "/api/" + str(number)
                self.assertNotIn(identity, seen); seen.add(identity)
                if call["parent"] is not None: self.assertLess(call["parent"], number)
                self.assertLess(call["source"], len(self.index["source_locations"]))
                raw = json.loads(use(call["input"], "raw_arguments"))
                use(call["python_types"], "python_types")
                if call["outcome"] == "returned": use(call["result"], "record")
                else: self.assertEqual(set(call["error"]), {"module", "type", "message"})
                api = call["api"]
                if api == "ComponentRegistry.lock": expected = {"registry": raw["args"][0], "selections": raw["args"][1]}
                elif api == "ComponentRegistry.resolve": expected = {"registry": raw["args"][0], "lock": raw["args"][1]}
                elif api == "reconstruct_component_mechanism": expected = raw["args"][0]
                elif api in ("run_component_model", "run_locked_mechanism"):
                    expected = {"subject": raw["args"][0], "history": raw["args"][1],
                        "until": raw["kwargs"].get("until"), "until_supplied": "until" in raw["kwargs"]}
                    if api == "run_locked_mechanism":
                        reconstruction = self.calls[call["reconstruction_call"]]
                        self.assertEqual(reconstruction["api"], "reconstruct_component_mechanism")
                        self.assertEqual(reconstruction["result"], fingerprint(expected["subject"]))
                        self.assertEqual(self.docs[call["result"]]["program_fingerprint"], reconstruction["result"])
                else:
                    name, method = api.split(".")
                    if method == "__init__":
                        cls = classes[name]
                        expected = dict(inspect.signature(cls).bind(*raw["args"], **raw["kwargs"]).arguments)
                        for item in fields(cls):
                            if item.name in expected: continue
                            if item.default is not MISSING: expected[item.name] = plain(item.default)
                            elif item.default_factory is not MISSING: expected[item.name] = plain(item.default_factory())
                            else: self.fail("Missing original constructor parameter")
                        if hasattr(cls, "schema_version"): expected["schema_version"] = cls.schema_version
                        if name == "ComponentAssembly": expected["nodes"] = [{"id": item["id"], "kind": "component_instance"} for item in expected["composition"]["instances"]]
                    else:
                        self.assertEqual(raw["kwargs"], {}); self.assertEqual(len(raw["args"]), 1)
                        expected = json.loads(raw["args"][0]) if method == "from_json" else raw["args"][0]
                native = call["native"]
                use(native["input"], native["input_format"])
                # Raw nonfinite tokens stay nonfinite text; avoid NaN equality.
                encode = lambda v: json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=True)
                self.assertEqual(encode(self.native_input(call, strict=False)), encode(expected), identity)
                self.assertEqual(native["expected_code"] is None, call["outcome"] == "returned")
        for case in self.index["supplemental"]:
            for key in ("assembly", "mechanism", "runtime_input", "trace"): use(case[key], "record")
        for case in self.index["supplemental_rejections"]: use(case["input"], "record")
        self.assertEqual(used, set(self.docs)); self.assertEqual(len(seen), 52476)

    def test_complete_original_capture_is_preserved_byte_for_byte(self):
        original_calls = []; by_context = {c["id"]: c for c in self.index["contexts"]}
        for identity in self.index["capture_context_order"]:
            context = by_context[identity]
            for number, row in enumerate(self.docs[context["ledger"]]["observations"]):
                call = {"id": identity + "/api/" + str(number), "source_test": identity, "api": row["api"],
                    "parent_call": None if row["parent"] is None else identity + "/api/" + str(row["parent"]),
                    "source": self.index["source_locations"][row["source"]], "input": row["input"],
                    "python_types": self.docs[row["python_types"]], "outcome": row["outcome"]}
                for key in ("result", "error", "reconstruction_call"):
                    if key in row: call[key] = row[key]
                original_calls.append(call)
        contexts = [{k: v for k, v in c.items() if k not in ("ledger", "api_calls")} |
            {"api_calls": [c["id"] + "/api/" + str(i) for i in range(c["api_calls"])]} for c in self.index["contexts"]]
        extra = {"native_stages", "native_operations", "unclassified_observations", "supplemental_successes", "supplemental_rejections"}
        captured = {"schema_version": "biocompiler.component_runtime_baseline_capture.v1", "source_files": self.index["source_files"],
            "contexts": contexts, "api_calls": original_calls,
            "documents": {identity: {"kind": self.descriptors[identity]["kind"], "value": self.docs[identity]} for identity in self.index["original_documents"]},
            "coverage": {k: v for k, v in self.index["coverage"].items() if k not in extra}}
        self.assertEqual(fingerprint(captured), CAPTURE_PIN)
        self.assertEqual(self.index["original_capture_fingerprint"], CAPTURE_PIN)

    def test_all_domain_and_registry_observations_replay(self):
        classes = self.classes()
        from biocompiler.ir.component_contracts import ComponentRecord
        for identity, call in self.calls.items():
            native = call["native"]; operation = native["operation"]
            if native["native_stage"] in ("runtime", "reconstruction"): continue
            if native["native_stage"] == "wire":
                self.assertEqual(native["expected_code"], "invalid_json")
                with self.assertRaises(ValueError): self.native_input(call)
                continue
            data = self.native_input(call)
            try:
                if operation == "registry_lock":
                    registry = classes["ComponentRegistry"].from_dict(data["registry"])
                    actual = registry.lock({key: ComponentRecord.from_dict(value) for key, value in data["selections"].items()})
                elif operation == "registry_resolve":
                    actual = classes["ComponentRegistry"].from_dict(data["registry"]).resolve(classes["RegistryLock"].from_dict(data["lock"]))
                else: actual = classes[operation].from_dict(data)
            except Exception as error:
                self.assertEqual(call["outcome"], "raised", identity)
                self.assertEqual({"module": type(error).__module__, "type": type(error).__qualname__, "message": str(error)}, call["error"], identity)
            else:
                self.assertEqual(call["outcome"], "returned", identity)
                self.assertEqual(canonical(plain(actual)), canonical(self.docs[call["result"]]), identity)

    def test_actual_locked_reconstruction_and_full_runtime_traces_replay(self):
        from biocompiler.ir.component_assembly import ComponentAssembly
        from biocompiler.ir.mechanism import MechanismProgram
        from biocompiler.models.components import reconstruct_component_mechanism, run_component_model
        from biocompiler.models.synthetic import ModelInputFrame, run_model
        kinds = set(); executed_kinds = set(); counts = Counter()
        for identity, call in self.calls.items():
            operation = call["native"]["operation"]
            if operation not in ("reconstruct", "run_component_model", "run_locked_mechanism"): continue
            data = self.native_input(call)
            try:
                if operation == "reconstruct": actual = reconstruct_component_mechanism(ComponentAssembly.from_dict(data))
                else:
                    frames = [ModelInputFrame.from_dict(frame) for frame in data["history"]]
                    options = {"until": data["until"]} if data["until_supplied"] else {}
                    actual = (run_component_model(ComponentAssembly.from_dict(data["subject"]), frames, **options)
                        if operation == "run_component_model" else run_model(MechanismProgram.from_dict(data["subject"]), frames, **options))
            except Exception as error:
                self.assertEqual(call["outcome"], "raised", identity)
                self.assertEqual({"module": type(error).__module__, "type": type(error).__qualname__, "message": str(error)}, call["error"], identity)
            else:
                self.assertEqual(call["outcome"], "returned", identity)
                self.assertEqual(canonical(actual.to_dict()), canonical(self.docs[call["result"]]), identity)
                if operation == "reconstruct": kinds.update(node.kind for node in actual.nodes)
                if operation == "run_locked_mechanism": executed_kinds.update(node["kind"] for node in data["subject"]["nodes"])
            counts[operation] += 1
        self.assertEqual(counts, {"reconstruct": 134, "run_component_model": 4, "run_locked_mechanism": 89})
        self.assertEqual(sorted(kinds), sorted(set(KINDS) - {"compare"}))
        self.assertEqual(executed_kinds, kinds)

    def test_new_literals_cover_missing_comparison_and_preserve_component_profile(self):
        from biocompiler.ir.component_assembly import ComponentAssembly
        from biocompiler.ir.component_contracts import SyntheticOperatorModel
        from biocompiler.models.components import reconstruct_component_mechanism, run_component_model
        from biocompiler.models.synthetic import ModelInputFrame
        self.assertEqual(len(self.index["supplemental"]), 1)
        kinds = set(self.index["coverage"]["successful_reconstruction_kinds"])
        for case in self.index["supplemental"]:
            self.assertEqual(case["origin"], "explicit_new_literal_not_original_assertion")
            assembly = ComponentAssembly.from_dict(self.docs[case["assembly"]])
            mechanism = reconstruct_component_mechanism(assembly)
            self.assertEqual(fingerprint(mechanism.to_dict()), case["mechanism"])
            kinds.update(node.kind for node in mechanism.nodes)
            data = self.docs[case["runtime_input"]]
            trace = run_component_model(assembly, [ModelInputFrame.from_dict(v) for v in data["history"]], until=data["until"])
            self.assertEqual(fingerprint(trace.to_dict()), case["trace"])
            self.assertEqual([frame.values["result"] for frame in trace.frames], [False, True])
        self.assertEqual(sorted(kinds), KINDS)
        self.assertEqual(len(self.index["supplemental_rejections"]), 1)
        for case in self.index["supplemental_rejections"]:
            self.assertEqual(self.docs[case["input"]]["operation"], "delay")
            with self.assertRaisesRegex(ValueError, "Unsupported synthetic component operation"):
                SyntheticOperatorModel.from_dict(self.docs[case["input"]])
        self.assertEqual(len(self.index["source_ledger"]["monkeypatches"]), 15)
        self.assertTrue(all(row["disposition"].startswith("original_") for row in self.index["source_ledger"]["monkeypatches"]))
        self.assertEqual(self.index["coverage"]["subprocess_invocations"], 0)
