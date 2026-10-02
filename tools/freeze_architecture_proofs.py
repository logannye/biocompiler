"""Retain independent controls/deployment theorem expectations, never candidate acceptance.

Existing functional-control assertions are executed while retaining their full
original source, explicit bindings and exact theorem results. Source locations
are standardized before publication for Python-version/host reproducibility.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import biocompiler as bc
from biocompiler.compiler.request import BuildRequest
from biocompiler.ir.implementation_requirements import source_request_from_dict
from biocompiler.ir.serialization import fingerprint
from biocompiler.ir.intent import thaw_json
from biocompiler.verification.architecture_controls import prove_extended_control, extended_control_targets
from biocompiler.verification.architecture_deployment import check_deployment_requirements
from biocompiler.verification.payload_architecture import _functional_control_proof
from tools.freeze_human_wrappers import standardized
from tests import test_architecture_functional_controls as legacy
from tests.test_architecture_deployment import timed_request

SCHEMA = 'biocompiler.architecture_proofs_conformance.v1'
PATHS = {kind:ROOT/'tests/conformance'/('architecture-'+kind+'-check-v1.json') for kind in ('controls','deployment')}

def encoded(value): return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
def inventory(value): return fingerprint({key:value[key] for key in ('cases','coverage','native_boundary')})
def source_nodes(source):
    build = source if isinstance(source,BuildRequest) else source.build_request
    return {node.id:node for node in build.intent.nodes}
def control_result(source,target,controllers,kind,bindings):
    nodes=source_nodes(source);control={'controlling_node_ids':controllers}
    reason=(_functional_control_proof(nodes,target,control,kind) if kind in ('activation','shutdown') else
            prove_extended_control(nodes,target,control,kind,parameter_bindings=bindings))
    return {'reason':reason,'targets':list(extended_control_targets(nodes,target,kind))}
def boundary():
    return {'claim_scope':'bounded_source_theorems_and_declared_interval_containment_only',
            'unproved_is_not_biological_infeasibility':True,
            'controls_max_work':10000000,'deployment_max_work':1000000,'controls_max_source_nodes':4096,'controls_max_controllers':4096,'controls_max_expression_depth':512,'aggregate_result_max_bytes':33554432,
            'whole_json_max_nodes':250000,'whole_json_max_bytes':16777216,
            'deployment_projection':'Used fields retain historical mapping semantics, duplicate window last-wins and arbitrary cached fields; native numeric inputs additionally require finite nonnegative seconds <=31536000.',
            'resource_exhaustion':'explicit native diagnostic; never a theorem result'}
def build_controls():
    documents={};cases=[];counts={};current=['']
    def retain(identity,source,target,controllers,kind,bindings=None,expected=None):
        source=source_request_from_dict(standardized(source.to_dict()))
        raw=source.to_dict();sha=fingerprint(raw);documents[sha]=raw
        result=control_result(source,target,controllers,kind,bindings)
        if expected is not None: assert result['reason']==expected,(identity,result,expected)
        cases.append({'id':identity,'source':sha,'target':target,'controlling_node_ids':list(controllers),'kind':kind,
                      'parameter_bindings':thaw_json(bindings),'expected':result})
    original=legacy.proof
    def capture(therapy,target,control,kind,*,nodes=None,bindings=None):
        program=therapy.freeze()
        if nodes is not None: program=replace(program,nodes=tuple(nodes.values()))
        source=BuildRequest.freeze(program)
        key=current[0];counts[key]=counts.get(key,0)+1
        retain(key+'/'+str(counts[key]),source,target.node_id,[control.node_id],kind,bindings)
        return cases[-1]['expected']['reason']
    legacy.proof=capture
    result=unittest.TestResult()
    try:
        suite=unittest.defaultTestLoader.loadTestsFromModule(legacy)
        for group in suite:
            for test in group:
                current[0]=test.id().split('.')[-2]+'.'+test.id().split('.')[-1]
                test.run(result)
    finally: legacy.proof=original
    assert result.wasSuccessful(),(result.errors,result.failures)
    # Independent literal gates and opaque cofactor witnesses, separately from
    # the extended-proof regression suite above.
    for gate in ('activation','shutdown'):
        for wrong in (False,True):
            therapy,cells,control,context=legacy.setup();condition=control.present()
            action=cells.rest();guard=condition if gate=='activation' else ~condition
            if wrong:guard=~guard
            cells.when(guard & context.present().held_for(bc.Duration(2))).do(action)
            retain('literal/'+gate+('/wrong' if wrong else '/valid'),BuildRequest.freeze(therapy.freeze()),action.node_id,[condition.node_id],gate,
                   expected=('deassertion_does_not_gate' if gate=='activation' else 'assertion_does_not_veto') if wrong else None)
    therapy,cells,control,context=legacy.setup();condition=control.present();action=cells.rest();cells.when(condition).do(action)
    source=BuildRequest.freeze(therapy.freeze())
    for label,refs,kind,reason in [('no_controller',[],'activity_control','requires_one_boolean_condition'),
        ('many_controllers',[condition.node_id,condition.node_id],'activity_control','requires_one_boolean_condition'),
        ('physical_only',[condition.node_id],'physical_separation','kind_not_implemented'),
        ('dependency_only',[condition.node_id],'dependency_disjointness','kind_not_implemented'),
        ('missing_target',[condition.node_id],'memory_reset','malformed_or_unsupported_control_source')]:
        retain('literal/'+label,source,'missing' if label=='missing_target' else action.node_id,refs,kind,expected=reason)
    from examples.architecture_control_designs import CASES,make_control_request
    for name in (*CASES,'production_independence'):
        for false in (False,True) if name in CASES else (False,):
            request=make_control_request(name,false_control=false)
            for control in request.library.refinements[0].controls:
                refinement=request.library.refinements[0];mapping=refinement.source_bindings
                controllers=[mapping[x] for x in control.controlling_node_ids]
                for index,target in enumerate(control.behavior_node_ids):
                    retain('pipeline/'+name+('/false' if false else '/valid')+'/'+control.id+'/'+str(index),request.source,mapping[target],controllers,control.kind,
                           request.source.resolved_bindings)
    # Exact 8-atom boundary, preserving independent present/high/low observations.
    for count in (8,9):
        therapy,cells,control,context=legacy.setup();c=control.present();guard=c
        for index in range(count-1):guard &= cells.environment.signal('atom'+str(index)).present()
        action=cells.rest();cells.when(guard).do(action)
        retain('literal/atoms_'+str(count),BuildRequest.freeze(therapy.freeze()),action.node_id,[c.node_id],'activity_control',
               expected='boolean_control_proof_bound' if count==9 else None)
    # Every reachable semantic rejection keeps its complete source and a literal
    # intended reason. Structural cycles are rejected by the Intent boundary.
    successful=[x for x in cases if x['expected']['reason'] is None]
    def base(kind,node_kind=None):
        return next(x for x in successful if x['kind']==kind and (node_kind is None or source_nodes(source_request_from_dict(documents[x['source']]))[x['target']].kind==node_kind))
    def mutant(label,case,predicate,change,reason,target=None):
        raw=deepcopy(documents[case['source']]);node=next(n for n in raw['intent']['nodes'] if predicate(n));change(node,raw)
        source=BuildRequest.from_dict(raw)
        retain('mutant/'+label,source,target or case['target'],case['controlling_node_ids'],case['kind'],case['parameter_bindings'],expected=reason)
    activity_case=base('activity_control');state_case=base('memory_reset','state');memory_case=base('memory_reset','memory');production_case=base('production_adjustment')
    mutant('non_boolean_control',activity_case,lambda n:n['id']==activity_case['controlling_node_ids'][0],lambda n,r:n.update(data_type=None),'non_boolean_control')
    mutant('unsupported_observation_band',activity_case,lambda n:n['kind']=='qualitative',lambda n,r:n['attributes'].update(band='opaque'),'unsupported_observation_band')
    mutant('unsupported_observation_atom',activity_case,lambda n:n['kind']=='signal',lambda n,r:n.update(kind='opaque'),'unsupported_observation_atom')
    mutant('non_boolean_guard',next(x for x in successful if x['kind']=='activity_control' and any(n['kind']=='and' for n in documents[x['source']]['intent']['nodes'])),lambda n:n['kind']=='and',lambda n,r:n.update(data_type=None),'non_boolean_guard')
    mutant('unsupported_state_policy',state_case,lambda n:n['kind']=='state',lambda n,r:n['attributes'].update(observation='future_state'),'unsupported_state_policy')
    mutant('invalid_state_domain',state_case,lambda n:n['kind']=='state',lambda n,r:n['attributes']['values'].append(n['attributes']['values'][0]),'invalid_state_domain')
    mutant('unsupported_state_assignment',state_case,lambda n:n['kind']=='action.state_set',lambda n,r:n['attributes'].update(idempotent=False),'unsupported_state_assignment')
    mutant('undeclared_state_predicate',state_case,lambda n:n['kind']=='state.is',lambda n,r:n['attributes'].update(value='absent'),'undeclared_state_predicate')
    mutant('persistent_or_event_state_writer',state_case,lambda n:n['kind']=='rule',lambda n,r:n['attributes'].update(trigger='event'),'persistent_or_event_state_writer')
    raw=deepcopy(documents[state_case['source']])
    for node in raw['intent']['nodes']:
        if node['kind']=='action.state_set':node['kind']='action.rest'
    retain('mutant/state_writer_missing',BuildRequest.from_dict(raw),state_case['target'],state_case['controlling_node_ids'],'memory_reset',expected='state_reset_writer_missing')
    retain('mutant/not_store',source_request_from_dict(documents[memory_case['source']]),memory_case['controlling_node_ids'][0],memory_case['controlling_node_ids'],'memory_reset',expected='target_not_memory_or_state')
    retain('mutant/not_production',source_request_from_dict(documents[activity_case['source']]),activity_case['target'],activity_case['controlling_node_ids'],'production_adjustment',expected='target_not_production_action')
    mutant('nonconstant_rate',production_case,lambda n:n['kind']=='literal',lambda n,r:n.update(kind='opaque'),'non_constant_rate_or_duration')
    def cross_role(n,raw):
        other=deepcopy(next(x for x in raw['intent']['nodes'] if x['kind']=='role'));other['id']='independent_role';raw['intent']['nodes'].append(other);n['role']=other['id']
    mutant('cross_role_control',activity_case,lambda n:n['id']==activity_case['controlling_node_ids'][0],cross_role,'cross_role_control_expression')
    for duration_value in (0,-1):
        therapy,cells,control,context=legacy.setup();memory=cells.memory('timer',set_when=context.present(),reset_when=control.present(),duration=bc.Duration(1))
        program=therapy.freeze();program=replace(program,nodes=tuple(replace(n,attributes={**n.attributes,'value':bc.Duration(duration_value).to_dict()}) if n.kind=='literal' else n for n in program.nodes))
        retain('literal/duration_'+str(duration_value),BuildRequest.freeze(program),memory.node_id,[control.node_id],'memory_reset',expected='unsupported_memory_duration')
    therapy,cells,control,context=legacy.setup();condition=control.present();orphan=cells.rest();cells.when(condition).do(orphan)
    program=therapy.freeze();rule_ids={n.id for n in program.nodes if n.kind=='rule'};program=replace(program,nodes=tuple(n for n in program.nodes if n.id not in rule_ids),roots=tuple(x for x in program.roots if x not in rule_ids))
    retain('literal/uninstalled_action',BuildRequest.freeze(program),orphan.node_id,[condition.node_id],'activity_control',expected='target_not_installed_ongoing_action')
    for op in ('add','subtract','negate','divide','divide_zero','overflow'):
        therapy,cells,control,context=legacy.setup();condition=control.present()
        rate=therapy.parameter('rate',type=bc.ProductionRate,default=bc.ProductionRate(1e308 if op=='overflow' else 3))
        expression={'add':lambda:rate+bc.ProductionRate(2),'subtract':lambda:rate-bc.ProductionRate(1),
                    'negate':lambda:-(-rate),'divide':lambda:rate/2,'divide_zero':lambda:rate/therapy.parameter('zero',type=bc.Level,default=bc.Level(1)),'overflow':lambda:rate*2}[op]()
        action=cells.secrete('numeric',rate=expression);cells.when(condition).do(action)
        source=BuildRequest.freeze(therapy.freeze(),parameters={'zero':bc.Level(0)} if op=='divide_zero' else {})
        retain('numeric/'+op,source,action.node_id,[condition.node_id],'production_adjustment',source.resolved_bindings if op=='divide_zero' else None,
               expected='undefined_constant' if op=='divide_zero' else 'non_finite_constant' if op=='overflow' else None)
    numeric_case=next(x for x in cases if x['id']=='numeric/add')
    mutant('extra_binary_operand',numeric_case,lambda n:n['kind']=='add',lambda n,r:n['inputs'].append(n['inputs'][0]),'malformed_or_unsupported_control_source')
    def duplicate_reset(n,raw):
        offset=n['attributes']['input_names'].index('set_when')
        n['attributes']['input_names'].append('reset_when');n['inputs'].append(n['inputs'][offset])
    mutant('duplicate_memory_name_last_wins',memory_case,lambda n:n['kind']=='memory',duplicate_reset,'assertion_does_not_reset')
    gate_case=next(x for x in cases if x['id']=='literal/activation/valid')
    raw=deepcopy(documents[gate_case['source']]);nodes=raw['intent']['nodes'];controller=gate_case['controlling_node_ids'][0]
    predicate=next(n for n in nodes if n['id']==controller);rule=next(n for n in nodes if n['kind']=='rule')
    inverse={**deepcopy(predicate),'id':'literal.inverse','kind':'not','inputs':[controller],'attributes':{}}
    bad={**deepcopy(predicate),'id':'literal.malformed','kind':'not','inputs':[],'attributes':{}}
    later={**deepcopy(rule),'id':'literal.later','inputs':[rule['inputs'][0],bad['id'],gate_case['target']]}
    rule['inputs'][1]=inverse['id'];nodes.extend([inverse,bad,later]);raw['intent']['roots'].append(later['id'])
    retain('lazy/first_gate_counterexample',BuildRequest.from_dict(raw),gate_case['target'],[controller],'activation',expected='deassertion_does_not_gate')
    raw=deepcopy(documents[gate_case['source']]);nodes=raw['intent']['nodes'];rule=next(n for n in nodes if n['kind']=='rule')
    never={**deepcopy(predicate),'id':'literal.never','kind':'and','inputs':[controller,inverse['id']],'attributes':{}}
    rule['inputs'][1]=bad['id'];nodes.extend([inverse,bad,never])
    retain('lazy/unrequired_guard_vacuity',BuildRequest.from_dict(raw),gate_case['target'],[never['id']],'shutdown',expected='vacuous_control_condition')
    for form in ('mapping','tuple'):
        raw=deepcopy(documents[state_case['source']])
        wrap=(lambda x:{'label':x}) if form=='mapping' else (lambda x:[x,True])
        for node in raw['intent']['nodes']:
            if node['kind']=='state':
                node['attributes']['values']=[wrap(x) for x in node['attributes']['values']];node['attributes']['initial']=wrap(node['attributes']['initial'])
            elif node['kind'] in ('state.is','action.state_set'):node['attributes']['value']=wrap(node['attributes']['value'])
        retain('state_values/'+form,BuildRequest.from_dict(raw),state_case['target'],state_case['controlling_node_ids'],'memory_reset',
               expected='malformed_or_unsupported_control_source' if form=='mapping' else None)
    raw=deepcopy(documents[state_case['source']]);store=next(n for n in raw['intent']['nodes'] if n['kind']=='state')
    store['attributes']['values']=[[True],[1]];store['attributes']['initial']=[True]
    retain('state_values/tuple_numeric_equality',BuildRequest.from_dict(raw),state_case['target'],state_case['controlling_node_ids'],'memory_reset',expected='invalid_state_domain')
    for band in ('high','low'):
        therapy,cells,control,context=legacy.setup();condition=getattr(control,band)();memory=cells.memory('banded',set_when=context.present(),reset_when=condition)
        retain('literal/control_band_'+band,BuildRequest.freeze(therapy.freeze()),memory.node_id,[condition.node_id],'memory_reset')
    corpus={'schema_version':SCHEMA,'kind':'controls','documents':documents,'cases':cases,
            'coverage':{'legacy_assertion_tests':result.testsRun,'theorem_kinds':sorted({x['kind'] for x in cases}),
                'reasons':sorted({x['expected']['reason'] for x in cases if x['expected']['reason'] is not None}),
                'source_authority':'Complete original BuildRequest; independent explicit binding mode retained.',
                'extended_regression_cases':sum(counts.values())},'native_boundary':boundary()}
    corpus['inventory_sha256']=inventory(corpus);return corpus

def ratio(value):
    value=Fraction(str(value));return {'numerator':value.numerator,'denominator':value.denominator}
def deployment_witnesses(request,inv):
    witnesses=[];groups={x.id:x for x in request.constraints.delivery_groups};windows={x['placement_id']:x for x in inv['availability']}
    for req in request.constraints.deployment_requirements:
        if req.delivery_group_id not in groups:continue
        for p in inv['placements']:
            if p['delivery_group']!=req.delivery_group_id or p['recipient_role']!=req.recipient_role:continue
            w=windows.get(p['id'])
            if w is None:continue
            def plus(a,b):
                v=Fraction(str(w[a]))+Fraction(str(w[b]));return {'numerator':v.numerator,'denominator':v.denominator}
            witnesses.append({'requirement_id':req.id,'placement_id':p['id'],'latest_onset':ratio(w['onset_max_seconds']),
                'earliest_end':plus('onset_min_seconds','duration_min_seconds'),'latest_end':plus('onset_max_seconds','duration_max_seconds'),
                'required_from':ratio(req.required_from_seconds),'required_until':ratio(req.required_until_seconds),
                'unavailable_after':None if req.unavailable_after_seconds is None else ratio(req.unavailable_after_seconds)})
    return witnesses

def build_deployment():
    documents={};cases=[]
    def retain(identity,request,inv,literal=None):
        request=bc.PayloadArchitectureRequest.from_dict(standardized(request.to_dict()))
        raw=request.to_dict();sha=fingerprint(raw);documents[sha]=raw
        inv=deepcopy(inv);si=fingerprint(inv);documents[si]=inv
        expected={'failures':check_deployment_requirements(request,inv),'witnesses':deployment_witnesses(request,inv)}
        if literal is not None:assert expected['failures']==literal,(identity,expected['failures'],literal)
        cases.append({'id':identity,'request':sha,'inventory':si,'expected':expected})
    request=timed_request();refinement=request.library.refinements[0]
    inv={k:[x.to_dict() for x in getattr(refinement,k)] for k in ('placements','availability')}
    req=request.constraints.deployment_requirements[0]
    retain('literal/exact_integer_boundaries',request,inv,[])
    def changed_req(**kw):return replace(request,constraints=replace(request.constraints,deployment_requirements=(replace(req,**kw),)))
    for label,kw in [('late_onset',{'required_from_seconds':3}),('short_overlap',{'required_until_seconds':13}),
        ('late_unavailability',{'unavailable_after_seconds':15}),('missing_group',{'delivery_group_id':'absent'}),
        ('wrong_recipient',{'recipient_role':'absent'}),('abstract_compartment',{'compartment':'abstract'}),
        ('unknown_compartment',{'compartment':'not_supplied'}),('no_unavailability',{'unavailable_after_seconds':None})]:retain(label,changed_req(**kw),inv)
    groups=tuple(replace(x,mode='independent',same_recipient=False) for x in request.constraints.delivery_groups)
    independent=replace(request,constraints=replace(request.constraints,delivery_groups=groups))
    retain('independent_recipients',independent,inv)
    retain('same_recipient_not_required',replace(independent,constraints=replace(independent.constraints,deployment_requirements=(replace(req,require_same_recipient=False),))),inv,[])
    for label,field,value in [('destination','compartment','nucleus'),('different_group','delivery_group','unused'),('different_recipient','recipient_role','unused')]:
        edited=deepcopy(inv);edited['placements'][0][field]=value;retain(label,request,edited)
    for label,edit in [('missing_helper_window',lambda x:x['availability'].pop(0)),('no_windows',lambda x:x.update(availability=[])),
                      ('no_members',lambda x:x.update(placements=[])),('wrong_clock',lambda x:x['availability'][0].update(clock='behavior_start')),
                      ('cached_lie',lambda x:x['availability'][0].update(guaranteed_until_seconds=999999))]:
        edited=deepcopy(inv);edit(edited);retain(label,request,edited)
    for onset,duration,until,label in [(0.1,0.2,0.3,'decimal_exact'),(0.1,0.2,0.30000000000000004,'decimal_real_gap'),
                                      (0.2,0.1,0.3,'decimal_permuted'),(1e-7,2e-7,3e-7,'exponent_exact'),(-0.0,0.3,0.3,'signed_zero')]:
        changed=changed_req(required_from_seconds=onset,required_until_seconds=until,unavailable_after_seconds=until)
        edited=deepcopy(inv)
        for w in edited['availability']:w.update(onset_min_seconds=onset,onset_max_seconds=onset,duration_min_seconds=duration,duration_max_seconds=duration)
        retain(label,changed,edited,[] if label!='decimal_real_gap' else None)
    edited=deepcopy(inv);edited['availability'][0]['onset_max_seconds']=0
    retain('historical_reversed_window_projection',request,edited)
    duplicate=deepcopy(inv);last=deepcopy(duplicate['availability'][0]);last['duration_min_seconds']=9
    duplicate['availability'].append(last);retain('duplicate_window_last_wins',request,duplicate)
    duplicate=deepcopy(inv);duplicate['placements'].append(deepcopy(duplicate['placements'][0]));retain('duplicate_placement_keeps_multiplicity',request,duplicate)
    for variant in ('base','parameter-default','parameter-override'):
        raw=json.loads((ROOT/'tests/conformance/case-b'/variant/'request.json').read_bytes())
        retained=bc.PayloadArchitectureRequest.from_dict(raw);retain('case_b/'+variant,retained,{'placements':[],'availability':[]},[])
    corpus={'schema_version':SCHEMA,'kind':'deployment','documents':documents,'cases':cases,
        'coverage':{'exact_fraction_str':True,'full_helper_inventory':True,'source_preserving_mutants':True,
        'legacy_failure_keys':sorted({x.split(':')[0] for item in cases for x in item['expected']['failures']})},'native_boundary':boundary()}
    corpus['inventory_sha256']=inventory(corpus);return corpus

def verify(corpus):
    assert corpus['schema_version']==SCHEMA and inventory(corpus)==corpus['inventory_sha256']
    docs=corpus['documents'];used=set();ids=set()
    for sha,doc in docs.items():assert fingerprint(doc)==sha
    for case in corpus['cases']:
        assert case['id'] not in ids;ids.add(case['id'])
        if corpus['kind']=='controls':
            used.add(case['source']);source=source_request_from_dict(docs[case['source']])
            actual=control_result(source,case['target'],case['controlling_node_ids'],case['kind'],case['parameter_bindings'])
        else:
            used.update((case['request'],case['inventory']));request=bc.PayloadArchitectureRequest.from_dict(docs[case['request']]);inv=docs[case['inventory']]
            actual={'failures':check_deployment_requirements(request,inv),'witnesses':deployment_witnesses(request,inv)}
        assert actual==case['expected'],case['id']
    assert used==set(docs)
    def count(x,depth=0):
        assert depth<=128
        return 1+(sum(1+count(v,depth+1) for v in x.values()) if isinstance(x,dict) else sum(count(v,depth+1) for v in x) if isinstance(x,list) else 0)
    assert count(corpus)<=250000 and len(encoded(corpus))<=16777216

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true');parser.add_argument('--check',action='store_true');args=parser.parse_args()
    for kind,build in [('controls',build_controls),('deployment',build_deployment)]:
        corpus=build();verify(corpus);raw=encoded(corpus)
        if args.write:PATHS[kind].write_bytes(raw)
        if args.check:assert PATHS[kind].read_bytes()==raw,kind+' retained bytes differ'
        print(json.dumps({'kind':kind,'cases':len(corpus['cases']),'documents':len(corpus['documents']),'bytes':len(raw),'inventory':corpus['inventory_sha256']}))
if __name__=='__main__':main()
