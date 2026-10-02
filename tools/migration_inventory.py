#!/usr/bin/env python3
"""Reproduce the LM-00 public capability ledger without importing product code.

This is source discovery, not execution coverage or a semantic parity certificate.
Unknown dynamic export/CLI/schema declarations fail instead of disappearing.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERSION_LITERAL = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*\.v[0-9]+(?:\.[0-9]+)*$")
CODECS = {"to_dict", "from_dict", "to_json", "from_json", "fingerprint", "parse_json", "freeze_json", "thaw_json"}


class InventoryError(ValueError):
    """The source cannot be inventoried completely by the supported static rules."""


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def assignments(body):
    for node in body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    yield target.id, node.value, node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            yield node.target.id, node.value, node


def literal(node, resolve):
    """Evaluate only a closed, side-effect-free subset; never exec/import source."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return resolve(node.id)
    if isinstance(node, ast.Attribute):
        return resolve(ast.unparse(node))
    if isinstance(node, ast.Subscript):
        value, key = literal(node.value, resolve), literal(node.slice, resolve)
        if ((type(value) is dict and type(key) in (str, int))
                or (type(value) in (tuple, list) and type(key) is int)):
            return value[key]
        raise InventoryError("Only literal mapping/sequence lookups may appear in static declarations")
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values = []
        for item in node.elts:
            if isinstance(item, ast.Starred):
                values.extend(literal(item.value, resolve))
            else:
                values.append(literal(item, resolve))
        return set(values) if isinstance(node, ast.Set) else values
    if isinstance(node, ast.DictComp) and len(node.generators) == 1:
        generator = node.generators[0]
        if isinstance(generator.target, ast.Name) and not generator.is_async:
            result = {}
            for item in literal(generator.iter, resolve):
                local = lambda name, item=item: item if name == generator.target.id else resolve(name)
                if all(literal(condition, local) for condition in generator.ifs):
                    result[literal(node.key, local)] = literal(node.value, local)
            return result
    if isinstance(node, ast.Dict):
        result = {}
        for key, value in zip(node.keys, node.values):
            if key is None:
                result.update(literal(value, resolve))
            else:
                result[literal(key, resolve)] = literal(value, resolve)
        return result
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {
        "frozenset", "set", "tuple", "list", "freeze_json", "MappingProxyType"
    } and len(node.args) == 1 and not node.keywords:
        value = literal(node.args[0], resolve)
        return set(value) if node.func.id in {"set", "frozenset"} else value
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name) and node.func.value.id == "json"
            and node.func.attr == "loads" and len(node.args) == 1 and not node.keywords):
        document = literal(node.args[0], resolve)
        if type(document) is not str:
            raise InventoryError("Static JSON declarations require literal text")
        def no_constant(value):
            raise InventoryError("Non-finite static JSON declaration: " + value)
        def unique_fields(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise InventoryError("Duplicate static JSON declaration field: " + key)
                result[key] = value
            return result
        try:
            return json.loads(document, parse_constant=no_constant, object_pairs_hook=unique_fields)
        except json.JSONDecodeError as exc:
            raise InventoryError("Malformed static JSON declaration") from exc
    if isinstance(node, ast.BinOp):
        left, right = literal(node.left, resolve), literal(node.right, resolve)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.BitOr):
            return left | right
        if isinstance(node.op, ast.Mult) and type(left) is int and type(right) is int:
            return left * right
    if isinstance(node, ast.JoinedStr):
        return "".join(str(literal(item.value, resolve)) if isinstance(item, ast.FormattedValue)
                       else str(item.value) for item in node.values)
    if isinstance(node, ast.IfExp):
        return literal(node.body if literal(node.test, resolve) else node.orelse, resolve)
    if isinstance(node, ast.Compare) and len(node.ops) == 1:
        left, right = literal(node.left, resolve), literal(node.comparators[0], resolve)
        op = node.ops[0]
        if isinstance(op, ast.Eq):
            return left == right
        if isinstance(op, ast.NotEq):
            return left != right
        if isinstance(op, ast.In):
            return left in right
        if isinstance(op, ast.NotIn):
            return left not in right
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not literal(node.operand, resolve)
    raise InventoryError(f"Unresolved static expression at line {getattr(node, 'lineno', '?')}: {ast.unparse(node)}")


def json_value(value):
    if isinstance(value, set):
        return sorted((json_value(item) for item in value), key=canonical)
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    return value


@dataclass
class Source:
    path: str
    module: str
    text: str
    tree: ast.Module
    bindings: dict
    imports: dict
    definitions: dict


class Sources:
    def __init__(self, root: Path):
        self.root = root
        self.modules = {}
        for path in sorted((root / "src" / "biocompiler").rglob("*.py")):
            relative = path.relative_to(root).as_posix()
            parts = list(path.relative_to(root / "src").with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            module = ".".join(parts)
            text = path.read_text(encoding="utf-8")
            try:
                tree = ast.parse(text, filename=relative)
            except SyntaxError as exc:
                raise InventoryError(f"Invalid Python source: {relative}: {exc}") from exc
            bindings = {name: value for name, value, _ in assignments(tree.body)}
            definitions = {item.name: item for item in tree.body
                           if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))}
            imports = {}
            for node in tree.body:
                if isinstance(node, ast.ImportFrom):
                    if node.level:
                        package = module if path.name == "__init__.py" else module.rpartition(".")[0]
                        prefix = package.split(".")[:len(package.split(".")) - node.level + 1]
                        origin = ".".join(prefix + ([node.module] if node.module else []))
                    else:
                        origin = node.module or ""
                    for alias in node.names:
                        if alias.name == "*":
                            raise InventoryError(f"Wildcard import needs explicit inventory support: {relative}:{node.lineno}")
                        imports[alias.asname or alias.name] = (origin, alias.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports[alias.asname or alias.name.split(".")[0]] = (alias.name if alias.asname else alias.name.split(".")[0], "")
            self.modules[module] = Source(relative, module, text, tree, bindings, imports, definitions)
        if not self.modules:
            raise InventoryError("No src/biocompiler Python modules found")

    def origin(self, module, name, seen=()):
        key = (module, name)
        if key in seen:
            raise InventoryError(f"Cyclic public binding: {module}.{name}")
        source = self.modules.get(module)
        if source is None:
            raise InventoryError(f"Missing source for public binding: {module}.{name}")
        if name in source.imports:
            owner, symbol = source.imports[name]
            if owner in self.modules and symbol:
                return self.origin(owner, symbol, (*seen, key))
            if not symbol and owner in self.modules:
                return owner, ""
            raise InventoryError(f"Unresolved public import: {module}.{name} -> {owner}.{symbol}")
        if name in source.bindings or name in source.definitions:
            return module, name
        raise InventoryError(f"Public symbol has no declaration: {module}.{name}")

    def value(self, module, name, seen=()):
        key = (module, name)
        if key in seen:
            raise InventoryError(f"Cyclic constant: {module}.{name}")
        source = self.modules.get(module)
        if source is None:
            raise InventoryError(f"Unknown constant module: {module}.{name}")
        if name in source.imports:
            owner, symbol = source.imports[name]
            return self.value(owner, symbol, (*seen, key))
        if "." in name:
            prefix, rest = name.split(".", 1)
            if prefix in source.imports:
                owner, symbol = source.imports[prefix]
                return self.value(owner, ".".join(filter(None, (symbol, rest))), (*seen, key))
            cls = source.definitions.get(prefix)
            if isinstance(cls, ast.ClassDef):
                members = {n: v for n, v, _ in assignments(cls.body)}
                if rest in members:
                    return literal(members[rest], lambda n: self.value(module, n, (*seen, key)))
        if name in source.bindings:
            return literal(source.bindings[name], lambda n: self.value(module, n, (*seen, key)))
        if name in source.definitions:
            return {"symbol": module + "." + name}
        raise InventoryError(f"Unknown static name: {module}.{name}")


def cli_commands(source: Source):
    """Expand literal loops/branches in registration code; reject dynamic names."""
    definitions = source.definitions
    commands, visited = {}, set()

    def evaluate(node, env):
        def resolve(name):
            if name in env:
                return env[name]
            raise InventoryError(f"Unresolved CLI registration name: {name}")
        return literal(node, resolve)

    def call(node, env, stack):
        if isinstance(node.func, ast.Name) and node.func.id in definitions:
            function = definitions[node.func.id]
            if node.func.id in stack:
                raise InventoryError("Recursive CLI registration is unsupported")
            local = dict(env)
            local.update({param.arg: evaluate(arg, env) for param, arg in zip(function.args.args, node.args)})
            walk(function.body, local, (*stack, node.func.id))
            return None
        if not isinstance(node.func, ast.Attribute):
            return None
        method = node.func.attr
        if method == "ArgumentParser":
            return {"parser_kind": "root"}
        if method not in {"add_subparsers", "add_parser", "add_argument", "add_mutually_exclusive_group", "add_argument_group"}:
            return None
        owner = evaluate(node.func.value, env)
        if not isinstance(owner, dict) or "parser_kind" not in owner:
            raise InventoryError(f"Unknown CLI parser receiver: {ast.unparse(node.func.value)}")
        if method == "add_subparsers":
            return {"parser_kind": "subparsers"}
        if method == "add_parser":
            if owner["parser_kind"] != "subparsers":
                raise InventoryError("CLI parser registration has unknown parent")
            name = evaluate(node.args[0], env)
            if not isinstance(name, str) or not name:
                raise InventoryError("CLI command names must be nonempty strings")
            if name in commands:
                raise InventoryError(f"Duplicate CLI command: {name}")
            visited.add(node.lineno)
            record = {"name": name, "line": node.lineno, "arguments": [], "help": ""}
            for keyword in node.keywords:
                if keyword.arg in {"help", "aliases"}:
                    record[keyword.arg] = evaluate(keyword.value, env)
            commands[name] = record
            return {"parser_kind": "command", "record": record}
        if method in {"add_mutually_exclusive_group", "add_argument_group"}:
            group = dict(owner)
            group["group"] = {keyword.arg: evaluate(keyword.value, env) for keyword in node.keywords}
            group["group"]["kind"] = method
            return group
        if owner["parser_kind"] == "command":
            argument = {"flags": [evaluate(item, env) for item in node.args]}
            for keyword in node.keywords:
                if keyword.arg in {"required", "choices", "action", "nargs", "const", "default", "dest"}:
                    argument[keyword.arg] = evaluate(keyword.value, env)
                elif keyword.arg == "type":
                    argument["type"] = ast.unparse(keyword.value)
            if "group" in owner:
                argument["group"] = owner["group"]
            owner["record"]["arguments"].append(argument)
        return None

    def walk(body, env, stack):
        for node in body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                value = node.value
                if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr == "parse_args":
                    return
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                result = call(value, env, stack) if isinstance(value, ast.Call) else evaluate(value, env)
                for target in targets:
                    if isinstance(target, ast.Name):
                        env[target.id] = result
            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                call(node.value, env, stack)
            elif isinstance(node, ast.For):
                if not isinstance(node.target, ast.Name):
                    raise InventoryError("Unsupported CLI registration loop target")
                for item in evaluate(node.iter, env):
                    env[node.target.id] = item
                    walk(node.body, env, stack)
            elif isinstance(node, ast.If):
                walk(node.body if evaluate(node.test, env) else node.orelse, env, stack)
            elif isinstance(node, (ast.Pass, ast.Expr)):
                continue
            else:
                raise InventoryError(f"Unsupported CLI registration statement: {type(node).__name__}:{node.lineno}")

    main = definitions.get("main")
    if not isinstance(main, ast.FunctionDef):
        raise InventoryError("CLI main registration function missing")
    walk(main.body, {}, ("main",))
    declared = {node.lineno for node in ast.walk(source.tree) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute) and node.func.attr == "add_parser"}
    if declared != visited:
        raise InventoryError(f"Unaccounted CLI registration lines: {sorted(declared - visited)}")
    return [commands[name] for name in sorted(commands)]


def ownership(module, category):
    if category == "studio_asset":
        return "TypeScript", ["LM-10", "LM-30"], "preserve_studio_surface"
    if category == "example":
        return "Python", ["LM-03", "LM-11"], "retain_example_with_core_routing"
    if module.startswith("biocompiler.frontend") or module in {"biocompiler.errors", "biocompiler", "biocompiler.__main__"}:
        return "Python", ["LM-11"], "retain_python_authoring_or_compatibility_adapter"
    if module in {"biocompiler.cli", "biocompiler.core_client", "biocompiler.core_pipeline_session", "biocompiler.core_pipeline_callback_session", "biocompiler.core_pipeline_manager", "biocompiler.pipeline_callback_objects", "biocompiler.core_architecture", "biocompiler.core_architecture_producer", "biocompiler.architecture_backend", "biocompiler.core_realization", "biocompiler.core_synthetic_producer", "biocompiler.synthetic_producer_backend", "biocompiler.core_synthetic_producer_public", "biocompiler.synthetic_producer_cli", "biocompiler.core_synthetic_inspection", "biocompiler.realization_backend", "biocompiler.core_artifacts", "biocompiler.core_workflow", "biocompiler.core_workflow_authority", "biocompiler.workflow_backend", "biocompiler.workflow_cli", "biocompiler.interop"} or module.startswith("biocompiler.studio"):
        return "Python", ["LM-10", "LM-11", "LM-25"], "retain_transport_route_semantic_authority_to_ocaml"
    section = module.split(".")[1] if "." in module else ""
    tasks = {"ir": ["LM-02", "LM-20"], "semantics": ["LM-20", "LM-21"],
             "models": ["LM-21", "LM-25"], "compiler": ["LM-22", "LM-23", "LM-24"],
             "synthesis": ["LM-22", "LM-23"], "backends": ["LM-24"],
             "verification": ["LM-25"], "artifacts": ["LM-26"], "registry": ["LM-22", "LM-23"]}
    if section not in tasks:
        raise InventoryError(f"No reviewed ownership rule for {module} ({category})")
    return "OCaml", tasks[section], "migrate_authority_preserve_python_public_facade"


def authority(module, category):
    if category in {"example", "studio_asset"}:
        return "authored_or_displayed_inputs_are_not_acceptance_authority"
    if module.startswith("biocompiler.verification"):
        return "independent_complete_request_and_pinned_component_model_sequence_roots"
    if module.startswith("biocompiler.models") or module in {"biocompiler.semantics.architecture_execution"}:
        return "candidate_records_and_locked_component_models_separate_from_source_evaluator"
    if module.startswith("biocompiler.frontend"):
        return "authored_program_freezes_explicit_domain_semantics"
    if module.startswith("biocompiler.ir"):
        return "versioned_domain_schema_and_explicit_validation_contract"
    if module.startswith("biocompiler.semantics"):
        return "versioned_semantics_and_explicit_request_assumptions"
    if module.startswith("biocompiler.artifacts"):
        return "fresh_independent_verification_and_exact_pinned_content_before_export"
    return "complete_explicit_operation_request_and_dependency_pins"


def test_references(root):
    names, values, files = defaultdict(set), defaultdict(set), []
    for path in sorted((root / "tests").rglob("test*.py")):
        if path.name == "test_migration_inventory.py":
            # Inventory tests are not evidence of product capability coverage.
            continue
        rel = path.relative_to(root).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        files.append(rel)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names[node.id].add(rel)
            elif isinstance(node, ast.Attribute):
                names[node.attr].add(rel)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                values[node.value].add(rel)
    return names, values, files


def build_inventory(root: Path):
    root = root.resolve()
    sources = Sources(root)
    tests_by_name, tests_by_value, test_files = test_references(root)
    entries, modules = [], []

    def add(category, identity, source, line, symbol="", value=None, **details):
        owner, tasks, disposition = ownership(source.module, category)
        references = set(tests_by_name.get(symbol.split(".")[-1], ())) if symbol else set()
        if isinstance(value, str):
            references.update(tests_by_value.get(value, ()))
        record = {"id": category + ":" + identity, "category": category,
                  "current_implementation": {"language": "JavaScript" if category == "studio_asset" and source.path.endswith(".js") else "Python",
                                             "module": source.module, "path": source.path, "line": line},
                  "source_authority": authority(source.module, category), "target_owner": owner,
                  "dependent_tasks": tasks, "disposition": disposition, "migration_state": "legacy",
                  "compatibility_contract": "preserve_names_signatures_versions_claim_scope_and_fresh_authority; intentional_breaks_require_versioned_review",
                  "test_coverage": {"kind": "static_reference_candidates", "files": sorted(references),
                                    "execution_status": "not_measured_by_inventory"}, **details}
        if symbol:
            record["symbol"] = symbol
        if value is not None:
            record["value"] = json_value(value)
        entries.append(record)
        return record

    for module, source in sorted(sources.modules.items()):
        dependencies = sorted({node.module for node in ast.walk(source.tree) if isinstance(node, ast.ImportFrom)
                               and node.module and node.module.startswith("biocompiler")}
                              | {alias.name for node in ast.walk(source.tree) if isinstance(node, ast.Import)
                                 for alias in node.names if alias.name.startswith("biocompiler")})
        module_entry = add("module", module, source, 1, imports=dependencies,
                           sha256=hashlib.sha256(source.text.encode()).hexdigest())
        modules.append(module_entry["id"])
        export_assignments = [node for node in ast.walk(source.tree)
                              if isinstance(node, (ast.Assign, ast.AnnAssign))
                              and any(isinstance(target, ast.Name) and target.id == "__all__"
                                      for target in (node.targets if isinstance(node, ast.Assign) else [node.target]))]
        if len(export_assignments) > 1 or any(node not in source.tree.body for node in export_assignments):
            raise InventoryError(f"Conditional or repeated __all__ declaration in {source.path}")
        exports = sources.value(module, "__all__") if "__all__" in source.bindings else []
        if not isinstance(exports, list) or any(not isinstance(item, str) or not item for item in exports):
            raise InventoryError(f"Nonliteral __all__ in {source.path}")
        if len(exports) != len(set(exports)):
            raise InventoryError(f"Duplicate __all__ symbol in {source.path}")
        mutations = [node for node in ast.walk(source.tree) if
                     (isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == "__all__")
                     or (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                         and isinstance(node.func.value, ast.Name) and node.func.value.id == "__all__")]
        if mutations or any(isinstance(node, ast.Name) and node.id == "__all__" and isinstance(node.ctx, ast.Load)
                            for node in ast.walk(source.tree)):
            raise InventoryError(f"Dynamic __all__ mutation or alias in {source.path}")
        if any(isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store)
               and isinstance(node.value, ast.Name) and node.value.id == "__all__" for node in ast.walk(source.tree)):
            raise InventoryError(f"Dynamic __all__ subscript mutation in {source.path}")
        for name in exports:
            owner_module, owner_symbol = sources.origin(module, name)
            owner_source = sources.modules[owner_module]
            declaration = owner_source.definitions.get(owner_symbol) or owner_source.bindings.get(owner_symbol)
            record = add("export", module + "." + name, owner_source, getattr(declaration, "lineno", 1), symbol=name,
                         exposed_by=module, implementation_symbol=owner_module + "." + owner_symbol)
            record["compatibility_contract"] = "retain_Python_import_at_exposed_by_and_symbol"
        for name, node in sorted(source.definitions.items()):
            if not name.startswith("_"):
                details = {"definition_kind": type(node).__name__}
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    details["signature"] = ast.unparse(node.args)
                    if node.returns:
                        details["returns"] = ast.unparse(node.returns)
                else:
                    details["bases"] = [ast.unparse(item) for item in node.bases]
                    details["public_methods"] = [{"name": member.name, "signature": ast.unparse(member.args)}
                                                 for member in node.body if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
                                                 and not member.name.startswith("_")]
                add("public_definition", module + "." + name, source, node.lineno, symbol=name, **details)
            if isinstance(node, ast.ClassDef) and name.endswith("Operation") and not name.startswith("_"):
                add("ir_operation", module + "." + name, source, node.lineno, symbol=name,
                    representation="operation_record")
        scopes = [("", source.tree.body)] + [(name + ".", node.body) for name, node in source.definitions.items()
                                             if isinstance(node, ast.ClassDef)]
        for scope, body in scopes:
            for name, value_node, node in assignments(body):
                if name == "schema_version" or name.endswith(("VERSION", "PROFILE")) or name == "__version__":
                    try:
                        value = literal(value_node, lambda n: sources.value(module, n))
                    except (InventoryError, TypeError) as exc:
                        raise InventoryError(f"Unresolved version declaration {module}.{scope}{name}: {exc}") from exc
                    add("schema" if name == "schema_version" else "version_profile",
                        module + "." + scope + name, source, node.lineno, symbol=scope + name, value=value)
                if module.startswith("biocompiler.ir") and any(word in name for word in ("KINDS", "OPERATIONS", "OPERATION_TYPES")):
                    value = sources.value(module, name)
                    members = sorted(value) if isinstance(value, (dict, set)) else value
                    if not isinstance(members, list):
                        members = list(members)
                    for item in members:
                        label = item["symbol"] if isinstance(item, dict) and "symbol" in item else str(item)
                        add("ir_operation", module + "." + scope + name + ":" + label, source, node.lineno,
                            symbol=scope + name, value=item, representation="declared_operation_or_kind_set")
            for node in body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in CODECS:
                    add("serializer", module + "." + scope + node.name, source, node.lineno,
                        symbol=scope + node.name, signature=ast.unparse(node.args))
        literals = defaultdict(list)
        for node in ast.walk(source.tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and VERSION_LITERAL.fullmatch(node.value):
                literals[node.value].append(node.lineno)
        for value, lines in sorted(literals.items()):
            add("version_literal", module + ":" + value, source, min(lines), value=value, occurrence_lines=sorted(set(lines)))
        if module.startswith(("biocompiler.verification", "biocompiler.models", "biocompiler.semantics", "biocompiler.synthesis", "biocompiler.backends", "biocompiler.compiler")):
            add("authority_boundary", module, source, 1, import_graph_entry="module:" + module,
                role="checker" if ".verification" in module else "candidate_execution" if ".models" in module or module.endswith("architecture_execution") else
                "source_execution" if module.endswith(("evaluator", "payload_execution")) else "semantic_or_producer_support",
                boundary_status="current_import_graph_recorded_not_independence_certification")
    cli_source = sources.modules.get("biocompiler.cli")
    if cli_source is None:
        raise InventoryError("CLI source missing")
    for command in cli_commands(cli_source):
        name, line = command.pop("name"), command.pop("line")
        record = add("cli_command", name, cli_source, line, value=name, **command)
        record["source_authority_flags"] = [flag for argument in command["arguments"] for flag in argument["flags"]
                                             if flag.startswith("--expected-") or flag in {"--request", "--inventory"}]
    server = sources.modules.get("biocompiler.studio.server")
    if server is None:
        raise InventoryError("Studio HTTP source missing")
    endpoint_paths = set()
    for table in ("_POST", "_STATIC"):
        declarations = [node for node in ast.walk(server.tree) if isinstance(node, ast.Assign)
                        and any(isinstance(target, ast.Name) and target.id == table for target in node.targets)]
        if len(declarations) != 1 or declarations[0] not in server.tree.body:
            raise InventoryError(f"Repeated or conditional Studio endpoint table: {table}")
        for node in ast.walk(server.tree):
            mutation = (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name) and node.func.value.id == table)
            mutation |= (isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store)
                         and isinstance(node.value, ast.Name) and node.value.id == table)
            mutation |= (isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and node.target.id == table)
            if mutation:
                raise InventoryError(f"Dynamic Studio endpoint table mutation: {table}")
    for name, method in (("_POST", "POST"), ("_STATIC", "GET/HEAD")):
        node = server.bindings.get(name)
        if not isinstance(node, ast.Dict) or any(not isinstance(key, ast.Constant) or not isinstance(key.value, str) for key in node.keys):
            raise InventoryError(f"Unresolved Studio endpoint table: {name}")
        for key, value in zip(node.keys, node.values):
            endpoint_paths.add(key.value)
            add("studio_endpoint", method + " " + key.value, server, key.lineno, value=key.value,
                method=method, handler=ast.unparse(value))
    for node in ast.walk(server.tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Attribute) and node.left.attr == "path":
            for comparator in node.comparators:
                if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str) and comparator.value.startswith("/"):
                    endpoint_paths.add(comparator.value)
                    # The only out-of-table API currently has an explicit GET guard.
                    if comparator.value != "/api/session":
                        raise InventoryError(f"Studio direct route needs method mapping: {comparator.value}")
                    add("studio_endpoint", "GET " + comparator.value, server, comparator.lineno, value=comparator.value,
                        method="GET", handler="service.session")
    api_literals = {node.value for node in ast.walk(server.tree) if isinstance(node, ast.Constant)
                    and isinstance(node.value, str) and node.value.startswith("/api/")}
    if not api_literals <= endpoint_paths:
        raise InventoryError(f"Unaccounted Studio API paths: {sorted(api_literals - endpoint_paths)}")
    for folder, category in ((root / "examples", "example"), (root / "src/biocompiler/studio/static", "studio_asset")):
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or (category == "example" and path.suffix != ".py"):
                continue
            rel = path.relative_to(root).as_posix()
            source = Source(rel, "biocompiler.studio" if category == "studio_asset" else "examples", "", ast.Module(body=[], type_ignores=[]), {}, {}, {})
            record = add(category, rel, source, 1, symbol=path.stem, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            if category == "studio_asset" and path.suffix != ".js":
                record["current_implementation"]["language"] = path.suffix.removeprefix(".").upper()
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    for name, target in sorted(project.get("scripts", {}).items()):
        source = sources.modules[target.split(":")[0]]
        add("console_script", name, source, 1, value=target, command=name)
    identities = [item["id"] for item in entries]
    duplicates = [key for key, count in Counter(identities).items() if count != 1]
    if duplicates:
        raise InventoryError(f"Duplicate inventory identities: {duplicates}")
    # Normalize repeated contracts, source paths and coverage candidate sets without
    # removing individual entries or test links. IDs derive only from content.
    contracts, coverage, source_table = {}, {}, {}
    contract_fields = ("source_authority", "target_owner", "dependent_tasks", "disposition", "compatibility_contract")
    for entry in entries:
        contract = {key: entry.pop(key) for key in contract_fields}
        contract_id = "contract_" + hashlib.sha256(canonical(contract).encode()).hexdigest()[:12]
        contracts[contract_id] = contract
        entry["contract"] = contract_id
        candidate = entry.pop("test_coverage")
        candidate["file_indices"] = [test_files.index(path) for path in candidate.pop("files")]
        coverage_id = "tests_" + hashlib.sha256(canonical(candidate).encode()).hexdigest()[:12]
        coverage[coverage_id] = candidate
        entry["test_coverage"] = coverage_id
        implementation = entry["current_implementation"]
        source_id = implementation["module"].removeprefix("biocompiler.") if implementation["path"].startswith("src/") and implementation["path"].endswith(".py") else implementation["path"]
        source_table[source_id] = {key: implementation[key] for key in ("module", "path", "language")}
        entry["current_implementation"] = {"source": source_id, "line": implementation["line"]}
    return {"schema_version": "biocompiler.migration_inventory.v0.1", "package_version": project["version"],
            "baseline_commit": "6156ed2841fd3308df833f1afe0e3f6af5d12bf6", "initial_migration_branch": "codex/language-migration",
            "scope": "current_source_ledger_including_new_migration_adapters; baseline_commit_is_starting_anchor_not_snapshot_revision",
            "coverage_method": "AST names and exact string references identify candidate test files, not executed coverage; no product modules imported",
            "migration_state_policy": "legacy is the initial LM-00 state, never an assertion of a completed port",
            "test_source_files": test_files, "counts": dict(sorted(Counter(item["category"] for item in entries).items())),
            "sources": dict(sorted(source_table.items())), "contracts": dict(sorted(contracts.items())),
            "test_reference_sets": dict(sorted(coverage.items())),
            "entries": sorted(entries, key=lambda item: item["id"])}


def markdown(inventory):
    counts = inventory["counts"]
    lines = ["# Language migration coverage ledger", "", "Generated by `python3 tools/migration_inventory.py`. Do not edit the generated ledger by hand.", "",
             "The complete per-entry ledger is [migration-inventory.json](../protocol/migration-inventory.json). This readable index supplements that file; it does not replace individual API, schema, serializer or operation records.", "",
             f"Starting baseline anchor: `{inventory['baseline_commit']}`; package `{inventory['package_version']}`. This ledger describes the current source snapshot, including newly introduced migration adapters such as `core_client.py`; it is not a whole-tree inventory of the starting commit. Per-module source digests bind the inspected implementation. The [baseline CI receipt](../protocol/migration-baseline.json) and retained conformance corpus are separate evidence. This inventory does not complete all LM-00 exit conditions.", "",
             "Every discovered entry records its current declaration and `legacy` migration state. Its referenced contract records target owner, authority category, dependent migration tasks, compatibility requirement and disposition. Source paths and static test-reference sets use shared keyed tables to avoid duplicating evidence. Test-reference `file_indices` address the complete ordered `test_source_files` array. Python public names remain compatibility facades where semantic ownership moves to OCaml. Studio transport remains Python; browser behavior moves to TypeScript.", "",
             "Static test references are candidate coverage links, not executed coverage or semantic parity. Empty test lists are visible coverage gaps. Shared names can produce false positives; inspect the linked tests before using them as acceptance evidence. The inventory neither imports product modules nor executes examples or compiler operations.", "",
             "Discovery includes every Python module, every explicit `__all__` export (resolved to its declaration), public top-level classes/functions with public method signatures, declared schema/version/profile constants and version literals, IR operation/kind sets and operation records, serializer definitions, expanded CLI commands and argument contracts, Studio endpoints/assets, examples and semantic/checker import boundaries. Private implementation helpers are represented by their owning module, not advertised as public APIs.", "",
             "Unknown export bindings, dynamic export mutations, unresolved schema/profile declarations, unvisited or duplicate CLI registrations and unknown Studio route forms fail discovery. New source forms require extending the scanner and its regression tests. Source digests bind this ledger to the inspected implementation; rerun after source changes.", "",
             "| Inventory category | Entries |", "| --- | ---: |"]
    lines += [f"| `{category}` | {count} |" for category, count in counts.items()]
    lines += ["", "## CLI command index", "", "| Command | Independent/request authority flags | State |", "| --- | --- | --- |"]
    for entry in inventory["entries"]:
        if entry["category"] == "cli_command":
            flags = ", ".join("`" + flag + "`" for flag in entry["source_authority_flags"]) or "See argument contract; inspection is not verification"
            lines.append(f"| `{entry['value']}` | {flags} | legacy |")
    lines += ["", "## Studio endpoint index", "", "| Method | Path | Handler |", "| --- | --- | --- |"]
    for entry in inventory["entries"]:
        if entry["category"] == "studio_endpoint":
            lines.append(f"| {entry['method']} | `{entry['value']}` | `{entry['handler']}` |")
    lines += ["", "## Reproduction", "", "```sh", "python3 tools/migration_inventory.py", "python3 tools/migration_inventory.py --check", "PYTHONPATH=src python3 -m unittest discover -s tests -p test_migration_inventory.py", "```", "",
              "`--output PATH` selects the JSON destination and `--markdown PATH` selects this readable index. `--check` compares both generated files without writing and fails for missing or stale content. No timestamps or host paths enter the output. CI should run `--check` before accepting inventory-dependent work.", ""]
    return "\n".join(lines)


def inventory_text(inventory):
    """One JSON entry per line keeps the complete ledger compact and diffable."""
    parts = []
    for key, value in sorted(inventory.items()):
        if isinstance(value, list) and key == "entries":
            encoded = "[\n" + ",\n".join("    " + json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for item in value) + "\n  ]"
        elif isinstance(value, dict):
            encoded = "{\n" + ",\n".join("    " + json.dumps(name) + ":" + json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for name, item in sorted(value.items())) + "\n  }"
        else:
            encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        parts.append("  " + json.dumps(key) + ": " + encoded)
    return "{\n" + ",\n".join(parts) + "\n}\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        inventory = build_inventory(args.root)
        outputs = {args.output or args.root / "protocol/migration-inventory.json": inventory_text(inventory),
                   args.markdown or args.root / "docs/migration-coverage.md": markdown(inventory)}
        stale = []
        for path, content in outputs.items():
            if args.check:
                if not path.is_file() or path.read_text(encoding="utf-8") != content:
                    stale.append(str(path))
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
        if stale:
            raise InventoryError("Stale or missing migration inventory: " + ", ".join(stale))
        print(f"Migration inventory {'checked' if args.check else 'written'}: {len(inventory['entries'])} entries")
        return 0
    except (InventoryError, OSError, SyntaxError, TypeError, KeyError) as exc:
        print(f"migration inventory: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
