"""Check all 72 default selection CLI children against the immutable full baseline.

Only exactly witnessed routes, individually pinned unused additions, the archived
unused backend replacement, composed package metadata, policy dispatch and the
independently captured argparse runtime counterpart may be projected. Complete
actual source, import, stream, filesystem and content evidence remains retained.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import freeze_synthetic_selection_cli as frozen
from tools import synthetic_selection_cli_source_lineage as routes
from tools import manager_registration_source_lineage as managers
from tools import cli_runtime_counterparts as runtime
from tools import package_metadata_source_lineage as packaging
from tools import policy_entrypoint_source_lineage as policy
from tools import synthetic_selection_cli_policy_capture as capture_current
from tools.realization_source_lineage import REFERENCE_ROUTES, verify_captured_source
from tools.reference_original_counterpart import route_source_witness
from tools.check_realization_workflow_corpus import REVIEWED_ADDITIONS, REVIEWED_EXAMPLES, addition_counterparts, addition_module

CORPUS_PIN = '69556f367752be3076513d96e63c933fb250eaf7d9736f9e39baac1dec47e5d9'
COUNTERPART = ROOT / 'tests/conformance/synthetic-selection-cli-runtime-counterparts-v1.json'
UNUSED_SOURCE = ROOT / "protocol/synthetic-selection-unused-transport-lineage-v1.json"
UNUSED_SOURCE_SHA256 = "1f21dfe3896f79e3f21865cc0119b7e30633027b85d766f4013b616f29d086de"
COUNTERPART_SHA256 = 'f9af4b5dedcdb12243209b862d0808866f1ae62355aca291465be75c7f00824b'
canonical, digest, sha, require = frozen.canonical, frozen.digest, frozen.sha, frozen.require


def counterparts():
    return runtime.Counterparts(COUNTERPART, COUNTERPART_SHA256, CORPUS_PIN)


def current_scope():
    scope = frozen.source_scope()
    return {**scope, 'schema_version': 'biocompiler.synthetic_selection_cli_source_scope.v2',
            'denied_modules': sorted(set(scope['denied_modules']) | {
                'biocompiler.core_policy', 'biocompiler.policy', 'examples.expressive_policies'})}


def load_baseline():
    original, blobs = frozen.load()
    require(original['inventory_fingerprint'] == CORPUS_PIN and len(blobs) == 113 and
            len(original['cases']) == original['coverage']['actual_children'] == 72 and
            original['coverage']['original_occurrences'] == 1, 'Immutable complete selection CLI baseline changed')
    parent = routes.load_witness()['historical_source'].encode()
    for name, reference in original['retained_source_bytes'].items():
        expected = (parent if name == routes.CLI else managers.original_source() if name == managers.PATH
                    else route_source_witness(name)[0] if name in REFERENCE_ROUTES
                    else packaging.counterpart(ROOT)[0] if name == packaging.PATH
                    else (ROOT / name).read_bytes())
        if name == managers.PATH:
            managers.verify_source(ROOT, name, managers.HISTORICAL[name])
        require(frozen.f.restore(reference, blobs) == expected, 'Archived selection CLI source bytes changed: ' + name)
    return original, blobs


def inventory(rows):
    require(type(rows) is list and all(type(row) is dict and set(row) == {'path','sha256'} for row in rows),
            'Invalid complete selection CLI source inventory')
    result = {}
    for row in rows:
        path, pin = row['path'], row['sha256']
        require(type(path) is str and not Path(path).is_absolute() and '..' not in Path(path).parts and
                type(pin) is str and len(pin) == 64 and all(c in '0123456789abcdef' for c in pin) and
                path not in result, 'Duplicate or unsafe selection CLI source identity')
        result[path] = pin
    require(rows == [{'path':path,'sha256':pin} for path,pin in sorted(result.items())],
            'Selection CLI source inventory order differs')
    return result


def unused_source_change(before, current):
    raw = UNUSED_SOURCE.read_bytes()
    require(sha(raw) == UNUSED_SOURCE_SHA256, 'Unused transport lineage bytes changed')
    witness = json.loads(raw)
    name = 'src/biocompiler/synthetic_producer_backend.py'
    require(witness['schema_version'] == 'biocompiler.unused_transport_source_lineage.v1' and
            witness['path'] == name and witness['historical_sha256'] == before[name] and
            witness['current_sha256'] == current[name] == REVIEWED_ADDITIONS.get(name) and
            sha(witness['historical_source'].encode()) == before[name] and
            sha(witness['current_source'].encode()) == current[name] and
            (ROOT / name).read_bytes() == witness['current_source'].encode(),
            'Unused transport source lineage differs')
    return witness


def verify_recapture(actual, blobs, *, python_version=None):
    original, old_blobs = load_baseline()
    require(type(actual) is dict and set(actual) == set(original) and actual['inventory_fingerprint'] ==
            digest({key:value for key,value in actual.items() if key != 'inventory_fingerprint'}),
            'Incomplete or changed actual selection CLI capture')
    scope = actual['source_scope']
    require(canonical(scope) == canonical(current_scope()), 'Actual selection CLI scope differs from current source bytes')
    before, current = inventory(original['source_scope']['actual_sources']), inventory(scope['actual_sources'])
    require(set(before) <= set(current), 'Selection CLI historical source membership changed')
    additions = []
    for name in sorted(set(current) - set(before)):
        path = ROOT / name
        require((name.startswith('src/biocompiler/') or name in REVIEWED_EXAMPLES) and name.endswith('.py') and
                REVIEWED_ADDITIONS.get(name) == current[name] and path.is_file() and
                not path.is_symlink() and sha(path.read_bytes()) == current[name],
                'Unreviewed selection CLI source addition: ' + name)
        additions.append({'path':name,'sha256':current[name],'source':path.read_text()})
    addition_proofs = addition_counterparts({row['path']: row['sha256'] for row in additions})
    require(set(scope) == set(original['source_scope']) and scope['denied_modules'] ==
            sorted(set(original['source_scope']['denied_modules']) | {
                'biocompiler.core_policy', 'biocompiler.policy', 'examples.expressive_policies'})
            and scope['schema_version'] == 'biocompiler.synthetic_selection_cli_source_scope.v2' and
            scope['source_inventory_sha256'] == digest(scope['actual_sources']), 'Selection CLI scope metadata changed')
    proof = routes.verify_source(ROOT, before[routes.CLI])
    manager_proof = managers.verify_source(ROOT, managers.PATH, before[managers.PATH])
    unused = unused_source_change(before,current)
    unused_name = unused['path']
    unused_module = unused_name[4:-3].replace('/','.')
    require(unused_module in scope['denied_modules'] and all(unused_module not in row['import_audit']['modules']
            for row in original['cases']), 'Original selection CLI imported changed native transport')
    reference_proofs = [verify_captured_source(ROOT, {'path': name, 'sha256': before[name]})
                        for name in sorted(REFERENCE_ROUTES & set(before))]
    policy_proofs = [verify_captured_source(ROOT, {'path': name, 'sha256': before[name]})
                     for name in sorted(policy.ROUTES & set(before))]
    dispatch_proof = capture_current.verify_sources()
    entrypoint = policy.verify_entrypoint(ROOT)
    shim = b'from biocompiler.entrypoint import main\nraise SystemExit(main())\n'
    expected_environment = deepcopy(original['capture_environment'])
    expected_environment.update(declared_console_entrypoint='biocompiler.entrypoint:main',
        entrypoint_source={'kind':'blob','bytes':len(shim),'sha256':sha(shim)})
    require(actual['capture_environment'] == expected_environment and
            frozen.f.restore(actual['capture_environment']['entrypoint_source'], blobs) == shim,
            'Actual selection CLI dispatch environment differs from its exact counterpart')
    original_metadata, packaging_counterpart = packaging.counterpart(ROOT)
    require(sha(original_metadata) == before[packaging.PATH] and
            packaging_counterpart['current_sha256'] == current[packaging.PATH],
            'Selection CLI package metadata source identities differ')
    for name, pin in before.items():
        path = ROOT / name
        require(path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == current[name] and
                (name in (routes.CLI,unused_name,managers.PATH,packaging.PATH) or
                 name in REFERENCE_ROUTES or name in policy.ROUTES or current[name] == pin),
                'Unreviewed selection CLI source bytes changed: ' + name)
    projected, projected_blobs = deepcopy(actual), dict(blobs)
    require(len(actual['cases']) == len(original['cases']), 'Actual selection CLI child census differs')
    for row, projected_row, old in zip(actual['cases'], projected['cases'], original['cases']):
        audit = row['import_audit']
        require(audit['guard_active'] is True and audit['denied_absent'] is True and
                'biocompiler.cli' in audit['modules'] and not(set(scope['denied_modules']) & set(audit['modules'])),
                'Actual selection CLI imported excluded native transport')
        require(row['id'] == old['id'] and set(audit['modules']) ==
                set(old['import_audit']['modules']) | {'biocompiler.entrypoint'},
                'Actual selection CLI import census differs from exact dispatch counterpart')
        require(audit['modules']['biocompiler.entrypoint'] ==
                {'path':policy.ENTRYPOINT,'sha256':entrypoint['sha256']},
                'Actual selection CLI dispatch source differs')
        for module, item in audit['modules'].items():
            if module == 'biocompiler.entrypoint':
                del projected_row['import_audit']['modules'][module]
                continue
            require(type(item) is dict and set(item) == {'path','sha256'} and
                    (module == 'biocompiler' or module.startswith('biocompiler.')) and
                    item['path'] == old['import_audit']['modules'][module]['path'] and
                    item['path'] in before and item['sha256'] == current[item['path']],
                    'Actual selection CLI imported unpinned source')
            if item['path'] in (routes.CLI,managers.PATH) or item['path'] in REFERENCE_ROUTES or item['path'] in policy.ROUTES:
                projected_row['import_audit']['modules'][module]['sha256'] = before[item['path']]
    current_shim = actual['capture_environment']['entrypoint_source']
    old_shim = original['capture_environment']['entrypoint_source']
    del projected_blobs[current_shim['sha256']]
    projected_blobs[old_shim['sha256']] = old_blobs[old_shim['sha256']]
    projected['capture_environment'] = deepcopy(original['capture_environment'])
    require(set(actual['retained_source_bytes']) == set(original['retained_source_bytes']),
            'Complete retained selection CLI source inventory differs')
    for name, reference in actual['retained_source_bytes'].items():
        raw = (ROOT / name).read_bytes()
        require(reference == {'kind':'blob','bytes':len(raw),'sha256':sha(raw)} and
                frozen.f.restore(reference, blobs) == raw, 'Actual retained selection CLI source bytes differ')
    retained_routes = {routes.CLI} | (({managers.PATH, packaging.PATH} | REFERENCE_ROUTES) & set(actual['retained_source_bytes']))
    for name in sorted(retained_routes):
        current_ref, old_ref = actual['retained_source_bytes'][name], original['retained_source_bytes'][name]
        if current_ref != old_ref:
            del projected_blobs[current_ref['sha256']]
            projected_blobs[old_ref['sha256']] = old_blobs[old_ref['sha256']]
            projected['retained_source_bytes'][name] = deepcopy(old_ref)
    projected['source_scope'] = deepcopy(original['source_scope'])
    minor, declared, changes = runtime.runtime_minor(python_version), counterparts(), []
    for old in original['cases']:
        if old['id'] not in declared.cases: continue
        rows = [row for row in projected['cases'] if row['id'] == old['id']]
        require(len(rows) == 1, 'Exact selection CLI counterpart occurrence inventory differs')
        row = rows[0]
        expected = declared.expected(old, {'exit_code':old['exit_code'],
            **{field:frozen.f.restore(old[field],old_blobs) for field in ('stdout','stderr')}}, minor)
        require(type(row['exit_code']) is int and row['exit_code'] == expected['exit_code'],
                'Exact selection CLI runtime counterpart exit differs')
        for field in ('stdout','stderr'):
            raw = frozen.f.restore(row[field],blobs)
            require(raw == expected[field], 'Exact selection CLI runtime counterpart '+field+' differs')
            if row[field] != old[field]:
                require(row[field] == {'kind':'blob','bytes':len(raw),'sha256':sha(raw)},
                        'Exact selection CLI runtime counterpart reference differs')
                changes.append({'id':old['id'],'field':field,'actual':deepcopy(row[field]),'baseline':deepcopy(old[field])})
                del projected_blobs[row[field]['sha256']]
                projected_blobs[old[field]['sha256']] = old_blobs[old[field]['sha256']]
                row[field] = deepcopy(old[field])
    projected['inventory_fingerprint'] = digest({key:value for key,value in projected.items() if key != 'inventory_fingerprint'})
    require(projected_blobs == old_blobs, 'Complete actual selection CLI content differs from immutable baseline')
    require(canonical(projected) == canonical(original), 'Complete actual selection CLI observations differ from immutable baseline')
    return {'schema_version':'biocompiler.synthetic_selection_cli_source_lineage.v3',
        'packaging_metadata_counterpart':packaging_counterpart,
        'policy_dispatch_counterpart':dispatch_proof, 'reviewed_policy_routes':policy_proofs,
        'reviewed_addition_counterparts': addition_proofs, 'reviewed_reference_routes': reference_proofs,
        'status':'complete_original_selection_cli_recapture_equal','native_execution':False,
        'baseline_inventory_fingerprint':CORPUS_PIN,'actual_inventory_fingerprint':actual['inventory_fingerprint'],
        'projected_inventory_fingerprint':projected['inventory_fingerprint'],'actual_capture':deepcopy(actual),
        'actual_retained_route_source':(ROOT/routes.CLI).read_text(),'reviewed_route':proof,
        'reviewed_manager_registration_prefix':manager_proof,
        'actual_retained_manager_source':(ROOT/managers.PATH).read_text(),
        'reviewed_unused_source_additions':[row for row in additions if row['path'] != policy.ENTRYPOINT],
        'reviewed_dispatch_source_addition':next(row for row in additions if row['path'] == policy.ENTRYPOINT),
        'reviewed_unused_source_change':unused,
        'runtime_counterpart':{'declaration_sha256':declared.pin,'python_minor':minor,
            'validated_cases':sorted(declared.cases),'changes':changes},'coverage':deepcopy(actual['coverage']),
        'content_documents':len(blobs),'content_bytes':sum(map(len,blobs.values())),
        'actual_content_inventory':[{'sha256':name,'bytes':len(raw)} for name,raw in sorted(blobs.items())],
        'projection':'exact_additive_selection_CLI_source_individually_pinned_unimported_additions_exact_archived_unused_backend_exact_manager_registration_prefix_composed_package_metadata_witnessed_policy_dispatch_and_declared_argparse_runtime_counterpart_only; actual_bytes_retained'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    actual, blobs = capture_current.capture()
    receipt = verify_recapture(actual, blobs)
    receipt['runtime'] = {'python':sys.version,'platform':sys.platform,'executable':sys.executable,
                          'revision':os.environ.get('GITHUB_SHA')}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    path = args.output.with_name(args.output.stem+'-actual.json')
    frozen.write(actual,blobs,path)
    receipt['actual_capture_path'] = path.name
    args.output.write_bytes(canonical(receipt)+b'\n')
    print(json.dumps({key:receipt[key] for key in ('status','actual_inventory_fingerprint','coverage')},sort_keys=True))
    return 0


if __name__ == '__main__': raise SystemExit(main())
