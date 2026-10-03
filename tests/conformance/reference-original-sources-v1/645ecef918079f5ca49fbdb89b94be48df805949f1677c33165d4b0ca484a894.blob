"""Pinned sequence-reference inputs, never empirical or full-payload evidence.

The first schema deliberately supports one reconciled DNA/RNA/protein CDS set.
It does not fetch sources, execute authoring code or repair source sequences.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
import hashlib
import itertools
import json
from pathlib import Path, PurePosixPath
import re

from biocompiler.errors import SerializationError
from biocompiler.ir.intent import freeze_json, thaw_json

SCHEMA_VERSION = "biocompiler.reference.v0.1"
NORMALIZATION = "ascii-layout-whitespace-and-uppercase.v1"
_ALPHABETS = {
    "DNA": frozenset("ACGT"),
    "RNA": frozenset("ACGU"),
    "protein": frozenset("ACDEFGHIKLMNPQRSTVWY*"),
}
_CLASSES = {"DNA": "coding_dna", "RNA": "coding_rna", "protein": "protein"}
_WHITESPACE = " \t\r\n\v\f"
# NCBI Standard Code (table 1), TCAG lexical order. No alternative starts.
_CODONS = dict(
    zip(
        ("".join(c) for c in itertools.product("TCAG", repeat=3)),
        "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG",
    )
)


def _require(condition, message):
    if not condition:
        raise SerializationError(message)


def _named(value):
    return isinstance(value, str) and bool(value.strip())


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _local_path(value):
    return (
        isinstance(value, str)
        and bool(value)
        and bool(PurePosixPath(value).name)
        and not PurePosixPath(value).is_absolute()
        and ".." not in PurePosixPath(value).parts
        and "\\" not in value
    )


def _fields(data, names, label):
    _require(
        isinstance(data, Mapping) and set(data) == set(names.split()),
        f"Invalid {label} fields.",
    )


def _strings(value, label, *, unique=True):
    _require(
        isinstance(value, (list, tuple)) and all(_named(x) for x in value),
        f"Invalid {label}.",
    )
    _require(not unique or len(set(value)) == len(value), f"Duplicate {label}.")
    return tuple(value)


def _sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def _pairs(items):
    result = {}
    for key, value in items:
        _require(key not in result, f"Duplicate JSON field: {key}.")
        result[key] = value
    return result


def normalize_sequence(raw_text: str, alphabet: str) -> tuple[str, dict]:
    """Remove only ASCII layout whitespace and uppercase; preserve '*' stops.

    Numbers, punctuation, non-ASCII whitespace and ambiguous symbols are errors,
    not OCR corrections. RNA is never derived by normalizing DNA.
    """
    _require(isinstance(raw_text, str) and bool(raw_text), "Missing raw sequence text.")
    _require(
        isinstance(alphabet, str) and alphabet in _ALPHABETS,
        "Unsupported sequence alphabet.",
    )
    _require(
        raw_text.isascii(),
        "Only ASCII sequence letters and layout whitespace are allowed.",
    )
    sequence = "".join(c for c in raw_text if c not in _WHITESPACE).upper()
    _require(
        bool(sequence) and set(sequence) <= _ALPHABETS[alphabet],
        f"Invalid {alphabet} symbol in reference extraction; no correction applied.",
    )
    return sequence, {
        "policy": NORMALIZATION,
        "removed_ascii_whitespace": sum(c in _WHITESPACE for c in raw_text),
        "uppercased_characters": sum(c.islower() for c in raw_text),
    }


def translate_cds(sequence: str, alphabet: str = "DNA") -> str:
    """Translate frame zero under table 1; retain the sole terminal '*' marker."""
    _require(
        isinstance(alphabet, str) and alphabet in {"DNA", "RNA"},
        "Translation requires DNA or RNA.",
    )
    _require(
        isinstance(sequence, str)
        and bool(sequence)
        and set(sequence) <= _ALPHABETS[alphabet],
        "Invalid translation alphabet.",
    )
    _require(len(sequence) % 3 == 0, "CDS length is not divisible by three.")
    dna = sequence.replace("U", "T")
    _require(dna.startswith("ATG"), "CDS does not start with the required ATG/AUG.")
    protein = "".join(_CODONS[dna[i : i + 3]] for i in range(0, len(dna), 3))
    _require(
        protein.endswith("*") and "*" not in protein[:-1],
        "CDS requires exactly one terminal stop, with no internal stops.",
    )
    return protein


@dataclass(frozen=True)
class ReferenceRecord:
    """Immutable independently extracted expectation with explicit provenance."""

    reference_id: str
    variant_id: str
    version: str
    alphabet: str
    artifact_class: str
    orientation: str
    source_id: str
    source_locator: str
    raw_sequence_text: str
    raw_text_sha256: str
    sequence: str
    sequence_sha256: str
    length: int
    normalization: Mapping
    linked_reference_ids: tuple[str, ...]
    completeness: str
    unknown_features: tuple[str, ...]
    evidence_relationships: tuple[str, ...]

    def __post_init__(self):
        for key in (
            "reference_id",
            "variant_id",
            "version",
            "source_id",
            "source_locator",
        ):
            _require(_named(getattr(self, key)), f"Invalid {key}.")
        _require(
            isinstance(self.alphabet, str) and self.alphabet in _ALPHABETS,
            "Unsupported sequence alphabet.",
        )
        _require(
            self.artifact_class == _CLASSES[self.alphabet],
            "Artifact class disagrees with declared alphabet.",
        )
        _require(
            self.orientation
            == ("N-to-C" if self.alphabet == "protein" else "5prime-to-3prime"),
            "Unsupported reference orientation.",
        )
        sequence, log = normalize_sequence(self.raw_sequence_text, self.alphabet)
        _require(
            self.sequence == sequence,
            "Normalized sequence differs from raw extraction.",
        )
        _require(
            self.raw_text_sha256 == _sha(self.raw_sequence_text),
            "Raw text hash mismatch.",
        )
        _require(
            self.sequence_sha256 == _sha(sequence), "Canonical sequence hash mismatch."
        )
        _require(
            type(self.length) is int and self.length == len(sequence),
            "Sequence length mismatch.",
        )
        _require(
            isinstance(self.normalization, Mapping)
            and _canonical(thaw_json(freeze_json(self.normalization)))
            == _canonical(log),
            "Normalization log mismatch.",
        )
        object.__setattr__(self, "normalization", freeze_json(self.normalization))
        for key in (
            "linked_reference_ids",
            "unknown_features",
            "evidence_relationships",
        ):
            object.__setattr__(self, key, _strings(getattr(self, key), key))
        _require(
            self.completeness == "CDS-reference-only", "Unsupported completeness claim."
        )
        _require(
            bool(self.unknown_features),
            "CDS-only unknown features must remain explicit.",
        )
        _require(
            "exact-experimental-material-identity-unresolved"
            in self.evidence_relationships,
            "Reference must distinguish exact experimental material identity.",
        )

    @property
    def fingerprint(self):
        return _sha(_canonical(self.to_dict()))

    def to_dict(self):
        return {
            name: thaw_json(getattr(self, name)) for name in self.__dataclass_fields__
        }

    @classmethod
    def from_dict(cls, data):
        _fields(data, " ".join(cls.__dataclass_fields__), "reference record")
        return cls(**data)


@dataclass(frozen=True)
class ReferenceManifest:
    """A locked reference set and the evidence required for its acceptance.

    Review evidence is provenance, not a cryptographic attestation. Callers must
    pin ``fingerprint`` in their build request; an edited manifest is a new input.
    """

    reference_set_id: str
    version: str
    sources: tuple[Mapping, ...]
    records: tuple[ReferenceRecord, ...]
    translation: Mapping
    reviews: tuple[Mapping, ...]
    status: str
    unresolved_discrepancies: tuple[str, ...]
    redistribution: Mapping
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        _require(
            self.schema_version == SCHEMA_VERSION,
            "Unsupported reference schema version.",
        )
        _require(
            _named(self.reference_set_id) and _named(self.version),
            "Invalid reference set identity.",
        )
        _require(
            isinstance(self.status, str)
            and self.status in {"candidate", "blocked", "accepted"},
            "Invalid reference status.",
        )
        _require(
            isinstance(self.sources, (tuple, list)) and bool(self.sources),
            "Missing source artifacts.",
        )
        source_ids = set()
        for source in self.sources:
            _fields(
                source,
                "id url publication publication_version retrieved_on media_type sha256 local_path",
                "source artifact",
            )
            _require(
                all(
                    _named(source[k])
                    for k in (
                        "id",
                        "url",
                        "publication",
                        "publication_version",
                        "media_type",
                    )
                ),
                "Invalid source artifact identity.",
            )
            _require(
                source["url"].startswith("https://") and _hash(source["sha256"]),
                "Invalid source URL/hash.",
            )
            try:
                _require(
                    isinstance(source["retrieved_on"], str)
                    and date.fromisoformat(source["retrieved_on"]).isoformat()
                    == source["retrieved_on"],
                    "Invalid retrieval date.",
                )
            except (ValueError, TypeError) as error:
                raise SerializationError("Invalid retrieval date.") from error
            path = source["local_path"]
            _require(
                path is None
                or (
                    isinstance(path, str)
                    and bool(path)
                    and not PurePosixPath(path).is_absolute()
                    and ".." not in PurePosixPath(path).parts
                    and "\\" not in path
                ),
                "Source paths must stay within the reference directory.",
            )
            _require(
                source["id"] not in source_ids, "Duplicate source artifact identity."
            )
            source_ids.add(source["id"])
        object.__setattr__(self, "sources", tuple(freeze_json(s) for s in self.sources))
        _require(
            isinstance(self.records, (list, tuple))
            and all(isinstance(r, ReferenceRecord) for r in self.records),
            "Invalid reference records.",
        )
        object.__setattr__(self, "records", tuple(self.records))
        _require(
            len(self.records) == 3
            and {r.alphabet for r in self.records} == set(_ALPHABETS),
            "A CDS reference set requires independently extracted DNA, RNA and protein.",
        )
        ids = {r.reference_id for r in self.records}
        _require(
            len(ids) == 3 and len({r.variant_id for r in self.records}) == 1,
            "Duplicate reference or inconsistent variant identity.",
        )
        for record in self.records:
            _require(record.source_id in source_ids, "Unknown record source.")
            _require(
                set(record.linked_reference_ids) == ids - {record.reference_id},
                "Reference links must name the other records in the set.",
            )
        _require(
            isinstance(self.translation, Mapping)
            and dict(self.translation)
            == {
                "genetic_code": 1,
                "frame_zero_based": 0,
                "start_codon": "ATG/AUG",
                "stop_convention": "exactly-one-terminal-star-retained",
                "protein_length_includes_stop": True,
            }
            and type(self.translation["genetic_code"]) is int
            and type(self.translation["frame_zero_based"]) is int
            and type(self.translation["protein_length_includes_stop"]) is bool,
            "Unsupported translation convention.",
        )
        object.__setattr__(self, "translation", freeze_json(self.translation))
        object.__setattr__(
            self,
            "unresolved_discrepancies",
            _strings(self.unresolved_discrepancies, "discrepancies"),
        )
        _fields(
            self.redistribution,
            "attribution terms_url license_status note",
            "redistribution",
        )
        _require(
            all(_named(v) for v in self.redistribution.values()),
            "Invalid redistribution record.",
        )
        object.__setattr__(self, "redistribution", freeze_json(self.redistribution))
        _require(isinstance(self.reviews, (tuple, list)), "Invalid review evidence.")
        review_ids = set()
        record_hashes = {r.reference_id: r.fingerprint for r in self.records}
        for review in self.reviews:
            _fields(
                review,
                "reviewer role reviewed_on method record_fingerprints source_hashes outcome evidence",
                "review evidence",
            )
            _require(
                _named(review["reviewer"])
                and _named(review["method"])
                and review["reviewer"] not in review_ids,
                "Invalid/duplicate reviewer identity.",
            )
            review_ids.add(review["reviewer"])
            evidence = review["evidence"]
            if evidence is not None:
                _fields(evidence, "local_path sha256", "review evidence artifact")
                _require(
                    _local_path(evidence["local_path"]) and _hash(evidence["sha256"]),
                    "Invalid review evidence path/hash.",
                )
            _require(
                isinstance(review["role"], str)
                and review["role"] in {"extraction", "independent-review"}
                and isinstance(review["outcome"], str)
                and review["outcome"] in {"pass", "blocked"},
                "Invalid review role/outcome.",
            )
            try:
                _require(
                    isinstance(review["reviewed_on"], str)
                    and date.fromisoformat(review["reviewed_on"]).isoformat()
                    == review["reviewed_on"],
                    "Invalid review date.",
                )
            except (ValueError, TypeError) as error:
                raise SerializationError("Invalid review date.") from error
            _require(
                review["record_fingerprints"] == record_hashes,
                "Review uses stale record identities.",
            )
            _require(
                review["source_hashes"] == {s["id"]: s["sha256"] for s in self.sources},
                "Review uses stale source identities.",
            )
        object.__setattr__(self, "reviews", tuple(freeze_json(r) for r in self.reviews))
        if self.status == "accepted":
            _require(
                not self.discrepancies, "Inconsistent references cannot be accepted."
            )
            _require(
                {r["role"] for r in self.reviews if r["outcome"] == "pass"}
                == {"extraction", "independent-review"}
                and all(r["outcome"] == "pass" for r in self.reviews),
                "Acceptance requires extraction and independent passing review.",
            )
        if self.discrepancies:
            _require(
                self.status == "blocked",
                "Inconsistent reference set must remain blocked.",
            )

    @property
    def discrepancies(self):
        diagnostics = list(self.unresolved_discrepancies)
        records = {r.alphabet: r for r in self.records}
        if records["DNA"].sequence.replace("T", "U") != records["RNA"].sequence:
            diagnostics.append(
                "DNA/RNA differ under the explicit T-to-U correspondence check."
            )
        for alphabet in ("DNA", "RNA"):
            try:
                translated = translate_cds(records[alphabet].sequence, alphabet)
                if translated != records["protein"].sequence:
                    diagnostics.append(
                        f"{alphabet} translation differs from independently extracted protein."
                    )
            except SerializationError as error:
                diagnostics.append(f"{alphabet}: {error}")
        return tuple(diagnostics)

    @property
    def fingerprint(self):
        return _sha(_canonical(self.to_dict()))

    def record(self, reference_id: str, *, require_accepted=True):
        _require(
            not require_accepted or self.status == "accepted",
            f"Reference set is {self.status}; promotion is required before build use.",
        )
        matches = [r for r in self.records if r.reference_id == reference_id]
        _require(len(matches) == 1, f"Unknown reference record: {reference_id}.")
        return matches[0]

    def to_dict(self):
        return {
            "schema_version": self.schema_version,
            "reference_set_id": self.reference_set_id,
            "version": self.version,
            "sources": [thaw_json(s) for s in self.sources],
            "records": [r.to_dict() for r in self.records],
            "translation": thaw_json(self.translation),
            "reviews": [thaw_json(r) for r in self.reviews],
            "status": self.status,
            "unresolved_discrepancies": list(self.unresolved_discrepancies),
            "redistribution": thaw_json(self.redistribution),
        }

    def to_json(self):
        return (
            json.dumps(self.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n"
        )

    @classmethod
    def from_dict(cls, data):
        _fields(data, " ".join(cls.__dataclass_fields__), "reference manifest")
        _require(
            isinstance(data["records"], (list, tuple)),
            "Reference records must be an array.",
        )
        values = dict(data)
        values["records"] = tuple(ReferenceRecord.from_dict(r) for r in data["records"])
        return cls(**values)

    @classmethod
    def from_json(cls, text):
        try:
            data = json.loads(
                text,
                object_pairs_hook=_pairs,
                parse_constant=lambda x: (_ for _ in ()).throw(
                    SerializationError(f"Invalid number: {x}")
                ),
            )
        except (ValueError, TypeError) as error:
            raise SerializationError(f"Invalid reference JSON: {error}") from error
        return cls.from_dict(data)


def load_reference_manifest(
    path: str | Path, *, expected_fingerprint: str | None = None
):
    """Resolve only pinned local inputs, checking retained source-file bytes.

    Full upstream PDF/HTML archives may be external (``local_path=None``); their
    raw identities remain pinned. Retained source excerpts are always verified.
    """
    path = Path(path)
    manifest = ReferenceManifest.from_json(path.read_text(encoding="utf-8"))
    if expected_fingerprint is not None:
        _require(
            manifest.fingerprint == expected_fingerprint,
            "Reference manifest lock mismatch.",
        )
    root = path.parent.resolve()
    retained = False
    for source in manifest.sources:
        if source["local_path"] is not None:
            source_path = (root / source["local_path"]).resolve()
            _require(
                source_path.is_relative_to(root),
                "Source path escapes reference directory.",
            )
            _require(
                hashlib.sha256(source_path.read_bytes()).hexdigest()
                == source["sha256"],
                f"Source artifact hash mismatch: {source['id']}.",
            )
            retained = True
    _require(
        retained, "At least one source extraction artifact must be retained offline."
    )
    for review in manifest.reviews:
        evidence = review["evidence"]
        if evidence is not None:
            evidence_path = (root / evidence["local_path"]).resolve()
            _require(
                evidence_path.is_relative_to(root),
                "Review evidence path escapes reference directory.",
            )
            _require(
                hashlib.sha256(evidence_path.read_bytes()).hexdigest()
                == evidence["sha256"],
                f"Review evidence hash mismatch: {review['reviewer']}.",
            )
    return manifest
