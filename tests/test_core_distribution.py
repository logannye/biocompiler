"""Only filesystem/package-metadata fixtures; never execute native artifacts."""
from copy import deepcopy
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import sys
import unittest
from unittest.mock import patch

import biocompiler
from biocompiler.core_client import CoreProtocolError, CoreUnavailable

from biocompiler import core_distribution as distribution


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Entry(str):
    def __new__(cls, name, raw):
        result = super().__new__(cls, name)
        result.hash = SimpleNamespace(mode='sha256', value=base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode())
        result.size = len(raw)
        return result


class Distribution:
    def __init__(self, root, name):
        self.root, self.metadata, self.version = root, {'Name': name}, biocompiler.__version__
        self.files = []
        self.wheel = 'Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: py3-none-manylinux_2_39_x86_64\n'
    def locate_file(self, entry): return self.root / str(entry)
    def read_text(self, name): return self.wheel if name == 'WHEEL' else None
    def put(self, name, raw, mode=0o644):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw); path.chmod(mode)
        self.files = [entry for entry in self.files if str(entry) != name]+[Entry(name, raw)]


class CoreDistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.temp)
        self.sdk = Distribution(self.root/'sdk', 'biocompiler')
        self.native = Distribution(self.root/'native', 'biocompiler-core')
        self.revision, self.tested_revision, self.run_id = 'a'*40, 'd'*40, '123456'
        self.target = 'linux-x86_64'
        for name in ('__init__.py', 'core_distribution.py', 'core_client.py'):
            self.sdk.put('biocompiler/'+name, b'nonexecuted SDK fixture')
        self.enterContext(patch.object(distribution, 'SDK_DIRECTORY', (self.sdk.root/'biocompiler').resolve()))
        header = bytearray(64); header[:6] = b'\x7fELF\x02\x01'; header[16:18] = (3).to_bytes(2, 'little'); header[18:20] = (62).to_bytes(2, 'little')
        self.files = {name: b'fixture evidence\n' for name in distribution.FILES}
        self.files['__init__.py'] = b''
        self.files['bin/biocompiler-core'] = bytes(header)+b'CORE NONEXECUTABLE TEST IMAGE'
        self.files['bin/biocompiler-verify'] = bytes(header)+b'VERIFY NONEXECUTABLE TEST IMAGE'
        self.sync()
        self.enterContext(patch.object(distribution.metadata, 'distributions', return_value=[self.sdk, self.native]))
        self.enterContext(patch.object(distribution.platform, 'system', return_value='Linux'))
        self.enterContext(patch.object(distribution.platform, 'machine', return_value='x86_64'))
        self.enterContext(patch.object(distribution.platform, 'libc_ver', return_value=('glibc', '2.39')))
        self.negotiate = self.enterContext(patch.object(distribution.CoreClient, 'negotiate'))

    def sync(self):
        binaries = {name: sha(self.files['bin/'+name]) for name in ('biocompiler-core', 'biocompiler-verify')}
        self.files['binaries.json'] = encoded({'revision': self.tested_revision, 'system': distribution.PLATFORMS[self.target][0], 'machine': distribution.PLATFORMS[self.target][1], 'sha256': binaries})
        self.files['linkage.json'] = encoded({'schema_version': 'biocompiler.core_linkage.v1',
            'native_platform': self.target, 'policy': 'system-libraries-only.v1', 'sha256': binaries})
        self.manifest = {'schema_version': distribution.DISTRIBUTION_SCHEMA,
            'distribution': 'biocompiler-core', 'distribution_version': biocompiler.__version__,
            'sdk_version': biocompiler.__version__, 'core_version': distribution.CORE_VERSION,
            'protocol': distribution.PROTOCOL, 'source_revision': self.revision,
            'tested_revision': self.tested_revision, 'run_id': self.run_id,
            'native_platform': self.target, 'wheel_tag': distribution.PLATFORMS[self.target][2],
            'files': {name: {'sha256': sha(raw), 'size': len(raw)} for name, raw in self.files.items()}}
        for name, raw in self.files.items():
            self.native.put('biocompiler_core/'+name, raw, 0o755 if name.startswith('bin/') else 0o644)
        self.publish_manifest()

    def publish_manifest(self):
        raw = encoded(self.manifest)
        self.native.put('biocompiler_core/distribution.json', raw)
        self.native.wheel = 'Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: '+distribution.PLATFORMS[self.target][2]+'\n'
        self.release = {'schema_version': distribution.RELEASE_SCHEMA, 'sdk_version': biocompiler.__version__,
            'distribution': 'biocompiler-core', 'distribution_version': biocompiler.__version__,
            'source_revision': self.revision, 'tested_revision': self.tested_revision, 'run_id': self.run_id,
            'platforms': {key: sha(raw) if key == self.target else 'b'*64 for key in distribution.PLATFORMS}}
        self.sdk.put('biocompiler/_core_release.json', encoded(self.release))

    def rejected(self, message):
        with self.assertRaisesRegex(CoreUnavailable, message): distribution.installed_core()
        self.negotiate.assert_not_called()

    def test_roles_resolve_only_owned_absolute_paths_and_negotiate_freshly(self):
        with patch.dict('os.environ', {'PATH': '/unrelated/bin'}):
            core = distribution.installed_core(operation='canonicalize')
            verify = distribution.installed_core(role='verify')
        self.assertEqual(core.executable, self.native.root/'biocompiler_core/bin/biocompiler-core')
        self.assertEqual(verify.executable.name, 'biocompiler-verify')
        self.assertEqual(verify.role, 'verify')
        self.assertEqual(core.expected_sha256, sha(self.files['bin/biocompiler-core']))
        self.assertEqual(self.negotiate.call_count, 2)
        self.assertNotEqual(distribution.CORE_VERSION, biocompiler.__version__)

    def test_missing_and_duplicate_distributions_never_search_path(self):
        for values in ([self.sdk], [self.sdk, self.native, self.native]):
            with self.subTest(count=len(values)), patch.object(distribution.metadata, 'distributions', return_value=values):
                self.rejected('exactly one owned')

    def test_missing_release_authority_is_not_replaced_by_native_self_hashes(self):
        self.sdk.files = []
        self.rejected('Missing or duplicate owned')

    def test_stale_same_version_manifest_cannot_replace_sdk_pin(self):
        raw = deepcopy(self.manifest); raw['source_revision'] = 'c'*40
        self.native.put('biocompiler_core/distribution.json', encoded(raw))
        self.rejected('SDK release pin')

    def test_wrong_manifest_revision_protocol_core_version_platform_and_wheel_tag(self):
        original = deepcopy(self.manifest)
        for key, value in (('source_revision', 'c'*40), ('protocol', 'other'), ('core_version', biocompiler.__version__),
                           ('native_platform', 'macos-arm64'), ('wheel_tag', 'py3-none-any')):
            with self.subTest(field=key):
                self.manifest = {**original, key: value}; self.publish_manifest()
                self.rejected('Stale or incompatible')

    def test_other_binary_is_also_checked_before_selected_role_runs(self):
        path = self.native.root/'biocompiler_core/bin/biocompiler-verify'
        path.write_bytes(path.read_bytes()+b'changed')
        self.rejected('wheel RECORD')

    def test_missing_executable_or_execute_bit_and_rehashed_wrong_architecture(self):
        path = self.native.root/'biocompiler_core/bin/biocompiler-core'
        path.chmod(0o644); self.rejected('not executable')
        path.unlink(); self.rejected('Unavailable owned')
        self.files['bin/biocompiler-core'] = b'not an ELF image'; self.sync()
        self.rejected('image does not match')

    def test_symlink_and_unowned_extra_binary_are_rejected(self):
        path = self.native.root/'biocompiler_core/bin/biocompiler-core'
        alternate = self.root/'other'; alternate.write_bytes(path.read_bytes())
        path.unlink(); path.symlink_to(alternate)
        self.rejected('Symlinked')
        path.unlink(); self.sync()
        self.native.put('biocompiler_core/bin/other', b'extra')
        self.rejected('file inventory differs')

    def test_platform_and_baseline_are_explicit(self):
        with patch.object(distribution.platform, 'machine', return_value='aarch64'):
            self.rejected('No prebuilt Core')
        for libc in (('musl', '1.2'), ('glibc', '2.38')):
            with self.subTest(libc=libc), patch.object(distribution.platform, 'libc_ver', return_value=libc):
                self.rejected('glibc 2.39')

    def test_wheel_and_installed_versions_must_match_release(self):
        self.native.version = '0.1.0.dev28'; self.rejected('SDK release differ')
        self.native.version = biocompiler.__version__; self.native.wheel = 'Root-Is-Purelib: true\nTag: py3-none-any\n'
        self.rejected('wheel tag differs')

    def test_installer_bytecode_is_not_loaded_or_treated_as_native_authority(self):
        self.native.put('biocompiler_core/__pycache__/__init__.'+sys.implementation.cache_tag+'.pyc', b'never imported')
        distribution.installed_core()
        self.negotiate.assert_called_once()
        self.negotiate.reset_mock()
        self.native.put('biocompiler_core/__pycache__/other.'+sys.implementation.cache_tag+'.pyc', b'unreviewed')
        self.rejected('file inventory differs')

    def test_loaded_sdk_source_must_belong_to_owning_distribution(self):
        with patch.object(distribution, 'SDK_DIRECTORY', self.root/'other'):
            self.rejected('does not belong')

    def test_macos_arm64_positive_and_old_os_rejection(self):
        self.target = 'macos-arm64'
        header = bytearray(32); header[:4] = b'\xcf\xfa\xed\xfe'
        header[4:8] = (0x0100000c).to_bytes(4, 'little'); header[12:16] = (2).to_bytes(4, 'little')
        for name in ('core', 'verify'):
            self.files['bin/biocompiler-'+name] = bytes(header)+name.encode()
        self.sync()
        with patch.object(distribution.platform, 'system', return_value='Darwin'), \
                patch.object(distribution.platform, 'machine', return_value='arm64'), \
                patch.object(distribution.platform, 'mac_ver', return_value=('14.7', (), '')):
            distribution.installed_core()
            self.negotiate.assert_called_once()
            self.negotiate.reset_mock()
            with patch.object(distribution.platform, 'mac_ver', return_value=('13.7', (), '')):
                self.rejected('macOS 14')

    def test_foreign_tested_revision_and_run_are_not_source_revision_aliases(self):
        for key, value in (('tested_revision', self.revision), ('run_id', '654321')):
            with self.subTest(field=key):
                self.manifest[key] = value; self.publish_manifest()
                self.rejected('Stale or incompatible')
                self.sync()

    def test_duplicate_manifest_fields_and_nonregular_files_fail_closed(self):
        raw = b'{"schema_version":1,"schema_version":2}'
        self.sdk.put('biocompiler/_core_release.json', raw)
        self.rejected('Duplicate')
        self.sync()
        target = self.native.root/'biocompiler_core/packages.txt'
        target.unlink(); target.mkdir()
        self.rejected('Nonregular')

    def test_negotiation_rejection_propagates_without_fallback(self):
        self.negotiate.side_effect = CoreProtocolError('incompatible capabilities')
        with self.assertRaisesRegex(CoreProtocolError, 'incompatible capabilities'):
            distribution.installed_core()
        self.negotiate.assert_called_once_with('capabilities')


if __name__ == '__main__': unittest.main()
