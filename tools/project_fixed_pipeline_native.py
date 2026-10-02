#!/usr/bin/env python3
"""Bound native corpus parsing without omitting any original provider record."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]
from tools.package_checked_pipeline_corpus import canonical, sha, require

DIRECTORY = ROOT / 'tests/conformance'
PROVIDERS = DIRECTORY / 'fixed-pipeline-provider-records-v1'
PAIRS = (('fixed-pipeline-literals-v1.json', 'fixed-pipeline-native-v1.json'),
         ('fixed-pipeline-continuations-v1.json', 'fixed-pipeline-continuations-native-v1.json'))
METADATA = ('id', 'class', 'origin', 'module', 'file', 'line', 'qualname', 'freevars', 'native_recipe')


def project(full, source_path, source_bytes):
    records, providers = {}, {}
    for identity, original in full['providers'].items():
        raw = canonical(original) + b'\n'
        fingerprint = sha(raw[:-1])
        records[fingerprint] = raw
        providers[identity] = {key: original[key] for key in METADATA if key in original}
        providers[identity]['complete_provider_record'] = {'id': fingerprint, 'bytes': len(raw)}
    result = {key: value for key, value in full.items() if key not in ('providers', 'inventory_fingerprint')}
    result.update(providers=providers, provider_directory=PROVIDERS.name,
        provider_documents=[{'id': key, 'bytes': len(raw)} for key, raw in sorted(records.items())],
        full_corpus={'path': source_path, 'sha256': sha(source_bytes),
                     'inventory_fingerprint': full['inventory_fingerprint']},
        storage_projection='complete_provider_records_externalized_without_semantic_rewrite')
    return result, records


def nodes(value):
    return 1 + (sum(nodes(item) for item in value.values()) if isinstance(value, dict) else
                sum(nodes(item) for item in value) if isinstance(value, list) else 0)


def main():
    require(not PROVIDERS.exists() and not any((DIRECTORY / output).exists() for _, output in PAIRS),
            'Refusing to replace a native corpus storage projection')
    retained, projections, receipt = {}, [], []
    for source, output in PAIRS:
        raw = (DIRECTORY / source).read_bytes()
        full = json.loads(raw)
        require(raw == canonical(full) + b'\n', 'Complete source index bytes changed')
        require(full['inventory_fingerprint'] == sha(canonical({key: value for key, value in full.items() if key != 'inventory_fingerprint'})),
                'Complete source inventory changed')
        result, records = project(full, source, raw)
        result['projection_generator'] = {'path': 'tools/project_fixed_pipeline_native.py', 'sha256': sha(Path(__file__).read_bytes())}
        result['inventory_fingerprint'] = sha(canonical(result))
        data = canonical(result) + b'\n'
        require(len(data) < 64 * 1024 * 1024 and nodes(result) < 1000000, 'Native projection exceeds retained parser bounds')
        retained.update(records)
        projections.append((output, data))
        receipt.append({'path': output, 'bytes': len(data), 'value_nodes': nodes(result),
                        'inventory_fingerprint': result['inventory_fingerprint'],
                        'provider_records': len(records), 'full_inventory': full['inventory_fingerprint']})
    PROVIDERS.mkdir()
    for identity, raw in retained.items():
        (PROVIDERS / (identity + '.json')).write_bytes(raw)
    for output, data in projections:
        (DIRECTORY / output).write_bytes(data)
    print(json.dumps({'projections': receipt, 'unique_provider_records': len(retained),
                      'provider_bytes': sum(len(raw) for raw in retained.values())}, sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
