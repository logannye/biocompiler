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

def require(value, message):
    if not value: raise AssertionError(message)

def sha(value): return hashlib.sha256(value).hexdigest()

def restore(current):
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
