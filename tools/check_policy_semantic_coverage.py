"""Check the reviewed rich-policy syntax/coverage ledger without importing policy.

This is a static inventory gate, not semantic validation or a test receipt. It
discovers records, fields, literal choices (including method event phases),
operators, type-alias alternatives and model constants using only Python ASTs.
The committed ledger supplies every disposition; discovery never invents one.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = "src/biocompiler/policy"
MODEL = SOURCE_ROOT + "/model.py"
LEDGER = "protocol/policy-semantic-coverage-v0.1.json"
SCHEMA = "biocompiler.policy_semantic_coverage.v0.1"
STAGES = (
    "authorable", "python_structure", "native_source", "operational",
    "implementation", "material", "export",
)
STATUSES = {
    "supported", "contextual", "preserved", "unsupported", "unassessed",
    "not_applicable",
}
KINDS = {"owner", "positive_control", "rejection_control", "contract"}


class CoverageError(ValueError):
    """The ledger is incomplete, stale, malformed or overclaims its evidence."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise CoverageError(message)


def closed(value: Any, keys: set[str], label: str) -> None:
    require(type(value) is dict and set(value) == keys, f"{label}: unexpected or missing keys")


# These fields were added in Python 3.12/3.13. Their absent and explicit empty
# defaults describe the same nongeneric source. Nonempty values remain hashed.
# Other fields, including future additions, are never silently discarded.
AST_ADDED_DEFAULTS: dict[str, dict[str, Any]] = {
    "FunctionDef": {"type_params": []},
    "AsyncFunctionDef": {"type_params": []},
    "ClassDef": {"type_params": []},
    "TypeVar": {"default_value": None},
    "ParamSpec": {"default_value": None},
    "TypeVarTuple": {"default_value": None},
}


def syntax(node: ast.AST | None) -> str | None:
    """Encode actual syntax fields, independent of ast.dump's display defaults.

    Python 3.14 omits empty collections from ast.dump by default. Keep them here,
    together with None, scalar types, operand order and all nonlocation fields.
    Only the version-added defaults above are filled when absent.
    """
    def shape(value: Any) -> Any:
        if isinstance(value, ast.AST):
            fields = dict(ast.iter_fields(value))
            for key, default in AST_ADDED_DEFAULTS.get(type(value).__name__, {}).items():
                fields[key] = getattr(value, key, default)
            return [type(value).__name__, [[key, shape(fields[key])] for key in sorted(fields)]]
        if type(value) is list:
            return ["list", [shape(item) for item in value]]
        if value is None:
            return ["none"]
        if type(value) in (str, bool):
            return [type(value).__name__, value]
        if type(value) is int:
            return ["int", str(value)]
        if type(value) is float:
            return ["float", value.hex()]
        if type(value) is complex:
            return ["complex", value.real.hex(), value.imag.hex()]
        if type(value) is bytes:
            return ["bytes", value.hex()]
        if value is Ellipsis:
            return ["ellipsis"]
        raise CoverageError(f"Unsupported AST field value: {type(value).__name__}")

    return None if node is None else json.dumps(shape(node), ensure_ascii=True,
                                               separators=(",", ":"), allow_nan=False)


def terminal(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def source_path(root: Path, relative: str) -> Path:
    require(type(relative) is str and bool(relative), "Reference path must be nonempty")
    path = root / relative
    require(not Path(relative).is_absolute() and ".." not in Path(relative).parts,
            f"Reference path must be repository-relative: {relative}")
    require(path.resolve().is_relative_to(root.resolve()), f"Reference escapes repository: {relative}")
    require(path.is_file(), f"Missing source/evidence file: {relative}")
    return path


def parse_file(root: Path, relative: str) -> ast.Module:
    return ast.parse(source_path(root, relative).read_text(encoding="utf-8"), filename=relative)


def symbols(tree: ast.AST) -> dict[str, ast.AST]:
    result: dict[str, ast.AST] = {}

    def visit(body: list[ast.stmt], prefix: str = "") -> None:
        for node in body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + node.name
                result[name] = node
                if isinstance(node, ast.ClassDef):
                    visit(node.body, name + ".")
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                result[prefix + node.target.id] = node
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        result[prefix + target.id] = node

    if isinstance(tree, ast.Module):
        visit(tree.body)
    return result


def alternatives(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return alternatives(node.left) + alternatives(node.right)
    return [node]


def discover(root: Path) -> list[dict[str, Any]]:
    """Return syntax distinctions only. No policy import, execution or support inference."""
    package = root / SOURCE_ROOT
    require(package.is_dir(), f"Missing policy source package: {package}")
    trees = {path.relative_to(root).as_posix(): ast.parse(path.read_text(encoding="utf-8"),
             filename=path.relative_to(root).as_posix()) for path in sorted(package.rglob("*.py"))}
    require(MODEL in trees, "Missing closed policy model")
    aliases: dict[str, dict[str, str]] = {}
    for path, tree in trees.items():
        local: dict[str, str] = {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                for item in node.names:
                    if item.asname:
                        local[item.asname] = item.name
            elif isinstance(node, ast.Assign) and isinstance(node.value, (ast.Name, ast.Attribute)):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        local[target.id] = terminal(node.value)
        aliases[path] = local

    def resolved(path: str, node: ast.AST) -> str:
        name = terminal(node)
        seen: set[str] = set()
        while name in aliases[path] and name not in seen:
            seen.add(name)
            name = aliases[path][name]
        return name

    classes = [(path, name, node) for path, tree in trees.items()
               for name, node in symbols(tree).items() if isinstance(node, ast.ClassDef)]
    record_names = {"Record"}
    changed = True
    while changed:
        changed = False
        for path, name, node in classes:
            if any(resolved(path, base) in record_names for base in node.bases):
                require("." not in name, f"Nested policy record needs explicit inventory support: {name}")
                if name not in record_names:
                    record_names.add(name)
                    changed = True
    found: dict[str, dict[str, Any]] = {}

    def add(identity: str, kind: str, path: str, symbol: str, shape: Any) -> None:
        require(identity not in found, f"Duplicate source distinction: {identity}")
        encoded = json.dumps(shape, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        found[identity] = {"id": identity, "kind": kind, "source": {"path": path, "symbol": symbol},
                           "syntax_sha256": hashlib.sha256(encoded.encode()).hexdigest()}

    def literal_choices(annotation: ast.AST, name: str, path: str, owner: str) -> None:
        for node in ast.walk(annotation):
            if isinstance(node, ast.Subscript) and resolved(path, node.value) == "Literal":
                choices = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
                for choice in choices:
                    require(isinstance(choice, ast.Constant) and type(choice.value) in (str, int, bool),
                            f"Nonliteral enum needs explicit inventory support: {name}")
                    value = choice.value
                    kind = "operator" if name == "Expr.op" else "literal"
                    suffix = json.dumps(value, ensure_ascii=True, separators=(",", ":"))
                    add(f"{kind}:{name}={suffix}", kind, path, owner, value)

    for path, name, node in classes:
        if name in record_names and (name != "Record" or path == MODEL):
            add("record:" + name, "record", path, name,
                {"bases": [syntax(base) for base in node.bases],
                 "decorators": [syntax(item) for item in node.decorator_list]})
            for child in node.body:
                if isinstance(child, ast.AnnAssign):
                    require(isinstance(child.target, ast.Name), f"Unsupported record field target: {name}")
                    field = name + "." + child.target.id
                    add("field:" + field, "field", path, field,
                        {"annotation": syntax(child.annotation), "default": syntax(child.value)})
                    literal_choices(child.annotation, field, path, field)
                elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = child.args.posonlyargs + child.args.args + child.args.kwonlyargs
                    args += [item for item in (child.args.vararg, child.args.kwarg) if item is not None]
                    for arg in args:
                        if arg.annotation is not None and any(isinstance(item, ast.Subscript)
                            and resolved(path, item.value) == "Literal" for item in ast.walk(arg.annotation)):
                            name_arg = f"{name}.{child.name}.{arg.arg}"
                            add("argument:" + name_arg, "argument", path, f"{name}.{child.name}", syntax(arg.annotation))
                            literal_choices(arg.annotation, name_arg, path, f"{name}.{child.name}")
        elif any(resolved(path, base) in ("Enum", "StrEnum", "IntEnum", "Flag", "IntFlag") for base in node.bases):
            add("enum:" + name, "enum", path, name, [syntax(base) for base in node.bases])
            for child in node.body:
                if isinstance(child, ast.Assign):
                    for target in child.targets:
                        require(isinstance(target, ast.Name), f"Unsupported enum target: {name}")
                        add(f"enum_member:{name}.{target.id}", "enum_member", path,
                            f"{name}.{target.id}", syntax(child.value))
                elif isinstance(child, ast.AnnAssign) and child.value is not None:
                    require(isinstance(child.target, ast.Name), f"Unsupported enum target: {name}")
                    add(f"enum_member:{name}.{child.target.id}", "enum_member", path,
                        f"{name}.{child.target.id}", {"annotation": syntax(child.annotation), "value": syntax(child.value)})

    for node in trees[MODEL].body:
        if isinstance(node, ast.AnnAssign) and terminal(node.annotation) == "TypeAlias":
            require(isinstance(node.target, ast.Name) and node.value is not None, "Unsupported source alias")
            name = node.target.id
            add("alias:" + name, "alias", MODEL, name, syntax(node.value))
            for member in alternatives(node.value):
                require(isinstance(member, ast.Name), f"Unsupported alias member: {name}")
                add(f"alternative:{name}.{member.id}", "alternative", MODEL, name, syntax(member))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    add("constant:" + target.id, "constant", MODEL, target.id, syntax(node.value))
    return [found[key] for key in sorted(found)]


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_ledger(path: Path) -> dict[str, Any]:
    def invalid_number(value: str) -> None:
        raise CoverageError(f"Ledger requires exact JSON values, not {value}")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object,
                      parse_float=invalid_number, parse_constant=invalid_number)


def validate(root: Path, ledger: dict[str, Any]) -> dict[str, Any]:
    closed(ledger, {"schema_version", "source_profile", "operational_profile", "source_roots", "stages",
                    "claim_scope", "references", "dispositions", "entries", "known_gaps"}, "ledger")
    require(ledger["schema_version"] == SCHEMA, "Wrong coverage schema")
    require(ledger["source_profile"] == "biocompiler.policy.v0.1", "Wrong source profile")
    require(ledger["operational_profile"] == "biocompiler.policy_operational.v0.1", "Wrong operational profile")
    require(ledger["source_roots"] == [SOURCE_ROOT], "Source inventory scope cannot be narrowed")
    require(ledger["stages"] == list(STAGES), "Coverage must retain every stage")
    require(type(ledger["claim_scope"]) is str and bool(ledger["claim_scope"]), "Missing scope statement")
    references = ledger["references"]
    require(type(references) is dict and bool(references), "Missing reference inventory")
    for identity, ref in references.items():
        closed(ref, {"path", "kind", "anchor", "scope"}, f"reference {identity}")
        require(ref["kind"] in KINDS and type(ref["scope"]) is str and bool(ref["scope"]),
                f"Invalid reference kind/scope: {identity}")
        path = source_path(root, ref["path"])
        anchor = ref["anchor"]
        require(type(anchor) is dict and len(anchor) == 1, f"Missing reference anchor: {identity}")
        if set(anchor) == {"symbol"}:
            require(path.suffix == ".py" and anchor["symbol"] in symbols(parse_file(root, ref["path"])),
                    f"Missing Python evidence symbol: {identity}")
        else:
            require(set(anchor) == {"text"} and type(anchor["text"]) is str and bool(anchor["text"]),
                    f"Invalid evidence anchor: {identity}")
            require(anchor["text"] in path.read_text(encoding="utf-8"), f"Missing evidence marker: {identity}")

    dispositions = ledger["dispositions"]
    require(type(dispositions) is dict and bool(dispositions), "Missing explicit dispositions")
    for identity, disposition in dispositions.items():
        closed(disposition, {"stages", "condition", "owners", "witnesses", "follow_up"}, f"disposition {identity}")
        closed(disposition["stages"], set(STAGES), f"stage map {identity}")
        require(all(status in STATUSES for status in disposition["stages"].values()), f"Unknown stage status: {identity}")
        require(type(disposition["condition"]) is str and bool(disposition["condition"]), f"Missing contextual boundary: {identity}")
        closed(disposition["owners"], {"source", "native"}, f"owners {identity}")
        for owner in disposition["owners"].values():
            require(type(owner) is list and bool(owner), f"Missing owner: {identity}")
            require(all(ref in references and references[ref]["kind"] == "owner" for ref in owner), f"Invalid owner: {identity}")
        witnesses = disposition["witnesses"]
        closed(witnesses, {"positive", "rejection", "dedicated", "scope"}, f"witnesses {identity}")
        require(type(witnesses["dedicated"]) is bool and type(witnesses["scope"]) is str and bool(witnesses["scope"]),
                f"Missing witness limitations: {identity}")
        for kind in ("positive", "rejection"):
            refs = witnesses[kind]
            require(type(refs) is list and bool(refs), f"Missing {kind} witness reference: {identity}")
            require(all(ref in references and references[ref]["kind"] == kind + "_control" for ref in refs),
                    f"Wrong {kind} witness kind: {identity}")
        require(type(disposition["follow_up"]) is list and bool(disposition["follow_up"])
                and all(type(task) is str and task.startswith("SM-") for task in disposition["follow_up"]),
                f"Missing stable follow-up tasks: {identity}")

    discovered = {entry["id"]: entry for entry in discover(root)}
    require(type(ledger["entries"]) is list, "Entries must be an ordered explicit inventory")
    entries: dict[str, Any] = {}
    for entry in ledger["entries"]:
        closed(entry, {"id", "kind", "source", "syntax_sha256", "disposition"}, "entry")
        require(type(entry["id"]) is str and entry["id"] not in entries, "Duplicate or invalid coverage ID")
        require(entry["disposition"] in dispositions, f"Unclassified distinction: {entry['id']}")
        entries[entry["id"]] = entry
    missing = sorted(set(discovered) - set(entries))
    obsolete = sorted(set(entries) - set(discovered))
    require(not missing and not obsolete, f"Coverage inventory differs: missing={missing}; obsolete={obsolete}")
    for identity, expected in discovered.items():
        actual = {key: value for key, value in entries[identity].items() if key != "disposition"}
        require(actual == expected, f"Source distinction changed; review its disposition: {identity}")
    require(list(entries) == sorted(entries), "Coverage entries must be sorted by stable ID")
    used = {entry["disposition"] for entry in entries.values()}
    require(used == set(dispositions), "Unused or missing disposition classes conceal inventory drift")
    require(type(ledger["known_gaps"]) is list and bool(ledger["known_gaps"]), "Inventory cannot imply semantic closure")
    gap_ids: set[str] = set()
    for gap in ledger["known_gaps"]:
        closed(gap, {"id", "task", "description"}, "gap")
        require(type(gap["id"]) is str and gap["id"] not in gap_ids, "Duplicate or invalid known gap")
        require(type(gap["task"]) is str and gap["task"].startswith("SM-") and bool(gap["description"]), "Missing gap scope/task")
        gap_ids.add(gap["id"])
    lacks_dedicated = sum(not dispositions[entry["disposition"]]["witnesses"]["dedicated"] for entry in entries.values())
    require(not lacks_dedicated or "dedicated_witnesses" in gap_ids, "Missing dedicated evidence must remain an explicit gap")
    return {
        "schema_version": SCHEMA, "status": "inventory_current", "semantic_acceptance": "not_established",
        "counts": dict(sorted(Counter(entry["kind"] for entry in entries.values()).items())),
        "total_distinctions": len(entries), "without_dedicated_witnesses": lacks_dedicated,
        "stage_counts": {stage: dict(sorted(Counter(dispositions[entry["disposition"]]["stages"][stage]
                         for entry in entries.values()).items())) for stage in STAGES},
        "known_gaps": ledger["known_gaps"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--json", action="store_true", help="Print the complete inventory result and known gaps")
    args = parser.parse_args(argv)
    try:
        result = validate(args.root, read_ledger(args.ledger or args.root / LEDGER))
    except (CoverageError, OSError, SyntaxError, json.JSONDecodeError) as exc:
        print(f"Policy semantic coverage: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"Policy syntax inventory current: {result['total_distinctions']} distinctions; "
              f"{result['without_dedicated_witnesses']} require dedicated witnesses. Semantic acceptance not established.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
