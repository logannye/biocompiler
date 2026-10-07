"""Static coverage-census controls: never import policy or execute a native tool."""
from __future__ import annotations

import ast
import copy
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.check_policy_semantic_coverage import (
    CoverageError, LEDGER, MODEL, ROOT, SOURCE_ROOT, STAGES, discover, main, read_ledger, syntax, validate,
)


class SyntaxNormalizationTests(unittest.TestCase):
    def test_call_empty_fields_and_optional_defaults_have_exact_portable_shape(self):
        # 3.11/3.12 ast.dump prints keywords=[]; 3.14 omits that same field.
        node = ast.parse('TypeSpec("event")', mode='eval').body
        expected = ['Call', [
            ['args', ['list', [['Constant', [['kind', ['none']], ['value', ['str', 'event']]]]]]],
            ['func', ['Name', [['ctx', ['Load', []]], ['id', ['str', 'TypeSpec']]]]],
            ['keywords', ['list', []]],
        ]]
        with patch('ast.dump', side_effect=AssertionError('Display formatting is not syntax authority')):
            self.assertEqual(json.loads(syntax(node)), expected)
        self.assertNotEqual(syntax(node), syntax(ast.parse('TypeSpec("event", unit=None)', mode='eval').body))
        self.assertNotEqual(syntax(node), syntax(ast.parse('TypeSpec()', mode='eval').body))

    def test_version_added_empty_generic_fields_normalize_without_hiding_values(self):
        for source in ('def f(): pass', 'async def f(): pass', 'class C: pass'):
            with self.subTest(source=source):
                absent = ast.parse(source).body[0]
                absent._fields = tuple(key for key in absent._fields if key != 'type_params')
                if hasattr(absent, 'type_params'):
                    delattr(absent, 'type_params')
                explicit = copy.deepcopy(absent)
                explicit._fields += ('type_params',)
                explicit.type_params = []
                self.assertEqual(syntax(absent), syntax(explicit))
                explicit.type_params = [ast.Name(id='T', ctx=ast.Load())]
                self.assertNotEqual(syntax(absent), syntax(explicit))
        for name in ('TypeVar', 'ParamSpec', 'TypeVarTuple'):
            # Construct both schema shapes even on interpreters predating them.
            node_type = type(name, (ast.AST,), {'_fields': ('name',)})
            absent = node_type(name='T')
            explicit = node_type(name='T')
            explicit._fields = ('name', 'default_value')
            explicit.default_value = None
            self.assertEqual(syntax(absent), syntax(explicit))
            explicit.default_value = ast.Name(id='int', ctx=ast.Load())
            self.assertNotEqual(syntax(absent), syntax(explicit))

    def test_scalar_types_empty_containers_and_none_default_slots_stay_distinct(self):
        sources = ('False', '0', '0.0', '""', 'b""', 'None', '()', '[]', '{}', '...', '0j')
        self.assertEqual(len({syntax(ast.parse(source, mode='eval').body) for source in sources}), len(sources))
        # kw_defaults=[None] means a required keyword, unlike Constant(None).
        required = ast.parse('def f(*, option): pass').body[0]
        defaulted = ast.parse('def f(*, option=None): pass').body[0]
        self.assertNotEqual(syntax(required), syntax(defaulted))

    def test_signature_default_operator_and_future_field_changes_remain_visible(self):
        original = ast.parse('def f(value: int = 0): return value + 1').body[0]
        for source in ('def f(value: str = 0): return value + 1',
                       'def f(value: int = 1): return value + 1',
                       'def f(value: int = 0): return value - 1',
                       'def f(value: int = 0, /): return value + 1'):
            with self.subTest(source=source):
                self.assertNotEqual(syntax(original), syntax(ast.parse(source).body[0]))
        changed = copy.deepcopy(original)
        changed._fields += ('future_semantic_field',)
        changed.future_semantic_field = []
        self.assertNotEqual(syntax(original), syntax(changed))


class PolicySemanticCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = read_ledger(ROOT / LEDGER)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        shutil.copytree(ROOT / SOURCE_ROOT, self.root / SOURCE_ROOT)
        for ref in self.ledger['references'].values():
            source = ROOT / ref['path']
            destination = self.root / ref['path']
            if not destination.exists():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
        destination = self.root / LEDGER
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / LEDGER, destination)

    def source_edit(self, before, after, path=MODEL):
        destination = self.root / path
        original = destination.read_text(encoding='utf-8')
        self.assertIn(before, original)
        destination.write_text(original.replace(before, after, 1), encoding='utf-8')

    def test_current_inventory_retains_scope_and_every_stage(self):
        report = validate(self.root, self.ledger)
        self.assertEqual(report['status'], 'inventory_current')
        self.assertEqual(report['semantic_acceptance'], 'not_established')
        self.assertEqual(report['counts'], {'alias': 2, 'alternative': 18, 'argument': 3,
                         'constant': 5, 'field': 306, 'literal': 199, 'operator': 33, 'record': 46})
        self.assertEqual(report['total_distinctions'], 612)
        self.assertEqual(report['without_dedicated_witnesses'], 612)
        self.assertEqual(set(report['stage_counts']), set(STAGES))
        for stage in ('implementation', 'material', 'export'):
            self.assertEqual(report['stage_counts'][stage], {'unsupported': 612})
        self.assertIn('contextual_rule_matrix', {gap['id'] for gap in report['known_gaps']})
        by_id = {row['id']: row for row in self.ledger['entries']}
        for identity in ('record:CompilationSubmission', 'field:Deployment.delivery',
                         'field:StateStore.capacity', 'operator:Expr.op="integrate"',
                         'literal:Effect.event.outcome="ceased"', 'literal:Message.event.phase="expired"',
                         'alternative:Declaration.SpatialScope', 'alternative:Document.BuildRequest'):
            self.assertIn(identity, by_id)

    def test_unsupported_authoring_is_not_promoted_to_execution(self):
        entries = {row['id']: row for row in self.ledger['entries']}
        for identity in ('operator:Expr.op="forall"', 'operator:Expr.op="integrate"',
                         'literal:Clock.basis="observation"', 'literal:StateStore.capacity="unbounded_requested"',
                         'literal:Effect.event.outcome="ceased"', 'record:Channel', 'record:SpatialScope'):
            disposition = self.ledger['dispositions'][entries[identity]['disposition']]
            with self.subTest(identity=identity):
                self.assertEqual(disposition['stages']['authorable'], 'supported')
                self.assertEqual(disposition['stages']['operational'], 'unsupported')
        target = self.ledger['dispositions'][entries['field:Deployment.delivery']['disposition']]
        self.assertEqual(target['stages']['operational'], 'unassessed')

    def test_discovery_never_imports_or_executes_the_policy_package(self):
        before = {name for name in sys.modules if name.startswith('biocompiler')}
        init = self.root / SOURCE_ROOT / '__init__.py'
        init.write_text('raise RuntimeError("Policy must not be imported")\n', encoding='utf-8')
        with (self.root / MODEL).open('a', encoding='utf-8') as handle:
            handle.write('\nraise RuntimeError("Model must not execute")\n')
        self.assertEqual(len(discover(self.root)), 612)
        self.assertEqual(before, {name for name in sys.modules if name.startswith('biocompiler')})

    def test_new_record_in_model_requires_classification(self):
        with (self.root / MODEL).open('a', encoding='utf-8') as handle:
            handle.write('\n@dataclass(frozen=True)\nclass NewPolicyRecord(Record):\n    new_field: str\n')
        with self.assertRaisesRegex(CoverageError, 'missing=.*NewPolicyRecord'):
            validate(self.root, self.ledger)

    def test_new_record_in_another_source_file_cannot_escape_census(self):
        (self.root / SOURCE_ROOT / 'new_records.py').write_text(
            'from .model import Record\nclass NewPolicyRecord(Record):\n    meaning: str\n', encoding='utf-8')
        with self.assertRaisesRegex(CoverageError, 'missing=.*NewPolicyRecord'):
            validate(self.root, self.ledger)

    def test_subclass_of_an_existing_record_is_also_discovered(self):
        (self.root / SOURCE_ROOT / 'new_records.py').write_text(
            'from .model import Role\nclass ExtendedRole(Role):\n    meaning: str\n', encoding='utf-8')
        with self.assertRaisesRegex(CoverageError, 'missing=.*ExtendedRole'):
            validate(self.root, self.ledger)

    def test_record_import_aliases_do_not_hide_new_records(self):
        (self.root / SOURCE_ROOT / 'new_records.py').write_text(
            'from .model import Role as Parent\nAlias = Parent\nclass ExtendedRole(Alias):\n    meaning: str\n', encoding='utf-8')
        with self.assertRaisesRegex(CoverageError, 'missing=.*ExtendedRole'):
            validate(self.root, self.ledger)

    def test_new_field_is_not_covered_by_existing_record_disposition(self):
        self.source_edit('class Clock(Record):', 'class Clock(Record):\n    hidden_clock: str = "unclassified"')
        with self.assertRaisesRegex(CoverageError, 'missing=.*Clock.hidden_clock'):
            validate(self.root, self.ledger)

    def test_new_operator_is_not_covered_by_existing_expression_disposition(self):
        self.source_edit('"message_event", "call", "integrate"]', '"message_event", "call", "integrate", "new_operator"]')
        with self.assertRaisesRegex(CoverageError, 'missing=.*new_operator'):
            validate(self.root, self.ledger)

    def test_nested_literal_enum_and_method_phase_are_individually_counted(self):
        self.source_edit('Literal["missing", "stale", "invalid", "conflicting"]',
                         'Literal["missing", "stale", "invalid", "conflicting", "new_invalidity"]')
        self.source_edit('"cancel_requested", "cancel_acknowledged", "ceased"]',
                         '"cancel_requested", "cancel_acknowledged", "ceased", "new_outcome"]')
        with self.assertRaises(CoverageError) as caught:
            validate(self.root, self.ledger)
        self.assertIn('Observation.invalidity', str(caught.exception))
        self.assertIn('Effect.event.outcome', str(caught.exception))
        self.assertIn('new_invalidity', str(caught.exception))
        self.assertIn('new_outcome', str(caught.exception))

    def test_new_enum_class_members_are_not_silently_ignored(self):
        (self.root / SOURCE_ROOT / 'new_records.py').write_text(
            'from enum import Enum\nclass PolicyMode(Enum):\n    NEW = "new"\n', encoding='utf-8')
        with self.assertRaisesRegex(CoverageError, 'missing=.*PolicyMode'):
            validate(self.root, self.ledger)

    def test_aliased_literal_and_annotated_enum_members_are_discovered(self):
        (self.root / SOURCE_ROOT / 'new_records.py').write_text(
            'from enum import Enum as Modes\nfrom typing import Literal as Choice\n'
            'from .model import Record as Base\nclass PolicyMode(Modes):\n    NEW: str = "new"\n'
            'class NewPolicyRecord(Base):\n    mode: Choice["new", "old"]\n', encoding='utf-8')
        ids = {entry['id'] for entry in discover(self.root)}
        self.assertIn('enum_member:PolicyMode.NEW', ids)
        self.assertIn('literal:NewPolicyRecord.mode="new"', ids)

    def test_alias_and_constant_changes_invalidate_review(self):
        self.source_edit('Document: TypeAlias = PolicyDraft | PolicyProgram | BuildRequest',
                         'Document: TypeAlias = PolicyDraft | PolicyProgram | BuildRequest | BackendCapabilities')
        with self.assertRaisesRegex(CoverageError, 'missing=.*alternative:Document.BackendCapabilities'):
            validate(self.root, self.ledger)
        self.source_edit(' | BuildRequest | BackendCapabilities', ' | BuildRequest')
        self.source_edit('TRUTH = TypeSpec("truth")', 'TRUTH = TypeSpec("text")')
        with self.assertRaisesRegex(CoverageError, 'changed.*constant:TRUTH'):
            validate(self.root, self.ledger)

    def test_annotation_default_and_record_mutability_changes_require_review(self):
        original = (self.root / MODEL).read_text(encoding='utf-8')
        for before, after, identity in (
            ('column: int = 0', 'column: str = "0"', 'field:SourceSpan.column'),
            ('column: int = 0', 'column: int = 1', 'field:SourceSpan.column'),
            ('@dataclass(frozen=True)\nclass Role', '@dataclass(frozen=False)\nclass Role', 'record:Role'),
        ):
            with self.subTest(identity=identity):
                (self.root / MODEL).write_text(original, encoding='utf-8')
                self.source_edit(before, after)
                with self.assertRaisesRegex(CoverageError, 'changed.*' + identity):
                    validate(self.root, self.ledger)

    def test_comments_and_line_numbers_do_not_create_semantic_drift(self):
        self.source_edit('class Role(Record):', '# New comment and shifted lines\nclass Role(Record):')
        self.assertEqual(validate(self.root, self.ledger)['status'], 'inventory_current')

    def test_missing_duplicate_obsolete_and_unclassified_rows_fail(self):
        for mutation, message in (
            (lambda data: data['entries'].pop(), 'inventory differs'),
            (lambda data: data['entries'].append(copy.deepcopy(data['entries'][0])), 'Duplicate'),
            (lambda data: data['entries'][0].update(id='alias:Unknown'), 'inventory differs'),
            (lambda data: data['entries'][0].update(disposition='invented'), 'Unclassified'),
        ):
            with self.subTest(message=message):
                data = copy.deepcopy(self.ledger)
                mutation(data)
                with self.assertRaisesRegex(CoverageError, message):
                    validate(self.root, data)

    def test_source_scope_stages_and_contextual_limits_cannot_be_dropped(self):
        for mutation, message in (
            (lambda data: data.update(source_roots=[MODEL]), 'scope cannot be narrowed'),
            (lambda data: data['stages'].pop(), 'retain every stage'),
            (lambda data: data['dispositions']['operational_contextual'].update(condition=''), 'contextual boundary'),
            (lambda data: data['dispositions']['operational_contextual']['stages'].update(material='accepted'), 'Unknown stage'),
        ):
            with self.subTest(message=message):
                data = copy.deepcopy(self.ledger)
                mutation(data)
                with self.assertRaisesRegex(CoverageError, message):
                    validate(self.root, data)

    def test_evidence_references_require_real_symbols_and_correct_polarity(self):
        for mutation, message in (
            (lambda data: data['references']['wire_positive']['anchor'].update(symbol='Invented.test'), 'Missing Python evidence'),
            (lambda data: data['references']['native_rejection']['anchor'].update(text='invented native assertion'), 'Missing evidence marker'),
            (lambda data: data['dispositions']['source_representation']['witnesses'].update(rejection=['wire_positive']), 'Wrong rejection'),
            (lambda data: data['dispositions']['source_representation']['owners'].update(native=[]), 'Missing owner'),
            (lambda data: data['known_gaps'].pop(0), 'dedicated evidence'),
        ):
            with self.subTest(message=message):
                data = copy.deepcopy(self.ledger)
                mutation(data)
                with self.assertRaisesRegex(CoverageError, message):
                    validate(self.root, data)

    def test_evidence_cannot_escape_repository(self):
        data = copy.deepcopy(self.ledger)
        data['references']['wire_positive']['path'] = '../other.py'
        with self.assertRaisesRegex(CoverageError, 'repository-relative'):
            validate(self.root, data)

    def test_ledger_duplicate_keys_and_inexact_json_are_rejected(self):
        path = self.root / 'broken.json'
        for raw in ('{"a":1,"a":2}', '{"a":0.1}', '{"a":NaN}'):
            with self.subTest(raw=raw):
                path.write_text(raw, encoding='utf-8')
                with self.assertRaises(CoverageError):
                    read_ledger(path)

    def test_cli_has_a_precise_static_success_and_nonzero_drift(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(['--root', str(self.root)]), 0)
        self.assertIn('612 distinctions', output.getvalue())
        self.assertIn('Semantic acceptance not established', output.getvalue())
        self.source_edit('column: int = 0', 'column: int = 1')
        error = io.StringIO()
        with redirect_stderr(error):
            self.assertEqual(main(['--root', str(self.root)]), 1)
        self.assertIn('field:SourceSpan.column', error.getvalue())


if __name__ == '__main__':
    unittest.main()
