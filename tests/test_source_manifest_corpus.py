"""Historical source manifests and independent expected-authority inventory."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

from biocompiler.errors import SerializationError
from biocompiler.ir.serialization import fingerprint

PATH=Path(__file__).resolve().parents[1]/'tools/freeze_source_manifest.py'
SPEC=importlib.util.spec_from_file_location('source_manifest_corpus_under_test',PATH)
campaign=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(campaign)
EXPECTED_INVENTORY='ba237e1adcbcb6e1853edd138f06edb7aaa1d729cfb2b31d61d8127d03d11d32'
EXPECTED_RECORDS='a3c23d6913756b2ef8a07f04d26f146846a7d5c820dc5c83a821d1e65d4621cf'
EXPECTED_REJECTIONS='f275c6700c1c6a520dec46cf1abd3273c4dc1a1ed1621005e0d8d6a90e4ec341'
EXPECTED_LITERALS='e12c054d13d8403d3e393c6cf4742e8e24c3496a0010711dcb01e9b5365653e5'


def validate(corpus):
    assert corpus['inventory_sha256']==campaign.inventory(corpus)==EXPECTED_INVENTORY,'Source manifest full inventory drift'
    assert fingerprint(sorted([item['id'],item['kind']] for item in corpus['records']))==EXPECTED_RECORDS,'Source manifest kind inventory drift'
    assert fingerprint(sorted([item['id'],item['kind'],item['expected_code']] for item in corpus['rejections']))==EXPECTED_REJECTIONS,'Source manifest intended diagnostic drift'
    assert fingerprint(corpus['literal_expectations'])==EXPECTED_LITERALS,'Source manifest literal drift'
    campaign.check_corpus(corpus)
    for case in corpus['rejections']:
        raw=campaign.edited(corpus['documents'][case['document']],case['edits'])
        try: campaign.PARSERS[case['kind']].from_dict(raw)
        except SerializationError: pass
        else: raise AssertionError('Source manifest intended rejection accepted: '+case['id'])
    return corpus


class SourceManifestCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content=campaign.CORPUS.read_bytes()
        cls.corpus=json.loads(cls.content)
        cls.records={item['id']:item for item in cls.corpus['records']}
        cls.checks={item['id']:item for item in cls.corpus['checks']}

    def document(self,identity):
        return self.corpus['documents'][self.records[identity]['normalized']]

    def test_full_corpus_reproduces_with_independent_inventory_pins(self):
        rebuilt=validate(campaign.build_corpus())
        self.assertEqual(campaign.encoded(rebuilt),self.content)
        self.assertEqual((len(rebuilt['records']),len(rebuilt['rejections']),len(rebuilt['checks'])),(34,56,35))
        self.assertEqual({item['kind'] for item in rebuilt['records']},{'manifest','output','diagnostic'})

    def test_independent_literals_preserve_big_integer_signed_zero_and_order(self):
        self.assertEqual(self.document('literal/output'),campaign.LITERAL_OUTPUT)
        self.assertEqual(self.document('literal/diagnostic'),campaign.LITERAL_DIAGNOSTIC)
        raw=self.document('literal/output')
        self.assertEqual(raw['lineage'],['z','','z'])
        self.assertEqual(raw['product'],'')
        self.assertEqual(raw['semantics']['amount'],9007199254740993)
        self.assertIn(b'"fraction": -0.0',campaign.encoded(raw))
        self.assertEqual(self.document('literal/diagnostic')['source_node_ids'],['a','a'])
        manifest=self.document('literal/unavailable')
        self.assertIsNone(manifest['behavior'])
        self.assertEqual(manifest['diagnostics'],[])
        self.assertFalse(self.records['literal/unavailable']['complete'])

    def test_every_trigger_activation_and_diagnostic_category_is_retained(self):
        outputs=[self.document(identity) for identity in self.records if identity.startswith('output/')]
        self.assertEqual({(item['trigger'],item['activation']) for item in outputs},
                         {(trigger,activation) for trigger in ('condition','event') for activation in ('level','event','onset','explicit_duration')})
        self.assertEqual({self.document('diagnostic/'+kind)['category'] for kind in ('unsupported_semantics','missing_refinement','contradiction')},
                         {'unsupported_semantics','missing_refinement','contradiction'})

    def test_original_case_b_and_complete_wrapped_authority_are_preserved(self):
        for variant in ('base','parameter-default','parameter-override'):
            original=json.loads((campaign.ROOT/f'tests/conformance/case-b/{variant}/candidate.json').read_bytes())
            self.assertEqual(self.document('case_b/'+variant),original['execution'])
        for kind in ('behavior_request','deployment_request','acceptance_request'):
            raw=self.document('wrapped/'+kind)
            self.assertNotEqual(raw['source']['schema_version'],'biocompiler.build_request.v0.1')
            self.assertIn('wrapped_source_obligations',[item['code'] for item in raw['diagnostics']])
            value=campaign.SourceExecutionManifest.from_dict(raw)
            self.assertEqual(value.source.to_dict(),raw['source'])
            self.assertNotEqual(value.source_fingerprint,value.build_request.fingerprint)

    def test_historical_import_does_not_establish_source_correspondence(self):
        raw=self.document('historical/arbitrary_inventories')
        value=campaign.SourceExecutionManifest.from_dict(raw)
        self.assertEqual(value.to_dict(),raw)
        self.assertEqual(raw['roles'],['','same','same'])
        self.assertEqual(raw['ledger'],[{'declared':True}])
        self.assertFalse(value.complete)
        check=self.checks['historical/diagnostics_are_not_authority']
        self.assertEqual(check['legacy_expected'],dict(failures=[],unresolved=[]))
        for identity in ('mutation/source_authority','mutation/output_guard','mutation/ledger_authority','mutation/channel_transport'):
            self.assertTrue(self.checks[identity]['expected']['failures'])
        change=self.checks['mutation/behavior_identity']
        self.assertEqual(change['expected']['failures'],['source_behavior:lowering_source_identity'])
        self.assertNotEqual(change['expected']['failures'],change['legacy_expected']['failures'])

    def test_4096_output_boundary_is_structural_and_generated_at_runtime(self):
        raw=deepcopy(self.document('empty_role'))
        output=dict(campaign.LITERAL_OUTPUT,lineage=[],semantics={})
        raw['outputs']=[output]*4096
        value=campaign.SourceExecutionManifest.from_dict(raw)
        self.assertEqual(len(value.outputs),4096)
        self.assertTrue(value.complete)
        raw['outputs'].append(output)
        with self.assertRaises(SerializationError): campaign.SourceExecutionManifest.from_dict(raw)
        self.assertEqual(len(self.document('historical/max_roles')['roles']),1024)
        self.assertEqual(len(self.document('historical/max_ledger')['ledger']),1025)

    def test_full_inventory_cannot_be_rehashed_to_hide_missing_or_changed_cases(self):
        for group in ('records','rejections','checks','literal_expectations'):
            changed=deepcopy(self.corpus);changed[group].pop();changed['inventory_sha256']=campaign.inventory(changed)
            with self.assertRaisesRegex(AssertionError,'inventory'): validate(changed)
        changed=deepcopy(self.corpus);changed['rejections'][0]['expected_code']='wrong';changed['inventory_sha256']=campaign.inventory(changed)
        with self.assertRaisesRegex(AssertionError,'inventory'): validate(changed)
        changed=deepcopy(self.corpus);next(iter(changed['documents'].values()))['extra']=True
        with self.assertRaises(AssertionError): validate(changed)

    def test_whole_wire_corpus_is_bounded_and_machine_independent(self):
        pending=[(self.corpus,0)];nodes=0;maximum_depth=0
        while pending:
            value,depth=pending.pop();nodes+=1;maximum_depth=max(maximum_depth,depth)
            if isinstance(value,dict): pending.extend((item,depth+1) for pair in value.items() for item in pair)
            elif isinstance(value,list): pending.extend((item,depth+1) for item in value)
            elif isinstance(value,str): self.assertLessEqual(len(value.encode()),4*1024*1024)
        self.assertLess(nodes,250000)
        self.assertLessEqual(maximum_depth,128)
        self.assertLess(len(self.content),16*1024*1024)
        self.assertNotIn(str(campaign.ROOT).encode(),self.content)
        self.assertNotIn(b'/Users/',self.content)


if __name__=='__main__': unittest.main()
