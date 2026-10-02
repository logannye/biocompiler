"""Real Python subprocesses exercise artifact transport without native builds."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from biocompiler import core_artifacts as artifacts
from biocompiler.core_client import (
    LIMITS, CoreCancelled, CoreClient, CoreError, CoreProtocolError, CoreTimeout,
    CoreTransportError, CoreUnavailable, encode_json,
)


CHILD = r'''
import hashlib,json,os,stat,sys,time
request=json.load(sys.stdin)
def descriptor(data):return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
response={'protocol':'biocompiler.core.v1','request_id':request['request_id'],
 'operation':request['operation'],'status':'ok','diagnostics':[],
 'core':{'implementation':'ocaml','version':'0.1.0','protocol':'biocompiler.core.v1','executable':'core'}}
if request['operation']=='capabilities':
 assert len(sys.argv)==1
 response['result']={'schema_version':'biocompiler.core_capabilities.v1',
  'operations':['capabilities','run-verification-workflow','replay-verification-workflow'],'intent_schemas':[],
  'canonicalization':'python-json-v1','validation_scopes':[],
  'profiles':{} if MODE=='missing-profile' else {'artifact_transport':PROFILE},
  'limits':LIMITS,'claim_scope':'Transport fixture only.'}
 print(json.dumps(response));sys.exit(0)
assert sys.argv[1]=='--artifact-fds-v1' and len(sys.argv)==5
authority_fd=int(sys.argv[2]);record_fd=None if sys.argv[3]=='-' else int(sys.argv[3]);output_fd=int(sys.argv[4])
identities=set()
def read(fd):
 info=os.fstat(fd);assert stat.S_ISREG(info.st_mode)
 identity=(info.st_dev,info.st_ino);assert identity not in identities;identities.add(identity)
 try:os.write(fd,b'!');raise AssertionError('input descriptor writable')
 except OSError:pass
 with os.fdopen(os.dup(fd),'rb') as source:return source.read()
authority=read(authority_fd);record=None if record_fd is None else read(record_fd)
payload=request['payload'];assert payload['authority']==descriptor(authority)
assert payload['retained_record']==(None if record is None else descriptor(record))
info=os.fstat(output_fd);assert stat.S_ISREG(info.st_mode) and info.st_size==0
assert (info.st_dev,info.st_ino) not in identities
if MODE=='stall':time.sleep(10)
if MODE=='flood-stdout':sys.stdout.write('x'*70000);sys.exit(0)
if MODE=='flood-stderr':sys.stderr.write('x'*1100000);sys.exit(0)
if MODE=='flood-artifact':os.write(output_fd,b'x'*1000);sys.exit(0)
raw=record if record is not None else authority
raw=json.dumps(json.loads(raw),sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
if MODE=='noncanonical':raw=b' '+raw
if MODE=='invalid-json':raw=b'{"x":1,"x":2}'
with os.fdopen(os.dup(output_fd),'wb') as output:output.write(raw[:-1] if MODE=='partial' else raw)
if MODE=='fail-after-write':sys.exit(9)
response['result']={'schema_version':'biocompiler.core.artifact_response.v1',
 'transport':'biocompiler.core.artifact_transport.v1','authority':descriptor(authority),
 'retained_record':None if record is None else descriptor(record),
 'artifact':descriptor(raw),'result':{'operation_payload':payload['operation_payload']}}
if MODE=='wrong-hash':response['result']['artifact']['sha256']='0'*64
if MODE=='wrong-authority':response['result']['authority']['sha256']='0'*64
if MODE=='bool-size':response['result']['artifact']['bytes']=True
if MODE=='wrong-request':response['request_id']='wrong'
print(json.dumps(response))
'''


class ArtifactCodecTests(unittest.TestCase):
    def test_exact_unicode_numeric_and_key_node_accounting(self):
        raw='{"é":[-0.0,1.0,1,9007199254740993,true,null]}'.encode()
        value=artifacts.decode_artifact(raw)
        self.assertEqual(artifacts._canonical(value,len(raw)),raw)
        with patch.object(artifacts,'MAX_ARTIFACT_NODES',2):
            with self.assertRaisesRegex(CoreProtocolError,'node'):
                artifacts.decode_artifact(b'{"k":1}')
        with patch.object(artifacts,'MAX_ARTIFACT_NODES',3):
            self.assertEqual(artifacts.decode_artifact(b'{"k":1}'),{'k':1})

    def test_bad_tokens_duplicates_escapes_and_structures_fail(self):
        for raw in [b'',b'NaN',b'Infinity',b'1e999',b'{"k":1,"k":2}',b'"\xff"',
                    b'"\\ud800"',b'"\\x20"',b'"\\u123"',b'"\n"',b'"unfinished',
                    b'01',b'{} {}',b'[}',b'[[0]',b'{"x":}',b'\xef\xbb\xbf{}']:
            with self.subTest(raw=raw),self.assertRaises(CoreProtocolError):
                artifacts.decode_artifact(raw)

    def test_preflight_rejects_inventory_before_full_decoder_allocation(self):
        with patch.object(artifacts,'MAX_ARTIFACT_NODES',4),patch.object(artifacts.json,'loads') as decoder:
            with self.assertRaises(CoreProtocolError):artifacts.decode_artifact(b'[0,0,0,0]')
            decoder.assert_not_called()
        with patch.dict(LIMITS,max_depth=2,max_number_chars=4,max_string_bytes=2):
            for raw in [b'[[[0]]]',b'10000',b'"abc"',b'"\\u0061\\u0062\\u0063"']:
                with self.subTest(raw=raw),self.assertRaises(CoreProtocolError):
                    artifacts.decode_artifact(raw)


@unittest.skipUnless(os.name=='posix','Experimental artifact channel targets POSIX')
class ArtifactProcessTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'artifact-core'

    def client(self,mode='valid',**kwargs):
        text=(f'#!{sys.executable}\nMODE={mode!r}\nPROFILE={artifacts.TRANSPORT_PROFILE!r}\n'
              f'LIMITS={LIMITS!r}\n'+CHILD)
        self.path.write_text(text);self.path.chmod(0o755)
        return CoreClient(self.path,**kwargs)

    def call(self,client=None,**kwargs):
        return artifacts.call_artifact(client or self.client(),'run-verification-workflow',{'finite':True},
                                       authority=b'{"source":1}',**kwargs)

    def test_complete_artifacts_and_independent_authority_bindings(self):
        record=b'{"complete":[-0.0,1.0,9007199254740993],"outcome":"FAIL"}'
        result=self.call(retained_record=record,request_id='finite-request')
        self.assertEqual(result.artifact,record)
        self.assertEqual(result.response.request_id,'finite-request')
        self.assertEqual(result.response.result['authority'],artifacts._descriptor(b'{"source":1}'))
        self.assertEqual(self.call().artifact,b'{"source":1}')

    def test_control_freezes_before_capability_negotiation(self):
        client=self.client();payload={'nested':[1]};negotiate=CoreClient.negotiate
        def change(core,*args,**kwargs):
            payload['nested'].append(2)
            return negotiate(core,*args,**kwargs)
        with patch.object(CoreClient,'negotiate',change):
            result=artifacts.call_artifact(client,'run-verification-workflow',payload,authority=b'{}')
        self.assertEqual(result.response.result['result']['operation_payload'],{'nested':[1]})

    def test_complete_36_mib_record_exceeds_old_envelope_without_changing_it(self):
        raw=json.dumps(['x'*(3*1024*1024)]*12,separators=(',',':')).encode()
        self.assertGreater(len(raw),LIMITS['max_response_bytes'])
        result=self.call(retained_record=raw)
        self.assertEqual(result.artifact,raw)
        self.assertEqual(LIMITS['max_request_bytes'],16777216)
        self.assertEqual(LIMITS['max_response_bytes'],33554432)
        self.assertEqual(LIMITS['max_json_nodes'],250000)

    def test_partial_stale_noncanonical_and_malformed_results_never_escape(self):
        for mode in ['missing-profile','wrong-hash','wrong-authority','bool-size','partial',
                     'wrong-request','noncanonical','invalid-json','fail-after-write']:
            with self.subTest(mode=mode),self.assertRaises(CoreError):self.call(self.client(mode))

    def test_bounded_controls_stderr_artifact_and_timeout(self):
        for mode in ['flood-stdout','flood-stderr','flood-artifact']:
            with self.subTest(mode=mode),self.assertRaises(CoreTransportError):
                self.call(self.client(mode),output_limit=100)
        with self.assertRaises(CoreTimeout):self.call(self.client('stall',timeout_seconds=.2))
        start=time.monotonic()
        with self.assertRaises(CoreCancelled):
            self.call(self.client('stall'),cancelled=lambda:time.monotonic()-start>.2)
        with self.assertRaises(CoreCancelled):self.call(cancelled=lambda:True)

    def test_release_pin_and_output_boundary_are_rechecked(self):
        with self.assertRaises(CoreUnavailable):self.call(self.client(expected_sha256='0'*64))
        self.assertEqual(self.call(output_limit=12).artifact,b'{"source":1}')
        with self.assertRaises(CoreTransportError):self.call(output_limit=11)
        for value in [True,0,artifacts.MAX_ARTIFACT_BYTES+1]:
            with self.assertRaises(CoreProtocolError):self.call(output_limit=value)
        client=self.client();digest=hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.assertEqual(self.call(CoreClient(self.path,expected_sha256=digest)).artifact,b'{"source":1}')
