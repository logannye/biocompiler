"""Hosted public joined workflow rehearsal with independent artificial originals.

No native code runs on import. Retained-result checks use literal source inputs,
exact wire identities and expected outcomes, never a Python activity evaluator.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys
import time
import zipfile
from unittest.mock import patch

try:
    from .check_policy_controlled_behavior import file_pin, imported_modules, require
    from .check_policy_core import source_identity
except ImportError:
    from check_policy_controlled_behavior import file_pin, imported_modules, require
    from check_policy_core import source_identity

ROOT = Path(__file__).resolve().parents[1]
ASSETS = 'data/controlled_composition'
EXAMPLE = 'examples/controlled_composition.py'
CASE_IDS = ('baseline','tight','short-member','short-total','tight-deadlines','horizon-eleven','short-horizon','material-longer','slow-onset','relaxed-onset','missing-readout')
ACCEPTED = ('baseline','tight','tight-deadlines','horizon-eleven','material-longer','relaxed-onset')
CONTROLS = ('check-core','check-verify','replay-verify','changed-fasta-a','changed-fasta-b','changed-candidate-a','changed-candidate-b','changed-manifest','stale-project','changed-limits','transport-cancellation','verify-producer')
OBSERVATIONS = tuple(case+'-'+step for case in CASE_IDS for step in
    (('original','prepared','compile','export','reverify','publication') if case in ACCEPTED else ('original','prepared','compile'))) + CONTROLS
INPUTS = (EXAMPLE, *(ASSETS+'/'+name+'-input.json' for name in CASE_IDS), ASSETS+'/expected.json', ASSETS+'/provenance.json')
SCHEMA = 'biocompiler.controlled_research_project_campaign.v0.1'
MILESTONES = tuple(case+'-'+('publication' if case in ACCEPTED else 'compile') for case in CASE_IDS) + ('verify-producer',)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',',':'), ensure_ascii=False, allow_nan=False).encode()


def digest(value): return hashlib.sha256(canonical(value)).hexdigest()


def load(path):
    from biocompiler.core_client import decode_json
    file_pin(path,16*1024*1024)
    return decode_json(Path(path).read_bytes())


def checked_assets(root=ROOT):
    root=Path(root); expected=load(root/ASSETS/'expected.json'); provenance=load(root/ASSETS/'provenance.json')
    require(tuple(row['id'] for row in expected['cases'])==CASE_IDS,'Independent case census differs')
    require(provenance['expected_sha256']==file_pin(root/ASSETS/'expected.json')['sha256'],'Expected literals changed')
    require(set(provenance['inputs'])=={case+'-input.json' for case in CASE_IDS},'Original input census differs')
    inputs={}
    for case in expected['cases']:
        path=root/ASSETS/case['input'];require(case['input']==case['id']+'-input.json','Foreign original path')
        require(file_pin(path)==provenance['inputs'][case['input']],'Original bytes changed')
        value=load(path);require(digest(value)==case['request_sha256'],'Original canonical authority changed')
        inputs[case['id']]=value
    require(expected['scope']=='artificial_two_rna_conditional_workflow_only' and expected['empirical']==expected['human_use']=='unassessed','Fixture scope promoted')
    return {'root':root,'expected':expected,'inputs':inputs,'pins':{name:file_pin(root/name) for name in INPUTS}}


def load_example(path):
    spec=importlib.util.spec_from_file_location('controlled_public_example',path)
    require(spec is not None and spec.loader is not None,'Missing public example')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def expected_fasta(case):
    return ''.join('>rna_%04d alphabet=RNA\n%s\n'%(i+1,sequence) for i,sequence in enumerate(case['sequences']))


def check_result(result,case,original,*,exported=False):
    report=result['report'];material=report['material'];behavior=report['behavior']
    require(result['request_fingerprint']==digest(original),'Result belongs to different complete original')
    require(report['project_context']==original['behavior_request']['original']['source_authority']['project_context'] and report['limits']==original['limits'],'Project context or limits substituted')
    require(report['empirical_status']==report['human_use']=='unassessed' and report['therapeutic_export']=='withheld','Workflow promoted human use')
    require(material['structure']['outcome']=='pass','Artificial supplied complete molecules lost structural correspondence')
    limits=material['material_limits'];require(limits['member_order']==case['member_order'] and limits['total_rna_nt']==sum(map(len,case['sequences'])),'Original member/length census changed')
    require([row['rna_nt'] for row in limits['members']]==list(map(len,case['sequences'])),'Per-member RNA lengths differ')
    domain=behavior['domain'];require(all(domain['counters'][key]==case[key] for key in ('histories','prefixes','transitions')),'Full finite-domain census differs')
    require(domain['completion']=='complete' and domain['assessed_histories']==2 and domain['pending_at_horizon'] is False,'Fixture domain was incomplete or retained pending work')
    require(behavior['model_correspondence']=='pass','Candidate differs from supplied model')
    status=case['status'];wanted='pass' if status=='accepted' else 'unknown' if status=='unknown' else 'fail'
    require(report['outcome']==wanted and report['status']==('controlled_workflow_accepted' if wanted=='pass' else 'not_accepted'),'Joined literal outcome differs')
    require(material['outcome']==('fail' if status=='material_fail' else 'pass'),'Material outcome differs')
    require(behavior['outcome']==('fail' if status=='behavior_fail' else 'unknown' if status=='unknown' else 'pass'),'Behavior outcome differs')
    resources=original['limits']['resources'];lengths=list(map(len,case['sequences']))
    require(limits=={'member_order':case['member_order'],'expected_member_order':case['member_order'],
        'members':[{'member_id':member,'rna_nt':length,'within_limit':length<=resources['max_member_rna_nt']} for member,length in zip(case['member_order'],lengths)],
        'max_member_rna_nt':resources['max_member_rna_nt'],'total_rna_nt':sum(lengths),
        'max_total_rna_nt':resources['max_total_rna_nt'],'outcome':'fail' if status=='material_fail' else 'pass'},'Material failure did not preserve its exact independent member/total bound')
    kinds=('no_unauthorized_activation','initial_activation','controller_cessation','antigen_cessation','component_cessation','reactivation')
    require(tuple(row['kind'] for row in behavior['requirements'])==kinds,'Source requirement inventory/order changed')
    for row in behavior['requirements']:
        kind=row['kind']
        if status=='unknown':counts={'pass':0,'fail':0,'unknown':2,'not_exercised':0}
        elif status=='behavior_fail' and kind=='initial_activation':counts={'pass':0,'fail':2,'unknown':0,'not_exercised':0}
        else:
            delayed=case['id'] in ('slow-onset','relaxed-onset')
            passed=(2 if kind in ('no_unauthorized_activation','initial_activation') else 0 if kind=='controller_cessation' else 1) if delayed else (1 if kind=='controller_cessation' else 2)
            counts={'pass':passed,'fail':0,'unknown':0,'not_exercised':2-passed}
        require({key:row[key] for key in counts}==counts,'Wrong specific source requirement outcome: '+kind)
    require(behavior['coverage']=={key:True for key in ('active','background','antigen_absent_controller_enabled','controller_disabled_antigen_present','reversible_cycle')},'Fixture non-vacuous coverage changed')
    require(behavior['evidence_status']==('unknown' if status=='unknown' else 'resolved'),'Readout missingness was confused with physical behavior')
    if status in ('behavior_fail','unknown'):
        cex=behavior['counterexample'];require(cex is not None and len(cex['trace'])==case['horizon_tick']+1,'Missing full failure history')
        require(cex['history_index']==1 and cex['reduction']=='none_complete_original_history' and cex['model_correspondence'] is True and cex['pending_at_horizon'] is False and cex['deployment_evidence_unknown'] is False,'Wrong failure history or cause')
        monitor=cex['source_monitor'];require(monitor['complete'] is True and monitor['outcome']==wanted and monitor['pending'] is False,'Wrong source-monitor outcome')
        require(monitor['evidence_gaps']==([{'tick':3,'channel':'activity','status':'missing'}] if status=='unknown' else []),'Failure came from unrelated observation evidence')
        # Independently literal first (held-controller) history, including the
        # complete suffix. This is a fixed fixture oracle, not an evaluator.
        bands=(['background']*3+['active']*3+['background']+['active']*5 if status=='behavior_fail'
               else ['background']+['active']*5+['background']+['active']*4)
        require(len(bands)==case['horizon_tick']+1,'Literal failure horizon changed')
        for tick,(row,band) in enumerate(zip(cex['trace'],bands)):
            sample={'tick':tick,'band':band,'activation_generation':1 if band=='active' else None}
            require(row['candidate']==row['model_reference']==sample and row['corresponds'] is True,'Full literal physical failure trace differs')
            fixed=next(item for item in original['behavior_request']['original']['operating_domain']['fixed_inputs'] if item['tick']==(1 if tick==2 else tick))
            expected_input={'tick':tick,'event':'start' if tick==0 else 'none','live':True,'generation':1,'generation_started_tick':0,'physical':fixed['physical'],'evidence':fixed['evidence']}
            require(row['input']==expected_input,'Counterexample selected different original inputs or evidence')
            require(monitor['history'][tick]=={'input':expected_input,'activity':sample,'readout_evidence':'missing' if status=='unknown' and tick==3 else 'valid','qualified_gate':tick!=5,'inputs_required':True},'Monitor changed the literal physical/readout separation')
        onset=next(row for row in monitor['requirements'] if row['kind']=='initial_activation')
        def onset_event(action,tick):return {'tick':tick,'action':action,'trigger_tick':0,'deadline_tick':2,'generation':1}
        events=[onset_event('triggered',0)]
        if status=='behavior_fail':events.append(onset_event('deadline_missed',2))
        events.append(onset_event('discharged',3 if status=='behavior_fail' else 1))
        require(onset['events']==events and onset['status']==('fail' if status=='behavior_fail' else 'unknown'),'Wrong onset deadline or failure reason')
    if exported:
        artifact=result['artifact'];require(artifact is not None and artifact['fasta']==expected_fasta(case),'Exact independent two-RNA FASTA differs')
        manifest=artifact['manifest'];require(manifest['request']==original and manifest['limits']==original['limits'] and manifest['candidate']==result['candidate'] and manifest['report']==report,'Published complete originals/candidate/report changed')
        require([row['member_id'] for row in manifest['members']]==case['member_order'],'Publication member order changed')
    else:require(result['artifact'] is None,'Compile or rejected result published unchecked material')


def check_pair(path,result,case):
    from biocompiler.core_client import encode_json
    artifact=result['artifact'];require(artifact['fasta']==expected_fasta(case),'Wrong expected FASTA')
    with zipfile.ZipFile(path) as archive:
        require(archive.namelist()==['program.fasta','manifest.json'],'Archive member census differs')
        require(all(row.compress_type==zipfile.ZIP_STORED and not row.flag_bits for row in archive.infolist()),'Unexpected ZIP representation')
        require(archive.read('program.fasta')==artifact['fasta'].encode() and archive.read('manifest.json')==encode_json(artifact['manifest']),'Published bytes differ from fresh Verify')
    return {'path':Path(path).name,**file_pin(path),'fasta_sha256':hashlib.sha256(artifact['fasta'].encode()).hexdigest(),'manifest_sha256':digest(artifact['manifest'])}


def changed_bundle(source,target,kind):
    from biocompiler.core_client import encode_json
    with zipfile.ZipFile(source) as archive:
        fasta=archive.read('program.fasta');manifest=json.loads(archive.read('manifest.json'))
    if kind.startswith('changed-fasta'):
        lines=fasta.split(b'\n');index=1 if kind.endswith('a') else 3;lines[index]=b'G'+lines[index][1:];fasta=b'\n'.join(lines)
    elif kind.startswith('changed-candidate'):
        construction=manifest['candidate']['material_candidate']['construction'];inventory=construction['inventory'];index=0 if kind.endswith('a') else 1
        molecule=inventory['molecules'][index];molecule['sequence']='G'+molecule['sequence'][1:]
        for role in inventory['role_instances']:
            if role['subject_id']==molecule['id']:role['subject_fingerprint']=digest(molecule)
    else:
        require(kind=='changed-manifest','Unknown exact mutation');manifest['report']['human_use']='accepted'
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_STORED) as archive:
        for name,raw in (('program.fasta',fasta),('manifest.json',encode_json(manifest))):
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.external_attr=0o100644<<16;archive.writestr(info,raw)


def prepare_case(example,packet,case,folder):
    name=case['id'];path=folder/(name+'-project.json');baseline=folder/'baseline-project.json'
    if name in ('tight','short-member','short-total'):
        resource=packet['inputs'][name]['limits']['resources'];project=example.edit(baseline,path,max_member_rna_nt=resource['max_member_rna_nt'],max_total_rna_nt=resource['max_total_rna_nt'])
    elif name=='tight-deadlines':
        project=example.edit(baseline,path,deadlines={key:1 for key in packet['inputs'][name]['behavior_request']['original']['source_authority']['control_contract']['requested_deadlines']})
    elif name in ('horizon-eleven','short-horizon'):
        project=example.edit(baseline,path,horizon_input=packet['root']/ASSETS/case['input'])
    elif name=='material-longer':project=example.edit(baseline,path,material_input=packet['root']/ASSETS/case['input'])
    elif name=='relaxed-onset':project=example.edit(folder/'slow-onset-project.json',path,deadlines={'onset_ticks':3})
    else:project=example.prepare(packet['root']/ASSETS/case['input'],path)
    require(project.request==packet['inputs'][name] and project.limits==packet['inputs'][name]['limits'],'Typed public edit changed independent authority')
    return path,project


def exercise(packet,example,core,verify,retain,folder):
    from biocompiler.core_client import CoreCancelled,CoreRejected,CoreProtocolError
    from biocompiler.core_policy_controlled_workflow import PolicyControlledWorkflowClient
    from biocompiler.policy.research_project import ResearchProjectRejected,ResearchProjectError
    values={};projects={};publications=[]
    for case in packet['expected']['cases']:
        name=case['id'];original=packet['inputs'][name];retain(name+'-original',{'request':original,'expected':case})
        path,project=prepare_case(example,packet,case,folder);projects[name]={'path':path.name,**file_pin(path),'project_sha256':project.digest,'originals_sha256':digest(original)}
        preflight=example.preflight(path);require(preflight['native_status']=='not_run','Preflight claimed native execution')
        retain(name+'-prepared',{'preflight':preflight,'explanation':example.explain(path),'project':project.data})
        bundle=folder/(name+'.zip')
        try:built=example.compile_project(path,bundle,core=core,verify=verify)
        except ResearchProjectRejected as error:
            require(case['status'] in ('material_fail','behavior_fail','unknown'),'Unexpected rejected positive case')
            check_result(error.compiled.result,case,original);retain(name+'-compile',error.compiled.result)
            require(not bundle.exists(),'Rejected project published a bundle');continue
        except CoreRejected as error:
            require(case['status']=='domain_rejected' and {d.code for d in error.response.diagnostics}=={'policy_controlled_domain'} and len(error.response.diagnostics)==1 and error.response.diagnostics[0].message=='Hold suffix cannot cover every original source deadline.','Domain rejection occurred at an unrelated boundary')
            retain(name+'-compile',{'status':error.response.status,'diagnostics':[asdict(d) for d in error.response.diagnostics]});require(not bundle.exists(),'Rejected domain published a bundle');continue
        require(case['status']=='accepted','Nonaccepted fixture acquired acceptance')
        check_result(built.compiled.result,case,original);check_result(built.verified.result,case,original,exported=True)
        retain(name+'-compile',built.compiled.result);retain(name+'-export',built.verified.result)
        fresh=example.verify_project(path,bundle,verify=verify);require(fresh.result==built.verified.result,'Fresh reopen changed complete native evidence')
        retain(name+'-reverify',fresh.result);pair=check_pair(bundle,fresh.result,case);retain(name+'-publication',pair);publications.append(pair);values[name]=built
    baseline=values['baseline'];request=packet['inputs']['baseline'];client=PolicyControlledWorkflowClient(verify)
    core_check=PolicyControlledWorkflowClient(core).check(request,baseline.compiled.candidate)
    require(core_check.report==baseline.compiled.report and core_check.candidate==baseline.compiled.candidate,'Core checking changed compiled evidence');retain('check-core',core_check.result)
    for operation in ('check','replay'):
        value=(client.check(request,baseline.compiled.candidate) if operation=='check' else client.replay(request,baseline.compiled.candidate,baseline.compiled.report))
        require(value.report==baseline.compiled.report and value.candidate==baseline.compiled.candidate,'Fresh Verify check/replay differs from Core compile')
        if operation=='check':require(value.result==core_check.result,'Fresh Core/Verify check differs')
        retain(operation+'-verify',value.result)
    for name in CONTROLS[3:8]:
        target=folder/(name+'.zip');changed_bundle(folder/'baseline.zip',target,name)
        try:example.verify_project(folder/'baseline-project.json',target,verify=verify)
        except ResearchProjectError as error:
            boundary='independent_verify_rejection' if name.startswith('changed-candidate') else 'exact_pair_mismatch'
            text='did not produce an accepted pair' if boundary=='independent_verify_rejection' else 'exact FASTA/manifest pair'
            require(text in str(error),'Mutation failed at unrelated boundary');retain(name,{'status':'rejected','boundary':boundary,'message':str(error),'bundle':file_pin(target)})
        else:raise AssertionError('Altered bundle acquired acceptance')
    try:example.verify_project(folder/'tight-project.json',folder/'baseline.zip',verify=verify)
    except ResearchProjectError as error:
        require('original authority differs' in str(error),'Changed project failed at unrelated boundary');retain('stale-project',{'status':'rejected','boundary':'independent_originals','message':str(error)})
    else:raise AssertionError('Changed independent originals accepted old pair')
    altered=deepcopy(request);altered['limits']['horizon_tick']+=1
    from biocompiler.policy.controlled_workflow import ControlledWorkflowRequest
    try:ControlledWorkflowRequest.from_request(altered)
    except CoreProtocolError as error:
        require('limits' in str(error) and 'original' in str(error),'Changed limits failed at unrelated boundary')
        retain('changed-limits',{'status':'rejected','boundary':'exact_limits_projection','message':str(error),'original':altered})
    else:raise AssertionError('Detached workflow limits accepted')
    output=folder/'cancelled.zip'
    try:example.compile_project(folder/'baseline-project.json',output,core=core,verify=verify,cancelled=lambda:True)
    except CoreCancelled:retain('transport-cancellation',{'status':'cancelled','published':output.exists()});require(not output.exists(),'Cancellation published a bundle')
    else:raise AssertionError('Cancelled workflow ran')
    try:verify.call('compile-policy-controlled-workflow',{'request':request})
    except CoreRejected as error:
        require(error.response.status=='unsupported' and {d.code for d in error.response.diagnostics}=={'unsupported_operation'},'Verify unexpectedly implements producer');retain('verify-producer',{'status':error.response.status,'diagnostics':[asdict(d) for d in error.response.diagnostics]})
    else:raise AssertionError('Verify producer operation accepted')
    return {'projects':projects,'publications':publications}



def expected_actions(packet, values):
    """Exact invocation plan from independent originals and supplied candidates.

    Candidate bytes remain proposals, never expected molecular/behavioral truth.
    Every negotiation, operation and local-only negative has an explicit place.
    """
    actions=[]
    def add(role, verb, payload, observation, *, negotiate=True):
        operation=verb+'-policy-controlled-workflow'
        if negotiate:actions.append({'role':role,'operation':'capabilities','payload':{},'next_operation':operation})
        actions.append({'role':role,'operation':operation,'payload':payload,'observation':observation})
    for name in CASE_IDS:
        request=packet['inputs'][name]
        add('core','compile',{'request':request},name+'-compile')
        if name in ACCEPTED:
            payload={'request':request,'candidate':values[name+'-compile']['candidate']}
            add('verify','export',payload,name+'-export')
            add('verify','export',payload,name+'-reverify')
    request=packet['inputs']['baseline'];candidate=values['baseline-compile']['candidate']
    payload={'request':request,'candidate':candidate}
    add('core','check',payload,'check-core');add('verify','check',payload,'check-verify')
    add('verify','replay',{**payload,'report':values['baseline-compile']['report']},'replay-verify')
    for name in CONTROLS[3:8]:
        changed=deepcopy(candidate)
        if name.startswith('changed-candidate'):
            inventory=changed['material_candidate']['construction']['inventory'];index=0 if name.endswith('a') else 1
            molecule=inventory['molecules'][index];molecule['sequence']='G'+molecule['sequence'][1:]
            for role in inventory['role_instances']:
                if role['subject_id']==molecule['id']:role['subject_fingerprint']=digest(molecule)
        add('verify','export',{'request':request,'candidate':changed},name)
    # Original/limit/cancellation controls must emit no native invocation.
    add('verify','compile',{'request':request},'verify-producer',negotiate=False)
    require(len(actions)==63,'Closed invocation plan changed')
    return actions


def validate_receipt(receipt, evidence, *, root=ROOT):
    """Inert complete original/byte comparison; saved PASS is not native authority."""
    from biocompiler.core_client import _response, _capabilities, encode_json
    from biocompiler.core_policy_controlled_workflow import _result, PROFILE, PRODUCER_PROFILE, VALIDATION_SCOPE
    from biocompiler.policy.material import _verify_staged
    packet=checked_assets(root);evidence=Path(evidence)
    require(receipt['schema_version']==SCHEMA and receipt['status']=='passed' and receipt['acceptance'] is False,'Incomplete public workflow receipt')
    require(receipt['inputs']==packet['pins'] and tuple(row['name'] for row in receipt['observations'])==OBSERVATIONS,'Stale inputs or observation census')
    expected_files={name+'.json' for name in OBSERVATIONS}|{name+'-project.json' for name in CASE_IDS}|{name+'.zip' for name in (*ACCEPTED,*CONTROLS[3:8])}|{'native-%03d.json'%index for index in range(63)}
    files=receipt['files'];require(set(files)==expected_files=={path.name for path in evidence.iterdir()} and all(path.is_file() and not path.is_symlink() for path in evidence.iterdir()),'Unexplained or missing workflow files')
    for name,expected in files.items():
        require(Path(name).name==name and file_pin(evidence/name)==expected,'Retained workflow file identity differs')
    values={}
    for row in receipt['observations']:
        path=evidence/(row['name']+'.json');require(row['path']==evidence.name+'/'+path.name and file_pin(path)=={key:row[key] for key in ('sha256','bytes')},'Sidecar identity/path changed')
        values[row['name']]=load(path)
    for case in packet['expected']['cases']:
        name=case['id'];original=packet['inputs'][name]
        require(values[name+'-original']=={'request':original,'expected':case},'Retained independent originals changed')
        prepared=values[name+'-prepared'];project=prepared['project'];context=original['behavior_request']['original']['source_authority']['project_context']
        require(project=={'schema_version':'biocompiler.research_project.v0.3','route':'controlled_composition','request':original,'limits':original['limits'],**context},'Complete retained project changed')
        require(load(evidence/(name+'-project.json'))==project and prepared['preflight']['project_sha256']==digest(project) and prepared['preflight']['native_status']=='not_run','Project/preflight differs')
        result=values[name+'-compile']
        if case['status']=='domain_rejected':require(result['status']=='error' and len(result['diagnostics'])==1 and result['diagnostics'][0]['code']=='policy_controlled_domain' and result['diagnostics'][0]['message']=='Hold suffix cannot cover every original source deadline.','Wrong domain rejection')
        else:check_result(result,case,original)
        if name in ACCEPTED:
            check_result(values[name+'-export'],case,original,exported=True)
            require(values[name+'-reverify']==values[name+'-export'],'Reopen differs from complete fresh export')
            require(check_pair(evidence/(name+'.zip'),values[name+'-export'],case)==values[name+'-publication'],'Retained pair differs')
            artifact=values[name+'-export']['artifact']
            _verify_staged(evidence/(name+'.zip'),(('program.fasta',artifact['fasta'].encode()),('manifest.json',encode_json(artifact['manifest']))))
        else:require(not (evidence/(name+'.zip')).exists(),'Rejected case retained an accepted archive')
    expected_projects={name:{'path':name+'-project.json',**file_pin(evidence/(name+'-project.json')),
        'project_sha256':digest(values[name+'-prepared']['project']),'originals_sha256':digest(packet['inputs'][name])} for name in CASE_IDS}
    require(receipt['projects']==expected_projects and receipt['publications']==[values[name+'-publication'] for name in ACCEPTED],'Project/publication inventory differs')
    actions=expected_actions(packet,values)
    require(len(receipt['native_frames'])==len(actions) and len({row['request_id'] for row in receipt['native_frames']})==len(actions),'Incomplete or duplicate native invocation census')
    for index,(row,action) in enumerate(zip(receipt['native_frames'],actions)):
        path=evidence/('native-%03d.json'%index);require(row['path']==evidence.name+'/'+path.name and file_pin(path)=={key:row[key] for key in ('sha256','bytes')},'Native frame path/pin/order differs')
        wire=load(path);frame=wire['frame'];raw=encode_json(frame,limit=16*1024*1024)
        require(set(wire)=={'payload','frame'} and wire['payload']==action['payload'] and row['operation']==action['operation'] and row['executable']==action['role'],'Native frame changed original payload, operation or role')
        require(hashlib.sha256(raw).hexdigest()==row['response_sha256'],'Decoded native response changed')
        require(frame['status'] in ('ok','error','unsupported'),'Unknown native response status')
        response=_response(raw,{'ok':0,'error':2,'unsupported':3}[frame['status']],row['request_id'],row['operation'],row['executable'])
        if action['operation']=='capabilities':
            require(response.status=='ok' and not response.diagnostics,'Capability negotiation failed')
            capabilities=_capabilities(response.result);capabilities.require_operation(action['next_operation'])
            require(capabilities.profiles.get('policy_controlled_workflow')==(PRODUCER_PROFILE if action['role']=='core' else PROFILE) and VALIDATION_SCOPE in capabilities.validation_scopes,'Negotiated a different workflow profile')
            continue
        name=action['observation']
        if name in ('short-horizon-compile','verify-producer'):
            require(response.result is None and response.status==('error' if name=='short-horizon-compile' else 'unsupported'),'Wrong native rejection stage')
            require(values[name]=={'status':response.status,'diagnostics':[asdict(d) for d in response.diagnostics]},'Retained rejection differs from actual native frame')
        else:
            require(response.status=='ok','Unexpected native error replaced required complete evidence')
            checked=_result(response,wire['payload']).result
            if name in CONTROLS[3:8]:
                if name.startswith('changed-candidate'):
                    report=checked['report'];material=report['material']
                    require(checked['artifact'] is None and report['outcome']==material['outcome']=='fail' and material['structure']['content_reconstruction']['outcome']=='fail' and material['material_limits']['outcome']=='pass','Changed candidate failed at an unrelated boundary')
                    require(report['behavior']==values['baseline-compile']['report']['behavior'],'Material mutation changed independent behavior assessment')
                else:require(checked==values['baseline-export'],'Changed exported bytes altered fresh native checking')
            else:require(checked==values[name],'Retained observation is not its exact fresh native result')
    baseline=values['baseline-export']['artifact']
    for name in CONTROLS[3:8]:
        fasta=baseline['fasta'].encode();manifest=deepcopy(baseline['manifest'])
        if name.startswith('changed-fasta'):
            lines=fasta.split(b'\n');index=1 if name.endswith('a') else 3;lines[index]=b'G'+lines[index][1:];fasta=b'\n'.join(lines)
        elif name.startswith('changed-candidate'):
            action=next(row for row in actions if row.get('observation')==name);manifest['candidate']=action['payload']['candidate']
        else:manifest['report']['human_use']='accepted'
        target=evidence/(name+'.zip');_verify_staged(target,(('program.fasta',fasta),('manifest.json',encode_json(manifest))))
        boundary='independent_verify_rejection' if name.startswith('changed-candidate') else 'exact_pair_mismatch'
        message='Independent Verify did not produce an accepted pair' if name.startswith('changed-candidate') else 'Bundle differs from the independently verified exact FASTA/manifest pair'
        require(values[name]=={'status':'rejected','boundary':boundary,'message':message,'bundle':file_pin(target)},'Mutation sidecar lost its exact rejection or bytes')
    require(values['stale-project']=={'status':'rejected','boundary':'independent_originals','message':'Bundle original authority differs from the independently supplied current project'},'Stale project rejected at wrong boundary')
    changed=deepcopy(packet['inputs']['baseline']);changed['limits']['horizon_tick']+=1
    require(values['changed-limits']=={'status':'rejected','boundary':'exact_limits_projection','message':'Joined limits must exactly equal the complete original authority','original':changed},'Detached limit projection rejected at wrong boundary')
    require(values['check-core']==values['check-verify'],'Fresh Core/Verify check mismatch')
    require(values['check-core']['report']==values['baseline-compile']['report'],'Fresh check changed the complete compiled assessment')
    require(values['replay-verify']['report']==values['baseline-compile']['report'],'Replay altered saved assessment')
    require(values['transport-cancellation']=={'status':'cancelled','published':False},'Cancellation acquired publication')
    require(values['verify-producer']['status']=='unsupported' and {d['code'] for d in values['verify-producer']['diagnostics']}=={'unsupported_operation'},'Verify producer boundary changed')
    timing=receipt['rehearsal'];require(tuple(row['name'] for row in timing['milestones'])==MILESTONES and timing['manual_interventions']==[] and timing['human_usability']=='unassessed' and timing['installation_timing']=='excluded','Rehearsal scope/census changed')
    times=[row['elapsed_ns'] for row in timing['milestones']]+[timing['total_elapsed_ns']]
    require(all(type(value) is int and 0<=value<2**63 for value in times) and times==sorted(times),'Malformed nonmonotonic rehearsal timing')
    return values


def native_authority(binaries, *, root=ROOT):
    try:
        from . import check_policy_development as development
    except ImportError:
        import check_policy_development as development
    prepared=development.preparation(root)
    feedback_path=root/'generated/development-feedback/feedback.json'
    feedback=load(feedback_path)
    development.validate_native_feedback(root,feedback,prepared)
    for role,path in binaries.items():
        actual=file_pin(path,128*1024*1024)
        require(feedback['binaries'][development.SDK_BINARIES[role]]=={'sha256':actual['sha256'],'size':actual['bytes']},'Native executable differs from same-run fresh feedback')
    return {'identity':prepared['identity'],'sources':prepared['sources'],'feedback':file_pin(feedback_path)}


def unchanged_authority(authority,binaries):
    require(native_authority(binaries)==authority,'Source or same-run native feedback changed during rehearsal')


def run(args):
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted','Native workflow rehearsal is hosted-only')
    from biocompiler.core_client import CoreClient,CoreRejected,PROTOCOL,encode_json
    root=Path(args.inputs_root).resolve();packet=checked_assets(root);output=Path(args.output).absolute()
    require(output.parent.is_dir() and not output.exists() and not output.parent.is_symlink(),'Use a fresh bounded receipt destination')
    folder=output.with_suffix('');folder.mkdir(exist_ok=False)
    binaries={role:Path(getattr(args,role)).absolute() for role in ('core','verify')};pins={role:file_pin(path,256*1024*1024) for role,path in binaries.items()}
    for role in pins:require(getattr(args,role+'_sha256') in (None,pins[role]['sha256']),'External native digest differs')
    identity=source_identity();require(identity['run_id']!='local','Missing hosted identity')
    authority=native_authority(binaries)
    receipt={'schema_version':SCHEMA,'status':'incomplete','acceptance':False,'identity':identity,'python':platform.python_version(),'platform':platform.system(),'machine':platform.machine(),'installed':args.require_installed,'inputs':packet['pins'],'binaries':pins,'observations':[],'native_frames':[],'projects':{},'publications':[],'files':{},'empirical':'unassessed','human_use':'unassessed','campaign_script':file_pin(__file__),'native_authority':authority}
    start=time.monotonic_ns();milestones=[]
    def save():output.write_bytes(canonical(receipt))
    def retain(name,value):
        require(len(receipt['observations'])<len(OBSERVATIONS) and name==OBSERVATIONS[len(receipt['observations'])],'Workflow observation census/order differs')
        path=folder/(name+'.json');raw=encode_json(value,limit=16*1024*1024)
        with path.open('xb') as stream:stream.write(raw)
        receipt['observations'].append({'name':name,'path':str(path.relative_to(output.parent)),**file_pin(path)})
        if name in MILESTONES:milestones.append({'name':name,'elapsed_ns':time.monotonic_ns()-start})
        save()
    original_call=CoreClient.call
    def recording_call(self,operation,payload,**kwargs):
        try:response=original_call(self,operation,payload,**kwargs)
        except CoreRejected as error:response=error.response;record(response,operation,payload);raise
        record(response,operation,payload);return response
    def record(response,operation,payload):
        frame={'protocol':PROTOCOL,'request_id':response.request_id,'operation':response.operation,'status':response.status,'result':response.result,'diagnostics':[asdict(d) for d in response.diagnostics],'core':{'implementation':'ocaml','version':response.version,'protocol':PROTOCOL,'executable':response.executable}}
        raw=encode_json(frame,limit=16*1024*1024);path=folder/('native-%03d.json'%len(receipt['native_frames']))
        path.write_bytes(encode_json({'payload':payload,'frame':frame},limit=16*1024*1024));receipt['native_frames'].append({'path':str(path.relative_to(output.parent)),**file_pin(path),'response_sha256':hashlib.sha256(raw).hexdigest(),'request_id':response.request_id,'operation':operation,'executable':response.executable})
    transports={role:CoreClient(path,role=role,expected_sha256=pins[role]['sha256'],timeout_seconds=300) for role,path in binaries.items()}
    try:
        with patch.object(CoreClient,'call',recording_call):
            receipt.update(exercise(packet,load_example(root/EXAMPLE),transports['core'],transports['verify'],retain,folder))
        require(tuple(row['name'] for row in receipt['observations'])==OBSERVATIONS,'Incomplete workflow observation census')
        receipt['imports']=imported_modules(args.require_installed)
        unchanged_authority(authority,binaries)
        require(source_identity()==identity,'Final source identity changed')
        receipt['final_source_identity']=source_identity()
        require(packet['pins']=={name:file_pin(root/name) for name in INPUTS} and pins=={role:file_pin(path,256*1024*1024) for role,path in binaries.items()},'Inputs or native files changed during rehearsal')
        receipt['rehearsal']={'scope':'automated_public_python_workflow_only','actor':'automated_maintainer_agent','clock':'monotonic_ns','installation_timing':'excluded','human_usability':'unassessed','manual_interventions':[],'milestones':milestones,'total_elapsed_ns':time.monotonic_ns()-start}
        require(tuple(row['name'] for row in milestones)==MILESTONES,'Incomplete rehearsal timing census')
        receipt['files']={path.name:file_pin(path) for path in sorted(folder.iterdir())}
        receipt['status']='passed'
        validate_receipt(receipt,folder,root=root)
    except Exception as error:receipt.update(status='failed',error=type(error).__name__+': '+str(error));raise
    finally:save()
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs-root',type=Path,default=ROOT)
    for role in ('core','verify'):
        parser.add_argument('--'+role,type=Path,required=True);parser.add_argument('--'+role+'-sha256')
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--require-installed',action='store_true')
    run(parser.parse_args())

if __name__=='__main__':main()
