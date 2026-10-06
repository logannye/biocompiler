"""Controls for the pure-Python installed authoring verifier itself."""
import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.check_policy_install import ImportBoundary, _read_json, run_bounded


class PolicyInstallToolTests(unittest.TestCase):
    def test_import_boundary_rejects_all_non_authoring_package_families(self):
        guard = ImportBoundary(Path('/'))
        for name in ('biocompiler.compiler', 'biocompiler.semantics',
                     'biocompiler.verification', 'biocompiler.core_pipeline_manager',
                     'biocompiler.cli', '_biocompiler_core'):
            with self.subTest(name=name), self.assertRaises(ImportError):
                guard.find_spec(name)
        for name in ('biocompiler', 'biocompiler.policy', 'biocompiler.policy.examples',
                     'biocompiler.entrypoint', 'biocompiler.__main__', 'json'):
            self.assertIsNone(guard.find_spec(name))
        with self.assertRaises(AssertionError):
            guard.origins()

    def test_origin_audit_rejects_already_loaded_forbidden_or_foreign_modules(self):
        forbidden = importlib.util.module_from_spec(importlib.machinery.ModuleSpec('biocompiler.compiler', loader=None))
        with patch.dict(sys.modules, {'biocompiler.compiler': forbidden}), self.assertRaises(AssertionError):
            ImportBoundary(Path('/')).origins()
        foreign = importlib.util.module_from_spec(importlib.machinery.ModuleSpec('biocompiler.policy.foreign', loader=None))
        foreign.__file__ = '/outside-install/foreign.py'
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(sys.modules, {'biocompiler.policy.foreign': foreign}), self.assertRaises(AssertionError):
                ImportBoundary(Path(directory)).origins()

    def test_cli_output_and_time_are_bounded(self):
        environment = dict(os.environ)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code, out, err = run_bounded([sys.executable, '-c', 'print("ok")'], cwd=root, env=environment)
            self.assertEqual((code, out, err), (0, b'ok\n', b''))
            with self.assertRaisesRegex(AssertionError, 'output bound'):
                run_bounded([sys.executable, '-c', 'print("x" * 65536)'], cwd=root, env=environment, maximum=32)
            with self.assertRaisesRegex(AssertionError, 'time bound'):
                run_bounded([sys.executable, '-c', 'import time; time.sleep(30)'], cwd=root, env=environment, timeout=0.05)

    def test_output_reader_rejects_symbolic_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'valid.json').write_text('{"status":"ok"}', encoding='utf-8')
            self.assertEqual(_read_json(root / 'valid.json'), {'status': 'ok'})
            (root / 'redirect.json').symlink_to(root / 'valid.json')
            with self.assertRaises(AssertionError):
                _read_json(root / 'redirect.json')


if __name__ == '__main__':
    unittest.main()
