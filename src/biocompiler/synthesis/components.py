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
    SyntheticOperatorModel,
)
from biocompiler.ir.composition import (
    CompositionInstance,
    CompositionRequest,
    Connection,
)
from biocompiler.ir.serialization import require
from biocompiler.models.synthetic import MODEL_RUNNER_VERSION
from biocompiler.registry.components import ComponentRegistry
from biocompiler.registry.synthetic import catalog_for_profile, SYNTHETIC_PROFILE_VERSION
from biocompiler.semantics.component_contracts import (
    OperatingDomain,
    PortContract,
    ValueDomain,
    canonical_synthetic_unit, synthetic_output_domain,
    STATELESS_TIMING, TEMPORAL_LEVEL_TIMING, TEMPORAL_EVENT_TIMING,
)
from biocompiler.semantics.types import Interval, DURATION
from biocompiler.synthesis.synthetic import check_synthetic_candidate
from biocompiler.verification.evidence import CheckOutcome, CheckResult

SYNTHETIC_COMPONENT_ADAPTER_VERSION = "biocompiler.synthetic_components.v0.2"


@dataclass(frozen=True)
class SyntheticComposition:
    registry: ComponentRegistry
    composition: CompositionRequest
    acceptance: CheckResult


def _input_domain(item):
    if isinstance(item.allowed, Interval):
        return ValueDomain.interval(
            item.allowed.lower.canonical_value,
            item.allowed.upper.canonical_value,
            item.observable.dtype,
            canonical_synthetic_unit(item.observable.dtype),
        )
    return ValueDomain.boolean(item.allowed)


def _output_domains(request, candidate, *, initialization=False):
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
        result[node.id] = (
            input_domains[node.id] if node.kind == "input" else
            synthetic_output_domain(
                node.kind, node.attributes, [result[ref] for ref in node.inputs],
                node.output.dtype, initialization=initialization,
                max_contacts=request.domain.max_contacts,
            )
        )
    return result



def adapt_synthetic_components(
    request, candidate, history, *, until=None
) -> SyntheticComposition:
    """Recheck exact request/candidate/history, then preserve every node and edge.

    This requires independently checked finite-trace acceptance. Composition
    linking does not upgrade that result into universal or biological evidence.
    """
    profile = candidate.generator_config.profile_version
    catalog = catalog_for_profile(profile)
    acceptance = check_synthetic_candidate(
        request, candidate, tuple(history), until=until
    )
    require(
        acceptance.outcome == CheckOutcome.PASS,
        "Component adaptation requires passing synthetic acceptance for the current request, candidate and history.",
    )
    domains = _output_domains(request, candidate)
    initial_domains = _output_domains(request, candidate, initialization=True)
    nodes = {node.id: node for node in candidate.mechanism.nodes}
    events = set()
    for node in candidate.mechanism.topological_nodes():
        if node.kind == "onset" or (node.kind == "any_contact" and node.inputs[0] in events):
            events.add(node.id)
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
            catalog.version,
            catalog.fingerprint,
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
            STATELESS_TIMING if profile == SYNTHETIC_PROFILE_VERSION else (
                TEMPORAL_EVENT_TIMING if ref in events else TEMPORAL_LEVEL_TIMING
            ),
            initial_domains[ref],
            domains[ref],
        )

    records = {}
    for node in candidate.mechanism.nodes:
        operator = catalog.for_operation(node.kind)
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
        elif node.kind in {"held_for", "pulse", "memory"} and node.attributes["duration"] is not None:
            duration = node.attributes["duration"]["canonical_value"]
            parameters = (ParameterProvenance(
                "duration", ValueDomain.interval(duration, duration, DURATION, "s"),
                request_identity, "authored_bound_duration",
            ),)
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
            synthetic_model=SyntheticOperatorModel(
                node.kind, node.attributes,
                tuple(f"in:{index}" for index in range(len(node.inputs))),
            ),
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
