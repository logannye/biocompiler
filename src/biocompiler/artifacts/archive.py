"""Deterministic, bounded build archives and atomic file publication.

Archive inspection verifies container structure and declared byte identities. It
never grants scientific or compiler acceptance; consumers recheck current frozen
inputs and evidence before publishing or reusing an imported package.
"""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import tempfile
from types import MappingProxyType
import zipfile

from biocompiler.artifacts.manifest import BuildManifest, RunMetadata
from biocompiler.artifacts.molecular_design import MolecularDesignBuildManifest
from biocompiler.artifacts.synthetic_build import SyntheticBuildManifest
from biocompiler.errors import SerializationError
from biocompiler.ir.serialization import parse_json, require

ARCHIVE_VERSION = "biocompiler.reference_archive.v0.4"
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_METADATA_BYTES = 1024 * 1024
MAX_ENTRIES = 128
MAX_PATH_BYTES = 1024
_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_FILE_MODE = stat.S_IFREG | 0o644
_RESERVED = frozenset({"manifest.json", "run.json"})


def _safe_path(path):
    require(isinstance(path, str) and bool(path), "Archive member path must be text.")
    require(
        not path.startswith("/")
        and "\\" not in path
        and ":" not in path
        and not any(ord(char) < 32 or ord(char) == 127 for char in path)
        and all(part not in {"", ".", ".."} for part in path.split("/"))
        and str(PurePosixPath(path)) == path,
        "Archive member paths must be canonical relative POSIX files.",
    )
    try:
        encoded = path.encode("utf-8")
    except UnicodeEncodeError as error:
        raise SerializationError("Archive member path is not valid UTF-8.") from error
    require(len(encoded) <= MAX_PATH_BYTES, "Archive member path is too long.")
    return path


def _json_bytes(artifact):
    try:
        return (artifact.to_json(indent=2) + "\n").encode("utf-8")
    except UnicodeEncodeError as error:
        raise SerializationError("Archive metadata is not valid UTF-8.") from error


def _files(manifest, files):
    require(
        isinstance(
            manifest,
            (BuildManifest, SyntheticBuildManifest, MolecularDesignBuildManifest),
        ),
        "Expected a build manifest.",
    )
    require(isinstance(files, Mapping), "Package files must be a byte mapping.")
    expected = {item.path: item for item in manifest.files}
    require(len(expected) == len(manifest.files), "Duplicate manifest member paths.")
    actual = {}
    total = 0
    for path, payload in files.items():
        _safe_path(path)
        require(
            path not in _RESERVED, "Package payload cannot replace archive metadata."
        )
        require(type(payload) is bytes, "Package payloads must be immutable bytes.")
        require(
            len(payload) <= MAX_MEMBER_BYTES, "Archive member exceeds the size limit."
        )
        total += len(payload)
        require(
            total <= MAX_ARCHIVE_BYTES, "Archive payload exceeds the total size limit."
        )
        actual[path] = payload
    require(
        set(actual) == set(expected),
        "Archive file inventory differs from the manifest.",
    )
    for path, payload in actual.items():
        declared = expected[path]
        require(
            len(payload) == declared.byte_length
            and hashlib.sha256(payload).hexdigest() == declared.sha256,
            f"Archive member size or SHA-256 mismatch: {path}.",
        )
    return actual


def _canonical_zip(entries):
    require(0 < len(entries) <= MAX_ENTRIES, "Archive member count exceeds the limit.")
    total = sum(len(value) for value in entries.values())
    require(total <= MAX_ARCHIVE_BYTES, "Archive contents exceed the total size limit.")
    buffer = io.BytesIO()
    with zipfile.ZipFile(
        buffer, "w", compression=zipfile.ZIP_STORED, allowZip64=False
    ) as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=_TIMESTAMP)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = _FILE_MODE << 16
            info.internal_attr = 0
            archive.writestr(info, entries[name])
    result = buffer.getvalue()
    require(len(result) <= MAX_ARCHIVE_BYTES, "Archive exceeds the byte-size limit.")
    return result


def assemble_archive(
    manifest: BuildManifest | SyntheticBuildManifest | MolecularDesignBuildManifest,
    files: Mapping[str, bytes],
    run_metadata: RunMetadata | None = None,
) -> bytes:
    """Create canonical stored ZIP bytes without importing acceptance receipts.

    ``files`` contains only manifest-declared core files. Optional run metadata is
    archived separately and does not change the manifest's build fingerprint.
    """
    entries = _files(manifest, files)
    require(
        run_metadata is None or isinstance(run_metadata, RunMetadata),
        "Invalid run metadata.",
    )
    entries["manifest.json"] = _json_bytes(manifest)
    if run_metadata is not None:
        entries["run.json"] = _json_bytes(run_metadata)
    require(
        all(
            len(entries[key]) <= MAX_METADATA_BYTES
            for key in _RESERVED
            if key in entries
        ),
        "Archive metadata exceeds the size limit.",
    )
    return _canonical_zip(entries)


def _preflight(data):
    require(type(data) is bytes, "Archive input must be immutable bytes.")
    require(
        22 <= len(data) <= MAX_ARCHIVE_BYTES,
        "Archive is empty or exceeds the byte-size limit.",
    )
    # Read the fixed, comment-free footer before ZipFile allocates any member
    # inventory. A malicious directory cannot bypass count limits by lying in
    # the end record and making ZipFile scan a huge directory first.
    footer = struct.unpack("<4s4H2LH", data[-22:])
    (
        signature,
        disk,
        directory_disk,
        disk_count,
        count,
        directory_size,
        directory_offset,
        comment_length,
    ) = footer
    require(
        signature == b"PK\x05\x06"
        and disk == directory_disk == comment_length == 0
        and disk_count == count
        and 0 < count <= MAX_ENTRIES,
        "Unsupported ZIP footer, comment, disk layout or member count.",
    )
    directory_end = len(data) - 22
    require(
        directory_offset + directory_size == directory_end,
        "ZIP has trailing data or an invalid directory.",
    )
    cursor = directory_offset
    for _ in range(count):
        require(
            cursor + 46 <= directory_end and data[cursor : cursor + 4] == b"PK\x01\x02",
            "Invalid ZIP member directory.",
        )
        name_size, extra_size, comment_size = struct.unpack_from(
            "<3H", data, cursor + 28
        )
        require(
            0 < name_size <= MAX_PATH_BYTES and extra_size == comment_size == 0,
            "Unsupported ZIP member name, extra data or comment.",
        )
        cursor += 46 + name_size
        require(cursor <= directory_end, "ZIP member directory is truncated.")
    require(cursor == directory_end, "ZIP directory member count is inconsistent.")


def read_archive(data: bytes):
    """Strictly inspect canonical bytes; return manifest, immutable files and run metadata.

    No archive member is extracted. Stored member sizes, names, hashes and complete
    inventory are checked before the returned files can be used by a caller.
    This function does not execute code, fetch dependencies or trust a success flag.
    """
    _preflight(data)
    entries = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data), "r", allowZip64=False) as archive:
            inventory = archive.infolist()
            require(
                0 < len(inventory) <= MAX_ENTRIES,
                "Archive member count exceeds the limit.",
            )
            total = 0
            for item in inventory:
                path = _safe_path(item.filename)
                require(path not in entries, "Duplicate archive member path.")
                require(
                    not item.is_dir()
                    and item.orig_filename == item.filename
                    and item.create_system == 3
                    and item.external_attr == _FILE_MODE << 16
                    and item.internal_attr == 0,
                    "Archive members must be regular, non-executable files.",
                )
                require(
                    item.compress_type == zipfile.ZIP_STORED
                    and item.compress_size == item.file_size
                    and item.flag_bits in {0, 0x800}
                    and item.date_time == _TIMESTAMP
                    and not item.extra
                    and not item.comment,
                    "Archive member violates the canonical stored-ZIP policy.",
                )
                limit = MAX_METADATA_BYTES if path in _RESERVED else MAX_MEMBER_BYTES
                require(
                    item.file_size <= limit, "Archive member exceeds the size limit."
                )
                total += item.file_size
                require(
                    total <= MAX_ARCHIVE_BYTES,
                    "Archive contents exceed the total size limit.",
                )
                payload = archive.read(item)
                require(len(payload) == item.file_size, "Archive member is truncated.")
                entries[path] = payload
    except SerializationError:
        raise
    except (
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        OSError,
        ValueError,
        RuntimeError,
        UnicodeError,
        EOFError,
    ) as error:
        raise SerializationError(f"Invalid reference archive: {error}") from error
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


def write_archive_atomic(path, data: bytes) -> Path:
    """Validate then atomically replace one .bcb file, preserving prior bytes on failure.

    Compiler acceptance must be freshly checked before calling this structural
    publication helper. A sibling temporary file is flushed and synced before
    ``os.replace``; prepublication failures remove the temporary file.
    """
    read_archive(data)
    destination = Path(path)
    require(destination.suffix == ".bcb", "Build archives require a .bcb destination.")
    require(
        destination.parent.is_dir(), "Archive destination parent must already exist."
    )
    if destination.exists() or destination.is_symlink():
        require(
            not destination.is_symlink() and destination.is_file(),
            "Archive destination must be a regular file, not a directory or symlink.",
        )
    descriptor = None
    temporary = None
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix="." + destination.name + ".", suffix=".tmp", dir=destination.parent
        )
        with os.fdopen(descriptor, "wb") as output:
            descriptor = None
            written = output.write(data)
            if written != len(data):
                raise OSError("Incomplete reference archive write.")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, destination)
        temporary = None
        return destination
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
