"""Freeze delivery authority before any future human mechanism selection."""

from dataclasses import dataclass
from typing import ClassVar

from cellweave.compiler.human_behavior import HumanBehaviorRequest
from cellweave.compiler.request import _strict_import
from cellweave.ir.serialization import JsonArtifact, fields, fingerprint, require
from cellweave.semantics.deployment import DeploymentContract


@dataclass(frozen=True)
class HumanDeploymentRequest(JsonArtifact):
    behavior_request: HumanBehaviorRequest
    deployment: DeploymentContract
    schema_version: ClassVar[str] = "cellweave.human_deployment_request.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.behavior_request, HumanBehaviorRequest),
            "Deployment requires source-authoritative human behavior.",
        )
        require(
            isinstance(self.deployment, DeploymentContract),
            "Expected DeploymentContract.",
        )
        deployment, target = self.deployment, self.target
        require(
            deployment.target_fingerprint == target.fingerprint,
            "Stale or different deployment target identity.",
        )
        require(
            deployment.recipient_role
            == self.behavior_request.contract.input_measurement.observable.role,
            "Delivery must bind the exact behavior recipient role.",
        )
        require(
            deployment.platform.payload_format == target.payload_format,
            "Delivery modality must match the human target.",
        )
        require(
            deployment.intended_population == target.human_target.population_inclusion
            and deployment.excluded_population
            == target.human_target.population_exclusion,
            "Delivery population must retain the target's complete inclusion/exclusion claims.",
        )
        for compartment in (
            deployment.intracellular_destination,
            *(item.compartment for item in deployment.exposures),
            *(item.destination for item in deployment.co_payloads),
        ):
            require(
                compartment in target.compartments and compartment != "abstract",
                "Deployment destinations and exposures require declared physical target compartments.",
            )
        evidence_ids = {item.id for item in target.human_target.evidence}
        for path, claim in deployment.claims:
            require(
                set(claim.evidence_ids) <= evidence_ids,
                f"Unknown deployment evidence reference in {path}.",
            )

    @property
    def build_request(self):
        return self.behavior_request.build_request

    @property
    def target(self):
        return self.behavior_request.target

    @property
    def fingerprint(self):
        return fingerprint(
            {
                "schema_version": self.schema_version,
                "behavior_request": self.behavior_request.fingerprint,
                "deployment": self.deployment.fingerprint,
            }
        )

    @property
    def artifact_fingerprint(self):
        return fingerprint(self.to_dict())

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "behavior_request": self.behavior_request.to_dict(),
            "deployment": self.deployment.to_dict(),
        }

    @classmethod
    @_strict_import
    def from_dict(cls, data):
        fields(data, {"schema_version", "behavior_request", "deployment"}, cls.__name__)
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported human deployment request schema.",
        )
        return cls(
            HumanBehaviorRequest.from_dict(data["behavior_request"]),
            DeploymentContract.from_dict(data["deployment"]),
        )
