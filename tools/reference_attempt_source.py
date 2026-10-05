"""Exact finite facade transport lineage; no historic result is imported."""
import ast
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'src/biocompiler/core_reference_manager.py'
WITNESS = 'tests/conformance/reference-attempt-facade-counterpart-v1.json'
PIN = '23d5cdd16455f81ad50de6a4f6931a2a3505dda089f28a105bc572ab558a571e'
OLD = '239fa3486751cfdc97e5f2e599a414562f3fba952b641169b4f04db0aab83772'
CURRENT = '188830c06e5865d65d4997558d602e9c28668e1d7f163693c515f306661c22f2'
TARGET_WITNESS = 'tests/conformance/reference-attempt-facade-counterpart-v2.json'
TARGET_PIN = 'ba2d5af2383bd91473425d40f3991564cdaf4f9407989bb294cfe9c987ba71af'
TARGET_CURRENT = 'cd75fca7e114b76ea42dfe433c399f175e6402ea7270f00e5ed5982d584bbd31'

def require(value, message):
    if not value: raise AssertionError(message)

def sha(value): return hashlib.sha256(value).hexdigest()

def restore_attempt(current):
    require(type(current) is bytes and sha(current) == CURRENT, 'Unreviewed current Molecular attempt facade')
    path = ROOT / WITNESS
    require(path.is_file() and not path.is_symlink(), 'Missing exact Molecular facade witness')
    raw = path.read_bytes()
    require(sha(raw) == PIN, 'Molecular facade witness bytes changed')
    witness = json.loads(raw)
    require(witness['path'] == SOURCE and witness['original_sha256'] == OLD and witness['current_sha256'] == CURRENT,
            'Molecular facade lineage identity differs')
    require(len(current) == witness['current_bytes'], 'Molecular facade current size differs')
    lines = current.decode().splitlines(keepends=True)
    for change in reversed(witness['changes']):
        start = change['current_start']; end = start + len(change['current_lines'])
        require(lines[start:end] == change['current_lines'], 'Molecular facade exact changed span differs')
        lines[start:end] = change['original_lines']
    original = ''.join(lines).encode()
    require(sha(original) == OLD and len(original) == witness['original_bytes'], 'Molecular facade whole-source restoration differs')
    ast.parse(original); ast.parse(current)
    return original, {'path':WITNESS,'sha256':PIN,'correspondence':witness}


def restore_targets(current, encoded=None):
    """Undo only the fixed-reference target identity addition before v1."""
    require(type(current) is bytes and sha(current) == TARGET_CURRENT,
            'Unreviewed current Molecular target facade')
    if encoded is None:
        path = ROOT / TARGET_WITNESS
        require(path.is_file() and not path.is_symlink(), 'Missing exact Molecular target witness')
        encoded = path.read_bytes()
    require(sha(encoded) == TARGET_PIN, 'Molecular target witness bytes changed')
    witness = json.loads(encoded)
    require(set(witness) == {'schema_version', 'base_revision', 'path', 'original_sha256',
        'current_sha256', 'original_bytes', 'current_bytes', 'changes', 'scope', 'predecessor'} and
        witness['schema_version'] == 'biocompiler.reference_attempt_facade_counterpart.v2' and
        witness['base_revision'] == '0297d583d5774dc8991fda24c4f8fb39a277cc9a' and
        witness['path'] == SOURCE and witness['original_sha256'] == CURRENT and
        witness['current_sha256'] == TARGET_CURRENT and
        witness['original_bytes'] == 43749 and witness['current_bytes'] == 45778 and
        witness['predecessor'] == {'path': WITNESS, 'sha256': PIN} and
        witness['scope'] == 'Exact historical source restoration only; current reference target identity validation is separate',
        'Molecular target lineage identity differs')
    require(len(current) == 45778, 'Molecular target current size differs')
    changes = witness['changes']
    fields = ('old_start_line', 'old_end_line', 'new_start_line', 'new_end_line')
    require(type(changes) is list and len(changes) == 2 and all(
        type(change) is dict and set(change) == {*fields, 'before', 'after'} and
        all(type(change[key]) is int for key in fields) and
        change['before'] == '' and type(change['after']) is str for change in changes) and
        [tuple(change[key] for key in fields) for change in changes] ==
        [(40, 39, 40, 71), (328, 327, 360, 360)],
        'Molecular target exact source span census differs')
    lines = current.decode().splitlines(keepends=True)
    for change in reversed(changes):
        start, end = change['new_start_line'] - 1, change['new_end_line']
        require(''.join(lines[start:end]) == change['after'], 'Molecular target exact changed span differs')
        del lines[start:end]
    previous = ''.join(lines).encode()
    require(len(previous) == 43749 and sha(previous) == CURRENT,
            'Molecular target whole-source restoration differs')
    ast.parse(previous); ast.parse(current)
    return previous, {'path': TARGET_WITNESS, 'sha256': TARGET_PIN, 'correspondence': witness}


def restore(current):
    previous, target_update = restore_targets(current)
    original, proof = restore_attempt(previous)
    return original, {**proof, 'target_update': target_update}
