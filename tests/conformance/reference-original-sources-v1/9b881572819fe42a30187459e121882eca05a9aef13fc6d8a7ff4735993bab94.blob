"""Read-only construction reviews; browser transport retains authority JSON text."""

from collections.abc import Mapping

from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.artifacts.circuit_inspection import inspect_circuit_construction
from biocompiler.ir.circuit_bindings import CircuitBindingRequest
from biocompiler.ir.circuit_construction import CircuitConstructionRequest
from biocompiler.ir.circuit_evidence import (
    CircuitEvidenceReceipt,
    CircuitEvidenceRequest,
)
from biocompiler.ir.circuit_sources import CircuitSourceInventory
from biocompiler.ir.serialization import fields, require
from biocompiler.studio.service import _json_document
from biocompiler.verification.circuit_bindings import check_circuit_bindings
from biocompiler.verification.circuit_evidence import check_circuit_evidence
from biocompiler.verification.circuit_sources import inspect_circuit_source_readiness


_REVIEW_RECORDS = {
    "source_inventory_json": (CircuitSourceInventory, "Source metadata inventory"),
    "binding_request_json": (CircuitBindingRequest, "Independent binding authority"),
    "evidence_request_json": (CircuitEvidenceRequest, "Independent evidence authority"),
    "evidence_receipt_json": (CircuitEvidenceReceipt, "Historical evidence receipt"),
}


def _optional(text, record, label):
    require(
        text is None or isinstance(text, str), f"{label} must be JSON text or null."
    )
    return None if text is None else record.from_dict(_json_document(text, label))


def _load(payload, *, saving=False):
    keys = {"build_json", "expected_request_json"}
    if isinstance(payload, Mapping) and "review" in payload:
        keys.add("review")
    if saving:
        keys.add("expected_build_fingerprint")
    fields(payload, keys, "construction inspection")
    # Validate bytes/depth before decoding. Never evaluate source code or fetch a
    # provenance URL. Raw text avoids JavaScript integer/float normalization.
    build = CircuitConstructionBuild.from_dict(
        _json_document(payload["build_json"], "Construction build")
    )
    authority = _optional(
        payload["expected_request_json"],
        CircuitConstructionRequest,
        "Independent construction authority",
    )
    review = payload.get("review", dict.fromkeys(_REVIEW_RECORDS))
    fields(review, set(_REVIEW_RECORDS), "construction review")
    records = {
        key: _optional(review[key], record, label)
        for key, (record, label) in _REVIEW_RECORDS.items()
    }
    authorities = [] if authority is None else [("construction_request", authority)]
    for key in ("binding_request_json", "evidence_request_json"):
        if records[key] is not None:
            authorities.append((key.removesuffix("_json"), records[key].construction))
    # Every supplied current authority must agree in full, including numeric
    # spellings/types and original human obligations. Never silently prefer one.
    for label, expected in authorities:
        require(
            expected.fingerprint == build.request.fingerprint
            and expected.to_dict() == build.request.to_dict(),
            f"Supplied independent complete authority in {label} differs from the retained construction.",
        )
    if saving:
        require(
            build.fingerprint == payload["expected_build_fingerprint"],
            "Construction changed since inspection; inspect the current build again.",
        )
    authority = authorities[0][1] if authorities else None
    return build, authority, records, [label for label, _ in authorities]


def _review(build, records, authority_sources):
    inventory = records["source_inventory_json"]
    binding = records["binding_request_json"]
    evidence = records["evidence_request_json"]
    receipt = records["evidence_receipt_json"]
    sources = {"status": "missing_inventory", "readiness": None}
    if inventory is not None:
        sources = {
            "status": "checked_metadata_only",
            "readiness": inspect_circuit_source_readiness(inventory),
        }
    # Current schemas do not assert a source-case-to-construction relation. A
    # colocated inventory cannot become evidence that this build matches a case.
    sources["build_correspondence"] = "not_established"
    bindings = {"status": "missing_authority", "assessment": None, "bindings": []}
    if binding is not None:
        assessment = check_circuit_bindings(build.candidate, expected_request=binding)
        bindings = {
            "status": "checked_nominal_only",
            "assessment": assessment.to_dict(),
            "bindings": [item.to_dict() for item in binding.bindings],
        }
    evidence_view = {
        "status": "missing_authority" if evidence is None else "missing_receipt",
        "assessment": None,
        "sources": []
        if evidence is None
        else [item.to_dict() for item in evidence.sources],
    }
    if evidence is not None and receipt is not None:
        assessment = check_circuit_evidence(receipt, build, expected_request=evidence)
        evidence_view.update(
            status=assessment.freshness,
            assessment=assessment.to_dict(),
            dependencies=[
                {"id": item.id, "status": item.status}
                for item in assessment.dependencies
            ],
        )
    return {
        "authority_sources": authority_sources,
        "sources": sources,
        "bindings": bindings,
        "evidence": evidence_view,
        "acceptance": {
            "software": "individual_check_results_only",
            "reviewed_reference_correspondence": "not_established",
            "human_biological_applicability": "unassessed",
            "human_therapeutic_admission": "not_admitted",
            "prediction": "unsupported",
        },
    }


def inspect(payload):
    build, authority, records, authority_sources = _load(payload)
    report = inspect_circuit_construction(build, expected_request=authority)
    report["review"] = _review(build, records, authority_sources)
    return report


def save(payload):
    """Losslessly return the retained build after checking all current inputs.

    This saves a historical record, not a newly admitted deployment or synthesis
    artifact. Supplied authorities are freshly replayed; a failed nominal check
    stays failed and does not prevent preserving the original historical record.
    """
    build, authority, records, authority_sources = _load(payload, saving=True)
    report = inspect_circuit_construction(build, expected_request=authority)
    review = _review(build, records, authority_sources)
    return {
        "build_json": payload["build_json"],
        "build_fingerprint": build.fingerprint,
        "freshness": report["freshness"],
        "claims": report["claims"],
        "review": review,
    }
