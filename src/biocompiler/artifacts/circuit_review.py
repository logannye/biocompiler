"""Versioned portable review inventories and separately retained authority.

A review bundle archives software check results, including honest failures. Its
identity never establishes reviewed reference correspondence or human admission.
"""

from dataclasses import dataclass
import json
from types import MappingProxyType
from typing import ClassVar

from biocompiler.artifacts.manifest import (
    ToolPin,
    _Record,
    _hash,
    validate_package_path,
)
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_bindings import CircuitBindingRequest
from biocompiler.ir.circuit_construction import CircuitConstructionRequest
from biocompiler.ir.circuit_evidence import CircuitEvidenceRequest
from biocompiler.ir.circuit_sources import CircuitSourceInventory
from biocompiler.ir.molecule_records import _MoleculeRecord, _decode_records, _text
from biocompiler.ir.serialization import parse_json, require

REVIEW_POLICY_VERSION = "biocompiler.circuit_review_policy.v0.1"
REVIEW_PACKAGE_VERSION = "0.1.0.dev26"
MAX_AUTHORITY_BYTES = 24 * 1024 * 1024
FILE_ROLES = MappingProxyType(
    {
        "request.json": "construction-request",
        "construction.json": "construction-build",
        "sources/inventory.json": "source-inventory",
        "checks/sources.json": "source-assessment",
        "bindings/request.json": "binding-request",
        "checks/bindings.json": "binding-assessment",
        "evidence/request.json": "evidence-request",
        "evidence/receipt.json": "evidence-receipt",
        "checks/evidence.json": "evidence-assessment",
    }
)
COHORTS = MappingProxyType(
    {
        "construction": frozenset({"request.json", "construction.json"}),
        "sources": frozenset({"sources/inventory.json", "checks/sources.json"}),
        "bindings": frozenset({"bindings/request.json", "checks/bindings.json"}),
        "evidence": frozenset(
            {"evidence/request.json", "evidence/receipt.json", "checks/evidence.json"}
        ),
    }
)


def _optional(cls):
    return lambda value: None if value is None else cls.from_dict(value)


@dataclass(frozen=True)
class CircuitReviewAuthority(_Record):
    """Caller-trusted complete authority, supplied outside the review archive.

    The historical evidence receipt pin prevents replacing a stale receipt with a
    newly captured one. Source metadata is checked independently; its presence
    does not establish a scientific link to the construction or source review.
    """

    construction: CircuitConstructionRequest
    sources: CircuitSourceInventory | None = None
    bindings: CircuitBindingRequest | None = None
    evidence: CircuitEvidenceRequest | None = None
    evidence_receipt_fingerprint: str | None = None
    schema_version: ClassVar[str] = "biocompiler.circuit_review_authority.v0.1"
    _decoders: ClassVar[dict] = {
        "construction": CircuitConstructionRequest.from_dict,
        "sources": _optional(CircuitSourceInventory),
        "bindings": _optional(CircuitBindingRequest),
        "evidence": _optional(CircuitEvidenceRequest),
    }

    def __post_init__(self):
        for key, cls in (
            ("construction", CircuitConstructionRequest),
            ("sources", CircuitSourceInventory),
            ("bindings", CircuitBindingRequest),
            ("evidence", CircuitEvidenceRequest),
        ):
            value = getattr(self, key)
            require(
                value is not None or key != "construction",
                "Complete independent construction authority is required.",
            )
            if value is not None:
                require(isinstance(value, cls), f"Invalid review {key} authority.")
                object.__setattr__(self, key, cls.from_dict(value.to_dict()))
        for value in (self.bindings, self.evidence):
            if value is not None:
                require(
                    value.construction.fingerprint == self.construction.fingerprint
                    and value.construction.to_dict() == self.construction.to_dict(),
                    "Review cohort construction differs from complete construction authority.",
                )
        require(
            (self.evidence is None) == (self.evidence_receipt_fingerprint is None),
            "Evidence authority requires a separately retained historical receipt fingerprint.",
        )
        if self.evidence_receipt_fingerprint is not None:
            _hash(self.evidence_receipt_fingerprint, "Historical evidence receipt")
        self.to_json()

    @property
    def cohorts(self):
        return ("construction",) + tuple(
            key
            for key in ("sources", "bindings", "evidence")
            if getattr(self, key) is not None
        )

    def to_json(self, *, indent=2):
        require(
            indent is None or type(indent) is int and 0 <= indent <= 8,
            "Invalid review authority indentation.",
        )
        encoder = json.JSONEncoder(
            sort_keys=True, indent=indent, ensure_ascii=False, allow_nan=False
        )
        chunks, size = [], 1
        try:
            for chunk in encoder.iterencode(self.to_dict()):
                size += len(chunk.encode("utf-8"))
                require(
                    size <= MAX_AUTHORITY_BYTES, "Review authority exceeds byte limit."
                )
                chunks.append(chunk)
        except (ValueError, TypeError, UnicodeError, RecursionError) as error:
            if isinstance(error, SerializationError):
                raise
            raise SerializationError(f"Invalid review authority: {error}") from error
        return "".join(chunks)

    @classmethod
    def from_json(cls, text):
        require(
            isinstance(text, str) and len(text) <= MAX_AUTHORITY_BYTES,
            "Review authority exceeds byte limit or is not text.",
        )
        try:
            require(
                len(text.encode("utf-8")) <= MAX_AUTHORITY_BYTES,
                "Review authority exceeds byte limit.",
            )
        except UnicodeError as error:
            raise SerializationError("Review authority is not UTF-8.") from error
        return cls.from_dict(parse_json(text))


@dataclass(frozen=True)
class CircuitReviewFile(_MoleculeRecord):
    path: str
    role: str
    sha256: str
    byte_length: int
    schema_version: ClassVar[str] = "biocompiler.circuit_review_file.v0.1"

    def __post_init__(self):
        validate_package_path(self.path)
        require(
            FILE_ROLES.get(self.path) == self.role,
            "Unsupported circuit review path/role.",
        )
        _hash(self.sha256, "Review file content")
        require(
            type(self.byte_length) is int and 0 <= self.byte_length <= 16 * 1024 * 1024,
            "Invalid review file byte length.",
        )
        self._check_resources()


@dataclass(frozen=True)
class CircuitReviewManifest(_MoleculeRecord):
    authority_fingerprint: str
    construction_fingerprint: str
    files: tuple[CircuitReviewFile, ...]
    toolchain: tuple[ToolPin, ...]
    package_version: str
    profile: str = "circuit_review"
    status: str = "retained_review_records"
    reviewed_reference_correspondence: str = "not_established"
    human_biological_applicability: str = "unassessed"
    human_therapeutic_admission: str = "not_admitted"
    family_semantics: str = "unimplemented"
    schema_version: ClassVar[str] = "biocompiler.circuit_review_manifest.v0.1"
    _decoders: ClassVar[dict] = {
        "files": _decode_records(CircuitReviewFile, len(FILE_ROLES)),
        "toolchain": _decode_records(ToolPin, 32),
    }

    def __post_init__(self):
        _hash(self.authority_fingerprint, "Review authority")
        _hash(self.construction_fingerprint, "Review construction")
        _text(self.package_version, "Review package version", maximum=256)
        for key, cls, maximum, identity in (
            ("files", CircuitReviewFile, len(FILE_ROLES), "path"),
            ("toolchain", ToolPin, 32, "id"),
        ):
            values = getattr(self, key)
            require(
                isinstance(values, (tuple, list)) and 0 < len(values) <= maximum,
                f"Invalid review {key} inventory.",
            )
            require(
                all(isinstance(value, cls) for value in values),
                f"Invalid review {key} record.",
            )
            values = tuple(cls.from_dict(value.to_dict()) for value in values)
            require(
                len({getattr(value, identity) for value in values}) == len(values),
                f"Duplicate review {key} identity.",
            )
            object.__setattr__(
                self,
                key,
                tuple(sorted(values, key=lambda value: getattr(value, identity))),
            )
        paths = {item.path for item in self.files}
        require(
            COHORTS["construction"] <= paths,
            "Review requires complete construction records.",
        )
        for cohort in COHORTS.values():
            require(
                not paths.intersection(cohort) or cohort <= paths,
                "Review optional cohorts must be complete.",
            )
        for key, value in {
            "profile": "circuit_review",
            "status": "retained_review_records",
            "reviewed_reference_correspondence": "not_established",
            "human_biological_applicability": "unassessed",
            "human_therapeutic_admission": "not_admitted",
            "family_semantics": "unimplemented",
        }.items():
            require(
                getattr(self, key) == value,
                "Review manifest cannot broaden its acceptance claims.",
            )
        self._check_resources()

    @property
    def build_fingerprint(self):
        return self.fingerprint

    @property
    def cohorts(self):
        paths = {item.path for item in self.files}
        return tuple(key for key, cohort in COHORTS.items() if cohort <= paths)
