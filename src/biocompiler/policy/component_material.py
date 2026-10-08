"""Inert reusable-component requests and fresh native paired publication."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from biocompiler.core_client import JsonValue, decode_json, encode_json
from biocompiler.core_policy_component_material import (
    ACCEPTED_STATUS, REQUEST_PROFILE, REQUEST_SCHEMA, INSTANCE_REQUEST_PROFILE, INSTANCE_REQUEST_SCHEMA, PolicyComponentMaterialClient, PolicyComponentMaterialResult, _original,
    PREREQUISITE_REQUEST_PROFILE, PREREQUISITE_REQUEST_SCHEMA,
    TWO_OBSERVATION_REQUEST_PROFILE, TWO_OBSERVATION_REQUEST_SCHEMA,
)
from .material import _publish_fresh


def prepare_request(*, implementation_request: JsonValue, component_library: JsonValue,
                    composition_rule: JsonValue, catalog_binding: JsonValue, input_bindings: JsonValue,
                    resource_bindings: JsonValue, context: JsonValue, budgets: JsonValue,
                    instanced: bool = False, prerequisites: bool = False,
                    two_observations: bool = False) -> dict[str, JsonValue]:
    """Snapshot all original authority unchanged; perform no semantic admission."""
    if prerequisites and not instanced:
        raise ValueError("Prerequisite closure requires the explicit named-instance profile")
    if two_observations and not (prerequisites and instanced):
        raise ValueError("Two observations require explicit named instances and prerequisite closure")
    request: JsonValue = {"schema_version": TWO_OBSERVATION_REQUEST_SCHEMA if two_observations else PREREQUISITE_REQUEST_SCHEMA if prerequisites else INSTANCE_REQUEST_SCHEMA if instanced else REQUEST_SCHEMA,
        "profile": TWO_OBSERVATION_REQUEST_PROFILE if two_observations else PREREQUISITE_REQUEST_PROFILE if prerequisites else INSTANCE_REQUEST_PROFILE if instanced else REQUEST_PROFILE,
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
