"""Explicit bounded edit and codon-policy declarations, without execution.

Canonical RNA spelling and chemical substitutions are distinct operations.
These records have no graph references, source sequence or biological claims.
Execution must independently bind positions, expected symbols, chemistry and
condition assumptions to the complete frozen construction authority.
"""

from dataclasses import dataclass
from itertools import product
from types import MappingProxyType
from typing import ClassVar

from biocompiler.ir.molecule_chemistry import ChemicalIdentity
from biocompiler.ir.molecule_records import (
    CANONICAL_ALPHABETS,
    MAX_RESIDUES,
    _MoleculeRecord,
    _choice,
    _decode_records,
    _optional,
    _records,
    _text,
)
from biocompiler.ir.serialization import require


MAX_RECODINGS = 4096
STANDARD_GENETIC_CODE = "ncbi_standard_v1"

# NCBI Standard Code, table 1, using the same UCAG-order data as the existing
# registry/references.py table (where RNA U is represented by DNA T). This is
# normative immutable data, not a shared translation executor. No U/O or
# alternative initiation is inferred by this table.
STANDARD_RNA_CODON_TABLE = MappingProxyType(
    dict(
        zip(
            ("".join(codon) for codon in product("UCAG", repeat=3)),
            "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG",
            strict=True,
        )
    )
)

# Keep the built-in nominal chemical parent constraints consistent with the R3
# BaseModification schema. Unrecognized identifiers remain nominal declarations.
_BUILTIN_PARENTS = MappingProxyType(
    {"inosine": "A", "pseudouridine": "U", "n1_methylpseudouridine": "U"}
)


def _index(value, maximum, label):
    require(
        type(value) is int and 0 <= value < maximum,
        f"{label} requires a nonnegative integer below {maximum}.",
    )


@dataclass(frozen=True)
class CanonicalBaseEdit(_MoleculeRecord):
    """Replace one expected canonical RNA symbol at an explicitly bound site."""

    position: int
    expected: str
    replacement: str
    schema_version: ClassVar[str] = "biocompiler.canonical_base_edit.v0.1"

    def __post_init__(self):
        _index(self.position, MAX_RESIDUES, "Canonical edit position")
        _choice(self.expected, CANONICAL_ALPHABETS["RNA"], "expected RNA base")
        _choice(self.replacement, CANONICAL_ALPHABETS["RNA"], "replacement RNA base")
        require(
            self.expected != self.replacement,
            "Canonical base edits must change the expected symbol.",
        )
        self._check_resources()


@dataclass(frozen=True)
class ChemicalBaseEdit(_MoleculeRecord):
    """Change site chemistry while retaining its canonical RNA parent symbol.

    None denotes explicitly unmodified parent chemistry, not unknown chemistry.
    An inosine declaration therefore retains parent A; neither I nor G is an
    implicit replacement. Material processing and molecular function are not
    asserted by this nominal edit.
    """

    position: int
    parent: str
    before: ChemicalIdentity | None
    after: ChemicalIdentity | None
    schema_version: ClassVar[str] = "biocompiler.chemical_base_edit.v0.1"
    _decoders: ClassVar[dict] = {
        "before": _optional(ChemicalIdentity),
        "after": _optional(ChemicalIdentity),
    }

    def __post_init__(self):
        _index(self.position, MAX_RESIDUES, "Chemical edit position")
        _choice(self.parent, CANONICAL_ALPHABETS["RNA"], "chemical edit parent base")
        for field in ("before", "after"):
            identity = getattr(self, field)
            require(
                identity is None or isinstance(identity, ChemicalIdentity),
                "Chemical edits require exact chemical identities or explicit unmodified parent chemistry.",
            )
            if identity is None:
                continue
            identity = ChemicalIdentity.from_dict(identity.to_dict())
            object.__setattr__(self, field, identity)
            if identity.namespace == "biocompiler.chemical" and identity.version == "1":
                expected_parent = _BUILTIN_PARENTS.get(identity.accession)
                require(
                    expected_parent is None or self.parent == expected_parent,
                    "Built-in chemical edit identity has the wrong canonical parent base.",
                )
        require(
            self.before != self.after,
            "Chemical base edits must change the declared site chemistry.",
        )
        self._check_resources()


@dataclass(frozen=True)
class CodonRecoding(_MoleculeRecord):
    """One explicit codon result under a later-bound construction assumption."""

    codon_index: int
    expected_triplet: str
    amino_acid: str
    condition: str
    schema_version: ClassVar[str] = "biocompiler.codon_recoding.v0.1"

    def __post_init__(self):
        _index(self.codon_index, MAX_RESIDUES // 3, "Recoding codon index")
        _text(self.expected_triplet, "Expected RNA codon", 3)
        require(
            len(self.expected_triplet) == 3
            and set(self.expected_triplet) <= CANONICAL_ALPHABETS["RNA"],
            "Recoding requires exactly three canonical RNA symbols.",
        )
        _choice(
            self.amino_acid,
            CANONICAL_ALPHABETS["protein"] | {"*"},
            "recoded amino acid or explicit stop",
        )
        _text(self.condition, "Recoding condition assumption")
        self._check_resources()


@dataclass(frozen=True)
class TranslationPolicy(_MoleculeRecord):
    """A nominal translation policy whose source checks belong to execution.

    Both profiles require an explicitly bound forward contiguous RNA CDS, AUG
    initiation and exactly one effective terminal stop. The ordinary profile
    uses the standard table only. The conditional profile requires one or more
    explicit codon results and exact assumption binding for every condition.
    U/O can be emitted only through explicit recoding. This leaf schema neither
    locates a CDS nor checks or translates an input sequence.
    """

    profile: str
    genetic_code: str = STANDARD_GENETIC_CODE
    recodings: tuple[CodonRecoding, ...] = ()
    schema_version: ClassVar[str] = "biocompiler.translation_policy.v0.1"
    _decoders: ClassVar[dict] = {
        "recodings": _decode_records(CodonRecoding, MAX_RECODINGS)
    }

    def __post_init__(self):
        _choice(
            self.profile, {"ordinary_cds", "conditional_cds"}, "translation profile"
        )
        _choice(self.genetic_code, {STANDARD_GENETIC_CODE}, "declared genetic code")
        object.__setattr__(
            self,
            "recodings",
            _records(
                self.recodings,
                CodonRecoding,
                MAX_RECODINGS,
                "codon recodings",
                key="codon_index",
            ),
        )
        require(
            bool(self.recodings)
            if self.profile == "conditional_cds"
            else not self.recodings,
            "Conditional translation requires explicit recodings; ordinary translation cannot carry them.",
        )
        self._check_resources()
