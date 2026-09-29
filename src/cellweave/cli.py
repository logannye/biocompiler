"""Inspect authored intent graphs and the planned compiler architecture."""

import argparse
from collections.abc import Sequence
import json
from pathlib import Path
import sys

from cellweave import __version__
from cellweave.ir.stages import STAGE_ORDER
from cellweave.errors import SerializationError
from cellweave.ir.intent import IntentProgram


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version", action="version", version=f"cellweave {__version__}"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "architecture", help="Show planned intermediate representations"
    )
    inspect_command = commands.add_parser(
        "inspect", help="Inspect a saved intent JSON graph"
    )
    inspect_command.add_argument("path", type=Path, help="IntentProgram JSON file")
    inspect_command.add_argument(
        "--json", action="store_true", help="Print the normalized full graph"
    )
    args = parser.parse_args(argv)
    if args.command == "architecture":
        print(
            "CellWeave pipeline (intent authoring implemented; molecular lowering planned)"
        )
        print("Python authoring -> immutable intent graph")
        for stage in STAGE_ORDER:
            print(f"  -> {stage.value}")
        print("  -> packaged digital build artifact")
    elif args.command == "inspect":
        try:
            program = IntentProgram.from_json(args.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SerializationError) as exc:
            print(f"cellweave: {exc}", file=sys.stderr)
            return 2
        print(
            program.to_json() if args.json else json.dumps(program.summary(), indent=2)
        )
    return 0
