"""Persistent, bounded transport to one explicitly selected native Core process.

This raw session interface retains live native managers. It is not a replacement
for the public PassManager API and supplies no callbacks, imported acceptance,
semantic constructors, reconnect, retry, or Python execution fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import selectors
import subprocess
import threading
import time
from typing import Any, Callable, cast
from uuid import uuid4
import weakref

from biocompiler.core_client import (
    CORE_VERSION, PROTOCOL as CORE_PROTOCOL, CoreCancelled, CoreClient, CoreError,
    CoreProtocolError, CoreTimeout, CoreTransportError, CoreUnavailable, Diagnostic,
    JsonValue, _terminate,
)

_DECLARATION_JSON = '{"argument":"--pipeline-session-v1","artifacts":{"components":["candidate","pipeline_result","selection_result","assembly","link_result","behavior_result"],"synthetic":["candidate","pipeline_result","selection_result"]},"budget":"one_lifetime_ancestor_including_hello_prefix_parse_import_execution_and_publication_no_per_command_reset","callback_scope":"native_fixed_providers_only_no_wire_callbacks_registration_decisions_or_accepted_record_import","claim_scope":"live_native_manager_scoped_acceptance_under_supplied_software_contracts_no_empirical_or_human_use_acceptance","dependencies_encoding":"ordered_unique_string_identity_pairs","exception_fields":["module","type","message","attributes"],"executable":"core","failure":"expected_logical_errors_keep_actual_partial_manager; framing_identity_budget_or_internal_errors_close","fixed_limits":{"max_depth":128,"max_number_chars":4300,"max_string_bytes":4194304,"terminal_reserve_bytes":8192,"terminal_reserve_work":1000000},"framing":"eight_lowercase_hex_body_bytes_then_lf_then_exact_utf8_json","hello_fields":["profile","limits","manager_limits"],"initialization_fields":["kind","manager","artifacts"],"limits":{"max_commands":10000,"max_frame_bytes":33554432,"max_json_nodes":1000000,"max_retained_bytes":134217728,"max_total_bytes":268435456,"max_work":1000000000000},"limits_encoding":"null_defaults_or_exact_all_positive_integer_reductions","manager_limits":{"max_ancestor_depth":128,"max_call_depth":128,"max_document_bytes":16777216,"max_document_nodes":250000,"max_providers":10000,"max_records":10000,"max_retained_bytes":67108864,"max_retained_items":1000000},"operations":{"add-build-request":{"fields":["identity","requirements","obligations","request"],"result":"complete_stage_record"},"add-input":{"fields":["identity","stage","requirements","obligations","document"],"result":"complete_stage_record"},"artifact":{"fields":["name"],"result":"complete_immutable_build_artifact"},"close":{"fields":[],"result":"null"},"get":{"fields":["identity"],"result":"fresh_complete_stage_record"},"hello":{"fields":["profile","limits","manager_limits"],"result":"exact_profile_and_effective_limits"},"initialize-components":{"fields":["request","history","until","config"],"result":"initialization"},"initialize-empty":{"fields":["target","dependencies","completion_profiles"],"result":"initialization"},"initialize-synthetic":{"fields":["request","history","until","config"],"result":"initialization"},"inspect":{"fields":[],"result":"complete_historical_manager_snapshot_with_process_local_provider_labels"},"register-completion-profile":{"fields":["profile"],"result":"null"},"result":{"fields":["identity","scope"],"result":"fresh_complete_pipeline_result"},"run":{"fields":["pass_id","input_id","output_id","configuration"],"result":"fresh_complete_stage_record"},"set-dependency":{"fields":["key","identity"],"result":"null"},"target":{"fields":[],"result":"complete_target"}},"profile":"biocompiler.core.pipeline_session.v1","protocol":"biocompiler.pipeline_session.v1","request_fields":["protocol","session_id","sequence","operation","payload"],"request_identity":"sha256_exact_utf8_body_without_frame_header","response_fields":["protocol","profile","session_id","sequence","operation","request_sha256","status","result","diagnostics","exception","closed","usage","core"],"retention":"conservative_cumulative_service_authorities_and_build_artifacts_separate_from_manager_limits_no_refund","schema_version":"biocompiler.pipeline_session_declaration.v1","sequence":"hello_zero_then_exact_successor_including_logical_errors","session_identity":"client_canonical_lowercase_uuid_bound_to_one_process_no_reconnect","terminal_reserve":"prepaid_work_and_byte_capacity_counted_before_reduced_limits; fatal_reply_may_exceed_reduced_frame_ceiling_up_to8192","usage_fields":["work_charged","work_remaining","input_bytes","output_bytes","commands","retained_bytes"]}'
PROTOCOL = 'biocompiler.pipeline_session.v1'
PROFILE = 'biocompiler.core.pipeline_session.v1'
MAX_STDERR_BYTES = 1_048_576
HEADER_BYTES = 9


def capability_profile() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_DECLARATION_JSON))


_DEFAULTS: dict[str, int] = capability_profile()['limits']
_FIXED: dict[str, int] = capability_profile()['fixed_limits']
OPERATIONS = tuple(capability_profile()['operations'])


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoreProtocolError(message)


def _object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == fields, label + ' has missing or unknown fields')
    return cast(dict[str, Any], value)


def _reductions(value: JsonValue, defaults: dict[str, int], label: str) -> dict[str, int]:
    if value is None:
        return dict(defaults)
    fields = _object(value, set(defaults), label)
    _require(all(type(fields[key]) is int and 0 < fields[key] <= maximum
                 for key, maximum in defaults.items()), label + ' require positive integer reductions')
    return cast(dict[str, int], dict(fields))


def _validate(value: JsonValue, max_bytes: int, max_nodes: int) -> None:
    stack = [(value, 0)]
    nodes = 0
    floor = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        _require(depth <= _FIXED['max_depth'] and nodes <= max_nodes, 'Session JSON depth or node limit exceeded')
        kind = type(item)
        if kind is str:
            try:
                size = len(cast(str, item).encode('utf-8'))
            except UnicodeError as exc:
                raise CoreProtocolError('Session JSON contains a non-scalar string') from exc
            _require(size <= _FIXED['max_string_bytes'], 'Session JSON string limit exceeded')
            floor += size + 2
        elif kind is int or kind is float:
            if kind is int:
                _require(cast(int, item).bit_length() <= math.ceil(_FIXED['max_number_chars'] * math.log2(10)),
                         'Session JSON number limit exceeded')
            else:
                _require(math.isfinite(cast(float, item)), 'Session JSON nonfinite number')
            try:
                size = len(str(item))
            except ValueError as exc:
                raise CoreProtocolError('Session JSON integer conversion limit') from exc
            _require(size <= _FIXED['max_number_chars'], 'Session JSON number limit exceeded')
            floor += size
        elif kind is list:
            items = cast(list[JsonValue], item)
            floor += 2 + max(0, len(items) - 1)
            _require(nodes + len(stack) + len(items) <= max_nodes, 'Session JSON node limit exceeded')
            stack.extend((child, depth + 1) for child in items)
        elif kind is dict:
            fields = cast(dict[str, JsonValue], item)
            floor += 2 + max(0, len(fields) - 1)
            _require(nodes + len(stack) + 2 * len(fields) <= max_nodes, 'Session JSON node limit exceeded')
            for key, child in fields.items():
                _require(type(key) is str, 'Session JSON keys must be strings')
                stack.extend(((key, depth + 1), (child, depth + 1)))
                floor += 1
        elif item is None or kind is bool:
            floor += 4 if item is None or item is True else 5
        else:
            raise CoreProtocolError('Session accepts only literal JSON values')
        _require(floor <= max_bytes, 'Session JSON byte limit exceeded')


def encode_document(value: JsonValue, *, max_bytes: int = _DEFAULTS['max_frame_bytes'],
                    max_nodes: int = _DEFAULTS['max_json_nodes']) -> bytes:
    """Strict UTF-8 JSON, counting both object keys and values under this profile."""
    _validate(value, max_bytes, max_nodes)
    result = bytearray()
    try:
        encoder = json.JSONEncoder(sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        for part in encoder.iterencode(value):
            chunk = part.encode('utf-8')
            _require(len(result) + len(chunk) <= max_bytes, 'Session JSON byte limit exceeded')
            result.extend(chunk)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CoreProtocolError('Cannot encode bounded session JSON') from exc
    return bytes(result)


def _scan(data: bytes, max_nodes: int) -> None:
    # Count tokens/containers before json.loads allocates their object graph.
    # JSON grammar, UTF-8, escaping, duplicates and numeric kinds are checked by
    # the decoder below; every key is a string token and counts toward the limit.
    index = depth = nodes = 0
    while index < len(data):
        byte = data[index]
        if byte in b' \t\r\n,:':
            index += 1
            continue
        if byte in b'}]':
            depth -= 1
            _require(depth >= 0, 'Malformed session JSON nesting')
            index += 1
            continue
        nodes += 1
        _require(nodes <= max_nodes and depth <= _FIXED['max_depth'], 'Session JSON depth or node limit exceeded')
        if byte in b'{[':
            depth += 1
            index += 1
        elif byte == 34:
            index += 1
            while index < len(data) and data[index] != 34:
                index += 2 if data[index] == 92 else 1
            _require(index < len(data), 'Incomplete session JSON string')
            index += 1
        else:
            while index < len(data) and data[index] not in b' \t\r\n,:{}[]"':
                index += 1
    _require(depth == 0, 'Incomplete session JSON containers')


def decode_document(data: bytes, *, max_bytes: int = _DEFAULTS['max_frame_bytes'],
                    max_nodes: int = _DEFAULTS['max_json_nodes']) -> JsonValue:
    _require(type(data) is bytes and len(data) <= max_bytes, 'Session JSON byte limit exceeded')
    _scan(data, max_nodes)
    def pairs(items: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {}
        for key, value in items:
            _require(key not in result, 'Duplicate session JSON key')
            result[key] = value
        return result
    def number(value: str) -> int | float:
        _require(len(value) <= _FIXED['max_number_chars'], 'Session JSON number limit exceeded')
        return float(value) if any(char in value for char in '.eE') else int(value)
    def nonfinite(value: str) -> None:
        raise CoreProtocolError('Session JSON nonfinite number: ' + value)
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=pairs,
                           parse_int=number, parse_float=number, parse_constant=nonfinite)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise CoreProtocolError('Malformed bounded session JSON') from exc
    _validate(value, max_bytes, max_nodes)
    return cast(JsonValue, value)


def _frame(body: bytes) -> bytes:
    return f'{len(body):08x}\n'.encode('ascii') + body


def _dispose(process: subprocess.Popen[bytes], selector: selectors.BaseSelector, owner_pid: int) -> None:
    try:
        # A fork inherits the Python object and its weakref finalizer, but not
        # ownership of the parent's native process. Closing copied descriptors
        # is safe; signalling that process group from the child is not.
        if os.getpid() == owner_pid:
            _terminate(process)
    finally:
        selector.close()
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None:
                pipe.close()


@dataclass(frozen=True)
class SessionResponse:
    session_id: str
    sequence: int
    operation: str
    status: str
    closed: bool
    diagnostics: tuple[Diagnostic, ...]
    request_document: bytes
    response_document: bytes

    @property
    def request_frame(self) -> bytes:
        return _frame(self.request_document)

    @property
    def response_frame(self) -> bytes:
        return _frame(self.response_document)

    @property
    def receipt(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_document(self.response_document))

    @property
    def result(self) -> JsonValue:
        return cast(JsonValue, self.receipt['result'])

    @property
    def usage(self) -> dict[str, int]:
        return cast(dict[str, int], self.receipt['usage'])

    @property
    def exception(self) -> dict[str, Any] | None:
        return cast(dict[str, Any] | None, self.receipt['exception'])


class SessionRejected(CoreError):
    """A complete native rejection; response.closed determines session lifetime."""
    def __init__(self, response: SessionResponse):
        self.response = response
        super().__init__('; '.join(f'{item.code}: {item.message}' for item in response.diagnostics))


class SessionUnsupported(SessionRejected):
    """The live session does not implement the requested operation."""


class CorePipelineSession:
    """One owner thread, one pinned process, one native lifetime; no reconnect."""
    def __init__(self, core: CoreClient, *, limits: JsonValue = None,
                 manager_limits: JsonValue = None, cancelled: Callable[[], bool] | None = None):
        _require(isinstance(core, CoreClient) and core.role == 'core', 'Pipeline sessions require an explicit Core role')
        if os.name != 'posix':
            raise CoreUnavailable('Pipeline sessions currently require POSIX')
        self._limits = _reductions(limits, _DEFAULTS, 'Session limits')
        self._manager_limits = _reductions(manager_limits, capability_profile()['manager_limits'], 'Manager limits')
        # Freeze caller-owned reductions before launching the process.
        hello: JsonValue = {'profile': PROFILE, 'limits': None if limits is None else dict(self._limits),
                            'manager_limits': None if manager_limits is None else dict(self._manager_limits)}
        self._core = core
        self._owner = threading.current_thread()
        self._owner_pid = os.getpid()
        self._nonce = str(uuid4())
        self._next = 0
        self._active = False
        self._closed = False
        self._invalidated = False
        self._input_bytes = self._output_bytes = 0
        self._usage: dict[str, int] | None = None
        self._stderr = bytearray()
        self._eof: set[str] = set()
        self._last_response: SessionResponse | None = None
        if cancelled is not None and cancelled():
            raise CoreCancelled('Pipeline session cancelled before launch')
        path = Path(core.executable)
        if not path.is_file() or not os.access(path, os.X_OK):
            raise CoreUnavailable('Selected pipeline Core is not executable: ' + str(path))
        try:
            with path.open('rb') as binary:
                self._executable_sha256 = hashlib.file_digest(binary, 'sha256').hexdigest()
        except OSError as exc:
            raise CoreUnavailable('Cannot read selected pipeline Core') from exc
        if core.expected_sha256 is not None and self._executable_sha256 != core.expected_sha256:
            raise CoreUnavailable('Selected pipeline Core does not match its release pin')
        self._selector = selectors.DefaultSelector()
        try:
            self._process = subprocess.Popen([str(path), capability_profile()['argument']],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        except BaseException as exc:
            self._selector.close()
            if isinstance(exc, OSError):
                raise CoreUnavailable('Cannot launch selected pipeline Core') from exc
            raise
        self._finalizer = weakref.finalize(self, _dispose, self._process, self._selector, self._owner_pid)
        try:
            for label, pipe in (('stdin', self._process.stdin), ('stdout', self._process.stdout), ('stderr', self._process.stderr)):
                assert pipe is not None
                os.set_blocking(pipe.fileno(), False)
                if label != 'stdin':
                    self._selector.register(pipe, selectors.EVENT_READ, label)
            self.hello_response = self._call('hello', hello, cancelled=cancelled)
        except BaseException:
            self._invalidate()
            raise

    @property
    def pid(self) -> int:
        return self._process.pid

    @property
    def returncode(self) -> int | None:
        return self._process.poll()

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def invalidated(self) -> bool:
        return self._invalidated

    @property
    def executable_sha256(self) -> str:
        return self._executable_sha256

    @property
    def stderr_bytes(self) -> bytes:
        return bytes(self._stderr)

    @property
    def last_response(self) -> SessionResponse | None:
        return self._last_response

    def _check_owner(self) -> None:
        _require(os.getpid() == self._owner_pid and threading.current_thread() is self._owner,
                 'Pipeline session can only be used by its creating process and thread')
        _require(not self._active, 'Pipeline session callbacks and reentrant calls are not supported by this profile')

    def _invalidate(self) -> None:
        self._closed = self._invalidated = True
        self._finalizer()

    def _read(self, key: selectors.SelectorKey) -> bytes:
        try:
            chunk = os.read(key.fd, 65_536)
        except BlockingIOError:
            return b''
        if not chunk:
            self._eof.add(str(key.data))
            self._selector.unregister(key.fileobj)
        elif key.data == 'stderr':
            if len(self._stderr) + len(chunk) > MAX_STDERR_BYTES:
                raise CoreTransportError('Pipeline session stderr limit exceeded')
            self._stderr.extend(chunk)
        return chunk

    def _quiet(self) -> None:
        for key, _ in self._selector.select(0):
            if key.data == 'stdin':
                continue
            chunk = self._read(key)
            if key.data == 'stdout' and chunk:
                raise CoreProtocolError('Unsolicited or trailing pipeline session output')

    def _check_time(self, deadline: float, cancelled: Callable[[], bool] | None) -> None:
        if cancelled is not None and cancelled():
            raise CoreCancelled('Pipeline session command cancelled')
        if time.monotonic() >= deadline:
            raise CoreTimeout('Pipeline session command exceeded its deadline')

    def _exchange(self, body: bytes, deadline: float, cancelled: Callable[[], bool] | None) -> bytes:
        self._quiet()
        if self._eof or self._process.poll() is not None:
            raise CoreTransportError('Pipeline session process or pipe was lost')
        packet = _frame(body)
        if self._input_bytes + self._output_bytes + len(packet) > self._limits['max_total_bytes']:
            raise CoreTransportError('Pipeline session aggregate byte limit exceeded')
        self._input_bytes += len(packet)
        assert self._process.stdin is not None
        self._selector.register(self._process.stdin, selectors.EVENT_WRITE, 'stdin')
        sent = 0
        received = bytearray()
        length: int | None = None
        ceiling = max(self._limits['max_frame_bytes'], _FIXED['terminal_reserve_bytes'])
        while True:
            self._check_time(deadline, cancelled)
            for key, _ in self._selector.select(min(0.05, max(0.0, deadline - time.monotonic()))):
                if key.data == 'stdin':
                    try:
                        sent += os.write(key.fd, packet[sent:sent + 65_536])
                    except BlockingIOError:
                        continue
                    except BrokenPipeError as exc:
                        raise CoreTransportError('Pipeline Core closed its input during a frame') from exc
                    if sent == len(packet):
                        self._selector.unregister(key.fileobj)
                else:
                    chunk = self._read(key)
                    if key.data != 'stdout':
                        continue
                    received.extend(chunk)
                    if self._input_bytes + self._output_bytes + len(received) > self._limits['max_total_bytes']:
                        raise CoreTransportError('Pipeline session aggregate byte limit exceeded')
                    if length is None and len(received) >= HEADER_BYTES:
                        header = received[:HEADER_BYTES]
                        _require(header[8] == 10 and all(value in b'0123456789abcdef' for value in header[:8]),
                                 'Invalid pipeline session frame header')
                        length = int(header[:8], 16)
                        _require(0 < length <= ceiling, 'Pipeline session frame byte limit exceeded')
                    if length is not None:
                        _require(len(received) <= HEADER_BYTES + length, 'Trailing or multiple pipeline session frames')
            if length is not None and len(received) == HEADER_BYTES + length:
                _require(sent == len(packet), 'Pipeline response preceded the complete request')
                self._output_bytes += len(received)
                self._quiet()
                return bytes(received[HEADER_BYTES:])
            if 'stdout' in self._eof or self._process.poll() is not None:
                raise CoreTransportError('Pipeline Core exited with an incomplete response frame')

    def _finish(self, deadline: float, cancelled: Callable[[], bool] | None) -> None:
        assert self._process.stdin is not None
        self._process.stdin.close()
        while self._selector.get_map() or self._process.poll() is None:
            self._check_time(deadline, cancelled)
            for key, _ in self._selector.select(min(0.05, max(0.0, deadline - time.monotonic()))):
                chunk = self._read(key)
                if key.data == 'stdout' and chunk:
                    raise CoreProtocolError('Trailing output after pipeline session closure')
        if self._process.wait() != 0:
            raise CoreTransportError('Closed pipeline session exited unsuccessfully')
        self._closed = True
        self._selector.close()
        for pipe in (self._process.stdout, self._process.stderr):
            assert pipe is not None
            pipe.close()
        self._finalizer.detach()

    def call(self, operation: str, payload: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> SessionResponse:
        self._check_owner()
        _require(operation not in ('hello', 'close'), 'Use session construction or close for lifecycle operations')
        return self._call(operation, payload, cancelled=cancelled)

    def _call(self, operation: str, payload: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> SessionResponse:
        self._check_owner()
        _require(not self._closed, 'Pipeline session is closed; it cannot reconnect')
        _require(type(operation) is str and bool(operation.strip()), 'Session operation must be a nonempty string')
        sequence = self._next
        body = encode_document({'protocol': PROTOCOL, 'session_id': self._nonce,
            'sequence': sequence, 'operation': operation, 'payload': payload},
            max_bytes=self._limits['max_frame_bytes'], max_nodes=self._limits['max_json_nodes'])
        self._active = True
        deadline = time.monotonic() + self._core.timeout_seconds
        try:
            raw = self._exchange(body, deadline, cancelled)
            response = self._response(raw, body, sequence, operation)
            self._last_response = response
            self._usage = response.usage
            self._next += 1
            if response.closed:
                self._finish(deadline, cancelled)
            elif self._eof or self._process.poll() is not None:
                raise CoreTransportError('Pipeline process exited without closing its live session')
        except BaseException:
            self._invalidate()
            raise
        finally:
            self._active = False
        if response.status != 'ok':
            if response.closed:
                self._invalidated = True
            raise (SessionUnsupported if response.status == 'unsupported' else SessionRejected)(response)
        return response

    def close(self) -> SessionResponse | None:
        self._check_owner()
        if self._closed:
            return None
        return self._call('close', {}, cancelled=None)

    def __enter__(self) -> CorePipelineSession:
        self._check_owner()
        _require(not self._closed, 'Pipeline session is closed')
        return self

    def __exit__(self, kind: Any, value: Any, traceback: Any) -> None:
        if kind is None:
            self.close()
        else:
            try:
                self.close()
            except BaseException:
                self._invalidate()

    def _response(self, raw: bytes, body: bytes, sequence: int, operation: str) -> SessionResponse:
        fields = _object(decode_document(raw, max_bytes=max(self._limits['max_frame_bytes'], _FIXED['terminal_reserve_bytes']),
            max_nodes=max(self._limits['max_json_nodes'], _FIXED['terminal_reserve_bytes'])),
            set(capability_profile()['response_fields']), 'Session response')
        _require(fields['protocol'] == PROTOCOL and fields['profile'] == PROFILE and fields['session_id'] == self._nonce
            and type(fields['sequence']) is int and fields['sequence'] == sequence and fields['operation'] == operation
            and fields['request_sha256'] == hashlib.sha256(body).hexdigest(), 'Session response authority binding mismatch')
        _require(fields['core'] == {'implementation': 'ocaml', 'version': CORE_VERSION,
            'protocol': CORE_PROTOCOL, 'executable': 'core'}, 'Session Core implementation or role mismatch')
        status, closed = fields['status'], fields['closed']
        _require(type(status) is str and status in ('ok', 'error', 'unsupported') and type(closed) is bool,
                 'Invalid session outcome or closure flag')
        if not closed or status == 'ok':
            _validate(cast(JsonValue, fields), self._limits['max_frame_bytes'], self._limits['max_json_nodes'])
            _require(len(raw) <= self._limits['max_frame_bytes'], 'Normal session response exceeds its frame limit')
        else:
            _require(len(raw) + HEADER_BYTES <= _FIXED['terminal_reserve_bytes'],
                     'Terminal session response exceeds its reserved capacity')
        raw_diagnostics = fields['diagnostics']
        _require(type(raw_diagnostics) is list, 'Session diagnostics must be an array')
        diagnostics = []
        for item in raw_diagnostics:
            diagnostic = _object(item, {'code', 'message', 'path'}, 'Session diagnostic')
            _require(type(diagnostic['code']) is str and bool(diagnostic['code'])
                and type(diagnostic['message']) is str and bool(diagnostic['message'])
                and (diagnostic['path'] is None or type(diagnostic['path']) is str), 'Malformed session diagnostic')
            diagnostics.append(Diagnostic(diagnostic['code'], diagnostic['message'], diagnostic['path']))
        exception = fields['exception']
        if exception is not None:
            exception = _object(exception, set(capability_profile()['exception_fields']), 'Session exception')
            _require(all(type(exception[key]) is str and bool(exception[key]) for key in ('module', 'type', 'message'))
                and type(exception['attributes']) is dict, 'Malformed native exception observation')
        if status == 'ok':
            _require(not diagnostics and exception is None and closed == (operation == 'close'),
                     'Successful session response has contradictory diagnostics or lifetime')
            self._result(operation, fields['result'])
        else:
            _require(bool(diagnostics) and fields['result'] is None, 'Rejected session response lost complete diagnostics')
        usage = _object(fields['usage'], set(capability_profile()['usage_fields']), 'Session usage')
        _require(all(type(value) is int and value >= 0 for value in usage.values()), 'Session usage must contain nonnegative integers')
        _require(usage['commands'] == sequence + 1 and usage['input_bytes'] == self._input_bytes
            and usage['output_bytes'] == self._output_bytes, 'Session usage changed its exact command or wire census')
        totals = {self._limits['max_work']}
        if closed and sequence == 0 and status != 'ok':
            totals.add(_DEFAULTS['max_work'])
        _require(usage['work_charged'] + usage['work_remaining'] in totals
            and usage['work_charged'] >= _FIXED['terminal_reserve_work'], 'Session work ancestor changed')
        if not closed or status == 'ok':
            _require(usage['commands'] <= self._limits['max_commands']
                and usage['retained_bytes'] <= self._limits['max_retained_bytes']
                and usage['input_bytes'] + usage['output_bytes'] + _FIXED['terminal_reserve_bytes'] <= self._limits['max_total_bytes'],
                'Session resource limits were exceeded without closure')
        if self._usage is not None:
            _require(usage['work_remaining'] <= self._usage['work_remaining']
                and all(usage[key] >= self._usage[key] for key in ('work_charged', 'retained_bytes')),
                'Session lifetime usage was reset')
        return SessionResponse(self._nonce, sequence, operation, status, closed, tuple(diagnostics), body, raw)

    def _result(self, operation: str, value: JsonValue) -> None:
        if operation == 'hello':
            result = _object(value, {'profile', 'limits', 'manager_limits'}, 'Session hello')
            _require(encode_document(result['profile']) == _DECLARATION_JSON.encode('utf-8')
                and encode_document(result['limits']) == encode_document(cast(JsonValue, self._limits))
                and encode_document(result['manager_limits']) == encode_document(cast(JsonValue, self._manager_limits)),
                'Incompatible pipeline session profile or limits')
        elif operation.startswith('initialize-'):
            result = _object(value, {'kind', 'manager', 'artifacts'}, 'Session initialization')
            kind = operation.removeprefix('initialize-')
            _require(result['kind'] == kind and result['manager'] is True
                and result['artifacts'] == capability_profile()['artifacts'].get(kind, []),
                'Native initialization result has incompatible fields')
        elif operation in ('set-dependency', 'register-completion-profile', 'close'):
            _require(value is None, 'Session unit operation returned an unexpected value')
        elif operation == 'inspect':
            result = _object(value, {'target', 'dependencies', 'passes', 'component_inputs', 'provider_history',
                'component_input_history', 'records', 'profiles'}, 'Native manager snapshot')
            _require(all(type(item) is dict for item in result.values()), 'Native manager snapshot fields must be objects')
        elif operation in ('get', 'run', 'add-input', 'add-build-request'):
            _stage(value)
        elif operation == 'result':
            result = _object(value, {'status', 'artifact', 'scope', 'unresolved'}, 'Native pipeline result')
            _require(result['status'] in ('partial', 'complete') and type(result['scope']) is str
                and type(result['unresolved']) is list, 'Malformed native pipeline result')
            _stage(result['artifact'])
        elif operation == 'target':
            _require(type(value) is dict and value.get('schema_version') in
                ('biocompiler.target.v0.1', 'biocompiler.human_target_context.v0.1'), 'Malformed native target')
        elif operation == 'artifact':
            _require(value is None or type(value) is dict, 'Native artifact must be a complete object or absent optional selection')
        else:
            raise CoreProtocolError('Native session accepted an undeclared operation')


def _stage(value: JsonValue) -> None:
    record = _object(value, {'schema_version', 'id', 'stage', 'payload', 'requirements', 'obligations', 'discharged',
        'dependencies', 'parent', 'pass_id', 'pass_identity', 'checks', 'provenance', 'accepted'}, 'Native stage record')
    _require(record['schema_version'] == 'biocompiler.stage_record.v0.1' and type(record['accepted']) is bool,
             'Malformed native stage schema or acceptance observation')
    _require(all(type(record[key]) is str for key in ('id', 'stage'))
        and all(type(record[key]) is dict for key in ('payload', 'dependencies', 'checks', 'provenance'))
        and all(type(record[key]) is list for key in ('requirements', 'obligations', 'discharged'))
        and all(record[key] is None or type(record[key]) is str for key in ('parent', 'pass_id', 'pass_identity')),
        'Malformed native stage field kinds')
