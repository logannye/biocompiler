"""Run independent architecture scenarios in two isolated Python processes.

All B-derived rejection and publication-lifecycle controls stay with case B.
The coordinator reconstructs the original 175-check, 219-artifact receipt and
applies the unchanged independent census before it can report success.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

try:
    from . import check_architecture_routing_reproducibility as checker
except ImportError:
    import check_architecture_routing_reproducibility as checker

PARTITIONS = (0, 1)


def partition_cases(partition):
    checker.require(type(partition) is int and partition in PARTITIONS, 'Unknown architecture partition')
    return tuple(sorted(checker.CASES)[partition::len(PARTITIONS)])


def merge(parts, artifacts, guards, receipt):
    checker.require(set(parts) == set(PARTITIONS), 'Incomplete architecture partition census')
    checks, files, calls, timings = [], {}, set(), {}
    records = {}
    for partition, directory in sorted(parts.items()):
        source, pin = checker._read(directory/'receipt.json')
        checker.require(source.get('schema_version') == 'biocompiler.architecture_routing_partition.v1'
                        and source.get('partition') == partition and source.get('status') == 'success'
                        and source.get('python_semantics_blocked') is True, 'Failed or unguarded architecture partition')
        keys = ('revision','source_revision','run_id','corpus_pin','system','machine','python_version','executables','package_path')
        checker.require(all(source.get(key) == receipt.get(key) for key in keys), 'Mixed architecture partition authority')
        identities = set(partition_cases(partition))
        expected = {key for key in checker.expected_checks() if key[0] in identities
                    or ('installed/B' in identities and key[0] not in checker.CASES)}
        actual = source.get('checks', [])
        checker.require(type(actual) is list and len(actual) == len(expected)
                        and source.get('completed_checks') == len(expected)
                        and {(row['id'],row['operation']) for row in actual} == expected, 'Incomplete or duplicated architecture scenario checks')
        checks.extend(actual)
        declared = source.get('artifacts')
        checker.require(type(declared) is dict, 'Missing architecture partition artifacts')
        expected_files = {name for name in checker.expected_artifacts()
                          if any(name.startswith((case.split('/',1)[1].lower() if case.startswith('installed/')
                               else case.replace('/','-'))+'/') for case in identities)}
        checker.require(set(declared) == expected_files, 'Wrong architecture partition artifact census')
        actual_files = {path.relative_to(directory/'artifacts').as_posix():path
                        for path in (directory/'artifacts').rglob('*') if not path.is_dir()}
        checker.require(set(actual_files) == set(declared), 'Missing or extra partition artifacts')
        for name, path in actual_files.items():
            checker.require(name not in files and checker._file_hash(path,16*1024*1024) == declared[name],
                            'Overlapping or changed partition artifact')
            files[name] = path
        allowed = source.get('allowed_calls')
        checker.require(type(allowed) is list and all(type(value) is str for value in allowed), 'Missing partition execution guard observations')
        calls.update(allowed)
        elapsed = source.get('scenario_timings', {})
        checker.require(set(elapsed) == identities, 'Missing per-scenario timing census')
        timings.update(elapsed)
        records[str(partition)] = {'receipt_sha256':pin,'checks':len(actual),'duration_seconds':source.get('duration_seconds')}
    combined = {**receipt,'checks':checks,'completed_checks':len(checks)}
    checker._checks(combined)  # All original outcomes and cross-operation pins.
    checker.require(not artifacts.exists() and not guards.exists(), 'Architecture output must be fresh')
    artifacts.mkdir(parents=True);guards.mkdir(parents=True)
    for name,path in sorted(files.items()):
        target=artifacts/name;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as output:output.write(path.read_bytes())
    for partition,directory in sorted(parts.items()):
        for path in sorted((directory/'guards').rglob('*')):
            checker.require(not path.is_symlink(), 'Symlinked partition guard evidence')
            if path.is_dir():continue
            target=guards/path.relative_to(directory/'guards')
            checker.require(not target.exists(), 'Overlapping guard evidence')
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as output:output.write(path.read_bytes())
    inventory={name:hashlib.sha256((artifacts/name).read_bytes()).hexdigest() for name in files}
    checker._artifacts(artifacts,inventory)  # Original complete 219-file census.
    receipt.update(checks=checks,allowed_calls=sorted(calls),python_semantics_blocked=True,
                   artifacts=inventory,scenario_timings=timings,partitions=records)


def execute(args, artifacts, guards, receipt):
    root=args.output.with_suffix('').resolve()/'partitions'
    root.mkdir(parents=True,exist_ok=False)
    script=Path(__file__).with_name('check_architecture_routing.py')
    parts={partition:root/str(partition) for partition in PARTITIONS}

    def run(partition):
        directory=parts[partition];directory.mkdir()
        command=[sys.executable,str(script),'--core',str(args.core),'--verify',str(args.verify),
                 '--partition',str(partition),'--output',str(directory/'receipt.json'),
                 '--artifacts',str(directory/'artifacts')]
        started=time.monotonic()
        with (directory/'worker.log').open('w') as log:
            # CLI child observations remain inside their original scenario.
            # Stream progress only; the complete log is retained independently.
            with subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                                  text=True,encoding='utf-8',errors='replace') as process:
                for line in process.stdout:
                    log.write(line);log.flush()
                    print(f'[architecture partition {partition}] '+line.rstrip()[:2000],flush=True)
                code=process.wait()
        print(f'Architecture partition {partition}: exit {code}, {time.monotonic()-started:.1f}s',flush=True)
        return code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(run,PARTITIONS))
    checker.require(all(code == 0 for code in results), 'Architecture partition process failed')
    # The existing CLI computes guards as output.with_suffix('') / 'guards'.
    for directory in parts.values():
        (directory/'receipt'/'guards').rename(directory/'guards')
    merge(parts,artifacts,guards,receipt)
