"""Additive original public identity graphs for every fixed continuation call.

Equal serialized authorities do not imply equal Python source identities. The
unchanged package/CLI bodies deserialize their requests, whereas the fixtures
retain authored constants. Observe all calls independently, then deduplicate
only identical complete graphs. No observation is an input to native execution.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import gzip
import inspect
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'tools/capture_pipeline_fixed_continuation_semantics.py'
OUTPUT = 'tests/conformance/pipeline-fixed-continuation-semantics-v1.json.gz'
SCHEMA = 'biocompiler.pipeline_fixed_continuation_semantics.v1'
MAX_BYTES = 32 * 1024 * 1024


def driver_identity(driver):
    """Bind the closed original-body driver without self-pinning its new oracle."""
    bodies = {name: inspect.getsource(getattr(driver, name)) for name in (
        'load_body_modules', 'run_original_bodies', 'public_graph', 'observed_public_graph')}
    return driver.sha(driver.canonical({'methods': driver.METHODS, 'bodies': bodies}))


def source_files(oracle):
    return {**oracle.source_files(), SOURCE: oracle.sha((ROOT / SOURCE).read_bytes())}


def validate(value, corpus, driver):
    """Check exact occurrence census, immutable source authority and graph content."""
    require, equal = driver.require, driver.equal
    require(type(value) is dict and set(value) == {'schema_version', 'source_files',
        'driver_body_sha256', 'original_build_sha256', 'fixed_inventory_fingerprint',
        'contexts', 'occurrences', 'graphs', 'coverage', 'inventory_fingerprint'},
        'Incomplete original continuation observation')
    require(value['schema_version'] == SCHEMA, 'Unknown original continuation observation')
    equal(value['inventory_fingerprint'], driver.sha(driver.canonical({key: item
        for key, item in value.items() if key != 'inventory_fingerprint'})),
        'Original continuation inventory changed')
    equal(value['driver_body_sha256'], driver_identity(driver), 'Original continuation driver changed')
    equal(value['original_build_sha256'], corpus.build_pin, 'Original six-authority witness changed')
    equal(value['fixed_inventory_fingerprint'], corpus.fixed.indexes['fixed']['inventory_fingerprint'],
        'Original fixed continuation inventory changed')
    wanted_contexts = [item for path, (name, methods) in driver.METHODS.items()
        for item in (path+'::fixture.setUpClass', *(path+'::'+name+'.'+method for method in methods))]
    equal(value['contexts'], wanted_contexts, 'Original continuation contexts were omitted or reordered')
    require(type(value['source_files']) is dict and set(value['source_files']) ==
        set(corpus.build['source_files']) | {SOURCE}, 'Original continuation source census differs')
    require(all(driver.r.pin(pin) for pin in value['source_files'].values()),
        'Invalid original continuation source pin')
    equal(value['source_files'][SOURCE], driver.sha((ROOT / SOURCE).read_bytes()),
        'Original continuation observer source changed')
    require(type(value['occurrences']) is list and len(value['occurrences']) == len(corpus.cases)
        and type(value['graphs']) is dict, 'Original continuation call census differs')
    counts, used, result = Counter(), set(), {}
    for expected, observed in zip(corpus.cases, value['occurrences']):
        require(type(observed) is dict and set(observed) == {'id', 'context', 'call_index',
            'authority', 'graph'}, 'Incomplete original continuation occurrence')
        wanted = {key: expected[key] for key in ('id', 'context', 'authority')}
        wanted['call_index'] = counts[expected['context']]
        counts[expected['context']] += 1
        equal({key: observed[key] for key in wanted}, wanted,
            'Original continuation occurrence identity/order differs')
        pin = observed['graph']
        require(driver.r.pin(pin) and pin in value['graphs'], 'Missing original occurrence graph')
        graph = value['graphs'][pin]
        require(type(graph) is dict and set(graph) == {'roots', 'source_origins', 'nodes'},
            'Incomplete original public graph')
        if pin not in used:
            equal(driver.sha(driver.canonical(graph)), pin, 'Original occurrence graph content changed')
        used.add(pin)
        result[observed['id']] = graph
    require(used == set(value['graphs']), 'Unreferenced original occurrence graph')
    equal(value['coverage'], {'occurrences': len(corpus.cases), 'contexts': len(wanted_contexts),
        'authorities': len(corpus.authorities), 'graphs': len(used), 'original_methods': 13},
        'Original continuation observation coverage differs')
    return result


def capture(corpus, oracle, driver, *, retain=None):
    """Execute unchanged original bodies and retain their exact per-call sources."""
    source_before = source_files(oracle)
    driver_before = driver_identity(driver)

    class Observer(oracle.Observer):
        def __init__(self):
            super().__init__()
            self.context = None
            self.offsets = Counter()
            self.occurrences = []

        @contextmanager
        def in_context(self, name):
            previous, self.context = self.context, name
            try:
                yield
            finally:
                self.context = previous

        def profile(self, frame, event, value):
            if frame.f_code is oracle.components.run_component_pipeline.__code__ and event == 'call':
                driver.require(self.context in corpus.by_context,
                    'Original component call occurred outside its captured context')
                index = self.offsets[self.context]
                driver.require(index < len(corpus.by_context[self.context]),
                    'Unexpected extra original component occurrence')
                expected = corpus.by_context[self.context][index]
                self.occurrences.append({key: expected[key] for key in ('id', 'context', 'authority')}
                    | {'call_index': index})
                self.offsets[self.context] += 1
            super().profile(frame, event, value)

    observer = Observer()
    with oracle.portable_sources(), observer.installed():
        execution = driver.run_original_bodies(context=observer.in_context)
    driver.require(observer.active is None and len(observer.cases) == len(corpus.cases)
        and len(observer.occurrences) == len(corpus.cases), 'Original public occurrence census differs')
    graphs = {}
    for row, objects in zip(observer.occurrences, observer.cases):
        authored = objects['authority_objects']
        authority = {'request': authored['request'].to_dict(),
            'history': [frame.to_dict() for frame in authored['history']], 'until': authored['until'],
            'config': None if authored['config'] is None else authored['config'].to_dict()}
        driver.equal(authority, corpus.fixed.document('fixed', row['authority']),
            'Original occurrence serialized authority changed')
        graph = driver.observed_public_graph(oracle, authored['request'], authored['config'],
            objects['synthetic'], objects['component'], objects['synthetic_records'], objects['component_records'])
        pin = driver.sha(driver.canonical(graph))
        if pin in graphs:
            driver.equal(graph, graphs[pin], 'Different original graphs share a content identity')
        else:
            graphs[pin] = graph
        row['graph'] = pin
    driver.equal(source_before, source_files(oracle), 'Original continuation source changed during capture')
    driver.equal(driver_before, driver_identity(driver), 'Original continuation driver changed during capture')
    result = {'schema_version': SCHEMA, 'source_files': source_before,
        'driver_body_sha256': driver_before, 'original_build_sha256': corpus.build_pin,
        'fixed_inventory_fingerprint': corpus.fixed.indexes['fixed']['inventory_fingerprint'],
        'contexts': execution['contexts'], 'occurrences': observer.occurrences, 'graphs': graphs,
        'coverage': {'occurrences': len(observer.occurrences), 'contexts': len(execution['contexts']),
            'authorities': len(corpus.authorities), 'graphs': len(graphs), 'original_methods': execution['methods']}}
    result['inventory_fingerprint'] = driver.sha(driver.canonical(result))
    validate(result, corpus, driver)
    if retain is not None:
        retain.extend(observer.cases)
    return result


def read_frozen(corpus, driver):
    raw = driver.r.raw_file(ROOT / OUTPUT, MAX_BYTES)
    driver.require(driver.sha(raw) == driver.OCCURRENCE_ORACLE_SHA256,
        'Frozen original continuation observation changed')
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as compressed:
        decoded = compressed.read(MAX_BYTES + 1)
    driver.require(len(decoded) <= MAX_BYTES, 'Original continuation observation exceeds its bound')
    value = json.loads(decoded)
    driver.require(decoded == driver.canonical(value) + b'\n',
        'Original continuation observation encoding differs')
    validate(value, corpus, driver)
    driver.equal({path: pin for path, pin in value['source_files'].items() if path != SOURCE},
        corpus.build['source_files'], 'Frozen continuation observation did not use exact original sources')
    return value
