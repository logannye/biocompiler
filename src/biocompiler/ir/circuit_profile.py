"""Human circuit scope declarations, without molecular or biological support.

The product target remains the complete original in-vivo human contract. A
literature experiment is separate source context, never a deployment target.
Typed immune lineage records declared eligibility; neither a lineage nor a
source pin establishes empirical applicability. R0 emits no molecules.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar

from biocompiler.artifacts.manifest import _Record, _hash, _plain_text
from biocompiler.compiler.acceptance import HumanAcceptanceRequest
from biocompiler.compiler.deployment import HumanDeploymentRequest
from biocompiler.compiler.human_behavior import HumanBehaviorRequest
from biocompiler.compiler.request import BuildRequest
from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.serialization import parse_json, require
from biocompiler.semantics.context import HumanTargetContext, PayloadFormat


PROFILE_VERSION = "biocompiler.human_circuit_profile.v0.1"
BOUNDARIES = frozenset({"import", "planning", "selection", "verification", "export"})
SOURCE_TYPES = (
    BuildRequest,
    HumanBehaviorRequest,
    HumanDeploymentRequest,
    HumanAcceptanceRequest,
)
MAX_PROFILE_JSON_BYTES = 1_000_000
# Published JSON files conventionally append one newline to ``to_json()``.
# The same byte budget covers that file and its subsequent import.
PUBLICATION_NEWLINE_BYTES = 1
MAX_PROFILE_ITEMS = 20_000
MAX_PROFILE_DEPTH = 64
MAX_PROFILE_TEXT_BYTES = 16_384
MAX_SOURCE_PINS = 16
MAX_ASSAY_CONDITIONS = 32


class ImmuneLineage(StrEnum):
    """Bounded recipient declarations, not a cell classifier or evidence result."""

    T_CELL = "t_cell"
    B_CELL = "b_cell"
    NK_CELL = "nk_cell"
    MONOCYTE = "monocyte"
    MACROPHAGE = "macrophage"
    DENDRITIC_CELL = "dendritic_cell"
    NEUTROPHIL = "neutrophil"
    EOSINOPHIL = "eosinophil"
    BASOPHIL = "basophil"
    MAST_CELL = "mast_cell"
    INNATE_LYMPHOID_CELL = "innate_lymphoid_cell"


def _choice(value, options, label):
    require(isinstance(value, str) and value in options, f"Invalid {label}.")


def _text(value, label):
    _plain_text(value, label)
    require(
        len(value.encode("utf-8")) <= MAX_PROFILE_TEXT_BYTES,
        f"{label} exceeds the circuit profile text limit.",
    )


def _bounded_tree(value):
    """Bound imported structure before recursively decoding legacy authority."""
    stack = [(value, 0)]
    count = 0
    text_bytes = 0
    while stack:
        item, depth = stack.pop()
        count += 1
        require(count <= MAX_PROFILE_ITEMS, "Circuit profile item limit exceeded.")
        require(depth <= MAX_PROFILE_DEPTH, "Circuit profile nesting limit exceeded.")
        if isinstance(item, Mapping):
            require(
                len(item) <= MAX_PROFILE_ITEMS - count,
                "Circuit profile item limit exceeded.",
            )
            for key, child in item.items():
                require(isinstance(key, str), "Circuit profile keys must be strings.")
                stack.extend(((key, depth + 1), (child, depth + 1)))
        elif isinstance(item, (tuple, list)):
            require(
                len(item) <= MAX_PROFILE_ITEMS - count,
                "Circuit profile item limit exceeded.",
            )
            stack.extend((child, depth + 1) for child in item)
        elif isinstance(item, str):
            try:
                size = len(item.encode("utf-8"))
            except UnicodeError as exc:
                raise SerializationError("Circuit profile text must be UTF-8.") from exc
            require(
                size <= MAX_PROFILE_TEXT_BYTES, "Circuit profile text limit exceeded."
            )
            text_bytes += size
            require(
                text_bytes <= MAX_PROFILE_JSON_BYTES,
                "Circuit profile byte limit exceeded.",
            )
        else:
            require(
                item is None or type(item) in (bool, int, float),
                "Circuit profile values must be JSON values.",
            )


class _ProfileRecord(_Record):
    @classmethod
    def from_dict(cls, data):
        _bounded_tree(data)
        return super().from_dict(data)

    @classmethod
    def from_json(cls, text):
        require(isinstance(text, str), "Circuit profile JSON must be text.")
        try:
            size = len(text.encode("utf-8"))
        except UnicodeError as exc:
            raise SerializationError("Circuit profile JSON must be UTF-8.") from exc
        require(size <= MAX_PROFILE_JSON_BYTES, "Circuit profile byte limit exceeded.")
        return cls.from_dict(parse_json(text))

    def to_json(self, *, indent=2):
        try:
            text = super().to_json(indent=indent)
            size = len(text.encode("utf-8"))
        except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
            raise SerializationError(
                f"Invalid circuit profile encoding: {exc}"
            ) from exc
        require(
            size + PUBLICATION_NEWLINE_BYTES <= MAX_PROFILE_JSON_BYTES,
            "Circuit profile byte limit exceeded (including publication newline).",
        )
        return text

    def _check_resources(self):
        _bounded_tree(self.to_dict())
        # Bound the default published representation, not only a compact form.
        # Nested original source wrappers participate in this complete budget.
        self.to_json()


def _optional(cls):
    return lambda value: None if value is None else cls.from_dict(value)


def _source_request_from_dict(data):
    if data is None:
        return None
    require(isinstance(data, Mapping), "Source request must be an object.")
    cls = next(
        (
            item
            for item in SOURCE_TYPES
            if item.schema_version == data.get("schema_version")
        ),
        None,
    )
    require(cls is not None, "Unsupported circuit source request schema.")
    return cls.from_dict(data)


def _source_pins(values):
    require(
        isinstance(values, (tuple, list)) and 0 < len(values) <= MAX_SOURCE_PINS,
        "Source context requires a bounded nonempty source pin inventory.",
    )
    return tuple(PinnedIdentity.from_dict(item) for item in values)


@dataclass(frozen=True)
class ImmuneRecipientIdentity(_ProfileRecord):
    """A typed declaration bound to the original target and its subtype claim.

    No free-text subtype inference occurs. Binding pins prevent reusing this
    declaration after an edit to either the target or its cell-subtype claim.
    Independent empirical eligibility remains unresolved even for cited claims.
    """

    lineage: ImmuneLineage
    target_fingerprint: str
    cell_subtype_claim_fingerprint: str
    eligibility_basis: str = "declared"
    empirical_support: str = "unestablished"
    schema_version: ClassVar[str] = "biocompiler.immune_recipient_identity.v0.1"
    _decoders: ClassVar[dict] = {"lineage": ImmuneLineage}

    def __post_init__(self):
        require(
            isinstance(self.lineage, ImmuneLineage), "Expected a typed immune lineage."
        )
        _hash(self.target_fingerprint, "Recipient target")
        _hash(self.cell_subtype_claim_fingerprint, "Recipient cell-subtype claim")
        require(
            self.eligibility_basis == "declared"
            and self.empirical_support == "unestablished",
            "An immune recipient declaration cannot assert empirical eligibility.",
        )
        self._check_resources()


@dataclass(frozen=True)
class HumanExperimentContext(_ProfileRecord):
    """Declared actual source experiment, never an intended deployment context.

    The source pins and locator make the assertion inspectable. They do not
    attest that the referenced experiment was retrieved, reviewed or validated.
    """

    system: str
    immune_classification: str
    cell_identity: str
    cell_state: str
    compartment: str
    delivery_mode: str
    sources: tuple[PinnedIdentity, ...]
    locator: str
    assay_conditions: tuple[str, ...]
    recipient_taxon_id: int = 9606
    immune_lineage: ImmuneLineage | None = None
    schema_version: ClassVar[str] = "biocompiler.human_experiment_context.v0.1"
    _decoders: ClassVar[dict] = {
        "sources": _source_pins,
        "immune_lineage": lambda value: None if value is None else ImmuneLineage(value),
    }

    def __post_init__(self):
        require(
            type(self.recipient_taxon_id) is int and self.recipient_taxon_id == 9606,
            "Human source experiments require recipient taxon 9606.",
        )
        _choice(
            self.system,
            {"human_cell_line", "primary_human_cells", "human_in_vivo"},
            "human experiment system",
        )
        _choice(
            self.immune_classification, {"immune", "nonimmune"}, "immune classification"
        )
        require(
            isinstance(self.immune_lineage, ImmuneLineage)
            if self.immune_classification == "immune"
            else self.immune_lineage is None,
            "Immune source context requires a typed lineage; nonimmune context has none.",
        )
        _choice(
            self.delivery_mode,
            {
                "dna_delivery",
                "rna_delivery",
                "dna_and_rna_delivery",
                "stable_dna_expression",
                "not_reported",
            },
            "source delivery mode",
        )
        for key in ("cell_identity", "cell_state", "compartment", "locator"):
            _text(getattr(self, key), f"Source experiment {key}")
        require(
            self.compartment != "abstract",
            "Source context needs a physical compartment.",
        )
        require(
            isinstance(self.sources, (tuple, list))
            and 0 < len(self.sources) <= MAX_SOURCE_PINS
            and all(isinstance(item, PinnedIdentity) for item in self.sources),
            "Source context requires a bounded nonempty source pin inventory.",
        )
        pins = tuple(PinnedIdentity.from_dict(item.to_dict()) for item in self.sources)
        require(
            all(item.kind in {"source", "evidence"} for item in pins),
            "Experiment context requires source or evidence pins.",
        )
        require(
            len({(item.kind, item.id, item.version) for item in pins}) == len(pins),
            "Duplicate or conflicting experiment source pins.",
        )
        for item in pins:
            _text(item.id, "Source pin id")
            _text(item.version, "Source pin version")
        object.__setattr__(
            self,
            "sources",
            tuple(sorted(pins, key=lambda item: (item.kind, item.id, item.version))),
        )
        require(
            isinstance(self.assay_conditions, (tuple, list))
            and 0 < len(self.assay_conditions) <= MAX_ASSAY_CONDITIONS,
            "Source context requires bounded explicit assay conditions.",
        )
        for condition in self.assay_conditions:
            _text(condition, "Assay condition")
        require(
            len(set(self.assay_conditions)) == len(self.assay_conditions),
            "Duplicate assay conditions.",
        )
        object.__setattr__(self, "assay_conditions", tuple(self.assay_conditions))
        self._check_resources()


@dataclass(frozen=True)
class CircuitProfileRequest(_ProfileRecord):
    """Freeze scope and operation authority without claiming implementation.

    ``molecular_form`` distinguishes DNA and RNA only at R0. It specifies no
    topology, sequence, chemistry or successful emission. Product source
    wrappers, when supplied, remain intact, including all unresolved contracts.
    """

    purpose: str
    mode: str
    molecular_form: PayloadFormat
    boundary: str
    target: HumanTargetContext | None = None
    recipient: ImmuneRecipientIdentity | None = None
    source_experiment: HumanExperimentContext | None = None
    source_request: object | None = None
    schema_version: ClassVar[str] = "biocompiler.circuit_profile_request.v0.1"
    _decoders: ClassVar[dict] = {
        "molecular_form": PayloadFormat,
        "target": _optional(HumanTargetContext),
        "recipient": _optional(ImmuneRecipientIdentity),
        "source_experiment": _optional(HumanExperimentContext),
        "source_request": _source_request_from_dict,
    }

    def __post_init__(self):
        _choice(
            self.purpose, {"human_immune_payload", "human_reference"}, "circuit purpose"
        )
        _choice(self.mode, {"exact_reproduction", "candidate_design"}, "circuit mode")
        _choice(self.boundary, BOUNDARIES, "circuit boundary")
        require(
            isinstance(self.molecular_form, PayloadFormat),
            "Expected a typed DNA/RNA molecular form.",
        )
        if self.source_experiment is not None:
            require(
                isinstance(self.source_experiment, HumanExperimentContext),
                "Expected typed human source experiment context.",
            )
            object.__setattr__(
                self,
                "source_experiment",
                HumanExperimentContext.from_dict(self.source_experiment.to_dict()),
            )
        if self.purpose == "human_reference":
            require(
                self.mode == "exact_reproduction",
                "Human reference requests require exact reproduction.",
            )
            require(
                self.source_experiment is not None,
                "Human reference requests require source experiment context.",
            )
            require(
                self.target is None
                and self.recipient is None
                and self.source_request is None,
                "Reference requests cannot carry an invented therapeutic target or source wrapper.",
            )
        else:
            require(
                isinstance(self.target, HumanTargetContext),
                "Product requests require the original human in-vivo target.",
            )
            object.__setattr__(
                self, "target", HumanTargetContext.from_dict(self.target.to_dict())
            )
            require(
                isinstance(self.recipient, ImmuneRecipientIdentity),
                "Product requests require typed immune recipient identity.",
            )
            object.__setattr__(
                self,
                "recipient",
                ImmuneRecipientIdentity.from_dict(self.recipient.to_dict()),
            )
            require(
                self.molecular_form == self.target.payload_format,
                "Molecular form must preserve the original target modality.",
            )
            require(
                self.recipient.target_fingerprint == self.target.fingerprint,
                "Stale or different recipient target binding.",
            )
            require(
                self.recipient.cell_subtype_claim_fingerprint
                == self.target.human_target.cell_subtype.fingerprint,
                "Stale or different recipient cell-subtype binding.",
            )
            if self.source_request is not None:
                require(
                    type(self.source_request) in SOURCE_TYPES,
                    "Unsupported original source request type.",
                )
                source_data = self.source_request.to_dict()
                _bounded_tree(source_data)
                source = _source_request_from_dict(source_data)
                require(
                    source.target is not None
                    and source.target.to_dict() == self.target.to_dict(),
                    "Circuit target must preserve the full original source target.",
                )
                object.__setattr__(self, "source_request", source)
        self._check_resources()
