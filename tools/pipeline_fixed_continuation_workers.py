"""Bounded whole-class continuation workers; no state crosses class processes."""
from __future__ import annotations
from collections import Counter
from contextlib import contextmanager, nullcontext
import io
import os
import signal
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

SCHEMA = 'biocompiler.fixed_continuation_class_worker.v1'
MAX_WORKERS = 2


def groups(driver):
    return tuple(driver.METHODS)


def contexts(driver, group):
    driver.require(group in driver.METHODS, 'Unknown continuation class partition')
    name, methods = driver.METHODS[group]
    return [group+'::fixture.setUpClass', *(group+'::'+name+'.'+method for method in methods)]


def cases(driver, corpus, group):
    selected = set(contexts(driver, group))
    return [case for case in corpus.cases if case['context'] in selected]


def run_original_group(driver, group, *, context=None, modules=None):
    """Run one complete fixture and its exact unchanged method sequence."""
    wanted = contexts(driver, group)
    class_name, methods = driver.METHODS[group]
    modules = driver.load_body_modules() if modules is None else modules
    context = context or (lambda name: nullcontext())
    cls = getattr(modules[group], class_name)
    original = cls.setUpClass
    retained = (original.__func__.__code__, *(getattr(cls, name).__code__ for name in methods))
    observed = []
    current = None
    class Result(unittest.TextTestResult):
        def startTest(self, test):
            nonlocal current
            name = group+'::'+class_name+'.'+test._testMethodName
            observed.append(name)
            current = context(name)
            current.__enter__()
            super().startTest(test)
        def stopTest(self, test):
            nonlocal current
            try:
                super().stopTest(test)
            finally:
                current.__exit__(None, None, None)
                current = None
    def setup(_cls):
        name = group+'::fixture.setUpClass'
        observed.append(name)
        with context(name):
            original()
    log = io.StringIO()
    with patch.object(cls, 'setUpClass', classmethod(setup)):
        result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=Result).run(
            unittest.TestSuite(cls(name) for name in methods))
    driver.require(result.wasSuccessful() and result.testsRun == len(methods) and not result.skipped,
        'Original class assertions failed:\n'+log.getvalue())
    driver.equal(observed, wanted, 'Original class execution order differs')
    after = (cls.setUpClass.__func__.__code__, *(getattr(cls, name).__code__ for name in methods))
    driver.require(len(retained) == len(after) and all(before is current for before, current in zip(retained, after)),
        'Original class bodies changed during grouped execution')
    return {'contexts': observed, 'methods': result.testsRun, 'assertions': 'passed', 'log': log.getvalue()}


def capture_original_group(driver, corpus, oracle, group):
    """Pure original execution; return comparison observations, never requests."""
    before = driver.occurrences.source_files(oracle)
    body_pin = driver.occurrences.driver_identity(driver)
    class Observer(oracle.Observer):
        def __init__(self):
            super().__init__()
            self.context = None
            self.offsets = Counter()
            self.occurrences = []
        @contextmanager
        def in_context(self, name):
            previous, self.context = self.context, name
            try: yield
            finally: self.context = previous
        def profile(self, frame, event, value):
            if frame.f_code is oracle.components.run_component_pipeline.__code__ and event == 'call':
                driver.require(self.context in contexts(driver, group) and self.context in corpus.by_context,
                    'Grouped original call escaped its source context')
                index = self.offsets[self.context]
                driver.require(index < len(corpus.by_context[self.context]), 'Extra grouped original occurrence')
                expected = corpus.by_context[self.context][index]
                self.occurrences.append({key: expected[key] for key in ('id','context','authority')} | {'call_index': index})
                self.offsets[self.context] += 1
            super().profile(frame, event, value)
    observer = Observer()
    with oracle.portable_sources(), observer.installed():
        execution = run_original_group(driver, group, context=observer.in_context)
    selected = cases(driver, corpus, group)
    driver.require(observer.active is None and len(observer.cases) == len(selected)
        and len(observer.occurrences) == len(selected), 'Grouped original occurrence census differs')
    graphs = {}
    for row, objects in zip(observer.occurrences, observer.cases):
        authored = objects['authority_objects']
        authority = {'request': authored['request'].to_dict(), 'history': [frame.to_dict() for frame in authored['history']],
            'until': authored['until'], 'config': None if authored['config'] is None else authored['config'].to_dict()}
        driver.equal(authority, corpus.fixed.document('fixed', row['authority']), 'Grouped authoring authority changed')
        graph = driver.observed_public_graph(oracle, authored['request'], authored['config'], objects['synthetic'],
            objects['component'], objects['synthetic_records'], objects['component_records'])
        identity = driver.sha(driver.canonical(graph))
        if identity in graphs: driver.equal(graphs[identity], graph, 'Grouped original graph collision')
        graphs[identity] = graph
        row['graph'] = identity
    driver.equal(before, driver.occurrences.source_files(oracle), 'Grouped original source changed during execution')
    driver.equal(body_pin, driver.occurrences.driver_identity(driver), 'Pinned original driver changed')
    return {'schema_version': SCHEMA, 'group': group, 'source_files': before, 'driver_body_sha256': body_pin,
        'execution': execution, 'occurrences': observer.occurrences, 'graphs': graphs}


def validate_original_group(driver, corpus, value, baseline, group):
    driver.require(type(value) is dict and set(value) == {'schema_version','group','source_files','driver_body_sha256',
        'execution','occurrences','graphs'} and value['schema_version'] == SCHEMA and value['group'] == group,
        'Malformed original class partition')
    driver.occurrences.validate(baseline, corpus, driver)
    driver.equal(value['source_files'], baseline['source_files'], 'Grouped original source authority differs')
    driver.equal(value['driver_body_sha256'], baseline['driver_body_sha256'], 'Grouped original driver authority differs')
    execution = value['execution']
    driver.require(type(execution) is dict and set(execution) == {'contexts','methods','assertions','log'}
        and execution['contexts'] == contexts(driver, group) and execution['methods'] == len(driver.METHODS[group][1])
        and execution['assertions'] == 'passed' and type(execution['log']) is str and execution['log'].endswith('\nOK\n'),
        'Incomplete original class assertions')
    wanted = [row for row in baseline['occurrences'] if row['context'] in set(contexts(driver, group))]
    driver.equal(value['occurrences'], wanted, 'Grouped original call identity or graph differs from serial execution')
    used = {row['graph'] for row in wanted}
    driver.equal(value['graphs'], {key: baseline['graphs'][key] for key in used},
        'Complete grouped original graph differs from serial execution')
    return {row['id']: value['graphs'][row['graph']] for row in wanted}


def terminate_group(process):
    """Stop the Python worker group; native sessions retain transport deadlines."""
    try: os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError: return
    try: process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        process.wait(timeout=10)


def bounded_processes(jobs, *, limit=MAX_WORKERS, popen=subprocess.Popen, clock=time.monotonic,
                      sleep=time.sleep, stop=terminate_group):
    """Attempt every job unless interrupted; retain failures without retry."""
    if type(limit) is not int or not 1 <= limit <= MAX_WORKERS:
        raise AssertionError('Continuation worker allowance must be one or two')
    if not jobs or len({job['id'] for job in jobs}) != len(jobs):
        raise AssertionError('Missing or duplicate continuation worker jobs')
    pending = list(jobs); active = []; results = {}
    try:
        while pending or active:
            while pending and len(active) < limit:
                job = pending.pop(0)
                output = Path(job['log']).open('xb')
                started = clock()
                try:
                    process = popen(job['command'], cwd=job['cwd'], env=job['env'], stdout=output,
                        stderr=subprocess.STDOUT, start_new_session=True)
                except OSError as error:
                    detail = type(error).__name__+': '+str(error)
                    output.write((detail+'\n').encode()); output.close()
                    results[job['id']] = {'returncode': None, 'spawn_error': detail, 'timed_out': False,
                        'duration_seconds': round(clock()-started, 6)}
                    continue
                except BaseException:
                    output.close(); raise
                active.append((job, process, output, started))
            for item in tuple(active):
                job, process, output, started = item
                status = process.poll()
                timeout = job.get('timeout')
                timed_out = timeout is not None and clock()-started > timeout
                if status is None and timed_out:
                    stop(process); status = process.poll()
                if status is not None:
                    output.close(); active.remove(item)
                    results[job['id']] = {'returncode': status, 'spawn_error': None, 'timed_out': timed_out,
                        'duration_seconds': round(clock()-started, 6)}
            if active: sleep(0.05)
    finally:
        for job, process, output, started in active:
            try: stop(process)
            finally: output.close()
    return {job['id']: results[job['id']] for job in jobs}


def worker_campaign(driver, core, corpus, receipt, group, baseline_path):
    baseline, baseline_pin = driver.r.read(baseline_path, driver.occurrences.MAX_BYTES)
    oracle = driver.load_oracle()
    original = capture_original_group(driver, corpus, oracle, group)
    # This equality is mandatory BEFORE any native manager is created.
    graphs = validate_original_group(driver, corpus, original, baseline, group)
    receipt['partition'] = {'group': group, 'serial_original_sha256': baseline_pin,
        'original_group': driver.manager.artifact(receipt, driver.canonical(original))}
    driver.run_native_bodies(core, corpus, receipt, oracle, graphs, group=group)


def merge_workers(driver, corpus, receipt, baseline, workers):
    """Merge complete receipts in source order after validating group isolation."""
    driver.equal(list(workers), list(groups(driver)), 'Missing, repeated or reordered class workers')
    all_contexts = []; all_entries = []; logs = []; checks = []; partitions = []
    wanted_metadata = ('schema_version','scope','revision','source_revision','run_id','python_version','system','machine',
        'native_platform','package_path','native_inputs','executables','python_sources','campaign_sources')
    for group in groups(driver):
        child, directory, raw_receipt, raw_log = workers[group]
        driver.equal(driver.r.decode(raw_receipt), child, 'Worker raw receipt differs')
        driver.require(raw_receipt == driver.canonical(child)+b'\n' and raw_log, 'Worker raw output encoding differs')
        driver.require(child.get('status') == 'success', 'Class worker did not complete successfully: '+group)
        for key in (*wanted_metadata, *driver.metadata(corpus)):
            driver.equal(child.get(key), receipt[key], 'Mixed class worker metadata: '+key)
        partition = child.get('partition')
        driver.require(type(partition) is dict and set(partition) == {'group','serial_original_sha256','original_group'}
            and partition['group'] == group and partition['serial_original_sha256'] == driver.sha(driver.canonical(baseline)),
            'Class worker serial original binding differs')
        artifacts = driver.manager.Artifacts(directory, child['artifacts'])
        validate_original_group(driver, corpus, artifacts.json(partition['original_group'], driver.occurrences.MAX_BYTES), baseline, group)
        execution = artifacts.json(child['original_execution'])
        driver.require(set(execution) == {'contexts','methods','assertions','log','entries'}
            and execution['contexts'] == contexts(driver, group) and execution['methods'] == len(driver.METHODS[group][1])
            and execution['assertions'] == 'passed' and execution['log'].endswith('\nOK\n')
            and ['biocompiler.compiler.components','run_component_pipeline'] in execution['entries'],
            'Incomplete original native class assertions')
        expected = [case['id'] for case in cases(driver, corpus, group)]
        driver.require(child['completed_checks'] == len(expected) and [row['id'] for row in child['checks']] == expected
            and child['direct_checks'] == [], 'Class worker call census differs')
        # Content-addressed artifacts merge only after checking actual raw bytes.
        for identity, definition in child['artifacts'].items():
            raw = artifacts.raw(identity, driver.r.MAX_ARTIFACT_BYTES)
            driver.equal(driver.manager.artifact(receipt, raw), identity, 'Worker artifact bytes changed during merge')
        checks.extend(child['checks']); all_contexts.extend(execution['contexts']); logs.append(execution['log'])
        for entry in execution['entries']:
            if entry not in all_entries: all_entries.append(entry)
        partitions.append({'group': group, 'original_group': partition['original_group'],
            'execution': child['original_execution'], 'checks': expected,
            'worker_receipt': driver.manager.artifact(receipt, raw_receipt),
            'worker_log': driver.manager.artifact(receipt, raw_log)})
    driver.equal([row['id'] for row in checks], [case['id'] for case in corpus.cases], 'Merged original39 census differs')
    receipt['checks'] = checks
    receipt['original_execution'] = driver.manager.artifact(receipt, driver.canonical({'contexts': all_contexts,
        'methods': sum(len(methods) for _, methods in driver.METHODS.values()), 'assertions':'passed',
        'log': ''.join(logs), 'entries': all_entries}))
    receipt['partitions'] = partitions


def run_workers(driver, core, corpus, receipt, baseline, *, limit=MAX_WORKERS, native_root):
    directory = Path(receipt['_artifact_directory']).parent/'pipeline-fixed-class-workers'
    directory.mkdir()
    baseline_path = directory/'serial-original.json'
    baseline_path.write_bytes(driver.canonical(baseline))
    jobs = []; outputs = {}
    environment = dict(os.environ); environment.pop('PYTHONPATH', None); environment['PYTHONDONTWRITEBYTECODE'] = '1'
    for index, group in enumerate(groups(driver)):
        slot = directory/str(index); slot.mkdir(); output = slot/driver.RECEIPT_FILE; outputs[group] = output
        driver.require(native_root is not None, 'Exact parent native root required')
        command = [sys.executable, '-B', str(driver.ROOT/'tools/check_pipeline_fixed_continuation_install.py'),
            '--core', receipt['executables']['core'], '--verify', receipt['executables']['verify'],
            '--core-sha256', core.expected_sha256, '--verify-sha256', receipt['native_inputs']['sha256'][Path(receipt['executables']['verify']).name],
            '--native-root', str(native_root), '--platform', receipt['native_platform'], '--output', str(output),
            '--workers','1','--worker-group',group,'--worker-baseline',str(baseline_path)]
        jobs.append({'id':group,'command':command,'cwd':str(Path.cwd()),'env':environment,'log':slot/'worker.log'})
    # Counts only prioritize submission; they are not measured timing claims.
    jobs.sort(key=lambda job: -len(cases(driver, corpus, job['id'])))
    outcomes = bounded_processes(jobs, limit=limit)
    receipt['worker_outcomes'] = outcomes
    driver.require(all(row['returncode'] == 0 and not row['timed_out'] for row in outcomes.values()),
        'Continuation class worker failed; raw per-worker receipts/logs retained')
    workers = {group: (driver.r.read(outputs[group])[0], outputs[group].with_name(driver.ARTIFACT_DIRECTORY),
        outputs[group].read_bytes(), outputs[group].with_name('worker.log').read_bytes()) for group in groups(driver)}
    merge_workers(driver, corpus, receipt, baseline, workers)


def validate_partitions(driver, receipt, corpus, artifacts, baseline):
    if 'partitions' not in receipt:
        driver.require('worker_outcomes' not in receipt, 'Worker outcomes lack partition evidence')
        return
    rows = receipt['partitions']
    driver.require(type(rows) is list and [row.get('group') for row in rows] == list(groups(driver)),
        'Missing or reordered class partition evidence')
    outcomes = receipt.get('worker_outcomes')
    driver.require(type(outcomes) is dict and set(outcomes) == set(groups(driver)), 'Missing class worker outcomes')
    contexts_seen = []; methods = 0; logs = []; entries = []; checks = []
    metadata_keys = ('schema_version','scope','revision','source_revision','run_id','python_version','system','machine',
        'native_platform','package_path','native_inputs','executables','python_sources','campaign_sources')
    for row in rows:
        group = row['group']; outcome = outcomes[group]
        driver.require(type(outcome) is dict and set(outcome) == {'returncode','spawn_error','timed_out','duration_seconds'}
            and type(outcome['returncode']) is int and outcome['returncode'] == 0 and outcome['spawn_error'] is None
            and outcome['timed_out'] is False and type(outcome['duration_seconds']) in (int,float)
            and outcome['duration_seconds'] >= 0, 'Class worker did not finish successfully')
        driver.require(set(row) == {'group','original_group','execution','checks','worker_receipt','worker_log'}
            and row['checks'] == [case['id'] for case in cases(driver, corpus, group)], 'Partition case census differs')
        raw = artifacts.raw(row['worker_receipt']); child = driver.r.decode(raw)
        driver.require(raw == driver.canonical(child)+b'\n' and child.get('status') == 'success'
            and artifacts.raw(row['worker_log']), 'Raw worker receipt/log is incomplete')
        for key in (*metadata_keys, *driver.metadata(corpus)):
            driver.equal(child.get(key), receipt[key], 'Raw worker metadata differs: '+key)
        driver.equal(child.get('partition'), {'group':group,'serial_original_sha256':driver.sha(driver.canonical(baseline)),
            'original_group':row['original_group']}, 'Raw worker serial authority differs')
        driver.require(child.get('original_execution') == row['execution'] and child.get('direct_checks') == []
            and child.get('completed_checks') == len(row['checks'])
            and [entry['id'] for entry in child['checks']] == row['checks'], 'Raw worker census differs')
        for identity, definition in child['artifacts'].items():
            driver.equal(artifacts.declared.get(identity), definition, 'Raw worker artifact inventory differs')
        checks.extend(child['checks'])
        validate_original_group(driver, corpus, artifacts.json(row['original_group'], driver.occurrences.MAX_BYTES), baseline, group)
        execution = artifacts.json(row['execution'])
        driver.require(set(execution) == {'contexts','methods','assertions','log','entries'}
            and execution['contexts'] == contexts(driver, group)
            and execution['methods'] == len(driver.METHODS[group][1]) and execution['assertions'] == 'passed'
            and execution['log'].endswith('\nOK\n')
            and ['biocompiler.compiler.components','run_component_pipeline'] in execution['entries'],
            'Partition native assertions did not complete')
        contexts_seen.extend(execution['contexts']); methods += execution['methods']; logs.append(execution['log'])
        for entry in execution['entries']:
            if entry not in entries: entries.append(entry)
    driver.equal(checks, receipt['checks'], 'Raw worker checks differ from aggregate')
    driver.equal(artifacts.json(receipt['original_execution']), {'contexts':contexts_seen,'methods':methods,
        'assertions':'passed','log':''.join(logs),'entries':entries}, 'Aggregate original execution differs from raw partitions')
