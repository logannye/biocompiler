"""Supported build manifest dispatch over the shared bounded ZIP container."""

from collections.abc import Mapping
import os as os
from types import MappingProxyType

from biocompiler.artifacts.manifest import BuildManifest, RunMetadata
from biocompiler.artifacts.molecular_design import MolecularDesignBuildManifest
from biocompiler.artifacts.synthetic_build import SyntheticBuildManifest
from biocompiler.artifacts.circuit_review import CircuitReviewManifest
from biocompiler.artifacts.archive_container import (
    ARCHIVE_VERSION as ARCHIVE_VERSION,
    MAX_ARCHIVE_BYTES as MAX_ARCHIVE_BYTES,
    MAX_MEMBER_BYTES as MAX_MEMBER_BYTES,
    MAX_METADATA_BYTES as MAX_METADATA_BYTES,
    MAX_ENTRIES as MAX_ENTRIES,
    MAX_PATH_BYTES as MAX_PATH_BYTES,
    _RESERVED,
    _canonical_zip as _canonical_zip,
    assemble_container,
    read_container,
    validate_files,
    write_container_atomic,
)
from biocompiler.errors import SerializationError
from biocompiler.ir.serialization import parse_json, require

_MANIFEST_TYPES = (
    BuildManifest,
    SyntheticBuildManifest,
    MolecularDesignBuildManifest,
    CircuitReviewManifest,
)


def _files(manifest, files):
    require(isinstance(manifest, _MANIFEST_TYPES), "Expected a build manifest.")
    return validate_files(manifest, files)


def assemble_archive(manifest, files: Mapping[str, bytes], run_metadata=None) -> bytes:
    """Create canonical bytes; metadata does not change canonical identity."""
    _files(manifest, files)
    require(
        run_metadata is None or isinstance(run_metadata, RunMetadata),
        "Invalid run metadata.",
    )
    return assemble_container(manifest, files, run_metadata)


def read_archive(data: bytes):
    """Inspect typed inventory integrity only, without granting acceptance."""
    entries = read_container(data)
    require("manifest.json" in entries, "Archive has no build manifest.")
    try:
        document = parse_json(entries["manifest.json"].decode("utf-8"))
        require(isinstance(document, dict), "Archive manifest must be an object.")
        schema = document.get("schema_version")
        require(isinstance(schema, str), "Archive manifest schema must be text.")
        manifest_type = {
            BuildManifest.schema_version: BuildManifest,
            SyntheticBuildManifest.schema_version: SyntheticBuildManifest,
            MolecularDesignBuildManifest.schema_version: MolecularDesignBuildManifest,
            CircuitReviewManifest.schema_version: CircuitReviewManifest,
        }.get(schema)
        require(manifest_type is not None, "Unsupported archive manifest schema.")
        manifest = manifest_type.from_dict(document)
        metadata = (
            RunMetadata.from_json(entries["run.json"].decode("utf-8"))
            if "run.json" in entries
            else None
        )
    except UnicodeDecodeError as error:
        raise SerializationError("Archive metadata is not UTF-8 JSON.") from error
    files = {
        name: payload for name, payload in entries.items() if name not in _RESERVED
    }
    validated = _files(manifest, files)
    require(
        assemble_archive(manifest, validated, metadata) == data,
        "Archive bytes are not canonical for the declared files and metadata.",
    )
    return manifest, MappingProxyType(validated), metadata


def write_archive_atomic(path, data: bytes):
    """Validate supported archive structure then atomically publish one .bcb."""
    read_archive(data)
    return write_container_atomic(path, data)
