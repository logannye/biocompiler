#!/usr/bin/env python3
"""Seed an exact, absent setup-python toolcache entry on hosted macOS ARM64.

This is dependency acquisition, not a build or a compiler acceptance gate. The
reviewed manifest pins a published CPython archive; no fallback version, local
execution, pre-existing cache adoption, package installation or native build is
allowed. Invoke with the runner's /usr/bin/python3 -I -S -B before setup-python.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import posixpath
import stat
import subprocess
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request

MANIFEST = "protocol/hosted-python-macos-arm64-v1.json"
SCHEMA = "biocompiler.hosted_python_macos_arm64.v1"
RECEIPT_SCHEMA = "biocompiler.hosted_python_bootstrap.v1"
CHUNK = 1024 * 1024
PROBE = (
    "import json, pathlib, platform, sys; "
    "print(json.dumps({'version': platform.python_version(), "
    "'implementation': platform.python_implementation(), 'system': platform.system(), "
    "'machine': platform.machine(), 'executable': str(pathlib.Path(sys.executable).resolve()), "
    "'prefix': str(pathlib.Path(sys.prefix).resolve()), "
    "'base_prefix': str(pathlib.Path(sys.base_prefix).resolve())}, sort_keys=True))"
)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _no_symlinks(path):
    for candidate in (path, *path.parents):
        _require(not candidate.is_symlink(), "Symlink in bootstrap filesystem path")


def _closed_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate JSON object key")
        result[key] = value
    return result


def _no_number(value):
    raise ValueError("Only exact integer JSON numbers are allowed")


def _source_pins(root):
    paths = {"manifest_sha256": root / MANIFEST, "helper_sha256": Path(__file__)}
    for path in paths.values():
        _no_symlinks(path)
    return {name: _sha256(path) for name, path in paths.items()}


def load_manifest(root):
    path = root / MANIFEST
    _no_symlinks(path)
    _require(path.is_file() and path.stat().st_size <= 16384, "Invalid bootstrap manifest")
    with path.open("rb") as stream:
        encoded = stream.read(16385)
    _require(len(encoded) <= 16384, "Bootstrap manifest exceeds size bound")
    value = json.loads(encoded, object_pairs_hook=_closed_object,
                       parse_float=_no_number, parse_constant=_no_number)
    _require(set(value) == {"schema_version", "python_version", "implementation", "system", "machine", "archive", "limits", "cache"}, "Unexpected bootstrap manifest fields")
    _require(value["schema_version"] == SCHEMA and value["python_version"] == "3.11.15"
             and value["implementation"] == "CPython" and value["system"] == "Darwin"
             and value["machine"] == "arm64", "Unsupported bootstrap runtime")
    _require(value["cache"] == {"version": "3.11.15", "architecture": "arm64"}, "Unsupported bootstrap cache slot")
    archive = value["archive"]
    _require(set(archive) == {"url", "release_tag", "asset_id", "size", "sha256"}, "Unexpected bootstrap archive fields")
    _require(archive == {
        "url": "https://github.com/astral-sh/python-build-standalone/releases/download/20260325/cpython-3.11.15%2B20260325-aarch64-apple-darwin-install_only.tar.gz",
        "release_tag": "20260325", "asset_id": 381125647, "size": 20082612,
        "sha256": "054a5e5645c87538df903aa5ffee9ae6b84323545b63bcd0e01285bda8898b6c",
    }, "Unreviewed bootstrap archive pin")
    _require(value["limits"] == {"members": 30000, "expanded_bytes": 268435456, "file_bytes": 134217728}, "Unreviewed archive bounds")
    return value


def validate_hosted_environment(environ, *, system, machine):
    _require(environ.get("GITHUB_ACTIONS") == "true"
             and environ.get("RUNNER_ENVIRONMENT") == "github-hosted"
             and environ.get("RUNNER_OS") == "macOS"
             and environ.get("RUNNER_ARCH") == "ARM64"
             and system == "Darwin" and machine == "arm64", "Python bootstrap requires hosted macOS ARM64")
    raw = environ.get("RUNNER_TOOL_CACHE", "")
    cache = Path(raw)
    _require(bool(raw) and cache.is_absolute(), "Absolute RUNNER_TOOL_CACHE required")
    _no_symlinks(cache)
    _require(cache.is_dir(), "Runner tool cache must exist")
    return cache


def download_archive(specification, destination):
    """Acquire bounded bytes only; the digest is checked before tar parsing."""
    pin = specification["archive"]
    _no_symlinks(destination)
    _require(not destination.exists(), "Refusing to overwrite bootstrap archive")
    request = urllib.request.Request(pin["url"], headers={"User-Agent": "biocompiler-hosted-python-bootstrap/1", "Accept": "application/octet-stream"})
    started, size, digest = time.monotonic(), 0, hashlib.sha256()
    with urllib.request.urlopen(request, timeout=30) as response, destination.open("xb") as output:
        final = urllib.parse.urlsplit(response.geturl())
        _require(final.scheme == "https" and final.hostname in {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"}, "Untrusted archive download destination")
        length = response.headers.get("Content-Length")
        _require(length is None or length == str(pin["size"]), "Archive response length differs from pin")
        while True:
            _require(time.monotonic() - started <= 180, "Archive download exceeded time bound")
            block = response.read(min(CHUNK, pin["size"] - size + 1))
            if not block:
                break
            size += len(block)
            _require(size <= pin["size"], "Archive download exceeded size pin")
            digest.update(block)
            output.write(block)
    _require(size == pin["size"] and digest.hexdigest() == pin["sha256"], "Archive bytes do not match reviewed pin")


def _archive_name(name):
    _require(isinstance(name, str) and 0 < len(name) <= 1024 and "\\" not in name and "\x00" not in name, "Unsafe archive name")
    _require(not name.endswith("//"), "Ambiguous trailing archive separators")
    name = name.removesuffix("/")
    parts = name.split("/")
    _require(parts[0] == "python" and all(part not in {"", ".", ".."} for part in parts), "Archive path outside python root")
    return name


def _link_target(name, target):
    _require(bool(target) and not target.startswith("/") and "\\" not in target and "\x00" not in target and len(target) <= 1024, "Unsafe archive link")
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
    _require(resolved == "python" or resolved.startswith("python/"), "Archive link escapes python root")
    return resolved


def validate_archive(path, specification):
    _no_symlinks(path)
    pin, limits = specification["archive"], specification["limits"]
    _require(path.is_file() and path.stat().st_size == pin["size"] and _sha256(path) == pin["sha256"], "Archive bytes do not match reviewed pin")
    members, names, total = [], {}, 0
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            name = _archive_name(member.name)
            _require(name not in names, "Duplicate archive member")
            _require(member.isfile() or member.isdir() or member.issym(), "Unsupported archive member type")
            _require(not getattr(member, "sparse", None) and member.mode & ~0o777 == 0, "Unsupported archive sparse file or special mode")
            _require(member.size >= 0 and member.size <= limits["file_bytes"], "Archive member size exceeds bound")
            _require(member.isfile() or member.size == 0, "Non-file archive member has data")
            total += member.size
            _require(total <= limits["expanded_bytes"] and len(members) < limits["members"], "Archive expansion exceeds bounds")
            names[name] = member
            members.append(member)
    for name, member in names.items():
        for parent in PurePosixPath(name).parents:
            if str(parent) in names:
                _require(names[str(parent)].isdir(), "Archive member traverses a file or link")
        if member.issym():
            target, visited = name, set()
            while names.get(target) is not None and names[target].issym():
                _require(target not in visited, "Cyclic archive link")
                visited.add(target)
                target = _link_target(target, names[target].linkname)
            _require(target in names, "Archive link target is absent")
            for parent in PurePosixPath(target).parents:
                _require(str(parent) not in names or names[str(parent)].isdir(), "Archive link target traverses another link")
    _require("python/bin/python" in names and "python/bin/python3.11" in names, "Archive lacks required Python executable")
    actual = names["python/bin/python3.11"]
    _require(actual.isfile() and actual.mode & 0o111, "Python executable is not an executable regular file")
    target, visited = "python/bin/python", set()
    while names[target].issym():
        _require(target not in visited, "Cyclic Python executable link")
        visited.add(target)
        target = _link_target(target, names[target].linkname)
    _require(target == "python/bin/python3.11", "Python launcher differs from pinned executable")
    return members


def closure_snapshot(directory):
    """Hash every entry without following links; include names and permission bits."""
    _no_symlinks(directory)
    result = {}
    for current, directories, files in os.walk(directory, followlinks=False):
        for name in sorted(directories + files):
            path = Path(current) / name
            relative = path.relative_to(directory).as_posix()
            info = path.lstat()
            if stat.S_ISLNK(info.st_mode):
                result[relative] = {"kind": "symlink", "target": os.readlink(path)}
            elif stat.S_ISDIR(info.st_mode):
                result[relative] = {"kind": "directory", "mode": stat.S_IMODE(info.st_mode)}
            elif stat.S_ISREG(info.st_mode):
                _require(info.st_nlink == 1, "Unexpected hardlink in Python cache")
                result[relative] = {"kind": "file", "mode": stat.S_IMODE(info.st_mode), "size": info.st_size, "sha256": _sha256(path)}
            else:
                raise ValueError("Unsupported entry in Python cache")
    return result


def extract_archive(path, destination, specification):
    members = validate_archive(path, specification)
    _no_symlinks(destination)
    _require(not destination.exists(), "Refusing existing extraction destination")
    destination.mkdir(mode=0o755)
    expected = {}
    # No tar.extract/all: create parents, regular bytes, and finally safe links.
    for member in members:
        name = _archive_name(member.name)
        relative = PurePosixPath(name).relative_to("python")
        if str(relative) == ".":
            _require(member.isdir(), "Archive python root must be a directory")
            continue
        for parent in reversed(relative.parents):
            if str(parent) != ".":
                target = destination / str(parent)
                if not target.exists():
                    target.mkdir(mode=0o755)
                expected.setdefault(str(parent), {"kind": "directory", "mode": 0o755})
        if member.isdir():
            (destination / str(relative)).mkdir(mode=0o755, exist_ok=True)
            expected[str(relative)] = {"kind": "directory", "mode": member.mode & 0o777}
    with tarfile.open(path, "r:gz") as archive:
        for member in members:
            relative = str(PurePosixPath(_archive_name(member.name)).relative_to("python"))
            if not member.isfile():
                continue
            target, digest, copied = destination / relative, hashlib.sha256(), 0
            source = archive.extractfile(member)
            _require(source is not None, "Missing regular archive bytes")
            with source, target.open("xb") as output:
                while True:
                    block = source.read(CHUNK)
                    if not block:
                        break
                    copied += len(block)
                    _require(copied <= member.size, "Archive member exceeds declared size")
                    digest.update(block)
                    output.write(block)
            _require(copied == member.size, "Truncated archive member")
            target.chmod(member.mode & 0o777)
            expected[relative] = {"kind": "file", "mode": member.mode & 0o777, "size": copied, "sha256": digest.hexdigest()}
    for member in members:
        if member.issym():
            relative = str(PurePosixPath(_archive_name(member.name)).relative_to("python"))
            (destination / relative).symlink_to(member.linkname)
            expected[relative] = {"kind": "symlink", "target": member.linkname}
    for relative, item in expected.items():
        if item["kind"] == "directory":
            (destination / relative).chmod(item["mode"])
    _require(path.stat().st_size == specification["archive"]["size"] and _sha256(path) == specification["archive"]["sha256"], "Archive changed during extraction")
    _require(closure_snapshot(destination) == expected, "Extracted Python closure differs from archive")
    return expected


def verify_runtime(executable, specification):
    prefix = executable.parent.parent.resolve()
    expected = {name: specification[key] for name, key in (("version", "python_version"), ("implementation", "implementation"), ("system", "system"), ("machine", "machine"))}
    expected.update(executable=str(executable.resolve()), prefix=str(prefix), base_prefix=str(prefix))
    # Ignore ambient Python variables, site customizations and writable bytecode.
    completed = subprocess.run([str(executable), "-I", "-S", "-B", "-c", PROBE], cwd=str(prefix), env={key: value for key, value in os.environ.items() if not key.startswith(("PYTHON", "DYLD_", "LD_"))}, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, check=False)
    _require(completed.returncode == 0 and not completed.stderr and len(completed.stdout) <= 16384, "Bootstrapped Python runtime probe failed")
    actual = json.loads(completed.stdout)
    _require(actual == expected, "Bootstrapped Python identity differs from pinned runtime")
    return actual


def _persist_receipt(output, receipt, *, replace=False):
    encoded = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    _require(len(encoded) <= 16384, "Bootstrap receipt exceeds size bound")
    _no_symlinks(output)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=str(output.parent),
                                         prefix=".bootstrap-receipt-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, output)
        else:
            # Exclusive publication never replaces a path created by another process.
            os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def bootstrap(root, output, *, environ=None):
    environment = dict(os.environ if environ is None else environ)
    cache_root = validate_hosted_environment(environment, system=platform.system(), machine=platform.machine())
    root = root.resolve()
    _require(environment.get("GITHUB_WORKSPACE") == str(root), "Bootstrap workspace differs from checkout")
    revision = environment.get("GITHUB_SHA", "")
    _require(len(revision) == 40 and all(char in "0123456789abcdef" for char in revision), "Full source revision required")
    _require(all(environment.get(key, "").isdigit() and int(environment[key]) > 0 for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")), "Positive hosted run identity required")
    source_pins = _source_pins(root)
    specification = load_manifest(root)
    _require(_source_pins(root) == source_pins, "Bootstrap sources changed during admission")
    cache = cache_root / "Python" / specification["cache"]["version"] / specification["cache"]["architecture"]
    marker = cache.with_name(cache.name + ".complete")
    _no_symlinks(cache)
    _no_symlinks(marker)
    _require(not cache.exists() and not marker.exists(), "Refusing unknown existing Python cache or complete marker")
    output = output if output.is_absolute() else root / output
    _no_symlinks(output)
    output = output.resolve()
    _require(not output.exists(), "Refusing existing bootstrap receipt")
    _require(output.is_relative_to(root), "Bootstrap receipt must remain in checkout")
    output.parent.mkdir(parents=True, exist_ok=True)
    receipt = {"schema_version": RECEIPT_SCHEMA, "status": "failed", "acceptance": False,
               **source_pins, "archive": specification["archive"],
               "cache": str(cache), "marker": str(marker),
               "run": {key: environment.get(key) for key in ("GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")}}
    receipt_written = False
    marker_created = False
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".biocompiler-python-", dir=str(cache.parent)) as temporary:
            archive = Path(temporary) / "python.tar.gz"
            download_archive(specification, archive)
            extracted = Path(temporary) / "extracted"
            expected = extract_archive(archive, extracted, specification)
            _require(closure_snapshot(extracted) == expected, "Python closure changed before publication")
            _require(not cache.exists() and not marker.exists(), "Python cache appeared during bootstrap")
            extracted.rename(cache)
            _require(closure_snapshot(cache) == expected, "Python closure changed before execution")
            receipt["runtime"] = verify_runtime(cache / "bin/python", specification)
            _require(closure_snapshot(cache) == expected, "Python closure changed during runtime probe")
            receipt["closure_entries"] = len(expected)
            receipt["closure_bytes"] = sum(item.get("size", 0) for item in expected.values())
            receipt["closure_sha256"] = hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            _require(_source_pins(root) == source_pins, "Bootstrap sources changed before completion")
            receipt["status"] = "ready"
            _persist_receipt(output, receipt)
            receipt_written = True
            _require(_source_pins(root) == source_pins, "Bootstrap sources changed during receipt publication")
            with marker.open("x", encoding="utf-8") as stream:
                marker_created = True
                stream.flush()
                os.fsync(stream.fileno())
    except Exception as error:
        if marker_created:
            marker.unlink()
        receipt["status"] = "failed"
        receipt["error"] = str(error)
        try:
            _persist_receipt(output, receipt, replace=receipt_written)
        except Exception as persistence_error:
            receipt["receipt_error"] = str(persistence_error)
        raise
    finally:
        print(json.dumps(receipt, sort_keys=True))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    bootstrap(Path(__file__).resolve().parents[1], arguments.output)


if __name__ == "__main__":
    main()
