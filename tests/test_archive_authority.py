"""Pure Python source/fixture checks; these never compile or execute native code."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

DRAFT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('archive_capture_authority', DRAFT/'tools/capture_archive_container.py')
authority = importlib.util.module_from_spec(spec)
spec.loader.exec_module(authority)

class ArchiveAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.current = authority.capture()
        cls.frozen = {minor:json.loads((DRAFT/f'tests/conformance/archive-container-{minor}.json').read_bytes())
                      for minor in ('311','314')}

    def test_complete_actual_original_capture(self):
        minor = self.current['python_minor'].replace('.','')
        self.assertEqual(self.current, self.frozen[minor])
        self.assertEqual(len(self.current['cases']), 125)
        self.assertEqual(len({row['id'] for row in self.current['cases']}), 125)
        self.assertEqual(set(row['operation'] for row in self.current['cases']),
                         {'read','encode','pretty','validate-files','assemble'})

    def test_only_explicit_diagnostic_runtime_difference(self):
        left,right=self.frozen['311'],self.frozen['314']
        changed=[]
        for a,b in zip(left['cases'],right['cases']):
            self.assertEqual({k:v for k,v in a.items() if k!='outcome'},
                             {k:v for k,v in b.items() if k!='outcome'})
            if a['outcome']!=b['outcome']:changed.append(a['id'])
            if a['outcome']['status']=='return':self.assertEqual(a,b)
        self.assertEqual(changed,['read:overlap-empty-beyond-input','read:zip64-extra-unicode-short','read:repr-newunicode'])

    def test_actual_canonical_bytes_roundtrip_and_field_census(self):
        rows=self.current['cases']
        for row in rows:
            if row['operation']=='encode' and row['outcome']['status']=='return':
                raw=bytes.fromhex(row['outcome']['value']['bytes'])
                self.assertEqual(authority.original.read_container(raw),
                    {name:bytes.fromhex(data) for name,data in row['input']['entries']})
        required={'read:crc','read:local-crc','read:duplicate','read:overlap','read:volume',
                  'read:zip64-alternate-valid','read:zip64-extra-unicode-short','read:zip64-record-missing',
                  'read:local-flags','read:reversed','read:prefix','read:metadata-size',
                  'validate:duplicate-manifest','validate:unsafe-first','assemble:metadata-limit'}
        self.assertLessEqual(required,{row['id'] for row in rows})

    def test_numeric_and_unicode_pretty_contract(self):
        values=[row for row in self.current['cases'] if row['operation']=='pretty']
        encoded=b'\n'.join(bytes.fromhex(row['outcome']['value']['bytes']) for row in values)
        for literal in (b'7.0',b'-0.0',b'5e-324',b'1e+16',b'1.7976931348623157e+308',
                        '\U0001f9ec'.encode(),'é'.encode(),b'\\u0000',b'\x7f'):
            self.assertIn(literal,encoded)
        self.assertNotIn(b'\\u007f',encoded)
        self.assertTrue(all(bytes.fromhex(row['outcome']['value']['bytes']).endswith(b'\n') for row in values))

    def test_closed_selected_stdlib_source_profile(self):
        minor=self.current['python_minor'].replace('.','')
        frozen=json.loads((DRAFT/f'tests/conformance/archive-stdlib-authority-{minor}.json').read_bytes())
        current=authority.runtime_authority()
        self.assertEqual(current['source_profile'],frozen['source_profile'])
        self.assertEqual(current['unicode'],frozen['unicode'])
        self.assertEqual(current['functions'],frozen['functions'])
        for row in frozen['functions'].values():
            self.assertEqual(hashlib.sha256(row['source'].encode()).hexdigest(),row['sha256'])
        self.assertEqual(len(frozen['functions']),8)

    def test_original_source_pin_and_no_fixture_rewrite(self):
        source=authority.ROOT/self.current['source']['path']
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),self.current['source']['sha256'])
        self.assertEqual(self.current['source']['sha256'],'36d598102ffea532b67a3a116266f573ccff07da39166230023d162fd675d43f')
        for value in self.frozen.values():self.assertEqual(value['source'],self.current['source'])

if __name__=='__main__':unittest.main()
