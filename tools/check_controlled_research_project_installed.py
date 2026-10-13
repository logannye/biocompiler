"""One hosted installed RC6 rehearsal outside the checkout, without installation.

The caller installs the exact current SDK wheel once in its existing runtime.
This runner authenticates installed bytes, copies inputs and native executables,
and delegates all semantic checking to the public example and fresh Core/Verify.
The complete four-platform/package acceptance remains a separate RC7 gate.
"""
from __future__ import annotations
import argparse
import base64
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile
try:
    from . import check_controlled_research_project as campaign
    from . import check_controlled_research_project_consumer as consumer
except ImportError:
    import check_controlled_research_project as campaign
    import check_controlled_research_project_consumer as consumer

ROOT=Path(__file__).resolve().parents[1]
SCHEMA='biocompiler.controlled_research_project_installed.v0.1'
require,file_pin,canonical=campaign.require,campaign.file_pin,campaign.canonical


def package_files(package):
    package=Path(package)
    result={}
    for path in sorted(package.rglob('*')):
        require(not path.is_symlink(),'Redirected package entry')
        if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':
            result['biocompiler/'+path.relative_to(package).as_posix()]=path
    return result


def installed_wheel(wheel, *, root=ROOT):
    import biocompiler
    package=Path(biocompiler.__file__).resolve().parent
    require(not package.is_relative_to(root),'Installed SDK resolved to checkout')
    distribution=metadata.distribution('biocompiler')
    records={Path(distribution.locate_file(row)).resolve():row for row in distribution.files or ()}
    source=package_files(root/'src/biocompiler');installed=package_files(package)
    require(set(source)==set(installed),'Installed/source package file census differs')
    result={}
    with zipfile.ZipFile(wheel) as archive:
        names=archive.namelist();require(len(names)==len(set(names)),'Duplicate SDK wheel members')
        members={name for name in names if name.startswith('biocompiler/') and not name.endswith('/')}
        require(members==set(source),'Wheel/source package file census differs')
        require(sum(row.file_size for row in archive.infolist())<=128*1024*1024,'Expanded SDK wheel too large')
        for name in sorted(members):
            relative=Path(name);require(not relative.is_absolute() and '..' not in relative.parts,'Unsafe wheel path')
            info=archive.getinfo(name);require(0<=info.file_size<=16*1024*1024,'Oversized wheel package file')
            path=installed[name];require(path.stat().st_size==info.file_size and source[name].stat().st_size==info.file_size,'Package file size differs')
            raw=archive.read(name);require(raw==path.read_bytes()==source[name].read_bytes(),'Wheel, installed and original source package bytes differ')
            actual={'sha256':__import__('hashlib').sha256(raw).hexdigest(),'bytes':len(raw)}
            record=records.get(path.resolve());require(record is not None and record.hash is not None and record.hash.mode=='sha256' and record.size==len(raw),'Installed file missing complete RECORD')
            require(record.hash.value==base64.urlsafe_b64encode(bytes.fromhex(actual['sha256'])).decode().rstrip('='),'Installed RECORD hash differs')
            result[name]=actual
    require('biocompiler/policy/research_project.py' in result and 'biocompiler/core_policy_controlled_workflow.py' in result,'Wheel omits public controlled workflow')
    return {'package':str(package),'distribution':distribution.version,'files':result}


def validate_retained(receipt, folder, *, root=ROOT):
    folder=Path(folder)
    require(receipt['schema_version']==SCHEMA and receipt['status']=='passed' and receipt['acceptance'] is False and receipt['rc7_four_slot_acceptance']=='not_performed','Incomplete installed rehearsal')
    require(receipt['scope']=='single_hosted_installed_public_workflow_rehearsal_only' and receipt['empirical']==receipt['human_use']=='unassessed' and receipt['host_filesystem']=='not_isolated','Installed scope changed')
    paths={str(path.relative_to(folder)):path for path in folder.rglob('*') if path.is_file()}
    require(set(paths)==set(receipt['files'])|set(receipt['empty_logs']),'Installed evidence file census differs')
    for name,value in receipt['files'].items():require(file_pin(paths[name])==value,'Installed retained file changed')
    for name in receipt['empty_logs']:require(name.endswith('.log') and paths[name].stat().st_size==0,'Invalid empty log')
    require(campaign.load(folder/'editable-inputs.json')==receipt['editable_starter']=={'schema_version':'biocompiler.controlled_composition_editable_inputs.v0.1','native_status':'not_run','files':receipt['inputs']},'Editable starter original manifest differs')
    rehearsal=campaign.load(folder/'rehearsal.json');values=campaign.validate_receipt(rehearsal,folder/'rehearsal',root=root)
    expected_paths={'rehearsal/'+name for name in rehearsal['files']}|{'editable-inputs.json','rehearsal.json','rehearsal.log','consumer.json','consumer.log','consumer-stage/authority.json','consumer-stage/result.json','consumer-stage/changed-fasta.zip'}
    require(set(paths)==expected_paths,'Installed evidence differs from fixed complete file census')
    require(rehearsal['installed'] is True and rehearsal['identity']==receipt['identity']==receipt['final_source_identity'] and rehearsal['native_authority']==receipt['native_authority'],'Installed/source/native original identity differs')
    require(receipt['inputs']==rehearsal['inputs']==campaign.checked_assets(root)['pins'] and receipt['rehearsal']==rehearsal['rehearsal'],'Installed original/timing receipt differs')
    for role,pin in rehearsal['binaries'].items():require(pin=={key:receipt['binaries'][role][key] for key in ('sha256','bytes')},'Child binary identity differs')
    sources=package_files(root/'src/biocompiler');require(set(sources)==set(receipt['installed_sdk']['files']),'Installed original SDK census changed')
    import hashlib
    for name,path in sources.items():
        raw=path.read_bytes();require(receipt['installed_sdk']['files'][name]=={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)},'Retained SDK source identity changed')
    saved=campaign.load(folder/'consumer.json');require(saved==receipt['consumer'],'Consumer receipt substituted')
    require(saved['log_pin']==consumer.log_pin(folder/'consumer.log') and saved['authority_pin']==file_pin(folder/'consumer-stage/authority.json'),'Consumer log/authority pin changed')
    for target,source in (('original-project.json',folder/'rehearsal/baseline-project.json'),('bundle.zip',folder/'rehearsal/baseline.zip')):
        require(saved['inputs'][target]==file_pin(source),'Consumer original project/pair differs')
    for target,source in (('consumer.py','tools/check_controlled_research_project_consumer.py'),('network_guard.py','tools/check_policy_material_consumer.py')):
        pin=receipt['native_authority']['sources'][source];require(saved['inputs'][target]=={'sha256':pin['sha256'],'bytes':pin['size']},'Consumer script differs from same-run original source')
    consumer.validate_report(saved,project=values['baseline-prepared']['project'],expected_result=values['baseline-export'],sdk_files=receipt['installed_sdk']['files'],verify_pin=rehearsal['binaries']['verify'])
    require(campaign.load(folder/'consumer-stage/result.json')=={key:value for key,value in saved.items() if key not in ('command','log_pin','authority_pin')},'Consumer worker result substituted')
    authority=campaign.load(folder/'consumer-stage/authority.json');require(tuple(authority['module_files'])==consumer.MODULE_FILES and authority['inputs']==saved['inputs'],'Consumer stage authority differs')
    from biocompiler.policy.material import _verify_staged
    from biocompiler.core_client import encode_json
    artifact=values['baseline-export']['artifact'];lines=artifact['fasta'].encode().split(b'\n');lines[3]=b'G'+lines[3][1:]
    mutation=folder/'consumer-stage/changed-fasta.zip';_verify_staged(mutation,(('program.fasta',b'\n'.join(lines)),('manifest.json',encode_json(artifact['manifest']))))
    require(saved['observations'][2]['bundle']==file_pin(mutation),'Consumer altered pair pin differs')
    return values


def run(args):
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted','Installed rehearsal is hosted-only')
    require(sys.version_info[:2]==(3,11) and sys.platform=='linux','RC6 development rehearsal uses the current hosted Linux Python3.11 slot')
    work=Path(args.work_dir).absolute();output=Path(args.output).absolute();wheel=Path(args.sdk_wheel).absolute();folder=output.with_suffix('')
    require(not work.exists() and not work.is_relative_to(ROOT) and work.parent.is_dir() and not work.parent.is_symlink(),'Use a new outside-checkout working directory')
    require(not output.exists() and not folder.exists() and output.parent.is_dir() and not output.parent.is_symlink(),'Use a new installed evidence receipt')
    sources=campaign.checked_assets();identity=campaign.source_identity();wheel_pin=file_pin(wheel,128*1024*1024)
    original_binaries={role:Path(getattr(args,role)).absolute() for role in ('core','verify')}
    authority=campaign.native_authority(original_binaries)
    if args.sdk_sha256 is not None:require(wheel_pin['sha256']==args.sdk_sha256,'Supplied SDK wheel digest differs')
    owned=installed_wheel(wheel);work.mkdir();inputs=work/'inputs';native=work/'native';native.mkdir();evidence=work/'evidence';evidence.mkdir()
    started=time.monotonic_ns()
    receipt={'schema_version':SCHEMA,'status':'incomplete','acceptance':False,'scope':'single_hosted_installed_public_workflow_rehearsal_only',
        'rc7_four_slot_acceptance':'not_performed','identity':identity,'native_authority':authority,'sdk_wheel':{'name':wheel.name,**wheel_pin},'installed_sdk':owned,
        'working_directory':str(work),'inputs':sources['pins'],'files':{},'empirical':'unassessed','human_use':'unassessed',
        'installation_timing':'excluded','human_usability':'unassessed','host_filesystem':'not_isolated'}
    try:
        try:
            from . import controlled_composition_starter as starter
        except ImportError:
            import controlled_composition_starter as starter
        receipt['editable_starter']=starter.stage_editable_inputs(sources,inputs)
        shutil.copyfile(inputs/'editable-inputs.json',evidence/'editable-inputs.json')
        binaries={}
        for role,original in original_binaries.items():
            pin=file_pin(original,128*1024*1024)
            require(getattr(args,role+'_sha256') in (None,pin['sha256']),'Supplied native executable digest differs')
            destination=native/('biocompiler-'+role);shutil.copyfile(original,destination);destination.chmod(0o700);require(file_pin(destination,128*1024*1024)==pin,'Copied native differs');binaries[role]={'path':str(destination),**pin}
        receipt.update(binaries=binaries,runtime_inputs={name:{'path':str(inputs/name),**value} for name,value in sources['pins'].items()})
        env={key:value for key,value in os.environ.items() if key not in ('PYTHONPATH','PYTHONHOME')};env['PYTHONNOUSERSITE']='1';env['PYTHONDONTWRITEBYTECODE']='1'
        command=[sys.executable,'-B',str(ROOT/'tools/check_controlled_research_project.py'),'--inputs-root',str(inputs),'--require-installed','--output',str(evidence/'rehearsal.json')]
        for role in binaries:command+=['--'+role,binaries[role]['path'],'--'+role+'-sha256',binaries[role]['sha256']]
        receipt['command']=command
        with (evidence/'rehearsal.log').open('xb') as stream:result=subprocess.run(command,cwd=work,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=2400,check=False)
        receipt['returncode']=result.returncode
        require(result.returncode==0,'Installed public rehearsal failed; see retained rehearsal.log')
        rehearsal=campaign.load(evidence/'rehearsal.json')
        require(rehearsal['installed'] is True and rehearsal['identity']==identity and rehearsal['native_authority']==authority,'Installed child identity differs')
        campaign.validate_receipt(rehearsal,evidence/'rehearsal')
        receipt['rehearsal']=rehearsal['rehearsal']
        receipt['consumer']=consumer.run_stage(package=Path(owned['package']),verify=Path(binaries['verify']['path']),
            project=evidence/'rehearsal/baseline-project.json',bundle=evidence/'rehearsal/baseline.zip',
            stage=work/'verify-only',output=evidence/'consumer.json',expected_verify_sha256=binaries['verify']['sha256'])
        require(installed_wheel(wheel)==owned and file_pin(wheel,128*1024*1024)==wheel_pin,'Installed SDK ownership changed')
        require(campaign.checked_assets()['pins']==sources['pins'] and campaign.source_identity()==identity,'Current original/source identity changed')
        require({name:file_pin(inputs/name) for name in campaign.INPUTS}==sources['pins'],'Copied original changed during installed rehearsal')
        for role,row in binaries.items():require(file_pin(Path(row['path']),128*1024*1024)=={key:row[key] for key in ('sha256','bytes')},'Copied native changed during installed rehearsal')
        campaign.unchanged_authority(authority,original_binaries);receipt['final_source_identity']=campaign.source_identity();receipt['status']='passed'
    except Exception as error:
        receipt.update(status='failed',error=type(error).__name__+': '+str(error));raise
    finally:
        # Copy evidence before propagating any child failure: outside-checkout logs
        # would otherwise be absent from the workflow's always-upload directory.
        if (work/'verify-only').exists():
            target=evidence/'consumer-stage';target.mkdir(exist_ok=True)
            for name in ('authority.json','result.json','changed-fasta.zip'):
                path=work/'verify-only'/name
                if path.is_file() and not path.is_symlink():shutil.copyfile(path,target/name)
        shutil.copytree(evidence,folder)
        receipt['files']={str(path.relative_to(folder)):file_pin(path) for path in sorted(folder.rglob('*')) if path.is_file() and path.stat().st_size>0}
        receipt['empty_logs']=[str(path.relative_to(folder)) for path in sorted(folder.rglob('*.log')) if path.is_file() and path.stat().st_size==0]
        receipt['elapsed_ns']=time.monotonic_ns()-started
        output.write_bytes(canonical(receipt))
    try:validate_retained(receipt,folder)
    except Exception as error:
        receipt.update(status='failed',error=type(error).__name__+': '+str(error));output.write_bytes(canonical(receipt));raise
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('sdk-wheel','core','verify','work-dir','output'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('sdk','core','verify'):parser.add_argument('--'+name+'-sha256')
    run(parser.parse_args())

if __name__=='__main__':main()
