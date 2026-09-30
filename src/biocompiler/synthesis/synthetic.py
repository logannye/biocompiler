"""Deterministic generation for a narrow combinational synthetic profile.

Generation establishes no acceptance claim. ``check_synthetic_candidate`` runs
the separate model runner and finite-history response checker afterwards.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import ClassVar

from biocompiler.errors import UnsupportedBehaviorError
from biocompiler.ir.components import ComponentLock
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.mechanism import MechanismNode, MechanismProgram
from biocompiler.ir.serialization import JsonArtifact, fields, names, require
from biocompiler.registry.synthetic import SYNTHETIC_CATALOG, SYNTHETIC_PROFILE_VERSION
from biocompiler.semantics.evaluator import InputFrame
from biocompiler.semantics.realization import Observable
from biocompiler.semantics.types import BOOLEAN, TypeSpec
from biocompiler.verification.evidence import (
    CheckDiagnostic,
    CheckOutcome,
    CheckResult,
    DependencySnapshot,
)
from biocompiler.verification.realization import (
    InputBinding,
    ObservationMap,
    OutputBinding,
    check_realization,
    realization_dependencies,
)

GENERATOR_VERSION = "biocompiler.synthetic.generator.v0.1"
SYNTHETIC_CHECKER_VERSION = "biocompiler.synthetic.acceptance.v0.2"


def _identity(value, label):
    require(
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value),
        f"{label} must be a SHA-256 identity.",
    )


@dataclass(frozen=True)
class SyntheticGeneratorConfig(JsonArtifact):
    """An exhaustive generation policy; no stochastic search is performed."""

    profile_version: str = SYNTHETIC_PROFILE_VERSION
    generator_version: str = GENERATOR_VERSION
    catalog_fingerprint: str = SYNTHETIC_CATALOG.fingerprint
    witness_selection: str = "closed_band_lower_endpoint"
    schema_version: ClassVar[str] = "biocompiler.synthetic_generator_config.v0.1"

    def __post_init__(self):
        require(
            self.profile_version == SYNTHETIC_PROFILE_VERSION,
            "Unsupported synthetic generation profile.",
        )
        require(
            self.generator_version == GENERATOR_VERSION,
            "Unsupported synthetic generator version.",
        )
        require(
            self.catalog_fingerprint == SYNTHETIC_CATALOG.fingerprint,
            "The selected synthetic catalog is unavailable or stale.",
        )
        require(
            self.witness_selection == "closed_band_lower_endpoint",
            "Unsupported response witness selection policy.",
        )

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "profile_version": self.profile_version,
            "generator_version": self.generator_version,
            "catalog_fingerprint": self.catalog_fingerprint,
            "witness_selection": self.witness_selection,
        }

    @classmethod
    def from_dict(cls, data: Mapping):
        fields(
            data,
            {
                "schema_version",
                "profile_version",
                "generator_version",
                "catalog_fingerprint",
                "witness_selection",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported generator-config schema.",
        )
        return cls(
            **{key: value for key, value in data.items() if key != "schema_version"}
        )


@dataclass(frozen=True)
class SyntheticCandidate(JsonArtifact):
    request_fingerprint: str
    mechanism: MechanismProgram
    observation_map: ObservationMap
    source_map: Mapping[str, tuple[str, ...]]
    behavior_requirement_ids: Mapping[str, tuple[str, ...]]
    component_locks: tuple[ComponentLock, ...]
    generator_config: SyntheticGeneratorConfig
    schema_version: ClassVar[str] = "biocompiler.synthetic_candidate.v0.1"

    def __post_init__(self):
        _identity(self.request_fingerprint, "Request fingerprint")
        require(
            isinstance(self.mechanism, MechanismProgram),
            "Candidate requires a mechanism.",
        )
        require(
            isinstance(self.observation_map, ObservationMap),
            "Candidate requires an observation map.",
        )
        require(
            isinstance(self.generator_config, SyntheticGeneratorConfig),
            "Candidate requires a generator configuration.",
        )
        node_ids = {node.id for node in self.mechanism.nodes}
        for key in ("source_map", "behavior_requirement_ids"):
            value = getattr(self, key)
            require(
                isinstance(value, Mapping) and set(value) == node_ids,
                f"{key} must cover every mechanism node exactly once.",
            )
            normalized = {ref: names(items, key) for ref, items in value.items()}
            if key == "source_map":
                require(
                    all(normalized.values()),
                    "Every mechanism node needs source correspondence.",
                )
            object.__setattr__(self, key, freeze_json(normalized))
        require(
            isinstance(self.component_locks, (tuple, list))
            and all(isinstance(item, ComponentLock) for item in self.component_locks),
            "Candidate requires component locks.",
        )
        locks = tuple(sorted(self.component_locks, key=lambda item: item.node_id))
        require(
            len({item.node_id for item in locks}) == len(locks)
            and {item.node_id for item in locks} == node_ids,
            "Component locks must cover every mechanism node exactly once.",
        )
        object.__setattr__(self, "component_locks", locks)

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "request_fingerprint": self.request_fingerprint,
            "mechanism": self.mechanism.to_dict(),
            "observation_map": self.observation_map.to_dict(),
            "source_map": thaw_json(self.source_map),
            "behavior_requirement_ids": thaw_json(self.behavior_requirement_ids),
            "component_locks": [item.to_dict() for item in self.component_locks],
            "generator_config": self.generator_config.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping):
        fields(
            data,
            {
                "schema_version",
                "request_fingerprint",
                "mechanism",
                "observation_map",
                "source_map",
                "behavior_requirement_ids",
                "component_locks",
                "generator_config",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported candidate schema.",
        )
        require(
            isinstance(data["component_locks"], (tuple, list)),
            "Component locks must be an array.",
        )
        return cls(
            data["request_fingerprint"],
            MechanismProgram.from_dict(data["mechanism"]),
            ObservationMap.from_dict(data["observation_map"]),
            data["source_map"],
            data["behavior_requirement_ids"],
            tuple(ComponentLock.from_dict(item) for item in data["component_locks"]),
            SyntheticGeneratorConfig.from_dict(data["generator_config"]),
        )


def _request(request):
    # Local import keeps the generator independent of authoring module imports.
    from biocompiler.compiler.request import RealizationRequest

    if not isinstance(request, RealizationRequest):
        raise TypeError("Synthetic generation requires a frozen RealizationRequest.")
    return (
        request.behavior,
        request.contract,
        request.domain,
        request.build_request.target,
    )


def generate_synthetic(
    request, *, config: SyntheticGeneratorConfig | None = None
) -> SyntheticCandidate:
    """Generate stateless digital operators from an authorized Behavior artifact.

    Supported guards are explicit qualitative observations, scalar observations
    compared to literals/bound parameters, and Boolean and/or/not combinations.
    Signature wrappers preserve their expression. Ongoing ``rest``, ``eliminate``
    and ``engulf`` requests become authored abstract response measurements.
    Response levels are compiler-selected witnesses in the authored bands, not
    new biological guarantees; deadlines are never changed or inferred.
    """
    behavior, contract, domain, target = _request(request)
    config = config if config is not None else SyntheticGeneratorConfig()
    require(
        isinstance(config, SyntheticGeneratorConfig),
        "Expected a synthetic generator configuration.",
    )
    source_nodes = {node.id: node for node in behavior.nodes}

    def reject(message, node=None):
        raise UnsupportedBehaviorError(
            message,
            node_id=node.id if node else None,
            source=node.source if node else None,
        )

    if request.build_request.artifact_scope != "synthetic_realization":
        reject(
            "Synthetic generation requires the explicit synthetic_realization artifact scope."
        )
    if (
        request.build_request.implementation_constraints
        or request.build_request.preferences
    ):
        reject(
            "This fixed synthetic catalog has no implementation-constraint or preference resolver; nonempty selections are unsupported."
        )
    if len(behavior.find(kind="role")) != 1 or domain.role != contract.role:
        reject(
            "The combinational synthetic profile requires exactly one executing role."
        )
    if domain.max_contacts is None:
        reject(
            "The combinational profile requires an explicit finite max_contacts bound."
        )
    if target is None or "synthetic_signal_graph" not in target.capabilities:
        reject(
            "Synthetic generation requires a target with synthetic_signal_graph capability."
        )
    if "abstract" not in target.compartments:
        reject("Synthetic generation requires the abstract compartment.")
    if set(domain.required_capabilities) - set(target.capabilities):
        reject("The target does not provide all operating-domain capabilities.")
    supported = {
        "role",
        "scope",
        "signal",
        "qualitative",
        "literal",
        "parameter",
        "and",
        "or",
        "not",
        "compare",
        "signature",
        "rule",
        "action.rest",
        "action.eliminate",
        "action.engulf",
    }
    for node in behavior.nodes:
        if node.kind not in supported:
            reject(
                f"Operation {node.kind!r} is unsupported by {SYNTHETIC_PROFILE_VERSION}; temporal/state semantics are never approximated.",
                node,
            )
        if node.kind == "rule" and node.attributes["trigger"] != "condition":
            reject(
                "The combinational synthetic profile requires condition-triggered rules.",
                node,
            )
    installed = {
        (rule.id, action)
        for rule in behavior.find(kind="rule")
        for action in rule.inputs[2:]
    }
    if installed != {
        (item.rule_id, item.specification_id) for item in contract.requirements
    }:
        reject("A response contract must cover every installed action exactly once.")
    if contract.behavior_fingerprint != behavior.fingerprint:
        reject("The response contract identifies a different Behavior artifact.")
    for item in (*domain.inputs, *contract.requirements):
        if item.observable.compartment != "abstract":
            reject("Synthetic components support only the abstract compartment.")

    generated: dict[str, MechanismNode] = {}
    source_map = {}
    behavior_requirements = {}
    input_map = {}
    observed = set()
    domain_inputs = {(item.signal_id, item.field): item for item in domain.inputs}
    expression_cache = {}
    response_sources = {
        item.id: set(behavior.source_links[item.rule_id])
        for item in contract.requirements
    }

    def add(
        ref,
        kind,
        dtype,
        scope,
        sources,
        inputs=(),
        attributes=None,
        output=None,
        response_ids=None,
    ):
        lineage = tuple(
            sorted(
                {
                    ancestor
                    for source in sources
                    for ancestor in behavior.source_links[source]
                }
            )
        )
        response_ids = tuple(
            sorted(
                response_ids
                if response_ids is not None
                else (
                    item.id
                    for item in contract.requirements
                    if set(sources) & response_sources[item.id]
                )
            )
        )
        generated[ref] = MechanismNode(
            ref,
            kind,
            output or Observable(f"synthetic.{ref}", dtype, domain.role, scope=scope),
            tuple(inputs),
            attributes or {},
            response_ids,
        )
        source_map[ref] = lineage
        behavior_requirements[ref] = tuple(
            sorted(
                {
                    requirement
                    for source in sources
                    for requirement in source_nodes[source].requirement_ids
                }
            )
        )
        return ref

    def observe(signal_id, field, source_id):
        key = (signal_id, field)
        if key not in domain_inputs:
            reject(
                f"Missing explicit operating-domain observation {key!r}.",
                source_nodes[source_id],
            )
        item, node = domain_inputs[key], source_nodes[signal_id]
        dtype = TypeSpec.from_dict(node.data_type) if field == "value" else BOOLEAN
        scope = "contact" if node.contact_bound else "cell"
        if item.observable.scope != scope or not item.observable.dtype.compatible(
            dtype
        ):
            reject(
                "The operating-domain observation has incorrect type or contact scope.",
                node,
            )
        observed.add(key)
        if key not in input_map:
            ref = f"input:{signal_id}:{field}"
            input_map[key] = add(
                ref, "input", dtype, scope, (source_id,), output=item.observable
            )
        else:
            ref = input_map[key]
            source_map[ref] = tuple(
                sorted(set(source_map[ref]) | set(behavior.source_links[source_id]))
            )
            behavior_requirements[ref] = tuple(
                sorted(
                    set(behavior_requirements[ref])
                    | set(source_nodes[source_id].requirement_ids)
                )
            )
            generated[ref] = replace(
                generated[ref],
                requirement_ids=tuple(
                    sorted(
                        set(generated[ref].requirement_ids)
                        | {
                            item.id
                            for item in contract.requirements
                            if source_id in response_sources[item.id]
                        }
                    )
                ),
            )
        return input_map[key]

    def expression(ref):
        if ref in expression_cache:
            return expression_cache[ref]
        node = source_nodes[ref]
        scope = "contact" if node.contact_bound else "cell"
        if node.kind == "qualitative":
            result = observe(node.inputs[0], node.attributes["band"], ref)
        elif node.kind == "signal":
            result = observe(ref, "value", ref)
        elif node.kind == "signature":
            result = expression(node.inputs[0])
            source_map[result] = tuple(
                sorted(set(source_map[result]) | set(behavior.source_links[ref]))
            )
        elif node.kind in {"literal", "parameter"}:
            result = add(
                f"expression:{ref}",
                "constant",
                TypeSpec.from_dict(node.data_type),
                "cell",
                (ref,),
                attributes={
                    "value": node.attributes[
                        "value" if node.kind == "literal" else "default"
                    ]
                },
            )
        elif node.kind in {"and", "or", "not", "compare"}:
            result = add(
                f"expression:{ref}",
                node.kind,
                BOOLEAN,
                scope,
                (ref,),
                inputs=tuple(expression(item) for item in node.inputs),
                attributes={"operator": node.attributes["operator"]}
                if node.kind == "compare"
                else None,
            )
        else:
            reject(f"Unsupported combinational expression {node.kind!r}.", node)
        expression_cache[ref] = result
        return result

    outputs = []
    bindings = []
    for requirement in contract.requirements:
        rule = source_nodes[requirement.rule_id]
        action = source_nodes[requirement.specification_id]
        scope = "contact" if action.contact_bound else "cell"
        if (
            requirement.observable.role != domain.role
            or requirement.observable.scope != scope
        ):
            reject(
                "The response observable does not preserve its action's role/contact scope.",
                action,
            )
        guard = expression(rule.inputs[1])
        if generated[guard].scope == "contact" and scope == "cell":
            guard = add(
                f"aggregate:{requirement.id}",
                "any_contact",
                BOOLEAN,
                "cell",
                (rule.id,),
                inputs=(guard,),
                response_ids=(requirement.id,),
            )
        values = []
        for state, band in (
            ("active", requirement.active_range),
            ("inactive", requirement.inactive_range),
        ):
            values.append(
                add(
                    f"{state}:{requirement.id}",
                    "constant",
                    requirement.observable.dtype,
                    scope,
                    (rule.id, action.id),
                    attributes={"value": band.lower.to_dict()},
                    response_ids=(requirement.id,),
                )
            )
        selected = add(
            f"select:{requirement.id}",
            "select",
            requirement.observable.dtype,
            scope,
            (rule.id, action.id),
            inputs=(guard, *values),
            response_ids=(requirement.id,),
        )
        output = add(
            f"output:{requirement.id}",
            "output",
            requirement.observable.dtype,
            scope,
            (rule.id, action.id),
            inputs=(selected,),
            output=requirement.observable,
            response_ids=(requirement.id,),
        )
        outputs.append(output)
        bindings.append(OutputBinding(requirement.id, output))
    if observed != set(domain_inputs):
        reject(
            "Operating-domain inputs must cover exactly the supported runtime observations; extra observations are not silently ignored."
        )
    mechanism = MechanismProgram(
        f"{behavior.name}.synthetic",
        tuple(generated[key] for key in sorted(generated)),
        tuple(outputs),
        ("synthetic_signal_graph",),
    )
    return SyntheticCandidate(
        request.fingerprint,
        mechanism,
        ObservationMap(
            tuple(InputBinding(*key, input_map[key]) for key in sorted(input_map)),
            tuple(bindings),
        ),
        source_map,
        behavior_requirements,
        SYNTHETIC_CATALOG.lock(mechanism),
        config,
    )


def check_synthetic_candidate(
    request, candidate: SyntheticCandidate, history: Iterable[InputFrame], *, until=None
) -> CheckResult:
    """Independently check this candidate over the supplied finite history.

    Component/source metadata cannot establish behavior. A valid inventory is
    followed by ``check_realization``, which executes both independent models.
    A passing result requires exercised active and inactive deadlines for every
    response. Its dependencies include this acceptance policy, the candidate,
    request and generator configuration in addition to model execution inputs.
    """
    behavior, contract, domain, target = _request(request)
    if not isinstance(candidate, SyntheticCandidate):
        raise TypeError("Expected a SyntheticCandidate.")
    frames = tuple(history)
    dependencies = realization_dependencies(
        behavior,
        contract,
        domain,
        target,
        candidate.mechanism,
        candidate.observation_map,
        frames,
        until=until,
    )
    dependencies = DependencySnapshot(
        {
            **dependencies.values,
            "settings": {
                **dependencies.values["settings"],
                "synthetic_acceptance": SYNTHETIC_CHECKER_VERSION,
                "synthetic_profile": SYNTHETIC_PROFILE_VERSION,
                "synthetic_candidate": candidate.fingerprint,
                "realization_request": request.fingerprint,
                "generator_configuration": candidate.generator_config.fingerprint,
                "catalog": SYNTHETIC_CATALOG.fingerprint,
                "required_coverage": "active_and_inactive_deadlines_for_every_response",
            },
        }
    )

    def failure(code, message):
        return CheckResult(
            CheckOutcome.FAIL,
            dependencies,
            tuple(item.id for item in contract.requirements),
            (CheckDiagnostic(code, message),),
        )

    if candidate.request_fingerprint != request.fingerprint:
        return failure(
            "candidate_request_identity",
            "The candidate belongs to a different frozen realization request.",
        )
    try:
        provenance = generate_synthetic(request, config=candidate.generator_config)
    except UnsupportedBehaviorError as error:
        return CheckResult(
            CheckOutcome.UNSUPPORTED,
            dependencies,
            tuple(item.id for item in contract.requirements),
            (
                CheckDiagnostic(
                    "unsupported_generation_profile",
                    str(error),
                    node_id=error.node_id,
                    source=error.source,
                ),
            ),
        )
    # Replay only the deterministic provenance policy. This neither compares
    # candidate edges/response values nor establishes behavioral refinement.
    if (
        candidate.source_map != provenance.source_map
        or candidate.behavior_requirement_ids != provenance.behavior_requirement_ids
    ):
        return failure(
            "candidate_lineage",
            "Source correspondence or requirement lineage differs from the declared generation profile.",
        )
    try:
        expected_locks = SYNTHETIC_CATALOG.lock(candidate.mechanism)
    except KeyError:
        return failure(
            "candidate_component",
            "The candidate contains an operation outside the pinned combinational catalog.",
        )
    if candidate.component_locks != expected_locks:
        return failure(
            "candidate_component",
            "The candidate's component versions or content identities are stale.",
        )
    nodes = {node.id: node for node in behavior.nodes}
    known_requirements = {item.id for item in behavior.requirements}
    for ref, lineage in candidate.source_map.items():
        if (
            set(lineage) - set(nodes)
            or set(candidate.behavior_requirement_ids[ref]) - known_requirements
        ):
            return failure(
                "candidate_lineage",
                "The candidate refers to unknown Behavior sources or requirements.",
            )
    carried_requirements = {
        item
        for values in candidate.behavior_requirement_ids.values()
        for item in values
    }
    if carried_requirements != known_requirements:
        return failure(
            "candidate_lineage",
            "The candidate does not retain every Behavior requirement.",
        )
    result = check_realization(
        behavior,
        contract,
        domain,
        target,
        candidate.mechanism,
        candidate.observation_map,
        frames,
        until=until,
    )
    return replace(result, dependencies=dependencies)
