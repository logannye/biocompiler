#!/usr/bin/env python3
"""Freeze complete component-domain records and local algebra; never acceptance."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from biocompiler.errors import SerializationError
from biocompiler.semantics.component_contracts import (
    DomainCheck, OperatingDomain, PortContract, ValueDomain,
    domain_subset, operating_domain_subset, ports_compatible,
    canonical_synthetic_unit, synthetic_output_domain,
    STATELESS_TIMING, TEMPORAL_LEVEL_TIMING, TEMPORAL_EVENT_TIMING,
)
from biocompiler.semantics.types import BOOLEAN, LEVEL, DURATION, CONCENTRATION, SURFACE_DENSITY, PRODUCTION_RATE, TypeSpec

SCHEMA = "biocompiler.component_contracts_conformance.v1"
OUTPUT = ROOT / "tests/conformance/component-contracts-v1.json"
RECORDS = {"value_domain": ValueDomain, "domain_check": DomainCheck,
           "operating_domain": OperatingDomain, "port": PortContract}
CASE_IDS_SHA256 = "1a961ee9bf62d6968054876d24813f559de96bb12fbe8945f8024fad27fb1c2e"
OPERATIONS = ("input", "constant", "and", "or", "not", "compare", "select", "any_contact", "output", "held_for", "onset", "pulse", "memory")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def encode(document):
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def port(*, direction="output", dtype=BOOLEAN, unit="1", initial=None, domain=None, timing=STATELESS_TIMING, **kwargs):
    return PortContract("port", direction, "meaning", dtype, unit, kwargs.get("role", "role"),
                        kwargs.get("scope", "cell"), kwargs.get("compartment", "abstract"), timing,
                        initial if initial is not None else ValueDomain.boolean(),
                        domain if domain is not None else ValueDomain.boolean())


def evaluate_case(item):
    data, operation = item["input"], item["operation"]
    if operation == "domain_subset":
        result = domain_subset(ValueDomain.from_dict(data["required"]), ValueDomain.from_dict(data["supported"]))
    elif operation == "operating_domain_subset":
        result = operating_domain_subset(OperatingDomain.from_dict(data["required"]), OperatingDomain.from_dict(data["supported"]))
    elif operation == "ports_compatible":
        result = ports_compatible(PortContract.from_dict(data["producer"]), PortContract.from_dict(data["consumer"]))
    elif operation == "canonical_synthetic_unit":
        return canonical_synthetic_unit(TypeSpec.from_dict(data["dtype"]))
    elif operation == "synthetic_output_domain":
        result = synthetic_output_domain(data["operator"], data["attributes"],
                  [ValueDomain.from_dict(value) for value in data["inputs"]], TypeSpec.from_dict(data["dtype"]),
                  initialization=data["initialization"], max_contacts=data["max_contacts"])
    else:
        raise AssertionError("Unknown algebra case operation")
    return None if result is None else result.to_dict()


def build_corpus():
    records, rejections, algebra = [], [], []

    def record(identity, kind, value, mutate=None):
        original = value.to_dict()
        if mutate:
            mutate(original)
        normalized = RECORDS[kind].from_dict(original).to_dict()
        records.append({"id": identity, "record_kind": kind, "input": original,
                        "normalized": normalized, "fingerprint": fingerprint(normalized)})

    def rejection(identity, kind, value, mutate, code="component_contract"):
        original = copy.deepcopy(value.to_dict())
        mutate(original)
        try:
            RECORDS[kind].from_dict(original)
        except SerializationError as error:
            rejections.append({"id": identity, "record_kind": kind, "input": original,
                               "expected_code": code, "python_error": str(error)})
        else:
            raise AssertionError("Accepted intended malformed record " + identity)

    def check(identity, operation, data, literal=None):
        item = {"id": identity, "operation": operation, "input": data}
        expected = evaluate_case(item)
        if literal is not None:
            assert canonical(expected) == canonical(literal), identity
        item.update(expected=expected, fingerprint=fingerprint(expected),
                    evidence="independent_literal" if literal is not None else "python_oracle")
        algebra.append(item)

    def subset(identity, required, supported, status=None, reason=None):
        literal = None if status is None else {"schema_version": DomainCheck.schema_version,
                                                "status": status, "reasons": [] if reason is None else [reason]}
        check(identity, "domain_subset", {"required": required.to_dict(), "supported": supported.to_dict()}, literal)

    yes, no, both = (ValueDomain.boolean(values) for values in ((True,), (False,), (False, True)))
    unknown = ValueDomain.unknown(reason="declared unknown")
    unknown_bool = ValueDomain.unknown(BOOLEAN, "1", "unobserved")
    interval = ValueDomain.interval(-2, 4.0)
    alias = TypeSpec("scalar", "SignalAlias")
    domains = [("boolean_true", yes), ("boolean_false", no), ("boolean_all", both),
               ("unknown_scalar", unknown), ("unknown_boolean", unknown_bool),
               ("interval_mixed", interval), ("interval_zero", ValueDomain.interval(-0.0, 0)),
               ("interval_point", ValueDomain.interval(2, 2)),
               ("interval_finite_large", ValueDomain.interval(10**300, 10**300)),
               ("interval_duration", ValueDomain.interval(0, 3, DURATION, "s")),
               ("interval_explicit_unit", ValueDomain.interval(0, 3, DURATION, "minutes")),
               ("interval_alias", ValueDomain.interval(0, 3, alias, "1")),
               ("unknown_custom_unit", ValueDomain.unknown(DURATION, "minutes", "not supplied"))]
    for identity, value in domains:
        record(identity, "value_domain", value)
    record("boolean_sort", "value_domain", both, lambda value: value.update(values=[True, False]))
    record("type_optional_fields", "value_domain", interval, lambda value: value["dtype"].pop("arguments"))
    for status in ("pass", "fail", "unknown"):
        record("claim_" + status, "domain_check", DomainCheck(status, ("second", "first")))
    record("claim_empty_pass", "domain_check", DomainCheck("pass"))
    empty = OperatingDomain()
    operating = OperatingDomain({"z": interval, "a": yes})
    record("operating_empty", "operating_domain", empty)
    record("operating_sort", "operating_domain", operating,
           lambda value: value.update(constraints=dict(reversed(list(value["constraints"].items())))))
    for timing in (STATELESS_TIMING, TEMPORAL_LEVEL_TIMING, TEMPORAL_EVENT_TIMING, "unknown"):
        record("port_" + timing, "port", port(timing=timing))
    record("port_input_contact", "port", port(direction="input", scope="contact"))
    record("port_unknown_initial", "port", port(initial=unknown_bool))
    record("port_unknown_runtime", "port", port(initial=no, domain=unknown_bool))
    record("port_scalar", "port", port(dtype=LEVEL, initial=ValueDomain.interval(0, 0), domain=interval))
    record("port_names_preserved", "port", port(role=" role ", compartment="μ"))

    for kind, value in (("value_domain", both), ("domain_check", DomainCheck("pass")), ("operating_domain", empty), ("port", port())):
        rejection(kind + "_unknown_field", kind, value, lambda d: d.update(extra=None), "unknown_field")
        rejection(kind + "_missing_field", kind, value, lambda d: d.pop("schema_version"), "missing_field")
        rejection(kind + "_schema", kind, value, lambda d: d.update(schema_version="unsupported"), "unsupported_schema")
    rejection("boolean_duplicates", "value_domain", both, lambda d: d.update(values=[False, False]))
    rejection("boolean_empty", "value_domain", both, lambda d: d.update(values=[]))
    rejection("boolean_integer", "value_domain", both, lambda d: d.update(values=[0]), "invalid_type")
    rejection("boolean_unit", "value_domain", both, lambda d: d.update(unit="bool"))
    rejection("boolean_bounds", "value_domain", both, lambda d: d.update(lower=0))
    rejection("interval_reversed", "value_domain", interval, lambda d: d.update(lower=5))
    rejection("interval_missing_bound", "value_domain", interval, lambda d: d.update(upper=None))
    rejection("interval_boolean_bound", "value_domain", interval, lambda d: d.update(lower=False))
    rejection("interval_huge_bound", "value_domain", interval, lambda d: d.update(upper=10**400))
    rejection("unknown_claims_bounds", "value_domain", unknown, lambda d: d.update(lower=0, upper=0))
    rejection("unknown_empty_reason", "value_domain", unknown, lambda d: d.update(reason=" "), "invalid_name")
    rejection("domain_kind", "value_domain", both, lambda d: d.update(kind="all"))
    rejection("event_dtype", "value_domain", both, lambda d: d["dtype"].update(kind="event", name="Event"))
    rejection("claim_status", "domain_check", DomainCheck("pass"), lambda d: d.update(status="verified"))
    rejection("claim_duplicate_reasons", "domain_check", DomainCheck("fail"), lambda d: d.update(reasons=["x", "x"]))
    rejection("operating_not_mapping", "operating_domain", empty, lambda d: d.update(constraints=[]), "invalid_type")
    rejection("operating_blank_coordinate", "operating_domain", operating, lambda d: d["constraints"].update({"\u2003": yes.to_dict()}), "invalid_name")
    rejection("port_direction", "port", port(), lambda d: d.update(direction="both"))
    rejection("port_scope", "port", port(), lambda d: d.update(scope="organ"))
    rejection("port_timing", "port", port(), lambda d: d.update(timing="continuous"))
    rejection("port_initial_exclusion", "port", port(), lambda d: d.update(initialization=yes.to_dict(), domain=no.to_dict()))
    rejection("port_type_alias", "port", port(), lambda d: d["dtype"].update(name="AliasCondition"))
    rejection("port_scalar_event", "port", port(dtype=LEVEL, initial=interval, domain=interval), lambda d: d.update(timing=TEMPORAL_EVENT_TIMING))

    subset("boolean_containment", yes, both, "pass")
    subset("boolean_directional", both, yes, "fail", "Required domain exceeds the supported domain.")
    subset("closed_endpoints", interval, interval, "pass")
    subset("scalar_exceeds", ValueDomain.interval(-3, 0), interval, "fail", "Required domain exceeds the supported domain.")
    subset("unknown_not_reflexive", unknown, unknown, "unknown", "Domain inclusion is unresolved because a domain is unknown.")
    subset("unknown_not_top", ValueDomain.interval(0, 1), unknown, "unknown", "Domain inclusion is unresolved because a domain is unknown.")
    subset("exact_type_not_dimensions", ValueDomain.interval(0, 1, alias), ValueDomain.interval(0, 1), "fail", "Domain types or explicit units differ.")
    subset("units_not_converted", ValueDomain.interval(0, 1, DURATION, "s"), ValueDomain.interval(0, 1, DURATION, "minutes"), "fail", "Domain types or explicit units differ.")
    subset("mixed_large_integer_float", ValueDomain.interval(2**53+1, 2**53+1), ValueDomain.interval(float(2**53), float(2**53)), "fail", "Required domain exceeds the supported domain.")
    check("operating_empty_inclusion", "operating_domain_subset", {"required": empty.to_dict(), "supported": empty.to_dict()}, DomainCheck("pass").to_dict())
    for key in ("missing", "quote'key", 'both\'"key', "line\nbreak", "μ", "a\u0085", "a\u00a0", "a\u200b", "a\ue000", "a\U000f0000", "a\u0378"):
        check("operating_missing_" + key, "operating_domain_subset",
              {"required": OperatingDomain({key: yes}).to_dict(), "supported": empty.to_dict()},
              DomainCheck("unknown", (f"Operating coordinate {key!r} is unspecified.",)).to_dict())
    check("operating_failure_dominates", "operating_domain_subset", {
        "required": OperatingDomain({"missing": yes, "x": both}).to_dict(),
        "supported": OperatingDomain({"x": no}).to_dict()},
        DomainCheck("fail", ("Operating coordinate 'missing' is unspecified.", "x: Required domain exceeds the supported domain.")).to_dict())
    check("port_exact_compatible", "ports_compatible", {"producer": port().to_dict(), "consumer": port(direction="input").to_dict()}, DomainCheck("pass").to_dict())
    check("port_unknown_not_pass", "ports_compatible", {"producer": port(timing="unknown").to_dict(), "consumer": port(direction="input").to_dict()},
          DomainCheck("unknown", ("Port timing is unknown.",)).to_dict())
    check("port_initial_is_separate", "ports_compatible", {"producer": port(initial=yes).to_dict(), "consumer": port(direction="input", initial=no).to_dict()},
          DomainCheck("fail", ("Initialization: Required domain exceeds the supported domain.",)).to_dict())
    for field, changed in (("direction", "output"), ("meaning", "other"), ("role", "other"), ("scope", "contact"), ("compartment", "other"), ("timing", TEMPORAL_LEVEL_TIMING)):
        consumer = port(direction="input").to_dict(); consumer[field] = changed
        check("port_mismatch_" + field, "ports_compatible", {"producer": port().to_dict(), "consumer": consumer})

    for identity, spec, unit in (("level", LEVEL, "1"), ("boolean", BOOLEAN, "1"), ("duration", DURATION, "s"),
        ("concentration", CONCENTRATION, "mol/m^3"), ("density", SURFACE_DENSITY, "mol/m^2"),
        ("rate", PRODUCTION_RATE, "mol/s"), ("derived", TypeSpec("scalar", "Custom", (("length", 2), ("time", -1))), "canonical:length^2;time^-1")):
        check("unit_" + identity, "canonical_synthetic_unit", {"dtype": spec.to_dict()}, unit)

    def synthetic(identity, operator, inputs, expected, *, dtype=BOOLEAN, attributes=None, initialization=False, max_contacts=None):
        data = {"operator": operator, "attributes": attributes or {}, "inputs": [x.to_dict() for x in inputs],
                "dtype": dtype.to_dict(), "initialization": initialization, "max_contacts": max_contacts}
        item = {"id": identity, "operation": "synthetic_output_domain", "input": data}
        expected = None if expected is None else expected.to_dict()
        assert canonical(evaluate_case(item)) == canonical(expected), identity
        item.update(expected=expected, fingerprint=fingerprint(expected), evidence="independent_literal")
        algebra.append(item)
    synthetic("infer_input", "input", [], None)
    synthetic("infer_constant_boolean", "constant", [], yes, attributes={"value": True})
    synthetic("infer_constant_scalar", "constant", [], ValueDomain.interval(2.0, 2.0), dtype=LEVEL,
              attributes={"value": {"canonical_value": 2.0}})
    synthetic("infer_and_false", "and", [no, both], no)
    synthetic("infer_and_possible", "and", [yes, both], both)
    synthetic("infer_or_true", "or", [yes, both], yes)
    synthetic("infer_or_possible", "or", [no, both], both)
    synthetic("infer_not", "not", [yes], no)
    synthetic("infer_compare", "compare", [interval, interval], both)
    synthetic("infer_select_boolean", "select", [both, yes, no], both)
    synthetic("infer_select_scalar", "select", [both, ValueDomain.interval(1, 3), ValueDomain.interval(-1.0, 2)], ValueDomain.interval(-1.0, 3), dtype=LEVEL)
    synthetic("infer_select_one_branch", "select", [yes, interval, ValueDomain.interval(-8, 8)], interval, dtype=LEVEL)
    synthetic("infer_any_contacts", "any_contact", [yes], both)
    synthetic("infer_zero_contacts", "any_contact", [yes], no, max_contacts=0.0)
    synthetic("infer_output", "output", [interval], interval, dtype=LEVEL)
    for operator in ("held_for", "onset", "pulse"):
        synthetic("infer_" + operator, operator, [yes], both)
        synthetic("infer_" + operator + "_false", operator, [no], no)
        synthetic("infer_" + operator + "_initial", operator, [yes], no if operator == "held_for" else yes, initialization=True)
    synthetic("infer_memory_runtime", "memory", [yes, no], both)
    synthetic("infer_memory_initial_set", "memory", [yes, no], yes, initialization=True)
    synthetic("infer_memory_initial_reset", "memory", [yes, yes], no, initialization=True)
    inferred_unknown = ValueDomain.unknown(BOOLEAN, "1", "Executable input domain is unknown.")
    for operator in ("and", "or", "not", "compare", "select", "any_contact", "output", "onset", "pulse", "memory"):
        synthetic("infer_unknown_" + operator, operator, [unknown_bool], inferred_unknown)
    synthetic("infer_held_initial_unknown", "held_for", [unknown_bool], no, initialization=True)
    synthetic("infer_held_runtime_unknown", "held_for", [unknown_bool], inferred_unknown)

    document = {"schema_version": SCHEMA,
        "claim_scope": "structural_component_domains_and_local_algebra_only_no_empirical_or_architecture_acceptance",
        "records": records, "rejections": rejections, "algebra": algebra,
        "diagnostic_profile": "python_repr_unicode14.v1",
        "diagnostic_witnesses": [
            {"id": "unicode15_new_shaking_face", "text": "a\U0001fae8", "expected_repr": "'a\\U0001fae8'", "newer_python_repr": "'a\U0001fae8'", "assigned_in_unicode": "15.0.0"},
            {"id": "unicode16_new_harp", "text": "a\U0001fa89", "expected_repr": "'a\\U0001fa89'", "newer_python_repr": "'a\U0001fa89'", "assigned_in_unicode": "16.0.0"},
            {"id": "unassigned_in_unicode16", "text": "a\U0010ffff", "expected_repr": "'a\\U0010ffff'", "newer_python_repr": "'a\\U0010ffff'", "assigned_in_unicode": None},
        ]}
    document["coverage"] = coverage(document)
    return document


def coverage(document):
    return {"record_kinds": sorted({item["record_kind"] for item in document["records"]}),
            "diagnostic_witness_count": len(document["diagnostic_witnesses"]),
            "record_count": len(document["records"]), "rejection_count": len(document["rejections"]),
            "algebra_count": len(document["algebra"]),
            "algebra_operations": sorted({item["operation"] for item in document["algebra"]}),
            "synthetic_operations": sorted({item["input"]["operator"] for item in document["algebra"] if item["operation"] == "synthetic_output_domain"}),
            "literal_algebra_count": sum(item["evidence"] == "independent_literal" for item in document["algebra"])}


def validate(document):
    assert document["schema_version"] == SCHEMA
    assert document["diagnostic_profile"] == "python_repr_unicode14.v1"
    assert len(document["records"]) >= 30 and len(document["rejections"]) >= 35 and len(document["algebra"]) >= 77, "Truncated component corpus"
    assert len(document["diagnostic_witnesses"]) == 3, "Missing explicit diagnostic profile witnesses"
    ids = [item["id"] for key in ("records", "rejections", "algebra") for item in document[key]]
    assert len(ids) == len(set(ids)), "Duplicate corpus identity"
    assert fingerprint(sorted(ids)) == CASE_IDS_SHA256, "Missing or changed retained case inventory"
    for item in document["records"]:
        result = RECORDS[item["record_kind"]].from_dict(item["input"]).to_dict()
        assert canonical(result) == canonical(item["normalized"])
        assert fingerprint(result) == item["fingerprint"]
    for item in document["rejections"]:
        try: RECORDS[item["record_kind"]].from_dict(item["input"])
        except SerializationError as error:
            assert str(error) == item["python_error"], "Changed Python rejection"
            identity = item["id"]
            expected = ("unknown_field" if identity.endswith("_unknown_field") else
                        "missing_field" if identity.endswith("_missing_field") else
                        "unsupported_schema" if identity.endswith("_schema") else
                        "invalid_type" if identity in {"boolean_integer", "operating_not_mapping"} else
                        "invalid_name" if identity in {"unknown_empty_reason", "operating_blank_coordinate"} else "component_contract")
            assert item["expected_code"] == expected, "Changed native rejection category"
        else: raise AssertionError("Malformed fixture was accepted")
    for item in document["algebra"]:
        result = evaluate_case(item)
        assert canonical(result) == canonical(item["expected"]), item["id"]
        assert fingerprint(result) == item["fingerprint"]
    assert document["coverage"] == coverage(document)
    assert document["coverage"]["record_kinds"] == sorted(RECORDS)
    assert document["coverage"]["synthetic_operations"] == sorted(OPERATIONS)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args(argv)
    document = build_corpus(); validate(document); content = encode(document)
    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(content)
    elif not args.output.is_file() or args.output.read_bytes() != content:
        raise SystemExit("Component contract corpus is absent or stale; regenerate explicitly with --write.")
    print(json.dumps({"status": "written" if args.write else "checked", "bytes": len(content), **document["coverage"]}, sort_keys=True))


if __name__ == "__main__":
    main()
