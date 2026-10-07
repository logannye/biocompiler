"""Hosted material-only prebuilt installation, owned routing and four-slot gate.

The wheel verifier is reused as a pure byte checker. Legacy migration campaigns
are never invoked. Native execution and installation occur only in hosted run
mode; unit tests use inert files and mocked process boundaries.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from copy import deepcopy
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import signal
import stat
import subprocess
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
# -I intentionally excludes both the checkout and the script directory. These
# are harness modules only: never add checkout/src or the repository root.
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
import build_prebuilt_core as build
import check_prebuilt_core_release as release_check
import check_policy_core as core
import check_policy_material_consumer as consumer
import prebuilt_release_pipeline as foundation

SCHEMA = "biocompiler.policy_material_prebuilt_campaign.v0.1"
PROBE_SCHEMA = "biocompiler.policy_material_prebuilt_probe.v0.1"
ARTIFACT_SCHEMA = "biocompiler.policy_material_prebuilt_artifact_identity.v0.1"
COMPONENT_SCHEMA = "biocompiler.policy_material_prebuilt_campaign.v0.2"
COMPONENT_PROBE_SCHEMA = "biocompiler.policy_material_prebuilt_probe.v0.2"
COMPONENT_CASES = ("component-profile-core", "component-profile-verify")
COMPONENT_EVIDENCE = ("component-material", "component-consumer", "component-resolver", "component-role", "component-controls")
COMPONENT_CLAIM = "supplied_prebuilt_material_and_component_profiles_only"
STAGED_SCHEMA = "biocompiler.policy_material_prebuilt_campaign.v0.3"
STAGED_CLAIM = "supplied_prebuilt_material_component_and_staged_profiles_only"
STAGED_EVIDENCE = ("staged-material",)
RESEARCHER_SCHEMA = "biocompiler.policy_material_prebuilt_campaign.v0.4"
RESEARCHER_CLAIM = "supplied_prebuilt_material_component_staged_and_researcher_project_profiles_only"
RESEARCHER_EVIDENCE = ("researcher-alpha",)
MAX_JSON = 64 * 1024 * 1024
MAX_LOG = 8 * 1024 * 1024
MAX_INSTALLED_RECORD = 2 * 1024 * 1024
CASES = ("wrong-version", "wrong-platform", "changed-binary", "changed-record", "changed-release", "mismatched-profile")
ERRORS = {
    "wrong-version": ("CoreUnavailable", "Prebuilt distribution and SDK release differ"),
    "wrong-platform": ("CoreUnavailable", "Installed native wheel tag differs from release policy"),
    "changed-binary": ("CoreUnavailable", "Owned file differs from wheel RECORD"),
    "changed-record": ("CoreUnavailable", "Owned file differs from wheel RECORD"),
    "changed-release": ("CoreUnavailable", "Native manifest differs from the SDK release pin"),
    "mismatched-profile": ("CoreProtocolError", "Selected executable lacks the exact material profile"),
    "missing": ("CoreUnavailable", "Install exactly one owned biocompiler-core distribution"),
}
EVIDENCE = ("ownership-before", "ownership-after", "missing", "resolver", "controls", "material", "consumer")
CANDIDATE_KEYS = {"schema_version", "status", "source_revision", "tested_revision", "run_id", "platforms", "distributions",
                  "material_companions", "release", "sdk_sources", "sdk", "native_execution", "acceptance"}

canonical = consumer.canonical
read_json = consumer.read_json
write_json = consumer.write_json


def same(left, right):
    return canonical(left) == canonical(right)


def bounded_bytes(path, maximum):
    require(path.is_file() and not path.is_symlink(), "Missing or redirected bounded input")
    with path.open("rb") as source:
        raw = source.read(maximum + 1)
    require(len(raw) <= maximum, "Bounded input grew beyond its allowance")
    return raw
require = build.require


def pin(path, maximum=release_check.MAX_ARCHIVE):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), "Missing or redirected retained file: " + str(path))
    digest, size = hashlib.sha256(), 0
    with path.open("rb") as stream:
        while chunk := stream.read(min(1024 * 1024, maximum + 1 - size)):
            size += len(chunk)
            require(size <= maximum, "Retained file exceeds bound")
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "size": size}


def hosted_identity():
    require(os.environ.get("GITHUB_ACTIONS") == "true", "Prebuilt installation is hosted-only")
    value = core.source_identity()
    require(value["run_id"].isdecimal() and int(value["run_id"]) > 0 and int(value["run_attempt"]) > 0,
            "A closed hosted run and attempt are required")
    return value


def source_pins():
    paths = set((ROOT / "tools").glob("*.py")) | set((ROOT / "tools").glob("*.sh"))
    paths |= set((ROOT / "tests").glob("test_policy_material*.py"))
    paths |= {ROOT / "tools/prebuilt-build-requirements.txt", ROOT / "protocol/core-release-sources-v1.json",
              ROOT / "protocol/policy-material-distribution-foundation-provenance-v1.json"}
    paths |= set((ROOT / "protocol/core-release-opam").glob("*.opam"))
    return {str(path.relative_to(ROOT)): pin(path, 4 * 1024 * 1024) for path in sorted(paths)}


def selected_target():
    matches = [name for name, values in build.TARGETS.items() if values[:2] == (platform.system(), platform.machine())]
    require(len(matches) == 1 and sys.version_info[:2] in ((3, 11), (3, 14)), "Unsupported prebuilt material slot")
    return matches[0]


def component_pairs(args, count):
    fixtures = getattr(args, "component_fixture", [])
    provenances = getattr(args, "component_provenance", [])
    require((not fixtures and not provenances) or len(fixtures) == len(provenances) == count,
            "Component mode requires one fixture/provenance pair per native platform")
    return list(zip(fixtures, provenances))


def staged_fixture(args, pairs):
    path = getattr(args, "staged_fixture", None)
    if path is not None:
        require(bool(pairs), "Staged mode requires the preserved component campaign")
        import check_policy_staged_material_installed as staged
        staged.staged.checked_fixture(ROOT, path)
    return path


def staged_argv(python, checkout, origin, ownership):
    import check_policy_staged_material_installed as staged
    files = ownership["files"]
    return [str(python), "-B", str(checkout / "tools/check_policy_staged_material_installed.py"),
            "--fixture", str(checkout / staged.staged.FIXTURE),
            "--core", files["bin/biocompiler-core"]["path"], "--core-sha256", files["bin/biocompiler-core"]["sha256"],
            "--verify", files["bin/biocompiler-verify"]["path"], "--verify-sha256", files["bin/biocompiler-verify"]["sha256"],
            "--output", str(origin / "evidence/staged-material.json")]


def staged_identity(receipt, identity, hashes, slot, ownership, sources):
    """Authenticate the child identity without importing SDK into the driver."""
    import check_policy_staged_material_installed as staged
    require(receipt["schema_version"] == staged.SCHEMA and receipt["status"] == "pass"
            and all(receipt[key] == identity[key] for key in identity) and consumer.slot(receipt) == slot
            and receipt["package"] == ownership["sdk_root"] and receipt["binary_sha256"] == hashes
            and receipt["inputs"] == staged.input_pins() and receipt["source_snapshot_sha256"] == core.canonical_digest(sources)
            and receipt["scope"] == staged.SCOPE and receipt["empirical"] == "unassessed"
            and receipt["python_semantic_authority"] == "forbidden", "Staged child changed its installed authority or scope")



def researcher_expected(args, staged_path):
    path = getattr(args, "researcher_expected", None)
    if path is not None:
        require(staged_path is not None, "Researcher mode requires all preserved staged and component campaigns")
        import check_researcher_alpha_installed as researcher
        researcher.checked_inputs(ROOT, path)
    return path


def researcher_argv(python, checkout, origin, ownership, expected):
    import check_researcher_alpha_installed as researcher
    require(Path(expected).resolve() == ROOT / researcher.EXPECTED, "Researcher expected authority must be the reviewed project packet")
    files = ownership["files"]
    return [str(python), "-B", str(checkout / "tools/check_researcher_alpha_installed.py"),
            "--expected", str(checkout / researcher.EXPECTED),
            "--core", files["bin/biocompiler-core"]["path"], "--core-sha256", files["bin/biocompiler-core"]["sha256"],
            "--verify", files["bin/biocompiler-verify"]["path"], "--verify-sha256", files["bin/biocompiler-verify"]["sha256"],
            "--output", str(origin / "evidence/researcher-alpha.json")]


def researcher_identity(receipt, identity, hashes, slot, ownership, sources):
    """Authenticate the project child without importing SDK into this driver."""
    import check_researcher_alpha_installed as researcher
    require(receipt["schema_version"] == researcher.SCHEMA and receipt["status"] == "pass"
            and all(receipt[key] == identity[key] for key in identity) and consumer.slot(receipt) == slot
            and receipt["package"] == ownership["sdk_root"] and receipt["binary_sha256"] == hashes
            and receipt["inputs"] == researcher.input_pins() and receipt["source_snapshot_sha256"] == core.canonical_digest(sources)
            and receipt["scope"] == researcher.SCOPE and receipt["empirical"] == "unassessed"
            and receipt["python_semantic_authority"] == "forbidden" and receipt["real_researcher_project_qualified"] is False
            and receipt["resolution"] == "owned_installed_defaults", "Researcher child changed installed authority or scope")


def component_authorities(pairs, identity, native_data):
    """Authenticate each independent emitter packet against supplied native bytes."""
    import check_policy_component_fixture as fixture_tool
    result = {}
    for fixture, provenance in pairs:
        value = read_json(provenance)
        platform_value = value.get("platform", {})
        key = (platform_value.get("system"), platform_value.get("machine"))
        targets = [name for name, row in build.TARGETS.items() if row[:2] == key and name in native_data]
        require(len(targets) == 1 and key not in result, "Duplicate or unexpected component fixture platform")
        native = native_data[targets[0]]
        hashes = {role: build.sha(native["entries"]["biocompiler_core/bin/biocompiler-" + role][0]) for role in ("core", "verify")}
        checked = fixture_tool.validate(ROOT, fixture, provenance, identity=identity, native_sha256=hashes, expected_platform=key)
        result[key] = {"fixture": fixture, "provenance": provenance, "sources": checked["sources"],
                       "pins": {"fixture": pin(fixture), "provenance": pin(provenance)}}
    require(set(result) == {build.TARGETS[name][:2] for name in native_data}, "Missing component fixture platform")
    require(len({row["pins"]["fixture"]["sha256"] for row in result.values()}) == 1,
            "Complete original component packets differ across platforms")
    return result


def component_argv(name, python, checkout, origin, ownership, fixture, provenance):
    files = ownership["files"]
    if name == "component-material":
        return [str(python), "-B", str(checkout / "tools/check_policy_component_material.py"), "--installed",
                "--fixture", str(fixture), "--fixture-provenance", str(provenance),
                "--core", files["bin/biocompiler-core"]["path"], "--core-sha256", files["bin/biocompiler-core"]["sha256"],
                "--verify", files["bin/biocompiler-verify"]["path"], "--verify-sha256", files["bin/biocompiler-verify"]["sha256"],
                "--output", str(origin / "evidence/component-material.json")]
    require(name == "component-consumer", "Unknown component campaign")
    return [str(python), "-B", str(checkout / "tools/check_policy_material_consumer.py"), "--profile", "component",
            "--fixture", str(fixture), "--fixture-provenance", str(provenance),
            "--producer-receipt", str(origin / "evidence/component-material.json"),
            "--verify", files["bin/biocompiler-verify"]["path"], "--core-sha256", files["bin/biocompiler-core"]["sha256"],
            "--network", "required", "--output", str(origin / "evidence/component-consumer.json")]


def component_inputs(receipt, evidence, authority, identity, hashes, slot):
    import check_policy_component_material as component
    return component.validate_installed(receipt, evidence, component.checked_fixture(ROOT, authority["fixture"]),
        authority["fixture"], identity, hashes, expected_sources=authority["sources"],
        fixture_provenance=authority["provenance"], expected_slot=slot)


def component_resolver_inputs(receipt, evidence, authority, identity, hashes, slot, package):
    """Retain complete original inputs without importing a product in the driver.

    The installed child validates the complete component result. The separate
    four-slot comparator repeats that validation and checks both actual ZIPs.
    This parent authenticates child sidecar bytes before independent resolver
    calls; an observed result never supplies the original request or limits.
    """
    import check_policy_component_material as component
    require(receipt["schema_version"] == component.INSTALLED_SCHEMA and receipt["status"] == "pass"
            and all(receipt[key] == identity[key] for key in identity) and consumer.slot(receipt) == slot
            and receipt["package"] == package and receipt["binary_sha256"] == hashes
            and receipt["fixture_sha256"] == authority["pins"]["fixture"]["sha256"]
            and receipt["fixture_provenance_sha256"] == authority["pins"]["provenance"]["sha256"]
            and receipt["source_snapshot_sha256"] == core.canonical_digest(authority["sources"])
            and receipt["python_semantic_authority"] == "forbidden", "Component resolver input receipt authority differs")
    rows = receipt["observations"]
    require(type(rows) is list and [(row.get("case"), row.get("name")) for row in rows] ==
            [(label, name) for label in ("A", "B") for name in component.CASE_NAMES], "Component resolver sidecar census differs")
    observations = []
    for row in rows:
        require(set(row) == {"case", "name", "path", "sha256", "bytes"}, "Component sidecar fields differ")
        path = component._retained(row["path"], evidence, {key: row[key] for key in ("sha256", "bytes")}, component.MAX_EVIDENCE)
        require(path.name == row["case"] + "-" + row["name"] + ".json", "Component sidecar name differs")
        observations.append({"case": row["case"], "name": row["name"], "result": read_json(path)})
    require(receipt["observations_fingerprint"] == core.canonical_digest(observations), "Complete component sidecar fingerprint differs")
    fixture = component.checked_fixture(ROOT, authority["fixture"])
    result = {}
    for case in fixture["cases"]:
        label = case["id"]; values = {row["name"]: row["result"] for row in observations if row["case"] == label}
        require(same(values["compile"], values["check-verify"]) and same(values["compile"], values["replay-verify"])
                and same(values["export-verify"]["candidate"], values["compile"]["candidate"])
                and same(values["export-verify"]["report"], values["compile"]["report"]), "Component resolver candidate or original assessment differs")
        result[label] = {"request": deepcopy(case["request"]), "limits": deepcopy(case["limits"]),
                         "candidate": values["check-verify"]["candidate"], "checked": values["check-verify"], "exported": values["export-verify"]}
    return result


def artifact_files(root, kind):
    if kind == "sdk":
        names = ["candidate.json", "biocompiler-" + build.VERSION + "-py3-none-any.whl"]
    else:
        packaging = read_json(root / "packaging-receipt.json")
        names = ["distribution.json", "packaging-receipt.json", "material-authority.json", "material-manifest.sha256",
                 packaging["wheel"]["name"], packaging["companion"]["filename"]]
    require(len(names) == len(set(names)) and all(Path(name).name == name for name in names), "Artifact basename inventory differs")
    return {name: pin(root / name) for name in sorted(names)}


def stamp_artifacts(root, kind, identity):
    """Fresh CI provenance sidecar; wheel/source verification remains mandatory."""
    value = {"schema_version": ARTIFACT_SCHEMA, "kind": kind, **identity, "files": artifact_files(root, kind)}
    output = root / "hosted-identity.json"
    require(not output.exists(), "Refusing to overwrite artifact attempt provenance")
    write_json(output, value)
    return value


def prior_attempt(value, identity):
    return (type(value) is dict and all(value.get(key) == identity[key] for key in ("revision", "head_revision", "run_id"))
            and type(value.get("run_attempt")) is str and re.fullmatch(r"[1-9][0-9]*", value["run_attempt"]) is not None
            and int(value["run_attempt"]) <= int(identity["run_attempt"]))


def check_stamp(root, kind, identity):
    value = read_json(root / "hosted-identity.json")
    require(prior_attempt(value, identity) and value == {"schema_version": ARTIFACT_SCHEMA, "kind": kind,
            **identity, "run_attempt": value["run_attempt"], "files": artifact_files(root, kind)},
            "Artifact bytes lack exact source/run and a current or prior successful attempt")
    return {"file": pin(root / "hosted-identity.json"), "producer_run_attempt": value["run_attempt"]}


def candidate_authority(candidate_path, sdk, identity):
    candidate = read_json(candidate_path)
    require(type(candidate) is dict and set(candidate) == CANDIDATE_KEYS and candidate["schema_version"] ==
            "biocompiler.prebuilt_candidate_validation.v1" and candidate["status"] == "pass"
            and candidate["native_execution"] is False and candidate["acceptance"] ==
            "staged bytes verified; installed four-runtime gates required", "Candidate validation receipt scope differs")
    expected = {"source_revision": identity["head_revision"], "tested_revision": identity["revision"], "run_id": identity["run_id"]}
    require(all(candidate[key] == value for key, value in expected.items()), "Candidate source/tested/run identity differs")
    require(set(candidate["distributions"]) == set(build.TARGETS) and set(candidate["platforms"]) == set(build.TARGETS)
            and set(candidate["material_companions"]) == set(build.TARGETS), "Candidate platform inventory differs")
    for target, document in candidate["distributions"].items():
        parsed = build.distribution(build.canonical(document))
        require(all(parsed[key] == value for key, value in {**expected, "native_platform": target}.items()),
                "Candidate platform manifest identity differs")
    release = build.release([build.canonical(candidate["distributions"][target]) for target in sorted(build.TARGETS)])
    require(candidate["release"] == release and candidate["sdk"] == pin(sdk), "Candidate SDK/release byte identity differs")
    source = release_check.source_package(ROOT)
    require(candidate["sdk_sources"] == {name: {"sha256": build.sha(raw), "size": len(raw)} for name, raw in source.items()},
            "Candidate package source inventory differs from current checkout")
    sdk_entries = release_check.read_wheel(sdk)
    release_check.validate_sdk(sdk_entries, source_files=source, release=release)
    require(sdk.name == "biocompiler-" + build.VERSION + "-py3-none-any.whl" and candidate_path.name == "candidate.json"
            and sdk.parent == candidate_path.parent, "SDK artifact paths differ")
    stamp = check_stamp(sdk.parent, "sdk", identity)
    return candidate, sdk_entries, stamp


def platform_authority(root, authority_path, candidate, identity, native=None):
    require(authority_path == root / "material-authority.json", "Only the independently supplied platform authority is supported")
    packaging = read_json(root / "packaging-receipt.json")
    target = packaging["distribution"]["native_platform"]
    require(target in build.TARGETS, "Unknown native platform")
    expected_name = "biocompiler_core-" + build.VERSION + "-" + build.TARGETS[target][2] + ".whl"
    path = root / expected_name
    require(native is None or native == path, "Supplied native wheel is outside its exact artifact slot")
    require(packaging["wheel"] == {"name": expected_name, **pin(path)}, "Supplied wheel differs from packaging receipt")
    authority = read_json(authority_path)
    raw = bounded_bytes(root / "material-manifest.sha256", 65).decode("ascii").strip()
    require(re.fullmatch(r"[0-9a-f]{64}", raw), "Material manifest pin is not a closed digest")
    entries = release_check.read_wheel(path)
    checked = release_check.validate_native(entries, expected={"source_revision": identity["head_revision"],
        "tested_revision": identity["revision"], "run_id": identity["run_id"], "native_platform": target},
        material_authority=authority, material_sha256=raw, packaging=packaging)
    release_check.verify_companion(root / checked["companion"]["filename"], checked)
    require(read_json(root / "distribution.json") == checked["distribution"]
            and candidate["distributions"][target] == checked["distribution"]
            and candidate["platforms"][target] == packaging["wheel"]
            and candidate["material_companions"][target] == checked["companion"], "Candidate differs from complete supplied native bytes")
    stamp = check_stamp(root, "native", identity)
    return {"target": target, "entries": entries, "distribution": checked["distribution"],
            "artifact_files": artifact_files(root, "native"), "stamp": stamp, "native": path}


def authority_receipt(candidate_path, sdk, sdk_stamp, platform_data):
    return {"candidate": pin(candidate_path), "sdk": {"name": sdk.name, **pin(sdk)}, "sdk_stamp": sdk_stamp,
            "native_platform": platform_data["target"], "native_files": platform_data["artifact_files"],
            "native_stamp": platform_data["stamp"]}


def safe_environment(*, probe=False):
    value = foundation.clean_environment(os.environ)
    for key in tuple(value):
        if key.startswith(("LD_", "DYLD_", "PYTHON")):
            value.pop(key)
    value["PYTHONNOUSERSITE"] = "1"
    value["PYTHONDONTWRITEBYTECODE"] = "1"
    if probe:
        value["PATH"] = ""
    return value


def command(output, name, argv, *, cwd, environment, timeout=1200):
    """Retain bounded full stdout/stderr even for timeouts and failed commands."""
    require(re.fullmatch(r"[a-z0-9-]+", name) and Path(argv[0]).is_absolute(), "Unclosed command identity")
    logs = output / "logs"
    logs.mkdir(exist_ok=True)
    buffers = [bytearray(), bytearray()]
    overflow = threading.Event()
    process = subprocess.Popen(argv, cwd=cwd, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True)
    def kill():
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    def drain(index):
        stream = process.stdout if index == 0 else process.stderr
        try:
            while chunk := stream.read(65536):
                remaining = MAX_LOG - len(buffers[index])
                buffers[index].extend(chunk[:remaining])
                if len(chunk) > remaining:
                    overflow.set(); kill(); break
        finally:
            stream.close()
    readers = [threading.Thread(target=drain, args=(index,), daemon=True) for index in (0, 1)]
    for reader in readers:
        reader.start()
    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True; kill(); process.wait(timeout=10)
    for reader in readers:
        reader.join(timeout=10)
    if any(reader.is_alive() for reader in readers):
        overflow.set(); kill()
    paths = [logs / (name + "." + suffix + ".log") for suffix in ("stdout", "stderr")]
    for path, content in zip(paths, buffers):
        require(not path.exists(), "Command evidence must not be overwritten")
        path.write_bytes(content)
    record = {"name": name, "argv": argv, "cwd": str(cwd), "executable": pin(Path(argv[0]).resolve()),
              "returncode": process.returncode, "timeout": timed_out, "overflow": overflow.is_set(),
              "environment": "empty_path_scrubbed_loaders" if environment.get("PATH") == "" else "scrubbed_loaders",
              "logs": {str(path.relative_to(output)): pin(path, MAX_LOG) for path in paths}}
    ledger_path = output / "commands.json"
    ledger = read_json(ledger_path) if ledger_path.exists() else []
    ledger.append(record); write_json(ledger_path, ledger)
    require(process.returncode == 0 and not timed_out and not overflow.is_set(), "Command failed; retained logs: " + name)
    return record


def snapshot_entries(root, entries):
    """Verify each original wheel-owned path, independently of import metadata."""
    result = {}
    for name, (raw, mode) in entries.items():
        if name.endswith(".dist-info/RECORD"):
            continue  # pip records generated scripts/bytecode; audit its records below.
        path = root / name
        require(not any(parent.is_symlink() for parent in (path, *path.parents) if parent.is_relative_to(root)),
                "Installed wheel path is redirected")
        require(pin(path, len(raw) + 1) == {"sha256": build.sha(raw), "size": len(raw)}
                and stat.S_IMODE(path.stat().st_mode) == mode, "Installed wheel-owned bytes or mode differ: " + name)
        result[name] = {"path": str(path), "sha256": build.sha(raw), "size": len(raw), "mode": mode}
    return result


def check_ownership(value, sdk_entries, native_data, candidate, environment):
    require(type(value) is dict and set(value) == {"schema_version", "status", "ownership", "inventory", "origins", "runtime", "environment"}
            and value["schema_version"] == PROBE_SCHEMA and value["status"] == "owned", "Incomplete ownership probe")
    ownership = value["ownership"]
    package = Path(ownership["package_root"]); sdk = Path(ownership["sdk_root"])
    require(package.name == "biocompiler_core" and sdk.name == "biocompiler" and package.parent == sdk.parent
            and package.is_relative_to(environment) and not package.is_relative_to(ROOT), "Resolver escaped fresh environment")
    manifest = native_data["distribution"]
    expected = {"schema_version": "biocompiler.installed_core_ownership.v1", "package_root": str(package), "sdk_root": str(sdk),
                **{key: manifest[key] for key in ("source_revision", "tested_revision", "run_id", "native_platform")},
                "release_sha256": build.sha(build.canonical(candidate["release"])),
                "distribution_sha256": build.sha(build.canonical(manifest)),
                "manifest_sha256": build.sha(native_data["entries"]["biocompiler_core/binaries.json"][0]),
                "files": {name: {"path": str(package / name), **row} for name, row in manifest["files"].items()},
                "sdk_files": {name: {"path": str(sdk / name), "sha256": build.sha(sdk_entries["biocompiler/" + name][0]),
                                     "size": len(sdk_entries["biocompiler/" + name][0])}
                              for name in ("__init__.py", "core_distribution.py", "core_client.py", "_core_release.json")}}
    require(same(ownership, expected), "Resolver ownership differs from original supplied wheel inventory")
    expected_inventory = {}
    for entries in (sdk_entries, native_data["entries"]):
        for name, (raw, mode) in entries.items():
            if not name.endswith(".dist-info/RECORD"):
                expected_inventory[name] = {"path": str(package.parent / name), "sha256": build.sha(raw), "size": len(raw), "mode": mode}
    require(same(value["inventory"], expected_inventory) and same(value["environment"],
            {"path": "", "loader_variables": [], "isolated": True, "dont_write_bytecode": True}),
            "Complete independently measured installed inventory or isolated resolver environment differs")
    require(value["origins"] == {name: str(sdk / path) for name, path in
            {"biocompiler": "__init__.py", "biocompiler.core_distribution": "core_distribution.py", "biocompiler.core_client": "core_client.py"}.items()},
            "Resolver imported a source or foreign package")


def installed_inventory():
    from importlib import metadata
    result = {}
    for distribution_name in ("biocompiler", "biocompiler-core"):
        distribution = metadata.distribution(distribution_name)
        for member in distribution.files or ():
            name = str(member)
            # Installer-generated metadata/scripts/bytecode are separately not
            # release source; all original wheel entries are checked by parent.
            if name.endswith((".pyc", ".dist-info/RECORD", ".dist-info/INSTALLER", ".dist-info/REQUESTED", ".dist-info/direct_url.json")) or ".." in Path(name).parts:
                continue
            path = Path(distribution.locate_file(member)).absolute()
            result[name] = {"path": str(path), **pin(path), "mode": stat.S_IMODE(path.stat().st_mode)}
    return result


def probe_environment():
    loader = [key for key in os.environ if key.startswith(("LD_", "DYLD_")) or key in ("PYTHONPATH", "PYTHONHOME", "OPAM_SWITCH_PREFIX", "CAML_LD_LIBRARY_PATH")]
    value = {"path": os.environ.get("PATH"), "loader_variables": sorted(loader),
             "isolated": bool(sys.flags.isolated), "dont_write_bytecode": bool(sys.flags.dont_write_bytecode)}
    require(value == {"path": "", "loader_variables": [], "isolated": True, "dont_write_bytecode": True}, "Probe environment is not isolated")
    require(not Path.cwd().resolve().is_relative_to(ROOT), "Probe working directory is in checkout")
    return value


def probe(args):
    env = probe_environment()
    from biocompiler.core_client import CoreUnavailable, CoreProtocolError
    from biocompiler.core_distribution import installed_distribution, installed_core
    if args.probe in ("component-resolver", "component-role", *COMPONENT_CASES):
        from biocompiler.core_policy_component_material import PolicyComponentMaterialClient
        inputs = read_json(args.inputs)
        require(type(inputs) is dict and set(inputs) == {"A", "B"}, "Complete component originals are required")
        results = {}
        for label in ("A", "B"):
            value = inputs[label]
            require(set(value) == {"request", "limits", "candidate", "checked", "exported"}, "Component original fields differ")
            roles = ("core", "verify") if args.probe == "component-resolver" else (
                "verify" if args.probe == "component-role" else args.probe.removeprefix("component-profile-"),)
            results[label] = {}
            for role in roles:
                client = PolicyComponentMaterialClient(installed_core(role=role, operation="check-policy-component-material", timeout_seconds=60))
                if args.probe == "component-resolver":
                    checked = client.check(value["request"], value["candidate"], value["limits"]).result
                    exported = client.export(value["request"], value["candidate"], value["limits"]).result
                    require(same(checked, value["checked"]) and same(exported, value["exported"]),
                            "Component resolver fresh check/export differs from supplied complete originals")
                    results[label][role] = {"checked": checked, "exported": exported}
                else:
                    message = ("Component production requires an explicitly selected Core producer" if args.probe == "component-role"
                               else "Selected executable lacks the exact component material profile")
                    try:
                        if args.probe == "component-role":
                            client.compile(value["request"], value["limits"])
                        else:
                            client.check(value["request"], value["candidate"], value["limits"])
                    except CoreProtocolError as error:
                        require(type(error).__name__ == "CoreProtocolError" and str(error) == message,
                                "Component control failed at an unrelated boundary")
                        results[label][role] = {"type": type(error).__name__, "message": str(error)}
                    else:
                        raise AssertionError("Component resolver control retained authority")
        result = {"schema_version": COMPONENT_PROBE_SCHEMA, "status": "pass" if args.probe == "component-resolver" else "rejected",
                  "case": args.probe, "environment": env, "ownership": installed_distribution().ownership(), "results": results}
        write_json(args.output, result)
        return
    if args.probe in ERRORS:
        try:
            if args.probe == "mismatched-profile":
                inputs = read_json(args.inputs)
                from biocompiler.core_policy_material import PolicyMaterialClient
                PolicyMaterialClient(installed_core(role="verify", operation="check-policy-material", timeout_seconds=60)).check(
                    inputs["request"], inputs["candidate"], inputs["limits"])
            else:
                installed_distribution()
        except (CoreUnavailable, CoreProtocolError) as error:
            expected_type, message = ERRORS[args.probe]
            require(type(error).__name__ == expected_type and str(error).startswith(message), "Installed mutation failed for an unrelated reason")
            result = {"schema_version": PROBE_SCHEMA, "status": "rejected", "case": args.probe,
                      "type": type(error).__name__, "message": str(error), "environment": env}
        else:
            raise AssertionError("Installed mutation retained authority: " + args.probe)
    elif args.probe == "ownership":
        owned = installed_distribution()
        result = {"schema_version": PROBE_SCHEMA, "status": "owned", "ownership": owned.ownership(), "inventory": installed_inventory(),
                  "origins": {name: str(Path(sys.modules[name].__file__).resolve()) for name in
                              ("biocompiler", "biocompiler.core_distribution", "biocompiler.core_client")},
                  "runtime": {"system": platform.system(), "machine": platform.machine(), "python_version": platform.python_version()},
                  "environment": env}
    else:
        require(args.probe == "resolver", "Unknown probe")
        inputs = read_json(args.inputs)
        from biocompiler.core_policy_material import PolicyMaterialClient
        results = {}
        for role in ("core", "verify"):
            client = PolicyMaterialClient(installed_core(role=role, operation="check-policy-material", timeout_seconds=60))
            checked = client.check(inputs["request"], inputs["candidate"], inputs["limits"]).result
            exported = client.export(inputs["request"], inputs["candidate"], inputs["limits"]).result
            require(canonical(checked) == canonical(inputs["checked"]) and canonical(exported) == canonical(inputs["exported"]),
                    "Installed resolver fresh check/export differs from separately supplied original expectation")
            results[role] = {"checked": checked, "exported": exported}
        result = {"schema_version": PROBE_SCHEMA, "status": "pass", "environment": env,
                  "ownership": installed_distribution().ownership(), "results": results}
    write_json(args.output, result)


def rewrite_record(record, relative, raw):
    rows = list(csv.reader(io.StringIO(record.read_text())))
    matches = [row for row in rows if row[0] == relative]
    require(len(matches) == 1, "Mutation RECORD target missing or duplicated")
    matches[0][1:] = ["sha256=" + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode(), str(len(raw))]
    stream = io.StringIO(newline=""); csv.writer(stream, lineterminator="\n").writerows(rows)
    record.write_text(stream.getvalue())


def mutation_files(case, ownership):
    package = Path(ownership["package_root"]); sdk = Path(ownership["sdk_root"])
    site = package.parent
    native_info = site / ("biocompiler_core-" + build.VERSION + ".dist-info")
    sdk_info = site / ("biocompiler-" + build.VERSION + ".dist-info")
    if case in COMPONENT_CASES:
        return [sdk / "core_policy_component_material.py", sdk_info / "RECORD"]
    return {
        "wrong-version": [native_info / "METADATA"], "wrong-platform": [native_info / "WHEEL"],
        "changed-binary": [package / "bin/biocompiler-verify"], "changed-record": [native_info / "RECORD"],
        "changed-release": [sdk / "_core_release.json", sdk_info / "RECORD"],
        "mismatched-profile": [sdk / "core_policy_material.py", sdk_info / "RECORD"],
    }[case]


@contextmanager
def installed_mutation(case, ownership):
    paths = mutation_files(case, ownership)
    originals = [(path, bounded_bytes(path, 256 * 1024 * 1024), path.stat()) for path in paths]
    try:
        path = paths[0]
        raw = originals[0][1]
        if case == "wrong-version":
            old = ("Version: " + build.VERSION + "\n").encode()
            require(raw.count(old) == 1, "Missing version mutation target")
            path.write_bytes(raw.replace(old, b"Version: 99.0.0\n"))
        elif case == "wrong-platform":
            old = ("Tag: " + build.TARGETS[ownership["native_platform"]][2]).encode()
            require(raw.count(old) == 1, "Missing platform mutation target")
            path.write_bytes(raw.replace(old, b"Tag: py3-none-any"))
        elif case == "changed-binary":
            path.write_bytes(raw + b"changed-installed-byte")
        elif case == "changed-record":
            rows = list(csv.reader(io.StringIO(raw.decode())))
            target = [row for row in rows if row[0] == "biocompiler_core/bin/biocompiler-verify"]
            require(len(target) == 1, "Missing binary RECORD mutation target")
            target[0][1] = "sha256=" + "A" * 43
            stream = io.StringIO(newline=""); csv.writer(stream, lineterminator="\n").writerows(rows)
            path.write_text(stream.getvalue())
        elif case == "changed-release":
            value = json.loads(raw); value["platforms"][ownership["native_platform"]] = "0" * 64
            path.write_bytes(build.canonical(value)); rewrite_record(paths[1], "biocompiler/_core_release.json", path.read_bytes())
        elif case in COMPONENT_CASES:
            old = b'VALIDATION_SCOPE = "policy-component-mrna-v0.1"'
            require(raw.count(old) == 1, "Missing component profile mutation target")
            path.write_bytes(raw.replace(old, b'VALIDATION_SCOPE = "foreign-component-profile"'))
            rewrite_record(paths[1], "biocompiler/core_policy_component_material.py", path.read_bytes())
        else:
            require(case == "mismatched-profile", "Unknown installed mutation")
            old = b'VALIDATION_SCOPE = "policy-truth-mrna-v0.1"'
            require(raw.count(old) == 1, "Missing material profile mutation target")
            path.write_bytes(raw.replace(old, b'VALIDATION_SCOPE = "foreign-material-profile"'))
            rewrite_record(paths[1], "biocompiler/core_policy_material.py", path.read_bytes())
        changes = [{"path": str(path), "before": {"sha256": build.sha(raw), "size": len(raw)}, "after": pin(path)}
                   for path, raw, _ in originals]
        require(all(row["before"] != row["after"] for row in changes), "Installed mutation did not change each selected input")
        yield changes
    finally:
        for path, raw, info in originals:
            path.write_bytes(raw); path.chmod(stat.S_IMODE(info.st_mode)); os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
            require(pin(path) == {"sha256": build.sha(raw), "size": len(raw)}, "Installed mutation restoration failed")


def run(args):
    identity = hosted_identity(); target = selected_target()
    pairs = component_pairs(args, 1)
    staged_path = staged_fixture(args, pairs)
    researcher_path = researcher_expected(args, staged_path)
    require(len(args.platform_root) == len(args.material_authority) == 1, "Run requires one supplied platform artifact slot")
    candidate, sdk_entries, sdk_stamp = candidate_authority(args.release_candidate, args.sdk, identity)
    native = platform_authority(args.platform_root[0], args.material_authority[0], candidate, identity, args.native)
    require(native["target"] == target, "Supplied wheel does not match this hosted runtime")
    authorities = component_authorities(pairs, identity, {target: native}) if pairs else None
    component_authority = authorities[(platform.system(), platform.machine())] if authorities else None
    output = args.output_dir.resolve()
    require(not output.exists() and not output.is_relative_to(ROOT), "Fresh output environment must be outside checkout")
    output.mkdir(parents=True); (output / "evidence").mkdir(); (output / "cwd").mkdir()
    environment = output / "env"; python = environment / "bin/python"; driver = Path(sys.executable).absolute()
    base_env = safe_environment(); probe_env = safe_environment(probe=True)
    cwd = output / "cwd"; evidence = output / "evidence"
    def launch(name, argv, *, probe_mode=False):
        return command(output, name, argv, cwd=cwd, environment=probe_env if probe_mode else base_env)
    def invoke_probe(name, mode, inputs=None):
        path = evidence / (name + ".json")
        argv = [str(python), "-I", "-B", str(Path(__file__).resolve()), "--probe", mode, "--output", str(path)]
        if inputs:
            argv += ["--inputs", str(inputs)]
        launch(name, argv, probe_mode=True)
        return read_json(path)
    launch("create-environment", [str(driver), "-m", "venv", "--without-pip", str(environment)])
    launch("install", foundation.install_plan(driver, python, args.sdk, args.native))
    before = invoke_probe("ownership-before", "ownership")
    check_ownership(before, sdk_entries, native, candidate, environment)
    # Directly compare actual installed bytes in the driver too, before any
    # resolver-mediated native launch. Resolver self-reports cannot supply pins.
    site = Path(before["ownership"]["package_root"]).parent
    snapshot_entries(site, sdk_entries); snapshot_entries(site, native["entries"])
    ownership = before["ownership"]
    binaries = {role: ownership["files"]["bin/biocompiler-" + role]["path"] for role in ("core", "verify")}
    launch("material", [str(python), "-B", str(ROOT / "tools/check_policy_material.py"), "--core", binaries["core"],
                        "--verify", binaries["verify"], "--console", str(environment / "bin/biocompiler"),
                        "--fixture", str(args.fixture), "--output", str(evidence / "material.json")])
    material = read_json(evidence / "material.json")
    require(material["run_attempt"] == identity["run_attempt"], "Material receipt attempt differs")
    original = read_json(args.fixture)
    outputs = {row["name"]: row["result"] for row in material["observations"]}
    inputs = {"request": original["request"], "limits": original["limits"],
              "candidate": outputs["check-verify"]["candidate"], "checked": outputs["check-verify"],
              "exported": outputs["export-verify"]}
    inputs_path = cwd / "original-inputs.json"; write_json(inputs_path, inputs)
    resolver = invoke_probe("resolver", "resolver", inputs_path)
    require(resolver["ownership"] == ownership, "Fresh resolver changed its owned release")
    controls = []
    for case in CASES:
        with installed_mutation(case, ownership) as changes:
            rejected = invoke_probe(case, case, inputs_path if case == "mismatched-profile" else None)
        restored = invoke_probe(case + "-restored", "ownership")
        require(same(restored, before), "Installed mutation was not fully restored")
        controls.append({"case": case, "changes": changes, "rejection": rejected, "restored": consumer.digest(restored)})
    write_json(evidence / "controls.json", controls)
    launch("consumer", [str(python), "-B", str(ROOT / "tools/check_policy_material_consumer.py"), "--verify", binaries["verify"],
                        "--fixture", str(args.fixture), "--producer-receipt", str(evidence / "material.json"),
                        "--network", "required", "--output", str(evidence / "consumer.json")])
    if component_authority:
        component_fixture = component_authority["fixture"]; provenance = component_authority["provenance"]
        launch("component-material", component_argv("component-material", python, ROOT, output, ownership, component_fixture, provenance))
        hashes = {"biocompiler-" + role: ownership["files"]["bin/biocompiler-" + role]["sha256"] for role in ("core", "verify")}
        original_inputs = component_resolver_inputs(read_json(evidence / "component-material.json"), evidence, component_authority,
            identity, hashes, (platform.system(), platform.machine(), f"{sys.version_info.major}.{sys.version_info.minor}"), ownership["sdk_root"])
        component_path = cwd / "component-original-inputs.json"; write_json(component_path, original_inputs)
        for name in ("component-resolver", "component-role"):
            value = invoke_probe(name, name, component_path)
            check_component_probe(value, name, original_inputs, before)
        component_controls = []
        for case in COMPONENT_CASES:
            record_path = mutation_files(case, ownership)[1]
            installed_record = bounded_bytes(record_path, MAX_INSTALLED_RECORD).decode("utf-8")
            with installed_mutation(case, ownership) as changes:
                rejected = invoke_probe(case, case, component_path)
                check_component_probe(rejected, case, original_inputs, before)
            restored = invoke_probe(case + "-restored", "ownership")
            require(same(restored, before), "Component profile mutation was not fully restored")
            component_controls.append({"case": case, "changes": changes, "rejection": rejected,
                "restored": consumer.digest(restored), "installed_record": {
                    "before": installed_record, "restored": pin(record_path, MAX_INSTALLED_RECORD)}})
        write_json(evidence / "component-controls.json", component_controls)
        launch("component-consumer", component_argv("component-consumer", python, ROOT, output, ownership, component_fixture, provenance))
    if staged_path is not None:
        launch("staged-material", staged_argv(python, ROOT, output, ownership))
        staged_identity(read_json(evidence / "staged-material.json"), identity,
                        {"biocompiler-" + role: ownership["files"]["bin/biocompiler-" + role]["sha256"] for role in ("core", "verify")},
                        (platform.system(), platform.machine(), ".".join(platform.python_version().split(".")[:2])),
                        ownership, component_authority["sources"])
    if researcher_path is not None:
        launch("researcher-alpha", researcher_argv(python, ROOT, output, ownership, researcher_path))
        researcher_identity(read_json(evidence / "researcher-alpha.json"), identity,
                            {"biocompiler-" + role: ownership["files"]["bin/biocompiler-" + role]["sha256"] for role in ("core", "verify")},
                            (platform.system(), platform.machine(), ".".join(platform.python_version().split(".")[:2])),
                            ownership, component_authority["sources"])
    launch("uninstall", [str(driver), "-m", "pip", "--python", str(python), "uninstall", "--yes", "biocompiler-core"])
    invoke_probe("missing", "missing")
    launch("reinstall", foundation.install_plan(driver, python, args.sdk, args.native))
    after = invoke_probe("ownership-after", "ownership")
    require(same(before, after), "Uninstall/reinstall changed complete owned wheel bytes or identity")
    snapshot_entries(site, sdk_entries); snapshot_entries(site, native["entries"])
    result = {"schema_version": SCHEMA, "status": "pass", **identity, "system": platform.system(), "machine": platform.machine(),
              "python_version": platform.python_version(), "output_root": str(output), "checkout_root": str(ROOT), "fixture": pin(args.fixture),
              "source_pins": source_pins(), "artifacts": authority_receipt(args.release_candidate, args.sdk, sdk_stamp, native),
              "evidence": {"evidence/" + name + ".json": pin(evidence / (name + ".json"), MAX_JSON) for name in EVIDENCE},
              "commands": pin(output / "commands.json", MAX_JSON), "cases": list(CASES),
              "claim": "supplied_prebuilt_material_profile_only", "python_semantic_authority": "forbidden",
              "network": "consumer_required_os_denial", "default_cutover": "unassessed"}
    if component_authority:
        result.update(schema_version=COMPONENT_SCHEMA, claim=COMPONENT_CLAIM, component_originals=component_authority["pins"],
                      component_cases=list(COMPONENT_CASES))
        result["evidence"].update({"evidence/" + name + ".json": pin(evidence / (name + ".json"), MAX_JSON) for name in COMPONENT_EVIDENCE})
    if staged_path is not None:
        import check_policy_staged_material_installed as staged
        result.update(schema_version=STAGED_SCHEMA, claim=STAGED_CLAIM, staged_originals=staged.input_pins())
        result["evidence"].update({"evidence/" + name + ".json": pin(evidence / (name + ".json"), MAX_JSON) for name in STAGED_EVIDENCE})
    if researcher_path is not None:
        import check_researcher_alpha_installed as researcher
        result.update(schema_version=RESEARCHER_SCHEMA, claim=RESEARCHER_CLAIM, researcher_originals=researcher.input_pins())
        result["evidence"].update({"evidence/" + name + ".json": pin(evidence / (name + ".json"), MAX_JSON) for name in RESEARCHER_EVIDENCE})
    write_json(output / "prebuilt.json", result)
    return result


def check_rejection(value, case):
    kind, message = ERRORS[case]
    require(type(value) is dict and set(value) == {"schema_version", "status", "case", "type", "message", "environment"}
            and value["schema_version"] == PROBE_SCHEMA and value["status"] == "rejected" and value["case"] == case
            and value["type"] == kind and value["message"].startswith(message) and value["environment"] ==
            {"path": "", "loader_variables": [], "isolated": True, "dont_write_bytecode": True}, "Mutation rejection differs")


def check_component_probe(value, case, inputs, before):
    require(case in ("component-resolver", "component-role", *COMPONENT_CASES), "Unexpected component probe")
    require(type(value) is dict and set(value) == {"schema_version", "status", "case", "environment", "ownership", "results"}
            and value["schema_version"] == COMPONENT_PROBE_SCHEMA and value["case"] == case
            and value["status"] == ("pass" if case == "component-resolver" else "rejected")
            and same(value["ownership"], before["ownership"]) and same(value["environment"], before["environment"]),
            "Component resolver identity, isolation or status differs")
    if case == "component-resolver":
        expected = {label: {role: {key: inputs[label][key] for key in ("checked", "exported")} for role in ("core", "verify")}
                    for label in ("A", "B")}
    else:
        role = "verify" if case == "component-role" else case.removeprefix("component-profile-")
        message = ("Component production requires an explicitly selected Core producer" if case == "component-role"
                   else "Selected executable lacks the exact component material profile")
        expected = {label: {role: {"type": "CoreProtocolError", "message": message}} for label in ("A", "B")}
    require(same(value["results"], expected), "Complete component resolver outputs or exact rejection boundaries differ")


def component_installed_record(text, record_name, sdk_entries, python_version):
    """Preserve wheel-owned rows and narrowly classify pip's additional rows.

    Installed RECORD is not a wheel member's original byte string: pip adds
    installer metadata, its console wrapper and bytecode, and may use CRLF.
    These extra rows never provide release-source authority. All original
    wheel-owned rows still require their independently supplied exact bytes.
    """
    require(type(text) is str and 0 < len(text.encode("utf-8")) <= MAX_INSTALLED_RECORD,
            "Missing or oversized installed component RECORD authority")
    require(type(python_version) is str and re.fullmatch(r"3\.(11|14)\.[0-9]+", python_version),
            "Unexpected installed RECORD runtime")
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as error:
        raise ValueError("Malformed installed component RECORD") from error
    require(0 < len(rows) <= 2 * len(sdk_entries) + 4 and all(len(row) == 3 for row in rows),
            "Installed component RECORD row census differs")
    names = [row[0] for row in rows]
    require(len(set(names)) == len(names) and all(0 < len(name) <= 1024 and
            not any(ord(char) < 32 or ord(char) == 127 for char in name) for name in names),
            "Duplicate or malformed installed component RECORD path")
    expected = {name: [name, "sha256=" + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b"=").decode(), str(len(raw))]
                for name, (raw, _) in sdk_entries.items() if name != record_name}
    require(record_name in sdk_entries and record_name.endswith(".dist-info/RECORD"),
            "Original component wheel RECORD authority is missing")
    expected[record_name] = [record_name, "", ""]
    actual = {row[0]: row for row in rows}
    require(set(expected) <= set(actual) and all(actual[name] == row for name, row in expected.items()),
            "Installed component RECORD lost exact original wheel rows")
    tag = "cpython-" + "".join(python_version.split(".")[:2])
    bytecode = {str(Path(name).parent / "__pycache__" / (Path(name).stem + "." + tag + ".pyc"))
                for name in sdk_entries if name.startswith("biocompiler/") and name.endswith(".py")}
    metadata = record_name.removesuffix("RECORD")
    additions = {metadata + name for name in ("INSTALLER", "REQUESTED", "direct_url.json")}
    entry_points = sdk_entries.get(metadata + "entry_points.txt")
    if entry_points is not None and entry_points[0] == b"[console_scripts]\nbiocompiler = biocompiler.entrypoint:main\n":
        additions.add("../../../bin/biocompiler")
    for name in set(actual) - set(expected):
        row = actual[name]
        if name in bytecode:
            require(row[1:] == ["", ""], "Installer bytecode cannot claim wheel-source authority")
        else:
            require(name in additions and re.fullmatch(r"sha256=[A-Za-z0-9_-]{43}", row[1])
                    and re.fullmatch(r"0|[1-9][0-9]{0,6}", row[2]) and int(row[2]) <= MAX_INSTALLED_RECORD,
                    "Unreviewed installed component RECORD addition")
            encoded = row[1].removeprefix("sha256=")
            require(base64.urlsafe_b64encode(base64.urlsafe_b64decode(encoded + "=")).rstrip(b"=").decode() == encoded,
                    "Noncanonical installed RECORD digest")
    return rows


def check_component_controls(directory, data, inputs, sdk_entries):
    before = data["ownership-before"]; ownership = before["ownership"]
    for name in ("component-resolver", "component-role"):
        check_component_probe(data[name], name, inputs, before)
    controls = data["component-controls"]
    require(type(controls) is list and [x.get("case") for x in controls] == list(COMPONENT_CASES), "Component mutation census differs")
    installed_original = None
    for row in controls:
        case = row["case"]
        require(set(row) == {"case", "changes", "rejection", "restored", "installed_record"} and row["restored"] == consumer.digest(before),
                "Component mutation restoration differs")
        check_component_probe(row["rejection"], case, inputs, before)
        require(same(read_json(directory / "evidence" / (case + ".json")), row["rejection"])
                and same(read_json(directory / "evidence" / (case + "-restored.json")), before), "Component control sidecars differ")
        paths = mutation_files(case, ownership)
        require(type(row["changes"]) is list and len(row["changes"]) == len(paths), "Component mutation file census differs")
        module_name = "biocompiler/core_policy_component_material.py"
        module_original = sdk_entries[module_name][0]
        marker = b'VALIDATION_SCOPE = "policy-component-mrna-v0.1"'
        require(module_original.count(marker) == 1, "Original component profile authority changed")
        module_changed = module_original.replace(marker, b'VALIDATION_SCOPE = "foreign-component-profile"')
        record_name = str(paths[1].relative_to(Path(ownership["sdk_root"]).parent))
        record = row["installed_record"]
        require(type(record) is dict and set(record) == {"before", "restored"}, "Incomplete installed component RECORD evidence")
        record_rows = component_installed_record(record["before"], record_name, sdk_entries, before["runtime"]["python_version"])
        record_original = record["before"].encode("utf-8")
        require(installed_original is None or installed_original == record_original,
                "Component controls did not restore the same installed RECORD")
        installed_original = record_original
        require(same(record["restored"], {"sha256": build.sha(record_original), "size": len(record_original)}),
                "Installed component RECORD restoration differs")
        selected = [entry for entry in record_rows if entry[0] == module_name]
        require(len(selected) == 1, "Original component wheel RECORD census changed")
        selected[0][1:] = ["sha256=" + base64.urlsafe_b64encode(hashlib.sha256(module_changed).digest()).rstrip(b"=").decode(), str(len(module_changed))]
        record_buffer = io.StringIO(newline=""); csv.writer(record_buffer, lineterminator="\n").writerows(record_rows)
        expected_after = {module_name: module_changed, record_name: record_buffer.getvalue().encode()}
        for change, path in zip(row["changes"], paths):
            relative = str(path.relative_to(Path(ownership["sdk_root"]).parent))
            original = record_original if relative == record_name else sdk_entries[relative][0]
            require(set(change) == {"path", "before", "after"} and change["path"] == str(path)
                    and change["before"] == {"sha256": build.sha(original), "size": len(original)}
                    and same(change["after"], {"sha256": build.sha(expected_after[relative]), "size": len(expected_after[relative])})
                    and change["after"] != change["before"], "Component mutation lost supplied original wheel-byte authority")


def verify_slot(directory, identity, candidate_path, sdk, sdk_entries, sdk_stamp, native_data, fixture, component_authority=None, *, staged_path=None, researcher_path=None):
    value = read_json(directory / "prebuilt.json")
    required = {"schema_version", "status", *identity, "system", "machine", "python_version", "output_root", "checkout_root", "fixture", "source_pins",
                "artifacts", "evidence", "commands", "cases", "claim", "python_semantic_authority", "network", "default_cutover"}
    if component_authority is not None:
        required |= {"component_originals", "component_cases"}
    require(staged_path is None or component_authority is not None, "Staged slot requires component authority")
    if staged_path is not None:
        required |= {"staged_originals"}
    require(researcher_path is None or staged_path is not None, "Researcher slot requires preserved staged authority")
    if researcher_path is not None:
        required |= {"researcher_originals"}
    schema = RESEARCHER_SCHEMA if researcher_path is not None else STAGED_SCHEMA if staged_path is not None else COMPONENT_SCHEMA if component_authority is not None else SCHEMA
    claim = RESEARCHER_CLAIM if researcher_path is not None else STAGED_CLAIM if staged_path is not None else COMPONENT_CLAIM if component_authority is not None else "supplied_prebuilt_material_profile_only"
    require(type(value) is dict and set(value) == required and value["schema_version"] == schema and value["status"] == "pass"
            and prior_attempt(value, identity), "Stale, failed or incomplete prebuilt slot")
    slot = consumer.slot(value)
    require(slot in {(row[0], row[1], minor) for row in build.TARGETS.values() for minor in ("3.11", "3.14")}, "Unexpected runtime slot")
    target = next(name for name, row in build.TARGETS.items() if row[:2] == slot[:2]); native = native_data[target]
    require(same(value["artifacts"], authority_receipt(candidate_path, sdk, sdk_stamp, native)) and same(value["source_pins"], source_pins())
            and same(value["fixture"], pin(fixture)) and value["cases"] == list(CASES)
            and value["claim"] == claim and value["python_semantic_authority"] == "forbidden"
            and value["network"] == "consumer_required_os_denial" and value["default_cutover"] == "unassessed", "Prebuilt slot authority or scope differs")
    evidence_names = EVIDENCE + (COMPONENT_EVIDENCE if component_authority is not None else ()) + (STAGED_EVIDENCE if staged_path is not None else ()) + (RESEARCHER_EVIDENCE if researcher_path is not None else ())
    expected_evidence = {"evidence/" + name + ".json" for name in evidence_names}
    require(set(value["evidence"]) == expected_evidence and all(same(pin(directory / name, MAX_JSON), row) for name, row in value["evidence"].items())
            and same(value["commands"], pin(directory / "commands.json", MAX_JSON)), "Complete retained slot evidence differs")
    data = {name: read_json(directory / "evidence" / (name + ".json")) for name in evidence_names}
    origin = Path(value["output_root"])
    require(origin.is_absolute() and not origin.is_relative_to(ROOT), "Original run was not outside checkout")
    candidate = read_json(candidate_path)
    check_ownership(data["ownership-before"], sdk_entries, native, candidate, origin / "env")
    require(same(data["ownership-before"], data["ownership-after"]) and data["ownership-before"]["runtime"] ==
            {key: value[key] for key in ("system", "machine", "python_version")}, "Ownership lifecycle or runtime identity differs")
    check_rejection(data["missing"], "missing")
    controls = data["controls"]
    require(type(controls) is list and [row.get("case") for row in controls] == list(CASES), "Installed mutation census differs")
    for row in controls:
        require(set(row) == {"case", "changes", "rejection", "restored"} and row["restored"] == consumer.digest(data["ownership-before"]), "Mutation restoration identity differs")
        check_rejection(row["rejection"], row["case"])
        require(same(read_json(directory / "evidence" / (row["case"] + ".json")), row["rejection"])
                and same(read_json(directory / "evidence" / (row["case"] + "-restored.json")), data["ownership-before"]),
                "Original installed control/restoration output differs from retained receipt")
        paths = mutation_files(row["case"], data["ownership-before"]["ownership"])
        require([entry["path"] for entry in row["changes"]] == [str(path) for path in paths]
                and all(set(entry) == {"path", "before", "after"} and entry["before"] != entry["after"]
                        and all(type(pin_value) is dict and set(pin_value) == {"sha256", "size"}
                            and re.fullmatch(r"[0-9a-f]{64}", pin_value["sha256"]) and type(pin_value["size"]) is int and pin_value["size"] > 0
                            for pin_value in (entry["before"], entry["after"])) for entry in row["changes"]), "Installed mutation byte evidence differs")
    ownership = data["ownership-before"]["ownership"]
    material = data["material"]; offline = data["consumer"]
    require(all(row["run_attempt"] == value["run_attempt"] for row in (material, offline))
            and material["package"] == ownership["sdk_root"] and offline["installed_package"] == ownership["sdk_root"],
            "Delegated campaign did not use the same current-attempt owned SDK")
    expected_binary = {"biocompiler-" + role: ownership["files"]["bin/biocompiler-" + role]["sha256"] for role in ("core", "verify")}
    require(material["binary_sha256"] == expected_binary and offline["verify_sha256"] == expected_binary["biocompiler-verify"],
            "Delegated campaign did not use supplied final wheel executables")
    from check_policy_material import checked_fixture
    inputs = consumer.validate_producer(material, checked_fixture(fixture), fixture, identity, expected_binary["biocompiler-verify"], expected_slot=slot)
    resolver = data["resolver"]
    require(set(resolver) == {"schema_version", "status", "environment", "ownership", "results"}
            and resolver["schema_version"] == PROBE_SCHEMA and resolver["status"] == "pass"
            and resolver["ownership"] == ownership and resolver["environment"] == data["ownership-before"]["environment"]
            and canonical(resolver["results"]) == canonical({role: {"checked": inputs["checked"], "exported": inputs["exported"]}
                                                           for role in ("core", "verify")}), "Fresh installed resolver results differ")
    if component_authority is not None:
        authority = component_authority[slot[:2]]
        require(same(value["component_originals"], authority["pins"]) and value["component_cases"] == list(COMPONENT_CASES),
                "Component original authority or mandatory controls differ")
        producer = data["component-material"]; offline_component = data["component-consumer"]
        require(all(row["run_attempt"] == value["run_attempt"] and row["python_version"] == value["python_version"]
                    for row in (producer, offline_component))
                and producer["package"] == ownership["sdk_root"] and offline_component["installed_package"] == ownership["sdk_root"]
                and offline_component["core_sha256"] == expected_binary["biocompiler-core"]
                and offline_component["verify_sha256"] == expected_binary["biocompiler-verify"],
                "Component campaign did not use the same current-attempt owned SDK and supplied executables")
        component_values = component_inputs(producer, directory / "evidence", authority, identity, expected_binary, slot)
        check_component_controls(directory, data, component_values, sdk_entries)
    if staged_path is not None:
        import check_policy_staged_material_installed as staged
        require(same(value["staged_originals"], staged.input_pins()), "Staged original authority differs")
        producer = data["staged-material"]
        staged_identity(producer, {**identity, "run_attempt": value["run_attempt"]}, expected_binary, slot, ownership, authority["sources"])
        require(producer["python_version"] == value["python_version"], "Staged child runtime differs")
        staged.validate_installed(producer, directory / "evidence", staged_path, identity, expected_binary,
                                  expected_sources=authority["sources"], expected_slot=slot)
    if researcher_path is not None:
        import check_researcher_alpha_installed as researcher
        require(same(value["researcher_originals"], researcher.input_pins()), "Researcher original authority differs")
        producer = data["researcher-alpha"]
        researcher_identity(producer, {**identity, "run_attempt": value["run_attempt"]}, expected_binary, slot, ownership, authority["sources"])
        require(producer["python_version"] == value["python_version"], "Researcher child runtime differs")
        researcher.validate_installed(producer, directory / "evidence", researcher_path, identity, expected_binary,
                                      expected_sources=authority["sources"], expected_slot=slot)
    check_commands(directory, read_json(directory / "commands.json"), origin, ownership, fixture, value,
                   component_authority=component_authority[slot[:2]] if component_authority is not None else None, staged_path=staged_path, researcher_path=researcher_path)
    return slot, data


def check_commands(directory, rows, origin, ownership, fixture, receipt, *, component_authority=None, staged_path=None, researcher_path=None):
    names = ["create-environment", "install", "ownership-before", "material", "resolver"]
    for case in CASES:
        names.extend((case, case + "-restored"))
    names += ["consumer"]
    if component_authority is not None:
        names += ["component-material", "component-resolver", "component-role"]
        for case in COMPONENT_CASES:
            names.extend((case, case + "-restored"))
        names += ["component-consumer"]
    if staged_path is not None:
        require(component_authority is not None, "Staged commands require component authority")
        names += ["staged-material"]
    if researcher_path is not None:
        require(staged_path is not None, "Researcher commands require all preserved staged commands")
        names += ["researcher-alpha"]
    names += ["uninstall", "missing", "reinstall", "ownership-after"]
    require(type(rows) is list and [row.get("name") for row in rows] == names, "Full installation/ownership command ledger differs")
    checkout = Path(receipt["checkout_root"])
    require(checkout.is_absolute() and not origin.is_relative_to(checkout), "Installed cwd overlaps original checkout")
    python = str(origin / "env/bin/python")
    driver = rows[0]["argv"][0]
    require(Path(driver).is_absolute(), "Driver interpreter is not absolute")
    interpreter_pins = {}
    for row in rows:
        require(set(row) == {"name", "argv", "cwd", "executable", "returncode", "timeout", "overflow", "environment", "logs"}
                and row["returncode"] == 0 and type(row["returncode"]) is int and row["timeout"] is False and row["overflow"] is False
                and row["cwd"] == str(origin / "cwd") and Path(row["argv"][0]).is_absolute(), "Failed or incomplete retained command")
        require(set(row["logs"]) == {"logs/" + row["name"] + "." + suffix + ".log" for suffix in ("stdout", "stderr")}
                and all(pin(directory / name, MAX_LOG) == item for name, item in row["logs"].items()), "Retained command logs differ")
        require(type(row["executable"]) is dict and set(row["executable"]) == {"sha256", "size"}
                and re.fullmatch(r"[0-9a-f]{64}", row["executable"]["sha256"]) and type(row["executable"]["size"]) is int
                and row["executable"]["size"] > 0, "Command interpreter pin differs")
        interpreter = row["argv"][0]
        require(interpreter not in interpreter_pins or same(interpreter_pins[interpreter], row["executable"]),
                "Interpreter changed during installed campaign")
        interpreter_pins[interpreter] = row["executable"]
        name = row["name"]; argv = row["argv"]
        if name == "create-environment":
            require(argv == [driver, "-m", "venv", "--without-pip", str(origin / "env")], "Environment creation route differs")
        elif name in ("install", "reinstall"):
            require(len(argv) == 11 and argv[:9] == [driver, "-m", "pip", "--python", python, "install", "--no-index", "--no-deps", "--only-binary=:all:"] and Path(argv[9]).name == receipt["artifacts"]["sdk"]["name"]
                    and Path(argv[10]).name == next(name for name in receipt["artifacts"]["native_files"] if name.endswith(".whl"))
                    and all(Path(path).is_absolute() for path in argv[9:]), "Installation allowed a source or unsupplied wheel route")
        elif name == "uninstall":
            require(argv == [driver, "-m", "pip", "--python", python, "uninstall", "--yes", "biocompiler-core"], "Uninstall route differs")
        elif name == "researcher-alpha":
            require(argv == researcher_argv(python, checkout, origin, ownership, researcher_path) and row["environment"] == "scrubbed_loaders",
                    "Researcher campaign exact command or isolation differs")
        elif name == "staged-material":
            require(argv == staged_argv(python, checkout, origin, ownership) and row["environment"] == "scrubbed_loaders",
                    "Staged campaign exact command or isolation differs")
        elif name in ("component-material", "component-consumer"):
            expected = component_argv(name, python, checkout, origin, ownership,
                                      component_authority["fixture"], component_authority["provenance"])
            for flag in ("--fixture", "--fixture-provenance"):
                index = expected.index(flag) + 1
                require(len(argv) > index and Path(argv[index]).is_absolute(), "Component original path must be absolute")
                expected[index] = argv[index]
            require(argv == expected and row["environment"] == "scrubbed_loaders", "Component campaign exact command or mandatory isolation differs")
        elif name in ("material", "consumer"):
            tool = "check_policy_material" + ("_consumer" if name == "consumer" else "") + ".py"
            require(argv[:3] == [python, "-B", str(checkout / "tools" / tool)], "Delegated campaign changed guard or imported resolver")
            expected = (["--core", ownership["files"]["bin/biocompiler-core"]["path"], "--verify", ownership["files"]["bin/biocompiler-verify"]["path"],
                         "--console", str(origin / "env/bin/biocompiler"), "--fixture", str(fixture)] if name == "material" else
                        ["--verify", ownership["files"]["bin/biocompiler-verify"]["path"], "--fixture", str(fixture), "--producer-receipt",
                         str(origin / "evidence/material.json"), "--network", "required"])
            # The fixture path can differ after download, but its supplied bytes
            # are independently pinned above; retain and check an absolute path.
            observed = argv[3:]; fixture_index = observed.index("--fixture") + 1
            require(Path(observed[fixture_index]).is_absolute(), "Fixture path must be absolute")
            expected[expected.index("--fixture") + 1] = observed[fixture_index]
            require(observed == expected + ["--output", str(origin / "evidence" / (name + ".json"))], "Delegated campaign argv differs")
        else:
            mode = "ownership" if name.endswith("-restored") or name.startswith("ownership-") else name
            expected = [python, "-I", "-B", str(checkout / "tools/check_policy_material_prebuilt.py"), "--probe", mode,
                        "--output", str(origin / "evidence" / (name + ".json"))]
            if name in ("resolver", "mismatched-profile"):
                expected += ["--inputs", str(origin / "cwd/original-inputs.json")]
            elif name in ("component-resolver", "component-role", *COMPONENT_CASES):
                expected += ["--inputs", str(origin / "cwd/component-original-inputs.json")]
            require(argv == expected and row["environment"] == "empty_path_scrubbed_loaders", "Resolver probe isolation or exact command differs")


def compare(args):
    identity = hosted_identity()
    pairs = component_pairs(args, 2)
    staged_path = staged_fixture(args, pairs)
    researcher_path = researcher_expected(args, staged_path)
    require(len(args.compare) == 4 and len(args.platform_root) == len(args.material_authority) == 2, "Comparison requires exactly four slots and two platform authorities")
    candidate, sdk_entries, sdk_stamp = candidate_authority(args.release_candidate, args.sdk, identity)
    native_data = {}
    for root, authority in zip(args.platform_root, args.material_authority):
        native = platform_authority(root, authority, candidate, identity)
        require(native["target"] not in native_data, "Duplicate platform artifact")
        native_data[native["target"]] = native
    require(set(native_data) == set(build.TARGETS), "Missing platform wheel")
    authorities = component_authorities(pairs, identity, native_data) if pairs else None
    slots = {}
    for directory in args.compare:
        options = {"staged_path": staged_path} if staged_path is not None else {}
        if researcher_path is not None:
            options["researcher_path"] = researcher_path
        slot, data = verify_slot(directory, identity, args.release_candidate, args.sdk, sdk_entries, sdk_stamp, native_data, args.fixture, authorities, **options)
        require(slot not in slots, "Duplicate prebuilt runtime slot")
        slots[slot] = data
    require(set(slots) == {(row[0], row[1], minor) for row in build.TARGETS.values() for minor in ("3.11", "3.14")}, "Missing prebuilt runtime slot")
    # Original wheel bytes are the only authority for this temporary adapter.
    # It is not a rewrite of an old _build manifest or acceptance receipt.
    with tempfile.TemporaryDirectory(prefix="policy-prebuilt-wheel-manifests-") as temporary:
        native_root = Path(temporary)
        for target, native in native_data.items():
            root = native_root / target; root.mkdir()
            (root / "binaries.json").write_bytes(native["entries"]["biocompiler_core/binaries.json"][0])
            for role in build.ROLES:
                (root / role).write_bytes(native["entries"]["biocompiler_core/bin/" + role][0])
        import check_policy_material as material
        producers = [path / "evidence/material.json" for path in args.compare]
        consumers = [path / "evidence/consumer.json" for path in args.compare]
        material_result = material.compare(producers, native_root, args.fixture)
        consumer_result = consumer.compare(consumers, producers, native_root, args.fixture)
        if authorities is not None:
            import check_policy_component_material as component
            component_producers = [path / "evidence/component-material.json" for path in args.compare]
            component_consumers = [path / "evidence/component-consumer.json" for path in args.compare]
            component_fixture = next(iter(authorities.values()))["fixture"]
            provenances = {key: row["provenance"] for key, row in authorities.items()}
            component_result = component.compare_installed(component_producers, native_root, component_fixture, provenances)
            component_consumer_result = consumer.compare(component_consumers, component_producers, native_root,
                component_fixture, profile="component", fixture_provenances=provenances)
        if staged_path is not None:
            import check_policy_staged_material_installed as staged
            sources = next(iter(authorities.values()))["sources"]
            require(all(row["sources"] == sources for row in authorities.values()), "Staged source authorities differ across platforms")
            binaries = {build.TARGETS[target][:2]: {"biocompiler-" + role:
                build.sha(native["entries"]["biocompiler_core/bin/biocompiler-" + role][0]) for role in ("core", "verify")}
                for target, native in native_data.items()}
            staged_result = staged.compare_installed([path / "evidence/staged-material.json" for path in args.compare],
                staged_path, identity, binaries, expected_sources=sources)
        if researcher_path is not None:
            import check_researcher_alpha_installed as researcher
            researcher_result = researcher.compare_installed([path / "evidence/researcher-alpha.json" for path in args.compare],
                researcher_path, identity, binaries, expected_sources=sources)
    result = {"schema_version": SCHEMA, "status": "pass", **identity, "source_pins": source_pins(), "fixture": pin(args.fixture),
              "slots": [{"slot": list(slot), "receipt": pin(path / "prebuilt.json"),
                         "run_attempt": read_json(path / "prebuilt.json")["run_attempt"],
                         "upstream_attempts": {"sdk": sdk_stamp["producer_run_attempt"],
                             "native": native_data[next(name for name, row in build.TARGETS.items() if row[:2] == slot[:2])]["stamp"]["producer_run_attempt"]}} for path, slot in
                        sorted(((path, consumer.slot(read_json(path / "prebuilt.json"))) for path in args.compare), key=lambda row: row[1])],
              "material": material_result, "consumer": consumer_result,
              "claim": "supplied_prebuilt_material_profile_only", "default_cutover": "unassessed"}
    if authorities is not None:
        result.update(schema_version=COMPONENT_SCHEMA, claim=COMPONENT_CLAIM,
                      component_originals=[{"platform": list(key), **row["pins"]} for key, row in sorted(authorities.items())],
                      component_material=component_result, component_consumer=component_consumer_result)
    if staged_path is not None:
        result.update(schema_version=STAGED_SCHEMA, claim=STAGED_CLAIM, staged_originals=staged.input_pins(), staged_material=staged_result)
    if researcher_path is not None:
        result.update(schema_version=RESEARCHER_SCHEMA, claim=RESEARCHER_CLAIM,
                      researcher_originals=researcher.input_pins(), researcher_project=researcher_result)
    require(not args.output_dir.exists(), "Comparison output must be fresh")
    args.output_dir.mkdir(parents=True); write_json(args.output_dir / "prebuilt-comparison.json", result)
    if researcher_path is not None:
        import researcher_alpha_starter
        researcher_alpha_starter.create_starter(args, result, native_data)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("sdk", "native", "release-candidate", "fixture", "staged-fixture", "researcher-expected", "output-dir", "inputs", "output", "stamp-artifacts"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--platform-root", type=Path, action="append", default=[])
    parser.add_argument("--material-authority", type=Path, action="append", default=[])
    parser.add_argument("--compare", type=Path, action="append", default=[])
    parser.add_argument("--component-fixture", type=Path, action="append", default=[])
    parser.add_argument("--component-provenance", type=Path, action="append", default=[])
    parser.add_argument("--artifact-kind", choices=("sdk", "native"))
    parser.add_argument("--probe", choices=("ownership", "resolver", *ERRORS, "component-resolver", "component-role", *COMPONENT_CASES))
    args = parser.parse_args()
    for name in ("sdk", "native", "release_candidate", "fixture", "staged_fixture", "researcher_expected", "output_dir", "inputs", "output", "stamp_artifacts"):
        if getattr(args, name) is not None:
            setattr(args, name, getattr(args, name).absolute())
    args.platform_root = [path.absolute() for path in args.platform_root]
    args.material_authority = [path.absolute() for path in args.material_authority]
    args.compare = [path.absolute() for path in args.compare]
    args.component_fixture = [path.absolute() for path in args.component_fixture]
    args.component_provenance = [path.absolute() for path in args.component_provenance]
    if args.probe:
        require(not args.component_fixture and not args.component_provenance and args.staged_fixture is None and args.researcher_expected is None, "Probes cannot replace supplied campaign authority")
        require(args.output is not None, "Probe output is required"); probe(args); return
    if args.stamp_artifacts:
        require(not args.component_fixture and not args.component_provenance and args.staged_fixture is None and args.researcher_expected is None, "Artifact stamps cannot acquire component acceptance")
        require(args.artifact_kind is not None, "Artifact kind is required")
        value = stamp_artifacts(args.stamp_artifacts, args.artifact_kind, hosted_identity())
    else:
        require(all(getattr(args, name) is not None for name in ("sdk", "release_candidate", "fixture", "output_dir")), "Missing prebuilt supplied authority")
        require(args.compare or args.native is not None, "Run requires the supplied native wheel")
        value = compare(args) if args.compare else run(args)
    print(json.dumps({"schema_version": value["schema_version"], "status": value.get("status", "stamped")}, sort_keys=True))


if __name__ == "__main__":
    main()
