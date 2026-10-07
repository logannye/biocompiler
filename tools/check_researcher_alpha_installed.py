"""Hosted installed researcher rehearsal with independent complete artifact checking.

The four existing supplied-wheel slots run this additive software-only campaign.
The public example and inputs are copied outside the checkout. No native process
runs on import or during retained-evidence comparison.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import sys

try:
    import check_policy_component_material as component
    import check_researcher_alpha as researcher
    from check_policy_core import canonical_digest, read_json, source_identity
    from check_policy_development import source_snapshot
    from check_policy_material import archive_receipt
except ModuleNotFoundError:
    from tools import check_policy_component_material as component
    from tools import check_researcher_alpha as researcher
    from tools.check_policy_core import canonical_digest, read_json, source_identity
    from tools.check_policy_development import source_snapshot
    from tools.check_policy_material import archive_receipt

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "biocompiler.researcher_alpha_installed_campaign.v0.2"
SCOPE = "installed_public_research_workflow_under_supplied_artificial_contracts"
EXPECTED = researcher.EXPECTED
RECEIPT = "researcher-alpha.json"
FOLDER = "researcher-alpha"
EXAMPLE = "examples/researcher_alpha.py"
COPY_INPUTS = tuple(name for name in researcher.INPUTS if not name.startswith("src/"))
require = component._require
pin = component.bounded_pin


def checked_inputs(root=ROOT, expected=None):
    return researcher.checked_assets(root, expected or root / EXPECTED)


def input_pins(root=ROOT):
    checked_inputs(root)
    return {name: pin(root / name, 4_000_000) for name in researcher.INPUTS}


def check_origins(origins, package, modules):
    require(type(package) is str and Path(package).is_absolute() and ".." not in Path(package).parts,
            "Missing installed researcher package origin")
    required = component.REQUIRED_MODULES | {"biocompiler.core_distribution", "biocompiler.core_policy_component_selection",
                "biocompiler.policy.component_selection", "biocompiler.policy.research_project", "biocompiler.policy.component_inputs"}
    require(type(origins) is dict and required <= set(origins), "Missing installed researcher transport origins")
    for name, origin in origins.items():
        require(researcher.ResearcherBoundary.allowed(name), "Forbidden Python semantic module in researcher campaign")
        relative = name.removeprefix("biocompiler").lstrip(".").replace(".", "/")
        options = (relative + ".py", relative + "/__init__.py") if relative else ("__init__.py",)
        matches = [path for path in options if path in modules]
        require(len(matches) == 1 and origin == str(Path(package) / matches[0]), "Foreign installed researcher module origin")


def expected_project(case, packet):
    """Independent literal authority; never calls the public producer."""
    return researcher.expected_project(case, packet)


def check_mutant(path, original, kind):
    """Reconstruct only the declared untrusted mutation, independently of the exerciser."""
    from biocompiler.core_client import encode_json
    from biocompiler.policy.material import _verify_staged
    artifact = original["artifact"]
    fasta, manifest = artifact["fasta"].encode(), deepcopy(artifact["manifest"])
    if kind == "candidate":
        construction = manifest["candidate"]["construction"]
        inventory = construction["inventory"]
        require(len(inventory["molecules"]) == 1 and inventory["complexes"] == []
                and inventory["form_mappings"] == [] and construction["experimental_amounts"] == [],
                "Installed candidate mutation has an unreviewed dependency shape")
        molecule = inventory["molecules"][0]
        roles = inventory["role_instances"]
        original_pin = canonical_digest(molecule)
        require(roles and all(role["subject_id"] == molecule["id"] and role["subject_fingerprint"] == original_pin for role in roles),
                "Installed candidate mutation lacks current owned role identities")
        molecule["sequence"] = ("G" if molecule["sequence"][0] != "G" else "C") + molecule["sequence"][1:]
        changed_pin = canonical_digest(molecule)
        for role in roles:
            role["subject_fingerprint"] = changed_pin
    else:
        require(kind == "fasta", "Unknown installed researcher mutation")
        lines = fasta.split(b"\n")
        lines[1] = (b"G" if lines[1][:1] != b"G" else b"C") + lines[1][1:]
        fasta = b"\n".join(lines)
    _verify_staged(path, (("program.fasta", fasta), ("manifest.json", encode_json(manifest))))


def validate_installed(receipt, evidence_root, expected_path, identity, binaries, *, expected_sources, expected_slot=None):
    evidence_root = Path(evidence_root)
    originals, packet = input_pins(), checked_inputs(ROOT, expected_path)
    fields = {"schema_version", "status", "revision", "head_revision", "run_id", "run_attempt", "system", "machine", "python_version",
        "scope", "inputs", "binary_sha256", "package", "installed_modules", "parent_imports", "source_snapshot_sha256",
        "working_directory", "runtime_inputs", "resolution", "observations", "observations_fingerprint", "projects", "publications", "files",
        "python_semantic_authority", "empirical", "real_researcher_project_qualified"}
    require(type(receipt) is dict and set(receipt) == fields and receipt["schema_version"] == SCHEMA and receipt["status"] == "pass",
            "Not a complete installed researcher receipt")
    require(type(receipt["python_version"]) is str and re.fullmatch(r"3\.(11|14)\.[0-9]+", receipt["python_version"]), "Invalid installed researcher runtime")
    slot = receipt["system"], receipt["machine"], ".".join(receipt["python_version"].split(".")[:2])
    require(slot in component.SLOTS and (expected_slot is None or slot == expected_slot), "Wrong installed researcher slot")
    require(all(receipt[key] == identity[key] for key in ("revision", "head_revision", "run_id"))
            and type(receipt["run_attempt"]) is str and re.fullmatch(r"[1-9][0-9]*", receipt["run_attempt"])
            and int(receipt["run_attempt"]) <= int(identity["run_attempt"]), "Stale installed researcher source/run/attempt")
    require(set(binaries) == {"biocompiler-core", "biocompiler-verify"} and all(component._sha(v) for v in binaries.values())
            and receipt["binary_sha256"] == binaries and receipt["inputs"] == originals
            and receipt["source_snapshot_sha256"] == canonical_digest(expected_sources), "Installed researcher external authority differs")
    require(receipt["scope"] == SCOPE and receipt["python_semantic_authority"] == "forbidden" and receipt["empirical"] == "unassessed"
            and receipt["real_researcher_project_qualified"] is False and receipt["resolution"] == "owned_installed_defaults", "Installed researcher scope or resolution promoted")
    require(type(receipt["package"]) is str and Path(receipt["package"]).is_absolute()
            and not Path(receipt["package"]).resolve().is_relative_to(ROOT), "Installed researcher package belongs to checkout")
    require(receipt["installed_modules"] == component.installed_source_modules(ROOT), "Installed researcher package inventory differs")
    check_origins(receipt["parent_imports"], receipt["package"], receipt["installed_modules"])
    cwd = Path(receipt["working_directory"])
    require(cwd.is_absolute() and ".." not in cwd.parts and not cwd.is_relative_to(ROOT), "Researcher working directory is not outside checkout")
    require(receipt["runtime_inputs"] == {name: {"path": str(cwd / "researcher-inputs" / name), **originals[name]}
            for name in COPY_INPUTS}, "Researcher example/input copy census differs")
    rows = receipt["observations"]
    require(type(rows) is list and all(type(row) is dict and set(row) == {"name", "path", "sha256", "bytes"} for row in rows),
            "Malformed installed researcher sidecars")
    researcher.check_census(row["name"] for row in rows)
    observations, expected_files = [], {}
    for row in rows:
        name = FOLDER + "/" + row["name"] + ".json"
        require(row["path"] == name, "Foreign researcher observation path")
        expected_files[name] = {key: row[key] for key in ("sha256", "bytes")}
        path = component._retained(name, evidence_root, expected_files[name], component.MAX_EVIDENCE)
        observations.append({"name": row["name"], "result": read_json(path, component.MAX_EVIDENCE)})
    require(receipt["observations_fingerprint"] == canonical_digest(observations), "Researcher observations fingerprint differs")
    values = researcher.check_observations({row["name"]: row["result"] for row in observations}, packet)
    require(type(receipt["projects"]) is dict and set(receipt["projects"]) == set(researcher.PROJECT_IDS), "Incomplete researcher project census")
    require(type(receipt["publications"]) is list and len(receipt["publications"]) == len(researcher.PROJECT_IDS), "Incomplete researcher publication census")
    authored_case = {**packet["expected"]["cases"][0], "id": "authored",
                     "originals_sha256": canonical_digest(researcher.authored_original(packet))}
    for index, case in enumerate([*packet["expected"]["cases"], authored_case]):
        identity = case["id"]
        project = receipt["projects"][identity]
        require(type(project) is dict and set(project) == {"path", "sha256", "project_sha256", "originals_sha256"}
                and project["path"] == identity + "-project.json", "Researcher project path/metadata differs")
        path = evidence_root / FOLDER / project["path"]
        raw_pin = pin(path); expected_files[FOLDER + "/" + project["path"]] = raw_pin
        actual = read_json(path, 8 * 1024 * 1024)
        require(researcher.exact_json(actual, researcher.expected_authored_project(packet) if identity == "authored" else expected_project(case, packet)) and project["sha256"] == raw_pin["sha256"]
                and canonical_digest(actual) == project["project_sha256"] == values[identity + "-preflight"]["project_sha256"]
                and project["originals_sha256"] == case["originals_sha256"], "Retained researcher project changed its independent originals")
        changed_originals = deepcopy(actual)
        changed_originals["request"]["implementation_request"]["document"]["program"]["source_map"][0]["file"] += ".changed"
        require(canonical_digest(changed_originals) == values[identity + "-changed-originals"]["changed_project_sha256"],
                "Retained original-authority mutation differs from the declared current project")
        publication = receipt["publications"][index]
        require(publication == values[identity + "-paired-publication"] and publication["path"] == identity + ".zip", "Researcher publication metadata differs")
        path = evidence_root / FOLDER / publication["path"]
        archive_receipt(values[identity + "-export-verify"], path)
        expected_files[FOLDER + "/" + publication["path"]] = pin(path)
        for kind in (() if identity == "authored" else ("candidate", "fasta")):
            name = FOLDER + "/" + identity + "-changed-" + kind + ".zip"
            path = evidence_root / name
            expected_files[name] = pin(path)
            require(expected_files[name]["sha256"] == values[identity + "-changed-" + kind]["bundle_sha256"], "Researcher mutation bytes differ")
            check_mutant(path, values[identity + "-export-verify"], kind)
    require(receipt["files"] == expected_files, "Missing or extra installed researcher evidence pins")
    folder = evidence_root / FOLDER
    require(not folder.is_symlink() and set(folder.iterdir()) == {evidence_root / name for name in expected_files},
            "Missing or extra installed researcher evidence file")
    for name, metadata in expected_files.items():
        component._retained(name, evidence_root, metadata, component.MAX_EVIDENCE)
    require(input_pins() == originals, "Researcher input authority changed during validation")
    return values


def compare_installed(paths, expected_path, identity, binary_authorities, *, expected_sources):
    require(len(paths) == 4 and set(binary_authorities) == {("Linux", "x86_64"), ("Darwin", "arm64")}, "Researcher comparison requires four slots and both native authorities")
    found, observations, attempts = set(), None, []
    for path in paths:
        receipt = read_json(path, component.MAX_RECEIPT)
        require(type(receipt) is dict and type(receipt.get("python_version")) is str, "Malformed researcher slot")
        slot = receipt.get("system"), receipt.get("machine"), ".".join(receipt["python_version"].split(".")[:2])
        require(slot in component.SLOTS and slot not in found, "Duplicate or unsupported researcher slot")
        values = validate_installed(receipt, path.parent, expected_path, identity, binary_authorities[slot[:2]], expected_sources=expected_sources, expected_slot=slot)
        require(observations is None or values == observations, "Complete researcher results differ across installed slots")
        observations = values; found.add(slot)
        attempts.append({"slot": list(slot), "run_attempt": receipt["run_attempt"], "receipt": pin(path, component.MAX_RECEIPT)})
    require(found == component.SLOTS, "Incomplete researcher installed slots")
    return {"schema_version": SCHEMA, "status": "pass", **identity, "scope": SCOPE, "inputs": input_pins(),
        "slots": sorted(found), "attempts": sorted(attempts, key=lambda row: row["slot"]), "observations_fingerprint": canonical_digest(observations),
        "empirical": "unassessed", "python_semantic_authority": "forbidden", "real_researcher_project_qualified": False}


def run(args):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted", "Installed researcher campaign is hosted-only")
    hosted, before = source_identity(), source_snapshot(ROOT)
    require(hosted["run_id"] != "local", "Installed researcher campaign needs a hosted run")
    slot = platform.system(), platform.machine(), f"{sys.version_info.major}.{sys.version_info.minor}"
    require(slot in component.SLOTS and not Path.cwd().resolve().is_relative_to(ROOT), "Installed researcher runtime must be outside checkout")
    originals = input_pins(); checked_inputs(ROOT, args.expected)
    binaries = {"biocompiler-core": args.core_sha256, "biocompiler-verify": args.verify_sha256}
    require(all(component._sha(value) for value in binaries.values()), "External researcher native pins are required")
    paths = {role: getattr(args, role).absolute() for role in ("core", "verify")}
    measured = {role: pin(path, 256 * 1024 * 1024, executable=True) for role, path in paths.items()}
    require(all(measured[role]["sha256"] == binaries["biocompiler-" + role] for role in measured), "Installed researcher native bytes differ")
    spec = importlib.util.find_spec("biocompiler")
    require(spec is not None and spec.origin is not None, "Install the reviewed researcher SDK")
    package = Path(spec.origin).resolve().parent
    modules = component.installed_package_modules(ROOT, package)
    output = args.output.absolute()
    require(output.name == RECEIPT and not output.exists() and not output.is_relative_to(ROOT)
            and output.parent.is_dir() and not output.parent.is_symlink(), "Use a fresh installed researcher receipt outside checkout")
    artifacts = output.with_suffix(""); artifacts.mkdir(exist_ok=False)
    cwd = Path.cwd().resolve(); copied = cwd / "researcher-inputs"; copied.mkdir(exist_ok=False)
    for name in COPY_INPUTS:
        target = copied / name; target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
        require(pin(target) == originals[name], "Researcher copied input changed")
    packet = checked_inputs(copied, copied / EXPECTED)
    result = {"schema_version": SCHEMA, "status": "incomplete", **hosted, "system": slot[0], "machine": slot[1],
        "python_version": platform.python_version(), "scope": SCOPE, "inputs": originals, "binary_sha256": binaries,
        "package": str(package), "installed_modules": modules, "parent_imports": {}, "source_snapshot_sha256": canonical_digest(before),
        "resolution": "owned_installed_defaults", "working_directory": str(cwd), "runtime_inputs": {name: {"path": str(copied / name), **originals[name]} for name in COPY_INPUTS},
        "observations": [], "observations_fingerprint": None, "projects": {}, "publications": [], "files": {},
        "python_semantic_authority": "forbidden", "empirical": "unassessed", "real_researcher_project_qualified": False}
    def save():
        raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(len(raw) <= component.MAX_RECEIPT, "Researcher installed receipt exceeded its bound")
        output.write_bytes(raw)
    def retain(name, value):
        from biocompiler.core_client import encode_json
        index = len(result["observations"])
        require(index < len(researcher.OBSERVATIONS) and name == researcher.OBSERVATIONS[index], "Changed installed researcher observation order")
        path = artifacts / (name + ".json")
        with path.open("xb") as stream: stream.write(encode_json(value))
        result["observations"].append({"name": name, "path": str(path.relative_to(output.parent)), **pin(path)})
        save()
    def unchanged():
        require(source_identity() == hosted and source_snapshot(ROOT) == before and input_pins() == originals
                and component.installed_package_modules(ROOT, package) == modules
                and {role: pin(path, 256 * 1024 * 1024, executable=True) for role, path in paths.items()} == measured
                and all(pin(copied / name) == originals[name] for name in COPY_INPUTS), "Researcher installed source/input/package/native authority changed")
    authored = researcher.prepare_authored(packet)
    previous, boundary = sys.getprofile(), researcher.ResearcherBoundary(package)
    try:
        boundary.origins()
        sys.meta_path.insert(0, boundary); sys.setprofile(boundary.trace)
        from biocompiler.core_client import CoreClient
        example = researcher.load_example(copied / EXAMPLE)
        transports = {role: CoreClient(path, role=role, expected_sha256=binaries["biocompiler-" + role], timeout_seconds=90) for role, path in paths.items()}
        result.update(researcher.exercise(packet, example, transports["core"], transports["verify"], retain, artifacts, use_installed_defaults=True, authored=authored))
        researcher.check_census(row["name"] for row in result["observations"])
        result["parent_imports"] = boundary.origins(); check_origins(result["parent_imports"], str(package), modules)
        observations = [{"name": row["name"], "result": read_json(output.parent / row["path"], component.MAX_EVIDENCE)} for row in result["observations"]]
        result["observations_fingerprint"] = canonical_digest(observations)
        result["files"] = {str(path.relative_to(output.parent)): pin(path) for path in sorted(artifacts.iterdir())}
        result["status"] = "pass"
    except Exception as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        sys.setprofile(previous)
        if boundary in sys.meta_path: sys.meta_path.remove(boundary)
        try:
            unchanged()
            if result["status"] == "pass":
                validate_installed(result, output.parent, args.expected, hosted, binaries, expected_sources=before, expected_slot=slot)
                unchanged()
                require(boundary.origins() == result["parent_imports"], "Installed researcher imports changed during validation")
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
