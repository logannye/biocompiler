"""Pure source/input controls; synthetic archive bytes are never linked or run."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'tools/prepare_static_gmp.py'
SPEC = importlib.util.spec_from_file_location('static_gmp_draft', SOURCE)
DRAFT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DRAFT)


class StaticGmpConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.archive, self.header = self.root / 'libgmp.a', self.root / 'gmp.h'
        self.archive.write_bytes(b'!<arch>\n' + b'x' * 60)
        self.header.write_bytes(b'/* synthetic header; never compiled */\n')
        self.output = self.root / 'config'

    def prepare(self, **updates):
        args = dict(archive=self.archive, header=self.header, version='6.3.0', output=self.output)
        return DRAFT.prepare(**(args | updates))

    def test_records_exact_inputs_and_uses_absolute_archive_without_dynamic_fallback(self):
        with patch.object(DRAFT.subprocess, 'run', side_effect=AssertionError('unexpected execution')):
            receipt = self.prepare()
        config = (self.output / 'gmp.pc').read_text()
        self.assertIn('Libs: -custom -cclib ' + str(self.archive) + '\n', config)
        self.assertNotIn('-lgmp', config)
        self.assertEqual(receipt['archive']['sha256'], DRAFT.pin(self.archive.read_bytes())['sha256'])
        self.assertEqual(receipt['pkg_config'], DRAFT.pin(config.encode()))
        self.assertEqual(receipt['final_binary_dependency_audit'], 'required')
        self.assertFalse(receipt['native_execution'])

    def test_rejects_dynamic_library_and_existing_output_without_overwriting(self):
        self.archive.write_bytes(b'\x7fELF' + b'x' * 64)
        with self.assertRaisesRegex(ValueError, 'not an archive'):
            self.prepare()
        self.assertFalse(self.output.exists())
        self.output.mkdir()
        marker = self.output / 'keep'; marker.write_bytes(b'preserve')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.prepare()
        self.assertEqual(marker.read_bytes(), b'preserve')

    def test_rejects_symlink_input(self):
        target = self.root / 'actual.a'; self.archive.rename(target); self.archive.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_rejects_pkg_config_injection_and_parent_paths(self):
        for version in ('6.3.0\nLibs: -lforeign', '', 'unknown'):
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'version'):
                DRAFT.pkgconfig(self.archive, self.header, version)
        for name in ('../libgmp.a', 'space here/libgmp.a', '$(uname)/libgmp.a', '${libdir}/libgmp.a'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                DRAFT.pkgconfig(self.root / name, self.header, '6.3.0')
        self.assertFalse(self.output.exists())

    def test_rejects_empty_header_before_any_output(self):
        self.header.write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'size bound'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def complete(self):
        record=self.prepare()
        environment={name:None for name in ('PKG_CONFIG_PATH','PKG_CONFIG_LIBDIR','PKG_CONFIG_SYSROOT_DIR',
            'PKG_CONFIG_ALLOW_SYSTEM_CFLAGS','PKG_CONFIG_ALLOW_SYSTEM_LIBS')}
        environment['LC_ALL']='C'
        tool={'path':'/usr/bin/pkg-config','sha256':'1'*64,'size':123}
        def probe(args,text,env=environment):
            return {'argv':[tool['path'],*args,'gmp'],'tool':dict(tool),'environment':dict(env),
                'stdout':text+'\n','stderr':'','returncode':0}
        record['selection']={'version':probe(['--modversion'],'6.3.0'),
            'libdir':probe(['--variable=libdir'],str(self.root)),
            'includedir':probe(['--variable=includedir'],str(self.root))}
        record['resolution']={name:DRAFT.resolve_selected(path,64*1024*1024)[1]
            for name,path in (('archive',self.archive),('header',self.header))}
        configured=environment | {'PKG_CONFIG_PATH':str(self.output),'PKG_CONFIG_LIBDIR':str(self.output),
            'PKG_CONFIG_ALLOW_SYSTEM_CFLAGS':'1','PKG_CONFIG_ALLOW_SYSTEM_LIBS':'1'}
        record['configured']={'directory':str(self.output),
            'libs':probe(['--libs'],'-custom -cclib '+str(self.archive),configured),
            'cflags':probe(['--cflags'],'-I'+str(self.root),configured)}
        return record,(self.output/'gmp.pc').read_bytes()

    def test_complete_metadata_receipt_binds_exact_command_environment_and_physical_inputs(self):
        record,pc=self.complete()
        self.assertIs(DRAFT.validate_receipt(record,pc),record)
        mutations=(
            lambda x:x['selection']['libdir'].update(stdout='/another\n'),
            lambda x:x['selection']['version']['environment'].update(PKG_CONFIG_PATH='/foreign'),
            lambda x:x['configured']['libs'].update(stdout='-lgmp\n'),
            lambda x:x['configured']['libs'].update(stdout='-cclib '+str(self.archive)+' -custom\n'),
            lambda x:x['configured']['cflags'].update(stdout='-I/foreign\n'),
            lambda x:x['configured']['libs']['tool'].update(sha256='2'*64),
            lambda x:x['configured']['libs']['environment'].update(PKG_CONFIG_SYSROOT_DIR='/foreign'),
            lambda x:x['archive'].update(size=64*1024*1024+1),
            lambda x:x['resolution']['archive'].update(resolved='/foreign/libgmp.a'),
            lambda x:x['configured']['libs'].update(returncode=True),
        )
        for mutate in mutations:
            changed=deepcopy(record);mutate(changed)
            with self.subTest(mutate=mutate),self.assertRaises(ValueError):DRAFT.validate_receipt(changed,pc)
        with self.assertRaisesRegex(ValueError,'configuration differs'):DRAFT.validate_receipt(record,pc+b'\n')

    def test_exact_symlink_discovery_chain_is_retained_and_not_guessed(self):
        selected=self.root/'selected';selected.symlink_to(self.root,target_is_directory=True)
        resolved,proof=DRAFT.resolve_selected(selected/'libgmp.a',64*1024*1024)
        self.assertEqual(resolved,self.archive)
        self.assertEqual(proof['links'],[{'path':str(selected),'target':str(self.root)}])
        expected={'path':str(self.archive),**DRAFT.pin(self.archive.read_bytes())}
        DRAFT.validate_resolution(proof,str(selected/'libgmp.a'),expected)
        for key,value in (('links',[]),('requested',str(self.archive)),('resolved','/other/libgmp.a')):
            changed=deepcopy(proof);changed[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                DRAFT.validate_resolution(changed,str(selected/'libgmp.a'),expected)
        selected.unlink();selected.symlink_to(selected,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'too many symlinks'):
            DRAFT.resolve_selected(selected/'libgmp.a',64*1024*1024)


if __name__ == '__main__':
    unittest.main()
