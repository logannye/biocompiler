"""Inspect the planned compiler architecture without claiming compilation."""

import argparse
from collections.abc import Sequence

from cellweave import __version__
from cellweave.ir.stages import STAGE_ORDER


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=f"cellweave {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("architecture", help="Show planned intermediate representations")
    args = parser.parse_args(argv)
    if args.command == "architecture":
        print("CellWeave planned pipeline (scaffold; no lowering passes implemented)")
        print("Python authoring")
        for stage in STAGE_ORDER:
            print(f"  -> {stage.value}")
        print("  -> packaged digital build artifact")
    return 0
