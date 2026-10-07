"""Complete supplied-catalog selection and fresh paired native publication."""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable

from biocompiler.core_client import JsonValue, decode_json, encode_json
from biocompiler.core_policy_component_selection import (
    ACCEPTED_STATUS, REQUEST_PROFILE, REQUEST_SCHEMA, PolicyComponentSelectionClient, PolicyComponentSelectionResult, _original,
)
from .material import _publish_fresh


def prepare_request(*, alternatives: JsonValue, predicate: JsonValue, budgets: JsonValue) -> dict[str, JsonValue]:
    """Snapshot complete originals unchanged; supplied budgets are never upgraded."""
    request: JsonValue = {"schema_version": REQUEST_SCHEMA, "profile": REQUEST_PROFILE,
                         "alternatives": alternatives, "predicate": predicate, "budgets": budgets}
    return _original(decode_json(encode_json(request)))


def check(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, client: PolicyComponentSelectionClient,
          cancelled: Callable[[], bool] | None = None) -> PolicyComponentSelectionResult:
    return client.check(request, candidate, limits, cancelled=cancelled)


def replay(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, report: JsonValue,
           client: PolicyComponentSelectionClient, cancelled: Callable[[], bool] | None = None) -> PolicyComponentSelectionResult:
    return client.replay(request, candidate, limits, report, cancelled=cancelled)


def export(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, client: PolicyComponentSelectionClient,
           output: Path, input_paths: Iterable[Path] = (), replace: bool = False,
           cancelled: Callable[[], bool] | None = None) -> PolicyComponentSelectionResult:
    """Fresh complete native check/export before atomic FASTA/manifest publication."""
    return _publish_fresh(lambda: client.export(request, candidate, limits, cancelled=cancelled),
        operation="export-policy-component-selection", status=ACCEPTED_STATUS, output=output,
        input_paths=input_paths, replace=replace, cancelled=cancelled)
