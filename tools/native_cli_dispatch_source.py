"""Restore the exact reviewed dispatch guard before older installed-path proofs.

This source-only witness changes no frozen capture, observation, or campaign
case. The complete current and historical helper bytes are independently pinned.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WITNESS = "tests/conformance/native-cli-dispatch-source-delta-v1.json"
WITNESS_SHA256 = "2b71aa0a5ea2585bce18f0411b5df893a240e54818ffb63fa93394c365a9630a"
BASE_REVISION = "573cfdf6504572cfc0fdd045bbd018c9e4d85320"
HISTORICAL = {
    "tools/check_native_synthetic_selection_cli.py": {
        "bytes": 41635, "sha256": "9822725b704fcab547a3afed967a4a31f27cce1ab8de4567ed8eed7f3546f230"},
    "tools/check_native_workflow_cli.py": {
        "bytes": 41628, "sha256": "e902e5faf7fcd8c76ff34825a065a5961c79cc3b5b2e427467090d5d5cef3890"},
}
SPAN_COUNTS = {"tools/check_native_synthetic_selection_cli.py": 10, "tools/check_native_workflow_cli.py": 11}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def restore(name, current, proof_bytes=None):
    require(name in HISTORICAL and type(current) is bytes, "Unknown native CLI dispatch source")
    if proof_bytes is None:
        path = ROOT / WITNESS
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 64 * 1024,
                "Missing or redirected native CLI dispatch witness")
        proof_bytes = path.read_bytes()
    require(type(proof_bytes) is bytes and hashlib.sha256(proof_bytes).hexdigest() == WITNESS_SHA256,
            "Unreviewed native CLI dispatch source witness")
    proof = json.loads(proof_bytes)
    require(set(proof) == {"schema", "base_revision", "policy_witness_sha256", "scope", "files"}
            and proof["schema"] == "biocompiler.native_cli_dispatch_source_delta.v1"
            and proof["base_revision"] == BASE_REVISION
            and proof["policy_witness_sha256"] == "680d26bc0107115e80ed4c6b8e9bae52698acf619e3ae4872e86d7f7ac3404e8"
            and set(proof["files"]) == set(HISTORICAL), "Native CLI dispatch witness shape differs")
    row = proof["files"][name]
    require(set(row) == {"historical", "current", "spans"} and row["historical"] == HISTORICAL[name]
            and pin(current) == row["current"], "Current native CLI guard differs from its exact reviewed source")
    spans = row["spans"]
    require(type(spans) is list and len(spans) == SPAN_COUNTS[name], "Native CLI dispatch span census differs")
    end = 0
    for span in spans:
        require(type(span) is dict and set(span) == {"offset", "before", "after"}
                and type(span["offset"]) is int and span["offset"] >= end
                and type(span["before"]) is str and type(span["after"]) is str
                and span["before"] != span["after"], "Native CLI dispatch span shape differs")
        end = span["offset"] + len(span["before"].encode())
    restored = current
    for index, span in reversed(list(enumerate(spans))):
        offset = span["offset"] + sum(len(prior["after"].encode()) - len(prior["before"].encode())
                                      for prior in spans[:index])
        before, after = span["before"].encode(), span["after"].encode()
        require(restored[offset:offset + len(after)] == after, "Native CLI dispatch source span bytes differ")
        restored = restored[:offset] + before + restored[offset + len(after):]
    require(pin(restored) == HISTORICAL[name], "Complete original native CLI helper source differs")
    def functions(raw):
        return {node.name: node for node in ast.parse(raw).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
    old, new = functions(restored), functions(current)
    require(set(new) - set(old) == {"dispatch_sources"} and set(old) <= set(new)
            and {key for key in old if ast.dump(old[key]) != ast.dump(new[key])}
                == {"allowed_cli_call", "product_sources", "validate_audit"},
            "Native CLI dispatch changed an original case, observation, transport, or campaign function")
    return restored
