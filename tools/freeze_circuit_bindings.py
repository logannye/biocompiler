"""Retain legacy supplementary circuit correspondence, not architecture acceptance.

Installed Python is the baseline oracle. Complete portable source wrappers and
requirements are retained independently from supplied bindings. Native bounded
stack/work behavior is an explicit compatibility boundary, never a semantic PASS.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import biocompiler as bc
from biocompiler.errors import SerializationError
from biocompiler.ir.executable_payload import PayloadCircuitBinding
from biocompiler.ir.implementation_requirements import source_request_from_dict
from biocompiler.ir.circuit_intent import CircuitRequirement, CircuitInputBinding, CircuitProviderRequirement
from biocompiler.ir.serialization import fingerprint
from biocompiler.verification.executable_payload import _check_circuit_bindings
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.freeze_human_wrappers import portable, profile, circuit
from examples.circuit_intent import observation
from examples.human_target import make_human_target
from examples.executable_payload import make_payload_request
CORPUS=ROOT/'tests/conformance/circuit-bindings-v1.json'
SCHEMA='biocompiler.circuit_bindings_conformance.v1'
LITERAL={'schema_version':'biocompiler.payload_circuit_binding.v0.1','requirement_id':'r','rule_id':'rule','action_id':'a','signals':{'z':'same','a':'same'}}

def encoded(raw): return (json.dumps(raw,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
def inventory(raw): return fingerprint({k:raw[k] for k in ('records','rejections','checks','literal_expectations','compatibility')})
def context(source,requirements,bindings): return SimpleNamespace(source=source,circuit=SimpleNamespace(requirements=tuple(requirements)),circuit_bindings=tuple(bindings))
def authored(count=2,kind='and',scope='environment',direct=False,parameter=False,override=False):
    therapy=bc.Therapy('binding_fixture')
    cell=therapy.engineer('recipient',cell_type='human_T_cell')
    signals=[getattr(cell,scope).signal('s'+str(i)) for i in range(count)]
    predicates=[x.present() for x in signals]
    guard=predicates[0]
    for predicate in predicates[1:]: guard=guard|predicate if kind=='or' else guard&predicate
    if kind=='not': guard=~guard
    if kind=='signature':
        decorated=bc.signature(lambda value:value,name='declared_boolean_wrapper')
        decorated._definition={'name':'declared_boolean_wrapper','module':'fixtures','qualname':'declared_boolean_wrapper'}
        guard=decorated(guard)
    if parameter:
        duration=therapy.parameter('dwell',type=bc.Duration,default=bc.Duration(2))
        guard=guard.held_for(duration)
    cell.when(guard).do(cell.secrete('artificial_product'))
    source=bc.BuildRequest.freeze(therapy.freeze(),target=make_human_target(),**({'parameters':{'dwell':bc.Duration(3)}} if override else {}))
    builder=bc.CircuitBuilder('supplementary',profile(source),role_id=cell.node_id)
    refs=predicates if direct else signals
    inputs=[builder.observe(observation('i'+str(i)),ref.node_id) for i,ref in enumerate(refs)]
    table=inputs[0]
    for operand in inputs[1:]: table=table|operand if kind=='or' else table&operand
    if kind=='not': table=~table
    rule=source.intent.find(kind='rule')[0]
    product=bc.CircuitProduct('artificial_product',bc.ProductKind.PROTEIN_EXPRESSION,
        observation('readout',bc.QuantityKind.TRANSLATION_RATE,bc.ObservationScope.EVALUATOR))
    builder.require('r',table,product,lifecycle=bc.CircuitLifecycle('production_control'),source=(rule.id,rule.inputs[2]))
    requirement=builder.freeze(requested_form='delivered_rna',fidelity_scope='complete_nominal',deployment_id='declared').requirements[0]
    binding=PayloadCircuitBinding('r',rule.id,rule.inputs[2],{'i'+str(i):ref.node_id for i,ref in enumerate(refs)})
    return portable(source),(requirement,),(binding,)

def portable_requirement(requirement):
    raw=requirement.to_dict()
    location=raw['source_location']
    if location is not None:
        location=dict(location)
        path=Path(location['file'])
        if path.is_absolute(): location['file']=path.resolve().relative_to(ROOT).as_posix()
        raw=dict(raw,source_location=location)
    return CircuitRequirement.from_dict(raw)

def build_corpus():
    documents,records,rejections,checks,literals={},[],[],[],[]
    def doc(raw):
        digest=fingerprint(raw);documents[digest]=deepcopy(raw);return digest
    def record(identity,raw,expected=None):
        value=PayloadCircuitBinding.from_dict(raw)
        records.append(dict(id=identity,document=doc(raw),normalized=doc(value.to_dict()),fingerprint=value.fingerprint))
        if expected is not None:
            assert value.to_dict()==expected;literals.append(dict(id=identity,expected=expected))
    def reject(identity,raw,code):
        try: PayloadCircuitBinding.from_dict(raw)
        except SerializationError: pass
        else: raise AssertionError('Accepted '+identity)
        rejections.append(dict(id=identity,document=doc(raw),expected_code=code))
    def check(identity,source,requirements,bindings,expected=None):
        source=portable(source)
        requirements=tuple(portable_requirement(x) for x in requirements)
        bindings=tuple(PayloadCircuitBinding.from_dict(x.to_dict()) for x in bindings)
        result=_check_circuit_bindings(context(source,requirements,bindings))
        if expected is not None: assert result==expected,(identity,result,expected)
        checks.append(dict(id=identity,source=doc(source.to_dict()),requirements=[doc(x.to_dict()) for x in requirements],
            bindings=[doc(x.to_dict()) for x in bindings],expected=result,source_fingerprint=source.fingerprint,
            source_artifact_fingerprint=fingerprint(source.to_dict())))
        if expected is not None: literals.append(dict(id=identity,diagnostics=expected))
    record('literal/duplicate_targets',LITERAL,LITERAL)
    record('empty_mapping',dict(LITERAL,signals={}))
    record('unicode_order',dict(LITERAL,signals={'𐀀':'second','\ue000':'first','é':'third'}))
    record('maximum_mapping',dict(LITERAL,signals={'s'+str(i):'n'+str(i) for i in range(256)}))
    record('maximum_text',dict(LITERAL,requirement_id='é'*2048))
    for key in LITERAL:
        changed=deepcopy(LITERAL);del changed[key];reject('missing/'+key,changed,'missing_field')
    reject('unknown_field',dict(LITERAL,extra=True),'unknown_field')
    reject('schema',dict(LITERAL,schema_version='future'),'unsupported_schema')
    for key in ('requirement_id','rule_id','action_id'):
        for label,value,code in (('empty','','invalid_molecular_text'),('leading',' x','invalid_molecular_text'),('trailing','x\u3000','invalid_molecular_text'),('control','x\nq','invalid_molecular_text'),('type',False,'invalid_type'),('large','é'*2049,'invalid_molecular_text')):
            reject(key+'/'+label,dict(LITERAL,**{key:value}),code)
    for label,value,code in (('array',[],'invalid_type'),('null',None,'invalid_type'),('count',{'s'+str(i):'x' for i in range(257)},'invalid_payload_circuit_binding'),('empty_key',{'':'x'},'invalid_molecular_text'),('empty_value',{'x':''},'invalid_molecular_text'),('bad_value',{'x':1},'invalid_type')):
        reject('signals/'+label,dict(LITERAL,signals=value),code)
    for count in (1,2,8):
        for kind in ('and','or','not','signature'):
            check('predicate/'+str(count)+'/'+kind,*authored(count,kind),expected=[])
    for scope in ('internal','environment','contact'):
        check('scope/'+scope,*authored(scope=scope),expected=[])
    check('mapping/qualitative_ids',*authored(direct=True),expected=[])
    for override in (False,True):
        check('parameter/'+('override' if override else 'default'),*authored(parameter=True,override=override),expected=['unsupported:circuit_temporal_or_input_refinement:r'])
    for kwargs in ({},{'guard':'or'},{'multi_output':True},{'temporal':True},{'memory':True},{'pulse':True}):
        request=make_payload_request(**kwargs)
        check('existing/'+('-'.join(str(k)+'='+str(v) for k,v in sorted(kwargs.items())) or 'ordinary'),request.source,request.circuit.requirements,request.circuit_bindings)
    source,requirements,bindings=authored();req=requirements[0];binding=bindings[0]
    aliases={node.id:'renamed_'+node.id for node in source.intent.nodes}
    renamed_intent=replace(source.intent,nodes=tuple(replace(node,id=aliases[node.id],inputs=tuple(aliases[x] for x in node.inputs),role=None if node.role is None else aliases[node.role]) for node in source.intent.nodes),roots=tuple(aliases[x] for x in source.intent.roots))
    renamed_req=replace(req,role_id=aliases[req.role_id],source_node_ids=tuple(aliases[x] for x in req.source_node_ids),input_bindings=tuple(replace(x,source_node_id=aliases[x.source_node_id]) for x in req.input_bindings))
    renamed_binding=replace(binding,rule_id=aliases[binding.rule_id],action_id=aliases[binding.action_id],signals={key:aliases[value] for key,value in binding.signals.items()})
    check('alpha_renamed',replace(source,intent=renamed_intent),(renamed_req,),(renamed_binding,),[])
    check('missing_binding',source,requirements,(),['unsupported:circuit_binding_missing:r'])
    for name,value in (('missing','unknown'),('wrong_kind',next(x.id for x in source.intent.nodes if x.kind=='signal'))):
        check('rule/'+name,source,requirements,(replace(binding,rule_id=value),),['fail:circuit_source_action:r'])
    check('action/not_installed',source,requirements,(replace(binding,action_id='unknown'),),['fail:circuit_source_action:r'])
    check('role',source,(replace(req,role_id=None),),bindings,['fail:circuit_source_role_or_lineage:r'])
    check('lineage',source,(replace(req,source_node_ids=tuple(x for x in req.source_node_ids if x!=binding.rule_id)),),bindings,['fail:circuit_source_role_or_lineage:r'])
    pairs=list(binding.signals.items())
    swapped=dict(zip((k for k,v in pairs),reversed([v for k,v in pairs])))
    check('mapping/swapped',source,requirements,(replace(binding,signals=swapped),),['fail:circuit_original_input_binding:r'])
    no_authored=replace(req,input_bindings=())
    check('mapping/no_authored',source,(no_authored,),bindings,[])
    for name,mapping,expected in (
        ('missing',{},['fail:circuit_input_inventory:r']),('duplicate',dict.fromkeys(binding.signals,pairs[0][1]),['fail:circuit_input_inventory:r']),
        ('unknown',dict(binding.signals,extra='unknown'),['fail:circuit_input_inventory:r']),
        ('unbound',dict(binding.signals,i0='unknown'),['fail:circuit_source_input_binding:r'])):
        check('mapping/'+name,source,(no_authored,),(replace(binding,signals=mapping),),expected)
    changed=replace(req,behavior=replace(req.behavior,output=replace(req.behavior.output,id='changed')))
    check('product',source,(changed,),bindings,['fail:circuit_source_product:r'])
    changed=replace(req,behavior=replace(req.behavior,response=replace(req.behavior.response,outputs=(True,)*4)))
    check('truth_table',source,(changed,),bindings,['fail:circuit_guard_contradiction:r'])
    for field in ('onset','cessation','clearance'):
        lifecycle=replace(req.behavior.lifecycle,**{field:bc.ObservationWindow('activation',0,0,'s','instant')})
        check('lifecycle/'+field,source,(replace(req,behavior=replace(req.behavior,lifecycle=lifecycle)),),bindings,['unsupported:circuit_lifecycle:r'])
    provider=CircuitProviderRequirement('declared_host',req.behavior.output.observation.entity,'host','cytoplasm','declared_colocation','declared')
    dependent=replace(req,behavior=replace(req.behavior,dependencies=(provider,)))
    check('provider',source,(dependent,),bindings,['unsupported:circuit_provider_mapping:r:declared_host'])
    check('ordered_obligations',source,(dependent,),(),['unsupported:circuit_provider_mapping:r:declared_host','unsupported:circuit_binding_missing:r'])
    nodes={x.id:x for x in source.intent.nodes};rule=nodes[binding.rule_id];guard=nodes[rule.inputs[1]];first=nodes[guard.inputs[0]]
    def source_nodes(changes,added=()): return replace(source,intent=replace(source.intent,nodes=tuple(changes.get(n.id,n) for n in source.intent.nodes)+tuple(added)))
    def guard_ref(ref,added=()): return source_nodes({rule.id:replace(rule,inputs=(rule.inputs[0],ref,*rule.inputs[2:]))},added)
    check('mapping/unused',guard_ref(first.id),(no_authored,),bindings,['fail:circuit_source_input_binding:r'])
    alias=replace(first,id='extra_band',attributes={'band':'absent'})
    ambiguous=replace(guard,inputs=(*guard.inputs,alias.id))
    check('mapping/ambiguous_band',source_nodes({guard.id:ambiguous},(alias,)),(no_authored,),bindings,['fail:circuit_source_input_binding:r'])
    temporal=replace(guard,id='future_temporal',kind='future.operation')
    for first_temporal in (False,True):
        bad=replace(first,id='unbound_predicate',inputs=(next(x.id for x in source.intent.nodes if x.kind=='role'),))
        mixed=replace(guard,inputs=(temporal.id,bad.id) if first_temporal else (bad.id,temporal.id))
        expected=['unsupported:circuit_temporal_or_input_refinement:r'] if first_temporal else ['fail:circuit_source_input_binding:r']
        check('eager/error_precedence/'+str(first_temporal),source_nodes({guard.id:mixed},(temporal,bad)),(no_authored,),bindings,expected)
    wrapper_corpus=json.loads((ROOT/'tests/conformance/human-wrappers-v1.json').read_bytes())
    for kind in ('behavior_request','deployment_request','acceptance_request'):
        raw=next(x['normalized'] for x in wrapper_corpus['records'] if x['id']=='base/'+kind)
        wrapped=source_request_from_dict(raw);supplement=circuit(wrapped)
        check('wrapper/'+kind,wrapped,supplement.requirements,(),['unsupported:circuit_binding_missing:supplementary'])
    for key in ('implementation_constraints','preferences'):
        changed=bc.BuildRequest.from_dict(dict(source.to_dict(),**{key:{'retained':True}}))
        check('scope/'+key,changed,requirements,bindings,[])
    result=dict(schema_version=SCHEMA,documents=documents,records=records,rejections=rejections,checks=checks,literal_expectations=literals,
        compatibility={'resource_profile':'biocompiler.circuit_binding_check.resources.v1','default_max_work':10000000,
            'max_output_bytes':4000000,'max_output_nodes':100000,
            'native_difference':'Explicit iterative evaluation and shared work exhaustion raise circuit_binding_resource_limit; cumulative diagnostic publication exhaustion raises circuit_binding_output_limit before retaining the next entry; never partial success. Diagnostic UTF-8 bytes also charge shared work. Python recursive traversal has no independent work or report bound.',
            'scope':'Boolean supplementary correspondence only. Full source wrappers, design parameters and constraints remain retained authority; this helper does not assess them or establish architecture acceptance.',
            'source_coordinates':'Normalized before retention via portable; complete and semantic source fingerprints are both bound.'})
    result['inventory_sha256']=inventory(result);return result

def check_corpus(corpus):
    assert corpus['schema_version']==SCHEMA and corpus['inventory_sha256']==inventory(corpus)
    for key,raw in corpus['documents'].items(): assert fingerprint(raw)==key
    for group in ('records','rejections','checks'): assert len({x['id'] for x in corpus[group]})==len(corpus[group])
    for case in corpus['records']:
        value=PayloadCircuitBinding.from_dict(corpus['documents'][case['document']]);assert value.to_dict()==corpus['documents'][case['normalized']] and value.fingerprint==case['fingerprint']
    for case in corpus['checks']:
        source=source_request_from_dict(corpus['documents'][case['source']])
        requirements=[CircuitRequirement.from_dict(corpus['documents'][key]) for key in case['requirements']]
        bindings=[PayloadCircuitBinding.from_dict(corpus['documents'][key]) for key in case['bindings']]
        assert _check_circuit_bindings(context(source,requirements,bindings))==case['expected'],case['id']
        assert source.fingerprint==case['source_fingerprint'] and fingerprint(source.to_dict())==case['source_artifact_fingerprint']

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');args=parser.parse_args()
    result=build_corpus();check_corpus(result);content=encoded(result)
    if args.write: CORPUS.write_bytes(content)
    else: assert CORPUS.read_bytes()==content,'Circuit binding corpus drift'
    print(json.dumps({key:len(result[key]) for key in ('records','rejections','checks','documents')}|{'bytes':len(content),'inventory':result['inventory_sha256']}))
if __name__=='__main__':main()
