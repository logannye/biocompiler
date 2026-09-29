"""Strict JSON and stable identity shared by versioned immutable artifacts."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from typing import Any, ClassVar

from cellweave.errors import SerializationError
from cellweave.ir.intent import freeze_json, thaw_json


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SerializationError(message)


def name(value: Any, label: str) -> str:
    require(
        isinstance(value, str) and bool(value.strip()),
        f"{label} must be a nonempty string.",
    )
    return value


def fields(data: Any, expected: set[str], label: str) -> None:
    require(
        isinstance(data, Mapping) and set(data) == expected,
        f"Invalid fields in {label}.",
    )


def names(values: Any, label: str) -> tuple[str, ...]:
    require(isinstance(values, (tuple, list)), f"{label} must be an array.")
    result = tuple(name(item, label) for item in values)
    require(len(set(result)) == len(result), f"{label} must be unique.")
    return result


def fingerprint(value: Any) -> str:
    encoded = json.dumps(
        thaw_json(freeze_json(value)),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def parse_json(text: str) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"Duplicate JSON key: {key}.")
            result[key] = value
        return result

    def invalid(value):
        raise SerializationError(f"Invalid JSON number: {value}.")

    try:
        return json.loads(text, object_pairs_hook=unique, parse_constant=invalid)
    except (TypeError, ValueError, RecursionError) as exc:
        if isinstance(exc, SerializationError):
            raise
        raise SerializationError(f"Invalid artifact JSON: {exc}") from exc


class JsonArtifact:
    """Serialization conveniences; subclasses supply checked to_dict/from_dict."""

    schema_version: ClassVar[str]

    def to_dict(self) -> dict:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: Mapping):
        raise NotImplementedError

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            indent=indent,
            ensure_ascii=False,
            allow_nan=False,
        )

    @classmethod
    def from_json(cls, text: str):
        return cls.from_dict(parse_json(text))

    @property
    def fingerprint(self) -> str:
        return fingerprint(self.to_dict())
