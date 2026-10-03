"""Reproducible software molecular-design packages under independent authority."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from urllib.parse import quote, unquote_to_bytes

from biocompiler.artifacts.archive import (
    ARCHIVE_VERSION,
    assemble_archive,
    read_archive,
    write_archive_atomic,
)
from biocompiler.artifacts.manifest import RunMetadata, ToolPin, _portable_sources
from biocompiler.artifacts.molecular_design import (
    HANDOFF_VERSION,
    REQUIRED_FILES,
    MolecularDesignBuildManifest,
    MolecularDesignHandoff,
    MolecularDesignPackageFile,
)
from biocompiler.backends.molecular_design import EMITTER_VERSION
from biocompiler.compiler.molecular_design import (
    PIPELINE_VERSION,
    run_molecular_design_pipeline,
)
from biocompiler.errors import SerializationError
from biocompiler.ir.molecular_design import PROFILE_VERSION, MolecularDesignRequest
from biocompiler.ir.payload import PAYLOAD_PROFILE_VERSION, PayloadMolecule
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
from biocompiler.synthesis.molecular_design import GENERATOR_VERSION
from biocompiler.verification.admission import require_software_use
from biocompiler.verification.molecular_design import (
    CHECKER_VERSION,
    check_molecular_design,
    check_molecular_design_construct,
    check_molecular_design_request,
)

MOLECULAR_DESIGN_BUILD_VERSION = "biocompiler.molecular_design_build.v0.1"
FASTA_POLICY_VERSION = "biocompiler.molecular_design_fasta.v0.1"
FASTA_LINE_WIDTH = 80


def _json_bytes(value):
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _tools():
    versions = {
        "molecular_design_build": MOLECULAR_DESIGN_BUILD_VERSION,
        "archive": ARCHIVE_VERSION,
        "human_admission_policy": ADMISSION_POLICY_VERSION,
        "design_profile": PROFILE_VERSION,
        "payload_profile": PAYLOAD_PROFILE_VERSION,
        "design_generator": GENERATOR_VERSION,
        "design_emitter": EMITTER_VERSION,
        "design_pipeline": PIPELINE_VERSION,
        "design_checker": CHECKER_VERSION,
        "design_fasta": FASTA_POLICY_VERSION,
        "design_handoff": HANDOFF_VERSION,
    }
    return tuple(
        ToolPin(key, value, fingerprint(value))
        for key, value in sorted(versions.items())
    )


def _verify_fasta(data, molecule):
    """Check serialized symbols and identity separately from the assembly path."""
    require(type(data) is bytes, "Molecular design FASTA must be immutable bytes.")
    require(isinstance(molecule, PayloadMolecule), "Expected an exact molecule.")
    try:
        text = data.decode("ascii")
    except UnicodeError as error:
        raise SerializationError("Molecular design FASTA must be ASCII.") from error
    lines = text.split("\n")
    require(
        len(lines) >= 3 and lines[-1] == "" and "\r" not in text,
        "Molecular design FASTA requires LF lines and a terminal newline.",
    )
    require(lines[0].startswith(">"), "Molecular design FASTA requires one header.")
    tokens = lines[0][1:].split(" ")
    require(len(tokens) == 5, "Molecular design FASTA header has invalid fields.")
    try:
        identifier = unquote_to_bytes(tokens[0]).decode("utf-8")
    except UnicodeError as error:
        raise SerializationError(
            "Molecular design FASTA identifier is invalid."
        ) from error
    require(
        identifier == molecule.id
        and quote(identifier, safe="-._~") == tokens[0]
        and tokens[1:]
        == [
            "alphabet=RNA",
            "scope=software_molecular_design",
            "use=software_test",
            "human_admission=not_admitted",
        ],
        "Molecular design FASTA changed nominal identity, alphabet or use scope.",
    )
    body = lines[1:-1]
    require(
        bool(body)
        and all(0 < len(line) <= FASTA_LINE_WIDTH for line in body)
        and all(len(line) == FASTA_LINE_WIDTH for line in body[:-1])
        and all(set(line) <= set("ACGU") for line in body),
        "Molecular design FASTA violates exact wrapping or RNA spelling.",
    )
    sequence = "".join(body)
    require(
        sequence == molecule.sequence
        and hashlib.sha256(sequence.encode("ascii")).hexdigest()
        == molecule.sequence_sha256,
        "Molecular design FASTA differs from checked nucleotide identity.",
    )


def _fasta(molecule):
    header = (
        ">"
        + quote(molecule.id, safe="-._~")
        + " alphabet=RNA scope=software_molecular_design use=software_test"
        + " human_admission=not_admitted\n"
    )
    body = "".join(
        molecule.sequence[start : start + FASTA_LINE_WIDTH] + "\n"
        for start in range(0, len(molecule.sequence), FASTA_LINE_WIDTH)
    )
    data = (header + body).encode("ascii")
    _verify_fasta(data, molecule)
    return data


@dataclass(frozen=True)
class MolecularDesignPackage:
    """Portable bytes and authority, freshly reconstructed before publication."""

    request: MolecularDesignRequest
    manifest: MolecularDesignBuildManifest
    data: bytes

    @property
    def build_fingerprint(self):
        return self.manifest.build_fingerprint

    @property
    def archive_sha256(self):
        return hashlib.sha256(self.data).hexdigest()


def build_molecular_design_package(
    request: MolecularDesignRequest, *, run_metadata: RunMetadata | None = None
) -> MolecularDesignPackage:
    """Build one exact software structural design from fully frozen authority.

    The request supplies all retained fragments and layout choices. No network,
    authoring execution, sequence optimization or biological admission occurs.
    """
    require(
        isinstance(request, MolecularDesignRequest), "Expected MolecularDesignRequest."
    )
    _portable_sources(request.to_dict())
    require_software_use(request.target, boundary="export")
    pin = request.fingerprint
    build = run_molecular_design_pipeline(request, expected_request_fingerprint=pin)
    checks = {
        "request": check_molecular_design_request(
            request, expected_request_fingerprint=pin
        ),
        "construct": check_molecular_design_construct(
            request, build.construct, expected_request_fingerprint=pin
        ),
        "molecular": check_molecular_design(
            request,
            build.construct,
            build.candidate,
            expected_request_fingerprint=pin,
        ),
    }
    require(
        all(item.passed for item in checks.values()),
        "Independent molecular design checks did not all pass.",
    )
    completion = build.manager.result("molecular", scope="software_molecular_design")
    require(
        completion.status.value == "complete",
        "Software molecular design scope is incomplete.",
    )
    records = tuple(
        build.manager.get(stage) for stage in ("components", "construct", "molecular")
    )
    molecule = build.candidate.molecule
    handoff = MolecularDesignHandoff(
        pin,
        build.candidate.fingerprint,
        molecule.fingerprint,
        molecule.id,
        molecule.sequence_sha256,
        len(molecule.sequence),
        molecule.features,
    )
    documents = {
        "request.json": request.to_dict(),
        "inputs/fragments.json": {
            "schema_version": "biocompiler.molecular_design_fragments.v0.1",
            "request_fingerprint": pin,
            "fragments": [item.to_dict() for item in request.fragments],
        },
        "inputs/layout.json": {
            "schema_version": "biocompiler.molecular_design_layout.v0.1",
            "request_fingerprint": pin,
            "molecule_id": request.molecule_id,
            "placements": [item.to_dict() for item in request.placements],
            "features": [item.to_dict() for item in request.features],
            "unknown_features": list(request.unknown_features),
        },
        "construct.json": build.construct.to_dict(),
        "candidate.json": build.candidate.to_dict(),
        "molecular.json": molecule.to_dict(),
        "source-map.json": {
            "schema_version": "biocompiler.molecular_design_source_map.v0.1",
            "request_fingerprint": pin,
            "candidate_fingerprint": build.candidate.fingerprint,
            "placements": [item.to_dict() for item in build.candidate.source_maps],
            "upstream_intent": None,
            "claim_scope": "Exact supplied fragment/layout correspondence; no inferred behavioral implementation.",
        },
        "handoff.json": handoff.to_dict(),
        **{f"checks/{key}.json": item.to_dict() for key, item in checks.items()},
        **{f"stages/{record.id}.json": record.to_dict() for record in records},
        "result.json": {
            "schema_version": "biocompiler.molecular_design_build_summary.v0.1",
            "status": completion.status.value,
            "scope": completion.scope,
            "intended_use": "software_test",
            "reference_promotion": "not_promoted",
            "human_therapeutic_admission": "not_admitted",
            "request_fingerprint": pin,
            "candidate_fingerprint": build.candidate.fingerprint,
            "molecule_fingerprint": molecule.fingerprint,
            "sequence_sha256": molecule.sequence_sha256,
            "sequence_length": len(molecule.sequence),
            "handoff_fingerprint": handoff.fingerprint,
            "fasta_policy": FASTA_POLICY_VERSION,
            "fasta_line_width": FASTA_LINE_WIDTH,
            "stages": [
                {
                    "id": record.id,
                    "fingerprint": record.fingerprint,
                    "payload_fingerprint": fingerprint(record.payload),
                }
                for record in records
            ],
            "unresolved": [item.to_dict() for item in completion.unresolved],
            "unresolved_handoff_claims": list(handoff.unresolved_claims),
            "claim_scope": "Complete nominal mature RNA design under the software structural profile; no behavior, empirical, material-quality or clinical-use acceptance.",
        },
    }
    files = {path: _json_bytes(value) for path, value in documents.items()}
    files["sequence.fasta"] = _fasta(molecule)
    entries = tuple(
        MolecularDesignPackageFile(
            path,
            REQUIRED_FILES[path],
            hashlib.sha256(content).hexdigest(),
            len(content),
        )
        for path, content in files.items()
    )
    from biocompiler import __version__

    manifest = MolecularDesignBuildManifest(pin, entries, _tools(), __version__)
    return MolecularDesignPackage(
        request, manifest, assemble_archive(manifest, files, run_metadata)
    )


def verify_molecular_design_package(
    data: bytes,
    *,
    expected_request: MolecularDesignRequest | None = None,
    expected_build_fingerprint: str | None = None,
) -> MolecularDesignPackage:
    """Reconstruct every canonical byte against independent full request/build authority."""
    require(
        expected_request is not None or expected_build_fingerprint is not None,
        "Fresh verification requires an independently trusted request or build fingerprint.",
    )
    require(
        expected_request is None
        or isinstance(expected_request, MolecularDesignRequest),
        "Expected a full MolecularDesignRequest as independent authority.",
    )
    manifest, files, metadata = read_archive(data)
    require(
        isinstance(manifest, MolecularDesignBuildManifest),
        "Expected a molecular design package.",
    )
    try:
        request = MolecularDesignRequest.from_json(
            files["request.json"].decode("utf-8")
        )
    except UnicodeError as error:
        raise SerializationError(
            "Packaged design request must be UTF-8 JSON."
        ) from error
    if expected_request is not None:
        require(
            request.fingerprint == expected_request.fingerprint,
            "Packaged design request differs from independent authority.",
        )
    if expected_build_fingerprint is not None:
        require(
            manifest.build_fingerprint == expected_build_fingerprint,
            "Packaged design differs from independently trusted build identity.",
        )
    require(
        manifest.request_fingerprint == request.fingerprint,
        "Packaged molecular design request fingerprint mismatch.",
    )
    require_software_use(request.target, boundary="verification")
    rebuilt = build_molecular_design_package(request, run_metadata=metadata)
    require(
        rebuilt.manifest == manifest,
        "Molecular design identities or evidence are stale, altered or unsupported by current tools.",
    )
    require(
        rebuilt.data == data,
        "Molecular design package differs from current independent offline reconstruction.",
    )
    return rebuilt


def publish_molecular_design_package(package: MolecularDesignPackage, output) -> Path:
    """Recheck complete nominal design evidence, then atomically publish one archive."""
    require(
        isinstance(package, MolecularDesignPackage), "Expected MolecularDesignPackage."
    )
    checked = verify_molecular_design_package(
        package.data,
        expected_request=package.request,
        expected_build_fingerprint=package.build_fingerprint,
    )
    return write_archive_atomic(output, checked.data)
