"""Immutable exact-CDS molecular candidates, never acceptance certificates.

Sequence identity hashes canonical symbols only. Artifact identity also binds
layout, lineage, policies and reference locks; file export has a third identity.
The initial profile makes no complete-molecule chemistry or behavior claim.
"""

from __future__ import annotations

from dataclasses import dataclass, fields as dataclass_fields
import hashlib
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir.components import ComponentLock
from biocompiler.ir.construct import ConstructFeature
from biocompiler.ir.intent import SourceLocation
from biocompiler.ir.serialization import (
    JsonArtifact,
    fields,
    fingerprint,
    name,
    names,
    require,
)
from biocompiler.registry.components import RegistryLock
from biocompiler.registry.reference_components import ReferenceSelection
from biocompiler.registry.references import ReferenceRecord
from biocompiler.semantics.coordinates import ORIENTATIONS, SequenceRange


def _hash(value, label):
    require(
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value),
        f"{label} must be a SHA-256 fingerprint.",
    )


def _enum(value, options, label):
    require(isinstance(value, str) and value in options, f"Invalid {label}.")


def _array(value, item_type, label):
    require(isinstance(value, (list, tuple)), f"{label} must be an array.")
    require(all(isinstance(item, item_type) for item in value), f"Invalid {label}.")
    return tuple(value)


def _decode_array(value, item_type):
    require(isinstance(value, (list, tuple)), "Molecular records must be arrays.")
    return tuple(item_type.from_dict(item) for item in value)


class _Record(JsonArtifact):
    _decoders: ClassVar[dict] = {}
    _derived: ClassVar[frozenset[str]] = frozenset()

    def to_dict(self):
        def encode(value):
            if hasattr(value, "to_dict"):
                return value.to_dict()
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            return value

        return {
            "schema_version": self.schema_version,
            **{
                item.name: encode(getattr(self, item.name))
                for item in dataclass_fields(self)
            },
        }

    @classmethod
    def from_dict(cls, data):
        try:
            fields(
                data,
                {item.name for item in dataclass_fields(cls)}
                | {"schema_version"}
                | set(cls._derived),
                cls.__name__,
            )
            require(
                data["schema_version"] == cls.schema_version,
                f"Unsupported {cls.__name__} schema.",
            )
            values = {
                item.name: cls._decoders.get(item.name, lambda value: value)(
                    data[item.name]
                )
                for item in dataclass_fields(cls)
            }
            result = cls(**values)
            for key in cls._derived:
                require(
                    fingerprint(data[key]) == fingerprint(result.to_dict()[key]),
                    f"Derived molecular {key} differs from its authority.",
                )
            return result
        except SerializationError:
            raise
        except (
            TypeError,
            ValueError,
            KeyError,
            IndexError,
            AttributeError,
            OverflowError,
            RecursionError,
        ) as exc:
            raise SerializationError(f"Invalid {cls.__name__}: {exc}") from exc


def canonical_sequence_sha256(sequence: str, alphabet: str) -> str:
    """Hash exact uppercase symbols; never repair, strip or convert an input."""
    _enum(alphabet, {"DNA", "RNA"}, "molecular alphabet")
    require(
        isinstance(sequence, str)
        and bool(sequence)
        and set(sequence) <= set("ACGT" if alphabet == "DNA" else "ACGU"),
        "Molecular sequence must contain canonical uppercase alphabet symbols only.",
    )
    return hashlib.sha256(sequence.encode("ascii")).hexdigest()


@dataclass(frozen=True)
class FeatureStatus(_Record):
    """A scope-specific declaration: unknown and inapplicable never mean absent."""

    feature: str
    status: str
    scope: str
    reason: str
    value: str | None = None
    schema_version: ClassVar[str] = "biocompiler.molecular_feature_status.v0.1"

    def __post_init__(self):
        name(self.feature, "Molecular feature")
        name(self.reason, "Feature status reason")
        _enum(self.status, {"known", "unknown", "inapplicable"}, "feature status")
        _enum(self.scope, {"cds_record", "delivered_molecule"}, "feature scope")
        if self.status == "known":
            name(self.value, "Known feature value")
        else:
            require(self.value is None, "Unknown/inapplicable features have no value.")


@dataclass(frozen=True)
class TranslationPolicy(_Record):
    """Explicit declared convention, reconciled with the independent reference."""

    genetic_code: int = 1
    start_codon: str = "ATG/AUG"
    stop_convention: str = "exactly-one-terminal-star-retained"
    protein_length_includes_stop: bool = True
    schema_version: ClassVar[str] = "biocompiler.translation_policy.v0.1"

    def __post_init__(self):
        require(
            type(self.genetic_code) is int and self.genetic_code > 0,
            "Genetic code must be a positive integer.",
        )
        name(self.start_codon, "Start codon convention")
        name(self.stop_convention, "Termination convention")
        require(
            type(self.protein_length_includes_stop) is bool,
            "Protein length convention must be Boolean.",
        )


@dataclass(frozen=True)
class EncodingPolicy(_Record):
    mode: str = "exact_reference"
    optimization: str = "disabled"
    transformations: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.encoding_policy.v0.1"

    def __post_init__(self):
        object.__setattr__(
            self, "transformations", names(self.transformations, "Transformations")
        )
        require(
            self.mode == "exact_reference"
            and self.optimization == "disabled"
            and not self.transformations,
            "Exact-reference encoding requires disabled optimization and no transformations.",
        )


_ENCODING_PROPERTIES = (
    "sequence",
    "chemistry",
    "end_features",
    "topology",
    "boundaries",
)
_INVALIDATED_ANALYSES = (
    "construct",
    "composition",
    "molecular",
    "structure",
    "expression",
    "behavior",
)


@dataclass(frozen=True)
class EncodingEvidencePolicy(_Record):
    """Conservative invalidation; protein equivalence cannot preserve analyses."""

    semantic_properties: tuple[str, ...] = _ENCODING_PROPERTIES
    invalidated_analyses: tuple[str, ...] = _INVALIDATED_ANALYSES
    schema_version: ClassVar[str] = "biocompiler.encoding_evidence_policy.v0.1"

    def __post_init__(self):
        for key in ("semantic_properties", "invalidated_analyses"):
            object.__setattr__(self, key, names(getattr(self, key), key))
        require(
            self.semantic_properties == _ENCODING_PROPERTIES
            and self.invalidated_analyses == _INVALIDATED_ANALYSES,
            "Encoding evidence invalidation policy cannot be weakened or replaced.",
        )


@dataclass(frozen=True)
class EncodingChange(_Record):
    """A future transformation proposal, not proof of preserved properties.

    The exact-reference profile rejects nonempty change records. Future modes
    require their own comparison contract and fresh affected analyses.
    """

    id: str
    record_id: str
    before_sequence_sha256: str
    after_sequence_sha256: str
    changed_properties: tuple[str, ...]
    reason: str
    preservation_claims: tuple[str, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.encoding_change.v0.1"

    def __post_init__(self):
        for key in ("id", "record_id", "reason"):
            name(getattr(self, key), key)
        for key in ("before_sequence_sha256", "after_sequence_sha256"):
            _hash(getattr(self, key), key)
        for key in ("changed_properties", "preservation_claims"):
            object.__setattr__(self, key, names(getattr(self, key), key))
        require(
            bool(self.changed_properties)
            and set(self.changed_properties) <= set(_ENCODING_PROPERTIES),
            "Encoding change requires explicit supported changed properties.",
        )


@dataclass(frozen=True)
class MolecularRecord(_Record):
    """A literal nucleotide CDS with exact placement and reference lineage."""

    id: str
    instance_id: str
    molecule_id: str
    alphabet: str
    artifact_class: str
    sequence: str
    sequence_sha256: str
    component: ComponentLock
    reference_selection: ReferenceSelection
    source_range: SequenceRange
    molecule_range: SequenceRange
    features: tuple[ConstructFeature, ...] = ()
    feature_statuses: tuple[FeatureStatus, ...] = ()
    orientation: str = "forward"
    reading_frame: int | None = 0
    translation_policy: TranslationPolicy = TranslationPolicy()
    completeness: str = "CDS-reference-only"
    unknown_features: tuple[str, ...] = ()
    evidence_relationships: tuple[str, ...] = ()
    requirement_ids: tuple[str, ...] = ()
    source: SourceLocation | None = None
    schema_version: ClassVar[str] = "biocompiler.molecular_record.v0.1"
    _derived: ClassVar[frozenset[str]] = frozenset({"length"})
    _decoders: ClassVar[dict] = {
        "component": ComponentLock.from_dict,
        "reference_selection": ReferenceSelection.from_dict,
        "source_range": SequenceRange.from_dict,
        "molecule_range": SequenceRange.from_dict,
        "features": lambda value: _decode_array(value, ConstructFeature),
        "feature_statuses": lambda value: _decode_array(value, FeatureStatus),
        "translation_policy": TranslationPolicy.from_dict,
        "source": lambda value: (
            SourceLocation.from_dict(value) if value is not None else None
        ),
    }

    def __post_init__(self):
        for key in (
            "id",
            "instance_id",
            "molecule_id",
            "artifact_class",
            "completeness",
        ):
            name(getattr(self, key), key)
        canonical_sequence_sha256(self.sequence, self.alphabet)
        _hash(self.sequence_sha256, "Canonical sequence identity")
        require(isinstance(self.component, ComponentLock), "Invalid component lock.")
        require(
            isinstance(self.reference_selection, ReferenceSelection),
            "Invalid molecular reference selection.",
        )
        for key in ("source_range", "molecule_range"):
            require(
                isinstance(getattr(self, key), SequenceRange)
                and getattr(self, key).length > 0,
                "Molecular records require nonempty coordinate ranges.",
            )
        for key, cls in (
            ("features", ConstructFeature),
            ("feature_statuses", FeatureStatus),
        ):
            object.__setattr__(self, key, _array(getattr(self, key), cls, key))
        require(
            len({item.id for item in self.features}) == len(self.features),
            "Duplicate molecular feature IDs.",
        )
        require(
            len({(item.scope, item.feature) for item in self.feature_statuses})
            == len(self.feature_statuses),
            "Duplicate scoped molecular feature statuses.",
        )
        _enum(self.orientation, ORIENTATIONS, "molecular orientation")
        require(
            self.reading_frame is None
            or (type(self.reading_frame) is int and self.reading_frame in (0, 1, 2)),
            "A reading frame must be 0, 1, 2 or unspecified.",
        )
        require(
            isinstance(self.translation_policy, TranslationPolicy),
            "Invalid translation policy.",
        )
        for key in ("unknown_features", "evidence_relationships", "requirement_ids"):
            object.__setattr__(self, key, names(getattr(self, key), key))
        require(
            self.source is None or isinstance(self.source, SourceLocation),
            "Invalid molecular source location.",
        )

    @property
    def reference(self):
        return self.reference_selection.reference

    @property
    def length(self):
        return len(self.sequence)

    def to_dict(self):
        return super().to_dict() | {"length": self.length}


@dataclass(frozen=True)
class MolecularArtifact(_Record):
    """Unchecked exact-CDS artifact binding all upstream identity roots."""

    request_fingerprint: str
    construct_fingerprint: str
    layout_fingerprint: str
    registry_lock: RegistryLock
    profile: str
    records: tuple[MolecularRecord, ...]
    encoding_policy: EncodingPolicy = EncodingPolicy()
    evidence_policy: EncodingEvidencePolicy = EncodingEvidencePolicy()
    changes: tuple[EncodingChange, ...] = ()
    source_request_fingerprint: str | None = None
    artifact_scope: str = "exact_cds"
    schema_version: ClassVar[str] = "biocompiler.molecular.v0.2"
    _derived: ClassVar[frozenset[str]] = frozenset(
        {"nodes", "intended_use", "human_therapeutic_admission"}
    )
    _decoders: ClassVar[dict] = {
        "registry_lock": RegistryLock.from_dict,
        "records": lambda value: _decode_array(value, MolecularRecord),
        "encoding_policy": EncodingPolicy.from_dict,
        "evidence_policy": EncodingEvidencePolicy.from_dict,
        "changes": lambda value: _decode_array(value, EncodingChange),
    }

    def __post_init__(self):
        for key in (
            "request_fingerprint",
            "construct_fingerprint",
            "layout_fingerprint",
        ):
            _hash(getattr(self, key), key)
        if self.source_request_fingerprint is not None:
            _hash(self.source_request_fingerprint, "Source request identity")
        require(isinstance(self.registry_lock, RegistryLock), "Invalid registry lock.")
        _enum(self.profile, {"DNA-CDS", "RNA-CDS"}, "molecular profile")
        require(self.artifact_scope == "exact_cds", "Unsupported molecular scope.")
        for key, cls in (
            ("records", MolecularRecord),
            ("changes", EncodingChange),
        ):
            object.__setattr__(self, key, _array(getattr(self, key), cls, key))
            require(
                len({item.id for item in getattr(self, key)})
                == len(getattr(self, key)),
                f"Duplicate molecular {key} IDs.",
            )
        require(
            len({item.instance_id for item in self.records}) == len(self.records),
            "Duplicate molecular source instance IDs.",
        )
        require(
            isinstance(self.encoding_policy, EncodingPolicy), "Invalid encoding policy."
        )
        require(
            isinstance(self.evidence_policy, EncodingEvidencePolicy),
            "Invalid encoding evidence policy.",
        )

    def to_dict(self):
        return super().to_dict() | {
            "intended_use": "software_test",
            "human_therapeutic_admission": "not_admitted",
            "nodes": [
                {"id": item.instance_id, "kind": "cds_record"} for item in self.records
            ],
        }


def reference_feature_statuses(reference: ReferenceRecord) -> tuple[FeatureStatus, ...]:
    """Normative exact-CDS declarations derived only from a pinned reference.

    This is schema/profile meaning, not an emission or acceptance operation.
    Inapplicability describes the CDS record; unknown delivered features remain
    unknown and must never be interpreted as absent from experimental material.
    """
    require(isinstance(reference, ReferenceRecord), "Expected a reference record.")
    require(reference.alphabet in {"DNA", "RNA"}, "Expected a nucleotide reference.")
    known = {
        "alphabet": reference.alphabet,
        "sequence-orientation": reference.orientation,
        "coding-boundaries": f"0:{reference.length}",
        "reading-frame": "0",
        "genetic-code": "1",
        "termination": "exactly-one-terminal-star-retained",
        "completeness": reference.completeness,
        "canonical-sequence-sha256": reference.sequence_sha256,
    }
    statuses = [
        FeatureStatus(
            feature,
            "known",
            "cds_record",
            "Pinned CDS reference record and standard-code policy.",
            value,
        )
        for feature, value in known.items()
    ]
    statuses.extend(
        FeatureStatus(
            feature,
            "unknown",
            "cds_record"
            if feature == "domain-feature-coordinates"
            else "delivered_molecule",
            "The reviewed reference does not establish this feature.",
        )
        for feature in reference.unknown_features
    )
    statuses.extend(
        FeatureStatus(
            feature,
            "inapplicable",
            "cds_record",
            "An exact CDS spelling does not specify a delivered molecule.",
        )
        for feature in (
            "cap",
            "nucleotide-modifications",
            "poly(A)-tail",
            "UTRs",
            "regulatory-context",
            "delivered-molecule-topology",
            "full-delivered-molecule-boundaries",
        )
    )
    return tuple(statuses)
