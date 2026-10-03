"""Bounded evidence dependency declarations, never biological endorsements.

External record pins and their declared uses are inspectable metadata. This
profile does not retrieve those records, review publications, execute models or
infer applicability from a source experiment to a human immune deployment.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

from biocompiler.artifacts.manifest import _hash
from biocompiler.ir.circuit_construction import CircuitConstructionRequest
from biocompiler.ir.circuit_profile import HumanExperimentContext
from biocompiler.ir.molecule_records import (
    DeclarationProvenance,
    _MoleculeRecord,
    _choice,
    _decode_records,
    _optional,
    _records,
    _text,
)
from biocompiler.ir.serialization import require


MAX_EVIDENCE_SOURCES = 64
MAX_EVIDENCE_OBSERVATIONS = 64
SOURCE_USES = MappingProxyType(
    {
        "observation": frozenset({"calibration", "held_out", "unassigned"}),
        "model": frozenset({"prediction"}),
        "reference": frozenset({"reference_only"}),
    }
)


@dataclass(frozen=True)
class CircuitEvidenceObservationBinding(_MoleculeRecord):
    """Name an existing nominal observation within one circuit requirement."""

    requirement_id: str
    observation_id: str
    schema_version: ClassVar[str] = "biocompiler.circuit_evidence_observation.v0.1"

    def __post_init__(self):
        _text(self.requirement_id, "Evidence requirement")
        _text(self.observation_id, "Evidence observation")
        self._check_resources()


@dataclass(frozen=True)
class CircuitEvidenceSource(_MoleculeRecord):
    """Complete *metadata* authority for an externally retained record.

    ``record_fingerprint`` is only a declared pin. No record contents or review
    outcome are inferred from it. A held-out label does not establish independence
    from a calibration dataset, and a model pin supplies no executable adapter.
    Source context remains distinct from the intended circuit target.
    """

    id: str
    kind: str
    version: str
    record_fingerprint: str
    use: str
    source_context: HumanExperimentContext | None
    observations: tuple[CircuitEvidenceObservationBinding, ...]
    provenance: DeclarationProvenance
    population_scope: str = "unknown"
    schema_version: ClassVar[str] = "biocompiler.circuit_evidence_source.v0.1"
    _decoders: ClassVar[dict] = {
        "source_context": _optional(HumanExperimentContext),
        "observations": _decode_records(
            CircuitEvidenceObservationBinding, MAX_EVIDENCE_OBSERVATIONS
        ),
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _text(self.id, "Evidence source identity")
        _text(self.version, "Evidence source version")
        _choice(self.kind, SOURCE_USES, "evidence source kind")
        _choice(self.use, SOURCE_USES[self.kind], "evidence source use")
        _hash(self.record_fingerprint, "External evidence record")
        _choice(
            self.population_scope,
            {"unknown", "single_cell", "mean_population"},
            "declared population scope",
        )
        require(
            self.source_context is None
            or isinstance(self.source_context, HumanExperimentContext),
            "Expected source experiment context or explicit unknown None.",
        )
        if self.source_context is not None:
            object.__setattr__(
                self,
                "source_context",
                HumanExperimentContext.from_dict(self.source_context.to_dict()),
            )
        require(
            isinstance(self.provenance, DeclarationProvenance),
            "Expected evidence declaration provenance.",
        )
        object.__setattr__(
            self,
            "provenance",
            DeclarationProvenance.from_dict(self.provenance.to_dict()),
        )
        require(
            isinstance(self.observations, (tuple, list))
            and len(self.observations) <= MAX_EVIDENCE_OBSERVATIONS
            and all(
                isinstance(item, CircuitEvidenceObservationBinding)
                for item in self.observations
            ),
            "Invalid evidence observation inventory.",
        )
        observations = tuple(
            CircuitEvidenceObservationBinding.from_dict(item.to_dict())
            for item in self.observations
        )
        keys = [(item.requirement_id, item.observation_id) for item in observations]
        require(len(set(keys)) == len(keys), "Duplicate evidence observation binding.")
        require(
            bool(observations) or self.kind == "reference",
            "Observation and model declarations require nominal observation bindings.",
        )
        object.__setattr__(
            self,
            "observations",
            tuple(
                sorted(
                    observations,
                    key=lambda item: (item.requirement_id, item.observation_id),
                )
            ),
        )
        self._check_resources()


@dataclass(frozen=True)
class CircuitEvidenceRequest(_MoleculeRecord):
    """Separately retained current construction and external metadata authority.

    Empty sources are permitted to report missing evidence explicitly. Each
    external descriptor conservatively depends on the entire construction,
    material specification, circuit and declared contexts; selective reuse after
    an edit requires a future evidence applicability implementation.
    """

    construction: CircuitConstructionRequest
    sources: tuple[CircuitEvidenceSource, ...]
    schema_version: ClassVar[str] = "biocompiler.circuit_evidence_request.v0.1"
    _decoders: ClassVar[dict] = {
        "construction": CircuitConstructionRequest.from_dict,
        "sources": _decode_records(CircuitEvidenceSource, MAX_EVIDENCE_SOURCES),
    }

    def __post_init__(self):
        require(
            isinstance(self.construction, CircuitConstructionRequest),
            "Evidence dependencies require complete independent construction authority.",
        )
        object.__setattr__(
            self,
            "construction",
            CircuitConstructionRequest.from_dict(self.construction.to_dict()),
        )
        object.__setattr__(
            self,
            "sources",
            _records(
                self.sources,
                CircuitEvidenceSource,
                MAX_EVIDENCE_SOURCES,
                "evidence sources",
            ),
        )
        observations = {
            (requirement.id, observation.id)
            for requirement in self.construction.circuit.requirements
            for observation in (
                *requirement.behavior.inputs,
                requirement.behavior.output.observation,
            )
        }
        for source in self.sources:
            require(
                all(
                    (item.requirement_id, item.observation_id) in observations
                    for item in source.observations
                ),
                "Evidence source names an absent requirement or nominal observation.",
            )
        self._check_resources()


@dataclass(frozen=True)
class CircuitEvidenceSourceReceipt(_MoleculeRecord):
    id: str
    source_fingerprint: str
    schema_version: ClassVar[str] = "biocompiler.circuit_evidence_source_receipt.v0.1"

    def __post_init__(self):
        _text(self.id, "Evidence source receipt identity")
        _hash(self.source_fingerprint, "Evidence source declaration")
        self._check_resources()


@dataclass(frozen=True)
class CircuitEvidenceReceipt(_MoleculeRecord):
    """Historical dependency snapshot, not evidence or a successful check."""

    circuit_fingerprint: str
    construction_fingerprint: str
    material_fingerprint: str
    context_fingerprint: str
    sources: tuple[CircuitEvidenceSourceReceipt, ...]
    schema_version: ClassVar[str] = "biocompiler.circuit_evidence_receipt.v0.1"
    _decoders: ClassVar[dict] = {
        "sources": _decode_records(CircuitEvidenceSourceReceipt, MAX_EVIDENCE_SOURCES)
    }

    def __post_init__(self):
        for key in ("circuit", "construction", "material", "context"):
            _hash(getattr(self, key + "_fingerprint"), "Evidence " + key)
        object.__setattr__(
            self,
            "sources",
            _records(
                self.sources,
                CircuitEvidenceSourceReceipt,
                MAX_EVIDENCE_SOURCES,
                "evidence source receipts",
            ),
        )
        self._check_resources()
