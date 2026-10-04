"""Complete architecture partition accounting without native execution."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tests import test_architecture_routing_reproducibility as fixtures
from tools import architecture_routing_parallel as parallel
from tools import check_architecture_routing_reproducibility as checker


class ArchitecturePartitionTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        source=self.root/'original';fixtures.fixture(source)
        slot=source/'linux-x86_64'
        self.original=json.loads((slot/'architecture-routing-3.11.json').read_bytes())
        self.original.update(package_path='/installed/biocompiler/__init__.py')
        self.parts={part:self.root/'parts'/str(part) for part in parallel.PARTITIONS}
        for part,directory in self.parts.items():
            directory.mkdir(parents=True)
            cases=set(parallel.partition_cases(part))
            receipt=deepcopy(self.original)
            receipt.update(schema_version='biocompiler.architecture_routing_partition.v1',partition=part,
                allowed_calls=['biocompiler.allowed.fixture'],scenario_timings={case:1.0 for case in cases},duration_seconds=8.0)
            receipt['checks']=[row for row in receipt['checks'] if row['id'] in cases
                or ('installed/B' in cases and row['id'] not in checker.CASES)]
            receipt['completed_checks']=len(receipt['checks'])
            folders={(case.split('/',1)[1].lower() if case.startswith('installed/') else case.replace('/','-')) for case in cases}
            receipt['artifacts']={name:pin for name,pin in receipt['artifacts'].items() if name.split('/',1)[0] in folders}
            for name in receipt['artifacts']:
                target=directory/'artifacts'/name;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((slot/'architecture-routing-3.11'/'artifacts'/name).read_bytes())
            (directory/'guards').mkdir()
            (directory/'guards'/('guard-'+str(part)+'.json')).write_text('{}')
            (directory/'receipt.json').write_text(json.dumps(receipt))

    def merge(self):
        receipt={key:deepcopy(value) for key,value in self.original.items() if key not in ('checks','artifacts')}
        receipt['checks']=[]
        parallel.merge(self.parts,self.root/'artifacts',self.root/'guards',receipt)
        return receipt

    def test_every_case_and_all_b_derived_controls_remain_exactly_once(self):
        cases=[case for part in parallel.PARTITIONS for case in parallel.partition_cases(part)]
        self.assertEqual(len(cases),16);self.assertEqual(set(cases),set(checker.CASES))
        self.assertEqual(cases.count('installed/B'),1)
        receipt=self.merge()
        self.assertEqual(len(receipt['checks']),175)
        self.assertEqual(receipt['artifacts'],self.original['artifacts'])
        self.assertEqual(len(receipt['artifacts']),219)
        self.assertEqual({(r['id'],r['operation']) for r in receipt['checks']},set(checker.expected_checks()))

    def test_incomplete_failed_stale_unguarded_and_duplicate_partitions_reject(self):
        path=self.parts[0]/'receipt.json';original=json.loads(path.read_bytes())
        changes=(lambda r:r.update(status='failure'),lambda r:r.update(partition=1),
                 lambda r:r.update(python_semantics_blocked=False),lambda r:r.update(revision='c'*40),
                 lambda r:r.update(python_version='3.14.7'),lambda r:r['checks'].pop(),
                 lambda r:r['checks'].__setitem__(1,r['checks'][0]),
                 lambda r:r['executables']['core'].update(sha256='d'*64),
                 lambda r:r['artifacts'].pop(next(iter(r['artifacts']))))
        for change in changes:
            receipt=deepcopy(original);change(receipt);path.write_text(json.dumps(receipt))
            with self.assertRaises(AssertionError):self.merge()
            self.assertFalse((self.root/'artifacts').exists())
        path.write_text(json.dumps(original));self.parts.pop(1)
        with self.assertRaisesRegex(AssertionError,'partition census'):self.merge()

    def test_wrong_outcomes_or_inconsistent_native_pins_fail_original_checker(self):
        path=self.parts[0]/'receipt.json';receipt=json.loads(path.read_bytes())
        row=next(row for row in receipt['checks'] if row['operation']=='cli.build')
        row['exit_code']=1;path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(AssertionError,'result/pin differs'):self.merge()
        self.assertFalse((self.root/'artifacts').exists())

    def test_changed_and_unlisted_artifacts_are_rejected_before_publication(self):
        path=next((self.parts[0]/'artifacts').rglob('request.json'));old=path.read_bytes()
        path.write_bytes(b'changed')
        with self.assertRaisesRegex(AssertionError,'changed partition artifact'):self.merge()
        path.write_bytes(old);(self.parts[0]/'artifacts'/'extra.json').write_text('{}')
        with self.assertRaisesRegex(AssertionError,'extra partition artifacts'):self.merge()
        self.assertFalse((self.root/'artifacts').exists())


if __name__=='__main__':unittest.main()
