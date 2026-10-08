"""Pin each complete runtime observation without any text normalization."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from tools import cli_runtime_counterparts as c
from tools import freeze_workflow_cli as f


class CliRuntimeCounterpartsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline, cls.blobs = f.load()
        cls.old = next(row for row in cls.baseline['cases'] if row['id'] == 'unknown-flag')
        cls.observation = {'exit_code': cls.old['exit_code'],
            **{field: f.restore(cls.old[field], cls.blobs) for field in ('stdout', 'stderr')}}

    def test_exact_two_runtime_bytes_archived_execution_and_unmodified_baseline(self):
        counterparts = c.workflow()
        self.assertEqual(set(counterparts.cases), {'unknown-flag'})
        before = deepcopy(self.old)
        current = counterparts.expected(self.old, self.observation, '3.14.9')
        legacy = counterparts.expected(self.old, self.observation, '3.11.15')
        self.assertEqual(current, self.observation)
        self.assertNotEqual(legacy['stderr'], current['stderr'])
        value = json.loads(c.WORKFLOW_PATH.read_bytes())
        proof = value['provenance']['python311_archived_pre_route_execution']
        self.assertEqual(proof['historical_cli_sha256'], 'eec53f1b4c3775b40236fc1e9f2bf1f12a37dd0f5a63e4083d1eb9f5a7551fd0')
        self.assertEqual(legacy, {'exit_code':proof['observation']['exit_code'],
            'stdout': proof['stdout'].encode(), 'stderr': proof['stderr'].encode()})
        self.assertEqual(self.old, before)
        for old in self.baseline['cases']:
            if old['id'] == self.old['id']: continue
            observation = {'exit_code':old['exit_code'],
                **{field:f.restore(old[field],self.blobs) for field in ('stdout','stderr')}}
            self.assertEqual(counterparts.expected(old, observation, '3.11'), observation)

    def test_unknown_runtime_and_changed_bound_invocation_or_original_bytes_fail(self):
        counterpart = c.workflow()
        for version in ('3.10.9', '3.12.9', '3.13.9', '3.15.0', '3.11.x', '3.110.0', '', None):
            if version is None: continue
            with self.assertRaisesRegex(AssertionError, 'CLI Python runtime'):
                counterpart.expected(self.old, self.observation, version)
        for mutate in (lambda row:row['argv'].append('--forged'), lambda row:row.update(entrypoint='module'),
                       lambda row:row.update(exit_code=0), lambda row:row.update(fault={}),
                       lambda row:row.update(files_after={"forged":{}})):
            row = deepcopy(self.old); mutate(row)
            with self.assertRaisesRegex(AssertionError, 'baseline case changed'):
                counterpart.expected(row, self.observation, '3.11')
        for field in ('stdout','stderr','exit_code'):
            observation = dict(self.observation)
            observation[field] = 9 if field == 'exit_code' else observation[field] + b' '
            with self.assertRaisesRegex(AssertionError, 'original bytes changed'):
                counterpart.expected(self.old, observation, '3.11')
        with self.assertRaisesRegex(AssertionError, 'Invalid original CLI observation'):
            counterpart.expected(self.old, {**self.observation,'exit_code':False}, '3.11')

    def test_immutable_declaration_and_complete_byte_pins_cannot_be_relabelled(self):
        original = c.WORKFLOW_PATH.read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'counterparts.json'; path.write_bytes(original+b' ')
            with self.assertRaisesRegex(AssertionError, 'Immutable CLI runtime counterpart bytes'):
                c.Counterparts(path, c.WORKFLOW_SHA256, self.baseline['inventory_fingerprint'])
            for mutate in (
                lambda value:value.update(baseline_inventory_fingerprint='0'*64),
                lambda value:value['supported_python_minors'].append('3.12'),
                lambda value:value['cases'].append(deepcopy(value['cases'][0])),
                lambda value:value['cases'][0]['observations']['3.11']['stderr'].update(bytes=1),
                lambda value:value['cases'][0]['observations']['3.11'].update(exit_code=False),
            ):
                value=json.loads(original); mutate(value); raw=c.canonical(value)+b'\n'; path.write_bytes(raw)
                with self.assertRaises(AssertionError):
                    c.Counterparts(path,c.sha(raw),self.baseline['inventory_fingerprint'])
