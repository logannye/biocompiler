"""Bounded POSIX artifact transport; bytes and receipts confer no acceptance.

The existing v1 JSON channel remains unchanged. This separate, opt-in channel
requires an exactly negotiated profile and inherited private file descriptors.
Only a profile-specific client can interpret the returned semantic receipt.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
import os
import re
import selectors
import subprocess
import tempfile
import time
from typing import BinaryIO, Callable, Iterator, cast
from uuid import uuid4

from biocompiler.core_client import (
    LIMITS, PROTOCOL, CoreCancelled, CoreClient, CoreProtocolError, CoreRejected,
    CoreResponse, CoreTimeout, CoreTransportError, CoreUnavailable, CoreUnsupported,
    JsonValue, _object, _response, _terminate, encode_json,
)

MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_ARTIFACT_NODES = 1_000_000
MAX_CONTROL_BYTES = 65_536
MAX_STDERR_BYTES = 1_048_576
ARTIFACT_OPERATIONS = ("run-verification-workflow", "replay-verification-workflow")
TRANSPORT_PROFILE: dict[str, JsonValue] = {
    "profile": "biocompiler.core.artifact_transport.v1",
    "operations": list(ARTIFACT_OPERATIONS),
    "arguments": "--artifact-fds-v1 authority-fd retained-record-fd-or-dash output-fd",
    "input_kind": "read_only_regular_files",
    "output_kind": "private_empty_regular_file",
    "max_authority_bytes": LIMITS["max_request_bytes"],
    "max_authority_nodes": LIMITS["max_json_nodes"],
    "max_record_bytes": MAX_ARTIFACT_BYTES,
    "max_record_nodes": MAX_ARTIFACT_NODES,
    "max_control_bytes": MAX_CONTROL_BYTES,
    "max_depth": LIMITS["max_depth"],
    "max_string_bytes": LIMITS["max_string_bytes"],
    "max_number_chars": LIMITS["max_number_chars"],
    "artifact_encoding": "python-json-v1",
    "node_accounting": "values_and_object_keys",
    "identity": "complete_bytes_sha256_and_length",
}
_PROFILE_BYTES = encode_json(TRANSPORT_PROFILE)
_TOKEN = re.compile(
    rb'[ \t\r\n]+|-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?'
    rb'|true|false|null|[{}\[\],:]')
_STRING_SPECIAL = re.compile(rb'["\\\x00-\x1f]')
_HEX_ESCAPE = re.compile(rb'u[0-9a-fA-F]{4}')


def _string_end(raw: bytes, start: int) -> int:
    # Skip plain runs in C without a repeated regex capture stack proportional
    # to a potentially oversized string. The decoder checks actual UTF-8 width.
    position = start + 1
    while True:
        special = _STRING_SPECIAL.search(raw, position)
        if special is None:
            raise CoreProtocolError("Incomplete artifact JSON string")
        offset = special.start()
        if offset - start > 6 * LIMITS["max_string_bytes"] + 1:
            raise CoreProtocolError("Artifact string budget exceeded")
        if raw[offset] == ord('"'):
            return offset + 1
        if raw[offset] != ord('\\') or offset + 1 >= len(raw):
            raise CoreProtocolError("Malformed artifact JSON string")
        escaped = raw[offset + 1]
        if escaped in b'"\\/bfnrt':
            position = offset + 2
        elif escaped == ord('u') and _HEX_ESCAPE.match(raw, offset + 1):
            position = offset + 6
        else:
            raise CoreProtocolError("Malformed artifact JSON escape")


def _preflight_bytes(raw: bytes, *, limit: int, nodes: int) -> None:
    """Bound token inventory and nesting before allocating the decoded tree."""
    if type(raw) is not bytes or not raw or len(raw) > limit:
        raise CoreProtocolError("Artifact byte budget exceeded or input is empty")
    offset = count = 0
    containers: list[int] = []
    while offset < len(raw):
        start = offset
        if raw[offset] == ord('"'):
            end = _string_end(raw, offset)
        else:
            match = _TOKEN.match(raw, offset)
            if match is None:
                raise CoreProtocolError("Malformed artifact JSON token")
            end = match.end()
        first = raw[start]
        offset = end
        if first in b" \t\r\n,:":
            continue
        if first in b"}]":
            if not containers or containers.pop() != first:
                raise CoreProtocolError("Malformed artifact JSON nesting")
            continue
        count += 1
        if count > nodes or len(containers) > LIMITS["max_depth"]:
            raise CoreProtocolError("Artifact node or depth budget exceeded")
        if first in b"{[":
            containers.append(ord("}") if first == ord("{") else ord("]"))
        elif first == ord('"'):
            if end - start > 6 * LIMITS["max_string_bytes"] + 2:
                raise CoreProtocolError("Artifact string budget exceeded")
        elif first in b"-0123456789" and end - start > LIMITS["max_number_chars"]:
            raise CoreProtocolError("Artifact number budget exceeded")
    if containers:
        raise CoreProtocolError("Incomplete artifact JSON")


def decode_artifact(raw: bytes, *, authority: bool = False) -> JsonValue:
    """Strict structural decoding only; never reconstructs semantic acceptance."""
    limit = LIMITS["max_request_bytes"] if authority else MAX_ARTIFACT_BYTES
    nodes = LIMITS["max_json_nodes"] if authority else MAX_ARTIFACT_NODES
    _preflight_bytes(raw, limit=limit, nodes=nodes)

    def pairs(items: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {}
        for key, value in items:
            if key in result:
                raise CoreProtocolError("Duplicate artifact JSON object key")
            result[key] = value
        return result

    def invalid(_value: str) -> None:
        raise CoreProtocolError("Nonfinite artifact JSON number")

    try:
        value = cast(JsonValue, json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                                          parse_constant=invalid))
        pending = [value]
        while pending:
            item = pending.pop()
            if type(item) is str:
                if len(item.encode("utf-8")) > LIMITS["max_string_bytes"]:
                    raise CoreProtocolError("Artifact string budget exceeded")
            elif type(item) is float and not math.isfinite(item):
                raise CoreProtocolError("Nonfinite artifact JSON number")
            elif type(item) is list:
                pending.extend(item)
            elif type(item) is dict:
                pending.extend(item.keys())
                pending.extend(item.values())
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CoreProtocolError("Malformed artifact JSON") from exc


def _canonical(value: JsonValue, limit: int) -> bytes:
    # Called only after the bounded byte-level decoder has checked the tree.
    output = bytearray()
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False)
    for text in encoder.iterencode(value):
        chunk = text.encode("utf-8")
        if len(output) + len(chunk) > limit:
            raise CoreProtocolError("Canonical artifact byte budget exceeded")
        output.extend(chunk)
    return bytes(output)


def _descriptor(raw: bytes) -> dict[str, JsonValue]:
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


@contextmanager
def _input_file(raw: bytes) -> Iterator[BinaryIO]:
    descriptor, name = tempfile.mkstemp(prefix="biocompiler-artifact-")
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(raw)
        with open(name, "rb") as source:
            os.unlink(name)
            yield source
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def _exchange_artifacts(core: CoreClient, request: bytes, arguments: tuple[str, ...],
                        files: tuple[BinaryIO, ...], output_file: BinaryIO,
                        output_limit: int, cancelled: Callable[[], bool] | None) -> tuple[bytes, int]:
    if os.name != "posix":
        raise CoreUnavailable("Artifact transport currently supports POSIX only")
    if cancelled is not None and cancelled():
        raise CoreCancelled("Artifact operation cancelled before execution")
    if not core.executable.is_file() or not os.access(core.executable, os.X_OK):
        raise CoreUnavailable("Selected core is not executable")
    if core.expected_sha256 is not None:
        with core.executable.open("rb") as binary:
            if hashlib.file_digest(binary, "sha256").hexdigest() != core.expected_sha256:
                raise CoreUnavailable("Selected executable does not match the supplied release pin")
    try:
        process = subprocess.Popen([str(core.executable), *arguments], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
            pass_fds=tuple(file.fileno() for file in files))
    except OSError as exc:
        raise CoreUnavailable("Cannot start selected artifact core") from exc
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    pipes = (process.stdin, process.stdout, process.stderr)
    sent = stderr_size = 0
    response = bytearray()
    deadline = time.monotonic() + core.timeout_seconds
    try:
        with selectors.DefaultSelector() as selector:
            for pipe in pipes:
                os.set_blocking(pipe.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map() or process.poll() is None:
                if cancelled is not None and cancelled():
                    raise CoreCancelled("Artifact operation cancelled")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise CoreTimeout("Artifact operation exceeded its time budget")
                if os.fstat(output_file.fileno()).st_size > output_limit:
                    raise CoreTransportError("Artifact output byte budget exceeded")
                for key, _ in selector.select(min(remaining, 0.05)):
                    if key.data == "stdin":
                        try:
                            sent += os.write(key.fd, request[sent:sent + 65_536])
                        except BlockingIOError:
                            continue
                        except BrokenPipeError as exc:
                            raise CoreTransportError("Incomplete artifact control request") from exc
                        if sent == len(request):
                            selector.unregister(key.fileobj)
                            process.stdin.close()
                    else:
                        chunk = os.read(key.fd, 65_536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            cast(BinaryIO, key.fileobj).close()
                        elif key.data == "stdout":
                            if len(response) + len(chunk) > MAX_CONTROL_BYTES:
                                raise CoreTransportError("Artifact control response byte budget exceeded")
                            response.extend(chunk)
                        else:
                            stderr_size += len(chunk)
                            if stderr_size > MAX_STDERR_BYTES:
                                raise CoreTransportError("Artifact stderr byte budget exceeded")
        if os.fstat(output_file.fileno()).st_size > output_limit:
            raise CoreTransportError("Artifact output byte budget exceeded")
        code = process.wait()
        if code not in (0, 2, 3):
            raise CoreTransportError(f"Artifact core failed with exit status {code}")
        return bytes(response), code
    except BaseException:
        _terminate(process)
        raise
    finally:
        for pipe in pipes:
            pipe.close()


@dataclass(frozen=True)
class ArtifactResponse:
    response: CoreResponse
    artifact: bytes
    # This wrapper binds transport bytes only. Profile-specific checks must
    # validate the semantic receipt before making an acceptance claim.


def call_artifact(core: CoreClient, operation: str, payload: JsonValue, *,
                  authority: bytes, retained_record: bytes | None = None,
                  output_limit: int = MAX_ARTIFACT_BYTES,
                  request_id: str | None = None,
                  cancelled: Callable[[], bool] | None = None) -> ArtifactResponse:
    """Freeze bytes before negotiation, reject partial output, return full bytes."""
    if (type(output_limit) is not int or not 0 < output_limit <= MAX_ARTIFACT_BYTES
            or type(operation) is not str or operation not in ARTIFACT_OPERATIONS):
        raise CoreProtocolError("Invalid artifact operation or output limit")
    decode_artifact(authority, authority=True)
    if retained_record is not None and (type(retained_record) is not bytes
            or not retained_record or len(retained_record) > MAX_ARTIFACT_BYTES):
        raise CoreProtocolError("Artifact byte budget exceeded or input is empty")
    authority_descriptor = _descriptor(authority)
    record_descriptor = None if retained_record is None else _descriptor(retained_record)
    identifier = str(uuid4()) if request_id is None else request_id
    if type(identifier) is not str or not identifier.strip():
        raise CoreProtocolError("Artifact request identity must be nonempty")
    # Freeze the caller's mutable control graph before running the executable.
    control: JsonValue = {"protocol": PROTOCOL, "request_id": identifier,
        "operation": operation, "payload": {
            "transport": "biocompiler.core.artifact_transport.v1",
            "authority": authority_descriptor, "retained_record": record_descriptor,
            "output_limit": output_limit, "operation_payload": payload}}
    request = encode_json(control, limit=MAX_CONTROL_BYTES)
    capabilities = core.negotiate(operation, cancelled=cancelled)
    advertised = capabilities.profiles.get("artifact_transport")
    if encode_json(advertised) != _PROFILE_BYTES:
        raise CoreProtocolError("Incompatible artifact transport profile")
    with ExitStack() as stack:
        source = stack.enter_context(_input_file(authority))
        record = None if retained_record is None else stack.enter_context(_input_file(retained_record))
        output = stack.enter_context(tempfile.TemporaryFile(mode="w+b"))
        files = (source, output) if record is None else (source, record, output)
        arguments = ("--artifact-fds-v1", str(source.fileno()),
                     "-" if record is None else str(record.fileno()), str(output.fileno()))
        data, code = _exchange_artifacts(core, request, arguments, files, output,
                                         output_limit, cancelled)
        response = _response(data, code, identifier, operation, core.role)
        if response.status == "unsupported":
            raise CoreUnsupported(response)
        if response.status == "error":
            raise CoreRejected(response)
        # Authority-first replay diagnostics belong to the core. Decode retained
        # input only after success, so malformed retained JSON cannot hide a
        # failure in the independent source request. Size/type were bounded
        # before transport; the native reader bounds nodes before allocation.
        if retained_record is not None:
            decode_artifact(retained_record)
        receipt = _object(response.result, {"schema_version", "transport", "authority",
            "retained_record", "artifact", "result"}, "Artifact receipt")
        if (receipt["schema_version"] != "biocompiler.core.artifact_response.v1"
                or receipt["transport"] != "biocompiler.core.artifact_transport.v1"
                or encode_json(receipt["authority"]) != encode_json(authority_descriptor)
                or encode_json(receipt["retained_record"]) != encode_json(record_descriptor)):
            raise CoreProtocolError("Artifact receipt authority binding differs")
        descriptor = _object(receipt["artifact"], {"bytes", "sha256"}, "Artifact descriptor")
        output.seek(0)
        raw = output.read(output_limit + 1)
        if (type(descriptor["bytes"]) is not int or len(raw) > output_limit
                or descriptor != _descriptor(raw)):
            raise CoreProtocolError("Artifact receipt differs from actual complete output bytes")
        parsed = decode_artifact(raw)
        if _canonical(parsed, output_limit) != raw:
            raise CoreProtocolError("Artifact output is not canonical JSON")
        return ArtifactResponse(response, raw)
