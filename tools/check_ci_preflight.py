"""Read every installed campaign's frozen inputs before expensive hosted work.

This is an early failure detector, never a substitute for native execution.
Child processes and network operations are prohibited during corpus loading.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import importlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prebuilt_release_pipeline import CAMPAIGNS, campaign_names
from tools.ci_native_bundle import test_plan


def audit(event, args):
    if event.startswith(('subprocess.', 'os.exec', 'os.spawn', 'socket.')) or event in {
        'os.system', 'os.fork', 'os.posix_spawn'}:
        raise AssertionError('Preflight prohibits processes and network: '+event)


def check(name):
    module = importlib.import_module('tools.'+name)
    if name in ('check_native_workflow_cli', 'check_native_synthetic_selection_cli'):
        document, blobs = module.baseline()
        counterpart = module.runtime.workflow() if name == 'check_native_workflow_cli' else module.counterparts()
        corpus = module.Oracle()
    else:
        corpus = module.Corpus()
    current = {}
    if name == 'check_pipeline_reference_install':
        module.load_bodies(corpus, installed=False)
        module.ContextSelection(corpus, None)
        runtime = importlib.import_module('tools.pipeline_reference_runtime')
        current = {**runtime.product_sources(corpus), **runtime.campaign_sources()}
    elif name == 'check_pipeline_fixed_registration_install':
        runtime = importlib.import_module('tools.pipeline_fixed_registration_runtime')
        current = {**runtime.product_sources(corpus), **runtime.campaign_sources()}
    elif name in ('check_native_workflow_cli', 'check_native_synthetic_selection_cli'):
        current = module.product_sources()
    elif hasattr(module, 'product_sources'):
        current = module.product_sources(corpus)
    elif hasattr(module, 'python_sources'):
        current = module.python_sources()
    if name == 'check_native_synthetic_inspection':
        module.declaration()
    for path in getattr(module, 'SOURCES', ()):
        current.setdefault(path, hashlib.sha256((ROOT/path).read_bytes()).hexdigest())
    for path, pin in current.items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest() != pin:
            raise AssertionError('Preflight source pin differs: '+path)
    return {'source_sha256':hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(), 'source_count':len(current)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    campaign_names()  # Exact group partition is mandatory even before loading.
    native = test_plan((ROOT/'core/test/dune').read_text())
    sys.addaudithook(audit)
    rows = []
    for name, campaign in CAMPAIGNS:
        started = time.monotonic()
        row = {'name':campaign, 'module':name}
        try:
            row.update(check(name), status='pass')
        except Exception as error:
            row.update(status='fail', error=type(error).__name__+': '+str(error))
        row['duration_seconds'] = round(time.monotonic()-started, 6)
        rows.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
        gc.collect()
    document = {'status':'pass' if all(row['status']=='pass' for row in rows) else 'fail',
                'python_version':platform.python_version(), 'native_suites':len(native), 'campaigns':rows,
                'scope':'source preflight only; native execution and final artifact acceptance remain required'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2)+'\n')
    return int(document['status'] != 'pass')


if __name__ == '__main__':
    raise SystemExit(main())
