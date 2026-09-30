"""Frozen build authority, followed by a separately frozen realization request.

Authoring Python is never executed by this module. Output artifacts cannot select
their own input bindings. Provenance locations remain inspectable but are not
part of semantic identities.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, ClassVar

from biocompiler.errors import (
    SerializationError,
    TypeMismatchError,
    UnsupportedBehaviorError,
)
from biocompiler.ir.behavior import BehaviorProgram, SCHEMA_VERSION as BEHAVIOR_PROFILE
from biocompiler.ir.intent import IntentProgram, freeze_json, thaw_json
from biocompiler.ir.serialization import (
    JsonArtifact,
    fields,
    fingerprint,
    name,
    require,
)
from biocompiler.semantics.context import TargetContext
from biocompiler.semantics.realization import BehaviorContract, OperatingDomain
from biocompiler.semantics.types import TypeSpec, decode_binding, validate_binding


def _mapping(value, label):
    require(isinstance(value, Mapping), f"{label} must be an object.")
    return freeze_json(value)


def _schema(data, cls, keys):
    fields(data, keys | {"schema_version"}, cls.__name__)
    require(
        data["schema_version"] == cls.schema_version,
        f"Unsupported {cls.__name__} schema.",
    )


def _strict_import(parse):
    """Keep nested constructors/checkers behind the serialized-input boundary.

    Direct Python construction retains its useful binding/lowering diagnostics;
    an invalid imported request always raises the public serialization error.
    """

    @wraps(parse)
    def read(cls, data):
        try:
            return parse(cls, data)
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

    return read


@dataclass(frozen=True)
class ElaborationProvenance(JsonArtifact):
    """Content identities and captured inputs, distinct from archival locations.

    Keys are stable logical source/dependency names, not workspace paths. Empty
    records explicitly mean provenance was not supplied; they imply no audit.
    """

    source_identities: Mapping[str, str] = field(default_factory=dict)
    dependency_identities: Mapping[str, str] = field(default_factory=dict)
    external_inputs: Mapping[str, Any] = field(default_factory=dict)
    locations: Mapping[str, str] = field(default_factory=dict)
    recorded_at: str | None = None
    schema_version: ClassVar[str] = "biocompiler.elaboration_provenance.v0.1"

    def __post_init__(self):
        for key in (
            "source_identities",
            "dependency_identities",
            "external_inputs",
            "locations",
        ):
            object.__setattr__(self, key, _mapping(getattr(self, key), key))
        for values in (
            self.source_identities,
            self.dependency_identities,
            self.locations,
        ):
            for key, value in values.items():
                name(key, "Logical provenance name")
                name(value, "Provenance identity/location")
        if self.recorded_at is not None:
            name(self.recorded_at, "Provenance timestamp")

    def to_dict(self, *, include_locations=True):
        result = {
            "schema_version": self.schema_version,
            "source_identities": thaw_json(self.source_identities),
            "dependency_identities": thaw_json(self.dependency_identities),
            "external_inputs": thaw_json(self.external_inputs),
        }
        if include_locations:
            result.update(
                locations=thaw_json(self.locations), recorded_at=self.recorded_at
            )
        return result

    @classmethod
    @_strict_import
    def from_dict(cls, data):
        _schema(
            data,
            cls,
            {
                "source_identities",
                "dependency_identities",
                "external_inputs",
                "locations",
                "recorded_at",
            },
        )
        return cls(
            **{key: value for key, value in data.items() if key != "schema_version"}
        )


@dataclass(frozen=True)
class BindingMetadata(JsonArtifact):
    """Meaning of a frozen design value; this does not establish robust behavior.

    Units live in the typed binding itself. Variation is a typed allowed Interval
    when supplied. Runtime observations are graph signals, never design bindings.
    """

    category: str = "user_selected"
    provenance: Mapping[str, Any] = field(default_factory=dict)
    allowed_variation: Mapping[str, Any] | None = None
    schema_version: ClassVar[str] = "biocompiler.binding_metadata.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.category, str)
            and self.category
            in {"user_selected", "compiler_selected", "measured", "uncertain"},
            "Unknown design-value category; runtime observations must remain graph signals.",
        )
        object.__setattr__(
            self, "provenance", _mapping(self.provenance, "Binding provenance")
        )
        if self.allowed_variation is not None:
            variation = _mapping(self.allowed_variation, "Allowed variation")
            try:
                dtype = TypeSpec.from_dict(variation.get("type"))
                require(
                    dtype.kind == "interval"
                    and len(dtype.arguments) == 1
                    and dtype.arguments[0].kind == "scalar",
                    "Allowed variation must be a typed scalar Interval.",
                )
                decode_binding(variation, dtype)
            except (TypeError, ValueError, KeyError, AttributeError) as exc:
                if isinstance(exc, SerializationError):
                    raise
                raise SerializationError(f"Invalid allowed variation: {exc}") from exc
            object.__setattr__(
                self,
                "allowed_variation",
                variation,
            )

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "category": self.category,
            "provenance": thaw_json(self.provenance),
            "allowed_variation": thaw_json(self.allowed_variation),
        }

    @classmethod
    @_strict_import
    def from_dict(cls, data):
        _schema(data, cls, {"category", "provenance", "allowed_variation"})
        return cls(data["category"], data["provenance"], data["allowed_variation"])


def _resolve(program, parameters, *, serialized=False):
    if not isinstance(program, IntentProgram):
        raise TypeMismatchError("Build authority requires an IntentProgram.")
    if not isinstance(parameters, Mapping):
        raise TypeMismatchError("Parameter bindings must be a mapping.")
    declarations = {
        node.attributes["name"]: node for node in program.find(kind="parameter")
    }
    unknown = set(parameters) - declarations.keys()
    if unknown:
        known = (
            ", ".join(f"{key} [{node.id}]" for key, node in declarations.items())
            or "none"
        )
        raise TypeMismatchError(
            f"Unknown parameter bindings: {', '.join(sorted(map(str, unknown)))}. Declared in {program.name!r}: {known}."
        )
    overrides, defaults, resolved = {}, {}, {}
    for key, node in declarations.items():
        if key in parameters:
            try:
                dtype = TypeSpec.from_dict(node.data_type)
                value = (
                    decode_binding(parameters[key], dtype).to_dict()
                    if serialized
                    else validate_binding(parameters[key], dtype)
                )
            except (TypeError, ValueError, KeyError) as exc:
                location = (
                    f" at {node.source.file}:{node.source.line}" if node.source else ""
                )
                raise TypeMismatchError(
                    f"Invalid binding for {key!r} [{node.id}]{location}: {exc}"
                ) from exc
            overrides[key] = value
        elif node.attributes["bound"]:
            value = thaw_json(node.attributes["default"])
            defaults[key] = value
        else:
            raise UnsupportedBehaviorError(
                f"Design parameter {key!r} must be bound before freezing a build request. Python control flow is design-time; use explicit operators for runtime behavior.",
                node_id=node.id,
                source=node.source,
            )
        resolved[key] = value
    return overrides, defaults, resolved


@dataclass(frozen=True)
class BuildRequest(JsonArtifact):
    """Phase-one immutable input authority, independent of emitted artifacts.

    Use freeze() with Python values. The constructor and JSON form carry already
    encoded typed bindings, whose defaults/resolution are independently checked.
    """

    intent: IntentProgram
    explicit_overrides: Mapping[str, Any]
    resolved_defaults: Mapping[str, Any]
    resolved_bindings: Mapping[str, Any]
    target: TargetContext | None = None
    artifact_scope: str = "abstract_behavior"
    implementation_constraints: Mapping[str, Any] = field(default_factory=dict)
    preferences: Mapping[str, Any] = field(default_factory=dict)
    parameter_metadata: Mapping[str, BindingMetadata] = field(default_factory=dict)
    provenance: ElaborationProvenance = field(default_factory=ElaborationProvenance)
    behavior_profile: str = BEHAVIOR_PROFILE
    schema_version: ClassVar[str] = "biocompiler.build_request.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.intent, IntentProgram),
            "BuildRequest requires a frozen IntentProgram.",
        )
        require(
            self.behavior_profile == BEHAVIOR_PROFILE,
            "Unsupported Behavior execution profile.",
        )
        require(
            self.target is None or isinstance(self.target, TargetContext),
            "BuildRequest target must be a TargetContext or null.",
        )
        require(
            isinstance(self.artifact_scope, str)
            and self.artifact_scope
            in {
                "abstract_behavior",
                "synthetic_realization",
                "exact_cds",
                "complete_payload",
            },
            "Unsupported build artifact scope.",
        )
        require(
            self.target is not None or self.artifact_scope == "abstract_behavior",
            "This artifact scope requires an explicit target context.",
        )
        require(
            isinstance(self.provenance, ElaborationProvenance),
            "Build provenance must be ElaborationProvenance.",
        )
        for key in (
            "explicit_overrides",
            "resolved_defaults",
            "resolved_bindings",
            "implementation_constraints",
            "preferences",
        ):
            object.__setattr__(self, key, _mapping(getattr(self, key), key))
        overrides, defaults, resolved = _resolve(
            self.intent, self.explicit_overrides, serialized=True
        )
        require(
            fingerprint(self.explicit_overrides) == fingerprint(overrides),
            "Noncanonical explicit binding encoding.",
        )
        require(
            fingerprint(self.resolved_defaults) == fingerprint(defaults),
            "Resolved defaults disagree with the frozen intent.",
        )
        require(
            fingerprint(self.resolved_bindings) == fingerprint(resolved),
            "Resolved bindings disagree with independent defaults and overrides.",
        )
        require(
            isinstance(self.parameter_metadata, Mapping),
            "Parameter metadata must be an object.",
        )
        require(
            not (set(self.parameter_metadata) - resolved.keys()),
            "Parameter metadata refers to an undeclared parameter.",
        )
        metadata = {}
        for node in self.intent.find(kind="parameter"):
            key = node.attributes["name"]
            item = self.parameter_metadata.get(key, BindingMetadata())
            require(
                isinstance(item, BindingMetadata), "Expected BindingMetadata records."
            )
            if item.allowed_variation is not None:
                dtype = TypeSpec.from_dict(node.data_type)
                require(
                    dtype.kind == "scalar",
                    "Allowed variation currently requires a scalar design parameter.",
                )
                from biocompiler.semantics.types import Interval

                try:
                    interval = decode_binding(item.allowed_variation, Interval[dtype])
                    value = decode_binding(resolved[key], dtype).canonical_value
                except (TypeError, ValueError, KeyError) as exc:
                    raise SerializationError(
                        f"Invalid allowed variation for {key!r}: {exc}"
                    ) from exc
                require(
                    interval.lower.canonical_value
                    <= value
                    <= interval.upper.canonical_value,
                    f"Frozen value of {key!r} is outside its allowed variation.",
                )
            metadata[key] = item
        from types import MappingProxyType

        object.__setattr__(self, "parameter_metadata", MappingProxyType(metadata))

    @classmethod
    def freeze(
        cls,
        program,
        *,
        target=None,
        parameters=None,
        artifact_scope="abstract_behavior",
        implementation_constraints=None,
        preferences=None,
        parameter_metadata=None,
        provenance=None,
        behavior_profile=BEHAVIOR_PROFILE,
    ):
        overrides, defaults, resolved = _resolve(
            program, {} if parameters is None else parameters
        )
        return cls(
            program,
            overrides,
            defaults,
            resolved,
            target,
            artifact_scope,
            {} if implementation_constraints is None else implementation_constraints,
            {} if preferences is None else preferences,
            {} if parameter_metadata is None else parameter_metadata,
            ElaborationProvenance() if provenance is None else provenance,
            behavior_profile,
        )

    @property
    def program(self):
        """Compatibility spelling shared with RealizationPlan."""
        return self.intent

    @property
    def runtime_observations(self):
        return tuple(node.id for node in self.intent.find(kind="signal"))

    def to_dict(self, *, include_provenance=True):
        return {
            "schema_version": self.schema_version,
            "intent": self.intent.to_dict(include_source=include_provenance),
            "explicit_overrides": thaw_json(self.explicit_overrides),
            "resolved_defaults": thaw_json(self.resolved_defaults),
            "resolved_bindings": thaw_json(self.resolved_bindings),
            "target": self.target.to_dict() if self.target else None,
            "artifact_scope": self.artifact_scope,
            "behavior_profile": self.behavior_profile,
            "implementation_constraints": thaw_json(self.implementation_constraints),
            "preferences": thaw_json(self.preferences),
            "parameter_metadata": {
                key: value.to_dict() for key, value in self.parameter_metadata.items()
            },
            "provenance": self.provenance.to_dict(include_locations=include_provenance),
        }

    @property
    def fingerprint(self):
        return fingerprint(self.to_dict(include_provenance=False))

    @property
    def artifact_fingerprint(self):
        """Exact archival identity, including source locations and timestamps."""
        return fingerprint(self.to_dict())

    @classmethod
    @_strict_import
    def from_dict(cls, data):
        _schema(
            data,
            cls,
            {
                "intent",
                "explicit_overrides",
                "resolved_defaults",
                "resolved_bindings",
                "target",
                "artifact_scope",
                "behavior_profile",
                "implementation_constraints",
                "preferences",
                "parameter_metadata",
                "provenance",
            },
        )
        require(
            isinstance(data["parameter_metadata"], Mapping),
            "Parameter metadata must be an object.",
        )
        require(
            isinstance(data["resolved_bindings"], Mapping)
            and set(data["parameter_metadata"]) == set(data["resolved_bindings"]),
            "Serialized metadata must cover every design parameter.",
        )
        return cls(
            IntentProgram.from_dict(data["intent"]),
            data["explicit_overrides"],
            data["resolved_defaults"],
            data["resolved_bindings"],
            TargetContext.from_dict(data["target"])
            if data["target"] is not None
            else None,
            data["artifact_scope"],
            data["implementation_constraints"],
            data["preferences"],
            {
                key: BindingMetadata.from_dict(value)
                for key, value in data["parameter_metadata"].items()
            },
            ElaborationProvenance.from_dict(data["provenance"]),
            data["behavior_profile"],
        )


@dataclass(frozen=True)
class RealizationRequest(JsonArtifact):
    """Phase two binds an already verified Behavior to declared model obligations.

    Freezing this request establishes input identity, not realization acceptance.
    The independent checker must still establish contract/domain consistency and
    finite-history outcomes for a proposed candidate.
    """

    build_request: BuildRequest
    behavior: BehaviorProgram
    contract: BehaviorContract
    domain: OperatingDomain
    schema_version: ClassVar[str] = "biocompiler.realization_request.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.build_request, BuildRequest),
            "Expected BuildRequest authority.",
        )
        require(isinstance(self.behavior, BehaviorProgram), "Expected BehaviorProgram.")
        require(
            isinstance(self.contract, BehaviorContract), "Expected BehaviorContract."
        )
        require(isinstance(self.domain, OperatingDomain), "Expected OperatingDomain.")
        require(
            self.build_request.target is not None,
            "Realization requests require an explicit target context.",
        )
        from biocompiler.compiler.behavior import verify_lowering

        verify_lowering(self.build_request, self.behavior)
        require(
            self.contract.behavior_fingerprint == self.behavior.fingerprint,
            "Contract must refer to this exact verified Behavior fingerprint.",
        )
        require(
            self.contract.role == self.domain.role,
            "Contract and operating domain must bind the same role.",
        )
        roles = {node.id for node in self.behavior.find(kind="role")}
        require(
            self.domain.role in roles,
            "Operating domain must bind an existing Behavior role.",
        )

    @classmethod
    def freeze(cls, build_request, behavior, contract, domain):
        return cls(build_request, behavior, contract, domain)

    @property
    def target(self):
        return self.build_request.target

    @property
    def upstream_request_fingerprint(self):
        return self.build_request.fingerprint

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "build_request": self.build_request.to_dict(),
            "behavior": self.behavior.to_dict(),
            "contract": self.contract.to_dict(),
            "domain": self.domain.to_dict(),
        }

    @property
    def fingerprint(self):
        return fingerprint(
            {
                "schema_version": self.schema_version,
                "build_request": self.build_request.fingerprint,
                "behavior": self.behavior.fingerprint,
                "contract": self.contract.fingerprint,
                "domain": self.domain.fingerprint,
            }
        )

    @property
    def artifact_fingerprint(self):
        return fingerprint(self.to_dict())

    @classmethod
    @_strict_import
    def from_dict(cls, data):
        _schema(data, cls, {"build_request", "behavior", "contract", "domain"})
        return cls(
            BuildRequest.from_dict(data["build_request"]),
            BehaviorProgram.from_dict(data["behavior"]),
            BehaviorContract.from_dict(data["contract"]),
            OperatingDomain.from_dict(data["domain"]),
        )
