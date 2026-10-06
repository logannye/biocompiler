"""Inert SDK metadata checks; no wheel writing, installation or execution."""
from copy import deepcopy
import base64
import csv
import hashlib
import io
from pathlib import Path
import tomllib
import unittest
from unittest.mock import patch

from tools import build_prebuilt_core as build
from tools import check_prebuilt_core_release as check


ROOT = Path(__file__).resolve().parents[1]


def record(entries):
    name = 'biocompiler-' + build.VERSION + '.dist-info/RECORD'
    output = io.StringIO(newline='')
    writer = csv.writer(output, lineterminator='\n')
    for path, (raw, _) in sorted(entries.items()):
        if path != name:
            digest = base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode()
            writer.writerow([path, 'sha256=' + digest, len(raw)])
    writer.writerow([name, '', ''])
    entries[name] = output.getvalue().encode(), 0o644


class PrebuiltSdkEntrypointTests(unittest.TestCase):
    def setUp(self):
        # Pure maps of independently supplied entry bytes; never packaged/imported.
        self.sources = {'biocompiler/__init__.py': b'never execute this source\n'}
        self.release = {'schema_version': 'biocompiler.core_release.v1', 'sdk_version': build.VERSION,
            'distribution': 'biocompiler-core', 'distribution_version': build.VERSION,
            'source_revision': 'a' * 40, 'tested_revision': 'b' * 40, 'run_id': '123',
            'platforms': {name: str(index) * 64 for index, name in enumerate(build.TARGETS, 1)}}
        self.info = 'biocompiler-' + build.VERSION + '.dist-info/'
        self.entries = {name: (raw, 0o644) for name, raw in self.sources.items()}
        self.entries.update({
            'biocompiler/_core_release.json': (build.canonical(self.release), 0o644),
            self.info + 'METADATA': (('Metadata-Version: 2.4\nName: biocompiler\nVersion: ' + build.VERSION
                + '\nRequires-Python: >=3.11\nProvides-Extra: core\nRequires-Dist: biocompiler-core=='
                + build.VERSION + '; extra == "core"\n\n').encode(), 0o644),
            self.info + 'WHEEL': (b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n', 0o644),
            self.info + 'entry_points.txt': (b'[console_scripts]\nbiocompiler = biocompiler.entrypoint:main\n', 0o644),
        })
        record(self.entries)
        self.enterContext(patch.object(build, 'write_wheel', side_effect=AssertionError('No packaging')))
        self.enterContext(patch('subprocess.run', side_effect=AssertionError('No process')))

    def verify(self, entries):
        check.validate_sdk(entries, source_files=self.sources, release=self.release)

    def test_current_declarative_policy_entrypoint_is_the_exact_sdk_route(self):
        metadata = tomllib.loads((ROOT / 'pyproject.toml').read_text())
        self.assertEqual(metadata['project']['scripts'], {'biocompiler': 'biocompiler.entrypoint:main'})
        self.verify(self.entries)

    def test_rehashed_legacy_or_foreign_entrypoint_still_rejects(self):
        for target in ('biocompiler.cli:main', 'biocompiler.policy.cli:main', 'foreign:main'):
            with self.subTest(target=target):
                changed = deepcopy(self.entries)
                changed[self.info + 'entry_points.txt'] = (
                    ('[console_scripts]\nbiocompiler = ' + target + '\n').encode(), 0o644)
                record(changed)
                check.validate_record(changed)
                with self.assertRaisesRegex(ValueError, 'SDK CLI entry point differs'):
                    self.verify(changed)


if __name__ == '__main__':
    unittest.main()
