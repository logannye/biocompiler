"""Check the RC1 declarative corpus without executing a biological or native model.

This checks closed representation, complete named-case accounting and claim
boundaries. Expected verdicts remain independently authored specifications. This
tool never computes those verdicts and cannot establish semantic acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROFILE = Path("protocol/controlled-composition-profile-v0.1.json")
CORPUS = Path("data/controlled_composition_v01/acceptance-cases.json")
MAX_BYTES = 2 * 1024 * 1024
MAX_NODES = 100_000
MAX_TICK = 10_000
MEMBERS = ("rna_a", "rna_b", "protein_a", "protein_b")
EVIDENCE = ("valid", "missing", "stale", "invalid", "conflicting")
BANDS = ("background", "active")
DEADLINES = {"onset_ticks", "cessation_ticks", "reactivation_ticks"}
PERTURBATION_OPERATIONS = {
    "candidate_activity": ("replace",),
    "candidate_state": ("clear_executor_controller_on_encounter_reset",),
    "candidate_material_members": ("replace",),
    "candidate": ("substitute", "substitute_and_repin_complete_local_authority"),
    "saved_report": ("substitute",),
    "bundle": ("substitute",),
    "original_controller": ("replace",),
    "deployment.same_recipient": ("replace",),
    "source.activity_endpoint": ("replace",),
    "source.initial_activity": ("replace",),
    "verification_domain.suffix_ticks": ("replace",),
    "verification_budget.max_work": ("replace",),
}
REQUIRED_CASES = (
    "reversible_on_off_on", "response_before_deadline", "constant_on", "forever_off",
    "irreversible_stop", "antigen_absent_quiet", "antigen_absent_activation",
    "controller_disabled_quiet", "both_inputs_disabled_quiet", "antigen_missing_evidence",
    "controller_missing_evidence", "protein_missing_evidence", "activity_missing_evidence",
    "controller_stale_evidence", "controller_invalid_evidence", "controller_conflicting_evidence",
    "protein_loss_and_recovery", "rna_loss_protein_persistence", "encounter_reset_recovery",
    "reset_during_onset", "wrong_scope_controller_reset", "encounter_end_and_restart",
    "restoration_during_cessation", "late_onset", "late_cessation", "late_reactivation",
    "tighter_source_deadline", "incomplete_suffix", "missing_material_member",
    "extra_material_member", "different_recipient", "foreign_candidate",
    "repinned_foreign_candidate", "foreign_report", "foreign_bundle",
    "changed_original_controller", "unsupported_killing_endpoint", "unsupported_initial_active",
    "work_exhaustion", "antigen_loss_and_recovery", "repeated_loss_does_not_postpone_stop",
)


class FoundationError(ValueError):
    """An RC1 representation, inventory or claim boundary is inconsistent."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise FoundationError(message)


def closed(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    require(type(value) is dict and set(value) == keys, label + ": unexpected or missing fields")
    return value


def text(value: Any, label: str) -> str:
    require(type(value) is str and 0 < len(value.encode("utf-8")) <= 4096,
            label + ": expected bounded nonempty text")
    return value


def count(value: Any, label: str, minimum: int = 0) -> int:
    require(type(value) is int and minimum <= value <= MAX_TICK, label + ": invalid bounded integer")
    return value


def literal(value: Any, choices: tuple[str, ...], label: str) -> None:
    require(type(value) is str and value in choices, label + ": unsupported literal")


def bounded(value: Any) -> None:
    pending = [(value, 0)]
    nodes = 0
    while pending:
        current, depth = pending.pop()
        nodes += 1
        require(nodes <= MAX_NODES and depth <= 32, "Foundation traversal limit exceeded")
        if type(current) is dict:
            require(all(type(key) is str for key in current), "Object keys must be text")
            pending.extend((child, depth + 1) for pair in current.items() for child in pair)
        elif type(current) is list:
            pending.extend((child, depth + 1) for child in current)
        elif type(current) is str:
            require(len(current.encode("utf-8")) <= 4096, "Foundation text exceeds byte bound")
        else:
            require(current is None or type(current) in (bool, int), "Non-declarative scalar")
            if type(current) is int:
                require(current.bit_length() <= 40 and len(str(current)) <= 12,
                        "Foundation integer exceeds digit bound")


def read(path: Path) -> dict[str, Any]:
    require(not path.is_symlink(), "Foundation file must not be a symlink")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            before = os.fstat(stream.fileno())
            require(stat.S_ISREG(before.st_mode), "Foundation input must be a regular file")
            require(0 < before.st_size <= MAX_BYTES, "Foundation file exceeds byte bound")
            raw = stream.read(MAX_BYTES + 1)
            after = os.fstat(stream.fileno())
    except OSError as error:
        raise FoundationError("Cannot read foundation file") from error
    require(len(raw) == before.st_size and
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
            "Foundation file changed during reading")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "Duplicate foundation key: " + key)
            result[key] = value
        return result

    def forbidden(value: str) -> None:
        raise FoundationError("Nonintegral/nonfinite foundation number: " + value)

    def integer(value: str) -> int:
        require(len(value.lstrip("-")) <= 12, "Foundation integer exceeds digit bound")
        return int(value)

    try:
        result = json.loads(raw, object_pairs_hook=pairs, parse_int=integer,
                            parse_float=forbidden, parse_constant=forbidden)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise FoundationError("Invalid foundation JSON") from error
    bounded(result)
    require(type(result) is dict, "Foundation root must be an object")
    return result


def validate_case(case: Any) -> None:
    row = closed(case, {"id", "family", "purpose", "original_conditions", "domain", "input_history",
        "candidate_activity", "obligations", "perturbation", "expected_verdict", "expected_reason"}, "Case")
    for key in ("id", "family", "purpose", "expected_reason"):
        text(row[key], key)
    literal(row["expected_verdict"], ("satisfies", "violates", "unknown", "unsupported", "reject"), "Expected verdict")
    original = closed(row["original_conditions"], {"executor_instances", "encounter_slots", "activity_endpoint",
        "initial_activity", "same_recipient", "material_members", "source_deadlines", "model_delays",
        "availability_loss_contract"}, "Original conditions")
    for key in ("executor_instances", "encounter_slots"):
        require(type(original[key]) is int and original[key] == 1, "Fixture requires one " + key)
    text(original["activity_endpoint"], "Activity endpoint")
    literal(original["initial_activity"], BANDS, "Initial activity")
    require(type(original["same_recipient"]) is bool, "Same-recipient value must be Boolean")
    require(type(original["material_members"]) is list, "Material members must be an ordered array")
    for member in original["material_members"]:
        text(member, "Material member")
    for key in ("source_deadlines", "model_delays"):
        for name, value in closed(original[key], DEADLINES, key).items():
            count(value, name, 1)
    text(original["availability_loss_contract"], "Availability contract")
    domain = closed(row["domain"], {"intervention_cutoff_tick", "suffix_ticks", "horizon_tick", "suffix_policy"}, "Domain")
    cutoff = count(domain["intervention_cutoff_tick"], "Decision cutoff")
    suffix = count(domain["suffix_ticks"], "Suffix")
    horizon = count(domain["horizon_tick"], "Horizon")
    require(cutoff + suffix == horizon, "Decision and suffix bounds must retain the complete horizon")
    literal(domain["suffix_policy"], ("hold_last_physical_inputs_no_encounter_events",), "Suffix policy")
    require(type(row["input_history"]) is list and type(row["candidate_activity"]) is list,
            "Input and candidate histories must be arrays")
    require(len(row["input_history"]) == horizon + 1 == len(row["candidate_activity"]),
            "Histories must contain the complete inclusive horizon")
    for tick, (input_row, activity_row) in enumerate(zip(row["input_history"], row["candidate_activity"], strict=True)):
        inputs = closed(input_row, {"tick", "encounter_event", "antigen", "controller", "availability", "evidence"}, "Input row")
        require(type(inputs["tick"]) is int and inputs["tick"] == tick, "Input ticks must be ordered and contiguous")
        literal(inputs["encounter_event"], ("none", "start", "end", "reset"), "Encounter event")
        literal(inputs["antigen"], ("present", "absent"), "Physical antigen")
        literal(inputs["controller"], ("enabled", "disabled"), "Physical controller")
        for value in closed(inputs["availability"], set(MEMBERS), "Availability").values():
            literal(value, ("present", "absent"), "Physical availability")
        for value in closed(inputs["evidence"], {"antigen", "controller", *MEMBERS}, "Evidence").values():
            literal(value, EVIDENCE, "Evidence status")
        activity = closed(activity_row, {"tick", "band", "evidence"}, "Activity row")
        require(type(activity["tick"]) is int and activity["tick"] == tick, "Activity ticks must be ordered and contiguous")
        literal(activity["band"], BANDS, "Physical activity band")
        literal(activity["evidence"], EVIDENCE, "Activity evidence")
    require(type(row["obligations"]) is list, "Obligations must be an array")
    for obligation in row["obligations"]:
        item = closed(obligation, {"kind", "trigger_tick", "deadline_tick", "required_band", "disposition", "cancelled_at_tick"}, "Obligation")
        literal(item["kind"], ("onset", "controller_cessation", "antigen_cessation", "availability_cessation", "encounter_cessation", "reactivation"), "Obligation kind")
        trigger = count(item["trigger_tick"], "Trigger")
        deadline = count(item["deadline_tick"], "Deadline")
        require(trigger <= horizon and trigger <= deadline, "Invalid obligation time order")
        literal(item["required_band"], BANDS, "Required band")
        literal(item["disposition"], ("required", "cancelled"), "Obligation disposition")
        if item["disposition"] == "cancelled":
            cancellation = count(item["cancelled_at_tick"], "Cancellation")
            require(trigger <= cancellation <= horizon, "Cancellation is outside the retained history")
        else:
            require(item["cancelled_at_tick"] is None, "Required obligation cannot carry cancellation")
    perturbation = closed(row["perturbation"], {"target", "operation", "value"}, "Perturbation")
    if perturbation["target"] is None:
        require(perturbation["operation"] is None and perturbation["value"] is None,
                "Absent perturbation must retain all null fields")
    else:
        target = perturbation["target"]
        literal(target, tuple(PERTURBATION_OPERATIONS), "Perturbation target")
        literal(perturbation["operation"], PERTURBATION_OPERATIONS[target], "Perturbation operation")
        value = perturbation["value"]
        if target == "candidate_activity":
            literal(value, ("constant_active", "constant_background", "irreversible_stop_after_first_cessation",
                "activity_without_antigen"), "Activity perturbation value")
        elif target == "candidate_state":
            require(value is True, "Controller-reset perturbation must be explicitly enabled")
        elif target == "candidate_material_members":
            require(type(value) is list and len(value) <= 3, "Material perturbation requires a bounded member array")
            for member in value:
                literal(member, ("rna_a", "rna_b", "rna_helper"), "Material perturbation member")
        elif target == "deployment.same_recipient":
            require(type(value) is bool, "Same-recipient perturbation must be Boolean")
        elif target == "source.initial_activity":
            literal(value, BANDS, "Initial-activity perturbation value")
        elif target == "verification_domain.suffix_ticks":
            count(value, "Suffix perturbation value")
        elif target == "verification_budget.max_work":
            count(value, "Work-budget perturbation value", 1)
        else:
            text(value, "Perturbation authority identity")


def validate(profile: dict[str, Any], corpus: dict[str, Any]) -> dict[str, Any]:
    bounded(profile)
    bounded(corpus)
    require(profile.get("schema_version") == "biocompiler.controlled_composition_profile.v0.1",
            "Unknown foundation profile")
    require(profile.get("status") == "specification_only" and profile.get("native_validation") == "not_run"
            and profile.get("native_admission") == "not_implemented_by_this_specification",
            "Foundation specification cannot claim native acceptance")
    require(profile["activity"]["physical_bands"] == list(BANDS)
            and profile["activity"]["unknown_is_physical_band"] is False,
            "Physical activity and unknown evidence must remain distinct")
    row = closed(corpus, {"schema_version", "status", "acceptance", "native_status", "fixture_kind",
        "source_profile", "material_profile", "coverage", "case_inventory", "cases"}, "Corpus")
    require(row["schema_version"] == "biocompiler.controlled_composition_acceptance_cases.v0.1"
            and row["status"] == "declarative_unexecuted" and row["acceptance"] is False
            and row["native_status"] == "not_run"
            and row["fixture_kind"] == "artificial_software_authority_examples",
            "Declarative cases must not claim execution or acceptance")
    for key in ("source_profile", "material_profile"):
        require(row[key] == profile[key], "Corpus differs from original profile: " + key)
    require(row["case_inventory"] == list(REQUIRED_CASES), "Required case inventory differs from the reviewed census")
    require(type(row["cases"]) is list, "Cases must be an array")
    for case in row["cases"]:
        validate_case(case)
    require([case["id"] for case in row["cases"]] == row["case_inventory"],
            "Cases are missing, duplicated, reordered or unaccounted")
    coverage = closed(row["coverage"], {"mode", "exhaustive_domain_execution", "families"}, "Coverage")
    require(coverage["mode"] == "named_examples_only" and coverage["exhaustive_domain_execution"] == "pending",
            "Named declarative cases cannot claim exhaustive execution")
    require(coverage["families"] == list(dict.fromkeys(case["family"] for case in row["cases"])),
            "Coverage families differ from the complete case inventory")
    return {"schema_version": "biocompiler.controlled_composition_foundation_check.v0.1",
        "status": "declarative_inventory_checked", "case_count": len(row["cases"]),
        "expected_verdict_counts": dict(sorted(Counter(case["expected_verdict"] for case in row["cases"]).items())),
        "native_status": "not_run", "semantic_execution": "not_performed", "acceptance": False,
        "claim_scope": "Closed declarative shape and complete named-case accounting only; expected verdicts were not executed."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        originals = {path: read(args.root / path) for path in (PROFILE, CORPUS)}
        result = validate(originals[PROFILE], originals[CORPUS])
        result["canonical_input_sha256"] = {str(path): hashlib.sha256(json.dumps(value, ensure_ascii=False,
            sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest() for path, value in originals.items()}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (FoundationError, OSError, KeyError, TypeError, ValueError) as error:
        print("Controlled composition foundation: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
