"""Local objects for explicitly negotiated trusted pipeline continuations.

This broker performs requested Python object operations in their original order.
It does not run a compiler pass manager, accept records, validate a biological
claim, or decide when an operation should occur. The native manager drives those
steps. Handles are local to this broker and cannot reconstruct native authority.

Handle counts, operation counts and serialized observations are bounded. Arbitrary
trusted Python callables, iterators, descriptors and their captured objects are
outside the native deterministic work and retained-JSON accounting proof.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import importlib
import json
import os
import threading
from types import TracebackType
from typing import Any, NoReturn, cast

from biocompiler.core_client import CoreProtocolError, JsonValue
from biocompiler.core_pipeline_session import decode_document, encode_document


class CallbackObjectProtocolError(CoreProtocolError):
    """A broker capability, instruction or resource boundary was violated."""


class _BrokerFault(CallbackObjectProtocolError):
    """Distinguish our own boundary failures from user-raised exceptions."""


@dataclass(frozen=True)
class ObjectLimits:
    max_objects: int = 100_000
    max_providers: int = 10_000
    max_exceptions: int = 1_024
    max_actions: int = 1_000_000
    max_document_bytes: int = 33_554_432
    max_document_nodes: int = 1_000_000

    def __post_init__(self) -> None:
        ceilings = (100_000, 10_000, 1_024, 1_000_000, 33_554_432, 1_000_000)
        values = (self.max_objects, self.max_providers, self.max_exceptions,
                  self.max_actions, self.max_document_bytes, self.max_document_nodes)
        if any(type(value) is not int or not 0 < value <= maximum
               for value, maximum in zip(values, ceilings)):
            raise _BrokerFault('Callback object limits must be positive reductions')


@dataclass(frozen=True)
class HostCompletion:
    """An immutable local completion; the transport must bind its invocation."""
    status: str
    document: bytes

    @property
    def value(self) -> JsonValue:
        return decode_document(self.document)


@dataclass(frozen=True)
class _ExceptionState:
    exception: BaseException
    traceback: TracebackType | None
    cause: BaseException | None
    context: BaseException | None
    suppress_context: bool


_TYPES: dict[str, tuple[str, str]] = {
    'PassResult': ('biocompiler.compiler.passes', 'PassResult'),
    'CheckDecision': ('biocompiler.compiler.pipeline', 'CheckDecision'),
    'PassContract': ('biocompiler.compiler.pipeline', 'PassContract'),
    'ComponentInputContract': ('biocompiler.compiler.pipeline', 'ComponentInputContract'),
    'CompletionProfile': ('biocompiler.compiler.pipeline', 'CompletionProfile'),
    'ScopedObligation': ('biocompiler.compiler.pipeline', 'ScopedObligation'),
    'SourceLink': ('biocompiler.artifacts.provenance', 'SourceLink'),
    'BuildRequest': ('biocompiler.compiler.request', 'BuildRequest'),
    'RealizationRequest': ('biocompiler.compiler.request', 'RealizationRequest'),
    'TargetContext': ('biocompiler.semantics.context', 'TargetContext'),
    'SyntheticGeneratorConfig': ('biocompiler.synthesis.synthetic', 'SyntheticGeneratorConfig'),
    'EvidenceKind': ('biocompiler.verification.evidence', 'EvidenceKind'),
    'CheckOutcome': ('biocompiler.verification.evidence', 'CheckOutcome'),
    'Stage': ('biocompiler.ir.stages', 'Stage'),
    'ArtifactStatus': ('biocompiler.compiler.pipeline', 'ArtifactStatus'),
    'PayloadFormat': ('biocompiler.semantics.context', 'PayloadFormat'),
}
_ENUM_TYPES = frozenset(('EvidenceKind', 'CheckOutcome', 'Stage', 'ArtifactStatus', 'PayloadFormat'))
_BUILTIN_TYPES: dict[str, Any] = {'Mapping': Mapping, 'str': str, 'int': int,
    'float': float, 'bool': bool, 'tuple': tuple, 'list': list}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise _BrokerFault(message)


def _fields(value: Any, expected: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == expected, 'Malformed callback object instruction')
    return cast(dict[str, Any], value)


def _text(value: Any) -> str:
    _require(type(value) is str and 0 < len(value) <= 256, 'Invalid callback object name')
    return cast(str, value)


def _known_type(name: Any) -> Any:
    name = _text(name)
    if name in _BUILTIN_TYPES:
        return _BUILTIN_TYPES[name]
    _require(name in _TYPES, 'Unknown callback object type')
    module, attribute = _TYPES[name]
    return getattr(importlib.import_module(module), attribute)


class CallbackObjects:
    """One owner thread/process, strong physical identities and no wire imports."""
    def __init__(self, *, limits: ObjectLimits | None = None) -> None:
        self.limits = ObjectLimits() if limits is None else limits
        _require(type(self.limits) is ObjectLimits, 'Invalid callback object limits')
        self._owner_pid = os.getpid()
        self._owner = threading.current_thread()
        self._closed = False
        self._objects: dict[str, Any] = {}
        self._identities: dict[int, str] = {}
        self._providers: dict[str, str] = {}
        self._provider_objects: dict[str, str] = {}
        self._exceptions: dict[str, _ExceptionState] = {}
        self._next_object = self._next_exception = self._actions = 0

    def _check(self) -> None:
        _require(not self._closed, 'Callback object broker is closed')
        _require(os.getpid() == self._owner_pid and threading.current_thread() is self._owner,
                 'Callback objects belong to their creating thread and process')

    @property
    def counts(self) -> dict[str, int]:
        self._check()
        return {'objects': len(self._objects), 'providers': len(self._providers),
                'exceptions': len(self._exceptions), 'actions': self._actions}

    def retain(self, value: Any) -> dict[str, JsonValue]:
        self._check()
        identity = id(value)
        previous = self._identities.get(identity)
        if previous is not None:
            # Strong references prevent id reuse, without invoking user equality.
            _require(self._objects[previous] is value, 'Callback object identity was reused')
            return {'handle': previous}
        _require(len(self._objects) < self.limits.max_objects, 'Callback object handle limit exceeded')
        handle = 'object/' + str(self._next_object)
        self._next_object += 1
        self._objects[handle] = value
        self._identities[identity] = handle
        return {'handle': handle}

    def resolve(self, reference: Any) -> Any:
        self._check()
        reference = _fields(reference, {'handle'})
        handle = _text(reference['handle'])
        _require(handle in self._objects, 'Unknown or released callback object handle')
        return self._objects[handle]

    def release(self, references: Any) -> None:
        self._check()
        _require(type(references) is list, 'Callback release requires a complete reference list')
        handles = []
        for reference in references:
            self.resolve(reference)
            handle = reference['handle']
            _require(handle not in self._provider_objects, 'A bound provider cannot be released while live')
            _require(handle not in handles, 'Duplicate callback object release')
            handles.append(handle)
        # Validate the complete release before mutating the table.
        for handle in handles:
            value = self._objects.pop(handle)
            del self._identities[id(value)]

    def bind_provider(self, provider_id: Any, reference: Any) -> None:
        """Install a native-minted token only during its bound invocation."""
        self._check()
        provider_id = _text(provider_id)
        value = self.resolve(reference)
        _require(callable(value), 'A native provider binding requires a retained callable')
        handle = reference['handle']
        previous = self._providers.get(provider_id)
        if previous is not None:
            _require(previous == handle, 'Native provider token was rebound to another object')
            return
        _require(handle not in self._provider_objects, 'One callable identity received multiple native provider tokens')
        _require(len(self._providers) < self.limits.max_providers, 'Callback provider handle limit exceeded')
        self._providers[provider_id] = handle
        self._provider_objects[handle] = provider_id

    def _capture(self, exception: BaseException) -> HostCompletion:
        _require(len(self._exceptions) < self.limits.max_exceptions, 'Callback exception handle limit exceeded')
        token = 'exception/' + str(self._next_exception)
        self._next_exception += 1
        slots = BaseException.__dict__
        self._exceptions[token] = _ExceptionState(exception,
            slots['__traceback__'].__get__(exception), slots['__cause__'].__get__(exception),
            slots['__context__'].__get__(exception), slots['__suppress_context__'].__get__(exception))
        # Even str(exception) can execute trusted user code. Do not invoke it
        # merely to transport a failure; retain and rethrow the actual object.
        return HostCompletion('exception', encode_document({'exception_token': token}))

    def rethrow(self, token: Any) -> NoReturn:
        """Call outside transport except blocks, after matching native response."""
        self._check()
        token = _text(token)
        _require(token in self._exceptions, 'Unknown or consumed callback exception token')
        state = self._exceptions.pop(token)
        exception = state.exception
        slots = BaseException.__dict__
        slots['__cause__'].__set__(exception, state.cause)
        slots['__context__'].__set__(exception, state.context)
        slots['__suppress_context__'].__set__(exception, state.suppress_context)
        raise BaseException.with_traceback(exception, state.traceback)

    def close(self) -> None:
        if self._closed:
            return
        self._check()
        self._objects.clear()
        self._identities.clear()
        self._providers.clear()
        self._provider_objects.clear()
        self._exceptions.clear()
        self._closed = True

    def execute(self, action: str, arguments: JsonValue) -> HostCompletion:
        """Execute one exact native-requested primitive, allowing nested calls."""
        self._check()
        _require(self._actions < self.limits.max_actions, 'Callback action limit exceeded')
        self._actions += 1
        # Instructions arrive as plain, bounded JSON. Validate local callers too,
        # so malformed instruction objects cannot execute Python user hooks.
        arguments = self._copy_json(arguments)
        try:
            value = self._evaluate(action, arguments)
        except _BrokerFault:
            raise
        except BaseException as exception:
            return self._capture(exception)
        # A failure to encode our completion is a transport boundary violation,
        # not an exception thrown by the retained Python object.
        try:
            document = encode_document(value, max_bytes=self.limits.max_document_bytes,
                                       max_nodes=self.limits.max_document_nodes)
        except CoreProtocolError as exception:
            raise _BrokerFault('Callback completion exceeds the document profile') from exception
        return HostCompletion('ok', document)

    def _copy_json(self, value: Any) -> JsonValue:
        try:
            return decode_document(encode_document(value, max_bytes=self.limits.max_document_bytes,
                max_nodes=self.limits.max_document_nodes), max_bytes=self.limits.max_document_bytes,
                max_nodes=self.limits.max_document_nodes)
        except CoreProtocolError as exception:
            raise _BrokerFault('Callback instruction exceeds the document profile') from exception

    def _json(self, value: Any) -> JsonValue:
        from biocompiler.ir.intent import thaw_json
        # JSON's handling of str/int subclasses must remain intact. The strict
        # session parser bounds the resulting plain document before it crosses
        # the wire; it never imports accepted manager state.
        encoder = json.JSONEncoder(sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        raw = bytearray()
        for piece in encoder.iterencode(thaw_json(value)):
            encoded = piece.encode('utf-8')
            _require(len(raw) + len(encoded) <= self.limits.max_document_bytes,
                     'Callback JSON observation byte limit exceeded')
            raw.extend(encoded)
        try:
            return decode_document(bytes(raw), max_bytes=self.limits.max_document_bytes,
                                   max_nodes=self.limits.max_document_nodes)
        except CoreProtocolError as exception:
            raise _BrokerFault('Callback JSON observation exceeds the document profile') from exception

    def _evaluate(self, action: str, arguments: JsonValue) -> JsonValue:
        _require(type(action) is str, 'Invalid callback object action')
        if action == 'literal':
            args = _fields(arguments, {'value', 'kind'})
            kind = args['kind']
            value = args['value']
            _require(kind in ('json', 'tuple', 'set'), 'Unknown callback literal kind')
            if kind != 'json':
                _require(type(value) is list, 'Callback collection literal requires an array')
                if kind == 'set':
                    _require(all(type(item) in (str, int, float, bool, type(None)) for item in value),
                             'Callback set literals require scalar members')
                return self.retain(tuple(value) if kind == 'tuple' else set(value))
            return self.retain(value)
        if action == 'enum':
            args = _fields(arguments, {'type', 'value'})
            name = _text(args['type'])
            _require(name in _ENUM_TYPES, 'Unknown callback enum type')
            enum = _known_type(name)
            _require(type(args['value']) is str and args['value'] in enum._value2member_map_,
                     'Unknown callback enum value')
            return self.retain(enum(args['value']))
        if action == 'bind-provider':
            args = _fields(arguments, {'provider_id', 'object'})
            self.bind_provider(args['provider_id'], args['object'])
            return None
        if action == 'release':
            self.release(_fields(arguments, {'handles'})['handles'])
            return None
        if action == 'call-provider':
            args = _fields(arguments, {'provider_id', 'context'})
            provider_id = _text(args['provider_id'])
            _require(provider_id in self._providers, 'Unknown native provider token')
            provider = self._objects[self._providers[provider_id]]
            return self.retain(provider(self.resolve(args['context'])))
        if action == 'call':
            args = _fields(arguments, {'callable', 'args', 'kwargs'})
            _require(type(args['args']) is list and type(args['kwargs']) is dict,
                     'Malformed callback call arguments')
            function = self.resolve(args['callable'])
            positional = [self.resolve(value) for value in args['args']]
            keywords = {key: self.resolve(value) for key, value in args['kwargs'].items()}
            return self.retain(function(*positional, **keywords))
        if action in ('attr', 'attr-default'):
            args = _fields(arguments, {'object', 'name'} | ({'default'} if action == 'attr-default' else set()))
            value, name = self.resolve(args['object']), _text(args['name'])
            return self.retain(getattr(value, name) if action == 'attr'
                               else getattr(value, name, self.resolve(args['default'])))
        if action == 'is-instance':
            args = _fields(arguments, {'object', 'type'})
            return isinstance(self.resolve(args['object']), _known_type(args['type']))
        if action == 'compare':
            args = _fields(arguments, {'left', 'right', 'operator'})
            left, right = self.resolve(args['left']), self.resolve(args['right'])
            operator = args['operator']
            if operator == 'eq':
                return bool(left == right)
            if operator == 'ne':
                return bool(left != right)
            if operator == 'is':
                return left is right
            if operator == 'is-not':
                return left is not right
            raise _BrokerFault('Unknown callback comparison operator')
        if action == 'contains':
            args = _fields(arguments, {'container', 'item'})
            return self.resolve(args['item']) in self.resolve(args['container'])
        if action == 'get-item':
            args = _fields(arguments, {'object', 'key'})
            return self.retain(self.resolve(args['object'])[self.resolve(args['key'])])
        if action == 'set-attribute-equal':
            args = _fields(arguments, {'objects', 'name', 'values'})
            _require(type(args['objects']) is list and type(args['values']) is list,
                     'Callback attribute-set comparison requires arrays')
            _require(all(type(item) in (str, int, float, bool, type(None)) for item in args['values']),
                     'Callback set literals require scalar members')
            objects = [self.resolve(reference) for reference in args['objects']]
            attribute = _text(args['name'])
            # Preserve getter/hash interleaving in the original comprehension.
            return {getattr(value, attribute) for value in objects} == set(args['values'])
        if action == 'lookup':
            args = _fields(arguments, {'object', 'entries'})
            _require(type(args['entries']) is list, 'Callback lookup requires entries')
            entries = args['entries']
            _require(all(type(entry) is list and len(entry) == 2 and type(entry[0]) is str
                         for entry in entries), 'Malformed callback lookup entries')
            _require(len({entry[0] for entry in entries}) == len(entries),
                     'Duplicate callback lookup key')
            mapping = {entry[0]: entry[1] for entry in entries}
            return self.retain(mapping[self.resolve(args['object'])])
        if action == 'merge':
            args = _fields(arguments, {'object', 'before', 'after'})
            _require(type(args['before']) is dict and type(args['after']) is dict,
                     'Callback merge literals must be objects')
            # Dict unpacking intentionally rejects pair iterables that update()
            # accepts, and preserves Mapping keys/getitem evaluation order.
            return self.retain({**args['before'], **self.resolve(args['object']), **args['after']})
        _require(action in ('is-none', 'truth', 'callable', 'iter', 'next', 'tuple', 'list', 'dict', 'len',
                            'mapping-items', 'mapping-values', 'mapping-keys', 'vars', 'document', 'freeze-json', 'json'),
                 'Unknown callback object action')
        value = self.resolve(_fields(arguments, {'object'})['object'])
        if action == 'is-none':
            return value is None
        if action == 'truth':
            return bool(value)
        if action == 'callable':
            return callable(value)
        if action == 'iter':
            return self.retain(iter(value))
        if action == 'next':
            try:
                item = next(value)
            except StopIteration:
                return {'exhausted': True, 'object': None}
            return {'exhausted': False, 'object': self.retain(item)}
        if action == 'tuple':
            return self.retain(tuple(value))
        if action == 'list':
            return self.retain(list(value))
        if action == 'dict':
            return self.retain(dict(value))
        if action == 'len':
            return len(value)
        if action == 'mapping-items':
            return self.retain(value.items())
        if action == 'mapping-values':
            return self.retain(value.values())
        if action == 'mapping-keys':
            return self.retain(value.keys())
        if action == 'vars':
            return self.retain(vars(value))
        if action == 'document':
            # Native validation must follow this conversion. Do not eagerly
            # inspect schema, freeze attributes or read an optional fingerprint.
            return self.retain(value if isinstance(value, Mapping) else value.to_dict())
        if action == 'freeze-json':
            from biocompiler.ir.intent import freeze_json
            return self.retain(freeze_json(value))
        return self._json(value)
