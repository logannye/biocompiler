"""Independent checks of declared human-circuit source metadata relationships.

This module neither retrieves nor reads source bytes. A byte receipt remains a
caller declaration, and a provided record remains declared availability. Exact
molecular reproduction, empirical support and human admission are not assessed.
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
import json
import math
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir import circuit_profile, circuit_sources
from biocompiler.ir.intent import freeze_json, thaw_json
from biocompiler.ir.payload import hash_value
from biocompiler.ir.serialization import (
    JsonArtifact,
    fields,
    fingerprint,
    name,
    names,
    parse_json,
    require,
)
from biocompiler.semantics import admission
from biocompiler.verification.evidence import CheckOutcome

CHECKER_VERSION = "biocompiler.circuit_source_checker.v0.1"
MAX_ASSESSMENT_JSON_BYTES = 12_000_000
PUBLICATION_NEWLINE_BYTES = 1
MAX_DIAGNOSTICS = 4096
MAX_DIAGNOSTIC_TEXT_BYTES = 512
MAX_ASSESSMENT_ITEMS = 250_000
MAX_ASSESSMENT_DEPTH = 72
MAX_ASSESSMENT_TEXT_BYTES = 16_384
_FIXED = {
    "claim_scope": "metadata_consistency_only",
    "molecular_readiness": "unassessed",
    "empirical_validation": "unknown",
    "human_admission": "not_admitted",
    "source_bytes": "not_checked",
}
_DEPENDENCY_KEYS = {
    "inventory",
    "checker",
    "source_profile",
    "inventory_policy",
    "circuit_profile",
    "admission_policy",
}
_SUMMARY_KEYS = {
    "case_id",
    "case_fingerprint",
    "context_status",
    "declared_provided_fields",
    "gaps",
}


def _bounded_assessment(value):
    """Bound the complete imported tree before decoding or copying its records.

    Repeated shared values count at every occurrence, as they do in JSON. The
    pending stack counts toward the item budget, so wide nested containers
    cannot allocate a traversal stack larger than the declared limit.
    """
    stack = [(value, 0)]
    items = text_bytes = 0
    while stack:
        item, depth = stack.pop()
        items += 1
        require(items <= MAX_ASSESSMENT_ITEMS, "Source assessment item limit exceeded.")
        require(
            depth <= MAX_ASSESSMENT_DEPTH, "Source assessment nesting limit exceeded."
        )
        remaining = MAX_ASSESSMENT_ITEMS - items - len(stack)
        if isinstance(item, Mapping):
            require(
                2 * len(item) <= remaining, "Source assessment item limit exceeded."
            )
            for key, child in item.items():
                require(isinstance(key, str), "Source assessment keys must be strings.")
                stack.extend(((key, depth + 1), (child, depth + 1)))
        elif isinstance(item, (tuple, list)):
            require(len(item) <= remaining, "Source assessment item limit exceeded.")
            stack.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            require(
                len(item) <= MAX_ASSESSMENT_TEXT_BYTES,
                "Source assessment text limit exceeded.",
            )
            try:
                size = len(item.encode("utf-8"))
            except UnicodeError as error:
                raise SerializationError(
                    "Source assessment text must be UTF-8."
                ) from error
            require(
                size <= MAX_ASSESSMENT_TEXT_BYTES,
                "Source assessment text limit exceeded.",
            )
            text_bytes += size
            require(
                text_bytes + PUBLICATION_NEWLINE_BYTES <= MAX_ASSESSMENT_JSON_BYTES,
                "Source assessment aggregate text byte limit exceeded.",
            )
        else:
            require(
                item is None or type(item) in (bool, int, float),
                "Source assessment must contain JSON values.",
            )
            require(
                type(item) is not float or math.isfinite(item),
                "Source assessment numbers must be finite.",
            )
            require(
                type(item) is not int or item.bit_length() <= 64,
                "Source assessment integer exceeds metadata bounds.",
            )


def _ref(value):
    """Keep large declared IDs in the snapshot, with bounded diagnostic references."""
    return value if len(value.encode("utf-8")) <= 80 else "sha256-" + fingerprint(value)


class _Diagnostics:
    """Bound repeated failures without hiding failure or dropping the inventory."""

    def __init__(self):
        self.values = set()
        self.omitted_occurrences = 0

    def add(self, message):
        if message in self.values:
            return
        if len(self.values) < MAX_DIAGNOSTICS - 1:
            self.values.add(message)
        else:
            self.omitted_occurrences += 1

    def messages(self):
        values = set(self.values)
        if self.omitted_occurrences:
            values.add(
                "additional_metadata_failure_occurrences_omitted:"
                + str(self.omitted_occurrences)
            )
        return tuple(sorted(values))

    def __bool__(self):
        return bool(self.values or self.omitted_occurrences)


def _dependencies(inventory):
    return {
        "inventory": inventory.fingerprint,
        "checker": CHECKER_VERSION,
        "source_profile": circuit_sources.SOURCE_PROFILE_VERSION,
        "inventory_policy": circuit_sources.INVENTORY_POLICY_VERSION,
        "circuit_profile": circuit_profile.PROFILE_VERSION,
        "admission_policy": admission.ADMISSION_POLICY_VERSION,
    }


def _summary(case):
    return {
        "case_id": case.id,
        "case_fingerprint": case.fingerprint,
        "context_status": "unknown" if case.context is None else "declared_unverified",
        "declared_provided_fields": sorted(
            gap.field for gap in case.coverage if gap.status == "provided"
        ),
        "gaps": [
            gap.to_dict()
            for gap in sorted(case.coverage, key=lambda value: value.field)
            if gap.status != "provided"
        ],
    }


def _checked_summaries(values, inventory):
    require(
        isinstance(values, (tuple, list)) and len(values) == len(inventory.cases),
        "Source assessment must retain a summary for every case.",
    )
    summaries = []
    for value in values:
        fields(value, _SUMMARY_KEYS, "Source case summary")
        name(value["case_id"], "Case summary ID")
        require(len(value["case_id"]) <= 16_384, "Case summary ID exceeds text limit.")
        hash_value(value["case_fingerprint"], "Case summary identity")
        require(
            isinstance(value["context_status"], str)
            and value["context_status"] in {"unknown", "declared_unverified"},
            "A source context summary cannot establish applicability.",
        )
        provided = names(value["declared_provided_fields"], "Declared provided fields")
        require(
            set(provided) <= circuit_sources.COVERAGE_FIELDS,
            "Unknown declared coverage field.",
        )
        require(
            isinstance(value["gaps"], (tuple, list))
            and len(value["gaps"]) <= len(circuit_sources.COVERAGE_FIELDS),
            "Invalid source gap summary array.",
        )
        gaps = tuple(
            circuit_sources.SourceGap.from_dict(item) for item in value["gaps"]
        )
        gap_fields = {item.field for item in gaps}
        require(
            len(gap_fields) == len(gaps)
            and all(item.status != "provided" for item in gaps)
            and not gap_fields.intersection(provided)
            and gap_fields | set(provided) == circuit_sources.COVERAGE_FIELDS,
            "Source summary must retain every coverage field without promotion.",
        )
        summaries.append(
            {
                "case_id": value["case_id"],
                "case_fingerprint": value["case_fingerprint"],
                "context_status": value["context_status"],
                "declared_provided_fields": sorted(provided),
                "gaps": [
                    item.to_dict() for item in sorted(gaps, key=lambda gap: gap.field)
                ],
            }
        )
    require(
        Counter((item["case_id"], item["case_fingerprint"]) for item in summaries)
        == Counter((item.id, item.fingerprint) for item in inventory.cases),
        "Source summaries differ from retained case identities.",
    )
    return tuple(
        freeze_json(item)
        for item in sorted(
            summaries, key=lambda item: (item["case_id"], item["case_fingerprint"])
        )
    )


@dataclass(frozen=True)
class CircuitSourcesAssessment(JsonArtifact):
    """A historical metadata consistency report, never source-byte validation."""

    inventory: circuit_sources.CircuitSourceInventory
    outcome: CheckOutcome
    diagnostics: tuple[str, ...]
    case_summaries: tuple[Mapping, ...]
    dependencies: Mapping
    schema_version: ClassVar[str] = "biocompiler.circuit_sources_assessment.v0.1"

    def __post_init__(self):
        require(
            isinstance(self.inventory, circuit_sources.CircuitSourceInventory),
            "A source assessment requires the complete inventory snapshot.",
        )
        require(
            isinstance(self.outcome, CheckOutcome)
            and self.outcome in {CheckOutcome.PASS, CheckOutcome.FAIL},
            "Source assessments only report metadata consistency PASS or FAIL.",
        )
        inventory_data = self.inventory.to_dict()
        _bounded_assessment(
            {
                "schema_version": self.schema_version,
                **_FIXED,
                "inventory": inventory_data,
                "outcome": self.outcome.value,
                "diagnostics": self.diagnostics,
                "case_summaries": self.case_summaries,
                "dependencies": self.dependencies,
            }
        )
        object.__setattr__(
            self,
            "inventory",
            circuit_sources.CircuitSourceInventory.from_dict(inventory_data),
        )
        require(
            isinstance(self.diagnostics, (tuple, list))
            and len(self.diagnostics) <= MAX_DIAGNOSTICS,
            "Source assessment diagnostic limit exceeded.",
        )
        diagnostics = names(self.diagnostics, "Source metadata diagnostics")
        try:
            diagnostic_sizes = tuple(len(item.encode("utf-8")) for item in diagnostics)
        except UnicodeError as error:
            raise SerializationError(
                "Source diagnostics must be valid UTF-8."
            ) from error
        require(
            all(size <= MAX_DIAGNOSTIC_TEXT_BYTES for size in diagnostic_sizes),
            "Source assessment diagnostic text limit exceeded.",
        )
        require(
            bool(diagnostics) == (self.outcome is CheckOutcome.FAIL),
            "Metadata consistency outcome disagrees with its diagnostics.",
        )
        object.__setattr__(self, "diagnostics", tuple(sorted(diagnostics)))
        object.__setattr__(
            self,
            "case_summaries",
            _checked_summaries(self.case_summaries, self.inventory),
        )
        fields(self.dependencies, _DEPENDENCY_KEYS, "Source metadata dependencies")
        hash_value(self.dependencies["inventory"], "Source inventory authority")
        require(
            self.dependencies["inventory"] == self.inventory.fingerprint,
            "Assessment inventory dependency differs from the retained snapshot.",
        )
        for key in _DEPENDENCY_KEYS - {"inventory"}:
            name(self.dependencies[key], f"Source dependency {key}")
            require(
                len(self.dependencies[key]) <= 256,
                "Source policy identity is too long.",
            )
        object.__setattr__(self, "dependencies", freeze_json(self.dependencies))
        self.to_json()

    @property
    def claim_scope(self):
        return _FIXED["claim_scope"]

    @property
    def molecular_readiness(self):
        return _FIXED["molecular_readiness"]

    @property
    def empirical_validation(self):
        return _FIXED["empirical_validation"]

    @property
    def human_admission(self):
        return _FIXED["human_admission"]

    @property
    def source_bytes(self):
        return _FIXED["source_bytes"]

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            **_FIXED,
            "inventory": self.inventory.to_dict(),
            "outcome": self.outcome.value,
            "diagnostics": list(self.diagnostics),
            "case_summaries": [thaw_json(item) for item in self.case_summaries],
            "dependencies": thaw_json(self.dependencies),
        }

    def to_json(self, *, indent=2):
        require(
            indent is None or (type(indent) is int and 0 <= indent <= 8),
            "Source assessment indentation must be None or an integer from 0 to 8.",
        )
        data = self.to_dict()
        _bounded_assessment(data)
        encoder = json.JSONEncoder(
            sort_keys=True, indent=indent, ensure_ascii=False, allow_nan=False
        )
        chunks, size = [], PUBLICATION_NEWLINE_BYTES
        try:
            for chunk in encoder.iterencode(data):
                size += len(chunk.encode("utf-8"))
                require(
                    size <= MAX_ASSESSMENT_JSON_BYTES,
                    "Source assessment byte limit exceeded (including publication newline).",
                )
                chunks.append(chunk)
        except (ValueError, TypeError, UnicodeError, RecursionError) as error:
            if isinstance(error, SerializationError):
                raise
            raise SerializationError(
                f"Invalid source assessment encoding: {error}"
            ) from error
        return "".join(chunks)

    @classmethod
    def from_dict(cls, data):
        _bounded_assessment(data)
        fields(
            data,
            {
                "schema_version",
                "inventory",
                "outcome",
                "diagnostics",
                "case_summaries",
                "dependencies",
                *_FIXED,
            },
            "CircuitSourcesAssessment",
        )
        require(
            data["schema_version"] == cls.schema_version,
            "Unsupported source assessment schema.",
        )
        for key, value in _FIXED.items():
            require(
                type(data[key]) is str and data[key] == value,
                f"Invalid source assessment {key}.",
            )
        try:
            return cls(
                circuit_sources.CircuitSourceInventory.from_dict(data["inventory"]),
                CheckOutcome(data["outcome"]),
                data["diagnostics"],
                data["case_summaries"],
                data["dependencies"],
            )
        except (ValueError, TypeError) as error:
            if isinstance(error, SerializationError):
                raise
            raise SerializationError(f"Invalid source assessment: {error}") from error

    @classmethod
    def from_json(cls, text):
        require(isinstance(text, str), "Source assessment JSON must be text.")
        require(
            len(text) <= MAX_ASSESSMENT_JSON_BYTES,
            "Source assessment byte limit exceeded.",
        )
        try:
            size = len(text.encode("utf-8"))
        except UnicodeError as error:
            raise SerializationError(
                "Source assessment must be valid UTF-8."
            ) from error
        require(
            size <= MAX_ASSESSMENT_JSON_BYTES, "Source assessment byte limit exceeded."
        )
        return cls.from_dict(parse_json(text))


def _index(records, kind, errors):
    result = {}
    for record in records:
        if record.id in result:
            errors.add(f"duplicate_{kind}_id:{_ref(record.id)}")
        else:
            result[record.id] = record
    return result


def _pin_errors(pin, source_ids, documents, prefix, errors):
    if pin.id not in source_ids:
        errors.add(f"{prefix}:pin_source_not_in_declared_sources:{_ref(pin.id)}")
    document = documents.get(pin.id)
    if document is None:
        errors.add(f"{prefix}:unknown_pin_source:{_ref(pin.id)}")
        return
    if pin.version != document.version:
        errors.add(f"{prefix}:pin_version_mismatch:{_ref(pin.id)}")
    if document.access_status != "retrieved" or document.byte_sha256 is None:
        errors.add(f"{prefix}:source_byte_receipt_missing:{_ref(pin.id)}")
    elif pin.content_fingerprint != document.byte_sha256:
        errors.add(f"{prefix}:pin_byte_receipt_mismatch:{_ref(pin.id)}")


def check_circuit_sources(inventory):
    """Check metadata references only; preserve missing fields and contexts."""
    require(
        isinstance(inventory, circuit_sources.CircuitSourceInventory),
        "Expected a complete source metadata inventory.",
    )
    inventory = circuit_sources.CircuitSourceInventory.from_dict(inventory.to_dict())
    errors = _Diagnostics()
    documents = _index(inventory.sources, "source", errors)
    _index(inventory.cases, "case", errors)
    _index(inventory.reviews, "review", errors)
    for case in inventory.cases:
        prefix = f"case:{_ref(case.id)}"
        for source_id in case.source_ids:
            if source_id not in documents:
                errors.add(f"{prefix}:unknown_source:{_ref(source_id)}")
        for gap in case.coverage:
            gap_prefix = f"{prefix}:coverage:{gap.field}"
            for source_id in gap.source_ids:
                if source_id not in documents:
                    errors.add(f"{gap_prefix}:unknown_source:{_ref(source_id)}")
                if source_id not in case.source_ids:
                    errors.add(f"{gap_prefix}:source_not_in_case:{_ref(source_id)}")
            for pin in gap.record_pins:
                _pin_errors(pin, gap.source_ids, documents, gap_prefix, errors)
            if gap.status == "provided" and set(gap.source_ids) != {
                pin.id for pin in gap.record_pins
            }:
                errors.add(f"{gap_prefix}:provided_sources_require_byte_receipt_pins")
        if case.context is not None:
            for pin in case.context.sources:
                _pin_errors(
                    pin, case.source_ids, documents, f"{prefix}:context", errors
                )
    for review in inventory.reviews:
        subjects = (
            inventory.sources if review.subject_kind == "source" else inventory.cases
        )
        matches = [
            subject
            for subject in subjects
            if subject.fingerprint == review.subject_fingerprint
        ]
        if not matches:
            errors.add(
                f"review:{_ref(review.id)}:stale_or_unknown_{review.subject_kind}_fingerprint"
            )
        elif len(matches) != 1:
            errors.add(
                f"review:{_ref(review.id)}:ambiguous_{review.subject_kind}_fingerprint"
            )
    return CircuitSourcesAssessment(
        inventory,
        CheckOutcome.FAIL if errors else CheckOutcome.PASS,
        errors.messages(),
        tuple(_summary(case) for case in inventory.cases),
        _dependencies(inventory),
    )


def verify_circuit_sources(assessment, *, expected_inventory):
    """Replay current checks against independently supplied complete authority.

    A successfully replayed FAIL is still a metadata consistency failure. Even
    PASS verifies only declared relationships; it establishes no source-byte,
    molecular, experimental, or human-use result.
    """
    require(
        isinstance(assessment, CircuitSourcesAssessment)
        and isinstance(expected_inventory, circuit_sources.CircuitSourceInventory),
        "Fresh source verification requires an assessment and independent complete inventory.",
    )
    saved = CircuitSourcesAssessment.from_dict(assessment.to_dict())
    inventory = circuit_sources.CircuitSourceInventory.from_dict(
        expected_inventory.to_dict()
    )
    require(
        saved.inventory.to_dict() == inventory.to_dict(),
        "Saved source assessment differs from the independent expected inventory.",
    )
    current = check_circuit_sources(inventory)
    require(
        saved.to_dict() == current.to_dict(),
        "Saved source assessment differs from current independent metadata checks.",
    )
    return current


def inspect_circuit_source_readiness(inventory, *, case_id=None):
    """Report declared source gaps without conferring case acceptance.

    The complete inventory is freshly checked for metadata consistency. Source
    bytes, their interpretation, complete molecular forms and family semantics
    are not evaluated. Consequently even fully provided metadata and current
    human-attributed metadata reviews leave case readiness unestablished.
    No source locator is opened or executed, and no molecule is reconstructed.
    """
    assessment = check_circuit_sources(inventory)
    inventory = assessment.inventory
    if case_id is not None:
        circuit_sources._text(case_id, "Selected source case ID")
        selected = tuple(case for case in inventory.cases if case.id == case_id)
        require(
            len(selected) == 1,
            "Selected source case ID must identify exactly one inventory case.",
        )
    else:
        selected = inventory.cases

    # Retain duplicate records in the report. A lookup that silently picked one
    # could hide precisely the ambiguous identities the metadata checker rejects.
    document_counts = Counter(source.id for source in inventory.sources)
    sources = []
    for source in inventory.sources:
        reviews = tuple(
            review
            for review in inventory.reviews
            if review.subject_kind == "source"
            and review.subject_fingerprint == source.fingerprint
        )
        sources.append(
            {
                "source_id": source.id,
                "source_fingerprint": source.fingerprint,
                "identity_status": (
                    "unique" if document_counts[source.id] == 1 else "ambiguous"
                ),
                "access_status": source.access_status,
                "byte_receipt": (
                    "declared_unverified"
                    if source.byte_sha256 is not None
                    else "missing"
                ),
                "reuse_status": source.reuse_status,
                "correction_status": source.correction_status,
                "metadata_review_ids": [review.id for review in reviews],
                "metadata_review_status": (
                    "declared_current_metadata_only" if reviews else "missing"
                ),
            }
        )

    cases = []
    for case in selected:
        reviews = tuple(
            review
            for review in inventory.reviews
            if review.subject_kind == "case"
            and review.subject_fingerprint == case.fingerprint
        )
        cases.append(
            {
                "case_id": case.id,
                "case_fingerprint": case.fingerprint,
                "family_id": case.family_id,
                "readiness": "not_established",
                "context_status": (
                    "unknown" if case.context is None else "declared_unverified"
                ),
                "source_ids": list(case.source_ids),
                "missing_source_ids": [
                    identity
                    for identity in case.source_ids
                    if identity not in document_counts
                ],
                "ambiguous_source_ids": [
                    identity
                    for identity in case.source_ids
                    if document_counts[identity] > 1
                ],
                "metadata_review_ids": [review.id for review in reviews],
                "metadata_review_status": (
                    "declared_current_metadata_only" if reviews else "missing"
                ),
                "fields": [
                    {
                        "field": gap.field,
                        "availability": gap.status,
                        "verification": "not_checked",
                        "note": gap.note,
                        "source_ids": list(gap.source_ids),
                        "locator": gap.locator,
                        "record_pins": [pin.to_dict() for pin in gap.record_pins],
                    }
                    for gap in case.coverage
                ],
                "missing_field_count": sum(
                    gap.status != "provided" for gap in case.coverage
                ),
                "declared_provided_field_count": sum(
                    gap.status == "provided" for gap in case.coverage
                ),
            }
        )

    report = {
        "schema_version": "biocompiler.circuit_source_readiness_inspection.v0.1",
        "scope": "source_metadata_gap_inspection",
        "inventory_fingerprint": inventory.fingerprint,
        "metadata_assessment_fingerprint": assessment.fingerprint,
        "metadata_consistency": assessment.outcome.value,
        "diagnostics": list(assessment.diagnostics),
        "case_inventory_status": "declared" if inventory.cases else "missing",
        "selected_case_id": case_id,
        "readiness": "not_established",
        "source_bytes": "not_checked",
        "empirical_validation": "unknown",
        "human_admission": "not_admitted",
        "unresolved_acceptance_gates": [
            "retained_source_bytes_and_reuse_not_verified",
            "independent_component_and_final_authority_not_reviewed",
            "complete_requested_molecular_form_not_assessed",
            "experiment_material_observation_mapping_not_validated",
            "family_correspondence_not_assessed",
        ],
        "sources": sources,
        "cases": cases,
    }
    _bounded_assessment(report)
    size = PUBLICATION_NEWLINE_BYTES
    encoder = json.JSONEncoder(
        indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False
    )
    for chunk in encoder.iterencode(report):
        size += len(chunk.encode("utf-8"))
        require(
            size <= MAX_ASSESSMENT_JSON_BYTES,
            "Source readiness report byte limit exceeded (including publication newline).",
        )
    return report
