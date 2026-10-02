#!/usr/bin/env python3
"""Package the complete original capture and derive a bounded manager pilot.

Compression and projection change storage only. The full original ledger and
all complete documents remain immutable evidence; neither establishes native
producer/checker parity.
"""
from collections import Counter
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'tests/conformance'
PROJECTION = DIRECTORY / 'checked-pipeline-v1.json'
MANIFEST = DIRECTORY / 'checked-pipeline-full-v1.json'
ARCHIVE = DIRECTORY / 'checked-pipeline-full-v1.json.gz'
DOCUMENTS = DIRECTORY / 'checked-pipeline-v1'
CAPTURE = ROOT / 'generated/migration-next/checked-pipeline-capture/full-capture.json'
CAPTURE_GENERATOR = 'b13c7870a886a66a63f8ae5ac4b95f70f3b9f9d1c272032984b215b80d83529c'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fingerprint(value):
    return sha(canonical({key: item for key, item in value.items() if key != 'inventory_fingerprint'}))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def provider_refs(value):
    if isinstance(value, dict):
        if value.get('$type') == 'provider':
            yield value['id']
        for item in value.values():
            yield from provider_refs(item)
    elif isinstance(value, list):
        for item in value:
            yield from provider_refs(item)


def derive_projection(full, read_document):
    contexts = [item for item in full['contexts'] if item['kind'] == 'original_method' and
                item['id'].startswith('tests/test_pipeline.py::')]
    context_ids = {item['id'] for item in contexts}
    require(len(contexts) == 21, 'Original manager pilot context census changed')
    events = [event for event in full['events'] if event['context'] in context_ids]
    references = {event[key] for event in events for key in ('arguments', 'result', 'state_before', 'state_after')
                  if event.get(key) is not None}
    documents = [item for item in full['documents'] if item['id'] in references]
    require(len(documents) == len(references), 'Manager pilot document missing from complete ledger')
    providers = set(event['provider'] for event in events if 'provider' in event)
    for descriptor in documents:
        providers.update(provider_refs(read_document(descriptor)))
    queue = list(providers)
    while queue:
        identity = queue.pop()
        for reference in provider_refs(full['providers'][identity]):
            if reference not in providers:
                providers.add(reference)
                queue.append(reference)
    result = {key: value for key, value in full.items() if key not in
              ('inventory_fingerprint', 'contexts', 'events', 'providers', 'documents', 'coverage',
               'original_methods', 'subprocesses', 'baseline_subprocesses')}
    result.update(capture_mode='manager_isolation_projection', contexts=contexts, events=events,
        providers={key: full['providers'][key] for key in sorted(providers)}, documents=documents,
        original_methods=[item['id'] for item in contexts], subprocesses=[], baseline_subprocesses=[],
        full_corpus={'inventory_fingerprint': full['inventory_fingerprint'],
            'original_capture_fingerprint': full['original_capture_fingerprint'],
            'contexts': full['coverage']['contexts'], 'original_methods': full['coverage']['original_methods']},
        coverage={'original_methods': 21, 'per_module_methods': {'tests/test_pipeline.py': 21},
            'contexts': len(contexts), 'events': len(events), 'documents': len(documents),
            'document_bytes': sum(item['bytes'] for item in documents), 'providers': len(providers),
            'api_census': dict(sorted(Counter(event['api'] for event in events).items())),
            'outcomes': dict(Counter(event['outcome'] for event in events))})
    result['inventory_fingerprint'] = fingerprint(result)
    return result


def package(capture=CAPTURE):
    require(not any(path.exists() for path in (PROJECTION, MANIFEST, ARCHIVE, DOCUMENTS)),
            'Refusing to replace existing original checked-pipeline evidence')
    raw = capture.read_bytes()
    document = json.loads(raw)
    require(raw == canonical(document) + b'\n', 'Original full capture bytes are not canonical')
    require(document['capture_mode'] == 'full' and document['coverage']['original_methods'] == 467,
            'Only the complete 467-method original capture can be packaged')
    require(document['capture_tool'] == {'path': 'tools/freeze_checked_pipeline.py', 'sha256': CAPTURE_GENERATOR}
            and sha((ROOT / document['capture_tool']['path']).read_bytes()) == CAPTURE_GENERATOR,
            'Successful original capture generator changed')
    for path, pin in document['source_files'].items():
        require(sha((ROOT / path).read_bytes()) == pin, 'Original captured source changed: ' + path)
    full = {key: value for key, value in document.items() if key != 'documents'}
    full.update(schema_version='biocompiler.checked_pipeline_conformance.v1', document_directory=DOCUMENTS.name,
        original_capture_fingerprint=sha(raw[:-1]), documents=[
            {'id': identity, 'bytes': len(canonical(value)) + 1}
            for identity, value in sorted(document['documents'].items())])
    full['inventory_fingerprint'] = fingerprint(full)
    projection = derive_projection(full, lambda descriptor: document['documents'][descriptor['id']])
    full_bytes = canonical(full) + b'\n'
    compressed = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed, mode='wb', filename='', mtime=0, compresslevel=9) as stream:
        stream.write(full_bytes)
    archive = compressed.getvalue()
    projection_bytes = canonical(projection) + b'\n'
    manifest = {'schema_version': 'biocompiler.checked_pipeline_archive.v1',
        'scope': full['scope'], 'capture_tool': full['capture_tool'],
        'packager': {'path': 'tools/package_checked_pipeline_corpus.py', 'sha256': sha(Path(__file__).read_bytes())},
        'inventory_fingerprint': full['inventory_fingerprint'],
        'original_capture_fingerprint': full['original_capture_fingerprint'],
        'original_capture_bytes': len(raw), 'original_capture_sha256': sha(raw),
        'coverage': full['coverage'], 'document_directory': DOCUMENTS.name,
        'archive': {'path': ARCHIVE.name, 'sha256': sha(archive), 'bytes': len(archive),
            'uncompressed_sha256': sha(full_bytes), 'uncompressed_bytes': len(full_bytes)},
        'projection': {'path': PROJECTION.name, 'sha256': sha(projection_bytes),
            'inventory_fingerprint': projection['inventory_fingerprint']}}
    DOCUMENTS.mkdir()
    for identity, value in document['documents'].items():
        content = canonical(value)
        require(sha(content) == identity, 'Original document content identity changed')
        (DOCUMENTS / (identity + '.json')).write_bytes(content + b'\n')
    ARCHIVE.write_bytes(archive)
    PROJECTION.write_bytes(projection_bytes)
    MANIFEST.write_bytes(canonical(manifest) + b'\n')
    print(json.dumps({'manifest_sha256': sha(MANIFEST.read_bytes()), 'full_inventory': full['inventory_fingerprint'],
        'projection_inventory': projection['inventory_fingerprint'], 'archive_bytes': len(archive),
        'full_index_bytes': len(full_bytes), 'projection_bytes': len(projection_bytes),
        'projection_coverage': projection['coverage']}, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, default=CAPTURE)
    args = parser.parse_args()
    package(args.capture)
