"""Hosted staging and fresh-install driver for the complete prebuilt campaign.

This is an explicit release-candidate command. It never publishes and does not
permit source-build fallback during installation. All paths and pins are supplied
by CI. Local controls test plans only; hosted execution is required for acceptance.
"""
from __future__ import annotations
import argparse
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
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
import time
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

# Scheduling changes only; every campaign and each stateful scenario inside it
# remains intact. Initial groups are conservative; recorded timings guide edits.
CAMPAIGN_GROUPS = {
    'protocol': ('protocol',),
    'manager': ('routing', 'pipeline-manager'),
    'fixed': ('pipeline-fixed-providers', 'pipeline-fixed-continuations',
              'pipeline-fixed-registration', 'pipeline-reference', 'pipeline-session'),
    'workflow': ('workflow', 'workflow-presentation', 'workflow-authority',
                 'workflow-public-sdk', 'workflow-cli'),
    'synthetic': ('synthetic-producer', 'synthetic-public-sdk',
                  'synthetic-selection-cli', 'synthetic-inspection'),
}
LIFECYCLE_NAMES = ('create-environment', 'install', 'smoke', 'uninstall', 'missing-package', 'reinstall')
PARALLEL_CAMPAIGN_GROUPS = frozenset(('fixed', 'manager', 'workflow', 'synthetic'))
CAMPAIGN_WORKERS = 2


def campaign_names(group=None):
    complete = [name for _, name in CAMPAIGNS]
    assigned = [name for names in CAMPAIGN_GROUPS.values() for name in names]
    require(len(assigned) == len(set(assigned)) and set(assigned) == set(complete),
            'Campaign groups omit or repeat required work')
    require(group is None or group in CAMPAIGN_GROUPS, 'Unknown campaign group')
    return complete if group is None else list(CAMPAIGN_GROUPS[group])


def require(value,message):
    if not value: raise ValueError(message)


def clean_environment(environment):
    result = {key:value for key,value in environment.items() if key not in ('PYTHONPATH','PYTHONHOME','LD_PRELOAD','LD_LIBRARY_PATH',
        'DYLD_LIBRARY_PATH','DYLD_FALLBACK_LIBRARY_PATH','DYLD_INSERT_LIBRARIES','OPAM_SWITCH_PREFIX','CAML_LD_LIBRARY_PATH')}
    result.update(PIP_NO_INDEX='1',PIP_DISABLE_PIP_VERSION_CHECK='1',PYTHONNOUSERSITE='1',
        BIOCOMPILER_NATIVE_INPUT_LAYOUT='installed')
    return result


FAILURE_TAIL_BYTES = 64 * 1024
FAILURE_TAIL_LINES = 80
FAILURE_LINE_CHARS = 1000


def _diagnostic_line(text):
    # ASCII escaping keeps control characters from rewriting hosted output.
    # Also neutralize both workflow-command forms, even after a line prefix.
    text = re.sub(r':(?=:)', ': ', ascii(text)[1:-1]).replace('##[', '# #[')
    suffix = ' ... [line truncated]'
    return text if len(text) <= FAILURE_LINE_CHARS else text[:FAILURE_LINE_CHARS-len(suffix)] + suffix


def failure_log_tail(log, *, reason):
    """Best-effort bounded diagnostics; the complete retained bytes stay intact."""
    try:
        with log.open('rb') as source:
            source.seek(0, os.SEEK_END)
            size = source.tell()
            source.seek(max(0, size - FAILURE_TAIL_BYTES))
            raw = source.read(FAILURE_TAIL_BYTES)
        lines = raw.splitlines()
        print('Failed hosted command (' + reason + ') log tail: ' + _diagnostic_line(str(log))
              + f' (last {len(raw)}/{size} bytes; at most {FAILURE_TAIL_LINES} lines, '
                f'{FAILURE_LINE_CHARS} characters per line)', flush=True)
        for line in lines[-FAILURE_TAIL_LINES:]:
            print('  | ' + _diagnostic_line(line.decode('utf-8', 'backslashreplace')), flush=True)
    except (OSError, UnicodeError, ValueError):
        # A missing/unreadable log or unavailable stdout must not replace the
        # child failure (including the original TimeoutExpired instance).
        pass

def _hosted_progress(text):
    # Progress output must not replace the child's status or original exception.
    try:
        print(text, flush=True)
    except (OSError, UnicodeError, ValueError):
        pass


def run(command, *, cwd, environment, log, timeout=10800, grouped=True):
    require(type(command) is list and all(type(part) is str for part in command), 'Invalid hosted command')
    require(not log.exists(), 'Hosted command log already exists')
    # Output is streamed to a retained file instead of unbounded PIPE accumulation.
    started = time.monotonic()
    _hosted_progress(('::group::' if grouped else '') + 'Installed campaign: ' + _diagnostic_line(log.stem))
    try:
        try:
            with log.open('xb') as output:
                completed = subprocess.run(command,cwd=cwd,env=environment,stdout=output,stderr=subprocess.STDOUT,timeout=timeout,check=False)
        except subprocess.TimeoutExpired:
            failure_log_tail(log, reason='timeout')
            raise
        elapsed = round(time.monotonic() - started, 6)
        _hosted_progress(f'{_diagnostic_line(log.stem)}: exit {completed.returncode}, {elapsed}s')
        if completed.returncode != 0:
            failure_log_tail(log, reason=f'exit {completed.returncode}')
        with log.open('rb') as source:
            log_sha256 = hashlib.file_digest(source, 'sha256').hexdigest()
        receipt = {'argv':command,'cwd':str(cwd),'returncode':completed.returncode,
            'duration_seconds':elapsed,
            'log':{'path':log.name,'sha256':log_sha256,'size':log.stat().st_size}}
        require(completed.returncode == 0, 'Hosted command failed; complete log retained: '+str(log))
        return receipt
    finally:
        if grouped:
            _hosted_progress('::endgroup::')


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


def campaign_plan(checkout, python, ownership, output, group=None):
    package = Path(ownership['package_root']); source = ownership['source_revision']; tested = ownership['tested_revision']
    require(package.is_absolute() and not package.is_relative_to(checkout) and source != '' and tested != '', 'Invalid installed campaign ownership')
    core = ownership['files']['bin/biocompiler-core']; verify = ownership['files']['bin/biocompiler-verify']
    require(core['path'] == str(package/'bin/biocompiler-core') and verify['path'] == str(package/'bin/biocompiler-verify'), 'Installed role paths are detached')
    result = []
    for tool,name in CAMPAIGNS:
        if name not in campaign_names(group): continue
        command = [str(python),str(checkout/'tools'/str(tool+'.py')),'--core',core['path'],'--verify',verify['path']]
        if name not in ('protocol','routing'):
            command += ['--core-sha256',core['sha256'],'--verify-sha256',verify['sha256'],
                '--native-root',str(package),'--platform',ownership['native_platform']]
        if name in ('protocol', 'routing'):
            command += ['--workers', '2']
        command += ['--output',str(output/str(name+'.json'))]
        result.append((name,command))
    return result


def campaign_execution(names, *, started=None):
    """Bind a complete ordered dispatch to this exact installed driver source."""
    return {'schema_version':'biocompiler.installed_campaign_execution.v1',
        'workers':CAMPAIGN_WORKERS, 'driver_source':{'path':'tools/prebuilt_release_pipeline.py',
            'sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        'campaign_order':list(names), 'started':list(names if started is None else started)}


def execute_campaigns(plan, *, cwd, environment, output, receipt):
    """Overlap whole commands only; stop dispatch on failure and drain children.

    Threads own no biological/session state: every task invokes the original
    complete campaign subprocess. Nested campaign workers retain their existing
    limits, so this bounds top-level campaigns rather than all native processes.
    """
    require(type(plan) is list and plan and len({name for name,_ in plan}) == len(plan),
            'Invalid or repeated parallel campaign plan')
    names = [name for name,_ in plan]
    outcomes, next_index, failed = {}, 0, False

    def execute(index):
        name,command = plan[index]
        row, campaign = None, None
        try:
            row = run(command, cwd=cwd, environment=environment, log=output/(name+'.log'), grouped=False)
            path = output/(name+'.json')
            require(path.is_file(), 'Campaign omitted its complete receipt')
            campaign = {'name':name, 'receipt_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
            return row, campaign, None
        except BaseException as error:
            # Return the same exception after draining; do not replace timeout
            # or process diagnostics, and do not synthesize a successful row.
            return row, campaign, error

    with ThreadPoolExecutor(max_workers=CAMPAIGN_WORKERS) as executor:
        pending = {}
        while next_index < min(CAMPAIGN_WORKERS, len(plan)):
            pending[executor.submit(execute,next_index)] = next_index
            next_index += 1
        while pending:
            done, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in sorted(done, key=pending.get):
                index = pending.pop(future)
                outcomes[index] = future.result()
                failed = failed or outcomes[index][2] is not None
            if not failed:
                while next_index < len(plan) and len(pending) < CAMPAIGN_WORKERS:
                    pending[executor.submit(execute,next_index)] = next_index
                    next_index += 1
    # Only the coordinator publishes receipt rows, in the original source order.
    receipt['campaign_execution'] = campaign_execution(names,
        started=[names[index] for index in sorted(outcomes)])
    for index in sorted(outcomes):
        row,campaign,error = outcomes[index]
        if row is not None:
            receipt['commands'].append(row)
        if campaign is not None:
            receipt['campaigns'].append(campaign)
    errors = [(index, outcome[2]) for index,outcome in sorted(outcomes.items()) if outcome[2] is not None]
    if errors:
        receipt['status'] = 'failure'
        receipt['campaign_failures'] = [{'name':names[index], 'type':type(error).__name__,
            'message':str(error)} for index,error in errors]
        raise errors[0][1]
    require(len(outcomes) == len(plan) and [row['name'] for row in receipt['campaigns']] == names,
            'Incomplete parallel campaign census')


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


def native_input_document(ownership, python_version):
    """Bridge actual installed ownership to existing cross-runtime checkers."""
    raw = build.regular(Path(ownership['package_root'])/'binaries.json', 64*1024)
    require(ownership['files']['binaries.json'] == {
        'path':str(Path(ownership['package_root'])/'binaries.json'), 'sha256':build.sha(raw), 'size':len(raw)},
        'Installed binary manifest differs from its owned bytes')
    manifest = json.loads(raw)
    require(set(manifest) == {'revision','system','machine','sha256'}
            and manifest['revision'] == ownership['tested_revision']
            and (manifest['system'],manifest['machine']) == build.TARGETS[ownership['native_platform']][:2]
            and manifest['sha256'] == {name:ownership['files']['bin/'+name]['sha256'] for name in build.ROLES},
            'Installed binary manifest identity differs')
    return {'schema_version':'biocompiler.native_conformance_inputs.v1', 'status':'pass',
            **manifest, 'native_platform':ownership['native_platform'], 'manifest_sha256':build.sha(raw),
            'source_revision':ownership['source_revision'], 'run_id':ownership['run_id'],
            'python_version':python_version}


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
    group = getattr(args, 'group', None)
    if group is not None:
        campaign_names(group)
        receipt.update(schema_version='biocompiler.prebuilt_installed_campaign.v2', campaign_group=group)
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
        inputs = build.canonical(native_input_document(ownership, sys.version.split()[0]))
        (args.output/'native-inputs.json').write_bytes(inputs)
        receipt['native_inputs_sha256'] = build.sha(inputs)
        plan = campaign_plan(source,python,ownership,args.output,group)
        if group in PARALLEL_CAMPAIGN_GROUPS:
            execute_campaigns(plan, cwd=environment, environment=env, output=args.output, receipt=receipt)
        else:
            for name,command in plan:
                execute(command,name)
                require((args.output/(name+'.json')).is_file(),'Campaign omitted its complete receipt')
                receipt['campaigns'].append({'name':name,'receipt_sha256':hashlib.sha256((args.output/(name+'.json')).read_bytes()).hexdigest()})
        receipt['ownership_after'] = installed_ownership(python,environment,env)
        require(receipt['ownership_after'] == ownership,'Installed ownership changed during campaigns')
        require([row['name'] for row in receipt['campaigns']] == campaign_names(group), 'Incomplete installed campaign census')
        receipt['status']='pass'
    finally:
        (args.output/'installed-release.json').write_bytes(build.canonical(receipt))


def aggregate(args):
    """Validate all group receipts and retain their original logs/authorities.

    Original campaign artifact paths remain at the slot root, so all existing
    independent semantic/reproducibility checkers still consume complete data.
    Lifecycle logs remain distinct under groups/<name>; no result is overwritten.
    """
    if __package__:
        from . import check_prebuilt_matrix as matrix
    else:
        import check_prebuilt_matrix as matrix
    expected = {key: getattr(args, key) for key in ('source_revision', 'tested_revision', 'run_id')}
    candidate = json.loads(args.candidate.read_bytes())
    require(candidate.get('status') == 'pass' and candidate.get('sdk') is not None
            and all(candidate.get(k) == v for k, v in expected.items()), 'Stale or incomplete candidate')
    require(not args.output.exists() and args.root.is_dir() and not args.root.is_symlink(), 'Unsafe aggregate paths')
    require({p.name for p in args.root.iterdir()} == set(CAMPAIGN_GROUPS), 'Incomplete installed group census')
    records = {}
    for group in CAMPAIGN_GROUPS:
        directory = args.root / group
        require(directory.is_dir() and not directory.is_symlink(), 'Unsafe installed group')
        require(all(not p.is_symlink() for p in directory.rglob('*')), 'Symlinked group evidence')
        receipt = json.loads((directory / 'installed-release.json').read_bytes())
        matrix.validate_slot(receipt, expected, args.platform, args.python_minor, candidate,
                             lambda name, directory=directory: (directory/name).read_bytes(), group=group)
        records[group] = receipt
    owners = [row['ownership_before'] for row in records.values()]
    require(all(owner == owners[0] for owner in owners), 'Group installed owners or binary identities differ')
    require(len({row['python_version'] for row in records.values()}) == 1, 'Group Python runtimes differ')
    # Copy only after the full receipt census has been independently checked.
    args.output.mkdir(parents=True)
    reserved = {'installed-release.json', 'smoke.json', *(name+'.log' for name in LIFECYCLE_NAMES)}
    for group in CAMPAIGN_GROUPS:
        directory = args.root/group
        for path in sorted(directory.rglob('*')):
            if path.is_dir(): continue
            relative = path.relative_to(directory)
            require(relative.parts[0] != 'groups', 'Reserved group evidence path')
            target = args.output/'groups'/group/relative if relative.as_posix() in reserved else args.output/relative
            if relative.as_posix() == 'native-inputs.json' and target.exists():
                require(target.read_bytes() == path.read_bytes(), 'Group native input authorities differ')
                continue
            require(not target.exists(), 'Overlapping campaign artifacts: '+str(relative))
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as output:
                output.write(path.read_bytes())
    document = {'schema_version':'biocompiler.prebuilt_installed_matrix_slot.v2', 'status':'pass',
                **expected, 'native_platform':args.platform, 'python_version':next(iter(records.values()))['python_version'],
                'groups':{group: hashlib.sha256((args.output/'groups'/group/'installed-release.json').read_bytes()).hexdigest()
                          for group in CAMPAIGN_GROUPS}}
    matrix.validate_partitioned_slot(document, expected, args.platform, args.python_minor, candidate,
                                     lambda name: (args.output/name).read_bytes())
    (args.output/'installed-release.json').write_bytes(build.canonical(document))


def main():
    parser=argparse.ArgumentParser(description=__doc__); commands=parser.add_subparsers(dest='operation',required=True)
    sdk=commands.add_parser('sdk'); sdk.add_argument('--checkout',type=Path,required=True)
    sdk.add_argument('--manifests',type=Path,nargs=2,required=True); sdk.add_argument('--staging',type=Path,required=True)
    sdk.add_argument('--output',type=Path,required=True)
    install=commands.add_parser('installed')
    for name in ('checkout','sdk','native','environment','output'): install.add_argument('--'+name,type=Path,required=True)
    for name in ('source-revision','tested-revision','run-id','platform'): install.add_argument('--'+name,required=True)
    install.add_argument('--group', choices=tuple(CAMPAIGN_GROUPS))
    combine=commands.add_parser('aggregate')
    for name in ('root','candidate','output'): combine.add_argument('--'+name,type=Path,required=True)
    for name in ('source-revision','tested-revision','run-id','platform','python-minor'): combine.add_argument('--'+name,required=True)
    args=parser.parse_args()
    if args.operation=='installed': installed(args)
    elif args.operation=='aggregate': aggregate(args)
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
