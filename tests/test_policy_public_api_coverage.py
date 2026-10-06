"""Inert census/lineage mutations; never import policy or start a backend."""
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

from tools import check_policy_public_api_coverage as c


class PolicyPublicApiCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = c.read_ledger(c.ROOT / c.LEDGER)

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.ledger = copy.deepcopy(self.original)
        paths = set(self.ledger['inventory']['files']) | {w['path'] for w in self.ledger['witnesses'].values()}
        paths |= {c.LEDGER, 'protocol/policy-semantic-coverage-v0.1.json'}
        for relative in paths:
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(c.ROOT / relative, target)

    def edit(self, path, before, after, *, repin_file=False):
        target = self.root / path
        source = target.read_text()
        self.assertIn(before, source)
        target.write_text(source.replace(before, after, 1))
        if repin_file:
            self.ledger['inventory']['files'][path] = c.digest(target.read_bytes())

    def test_exact_census_and_scoped_evidence(self):
        result = c.validate(self.root, self.ledger)
        self.assertEqual((result['files'], result['entries'], result['exports'], result['cli_commands'], result['native_operations']), (38, 700, 163, 17, 13))
        self.assertEqual(result['coverage'], {'compatibility_support': 6, 'dependency': 121,
            'independent_expansion': 28, 'shared_invariant': 448, 'source_only': 97})
        self.assertEqual(len(self.ledger['syntax_links']), 359)
        self.assertEqual(len(self.ledger['witnesses']), 90)
        self.assertEqual(result['status'], 'source_inventory_checked')
        self.assertEqual(result['runtime_protocol_scope'], c.RUNTIME_SCOPE)
        self.assertIn('not an exhaustive runtime-attribute census', result['runtime_protocol_scope'])
        self.assertIn('neither executed coverage', result['claim_scope'])
        self.assertEqual({r['id'].removeprefix('biocompiler.policy.') for r in self.ledger['inventory']['entries'] if r['scope'] == 'compatibility_support'}, c.SUPPORT)

    def test_discovery_is_inert_even_for_source_with_executable_statements(self):
        before = {key for key in sys.modules if key.startswith('biocompiler')}
        marker = self.root / 'must_not_exist'
        path = self.root / c.PACKAGE / '__init__.py'
        with path.open('a') as stream:
            stream.write('\nraise RuntimeError("Do not execute source")\n')
            stream.write(f'open({str(marker)!r}, "w").write("executed")\n')
        found = c.discover(self.root)
        self.assertEqual(len(found['entries']), 700)
        self.assertFalse(marker.exists())
        self.assertEqual(before, {key for key in sys.modules if key.startswith('biocompiler')})

    def test_file_census_rejects_new_module_even_with_repinned_ledger(self):
        path = c.PACKAGE + '/unreviewed.py'
        (self.root / path).write_text('def public_api(): return 1\n')
        self.ledger['inventory']['files'][path] = c.digest((self.root / path).read_bytes())
        with self.assertRaisesRegex(c.ApiCoverageError, 'file census differs'):
            c.validate(self.root, self.ledger)

    def test_body_and_default_drift_remain_after_file_digest_is_refreshed(self):
        path = c.PACKAGE + '/programs.py'
        self.edit(path, 'termination: Literal["contact_loss", "explicit_event", "contract"] = "contact_loss"',
                  'termination: Literal["contact_loss", "explicit_event", "contract"] = "explicit_event"', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'Source/API inventory drift'):
            c.validate(self.root, self.ledger)

    def test_same_signature_different_body_is_not_signature_coverage(self):
        path = c.PACKAGE + '/programs.py'
        self.edit(path, 'return self.add(m.Clock(self.qualified(identity), basis, resolution))',
                  'return self.add(m.Clock(self.qualified(identity), "logical", resolution))', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'Source/API inventory drift'):
            c.validate(self.root, self.ledger)

    def test_compatibility_alias_cannot_be_repointed_with_new_file_pin(self):
        self.edit(c.PACKAGE + '/inspection.py', 'summary = inspect', 'summary = graph', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'compatibility/display aliases differ'):
            c.validate(self.root, self.ledger)

    def test_root_export_same_name_wrong_owned_target_rejects(self):
        self.edit(c.PACKAGE + '/__init__.py', '    Role,', '    TypeSpec as Role,', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'export target/alias census differs'):
            c.validate(self.root, self.ledger)

    def test_imported_arbitrary_attribute_cannot_become_public_by_repinning(self):
        path = c.PACKAGE + '/__init__.py'
        self.edit(path, "    'Role',", "    'Path',", repin_file=True)
        with (self.root / path).open('a') as stream:
            stream.write('\nfrom pathlib import Path\n')
        self.ledger['inventory']['files'][path] = c.digest((self.root / path).read_bytes())
        with self.assertRaisesRegex(c.ApiCoverageError, 'outside the reviewed owned surface'):
            c.validate(self.root, self.ledger)

    def test_native_route_mutation_rejects_beyond_file_hash(self):
        self.edit('src/biocompiler/core_policy_operational.py',
                  'return self._call("execute-policy",', 'return self._call("check-policy-lowering",', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'Native operation route differs'):
            c.validate(self.root, self.ledger)

    def test_native_dropped_original_input_rejects_beyond_file_hash(self):
        self.edit('src/biocompiler/core_policy_operational.py',
                  '"candidate": candidate, "timeline": timeline}', '"candidate": candidate}', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'original-input inventory differs'):
            c.validate(self.root, self.ledger)

    def test_cli_command_cannot_be_silently_renamed(self):
        self.edit(c.PACKAGE + '/cli.py', '("export-schema", "Export the versioned authoring document schema."),',
                  '("export-python", "Export the versioned authoring document schema."),', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'CLI route census differs'):
            c.validate(self.root, self.ledger)

    def test_portable_ast_helper_is_an_explicit_source_dependency(self):
        path = 'tools/check_policy_semantic_coverage.py'
        self.assertIn(path, self.ledger['inventory']['files'])
        self.edit(path, '"FunctionDef": {"type_params": []}', '"FunctionDef": {"type_params": ["unreviewed"]}')
        with self.assertRaisesRegex(c.ApiCoverageError, 'Source/API inventory drift'):
            c.validate(self.root, self.ledger)

    def test_new_builder_method_cannot_replace_old_same_sized_inventory(self):
        self.edit(c.PACKAGE + '/programs.py', 'def qualified(self, identity: str)', 'def quietly_rename(self, identity: str)', repin_file=True)
        with self.assertRaisesRegex(c.ApiCoverageError, 'builder method census differs'):
            c.validate(self.root, self.ledger)

    def test_missing_symbol_and_new_schema_fields_are_not_hash_coverage(self):
        self.ledger['inventory']['entries'].pop()
        with self.assertRaisesRegex(c.ApiCoverageError, 'Source/API inventory drift'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        self.ledger['accepted'] = True
        with self.assertRaisesRegex(c.ApiCoverageError, 'unexpected or missing fields'):
            c.validate(self.root, self.ledger)

    def test_source_only_schema_cannot_claim_runtime_acceptance(self):
        self.ledger['claim_scope'] = 'Every exposed API is runtime verified.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'acceptance claim'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        self.ledger['coverage']['biocompiler.policy.model.declaration_ref']['status'] = 'source_only'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Compatibility support'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        self.ledger['runtime_protocol_scope'] = 'All Python runtime methods are inventoried and symbolically evaluated.'
        with self.assertRaisesRegex(c.ApiCoverageError, 'runtime protocol scope must remain explicit'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        self.ledger['known_gaps'] = []
        with self.assertRaisesRegex(c.ApiCoverageError, 'limitations must remain'):
            c.validate(self.root, self.ledger)

    def test_dropped_witness_is_distinct_from_malformed_witness(self):
        del self.ledger['witnesses']['builder.holes']
        with self.assertRaisesRegex(c.ApiCoverageError, 'Dropped required expansion witness'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        self.ledger['witnesses']['builder.holes']['role'] = 'passing_runtime_proof'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Malformed witness distinction'):
            c.validate(self.root, self.ledger)

    def test_repinned_expansion_witness_cannot_point_to_unrelated_test(self):
        wrong = self.ledger['witnesses']['builder.holes']
        source = self.ledger['witnesses']['builder.freeze']
        wrong['symbol'], wrong['syntax_sha256'] = source['symbol'], source['syntax_sha256']
        with self.assertRaisesRegex(c.ApiCoverageError, 'Repinned expansion witness points to the wrong test'):
            c.validate(self.root, self.ledger)

    def test_shared_witness_cannot_be_repointed_with_all_current_source_pins(self):
        row = self.ledger['witnesses']['shared.immutable_snapshots.1']
        wrong = self.ledger['witnesses']['builder.freeze']
        for name in ('path', 'symbol', 'file_sha256', 'syntax_sha256'):
            row[name] = wrong[name]
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)

    def test_source_only_row_cannot_gain_unrelated_shared_evidence(self):
        row = self.ledger['coverage']['biocompiler.policy.material.replay']
        self.assertEqual(row['status'], 'source_only')
        row.update(status='shared_invariant', witnesses=['builder.holes'], scope='Invented full replay coverage')
        with self.assertRaisesRegex(c.ApiCoverageError, 'Reviewed API witness/coverage metadata differs'):
            c.validate(self.root, self.ledger)

    def test_witness_body_and_file_must_both_match(self):
        path = 'tests/test_policy_builders.py'
        self.edit(path, 'self.assertEqual(builder.snapshot().holes, ())', 'self.assertEqual(builder.snapshot().holes, ())  # review change')
        with self.assertRaisesRegex(c.ApiCoverageError, 'Stale witness source'):
            c.validate(self.root, self.ledger)
        for witness in self.ledger['witnesses'].values():
            if witness['path'] == path:
                witness['file_sha256'] = c.digest((self.root / path).read_bytes())
        # A comment-only change preserves every AST; a semantically changed test does not.
        c.validate(self.root, self.ledger)
        self.edit(path, 'self.assertEqual(builder.snapshot().holes, ())', 'self.assertEqual(builder.snapshot().holes, (slot,))')
        for witness in self.ledger['witnesses'].values():
            if witness['path'] == path:
                witness['file_sha256'] = c.digest((self.root / path).read_bytes())
        with self.assertRaisesRegex(c.ApiCoverageError, 'Stale witness source'):
            c.validate(self.root, self.ledger)

    def test_dropping_specific_expansion_link_cannot_hide_in_shared_status(self):
        row = self.ledger['coverage']['biocompiler.policy.programs.ProgramBuilder.resolve']
        row['status'] = 'shared_invariant'
        with self.assertRaisesRegex(c.ApiCoverageError, 'Missing independent builder expansion'):
            c.validate(self.root, self.ledger)
        self.ledger = copy.deepcopy(self.original)
        row = self.ledger['coverage']['biocompiler.policy.programs.ProgramBuilder.resolve']
        row['witnesses'] = ['builder.defaults']
        with self.assertRaisesRegex(c.ApiCoverageError, 'Missing independent builder expansion'):
            c.validate(self.root, self.ledger)

    def test_existing_syntax_field_links_cannot_be_dropped_or_forged(self):
        links = self.ledger['syntax_links']
        links['biocompiler.policy.model.Clock.basis'] = 'field:Clock.simultaneous'
        with self.assertRaisesRegex(c.ApiCoverageError, 'syntax-ledger links'):
            c.validate(self.root, self.ledger)

    def test_syntax_link_target_cannot_keep_id_and_change_source_owner(self):
        path = self.root / 'protocol/policy-semantic-coverage-v0.1.json'
        original = json.loads(path.read_text())
        row = next(row for row in original['entries'] if row['id'] == 'field:Clock.basis')
        row['source']['symbol'] = 'Clock.simultaneous'
        path.write_text(json.dumps(original))
        with self.assertRaisesRegex(c.ApiCoverageError, 'another source owner'):
            c.validate(self.root, self.ledger)

    def test_bounded_decoder_duplicate_numbers_depth_nodes_and_paths(self):
        target = self.root / 'bad.json'
        for raw in ('{"a":1,"a":2}', '{"a":1.25}', '{"a":NaN}', '[' * 80 + '0' + ']' * 80):
            with self.subTest(raw=raw[:30]):
                target.write_text(raw)
                with self.assertRaises(c.ApiCoverageError):
                    c.read_ledger(target)
        with self.assertRaisesRegex(c.ApiCoverageError, 'array limit'):
            c.bounded([0] * 4097)
        with patch.object(c, 'MAX_NODES', 4), self.assertRaisesRegex(c.ApiCoverageError, 'node limit'):
            c.bounded({'a': [1, 2, 3]})
        with patch.object(c, 'MAX_LEDGER', 4):
            target.write_text('{"valid":true}')
            with self.assertRaisesRegex(c.ApiCoverageError, 'byte limit'):
                c.read_ledger(target)
        for path in ('../outside', '/absolute', ''):
            with self.subTest(path=path), self.assertRaises(c.ApiCoverageError):
                c.read_bytes(self.root, path)
        target = self.root / 'link.py'
        target.symlink_to(c.ROOT / 'src/biocompiler/policy/model.py')
        with self.assertRaisesRegex(c.ApiCoverageError, 'escaping'):
            c.read_bytes(self.root, 'link.py')

    def test_cli_has_no_regeneration_or_acceptance_switch(self):
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(c.main(['--root', str(self.root)]), 0)
        self.assertEqual(json.loads(output.getvalue())['status'], 'source_inventory_checked')
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            c.main(['--regenerate'])
        self.edit(c.PACKAGE + '/logic.py', 'def literal(value:', 'def literal(renamed:')
        with redirect_stderr(io.StringIO()) as error:
            self.assertEqual(c.main(['--root', str(self.root)]), 1)
        self.assertIn('inventory drift', error.getvalue())


if __name__ == '__main__':
    unittest.main()
