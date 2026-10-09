"""Typed authoring and explicit native handoff for quantitative assurance.

Original inputs are snapshotted. Python assembles descriptions; native checking
establishes separately scoped mathematical and supplied-evidence conclusions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, cast

from biocompiler.core_client import JsonValue, decode_json, encode_json
from biocompiler.core_policy_quantitative_assurance import (
    MAX_WORK, REQUEST_SCHEMA, REQUEST_PROFILE, PolicyQuantitativeAssuranceClient,
    PolicyQuantitativeAssuranceResult, _request,
)
from .approximation import ApproximationContract
from .realization_evidence import EvidenceContract


@dataclass(frozen=True, slots=True, init=False)
class QuantitativeAssuranceRequest:
    _request_json: bytes

    def __init__(self, material_request: JsonValue, *, approximation: ApproximationContract | None = None,
                 realization_evidence: EvidenceContract | None = None, max_work: int = MAX_WORK) -> None:
        if approximation is not None and type(approximation) is not ApproximationContract:
            raise TypeError("Approximation requires an explicit typed contract")
        if realization_evidence is not None and type(realization_evidence) is not EvidenceContract:
            raise TypeError("Realization evidence requires an explicit typed contract")
        value: JsonValue = {"schema_version": REQUEST_SCHEMA, "profile": REQUEST_PROFILE,
            "material_request": material_request, "approximation": None if approximation is None else approximation.to_data(),
            "realization_evidence": None if realization_evidence is None else realization_evidence.to_data(), "max_work": max_work}
        snapshot = encode_json(value)
        _request(decode_json(snapshot))
        object.__setattr__(self, "_request_json", snapshot)

    def to_data(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._request_json))


def compile(request: QuantitativeAssuranceRequest, *, limits: JsonValue, client: PolicyQuantitativeAssuranceClient,
            cancelled: Callable[[], bool] | None = None) -> PolicyQuantitativeAssuranceResult:
    return client.compile(request.to_data(), limits, cancelled=cancelled)


def check(request: QuantitativeAssuranceRequest, *, candidate: JsonValue, limits: JsonValue,
          client: PolicyQuantitativeAssuranceClient, cancelled: Callable[[], bool] | None = None) -> PolicyQuantitativeAssuranceResult:
    return client.check(request.to_data(), candidate, limits, cancelled=cancelled)


def replay(request: QuantitativeAssuranceRequest, *, candidate: JsonValue, limits: JsonValue, report: JsonValue,
           client: PolicyQuantitativeAssuranceClient, cancelled: Callable[[], bool] | None = None) -> PolicyQuantitativeAssuranceResult:
    return client.replay(request.to_data(), candidate, limits, report, cancelled=cancelled)


def export(request: QuantitativeAssuranceRequest, *, candidate: JsonValue, limits: JsonValue,
           client: PolicyQuantitativeAssuranceClient, cancelled: Callable[[], bool] | None = None) -> PolicyQuantitativeAssuranceResult:
    return client.export(request.to_data(), candidate, limits, cancelled=cancelled)


__all__ = ["QuantitativeAssuranceRequest", "PolicyQuantitativeAssuranceClient", "PolicyQuantitativeAssuranceResult",
           "compile", "check", "replay", "export"]
