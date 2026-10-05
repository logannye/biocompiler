"""Explicit trusted callback channel, with one live process and nested stack.

This transport owns no manager semantics and imports no acceptance. The caller
supplies an exact application declaration and local host object capabilities.
The public manager adapter must separately preserve authoring/context semantics.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
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
    CoreCancelled, CoreClient, CoreError, CoreProtocolError, CoreTimeout,
    CoreTransportError, CoreUnavailable, JsonValue,
)
from biocompiler.core_pipeline_session import (
    HEADER_BYTES, MAX_STDERR_BYTES, _dispose, _frame, decode_document, encode_document,
)
from biocompiler.pipeline_callback_objects import CallbackObjects, HostCompletion

_DECLARATION_JSON = "{\"application\":\"caller_supplied_exact_declaration;channel_has_no_manager_or_acceptance_authority\",\"client_fields\":{\"close\":[\"protocol\",\"profile\",\"session_id\",\"kind\",\"sequence\",\"parent_invocation\"],\"command\":[\"protocol\",\"profile\",\"session_id\",\"kind\",\"sequence\",\"parent_invocation\",\"operation\",\"arguments\"],\"continue\":[\"protocol\",\"profile\",\"session_id\",\"kind\",\"sequence\",\"invocation_id\",\"invocation_sha256\",\"outcome\"],\"hello\":[\"protocol\",\"profile\",\"session_id\",\"kind\",\"sequence\",\"declaration\",\"application\",\"limits\"]},\"close\":\"top_level_only;successful_null_reply_with_closed_true;no_resume\",\"continuation_binding\":\"only_exact_current_top_invocation_id_and_body_sha256_may_complete\",\"continuation_outcomes\":{\"raise\":[\"status\",\"token\"],\"return\":[\"status\",\"value\"]},\"event_sequence\":\"zero_then_exact_successor_across_replies_invocations_and_fatal\",\"exception\":\"opaque_bounded_host_token_preserved;only_explicit_rejected_reply_or_Host_exception_keeps_application_live\",\"fatal\":\"pipeline_callback_fatal;closed_latched;nullable_last_validated_request_binding;no_retry_or_fatal_write_after_uncertain_write\",\"fixed_limits\":{\"frame_header_bytes\":9,\"max_action_bytes\":128,\"max_frame_json_nodes\":1000000,\"max_json_depth\":128,\"max_json_number_characters\":4300,\"max_json_string_bytes\":4194304,\"max_token_bytes\":128,\"terminal_bytes\":8192,\"terminal_work\":1000000},\"framing\":\"8_lowercase_hex_utf8_body_bytes_then_LF_then_exact_body\",\"hello\":\"exact_complete_transport_and_application_declarations;null_or_complete_positive_integer_limit_reductions;already_consumed_prefix_counts\",\"hello_result_fields\":[\"declaration\",\"application\",\"limits\"],\"host_execution\":\"arbitrary_host_callback_cpu_and_memory_outside_native_bound;application_must_charge_its_native_work_and_retention_to_channel\",\"invocation_identity\":\"event_id_and_sha256_exact_invocation_body_without_frame_header\",\"limits\":{\"max_commands\":10000,\"max_frame_bytes\":33554432,\"max_frames\":1000000,\"max_json_nodes\":2000000,\"max_pending_invocations\":128,\"max_retained_bytes\":134217728,\"max_total_bytes\":268435456,\"max_work\":1000000000000},\"parent_binding\":\"command_parent_is_current_top_invocation_or_null_at_top_level;invocation_parent_is_enclosing_invocation\",\"profile\":\"biocompiler.core.pipeline_callback_channel.v2\",\"protocol\":\"biocompiler.pipeline_callback_channel.v1\",\"reply_outcomes\":{\"ok\":[\"status\",\"value\"],\"raise\":[\"status\",\"token\"],\"rejected\":[\"status\",\"value\"]},\"request_identity\":\"sha256_exact_utf8_body_without_frame_header\",\"retention\":\"cumulative_canonical_application_declaration_and_received_body_bytes_plus_callback_arguments_and_explicit_application_reservations;no_refund\",\"schema_version\":\"biocompiler.pipeline_callback_channel_declaration.v1\",\"sequence\":\"hello_zero_then_exact_successor_across_commands_continuations_and_close\",\"server_fields\":{\"fatal\":[\"protocol\",\"profile\",\"session_id\",\"kind\",\"event_id\",\"sequence\",\"request_sha256\",\"code\",\"closed\",\"usage\"],\"invoke\":[\"protocol\",\"profile\",\"session_id\",\"kind\",\"event_id\",\"invocation_id\",\"parent_invocation\",\"command_sequence\",\"command_sha256\",\"action\",\"arguments\",\"usage\"],\"reply\":[\"protocol\",\"profile\",\"session_id\",\"kind\",\"event_id\",\"sequence\",\"request_sha256\",\"outcome\",\"closed\",\"usage\"]},\"session_identity\":\"client_canonical_lowercase_uuid_bound_to_one_channel_no_reconnect\",\"terminal_reserve\":\"prepaid_1000000_work;normal_frames_leave_8192_bytes_and_one_frame;one_fatal_may_exceed_reduced_frame_and_node_ceilings_within_prepaid_byte_work_bound\",\"usage\":\"conservative_reservations_before_io_or_allocation;partial_headers_and_bodies_remain_charged;json_nodes_counts_all_received_and_published_keys_and_values\",\"usage_fields\":[\"work_charged\",\"work_remaining\",\"input_bytes\",\"output_bytes\",\"frames\",\"commands\",\"json_nodes\",\"pending_invocations\",\"retained_bytes\"]}"
PROTOCOL = 'biocompiler.pipeline_callback_channel.v1'
PROFILE = 'biocompiler.core.pipeline_callback_channel.v2'
ARGUMENT = '--pipeline-callback-session-v1'
_BROKER_ACTIONS = (
    'literal', 'enum', 'bind-provider', 'release', 'call-provider', 'call',
    'attr', 'attr-default', 'is-instance', 'compare', 'contains', 'get-item',
    'set-attribute-equal', 'lookup', 'merge', 'is-none', 'truth', 'callable',
    'iter', 'next', 'tuple', 'list', 'dict', 'len', 'mapping-items',
    'mapping-values', 'mapping-keys', 'vars', 'document', 'freeze-json', 'json',
)


def capability_profile() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(_DECLARATION_JSON))


_DEFAULTS: dict[str, int] = capability_profile()['limits']
_FIXED: dict[str, int] = capability_profile()['fixed_limits']


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CoreProtocolError(message)


def _object(value: Any, fields: set[str], label: str) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == fields, label + ' has missing or unknown fields')
    return cast(dict[str, Any], value)


def _name(value: Any, maximum: int, label: str) -> str:
    _require(type(value) is str and bool(value) and len(value.encode('utf-8')) <= maximum,
             'Invalid callback ' + label)
    return cast(str, value)


def _nodes(value: JsonValue) -> int:
    count = 0
    stack = [value]
    while stack:
        item = stack.pop()
        count += 1
        if type(item) is dict:
            count += len(item)
            stack.extend(item.values())
        elif type(item) is list:
            stack.extend(item)
    return count


@dataclass(frozen=True)
class CallbackFrame:
    direction: str
    index: int
    document: bytes

    @property
    def frame(self) -> bytes:
        return _frame(self.document)

    @property
    def value(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_document(self.document))


@dataclass(frozen=True)
class CallbackResponse:
    sequence: int
    event_id: int
    operation: str
    status: str
    closed: bool
    request_document: bytes
    response_document: bytes

    @property
    def receipt(self) -> dict[str, Any]:
        return cast(dict[str, Any], decode_document(self.response_document))

    @property
    def result(self) -> JsonValue:
        return cast(JsonValue, self.receipt['outcome'].get('value'))

    @property
    def usage(self) -> dict[str, int]:
        return cast(dict[str, int], self.receipt['usage'])

    @property
    def request_frame(self) -> bytes:
        return _frame(self.request_document)

    @property
    def response_frame(self) -> bytes:
        return _frame(self.response_document)


class CallbackRejected(CoreError):
    """An explicit application rejection; the actual native process stays live."""
    def __init__(self, response: CallbackResponse):
        self.response = response
        super().__init__('Native callback application rejected the command')


class CallbackFatal(CoreProtocolError):
    def __init__(self, document: bytes):
        self.document = document
        super().__init__('Native callback channel closed after a terminal failure')


@dataclass
class _Command:
    sequence: int
    operation: str
    document: bytes
    deadline: float
    cancelled: Callable[[], bool] | None
    exception_tokens: set[str] = field(default_factory=set)


class CorePipelineCallbackSession:
    """Explicit local extension authority; no retries, reconnects or fallback."""
    def __init__(self, core: CoreClient, *, application: JsonValue,
                 objects: CallbackObjects, limits: JsonValue = None,
                 allowed_actions: tuple[str, ...] = _BROKER_ACTIONS,
                 invocation_handler: Callable[[str, JsonValue], HostCompletion] | None = None,
                 cancelled: Callable[[], bool] | None = None):
        _require(isinstance(core, CoreClient) and core.role == 'core', 'Callback sessions require an explicit Core role')
        if os.name != 'posix':
            raise CoreUnavailable('Callback sessions currently require POSIX')
        self._limits = dict(_DEFAULTS)
        if limits is not None:
            reduced = _object(limits, set(_DEFAULTS), 'Callback limits')
            _require(all(type(reduced[key]) is int and 0 < reduced[key] <= maximum
                         for key, maximum in _DEFAULTS.items()), 'Callback limits require positive integer reductions')
            self._limits = cast(dict[str, int], dict(reduced))
        _require(isinstance(objects, CallbackObjects), 'Callback sessions require a local object broker')
        objects.counts  # Check broker ownership before launching a process.
        _require(type(allowed_actions) is tuple and bool(allowed_actions), 'Callback actions require an explicit allowlist')
        for action in allowed_actions:
            _name(action, _FIXED['max_action_bytes'], 'action')
        _require(len(set(allowed_actions)) == len(allowed_actions), 'Duplicate callback action')
        self._allowed_actions = frozenset(allowed_actions)
        self.objects = objects
        self._handler = objects.execute if invocation_handler is None else invocation_handler
        _require(callable(self._handler), 'Callback invocation handler must be callable')
        self._application = encode_document(application)
        self._core = core
        self._owner_pid, self._owner = os.getpid(), threading.current_thread()
        self._nonce = str(uuid4())
        self._next_sequence = self._next_event = 0
        self._input_bytes = self._output_bytes = self._frame_count = self._node_count = self._command_count = 0
        self._commands: list[_Command] = []
        self._handlers: list[_Command] = []
        self._invocations: list[int] = []
        self._traffic: list[CallbackFrame] = []
        self._sent: dict[int, bytes] = {}
        self._usage: dict[str, int] | None = None
        self._stderr = bytearray()
        self._eof: set[str] = set()
        self._closed = self._invalidated = False
        self._last_response: CallbackResponse | None = None
        if cancelled is not None and cancelled():
            raise CoreCancelled('Callback session cancelled before launch')
        path = Path(core.executable)
        if not path.is_file() or not os.access(path, os.X_OK):
            raise CoreUnavailable('Selected callback Core is not executable: ' + str(path))
        try:
            with path.open('rb') as binary:
                self._executable_sha256 = hashlib.file_digest(binary, 'sha256').hexdigest()
        except OSError as exception:
            raise CoreUnavailable('Cannot read selected callback Core') from exception
        if core.expected_sha256 is not None and self._executable_sha256 != core.expected_sha256:
            raise CoreUnavailable('Selected callback Core does not match its release pin')
        self._selector = selectors.DefaultSelector()
        try:
            self._process = subprocess.Popen([str(path), ARGUMENT], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        except BaseException as exception:
            self._selector.close()
            if isinstance(exception, OSError):
                raise CoreUnavailable('Cannot launch selected callback Core') from exception
            raise
        self._finalizer = weakref.finalize(self, _dispose, self._process, self._selector, self._owner_pid)
        try:
            for label, pipe in (('stdin', self._process.stdin), ('stdout', self._process.stdout), ('stderr', self._process.stderr)):
                assert pipe is not None
                os.set_blocking(pipe.fileno(), False)
                if label != 'stdin':
                    self._selector.register(pipe, selectors.EVENT_READ, label)
            self.hello_response = self._request('hello', 'hello', {
                'declaration': capability_profile(), 'application': decode_document(self._application),
                'limits': None if limits is None else cast(JsonValue, dict(self._limits)),
            }, cancelled)
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
    def traffic(self) -> tuple[CallbackFrame, ...]:
        """Complete transferred frames, in actual local send/receive order."""
        return tuple(self._traffic)

    @property
    def last_response(self) -> CallbackResponse | None:
        return self._last_response

    def _check_owner(self) -> None:
        _require(os.getpid() == self._owner_pid and threading.current_thread() is self._owner,
                 'Callback session belongs to its creating thread and process')
        _require(not self._closed, 'Callback session is closed; it cannot reconnect')

    def _invalidate(self) -> None:
        self._closed = self._invalidated = True
        self._finalizer()

    def _check_time(self, deadline: float) -> None:
        for command in self._commands:
            if command.cancelled is not None and command.cancelled():
                raise CoreCancelled('Callback session command cancelled')
        if time.monotonic() >= deadline:
            raise CoreTimeout('Callback session command exceeded its deadline')

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
                raise CoreTransportError('Callback session stderr limit exceeded')
            self._stderr.extend(chunk)
        return chunk

    def _quiet(self) -> None:
        for key, _ in self._selector.select(0):
            if key.data != 'stdin':
                chunk = self._read(key)
                if key.data == 'stdout' and chunk:
                    raise CoreProtocolError('Unsolicited or trailing callback session output')

    def _exchange(self, body: bytes, deadline: float) -> bytes:
        self._quiet()
        if self._eof or self._process.poll() is not None:
            raise CoreTransportError('Callback session process or pipe was lost')
        packet = _frame(body)
        _require(self._input_bytes + self._output_bytes + len(packet) + _FIXED['terminal_bytes'] <= self._limits['max_total_bytes'],
                 'Callback session aggregate byte limit exceeded')
        _require(self._frame_count + 2 <= self._limits['max_frames'], 'Callback session frame limit exceeded')
        self._input_bytes += len(packet)
        self._frame_count += 1
        value = cast(dict[str, Any], decode_document(body, max_nodes=self._frame_node_limit()))
        self._node_count += _nodes(value)
        _require(self._node_count <= self._limits['max_json_nodes'], 'Callback session cumulative JSON node limit exceeded')
        self._sent[value['sequence']] = body
        assert self._process.stdin is not None
        self._selector.register(self._process.stdin, selectors.EVENT_WRITE, 'stdin')
        sent = 0
        received = bytearray()
        length: int | None = None
        ceiling = max(self._limits['max_frame_bytes'], _FIXED['terminal_bytes'])
        while True:
            self._check_time(deadline)
            for key, _ in self._selector.select(min(0.05, max(0.0, deadline - time.monotonic()))):
                if key.data == 'stdin':
                    try:
                        sent += os.write(key.fd, packet[sent:sent + 65_536])
                    except BlockingIOError:
                        continue
                    except BrokenPipeError as exception:
                        raise CoreTransportError('Callback Core closed its input during a frame') from exception
                    if sent == len(packet):
                        self._selector.unregister(key.fileobj)
                        self._traffic.append(CallbackFrame('client', value['sequence'], body))
                else:
                    chunk = self._read(key)
                    if key.data != 'stdout':
                        continue
                    received.extend(chunk)
                    _require(self._input_bytes + self._output_bytes + len(received) <= self._limits['max_total_bytes'],
                             'Callback session aggregate byte limit exceeded')
                    if length is None and len(received) >= HEADER_BYTES:
                        header = received[:HEADER_BYTES]
                        _require(header[8] == 10 and all(value in b'0123456789abcdef' for value in header[:8]),
                                 'Invalid callback frame header')
                        length = int(header[:8], 16)
                        _require(0 < length <= ceiling, 'Callback frame byte limit exceeded')
                    if length is not None:
                        _require(len(received) <= HEADER_BYTES + length, 'Trailing or multiple callback frames')
            if length is not None and len(received) == HEADER_BYTES + length:
                _require(sent == len(packet), 'Callback event preceded the complete client frame')
                self._output_bytes += len(received)
                self._frame_count += 1
                raw = bytes(received[HEADER_BYTES:])
                self._traffic.append(CallbackFrame('server', self._next_event, raw))
                self._quiet()
                return raw
            # Exit can race with a readiness snapshot while the final reply is
            # still buffered. Only stdout EOF proves an incomplete frame; the
            # existing deadline also bounds pipes inherited by descendants.
            if 'stdout' in self._eof:
                raise CoreTransportError('Callback Core exited with an incomplete frame')

    def _finish(self, deadline: float) -> None:
        assert self._process.stdin is not None
        self._process.stdin.close()
        while self._selector.get_map() or self._process.poll() is None:
            self._check_time(deadline)
            for key, _ in self._selector.select(min(0.05, max(0.0, deadline - time.monotonic()))):
                if key.data == 'stdout' and self._read(key):
                    raise CoreProtocolError('Trailing output after callback closure')
                if key.data != 'stdout':
                    self._read(key)
        if self._process.wait() != 0:
            raise CoreTransportError('Closed callback session exited unsuccessfully')
        self._closed = True
        self._selector.close()
        for pipe in (self._process.stdout, self._process.stderr):
            assert pipe is not None
            pipe.close()
        self._finalizer.detach()

    def _frame_node_limit(self) -> int:
        return min(_FIXED['max_frame_json_nodes'], self._limits['max_json_nodes'])

    def _body(self, kind: str, fields: dict[str, JsonValue]) -> bytes:
        value: JsonValue = {'protocol': PROTOCOL, 'profile': PROFILE, 'session_id': self._nonce,
            'kind': kind, 'sequence': self._next_sequence, **fields}
        body = encode_document(value, max_bytes=self._limits['max_frame_bytes'], max_nodes=self._frame_node_limit())
        self._next_sequence += 1
        return body

    def _usage_check(self, usage: Any, *, pending: int, fatal: bool) -> None:
        value = _object(usage, set(capability_profile()['usage_fields']), 'Callback usage')
        _require(all(type(item) is int and item >= 0 for item in value.values()), 'Callback usage requires nonnegative integers')
        totals = {self._limits['max_work']}
        if fatal and len(self._commands) == 1 and self._commands[0].operation == 'hello':
            totals.add(_DEFAULTS['max_work'])
        _require(value['work_charged'] + value['work_remaining'] in totals
                 and value['work_charged'] >= _FIXED['terminal_work'], 'Callback lifetime work ancestor changed')
        if not fatal:
            _require(value['input_bytes'] == self._input_bytes and value['output_bytes'] == self._output_bytes
                and value['frames'] == self._frame_count and value['commands'] == self._command_count
                and value['json_nodes'] == self._node_count and value['pending_invocations'] == pending,
                'Callback usage changed its exact wire or invocation census')
            _require(value['frames'] < self._limits['max_frames'] and value['commands'] <= self._limits['max_commands']
                and value['json_nodes'] <= self._limits['max_json_nodes']
                and value['pending_invocations'] <= self._limits['max_pending_invocations']
                and value['retained_bytes'] <= self._limits['max_retained_bytes']
                and value['input_bytes'] + value['output_bytes'] + _FIXED['terminal_bytes'] <= self._limits['max_total_bytes'],
                'Callback resources exceeded without closure')
        if self._usage is not None:
            _require(value['work_remaining'] <= self._usage['work_remaining']
                and all(value[key] >= self._usage[key] for key in ('work_charged', 'input_bytes', 'output_bytes',
                    'frames', 'commands', 'json_nodes', 'retained_bytes')), 'Callback lifetime counters were reset')
        self._usage = cast(dict[str, int], value)

    def _event(self, raw: bytes, command: _Command) -> dict[str, Any]:
        value = decode_document(raw, max_bytes=max(self._limits['max_frame_bytes'], _FIXED['terminal_bytes']),
                                max_nodes=max(self._frame_node_limit(), _FIXED['terminal_bytes']))
        _require(type(value) is dict, 'Callback event must be an object')
        fields = cast(dict[str, Any], value)
        kind = fields.get('kind')
        _require(type(kind) is str and kind in ('reply', 'invoke', 'fatal'), 'Unknown callback event kind')
        _object(fields, set(capability_profile()['server_fields'][kind]), 'Callback event')
        _require(fields['protocol'] == PROTOCOL and fields['profile'] == PROFILE and fields['session_id'] == self._nonce
            and type(fields['event_id']) is int and fields['event_id'] == self._next_event,
            'Callback event session, profile or sequence mismatch')
        self._next_event += 1
        frame_nodes = _nodes(value)
        self._node_count += frame_nodes
        if kind == 'fatal':
            _require(len(raw) + HEADER_BYTES <= _FIXED['terminal_bytes'] and fields['closed'] is True
                and fields['code'] == 'pipeline_callback_fatal', 'Malformed callback fatal event')
            sequence, digest = fields['sequence'], fields['request_sha256']
            _require((sequence is None and digest is None) or (type(sequence) is int and sequence in self._sent
                and digest == hashlib.sha256(self._sent[sequence]).hexdigest()), 'Callback fatal request binding mismatch')
            self._usage_check(fields['usage'], pending=0, fatal=True)
            raise CallbackFatal(raw)
        _require(len(raw) <= self._limits['max_frame_bytes'] and frame_nodes <= self._frame_node_limit()
                 and self._node_count <= self._limits['max_json_nodes'],
                 'Callback normal event exceeds document limits')
        parent = self._invocations[-1] if self._invocations else None
        if kind == 'invoke':
            _require(command.operation != 'hello' and command.operation != 'close', 'Lifecycle command requested a callback')
            _require(type(fields['invocation_id']) is int and fields['invocation_id'] == fields['event_id']
                and fields['parent_invocation'] == parent and type(fields['parent_invocation']) is type(parent)
                and type(fields['command_sequence']) is int and fields['command_sequence'] == command.sequence
                and fields['command_sha256'] == hashlib.sha256(command.document).hexdigest(),
                'Callback invocation authority or stack binding mismatch')
            action = _name(fields['action'], _FIXED['max_action_bytes'], 'action')
            _require(action in self._allowed_actions, 'Callback action is outside the negotiated local allowlist')
            self._usage_check(fields['usage'], pending=len(self._invocations) + 1, fatal=False)
        else:
            _require(type(fields['sequence']) is int and fields['sequence'] == command.sequence
                and fields['request_sha256'] == hashlib.sha256(command.document).hexdigest(),
                'Callback reply is not bound to its original command')
            _require(type(fields['closed']) is bool and fields['closed'] == (command.operation == 'close'),
                     'Callback reply has contradictory closure')
            self._usage_check(fields['usage'], pending=len(self._invocations), fatal=False)
        return fields

    def _continuation(self, fields: dict[str, Any], raw: bytes, command: _Command) -> bytes:
        invocation = fields['invocation_id']
        _require(len(self._invocations) < self._limits['max_pending_invocations'], 'Callback invocation depth exceeded')
        self._invocations.append(invocation)
        self._handlers.append(command)
        try:
            completion = self._handler(fields['action'], fields['arguments'])
            _require(type(completion) is HostCompletion, 'Callback handler returned an invalid completion')
            value = completion.value
            if completion.status == 'ok':
                outcome: JsonValue = {'status': 'return', 'value': value}
            else:
                _require(completion.status == 'exception', 'Callback handler returned an unknown status')
                token = _name(_object(value, {'exception_token'}, 'Callback exception')['exception_token'],
                              _FIXED['max_token_bytes'], 'exception token')
                command.exception_tokens.add(token)
                outcome = {'status': 'raise', 'token': token}
            self._check_time(command.deadline)
            return self._body('continue', {'invocation_id': invocation,
                'invocation_sha256': hashlib.sha256(raw).hexdigest(), 'outcome': outcome})
        finally:
            self._handlers.pop()
            self._invocations.pop()

    def _request(self, kind: str, operation: str, fields: dict[str, JsonValue],
                 cancelled: Callable[[], bool] | None) -> CallbackResponse:
        self._check_owner()
        deadline = min([time.monotonic() + self._core.timeout_seconds] + [item.deadline for item in self._commands])
        body = self._body(kind, fields)
        sequence = self._next_sequence - 1
        command = _Command(sequence, operation, body, deadline, cancelled)
        self._commands.append(command)
        try:
            _require(self._command_count < self._limits['max_commands'], 'Callback command limit exceeded')
            self._command_count += 1
            outgoing = body
            while True:
                raw = self._exchange(outgoing, deadline)
                event = self._event(raw, command)
                if event['kind'] == 'invoke':
                    outgoing = self._continuation(event, raw, command)
                    continue
                outcome = event['outcome']
                _require(type(outcome) is dict and type(outcome.get('status')) is str
                    and outcome['status'] in ('ok', 'rejected', 'raise'), 'Invalid callback reply outcome')
                status = outcome['status']
                _object(outcome, {'status', 'token' if status == 'raise' else 'value'}, 'Callback reply outcome')
                if status == 'raise':
                    token = _name(outcome['token'], _FIXED['max_token_bytes'], 'exception token')
                    _require(token in command.exception_tokens, 'Native response imported an unbound host exception')
                if operation == 'hello':
                    _require(status == 'ok', 'Callback hello was rejected')
                    result = _object(outcome['value'], {'declaration', 'application', 'limits'}, 'Callback hello result')
                    _require(encode_document(result['declaration']) == _DECLARATION_JSON.encode('utf-8')
                        and encode_document(result['application']) == self._application
                        and encode_document(result['limits']) == encode_document(cast(JsonValue, self._limits)),
                        'Callback negotiation changed its exact declarations or limits')
                if operation == 'close':
                    _require(status == 'ok' and outcome['value'] is None, 'Callback close returned an invalid outcome')
                    self._finish(deadline)
                elif self._eof or self._process.poll() is not None:
                    raise CoreTransportError('Callback Core exited without closing its live channel')
                response = CallbackResponse(sequence, event['event_id'], operation, status, event['closed'], body, raw)
                self._last_response = response
                break
        except BaseException:
            self._invalidate()
            raise
        finally:
            self._commands.pop()
        # Rethrow only outside internal except blocks. A logical rejection or an
        # original Python exception leaves the actual native manager usable.
        if response.status == 'raise':
            self.objects.rethrow(token)
        if response.status == 'rejected':
            raise CallbackRejected(response)
        return response

    def call(self, operation: str, arguments: JsonValue, *, cancelled: Callable[[], bool] | None = None) -> CallbackResponse:
        self._check_owner()
        _name(operation, _FIXED['max_action_bytes'], 'operation')
        _require(operation not in ('hello', 'close'), 'Use callback session lifecycle methods')
        _require(not self._commands or (bool(self._handlers) and self._handlers[-1] is self._commands[-1]),
                 'Reentrant commands require the currently executing host handler')
        parent = self._invocations[-1] if self._invocations else None
        return self._request('command', operation, {'parent_invocation': parent, 'operation': operation,
                                                  'arguments': arguments}, cancelled)

    def close(self) -> CallbackResponse | None:
        _require(os.getpid() == self._owner_pid and threading.current_thread() is self._owner,
                 'Callback session belongs to its creating thread and process')
        if self._closed:
            return None
        _require(not self._commands and not self._invocations, 'Cannot close inside an active callback')
        return self._request('close', 'close', {'parent_invocation': None}, None)

    def __enter__(self) -> CorePipelineCallbackSession:
        self._check_owner()
        return self

    def __exit__(self, kind: Any, value: Any, traceback: Any) -> None:
        if kind is None:
            self.close()
        else:
            try:
                self.close()
            except BaseException:
                self._invalidate()
