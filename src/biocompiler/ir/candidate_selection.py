"""Frozen bounded molecular candidate choices and automatically derived layouts.

Eligibility here is structural. Neither selection nor layout establishes that a
sequence realizes the source program's sensing, control or therapeutic behavior.
"""

from dataclasses import dataclass
from types import MappingProxyType
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir.molecular_design import (
    FragmentPlacement,
    SequenceFragment,
    _Record,
    _decode_records,
    _records,
)
from biocompiler.ir.payload import PayloadFeature, hash_value, name
from biocompiler.ir.serialization import fingerprint, names, require
from biocompiler.semantics.context import TargetContext

SELECTION_PROFILE_VERSION = "biocompiler.candidate_selection_profile.v0.1"
LAYOUT_PROFILE_VERSION = "biocompiler.candidate_layout_profile.v0.1"
MAX_ALTERNATIVES = 256
REJECTION_MESSAGES = MappingProxyType(
    {
        "architecture_not_allowed": "Architecture is outside the authored allowed architecture identities.",
        "cds_part_not_allowed": "CDS part is outside the authored allowed CDS identities.",
        "max_length_exceeded": "Exact assembled nucleotide length exceeds the authored maximum.",
        "unsupported_modality": "This candidate family supports mature linear RNA only; no DNA conversion is implemented.",
    }
)


@dataclass(frozen=True)
class CandidateRejection(_Record):
    status: str
    code: str
    message: str
    schema_version: ClassVar[str] = "biocompiler.candidate_rejection.v0.1"

    def __post_init__(self):
        require(
            self.status in ("fail", "unknown", "unsupported"),
            "Invalid candidate rejection status.",
        )
        name(self.code, "Rejection code")
        name(self.message, "Rejection message")


@dataclass(frozen=True)
class CandidateAlternative(_Record):
    architecture_id: str
    cds_part_id: str
    sequence_length: int
    rejections: tuple[CandidateRejection, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.candidate_alternative.v0.1"
    _decoders: ClassVar[dict] = {
        "rejections": lambda value: _decode_records(value, CandidateRejection),
    }
    _derived: ClassVar[tuple[str, ...]] = ("id", "status", "rejection_reasons")

    def __post_init__(self):
        name(self.architecture_id, "Architecture id")
        name(self.cds_part_id, "CDS part id")
        require(
            type(self.sequence_length) is int and self.sequence_length > 0,
            "Candidate length must be a positive integer.",
        )
        object.__setattr__(
            self,
            "rejections",
            _records(self.rejections, CandidateRejection, "candidate rejections"),
        )

    @property
    def id(self):
        return "alternative:" + fingerprint(
            {"architecture_id": self.architecture_id, "cds_part_id": self.cds_part_id}
        )

    @property
    def status(self):
        statuses = {item.status for item in self.rejections}
        return next(
            (
                value
                for status, value in (
                    ("fail", "rejected"),
                    ("unsupported", "unsupported"),
                    ("unknown", "unknown"),
                )
                if status in statuses
            ),
            "eligible",
        )

    @property
    def rejection_reasons(self):
        return tuple(item.code for item in self.rejections)


@dataclass(frozen=True)
class CandidateSelection(_Record):
    request_fingerprint: str
    requirements_fingerprint: str
    alternatives: tuple[CandidateAlternative, ...]
    selected_alternative_id: str | None
    diagnostics: tuple[str, ...] = ()
    search_complete: bool = True
    profile: str = SELECTION_PROFILE_VERSION
    schema_version: ClassVar[str] = "biocompiler.candidate_selection.v0.1"
    _decoders: ClassVar[dict] = {
        "alternatives": lambda value: _decode_records(value, CandidateAlternative),
    }
    _derived: ClassVar[tuple[str, ...]] = ("outcome", "nodes")

    def __post_init__(self):
        hash_value(self.request_fingerprint, "Selection request")
        hash_value(self.requirements_fingerprint, "Selection requirements")
        object.__setattr__(
            self,
            "alternatives",
            _records(self.alternatives, CandidateAlternative, "alternatives"),
        )
        require(
            len(self.alternatives) <= MAX_ALTERNATIVES,
            "Candidate enumeration exceeds the fixed bound.",
        )
        require(
            len({item.id for item in self.alternatives}) == len(self.alternatives),
            "Duplicate candidate alternatives.",
        )
        require(
            tuple(
                sorted(
                    self.alternatives,
                    key=lambda item: (item.architecture_id, item.cds_part_id),
                )
            )
            == self.alternatives,
            "Candidate alternatives require deterministic architecture/CDS order.",
        )
        object.__setattr__(
            self, "diagnostics", names(self.diagnostics, "Selection diagnostics")
        )
        for code in self.diagnostics:
            name(code, "Selection diagnostic")
        require(
            self.search_complete is True and self.profile == SELECTION_PROFILE_VERSION,
            "This profile requires complete bounded enumeration.",
        )
        if self.selected_alternative_id is not None:
            name(self.selected_alternative_id, "Selected alternative id")
            require(
                self.selected is not None and self.selected.status == "eligible",
                "Selected alternative must be an eligible enumerated candidate.",
            )

    @property
    def selected(self):
        return next(
            (
                item
                for item in self.alternatives
                if item.id == self.selected_alternative_id
            ),
            None,
        )

    @property
    def outcome(self):
        return (
            "selected" if self.selected_alternative_id is not None else "no_candidate"
        )

    @property
    def nodes(self):
        return tuple(
            {"id": item.id, "kind": "candidate_alternative"}
            for item in self.alternatives
        )


@dataclass(frozen=True)
class CandidateLayout(_Record):
    request_fingerprint: str
    requirements_fingerprint: str
    selection_fingerprint: str
    selected_alternative_id: str
    architecture_id: str
    cds_part_id: str
    molecule_id: str
    target: TargetContext
    fragments: tuple[SequenceFragment, ...]
    placements: tuple[FragmentPlacement, ...]
    features: tuple[PayloadFeature, ...]
    unknown_features: tuple[str, ...] = ()
    profile: str = LAYOUT_PROFILE_VERSION
    schema_version: ClassVar[str] = "biocompiler.candidate_layout.v0.1"
    _decoders: ClassVar[dict] = {
        "target": TargetContext.from_dict,
        "fragments": lambda value: _decode_records(value, SequenceFragment),
        "placements": lambda value: _decode_records(value, FragmentPlacement),
        "features": lambda value: _decode_records(value, PayloadFeature),
    }
    _derived: ClassVar[tuple[str, ...]] = ("nodes",)

    def __post_init__(self):
        for key in (
            "request_fingerprint",
            "requirements_fingerprint",
            "selection_fingerprint",
        ):
            hash_value(getattr(self, key), key)
        for key in (
            "selected_alternative_id",
            "architecture_id",
            "cds_part_id",
            "molecule_id",
        ):
            name(getattr(self, key), key)
        require(
            isinstance(self.target, TargetContext),
            "Candidate layout must retain its original target.",
        )
        try:
            self.target.to_json(indent=None).encode("utf-8")
        except UnicodeError as exc:
            raise SerializationError(
                "Candidate target must contain valid UTF-8 text."
            ) from exc
        for key, cls in (
            ("fragments", SequenceFragment),
            ("placements", FragmentPlacement),
            ("features", PayloadFeature),
        ):
            object.__setattr__(self, key, _records(getattr(self, key), cls, key))
        require(
            0 < len(self.fragments) <= 4 and 0 < len(self.placements) <= 4,
            "Candidate layouts require one bounded single-CDS RNA assembly.",
        )
        require(
            len({item.id for item in self.fragments}) == len(self.fragments),
            "Duplicate candidate fragments.",
        )
        require(
            len({item.region_id for item in self.placements}) == len(self.placements),
            "Duplicate candidate regions.",
        )
        require(
            len({item.feature for item in self.features}) == len(self.features),
            "Duplicate candidate features.",
        )
        object.__setattr__(
            self,
            "unknown_features",
            names(self.unknown_features, "Unknown candidate features"),
        )
        for value in self.unknown_features:
            name(value, "Unknown candidate feature")
        require(
            self.profile == LAYOUT_PROFILE_VERSION,
            "Unsupported candidate layout profile.",
        )

    @property
    def nodes(self):
        return tuple(
            {"id": item.region_id, "kind": "fragment_placement"}
            for item in self.placements
        )
