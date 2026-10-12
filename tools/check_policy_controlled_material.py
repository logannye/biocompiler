"""Hosted actual-binary RC4 structural pair campaign; no activity acceptance."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import platform
from unittest.mock import patch
import zipfile

try:
    from .check_policy_controlled_composition import file_pin, imported_modules, require
    from .check_policy_core import source_identity
except ImportError:
    from check_policy_controlled_composition import file_pin, imported_modules, require
    from check_policy_core import source_identity

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = {"request": "core/test/data/policy_controlled_request_v014.json",
    "material": "core/test/data/policy_controlled_material_v01.json"}
MUTATIONS = ("changed-utr", "changed-cds", "changed-chemistry", "swapped-members", "missing-member", "extra-member", "foreign-repinned")
NEGATIVE_DIAGNOSTICS = {
    "foreign-original": ("error", "controlled_material_request_binding"),
    "request-work-exhaustion": ("error", "controlled_material_service_work_limit"),
    "domain-work-exhaustion": ("error", "controlled_domain_exhausted"),
    "report-byte-exhaustion": ("error", "policy_material_input_limit"),
    "verifier-production-role": ("unsupported", "unsupported_operation"),
}
OBSERVATIONS = ("baseline-original", "construct-core", "check-core", "check-verify", "publish-core", "publish-verify",
    "paired-publication", *MUTATIONS, *NEGATIVE_DIAGNOSTICS, "rejected-publication", "prelaunch-cancellation",
    "after-readback-cancellation", "staged-io-failure")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()



def foreign_pair(original, literal):
    """Retain the complete foreign premise and candidate before local repinning."""
    from biocompiler.ir.payload_contracts import PayloadTemplate
    request = deepcopy(original)
    molecule = request["material_authority"]["template"]["sources"][0]["molecule"]
    molecule["sequence"] = "A" + molecule["sequence"][1:]
    candidate = deepcopy(literal)
    candidate["request_fingerprint"] = digest(request)
    candidate["construction"]["authority_fingerprint"] = digest({
        "schema_version": "biocompiler.construction_content_authority.v0.1",
        "template": PayloadTemplate.from_dict(request["material_authority"]["template"]).to_dict(),
        "member_order": request["material_authority"]["member_order"]})
    molecule = candidate["construction"]["inventory"]["molecules"][0]
    molecule["sequence"] = "A" + molecule["sequence"][1:]
    for role in candidate["construction"]["inventory"]["role_instances"]:
        if role["subject_id"] == molecule["id"]: role["subject_fingerprint"] = digest(molecule)
    return request, candidate


def candidates(original, literal):
    """Explicit adversarial record edits, never biological design or construction."""
    result = {name: deepcopy(literal) for name in MUTATIONS}
    for name in ("changed-utr", "foreign-repinned"):
        molecule = result[name]["construction"]["inventory"]["molecules"][0]
        molecule["sequence"] = "A" + molecule["sequence"][1:]
    result["changed-cds"]["construction"]["inventory"]["molecules"][0]["sequence"] = "CCAUGGGUUAAGGAAAA"
    result["changed-chemistry"]["construction"]["inventory"]["molecules"][0]["chemistry"]["cap"]["identity"]["accession"] = "foreign_cap"
    swapped = result["swapped-members"]["construction"]
    swapped["member_order"].reverse(); swapped["inventory"]["molecules"].reverse()
    missing = result["missing-member"]["construction"]
    missing["member_order"].pop(); missing["inventory"]["molecules"].pop()
    missing["inventory"]["role_instances"] = [row for row in missing["inventory"]["role_instances"] if row["subject_id"] == "rna-a"]
    extra = result["extra-member"]["construction"]
    molecule = deepcopy(extra["inventory"]["molecules"][1])
    # A third foreign member has its own declared output frame, including every
    # coordinate occurrence, rather than an invalid duplicate nominal identity.
    def rename(value):
        if isinstance(value, str): return value.replace("rna-b.output.frame", "rna-c.output.frame")
        if isinstance(value, list): return [rename(row) for row in value]
        if isinstance(value, dict): return {key: rename(row) for key, row in value.items()}
        return value
    molecule = rename(molecule); molecule["id"] = "rna-c"
    extra["member_order"].append("rna-c"); extra["inventory"]["molecules"].append(molecule)
    _, foreign = foreign_pair(original, literal)
    foreign["request_fingerprint"] = digest(original)
    foreign["construction"]["authority_fingerprint"] = literal["construction"]["authority_fingerprint"]
    result["foreign-repinned"] = foreign
    for candidate in result.values():
        inventory = candidate["construction"]["inventory"]
        for role in inventory["role_instances"]:
            molecule = next(row for row in inventory["molecules"] if row["id"] == role["subject_id"])
            role["subject_fingerprint"] = digest(molecule)
    return result


def run(args):
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted",
            "Actual native campaign is hosted-only; local execution requires separate authorization")
    from biocompiler.core_client import CoreClient, CoreRejected, CoreCancelled, CoreProtocolError, encode_json
    from biocompiler.core_policy_controlled_material import PolicyControlledMaterialClient, CHECK, CONSTRUCT
    from biocompiler.policy import controlled_material as sdk

    binaries = {role: Path(getattr(args, role)).absolute() for role in ("core", "verify")}
    binary_pins = {role: file_pin(path, 256 * 1024 * 1024) for role, path in binaries.items()}
    for role, path in binaries.items():
        require(os.access(path, os.X_OK), "Selected native path is not executable")
        expected = getattr(args, role + "_sha256")
        require(expected is None or expected == binary_pins[role]["sha256"], "Native bytes differ from supplied digest")
    fixture_pins = {name: file_pin(ROOT/path, 4 * 1024 * 1024) for name, path in FIXTURES.items()}
    request, fixture = (json.loads((ROOT/FIXTURES[name]).read_text()) for name in ("request", "material"))
    require(digest(request) == fixture["request_sha256"] and digest(fixture["literal_candidate"]) == fixture["candidate_sha256"],
            "Independent literal candidate is detached from the complete original")
    require(fixture["expected"]["sequences"] == ["CCAUGGCUUAAGGAAAA", "CCAUGGGUUAAGGAAAA"]
            and fixture["expected"]["products"] == ["MA", "MG"] and fixture["expected"]["total_rna_nt"] == 34,
            "Artificial independent molecular oracle changed")
    output = args.output.absolute()
    require(output.parent.is_dir() and not output.parent.is_symlink() and not output.exists(), "Use a fresh campaign receipt")
    sidecars = output.with_suffix(""); sidecars.mkdir(exist_ok=False)
    identity = source_identity()
    require(identity["run_id"].isdecimal() and int(identity["run_id"]) > 0 and int(identity["run_attempt"]) > 0, "Hosted identity absent")
    receipt = {"schema_version": "biocompiler.policy_controlled_material_campaign.v0.1", "status": "incomplete", **identity,
        "scope": "fresh_native_exact_supplied_two_member_rna_structure_only", "platform": platform.system(),
        "machine": platform.machine(), "python": platform.python_version(), "installed": args.require_installed,
        "binaries": binary_pins, "inputs": fixture_pins, "imports": imported_modules(args.require_installed),
        "campaign_script": file_pin(__file__), "observations": [], "behavior": "not_performed", "empirical": "unassessed",
        "human_use": "unassessed", "therapeutic_export": "withheld"}
    def save(): output.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    def observe(name, value):
        index = len(receipt["observations"])
        require(index < len(OBSERVATIONS) and name == OBSERVATIONS[index], "Campaign census or order changed")
        path = sidecars/(name + ".json")
        with path.open("xb") as stream: stream.write(encode_json(value, limit=16 * 1024 * 1024))
        receipt["observations"].append({"name": name, "path": str(path.relative_to(output.parent)), **file_pin(path)})
        save()
    transports = {role: CoreClient(path, role=role, expected_sha256=binary_pins[role]["sha256"], timeout_seconds=180) for role, path in binaries.items()}
    clients = {role: PolicyControlledMaterialClient(transport) for role, transport in transports.items()}
    def accepted(response):
        require(response.status == "checked_controlled_material" and response.report["outcome"] == "pass", "Structural checkpoint not accepted")
        require(response.report["behavior_status"] == "not_performed" and response.report["empirical_status"] == "unassessed"
                and response.report["human_use"] == "unassessed" and response.report["therapeutic_export"] == "withheld", "Structural checkpoint upgraded its claim")
        require(response.candidate == fixture["literal_candidate"], "Native material differs from complete independent literal")
        require([row["translated_product"] for row in response.report["structure"]["members"]] == fixture["expected"]["products"], "Exact original products changed")
        if response.artifact is not None:
            require(response.artifact["fasta"] == fixture["expected"]["fasta"], "Published FASTA differs from independent two-member oracle")
    def result_record(response):
        return {"request_id": response.request_id, "operation": response.operation, "executable": response.executable, "result": response.result}
    try:
        save(); observe("baseline-original", {"request": request, "fixture": fixture})
        built = clients["core"].construct_material(request); accepted(built); observe("construct-core", result_record(built))
        for role in ("core", "verify"):
            checked = clients[role].check_material(request, built.candidate); accepted(checked)
            require(checked.report == built.report and checked.candidate == built.candidate, "Fresh independent material evidence differs")
            observe("check-" + role, result_record(checked))
        published = {}
        for role in ("core", "verify"):
            fresh = clients[role].publish_material(request, built.candidate); accepted(fresh)
            require(fresh.report == built.report, "Publication changed fresh structural evidence")
            published[role] = fresh; observe("publish-" + role, result_record(fresh))
        require(published["core"].artifact == published["verify"].artifact, "Core/Verify exact material publication differs")
        archive = sidecars/"structural-pair.zip"
        pair = sdk.publish_material(request, candidate=built.candidate, client=clients["verify"], output=archive,
            input_paths=[ROOT/path for path in FIXTURES.values()]); accepted(pair)
        with zipfile.ZipFile(archive) as bundle:
            require(bundle.namelist() == ["program.fasta", "manifest.json"], "Structural archive member inventory changed")
            require(bundle.read("program.fasta") == pair.artifact["fasta"].encode()
                    and bundle.read("manifest.json") == encode_json(pair.artifact["manifest"]), "Archive substituted native bytes")
        observe("paired-publication", {**result_record(pair), "archive": {"path": str(archive.relative_to(output.parent)), **file_pin(archive)}})
        mutants = candidates(request, built.candidate)
        for name, candidate in mutants.items():
            rejected = clients["verify"].check_material(request, candidate)
            require(rejected.status == "not_accepted" and rejected.report["outcome"] == "fail" and rejected.artifact is None,
                    "Altered material retained acceptance: " + name)
            structure = rejected.report["structure"]
            codes = [row["code"] for row in structure["diagnostics"]]
            specific = {"changed-cds": "complete_product_spelling_mismatch",
                "changed-chemistry": "original_full_chemistry_mismatch",
                "swapped-members": "original_exact_member_order",
                "missing-member": "missing_delivered_member", "extra-member": "original_exact_member_order"}
            if name in specific: require(specific[name] in codes, "Material negative failed for another reason: " + name)
            if name in ("changed-utr", "foreign-repinned"):
                require(structure["content_outcome"] == "fail" and structure["structural_outcome"] == "pass"
                    and structure["content_reconstruction"]["diagnostics"] == ["fail:content:inventory"],
                    "Destination-repinned content did not reach independent reconstruction")
            retained = {"candidate": candidate, **result_record(rejected)}
            if name == "foreign-repinned":
                foreign_request, foreign_candidate = foreign_pair(request, built.candidate)
                retained.update(foreign_original=foreign_request, foreign_candidate=foreign_candidate)
            observe(name, retained)
        adversaries = {name: deepcopy(request) for name in NEGATIVE_DIAGNOSTICS}
        adversaries["foreign-original"]["source_authority"]["project_context"]["title"] += " changed original"
        adversaries["request-work-exhaustion"]["budgets"]["max_work"] = 1
        adversaries["domain-work-exhaustion"]["operating_domain"]["limits"]["max_work"] = 1
        adversaries["report-byte-exhaustion"]["budgets"]["max_report_bytes"] = 1
        for name, altered in adversaries.items():
            candidate = deepcopy(built.candidate)
            if name != "foreign-original": candidate["request_fingerprint"] = digest(altered)
            operation = CONSTRUCT if name == "verifier-production-role" else CHECK
            payload = {"request": altered} if operation == CONSTRUCT else {"request": altered, "candidate": candidate}
            try: transports["verify"].call(operation, payload)
            except CoreRejected as error:
                response = error.response; status, code = NEGATIVE_DIAGNOSTICS[name]
                require(response.result is None and response.status == status and [row.code for row in response.diagnostics] == [code], "Negative rejected for unexpected reason: " + name)
                observe(name, {"payload": payload, "operation": operation, "status": response.status, "executable": response.executable,
                    "diagnostics": [{"code": row.code, "message": row.message, "path": row.path} for row in response.diagnostics]})
            else: raise AssertionError("Native negative accepted: " + name)
        destination = sidecars/"preserved.zip"; destination.write_bytes(b"independent previous output\n"); before = file_pin(destination)
        class Capture:
            result = None
            def publish_material(self, *args, **kwargs):
                self.result = clients["verify"].publish_material(*args, **kwargs)
                return self.result
        capture = Capture()
        try: sdk.publish_material(request, candidate=mutants["changed-utr"], client=capture, output=destination, replace=True)
        except CoreProtocolError:
            require(capture.result is not None and capture.result.status == "not_accepted" and file_pin(destination) == before, "Rejected publication changed prior output")
            observe("rejected-publication", {"candidate": mutants["changed-utr"], **result_record(capture.result), "before": before, "after": file_pin(destination)})
        else: raise AssertionError("Rejected structural pair was published")
        try: sdk.publish_material(request, candidate=built.candidate, client=clients["verify"], output=destination, replace=True, cancelled=lambda: True)
        except CoreCancelled:
            require(file_pin(destination) == before, "Prelaunch cancellation changed previous output")
            observe("prelaunch-cancellation", {"status": "cancelled", "phase": "before_native_launch", "accepted_result": None, "before": before, "after": file_pin(destination)})
        else: raise AssertionError("Precancelled publication succeeded")
        after_readback = False; readback = sdk._verify_staged
        def complete_readback(*args):
            nonlocal after_readback
            readback(*args); after_readback = True
        capture = Capture()
        with patch.object(sdk, "_verify_staged", side_effect=complete_readback):
            try: sdk.publish_material(request, candidate=built.candidate, client=capture, output=destination, replace=True, cancelled=lambda: after_readback)
            except CoreCancelled:
                require(after_readback and file_pin(destination) == before, "Late cancellation committed partial pair")
                observe("after-readback-cancellation", {"status": "cancelled", "phase": "after_staged_readback_before_atomic_commit", **result_record(capture.result), "before": before, "after": file_pin(destination)})
            else: raise AssertionError("Cancelled staged pair was committed")
        capture = Capture()
        with patch.object(sdk.os, "fsync", side_effect=OSError("injected staged failure")):
            try: sdk.publish_material(request, candidate=built.candidate, client=capture, output=destination, replace=True)
            except OSError:
                require(file_pin(destination) == before, "Staged IO failure committed partial output")
                observe("staged-io-failure", {"status": "injected_io_failure", **result_record(capture.result), "before": before, "after": file_pin(destination)})
            else: raise AssertionError("Injected staged IO failure did not fail")
        require(not list(sidecars.glob(".controlled-material-*")), "Interrupted publication leaked staged output")
        require(tuple(row["name"] for row in receipt["observations"]) == OBSERVATIONS, "Incomplete material campaign")
        final_imports = imported_modules(args.require_installed)
        require(all(final_imports["modules"].get(name) == pin for name, pin in receipt["imports"]["modules"].items()), "SDK authority changed during execution")
        receipt["imports"] = final_imports
        require({role: file_pin(path, 256 * 1024 * 1024) for role, path in binaries.items()} == binary_pins
                and {name: file_pin(ROOT/path, 4 * 1024 * 1024) for name, path in FIXTURES.items()} == fixture_pins,
                "Original fixture or native identity changed during execution")
        require(file_pin(__file__) == receipt["campaign_script"] and source_identity() == identity, "Campaign source or hosted identity changed")
        receipt["status"] = "pass"
    except Exception as error:
        receipt.update(status="failed", error=f"{type(error).__name__}: {error}"); raise
    finally: save()
    print(json.dumps({"status": "pass", "observations": len(OBSERVATIONS), "receipt": str(output), "installed": args.require_installed}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", required=True); parser.add_argument("--verify", required=True)
    parser.add_argument("--core-sha256"); parser.add_argument("--verify-sha256")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-installed", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__": main()
