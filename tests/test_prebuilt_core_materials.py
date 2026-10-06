"""Synthetic material byte fixtures are never compiled, linked or executed."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


inputs = load('materials_gmp_tests', ROOT / 'tests/test_static_gmp_configuration.py')
with patch.dict(sys.modules, {'prepare_static_gmp': inputs.DRAFT}):
    materials = load('prebuilt_materials_draft', ROOT / 'tools/prebuilt_core_materials.py')


class MaterialsTests(unittest.TestCase):
    def setUp(self):
        self.input = inputs.StaticGmpConfigurationTests()
        self.input.setUp()
        self.addCleanup(self.input.doCleanups)
        receipt, pc = self.input.complete()
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.files = {}
        self.components = {name: {'version': 'fixture-1', 'linked': name != 'dune'}
                           for name in sorted(materials.MINIMUM)}
        self.components['gmp']['version'] = '6.3.0'
        for name in self.components:
            for role in ('source', 'license', 'build-recipe', 'relink-input'):
                self.add(name + '/' + role, name, role, (name + ':' + role + '\n').encode())
        self.add('build/lock', 'biocompiler', 'dependency-lock', b'actual synthetic dependency lock\n')
        self.add('build/relink', 'biocompiler', 'build-recipe', b'never execute this fixture\n')
        self.add('gmp/input.json', 'gmp', 'build-receipt', materials.canonical(receipt))
        self.add('gmp/gmp.pc', 'gmp', 'pkg-config', pc)
        self.add('gmp/libgmp.a', 'gmp', 'link-input', self.input.archive.read_bytes())
        self.add('gmp/gmp.h', 'gmp', 'header', self.input.header.read_bytes())
        self.expected = {'source_revision': '1' * 40, 'tested_revision': '2' * 40, 'run_id': '123',
            'native_platform': 'linux-x86_64', 'components': self.components,
            'static_gmp_receipt': materials.digest(materials.canonical(receipt)),
            'binaries': {name: {'sha256': value * 64, 'size': 64} for name, value in
                (('biocompiler-core', '3'), ('biocompiler-verify', '4'))}}
        self.document = {'schema_version': materials.SCHEMA, **deepcopy(self.expected),
            'files': self.files, 'dependency_lock': 'build/lock',
            'recipes': {'build': 'biocompiler/build-recipe', 'relink': 'build/relink'},
            'static_gmp': {'receipt': 'gmp/input.json', 'pkg_config': 'gmp/gmp.pc',
                'archive': 'gmp/libgmp.a', 'header': 'gmp/gmp.h'}}
        self.lock = materials.digest((self.root / 'build/lock').read_bytes())

    def add(self, name, component, role, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        self.files[name] = {'component': component, 'role': role, **materials.digest(raw)}

    def verify(self, document=None, **kw):
        document = self.document if document is None else document
        return materials.verify(self.root, document, self.expected, dependency_lock=self.lock,
            manifest_sha256=kw.get('manifest_sha256', materials.digest(materials.canonical(document))['sha256']))

    def test_complete_retained_closure_binds_source_run_inputs_and_final_bytes(self):
        with patch.object(inputs.DRAFT.subprocess, 'run', side_effect=AssertionError('unexpected execution')):
            evidence = self.verify()
        self.assertEqual(set(evidence['files']), set(self.files))
        self.assertEqual(evidence['authority'], self.expected)
        self.assertIn('license review', evidence['scope'])

    def test_missing_source_license_relink_and_foreign_dependency_fail_after_rehash(self):
        for component, role in (('gmp', 'license'), ('ocaml', 'source'), ('biocompiler', 'relink-input')):
            changed = deepcopy(self.document)
            del changed['files'][component + '/' + role]
            with self.subTest(component=component), self.assertRaisesRegex(ValueError, 'lacks retained'):
                self.verify(changed)
        changed = deepcopy(self.document)
        changed['files']['gmp/source']['component'] = 'unreviewed'
        with self.assertRaisesRegex(ValueError, 'Unreviewed release material'):
            self.verify(changed)
        changed = deepcopy(self.document)
        changed['components']['gmp']['version'] = '7.0.0'
        with self.assertRaisesRegex(ValueError, 'independently supplied'):
            self.verify(changed)

    def test_changed_actual_input_and_repaired_receipt_cannot_change_external_authority(self):
        self.add('gmp/libgmp.a', 'gmp', 'link-input', b'!<arch>\n' + b'z' * 60)
        with self.assertRaisesRegex(ValueError, 'actual selected link input'):
            self.verify()
        path = self.root / 'gmp/input.json'
        import json
        receipt = json.loads(path.read_bytes())
        changed = materials.digest((self.root / 'gmp/libgmp.a').read_bytes())
        receipt['archive'].update(changed)
        receipt['resolution']['archive'].update(changed)
        self.add('gmp/input.json', 'gmp', 'build-receipt', materials.canonical(receipt))
        with self.assertRaisesRegex(ValueError, 'independently retained static GMP'):
            self.verify()

    def test_manifest_lock_or_extra_member_cannot_escape_exact_census(self):
        with self.assertRaisesRegex(ValueError, 'independently retained identity'):
            self.verify(manifest_sha256='0' * 64)
        self.add('build/lock', 'biocompiler', 'dependency-lock', b'changed lock\n')
        with self.assertRaisesRegex(ValueError, 'actual native dependency lock'):
            self.verify()
        (self.root / 'unexpected').write_bytes(b'extra')
        with self.assertRaisesRegex(ValueError, 'unclaimed release materials'):
            self.verify()

    def test_paths_symlinks_and_size_bound_cannot_hide_inputs(self):
        for path in ('../outside', '/absolute', 'a/../b', './source', 'a//b', 'a\\b'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                materials.logical(path)
        changed = deepcopy(self.document)
        changed['files']['gmp/source']['size'] = materials.MAX_FILE + 1
        with self.assertRaisesRegex(ValueError, 'byte identity'):
            self.verify(changed)
        target = self.root / 'gmp/source'
        target.unlink(); target.symlink_to(self.root / 'gmp/license')
        with self.assertRaisesRegex(ValueError, 'not a regular file'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
