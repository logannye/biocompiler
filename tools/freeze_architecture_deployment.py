"""Freeze supplied deployment declarations and exact decimal-second boundaries."""
from __future__ import annotations

import argparse
from copy import deepcopy
from fractions import Fraction
import json
import math
from pathlib import Path

from biocompiler.errors import SerializationError
from biocompiler.ir.architecture_deployment import RNAAvailabilityContract, RNADeploymentRequirement
from biocompiler.ir.serialization import fingerprint

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/architecture-deployment-v1.json"
SCHEMA = "biocompiler.architecture_deployment_conformance.v1"
KINDS = {"availability": RNAAvailabilityContract, "requirement": RNADeploymentRequirement}


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n").encode()


def build_corpus():
    records, rejections = [], []

    def retain(identity, kind, value):
        raw = value.to_dict() if hasattr(value, "to_dict") else value
        result = KINDS[kind].from_dict(raw)
        records.append({"id": identity, "kind": kind, "input": raw, "normalized": result.to_dict(),
                        "fingerprint": result.fingerprint})
        return raw

    def reject(identity, kind, raw, code):
        try:
            KINDS[kind].from_dict(raw)
        except SerializationError:
            pass
        else:
            raise AssertionError("Accepted intended rejection " + identity)
        rejections.append({"id": identity, "kind": kind, "input": raw, "expected_code": code})

    a = retain("availability/base", "availability", RNAAvailabilityContract("a", "member", 0, 0.1, 0.2, 0.3, ("declared",)))
    r = retain("requirement/base", "requirement", RNADeploymentRequirement("r", "group", "role", "cytosol", 0.1, 0.3, ("declared",)))
    for name, changes in (
        ("empty_common_window", {"onset_max_seconds": 9, "duration_min_seconds": 1, "duration_max_seconds": 2}),
        ("exact_decimal_cap", {"onset_min_seconds": 0.1, "onset_max_seconds": 0.1, "duration_max_seconds": 31535999.9}),
        ("negative_zero", {"onset_min_seconds": -0.0, "onset_max_seconds": 0}),
        ("smallest_duration", {"onset_max_seconds": 0, "duration_min_seconds": 5e-324, "duration_max_seconds": 5e-324}),
        ("sorted_assumptions", {"assumptions": ["z", "a", "🧬"]}),
        ("maximum_assumptions", {"assumptions": [f"assumption{i}" for i in range(64)]}),
    ):
        value = deepcopy(a); value.update(changes)
        retain("availability/" + name, "availability", value)
    # Empty common overlap is a contextual selection failure, not a malformed window.
    for name, changes in (
        ("same_recipient_false", {"require_same_recipient": False}),
        ("unavailability_equal", {"unavailable_after_seconds": 0.3}),
        ("unavailability_later", {"unavailable_after_seconds": 1}),
        ("negative_zero", {"required_from_seconds": -0.0}),
        ("sorted_assumptions", {"assumptions": ["z", "a"]}),
        ("abstract_compartment", {"compartment": "abstract"}),
        ("full_bound", {"required_from_seconds": 0, "required_until_seconds": 31536000}),
    ):
        value = deepcopy(r); value.update(changes)
        retain("requirement/" + name, "requirement", value)

    for kind, base in (("availability", a), ("requirement", r)):
        for key in base:
            raw = deepcopy(base); raw.pop(key)
            reject(kind + "/missing/" + key, kind, raw, "missing_field")
        for name, key, value, code in (
            ("future_schema", "schema_version", "future", "unsupported_schema"),
            ("extra_authority", "accepted", True, "unknown_field"),
            ("bad_clock", "clock", "absolute_time", "invalid_deployment"),
            ("empty_assumptions", "assumptions", [], "invalid_deployment"),
            ("duplicate_assumptions", "assumptions", ["a", "a"], "invalid_deployment"),
            ("too_many_assumptions", "assumptions", [str(i) for i in range(65)], "molecular_resource_limit"),
            ("assumption_control", "assumptions", ["a\nb"], "invalid_molecular_text"),
            ("assumption_trim", "assumptions", [" a"], "invalid_molecular_text"),
            ("blank_id", "id", "", "invalid_molecular_text"),
        ):
            raw = deepcopy(base); raw[key] = value
            reject(kind + "/" + name, kind, raw, code)
    for key in ("onset_min_seconds", "onset_max_seconds", "duration_min_seconds", "duration_max_seconds"):
        for name, value in (("negative", -1), ("boolean", True), ("text", "0.1"), ("null", None), ("over_cap", 31536001)):
            raw = deepcopy(a); raw[key] = value
            reject("availability/" + key + "/" + name, "availability", raw, "invalid_deployment_time")
    for key in ("required_from_seconds", "required_until_seconds", "unavailable_after_seconds"):
        for name, value in (("negative", -1), ("boolean", False), ("text", "0.1"), ("over_cap", 31536001)):
            raw = deepcopy(r); raw[key] = value
            reject("requirement/" + key + "/" + name, "requirement", raw, "invalid_deployment_time")
    for identity, kind, base, changes, code in (
        ("reversed_onset", "availability", a, {"onset_min_seconds": 1}, "invalid_deployment"),
        ("zero_duration", "availability", a, {"duration_min_seconds": 0}, "invalid_deployment"),
        ("reversed_duration", "availability", a, {"duration_min_seconds": 1}, "invalid_deployment"),
        ("sum_over_cap", "availability", a, {"duration_max_seconds": 31536000}, "invalid_deployment"),
        ("empty_window", "requirement", r, {"required_until_seconds": 0.1}, "invalid_deployment"),
        ("reversed_window", "requirement", r, {"required_until_seconds": 0}, "invalid_deployment"),
        ("unavailable_early", "requirement", r, {"unavailable_after_seconds": 0.2}, "invalid_deployment"),
        ("numeric_boolean", "requirement", r, {"require_same_recipient": 1}, "invalid_type"),
    ):
        raw = deepcopy(base); raw.update(changes)
        reject(kind + "/" + identity, kind, raw, code)

    times = [0, -0.0, 0.0, 1, 1.0, 0.1, 0.2, 0.3, 0.7, 0.8, 1e-5, 1e-4, 5e-324,
             2.2250738585072014e-308, 31536000, 31535999.9, math.nextafter(0.3, 0), math.nextafter(0.3, 1)]
    decimals = [{"id": f"decimal/{index}", "input": value, "numerator": Fraction(str(value)).numerator,
                 "denominator": Fraction(str(value)).denominator} for index, value in enumerate(times)]
    sums = [{"id": identity, "left": left, "right": right, "bound": bound, "expected": expected}
            for identity, left, right, bound, expected in (
                ("sum/tenths", 0.1, 0.2, 0.3, 0), ("sum/eighths", 0.7, 0.1, 0.8, 0),
                ("sum/below", 0.1, 0.2, math.nextafter(0.3, 1), -1),
                ("sum/above", 0.1, 0.2, math.nextafter(0.3, 0), 1),
                ("sum/cap", 0.1, 31535999.9, 31536000, 0), ("sum/tiny", 5e-324, 5e-324, 1e-323, 0))]
    result = {"schema_version": SCHEMA, "claim_scope": "structural declarations and exact decimal intervals only; no deployment assessment or empirical claim",
              "records": records, "rejections": rejections, "decimals": decimals, "sums": sums}
    result["case_ids_sha256"] = fingerprint([item["id"] for group in (records, rejections, decimals, sums) for item in group])
    check_corpus(result)
    return result


def check_corpus(corpus):
    assert corpus["schema_version"] == SCHEMA
    ids = [item["id"] for key in ("records", "rejections", "decimals", "sums") for item in corpus[key]]
    assert len(set(ids)) == len(ids)
    assert len(corpus["records"]) == 15 and len(corpus["rejections"]) == 78
    assert len(corpus["decimals"]) == 18 and len(corpus["sums"]) == 6
    assert corpus["case_ids_sha256"] == "c2a7f64b484d3208d2608131f860b0d8d2a0edeaffbe573e252b619aa460cd1d"
    assert fingerprint(ids) == corpus["case_ids_sha256"]
    for case in corpus["records"]:
        value = KINDS[case["kind"]].from_dict(case["input"])
        assert encoded(value.to_dict()) == encoded(case["normalized"]), case["id"]
        assert value.fingerprint == case["fingerprint"], case["id"]
    for case in corpus["rejections"]:
        try: KINDS[case["kind"]].from_dict(case["input"])
        except SerializationError: pass
        else: raise AssertionError("Accepted " + case["id"])
    for case in corpus["decimals"]:
        value = Fraction(str(case["input"]))
        assert (value.numerator, value.denominator) == (case["numerator"], case["denominator"])
    for case in corpus["sums"]:
        difference = Fraction(str(case["left"])) + Fraction(str(case["right"])) - Fraction(str(case["bound"]))
        assert (difference > 0) - (difference < 0) == case["expected"]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path, default=CORPUS)
    args = parser.parse_args(argv)
    corpus = build_corpus(); raw = encoded(corpus)
    if args.write: args.output.write_bytes(raw)
    else:
        assert args.output.read_bytes() == raw, "Stale deployment corpus"
    print(json.dumps({"status": "written" if args.write else "checked", "bytes": len(raw),
                      **{key: len(corpus[key]) for key in ("records", "rejections", "decimals", "sums")},
                      "case_ids_sha256": corpus["case_ids_sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
