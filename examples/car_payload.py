"""Prepare and check an editable nominal CAR RNA project with the installed SDK.

The RM_61461 reference retains its complete published nominal sequence and
source-declared chemistry. Its unreported terminal chemistry requires an
explicit designer choice. Native checks do not establish biological behavior.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from biocompiler.core_client import CoreClient
from biocompiler.policy.car_reference import rm61461_request
from biocompiler.policy.research_project import ResearchProject, ResearchProjectRejected


def prepare(output, *, maximum_rna_nt, three_prime_end):
    request = rm61461_request(maximum_rna_nt=maximum_rna_nt, three_prime_end=three_prime_end)
    project = ResearchProject.from_expression(request)
    project.dump(Path(output))
    return project


def _project(project_path):
    project = ResearchProject.load(project_path)
    # This starter is the static expression route; do not silently select a
    # temporal component route when a different project is supplied.
    _ = project.expression
    return project


def preflight(project_path):
    return asdict(_project(project_path).preflight())


def compile_project(project_path, output, *, core=None, verify=None):
    return _project(project_path).compile(output=output, core=core, verify=verify)


def verify_project(project_path, bundle, *, verify=None):
    return _project(project_path).verify_bundle(bundle, verify=verify)


def _transport(args, role):
    path = getattr(args, role, None)
    digest = getattr(args, role + "_sha256", None)
    if bool(path) != bool(digest):
        raise ValueError("Explicit executable selection requires its matching SHA-256")
    return CoreClient(Path(path), role=role, expected_sha256=digest) if path else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("prepare", help="Save an editable typed nominal CAR expression project")
    create.add_argument("output", type=Path)
    create.add_argument("--max-rna-nt", type=int, required=True, help="Explicit upper bound on the complete RNA length")
    create.add_argument("--three-prime-end", choices=("designer_supplied_hydroxyl",), required=True,
                        help="Explicit design choice; the publication's physical 3prime chemistry is unreported")
    inspect = commands.add_parser("preflight", help="Check project structure without native execution")
    inspect.add_argument("project", type=Path)
    build = commands.add_parser("compile", help="Generate with Core, freshly check with Verify, then publish the pair")
    build.add_argument("project", type=Path)
    build.add_argument("output", type=Path)
    check = commands.add_parser("verify", help="Freshly check a bundle against the independently retained project")
    check.add_argument("project", type=Path)
    check.add_argument("bundle", type=Path)
    for command, roles in ((build, ("core", "verify")), (check, ("verify",))):
        for role in roles:
            command.add_argument("--" + role, type=Path, help="Optional executable; defaults to the owned installed package")
            command.add_argument("--" + role + "-sha256")
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            result = asdict(prepare(args.output, maximum_rna_nt=args.max_rna_nt,
                                    three_prime_end=args.three_prime_end).preflight())
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
