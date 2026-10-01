"""Historical construction records; imported receipts require fresh replay."""

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.artifacts.circuit_construction import ConstructionCandidate
from biocompiler.ir.circuit_construction import CircuitConstructionRequest
from biocompiler.ir.molecule_records import _MoleculeRecord
from biocompiler.ir.serialization import require
from biocompiler.verification.circuit_construction import CircuitConstructionAssessment


@dataclass(frozen=True)
class CircuitConstructionBuild(_MoleculeRecord):
    request: CircuitConstructionRequest
    candidate: ConstructionCandidate
    assessment: CircuitConstructionAssessment
    schema_version: ClassVar[str] = "biocompiler.circuit_construction_build.v0.1"
    _decoders: ClassVar[dict] = {
        "request": CircuitConstructionRequest.from_dict,
        "candidate": ConstructionCandidate.from_dict,
        "assessment": CircuitConstructionAssessment.from_dict,
    }

    def __post_init__(self):
        require(
            isinstance(self.request, CircuitConstructionRequest),
            "Expected frozen construction request.",
        )
        require(
            isinstance(self.candidate, ConstructionCandidate),
            "Expected proposed construction.",
        )
        require(
            isinstance(self.assessment, CircuitConstructionAssessment),
            "Expected historical construction assessment.",
        )
        for key, cls in (
            ("request", CircuitConstructionRequest),
            ("candidate", ConstructionCandidate),
            ("assessment", CircuitConstructionAssessment),
        ):
            object.__setattr__(self, key, cls.from_dict(getattr(self, key).to_dict()))
        require(
            self.request.fingerprint
            == self.candidate.request_fingerprint
            == self.assessment.request_fingerprint,
            "Historical construction authority identities disagree.",
        )
        require(
            self.candidate.fingerprint == self.assessment.candidate_fingerprint,
            "Historical construction candidate identity changed.",
        )
        self._check_resources()
