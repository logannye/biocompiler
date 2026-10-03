"""File and publication orchestration for explicit native synthetic selection.

The complete build request goes to native authority unchanged. Native decisions
and native presentation choose output and exit status; Python only formats the
complete retained report and invokes the original atomic publication callback.
"""
from __future__ import annotations

import sys
from typing import Any, Callable

from biocompiler.core_client import CoreClient, CoreError, CoreRejected
from biocompiler.core_synthetic_producer_public import SyntheticProducerPublicClient
from biocompiler.errors import BiocompilerError, SerializationError
from biocompiler.ir.serialization import parse_json
from biocompiler.synthetic_producer_backend import view_result


def _core(args: Any) -> CoreClient:
    if args.core_executable is None:
        raise SerializationError("Core timeout and digest options require an explicit executable.")
    return CoreClient(args.core_executable, expected_sha256=args.core_sha256,
        timeout_seconds=30.0 if args.core_timeout is None else args.core_timeout)


def _error_message(error: Exception) -> str:
    if isinstance(error, CoreRejected) and len(error.response.diagnostics) == 1:
        return error.response.diagnostics[0].message
    return str(error)


def selection_command(args: Any, *, bounded_text: Callable[..., str],
                      publish_report: Callable[..., None]) -> int:
    try:
        core = _core(args)
        raw = bounded_text(args.request)
        # Preserve original duplicate-key, invalid-number and JSON syntax errors
        # without constructing a Python SyntheticBuildRequest.
        parse_json(raw)
        result = SyntheticProducerPublicClient(core).select_document(raw.encode("utf-8"))
        view = view_result(result.production)
        publish_report(view, args.output, inputs=(args.request,))
        print(view.to_json())
        return result.exit_code
    except (OSError, UnicodeError, BiocompilerError, CoreError, ValueError, RecursionError) as error:
        print(f"biocompiler: {_error_message(error)}", file=sys.stderr)
        return 2
