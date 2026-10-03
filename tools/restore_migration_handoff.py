"""Verify or restore the frozen, unfinished migration source/evidence packet.

This never applies a patch, imports the drafts, builds code, or overwrites a
different existing file. Restored paths remain under ignored generated/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "docs/migration-handoff/2026-10-02"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    manifest = json.loads((PACKET / "manifest.json").read_bytes())
    require(manifest["schema_version"] == "biocompiler.migration_handoff.v1", "Unknown packet")
    archive = PACKET / "drafts.tar.gz"
    raw = archive.read_bytes()
    require(len(raw) == manifest["archive_bytes"] and
            hashlib.sha256(raw).hexdigest() == manifest["archive_sha256"], "Archive identity changed")
    expected = {row["path"]: row for row in manifest["files"]}
    require(len(expected) == len(manifest["files"]), "Duplicate manifest member")
    require(sum(row["bytes"] for row in expected.values()) <= 256 * 1024 * 1024, "Packet too large")
    verified = {}
    with tarfile.open(archive, "r:gz") as source:
        for member in source:
            name = member.name
            path = PurePosixPath(name)
            require(member.isfile() and not path.is_absolute() and ".." not in path.parts and
                    path.parts[:2] == ("generated", "migration-next") and
                    name in expected and name not in verified, "Unexpected archive member")
            row = expected[name]
            require(member.size == row["bytes"] and member.size <= 32 * 1024 * 1024,
                    "Member size differs")
            stream = source.extractfile(member)
            require(stream is not None, "Missing member content")
            content = stream.read(member.size + 1)
            require(len(content) == member.size and
                    hashlib.sha256(content).hexdigest() == row["sha256"], "Member identity changed")
            verified[name] = content
    require(set(verified) == set(expected), "Incomplete archive")
    written = 0
    if args.restore:
        root = args.root.resolve()
        # Validate every destination before creating any file.
        for name, content in verified.items():
            target = root / name
            for parent in (target, *target.parents):
                if parent == root:
                    break
                require(not parent.is_symlink(), "Refusing symlinked destination: " + name)
            require(not target.exists() or (target.is_file() and target.read_bytes() == content),
                    "Existing file differs; restore into a fresh directory: " + name)
        for name, content in verified.items():
            target = root / name
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("xb") as destination:
                    destination.write(content)
                written += 1
    print(json.dumps({"status": "restored" if args.restore else "verified",
                      "files": len(verified), "written": written,
                      "bytes": sum(map(len, verified.values())), "native_execution": False}))


if __name__ == "__main__":
    main()
