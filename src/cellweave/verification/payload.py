"""Independent structural readiness checks for supplied complete molecules.

There is no emitter, registry promotion, biological model or compiler admission
in this module. The caller supplies an authority pin separately from the output.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
from typing import ClassVar

from cellweave.errors import SerializationError
from cellweave.ir.intent import freeze_json, thaw_json
from cellweave.ir.payload import (
    PAYLOAD_PROFILE_VERSION,
    SUPPORTED_PAYLOAD_CLASSES,
    PayloadMolecule,
    PayloadReference,
    hash_value,
    name,
    names,
)
from cellweave.ir.serialization import JsonArtifact, fields, parse_json, require
from cellweave.registry.references import normalize_sequence, translate_cds
from cellweave.semantics.coordinates import SequenceRange
from cellweave.verification.evidence import CheckOutcome, FreshnessReport

CHECKER_VERSION = "cellweave.payload_checker.v0.1"
REVIEW_SCHEMA_VERSION = "cellweave.payload_review_statement.v0.1"
CLAIM_SCOPE = (
    "Structural completeness and exact correspondence to separately pinned supplied "
    "expectations and retained source/review bytes only. No reference promotion, "
    "compiler admission, experimental-material identity, expression, molecular "
    "behavior or therapeutic efficacy is established."
)
_CHECKS = (
    "authority_pin",
    "retained_sources",
    "independent_review_declarations",
    "source_sequence",
    "exact_molecule",
    "whole_molecule_profile",
    "coding_correspondence",
)


def _sha(value):
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class PayloadDiagnostic:
    status: str
    code: str
    message: str

    def __post_init__(self):
        require(
            self.status in ("fail", "unknown", "unsupported"),
            "Invalid payload diagnostic.",
        )
        name(self.code, "Diagnostic code")
        name(self.message, "Diagnostic message")

    def to_dict(self):
        return {key: getattr(self, key) for key in ("status", "code", "message")}

    @classmethod
    def from_dict(cls, data):
        fields(data, {"status", "code", "message"}, cls.__name__)
        return cls(**data)


def _outcome(diagnostics):
    statuses = {item.status for item in diagnostics}
    return next(
        (
            x
            for x in (CheckOutcome.FAIL, CheckOutcome.UNSUPPORTED, CheckOutcome.UNKNOWN)
            if x.value in statuses
        ),
        CheckOutcome.PASS,
    )


@dataclass(frozen=True)
class PayloadResult(JsonArtifact):
    outcome: CheckOutcome
    dependencies: Mapping
    evidence_boundary: str
    diagnostics: tuple[PayloadDiagnostic, ...] = ()
    checks: tuple[str, ...] = _CHECKS
    reference_promotion: str = "not_promoted"
    compiler_admission: bool = False
    claim_scope: str = CLAIM_SCOPE
    schema_version: ClassVar[str] = "cellweave.payload_result.v0.1"

    def __post_init__(self):
        require(isinstance(self.outcome, CheckOutcome), "Invalid payload outcome.")
        fields(
            self.dependencies,
            {
                "candidate",
                "reference",
                "authority_pin",
                "retained_sources",
                "checker",
                "profile",
                "schema",
            },
            "Payload dependencies",
        )
        for key in ("candidate", "reference", "authority_pin"):
            hash_value(self.dependencies[key], key)
        require(
            isinstance(self.dependencies["retained_sources"], Mapping),
            "Invalid source pins.",
        )
        for key, value in self.dependencies["retained_sources"].items():
            name(key, "Source id")
            hash_value(value, "Retained source")
        for key in ("checker", "profile", "schema"):
            name(self.dependencies[key], key)
        require(
            self.dependencies["checker"] == CHECKER_VERSION
            and self.dependencies["profile"] == PAYLOAD_PROFILE_VERSION
            and self.dependencies["schema"] == PayloadMolecule.schema_version,
            "Payload receipts require the current schema, profile and checker; recheck old inputs.",
        )
        object.__setattr__(self, "dependencies", freeze_json(self.dependencies))
        require(
            self.evidence_boundary in ("software_fixture", "externally_reviewed"),
            "Invalid evidence boundary.",
        )
        require(
            isinstance(self.diagnostics, (tuple, list))
            and all(isinstance(x, PayloadDiagnostic) for x in self.diagnostics),
            "Invalid diagnostics.",
        )
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        object.__setattr__(self, "checks", names(self.checks, "Payload checks"))
        require(self.checks == _CHECKS, "Incomplete payload check inventory.")
        require(
            self.outcome == _outcome(self.diagnostics),
            "Payload outcome disagrees with diagnostics.",
        )
        require(
            self.reference_promotion == "not_promoted"
            and self.compiler_admission is False,
            "Readiness cannot grant reference promotion or compiler admission.",
        )
        require(
            self.claim_scope == CLAIM_SCOPE, "Payload claim scope cannot be weakened."
        )

    @property
    def passed(self):
        return self.outcome is CheckOutcome.PASS

    def freshness(
        self, candidate, reference, *, expected_reference_fingerprint, retained_sources
    ):
        current = freeze_json(
            payload_dependencies(
                candidate,
                reference,
                expected_reference_fingerprint=expected_reference_fingerprint,
                retained_sources=retained_sources,
            )
        )
        return FreshnessReport(
            tuple(
                sorted(key for key in current if current[key] != self.dependencies[key])
            )
        )

    def is_fresh(
        self, candidate, reference, *, expected_reference_fingerprint, retained_sources
    ):
        return self.freshness(
            candidate,
            reference,
            expected_reference_fingerprint=expected_reference_fingerprint,
            retained_sources=retained_sources,
        ).fresh

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "outcome": self.outcome.value,
            "dependencies": thaw_json(self.dependencies),
            "evidence_boundary": self.evidence_boundary,
            "diagnostics": [x.to_dict() for x in self.diagnostics],
            "checks": list(self.checks),
            "reference_promotion": self.reference_promotion,
            "compiler_admission": self.compiler_admission,
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
                "evidence_boundary",
                "diagnostics",
                "checks",
                "reference_promotion",
                "compiler_admission",
                "claim_scope",
            },
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported payload result schema.",
        )
        require(
            isinstance(data["outcome"], str)
            and data["outcome"] in {x.value for x in CheckOutcome},
            "Invalid payload outcome.",
        )
        require(
            isinstance(data["diagnostics"], (tuple, list)),
            "Diagnostics must be an array.",
        )
        return cls(
            **{
                key: value
                for key, value in data.items()
                if key not in ("schema_version", "outcome", "diagnostics")
            },
            outcome=CheckOutcome(data["outcome"]),
            diagnostics=tuple(
                PayloadDiagnostic.from_dict(x) for x in data["diagnostics"]
            ),
        )


def payload_dependencies(
    candidate, reference, *, expected_reference_fingerprint, retained_sources
):
    require(
        isinstance(candidate, PayloadMolecule)
        and isinstance(reference, PayloadReference),
        "Payload checking requires a molecule and independent reference authority.",
    )
    hash_value(expected_reference_fingerprint, "Expected reference")
    require(
        isinstance(retained_sources, Mapping)
        and all(
            isinstance(k, str) and bool(k.strip()) and isinstance(v, bytes)
            for k, v in retained_sources.items()
        ),
        "Retained sources must map ids to bytes.",
    )
    for key in retained_sources:
        name(key, "Retained source id")
    return {
        "candidate": candidate.fingerprint,
        "reference": reference.fingerprint,
        "authority_pin": expected_reference_fingerprint,
        "retained_sources": {
            key: _sha(value) for key, value in retained_sources.items()
        },
        "checker": CHECKER_VERSION,
        "profile": PAYLOAD_PROFILE_VERSION,
        "schema": PayloadMolecule.schema_version,
    }


def _profile_diagnostics(molecule):
    diagnostics = []

    def problem(code, message, status="fail"):
        diagnostics.append(PayloadDiagnostic(status, code, message))

    if molecule.artifact_class not in SUPPORTED_PAYLOAD_CLASSES:
        problem(
            "unsupported_payload_class",
            "This artifact class has no complete-molecule profile.",
            "unsupported",
        )
        return diagnostics
    rna = molecule.artifact_class == "mature_linear_rna"
    circular = molecule.artifact_class == "circular_plasmid"
    if (molecule.alphabet, molecule.topology, molecule.strandedness) != (
        "RNA" if rna else "DNA",
        "circular" if circular else "linear",
        "single" if rna else "double",
    ):
        problem(
            "payload_modality_mismatch",
            "Alphabet, topology and strandedness must match this exact molecule class.",
        )
    if (
        molecule.completeness != "complete_molecule"
        or molecule.orientation != "5prime-to-3prime"
    ):
        problem(
            "incomplete_molecule_claim",
            "A complete 5-prime-to-3-prime molecule spelling is required.",
        )
    if molecule.boundaries != SequenceRange(0, len(molecule.sequence)):
        problem(
            "whole_molecule_boundaries",
            "The source-located molecule must cover exactly [0, sequence length).",
        )
    if _sha(molecule.sequence.encode("ascii")) != molecule.sequence_sha256:
        problem(
            "payload_sequence_hash",
            "Sequence SHA-256 differs from the supplied symbols.",
        )
    if molecule.unknown_features:
        problem(
            "unknown_payload_features",
            "Complete-molecule features remain unresolved: "
            + ", ".join(molecule.unknown_features),
            "unknown",
        )
    cursor = 0
    for region in molecule.regions:
        if (
            region.range.start != cursor
            or region.range.length == 0
            or region.range.end > len(molecule.sequence)
        ):
            problem(
                "region_partition",
                "Coding and noncoding regions must cover every base once, in order.",
            )
        cursor = region.range.end
        if region.source_range != region.range:
            problem(
                "region_source_correspondence",
                "Regions must retain exact coordinates in the independent whole-molecule extraction.",
            )
        if region.orientation != "forward" or region.reading_frame != 0:
            problem(
                "unsupported_region_traversal",
                "This profile supports forward, frame-zero coding only.",
                "unsupported",
            )
        if region.kind != "cds" and region.protein_sequence is not None:
            problem(
                "noncoding_protein_claim",
                "A noncoding region cannot claim a translated protein.",
            )
    if cursor != len(molecule.sequence):
        problem(
            "region_partition", "Region coverage must end at the final molecule base."
        )
    kinds = tuple(x.kind for x in molecule.regions)
    allowed = (
        (
            ("five_prime_utr", "cds", "three_prime_utr"),
            ("five_prime_utr", "cds", "three_prime_utr", "poly_a"),
        )
        if rna
        else (
            ("promoter", "cds", "terminator", "backbone")
            if circular
            else ("promoter", "cds", "terminator"),
        )
    )
    if kinds not in allowed:
        problem(
            "payload_region_profile",
            "This narrow profile requires one CDS and explicit source-mapped noncoding regions.",
            "unsupported",
        )
    features = {x.feature: x for x in molecule.features}
    required = {
        "cap",
        "poly_a_tail",
        "nucleotide_modifications",
        "end_structure",
        "five_prime_end",
        "three_prime_end",
    }
    if set(features) != required:
        problem(
            "payload_feature_inventory",
            "The complete chemistry/end-feature inventory must be explicit and contain no extra assertions.",
        )
    expected = {
        "cap": ("known", {"none", "cap0", "cap1"}) if rna else ("inapplicable", {None}),
        "poly_a_tail": ("known", None) if rna else ("inapplicable", {None}),
        "nucleotide_modifications": ("known", {"none"}),
        "end_structure": ("inapplicable", {None})
        if circular
        else ("known", {"single_strand" if rna else "blunt"}),
        "five_prime_end": (
            ("inapplicable", {None})
            if circular
            else ("known", {"capped", "hydroxyl", "monophosphate", "triphosphate"})
            if rna
            else ("known", {"hydroxyl_both_strands", "phosphate_both_strands"})
        ),
        "three_prime_end": (
            ("inapplicable", {None})
            if circular
            else ("known", {"hydroxyl" if rna else "hydroxyl_both_strands"})
        ),
    }
    for key, (status, values) in expected.items():
        actual = features.get(key)
        if actual is None:
            continue
        if actual.status == "unknown":
            problem(
                "unknown_payload_chemistry",
                f"The {key} feature remains unknown.",
                "unknown",
            )
        elif (
            actual.status != status or values is not None and actual.value not in values
        ):
            problem(
                "unsupported_payload_chemistry",
                f"The {key} declaration is outside this concrete profile.",
                "unsupported",
            )
    if (
        rna
        and (cap := features.get("cap")) is not None
        and (end := features.get("five_prime_end")) is not None
    ):
        if cap.status == end.status == "known" and (
            (cap.value in {"cap0", "cap1"}) != (end.value == "capped")
        ):
            problem(
                "cap_end_correspondence",
                "RNA cap state and source-specified 5-prime terminal chemistry disagree.",
            )
    if (
        rna
        and (tail := features.get("poly_a_tail")) is not None
        and tail.status == "known"
    ):
        tail_region = molecule.regions[-1] if kinds and kinds[-1] == "poly_a" else None
        expected_tail = f"exact:{tail_region.range.length}" if tail_region else "absent"
        if (
            tail.value != expected_tail
            or tail_region
            and set(molecule.sequence[tail_region.range.start : tail_region.range.end])
            != {"A"}
        ):
            problem(
                "poly_a_tail_correspondence",
                "A tail must have exact source-specified boundaries, length and adenine spelling; heterogeneous or nominal tails are unsupported.",
            )
    for region in molecule.regions:
        if region.kind == "cds":
            try:
                translated = translate_cds(
                    molecule.sequence[region.range.start : region.range.end],
                    molecule.alphabet,
                )
            except SerializationError as exc:
                problem("payload_coding_translation", str(exc))
            else:
                if translated != region.protein_sequence:
                    problem(
                        "payload_protein_correspondence",
                        "Translation must equal the independently supplied protein, including its terminal stop.",
                    )
    return diagnostics


def check_payload(
    candidate, reference, *, expected_reference_fingerprint, retained_sources
):
    """Check supplied expectations; a PASS is structural readiness, never promotion."""
    dependencies = payload_dependencies(
        candidate,
        reference,
        expected_reference_fingerprint=expected_reference_fingerprint,
        retained_sources=retained_sources,
    )
    diagnostics = []

    def problem(code, message):
        diagnostics.append(PayloadDiagnostic("fail", code, message))

    if reference.fingerprint != expected_reference_fingerprint:
        problem(
            "payload_authority_pin",
            "Supplied reference differs from the separately trusted authority pin.",
        )
    sources = (reference.primary_source, reference.sequence_source) + tuple(
        x.source for x in reference.reviews
    )
    if set(retained_sources) != {x.id for x in sources}:
        problem(
            "payload_source_inventory",
            "Retained inputs must contain exactly the declared primary, sequence and review sources.",
        )
    for source in sources:
        content = retained_sources.get(source.id)
        if not content or _sha(content) != source.sha256:
            problem(
                "payload_source_hash",
                f"Retained source {source.id!r} is missing, empty or has changed.",
            )
    reviews = reference.reviews
    if (
        len(reviews) != 2
        or {x.role for x in reviews} != {"extraction", "independent_review"}
        or len({x.reviewer for x in reviews}) != 2
    ):
        problem(
            "independent_payload_review",
            "Extraction and independent acceptance require two distinct declared reviewers.",
        )
    for review in reviews:
        try:
            statement = parse_json(
                retained_sources.get(review.source.id, b"").decode("utf-8")
            )
        except (UnicodeError, SerializationError):
            statement = None
        expected_statement = {
            "schema_version": REVIEW_SCHEMA_VERSION,
            "molecule_fingerprint": reference.expected.fingerprint,
            "primary_source_sha256": reference.primary_source.sha256,
            "sequence_source_sha256": reference.sequence_source.sha256,
            "reviewer": review.reviewer,
            "role": review.role,
            "decision": "accept",
            "source_kind": reference.source_kind,
        }
        if statement != expected_statement:
            problem(
                "payload_review_statement",
                "Retained review must accept these exact independent molecule and source identities.",
            )
    try:
        extracted, _ = normalize_sequence(
            retained_sources.get(reference.sequence_source.id, b"").decode("ascii"),
            reference.expected.alphabet,
        )
    except (UnicodeError, SerializationError):
        problem(
            "payload_source_sequence",
            "Retained sequence extraction is missing or violates narrow reference normalization.",
        )
    else:
        if extracted != reference.expected.sequence:
            problem(
                "payload_source_sequence",
                "Independent source extraction differs from the frozen expected molecule.",
            )
    if candidate.fingerprint != reference.expected.fingerprint:
        problem(
            "exact_payload_mismatch",
            "Candidate differs from the independently pinned whole-molecule expectation.",
        )
    diagnostics.extend(_profile_diagnostics(candidate))
    return PayloadResult(
        _outcome(diagnostics), dependencies, reference.source_kind, tuple(diagnostics)
    )
