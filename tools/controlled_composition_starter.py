"""Bounded editable RC6 development starter from this same installed rehearsal.

This copies an already built SDK and exact native executables. It performs no
installation or native execution and is not the four-slot RC7 release gate.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import tempfile
try:
    from . import check_controlled_research_project as campaign
    from . import check_controlled_research_project_installed as installed
except ImportError:
    import check_controlled_research_project as campaign
    import check_controlled_research_project_installed as installed

ROOT=Path(__file__).resolve().parents[1]
SOURCE_FILES=(*campaign.INPUTS,'docs/controlled-composition-quickstart.md')
MAX_FILE=128*1024*1024
MAX_TOTAL=512*1024*1024
require=campaign.require


def stage_editable_inputs(packet,destination):
    """Copy editable originals without asserting native acceptance or installing."""
    destination=Path(destination)
    require(not destination.exists() and destination.parent.is_dir() and not destination.parent.is_symlink(),'Use a new editable starter directory')
    destination.mkdir()
    for name in campaign.INPUTS:
        path=destination/name;path.parent.mkdir(parents=True,exist_ok=True)
        source=packet['root']/name;require(campaign.file_pin(source)==packet['pins'][name],'Editable original changed before copy')
        shutil.copyfile(source,path);require(campaign.file_pin(path)==packet['pins'][name],'Editable starter copy differs')
    manifest={'schema_version':'biocompiler.controlled_composition_editable_inputs.v0.1','native_status':'not_run','files':packet['pins']}
    (destination/'editable-inputs.json').write_bytes(campaign.canonical(manifest))
    return manifest


def plan(*,root,receipt_path,sdk_wheel,binaries):
    """Validate retained bytes and prepare an exact copy census, without execution."""
    root=Path(root);receipt_path=Path(receipt_path);sdk_wheel=Path(sdk_wheel)
    receipt=campaign.load(receipt_path);folder=receipt_path.with_suffix('')
    installed.validate_retained(receipt,folder,root=root)
    require(receipt['sdk_wheel']=={'name':sdk_wheel.name,**campaign.file_pin(sdk_wheel,MAX_FILE)},'Starter SDK differs from installed wheel')
    files={name:root/name for name in SOURCE_FILES}
    files.update({'wheels/'+sdk_wheel.name:sdk_wheel,'evidence/installed.json':receipt_path})
    for role in ('core','verify'):
        require(campaign.file_pin(binaries[role],MAX_FILE)=={key:receipt['binaries'][role][key] for key in ('sha256','bytes')},'Starter native differs from installed rehearsal')
        files['bin/biocompiler-'+role]=Path(binaries[role])
    for name in receipt['files']:files['evidence/installed/'+name]=folder/name
    # Empty diagnostic logs are preserved as bytes too.
    for name in receipt['empty_logs']:files['evidence/installed/'+name]=folder/name
    for case in campaign.CASE_IDS:
        files['projects/'+case+'.json']=folder/'rehearsal'/(case+'-project.json')
        if case in campaign.ACCEPTED:files['accepted/'+case+'.zip']=folder/'rehearsal'/(case+'.zip')
    metadata={}
    import hashlib
    for name,path in files.items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and not path.is_symlink() and path.is_file(),'Unsafe starter path')
        require(0<=path.stat().st_size<=MAX_FILE,'Oversized starter file')
        raw=path.read_bytes();require(len(raw)<=MAX_FILE,'Starter file grew beyond bound')
        metadata[name]={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}
    require(sum(row['bytes'] for row in metadata.values())<=MAX_TOTAL,'Starter exceeds total byte bound')
    for name in SOURCE_FILES:
        original=receipt['native_authority']['sources'][name]
        require(metadata[name]=={'sha256':original['sha256'],'bytes':original['size']},'Starter source differs from the fresh native source snapshot')
    manifest={'schema_version':'biocompiler.controlled_composition_starter.v0.1','status':'installed_development_candidate',
        'identity':receipt['identity'],'native_authority':receipt['native_authority'],'slot':['Linux','x86_64','3.11'],
        'scope':'artificial_two_rna_joined_workflow_only','rc7_four_slot_acceptance':'not_performed',
        'empirical_status':'unassessed','human_use':'unassessed','therapeutic_export':'withheld',
        'files':metadata,'entrypoint':'docs/controlled-composition-quickstart.md','editable_originals':list(campaign.CASE_IDS)}
    return files,manifest


def create(args):
    require(os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ENVIRONMENT')=='github-hosted','Starter assembly is hosted-only')
    destination=Path(args.output).absolute();require(not destination.exists() and destination.parent.is_dir() and not destination.parent.is_symlink(),'Use a fresh starter destination')
    binaries={role:Path(getattr(args,role)).absolute() for role in ('core','verify')}
    authority=campaign.native_authority(binaries)
    files,manifest=plan(root=ROOT,receipt_path=args.installed_receipt,sdk_wheel=args.sdk_wheel,binaries=binaries)
    require(manifest['native_authority']==authority and manifest['identity']==campaign.source_identity(),'Starter differs from this complete same-run native/installed authority')
    with tempfile.TemporaryDirectory(prefix='.controlled-starter-',dir=destination.parent) as temporary:
        staged=Path(temporary)/'starter';staged.mkdir()
        for name,source in files.items():
            target=staged/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
            target.chmod(0o700 if name.startswith('bin/') else 0o600)
        (staged/'starter-manifest.json').write_bytes(campaign.canonical(manifest))
        import hashlib
        for name,pin in manifest['files'].items():
            raw=(staged/name).read_bytes();require(pin=={'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)},'Staged starter bytes changed')
        campaign.unchanged_authority(authority,binaries)
        require(not destination.exists(),'Starter destination appeared during staging')
        staged.rename(destination)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('installed-receipt','sdk-wheel','core','verify','output'):parser.add_argument('--'+name,type=Path,required=True)
    create(parser.parse_args())

if __name__=='__main__':main()
