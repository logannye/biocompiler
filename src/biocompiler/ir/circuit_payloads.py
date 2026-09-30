"""Independently declared required-region inventories for final human payloads.

The four supported modalities establish nominal structural correspondence only.
Neither this inventory nor declared provenance establishes regulatory activity,
independent source-byte review, exact experimental fidelity or human admission.
There is no inferred universal list or ordering of regulatory regions.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

from biocompiler.ir.molecule_records import (
    DeclarationProvenance,
    _MoleculeRecord,
    _choice,
    _decode_records,
    _records,
    _text,
)
from biocompiler.ir.serialization import require


MAX_PAYLOAD_CONTRACTS = 64
MAX_REQUIRED_PAYLOAD_REGIONS = 256
PAYLOAD_STRUCTURE_PROFILE = "biocompiler.declared_payload_structure.v0.1"
PAYLOAD_STRUCTURE_CLAIM = "correspondence_to_declared_payload_regions"
PAYLOAD_MODALITY_CAPABILITIES = MappingProxyType(
    {
        ("delivered_rna", "linear"): "RNA",
        ("delivered_rna", "circular"): "RNA",
        ("delivered_dna", "linear"): "DNA",
        ("delivered_dna", "circular"): "DNA",
    }
)


@dataclass(frozen=True)
class RequiredPayloadRegion(_MoleculeRecord):
    """One exact feature identity and nominal kind, without functional inference."""

    feature_id: str
    kind: str
    schema_version: ClassVar[str] = "biocompiler.required_payload_region.v0.1"

    def __post_init__(self):
        _text(self.feature_id, "Required payload feature identity")
        _text(self.kind, "Required payload feature kind")
        self._check_resources()


@dataclass(frozen=True)
class PayloadStructureContract(_MoleculeRecord):
    """Frozen required-region authority for one distinct covalent payload member.

    Region order is not geometric order. Independent features may overlap and
    may cross a circular origin. Unknown provenance is retained for an explicit
    unsupported assessment; it cannot acquire declared boundary authority.
    """

    member_id: str
    form: str
    topology: str
    regions: tuple[RequiredPayloadRegion, ...]
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.payload_structure_contract.v0.1"
    _decoders: ClassVar[dict] = {
        "regions": _decode_records(RequiredPayloadRegion, MAX_REQUIRED_PAYLOAD_REGIONS),
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _text(self.member_id, "Required payload member identity")
        _choice(
            self.form,
            {"delivered_rna", "delivered_dna"},
            "final delivered payload form",
        )
        _choice(
            self.topology, {"linear", "circular"}, "final delivered payload topology"
        )
        object.__setattr__(
            self,
            "regions",
            _records(
                self.regions,
                RequiredPayloadRegion,
                MAX_REQUIRED_PAYLOAD_REGIONS,
                "required payload regions",
                key="feature_id",
                nonempty=True,
            ),
        )
        require(
            isinstance(self.provenance, DeclarationProvenance),
            "Payload structure contracts require explicit provenance or declared unknown provenance.",
        )
        object.__setattr__(
            self,
            "provenance",
            DeclarationProvenance.from_dict(self.provenance.to_dict()),
        )
        self._check_resources()
