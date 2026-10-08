"""Real small ZIP rejection checks and literal large-bound predicates."""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import tempfile
from types import SimpleNamespace
import unittest
import warnings
import zipfile
from tools import release_audit_artifacts as artifacts

ROOT = Path(__file__).resolve().parents[1]


class ReleaseAuditArtifactTests(unittest.TestCase):
    def fixture(self, root, names=('safe.txt',), *, mode=stat.S_IFREG):
        archive = root / 'artifact.zip'
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(archive, 'w') as stream:
                for name in names:
                    entry = zipfile.ZipInfo(name); entry.external_attr = mode << 16
                    stream.writestr(entry, b'exact literal bytes')
        metadata = {'one': {'name': 'one', 'id': 19, 'expired': False,
            'workflow_run': {'id': 37, 'head_sha': 'a' * 40}, 'created_at': '2026-01-01T00:00:01Z',
            'size_in_bytes': archive.stat().st_size, 'digest': 'sha256:' + artifacts.sha(archive)}}
        return metadata, {'one': str(archive)}

    def store(self, metadata, paths):
        return artifacts.ArtifactStore(metadata=metadata, paths=paths, required=['one'], run=37,
            head='a' * 40, started_at='2026-01-01T00:00:00Z')

    def test_small_archive_read_and_identical_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); metadata, paths = self.fixture(root)
            store = self.store(metadata, paths)
            try:
                self.assertEqual(store.names('one'), {'safe.txt'})
                self.assertEqual(store.read('one', 'safe.txt'), b'exact literal bytes')
                target = store.extract('one', root / 'extracted')
                self.assertEqual((target / 'safe.txt').read_bytes(), b'exact literal bytes')
                self.assertEqual((target / 'safe.txt').stat().st_mode & 0o777, 0o600)
                store.extract('one', target, allow_identical_existing=True)
                with self.assertRaises(AssertionError):
                    store.extract('one', target)
                (target / 'safe.txt').write_bytes(b'other literal byte')
                with self.assertRaises(AssertionError):
                    store.extract('one', target, allow_identical_existing=True)
            finally:
                store.close()

    def test_metadata_and_bytes_cannot_be_substituted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); original, paths = self.fixture(root)
            variants = [({'name': 'other'}), ({'expired': True}), ({'digest': 'sha256:' + '0' * 64}),
                        ({'size_in_bytes': 1}), ({'created_at': '2025-01-01T00:00:00Z'}),
                        ({'workflow_run': {'id': 38, 'head_sha': 'a' * 40}}),
                        ({'workflow_run': {'id': 37, 'head_sha': 'b' * 40}})]
            for change in variants:
                metadata = deepcopy(original); metadata['one'].update(change)
                with self.subTest(change=change), self.assertRaises(AssertionError):
                    self.store(metadata, paths)
            with self.assertRaises(AssertionError):
                self.store({}, paths)
            with self.assertRaises(AssertionError):
                self.store(original, {})
            Path(paths['one']).write_bytes(b'altered')
            with self.assertRaises(AssertionError):
                self.store(original, paths)

    def test_duplicate_unsafe_and_symlink_members_reject(self):
        for names, mode in [(('same', 'same'), stat.S_IFREG), (('../bad',), stat.S_IFREG),
                            (('/absolute',), stat.S_IFREG), (('bad\\path',), stat.S_IFREG),
                            (('link',), stat.S_IFLNK)]:
            with self.subTest(names=names), tempfile.TemporaryDirectory() as directory:
                metadata, paths = self.fixture(Path(directory), names, mode=mode)
                with self.assertRaises(AssertionError):
                    self.store(metadata, paths)

    def test_extraction_budget_is_cumulative_and_checked_before_new_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); metadata, paths = self.fixture(root, ('first', 'second'))
            store = self.store(metadata, paths)
            try:
                member_bytes = len(b'exact literal bytes')
                store.extracted = 2560 * 1024**2 - 2 * member_bytes
                target = root / 'extracted'
                store.extract('one', target, names=['first'])
                self.assertEqual(store.extracted, 2560 * 1024**2 - member_bytes)
                store.extract('one', target, names=['second'])
                self.assertEqual(store.extracted, 2560 * 1024**2)
                store.extract('one', target, allow_identical_existing=True)
                self.assertEqual(store.extracted, 2560 * 1024**2)
                store.extracted = 2560 * 1024**2 - member_bytes + 1
                rejected = root / 'rejected'
                with self.assertRaisesRegex(AssertionError, 'Prepared extraction budget exceeded'):
                    store.extract('one', rejected, names=['first'])
                self.assertEqual(store.extracted, 2560 * 1024**2 + 1)
                self.assertFalse((rejected / 'first').exists())
            finally:
                store.close()

    def test_large_bounds_at_limit_and_one_over_without_large_files(self):
        limits = {'MAX_ARCHIVE': 640 * 1024**2, 'MAX_EXPANDED': 4 * 1024**3,
                  'MAX_MEMBER': 512 * 1024**2, 'MAX_ALL_COMPRESSED': 4 * 1024**3,
                  'MAX_ALL_EXPANDED': 20 * 1024**3, 'MAX_EXTRACTED': 2560 * 1024**2}
        self.assertEqual({name: getattr(artifacts, name) for name in limits}, limits)
        trees = {name: ast.parse((ROOT / ('tools/' + name + '.py')).read_text())
                 for name in ('release_audit_artifacts', 'release_audit_native')}
        def evaluate(module, prefix, environment):
            calls = [node for node in ast.walk(trees[module]) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == 'require'
                     and len(node.args) >= 2 and any(isinstance(x, ast.Constant)
                         and isinstance(x.value, str) and x.value.startswith(prefix)
                         for x in ast.walk(node.args[1]))]
            self.assertEqual(len(calls), 1)
            expression = ast.fix_missing_locations(ast.Expression(deepcopy(calls[0].args[0])))
            namespace = {'__builtins__': {}, 'len': len, 'set': set, 'sum': sum, 'str': str,
                         **limits, **environment}
            return eval(compile(expression, '<literal-guard>', 'eval'), namespace, namespace)
        checks = 0
        for offset, accepted in ((0, True), (1, False)):
            size = 640 * 1024**2 + offset
            path = SimpleNamespace(is_file=lambda: True, is_symlink=lambda: False,
                                   stat=lambda size=size: SimpleNamespace(st_size=size))
            self.assertIs(evaluate('release_audit_artifacts', 'Missing or oversized archive', {'path': path}), accepted)
            checks += 1
            for key, maximum in [('expanded', 4 * 1024**3), ('expanded_total', 20 * 1024**3),
                                 ('compressed_total', 4 * 1024**3)]:
                environment = {'expanded': 1, 'expanded_total': 1, 'compressed_total': 1}
                environment[key] = maximum + offset
                self.assertIs(evaluate('release_audit_artifacts', 'Prepared archive budget exceeded', environment), accepted)
                checks += 1
            count = 300000 + offset
            self.assertIs(evaluate('release_audit_artifacts', 'Duplicate or oversized ZIP census',
                                  {'entries': range(count), 'all_names': range(count)}), accepted)
            self.assertIs(evaluate('release_audit_artifacts', 'Prepared extraction budget exceeded',
                                  {'self': SimpleNamespace(extracted=2560 * 1024**2 + offset)}), accepted)
            entry = SimpleNamespace(filename='safe', file_size=512 * 1024**2 + offset,
                                    external_attr=stat.S_IFREG << 16, flag_bits=0)
            self.assertIs(evaluate('release_audit_artifacts', 'Unsafe ZIP member',
                                  {'entry': entry, 'relative': PurePosixPath('safe'), 'stat': stat}), accepted)
            self.assertIs(evaluate('release_audit_native', 'Nested native bundle exceeds',
                                  {'archive': SimpleNamespace(infolist=lambda offset=offset: [SimpleNamespace(file_size=2 * 1024**3 + offset)])}), accepted)
            checks += 4
        self.assertEqual(checks, 16)
