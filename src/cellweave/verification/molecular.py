"""Independent exact-reference molecular acceptance without emitter trust.

CDS spelling equality, linked-reference consistency and translation are distinct
checks. A translated protein match cannot forgive a changed reference nucleotide.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
from typing import ClassVar

from cellweave.errors import SerializationError
from cellweave.ir.construct import ConstructCandidate, ConstructRequest
from cellweave.ir.intent import SourceLocation, freeze_json, thaw_json
from cellweave.ir.serialization import (
    JsonArtifact,
    fields,
    fingerprint,
    name,
    names,
    require,
)
from cellweave.registry.components import ComponentRegistry
from cellweave.registry.references import ReferenceManifest, translate_cds
from cellweave.verification.construct import (
    CHECKER_VERSION as CONSTRUCT_CHECKER_VERSION,
    check_construct,
)
from cellweave.verification.evidence import CheckOutcome, FreshnessReport

CHECKER_VERSION = "cellweave.molecular_checker.v0.1"
_COMPARISONS = frozenset(
    {
        "canonical_hash",
        "exact_reference",
        "translation_reference",
        "dna_rna_correspondence",
    }
)
CLAIM_SCOPE = (
    "Exact selected DNA-CDS or RNA-CDS spelling, source correspondence, linked "
    "reference consistency and standard-code translation only. A protein match "
    "does not establish nucleotide equality, complete delivered-payload features, "
    "expression, molecular behavior, modality interchangeability or efficacy."
)


def _hash(value, label):
    require(
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value),
        f"Invalid {label} fingerprint.",
    )


def _sha(sequence):
    return hashlib.sha256(sequence.encode("ascii")).hexdigest()


def _outcome(diagnostics):
    statuses = {item.status for item in diagnostics}
    return next(
        (
            outcome
            for outcome in (
                CheckOutcome.FAIL,
                CheckOutcome.UNSUPPORTED,
                CheckOutcome.UNKNOWN,
            )
            if outcome.value in statuses
        ),
        CheckOutcome.PASS,
    )


@dataclass(frozen=True)
class MolecularDiagnostic:
    status: str
    code: str
    message: str
    record_id: str | None = None
    instance_id: str | None = None
    molecule_id: str | None = None
    requirement_ids: tuple[str, ...] = ()
    source: SourceLocation | None = None

    def __post_init__(self):
        require(
            isinstance(self.status, str)
            and self.status in {"fail", "unsupported", "unknown"},
            "Invalid molecular diagnostic status.",
        )
        for key in ("code", "message"):
            name(getattr(self, key), key)
        for key in ("record_id", "instance_id", "molecule_id"):
            if getattr(self, key) is not None:
                name(getattr(self, key), key)
        object.__setattr__(
            self,
            "requirement_ids",
            names(self.requirement_ids, "Diagnostic requirements"),
        )
        require(
            self.source is None or isinstance(self.source, SourceLocation),
            "Invalid molecular diagnostic source.",
        )

    def to_dict(self):
        return {
            "status": self.status,
            "code": self.code,
            "message": self.message,
            "record_id": self.record_id,
            "instance_id": self.instance_id,
            "molecule_id": self.molecule_id,
            "requirement_ids": list(self.requirement_ids),
            "source": self.source.to_dict() if self.source else None,
        }

    @classmethod
    def from_dict(cls, data):
        fields(data, set(cls.__dataclass_fields__), cls.__name__)
        values = dict(data)
        if values["source"] is not None:
            values["source"] = SourceLocation.from_dict(values["source"])
        return cls(**values)


@dataclass(frozen=True)
class MolecularCheck:
    """One independently computed comparison; exact and protein checks differ."""

    record_id: str
    check: str
    outcome: CheckOutcome
    expected_fingerprint: str | None
    actual_fingerprint: str | None
    message: str

    def __post_init__(self):
        for key in ("record_id", "check", "message"):
            name(getattr(self, key), key)
        require(
            isinstance(self.outcome, CheckOutcome),
            "Invalid molecular comparison outcome.",
        )
        for key in ("expected_fingerprint", "actual_fingerprint"):
            if getattr(self, key) is not None:
                _hash(getattr(self, key), key)
        require(self.check in _COMPARISONS, "Unsupported molecular comparison.")
        require(
            self.outcome is not CheckOutcome.PASS
            or self.expected_fingerprint is not None
            and self.expected_fingerprint == self.actual_fingerprint,
            "A passing molecular comparison requires equal concrete identities.",
        )

    def to_dict(self):
        return {
            "record_id": self.record_id,
            "check": self.check,
            "outcome": self.outcome.value,
            "expected_fingerprint": self.expected_fingerprint,
            "actual_fingerprint": self.actual_fingerprint,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data):
        fields(data, set(cls.__dataclass_fields__), cls.__name__)
        require(
            isinstance(data["outcome"], str)
            and data["outcome"] in {item.value for item in CheckOutcome},
            "Invalid molecular comparison outcome.",
        )
        return cls(**(dict(data) | {"outcome": CheckOutcome(data["outcome"])}))


@dataclass(frozen=True)
class MolecularResult(JsonArtifact):
    outcome: CheckOutcome
    dependencies: Mapping
    checked_requirement_ids: tuple[str, ...]
    diagnostics: tuple[MolecularDiagnostic, ...] = ()
    checks: tuple[MolecularCheck, ...] = ()
    claim_scope: str = CLAIM_SCOPE
    schema_version: ClassVar[str] = "cellweave.molecular_result.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.outcome, CheckOutcome), "Invalid molecular check outcome."
        )
        hashes = {
            "request",
            "construct",
            "layout",
            "candidate",
            "registry",
            "registry_lock",
            "target",
            "profile",
            "encoding_policy",
            "evidence_policy",
        }
        fields(
            self.dependencies,
            hashes | {"references", "checker", "construct_checker"},
            "Molecular dependencies",
        )
        for key in hashes:
            _hash(self.dependencies[key], key)
        for key, expected in (
            ("checker", CHECKER_VERSION),
            ("construct_checker", CONSTRUCT_CHECKER_VERSION),
        ):
            require(self.dependencies[key] == expected, f"Unsupported {key} version.")
        refs = self.dependencies["references"]
        require(isinstance(refs, Mapping), "Reference dependencies must be a mapping.")
        for key, value in refs.items():
            name(key, "Reference dependency")
            _hash(value, "reference")
        object.__setattr__(self, "dependencies", freeze_json(self.dependencies))
        object.__setattr__(
            self,
            "checked_requirement_ids",
            names(self.checked_requirement_ids, "Checked requirements"),
        )
        for key, kind in (
            ("diagnostics", MolecularDiagnostic),
            ("checks", MolecularCheck),
        ):
            value = getattr(self, key)
            require(
                isinstance(value, (tuple, list))
                and all(isinstance(item, kind) for item in value),
                f"Invalid molecular {key}.",
            )
            object.__setattr__(self, key, tuple(value))
        require(
            len({(item.record_id, item.check) for item in self.checks})
            == len(self.checks),
            "Duplicate molecular comparisons.",
        )
        require(
            self.outcome is _outcome(self.diagnostics),
            "Molecular outcome disagrees with diagnostics.",
        )
        require(
            self.outcome is not CheckOutcome.PASS
            or all(item.outcome is CheckOutcome.PASS for item in self.checks),
            "Passing molecular results cannot contain failed or unresolved comparisons.",
        )
        require(
            self.outcome is not CheckOutcome.PASS
            or len({item.record_id for item in self.checks}) == 1
            and {item.check for item in self.checks} == _COMPARISONS,
            "A passing molecular result requires every independent single-CDS comparison.",
        )
        require(self.claim_scope == CLAIM_SCOPE, "Invalid molecular claim scope.")

    @property
    def passed(self):
        return self.outcome is CheckOutcome.PASS

    def freshness(self, request, construct, candidate, registry, manifests):
        current = freeze_json(
            molecular_dependencies(request, construct, candidate, registry, manifests)
        )
        return FreshnessReport(
            tuple(
                sorted(key for key in current if current[key] != self.dependencies[key])
            )
        )

    def is_fresh(self, request, construct, candidate, registry, manifests):
        return self.freshness(request, construct, candidate, registry, manifests).fresh

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "outcome": self.outcome.value,
            "dependencies": thaw_json(self.dependencies),
            "checked_requirement_ids": list(self.checked_requirement_ids),
            "diagnostics": [item.to_dict() for item in self.diagnostics],
            "checks": [item.to_dict() for item in self.checks],
            "claim_scope": self.claim_scope,
        }

    @classmethod
    def from_dict(cls, data):
        fields(
            data,
            {
                "schema_version",
                "outcome",
                "dependencies",
                "checked_requirement_ids",
                "diagnostics",
                "checks",
                "claim_scope",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported molecular result schema.",
        )
        require(
            isinstance(data["outcome"], str)
            and data["outcome"] in {item.value for item in CheckOutcome},
            "Invalid molecular outcome.",
        )
        for key in ("diagnostics", "checks"):
            require(
                isinstance(data[key], (tuple, list)),
                f"Molecular {key} must be an array.",
            )
        return cls(
            CheckOutcome(data["outcome"]),
            data["dependencies"],
            data["checked_requirement_ids"],
            tuple(MolecularDiagnostic.from_dict(item) for item in data["diagnostics"]),
            tuple(MolecularCheck.from_dict(item) for item in data["checks"]),
            data["claim_scope"],
        )


def molecular_dependencies(request, construct, candidate, registry, manifests):
    from cellweave.ir.molecular import MolecularArtifact

    require(
        isinstance(request, ConstructRequest)
        and isinstance(construct, ConstructCandidate)
        and isinstance(candidate, MolecularArtifact),
        "Invalid molecular checker artifacts.",
    )
    require(isinstance(registry, ComponentRegistry), "Expected a component registry.")
    require(
        isinstance(manifests, Mapping)
        and all(
            isinstance(key, str) and isinstance(item, ReferenceManifest)
            for key, item in manifests.items()
        ),
        "Expected frozen offline reference manifests.",
    )
    return {
        "request": request.fingerprint,
        "construct": construct.fingerprint,
        "layout": construct.layout_fingerprint,
        "candidate": candidate.fingerprint,
        "registry": registry.fingerprint,
        "registry_lock": request.composition.registry_lock.fingerprint,
        "target": request.composition.target.fingerprint,
        "profile": fingerprint(
            {
                "schema_version": candidate.schema_version,
                "profile": candidate.profile,
                "artifact_scope": candidate.artifact_scope,
            }
        ),
        "encoding_policy": candidate.encoding_policy.fingerprint,
        "evidence_policy": candidate.evidence_policy.fingerprint,
        "references": {
            key: item.fingerprint for key, item in sorted(manifests.items())
        },
        "checker": CHECKER_VERSION,
        "construct_checker": CONSTRUCT_CHECKER_VERSION,
    }


def check_molecular(request, construct, candidate, registry, manifests):
    """Recompute exact-reference acceptance from caller authority and live inputs.

    The emitter supplies no success receipt. The reviewed nucleotide, linked
    protein and counterpart nucleotide records remain independent expectations.
    """
    from cellweave.ir.molecular import reference_feature_statuses

    dependencies = molecular_dependencies(
        request, construct, candidate, registry, manifests
    )
    upstream = check_construct(request, construct, registry, manifests)
    diagnostics = [
        MolecularDiagnostic(
            item.status,
            "construct:" + item.code,
            item.message,
            None,
            item.instance_id,
            item.molecule_id,
            item.requirement_ids,
            item.source,
        )
        for item in upstream.diagnostics
    ]
    checks = []
    placements = {item.instance_id: item for item in construct.placements}
    selections = {item.instance_id: item.selection for item in request.references}
    molecules = {item.id: item for item in construct.molecules}

    def diagnostic(status, code, message, record=None):
        placement = placements.get(record.instance_id) if record is not None else None
        diagnostics.append(
            MolecularDiagnostic(
                status,
                code,
                message,
                record.id if record else None,
                record.instance_id if record else None,
                record.molecule_id if record else None,
                placement.requirement_ids
                if placement
                else request.composition.requirement_ids,
                placement.source if placement else None,
            )
        )

    def comparison(record, check, passed, expected_hash, actual_hash, message):
        checks.append(
            MolecularCheck(
                record.id,
                check,
                CheckOutcome.PASS if passed else CheckOutcome.FAIL,
                expected_hash,
                actual_hash,
                message,
            )
        )
        if not passed:
            diagnostic("fail", check, message, record)

    for name_, actual, expected in (
        ("request_identity", candidate.request_fingerprint, request.fingerprint),
        ("construct_identity", candidate.construct_fingerprint, construct.fingerprint),
        ("layout_identity", candidate.layout_fingerprint, construct.layout_fingerprint),
        ("registry_lock", candidate.registry_lock, request.composition.registry_lock),
        (
            "source_request",
            candidate.source_request_fingerprint,
            request.source_request_fingerprint,
        ),
    ):
        if actual != expected:
            diagnostic(
                "fail",
                name_,
                "Molecular artifact changed its authoritative "
                + name_.replace("_", " ")
                + ".",
            )
    if (
        candidate.profile != request.composition.target.payload_format.value + "-CDS"
        or candidate.artifact_scope != "exact_cds"
    ):
        diagnostic(
            "fail",
            "output_profile",
            "The molecular profile must reproduce only the selected target's coding reference.",
        )
    if candidate.changes:
        diagnostic(
            "unsupported",
            "encoding_changes",
            "Exact-reference reproduction disables sequence optimization and all encoding transformations; a change record does not preserve prior acceptance.",
        )
    if len(candidate.records) != 1 or {
        item.instance_id for item in candidate.records
    } != set(placements):
        diagnostic(
            "fail",
            "record_inventory",
            "Molecular records must cover exactly the accepted single selected CDS instance.",
        )
    for record in candidate.records:
        placement = placements.get(record.instance_id)
        selection = selections.get(record.instance_id)
        molecule = molecules.get(record.molecule_id)
        if placement is None or selection is None or molecule is None:
            diagnostic(
                "fail",
                "record_correspondence",
                "The molecular record names no authoritative selected placement, reference or molecule.",
                record,
            )
            continue
        if record.id != molecule.id or record.molecule_id != placement.molecule_id:
            diagnostic(
                "fail",
                "record_membership",
                "Record identity and molecule membership must identify the accepted construct molecule.",
                record,
            )
        if (
            record.component != placement.component
            or record.reference_selection != selection
        ):
            diagnostic(
                "fail",
                "selected_identity",
                "The molecular record changed the selected component or trusted reference manifest/record identity.",
                record,
            )
        if (
            record.source_range,
            record.molecule_range,
            record.orientation,
            record.reading_frame,
        ) != (
            placement.source_range,
            placement.molecule_range,
            placement.orientation,
            placement.reading_frame,
        ):
            diagnostic(
                "fail",
                "construct_coordinates",
                "Source/destination ranges, orientation and reading frame must preserve the accepted placement.",
                record,
            )
        if record.orientation != "forward" or record.reading_frame != 0:
            diagnostic(
                "fail",
                "reference_orientation_or_frame",
                "The reference reproduction profile requires forward 5prime-to-3prime spelling and frame zero.",
                record,
            )
        if (
            record.requirement_ids != placement.requirement_ids
            or record.source != placement.source
        ):
            diagnostic(
                "fail",
                "source_correspondence",
                "The molecular record changed source or requirement correspondence.",
                record,
            )
        if record.features != construct.features:
            diagnostic(
                "fail",
                "feature_coordinates",
                "The molecular record introduced or changed feature-boundary assertions absent from the accepted construct.",
                record,
            )
        manifest = manifests.get(selection.manifest.id)
        if manifest is None:
            diagnostic(
                "unknown",
                "missing_reference",
                "The selected frozen offline reference manifest is missing.",
                record,
            )
            continue
        try:
            reference = manifest.record(selection.reference.id)
        except SerializationError as error:
            diagnostic("fail", "selected_reference", str(error), record)
            continue
        if (
            record.alphabet,
            record.artifact_class,
            record.completeness,
            record.unknown_features,
            record.evidence_relationships,
        ) != (
            reference.alphabet,
            reference.artifact_class,
            reference.completeness,
            reference.unknown_features,
            reference.evidence_relationships,
        ):
            diagnostic(
                "fail",
                "reference_metadata",
                "Molecular alphabet, artifact class, coding-only scope, unknown features and evidence relationships must match the independently pinned reference.",
                record,
            )
        if (
            record.alphabet != molecule.alphabet
            or record.length != molecule.length
            or record.length != reference.length
        ):
            diagnostic(
                "fail",
                "sequence_length_or_alphabet",
                "The emitted sequence length and alphabet must agree with both the accepted construct and frozen reference.",
                record,
            )
        if record.feature_statuses != reference_feature_statuses(reference):
            diagnostic(
                "fail",
                "feature_statuses",
                "Known, unknown and inapplicable feature declarations must preserve the exact scoped reference-CDS profile; delivered-payload features cannot become known.",
                record,
            )
        expected_translation = dict(manifest.translation)
        actual_translation = record.translation_policy.to_dict()
        actual_translation.pop("schema_version", None)
        expected_translation.pop("frame_zero_based", None)
        if actual_translation != expected_translation:
            diagnostic(
                "fail",
                "translation_policy",
                "Translation must use the independently frozen standard-code start, frame-zero and terminal-stop conventions.",
                record,
            )
        actual_hash = _sha(record.sequence)
        comparison(
            record,
            "canonical_hash",
            record.sequence_sha256 == actual_hash,
            actual_hash,
            record.sequence_sha256,
            "Declared canonical sequence hash agrees with the emitted symbols."
            if record.sequence_sha256 == actual_hash
            else "Declared canonical sequence hash differs from the emitted symbols.",
        )
        exact = record.sequence == reference.sequence
        if exact:
            message = "Every emitted nucleotide equals the independently frozen selected reference."
        else:
            mismatch = next(
                (
                    index
                    for index, (actual, expected) in enumerate(
                        zip(record.sequence, reference.sequence)
                    )
                    if actual != expected
                ),
                min(record.length, reference.length),
            )
            expected = (
                reference.sequence[mismatch] if mismatch < reference.length else "<end>"
            )
            actual = record.sequence[mismatch] if mismatch < record.length else "<end>"
            message = f"Exact reference mismatch at zero-based nucleotide {mismatch}: expected {expected!r}, observed {actual!r}."
        comparison(
            record,
            "exact_reference",
            exact,
            reference.sequence_sha256,
            actual_hash,
            message,
        )
        linked = {
            item.alphabet: item
            for item in manifest.records
            if item.reference_id in reference.linked_reference_ids
        }
        protein = linked.get("protein")
        counterpart_alphabet = "RNA" if reference.alphabet == "DNA" else "DNA"
        counterpart = linked.get(counterpart_alphabet)
        if protein is None or counterpart is None:
            diagnostic(
                "fail",
                "linked_reference_inventory",
                "The selected CDS lacks its independently frozen protein or counterpart nucleotide reference.",
                record,
            )
            continue
        try:
            translated = translate_cds(record.sequence, record.alphabet)
        except SerializationError as error:
            comparison(
                record,
                "translation_reference",
                False,
                protein.sequence_sha256,
                None,
                "Emitted CDS fails the independent translation convention: "
                + str(error),
            )
        else:
            equal = translated == protein.sequence
            comparison(
                record,
                "translation_reference",
                equal,
                protein.sequence_sha256,
                _sha(translated),
                "Independent standard-code translation matches the frozen protein, retaining the terminal stop."
                if equal
                else "Independent standard-code translation differs from the separately frozen protein reference.",
            )
        transformed = (
            record.sequence.replace("T", "U")
            if reference.alphabet == "DNA"
            else record.sequence.replace("U", "T")
        )
        consistent = transformed == counterpart.sequence
        comparison(
            record,
            "dna_rna_correspondence",
            consistent,
            counterpart.sequence_sha256,
            _sha(transformed),
            "Emitted spelling agrees with the independently frozen counterpart under T/U correspondence; this makes no delivered-modality equivalence claim."
            if consistent
            else "Emitted spelling differs from the independently frozen counterpart under the separate T/U consistency check.",
        )
    return MolecularResult(
        _outcome(diagnostics),
        dependencies,
        request.composition.requirement_ids,
        tuple(diagnostics),
        tuple(checks),
    )
