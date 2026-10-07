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
POLICY_DECLARATION = '''(test (name test_policy_check) (modules test_policy_check) (libraries example)
 (action (run %{test} %{dep:data/policy_frontend_request.json}
  %{dep:data/policy_frontend_submission.json} %{dep:data/policy_documents_v01.json})))
(test (name test_policy_service) (modules test_policy_service) (libraries example)
 (action (run %{test} %{dep:data/policy_documents_v01.json})))
'''
POLICY_FIXTURES = ["data/policy_frontend_request.json", "data/policy_frontend_submission.json",
                   "data/policy_documents_v01.json"]


# Literal union inventory, independent of the runner's closed allowlist.
POLICY_OPERATIONAL_FIXTURES = {
    'test_policy_operational': ['data/policy_operational_v01.json'],
    'test_policy_execution': ['data/policy_operational_v01.json'],
    'test_policy_operational_service': ['data/policy_operational_v01.json'],
    'test_policy_realization_source': ['data/policy_realization_source_v01.json'],
    'test_policy_exclusion_source': ['data/policy_exclusion_source_v01.json'],
    'test_policy_operating_domain': ['data/policy_operating_domain_v01.json', 'data/policy_operational_v01.json'],
    'test_policy_implementation': ['data/policy_implementation_v01.json'],
    'test_policy_realization_admission': ['data/policy_realization_request_v01.json', 'data/policy_realization_source_v01.json'],
    'test_policy_domain_reference': ['data/policy_operating_domain_v01.json', 'data/policy_operational_v01.json'],
    'test_policy_primitives': ['data/policy_implementation_v01.json', 'data/policy_primitives_v01.json'],
    'test_policy_trace_correspondence': ['data/policy_implementation_binding_v01.json'],
    'test_policy_implementation_binding': ['data/policy_implementation_binding_v01.json', 'data/policy_realization_request_v01.json', 'data/policy_exclusion_source_v01.json'],
    'test_policy_implementation_lowering': ['data/policy_implementation_binding_v01.json'],
    'test_policy_requirement_monitor': ['data/policy_implementation_binding_v01.json'],
    'test_policy_preservation_check': ['data/policy_implementation_binding_v01.json'],
    'test_construction_content': ['data/construction_content_v01.json'],
    'test_policy_mrna_structure': ['data/policy_mrna_structure_v01.json'],
    'test_policy_implementation_service': ['data/policy_implementation_request_v01.json'],
    'test_policy_material_binding': ['data/policy_material_binding_v01.json'],
    'test_policy_component_fragment': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_material': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_assembly_rule': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_assembly_check': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_material_request': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_selection_request': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_material_candidate': ['data/policy_material_request_v01.json'],
    'test_policy_component_context_check': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_component_material_service': ['data/policy_material_request_v01.json', 'data/policy_material_state_v01.json'],
    'test_policy_material_context': ['data/policy_material_context_v01.json'],
    'test_policy_material_check': ['data/policy_material_request_v01.json'],
    'test_policy_material_service': ['data/policy_material_request_v01.json'],
    'test_policy_material_lifecycle': ['data/policy_material_lifecycle_v01.json'],
    'test_policy_material_compound': ['data/policy_material_compound_v01.json'],
    'test_policy_material_domain': ['data/policy_material_domain_v01.json'],
    'test_policy_material_closure': ['data/policy_material_closure_v01.json'],
    'test_policy_material_timing': ['data/policy_material_timing_v01.json'],
    'test_policy_material_state': ['data/policy_material_state_v01.json'],
}


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
        self.assertEqual(len(plan),158)
        manager = next(row for row in plan if row['name']=='test_pipeline_callback_manager')
        self.assertEqual(manager['environment'], ['BIOCOMPILER_PIPELINE_CALLBACK_MANAGER_DECLARATION',
            'BIOCOMPILER_PIPELINE_CONTRACT_LITERALS','BIOCOMPILER_FIXED_PIPELINE_CORPUS'])
        self.assertEqual(bundle.test_plan(DECLARATION)[1]['environment'],['BIOCOMPILER_FIXTURE'])
        policy = next(row for row in plan if row['name']=='test_policy_check')
        self.assertEqual(policy, {'name':'test_policy_check', 'environment':[], 'dependencies':POLICY_FIXTURES})
        for name in ('test_policy_document', 'test_policy_service'):
            self.assertEqual(next(row for row in plan if row['name']==name),
                             {'name':name, 'environment':[], 'dependencies':['data/policy_documents_v01.json']})

    def test_every_operational_dependency_is_exact_ordered_and_source_complete(self):
        plan = bundle.test_plan((ROOT/'core/test/dune').read_text())
        observed = {row['name']:row['dependencies'] for row in plan if 'dependencies' in row}
        self.assertEqual(observed, {**POLICY_OPERATIONAL_FIXTURES,
            'test_policy_check':POLICY_FIXTURES,
            'test_policy_document':['data/policy_documents_v01.json'],
            'test_policy_service':['data/policy_documents_v01.json']})
        self.assertEqual(len(POLICY_OPERATIONAL_FIXTURES),37)
        self.assertEqual(len(observed),40)
        self.assertEqual(len(bundle.dependency_members(ROOT)),23)
        self.assertEqual(len(bundle.expected_members(ROOT)),183)
        self.assertEqual(sum(path.endswith('.exe') for path in bundle.expected_members(ROOT)),160)
        for name, relatives in POLICY_OPERATIONAL_FIXTURES.items():
            declaration = '(test (name '+name+') (modules '+name+') (libraries example) (action (run %{test} '
            arguments = ['%{dep:'+relative+'}' for relative in relatives]
            for changed in ([], arguments+arguments[:1], list(reversed(arguments)) if len(arguments)>1 else ['%{dep:data/unreviewed.json}'],
                            ['%{dep:../'+relatives[0]+'}']+arguments[1:],
                            ['%{dep:/'+relatives[0]+'}']+arguments[1:]):
                with self.subTest(suite=name,arguments=changed), self.assertRaisesRegex(ValueError,'dependency fixture arguments'):
                    bundle.test_plan(declaration+' '.join(changed)+')))')
            for relative in relatives:
                with self.subTest(suite=name,fixture=relative):
                    self.assertTrue((ROOT/'core/test'/relative).is_file())

    def test_unhandled_dune_actions_or_fields_and_duplicate_tests_fail_closed(self):
        for text in (DECLARATION+DECLARATION, DECLARATION+'(rule (action (run other)))',
                     DECLARATION.replace('(libraries example)', '(libraries example) (deps foo)',1),
                     DECLARATION.replace('(run %{test}', '(progn (run %{test}'),
                     DECLARATION.replace('%{env:BIOCOMPILER_FIXTURE=missing}', 'unreviewed'),
                     DECLARATION.replace('(modules test_a)', '(modules test_b)')):
            with self.subTest(text=text),self.assertRaises(ValueError): bundle.test_plan(text)

    def test_dependency_arguments_are_closed_ordered_and_never_paths_from_the_archive(self):
        original = '%{dep:data/policy_frontend_request.json}'
        for changed in ('%{dep:../data/policy_frontend_request.json}',
                        '%{dep:/data/policy_frontend_request.json}',
                        '%{dep:data/../../escaped.json}', '%{dep:data/unreviewed.json}',
                        '%{env:BIOCOMPILER_FIXTURE=missing}', ''):
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, 'dependency fixture arguments'):
                bundle.test_plan(POLICY_DECLARATION.replace(original, changed, 1))
        swapped = POLICY_DECLARATION.replace('policy_frontend_request.json', 'temporary.json').replace(
            'policy_frontend_submission.json', 'policy_frontend_request.json').replace('temporary.json', 'policy_frontend_submission.json')
        with self.assertRaisesRegex(ValueError, 'dependency fixture arguments'):
            bundle.test_plan(swapped)
        with self.assertRaisesRegex(ValueError, 'Unsupported native test argument'):
            bundle.test_plan(DECLARATION.replace('%{env:BIOCOMPILER_FIXTURE=missing}', original))

    def policy_bundle(self):
        (self.source/'core/test/dune').write_text(POLICY_DECLARATION)
        for index, relative in enumerate(POLICY_FIXTURES):
            path = self.source/'core/test'/relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({'original_fixture':index}))
        for name in ('test_policy_check', 'test_policy_service'):
            (self.source/'core/_build/default/test'/(name+'.exe')).write_bytes(b'INERT: mocked subprocess only')
        archive = self.root/'policy.zip'
        bundle.bundle(self.source, archive)
        return archive

    def policy_destination(self, name):
        root = self.destination(name)
        (root/'core/test/dune').write_text(POLICY_DECLARATION)
        for relative in POLICY_FIXTURES:
            path = root/'core/test'/relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((self.source/'core/test'/relative).read_bytes())
        return root

    def test_source_dependencies_are_bundled_pinned_restored_and_dispatched_in_exact_order(self):
        archive = self.policy_bundle()
        target = self.policy_destination('policy-roundtrip')
        document = bundle.restore(target, archive)
        for relative in POLICY_FIXTURES:
            original = self.source/'core/test'/relative
            member = 'core/_build/default/test/'+relative
            self.assertEqual(document['files'][member], bundle.file_pin(original))
            self.assertEqual((target/member).read_bytes(), original.read_bytes())
            self.assertFalse(os.access(target/member, os.X_OK))
        observed = []
        def execute(command, **kwargs):
            observed.append(command)
            kwargs['stdout'].write(b'inert source fixture scheduling\n')
            return subprocess.CompletedProcess(command, 0)
        with patch.dict(os.environ, {}, clear=True), patch.object(bundle.subprocess, 'run', side_effect=execute):
            bundle.run_tests(target, self.root/'policy-results', 2)
        expected = {name: [str(target/'core/_build/default/test'/relative) for relative in relatives]
                    for name, relatives in [('test_policy_check', POLICY_FIXTURES),
                                            ('test_policy_service', ['data/policy_documents_v01.json'])]}
        self.assertEqual({Path(argv[0]).stem:argv[1:] for argv in observed}, expected)

    def test_changed_missing_symlinked_or_repinned_source_fixtures_cannot_restore(self):
        archive = self.policy_bundle()
        for mutation in ('missing', 'changed', 'symlink', 'parent-symlink', 'repinned-archive'):
            target = self.policy_destination('policy-'+mutation)
            path = target/'core/test/data/policy_frontend_request.json'
            selected = archive
            if mutation=='missing': path.unlink()
            elif mutation=='changed': path.write_text('{"changed":true}')
            elif mutation=='symlink':
                path.unlink(); path.symlink_to(self.source/'core/test/data/policy_frontend_request.json')
            elif mutation=='parent-symlink':
                data = target/'core/test/data'
                data.rename(target/'core/test/original-data'); data.symlink_to(target/'core/test/original-data', target_is_directory=True)
            else:
                with zipfile.ZipFile(archive) as source:
                    entries = {name:source.read(name) for name in source.namelist()}
                member = 'core/_build/default/test/data/policy_frontend_request.json'
                entries[member] = b'{"changed":true}'
                document = json.loads(entries['manifest.json'])
                document['files'][member] = {'sha256':hashlib.sha256(entries[member]).hexdigest(), 'size':len(entries[member])}
                entries['manifest.json'] = json.dumps(document).encode()
                selected = self.root/'repinned-policy.zip'
                with zipfile.ZipFile(selected, 'w') as damaged:
                    for name, raw in entries.items(): damaged.writestr(name, raw)
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ValueError, 'native dependency fixture|Native dependency fixture'):
                bundle.restore(target, selected)
            self.assertFalse((target/'core/_build').exists())

    def test_dependency_change_after_restore_prevents_every_test_dispatch(self):
        archive = self.policy_bundle()
        for mutation in ('original', 'restored', 'restored-symlink'):
            target = self.policy_destination('late-'+mutation)
            bundle.restore(target, archive)
            relative = ('core/test' if mutation=='original' else 'core/_build/default/test')+'/data/policy_documents_v01.json'
            path = target/relative
            if mutation=='restored-symlink':
                path.unlink(); path.symlink_to(target/'core/test/data/policy_documents_v01.json')
            else: path.write_text('{"changed":true}')
            with self.subTest(mutation=mutation), patch.object(bundle.subprocess, 'run') as child:
                with self.assertRaisesRegex(ValueError, 'native dependency fixture|Native dependency fixture'):
                    bundle.run_tests(target, target/'results', 2)
                child.assert_not_called()

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
