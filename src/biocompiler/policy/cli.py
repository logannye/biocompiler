"""Data-only policy authoring commands; no compiler or semantic execution."""

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
        description="Inspect and check policy authoring documents. Native semantics and target realizability remain unassessed.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("check", "Check authoring structure and unresolved declarations."),
        ("inspect", "Inspect declarations and their authoring status."),
        ("diff", "Compare complete authoring documents."),
        ("export-schema", "Export the versioned authoring document schema."),
        ("export-request", "Export a structurally complete request for a future native backend."),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--json", action="store_true", default=argparse.SUPPRESS, help="Print machine-readable JSON.")
        if name != "export-schema":
            command.add_argument("path", type=Path, help="Saved policy authoring JSON document.")
        if name == "diff":
            command.add_argument("other", type=Path, help="Document to compare against.")
        command.add_argument("--output", "-o", type=Path, help="Write complete JSON atomically to this path.")
        command.add_argument("--replace", action="store_true", help="Explicitly permit atomic replacement of an existing output file.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    if arguments.replace and arguments.output is None:
        parser.error("--replace requires --output")
    try:
        from .serialization import PolicySerializationError, load, schema, to_data
        from .handoff import SubmissionError

        inputs: tuple[Path, ...] = ()
        exit_code = 0
        result: object
        if arguments.command == "export-schema":
            result = schema()
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
        elif arguments.json or arguments.command in ("export-schema", "export-request"):
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
