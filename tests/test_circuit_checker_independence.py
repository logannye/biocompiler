"""Audit circuit checker dependency paths without importing package façades.

The public package eagerly reexports both producers and checkers. Those imports
are not checker oracle dependencies. This audit instead follows explicit module
imports, including function-local imports, from the checker implementations.
"""

import ast
from dataclasses import dataclass
from importlib.util import resolve_name
from pathlib import Path
import unittest


SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src"
CHECKERS = (
    "biocompiler.verification.circuit_review",
    "biocompiler.verification.circuit_sources",
    "biocompiler.verification.circuit_bindings",
    "biocompiler.verification.circuit_evidence",
    "biocompiler.verification.circuit_construction",
    "biocompiler.verification.circuit_transitions",
    "biocompiler.verification.circuit_payloads",
)
DECLARATION_IMPORTS = {
    "biocompiler.compiler.request": {"BuildRequest", "_strict_import"},
    "biocompiler.compiler.acceptance": {"HumanAcceptanceRequest"},
    "biocompiler.compiler.deployment": {"HumanDeploymentRequest"},
    "biocompiler.compiler.human_behavior": {"HumanBehaviorRequest"},
}
FORBIDDEN_PREFIXES = (
    "biocompiler.backends",
    "biocompiler.frontend",
    "biocompiler.models",
    "biocompiler.synthesis",
    "biocompiler.studio",
)


@dataclass(frozen=True)
class ImportEdge:
    caller: str
    target: str
    names: tuple[str, ...]
    scope: tuple[str, ...]


def _module_path(module):
    return SOURCE_ROOT.joinpath(*module.split(".")).with_suffix(".py")


def _imports(module, text):
    """Resolve explicit child-module imports without executing any module."""
    edges = []
    problems = []

    def visit(node, scope=()):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            scope = (*scope, node.name)
        if isinstance(node, ast.Import):
            edges.extend(
                ImportEdge(module, item.name, (), scope) for item in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            target = node.module or ""
            if node.level:
                target = resolve_name(
                    "." * node.level + target, module.rpartition(".")[0]
                )
            if target.startswith("biocompiler"):
                if _module_path(target).is_file():
                    edges.append(
                        ImportEdge(
                            module,
                            target,
                            tuple(item.name for item in node.names),
                            scope,
                        )
                    )
                else:
                    for item in node.names:
                        child = target + "." + item.name
                        if _module_path(child).is_file() or child.startswith(
                            FORBIDDEN_PREFIXES
                        ):
                            edges.append(ImportEdge(module, child, (), scope))
                        else:
                            problems.append(
                                f"{module}: unresolved package reexport {child}"
                            )
        elif isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Name) and node.func.id == "__import__") or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "import_module"
            ):
                problems.append(
                    f"{module}: dynamic import requires an explicit dependency audit"
                )
        for child in ast.iter_child_nodes(node):
            visit(child, scope)

    visit(ast.parse(text))
    return edges, problems


def _permitted_compiler_edge(edge):
    if edge.target in DECLARATION_IMPORTS:
        return bool(edge.names) and set(edge.names) <= DECLARATION_IMPORTS[edge.target]
    # This legacy constructor is in the shared request declaration file, but no
    # circuit checker constructs RealizationRequest. Its exact import is an
    # independent lowering verifier, not a construction producer. Traverse the
    # verifier module too, so a new dependency there still fails the audit.
    return (
        edge.caller == "biocompiler.compiler.request"
        and edge.scope == ("RealizationRequest", "__post_init__")
        and edge.target == "biocompiler.compiler.behavior"
        and edge.names == ("verify_lowering",)
    )


def _audit(entrypoints, replacements=None):
    replacements = replacements or {}
    visited = set()
    pending = list(entrypoints)
    problems = []
    while pending:
        module = pending.pop()
        if module in visited:
            continue
        visited.add(module)
        path = _module_path(module)
        if not path.is_file():
            problems.append(f"Missing checker dependency source: {module}")
            continue
        text = replacements.get(module, path.read_text(encoding="utf-8"))
        edges, invalid = _imports(module, text)
        problems.extend(invalid)
        for edge in edges:
            if not edge.target.startswith("biocompiler"):
                continue
            forbidden = edge.target.startswith(FORBIDDEN_PREFIXES) or (
                edge.target.startswith("biocompiler.compiler")
                and not _permitted_compiler_edge(edge)
            )
            if forbidden:
                problems.append(
                    f"Forbidden oracle dependency: {edge.caller} -> {edge.target}"
                )
            elif edge.target == "biocompiler":
                problems.append(
                    f"Checker imports public producer/checker façade: {edge.caller}"
                )
            else:
                pending.append(edge.target)
    return problems, visited


class CircuitCheckerIndependenceTests(unittest.TestCase):
    def test_transitive_circuit_checker_dependencies_have_no_producer_oracles(self):
        for entrypoint in CHECKERS:
            with self.subTest(checker=entrypoint):
                problems, visited = _audit((entrypoint,))
                self.assertEqual(problems, [], "\n".join(problems))
                self.assertIn("biocompiler.ir.serialization", visited)

    def test_audit_detects_backend_dependency_hidden_in_shared_ir(self):
        module = "biocompiler.ir.serialization"
        original = _module_path(module).read_text(encoding="utf-8")
        for injected in (
            "from biocompiler.backends.circuit_construction import construct_circuit_candidate",
            "def hidden():\n    import biocompiler.backends.circuit_construction as producer",
            "from biocompiler import backends",
        ):
            with self.subTest(import_form=injected):
                problems, _ = _audit(CHECKERS, {module: original + "\n" + injected})
                self.assertTrue(
                    any("Forbidden oracle dependency" in item for item in problems),
                    problems,
                )

    def test_declaration_exception_cannot_expand_to_compiler_or_generator(self):
        module = "biocompiler.ir.circuit_profile"
        original = _module_path(module).read_text(encoding="utf-8")
        for injected in (
            "from biocompiler.compiler.circuit_construction import build_circuit_construction",
            "from biocompiler.compiler.behavior import lower_intent",
            "from biocompiler.compiler.request import RealizationRequest",
        ):
            with self.subTest(import_form=injected):
                problems, _ = _audit(CHECKERS, {module: original + "\n" + injected})
                self.assertTrue(
                    any("Forbidden oracle dependency" in item for item in problems),
                    problems,
                )

    def test_public_facade_and_dynamic_imports_cannot_hide_oracles(self):
        module = CHECKERS[0]
        original = _module_path(module).read_text(encoding="utf-8")
        for injected in (
            "import biocompiler",
            "from biocompiler import build_circuit_construction",
            "__import__('biocompiler.backends.circuit_construction')",
            "import importlib\nimportlib.import_module('biocompiler.backends.circuit_construction')",
        ):
            with self.subTest(import_form=injected):
                problems, _ = _audit((module,), {module: original + "\n" + injected})
                self.assertTrue(problems)


if __name__ == "__main__":
    unittest.main()
