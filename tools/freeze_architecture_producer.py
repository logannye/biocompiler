"""Freeze complete producer outputs from existing assertions and installed fixtures.

Source-only Python oracle capture. Test-only one-level deltas preserve complete
original documents and their canonical identities; production accepts no deltas.
"""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from dataclasses import replace
import importlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
for directory in (str(ROOT),str(ROOT/'tools'),str(ROOT/'tests')):
    if directory not in sys.path:sys.path.insert(0,directory)
import biocompiler as bc
from biocompiler.ir.serialization import fingerprint
from biocompiler.ir.architecture_build import PayloadArchitectureRequest,PayloadArchitectureBuild
from biocompiler.ir.payload_architecture import PayloadArchitectureRefinement
from biocompiler.ir.behavior import BehaviorProgram
from biocompiler.ir.circuit_intent import CircuitRequest
from biocompiler.ir.implementation_requirements import source_request_from_dict
from biocompiler.semantics.payload_execution import SourceExecutionManifest
from freeze_architecture_check import (require,encoded,canonical,stored_encoded,inventory,bounds,
    apply_edits,difference,resolve,DELTA_SCHEMA,MAX_STORED_BYTES,MAX_RESOLVED_BYTES)

CORPUS=ROOT/'tests/conformance/architecture-producer-v1.json'
DOCUMENTS=CORPUS.with_suffix('')
SCHEMA='biocompiler.architecture_producer_conformance.v1'
MODULES=(('test_architecture_matching','ArchitectureMatchingTests'),
 ('test_architecture_matching','AutomaticArchitectureCompilationTests'),
 ('test_architecture_search_bounds','ArchitectureSearchBoundsTests'),
 ('test_payload_architecture','PayloadArchitectureTests'))
KINDS={'source','manifest','refinement','behavior','circuit','request','build'}
MAX_CASES=2048

_base_bounds=bounds
def location_paths(raw):
    pending=[raw]
    while pending:
        value=pending.pop()
        if isinstance(value,dict):
            if {'file','line','function'}<=set(value) and isinstance(value['file'],str):
                name=value['file']
                require(not Path(name).is_absolute() and not (len(name)>2 and name[1]==':' and name[2] in '/\\'),
                        'Absolute source location in complete producer authority')
            pending.extend(value.values())
        elif isinstance(value,list):pending.extend(value)

def bounds(raw,maximum=4_000_000,nodes=100_000,depth=96):
    size=_base_bounds(raw,maximum,nodes,depth);location_paths(raw);return size

def method_inventory():
    return [name+'.'+cls+'.'+method for name,cls in MODULES
            for method in ['setUpClass',*sorted(item for item in dir(getattr(importlib.import_module(name),cls)) if item.startswith('test_'))]]


def decode(kind,raw):
    return source_request_from_dict(raw) if kind=='source' else {
      'manifest':SourceExecutionManifest,'refinement':PayloadArchitectureRefinement,
      'behavior':BehaviorProgram,'circuit':CircuitRequest,'request':PayloadArchitectureRequest,
      'build':PayloadArchitectureBuild}[kind].from_dict(raw)

def match_document(result):
    return dict(instances=[item.to_dict() for item in result.instances],states_examined=result.states_examined,
                exhausted=result.exhausted,diagnostics=list(result.diagnostics))

def build_corpus():
    require(os.environ.get('PYTHONHASHSEED')=='0','Deterministic capture requires PYTHONHASHSEED=0')
    graph=importlib.import_module('biocompiler.frontend.graph')
    execution=importlib.import_module('biocompiler.semantics.payload_execution')
    matching=importlib.import_module('biocompiler.compiler.architecture_matching')
    producer=importlib.import_module('biocompiler.compiler.payload_architecture')
    originals={};kinds={};cases=[];ledger=[];counts=Counter();current=[''];force_full=set();captured_bytes=0
    old_source=execution.derive_source_execution;old_match=matching.match_architecture_refinement
    old_compile=producer.compile_payload_architecture;old_export=producer.export_payload_architecture
    location=graph.SourceLocation
    def portable(file,line,function):
        path=Path(file)
        if path.is_absolute():file=path.resolve().relative_to(ROOT).as_posix()
        return location(file,line,function)
    def retain(kind,value):
        nonlocal captured_bytes
        raw=value.to_dict();identity=fingerprint(raw)
        if identity not in originals:
            captured_bytes+=bounds(raw);require(captured_bytes<=MAX_RESOLVED_BYTES,'Capture byte bound')
            require(canonical(decode(kind,raw).to_dict())==canonical(raw),'Typed normalization drift')
            originals[identity]=raw;kinds[identity]=kind
        require(kinds[identity]==kind,'Conflicting document kinds')
        return identity
    def capture(operation,**fields):
        key=current[0]+'/'+operation;number=counts[key];counts[key]+=1
        require(len(cases)<MAX_CASES,'Producer case bound')
        case=dict(id=key+'/'+str(number),operation=operation,**fields);cases.append(case);return case
    def source(value):
        result=old_source(value)
        capture('source',source=retain('source',value),manifest=retain('manifest',result))
        return result
    def match(refinement,behavior,*,circuit=None,max_states=100_000,max_instances=256):
        result=old_match(refinement,behavior,circuit=circuit,max_states=max_states,max_instances=max_instances)
        expected=match_document(result)
        capture('match',refinement=retain('refinement',refinement),behavior=retain('behavior',behavior),
            circuit=retain('circuit',circuit) if circuit is not None else None,
            max_states=max_states,max_instances=max_instances,expected=expected,expected_fingerprint=fingerprint(expected),
            instantiated_fingerprints=[fingerprint(matching.instantiate_architecture_refinement(refinement,item).to_dict()) for item in result.instances])
        return result
    def compile(value):
        result=old_compile(value)
        capture('compile',request=retain('request',value),build=retain('build',result))
        return result
    def export(value,*,expected_request):
        result=old_export(value,expected_request=expected_request)
        capture('export',request=retain('request',expected_request),build=retain('build',value),
            expected_fingerprint=fingerprint(result.to_dict()),fasta=result.fasta)
        return result
    modules=[(importlib.import_module(name),getattr(importlib.import_module(name),cls)) for name,cls in MODULES]
    with ExitStack() as stack:
        stack.enter_context(patch.object(graph,'SourceLocation',portable))
        for module,name,replacement in ((execution,'derive_source_execution',source),(producer,'derive_source_execution',source),
          (matching,'match_architecture_refinement',match),(producer,'match_architecture_refinement',match),
          (producer,'compile_payload_architecture',compile),(producer,'export_payload_architecture',export),
          (bc,'compile_payload_architecture',compile),(bc,'export_payload_architecture',export)):
            stack.enter_context(patch.object(module,name,replacement))
        patched=set()
        for module,_ in modules:
            for name,replacement in (('derive_source_execution',source),('match_architecture_refinement',match),
                    ('compile_payload_architecture',compile)):
                if hasattr(module,name) and (module.__name__,name) not in patched:
                    patched.add((module.__name__,name));stack.enter_context(patch.object(module,name,replacement))
            for item in vars(module).values():
                if callable(getattr(item,'cache_clear',None)):item.cache_clear()
        for module,cls in modules:
            prefix=module.__name__+'.'+cls.__name__
            for method in ['setUpClass',*sorted(name for name in dir(cls) if name.startswith('test_'))]:
                current[0]=prefix+'.'+method;before=len(cases)
                print('Capturing '+current[0],flush=True)
                cls.setUpClass() if method=='setUpClass' else cls(method).debug()
                ledger.append(dict(method=current[0],status='source_assertions_executed',retained_calls=len(cases)-before))
            cls.tearDownClass()
        from examples.payload_architectures import make_architecture_request
        from examples.architecture_automation import make_automatic_case,make_automation_request
        from examples.architecture_control_designs import make_control_request
        installed=[(name,make_architecture_request(name,variants=('one_rna','many_components_one_rna','two_rna','one_rna_helper'),independent_shutdown=True) if name=='A' else make_architecture_request(name)) for name in 'ABCDEF']
        installed += [('automatic_timing',make_automation_request())]
        installed += [('automatic_'+name.lower(),make_automatic_case(name)) for name in 'BF']
        installed += [(name,make_control_request(name)) for name in ('memory_reset','state_reset','production_adjustment','activity_control')]
        installed_ids=[]
        for name,request in installed:
            current[0]='installed/'+name;print('Capturing '+current[0],flush=True)
            build=compile(request);require(build.status=='compiled','Installed producer outcome')
            export(build,expected_request=request);installed_ids.append(current[0])
        case_b=[]
        for variant in ('base','parameter-default','parameter-override'):
            directory=ROOT/'tests/conformance/case-b'/variant
            request=PayloadArchitectureRequest.from_dict(json.loads((directory/'request.json').read_bytes()))
            original_build=json.loads((directory/'candidate.json').read_bytes())
            current[0]='case_b/'+variant;build=compile(request)
            require(canonical(build.to_dict())==canonical(original_build),'Complete original case-B producer drift')
            export(build,expected_request=request);force_full.update((retain('request',request),retain('build',build)));case_b.append(current[0])
        supplementary=[]
        base=make_architecture_request('A',variants=('one_rna',))
        for name,identity in (('construction_id_exact','r'*4067),('construction_id_one_over','r'*4068),
                              ('construction_id_request_maximum','r'*4080),('construction_id_utf8_over','é'*2034)):
            current[0]='supplementary/'+name
            build=compile(replace(base,id=identity))
            expected='compiled' if name=='construction_id_exact' else 'no_solution'
            require(build.status==expected,'Derived construction identity boundary changed')
            if expected=='no_solution':
                require([(gap.code,gap.message) for alternative in build.alternatives for gap in alternative.gaps]==[
                    ('construction_authority_rejected','Circuit construction identity exceeds its byte limit.' if name=='construction_id_utf8_over' else
                     'Invalid or excessive Circuit construction identity text.')],
                    'Construction identity rejection text changed')
            supplementary.append(current[0])
        raw_base=base.to_dict()
        template_id=raw_base['library']['refinements'][0]['templates'][0]['id']
        def renamed(raw,identity):
            if isinstance(raw,str):return identity if raw==template_id else raw
            if isinstance(raw,list):return [renamed(value,identity) for value in raw]
            if isinstance(raw,dict):return {key:renamed(value,identity) for key,value in raw.items()}
            return raw
        for name,identity in (('template_id_exact','t'*4086),('template_id_one_over','t'*4087),
                              ('template_id_maximum','t'*4096),('template_id_utf8_over','é'*2044)):
            current[0]='supplementary/'+name
            build=compile(PayloadArchitectureRequest.from_dict(renamed(raw_base,identity)))
            expected='compiled' if name=='template_id_exact' else 'no_solution'
            require(build.status==expected,'Namespaced template identity boundary changed')
            if expected=='no_solution':
                require([(gap.code,gap.message) for alternative in build.alternatives for gap in alternative.gaps]==[
                    ('construction_authority_rejected','Payload template identity exceeds its byte limit.' if name=='template_id_utf8_over' else
                     'Invalid or excessive Payload template identity text.')],
                    'Namespaced template rejection text changed')
            supplementary.append(current[0])
        for name,invalid in (('source_roots_valid',False),('source_roots_invalid',True)):
            current[0]='supplementary/'+name
            raw=base.source.to_dict()
            raw_build=raw
            while 'intent' not in raw_build:
                raw_build=raw_build[next(key for key in ('deployment_request','behavior_request','build_request') if key in raw_build)]
            node=next(node for node in raw_build['intent']['nodes'] if node['kind']=='qualitative')
            if invalid:raw_build['intent']['roots'].append(node['id'])
            result=source(source_request_from_dict(raw))
            require((result.behavior is None)==invalid,'Literal root validity changed')
            if invalid:
                require(any(item.code=='invalid_source_execution_semantics' and
                    item.message=='Behavior roots must include exactly all executable declarations.' for item in result.diagnostics),
                    'Invalid source root lost its exact contradiction')
            supplementary.append(current[0])
    original=dict(documents=originals,kinds=kinds,cases=cases,ledger=ledger,installed=installed_ids,case_b=case_b,supplementary=supplementary,force_full=sorted(force_full))
    checkpoint=ROOT/'generated/migration-next/architecture-producer-originals.json'
    checkpoint.parent.mkdir(parents=True,exist_ok=True);checkpoint.write_bytes(encoded(original))
    return pack_corpus(original)

def pack_corpus(original):
    raw_documents=original['documents'];kinds=original['kinds'];force_full=set(original['force_full'])
    documents={};metadata=[];full={kind:[] for kind in KINDS}
    for identity in sorted(raw_documents,key=lambda value:(value not in force_full,kinds[value],value)):
        raw=raw_documents[identity];kind=kinds[identity];size=len(encoded(raw));best=None;best_size=size
        if identity not in force_full:
            for baseline in full[kind]:
                delta=dict(schema_version=DELTA_SCHEMA,base=baseline,edits=difference(raw_documents[baseline],raw))
                delta_size=len(stored_encoded(delta,'delta'))
                if delta_size<best_size:
                    try:bounds(delta)
                    except AssertionError:continue
                    best=(baseline,delta);best_size=delta_size
        if best is None or best_size>size*.72:
            stored=raw;format_='full';base=None;full[kind].append(identity)
        else:
            base,stored=best;format_='delta'
            require(canonical(apply_edits(raw_documents[base],stored['edits']))==canonical(raw),'Delta changed complete original')
        documents[identity]=stored
        metadata.append(dict(id=identity,kind=kind,format=format_,stored_fingerprint=fingerprint(stored),bytes=len(stored_encoded(stored,format_)),resolved_bytes=size,base=base))
    coverage=dict(methods=original['ledger'],installed=original['installed'],case_b=original['case_b'],supplementary=original['supplementary'],cases=len(original['cases']),
      documents=len(documents),operations=dict(sorted(Counter(case['operation'] for case in original['cases']).items())),
      document_kinds=dict(sorted(Counter(kinds.values()).items())),stored_bytes=sum(item['bytes'] for item in metadata),
      resolved_bytes=sum(item['resolved_bytes'] for item in metadata),diagnostic_exceptions=[],
      resource_profile=dict(max_work=200_000_000,matcher_max_work=50_000_000,matcher_output_bytes=16*1024*1024,matcher_output_nodes=250_000,
        native_error_has_no_partial_candidate=True))
    index=dict(schema_version=SCHEMA,oracle='existing_python_producers_with_fresh_independent_checkers',coverage=coverage,
      documents=sorted(metadata,key=lambda item:item['id']),cases=original['cases'])
    index['inventory_fingerprint']=inventory(index)
    require(coverage['stored_bytes']+len(encoded(index))<=MAX_STORED_BYTES,'Stored campaign budget')
    for item in metadata:require(canonical(resolve(index,documents,item['id']))==canonical(raw_documents[item['id']]),'Resolved original drift')
    return index,documents

def load(path=CORPUS):
    require(path.stat().st_size<=MAX_STORED_BYTES,'Index byte bound')
    index=json.loads(path.read_bytes());directory=path.with_suffix('')
    require(sum(item.stat().st_size for item in directory.glob('*.json'))+path.stat().st_size<=MAX_STORED_BYTES,'Stored campaign bound')
    documents={file.stem:json.loads(file.read_bytes()) for file in directory.glob('*.json')}
    return index,documents

def check_corpus(index,documents,*,fresh=False):
    require(index['schema_version']==SCHEMA and index['inventory_fingerprint']==inventory(index),'Producer corpus identity')
    metadata=index['documents'];cases=index['cases'];coverage=index['coverage']
    require(len(cases)==193 and len({case['id'] for case in cases})==len(cases),'Case census')
    require(len(metadata)==166 and len(metadata)==len({item['id'] for item in metadata})==len(documents) and {item['id'] for item in metadata}==set(documents),'Document census')
    require(coverage['cases']==len(cases) and coverage['documents']==len(metadata),'Coverage census')
    require(coverage['operations']==dict(sorted(Counter(case['operation'] for case in cases).items()))=={'source':67,'match':40,'compile':56,'export':30},'Operation census')
    require([item['method'] for item in coverage['methods']]==method_inventory(),'Exact original assertion inventory')
    require(all(item['status']=='source_assertions_executed' and item['retained_calls']==sum(case['id'].startswith(item['method']+'/') for case in cases) for item in coverage['methods']),'Assertion execution ledger')
    require(coverage['installed']==['installed/'+name for name in ['A','B','C','D','E','F','automatic_timing','automatic_b','automatic_f','memory_reset','state_reset','production_adjustment','activity_control']] and coverage['case_b']==['case_b/base','case_b/parameter-default','case_b/parameter-override'],'Installed complete inventory')
    for prefix in coverage['installed']+coverage['case_b']:
        require(sum(case['id'].startswith(prefix+'/compile/') for case in cases)==1 and sum(case['id'].startswith(prefix+'/export/') for case in cases)==1,'Missing complete installed producer/export')
    require(coverage['supplementary']==['supplementary/'+name for name in ('construction_id_exact',
      'construction_id_one_over','construction_id_request_maximum','construction_id_utf8_over',
      'template_id_exact','template_id_one_over','template_id_maximum','template_id_utf8_over',
      'source_roots_valid','source_roots_invalid')],
      'Missing construction identity boundary inventory')
    for prefix in coverage['supplementary']:
        require(sum(case['id'].startswith(prefix+'/compile/') for case in cases)==(0 if '/source_roots_' in prefix else 1) and
                sum(case['id'].startswith(prefix+'/source/') for case in cases)==1,'Missing boundary source/compile pair')
    require(coverage['diagnostic_exceptions']==[],'Undeclared producer diagnostic exception')
    references=set()
    for case in cases:
        operation=case['operation'];require(operation in {'source','match','compile','export'},'Unknown operation')
        expected_keys={'source':{'source','manifest'},'match':{'refinement','behavior','circuit','max_states','max_instances','expected','expected_fingerprint','instantiated_fingerprints'},'compile':{'request','build'},'export':{'request','build','expected_fingerprint','fasta'}}[operation]|{'id','operation'}
        require(set(case)==expected_keys,'Unknown or missing producer case fields')
        if operation=='match':
            require(fingerprint(case['expected'])==case['expected_fingerprint'],'Matching expected identity drift')
            require(type(case['max_states']) is int and 0<=case['max_states']<=1_000_000 and type(case['max_instances']) is int and 0<=case['max_instances']<=256,'Matching input budget drift')
        for key in {'source':('source','manifest'),'match':('refinement','behavior','circuit'),'compile':('request','build'),'export':('request','build')}[operation]:
            if case[key] is not None:references.add(case[key])
    require(references<=set(documents),'Missing producer authority')
    required=references|{item['base'] for item in metadata if item['id'] in references and item['base'] is not None}
    require(required==set(documents),'Unused complete document')
    require(coverage['stored_bytes']==sum(item['bytes'] for item in metadata) and coverage['stored_bytes']+len(encoded(index))<=MAX_STORED_BYTES,'Stored byte census')
    require(coverage['resolved_bytes']==sum(item['resolved_bytes'] for item in metadata)<=MAX_RESOLVED_BYTES,'Resolved byte census')
    for item in metadata:
        require(item['kind'] in KINDS,'Unknown document kind')
        raw=resolve(index,documents,item['id']);location_paths(raw);require(canonical(decode(item['kind'],raw).to_dict())==canonical(raw),'Complete typed identity')
    if fresh:
        producer=importlib.import_module('biocompiler.compiler.payload_architecture')
        execution=importlib.import_module('biocompiler.semantics.payload_execution')
        matching=importlib.import_module('biocompiler.compiler.architecture_matching')
        def read(key):
            descriptor=next(item for item in metadata if item['id']==key)
            return decode(descriptor['kind'],resolve(index,documents,key))
        for case in cases:
            if case['operation']=='source':actual=execution.derive_source_execution(read(case['source'])).to_dict();expected=resolve(index,documents,case['manifest'])
            elif case['operation']=='match':
                refinement=read(case['refinement']);result=matching.match_architecture_refinement(refinement,read(case['behavior']),
                    circuit=read(case['circuit']) if case['circuit'] else None,max_states=case['max_states'],max_instances=case['max_instances'])
                actual=match_document(result);expected=case['expected']
                require([fingerprint(matching.instantiate_architecture_refinement(refinement,item).to_dict()) for item in result.instances]==case['instantiated_fingerprints'],'Instantiated authority drift')
            elif case['operation']=='compile':actual=producer.compile_payload_architecture(read(case['request'])).to_dict();expected=resolve(index,documents,case['build'])
            else:
                value=producer.export_payload_architecture(read(case['build']),expected_request=read(case['request']))
                require(fingerprint(value.to_dict())==case['expected_fingerprint'] and value.fasta==case['fasta'],'Complete export drift');continue
            require(canonical(actual)==canonical(expected),'Complete producer drift: '+case['id'])
    return index['inventory_fingerprint']

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argv);index,documents=build_corpus();check_corpus(index,documents)
    if args.write:
        DOCUMENTS.mkdir(parents=True,exist_ok=True)
        for path in DOCUMENTS.glob('*.json'):
            if path.stem not in documents:path.unlink()
        for item in index['documents']:(DOCUMENTS/(item['id']+'.json')).write_bytes(stored_encoded(documents[item['id']],item['format']))
        CORPUS.write_bytes(encoded(index))
    else:
        require(load()==(index,documents),'Retained producer corpus differs from complete fresh oracle')
    print(json.dumps(dict(fingerprint=index['inventory_fingerprint'],coverage=index['coverage']),sort_keys=True),flush=True)
if __name__=='__main__':main()
