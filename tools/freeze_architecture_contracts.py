#!/usr/bin/env python3
"""Freeze all architecture leaf declarations without running an architecture checker."""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from biocompiler.errors import SerializationError
from biocompiler.ir.payload_architecture import (ArchitectureBinding, ArchitectureConnection, ArchitecturePlacement,
    ArchitectureControl, ControlRequirement, ArchitectureHelper, ArchitectureChannel, ArchitectureOutputBinding,
    RecipientDeliveryGroup, RNAArchitectureConstraints, ArchitectureMatchPolicy, ArchitectureRefinementInstance)
from biocompiler.ir.architecture_deployment import RNADeploymentRequirement

SCHEMA = 'biocompiler.architecture_contracts_conformance.v1'
CORPUS = ROOT / 'tests/conformance/architecture-contracts-v1.json'
KINDS = dict(binding=ArchitectureBinding, connection=ArchitectureConnection, placement=ArchitecturePlacement,
    control=ArchitectureControl, control_requirement=ControlRequirement, helper=ArchitectureHelper,
    channel=ArchitectureChannel, output_binding=ArchitectureOutputBinding, delivery_group=RecipientDeliveryGroup,
    constraints=RNAArchitectureConstraints, match_policy=ArchitectureMatchPolicy, instance=ArchitectureRefinementInstance)
CONTROL_KINDS = ('activation', 'production_adjustment', 'activity_control', 'memory_reset', 'shutdown', 'physical_separation', 'dependency_disjointness')
CENSUS = (88, 345, 4)
CASE_IDS_SHA256 = "96f988d6d2fe3d088d6a0301d6928b671c269bd47e399195475fc68418096b8e"
REJECTIONS_SHA256 = "cf9b3ccf61a6084aeb68c1f0ac2f68d76f3cff82a070d86a552c89489e3c010b"
LITERALS_SHA256 = "32ed4c6ba038b8c2aebc603d2659c3ea0cee5ca5d3a39e0ac6da4d88b9d116a5"

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
def fingerprint(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()
def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
def require(condition, message):
    if not condition: raise AssertionError(message)
def signature(corpus):
    identities = sorted(item['id'] for item in corpus['records'] + corpus['rejections'])
    rejected = sorted([item['id'], item['kind'], item['expected_code']] for item in corpus['rejections'])
    return fingerprint(identities), fingerprint(rejected), fingerprint(corpus['literal_expectations'])
def coverage(corpus):
    return dict(positive_count=len(corpus['records']), rejection_count=len(corpus['rejections']),
                independent_literal_count=len(corpus['literal_expectations']), record_kinds=sorted({x['kind'] for x in corpus['records']}))

def build_corpus():
    records, rejections, literals = [], [], []
    def retain(identity, kind, value, changes=None):
        raw = deepcopy(value.to_dict() if hasattr(value, 'to_dict') else value)
        if changes: raw.update(changes)
        parsed = KINDS[kind].from_dict(raw)
        records.append(dict(id=identity, kind=kind, input=raw, normalized=parsed.to_dict(), fingerprint=parsed.fingerprint))
        return raw
    def reject(identity, kind, raw, changes=None, *, remove=None, code='invalid_architecture_contract'):
        raw = deepcopy(raw)
        if changes: raw.update(changes)
        if remove is not None: del raw[remove]
        try: KINDS[kind].from_dict(raw)
        except SerializationError as error:
            rejections.append(dict(id=identity, kind=kind, input=raw, expected_code=code, python_error=str(error)))
        else: raise AssertionError('Accepted intended rejection ' + identity)
    base = {}
    base['binding'] = ArchitectureBinding('binding', ('node',), ('component',), ('template',), ('placement',))
    base['connection'] = ArchitectureConnection('connection', 'producer', 'out', 'consumer', 'in')
    base['placement'] = ArchitecturePlacement('placement', 'template', 'member', 'recipient', 'cytoplasm', 'delivery')
    base['control'] = ArchitectureControl('control', 'activation', ('action',), (), ('component',), 'physical-domain', ('supplied',))
    base['control_requirement'] = ControlRequirement('requirement', 'shutdown', ('action',), 'independent')
    base['helper'] = ArchitectureHelper('helper', 'capability', ('a', 'b'), 'recipient', 'cytoplasm', 'host', 'after_trigger', 'exclusive', 1, ('supplied',), depends_on=('helper',))
    base['channel'] = ArchitectureChannel('channel', 'source-channel', 'sender', 'receiver', 'send', 'receive', 0, None, 'unknown', 'single_sender', {'nested': [True, None, {'numeric': 1.0, 'negative_zero': -0.0}]}, ('supplied',))
    retained = json.loads((ROOT / 'tests/conformance/case-b/base/request.json').read_bytes())
    refinement = retained['library']['refinements'][0]
    base['output_binding'] = ArchitectureOutputBinding.from_dict(refinement['output_contracts'][0])
    base['delivery_group'] = RecipientDeliveryGroup('delivery', ('recipient',), 'independent', False, ('supplied',))
    base['constraints'] = RNAArchitectureConstraints()
    base['match_policy'] = ArchitectureMatchPolicy()
    base['instance'] = ArchitectureRefinementInstance('instance', 'refinement', {'z': 'b', 'a': 'c'})
    raw = {kind: retain('base/' + kind, kind, value) for kind, value in base.items()}
    for name, value in [('binding',refinement['bindings'][0]),('placement',refinement['placements'][0]),
                        ('control',refinement['controls'][1]),('output_binding',refinement['output_contracts'][0]),
                        ('delivery_group',retained['constraints']['delivery_groups'][0]),('constraints',retained['constraints'])]:
        retain('retained_case_b/' + name, name, value)
    # Independent complete expected records do not use to_dict() for their expected side.
    for identity, kind, expected in [
        ('literal/connection','connection',{'schema_version':'biocompiler.architecture_connection.v0.1','id':'c','producer_component_id':'same','producer_port_id':'port','consumer_component_id':'same','consumer_port_id':'port'}),
        ('literal/placement','placement',{'schema_version':'biocompiler.architecture_placement.v0.1','id':'p','template_id':'t','member_id':'m','recipient_role':'r','compartment':'abstract','delivery_group':'g'}),
        ('literal/policy','match_policy',{'schema_version':'biocompiler.architecture_match_policy.v0.1','mode':'exact_semantic_subgraph'}),
        ('literal/group','delivery_group',{'schema_version':'biocompiler.recipient_delivery_group.v0.1','id':'g','recipient_roles':['a','z'],'mode':'independent','same_recipient':False,'assumptions':['a','z'],'exact_count':0,'max_count':0,'max_total_bases':0}),
    ]:
        supplied=deepcopy(expected)
        if kind=='delivery_group': supplied.update(recipient_roles=['z','a'],assumptions=['z','a'])
        retain(identity,kind,supplied)
        literals.append(dict(id=identity,normalized=expected))
    for kind in CONTROL_KINDS:
        retain('control_kind/' + kind,'control',replace(base['control'],kind=kind))
        retain('control_requirement_kind/' + kind,'control_requirement',replace(base['control_requirement'],kind=kind,relation='shared'))
    for availability in ('same_rna','other_rna','host','external'):
        for initialization in ('available_at_start','after_expression','after_trigger'):
            retain('helper/' + availability + '/' + initialization,'helper',replace(base['helper'],availability=availability,
                initialization=initialization,sharing='shared',placement_id='placement' if availability.endswith('rna') else None,
                provider_component_id='provider'))
    retain('helper/capacity_max','helper',replace(base['helper'],capacity=4096))
    retain('helper/cycle_and_insufficient_exclusive_capacity_retained','helper',base['helper'])
    for failure in ('retain_last','clear','unknown'):
        for aggregation in ('single_sender','sum','max'):
            retain('channel/' + failure + '/' + aggregation,'channel',replace(base['channel'],failure_mode=failure,aggregation=aggregation,latency_seconds=-0.0,persistence_seconds=0))
    for name,value in [('null',None),('boolean',False),('integer',0),('float',0.0),('string','declared'),('array',[1,2]),('max_time',True)]:
        retain('channel/initial_' + name,'channel',replace(base['channel'],initial_value=value,
            latency_seconds=31536000 if name=='max_time' else 0, persistence_seconds=31536000 if name=='max_time' else None))
    for product,quantity in [('protein_expression','translation_rate'),('mature_protein_quantity','protein_abundance'),
                             ('reporter_fluorescence','fluorescence'),('biological_activity','downstream_activity'),('rna_product','rna_abundance')]:
        changed=deepcopy(raw['output_binding']); changed['product']['kind']=product; changed['product']['observation']['quantity']=quantity
        retain('output/product_' + product,'output_binding',changed)
    for mode in ('production_control','abundance_control','activity_control','readout'):
        changed=deepcopy(raw['output_binding']);changed['lifecycle']['mode']=mode
        retain('output/lifecycle_' + mode + '_contextual_pairing_deferred','output_binding',changed)
    window={'schema_version':'biocompiler.observation_window.v0.1','reference':'declared_start','start':0,'end':1.0,'unit':'s','aggregation':'mean'}
    changed=deepcopy(raw['output_binding']);changed['lifecycle'].update(onset=window,cessation=window,clearance=window)
    retain('output/complete_lifecycle_windows','output_binding',changed)
    for mode in ('co_delivered','independent'):
        for same in (False,True):
            retain('group/' + mode + '/' + str(same).lower(),'delivery_group',replace(base['delivery_group'],mode=mode,same_recipient=same,exact_count=4096,max_count=4096,max_total_bases=1_000_000))
    retain('constraints/zero_complete','constraints',RNAArchitectureConstraints(exact_count=0,max_count=0,max_member_bases=0,max_total_bases=0,require_complete=True,max_combinations=1,max_match_states=1,max_match_instances=1))
    retain('constraints/max_limits','constraints',RNAArchitectureConstraints(exact_count=4096,max_count=4096,max_member_bases=1_000_000,max_total_bases=1_000_000,max_combinations=4096,max_match_states=1_000_000,max_match_instances=256))
    deployment=RNADeploymentRequirement('deployment','missing-group','recipient','abstract',0,1,('supplied',),require_same_recipient=False)
    full=RNAArchitectureConstraints(delivery_groups=(replace(base['delivery_group'],id='z'),replace(base['delivery_group'],id='a')),
        control_requirements=(replace(base['control_requirement'],id='z'),replace(base['control_requirement'],id='a')),
        deployment_requirements=(replace(deployment,id='z'),replace(deployment,id='a')),preferred_refinement_ids=('z','a'))
    fullraw=full.to_dict()
    for key in ('delivery_groups','control_requirements','deployment_requirements','preferred_refinement_ids'):fullraw[key].reverse()
    retain('constraints/sorted_inventories_contextual_refs_deferred','constraints',fullraw)
    retain('binding/exact_name_inventory_limit','binding',raw['binding'],{'behavior_node_ids':['n'+str(i) for i in range(4096)]})
    retain('binding/unicode_byte_limit','binding',raw['binding'],{'id':'é'*2048})
    retain('control/exact_assumption_limit','control',raw['control'],{'assumptions':[str(i) for i in range(64)]})
    retain('constraints/exact_preference_limit','constraints',raw['constraints'],{'preferred_refinement_ids':[str(i) for i in range(256)]})
    retain('instance/exact_mapping_limit','instance',raw['instance'],{'source_bindings':{'k'+str(i):'v'+str(i) for i in range(4096)}})
    for kind,value in raw.items():
        for key in value: reject(kind+'/missing/'+key,kind,value,remove=key,code='missing_field')
        reject(kind+'/future_schema',kind,value,{'schema_version':'future'},code='unsupported_schema')
        reject(kind+'/unknown_field',kind,value,{'accepted':True},code='unknown_field')
        if 'id' in value:
            for label,text in [('blank',''),('trim',' x'),('control','x\ny'),('bytes','é'*2049)]:
                reject(kind+'/id_'+label,kind,value,{'id':text},code='invalid_molecular_text')
    name_fields={'binding':('behavior_node_ids','component_ids','template_ids','placement_ids'),
        'control':('behavior_node_ids','component_ids','controlling_node_ids'),'control_requirement':('behavior_node_ids','forbidden_shared_dependencies'),
        'helper':('consumer_component_ids','depends_on'),'output_binding':('action_ids',),'delivery_group':('recipient_roles',),'constraints':('preferred_refinement_ids',)}
    for kind,keys in name_fields.items():
        for key in keys:
            for label,val,code in [('duplicate',['a','a'],'invalid_architecture_contract'),('not_array',None,'invalid_type'),
                                   ('blank',[''],'invalid_molecular_text')]:
                reject(kind+'/'+key+'/'+label,kind,raw[kind],{key:val},code=code)
            maximum=256 if key=='preferred_refinement_ids' else 4096
            reject(kind+'/'+key+'/over_limit',kind,raw[kind],{key:[str(i) for i in range(maximum+1)]},code='molecular_resource_limit')
            if key not in ('controlling_node_ids','forbidden_shared_dependencies','depends_on','preferred_refinement_ids'):
                reject(kind+'/'+key+'/empty',kind,raw[kind],{key:[]})
    for kind in ('control','helper','channel','delivery_group'):
        for label,val,code in [('empty',[],'invalid_architecture_contract'),('duplicate',['a','a'],'invalid_architecture_contract'),
            ('over_limit',[str(i) for i in range(65)],'molecular_resource_limit'),('not_array',None,'invalid_type')]:
            reject(kind+'/assumptions/'+label,kind,raw[kind],{'assumptions':val},code=code)
    for kind,keys in {'control':['kind'],'control_requirement':['kind','relation'],'helper':['availability','initialization','sharing'],
                      'channel':['failure_mode','aggregation'],'delivery_group':['mode'],'match_policy':['mode']}.items():
        for key in keys:
            reject(kind+'/'+key+'/unsupported',kind,raw[kind],{key:'unsupported'})
            reject(kind+'/'+key+'/wrong_type',kind,raw[kind],{key:False},code='invalid_type')
    for availability in ('same_rna','other_rna','host','external'):
        reject('helper/placement/'+availability,'helper',raw['helper'],{'availability':availability,'placement_id':None if availability.endswith('rna') else 'placement'})
    for key in ('placement_id','provider_component_id'):
        reject('helper/'+key+'/blank','helper',raw['helper'],{key:''},code='invalid_molecular_text')
    for kind,key,minimum,maximum in [('helper','capacity',1,4096),('constraints','max_combinations',1,4096),('constraints','max_match_states',1,1_000_000),('constraints','max_match_instances',1,256)]:
        for label,val,code in [('below',minimum-1,'invalid_architecture_contract'),('above',maximum+1,'invalid_architecture_contract'),
                             ('bool',True,'invalid_type'),('float',1.0,'invalid_type'),('null',None,'invalid_type')]:
            reject(kind+'/'+key+'/'+label,kind,raw[kind],{key:val},code=code)
    for kind,keys in [('constraints',('exact_count','max_count','max_member_bases','max_total_bases')),('delivery_group',('exact_count','max_count','max_total_bases'))]:
        for key in keys:
            maximum=4096 if 'count' in key else 1_000_000
            for label,val,code in [('below',-1,'invalid_architecture_contract'),('above',maximum+1,'invalid_architecture_contract'),('bool',False,'invalid_type'),('float',0.0,'invalid_type')]:
                reject(kind+'/'+key+'/'+label,kind,raw[kind],{key:val},code=code)
        reject(kind+'/count_conflict',kind,raw[kind],{'exact_count':2,'max_count':1})
    for key in ('latency_seconds','persistence_seconds'):
        for label,val in [('negative',-1),('over_limit',31536001),('bool',False),('text','0')]:
            reject('channel/'+key+'/'+label,'channel',raw['channel'],{key:val},code='invalid_deployment_time')
    reject('channel/null_latency','channel',raw['channel'],{'latency_seconds':None},code='invalid_deployment_time')
    reject('channel/same_role','channel',raw['channel'],{'receiver_role':'sender'})
    reject('group/non_boolean','delivery_group',raw['delivery_group'],{'same_recipient':0},code='invalid_type')
    reject('constraints/non_boolean','constraints',raw['constraints'],{'require_complete':0},code='invalid_type')
    for key,example in [('delivery_groups',base['delivery_group'].to_dict()),('control_requirements',base['control_requirement'].to_dict()),('deployment_requirements',deployment.to_dict())]:
        reject('constraints/'+key+'/duplicate','constraints',raw['constraints'],{key:[example,example]})
        reject('constraints/'+key+'/over_limit','constraints',raw['constraints'],{key:[dict(example,id=str(i)) for i in range(257)]},code='molecular_resource_limit')
        reject('constraints/'+key+'/not_array','constraints',raw['constraints'],{key:None},code='invalid_type')
    for label,value,code in [('empty',{},'invalid_architecture_contract'),('noninjective',{'a':'x','b':'x'},'invalid_architecture_contract'),
        ('not_object',[],'invalid_type'),('blank_key',{'':'a'},'invalid_molecular_text'),('blank_value',{'a':''},'invalid_molecular_text'),
        ('over_limit',{str(i):str(i) for i in range(4097)},'molecular_resource_limit')]:
        reject('instance/mapping/'+label,'instance',raw['instance'],{'source_bindings':value},code=code)
    changed=deepcopy(raw['output_binding']);changed['product']['observation']['quantity']='rna_abundance'
    reject('output/product_quantity_mismatch','output_binding',changed,code='invalid_circuit_record')
    changed=deepcopy(raw['output_binding']);changed['lifecycle']['mode']='invented'
    reject('output/lifecycle_mode','output_binding',changed,code='invalid_circuit_record')
    corpus=dict(schema_version=SCHEMA,claim_scope='Complete local structural declarations only; no matching, feasibility, construction or fresh architecture acceptance.',
                records=records,rejections=rejections,literal_expectations=literals)
    corpus['coverage']=coverage(corpus)
    corpus['case_ids_sha256'],corpus['rejections_sha256'],corpus['literals_sha256']=signature(corpus)
    check_corpus(corpus)
    return corpus

def check_corpus(corpus):
    require(corpus['schema_version']==SCHEMA,'Wrong schema')
    require(corpus['coverage']==coverage(corpus),'Incorrect coverage')
    require(corpus['coverage']['record_kinds']==sorted(KINDS),'Missing record kinds')
    census=(len(corpus['records']),len(corpus['rejections']),len(corpus['literal_expectations']))
    require(census==CENSUS,'Truncated corpus')
    ids=[x['id'] for x in corpus['records']+corpus['rejections']]
    require(len(ids)==len(set(ids)),'Duplicate identities')
    signatures=signature(corpus)
    require(signatures==(corpus['case_ids_sha256'],corpus['rejections_sha256'],corpus['literals_sha256']),'Incorrect manifest')
    require(signatures==(CASE_IDS_SHA256,REJECTIONS_SHA256,LITERALS_SHA256),'Changed retained case/rejection/literal inventory')
    by_id={}
    for case in corpus['records']:
        value=KINDS[case['kind']].from_dict(case['input'])
        require(canonical(value.to_dict())==canonical(case['normalized']),'Changed complete normalized record: '+case['id'])
        require(value.fingerprint==case['fingerprint'],'Changed fingerprint: '+case['id'])
        by_id[case['id']]=value.to_dict()
    for case in corpus['rejections']:
        try: KINDS[case['kind']].from_dict(case['input'])
        except SerializationError as error: require(str(error)==case['python_error'],'Wrong rejection signature: '+case['id'])
        else: raise AssertionError('Accepted negative: '+case['id'])
    for item in corpus['literal_expectations']:
        require(canonical(by_id[item['id']])==canonical(item['normalized']),'Independent literal mismatch')
    pending=[(corpus,0)];count=0
    while pending:
        item,depth=pending.pop();count+=1
        require(count<=250_000 and depth<=128,'Whole corpus JSON budget exceeded')
        if isinstance(item,dict):pending.extend((v,depth+1) for pair in item.items() for v in pair)
        elif isinstance(item,list):pending.extend((v,depth+1) for v in item)
        elif isinstance(item,str):require(len(item.encode())<=4*1024*1024,'Corpus string budget exceeded')
    require(len(encoded(corpus))<=16*1024*1024,'Whole corpus byte budget exceeded')
    require(b'/Users/' not in encoded(corpus),'Machine-specific source coordinates retained')

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=CORPUS)
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--write',action='store_true');mode.add_argument('--check',action='store_true')
    args=parser.parse_args(argv);value=build_corpus();content=encoded(value)
    if args.write:args.output.write_bytes(content)
    else:require(args.output.read_bytes()==content,'Retained architecture corpus differs')
    print(json.dumps(dict(status='written' if args.write else 'checked',bytes=len(content),**value['coverage'],case_ids_sha256=value['case_ids_sha256'],rejections_sha256=value['rejections_sha256'],literals_sha256=value['literals_sha256']),sort_keys=True))
    return 0
if __name__=='__main__':raise SystemExit(main())
