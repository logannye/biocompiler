"""Review only derived producer binding additions; preserve complete raw capture.

No product callable, signature, assertion, callback, input, result or exception is
replaced. Exact old signatures are independently reconstructed from retained AST,
and the current binding must differ only by the absent core keyword's None value.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
from copy import deepcopy
import inspect
import json
from unittest.mock import patch

from tools import synthetic_producer_source_lineage as lineage


def historical_signature(name):
    lineage.require(name in lineage.FUNCTIONS, "Unreviewed producer signature")
    path = lineage.FUNCTIONS[name]
    entry = lineage.load_witness()[path]
    lineage.verify_extension(entry, (lineage.ROOT / path).read_bytes(), entry["historical_sha256"])
    arguments = lineage.function(lineage.tree(entry["historical_source"]), name).args
    lineage.require(not arguments.posonlyargs and not arguments.vararg and not arguments.kwarg and not arguments.defaults,
                    "Historical producer signature shape differs")
    parameters = [inspect.Parameter(item.arg, inspect.Parameter.POSITIONAL_OR_KEYWORD) for item in arguments.args]
    for item, default in zip(arguments.kwonlyargs, arguments.kw_defaults):
        lineage.require(isinstance(default, ast.Constant) and default.value is None, "Historical producer default differs")
        parameters.append(inspect.Parameter(item.arg, inspect.Parameter.KEYWORD_ONLY, default=None))
    return inspect.Signature(parameters)


def project_binding(call, documents, actual, plain):
    lineage.require(call["api"] in lineage.FUNCTIONS, "Unreviewed producer binding projection")
    raw_text = documents[call["input"]]["value"]
    raw = json.loads(raw_text)
    lineage.require(set(raw) == {"args", "kwargs"} and type(raw["args"]) is list and type(raw["kwargs"]) is dict
                    and "core" not in raw["kwargs"], "Historical producer call supplied a native route argument")
    bound = historical_signature(call["api"]).bind(*raw["args"], **raw["kwargs"])
    bound.apply_defaults()
    original = plain(dict(bound.arguments))
    exact = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=True)
    lineage.require(type(actual) is dict and "core" not in original and exact(actual) == exact({**original, "core": None}),
                    "Actual producer binding differs beyond the reviewed None default")
    return original, {"call_id": call["id"], "api": call["api"], "raw_input_document": call["input"],
        "raw_arguments_text": raw_text, "actual_bound_arguments": deepcopy(actual), "historical_bound_arguments": deepcopy(original),
        "projection": "exact_added_keyword_only_core_none_default_only"}


@contextmanager
def producer_bindings(previous):
    bindings = []
    original_input = previous._foundation_input
    def observation(call, documents):
        operation, actual, stage = original_input(call, documents)
        if call["api"] not in lineage.FUNCTIONS:
            return operation, actual, stage
        original, evidence = project_binding(call, documents, actual, previous.foundation.plain)
        bindings.append(evidence)
        return operation, original, stage
    # The original producer freezer subsequently applies its exact original
    # selection-injection recipe around this independently reviewed binding.
    with patch.object(previous, "_foundation_input", observation):
        yield bindings
