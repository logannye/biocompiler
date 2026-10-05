"""Run the frozen reference tests in their exact, finite original source closure.

New product files are not original authority. Every captured file retains its
pinned bytes in the child. The finite reviewed Core and public route counterparts are
restored from an exact archived source; this never validates the current bridge
or refreshes an expectation. Native code is neither loaded nor run.
"""
from __future__ import annotations

import ast
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import MethodType

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'biocompiler.reference_original_counterpart.v1'
CORPUS = 'tests/conformance/reference-contracts-v1.json'
CORPUS_SHA = 'f0d3acadad15fbc29f195fc1a7dae875e8fb027565ec20fdbe1934fec7f3cf1b'
INVENTORY = '69c26f9329ec1d3a40e17a0a5f70d311611121d57b9b9f9962163678b1dc952c'
FREEZER = 'tools/freeze_reference_contracts.py'
FREEZER_SHA = '9f5696318883ada6e56d582cadff25e2431724e27ab27e28f3eabf864e0f1e1f'
TEST = 'tests/test_reference_contracts_corpus.py'
TEST_SHA = '84df82fd9a57d18ad022d68a318aeb3495ff0a724b1205a73cb8092d20c2133b'
RUNNER = 'tools/reference_original_counterpart.py'
CORE_SOURCE = 'src/biocompiler/core_pipeline_manager.py'
CALLBACK_SOURCE = 'src/biocompiler/core_pipeline_callback_session.py'
CALLBACK_ORIGINAL_SHA = '0ff388509eb9c123b87cf5decc1f35cf5eaca61a02d84a756beba7150de17018'
CALLBACK_PREVIOUS_SHA = '96cf3c4c70231f3039e2e16c51efc06bc202c86208f94dbddd5f438996c1bb5a'
CALLBACK_CURRENT_SHA = 'd24cb3b78df7b7c85d0bbec5cd3c7634ca4756c5e8b0e113a8a3ba7258229a54'
CALLBACK_BLOB = 'tests/conformance/reference-original-sources-v1/' + CALLBACK_ORIGINAL_SHA + '.blob'
CALLBACK_WITNESS = 'tests/conformance/reference-callback-source-counterpart-v1.json'
CALLBACK_WITNESS_SHA = 'e3be989e0a76913f64ec959d4354bb4a352c70e0bf661ca58df68db15e544b5c'
CALLBACK_DRAIN_WITNESS = 'tests/conformance/reference-callback-source-counterpart-v2.json'
CALLBACK_DRAIN_WITNESS_SHA = '878291d0b0e70db1f5e98611e103099d252ab3ffacf4995ae72ae73a9a9e16ce'
SESSION_SOURCE = 'src/biocompiler/core_pipeline_session.py'
SESSION_ORIGINAL_SHA = 'b0c744d8f3a38b1681805250ccf93884ba866678527cf366bcf08ff326da080d'
SESSION_CURRENT_SHA = '8de06056804e4e58350fa562c438acf2b6306a462edd9df3a1da2070f298d169'
SESSION_BLOB = 'tests/conformance/reference-original-sources-v1/' + SESSION_ORIGINAL_SHA + '.blob'
SESSION_WITNESS = 'tests/conformance/reference-session-source-counterpart-v1.json'
SESSION_WITNESS_SHA = '0ad1db1de89c118f74d8b0237e9ecad7e09da28d02931362332ac520fc911250'
CORE_ORIGINAL_SHA = '40a08477c97a97159372d9723267df3cacf8335a59d6b00ada34bb56470e31f3'
CORE_PREVIOUS_SHA = '0c0cfac138484cf71f1bb1303e66873b8b148ca236e07930fdbadd0b477a11be'
CORE_ROUTING_SHA = '18ee9bd517524b4440bcf29292a5d834470603713d662198b83ca61373c7fd09'
CORE_MERGED_SHA = '562052f3848c27ccb3fd19f156bd019da44aed58abe8cd4a2c7bd922ba07fc5b'
CORE_PRE_VIEW_SHA = 'f5c3410fb93d99182a1c5b9d8f3fa948990a0e1d4ce0b3b609c6b9f470d67bdd'
CORE_CURRENT_SHA = '44eeed2c22a9d07ff254dcd5b1e1edd26cf7e6bcfc29918ae20da39c2fbb544c'
CORE_PACKAGE_SHA = 'e70b302502bbae0cf274fb5dc420b276edf033189ea41cc3083575935f7119ba'
CALLBACK_PACKAGE_SHA = '963af95957f4a6c7843fca8f575ebe3817349b9ce0722c59da0cd64d21e9bc51'
CORE_VIEW_UPDATE = 'tests/conformance/reference-manager-source-counterpart-v5.json'
CORE_VIEW_UPDATE_SHA = '56e6f74417aab4de65eafdc4e7ca00a78db736c4b3ae8608be046a6340ce913d'
CORE_ATTEMPT_UPDATE = 'tests/conformance/reference-manager-source-counterpart-v4.json'
CORE_ATTEMPT_UPDATE_SHA = '7c17725b7d5e5843418dfea595b97aeb786ffc2ed2bf477d16db40012533c143'
CORE_BLOB = 'tests/conformance/reference-original-sources-v1/' + CORE_ORIGINAL_SHA + '.blob'
CORE_WITNESS = 'tests/conformance/reference-manager-source-counterpart-v1.json'
CORE_WITNESS_SHA = '9f4406d46a7d18db944094ea6875a1daceb3d327b2da8e8029250e312ea833f8'
CORE_UPDATE = 'tests/conformance/reference-manager-source-counterpart-v2.json'
CORE_UPDATE_SHA = 'd19d7e706876ac234e2f3e5a45c66ebbf9625599a880c15dec64595c1bbed8e4'
CORE_MERGE_UPDATE = 'tests/conformance/reference-manager-source-counterpart-v3.json'
CORE_MERGE_UPDATE_SHA = 'dd91ae7b9929f5806105245461a70874609781eb93a9dceffed53cfeffe13455'
ROUTE_WITNESS = 'tests/conformance/reference-public-routing-source-counterpart-v1.json'
ROUTE_WITNESS_SHA = '949bd00942bbaa8c6107c490692e38007e41309b0d8f22b0bccd4d8f8514f074'
ROUTE_SOURCES = ('src/biocompiler/compiler/construct.py', 'src/biocompiler/compiler/molecular.py')
# Imported by the frozen test_synthetic_generation fixture, but not included
# in its original source_inventory traversal. Entire bytes match c58aa504.
SUPPORT = {'examples/realization_check.py': '0d1012d2c3cd074540afce586658ee2ee3cba08a4e3d2e2586f8aaec1fa75fc2'}
TEST_MODULE = 'test_reference_contracts_corpus'
CLASS = 'ReferenceContractsCorpusTests'
HOOK = '''\n\ndef load_tests(loader, tests, pattern):
    from tools.reference_original_counterpart import original_test_suite
    return original_test_suite(loader, tests, pattern, __name__)
'''
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_DATA_BYTES = 64 * 1024 * 1024
MAX_RESULT_BYTES = 4 * 1024 * 1024


def require(value, message):
    if not value:
        raise AssertionError(message)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def local_file(root, logical):
    require(type(logical) is str and not Path(logical).is_absolute() and '..' not in Path(logical).parts,
            'Reference counterpart logical path escapes its source root')
    path = root / logical
    require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root.resolve()),
            'Reference counterpart source path is missing or redirected: ' + logical)
    return path


def authority():
    raw = local_file(ROOT, CORPUS).read_bytes()
    require(sha(raw) == CORPUS_SHA, 'Frozen reference corpus bytes differ')
    index = json.loads(raw)
    require(index['inventory_fingerprint'] == INVENTORY == sha(canonical(
        {key: value for key, value in index.items() if key != 'inventory_fingerprint'})),
        'Frozen reference inventory differs')
    require(len(index['source_files']) == 203 and len(index['documents']) == 4000,
            'Frozen reference closure census differs')
    return index


def core_view_source_witness(current, encoded=None):
    """Restore only the exact structural-view update before the unchanged v4 chain."""
    from tools.reference_package_source_lineage import restore
    current, _ = restore(CORE_SOURCE, current, root=ROOT)
    encoded = local_file(ROOT, CORE_VIEW_UPDATE).read_bytes() if encoded is None else encoded
    require(sha(encoded) == CORE_VIEW_UPDATE_SHA, 'Reference Core view source witness changed')
    witness = json.loads(encoded)
    require(set(witness) == {'schema_version', 'base_revision', 'path', 'original_sha256',
        'current_sha256', 'original_bytes', 'current_bytes', 'changes', 'scope', 'predecessor'} and
        witness['schema_version'] == 'biocompiler.reference_manager_source_counterpart.v5' and
        witness['base_revision'] == '0297d583d5774dc8991fda24c4f8fb39a277cc9a' and
        witness['path'] == CORE_SOURCE and witness['original_sha256'] == CORE_PRE_VIEW_SHA and
        witness['current_sha256'] == CORE_CURRENT_SHA and
        witness['original_bytes'] == 93594 and witness['current_bytes'] == 94893 and
        witness['predecessor'] == {'path': CORE_ATTEMPT_UPDATE, 'sha256': CORE_ATTEMPT_UPDATE_SHA} and
        witness['scope'] == 'Exact historical source restoration only; current structural view validation is separate',
        'Reference Core view source correspondence differs')
    require(type(current) is bytes and sha(current) == CORE_CURRENT_SHA and len(current) == 94893,
        'Captured reference Core source is outside its exact counterpart')
    changes = witness['changes']
    fields = ('old_start_line', 'old_end_line', 'new_start_line', 'new_end_line')
    require(type(changes) is list and len(changes) == 1 and type(changes[0]) is dict and
        set(changes[0]) == {*fields, 'before', 'after'} and
        all(type(changes[0][key]) is int for key in fields) and
        tuple(changes[0][key] for key in fields) == (112, 117, 112, 139) and
        type(changes[0]['before']) is str and type(changes[0]['after']) is str,
        'Reference Core view exact source span census differs')
    change = changes[0]
    lines = current.decode().splitlines(keepends=True)
    require(''.join(lines[111:139]) == change['after'] and
        len(change['before'].splitlines(keepends=True)) == 6,
        'Reference Core view complete source span differs')
    lines[111:139] = change['before'].splitlines(keepends=True)
    restored = ''.join(lines).encode()
    require(len(restored) == 93594 and sha(restored) == CORE_PRE_VIEW_SHA,
        'Reference Core view whole preceding source differs')
    return restored, {'path': CORE_VIEW_UPDATE, 'sha256': CORE_VIEW_UPDATE_SHA,
                      'correspondence': witness}


def core_source_witness(raw=None):
    """One exact reviewed transport revision, never a changed-file whitelist."""
    encoded = local_file(ROOT, CORE_WITNESS).read_bytes()
    require(sha(encoded) == CORE_WITNESS_SHA, 'Reference Core source witness changed')
    witness = json.loads(encoded)
    require(set(witness) == {'schema_version', 'base_revision', 'path', 'original_sha256',
        'current_sha256', 'changes', 'restoration'} and
        witness['schema_version'] == 'biocompiler.reference_manager_source_counterpart.v1' and
        witness['base_revision'] == 'a8cf5266963abfb5beae408c296a6f626e8f51fe' and
        witness['path'] == CORE_SOURCE and witness['original_sha256'] == CORE_ORIGINAL_SHA and
        witness['current_sha256'] == CORE_PREVIOUS_SHA and len(witness['changes']) == 6,
        'Reference Core source correspondence is not the closed reviewed revision')
    current = local_file(ROOT, CORE_SOURCE).read_bytes() if raw is None else raw
    current, view_update = core_view_source_witness(current)
    require(type(current) is bytes and sha(current) == CORE_PRE_VIEW_SHA,
            'Captured reference Core source is outside its exact counterpart')
    attempt_raw = local_file(ROOT, CORE_ATTEMPT_UPDATE).read_bytes()
    require(sha(attempt_raw) == CORE_ATTEMPT_UPDATE_SHA, 'Reference Core attempt witness changed')
    attempt = json.loads(attempt_raw)
    require(set(attempt) == {'schema_version', 'base_revision', 'path', 'original_sha256',
        'current_sha256', 'predecessor', 'changes', 'restoration'} and
        attempt['schema_version'] == 'biocompiler.reference_manager_source_counterpart.v4' and
        attempt['base_revision'] == '7645c254b170846cca2289090111241e20c3769d' and attempt['path'] == CORE_SOURCE and
        attempt['original_sha256'] == CORE_MERGED_SHA and attempt['current_sha256'] == CORE_PRE_VIEW_SHA and
        attempt['predecessor'] == {'path': CORE_MERGE_UPDATE, 'sha256': CORE_MERGE_UPDATE_SHA} and
        len(attempt['changes']) == 1, 'Reference Core attempt update differs from its exact predecessor')
    change = attempt['changes'][0]
    require(set(change) == {'old_start_line', 'old_end_line', 'new_start_line', 'new_end_line', 'before', 'after'} and
        all(type(change[key]) is int and change[key] == 44 for key in
            ('old_start_line', 'old_end_line', 'new_start_line', 'new_end_line')) and
        type(change['before']) is str and type(change['after']) is str and
        change['before'].startswith('_APPLICATION_JSON = ') and change['after'].startswith('_APPLICATION_JSON = '),
        'Reference Core attempt update is not the exact application declaration assignment')
    lines = current.decode().splitlines(keepends=True)
    require(lines[43] == change['after'], 'Reference Core attempt complete declaration differs')
    lines[43:44] = change['before'].splitlines(keepends=True)
    current = ''.join(lines).encode()
    require(sha(current) == CORE_MERGED_SHA, 'Reference Core pre-attempt whole source restoration differs')
    merge_raw = local_file(ROOT, CORE_MERGE_UPDATE).read_bytes()
    require(sha(merge_raw) == CORE_MERGE_UPDATE_SHA, 'Reference Core ordered-merge witness changed')
    merge = json.loads(merge_raw)
    require(set(merge) == {'schema_version', 'base_revision', 'path', 'original_sha256',
        'current_sha256', 'predecessor', 'changes', 'restoration'} and
        merge['schema_version'] == 'biocompiler.reference_manager_source_counterpart.v3' and
        merge['base_revision'] == '28d2b2ceb119015e5743819bab695e02e4d6b9a9' and
        merge['path'] == CORE_SOURCE and merge['original_sha256'] == CORE_ROUTING_SHA and
        merge['current_sha256'] == CORE_MERGED_SHA and
        merge['predecessor'] == {'path': CORE_UPDATE, 'sha256': CORE_UPDATE_SHA} and
        len(merge['changes']) == 4, 'Reference Core ordered merge is outside its exact counterpart')
    lines = current.decode().splitlines(keepends=True)
    require([(row['old_start_line'], row['old_end_line'], row['new_start_line'], row['new_end_line'])
        for row in merge['changes']] == [(44, 44, 44, 44), (271, 271, 271, 271), (882, 882, 882, 883), (929, 929, 930, 947)],
        'Reference Core ordered-merge source spans differ')
    for change in reversed(merge['changes']):
        require(set(change) == {'old_start_line', 'old_end_line', 'new_start_line', 'new_end_line', 'before', 'after'}
            and type(change['before']) is str and type(change['after']) is str and
            ''.join(lines[change['new_start_line'] - 1:change['new_end_line']]) == change['after'],
            'Reference Core ordered-merge complete source span differs')
        lines[change['new_start_line'] - 1:change['new_end_line']] = change['before'].splitlines(keepends=True)
    current = ''.join(lines).encode()
    require(sha(current) == CORE_ROUTING_SHA, 'Reference Core pre-merge whole source restoration differs')
    updated = local_file(ROOT, CORE_UPDATE).read_bytes()
    require(sha(updated) == CORE_UPDATE_SHA, 'Reference Core source update witness changed')
    update = json.loads(updated)
    require(set(update) == {'schema_version', 'base_revision', 'path', 'original_sha256',
        'current_sha256', 'predecessor', 'changes', 'restoration'} and
        update['schema_version'] == 'biocompiler.reference_manager_source_counterpart.v2' and
        update['base_revision'] == 'e73743bc2f17597b57ac15869986255802289615' and
        update['path'] == CORE_SOURCE and update['original_sha256'] == CORE_PREVIOUS_SHA and
        update['current_sha256'] == CORE_ROUTING_SHA and
        update['predecessor'] == {'path': CORE_WITNESS, 'sha256': CORE_WITNESS_SHA} and
        len(update['changes']) == 1, 'Reference Core update is outside its exact counterpart')
    change = update['changes'][0]
    require(set(change) == {'old_start_line', 'old_end_line', 'new_start_line', 'new_end_line', 'before', 'after'} and
        change['old_start_line'] == change['old_end_line'] == change['new_start_line'] == change['new_end_line'] == 44 and
        change['before'].startswith('_APPLICATION_JSON = ') and change['after'].startswith('_APPLICATION_JSON = '),
        'Reference Core update is not the exact application declaration assignment')
    current_lines = current.decode().splitlines(keepends=True)
    require(current_lines[43] == change['after'], 'Reference Core update complete source span differs')
    current_lines[43:44] = change['before'].splitlines(keepends=True)
    previous = ''.join(current_lines).encode()
    require(sha(previous) == CORE_PREVIOUS_SHA, 'Reference Core preceding whole source restoration differs')
    archived = local_file(ROOT, CORE_BLOB).read_bytes()
    require(sha(archived) == CORE_ORIGINAL_SHA, 'Original reference Core archive changed')
    lines = previous.decode().splitlines(keepends=True)
    original_lines = archived.decode().splitlines(keepends=True)
    previous = 0
    for change in witness['changes']:
        require(set(change) == {'old_start_line', 'old_end_line', 'new_start_line', 'new_end_line', 'before', 'after'}
            and all(type(change[key]) is int for key in ('old_start_line', 'old_end_line', 'new_start_line', 'new_end_line'))
            and type(change['before']) is str and type(change['after']) is str
            and previous < change['new_start_line'] <= change['new_end_line'],
            'Reference Core exact source spans overlap or changed')
        previous = change['new_end_line']
        require(''.join(lines[change['new_start_line'] - 1:change['new_end_line']]) == change['after']
            and ''.join(original_lines[change['old_start_line'] - 1:change['old_end_line']]) == change['before'],
            'Reference Core complete source span differs')
    for change in reversed(witness['changes']):
        lines[change['new_start_line'] - 1:change['new_end_line']] = change['before'].splitlines(keepends=True)
    require(''.join(lines).encode() == archived, 'Reference Core restoration differs from entire archived source')
    return archived, {'path': CORE_SOURCE, 'archive': CORE_BLOB, 'archive_sha256': CORE_ORIGINAL_SHA,
        'current_sha256': CORE_PACKAGE_SHA, 'witness': CORE_WITNESS, 'witness_sha256': CORE_WITNESS_SHA,
        'correspondence': witness, 'update': {'path': CORE_UPDATE, 'sha256': CORE_UPDATE_SHA, 'correspondence': update},
        'attempt_update': {'path': CORE_ATTEMPT_UPDATE, 'sha256': CORE_ATTEMPT_UPDATE_SHA, 'correspondence': attempt},
        'view_update': view_update,
        'ordered_merge_update': {'path': CORE_MERGE_UPDATE, 'sha256': CORE_MERGE_UPDATE_SHA, 'correspondence': merge},
        'scope': 'original source execution only; current native bridge validation is separate'}


def callback_drain_source_witness(current, encoded=None):
    """Undo only the exact buffered-close correction before the frozen v1 proof."""
    from tools.reference_package_source_lineage import restore
    current, _ = restore(CALLBACK_SOURCE, current, root=ROOT)
    encoded = local_file(ROOT, CALLBACK_DRAIN_WITNESS).read_bytes() if encoded is None else encoded
    require(sha(encoded) == CALLBACK_DRAIN_WITNESS_SHA, 'Reference callback drain source witness changed')
    witness = json.loads(encoded)
    require(set(witness) == {'schema_version', 'base_revision', 'path', 'original_sha256',
        'current_sha256', 'original_bytes', 'current_bytes', 'changes', 'scope', 'predecessor'} and
        witness['schema_version'] == 'biocompiler.reference_callback_source_counterpart.v2' and
        witness['base_revision'] == '4baaaf7e6e19ef9138372746495ef4e0fa51b71f' and
        witness['path'] == CALLBACK_SOURCE and witness['original_sha256'] == CALLBACK_PREVIOUS_SHA and
        witness['current_sha256'] == CALLBACK_CURRENT_SHA and
        witness['original_bytes'] == 32588 and witness['current_bytes'] == 32785 and
        witness['predecessor'] == {'path': CALLBACK_WITNESS, 'sha256': CALLBACK_WITNESS_SHA} and
        witness['scope'] == 'Exact historical source restoration only; current transport validation is separate',
        'Reference callback drain source correspondence differs')
    require(type(current) is bytes and sha(current) == CALLBACK_CURRENT_SHA and len(current) == 32785,
        'Captured reference callback source is outside its exact counterpart')
    changes = witness['changes']
    fields = ('old_start_line', 'old_end_line', 'new_start_line', 'new_end_line')
    require(type(changes) is list and len(changes) == 1 and type(changes[0]) is dict and
        set(changes[0]) == {*fields, 'before', 'after'} and
        all(type(changes[0][key]) is int for key in fields) and
        tuple(changes[0][key] for key in fields) == (355, 355, 355, 358) and
        type(changes[0]['before']) is str and type(changes[0]['after']) is str,
        'Reference callback drain exact source span census differs')
    change = changes[0]
    lines = current.decode().splitlines(keepends=True)
    require(''.join(lines[354:358]) == change['after'] and
        len(change['before'].splitlines(keepends=True)) == 1,
        'Reference callback drain complete source span differs')
    lines[354:358] = change['before'].splitlines(keepends=True)
    restored = ''.join(lines).encode()
    require(len(restored) == 32588 and sha(restored) == CALLBACK_PREVIOUS_SHA,
        'Reference callback drain whole preceding source differs')
    return restored, {'path': CALLBACK_DRAIN_WITNESS, 'sha256': CALLBACK_DRAIN_WITNESS_SHA,
                      'correspondence': witness}


def callback_source_witness(raw=None):
    """Restore one exact resource-profile update to its whole archived client."""
    encoded = local_file(ROOT, CALLBACK_WITNESS).read_bytes()
    require(sha(encoded) == CALLBACK_WITNESS_SHA, 'Reference callback source witness changed')
    witness = json.loads(encoded)
    require(set(witness) == {'schema_version', 'base_revision', 'path', 'original_sha256',
        'current_sha256', 'original_bytes', 'current_bytes', 'changes', 'scope'} and
        witness['schema_version'] == 'biocompiler.reference_callback_source_counterpart.v1' and
        witness['base_revision'] == 'b27f52447f49c749d33cac17f3bbb6fe772cbc24' and
        witness['path'] == CALLBACK_SOURCE and witness['original_sha256'] == CALLBACK_ORIGINAL_SHA and
        witness['current_sha256'] == CALLBACK_PREVIOUS_SHA and
        witness['scope'] == 'Exact historical source restoration only; current resource profile validation is separate',
        'Reference callback source correspondence differs')
    current = local_file(ROOT, CALLBACK_SOURCE).read_bytes() if raw is None else raw
    current, drain_update = callback_drain_source_witness(current)
    archived = local_file(ROOT, CALLBACK_BLOB).read_bytes()
    require(type(current) is bytes and sha(current) == CALLBACK_PREVIOUS_SHA and
        len(current) == witness['current_bytes'], 'Captured reference callback source is outside its exact counterpart')
    require(sha(archived) == CALLBACK_ORIGINAL_SHA and len(archived) == witness['original_bytes'],
        'Original reference callback archive changed')
    changes = witness['changes']
    fields = ('old_start_line', 'old_end_line', 'new_start_line', 'new_end_line')
    require(type(changes) is list and len(changes) == 8 and all(type(row) is dict and
        set(row) == {*fields, 'before', 'after'} and all(type(row[key]) is int for key in fields) and
        type(row['before']) is str and type(row['after']) is str for row in changes) and
        [tuple(row[key] for key in fields) for row in changes] ==
        [(31, 31, 31, 31), (33, 33, 33, 33), (309, 309, 309, 309), (377, 376, 377, 379),
         (380, 380, 383, 383), (411, 411, 414, 414), (421, 421, 424, 425), (430, 430, 434, 435)],
        'Reference callback exact source span census differs')
    lines, original = current.decode().splitlines(keepends=True), archived.decode().splitlines(keepends=True)
    for row in changes:
        require(''.join(lines[row['new_start_line']-1:row['new_end_line']]) == row['after'] and
            ''.join(original[row['old_start_line']-1:row['old_end_line']]) == row['before'],
            'Reference callback complete source span differs')
    for row in reversed(changes):
        lines[row['new_start_line']-1:row['new_end_line']] = row['before'].splitlines(keepends=True)
    require(''.join(lines).encode() == archived, 'Reference callback restoration differs from entire archived source')
    return archived, {'path': CALLBACK_SOURCE, 'archive': CALLBACK_BLOB, 'archive_sha256': CALLBACK_ORIGINAL_SHA,
        'current_sha256': CALLBACK_PACKAGE_SHA, 'witness': CALLBACK_WITNESS, 'witness_sha256': CALLBACK_WITNESS_SHA,
        'correspondence': witness, 'buffered_close_update': drain_update, 'scope': witness['scope']}


def session_source_witness(raw=None, encoded=None):
    """Restore the exact buffered-exit edit to the frozen whole session module."""
    encoded = local_file(ROOT, SESSION_WITNESS).read_bytes() if encoded is None else encoded
    require(sha(encoded) == SESSION_WITNESS_SHA, 'Reference session source witness changed')
    witness = json.loads(encoded)
    require(set(witness) == {'schema_version', 'base_revision', 'path', 'original_sha256',
        'current_sha256', 'original_bytes', 'current_bytes', 'changes', 'scope'} and
        witness['schema_version'] == 'biocompiler.reference_session_source_counterpart.v1' and
        witness['base_revision'] == '0297d583d5774dc8991fda24c4f8fb39a277cc9a' and
        witness['path'] == SESSION_SOURCE and witness['original_sha256'] == SESSION_ORIGINAL_SHA and
        witness['current_sha256'] == SESSION_CURRENT_SHA and
        witness['original_bytes'] == 33907 and witness['current_bytes'] == 34104 and
        witness['scope'] == 'Exact historical source restoration only; current session transport validation is separate',
        'Reference session source correspondence differs')
    current = local_file(ROOT, SESSION_SOURCE).read_bytes() if raw is None else raw
    require(type(current) is bytes and sha(current) == SESSION_CURRENT_SHA and len(current) == 34104,
        'Captured reference session source is outside its exact counterpart')
    changes = witness['changes']
    fields = ('old_start_line', 'old_end_line', 'new_start_line', 'new_end_line')
    require(type(changes) is list and len(changes) == 1 and type(changes[0]) is dict and
        set(changes[0]) == {*fields, 'before', 'after'} and
        all(type(changes[0][key]) is int for key in fields) and
        tuple(changes[0][key] for key in fields) == (418, 418, 418, 421) and
        type(changes[0]['before']) is str and type(changes[0]['after']) is str,
        'Reference session exact source span census differs')
    change = changes[0]
    lines = current.decode().splitlines(keepends=True)
    require(''.join(lines[417:421]) == change['after'] and
        len(change['before'].splitlines(keepends=True)) == 1,
        'Reference session complete source span differs')
    lines[417:421] = change['before'].splitlines(keepends=True)
    restored = ''.join(lines).encode()
    archived = local_file(ROOT, SESSION_BLOB).read_bytes()
    require(len(archived) == 33907 and sha(archived) == SESSION_ORIGINAL_SHA and restored == archived,
        'Reference session restoration differs from whole original source')
    return archived, {'path': SESSION_SOURCE, 'archive': SESSION_BLOB, 'archive_sha256': SESSION_ORIGINAL_SHA,
        'current_sha256': SESSION_CURRENT_SHA, 'witness': SESSION_WITNESS, 'witness_sha256': SESSION_WITNESS_SHA,
        'correspondence': witness, 'scope': witness['scope']}


def route_source_witness(logical, raw=None):
    """Remove only the two pinned five-line public entry prefixes."""
    require(logical in ROUTE_SOURCES, 'Unknown reference route source')
    encoded = local_file(ROOT, ROUTE_WITNESS).read_bytes()
    require(sha(encoded) == ROUTE_WITNESS_SHA, 'Reference public route witness changed')
    witness = json.loads(encoded)
    require(witness['schema'] == 'biocompiler.reference_public_routing_source_counterpart.v1' and
        witness['base_revision'] == 'e73743bc2f17597b57ac15869986255802289615' and
        set(witness['entrypoint_prefixes']) == set(ROUTE_SOURCES), 'Reference route correspondence differs')
    entry = witness['entrypoint_prefixes'][logical]
    current = local_file(ROOT, logical).read_bytes() if raw is None else raw
    require(type(current) is bytes and len(current) == entry['current_bytes'] and sha(current) == entry['current_sha256'],
        'Captured reference route source is outside its exact counterpart')
    insertion = entry['insertion']
    offset, prefix = insertion['byte_offset'], insertion['text'].encode()
    require(type(offset) is int and offset >= 0 and current[offset:offset + len(prefix)] == prefix and
        len(prefix.splitlines()) == 5, 'Reference route prefix differs')
    original = current[:offset] + current[offset + len(prefix):]
    require(len(original) == entry['original_bytes'] and sha(original) == entry['original_sha256'],
        'Reference route whole source restoration differs')
    return original, {'path': logical, 'witness': ROUTE_WITNESS, 'witness_sha256': ROUTE_WITNESS_SHA,
        'correspondence': entry, 'scope': 'original source execution only; current public routing validation is separate'}


def test_witness(raw=None):
    current = local_file(ROOT, TEST).read_bytes() if raw is None else raw
    require(type(current) is bytes, 'Original reference test source must be bytes')
    if sha(current) == TEST_SHA:
        original, hooked = current, False
    else:
        hook = HOOK.encode()
        require(current.count(hook) == 1 and current.endswith(hook),
                'Reference test has an unreviewed bridge extension')
        original, hooked = current[:-len(hook)], True
        require(sha(original) == TEST_SHA, 'Reference test bodies differ from their whole original source')
    return {'original_sha256': TEST_SHA, 'current_sha256': sha(current),
            'original_source': original.decode(), 'current_source': current.decode(),
            'hook': HOOK if hooked else None}


def method_names():
    tree = ast.parse(test_witness()['original_source'])
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == CLASS)
    result = sorted(node.name for node in cls.body if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'))
    require(len(result) == 8, 'Original reference test method census differs')
    return result


def selection(module, ids):
    require(module in (TEST_MODULE, 'tests.' + TEST_MODULE), 'Unknown reference counterpart test module')
    available = [module + '.' + CLASS + '.' + method for method in method_names()]
    ids = available if ids is None else ids
    require(type(ids) is list and ids == available,
            'Original reference test selection is missing, duplicated or reordered')
    return ids


def data_closure(index):
    from tools.reference_package_source_lineage import PUBLIC_WITNESS, PUBLIC_PIN, TRANSPORT_WITNESS, TRANSPORT_PIN
    from tools.policy_entrypoint_source_lineage import WITNESS as POLICY_WITNESS, WITNESS_SHA256 as POLICY_PIN
    result = [{'logical': CORPUS, 'sha256': CORPUS_SHA, 'bytes': len(local_file(ROOT, CORPUS).read_bytes())}]
    for identity, row in sorted(index['documents'].items()):
        logical = 'tests/conformance/reference-contracts-v1/' + identity + '.json'
        require(row['path'] == logical, 'Frozen reference document path differs')
        raw = local_file(ROOT, logical).read_bytes()
        require(len(raw) == row['bytes'] and raw.endswith(b'\n') and sha(raw[:-1]) == identity,
                'Frozen complete reference document bytes differ')
        result.append({'logical': logical, 'sha256': sha(raw), 'bytes': len(raw)})
    for logical, identity in ((POLICY_WITNESS, POLICY_PIN), (PUBLIC_WITNESS, PUBLIC_PIN), (TRANSPORT_WITNESS, TRANSPORT_PIN),
                              (CORE_BLOB, CORE_ORIGINAL_SHA), (CORE_WITNESS, CORE_WITNESS_SHA),
                              (CORE_UPDATE, CORE_UPDATE_SHA), (CORE_MERGE_UPDATE, CORE_MERGE_UPDATE_SHA),
                              (CORE_ATTEMPT_UPDATE, CORE_ATTEMPT_UPDATE_SHA), (CORE_VIEW_UPDATE, CORE_VIEW_UPDATE_SHA),
                              (ROUTE_WITNESS, ROUTE_WITNESS_SHA),
                              (CALLBACK_BLOB, CALLBACK_ORIGINAL_SHA), (CALLBACK_WITNESS, CALLBACK_WITNESS_SHA),
                              (CALLBACK_DRAIN_WITNESS, CALLBACK_DRAIN_WITNESS_SHA),
                              (SESSION_BLOB, SESSION_ORIGINAL_SHA), (SESSION_WITNESS, SESSION_WITNESS_SHA)):
        raw = local_file(ROOT, logical).read_bytes()
        require(sha(raw) == identity, 'Reference exact Core counterpart data changed')
        result.append({'logical': logical, 'sha256': identity, 'bytes': len(raw)})
    require(sum(row['bytes'] for row in result) <= MAX_DATA_BYTES, 'Reference counterpart data copy exceeds bound')
    return result


def source_closure(index, package_root):
    from tools.policy_entrypoint_source_lineage import PATHS as POLICY_ROUTES, restore as restore_policy
    from tools.reference_package_source_lineage import PUBLIC, restore
    values = {}
    pins = index['source_files'] | {FREEZER: FREEZER_SHA} | SUPPORT
    for logical, identity in sorted(pins.items()):
        path = local_file(ROOT, logical)
        raw = path.read_bytes()
        if logical == CORE_SOURCE:
            require(identity == CORE_ORIGINAL_SHA, 'Frozen reference Core authority changed')
            copied, _ = core_source_witness(raw)
        elif logical == CALLBACK_SOURCE:
            require(identity == CALLBACK_ORIGINAL_SHA, 'Frozen reference callback authority changed')
            copied, _ = callback_source_witness(raw)
        elif logical == SESSION_SOURCE:
            require(identity == SESSION_ORIGINAL_SHA, 'Frozen reference session authority changed')
            copied, _ = session_source_witness(raw)
        elif logical in ROUTE_SOURCES:
            copied, _ = route_source_witness(logical, raw)
            require(sha(copied) == identity, 'Frozen reference public route authority changed')
        elif logical in POLICY_ROUTES:
            copied, _ = restore_policy(logical, raw, root=ROOT)
            require(sha(copied) == identity, 'Frozen policy entrypoint source authority changed')
        elif logical in PUBLIC:
            copied, _ = restore(logical, raw, root=ROOT)
            require(sha(copied) == identity, 'Frozen package public source authority changed')
        else:
            require(sha(raw) == identity, 'Captured reference source bytes changed: ' + logical)
            copied = raw
        if logical.startswith('src/biocompiler/'):
            path = local_file(package_root, logical.removeprefix('src/biocompiler/'))
            require(path.read_bytes() == raw, 'Installed captured reference source bytes differ: ' + logical)
        values[logical] = (path, raw, copied)
    witness = test_witness()
    values[TEST] = (local_file(ROOT, TEST), witness['current_source'].encode(), witness['original_source'].encode())
    path = local_file(ROOT, RUNNER)
    values[RUNNER] = (path, path.read_bytes(), path.read_bytes())
    require(sum(len(raw) for _, raw, _ in values.values()) <= MAX_SOURCE_BYTES, 'Reference counterpart source copy exceeds bound')
    require(len(values) == 207, 'Reference counterpart complete source census differs')
    return values, witness


def run(*, test_module=TEST_MODULE, test_ids=None):
    ids = selection(test_module, test_ids)
    index = authority()
    package = importlib.import_module('biocompiler')
    package_root = Path(package.__file__).resolve().parent
    sources, witness = source_closure(index, package_root)
    data = data_closure(index)
    with tempfile.TemporaryDirectory(prefix='biocompiler-reference-original-') as directory:
        overlay = Path(directory).resolve()
        rows = []
        for logical, (origin, current, copied) in sorted(sources.items()):
            target = overlay / logical
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(copied)
            rows.append({'logical': logical, 'origin': str(origin), 'origin_sha256': sha(current),
                         'path': str(target), 'sha256': sha(copied), 'substituted': current != copied})
        for row in data:
            target = overlay / row['logical']
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(local_file(ROOT, row['logical']), target)
        manifest = {'schema': SCHEMA, 'root': str(overlay), 'package_root': str(package_root),
                    'test_module': test_module, 'test_ids': ids, 'sources': rows, 'data': data,
                    'test_witness': witness, 'source_inventory': index['source_files'],
                    'core_source_witness': core_source_witness()[1],
                    'callback_source_witness': callback_source_witness()[1],
                    'session_source_witness': session_source_witness()[1],
                    'route_source_witnesses': [route_source_witness(path)[1] for path in ROUTE_SOURCES]}
        (overlay / 'manifest.json').write_bytes(canonical(manifest))
        script = ('import sys;sys.path[:0]=[sys.argv[1],sys.argv[1]+"/src",sys.argv[1]+"/tests"];'
                  'from tools.reference_original_counterpart import child;child(sys.argv[1])')
        environment = dict(os.environ)
        environment.pop('PYTHONPATH', None)
        completed = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(overlay)],
            cwd=overlay, env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        require(completed.returncode == 0, 'Original reference child failed: ' + completed.stderr.decode(errors='replace')[-12000:])
        output = overlay / 'result.json'
        require(output.is_file() and output.stat().st_size <= MAX_RESULT_BYTES, 'Original reference child result is missing or too large')
        receipt = json.loads(output.read_bytes())
        try:
            validate(receipt)
        except AssertionError as error:
            raise AssertionError(str(error) + '\n' + completed.stderr.decode(errors='replace')[-12000:]) from error
        return receipt


def outcomes(value, ids, classname):
    require(type(value) is dict and set(value) == {'test_ids', 'tests', 'outcomes'} and
            value['test_ids'] == ids and value['tests'] == len(ids), 'Original reference execution census differs')
    rows = value['outcomes']
    require(type(rows) is list and [row['id'] for row in rows] == ids,
            'Original reference outcomes are missing, duplicated or reordered')
    for row in rows:
        require(set(row) == {'id', 'class', 'status', 'detail'} and row['class'] == classname and
                row['status'] in ('success', 'failure', 'error', 'skipped', 'expected-failure', 'unexpected-success') and
                (row['detail'] is None or type(row['detail']) is str), 'Original reference outcome identity or status differs')
    return {row['id']: row for row in rows}


def validate(receipt):
    require(type(receipt) is dict and set(receipt) == {'manifest', 'modules', 'source_inventory', 'value'},
            'Malformed original reference receipt')
    manifest = receipt['manifest']
    require(type(manifest) is dict and set(manifest) == {'schema', 'root', 'package_root', 'test_module', 'test_ids',
            'sources', 'data', 'test_witness', 'source_inventory', 'core_source_witness', 'callback_source_witness',
            'session_source_witness', 'route_source_witnesses'} and manifest['schema'] == SCHEMA,
            'Malformed original reference manifest')
    root, package_root = Path(manifest['root']), Path(manifest['package_root'])
    require(root.is_absolute() and package_root.is_absolute(), 'Original reference roots differ')
    current_package = Path(importlib.import_module('biocompiler').__file__).resolve().parent
    require(package_root == current_package, 'Original reference installed package origin differs')
    ids = selection(manifest['test_module'], manifest['test_ids'])
    index = authority()
    sources, witness = source_closure(index, package_root)
    require(manifest['core_source_witness'] == core_source_witness()[1],
            'Original reference Core source correspondence differs')
    require(manifest['callback_source_witness'] == callback_source_witness()[1],
            'Original reference callback source correspondence differs')
    require(manifest['session_source_witness'] == session_source_witness()[1],
            'Original reference session source correspondence differs')
    require(manifest['route_source_witnesses'] == [route_source_witness(path)[1] for path in ROUTE_SOURCES],
            'Original reference public route correspondence differs')
    require(manifest['test_witness'] == witness, 'Original reference whole-test correspondence differs')
    expected = []
    for logical, (origin, current, copied) in sorted(sources.items()):
        expected.append({'logical': logical, 'origin': str(origin), 'origin_sha256': sha(current),
                         'path': str(root / logical), 'sha256': sha(copied), 'substituted': current != copied})
    require(manifest['sources'] == expected, 'Original reference source/copy census differs')
    require(manifest['data'] == data_closure(index), 'Original reference complete document census differs')
    require(receipt['source_inventory'] == manifest['source_inventory'] == index['source_files'],
            'Original reference executed source closure differs')
    rows = {row['logical']: row for row in expected}
    modules = receipt['modules']
    mandatory = {'biocompiler', 'biocompiler.compiler.pipeline', 'biocompiler.registry.references',
        'biocompiler.ir.construct', 'biocompiler.ir.molecular', 'biocompiler.verification.construct',
        'biocompiler.verification.molecular', 'examples.realization_check', manifest['test_module']}
    require(type(modules) is dict and mandatory <= set(modules), 'Original reference canonical module census differs')
    for name, module in modules.items():
        require(type(module) is dict and set(module) == {'logical', 'path', 'sha256', 'namespace'},
                'Malformed original reference module authority')
        logical = module['logical']
        require(logical in rows and module['path'] == rows[logical]['path'] and
                module['sha256'] == rows[logical]['sha256'] and module['namespace'] == name,
                'Original reference loaded module source differs')
        if name == manifest['test_module']:
            require(logical == TEST, 'Original reference test module differs')
        elif name == 'examples.realization_check':
            require(logical == 'examples/realization_check.py', 'Original reference supporting fixture module differs')
        else:
            require(logical.startswith('src/biocompiler/') and name == logical.removeprefix('src/').removesuffix('.py')
                    .replace('/', '.').removesuffix('.__init__'), 'Original reference product namespace differs')
    outcomes(receipt['value'], ids, manifest['test_module'] + '.' + CLASS)
    return receipt['value']


def leaves(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from leaves(item)
        else:
            yield item


def child(directory):
    overlay = Path(directory).resolve()
    require(overlay == ROOT, 'Original reference runner escaped its snapshot')
    manifest = json.loads((overlay / 'manifest.json').read_bytes())
    for row in manifest['sources'] + manifest['data']:
        require(sha(local_file(overlay, row['logical']).read_bytes()) == row['sha256'],
                'Original reference copied bytes differ')
    require(sha(local_file(overlay, TEST).read_bytes()) == TEST_SHA, 'Original reference test body was not restored')
    require(sha(local_file(overlay, FREEZER).read_bytes()) == FREEZER_SHA, 'Original reference freezer changed')
    module = importlib.import_module(manifest['test_module'])
    discovered = list(leaves(unittest.defaultTestLoader.loadTestsFromModule(module)))
    selected = [case for case in discovered if case.id() in manifest['test_ids']]
    require([case.id() for case in selected] == manifest['test_ids'] and
            all(type(case) is getattr(module, CLASS) for case in selected), 'Original reference selected TestCases differ')

    class RetainedResult(unittest.TextTestResult):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.outcomes = []

        def retain(self, test, status, detail=None):
            self.outcomes.append({'id': test.id(), 'class': type(test).__module__ + '.' + type(test).__qualname__,
                                  'status': status, 'detail': detail})

        def addSuccess(self, test):
            super().addSuccess(test); self.retain(test, 'success')

        def addError(self, test, error):
            super().addError(test, error); self.retain(test, 'error', self._exc_info_to_string(error, test))

        def addFailure(self, test, error):
            super().addFailure(test, error); self.retain(test, 'failure', self._exc_info_to_string(error, test))

        def addSkip(self, test, reason):
            super().addSkip(test, reason); self.retain(test, 'skipped', reason)

        def addExpectedFailure(self, test, error):
            super().addExpectedFailure(test, error); self.retain(test, 'expected-failure', self._exc_info_to_string(error, test))

        def addUnexpectedSuccess(self, test):
            super().addUnexpectedSuccess(test); self.retain(test, 'unexpected-success')

    result = unittest.TextTestRunner(stream=sys.stderr, resultclass=RetainedResult).run(unittest.TestSuite(selected))
    value = {'test_ids': manifest['test_ids'], 'tests': result.testsRun, 'outcomes': result.outcomes}
    inventory = module.oracle.source_inventory()
    require(inventory == authority()['source_files'], 'Original reference fresh source inventory differs')
    rows = {row['logical']: row for row in manifest['sources']}
    modules = {}
    for name, loaded in tuple(sys.modules.items()):
        if name == 'biocompiler' or name.startswith('biocompiler.') or name in (manifest['test_module'], 'examples.realization_check'):
            path = Path(loaded.__file__).resolve()
            require(path.is_relative_to(overlay) and vars(loaded).get('__name__') == name,
                    'Original reference loaded module escaped canonical snapshot')
            logical = path.relative_to(overlay).as_posix()
            require(logical in rows and sha(path.read_bytes()) == rows[logical]['sha256'],
                    'Original reference loaded source bytes changed')
            modules[name] = {'logical': logical, 'path': str(path), 'sha256': rows[logical]['sha256'], 'namespace': name}
    for row in manifest['sources'] + manifest['data']:
        require(sha(local_file(overlay, row['logical']).read_bytes()) == row['sha256'],
                'Original reference source or expected documents changed during execution')
    (overlay / 'result.json').write_bytes(canonical({'manifest': manifest, 'modules': modules,
                                                   'source_inventory': inventory, 'value': value}))


def original_test_suite(loader, tests, pattern, module):
    """Retain actual discovered instances/classes; forward each real child outcome."""
    require(module in (TEST_MODULE, 'tests.' + TEST_MODULE), 'Unknown reference test bridge module')
    witness = test_witness()
    if witness['hook'] is None:
        return tests
    cases = list(leaves(tests))
    require(cases and len({type(case) for case in cases}) == 1, 'Original reference test class census differs')
    original = type(cases[0])
    require(original.__module__ == module and original.__qualname__ == CLASS and 'tearDownClass' not in vars(original),
            'Original reference class identity or fixtures changed')
    ids = selection(module, [case.id() for case in cases])
    classname = module + '.' + CLASS

    def setup(cls):
        receipt = run(test_module=module, test_ids=ids)
        cls._reference_original_receipt = receipt
        cls._reference_original_outcomes = outcomes(receipt['value'], ids, classname)

    original.setUpClass = classmethod(setup)

    def execute(self, result=None):
        own = result is None
        if own:
            result = self.defaultTestResult()
            result.startTestRun()
        result.startTest(self)
        try:
            row = type(self)._reference_original_outcomes[self.id()]
            status, detail = row['status'], row['detail']
            if status == 'success': result.addSuccess(self)
            elif status == 'skipped': result.addSkip(self, detail)
            elif status == 'unexpected-success': result.addUnexpectedSuccess(self)
            else:
                error = RuntimeError(detail) if status == 'error' else AssertionError(detail)
                info = (type(error), error, None)
                if status == 'error': result.addError(self, info)
                elif status == 'failure': result.addFailure(self, info)
                else: result.addExpectedFailure(self, info)
        finally:
            result.stopTest(self)
            if own: result.stopTestRun()
        return result

    for case in cases:
        case.run = MethodType(execute, case)
    return unittest.TestSuite(cases)
