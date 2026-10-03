"""Pure SDK/installed receipt adversaries; do not build or install any wheel."""
from copy import deepcopy
import base64
import csv
import hashlib
import importlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
with patch.object(sys,'path',[str(ROOT/'tools'),*sys.path]):
    check=importlib.import_module('check_prebuilt_core_release')
    matrix=importlib.import_module('check_prebuilt_matrix')
    pipeline=importlib.import_module('prebuilt_release_pipeline')
    build=importlib.import_module('build_prebuilt_core')


def record(entries):
    info='biocompiler-'+build.VERSION+'.dist-info/'
    path=info+'RECORD';text=io.StringIO(newline='');writer=csv.writer(text,lineterminator='\n')
    for name,(raw,_) in sorted(entries.items()):
        if name!=path:writer.writerow([name,'sha256='+base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode(),str(len(raw))])
    writer.writerow([path,'','']);entries[path]=(text.getvalue().encode(),0o644);return entries


class SdkWheelTests(unittest.TestCase):
    def setUp(self):
        self.sources={'biocompiler/__init__.py':b'__version__="0.1.0.dev29"\n','biocompiler/py.typed':b'',
            'biocompiler/studio/static/app.js':b'actual fixture static bytes','biocompiler/studio/data/data.json':b'{}'}
        self.release={'schema_version':'biocompiler.core_release.v1','sdk_version':build.VERSION,
            'distribution':'biocompiler-core','distribution_version':build.VERSION,'source_revision':'a'*40,
            'tested_revision':'b'*40,'run_id':'123','platforms':{name:str(i)*64 for i,name in enumerate(build.TARGETS,1)}}
        info='biocompiler-'+build.VERSION+'.dist-info/'
        self.entries={name:(raw,0o644) for name,raw in self.sources.items()}
        self.entries['biocompiler/_core_release.json']=(build.canonical(self.release),0o644)
        self.entries.update({info+'METADATA':(('Metadata-Version: 2.4\nName: biocompiler\nVersion: '+build.VERSION+
            '\nRequires-Python: >=3.11\nProvides-Extra: core\nRequires-Dist: biocompiler-core=='+build.VERSION+'; extra == "core"\n\n').encode(),0o644),
            info+'WHEEL':(b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n',0o644),
            info+'entry_points.txt':(b'[console_scripts]\nbiocompiler = biocompiler.cli:main\n',0o644)})
        record(self.entries)
    def verify(self):check.validate_sdk(self.entries,source_files=self.sources,release=self.release)
    def test_complete_sdk_source_resources_cli_and_exact_optional_native_pin(self):self.verify()
    def test_repaired_record_cannot_remove_studio_resource_or_change_source(self):
        del self.entries['biocompiler/studio/static/app.js'];record(self.entries)
        with self.assertRaisesRegex(ValueError,'source/resource'):self.verify()
    def test_repaired_sdk_release_or_dependency_pin_fails(self):
        original=dict(self.entries);changed=deepcopy(self.release);changed['platforms']['linux-x86_64']='0'*64
        self.entries['biocompiler/_core_release.json']=(build.canonical(changed),0o644);record(self.entries)
        with self.assertRaisesRegex(ValueError,'release pins'):self.verify()
        self.entries=original;name='biocompiler-'+build.VERSION+'.dist-info/METADATA'
        self.entries[name]=(self.entries[name][0].replace(b'biocompiler-core==',b'biocompiler-core>='),0o644);record(self.entries)
        with self.assertRaisesRegex(ValueError,'exact optional'):self.verify()
    def test_unknown_metadata_or_executable_sdk_member_rejects(self):
        self.entries['biocompiler-'+build.VERSION+'.dist-info/custom.py']=(b'anything',0o644);record(self.entries)
        with self.assertRaisesRegex(ValueError,'unreviewed distribution'):self.verify()


class MatrixTests(unittest.TestCase):
    def setUp(self):
        self.expected={'source_revision':'a'*40,'tested_revision':'b'*40,'run_id':'123'}
        self.manifest={'files':{'bin/biocompiler-core':{'sha256':'c'*64,'size':10},'bin/biocompiler-verify':{'sha256':'d'*64,'size':11}}}
        self.binaries=build.canonical({'revision':'b'*40,'system':'Linux','machine':'x86_64',
            'sha256':{'biocompiler-core':'c'*64,'biocompiler-verify':'d'*64}})
        self.manifest['files']['binaries.json']={'sha256':build.sha(self.binaries),'size':len(self.binaries)}
        self.release={'platforms':{'linux-x86_64':hashlib.sha256(build.canonical(self.manifest)).hexdigest()}}
        self.candidate={'release':self.release,'distributions':{'linux-x86_64':self.manifest}}
        self.owner={**self.expected,'package_root':'/fresh/site/biocompiler_core','native_platform':'linux-x86_64',
            'distribution_sha256':self.release['platforms']['linux-x86_64'],'release_sha256':hashlib.sha256(build.canonical(self.release)).hexdigest(),
            'files':{name:{'path':'/fresh/site/biocompiler_core/'+name,**pin} for name,pin in self.manifest['files'].items()}}
        python=Path('/fresh/bin/python');sdk=Path('/wheel/biocompiler-'+build.VERSION+'-py3-none-any.whl')
        native=Path('/wheel/biocompiler_core-'+build.VERSION+'-'+build.TARGETS['linux-x86_64'][2]+'.whl')
        installation=pipeline.install_plan(Path('/python'),python,sdk,native)
        plans=[*pipeline.lifecycle_plan(Path('/python'),python,Path('/checkout'),Path('/evidence'),sdk,native,self.expected),
            *pipeline.campaign_plan(Path('/checkout'),python,self.owner,Path('/evidence'))]
        self.raw={name+'.log':b'full actual command log\n' for name,_ in plans}
        self.raw.update({name+'.json':b'{"full":"original receipt"}\n' for _,name in pipeline.CAMPAIGNS})
        self.raw['smoke.json']=build.canonical({**self.expected,'python_version':'3.11.15','roles':{
            role:{key:self.owner['files']['bin/biocompiler-'+role][key] for key in ('path','sha256')} for role in ('core','verify')},
            'process_lifecycle':{'reaped':True,'attempts':1}})
        self.raw['native-inputs.json']=build.canonical({'schema_version':'biocompiler.native_conformance_inputs.v1','status':'pass',
            'revision':self.expected['tested_revision'],'source_revision':self.expected['source_revision'],'run_id':'123',
            'native_platform':'linux-x86_64','system':'Linux','machine':'x86_64','manifest_sha256':build.sha(self.binaries),
            'python_version':'3.11.15','sha256':{'biocompiler-core':'c'*64,'biocompiler-verify':'d'*64}})
        self.receipt={'schema_version':'biocompiler.prebuilt_installed_campaign.v1','status':'pass',**self.expected,'native_platform':'linux-x86_64','python_version':'3.11.15 actual',
            'ownership_before':self.owner,'ownership_after':deepcopy(self.owner),'commands':[
                {'argv':command,'cwd':'/evidence' if name=='create-environment' else '/fresh','returncode':0,'log':{'path':name+'.log','sha256':hashlib.sha256(self.raw[name+'.log']).hexdigest(),'size':len(self.raw[name+'.log'])}} for name,command in plans],
            'campaigns':[{'name':name,'receipt_sha256':hashlib.sha256(self.raw[name+'.json']).hexdigest()} for _,name in pipeline.CAMPAIGNS]}
    def verify(self):return matrix.validate_slot(self.receipt,self.expected,'linux-x86_64','3.11',self.candidate,self.raw.__getitem__)
    def test_complete_phase_and_campaign_census_is_accepted(self):self.verify()
    def test_missing_campaign_failed_command_or_wrong_runtime_rejects(self):
        original=deepcopy(self.receipt)
        for mutate in (lambda r:r['campaigns'].pop(),lambda r:r['commands'][8].update(returncode=1),lambda r:r.update(python_version='3.14.6')):
            self.receipt=deepcopy(original);mutate(self.receipt)
            with self.assertRaises(ValueError):self.verify()
    def test_fully_repaired_owned_role_pin_cannot_change_candidate(self):
        for field in ('ownership_before','ownership_after'):
            self.receipt[field]['files']['bin/biocompiler-core']['sha256']='e'*64
        with self.assertRaisesRegex(ValueError,'independently verified candidate'):self.verify()
    def test_repaired_lifecycle_cannot_skip_actual_uninstall_or_missing_probe(self):
        original=deepcopy(self.receipt)
        for index in (0,2,3,4):
            self.receipt=deepcopy(original);self.receipt['commands'][index]['argv']=['/fresh/bin/python','-c','pass']
            with self.subTest(index=index),self.assertRaises(ValueError):self.verify()
    def test_repaired_command_cannot_use_artifact_mirror_or_subset(self):
        self.receipt['commands'][6]['argv'][3]='/artifact/biocompiler-core'
        with self.assertRaisesRegex(ValueError,'owned-path recipe'):self.verify()


if __name__=='__main__':unittest.main()
