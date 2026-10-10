"""Hosted installed two_observation SDK witness and retained-evidence gate.

Executes only supplied installed native bytes against separately retained source
declarations. This additive campaign preserves the earlier component and staged
receipts. Its finite, conditional result supplies no empirical or clinical claim.
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
    import check_policy_two_observation_material as two_observation
    import check_policy_two_observation_fixture as fixture_tool
    from check_policy_core import canonical_digest, read_json, source_identity
    from check_policy_development import source_snapshot
    from check_policy_material import archive_receipt
except ModuleNotFoundError:
    from tools import check_policy_component_material as component
    from tools import check_policy_two_observation_material as two_observation
    from tools import check_policy_two_observation_fixture as fixture_tool
    from tools.check_policy_core import canonical_digest, read_json, source_identity
    from tools.check_policy_development import source_snapshot
    from tools.check_policy_material import archive_receipt

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "biocompiler.policy_two_observation_material_campaign.v0.1"
SCOPE = "installed_sdk_bounded_conditional_two_observation_material"
RECEIPT = "two-observation-material.json"
FOLDER = "two-observation-material"
require = component._require
pin = component.bounded_pin


def input_pins(root=ROOT):
    return {name: pin(root / name, 4_000_000) for name in two_observation.INPUTS}


def check_census(rows):
    require(type(rows) is list and all(type(row) is dict for row in rows)
            and [(row.get("case"), row.get("name")) for row in rows]
            == [(case, name) for case in ("A", "B") for name in component.CASE_NAMES],
            "Incomplete, duplicate or reordered installed two_observation observations")


def check_observations(observations, fixture):
    """Retain the shared 26 controls and the two_observation-specific literal oracle."""
    return component.check_observations(observations, fixture,
        validate_result=two_observation.checked_result, expected_obligations=two_observation.OBLIGATIONS)


def validate_fixture(fixture_path, provenance_path, identity_value, binaries, slot, expected_sources):
    value = fixture_tool.validate(ROOT, fixture_path, provenance_path, identity=identity_value,
        native_sha256={role: binaries["biocompiler-" + role] for role in ("core", "verify")},
        expected_platform=slot[:2])
    require(value["sources"] == expected_sources, "Two-observation fixture source authority differs")


def validate_installed(receipt, evidence_root, fixture_path, identity_value, binaries, *, expected_sources,
                       fixture_provenance, expected_slot=None):
    """Independently check package origins, original authority and all sidecars."""
    evidence_root, fixture_path, fixture_provenance = Path(evidence_root), Path(fixture_path), Path(fixture_provenance)
    originals = input_pins()
    authority = component.fixture_authority_pins(fixture_path, fixture_provenance)
    fields = {"schema_version", "status", "revision", "head_revision", "run_id", "run_attempt", "system", "machine", "python_version",
              "scope", "inputs", "fixture_sha256", "fixture_provenance_sha256", "binary_sha256", "package", "installed_modules",
              "parent_imports", "source_snapshot_sha256", "authoring", "observations", "observations_fingerprint",
              "publications", "python_semantic_authority", "empirical"}
    require(type(receipt) is dict and set(receipt) == fields and receipt["schema_version"] == SCHEMA and receipt["status"] == "pass",
            "Not a complete installed two_observation receipt")
    require(type(receipt["python_version"]) is str and re.fullmatch(r"3\.(11|14)\.[0-9]+", receipt["python_version"]),
            "Invalid installed two_observation runtime")
    slot = receipt["system"], receipt["machine"], ".".join(receipt["python_version"].split(".")[:2])
    require(slot in component.SLOTS and (expected_slot is None or slot == expected_slot), "Wrong installed two_observation slot")
    require(all(receipt[key] == identity_value[key] for key in ("revision", "head_revision", "run_id"))
            and type(receipt["run_attempt"]) is str and re.fullmatch(r"[1-9][0-9]*", receipt["run_attempt"])
            and int(receipt["run_attempt"]) <= int(identity_value["run_attempt"]), "Stale installed two_observation source/run/attempt")
    require(set(binaries) == {"biocompiler-core", "biocompiler-verify"} and all(component._sha(value) for value in binaries.values())
            and receipt["binary_sha256"] == binaries and receipt["inputs"] == originals
            and receipt["fixture_sha256"] == authority["fixture"]["sha256"]
            and receipt["fixture_provenance_sha256"] == authority["provenance"]["sha256"]
            and receipt["source_snapshot_sha256"] == canonical_digest(expected_sources), "Installed two_observation external authority differs")
    require(receipt["scope"] == SCOPE and receipt["python_semantic_authority"] == "forbidden"
            and receipt["empirical"] == "unassessed", "Installed two_observation scope promoted")
    validate_fixture(fixture_path, fixture_provenance, identity_value, binaries, slot, expected_sources)
    fixture = two_observation.checked_fixture(ROOT, fixture_path)
    require(type(receipt["package"]) is str and Path(receipt["package"]).is_absolute()
            and not Path(receipt["package"]).resolve().is_relative_to(ROOT), "Installed two_observation package belongs to checkout")
    require(receipt["installed_modules"] == component.installed_source_modules(ROOT), "Installed two_observation package inventory differs")
    component.check_installed_origins(receipt["parent_imports"], receipt["package"], receipt["installed_modules"])
    authoring = [{"case": case["id"], **two_observation.author_request(case["request"], case["id"] == "B")[1]}
                 for case in fixture["cases"]]
    require(receipt["authoring"] == authoring, "Two-observation original Python authoring changed")
    rows = receipt["observations"]
    check_census(rows)
    require(all(set(row) == {"case", "name", "path", "sha256", "bytes"} for row in rows), "Malformed two_observation sidecars")
    observations, paths = [], []
    for row in rows:
        require(row["path"] == FOLDER + "/" + row["case"] + "-" + row["name"] + ".json", "Foreign two_observation observation path")
        path = component._retained(row["path"], evidence_root, {key: row[key] for key in ("sha256", "bytes")}, component.MAX_EVIDENCE)
        observations.append({"case": row["case"], "name": row["name"], "result": read_json(path, component.MAX_EVIDENCE)})
        paths.append(path)
    require(receipt["observations_fingerprint"] == canonical_digest(observations), "Complete two_observation observations changed")
    values = check_observations(observations, fixture)
    publications = receipt["publications"]
    require(type(publications) is list and all(type(row) is dict and set(row) == {"case", "path", "sha256", "bytes"} for row in publications)
            and [row["case"] for row in publications] == ["A", "B"], "Missing or reordered paired two_observation publications")
    for row in publications:
        require(row["path"] == FOLDER + "/" + row["case"] + "-program.zip", "Foreign two_observation publication path")
        path = component._retained(row["path"], evidence_root, {key: row[key] for key in ("sha256", "bytes")}, component.MAX_EVIDENCE)
        archive_receipt(values[row["case"]]["exported"], path)
        paths.append(path)
    require(set((evidence_root / FOLDER).iterdir()) == set(paths), "Missing or extra two_observation evidence file")
    for row in (*rows, *publications):
        component._retained(row["path"], evidence_root, {key: row[key] for key in ("sha256", "bytes")}, component.MAX_EVIDENCE)
    require(input_pins() == originals and component.fixture_authority_pins(fixture_path, fixture_provenance) == authority,
            "Original two_observation authority changed during validation")
    return values


def compare_installed(paths, fixture_path, identity_value, binary_authorities, *, expected_sources, fixture_provenances):
    platforms = {("Linux", "x86_64"), ("Darwin", "arm64")}
    require(len(paths) == 4 and set(binary_authorities) == set(fixture_provenances) == platforms,
            "Two-observation comparison requires four slots and both native/fixture authorities")
    require(source_snapshot(ROOT) == expected_sources, "Two-observation comparison source authority differs")
    fixture_path = Path(fixture_path)
    fixture_pin = pin(fixture_path, 4_000_000)
    originals = input_pins()
    found, baseline, observation_fingerprint, attempts, retained, authorities = set(), None, None, [], [], []
    for raw_path in paths:
        path = Path(raw_path)
        receipt_pin = pin(path, component.MAX_RECEIPT)
        receipt = read_json(path, component.MAX_RECEIPT)
        require(type(receipt) is dict and type(receipt.get("python_version")) is str, "Malformed two_observation slot")
        slot = receipt.get("system"), receipt.get("machine"), ".".join(receipt["python_version"].split(".")[:2])
        require(slot in component.SLOTS and slot not in found, "Duplicate or unsupported two_observation slot")
        provenance = Path(fixture_provenances[slot[:2]])
        local_fixture = provenance.parent / "originals.json"
        require(pin(local_fixture, 4_000_000) == fixture_pin, "Complete two_observation original packets differ across platforms")
        authority = component.fixture_authority_pins(local_fixture, provenance)
        values = validate_installed(receipt, path.parent, local_fixture, identity_value, binary_authorities[slot[:2]],
            expected_sources=expected_sources, fixture_provenance=provenance, expected_slot=slot)
        require(baseline is None or (values == baseline and receipt["observations_fingerprint"] == observation_fingerprint),
                "Complete two_observation results differ across installed slots")
        baseline = values
        observation_fingerprint = receipt["observations_fingerprint"]
        found.add(slot)
        attempts.append({"slot": list(slot), "run_attempt": receipt["run_attempt"], "receipt": receipt_pin})
        retained.append((path, component.MAX_RECEIPT, receipt_pin))
        retained.extend((path.parent / row["path"], component.MAX_EVIDENCE, {key: row[key] for key in ("sha256", "bytes")})
                        for row in (*receipt["observations"], *receipt["publications"]))
        authorities.append((local_fixture, provenance, authority))
    require(found == component.SLOTS and source_snapshot(ROOT) == expected_sources
            and pin(fixture_path, 4_000_000) == fixture_pin and input_pins() == originals
            and all(pin(path, maximum) == expected for path, maximum, expected in retained)
            and all(component.fixture_authority_pins(original, provenance) == expected for original, provenance, expected in authorities),
            "Incomplete two_observation slots or changed retained authority")
    return {"schema_version": SCHEMA, "status": "pass", **identity_value, "scope": SCOPE, "inputs": originals,
            "fixture_sha256": fixture_pin["sha256"], "slots": sorted(found), "attempts": sorted(attempts, key=lambda row: row["slot"]),
            "observations_fingerprint": observation_fingerprint, "empirical": "unassessed", "python_semantic_authority": "forbidden"}


def run(args):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Installed two_observation native campaign is hosted-only")
    hosted, before = source_identity(), source_snapshot(ROOT)
    require(hosted["run_id"] != "local", "Installed two_observation campaign needs a hosted run")
    slot = platform.system(), platform.machine(), f"{sys.version_info.major}.{sys.version_info.minor}"
    require(slot in component.SLOTS and not Path.cwd().resolve().is_relative_to(ROOT), "Installed two_observation runtime must be outside checkout")
    binaries = {"biocompiler-core": args.core_sha256, "biocompiler-verify": args.verify_sha256}
    require(all(component._sha(value) for value in binaries.values()), "External native pins are required")
    binary_paths = {role: getattr(args, role).absolute() for role in ("core", "verify")}
    measured = {role: pin(path, 256 * 1024 * 1024, executable=True) for role, path in binary_paths.items()}
    require(all(measured[role]["sha256"] == binaries["biocompiler-" + role] for role in measured), "Installed native bytes differ from external authority")
    fixture, originals = two_observation.checked_fixture(ROOT, args.fixture), input_pins()
    authority = component.fixture_authority_pins(args.fixture, args.fixture_provenance)
    validate_fixture(args.fixture, args.fixture_provenance, hosted, binaries, slot, before)
    spec = importlib.util.find_spec("biocompiler")
    require(spec is not None and spec.origin is not None, "Install the reviewed two_observation SDK")
    package = Path(spec.origin).resolve().parent
    modules = component.installed_package_modules(ROOT, package)
    output = args.output.absolute()
    require(output.name == RECEIPT and not output.exists() and not output.is_relative_to(ROOT)
            and output.parent.is_dir() and not output.parent.is_symlink(), "Use one fresh installed two_observation receipt outside checkout")
    artifacts = output.with_suffix("")
    artifacts.mkdir(exist_ok=False)
    result = {"schema_version": SCHEMA, "status": "incomplete", **hosted, "system": slot[0], "machine": slot[1],
        "python_version": platform.python_version(), "scope": SCOPE, "inputs": originals,
        "fixture_sha256": authority["fixture"]["sha256"], "fixture_provenance_sha256": authority["provenance"]["sha256"],
        "binary_sha256": binaries, "package": str(package), "installed_modules": modules, "parent_imports": {},
        "source_snapshot_sha256": canonical_digest(before), "authoring": [], "observations": [],
        "observations_fingerprint": None, "publications": [], "python_semantic_authority": "forbidden", "empirical": "unassessed"}
    def save():
        raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(len(raw) <= component.MAX_RECEIPT, "Installed two_observation receipt exceeded its bound")
        output.write_bytes(raw)
    def retain(case, name, value):
        from biocompiler.core_client import encode_json
        index = len(result["observations"])
        wanted = [(label, item) for label in ("A", "B") for item in component.CASE_NAMES]
        require(index < len(wanted) and (case, name) == wanted[index], "Changed installed two_observation observation order")
        raw = encode_json(value)
        require(len(raw) <= component.MAX_EVIDENCE, "Two-observation observation exceeded its bound")
        path = artifacts / (case + "-" + name + ".json")
        with path.open("xb") as stream:
            stream.write(raw)
        result["observations"].append({"case": case, "name": name, "path": str(path.relative_to(output.parent)), **pin(path)})
        save()
    boundary = component.ComponentBoundary(package)
    previous = sys.getprofile()
    def unchanged():
        require(source_identity() == hosted and source_snapshot(ROOT) == before and component.installed_package_modules(ROOT, package) == modules
                and input_pins() == originals and component.fixture_authority_pins(args.fixture, args.fixture_provenance) == authority
                and {role: pin(path, 256 * 1024 * 1024, executable=True) for role, path in binary_paths.items()} == measured,
                "Installed two_observation source/run/package/native/original authority changed")
    try:
        boundary.origins()
        cases = []
        for case in fixture["cases"]:
            request, authored = two_observation.author_request(case["request"], case["id"] == "B")
            cases.append((case, request))
            result["authoring"].append({"case": case["id"], **authored})
        sys.meta_path.insert(0, boundary)
        sys.setprofile(boundary.trace)
        from biocompiler.core_client import CoreClient
        from biocompiler.core_policy_component_material import PolicyComponentMaterialClient
        from biocompiler.policy import component_material as sdk
        core = PolicyComponentMaterialClient(CoreClient(binary_paths["core"], role="core", expected_sha256=binaries["biocompiler-core"], timeout_seconds=90))
        transport = CoreClient(binary_paths["verify"], role="verify", expected_sha256=binaries["biocompiler-verify"], timeout_seconds=90)
        component.exercise_cases(cases, core, transport, PolicyComponentMaterialClient(transport), sdk, retain, artifacts,
            (args.fixture, args.fixture_provenance, *(ROOT / name for name in two_observation.INPUTS)), validate_result=two_observation.checked_result, expected_obligations=two_observation.OBLIGATIONS)
        check_census(result["observations"])
        result["parent_imports"] = boundary.origins()
        component.check_installed_origins(result["parent_imports"], str(package), modules)
        for case in ("A", "B"):
            path = artifacts / (case + "-program.zip")
            result["publications"].append({"case": case, "path": str(path.relative_to(output.parent)), **pin(path)})
        observations = [{"case": row["case"], "name": row["name"], "result": read_json(output.parent / row["path"], component.MAX_EVIDENCE)}
                        for row in result["observations"]]
        result["observations_fingerprint"] = canonical_digest(observations)
        result["status"] = "pass"
    except Exception as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        sys.setprofile(previous)
        if boundary in sys.meta_path:
            sys.meta_path.remove(boundary)
        try:
            unchanged()
            if result["status"] == "pass":
                require(boundary.origins() == result["parent_imports"], "Installed two_observation imports changed")
                validate_installed(result, output.parent, args.fixture, hosted, binaries, expected_sources=before,
                                   fixture_provenance=args.fixture_provenance, expected_slot=slot)
                unchanged()
                require(boundary.origins() == result["parent_imports"], "Installed two_observation imports changed during validation")
        except Exception as error:
            result.update(status="failed", source_error=str(error))
        save()
        require(result["status"] == "pass", result.get("source_error", result.get("error", "Incomplete installed two_observation campaign")))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("fixture", "fixture-provenance", "core", "verify", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("core-sha256", "verify-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    for name in ("fixture", "fixture_provenance", "core", "verify", "output"):
        setattr(args, name, getattr(args, name).absolute())
    result = run(args)
    print(json.dumps({"schema_version": result["schema_version"], "status": result["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
