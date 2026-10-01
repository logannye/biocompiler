"""Authority and results for contract-conditional payload translation.

The request contains original source and supplied implementations. A build is a
historical candidate, never its own verification authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar, TYPE_CHECKING

from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.artifacts.manifest import _hash
from biocompiler.ir.circuit_intent import CircuitRequest
from biocompiler.ir.mechanism import MechanismProgram
from biocompiler.ir.molecule_records import _MoleculeRecord, _text
from biocompiler.ir.serialization import names, require

if TYPE_CHECKING:
    from biocompiler.ir.payload_contracts import PayloadContractLibrary
    from biocompiler.semantics.payload_requirements import PayloadRequirements


def _mapping(value):
    require(isinstance(value, Mapping) and len(value) <= 256, "Invalid payload bindings.")
    for key, item in value.items():
        _text(key, "Binding identity")
        _text(item, "Binding target")
    return MappingProxyType(dict(sorted(value.items())))


@dataclass(frozen=True)
class PayloadCircuitBinding(_MoleculeRecord):
    requirement_id: str
    rule_id: str
    action_id: str
    signals: Mapping[str, str]
    schema_version: ClassVar[str] = "biocompiler.payload_circuit_binding.v0.1"

    def __post_init__(self):
        for key in ("requirement_id", "rule_id", "action_id"):
            _text(getattr(self, key), key)
        object.__setattr__(self, "signals", _mapping(self.signals))


@dataclass(frozen=True)
class PayloadSelectionConstraints(_MoleculeRecord):
    max_combinations: int = 256
    max_total_bases: int | None = None
    preferred_contract_ids: tuple[str, ...] = ()
    require_complete: bool = False
    schema_version: ClassVar[str] = "biocompiler.payload_selection_constraints.v0.1"

    def __post_init__(self):
        require(type(self.max_combinations) is int and 1 <= self.max_combinations <= 4096,
                "Search budget must be between 1 and 4096 combinations.")
        require(self.max_total_bases is None or
                (type(self.max_total_bases) is int and 0 <= self.max_total_bases <= 1_000_000),
                "Invalid complete molecule nucleotide budget.")
        object.__setattr__(self, "preferred_contract_ids",
                           names(self.preferred_contract_ids, "Preferred contracts"))
        require(type(self.require_complete) is bool, "Completeness must be Boolean.")


def _library(data):
    from biocompiler.ir.payload_contracts import PayloadContractLibrary
    return PayloadContractLibrary.from_dict(data)


@dataclass(frozen=True)
class PayloadCompilationRequest(_MoleculeRecord):
    id: str
    circuit: CircuitRequest
    library: PayloadContractLibrary
    circuit_bindings: tuple[PayloadCircuitBinding, ...] = ()
    constraints: PayloadSelectionConstraints = PayloadSelectionConstraints()
    schema_version: ClassVar[str] = "biocompiler.payload_compilation_request.v0.1"
    _decoders: ClassVar[dict] = {
        "circuit": CircuitRequest.from_dict,
        "library": _library,
        "circuit_bindings": lambda items: tuple(PayloadCircuitBinding.from_dict(x) for x in items),
        "constraints": PayloadSelectionConstraints.from_dict,
    }

    def __post_init__(self):
        from biocompiler.ir.payload_contracts import PayloadContractLibrary
        from biocompiler.semantics.context import HumanTargetContext, PayloadFormat
        _text(self.id, "Payload compilation identity")
        require(isinstance(self.circuit, CircuitRequest) and
                self.circuit.profile.source_request is not None,
                "Payload compilation requires the full original human source request.")
        require(self.circuit.profile.purpose == "human_immune_payload" and
                isinstance(self.circuit.profile.target, HumanTargetContext) and
                self.circuit.profile.molecular_form is PayloadFormat.RNA and
                self.circuit.profile.target.payload_format is PayloadFormat.RNA,
                "Executable payload compilation targets human in-vivo immune-cell RNA only.")
        require(isinstance(self.library, PayloadContractLibrary), "Expected supplied payload contracts.")
        require(isinstance(self.constraints, PayloadSelectionConstraints), "Expected typed selection constraints.")
        require(isinstance(self.circuit_bindings, (tuple, list)) and
                len(self.circuit_bindings) <= 32 and
                all(isinstance(x, PayloadCircuitBinding) for x in self.circuit_bindings),
                "Invalid source-to-circuit bindings.")
        require(len({x.requirement_id for x in self.circuit_bindings}) == len(self.circuit_bindings),
                "Circuit requirements must be bound at most once.")
        require({x.requirement_id for x in self.circuit_bindings} <=
                {x.id for x in self.circuit.requirements}, "Unknown circuit requirement binding.")
        object.__setattr__(self, "circuit_bindings", tuple(sorted(self.circuit_bindings, key=lambda x: x.requirement_id)))
        self._check_resources()

    @property
    def source(self):
        return self.circuit.profile.source_request


@dataclass(frozen=True)
class PayloadAlternative(_MoleculeRecord):
    selections: Mapping[str, str]
    reasons: tuple[str, ...]
    schema_version: ClassVar[str] = "biocompiler.payload_alternative.v0.1"

    def __post_init__(self):
        object.__setattr__(self, "selections", _mapping(self.selections))
        object.__setattr__(self, "reasons", names(self.reasons, "Alternative reasons"))

    @property
    def eligible(self):
        return not self.reasons


def _requirements(data):
    from biocompiler.semantics.payload_requirements import PayloadRequirements
    return PayloadRequirements.from_dict(data)


@dataclass(frozen=True)
class PayloadBuild(_MoleculeRecord):
    request_fingerprint: str
    requirements: PayloadRequirements
    selected: Mapping[str, str]
    mechanism: MechanismProgram | None
    construction: CircuitConstructionBuild | None
    alternatives: tuple[PayloadAlternative, ...]
    diagnostics: tuple[str, ...]
    assumptions: tuple[str, ...]
    status: str
    schema_version: ClassVar[str] = "biocompiler.payload_build.v0.1"
    _decoders: ClassVar[dict] = {
        "requirements": _requirements,
        "mechanism": lambda x: MechanismProgram.from_dict(x) if x is not None else None,
        "construction": lambda x: CircuitConstructionBuild.from_dict(x) if x is not None else None,
        "alternatives": lambda items: tuple(PayloadAlternative.from_dict(x) for x in items),
    }

    def __post_init__(self):
        from biocompiler.semantics.payload_requirements import PayloadRequirements
        _hash(self.request_fingerprint, "Payload request authority")
        require(isinstance(self.requirements, PayloadRequirements), "Expected retained source requirements.")
        object.__setattr__(self, "selected", _mapping(self.selected))
        require(self.mechanism is None or isinstance(self.mechanism, MechanismProgram), "Invalid mechanism.")
        require(self.construction is None or isinstance(self.construction, CircuitConstructionBuild), "Invalid construction.")
        require(isinstance(self.alternatives, (tuple, list)) and len(self.alternatives) <= 16384 and
                all(isinstance(x, PayloadAlternative) for x in self.alternatives), "Invalid bounded search record.")
        object.__setattr__(self, "alternatives", tuple(self.alternatives))
        for key in ("diagnostics", "assumptions"):
            object.__setattr__(self, key, names(getattr(self, key), key))
        require(self.status in {"compiled", "partial", "unsupported", "no_solution", "search_exhausted"},
                "Invalid payload compilation status.")
        require((self.status in {"compiled", "partial"}) ==
                bool(self.selected and self.mechanism is not None and self.construction is not None),
                "Payload status and selected artifacts disagree.")

    @property
    def molecules(self):
        return None if self.construction is None else self.construction.candidate.bundle
