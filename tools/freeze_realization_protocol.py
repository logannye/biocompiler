#!/usr/bin/env python3
"""Project all frozen acceptance occurrences and independently check new witnesses.

No original corpus is recaptured or rewritten. --check independently regenerates
the complete new inventory and compares every supplemental byte.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]
from tools.check_realization_protocol import (
    APIS, BASE_PIN, BASE_CAPTURE_PIN, CORPUS, EXPECTED_API_COUNTS,
    PROFILES_PATH, VERSION_MUTATIONS, Baseline, canonical, digest, require,
)


def oracle(api, authority):
    from tools.freeze_synthetic_acceptance import python_decode, plain
    return plain(python_decode(api, authority))


def authority_identities(api, value):
    """Independent original typed getters, used only when freezing/testing."""
    from biocompiler.compiler.request import RealizationRequest
    from biocompiler.ir.behavior import BehaviorProgram
    from biocompiler.semantics.evaluator import InputFrame, SignalSample
    frames = [InputFrame(frame["time"],
        {key: SignalSample(**sample) for key, sample in frame["signals"].items()},
        {contact: {key: SignalSample(**sample) for key, sample in samples.items()}
         for contact, samples in frame["contacts"].items()}).to_dict() for frame in value["history"]]
    identities = {"history_ascii_fingerprint": digest(frames, ascii=True)}
    if api in ("realization_dependencies", "check_realization"):
        behavior = BehaviorProgram.from_dict(value["behavior"])
        identities.update(behavior_fingerprint=behavior.fingerprint,
                          behavior_artifact_ascii_fingerprint=digest(behavior.to_dict(), ascii=True))
        for key in ("contract", "domain", "target", "mechanism", "observation_map"):
            identities[key + "_fingerprint"] = digest(value[key])
    else:
        request = RealizationRequest.from_dict(value["request"])
        identities.update(request_fingerprint=request.fingerprint,
                          request_artifact_fingerprint=request.artifact_fingerprint)
        for key in ("candidate", "assembly"):
            if key in value:
                identities[key + "_fingerprint"] = digest(value[key])
    return identities


def source_relocation(value):
    value = deepcopy(value)
    def visit(item):
        if isinstance(item, dict):
            if set(item) == {"file", "line", "function"}:
                item["file"] = "/原始意图/é/免疫.py"
                item["function"] = "功能_e\u0301_α"
            else:
                for child in item.values():
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
    visit(value)
    return value


def history_unicode(value):
    value = deepcopy(value)
    changed = False
    for frame in value["history"]:
        if frame["contacts"]:
            frame["contacts"] = {"细胞_é_e\u0301_" + name: samples
                                 for name, samples in frame["contacts"].items()}
            changed = True
    require(changed, "Unicode history witness lacks original contacts")
    return value


def build():
    baseline = Baseline()
    documents = {}
    def store(value, kind):
        identity = digest(value)
        documents[identity] = {"kind": kind, "value": deepcopy(value)}
        return identity
    cases, authorities, results, identities_cache = [], {}, {}, {}
    for context, ordinal, call in baseline.occurrences():
        identity = context["id"] + "/api/" + str(ordinal)
        mutation = identity in VERSION_MUTATIONS
        native = call["native"]
        raw = json.loads(baseline.document(native["input"]))
        authority = raw["authority"] if mutation else raw
        result_ref = None if call["outcome"] == "raised" else "baseline:" + call["result"]
        historical_ref = result_ref
        if mutation:
            api, version, line = VERSION_MUTATIONS[identity]
            require(call["api"] == api and baseline.index["source_locations"][call["source"]]["line"] == line,
                    "Original exact policy mutation context differs")
            original = baseline.document(call["result"])
            dependencies = original if api == "realization_dependencies" else original["dependencies"]
            require(dependencies["checker"] == version, "Original historical checker differs")
            expected = deepcopy(original)
            (expected if api == "realization_dependencies" else expected["dependencies"])["checker"] = "biocompiler.realization_checker.v0.3"
            current = oracle(api, authority)
            require(canonical(current) == canonical(expected), "Policy witness changed beyond its exact checker field")
            result_ref = store(current, "current_policy_counterpart")
        case = {
            "id": identity, "context": context["id"], "ordinal": ordinal,
            "api": call["api"], "input": "baseline:" + native["input"],
            "result": result_ref, "historical_result": historical_ref,
            "source": baseline.index["source_locations"][call["source"]],
            "parent": call["parent"], "version_mutation": mutation,
            "error": None if call["outcome"] == "returned" else {"code": native["expected_code"], **call["error"]},
        }
        authority_pin = digest(authority)
        if authority_pin not in identities_cache:
            identities_cache[authority_pin] = authority_identities(call["api"], authority)
        case["authority_identities"] = identities_cache[authority_pin]
        cases.append(case)
        authorities[identity] = authority
        if result_ref is not None:
            results[identity] = documents[result_ref]["value"] if mutation else baseline.document(call["result"])
    require(Counter(c["api"] for c in cases) == EXPECTED_API_COUNTS, "Full original direct census differs")
    require(len({c["id"] for c in cases}) == 4119, "Original occurrences were deduplicated")
    require({c["id"] for c in cases if c["version_mutation"]} == set(VERSION_MUTATIONS), "Policy mutation inventory differs")
    extra = []
    def add(name, source, value):
        error = None
        try:
            expected = oracle(source["api"], value)
        except Exception as raised:
            require(source["api"] == "check_component_assembly" and type(raised).__name__ == "SerializationError" and
                    str(raised) == "Component adaptation requires passing synthetic acceptance for the current request, candidate and history.",
                    "Unclassified independently evaluated supplemental error: " + repr(raised))
            expected = None
            error = {"code": "synthetic_component_acceptance", "module": type(raised).__module__,
                     "type": type(raised).__qualname__, "message": str(raised)}
        identity = "additional/" + name
        require(all(c["id"] != identity for c in extra), "Duplicate supplemental case")
        result = None if error else store(expected, "independent_python_result")
        extra.append({
            "id": identity, "api": source["api"], "input": store(value, "complete_additional_authority"),
            "result": result, "historical_result": result, "source_case": source["id"],
            "version_mutation": False, "error": error, "recipe": name,
            "authority_identities": authority_identities(source["api"], value),
        })
        results[identity], authorities[identity] = expected, value
    for api in APIS:
        applicable = [c for c in cases if c["api"] == api and c["result"] is not None and not c["version_mutation"]]
        base = next(c for c in applicable if api == "realization_dependencies" or results[c["id"]]["outcome"] == "pass")
        source = next(c for c in applicable if any(frame["contacts"] for frame in authorities[c["id"]]["history"])
                      and (api == "realization_dependencies" or results[c["id"]]["outcome"] == "pass"))
        add(api + "/unicode-history", source, history_unicode(authorities[source["id"]]))
        add(api + "/unicode-source", base, source_relocation(authorities[base["id"]]))
        for label, horizon in (("null", None), ("integer", 7), ("float", 7.0), ("zero", 0), ("negative-zero", -0.0)):
            value = deepcopy(authorities[base["id"]])
            value["until"] = horizon
            add(api + "/horizon-" + label, base, value)
        failing = next((c for c in applicable if results[c["id"]].get("outcome") == "fail"
                        and any(f["contacts"] for f in authorities[c["id"]]["history"])), None)
        if failing:
            add(api + "/unicode-failing-history", failing, history_unicode(authorities[failing["id"]]))
    profiles = json.loads(PROFILES_PATH.read_text())
    boundary = []
    def reject(source, replay, name, edits, code):
        boundary.append({
            "id": "boundary/" + source["api"] + "/" + ("replay/" if replay else "verify/") + name,
            "source": source["id"], "replay": replay, "edits": edits, "code": code,
        })
    def set_to(path, value):
        return {"op": "set", "path": path, "value": value}
    for api, (family, op) in APIS.items():
        source = next(c for c in cases if c["api"] == api and c["result"] is not None
                      and not c["version_mutation"] and
                      (api == "realization_dependencies" or results[c["id"]]["outcome"] == "pass"))
        profile = profiles["capability_profiles"][family]
        for replay in ((False,) if api == "realization_dependencies" else (False, True)):
            operation = "replay-" + op.removeprefix("verify-") if replay else op
            for field in profile["payload_fields"][operation]:
                reject(source, replay, "missing-" + field, [{"op": "remove", "path": [field]}], "missing_field")
            reject(source, replay, "extra-field", [set_to(["accepted"], True)], "unknown_field")
            reject(source, replay, "wrong-profile", [set_to(["profile"], "biocompiler.core.unrelated.v1")], "realization_protocol_profile")
            reject(source, replay, "profile-type", [set_to(["profile"], True)], "invalid_type")
            defaults = profile["default_limits"]
            for field in profile["limits_fields"]:
                for label, value in (("zero", 0), ("negative", -1), ("increase", defaults[field] + 1),
                                     ("boolean", True), ("float", 1.0)):
                    reject(source, replay, "limits-" + field + "-" + label,
                           [set_to(["limits"], {**defaults, field: value})], "realization_limits")
            reject(source, replay, "limits-type", [set_to(["limits"], True)], "realization_limits")
            reject(source, replay, "limits-missing", [set_to(["limits"], {k:v for k,v in defaults.items() if k != "max_work"})], "missing_field")
            reject(source, replay, "limits-extra", [set_to(["limits"], {**defaults, "accepted": True})], "unknown_field")
            reject(source, replay, "bad-horizon-type", [set_to(["until"], True)], "invalid_type")
            for field, code in (("max_work", "realization_work_limit"), ("max_request_bytes", "realization_input_limit"),
                                ("max_report_bytes", "realization_report_limit"), ("max_report_nodes", "realization_report_limit")):
                reject(source, replay, "exhaust-" + field, [set_to(["limits"], {**defaults, field: 1})], code)
            if api != "realization_dependencies":
                reject(source, replay, "exhaust-max_monitor_items", [set_to(["limits"], {**defaults, "max_monitor_items": 1})],
                       "realization_monitor_limit")
            if replay:
                result = results[source["id"]]
                reject(source, replay, "historical-extra", [set_to(["assessment", "accepted"], True)], "unknown_field")
                reject(source, replay, "forged-outcome", [set_to(["assessment", "outcome"], "fail")], "realization_assessment_mismatch")
                if "dependencies" in result and "checker" in result["dependencies"]:
                    reject(source, replay, "stale-checker", [set_to(["assessment", "dependencies", "checker"], "changed.v999")],
                           "composition_evidence" if api == "check_component_assembly" else "realization_assessment_mismatch")
                reject(source, replay, "forged-requirement-summary", [set_to(["assessment", "checked_requirement_ids"], [])],
                       "realization_assessment_mismatch" if api == "check_component_assembly" else "realization_evidence")
    source_files = [{"path": p, "sha256": hashlib.sha256((ROOT / p).read_bytes()).hexdigest()}
                    for p in ("tools/freeze_realization_protocol.py", "docs/migration-realization-protocol-profiles.json")]
    index = {
        "schema_version": "biocompiler.realization_protocol_corpus.v1",
        "baseline": {
            "path": str(baseline.path.relative_to(ROOT)), "inventory_fingerprint": BASE_PIN,
            "original_capture_fingerprint": BASE_CAPTURE_PIN, "source_files": baseline.index["source_files"],
            "contexts": baseline.index["contexts"], "subprocesses": baseline.index["subprocesses"],
            "source_ledger": baseline.index["source_ledger"],
        },
        "profiles": store(profiles, "complete_protocol_profiles"), "source_files": source_files,
        "cases": cases, "additional_cases": extra, "boundary_cases": boundary,
        "coverage": {
            "original_direct": 4119, "original_replay": 2112, "current_policy_successful_replays": 2,
            "original_methods": 373, "original_contexts": 381, "original_children": 2,
            "api_calls": EXPECTED_API_COUNTS, "additional_direct": len(extra),
            "additional_replay": sum(c["api"] != "realization_dependencies" and c["result"] is not None for c in extra),
            "boundary_cases": len(boundary), "original_policy_mutations": sorted(VERSION_MUTATIONS),
            "unported_obligations": ["full_workflow_routing", "pipeline_policy", "producer_dispatch", "archive_replay", "export_acceptance"],
        },
    }
    index["coverage"]["protocol_checks_per_role"] = 6233 + len(extra) + index["coverage"]["additional_replay"] + len(boundary)
    index["coverage"]["sdk_checks_per_role"] = 4119 + len(extra)
    index["documents"] = [{"id": key, "kind": entry["kind"], "bytes": len(canonical(entry["value"])) + 1}
                          for key, entry in sorted(documents.items())]
    index["inventory_fingerprint"] = digest(index)
    return index, documents


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    index, documents = build()
    if args.check:
        require(json.loads(CORPUS.read_text()) == index, "Independent complete projection inventory differs")
        require({p.name for p in CORPUS.with_suffix("").iterdir()} == {key + ".json" for key in documents},
                "Independent projection document inventory differs")
        for key, entry in documents.items():
            require((CORPUS.with_suffix("") / (key + ".json")).read_bytes() == canonical(entry["value"]) + b"\n",
                    "Independent complete supplemental document differs: " + key)
    else:
        CORPUS.with_suffix("").mkdir(parents=True, exist_ok=True)
        for key, entry in documents.items():
            (CORPUS.with_suffix("") / (key + ".json")).write_bytes(canonical(entry["value"]) + b"\n")
        CORPUS.write_text(json.dumps(index, sort_keys=True, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"inventory_fingerprint": index["inventory_fingerprint"], "documents": len(documents),
                      "coverage": index["coverage"]}, sort_keys=True))


if __name__ == "__main__":
    main()
