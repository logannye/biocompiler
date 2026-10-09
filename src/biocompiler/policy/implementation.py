"""Inert request assembly and explicit native implementation routing only."""
from __future__ import annotations

from typing import Callable, cast

from biocompiler.core_client import JsonValue, decode_json, encode_json
from biocompiler.core_policy_implementation import (
    REQUEST_PROFILE, REQUEST_SCHEMA, PREREQUISITE_REQUEST_PROFILE, PREREQUISITE_REQUEST_SCHEMA,
    TWO_OBSERVATION_REQUEST_PROFILE, TWO_OBSERVATION_REQUEST_SCHEMA,
    MULTI_PRODUCT_REQUEST_PROFILE, MULTI_PRODUCT_REQUEST_SCHEMA,
    FINITE_MACHINE_REQUEST_PROFILE, FINITE_MACHINE_REQUEST_SCHEMA,
    PolicyImplementationClient, PolicyImplementationResult,
)
from .model import BuildRequest
from .serialization import to_data


def prepare_request(document: BuildRequest, *, definitions: JsonValue, operating_domain: JsonValue,
                    implementation_library: JsonValue, catalog_bindings: JsonValue,
                    budgets: JsonValue, prerequisites: bool = False,
                    two_observations: bool = False, multi_product: bool = False, finite_machine: bool = False) -> dict[str, JsonValue]:
    """Freeze complete caller-supplied authority; this performs no admission."""
    if type(document) is not BuildRequest:
        raise TypeError("Implementation authority requires an original frozen BuildRequest")
    if finite_machine and (not prerequisites or two_observations or multi_product):
        raise ValueError("Finite-machine compilation requires its distinct explicit prerequisite route")
    if multi_product and (not prerequisites or two_observations):
        raise ValueError("Multi-member compilation requires its distinct explicit prerequisite route")
    if two_observations and not prerequisites:
        raise ValueError("Two observations require explicit prerequisite closure")
    raw: JsonValue = {
        "schema_version": FINITE_MACHINE_REQUEST_SCHEMA if finite_machine else MULTI_PRODUCT_REQUEST_SCHEMA if multi_product else TWO_OBSERVATION_REQUEST_SCHEMA if two_observations else PREREQUISITE_REQUEST_SCHEMA if prerequisites else REQUEST_SCHEMA,
        "profile": FINITE_MACHINE_REQUEST_PROFILE if finite_machine else MULTI_PRODUCT_REQUEST_PROFILE if multi_product else TWO_OBSERVATION_REQUEST_PROFILE if two_observations else PREREQUISITE_REQUEST_PROFILE if prerequisites else REQUEST_PROFILE,
        "document": cast(JsonValue, to_data(document)), "definitions": definitions,
        "operating_domain": operating_domain, "implementation_library": implementation_library,
        "catalog_bindings": catalog_bindings, "budgets": budgets,
    }
    return cast(dict[str, JsonValue], decode_json(encode_json(raw)))


def compile(request: JsonValue, *, limits: JsonValue, client: PolicyImplementationClient,
            cancelled: Callable[[], bool] | None = None) -> PolicyImplementationResult:
    return client.compile(request, limits, cancelled=cancelled)


def check(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, client: PolicyImplementationClient,
          cancelled: Callable[[], bool] | None = None) -> PolicyImplementationResult:
    return client.check(request, candidate, limits, cancelled=cancelled)


def replay(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, report: JsonValue,
           client: PolicyImplementationClient,
           cancelled: Callable[[], bool] | None = None) -> PolicyImplementationResult:
    """Replay the complete saved wrapper; external original authority is required."""
    return client.replay(request, candidate, limits, report, cancelled=cancelled)
