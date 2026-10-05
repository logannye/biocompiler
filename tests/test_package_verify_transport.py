"""Real Python peers exercise protocol/FD rejection only, never native validity."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
from biocompiler import core_package_files as files
from biocompiler import core_reference_package_verify as verify
from biocompiler.core_client import CoreClient, CoreError, CoreProtocolError, CoreTimeout, CoreCancelled

PEER = r'''
import hashlib,json,os,sys,time
assert sys.argv[1]=='--verify-reference-package-fds-v1'
raw=sys.stdin.buffer.read(); request=json.loads(raw)
assert request['declaration']==DECLARATION
assert request['runtime'] in DECLARATION['runtime_profiles']
assert request['runtime']==('python311' if sys.version_info[:2]==(3,11) else 'python314')
source,target=map(int,sys.argv[2:])
assert os.fstat(target).st_size==0
data=os.read(source,request['archive']['bytes']+1)
assert len(data)==request['archive']['bytes'] and hashlib.sha256(data).hexdigest()==request['archive']['sha256']
try: os.write(source,b'bad')
except OSError: pass
else: raise AssertionError('input must be readonly')
def encode(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
report={'schema_version':'biocompiler.reference_package_check.v1','outcome':'pass',
 'archive_sha256':hashlib.sha256(data).hexdigest(),
 'build_fingerprint':request['expected_build_fingerprint'] or 'b'*64,'request_fingerprint':'c'*64,
 'metadata_authority':hashlib.sha256(encode(request['authority'])).hexdigest(),
 'claim_scope':CLAIM,'core_reconstruction_required':True}
reply={'protocol':request['protocol'],'profile':request['profile'],'executable':'verify','version':'0.1.0',
 'request_id':request['request_id'],'request_sha256':hashlib.sha256(raw).hexdigest(),
 'operation':request['operation'],'archive':request['archive'],'status':'ok','result':report,'diagnostics':[],
 'usage':{'work':1000,'retained_bytes':2000}}
# MUTATE
sys.stdout.buffer.write(encode(reply)+b'\n')
'''


class PackageVerifyTransportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.options = {'package_version': 'test-sdk', 'tool_pins': [
            {'schema_version': 'biocompiler.tool_pin.v0.1', 'id': name,
             'version': 'test-version', 'content_fingerprint': 'd'*64} for name in verify.TOOL_IDS],
            'expected_build_fingerprint': 'b'*64}

    def client(self, mutation='', *, timeout=3):
        path = Path(self.directory.name) / 'python-verifier-peer'
        path.write_text('#!' + sys.executable + '\nDECLARATION=' + repr(verify.DECLARATION)
            + '\nCLAIM=' + repr(verify.CLAIM) + '\n' + PEER.replace('# MUTATE', mutation))
        path.chmod(0o700)
        return CoreClient(path, role='verify', timeout_seconds=timeout,
            expected_sha256=hashlib.sha256(path.read_bytes()).hexdigest())

    def call(self, client=None, **kwargs):
        return verify.verify_package(client or self.client(), b'PK\0\xff\r\n transport-only fixture', **{**self.options, **kwargs})

    def test_exact_bytes_independent_authority_and_immutable_report(self):
        result = self.call()
        self.assertEqual(result.archive_sha256, hashlib.sha256(b'PK\0\xff\r\n transport-only fixture').hexdigest())
        self.assertEqual(result.build_fingerprint, 'b'*64)
        result.report['outcome'] = 'forged'
        self.assertEqual(result.report['outcome'], 'pass')
        self.assertTrue(result.report['core_reconstruction_required'])

    def test_repaired_detached_fields_wrong_profile_and_extended_claims(self):
        for mutation in (
            "reply['request_sha256']='a'*64", "reply['request_id']='other'", "reply['executable']='core'",
            "reply['profile']='old'", "report['archive_sha256']='a'*64", "report['metadata_authority']='a'*64",
            "report['build_fingerprint']='a'*64", "report['core_reconstruction_required']=False",
            "report['claim_scope']='human-use accepted'", "reply['archive']['bytes']+=1",
            "reply['usage']['work']=True", "reply['usage']['retained_bytes']=536870913",
            "report['extra']='unbound'", "reply['diagnostics']=[{'code':'x','message':'x','path':None}]",
        ):
            with self.subTest(mutation=mutation), self.assertRaises(CoreProtocolError):
                self.call(self.client(mutation))

    def test_error_reply_cannot_carry_acceptance(self):
        mutation="reply.update(status='error',result=None,diagnostics=[{'code':'reference_package_check','message':'fresh check failed','path':None}])"
        with self.assertRaisesRegex(verify.PackageVerificationRejected, 'fresh check failed'):
            self.call(self.client(mutation))
        with self.assertRaises(CoreProtocolError):
            self.call(self.client(mutation + ";reply['result']=report"))

    def test_verify_cannot_write_even_one_byte_to_output(self):
        with self.assertRaises(CoreError):
            self.call(self.client("os.write(target,b'X')"))

    def test_cancel_timeout_and_pinned_executable_failure(self):
        with self.assertRaises(CoreCancelled):
            self.call(cancelled=lambda: True)
        with self.assertRaises(CoreTimeout):
            self.call(self.client('time.sleep(10)', timeout=0.05))
        client = self.client()
        client.executable.write_text(client.executable.read_text()+'\n# changed\n')
        with self.assertRaises(CoreError):
            self.call(client)

    def test_missing_authority_role_and_reductions_fail_before_execution(self):
        client = self.client("raise AssertionError('must not execute')")
        for kwargs in ({'expected_build_fingerprint': None}, {'tool_pins': self.options['tool_pins'][:-1]},
            {'tool_pins': [self.options['tool_pins'][0]]*13}, {'limits': {}},
            {'limits': {**verify.LIMITS, 'max_archive_bytes': 1}},
            {'limits': {**verify.LIMITS, 'max_work': True}}):
            with self.subTest(kwargs=kwargs), self.assertRaises(CoreProtocolError):
                self.call(client, **kwargs)
        with self.assertRaisesRegex(CoreProtocolError, 'standalone Verify'):
            self.call(CoreClient(client.executable))
        with patch.object(verify.sys, 'version_info', (3, 13)):
            with self.assertRaisesRegex(CoreProtocolError, 'Python 3.11 or 3.14'):
                self.call(client)

    def test_full_current_tool_pins_are_independent_and_bound_to_report(self):
        for field, value in (('schema_version', 'unknown'), ('id', 'foreign'),
                ('content_fingerprint', 'not-a-digest'), ('version', '')):
            pins = [dict(item) for item in self.options['tool_pins']]
            pins[0][field] = value
            with self.subTest(field=field), self.assertRaises(CoreProtocolError):
                self.call(self.client("raise AssertionError('must not execute')"), tool_pins=pins)
        changed = [dict(item) for item in self.options['tool_pins']]
        changed[0]['content_fingerprint'] = 'e'*64
        original = self.call()
        revised = self.call(tool_pins=changed)
        self.assertNotEqual(original.metadata_authority, revised.metadata_authority)


if __name__ == '__main__':
    unittest.main()
