"""Reproducible offline reference packages; imported reports never grant acceptance."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tempfile

from biocompiler.artifacts.archive import (
    ARCHIVE_VERSION,
    assemble_archive,
    read_archive,
    write_archive_atomic,
)
from biocompiler.artifacts.manifest import (
    AcceptedStage,
    BuildManifest,
    PackageFile,
    ReferenceBuildRequest,
    RunMetadata,
    ToolPin,
)
from biocompiler.artifacts.sequences import (
    SEQUENCE_EXPORT_VERSION,
    export_reference_sequence,
)
from biocompiler.backends.reference import EMITTER_VERSION
from biocompiler.compiler.construct import CONSTRUCT_PIPELINE_VERSION
from biocompiler.compiler.molecular import (
    MOLECULAR_PIPELINE_VERSION,
    run_molecular_pipeline,
)
from biocompiler.errors import SerializationError
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.registry.reference_builds import (
    MANIFEST_PIN,
    REFERENCE_BUILD_INPUTS_VERSION,
    collect_reference_files,
    load_reference_inputs,
)
from biocompiler.registry.reference_components import REFERENCE_COMPONENT_VERSION
from biocompiler.synthesis.construct import CONSTRUCT_GENERATOR_VERSION
from biocompiler.verification.components import (
    CHECKER_VERSION as COMPONENT_CHECKER_VERSION,
)
from biocompiler.verification.components import check_composition
from biocompiler.verification.construct import (
    CHECKER_VERSION as CONSTRUCT_CHECKER_VERSION,
)
from biocompiler.verification.construct import check_construct
from biocompiler.verification.molecular import (
    CHECKER_VERSION as MOLECULAR_CHECKER_VERSION,
)

from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
from biocompiler.verification.admission import require_software_use

REFERENCE_BUILD_VERSION = "biocompiler.reference_build.v0.2"


def _json_bytes(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _tools():
    import sys as _package_sys
    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')
    if _package_backend is not None:
        _package_value = _package_backend.default('_tools')
        if _package_value is not _package_backend.UNSELECTED:
            return _package_value
    versions = {
        "reference_build": REFERENCE_BUILD_VERSION,
        "human_admission_policy": ADMISSION_POLICY_VERSION,
        "reference_inputs": REFERENCE_BUILD_INPUTS_VERSION,
        "archive": ARCHIVE_VERSION,
        "sequence_export": SEQUENCE_EXPORT_VERSION,
        "sequence_emitter": EMITTER_VERSION,
        "construct_pipeline": CONSTRUCT_PIPELINE_VERSION,
        "molecular_pipeline": MOLECULAR_PIPELINE_VERSION,
        "reference_adapter": REFERENCE_COMPONENT_VERSION,
        "construct_generator": CONSTRUCT_GENERATOR_VERSION,
        "component_checker": COMPONENT_CHECKER_VERSION,
        "construct_checker": CONSTRUCT_CHECKER_VERSION,
        "molecular_checker": MOLECULAR_CHECKER_VERSION,
    }
    return tuple(
        ToolPin(key, value, fingerprint(value))
        for key, value in sorted(versions.items())
    )


@dataclass(frozen=True)
class ReferencePackage:
    """Checked package content; publish rechecks it instead of trusting this type."""

    request: ReferenceBuildRequest
    manifest: BuildManifest
    data: bytes

    @property
    def build_fingerprint(self):
        return self.manifest.build_fingerprint

    @property
    def archive_sha256(self):
        return hashlib.sha256(self.data).hexdigest()


def prepare_reference_build(alphabet, reference_directory, *, fasta_line_width=80):
    """Freeze a supported component-root request against reviewed offline pins."""
    import sys as _package_sys
    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')
    _package_route = None if _package_backend is None else _package_backend.current()
    if _package_route is not None:
        return _package_route.prepare(alphabet, reference_directory, fasta_line_width=fasta_line_width)
    construct, _, _ = load_reference_inputs(alphabet, reference_directory)
    return ReferenceBuildRequest(construct, fasta_line_width=fasta_line_width)


def build_reference_package(
    request: ReferenceBuildRequest,
    reference_directory,
    *,
    run_metadata: RunMetadata | None = None,
) -> ReferencePackage:
    """Build through accepted Components/Construct/Molecular stages, without IO output.

    Only the separately curated DNA/RNA CDS reference is supported. The supplied
    request remains authoritative; deriving a registry from pinned reference inputs
    cannot relax its selected identity, source, target or layout requirements.
    """
    import sys as _package_sys
    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')
    _package_route = None if _package_backend is None else _package_backend.current()
    if _package_route is not None:
        return _package_route.build(request, reference_directory, run_metadata=run_metadata)
    require(
        isinstance(request, ReferenceBuildRequest),
        "Expected a frozen ReferenceBuildRequest; general intent compilation is unsupported.",
    )
    require_software_use(request.construct.target, boundary="export")
    _, reference, registry = load_reference_inputs(
        request.construct.target.payload_format.value, reference_directory
    )
    # Capture checked retained bytes before compilation. No later filesystem read
    # supplies different bytes to the packaged reference snapshot.
    retained = collect_reference_files(reference_directory, reference)
    manifests = {reference.reference_set_id: reference}
    build = run_molecular_pipeline(request.construct, registry, manifests)
    exported = export_reference_sequence(
        request.construct,
        build.construct,
        build.candidate,
        registry,
        manifests,
        line_width=request.fasta_line_width,
    )
    records = tuple(
        build.manager.get(stage) for stage in ("components", "construct", "molecular")
    )
    # Re-query completion before taking the immutable package snapshot.
    completion = build.manager.result("molecular", scope="exact_cds")
    files = {}
    roles = {}

    def add(path, role, content):
        files[path] = content
        roles[path] = role

    add("request.json", "request", _json_bytes(request.to_dict()))
    add("inputs/registry.json", "registry", _json_bytes(registry.to_dict()))
    for record in records:
        add(
            f"stages/{record.id}.json",
            f"{record.id}-stage",
            _json_bytes(record.to_dict()),
        )
    add("molecular.json", "molecular-specification", exported.specification_bytes)
    add("sequence.fasta", "sequence", exported.fasta_bytes)
    checks = {
        "composition": check_composition(request.construct.composition, registry),
        "construct": check_construct(
            request.construct, build.construct, registry, manifests
        ),
        "molecular": build.check_result,
    }
    for name, result in checks.items():
        require(result.passed, "A current independent check failed during packaging.")
        add(f"checks/{name}.json", f"{name}-check", _json_bytes(result.to_dict()))
    summary = {
        "schema_version": "biocompiler.reference_build_summary.v0.2",
        "intended_use": "software_test",
        "human_therapeutic_admission": "not_admitted",
        "status": completion.status.value,
        "scope": completion.scope,
        "request_fingerprint": request.fingerprint,
        "selected_alternatives": [
            item.to_dict() for item in request.construct.references
        ],
        "feature_map": [
            item.to_dict() for item in build.candidate.records[0].feature_statuses
        ],
        "source_maps": {
            record.id: record.to_dict()["provenance"] for record in records
        },
        "unresolved": [item.to_dict() for item in completion.unresolved],
        "model_locks": [],
        "model_scope": "Sequence-reference components supply no dynamic model or biological refinement evidence.",
        "upstream_intent": None,
        "upstream_scope": "This component-root reference request has no accepted upstream intent or behavior realization.",
    }
    add("result.json", "build-summary", _json_bytes(summary))
    for path, content in retained.items():
        add(
            f"references/{reference.reference_set_id}/{path}",
            "reference-input",
            content,
        )
    entries = tuple(
        PackageFile(
            path, roles[path], hashlib.sha256(content).hexdigest(), len(content)
        )
        for path, content in sorted(files.items())
    )
    stages = tuple(
        AcceptedStage(
            record.id,
            fingerprint(record.payload),
            record.fingerprint,
            record.payload["schema_version"],
        )
        for record in records
    )
    from biocompiler import __version__

    manifest = BuildManifest(
        request_fingerprint=request.fingerprint,
        files=entries,
        accepted_stages=stages,
        toolchain=_tools(),
        package_version=__version__,
    )
    return ReferencePackage(
        request, manifest, assemble_archive(manifest, files, run_metadata)
    )


def verify_reference_package(
    data: bytes,
    *,
    expected_request: ReferenceBuildRequest | None = None,
    expected_build_fingerprint: str | None = None,
) -> ReferencePackage:
    """Reconstruct offline with current tools and caller-trusted request/build identity.

    Neither a self-reported manifest fingerprint nor serialized PASS records are
    authority. At least one expected identity must be supplied independently.
    Inspection without authority is available through read_archive instead.
    """
    import sys as _package_sys
    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')
    _package_route = None if _package_backend is None else _package_backend.current()
    if _package_route is not None:
        return _package_route.reconstruct(data, expected_request=expected_request, expected_build_fingerprint=expected_build_fingerprint)
    require(
        expected_request is not None or expected_build_fingerprint is not None,
        "Fresh verification requires an independently trusted request or build fingerprint.",
    )
    require(
        expected_request is None or isinstance(expected_request, ReferenceBuildRequest),
        "Expected a frozen ReferenceBuildRequest.",
    )
    manifest, files, metadata = read_archive(data)
    require(isinstance(manifest, BuildManifest), "Expected a reference package.")
    try:
        request = ReferenceBuildRequest.from_json(files["request.json"].decode("utf-8"))
    except UnicodeError as error:
        raise SerializationError("Packaged request must be UTF-8 JSON.") from error
    if expected_request is not None:
        require(
            request == expected_request,
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
    require_software_use(request.construct.target, boundary="verification")
    prefix = f"references/{MANIFEST_PIN.id}/"
    # read_archive has already rejected traversal, duplicate and symlink entries.
    with tempfile.TemporaryDirectory(prefix="biocompiler-reference-") as temporary:
        root = Path(temporary)
        for path, content in files.items():
            if path.startswith(prefix):
                destination = root / path[len(prefix) :]
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
        rebuilt = build_reference_package(request, root, run_metadata=metadata)
    require(
        rebuilt.manifest == manifest,
        "Package identities or evidence are stale, altered or unsupported by current tools.",
    )
    require(
        rebuilt.data == data,
        "Package content differs from current independent offline reconstruction.",
    )
    return rebuilt


def publish_reference_package(package: ReferencePackage, output) -> Path:
    """Recheck current package evidence, then atomically replace a single archive."""
    import sys as _package_sys
    _package_backend = _package_sys.modules.get('biocompiler.reference_package_backend')
    _package_route = None if _package_backend is None else _package_backend.current()
    if _package_route is not None:
        return _package_route.publish(package, output)
    require(isinstance(package, ReferencePackage), "Expected a reference package.")
    checked = verify_reference_package(
        package.data,
        expected_request=package.request,
        expected_build_fingerprint=package.manifest.build_fingerprint,
    )
    return write_archive_atomic(output, checked.data)
