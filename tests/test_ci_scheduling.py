"""Parallel scheduling must retain full executable and installed coverage."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from tests import test_prebuilt_sdk_matrix as fixtures
from tests import test_ci_validation as gate_fixtures
from tools import ci_validation as ci
from tools import prebuilt_release_pipeline as pipeline
from tools import check_prebuilt_matrix as matrix

ROOT=Path(__file__).resolve().parents[1]


class SchedulingTests(unittest.TestCase):
    def test_complete_campaign_partition_and_all_runtime_jobs_are_required(self):
        names=pipeline.campaign_names()
        self.assertEqual(len(names),17)
        assigned=[name for group in pipeline.CAMPAIGN_GROUPS for name in pipeline.campaign_names(group)]
        self.assertEqual(len(assigned),len(set(assigned)))
        self.assertEqual(set(assigned),set(names))
        self.assertEqual(assigned,names)
        self.assertEqual(pipeline.CAMPAIGN_GROUPS,{
            'protocol':('protocol',), 'manager':('routing','pipeline-manager'),
            'fixed':('pipeline-fixed-providers','pipeline-fixed-continuations',
                     'pipeline-fixed-registration','pipeline-reference','pipeline-session'),
            'workflow':('workflow','workflow-presentation','workflow-authority','workflow-public-sdk','workflow-cli'),
            'synthetic':('synthetic-producer','synthetic-public-sdk','synthetic-selection-cli','synthetic-inspection')})
        self.assertEqual(len(ci.CAMPAIGN_VARIANTS),20)
        self.assertEqual(len(ci.EXPECTED_RECEIPTS),53)
        self.assertEqual(len(ci.REALIZATION_VARIANTS),4)
        plan_fixture=fixtures.MatrixTests();plan_fixture.setUp()
        plan_args=(Path('/checkout'),Path('/fresh/bin/python'),plan_fixture.owner,Path('/evidence'))
        complete=pipeline.campaign_plan(*plan_args)
        grouped=[row for group in pipeline.CAMPAIGN_GROUPS for row in pipeline.campaign_plan(*plan_args,group)]
        self.assertEqual(grouped,complete)
        self.assertEqual([name for name,_ in complete],names)
        fixture=gate_fixtures.ValidationGateTests()
        for job in ('ci-preflight','ocaml-build','ocaml-native-tests','architecture-sdk','installed-campaigns'):
            args=fixture.fixture()
            self.assertEqual(ci.validate(*args)['status'],'pass')
            receipt=next(row for row in args[1] if row['job']==job)
            args[1].remove(receipt)
            self.assertEqual(ci.validate(*args)['status'],'fail')
            args=fixture.fixture();args[0][job]['result']='skipped'
            self.assertEqual(ci.validate(*args)['status'],'fail')
        for variant in ci.CAMPAIGN_VARIANTS:
            args=fixture.fixture()
            row=next(row for row in args[1] if row['job']=='installed-campaigns' and row['variant']==variant)
            row['machine']='unreviewed'
            self.assertEqual(ci.validate(*args)['status'],'fail')

    def test_omitted_repeated_or_unreviewed_campaign_groups_fail_before_execution(self):
        for change in ({'manager':()}, {'manager':('protocol',)}, {'manager':('unreviewed',)}):
            with patch.dict(pipeline.CAMPAIGN_GROUPS,change):
                with self.assertRaisesRegex(ValueError,'omit or repeat'):pipeline.campaign_names()
        with self.assertRaisesRegex(ValueError,'Unknown campaign group'):pipeline.campaign_names('unknown')

    def test_workflow_removes_long_campaigns_from_build_critical_path(self):
        text=(ROOT/'.github/workflows/ci.yml').read_text()
        jobs={m.group(1):m.group(2) for m in re.finditer(r'^  ([a-z][a-z0-9-]*):\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)',text.split('\njobs:\n',1)[1],re.M|re.S)}
        self.assertEqual(set(jobs),ci.REQUIRED_NEEDS|{'validation'})
        build=jobs['ocaml-build']
        self.assertIn('needs: ci-preflight',build)
        self.assertEqual(text.count('opam exec -- dune build --root core @all'),1)
        self.assertIn('tools/build_prebuilt_core.py wheel',build)
        self.assertIn('tools/ci_native_bundle.py bundle',build)
        for command in ('check_architecture_routing.py','dune runtest','check_pipeline_manager_install.py'):
            self.assertNotIn(command,build)
        self.assertIn('needs: ocaml-build',jobs['prebuilt-core-assembly'])
        for job in ('ocaml-core','ocaml-native-tests','architecture-sdk'):
            self.assertIn('needs: ocaml-build',jobs[job])
            self.assertIn('tools/ci_native_bundle.py restore',jobs[job])
            self.assertNotIn('dune build',jobs[job])
        installed=jobs['installed-campaigns']
        self.assertIn('needs: [ocaml-build, prebuilt-core-assembly]',installed)
        self.assertIn('max-parallel: 8',installed)
        self.assertIn('--group ${{ matrix.group }}',installed)
        rows=re.findall(r'platform: ([a-z0-9_-]+)\n            python-version: "([0-9.]+)"\n            group: ([a-z]+)',installed)
        self.assertEqual(len(rows),20)
        self.assertEqual({f'{platform}-py{version}-{group}' for platform,version,group in rows},set(ci.CAMPAIGN_VARIANTS))
        self.assertIn('needs: [installed-campaigns, prebuilt-core-assembly]',jobs['realization-conformance'])
        self.assertIn('prebuilt_release_pipeline.py aggregate',jobs['realization-conformance'])
        for name in pipeline.CAMPAIGN_GROUPS:
            self.assertIn('path: artifacts/groups/'+name,jobs['realization-conformance'])
        release_needs=jobs['prebuilt-core-validation'].split('needs: [',1)[1].split(']',1)[0].split(', ')
        self.assertEqual(set(release_needs),matrix.REQUIRED_RELEASE_NEEDS)
        self.assertTrue({'ocaml-core','ocaml-native-tests','architecture-sdk','architecture-core-reproducibility'} <= set(release_needs))


class PartitionedReceiptTests(unittest.TestCase):
    def setUp(self):
        fixture=fixtures.MatrixTests();fixture.setUp()
        self.expected=fixture.expected;self.candidate={**fixture.candidate,**self.expected,'status':'pass','sdk':{'status':'pass'}}
        self.parts={};self.files={}
        for group,names in pipeline.CAMPAIGN_GROUPS.items():
            receipt=deepcopy(fixture.receipt)
            receipt.update(schema_version='biocompiler.prebuilt_installed_campaign.v2',campaign_group=group)
            receipt['native_inputs_sha256']=hashlib.sha256(fixture.raw['native-inputs.json']).hexdigest()
            receipt['campaigns']=[row for row in receipt['campaigns'] if row['name'] in names]
            allowed={name+'.log' for name in (*pipeline.LIFECYCLE_NAMES,*names)}
            receipt['commands']=[{**row,'duration_seconds':1.25} for row in receipt['commands'] if row['log']['path'] in allowed]
            self.parts[group]=receipt
            self.files[group]={key:value for key,value in fixture.raw.items() if key in allowed or key in ('smoke.json','native-inputs.json')
                               or key in {name+'.json' for name in names}}
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.args=argparse.Namespace(root=self.root/'groups',output=self.root/'complete',candidate=self.root/'candidate.json',
            platform='linux-x86_64',python_minor='3.11',**self.expected)
        self.args.candidate.write_text(json.dumps(self.candidate))

    def write_groups(self):
        for group,receipt in self.parts.items():
            directory=self.args.root/group;directory.mkdir(parents=True,exist_ok=True)
            for name,raw in self.files[group].items():(directory/name).write_bytes(raw)
            (directory/'installed-release.json').write_text(json.dumps(receipt))

    def verify(self):
        document=json.loads((self.args.output/'installed-release.json').read_bytes())
        return matrix.validate_partitioned_slot(document,self.expected,'linux-x86_64','3.11',self.candidate,
            lambda name:(self.args.output/name).read_bytes())

    def test_all_groups_reconstruct_complete_census_with_separate_lifecycle_logs(self):
        self.assertEqual([row['name'] for row in self.parts['protocol']['campaigns']],['protocol'])
        self.assertEqual([row['name'] for row in self.parts['manager']['campaigns']],['routing','pipeline-manager'])
        for group in ('protocol','manager'):
            self.assertEqual([row['log']['path'] for row in self.parts[group]['commands']],
                [name+'.log' for name in (*pipeline.LIFECYCLE_NAMES,*pipeline.campaign_names(group))])
        self.write_groups()
        # Inert sidecars exercise the real aggregate copy without native execution.
        sidecars={'protocol':('protocol-reports/report.json',),
                  'manager':('routing-reports/report.json','pipeline-manager-artifacts/report.json')}
        for group,paths in sidecars.items():
            for name in paths:
                path=self.args.root/group/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(('complete inert sidecar: '+name).encode())
        pipeline.aggregate(self.args)
        result=self.verify()
        for group,paths in sidecars.items():
            for name in (*paths,*(campaign+suffix for campaign in pipeline.campaign_names(group) for suffix in ('.json','.log'))):
                self.assertEqual((self.args.output/name).read_bytes(),(self.args.root/group/name).read_bytes())
        self.assertEqual([row['name'] for row in result['campaigns']],pipeline.campaign_names())
        for group in pipeline.CAMPAIGN_GROUPS:
            self.assertTrue((self.args.output/'groups'/group/'smoke.json').is_file())
            for name in pipeline.LIFECYCLE_NAMES:
                self.assertTrue((self.args.output/'groups'/group/(name+'.log')).is_file())

    def test_missing_group_cannot_aggregate(self):
        self.parts.pop('manager');self.write_groups()
        with self.assertRaisesRegex(ValueError,'group census'):pipeline.aggregate(self.args)
        self.assertFalse(self.args.output.exists())

    def test_native_input_bridge_uses_actual_owned_manifest_and_rejects_rehashed_forgery(self):
        fixture=fixtures.MatrixTests();fixture.setUp()
        package=self.root/'package';package.mkdir()
        owner=deepcopy(fixture.owner);owner['package_root']=str(package)
        for name,pin in owner['files'].items():pin['path']=str(package/name)
        path=package/'binaries.json';path.write_bytes(fixture.binaries)
        record=pipeline.native_input_document(owner,'3.11.15')
        self.assertEqual(record,json.loads(fixture.raw['native-inputs.json']))
        for field,value in (('revision','d'*40),('machine','arm64'),('sha256',{'biocompiler-core':'e'*64,'biocompiler-verify':'d'*64})):
            manifest=json.loads(fixture.binaries);manifest[field]=value
            raw=json.dumps(manifest).encode();path.write_bytes(raw)
            owner['files']['binaries.json'].update(sha256=hashlib.sha256(raw).hexdigest(),size=len(raw))
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'manifest identity differs'):
                pipeline.native_input_document(owner,'3.11.15')

    def test_native_input_rejection_survives_repairing_its_outer_hash(self):
        raw=json.loads(self.files['manager']['native-inputs.json']);raw['revision']='c'*40
        changed=json.dumps(raw).encode()
        self.files['manager']['native-inputs.json']=changed
        self.parts['manager']['native_inputs_sha256']=hashlib.sha256(changed).hexdigest()
        self.write_groups()
        with self.assertRaisesRegex(ValueError,'Native input authority differs'):pipeline.aggregate(self.args)
        self.assertFalse(self.args.output.exists())

    def test_bad_campaign_runtime_source_owner_or_recipe_rejects_before_copy(self):
        original=deepcopy(self.parts['manager'])
        def corrupt_owned_role(row,name):
            command=next(item for item in row['commands'] if item['log']['path']==name+'.log')
            command['argv'][3]='/unowned/core'
        mutations=(lambda row:row['campaigns'].clear(),lambda row:row.update(campaign_group='protocol'),
                   lambda row:row.update(source_revision='c'*40),lambda row:row.update(python_version='3.14.7'),
                   lambda row:row['commands'][0].update(returncode=1),
                   lambda row:row['commands'][3].update(argv=['/python','-c','pass']),
                   lambda row:row['commands'][6]['argv'].__setitem__(3,'/unowned/core'),
                   lambda row:corrupt_owned_role(row,'routing'),
                   lambda row:corrupt_owned_role(row,'pipeline-manager'),
                   lambda row:row['campaigns'].pop(0),
                   lambda row:row['campaigns'].append(deepcopy(row['campaigns'][0])),
                   lambda row:row['ownership_after'].update(run_id='124'),
                   lambda row:row['commands'][0].update(duration_seconds=float('nan')))
        for mutation in mutations:
            self.parts['manager']=deepcopy(original);mutation(self.parts['manager']);self.write_groups()
            with self.assertRaises((ValueError,KeyError)):pipeline.aggregate(self.args)
            self.assertFalse(self.args.output.exists())

        # Receipts from the old split must fail even when every row is present.
        self.parts['manager']=deepcopy(original)
        routing=self.parts['manager']['campaigns'].pop(0)
        command=next(row for row in self.parts['manager']['commands'] if row['log']['path']=='routing.log')
        self.parts['manager']['commands'].remove(command)
        self.parts['protocol']['campaigns'].append(routing)
        self.parts['protocol']['commands'].append(command)
        for name in ('routing.json','routing.log'):
            self.files['protocol'][name]=self.files['manager'].pop(name)
        self.write_groups()
        for name in ('routing.json','routing.log'):(self.args.root/'manager'/name).unlink()
        with self.assertRaisesRegex(ValueError,'campaign census'):pipeline.aggregate(self.args)
        self.assertFalse(self.args.output.exists())

    def test_changed_or_missing_group_logs_and_campaign_artifacts_are_rechecked(self):
        self.write_groups();pipeline.aggregate(self.args)
        for path in ('groups/manager/uninstall.log','pipeline-manager.json','pipeline-manager.log','routing.json','routing.log'):
            target=self.args.output/path;old=target.read_bytes();target.write_bytes(b'changed')
            with self.subTest(path=path),self.assertRaises(ValueError):self.verify()
            target.write_bytes(old)
        document_path=self.args.output/'installed-release.json'
        group_path=self.args.output/'groups/manager/installed-release.json'
        original_document=document_path.read_bytes();original_group=group_path.read_bytes()
        for mutation in (lambda row:row['campaigns'].pop(0),
                         lambda row:row['campaigns'].append(deepcopy(row['campaigns'][0]))):
            part=json.loads(original_group);mutation(part)
            raw=json.dumps(part).encode();group_path.write_bytes(raw)
            document=json.loads(original_document);document['groups']['manager']=hashlib.sha256(raw).hexdigest()
            document_path.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError,'campaign census'):self.verify()
        group_path.write_bytes(original_group);document_path.write_bytes(original_document)
        document=json.loads((self.args.output/'installed-release.json').read_bytes());document['groups'].pop('fixed')
        (self.args.output/'installed-release.json').write_text(json.dumps(document))
        with self.assertRaisesRegex(ValueError,'Missing or extra'):self.verify()

    def test_symlinked_and_overlapping_evidence_is_rejected(self):
        self.write_groups()
        path=self.args.root/'manager'/'foreign';path.symlink_to(self.args.candidate)
        with self.assertRaisesRegex(ValueError,'Symlinked'):pipeline.aggregate(self.args)
        path.unlink()
        (self.args.root/'manager'/'unexpected.json').write_text('{}')
        (self.args.root/'fixed'/'unexpected.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Overlapping'):pipeline.aggregate(self.args)
        self.assertFalse((self.args.output/'installed-release.json').exists())


if __name__=='__main__':unittest.main()
