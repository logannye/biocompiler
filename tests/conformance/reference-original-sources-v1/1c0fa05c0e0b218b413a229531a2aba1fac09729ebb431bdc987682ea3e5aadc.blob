"""Independent offline replay of retained circuit review records.

The archive's request and hashes are historical data. Verification always requires
separately supplied typed authority for every included cohort and receipt history.
No producer, model executor, URL resolver or archive extraction is used here.
"""

from biocompiler.artifacts.archive_container import (
    ARCHIVE_VERSION,
    assemble_container,
    read_container,
    validate_files,
)
from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.artifacts.circuit_review import (
    CircuitReviewAuthority,
    CircuitReviewManifest,
    REVIEW_PACKAGE_VERSION,
    REVIEW_POLICY_VERSION,
)
from biocompiler.artifacts.manifest import RunMetadata, ToolPin
from biocompiler.errors import SerializationError
from biocompiler.ir import (
    circuit_construction,
    circuit_profile,
    circuit_logic,
    circuit_sources,
)
from biocompiler.ir.circuit_bindings import CircuitBindingRequest
from biocompiler.ir.circuit_construction import CircuitConstructionRequest
from biocompiler.ir.circuit_evidence import (
    CircuitEvidenceReceipt,
    CircuitEvidenceRequest,
)
from biocompiler.ir.circuit_sources import CircuitSourceInventory
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
from biocompiler.verification import (
    circuit_bindings as bindings_checker,
    circuit_construction as construction_checker,
    circuit_evidence as evidence_checker,
    circuit_intent as intent_checker,
    circuit_profile as profile_checker,
    circuit_sources as sources_checker,
)

CHECKER_VERSION = "biocompiler.circuit_review_checker.v0.1"


def current_review_toolchain():
    """Declared current runtime policies, compared as a complete fixed inventory."""
    versions = {
        "archive": ARCHIVE_VERSION,
        "review": REVIEW_POLICY_VERSION,
        "review_checker": CHECKER_VERSION,
        "construction": circuit_construction.CONSTRUCTION_PROFILE_VERSION,
        "capabilities": circuit_construction.CAPABILITY_PROFILE_VERSION,
        "construction_checker": construction_checker.CHECKER_VERSION,
        "bindings_checker": bindings_checker.CHECKER_VERSION,
        "evidence_checker": evidence_checker.CHECKER_VERSION,
        "sources_checker": sources_checker.CHECKER_VERSION,
        "source_profile": circuit_sources.SOURCE_PROFILE_VERSION,
        "source_inventory": circuit_sources.INVENTORY_POLICY_VERSION,
        "circuit_profile": circuit_profile.PROFILE_VERSION,
        "profile_checker": profile_checker.CHECKER_VERSION,
        "intent_checker": intent_checker.CHECKER_VERSION,
        "logic_profile": circuit_logic.LOGIC_PROFILE_VERSION,
        "admission": ADMISSION_POLICY_VERSION,
    }
    return tuple(
        ToolPin(key, value, fingerprint(value))
        for key, value in sorted(versions.items())
    )


_TYPES = {
    "request.json": CircuitConstructionRequest,
    "construction.json": CircuitConstructionBuild,
    "sources/inventory.json": CircuitSourceInventory,
    "checks/sources.json": sources_checker.CircuitSourcesAssessment,
    "bindings/request.json": CircuitBindingRequest,
    "checks/bindings.json": bindings_checker.CircuitBindingAssessment,
    "evidence/request.json": CircuitEvidenceRequest,
    "evidence/receipt.json": CircuitEvidenceReceipt,
    "checks/evidence.json": evidence_checker.CircuitEvidenceAssessment,
}


def _parse(payload, cls):
    try:
        value = cls.from_json(payload.decode("utf-8"))
        require(
            (value.to_json(indent=2) + "\n").encode("utf-8") == payload,
            "Review records require canonical typed JSON bytes.",
        )
        return value
    except UnicodeError as error:
        raise SerializationError("Review record must be UTF-8 JSON.") from error


def _same(actual, expected, message):
    require(
        actual.fingerprint == expected.fingerprint
        and actual.to_dict() == expected.to_dict(),
        message,
    )


def _load_review(data):
    entries = read_container(data)
    require("manifest.json" in entries, "Review archive has no manifest.")
    manifest = _parse(entries["manifest.json"], CircuitReviewManifest)
    metadata = (
        _parse(entries["run.json"], RunMetadata) if "run.json" in entries else None
    )
    files = {
        key: value
        for key, value in entries.items()
        if key not in {"manifest.json", "run.json"}
    }
    validate_files(manifest, files)
    require(
        assemble_container(manifest, files, metadata) == data,
        "Review archive bytes are not canonical.",
    )
    records = {path: _parse(payload, _TYPES[path]) for path, payload in files.items()}
    build = records["construction.json"]
    request = records["request.json"]
    _same(build.request, request, "Retained construction and request disagree.")
    require(
        manifest.construction_fingerprint == build.fingerprint,
        "Review manifest construction identity disagrees.",
    )
    receipt = records.get("evidence/receipt.json")
    retained = CircuitReviewAuthority(
        request,
        sources=records.get("sources/inventory.json"),
        bindings=records.get("bindings/request.json"),
        evidence=records.get("evidence/request.json"),
        evidence_receipt_fingerprint=None if receipt is None else receipt.fingerprint,
    )
    require(
        manifest.authority_fingerprint == retained.fingerprint,
        "Review manifest retained authority identity disagrees.",
    )
    return manifest, records, metadata, retained


def _report(manifest, records, metadata, *, fresh):
    build = records["construction.json"]
    sources = records.get("checks/sources.json")
    bindings = records.get("checks/bindings.json")
    evidence = records.get("checks/evidence.json")
    return {
        "schema_version": "biocompiler.circuit_review_inspection.v0.1",
        "build_fingerprint": manifest.build_fingerprint,
        "authority_fingerprint": manifest.authority_fingerprint,
        "verification": "fresh_independent_replay"
        if fresh
        else "historical_unverified",
        "software_implementation": {
            "construction": build.assessment.outcome.value,
            "construction_complete": build.assessment.complete,
            "sources": "missing" if sources is None else sources.outcome.value,
            "bindings": "missing" if bindings is None else bindings.outcome.value,
            "evidence": "missing" if evidence is None else evidence.freshness,
            "prediction": "unsupported",
            "family_semantics": "unimplemented",
        },
        "reviewed_reference_correspondence": "not_established",
        "human_biological_applicability": "unassessed",
        "human_therapeutic_admission": "not_admitted",
        "source_metadata_construction_correspondence": "not_established",
        "source_bytes": "not_included_or_checked",
        "cohorts": list(manifest.cohorts),
        "files": [item.to_dict() for item in manifest.files],
        "run_metadata": None if metadata is None else metadata.to_dict(),
    }


def inspect_circuit_review_bundle(data):
    """Validate typed container integrity; every retained check remains historical."""
    manifest, records, metadata, _ = _load_review(data)
    return _report(manifest, records, metadata, fresh=False)


def verify_circuit_review_bundle(data, *, expected_authority):
    """Replay included checks against complete external authority, even honest FAIL.

    Successful replay means the retained result is accurate for supplied software
    authority. It does not mean that the construction, bindings or evidence passed.
    The returned scoped outcomes and all unresolved biological tracks stay explicit.
    """
    require(
        isinstance(expected_authority, CircuitReviewAuthority),
        "Fresh review verification requires complete independent typed authority.",
    )
    expected = CircuitReviewAuthority.from_dict(expected_authority.to_dict())
    manifest, records, metadata, retained = _load_review(data)
    _same(
        retained,
        expected,
        "Review records differ from complete independent authority; every included cohort requires its external authority.",
    )
    require(
        manifest.package_version == REVIEW_PACKAGE_VERSION,
        "Review package version is not current.",
    )
    require(
        tuple(item.to_dict() for item in manifest.toolchain)
        == tuple(item.to_dict() for item in current_review_toolchain()),
        "Review toolchain differs from current trusted checker policies.",
    )
    build = records["construction.json"]
    construction_checker.verify_circuit_construction_assessment(
        build.assessment,
        build.candidate,
        expected_request=expected.construction,
    )
    if expected.sources is not None:
        sources_checker.verify_circuit_sources(
            records["checks/sources.json"], expected_inventory=expected.sources
        )
    if expected.bindings is not None:
        bindings_checker.verify_circuit_binding_assessment(
            records["checks/bindings.json"],
            build.candidate,
            expected_request=expected.bindings,
        )
    if expected.evidence is not None:
        receipt = records["evidence/receipt.json"]
        require(
            receipt.fingerprint == expected.evidence_receipt_fingerprint,
            "Historical evidence receipt differs from independent authority.",
        )
        evidence_checker.verify_circuit_evidence_assessment(
            records["checks/evidence.json"],
            receipt,
            build,
            expected_request=expected.evidence,
        )
    return _report(manifest, records, metadata, fresh=True)
