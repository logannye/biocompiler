"""Reuse authenticated installed wheels and compare four complete assurance runs.

Existing prebuilt gates remain mandatory. This additive companion neither
installs packages nor builds binaries, and comparison never executes native code.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import platform
import re

try:
    from . import check_policy_material_prebuilt as base
    from . import check_policy_grounded_helper_prebuilt as ownership_gate
    from . import check_policy_quantitative_assurance as campaign
except ImportError:
    import check_policy_material_prebuilt as base
    import check_policy_grounded_helper_prebuilt as ownership_gate
    import check_policy_quantitative_assurance as campaign

ROOT = Path(__file__).resolve().parents[1]
FOLDER = "quantitative-assurance-installed"
RECEIPT = "quantitative-assurance.json"
SCHEMA = "biocompiler.policy_quantitative_assurance_prebuilt_companion.v0.1"
SCOPE = "supplied_installed_quantitative_assurance_separate_from_existing_release_gates"
SLOTS = {(system, machine, minor) for system, machine in (("Linux", "x86_64"), ("Darwin", "arm64")) for minor in ("3.11", "3.14")}
require, pin, read, write = base.require, base.pin, base.read_json, base.write_json


def authorities(args, identity, count):
    require(len(args.platform_root) == len(args.material_authority) == count, "One complete authority is required per native platform")
    candidate, sdk_entries, stamp = base.candidate_authority(args.release_candidate, args.sdk, identity)
    native = {}
    for root, material in zip(args.platform_root, args.material_authority):
        value = base.platform_authority(root, material, candidate, identity)
        key = base.build.TARGETS[value["target"]][:2]
        require(key not in native, "Duplicate assurance platform authority")
        native[key] = value
    return candidate, sdk_entries, stamp, native


def argv(checkout, origin, ownership):
    files = ownership["files"]
    return [str(origin / "env/bin/python"), "-B", str(checkout / "tools/check_policy_quantitative_assurance.py"),
        "--core", files["bin/biocompiler-core"]["path"], "--verify", files["bin/biocompiler-verify"]["path"],
        "--core-sha256", files["bin/biocompiler-core"]["sha256"], "--verify-sha256", files["bin/biocompiler-verify"]["sha256"],
        "--require-installed", "--output", str(origin / FOLDER / RECEIPT)]


def run(args):
    identity = base.hosted_identity()
    base.selected_target()
    candidate, sdk_entries, stamp, native = authorities(args, identity, 1)
    require(len(args.slot) == 1, "Launch requires one authenticated existing slot")
    directory = args.slot[0]
    slot, origin, ownership = ownership_gate.owned_slot(directory, identity, candidate, sdk_entries, stamp, native, args)
    require(directory == origin and slot == (platform.system(), platform.machine(), f"{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}"),
            "Cannot execute a relocated or foreign installed slot")
    output = directory / FOLDER
    require(not output.exists(), "Assurance output must be fresh")
    output.mkdir()
    baseline = pin(directory / "prebuilt.json")
    site = Path(ownership["package_root"]).parent
    def unchanged():
        require(base.hosted_identity() == identity and pin(directory / "prebuilt.json") == baseline, "Original installation identity changed")
        base.snapshot_entries(site, sdk_entries)
        base.snapshot_entries(site, native[slot[:2]]["entries"])
    unchanged()
    command = base.command(output, "quantitative-assurance", argv(ROOT, origin, ownership), cwd=origin / "cwd", environment=base.safe_environment())
    receipt = read(output / RECEIPT)
    expected_binaries = {role: {"sha256": ownership["files"]["bin/biocompiler-" + role]["sha256"],
        "bytes": len(native[slot[:2]]["entries"]["biocompiler_core/bin/biocompiler-" + role][0])} for role in ("core", "verify")}
    validate_campaign(output / RECEIPT, identity, slot, expected_binaries, sdk_entries, ownership["sdk_root"])
    require(receipt["run_attempt"] == identity["run_attempt"], "Campaign belongs to another invocation attempt")
    unchanged()
    result = {"schema_version": SCHEMA, "status": "pass", **identity, "scope": SCOPE, "slot": list(slot),
        "origin": str(origin), "checkout": str(ROOT), "baseline": baseline,
        "artifacts": base.authority_receipt(args.release_candidate, args.sdk, stamp, native[slot[:2]]),
        "command": command, "receipt": pin(output / RECEIPT)}
    write(output / "companion.json", result)
    return result


def validate_result(raw, operation, role, payload):
    from biocompiler.core_client import CoreResponse
    from biocompiler.core_policy_quantitative_assurance import _result
    response = CoreResponse("quantitative-assurance-comparison", operation, "ok", raw, (), role, "comparison")
    return _result(response, payload)


def validate_campaign(path, identity, slot, binaries, sdk_entries, package):
    """Rehash all originals/sidecars and validate every complete result binding."""
    value = read(path)
    require(type(value) is dict and set(value) == {"schema_version", "status", "scope", *identity, "platform", "machine", "python", "installed", "binaries", "inputs", "imports", "campaign_script", "observations", "empirical_function"}
        and value["schema_version"] == "biocompiler.policy_quantitative_assurance_campaign.v0.1" and value["status"] == "pass"
        and value["scope"] == "fresh_native_quantitative_assurance_sdk_with_exact_rna" and value["installed"] is True
        and value["empirical_function"] == "unassessed" and base.prior_attempt(value, identity), "Stale, partial or promoted assurance campaign")
    require(type(value["python"]) is str and re.fullmatch(r"3\.(11|14)\.[0-9]+", value["python"])
        and (value["platform"], value["machine"], ".".join(value["python"].split(".")[:2])) == slot and slot in SLOTS,
        "Assurance runtime slot changed")
    originals = {name: campaign.file_pin(ROOT / relative, 4 * 1024 * 1024) for name, relative in campaign.FIXTURES.items()}
    require(value["binaries"] == binaries and value["inputs"] == originals
        and value["campaign_script"] == campaign.file_pin(ROOT / "tools/check_policy_quantitative_assurance.py"), "Native, script or complete original authority changed")
    imports = value["imports"]
    require(type(imports) is dict and set(imports) == {"package", "modules", "record_verified"} and imports["record_verified"] is True
        and imports["package"] == package and type(imports["modules"]) is dict and bool(imports["modules"]), "Installed import ownership is missing")
    required = {"biocompiler", "biocompiler.core_client", "biocompiler.core_policy_quantitative_assurance",
        "biocompiler.policy.approximation", "biocompiler.policy.realization_evidence", "biocompiler.policy.quantitative_assurance"}
    require(required <= set(imports["modules"]), "Required installed SDK modules were not exercised")
    for name, row in imports["modules"].items():
        require(name == "biocompiler" or name.startswith("biocompiler."), "Foreign recorded import")
        relative = name.replace(".", "/")
        matches = [path for path in (relative + ".py", relative + "/__init__.py") if path in sdk_entries]
        require(len(matches) == 1 and type(row) is dict and set(row) == {"path", "sha256", "bytes"}, "Ambiguous or malformed installed module")
        member = matches[0]
        require(row == {"path": str(Path(package).parent / member), "sha256": base.build.sha(sdk_entries[member][0]), "bytes": len(sdk_entries[member][0])},
                "Imported file differs from the original owned SDK wheel")
    rows = value["observations"]
    require(type(rows) is list and [row.get("name") for row in rows if type(row) is dict] == list(campaign.OBSERVATIONS)
        and len(rows) == len(campaign.OBSERVATIONS), "Incomplete or reordered assurance observations")
    found, retained = {}, []
    directory = path.with_suffix("")
    require(directory.is_dir() and not directory.is_symlink(), "Retained assurance sidecar directory is redirected")
    for row in rows:
        require(set(row) == {"name", "path", "sha256", "bytes"} and row["path"] == directory.name + "/" + row["name"] + ".json", "Unsafe assurance sidecar path")
        target = path.parent / row["path"]
        require(campaign.file_pin(target) == {key: row[key] for key in ("sha256", "bytes")}, "Retained assurance sidecar bytes changed")
        found[row["name"]] = read(target)
        retained.append((target, campaign.file_pin(target)))
    require(set(directory.iterdir()) == {target for target, _ in retained}, "Extra or absent assurance sidecars")
    fixtures = {name: read(ROOT / relative) for name, relative in campaign.FIXTURES.items()}
    from biocompiler.core_client import encode_json
    digest = lambda raw: base.build.sha(encode_json(raw))
    require(fixtures["evidence"]["material_fixture_fingerprint"] == digest(fixtures["network"]), "Evidence original detached from material fixture")
    cases = campaign.original_cases(fixtures)
    for name, original, limits, sequence in cases:
        require(found[name + "-originals"] == {"request": original, "limits": limits, "expected_sequence": sequence}, "Retained original authority differs")
        compiled, checked, replayed, exported = [found[name + "-" + suffix] for suffix in ("compile", "check", "replay", "export")]
        for suffix, raw, role in (("compile", compiled, "core"), ("check", checked, "verify"), ("replay", replayed, "verify"), ("export", exported, "verify")):
            payload = {"request": original, "limits": limits}
            if suffix != "compile": payload["candidate"] = checked["candidate"]
            if suffix == "replay": payload["report"] = checked
            validate_result(raw, suffix + "-policy-quantitative-assurance", role, payload)
        require(compiled == checked == replayed and exported["report"]["export_permitted"] is True, "Complete independent compile/check/replay differs")
        require("".join(line for line in exported["artifact"]["fasta"].splitlines() if not line.startswith(">")) == sequence, "Exact RNA differs from independent literal")
        if name == "evidence":
            require(checked["report"]["realization_evidence"]["status"] == "supported", "Supplied evidence compatibility disappeared")
        else:
            require(checked["report"]["approximation"]["composition"]["maximum_error"]["numerator"] == ("1" if name == "approximation" else "0"), "Literal model error changed")
    original, limits = cases[0][1:3]
    from copy import deepcopy
    tight = deepcopy(original)
    tight["approximation"]["maximum_error"]["numerator"] = "0"
    failed = found["insufficient-error-bound"]
    validate_result(failed, "check-policy-quantitative-assurance", "verify", {"request": tight, "candidate": found["approximation-check"]["candidate"], "limits": limits})
    require(failed["report"]["export_permitted"] is False and failed["report"]["approximation"]["outcome"] == "fail"
        and failed["report"]["material"]["status"] == "checked_component_material", "Failed approximation changed exact material or export gate")
    missing = deepcopy(cases[1][1])
    missing["realization_evidence"].update(dossier=None, require_compatibility=True)
    raw = found["missing-gated-evidence"]
    validate_result(raw, "check-policy-quantitative-assurance", "verify", {"request": missing, "candidate": found["evidence-check"]["candidate"], "limits": cases[1][2]})
    require(raw["report"]["export_permitted"] is False and raw["report"]["realization_evidence"]["status"] == "unassessed"
        and raw["report"]["material"]["status"] == "checked_component_material", "Missing dossier did not preserve separate gate")
    for name, operation in (("cumulative-budget", "check"), ("failed-bound-export", "export"), ("retained-pass-mutation", "replay"), ("verifier-production-role", "compile")):
        row = found[name]
        status, code = campaign.NEGATIVE_DIAGNOSTICS[name]
        require(type(row) is dict and set(row) == {"status", "operation", "executable", "diagnostics"}
            and row["status"] == status and row["operation"] == operation + "-policy-quantitative-assurance"
            and row["executable"] == "verify" and type(row["diagnostics"]) is list and bool(row["diagnostics"])
            and all(type(item) is dict and set(item) == {"code", "message"} and all(type(item[key]) is str and item[key] for key in item) for item in row["diagnostics"]),
            "Native negative control lost its complete rejection")
        require([item["code"] for item in row["diagnostics"]] == [code], "Negative control failed for another reason")
    require(all(campaign.file_pin(target) == expected for target, expected in retained), "Evidence changed during independent comparison")
    return found


def check_command(output, value, origin, ownership):
    rows = read(output / "commands.json")
    require(type(rows) is list and rows == [value["command"]], "Assurance command census differs")
    row = rows[0]
    baseline = read(output.parent / "prebuilt.json")
    require(value["checkout"] == baseline["checkout_root"] and baseline["commands"] == pin(output.parent / "commands.json"), "Preserved installation command authority changed")
    require(set(row) == {"name", "argv", "cwd", "executable", "returncode", "timeout", "overflow", "environment", "logs"}
        and row["name"] == "quantitative-assurance" and row["argv"] == argv(Path(value["checkout"]), origin, ownership)
        and row["cwd"] == str(origin / "cwd") and type(row["returncode"]) is int and row["returncode"] == 0
        and row["timeout"] is False and row["overflow"] is False and row["environment"] == "scrubbed_loaders", "Actual installed assurance command changed")
    require(set(row["logs"]) == {"logs/quantitative-assurance.stdout.log", "logs/quantitative-assurance.stderr.log"}
        and all(pin(output / name, base.MAX_LOG) == expected for name, expected in row["logs"].items()), "Retained command logs changed")
    before = [old for old in read(output.parent / "commands.json") if old["argv"][0] == row["argv"][0]]
    require(before and all(old["executable"] == row["executable"] for old in before), "Installed interpreter changed since preserved gate")


def compare(args):
    identity = base.hosted_identity()
    candidate, sdk_entries, stamp, native = authorities(args, identity, 2)
    require(set(native) == {("Linux", "x86_64"), ("Darwin", "arm64")} and len(args.slot) == 4, "Exactly four installed slots on both platforms are required")
    found, baseline, attempts, retained = set(), None, [], []
    def retain(path, maximum=base.MAX_JSON):
        retained.append((path, maximum, pin(path, maximum)))
    retain(args.sdk, base.release_check.MAX_ARCHIVE)
    retain(args.release_candidate)
    retain(args.sdk.parent / "hosted-identity.json")
    for root in args.platform_root:
        for name in (*base.artifact_files(root, "native"), "hosted-identity.json"):
            retain(root / name, base.release_check.MAX_ARCHIVE)
    for directory in args.slot:
        slot, origin, ownership = ownership_gate.owned_slot(directory, identity, candidate, sdk_entries, stamp, native, args)
        require(slot not in found, "Duplicate installed assurance slot")
        output = directory / FOLDER
        value = read(output / "companion.json")
        require(set(value) == {"schema_version", "status", *identity, "scope", "slot", "origin", "checkout", "baseline", "artifacts", "command", "receipt"}
            and base.prior_attempt(value, identity) and value["schema_version"] == SCHEMA and value["status"] == "pass" and value["scope"] == SCOPE
            and value["slot"] == list(slot) and value["origin"] == str(origin) and Path(value["checkout"]).is_absolute()
            and value["baseline"] == pin(directory / "prebuilt.json") and value["receipt"] == pin(output / RECEIPT)
            and value["artifacts"] == base.authority_receipt(args.release_candidate, args.sdk, stamp, native[slot[:2]]), "Stale or altered assurance companion")
        check_command(output, value, origin, ownership)
        binaries = {role: {"sha256": base.build.sha(native[slot[:2]]["entries"]["biocompiler_core/bin/biocompiler-" + role][0]),
            "bytes": len(native[slot[:2]]["entries"]["biocompiler_core/bin/biocompiler-" + role][0])} for role in ("core", "verify")}
        receipt = read(output / RECEIPT)
        require(receipt["run_attempt"] == value["run_attempt"], "Campaign and launch attempt differ")
        complete = validate_campaign(output / RECEIPT, identity, slot, binaries, sdk_entries, ownership["sdk_root"])
        require(baseline is None or baseline == complete, "Complete deterministic assurance observations differ across platforms or Python versions")
        baseline = complete
        for path in (output / "companion.json", output / "commands.json", output / RECEIPT, directory / "prebuilt.json", directory / "commands.json",
                directory / "evidence/ownership-before.json", directory / "evidence/ownership-after.json"):
            retain(path)
        for name in value["command"]["logs"]: retain(output / name, base.MAX_LOG)
        for row in receipt["observations"]: retain(output / row["path"], 32 * 1024 * 1024)
        attempts.append({"slot": list(slot), "run_attempt": value["run_attempt"], "companion": pin(output / "companion.json")})
        found.add(slot)
    require(found == SLOTS and all(pin(path, maximum) == expected for path, maximum, expected in retained), "Missing slots or changed retained authority")
    require(args.output is not None and not args.output.exists(), "Comparison output must be fresh")
    from biocompiler.core_client import encode_json
    result = {"schema_version": SCHEMA, "status": "pass", **identity, "scope": SCOPE, "slots": sorted(attempts, key=lambda row: row["slot"]),
        "observations": list(campaign.OBSERVATIONS), "complete_observations_sha256": base.build.sha(encode_json(baseline, limit=128 * 1024 * 1024)),
        "empirical_function": "unassessed"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write(args.output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "compare"))
    for name in ("sdk", "release-candidate"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("platform-root", "material-authority", "slot"):
        parser.add_argument("--" + name, type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    for key, value in vars(args).items():
        if isinstance(value, Path): setattr(args, key, value.absolute())
        elif isinstance(value, list): setattr(args, key, [path.absolute() for path in value])
    print((run(args) if args.mode == "run" else compare(args))["status"])


if __name__ == "__main__":
    main()
