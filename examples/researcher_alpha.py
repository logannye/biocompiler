"""Prepare, inspect, compile and independently verify a caller-owned project.

This standalone example uses only the installed public Python SDK. Preparation
accepts a complete {request, limits} JSON document; it does not invent missing
implementation contracts or establish their biological validity.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

from biocompiler.core_client import CoreClient, decode_json
from biocompiler.policy.research_project import MAX_PROJECT_BYTES, ResearchProject, ResearchProjectRejected, SourceRecord


def prepare(input_path, output, *, project_id, title, version, reuse_terms):
    source, destination = Path(input_path), Path(output)
    if source.is_symlink() or not source.is_file():
        raise ValueError("Input must be a regular, non-symlink JSON file")
    if source.resolve() == destination.resolve() or (destination.exists() and source.samefile(destination)):
        raise ValueError("Project output cannot overwrite its original input")
    descriptor = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_PROJECT_BYTES:
            raise ValueError("Input must be a nonempty bounded regular file")
        raw = handle.read(MAX_PROJECT_BYTES + 1)
        after = os.fstat(handle.fileno())
    if len(raw) != before.st_size or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError("Original input changed during reading")
    original = decode_json(raw)
    if type(original) is not dict or set(original) != {"request", "limits"}:
        raise ValueError("Input requires exactly the complete original request and limits")
    project = ResearchProject.from_request(project_id=project_id, title=title,
        request=original["request"], limits=original["limits"], sources=[SourceRecord(
            id="original-input", locator=source.name, version=version,
            sha256=hashlib.sha256(raw).hexdigest(), role="caller_supplied_complete_contract",
            reuse_terms=reuse_terms)], assumptions=[
                "Supplied implementation and material contracts are premises; biological validity is unassessed.",
                "Acceptance is limited to the exact supported native profile and supplied bounded domain."])
    project.dump(destination)
    return project


def preflight(project_path):
    return asdict(ResearchProject.load(project_path).preflight())


def compile_project(project_path, output, *, core=None, verify=None):
    return ResearchProject.load(project_path).compile(output=output, core=core, verify=verify)


def verify_project(project_path, bundle, *, verify=None):
    return ResearchProject.load(project_path).verify_bundle(bundle, verify=verify)


def _transport(args, role):
    path = getattr(args, role, None)
    digest = getattr(args, role + "_sha256", None)
    if bool(path) != bool(digest):
        raise ValueError("Explicit executable selection requires its matching SHA-256")
    return CoreClient(Path(path), role=role, expected_sha256=digest) if path else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("prepare", help="Freeze complete caller inputs as a versioned project")
    create.add_argument("input", type=Path)
    create.add_argument("output", type=Path)
    for field in ("project-id", "title", "version", "reuse-terms"):
        create.add_argument("--" + field, required=True)
    inspect = commands.add_parser("preflight", help="Check transport structure without native execution")
    inspect.add_argument("project", type=Path)
    build = commands.add_parser("compile", help="Compile, independently Verify, then publish the exact pair")
    build.add_argument("project", type=Path)
    build.add_argument("output", type=Path)
    check = commands.add_parser("verify", help="Freshly verify a bundle against independently retained originals")
    check.add_argument("project", type=Path)
    check.add_argument("bundle", type=Path)
    for command, roles in ((build, ("core", "verify")), (check, ("verify",))):
        for role in roles:
            command.add_argument("--" + role, type=Path, help="Optional explicit executable; defaults to owned installed package")
            command.add_argument("--" + role + "-sha256")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = asdict(prepare(args.input, args.output, project_id=args.project_id,
                title=args.title, version=args.version, reuse_terms=args.reuse_terms).preflight())
        elif args.command == "preflight":
            result = preflight(args.project)
        elif args.command == "compile":
            built = compile_project(args.project, args.output, core=_transport(args, "core"), verify=_transport(args, "verify"))
            result = {"project_sha256": built.project_sha256, "output": str(built.output),
                      "status": built.verified.status, "biological_status": "unassessed"}
        else:
            verified = verify_project(args.project, args.bundle, verify=_transport(args, "verify"))
            result = {"status": verified.status, "operation": verified.operation,
                      "executable": verified.executable, "biological_status": "unassessed"}
        print(json.dumps(result, sort_keys=True))
        return 0
    except ResearchProjectRejected as error:
        print(json.dumps({"status": error.status, "report": error.report,
                          "artifact": "absent", "biological_status": "unassessed"}, sort_keys=True), file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
