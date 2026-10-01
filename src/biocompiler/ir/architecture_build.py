"""Complete authority, plans and diagnostic ledgers for RNA architecture search."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.artifacts.manifest import _hash
from biocompiler.ir.circuit_intent import CircuitRequest
from biocompiler.ir.intent import freeze_json
from biocompiler.ir.molecule_records import _MoleculeRecord, _decode_records, _text
from biocompiler.ir.payload_architecture import (
    MAX_ARCHITECTURE_RECORDS, PayloadArchitectureLibrary, RNAArchitectureConstraints, _names,
)
from biocompiler.ir.serialization import require


# The ledger preserves every prefilter rejection in addition to every examined
# search combination; neither class may silently consume the other's budget.
MAX_ARCHITECTURE_ALTERNATIVES = 4096 + MAX_ARCHITECTURE_RECORDS


@dataclass(frozen=True)
class ArchitectureGap(_MoleculeRecord):
    category: str
    code: str
    requirement_ids: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    message: str
    conflict_set: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.architecture_gap.v0.1"

    def __post_init__(self):
        require(self.category in {
            "unsupported_semantics", "missing_implementation", "incompatible_composition",
            "contradictory_requirements", "missing_sequence_authority",
            "search_budget_exhausted", "independent_verification_failure",
        }, "Unknown architecture diagnostic category.")
        for key in ("code", "message"):
            _text(getattr(self, key), key)
        for key in ("requirement_ids", "candidate_ids", "conflict_set"):
            object.__setattr__(self, key, _names(getattr(self, key), key))


@dataclass(frozen=True)
class RequirementRealization(_MoleculeRecord):
    id: str
    source_node_ids: tuple[str, ...]
    refinement_ids: tuple[str, ...]
    status: str
    assumptions: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.requirement_realization.v0.1"

    def __post_init__(self):
        _text(self.id, "Requirement identity")
        require(self.status in {"implemented", "unresolved"}, "Unknown requirement status.")
        for key in ("source_node_ids", "refinement_ids", "assumptions", "reasons"):
            object.__setattr__(self, key, _names(getattr(self, key), key))
        require(self.status != "implemented" or bool(self.refinement_ids),
                "Implemented source requirements need supplied realizations.")


def _json_records(values, label):
    require(isinstance(values, (tuple, list)) and len(values) <= 4096
            and all(isinstance(item, Mapping) for item in values), f"Invalid {label} inventory.")
    return tuple(freeze_json(item) for item in values)


@dataclass(frozen=True)
class PayloadArchitecturePlan(_MoleculeRecord):
    selected_refinement_ids: tuple[str, ...]
    ledger: tuple[RequirementRealization, ...]
    placements: tuple[Mapping, ...]
    helpers: tuple[Mapping, ...]
    channels: tuple[Mapping, ...]
    control_domains: tuple[Mapping, ...]
    assumptions: tuple[str, ...]
    schema_version: ClassVar[str] = "biocompiler.payload_architecture_plan.v0.1"
    _decoders: ClassVar[dict] = {"ledger": _decode_records(RequirementRealization, 8192)}

    def __post_init__(self):
        object.__setattr__(self, "selected_refinement_ids", _names(
            self.selected_refinement_ids, "selected refinements", nonempty=True, maximum=256))
        require(isinstance(self.ledger, (tuple, list)) and len(self.ledger) <= 8192
                and all(isinstance(item, RequirementRealization) for item in self.ledger),
                "Invalid architecture requirement ledger.")
        require(len({item.id for item in self.ledger}) == len(self.ledger), "Duplicate ledger requirements.")
        object.__setattr__(self, "ledger", tuple(self.ledger))
        for key in ("placements", "helpers", "channels", "control_domains"):
            object.__setattr__(self, key, _json_records(getattr(self, key), key))
        object.__setattr__(self, "assumptions", _names(self.assumptions, "architecture assumptions"))


@dataclass(frozen=True)
class ArchitectureAlternative(_MoleculeRecord):
    refinement_ids: tuple[str, ...]
    gaps: tuple[ArchitectureGap, ...]
    schema_version: ClassVar[str] = "biocompiler.architecture_alternative.v0.1"
    _decoders: ClassVar[dict] = {"gaps": _decode_records(ArchitectureGap, 4096)}

    def __post_init__(self):
        object.__setattr__(self, "refinement_ids", _names(self.refinement_ids, "alternative refinements"))
        require(isinstance(self.gaps, (tuple, list)) and len(self.gaps) <= 4096
                and all(isinstance(item, ArchitectureGap) for item in self.gaps), "Invalid alternative gaps.")
        object.__setattr__(self, "gaps", tuple(self.gaps))

    @property
    def eligible(self):
        return not self.gaps


@dataclass(frozen=True)
class PayloadArchitectureRequest(_MoleculeRecord):
    id: str
    circuit: CircuitRequest
    library: PayloadArchitectureLibrary
    constraints: RNAArchitectureConstraints = RNAArchitectureConstraints()
    schema_version: ClassVar[str] = "biocompiler.payload_architecture_request.v0.1"
    _decoders: ClassVar[dict] = {
        "circuit": CircuitRequest.from_dict,
        "library": PayloadArchitectureLibrary.from_dict,
        "constraints": RNAArchitectureConstraints.from_dict,
    }

    def __post_init__(self):
        from biocompiler.semantics.context import HumanTargetContext, PayloadFormat
        _text(self.id, "Architecture request identity")
        require(isinstance(self.circuit, CircuitRequest)
                and self.circuit.profile.source_request is not None,
                "Architecture compilation requires complete original source authority.")
        profile = self.circuit.profile
        require(profile.purpose == "human_immune_payload" and isinstance(profile.target, HumanTargetContext)
                and profile.molecular_form is PayloadFormat.RNA and profile.target.payload_format is PayloadFormat.RNA,
                "Architecture compilation targets human in-vivo immune-cell RNA only.")
        require(isinstance(self.library, PayloadArchitectureLibrary)
                and isinstance(self.constraints, RNAArchitectureConstraints), "Invalid architecture authority.")
        self._check_resources()

    @property
    def source(self):
        return self.circuit.profile.source_request


def _execution(data):
    from biocompiler.semantics.payload_execution import SourceExecutionManifest
    return SourceExecutionManifest.from_dict(data)


@dataclass(frozen=True)
class PayloadArchitectureBuild(_MoleculeRecord):
    request_fingerprint: str
    execution: object
    plan: PayloadArchitecturePlan | None
    construction: CircuitConstructionBuild | None
    alternatives: tuple[ArchitectureAlternative, ...]
    diagnostics: tuple[ArchitectureGap, ...]
    status: str
    schema_version: ClassVar[str] = "biocompiler.payload_architecture_build.v0.1"
    _decoders: ClassVar[dict] = {
        "execution": _execution,
        "plan": lambda data: PayloadArchitecturePlan.from_dict(data) if data is not None else None,
        "construction": lambda data: CircuitConstructionBuild.from_dict(data) if data is not None else None,
        "alternatives": _decode_records(ArchitectureAlternative, MAX_ARCHITECTURE_ALTERNATIVES),
        "diagnostics": _decode_records(ArchitectureGap, 4096),
    }

    def __post_init__(self):
        from biocompiler.semantics.payload_execution import SourceExecutionManifest
        _hash(self.request_fingerprint, "Complete architecture request")
        require(isinstance(self.execution, SourceExecutionManifest), "Expected retained executable source authority.")
        require(self.plan is None or isinstance(self.plan, PayloadArchitecturePlan), "Invalid architecture plan.")
        require(self.construction is None or isinstance(self.construction, CircuitConstructionBuild),
                "Invalid complete construction.")
        for key, cls in (("alternatives", ArchitectureAlternative), ("diagnostics", ArchitectureGap)):
            maximum = MAX_ARCHITECTURE_ALTERNATIVES if key == "alternatives" else 4096
            require(isinstance(getattr(self, key), (tuple, list)) and len(getattr(self, key)) <= maximum
                    and all(isinstance(item, cls) for item in getattr(self, key)), f"Invalid {key}.")
            object.__setattr__(self, key, tuple(getattr(self, key)))
        require(self.status in {"compiled", "partial", "unsupported", "no_solution", "search_exhausted"},
                "Unknown architecture build status.")
        require((self.status in {"compiled", "partial"}) == (self.plan is not None and self.construction is not None),
                "Architecture status and retained construction disagree.")

    @property
    def molecules(self):
        return None if self.construction is None else self.construction.candidate.bundle


@dataclass(frozen=True)
class PayloadArchitectureExport(_MoleculeRecord):
    fasta: str
    manifest: Mapping
    schema_version: ClassVar[str] = "biocompiler.payload_architecture_export.v0.1"

    def __post_init__(self):
        require(isinstance(self.fasta, str) and self.fasta.startswith(">"), "Export needs RNA FASTA.")
        require(isinstance(self.manifest, Mapping), "FASTA export requires its complete companion manifest.")
        object.__setattr__(self, "manifest", freeze_json(self.manifest))
