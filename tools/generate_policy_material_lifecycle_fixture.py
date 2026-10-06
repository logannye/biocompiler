"""Author four complete artificial lifecycle cases; never execute policy semantics.

The supplied whole-kernel/material cases are independent conditional premises.
Reusing exact RNA does not infer its behavior. Native tests freshly check each
case and reject substituting another complete case, even with identical bases.
Expected traces and the finite census below are literal reviewable expectations,
not observations obtained from either runtime or the lowering producer.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from biocompiler import policy as p

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "core/test/data/policy_material_request_v01.json"
OUTPUT = ROOT / "core/test/data/policy_material_lifecycle_v01.json"
SEED_REQUEST = "754a3a30752855c3e9458c0b657a2e7ac850d6aebb27e260009e331296341e36"


def digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def pin(record: dict) -> None:
    record["identity"]["content_fingerprint"] = digest(record["body"])


def author(seed: dict, authorization: str, on_unknown: str) -> dict:
    identity = f"{authorization}_{on_unknown}"
    request = deepcopy(seed["request"])
    parts = deepcopy(seed["candidate_parts"])
    original = request["implementation_request"]
    source = p.from_data(original["document"], p.BuildRequest)
    declarations = tuple(
        replace(item, lifecycle=replace(item.lifecycle, authorization=authorization,
                on_unknown=on_unknown, timeout=p.quantity(5, p.SECOND)))
        if isinstance(item, p.Effect) else item for item in source.program.declarations
    )
    program = replace(source.program, id=f"lifecycle.{identity}", declarations=declarations,
        source_map=tuple(replace(span, file=f"policy_lifecycle_{identity}.py") for span in source.program.source_map))
    original["document"] = p.to_data(replace(source, program=program))
    # Every original hard requirement, scope, target and source constraint is
    # unchanged. Only the explicitly authored effect lifecycle above differs.
    assert [d for d in original["document"]["program"]["declarations"] if d["$type"] == "Requirement"] == [
        d for d in seed["request"]["implementation_request"]["document"]["program"]["declarations"] if d["$type"] == "Requirement"]
    domain = original["operating_domain"]
    domain["fixed_observations"] = [row for row in domain["fixed_observations"] if row["available_tick"] < 2]
    domain["observation_factors"] = [{"age_ticks": [0], "alphabet": "known_truth_and_evidence_status.v1",
        "max_rows_per_slot_tick": 1, "observation": "condition", "slots": ["e1"], "ticks": [2]}]
    domain["feedback_factors"][0]["ticks"] = [4]
    library = original["implementation_library"]
    library["id"] = "lifecycle.complete.library"
    prototype = next(m for m in library["models"] if m["body"]["primitive"] == "attempt_bank")
    library["models"] = [m for m in library["models"] if m["body"]["primitive"] != "attempt_bank"]
    for mode in ("initiation", "continuous"):
        for response in ("continue", "defer"):
            variant = deepcopy(prototype)
            variant["identity"]["id"] = f"lifecycle.attempt.{mode}_{response}"
            variant["body"]["configuration"].update(authorization=mode, on_unknown=response, timeout_ticks=5)
            variant["configuration_digest"] = digest(variant["body"]["configuration"])
            pin(variant)
            library["models"].append(variant)
    model = next(m for m in library["models"] if m["identity"]["id"] == f"lifecycle.attempt.{identity}")
    original["catalog_bindings"][0]["models"] = [deepcopy(value["identity"]) for value in library["models"]]
    node = next(n for n in parts["implementation"]["nodes"] if n["id"] == "attempt")
    node.update(model=deepcopy(model["identity"]), configuration_digest=model["configuration_digest"])
    authority = parts["implementation"]["authority"]
    authority.update(source_artifact_digest=digest(original["document"]), domain_digest=digest(domain), library_digest=digest(library))
    contract = request["material_contract"]
    contract["identity"]["id"] = f"artificial.lifecycle.{identity}"
    kernel = contract["body"]["kernel"]
    kernel["library_digest"] = digest(library)
    next(n for n in kernel["nodes"] if n["local_id"] == "local.attempt")["model"] = deepcopy(model)
    pin(contract)
    request["catalog_binding"]["material_contract"] = deepcopy(contract["identity"])
    parts["material_binding"]["contract_digest"] = digest(contract)
    context = request["context"]
    context["record_layout"].update(domain_digest=digest(domain), kernel_digest=digest(kernel), maximum_tick=11)
    layout_digest = digest(context["record_layout"])
    for provider in context["providers"]:
        if provider["body"]["kind"] == "environment":
            provider["body"]["grammar"] = deepcopy(domain)
        for capacity in provider["body"]["capacities"]:
            capacity["record_layout_digest"] = layout_digest
        pin(provider)
    return {"id": identity, "authorization": authorization, "on_unknown": on_unknown,
        "request": request, "candidate_parts": parts,
        "expected": {"request_fingerprint": digest(request), "histories": 54, "transitions": 176,
            "prefixes_started": 177, "sequence": "CCAUGGCUUAAGGAAAA", "requirements": [
                "exclusive_selection", "initiation_progress", "request_progress"],
            "creation_tick": 1, "deadline_tick": 6, "feedback_tick": 4,
            "unknown_preserves_activity": True, "cancellation": "unsupported"}}


def build() -> dict:
    seed = json.loads(SEED.read_text())
    if digest(seed["request"]) != SEED_REQUEST:
        raise ValueError("Original complete seed changed; independently review all authority before regeneration")
    return {"schema_version": "biocompiler.policy_material_lifecycle_literals.v0.1",
        "notice": "Artificial supplied whole-kernel-to-RNA cases. Native validation pending; no empirical realization claim.",
        "seed_request_fingerprint": SEED_REQUEST, "limits": seed["limits"],
        "census_derivation": {"inclusive_ticks": 7, "tick_prefix_counts": [1, 1, 6, 6, 54, 54, 54],
            "observation_choices_at_two": ["silence", "false", "true", "missing", "invalid", "conflicting"],
            "feedback_choices_per_prior_attempt_at_four": ["silence", "completed", "failed"],
            "previously_created_attempts": 2, "histories": 54, "transitions": 176, "prefixes_started": 177},
        "cases": [author(seed, authorization, on_unknown) for authorization in ("initiation", "continuous")
            for on_unknown in ("continue", "defer")]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = json.dumps(build(), sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.check:
        if OUTPUT.read_text() != encoded:
            raise SystemExit("Lifecycle fixture differs from inert authoring source")
    else:
        OUTPUT.write_text(encoded)


if __name__ == "__main__":
    main()
