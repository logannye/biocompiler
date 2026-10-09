"""Check one reviewed source unit/scope slice without importing policy code.

Closed identifiers, Python AST structure and exact source pins detect drift.
They do not infer semantic equivalence, execute the native checker, or establish
that the wider source/admission/material census is complete. OCaml mappings are
reviewed source regions, never a home-made semantic parser. There is deliberately
no command to regenerate or approve the reviewed pins.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

try:
    from tools.check_policy_semantic_coverage import syntax
except ModuleNotFoundError:  # Direct invocation from tools/.
    from check_policy_semantic_coverage import syntax

ROOT = Path(__file__).resolve().parents[1]
LEDGER = "protocol/policy-source-context-coverage-v0.1.json"
SCHEMA = "biocompiler.policy_source_context_coverage.v0.1"
CLAIM = "reviewed_source_unit_scope_slice_only"
AST_HELPER = "tools/check_policy_semantic_coverage.py"
MAX_BYTES = 4 * 1024 * 1024
MAX_DEPTH = 48
MAX_NODES = 100000
MAX_STRING = 16384
MAX_LIST = 4096
# Independently reviewed closed identities and pins, populated in this change.
RULE_IDS = ('source.type.quantity_requires_unit',
 'source.type.nonquantity_forbids_unit',
 'source.type.entity_requires_nominal_kind',
 'source.type.nonentity_forbids_nominal_kind',
 'source.unit.scale_positive',
 'source.unit.dimension_nonblank',
 'source.unit.quantity_kind_nonblank',
 'source.compatibility.same_kind',
 'source.compatibility.same_entity_kind',
 'source.compatibility.nonquantity_units_absent',
 'source.compatibility.quantity_units_present',
 'source.compatibility.same_dimension',
 'source.compatibility.same_quantity_kind',
 'source.compatibility.same_nominal_reference',
 'source.integer_bound.count_dimension',
 'source.integer_bound.count_quantity_kind',
 'source.integer_bound.no_nominal_reference',
 'source.integer_bound.scale_one',
 'source.quantity.exact_scaled_value',
 'source.duration.required',
 'source.duration.time_dimension',
 'source.duration.duration_quantity_kind',
 'source.duration.strictly_positive',
 'source.duration.nonnegative',
 'source.scope.program_has_no_subject',
 'source.scope.other_kinds_require_subject',
 'source.scope.subject_kind',
 'source.scope.declaration_excludes_bound_subject',
 'source.scope.nominal_aggregate_kind',
 'source.reference.exists',
 'source.reference.nominal_kind',
 'source.reference.allowed_kind',
 'source.reference.lexical_formal_precedence',
 'source.scope.executor_derivation',
 'source.access.state_executor',
 'source.access.state_channel_participant',
 'source.access.observation_cell_access',
 'source.access.observation_executor',
 'source.access.effect_feedback_executor',
 'source.access.message_phase_executor')
CONTEXT_IDS = ('source.context.compatibility.reference_value',
 'source.context.compatibility.literal',
 'source.context.compatibility.comparison',
 'source.context.compatibility.add_subtract',
 'source.context.compatibility.call_argument',
 'source.context.compatibility.call_result',
 'source.context.compatibility.assignment',
 'source.context.compatibility.observation_result',
 'source.context.compatibility.state_initial',
 'source.context.compatibility.effect_argument',
 'source.context.compatibility.message_payload',
 'source.context.compatibility.parameter_value',
 'source.context.compatibility.parameter_lower',
 'source.context.compatibility.parameter_upper',
 'source.context.compatibility.interval',
 'source.context.duration.expr.holds',
 'source.context.duration.expr.recently',
 'source.context.duration.expr.followed_by',
 'source.context.duration.expr.within',
 'source.context.duration.expr.integrate',
 'source.context.duration.clock_resolution',
 'source.context.duration.observation_freshness',
 'source.context.duration.state_duration',
 'source.context.duration.lifecycle_timeout',
 'source.context.duration.channel_latency',
 'source.context.duration.requirement_deadline',
 'source.context.duration.requirement_horizon',
 'source.context.duration.assurance_horizon',
 'source.context.duration.payload_persistence',
 'source.context.duration.effector_persistence',
 'source.context.scope.StateStore',
 'source.context.scope.Machine',
 'source.context.scope.Channel',
 'source.context.scope.Requirement',
 'source.context.access.rule_on',
 'source.context.access.rule_guard',
 'source.context.access.transition_on',
 'source.context.access.transition_guard',
 'source.context.access.assignment_value',
 'source.context.access.effect_argument',
 'source.context.access.state_reset',
 'source.context.access.message_payload',
 'source.context.access.message_state_correlation')
SOURCE_PINS = {'core/lib/checker/policy_admission.ml': 'b248d924d5b8768b8dcdff44dc503b7b220d2da58e7fe03802ac24b96bf29c87',
 'core/lib/checker/policy_check.ml': 'd8fc6d8a30ede74b89d90aca49d7ec77756761f317205e9bf96a906760ccd054',
 'core/lib/checker/policy_generation_meter.ml': '13c4647bc0efcb50f239af693e8fa3281fdbca4115ce4e5a84bcd4e9a4a1b965',
 'core/lib/checker/policy_generation_meter.mli': 'f1bb20416d692f4d0aa72b92028f75f6ea5ca532ae90e1d7593b424e703bf4ba',
 'core/lib/checker/policy_implementation_binding_check.ml': '3ef7df801f1da057fe3e1d2596ba6e8368a7162f82212afb20c4e61a962a446a',
 'core/lib/domain/policy_document.ml': 'db2860b602d63df29d1a8240417f8632c37693b797f9561e00395bd1fd2f95dc',
 'core/lib/domain/policy_material_context.ml': '00aab6a0635a99cb59fd171b120483c93035a6004cb168d7a10e2950e0ccf013',
 'core/lib/domain/policy_operating_domain.ml': 'bbdc0925c24c95852f356a513c1707f330da3b936227a24e0234730a9deb5384',
 'core/lib/domain/policy_operational.ml': 'bd5d03f8acefed68ab0a8059041774479426928266351b325535a124e3e23d34',
 'core/lib/domain/policy_schema.ml': '8057ea511a25835f4e51c720ce815602f69839d0a664fc880c2f8f5bee918e78',
 'core/lib/realization_checker/policy_material_context_check.ml': '24a2fe4aa3d58bb133ebe0b90fb53aae6b0fc9da30a5c45d6c3577994037a8d1',
 'src/biocompiler/policy/model.py': '7197696399733e610b7a5c458aebf0ddc4b0df997f190cb53fa1659c419b6038',
 'src/biocompiler/policy/serialization.py': 'd0e2feb4e8dd3fe65a10793d20c06144ad6fec396d99e6107f3485682ee570bf',
 'src/biocompiler/policy/validation.py': '00be9fc170771f06ee7fae34c17ec9a47fcd1c1741efb34fd64044a114d7c5b8',
 'tools/check_policy_semantic_coverage.py': '5ba275b0d8aac9f70aa3b8d1f28c6a8cd1d7fba62afdb7e988f5ef1957f0ddef'}
AST_PINS = {'src/biocompiler/policy/model.py': 'e2cfabc143415a86d1e3e2c42ba744892b4cad5d22ef28e7d085664159f2daf5',
 'src/biocompiler/policy/serialization.py': '3db49f534fa75ed53db36d81a0ead63fa89705226ca7108cf83bdc2fd3b83fc4',
 'src/biocompiler/policy/validation.py': '0d4d303ca4ba1991af7c523f0b09ad1117d1960b8a69c045afca86276cc65f6b',
 'tools/check_policy_semantic_coverage.py': 'dc854464d73f62aefee48a25849b9067082a619b06f2a8a676f9d31c016a5953'}
INPUT_PINS = {'core/test/data/policy_documents_v01.json': 'c4c7f3251c882ed739eb3b733bb0eea0cd2965470e02e6293196e114b0a3aded',
 'core/test/data/policy_operational_v01.json': 'bd9dfbb65c456b75fa401049341e85a6de882e8f130b4c76dfdadd9b6dd08968',
 'core/test/data/policy_realization_source_v01.json': 'fa4008fb9196ed1a318a2b293f452d19227b9562c5d1dece16183e2110ceec51'}
REVIEWED_DECLARATIONS_SHA256 = '4ddf3f0558a8e202891e175a576736f22483ed3519f7b9d4342bc4b8ece2dbde'
SYNTAX_LEDGER = "protocol/policy-semantic-coverage-v0.1.json"
FAMILY_LEDGER = "protocol/policy-material-rule-coverage-v0.1.json"


class CoverageError(ValueError):
    """The bounded index is malformed, stale or claims more than its review."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CoverageError(message)


def closed(value: Any, keys: set[str], label: str) -> None:
    require(type(value) is dict and set(value) == keys, label + ": missing or extra fields")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def bounded(value: Any) -> None:
    queue = [(value, 0)]
    seen = 0
    while queue:
        item, depth = queue.pop()
        seen += 1
        require(depth <= MAX_DEPTH and seen <= MAX_NODES, "JSON depth/node bound exceeded")
        if type(item) is dict:
            require(len(item) <= MAX_LIST, "JSON object bound exceeded")
            for key, child in item.items():
                require(type(key) is str and len(key) <= MAX_STRING, "JSON key bound exceeded")
                queue.append((child, depth + 1))
        elif type(item) is list:
            require(len(item) <= MAX_LIST, "JSON list bound exceeded")
            queue.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            require(len(item) <= MAX_STRING, "JSON string bound exceeded")
        else:
            require(item is None or type(item) in (bool, int), "Only closed JSON scalar types permitted")
            if type(item) is int:
                require(item.bit_length() <= 256, "JSON integer bound exceeded")


def decode(raw: bytes) -> Any:
    require(type(raw) is bytes and len(raw) <= MAX_BYTES, "JSON byte bound exceeded")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            require(key not in result, "Duplicate JSON key: " + key)
            result[key] = item
        return result

    try:
        value = json.loads(raw, object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(CoverageError("Nonfinite JSON")))
        bounded(value)
        return value
    except (ValueError, UnicodeError, RecursionError) as error:
        raise CoverageError("Invalid bounded JSON: " + str(error)) from error


def read(root: Path, name: str) -> bytes:
    require(type(name) is str and bool(name) and "\\" not in name, "Invalid source path")
    relative = Path(name)
    require(not relative.is_absolute() and relative.as_posix() == name
            and all(part not in (".", "..") for part in relative.parts), "Unsafe source path")
    path = root / relative
    require(path.resolve().is_relative_to(root.resolve()) and path.is_file(), "Missing or escaping source path")
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    require(len(raw) <= MAX_BYTES, "Source byte bound exceeded")
    return raw


def parse(raw: bytes, name: str) -> ast.Module:
    try:
        return ast.parse(raw.decode("utf-8"), filename=name)
    except (SyntaxError, UnicodeError, RecursionError) as error:
        raise CoverageError("Cannot parse inert Python source: " + name) from error


def ast_closure(raw: bytes, name: str) -> dict[str, Any]:
    """Inventory syntax, including every call; this is not a semantic call graph."""
    tree = parse(raw, name)
    symbols: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []

    def walk(node: ast.AST, owner: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            owner = owner + "." + node.name if owner else node.name
            symbols.append({"id": owner, "kind": type(node).__name__, "first_line": node.lineno,
                            "last_line": node.end_lineno, "sha256": digest(syntax(node).encode())})
        if isinstance(node, ast.Call):
            function = node.func
            parts = []
            while isinstance(function, ast.Attribute):
                parts.append(function.attr)
                function = function.value
            if isinstance(function, ast.Name):
                parts.append(function.id)
            calls.append({"id": f"L{node.lineno}C{node.col_offset}", "owner": owner,
                          "function": ".".join(reversed(parts)) if isinstance(function, ast.Name) else "<expression>",
                          "first_line": node.lineno, "last_line": node.end_lineno,
                          "sha256": digest(syntax(node).encode())})
        for child in ast.iter_child_nodes(node):
            walk(child, owner)

    walk(tree, "")
    return {"module_sha256": digest(syntax(tree).encode()), "symbols": symbols,
            "calls": sorted(calls, key=lambda row: (row["first_line"], row["id"]))}


def inert_helper(raw: bytes) -> None:
    """The shared AST encoder's entire import closure is explicit stdlib only."""
    allowed = {"__future__", "argparse", "ast", "collections", "hashlib", "json", "pathlib", "sys", "typing"}
    for node in ast.walk(parse(raw, AST_HELPER)):
        if isinstance(node, ast.Import):
            require(all(item.name in allowed for item in node.names), "AST helper non-stdlib dependency")
        if isinstance(node, ast.ImportFrom):
            require(node.level == 0 and node.module in allowed, "AST helper non-stdlib dependency")


def anchor(root: Path, path: str, first: int, last: int,
           structures: dict[str, dict[str, Any]]) -> dict[str, Any]:
    require(type(first) is int and type(last) is int and 1 <= first <= last, "Invalid source region bounds")
    lines = read(root, path).splitlines(keepends=True)
    require(last <= len(lines), "Source region exceeds file")
    structure = structures.get(path, {})
    symbols = [row["id"] for row in structure.get("symbols", [])
               if row["first_line"] <= first and last <= row["last_line"]]
    calls = [row["id"] for row in structure.get("calls", [])
             if row["first_line"] <= last and first <= row["last_line"]]
    return {"path": path, "first_line": first, "last_line": last,
            "region_sha256": digest(b"".join(lines[first - 1:last])),
            "python_symbols": symbols, "python_calls": calls}


def declarations(ledger: dict[str, Any]) -> dict[str, Any]:
    """Reviewed meaning/linkage is independent of supplied file hash claims."""
    result = {key: value for key, value in ledger.items() if key not in {"sources", "counterexample_inputs"}}
    result["reviewed_source_dispositions"] = [
        {"path": row["path"], "disposition": row["disposition"]} for row in ledger["sources"]
    ]
    return result


def check(root: Path = ROOT, ledger: Any | None = None) -> dict[str, Any]:
    if ledger is None:
        ledger = decode(read(root, LEDGER))
    bounded(ledger)
    closed(ledger, {"schema_version", "claim_scope", "reviewed_source", "counts", "limitations", "path_conventions",
                    "sources", "counterexample_inputs", "syntax_ledger", "family_ledger", "rules", "contexts",
                    "stage_differences", "remainder"}, "ledger")
    require(ledger["schema_version"] == SCHEMA and ledger["claim_scope"] == CLAIM, "Wrong source-slice claim/schema")
    require(ledger["counts"] == {"rules": 40, "contexts": 43, "whole_source_census": "open",
                                 "whole_stack_census": "open", "witness_sufficiency": "not_assessed"}, "Changed bounded census claim")
    require(type(ledger["rules"]) is list and all(type(row) is dict for row in ledger["rules"])
            and tuple(row.get("id") for row in ledger["rules"]) == RULE_IDS, "Changed closed rule IDs/order")
    require(type(ledger["contexts"]) is list and all(type(row) is dict for row in ledger["contexts"])
            and tuple(row.get("id") for row in ledger["contexts"]) == CONTEXT_IDS, "Changed closed context IDs/order")
    require(ledger["syntax_ledger"] == SYNTAX_LEDGER and ledger["family_ledger"] == FAMILY_LEDGER, "Changed complementary ledger path")
    syntax_ledger = decode(read(root, SYNTAX_LEDGER))
    family_ledger = decode(read(root, FAMILY_LEDGER))
    require(type(syntax_ledger) is dict and syntax_ledger.get("schema_version") == "biocompiler.policy_semantic_coverage.v0.1", "Wrong syntax ledger")
    require(type(family_ledger) is dict and family_ledger.get("schema_version") == "biocompiler.policy_material_rule_coverage.v0.1", "Wrong family ledger")
    entries, families = syntax_ledger.get("entries"), family_ledger.get("rules")
    require(type(entries) is list and len(entries) == 612 and all(type(row) is dict and type(row.get("id")) is str for row in entries), "Changed 612 syntax census")
    require(type(families) is list and len(families) == 62 and all(type(row) is dict and type(row.get("id")) is str for row in families), "Changed 62 family census")
    syntax_ids = {row["id"] for row in entries}
    family_ids = {row["id"] for row in families}
    require(len(syntax_ids) == 612 and len(family_ids) == 62, "Duplicate complementary identity")
    structures: dict[str, dict[str, Any]] = {}
    sources = ledger["sources"]
    require(type(sources) is list and all(type(row) is dict for row in sources)
            and [row.get("path") for row in sources] == list(SOURCE_PINS), "Changed closed source paths/order")
    for row in sources:
        closed(row, {"path", "sha256", "disposition", "ast"}, "source")
        name = row["path"]
        raw = read(root, name)
        require(digest(raw) == row["sha256"], "Stale source hash: " + name)
        if name.endswith(".py"):
            structure = ast_closure(raw, name)
            require(structure == row["ast"], "Changed Python AST/caller closure: " + name)
            require(digest(canonical(structure)) == AST_PINS[name], "Unreviewed Python AST/caller closure: " + name)
            structures[name] = structure
        else:
            require(row["ast"] is None, "OCaml source must not claim inferred AST semantics")
        require(digest(raw) == SOURCE_PINS[name], "Unreviewed complete source pin: " + name)
        require(row["disposition"] in {"source_rule_owner", "source_codec_dependency", "deferred_boundary", "inert_ast_dependency",
                                       "shared_metering_dependency"}, "Unknown source disposition")
    inert_helper(read(root, AST_HELPER))
    for group, is_context in ((ledger["rules"], False), (ledger["contexts"], True)):
        for row in group:
            keys = {"id", "owners", "syntax_ids", "family_ids", "evidence"}
            keys |= {"predicate_ids", "selector", "diagnostic", "path_template", "parameters", "notes"} if is_context else {"kind", "predicate", "diagnostics", "path_template", "notes"}
            closed(row, keys, "context" if is_context else "rule")
            require(row["evidence"] == "source_review_only_witness_sufficiency_pending", "Invented semantic/execution evidence")
            for key, available in (("syntax_ids", syntax_ids), ("family_ids", family_ids)):
                values = row[key]
                require(type(values) is list and values and all(type(value) is str for value in values)
                        and len(values) == len(set(values)) and set(values) <= available, "Dangling or duplicate " + key)
            if is_context:
                values = row["predicate_ids"]
                require(type(values) is list and values and all(type(value) is str for value in values)
                        and len(values) == len(set(values)) and set(values) <= set(RULE_IDS), "Dangling or duplicate predicate IDs")
                require(type(row["parameters"]) is dict, "Context parameters must be explicit")
            owners = row["owners"]
            require(type(owners) is list and owners, "Missing source owners")
            for owner in owners:
                closed(owner, {"path", "first_line", "last_line", "region_sha256", "python_symbols", "python_calls"}, "owner")
                require(type(owner["path"]) is str and owner["path"] in SOURCE_PINS, "Unclassified source owner")
                require(owner == anchor(root, owner["path"], owner["first_line"], owner["last_line"], structures), "Changed source anchor/AST linkage")
    inputs = ledger["counterexample_inputs"]
    require(type(inputs) is list and all(type(row) is dict for row in inputs)
            and [row.get("path") for row in inputs] == list(INPUT_PINS), "Changed counterexample input census")
    for row in inputs:
        closed(row, {"path", "sha256"}, "counterexample input")
        require(row["sha256"] == INPUT_PINS[row["path"]] == digest(read(root, row["path"])), "Changed original counterexample input")
    require(digest(canonical(declarations(ledger))) == REVIEWED_DECLARATIONS_SHA256,
            "Unreviewed source predicates/contexts/stage differences/linkage")
    return {"schema_version": "biocompiler.policy_source_context_coverage_receipt.v0.1",
            "status": "source_slice_current", "rules": len(RULE_IDS), "contexts": len(CONTEXT_IDS),
            "sources": len(SOURCE_PINS), "counterexample_inputs": len(INPUT_PINS),
            "syntax_rows": len(syntax_ids), "families": len(family_ids),
            "whole_source_census": "open", "whole_stack_census": "open",
            "witness_sufficiency": "not_assessed", "semantic_proof": "not_established",
            "product_imports": "not_performed", "native_execution": "not_performed"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.root), sort_keys=True))
        return 0
    except (CoverageError, OSError) as error:
        print("Source-context coverage rejected: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
