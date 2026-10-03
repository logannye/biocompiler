"""Fail-closed final accounting for both wheels and all four fresh installed slots."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

if __package__:
    from . import build_prebuilt_core as build,prebuilt_release_pipeline as pipeline
else:
    import build_prebuilt_core as build
    import prebuilt_release_pipeline as pipeline

require=build.require
SLOTS={f'{target}-py{python}':(target,python) for target in build.TARGETS for python in ('3.11','3.14')}


def validate_slot(receipt,expected,platform,minor,candidate,read):
    require(type(receipt) is dict and receipt.get('status')=='pass' and all(receipt.get(k)==v for k,v in expected.items()),'Installed slot is incomplete or stale')
    require(receipt['native_platform']==platform and receipt['python_version'].split()[0].startswith(minor+'.'),'Installed slot runtime differs')
    before=receipt['ownership_before'];after=receipt['ownership_after']
    require(before==after and all(before[k]==v for k,v in expected.items()),'Installed ownership changed or is stale')
    require(before['native_platform']==platform and before['distribution_sha256']==candidate['release']['platforms'][platform], 'Installed wheel is detached from reviewed SDK pin')
    manifest=candidate['distributions'][platform]
    require(hashlib.sha256(build.canonical(manifest)).hexdigest()==before['distribution_sha256']
        and set(before['files'])==set(manifest['files']), 'Owned manifest/member census differs from candidate')
    for name,pin in manifest['files'].items():
        owned=before['files'][name]
        require(owned=={'path':str(Path(before['package_root'])/name),**pin}, 'Owned file differs from independently verified candidate')
    require(before['release_sha256']==hashlib.sha256(build.canonical(candidate['release'])).hexdigest(), 'Owned SDK release pin bytes differ')
    require([row['name'] for row in receipt['campaigns']]==[name for _,name in pipeline.CAMPAIGNS], 'Full installed campaign census differs')
    for row in receipt['campaigns']:
        raw=read(row['name']+'.json')
        require(hashlib.sha256(raw).hexdigest()==row['receipt_sha256'],'Installed campaign receipt bytes differ')
    commands=receipt['commands']
    names=['create-environment','install','smoke','uninstall','missing-package','reinstall']+[name for _,name in pipeline.CAMPAIGNS]
    require(len(commands)==len(names),'Hosted command census differs')
    for row,name in zip(commands,names):
        require(type(row) is dict and set(row)=={'argv','cwd','returncode','log'} and row['returncode']==0
            and type(row['returncode']) is int and Path(row['cwd']).is_absolute(),'Hosted command outcome differs')
        require(row['log']['path']==name+'.log','Hosted command log belongs to another phase')
        raw=read(name+'.log')
        require(row['log']['size']==len(raw) and row['log']['sha256']==hashlib.sha256(raw).hexdigest(),'Hosted command log bytes differ')
    install=commands[1]['argv'];reinstall=commands[5]['argv']
    require(len(install)==11 and type(install) is list, 'Installed wheel command is incomplete')
    require(install==reinstall and install[1:6]==['-m','pip','--python',install[4],'install']
        and install[6:9]==['--no-index','--no-deps','--only-binary=:all:'],'Installed slot permits package resolution or source fallback')
    python=Path(install[4]);sdk=Path(install[9]);native=Path(install[10])
    require(install==pipeline.install_plan(Path(install[0]),python,sdk,native),'Installed wheel names or command differ')
    checkout=Path(commands[2]['argv'][2]).parent.parent
    wanted=pipeline.campaign_plan(checkout,python,before,Path(commands[6]['argv'][-1]).parent)
    require([row['argv'] for row in commands[6:]]==[command for _,command in wanted], 'Campaign command differs from exact owned-path recipe')
    output=Path(commands[6]['argv'][-1]).parent
    lifecycle=pipeline.lifecycle_plan(Path(install[0]),python,checkout,output,sdk,native,expected)
    require([row['argv'] for row in commands[:6]]==[command for _,command in lifecycle], 'Installed lifecycle command differs from exact source recipe')
    require([row['cwd'] for row in commands]==[str(output)]+[str(python.parent.parent)]*(len(commands)-1),
        'Installed commands did not execute in the fresh isolated directories')
    # Mandatory smoke contains actual two-role paths and fresh process lifecycle.
    smoke=json.loads(read('smoke.json'))
    require(all(smoke[key]==value for key,value in expected.items()) and smoke['python_version'].startswith(minor+'.'), 'Smoke authority differs')
    for role in ('core','verify'):
        pin=before['files']['bin/biocompiler-'+role]
        require(smoke['roles'][role]=={'path':pin['path'],'sha256':pin['sha256']},'Smoke did not run the owned final role')
    require(smoke['process_lifecycle']['reaped'] is True and smoke['process_lifecycle']['attempts']==1,'Started process cancellation is incomplete')
    return {'native_platform':platform,'python_minor':minor,'ownership':before,'campaigns':receipt['campaigns']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True);parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--needs',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    for key in ('source-revision','tested-revision','run-id'):parser.add_argument('--'+key,required=True)
    args=parser.parse_args();expected={key:getattr(args,key) for key in ('source_revision','tested_revision','run_id')}
    needs=json.loads(args.needs.read_bytes())
    require(set(needs)=={'ocaml-core','prebuilt-core-assembly','realization-conformance','realization-core-reproducibility'}
        and all(row['result']=='success' for row in needs.values()),'Prebuilt release has missing, skipped or failed required jobs')
    candidate=json.loads(args.candidate.read_bytes())
    require(candidate['status']=='pass' and candidate['sdk'] is not None and all(candidate[k]==v for k,v in expected.items()),'Candidate wheel/SDK validation missing')
    require({path.name for path in args.root.iterdir()}==set(SLOTS),'Fresh installed four-runtime directory census differs')
    results={}
    for name,(target,minor) in SLOTS.items():
        root=args.root/name;receipt=json.loads((root/'installed-release.json').read_bytes())
        results[name]=validate_slot(receipt,expected,target,minor,candidate,lambda name:(root/name).read_bytes())
    require(results['linux-x86_64-py3.11']['ownership']['distribution_sha256']==results['linux-x86_64-py3.14']['ownership']['distribution_sha256']
        and results['macos-arm64-py3.11']['ownership']['distribution_sha256']==results['macos-arm64-py3.14']['ownership']['distribution_sha256'],'Same-platform native wheel identity differs')
    result={'schema_version':'biocompiler.prebuilt_release_validation.v1','status':'pass',**expected,
        'candidate_sha256':hashlib.sha256(args.candidate.read_bytes()).hexdigest(),'slots':results,'needs':needs,
        'scope':'internal release artifacts; publishing and default semantic cutover are separate'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(build.canonical(result))


if __name__=='__main__':main()
