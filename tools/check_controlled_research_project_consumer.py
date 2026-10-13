"""Hosted Verify-only staged consumer using unchanged public ResearchProject.

The closed SDK closure includes reviewed authority dataclasses and inert codecs.
It excludes actual molecular producers and native Core. The host filesystem is
not isolated; the launch guard pins Verify and the kernel denies network access.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import importlib.abc
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

MODULE_FILES = ('biocompiler/__init__.py', 'biocompiler/_policy_coupled_wire.py', 'biocompiler/artifacts/__init__.py', 'biocompiler/artifacts/circuit_construction.py', 'biocompiler/artifacts/circuit_molecules.py', 'biocompiler/artifacts/manifest.py', 'biocompiler/compiler/__init__.py', 'biocompiler/compiler/acceptance.py', 'biocompiler/compiler/deployment.py', 'biocompiler/compiler/human_behavior.py', 'biocompiler/compiler/request.py', 'biocompiler/core_client.py', 'biocompiler/core_distribution.py', 'biocompiler/core_policy.py', 'biocompiler/core_policy_component_material.py', 'biocompiler/core_policy_component_selection.py', 'biocompiler/core_policy_controlled_behavior.py', 'biocompiler/core_policy_controlled_composition.py', 'biocompiler/core_policy_controlled_material.py', 'biocompiler/core_policy_controlled_workflow.py', 'biocompiler/core_policy_expression_material.py', 'biocompiler/core_policy_implementation.py', 'biocompiler/core_policy_material.py', 'biocompiler/core_policy_operational.py', 'biocompiler/errors.py', 'biocompiler/ir/__init__.py', 'biocompiler/ir/behavior.py', 'biocompiler/ir/circuit_construction.py', 'biocompiler/ir/circuit_intent.py', 'biocompiler/ir/circuit_logic.py', 'biocompiler/ir/circuit_molecules.py', 'biocompiler/ir/circuit_observations.py', 'biocompiler/ir/circuit_payloads.py', 'biocompiler/ir/circuit_profile.py', 'biocompiler/ir/circuit_recoding.py', 'biocompiler/ir/circuit_transitions.py', 'biocompiler/ir/component_contracts.py', 'biocompiler/ir/components.py', 'biocompiler/ir/composition.py', 'biocompiler/ir/construct.py', 'biocompiler/ir/intent.py', 'biocompiler/ir/mechanism.py', 'biocompiler/ir/molecule_chemistry.py', 'biocompiler/ir/molecule_records.py', 'biocompiler/ir/payload_contracts.py', 'biocompiler/ir/serialization.py', 'biocompiler/policy/__init__.py', 'biocompiler/policy/behavior.py', 'biocompiler/policy/catalog.py', 'biocompiler/policy/chassis.py', 'biocompiler/policy/component_material.py', 'biocompiler/policy/component_selection.py', 'biocompiler/policy/controlled_behavior.py', 'biocompiler/policy/controlled_composition.py', 'biocompiler/policy/controlled_material.py', 'biocompiler/policy/controlled_workflow.py', 'biocompiler/policy/coordination.py', 'biocompiler/policy/deployment.py', 'biocompiler/policy/effects.py', 'biocompiler/policy/entities.py', 'biocompiler/policy/expression_material.py', 'biocompiler/policy/finite_build.py', 'biocompiler/policy/handoff.py', 'biocompiler/policy/inspection.py', 'biocompiler/policy/logic.py', 'biocompiler/policy/material.py', 'biocompiler/policy/model.py', 'biocompiler/policy/modules.py', 'biocompiler/policy/observations.py', 'biocompiler/policy/patterns.py', 'biocompiler/policy/programs.py', 'biocompiler/policy/requirements.py', 'biocompiler/policy/research_project.py', 'biocompiler/policy/serialization.py', 'biocompiler/policy/space.py', 'biocompiler/policy/state.py', 'biocompiler/policy/time.py', 'biocompiler/policy/typed.py', 'biocompiler/policy/validation.py', 'biocompiler/policy/values.py', 'biocompiler/registry/__init__.py', 'biocompiler/registry/components.py', 'biocompiler/registry/reference_components.py', 'biocompiler/registry/references.py', 'biocompiler/semantics/__init__.py', 'biocompiler/semantics/acceptance.py', 'biocompiler/semantics/admission.py', 'biocompiler/semantics/component_contracts.py', 'biocompiler/semantics/context.py', 'biocompiler/semantics/contracts.py', 'biocompiler/semantics/coordinates.py', 'biocompiler/semantics/deployment.py', 'biocompiler/semantics/human_behavior.py', 'biocompiler/semantics/human_target.py', 'biocompiler/semantics/molecule_coordinates.py', 'biocompiler/semantics/realization.py', 'biocompiler/semantics/types.py', 'biocompiler/verification/__init__.py', 'biocompiler/verification/admission.py')
ROOT=Path(__file__).resolve().parents[1]
OBSERVATIONS=('reopen-verify','repeat-reopen-verify','changed-fasta','changed-originals','verify-producer')


def require(value,message):
    if not value:raise AssertionError(message)


def pin(path,maximum=32*1024*1024):
    path=Path(path);require(path.is_file() and not path.is_symlink() and all(not p.is_symlink() for p in path.parents),'Missing or redirected consumer file')
    require(0<path.stat().st_size<=maximum,'Oversized consumer input')
    raw=path.read_bytes();require(0<len(raw)<=maximum,'Consumer file changed its bound')
    return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def log_pin(path):
    """Only diagnostic logs may be empty; input-file checks remain nonempty."""
    path=Path(path);require(path.is_file() and not path.is_symlink(),'Missing or redirected consumer log')
    require(0<=path.stat().st_size<=32*1024*1024,'Oversized consumer log')
    with path.open('rb') as stream:raw=stream.read(32*1024*1024+1)
    require(len(raw)<=32*1024*1024,'Consumer log grew beyond its bound')
    return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def module_name(path):
    return path[:-12].replace('/','.') if path.endswith('/__init__.py') else path[:-3].replace('/','.')


def worker(stage):
    require(os.environ.get("GITHUB_ACTIONS")=="true" and os.environ.get("RUNNER_ENVIRONMENT")=="github-hosted" and sys.platform=="linux","Native consumer is hosted Linux only")
    stage=Path(stage).resolve();manifest=json.loads((stage/'authority.json').read_bytes())
    require(tuple(manifest['module_files'])==MODULE_FILES,'Consumer codec closure changed')
    for name,expected in manifest['inputs'].items():require(pin(stage/name,256*1024*1024)==expected,'Staged input identity changed')
    expected_paths=set(manifest['inputs'])|{'authority.json'}
    require({str(p.relative_to(stage)) for p in stage.rglob('*') if p.is_file()}==expected_paths,'Unexpected staged file or producer')
    sys.path.insert(0,str(stage));import network_guard
    network=network_guard.network_state('required','linux_libseccomp')
    allowed={module_name(name) for name in MODULE_FILES};launches=[]
    class Boundary(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if (fullname=='biocompiler' or fullname.startswith(('biocompiler.','_biocompiler','biocompiler_core'))) and fullname not in allowed:
                raise ImportError('Unreviewed SDK or producer import: '+fullname)
            return None
    def audit(event,arguments):
        if event=='subprocess.Popen':
            executable,argv,cwd,env=arguments;verify=stage/'bin/biocompiler-verify'
            require(str(executable)==str(verify) and list(argv)==[str(verify)] and cwd is None and env is None,'Consumer may launch only pinned Verify')
            require(pin(verify,256*1024*1024)==manifest['inputs']['bin/biocompiler-verify'],'Staged Verify changed');launches.append(manifest['inputs']['bin/biocompiler-verify']['sha256'])
        elif event in ('os.system','os.exec','os.posix_spawn','os.spawn'):raise AssertionError('Alternate launch path forbidden')
    sys.meta_path.insert(0,Boundary());sys.addaudithook(audit)
    from biocompiler.core_client import CoreClient,CoreRejected,encode_json,PROTOCOL
    from biocompiler.policy.research_project import ResearchProject,ResearchProjectError
    from biocompiler.policy.controlled_workflow import ControlledWorkflowRequest
    frames=[];original_call=CoreClient.call
    def record(response,operation,payload):
        frame={'protocol':PROTOCOL,'request_id':response.request_id,'operation':response.operation,'status':response.status,'result':response.result,'diagnostics':[asdict(d) for d in response.diagnostics],'core':{'implementation':'ocaml','version':response.version,'protocol':PROTOCOL,'executable':response.executable}}
        frames.append({'operation':operation,'payload':payload,'frame':frame,'response_sha256':hashlib.sha256(encode_json(frame,limit=16*1024*1024)).hexdigest()})
    def recording_call(self,operation,payload,**kwargs):
        try:response=original_call(self,operation,payload,**kwargs)
        except CoreRejected as error:record(error.response,operation,payload);raise
        record(response,operation,payload);return response
    CoreClient.call=recording_call
    verify=CoreClient(stage/'bin/biocompiler-verify' ,role='verify',expected_sha256=manifest['inputs']['bin/biocompiler-verify']['sha256'],timeout_seconds=300)
    project=ResearchProject.load(stage/'original-project.json');observations=[]
    first=project.verify_bundle(stage/'bundle.zip',verify=verify);observations.append({'name':'reopen-verify','result':first.result})
    second=project.verify_bundle(stage/'bundle.zip',verify=verify);require(second.result==first.result,'Fresh consumer verification changed evidence');observations.append({'name':'repeat-reopen-verify','result':second.result})
    with zipfile.ZipFile(stage/'bundle.zip') as archive:fasta=archive.read('program.fasta');body=archive.read('manifest.json')
    lines=fasta.split(b'\n');lines[3]=b'G'+lines[3][1:]
    changed=stage/'changed-fasta.zip'
    with zipfile.ZipFile(changed,'x',compression=zipfile.ZIP_STORED) as archive:
        for name,raw in (('program.fasta',b'\n'.join(lines)),('manifest.json',body)):
            info=zipfile.ZipInfo(name,(1980,1,1,0,0,0));info.external_attr=0o100644<<16;archive.writestr(info,raw)
    try:project.verify_bundle(changed,verify=verify)
    except ResearchProjectError as error:
        require('exact FASTA/manifest pair' in str(error),'Consumer mutation failed at wrong boundary');observations.append({'name':'changed-fasta','status':'rejected','message':str(error),'bundle':pin(changed)})
    else:raise AssertionError('Changed FASTA accepted')
    request=project.request;request['behavior_request']['original']['source_authority']['project_context']['assumptions'].append('Changed independent caller assumption')
    changed_project=ResearchProject.from_controlled(ControlledWorkflowRequest.from_request(request))
    try:changed_project.verify_bundle(stage/'bundle.zip',verify=verify)
    except ResearchProjectError as error:
        require('original authority differs' in str(error),'Changed original rejected elsewhere');observations.append({'name':'changed-originals','status':'rejected','message':str(error),'project':changed_project.data})
    else:raise AssertionError('Changed independent authority accepted')
    try:verify.call('compile-policy-controlled-workflow',{'request':project.request})
    except CoreRejected as error:
        require(error.response.status=='unsupported' and {d.code for d in error.response.diagnostics}=={'unsupported_operation'},'Verify producer rejection changed');observations.append({'name':'verify-producer','status':'unsupported','diagnostics':[{'code':d.code,'message':d.message,'path':d.path} for d in error.response.diagnostics]})
    else:raise AssertionError('Verify produced a candidate')
    CoreClient.call=original_call
    expected_ops=['capabilities','export-policy-controlled-workflow']*3+['compile-policy-controlled-workflow']
    require([row['operation'] for row in frames]==expected_ops and len(launches)==7,'Consumer native call census differs')
    require(len({row['frame']['request_id'] for row in frames})==7,'Repeated consumer invocation identity')
    for index,row in enumerate(frames):
        if row['operation']=='capabilities':require(row['payload']=={} and row['frame']['status']=='ok','Changed capability invocation')
        else:
            expected={'request':project.request}
            if index<6:expected['candidate']=first.candidate
            require(row['payload']==expected,'Consumer native payload changed independent authority')
            if index<6:require(row['frame']['result']==first.result,'Fresh Verify returned different complete exported evidence')
            else:require(row['frame']['status']=='unsupported','Consumer producer claim changed')
    imports={}
    for name,module in sorted(sys.modules.items()):
        if name=='biocompiler' or name.startswith('biocompiler.'):
            require(name in allowed,'Consumer loaded unreviewed SDK module');path=Path(module.__file__).resolve();require(path.is_relative_to(stage),'Consumer imported outside its stage');imports[name]={'path':str(path),**pin(path)}
    require(tuple(row['name'] for row in observations)==OBSERVATIONS,'Incomplete consumer census')
    for name,expected in manifest['inputs'].items():require(pin(stage/name,256*1024*1024)==expected,'Staged input changed during verification')
    result={'schema_version':'biocompiler.controlled_research_project_consumer.v0.1','status':'passed','acceptance':False,'network':network,
        'scope':'fresh_public_research_project_verify_only_under_supplied_artificial_contracts','producer_absence':{'native_core':'absent_from_staged_tree','actual_python_producers':'absent_from_staged_tree','authority_codecs':'closed_reviewed_original_sdk_files','host_filesystem':'not_isolated','launch_guard':'exact_staged_verify_only'},
        'inputs':manifest['inputs'],'imports':imports,'launches':launches,'native_frames':frames,'observations':observations,'empirical':'unassessed','human_use':'unassessed'}
    (stage/'result.json').write_bytes(canonical(result))


def validate_report(result, *, project, expected_result, sdk_files, verify_pin):
    """Read-only protocol and original-byte checks for the retained consumer."""
    from biocompiler.core_client import _response,_capabilities,encode_json
    from biocompiler.core_policy_controlled_workflow import _result,PROFILE,VALIDATION_SCOPE
    require(result['schema_version']=='biocompiler.controlled_research_project_consumer.v0.1' and result['status']=='passed' and result['acceptance'] is False,'Incomplete consumer result')
    require(tuple(row['name'] for row in result['observations'])==OBSERVATIONS,'Changed consumer observation census')
    require(result['producer_absence']=={'native_core':'absent_from_staged_tree','actual_python_producers':'absent_from_staged_tree','authority_codecs':'closed_reviewed_original_sdk_files','host_filesystem':'not_isolated','launch_guard':'exact_staged_verify_only'},'Consumer scope changed')
    expected_paths=set(MODULE_FILES)|{'consumer.py','network_guard.py','original-project.json','bundle.zip','bin/biocompiler-verify'}
    require(set(result['inputs'])==expected_paths,'Consumer input closure differs')
    for name in MODULE_FILES:require(result['inputs'][name]==sdk_files[name],'Consumer codec differs from original installed package')
    require(result['inputs']['bin/biocompiler-verify']==verify_pin and result['launches']==[verify_pin['sha256']]*7,'Consumer native launch authority differs')
    network=result['network'];require(network['status']=='os_denied' and network['mechanism']=='linux_libseccomp' and network['scope']=='worker_and_descendants' and [row['family'] for row in network['probes']]==['IPv4','IPv6'] and all(type(row['errno']) is int and row['errno'] in (1,13) for row in network['probes']),'Consumer lacks kernel network denial evidence')
    allowed={module_name(path):path for path in MODULE_FILES}
    require('biocompiler.policy.research_project' in result['imports'],'Consumer omitted public project route')
    require(type(result['command']) is list and len(result['command'])==7 and result['command'][1:4]==['-I','-S','-B'] and result['command'][-2]=='--worker','Consumer worker command changed')
    stage=Path(result['command'][-1]);require(stage.is_absolute() and result['command'][4]==str(stage/'consumer.py'),'Consumer worker stage changed')
    for name,row in result['imports'].items():
        require(name in allowed and row['path']==str(stage/allowed[name]),'Consumer import escaped staged closure')
        require(name in allowed and {key:row[key] for key in ('sha256','bytes')}==sdk_files[allowed[name]],'Unexpected or changed consumer import')
    rows=result['native_frames'];operations=['capabilities','export-policy-controlled-workflow']*3+['compile-policy-controlled-workflow']
    require([row['operation'] for row in rows]==operations and len({row['frame']['request_id'] for row in rows})==7,'Changed consumer native action census')
    for index,row in enumerate(rows):
        frame=row['frame'];raw=encode_json(frame,limit=16*1024*1024)
        require(hashlib.sha256(raw).hexdigest()==row['response_sha256'],'Retained consumer wire changed')
        response=_response(raw,{'ok':0,'error':2,'unsupported':3}[frame['status']],frame['request_id'],operations[index],'verify')
        if operations[index]=='capabilities':
            require(row['payload']=={} and response.status=='ok','Capability action differs')
            caps=_capabilities(response.result);caps.require_operation('export-policy-controlled-workflow')
            require(caps.profiles.get('policy_controlled_workflow')==PROFILE and VALIDATION_SCOPE in caps.validation_scopes,'Consumer negotiated different Verify profile')
        else:
            payload={'request':project['request']}
            if index<6:payload['candidate']=expected_result['candidate']
            require(row['payload']==payload,'Consumer action original authority differs')
            if index<6:
                _result(response,payload);require(response.result==expected_result,'Fresh Verify result differs')
            else:require(response.status=='unsupported' and {d.code for d in response.diagnostics}=={'unsupported_operation'},'Verify acquired producer')
    observations=result['observations']
    require(observations[0]['result']==observations[1]['result']==expected_result,'Retained public fresh reopens differ')
    require(observations[2]['status']=='rejected' and 'exact FASTA/manifest pair' in observations[2]['message'],'FASTA mutation failed elsewhere')
    changed=json.loads(canonical(project));changed['request']['behavior_request']['original']['source_authority']['project_context']['assumptions'].append('Changed independent caller assumption');changed['assumptions'].append('Changed independent caller assumption')
    require(observations[3]['status']=='rejected' and 'original authority differs' in observations[3]['message'] and observations[3]['project']==changed,'Independent-original control differs')
    require(observations[4]=={'name':'verify-producer','status':'unsupported','diagnostics':rows[-1]['frame']['diagnostics']},'Producer control differs from exact native diagnostics')
    require(result['empirical']==result['human_use']=='unassessed','Consumer promoted empirical claim')
    return result


def run_stage(*,package,verify,project,bundle,stage,output,expected_verify_sha256):
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted' and sys.platform=='linux','Native consumer is hosted Linux only')
    stage=Path(stage).absolute();require(not stage.exists() and not stage.is_relative_to(ROOT),'Use new outside-checkout consumer stage')
    stage.mkdir();files={}
    for name in MODULE_FILES:files[name]=Path(package).parent/name
    files.update({'consumer.py':Path(__file__),'network_guard.py':ROOT/'tools/check_policy_material_consumer.py','original-project.json':Path(project),'bundle.zip':Path(bundle),'bin/biocompiler-verify':Path(verify)})
    for name,source in files.items():
        destination=stage/name;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,destination)
    (stage/'bin/biocompiler-verify').chmod(0o700)
    inputs={name:pin(stage/name,256*1024*1024) for name in files}
    require(inputs['bin/biocompiler-verify']['sha256']==expected_verify_sha256,'Consumer native identity differs')
    (stage/'authority.json').write_bytes(canonical({'module_files':MODULE_FILES,'inputs':inputs}))
    command=[sys.executable,'-I','-S','-B',str(stage/'consumer.py'),'--worker',str(stage)]
    log=Path(output).with_suffix('.log')
    with log.open('xb') as stream:completed=subprocess.run(command,cwd=stage,stdout=stream,stderr=subprocess.STDOUT,timeout=600,check=False)
    require(completed.returncode==0,'Verify-only consumer failed; retain '+str(log))
    result=json.loads((stage/'result.json').read_bytes());require(result['status']=='passed' and result['inputs']==inputs,'Consumer returned incomplete or foreign authority')
    result['command']=command;result['log_pin']=log_pin(log);result['authority_pin']=pin(stage/'authority.json')
    Path(output).write_bytes(canonical(result));return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--worker',type=Path,required=True);worker(parser.parse_args().worker)
