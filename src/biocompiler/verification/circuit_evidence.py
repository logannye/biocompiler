"""Replay structural checks and compare evidence metadata against current authority.

This checker imports no assembler, compiler or model runner. It does not trust
historical construction labels and never maps identity agreement to empirical
validation, publication fidelity, predictive support or human admission.
"""

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.artifacts.circuit_molecules import CircuitMoleculeRecord
from biocompiler.artifacts.manifest import _hash
from biocompiler.ir.circuit_evidence import (
    CircuitEvidenceReceipt,
    CircuitEvidenceRequest,
    CircuitEvidenceSourceReceipt,
    MAX_EVIDENCE_SOURCES,
)
from biocompiler.ir.molecule_records import (
    _MoleculeRecord,
    _choice,
    _decode_records,
    _records,
    _text,
)
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.verification.circuit_construction import (
    verify_circuit_construction_assessment,
)


CHECKER_VERSION = "biocompiler.circuit_evidence_checker.v0.1"
CLAIM_SCOPE = (
    "Current construction and declared evidence dependency identities only; "
    "external contents, review, model predictions, evidence applicability and "
    "human use remain unassessed."
)


@dataclass(frozen=True)
class CircuitEvidenceDependencyStatus(_MoleculeRecord):
    id: str
    recorded_fingerprint: str | None
    current_fingerprint: str | None
    schema_version: ClassVar[str] = (
        "biocompiler.circuit_evidence_dependency_status.v0.1"
    )

    def __post_init__(self):
        _text(self.id, "Evidence dependency identity", maximum=4120)
        require(
            self.id in {"circuit", "construction", "material", "context"}
            or (self.id.startswith("source:") and len(self.id) > len("source:")),
            "Unknown evidence dependency category.",
        )
        for value in (self.recorded_fingerprint, self.current_fingerprint):
            if value is not None:
                _hash(value, "Evidence dependency")
        require(
            self.recorded_fingerprint is not None
            or self.current_fingerprint is not None,
            "A dependency comparison needs at least one identity.",
        )
        self._check_resources()

    @property
    def status(self):
        if self.current_fingerprint is None:
            return "missing_current"
        if self.recorded_fingerprint is None:
            return "missing_receipt"
        return (
            "current"
            if self.recorded_fingerprint == self.current_fingerprint
            else "stale"
        )


@dataclass(frozen=True)
class CircuitEvidenceAssessment(_MoleculeRecord):
    receipt_fingerprint: str
    request_fingerprint: str
    build_fingerprint: str
    construction_status: str
    dependencies: tuple[CircuitEvidenceDependencyStatus, ...]
    missing_evidence: bool
    checker_version: str = CHECKER_VERSION
    claim_scope: str = CLAIM_SCOPE
    prediction: str = "unsupported"
    empirical_validation: str = "unknown"
    evidence_applicability: str = "unassessed"
    human_therapeutic_admission: str = "not_admitted"
    schema_version: ClassVar[str] = "biocompiler.circuit_evidence_assessment.v0.1"
    _decoders: ClassVar[dict] = {
        "dependencies": _decode_records(
            CircuitEvidenceDependencyStatus, MAX_EVIDENCE_SOURCES * 2 + 4
        )
    }

    def __post_init__(self):
        for key in ("receipt_fingerprint", "request_fingerprint", "build_fingerprint"):
            _hash(getattr(self, key), key)
        _choice(
            self.construction_status,
            {"checked_complete", "unsupported"},
            "construction evidence status",
        )
        require(
            type(self.missing_evidence) is bool, "Missing evidence must be Boolean."
        )
        object.__setattr__(
            self,
            "dependencies",
            _records(
                self.dependencies,
                CircuitEvidenceDependencyStatus,
                MAX_EVIDENCE_SOURCES * 2 + 4,
                "evidence dependencies",
            ),
        )
        require(
            self.construction_status == "checked_complete" or not self.dependencies,
            "Unsupported construction cannot claim current dependency identities.",
        )
        if self.construction_status == "checked_complete":
            require(
                {"circuit", "construction", "material", "context"}
                <= {item.id for item in self.dependencies},
                "A checked evidence snapshot needs every core dependency.",
            )
            require(
                self.missing_evidence
                == (
                    not any(
                        item.id.startswith("source:")
                        and item.current_fingerprint is not None
                        for item in self.dependencies
                    )
                ),
                "Missing evidence flag disagrees with current source inventory.",
            )
        for key, value in {
            "checker_version": CHECKER_VERSION,
            "claim_scope": CLAIM_SCOPE,
            "prediction": "unsupported",
            "empirical_validation": "unknown",
            "evidence_applicability": "unassessed",
            "human_therapeutic_admission": "not_admitted",
        }.items():
            require(
                getattr(self, key) == value,
                "Evidence identity checks cannot broaden their claim scope.",
            )
        self._check_resources()

    @property
    def freshness(self):
        if self.construction_status == "unsupported":
            return "unsupported"
        if self.missing_evidence or any(
            item.status.startswith("missing_") for item in self.dependencies
        ):
            return "missing"
        if any(item.status == "stale" for item in self.dependencies):
            return "stale"
        return "current"


def _context_identity(circuit):
    profile = circuit.profile
    return fingerprint(
        {
            "target": None if profile.target is None else profile.target.to_dict(),
            "recipient": None
            if profile.recipient is None
            else profile.recipient.to_dict(),
            "source_experiment": None
            if profile.source_experiment is None
            else profile.source_experiment.to_dict(),
            "deployment_id": circuit.deployment_id,
            "purpose": profile.purpose,
            "mode": profile.mode,
        }
    )


def _current_authority(build, expected_request):
    require(
        isinstance(build, CircuitConstructionBuild),
        "Expected a current circuit construction build.",
    )
    require(
        isinstance(expected_request, CircuitEvidenceRequest),
        "Expected complete independent circuit evidence authority.",
    )
    build = CircuitConstructionBuild.from_dict(build.to_dict())
    expected = CircuitEvidenceRequest.from_dict(expected_request.to_dict())
    require(
        build.request.fingerprint == expected.construction.fingerprint
        and build.request.to_dict() == expected.construction.to_dict(),
        "Current construction differs from independent evidence authority.",
    )
    assessment = verify_circuit_construction_assessment(
        build.assessment, build.candidate, expected_request=expected.construction
    )
    complete = (
        expected.construction.mode == "strict"
        and assessment.passed
        and assessment.complete
        and build.candidate.bundle is not None
        and not build.candidate.missing_members
    )
    return build, expected, complete


def capture_circuit_evidence(build, *, expected_request):
    """Capture metadata after fresh strict construction checks, granting no evidence."""
    build, expected, complete = _current_authority(build, expected_request)
    require(
        complete,
        "Evidence capture requires a freshly checked complete strict construction.",
    )
    material = CircuitMoleculeRecord(
        build.candidate.bundle, build.candidate.experimental_amounts, {}
    )
    return CircuitEvidenceReceipt(
        expected.construction.circuit.fingerprint,
        expected.construction.fingerprint,
        material.experimental_specification_identity,
        _context_identity(expected.construction.circuit),
        tuple(
            CircuitEvidenceSourceReceipt(item.id, item.fingerprint)
            for item in expected.sources
        ),
    )


def check_circuit_evidence(receipt, build, *, expected_request):
    """Independently replay construction and compare a historical dependency snapshot.

    Invalid or forged authority fails closed. A valid but incomplete/diagnostic
    build returns explicit unsupported freshness; it cannot become current.
    """
    require(
        isinstance(receipt, CircuitEvidenceReceipt),
        "Expected historical evidence dependency receipt.",
    )
    receipt = CircuitEvidenceReceipt.from_dict(receipt.to_dict())
    build, expected, complete = _current_authority(build, expected_request)
    dependencies = ()
    if complete:
        # Recompute material from the independently replayed current candidate;
        # no receipt or stored PASS supplies expected values.
        material = CircuitMoleculeRecord(
            build.candidate.bundle, build.candidate.experimental_amounts, {}
        )
        current = {
            "circuit": expected.construction.circuit.fingerprint,
            "construction": expected.construction.fingerprint,
            "material": material.experimental_specification_identity,
            "context": _context_identity(expected.construction.circuit),
            **{"source:" + item.id: item.fingerprint for item in expected.sources},
        }
        recorded = {
            key: getattr(receipt, key + "_fingerprint")
            for key in ("circuit", "construction", "material", "context")
        }
        recorded.update(
            {"source:" + item.id: item.source_fingerprint for item in receipt.sources}
        )
        dependencies = tuple(
            CircuitEvidenceDependencyStatus(key, recorded.get(key), current.get(key))
            for key in sorted(recorded.keys() | current.keys())
        )
    return CircuitEvidenceAssessment(
        receipt.fingerprint,
        expected.fingerprint,
        build.fingerprint,
        "checked_complete" if complete else "unsupported",
        dependencies,
        not expected.sources,
    )


def verify_circuit_evidence_assessment(assessment, receipt, build, *, expected_request):
    """Require fresh replay of every field against complete current authority."""
    require(
        isinstance(assessment, CircuitEvidenceAssessment),
        "Expected historical circuit evidence assessment.",
    )
    assessment = CircuitEvidenceAssessment.from_dict(assessment.to_dict())
    current = check_circuit_evidence(receipt, build, expected_request=expected_request)
    require(
        assessment.fingerprint == current.fingerprint
        and assessment.to_dict() == current.to_dict(),
        "Circuit evidence assessment is stale or differs from fresh independent replay.",
    )
    return current
