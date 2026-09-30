"""Deterministic offline component selection and exact dependency locks.

Selection first proves the supported hard constraints. Preferences order only
eligible alternatives; unknown applicability is never treated as eligibility.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from biocompiler.ir.component_contracts import ComponentRecord, PinnedIdentity
from biocompiler.ir.components import ComponentLock
from biocompiler.ir.serialization import JsonArtifact, fields, name, names, require
from biocompiler.semantics.context import TargetContext
from biocompiler.semantics.component_contracts import (
    OperatingDomain,
    operating_domain_subset,
)

REGISTRY_POLICY_VERSION = "biocompiler.component_registry.v0.1"


def _hash(value, label):
    require(
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value),
        f"{label} must be a SHA-256 identity.",
    )


def _identities(values):
    require(
        isinstance(values, (tuple, list))
        and all(isinstance(item, PinnedIdentity) for item in values),
        "Expected pinned identities.",
    )
    result = {}
    for item in values:
        key = (item.kind, item.id, item.version)
        require(
            key not in result or result[key] == item,
            "Ambiguous dependency identity: one kind/ID/version has different hashes.",
        )
        result[key] = item
    return tuple(result[key] for key in sorted(result))


def _read(data, cls):
    fields(
        data,
        set(cls.__dataclass_fields__) - {"schema_version"} | {"schema_version"},
        cls.__name__,
    )
    require(
        data["schema_version"] == cls.schema_version, "Unsupported registry schema."
    )
    return {key: value for key, value in data.items() if key != "schema_version"}


def _decode_array(values, cls):
    require(isinstance(values, (tuple, list)), "Registry records must be an array.")
    return tuple(cls.from_dict(item) for item in values)


@dataclass(frozen=True)
class RegistryLock(JsonArtifact):
    registry_id: str
    registry_version: str
    registry_fingerprint: str
    components: tuple[ComponentLock, ...]
    identities: tuple[PinnedIdentity, ...]
    schema_version: ClassVar[str] = "biocompiler.component_registry_lock.v0.1"

    def __post_init__(self):
        name(self.registry_id, "Registry ID")
        name(self.registry_version, "Registry version")
        _hash(self.registry_fingerprint, "Registry fingerprint")
        require(
            isinstance(self.components, (tuple, list))
            and all(isinstance(item, ComponentLock) for item in self.components),
            "Registry locks require component locks.",
        )
        components = tuple(sorted(self.components, key=lambda item: item.node_id))
        require(
            len({item.node_id for item in components}) == len(components),
            "Registry lock instance IDs must be unique.",
        )
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "identities", _identities(self.identities))

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "registry_id": self.registry_id,
            "registry_version": self.registry_version,
            "registry_fingerprint": self.registry_fingerprint,
            "components": [item.to_dict() for item in self.components],
            "identities": [item.to_dict() for item in self.identities],
        }

    @classmethod
    def from_dict(cls, data):
        values = _read(data, cls)
        values["components"] = _decode_array(values["components"], ComponentLock)
        values["identities"] = _decode_array(values["identities"], PinnedIdentity)
        return cls(**values)


@dataclass(frozen=True)
class SelectionRequest(JsonArtifact):
    implementation_role: str
    target: TargetContext
    required_domain: OperatingDomain
    instance_id: str = "selected"
    classification: str | None = None
    required_guarantees: tuple[str, ...] = ()
    component_id: str | None = None
    component_version: str | None = None
    required_identities: tuple[PinnedIdentity, ...] = ()
    preferred_component_ids: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.component_selection_request.v0.1"

    def __post_init__(self):
        for key in ("implementation_role", "instance_id"):
            name(getattr(self, key), key)
        require(
            isinstance(self.target, TargetContext),
            "Selection requires a full target context.",
        )
        for key in ("classification", "component_id", "component_version"):
            if getattr(self, key) is not None:
                name(getattr(self, key), key)
        require(
            isinstance(self.required_domain, OperatingDomain),
            "Selection requires an operating domain.",
        )
        require(
            self.component_version is None or self.component_id is not None,
            "A hard version pin requires a component ID.",
        )
        for key in ("required_guarantees", "preferred_component_ids"):
            object.__setattr__(self, key, names(getattr(self, key), key))
        object.__setattr__(
            self, "required_identities", _identities(self.required_identities)
        )

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "implementation_role": self.implementation_role,
            "target": self.target.to_dict(),
            "required_domain": self.required_domain.to_dict(),
            "instance_id": self.instance_id,
            "classification": self.classification,
            "required_guarantees": list(self.required_guarantees),
            "component_id": self.component_id,
            "component_version": self.component_version,
            "required_identities": [
                item.to_dict() for item in self.required_identities
            ],
            "preferred_component_ids": list(self.preferred_component_ids),
        }

    @classmethod
    def from_dict(cls, data):
        values = _read(data, cls)
        values["target"] = TargetContext.from_dict(values["target"])
        values["required_domain"] = OperatingDomain.from_dict(values["required_domain"])
        values["required_identities"] = _decode_array(
            values["required_identities"], PinnedIdentity
        )
        return cls(**values)


@dataclass(frozen=True)
class SelectionAlternative(JsonArtifact):
    component_id: str
    version: str
    content_fingerprint: str
    status: str
    reasons: tuple[str, ...]
    preference_rank: int | None = None
    schema_version: ClassVar[str] = "biocompiler.component_selection_alternative.v0.1"

    def __post_init__(self):
        name(self.component_id, "Component ID")
        name(self.version, "Component version")
        _hash(self.content_fingerprint, "Component fingerprint")
        require(
            isinstance(self.status, str)
            and self.status in {"eligible", "rejected", "unknown"},
            "Invalid alternative status.",
        )
        object.__setattr__(self, "reasons", names(self.reasons, "Selection reasons"))
        require(bool(self.reasons), "Selection alternatives require rationale.")
        require(
            (
                self.status == "eligible"
                and type(self.preference_rank) is int
                and self.preference_rank >= 0
            )
            or (self.status != "eligible" and self.preference_rank is None),
            "Preferences can rank only eligible alternatives.",
        )

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "component_id": self.component_id,
            "version": self.version,
            "content_fingerprint": self.content_fingerprint,
            "status": self.status,
            "reasons": list(self.reasons),
            "preference_rank": self.preference_rank,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**_read(data, cls))


@dataclass(frozen=True)
class SelectionResult(JsonArtifact):
    registry_fingerprint: str
    request_fingerprint: str
    selected: ComponentLock | None
    alternatives: tuple[SelectionAlternative, ...]
    schema_version: ClassVar[str] = "biocompiler.component_selection_result.v0.1"

    def __post_init__(self):
        _hash(self.registry_fingerprint, "Registry fingerprint")
        _hash(self.request_fingerprint, "Selection request fingerprint")
        require(
            self.selected is None or isinstance(self.selected, ComponentLock),
            "Invalid selected component lock.",
        )
        require(
            isinstance(self.alternatives, (tuple, list))
            and all(
                isinstance(item, SelectionAlternative) for item in self.alternatives
            ),
            "Expected selection alternatives.",
        )
        alternatives = tuple(
            sorted(
                self.alternatives,
                key=lambda item: (
                    item.component_id,
                    item.version,
                    item.content_fingerprint,
                ),
            )
        )
        require(
            len({(item.component_id, item.version) for item in alternatives})
            == len(alternatives),
            "Duplicate selection alternatives.",
        )
        eligible = [item for item in alternatives if item.status == "eligible"]
        winner = (
            min(
                eligible,
                key=lambda item: (
                    item.preference_rank,
                    item.component_id,
                    item.version,
                    item.content_fingerprint,
                ),
            )
            if eligible
            else None
        )
        require(
            self.selected is None
            if winner is None
            else self.selected is not None
            and (
                self.selected.component_id,
                self.selected.version,
                self.selected.content_fingerprint,
            )
            == (winner.component_id, winner.version, winner.content_fingerprint),
            "Selection must choose the deterministically ranked eligible alternative.",
        )
        object.__setattr__(self, "alternatives", alternatives)

    @property
    def outcome(self):
        return (
            "pass"
            if self.selected is not None
            else "unknown"
            if any(item.status == "unknown" for item in self.alternatives)
            else "fail"
        )

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "registry_fingerprint": self.registry_fingerprint,
            "request_fingerprint": self.request_fingerprint,
            "selected": self.selected.to_dict() if self.selected else None,
            "alternatives": [item.to_dict() for item in self.alternatives],
        }

    @classmethod
    def from_dict(cls, data):
        values = _read(data, cls)
        values["selected"] = (
            ComponentLock.from_dict(values["selected"])
            if values["selected"] is not None
            else None
        )
        values["alternatives"] = _decode_array(
            values["alternatives"], SelectionAlternative
        )
        return cls(**values)


@dataclass(frozen=True)
class ComponentRegistry(JsonArtifact):
    id: str
    version: str
    components: tuple[ComponentRecord, ...]
    schema_version: ClassVar[str] = REGISTRY_POLICY_VERSION

    def __post_init__(self):
        name(self.id, "Registry ID")
        name(self.version, "Registry version")
        require(
            isinstance(self.components, (tuple, list))
            and all(isinstance(item, ComponentRecord) for item in self.components),
            "Expected component records.",
        )
        components = tuple(
            sorted(
                self.components,
                key=lambda item: (item.id, item.version, item.fingerprint),
            )
        )
        require(
            len({(item.id, item.version) for item in components}) == len(components),
            "Duplicate or ambiguous component ID/version in registry.",
        )
        _identities(
            tuple(
                identity
                for item in components
                for identity in (
                    *item.identities,
                    *item.evidence,
                    *(parameter.source for parameter in item.parameters),
                )
            )
        )
        object.__setattr__(self, "components", components)

    def lock(self, instances: Mapping[str, ComponentRecord]) -> RegistryLock:
        require(
            isinstance(instances, Mapping), "Instance selections must be a mapping."
        )
        known = {
            (item.id, item.version, item.fingerprint): item for item in self.components
        }
        components = []
        identities = []
        for instance_id, component in instances.items():
            name(instance_id, "Instance ID")
            require(
                isinstance(component, ComponentRecord),
                "Expected a selected component record.",
            )
            require(
                (component.id, component.version, component.fingerprint) in known,
                "Selected component is absent or stale in this registry.",
            )
            components.append(
                ComponentLock(
                    instance_id, component.id, component.version, component.fingerprint
                )
            )
            identities.extend(
                (
                    *component.identities,
                    *component.evidence,
                    *(parameter.source for parameter in component.parameters),
                )
            )
        return RegistryLock(
            self.id,
            self.version,
            self.fingerprint,
            tuple(components),
            _identities(tuple(identities)),
        )

    def resolve(self, lock: RegistryLock) -> dict[str, ComponentRecord]:
        require(isinstance(lock, RegistryLock), "An exact registry lock is required.")
        require(
            (lock.registry_id, lock.registry_version, lock.registry_fingerprint)
            == (self.id, self.version, self.fingerprint),
            "Registry identity/version/content lock mismatch.",
        )
        known = {
            (item.id, item.version, item.fingerprint): item for item in self.components
        }
        resolved = {}
        for selection in lock.components:
            key = (
                selection.component_id,
                selection.version,
                selection.content_fingerprint,
            )
            require(
                key in known,
                "Selected component identity/version/content lock mismatch.",
            )
            resolved[selection.node_id] = known[key]
        require(
            self.lock(resolved) == lock,
            "Model/reference/evidence dependency lock mismatch.",
        )
        return resolved

    def select(self, request: SelectionRequest) -> SelectionResult:
        require(
            isinstance(request, SelectionRequest),
            "A frozen selection request is required.",
        )
        alternatives = []
        for component in self.components:
            reasons = []
            if component.implementation_role != request.implementation_role:
                reasons.append("implementation_role_mismatch")
            if request.target.payload_format.value not in component.supported_targets:
                reasons.append("unsupported_target")
            if {port.compartment for port in component.ports} - set(
                request.target.compartments
            ):
                reasons.append("unsupported_compartment")
            if (
                request.classification is not None
                and request.classification != component.classification
            ):
                reasons.append("classification_mismatch")
            if (
                request.component_id is not None
                and request.component_id != component.id
            ):
                reasons.append("component_id_mismatch")
            if (
                request.component_version is not None
                and request.component_version != component.version
            ):
                reasons.append("component_version_mismatch")
            if set(request.required_guarantees) - set(component.guarantees):
                reasons.append("missing_required_guarantee")
            available = set(
                (
                    *component.identities,
                    *component.evidence,
                    *(parameter.source for parameter in component.parameters),
                )
            )
            if set(request.required_identities) - available:
                reasons.append("required_dependency_identity_mismatch")
            domain = operating_domain_subset(
                request.required_domain, component.supported_domain
            )
            if domain.status == "fail":
                reasons.extend(f"domain:{reason}" for reason in domain.reasons)
            status = (
                "rejected"
                if reasons
                else "unknown"
                if domain.status == "unknown"
                else "eligible"
            )
            rank = None
            if status == "eligible":
                rank = (
                    request.preferred_component_ids.index(component.id)
                    if component.id in request.preferred_component_ids
                    else len(request.preferred_component_ids)
                )
                reasons = [
                    "all_hard_constraints_satisfied",
                    "preference_rank_applied_after_hard_constraints",
                ]
            elif status == "unknown":
                reasons = [f"domain:{reason}" for reason in domain.reasons]
            alternatives.append(
                SelectionAlternative(
                    component.id,
                    component.version,
                    component.fingerprint,
                    status,
                    tuple(reasons),
                    rank,
                )
            )
        eligible = [item for item in alternatives if item.status == "eligible"]
        winner = (
            min(
                eligible,
                key=lambda item: (
                    item.preference_rank,
                    item.component_id,
                    item.version,
                    item.content_fingerprint,
                ),
            )
            if eligible
            else None
        )
        selected = (
            ComponentLock(
                request.instance_id,
                winner.component_id,
                winner.version,
                winner.content_fingerprint,
            )
            if winner
            else None
        )
        return SelectionResult(
            self.fingerprint, request.fingerprint, selected, tuple(alternatives)
        )

    def verify_selection(
        self, request: SelectionRequest, result: SelectionResult
    ) -> bool:
        """Recompute constraints/ranking from authoritative request and registry."""
        return isinstance(result, SelectionResult) and result == self.select(request)

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "id": self.id,
            "version": self.version,
            "components": [item.to_dict() for item in self.components],
        }

    @classmethod
    def from_dict(cls, data):
        values = _read(data, cls)
        values["components"] = _decode_array(values["components"], ComponentRecord)
        return cls(**values)
