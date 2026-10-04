"""Native scheduling over inert executable bytes; never run or compile native code."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools import ci_native_bundle as bundle

ROOT = Path(__file__).resolve().parents[1]
IDENTITY = {'revision':'a'*40, 'run_id':'123', 'run_attempt':'2'}
DECLARATION = '''(test (name test_a) (modules test_a) (libraries example))
(test (name test_b) (modules test_b) (libraries example)
 (action (run %{test} %{env:BIOCOMPILER_FIXTURE=missing})))
'''


class NativeBundleTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.source = self.root/'source'
        (self.source/'core/test').mkdir(parents=True)
        (self.source/'core/test/dune').write_text(DECLARATION)
        for name in bundle.expected_members(self.source):
            path = self.source/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(b'INERT fixture; never executable: '+name.encode())
        self.enterContext(patch.object(bundle.ci,'identity',return_value=IDENTITY))
        self.archive = self.root/'native.zip'
        bundle.bundle(self.source,self.archive)

    def destination(self, name='dest'):
        root = self.root/name
        (root/'core/test').mkdir(parents=True)
        (root/'core/test/dune').write_text(DECLARATION)
        return root

    def test_actual_dune_suite_census_and_argument_order_are_preserved(self):
        plan = bundle.test_plan((ROOT/'core/test/dune').read_text())
        self.assertEqual(len(plan),118)
        manager = next(row for row in plan if row['name']=='test_pipeline_callback_manager')
        self.assertEqual(manager['environment'], ['BIOCOMPILER_PIPELINE_CALLBACK_MANAGER_DECLARATION',
            'BIOCOMPILER_PIPELINE_CONTRACT_LITERALS','BIOCOMPILER_FIXED_PIPELINE_CORPUS'])
        self.assertEqual(bundle.test_plan(DECLARATION)[1]['environment'],['BIOCOMPILER_FIXTURE'])

    def test_unhandled_dune_actions_or_fields_and_duplicate_tests_fail_closed(self):
        for text in (DECLARATION+DECLARATION, DECLARATION+'(rule (action (run other)))',
                     DECLARATION.replace('(libraries example)', '(libraries example) (deps foo)',1),
                     DECLARATION.replace('(run %{test}', '(progn (run %{test}'),
                     DECLARATION.replace('%{env:BIOCOMPILER_FIXTURE=missing}', 'unreviewed'),
                     DECLARATION.replace('(modules test_a)', '(modules test_b)')):
            with self.subTest(text=text),self.assertRaises(ValueError): bundle.test_plan(text)

    def test_complete_bundle_restores_exact_bytes_and_executable_modes(self):
        target=self.destination()
        bundle.restore(target,self.archive)
        for name in bundle.expected_members(self.source):
            self.assertEqual((target/name).read_bytes(),(self.source/name).read_bytes())
            self.assertTrue(os.access(target/name,os.X_OK))

    def test_stale_tampered_missing_extra_and_duplicate_bundles_never_restore(self):
        with zipfile.ZipFile(self.archive) as archive:
            baseline={name:archive.read(name) for name in archive.namelist()}
        mutations=['revision','run_id','run_attempt','machine','dune_sha256','missing','extra','bytes','duplicate',
                   'duplicate-key','nonfinite']
        for number,mutation in enumerate(mutations):
            entries=deepcopy(baseline);manifest=json.loads(entries['manifest.json'])
            if mutation in ('revision','run_id','run_attempt','machine','dune_sha256'):
                manifest[mutation]='999';entries['manifest.json']=json.dumps(manifest).encode()
            elif mutation=='missing': entries.pop(next(name for name in entries if name.endswith('.exe')))
            elif mutation=='extra':entries['../../escaped']=b'not allowed'
            elif mutation=='bytes':entries[next(name for name in entries if name.endswith('.exe'))]=b'changed'
            elif mutation=='duplicate-key':entries['manifest.json']=b'{"run_id":"stale",'+entries['manifest.json'][1:]
            elif mutation=='nonfinite':entries['manifest.json']=b'{"untrusted":NaN,'+entries['manifest.json'][1:]
            damaged=self.root/('damaged-'+str(number)+'.zip')
            with zipfile.ZipFile(damaged,'w') as archive:
                for name,raw in entries.items():archive.writestr(name,raw)
                if mutation=='duplicate':
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore');archive.writestr('manifest.json',entries['manifest.json'])
            target=self.destination('dest-'+str(number))
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):bundle.restore(target,damaged)
            self.assertFalse((target/'core/_build').exists())

    def test_symlinked_or_existing_destinations_are_not_overwritten(self):
        for name in ('symlink','existing'):
            target=self.destination(name)
            if name=='symlink':(target/'core/_build').symlink_to(self.root,target_is_directory=True)
            else:
                path=target/'core/_build/default/bin/core/main.exe';path.parent.mkdir(parents=True);path.write_bytes(b'preserve')
            with self.assertRaises(ValueError):bundle.restore(target,self.archive)

    def test_every_suite_executes_and_one_failure_prevents_success(self):
        target=self.destination();bundle.restore(target,self.archive)
        fixture=self.root/'fixture.json';fixture.write_text('{}')
        observed=[]
        def execute(command,**kwargs):
            observed.append(command)
            kwargs['stdout'].write(b'complete native test fixture log\n')
            return subprocess.CompletedProcess(command,1 if command[0].endswith('test_b.exe') else 0)
        with patch.dict(os.environ,{'BIOCOMPILER_FIXTURE':str(fixture)}),patch.object(bundle.subprocess,'run',side_effect=execute):
            with self.assertRaisesRegex(ValueError,'failed native suite census'):
                bundle.run_tests(target,self.root/'results',2)
        self.assertEqual(len(observed),2)
        self.assertEqual(next(row for row in observed if row[0].endswith('test_b.exe'))[1:],[str(fixture)])
        result=json.loads((self.root/'results/receipt.json').read_text())
        self.assertEqual([row['name'] for row in result['tests']],['test_a','test_b'])
        self.assertEqual([row['returncode'] for row in result['tests']],[0,1])


if __name__=='__main__':unittest.main()
