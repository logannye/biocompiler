"""Inert reusable-component requests and fresh native paired publication."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from biocompiler.core_client import JsonValue, decode_json, encode_json
from biocompiler.core_policy_component_material import (
    ACCEPTED_STATUS, REQUEST_PROFILE, REQUEST_SCHEMA, PolicyComponentMaterialClient, PolicyComponentMaterialResult, _original,
)
from .material import _publish_fresh


def prepare_request(*, implementation_request: JsonValue, component_library: JsonValue,
                    composition_rule: JsonValue, catalog_binding: JsonValue, input_bindings: JsonValue,
                    resource_bindings: JsonValue, context: JsonValue, budgets: JsonValue) -> dict[str, JsonValue]:
    """Snapshot all original authority unchanged; perform no semantic admission."""
    request: JsonValue = {"schema_version": REQUEST_SCHEMA, "profile": REQUEST_PROFILE,
        "implementation_request": implementation_request, "component_library": component_library,
        "composition_rule": composition_rule, "catalog_binding": catalog_binding, "input_bindings": input_bindings,
        "resource_bindings": resource_bindings, "context": context, "budgets": budgets}
    return _original(decode_json(encode_json(request)))


def compile(request: JsonValue, *, limits: JsonValue, client: PolicyComponentMaterialClient,
            cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
    return client.compile(request, limits, cancelled=cancelled)


def check(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, client: PolicyComponentMaterialClient,
          cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
    return client.check(request, candidate, limits, cancelled=cancelled)


def replay(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, report: JsonValue,
           client: PolicyComponentMaterialClient, cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
    """Replay the complete wrapper against independently supplied current originals."""
    return client.replay(request, candidate, limits, report, cancelled=cancelled)


def export(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, client: PolicyComponentMaterialClient,
           output: Path, input_paths: Iterable[Path] = (), replace: bool = False,
           cancelled: Callable[[], bool] | None = None) -> PolicyComponentMaterialResult:
    """Fresh native check/export followed by exact atomic FASTA/manifest publication."""
    return _publish_fresh(lambda: client.export(request, candidate, limits, cancelled=cancelled),
        operation="export-policy-component-material", status=ACCEPTED_STATUS, output=output,
        input_paths=input_paths, replace=replace, cancelled=cancelled)
