"""Exact additive synthetic-select CLI route chained to the original CLI witness."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = "src/biocompiler/cli.py"
WITNESS = ROOT / "tests/conformance/synthetic-selection-cli-routing-source-lineage-v1.json"
WITNESS_SHA256 = "ffbbc7daae44136c2fbe483f69b7409ce090ee267781a072fdb65bc23d4eaa6b"
PARENT_REVISION = "a7db48b10b1005e9a6c7cf8cca975ddc1bc82fde"
HISTORICAL_SHA256 = "3920bd2b19a93482133c787da5924f1bfbfebcf1885663c2eceee4d023c34774"
HELPER = '''def _synthetic_producer_core_arguments(command):
    command.add_argument("--core-executable", type=Path, help=argparse.SUPPRESS)
    command.add_argument("--core-sha256", help=argparse.SUPPRESS)
    command.add_argument("--core-timeout", type=float, help=argparse.SUPPRESS)
'''
BRANCH = '''if any(getattr(args, name, None) is not None for name in ("core_executable", "core_sha256", "core_timeout")):
    from biocompiler.synthetic_producer_cli import selection_command
    return selection_command(args, bounded_text=_bounded_text, publish_report=_publish_report)
'''
REGISTRATION = '_synthetic_producer_core_arguments(selection)'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def tree(raw):
    return ast.parse(raw, type_comments=True)


def shape(node):
    return ast.dump(node, include_attributes=False)


def function(module, name):
    matches = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(matches) == 1, "Selection CLI route function census differs: " + name)
    return matches[0]


def load_witness():
    raw = WITNESS.read_bytes()
    require(sha(raw) == WITNESS_SHA256, "Selection CLI route witness bytes differ")
    value = json.loads(raw)
    require(set(value) == {"schema_version", "parent_revision", "entry"} and
            value['schema_version'] == 'biocompiler.synthetic_selection_cli_routing_source_lineage.v1' and
            value['parent_revision'] == PARENT_REVISION, "Selection CLI route witness shape differs")
    return value['entry']


def verify_extension(entry, current, historical_sha256):
    require(type(entry) is dict and set(entry) == {"path", "historical_sha256", "historical_source", "routed_sha256", "routed_source"}
            and entry['path'] == CLI and historical_sha256 == HISTORICAL_SHA256,
            "Unreviewed historical selection CLI source")
    historical, routed = entry['historical_source'].encode(), entry['routed_source'].encode()
    require(sha(historical) == historical_sha256 == entry['historical_sha256'], "Historical selection CLI bytes differ")
    require(current == routed and sha(current) == entry['routed_sha256'], "Current selection CLI route bytes differ")
    old, new = tree(historical), tree(current)
    helper = function(new, '_synthetic_producer_core_arguments')
    require(shape(helper) == shape(tree(HELPER).body[0]), "Selection CLI exact hidden options differ")
    position = new.body.index(helper)
    require(position > 0 and position + 1 < len(new.body) and
            getattr(new.body[position-1], 'name', None) == '_workflow_core_arguments' and
            getattr(new.body[position+1], 'name', None) == 'main', "Selection CLI helper placement differs")
    new.body.remove(helper)
    command = function(new, '_selection_command')
    require(shape(command.body[0]) == shape(tree(BRANCH).body[0]), "Selection CLI exact early branch differs")
    command.body.pop(0)
    main = function(new, 'main')
    matches = [node for node in main.body if shape(node) == shape(tree(REGISTRATION).body[0])]
    require(len(matches) == 1, "Selection CLI option registration census differs")
    position = main.body.index(matches[0])
    require(position > 0 and shape(main.body[position-1]) == shape(tree(
        'selection.add_argument("--output", type=Path, help="Atomic selection report destination")').body[0]), "Selection CLI option registration placement differs")
    main.body.remove(matches[0])
    require(shape(old) == shape(new), "Historical selection CLI default implementation AST differs")
    return {"path": CLI, "historical_sha256": historical_sha256, "current_sha256": sha(current),
            "kind": "reviewed_public_synthetic_selection_cli_route", "witness_sha256": WITNESS_SHA256}


def verify_source(root, historical_sha256):
    path = Path(root) / CLI
    require(path.is_file() and not path.is_symlink(), "Missing or linked selection CLI source")
    current = path.read_bytes()
    if sha(current) == historical_sha256:
        return {"path": CLI, "historical_sha256": historical_sha256, "current_sha256": historical_sha256,
                "kind": "identical_bytes"}
    entry = load_witness()
    latest = verify_extension(entry, current, HISTORICAL_SHA256)
    if historical_sha256 == HISTORICAL_SHA256:
        return latest
    from tools import workflow_source_lineage as earlier
    previous = earlier.verify_extension(earlier.load_witness()[CLI], entry['historical_source'].encode(), historical_sha256)
    require(previous['current_sha256'] == latest['historical_sha256'], "Selection CLI source chain is discontinuous")
    return {"path": CLI, "historical_sha256": historical_sha256, "current_sha256": latest['current_sha256'],
            "kind": "reviewed_public_synthetic_selection_cli_route_chain", "witness_sha256": WITNESS_SHA256,
            "lineage": [previous, latest]}
