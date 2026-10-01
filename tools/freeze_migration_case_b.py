"""Freeze/check the case B Python baseline; this does not grant native acceptance.

Import biocompiler from the caller's selected environment. The repository is added
only for its independently authored examples, never to select src implicitly.
No native executable, build, installation or network operation is used.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
from unittest.mock import patch

import biocompiler as bc
from biocompiler.compiler.request import BuildRequest
from biocompiler.ir.intent import SourceLocation
from biocompiler.semantics.evaluator import (
    InputFrame, REFERENCE_EVALUATOR_VERSION, SignalSample, evaluate,
)


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/case-b"
TOOL_VERSION = "biocompiler.freeze_migration_case_b.v0.1"
VARIANTS = ("base", "parameter-default", "parameter-override")
LITERAL_FILES = ("expectations.json", "descriptors.json")


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def examples_module():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from examples import payload_architectures
    return payload_architectures


def normalize_program(program, *, root=ROOT):
    """Relocate source coordinates BEFORE freezing any enclosing authority.

    The original absolute checkout prefix is represented by <checkout> in the
    retained coordinate map. Lines/functions and relative suffixes are preserved.
    There is no post-hoc rewrite of request/candidate hashes or serialized bytes.
    """
    nodes, coordinates = [], []
    for node in program.nodes:
        if node.source is None:
            nodes.append(node)
            continue
        path = Path(node.source.file)
        relative = path.resolve().relative_to(Path(root).resolve()).as_posix()
        canonical = SourceLocation(relative, node.source.line, node.source.function)
        coordinates.append({"node_id": node.id,
                            "original": {**node.source.to_dict(), "file": "<checkout>/" + relative},
                            "canonical": canonical.to_dict()})
        nodes.append(replace(node, source=canonical))
    normalized = replace(program, nodes=tuple(nodes))
    require(normalized.fingerprint == program.fingerprint,
            "Source relocation changed semantic Intent identity")
    return normalized, coordinates


def parameterize_dwell(program):
    """An explicit fixture authoring variant, applied independently to both programs.

    Select by operation/typed edge, not fixture node IDs. All remaining source
    nodes/edges are preserved. This is not a runtime rewrite or checker rule.
    """
    timers = [node for node in program.nodes if node.kind == "held_for"]
    require(len(timers) == 1 and len(timers[0].inputs) == 2, "Ambiguous dwell timer")
    duration_id = timers[0].inputs[1]
    duration = next(node for node in program.nodes if node.id == duration_id)
    require(duration.kind == "literal" and duration.to_dict()["attributes"]["value"] == bc.Duration(2).to_dict(),
            "Case B no longer has the expected typed two-second duration")
    replacement = replace(duration, kind="parameter", role=None,
                          attributes={"name": "dwell_duration", "bound": True,
                                      "default": bc.Duration(2).to_dict()})
    return replace(program, nodes=tuple(replacement if node.id == duration_id else node
                                        for node in program.nodes),
                   roots=(*program.roots, duration_id))


def make_request(variant):
    require(variant in VARIANTS, "Unknown corpus variant")
    module = examples_module()
    original_source, original_contract, original_freeze = (
        module.source_program, module.contract_program, module._freeze)
    coordinates = {}

    def authored(factory, label):
        def wrapper(*args, **kwargs):
            raw = factory(*args, **kwargs)
            normalized, mapping = normalize_program(raw)
            retained = parameterize_dwell(normalized) if variant != "base" else normalized
            coordinates[label] = {"raw_intent_semantic_fingerprint": raw.fingerprint,
                                  "normalized_intent_semantic_fingerprint": normalized.fingerprint,
                                  "variant_intent_semantic_fingerprint": retained.fingerprint,
                                  "authoring_variant": variant, "nodes": mapping}
            return retained
        return wrapper

    def freeze(program, case):
        if variant != "parameter-override":
            return original_freeze(program, case)
        # Re-freeze from caller input, with a separately authored supplier model
        # receiving the same explicitly chosen override. No source-to-model copy.
        return BuildRequest.freeze(program, target=module.make_human_target(),
                                   behavior_profile=module.BEHAVIOR_V2,
                                   implementation_constraints={},
                                   parameters={"dwell_duration": bc.Duration(3)})

    with patch.object(module, "source_program", authored(original_source, "source")), \
         patch.object(module, "contract_program", authored(original_contract, "supplier")), \
         patch.object(module, "_freeze", freeze):
        request = module.make_architecture_request("B")
    return request, coordinates


def schema_census(document):
    result = {}

    def visit(value, path):
        if isinstance(value, dict):
            if isinstance(value.get("schema_version"), str):
                entry = result.setdefault(value["schema_version"], {"paths": [], "field_sets": []})
                entry["paths"].append(path or "/")
                keys = sorted(value)
                if keys not in entry["field_sets"]:
                    entry["field_sets"].append(keys)
            for key, child in value.items():
                visit(child, path + "/" + key.replace("~", "~0").replace("/", "~1"))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, path + "/" + str(index))

    visit(document, "")
    return result


def inspect_case(request, build):
    behavior = build.execution.behavior
    require(behavior is not None and build.plan is not None and build.construction is not None,
            "Python producer did not emit a complete case B candidate")
    return {
        "intent_node_count": len(request.source.intent.nodes),
        "intent_kinds": dict(sorted(Counter(node.kind for node in request.source.intent.nodes).items())),
        "runtime_node_count": sum(node.kind in {"state", "memory", "rule"} or node.kind.startswith("action.")
                                  for node in behavior.nodes),
        "role_count": len(build.execution.roles),
        "channel_count": len(build.execution.channels),
        "state_declarations": [{"values": list(item["declaration"]["attributes"]["values"]),
                                "initial": item["declaration"]["attributes"]["initial"],
                                "observation": item["declaration"]["attributes"]["observation"],
                                "arbitration": item["declaration"]["attributes"]["arbitration"],
                                "assignment_values": [assignment["value"] for assignment in item["assignments"]]}
                               for item in build.execution.states],
        "outputs": [{"action_kind": item.action_kind, "trigger": item.trigger,
                     "activation": item.activation, "product": item.product,
                     "assigned_value": item.semantics["primitive_action"]["attributes"].get("value"),
                     "ongoing": item.semantics["primitive_action"]["attributes"].get("ongoing"),
                     "rate": item.semantics["primitive_action"]["attributes"].get("rate")}
                    for item in build.execution.outputs],
        "rna_count": len(build.molecules.molecules),
        "rna_sequences": [item.sequence for item in build.molecules.molecules],
        "requested_control_requirements": len(request.constraints.control_requirements),
        "supplier_control_kinds": [control.kind for control in request.library.refinements[0].controls],
        "require_complete": request.constraints.require_complete,
    }


def timeline_result(behavior, specification):
    signals = {node.attributes["name"]: node.id for node in behavior.nodes if node.kind == "signal"}
    require(set(signals) == {"context", "reset", "shutdown"}, "Unexpected case B signal inventory")
    states = [node.id for node in behavior.nodes if node.kind == "state"]
    require(len(states) == 1, "Unexpected case B state inventory")
    history = []
    for frame in specification["inputs"]:
        require(set(frame["present"]) == set(signals), "Timeline is not a complete observation snapshot")
        history.append(InputFrame(frame["time"], {signals[name]: SignalSample(present=value)
                                                   for name, value in frame["present"].items()}))
    result = evaluate(behavior, history, until=specification["horizon"])
    return [{"time": frame.time, "state": frame.states[states[0]],
             "secretion_count": sum(action.kind == "action.secrete" for action in frame.actions)}
            for frame in result.frames]


def validate_descriptors(document):
    require(document["schema_version"] == "biocompiler.migration_case_b_descriptors.v0.1",
            "Unknown descriptors schema")
    ids = [case["id"] for case in document["cases"]]
    require(len(ids) == len(set(ids)), "Duplicate descriptor identity")
    for case in document["cases"]:
        require(case["native_execution"] == "not_run", "Descriptors cannot assert native execution")
        require(case["expected"] in {"accept_complete", "reject", "unsupported"}, "Unknown expectation")
        require(bool(case["check"]) and bool(case["change"]), "Missing intended semantic check")


def generate(corpus=CORPUS):
    corpus = Path(corpus)
    literal_bytes = {name: (corpus / name).read_bytes() for name in LITERAL_FILES}
    expectations = json.loads(literal_bytes["expectations.json"])
    descriptors = json.loads(literal_bytes["descriptors.json"])
    require(expectations["schema_version"] == "biocompiler.migration_case_b_expectations.v0.1",
            "Unknown expectations schema")
    validate_descriptors(descriptors)
    outputs, cases, coordinates, census = {}, {}, {}, {}
    for variant in VARIANTS:
        request, coordinates[variant] = make_request(variant)
        build = bc.compile(request)  # Exactly one producer call per retained request.
        receipt = bc.check_payload_architecture(build, expected_request=request)
        for name, artifact in (("request", request), ("candidate", build)):
            document = artifact.to_dict()
            outputs[variant + "/" + name + ".json"] = encoded(document)
            census[variant + "/" + name] = schema_census(document)
        observed = inspect_case(request, build)
        expected_structure = json.loads(json.dumps(expectations["structure"]))
        if variant != "base":
            expected_structure["intent_kinds"].pop("literal")
            expected_structure["intent_kinds"]["parameter"] = 1
        require(observed == expected_structure, variant + ": literal structural expectations changed: " + repr(observed))
        require({key: receipt.to_dict()[key] for key in expectations["verification"]}
                == expectations["verification"], variant + ": Python baseline scope/completeness changed")
        require(build.status == "compiled", variant + ": baseline producer label changed")
        timelines = {}
        for specification in expectations["timelines"]:
            if variant not in specification["variants"]:
                continue
            actual = timeline_result(build.execution.behavior, specification)
            require(actual == specification["frames"], variant + ": literal timeline changed: " + specification["id"] + ": " + repr(actual))
            timelines[specification["id"]] = actual
        binding = request.source.to_dict()
        require({name: binding[name] for name in ("explicit_overrides", "resolved_defaults", "resolved_bindings")}
                == expectations["bindings"][variant], variant + ": frozen caller binding changed")
        cases[variant] = {
            "request_fingerprint": request.fingerprint,
            "source_request_fingerprint": request.source.fingerprint,
            "source_request_artifact_fingerprint": request.source.artifact_fingerprint,
            "intent_fingerprint": request.source.intent.fingerprint,
            "behavior_fingerprint": build.execution.behavior.fingerprint,
            "supplier_behavior_fingerprints": [item.behavior.fingerprint for item in request.library.refinements],
            "candidate_fingerprint": build.fingerprint,
            "python_verification": receipt.to_dict(),
            "literal_structure_matched": observed,
            "literal_timelines_matched": timelines,
        }
        if variant == "base":
            require(request.source.intent.fingerprint == expectations["base_identities"]["intent"],
                    "Baseline source semantic fingerprint changed")
            require(build.execution.behavior.fingerprint == expectations["base_identities"]["behavior"],
                    "Baseline Behavior fingerprint changed")
            partial = replace(build, status="partial")
            partial_receipt = bc.check_payload_architecture(partial, expected_request=request)
            require(partial.fingerprint != build.fingerprint and partial_receipt.passed
                    and partial_receipt.translation_complete and partial_receipt.construction_complete,
                    "Complete candidate with partial producer label must independently remain complete")
            cases[variant]["complete_partial_label_positive"] = {
                "transformation": {"field": "/status", "value": "partial"},
                "candidate_fingerprint": partial.fingerprint,
                "python_verification": partial_receipt.to_dict(),
            }
    outputs["source-coordinates.json"] = encoded(coordinates)
    outputs["schema-census.json"] = encoded(census)
    inventory = {name: {"sha256": digest(data), "bytes": len(data)}
                 for name, data in sorted({**outputs, **literal_bytes}.items())}
    outputs["current-baseline-oracle.json"] = encoded({
        "schema_version": "biocompiler.migration_case_b_baseline.v0.1",
        "tool_version": TOOL_VERSION, "biocompiler_version": bc.__version__,
        "evaluator_version": REFERENCE_EVALUATOR_VERSION,
        "evidence_kind": "current_python_baseline_oracle",
        "acceptance_authority": False, "native_execution": "not_run",
        "scope": "Retained artificial case B software baseline and fresh Python-only comparison to literal expectations; no OCaml validation, biological function or human admission.",
        "files": inventory, "cases": cases,
        "descriptor_count": len(descriptors["cases"]),
        "descriptor_execution": "Planned descriptors are not executed by this generator; only named literal timelines, three parameter/baseline variants and complete_partial_label_positive run here.",
    })
    return outputs


def source_inventory():
    paths = [ROOT / "tools/freeze_migration_case_b.py", *sorted((ROOT / "examples").glob("*.py"))]
    result = {path.relative_to(ROOT).as_posix(): digest(path.read_bytes()) for path in paths}
    package = Path(bc.__file__).resolve().parent
    result.update({"imported-package/biocompiler/" + path.relative_to(package).as_posix(): digest(path.read_bytes())
                   for path in sorted(package.rglob("*.py"))})
    return result


def generation_metadata(outputs):
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    return {"schema_version": "biocompiler.migration_case_b_generation.v0.1",
            "tool_version": TOOL_VERSION, "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(), "machine": platform.machine(),
            "biocompiler_version": bc.__version__,
            "package_mode": "source" if Path(bc.__file__).resolve().is_relative_to(ROOT / "src") else "installed",
            "checkout_revision_at_freeze": revision,
            "source_sha256_at_freeze": source_inventory(),
            "baseline_oracle_sha256": digest(outputs["current-baseline-oracle.json"]),
            "acceptance_authority": False,
            "note": "Historical provenance outside artifact identities. Revision may have uncommitted changes; recorded source hashes identify actual bytes. --check preserves this historical platform and reports current comparison separately."}


def check_files(corpus, outputs):
    failures = [name for name, data in outputs.items()
                if not (Path(corpus) / name).is_file() or (Path(corpus) / name).read_bytes() != data]
    metadata_path = Path(corpus) / "generation.json"
    if not metadata_path.is_file():
        failures.append("generation.json missing")
    else:
        metadata = json.loads(metadata_path.read_bytes())
        if metadata.get("baseline_oracle_sha256") != digest(outputs["current-baseline-oracle.json"]):
            failures.append("generation.json baseline oracle digest")
        if metadata.get("tool_version") != TOOL_VERSION or metadata.get("acceptance_authority") is not False:
            failures.append("generation.json tool/scope")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare all regenerated bytes; never rewrite the baseline")
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    args = parser.parse_args(argv)
    outputs = generate(args.corpus)
    if args.check:
        failures = check_files(args.corpus, outputs)
        if failures:
            parser.exit(1, "Case B corpus drift: " + ", ".join(failures) + "\n")
    else:
        for name, data in outputs.items():
            path = args.corpus / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        (args.corpus / "generation.json").write_bytes(encoded(generation_metadata(outputs)))
    print(json.dumps({"result": "matches_retained_python_baseline" if args.check else "frozen_python_baseline",
                      "files": len(outputs), "bytes": sum(map(len, outputs.values())),
                      "python_version": platform.python_version(), "platform": platform.platform(),
                      "native_execution": "not_run", "acceptance_authority": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
