"""Hosted public research-project rehearsal under supplied artificial contracts.

Complete original inputs and independent expected values come from the reviewed
research corpus. This source-tree receipt does not grant installed, release,
empirical or researcher-project acceptance. No native process runs on import.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import re
import sys
import time
import zipfile

try:
    from check_policy_core import canonical_digest, digest_file, read_json, source_identity
    from check_policy_development import git, identity, pin, source_snapshot
    from check_policy_component_material import ComponentBoundary, NATIVE_PATHS, MAX_RECEIPT, MAX_EVIDENCE
    from check_policy_material import archive_receipt
except ModuleNotFoundError:
    from tools.check_policy_core import canonical_digest, digest_file, read_json, source_identity
    from tools.check_policy_development import git, identity, pin, source_snapshot
    from tools.check_policy_component_material import ComponentBoundary, NATIVE_PATHS, MAX_RECEIPT, MAX_EVIDENCE
    from tools.check_policy_material import archive_receipt

SCHEMA = "biocompiler.researcher_alpha_sdk_development.v0.1"
EXPECTED = "data/researcher_alpha/expected.json"
OUTPUT = "generated/development-feedback/researcher-alpha-sdk-witness.json"
ASSETS = ("staged-input.json", "comparison-input.json", "expected.json", "provenance.json", "qualification.json", "negative-controls.json")
INPUTS = tuple("data/researcher_alpha/" + name for name in ASSETS) + (
    "examples/researcher_alpha.py", "src/biocompiler/policy/research_project.py")
CASE_IDS = ("staged", "comparison")
CASE_OBSERVATIONS = ("preflight", "compile-core", "export-verify", "reverify-verify", "paired-publication",
                     "changed-candidate", "changed-fasta", "changed-originals")
OBSERVATIONS = tuple(case + "-" + name for case in CASE_IDS for name in CASE_OBSERVATIONS) + (
    "staged-insufficient-capacity", "staged-capacity-no-publication", "staged-completion-without-feedback", "incomplete-reference")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check_census(names):
    require(tuple(names) == OBSERVATIONS, "Incomplete, duplicated or reordered researcher observation census")


class ResearcherBoundary(ComponentBoundary):
    """Allow public owned-package resolution without enabling Python semantics."""
    @staticmethod
    def allowed(name):
        return name in {"biocompiler.core_distribution", "biocompiler.core_policy_component_selection"} or ComponentBoundary.allowed(name)


def tracked_inputs(root):
    """Bind extra data/example inputs to exact HEAD blobs, beyond the shared source roots."""
    rows = git(root, "ls-tree", "-r", "-z", "HEAD", "--", *INPUTS).split(b"\0")
    result = {}
    for row in filter(None, rows):
        header, encoded_name = row.split(b"\t", 1)
        mode, kind, blob = header.decode().split()
        name = encoded_name.decode("utf-8")
        require(name in INPUTS and name not in result and mode in {"100644", "100755"} and kind == "blob", "Unexpected researcher tracked input")
        raw = (root / name).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        require(actual == blob, "Researcher input differs from HEAD: " + name)
        result[name] = {**pin(root, name), "git_blob": blob}
    require(set(result) == set(INPUTS), "Missing complete researcher tracked-input census")
    return result


def read_provenance(path):
    """Read bounded metadata, retaining finite historical elapsed-time numbers."""
    require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 128 * 1024, "Invalid provenance input")
    raw = path.read_bytes()
    require(len(raw) <= 128 * 1024, "Provenance exceeds its byte bound")
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "Duplicate provenance key")
            result[key] = value
        return result
    def number(value):
        require(len(value) <= 64 and math.isfinite(float(value)), "Nonfinite or oversized provenance number")
        return float(value)
    def forbidden(value):
        raise AssertionError("Nonfinite provenance value: " + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_float=number, parse_constant=forbidden)


def checked_assets(root: Path, expected_path: Path) -> dict:
    require(expected_path.resolve() == (root / EXPECTED).resolve() and not expected_path.is_symlink(), "Use the exact independent researcher oracle")
    folder = root / "data/researcher_alpha"
    expected = read_json(expected_path, 128 * 1024)
    require(set(expected) == {"schema_version", "acceptance", "cases", "claim_scope", "kind", "method"}
            and expected["schema_version"] == "biocompiler.researcher_alpha_expected.v0.1"
            and expected["acceptance"] is False and expected["kind"] == "independently_declared_software_oracle"
            and tuple(row["id"] for row in expected["cases"]) == CASE_IDS,
            "Researcher oracle has an unexpected schema, census or acceptance claim")
    require(expected["claim_scope"] == {"empirical": "unassessed", "functional_expression": "not_claimed",
            "human_immune_applicability": "not_established", "intended_validation": "software_under_supplied_artificial_contracts",
            "physical_staged_realization": "not_claimed", "real_researcher_project_qualified": False,
            "universal_termination": "not_claimed"}, "Researcher oracle widened its software-only claim")
    provenance = read_provenance(folder / "provenance.json")
    files = provenance["files"]
    require([row["path"] for row in files] == [name for name in ASSETS if name != "provenance.json"], "Provenance omitted or added input files")
    for row in files:
        raw = (folder / row["path"]).read_bytes()
        require(set(row) == {"path", "bytes", "sha256"} and type(row["bytes"]) is int
                and row["bytes"] == len(raw) and row["sha256"] == hashlib.sha256(raw).hexdigest(), "Research input differs from its retained provenance")
    inputs = {}
    for case in expected["cases"]:
        require(case["input"] == case["id"] + "-input.json" and case["route"] == "component_material", "Research case changed its supported route")
        value = read_json(folder / case["input"], 4 * 1024 * 1024)
        require(set(value) == {"request", "limits"} and canonical_digest(value) == case["originals_sha256"], "Original request/limits differ from the frozen oracle")
        require(len(case["sequence"]) == case["length"] and hashlib.sha256(case["sequence"].encode()).hexdigest() == case["sequence_sha256"]
                and hashlib.sha256(case["fasta"].encode()).hexdigest() == case["fasta_sha256"], "Independent exact sequence oracle is internally inconsistent")
        inputs[case["id"]] = value
    qualification = read_json(folder / "qualification.json", 128 * 1024)
    controls = read_json(folder / "negative-controls.json", 128 * 1024)
    require(qualification["schema_version"] == "biocompiler.researcher_alpha_qualification.v0.1"
            and controls["schema_version"] == "biocompiler.researcher_alpha_negative_controls.v0.1"
            and qualification["real_researcher_project_status"] == "open", "Qualification scope changed")
    return {"root": root, "expected": expected, "inputs": inputs, "qualification": qualification, "controls": controls}


def load_example(path: Path):
    spec = importlib.util.spec_from_file_location("researcher_alpha_example", path)
    require(spec is not None and spec.loader is not None, "Public researcher example cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checked_result(result, case, original, *, exported=False):
    """Compare native results with independent input/output and bounded-domain declarations."""
    report, candidate = result["report"], result["candidate"]
    require(report["status"] == "checked_component_material" and report["empirical"] == "unassessed"
            and report["assembly_status"] == report["context_status"] == "pass"
            and report["all_original_obligations_discharged"] is True
            and report["artifact"] == report["export"] == "withheld"
            and report["obligations"] and all(row["status"] == "discharged" for row in report["obligations"]),
            "Research result lacks the complete conditional conjunction")
    coverage = report["preservation"]["coverage"]
    require(report["preservation"]["preservation"] == "pass" and coverage["complete"] is True
            and {key: coverage[key] for key in case["bounded_domain"]} == case["bounded_domain"]
            and coverage["matched_prefixes"] == case["bounded_domain"]["prefixes_started"], "Research bounded-domain coverage changed")
    molecules = candidate["construction"]["inventory"]["molecules"]
    require(len(molecules) == 1, "Research candidate changed its complete molecule census")
    molecule = molecules[0]
    require(molecule["id"] == case["molecule_id"] and molecule["sequence"] == case["sequence"]
            and molecule["space"]["alphabet"] == case["alphabet"] and molecule["space"]["topology"] == case["topology"]
            and molecule["space"]["length"] == case["length"], "Research molecule differs from independent exact authority")
    require(all(len(row["path"]["spans"]) == 1 for row in molecule["features"]), "Research features changed their whole-region coordinates")
    regions = [{"id": row["id"], "start": row["path"]["spans"][0]["start"], "end": row["path"]["spans"][0]["end"]}
               for row in molecule["features"]]
    require(sorted(regions, key=lambda row: row["start"]) == case["regions"], "Research exact region boundaries differ from independent coordinates")
    chemistry = molecule["chemistry"]
    require(chemistry["cap"]["status"] == "declared" and chemistry["cap"]["identity"]["accession"] == case["cap_accession"]
            and chemistry["cap"]["identity"]["namespace"] == case["cap_namespace"]
            and chemistry["modifications"] == case["declared_modifications"]
            and chemistry["terminal_tail"]["length"]["mode"] == "exact"
            and chemistry["terminal_tail"]["length"]["exact"] == case["declared_tail_length"], "Research chemistry declarations changed")
    require({"nodes": len(candidate["implementation"]["nodes"]), "wires": len(candidate["implementation"]["wires"]),
             "links": len(report["assembly"]["link_projections"])} == case["graph"], "Research graph/assembly census changed")
    if exported:
        artifact = result["artifact"]
        require(artifact is not None and artifact["fasta"] == case["fasta"]
                and artifact["fasta_sha256"] == case["fasta_sha256"], "Research exact exported FASTA differs")
        manifest = artifact["manifest"]
        require(manifest["request"] == original["request"] and manifest["limits"] == original["limits"]
                and manifest["candidate"] == candidate and manifest["assessment"] == report
                and artifact["manifest_sha256"] == canonical_digest(manifest), "Research export omitted original authority or native evidence")
    else:
        require(result["artifact"] is None, "Compilation unexpectedly published an artifact")


def changed_bundle(source, target, kind):
    """Rebuild fixed ZIP metadata while changing only the specified untrusted content."""
    from biocompiler.core_client import decode_json, encode_json
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, "x", compression=zipfile.ZIP_STORED) as changed:
        for entry in original.infolist():
            raw = original.read(entry)
            if kind == "candidate" and entry.filename == "manifest.json":
                value = decode_json(raw)
                molecule = value["candidate"]["construction"]["inventory"]["molecules"][0]
                molecule["sequence"] = ("G" if molecule["sequence"][0] != "G" else "C") + molecule["sequence"][1:]
                raw = encode_json(value)
            elif kind == "fasta" and entry.filename == "program.fasta":
                lines = raw.split(b"\n")
                lines[1] = (b"G" if lines[1][:1] != b"G" else b"C") + lines[1][1:]
                raw = b"\n".join(lines)
            changed.writestr(entry, raw)
    require(kind in {"candidate", "fasta"}, "Unknown bundle mutation")


def deficient_capacity(request):
    value, count = deepcopy(request), 0
    for provider in value["context"]["providers"]:
        for capacity in provider["body"]["capacities"]:
            if capacity["unit"] == "machine_state_bits":
                capacity["quantity"] = 2
                count += 1
        provider["identity"]["content_fingerprint"] = canonical_digest(provider["body"])
    require(count == 1, "Missing unique staged capacity premise")
    return value


def completion_request(request):
    value = deepcopy(request)
    requirements = [row for row in value["implementation_request"]["document"]["program"]["declarations"]
                    if row["$type"] == "Requirement" and row["id"] == "second_initiation"]
    require(len(requirements) == 1 and requirements[0]["response"]["value"] == "initiated", "Missing completion mutation target")
    requirements[0]["response"]["value"] = "completed"
    return value


def check_observations(observations, packet):
    """Audit retained native results against external originals without executing native code.

    observations is an insertion-ordered mapping of exact observation names to
    decoded JSON values. The caller authenticates sidecar/ZIP/project bytes and
    source/run/installed ownership independently; this function grants none.
    """
    from biocompiler.core_client import CORE_VERSION, CoreResponse
    from biocompiler.core_policy_component_material import _result
    check_census(observations)
    for case in packet["expected"]["cases"]:
        prefix = case["id"] + "-"
        original = packet["inputs"][case["id"]]
        preflight = observations[prefix + "preflight"]
        require(set(preflight) == {"project_sha256", "route", "source_count", "status", "native_status", "biological_status", "provenance_status"}
                and preflight["route"] == case["route"] and type(preflight["source_count"]) is int and preflight["source_count"] == 1
                and preflight["status"] == "structurally_ready" and preflight["native_status"] == "not_run"
                and preflight["biological_status"] == "unassessed" and preflight["provenance_status"] == "caller_declared"
                and re.fullmatch(r"[0-9a-f]{64}", preflight["project_sha256"]), "Retained preflight widened its structural scope")
        for name, role, operation in (("compile-core", "core", "compile"), ("export-verify", "verify", "export"), ("reverify-verify", "verify", "export")):
            result = observations[prefix + name]
            payload = {"request": original["request"], "limits": original["limits"]}
            if operation == "export":
                payload["candidate"] = observations[prefix + "compile-core"]["candidate"]
            _result(CoreResponse("retained-research", operation + "-policy-component-material", "ok", result, (), role, CORE_VERSION), payload)
            checked_result(result, case, original, exported=operation == "export")
        require(observations[prefix + "export-verify"] == observations[prefix + "reverify-verify"], "Retained fresh verification differs")
        require(observations[prefix + "paired-publication"] == {**archive_receipt(observations[prefix + "export-verify"]), "path": case["id"] + ".zip"},
                "Retained paired publication differs from native bytes")
        changed = observations[prefix + "changed-candidate"]
        require(set(changed) == {"status", "diagnostics", "bundle_sha256"} and changed["status"] == "error"
                and changed["diagnostics"] and {row["code"] for row in changed["diagnostics"]} == {"policy_component_material_export_not_accepted"}
                and re.fullmatch(r"[0-9a-f]{64}", changed["bundle_sha256"]), "Retained candidate rejection differs")
        changed = observations[prefix + "changed-fasta"]
        require(set(changed) == {"status", "boundary", "message", "bundle_sha256"} and changed["status"] == "rejected"
                and changed["boundary"] == "exact_native_pair_comparison" and "exact FASTA/manifest pair" in changed["message"]
                and re.fullmatch(r"[0-9a-f]{64}", changed["bundle_sha256"]), "Retained FASTA rejection differs")
        changed = observations[prefix + "changed-originals"]
        require(set(changed) == {"status", "boundary", "changed_project_sha256", "message"} and changed["status"] == "rejected"
                and changed["boundary"] == "independent_original_authority" and "authority differs" in changed["message"]
                and re.fullmatch(r"[0-9a-f]{64}", changed["changed_project_sha256"]), "Retained original-authority rejection differs")
    original = packet["inputs"]["staged"]
    for name, request in (("staged-insufficient-capacity", deficient_capacity(original["request"])),
                          ("staged-completion-without-feedback", completion_request(original["request"]))):
        value = observations[name]
        checked = _result(CoreResponse("retained-research", "compile-policy-component-material", "ok", value, (), "core", CORE_VERSION),
                          {"request": request, "limits": original["limits"]})
        require(checked.status == "not_accepted" and checked.artifact is None, "Retained negative compilation acquired acceptance")
        if name == "staged-insufficient-capacity":
            require(checked.report["context_status"] == "fail", "Capacity rejection failed at another stage")
        else:
            require(any(row["id"] == "second_initiation" and row["status"] == "fail" for row in checked.report["preservation"]["requirements"]),
                    "Completion control lacks its actual requirement failure")
    value = observations["staged-capacity-no-publication"]
    require(set(value) == {"status", "artifact", "message"} and value["status"] == "rejected" and value["artifact"] == "absent"
            and "Core did not accept" in value["message"], "Capacity-publication control changed")
    value, control = observations["incomplete-reference"], packet["controls"]["qualification_control"]
    require(set(value) == {"status", "scope", "missing", "message", "artifact"}
            and value["status"] == control["expected_status"] and value["missing"] == control["required_missing"]
            and value["scope"] == "structural_qualification_not_native_rejection" and value["artifact"] == "absent"
            and "complete versioned fields" in value["message"], "Incomplete reference became native admission")
    return observations


def exercise(packet, example, core, verify, retain, artifacts: Path, *, use_installed_defaults=False):
    from biocompiler.core_client import CoreRejected
    from biocompiler.core_policy_component_material import PolicyComponentMaterialClient
    from biocompiler.policy.research_project import ResearchProject, ResearchProjectError

    require(type(use_installed_defaults) is bool, "Researcher resolver mode must be explicit")
    if use_installed_defaults:
        from biocompiler.core_distribution import installed_core
        for role, operation, supplied in (("core", "compile-policy-component-material", core),
                                           ("verify", "export-policy-component-material", verify)):
            resolved = installed_core(role=role, operation=operation, timeout_seconds=90)
            require(resolved.role == role and resolved.executable.resolve() == supplied.executable.resolve()
                    and resolved.expected_sha256 == supplied.expected_sha256,
                    "Owned default resolver differs from independently pinned installed executables")
    public_core, public_verify = (None, None) if use_installed_defaults else (core, verify)
    projects, publications = {}, []
    staged_project = None
    for case in packet["expected"]["cases"]:
        identity, original = case["id"], packet["inputs"][case["id"]]
        prefix = identity + "-"
        project_path, output = artifacts / (identity + "-project.json"), artifacts / (identity + ".zip")
        project = example.prepare(packet["root"] / "data/researcher_alpha" / case["input"], project_path,
            project_id="software.rehearsal." + identity, title="Artificial software rehearsal: " + identity,
            version="1", reuse_terms="Project-authored software test inputs; repository distribution terms remain separate.")
        require(project.request == original["request"] and project.limits == original["limits"], "Public preparation changed complete caller authority")
        preflight = example.preflight(project_path)
        require(preflight["native_status"] == "not_run" and preflight["biological_status"] == "unassessed"
                and preflight["status"] == "structurally_ready", "Preflight silently became native acceptance")
        retain(prefix + "preflight", preflight)
        built = example.compile_project(project_path, output, core=public_core, verify=public_verify)
        require(built.compiled.executable == "core" and built.verified.executable == "verify", "Public path omitted independent Verify")
        checked_result(built.compiled.result, case, original)
        checked_result(built.verified.result, case, original, exported=True)
        retain(prefix + "compile-core", built.compiled.result)
        retain(prefix + "export-verify", built.verified.result)
        fresh = example.verify_project(project_path, output, verify=public_verify)
        checked_result(fresh.result, case, original, exported=True)
        require(fresh.result == built.verified.result, "Fresh public verification changed complete native evidence")
        retain(prefix + "reverify-verify", fresh.result)
        pair = archive_receipt(fresh.result)
        require(output.read_bytes() and pair["sha256"] == digest_file(output), "Published archive differs from exact native bytes")
        pair = {**pair, "path": output.name}
        retain(prefix + "paired-publication", pair)
        publications.append(pair)
        for kind in ("candidate", "fasta"):
            changed = artifacts / (identity + "-changed-" + kind + ".zip")
            changed_bundle(output, changed, kind)
            try:
                example.verify_project(project_path, changed, verify=public_verify)
            except CoreRejected as error:
                require(kind == "candidate" and error.response.result is None and
                    {row.code for row in error.response.diagnostics} == {"policy_component_material_export_not_accepted"},
                    "Candidate control failed at an unrelated native boundary")
                retained = {"status": error.response.status, "diagnostics": [asdict(row) for row in error.response.diagnostics]}
            except ResearchProjectError as error:
                require(kind == "fasta" and "exact FASTA/manifest pair" in str(error), "FASTA control failed at an unrelated boundary")
                retained = {"status": "rejected", "boundary": "exact_native_pair_comparison", "message": str(error)}
            else:
                raise AssertionError("Changed research bundle acquired acceptance")
            retain(prefix + "changed-" + kind, {**retained, "bundle_sha256": digest_file(changed)})
        altered = project.data
        altered["request"]["implementation_request"]["document"]["program"]["source_map"][0]["file"] += ".changed"
        try:
            ResearchProject.from_data(altered).verify_bundle(output, verify=verify)
        except ResearchProjectError as error:
            require("authority differs" in str(error), "Stale originals failed at an unrelated boundary")
            retain(prefix + "changed-originals", {"status": "rejected", "boundary": "independent_original_authority",
                "changed_project_sha256": canonical_digest(altered), "message": str(error)})
        else:
            raise AssertionError("Embedded bundle originals replaced current independent authority")
        projects[identity] = {"path": project_path.name, "sha256": digest_file(project_path), "project_sha256": project.digest,
                              "originals_sha256": canonical_digest(original)}
        if identity == "staged":
            staged_project = project

    require(staged_project is not None, "Missing staged independent project")
    deficient = deficient_capacity(staged_project.request)
    failed = PolicyComponentMaterialClient(core).compile(deficient, staged_project.limits)
    require(failed.status == "not_accepted" and failed.artifact is None and failed.report["context_status"] == "fail",
            "Insufficient capacity acquired acceptance or failed for another reason")
    retain("staged-insufficient-capacity", failed.result)
    altered = staged_project.data
    altered["request"] = deficient
    output = artifacts / "insufficient-capacity.zip"
    try:
        ResearchProject.from_data(altered).compile(output=output, core=core, verify=verify)
    except ResearchProjectError as error:
        require("Core did not accept" in str(error) and not output.exists(), "Capacity failure published an artifact")
        retain("staged-capacity-no-publication", {"status": "rejected", "artifact": "absent", "message": str(error)})
    else:
        raise AssertionError("Insufficient public project published a bundle")
    completion = completion_request(staged_project.request)
    incomplete = PolicyComponentMaterialClient(core).compile(completion, staged_project.limits)
    require(incomplete.status == "not_accepted" and incomplete.artifact is None
            and any(row["id"] == "second_initiation" and row["status"] == "fail" for row in incomplete.report["preservation"]["requirements"]),
            "Absent completion feedback was promoted to guaranteed progress")
    retain("staged-completion-without-feedback", incomplete.result)
    control = packet["controls"]["qualification_control"]
    candidates = [row for row in packet["qualification"]["candidates"] if row["id"] == control["source_candidate"]]
    require(len(candidates) == 1 and candidates[0]["missing"] == control["required_missing"], "Incomplete-reference qualification changed")
    try:
        ResearchProject.from_data(candidates[0])
    except ResearchProjectError as error:
        retain("incomplete-reference", {"status": control["expected_status"], "scope": "structural_qualification_not_native_rejection",
            "missing": candidates[0]["missing"], "message": str(error), "artifact": "absent"})
    else:
        raise AssertionError("Incomplete reference metadata acquired complete project authority")
    return {"projects": projects, "publications": publications}


def run(args):
    root = Path(__file__).resolve().parents[1]
    hosted, source, before = identity(root), source_identity(), source_snapshot(root)
    inputs = tracked_inputs(root)
    packet = checked_assets(root, args.expected)
    paths = {role: getattr(args, role).resolve(strict=True) for role in NATIVE_PATHS}
    require(all(path == (root / NATIVE_PATHS[role]).resolve() for role, path in paths.items()), "Use the exact current hosted native build")
    binaries = {role: pin(root, relative, executable=True) for role, relative in NATIVE_PATHS.items()}
    output = args.output.resolve()
    require(output == (root / OUTPUT).resolve() and not args.output.is_symlink() and not output.exists(), "Use a fresh fixed researcher receipt path")
    artifacts = output.with_suffix("")
    artifacts.mkdir(exist_ok=False)
    result = {"schema_version": SCHEMA, "status": "incomplete", "acceptance": False, "identity": hosted,
        "source_identity": source, "python": platform.python_version(), "binary_sha256": binaries,
        "inputs": inputs, "observations": [], "python_semantic_authority": "forbidden",
        "scope": "Hosted source-tree public research workflow under artificial supplied contracts; installed, release, empirical and actual researcher qualification remain separate."}
    previous, boundary, start = sys.getprofile(), None, time.monotonic()

    def save():
        raw = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
        require(len(raw) <= MAX_RECEIPT, "Research receipt exceeds its bound")
        output.write_bytes(raw)

    def retain(name, value):
        from biocompiler.core_client import encode_json
        index = len(result["observations"])
        require(index < len(OBSERVATIONS) and name == OBSERVATIONS[index], "Changed researcher observation order")
        raw = encode_json(value)
        require(len(raw) <= MAX_EVIDENCE, "Research observation exceeds its bound")
        path = artifacts / (name + ".json")
        with path.open("xb") as stream:
            stream.write(raw)
        result["observations"].append({"name": name, "path": str(path.relative_to(output.parent)),
                                     "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)})
        save()

    try:
        sys.path.insert(0, str(root / "src"))
        spec = importlib.util.find_spec("biocompiler")
        require(spec is not None and Path(spec.origin).resolve() == root / "src/biocompiler/__init__.py", "Foreign researcher SDK package")
        boundary = ResearcherBoundary(root / "src/biocompiler")
        sys.meta_path.insert(0, boundary)
        sys.setprofile(boundary.trace)
        from biocompiler.core_client import CoreClient
        example = load_example(root / "examples/researcher_alpha.py")
        transports = {role: CoreClient(paths[role], role=role, expected_sha256=binaries[role]["sha256"], timeout_seconds=90)
                      for role in NATIVE_PATHS}
        result.update(exercise(packet, example, transports["core"], transports["verify"], retain, artifacts))
        check_census(row["name"] for row in result["observations"])
        result["parent_imports"] = boundary.origins()
        result["status"] = "passed"
    except Exception as error:
        result.update(status="failed", error=f"{type(error).__name__}: {error}")
        raise
    finally:
        sys.setprofile(previous)
        if boundary is not None:
            sys.meta_path.remove(boundary)
        result["elapsed_seconds"] = round(time.monotonic() - start, 3)
        try:
            require(identity(root) == hosted and source_identity() == source and source_snapshot(root) == before
                    and tracked_inputs(root) == inputs and
                    {role: pin(root, relative, executable=True) for role, relative in NATIVE_PATHS.items()} == binaries,
                    "Research source, inputs, native bytes or hosted identity changed")
            result["source_snapshot_sha256"] = canonical_digest(before)
        except Exception as error:
            result.update(status="failed", source_error=str(error))
        save()
        require(result["status"] == "passed", result.get("source_error", result.get("error", "Incomplete researcher witness")))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, required=True)
    parser.add_argument("--verify", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    print(json.dumps(run(parser.parse_args()), sort_keys=True))


if __name__ == "__main__":
    main()
