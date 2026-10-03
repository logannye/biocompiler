"""Exact draft CI/source topology; no hosted or native operations execute."""
import ast
import hashlib
import importlib.util
from importlib.machinery import SourceFileLoader
import os
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'tests/conformance/prebuilt-source-v1'
CONTEXT_DELTA=ROOT/'tests/conformance/deferred-context-checker-source-delta-v1.json'
CONTEXT_DELTA_SHA256='c052ed313423f5b4a016b8f8474d50a9364e278904983f3d139eb9e1ca8e4253'
PROVIDER_DELTA=ROOT/'tests/conformance/fixed-provider-checker-source-delta-v1.json'
PROVIDER_DELTA_SHA256='67c11513477659bb81c2e9a0cfb87191fd669cf2caf2acce0962e77f54a50b8b'


def restore_deferred_context_source(current, proof_bytes):
    """Recover the exact installed-path checkpoint before its later proof fix."""
    def require(condition,message):
        if not condition:raise AssertionError(message)
    require(hashlib.sha256(proof_bytes).hexdigest()==CONTEXT_DELTA_SHA256,
        'Unreviewed deferred-context source witness')
    proof=json.loads(proof_bytes)
    require(set(proof)=={'schema','path','historical','current','spans'}
        and proof['schema']=='biocompiler.deferred_context_checker_source_delta.v1'
        and proof['path']=='tools/check_pipeline_manager_install.py',
        'Deferred-context witness shape differs')
    require(proof['current']=={'bytes':len(current),'sha256':hashlib.sha256(current).hexdigest()},
        'Current checker differs from the reviewed deferred-context correction')
    spans=proof['spans']
    require(type(spans) is list and len(spans)==2 and all(set(row)=={'offset','before','after'}
        and type(row['offset']) is int and row['offset']>=0
        and type(row['before']) is str and type(row['after']) is str for row in spans),
        'Deferred-context source span census differs')
    addition=ast.parse(spans[0]['after'])
    require(spans[0]['before']=='' and len(addition.body)==1
        and isinstance(addition.body[0],ast.FunctionDef)
        and addition.body[0].name=='deferred_context_document',
        'Deferred-context source addition is not its single proof function')
    require(spans[1]['before']=='equal(contexts[-1]["arguments"]["document"], values["context"], "Deferred callback read a context different from native authority")'
        and spans[1]['after']=='equal(deferred_context_document(contexts[-1], native), values["context"],\n                "Deferred callback read a context different from native authority")'
        and spans[0]['offset']<spans[1]['offset'],
        'Deferred-context comparison call is not the single reviewed substitution')
    restored=current
    for index,row in reversed(list(enumerate(spans))):
        offset=row['offset']+sum(len(prior['after'].encode())-len(prior['before'].encode()) for prior in spans[:index])
        before,after=row['before'].encode(),row['after'].encode()
        require(restored[offset:offset+len(after)]==after,'Deferred-context source span bytes differ')
        restored=restored[:offset]+before+restored[offset+len(after):]
    require(proof['historical']=={'revision':'817a8ed1154975befd293327dfabdf7798ed2b4c',
        'bytes':len(restored),'sha256':hashlib.sha256(restored).hexdigest()},
        'Complete historical installed-path checker source differs')
    return restored


def restore_fixed_provider_source(current, proof_bytes):
    """Recover the complete installed-path checker before its lineage fix."""
    def require(condition,message):
        if not condition:raise AssertionError(message)
    require(hashlib.sha256(proof_bytes).hexdigest()==PROVIDER_DELTA_SHA256,
        'Unreviewed fixed-provider source witness')
    proof=json.loads(proof_bytes)
    require(set(proof)=={'schema','path','historical','current','spans'}
        and proof['schema']=='biocompiler.fixed_provider_checker_source_delta.v1'
        and proof['path']=='tools/check_pipeline_fixed_provider_install.py',
        'Fixed-provider witness shape differs')
    require(proof['current']=={'bytes':len(current),'sha256':hashlib.sha256(current).hexdigest()},
        'Current fixed-provider checker differs from the reviewed lineage correction')
    spans=proof['spans']
    require(type(spans) is list and len(spans)==1
        and set(spans[0])=={'offset','before','after'}
        and type(spans[0]['offset']) is int and spans[0]['offset']>=0
        and all(type(spans[0][name]) is str and spans[0][name] for name in ('before','after')),
        'Fixed-provider source span census differs')
    row=spans[0];offset=row['offset'];before=row['before'].encode();after=row['after'].encode()
    require(current[offset:offset+len(after)]==after,'Fixed-provider source span bytes differ')
    restored=current[:offset]+before+current[offset+len(after):]
    require(proof['historical']=={'revision':'0dd0fe54f3d1f0e502b30188f096cb5387fbb9b2',
        'bytes':len(restored),'sha256':hashlib.sha256(restored).hexdigest()},
        'Complete historical fixed-provider checker source differs')
    return restored


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path,loader=SourceFileLoader(name,str(path)));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


class HostedCiPlanTests(unittest.TestCase):
    def setUp(self):
        import hashlib,json
        raw=(ROOT/'tests/conformance/prebuilt-source-v1.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'d679ec6aaf09cb0fc1ba56c42bf72b85b3184b37f34456633f76139b4274363d')
        for name,pin in json.loads(raw)['files'].items():
            content=Path(str(SOURCE/name)+'.source').read_bytes()
            self.assertEqual({'sha256':hashlib.sha256(content).hexdigest(),'size':len(content)},pin)
        self.old=(SOURCE/'.github/workflows/ci.yml.source').read_text()
        self.new=(ROOT/'.github/workflows/ci.yml').read_text()

    def test_every_previous_required_job_and_variant_remains_with_two_additions(self):
        old=load('old_ci_validation',SOURCE/'tools/ci_validation.py.source');new=load('draft_ci_validation',ROOT/'tools/ci_validation.py')
        self.assertEqual(new.REQUIRED_NEEDS-old.REQUIRED_NEEDS,{'prebuilt-core-assembly','prebuilt-core-validation'})
        self.assertEqual(old.REQUIRED_NEEDS-new.REQUIRED_NEEDS,set())
        self.assertEqual(new.EXPECTED_RECEIPTS-old.EXPECTED_RECEIPTS,{('prebuilt-core-assembly','cross-platform'),('prebuilt-core-validation','cross-platform')})
        self.assertEqual(new.REALIZATION_VARIANTS,old.REALIZATION_VARIANTS)
        self.assertEqual(new.workflow_jobs(ROOT/'.github/workflows/ci.yml'),new.REQUIRED_NEEDS|{'validation'})

    def test_every_native_test_command_survives_and_static_preparation_precedes_dependencies(self):
        before=re.findall(r'core/_build/default/test/[^\n]+',self.old)
        after=re.findall(r'core/_build/default/test/[^\n]+',self.new)
        self.assertEqual(after,before)
        self.assertLess(self.new.index('tools/prebuilt_sources.py static-build'),self.new.index('opam install core/biocompiler_core.opam'))
        self.assertIn('opam reinstall zarith.1.14 --yes --no-depexts',self.new)
        self.assertLess(self.new.index('Retain revision-bound native executables'),self.new.index('tools/build_prebuilt_core.py wheel'))
        self.assertIn('native_build',self.new)

    def test_fresh_four_runtime_slots_have_no_source_install_or_dynamic_gmp_fallback(self):
        block=self.new.split('  realization-conformance:',1)[1].split('  realization-core-reproducibility:',1)[0]
        self.assertEqual(block.count('python-version: "3.11"'),2);self.assertEqual(block.count('python-version: "3.14"'),2)
        self.assertIn('needs: [ocaml-core, prebuilt-core-assembly]',block)
        self.assertIn('tools/prebuilt_release_pipeline.py installed',block)
        self.assertNotIn('pip install .',block);self.assertNotIn('brew install',block);self.assertNotIn('--prepare',block)
        self.assertIn('$RUNNER_TEMP/biocompiler-fresh-',block)

    def test_hosted_audit_selection_resolves_tool_symlinks_without_relaxing_release_inputs(self):
        lines=self.new.splitlines()
        index=next(i for i,line in enumerate(lines) if 'audit_tool="$(command -v otool)"' in line)
        selection=lines[index].strip();resolution=lines[index+1].strip()
        self.assertEqual(resolution,
            'audit_tool="$(python -c \'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve(strict=True))\' "$audit_tool")"')
        release=load('hosted_audit_release',ROOT/'tools/build_prebuilt_core.py')
        policy=load('hosted_audit_policy',ROOT/'tests/test_prebuilt_core_release.py')
        bash=shutil.which('bash');self.assertIsNotNone(bash)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();bin_path=root/'bin';bin_path.mkdir()
            (bin_path/'python').symlink_to(Path(sys.executable).resolve())
            artifact=root/'artifact';artifact.write_bytes(b'nonexecuted native-byte fixture')
            for runner_os,name,target,output in (
                    ('Linux','readelf','linux-x86_64',policy.ELF),
                    ('macOS','otool','macos-arm64',policy.MACHO)):
                with self.subTest(runner_os=runner_os):
                    actual=root/(name+'-actual');actual.write_bytes(b'nonexecuted audit fixture: '+name.encode());actual.chmod(0o755)
                    selected=bin_path/name;selected.symlink_to(actual)
                    script='\n'.join((selection.replace('${{ runner.os }}',runner_os),resolution,'printf \'%s\\n\' "$audit_tool"'))
                    resolved=subprocess.run([bash,'-e','-c',script],env={**os.environ,'PATH':str(bin_path)},
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=10)
                    self.assertEqual(resolved.stderr,b'')
                    canonical=Path(resolved.stdout.decode().rstrip('\n'))
                    self.assertEqual(canonical,actual);self.assertFalse(canonical.is_symlink())
                    completed=subprocess.CompletedProcess([],0,stdout=output.encode(),stderr=b'')
                    with patch.object(release.subprocess,'run',return_value=completed) as invoked:
                        with self.assertRaisesRegex(ValueError,'symlinked'):
                            release.audit(selected,artifact,target)
                        receipt=release.audit(canonical,artifact,target)
                    self.assertEqual(receipt['argv'][0],str(actual))
                    self.assertEqual(receipt['tool_sha256'],release.sha(actual.read_bytes()))
                    self.assertEqual(invoked.call_args.args[0],receipt['argv'])
                    artifact_link=root/(name+'-artifact-link');artifact_link.symlink_to(artifact)
                    with self.assertRaisesRegex(ValueError,'symlinked'):
                        release.regular(artifact_link,1024)

    def test_sdk_assembly_pins_build_tools_and_both_material_companions(self):
        block=self.new.split('  prebuilt-core-assembly:',1)[1].split('  prebuilt-core-validation:',1)[0]
        self.assertIn('needs: ocaml-core',block)
        self.assertEqual(block.count('tools/check_prebuilt_core_release.py'),2)
        self.assertIn('--only-binary=:all: --require-hashes',block)
        self.assertIn('prebuilt-linux-x86_64',block);self.assertIn('prebuilt-macos-arm64',block)
        self.assertIn('--sdk generated/prebuilt-wheelhouse/',block)
        requirements=(ROOT/'tools/prebuilt-build-requirements.txt').read_text().splitlines()
        self.assertEqual(len(requirements),5)
        self.assertTrue(all(re.fullmatch(r'[a-z-]+==[0-9.]+ --hash=sha256:[0-9a-f]{64}',line) for line in requirements))

    def test_installed_path_edits_are_finite_and_no_semantic_case_body_is_changed(self):
        import json,hashlib
        proof=json.loads((ROOT/'tests/conformance/prebuilt-installed-path-delta-v1.json').read_bytes())
        self.assertEqual(len(proof),14)
        for name,row in proof.items():
            old=Path(str(SOURCE/name)+'.source').read_text();new=(ROOT/name).read_bytes()
            if name=='tools/check_pipeline_manager_install.py':
                new=restore_deferred_context_source(new,CONTEXT_DELTA.read_bytes())
            elif name=='tools/check_pipeline_fixed_provider_install.py':
                new=restore_fixed_provider_source(new,PROVIDER_DELTA.read_bytes())
            new=new.decode()
            self.assertEqual(hashlib.sha256(new.encode()).hexdigest(),row['current_sha256'])
            old_ast=ast.parse(old);new_ast=ast.parse(new)
            old_functions={n.name:n for n in old_ast.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
            new_functions={n.name:n for n in new_ast.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
            self.assertEqual(set(old_functions),set(new_functions))
            changed=[name for name,node in old_functions.items() if ast.dump(node)!=ast.dump(new_functions[name])]
            self.assertEqual(len(changed),1,name)
            self.assertIn(changed[0],('campaign_main','main'),name)
        self.assertIn('  prebuilt-core-validation:',self.new)
        block=self.new.split('  prebuilt-core-validation:',1)[1].split('  validation:',1)[0]
        self.assertIn('realization-core-reproducibility',block)
        self.assertEqual(block.count('name: realization-'),4)

    def test_deferred_context_restoration_rejects_unreviewed_or_extra_source_changes(self):
        current=(ROOT/'tools/check_pipeline_manager_install.py').read_bytes()
        witness=CONTEXT_DELTA.read_bytes();proof=json.loads(witness)
        restored=restore_deferred_context_source(current,witness)
        self.assertEqual(hashlib.sha256(restored).hexdigest(),
            'd12f67bf4080b15a96856342e87e8678007e6093188b1a36540c7f337f6463b7')
        mutants={
            'stale historical bytes':restored,
            'added proof body':current.replace(b'and outcome["value"] is True',b'and outcome["value"] == True'),
            'comparison call':current.replace(proof['spans'][1]['after'].encode(),proof['spans'][1]['before'].encode()),
            'outside original body':current.replace(b'def validate_deferred_accesses(',b'def unchecked_accesses('),
            'extra function':current+b'\ndef unreviewed():\n    return True\n',
            'newline normalization':current.replace(b'\n',b'\r\n'),
        }
        for name,mutant in mutants.items():
            with self.subTest(change=name):
                self.assertNotEqual(mutant,current)
                with self.assertRaisesRegex(AssertionError,'Current checker differs'):
                    restore_deferred_context_source(mutant,witness)
                # Rehashing the source or editing a span cannot turn new bytes
                # into a newly approved witness; its complete pin is separate.
                changed=json.loads(witness)
                changed['current']={'bytes':len(mutant),'sha256':hashlib.sha256(mutant).hexdigest()}
                with self.assertRaisesRegex(AssertionError,'Unreviewed deferred-context source witness'):
                    restore_deferred_context_source(mutant,json.dumps(changed,sort_keys=True,indent=2).encode()+b'\n')
        changed=json.loads(witness);changed['spans'][0]['offset']+=1
        with self.assertRaisesRegex(AssertionError,'Unreviewed deferred-context source witness'):
            restore_deferred_context_source(current,json.dumps(changed,sort_keys=True,indent=2).encode()+b'\n')


    def test_fixed_provider_restoration_rejects_unreviewed_source_changes(self):
        current=(ROOT/'tools/check_pipeline_fixed_provider_install.py').read_bytes()
        witness=PROVIDER_DELTA.read_bytes();proof=json.loads(witness)
        restored=restore_fixed_provider_source(current,witness)
        original=json.loads((ROOT/'tests/conformance/prebuilt-installed-path-delta-v1.json').read_bytes())
        self.assertEqual(hashlib.sha256(restored).hexdigest(),
            original['tools/check_pipeline_fixed_provider_install.py']['current_sha256'])
        mutants={
            'stale historical bytes':restored,
            'changed lineage target':current.replace(b'src/biocompiler/compiler/pipeline.py',b'src/biocompiler/compiler/unreviewed.py'),
            'extra function':current+b'\ndef unreviewed():\n    return True\n',
            'newline normalization':current.replace(b'\n',b'\r\n'),
        }
        for name,mutant in mutants.items():
            with self.subTest(change=name):
                self.assertNotEqual(mutant,current)
                with self.assertRaisesRegex(AssertionError,'Current fixed-provider checker differs'):
                    restore_fixed_provider_source(mutant,witness)
                changed=json.loads(witness)
                changed['current']={'bytes':len(mutant),'sha256':hashlib.sha256(mutant).hexdigest()}
                with self.assertRaisesRegex(AssertionError,'Unreviewed fixed-provider source witness'):
                    restore_fixed_provider_source(mutant,json.dumps(changed,sort_keys=True,indent=2).encode()+b'\n')
        changed=json.loads(witness);changed['spans'][0]['offset']+=1
        with self.assertRaisesRegex(AssertionError,'Unreviewed fixed-provider source witness'):
            restore_fixed_provider_source(current,json.dumps(changed,sort_keys=True,indent=2).encode()+b'\n')


if __name__=='__main__':unittest.main()
