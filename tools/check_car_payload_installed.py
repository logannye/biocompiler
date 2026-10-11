"""Hosted installed nominal CAR workflow and inert complete-evidence comparison.

The campaign uses owned installed defaults outside the checkout. Python records
and independently checks transport/artifact correspondence; all source and
material semantics remain in fresh native Core/Verify calls. No process runs
on import or during retained-evidence validation.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
from importlib import metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys

try:
    import check_car_payload as car
    import check_policy_component_material as component
    from check_policy_core import canonical_digest, read_json, source_identity
    from check_policy_development import source_snapshot
except ModuleNotFoundError:
    from tools import check_car_payload as car
    from tools import check_policy_component_material as component
    from tools.check_policy_core import canonical_digest, read_json, source_identity
    from tools.check_policy_development import source_snapshot

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "biocompiler.car_payload_installed_campaign.v0.1"
SCOPE = "installed_nominal_car_reference_under_supplied_expression_and_material_contracts"
EXPECTED = "data/car_payload/expected.json"
RECEIPT = "car-payload.json"
FOLDER = "car-payload"
EXAMPLE = "examples/car_payload.py"
REFERENCE = "src/biocompiler/policy/data/car_rm61461_reference_v01.json"
COPY_INPUTS = tuple(name for name in car.INPUTS if not name.startswith("src/") or name == REFERENCE)
MAX_RECORD = 2 * 1024 * 1024
DATA_PATTERNS = ("py.typed", "studio/static/*", "studio/data/*.json", "policy/data/*.json")
REQUIRED_MODULES = car.REQUIRED_MODULES | {"biocompiler", "biocompiler.core_distribution"}
require = component._require
pin = component.bounded_pin


def checked_inputs(root=ROOT, expected=None):
    return car.checked_assets(root, expected or root / EXPECTED)


def input_pins(root=ROOT):
    checked_inputs(root)
    return {name: pin(root / name, 4_000_000) for name in car.INPUTS}


def _bytes(path, maximum):
    """Read even empty package data, with the same finite regular-file boundary."""
    path = Path(path)
    require(not path.is_symlink(), "Redirected CAR package/RECORD file")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and 0 <= before.st_size <= maximum, "Unbounded or nonregular CAR package file")
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
    require(len(raw) == before.st_size and (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "CAR package file changed during reading")
    return raw


def _raw_pin(raw):
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def source_data(root=ROOT):
    package = root / "src/biocompiler"
    paths = sorted({path for pattern in DATA_PATTERNS for path in package.glob(pattern) if path.is_file()})
    require(0 < len(paths) <= 1024, "Invalid source CAR package-data census")
    return {path.relative_to(package).as_posix(): _raw_pin(_bytes(path, component.MAX_EVIDENCE)) for path in paths}


def check_record(value, package, modules, data):
    """Check source-owned Python/data rows against the retained installed RECORD.

    Other wheel metadata and generated release bytes remain bound by the outer
    supplied-wheel ownership gate; a self-consistent RECORD is not authentication.
    """
    require(type(value) is dict and set(value) == {"path", "text", "sha256", "bytes"}
            and type(value["text"]) is str, "Missing complete CAR SDK RECORD")
    raw = value["text"].encode("utf-8")
    require(0 < len(raw) <= MAX_RECORD and _raw_pin(raw) == {key: value[key] for key in ("sha256", "bytes")},
            "Changed or unbounded CAR SDK RECORD")
    path, package = Path(value["path"]), Path(package)
    require(path.is_absolute() and ".." not in path.parts and path.name == "RECORD"
            and path.parent.parent == package.parent
            and re.fullmatch(r"biocompiler-[A-Za-z0-9_.+\-]+\.dist-info", path.parent.name), "Foreign CAR SDK RECORD path")
    try:
        rows = list(csv.reader(io.StringIO(value["text"], newline=""), strict=True))
    except csv.Error as error:
        raise AssertionError("Malformed CAR SDK RECORD") from error
    require(0 < len(rows) <= 10_000 and all(len(row) == 3 and row[0] for row in rows)
            and len({row[0] for row in rows}) == len(rows), "Duplicate or malformed CAR SDK RECORD rows")
    indexed = {row[0]: row for row in rows}
    for name, measured in {**modules, **data}.items():
        digest = base64.urlsafe_b64encode(bytes.fromhex(measured["sha256"])).rstrip(b"=").decode("ascii")
        key = "biocompiler/" + name
        require(indexed.get(key) == [key, "sha256=" + digest, str(measured["bytes"])], "CAR SDK RECORD differs from original package bytes: " + name)
    key = path.relative_to(package.parent).as_posix()
    require(indexed.get(key) == [key, "", ""], "Missing exact CAR SDK RECORD self-row")


def installed_package(package):
    modules = component.installed_package_modules(ROOT, package)
    expected = source_data(ROOT)
    actual_paths = sorted({path for pattern in DATA_PATTERNS for path in package.glob(pattern) if path.is_file()})
    actual = {path.relative_to(package).as_posix(): _raw_pin(_bytes(path, component.MAX_EVIDENCE)) for path in actual_paths}
    require(actual == expected, "Installed CAR package data differs from complete source authority")
    distributions = [value for value in metadata.distributions()
        if re.sub(r"[-_.]+", "-", value.metadata.get("Name", "")).lower() == "biocompiler"]
    require(len(distributions) == 1, "CAR requires exactly one installed SDK distribution")
    distribution = distributions[0]
    records = [entry for entry in distribution.files or () if str(entry).endswith(".dist-info/RECORD")]
    require(len(records) == 1, "Missing or duplicate CAR SDK RECORD")
    path = Path(distribution.locate_file(records[0])).absolute()
    require(not any(item.is_symlink() for item in (path, path.parent, package, package.parent)), "Redirected CAR SDK RECORD ownership")
    raw = _bytes(path, MAX_RECORD)
    record = {"path": str(path), "text": raw.decode("utf-8"), **_raw_pin(raw)}
    check_record(record, package, modules, actual)
    return modules, actual, record


def check_origins(origins, package, modules):
    require(type(package) is str and Path(package).is_absolute() and ".." not in Path(package).parts,
            "Missing installed CAR package origin")
    require(type(origins) is dict and REQUIRED_MODULES <= set(origins), "Missing installed CAR transport/authoring origins")
    for name, origin in origins.items():
        require(car.CarBoundary.allowed(name), "Forbidden Python semantic module in CAR campaign")
        relative = name.removeprefix("biocompiler").lstrip(".").replace(".", "/")
        options = (relative + ".py", relative + "/__init__.py") if relative else ("__init__.py",)
        matches = [path for path in options if path in modules]
        require(len(matches) == 1 and origin == str(Path(package) / matches[0]), "Foreign installed CAR module origin")


def validate_installed(receipt, evidence_root, expected_path, identity, binaries, *, expected_sources, expected_slot=None):
    evidence_root = Path(evidence_root)
    originals, packet = input_pins(), checked_inputs(ROOT, expected_path)
    fields = {"schema_version", "status", "revision", "head_revision", "run_id", "run_attempt", "system", "machine", "python_version",
        "scope", "inputs", "binary_sha256", "package", "installed_modules", "installed_data", "sdk_record", "parent_imports", "source_snapshot_sha256",
        "working_directory", "runtime_inputs", "resolution", "observations", "observations_fingerprint", "projects", "publications", "native_actions", "files",
        "python_semantic_authority", "empirical", "human_use", "real_researcher_project_qualified"}
    require(type(receipt) is dict and set(receipt) == fields and receipt["schema_version"] == SCHEMA and receipt["status"] == "pass",
            "Not a complete installed CAR receipt")
    require(type(receipt["python_version"]) is str and re.fullmatch(r"3\.(11|14)\.[0-9]+", receipt["python_version"]), "Invalid installed CAR runtime")
    slot = receipt["system"], receipt["machine"], ".".join(receipt["python_version"].split(".")[:2])
    require(slot in component.SLOTS and (expected_slot is None or slot == expected_slot), "Wrong installed CAR slot")
    require(all(receipt[key] == identity[key] for key in ("revision", "head_revision", "run_id"))
            and type(receipt["run_attempt"]) is str and re.fullmatch(r"[1-9][0-9]*", receipt["run_attempt"])
            and int(receipt["run_attempt"]) <= int(identity["run_attempt"]), "Stale installed CAR source/run/attempt")
    require(set(binaries) == {"biocompiler-core", "biocompiler-verify"} and all(component._sha(v) for v in binaries.values())
            and receipt["binary_sha256"] == binaries and receipt["inputs"] == originals
            and receipt["source_snapshot_sha256"] == canonical_digest(expected_sources), "Installed CAR external authority differs")
    require(receipt["scope"] == SCOPE and receipt["python_semantic_authority"] == "forbidden" and receipt["empirical"] == "unassessed"
            and receipt["human_use"] == "unassessed" and receipt["real_researcher_project_qualified"] is False
            and receipt["resolution"] == "owned_installed_defaults", "Installed CAR scope or resolution promoted")
    require(type(receipt["package"]) is str and Path(receipt["package"]).is_absolute()
            and not Path(receipt["package"]).resolve().is_relative_to(ROOT), "Installed CAR package belongs to checkout")
    require(canonical_digest(receipt["installed_modules"]) == canonical_digest(component.installed_source_modules(ROOT))
            and canonical_digest(receipt["installed_data"]) == canonical_digest(source_data()), "Installed CAR Python/data package inventory differs")
    check_record(receipt["sdk_record"], receipt["package"], receipt["installed_modules"], receipt["installed_data"])
    check_origins(receipt["parent_imports"], receipt["package"], receipt["installed_modules"])
    require(type(receipt["working_directory"]) is str, "Missing CAR independent workspace")
    cwd = Path(receipt["working_directory"])
    require(cwd.is_absolute() and ".." not in cwd.parts and not cwd.is_relative_to(ROOT), "CAR working directory is not outside checkout")
    require(receipt["runtime_inputs"] == {name: {"path": str(cwd / "car-inputs" / name), **originals[name]} for name in COPY_INPUTS},
            "CAR example/input copy census differs")
    rows = receipt["observations"]
    require(type(rows) is list and all(type(row) is dict and set(row) == {"name", "path", "sha256", "bytes"} for row in rows),
            "Malformed installed CAR sidecars")
    require(tuple(row["name"] for row in rows) == car.OBSERVATIONS, "Incomplete, duplicate or reordered installed CAR observation census")
    observations = []
    for row in rows:
        require(row["path"] == FOLDER + "/" + row["name"] + ".json", "Foreign CAR observation path")
        path = component._retained(row["path"], evidence_root, {key: row[key] for key in ("sha256", "bytes")}, component.MAX_EVIDENCE)
        observations.append({"name": row["name"], "result": read_json(path, component.MAX_EVIDENCE)})
    require(receipt["observations_fingerprint"] == canonical_digest(observations), "CAR observations fingerprint differs")
    values = car.check_observations({row["name"]: row["result"] for row in observations}, packet)
    folder = evidence_root / FOLDER
    require(not folder.is_symlink() and folder.is_dir(), "Missing or redirected CAR evidence directory")
    require(type(receipt["files"]) is dict and set(receipt["files"]) == {FOLDER + "/" + name for name in car.EVIDENCE_FILES},
            "Missing or extra installed CAR evidence pins")
    require(set(folder.iterdir()) == {evidence_root / name for name in receipt["files"]}, "Missing or extra installed CAR evidence file")
    for name, measured in receipt["files"].items():
        component._retained(name, evidence_root, measured, component.MAX_EVIDENCE)
    action_row = next(row for row in rows if row["name"] == "native-actions")
    require(receipt["native_actions"] == {key: action_row[key] for key in ("path", "sha256", "bytes")}
            and values["native-actions"]["resolution"] == "owned_installed_defaults", "Installed CAR native actions changed resolution or evidence")
    car.validate_files(values, packet, folder, projects=receipt["projects"], publications=receipt["publications"], native_actions=values["native-actions"])
    require(input_pins() == originals, "CAR input authority changed during validation")
    return values


def compare_installed(paths, expected_path, identity, binary_authorities, *, expected_sources):
    require(len(paths) == 4 and set(binary_authorities) == {("Linux", "x86_64"), ("Darwin", "arm64")}, "CAR comparison requires four slots and both native authorities")
    found, observations, attempts = set(), None, []
    for path in paths:
        path = Path(path)
        receipt = read_json(path, component.MAX_RECEIPT)
        require(type(receipt) is dict and type(receipt.get("python_version")) is str, "Malformed CAR slot")
        slot = receipt.get("system"), receipt.get("machine"), ".".join(receipt["python_version"].split(".")[:2])
        require(slot in component.SLOTS and slot not in found, "Duplicate or unsupported CAR slot")
        values = validate_installed(receipt, path.parent, expected_path, identity, binary_authorities[slot[:2]], expected_sources=expected_sources, expected_slot=slot)
        require(observations is None or canonical_digest(values) == canonical_digest(observations), "Complete CAR results differ across installed slots")
        observations = values
        found.add(slot)
        attempts.append({"slot": list(slot), "run_attempt": receipt["run_attempt"], "receipt": pin(path, component.MAX_RECEIPT)})
    require(found == component.SLOTS, "Incomplete CAR installed slots")
    return {"schema_version": SCHEMA, "status": "pass", **identity, "scope": SCOPE, "inputs": input_pins(),
        "slots": sorted(found), "attempts": sorted(attempts, key=lambda row: row["slot"]), "observations_fingerprint": canonical_digest(observations),
        "empirical": "unassessed", "human_use": "unassessed", "python_semantic_authority": "forbidden", "real_researcher_project_qualified": False}


def run(args):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted", "Installed CAR campaign is hosted-only")
    hosted, before = source_identity(), source_snapshot(ROOT)
    require(hosted["run_id"] != "local", "Installed CAR campaign needs a hosted run")
    slot = platform.system(), platform.machine(), f"{sys.version_info.major}.{sys.version_info.minor}"
    require(slot in component.SLOTS and not Path.cwd().resolve().is_relative_to(ROOT), "Installed CAR runtime must be outside checkout")
    originals = input_pins()
    checked_inputs(ROOT, args.expected)
    binaries = {"biocompiler-core": args.core_sha256, "biocompiler-verify": args.verify_sha256}
    require(all(component._sha(value) for value in binaries.values()), "External CAR native pins are required")
    paths = {role: getattr(args, role).absolute() for role in ("core", "verify")}
    measured = {role: pin(path, 256 * 1024 * 1024, executable=True) for role, path in paths.items()}
    require(all(measured[role]["sha256"] == binaries["biocompiler-" + role] for role in measured), "Installed CAR native bytes differ")
    spec = importlib.util.find_spec("biocompiler")
    require(spec is not None and spec.origin is not None, "Install the reviewed CAR SDK")
    package = Path(spec.origin).resolve().parent
    modules, data, record = installed_package(package)
    output = args.output.absolute()
    require(output.name == RECEIPT and not output.exists() and not output.is_relative_to(ROOT)
            and output.parent.is_dir() and not output.parent.is_symlink(), "Use a fresh installed CAR receipt outside checkout")
    artifacts = output.with_suffix("")
    artifacts.mkdir(exist_ok=False)
    cwd = Path.cwd().resolve()
    copied = cwd / "car-inputs"
    copied.mkdir(exist_ok=False)
    for name in COPY_INPUTS:
        target = copied / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
        require(pin(target) == originals[name], "CAR copied input changed")
    packet = checked_inputs(copied, copied / EXPECTED)
    result = {"schema_version": SCHEMA, "status": "incomplete", **hosted, "system": slot[0], "machine": slot[1],
        "python_version": platform.python_version(), "scope": SCOPE, "inputs": originals, "binary_sha256": binaries,
        "package": str(package), "installed_modules": modules, "installed_data": data, "sdk_record": record, "parent_imports": {},
        "source_snapshot_sha256": canonical_digest(before), "resolution": "owned_installed_defaults", "working_directory": str(cwd),
        "runtime_inputs": {name: {"path": str(copied / name), **originals[name]} for name in COPY_INPUTS},
        "observations": [], "observations_fingerprint": None, "projects": {}, "publications": [], "native_actions": {}, "files": {},
        "python_semantic_authority": "forbidden", "empirical": "unassessed", "human_use": "unassessed", "real_researcher_project_qualified": False}
    def save():
        raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(len(raw) <= component.MAX_RECEIPT, "CAR installed receipt exceeded its bound")
        output.write_bytes(raw)
    def retain(name, value):
        from biocompiler.core_client import encode_json
        index = len(result["observations"])
        require(index < len(car.OBSERVATIONS) and name == car.OBSERVATIONS[index], "Changed installed CAR observation order")
        path = artifacts / (name + ".json")
        with path.open("xb") as stream:
            stream.write(encode_json(value))
        result["observations"].append({"name": name, "path": str(path.relative_to(output.parent)), **pin(path)})
        save()
    def unchanged():
        require(source_identity() == hosted and source_snapshot(ROOT) == before and input_pins() == originals
                and installed_package(package) == (modules, data, record)
                and {role: pin(path, 256 * 1024 * 1024, executable=True) for role, path in paths.items()} == measured
                and all(pin(copied / name) == originals[name] for name in COPY_INPUTS), "CAR installed source/input/package/native authority changed")
    previous, boundary = sys.getprofile(), car.CarBoundary(package)
    try:
        boundary.origins()
        sys.meta_path.insert(0, boundary)
        sys.setprofile(boundary.trace)
        from biocompiler.core_client import CoreClient
        example = car.load_example(copied / EXAMPLE)
        transports = {role: CoreClient(path, role=role, expected_sha256=binaries["biocompiler-" + role], timeout_seconds=90) for role, path in paths.items()}
        fields = car.exercise(packet, example, transports["core"], transports["verify"], retain, artifacts, use_installed_defaults=True)
        action_row = next(row for row in result["observations"] if row["name"] == "native-actions")
        result.update(projects=fields["projects"], publications=fields["publications"],
                      native_actions={key: action_row[key] for key in ("path", "sha256", "bytes")})
        require(tuple(row["name"] for row in result["observations"]) == car.OBSERVATIONS, "Incomplete installed CAR observation census")
        result["parent_imports"] = boundary.origins()
        check_origins(result["parent_imports"], str(package), modules)
        observations = [{"name": row["name"], "result": read_json(output.parent / row["path"], component.MAX_EVIDENCE)} for row in result["observations"]]
        result["observations_fingerprint"] = canonical_digest(observations)
        result["files"] = {str(path.relative_to(output.parent)): pin(path) for path in sorted(artifacts.iterdir())}
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
                validate_installed(result, output.parent, args.expected, hosted, binaries, expected_sources=before, expected_slot=slot)
                unchanged()
                require(boundary.origins() == result["parent_imports"], "Installed CAR imports changed during validation")
        except Exception as error:
            result.update(status="failed", error=f"{type(error).__name__}: {error}")
            save()
            raise
        save()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("expected", "core", "verify", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("core-sha256", "verify-sha256"):
        parser.add_argument("--" + name, required=True)
    result = run(parser.parse_args())
    print(json.dumps({"schema_version": result["schema_version"], "status": result["status"]}, sort_keys=True))


if __name__ == "__main__":
    main()
