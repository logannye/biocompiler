"""Complete historical imports, literal scope and corpus authority inventory."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('architecture_build_campaign', ROOT/'tools/freeze_architecture_build.py')
campaign=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(campaign)
DIGEST='1b93ea91ecb5f6fc35bce14bd9d0ba878c3f96ab9f343f5400d0c4b6f58525bd'

class ArchitectureBuildCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus=json.loads(campaign.CORPUS.read_bytes());cls.docs=cls.corpus['documents']
        cls.records={x['id']:x for x in cls.corpus['records']}
    def value(self,identity):return self.docs[self.records[identity]['normalized']]
    def test_exact_full_inventory_documents_and_wire_bounds(self):
        self.assertEqual(campaign.inventory(self.corpus),DIGEST)
        self.assertEqual(self.corpus['inventory_fingerprint'],DIGEST)
        self.assertEqual((len(self.records),len(self.corpus['rejections']),len(self.docs)),(48,117,50))
        self.assertEqual(campaign.encoded(self.corpus),campaign.CORPUS.read_bytes())
        nodes=0;pending=[self.corpus]
        while pending:
            value=pending.pop();nodes+=1
            if isinstance(value,dict):nodes+=len(value);pending.extend(value.values())
            elif isinstance(value,list):pending.extend(value)
        self.assertLessEqual(nodes,250_000)
        self.assertLess(len(campaign.CORPUS.read_bytes()),16*1024*1024)
        for identity,document in self.docs.items():self.assertEqual(campaign.fingerprint(document),identity)
        for group in ('records','rejections'):
            self.assertEqual(len({x['id'] for x in self.corpus[group]}),len(self.corpus[group]))
    def test_every_record_and_intended_rejection_replays(self):
        for item in self.corpus['records']:
            raw=campaign.changed(self.docs[item['document']],item['edits'])
            parsed=campaign.KINDS[item['kind']].from_dict(raw)
            self.assertEqual(parsed.to_dict(),self.docs[item['normalized']])
            self.assertEqual(parsed.fingerprint,item['normalized'])
        for item in self.corpus['rejections']:
            raw=campaign.changed(self.docs[item['document']],item['edits'])
            with self.assertRaises(campaign.SerializationError,msg=item['id']):campaign.KINDS[item['kind']].from_dict(raw)
    def test_original_case_b_builds_and_construction_authority_are_intact(self):
        for variant in ('base','parameter-default','parameter-override'):
            original=json.loads((ROOT/'tests/conformance/case-b'/variant/'candidate.json').read_bytes())
            self.assertEqual(self.value('case_b/'+variant),original)
            self.assertEqual(self.value('construction/'+variant),original['construction'])
            self.assertEqual(self.value('plan/'+variant),original['plan'])
    def test_independent_literals_and_ordering(self):
        self.assertEqual(self.value('literal/gap'),{'schema_version':'biocompiler.architecture_gap.v0.1','category':'missing_implementation','code':'declared_gap','requirement_ids':['r'],'candidate_ids':[],'message':'Missing declared realization.','conflict_set':[]})
        self.assertEqual(self.value('literal/realization'),{'schema_version':'biocompiler.requirement_realization.v0.1','id':'r','source_node_ids':['node'],'refinement_ids':[],'status':'unresolved','assumptions':[],'reasons':['Needs a realization.']})
        self.assertEqual([x['id'] for x in self.value('plan/ordered_ledger')['ledger']],['z','a'])
        self.assertEqual([x['id'] for x in self.value('plan/instances')['instances']],['a','z'])
        self.assertEqual(self.value('gap/sorted')['requirement_ids'],['a','z'])
        self.assertEqual(self.value('assessment/pass')['unresolved'],['z','a'])
        self.assertEqual(self.value('assessment/pass')['assumptions'],[' z ','a\n'])
    def test_historical_status_does_not_confer_acceptance(self):
        report=self.value('assessment/pass')
        self.assertEqual(report['outcome'],'pass');self.assertFalse(report['translation_complete']);self.assertTrue(report['unresolved'])
        stale=self.value('construction/stale_reconstruction_is_historical')
        self.assertEqual(stale['assessment']['reconstructed_fingerprint'],'f'*64)
        self.assertFalse(self.corpus['coverage']['fresh_acceptance'])
        self.assertEqual(self.value('export/historical_prefix_only')['fasta'],'>')
        for item in self.corpus['records']:
            if item['kind']=='assessment':
                raw=self.docs[item['normalized']]
                self.assertFalse(raw['search_verified']);self.assertEqual(raw['empirical_validation'],'unknown');self.assertEqual(raw['human_therapeutic_admission'],'not_admitted')
    def test_all_kinds_have_shape_and_semantic_negatives(self):
        self.assertEqual({x['kind'] for x in self.corpus['records']},set(campaign.KINDS))
        self.assertEqual({x['kind'] for x in self.corpus['rejections']},set(campaign.KINDS))
        for kind in campaign.KINDS:
            ids={x['id'] for x in self.corpus['rejections'] if x['kind']==kind}
            self.assertIn(kind+'/extra',ids);self.assertIn(kind+'/schema',ids)
            self.assertTrue(any(x.startswith(kind+'/missing/') for x in ids))
    def test_mutation_of_complete_inventory_changes_identity(self):
        bad=deepcopy(self.corpus);bad['records'].pop();self.assertNotEqual(campaign.inventory(bad),DIGEST)
        bad=deepcopy(self.corpus);bad['rejections'][0]['expected_code']='accepted';self.assertNotEqual(campaign.inventory(bad),DIGEST)
        bad=deepcopy(self.corpus);bad['coverage']['fresh_acceptance']=True;self.assertNotEqual(campaign.inventory(bad),DIGEST)

if __name__=='__main__':unittest.main()
