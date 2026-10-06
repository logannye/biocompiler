"""Opt-in connection from frozen authoring records to a selected native checker.

Import this module explicitly. Ordinary authoring never discovers or starts a
backend, and this bridge never falls back to Python semantic execution.
"""
from __future__ import annotations

from typing import Callable, cast

from biocompiler.core_client import JsonValue
from biocompiler.core_policy import PolicyAssessment, PolicyClient
from .model import BuildRequest, CompilationSubmission, PolicyProgram
from .serialization import to_data


def assess(document: PolicyProgram | BuildRequest | CompilationSubmission, *,
           client: PolicyClient, cancelled: Callable[[], bool] | None = None) -> PolicyAssessment:
    """Submit complete frozen declarations for independent native source analysis."""
    if type(document) not in (PolicyProgram, BuildRequest, CompilationSubmission):
        raise TypeError("Native source assessment requires a frozen program, request or submission")
    return client.assess(cast(JsonValue, to_data(document)), cancelled=cancelled)


def replay(document: PolicyProgram | BuildRequest | CompilationSubmission, *,
           assessment: PolicyAssessment, client: PolicyClient,
           cancelled: Callable[[], bool] | None = None) -> PolicyAssessment:
    """Recheck exact original declarations; a retained assessment is not authority."""
    if type(document) not in (PolicyProgram, BuildRequest, CompilationSubmission):
        raise TypeError("Native replay requires the original frozen program, request or submission")
    return client.replay(expected_document=cast(JsonValue, to_data(document)),
                         assessment=assessment.assessment, cancelled=cancelled)
