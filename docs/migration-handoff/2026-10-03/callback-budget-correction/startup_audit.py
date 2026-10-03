"""Read complete startup fixtures only; reject subprocess/network execution."""
import gc
import hashlib
import importlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

def audit(event, args):
    if event.startswith(('subprocess.', 'os.exec', 'os.spawn', 'socket.')) or event in {'os.system', 'os.fork', 'os.posix_spawn'}:
        raise AssertionError('Startup audit may not execute processes or network: ' + event)
sys.addaudithook(audit)

names = (
    'check_native_workflow', 'check_native_workflow_presentation',
    'check_native_workflow_authority', 'check_native_workflow_public_sdk',
    'check_native_workflow_cli', 'check_native_synthetic_producer',
    'check_native_synthetic_public_sdk', 'check_native_synthetic_selection_cli',
    'check_native_synthetic_inspection',
)
rows = []
for name in names:
    started = time.monotonic()
    row = {'module': name}
    try:
        module = importlib.import_module('tools.' + name)
        row['source_sha256'] = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        if name == 'check_native_workflow_cli':
            document, blobs = module.baseline()
            counterpart = module.runtime.workflow()
            obj = module.Oracle()
            row['baseline_cases'] = len(document['cases'])
            row['case_count'] = len(obj.cases)
            del document, blobs, counterpart
        elif name == 'check_native_synthetic_selection_cli':
            document, blobs = module.baseline()
            counterpart = module.counterparts()
            obj = module.Oracle()
            row['baseline_cases'] = len(document['cases'])
            row['case_count'] = len(obj.cases)
            del document, blobs, counterpart
        else:
            obj = module.Corpus()
            cases = obj.cases() if callable(obj.cases) else obj.cases
            row['case_count'] = len(list(cases))
            if name == 'check_native_synthetic_inspection': module.declaration()
            del cases
        if hasattr(module, 'SOURCES'):
            row['campaign_sources'] = {
                path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                for path in module.SOURCES
            }
        row['status'] = 'passed'
        del obj
    except Exception as exc:
        row.update(status='failed', error=type(exc).__name__ + ': ' + str(exc))
    row['seconds'] = round(time.monotonic() - started, 3)
    rows.append(row)
    print(json.dumps({k:v for k,v in row.items() if k != 'campaign_sources'}), flush=True)
    gc.collect()
result = {'python_version': platform.python_version(), 'scope': 'complete startup corpus/declaration/source-file reads only; subprocess and network audited forbidden', 'rows': rows}
path = Path(__file__).resolve().parent / ('startup-audit-' + platform.python_version() + '.json')
path.write_text(json.dumps(result, indent=2) + '\n')
raise SystemExit(any(row['status'] != 'passed' for row in rows))
