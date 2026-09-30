"""Adapt accepted synthetic mechanisms into exact, typed component compositions.

The adapter models the existing software operators only. Empty resource demand
means this digital profile declares no biological reservation; it never asserts
unlimited host capacity or a molecular implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

from biocompiler.ir.component_contracts import (
    ComponentRecord,
    ParameterProvenance,
    PinnedIdentity,
)
from biocompiler.ir.composition import (
    CompositionInstance,
    CompositionRequest,
    Connection,
)
from biocompiler.ir.serialization import require
from biocompiler.models.synthetic import MODEL_RUNNER_VERSION
from biocompiler.registry.components import ComponentRegistry
from biocompiler.registry.synthetic import SYNTHETIC_CATALOG, SYNTHETIC_PROFILE_VERSION
from biocompiler.semantics.component_contracts import (
    OperatingDomain,
    PortContract,
    ValueDomain,
)
from biocompiler.semantics.types import Interval
from biocompiler.synthesis.synthetic import check_synthetic_candidate
from biocompiler.verification.evidence import CheckOutcome, CheckResult

SYNTHETIC_COMPONENT_ADAPTER_VERSION = "biocompiler.synthetic_components.v0.1"
_TIMING = "atomic_snapshot_stateless.v0.1"


@dataclass(frozen=True)
class SyntheticComposition:
    registry: ComponentRegistry
    composition: CompositionRequest
    acceptance: CheckResult


def _unit(dtype):
    """Name canonical base units; no conversion or label-based equivalence."""
    known = {
        (): "1",
        (("time", 1),): "s",
        (("amount", 1), ("length", -3)): "mol/m^3",
        (("amount", 1), ("length", -2)): "mol/m^2",
        (("amount", 1), ("time", -1)): "mol/s",
    }
    return known.get(
        dtype.dimensions,
        "canonical:" + ";".join(f"{key}^{power}" for key, power in dtype.dimensions),
    )


def _input_domain(item):
    if isinstance(item.allowed, Interval):
        return ValueDomain.interval(
            item.allowed.lower.canonical_value,
            item.allowed.upper.canonical_value,
            item.observable.dtype,
            _unit(item.observable.dtype),
        )
    return ValueDomain.boolean(item.allowed)


def _output_domains(request, candidate):
    authored = {
        (item.signal_id, item.field): _input_domain(item)
        for item in request.domain.inputs
    }
    input_domains = {
        item.mechanism_input_id: authored[(item.signal_id, item.field)]
        for item in candidate.observation_map.inputs
    }
    result = {}
    for node in candidate.mechanism.topological_nodes():
        incoming = [result[ref] for ref in node.inputs]
        if node.kind == "input":
            value = input_domains[node.id]
        elif node.kind == "constant":
            literal = node.attributes["value"]
            value = (
                ValueDomain.boolean((literal,))
                if type(literal) is bool
                else ValueDomain.interval(
                    literal["canonical_value"],
                    literal["canonical_value"],
                    node.output.dtype,
                    _unit(node.output.dtype),
                )
            )
        elif node.kind in {"and", "or"}:
            if node.kind == "and":
                values = (
                    {False} if any(False in item.values for item in incoming) else set()
                ) | ({True} if all(True in item.values for item in incoming) else set())
            else:
                values = (
                    {True} if any(True in item.values for item in incoming) else set()
                ) | (
                    {False} if all(False in item.values for item in incoming) else set()
                )
            value = ValueDomain.boolean(tuple(sorted(values)))
        elif node.kind == "not":
            value = ValueDomain.boolean(tuple(not item for item in incoming[0].values))
        elif node.kind == "compare":
            # A sound bound. Relational correlations are outside this contract algebra.
            value = ValueDomain.boolean()
        elif node.kind == "any_contact":
            value = ValueDomain.boolean(
                (False, True)
                if True in incoming[0].values and request.domain.max_contacts
                else (False,)
            )
        elif node.kind == "select":
            branches = [
                incoming[1] if condition else incoming[2]
                for condition in incoming[0].values
            ]
            if node.output.dtype.kind == "condition":
                value = ValueDomain.boolean(
                    tuple(sorted({v for branch in branches for v in branch.values}))
                )
            else:
                value = ValueDomain.interval(
                    min(branch.lower for branch in branches),
                    max(branch.upper for branch in branches),
                    node.output.dtype,
                    _unit(node.output.dtype),
                )
        elif node.kind == "output":
            value = incoming[0]
        else:
            require(False, "Unsupported synthetic component operation.")
        result[node.id] = value
    return result


def adapt_synthetic_components(
    request, candidate, history, *, until=None
) -> SyntheticComposition:
    """Recheck exact request/candidate/history, then preserve every node and edge.

    This requires independently checked finite-trace acceptance. Composition
    linking does not upgrade that result into universal or biological evidence.
    """
    require(
        candidate.generator_config.profile_version == SYNTHETIC_PROFILE_VERSION,
        "The component linker currently supports only the stateless combinational profile; temporal interfaces require a separate timing contract.",
    )
    acceptance = check_synthetic_candidate(
        request, candidate, tuple(history), until=until
    )
    require(
        acceptance.outcome == CheckOutcome.PASS,
        "Component adaptation requires passing synthetic acceptance for the current request, candidate and history.",
    )
    domains = _output_domains(request, candidate)
    nodes = {node.id: node for node in candidate.mechanism.nodes}
    required_domain = OperatingDomain(
        {
            **{
                f"observation:{item.signal_id}:{item.field}": _input_domain(item)
                for item in request.domain.inputs
            },
            "concurrent_contacts": ValueDomain.interval(0, request.domain.max_contacts),
        }
    )
    request_identity = PinnedIdentity(
        "source", "realization_request", request.schema_version, request.fingerprint
    )
    identities = (
        request_identity,
        PinnedIdentity(
            "model",
            "synthetic.program",
            MODEL_RUNNER_VERSION,
            candidate.mechanism.fingerprint,
        ),
        PinnedIdentity(
            "registry",
            "synthetic.catalog",
            SYNTHETIC_CATALOG.version,
            SYNTHETIC_CATALOG.fingerprint,
        ),
    )

    def port(ref, port_id, direction):
        observable = nodes[ref].output
        return PortContract(
            port_id,
            direction,
            observable.id,
            observable.dtype,
            domains[ref].unit,
            observable.role,
            observable.scope,
            observable.compartment,
            _TIMING,
            domains[ref],
            domains[ref],
        )

    records = {}
    for node in candidate.mechanism.nodes:
        operator = SYNTHETIC_CATALOG.for_operation(node.kind)
        parameters = ()
        if node.kind == "constant":
            parameters = (
                ParameterProvenance(
                    "value",
                    domains[node.id],
                    request_identity,
                    "authored_bound_literal"
                    if node.id.startswith("expression:")
                    else "contract_band_lower_endpoint_witness",
                ),
            )
        records[node.id] = ComponentRecord(
            id="synthetic.instance:" + node.id,
            version="1",
            classification="synthetic_model",
            implementation_role=node.kind,
            supported_targets=(request.target.payload_format.value,),
            ports=(
                port(node.id, "out", "output"),
                *(
                    port(ref, f"in:{index}", "input")
                    for index, ref in enumerate(node.inputs)
                ),
            ),
            supported_domain=required_domain,
            identities=(
                *identities,
                PinnedIdentity(
                    "source", operator.id, operator.version, operator.fingerprint
                ),
            ),
            assumptions=(
                *operator.assumptions,
                "Adapter policy: " + SYNTHETIC_COMPONENT_ADAPTER_VERSION,
                "No biological resource demand or capacity is declared by this software profile.",
            ),
            guarantees=operator.guarantees,
            parameters=parameters,
        )
    registry = ComponentRegistry(
        "synthetic.components:" + candidate.fingerprint,
        SYNTHETIC_COMPONENT_ADAPTER_VERSION,
        tuple(records.values()),
    )
    lock = registry.lock(records)
    component_locks = {item.node_id: item for item in lock.components}
    behavior_nodes = {node.id: node for node in request.behavior.nodes}
    instances = tuple(
        CompositionInstance(
            node.id,
            component_locks[node.id],
            required_domain,
            requirement_ids=tuple(
                sorted(
                    set(node.requirement_ids)
                    | set(candidate.behavior_requirement_ids[node.id])
                )
            ),
            source=next(
                (
                    behavior_nodes[ref].source
                    for ref in candidate.source_map[node.id]
                    if behavior_nodes[ref].source is not None
                ),
                None,
            ),
        )
        for node in candidate.mechanism.nodes
    )
    composition = CompositionRequest(
        request.target,
        lock,
        instances,
        connections=tuple(
            Connection(ref, "out", node.id, f"in:{index}")
            for node in candidate.mechanism.nodes
            for index, ref in enumerate(node.inputs)
        ),
        requirement_ids=tuple(
            sorted(
                {item.id for item in request.behavior.requirements}
                | {item.id for item in request.contract.requirements}
            )
        ),
    )
    return SyntheticComposition(registry, composition, acceptance)
