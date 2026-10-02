"""Installed execution and exact four-runtime receipts for registration replay.

The companion gate owns source recipes and semantic reconstruction. This module
binds that complete reconstruction to installed sources, native binaries and the
current hosted run; it never executes a cached result as acceptance.
"""
from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path
import platform
import re
import sys
import time

if __package__:
    from . import check_pipeline_fixed_registration_install as gate
else:
    import check_pipeline_fixed_registration_install as gate

manager, providers, continuation, r = gate.manager, gate.providers, gate.continuation, gate.r
ROOT = gate.ROOT
require, equal, canonical, sha = gate.require, gate.equal, gate.canonical, gate.sha


def product_sources(corpus):
    original, identity = r.read(ROOT / continuation.BUILD_ORACLE)
    require(identity == continuation.BUILD_ORACLE_SHA256,
        'Registration source closure lost its complete original build witness')
    paths = {path for path in original['source_files'] if path.startswith('src/')}
    paths.update(path for path in corpus.fixed.original_sources if path.startswith('src/'))
    paths.update(manager.python_sources())
    paths.update(('src/biocompiler/core_pipeline_provider_views.py',
        'src/biocompiler/core_pipeline_build_views.py'))
    return r.source_pins(paths)


def metadata(corpus):
    return {**corpus.metadata(),
        'declarations': r.source_pins((manager.CHANNEL_PATH, manager.APPLICATION_PATH))}


def campaign_sources():
    return r.source_pins(tuple(dict.fromkeys((*gate.SOURCES,
        'tools/pipeline_fixed_registration_runtime.py',
        'tests/test_pipeline_fixed_registration_runtime.py'))))


def compare(root, native_root, *, revision, source_revision, run_id):
    require(type(revision) is str and re.fullmatch(r'[0-9a-f]{40}', revision)
        and type(source_revision) is str and re.fullmatch(r'[0-9a-f]{40}', source_revision)
        and type(run_id) is str and run_id, 'Missing current registration validation authority')
    root, native_root = Path(root), Path(native_root)
    names = {'realization-'+target+'-py'+python for target in r.PLATFORMS for python in r.PYTHONS}
    require(root.is_dir() and not root.is_symlink() and native_root.is_dir() and not native_root.is_symlink()
        and {path.name for path in root.iterdir() if path.name.startswith('realization-')} == names,
        'Incomplete four-runtime registration matrix')
    corpus, receipts, binaries, reference_projection = gate.Corpus(), {}, {}, None
    sources, tools, source_metadata = product_sources(corpus), campaign_sources(), metadata(corpus)
    for target, (system, machine) in r.PLATFORMS.items():
        native = r.verify_binaries(native_root / target, revision, target)
        binaries[target] = native
        for python in r.PYTHONS:
            name = 'realization-'+target+'-py'+python
            directory = root / name
            require(directory.is_dir() and not directory.is_symlink(), 'Unsafe registration runtime slot')
            inputs, inputs_pin = r.read(directory / 'native-inputs.json', r.CONTROL_BYTES)
            require(all(inputs.get(key) == value for key, value in native.items())
                and inputs.get('run_id') == run_id and inputs.get('source_revision') == source_revision
                and type(inputs.get('python_version')) is str and inputs['python_version'].startswith(python+'.'),
                'Stale registration native inputs')
            receipt, receipt_pin = r.read(directory / gate.RECEIPT_FILE)
            wanted = {'schema_version': gate.SCHEMA, 'status': 'success', 'scope': gate.SCOPE,
                'revision': revision, 'source_revision': source_revision, 'run_id': run_id,
                'python_version': inputs['python_version'], 'system': system, 'machine': machine,
                'native_platform': target, 'artifact_directory': gate.ARTIFACT_DIRECTORY,
                'native_inputs': native, 'python_sources': sources, 'campaign_sources': tools,
                **source_metadata}
            for key, value in wanted.items():
                equal(receipt.get(key), value, 'Stale or mixed registration receipt: '+key)
            require(type(receipt.get('package_path')) is str and Path(receipt['package_path']).is_absolute()
                and not Path(receipt['package_path']).is_relative_to(ROOT),
                'Registration package was not installed')
            require(type(receipt.get('executables')) is dict and set(receipt['executables']) == {'core', 'verify'}
                and all(type(path) is str and Path(path).is_absolute() and Path(path).name == 'biocompiler-'+role
                    for role, path in receipt['executables'].items())
                and Path(receipt['executables']['core']).parent == Path(receipt['executables']['verify']).parent,
                'Exact registration binary selection absent')
            artifacts = manager.Artifacts(directory / gate.ARTIFACT_DIRECTORY, receipt['artifacts'])
            projected = canonical(gate.validate_checks(receipt, corpus, artifacts))
            require(reference_projection is None or projected == reference_projection,
                'Complete registration observations differ across four runtimes')
            reference_projection = projected
            receipts[name] = {'receipt_sha256': receipt_pin, 'native_inputs_sha256': inputs_pin,
                'complete_artifacts': artifacts.verified}
    return {'schema_version': 'biocompiler.pipeline_fixed_registration_reproducibility.v1',
        'status': 'success', 'scope': gate.SCOPE, 'revision': revision,
        'source_revision': source_revision, 'run_id': run_id, **source_metadata,
        'receipts': receipts, 'native_inputs': binaries,
        'complete_results_sha256': sha(reference_projection),
        'projection': 'validated_unique_session_UUID4_and_process_PID_only;exact_command_invocation_hash_bindings_verified_before_projection;complete_frames_retained'}


def campaign_main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ('core', 'verify'):
        parser.add_argument('--'+role, required=True, type=Path)
        parser.add_argument('--'+role+'-sha256', required=True)
    parser.add_argument('--native-root', required=True, type=Path)
    parser.add_argument('--platform', required=True, choices=r.PLATFORMS)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    import biocompiler
    from biocompiler.core_client import CoreClient
    for name in sorted(manager.TRANSPORT_MODULES | manager.LITERAL_MODULES |
            {'biocompiler.core_pipeline_provider_views', 'biocompiler.core_pipeline_build_views'}):
        importlib.import_module(name)
    corpus, directory = gate.Corpus(), args.output.with_name(gate.ARTIFACT_DIRECTORY)
    sources = product_sources(corpus)
    for path in sources:
        importlib.import_module(path.removeprefix('src/').removesuffix('.py').replace('/', '.'))
    directory.mkdir(parents=True, exist_ok=True)
    require(not directory.is_symlink() and not any(directory.iterdir()),
        'Unsafe or nonempty registration artifact directory')
    started = time.monotonic()
    receipt = {'schema_version': gate.SCHEMA, 'status': 'running', 'scope': gate.SCOPE,
        **metadata(corpus), 'revision': os.environ.get('GITHUB_SHA'),
        'source_revision': os.environ.get('GITHUB_HEAD_SHA', os.environ.get('GITHUB_SHA')),
        'run_id': os.environ.get('GITHUB_RUN_ID'), 'python_version': platform.python_version(),
        'system': platform.system(), 'machine': platform.machine(), 'native_platform': args.platform,
        'package_path': str(Path(biocompiler.__file__).resolve()), 'checks': [], 'artifacts': {},
        'artifact_directory': gate.ARTIFACT_DIRECTORY, '_artifact_directory': str(directory)}
    code = 1
    try:
        require(not Path.cwd().resolve().is_relative_to(ROOT),
            'Run installed registration campaign outside checkout')
        require(receipt['run_id'] and receipt['source_revision']
            and (platform.system(), platform.machine()) == r.PLATFORMS[args.platform],
            'Missing or mismatched hosted registration authority')
        providers.installed_modules()
        native = r.verify_binaries(args.native_root, receipt['revision'], args.platform)
        receipt['native_inputs'], receipt['executables'] = native, {}
        for role in ('core', 'verify'):
            path, pin = getattr(args, role), getattr(args, role+'_sha256')
            require(path.is_absolute() and path.resolve() == (args.native_root / ('biocompiler-'+role)).resolve()
                and not path.is_symlink() and os.access(path, os.X_OK)
                and pin == native['sha256'][path.name], 'Unbound registration binary')
            receipt['executables'][role] = str(path)
        receipt['python_sources'] = sources
        for relative, pin in sources.items():
            name = relative.removeprefix('src/').removesuffix('.py').replace('/', '.')
            require(sha(r.raw_file(Path(sys.modules[name].__file__))) == pin,
                'Installed registration source differs: '+name)
        receipt['campaign_sources'] = campaign_sources()
        client = CoreClient(args.core, role='core', expected_sha256=args.core_sha256, timeout_seconds=300)
        manager.verify_rejection(args.verify, args.verify_sha256, receipt)
        gate.campaign(client, corpus, receipt)
        receipt['completed_checks'] = len(receipt['checks'])
        gate.validate_checks(receipt, corpus, manager.Artifacts(directory, receipt['artifacts']))
        equal(r.verify_binaries(args.native_root, receipt['revision'], args.platform), native,
            'Registration binaries changed during execution')
        receipt['status'], code = 'success', 0
    except Exception as error:
        receipt['status'], receipt['error'] = 'failure', type(error).__name__+': '+str(error)
        print(receipt['error'], file=sys.stderr)
    receipt['completed_checks'] = len(receipt['checks'])
    receipt['duration_seconds'] = round(time.monotonic()-started, 6)
    del receipt['_artifact_directory']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(receipt)+b'\n')
    print('Installed registration interception:', receipt['status'], receipt['completed_checks'],
        'chains, six original boundaries and 33 original operations')
    return code


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if '--compare' not in arguments:
        return campaign_main(arguments)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compare', required=True, action='store_true')
    for name in ('root', 'native-root', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args(arguments)
    result = compare(args.root, args.native_root, revision=os.environ.get('GITHUB_SHA'),
        source_revision=os.environ.get('GITHUB_HEAD_SHA', os.environ.get('GITHUB_SHA')),
        run_id=os.environ.get('GITHUB_RUN_ID'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result)+b'\n')
    return 0
