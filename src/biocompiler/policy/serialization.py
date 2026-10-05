"""Bounded, data-only encoding for the closed policy declaration registry.

Wire tags name reviewed declarations, never Python import paths. These codecs
establish representation validity only; they do not establish policy semantics.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import types
from typing import Any, Literal, NoReturn, TypeAlias, TypeVar, Union, cast, get_args, get_origin, get_type_hints, overload

from . import model

JSONValue: TypeAlias = None | bool | int | str | list['JSONValue'] | dict[str, 'JSONValue']
R = TypeVar('R', bound=model.Record)


class PolicySerializationError(ValueError):
    """A document is outside the closed authoring representation contract."""


@dataclass(frozen=True)
class SerializationLimits:
    max_bytes: int = 2 * 1024 * 1024
    max_depth: int = 64
    max_nodes: int = 100_000
    max_string_bytes: int = 262_144
    max_number_characters: int = 256
    max_decimal_exponent: int = 1024

    def __post_init__(self) -> None:
        if any(type(getattr(self, item.name)) is not int or getattr(self, item.name) <= 0
               for item in fields(self)):
            raise PolicySerializationError('Serialization limits must be positive integers.')


DEFAULT_LIMITS = SerializationLimits()
# Snapshot after importing the complete model; importing plugins cannot extend
# this decoder's class authority.
_CLOSED_REGISTRY = dict(model.REGISTRY)
_DECIMAL = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z')


def _fail(message: str) -> NoReturn:
    raise PolicySerializationError(message)


class _Budget:
    def __init__(self, limits: SerializationLimits):
        if type(limits) is not SerializationLimits:
            _fail('Expected serialization limits.')
        self.limits, self.nodes, self.payload_bytes = limits, 0, 0

    def payload(self, size: int) -> None:
        # Bound aggregate scalar storage while traversing caller-owned objects,
        # before constructing a complete encoded graph or JSON string. The final
        # renderer additionally checks punctuation, quoting and escape bytes.
        self.payload_bytes += size
        if self.payload_bytes > self.limits.max_bytes:
            _fail('Policy document exceeds its aggregate payload byte limit.')

    def visit(self, depth: int) -> None:
        self.nodes += 1
        if depth > self.limits.max_depth or self.nodes > self.limits.max_nodes:
            _fail('Policy document exceeds its depth or node limit.')

    def string(self, value: str) -> None:
        if len(value) > self.limits.max_string_bytes:
            _fail('Policy string exceeds its byte limit.')
        try:
            size = len(value.encode('utf-8'))
        except UnicodeError as error:
            raise PolicySerializationError('Policy strings must be valid UTF-8.') from error
        if size > self.limits.max_string_bytes:
            _fail('Policy string exceeds its byte limit.')
        self.payload(size)


def _registry() -> dict[str, type]:
    result = _CLOSED_REGISTRY
    if not isinstance(result, Mapping):
        _fail('Policy registry is unavailable.')
    for name, kind in result.items():
        if (type(name) is not str or not isinstance(kind, type)
                or not issubclass(kind, model.Record) or not is_dataclass(kind)
                or kind.__name__ != name or kind.__module__ != model.__name__
                or vars(model).get(name) is not kind):
            _fail('Policy registry contains an invalid declaration.')
    return dict(result)


def _decimal(value: str, budget: _Budget) -> Decimal:
    if type(value) is not str or len(value) > budget.limits.max_number_characters or not _DECIMAL.fullmatch(value):
        _fail('Decimal values require bounded finite decimal text.')
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise PolicySerializationError('Invalid decimal value.') from error
    exponent = parsed.as_tuple().exponent
    if not parsed.is_finite() or not isinstance(exponent, int) or abs(exponent) > budget.limits.max_decimal_exponent:
        _fail('Decimal value exceeds its finite exponent bound.')
    return parsed


def _encode(value: Any, budget: _Budget, depth: int, registry: dict[str, type]) -> Any:
    budget.visit(depth)
    kind = type(value)
    if kind is str:
        budget.string(value)
        return value
    if value is None or kind is bool:
        return value
    if kind is int:
        if value.bit_length() > budget.limits.max_number_characters * 4 or len(str(value)) > budget.limits.max_number_characters:
            _fail('Integer value exceeds its digit bound.')
        budget.payload(len(str(value)))
        return value
    if kind is Decimal:
        encoded = str(value)
        _decimal(encoded, budget)
        return encoded
    if isinstance(value, Enum):
        if type(value.value) is not str:
            _fail('Policy enums require string values.')
        budget.string(value.value)
        return value.value
    if kind is tuple:
        return [_encode(item, budget, depth + 1, registry) for item in value]
    if kind in registry.values():
        data: dict[str, Any] = {'$type': kind.__name__}
        for item in fields(value):
            if item.name == '$type':
                _fail('Policy declaration fields cannot shadow the wire tag.')
            budget.visit(depth + 1)
            budget.string(item.name)
            data[item.name] = _encode(getattr(value, item.name), budget, depth + 1, registry)
        return data
    _fail('Policy values must use registered immutable declarations and exact scalar types.')


def _decode(value: Any, expected: Any, budget: _Budget, depth: int, registry: dict[str, type]) -> Any:
    budget.visit(depth)
    origin, arguments = get_origin(expected), get_args(expected)
    if origin in (Union, types.UnionType):
        # A tagged declaration has exactly one registry-selected concrete class.
        # Other alternatives use exact scalar type rules, never coercion.
        for option in arguments:
            try:
                return _decode(value, option, budget, depth, registry)
            except PolicySerializationError:
                pass
        _fail('Policy value does not match any declared union alternative.')
    if origin is Literal:
        if not any(type(value) is type(item) and value == item for item in arguments):
            _fail('Policy value is outside its declared literal alternatives.')
        return value
    if origin is tuple:
        if type(value) is not list:
            _fail('Policy tuple fields require JSON arrays.')
        if len(arguments) == 2 and arguments[1] is Ellipsis:
            return tuple(_decode(item, arguments[0], budget, depth + 1, registry) for item in value)
        if len(value) != len(arguments):
            _fail('Policy tuple has the wrong number of elements.')
        return tuple(_decode(item, item_type, budget, depth + 1, registry)
                     for item, item_type in zip(value, arguments))
    if expected is type(None):
        if value is not None:
            _fail('Expected null.')
        return None
    if expected in (str, int, bool):
        if type(value) is not expected:
            _fail('Policy scalar type differs from its declaration.')
        if expected is str:
            budget.string(value)
        if expected is int and (value.bit_length() > budget.limits.max_number_characters * 4
                                or len(str(value)) > budget.limits.max_number_characters):
            _fail('Integer value exceeds its digit bound.')
        return value
    if expected is Decimal:
        return _decimal(value, budget)
    if isinstance(expected, type) and issubclass(expected, Enum):
        if type(value) is not str:
            _fail('Policy enums require strings.')
        try:
            return expected(value)
        except ValueError as error:
            raise PolicySerializationError('Unknown policy enum value.') from error
    if isinstance(expected, type) and issubclass(expected, model.Record):
        if type(value) is not dict or type(value.get('$type')) is not str:
            _fail('Policy declarations require an explicit registered kind.')
        actual = registry.get(value['$type'])
        if actual is None or (expected is not model.Record and actual is not expected):
            _fail('Unknown or incompatible policy declaration kind.')
        names = tuple(item.name for item in fields(actual))
        if set(value) != set(names) | {'$type'}:
            _fail('Policy declaration has unknown or missing fields.')
        if actual is model.Quantity:
            _decimal(value['amount'], budget)
        if actual is model.Unit:
            _decimal(value['scale'], budget)
        hints = get_type_hints(actual)
        decoded = {name: _decode(value[name], hints[name], budget, depth + 1, registry)
                   for name in names}
        try:
            return actual(**decoded)
        except (ValueError, TypeError, ArithmeticError) as error:
            raise PolicySerializationError('Invalid policy declaration: ' + str(error)) from error
    _fail('Policy declaration uses an unsupported field type.')


def _measure(value: Any, budget: _Budget, depth: int = 0) -> None:
    budget.visit(depth)
    if type(value) is str:
        budget.string(value)
    elif value is None or type(value) is bool:
        return
    elif type(value) is int:
        if value.bit_length() > budget.limits.max_number_characters * 4 or len(str(value)) > budget.limits.max_number_characters:
            _fail('Integer value exceeds its digit bound.')
        budget.payload(len(str(value)))
    elif type(value) is list:
        for item in value:
            _measure(item, budget, depth + 1)
    elif type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                _fail('Policy object keys must be strings.')
            _measure(key, budget, depth + 1)
            _measure(item, budget, depth + 1)
    else:
        _fail('Policy wire values cannot contain floats or arbitrary objects.')


def to_data(document: model.Record, *, limits: SerializationLimits = DEFAULT_LIMITS) -> dict[str, JSONValue]:
    """Return a detached tagged declaration, validating every declared type."""
    registry = _registry()
    if type(document) not in registry.values():
        _fail('Expected a registered policy declaration.')
    result = _encode(document, _Budget(limits), 0, registry)
    # Frozen dataclasses do not enforce annotations at runtime. Reject malformed
    # directly constructed values as strictly as imported wire declarations.
    _decode(result, type(document), _Budget(limits), 0, registry)
    if len(json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')) > limits.max_bytes:
        _fail('Policy document exceeds its byte limit.')
    return cast(dict[str, JSONValue], result)


@overload
def from_data(data: object, expected_type: type[R], *, limits: SerializationLimits = DEFAULT_LIMITS) -> R: ...


@overload
def from_data(data: object, expected_type: None = None, *, limits: SerializationLimits = DEFAULT_LIMITS) -> model.Record: ...


def from_data(data: object, expected_type: type[model.Record] | None = None, *, limits: SerializationLimits = DEFAULT_LIMITS) -> model.Record:
    """Decode only classes in the in-process, reviewed declaration registry."""
    registry = _registry()
    if expected_type is not None and expected_type not in registry.values() and expected_type is not model.Record:
        _fail('Expected type must be a registered policy declaration.')
    _measure(data, _Budget(limits))
    if len(json.dumps(data, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')) > limits.max_bytes:
        _fail('Policy document exceeds its byte limit.')
    return cast(model.Record, _decode(data, expected_type or model.Record, _Budget(limits), 0, registry))


def _text_preflight(text: str, limits: SerializationLimits) -> None:
    # Bound nesting and lexical token counts before the stdlib parser allocates
    # complete containers. JSON validity is still checked by the parser below.
    depth = tokens = 0
    in_string = escaped = in_atom = False
    for character in text:
        if in_string:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string, in_atom = True, False
            tokens += 1
        elif character in '[{':
            depth += 1
            tokens += 1
            in_atom = False
        elif character in ']}':
            depth -= 1
            in_atom = False
        elif character in ' \t\r\n,:':
            in_atom = False
        elif not in_atom:
            tokens += 1
            in_atom = True
        if depth > limits.max_depth or tokens > limits.max_nodes:
            _fail('Policy JSON exceeds its depth or token limit.')


@overload
def loads(text: str | bytes, expected_type: type[R], *, limits: SerializationLimits = DEFAULT_LIMITS) -> R: ...


@overload
def loads(text: str | bytes, expected_type: None = None, *, limits: SerializationLimits = DEFAULT_LIMITS) -> model.Record: ...


def loads(text: str | bytes, expected_type: type[model.Record] | None = None, *, limits: SerializationLimits = DEFAULT_LIMITS) -> model.Record:
    _Budget(limits)
    if type(text) not in (str, bytes):
        _fail('Policy JSON must be UTF-8 bytes or text.')
    if len(text) > limits.max_bytes:
        _fail('Policy JSON exceeds its byte limit.')
    try:
        raw = text if isinstance(text, bytes) else text.encode('utf-8')
        if len(raw) > limits.max_bytes:
            _fail('Policy JSON exceeds its byte limit.')
        decoded = raw.decode('utf-8')
    except UnicodeError as error:
        raise PolicySerializationError('Policy JSON must be valid UTF-8.') from error
    _text_preflight(decoded, limits)

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            if key in result:
                _fail('Policy JSON contains a duplicate key.')
            result[key] = value
        return result

    def integer(value: str) -> int:
        if len(value) > limits.max_number_characters:
            _fail('Policy integer exceeds its digit bound.')
        return int(value)

    def forbidden(_: str) -> Any:
        _fail('Policy JSON forbids raw floats and nonfinite numbers; use typed decimal text.')

    try:
        value = json.loads(decoded, object_pairs_hook=pairs, parse_int=integer,
                           parse_float=forbidden, parse_constant=forbidden)
    except (json.JSONDecodeError, RecursionError) as error:
        raise PolicySerializationError('Invalid policy JSON.') from error
    return from_data(value, expected_type, limits=limits)


def dumps(document: model.Record, *, indent: int | None = 2, limits: SerializationLimits = DEFAULT_LIMITS) -> str:
    if indent is not None and (type(indent) is not int or not 0 <= indent <= 8):
        _fail('Policy JSON indentation must be null or an integer from zero to eight.')
    text = json.dumps(to_data(document, limits=limits), ensure_ascii=False, sort_keys=True,
                      allow_nan=False, indent=indent, separators=(',', ':') if indent is None else None)
    if len(text.encode('utf-8')) > limits.max_bytes:
        _fail('Rendered policy JSON exceeds its byte limit.')
    return text


@overload
def load(path: str | os.PathLike[str], expected_type: type[R], *, limits: SerializationLimits = DEFAULT_LIMITS) -> R: ...


@overload
def load(path: str | os.PathLike[str], expected_type: None = None, *, limits: SerializationLimits = DEFAULT_LIMITS) -> model.Record: ...


def load(path: str | os.PathLike[str], expected_type: type[model.Record] | None = None, *, limits: SerializationLimits = DEFAULT_LIMITS) -> model.Record:
    _Budget(limits)
    with open(path, 'rb') as stream:
        raw = stream.read(limits.max_bytes + 1)
    return loads(raw, expected_type, limits=limits)


def dump(document: model.Record, path: str | os.PathLike[str], *, limits: SerializationLimits = DEFAULT_LIMITS) -> None:
    """Atomically create one complete document; never overwrite an existing path."""
    raw = (dumps(document, limits=limits) + '\n').encode('utf-8')
    if len(raw) > limits.max_bytes:
        _fail('Rendered policy JSON exceeds its byte limit.')
    destination = Path(path)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.policy-', delete=False) as stream:
            temporary = stream.name
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, destination)
    finally:
        if temporary is not None:
            os.unlink(temporary)


def document_digest(document: model.Record, *, limits: SerializationLimits = DEFAULT_LIMITS) -> str:
    """Hash the declaration with source_map/provenance fields excluded recursively."""
    def semantic(value: Any) -> Any:
        if type(value) is dict:
            return {key: semantic(item) for key, item in value.items() if key not in ('source_map', 'provenance')}
        if type(value) is list:
            return [semantic(item) for item in value]
        return value
    raw = json.dumps(semantic(to_data(document, limits=limits)), ensure_ascii=False,
                     sort_keys=True, allow_nan=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def schema(root_type: type[model.Record] | None = None) -> dict[str, JSONValue]:
    """Generate syntactic JSON Schema from the same closed record/type registry."""
    registry = _registry()

    def shape(hint: Any) -> dict[str, Any]:
        origin, args = get_origin(hint), get_args(hint)
        if origin in (Union, types.UnionType):
            return {'anyOf': [shape(item) for item in args]}
        if origin is Literal:
            return {'enum': list(args)}
        if origin is tuple:
            if len(args) == 2 and args[1] is Ellipsis:
                return {'type': 'array', 'items': shape(args[0])}
            return {'type': 'array', 'prefixItems': [shape(item) for item in args],
                    'minItems': len(args), 'maxItems': len(args)}
        if hint in (str, int, bool, type(None)):
            return {'type': {str: 'string', int: 'integer', bool: 'boolean', type(None): 'null'}[hint]}
        if hint is Decimal:
            return {'type': 'string', 'pattern': r'^-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][+-]?[0-9]+)?$',
                    'description': 'Exact finite decimal text; codec bounds also apply.'}
        if isinstance(hint, type) and issubclass(hint, Enum):
            return {'type': 'string', 'enum': [item.value for item in hint]}
        if hint is model.Record:
            return {'oneOf': [{'$ref': '#/$defs/' + name} for name in sorted(registry)]}
        if hint in registry.values():
            return {'$ref': '#/$defs/' + hint.__name__}
        _fail('Policy schema encountered an unsupported declaration type.')

    definitions = {}
    for name, kind in sorted(registry.items()):
        hints = get_type_hints(kind)
        properties = {'$type': {'const': name}, **{item.name: shape(hints[item.name]) for item in fields(kind)}}
        definitions[name] = {'type': 'object', 'properties': properties,
                             'required': list(properties), 'additionalProperties': False}
    if root_type is None:
        roots = [registry[name] for name in ('PolicyDraft', 'PolicyProgram', 'BuildRequest') if name in registry]
        root = {'oneOf': [shape(kind) for kind in roots]} if roots else shape(model.Record)
    elif root_type in registry.values():
        root = shape(root_type)
    else:
        _fail('Schema root must be a registered policy declaration.')
    return cast(dict[str, JSONValue], {'$schema': 'https://json-schema.org/draft/2020-12/schema',
            'title': 'Biocompiler policy declarations (representation only)', **root, '$defs': definitions})
