"""Frozen Python wire boundaries retain every occurrence without helper parity."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import check_native_synthetic_inspection as p
from tests import test_native_synthetic_inspection_campaign as fixtures


class SyntheticInspectionBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = p.Corpus()
        boundaries = [case for case in cls.full.cases if case['id'] in p.BOUNDARY_IDS]
        supplement = p.decode((p.ROOT / 'tests/conformance/synthetic-inspection-supplemental-v1.json').read_bytes())
        cases = [next(case for case in supplement['cases'] if case['operation'] == operation)
                 for operation in p.declaration()['operations']]
        cls.small = SimpleNamespace(cases=deepcopy([*boundaries, *cases]), pins=cls.full.pins,
            census=cls.full.census, original_count=cls.full.original_count)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.artifacts = cls.root / p.ARTIFACT_DIRECTORY
        cls.artifacts.mkdir()
        table = {}
        for (role, _), case in p.expected_cases(cls.small).items():
            if role == 'core' and p.wire_boundary(case) is not None:
                continue
            if role == 'verify':
                response, code = p.envelope(role, 'replaced', case['operation'], 'unsupported', None, [p.UNSUPPORTED]), 3
            elif case['error'] is not None:
                response, code = p.envelope(role, 'replaced', case['operation'], 'error', None, [case['error']]), 2
            else:
                response, code = p.envelope(role, 'replaced', case['operation'], 'ok', p.expected_semantic(case), []), 0
            table[role + ':' + case['operation'] + ':' + p.digest(case['payload'])] = [response, code]
        # The inert peer recognizes only these exact immutable bytes. It never
        # executes product semantics and is not evidence of native behavior.
        data = {'table': table, 'raw': boundaries[0]['evidence']['original_native_arguments'],
                'capabilities': {role: fixtures.SyntheticInspectionCampaignTests.capabilities(role) for role in p.ROLES}}
        (cls.root / 'fixture.json').write_bytes(p.canonical(data))
        script = '''import hashlib,json,pathlib,sys
role=pathlib.Path(sys.argv[0]).name.removeprefix("biocompiler-")
data=json.loads(pathlib.Path(sys.argv[0]).with_name("fixture.json").read_bytes())
raw=sys.stdin.buffer.read()
def enc(x):return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
identity={"implementation":"ocaml","version":"0.1.0","protocol":"biocompiler.core.v1","executable":role}
if role=="core" and raw==data["raw"].encode("ascii"):
 response={"protocol":"biocompiler.core.v1","request_id":None,"operation":None,"status":"error","result":None,"diagnostics":[{"code":"invalid_json","message":"Unexpected JSON token.","path":"byte:1303"}],"core":identity}
 code=2
else:
 request=json.loads(raw)
 if request["operation"]=="capabilities":
  response={"protocol":"biocompiler.core.v1","request_id":request["request_id"],"operation":"capabilities","status":"ok","diagnostics":[],"result":data["capabilities"][role],"core":identity}
  code=0
 else:
  response,code=data["table"][role+":"+request["operation"]+":"+hashlib.sha256(enc(request["payload"])).hexdigest()]
  response["request_id"]=request["request_id"]
sys.stdout.buffer.write(enc(response)+b"\\n")
sys.exit(code)
'''
        from biocompiler.core_client import CoreClient
        for module in p.SOURCE_MODULES:
            p.importlib.import_module(module)
        cls.clients = []
        for role in p.ROLES:
            path = cls.root / ('biocompiler-' + role)
            path.write_text('#!' + sys.executable + '\n' + script)
            path.chmod(0o700)
            cls.clients.append(CoreClient(path, role=role, expected_sha256=p.sha(path.read_bytes())))
        cls.receipt = {'checks': [], 'artifacts': {}, '_artifact_directory': str(cls.artifacts),
                       'executables': {client.role: str(client.executable) for client in cls.clients}}
        p.campaign(cls.clients, cls.small, cls.receipt)
        cls.receipt['completed_checks'] = len(cls.receipt['checks'])

    def validate(self, receipt=None):
        value = self.receipt if receipt is None else receipt
        return p.validate_checks(value, self.small, p.Artifacts(self.artifacts, value['artifacts']))

    def test_every_original_case_has_explicit_shape_and_boundary_authority(self):
        self.assertEqual(p.preflight_cases(self.full), {'cases': 9660, 'native_wire_boundaries': list(p.BOUNDARY_IDS)})
        self.assertEqual(len(p.expected_cases(self.full)), 9668)
        self.assertEqual(p.metadata(self.full)['public_helper_occurrences'], 9658)
        for case in self.small.cases[:2]:
            self.assertEqual(case['evidence']['observation']['native']['expected_code'], 'invalid_json')
            self.assertEqual(case['expected_public']['value'], [])
            self.assertEqual(case['evidence']['original_result'], case['payload']['record'])
        malformed = deepcopy(self.full.cases[0]); malformed['payload']['registry'] = 'unreviewed'
        with self.assertRaisesRegex(AssertionError, 'complete object'):
            p.preflight_cases(SimpleNamespace(cases=[malformed]))

    def test_actual_python_peers_preserve_both_boundaries_and_complete_receipts(self):
        result = self.validate()
        self.assertEqual(len(result['checks']), 18)
        self.assertEqual([row['id'] for row in self.receipt['checks']], [key[1] for key in p.expected_cases(self.small)])
        self.assertEqual(sum(len(row['exchanges']) for row in self.receipt['checks']) + 1, 29)
        artifacts = p.Artifacts(self.artifacts, self.receipt['artifacts'])
        for row, case in zip(self.receipt['checks'][:2], self.small.cases[:2]):
            self.assertIsNone(row['public'])
            self.assertFalse(artifacts.json(row['boundary'])['native_helper_equivalence'])
            self.assertEqual(artifacts.raw(row['exchanges'][1]['request']), case['evidence']['original_native_arguments'].encode('ascii'))
            self.assertEqual(p.decode(artifacts.raw(row['exchanges'][1]['response'])), {
                'protocol': 'biocompiler.core.v1', 'request_id': None, 'operation': None, 'status': 'error',
                'result': None, 'diagnostics': [{'code': 'invalid_json', 'message': 'Unexpected JSON token.', 'path': 'byte:1303'}],
                'core': {'implementation': 'ocaml', 'version': '0.1.0', 'protocol': 'biocompiler.core.v1', 'executable': 'core'}})

    def test_original_case_or_native_mapping_cannot_be_relabelled(self):
        for field in ('id', 'stage', 'code', 'raw', 'property', 'result'):
            case = deepcopy(self.small.cases[0])
            if field == 'id': case['id'] = 'unreviewed-boundary'
            elif field == 'stage': case['evidence']['observation']['native']['native_stage'] = 'domain'
            elif field == 'code': case['evidence']['observation']['native']['expected_code'] = 'other'
            elif field == 'raw': case['evidence']['original_native_arguments'] += ' '
            elif field == 'property': case['evidence']['properties']['exercised_requirement_ids'] = ['invented']
            else: case['evidence']['original_result'] += ' '
            with self.subTest(field=field), self.assertRaises(AssertionError): p.wire_boundary(case)
        case = deepcopy(self.full.cases[0]); case['id'] = p.BOUNDARY_IDS[0]
        with self.assertRaises((AssertionError, KeyError)): p.wire_boundary(case)

    def test_missing_duplicate_or_falsely_equivalent_boundary_fails(self):
        for field in ('missing', 'duplicate', 'public', 'classification', 'exit', 'executable'):
            value = deepcopy(self.receipt)
            if field == 'missing': value['checks'].pop(0)
            elif field == 'duplicate': value['checks'][1] = deepcopy(value['checks'][0])
            elif field == 'public': value['checks'][0]['public'] = value['checks'][2]['public']
            elif field == 'classification': del value['checks'][0]['boundary']
            elif field == 'exit': value['checks'][0]['exchanges'][1]['exit_code'] = 0
            else: value['checks'][0]['exchanges'][1]['executable'] = value['executables']['verify']
            with self.subTest(field=field), self.assertRaises(AssertionError): self.validate(value)

    def test_rehashed_wire_and_boundary_evidence_cannot_authorize_success(self):
        for field in ('request', 'response', 'boundary', 'guard'):
            for mutation in (('bytes',) if field != 'response' else ('bytes', 'code', 'path', 'identity', 'status')):
                value = deepcopy(self.receipt); row = value['checks'][0]
                item = row['exchanges'][1] if field in ('request', 'response') else row
                old = item[field]; raw = (self.artifacts / (old + '.bin')).read_bytes()
                if mutation == 'bytes': raw += b' '
                else:
                    response = p.decode(raw)
                    if mutation == 'code': response['diagnostics'][0]['code'] = 'other'
                    elif mutation == 'path': response['diagnostics'][0]['path'] = 'byte:1304'
                    elif mutation == 'identity': response['request_id'] = 'invented'
                    else: response['status'] = 'ok'
                    raw = p.canonical(response) + b'\n'
                pin = p.artifact(value, raw); item[field] = pin
                with self.subTest(field=field, mutation=mutation), self.assertRaises(AssertionError): self.validate(value)
                (self.artifacts / (pin + '.bin')).unlink()

    def test_raw_exchange_rechecks_role_pin_and_cannot_use_expected_values_as_input(self):
        import biocompiler.core_client as transport
        case = self.small.cases[0]
        changed = deepcopy(case); changed['expected_value']['exercised_requirement_ids'] = ['forged']
        with patch.object(transport, '_exchange', side_effect=AssertionError('Transport must not run')) as exchange:
            with self.assertRaises(AssertionError): p.invoke_boundary(changed, self.clients[0])
            exchange.assert_not_called()
            with self.assertRaises(AssertionError): p.invoke_boundary(case, self.clients[1])
            exchange.assert_not_called()
        class Unpinned:
            role = 'core'; expected_sha256 = '0' * 64; executable = self.clients[0].executable
            def capabilities(self): pass
        with patch.object(transport, '_exchange', side_effect=AssertionError('Transport must not run')) as exchange:
            with self.assertRaisesRegex(AssertionError, 'executable changed'): p.invoke_boundary(case, Unpinned())
            exchange.assert_not_called()
