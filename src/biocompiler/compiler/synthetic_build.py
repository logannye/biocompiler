"""Reconstructible finite-history synthetic packages using current trusted tools."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from biocompiler.artifacts.archive import (
    ARCHIVE_VERSION,
    assemble_archive,
    read_archive,
    write_archive_atomic,
)
from biocompiler.artifacts.manifest import RunMetadata, ToolPin
from biocompiler.artifacts.synthetic_build import (
    REQUIRED_FILES,
    SyntheticBuildManifest,
    SyntheticBuildRequest,
    SyntheticPackageFile,
)
from biocompiler.compiler.synthetic import run_synthetic_pipeline
from biocompiler.errors import SerializationError
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.models.synthetic import MODEL_RUNNER_VERSION
from biocompiler.registry.synthetic import catalog_for_profile
from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
from biocompiler.semantics.evaluator import REFERENCE_EVALUATOR_VERSION
from biocompiler.synthesis.synthetic import (
    GENERATOR_VERSION,
    SYNTHETIC_CHECKER_VERSION,
    check_synthetic_candidate,
)
from biocompiler.verification.admission import require_software_use
from biocompiler.verification.realization import CHECKER_VERSION

SYNTHETIC_BUILD_VERSION = "biocompiler.synthetic_build.v0.1"


def _json_bytes(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _tools():
    versions = {
        "synthetic_build": SYNTHETIC_BUILD_VERSION,
        "archive": ARCHIVE_VERSION,
        "human_admission_policy": ADMISSION_POLICY_VERSION,
        "generator": GENERATOR_VERSION,
        "synthetic_acceptance": SYNTHETIC_CHECKER_VERSION,
        "model": MODEL_RUNNER_VERSION,
        "realization_checker": CHECKER_VERSION,
        "reference_evaluator": REFERENCE_EVALUATOR_VERSION,
    }
    return tuple(
        ToolPin(key, value, fingerprint(value))
        for key, value in sorted(versions.items())
    )


@dataclass(frozen=True)
class SyntheticPackage:
    """Package bytes and authority; publication rechecks rather than trusting this type."""

    request: SyntheticBuildRequest
    manifest: SyntheticBuildManifest
    data: bytes

    @property
    def build_fingerprint(self):
        return self.manifest.build_fingerprint

    @property
    def archive_sha256(self):
        return hashlib.sha256(self.data).hexdigest()


def build_synthetic_package(
    request: SyntheticBuildRequest,
    *,
    run_metadata: RunMetadata | None = None,
) -> SyntheticPackage:
    """Generate, independently check and package one frozen finite-history request.

    No source fetching or Python authoring execution occurs. Success is bounded
    to the requested software model and history; molecular behavior is unresolved.
    """
    require(
        isinstance(request, SyntheticBuildRequest), "Expected SyntheticBuildRequest."
    )
    require_software_use(request.realization.target, boundary="export")
    build = run_synthetic_pipeline(
        request.realization,
        request.history.frames,
        until=request.until,
        config=request.config,
    )
    # Retain a fresh, standalone checker result as well as each accepted stage.
    check = check_synthetic_candidate(
        request.realization,
        build.candidate,
        request.history.frames,
        until=request.until,
    )
    require(check.passed, "The current independent synthetic check did not pass.")
    completion = build.manager.result("mechanism", scope="synthetic_realization")
    require(
        completion.status.value == "complete", "Synthetic build scope is incomplete."
    )
    records = tuple(
        build.manager.get(stage) for stage in ("request", "behavior", "mechanism")
    )
    catalog = catalog_for_profile(request.config.profile_version)
    documents = {
        "request.json": request.to_dict(),
        "inputs/history.json": request.history.to_dict(),
        "inputs/config.json": request.config.to_dict(),
        "inputs/catalog.json": catalog.to_dict(),
        "candidate.json": build.candidate.to_dict(),
        "checks/realization.json": check.to_dict(),
        **{f"stages/{record.id}.json": record.to_dict() for record in records},
        "result.json": {
            "schema_version": "biocompiler.synthetic_build_summary.v0.1",
            "status": completion.status.value,
            "scope": completion.scope,
            "intended_use": "software_test",
            "human_therapeutic_admission": "not_admitted",
            "request_fingerprint": request.fingerprint,
            "realization_fingerprint": request.realization.fingerprint,
            "candidate_fingerprint": build.candidate.fingerprint,
            "history_fingerprint": request.history.fingerprint,
            "until": request.until,
            "generator_config_fingerprint": request.config.fingerprint,
            "component_locks": [
                lock.to_dict() for lock in build.candidate.component_locks
            ],
            "stages": [
                {
                    "id": record.id,
                    "fingerprint": record.fingerprint,
                    "payload_fingerprint": fingerprint(record.payload),
                }
                for record in records
            ],
            "claim_scope": check.claim_scope,
            "unresolved": [item.to_dict() for item in completion.unresolved],
            "limitations": "Finite supplied-history software-model evidence only; no empirical, universal or molecular implementation claim.",
        },
    }
    files = {path: _json_bytes(value) for path, value in documents.items()}
    entries = tuple(
        SyntheticPackageFile(
            path,
            REQUIRED_FILES[path],
            hashlib.sha256(content).hexdigest(),
            len(content),
        )
        for path, content in files.items()
    )
    from biocompiler import __version__

    manifest = SyntheticBuildManifest(
        request.fingerprint, entries, _tools(), __version__
    )
    return SyntheticPackage(
        request, manifest, assemble_archive(manifest, files, run_metadata)
    )


def verify_synthetic_package(
    data: bytes,
    *,
    expected_request: SyntheticBuildRequest | None = None,
    expected_build_fingerprint: str | None = None,
) -> SyntheticPackage:
    """Rebuild with current tools and independent authority binding *all* input values."""
    require(
        expected_request is not None or expected_build_fingerprint is not None,
        "Fresh verification requires an independently trusted request or build fingerprint.",
    )
    require(
        expected_request is None or isinstance(expected_request, SyntheticBuildRequest),
        "Expected a complete SyntheticBuildRequest binding history, horizon and config.",
    )
    manifest, files, metadata = read_archive(data)
    require(
        isinstance(manifest, SyntheticBuildManifest), "Expected a synthetic package."
    )
    try:
        request = SyntheticBuildRequest.from_json(files["request.json"].decode("utf-8"))
    except UnicodeError as error:
        raise SerializationError("Packaged request must be UTF-8 JSON.") from error
    if expected_request is not None:
        require(
            request.fingerprint == expected_request.fingerprint,
            "Packaged request differs from independent authority.",
        )
    if expected_build_fingerprint is not None:
        require(
            manifest.build_fingerprint == expected_build_fingerprint,
            "Packaged build differs from independently trusted identity.",
        )
    require(
        manifest.request_fingerprint == request.fingerprint,
        "Packaged request fingerprint mismatch.",
    )
    require_software_use(request.realization.target, boundary="verification")
    rebuilt = build_synthetic_package(request, run_metadata=metadata)
    require(
        rebuilt.manifest == manifest,
        "Package identities or evidence are stale, altered or unsupported by current tools.",
    )
    require(
        rebuilt.data == data,
        "Package content differs from current independent offline reconstruction.",
    )
    return rebuilt


def publish_synthetic_package(package: SyntheticPackage, output) -> Path:
    """Freshly validate before atomically replacing one portable .bcb archive."""
    require(isinstance(package, SyntheticPackage), "Expected a synthetic package.")
    checked = verify_synthetic_package(
        package.data,
        expected_request=package.request,
        expected_build_fingerprint=package.build_fingerprint,
    )
    return write_archive_atomic(output, checked.data)
