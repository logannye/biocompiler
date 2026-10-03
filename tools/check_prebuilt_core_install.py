"""Hosted installed-wheel smoke gate; run outside the repository using -I.

The environment is created and installed by the reviewed CI job. This probe
does not install packages, search PATH, fetch network resources or compile.
It supplements, rather than replaces, all profile-specific installed gates.
"""
import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile


def require(value, message):
    if not value: raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkout', type=Path, required=True)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--tested-revision', required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    require(sys.flags.isolated and not Path.cwd().resolve().is_relative_to(checkout), 'Installed probe must run isolated outside checkout')
    import biocompiler
    from biocompiler.core_client import CoreCancelled
    from biocompiler.core_distribution import installed_core
    package = Path(biocompiler.__file__).resolve().parent
    require(not package.is_relative_to(checkout), 'Installed probe imported checkout sources')
    release = json.loads((package/'_core_release.json').read_bytes())
    require(release['source_revision'] == args.source_revision and release['tested_revision'] == args.tested_revision
        and release['run_id'] == args.run_id, 'Installed SDK authority differs from the exact release job')
    original_path = os.environ.get('PATH')
    os.environ['PATH'] = ''
    try:
        core, verify = installed_core(operation='canonicalize'), installed_core(role='verify')
        payload = {'unicode': 'λ', 'signed_zero': -0.0, 'integer': 2**80}
        canonicalized = core.canonicalize(payload)
        wanted = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)
        require(canonicalized.status == 'ok' and canonicalized.executable == 'core' and canonicalized.result ==
            {'canonical_json': wanted, 'sha256': hashlib.sha256(wanted.encode()).hexdigest()}, 'Installed canonicalization failed')
        try: core.call('capabilities', {}, cancelled=lambda: True)
        except CoreCancelled: pass
        else: raise AssertionError('Installed Core ignored cancellation')
        if __package__:
            from .prebuilt_process_probe import started_cancellation
        else:
            import importlib.util
            helper = Path(__file__).resolve().with_name('prebuilt_process_probe.py')
            spec = importlib.util.spec_from_file_location('prebuilt_process_probe', helper)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            started_cancellation = module.started_cancellation
        with tempfile.TemporaryDirectory(prefix='installed-core-process-') as temporary:
            lifecycle = started_cancellation(Path(temporary).resolve() / 'probe')
        rejected = subprocess.run([str(verify.executable), '--pipeline-callback-session-v1'], input=b'',
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, check=False)
        document = json.loads(rejected.stdout)
        require(rejected.returncode == 2 and rejected.stderr == b'' and document['status'] == 'error'
            and document['diagnostics'][0]['code'] == 'unexpected_arguments', 'Standalone Verify exposed Core manager service')
    finally:
        if original_path is None: os.environ.pop('PATH', None)
        else: os.environ['PATH'] = original_path
    for name, module in tuple(sys.modules.items()):
        if name == 'biocompiler' or name.startswith('biocompiler.'):
            require(Path(module.__file__).resolve().is_relative_to(package), 'Installed product import escaped its owned package')
    record = {'schema_version': 'biocompiler.installed_prebuilt_core.v1', 'source_revision': args.source_revision,
        'tested_revision': args.tested_revision, 'run_id': args.run_id, 'python_version': platform.python_version(),
        'system': platform.system(), 'machine': platform.machine(), 'package_root': str(package),
        'versions': {name: metadata.version(name) for name in ('biocompiler', 'biocompiler-core')},
        'roles': {client.role: {'path': str(client.executable), 'sha256': hashlib.sha256(client.executable.read_bytes()).hexdigest()}
            for client in (core, verify)}, 'checks': ['owned-discovery', 'fresh-role-negotiation', 'canonicalize',
                'pre-spawn-cancellation', 'started-python-child-cancellation-reaping', 'empty-PATH', 'standalone-Verify-rejection'],
        'process_lifecycle': lifecycle}
    args.output.write_text(json.dumps(record, sort_keys=True, indent=2)+'\n')


if __name__ == '__main__': main()
