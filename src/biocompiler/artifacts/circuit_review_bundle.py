"""Create and publish deterministic review bundles of existing checked records.

This packages supplied artifacts without running a construction producer. Honest
failed, unknown, unsupported or stale assessments may be retained after replay.
It never performs reference reconstruction, model prediction or human admission.
"""

from dataclasses import dataclass
import hashlib

from biocompiler.artifacts.archive_container import (
    assemble_container,
    write_container_atomic,
)
from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.artifacts.circuit_review import (
    CircuitReviewAuthority,
    CircuitReviewFile,
    CircuitReviewManifest,
    FILE_ROLES,
    REVIEW_PACKAGE_VERSION,
)
from biocompiler.artifacts.manifest import RunMetadata
from biocompiler.ir.circuit_evidence import CircuitEvidenceReceipt
from biocompiler.ir.serialization import require
from biocompiler.verification.circuit_bindings import CircuitBindingAssessment
from biocompiler.verification.circuit_evidence import CircuitEvidenceAssessment
from biocompiler.verification.circuit_sources import CircuitSourcesAssessment


@dataclass(frozen=True)
class CircuitReviewBundle:
    data: bytes
    manifest: CircuitReviewManifest

    def __post_init__(self):
        require(
            type(self.data) is bytes
            and isinstance(self.manifest, CircuitReviewManifest),
            "Expected immutable review bundle bytes and manifest.",
        )


def create_circuit_review_bundle(
    build,
    *,
    expected_authority,
    source_assessment=None,
    binding_assessment=None,
    evidence_receipt=None,
    evidence_assessment=None,
    run_metadata=None,
):
    """Require complete fresh replay before producing a retained-review archive."""
    from biocompiler.verification.circuit_review import (
        current_review_toolchain,
        verify_circuit_review_bundle,
    )

    require(
        isinstance(build, CircuitConstructionBuild),
        "Expected a retained circuit construction build.",
    )
    require(
        isinstance(expected_authority, CircuitReviewAuthority),
        "Review creation requires separately supplied typed authority.",
    )
    expected = CircuitReviewAuthority.from_dict(expected_authority.to_dict())
    require(
        run_metadata is None or isinstance(run_metadata, RunMetadata),
        "Invalid review run metadata.",
    )
    records = {"request.json": expected.construction, "construction.json": build}
    for key, cls, value, path in (
        ("sources", CircuitSourcesAssessment, source_assessment, "checks/sources.json"),
        (
            "bindings",
            CircuitBindingAssessment,
            binding_assessment,
            "checks/bindings.json",
        ),
        (
            "evidence",
            CircuitEvidenceAssessment,
            evidence_assessment,
            "checks/evidence.json",
        ),
    ):
        authority = getattr(expected, key)
        require(
            (authority is None) == (value is None),
            "Review authority and optional assessment cohorts must match exactly.",
        )
        if value is not None:
            require(isinstance(value, cls), f"Invalid review {key} assessment.")
            records[path] = value
    if expected.sources is not None:
        records["sources/inventory.json"] = expected.sources
    if expected.bindings is not None:
        records["bindings/request.json"] = expected.bindings
    require(
        (expected.evidence is None) == (evidence_receipt is None),
        "Evidence cohort requires its complete historical receipt.",
    )
    if expected.evidence is not None:
        require(
            isinstance(evidence_receipt, CircuitEvidenceReceipt),
            "Invalid historical evidence receipt.",
        )
        records["evidence/request.json"] = expected.evidence
        records["evidence/receipt.json"] = evidence_receipt
    files = {
        path: (value.to_json(indent=2) + "\n").encode("utf-8")
        for path, value in records.items()
    }
    manifest = CircuitReviewManifest(
        expected.fingerprint,
        build.fingerprint,
        tuple(
            CircuitReviewFile(
                path,
                FILE_ROLES[path],
                hashlib.sha256(payload).hexdigest(),
                len(payload),
            )
            for path, payload in sorted(files.items())
        ),
        current_review_toolchain(),
        REVIEW_PACKAGE_VERSION,
    )
    data = assemble_container(manifest, files, run_metadata)
    verify_circuit_review_bundle(data, expected_authority=expected)
    return CircuitReviewBundle(data, manifest)


def publish_circuit_review_bundle(bundle, output, *, expected_authority):
    """Freshly replay before atomic single-file publication; never publish partial bytes."""
    from biocompiler.verification.circuit_review import verify_circuit_review_bundle

    require(
        isinstance(bundle, CircuitReviewBundle), "Expected a circuit review bundle."
    )
    report = verify_circuit_review_bundle(
        bundle.data, expected_authority=expected_authority
    )
    require(
        bundle.manifest.build_fingerprint == report["build_fingerprint"],
        "Review bundle manifest differs from retained bytes.",
    )
    return write_container_atomic(output, bundle.data)
