"""Supplied nominal correspondence to a complete circuit construction.

Bindings name existing source declarations and existing final construction roles.
They never infer molecular entity equivalence from an alphabet, a feature or a
role label. The complete source request remains inside construction authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.ir.circuit_construction import CircuitConstructionRequest
from biocompiler.ir.circuit_intent import MAX_PROVIDERS, MAX_REQUIREMENTS
from biocompiler.ir.circuit_logic import MAX_BOOLEAN_INPUTS
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
from biocompiler.semantics.molecule_coordinates import CoordinatePath


MAX_CIRCUIT_BINDINGS = MAX_REQUIREMENTS * (MAX_BOOLEAN_INPUTS + MAX_PROVIDERS + 1)
MAX_BINDING_ASSUMPTIONS = 32
SUBJECT_KINDS = frozenset(
    {
        "DNA",
        "RNA",
        "protein",
        "dna_duplex",
        "rna_complex",
        "protein_complex",
        "external",
    }
)


def _binding_assumptions(values):
    require(
        isinstance(values, (tuple, list)) and len(values) <= MAX_BINDING_ASSUMPTIONS,
        "Invalid binding assumption inventory.",
    )
    for value in values:
        _text(value, "Explicit binding assumption")
    require(len(set(values)) == len(values), "Duplicate binding assumptions.")
    return tuple(sorted(values))


@dataclass(frozen=True)
class CircuitEntityBinding(_MoleculeRecord):
    """A declared association, not proof that the named entity exists or functions.

    Source IDs are scoped by circuit requirement and source kind. The role ID
    must occur in the nominated construction requirement. Optional coordinates
    must exactly repeat a nominated final feature, in its final output frame;
    unknown feature coordinates remain explicit ``None``.
    """

    id: str
    requirement_id: str
    source_kind: str
    source_id: str
    construction_requirement_id: str
    role_id: str
    subject_kind: str
    provenance: DeclarationProvenance
    feature_id: str | None = None
    path: CoordinatePath | None = None
    schema_version: ClassVar[str] = "biocompiler.circuit_entity_binding.v0.1"
    _decoders: ClassVar[dict] = {
        "provenance": DeclarationProvenance.from_dict,
        "path": _optional(CoordinatePath),
    }

    def __post_init__(self):
        for key in (
            "id",
            "requirement_id",
            "source_id",
            "construction_requirement_id",
            "role_id",
        ):
            _text(getattr(self, key), key)
        _choice(
            self.source_kind,
            {"input_observation", "output_product", "provider"},
            "binding source kind",
        )
        _choice(self.subject_kind, SUBJECT_KINDS, "binding subject kind")
        require(
            isinstance(self.provenance, DeclarationProvenance),
            "A binding requires explicit declaration provenance.",
        )
        if self.feature_id is not None:
            _text(self.feature_id, "Binding feature identity")
        require(
            self.path is None or isinstance(self.path, CoordinatePath),
            "Binding coordinates must be a typed path or explicit unknown.",
        )
        require(
            self.path is None or self.feature_id is not None,
            "Binding coordinates require an explicit feature identity.",
        )
        require(
            self.feature_id is None or self.subject_kind in {"DNA", "RNA", "protein"},
            "Features belong to covalent final members, not complexes or external providers.",
        )
        self._check_resources()

    @property
    def source_key(self):
        return self.requirement_id, self.source_kind, self.source_id


@dataclass(frozen=True)
class CircuitBindingRequest(_MoleculeRecord):
    """Independent complete construction and nominal binding authority.

    Partial or inconsistent inventories are representable for diagnostics. Only
    fresh checking can establish complete nominal correspondence; neither this
    record nor a saved assessment grants molecular implementation authority.
    """

    id: str
    construction: CircuitConstructionRequest
    bindings: tuple[CircuitEntityBinding, ...]
    assumptions: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.circuit_binding_request.v0.1"
    _decoders: ClassVar[dict] = {
        "construction": CircuitConstructionRequest.from_dict,
        "bindings": _decode_records(CircuitEntityBinding, MAX_CIRCUIT_BINDINGS),
    }

    def __post_init__(self):
        _text(self.id, "Circuit binding authority identity")
        require(
            isinstance(self.construction, CircuitConstructionRequest),
            "Bindings require complete independent construction authority.",
        )
        object.__setattr__(
            self,
            "construction",
            CircuitConstructionRequest.from_dict(self.construction.to_dict()),
        )
        object.__setattr__(
            self,
            "bindings",
            _records(
                self.bindings,
                CircuitEntityBinding,
                MAX_CIRCUIT_BINDINGS,
                "circuit bindings",
            ),
        )
        object.__setattr__(self, "assumptions", _binding_assumptions(self.assumptions))
        self._check_resources()
