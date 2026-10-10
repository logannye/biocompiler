"""Additive installed prerequisite campaign over the existing exact owned wheels.

The original prebuilt campaigns and their receipts remain separate mandatory
gates. This companion reuses their installed environment, authenticates complete
wheel bytes, and adds its own commands, observations and four-runtime comparison.
Native execution is hosted-only; retained-evidence comparison is inert.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import platform
import sys

try:
    from . import check_policy_material_prebuilt as base
    from . import check_policy_prerequisite_fixture as fixture_tool
    from . import check_policy_prerequisite_material_installed as campaign
except ImportError:
    import check_policy_material_prebuilt as base
    import check_policy_prerequisite_fixture as fixture_tool
    import check_policy_prerequisite_material_installed as campaign

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "biocompiler.policy_prerequisite_prebuilt_companion.v0.1"
SCOPE = "supplied_installed_prerequisite_profile_separate_from_original_release_gates"
FOLDER = "prerequisite-installed"
require, pin, read, write = base.require, base.pin, base.read_json, base.write_json


def authorities(args, identity, count):
    require(len(args.platform_root) == len(args.material_authority) ==
            len(args.prerequisite_fixture) == len(args.prerequisite_provenance) == count,
            "Prerequisite campaign requires exactly one complete authority per native platform")
    candidate, sdk_entries, stamp = base.candidate_authority(args.release_candidate, args.sdk, identity)
    native, originals = {}, {}
    for root, material in zip(args.platform_root, args.material_authority):
        value = base.platform_authority(root, material, candidate, identity)
        key = base.build.TARGETS[value["target"]][:2]
        require(key not in native, "Duplicate prerequisite native platform")
        native[key] = value
    for fixture, provenance in zip(args.prerequisite_fixture, args.prerequisite_provenance):
        value = read(provenance)
        declared = value.get("platform", {})
        key = declared.get("system"), declared.get("machine")
        require(key in native and key not in originals, "Duplicate or foreign prerequisite original platform")
        hashes = binary_hashes(native[key])
        checked = fixture_tool.validate(ROOT, fixture, provenance, identity=identity,
            native_sha256={role: hashes["biocompiler-" + role] for role in ("core", "verify")}, expected_platform=key)
        originals[key] = {"fixture": fixture, "provenance": provenance, "sources": checked["sources"],
                          "pins": {"fixture": pin(fixture), "provenance": pin(provenance)}}
    require(set(originals) == set(native) and len({row["pins"]["fixture"]["sha256"] for row in originals.values()}) == 1,
            "Prerequisite originals are missing or differ across native builds")
    require(all(row["sources"] == next(iter(originals.values()))["sources"] for row in originals.values()),
            "Prerequisite source snapshots differ across native builds")
    return candidate, sdk_entries, stamp, native, originals


def binary_hashes(native):
    return {"biocompiler-" + role: base.build.sha(native["entries"]["biocompiler_core/bin/biocompiler-" + role][0])
            for role in ("core", "verify")}


def owned_slot(directory, identity, candidate, sdk_entries, stamp, native, args):
    """Bind the installed environment to supplied wheels, not a child's hashes."""
    baseline = read(directory / "prebuilt.json")
    require(base.prior_attempt(baseline, identity) and baseline.get("status") == "pass"
            and baseline.get("schema_version") == base.RESEARCHER_SCHEMA,
            "Prerequisite integration requires the preserved researcher prebuilt campaign")
    slot = base.consumer.slot(baseline)
    require(slot in campaign.component.SLOTS and slot[:2] in native, "Foreign prerequisite installed runtime")
    origin = Path(baseline["output_root"])
    require(origin.is_absolute() and not origin.is_relative_to(ROOT), "Installed prerequisite origin belongs to checkout")
    require(baseline["commands"] == pin(directory / "commands.json") and baseline["source_pins"] == base.source_pins(),
            "Preserved installation commands or sources changed")
    before = read(directory / "evidence/ownership-before.json")
    after = read(directory / "evidence/ownership-after.json")
    require(before == after and all(after["runtime"][key] == baseline[key]
            for key in ("system", "machine", "python_version")), "Preserved ownership lifecycle differs")
    require(all(baseline["evidence"]["evidence/" + name + ".json"] == pin(directory / "evidence" / (name + ".json"))
            for name in ("ownership-before", "ownership-after")), "Ownership evidence differs from its original receipt")
    base.check_ownership(after, sdk_entries, native[slot[:2]], candidate, origin / "env")
    require(baseline["artifacts"] == base.authority_receipt(args.release_candidate, args.sdk, stamp, native[slot[:2]]),
            "Prerequisite environment does not belong to supplied wheel authority")
    return slot, origin, after["ownership"]


def argv(checkout, origin, ownership, fixture, provenance):
    files = ownership["files"]
    return [str(origin / "env/bin/python"), "-B", str(checkout / "tools/check_policy_prerequisite_material_installed.py"),
        "--fixture", str(fixture), "--fixture-provenance", str(provenance),
        "--core", files["bin/biocompiler-core"]["path"], "--verify", files["bin/biocompiler-verify"]["path"],
        "--core-sha256", files["bin/biocompiler-core"]["sha256"],
        "--verify-sha256", files["bin/biocompiler-verify"]["sha256"],
        "--output", str(origin / FOLDER / "evidence" / campaign.RECEIPT)]


def run(args):
    identity = base.hosted_identity()
    base.selected_target()  # Enforce supported hosted Python/platform before launch.
    candidate, sdk_entries, stamp, native, originals = authorities(args, identity, 1)
    require(len(args.slot) == 1, "Prerequisite launch needs one preserved installed slot")
    directory = args.slot[0]
    slot, origin, ownership = owned_slot(directory, identity, candidate, sdk_entries, stamp, native, args)
    require(directory == origin and slot == (platform.system(), platform.machine(), f"{sys.version_info.major}.{sys.version_info.minor}"),
            "Prerequisite launch cannot execute a relocated or foreign installed environment")
    authority = originals[slot[:2]]
    expected_fixture = ROOT / "artifacts" / ("core-" + native[slot[:2]]["target"]) / "prerequisite-originals"
    require(authority["fixture"] == expected_fixture / "originals.json"
            and authority["provenance"] == expected_fixture / "provenance.json", "Prerequisite fixture path differs from the fixed CI recipe")
    output = directory / FOLDER
    require(not output.exists(), "Prerequisite companion output must be fresh")
    output.mkdir(); (output / "evidence").mkdir()
    baseline_pin = pin(directory / "prebuilt.json")
    site = Path(ownership["package_root"]).parent
    def unchanged():
        require(base.hosted_identity() == identity and pin(directory / "prebuilt.json") == baseline_pin,
                "Prerequisite hosted or preserved original campaign identity changed")
        base.snapshot_entries(site, sdk_entries)
        base.snapshot_entries(site, native[slot[:2]]["entries"])
    unchanged()
    command = base.command(output, "prerequisite-material", argv(ROOT, origin, ownership, authority["fixture"], authority["provenance"]),
                           cwd=origin / "cwd", environment=base.safe_environment())
    receipt = read(output / "evidence" / campaign.RECEIPT)
    require(receipt["status"] == "pass" and receipt["schema_version"] == campaign.SCHEMA
            and all(receipt[key] == identity[key] for key in identity)
            and base.consumer.slot(receipt) == slot and receipt["package"] == ownership["sdk_root"]
            and receipt["binary_sha256"] == binary_hashes(native[slot[:2]])
            and receipt["scope"] == campaign.SCOPE and receipt["python_semantic_authority"] == "forbidden",
            "Installed prerequisite child changed identity, owned package, native authority or scope")
    unchanged()
    result = {"schema_version": SCHEMA, "status": "pass", **identity, "scope": SCOPE,
        "slot": list(slot), "origin": str(origin), "checkout": str(ROOT), "baseline": baseline_pin,
        "artifacts": base.authority_receipt(args.release_candidate, args.sdk, stamp, native[slot[:2]]),
        "originals": authority["pins"], "command": command,
        "receipt": pin(output / "evidence" / campaign.RECEIPT)}
    write(output / "companion.json", result)
    return result


def check_command(output, value, origin, ownership):
    rows = read(output / "commands.json")
    require(type(rows) is list and rows == [value["command"]], "Prerequisite command census differs")
    row = rows[0]
    baseline = read(output.parent / "prebuilt.json")
    require(value["checkout"] == baseline["checkout_root"] and baseline["commands"] == pin(output.parent / "commands.json"),
            "Prerequisite checkout or preserved installation ledger differs")
    target = next(name for name, spec in base.build.TARGETS.items() if spec[:2] == tuple(value["slot"][:2]))
    original = Path(value["checkout"]) / "artifacts" / ("core-" + target) / "prerequisite-originals"
    expected = argv(Path(value["checkout"]), origin, ownership, original / "originals.json", original / "provenance.json")
    require(set(row) == {"name", "argv", "cwd", "executable", "returncode", "timeout", "overflow", "environment", "logs"}
            and row["name"] == "prerequisite-material" and row["argv"] == expected and row["cwd"] == str(origin / "cwd")
            and type(row["returncode"]) is int and row["returncode"] == 0 and row["timeout"] is False
            and row["overflow"] is False and row["environment"] == "scrubbed_loaders", "Prerequisite execution recipe differs")
    require(set(row["logs"]) == {"logs/prerequisite-material.stdout.log", "logs/prerequisite-material.stderr.log"}
            and all(pin(output / name, base.MAX_LOG) == declared for name, declared in row["logs"].items()),
            "Prerequisite command logs differ")
    old_rows = read(output.parent / "commands.json")
    interpreter = [old for old in old_rows if old["argv"][0] == row["argv"][0]]
    require(interpreter and all(old["executable"] == row["executable"] for old in interpreter),
            "Prerequisite interpreter differs from the preserved installation lifecycle")


def compare(args):
    identity = base.hosted_identity()
    candidate, sdk_entries, stamp, native, originals = authorities(args, identity, 2)
    require(set(native) == {("Linux", "x86_64"), ("Darwin", "arm64")} and len(args.slot) == 4,
            "Prerequisite comparison requires both native platforms and four installed slots")
    found, receipts, attempts, retained = set(), [], [], []
    def retain(path, maximum=base.MAX_JSON):
        retained.append((path, maximum, pin(path, maximum)))
    retain(args.sdk, base.release_check.MAX_ARCHIVE)
    retain(args.release_candidate)
    retain(args.sdk.parent / "hosted-identity.json")
    for root in args.platform_root:
        for name in (*base.artifact_files(root, "native"), "hosted-identity.json"):
            retain(root / name, base.release_check.MAX_ARCHIVE)
    for directory in args.slot:
        slot, origin, ownership = owned_slot(directory, identity, candidate, sdk_entries, stamp, native, args)
        require(slot not in found, "Duplicate installed prerequisite runtime")
        output = directory / FOLDER
        value = read(output / "companion.json")
        require(set(value) == {"schema_version", "status", *identity, "scope", "slot", "origin", "checkout", "baseline",
            "artifacts", "originals", "command", "receipt"} and base.prior_attempt(value, identity)
            and value["schema_version"] == SCHEMA and value["status"] == "pass" and value["scope"] == SCOPE
            and value["slot"] == list(slot) and value["origin"] == str(origin) and Path(value["checkout"]).is_absolute()
            and value["baseline"] == pin(directory / "prebuilt.json") and value["originals"] == originals[slot[:2]]["pins"]
            and value["artifacts"] == base.authority_receipt(args.release_candidate, args.sdk, stamp, native[slot[:2]])
            and value["receipt"] == pin(output / "evidence" / campaign.RECEIPT), "Stale or altered prerequisite companion")
        check_command(output, value, origin, ownership)
        for path in (output / "companion.json", output / "commands.json", directory / "prebuilt.json",
                     directory / "commands.json", directory / "evidence/ownership-before.json",
                     directory / "evidence/ownership-after.json"):
            retain(path)
        for name in value["command"]["logs"]:
            retain(output / name, base.MAX_LOG)
        receipt_path = output / "evidence" / campaign.RECEIPT
        receipt = read(receipt_path)
        require(receipt["package"] == ownership["sdk_root"] and receipt["run_attempt"] == value["run_attempt"],
                "Prerequisite observation package or attempt differs from companion")
        receipts.append(receipt_path); found.add(slot)
        attempts.append({"slot": list(slot), "companion": pin(output / "companion.json"), "run_attempt": value["run_attempt"]})
    require(found == campaign.component.SLOTS, "Missing installed prerequisite runtime")
    sources = next(iter(originals.values()))["sources"]
    checked = campaign.compare_installed(receipts, next(iter(originals.values()))["fixture"], identity,
        {key: binary_hashes(value) for key, value in native.items()}, expected_sources=sources,
        fixture_provenances={key: value["provenance"] for key, value in originals.items()})
    require(all(pin(path, maximum) == expected for path, maximum, expected in retained),
            "Prerequisite companion, installation evidence or supplied wheel authority changed during comparison")
    require(args.output is not None and not args.output.exists(), "Prerequisite comparison output must be fresh")
    result = {"schema_version": SCHEMA, "status": "pass", **identity, "scope": SCOPE,
              "slots": sorted(attempts, key=lambda row: row["slot"]), "prerequisite_material": checked}
    args.output.parent.mkdir(parents=True, exist_ok=True); write(args.output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "compare"))
    for name in ("sdk", "release-candidate"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("platform-root", "material-authority", "prerequisite-fixture", "prerequisite-provenance", "slot"):
        parser.add_argument("--" + name, type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    for key, value in vars(args).items():
        if isinstance(value, Path): setattr(args, key, value.absolute())
        elif isinstance(value, list): setattr(args, key, [path.absolute() for path in value])
    result = run(args) if args.mode == "run" else compare(args)
    print(result["status"])


if __name__ == "__main__":
    main()
