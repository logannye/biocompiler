"""Offline exact-CDS reference adapter with no molecular behavior attribution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.ir.component_contracts import (
    ComponentRecord,
    PinnedIdentity,
    SequenceReferenceMetadata,
)
from biocompiler.ir.serialization import JsonArtifact, fields, require
from biocompiler.registry.references import ReferenceManifest
from biocompiler.semantics.component_contracts import OperatingDomain

FAP_REFERENCE_SET = "wo2022081694a1.murine-fapcar.cds"
REFERENCE_COMPONENT_VERSION = "biocompiler.reference_component.v0.1"


@dataclass(frozen=True)
class ReferenceSelection(JsonArtifact):
    """Caller-trusted pins supplied independently of the manifest being adapted."""

    manifest: PinnedIdentity
    reference: PinnedIdentity
    schema_version: ClassVar[str] = "biocompiler.reference_selection.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.manifest, PinnedIdentity)
            and isinstance(self.reference, PinnedIdentity)
            and self.manifest.kind == self.reference.kind == "reference",
            "Reference selection requires explicit manifest and record identities.",
        )

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "manifest": self.manifest.to_dict(),
            "reference": self.reference.to_dict(),
        }

    @classmethod
    def from_dict(cls, data):
        fields(data, {"schema_version", "manifest", "reference"}, cls.__name__)
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported reference selection schema.",
        )
        return cls(
            PinnedIdentity.from_dict(data["manifest"]),
            PinnedIdentity.from_dict(data["reference"]),
        )


def adapt_reference_component(
    manifest: ReferenceManifest, selection: ReferenceSelection
) -> ComponentRecord:
    """Resolve an accepted FAP DNA/RNA CDS using independently supplied pins.

    The manifest binds reviewed source/sequence identities. It supplies no model,
    expression guarantee, empirical claim or complete-payload construction rule.
    """
    require(isinstance(manifest, ReferenceManifest), "Expected a reference manifest.")
    require(
        isinstance(selection, ReferenceSelection),
        "A caller-trusted reference selection is required.",
    )
    require(
        manifest.reference_set_id == FAP_REFERENCE_SET,
        "Unsupported reference set for the FAP adapter.",
    )
    require(
        selection.manifest
        == PinnedIdentity(
            "reference",
            manifest.reference_set_id,
            manifest.version,
            manifest.fingerprint,
        ),
        "Reference manifest identity/version/content lock mismatch.",
    )
    record = manifest.record(selection.reference.id)
    require(
        selection.reference
        == PinnedIdentity(
            "reference", record.reference_id, record.version, record.fingerprint
        ),
        "Selected reference identity/version/content lock mismatch.",
    )
    require(
        record.alphabet in {"DNA", "RNA"},
        "The component adapter selects an exact nucleotide CDS, not a protein payload.",
    )
    identities = [selection.manifest]
    identities.extend(
        PinnedIdentity("reference", item.reference_id, item.version, item.fingerprint)
        for item in manifest.records
    )
    identities.extend(
        PinnedIdentity(
            "source", item["id"], item["publication_version"], item["sha256"]
        )
        for item in manifest.sources
    )
    evidence = tuple(
        PinnedIdentity(
            "evidence",
            "review:" + review["reviewer"],
            review["reviewed_on"],
            review["evidence"]["sha256"],
        )
        for review in manifest.reviews
        if review["evidence"] is not None
    )
    return ComponentRecord(
        id="reference." + record.reference_id,
        version=record.version,
        classification="sequence_reference",
        implementation_role="exact_cds_reference",
        supported_targets=(record.alphabet,),
        ports=(),
        supported_domain=OperatingDomain(),
        identities=tuple(identities),
        assumptions=(
            "Reference adapter policy: " + REFERENCE_COMPONENT_VERSION,
            "Coding-sequence boundaries only; no complete delivered payload is specified.",
            "No molecular dynamic contract, empirical behavior or host capacity is established.",
            *("Unknown feature: " + item for item in record.unknown_features),
            *(
                "Evidence relationship: " + item
                for item in record.evidence_relationships
            ),
        ),
        guarantees=(
            "completeness:" + record.completeness,
            "artifact_class:" + record.artifact_class,
            "alphabet:" + record.alphabet,
            "orientation:" + record.orientation,
            "sequence_length:" + str(record.length),
            "sequence_sha256:" + record.sequence_sha256,
            "selected_reference:" + record.reference_id,
            "source_locator:" + record.source_locator,
            "source_id:" + record.source_id,
            "translation:frame-zero-standard-code-terminal-stop-retained",
        ),
        evidence=evidence,
        reference_metadata=SequenceReferenceMetadata(
            record.artifact_class, record.length, record.unknown_features
        ),
    )
