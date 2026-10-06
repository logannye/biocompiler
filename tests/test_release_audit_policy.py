"""Exact source-body and imported dependency correspondence for policy adapters."""
from __future__ import annotations
import ast
import builtins
import copy
import hashlib
import importlib
import json
from pathlib import Path
import symtable
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))


def run_controls():
    if not __debug__:
        raise RuntimeError('Literal audit controls require enabled assertions')
    SPECS = [
        ('audit_source', 'check_policy_core', 'compare_receipts'),
        ('audit_operational', 'check_policy_operational', 'compare'),
        ('audit_implementation', 'check_policy_implementation', 'compare'),
        ('audit_material', 'check_policy_material', 'compare'),
        ('audit_consumer', 'check_policy_material_consumer', 'compare'),
    ]
    BUILTINS = set(vars(builtins))


    def sha(data):
        return hashlib.sha256(data).hexdigest()


    def global_reads(table):
        result = {s.get_name() for s in table.get_symbols() if s.is_referenced() and s.is_global()}
        for child in table.get_children():
            result.update(global_reads(child))
        return result


    def name_closure(source):
        root = symtable.symtable(source, 'policy_receipt_checks.py', 'exec')
        module_bindings = {s.get_name() for s in root.get_symbols()
                           if s.is_imported() or s.is_assigned() or s.is_namespace()}
        scopes = []

        def walk(table, ancestors, path):
            missing_global = sorted(s.get_name() for s in table.get_symbols()
                                    if s.is_referenced() and s.is_global()
                                    and s.get_name() not in module_bindings | BUILTINS)
            missing_free = sorted(s.get_name() for s in table.get_symbols()
                                  if s.is_referenced() and s.is_free()
                                  and not any(s.get_name() in {a.get_name() for a in parent.get_symbols()
                                                              if a.is_local() or a.is_parameter() or a.is_imported()}
                                              for parent in ancestors))
            assert not missing_global, (path, 'unresolved global', missing_global)
            assert not missing_free, (path, 'unresolved lexical free name', missing_free)
            scopes.append({'scope': path, 'globals': sorted(s.get_name() for s in table.get_symbols()
                                                           if s.is_referenced() and s.is_global()),
                           'free': sorted(s.get_name() for s in table.get_symbols()
                                          if s.is_referenced() and s.is_free())})
            for ordinal, child in enumerate(table.get_children()):
                walk(child, [table, *ancestors], path + '/' + child.get_name() + ':' + str(ordinal))

        walk(root, [], 'module')
        return scopes


    def imported_bindings(statements):
        result = {}
        for node in statements:
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0 and all(alias.name != '*' for alias in node.names)
                module = importlib.import_module(node.module)
                for alias in node.names:
                    # getattr is intentional: it independently checks that each imported
                    # dependency actually exists, rather than merely accepting a spelling.
                    result[alias.asname or alias.name] = getattr(module, alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    result[alias.asname or alias.name.split('.')[0]] = importlib.import_module(alias.name)
        return result


    def reverse_adapter(node, original):
        restored = copy.deepcopy(node)
        assert isinstance(restored.body[0], ast.ImportFrom)
        restored.body.pop(0)
        restored.name = original.name
        assert restored.args.kwonlyargs[-1].arg == 'audited_identity'
        restored.args.kwonlyargs.pop()
        assert restored.args.kw_defaults.pop() is None

        class Restore(ast.NodeTransformer):
            def visit_Call(self, call):
                self.generic_visit(call)
                if (isinstance(call.func, ast.Name) and call.func.id == 'dict'
                        and len(call.args) == 1 and isinstance(call.args[0], ast.Name)
                        and call.args[0].id == 'audited_identity' and not call.keywords):
                    return ast.parse('core.source_identity()' if node.name == 'audit_consumer'
                                     else 'source_identity()', mode='eval').body
                if isinstance(call.func, ast.Name) and call.func.id == 'audit_material':
                    assert node.name == 'audit_consumer'
                    assert len(call.keywords) == 1 and call.keywords[0].arg == 'audited_identity'
                    call.func = ast.Attribute(value=ast.Name(id='material', ctx=ast.Load()), attr='compare', ctx=ast.Load())
                    call.keywords = []
                return call

        return Restore().visit(restored)


    def check(source):
        tree = ast.parse(source)
        scopes = name_closure(source)
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        assert set(functions) == {row[0] for row in SPECS}
        top = imported_bindings(tree.body)
        rows = []
        for name, module_name, original_name in SPECS:
            module = importlib.import_module(module_name)
            module_path = ROOT / 'tools' / (module_name + '.py')
            assert Path(module.__file__).resolve() == module_path.resolve()
            original_text = module_path.read_text()
            original = next(n for n in ast.parse(original_text).body
                            if isinstance(n, ast.FunctionDef) and n.name == original_name)
            original_table = next(t for t in symtable.symtable(original_text, str(module_path), 'exec').get_children()
                                  if t.get_name() == original_name)
            required = global_reads(original_table) - BUILTINS - {'source_identity'}
            available = {**top, **imported_bindings(functions[name].body)}
            for dependency in sorted(required):
                assert dependency in available, (name, 'missing original dependency', dependency)
                assert available[dependency] is vars(module)[dependency], (name, 'foreign dependency', dependency)
            assert ast.dump(reverse_adapter(functions[name], original), include_attributes=False) == ast.dump(original, include_attributes=False), name
            rows.append({'audit': name, 'original': str(module_path.relative_to(ROOT)) + ':' + original_name,
                         'original_source_sha256': sha(ast.get_source_segment(original_text, original).encode()),
                         'original_module_sha256': sha(module_path.read_bytes()),
                         'required_original_dependencies': sorted(required),
                         'all_imports_resolved_under_process_and_network_denial': True,
                         'dependency_objects_identical_to_original_module': True,
                         'reverse_adaptation_ast_equals_original': True})
        return scopes, rows


    source_path = ROOT / 'tools/release_audit_policy.py'
    source = source_path.read_text()
    scopes, rows = check(source)
    negative = []


    def rejects(label, candidate, operation=check):
        try:
            operation(candidate)
        except (AssertionError, AttributeError, ImportError):
            negative.append(label)
        else:
            raise AssertionError('Mutation accepted: ' + label)


    old = source.replace('EXPECTED_NAMES, ImportBoundary, Path, __file__', 'EXPECTED_NAMES, Path, __file__')
    rejects('original missing ImportBoundary in nested origins', old, name_closure)
    assert old.replace('EXPECTED_NAMES, Path, __file__', 'EXPECTED_NAMES, ImportBoundary, Path, __file__') == source
    for name, _, _ in SPECS:
        mutant = ast.parse(source)
        node = next(n for n in mutant.body if isinstance(n, ast.FunctionDef) and n.name == name)
        node.body.insert(1, ast.Expr(value=ast.Name(id='unbound_adapter_dependency', ctx=ast.Load())))
        rejects(name + ': unresolved direct global', ast.unparse(mutant), name_closure)
        # Every exact imported binding receives a nonexistent provider symbol while
        # retaining its local spelling. This catches missing imports and wrong aliases
        # even if lexical symbol-table closure alone would accept the spelling.
        imports = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name).body[0]
        for index, alias in enumerate(imports.names):
            mutant = ast.parse(source)
            node = next(n for n in mutant.body if isinstance(n, ast.FunctionDef) and n.name == name)
            node.body[0].names[index] = ast.alias(name='missing_dependency_for_selfcheck', asname=alias.asname or alias.name)
            rejects(name + ': missing provider export ' + alias.name, ast.unparse(mutant))

    result = {'schema': 'biocompiler.generated_policy_adapter_dependency_review.v1', 'status': 'pass',
              'scope': 'Recursive adapter name/import closure and exact original body restoration only; no receipt replay or final audit',
              'helper_sha256': sha(source_path.read_bytes()), 'checker_sha256': sha(Path(__file__).read_bytes()),
              'previous_helper_sha256': sha(old.encode()), 'rows': rows, 'recursive_scopes': scopes,
              'rejected_mutations': negative, 'native_execution': 'not_performed', 'final_audit': 'not_run'}
    return result


class ReleaseAuditPolicyTests(unittest.TestCase):
    def test_exact_five_bodies_and_dependency_closure(self):
        result = run_controls()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(len(result["rows"]), 5)
        self.assertEqual(len(result["rejected_mutations"]), 61)
