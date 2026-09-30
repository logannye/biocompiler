"""Bounded source metadata and declared coverage, without source acquisition.

Byte receipts describe caller-supplied metadata; no bytes are retrieved or
checked here. A ``provided`` coverage entry is an availability declaration,
never molecular completeness, independent source review or empirical support.
Cross-record reference consistency is checked by a separate checker.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields as dataclass_fields
from datetime import datetime
import math
from typing import ClassVar
from urllib.parse import urlsplit

from biocompiler.artifacts.manifest import _Record, _hash, _plain_text
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_profile import HumanExperimentContext
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.serialization import fields, names, parse_json, require

SOURCE_PROFILE_VERSION = "biocompiler.circuit_source_metadata_profile.v0.1"
INVENTORY_POLICY_VERSION = "biocompiler.human_circuit_inventory_policy.v0.1"
FAMILY_IDS = frozenset(
    {
        "wroblewska_2015_mrna",
        "matsuura_2018_mrna",
        "post_polya_human",
        "adar_human",
        "promitar_human",
        "abe_2025_split_protein",
        "liu_2018_rna_control",
    }
)
COVERAGE_FIELDS = frozenset(
    {
        "construct_inventory",
        "input_states",
        "molecule_inventory",
        "controls",
        "transcript_boundaries",
        "chemistry",
        "component_authority",
        "independent_final_authority",
        "observations",
    }
)
GAP_STATUSES = frozenset(
    {
        "not_reviewed",
        "not_reported",
        "unavailable",
        "ambiguous",
        "conflicting",
        "provided",
    }
)
MAX_SOURCE_JSON_BYTES = 4_000_000
PUBLICATION_NEWLINE_BYTES = 1
MAX_METADATA_ITEMS = 100_000
MAX_METADATA_DEPTH = 64
MAX_METADATA_TEXT_BYTES = 16_384
MAX_SOURCE_DOCUMENTS = 128
MAX_SOURCE_CASES = 256
MAX_SOURCE_REVIEWS = 256
MAX_SOURCE_IDS = 32
MAX_RECORD_PINS = 16
MAX_REVIEW_FINDINGS = 32
MAX_DECLARED_BYTE_SIZE = 2**63 - 1


def _choice(value, choices, label):
    require(isinstance(value, str) and value in choices, f"Invalid {label}.")


def _text(value, label):
    try:
        _plain_text(value, label)
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise SerializationError(f"{label} must contain valid UTF-8.") from exc
    require(
        size <= MAX_METADATA_TEXT_BYTES,
        f"{label} exceeds the source metadata text limit.",
    )


def _bounded_metadata(value):
    stack = [(value, 0)]
    count = size = 0
    while stack:
        item, depth = stack.pop()
        count += 1
        require(count <= MAX_METADATA_ITEMS, "Source metadata item limit exceeded.")
        require(depth <= MAX_METADATA_DEPTH, "Source metadata nesting limit exceeded.")
        remaining = MAX_METADATA_ITEMS - count - len(stack)
        if isinstance(item, Mapping):
            require(
                2 * len(item) <= remaining,
                "Source metadata item limit exceeded.",
            )
            for key, child in item.items():
                require(isinstance(key, str), "Source metadata keys must be strings.")
                stack.extend(((key, depth + 1), (child, depth + 1)))
        elif isinstance(item, (tuple, list)):
            require(
                len(item) <= remaining,
                "Source metadata item limit exceeded.",
            )
            stack.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            try:
                text_size = len(item.encode("utf-8"))
            except UnicodeError as exc:
                raise SerializationError("Source metadata text must be UTF-8.") from exc
            require(
                text_size <= MAX_METADATA_TEXT_BYTES,
                "Source metadata text limit exceeded.",
            )
            size += text_size
            require(
                size <= MAX_SOURCE_JSON_BYTES, "Source metadata byte limit exceeded."
            )
        else:
            require(
                item is None or type(item) in (bool, int, float),
                "Source metadata must contain JSON values.",
            )
            require(
                type(item) is not float or math.isfinite(item),
                "Source metadata numbers must be finite.",
            )


class _SourceRecord(_Record):
    _fixed_fields: ClassVar[dict] = {}

    def to_dict(self):
        return super().to_dict() | self._fixed_fields

    @classmethod
    def from_dict(cls, data):
        _bounded_metadata(data)
        fields(
            data,
            {item.name for item in dataclass_fields(cls)}
            | {"schema_version"}
            | set(cls._fixed_fields),
            cls.__name__,
        )
        for key, value in cls._fixed_fields.items():
            require(
                type(data[key]) is type(value) and data[key] == value, f"Invalid {key}."
            )
        return super().from_dict(
            {key: value for key, value in data.items() if key not in cls._fixed_fields}
        )

    @classmethod
    def from_json(cls, text):
        require(isinstance(text, str), "Source metadata JSON must be text.")
        try:
            size = len(text.encode("utf-8"))
        except UnicodeError as exc:
            raise SerializationError("Source metadata JSON must be UTF-8.") from exc
        require(size <= MAX_SOURCE_JSON_BYTES, "Source metadata byte limit exceeded.")
        return cls.from_dict(parse_json(text))

    def to_json(self, *, indent=2):
        try:
            text = super().to_json(indent=indent)
            size = len(text.encode("utf-8"))
        except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
            raise SerializationError(
                f"Invalid source metadata encoding: {exc}"
            ) from exc
        require(
            size + PUBLICATION_NEWLINE_BYTES <= MAX_SOURCE_JSON_BYTES,
            "Source metadata byte limit exceeded (including publication newline).",
        )
        return text

    def _check_resources(self):
        _bounded_metadata(self.to_dict())
        self.to_json()


def _ids(values):
    require(
        isinstance(values, (tuple, list)) and len(values) <= MAX_SOURCE_IDS,
        "Source ID inventory limit exceeded.",
    )
    result = names(values, "Source IDs")
    for value in result:
        _text(value, "Source ID")
    return tuple(sorted(result))


def _records(values, cls, limit, label):
    require(
        isinstance(values, (tuple, list))
        and len(values) <= limit
        and all(isinstance(item, cls) for item in values),
        f"Invalid or oversized {label} inventory.",
    )
    return tuple(cls.from_dict(item.to_dict()) for item in values)


def _decode_records(values, cls, limit):
    require(
        isinstance(values, (tuple, list)) and len(values) <= limit,
        "Source metadata record inventory limit exceeded.",
    )
    return tuple(cls.from_dict(item) for item in values)


@dataclass(frozen=True)
class SourceDocument(_SourceRecord):
    """Metadata identity is distinct from a declared retrieved-file byte hash."""

    id: str
    version: str
    title: str
    url: str | None
    record_kind: str
    access_status: str
    reuse_status: str
    reuse_locator: str | None
    correction_status: str
    byte_sha256: str | None = None
    byte_size: int | None = None
    retrieved_at: str | None = None
    schema_version: ClassVar[str] = "biocompiler.circuit_source_document.v0.1"

    def __post_init__(self):
        for key in ("id", "version", "title"):
            _text(getattr(self, key), f"Source {key}")
        _choice(
            self.record_kind,
            {"article", "supplement", "deposit", "author_record"},
            "source record kind",
        )
        if self.url is None:
            require(
                self.record_kind == "author_record",
                "Only author records may explicitly lack a source URL.",
            )
        else:
            _text(self.url, "Source URL")
            try:
                parsed = urlsplit(self.url)
                # Reading port also validates its syntax and numeric range.
                _ = parsed.port
                valid_url = (
                    parsed.scheme in {"https", "http"}
                    and bool(parsed.hostname)
                    and parsed.username is None
                    and parsed.password is None
                    and not any(char.isspace() for char in self.url)
                )
            except ValueError as exc:
                raise SerializationError("Invalid source URL.") from exc
            require(
                valid_url,
                "Source URL must be an absolute HTTP(S) metadata link without credentials.",
            )
        _choice(
            self.access_status,
            {"not_retrieved", "retrieved", "unavailable", "restricted"},
            "source access status",
        )
        _choice(
            self.reuse_status,
            {"unreviewed", "permitted", "restricted"},
            "source reuse status",
        )
        _choice(
            self.correction_status,
            {"not_checked", "none_known", "corrected", "retracted"},
            "source correction status",
        )
        if self.reuse_locator is not None:
            _text(self.reuse_locator, "Reuse locator")
        require(
            self.reuse_status == "unreviewed" or self.reuse_locator is not None,
            "Reviewed reuse declarations require an explicit locator.",
        )
        receipt = (self.byte_sha256, self.byte_size, self.retrieved_at)
        if self.access_status == "retrieved":
            require(
                all(value is not None for value in receipt),
                "Retrieved sources require a complete byte receipt.",
            )
            _hash(self.byte_sha256, "Source byte hash")
            require(
                type(self.byte_size) is int
                and 0 <= self.byte_size <= MAX_DECLARED_BYTE_SIZE,
                "Declared source byte size is out of bounds.",
            )
            _text(self.retrieved_at, "Retrieval timestamp")
            try:
                timestamp = datetime.fromisoformat(self.retrieved_at)
            except ValueError as exc:
                raise SerializationError(
                    "Retrieval timestamp must be an ISO 8601 datetime."
                ) from exc
            require(
                "T" in self.retrieved_at and timestamp.utcoffset() is not None,
                "Retrieval timestamp requires an explicit timezone.",
            )
        else:
            require(
                all(value is None for value in receipt),
                "Unretrieved sources cannot carry a byte receipt.",
            )
        self._check_resources()


@dataclass(frozen=True)
class SourceGap(_SourceRecord):
    field: str
    status: str
    note: str
    source_ids: tuple[str, ...] = ()
    locator: str | None = None
    record_pins: tuple[PinnedIdentity, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.circuit_source_gap.v0.1"
    _decoders: ClassVar[dict] = {
        "record_pins": lambda value: _decode_records(
            value, PinnedIdentity, MAX_RECORD_PINS
        )
    }

    def __post_init__(self):
        _choice(self.field, COVERAGE_FIELDS, "source coverage field")
        _choice(self.status, GAP_STATUSES, "source gap status")
        _text(self.note, "Source gap note")
        object.__setattr__(self, "source_ids", _ids(self.source_ids))
        if self.locator is not None:
            _text(self.locator, "Coverage locator")
        pins = _records(
            self.record_pins, PinnedIdentity, MAX_RECORD_PINS, "coverage pin"
        )
        require(
            all(item.kind in {"source", "evidence"} for item in pins),
            "Coverage requires source or evidence record pins.",
        )
        object.__setattr__(
            self,
            "record_pins",
            tuple(
                sorted(
                    pins,
                    key=lambda item: (
                        item.kind,
                        item.id,
                        item.version,
                        item.content_fingerprint,
                    ),
                )
            ),
        )
        if self.status == "provided":
            require(
                bool(self.source_ids) and self.locator is not None and bool(pins),
                "Provided coverage requires source IDs, a locator and record pins.",
            )
        self._check_resources()


@dataclass(frozen=True)
class CircuitSourceCase(_SourceRecord):
    id: str
    family_id: str
    label: str
    source_ids: tuple[str, ...]
    coverage: tuple[SourceGap, ...]
    context: HumanExperimentContext | None = None
    schema_version: ClassVar[str] = "biocompiler.circuit_source_case.v0.1"
    _decoders: ClassVar[dict] = {
        "coverage": lambda value: _decode_records(
            value, SourceGap, len(COVERAGE_FIELDS)
        ),
        "context": lambda value: (
            None if value is None else HumanExperimentContext.from_dict(value)
        ),
    }

    def __post_init__(self):
        _text(self.id, "Source case ID")
        _text(self.label, "Source case label")
        _choice(self.family_id, FAMILY_IDS, "source case family")
        object.__setattr__(self, "source_ids", _ids(self.source_ids))
        require(
            bool(self.source_ids),
            "Source cases require a nonempty source ID inventory.",
        )
        coverage = _records(self.coverage, SourceGap, len(COVERAGE_FIELDS), "coverage")
        require(
            len(coverage) == len(COVERAGE_FIELDS)
            and {item.field for item in coverage} == COVERAGE_FIELDS,
            "Source cases require every coverage field exactly once.",
        )
        object.__setattr__(
            self, "coverage", tuple(sorted(coverage, key=lambda item: item.field))
        )
        if self.context is not None:
            require(
                isinstance(self.context, HumanExperimentContext),
                "Source case context must be human or explicitly unknown.",
            )
            object.__setattr__(
                self,
                "context",
                HumanExperimentContext.from_dict(self.context.to_dict()),
            )
        self._check_resources()


@dataclass(frozen=True)
class SourceReview(_SourceRecord):
    """An attributed metadata review declaration, not reviewer authentication."""

    id: str
    subject_kind: str
    subject_fingerprint: str
    reviewer_kind: str
    reviewer_id: str
    method: str
    findings: tuple[str, ...]
    disposition: str = "metadata_review_only"
    schema_version: ClassVar[str] = "biocompiler.circuit_source_review.v0.1"
    claim_scope: ClassVar[str] = (
        "metadata_only_no_source_bytes_sequence_or_empirical_validation"
    )
    _fixed_fields: ClassVar[dict] = {"claim_scope": claim_scope}

    def __post_init__(self):
        for key in ("id", "reviewer_id", "method"):
            _text(getattr(self, key), f"Review {key}")
        _choice(self.subject_kind, {"source", "case"}, "review subject kind")
        _choice(self.reviewer_kind, {"human", "software_agent"}, "reviewer kind")
        _hash(self.subject_fingerprint, "Review subject metadata")
        require(
            self.disposition == "metadata_review_only",
            "Source reviews cannot establish source, molecular or empirical validity.",
        )
        require(
            isinstance(self.findings, (tuple, list))
            and 0 < len(self.findings) <= MAX_REVIEW_FINDINGS,
            "Reviews require a bounded nonempty findings inventory.",
        )
        for finding in self.findings:
            _text(finding, "Metadata review finding")
        object.__setattr__(self, "findings", tuple(self.findings))
        self._check_resources()


@dataclass(frozen=True)
class CircuitSourceInventory(_SourceRecord):
    """A canonical metadata snapshot; cross-ID consistency is a separate check."""

    id: str
    version: str
    sources: tuple[SourceDocument, ...]
    cases: tuple[CircuitSourceCase, ...]
    reviews: tuple[SourceReview, ...]
    previous_inventory_fingerprint: str | None = None
    change_reason: str | None = None
    schema_version: ClassVar[str] = "biocompiler.circuit_source_inventory.v0.1"
    _decoders: ClassVar[dict] = {
        "sources": lambda value: _decode_records(
            value, SourceDocument, MAX_SOURCE_DOCUMENTS
        ),
        "cases": lambda value: _decode_records(
            value, CircuitSourceCase, MAX_SOURCE_CASES
        ),
        "reviews": lambda value: _decode_records(
            value, SourceReview, MAX_SOURCE_REVIEWS
        ),
    }

    def __post_init__(self):
        _text(self.id, "Source inventory ID")
        _text(self.version, "Source inventory version")
        for key, cls, limit in (
            ("sources", SourceDocument, MAX_SOURCE_DOCUMENTS),
            ("cases", CircuitSourceCase, MAX_SOURCE_CASES),
            ("reviews", SourceReview, MAX_SOURCE_REVIEWS),
        ):
            values = _records(getattr(self, key), cls, limit, key)
            object.__setattr__(
                self,
                key,
                tuple(sorted(values, key=lambda item: (item.id, item.fingerprint))),
            )
        require(
            (self.previous_inventory_fingerprint is None)
            == (self.change_reason is None),
            "Inventory history needs both a previous fingerprint and a change reason.",
        )
        if self.previous_inventory_fingerprint is not None:
            _hash(self.previous_inventory_fingerprint, "Previous inventory")
            _text(self.change_reason, "Inventory change reason")
        self._check_resources()
