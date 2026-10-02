"""Complete original producer corpus identities and strict storage boundaries."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import freeze_architecture_producer as fixture
from biocompiler.ir.serialization import fingerprint

PIN='269e64293c36d52a5ad797c5c2808e52b0072e520992ade9bfa9f5de97dff90a'
class ArchitectureProducerCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.index,cls.documents=fixture.load()
    def rehash(self,index):index['inventory_fingerprint']=fixture.inventory(index);return index
    def test_complete_typed_corpus_and_independent_pin(self):
        self.assertEqual(fixture.check_corpus(self.index,self.documents),PIN)
        self.assertEqual(len(self.index['coverage']['methods']),39)
        self.assertEqual(sum(item['method'].split('.')[-1].startswith('test_') for item in self.index['coverage']['methods']),35)
        self.assertEqual(self.index['coverage']['diagnostic_exceptions'],[])
    def test_full_original_case_b_and_installed_inventory(self):
        metadata={item['id']:item for item in self.index['documents']}
        for variant in ('base','parameter-default','parameter-override'):
            case=next(case for case in self.index['cases'] if case['id']==f'case_b/{variant}/compile/0')
            for key,filename in (('request','request.json'),('build','candidate.json')):
                self.assertEqual(metadata[case[key]]['format'],'full')
                original=json.loads((ROOT/'tests/conformance/case-b'/variant/filename).read_bytes())
                self.assertEqual(fixture.canonical(fixture.resolve(self.index,self.documents,case[key])),fixture.canonical(original))
        self.assertEqual(len(self.index['coverage']['installed']),13)
    def test_all_storage_bytes_and_one_level_resolution_independently(self):
        metadata={item['id']:item for item in self.index['documents']}
        def edit(value,path,replacement,remove=False):
            target=value
            for key in path[:-1]:target=target[key]
            if remove:del target[path[-1]]
            else:target[path[-1]]=deepcopy(replacement)
        for identity,item in metadata.items():
            stored=self.documents[identity]
            if item['format']=='full':raw=deepcopy(stored)
            else:
                base=metadata[item['base']]
                self.assertEqual(base['format'],'full');self.assertEqual(base['kind'],item['kind'])
                raw=deepcopy(self.documents[item['base']])
                for change in stored['edits']:edit(raw,change['path'],change.get('value'),change['op']=='remove')
            self.assertEqual(fingerprint(raw),identity)
            self.assertEqual(len(fixture.encoded(raw)),item['resolved_bytes'])
            path=fixture.DOCUMENTS/(identity+'.json')
            expected=(json.dumps(stored,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode() if item['format']=='full' else (json.dumps(stored,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n').encode()
            self.assertEqual(path.read_bytes(),expected)
            fixture.location_paths(raw)
    def test_missing_case_and_duplicate_case_rejected_after_rehash(self):
        index=deepcopy(self.index);index['cases'].pop();index['coverage']['cases']-=1
        with self.assertRaises(AssertionError):fixture.check_corpus(self.rehash(index),self.documents)
        index=deepcopy(self.index);index['cases'][1]['id']=index['cases'][0]['id']
        with self.assertRaises(AssertionError):fixture.check_corpus(self.rehash(index),self.documents)
    def test_unknown_operation_and_forged_method_inventory_rejected(self):
        index=deepcopy(self.index);index['cases'][0]['operation']='cached_success'
        with self.assertRaises(AssertionError):fixture.check_corpus(self.rehash(index),self.documents)
        index=deepcopy(self.index);index['coverage']['methods'][0]['method']='not_an_executed_method'
        with self.assertRaises(AssertionError):fixture.check_corpus(self.rehash(index),self.documents)
    def test_mismatched_matching_result_hash_rejected(self):
        index=deepcopy(self.index);case=next(case for case in index['cases'] if case['operation']=='match');case['expected']['exhausted']=not case['expected']['exhausted']
        with self.assertRaises(AssertionError):fixture.check_corpus(self.rehash(index),self.documents)
    def test_undeclared_diagnostic_exception_rejected(self):
        index=deepcopy(self.index);index['coverage']['diagnostic_exceptions']=['ignore_all_messages']
        with self.assertRaises(AssertionError):fixture.check_corpus(self.rehash(index),self.documents)
    def test_missing_or_extra_document_rejected(self):
        documents=dict(self.documents);documents.pop(next(iter(documents)))
        with self.assertRaises(AssertionError):fixture.check_corpus(self.index,documents)
        documents=dict(self.documents);documents['0'*64]={}
        with self.assertRaises(AssertionError):fixture.check_corpus(self.index,documents)
    def test_delta_missing_descent_cyclic_baseline_and_wrong_kind_rejected(self):
        base={'entries':[{'value':1}]}
        for edits in ([{'op':'set','path':['missing','value'],'value':2}],
                      [{'op':'remove','path':['entries',0]}],
                      [{'op':'set','path':[],'value':{}}],
                      [{'op':'set','path':['entries',True],'value':0}]):
            with self.assertRaises(AssertionError):fixture.apply_edits(base,edits)
        descriptor=next(item for item in self.index['documents'] if item['format']=='delta')
        for mode in ('cycle','kind'):
            index=deepcopy(self.index);items={item['id']:item for item in index['documents']};documents=deepcopy(self.documents)
            if mode=='cycle':
                items[descriptor['id']]['base']=descriptor['id'];documents[descriptor['id']]['base']=descriptor['id']
                items[descriptor['id']]['stored_fingerprint']=fingerprint(documents[descriptor['id']]);items[descriptor['id']]['bytes']=len(fixture.stored_encoded(documents[descriptor['id']],'delta'))
            else:items[descriptor['base']]['kind']='different_kind'
            with self.assertRaises(AssertionError):fixture.resolve(index,documents,descriptor['id'])
    def test_absolute_source_location_rejected_recursively(self):
        for filename in ('/Users/person/source.py','/home/runner/work/source.py','/tmp/source.py','C:\\work\\source.py'):
            with self.assertRaises(AssertionError):fixture.location_paths({'wrapped':[{'source_location':{'file':filename,'line':7,'function':'author'}}]})
        fixture.location_paths({'source':{'file':'examples/source.py','line':7,'function':'author'}})
    def test_matching_pair_limits_and_exact_bindings_fresh(self):
        from biocompiler.compiler.architecture_matching import match_architecture_refinement
        cases=[case for case in self.index['cases'] if case['operation']=='match' and case['expected']['exhausted']]
        self.assertTrue(cases)
        for case in cases:
            refinement=fixture.decode('refinement',fixture.resolve(self.index,self.documents,case['refinement']))
            behavior=fixture.decode('behavior',fixture.resolve(self.index,self.documents,case['behavior']))
            circuit=fixture.decode('circuit',fixture.resolve(self.index,self.documents,case['circuit'])) if case['circuit'] else None
            result=match_architecture_refinement(refinement,behavior,circuit=circuit,max_states=case['max_states'],max_instances=case['max_instances'])
            self.assertEqual(fixture.canonical(fixture.match_document(result)),fixture.canonical(case['expected']))
    def test_derived_construction_identity_boundaries_preserve_complete_results(self):
        from biocompiler.compiler.payload_architecture import compile_payload_architecture
        counts={}
        for case in self.index['cases']:
            if case['operation']!='compile' or not case['id'].startswith('supplementary/construction_id_'):continue
            request=fixture.decode('request',fixture.resolve(self.index,self.documents,case['request']))
            actual=compile_payload_architecture(request)
            expected=fixture.resolve(self.index,self.documents,case['build'])
            self.assertEqual(fixture.canonical(actual.to_dict()),fixture.canonical(expected))
            name=case['id'].split('/')[1];counts[name]=len(request.id.encode('utf-8'))
            if name=='construction_id_exact':self.assertEqual(actual.status,'compiled')
            else:
                self.assertEqual(actual.status,'no_solution')
                self.assertEqual([(gap.code,gap.message) for alternative in actual.alternatives for gap in alternative.gaps],
                    [('construction_authority_rejected','Circuit construction identity exceeds its byte limit.' if name=='construction_id_utf8_over' else
                      'Invalid or excessive Circuit construction identity text.')])
        self.assertEqual(counts,{'construction_id_exact':4067,'construction_id_one_over':4068,
            'construction_id_request_maximum':4080,'construction_id_utf8_over':4068})
    def test_namespaced_template_identity_boundaries_preserve_complete_results(self):
        from biocompiler.compiler.payload_architecture import compile_payload_architecture
        seen=[]
        for case in self.index['cases']:
            if case['operation']!='compile' or not case['id'].startswith('supplementary/template_id_'):continue
            request=fixture.decode('request',fixture.resolve(self.index,self.documents,case['request']))
            actual=compile_payload_architecture(request)
            self.assertEqual(fixture.canonical(actual.to_dict()),fixture.canonical(fixture.resolve(self.index,self.documents,case['build'])))
            name=case['id'].split('/')[1];seen.append(name)
            if name=='template_id_exact':self.assertEqual(actual.status,'compiled')
            else:
                self.assertEqual(actual.status,'no_solution')
                message='Payload template identity exceeds its byte limit.' if name=='template_id_utf8_over' else 'Invalid or excessive Payload template identity text.'
                self.assertEqual([(gap.code,gap.message) for alternative in actual.alternatives for gap in alternative.gaps],
                    [('construction_authority_rejected',message)])
        self.assertEqual(seen,['template_id_exact','template_id_one_over','template_id_maximum','template_id_utf8_over'])
    def test_nonexecutable_source_root_preserves_explicit_contradiction(self):
        from biocompiler.semantics.payload_execution import derive_source_execution
        for name in ('source_roots_valid','source_roots_invalid'):
            case=next(case for case in self.index['cases'] if case['id']=='supplementary/'+name+'/source/0')
            source=fixture.decode('source',fixture.resolve(self.index,self.documents,case['source']))
            actual=derive_source_execution(source)
            self.assertEqual(fixture.canonical(actual.to_dict()),fixture.canonical(fixture.resolve(self.index,self.documents,case['manifest'])))
            self.assertEqual(actual.behavior is None,name=='source_roots_invalid')
            if name=='source_roots_invalid':
                self.assertIn(('invalid_source_execution_semantics','Behavior roots must include exactly all executable declarations.'),
                    [(item.code,item.message) for item in actual.diagnostics])
    def test_source_and_small_installed_build_fresh(self):
        from biocompiler.compiler.payload_architecture import compile_payload_architecture,export_payload_architecture
        case=next(case for case in self.index['cases'] if case['id']=='installed/B/compile/0')
        request=fixture.decode('request',fixture.resolve(self.index,self.documents,case['request']))
        actual=compile_payload_architecture(request)
        self.assertEqual(fixture.canonical(actual.to_dict()),fixture.canonical(fixture.resolve(self.index,self.documents,case['build'])))
        export=next(case for case in self.index['cases'] if case['id']=='installed/B/export/0')
        result=export_payload_architecture(actual,expected_request=request)
        self.assertEqual(fingerprint(result.to_dict()),export['expected_fingerprint']);self.assertEqual(result.fasta,export['fasta'])

if __name__=='__main__':unittest.main()
