"""Retain exact construction proposals and freshly checked public workflows.

All original regression assertions run, including Python CLI publication tests.
Native replay covers typed molecular proposals/workflows, not filesystem CLI
publication. No native implementation identity alters canonical candidates.
"""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

from biocompiler.ir.serialization import fingerprint
from biocompiler.errors import SerializationError
from biocompiler.ir.circuit_construction import CircuitConstructionRequest, TransformStep, OPERATION_TYPES
from biocompiler.ir.circuit_molecules import CircuitMolecule
from biocompiler.artifacts.circuit_construction import ConstructionCandidate, ConstructedValue
from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.artifacts.circuit_molecules import CircuitMoleculeRecord
from biocompiler.verification.circuit_construction import CircuitConstructionAssessment

ROOT=Path(__file__).resolve().parents[1]
CORPUS=ROOT/'tests/conformance/construction-producer-v1.json'
DOCUMENTS=CORPUS.with_suffix('')
SCHEMA='biocompiler.construction_producer_conformance.v1'
MODULES=(('test_circuit_construction_producer','ConstructionProducerTests'),
         ('test_circuit_processing_producer','ProcessingProducerTests'),
         ('test_circuit_recoding_producer','RecodingProducerTests'),
         ('test_circuit_construction_edges','CircuitConstructionEdgeTests'),
         ('test_circuit_construction_workflow','CircuitConstructionWorkflowTests'),
         ('test_circuit_recoding','CircuitRecodingTests'))
KINDS=dict(request=CircuitConstructionRequest,candidate=ConstructionCandidate,step=TransformStep,
           root=CircuitMolecule,value=ConstructedValue,build=CircuitConstructionBuild,
           assessment=CircuitConstructionAssessment,molecules=CircuitMoleculeRecord)
ERRORS={
 'Construction build differs from independent complete authority.':'construction_build_authority',
 'Construction assessment differs from fresh complete replay.':'construction_assessment_mismatch',
 'Diagnostic construction cannot produce a complete-set handoff.':'construction_handoff_mode',
 'Complete-set handoff requires fresh successful construction and payload checks.':'construction_handoff_incomplete',
 'Complete-set handoff cannot omit a required member.':'construction_handoff_inventory',
}
def require(value,message):
    if not value:raise AssertionError(message)
def encoded(raw):return (json.dumps(raw,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
def inventory(index):return fingerprint({key:value for key,value in index.items() if key!='inventory_fingerprint'})
def bounds(raw,maximum=4_000_000):
    pending=[(raw,0)];count=0
    while pending:
        value,depth=pending.pop();count+=1
        require(count<=250_000 and depth<=128,'Producer fixture node/depth bound')
        if isinstance(value,dict):pending.extend((v,depth+1) for pair in value.items() for v in pair)
        elif isinstance(value,list):pending.extend((v,depth+1) for v in value)
    data=encoded(raw);require(len(data)<=maximum,'Producer fixture byte bound')
    require(b'/Users/' not in data and b'/home/runner/' not in data,'Machine-specific producer authority')
    return len(data)
def source_methods():
    if str(ROOT/'tests') not in sys.path:sys.path.insert(0,str(ROOT/'tests'))
    result=[]
    for module_name,class_name in MODULES:
        cls=getattr(importlib.import_module(module_name),class_name)
        prefix=module_name+'.'+class_name+'.'
        result.append(prefix+'setUpClass')
        result.extend(prefix+name for name in sorted(dir(cls)) if name.startswith('test_'))
    return result

def build_corpus():
    for directory in (str(ROOT),str(ROOT/'tests')):
        if directory not in sys.path:sys.path.insert(0,directory)
    import biocompiler as bc
    import biocompiler.cli as cli
    import biocompiler.frontend.graph as graph
    import biocompiler.backends.circuit_construction as producer
    import biocompiler.backends.circuit_recoding as recoder
    import biocompiler.compiler.circuit_construction as workflow
    modules=[(importlib.import_module(module),getattr(importlib.import_module(module),name)) for module,name in MODULES]
    construct=producer.construct_circuit_candidate;recode=recoder.construct_recoding_step
    workflows={name:getattr(workflow,name) for name in ('build_circuit_construction','verify_circuit_construction','verified_circuit_molecules')}
    documents={};kinds={};constructions=[];recodings=[];public=[];ledger=[];boundaries=[];counts=Counter();current=['']
    def doc(kind,value):
        raw=value.to_dict();identity=fingerprint(raw)
        if identity not in documents:
            bounds(raw);require(KINDS[kind].from_dict(raw).fingerprint==identity,'Producer retained record normalization differs')
            documents[identity]=raw;kinds[identity]=kind
        require(kinds[identity]==kind,'Producer document kind collision')
        return identity
    def identity(kind):
        key=current[0]+'/'+kind;number=counts[key];counts[key]+=1
        return key+'/'+str(number)
    def candidate(request):
        result=construct(request)
        constructions.append(dict(id=identity('construct'),request=doc('request',request),candidate=doc('candidate',result),
            produced_residues=producer.MAX_CUMULATIVE_PRODUCED_RESIDUES,final_residues=producer.MAX_RESIDUES,origin='source_assertion'))
        return result
    def recoding(step,available,remaining_budget):
        values,used,code=recode(step,available,remaining_budget)
        bindings=[dict(id=key,kind='root' if isinstance(value,CircuitMolecule) else 'value',
            document=doc('root' if isinstance(value,CircuitMolecule) else 'value',value)) for key,value in sorted(available.items())]
        recodings.append(dict(id=identity('recoding'),step=doc('step',step),available=bindings,remaining_residues=remaining_budget,
            values=[doc('value',value) for value in values],used_residues=used,diagnostic=code))
        return values,used,code
    def public_call(name):
        original=workflows[name]
        def call(*args,**kwargs):
            first=args[0] if args else None;expected=kwargs.get('expected_request')
            valid=isinstance(first,CircuitConstructionRequest) if name=='build_circuit_construction' else (
                isinstance(first,CircuitConstructionBuild) and isinstance(expected,CircuitConstructionRequest))
            try:result=original(*args,**kwargs)
            except (SerializationError,TypeError) as error:
                if not valid:
                    boundaries.append(dict(id=identity('typed_boundary'),operation=name,error_type=type(error).__name__))
                else:
                    require(str(error) in ERRORS,'Unclassified producer workflow failure: '+str(error))
                    public.append(dict(id=identity('workflow'),operation=name,build=doc('build',first),
                        request=doc('request',expected),expected_error=ERRORS[str(error)],result=None))
                raise
            if name=='build_circuit_construction':
                public.append(dict(id=identity('workflow'),operation=name,build=None,request=doc('request',first),
                    expected_error=None,result=doc('build',result)))
            else:
                public.append(dict(id=identity('workflow'),operation=name,build=doc('build',first),request=doc('request',expected),
                    expected_error=None,result=doc('assessment' if name=='verify_circuit_construction' else 'molecules',result)))
            return result
        return call
    location=graph.SourceLocation
    def portable(file,line,function):
        path=Path(file)
        if path.is_absolute():file=path.resolve().relative_to(ROOT).as_posix()
        return location(file,line,function)
    with ExitStack() as stack:
        stack.enter_context(patch.object(graph,'SourceLocation',portable))
        for module in (producer,workflow,*[module for module,_ in modules]):
            if hasattr(module,'construct_circuit_candidate'):stack.enter_context(patch.object(module,'construct_circuit_candidate',candidate))
        for module in (recoder,*[module for module,_ in modules]):
            if hasattr(module,'construct_recoding_step'):stack.enter_context(patch.object(module,'construct_recoding_step',recoding))
        for name in workflows:
            wrapper=public_call(name)
            for module in (workflow,bc,cli):
                if hasattr(module,name):stack.enter_context(patch.object(module,name,wrapper))
        for module,cls in modules:
            prefix=module.__name__+'.'+cls.__name__+'.'
            for item in vars(module).values():
                if callable(getattr(item,'cache_clear',None)):item.cache_clear()
            current[0]=prefix+'setUpClass';cls.setUpClass()
            ledger.append(dict(method=current[0],status='source_assertions_executed'))
            for method in sorted(name for name in dir(cls) if name.startswith('test_')):
                current[0]=prefix+method;cls(method).debug()
                ledger.append(dict(method=current[0],status='source_assertions_executed'))
            cls.tearDownClass()
            print('Captured '+prefix.rstrip('.'),flush=True)
    case_b=[]
    for variant in ('base','parameter-default','parameter-override'):
        raw=json.loads((ROOT/'tests/conformance/case-b'/variant/'candidate.json').read_bytes())['construction']
        request=CircuitConstructionRequest.from_dict(raw['request']);result=construct(request)
        require(encoded(result.to_dict())==encoded(raw['candidate']),'Original complete case B candidate differs')
        case=dict(id='case_b/'+variant,request=doc('request',request),candidate=doc('candidate',result),produced_residues=1_000_000,
            final_residues=1_000_000,origin='complete_retained_case_b')
        constructions.append(case);case_b.append(case['id'])
    operations=sorted({step['operation']['schema_version'] for case in constructions for step in documents[case['request']]['steps']})
    require(operations==sorted(cls.schema_version for cls in OPERATION_TYPES),'Producer operation closure incomplete')
    for entry in ledger:
        prefix=entry['method']+'/'
        entry['retained_calls']=sum(item['id'].startswith(prefix) for group in (constructions,recodings,public,boundaries) for item in group)
    index=dict(schema_version=SCHEMA,
        claim_scope='Exact untrusted molecular proposals and fresh typed workflow correspondence only; no biological or human admission claim.',
        compatibility=dict(native_work_maximum=50_000_000,native_work_error='construction_producer_limit',
            residue_limits='Optional reductions only; same legacy diagnostics and attempted-work accounting.',
            workflow_error_codes=ERRORS,
            source_only_boundaries='Python class misuse, CLI publication and monkeypatch allocation sentinels execute as source assertions. Native replay uses typed calls and independent allocation/budget literals.',
            candidate_identity='No generated producer/tool pin exists; every complete candidate fingerprint must match exactly.'),
        documents=[dict(id=key,kind=kinds[key],bytes=len(encoded(documents[key]))) for key in sorted(documents)],
        constructions=constructions,recodings=recodings,workflows=public,typed_boundaries=boundaries,
        coverage=dict(methods=ledger,case_b=case_b,operations=operations,constructions=len(constructions),recodings=len(recodings),
            workflows=len(public),typed_boundaries=len(boundaries),documents=len(documents),exclusions=[]))
    index['inventory_fingerprint']=inventory(index)
    check_corpus(index,documents)
    return index,documents

def check_corpus(index,documents,*,fresh=False):
    require(index['schema_version']==SCHEMA and index['inventory_fingerprint']==inventory(index),'Producer inventory drift')
    bounds(index,16*1024*1024)
    entries={item['id']:item for item in index['documents']}
    require(len(entries)==len(index['documents']) and set(entries)==set(documents),'Missing/extra/duplicate producer documents')
    require(len(encoded(index))+sum(item['bytes'] for item in entries.values())<=16*1024*1024,'Producer campaign byte ceiling')
    require([entry['method'] for entry in index['coverage']['methods']]==source_methods(),'Changed original producer assertion inventory')
    require(index['coverage']['exclusions']==[] and all(entry['status']=='source_assertions_executed' for entry in index['coverage']['methods']),'Unexecuted source assertion')
    calls=[row['id'] for group in ('constructions','recodings','workflows','typed_boundaries') for row in index[group]]
    require(len(calls)==len(set(calls)),'Producer captured-call identities collide')
    for entry in index['coverage']['methods']:
        require(entry['retained_calls']==sum(identity.startswith(entry['method']+'/') for identity in calls),'Stale producer method call census')
    used=set()
    def reference(kind,identity):
        require(identity in entries and entries[identity]['kind']==kind,'Wrong producer authority kind')
        used.add(identity);return documents[identity]
    for kind in ('constructions','recodings','workflows','typed_boundaries'):
        rows=index[kind];require(len({row['id'] for row in rows})==len(rows),'Duplicate producer case')
        require(index['coverage'][kind]==len(rows),'Stale producer case census')
    for case in index['constructions']:
        request=reference('request',case['request']);candidate=reference('candidate',case['candidate'])
        require(candidate['request_fingerprint']==case['request'],'Candidate lost complete source authority')
        require(0<=case['produced_residues']<=1_000_000 and 0<=case['final_residues']<=1_000_000,'Invalid producer residue ceiling')
        if fresh:
            import biocompiler.backends.circuit_construction as producer
            with patch.object(producer,'MAX_CUMULATIVE_PRODUCED_RESIDUES',case['produced_residues']),patch.object(producer,'MAX_RESIDUES',case['final_residues']):
                actual=producer.construct_circuit_candidate(CircuitConstructionRequest.from_dict(request))
            require(encoded(actual.to_dict())==encoded(candidate),'Fresh producer candidate differs: '+case['id'])
    for case in index['recodings']:
        reference('step',case['step'])
        for binding in case['available']:reference(binding['kind'],binding['document'])
        for value in case['values']:reference('value',value)
        require(case['diagnostic'] is None or case['values']==[],'Partial recoding output escaped atomic failure')
        require(0<=case['used_residues']<=case['remaining_residues']<=1_000_000,'Recoding residue census')
    for case in index['workflows']:
        reference('request',case['request'])
        if case['build'] is not None:reference('build',case['build'])
        if case['result'] is not None:
            kind={'build_circuit_construction':'build','verify_circuit_construction':'assessment','verified_circuit_molecules':'molecules'}[case['operation']]
            reference(kind,case['result'])
        else:require(case['expected_error'] in ERRORS.values(),'Unknown workflow failure')
    require(used==set(entries),'Unused producer fixture documents')
    require(index['coverage']['documents']==len(documents),'Stale document census')
    require(index['coverage']['operations']==sorted(cls.schema_version for cls in OPERATION_TYPES),'Incomplete producer operation inventory')
    actual_operations={step['operation']['schema_version'] for case in index['constructions'] for step in documents[case['request']]['steps']}
    require(sorted(actual_operations)==index['coverage']['operations'],'Stale actual producer operation inventory')
    require(set(index['coverage']['case_b'])=={'case_b/base','case_b/parameter-default','case_b/parameter-override'},'Missing original case B authority')
    for identity,raw in documents.items():
        entry=entries[identity];require(bounds(raw)==entry['bytes'] and fingerprint(raw)==identity,'Changed producer document')
        require(KINDS[entry['kind']].from_dict(raw).fingerprint==identity,'Unnormalized producer authority')
def load():
    require(CORPUS.stat().st_size<=16*1024*1024,'Producer index read bound')
    index=json.loads(CORPUS.read_bytes())
    docs={}
    for entry in index['documents']:
        path=DOCUMENTS/(entry['id']+'.json');require(path.stat().st_size<=4_000_000,'Producer document read bound')
        docs[entry['id']]=json.loads(path.read_bytes())
    require({path.stem for path in DOCUMENTS.glob('*.json')}==set(docs),'Extra producer files')
    return index,docs
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');parser.add_argument('--check',action='store_true')
    args=parser.parse_args();index,docs=build_corpus()
    if args.write:
        DOCUMENTS.mkdir(exist_ok=True)
        for path in DOCUMENTS.glob('*.json'):
            if path.stem not in docs:path.unlink()
        for key,raw in docs.items():(DOCUMENTS/(key+'.json')).write_bytes(encoded(raw))
        CORPUS.write_bytes(encoded(index))
    else:
        require({path.stem for path in DOCUMENTS.glob('*.json')}==set(docs),'Extra producer files')
        require(CORPUS.read_bytes()==encoded(index),'Producer index drift')
        for key,raw in docs.items():require((DOCUMENTS/(key+'.json')).read_bytes()==encoded(raw),'Producer document drift')
    print(json.dumps({key:value for key,value in index['coverage'].items() if key not in ('methods','case_b','operations')}|{'inventory':index['inventory_fingerprint']},sort_keys=True))
if __name__=='__main__':main()
