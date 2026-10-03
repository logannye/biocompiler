"""Exact draft CI/source topology; no hosted or native operations execute."""
import ast
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'tests/conformance/prebuilt-source-v1'


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
            old=Path(str(SOURCE/name)+'.source').read_text();new=(ROOT/name).read_text()
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


if __name__=='__main__':unittest.main()
