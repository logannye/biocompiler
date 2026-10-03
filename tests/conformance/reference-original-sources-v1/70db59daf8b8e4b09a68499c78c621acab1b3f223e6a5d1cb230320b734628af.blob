"""Check declared delivery dependencies and timing without certifying delivery."""

from dataclasses import dataclass
from fractions import Fraction
from typing import ClassVar

from biocompiler.compiler.deployment import HumanDeploymentRequest
from biocompiler.ir.serialization import names, require
from biocompiler.semantics.deployment import _DeploymentRecord

CHECKER_VERSION = "biocompiler.deployment_checker.v0.1"


@dataclass(frozen=True)
class DeploymentAssessment(_DeploymentRecord):
    request_fingerprint: str
    compatibility: str
    diagnostics: tuple[str, ...]
    unresolved_evidence: tuple[str, ...]
    schema_version: ClassVar[str] = "biocompiler.deployment_assessment.v0.1"
    _fixed: ClassVar[dict] = {
        "checker": CHECKER_VERSION,
        "scope": "declared_deployment_compatibility_only",
        "biological_applicability": "unestablished",
        "mechanism_selection": "blocked",
    }

    def __post_init__(self):
        require(
            isinstance(self.request_fingerprint, str)
            and len(self.request_fingerprint) == 64
            and set(self.request_fingerprint) <= set("0123456789abcdef"),
            "Invalid deployment request fingerprint.",
        )
        require(
            isinstance(self.compatibility, str)
            and self.compatibility in {"pass", "fail", "unknown", "unsupported"},
            "Unknown deployment compatibility outcome.",
        )
        for key in ("diagnostics", "unresolved_evidence"):
            object.__setattr__(self, key, names(getattr(self, key), key))
        require(
            bool(self.unresolved_evidence),
            "This profile cannot discharge empirical evidence.",
        )
        require(
            (self.compatibility == "pass") == (not self.diagnostics),
            "Compatibility PASS requires no unresolved structural diagnostics.",
        )
        self._utf8()

    def is_current(self, request):
        """Dependency equality only; callers must rerun the checker for acceptance."""
        require(
            isinstance(request, HumanDeploymentRequest),
            "Expected HumanDeploymentRequest.",
        )
        return request.fingerprint == self.request_fingerprint


def check_deployment(request):
    """Independently recheck frozen inputs; co-payload support is never inferred.

    Expression bounds describe independent ranges, not a probability model.
    The latest onset and earliest possible loss must cover the entire behavior
    interval under every combination in those declared ranges.
    """
    require(
        isinstance(request, HumanDeploymentRequest),
        "Expected HumanDeploymentRequest authority.",
    )
    request = HumanDeploymentRequest.from_dict(request.to_dict())
    deployment = request.deployment
    failures, unsupported, unknown = [], [], []
    if (
        deployment.platform.payload_format.value,
        deployment.intracellular_destination,
    ) not in {("RNA", "cytoplasm"), ("DNA", "nucleus")}:
        unsupported.append("deployment_destination_profile_unsupported")
    if deployment.co_payloads:
        unsupported.append("same_cell_co_payload_delivery_unsupported")
    if any(item.domain.kind == "unknown" for item in deployment.exposures):
        unknown.append("deployment_exposure_bounds_unknown")

    timing = deployment.timing
    start = Fraction(str(timing.behavior_start.canonical_value))
    horizon = Fraction(str(request.behavior_request.contract.horizon.canonical_value))
    if timing.onset is None or timing.duration is None:
        unknown.append("expression_window_unknown")
    if timing.onset is not None:
        latest_onset = Fraction(str(timing.onset.upper.canonical_value))
        if latest_onset > start:
            failures.append("expression_onset_after_behavior_start")
    if timing.onset is not None and timing.duration is not None:
        earliest_end = Fraction(str(timing.onset.lower.canonical_value)) + Fraction(
            str(timing.duration.lower.canonical_value)
        )
        if earliest_end < start + horizon:
            failures.append("expression_duration_does_not_cover_behavior")
    compatibility = (
        "fail"
        if failures
        else "unsupported"
        if unsupported
        else "unknown"
        if unknown
        else "pass"
    )
    unresolved = (
        *(f"target.{path}" for path in request.target.human_target.unresolved_evidence),
        *(
            f"behavior.{path}"
            for path in request.behavior_request.contract.unresolved_evidence
        ),
        *(f"deployment.{path}" for path in deployment.unresolved_evidence),
    )
    return DeploymentAssessment(
        request.fingerprint,
        compatibility,
        tuple(failures + unsupported + unknown),
        unresolved,
    )
