"""Frozen synthetic build inputs and inventories; imported claims are historical."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import ClassVar

from biocompiler.artifacts.manifest import (
    ToolPin,
    _Record,
    _array,
    _decode_array,
    _hash,
    _plain_text,
    _portable_sources,
    validate_package_path,
)
from biocompiler.compiler.request import RealizationRequest
from biocompiler.ir.serialization import fields, require
from biocompiler.semantics.evaluator import InputFrame, SignalSample
from biocompiler.synthesis.synthetic import SyntheticGeneratorConfig

REQUIRED_FILES = MappingProxyType(
    {
        "request.json": "request",
        "inputs/history.json": "history",
        "inputs/config.json": "generator-config",
        "inputs/catalog.json": "synthetic-catalog",
        "stages/request.json": "request-stage",
        "stages/behavior.json": "behavior-stage",
        "stages/mechanism.json": "mechanism-stage",
        "candidate.json": "synthetic-candidate",
        "selection.json": "synthetic-selection",
        "checks/realization.json": "realization-check",
        "result.json": "build-summary",
    }
)
COMPONENT_FILES = MappingProxyType(
    {
        "assembly.json": "component-assembly",
        "stages/components.json": "components-stage",
        "checks/composition.json": "component-composition-check",
        "checks/component-behavior.json": "component-behavior-check",
    }
)
ALL_FILES = MappingProxyType({**REQUIRED_FILES, **COMPONENT_FILES})


def required_files(profile):
    require(
        isinstance(profile, str)
        and profile in {"synthetic_realization", "synthetic_components"},
        "Unsupported synthetic package profile.",
    )
    return ALL_FILES if profile == "synthetic_components" else REQUIRED_FILES


def _sample(data):
    fields(data, {"value", "present", "high", "low"}, "SignalSample")
    return SignalSample(**data)


def _signals(data):
    require(isinstance(data, Mapping), "History signals must be an object.")
    return {key: _sample(value) for key, value in data.items()}


def _frame(data):
    fields(data, {"time", "signals", "contacts"}, "InputFrame")
    require(
        isinstance(data["contacts"], Mapping), "History contacts must be an object."
    )
    return InputFrame(
        data["time"],
        _signals(data["signals"]),
        {key: _signals(value) for key, value in data["contacts"].items()},
    )


def _frames(data):
    require(isinstance(data, (tuple, list)), "History frames must be an array.")
    return tuple(_frame(item) for item in data)


@dataclass(frozen=True)
class SyntheticHistory(_Record):
    """Complete observation snapshots in canonical seconds; no executable input."""

    frames: tuple[InputFrame, ...]
    schema_version: ClassVar[str] = "biocompiler.synthetic_history.v0.1"
    _decoders: ClassVar[dict] = {"frames": _frames}

    def __post_init__(self):
        frames = _array(self.frames, InputFrame, "History frames")
        require(bool(frames), "A synthetic build needs a nonempty history.")
        require(frames[0].time == 0, "A synthetic build history must begin at zero.")
        require(
            all(a.time < b.time for a, b in zip(frames, frames[1:])),
            "History times must be strictly increasing.",
        )
        object.__setattr__(self, "frames", frames)


@dataclass(frozen=True)
class SyntheticBuildRequest(_Record):
    """Independent build authority binds behavior, observations, horizon and policy."""

    realization: RealizationRequest
    history: SyntheticHistory
    until: int | float
    config: SyntheticGeneratorConfig = field(default_factory=SyntheticGeneratorConfig)
    profile: str = "synthetic_realization"
    intended_use: str = "software_test"
    schema_version: ClassVar[str] = "biocompiler.synthetic_build_request.v0.2"
    _decoders: ClassVar[dict] = {
        "realization": RealizationRequest.from_dict,
        "history": SyntheticHistory.from_dict,
        "config": SyntheticGeneratorConfig.from_dict,
    }

    def __post_init__(self):
        require(
            isinstance(self.realization, RealizationRequest),
            "Expected a frozen RealizationRequest.",
        )
        require(
            isinstance(self.history, SyntheticHistory), "Expected SyntheticHistory."
        )
        require(
            isinstance(self.config, SyntheticGeneratorConfig),
            "Expected SyntheticGeneratorConfig.",
        )
        require(
            type(self.until) in {int, float}, "An explicit finite horizon is required."
        )
        try:
            finite = math.isfinite(self.until)
        except OverflowError:
            finite = False
        require(
            finite and self.until >= self.history.frames[-1].time,
            "Horizon must be finite and at least the last input time.",
        )
        required_files(self.profile)
        require(
            self.intended_use == "software_test",
            "Synthetic builds only support software_test use.",
        )
        require(
            self.realization.build_request.artifact_scope == "synthetic_realization",
            "The source request must select synthetic_realization scope.",
        )
        _portable_sources(self.realization.to_dict())
        provenance = self.realization.build_request.provenance
        require(
            not provenance.locations and provenance.recorded_at is None,
            "Host locations and run timestamps belong in separate RunMetadata.",
        )


@dataclass(frozen=True)
class SyntheticPackageFile(_Record):
    path: str
    role: str
    sha256: str
    byte_length: int
    schema_version: ClassVar[str] = "biocompiler.synthetic_package_file.v0.2"

    def __post_init__(self):
        validate_package_path(self.path)
        require(
            ALL_FILES.get(self.path) == self.role,
            "Unsupported synthetic package path/role.",
        )
        _hash(self.sha256, "Synthetic package file")
        require(
            type(self.byte_length) is int and self.byte_length >= 0,
            "Invalid synthetic file byte length.",
        )


@dataclass(frozen=True)
class SyntheticBuildManifest(_Record):
    request_fingerprint: str
    files: tuple[SyntheticPackageFile, ...]
    toolchain: tuple[ToolPin, ...]
    package_version: str
    profile: str = "synthetic_realization"
    status: str = "complete"
    scope: str = "synthetic_realization"
    intended_use: str = "software_test"
    human_therapeutic_admission: str = "not_admitted"
    schema_version: ClassVar[str] = "biocompiler.synthetic_build_manifest.v0.2"
    _decoders: ClassVar[dict] = {
        "files": lambda value: _decode_array(value, SyntheticPackageFile),
        "toolchain": lambda value: _decode_array(value, ToolPin),
    }

    def __post_init__(self):
        _hash(self.request_fingerprint, "Synthetic build request")
        _plain_text(self.package_version, "Package version")
        inventory = required_files(self.profile)
        require(
            self.profile == self.scope and self.status == "complete",
            "Unsupported synthetic manifest profile/status/scope.",
        )
        require(
            self.intended_use == "software_test"
            and self.human_therapeutic_admission == "not_admitted",
            "Synthetic manifests cannot admit human therapeutic use.",
        )
        files = _array(self.files, SyntheticPackageFile, "Synthetic package files")
        require(
            len(files) == len(inventory)
            and {item.path: item.role for item in files} == inventory,
            "Synthetic manifest requires the exact file inventory.",
        )
        tools = _array(self.toolchain, ToolPin, "Toolchain")
        require(
            bool(tools) and len({item.id for item in tools}) == len(tools),
            "Synthetic manifest must pin unique tools.",
        )
        object.__setattr__(
            self, "files", tuple(sorted(files, key=lambda item: item.path))
        )
        object.__setattr__(
            self, "toolchain", tuple(sorted(tools, key=lambda item: item.id))
        )

    @property
    def build_fingerprint(self):
        return self.fingerprint
