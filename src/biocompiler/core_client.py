"""Bounded transport to an explicitly selected experimental OCaml executable.

This module supplies no semantic fallback or acceptance authority. Existing public
compiler paths remain on their current engine until their migration gates pass.
The v1 transport initially supports the POSIX platforms built by hosted CI.
"""

from __future__ import annotations

from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
from threading import get_ident
import time
from typing import BinaryIO, Callable, Iterator, Literal, TypeAlias, cast
from uuid import uuid4


JsonValue: TypeAlias = "None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]"
PROTOCOL = "biocompiler.core.v1"
CORE_VERSION = "0.1.0"
LIMITS = {
    "max_request_bytes": 16_777_216,
    "max_response_bytes": 33_554_432,
    "max_depth": 128,
    "max_json_nodes": 250_000,
    "max_string_bytes": 4_194_304,
    "max_number_chars": 4_300,
    "max_intent_nodes": 50_000,
    "max_graph_edges": 250_000,
}
MAX_STDERR_BYTES = 1_048_576
CAPABILITIES_SCHEMA = "biocompiler.core_capabilities.v1"


class CoreError(RuntimeError):
    """Base for transport or explicitly reported core failures."""


class CoreUnavailable(CoreError):
    """The selected executable cannot be used; never triggers a fallback."""


class CoreProtocolError(CoreError):
    """Input, output or execution identity violates the pinned protocol."""


class CoreTransportError(CoreError):
    """Process failure, output exhaustion or incomplete communication."""


class CoreTimeout(CoreTransportError):
    """Operation exceeded its wall-clock budget."""


class CoreCancelled(CoreTransportError):
    """Caller cancelled this operation; no partial result is accepted."""


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    path: str | None


@dataclass(frozen=True)
class CoreResponse:
    request_id: str
    operation: str
    status: Literal["ok", "error", "unsupported"]
    result: JsonValue
    diagnostics: tuple[Diagnostic, ...]
    executable: Literal["core", "verify"]
    version: str


class CoreRejected(CoreError):
    """The core rejected a complete operation with structured diagnostics."""

    def __init__(self, response: CoreResponse):
        self.response = response
        super().__init__("; ".join(f"{d.code}: {d.message}" for d in response.diagnostics))


class CoreUnsupported(CoreRejected):
    """The selected core explicitly does not implement this operation."""


@dataclass(frozen=True)
class CoreCapabilities:
    """Validated, immutable transport capabilities; never an acceptance token."""

    operations: tuple[str, ...]
    intent_schemas: tuple[str, ...]
    validation_scopes: tuple[str, ...]
    claim_scope: str
    _profiles_json: bytes

    @property
    def profiles(self) -> dict[str, JsonValue]:
        # Each read returns a separate document; callers cannot mutate a prior
        # negotiation through a nested list or dictionary.
        return cast(dict[str, JsonValue], decode_json(self._profiles_json))

    def require_operation(self, operation: str) -> None:
        if operation not in self.operations:
            raise CoreProtocolError(f"Selected core does not advertise {operation}")


def _names(value: JsonValue, label: str) -> tuple[str, ...]:
    if (type(value) is not list or any(type(item) is not str or not item.strip() for item in value)
            or len(set(cast(list[str], value))) != len(value)):
        raise CoreProtocolError(f"{label} must contain distinct nonempty strings")
    return tuple(cast(list[str], value))


def _capabilities(value: JsonValue) -> CoreCapabilities:
    fields = _object(value, {"schema_version", "operations", "intent_schemas", "canonicalization",
                             "validation_scopes", "profiles", "limits", "claim_scope"}, "Capabilities")
    if fields["schema_version"] != CAPABILITIES_SCHEMA or fields["canonicalization"] != "python-json-v1":
        raise CoreProtocolError("Incompatible capability schema or canonicalization")
    limits = _object(fields["limits"], set(LIMITS), "Core limits")
    if any(type(limits[key]) is not int or limits[key] != expected for key, expected in LIMITS.items()):
        raise CoreProtocolError("Incompatible core resource limits")
    operations = _names(fields["operations"], "Operations")
    if "capabilities" not in operations:
        raise CoreProtocolError("Capabilities operation is missing")
    schemas = _names(fields["intent_schemas"], "Intent schemas")
    scopes = _names(fields["validation_scopes"], "Validation scopes")
    profiles, claim = fields["profiles"], fields["claim_scope"]
    if type(profiles) is not dict or type(claim) is not str or not claim.strip():
        raise CoreProtocolError("Invalid capability profiles or claim scope")
    for name, profile in profiles.items():
        if not name.strip() or type(profile) is not dict:
            raise CoreProtocolError("Invalid capability profile")
        advertised = _names(profile.get("operations"), "Profile operations")
        if not advertised or not set(advertised) <= set(operations):
            raise CoreProtocolError("Profile operations disagree with advertised operations")
    return CoreCapabilities(operations, schemas, scopes, claim, encode_json(profiles))


def _validate_string(value: str, limit: int) -> int:
    try:
        length = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise CoreProtocolError("JSON strings must contain Unicode scalar values") from exc
    if length > limit:
        raise CoreProtocolError("JSON string budget exceeded")
    return length


def validate_json(value: object, *, string_limit: int | None = None,
                  byte_limit: int = LIMITS["max_request_bytes"]) -> None:
    """Enforce v1 JSON kinds and aggregate bounds without coercing Python values."""
    stack = [(value, 0)]
    if string_limit is None:
        string_limit = LIMITS["max_string_bytes"]
    nodes = 0
    size_floor = 0

    def account(size: int) -> None:
        # Bound work even when a small Python graph repeats a very large string.
        nonlocal size_floor
        size_floor += size
        if size_floor > byte_limit:
            raise CoreProtocolError("JSON byte budget exceeded")

    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > LIMITS["max_json_nodes"] or depth > LIMITS["max_depth"]:
            raise CoreProtocolError("JSON node or depth budget exceeded")
        kind = type(item)
        if type(item) is str:
            account(_validate_string(item, string_limit) + 2)
        elif kind is int or kind is float:
            # Do not rely on Python's process-global decimal conversion limit:
            # an authoring notebook may have changed or disabled it.
            if type(item) is int and item.bit_length() > math.ceil(LIMITS["max_number_chars"] * math.log2(10)):
                raise CoreProtocolError("JSON number budget exceeded")
            try:
                text = str(item)
            except ValueError as exc:
                raise CoreProtocolError("JSON number budget exceeded") from exc
            if len(text) > LIMITS["max_number_chars"]:
                raise CoreProtocolError("JSON number budget exceeded")
            account(len(text))
            if type(item) is float and not math.isfinite(item):
                raise CoreProtocolError("Nonfinite JSON numbers are forbidden")
        elif type(item) is list:
            account(2 + max(0, len(item) - 1))
            if len(item) + len(stack) + nodes > LIMITS["max_json_nodes"]:
                raise CoreProtocolError("JSON node budget exceeded")
            stack.extend((child, depth + 1) for child in item)
        elif type(item) is dict:
            account(2 + max(0, len(item) - 1))
            if len(item) + len(stack) + nodes > LIMITS["max_json_nodes"]:
                raise CoreProtocolError("JSON node budget exceeded")
            for key, child in item.items():
                if type(key) is not str:
                    raise CoreProtocolError("JSON object keys must be strings")
                account(_validate_string(key, string_limit) + 3)
                stack.append((child, depth + 1))
        elif item is not None and kind is not bool:
            raise CoreProtocolError("Only literal JSON values may cross the core boundary")
        else:
            account(4 if item is None or item is True else 5)


# These are optimization bounds, not protocol limits. Declining a copy or an
# enrollment/cache admission always leaves the ordinary validator in charge.
_OWNED_COPY_MAX_VISITS = 250_000
_OWNED_COPY_MAX_CONTAINERS = 50_000
_OWNED_COPY_MAX_DEPTH = 128
_OWNED_ENCODING_MAX_ENROLLED = 2_048
_OWNED_ENCODING_MAX_VISITS = 250_000
_OWNED_ENCODING_MAX_ENTRIES = 2_048
_OWNED_ENCODING_MAX_BYTES = 16_777_216


@dataclass(frozen=True)
class _OwnedJson:
    value: JsonValue


def _owned_response_eligible(response: CoreResponse) -> bool:
    # A custom transport may supply subclasses with callbacks. Keep its existing
    # validation behavior, but never borrow private roots while invoking hooks.
    return (type(response) is CoreResponse and type(response.diagnostics) is tuple
            and len(response.diagnostics) == 0
            and all(type(value) is str for value in (
                response.request_id, response.operation, response.status, response.executable, response.version)))


@dataclass
class _CopyFrame:
    source: list[JsonValue] | dict[str, JsonValue]
    target: list[JsonValue] | dict[str, JsonValue]
    children: Iterator[object]
    depth: int
    length: int


def _try_owned_json_copy(value: JsonValue) -> _OwnedJson | None:
    """Copy literal containers without hooks, coercion or new protocol errors.

    A shared child is copied at each occurrence; active ancestors detect cycles.
    The iterator stack bounds temporary storage before inspecting all children.
    Immutable atoms deliberately receive no encoding validation here: the
    existing profile preflight retains its diagnostic order and limits.
    """
    visits = containers = 0
    ancestors: set[int] = set()
    stack: list[_CopyFrame] = []

    def copy(item: JsonValue, depth: int) -> tuple[bool, JsonValue]:
        nonlocal visits, containers
        visits += 1
        if visits > _OWNED_COPY_MAX_VISITS or depth > _OWNED_COPY_MAX_DEPTH:
            return False, None
        kind = type(item)
        if item is None or kind is bool or kind is int or kind is float or kind is str:
            return True, item
        if (kind is not dict and kind is not list) or id(item) in ancestors:
            return False, None
        containers += 1
        if containers > _OWNED_COPY_MAX_CONTAINERS:
            return False, None
        source = cast(list[JsonValue] | dict[str, JsonValue], item)
        target: list[JsonValue] | dict[str, JsonValue] = {} if kind is dict else []
        children: Iterator[object] = iter(source.items()) if type(source) is dict else iter(source)
        stack.append(_CopyFrame(source, target, children, depth, len(source)))
        ancestors.add(id(source))
        return True, target

    accepted, root = copy(value, 0)
    if not accepted:
        return None
    try:
        while stack:
            frame = stack[-1]
            if len(frame.source) != frame.length:
                return None
            try:
                child = next(frame.children)
            except StopIteration:
                ancestors.remove(id(frame.source))
                stack.pop()
                continue
            if type(frame.source) is dict:
                key, item = cast(tuple[object, JsonValue], child)
                visits += 1
                if type(key) is not str or visits > _OWNED_COPY_MAX_VISITS:
                    return None
                accepted, cloned = copy(item, frame.depth + 1)
                if not accepted:
                    return None
                cast(dict[str, JsonValue], frame.target)[key] = cloned
            else:
                accepted, cloned = copy(cast(JsonValue, child), frame.depth + 1)
                if not accepted:
                    return None
                cast(list[JsonValue], frame.target).append(cloned)
    except RuntimeError:
        # Exact builtin dictionary iterators report concurrent structural edits.
        return None
    return _OwnedJson(root)


@dataclass
class _OwnedEncodingEntry:
    value: list[JsonValue] | dict[str, JsonValue]
    data: bytes | None = None


@dataclass
class _OwnedEncoding:
    owner: int = field(default_factory=get_ident)
    active: bool = True
    entries: dict[int, _OwnedEncodingEntry] = field(default_factory=dict)
    cached_entries: int = 0
    cached_bytes: int = 0

    def enroll(self, roots: tuple[_OwnedJson, ...]) -> None:
        # Breadth first admission keeps both roots and nearby repeated evidence
        # eligible without retaining an unbounded traversal queue.
        pending: deque[list[JsonValue] | dict[str, JsonValue]] = deque()

        def admit(value: JsonValue) -> None:
            if ((type(value) is list or type(value) is dict) and id(value) not in self.entries
                    and len(self.entries) < _OWNED_ENCODING_MAX_ENROLLED):
                container = value
                self.entries[id(value)] = _OwnedEncodingEntry(container)
                pending.append(container)

        for root in roots:
            admit(root.value)
        visits = 0
        while pending and len(self.entries) < _OWNED_ENCODING_MAX_ENROLLED:
            parent = pending.popleft()
            for child in parent.values() if type(parent) is dict else parent:
                visits += 1
                if visits > _OWNED_ENCODING_MAX_VISITS:
                    return
                admit(child)
                if len(self.entries) >= _OWNED_ENCODING_MAX_ENROLLED:
                    return


_OWNED_ENCODING: ContextVar[_OwnedEncoding | None] = ContextVar("_owned_encoding", default=None)


@contextmanager
def _owned_encoding_scope(*roots: _OwnedJson) -> Iterator[None]:
    """Borrow private, unexposed roots only during synchronous result validation."""
    scope = _OwnedEncoding()
    scope.enroll(roots)
    token = _OWNED_ENCODING.set(scope)
    try:
        yield
    finally:
        scope.active = False
        scope.entries.clear()
        scope.cached_bytes = scope.cached_entries = 0
        _OWNED_ENCODING.reset(token)


def encode_json(value: JsonValue, *, limit: int = LIMITS["max_request_bytes"]) -> bytes:
    validate_json(value, byte_limit=limit)
    scope = _OWNED_ENCODING.get()
    entry = None
    if scope is not None and scope.active and scope.owner == get_ident():
        entry = scope.entries.get(id(value))
        if entry is not None and entry.value is not value:
            entry = None
        if entry is not None and entry.data is not None:
            if len(entry.data) > limit:
                raise CoreProtocolError("JSON byte budget exceeded")
            return entry.data
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False)
    data = bytearray()
    for part in encoder.iterencode(value):
        chunk = part.encode("utf-8")
        if len(data) + len(chunk) > limit:
            raise CoreProtocolError("JSON byte budget exceeded")
        data.extend(chunk)
    encoded = bytes(data)
    if (entry is not None and scope is not None and scope.active and scope.owner == get_ident()
            and _OWNED_ENCODING.get() is scope
            and scope.cached_entries < _OWNED_ENCODING_MAX_ENTRIES
            and scope.cached_bytes + len(encoded) <= _OWNED_ENCODING_MAX_BYTES):
        entry.data = encoded
        scope.cached_entries += 1
        scope.cached_bytes += len(encoded)
    return encoded


def decode_json(data: bytes, *, limit: int = LIMITS["max_response_bytes"]) -> JsonValue:
    if len(data) > limit:
        raise CoreProtocolError("JSON byte budget exceeded")

    def pairs(items: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {}
        for key, value in items:
            if key in result:
                raise CoreProtocolError("Duplicate JSON object key")
            result[key] = value
        return result

    def number(text: str) -> int | float:
        if len(text) > LIMITS["max_number_chars"]:
            raise CoreProtocolError("JSON number budget exceeded")
        return float(text) if any(c in text for c in ".eE") else int(text)

    def nonfinite(_text: str) -> None:
        raise CoreProtocolError("Nonfinite JSON numbers are forbidden")

    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=nonfinite, parse_int=number, parse_float=number)
        # Canonicalization can return an entire request encoded in one string.
        # Response strings have the response byte bound, not the per-input bound.
        validate_json(value, string_limit=limit, byte_limit=limit)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CoreProtocolError("Malformed or over-budget JSON") from exc
    return cast(JsonValue, value)


def _object(value: JsonValue, keys: set[str], label: str) -> dict[str, JsonValue]:
    if type(value) is not dict or set(value) != keys:
        raise CoreProtocolError(f"{label} has missing or unknown fields")
    return value


def _response(data: bytes, exit_code: int, request_id: str, operation: str,
              executable: Literal["core", "verify"]) -> CoreResponse:
    value = _object(decode_json(data), {
        "protocol", "request_id", "operation", "status", "result", "diagnostics", "core",
    }, "Core response")
    if (value["protocol"] != PROTOCOL or value["request_id"] != request_id
            or value["operation"] != operation):
        raise CoreProtocolError("Response protocol or request identity mismatch")
    identity = _object(value["core"], {"implementation", "version", "protocol", "executable"}, "Core identity")
    if identity != {"implementation": "ocaml", "version": CORE_VERSION,
                    "protocol": PROTOCOL, "executable": executable}:
        raise CoreProtocolError("Incompatible core implementation, version or executable role")
    status = value["status"]
    if type(status) is not str or status not in {"ok", "error", "unsupported"}:
        raise CoreProtocolError("Unknown core outcome")
    if exit_code != {"ok": 0, "error": 2, "unsupported": 3}[status]:
        raise CoreProtocolError("Process exit status contradicts the response")
    raw_diagnostics = value["diagnostics"]
    if type(raw_diagnostics) is not list:
        raise CoreProtocolError("Diagnostics must be a list")
    diagnostics = []
    for item in raw_diagnostics:
        diag = _object(item, {"code", "message", "path"}, "Diagnostic")
        if (type(diag["code"]) is not str or not diag["code"]
                or type(diag["message"]) is not str or not diag["message"]
                or not (diag["path"] is None or type(diag["path"]) is str)):
            raise CoreProtocolError("Invalid diagnostic fields")
        diagnostics.append(Diagnostic(diag["code"], diag["message"], diag["path"]))
    if status == "ok":
        if diagnostics or value["result"] is None:
            raise CoreProtocolError("Successful response must have a result and no diagnostics")
    elif not diagnostics or value["result"] is not None:
        raise CoreProtocolError("Rejected response must have diagnostics and no result")
    return CoreResponse(request_id, operation, cast(Literal["ok", "error", "unsupported"], status),
                        value["result"], tuple(diagnostics), executable, CORE_VERSION)


def _terminate(process: subprocess.Popen[bytes]) -> None:
    # A descendant retaining an inherited pipe must not keep a timed-out call alive.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        # Some POSIX hosts report EPERM for an already-exited process group.
        # Always reap the direct child and retain the original transport error.
        if process.poll() is None:
            process.kill()
    process.wait()


def _exchange(executable: Path, request: bytes, timeout: float,
              cancelled: Callable[[], bool] | None) -> tuple[bytes, int]:
    if os.name != "posix":
        raise CoreUnavailable("The experimental core transport currently supports POSIX only")
    if cancelled is not None and cancelled():
        raise CoreCancelled("Core operation cancelled before execution")
    try:
        process = subprocess.Popen([str(executable)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
    except OSError as exc:
        raise CoreUnavailable(f"Cannot start selected core: {executable}") from exc
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    output = bytearray()
    stderr_size = 0
    sent = 0
    deadline = time.monotonic() + timeout
    pipes = (process.stdin, process.stdout, process.stderr)
    try:
        with selectors.DefaultSelector() as selector:
            for pipe in pipes:
                os.set_blocking(pipe.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
            selector.register(process.stdout, selectors.EVENT_READ, "stdout")
            selector.register(process.stderr, selectors.EVENT_READ, "stderr")
            while selector.get_map() or process.poll() is None:
                if cancelled is not None and cancelled():
                    raise CoreCancelled("Core operation cancelled")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise CoreTimeout("Core operation exceeded its time budget")
                for key, _events in selector.select(min(remaining, 0.05)):
                    if key.data == "stdin":
                        try:
                            sent += os.write(key.fd, request[sent:sent + 65_536])
                        except BlockingIOError:
                            continue
                        except BrokenPipeError as exc:
                            raise CoreTransportError("Core closed its input before the complete request") from exc
                        if sent == len(request):
                            selector.unregister(key.fileobj)
                            process.stdin.close()
                    else:
                        chunk = os.read(key.fd, 65_536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            cast(BinaryIO, key.fileobj).close()
                        elif key.data == "stdout":
                            if len(output) + len(chunk) > LIMITS["max_response_bytes"]:
                                raise CoreTransportError("Core response byte budget exceeded")
                            output.extend(chunk)
                        else:
                            stderr_size += len(chunk)
                            if stderr_size > MAX_STDERR_BYTES:
                                raise CoreTransportError("Core stderr byte budget exceeded")
        exit_code = process.wait()
        if exit_code not in (0, 2, 3):
            raise CoreTransportError(f"Core process failed with exit status {exit_code}")
        return bytes(output), exit_code
    except BaseException:
        _terminate(process)
        raise
    finally:
        for pipe in pipes:
            pipe.close()


@dataclass(frozen=True)
class CoreClient:
    """Use a known local binary; a missing/incompatible core always fails closed.

    ``expected_sha256`` pins locally supplied release authority when available.
    It is not a signature or a substitute for distribution provenance.
    """

    executable: Path
    role: Literal["core", "verify"] = "core"
    timeout_seconds: float = 30.0
    expected_sha256: str | None = None

    def __post_init__(self) -> None:
        path = Path(self.executable)
        if not path.is_absolute():
            raise ValueError("Select the core by an explicit absolute executable path")
        if self.role not in ("core", "verify"):
            raise ValueError("Unknown core executable role")
        if (type(self.timeout_seconds) not in (int, float)
                or not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0):
            raise ValueError("Core timeout must be a finite positive number")
        if self.expected_sha256 is not None and (
            len(self.expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.expected_sha256)
        ):
            raise ValueError("Expected executable digest must be lowercase SHA-256")
        object.__setattr__(self, "executable", path)

    def call(self, operation: str, payload: JsonValue, *, request_id: str | None = None,
             cancelled: Callable[[], bool] | None = None) -> CoreResponse:
        if type(operation) is not str or not operation.strip():
            raise CoreProtocolError("Operation must be a nonempty string")
        identifier = str(uuid4()) if request_id is None else request_id
        if type(identifier) is not str or not identifier.strip():
            raise CoreProtocolError("Request identity must be a nonempty string")
        request = encode_json({"protocol": PROTOCOL, "request_id": identifier,
                               "operation": operation, "payload": payload})
        if not self.executable.is_file() or not os.access(self.executable, os.X_OK):
            raise CoreUnavailable(f"Selected core is not executable: {self.executable}")
        if self.expected_sha256 is not None:
            with self.executable.open("rb") as binary:
                digest = hashlib.file_digest(binary, "sha256").hexdigest()
            if digest != self.expected_sha256:
                raise CoreUnavailable("Selected executable does not match the supplied release pin")
        data, exit_code = _exchange(self.executable, request, self.timeout_seconds, cancelled)
        response = _response(data, exit_code, identifier, operation, self.role)
        if response.status == "unsupported":
            raise CoreUnsupported(response)
        if response.status == "error":
            raise CoreRejected(response)
        return response

    def capabilities(self) -> CoreResponse:
        return self.call("capabilities", {})

    def negotiate(self, operation: str, *, cancelled: Callable[[], bool] | None = None) -> CoreCapabilities:
        """Check current executable capabilities before a profile-specific call.

        No cached negotiation authorizes a later executable or artifact. The
        operation response still undergoes all identity and protocol checks.
        """
        capabilities = _capabilities(self.call("capabilities", {}, cancelled=cancelled).result)
        capabilities.require_operation(operation)
        return capabilities

    def canonicalize(self, value: JsonValue) -> CoreResponse:
        return self.call("canonicalize", value)

    def validate_intent(self, intent: JsonValue) -> CoreResponse:
        return self.call("validate-intent", intent)

    def verify_lowering(self, *, expected_request: JsonValue, behavior: JsonValue) -> CoreResponse:
        """Check supplied Behavior against independently supplied frozen source.

        The scoped result does not establish execution, molecular realization or
        architecture acceptance. This adapter transports both authorities without
        lowering, reconstructing a candidate or falling back to Python checking.
        """
        return self.call("verify-lowering", {"expected_request": expected_request,
                                             "behavior": behavior})
