"""Caller-owned research projects routed to fresh Core and independent Verify.

Project loading checks transport structure, never therapeutic admissibility.
Source records are explicit caller declarations, not authenticated publications
or evidence that supplied molecular contracts hold in cells. No contracts,
sequences, limits or implementation models are invented by this module.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import io
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Callable, Literal, Sequence, cast
import zipfile

from biocompiler.core_client import CoreCancelled, CoreClient, CoreProtocolError, JsonValue, decode_json, encode_json
from biocompiler.core_distribution import installed_core
from biocompiler import core_policy_component_material as component
from biocompiler import core_policy_component_selection as selection
from biocompiler.core_policy_material import PolicyMaterialResult
from . import component_material, component_selection
from .material import _destination, _verify_staged

SCHEMA = "biocompiler.research_project.v0.1"
MAX_PROJECT_BYTES = 8 * 1024 * 1024
MAX_BUNDLE_BYTES = 16 * 1024 * 1024
Route = Literal["component_material", "component_selection"]


class ResearchProjectError(ValueError):
    """Incomplete project authority or a research bundle that does not match it."""


class ResearchProjectRejected(ResearchProjectError):
    """An actual nonaccepted native result, retained for actionable diagnostics."""
    def __init__(self, compiled: PolicyMaterialResult) -> None:
        super().__init__("Core did not accept this complete project; no bundle was published")
        self._compiled = compiled

    @property
    def compiled(self) -> PolicyMaterialResult:
        return self._compiled

    @property
    def status(self) -> str:
        return self._compiled.status

    @property
    def report(self) -> dict[str, JsonValue]:
        return self._compiled.report


def _require(condition: object, message: str) -> None:
    if not condition:
        raise ResearchProjectError(message)


def _text(value: object, label: str, maximum: int = 4096) -> str:
    _require(type(value) is str and bool(value.strip()) and len(value.encode("utf-8")) <= maximum,
             label + " requires a nonempty bounded string")
    return cast(str, value)


@dataclass(frozen=True)
class SourceRecord:
    """Versioned external-source declaration; its digest is not fetched or trusted as evidence."""
    id: str
    locator: str
    version: str
    sha256: str
    role: str
    reuse_terms: str

    def __post_init__(self) -> None:
        for name in ("id", "locator", "version", "role", "reuse_terms"):
            _text(getattr(self, name), "Source " + name)
        _require(type(self.sha256) is str and re.fullmatch(r"[0-9a-f]{64}", self.sha256),
                 "Source sha256 requires the exact lowercase digest of the independently retained source")


@dataclass(frozen=True)
class ProjectPreflight:
    """Transport readiness only; native support and biological behavior remain unassessed."""
    project_sha256: str
    route: Route
    source_count: int
    status: Literal["structurally_ready"] = "structurally_ready"
    native_status: Literal["not_run"] = "not_run"
    biological_status: Literal["unassessed"] = "unassessed"
    provenance_status: Literal["caller_declared"] = "caller_declared"


@dataclass(frozen=True)
class ProjectBuild:
    """Separate current producer and verifier results, with the published destination."""
    project_sha256: str
    compiled: PolicyMaterialResult
    verified: PolicyMaterialResult
    output: Path


def _route(request: JsonValue) -> Route:
    _require(type(request) is dict, "A complete original component or selection request is required")
    row = cast(dict[str, JsonValue], request)
    if row.get("schema_version") == component.REQUEST_SCHEMA:
        component._original(row)
        return "component_material"
    if row.get("schema_version") == selection.REQUEST_SCHEMA:
        selection._original(row)
        return "component_selection"
    raise ResearchProjectError("Unsupported or incomplete original request; provide a complete component-material or component-selection contract")


def _project(value: JsonValue) -> dict[str, JsonValue]:
    _require(type(value) is dict and set(value) == {"schema_version", "project_id", "title", "route", "request", "limits", "sources", "assumptions"},
             "Research project requires its complete versioned fields, original request, limits and provenance")
    row = cast(dict[str, JsonValue], value)
    _require(row["schema_version"] == SCHEMA, "Unsupported research project schema")
    _text(row["project_id"], "Project id", 128)
    _text(row["title"], "Project title")
    _require(row["route"] == _route(row["request"]), "Project route differs from its complete original request")
    _require(type(row["limits"]) is dict and bool(row["limits"]), "Explicit original execution limits are required")
    sources = row["sources"]
    _require(type(sources) is list and 1 <= len(sources) <= 128, "One to 128 independent source records are required")
    ids: set[str] = set()
    for source in cast(list[JsonValue], sources):
        _require(type(source) is dict and set(source) == {"id", "locator", "version", "sha256", "role", "reuse_terms"},
                 "Source records require exact identity, version, digest, role and reuse terms")
        record = SourceRecord(**cast(dict[str, str], source))
        _require(record.id not in ids, "Source ids must be unique")
        ids.add(record.id)
    assumptions = row["assumptions"]
    _require(type(assumptions) is list and len(assumptions) <= 128, "Assumptions must be an explicit bounded list")
    for assumption in cast(list[JsonValue], assumptions):
        _text(assumption, "Assumption")
    return row


def _read_file(path: Path, maximum: int) -> bytes:
    """Read one bounded regular file without following a final symlink or opening a FIFO."""
    _require(not path.is_symlink(), "Research inputs cannot be symbolic links")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        before = os.fstat(source.fileno())
        _require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= maximum,
                 "Research input must be a nonempty bounded regular file")
        raw = source.read(maximum + 1)
        after = os.fstat(source.fileno())
    _require(len(raw) == before.st_size and len(raw) <= maximum and
             (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
             "Research input changed during reading")
    return raw


def _cancel(cancelled: Callable[[], bool] | None) -> None:
    if cancelled is not None and cancelled():
        raise CoreCancelled("Research project operation cancelled")


def _transport(value: CoreClient | None, role: Literal["core", "verify"], operation: str, timeout_seconds: float) -> CoreClient:
    if value is None:
        return cast(CoreClient, installed_core(role=role, operation=operation, timeout_seconds=timeout_seconds))
    _require(type(value) is CoreClient and value.role == role, "Research workflow requires a separate explicit " + role + " executable role")
    return value


def _client(route: Route, transport: CoreClient) -> component.PolicyComponentMaterialClient | selection.PolicyComponentSelectionClient:
    return (component.PolicyComponentMaterialClient(transport) if route == "component_material"
            else selection.PolicyComponentSelectionClient(transport))


@dataclass(frozen=True)
class ResearchProject:
    """Immutable full caller authority; properties return detached JSON snapshots."""
    _json: bytes
    _input_paths: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        _require(type(self._json) is bytes and len(self._json) <= MAX_PROJECT_BYTES, "Project requires bounded canonical JSON bytes")
        row = _project(decode_json(self._json))
        _require(encode_json(row, limit=MAX_PROJECT_BYTES) == self._json, "Project bytes must use canonical JSON encoding")
        _require(type(self._input_paths) is tuple and all(isinstance(path, Path) for path in self._input_paths),
                 "Project input paths must be immutable paths")

    @classmethod
    def from_request(cls, *, project_id: str, title: str, request: JsonValue, limits: JsonValue,
                     sources: Sequence[SourceRecord], assumptions: Sequence[str]) -> ResearchProject:
        """Snapshot supplied contracts unchanged; never supply missing implementation authority."""
        _require(not isinstance(sources, (str, bytes)) and all(type(source) is SourceRecord for source in sources),
                 "Sources must be explicit SourceRecord values")
        _require(not isinstance(assumptions, (str, bytes)), "Assumptions must be an explicit sequence")
        return cls.from_data({"schema_version": SCHEMA, "project_id": project_id, "title": title,
            "route": _route(request), "request": request, "limits": limits,
            "sources": cast(JsonValue, [asdict(source) for source in sources]), "assumptions": list(assumptions)})

    @classmethod
    def from_data(cls, value: JsonValue) -> ResearchProject:
        """Freeze an inert versioned project; this does not run semantic admission."""
        return cls(encode_json(value, limit=MAX_PROJECT_BYTES))

    @classmethod
    def load(cls, path: Path | str) -> ResearchProject:
        """Load bounded JSON only; source locators are never followed or executed."""
        source = Path(path)
        project = cls.from_data(decode_json(_read_file(source, MAX_PROJECT_BYTES)))
        return cls(project._json, (source.resolve(),))

    @property
    def data(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], decode_json(self._json))

    @property
    def request(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.data["request"])

    @property
    def limits(self) -> dict[str, JsonValue]:
        return cast(dict[str, JsonValue], self.data["limits"])

    @property
    def digest(self) -> str:
        return hashlib.sha256(self._json).hexdigest()

    @property
    def route(self) -> Route:
        return cast(Route, self.data["route"])

    def preflight(self) -> ProjectPreflight:
        """Report structural readiness only; native capability/admission has not run."""
        return ProjectPreflight(self.digest, self.route, len(cast(list[JsonValue], self.data["sources"])))

    def dump(self, path: Path | str, *, replace: bool = False) -> None:
        """Publish canonical project JSON atomically without overwriting loaded originals."""
        output = Path(path)

        def destination() -> Path:
            _require(not output.is_symlink(), "Project output cannot replace a symbolic link")
            target = output.resolve()
            _require(target.parent.is_dir(), "Project output parent directory does not exist")
            _require(not target.exists() or target.is_file(), "Project output must be a regular file")
            for original in self._input_paths:
                _require(target != original.resolve() and not
                    (target.exists() and original.exists() and os.path.samefile(target, original)),
                    "Project output cannot overwrite or alias a loaded original")
            if target.exists() and not replace:
                raise FileExistsError("Project output exists; explicit replacement is required")
            return target

        target = destination()
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile("wb", prefix=".research-project-", dir=target.parent, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(self._json)
                handle.flush()
                os.fsync(handle.fileno())
            _require(destination() == target and _read_file(temporary, MAX_PROJECT_BYTES) == self._json,
                     "Project output changed during publication")
            if replace:
                os.replace(temporary, target)
            else:
                os.link(temporary, target)
                temporary.unlink()
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def compile(self, *, output: Path | str, core: CoreClient | None = None, verify: CoreClient | None = None,
                timeout_seconds: float = 300.0, replace: bool = False,
                cancelled: Callable[[], bool] | None = None) -> ProjectBuild:
        """Generate with Core, then independently Verify and atomically publish the exact pair."""
        destination = _destination(Path(output), self._input_paths, replace=replace)
        _require(destination.parent.is_dir(), "Bundle output parent directory does not exist")
        _cancel(cancelled)
        route = self.route
        suffix = "policy-component-material" if route == "component_material" else "policy-component-selection"
        producer = _transport(core, "core", "compile-" + suffix, timeout_seconds)
        verifier = _transport(verify, "verify", "export-" + suffix, timeout_seconds)
        compiled = _client(route, producer).compile(self.request, self.limits, cancelled=cancelled)
        accepted = component.ACCEPTED_STATUS if route == "component_material" else selection.ACCEPTED_STATUS
        _require(compiled.executable == "core" and compiled.operation == "compile-" + suffix,
                 "Producer result changed the requested executable role or operation")
        if compiled.status != accepted:
            raise ResearchProjectRejected(compiled)
        _cancel(cancelled)
        verified: PolicyMaterialResult
        if route == "component_material":
            verified = component_material.export(self.request, candidate=compiled.candidate, limits=self.limits,
                client=component.PolicyComponentMaterialClient(verifier), output=Path(output),
                input_paths=self._input_paths, replace=replace, cancelled=cancelled)
        else:
            verified = component_selection.export(self.request, candidate=compiled.candidate, limits=self.limits,
                client=selection.PolicyComponentSelectionClient(verifier), output=Path(output),
                input_paths=self._input_paths, replace=replace, cancelled=cancelled)
        return ProjectBuild(self.digest, compiled, verified, destination)

    def verify_bundle(self, bundle: Path | str, *, verify: CoreClient | None = None,
                      timeout_seconds: float = 300.0, cancelled: Callable[[], bool] | None = None) -> PolicyMaterialResult:
        """Freshly Verify a candidate against this independent project and compare every exported byte."""
        path = Path(bundle)
        raw = _read_file(path, MAX_BUNDLE_BYTES)
        _cancel(cancelled)
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries = archive.infolist()
                _require([entry.filename for entry in entries] == ["program.fasta", "manifest.json"] and
                    all(entry.compress_type == zipfile.ZIP_STORED and not entry.flag_bits and
                        0 < entry.file_size <= MAX_BUNDLE_BYTES for entry in entries),
                    "Bundle must contain exactly the bounded, uncompressed FASTA and manifest pair")
                _require(sum(entry.file_size for entry in entries) <= MAX_BUNDLE_BYTES, "Bundle exceeds its complete byte bound")
                members = []
                for entry in entries:
                    with archive.open(entry) as member:
                        content = member.read(entry.file_size + 1)
                    _require(len(content) == entry.file_size, "Bundle member changed its bounded size")
                    members.append((entry.filename, content))
        except (zipfile.BadZipFile, RuntimeError, EOFError) as error:
            raise ResearchProjectError("Malformed research bundle") from error
        _verify_staged(path, tuple(members))
        manifest = decode_json(members[1][1])
        _require(type(manifest) is dict and "candidate" in manifest, "Bundle lacks a complete candidate")
        original = cast(dict[str, JsonValue], manifest)
        _require(encode_json(original.get("request")) == encode_json(self.request) and
                 encode_json(original.get("limits")) == encode_json(self.limits),
                 "Bundle original authority differs from the independently supplied current project")
        route = self.route
        suffix = "policy-component-material" if route == "component_material" else "policy-component-selection"
        verifier = _transport(verify, "verify", "export-" + suffix, timeout_seconds)
        fresh = _client(route, verifier).export(self.request, original["candidate"], self.limits, cancelled=cancelled)
        artifact = fresh.artifact
        _require(fresh.executable == "verify" and artifact is not None, "Independent Verify did not produce an accepted pair")
        artifact = cast(dict[str, JsonValue], artifact)
        fasta = artifact.get("fasta")
        _require(type(fasta) is str, "Independent Verify did not return exact FASTA bytes")
        expected = [("program.fasta", cast(str, fasta).encode("utf-8")), ("manifest.json", encode_json(artifact["manifest"]))]
        _require(members == expected, "Bundle differs from the independently verified exact FASTA/manifest pair")
        _cancel(cancelled)
        _require(_read_file(path, MAX_BUNDLE_BYTES) == raw, "Bundle changed during independent verification")
        return fresh
