"""Hosted staging and fresh-install driver for the complete prebuilt campaign.

This is an explicit release-candidate command. It never publishes and does not
permit source-build fallback during installation. All paths and pins are supplied
by CI. Local controls test plans only; hosted execution is required for acceptance.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import tomllib
import zipfile

if __package__:
    from . import build_prebuilt_core as build, check_prebuilt_core_release as check
else:
    import build_prebuilt_core as build
    import check_prebuilt_core_release as check

# This is the complete realization-conformance command census, not smoke selection.
CAMPAIGNS = (
    ('check_realization_protocol','protocol'), ('check_realization_routing','routing'),
    ('check_pipeline_manager_install','pipeline-manager'),
    ('check_pipeline_fixed_provider_install','pipeline-fixed-providers'),
    ('check_pipeline_fixed_continuation_install','pipeline-fixed-continuations'),
    ('check_pipeline_fixed_registration_install','pipeline-fixed-registration'),
    ('check_pipeline_reference_install','pipeline-reference'),
    ('check_pipeline_session_install','pipeline-session'),
    ('check_native_workflow','workflow'), ('check_native_workflow_presentation','workflow-presentation'),
    ('check_native_workflow_authority','workflow-authority'), ('check_native_workflow_public_sdk','workflow-public-sdk'),
    ('check_native_workflow_cli','workflow-cli'), ('check_native_synthetic_producer','synthetic-producer'),
    ('check_native_synthetic_public_sdk','synthetic-public-sdk'),
    ('check_native_synthetic_selection_cli','synthetic-selection-cli'),
    ('check_native_synthetic_inspection','synthetic-inspection'))


def require(value,message):
    if not value: raise ValueError(message)


def clean_environment(environment):
    result = {key:value for key,value in environment.items() if key not in ('PYTHONPATH','PYTHONHOME','LD_PRELOAD','LD_LIBRARY_PATH',
        'DYLD_LIBRARY_PATH','DYLD_FALLBACK_LIBRARY_PATH','DYLD_INSERT_LIBRARIES','OPAM_SWITCH_PREFIX','CAML_LD_LIBRARY_PATH')}
    result.update(PIP_NO_INDEX='1',PIP_DISABLE_PIP_VERSION_CHECK='1',PYTHONNOUSERSITE='1',
        BIOCOMPILER_NATIVE_INPUT_LAYOUT='installed')
    return result


def run(command, *, cwd, environment, log, timeout=10800):
    require(type(command) is list and all(type(part) is str for part in command), 'Invalid hosted command')
    require(not log.exists(), 'Hosted command log already exists')
    # Output is streamed to a retained file instead of unbounded PIPE accumulation.
    with log.open('xb') as output:
        completed = subprocess.run(command,cwd=cwd,env=environment,stdout=output,stderr=subprocess.STDOUT,timeout=timeout,check=False)
    receipt = {'argv':command,'cwd':str(cwd),'returncode':completed.returncode,
        'log':{'path':log.name,'sha256':hashlib.file_digest(log.open('rb'),'sha256').hexdigest(),'size':log.stat().st_size}}
    require(completed.returncode == 0, 'Hosted command failed; complete log retained: '+str(log))
    return receipt


def install_plan(python, environment_python, sdk, native):
    require(python.is_absolute() and environment_python.is_absolute() and sdk.is_absolute() and native.is_absolute(), 'Installation paths must be absolute')
    require(sdk.name == 'biocompiler-'+build.VERSION+'-py3-none-any.whl'
        and native.name in {'biocompiler_core-'+build.VERSION+'-'+row[2]+'.whl' for row in build.TARGETS.values()}, 'Only exact reviewed wheels may be installed')
    return [str(python),'-m','pip','--python',str(environment_python),'install','--no-index','--no-deps',
        '--only-binary=:all:',str(sdk),str(native)]


MISSING_PACKAGE_SCRIPT = ('from biocompiler.core_distribution import installed_distribution\nfrom biocompiler.core_client import CoreUnavailable\n'
    'try: installed_distribution()\nexcept CoreUnavailable: pass\nelse: raise AssertionError("missing package accepted")\n')


def lifecycle_plan(driver, python, checkout, output, sdk, native, authority):
    environment = python.parent.parent
    return [('create-environment',[str(driver),'-m','venv','--without-pip',str(environment)]),
        ('install',install_plan(driver,python,sdk,native)),
        ('smoke',[str(python),'-I',str(checkout/'tools/check_prebuilt_core_install.py'),'--checkout',str(checkout),
            '--source-revision',authority['source_revision'],'--tested-revision',authority['tested_revision'],
            '--run-id',authority['run_id'],'--output',str(output/'smoke.json')]),
        ('uninstall',[str(driver),'-m','pip','--python',str(python),'uninstall','--yes','biocompiler-core']),
        ('missing-package',[str(python),'-I','-c',MISSING_PACKAGE_SCRIPT]),
        ('reinstall',install_plan(driver,python,sdk,native))]


def campaign_plan(checkout, python, ownership, output):
    package = Path(ownership['package_root']); source = ownership['source_revision']; tested = ownership['tested_revision']
    require(package.is_absolute() and not package.is_relative_to(checkout) and source != '' and tested != '', 'Invalid installed campaign ownership')
    core = ownership['files']['bin/biocompiler-core']; verify = ownership['files']['bin/biocompiler-verify']
    require(core['path'] == str(package/'bin/biocompiler-core') and verify['path'] == str(package/'bin/biocompiler-verify'), 'Installed role paths are detached')
    result = []
    for tool,name in CAMPAIGNS:
        command = [str(python),str(checkout/'tools'/str(tool+'.py')),'--core',core['path'],'--verify',verify['path']]
        if name not in ('protocol','routing'):
            command += ['--core-sha256',core['sha256'],'--verify-sha256',verify['sha256'],
                '--native-root',str(package),'--platform',ownership['native_platform']]
        command += ['--output',str(output/str(name+'.json'))]
        result.append((name,command))
    return result


def sdk_stage(source, manifests, staging):
    require(not staging.exists(), 'SDK build staging already exists')
    pins = build.release([build.regular(path,64*1024) for path in manifests])
    package = check.source_package(source)
    staging.mkdir(parents=True)
    for name,raw in package.items():
        path = staging/'src'/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
    # Keep source metadata unchanged except the explicitly reviewed binary extra
    # and generated package-data authority. No setup.py is introduced or executed.
    pyproject = (source/'pyproject.toml').read_text()
    optional = tomllib.loads(pyproject)['project'].get('optional-dependencies')
    require(optional in (None, {'core':['biocompiler-core=='+build.VERSION]}), 'SDK metadata has an unreviewed release extra')
    if optional is None:
        pyproject = pyproject.replace('[project.scripts]', '[project.optional-dependencies]\ncore = ["biocompiler-core=='+build.VERSION+'"]\n\n[project.scripts]')
    if '_core_release.json' not in pyproject:
        pyproject = pyproject.replace('biocompiler = ["py.typed",', 'biocompiler = ["_core_release.json", "py.typed",')
    (staging/'pyproject.toml').write_text(pyproject)
    (staging/'README.md').write_bytes((source/'README.md').read_bytes())
    (staging/'src/biocompiler/_core_release.json').write_bytes(build.canonical(pins))
    return pins


def sdk_canonical_bytes(raw, *, source_files, release):
    """Validate backend bytes, then change only the known RECORD mode metadata.

    No content, RECORD hashes, compression, ordering or other ZIP fields are
    repaired. The final bytes must pass the ordinary strict release policy.
    """
    require(type(raw) is bytes and 0 < len(raw) <= check.MAX_ARCHIVE, 'Invalid backend SDK archive size')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        rows = check.archive_members(archive, maximum_files=10000, maximum_total=768*1024*1024,
            maximum_file=256*1024*1024, _sdk_backend_record=True)
        entries = {name:(archive.read(entry),stat.S_IMODE(entry.external_attr >> 16)) for name,entry in rows.items()}
        record = 'biocompiler-'+build.VERSION+'.dist-info/RECORD'
        normalized = dict(entries)
        if record in normalized and normalized[record][1] == 0o664:
            normalized[record] = (normalized[record][0],0o644)
        # This independently binds every member to checkout source or reviewed
        # metadata and checks RECORD before changing even one archive byte.
        check.validate_sdk(normalized, source_files=source_files, release=release)
        changes, cursor = [], archive.start_dir
        for name,entry in rows.items():
            require(raw[cursor:cursor+4] == b'PK\x01\x02'
                and struct.unpack_from('<I',raw,cursor+38)[0] == entry.external_attr,
                'Backend SDK central metadata differs')
            if name == record and entries[name][1] == 0o664:
                changes.append({'member':name,'offset':cursor+38,'before':entry.external_attr,
                    'after':(stat.S_IFREG|0o644)<<16 | (entry.external_attr & 0xffff)})
            cursor += 46+len(name.encode('utf-8'))
    result = bytearray(raw)
    for change in changes:
        struct.pack_into('<I',result,change['offset'],change['after'])
    final = bytes(result)
    with zipfile.ZipFile(io.BytesIO(final)) as archive:
        rows = check.archive_members(archive, maximum_files=10000, maximum_total=768*1024*1024, maximum_file=256*1024*1024)
        actual = {name:(archive.read(entry),stat.S_IMODE(entry.external_attr >> 16)) for name,entry in rows.items()}
    require(actual == normalized, 'SDK canonicalization changed member bytes')
    check.validate_sdk(actual, source_files=source_files, release=release)
    return final, {'schema_version':'biocompiler.sdk_archive_canonicalization.v1',
        'backend':{'sha256':build.sha(raw),'size':len(raw)},
        'canonical':{'sha256':build.sha(final),'size':len(final)},'changes':changes}


def canonicalize_sdk(path, *, source_files, release):
    require(path.name == 'biocompiler-'+build.VERSION+'-py3-none-any.whl', 'Unexpected backend SDK wheel name')
    raw = build.regular(path,check.MAX_ARCHIVE)
    final, receipt = sdk_canonical_bytes(raw, source_files=source_files, release=release)
    # Publish only a fully checked replacement; preserve the original on failure.
    with tempfile.TemporaryDirectory(prefix='.sdk-canonical-',dir=path.parent) as temporary:
        candidate = Path(temporary)/path.name
        candidate.write_bytes(final)
        check.validate_sdk(check.read_wheel(candidate), source_files=source_files, release=release)
        require(build.regular(path,check.MAX_ARCHIVE) == raw, 'Backend SDK changed during validation')
        os.replace(candidate,path)
    return receipt


def installed_ownership(python, cwd, environment):
    script = 'import json; from biocompiler.core_distribution import installed_distribution; print(json.dumps(installed_distribution().ownership(),sort_keys=True))'
    result = subprocess.run([str(python),'-I','-c',script],cwd=cwd,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=False)
    require(result.returncode == 0 and not result.stderr and len(result.stdout) < 256*1024, 'Installed ownership discovery failed')
    return json.loads(result.stdout)


def installed(args):
    require(not args.output.exists() and not args.environment.exists(), 'Installed job requires fresh environment and evidence')
    args.output.mkdir(parents=True); env = clean_environment(os.environ)
    require(not args.environment.is_relative_to(args.checkout), 'Fresh environment must be outside checkout')
    source = args.checkout.resolve(); environment = args.environment.resolve()
    python = environment/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    # Explicit Python invocation does not activate this environment for console
    # lookup in child campaigns. Select its installed commands before host tools.
    env['PATH'] = str(python.parent) + os.pathsep + env.get('PATH', os.defpath)
    receipt = {'schema_version':'biocompiler.prebuilt_installed_campaign.v1','status':'running','python_version':sys.version,
        'source_revision':args.source_revision,'tested_revision':args.tested_revision,'run_id':args.run_id,
        'native_platform':args.platform,'commands':[],'campaigns':[]}
    def execute(command,name,cwd=environment):
        receipt['commands'].append(run(command,cwd=cwd,environment=env,log=args.output/(name+'.log')))
    lifecycle = lifecycle_plan(Path(sys.executable).resolve(),python,source,args.output,args.sdk,args.native,receipt)
    try:
        execute(lifecycle[0][1],lifecycle[0][0],args.output)
        execute(lifecycle[1][1],lifecycle[1][0])
        ownership = installed_ownership(python,environment,env)
        require(all(ownership[key] == getattr(args,key) for key in ('source_revision','tested_revision','run_id','native_platform') if hasattr(args,key)), 'Installed release identity differs')
        require(ownership['native_platform'] == args.platform,'Installed platform differs')
        receipt['ownership_before'] = ownership
        for name,command in lifecycle[2:]:
            execute(command,name)
        require(installed_ownership(python,environment,env) == ownership,'Reinstalled ownership differs')
        console = python.parent/('biocompiler.exe' if os.name == 'nt' else 'biocompiler')
        require(shutil.which('biocompiler',path=env['PATH']) == str(console),
                'Fresh installed console script missing')
        for name,command in campaign_plan(source,python,ownership,args.output):
            execute(command,name)
            require((args.output/(name+'.json')).is_file(),'Campaign omitted its complete receipt')
            receipt['campaigns'].append({'name':name,'receipt_sha256':hashlib.sha256((args.output/(name+'.json')).read_bytes()).hexdigest()})
        receipt['ownership_after'] = installed_ownership(python,environment,env)
        require(receipt['ownership_after'] == ownership,'Installed ownership changed during campaigns')
        require([row['name'] for row in receipt['campaigns']] == [name for _,name in CAMPAIGNS], 'Incomplete installed campaign census')
        receipt['status']='pass'
    finally:
        (args.output/'installed-release.json').write_bytes(build.canonical(receipt))


def main():
    parser=argparse.ArgumentParser(description=__doc__); commands=parser.add_subparsers(dest='operation',required=True)
    sdk=commands.add_parser('sdk'); sdk.add_argument('--checkout',type=Path,required=True)
    sdk.add_argument('--manifests',type=Path,nargs=2,required=True); sdk.add_argument('--staging',type=Path,required=True)
    sdk.add_argument('--output',type=Path,required=True)
    install=commands.add_parser('installed')
    for name in ('checkout','sdk','native','environment','output'): install.add_argument('--'+name,type=Path,required=True)
    for name in ('source-revision','tested-revision','run-id','platform'): install.add_argument('--'+name,required=True)
    args=parser.parse_args()
    if args.operation=='installed': installed(args)
    else:
        pins = sdk_stage(args.checkout,args.manifests,args.staging)
        require(not args.output.exists(),'SDK output must be fresh'); args.output.mkdir(parents=True)
        env=clean_environment(os.environ); env['SOURCE_DATE_EPOCH']='315532800'
        receipt=run([sys.executable,'-m','build','--no-isolation','--wheel','--outdir',str(args.output)],
            cwd=args.staging,environment=env,log=args.output/'build-sdk.log',timeout=300)
        receipt['sdk_canonicalization'] = canonicalize_sdk(args.output/('biocompiler-'+build.VERSION+'-py3-none-any.whl'),
            source_files=check.source_package(args.checkout),release=pins)
        (args.output/'build-sdk.json').write_bytes(build.canonical(receipt))


if __name__=='__main__': main()
