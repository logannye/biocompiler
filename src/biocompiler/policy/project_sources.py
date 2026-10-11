"""Bounded inspection of supplied source bytes against a current research project.

This module does no file, network or native I/O. Matching a caller-declared digest
does not authenticate a publication, qualify biological evidence, approve reuse
rights or admit a compiler request. The returned inspection is inert data, never
authority to bypass fresh project compilation or independent verification.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import hashlib
from typing import Literal, cast

from .research_project import ResearchProject, ResearchProjectError, SourceRecord

# The qualified public CAR publication is 17.2 MB. Both ceilings remain finite.
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_SOURCE_BYTES = 64 * 1024 * 1024


class ProjectSourceError(ResearchProjectError):
    """Supplied source bytes are incomplete, malformed, oversized or mismatched."""


@dataclass(frozen=True, slots=True)
class ProjectSourceMatch:
    source_id: str
    sha256: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class ProjectSourceInspection:
    """Immutable byte matches in project declaration order, bound to that project.

    This record retains no source bytes or mutable caller containers. It is not
    a verification capability, and no compiler or exporter consumes it.
    """
    project_sha256: str
    sources: tuple[ProjectSourceMatch, ...]
    total_bytes: int
    status: Literal["source_bytes_matched"] = field(default="source_bytes_matched", init=False)
    publication_authenticity: Literal["unassessed"] = field(default="unassessed", init=False)
    biological_status: Literal["unassessed"] = field(default="unassessed", init=False)
    rights_status: Literal["unassessed"] = field(default="unassessed", init=False)
    native_status: Literal["not_run"] = field(default="not_run", init=False)


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ProjectSourceError(message)


def inspect_project_sources(project: ResearchProject, sources: Mapping[str, bytes]) -> ProjectSourceInspection:
    """Match every source ID and exact SHA-256 against independent current authority.

    Supply one immutable, nonempty byte string per declared source ID, with no
    missing or extra IDs. Each source is at most 32 MiB and the total at most
    64 MiB. A bounded snapshot is taken before hashing; later mapping edits do
    not change the inspection. Every invocation freshly hashes those bytes.

    The complete canonical project digest also binds locators, versions, roles,
    reuse terms, assumptions, request and limits. Matching bytes cannot establish
    that any of those declarations are true. Locators are never followed.
    """
    _require(type(project) is ResearchProject, "An independent ResearchProject is required")
    _require(isinstance(sources, Mapping), "Sources require a mapping from source IDs to bytes")
    records = tuple(SourceRecord(**row) for row in cast(list[dict[str, str]], project.data["sources"]))
    expected = {record.id: record for record in records}
    _require(len(sources) == len(expected), "Source inventory must contain exactly every declared source ID")
    snapshot: dict[str, bytes] = {}
    total = 0
    try:
        for source_id in sources:
            _require(len(snapshot) < len(expected), "Source inventory contains extra or repeated source IDs")
            _require(type(source_id) is str and len(source_id) <= 4096,
                     "Source IDs must be bounded plain strings")
            _require(source_id in expected and source_id not in snapshot,
                     "Source inventory contains an undeclared or repeated source ID")
            raw = sources[source_id]
            _require(type(raw) is bytes, "Source " + source_id + " requires immutable bytes")
            _require(0 < len(raw) <= MAX_SOURCE_BYTES, "Source " + source_id + " exceeds its nonempty byte bound")
            total += len(raw)
            _require(total <= MAX_TOTAL_SOURCE_BYTES, "Source inventory exceeds its total byte bound")
            snapshot[source_id] = raw
    except (KeyError, RuntimeError) as error:
        raise ProjectSourceError("Source mapping changed during inspection") from error
    _require(set(snapshot) == set(expected), "Source inventory must contain exactly every declared source ID")
    matches = []
    for record in records:
        raw = snapshot[record.id]
        digest = hashlib.sha256(raw).hexdigest()
        _require(digest == record.sha256, "Source bytes differ from the project digest: " + record.id)
        matches.append(ProjectSourceMatch(record.id, digest, len(raw)))
    return ProjectSourceInspection(project.digest, tuple(matches), total)
