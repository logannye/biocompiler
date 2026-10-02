"""Retain bounded complete source-transport authority and exact Python traces.

All original assertions execute. Transport is source-prefix replay under supplied
contracts, never candidate or biological evidence. Relative source locations are
established before any request/build identity is computed.
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
import subprocess
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
for directory in (str(ROOT),str(ROOT/'tests')):
    if directory not in sys.path:sys.path.insert(0,directory)
import biocompiler as bc
from biocompiler.ir.architecture_build import PayloadArchitectureBuild,PayloadArchitectureRequest
from biocompiler.ir.serialization import fingerprint,parse_json
from biocompiler.semantics.evaluator import InputFrame,SignalSample
from biocompiler.semantics.architecture_execution import evaluate_payload_architecture
from tools.freeze_architecture_check import difference,apply_edits,stored_encoded,encoded,bounds,canonical

CORPUS=ROOT/'tests/conformance/source-transport-v1.json'
DOCUMENTS=CORPUS.with_suffix('')
SCHEMA='biocompiler.source_transport_conformance.v1'
DELTA='biocompiler.test_document_delta.v1'
MAX_BYTES=16*1024*1024
CODE_MESSAGES=(
 ('fresh complete independent','source_transport_authority'),
 ('must have duration units','source_transport_seconds'),('integer number of canonical seconds','source_transport_seconds'),
 ('Step must be positive','source_transport_grid'),('max_samples','source_transport_samples'),
 ('10000 role evaluations','source_transport_roles'),('Unknown or duplicate external','source_transport_history'),
 ('bounded InputFrame','source_transport_history'),('start at zero','source_transport_history'),
 ('External observations must lie','source_transport_grid'),('every source role','source_transport_history'),
 ('Duplicate selected channel','source_transport_channel'),('selected channels','source_transport_failure'),
 ('Invalid channel failure','source_transport_failure'),('unique grid points','source_transport_failure'),
 ('Zero-delay','source_transport_latency'),('Channel persistence must be positive','source_transport_persistence'),
 ('qualitative observation encoding','source_transport_encoding'),('explicit numeric source emission','source_transport_emission'),
 ('agree on aggregation','source_transport_aggregation'),('single_sender','source_transport_aggregation'),
 ('Every source channel observation','source_transport_channel'),('cannot override','source_transport_override'),
 ('unknown channel failure','source_transport_failure'),('non-finite observation','source_transport_aggregation'),
 ('Multiple active emitter','source_transport_emission'),('Contact-scoped emitter','source_transport_emission'),
 ('finite canonical scalar','source_transport_emission'))
def require(value,message):
    if not value:raise AssertionError(message)
def error_code(error):
    text=str(error)
    for fragment,code in CODE_MESSAGES:
        if fragment in text:return code
    raise AssertionError('Unclassified transport error: '+type(error).__name__+': '+text)
def option(value):return value.to_dict() if hasattr(value,'to_dict') else value
def input_json(histories,until,step,max_samples=1000,failed_channels=None):
    return dict(histories={key:[frame.to_dict() for frame in frames] for key,frames in histories.items()},
      until=option(until),step=option(step),max_samples=max_samples,
      failed_channels={key:[option(v) for v in values] for key,values in (failed_channels or {}).items()})
def inventory(index):return fingerprint({k:v for k,v in index.items() if k!='inventory_fingerprint'})

def custom_program(name,variant):
    t=bc.Therapy(name)
    sender=t.engineer('sender',cell_type='human_T_cell');receiver=t.engineer('receiver',cell_type='human_T_cell')
    channel=t.channel('artificial_alert',scope='local',type=bc.Level)
    context=(sender.contact.marker('context') if variant=='contact' else sender.environment.signal('context')).present()
    values=(1e16,1,-1e16) if variant=='sum' else (1,1.0) if variant=='max' else (1,)
    for value in values:
        emitted=sender.emit(channel,value=value)
        if variant=='pulse':sender.when(context).do(emitted.for_(bc.Duration(2)))
        elif variant=='duplicate':
            sender.when(context).do(emitted);sender.when(context | ~context).do(emitted)
        else:sender.when(context).do(emitted)
    received=receiver.sense(channel)
    stop=receiver.environment.signal('shutdown').present()
    active=received.high() if variant=='qualitative' else received>0
    receiver.when(active & ~stop).do(receiver.secrete('artificial_alpha'))
    return t.freeze()

def build_corpus():
    require(os.environ.get('PYTHONHASHSEED')=='0','Use deterministic source hash seed0')
    examples=importlib.import_module('examples.payload_architectures')
    tests=importlib.import_module('test_architecture_execution')
    graph=importlib.import_module('biocompiler.frontend.graph');location=graph.SourceLocation
    def portable(file,line,function):
        path=Path(file)
        return location(path.resolve().relative_to(ROOT).as_posix() if path.is_absolute() else file,line,function)
    originals={};kinds={};cases=[];ledger=[];current=[''];counts=Counter();literal=[]
    def retain(kind,raw):
        bounds(raw);identity=fingerprint(raw)
        if identity in kinds:require(kinds[identity]==kind,'Kind identity collision')
        kinds[identity]=kind;originals[identity]=raw
        require(sum(len(encoded(v)) for v in originals.values())<=256*1024*1024,'Resolved campaign size bound')
        return identity
    def capture(identity,build,request,history,*,until=5,step=1,max_samples=1000,failed_channels=None,origin='independent_fixture'):
        raw_input=input_json(history,until,step,max_samples,failed_channels)
        entry=dict(id=identity,request=retain('request',request.to_dict()),build=retain('build',build.to_dict()),
                   input=retain('input',raw_input),origin=origin)
        try:
            result=evaluate_payload_architecture(build,request,history,until=until,step=step,
                max_samples=max_samples,failed_channels=failed_channels)
        except Exception as error:
            entry.update(expected=None,expected_code=error_code(error),python_error=str(error))
            cases.append(entry);return None,error
        entry.update(expected=retain('result',result.to_dict()),expected_code=None,python_error=None)
        cases.append(entry);return result,None
    def observed(build,request,history,**kwargs):
        number=counts[current[0]];counts[current[0]]+=1
        result,error=capture(current[0]+'/'+str(number),build,request,history,origin='original_assertion',**kwargs)
        if error is not None:raise error
        return result
    with patch.object(graph,'SourceLocation',portable):
        cls=tests.CoupledArchitectureExecutionTests
        with patch.object(tests,'evaluate_payload_architecture',observed):
            cls.setUpClass()
            for name in sorted(n for n in dir(cls) if n.startswith('test_')):
                current[0]='test_architecture_execution.CoupledArchitectureExecutionTests.'+name
                cls(name).debug();ledger.append(dict(method=current[0],retained_calls=counts[current[0]],status='source_assertions_executed'))
        request,build=cls.request,cls.build
        history=tests.histories(request)
        channel=build.plan.channels[0];receiver=channel['receiver_role'];sender=channel['sender_role'];channel_id=channel['id']
        def run(name,**kwargs):
            return capture('literal/'+name,kwargs.pop('build',build),kwargs.pop('request',request),kwargs.pop('history',history),**kwargs)
        result,error=run('baseline')
        require(error is None,'Baseline transport failed')
        literal.append(dict(case_id='literal/baseline',projection='receiver_values',receiver=channel['receiver_node_id'],expected=[0,1,1,1,0,0]))
        literal.append(dict(case_id='literal/baseline',projection='delivery_times',channel=channel_id,expected=[1,2,None,None,None,None]))
        run('horizon_zero',until=0,history={key:(frames[0],) for key,frames in history.items()})
        named={next(node.attributes['name'] for node in request.source.intent.nodes if node.id==key):frames for key,frames in history.items()}
        run('role_names',history=named)
        run('duplicate_alias',history={**history,'sender':history[sender]})
        run('unknown_role',history={**history,'missing':history[sender]})
        run('empty_history',history={**history,sender:()})
        run('late_start',history={**history,sender:(replace(history[sender][0],time=1),)})
        run('duplicate_time',history={**history,sender:(history[sender][0],history[sender][0])})
        run('beyond_horizon',history={**history,sender:(history[sender][0],replace(history[sender][1],time=6))})
        run('zero_step',step=0);run('negative_horizon',until=-1);run('boolean_step',step=True)
        run('float_grid',step=1.0,until=5.0);run('duration_minutes',step=bc.Duration(1/60,unit='min'))
        run('wrong_units',step=bc.Level(1));run('boolean_sample_limit',max_samples=True);run('zero_sample_limit',max_samples=0)
        run('excess_sample_limit',max_samples=1001);run('duplicate_failure',failed_channels={channel_id:(1,1)})
        run('failure_beyond_horizon',failed_channels={channel_id:(6,)})
        run('failure_unsorted',failed_channels={channel_id:(4,2)})
        contacts=dict(history);contacts[receiver]=(replace(history[receiver][0],contacts={'contact':{channel['receiver_node_id']:SignalSample(value=9)}}),)
        run('contact_override',history=contacts)
        source=request.source.to_dict();source['intent']['nodes'][0]['source']={'file':'changed.py','line':1,'function':'changed'}
        moved=type(request.source).from_dict(source)
        moved_request=replace(request,circuit=replace(request.circuit,profile=replace(request.circuit.profile,source_request=moved)))
        run('source_location_authority',request=moved_request)
        def changed_channel(name,**changes):
            refinement=request.library.refinements[0]
            altered=replace(refinement.channels[0],**changes)
            req=replace(request,library=replace(request.library,refinements=(replace(refinement,channels=(altered,)),)))
            candidate=bc.compile(req)
            require(candidate.status=='compiled' or name=='unknown_failure','Transport variant not compiled: '+name)
            return req,candidate
        for name,changes in (
            ('indefinite',dict(persistence_seconds=None)),('delayed',dict(latency_seconds=2)),
            ('sum',dict(aggregation='sum')),('max',dict(aggregation='max')),
            ('unknown_failure',dict(failure_mode='unknown')),('offgrid_latency',dict(latency_seconds=.5)),
            ('offgrid_persistence',dict(persistence_seconds=.5))):
            print('Transport declaration variant: '+name,flush=True)
            req,candidate=changed_channel(name,**changes)
            failed={channel_id:(2,)} if name=='unknown_failure' else None
            result,error=run(name,request=req,build=candidate,failed_channels=failed)
            if name=='indefinite':literal.append(dict(case_id='literal/'+name,projection='receiver_values',receiver=channel['receiver_node_id'],expected=[0,1,1,1,1,1]))
            if name=='delayed':literal.append(dict(case_id='literal/'+name,projection='receiver_values',receiver=channel['receiver_node_id'],expected=[0,0,1,1,1,0]))
            if name=='sum':literal.append(dict(case_id='literal/'+name,projection='receiver_values',receiver=channel['receiver_node_id'],expected=[0,1.0,1.0,1.0,0,0]))
        for variant in ('pulse','duplicate','contact','qualitative','sum','max'):
            print('Transport source variant: '+variant,flush=True)
            with patch.object(examples,'source_program',lambda case,product='artificial_alpha':custom_program('source_'+variant,variant)),\
                 patch.object(examples,'contract_program',lambda case:custom_program('supplier_'+variant,variant)):
                req=examples.make_architecture_request('D')
            refinement=req.library.refinements[0]
            channels=[]
            emitters=[node for node in refinement.behavior.nodes if node.kind==('action.pulse' if variant=='pulse' else 'action.emit')]
            for i,emitter in enumerate(emitters):
                channels.append(replace(refinement.channels[0],id='transport.'+str(i),sender_node_id=emitter.id,
                    aggregation=variant if variant in ('sum','max') else 'single_sender'))
            req=replace(req,library=replace(req.library,refinements=(replace(refinement,channels=tuple(channels)),)))
            candidate=bc.compile(req);require(candidate.status=='compiled' or variant=='duplicate','Custom transport variant failed: '+variant+' '+str(candidate.diagnostics))
            if variant=='contact':
                context=next(node for node in req.source.intent.nodes if node.kind=='signal' and node.attributes.get('observation')=='marker')
                stop=next(node for node in req.source.intent.nodes if node.kind=='signal' and node.attributes['name']=='shutdown')
                external={context.role:(InputFrame(0,contacts={'one':{context.id:SignalSample(present=True)}}),),
                          stop.role:(InputFrame(0,{stop.id:SignalSample(present=False)}),)}
            else:external=tests.histories(req)
            if variant=='pulse':
                sender=candidate.plan.channels[0]['sender_role']
                external[sender]=(external[sender][0],replace(external[sender][1],time=1))
            result,error=run('custom_'+variant,request=req,build=candidate,history=external)
            if variant=='sum':
                require(error is None,'Custom sum failed')
                receive=candidate.plan.channels[0]['receiver_node_id']
                literal.append(dict(case_id='literal/custom_sum',projection='receiver_values',receiver=receive,expected=[0,1.0,1.0,1.0,0,0]))
            if variant=='pulse':
                require(error is None,'Custom pulse failed')
                literal.append(dict(case_id='literal/custom_pulse',projection='receiver_values',receiver=candidate.plan.channels[0]['receiver_node_id'],expected=[0,1,1,1,0,0]))
    return pack(originals,kinds,cases,ledger,literal)

def pack(originals,kinds,cases,ledger,literal):
    stored={};descriptors=[];full={kind:[] for kind in set(kinds.values())}
    for identity in sorted(originals,key=lambda identity:(kinds[identity],identity)):
        raw=originals[identity];kind=kinds[identity];size=bounds(raw);best=None;best_size=size
        for base in full[kind]:
            delta=dict(schema_version=DELTA,base=base,edits=difference(originals[base],raw))
            delta_size=len(encoded(delta))
            if delta_size<best_size:
                try:bounds(delta)
                except AssertionError:continue
                best=(base,delta);best_size=delta_size
        if best is None or best_size>size*.72:
            value=raw;format_='full';base=None;full[kind].append(identity)
        else:
            base,value=best;format_='delta';require(canonical(apply_edits(originals[base],value['edits']))==canonical(raw),'Delta altered authority')
        stored[identity]=value
        descriptors.append(dict(id=identity,kind=kind,format=format_,base=base,stored_fingerprint=fingerprint(value),
            bytes=len(stored_encoded(value,format_)),resolved_bytes=size))
    index=dict(schema_version=SCHEMA,delta_schema=DELTA,claim_scope='source_prefix_execution_under_declared_contracts_only',
        documents=descriptors,cases=cases,literal_assertions=literal,coverage=dict(methods=ledger,cases=len(cases),
        positive=sum(c['expected'] is not None for c in cases),negative=sum(c['expected'] is None for c in cases),
        documents=len(descriptors),original_calls=sum(m['retained_calls'] for m in ledger),
        rejection_codes=sorted({c['expected_code'] for c in cases if c['expected_code']})),
        compatibility=dict(native_data='biocompiler.native_source_transport_data.v0.1',native_resources='biocompiler.source_transport.resources.v1',
            max_work=50000000,max_replayed_frames=100000,max_replayed_trace_items=1000000,max_queued_deliveries=100000,
            max_output_bytes=33*1024*1024,max_output_nodes=250000,
            earlier_fresh_authority_rejections=['unknown_failure','custom_duplicate'],
            scope='Cumulative native resource failures are explicit exceptions with no partial result; full Python traces retain original semantics.'))
    index['inventory_fingerprint']=inventory(index)
    require(len(encoded(index))+sum(x['bytes'] for x in descriptors)<=MAX_BYTES,'Stored transport campaign exceeds16MiB')
    return index,stored

def load():
    index=parse_json(CORPUS.read_text());docs={}
    for desc in index['documents']:
        path=DOCUMENTS/(desc['id']+'.json');require(path.stat().st_size==desc['bytes'],'Stored size drift')
        docs[desc['id']]=parse_json(path.read_text())
    return index,docs

def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if os.environ.get('PYTHONHASHSEED')!='0':raise SystemExit(subprocess.call([sys.executable,str(Path(__file__).resolve()),*argv],env={**os.environ,'PYTHONHASHSEED':'0'}))
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');parser.add_argument('--check',action='store_true');args=parser.parse_args(argv)
    index,docs=build_corpus();metadata={x['id']:x for x in index['documents']}
    if args.write:
        DOCUMENTS.mkdir(exist_ok=True)
        for path in DOCUMENTS.glob('*.json'):
            if path.stem not in docs:path.unlink()
        for identity,value in docs.items():(DOCUMENTS/(identity+'.json')).write_bytes(stored_encoded(value,metadata[identity]['format']))
        CORPUS.write_bytes(encoded(index))
    else:
        require(CORPUS.read_bytes()==encoded(index),'Source transport index drift')
        require({p.stem for p in DOCUMENTS.glob('*.json')}==set(docs),'Source transport document inventory drift')
        for identity,value in docs.items():require((DOCUMENTS/(identity+'.json')).read_bytes()==stored_encoded(value,metadata[identity]['format']),'Stored transport authority drift')
    print(json.dumps(index['coverage']|{'inventory':index['inventory_fingerprint']},sort_keys=True))
if __name__=='__main__':main()
