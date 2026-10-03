"""Pure release-policy and wheel-entry tests; no native audit or packaging."""
from copy import deepcopy
import csv
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).parents[1]/'tools/build_prebuilt_core.py'
SPEC = importlib.util.spec_from_file_location('prebuilt_core_draft', SOURCE)
release = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(release)

ELF = ''' [Requesting program interpreter: /lib64/ld-linux-x86-64.so.2]
 0x0000000000000001 (NEEDED) Shared library: [libm.so.6]
 0x0000000000000001 (NEEDED) Shared library: [libc.so.6]
 0x0010 Name: GLIBC_2.2.5 Flags: none Version: 2
 0x0020 Name: GLIBC_2.39 Flags: none Version: 3
'''
MACHO = '''Load command 1
          cmd LC_LOAD_DYLIB
      cmdsize 56
         name /usr/lib/libSystem.B.dylib (offset 24)
Load command 2
          cmd LC_BUILD_VERSION
      cmdsize 32
     platform 1
        minos 14.0
          sdk 14.5
'''


class PrebuiltReleasePolicyTests(unittest.TestCase):
    def test_elf_closed_system_linkage_and_exact_glibc_tag(self):
        self.assertEqual(release.elf_policy(ELF), {'needed': ['libm.so.6', 'libc.so.6'], 'maximum_glibc': '2.39'})
        for text, message in ((ELF.replace('libm.so.6', 'libgmp.so.10'), 'unbundled'),
            (ELF+' (RUNPATH) [/opt/build/lib]\n', 'search path'),
            (ELF.replace('GLIBC_2.39', 'GLIBC_2.40'), 'newer'),
            (ELF+' GLIBC_PRIVATE', 'Unreviewed'), (ELF+' GCC_4.2.0', 'compiler runtime'),
            (ELF.replace('/lib64/', '/foreign/'), 'interpreter'),
            (ELF+' x86 ISA needed: x86-64-v3', 'CPU ISA')):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message): release.elf_policy(text)

    def test_macho_closed_system_linkage_and_deployment_target(self):
        self.assertEqual(release.macho_policy(MACHO), {'needed': ['/usr/lib/libSystem.B.dylib'], 'minimum_macos': '14.0'})
        for text, message in ((MACHO.replace('/usr/lib/libSystem.B.dylib', '/opt/homebrew/lib/libgmp.10.dylib'), 'unbundled'),
            (MACHO+'Load command 3\n          cmd LC_RPATH\n', 'search path'),
            (MACHO.replace('minos 14.0', 'minos 15.0'), 'deployment target'),
            (MACHO.replace('platform 1', 'platform 2'), 'Apple platform'),
            (MACHO.replace('LC_LOAD_DYLIB', 'LC_LOAD_WEAK_DYLIB'), 'loader command'),
            (MACHO.replace('LC_LOAD_DYLIB', 'LC_LAZY_LOAD_DYLIB'), 'loader command')):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message): release.macho_policy(text)

    def test_wheel_entry_modes_complete_records_and_platform_metadata(self):
        files = {name: b'nonexecuted fixture' for name in release.FILES | {'distribution.json'}}
        for target, (_, _, tag) in release.TARGETS.items():
            entries = release.wheel_entries(files, target)
            info = 'biocompiler_core-'+release.VERSION+'.dist-info/'
            rows = list(csv.reader(io.StringIO(entries[info+'RECORD'][0].decode())))
            self.assertEqual({row[0] for row in rows}, set(entries))
            self.assertEqual(rows[-1], [info+'RECORD', '', ''])
            for path, digest, size in rows[:-1]:
                self.assertTrue(digest.startswith('sha256=')); self.assertEqual(int(size), len(entries[path][0]))
            self.assertIn(('Tag: '+tag).encode(), entries[info+'WHEEL'][0])
            self.assertIn(b'Root-Is-Purelib: false', entries[info+'WHEEL'][0])
            self.assertEqual(entries['biocompiler_core/bin/biocompiler-core'][1], 0o755)
            self.assertEqual(entries['biocompiler_core/bin/biocompiler-verify'][1], 0o755)
        with self.assertRaisesRegex(ValueError, 'layout'):
            release.wheel_entries({**files, 'unowned': b''}, 'linux-x86_64')

    def test_release_requires_both_platforms_same_source_tested_run_and_versions(self):
        rows = [{ 'schema_version': release.SCHEMA, 'native_platform': target,
            'sdk_version': release.VERSION, 'distribution': 'biocompiler-core', 'distribution_version': release.VERSION,
            'source_revision': 'a'*40, 'tested_revision': 'b'*40, 'run_id': '123',
            'core_version': release.CORE_VERSION, 'protocol': release.PROTOCOL, 'wheel_tag': release.TARGETS[target][2],
            'files': {name: {'sha256': 'a'*64, 'size': 8} for name in release.FILES}} for target in release.TARGETS]
        raw = [release.canonical(row) for row in rows]
        result = release.release(raw)
        self.assertNotEqual(result['source_revision'], result['tested_revision'])
        self.assertEqual(set(result['platforms']), set(release.TARGETS))
        for key in ('sdk_version', 'tested_revision', 'source_revision', 'run_id', 'protocol', 'core_version'):
            forged = deepcopy(rows); forged[1][key] += 'changed'
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'mixes|identity'):
                release.release([release.canonical(row) for row in forged])
        with self.assertRaisesRegex(ValueError, 'both reviewed'): release.release(raw[:1])
        with self.assertRaisesRegex(ValueError, 'census'): release.release([raw[0], raw[0]])

    def test_source_versions_are_read_without_import_or_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'src/biocompiler').mkdir(parents=True)
            (root/'pyproject.toml').write_text('[project]\nversion = "'+release.VERSION+'"\n')
            client = root/'src/biocompiler/core_client.py'
            client.write_text('raise RuntimeError("must never execute")\nCORE_VERSION = "0.1.0"\nPROTOCOL = "biocompiler.core.v1"\n')
            release.source_versions(root)
            client.write_text(client.read_text().replace('"0.1.0"', '"0.2.0"'))
            with self.assertRaisesRegex(ValueError, 'constants differ'): release.source_versions(root)


if __name__ == '__main__': unittest.main()
