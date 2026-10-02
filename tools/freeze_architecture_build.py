"""Freeze historical architecture build/assessment imports; no native execution.

A parsed PASS is deliberately retained as an untrusted historical record. Fresh
acceptance belongs to the separate checker campaign and full external authority.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
from pathlib import Path

from biocompiler.errors import SerializationError
from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.ir.architecture_build import (ArchitectureGap, RequirementRealization,
    PayloadArchitecturePlan, ArchitectureAlternative, PayloadArchitectureBuild,
    PayloadArchitectureExport)
from biocompiler.ir.serialization import fingerprint
from biocompiler.verification.payload_architecture import PayloadArchitectureVerification, CHECKER_VERSION, CLAIM_SCOPE

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / 'tests/conformance/architecture-build-v1.json'
SCHEMA = 'biocompiler.architecture_build_conformance.v1'
KINDS = {'construction_build':CircuitConstructionBuild, 'gap':ArchitectureGap,
    'realization':RequirementRealization, 'plan':PayloadArchitecturePlan,
    'alternative':ArchitectureAlternative, 'build':PayloadArchitectureBuild,
    'export':PayloadArchitectureExport, 'assessment':PayloadArchitectureVerification}

def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()

def changed(raw, edits):
    raw=deepcopy(raw)
    for edit in edits:
        obj=raw
        for key in edit['path'][:-1]: obj=obj[key]
        if edit.get('remove'): del obj[edit['path'][-1]]
        else: obj[edit['path'][-1]]=deepcopy(edit['value'])
    return raw

def inventory(corpus):
    return fingerprint({key:corpus[key] for key in ('schema_version','records','rejections','literal_expectations','coverage')})

def build_corpus():
    documents,records,rejections={},[],[]
    def doc(raw):
        identity=fingerprint(raw);documents[identity]=deepcopy(raw);return identity
    def keep(identity,kind,raw,edits=()):
        raw=raw.to_dict() if hasattr(raw,'to_dict') else raw
        value=KINDS[kind].from_dict(changed(raw,edits))
        records.append({'id':identity,'kind':kind,'document':doc(raw),'edits':list(edits),'normalized':doc(value.to_dict())})
        return value.to_dict()
    def reject(identity,kind,raw,edits,code):
        try:KINDS[kind].from_dict(changed(raw,edits))
        except SerializationError:pass
        else:raise AssertionError('accepted rejection '+identity)
        rejections.append({'id':identity,'kind':kind,'document':doc(raw),'edits':edits,'expected_code':code})
    def set_(identity,kind,raw,key,value,code):reject(identity,kind,raw,[{'path':key if isinstance(key,list) else [key],'value':value}],code)
    categories=('unsupported_semantics','missing_implementation','incompatible_composition','contradictory_requirements','missing_sequence_authority','search_budget_exhausted','independent_verification_failure')
    literal_gap={'schema_version':ArchitectureGap.schema_version,'category':'missing_implementation','code':'declared_gap','requirement_ids':['r'],'candidate_ids':[], 'message':'Missing declared realization.','conflict_set':[]}
    gap=keep('literal/gap','gap',literal_gap)
    for category in categories:keep('gap/'+category,'gap',dict(gap,category=category))
    keep('gap/sorted','gap',dict(gap,requirement_ids=['z','a'],candidate_ids=['b','a'],conflict_set=['z','a']))
    literal_real={'schema_version':RequirementRealization.schema_version,'id':'r','source_node_ids':['node'],'refinement_ids':[],'status':'unresolved','assumptions':[],'reasons':['Needs a realization.']}
    realization=keep('literal/realization','realization',literal_real)
    keep('realization/implemented','realization',dict(realization,status='implemented',refinement_ids=['z','a'],source_node_ids=['z','a'],assumptions=['z','a'],reasons=[]))
    alternate=keep('alternative/empty','alternative',{'schema_version':ArchitectureAlternative.schema_version,'refinement_ids':[],'gaps':[]})
    keep('alternative/repeated_gaps','alternative',dict(alternate,refinement_ids=['z','a'],gaps=[gap,gap]))
    plan=keep('plan/literal','plan',{'schema_version':PayloadArchitecturePlan.schema_version,'selected_refinement_ids':['a'], 'ledger':[realization], 'placements':[], 'helpers':[], 'channels':[], 'control_domains':[], 'assumptions':[], 'instances':[], 'availability':[]})
    arbitrary={'empty':None,'big':9007199254740993,'negative_zero':-0.0,'real':1.0,'integer':1,'boolean':True,'unicode':'α'}
    keep('plan/arbitrary_ordered_maps','plan',dict(plan,**{k:[arbitrary,{},arbitrary] for k in ('placements','helpers','channels','control_domains','availability')},assumptions=['z','a']))
    keep('plan/ordered_ledger','plan',dict(plan,ledger=[dict(realization,id='z'),dict(realization,id='a')]))
    instance=lambda identity:{'schema_version':'biocompiler.architecture_refinement_instance.v0.1','id':identity,'refinement_id':'declared','source_bindings':{'model':'source'}}
    keep('plan/instances','plan',dict(plan,selected_refinement_ids=['z','a'],instances=[instance('z'),instance('a')]))
    export=keep('literal/export','export',{'schema_version':PayloadArchitectureExport.schema_version,'fasta':'>member\nAU\n','manifest':arbitrary})
    keep('export/historical_prefix_only','export',dict(export,fasta='>',manifest={}))
    base=None
    for variant in ('base','parameter-default','parameter-override'):
        raw=json.loads((ROOT/'tests/conformance/case-b'/variant/'candidate.json').read_bytes())
        keep('case_b/'+variant,'build',raw)
        keep('construction/'+variant,'construction_build',raw['construction'])
        keep('plan/'+variant,'plan',raw['plan'])
        if variant=='base':base=raw
    construction=base['construction']
    stale=deepcopy(construction);stale['assessment']['reconstructed_fingerprint']='f'*64
    keep('construction/stale_reconstruction_is_historical','construction_build',stale)
    for status in ('compiled','partial'):keep('build/'+status,'build',dict(base,status=status))
    for status in ('unsupported','no_solution','search_exhausted'):
        for left,right in ((None,None),(plan,None),(None,construction)):
            keep('build/'+status+'/'+str(len(records)),'build',dict(base,status=status,plan=left,construction=right))
    keep('build/matching_census','build',dict(base,match_instances=[instance('z'),instance('a')]))
    keep('build/duplicate_diagnostics_and_alternatives','build',dict(base,diagnostics=[gap,gap],alternatives=[alternate,alternate]))
    report={'schema_version':PayloadArchitectureVerification.schema_version,'request_fingerprint':base['request_fingerprint'],'build_fingerprint':fingerprint(base),'outcome':'pass','translation_complete':True,'construction_complete':True,'diagnostics':[], 'unresolved':[], 'assumptions':[], 'checker_version':CHECKER_VERSION,'claim_scope':CLAIM_SCOPE,'search_verified':False,'empirical_validation':'unknown','human_therapeutic_admission':'not_admitted'}
    assessment=keep('assessment/complete','assessment',report)
    for outcome in ('pass','fail','unknown','unsupported'):
        keep('assessment/'+outcome,'assessment',dict(report,outcome=outcome,translation_complete=False,construction_complete=False,diagnostics=[] if outcome=='pass' else [gap,gap],unresolved=['z','a'],assumptions=[' z ','a\n']))
    keep('assessment/fail_complete_historical','assessment',dict(report,outcome='fail',diagnostics=[gap]))
    bases={'construction_build':construction,'gap':gap,'realization':realization,'plan':plan,'alternative':alternate,'build':base,'export':export,'assessment':assessment}
    for kind,raw in bases.items():
        for key in raw:reject(kind+'/missing/'+key,kind,raw,[{'path':[key],'remove':True}],'missing_field')
        set_(kind+'/extra',kind,raw,'extra',None,'unknown_field')
        set_(kind+'/schema',kind,raw,'schema_version','future','unsupported_schema')
    for field in ('request_fingerprint','candidate_fingerprint'):
        set_('construction/'+field,'construction_build',construction,['assessment',field],'f'*64,'invalid_construction_build')
    set_('construction/request','construction_build',construction,['candidate','request_fingerprint'],'f'*64,'invalid_construction_build')
    for key in ('code','message'):set_('gap/empty/'+key,'gap',gap,key,'','invalid_molecular_text')
    set_('gap/category','gap',gap,'category','future','invalid_architecture_build')
    for key in ('requirement_ids','candidate_ids','conflict_set'):set_('gap/duplicate/'+key,'gap',gap,key,['same','same'],'invalid_architecture_build')
    set_('realization/status','realization',realization,'status','future','invalid_architecture_build')
    set_('realization/empty_implemented','realization',realization,'status','implemented','invalid_architecture_build')
    set_('plan/empty_selection','plan',plan,'selected_refinement_ids',[],'invalid_architecture_build')
    set_('plan/duplicate_ledger','plan',plan,'ledger',[realization,realization],'invalid_architecture_build')
    for key in ('placements','helpers','channels','control_domains','availability'):set_('plan/type/'+key,'plan',plan,key,[None],'invalid_type')
    set_('plan/unknown_instance','plan',plan,'instances',[instance('z')],'invalid_architecture_build')
    set_('plan/duplicate_instance','plan',plan,'instances',[instance('a'),instance('a')],'invalid_architecture_build')
    set_('build/duplicate_instance','build',base,'match_instances',[instance('a'),instance('a')],'invalid_architecture_build')
    set_('build/status','build',base,'status','future','invalid_architecture_build')
    set_('build/compiled_missing_plan','build',base,'plan',None,'invalid_architecture_build')
    set_('build/unsupported_retains_both','build',base,'status','unsupported','invalid_architecture_build')
    set_('export/prefix','export',export,'fasta','AU','invalid_architecture_build')
    set_('export/map','export',export,'manifest',[],'invalid_type')
    for key,value in (('outcome','future'),('request_fingerprint','f'*63),('build_fingerprint','F'*64),('checker_version','future'),('claim_scope','verified'),('empirical_validation','pass'),('human_therapeutic_admission','admitted'),('search_verified',True),('diagnostics',[gap]),('construction_complete',False),('unresolved',['open'])):
        set_('assessment/reject/'+key,'assessment',assessment,key,value,'invalid_architecture_assessment')
    for key in ('translation_complete','construction_complete','search_verified'):set_('assessment/bool/'+key,'assessment',assessment,key,1,'invalid_type')
    for key in ('unresolved','assumptions'):
        set_('assessment/duplicate/'+key,'assessment',assessment,key,['a','a'],'invalid_architecture_assessment')
        set_('assessment/empty/'+key,'assessment',assessment,key,[' \t'],'invalid_name')
    corpus={'schema_version':SCHEMA,'documents':documents,'records':records,'rejections':rejections,
        'literal_expectations':{'gap':literal_gap,'realization':literal_real,'export':export},
        'coverage':{'case_b':['base','parameter-default','parameter-override'],'kinds':sorted(KINDS),'fresh_acceptance':False}}
    corpus['inventory_fingerprint']=inventory(corpus)
    return corpus

def main():
    p=argparse.ArgumentParser();p.add_argument('--write',action='store_true');args=p.parse_args()
    corpus=build_corpus();data=encoded(corpus)
    if args.write:CORPUS.write_bytes(data)
    else:assert CORPUS.read_bytes()==data,'Architecture build corpus drift'
    print(f"Architecture build corpus: {len(corpus['records'])} records, {len(corpus['rejections'])} rejections, {len(corpus['documents'])} documents, {len(data)} bytes; {corpus['inventory_fingerprint']}")
if __name__=='__main__':main()
