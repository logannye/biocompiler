"""Inert request assembly and explicit native implementation routing only."""
from __future__ import annotations

from typing import Callable, cast

from biocompiler.core_client import JsonValue, decode_json, encode_json
from biocompiler.core_policy_implementation import (
    REQUEST_PROFILE, REQUEST_SCHEMA, PolicyImplementationClient, PolicyImplementationResult,
)
from .model import BuildRequest
from .serialization import to_data


def prepare_request(document: BuildRequest, *, definitions: JsonValue, operating_domain: JsonValue,
                    implementation_library: JsonValue, catalog_bindings: JsonValue,
                    budgets: JsonValue) -> dict[str, JsonValue]:
    """Freeze complete caller-supplied authority; this performs no admission."""
    if type(document) is not BuildRequest:
        raise TypeError("Implementation authority requires an original frozen BuildRequest")
    raw: JsonValue = {
        "schema_version": REQUEST_SCHEMA, "profile": REQUEST_PROFILE,
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
