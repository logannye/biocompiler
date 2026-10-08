"""Human in-vivo target declarations, never certificates of biological validity.

The first profile records explicit applicability and evidence obligations. Source
pins and caller-supplied context labels identify assertions, not verified facts.
No record in this module admits a component, model or therapeutic payload.
"""

from __future__ import annotations

from dataclasses import dataclass, fields as dataclass_fields
from typing import ClassVar

from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.serialization import JsonArtifact, fields, name, names, require
from biocompiler.semantics.component_contracts import ValueDomain


def _choice(value, choices, label):
    require(isinstance(value, str) and value in choices, f"Invalid {label}.")


def _records(values, cls, label):
    require(isinstance(values, (tuple, list)), f"{label} must be an array.")
    require(all(isinstance(item, cls) for item in values), f"Invalid {label}.")
    require(len({item.id for item in values}) == len(values), f"Duplicate {label} IDs.")
    return tuple(sorted(values, key=lambda item: item.id))


def _decode_records(values, cls):
    require(isinstance(values, (tuple, list)), "Records must be an array.")
    return tuple(cls.from_dict(item) for item in values)


class _TargetRecord(JsonArtifact):
    _decoders: ClassVar[dict] = {}
    _fixed_fields: ClassVar[dict] = {}

    def to_dict(self):
        def encode(value):
            if isinstance(value, JsonArtifact):
                return value.to_dict()
            if isinstance(value, tuple):
                return [encode(item) for item in value]
            return value

        return {
            "schema_version": self.schema_version,
            **self._fixed_fields,
            **{
                item.name: encode(getattr(self, item.name))
                for item in dataclass_fields(self)
            },
        }

    @classmethod
    def from_dict(cls, data):
        fields(
            data,
            {item.name for item in dataclass_fields(cls)}
            | {"schema_version"}
            | set(cls._fixed_fields),
            cls.__name__,
        )
        require(
            data["schema_version"] == cls.schema_version,
            f"Unsupported {cls.__name__} schema.",
        )
        for key, value in cls._fixed_fields.items():
            require(
                type(data[key]) is type(value) and data[key] == value, f"Invalid {key}."
            )
        try:
            return cls(
                **{
                    item.name: cls._decoders.get(item.name, lambda value: value)(
                        data[item.name]
                    )
                    for item in dataclass_fields(cls)
                }
            )
        except SerializationError:
            raise
        except (
            TypeError,
            ValueError,
            KeyError,
            AttributeError,
            OverflowError,
            RecursionError,
        ) as error:
            raise SerializationError(f"Invalid {cls.__name__}: {error}") from error

    def _check_utf8(self):
        try:
            self.to_json(indent=None).encode("utf-8")
        except UnicodeError as error:
            raise SerializationError(
                "Human target strings must be valid UTF-8."
            ) from error


@dataclass(frozen=True)
class TargetClaim(_TargetRecord):
    """An explicit scope or assumption; ``cited`` does not mean validated."""

    description: str
    basis: str
    evidence_ids: tuple[str, ...]
    limitations: str
    schema_version: ClassVar[str] = "biocompiler.target_claim.v0.1"

    def __post_init__(self):
        name(self.description, "Target claim description")
        name(self.limitations, "Target claim limitations")
        _choice(self.basis, {"unestablished", "assumed", "cited"}, "target claim basis")
        ids = tuple(sorted(names(self.evidence_ids, "Claim evidence IDs")))
        require(
            bool(ids) == (self.basis == "cited"),
            "Only cited claims require nonempty evidence IDs.",
        )
        object.__setattr__(self, "evidence_ids", ids)
        self._check_utf8()


@dataclass(frozen=True)
class TargetEvidence(_TargetRecord):
    """Pinned evidence provenance with an explicitly declared biological context."""

    id: str
    source: PinnedIdentity
    taxon_id: int | None
    system: str
    source_context: str
    locator: str
    limitations: str
    schema_version: ClassVar[str] = "biocompiler.target_evidence.v0.1"
    _decoders: ClassVar[dict] = {"source": PinnedIdentity.from_dict}

    def __post_init__(self):
        for key in ("id", "source_context", "locator", "limitations"):
            name(getattr(self, key), f"Evidence {key}")
        require(
            isinstance(self.source, PinnedIdentity)
            and self.source.kind in {"source", "evidence"},
            "Target evidence requires a pinned source or evidence identity.",
        )
        _choice(
            self.system,
            {
                "human_in_vivo",
                "primary_human_cells",
                "human_cell_line",
                "nonhuman_in_vivo",
                "nonhuman_cells",
                "cell_free",
                "software_fixture",
            },
            "evidence system",
        )
        if self.system in {"human_in_vivo", "primary_human_cells", "human_cell_line"}:
            require(
                type(self.taxon_id) is int and self.taxon_id == 9606,
                "Human evidence requires taxon 9606.",
            )
        elif self.system in {"nonhuman_in_vivo", "nonhuman_cells"}:
            require(
                type(self.taxon_id) is int
                and self.taxon_id > 0
                and self.taxon_id != 9606,
                "Non-human evidence requires a non-human taxon.",
            )
        else:
            require(
                self.taxon_id is None,
                "Cell-free and software evidence have no recipient taxon.",
            )
        self._check_utf8()


@dataclass(frozen=True)
class HumanHostDependency(_TargetRecord):
    id: str
    capability: str
    compartment: str
    support: TargetClaim
    schema_version: ClassVar[str] = "biocompiler.human_host_dependency.v0.1"
    _decoders: ClassVar[dict] = {"support": TargetClaim.from_dict}

    def __post_init__(self):
        for key in ("id", "capability", "compartment"):
            name(getattr(self, key), f"Host dependency {key}")
        require(
            isinstance(self.support, TargetClaim),
            "Host dependency support requires a TargetClaim.",
        )
        self._check_utf8()


@dataclass(frozen=True)
class HumanOperatingCondition(_TargetRecord):
    id: str
    observable: str
    compartment: str
    domain: ValueDomain
    support: TargetClaim
    schema_version: ClassVar[str] = "biocompiler.human_operating_condition.v0.1"
    _decoders: ClassVar[dict] = {
        "domain": ValueDomain.from_dict,
        "support": TargetClaim.from_dict,
    }

    def __post_init__(self):
        for key in ("id", "observable", "compartment"):
            name(getattr(self, key), f"Operating condition {key}")
        require(
            isinstance(self.domain, ValueDomain),
            "Operating conditions require a typed ValueDomain.",
        )
        require(
            isinstance(self.support, TargetClaim),
            "Operating condition support requires a TargetClaim.",
        )
        self._check_utf8()


@dataclass(frozen=True)
class HumanTargetContract(_TargetRecord):
    """Required human applicability declarations; there are no universal defaults.

    The schema fixes human recipients and in-vivo engineering. Evidence from a
    different setting remains separately classified, even when cited by a claim.
    The existence, completeness and truth of these claims require later review.
    """

    cell_subtype: TargetClaim
    cell_state: TargetClaim
    tissue_context: TargetClaim
    disease_context: TargetClaim
    population_inclusion: TargetClaim
    population_exclusion: TargetClaim
    host_dependencies: tuple[HumanHostDependency, ...]
    operating_conditions: tuple[HumanOperatingCondition, ...]
    evidence: tuple[TargetEvidence, ...]
    schema_version: ClassVar[str] = "biocompiler.human_target_contract.v0.1"
    _fixed_fields: ClassVar[dict] = {
        "recipient_taxon_id": 9606,
        "engineering": "in_vivo",
    }
    _claim_fields: ClassVar[tuple[str, ...]] = (
        "cell_subtype",
        "cell_state",
        "tissue_context",
        "disease_context",
        "population_inclusion",
        "population_exclusion",
    )
    _decoders: ClassVar[dict] = {
        **dict.fromkeys(_claim_fields, TargetClaim.from_dict),
        "host_dependencies": lambda values: _decode_records(
            values, HumanHostDependency
        ),
        "operating_conditions": lambda values: _decode_records(
            values, HumanOperatingCondition
        ),
        "evidence": lambda values: _decode_records(values, TargetEvidence),
    }

    def __post_init__(self):
        for key in self._claim_fields:
            require(
                isinstance(getattr(self, key), TargetClaim),
                f"{key} requires an explicit TargetClaim.",
            )
        for key, cls in (
            ("host_dependencies", HumanHostDependency),
            ("operating_conditions", HumanOperatingCondition),
            ("evidence", TargetEvidence),
        ):
            object.__setattr__(self, key, _records(getattr(self, key), cls, key))
        require(
            bool(self.host_dependencies),
            "Human targets require an explicit host dependency inventory.",
        )
        require(
            bool(self.operating_conditions),
            "Human targets require explicit operating conditions.",
        )
        evidence_ids = {item.id for item in self.evidence}
        for path, claim in self.claims:
            require(
                set(claim.evidence_ids) <= evidence_ids,
                f"Unknown evidence reference in {path}.",
            )
        self._check_utf8()

    @property
    def claims(self):
        """Stable paths for evidence review; no assertion is promoted to PASS."""
        return (
            *((key, getattr(self, key)) for key in self._claim_fields),
            *(
                (f"host_dependencies.{item.id}", item.support)
                for item in self.host_dependencies
            ),
            *(
                (f"operating_conditions.{item.id}", item.support)
                for item in self.operating_conditions
            ),
        )

    @property
    def unresolved_evidence(self):
        """Every applicability assertion awaits independent acceptance in v0.1."""
        return tuple(path for path, _claim in self.claims)
