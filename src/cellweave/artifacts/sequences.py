"""Deterministic FASTA and structured-specification serialization for exact CDSs.

Export rechecks current authoritative inputs. File bytes and canonical sequence
identity are separate: changing FASTA line width changes its file digest without
changing the sequence. Publishing multi-file build packages is a later scope.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from urllib.parse import quote, unquote_to_bytes

from cellweave.errors import SerializationError
from cellweave.ir.molecular import MolecularArtifact
from cellweave.ir.serialization import require
from cellweave.verification.molecular import check_molecular

SEQUENCE_EXPORT_VERSION = "cellweave.sequence_export.v0.1"
FASTA_POLICY = "single-reference-percent-encoded-id-uppercase-lf-terminal-newline.v1"
JSON_POLICY = "molecular-specification-sorted-keys-indent-2-utf8-lf-terminal-newline.v1"


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _hash(value, label):
    require(
        isinstance(value, str)
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value),
        f"Invalid {label} fingerprint.",
    )


def _line_width(value):
    require(
        type(value) is int and 1 <= value <= 10000,
        "FASTA line width must be an integer from 1 to 10000.",
    )


@dataclass(frozen=True)
class SequenceExport:
    """Checked export text; this object is not an imported acceptance receipt.

    Write ``fasta_bytes`` and ``specification_bytes`` in binary mode to preserve
    the documented LF newlines on every platform. No output path enters identity.
    """

    fasta: str
    specification: str
    line_width: int
    sequence_sha256: str
    molecular_fingerprint: str

    def __post_init__(self):
        require(isinstance(self.fasta, str), "FASTA export must be text.")
        require(
            isinstance(self.specification, str), "Molecular specification must be text."
        )
        _line_width(self.line_width)
        _hash(self.sequence_sha256, "canonical sequence")
        _hash(self.molecular_fingerprint, "molecular artifact")

    @property
    def fasta_bytes(self):
        return self.fasta.encode("utf-8")

    @property
    def specification_bytes(self):
        return self.specification.encode("utf-8")

    @property
    def fasta_sha256(self):
        return _digest(self.fasta_bytes)

    @property
    def specification_sha256(self):
        return _digest(self.specification_bytes)


def verify_sequence_export(bundle: SequenceExport, artifact: MolecularArtifact) -> bool:
    """Parse both encodings and prove serialization fidelity to one artifact.

    This is an identity check, not reference or biological acceptance. Use
    ``export_reference_sequence`` to independently check current authoritative
    inputs before obtaining an accepted export. Imported result labels are unused.
    """
    require(isinstance(bundle, SequenceExport), "Expected a sequence export.")
    require(isinstance(artifact, MolecularArtifact), "Expected a molecular artifact.")
    require(len(artifact.records) == 1, "Sequence export supports one CDS record.")
    require(
        bundle.molecular_fingerprint == artifact.fingerprint,
        "Export identifies a different molecular artifact.",
    )
    record = artifact.records[0]
    text = bundle.fasta
    require(
        text.isascii() and text.endswith("\n") and "\r" not in text,
        "FASTA requires ASCII symbols, LF newlines and one terminal newline.",
    )
    lines = text.split("\n")
    require(
        len(lines) >= 3 and lines[-1] == "", "FASTA requires a header and sequence."
    )
    header, sequence_lines = lines[0], lines[1:-1]
    require(header.startswith(">"), "FASTA is missing its record header.")
    tokens = header[1:].split(" ")
    require(
        len(tokens) == 3,
        "FASTA header must identify exactly one reference, alphabet and scope.",
    )
    try:
        reference_id = unquote_to_bytes(tokens[0]).decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError) as error:
        raise SerializationError("Invalid encoded FASTA reference identity.") from error
    require(
        quote(reference_id, safe="-._~") == tokens[0]
        and reference_id == record.reference_selection.reference.id
        and tokens[1] == "alphabet=" + record.alphabet
        and tokens[2] == "scope=CDS-reference-only",
        "FASTA header changed reference identity, alphabet, scope or encoding.",
    )
    require(
        bool(sequence_lines)
        and all(0 < len(line) <= bundle.line_width for line in sequence_lines)
        and all(len(line) == bundle.line_width for line in sequence_lines[:-1]),
        "FASTA wrapping differs from its declared line-width policy.",
    )
    symbols = set("ACGT" if record.alphabet == "DNA" else "ACGU")
    require(
        all(set(line) <= symbols for line in sequence_lines),
        "FASTA contains invalid symbols or an additional record; no normalization is applied.",
    )
    sequence = "".join(sequence_lines)
    sequence_hash = _digest(sequence.encode("ascii"))
    require(
        sequence == record.sequence
        and sequence_hash == record.sequence_sha256 == bundle.sequence_sha256,
        "FASTA canonical sequence differs from the molecular artifact.",
    )
    decoded = MolecularArtifact.from_json(bundle.specification)
    require(
        decoded.fingerprint == artifact.fingerprint,
        "Structured export changed molecular content or provenance.",
    )
    require(
        bundle.specification == artifact.to_json(indent=2) + "\n",
        "Structured export differs from the canonical JSON file policy.",
    )
    return True


def export_reference_sequence(
    request,
    construct,
    artifact: MolecularArtifact,
    registry,
    manifests,
    *,
    line_width: int = 80,
) -> SequenceExport:
    """Independently check a current exact CDS, then serialize FASTA plus JSON.

    Return immutable text/bytes for the caller to save. This does not publish a
    success manifest or promise atomic multi-file packaging.
    """
    _line_width(line_width)
    checked = check_molecular(request, construct, artifact, registry, manifests)
    require(
        checked.passed,
        "Sequence export requires a currently passing independent molecular check: "
        + "; ".join(item.code for item in checked.diagnostics),
    )
    record = artifact.records[0]
    header = (
        ">"
        + quote(record.reference_selection.reference.id, safe="-._~")
        + " alphabet="
        + record.alphabet
        + " scope=CDS-reference-only\n"
    )
    sequence_lines = (
        record.sequence[start : start + line_width]
        for start in range(0, len(record.sequence), line_width)
    )
    bundle = SequenceExport(
        fasta=header + "\n".join(sequence_lines) + "\n",
        specification=artifact.to_json(indent=2) + "\n",
        line_width=line_width,
        sequence_sha256=record.sequence_sha256,
        molecular_fingerprint=artifact.fingerprint,
    )
    verify_sequence_export(bundle, artifact)
    return bundle
