"""Project every retained original rich-helper observation without product imports.

The four original corpora and all of their documents stay immutable. This reader
binds complete original arguments/results/properties and call parentage; it does
not compute graph ordering, selection, coverage or freshness in Python.
"""
from __future__ import annotations
from collections import Counter
import hashlib
from pathlib import Path
if __package__:
    from . import check_workflow_reproducibility as evidence
else:
    import check_workflow_reproducibility as evidence

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "biocompiler.core.synthetic_inspection.v1"
SUPPLEMENTAL_SHA256 = "c9b6179b9c36ee56cd11706f4bf5593f23524de054ff9cb245610245170b818d"
SUPPLEMENTAL_NAME = "synthetic-inspection-supplemental-v1"
PINS = {
    "component-runtime-v1": ("aea8309d6efa172777f550d4a91cd3ebb7b40c301234fc7e90636fb4f466fcbf", "de5a18829b1d624262dddc12488e52c7b1898d1191ce09df53de13aa6d3c6114", 52476, 4934, 167),
    "realization-foundation-v1": ("ac1499688ec6f0eca41398134b9421de9f95ffe9405422332c2bf43b04db32f8", "152a87971fcaa3d6a47eb0320b1c2ed9081f61032511e3179faba22b4fdb59a2", 70019, 19458, 332),
    "realization-checks-v1": ("8ddc5a929f90e8364e3ffb53c6902ff23bd5dec2524897a8d463f543b887d80a", "05d24d0ff4450fc072ba2db4af4a608f6a929aa0f3a6680c2cb9cf29082f046e", 74803, 26410, 348),
    "component-acceptance-v1": ("9eb76b8f697b00be207e6bb2e1cccdfd46ee974b09a3525d21eb4f32634ee116", "592dce033ac74ca643b2a53bd590e0033674b42fa95b526e8632db1496dc81fe", 4539, 5394, 380),
}
METHODS = {
    "ComponentRegistry.lock": "lock-synthetic-registry",
    "ComponentRegistry.resolve": "resolve-synthetic-registry",
    "ComponentRegistry.select": "select-synthetic-registry",
    "ComponentRegistry.verify_selection": "verify-synthetic-registry-selection",
    "CheckResult.freshness": "inspect-synthetic-check-result",
    "CheckResult.is_fresh": "inspect-synthetic-check-result",
    "DependencySnapshot.changed": "compare-synthetic-dependencies",
}
EXPECTED_CENSUS = {
    "component-runtime-v1": {"ComponentRegistry.lock/returned": 926,
        "ComponentRegistry.resolve/returned": 711, "ComponentRegistry.resolve/raised": 13},
    "realization-foundation-v1": {"CheckResult.freshness/returned": 21,
        "CheckResult.is_fresh/returned": 2, "DependencySnapshot.changed/returned": 21,
        "CheckResult.exercised_requirement_ids/returned": 3883},
    "realization-checks-v1": {"CheckResult.freshness/returned": 21,
        "CheckResult.is_fresh/returned": 2, "DependencySnapshot.changed/returned": 21,
        "CheckResult.exercised_requirement_ids/returned": 3898},
    "component-acceptance-v1": {"ComponentRegistry.select/returned": 35,
        "ComponentRegistry.verify_selection/returned": 8, "SelectionResult.outcome/returned": 70},
}
require, canonical, digest = evidence.require, evidence.canonical, evidence.digest


def supplemental(root):
    path = Path(root) / "tests/conformance" / (SUPPLEMENTAL_NAME + ".json")
    raw = evidence.raw_file(path)
    require(hashlib.sha256(raw).hexdigest() == SUPPLEMENTAL_SHA256,
            "Complete original supplemental helper capture changed")
    value = evidence.decode(raw)
    require(raw == canonical(value) + b"\n" and set(value) == {"schema_version", "source_files", "capture_source", "cases"}
        and value["schema_version"] == "biocompiler.synthetic_inspection_supplemental.v1" and
        type(value["capture_source"]) is str and value["capture_source"] and len(value["cases"]) == 28 and
        sum(case["error"] is not None for case in value["cases"]) == 8,
        "Supplemental original helper cohort changed")
    for source, pin in value["source_files"].items():
        require(source.startswith("src/biocompiler/") and ".." not in Path(source).parts and evidence.pin(pin) and
            hashlib.sha256(evidence.raw_file(Path(root) / source)).hexdigest() == pin,
            "Supplemental original helper source changed: " + source)
    return value


class Original:
    def __init__(self, root, name):
        self.name, self.directory = name, root / "tests/conformance" / name
        self.index, self.file_sha256 = evidence.read(self.directory.with_suffix(".json"))
        pin, capture, calls, documents, contexts = PINS[name]
        require(self.index["inventory_fingerprint"] == pin and digest({
            k: v for k, v in self.index.items() if k != "inventory_fingerprint"}) == pin,
            "Original helper corpus inventory changed: " + name)
        require(self.index["original_capture_fingerprint"] == capture and
            self.index["coverage"]["api_calls"] == calls and
            len(self.index["documents"]) == documents and len(self.index["contexts"]) == contexts,
            "Original helper source cohort changed: " + name)
        self.metadata = {row["id"]: row for row in self.index["documents"]}
        require(len(self.metadata) == documents, "Duplicate original helper document")
        self.cache = {}
        self.rows = []
        census = Counter()
        for context in self.index["contexts"]:
            ledger = self.document(context["ledger"])
            observations = ledger["observations"]
            require(context["assertion_status"] == "passed" and len(observations) == context["api_calls"],
                    "Original helper context lost observations or assertions")
            for ordinal, call in enumerate(observations):
                self.rows.append((context, ordinal, call))
                census[call["api"]] += 1
        require(dict(census) == self.index["coverage"]["api_census"] and sum(census.values()) == calls,
                "Complete original helper API census changed")

    def document(self, identity):
        require(evidence.pin(identity) and identity in self.metadata, "Unknown original helper document")
        if identity not in self.cache:
            raw = evidence.raw_file(self.directory / (identity + ".json"))
            value = evidence.decode(raw)
            require(len(raw) == self.metadata[identity]["bytes"] and digest(value) == identity
                    and raw == canonical(value) + b"\n", "Original complete helper bytes changed")
            self.cache[identity] = value
        return self.cache[identity]

    def bound(self, call):
        native = call["native"]
        value = self.document(native["input"])
        if native["input_format"] == "json_text":
            require(type(value) is str, "Original JSON-text helper authority changed")
            value = evidence.decode(value.encode("utf-8"))
        else:
            require(native["input_format"] == "record", "Unknown original helper input encoding")
        require(type(value) is dict, "Original bound helper authority is not an object")
        return value

    def call_evidence(self, context, ordinal, call):
        value = {"corpus": self.name, "corpus_pin": self.index["inventory_fingerprint"],
            "context": context, "ordinal": ordinal, "observation": call,
            "source": self.index["source_locations"][call["source"]],
            "raw_arguments": self.document(call["input"]),
            "python_types": self.document(call["python_types"]),
            "original_result": self.document(call["result"]) if call["outcome"] == "returned" else None,
            "properties": self.document(call["properties"]) if "properties" in call else None}
        if "input" in call["native"]:
            value["original_native_arguments"] = self.document(call["native"]["input"])
        return value


def bind_authority(api, bound):
    """Rename explicit frozen fields only; never evaluate a semantic helper."""
    fields = {
        "ComponentRegistry.lock": ({"registry", "selections"}, {"registry": "registry", "instances": "selections"}),
        "ComponentRegistry.resolve": ({"registry", "lock"}, {"registry": "registry", "lock": "lock"}),
        "ComponentRegistry.select": ({"subject", "request"}, {"registry": "subject", "request": "request"}),
        "ComponentRegistry.verify_selection": ({"subject", "request", "result"}, {"registry": "subject", "request": "request", "selection": "result"}),
        "CheckResult.freshness": ({"subject", "current"}, {"record": "subject", "current": "current"}),
        "CheckResult.is_fresh": ({"subject", "current"}, {"record": "subject", "current": "current"}),
        "DependencySnapshot.changed": ({"subject", "current"}, {"previous": "subject", "current": "current"}),
    }
    expected, mapping = fields[api]
    require(set(bound) == expected, "Original helper authority cannot be projected without loss")
    return {key: bound[source] for key, source in mapping.items()}


class Corpus:
    def __init__(self, root=ROOT):
        originals = [Original(Path(root), name) for name in PINS]
        self.pins = {source.name: {"inventory_fingerprint": PINS[source.name][0],
            "original_capture_fingerprint": PINS[source.name][1], "file_sha256": source.file_sha256}
            for source in originals}
        self.cases, self.census = [], {}
        for source in originals:
            coverage, freshness = {}, {}
            for _, _, call in source.rows:
                if call["outcome"] != "returned":
                    continue
                properties = source.document(call["properties"]) if "properties" in call else {}
                if "exercised_requirement_ids" in properties:
                    result = source.document(call["result"])
                    key = canonical(result)
                    value = properties["exercised_requirement_ids"]
                    require(key not in coverage or canonical(coverage[key]) == canonical(value),
                            "Original coverage properties contradict their exact record")
                    coverage[key] = value
                if call["api"] == "CheckResult.freshness":
                    bound, result = source.bound(call), source.document(call["result"])
                    require(set(result) == {"changed_dependencies"} and set(properties) == {"fresh", "status"},
                            "Complete original freshness presentation changed")
                    key, value = canonical(bound), {**result, **properties}
                    require(key not in freshness or canonical(freshness[key]) == canonical(value),
                            "Original freshness observations contradict the same complete authority")
                    freshness[key] = value
            counts = Counter()
            for context, ordinal, call in source.rows:
                api = call["api"]
                properties = source.document(call["properties"]) if "properties" in call else {}
                property_call = "exercised_requirement_ids" in properties
                selection_property = (source.name == "component-acceptance-v1" and
                    api in {"SelectionResult.__init__", "SelectionResult.from_dict", "SelectionResult.from_json"} and "outcome" in properties)
                if api not in METHODS and not property_call and not selection_property:
                    continue
                original = source.call_evidence(context, ordinal, call)
                identity = source.name + "/" + context["id"] + "/api/" + str(ordinal)
                if selection_property:
                    require(call["outcome"] == "returned" and original["original_result"].get("schema_version") ==
                            "biocompiler.component_selection_result.v0.2", "Original selection outcome subject changed")
                    api = "SelectionResult.outcome"
                    identity += "/property/outcome"
                    authority = {"selection": original["original_result"]}
                    value = {"outcome": properties["outcome"]}
                    public = {"value": properties["outcome"], "properties": {}}
                    operation, error = "inspect-synthetic-registry-selection", None
                elif property_call:
                    require(api not in METHODS and call["outcome"] == "returned", "Ambiguous original helper occurrence")
                    api = "CheckResult.exercised_requirement_ids"
                    identity += "/property/exercised_requirement_ids"
                    authority = {"record": original["original_result"], "current": None, "query": "coverage"}
                    value = {"exercised_requirement_ids": properties["exercised_requirement_ids"], "freshness": None}
                    public = {"value": properties["exercised_requirement_ids"], "properties": {}}
                    operation, error = "inspect-synthetic-check-result", None
                else:
                    authority = bind_authority(api, source.bound(call))
                    if api in {"CheckResult.freshness", "CheckResult.is_fresh"}:
                        authority["query"] = "freshness"
                    operation, value, error = METHODS[api], None, None
                    public = {"value": original["original_result"], "properties": properties}
                    if call["outcome"] == "raised":
                        require(api == "ComponentRegistry.resolve" and call["error"]["module"] == "biocompiler.errors"
                            and call["error"]["type"] == "SerializationError", "Unknown original helper rejection")
                        error = {"code": call["native"]["expected_code"], "message": call["error"]["message"], "path": None}
                        public = {"error": call["error"]}
                    elif api in {"CheckResult.freshness", "CheckResult.is_fresh"}:
                        key = canonical(authority["record"])
                        require(key in coverage and canonical(source.bound(call)) in freshness,
                                "Missing complete captured coverage/freshness counterpart")
                        value = {"exercised_requirement_ids": coverage[key],
                            "freshness": freshness[canonical(source.bound(call))]}
                    elif api == "DependencySnapshot.changed":
                        value = {"changed_dependencies": original["original_result"]}
                    elif api == "ComponentRegistry.lock":
                        value = {"lock": original["original_result"]}
                    elif api == "ComponentRegistry.resolve":
                        value = {"instances": original["original_result"]}
                    elif api == "ComponentRegistry.select":
                        require(set(properties) == {"fingerprint", "outcome"}, "Original selection properties changed")
                        value = {"selection": original["original_result"], "outcome": properties["outcome"]}
                    elif api == "ComponentRegistry.verify_selection":
                        value = {"valid": original["original_result"]}
                counts[api + "/" + call["outcome"]] += 1
                self.cases.append({"id": identity, "api": api, "operation": operation,
                    "payload": {"profile": PROFILE, "limits": None, **authority},
                    "expected_value": value, "error": error, "expected_public": public,
                    "evidence": original})
            require(dict(counts) == EXPECTED_CENSUS[source.name], "Complete original helper occurrence census changed")
            self.census[source.name] = dict(counts)
        require(len(self.cases) == 9632 and len({case["id"] for case in self.cases}) == 9632,
                "Original rich-helper observations were narrowed or duplicated")
        self.original_count = len(self.cases)
        extra = supplemental(root)
        self.pins[SUPPLEMENTAL_NAME] = {"file_sha256": SUPPLEMENTAL_SHA256,
            "capture_source_sha256": hashlib.sha256(extra["capture_source"].encode("utf-8")).hexdigest(),
            "source_files": extra["source_files"], "case_count": len(extra["cases"])}
        self.census[SUPPLEMENTAL_NAME] = dict(Counter(case["api"] + "/" +
            ("returned" if case["error"] is None else "raised") for case in extra["cases"]))
        self.cases.extend(extra["cases"])
        require(len(self.cases) == 9660 and len({case["id"] for case in self.cases}) == 9660,
                "Complete original and supplemental helper observations were narrowed or duplicated")
