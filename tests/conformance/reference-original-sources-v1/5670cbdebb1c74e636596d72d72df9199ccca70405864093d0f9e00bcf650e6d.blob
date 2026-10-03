"""One frozen authority for required behavior, prohibitions and deployment."""

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.compiler.deployment import HumanDeploymentRequest
from biocompiler.compiler.request import _strict_import
from biocompiler.ir.serialization import JsonArtifact, fields, fingerprint, require
from biocompiler.semantics.acceptance import HumanAcceptanceContract


@dataclass(frozen=True)
class HumanAcceptanceRequest(JsonArtifact):
    deployment_request: HumanDeploymentRequest
    acceptance: HumanAcceptanceContract
    schema_version: ClassVar[str] = "biocompiler.human_acceptance_request.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.deployment_request, HumanDeploymentRequest),
            "Expected frozen human deployment authority.",
        )
        require(
            isinstance(self.acceptance, HumanAcceptanceContract),
            "Expected HumanAcceptanceContract.",
        )
        require(
            self.acceptance.behavior_fingerprint == self.behavior_request.fingerprint,
            "Acceptance binds stale or different required behavior.",
        )
        observation = self.acceptance.healthy_measurement.observable
        behavior = self.behavior_request.contract
        require(
            observation.role == behavior.input_measurement.observable.role
            and observation.compartment in self.target.compartments
            and observation.compartment != "abstract",
            "Healthy context must bind the same recipient in a declared physical compartment.",
        )
        require(
            observation.id
            not in {
                behavior.input_measurement.observable.id,
                behavior.output_measurement.observable.id,
            },
            "Context classification must be a distinct observation endpoint.",
        )
        require(
            behavior.response.inactive_range.lower.canonical_value
            <= self.acceptance.background_ceiling.canonical_value
            <= behavior.response.inactive_range.upper.canonical_value,
            "Background ceiling must refine the required inactive range.",
        )
        require(
            self.acceptance.peak_ceiling.canonical_value
            >= behavior.response.active_range.lower.canonical_value,
            "Peak ceiling conflicts with all required active rates.",
        )
        for delay in (
            self.acceptance.input_availability.response_delay,
            self.acceptance.shutdown.response_delay,
        ):
            require(
                delay.canonical_value < behavior.horizon.canonical_value,
                "Recovery/control deadline must be exercisable within the horizon.",
            )
        evidence = {item.id for item in self.target.human_target.evidence}
        for path, claim in self.acceptance.claims:
            require(
                set(claim.evidence_ids) <= evidence,
                f"Unknown acceptance evidence reference in {path}.",
            )

    @property
    def behavior_request(self):
        return self.deployment_request.behavior_request

    @property
    def build_request(self):
        return self.deployment_request.build_request

    @property
    def target(self):
        return self.deployment_request.target

    @property
    def fingerprint(self):
        return fingerprint(
            {
                "schema_version": self.schema_version,
                "deployment_request": self.deployment_request.fingerprint,
                "acceptance": self.acceptance.fingerprint,
            }
        )

    @property
    def artifact_fingerprint(self):
        return fingerprint(self.to_dict())

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "deployment_request": self.deployment_request.to_dict(),
            "acceptance": self.acceptance.to_dict(),
        }

    @classmethod
    @_strict_import
    def from_dict(cls, data):
        fields(
            data, {"schema_version", "deployment_request", "acceptance"}, cls.__name__
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported human acceptance request schema.",
        )
        return cls(
            HumanDeploymentRequest.from_dict(data["deployment_request"]),
            HumanAcceptanceContract.from_dict(data["acceptance"]),
        )
