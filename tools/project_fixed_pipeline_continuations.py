#!/usr/bin/env python3
"""Derive complete fixed-pipeline continuation observations from the original ledger.

The first successful scoped result is the pinned function's return boundary.
Every later top-level manager action is retained. Native replay may execute only
a supported prefix; remaining callback-dependent actions remain explicit.
"""
from collections import defaultdict
import gzip
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]
from tools.package_checked_pipeline_corpus import canonical, sha, require, provider_refs

FIXED = ROOT / 'tests/conformance/fixed-pipeline-literals-v1.json'
OUTPUT = ROOT / 'tests/conformance/fixed-pipeline-continuations-v1.json'
SIMPLE_APIS = ('PassManager.get', 'PassManager.result', 'PassManager.set_dependency', 'PassManager.target')


def mapping_get(value, key):
    require(value.get('$type') == 'mapping', 'Original bound arguments are not a mapping')
    values = [item for candidate, item in value['items'] if candidate == key]
    require(len(values) == 1, 'Original bound argument absent or duplicated: ' + key)
    return values[0]


def derive(fixed, prior, read_document):
    positions = {item['id']: offset for offset, item in enumerate(prior['events'])}
    roots, subtrees, by_manager = {}, defaultdict(list), defaultdict(list)
    for event in prior['events']:
        root = event['id'] if event['parent'] is None else roots[event['parent']]
        roots[event['id']] = root
        subtrees[root].append(event['id'])
        if event['manager'] is not None and event['parent'] is None:
            by_manager[event['manager']].append(event)
    refs, entries = set(), []
    def retain(event):
        refs.update(event[key] for key in ('arguments', 'result', 'state_before', 'state_after') if event.get(key) is not None)
    for case in fixed['cases']:
        entry = {'case': case['id'], 'operation': case['api'], 'kind': case['kind'],
                 'changed_bindings': case['changed_bindings'], 'python_only_inputs': case['python_only_inputs']}
        if case['outcome'] != 'returned' or case['kind'] != 'actual_original_function':
            entry.update(status='function_raised_no_return_boundary', boundary=None, events=[],
                         native_partial_failure_state='pending_inspection_outcome_api')
            entries.append(entry)
            continue
        binding = case['manager_ledger']
        require(binding is not None, 'Returned original fixed pipeline lost its manager')
        scope = 'synthetic_realization' if case['api'] == 'run_synthetic_pipeline' else 'synthetic_components'
        candidates = []
        for event in by_manager[binding['manager']]:
            if event['api'] == 'PassManager.result' and event['outcome'] == 'returned':
                arguments = read_document(event['arguments'])
                if mapping_get(mapping_get(arguments, 'bound'), 'scope') == scope:
                    candidates.append(event)
        require(candidates, 'Returned original fixed pipeline lacks its scoped result')
        boundary = candidates[0]
        subtree = subtrees[boundary['id']]
        last = max(positions[key] for key in subtree)
        events = [event for event in by_manager[binding['manager']] if positions[event['id']] > last]
        for event in [boundary, *events]:
            retain(event)
        prefix = 0
        for event in events:
            if event['api'] not in SIMPLE_APIS:
                break
            prefix += 1
        entry.update(status='complete_original_continuation', manager=binding['manager'],
            boundary=boundary, boundary_subtree=subtree, events=events,
            supported_prefix_events=[event['id'] for event in events[:prefix]],
            pending_callback_dependent_suffix=[event['id'] for event in events[prefix:]],
            native_replay='pending_exact_native_prefix_and_full_suffix_execution')
        entries.append(entry)
    providers = set()
    for identity in refs:
        providers.update(provider_refs(read_document(identity)))
    queue = list(providers)
    while queue:
        identity = queue.pop()
        for reference in provider_refs(prior['providers'][identity]):
            if reference not in providers:
                providers.add(reference)
                queue.append(reference)
    documents = [item for item in prior['documents'] if item['id'] in refs]
    require(len(documents) == len(refs), 'Original continuation document is absent')
    return {'schema_version': 'biocompiler.fixed_pipeline_continuations.v1',
        'scope': 'complete_original_continuations_with_explicit_unported_callback_suffixes',
        'fixed_inventory_fingerprint': fixed['inventory_fingerprint'],
        'prior_inventory_fingerprint': prior['inventory_fingerprint'],
        'prior_original_capture_fingerprint': prior['original_capture_fingerprint'],
        'document_directory': prior['document_directory'], 'source_files': fixed['source_files'],
        'providers': {key: prior['providers'][key] for key in sorted(providers)}, 'documents': documents,
        'entries': entries, 'supported_prefix_apis': list(SIMPLE_APIS),
        'coverage': {'cases': len(entries), 'returned_cases': sum(item['boundary'] is not None for item in entries),
            'top_level_observations': sum(len(item['events']) for item in entries),
            'supported_prefix_observations': sum(len(item.get('supported_prefix_events', [])) for item in entries),
            'pending_suffix_observations': sum(len(item.get('pending_callback_dependent_suffix', [])) for item in entries),
            'documents': len(documents), 'document_bytes': sum(item['bytes'] for item in documents),
            'providers': len(providers)}}


def main():
    require(not OUTPUT.exists(), 'Refusing to replace original fixed pipeline continuation projection')
    fixed_raw = FIXED.read_bytes()
    fixed = json.loads(fixed_raw)
    require(fixed_raw == canonical(fixed) + b'\n', 'Original fixed pipeline index bytes changed')
    require(fixed['inventory_fingerprint'] == sha(canonical({key: value for key, value in fixed.items() if key != 'inventory_fingerprint'})),
            'Original fixed pipeline inventory identity changed')
    reference = fixed['prior_ledger']
    manifest_path = ROOT / reference['manifest']
    require(sha(manifest_path.read_bytes()) == reference['manifest_sha256'], 'Original manager manifest changed')
    manifest = json.loads(manifest_path.read_bytes())
    archive = (manifest_path.parent / manifest['archive']['path']).read_bytes()
    require(sha(archive) == manifest['archive']['sha256'], 'Original manager archive changed')
    raw = gzip.decompress(archive)
    require(sha(raw) == manifest['archive']['uncompressed_sha256'], 'Original manager index changed')
    prior = json.loads(raw)
    require(prior['inventory_fingerprint'] == reference['inventory_fingerprint'], 'Original manager inventory changed')
    directory = manifest_path.parent / prior['document_directory']
    descriptors = {item['id']: item for item in prior['documents']}
    def read(identity):
        content = (directory / (identity + '.json')).read_bytes()
        require(len(content) == descriptors[identity]['bytes'] and sha(content[:-1]) == identity and content.endswith(b'\n'),
                'Complete original continuation document changed')
        return json.loads(content)
    result = derive(fixed, prior, read)
    result.update(generator={'path': 'tools/project_fixed_pipeline_continuations.py', 'sha256': sha(Path(__file__).read_bytes())},
        fixed_index_sha256=sha(fixed_raw), prior_ledger=reference)
    result['inventory_fingerprint'] = sha(canonical(result))
    data = canonical(result) + b'\n'
    require(len(data) < 64 * 1024 * 1024, 'Original continuation projection needs bounded packaging')
    OUTPUT.write_bytes(data)
    print(json.dumps({'bytes': len(data), 'inventory_fingerprint': result['inventory_fingerprint'],
                      'coverage': result['coverage']}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
