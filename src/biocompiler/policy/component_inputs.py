"""Immutable supplied component authority, separate from an authored policy.

This package preserves caller declarations verbatim. It neither repairs stale
bindings nor establishes that a material contract realizes behavior in cells.
Only fresh native checking can assess a new source against these inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import cast

from biocompiler.core_client import JsonValue, decode_json, encode_json
from biocompiler import core_policy_component_material as component
from biocompiler import core_policy_implementation as implementation
from . import component_material
from .implementation import prepare_request as prepare_implementation
from .model import BuildRequest
from .research_project import MAX_PROJECT_BYTES, ResearchProjectError, _publish_json, _read_file

SCHEMA = "biocompiler.policy_component_inputs.v0.1"
MAX_INPUT_BYTES = MAX_PROJECT_BYTES
_IMPLEMENTATION = {"definitions", "operating_domain", "implementation_library", "catalog_bindings", "budgets"}
_MATERIAL = {"component_library", "composition_rule", "catalog_binding", "input_bindings", "resource_bindings", "context", "budgets"}


class ComponentInputsError(ResearchProjectError):
    """Missing or malformed supplied authority; not a native semantic judgment."""


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ComponentInputsError(message)


def _parts(value: JsonValue) -> dict[str, JsonValue]:
    _require(type(value) is dict and set(value) == {"schema_version", "implementation", "material"},
             "Component inputs require their exact versioned implementation and material fields")
    row = cast(dict[str, JsonValue], value)
    _require(row["schema_version"] == SCHEMA, "Unsupported component inputs schema")
    for name, fields, list_fields in (
        ("implementation", _IMPLEMENTATION, {"catalog_bindings"}),
        ("material", _MATERIAL, {"input_bindings", "resource_bindings"}),
    ):
        part = row[name]
        _require(type(part) is dict and set(part) == fields,
                 "Component inputs require complete " + name + " authority without a source document")
        for key, item in cast(dict[str, JsonValue], part).items():
            if key in list_fields:
                _require(type(item) is list and all(type(entry) is dict for entry in item),
                         name + "." + key + " must contain explicit records")
            else:
                _require(type(item) is dict, name + "." + key + " must be an explicit record")
    return row


@dataclass(frozen=True)
class ComponentMaterialInputs:
    """Canonical caller-owned authority; all returned JSON views are detached.

    The fixed schemas select the existing component-material request route.
    Native support, supplied pin validity and source correspondence are not
    inferred from structural construction or loading.
    """
    _json: bytes
    _input_paths: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        _require(type(self._json) is bytes and 0 < len(self._json) <= MAX_INPUT_BYTES,
                 "Component inputs require bounded canonical JSON bytes")
        row = _parts(decode_json(self._json))
        _require(encode_json(row, limit=MAX_INPUT_BYTES) == self._json, "Component inputs must use canonical JSON")
        _require(type(self._input_paths) is tuple and all(isinstance(path, Path) for path in self._input_paths),
                 "Component input paths must be immutable paths")

    @classmethod
    def from_data(cls, value: JsonValue) -> ComponentMaterialInputs:
        """Freeze complete declarations without semantic admission or repinning."""
        return cls(encode_json(value, limit=MAX_INPUT_BYTES))

    @classmethod
    def from_request(cls, request: JsonValue) -> ComponentMaterialInputs:
        """Extract every non-source authority from an existing complete request.

        Request parsing is structural. Candidate results and acceptance labels
        cannot supply inputs. The original source is deliberately not retained.
        """
        original = component._original(decode_json(encode_json(request, limit=MAX_INPUT_BYTES)))
        supplied = cast(dict[str, JsonValue], original["implementation_request"])
        _require(supplied["schema_version"] == implementation.REQUEST_SCHEMA and
                 supplied["profile"] == implementation.REQUEST_PROFILE, "Unsupported implementation request profile")
        return cls.from_data({"schema_version": SCHEMA,
            "implementation": {key: supplied[key] for key in _IMPLEMENTATION},
            "material": {key: original[key] for key in _MATERIAL}})

    @classmethod
    def load(cls, path: Path | str) -> ComponentMaterialInputs:
        """Read bounded literal JSON without executing code or following locators.

        Malformed protocol JSON raises CoreProtocolError; invalid package fields
        raise ComponentInputsError. File protections raise ResearchProjectError,
        while ordinary filesystem failures retain their OSError diagnostics.
        """
        source = Path(path)
        inputs = cls.from_data(decode_json(_read_file(source, MAX_INPUT_BYTES)))
        return cls(inputs._json, (source.resolve(),))

    @property
    def data(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._json))

    @property
    def digest(self) -> str:
        return hashlib.sha256(self._json).hexdigest()

    def dump(self, path: Path | str, *, replace: bool = False) -> None:
        """Publish canonical inputs atomically, protecting loaded originals."""
        _publish_json(self._json, Path(path), self._input_paths, replace=replace)

    def prepare(self, document: BuildRequest) -> dict[str, JsonValue]:
        """Pair a typed source with unchanged authority for fresh native checking.

        Changing the source never changes a model, definition, catalog pin,
        composition rule, material carrier, domain or provider declaration.
        Incompatible pairs remain visible to the native checker.
        """
        _require(type(document) is BuildRequest, "Component input preparation requires an original typed BuildRequest")
        parts = self.data
        supplied = cast(dict[str, JsonValue], parts["implementation"])
        material = cast(dict[str, JsonValue], parts["material"])
        request = prepare_implementation(document, definitions=supplied["definitions"],
            operating_domain=supplied["operating_domain"], implementation_library=supplied["implementation_library"],
            catalog_bindings=supplied["catalog_bindings"], budgets=supplied["budgets"])
        return component_material.prepare_request(implementation_request=request,
            component_library=material["component_library"], composition_rule=material["composition_rule"],
            catalog_binding=material["catalog_binding"], input_bindings=material["input_bindings"],
            resource_bindings=material["resource_bindings"], context=material["context"], budgets=material["budgets"])
