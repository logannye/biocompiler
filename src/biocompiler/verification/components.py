"""Independent, conservative acceptance of locked offline compositions.

The checker reads component requirements from the locked registry, never from a
producer's report. Passing is conditional on declared contracts and providers.
It does not validate biological function or discharge an empirical assumption.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
import math
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.composition import CompositionRequest, _Record, _array
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.serialization import JsonArtifact, fields, name, names, require
from biocompiler.registry.components import ComponentRegistry
from biocompiler.semantics.component_contracts import (
    operating_domain_subset,
    ports_compatible,
)
from biocompiler.semantics.admission import ADMISSION_POLICY_VERSION
from biocompiler.verification.admission import admission_for_target
from biocompiler.verification.evidence import CheckOutcome, FreshnessReport

CHECKER_VERSION = "biocompiler.component_linker.v0.3"
CLAIM_SCOPE = (
    "Structural component compatibility under the locked records and declared "
    "target, provider, lifecycle, model and resource assumptions only. This is "
    "not biological efficacy, sequence emission, or empirical validation."
)


@dataclass(frozen=True)
class LinkDiagnostic(_Record):
    status: str
    code: str
    message: str
    instance_id: str | None = None
    requirement_ids: tuple[str, ...] = ()

    def __post_init__(self):
        require(
            isinstance(self.status, str)
            and self.status in {"fail", "unknown", "unsupported"},
            "Invalid link diagnostic status.",
        )
        for key in ("code", "message"):
            name(getattr(self, key), key)
        if self.instance_id is not None:
            name(self.instance_id, "Diagnostic instance")
        object.__setattr__(
            self,
            "requirement_ids",
            names(self.requirement_ids, "Diagnostic requirements"),
        )

    @classmethod
    def from_dict(cls, data):
        cls._fields(data)
        return cls(**data)


@dataclass(frozen=True)
class ResolvedDependency(_Record):
    instance_id: str
    requirement_id: str
    provider_id: str | None
    provider_kind: str
    status: str

    def __post_init__(self):
        name(self.instance_id, "Dependency instance")
        name(self.requirement_id, "Dependency requirement")
        if self.provider_id is not None:
            name(self.provider_id, "Dependency provider")
        require(
            isinstance(self.provider_kind, str)
            and self.provider_kind
            in {"encoded_here", "co_payload", "host", "external", "unresolved"},
            "Invalid provider category.",
        )
        require(
            isinstance(self.status, str)
            and self.status in {"pass", "fail", "unknown", "unsupported"},
            "Invalid dependency status.",
        )

    @classmethod
    def from_dict(cls, data):
        cls._fields(data)
        return cls(**data)


@dataclass(frozen=True)
class ResourceUsage(_Record):
    pool_id: str
    peak_reservation: float | int | None
    capacity: float | int | None
    unit: str
    status: str

    def __post_init__(self):
        name(self.pool_id, "Resource usage pool")
        name(self.unit, "Resource usage unit")
        from biocompiler.ir.composition import _quantity

        _quantity(self.peak_reservation, "Peak reservation", optional=True)
        _quantity(self.capacity, "Capacity", optional=True)
        require(
            isinstance(self.status, str)
            and self.status in {"pass", "fail", "unknown", "unsupported"},
            "Invalid resource status.",
        )

    @classmethod
    def from_dict(cls, data):
        cls._fields(data)
        return cls(**data)


def composition_dependencies(request: CompositionRequest, registry: ComponentRegistry):
    return {
        "request": request.fingerprint,
        "registry": registry.fingerprint,
        "registry_lock": request.registry_lock.fingerprint,
        "target": request.target.fingerprint,
        "checker": CHECKER_VERSION,
        "admission_policy": ADMISSION_POLICY_VERSION,
        "identities": [item.to_dict() for item in request.registry_lock.identities],
    }


@dataclass(frozen=True)
class CompositionResult(JsonArtifact):
    outcome: CheckOutcome
    dependencies: Mapping
    checked_requirement_ids: tuple[str, ...]
    diagnostics: tuple[LinkDiagnostic, ...] = ()
    resolved_dependencies: tuple[ResolvedDependency, ...] = ()
    resource_usage: tuple[ResourceUsage, ...] = ()
    claim_scope: str = CLAIM_SCOPE
    schema_version: ClassVar[str] = "biocompiler.component_link_result.v0.3"

    def __post_init__(self):
        require(isinstance(self.outcome, CheckOutcome), "Invalid composition outcome.")
        fields(
            self.dependencies,
            {
                "request",
                "registry",
                "registry_lock",
                "target",
                "checker",
                "identities",
                "admission_policy",
            },
            "Composition dependencies",
        )
        for key in ("request", "registry", "registry_lock", "target"):
            value = self.dependencies[key]
            require(
                isinstance(value, str)
                and len(value) == 64
                and all(c in "0123456789abcdef" for c in value),
                "Invalid composition dependency hash.",
            )
        require(
            self.dependencies["checker"] == CHECKER_VERSION
            and self.dependencies["admission_policy"] == ADMISSION_POLICY_VERSION,
            "Unsupported checker version.",
        )
        identities = self.dependencies["identities"]
        require(
            isinstance(identities, (list, tuple)),
            "Dependency identities must be an array.",
        )
        identities = tuple(PinnedIdentity.from_dict(item) for item in identities)
        require(
            len({(item.kind, item.id, item.version) for item in identities})
            == len(identities),
            "Duplicate dependency identities.",
        )
        object.__setattr__(self, "dependencies", freeze_json(self.dependencies))
        object.__setattr__(
            self,
            "checked_requirement_ids",
            names(self.checked_requirement_ids, "Checked requirements"),
        )
        for key, typ in (
            ("diagnostics", LinkDiagnostic),
            ("resolved_dependencies", ResolvedDependency),
            ("resource_usage", ResourceUsage),
        ):
            object.__setattr__(self, key, _array(getattr(self, key), typ, key))
        require(self.claim_scope == CLAIM_SCOPE, "Invalid composition claim scope.")
        require(
            self.outcome is not CheckOutcome.PASS or not self.diagnostics,
            "Passing compositions cannot contain unresolved diagnostics.",
        )
        require(
            self.outcome is not CheckOutcome.PASS
            or all(item.status == "pass" for item in self.resource_usage),
            "Passing compositions cannot contain unresolved resource accounting.",
        )

    @property
    def passed(self):
        return self.outcome is CheckOutcome.PASS

    def freshness(self, request: CompositionRequest, registry: ComponentRegistry):
        current = freeze_json(composition_dependencies(request, registry))
        return FreshnessReport(
            tuple(
                sorted(key for key in current if current[key] != self.dependencies[key])
            )
        )

    def is_fresh(self, request: CompositionRequest, registry: ComponentRegistry):
        return self.freshness(request, registry).fresh

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "outcome": self.outcome.value,
            "dependencies": thaw_json(self.dependencies),
            "checked_requirement_ids": list(self.checked_requirement_ids),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "resolved_dependencies": [
                item.to_dict() for item in self.resolved_dependencies
            ],
            "resource_usage": [item.to_dict() for item in self.resource_usage],
            "claim_scope": self.claim_scope,
        }

    @classmethod
    def from_dict(cls, data):
        fields(
            data,
            {
                "schema_version",
                "outcome",
                "dependencies",
                "checked_requirement_ids",
                "diagnostics",
                "resolved_dependencies",
                "resource_usage",
                "claim_scope",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported link result schema.",
        )
        try:
            outcome = CheckOutcome(data["outcome"])
        except (TypeError, ValueError) as exc:
            raise SerializationError("Invalid link outcome.") from exc
        for key in ("diagnostics", "resolved_dependencies", "resource_usage"):
            require(isinstance(data[key], (tuple, list)), f"{key} must be an array.")
        return cls(
            outcome,
            data["dependencies"],
            data["checked_requirement_ids"],
            tuple(LinkDiagnostic.from_dict(item) for item in data["diagnostics"]),
            tuple(
                ResolvedDependency.from_dict(item)
                for item in data["resolved_dependencies"]
            ),
            tuple(ResourceUsage.from_dict(item) for item in data["resource_usage"]),
            data["claim_scope"],
        )


def check_composition(
    request: CompositionRequest, registry: ComponentRegistry
) -> CompositionResult:
    """Recompute acceptance using the authoritative frozen request and registry.

    No accepted producer report, capability assertion for a selected component,
    or caller-edited reservation list enters this interface.
    """
    require(
        isinstance(request, CompositionRequest)
        and isinstance(registry, ComponentRegistry),
        "Invalid component check inputs.",
    )
    diagnostics = []
    instances = {item.id: item for item in request.instances}
    resolved = []
    usage = []
    covered_requirements = tuple(
        sorted({ref for item in request.instances for ref in item.requirement_ids})
    )

    def diagnostic(status, code, message, instance_id=None):
        instance = instances.get(instance_id)
        diagnostics.append(
            LinkDiagnostic(
                status,
                code,
                message,
                instance_id,
                instance.requirement_ids if instance else request.requirement_ids,
            )
        )

    def finish():
        statuses = {item.status for item in diagnostics}
        outcome = next(
            (
                CheckOutcome(value)
                for value in ("fail", "unsupported", "unknown")
                if value in statuses
            ),
            CheckOutcome.PASS,
        )
        return CompositionResult(
            outcome,
            composition_dependencies(request, registry),
            covered_requirements,
            tuple(diagnostics),
            tuple(resolved),
            tuple(usage),
        )

    if set(covered_requirements) != set(request.requirement_ids):
        diagnostic(
            "unknown",
            "uncovered_requirement",
            "Every requested requirement must correspond to at least one selected instance.",
        )

    try:
        records = registry.resolve(request.registry_lock)
    except SerializationError as exc:
        diagnostic("fail", "stale_registry_lock", str(exc))
        return finish()
    locks = {item.node_id: item for item in request.registry_lock.components}
    if set(records) != set(instances) or any(
        locks.get(item.id) != item.component for item in request.instances
    ):
        diagnostic(
            "fail",
            "instance_lock_mismatch",
            "Instances must exactly match the locked selections.",
        )
        return finish()

    admission = admission_for_target(
        request.target, boundary="verification", components=tuple(records.values())
    )
    if admission.decision != "software_only":
        diagnostic(
            "unsupported",
            "human_profile_not_admitted",
            "; ".join(admission.diagnostics),
        )

    target = request.target.payload_format.value
    invalid_providers = set()
    for instance_id, record in records.items():
        if record.synthetic_model is not None and any(
            check.status == "unknown" for check in record.synthetic_model.domain_checks(
                record.ports, record.supported_domain
            )
        ):
            diagnostic("unknown", "unknown_executable_domain",
                       "Executable output guarantees cannot be established from unknown domains.",
                       instance_id)
        if any(port.timing.startswith("atomic_discrete_event_") for port in record.ports) and record.synthetic_model is None:
            diagnostic(
                "unknown", "missing_transition_model",
                "Discrete-event interfaces require an explicit executable transition model.",
                instance_id,
            )
        if target not in record.supported_targets:
            diagnostic(
                "fail",
                "unsupported_target",
                "Selected component does not support this payload target.",
                instance_id,
            )
            invalid_providers.add(instance_id)
        domain = operating_domain_subset(
            instances[instance_id].required_domain, record.supported_domain
        )
        if not domain.passed:
            diagnostic(
                domain.status, "operating_domain", " ".join(domain.reasons), instance_id
            )
            invalid_providers.add(instance_id)
        if any(
            item.compartment not in request.target.compartments
            for item in (
                *record.ports,
                *record.capabilities,
                *record.dependencies,
                *record.resources,
            )
        ):
            diagnostic(
                "fail",
                "target_compartment",
                "A selected interface or dependency uses a compartment absent from the target.",
                instance_id,
            )
            invalid_providers.add(instance_id)

    ports = {
        (key, port.id): port for key, record in records.items() for port in record.ports
    }
    connected = defaultdict(int)
    for connection in request.connections:
        producer = ports.get((connection.producer_instance, connection.producer_port))
        consumer_key = (connection.consumer_instance, connection.consumer_port)
        consumer = ports.get(consumer_key)
        connected[consumer_key] += 1
        if producer is None or consumer is None:
            diagnostic(
                "fail",
                "missing_port",
                "A connection references an unknown instance or port.",
                connection.consumer_instance,
            )
            continue
        checked = ports_compatible(producer, consumer)
        if not checked.passed:
            diagnostic(
                checked.status,
                "incompatible_ports",
                " ".join(checked.reasons),
                connection.consumer_instance,
            )
    for (instance_id, port_id), port in ports.items():
        if port.direction == "input" and connected[(instance_id, port_id)] != 1:
            diagnostic(
                "fail" if connected[(instance_id, port_id)] > 1 else "unknown",
                "input_connection_count",
                "Every input port requires exactly one producer.",
                instance_id,
            )
    upstream = {key: set() for key in instances}
    for connection in request.connections:
        if (
            connection.producer_instance in instances
            and connection.consumer_instance in instances
        ):
            upstream[connection.consumer_instance].add(connection.producer_instance)
    ordered = set()
    while True:
        ready = {
            key
            for key, dependencies in upstream.items()
            if key not in ordered and dependencies <= ordered
        }
        if not ready:
            break
        ordered.update(ready)
    if len(ordered) != len(instances):
        diagnostic(
            "unsupported",
            "cyclic_port_connections",
            "The stateless interface profile cannot establish a solution for cyclic wiring.",
        )

    # Payload capabilities always come from exact selected records. Textual
    # assumptions and similarly named guarantees are never providers.
    provider_caps = {key: record.capabilities for key, record in records.items()}
    provider_kinds = {key: instances[key].placement for key in records}
    prerequisites = {key: set() for key in records}
    for provider in request.providers:
        provider_caps[provider.id] = provider.capabilities
        provider_kinds[provider.id] = provider.kind
        prerequisites[provider.id] = set(provider.depends_on)
        if provider.kind == "unresolved":
            invalid_providers.add(provider.id)
        if target not in provider.supported_targets:
            invalid_providers.add(provider.id)
            diagnostic(
                "fail",
                "provider_target",
                f"Provider {provider.id!r} does not support the target.",
            )
        if any(
            cap.compartment not in request.target.compartments
            for cap in provider.capabilities
        ):
            invalid_providers.add(provider.id)
            diagnostic(
                "fail",
                "provider_compartment",
                f"Provider {provider.id!r} uses an undeclared compartment.",
            )
        if provider.kind == "host" and not {
            cap.id for cap in provider.capabilities
        } <= set(request.target.capabilities):
            invalid_providers.add(provider.id)
            diagnostic(
                "fail",
                "host_capability",
                f"Provider {provider.id!r} claims a capability absent from the target.",
            )

    bindings = defaultdict(list)
    for item in request.dependency_bindings:
        bindings[(item.instance_id, item.requirement_id)].append(item.provider_id)
    requirements = {
        (key, req.id): req
        for key, record in records.items()
        for req in record.dependencies
    }
    for key in bindings.keys() - requirements.keys():
        diagnostic(
            "fail",
            "unknown_dependency_binding",
            f"Binding names undeclared dependency {key[1]!r}.",
            key[0],
        )
    selected_providers = {}
    for (instance_id, requirement_id), requirement in requirements.items():

        def compatible(cap):
            return (
                cap.id == requirement.capability
                and cap.role == requirement.role
                and cap.scope == requirement.scope
                and cap.compartment == requirement.compartment
            )

        candidates = sorted(
            key
            for key, caps in provider_caps.items()
            if any(compatible(cap) for cap in caps)
        )
        explicit = bindings[(instance_id, requirement_id)]
        chosen = None
        status = "unknown"
        if len(explicit) > 1:
            status = "fail"
            diagnostic(
                "fail",
                "duplicate_dependency_binding",
                "A dependency has multiple explicit bindings.",
                instance_id,
            )
        elif explicit:
            if explicit[0] in candidates:
                chosen = explicit[0]
            else:
                status = "fail"
                diagnostic(
                    "fail",
                    "incompatible_provider",
                    "The bound provider is absent or differs in capability meaning, role, scope or compartment.",
                    instance_id,
                )
        elif len(candidates) == 1:
            chosen = candidates[0]
        elif requirement.required:
            diagnostic(
                "unknown",
                "ambiguous_provider" if candidates else "missing_provider",
                "A required dependency needs exactly one compatible provider or an explicit binding.",
                instance_id,
            )
        if chosen is not None:
            selected_providers[(instance_id, requirement_id)] = chosen
            if requirement.required:
                prerequisites[instance_id].add(chosen)
        elif requirement.required:
            invalid_providers.add(instance_id)
        resolved.append(
            ResolvedDependency(
                instance_id,
                requirement_id,
                chosen,
                provider_kinds[chosen] if chosen is not None else "unresolved",
                status,
            )
        )

    # Resource supply is also an implementation prerequisite. A component that
    # needs a pool to exist cannot establish that same pool merely by naming its
    # own resource-producing capability (including cycles through other parts).
    pools = {pool.id: pool for pool in request.resource_pools}
    resource_bindings = defaultdict(list)
    for binding in request.resource_bindings:
        resource_bindings[(binding.instance_id, binding.reservation_id)].append(
            binding.pool_id
        )
    reservations = {
        (key, reservation.id): reservation
        for key, record in records.items()
        for reservation in record.resources
    }
    for (instance_id, reservation_id), reservation in reservations.items():
        bound = resource_bindings[(instance_id, reservation_id)]
        if len(bound) == 1 and bound[0] in pools:
            pool = pools[bound[0]]
            prerequisites[instance_id].add(pool.provider_id)
            if reservation.amount is None or pool.capacity is None:
                invalid_providers.add(instance_id)
        else:
            invalid_providers.add(instance_id)

    def provider_lifetime(provider_id, instance_id, *, consumed=False):
        if provider_id not in instances:
            return
        provider = instances[provider_id].lifetime
        consumer = instances[instance_id].lifetime
        if provider.unit != "s" or consumer.unit != "s":
            diagnostic(
                "unsupported",
                "provider_lifecycle",
                "Provider availability requires lifecycle intervals in seconds.",
                instance_id,
            )
            invalid_providers.add(instance_id)
        elif (
            provider.start > consumer.start
            or provider.end is not None
            and (
                provider.end <= consumer.start
                if consumed
                else consumer.end is None or provider.end < consumer.end
            )
        ):
            diagnostic(
                "fail",
                "provider_lifecycle",
                "The provider does not cover the required consumer lifetime.",
                instance_id,
            )
            invalid_providers.add(instance_id)

    for (instance_id, _), provider_id in selected_providers.items():
        provider_lifetime(provider_id, instance_id)
    for (instance_id, reservation_id), reservation in reservations.items():
        bound = resource_bindings[(instance_id, reservation_id)]
        if len(bound) == 1 and bound[0] in pools:
            provider_lifetime(
                pools[bound[0]].provider_id,
                instance_id,
                consumed=not reservation.reusable,
            )

    # Least fixed point: no strongly connected assumptions establish themselves.
    # An independent anchor must actually replace a selected cyclic prerequisite.
    grounded = set()
    while True:
        additions = {
            key
            for key, required in prerequisites.items()
            if key not in grounded
            and key not in invalid_providers
            and required <= grounded
        }
        if not additions:
            break
        grounded.update(additions)
    resolved_final = []
    for dependency in resolved:
        key = (dependency.instance_id, dependency.requirement_id)
        chosen = selected_providers.get(key)
        status = "pass" if chosen in grounded else dependency.status
        if chosen is not None and chosen not in grounded and requirements[key].required:
            diagnostic(
                "unknown",
                "ungrounded_provider",
                "Provider prerequisites are missing, invalid, or circular; assumptions cannot establish their own guarantees.",
                dependency.instance_id,
            )
        resolved_final.append(
            ResolvedDependency(
                dependency.instance_id,
                dependency.requirement_id,
                chosen,
                dependency.provider_kind,
                status,
            )
        )
    resolved[:] = resolved_final

    physical_pools = defaultdict(list)
    for pool in request.resource_pools:
        # Every host provider refers to the same target host. Renaming host
        # provider records cannot multiply one declared host resource capacity.
        physical_provider = (
            "@target_host"
            if provider_kinds.get(pool.provider_id) == "host"
            else pool.provider_id
        )
        physical_pools[(physical_provider, pool.resource)].append(pool.id)
    for aliases in physical_pools.values():
        if len(aliases) > 1:
            diagnostic(
                "unsupported",
                "aliased_resource_pool",
                "Multiple pool IDs alias one provider resource; explicit partitioning is unsupported.",
            )

    for key in resource_bindings.keys() - reservations.keys():
        diagnostic(
            "fail",
            "unknown_resource_binding",
            "Resource binding names no declared reservation.",
            key[0],
        )
    events = defaultdict(list)
    pool_statuses = defaultdict(set)
    used_pools = set()
    for (instance_id, reservation_id), reservation in reservations.items():
        bound = resource_bindings[(instance_id, reservation_id)]
        if len(bound) != 1 or bound[0] not in pools:
            diagnostic(
                "fail" if len(bound) > 1 else "unknown",
                "missing_resource_pool",
                "Every reservation requires exactly one declared resource pool.",
                instance_id,
            )
            continue
        pool = pools[bound[0]]
        used_pools.add(pool.id)
        if (reservation.resource, reservation.unit, reservation.dtype) != (
            pool.resource,
            pool.unit,
            pool.dtype,
        ):
            pool_statuses[pool.id].add("fail")
            diagnostic(
                "fail",
                "resource_unit_or_type",
                "Reservation and pool must match resource meaning, type and explicit units.",
                instance_id,
            )
            continue
        if not any(
            (cap.id, cap.role, cap.scope, cap.compartment)
            == (
                reservation.resource,
                reservation.role,
                reservation.scope,
                reservation.compartment,
            )
            for cap in provider_caps.get(pool.provider_id, ())
        ):
            pool_statuses[pool.id].add("fail")
            diagnostic(
                "fail",
                "resource_provider_context",
                "A resource provider must match the reservation's exact role, contact scope and compartment.",
                instance_id,
            )
            continue
        if reservation.amount is None:
            pool_statuses[pool.id].add("unknown")
            diagnostic(
                "unknown",
                "unknown_reservation",
                "A resource reservation amount is unknown.",
                instance_id,
            )
            continue
        lifetime = instances[instance_id].lifetime
        if lifetime.unit != "s":
            pool_statuses[pool.id].add("unsupported")
            diagnostic(
                "unsupported",
                "unsupported_lifecycle",
                "Only explicit half-open lifecycle intervals in seconds are supported.",
                instance_id,
            )
            continue
        amount = Fraction(str(reservation.amount))
        events[pool.id].append((Fraction(str(lifetime.start)), amount))
        if reservation.reusable and lifetime.end is not None:
            events[pool.id].append((Fraction(str(lifetime.end)), -amount))
    for pool_id in sorted(used_pools):
        pool = pools[pool_id]
        statuses = pool_statuses[pool_id]
        if pool.provider_id not in grounded:
            statuses.add("unknown")
            diagnostic(
                "unknown",
                "resource_provider_unresolved",
                f"Pool {pool_id!r} has no grounded provider.",
            )
        if not any(
            cap.id == pool.resource for cap in provider_caps.get(pool.provider_id, ())
        ):
            statuses.add("fail")
            diagnostic(
                "fail",
                "resource_provider_capability",
                f"Pool {pool_id!r} is not supplied by the named provider capability.",
            )
        if pool.capacity is None:
            statuses.add("unknown")
            diagnostic(
                "unknown",
                "unknown_capacity",
                f"Pool {pool_id!r} capacity is unknown; missing measurement is not unlimited capacity.",
            )
        if provider_kinds.get(pool.provider_id) == "host":
            target_capacity = request.target.resources.get(pool.resource)
            if target_capacity is None:
                statuses.add("unknown")
                diagnostic(
                    "unknown",
                    "unknown_host_capacity",
                    f"Target does not declare capacity for host resource {pool.resource!r}.",
                )
            elif (
                target_capacity.dtype != pool.dtype
                or target_capacity.unit != pool.unit
                or pool.capacity is not None
                and pool.capacity > target_capacity.value
            ):
                statuses.add("fail")
                diagnostic(
                    "fail",
                    "host_capacity_mismatch",
                    f"Pool {pool_id!r} exceeds or differs from the target host resource declaration.",
                )
        current = peak = Fraction(0)
        # Negative end events sort before starts at the same instant, realizing
        # half-open intervals without crediting any unproven earlier release.
        for _, change in sorted(events[pool_id]):
            current += change
            peak = max(peak, current)
        if pool.capacity is not None and peak > Fraction(str(pool.capacity)):
            statuses.add("fail")
            diagnostic(
                "fail",
                "resource_overallocation",
                f"Pool {pool_id!r} exceeds its declared shared capacity.",
            )
        status = next(
            (
                value
                for value in ("fail", "unsupported", "unknown")
                if value in statuses
            ),
            "pass",
        )
        try:
            peak_value = int(peak) if peak.denominator == 1 else float(peak)
            if not math.isfinite(peak_value):
                raise OverflowError
        except OverflowError:
            peak_value = None
            diagnostic(
                "unknown",
                "resource_total_unrepresentable",
                f"Pool {pool_id!r} total exceeds finite artifact reporting; exact capacity comparison was retained.",
            )
            statuses.add("unknown")
            status = next(
                (
                    value
                    for value in ("fail", "unsupported", "unknown")
                    if value in statuses
                ),
                "pass",
            )
        usage.append(
            ResourceUsage(
                pool_id,
                None if statuses & {"unknown", "unsupported"} else peak_value,
                pool.capacity,
                pool.unit,
                status,
            )
        )
    return finish()
