"""Read-only, bounded views of retained supplied-construction artifacts.

Reports are display data, never acceptance authority. No sequence alignment,
mechanism inference, source retrieval or biological evidence promotion occurs.
"""

from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.ir.molecule_records import _bounded_tree
from biocompiler.ir.serialization import fingerprint, require


INSPECTION_VERSION = "biocompiler.circuit_inspection.v0.1"
DIFF_VERSION = "biocompiler.circuit_diff.v0.1"
MAX_DIFF_CHANGES = 4096
CLAIMS = {
    "source_fidelity": "unestablished",
    "biological_function": "unestablished",
    "human_therapeutic_admission": "not_admitted",
}


def _build(value):
    require(isinstance(value, CircuitConstructionBuild), "Expected a construction build.")
    return CircuitConstructionBuild.from_dict(value.to_dict())


def _freshness(build, authority):
    if authority is None:
        return {"status": "not_replayed", "assessment": None}
    # Inspection alone never imports or invokes the checker/producer. Verification
    # is a separate, explicitly requested replay against external authority.
    from biocompiler.compiler.circuit_construction import verify_circuit_construction

    result = verify_circuit_construction(build, expected_request=authority)
    return {"status": "replayed_external_authority", "assessment": result.to_dict()}


def _identity(value):
    return value.fingerprint if value is not None else None


def _without_spelling(value):
    document = value.to_dict()
    document.pop("sequence", None)
    document["fingerprint"] = value.fingerprint
    document["spelling_fingerprint"] = fingerprint(
        {"alphabet": value.space.alphabet, "sequence": value.sequence}
    )
    return document


def inspect_circuit_construction(build, *, expected_request=None):
    """Describe stored records; optional external authority requests fresh replay.

    Spelling hashes and coordinate maps are shown without copying long sequence
    strings into the view. The original artifact remains the lossless record.
    """
    build = _build(build)
    freshness = _freshness(build, expected_request)
    candidate, request = build.candidate, build.request
    bundle = candidate.bundle
    report = {
        "schema_version": INSPECTION_VERSION,
        "scope": "supplied_construction_inspection_only",
        "build_fingerprint": build.fingerprint,
        "request_fingerprint": request.fingerprint,
        "candidate_fingerprint": candidate.fingerprint,
        "freshness": freshness,
        "stored_assessment": build.assessment.to_dict(),
        "claims": dict(CLAIMS),
        "request": {
            "id": request.id,
            "mode": request.mode,
            "circuit_fingerprint": request.circuit.fingerprint,
            "circuit": request.circuit.to_dict(),
            "required_members": [item.to_dict() for item in request.requirements],
            "output_members": [item.to_dict() for item in request.output_members],
            "payload_structures": [item.to_dict() for item in request.payload_structures],
        },
        "roots": [
            {"id": root.id, "provenance": root.provenance.to_dict(),
             "molecule": _without_spelling(root.molecule)}
            for root in request.sources
        ],
        "steps": [step.to_dict() for step in request.steps],
        "values": [_without_spelling(value) for value in candidate.values],
        "molecules": [] if bundle is None else [
            _without_spelling(molecule) for molecule in bundle.molecules
        ],
        "complexes": [] if bundle is None else [item.to_dict() for item in bundle.complexes],
        "roles": [] if bundle is None else [item.to_dict() for item in bundle.role_instances],
        "amounts": [item.to_dict() for item in candidate.experimental_amounts],
        "missing_members": list(candidate.missing_members),
        "construction_diagnostics": list(candidate.diagnostics),
        "nominal_bundle_identity": None if bundle is None else bundle.declared_nominal_bundle_identity,
    }
    _bounded_tree(report)
    return report


def _changed_interval(before, after):
    """One enclosing changed interval, in linear time and constant extra space."""
    if before == after:
        return None
    prefix, shortest = 0, min(len(before), len(after))
    while prefix < shortest and before[prefix] == after[prefix]:
        prefix += 1
    suffix = 0
    while suffix < shortest - prefix and before[-suffix - 1] == after[-suffix - 1]:
        suffix += 1
    return {
        "comparison": "unaligned_common_prefix_suffix",
        "before": {"start": prefix, "end": len(before) - suffix},
        "after": {"start": prefix, "end": len(after) - suffix},
        "coordinate_convention": "zero_based_half_open",
    }


def diff_circuit_constructions(
    before, after, *, expected_before=None, expected_after=None, max_changes=256
):
    """Compare retained identities without alignment or treating equality as proof.

    Both authorities must be supplied for optional fresh replay. Each changed
    record has exact field names and identities; bounded output reports omissions.
    """
    require(type(max_changes) is int and 1 <= max_changes <= MAX_DIFF_CHANGES,
            "Diff change limit must be an integer from 1 to 4096.")
    require((expected_before is None) == (expected_after is None),
            "Fresh diff requires independent authority for both builds.")
    before, after = _build(before), _build(after)
    freshness = {
        "before": _freshness(before, expected_before),
        "after": _freshness(after, expected_after),
    }
    changes, count = [], 0

    def compare(section, identity, left, right):
        nonlocal count
        if _identity(left) == _identity(right):
            return
        count += 1
        if len(changes) >= max_changes:
            return
        old = {} if left is None else left.to_dict()
        new = {} if right is None else right.to_dict()
        # Canonical comparison preserves numeric type and all ordered paths.
        changed_fields = [key for key in sorted(old.keys() | new.keys())
                          if key not in old or key not in new
                          or fingerprint(old[key]) != fingerprint(new[key])]
        entry = {
            "section": section, "id": identity,
            "change": "added" if left is None else "removed" if right is None else "changed",
            "before_fingerprint": _identity(left), "after_fingerprint": _identity(right),
            "fields": changed_fields,
        }
        if "sequence" in changed_fields:
            entry["sequence_interval"] = _changed_interval(
                old.get("sequence", ""), new.get("sequence", "")
            )
        changes.append(entry)

    def inventory(section, left, right):
        old, new = {item.id: item for item in left}, {item.id: item for item in right}
        for identity in sorted(old.keys() | new.keys()):
            compare(section, identity, old.get(identity), new.get(identity))

    compare("request", "construction", before.request, after.request)
    compare("circuit", "original_authority", before.request.circuit, after.request.circuit)
    for field in ("sources", "steps", "output_members", "requirements", "complex_members", "amounts"):
        inventory("authority." + field, getattr(before.request, field), getattr(after.request, field))
    # Required payload contracts use member_id, not a free-standing record id.
    old_contracts = {item.member_id: item for item in before.request.payload_structures}
    new_contracts = {item.member_id: item for item in after.request.payload_structures}
    for identity in sorted(old_contracts.keys() | new_contracts.keys()):
        compare("authority.payload_structures", identity, old_contracts.get(identity), new_contracts.get(identity))
    inventory("values", before.candidate.values, after.candidate.values)
    compare("candidate", "complete_candidate", before.candidate, after.candidate)
    compare("assessment", "historical_receipt", before.assessment, after.assessment)
    left_bundle, right_bundle = before.candidate.bundle, after.candidate.bundle
    for field in ("molecules", "complexes", "role_instances"):
        inventory(field, () if left_bundle is None else getattr(left_bundle, field),
                  () if right_bundle is None else getattr(right_bundle, field))
    inventory("experimental_amounts", before.candidate.experimental_amounts,
              after.candidate.experimental_amounts)
    report = {
        "schema_version": DIFF_VERSION,
        "scope": "retained_artifact_comparison_only",
        "before_fingerprint": before.fingerprint, "after_fingerprint": after.fingerprint,
        "identical_content": before.fingerprint == after.fingerprint,
        "freshness": freshness, "claims": dict(CLAIMS),
        "changes": changes, "total_changes": count,
        "omitted_changes": count - len(changes), "truncated": count > len(changes),
    }
    _bounded_tree(report)
    return report
