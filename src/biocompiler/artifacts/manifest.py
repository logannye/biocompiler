"""Portable reference-build authority and deterministic manifest identities.

Manifest success labels describe archived claims. Import alone never grants
acceptance: rebuilding with current trusted tools must reproduce their evidence.
Run metadata is a separate artifact and does not enter the canonical build hash.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields as dataclass_fields
from datetime import datetime, timezone
from pathlib import PurePosixPath, PureWindowsPath
import re
from types import MappingProxyType
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir.construct import ConstructRequest
from biocompiler.ir.intent import freeze_json
from biocompiler.ir.serialization import JsonArtifact, fields, name, require


REQUIRED_FILES = MappingProxyType(
    {
        "request.json": "request",
        "inputs/registry.json": "registry",
        "stages/components.json": "components-stage",
        "stages/construct.json": "construct-stage",
        "stages/molecular.json": "molecular-stage",
        "molecular.json": "molecular-specification",
        "sequence.fasta": "sequence",
        "result.json": "build-summary",
        "checks/construct.json": "construct-check",
        "checks/molecular.json": "molecular-check",
        "checks/composition.json": "composition-check",
    }
)
RESERVED_FILES = frozenset({"manifest.json", "run.json"})
_STAGES = ("components", "construct", "molecular")


def _hash(value, label):
    require(
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value),
        f"{label} must be a SHA-256 fingerprint.",
    )


def _unicode_text(value, label):
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise SerializationError(f"{label} must contain valid UTF-8 Unicode.") from exc


def _plain_text(value, label):
    name(value, label)
    _unicode_text(value, label)
    require(
        not any(ord(char) < 32 or ord(char) == 127 for char in value),
        f"{label} cannot contain control characters.",
    )
    return value


def _logical_path(value, label):
    _plain_text(value, label)
    require(
        "\\" not in value
        and ":" not in value
        and not value.startswith("/")
        and all(part not in {"", ".", ".."} for part in value.split("/")),
        f"{label} must be a canonical relative POSIX path without traversal.",
    )
    return value


def validate_package_path(path: str, *, allow_reserved: bool = False) -> str:
    """Validate an archive name without reading it or resolving a host path."""
    _logical_path(path, "Package path")
    require(
        allow_reserved or path not in RESERVED_FILES,
        "Manifest and run metadata are not package inventory files.",
    )
    return path


def _portable_sources(value):
    if isinstance(value, Mapping):
        if set(value) == {"file", "line", "function"}:
            _logical_path(value["file"], "Logical source location")
        for key, item in value.items():
            _unicode_text(key, "Reference request key")
            _portable_sources(item)
    elif isinstance(value, (tuple, list)):
        for item in value:
            _portable_sources(item)
    elif isinstance(value, str):
        _unicode_text(value, "Reference request text")


def _array(value, item_type, label):
    require(isinstance(value, (tuple, list)), f"{label} must be an array.")
    require(all(isinstance(item, item_type) for item in value), f"Invalid {label}.")
    return tuple(value)


def _decode_array(value, item_type):
    require(isinstance(value, (tuple, list)), "Manifest records must be arrays.")
    return tuple(item_type.from_dict(item) for item in value)


class _Record(JsonArtifact):
    _decoders: ClassVar[dict] = {}

    def to_dict(self):
        def encode(value):
            if hasattr(value, "to_dict"):
                return value.to_dict()
            if isinstance(value, Mapping):
                return {key: encode(item) for key, item in value.items()}
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            return value

        return {
            "schema_version": self.schema_version,
            **{
                item.name: encode(getattr(self, item.name))
                for item in dataclass_fields(self)
            },
        }

    @classmethod
    def from_dict(cls, data):
        try:
            fields(
                data,
                {item.name for item in dataclass_fields(cls)} | {"schema_version"},
                cls.__name__,
            )
            require(
                data["schema_version"] == cls.schema_version,
                f"Unsupported {cls.__name__} schema.",
            )
            return cls(
                **{
                    item.name: cls._decoders.get(item.name, lambda value: value)(
                        data[item.name]
                    )
                    for item in dataclass_fields(cls)
                }
            )
        except SerializationError:
            raise
        except (
            TypeError,
            ValueError,
            KeyError,
            IndexError,
            AttributeError,
            OverflowError,
            RecursionError,
        ) as exc:
            raise SerializationError(f"Invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True)
class ReferenceBuildRequest(_Record):
    """Build authority for an explicitly selected component-root CDS profile.

    No upstream intent graph or behavioral refinement is invented. Logical source
    names must already be frozen before construct identities are computed.
    """

    construct: ConstructRequest
    profile: str = "reference_cds"
    artifact_scope: str = "exact_cds"
    fasta_line_width: int = 80
    schema_version: ClassVar[str] = "biocompiler.reference_build_request.v0.1"
    _decoders: ClassVar[dict] = {"construct": ConstructRequest.from_dict}

    def __post_init__(self):
        require(
            isinstance(self.construct, ConstructRequest), "Expected a ConstructRequest."
        )
        require(self.profile == "reference_cds", "Unsupported reference build profile.")
        require(
            self.artifact_scope == "exact_cds", "Unsupported reference build scope."
        )
        require(
            type(self.fasta_line_width) is int and 1 <= self.fasta_line_width <= 10000,
            "FASTA line width must be an integer from 1 to 10000.",
        )
        _portable_sources(self.construct.to_dict())


@dataclass(frozen=True)
class RunMetadata(_Record):
    """Optional execution context; never input to canonical artifact/build hashes."""

    timestamp_utc: str
    machine_label: str
    locations: Mapping[str, str] = field(default_factory=dict)
    schema_version: ClassVar[str] = "biocompiler.run_metadata.v0.1"

    def __post_init__(self):
        _plain_text(self.timestamp_utc, "Run timestamp")
        require(
            re.fullmatch(
                r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z",
                self.timestamp_utc,
            )
            is not None,
            "Run timestamp must use an explicit UTC ISO-8601 Z representation.",
        )
        try:
            parsed = datetime.fromisoformat(self.timestamp_utc.replace("Z", "+00:00"))
            require(
                parsed.utcoffset() == timezone.utc.utcoffset(None),
                "Run timestamp must be UTC.",
            )
        except ValueError as exc:
            raise SerializationError("Invalid UTC run timestamp.") from exc
        _plain_text(self.machine_label, "Machine label")
        require(isinstance(self.locations, Mapping), "Run locations must be a mapping.")
        for logical, location in self.locations.items():
            _logical_path(logical, "Logical source location")
            _plain_text(location, "Run source location")
            require(
                PurePosixPath(location).is_absolute()
                or PureWindowsPath(location).is_absolute(),
                "Run locations must contain explicit absolute host paths.",
            )
        object.__setattr__(self, "locations", freeze_json(dict(self.locations)))


@dataclass(frozen=True)
class PackageFile(_Record):
    path: str
    role: str
    sha256: str
    byte_length: int
    schema_version: ClassVar[str] = "biocompiler.package_file.v0.1"

    def __post_init__(self):
        validate_package_path(self.path)
        _plain_text(self.role, "Package file role")
        _hash(self.sha256, "Package file content")
        require(
            type(self.byte_length) is int and self.byte_length >= 0,
            "Invalid package file byte length.",
        )
        if self.role == "reference-input":
            parts = self.path.split("/")
            require(
                len(parts) >= 3 and parts[0] == "references",
                "Reference inputs must be under references/<reference-set>/<file>.",
            )
        else:
            require(
                REQUIRED_FILES.get(self.path) == self.role,
                "Package file path/role is not part of the reference-build profile.",
            )


@dataclass(frozen=True)
class AcceptedStage(_Record):
    """Archived payload and StageRecord identities, not a reusable success token."""

    stage: str
    artifact_fingerprint: str
    record_fingerprint: str
    artifact_schema: str
    schema_version: ClassVar[str] = "biocompiler.accepted_stage.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.stage, str) and self.stage in _STAGES,
            "Invalid accepted stage.",
        )
        _hash(self.artifact_fingerprint, "Stage payload")
        _hash(self.record_fingerprint, "Stage record")
        _plain_text(self.artifact_schema, "Stage payload schema")
        expected_schemas = {
            "components": "biocompiler.construct_request.v0.1",
            "construct": "biocompiler.construct.v0.1",
            "molecular": "biocompiler.molecular.v0.1",
        }
        require(
            self.artifact_schema == expected_schemas[self.stage],
            "Stage payload schema does not match the reference-build profile.",
        )


@dataclass(frozen=True)
class ToolPin(_Record):
    id: str
    version: str
    content_fingerprint: str
    schema_version: ClassVar[str] = "biocompiler.tool_pin.v0.1"

    def __post_init__(self):
        _plain_text(self.id, "Tool ID")
        _plain_text(self.version, "Tool version")
        _hash(self.content_fingerprint, "Tool content")


@dataclass(frozen=True)
class BuildManifest(_Record):
    """Deterministic complete exact-CDS package inventory and archived claims."""

    request_fingerprint: str
    files: tuple[PackageFile, ...]
    accepted_stages: tuple[AcceptedStage, ...]
    toolchain: tuple[ToolPin, ...]
    package_version: str
    profile: str = "reference_cds"
    status: str = "complete"
    scope: str = "exact_cds"
    schema_version: ClassVar[str] = "biocompiler.build_manifest.v0.1"
    _decoders: ClassVar[dict] = {
        "files": lambda value: _decode_array(value, PackageFile),
        "accepted_stages": lambda value: _decode_array(value, AcceptedStage),
        "toolchain": lambda value: _decode_array(value, ToolPin),
    }

    def __post_init__(self):
        _hash(self.request_fingerprint, "Reference build request")
        _plain_text(self.package_version, "Package version")
        require(
            self.profile == "reference_cds"
            and self.status == "complete"
            and self.scope == "exact_cds",
            "Unsupported build manifest profile/status/scope.",
        )
        files = _array(self.files, PackageFile, "Package files")
        require(
            len({item.path for item in files}) == len(files), "Duplicate package paths."
        )
        inventory = {item.path: item.role for item in files}
        require(
            not any(
                "/".join(path.split("/")[:index]) in inventory
                for path in inventory
                for index in range(1, len(path.split("/")))
            ),
            "Package file paths cannot overlap directory prefixes.",
        )
        require(
            all(inventory.get(path) == role for path, role in REQUIRED_FILES.items()),
            "Reference build manifest is missing a required file role.",
        )
        require(
            any(item.role == "reference-input" for item in files),
            "Reference build manifest requires offline reference inputs.",
        )
        object.__setattr__(
            self, "files", tuple(sorted(files, key=lambda item: item.path))
        )
        stages = _array(self.accepted_stages, AcceptedStage, "Accepted stages")
        require(
            tuple(item.stage for item in stages) == _STAGES,
            "Accepted stages must be exactly components, construct, molecular in order.",
        )
        object.__setattr__(self, "accepted_stages", stages)
        tools = _array(self.toolchain, ToolPin, "Toolchain")
        require(bool(tools), "Build manifests must pin their toolchain.")
        require(len({item.id for item in tools}) == len(tools), "Duplicate tool IDs.")
        object.__setattr__(
            self, "toolchain", tuple(sorted(tools, key=lambda item: item.id))
        )

    @property
    def build_fingerprint(self):
        """Hash canonical manifest content; excludes manifest/run files and metadata."""
        return self.fingerprint
