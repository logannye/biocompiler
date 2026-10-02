#!/usr/bin/env python3
"""Replay the immutable workflow freezer with explicit signature-only lineage.

The original freezer, raw observations, assertion corpus and goldens stay exact.
The added optional ``core=None`` appears in current derived bindings. Only that
default is projected, after exact source/AST review and independent historical
signature binding. Every full actual binding remains in a separate receipt.
"""
from __future__ import annotations

import argparse
import ast
from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import workflow_source_lineage as lineage


def historical_signature(name):
    lineage.require(name in lineage.FUNCTIONS, "Unreviewed workflow signature")
    entry = lineage.load_witness()[lineage.WORKFLOW]
    lineage.verify_extension(entry, (ROOT / lineage.WORKFLOW).read_bytes(), entry["historical_sha256"])
    function = lineage._function(lineage.tree(entry["historical_source"]), name)
    arguments = function.args
    lineage.require(not arguments.posonlyargs and not arguments.vararg and not arguments.kwarg and
                    not arguments.defaults and all(value is None for value in arguments.kw_defaults),
                    "Historical workflow signature shape differs")
    parameters = [inspect.Parameter(item.arg, inspect.Parameter.POSITIONAL_OR_KEYWORD)
                  for item in arguments.args]
    parameters.extend(inspect.Parameter(item.arg, inspect.Parameter.KEYWORD_ONLY) for item in arguments.kwonlyargs)
    return inspect.Signature(parameters)


def project_binding(call, documents, actual, plain):
    """Preserve full actual evidence; remove one independently proved default."""
    lineage.require(call["api"] in lineage.FUNCTIONS, "Unreviewed workflow binding projection")
    raw_text = documents[call["input"]]["value"]
    raw = json.loads(raw_text)
    lineage.require(set(raw) == {"args", "kwargs"} and type(raw["args"]) is list and
                    type(raw["kwargs"]) is dict and "core" not in raw["kwargs"],
                    "Historical workflow call supplied a native route argument")
    bound = historical_signature(call["api"]).bind(*raw["args"], **raw["kwargs"])
    bound.apply_defaults()
    original = plain(dict(bound.arguments))
    exact = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=True)
    lineage.require(type(actual) is dict and "core" not in original and
                    exact(actual) == exact({**original, "core": None}),
                    "Actual workflow binding differs beyond the reviewed None default")
    return original, {
        "call_id": call["id"], "api": call["api"], "raw_input_document": call["input"],
        "raw_arguments_text": raw_text, "actual_bound_arguments": deepcopy(actual),
        "historical_bound_arguments": deepcopy(original),
        "projection": "exact_added_keyword_only_core_none_default_only",
    }


def check(document, frozen):
    from tools.check_realization_workflow_corpus import source_scope
    scope = source_scope(document["source_files"])
    lineage.require(frozen.LAST_SOURCE_SCOPE == {**scope,
        "import_guard": "passed_before_during_and_after_original_cohort"},
        "Original workflow route recapture lacks actual source and import-denial evidence")
    lineage.require("biocompiler.workflow_backend" in scope["denied_modules"],
                    "Original workflow capture could have entered a native route")
    bindings = []
    original_bind = frozen.bind_operation

    def bind(call, documents):
        actual = original_bind(call, documents)
        if call["api"] not in lineage.FUNCTIONS:
            return actual
        historical, evidence = project_binding(call, documents, actual, frozen.plain)
        bindings.append(evidence)
        return historical

    # This changes only the freezer's derived binding projection. It does not
    # replace a product function, its signature, source, execution or result.
    with patch.object(frozen, "bind_operation", bind):
        index = frozen.freeze(document, check=True)
    lineage.require(bindings and len({item["call_id"] for item in bindings}) == len(bindings),
                    "Missing or duplicate workflow signature evidence")
    return {
        "schema_version": "biocompiler.workflow_signature_lineage.v1",
        "status": "complete_original_workflow_recapture_equal", "native_execution": False,
        "witness_sha256": lineage.WITNESS_SHA256,
        "actual_capture_sha256": frozen.digest(frozen.canonical(document) + b"\n"),
        "actual_source_scope": scope, "baseline_inventory_fingerprint": index["inventory_fingerprint"],
        "raw_observations_results_assertions_callbacks_and_documents": "exact_immutable_baseline",
        "actual_bindings": bindings,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--captured", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    from tools import freeze_realization_workflow as frozen
    if args.captured:
        payload = args.captured.read_bytes()
        receipt = json.loads(args.captured.with_name("receipt.json").read_bytes())
        lineage.require(receipt["capture_sha256"] == frozen.digest(payload), "Actual capture receipt does not bind bytes")
        document = json.loads(payload)
        frozen.LAST_SOURCE_SCOPE = receipt.get("source_scope")
    else:
        with frozen.portable_sources():
            document = frozen.capture()
    evidence = check(document, frozen)
    output = args.output or frozen.OUT / "signature-lineage.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(frozen.canonical(evidence) + b"\n")
    print(json.dumps({"status": evidence["status"], "signature_projections": len(evidence["actual_bindings"]),
                      "baseline_inventory_fingerprint": evidence["baseline_inventory_fingerprint"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
