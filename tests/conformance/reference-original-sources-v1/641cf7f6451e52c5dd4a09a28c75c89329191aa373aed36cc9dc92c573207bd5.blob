"""Selected native workflow CLI orchestration and structural presentation.

The native service decides source validity, execution, acceptance and command
status. This module reads bounded files and projects complete native views; its
publication callback is the original atomic report writer. Replay validates the
source before reading history, then freshly validates the same source bytes
again during execution. Preflight alone never authorizes a retained result.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Callable, cast

from biocompiler.core_client import CoreClient, CoreError, CoreRejected
from biocompiler.core_workflow_authority import AuthorityClient
from biocompiler.errors import BiocompilerError, SerializationError
from biocompiler.ir.serialization import parse_json
from biocompiler.workflow_backend import (
    NativeWorkflowRecord, WorkflowCoreError, replay_document, run_document,
)


def _core(args: Any) -> CoreClient:
    verifier = args.verify_executable
    executable = args.core_executable if args.core_executable is not None else verifier
    if executable is None:
        raise SerializationError("Core timeout and digest options require an explicit executable.")
    return CoreClient(executable, role="verify" if verifier is not None else "core",
                      expected_sha256=args.core_sha256,
                      timeout_seconds=30.0 if args.core_timeout is None else args.core_timeout)


def summary(record: NativeWorkflowRecord) -> dict[str, Any]:
    """Copy native outcome fields and native presentation counts verbatim."""
    operation = record.request.operation
    result = record.result
    value = {
        "record_fingerprint": record.fingerprint,
        "request_fingerprint": record.request.fingerprint,
        "operation": operation,
        "mode": record.request.mode,
        "intended_use": "software_test",
        "human_therapeutic_admission": "not_admitted",
        "claim_scope": record.claim_scope,
    }
    if operation == "check":
        value.update(outcome=result.outcome.value,
            diagnostics=[item.to_dict() for item in result.diagnostics],
            counterexamples=[item.to_dict() for item in result.counterexamples],
            coverage=[item.to_dict() for item in result.coverage])
    elif operation == "explore":
        value.update(complete=result.complete, all_passed=result.all_passed,
            evaluated_histories=result.evaluated_histories, possible_histories=result.possible_histories,
            outcome_counts=dict(result.outcome_counts), bounds=result.config.to_dict())
    else:
        value.update(outcome=result.result.outcome.value, one_minimal=result.one_minimal,
            evaluations=result.evaluations,
            original_frames=record.presentation["original_frames"],
            reduced_frames=record.presentation["reduced_frames"],
            selected_failure=result.signature.to_dict())
    return value


def _error_message(error: Exception) -> str:
    cause = error.core_error if isinstance(error, WorkflowCoreError) else error
    if isinstance(cause, CoreRejected) and len(cause.response.diagnostics) == 1:
        # Legacy CLI errors expose their human-readable message. The SDK keeps
        # the complete native diagnostic code and path on its structured cause.
        return cause.response.diagnostics[0].message
    return str(error)


def selected_core_command(args: Any, *, bounded_text: Callable[..., str],
                          publish_report: Callable[..., None]) -> int:
    try:
        core = _core(args)
        if args.command == "synthetic-replay":
            authority_text = bounded_text(args.expected_request)
            parse_json(authority_text)
            authority = authority_text.encode("utf-8")
            AuthorityClient(core).validate(authority)
            historical_text = bounded_text(args.path, 64 * 1024 * 1024)
            parse_json(historical_text)
            historical = historical_text.encode("utf-8")
            record, _native = replay_document(request=authority, record=historical,
                                               core=core, command=args.command)
            inputs: tuple[Any, ...] = (args.path, args.expected_request)
        else:
            authority_text = bounded_text(args.request)
            parse_json(authority_text)
            authority = authority_text.encode("utf-8")
            record, _native = run_document(request=authority, core=core, command=args.command)
            inputs = (args.request,)
        publish_report(record, args.output, inputs=inputs)
        value = summary(record)
        if args.command == "synthetic-replay":
            value["replay"] = (
                "Fresh execution reproduced the declared outcome; this does not turn a failure or unknown into PASS."
            )
        if args.output:
            value["output"] = str(args.output)
        print(json.dumps(value, indent=2))
        return cast(int, record.command_exit_code)
    except (OSError, UnicodeError, BiocompilerError, CoreError, ValueError, RecursionError) as error:
        print(f"biocompiler: {_error_message(error)}", file=sys.stderr)
        return 2
