"""Typed, inert target-plan request assembly and explicit native dispatch.

Planning does not execute histories, discharge requirements or produce payloads.
Use the raw client for malformed-source diagnostics; this facade accepts frozen
source records and carries every supplied authority unchanged to the producer.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, cast

from biocompiler.core_client import JsonValue, decode_json, encode_json
from biocompiler.core_policy_planning import (
    MAX_INPUT_BYTES, MAX_RESULT_BYTES, MAX_RESULT_NODES, REQUEST_SCHEMA,
    PolicyTargetPlan, PolicyTargetPlanningClient, TargetId,
)
from .model import BuildRequest, CompilationSubmission, PolicyProgram
from .serialization import to_data


@dataclass(frozen=True, slots=True)
class PlanningLimits:
    """Bounded diagnostic work and publication; never execution allowances."""
    max_work: int = 100_000_000
    max_report_bytes: int = MAX_RESULT_BYTES
    max_report_nodes: int = MAX_RESULT_NODES

    def __post_init__(self) -> None:
        for name, maximum in (("max_work", 100_000_000), ("max_report_bytes", MAX_RESULT_BYTES),
                              ("max_report_nodes", MAX_RESULT_NODES)):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(name + " must be a positive integer within the planning profile")

    def to_data(self) -> dict[str, JsonValue]:
        return {"max_work": self.max_work, "max_report_bytes": self.max_report_bytes,
                "max_report_nodes": self.max_report_nodes}


def prepare_request(document: PolicyProgram | BuildRequest | CompilationSubmission, *, target: TargetId,
                    definitions: JsonValue = None, realization_request: JsonValue = None,
                    material_request: JsonValue = None, limits: PlanningLimits = PlanningLimits()) -> dict[str, JsonValue]:
    """Freeze explicit inputs; supplying or preparing them performs no admission.

    If only material authority is supplied, its complete nested realization
    request is copied into the explicit wire field. Native planning checks that
    all repeated original source, definitions and request identities agree.
    """
    if type(document) not in (PolicyProgram, BuildRequest, CompilationSubmission):
        raise TypeError("Target planning requires a frozen source program, request or submission")
    if type(limits) is not PlanningLimits:
        raise TypeError("Target planning requires explicit PlanningLimits")
    if realization_request is None and type(material_request) is dict:
        realization_request = material_request.get("implementation_request")
    raw: JsonValue = {"schema_version": REQUEST_SCHEMA, "target": target,
        "document": cast(JsonValue, to_data(document)), "definitions": definitions,
        "realization_request": realization_request, "material_request": material_request,
        "limits": limits.to_data()}
    return cast(dict[str, JsonValue], decode_json(encode_json(raw, limit=MAX_INPUT_BYTES)))


def plan(request: JsonValue, *, client: PolicyTargetPlanningClient,
         cancelled: Callable[[], bool] | None = None) -> PolicyTargetPlan:
    """Run one fresh native diagnostic plan; no checked capability is returned."""
    return client.plan(request, cancelled=cancelled)


def replay(request: JsonValue, *, report: PolicyTargetPlan, client: PolicyTargetPlanningClient,
           cancelled: Callable[[], bool] | None = None) -> PolicyTargetPlan:
    """Recompute against original authority and compare the complete saved result."""
    return client.replay(request, report=report.result, cancelled=cancelled)
