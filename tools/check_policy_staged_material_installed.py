"""Hosted installed staged SDK witness and independent retained-evidence gate.

Only supplied wheel bytes are executed. This additive bounded, conditional
profile preserves the separate original material/component campaigns; it does
not establish universal termination, biological function or release acceptance.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import sys

try:
    import check_policy_component_material as component
    import check_policy_staged_component_material as staged
    from check_policy_core import canonical_digest, read_json, source_identity
    from check_policy_development import source_snapshot
    from check_policy_material import archive_receipt, changed_candidate
except ModuleNotFoundError:
    from tools import check_policy_component_material as component
    from tools import check_policy_staged_component_material as staged
    from tools.check_policy_core import canonical_digest, read_json, source_identity
    from tools.check_policy_development import source_snapshot
    from tools.check_policy_material import archive_receipt, changed_candidate

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "biocompiler.policy_staged_material_campaign.v0.1"
SCOPE = "installed_sdk_bounded_conditional_staged_material"
RECEIPT = "staged-material.json"
FOLDER = "staged-material"
require = component._require
pin = component.bounded_pin


def input_pins(root=ROOT):
    return {name: pin(root / name, 4_000_000) for name in staged.INPUTS}


def check_observations(observations, fixture):
    """Recheck every retained protocol value and control against original inputs."""
    from biocompiler.core_client import CORE_VERSION, CoreResponse
    from biocompiler.core_policy_component_material import _result
    require(type(observations) is list and all(type(row) is dict and set(row) == {"name", "result"} for row in observations),
            "Malformed staged observations")
    staged.check_census(row["name"] for row in observations)
    values = {row["name"]: row["result"] for row in observations}
    request, limits = fixture["request"], fixture["limits"]
    compiled = values["compile"]; candidate = compiled["candidate"]
    for name, operation, role in (("compile", "compile", "core"), ("check-verify", "check", "verify"),
            ("replay-verify", "replay", "verify"), ("export-verify", "export", "verify"),
            ("changed-material", "check", "verify"), ("insufficient-machine-capacity", "check", "verify"),
            ("completion-without-feedback", "compile", "core")):
        original = (staged.deficient_capacity(request) if name == "insufficient-machine-capacity" else
                    staged.completion_request(request) if name == "completion-without-feedback" else request)
        payload = {"request": original, "limits": limits}
        if operation != "compile":
            payload["candidate"] = changed_candidate(candidate, "material") if name == "changed-material" else candidate
        if operation == "replay":
            payload["report"] = compiled
        _result(CoreResponse("retained-staged", operation + "-policy-component-material", "ok", values[name], (), role, CORE_VERSION), payload)
        if name in ("compile", "check-verify", "replay-verify"):
            staged.checked_result(values[name], fixture)
    require(compiled == values["check-verify"] == values["replay-verify"] and compiled["artifact"] is None,
            "Complete staged compile/check/replay evidence differs")
    exported = values["export-verify"]
    staged.checked_export(exported, fixture)
    require(exported["candidate"] == candidate and exported["report"] == compiled["report"]
            and values["paired-publication"] == archive_receipt(exported), "Fresh staged paired export differs")
    failed = values["changed-material"]
    require(failed["report"]["status"] == "not_accepted" and failed["artifact"] is None
            and failed["report"]["assembly_status"] == "fail" and failed["report"]["context_status"] == "unassessed"
            and failed["report"]["assembly"]["structure"]["content_outcome"] == "fail", "Changed staged material acquired acceptance")
    deficient = values["insufficient-machine-capacity"]
    require(deficient["report"]["status"] == "not_accepted" and deficient["artifact"] is None
            and deficient["report"]["context_status"] == "fail", "Insufficient staged capacity acquired acceptance")
    completion = values["completion-without-feedback"]
    require(completion["report"]["status"] == "not_accepted" and completion["artifact"] is None
            and any(row["id"] == "second_initiation" and row["status"] == "fail"
                    for row in completion["report"]["preservation"]["requirements"]),
            "Absent feedback acquired guaranteed completion")
    for name, code in staged.NEGATIVE_CODES.items():
        value = values[name]
        require(type(value) is dict and set(value) == {"status", "diagnostics"}
                and value["status"] == ("unsupported" if name == "verify-has-no-producer" else "error")
                and type(value["diagnostics"]) is list and value["diagnostics"]
                and all(type(row) is dict and set(row) == {"code", "message", "path"}
                        and type(row["message"]) is str and (row["path"] is None or type(row["path"]) is str)
                        for row in value["diagnostics"])
                and {row["code"] for row in value["diagnostics"]} == {code},
                "Staged control failed at an unrelated boundary: " + name)
    return values


def validate_installed(receipt, evidence_root, fixture_path, identity_value, binaries, *, expected_sources, expected_slot=None):
    """Validate the complete sidecar/ZIP census, package origins and external pins."""
    evidence_root = Path(evidence_root)
    originals = input_pins()
    fields = {"schema_version", "status", "revision", "head_revision", "run_id", "run_attempt", "system", "machine", "python_version",
              "scope", "inputs", "binary_sha256", "package", "installed_modules", "parent_imports", "source_snapshot_sha256",
              "authoring", "observations", "observations_fingerprint", "publications", "python_semantic_authority", "empirical"}
    require(type(receipt) is dict and set(receipt) == fields and receipt["schema_version"] == SCHEMA and receipt["status"] == "pass",
            "Not a complete installed staged receipt")
    require(type(receipt["python_version"]) is str and re.fullmatch(r"3\.(11|14)\.[0-9]+", receipt["python_version"]),
            "Invalid installed staged runtime")
    slot = receipt["system"], receipt["machine"], ".".join(receipt["python_version"].split(".")[:2])
    require(slot in component.SLOTS and (expected_slot is None or slot == expected_slot), "Wrong installed staged slot")
    require(all(receipt[key] == identity_value[key] for key in ("revision", "head_revision", "run_id"))
            and type(receipt["run_attempt"]) is str and re.fullmatch(r"[1-9][0-9]*", receipt["run_attempt"])
            and int(receipt["run_attempt"]) <= int(identity_value["run_attempt"]), "Stale installed staged source/run/attempt")
    require(set(binaries) == {"biocompiler-core", "biocompiler-verify"} and all(component._sha(value) for value in binaries.values())
            and receipt["binary_sha256"] == binaries and receipt["inputs"] == originals
            and receipt["source_snapshot_sha256"] == canonical_digest(expected_sources), "Installed staged external authority differs")
    require(receipt["scope"] == SCOPE and receipt["python_semantic_authority"] == "forbidden"
            and receipt["empirical"] == "unassessed", "Installed staged scope promoted")
    fixture = staged.checked_fixture(ROOT, fixture_path)
    require(type(receipt["package"]) is str and Path(receipt["package"]).is_absolute()
            and not Path(receipt["package"]).resolve().is_relative_to(ROOT), "Installed staged package belongs to checkout")
    require(receipt["installed_modules"] == component.installed_source_modules(ROOT), "Installed staged package inventory differs")
    component.check_installed_origins(receipt["parent_imports"], receipt["package"], receipt["installed_modules"])
    require(receipt["authoring"] == staged.author_request(fixture["request"])[1], "Staged original Python authoring changed")
    rows = receipt["observations"]
    require(type(rows) is list and all(type(row) is dict and set(row) == {"name", "path", "sha256", "bytes"} for row in rows),
            "Malformed installed staged sidecars")
    staged.check_census(row["name"] for row in rows)
    observations, paths = [], []
    for row in rows:
        require(row["path"] == FOLDER + "/" + row["name"] + ".json", "Foreign staged observation path")
        path = component._retained(row["path"], evidence_root, {key: row[key] for key in ("sha256", "bytes")}, component.MAX_EVIDENCE)
        observations.append({"name": row["name"], "result": read_json(path, component.MAX_EVIDENCE)})
        paths.append(path)
    require(receipt["observations_fingerprint"] == canonical_digest(observations), "Complete staged observations changed")
    values = check_observations(observations, fixture)
    pubs = receipt["publications"]
    require(type(pubs) is list and len(pubs) == 1 and type(pubs[0]) is dict and set(pubs[0]) == {"path", "sha256", "bytes"}
            and pubs[0]["path"] == FOLDER + "/staged-program.zip", "Missing or foreign paired staged publication")
    path = component._retained(pubs[0]["path"], evidence_root, {key: pubs[0][key] for key in ("sha256", "bytes")}, component.MAX_EVIDENCE)
    archive_receipt(values["export-verify"], path); paths.append(path)
    require(set((evidence_root / FOLDER).iterdir()) == set(paths), "Missing or extra staged evidence file")
    for row in (*rows, *pubs):
        component._retained(row["path"], evidence_root, {key: row[key] for key in ("sha256", "bytes")}, component.MAX_EVIDENCE)
    require(input_pins() == originals, "Original staged authority changed during validation")
    return values


def compare_installed(paths, fixture_path, identity_value, binary_authorities, *, expected_sources):
    require(len(paths) == 4 and set(binary_authorities) == {("Linux", "x86_64"), ("Darwin", "arm64")},
            "Staged comparison requires four slots and both supplied native authorities")
    found, observations, attempts = set(), None, []
    for path in paths:
        receipt = read_json(path, component.MAX_RECEIPT)
        require(type(receipt) is dict and type(receipt.get("python_version")) is str, "Malformed staged slot")
        slot = receipt.get("system"), receipt.get("machine"), ".".join(receipt["python_version"].split(".")[:2])
        require(slot in component.SLOTS and slot not in found, "Duplicate or unsupported staged slot")
        values = validate_installed(receipt, path.parent, fixture_path, identity_value, binary_authorities[slot[:2]],
                                    expected_sources=expected_sources, expected_slot=slot)
        require(observations is None or values == observations, "Complete staged results differ across installed slots")
        observations = values; found.add(slot)
        attempts.append({"slot": list(slot), "run_attempt": receipt["run_attempt"], "receipt": pin(path, component.MAX_RECEIPT)})
    require(found == component.SLOTS, "Incomplete installed staged slots")
    return {"schema_version": SCHEMA, "status": "pass", **identity_value, "scope": SCOPE, "inputs": input_pins(),
            "slots": sorted(found), "attempts": sorted(attempts, key=lambda row: row["slot"]),
            "observations_fingerprint": canonical_digest(observations), "empirical": "unassessed", "python_semantic_authority": "forbidden"}


def run(args):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Installed staged native campaign is hosted-only")
    hosted, before = source_identity(), source_snapshot(ROOT)
    require(hosted["run_id"] != "local", "Installed staged campaign needs a hosted run")
    slot = platform.system(), platform.machine(), f"{sys.version_info.major}.{sys.version_info.minor}"
    require(slot in component.SLOTS and not Path.cwd().resolve().is_relative_to(ROOT), "Installed staged runtime must be outside checkout")
    binaries = {"biocompiler-core": args.core_sha256, "biocompiler-verify": args.verify_sha256}
    require(all(component._sha(value) for value in binaries.values()), "External native pins are required")
    binary_paths = {role: getattr(args, role).absolute() for role in ("core", "verify")}
    measured = {role: pin(path, 256 * 1024 * 1024, executable=True) for role, path in binary_paths.items()}
    require(all(measured[role]["sha256"] == binaries["biocompiler-" + role] for role in measured), "Installed native bytes differ from external authority")
    fixture, originals = staged.checked_fixture(ROOT, args.fixture), input_pins()
    spec = importlib.util.find_spec("biocompiler")
    require(spec is not None and spec.origin is not None, "Install the reviewed staged SDK")
    package = Path(spec.origin).resolve().parent
    modules = component.installed_package_modules(ROOT, package)
    output = args.output.absolute()
    require(output.name == RECEIPT and not output.exists() and not output.is_relative_to(ROOT)
            and output.parent.is_dir() and not output.parent.is_symlink(), "Use one fresh installed staged receipt outside checkout")
    artifacts = output.with_suffix(""); artifacts.mkdir(exist_ok=False)
    result = {"schema_version": SCHEMA, "status": "incomplete", **hosted, "system": slot[0], "machine": slot[1],
        "python_version": platform.python_version(), "scope": SCOPE, "inputs": originals, "binary_sha256": binaries,
        "package": str(package), "installed_modules": modules, "parent_imports": {}, "source_snapshot_sha256": canonical_digest(before),
        "authoring": None, "observations": [], "observations_fingerprint": None, "publications": [],
        "python_semantic_authority": "forbidden", "empirical": "unassessed"}
    def save():
        raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(len(raw) <= component.MAX_RECEIPT, "Installed staged receipt exceeded its bound"); output.write_bytes(raw)
    def retain(name, value):
        from biocompiler.core_client import encode_json
        index = len(result["observations"])
        require(index < len(staged.OBSERVATIONS) and name == staged.OBSERVATIONS[index], "Changed installed staged observation order")
        raw = encode_json(value); require(len(raw) <= component.MAX_EVIDENCE, "Staged observation exceeded its bound")
        path = artifacts / (name + ".json")
        with path.open("xb") as stream: stream.write(raw)
        result["observations"].append({"name": name, "path": str(path.relative_to(output.parent)), **pin(path)})
        save()
    boundary = component.ComponentBoundary(package); previous = sys.getprofile()
    def unchanged():
        require(source_identity() == hosted and source_snapshot(ROOT) == before and component.installed_package_modules(ROOT, package) == modules
                and input_pins() == originals and {role: pin(path, 256 * 1024 * 1024, executable=True)
                    for role, path in binary_paths.items()} == measured, "Installed staged source/run/package/native/original authority changed")
    try:
        boundary.origins()
        request, result["authoring"] = staged.author_request(fixture["request"])
        sys.meta_path.insert(0, boundary); sys.setprofile(boundary.trace)
        from biocompiler.core_client import CoreClient
        from biocompiler.core_policy_component_material import PolicyComponentMaterialClient
        from biocompiler.policy import component_material as sdk
        core = PolicyComponentMaterialClient(CoreClient(binary_paths["core"], role="core", expected_sha256=binaries["biocompiler-core"], timeout_seconds=90))
        transport = CoreClient(binary_paths["verify"], role="verify", expected_sha256=binaries["biocompiler-verify"], timeout_seconds=90)
        staged.exercise(fixture, request, core, transport, PolicyComponentMaterialClient(transport), sdk, retain, artifacts,
                        tuple(ROOT / name for name in staged.INPUTS))
        staged.check_census(row["name"] for row in result["observations"])
        result["parent_imports"] = boundary.origins()
        component.check_installed_origins(result["parent_imports"], str(package), modules)
        path = artifacts / "staged-program.zip"
        result["publications"] = [{"path": str(path.relative_to(output.parent)), **pin(path)}]
        observations = [{"name": row["name"], "result": read_json(output.parent / row["path"], component.MAX_EVIDENCE)} for row in result["observations"]]
        result["observations_fingerprint"] = canonical_digest(observations); result["status"] = "pass"
    except Exception as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        sys.setprofile(previous)
        if boundary in sys.meta_path: sys.meta_path.remove(boundary)
        try:
            unchanged()
            if result["status"] == "pass":
                require(boundary.origins() == result["parent_imports"], "Installed staged imports changed")
                validate_installed(result, output.parent, args.fixture, hosted, binaries, expected_sources=before, expected_slot=slot)
                unchanged()
                require(boundary.origins() == result["parent_imports"], "Installed staged imports changed during validation")
        except Exception as error:
            result.update(status="failed", source_error=str(error))
        save()
        require(result["status"] == "pass", result.get("source_error", result.get("error", "Incomplete installed staged campaign")))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("fixture", "core", "verify", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("core-sha256", "verify-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    for name in ("fixture", "core", "verify", "output"):
        setattr(args, name, getattr(args, name).absolute())
    result = run(args)
    print(json.dumps({"schema_version": result["schema_version"], "status": result["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
