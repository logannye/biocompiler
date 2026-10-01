"""Nominal molecular chemistry declarations, without transformation or evidence.

Canonical spelling is retained separately from modifications. In particular,
adenosine-to-inosine declarations preserve canonical A plus an explicit chemical
identity: neither I nor G is silently substituted into the canonical sequence.
Provenance completeness is independent of nominal chemistry completeness.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from biocompiler.ir.molecule_records import (
    CANONICAL_ALPHABETS,
    DeclarationProvenance,
    MAX_RESIDUES,
    _MoleculeRecord,
    _choice,
    _text,
)
from biocompiler.ir.serialization import fingerprint, require
from biocompiler.semantics.molecule_coordinates import CoordinatePath, CoordinateSpace


MAX_MODIFICATIONS = 128
MAX_MODIFICATION_POSITIONS = 4096
MAX_TAIL_LENGTH = MAX_RESIDUES
_BUILTIN_PARENTS = {
    "inosine": "A",
    "pseudouridine": "U",
    "n1_methylpseudouridine": "U",
}


def _optional(record):
    return lambda value: None if value is None else record.from_dict(value)


def _provenance(value):
    require(
        isinstance(value, DeclarationProvenance),
        "Expected explicit chemistry provenance.",
    )


def _nonnegative_integer(value, label, *, maximum=MAX_TAIL_LENGTH):
    require(
        type(value) is int and 0 <= value <= maximum,
        f"{label} requires a bounded nonnegative integer.",
    )


@dataclass(frozen=True)
class ChemicalIdentity(_MoleculeRecord):
    """An exact declared chemical identifier; no ontology lookup is inferred."""

    namespace: str
    accession: str
    version: str
    schema_version: ClassVar[str] = "biocompiler.chemical_identity.v0.1"

    def __post_init__(self):
        for field in ("namespace", "accession", "version"):
            _text(getattr(self, field), f"Chemical {field}")
        self._check_resources()

    def nominal_dict(self):
        return self.to_dict()

    @property
    def declared_nominal_complete(self):
        return all(
            value != "unknown"
            for value in (self.namespace, self.accession, self.version)
        )


@dataclass(frozen=True)
class ChemistryClaim(_MoleculeRecord):
    status: str
    identity: ChemicalIdentity | None
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.chemistry_claim.v0.1"
    _decoders: ClassVar[dict] = {
        "identity": _optional(ChemicalIdentity),
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _choice(
            self.status,
            {"declared", "unknown", "inapplicable", "absent"},
            "chemistry claim status",
        )
        require(
            isinstance(self.identity, ChemicalIdentity)
            if self.status == "declared"
            else self.identity is None,
            "Only declared chemistry claims carry a chemical identity.",
        )
        _provenance(self.provenance)
        self._check_resources()

    def nominal_dict(self):
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "identity": None if self.identity is None else self.identity.nominal_dict(),
        }

    @property
    def declared_nominal_complete(self):
        return self.status != "unknown" and (
            self.identity is None or self.identity.declared_nominal_complete
        )


@dataclass(frozen=True)
class BaseModification(_MoleculeRecord):
    """One positional or all-matching policy; occurrence ID is archival metadata."""

    id: str
    identity: ChemicalIdentity
    canonical_base: str
    scope: str
    positions: tuple[int, ...]
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.base_modification.v0.1"
    _decoders: ClassVar[dict] = {
        "identity": ChemicalIdentity.from_dict,
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _text(self.id, "Modification occurrence identity")
        require(
            isinstance(self.identity, ChemicalIdentity),
            "Expected exact modification chemical identity.",
        )
        _choice(
            self.canonical_base, {"A", "C", "G", "T", "U"}, "modification parent base"
        )
        _choice(self.scope, {"positions", "all_matching_bases"}, "modification scope")
        require(
            isinstance(self.positions, (tuple, list))
            and len(self.positions) <= MAX_MODIFICATION_POSITIONS,
            "Modification positions require a bounded array.",
        )
        for position in self.positions:
            _nonnegative_integer(
                position, "Modification position", maximum=MAX_RESIDUES - 1
            )
        require(
            len(set(self.positions)) == len(self.positions),
            "Duplicate modification positions.",
        )
        object.__setattr__(self, "positions", tuple(sorted(self.positions)))
        require(
            bool(self.positions) if self.scope == "positions" else not self.positions,
            "Position modifications require explicit sites; all-matching policies have no site list.",
        )
        if (
            self.identity.namespace == "biocompiler.chemical"
            and self.identity.version == "1"
        ):
            expected = _BUILTIN_PARENTS.get(self.identity.accession)
            require(
                expected is None or self.canonical_base == expected,
                "Built-in modification has the wrong canonical parent base.",
            )
        _provenance(self.provenance)
        self._check_resources()

    def nominal_dict(self):
        return {
            "schema_version": self.schema_version,
            "identity": self.identity.nominal_dict(),
            "canonical_base": self.canonical_base,
            "scope": self.scope,
            "positions": list(self.positions),
        }


@dataclass(frozen=True)
class TailLength(_MoleculeRecord):
    mode: str
    exact: int | None = None
    lower: int | None = None
    upper: int | None = None
    schema_version: ClassVar[str] = "biocompiler.tail_length.v0.1"

    def __post_init__(self):
        _choice(self.mode, {"exact", "bounded", "unknown"}, "tail length mode")
        if self.mode == "exact":
            _nonnegative_integer(self.exact, "Exact tail length")
            require(
                self.lower is None and self.upper is None,
                "Exact tails cannot carry uncertainty bounds.",
            )
        elif self.mode == "bounded":
            require(self.exact is None, "Bounded tails cannot invent an exact length.")
            _nonnegative_integer(self.lower, "Tail lower bound")
            _nonnegative_integer(self.upper, "Tail upper bound")
            require(
                self.lower < self.upper,
                "Tail uncertainty requires distinct ordered bounds.",
            )
        else:
            require(
                self.exact is None and self.lower is None and self.upper is None,
                "Unknown tail lengths cannot invent numbers.",
            )
        self._check_resources()

    def nominal_dict(self):
        return self.to_dict()


@dataclass(frozen=True)
class TailDeclaration(_MoleculeRecord):
    """A terminal poly(A) declaration; internal tracts are sequence annotations."""

    status: str
    placement: str | None
    length: TailLength | None
    path: CoordinatePath | None
    provenance: DeclarationProvenance
    schema_version: ClassVar[str] = "biocompiler.tail_declaration.v0.1"
    _decoders: ClassVar[dict] = {
        "length": _optional(TailLength),
        "path": _optional(CoordinatePath),
        "provenance": DeclarationProvenance.from_dict,
    }

    def __post_init__(self):
        _choice(
            self.status,
            {"declared", "unknown", "inapplicable"},
            "tail declaration status",
        )
        if self.status == "declared":
            _choice(
                self.placement,
                {"represented_terminal", "appended_terminal", "absent"},
                "tail placement",
            )
            require(
                isinstance(self.length, TailLength),
                "Declared tails require explicit length knowledge.",
            )
            if self.placement == "represented_terminal":
                require(
                    self.length.mode == "exact" and self.length.exact > 0,
                    "Represented tails require a positive exact length.",
                )
                require(
                    isinstance(self.path, CoordinatePath),
                    "Represented tails require exact coordinates.",
                )
            elif self.placement == "appended_terminal":
                require(
                    self.length.mode in {"bounded", "unknown"} and self.path is None,
                    "Uncertain appended tails cannot invent coordinates or an exact length.",
                )
            else:
                require(
                    self.length.mode == "exact"
                    and self.length.exact == 0
                    and self.path is None,
                    "Absent tails require exact zero and no coordinates.",
                )
        else:
            require(
                self.placement is None and self.length is None and self.path is None,
                "Unknown/inapplicable tails cannot invent placement, length or coordinates.",
            )
        _provenance(self.provenance)
        self._check_resources()

    def nominal_dict(self):
        path = (
            None
            if self.path is None
            else {
                key: value
                for key, value in self.path.to_dict().items()
                if key != "space_id"
            }
        )
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "placement": self.placement,
            "length": None if self.length is None else self.length.nominal_dict(),
            "path": path,
        }

    @property
    def declared_nominal_complete(self):
        return self.status == "inapplicable" or (
            self.status == "declared" and self.length.mode == "exact"
        )


def _modifications_from_dict(values):
    require(
        isinstance(values, (tuple, list)) and len(values) <= MAX_MODIFICATIONS,
        "Invalid modification inventory.",
    )
    return tuple(BaseModification.from_dict(value) for value in values)


@dataclass(frozen=True)
class MoleculeChemistry(_MoleculeRecord):
    cap: ChemistryClaim
    start_end: ChemistryClaim
    finish_end: ChemistryClaim
    modifications: tuple[BaseModification, ...]
    modification_inventory_status: str
    modification_inventory_provenance: DeclarationProvenance
    terminal_tail: TailDeclaration
    schema_version: ClassVar[str] = "biocompiler.molecule_chemistry.v0.1"
    _decoders: ClassVar[dict] = {
        "cap": ChemistryClaim.from_dict,
        "start_end": ChemistryClaim.from_dict,
        "finish_end": ChemistryClaim.from_dict,
        "modifications": _modifications_from_dict,
        "modification_inventory_provenance": DeclarationProvenance.from_dict,
        "terminal_tail": TailDeclaration.from_dict,
    }

    def __post_init__(self):
        for value in (self.cap, self.start_end, self.finish_end):
            require(
                isinstance(value, ChemistryClaim),
                "Expected structured cap and terminal chemistry.",
            )
        require(
            isinstance(self.terminal_tail, TailDeclaration),
            "Expected a structured terminal-tail declaration.",
        )
        _choice(
            self.modification_inventory_status,
            {"declared", "unknown", "inapplicable"},
            "modification inventory status",
        )
        require(
            isinstance(self.modifications, (tuple, list))
            and len(self.modifications) <= MAX_MODIFICATIONS,
            "Invalid modification inventory size.",
        )
        require(
            all(isinstance(item, BaseModification) for item in self.modifications),
            "Expected typed modification declarations.",
        )
        modifications = tuple(self.modifications)
        require(
            len({item.id for item in modifications}) == len(modifications),
            "Duplicate modification occurrence IDs.",
        )
        require(
            self.modification_inventory_status != "inapplicable" or not modifications,
            "Inapplicable modification inventories must be empty.",
        )
        # Preserve occurrences but canonicalize archival order. Nominal order is
        # independently canonicalized by chemical content below.
        object.__setattr__(
            self,
            "modifications",
            tuple(sorted(modifications, key=lambda item: item.id)),
        )
        _provenance(self.modification_inventory_provenance)
        self._check_resources()

    def validate_for(self, space, sequence, sequence_extent):
        """Check declared consistency without editing symbols or inferring biology."""
        require(
            isinstance(space, CoordinateSpace),
            "Expected molecular coordinate-space authority.",
        )
        _choice(sequence_extent, {"complete", "exact_core"}, "sequence extent")
        alphabet = CANONICAL_ALPHABETS[space.alphabet]
        require(
            isinstance(sequence, str)
            and len(sequence) == space.length
            and bool(sequence)
            and set(sequence) <= set(alphabet),
            "Sequence must match the coordinate space and its canonical alphabet.",
        )
        if space.topology == "circular":
            require(
                all(
                    item.status == "inapplicable"
                    for item in (self.cap, self.start_end, self.finish_end)
                )
                and self.terminal_tail.status == "inapplicable",
                "Circular molecules have inapplicable caps, free ends and terminal tails.",
            )
        else:
            require(
                self.start_end.status in {"declared", "unknown"}
                and self.finish_end.status in {"declared", "unknown"},
                "Linear terminal groups must be declared or explicitly unknown.",
            )
        if space.alphabet != "RNA":
            require(
                self.cap.status == "inapplicable"
                and self.terminal_tail.status == "inapplicable",
                "DNA/protein caps and RNA-style tails must be inapplicable.",
            )
        elif space.topology == "linear":
            require(
                self.cap.status in {"declared", "unknown", "absent"},
                "Linear RNA cap must be declared, absent or unknown.",
            )
            require(
                self.terminal_tail.status in {"declared", "unknown"},
                "Linear RNA tail must be declared or explicitly unknown.",
            )
        if space.alphabet == "protein":
            require(
                not self.modifications,
                "Protein records cannot carry nucleotide base modifications.",
            )
        else:
            require(
                self.modification_inventory_status != "inapplicable",
                "Nucleotide modification inventories must be declared or unknown.",
            )
        used = set()
        all_matching_bases = set()
        explicit_bases = set()
        for modification in self.modifications:
            require(
                modification.canonical_base in alphabet,
                "Modification parent base differs from molecule alphabet.",
            )
            if modification.scope == "positions":
                positions = modification.positions
                require(
                    all(position < len(sequence) for position in positions),
                    "Modification position is outside the represented sequence.",
                )
                require(
                    all(
                        sequence[position] == modification.canonical_base
                        for position in positions
                    ),
                    "Modification position differs from its declared canonical parent base.",
                )
                require(
                    modification.canonical_base not in all_matching_bases,
                    "Modification declarations overlap an all-matching policy.",
                )
                require(
                    not used.intersection(positions),
                    "Modification declarations overlap on represented bases.",
                )
                used.update(positions)
                explicit_bases.add(modification.canonical_base)
            else:
                require(
                    modification.canonical_base
                    not in all_matching_bases | explicit_bases,
                    "Modification declarations overlap an all-matching policy.",
                )
                all_matching_bases.add(modification.canonical_base)
        tail = self.terminal_tail
        if tail.status == "declared" and tail.placement == "represented_terminal":
            tail.path.validate_for(space)
            require(
                tail.path.strand == "+"
                and len(tail.path.spans) == 1
                and tail.path.spans[0].end == len(sequence)
                and tail.path.length == tail.length.exact,
                "Exact tails require one forward terminal interval with the declared length.",
            )
            span = tail.path.spans[0]
            require(
                set(sequence[span.start : span.end]) == {"A"},
                "An exact poly(A) tail requires literal canonical adenines.",
            )
        appended = tail.status == "declared" and tail.placement == "appended_terminal"
        if appended:
            require(
                space.alphabet == "RNA"
                and space.topology == "linear"
                and sequence_extent == "exact_core",
                "Uncertain appended tails require an exact linear RNA core.",
            )
        if sequence_extent == "exact_core":
            require(
                appended,
                "An exact core must explicitly declare its uncertain appended tail.",
            )

    def nominal_dict(self):
        modifications = [item.nominal_dict() for item in self.modifications]
        modifications.sort(key=fingerprint)
        return {
            "schema_version": self.schema_version,
            "cap": self.cap.nominal_dict(),
            "start_end": self.start_end.nominal_dict(),
            "finish_end": self.finish_end.nominal_dict(),
            "modifications": modifications,
            "modification_inventory_status": self.modification_inventory_status,
            "terminal_tail": self.terminal_tail.nominal_dict(),
        }

    @property
    def declared_nominal_complete(self):
        return (
            all(
                item.declared_nominal_complete
                for item in (self.cap, self.start_end, self.finish_end)
            )
            and self.modification_inventory_status != "unknown"
            and all(
                item.identity.declared_nominal_complete for item in self.modifications
            )
            and self.terminal_tail.declared_nominal_complete
        )
