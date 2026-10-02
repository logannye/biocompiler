"""Retain independent transition correspondence, never producer acceptance."""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler.artifacts.circuit_construction import ConstructedValue, DerivedSegment
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_molecules import CircuitMolecule
from biocompiler.ir.circuit_transitions import ChemistryTransition, FeatureTransition
from biocompiler.ir.molecule_chemistry import MoleculeChemistry
from biocompiler.ir.serialization import fingerprint
from biocompiler.semantics.molecule_coordinates import CoordinateSpace, CoordinatePath, IndexSpan
from biocompiler.verification.circuit_transitions import resolve_transitions

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tests import test_circuit_transitions as source_tests
from tools.freeze_construction_artifacts import LITERAL_VALUE
CORPUS=ROOT/'tests/conformance/transition-check-v1.json'
SCHEMA='biocompiler.transition_check_conformance.v1'
EXPECTED_INVENTORY='33f2d16cb3d4e03c33fe3b1e4d0ee5fbae0a075046bda8176c9b789bd56f85b7'
EXPECTED_SECTIONS={
    'coverage':'34f4b4468d4b86036468f95a2fa61310d74cb7fdb9789136b0325c9533edde06',
    'literal_expectations':'c9145f5b6b5cca12c99692a20545ed0421eb3545fd6c142224898b36c2c3cc50',
    'runtime_cases':'655dc74a401a932e983e1580f046fcb83de0a4095236c25da5a204c692da16c5',
    'typed_unrepresentable':'4a02b420a6f60dd2c9680b3b65f6959739dd80cd903a23dbfbc7fe471b2c8f68',
}


def encoded(value):
    return (json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2,sort_keys=True)+'\n').encode()


def result_dict(result):
    return dict(chemistry=None if result.chemistry is None else result.chemistry.to_dict(),
                features=[item.to_dict() for item in result.features],diagnostics=list(result.diagnostics),unsupported=list(result.unsupported))


def segment_dict(value):
    return dict(schema_version=DerivedSegment.schema_version,destination=value.destination.to_dict(),source_id=value.source_id,
                source_path=value.source_path.to_dict(),rule=value.rule)


def call_dict(chemistry,features,kwargs):
    inputs=[]
    for key,value in kwargs['inputs'].items():
        if not isinstance(value,(CircuitMolecule,ConstructedValue)):
            return None
        inputs.append(dict(id=key,kind='molecule' if isinstance(value,CircuitMolecule) else 'value',value=value.to_dict()))
    return dict(chemistry_transition=chemistry.to_dict(),feature_transition=features.to_dict(),inputs=inputs,
                output_sequence=kwargs['output_sequence'],output_space=kwargs['output_space'].to_dict(),
                derivation=[segment_dict(value) for value in kwargs['derivation']],sequence_extent=kwargs.get('sequence_extent','complete'))


def decode_call(raw):
    chemistry=ChemistryTransition.from_dict(raw['chemistry_transition'])
    features=FeatureTransition.from_dict(raw['feature_transition'])
    values={item['id']:(CircuitMolecule if item['kind']=='molecule' else ConstructedValue).from_dict(item['value']) for item in raw['inputs']}
    derivation=tuple(DerivedSegment.from_dict(value) for value in raw['derivation'])
    return chemistry,features,dict(inputs=values,output_sequence=raw['output_sequence'],output_space=CoordinateSpace.from_dict(raw['output_space']),
                                  derivation=derivation,sequence_extent=raw['sequence_extent'])


def run(raw):
    chemistry,features,kwargs=decode_call(raw)
    return result_dict(resolve_transitions(chemistry,features,**kwargs))


def runtime_recipes():
    return [dict(id='runtime/'+kind+'/'+str(count),kind=kind,count=count) for kind,counts in (
        ('feature',(100000,100001)),('modification',(100000,100001)),('tail',(100000,100001)),
        ('copied_feature',(100000,)),('segments',(4096,4097)),('path_blocks',(2048,2049)),
    ) for count in counts]


def runtime_call(recipe):
    kind,count=recipe['kind'],recipe['count']
    length=2 if kind=='path_blocks' else 1 if kind=='segments' else count
    source=source_tests.make_molecule('source','A'*length)
    total=2*count if kind in {'copied_feature','path_blocks'} else count
    output_space=source_tests.frame(total)
    transition=source_tests.replacements({source.id:source},source.chemistry)
    feature_transition=source_tests.features()
    derivation=(source_tests.segment(source),)
    if kind in {'feature','copied_feature'}:
        source=replace(source,features=(source_tests.annotation(source.space,'feature',(0,length)),))
        outputs=(source_tests.annotation(output_space,'first',(0,length)),)
        decision='exact'
        if kind=='copied_feature':
            outputs=(*outputs,source_tests.annotation(output_space,'second',(length,2*length)))
            derivation=(source_tests.segment(source),source_tests.segment(source,destination=length));decision='split'
        feature_transition=source_tests.features(source_tests.feature_map(source,decision,outputs))
    elif kind=='modification':
        modification=source_tests.mod(positions=(),scope='all_matching_bases')
        source=replace(source,chemistry=replace(source.chemistry,modifications=(modification,)))
        transition=source_tests.replacements({source.id:source},source.chemistry,(source_tests.disposition(source,'modification:mod'),))
    elif kind=='tail':
        tail=source_tests.TailDeclaration('declared','represented_terminal',source_tests.TailLength('exact',exact=length),source_tests.path(source.space,(0,length)),source_tests.provenance())
        source=replace(source,chemistry=replace(source.chemistry,terminal_tail=tail))
        output=replace(source.chemistry,terminal_tail=replace(tail,path=source_tests.path(output_space,(0,length))))
        transition=source_tests.replacements({source.id:source},output,(source_tests.disposition(source,'terminal_tail'),))
    elif kind=='segments':
        derivation=tuple(source_tests.segment(source,destination=index) for index in range(count))
    elif kind=='path_blocks':
        derivation=tuple(source_tests.Segment(IndexSpan(index*2,index*2+2),source.id,source_tests.path(source.space,(0,1),(1,2))) for index in range(count))
    else: raise AssertionError('Unknown runtime recipe')
    return transition,feature_transition,dict(inputs={source.id:source},output_sequence='A'*total,output_space=output_space,derivation=derivation,sequence_extent='complete')


def compress_runtime(value):
    if isinstance(value,str) and len(value)>=1000 and set(value)=={'A'}:
        return {'__repeat_ascii__':len(value)}
    if isinstance(value,list):
        if len(value)>1000 and all(isinstance(item,dict) and item.get('schema_version')==DerivedSegment.schema_version for item in value):
            width=value[0]['destination']['end']-value[0]['destination']['start']
            assert all(item==dict(value[0],destination=dict(value[0]['destination'],start=index*width,end=(index+1)*width)) for index,item in enumerate(value))
            return {'__repeat_segments__':dict(count=len(value),width=width,template=value[0])}
        return [compress_runtime(item) for item in value]
    if isinstance(value,dict): return {key:compress_runtime(item) for key,item in value.items()}
    return value


def expand_runtime(value):
    if isinstance(value,list): return [expand_runtime(item) for item in value]
    if isinstance(value,dict):
        if set(value)=={'__repeat_ascii__'}:
            count=value['__repeat_ascii__'];assert type(count) is int and 0<=count<=1000000
            return 'A'*count
        if set(value)=={'__repeat_segments__'}:
            recipe=value['__repeat_segments__'];count,width=recipe['count'],recipe['width'];assert 0<=count<=4097 and width in {1,2}
            return [dict(recipe['template'],destination=dict(recipe['template']['destination'],start=index*width,end=(index+1)*width)) for index in range(count)]
        return {key:expand_runtime(item) for key,item in value.items()}
    return value


def build_corpus():
    documents={};cases=[];parser_rejections=[];excluded=[];source_witnesses=[];literal_expectations=[]
    def retain(identity,chemistry,features,kwargs,result=None):
        expected=result_dict(resolve_transitions(chemistry,features,**kwargs)) if result is None else result_dict(result)
        raw=call_dict(chemistry,features,kwargs)
        if raw is None:
            excluded.append(dict(id=identity,reason='Malformed foreign Python object cannot inhabit the abstract typed Input API.',expected=expected))
            return
        digest=fingerprint(raw);documents[digest]=raw
        try: decode_call(raw)
        except SerializationError as error:
            parser_rejections.append(dict(id=identity,document_id=digest,expected_code='invalid_construction_artifact',python_error=str(error),legacy_result=expected))
        else:
            assert run(raw)==expected,identity
            cases.append(dict(id=identity,document_id=digest,expected=expected,fingerprint=fingerprint(expected)))
    for name in unittest.defaultTestLoader.getTestCaseNames(source_tests.CircuitTransitionTests):
        calls=[]
        def capture(chemistry,features,**kwargs):
            result=resolve_transitions(chemistry,features,**kwargs)
            calls.append((chemistry,features,kwargs,result))
            return result
        result=unittest.TestResult()
        with patch.object(source_tests,'resolve_transitions',capture): source_tests.CircuitTransitionTests(name).run(result)
        if not result.wasSuccessful(): raise AssertionError(result.errors+result.failures)
        # Some original tests iterate a frozenset of facets. Their assertions
        # still execute unchanged; assign retained IDs from complete authority,
        # so hash randomization cannot silently replace the meaning of a case.
        calls.sort(key=lambda call: encoded(call_dict(*call[:2],call[2])) if call_dict(*call[:2],call[2]) is not None else b'~')
        for index,(chemistry,features,kwargs,actual) in enumerate(calls):
            retain(name+'/'+str(index),chemistry,features,kwargs,actual)
        source_witnesses.append(dict(test=name,calls=len(calls)))
    literal=ConstructedValue.from_dict(deepcopy(LITERAL_VALUE))
    output=source_tests.frame(1)
    derived=DerivedSegment(IndexSpan(0,1),'source',CoordinatePath(literal.space.id,(IndexSpan(0,1),),'+'),'copy')
    kwargs=dict(inputs={'source':literal},output_sequence='A',output_space=output,derivation=(derived,),sequence_extent='complete')
    for identity,changed,expected in (
        ('literal/empty',dict(kwargs,inputs={}),dict(chemistry=None,features=[],diagnostics=['transition_derivation: Expected bounded participating source values.'],unsupported=[])),
        ('literal/unknown',kwargs,dict(chemistry=LITERAL_VALUE['chemistry'],features=[],diagnostics=[],unsupported=['unknown_output_chemistry: nominal chemistry remains incomplete'])),
        ('literal/changed',dict(kwargs,output_sequence='C'),dict(chemistry=None,features=[],diagnostics=['chemistry_exact_inheritance: Exact chemistry inheritance requires unchanged spelling, alphabet and topology.'],unsupported=[])),
    ):
        retain(identity,source_tests.inherited(),source_tests.features(),changed)
        assert cases[-1]['expected']==expected
        literal_expectations.append(dict(id=identity,expected=expected))
    # Structurally valid geometry and declaration mutants exercise exact report
    # contents; malformed domain inputs are retained in a separate parser stage.
    source=source_tests.make_molecule('source','ACGU')
    base=dict(inputs={source.id:source},output_sequence='ACGU',output_space=source_tests.frame(4),derivation=(source_tests.segment(source),),sequence_extent='complete')
    def add(identity,kwargs=base,chemistry=None,features=None):
        retain('mutation/'+identity,source_tests.inherited() if chemistry is None else chemistry,source_tests.features() if features is None else features,kwargs)
    add('output_length',dict(base,output_sequence='A'))
    add('output_unicode',dict(base,output_sequence='ÅCGU'),chemistry=source_tests.replacements(base['inputs'],source.chemistry))
    add('empty_derivation',dict(base,derivation=()))
    add('partition_gap',dict(base,output_sequence='AACGU',output_space=source_tests.frame(5),derivation=(replace(source_tests.segment(source),destination=IndexSpan(1,5)),)))
    add('short_partition',dict(base,output_sequence='ACGUA',output_space=source_tests.frame(5)))
    add('beyond_source',dict(base,derivation=(replace(source_tests.segment(source),source_path=source_tests.path(source.space,(1,5))),)))
    add('wrong_output_alphabet',dict(base,output_sequence='ACGT',output_space=source_tests.frame(4,alphabet='DNA')))
    add('topology_changed',dict(base,output_space=source_tests.frame(4,topology='circular')))
    add('cut_reordered',dict(base,derivation=(source_tests.segment(source,2,4),source_tests.segment(source,0,2,2))))
    transition=source_tests.replacements(base['inputs'],source.chemistry)
    add('output_chemistry_circular',dict(base,output_space=source_tests.frame(4,topology='circular')),chemistry=transition)
    add('output_chemistry_exact_core',dict(base,sequence_extent='exact_core'),chemistry=transition)
    feature=source_tests.annotation(source.space,'feature',(0,4))
    source=replace(source,features=(feature,))
    featured=dict(base,inputs={source.id:source})
    target=source_tests.annotation(base['output_space'],'mapped',(0,4))
    add('feature_output_unresolved',featured,features=source_tests.features(source_tests.feature_map(source,'exact',(replace(target,path=None),))))
    add('feature_unselected',dict(featured,output_sequence='AC',output_space=source_tests.frame(2),derivation=(source_tests.segment(source,0,2),)),chemistry=source_tests.replacements(featured['inputs'],source.chemistry),features=source_tests.features(source_tests.feature_map(source,'exact',(target,))))
    extra=source_tests.feature_map(source,'unknown',feature_id='missing')
    add('extra_feature_authority',featured,features=source_tests.features(extra))
    chemical_corpus=json.loads((ROOT/'tests/conformance/molecule-chemistry-v1.json').read_bytes())
    chemical_records={item['id']:item for item in chemical_corpus['records']}
    for item in chemical_corpus['validations']:
        space=CoordinateSpace.from_dict(item['space'])
        source=source_tests.make_molecule('context_source','A'*space.length,
            form='mature_protein' if space.alphabet=='protein' else 'delivered_dna' if space.alphabet=='DNA' else 'delivered_rna',topology=space.topology)
        output=MoleculeChemistry.from_dict(chemical_records[item['chemistry_id']]['normalized'])
        transition=source_tests.replacements({source.id:source},output)
        if output.modifications:
            first=transition.dispositions[0]
            first=replace(first,destination_components=first.destination_components+tuple('modification:'+mod.id for mod in output.modifications))
            transition=replace(transition,dispositions=(first,*transition.dispositions[1:]))
        kwargs=dict(inputs={source.id:source},output_sequence=item['sequence'],output_space=space,derivation=(source_tests.segment(source),),sequence_extent=item['sequence_extent'])
        retain('chemistry_context/'+item['id'],transition,source_tests.features(),kwargs)
    runtime=[]
    for recipe in runtime_recipes():
        chemistry,features,kwargs=runtime_call(recipe)
        raw=call_dict(chemistry,features,kwargs)
        expected=result_dict(resolve_transitions(chemistry,features,**kwargs))
        runtime.append(dict(id=recipe['id'],recipe=recipe,template=compress_runtime(raw),expected=expected,fingerprint=fingerprint(expected)))
    coverage=dict(source_tests=source_witnesses,source_test_count=len(source_witnesses),captured_calls=sum(item['calls'] for item in source_witnesses),
                  case_count=len(cases),parser_rejection_count=len(parser_rejections),typed_unrepresentable_count=len(excluded),independent_literal_count=len(literal_expectations),runtime_count=len(runtime))
    corpus=dict(schema_version=SCHEMA,claim_scope='Independent declared chemistry/feature correspondence only; no construction acceptance or biochemical fate.',
                documents=documents,cases=cases,parser_rejections=parser_rejections,typed_unrepresentable=excluded,literal_expectations=literal_expectations,runtime_cases=runtime,coverage=coverage)
    corpus['inventory_sha256']=inventory(corpus)
    return corpus


def inventory(corpus):
    return fingerprint(dict(cases=sorted(item['id'] for item in corpus['cases']),
                            parser_rejections=sorted([item['id'],item['expected_code']] for item in corpus['parser_rejections']),
                            typed_unrepresentable=sorted(item['id'] for item in corpus['typed_unrepresentable']),runtime_cases=sorted(item['id'] for item in corpus['runtime_cases'])))


def check_corpus(corpus):
    assert corpus['schema_version']==SCHEMA
    assert corpus['inventory_sha256']==inventory(corpus)==EXPECTED_INVENTORY,'Changed transition inventory'
    for key,expected in EXPECTED_SECTIONS.items():
        assert fingerprint(corpus[key])==expected,'Changed independent transition '+key
    ids=[item['id'] for key in ('cases','parser_rejections','typed_unrepresentable') for item in corpus[key]]
    assert len(ids)==len(set(ids)),'Duplicate transition case'
    for digest,raw in corpus['documents'].items(): assert fingerprint(raw)==digest,'Changed transition document pin'
    for case in corpus['cases']:
        actual=run(corpus['documents'][case['document_id']])
        assert encoded(actual)==encoded(case['expected']),'Changed complete transition result: '+case['id']
        assert fingerprint(actual)==case['fingerprint'],'Changed transition result identity'
    for case in corpus['parser_rejections']:
        try: decode_call(corpus['documents'][case['document_id']])
        except SerializationError: pass
        else: raise AssertionError('Intended domain rejection accepted')
    lookup={item['id']:item for item in corpus['cases']}
    for literal in corpus['literal_expectations']: assert encoded(lookup[literal['id']]['expected'])==encoded(literal['expected']),'Changed independent transition literal'
    for case in corpus['runtime_cases']:
        actual=run(expand_runtime(case['template']))
        assert encoded(actual)==encoded(case['expected']) and fingerprint(actual)==case['fingerprint'],'Changed runtime transition expectation'
    pending=[(corpus,0)];count=0;depth=0
    while pending:
        value,level=pending.pop();count+=1;depth=max(depth,level)
        assert count<=250000 and level<=128,'Transition corpus exceeds wire node/depth budget'
        if isinstance(value,dict): pending.extend((part,level+1) for pair in value.items() for part in pair)
        elif isinstance(value,list): pending.extend((part,level+1) for part in value)
        elif isinstance(value,str): assert len(value.encode())<=4*1024*1024
    data=encoded(corpus);assert len(data)<=16*1024*1024 and b'/Users/' not in data
    return dict(bytes=len(data),nodes=count,depth=depth)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');args=parser.parse_args()
    corpus=build_corpus();usage=check_corpus(corpus);data=encoded(corpus)
    if args.write: CORPUS.write_bytes(data)
    elif not CORPUS.is_file() or CORPUS.read_bytes()!=data: raise SystemExit('Transition-check corpus is stale; review before --write')
    print(json.dumps(dict(corpus['coverage'],**usage,inventory_sha256=corpus['inventory_sha256'])))
if __name__=='__main__': main()
