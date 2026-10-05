"""Two isolated workers retain every original inspection ordinal and wire call.

Only per-case independent occurrences are partitioned. Worker receipts, logs and
all artifacts remain available for independent postrun reconstruction.
"""
from contextlib import ExitStack
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time

if __package__:
    from . import check_native_synthetic_inspection as p
else:
    import check_native_synthetic_inspection as p

SCHEMA = 'biocompiler.synthetic_inspection_worker.v1'
ROOT_NAME = 'synthetic-inspection-workers'
AUTHORITY = ('revision', 'source_revision', 'run_id', 'python_version', 'system', 'machine', 'native_platform',
             'package_path', 'scope', 'native_inputs', 'executables', 'transport_sources', 'campaign_sources',
             'corpus_pins', 'corpus_census', 'original_occurrences', 'profile_pin',
             'native_wire_boundary_occurrences', 'public_helper_occurrences')


def ordinals(corpus, index):
    p.require(type(index) is int and index in (0, 1), 'Invalid inspection worker index')
    return list(range(index, len(p.expected_cases(corpus)), 2))


class CombinedArtifacts:
    """Read only already validated worker inventories; preserve original bytes."""
    def __init__(self, declared, owners):
        self.declared, self.owners, self.used = declared, owners, set()

    def raw(self, identity, maximum=p.r.MAX_ARTIFACT_BYTES):
        p.require(identity in self.declared, 'Missing merged inspection artifact')
        self.used.add(identity)
        return self.owners[identity].raw(identity, maximum)

    def json(self, identity, maximum=p.r.CONTROL_BYTES):
        raw = self.raw(identity, maximum)
        value = p.decode(raw)
        p.require(p.canonical(value) == raw, 'Noncanonical merged inspection evidence')
        return value


def collect(root, receipt, corpus):
    started = time.monotonic()
    root = Path(root)
    p.require(p.canonical(receipt.get('execution')) == p.canonical(p.PARALLEL_EXECUTION),
              'Complete inspection acceptance requires two isolated occurrence workers')
    p.require(root.is_dir() and not root.is_symlink() and {path.name for path in root.iterdir()} == {'0', '1'},
              'Incomplete inspection worker directory census')
    expected = list(p.expected_cases(corpus))
    by_key, declared, owners, records = {}, {}, {}, {}
    side = {}
    for index in (0, 1):
        folder = root / str(index)
        p.require(folder.is_dir() and not folder.is_symlink() and
                  {path.name for path in folder.iterdir()} == {'receipt.json', 'worker.log', p.ARTIFACT_DIRECTORY},
                  'Unsafe or incomplete inspection worker evidence')
        source, pin = p.read(folder / 'receipt.json')
        log = folder / 'worker.log'
        raw_log = p.r.raw_file(log, 32 * 1024 * 1024)
        p.require(source.get('schema_version') == SCHEMA and source.get('worker_index') == index and
            type(source.get('worker_index')) is int and source.get('worker_count') == 2 and
            type(source.get('worker_count')) is int and
            source.get('status') == 'success' and source.get('artifact_directory') == p.ARTIFACT_DIRECTORY,
            'Failed or foreign inspection worker receipt')
        p.require(p.canonical(source.get('execution')) == p.canonical(
            {'mode': 'occurrence_worker', 'workers': 2, 'index': index}), 'Inspection child execution mode differs')
        p.require(all(key in source and key in receipt and p.canonical(source[key]) == p.canonical(receipt[key]) for key in AUTHORITY),
                  'Mixed inspection worker authority')
        artifacts = p.Artifacts(folder / p.ARTIFACT_DIRECTORY, source.get('artifacts'))
        p.validate_checks(source, corpus, artifacts, ordinals=ordinals(corpus, index), verify_capabilities=index == 0)
        for row in source['checks']:
            key = row['role'], row['id']
            p.require(key not in by_key, 'Duplicated inspection worker occurrence')
            by_key[key] = row
        for identity, descriptor in artifacts.declared.items():
            if identity in declared:
                p.require(declared[identity] == descriptor and owners[identity].raw(identity) == artifacts.raw(identity),
                          'Conflicting inspection worker artifact')
            else:
                declared[identity], owners[identity] = descriptor, artifacts
        if index == 0:
            side = {key: source[key] for key in ('verify_capabilities', 'verify_capability_guard')}
        records[str(index)] = {
            'receipt': {'path': f'{ROOT_NAME}/{index}/receipt.json', 'sha256': pin,
                        'bytes': (folder / 'receipt.json').stat().st_size},
            'log': {'path': f'{ROOT_NAME}/{index}/worker.log', 'sha256': hashlib.sha256(raw_log).hexdigest(),
                    'bytes': len(raw_log)}}
    p.require(set(by_key) == set(expected), 'Missing inspection worker occurrence')
    combined = {**receipt, 'checks': [by_key[key] for key in expected], 'completed_checks': len(expected),
                'artifacts': declared, **side}
    artifacts = CombinedArtifacts(declared, owners)
    p.validate_checks(combined, corpus, artifacts)
    metadata = {'schema_version': 'biocompiler.synthetic_inspection_workers.v1', 'workers': 2,
                'assignment': 'original_ordinal_modulo_two', 'source_pins': receipt['campaign_sources'],
                'parts': records}
    print(f'Inspection worker collection and reconstruction: {time.monotonic()-started:.3f}s', flush=True)
    return combined, artifacts, metadata


def validate_evidence(directory, receipt, corpus):
    root = Path(directory) / ROOT_NAME
    metadata = receipt.get('occurrence_workers')
    p.require(p.canonical(receipt.get('execution')) == p.canonical(p.PARALLEL_EXECUTION) and metadata is not None,
              'Inspection acceptance requires complete two-worker evidence metadata')
    combined, _, expected = collect(root, receipt, corpus)
    p.require(p.canonical(metadata) == p.canonical(expected), 'Inspection worker receipts/logs/source bindings differ')
    for key in ('checks', 'completed_checks', 'artifacts', 'verify_capabilities', 'verify_capability_guard'):
        p.require(p.canonical(receipt.get(key)) == p.canonical(combined[key]), 'Inspection worker aggregate differs: ' + key)


def execute(args, directory, receipt, corpus):
    directory = Path(directory)
    p.require(directory.is_dir() and not directory.is_symlink() and not any(directory.iterdir()),
              'Inspection aggregate destination is not empty and safe')
    requested = args.output.parent / ROOT_NAME
    p.require(not requested.is_symlink() and not requested.exists(), 'Inspection worker destination already exists')
    root = requested.resolve()
    root.mkdir(parents=True, exist_ok=False)
    script = Path(__file__).with_name('check_native_synthetic_inspection.py').resolve()
    environment = dict(os.environ, GITHUB_SHA=receipt['revision'], GITHUB_HEAD_SHA=receipt['source_revision'],
                       GITHUB_RUN_ID=receipt['run_id'])
    processes, codes = [], []
    with ExitStack() as stack:
        try:
            for index in (0, 1):
                folder = root / str(index); folder.mkdir()
                log = stack.enter_context((folder / 'worker.log').open('wb'))
                command = [sys.executable, str(script)]
                for role in p.ROLES:
                    command += ['--' + role, str(getattr(args, role)), '--' + role + '-sha256', getattr(args, role + '_sha256')]
                command += ['--native-root', str(args.native_root), '--platform', args.platform,
                            '--workers', '1', '--worker-index', str(index), '--output', str(folder / 'receipt.json')]
                print(f'Inspection occurrence worker {index}: start', flush=True)
                process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=environment)
                processes.append((index, process, time.monotonic()))
        finally:
            # Drain every started whole worker, including launch/worker failure.
            # Native exchanges keep their original 300s bound; the hosted job
            # owns the full campaign deadline and descendant cleanup.
            for index, process, started in processes:
                code = process.wait(); codes.append(code)
                print(f'Inspection occurrence worker {index}: exit {code}, observed elapsed {time.monotonic()-started:.1f}s', flush=True)
    p.require(len(codes) == 2 and codes == [0, 0], 'Inspection worker failed; retained receipts/logs contain diagnostics')
    combined, artifacts, metadata = collect(root, receipt, corpus)
    started = time.monotonic()
    for identity, descriptor in combined['artifacts'].items():
        with (directory / descriptor['path']).open('xb') as target:
            target.write(artifacts.raw(identity))
    print(f'Inspection aggregate artifact copy: {time.monotonic()-started:.3f}s', flush=True)
    for key in ('checks', 'completed_checks', 'artifacts', 'verify_capabilities', 'verify_capability_guard'):
        receipt[key] = combined[key]
    receipt['occurrence_workers'] = metadata
