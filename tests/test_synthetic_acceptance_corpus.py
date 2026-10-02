"""Complete original synthetic and assembly acceptance observations."""
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
CORPUS = ROOT / "tests/conformance/synthetic-acceptance-v1.json"
PIN = "d32009a03f0af00de4da60f0244c210ba15b9ff89e828ea56c82b5f9e4a73331"
CAPTURE_PIN = "9b17701d25eb2dfe1ecef87eccc46dc506475ae34d90fcce8bcda88b6e058f29"
DEFERRED = {"generate_synthetic", "_generate_synthetic", "select_synthetic", "adapt_synthetic_components"}
EXPECTED_STAGES = {'assembly_acceptance': 52, 'catalog': 38534, 'checker_version_mutation': 5, 'component_behavior': 85, 'deferred_acceptance': 2372, 'dependencies': 1993, 'domain': 2733, 'realization': 1079, 'synthetic_acceptance': 905}


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
        raise ValueError("Synthetic acceptance corpus pin differs")
    if canonical(index) + b"\n" != payload: raise ValueError("Noncanonical corpus")
    descriptors = {item["id"]: item for item in index["documents"]}; directory = CORPUS.with_suffix("")
    if len(descriptors) != 4910 or len(descriptors) != len(index["documents"]): raise ValueError("Document census differs")
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
    if total != 109400531 or total > 256 * 1024 * 1024: raise ValueError("Complete storage census differs")
    return index, descriptors, docs


class SyntheticAcceptanceCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index, cls.descriptors, cls.docs = load()
        cls.calls = {context["id"] + "/api/" + str(number): call
            for context in cls.index["contexts"]
            for number, call in enumerate(cls.docs[context["ledger"]]["observations"])}

    def test_capture_profiles_do_not_mutate_each_others_inventory(self):
        from tools import freeze_realization_acceptance as original
        before = (original.FILES, tuple(original.METHOD_COUNTS), original.CLASSES,
                  original.PROPERTY_NAMES, original.CORPUS)
        from tools.freeze_synthetic_acceptance import foundation
        self.assertIsNot(original, foundation)
        self.assertEqual(sum(original.METHOD_COUNTS), 324)
        self.assertEqual(sum(foundation.METHOD_COUNTS), 373)
        self.assertEqual(before, (original.FILES, tuple(original.METHOD_COUNTS), original.CLASSES,
                                original.PROPERTY_NAMES, original.CORPUS))

    def test_complete_source_assertion_call_and_stage_census(self):
        from tools.freeze_synthetic_acceptance import foundation
        FILES, METHOD_COUNTS = foundation.FILES, foundation.METHOD_COUNTS
        expected = []
        for path, count in zip(FILES, METHOD_COUNTS):
            tree = ast.parse((ROOT / path).read_text())
            methods = [path + "::" + cls.name + "." + method.name
                for cls in sorted((n for n in tree.body if isinstance(n, ast.ClassDef)), key=lambda x: x.name)
                for method in sorted((n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")), key=lambda x: x.name)]
            self.assertEqual(len(methods), count); expected.extend(methods)
        self.assertEqual([c["id"] for c in self.index["contexts"] if c["kind"] == "original_method"], expected)
        coverage = self.index["coverage"]
        self.assertEqual((len(expected), len(self.index["contexts"]), len(self.calls)), (373, 381, 47758))
        self.assertEqual(coverage["per_module_methods"], METHOD_COUNTS)
        self.assertEqual(Counter(c["api"] for c in self.calls.values()), coverage["api_census"])
        self.assertEqual(Counter(c["outcome"] for c in self.calls.values()), {"returned": 47673, "raised": 85})
        self.assertEqual(Counter(c["native"]["operation"] for c in self.calls.values()), coverage["native_operations"])
        self.assertEqual(Counter(c["native"]["native_stage"] for c in self.calls.values()), EXPECTED_STAGES)
        self.assertEqual(coverage["unclassified_observations"], 0)
        for entry in self.index["source_files"]:
            verify_captured_source(ROOT, entry)
        self.assertEqual(len(self.index["subprocesses"]), 2)
        self.assertEqual({item["invocation"]["hash_seed"] for item in self.index["subprocesses"]}, {"1", "37"})
        for child in self.index["subprocesses"]:
            self.assertEqual(child["invocation"]["returncode"], 0)
            self.assertTrue(child["invocation"]["script"] and child["invocation"]["stdout"])
            self.assertTrue(all(c["kind"] == "subprocess" for c in child["contexts"]))

    def test_profiles_children_and_exact_rejection_counterparts_are_complete(self):
        errors = Counter()
        configurations = Counter()
        catalogs = Counter()
        for call in self.calls.values():
            api = call["api"]
            if call["outcome"] == "returned":
                result = self.docs[call["result"]]
                if api == "SyntheticGeneratorConfig.__init__":
                    configurations[(result["profile_version"], result["conjunction_strategy"])] += 1
                elif api == "catalog_for_profile":
                    catalogs[(result["version"], len(result["components"]))] += 1
            elif call["native"]["native_stage"] != "deferred_acceptance":
                error = call["error"]
                self.assertIn((error["module"], error["type"]), {
                    ("biocompiler.errors", "SerializationError"), ("biocompiler.compiler.pipeline", "PipelineError")})
                errors[(api, error["message"], call["native"]["expected_code"])] += 1
        self.assertEqual(errors, {
            ("check_component_assembly", "Component assembly changed its authoritative source correspondence.", "component_assembly"): 9,
            ("check_component_assembly", "Component adaptation requires passing synthetic acceptance for the current request, candidate and history.", "synthetic_component_acceptance"): 2,
            ("SyntheticCandidate.from_dict", "Unsupported candidate schema.", "unsupported_schema"): 4,
            ("SyntheticGeneratorConfig.from_dict", "Unsupported generator-config schema.", "unsupported_schema"): 1,
            ("SyntheticGeneratorConfig.__init__", "The selected synthetic catalog is unavailable or stale.", "synthetic_authority"): 2,
            ("SyntheticGeneratorConfig.from_dict", "The selected synthetic catalog is unavailable or stale.", "synthetic_authority"): 1,
            ("SyntheticGeneratorConfig.__init__", "Unsupported synthetic generation profile.", "synthetic_authority"): 1,
            ("SyntheticGeneratorConfig.from_dict", "Unsupported synthetic generation profile.", "synthetic_authority"): 1,
            ("catalog_for_profile", "Unsupported synthetic generation profile.", "synthetic_authority"): 1,
        })
        self.assertEqual(configurations, {
            ("biocompiler.synthetic.combinational.v0.1", "native"): 390,
            ("biocompiler.synthetic.combinational.v0.1", "de_morgan"): 41,
            ("biocompiler.synthetic.temporal.v0.1", "native"): 156,
            ("biocompiler.synthetic.temporal.v0.1", "de_morgan"): 79,
        })
        self.assertEqual(catalogs, {("biocompiler.synthetic.catalog.v0.2", 9): 3315,
            ("biocompiler.synthetic.catalog.v0.2", 13): 2790})
        for child in self.index["subprocesses"]:
            self.assertEqual(sum(len(context["api_calls"]) for context in child["contexts"]), 24)

    def test_all_reached_acceptance_and_exact_original_version_mutants_are_replayed(self):
        from tools.freeze_synthetic_acceptance import ACCEPTANCE, VERSION_MUTATIONS
        mutations = {identity: call for identity, call in self.calls.items()
            if call["native"]["native_stage"] == "checker_version_mutation"}
        self.assertEqual(set(mutations), set(VERSION_MUTATIONS))
        for identity, call in self.calls.items():
            if call["api"] in ACCEPTANCE:
                self.assertNotEqual(call["native"]["native_stage"], "deferred_acceptance", identity)
                self.assertIn(call["native"]["native_stage"], {
                    "synthetic_acceptance", "assembly_acceptance", "component_behavior", "realization", "dependencies",
                    "checker_version_mutation"})
                self.assertEqual(call["native"]["expected_code"], None if call["outcome"] == "returned" else
                    "component_assembly" if call["error"]["type"] == "PipelineError" else "synthetic_component_acceptance")
        for identity, call in mutations.items():
            api, version, line = VERSION_MUTATIONS[identity]
            self.assertEqual(call["api"], api)
            self.assertEqual(self.index["source_locations"][call["source"]]["line"], line)
            original = self.docs[call["result"]]
            self.assertEqual((original if api == "realization_dependencies" else original["dependencies"])["checker"], version)

    def test_native_inputs_independently_rebuild_complete_arguments_defaults_and_types(self):
        from tools.freeze_synthetic_acceptance import foundation
        CLASSES, FUNCTIONS = foundation.CLASSES, foundation.FUNCTIONS
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
                        "obligation": "full_original_producer_observation_retained_no_native_generation_adaptation_or_selection_claim"})
                    continue
                if "." not in api:
                    bound = inspect.signature(functions[api]).bind(*raw["args"], **raw["kwargs"]); bound.apply_defaults()
                    # The later opt-in transport default is absent from this original semantic capture.
                    if api in {"realization_dependencies", "check_realization", "check_synthetic_candidate", "check_component_behavior", "check_component_assembly"} and bound.arguments.get("core") is None:
                        bound.arguments.pop("core", None)
                    expected = plain(dict(bound.arguments))
                else:
                    name, method = api.split(".")
                    if method in ("__init__", "freeze"):
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
                            if name == "SyntheticCandidate":
                                expected.update(intended_use="software_test", human_therapeutic_admission="not_admitted")
                            if name == "SyntheticGeneratorConfig" and expected["catalog_fingerprint"] is None:
                                from biocompiler.registry.synthetic import SYNTHETIC_CATALOG, TEMPORAL_CATALOG
                                catalogs = {"biocompiler.synthetic.combinational.v0.1": SYNTHETIC_CATALOG,
                                    "biocompiler.synthetic.temporal.v0.1": TEMPORAL_CATALOG}
                                profile = expected["profile_version"]
                                if isinstance(profile, str) and profile in catalogs:
                                    expected["catalog_fingerprint"] = catalogs[profile].fingerprint
                    elif method in ("from_dict", "from_json"):
                        self.assertEqual(raw["kwargs"], {}); self.assertEqual(len(raw["args"]), 1)
                        expected = raw["args"][0]
                        if method == "from_json":
                            self.assertEqual(use(native["input"], native["input_format"]), expected)
                            continue
                    else:
                        self.assertIn(method, ("for_operation", "lock"))
                        bound = inspect.signature(getattr(classes[name], method)).bind(*raw["args"], **raw["kwargs"])
                        bound.apply_defaults()
                        expected = plain(dict(bound.arguments))
                        expected["subject"] = expected.pop("self")
                if native["native_stage"] == "checker_version_mutation":
                    from tools.freeze_synthetic_acceptance import VERSION_MUTATIONS
                    identity = context["id"] + "/api/" + str(number)
                    api, version, line = VERSION_MUTATIONS[identity]
                    self.assertEqual(call["api"], api)
                    self.assertEqual(self.index["source_locations"][call["source"]]["line"], line)
                    expected = {"api": api, "authority": expected, "checker_version": version,
                        "original_result": self.docs[call["result"]]}
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
        self.assertEqual(len(order), 47758); self.assertEqual(len({tuple(item) for item in order}), 47758)
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

    def test_all_implemented_records_methods_and_acceptance_outputs_replay_fully(self):
        from tools.freeze_synthetic_acceptance import python_decode
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
