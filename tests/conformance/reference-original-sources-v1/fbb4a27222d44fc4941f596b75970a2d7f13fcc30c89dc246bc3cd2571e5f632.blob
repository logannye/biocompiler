"""Bounded declarative molecular records and explicit provenance, without proof."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import math
from typing import ClassVar
from types import MappingProxyType

from biocompiler.artifacts.manifest import _Record
from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.serialization import parse_json, require


MAX_MOLECULE_JSON_BYTES = 4_000_000
MAX_MOLECULE_ITEMS = 100_000
MAX_MOLECULE_DEPTH = 96
MAX_RESIDUES = 1_000_000
MAX_TEXT_BYTES = 4096
CANONICAL_ALPHABETS = MappingProxyType(
    {
        "DNA": frozenset("ACGT"),
        "RNA": frozenset("ACGU"),
        "protein": frozenset("ACDEFGHIKLMNPQRSTVWYOU"),
    }
)


def _text(value, label, maximum=MAX_TEXT_BYTES):
    require(
        isinstance(value, str) and len(value) <= maximum,
        f"Invalid or excessive {label} text.",
    )
    require(
        bool(value.strip()) and value == value.strip(),
        f"{label} must be nonempty text without surrounding whitespace.",
    )
    require(
        not any(ord(char) < 32 or ord(char) == 127 for char in value),
        f"Invalid control character in {label}.",
    )
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as error:
        raise SerializationError(f"{label} must be UTF-8.") from error
    require(size <= maximum, f"{label} exceeds its byte limit.")


def _choice(value, options, label):
    require(isinstance(value, str) and value in options, f"Invalid {label}.")


def _bounded_tree(value):
    pending = [(value, 0, False)]
    active = set()
    count = size = 0
    while pending:
        item, depth, closing = pending.pop()
        if closing:
            active.remove(id(item))
            continue
        count += 1
        require(count <= MAX_MOLECULE_ITEMS, "Molecule item limit exceeded.")
        require(depth <= MAX_MOLECULE_DEPTH, "Molecule nesting limit exceeded.")
        if isinstance(item, (Mapping, tuple, list)):
            require(id(item) not in active, "Cyclic molecular record.")
            children = 2 * len(item) if isinstance(item, Mapping) else len(item)
            require(
                count + len(pending) + children <= MAX_MOLECULE_ITEMS,
                "Molecule pending item limit exceeded.",
            )
            active.add(id(item))
            pending.append((item, depth, True))
            if isinstance(item, Mapping):
                for key, child in item.items():
                    require(
                        isinstance(key, str), "Molecular JSON keys must be strings."
                    )
                    pending.extend(((key, depth + 1, False), (child, depth + 1, False)))
            else:
                pending.extend((child, depth + 1, False) for child in item)
            size += children + 2
        elif isinstance(item, str):
            require(len(item) <= MAX_RESIDUES, "Molecule text limit exceeded.")
            try:
                encoded = len(item.encode("utf-8"))
            except UnicodeError as error:
                raise SerializationError("Molecular text must be UTF-8.") from error
            require(encoded <= MAX_RESIDUES, "Molecule text byte limit exceeded.")
            size += encoded + 2
        elif type(item) is int:
            require(item.bit_length() <= 4096, "Molecular integer limit exceeded.")
            size += len(str(item))
        elif type(item) is float:
            require(math.isfinite(item), "Molecular numbers must be finite.")
            size += len(repr(item))
        else:
            require(
                item is None or type(item) is bool,
                "Molecular records require JSON values.",
            )
            size += 5
        require(size <= MAX_MOLECULE_JSON_BYTES, "Molecule byte limit exceeded.")


class _MoleculeRecord(_Record):
    @classmethod
    def from_dict(cls, data):
        _bounded_tree(data)
        return super().from_dict(data)

    @classmethod
    def from_json(cls, text):
        require(isinstance(text, str), "Molecular JSON must be text.")
        require(len(text) <= MAX_MOLECULE_JSON_BYTES, "Molecule byte limit exceeded.")
        try:
            size = len(text.encode("utf-8"))
        except UnicodeError as error:
            raise SerializationError("Molecular JSON must be UTF-8.") from error
        require(size <= MAX_MOLECULE_JSON_BYTES, "Molecule byte limit exceeded.")
        return cls.from_dict(parse_json(text))

    def to_json(self, *, indent=2):
        require(
            indent is None or (type(indent) is int and 0 <= indent <= 8),
            "Molecular indentation must be None or an integer from 0 to 8.",
        )
        data = self.to_dict()
        _bounded_tree(data)
        # Bound pretty-printed expansion while encoding, before joining the
        # document. One byte is reserved for the published trailing newline.
        encoder = json.JSONEncoder(
            sort_keys=True, indent=indent, ensure_ascii=False, allow_nan=False
        )
        chunks, size = [], 1
        try:
            for chunk in encoder.iterencode(data):
                size += len(chunk.encode("utf-8"))
                require(
                    size <= MAX_MOLECULE_JSON_BYTES,
                    "Molecule byte limit exceeded (including publication newline).",
                )
                chunks.append(chunk)
        except (TypeError, ValueError, UnicodeError, RecursionError) as error:
            if isinstance(error, SerializationError):
                raise
            raise SerializationError(f"Invalid molecular encoding: {error}") from error
        return "".join(chunks)

    def _check_resources(self):
        self.to_json()


def _optional(cls):
    return lambda value: None if value is None else cls.from_dict(value)


def _decode_records(cls, maximum):
    def decode(values):
        require(
            isinstance(values, (tuple, list)) and len(values) <= maximum,
            "Invalid molecular record array.",
        )
        return tuple(cls.from_dict(value) for value in values)

    return decode


def _records(values, cls, maximum, label, *, key="id", nonempty=False):
    require(isinstance(values, (tuple, list)), f"{label} must be an array.")
    require(int(nonempty) <= len(values) <= maximum, f"Invalid {label} count.")
    require(
        all(isinstance(value, cls) for value in values), f"Invalid {label} record type."
    )
    result = tuple(cls.from_dict(value.to_dict()) for value in values)
    ids = [getattr(value, key) for value in result]
    require(len(set(ids)) == len(ids), f"Duplicate {label} identities.")
    return tuple(sorted(result, key=lambda value: getattr(value, key)))


@dataclass(frozen=True)
class DeclarationProvenance(_MoleculeRecord):
    """Traceable declarations or explicit missing provenance, never evidence PASS."""

    status: str
    authority: tuple[PinnedIdentity, ...]
    locator: str | None
    reason: str
    schema_version: ClassVar[str] = "biocompiler.molecular_declaration_provenance.v0.1"
    _decoders: ClassVar[dict] = {"authority": _decode_records(PinnedIdentity, 16)}

    def __post_init__(self):
        _choice(self.status, {"declared", "unknown"}, "provenance status")
        _text(self.reason, "Provenance reason")
        require(
            isinstance(self.authority, (tuple, list))
            and len(self.authority) <= 16
            and all(isinstance(pin, PinnedIdentity) for pin in self.authority),
            "Invalid provenance authority inventory.",
        )
        pins = tuple(PinnedIdentity.from_dict(pin.to_dict()) for pin in self.authority)
        require(
            all(pin.kind in {"source", "evidence"} for pin in pins),
            "Provenance requires source/evidence pins.",
        )
        require(
            len({(pin.kind, pin.id, pin.version) for pin in pins}) == len(pins),
            "Duplicate or conflicting provenance authority.",
        )
        object.__setattr__(
            self,
            "authority",
            tuple(sorted(pins, key=lambda pin: (pin.kind, pin.id, pin.version))),
        )
        if self.status == "declared":
            require(bool(pins), "Declared provenance requires authority pins.")
            _text(self.locator, "Provenance locator")
        else:
            require(
                not pins and self.locator is None,
                "Unknown provenance cannot invent source authority or a locator.",
            )
        self._check_resources()
