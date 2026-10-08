"""Policy authoring and explicitly selected bounded native policy commands."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

_OPERATIONAL_COMMANDS = ("compile-native", "check-lowering-native", "execute-native", "replay-execution-native")
_IMPLEMENTATION_COMMANDS = ("compile-implementation-native", "check-implementation-native", "replay-implementation-native")
_MATERIAL_COMMANDS = ("compile-material-native", "check-material-native", "replay-material-native", "export-material-native")


def _operational_json(path: Path, *, field: str | None = None) -> object:
    """Read inert bounded JSON; optionally extract an earlier transport result."""
    from biocompiler.core_client import LIMITS, decode_json
    from biocompiler.core_policy_operational import RESULT_SCHEMA

    with path.open("rb") as stream:
        content = stream.read(LIMITS["max_request_bytes"] + 1)
    if len(content) > LIMITS["max_request_bytes"]:
        raise ValueError("Operational input exceeds the native request byte budget.")
    value = decode_json(content)
    if field is not None and isinstance(value, dict) and value.get("schema_version") == RESULT_SCHEMA:
        if field not in value:
            raise ValueError("Saved operational result is missing " + field + ".")
        return value[field]
    return value


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def _write(path: Path, text: str, *, replace: bool, inputs: Sequence[Path] = ()) -> None:
    """Publish one complete file, with no overwrite unless explicitly selected."""
    destination = path.absolute()
    if any(destination.resolve() == source.resolve() for source in inputs):
        raise ValueError("Output must not replace an input document.")
    try:
        metadata = destination.lstat()
    except FileNotFoundError:
        metadata = None
    if metadata is not None:
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("Output must be a regular file, not a directory or symbolic link.")
        if not replace:
            raise FileExistsError("Output exists; pass --replace to replace it explicitly.")
    descriptor, temporary = tempfile.mkstemp(prefix=".biocompiler-policy-", suffix=".tmp", dir=destination.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            if stream.write(text) != len(text):
                raise OSError("Incomplete output write.")
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, destination)
        else:
            # Same-directory linking is atomic and does not overwrite a file
            # created after the initial existence check.
            os.link(temporary, destination)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="biocompiler policy",
        description="Inspect policy documents and explicitly invoke bounded native operations. Material claims require the separate complete supplied-contract profile.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("check", "Check authoring structure and unresolved declarations."),
        ("inspect", "Inspect declarations and their authoring status."),
        ("diff", "Compare complete authoring documents."),
        ("export-schema", "Export the versioned authoring document schema."),
        ("export-request", "Export a structurally complete request for a future native backend."),
        ("assess-native", "Independently assess frozen source with an explicitly selected native executable."),
        ("compile-native", "Lower the supported operational policy subset using an explicitly selected native core."),
        ("check-lowering-native", "Independently check a candidate against complete original policy authority."),
        ("execute-native", "Check and execute an operational candidate on a bounded supplied timeline."),
        ("replay-execution-native", "Freshly replay a complete retained bounded execution report."),
        ("compile-implementation-native", "Lower and independently check an implementation over its complete finite domain."),
        ("check-implementation-native", "Independently check an implementation against the complete original realization request."),
        ("replay-implementation-native", "Freshly reproduce the full retained implementation-check wrapper."),
        ("compile-material-native", "Lower and freshly check a complete supplied policy-to-mRNA case."),
        ("check-material-native", "Independently reconstruct the complete policy/material/context chain."),
        ("replay-material-native", "Freshly reproduce the entire saved material-check wrapper."),
        ("export-material-native", "Freshly check and atomically export the exact RNA/manifest pair as a ZIP archive."),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Print machine-readable JSON.")
        if name != "export-schema":
            command.add_argument("path", type=Path, help="Saved policy authoring JSON document.")
        if name == "diff":
            command.add_argument("other", type=Path, help="Document to compare against.")
        if name in ("assess-native", "compile-native", "check-lowering-native", "execute-native", "replay-execution-native", "compile-implementation-native", "check-implementation-native", "replay-implementation-native", "compile-material-native", "check-material-native", "replay-material-native", "export-material-native"):
            backend = command.add_mutually_exclusive_group(required=True)
            backend.add_argument("--core", type=Path, help="Absolute path to the selected Core executable.")
            if name not in ("compile-native", "compile-implementation-native", "compile-material-native"):
                backend.add_argument("--verify", type=Path, help="Absolute path to the selected independent Verify executable.")
            command.add_argument("--expected-sha256", help="Optional caller-supplied executable SHA-256 pin.")
            command.add_argument("--timeout", type=float, default=30.0, help="Positive per-exchange timeout in seconds.")
        if name in ("compile-native", "check-lowering-native", "execute-native", "replay-execution-native"):
            command.add_argument("--definitions", required=True, type=Path, help="Separately supplied operational definition JSON.")
            if name != "compile-native":
                command.add_argument("--candidate", required=True, type=Path, help="Candidate JSON or a complete saved operational result.")
            if name in ("execute-native", "replay-execution-native"):
                command.add_argument("--timeline", required=True, type=Path, help="Timeline JSON retaining all explicit execution bounds.")
            if name == "replay-execution-native":
                command.add_argument("--report", required=True, type=Path, help="Complete report JSON or a complete saved operational result.")
        if name in ("compile-implementation-native", "check-implementation-native", "replay-implementation-native"):
            command.add_argument("--limits", required=True, type=Path, help="Explicit preservation execution and publication resource limits.")
            if name != "compile-implementation-native":
                command.add_argument("--candidate", required=True, type=Path, help="Implementation candidate JSON or complete saved implementation result.")
            if name == "replay-implementation-native":
                command.add_argument("--report", required=True, type=Path, help="Entire saved implementation result wrapper; inner reports are insufficient.")
        if name in ("compile-material-native", "check-material-native", "replay-material-native", "export-material-native"):
            command.add_argument("--limits", required=True, type=Path, help="Explicit original preservation execution limits.")
            if name != "compile-material-native":
                command.add_argument("--candidate", required=True, type=Path, help="Complete material candidate or saved material result.")
            if name == "replay-material-native":
                command.add_argument("--report", required=True, type=Path, help="Entire saved material result wrapper.")
        command.add_argument("--output", "-o", type=Path, help="Atomically write JSON; material export writes one RNA/manifest ZIP archive.")
        command.add_argument("--replace", action="store_true", help="Explicitly permit atomic replacement of an existing output file.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    if arguments.replace and arguments.output is None:
        parser.error("--replace requires --output")
    if arguments.command == "export-material-native" and arguments.output is None:
        parser.error("export-material-native requires --output for the inseparable RNA/manifest archive")
    try:
        from .serialization import PolicySerializationError, load, schema, to_data
        from .handoff import SubmissionError

        inputs: tuple[Path, ...] = ()
        exit_code = 0
        result: object
        if arguments.command == "export-schema":
            result = schema()
        elif arguments.command in _MATERIAL_COMMANDS:
            from typing import cast

            from biocompiler.core_client import CoreClient, CoreError, JsonValue
            from biocompiler.core_policy_material import PolicyMaterialClient, RESULT_SCHEMA

            request = cast(JsonValue, _operational_json(arguments.path))
            limits = cast(JsonValue, _operational_json(arguments.limits))
            inputs = (arguments.path, arguments.limits)
            try:
                transport = CoreClient(arguments.core or arguments.verify,
                                       role="core" if arguments.core else "verify",
                                       timeout_seconds=arguments.timeout,
                                       expected_sha256=arguments.expected_sha256)
                material_client = PolicyMaterialClient(transport)
                if arguments.command == "compile-material-native":
                    material_result = material_client.compile(request, limits)
                else:
                    candidate = cast(JsonValue, _operational_json(arguments.candidate))
                    if isinstance(candidate, dict) and candidate.get("schema_version") == RESULT_SCHEMA:
                        if "candidate" not in candidate:
                            raise ValueError("Saved material result is missing candidate.")
                        candidate = candidate["candidate"]
                    inputs += (arguments.candidate,)
                    if arguments.command == "check-material-native":
                        material_result = material_client.check(request, candidate, limits)
                    elif arguments.command == "replay-material-native":
                        saved = cast(JsonValue, _operational_json(arguments.report))
                        inputs += (arguments.report,)
                        material_result = material_client.replay(request, candidate, limits, saved)
                    else:
                        from .material import export

                        material_result = export(request, candidate=candidate, limits=limits, client=material_client,
                                                 output=arguments.output, input_paths=inputs, replace=arguments.replace)
                        notice = {"status": "written", "operation": arguments.command,
                                  "output": str(arguments.output), "format": "RNA_FASTA_and_canonical_manifest_zip"}
                        print(_json(notice) if arguments.json else "Wrote " + str(arguments.output),
                              end="" if arguments.json else "\n")
                        return 0
            except CoreError as error:
                raise ValueError(str(error)) from error
            result = material_result.result
            exit_code = 0 if material_result.status == "checked_material" else 1
        elif arguments.command in _IMPLEMENTATION_COMMANDS:
            from typing import cast

            from biocompiler.core_client import CoreClient, CoreError, JsonValue
            from biocompiler.core_policy_implementation import PolicyImplementationClient, RESULT_SCHEMA

            # This is a complete realization envelope, not an authoring document.
            # Read inert bounded JSON before the separate authoring loader below.
            request = cast(JsonValue, _operational_json(arguments.path))
            limits = cast(JsonValue, _operational_json(arguments.limits))
            inputs = (arguments.path, arguments.limits)
            try:
                transport = CoreClient(arguments.core or arguments.verify,
                                       role="core" if arguments.core else "verify",
                                       timeout_seconds=arguments.timeout,
                                       expected_sha256=arguments.expected_sha256)
                implementation_client = PolicyImplementationClient(transport)
                if arguments.command == "compile-implementation-native":
                    implementation_result = implementation_client.compile(request, limits)
                else:
                    candidate = cast(JsonValue, _operational_json(arguments.candidate))
                    if isinstance(candidate, dict) and candidate.get("schema_version") == RESULT_SCHEMA:
                        if "candidate" not in candidate:
                            raise ValueError("Saved implementation result is missing candidate.")
                        candidate = candidate["candidate"]
                    inputs += (arguments.candidate,)
                    if arguments.command == "check-implementation-native":
                        implementation_result = implementation_client.check(request, candidate, limits)
                    else:
                        saved = cast(JsonValue, _operational_json(arguments.report))
                        inputs += (arguments.report,)
                        implementation_result = implementation_client.replay(request, candidate, limits, saved)
            except CoreError as error:
                raise ValueError(str(error)) from error
            result = implementation_result.result
            exit_code = 0 if implementation_result.status == "checked_implementation" else 1
        else:
            record = load(arguments.path)
            inputs = (arguments.path,)
            if arguments.command == "check":
                from .validation import check

                report = check(record)
                result = report.to_dict()
                exit_code = 0 if report.status == "complete" else 1
            elif arguments.command == "inspect":
                from .inspection import inspect

                result = inspect(record)
            elif arguments.command == "diff":
                from .inspection import diff

                result = diff(record, load(arguments.other))
                exit_code = 0 if result["identical_document"] else 1
                inputs += (arguments.other,)
            elif arguments.command == "assess-native":
                from biocompiler.core_client import CoreClient, CoreError
                from biocompiler.core_policy import PolicyClient
                from .native import assess
                from .model import BuildRequest, CompilationSubmission, PolicyProgram

                if not isinstance(record, (PolicyProgram, BuildRequest, CompilationSubmission)):
                    raise ValueError("Native assessment requires a frozen program, request or submission.")
                try:
                    transport = CoreClient(arguments.core or arguments.verify,
                                           role="core" if arguments.core else "verify",
                                           timeout_seconds=arguments.timeout,
                                           expected_sha256=arguments.expected_sha256)
                    assessment = assess(record, client=PolicyClient(transport))
                except CoreError as error:
                    raise ValueError(str(error)) from error
                result = assessment.assessment
                exit_code = 0 if assessment.status == "valid" else 1
            elif arguments.command in _OPERATIONAL_COMMANDS:
                from typing import cast

                from biocompiler.core_client import CoreClient, CoreError, JsonValue
                from biocompiler.core_policy_operational import OperationalPolicyClient
                from . import operational
                from .model import BuildRequest, CompilationSubmission, PolicyProgram

                if not isinstance(record, (PolicyProgram, BuildRequest, CompilationSubmission)):
                    raise ValueError("Native operations require a frozen program, request or submission.")
                try:
                    transport = CoreClient(arguments.core or arguments.verify,
                                           role="core" if arguments.core else "verify",
                                           timeout_seconds=arguments.timeout,
                                           expected_sha256=arguments.expected_sha256)
                    operational_client = OperationalPolicyClient(transport)
                    definitions = cast(JsonValue, _operational_json(arguments.definitions))
                    inputs += (arguments.definitions,)
                    if arguments.command == "compile-native":
                        native_result = operational.compile(record, definitions=definitions, client=operational_client)
                    else:
                        candidate = cast(JsonValue, _operational_json(arguments.candidate, field="candidate"))
                        inputs += (arguments.candidate,)
                        if arguments.command == "check-lowering-native":
                            native_result = operational.check_lowering(record, definitions=definitions,
                                                                       candidate=candidate, client=operational_client)
                        else:
                            timeline = cast(JsonValue, _operational_json(arguments.timeline))
                            inputs += (arguments.timeline,)
                            if arguments.command == "execute-native":
                                native_result = operational.execute(record, definitions=definitions, candidate=candidate,
                                                                    timeline=timeline, client=operational_client)
                            else:
                                retained_report = cast(JsonValue, _operational_json(arguments.report, field="report"))
                                inputs += (arguments.report,)
                                native_result = operational.replay(record, definitions=definitions, candidate=candidate,
                                                                   timeline=timeline, report=retained_report, client=operational_client)
                except CoreError as error:
                    raise ValueError(str(error)) from error
                result = native_result.result
                if arguments.command in ("execute-native", "replay-execution-native"):
                    execution = cast(dict[str, JsonValue], native_result.report["execution"])
                    requirement_results = cast(list[dict[str, JsonValue]], execution["requirements"])
                    exit_code = 1 if any(row["status"] == "fail" for row in requirement_results) else 0
            else:
                from .handoff import prepare_submission

                result = to_data(prepare_submission(record))
        text = _json(result)
        if arguments.output is not None:
            _write(arguments.output, text, replace=arguments.replace, inputs=inputs)
            notice = {
                "status": "written",
                "operation": arguments.command,
                "output": str(arguments.output),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
            if arguments.json:
                print(_json(notice), end="")
            else:
                print(f"Wrote {arguments.output}")
        elif arguments.json or arguments.command in ("export-schema", "export-request", "assess-native", *_OPERATIONAL_COMMANDS, *_IMPLEMENTATION_COMMANDS, *_MATERIAL_COMMANDS):
            print(text, end="")
        else:
            label = {"check": "Authoring check", "inspect": "Authoring inspection", "diff": "Authoring comparison"}[arguments.command]
            print(label + " (native semantics and target realizability unassessed)")
            print(text, end="")
        return exit_code
    except (OSError, ValueError, TypeError) as error:
        if arguments.json:
            print(_json({"status": "error", "operation": arguments.command, "message": str(error)}), file=sys.stderr, end="")
        else:
            print(f"Policy authoring error: {error}", file=sys.stderr)
        return 1 if isinstance(error, (PolicySerializationError, SubmissionError)) else 2


if __name__ == "__main__":
    raise SystemExit(main())
