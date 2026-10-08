"""Outer authority/orchestration controls, never a native semantic substitute."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from tools import pipeline_reference_runtime as runtime


class ReferenceRuntimeAuthorityTests(unittest.TestCase):
    revision='a'*40
    source_revision='b'*40
    run_id='12345'

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'receipts';self.root.mkdir()
        self.native=Path(self.temp.name)/'native';self.native.mkdir()
        self.sources={'src/biocompiler/example.py':'c'*64}
        self.tools={'tools/example.py':'d'*64}
        self.metadata={'corpus':{'path':'frozen','sha256':'e'*64},'declarations':{'profile':'f'*64}}
        self.rows={};self.inputs={};self.binaries={}
        for target,(system,machine) in runtime.r.PLATFORMS.items():
            native={'revision':self.revision,'system':system,'machine':machine,
                'sha256':{'biocompiler-core':'1'*64,'biocompiler-verify':'2'*64}}
            self.binaries[target]=native;(self.native/target).mkdir()
            for python in runtime.r.PYTHONS:
                name='realization-'+target+'-py'+python
                directory=self.root/name;(directory/runtime.gate.ARTIFACT_DIRECTORY).mkdir(parents=True)
                self.inputs[name]={**native,'source_revision':self.source_revision,'run_id':self.run_id,'python_version':python+'.99'}
                self.rows[name]={'schema_version':runtime.gate.SCHEMA,'execution_kind':'installed-native','scope':runtime.SCOPE,
                    'status':'success','revision':self.revision,'source_revision':self.source_revision,'run_id':self.run_id,
                    'native_platform':target,'system':system,'machine':machine,'python_version':python+'.99',
                    'python_sources':self.sources,'campaign_sources':self.tools,'native_inputs':native,
                    'artifact_directory':runtime.gate.ARTIFACT_DIRECTORY,**self.metadata,
                    'package_path':'/installed/site-packages/biocompiler/__init__.py',
                    'executables':{'core':'/native/biocompiler-core','verify':'/native/biocompiler-verify'},'artifacts':{}}
        self.interpreters={}
        for python in runtime.r.PYTHONS:
            path=Path(self.temp.name)/('python'+python);path.write_bytes(('test interpreter '+python).encode());path.chmod(0o700)
            self.interpreters[python]=path
        self.save()
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for owner,name,value in ((runtime.gate,'Corpus',object()),(runtime,'product_sources',self.sources),
                (runtime,'campaign_sources',self.tools),(runtime,'metadata',self.metadata)):
            self.stack.enter_context(patch.object(owner,name,return_value=value))
        self.binary=self.stack.enter_context(patch.object(runtime.r,'verify_binaries',
            side_effect=lambda path,revision,target:deepcopy(self.binaries[target])))
        self.run=self.stack.enter_context(patch.object(runtime.subprocess,'run',side_effect=self.worker))

    def save(self):
        for name,row in self.rows.items():
            (self.root/name/runtime.gate.RECEIPT_FILE).write_bytes(runtime.canonical(row)+b'\n')
            (self.root/name/'native-inputs.json').write_bytes(runtime.canonical(self.inputs[name])+b'\n')

    def worker(self,command,**kwargs):
        from types import SimpleNamespace
        def arg(name):return command[command.index('--'+name)+1]
        receipt,pin=runtime.r.read(Path(arg('receipt')))
        report={'schema_version':'biocompiler.reference_independent_reconstruction.v1','status':'success',
            'receipt_sha256':pin,'revision':self.revision,'source_revision':self.source_revision,'run_id':self.run_id,
            'native_platform':arg('platform'),'campaign_sources':self.tools,'python_sources':self.sources,
            'interpreter':command[0],'interpreter_sha256':runtime.sha(Path(command[0]).read_bytes()),
            'python_version':arg('python')+'.99','complete_artifacts':{},
            'projection':{'original_behavior':{'unit_fixture':'outer orchestration only'}},'reconstruction':{}}
        Path(arg('output')).write_bytes(runtime.canonical(report)+b'\n')
        return SimpleNamespace(returncode=0,stdout=b'',stderr=b'')

    def compare(self,**changes):
        return runtime.compare(self.root,self.native,**{'revision':self.revision,'source_revision':self.source_revision,
            'run_id':self.run_id,'python311':self.interpreters['3.11'],'python314':self.interpreters['3.14'],**changes})

    def test_all_four_slots_require_separate_matching_runtime_reconstruction(self):
        result=self.compare()
        self.assertEqual(set(result['receipts']),set(self.rows));self.assertEqual(self.run.call_count,4)
        self.assertEqual(self.binary.call_count,2)
        for call in self.run.call_args_list:
            command=call.args[0];minor=command[command.index('--python')+1]
            self.assertEqual(command[0],str(self.interpreters[minor].resolve()))
            self.assertIn('--reconstruct',command)
            self.assertFalse(Path(call.kwargs['cwd']).is_relative_to(runtime.ROOT))

    def test_source_run_binary_execution_kind_and_runtime_cannot_be_relabelled(self):
        name=next(iter(self.rows));original=deepcopy(self.rows[name])
        for field,value in {'execution_kind':'transcript-reconstruction','status':'running','revision':'f'*40,
                'source_revision':'f'*40,'run_id':'old','python_sources':{},'campaign_sources':{},
                'native_inputs':{},'native_platform':'other','python_version':'3.10.99','declarations':{}}.items():
            with self.subTest(field=field):
                self.rows[name]={**deepcopy(original),field:value};self.save()
                with self.assertRaises(AssertionError):self.compare()
        self.rows[name]=original

    def test_complete_matrix_and_independent_worker_success_are_mandatory(self):
        name=next(iter(self.rows));slot=self.root/name;held=self.root/'held';slot.rename(held)
        with self.assertRaisesRegex(AssertionError,'Incomplete four-runtime'):self.compare()
        slot.symlink_to(held,target_is_directory=True)
        with self.assertRaisesRegex(AssertionError,'Unsafe reference runtime'):self.compare()
        slot.unlink();held.rename(slot)
        from types import SimpleNamespace
        self.run.side_effect=lambda *args,**kwargs:SimpleNamespace(returncode=1,stdout=b'',stderr=b'actual replay failed')
        with self.assertRaisesRegex(AssertionError,'independent reconstruction failed'):self.compare()

    def test_worker_report_and_full_artifact_inventory_are_independently_bound(self):
        original=self.worker
        def changed(command,**kwargs):
            result=original(command,**kwargs);path=Path(command[command.index('--output')+1]);report,_=runtime.r.read(path)
            report['receipt_sha256']='0'*64;path.write_bytes(runtime.canonical(report)+b'\n');return result
        self.run.side_effect=changed
        with self.assertRaisesRegex(AssertionError,'Unbound reference reconstruction worker'):self.compare()
        self.run.side_effect=original
        name=next(iter(self.rows));(self.root/name/runtime.gate.ARTIFACT_DIRECTORY/'unclaimed.bin').write_bytes(b'unclaimed')
        with self.assertRaisesRegex(AssertionError,'Missing or extra complete workflow artifact'):self.compare()

    def test_actual_two_runtimes_and_current_authority_are_required(self):
        with self.assertRaisesRegex(AssertionError,'two actual Python runtimes'):
            self.compare(python314=self.interpreters['3.11'])
        with self.assertRaisesRegex(AssertionError,'Missing current reference run authority'):
            self.compare(run_id=None)


class ReferenceInstalledSourceClosureTests(unittest.TestCase):
    """Pure source/import controls; the inert package is not an installation."""
    distribution_source = 'src/biocompiler/core_distribution.py'

    @contextmanager
    def inert_package(self):
        # Exercise the actual installed-layout resolver and source checker while
        # replacing distribution discovery with an explicitly inert module.
        # No wheel, native executable, product constructor or subprocess runs.
        with tempfile.TemporaryDirectory(prefix='reference-source-control-') as directory, \
                patch.dict(sys.modules), \
                patch.dict(os.environ, {'BIOCOMPILER_NATIVE_INPUT_LAYOUT': 'installed'}), \
                patch.object(runtime.subprocess, 'Popen', side_effect=AssertionError('No subprocess in source control')):
            root = Path(directory).resolve()
            package = root / 'biocompiler'
            package.mkdir()
            native = root / 'inert-owned-core'
            (package / '__init__.py').write_bytes(b'"""Inert source-control package, not an installed SDK."""\n')
            (package / 'core_distribution.py').write_text(
                '"""Inert discovery stand-in; no distribution is inspected."""\n'
                'from pathlib import Path\n'
                'from types import SimpleNamespace\n'
                'def installed_distribution():\n'
                '    root = Path(' + repr(str(native)) + ')\n'
                '    return SimpleNamespace(package_root=root,\n'
                '        executable=lambda role: root / "bin" / ("biocompiler-" + role))\n')
            for name in tuple(sys.modules):
                if name == 'biocompiler' or name.startswith('biocompiler.'):
                    del sys.modules[name]
            module = ModuleType('biocompiler')
            module.__file__ = str(package / '__init__.py')
            module.__path__ = [str(package)]
            sys.modules['biocompiler'] = module
            sources = {'src/biocompiler/' + path.name: runtime.sha(path.read_bytes())
                       for path in package.glob('*.py')}
            yield SimpleNamespace(package=package, native=native, sources=sources)

    def test_current_source_closure_explicitly_pins_distribution_bytes(self):
        original = 'src/biocompiler/__init__.py'
        corpus = SimpleNamespace(index={'source_files': {original: 'frozen-original-pin'}})
        with patch.object(runtime.manager, 'python_sources', return_value={}), \
                patch.object(runtime.gate, 'SOURCES', ()), \
                patch.object(runtime.subprocess, 'Popen', side_effect=AssertionError('No subprocess in source control')):
            sources = runtime.product_sources(corpus)
        self.assertEqual(sources, {path: runtime.sha((runtime.ROOT / path).read_bytes())
                                  for path in (original, self.distribution_source)})

    def test_lazy_installed_resolver_import_remains_in_closed_source_authority(self):
        with self.inert_package() as fixture:
            self.assertNotIn('biocompiler.core_distribution', sys.modules)
            runtime.installed_sources(fixture.sources)
            self.assertEqual(runtime.native_executable(fixture.native, 'core'),
                             fixture.native / 'bin/biocompiler-core')
            self.assertIn('biocompiler.core_distribution', sys.modules)
            self.assertEqual(runtime.installed_sources(fixture.sources),
                             str(fixture.package / '__init__.py'))

    def test_omitted_or_changed_distribution_source_is_rejected(self):
        with self.inert_package() as fixture:
            runtime.native_executable(fixture.native, 'verify')
            omitted = {path: pin for path, pin in fixture.sources.items() if path != self.distribution_source}
            with self.assertRaisesRegex(AssertionError,
                    'Loaded reference module lacks current source authority: biocompiler.core_distribution'):
                runtime.installed_sources(omitted)
            path = fixture.package / 'core_distribution.py'
            path.write_bytes(path.read_bytes() + b'\n# changed after source pinning\n')
            with self.assertRaisesRegex(AssertionError,
                    'Installed reference source differs: src/biocompiler/core_distribution.py'):
                runtime.installed_sources(fixture.sources)

    def test_loaded_unlisted_module_does_not_expand_source_authority(self):
        with self.inert_package() as fixture:
            runtime.native_executable(fixture.native, 'core')
            path = fixture.package / 'unlisted.py'
            path.write_bytes(b'"""Unlisted inert source."""\n')
            module = ModuleType('biocompiler.unlisted')
            module.__file__ = str(path)
            sys.modules[module.__name__] = module
            with self.assertRaisesRegex(AssertionError,
                    'Loaded reference module lacks current source authority: biocompiler.unlisted'):
                runtime.installed_sources(fixture.sources)
