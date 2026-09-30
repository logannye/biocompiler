"""Portable nominal molecular-design inventories and a bounded handoff contract.

These artifacts retain software structural claims. Parsing an archived success
label establishes neither current compiler acceptance nor biological evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

from biocompiler.artifacts.manifest import (
    ToolPin,
    _Record,
    _array,
    _decode_array,
    _hash,
    _plain_text,
    validate_package_path,
)
from biocompiler.ir.payload import PayloadFeature
from biocompiler.ir.serialization import require

HANDOFF_VERSION = "biocompiler.molecular_design_handoff.v0.1"
UNRESOLVED_HANDOFF_CLAIMS = (
    "expression",
    "molecular_behavior",
    "delivery",
    "therapeutic_efficacy",
    "experimental_material_identity",
    "material_quality",
    "material_potency",
    "clinical_use",
)
REQUIRED_FILES = MappingProxyType(
    {
        "request.json": "request",
        "inputs/fragments.json": "fragment-authority",
        "inputs/layout.json": "layout-authority",
        "construct.json": "design-construct",
        "candidate.json": "design-candidate",
        "molecular.json": "molecular-specification",
        "sequence.fasta": "sequence",
        "source-map.json": "source-map",
        "handoff.json": "nominal-design-handoff",
        "checks/request.json": "request-check",
        "checks/construct.json": "construct-check",
        "checks/molecular.json": "molecular-check",
        "stages/components.json": "components-stage",
        "stages/construct.json": "construct-stage",
        "stages/molecular.json": "molecular-stage",
        "result.json": "build-summary",
    }
)


@dataclass(frozen=True)
class MolecularDesignHandoff(_Record):
    """Exact nominal identity, with actual material and release evidence absent.

    This is a portable artifact contract, not manufacturing instructions or a
    claim that a material has been made, tested, released or authorized for use.
    """

    request_fingerprint: str
    candidate_fingerprint: str
    molecule_fingerprint: str
    molecule_id: str
    sequence_sha256: str
    sequence_length: int
    features: tuple[PayloadFeature, ...]
    artifact_class: str = "mature_linear_rna"
    alphabet: str = "RNA"
    topology: str = "linear"
    strandedness: str = "single"
    orientation: str = "5prime-to-3prime"
    identity_kind: str = "nominal_design"
    intended_use: str = "software_test"
    actual_material_identity: str = "unestablished"
    material_quality: str = "unestablished"
    material_potency: str = "unestablished"
    reference_promotion: str = "not_promoted"
    human_therapeutic_admission: str = "not_admitted"
    clinical_use: str = "not_authorized"
    unresolved_claims: tuple[str, ...] = UNRESOLVED_HANDOFF_CLAIMS
    schema_version: ClassVar[str] = HANDOFF_VERSION
    _decoders: ClassVar[dict] = {
        "features": lambda value: _decode_array(value, PayloadFeature),
    }

    def __post_init__(self):
        for key in (
            "request_fingerprint",
            "candidate_fingerprint",
            "molecule_fingerprint",
            "sequence_sha256",
        ):
            _hash(getattr(self, key), key)
        _plain_text(self.molecule_id, "Molecule id")
        require(
            type(self.sequence_length) is int and self.sequence_length > 0,
            "Handoff requires an exact positive nucleotide length.",
        )
        features = _array(self.features, PayloadFeature, "Handoff features")
        require(
            bool(features)
            and len({item.feature for item in features}) == len(features),
            "Handoff requires unique explicit chemistry/end features.",
        )
        object.__setattr__(self, "features", features)
        fixed = {
            "artifact_class": "mature_linear_rna",
            "alphabet": "RNA",
            "topology": "linear",
            "strandedness": "single",
            "orientation": "5prime-to-3prime",
            "identity_kind": "nominal_design",
            "intended_use": "software_test",
            "actual_material_identity": "unestablished",
            "material_quality": "unestablished",
            "material_potency": "unestablished",
            "reference_promotion": "not_promoted",
            "human_therapeutic_admission": "not_admitted",
            "clinical_use": "not_authorized",
        }
        require(
            all(getattr(self, key) == value for key, value in fixed.items()),
            "Molecular design handoff cannot broaden its molecule or evidence scope.",
        )
        require(
            isinstance(self.unresolved_claims, (tuple, list))
            and tuple(self.unresolved_claims) == UNRESOLVED_HANDOFF_CLAIMS,
            "Nominal design handoff cannot discharge biological or material claims.",
        )
        object.__setattr__(self, "unresolved_claims", UNRESOLVED_HANDOFF_CLAIMS)


@dataclass(frozen=True)
class MolecularDesignPackageFile(_Record):
    path: str
    role: str
    sha256: str
    byte_length: int
    schema_version: ClassVar[str] = "biocompiler.molecular_design_package_file.v0.1"

    def __post_init__(self):
        validate_package_path(self.path)
        require(
            REQUIRED_FILES.get(self.path) == self.role,
            "Unsupported molecular design package path/role.",
        )
        _hash(self.sha256, "Molecular design package file")
        require(
            type(self.byte_length) is int and self.byte_length >= 0,
            "Invalid molecular design file byte length.",
        )


@dataclass(frozen=True)
class MolecularDesignBuildManifest(_Record):
    request_fingerprint: str
    files: tuple[MolecularDesignPackageFile, ...]
    toolchain: tuple[ToolPin, ...]
    package_version: str
    profile: str = "mature_linear_rna_design"
    status: str = "complete"
    scope: str = "software_molecular_design"
    intended_use: str = "software_test"
    reference_promotion: str = "not_promoted"
    human_therapeutic_admission: str = "not_admitted"
    schema_version: ClassVar[str] = "biocompiler.molecular_design_build_manifest.v0.1"
    _decoders: ClassVar[dict] = {
        "files": lambda value: _decode_array(value, MolecularDesignPackageFile),
        "toolchain": lambda value: _decode_array(value, ToolPin),
    }

    def __post_init__(self):
        _hash(self.request_fingerprint, "Molecular design request")
        _plain_text(self.package_version, "Package version")
        require(
            self.profile == "mature_linear_rna_design"
            and self.status == "complete"
            and self.scope == "software_molecular_design",
            "Unsupported molecular design manifest profile/status/scope.",
        )
        require(
            self.intended_use == "software_test"
            and self.reference_promotion == "not_promoted"
            and self.human_therapeutic_admission == "not_admitted",
            "Molecular design manifests cannot promote references or human use.",
        )
        files = _array(self.files, MolecularDesignPackageFile, "Design package files")
        require(
            len(files) == len(REQUIRED_FILES)
            and {item.path: item.role for item in files} == REQUIRED_FILES,
            "Molecular design manifest requires the exact file inventory.",
        )
        tools = _array(self.toolchain, ToolPin, "Toolchain")
        require(
            bool(tools) and len({item.id for item in tools}) == len(tools),
            "Molecular design manifest must pin unique tools.",
        )
        object.__setattr__(
            self, "files", tuple(sorted(files, key=lambda item: item.path))
        )
        object.__setattr__(
            self, "toolchain", tuple(sorted(tools, key=lambda item: item.id))
        )

    @property
    def build_fingerprint(self):
        return self.fingerprint
