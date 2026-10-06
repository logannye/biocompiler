"""Opt-in serialization bridge to explicitly selected native policy operations.

This module supplies no Python operational semantics or implicit backend.
Operational definitions and timelines are declarative JSON supplied by callers.
"""
from __future__ import annotations

from typing import Callable, cast

from biocompiler.core_client import JsonValue
from biocompiler.core_policy_operational import OperationalPolicyClient, OperationalPolicyResult
from .model import BuildRequest, CompilationSubmission, PolicyProgram
from .serialization import to_data

FrozenPolicy = PolicyProgram | BuildRequest | CompilationSubmission


def _document(document: FrozenPolicy) -> JsonValue:
    if type(document) not in (PolicyProgram, BuildRequest, CompilationSubmission):
        raise TypeError("Native policy operations require an original frozen program, request or submission")
    return cast(JsonValue, to_data(document))


def compile(document: FrozenPolicy, *, definitions: JsonValue, client: OperationalPolicyClient,
            cancelled: Callable[[], bool] | None = None) -> OperationalPolicyResult:
    """Lower the supported native subset with independent source correspondence."""
    return client.compile(_document(document), definitions, cancelled=cancelled)


def check_lowering(document: FrozenPolicy, *, definitions: JsonValue, candidate: JsonValue,
                   client: OperationalPolicyClient,
                   cancelled: Callable[[], bool] | None = None) -> OperationalPolicyResult:
    """Check a complete candidate against separately supplied original authority."""
    return client.check_lowering(_document(document), definitions, candidate, cancelled=cancelled)


def execute(document: FrozenPolicy, *, definitions: JsonValue, candidate: JsonValue, timeline: JsonValue,
            client: OperationalPolicyClient,
            cancelled: Callable[[], bool] | None = None) -> OperationalPolicyResult:
    """Check correspondence and execute one explicitly bounded supplied timeline."""
    return client.execute(_document(document), definitions, candidate, timeline, cancelled=cancelled)


def replay(document: FrozenPolicy, *, definitions: JsonValue, candidate: JsonValue, timeline: JsonValue,
           report: JsonValue, client: OperationalPolicyClient,
           cancelled: Callable[[], bool] | None = None) -> OperationalPolicyResult:
    """Freshly reconstruct and compare every retained execution report field."""
    return client.replay(_document(document), definitions, candidate, timeline, report, cancelled=cancelled)
