"""Import-only CLI controls and inert frame validation; no native execution."""
import ast
from contextlib import contextmanager
from copy import deepcopy
import hashlib
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import check_pipeline_reference_install as campaign
from tests import test_reference_attempt_receipts as fixtures


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'tools/reference_attempt_receipts.py'
ORIGINAL_SHA256 = '8eede959a8eec6ee6716c46daeb2a2ed4343db679ba8c44834ca0fbc049bcdcb'
ORIGINAL_IMPORT = b'from . import check_pipeline_manager_install as manager\n'
CURRENT_IMPORT = (b'if __package__:\n'
    b'    from . import check_pipeline_manager_install as manager\n'
    b'else:\n'
    b'    import check_pipeline_manager_install as manager\n')
HELPERS = ('reference_execution_guard', 'reference_pipeline_transcript',
    'pipeline_reference_runtime', 'reference_attempt_receipts')


@contextmanager
def script_mode():
    """Use actual script globals and sibling imports, without entering main."""
    with patch.object(sys, 'path', [str(ROOT / 'tools'), *sys.path]), patch.dict(sys.modules):
        # Avoid borrowing a previously loaded top-level helper from another test.
        for path in (ROOT / 'tools').glob('*.py'):
            sys.modules.pop(path.stem, None)
        namespace = runpy.run_path(str(ROOT / 'tools/check_pipeline_reference_install.py'),
            run_name='_reference_import_only')
        yield namespace


class ReferenceAttemptImportModeTests(unittest.TestCase):
    def test_exact_import_only_restoration_reproduces_original_script_failure(self):
        current = SOURCE.read_bytes()
        self.assertEqual(current.count(CURRENT_IMPORT), 1)
        original = current.replace(CURRENT_IMPORT, ORIGINAL_IMPORT, 1)
        self.assertEqual(hashlib.sha256(original).hexdigest(), ORIGINAL_SHA256)
        def functions(raw):
            tree = ast.parse(raw)
            return {node.name: ast.get_source_segment(raw.decode(), node)
                    for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertEqual(functions(current), functions(original))
        self.assertEqual(set(functions(current)), {'reference', 'validate'})
        with self.assertRaisesRegex(ImportError, 'attempted relative import with no known parent package'):
            exec(compile(original, str(SOURCE), 'exec'),
                {'__name__': '_original_reference_attempt_receipts', '__package__': ''})

    def check_helpers(self, loader, manager, prefix):
        helpers = {name: loader(name) for name in HELPERS}
        for name, helper in helpers.items():
            self.assertEqual(helper.__name__, prefix + name)
            self.assertEqual(Path(helper.__file__).resolve(), ROOT / 'tools' / (name + '.py'))
            if name != 'reference_pipeline_transcript':
                self.assertIs(helper.manager, manager)
        attempt = helpers['reference_attempt_receipts']
        self.assertIs(attempt.require, manager.require)
        self.assertIs(attempt.equal, manager.equal)
        with self.assertRaisesRegex(AssertionError, 'Unknown closed reference campaign helper'):
            loader('unreviewed_reference_helper')
        return attempt

    def test_complete_closed_helper_census_in_package_and_script_modes(self):
        self.check_helpers(campaign.tool, campaign.manager, 'tools.')
        with script_mode() as namespace:
            self.assertEqual(namespace['__package__'], '')
            self.assertEqual(namespace['manager'].__name__, 'check_pipeline_manager_install')
            self.check_helpers(namespace['tool'], namespace['manager'], '')

    def test_script_mode_retains_complete_inert_attempt_proof_and_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            details = fixtures.checked(fixtures.fixture(directory, nested=True))
        expected = campaign.tool('reference_attempt_receipts').validate([details])
        self.assertEqual(len(expected['attempts']), 2)
        self.assertEqual(len(expected['lifecycle_commands']), 2)
        with script_mode() as namespace:
            attempt = namespace['tool']('reference_attempt_receipts')
            self.assertEqual(attempt.validate([details]), expected)
            changed = deepcopy(details)
            next(row for row in changed['commands'] if row['operation'] == 'set-dependency')[
                'arguments']['identity'] = 'changed'
            for validator in (campaign.tool('reference_attempt_receipts').validate, attempt.validate):
                with self.assertRaisesRegex(AssertionError, 'dependency write order or identity changed'):
                    validator([changed])


if __name__ == '__main__':
    unittest.main()
