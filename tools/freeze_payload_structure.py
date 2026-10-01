"""Freeze structural payload declarations; these fixtures grant no acceptance."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys

from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_payloads import PayloadStructureContract, RequiredPayloadRegion
from biocompiler.ir.serialization import fingerprint
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tests.test_circuit_payloads import contract, molecule, unknown_provenance

CORPUS = ROOT / "tests/conformance/payload-structure-v1.json"
SCHEMA = "biocompiler.payload_structure_conformance.v1"
KINDS = {"region": RequiredPayloadRegion, "contract": PayloadStructureContract}


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode()


def inventory(corpus):
    return fingerprint({
        "records": sorted([item["id"], item["kind"]] for item in corpus["records"]),
        "rejections": sorted([item["id"], item["kind"], item["expected_code"]] for item in corpus["rejections"]),
    })


def build_corpus():
    records, rejections = [], []

    def retain(identity, kind, value):
        raw = value.to_dict() if hasattr(value, "to_dict") else value
        result = KINDS[kind].from_dict(raw)
        records.append({"id": identity, "kind": kind, "input": raw,
                        "normalized": result.to_dict(), "fingerprint": result.fingerprint})
        return raw

    def reject(identity, kind, raw, code):
        try:
            KINDS[kind].from_dict(raw)
        except SerializationError:
            pass
        else:
            raise AssertionError("Accepted intended rejection: " + identity)
        rejections.append({"id": identity, "kind": kind, "input": raw, "expected_code": code})

    region = retain("region/base", "region", RequiredPayloadRegion("feature", "arbitrary_declared_label"))
    retain("region/unicode", "region", RequiredPayloadRegion("🧬", "supplied_β"))
    retain("region/maximum_text", "region", RequiredPayloadRegion("a" * 4096, "b" * 4096))
    base = contract(molecule())
    raw = retain("contract/base", "contract", base)
    for form in ("delivered_rna", "delivered_dna"):
        for topology in ("linear", "circular"):
            retain(f"contract/{form}/{topology}", "contract", replace(base, form=form, topology=topology))
    retain("contract/unknown_authority", "contract", replace(base, provenance=unknown_provenance()))
    retain("contract/maximum_regions", "contract", replace(base, regions=tuple(
        RequiredPayloadRegion(f"feature{i:03d}", "declared_label") for i in range(256))))
    reverse = deepcopy(raw); reverse["regions"].reverse()
    retain("contract/reversed_input", "contract", reverse)
    for variant in ("base", "parameter-default", "parameter-override"):
        request = json.loads((ROOT / f"tests/conformance/case-b/{variant}/request.json").read_bytes())
        retain("case_b/" + variant, "contract", request["library"]["refinements"][0]["templates"][0]["payload_structures"][0])

    for kind, original in (("region", region), ("contract", raw)):
        for key in original:
            bad = deepcopy(original); del bad[key]
            reject(f"{kind}/missing/{key}", kind, bad, "missing_field")
        for name, key, value, code in (
            ("future_schema", "schema_version", "future", "unsupported_schema"),
            ("extra_field", "accepted", True, "unknown_field"),
        ):
            bad = deepcopy(original); bad[key] = value
            reject(f"{kind}/{name}", kind, bad, code)
        for key in (("feature_id", "kind") if kind == "region" else ("member_id",)):
            for name, value, code in (
                ("empty", "", "invalid_molecular_text"),
                ("trim", "\u00a0x", "invalid_molecular_text"),
                ("control", "a\x7fb", "invalid_molecular_text"),
                ("too_long", "🧬" * 1025, "invalid_molecular_text"),
                ("null", None, "invalid_type"),
                ("boolean", True, "invalid_type"),
            ):
                bad = deepcopy(original); bad[key] = value
                reject(f"{kind}/{key}/{name}", kind, bad, code)
    for name, key, value, code in (
        ("template_form", "form", "dna_expression_template", "invalid_payload_structure"),
        ("primary_form", "form", "primary_rna", "invalid_payload_structure"),
        ("protein_form", "form", "mature_protein", "invalid_payload_structure"),
        ("unknown_topology", "topology", "unknown", "invalid_payload_structure"),
        ("null_form", "form", None, "invalid_type"),
        ("boolean_topology", "topology", False, "invalid_type"),
        ("empty_regions", "regions", [], "invalid_payload_structure"),
        ("duplicate_regions", "regions", [region, region], "invalid_payload_structure"),
        ("too_many_regions", "regions", [region] * 257, "molecular_resource_limit"),
        ("region_shape", "regions", {}, "invalid_type"),
        ("null_provenance", "provenance", None, "invalid_type"),
    ):
        bad = deepcopy(raw); bad[key] = value
        reject("contract/" + name, "contract", bad, code)
    bad = deepcopy(raw); bad["regions"][0]["accepted"] = True
    reject("contract/nested_extra_field", "contract", bad, "unknown_field")
    bad = deepcopy(raw); bad["provenance"]["status"] = "unknown"
    reject("contract/conflicting_provenance", "contract", bad, "invalid_molecular_provenance")
    result = {"schema_version": SCHEMA, "claim_scope": "supplied region inventory only; no geometry, function, evidence or admission assessment",
              "records": records, "rejections": rejections}
    result["inventory_sha256"] = inventory(result)
    return result


def check_corpus(corpus):
    assert corpus["schema_version"] == SCHEMA
    assert len(corpus["records"]) == 14 and len(corpus["rejections"]) == 44, "Incomplete payload structure inventory"
    ids = [item["id"] for key in ("records", "rejections") for item in corpus[key]]
    assert len(ids) == len(set(ids)), "Duplicate payload structure case"
    assert corpus["inventory_sha256"] == inventory(corpus), "Changed payload structure inventory"
    assert inventory(corpus) == "34f60cd9057611341e84ab3572af9839fd7817791496507684d007e590637094", "Changed required case/diagnostic inventory"
    for item in corpus["records"]:
        actual = KINDS[item["kind"]].from_dict(item["input"])
        assert encoded(actual.to_dict()) == encoded(item["normalized"])
        assert actual.fingerprint == item["fingerprint"]
    for item in corpus["rejections"]:
        try:
            KINDS[item["kind"]].from_dict(item["input"])
        except SerializationError:
            continue
        raise AssertionError("Accepted intended rejection: " + item["id"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    corpus = build_corpus(); check_corpus(corpus)
    data = encoded(corpus)
    if args.write:
        CORPUS.write_bytes(data)
    elif not CORPUS.is_file() or CORPUS.read_bytes() != data:
        raise SystemExit("Payload structure corpus is stale; review before --write")
    print(json.dumps({"records": len(corpus["records"]), "rejections": len(corpus["rejections"]),
                      "bytes": len(data), "inventory_sha256": corpus["inventory_sha256"]}))


if __name__ == "__main__":
    main()
