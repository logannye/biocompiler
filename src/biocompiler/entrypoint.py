"""Dispatch authoring commands before importing the historical compiler CLI."""

from __future__ import annotations

from collections.abc import Sequence
import sys


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "policy":
        from biocompiler.policy.cli import main as policy_main

        return policy_main(arguments[1:])
    from biocompiler import _load_legacy_exports

    _load_legacy_exports()
    from biocompiler.cli import main as legacy_main

    return legacy_main(arguments)
