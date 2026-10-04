"""Run both complete protocol or routing transport roles in two isolated Python workers.

Each role keeps all direct/replay/current-policy and boundary calls in order.
Only the coordinator publishes the original complete aggregate report directory.
The unchanged independent checker rechecks every original report and occurrence.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import time

try:
    from . import check_realization_reproducibility as checker
except ImportError:
    import check_realization_reproducibility as checker

ROLES = ('core', 'verify')
SCHEMA = 'biocompiler.realization_protocol_role.v1'
MODES = {f'biocompiler.realization_{kind}_conformance.v1':kind for kind in ('protocol', 'routing')}


def mode(receipt):
    checker.require(receipt.get('schema_version') in MODES, 'Unknown role-worker campaign mode')
    return MODES[receipt['schema_version']]
AUTHORITY = ('revision', 'source_revision', 'run_id', 'corpus_pin', 'baseline_pin',
             'platform', 'system', 'machine', 'python_version', 'executables', 'package_path', 'scope', 'campaign_sources')


def merge(parts, directory, receipt):
    checker.require(set(parts) == set(ROLES), 'Incomplete protocol role census')
    checker.require(directory.is_dir() and not directory.is_symlink() and not any(directory.iterdir()),
                    'Protocol aggregate report destination must be empty and safe')
    kind = mode(receipt)
    golden = checker.Golden()
    ordered = list(golden.expected(kind))
    checks, values, declared, calls, records = [], {}, {}, set(), {}
    for role in ROLES:
        root = parts[role]
        checker.require(root == (directory.parent/(kind+'-workers')/role).resolve(), 'Detached protocol role evidence path')
        checker.require(root.is_dir() and not root.is_symlink(), 'Unsafe protocol role directory')
        source, receipt_pin = checker.read(root/'receipt.json')
        log = root/'worker.log'
        checker.require(log.is_file() and not log.is_symlink() and log.stat().st_size <= 32*1024*1024, 'Missing or oversized role log')
        records[role] = {'receipt':{'path':f'{kind}-workers/{role}/receipt.json', 'sha256':receipt_pin, 'bytes':(root/'receipt.json').stat().st_size},
                         'log':{'path':f'{kind}-workers/{role}/worker.log', 'sha256':hashlib.sha256(log.read_bytes()).hexdigest(), 'bytes':log.stat().st_size}}
        checker.require(source.get('schema_version') == f'biocompiler.realization_{kind}_role.v1' and source.get('role') == role
                        and source.get('status') == 'success', 'Failed or foreign protocol role receipt')
        checker.require(all(source.get(key) == receipt.get(key) for key in AUTHORITY), 'Mixed protocol role authority')
        expected = [key for key in ordered if key[0] == role]
        actual = source.get('checks')
        checker.require(type(actual) is list and source.get('completed_checks') == len(expected)
                        and [(row.get('role'), row.get('id'), row.get('operation')) for row in actual] == expected,
                        'Incomplete, duplicated or reordered protocol role sequence')
        checker.require(source.get('artifact_directory') == 'receipt-reports', 'Unsafe protocol role report path')
        role_values = checker.artifacts(root/'receipt-reports', source.get('artifacts'))
        checker.require({row.get('artifact') for row in actual} == set(role_values), 'Unused or missing role report artifact')
        for identity, value in role_values.items():
            entry = source['artifacts'][identity]
            if identity in values:
                checker.require(declared[identity] == entry and checker.canonical(values[identity]) == checker.canonical(value),
                                'Conflicting complete report artifacts across protocol roles')
            else:
                values[identity] = value; declared[identity] = entry
        if kind == 'routing':
            guard = source.get('guard', {})
            checker.require(set(guard) == {'status', 'allowed_executed_functions', 'input_hydration', 'snapshot_request_rehydration'}
                            and guard.get('status') == 'passed'
                            and guard.get('input_hydration') == 'outside_guard_before_native_call'
                            and guard.get('snapshot_request_rehydration') == 'forbidden_during_native_call'
                            and type(guard.get('allowed_executed_functions')) is list
                            and all(type(item) is str for item in guard['allowed_executed_functions'])
                            and checker.REQUIRED_ROUTES <= set(guard['allowed_executed_functions'])
                            and 'biocompiler.compiler.request.RealizationRequest.__post_init__' not in guard['allowed_executed_functions'],
                            'Missing or invalid complete routing execution guard')
            calls.update(guard['allowed_executed_functions'])
        checks.extend(actual)
    combined = {**receipt, 'checks':checks, 'completed_checks':len(checks)}
    checker.validate_checks(combined, kind, golden, values)
    # No worker writes this directory. Reconstitute only independently checked
    # canonical bytes so a post-read worker-file change cannot alter publication.
    for identity, value in sorted(values.items()):
        with (directory/(identity+'.json')).open('xb') as target:
            target.write(checker.canonical(value)+b'\n')
    checker.artifacts(directory, declared)
    receipt.update(checks=checks, artifacts=declared, role_workers={
        'schema_version':'biocompiler.realization_role_workers.v1', 'workers':2, 'campaign':kind,
        'source_pins':receipt['campaign_sources'], 'roles':records})
    if kind == 'routing':
        receipt['guard'] = {'status':'passed', 'allowed_executed_functions':sorted(calls),
                            'input_hydration':'outside_guard_before_native_call',
                            'snapshot_request_rehydration':'forbidden_during_native_call'}


def execute(args, directory, receipt):
    kind = mode(receipt)
    root = (args.output.parent/(kind+'-workers')).resolve()
    root.mkdir(parents=True, exist_ok=False)
    script = Path(__file__).with_name(f'check_realization_{kind}.py').resolve()
    parts = {role:root/role for role in ROLES}
    # Explicit current authority is copied, never invented from inherited child
    # state. Each worker independently checks it against the same checkout.
    environment = dict(os.environ, GITHUB_SHA=receipt['revision'],
                       GITHUB_HEAD_SHA=receipt['source_revision'], GITHUB_RUN_ID=receipt['run_id'])

    def run(role):
        folder = parts[role]; folder.mkdir()
        command = [sys.executable, str(script), '--core', str(args.core), '--verify', str(args.verify),
                   '--workers', '1', '--role', role, '--output', str(folder/'receipt.json')]
        started = time.monotonic()
        print(f'Protocol role {role}: start', flush=True)
        with (folder/'worker.log').open('wb') as log:
            # Each native call keeps its original 60-second transport deadline.
            # Do not kill just the Python worker and orphan its native session;
            # the enclosing hosted job retains the complete campaign deadline.
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=environment,
                                    check=False)
        print(f'Protocol role {role}: exit {result.returncode}, {time.monotonic()-started:.1f}s', flush=True)
        return result.returncode

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(run, ROLES))
    checker.require(all(code == 0 for code in results), 'Protocol role process failed; inspect retained worker receipts/logs')
    merge(parts, directory, receipt)
