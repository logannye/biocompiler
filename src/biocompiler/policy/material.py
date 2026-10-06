"""Inert material requests and fresh native paired publication."""
from __future__ import annotations

import os
import struct
from pathlib import Path
import tempfile
from typing import Callable, Iterable, cast
import zipfile
import zlib

from biocompiler.core_client import CoreProtocolError, JsonValue, decode_json, encode_json
from biocompiler.core_policy_material import (
    REQUEST_PROFILE, REQUEST_SCHEMA, PolicyMaterialClient, PolicyMaterialResult, _original,
)


def prepare_request(*, implementation_request: JsonValue, material_contract: JsonValue,
                    context: JsonValue, catalog_binding: JsonValue, budgets: JsonValue) -> dict[str, JsonValue]:
    """Snapshot the caller's full authority without performing admission."""
    request: JsonValue = {"schema_version": REQUEST_SCHEMA, "profile": REQUEST_PROFILE,
        "implementation_request": implementation_request, "material_contract": material_contract,
        "context": context, "catalog_binding": catalog_binding, "budgets": budgets}
    return cast(dict[str, JsonValue], _original(decode_json(encode_json(request))))


def compile(request: JsonValue, *, limits: JsonValue, client: PolicyMaterialClient,
            cancelled: Callable[[], bool] | None = None) -> PolicyMaterialResult:
    return client.compile(request, limits, cancelled=cancelled)


def check(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, client: PolicyMaterialClient,
          cancelled: Callable[[], bool] | None = None) -> PolicyMaterialResult:
    return client.check(request, candidate, limits, cancelled=cancelled)


def replay(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, report: JsonValue,
           client: PolicyMaterialClient, cancelled: Callable[[], bool] | None = None) -> PolicyMaterialResult:
    """Replay the entire saved wrapper under the supplied original authority."""
    return client.replay(request, candidate, limits, report, cancelled=cancelled)


def _destination(output: Path, input_paths: Iterable[Path], *, replace: bool) -> Path:
    if output.suffix.lower() != ".zip":
        raise ValueError("Material export requires one .zip destination for the complete pair")
    if output.is_symlink():
        raise ValueError("Material export cannot replace a symbolic link")
    destination = output.resolve()
    if destination.exists() and not destination.is_file():
        raise ValueError("Material export destination must be a regular file")
    if destination.exists() and not replace:
        raise FileExistsError("Material export destination exists; explicit replacement is required")
    for supplied in input_paths:
        original = supplied.resolve()
        if destination == original or (destination.exists() and original.exists() and os.path.samefile(destination, original)):
            raise ValueError("Material export cannot overwrite or alias an original input")
    return destination


def _verify_staged(path: Path, members: tuple[tuple[str, bytes], ...]) -> None:
    """Read back the bounded stored ZIP before it can become the output."""
    # Fixed ASCII names, no extras/comments, and a seekable file require exactly
    # one local header and central entry per member plus the end record.
    expected_size = 22 + sum(30 + 46 + 2 * len(name.encode("ascii")) + len(content) for name, content in members)
    if path.stat().st_size != expected_size:
        raise CoreProtocolError("Staged material archive was truncated or changed size")
    with path.open("rb") as staged:
        archive_bytes = staged.read(expected_size + 1)
    if len(archive_bytes) != expected_size:
        raise CoreProtocolError("Staged material archive changed during bounded readback")
    # Compare every byte against the fixed stored-ZIP format independently of
    # the writer/parser. ZipFile uses central-directory metadata when reading
    # and does not validate every corresponding local-header field.
    cursor = 0
    view = memoryview(archive_bytes)
    def expect(expected: bytes) -> None:
        nonlocal cursor
        if view[cursor:cursor + len(expected)] != expected:
            raise CoreProtocolError("Staged material archive differs from exact native bytes or fixed ZIP metadata")
        cursor += len(expected)

    central_entries: list[bytes] = []
    for name, content in members:
        encoded_name = name.encode("ascii")
        size, crc, local_offset = len(content), zlib.crc32(content), cursor
        # DOS time/date 0/33 is 1980-01-01 00:00:00; all optional fields are empty.
        expect(struct.pack("<4s5H3I2H", b"PK\x03\x04", 20, 0, 0, 0, 33,
                           crc, size, size, len(encoded_name), 0))
        expect(encoded_name)
        expect(content)
        central_entries.append(struct.pack("<4s6H3I5H2I", b"PK\x01\x02", (3 << 8) | 20, 20, 0, 0, 0, 33,
            crc, size, size, len(encoded_name), 0, 0, 0, 0, 0o100644 << 16, local_offset) + encoded_name)
    central_offset = cursor
    for entry in central_entries:
        expect(entry)
    central_size = cursor - central_offset
    expect(struct.pack("<4s4H2IH", b"PK\x05\x06", 0, 0, len(members), len(members), central_size, central_offset, 0))
    if cursor != expected_size:
        raise CoreProtocolError("Staged material archive changed its complete byte inventory")


def export(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, client: PolicyMaterialClient,
           output: Path, input_paths: Iterable[Path] = (), replace: bool = False,
           cancelled: Callable[[], bool] | None = None) -> PolicyMaterialResult:
    """Fresh native export, then atomically publish its exact pair in one archive.

    No saved result is accepted as publication authority. Archive order,
    timestamps, permissions and compression are fixed for reproducible bytes.
    """
    paths = tuple(Path(value) for value in input_paths)
    output = Path(output)
    destination = _destination(output, paths, replace=replace)
    result = client.export(request, candidate, limits, cancelled=cancelled)
    artifact = result.artifact
    if result.operation != "export-policy-material" or result.status != "checked_material" or artifact is None:
        raise CoreProtocolError("Publication requires a fresh native accepted material export")
    fasta = artifact.get("fasta")
    if type(fasta) is not str:
        raise CoreProtocolError("Native export did not return exact FASTA bytes")
    members = (("program.fasta", fasta.encode("utf-8")), ("manifest.json", encode_json(artifact["manifest"])))
    temporary: Path | None = None
    try:
        # Recheck after native work: a user may have changed a path while the
        # checker was running. No input is read or overwritten by publication.
        if _destination(output, paths, replace=replace) != destination:
            raise ValueError("Material export destination changed during checking")
        with tempfile.NamedTemporaryFile(mode="w+b", prefix=".policy-material-", suffix=".tmp", dir=destination.parent, delete=False) as handle:
            temporary = Path(handle.name)
            with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
                for name, content in members:
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_STORED
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, content)
            handle.flush()
            os.fsync(handle.fileno())
        if cancelled is not None and cancelled():
            from biocompiler.core_client import CoreCancelled
            raise CoreCancelled("Material publication cancelled before atomic replacement")
        if _destination(output, paths, replace=replace) != destination:
            raise ValueError("Material export destination changed during publication")
        _verify_staged(temporary, members)
        if replace:
            os.replace(temporary, destination)
            temporary = None
        else:
            # Exclusive publication is atomic even when another writer creates
            # the destination after our final preflight.
            os.link(temporary, destination)
            temporary.unlink()
            temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return result
