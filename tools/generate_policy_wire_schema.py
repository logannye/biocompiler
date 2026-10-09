"""Generate native policy shapes from the independent versioned language schema.

The Python SDK is a conformance client, inspected without importing or executing
it. Generation never extracts authority from dataclasses or repairs the schema.
This check establishes representation agreement, not semantic acceptance.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
SPECIFICATION = Path("protocol/policy-language-v0.1.schema.json")
MODEL = Path("src/biocompiler/policy/model.py")
TARGET = Path("core/lib/domain/policy_schema.ml")
MAX_SPEC_BYTES = 512 * 1024
MAX_SPEC_DEPTH = 64
MAX_SPEC_NODES = 100_000
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
LITERAL = re.compile(r"[A-Za-z][A-Za-z0-9_.:/-]*\Z")
PROFILE = "biocompiler.policy.v0.1"
# Supported encoding contract. An encoding change needs a new generator profile,
# not an unreviewed metadata change beside an otherwise unchanged shape table.
METADATA = {
    "profile": PROFILE, "revision": 1, "scope": "closed_representation_only",
    "wire_defaults": "none_all_fields_required",
    "canonical_json": {"encoding": "UTF-8", "sort_object_keys": True,
        "array_order": "preserved", "ensure_ascii": False, "separators": [",", ":"], "allow_nan": False},
    "document_digest": {"algorithm": "SHA-256", "exclude_keys_recursively": ["source_map", "provenance"]},
    "limits": {"max_bytes": 2097152, "max_depth": 64, "max_nodes": 100000,
        "max_string_bytes": 262144, "max_number_characters": 256, "max_decimal_exponent": 1024},
}


class LanguageSchemaError(ValueError):
    """A specification or conformance client differs from the closed contract."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise LanguageSchemaError(message)


def _pairs(items: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in items:
        require(key not in result, f"Duplicate specification key: {key}")
        result[key] = value
    return result


def _forbidden(value: str) -> None:
    raise LanguageSchemaError(f"Nonintegral/nonfinite specification number: {value}")


def _bounded(value: object) -> None:
    pending = [(value, 0)]
    count = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        require(count <= MAX_SPEC_NODES and depth <= MAX_SPEC_DEPTH, "Specification traversal limit exceeded")
        if type(item) is dict:
            pending.extend((child, depth + 1) for pair in item.items() for child in pair)
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            require(len(item.encode("utf-8")) <= 262144, "Specification string limit exceeded")
        else:
            require(item is None or type(item) in (int, bool), "Unsupported specification scalar")


def shape(value: dict, names: set[str]) -> str:
    """Translate only the normative schema's closed shape vocabulary."""
    require(type(value) is dict, "Schema shapes must be objects")
    if set(value) == {"type"}:
        primitive = {"string": "String", "integer": "Integer", "boolean": "Boolean", "null": "Null"}
        require(type(value["type"]) is str and value["type"] in primitive, "Unknown primitive shape")
        return primitive[value["type"]]
    if set(value) == {"$ref"}:
        reference = value["$ref"]
        require(type(reference) is str and reference.startswith("#/$defs/") and reference[8:] in names,
                "Record reference must resolve in the language specification")
        return "Record " + json.dumps(reference[8:])
    if set(value) == {"enum"}:
        values = value["enum"]
        require(type(values) is list and bool(values) and all(type(item) is str for item in values),
                "Literal alternatives must be nonempty exact strings")
        require(all(LITERAL.fullmatch(item) for item in values), "Unsupported literal spelling")
        require(len(set(values)) == len(values), "Duplicate literal alternative")
        return "Literals [" + "; ".join(json.dumps(item) for item in values) + "]"
    if set(value) == {"anyOf"}:
        alternatives = value["anyOf"]
        require(type(alternatives) is list and len(alternatives) >= 2, "Union needs at least two shapes")
        rendered = [shape(item, names) for item in alternatives]
        require(len(set(rendered)) == len(rendered), "Duplicate union alternative")
        return "Union [" + "; ".join(rendered) + "]"
    if set(value) == {"type", "items"} and value["type"] == "array":
        return "Many (" + shape(value["items"], names) + ")"
    if set(value) == {"type", "prefixItems", "minItems", "maxItems"} and value["type"] == "array":
        items = value["prefixItems"]
        require(type(items) is list and type(value["minItems"]) is int and type(value["maxItems"]) is int
                and value["minItems"] == value["maxItems"] == len(items), "Tuple arity differs from its shapes")
        return "Tuple [" + "; ".join(shape(item, names) for item in items) + "]"
    raise LanguageSchemaError("Unknown or extended schema shape: " + repr(value))


def validate(specification: object) -> dict:
    _bounded(specification)
    require(type(specification) is dict and set(specification) == {
        "$schema", "$id", "title", "oneOf", "$defs", "x-policy-language"}, "Unexpected language schema root")
    require(specification["$schema"] == "https://json-schema.org/draft/2020-12/schema"
            and specification["$id"] == "https://biocompiler.org/protocol/policy-language-v0.1.schema.json",
            "Unsupported language schema identity")
    require(specification["title"] == "Biocompiler policy declarations (representation only)", "Unexpected schema scope")
    # Serialized comparison distinguishes integer 1 from boolean true.
    require(json.dumps(specification["x-policy-language"], sort_keys=True) == json.dumps(METADATA, sort_keys=True),
            "Unsupported language encoding, defaults, limits or version")
    records = specification["$defs"]
    require(type(records) is dict and bool(records), "Language records must be a nonempty object")
    names = set(records)
    require(all(type(name) is str and IDENTIFIER.fullmatch(name) for name in names), "Invalid record name")
    require(specification["oneOf"] == [{"$ref": "#/$defs/" + name}
            for name in ("PolicyDraft", "PolicyProgram", "BuildRequest")], "Unexpected public document roots")
    for root in specification["oneOf"]:
        shape(root, names)
    for name, record in records.items():
        require(type(record) is dict and set(record) == {"type", "properties", "required", "additionalProperties"}
                and record["type"] == "object" and record["additionalProperties"] is False,
                "Records must be closed objects without wire defaults: " + name)
        properties, required = record["properties"], record["required"]
        require(type(properties) is dict and type(required) is list and bool(required)
                and all(type(field) is str for field in required), "Invalid record fields: " + name)
        require(len(set(required)) == len(required) and set(required) == set(properties)
                and required[0] == "$type" and properties["$type"] == {"const": name},
                "Every field and exact discriminator must be required: " + name)
        for field in required[1:]:
            require(IDENTIFIER.fullmatch(field) is not None, "Invalid field name: " + field)
            shape(properties[field], names)
    return specification


def read_specification(path: Path | None = None) -> dict:
    with (path or ROOT / SPECIFICATION).open("rb") as stream:
        raw = stream.read(MAX_SPEC_BYTES + 1)
    require(len(raw) <= MAX_SPEC_BYTES, "Specification byte limit exceeded")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                           parse_float=_forbidden, parse_constant=_forbidden)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise LanguageSchemaError("Invalid language specification JSON") from exc
    return validate(value)


def specification_digest(specification: dict) -> str:
    raw = json.dumps(validate(specification), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def render(specification: dict | None = None) -> str:
    specification = read_specification() if specification is None else validate(specification)
    records = specification["$defs"]
    lines = [
        "(* Generated by tools/generate_policy_wire_schema.py from the versioned language schema.",
        "   Closed representation data only; no semantic acceptance authority. *)",
        'let language_sha256 = "' + specification_digest(specification) + '"',
        "type shape = String | Integer | Boolean | Null | Literals of string list",
        "  | Record of string | Many of shape | Tuple of shape list | Union of shape list",
        "let records = [",
    ]
    for name, record in sorted(records.items()):
        members = ";\n    ".join(json.dumps(field) + ", " + shape(record["properties"][field], set(records))
                                for field in record["required"][1:])
        lines.append("  " + json.dumps(name) + ", [\n    " + members + "];" )
    lines.extend(["]", "let find name = List.assoc_opt name records", ""])
    return "\n".join(lines)


def check_python_conformance(specification: dict, source: str | None = None) -> None:
    """Inspect declaration annotations inertly; Python is never generation input."""
    specification = validate(specification)
    tree = ast.parse((ROOT / MODEL).read_text() if source is None else source)
    classes: dict[str, ast.ClassDef] = {}
    aliases: dict[str, ast.expr] = {}
    alias_nodes: dict[str, ast.AnnAssign] = {}
    profiles = []
    profile_nodes = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            require(node.name not in classes, "Duplicate Python class: " + node.name)
            classes[node.name] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if isinstance(node.annotation, ast.Name) and node.annotation.id == "TypeAlias":
                require(node.target.id not in aliases and node.value is not None, "Duplicate/empty Python type alias")
                aliases[node.target.id] = node.value
                alias_nodes[node.target.id] = node
        elif isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "PROFILE" for target in node.targets):
            profiles.append(ast.literal_eval(node.value))
            profile_nodes.append(node)
    require(profiles == [PROFILE], "Python profile differs from the language specification")
    record_names = set(specification["$defs"])
    records = {name: node for name, node in classes.items()
               if any(isinstance(base, ast.Name) and base.id in record_names | {"Record"} for base in node.bases)}
    require(set(records) == set(specification["$defs"]), "Python record census differs from the language specification")
    require("Record" in classes and not classes["Record"].bases and not classes["Record"].keywords
            and not any(isinstance(item, ast.AnnAssign) for item in classes["Record"].body),
            "Python Record base must not supply implicit wire fields")
    require(not set(classes) & set(aliases), "Python class/type alias identity collision")

    def bound_names(node: ast.AST) -> set[str]:
        # Traverse module-level control structures, but not function/class local
        # scopes. Detect declarations/imports as well as destructuring stores.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return {node.name}
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            require(all(item.name != "*" for item in node.names), "Wildcard Python bindings are unsupported")
            return {item.asname or item.name.split(".")[0] for item in node.names}
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            return {node.id}
        result = {node.name} if isinstance(node, ast.ExceptHandler) and node.name else set()
        for child in ast.iter_child_nodes(node):
            result.update(bound_names(child))
        return result

    protected = record_names | set(aliases) | {"Record", "PROFILE"}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in protected:
            continue
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and alias_nodes.get(node.target.id) is node:
            continue
        if node in profile_nodes:
            continue
        require(not bound_names(node) & protected, "Python record/type alias is reassigned")

    def annotation(node: ast.expr, active: tuple[str, ...] = ()) -> dict:
        if isinstance(node, ast.Name):
            primitives = {"str": "string", "int": "integer", "bool": "boolean"}
            if node.id in primitives:
                return {"type": primitives[node.id]}
            if node.id in records:
                return {"$ref": "#/$defs/" + node.id}
            if node.id in aliases:
                require(node.id not in active, "Recursive Python type alias")
                return annotation(aliases[node.id], (*active, node.id))
        elif isinstance(node, ast.Constant) and node.value is None:
            return {"type": "null"}
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            alternatives = []
            for child in (node.left, node.right):
                item = annotation(child, active)
                alternatives.extend(item["anyOf"] if "anyOf" in item else [item])
            unique = []
            for item in alternatives:
                if item not in unique:
                    unique.append(item)
            return {"anyOf": unique} if len(unique) > 1 else unique[0]
        elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            items = node.slice.elts if isinstance(node.slice, ast.Tuple) else [node.slice]
            if node.value.id == "Literal":
                require(all(isinstance(item, ast.Constant) and type(item.value) is str for item in items),
                        "Python literal alternatives must be exact strings")
                return {"enum": [item.value for item in items]}
            if node.value.id == "tuple":
                if len(items) == 2 and isinstance(items[1], ast.Constant) and items[1].value is Ellipsis:
                    return {"type": "array", "items": annotation(items[0], active)}
                return {"type": "array", "prefixItems": [annotation(item, active) for item in items],
                        "minItems": len(items), "maxItems": len(items)}
        raise LanguageSchemaError("Unsupported Python annotation: " + ast.dump(node))

    require("Document" in aliases and annotation(aliases["Document"]) == {"anyOf": specification["oneOf"]},
            "Python Document alias differs from the language specification")
    for name, node in records.items():
        require(len(node.bases) == 1 and isinstance(node.bases[0], ast.Name)
                and node.bases[0].id == "Record" and not node.keywords,
                "Unexpected Python record inheritance: " + name)
        require(any(isinstance(item, ast.Call) and isinstance(item.func, ast.Name) and item.func.id == "dataclass"
                    and any(keyword.arg == "frozen" and isinstance(keyword.value, ast.Constant)
                            and keyword.value.value is True for keyword in item.keywords)
                    for item in node.decorator_list), "Python wire records must remain frozen dataclasses: " + name)
        properties = {"$type": {"const": name}}
        for field in node.body:
            if isinstance(field, ast.AnnAssign):
                require(isinstance(field.target, ast.Name), "Unsupported Python field target")
                identity = field.target.id
                require(identity not in properties, "Duplicate Python field: " + name + "." + identity)
                properties[identity] = annotation(field.annotation)
        expected = specification["$defs"][name]
        require(list(properties) == expected["required"] and properties == expected["properties"],
                "Python fields/types differ from the language specification: " + name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        specification = read_specification()
        expected = render(specification)
        check_python_conformance(specification)
        target = ROOT / TARGET
        if args.check:
            require(target.exists() and target.read_text() == expected,
                    "Native policy schema differs from the language specification; regenerate and review")
            print(f"Language schema and Python/native clients agree on {len(specification['$defs'])} closed records.")
        else:
            target.write_text(expected)
        return 0
    except (LanguageSchemaError, SyntaxError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
