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
    def assert_supported_runtime_workflow(self, text):
        matches = re.findall(r"^  BIOCOMPILER_SUPPORTED_PYTHON: '([^'\n]+)'$", text, re.M)
        self.assertEqual(len(matches), 1)
        patches = json.loads(matches[0])
        self.assertEqual(patches, {'3.11': '3.11.15', '3.14': '3.14.6'})
        for minor, patch_version in patches.items():
            authority = json.loads((ROOT / ('tests/conformance/archive-stdlib-authority-'
                                           + minor.replace('.', '') + '.json')).read_text())
            self.assertEqual(authority['python'], patch_version)
        jobs = {match.group(1): match.group(2) for match in re.finditer(
            r'^  ([a-z][a-z0-9-]*):\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)',
            text.split('\njobs:\n', 1)[1], re.M | re.S)}
        self.assertEqual(set(jobs), ci.REQUIRED_NEEDS | {'validation'})
        matrix_jobs = {'ci-preflight', 'unit-plan', 'installed-executable', 'installed-architecture',
                       'circuit-integration', 'integration-examples', 'architecture-sdk',
                       'installed-campaigns', 'realization-conformance', 'policy-prebuilt-installed'}
        matrix = '${{ fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)[matrix.python-version] }}'
        fixed311 = "${{ fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)['3.11'] }}"
        fixed314 = "${{ fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)['3.14'] }}"
        selected_plan = '${{ steps.plan_python.outputs.python-version }}'
        total = 0
        for name, job in jobs.items():
            steps = [match.group(1) for match in re.finditer(
                r'^      - (.*?)(?=^      - |\Z)', job, re.M | re.S)]
            setup = [step for step in steps if step.startswith('uses: actions/setup-python@v5\n')]
            total += len(setup)
            actual = []
            for step in setup:
                versions = re.findall(r'^          python-version: (.*)$', step, re.M)
                self.assertEqual(len(versions), 1)
                actual.extend(versions)
            expected = ([matrix] if name in matrix_jobs else
                        [selected_plan] if name in {'unit-tests', 'unit-accounting'} else
                        [fixed311, fixed314] if name == 'realization-core-reproducibility' else
                        [fixed311])
            self.assertEqual(actual, expected, name)
            # A narrower job/step environment cannot replace the reviewed mapping.
            self.assertNotRegex(job, r'BIOCOMPILER_SUPPORTED_PYTHON:')
        self.assertEqual(total, 28)
        self.assertEqual(text.count('uses: actions/setup-python@'), 28)
        preflight = jobs['ci-preflight']
        self.assertIn('tests.test_archive_authority', preflight)
        self.assertIn('python -B tools/migration_inventory.py --check', preflight)

    def test_every_hosted_python_consumer_selects_the_supported_source_profile(self):
        text = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assert_supported_runtime_workflow(text)
        changes = [
            text.replace('"3.14":"3.14.6"', '"3.14":"3.14.8"'),
            text.replace('"3.11":"3.11.15"', '"3.11":"3.11"'),
            text.replace('fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)[matrix.python-version]',
                         'matrix.python-version', 1),
            text.replace("fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)['3.11']", "'3.11'", 1),
            text.replace("fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)['3.14']", "'3.14'", 1),
            text.replace('steps.plan_python.outputs.python-version', 'matrix.python-version', 1),
            text.replace('uses: actions/setup-python@v5', 'uses: actions/setup-python@v6', 1),
            text.replace(' tests.test_archive_authority', ''),
            text.replace('          python -B tools/migration_inventory.py --check\n', ''),
        ]
        for index, changed in enumerate(changes):
            with self.subTest(mutation=index), self.assertRaises(AssertionError):
                self.assert_supported_runtime_workflow(changed)

    def test_unit_consumers_select_the_plans_exact_patch_before_installation(self):
        text = (ROOT / '.github/workflows/ci.yml').read_text()
        jobs = {match.group(1): match.group(2) for match in re.finditer(
            r'^  ([a-z][a-z0-9-]*):\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)',
            text.split('\njobs:\n', 1)[1], re.M | re.S)}
        self.assertIn('python-version: ${{ fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)[matrix.python-version] }}', jobs['unit-plan'])
        for name in ('unit-tests', 'unit-accounting'):
            with self.subTest(job=name):
                job = jobs[name]
                ordered = (
                    'uses: actions/checkout@v4',
                    'name: unit-plan-py${{ matrix.python-version }}',
                    'id: plan_python',
                    'python3 -I -B tools/test_shards.py runtime --plan generated/unit-plan/plan.json '
                    "--python-minor '${{ matrix.python-version }}'",
                    "printf 'python-version=%s\\n' \"$plan_python_version\" >> \"$GITHUB_OUTPUT\"",
                    'uses: actions/setup-python@v5',
                    'python-version: ${{ steps.plan_python.outputs.python-version }}',
                    'run: python -m pip install .',
                    'python tools/test_shards.py ' + ('run' if name == 'unit-tests' else 'verify'),
                )
                positions = [job.index(value) for value in ordered]
                self.assertEqual(positions, sorted(positions))
                self.assertEqual(job.count('uses: actions/setup-python@v5'), 1)
                self.assertEqual(job.count('name: unit-plan-py${{ matrix.python-version }}'), 1)
                self.assertNotIn('python-version: ${{ matrix.python-version }}', job)
                self.assertIn('python-version: ["3.11", "3.14"]', job)
        self.assertIn('shard: [0, 1, 2, 3, 4]', jobs['unit-tests'])
        self.assertIn('needs: [unit-plan, unit-tests]', jobs['unit-accounting'])
        for index in range(5):
            self.assertIn('--result generated/unit-results/shard-' + str(index) + '.json',
                          jobs['unit-accounting'])

    def assert_hosted_bootstrap_workflow(self, text):
        jobs = {match.group(1): match.group(2) for match in re.finditer(
            r'^  ([a-z][a-z0-9-]*):\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)',
            text.split('\njobs:\n', 1)[1], re.M | re.S)}
        fixed = {'ocaml-build', 'ocaml-native-tests', 'ocaml-core'}
        selected = {'architecture-sdk', 'installed-campaigns',
                    'realization-conformance', 'policy-prebuilt-installed'}
        expected_slots = {'ocaml-build': 1, 'ocaml-native-tests': 1, 'ocaml-core': 1,
                          'architecture-sdk': 1, 'installed-campaigns': 5,
                          'realization-conformance': 1, 'policy-prebuilt-installed': 1}
        command = ('run: /usr/bin/python3 -I -S -B tools/bootstrap_hosted_python.py '
                   '--output generated/ci-python/bootstrap.json')
        marker = 'name: Seed the exact hosted macOS ARM64 Python runtime'
        total_slots = 0
        for name, job in jobs.items():
            steps = [match.group(1) for match in re.finditer(
                r'^      - (.*?)(?=^      - |\Z)', job, re.M | re.S)]
            seeds = [step for step in steps if 'tools/bootstrap_hosted_python.py' in step]
            if name not in fixed | selected:
                self.assertEqual(seeds, [], name)
                continue
            version = ("fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)['3.11']" if name in fixed
                       else 'fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)[matrix.python-version]')
            condition = ("if: ${{ runner.environment == 'github-hosted' && runner.os == 'macOS' "
                         "&& runner.arch == 'ARM64' && " + version + " == '3.11.15' }}")
            self.assertEqual(seeds, [marker + '\n        ' + condition +
                                     '\n        ' + command + '\n'], name)
            seed_index = steps.index(seeds[0])
            self.assertGreater(seed_index, 0, name)
            self.assertEqual(steps[seed_index - 1], 'uses: actions/checkout@v4\n', name)
            self.assertTrue(steps[seed_index + 1].startswith('uses: actions/setup-python@v5\n'), name)
            rows = re.findall(r'          - runner: macos-14\n            platform: macos-arm64\n'
                              r'(?:            python-version: "([0-9.]+)"\n)?', job)
            selected_rows = rows.count('') if name in fixed else rows.count('3.11')
            self.assertEqual(selected_rows, expected_slots[name], name)
            total_slots += selected_rows
        self.assertEqual(total_slots, 11)
        self.assertEqual(text.count('tools/bootstrap_hosted_python.py'), 7)
        self.assertIn('tests.test_bootstrap_hosted_python', jobs['ci-preflight'])
        self.assert_supported_runtime_workflow(text)

    def test_mac_arm_bootstrap_preserves_exact_selection_and_all_existing_jobs(self):
        text = (ROOT / '.github/workflows/ci.yml').read_text()
        self.assert_hosted_bootstrap_workflow(text)
        seed = re.search(r'^      - name: Seed the exact hosted macOS ARM64 Python runtime\n'
                         r'        if: .*\n        run: .*\n', text, re.M).group(0)
        setup = ("      - uses: actions/setup-python@v5\n        with:\n"
                 "          python-version: ${{ fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)['3.11'] }}\n")
        changes = [
            text.replace(seed, '', 1),
            text.replace("runner.environment == 'github-hosted' && ", '', 1),
            text.replace("runner.os == 'macOS'", "runner.os == 'Linux'", 1),
            text.replace("runner.arch == 'ARM64'", "runner.arch == 'X64'", 1),
            text.replace(" == '3.11.15' }}", " == '3.14.6' }}", 1),
            text.replace('fromJSON(env.BIOCOMPILER_SUPPORTED_PYTHON)[matrix.python-version] '
                         "== '3.11.15'", "matrix.python-version == '3.11'", 1),
            text.replace(seed + setup, setup + seed, 1),
            text.replace('/usr/bin/python3 -I -S -B tools/bootstrap_hosted_python.py',
                         'python3 tools/bootstrap_hosted_python.py', 1),
            text.replace(seed, seed + seed, 1),
            text.replace(' tests.test_bootstrap_hosted_python', '', 1),
        ]
        for index, changed in enumerate(changes):
            with self.subTest(mutation=index), self.assertRaises(AssertionError):
                self.assert_hosted_bootstrap_workflow(changed)

    def assert_bootstrap_feedback_workflow(self, text):
        self.assertIn("on:\n  push:\n    branches: ['codex/dev-python/**']\n", text)
        self.assertNotIn('pull_request:', text)
        self.assertNotIn('workflow_run:', text)
        self.assertIn('permissions:\n  contents: read\n', text)
        self.assertIn('group: ${{ github.workflow }}-${{ github.ref }}', text)
        jobs = re.findall(r'^  ([a-z][a-z0-9-]*):\n', text.split('\njobs:\n', 1)[1], re.M)
        self.assertEqual(jobs, ['macos-python-bootstrap'])
        self.assertIn('runs-on: macos-14', text)
        self.assertIn('timeout-minutes: 15', text)
        ordered = (
            'uses: actions/checkout@v4',
            '/usr/bin/python3 -I -S -B tools/bootstrap_hosted_python.py '
            '--output generated/ci-python/bootstrap.json',
            'uses: actions/setup-python@v5',
            "python-version: '3.11.15'",
            'platform.python_version()=="3.11.15" and platform.machine()=="arm64" '
            'and platform.system()=="Darwin"',
            '"release_acceptance":False',
            'python -B -m unittest -v tests.test_archive_authority tests.test_bootstrap_hosted_python',
            'if: always()',
            'uses: actions/upload-artifact@v4',
            'path: generated/ci-python/',
            'if-no-files-found: error',
            'retention-days: 7',
        )
        positions = [text.index(value) for value in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(text.count('tools/bootstrap_hosted_python.py'), 1)
        self.assertEqual(text.count('uses: actions/setup-python@'), 1)
        for unrelated in ('dune ', 'cargo ', 'pip install', 'ci_validation.py finish'):
            self.assertNotIn(unrelated, text)

    def test_bootstrap_feedback_is_isolated_and_preserves_runtime_authority_checks(self):
        text = (ROOT / '.github/workflows/python-bootstrap.yml').read_text()
        self.assert_bootstrap_feedback_workflow(text)
        changes = [
            text.replace("branches: ['codex/dev-python/**']", "branches: ['**']"),
            text.replace('contents: read', 'contents: write'),
            text.replace('group: ${{ github.workflow }}-${{ github.ref }}',
                         'group: release-${{ github.ref }}'),
            text.replace("python-version: '3.11.15'", "python-version: '3.11'"),
            text.replace('tests.test_archive_authority ', ''),
            text.replace('"release_acceptance":False', '"release_acceptance":True'),
            text.replace('if: always()', 'if: success()'),
        ]
        for index, changed in enumerate(changes):
            with self.subTest(mutation=index), self.assertRaises((AssertionError, ValueError)):
                self.assert_bootstrap_feedback_workflow(changed)

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
        self.assertEqual(len(ci.EXPECTED_RECEIPTS),59)
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
        self.assertIn('max-parallel: 20',installed)
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
            if group in pipeline.PARALLEL_CAMPAIGN_GROUPS:
                receipt['campaign_execution'] = pipeline.campaign_execution(pipeline.campaign_names(group))
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
