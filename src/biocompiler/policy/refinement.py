"""Explicit fresh named-refinement checking; evidence views grant no capability."""
from __future__ import annotations

from typing import Callable
from biocompiler.core_client import JsonValue
from biocompiler.core_policy_refinement import (
    Stage, Relation, PremiseKind, DerivationRule, StageIdentity, RefinementScope,
    RefinementClaim, RefinementPremise, RefinementDerivation, RefinementEvidence,
    PolicyRefinementResult, PolicyRefinementClient,
)


def check(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, client: PolicyRefinementClient,
          cancelled: Callable[[], bool] | None = None) -> PolicyRefinementResult:
    """Ask the selected native checker to recheck all original material authority."""
    return client.check(request, candidate, limits, cancelled=cancelled)


def replay(request: JsonValue, *, candidate: JsonValue, limits: JsonValue, report: JsonValue,
           client: PolicyRefinementClient, cancelled: Callable[[], bool] | None = None) -> PolicyRefinementResult:
    """Fresh checking plus equality with the entire saved refinement wrapper."""
    return client.replay(request, candidate, limits, report, cancelled=cancelled)


__all__ = ["Stage", "Relation", "PremiseKind", "DerivationRule", "StageIdentity", "RefinementScope", "RefinementClaim",
    "RefinementPremise", "RefinementDerivation", "RefinementEvidence", "PolicyRefinementResult", "PolicyRefinementClient", "check", "replay"]
