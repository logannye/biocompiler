"""Fixed reviewed reference-build inputs, independent of emitted candidates.

Only the explicitly pinned FAP DNA/RNA CDS records are supported. Loading stays
offline and requires a caller-selected reference directory. Retained evidence is
read as bounded regular files, without following source-file symlinks.
"""

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from types import MappingProxyType

from biocompiler.errors import SerializationError
from biocompiler.ir.component_contracts import PinnedIdentity
from biocompiler.ir.composition import CompositionInstance, CompositionRequest
from biocompiler.ir.serialization import require
from biocompiler.registry.components import ComponentRegistry
from biocompiler.registry.reference_components import (
    ReferenceSelection,
    adapt_reference_component,
)
from biocompiler.registry.references import ReferenceManifest, load_reference_manifest
from biocompiler.semantics.component_contracts import OperatingDomain
from biocompiler.semantics.context import PayloadFormat, TargetContext
from biocompiler.synthesis.construct import prepare_reference_construct

REFERENCE_BUILD_INPUTS_VERSION = "biocompiler.reference_build_inputs.v0.1"
MAX_REFERENCE_FILE_BYTES = 16 * 1024 * 1024

# These reviewed expectations are never calculated from an emitted candidate.
MANIFEST_PIN = PinnedIdentity(
    "reference",
    "wo2022081694a1.murine-fapcar.cds",
    "1",
    "e6bd93305ccf638757844d744c9ce9f8d84bbea4cfed40ba4cb224f28e610102",
)
REFERENCE_PINS = MappingProxyType(
    {
        "DNA": PinnedIdentity(
            "reference",
            "wo2022081694a1.murine-fapcar.seq2",
            "1",
            "be64d2c4e6a5887a78c193be6f3aa747460487fa3e0a3a479784a95f58bcad90",
        ),
        "RNA": PinnedIdentity(
            "reference",
            "wo2022081694a1.murine-fapcar.seq3",
            "1",
            "8c4deb2c377aa04b1586abdef9eda951418ea3dc04b3146dba2a2bef5b40a5d5",
        ),
    }
)


def _directory(reference_directory):
    require(
        isinstance(reference_directory, (str, Path))
        and bool(str(reference_directory).strip()),
        "A reference directory must be supplied explicitly.",
    )
    path = Path(reference_directory)
    require(not path.is_symlink(), "Reference directories must not be symlinks.")
    root = path.resolve(strict=True)
    require(root.is_dir(), "The reference input path must be a directory.")
    return root


def _read_file(root, relative_path):
    require(
        isinstance(relative_path, str) and bool(relative_path),
        "Invalid retained reference path.",
    )
    relative = PurePosixPath(relative_path)
    require(
        not relative.is_absolute()
        and relative_path == relative.as_posix()
        and all(part not in {"", ".", ".."} for part in relative.parts)
        and "\\" not in relative_path,
        "Retained reference paths must be canonical relative file paths.",
    )
    path = root
    for part in relative.parts:
        path = path / part
        require(
            not path.is_symlink(), "Retained reference files must not use symlinks."
        )
    require(
        path.resolve(strict=True).is_relative_to(root),
        "Retained reference path escapes its directory.",
    )
    require(path.is_file(), "Retained reference evidence must be a regular file.")
    require(
        path.stat().st_size <= MAX_REFERENCE_FILE_BYTES,
        "Retained reference file exceeds the bounded offline input size.",
    )
    with path.open("rb") as stream:
        data = stream.read(MAX_REFERENCE_FILE_BYTES + 1)
    require(
        len(data) <= MAX_REFERENCE_FILE_BYTES,
        "Retained reference file exceeds the bounded offline input size.",
    )
    return data


def _retained_paths(manifest):
    paths = {}
    for item in manifest.sources:
        if item["local_path"] is not None:
            paths[item["local_path"]] = item["sha256"]
    for item in manifest.reviews:
        evidence = item["evidence"]
        if evidence is not None:
            path = evidence["local_path"]
            require(
                path not in paths or paths[path] == evidence["sha256"],
                "Conflicting retained reference identities.",
            )
            paths[path] = evidence["sha256"]
    require(
        "manifest.json" not in paths, "Reference evidence cannot replace its manifest."
    )
    return paths


def _load_pinned_inputs(reference_directory):
    """Return one checked evidence snapshot with deterministic manifest spelling."""
    try:
        root = _directory(reference_directory)
        manifest = ReferenceManifest.from_json(
            _read_file(root, "manifest.json").decode("utf-8")
        )
        require(
            PinnedIdentity(
                "reference",
                manifest.reference_set_id,
                manifest.version,
                manifest.fingerprint,
            )
            == MANIFEST_PIN,
            "Reference build manifest differs from the independently reviewed pin.",
        )
        retained = {}
        for path, expected_hash in sorted(_retained_paths(manifest).items()):
            data = _read_file(root, path)
            require(
                hashlib.sha256(data).hexdigest() == expected_hash,
                f"Retained reference hash mismatch: {path}.",
            )
            retained[path] = data
        # Preserve the shared loader's evidence validation as an independent gate.
        # Bounded, symlink-free preflight above runs before its file reads.
        checked = load_reference_manifest(
            root / "manifest.json",
            expected_fingerprint=MANIFEST_PIN.content_fingerprint,
        )
        require(
            checked.fingerprint == manifest.fingerprint,
            "Reference manifest changed while reading offline inputs.",
        )
        return checked, {"manifest.json": checked.to_json().encode("utf-8"), **retained}
    except (OSError, UnicodeError) as error:
        raise SerializationError(
            f"Cannot read pinned offline reference inputs: {error}"
        ) from error


def load_reference_inputs(alphabet, reference_directory):
    """Return the pinned ConstructRequest, manifest and registry for DNA or RNA.

    The directory is explicit so relocated packages and installed wheels use the
    same profile without relying on a checkout path or executable authoring file.
    """
    require(
        isinstance(alphabet, str) and alphabet in REFERENCE_PINS,
        "The reviewed reference build supports only DNA or RNA.",
    )
    manifest, _ = _load_pinned_inputs(reference_directory)
    selection = ReferenceSelection(MANIFEST_PIN, REFERENCE_PINS[alphabet])
    component = adapt_reference_component(manifest, selection)
    registry = ComponentRegistry("reviewed-cds", "1", (component,))
    lock = registry.lock({"fap_cds": component})
    requirements = ("preserve_selected_cds",)
    composition = CompositionRequest(
        TargetContext("reference", "1", PayloadFormat(alphabet)),
        lock,
        (
            CompositionInstance(
                "fap_cds",
                lock.components[0],
                OperatingDomain(),
                requirement_ids=requirements,
            ),
        ),
        requirement_ids=requirements,
    )
    request = prepare_reference_construct(manifest, selection, composition, registry)
    return request, manifest, registry


def collect_reference_files(reference_directory, manifest):
    """Collect only pinned manifest/source/review bytes for offline reconstruction.

    Manifest JSON is canonicalized; source and review bytes remain exact. Remote
    source URLs are metadata and are never fetched. Unrelated directory files and
    authoring scripts are excluded from the returned inventory.
    """
    require(
        isinstance(manifest, ReferenceManifest),
        "Expected a reviewed reference manifest.",
    )
    checked, files = _load_pinned_inputs(reference_directory)
    require(
        manifest.fingerprint == checked.fingerprint,
        "Supplied manifest differs from the current pinned offline reference snapshot.",
    )
    return files
