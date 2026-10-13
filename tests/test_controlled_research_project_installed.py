"""Inert package-census and failure-retention controls; no installation or native code."""
import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from tools import check_controlled_research_project_installed as installed

class ControlledInstalledTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.base=Path(temp.name)
        self.root=self.base/'source';self.package=self.base/'site/biocompiler';self.package.mkdir(parents=True)
        self.files={'biocompiler/__init__.py':b'# inert', 'biocompiler/policy/research_project.py':b'# inert project', 'biocompiler/core_policy_controlled_workflow.py':b'# inert wire','biocompiler/py.typed':b''}
        for name,raw in self.files.items():
            for path in (self.root/'src'/name,self.package.parent/name):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        self.archive=self.base/'inert-members.zip';self.write_archive(self.files)
        rows=[SimpleNamespace(name=name,size=len(raw),hash=SimpleNamespace(mode='sha256',value=base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('='))) for name,raw in self.files.items()]
        self.dist=SimpleNamespace(version='inert',files=rows,locate_file=lambda row:self.package.parent/row.name)
        import biocompiler
        for mock in (patch.object(biocompiler,'__file__',str(self.package/'__init__.py')),patch.object(installed.metadata,'distribution',return_value=self.dist),patch('subprocess.Popen',side_effect=AssertionError('No execution'))):mock.start();self.addCleanup(mock.stop)
    def write_archive(self,files):
        with zipfile.ZipFile(self.archive,'w') as archive:
            for name,raw in files.items():archive.writestr(name,raw)
    def test_three_way_exact_file_and_empty_marker_identity(self):
        result=installed.installed_wheel(self.archive,root=self.root)
        self.assertEqual(set(result['files']),set(self.files));self.assertEqual(result['files']['biocompiler/py.typed']['bytes'],0)
    def test_source_installed_wheel_missing_extra_and_rehashed_changes_reject(self):
        changes=[('source',self.root/'src/biocompiler/__init__.py'),('installed',self.package/'__init__.py')]
        for kind,path in changes:
            before=path.read_bytes();path.write_bytes(b'# altered')
            with self.subTest(kind=kind),self.assertRaises(AssertionError):installed.installed_wheel(self.archive,root=self.root)
            path.write_bytes(before)
        for corpus in ({name:raw for name,raw in self.files.items() if not name.endswith('py.typed')},{**self.files,'biocompiler/producer.py':b'# unexpected'}):
            self.write_archive(corpus)
            with self.assertRaisesRegex(AssertionError,'census'):installed.installed_wheel(self.archive,root=self.root)
        self.write_archive(self.files);(self.package/'extra.py').write_bytes(b'# extra')
        with self.assertRaisesRegex(AssertionError,'census'):installed.installed_wheel(self.archive,root=self.root)
    def test_redirected_package_entry_rejects(self):
        (self.package/'extra.py').symlink_to(self.package/'__init__.py')
        with self.assertRaisesRegex(AssertionError,'Redirected'):installed.installed_wheel(self.archive,root=self.root)
    def test_local_native_runner_is_unavailable(self):
        with patch.dict('os.environ',{},clear=True),self.assertRaisesRegex(AssertionError,'hosted-only'):installed.run(object())

class ControlledInstalledFailureTests(unittest.TestCase):
    def test_failed_outside_child_log_is_copied_before_failure_propagates(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);root=base/'source';root.mkdir();output=base/'installed.json'
            sdk=base/'inert-wheel';sdk.write_bytes(b'INERT NEVER INSTALLED');native=base/'inert-native';native.write_bytes(b'INERT NEVER EXECUTED')
            args=SimpleNamespace(work_dir=base/'outside',output=output,sdk_wheel=sdk,sdk_sha256=None,core=native,verify=native,core_sha256=None,verify_sha256=None)
            def failed(*a,**kw):kw['stdout'].write(b'inert retained failure\n');return SimpleNamespace(returncode=9)
            with patch.object(installed,'ROOT',root),patch.object(installed.sys,'platform','linux'),patch.object(installed.sys,'version_info',(3,11)),patch.dict('os.environ',{'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted'},clear=True),patch.object(installed.campaign,'INPUTS',()),patch.object(installed.campaign,'checked_assets',return_value={'root':root,'pins':{}}),patch.object(installed.campaign,'source_identity',return_value={}),patch.object(installed.campaign,'native_authority',return_value={}),patch.object(installed,'installed_wheel',return_value={'package':str(base),'files':{}}),patch.object(installed.subprocess,'run',side_effect=failed),self.assertRaisesRegex(AssertionError,'Installed public rehearsal failed'):
                installed.run(args)
            self.assertEqual((base/'installed/rehearsal.log').read_bytes(),b'inert retained failure\n')
            receipt=json.loads(output.read_bytes());self.assertEqual(receipt['status'],'failed');self.assertEqual(receipt['returncode'],9)
            self.assertIn('rehearsal.log',receipt['files'])

if __name__=='__main__':unittest.main()
