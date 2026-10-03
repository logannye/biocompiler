"""Run/source/binary authority for installed reference workflow replay.

Each successful native receipt is independently reconstructed with its Python
minor. Reconstruction emits only recorded server bytes and never replaces the
real native process or independent checker authority.
"""
from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time

if __package__:
    from . import check_pipeline_reference_install as gate
else:
    import check_pipeline_reference_install as gate

manager, r, ROOT = gate.manager, gate.manager.r, gate.ROOT
require, equal, canonical, sha = gate.require, gate.equal, gate.canonical, gate.sha
SCOPE = 'unchanged18_reference_methods_complete_public_native_process_callback_and_object_receipts'
SOURCE = 'tools/pipeline_reference_runtime.py'
TEST_SOURCE = 'tests/test_pipeline_reference_runtime.py'


def product_sources(corpus):
    paths = set(path for path in corpus.index['source_files'] if path.startswith('src/'))
    paths.update(manager.python_sources())
    paths.update(path for path in gate.SOURCES if path.startswith('src/'))
    return r.source_pins(paths)


def campaign_sources():
    return r.source_pins(tuple(dict.fromkeys((*gate.SOURCES, SOURCE, TEST_SOURCE))))


def metadata(corpus):
    return {**corpus.metadata(), 'declarations': r.source_pins((manager.CHANNEL_PATH, manager.APPLICATION_PATH))}


def installed_sources(sources):
    import biocompiler
    package = Path(biocompiler.__file__).resolve().parent
    require(not package.is_relative_to(ROOT), 'Reference campaign loaded checkout product code')
    for logical, identity in sources.items():
        require(logical.startswith('src/biocompiler/') and '..' not in Path(logical).parts,
                'Reference installed source escaped package')
        path = package / logical.removeprefix('src/biocompiler/')
        require(sha(r.raw_file(path)) == identity, 'Installed reference source differs: '+logical)
    for name, module in tuple(sys.modules.items()):
        if name == 'biocompiler' or name.startswith('biocompiler.'):
            path = Path(module.__file__).resolve()
            require(path.is_relative_to(package), 'Reference execution mixed product package origins')
            logical = 'src/biocompiler/' + path.relative_to(package).as_posix()
            require(logical in sources and sha(r.raw_file(path)) == sources[logical],
                    'Loaded reference module lacks current source authority: '+name)
    return str(package / '__init__.py')


def authority(receipt, corpus, native, *, revision, source_revision, run_id, target, python, allow_running=False):
    require(type(revision) is str and re.fullmatch('[0-9a-f]{40}',revision)
        and type(source_revision) is str and re.fullmatch('[0-9a-f]{40}',source_revision)
        and type(run_id) is str and run_id, 'Missing current reference run authority')
    require(target in r.PLATFORMS and python in r.PYTHONS, 'Unknown reference runtime slot')
    system,machine=r.PLATFORMS[target]
    wanted={'schema_version':gate.SCHEMA, 'execution_kind':'installed-native', 'scope':SCOPE,
        'revision':revision, 'source_revision':source_revision, 'run_id':run_id,
        'native_platform':target, 'system':system, 'machine':machine,
        'native_inputs':native, 'python_sources':product_sources(corpus), 'campaign_sources':campaign_sources(),
        'artifact_directory':gate.ARTIFACT_DIRECTORY, **metadata(corpus)}
    for key,value in wanted.items():
        equal(receipt.get(key),value,'Stale or mixed reference authority: '+key)
    require(receipt.get('status') in (('running','success') if allow_running else ('success',))
        and type(receipt.get('python_version')) is str
        and receipt['python_version'].startswith(python+'.'), 'Reference runtime status/version differs')
    require(type(receipt.get('package_path')) is str and Path(receipt['package_path']).is_absolute()
        and not Path(receipt['package_path']).is_relative_to(ROOT), 'Reference package was not installed')
    paths=receipt.get('executables')
    require(type(paths) is dict and set(paths)=={'core','verify'}
        and all(type(value) is str and Path(value).is_absolute() and Path(value).name=='biocompiler-'+role
            for role,value in paths.items())
        and Path(paths['core']).parent==Path(paths['verify']).parent, 'Reference executable selection is incomplete')
    return wanted


def campaign_main(argv):
    parser=argparse.ArgumentParser(description=__doc__)
    for role in ('core','verify'):
        parser.add_argument('--'+role,type=Path,required=True)
        parser.add_argument('--'+role+'-sha256',required=True)
    parser.add_argument('--native-root',type=Path,required=True)
    parser.add_argument('--platform',choices=r.PLATFORMS,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    import biocompiler
    from biocompiler.core_client import CoreClient
    guard=gate.tool('reference_execution_guard')
    corpus=gate.Corpus()
    sources=product_sources(corpus)
    directory=args.output.with_name(gate.ARTIFACT_DIRECTORY)
    directory.mkdir(parents=True,exist_ok=True)
    require(not directory.is_symlink() and not any(directory.iterdir()), 'Unsafe or nonempty reference evidence directory')
    receipt={'schema_version':gate.SCHEMA,'execution_kind':'installed-native','status':'running','scope':SCOPE,
        **metadata(corpus),'revision':os.environ.get('GITHUB_SHA'),
        'source_revision':os.environ.get('GITHUB_HEAD_SHA',os.environ.get('GITHUB_SHA')),
        'run_id':os.environ.get('GITHUB_RUN_ID'),'python_version':platform.python_version(),
        'system':platform.system(),'machine':platform.machine(),'native_platform':args.platform,
        'package_path':str(Path(biocompiler.__file__).resolve()),'artifact_directory':gate.ARTIFACT_DIRECTORY,
        'artifacts':{},'_artifact_directory':str(directory),'python_sources':sources,'campaign_sources':campaign_sources()}
    started=time.monotonic(); code=1
    try:
        require(not Path.cwd().resolve().is_relative_to(ROOT),'Run installed reference replay outside checkout')
        require((platform.system(),platform.machine())==r.PLATFORMS[args.platform], 'Reference native process platform differs')
        installed_sources(sources)
        native=r.verify_binaries(args.native_root,receipt['revision'],args.platform)
        receipt['native_inputs'],receipt['executables']=native,{}
        for role in ('core','verify'):
            path,pin=getattr(args,role),getattr(args,role+'_sha256')
            require(path.is_absolute() and path.resolve()==(args.native_root/('biocompiler-'+role)).resolve()
                and not path.is_symlink() and os.access(path,os.X_OK) and pin==native['sha256'][path.name],
                'Unbound actual reference native binary')
            receipt['executables'][role]=str(path)
        authority(receipt,corpus,native,revision=receipt['revision'],source_revision=receipt['source_revision'],
            run_id=receipt['run_id'],target=args.platform,python='.'.join(map(str,sys.version_info[:2])),allow_running=True)
        client=CoreClient(args.core,role='core',expected_sha256=args.core_sha256,timeout_seconds=300)
        manager.verify_rejection(args.verify,args.verify_sha256,receipt)
        gate.run_observed(client,corpus,receipt,guard=guard.execution)
        installed_sources(sources)
        artifacts=manager.Artifacts(directory,dict(receipt['artifacts']))
        reconstruction=gate.reconstruct(receipt,corpus,artifacts,retain=lambda raw:manager.artifact(receipt,raw))
        receipt['reconstruction']=manager.artifact(receipt,canonical(reconstruction))
        gate.validate_complete(receipt,corpus,manager.Artifacts(directory,receipt['artifacts']))
        equal(r.verify_binaries(args.native_root,receipt['revision'],args.platform),native,'Reference binaries changed during execution')
        equal(product_sources(corpus),sources,'Reference current product sources changed during execution')
        equal(campaign_sources(),receipt['campaign_sources'],'Reference campaign sources changed during execution')
        receipt['status'],code='success',0
    except Exception as error:
        receipt['status'],receipt['error']='failure',type(error).__name__+': '+str(error)
        print(receipt['error'],file=sys.stderr)
    receipt['duration_seconds']=round(time.monotonic()-started,6)
    del receipt['_artifact_directory']
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(canonical(receipt)+b'\n')
    print('Installed reference workflows:',receipt['status'])
    return code


def worker(argv):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reconstruct',action='store_true',required=True)
    for name in ('receipt','native-root','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    for name in ('revision','source-revision','run-id','platform','python'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args(argv)
    require(args.python=='.'.join(map(str,sys.version_info[:2])), 'Reference reconstruction selected the wrong Python minor')
    require(not Path.cwd().resolve().is_relative_to(ROOT), 'Run reference reconstruction outside checkout')
    receipt,pin=r.read(args.receipt)
    corpus=gate.Corpus(); installed_sources(product_sources(corpus))
    native=r.verify_binaries(args.native_root,args.revision,args.platform)
    authority(receipt,corpus,native,revision=args.revision,source_revision=args.source_revision,
        run_id=args.run_id,target=args.platform,python=args.python)
    artifacts=manager.Artifacts(args.receipt.with_name(gate.ARTIFACT_DIRECTORY),receipt['artifacts'])
    projection=gate.validate_complete(receipt,corpus,artifacts)
    reconstructed=gate.reconstruct(receipt,corpus,artifacts)
    equal(reconstructed['complete_observation_sha256'],projection['complete_observation_sha256'],
        'Independent reconstruction changed the source-platform observation')
    require(artifacts.used==set(artifacts.declared),'Unconsumed reference receipt artifact')
    result={'schema_version':'biocompiler.reference_independent_reconstruction.v1','status':'success',
        'receipt_sha256':pin,'revision':args.revision,'source_revision':args.source_revision,'run_id':args.run_id,
        'native_platform':args.platform,'python_version':platform.python_version(),
        'interpreter':str(Path(sys.executable).resolve()),'interpreter_sha256':sha(r.raw_file(Path(sys.executable).resolve(),256*1024*1024)),
        'campaign_sources':campaign_sources(),'python_sources':product_sources(corpus),
        'complete_artifacts':artifacts.verified,'reconstruction':reconstructed,'projection':projection}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(canonical(result)+b'\n')
    return 0


def compare(root,native_root,*,revision,source_revision,run_id,python311,python314):
    require(type(revision) is str and re.fullmatch('[0-9a-f]{40}',revision)
        and type(source_revision) is str and re.fullmatch('[0-9a-f]{40}',source_revision)
        and type(run_id) is str and run_id, 'Missing current reference run authority')
    root,native_root=Path(root).absolute(),Path(native_root).absolute()
    names={'realization-'+target+'-py'+python for target in r.PLATFORMS for python in r.PYTHONS}
    require(root.is_dir() and not root.is_symlink() and native_root.is_dir() and not native_root.is_symlink()
        and {p.name for p in root.iterdir() if p.name.startswith('realization-')}==names,
        'Incomplete four-runtime reference matrix')
    corpus=gate.Corpus(); sources,tools=product_sources(corpus),campaign_sources()
    interpreters={'3.11':Path(python311).resolve(),'3.14':Path(python314).resolve()}
    require(all(path.is_absolute() and path.is_file() and os.access(path,os.X_OK) for path in interpreters.values())
        and len(set(interpreters.values()))==2,'Reference comparison requires two actual Python runtimes')
    receipts,binaries,common={}, {},None
    with tempfile.TemporaryDirectory(prefix='reference-independent-replay-') as temporary:
        for target in r.PLATFORMS:
            native=r.verify_binaries(native_root/target,revision,target);binaries[target]=native
            for python in r.PYTHONS:
                name='realization-'+target+'-py'+python;directory=root/name
                require(directory.is_dir() and not directory.is_symlink(),'Unsafe reference runtime slot')
                inputs,inputs_pin=r.read(directory/'native-inputs.json',r.CONTROL_BYTES)
                require(all(inputs.get(key)==value for key,value in native.items())
                    and inputs.get('run_id')==run_id and inputs.get('source_revision')==source_revision
                    and type(inputs.get('python_version')) is str and inputs['python_version'].startswith(python+'.'),
                    'Stale reference native inputs')
                receipt,pin=r.read(directory/gate.RECEIPT_FILE)
                authority(receipt,corpus,native,revision=revision,source_revision=source_revision,run_id=run_id,
                    target=target,python=python)
                require(receipt['python_version']==inputs['python_version'],'Reference exact source runtime differs')
                artifacts=manager.Artifacts(directory/gate.ARTIFACT_DIRECTORY,receipt['artifacts'])
                output=Path(temporary)/(name+'.json')
                command=[str(interpreters[python]),str(ROOT/gate.SOURCE),'--reconstruct','--receipt',str(directory/gate.RECEIPT_FILE),
                    '--native-root',str(native_root/target),'--output',str(output),'--revision',revision,
                    '--source-revision',source_revision,'--run-id',run_id,'--platform',target,'--python',python]
                completed=subprocess.run(command,cwd=temporary,capture_output=True,timeout=1800,check=False)
                require(len(completed.stdout)+len(completed.stderr)<=1024*1024,'Reference reconstruction diagnostics exceeded bound')
                require(completed.returncode==0,'Reference independent reconstruction failed: '+completed.stderr.decode('utf-8','replace'))
                report,report_pin=r.read(output)
                expected={'schema_version':'biocompiler.reference_independent_reconstruction.v1','status':'success',
                    'receipt_sha256':pin,'revision':revision,'source_revision':source_revision,'run_id':run_id,
                    'native_platform':target,'campaign_sources':tools,'python_sources':sources,
                    'interpreter':str(interpreters[python]),'interpreter_sha256':sha(r.raw_file(interpreters[python],256*1024*1024)),
                    'complete_artifacts':artifacts.verified}
                for key,value in expected.items():equal(report.get(key),value,'Unbound reference reconstruction worker: '+key)
                require(report['python_version'].startswith(python+'.'),'Reference worker used another runtime')
                projected=canonical(report['projection']['original_behavior'])
                require(common is None or projected==common,'Original reference public behavior differs across runtimes')
                common=projected
                receipts[name]={'receipt_sha256':pin,'native_inputs_sha256':inputs_pin,'independent_reconstruction':report,
                    'independent_reconstruction_sha256':report_pin,'complete_artifacts':artifacts.verified}
    return {'schema_version':'biocompiler.reference_workflow_reproducibility.v1','status':'success','scope':SCOPE,
        'revision':revision,'source_revision':source_revision,'run_id':run_id,**metadata(corpus),
        'receipts':receipts,'native_inputs':binaries,'complete_original_behavior_sha256':sha(common),
        'projection':'only physically checked object/provider aliases and proved source paths; raw native and reconstruction evidence retained'}


def main(argv=None):
    arguments=list(sys.argv[1:] if argv is None else argv)
    if '--reconstruct' in arguments:return worker(arguments)
    if '--compare' not in arguments:return campaign_main(arguments)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compare',action='store_true',required=True)
    for name in ('root','native-root','output','python311','python314'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(arguments)
    result=compare(args.root,args.native_root,revision=os.environ.get('GITHUB_SHA'),
        source_revision=os.environ.get('GITHUB_HEAD_SHA',os.environ.get('GITHUB_SHA')),run_id=os.environ.get('GITHUB_RUN_ID'),
        python311=args.python311,python314=args.python314)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_bytes(canonical(result)+b'\n')
    return 0
