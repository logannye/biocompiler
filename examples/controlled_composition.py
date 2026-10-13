"""Editable artificial two-RNA workflow through the installed public SDK.

Preparation and inspection are inert. Every acceptance and RNA publication comes
from fresh native Core and Verify under complete caller-supplied authority.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import stat
import sys

from biocompiler.core_client import CoreClient, decode_json
from biocompiler.policy.controlled_workflow import ControlledWorkflowRequest
from biocompiler.policy.research_project import ResearchProject, ResearchProjectRejected

MAX_INPUT_BYTES = 4_000_000


def read_input(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Original must be a regular non-symlink file")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_INPUT_BYTES:
            raise ValueError("Original exceeds its regular-file byte bound")
        raw = stream.read(MAX_INPUT_BYTES + 1)
        after = os.fstat(stream.fileno())
    if len(raw) != before.st_size or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError("Original changed during reading")
    return ControlledWorkflowRequest.from_request(decode_json(raw))


def _save(build, output, original):
    destination, source = Path(output), Path(original)
    if destination.resolve() == source.resolve() or (destination.exists() and source.samefile(destination)):
        raise ValueError("Output cannot overwrite its independent original")
    project = ResearchProject.from_controlled(build)
    project.dump(destination)
    return project


def prepare(input_path, output):
    """Preserve the complete frozen input and its source-bound project metadata."""
    return _save(read_input(input_path), output, input_path)


def edit(project_path, output, *, max_member_rna_nt=None, max_total_rna_nt=None,
         deadlines=None, horizon_input=None, material_input=None):
    """Apply explicit public typed edits; selected inputs remain independent files."""
    project = ResearchProject.load(project_path)
    build = project.controlled
    if max_member_rna_nt is not None or max_total_rna_nt is not None:
        if max_member_rna_nt is None or max_total_rna_nt is None:
            raise ValueError("Supply both RNA ceilings explicitly")
        build = build.with_rna_limits(max_member_rna_nt=max_member_rna_nt, max_total_rna_nt=max_total_rna_nt)
    if deadlines is not None:
        build = build.with_deadlines(**deadlines)
    if horizon_input is not None:
        selected = read_input(horizon_input).behavior.to_request()
        domain = selected["original"]["operating_domain"]
        build = build.with_horizon(domain["horizon_tick"], readout_evidence=selected["readout_evidence"], operating_domain=domain)
    if material_input is not None:
        authority = read_input(material_input).behavior.original.to_request()["material_authority"]
        build = build.with_material_authority(authority)
    return _save(build, output, project_path)


def preflight(project_path):
    return asdict(ResearchProject.load(project_path).preflight())


def explain(project_path, report=None):
    """Describe supplied authority and retained diagnostics, without evaluating it."""
    project = ResearchProject.load(project_path)
    original = project.controlled.behavior.original.to_request()
    contract = original["source_authority"]["control_contract"]
    return {"project_sha256": project.digest, "endpoint": "receptor activity; not expression or cell killing",
        "products": [row["product"]["sequence"] for row in original["material_authority"]["members"]],
        "rna_members": original["material_authority"]["member_order"],
        "controller": "executor-scoped external dependency; not an RNA member",
        "requested_deadlines": contract["requested_deadlines"], "actual_delays": contract["actual_delays"],
        "horizon_tick": original["operating_domain"]["horizon_tick"],
        "same_cell_assumptions": original["context"]["co_delivery"]["assumptions"],
        "rna_bounds": {key: original["resources"][key] for key in ("max_member_rna_nt", "max_total_rna_nt")},
        "empirical_status": "unassessed", "human_use": "unassessed", "native_report": report}


def compile_project(project_path, output, *, core=None, verify=None, cancelled=None):
    return ResearchProject.load(project_path).compile(output=output, core=core, verify=verify, cancelled=cancelled)


def verify_project(project_path, bundle, *, verify=None, cancelled=None):
    return ResearchProject.load(project_path).verify_bundle(bundle, verify=verify, cancelled=cancelled)


def _transport(args, role):
    path, digest = getattr(args, role, None), getattr(args, role + "_sha256", None)
    if bool(path) != bool(digest):
        raise ValueError("Explicit native executable requires its exact SHA-256")
    return CoreClient(Path(path).absolute(), role=role, expected_sha256=digest) if path else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("prepare"); create.add_argument("input", type=Path); create.add_argument("output", type=Path)
    for name in ("preflight", "explain"):
        command = commands.add_parser(name); command.add_argument("project", type=Path)
    change = commands.add_parser("edit"); change.add_argument("project", type=Path); change.add_argument("output", type=Path)
    for field in ("max-member-rna-nt", "max-total-rna-nt", "onset-ticks", "controller-off-ticks", "antigen-off-ticks", "component-off-ticks", "reactivation-ticks"):
        change.add_argument("--" + field, type=int)
    for field in ("horizon-input", "material-input"): change.add_argument("--" + field, type=Path)
    for name, roles in (("compile", ("core", "verify")), ("verify", ("verify",))):
        command = commands.add_parser(name); command.add_argument("project", type=Path); command.add_argument("bundle", type=Path)
        for role in roles:
            command.add_argument("--" + role, type=Path); command.add_argument("--" + role + "-sha256")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare": result = asdict(prepare(args.input, args.output).preflight())
        elif args.command == "preflight": result = preflight(args.project)
        elif args.command == "explain": result = explain(args.project)
        elif args.command == "edit":
            deadlines = {key: getattr(args, key) for key in ("onset_ticks", "controller_off_ticks", "antigen_off_ticks", "component_off_ticks", "reactivation_ticks") if getattr(args, key) is not None}
            edited = edit(args.project, args.output, max_member_rna_nt=args.max_member_rna_nt,
                max_total_rna_nt=args.max_total_rna_nt, deadlines=deadlines or None,
                horizon_input=args.horizon_input, material_input=args.material_input)
            result = asdict(edited.preflight())
        elif args.command == "compile":
            built = compile_project(args.project, args.bundle, core=_transport(args, "core"), verify=_transport(args, "verify"))
            result = explain(args.project, built.verified.report)
        else:
            verified = verify_project(args.project, args.bundle, verify=_transport(args, "verify"))
            result = explain(args.project, verified.report)
        print(json.dumps(result, sort_keys=True)); return 0
    except ResearchProjectRejected as error:
        print(json.dumps({"status": error.status, "report": error.report, "artifact": "absent"}, sort_keys=True), file=sys.stderr); return 1
    except (OSError, ValueError, RuntimeError) as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr); return 1


if __name__ == "__main__":
    raise SystemExit(main())
