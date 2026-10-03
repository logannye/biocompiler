"""Pure startup reads for eight final campaigns; no child/native/network use."""
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
OUTPUT = Path(__file__).resolve().parent
NAMES = (
    'check_realization_protocol', 'check_realization_routing',
    'check_pipeline_session_install', 'check_pipeline_manager_install',
    'check_pipeline_fixed_provider_install', 'check_pipeline_fixed_continuation_install',
    'check_pipeline_fixed_registration_install', 'check_pipeline_reference_install',
)

def audit(event, args):
    if event.startswith(('subprocess.', 'os.exec', 'os.spawn', 'socket.')) or event in {'os.system', 'os.fork', 'os.posix_spawn'}:
        raise AssertionError('Startup audit prohibits child processes and network: ' + event)

sys.addaudithook(audit)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

rows, retained_sources = [], {}
for name in NAMES:
    started = time.monotonic()
    row = {'module': name}
    try:
        module = importlib.import_module('tools.' + name)
        source = Path(module.__file__)
        row['source_sha256'] = sha(source.read_bytes())
        retained_sources[source] = row['source_sha256']
        corpus = module.Corpus()
        row['corpus_class'] = type(corpus).__module__ + '.' + type(corpus).__qualname__
        if name == 'check_pipeline_reference_install':
            bodies = module.load_bodies(corpus, installed=False)
            selection = module.ContextSelection(corpus, None)
            row['unchanged_test_cases'] = len(bodies[1])
            row['exact_public_prefixes'] = len(selection.sources)
            runtime = importlib.import_module('tools.pipeline_reference_runtime')
            current = runtime.product_sources(corpus)
            declared = runtime.campaign_sources()
            del bodies, selection
        elif name == 'check_pipeline_fixed_registration_install':
            runtime = importlib.import_module('tools.pipeline_fixed_registration_runtime')
            current = runtime.product_sources(corpus)
            declared = runtime.campaign_sources()
        else:
            current = (module.product_sources(corpus) if hasattr(module, 'product_sources') else
                module.python_sources() if hasattr(module, 'python_sources') else {})
            declared = {path: sha((ROOT / path).read_bytes()) for path in getattr(module, 'SOURCES', ())}
        for path, pin in {**current, **declared}.items():
            actual = ROOT / path
            assert sha(actual.read_bytes()) == pin, 'Source census pin differs: ' + path
            if actual in retained_sources:
                assert retained_sources[actual] == pin, 'Source changed during startup audit: ' + path
            retained_sources[actual] = pin
        row['current_product_sources'] = {'count': len(current), 'sha256': sha(canonical(current))}
        row['declared_campaign_sources'] = {'count': len(declared), 'sha256': sha(canonical(declared))}
        row['status'] = 'passed'
        del corpus
    except Exception as error:
        row.update(status='failed', error=type(error).__name__ + ': ' + str(error))
    row['seconds'] = round(time.monotonic() - started, 3)
    rows.append(row)
    print(json.dumps(row), flush=True)
    gc.collect()
for path, pin in retained_sources.items():
    assert sha(path.read_bytes()) == pin, 'Source changed before audit completion: ' + str(path)
result = {
    'python_version': platform.python_version(),
    'scope': 'Final complete startup Corpus reads and applicable current source declarations; source-tree pure audit, not installed/native execution or acceptance',
    'prohibited': 'Subprocess, process creation/replacement and socket audit events',
    'script_sha256': sha(Path(__file__).read_bytes()),
    'source_count': len(retained_sources),
    'source_inventory_sha256': sha(canonical({str(path.relative_to(ROOT)): pin for path, pin in retained_sources.items()})),
    'rows': rows,
}
path = OUTPUT / ('startup-eight-' + platform.python_version() + '.json')
path.write_text(json.dumps(result, indent=2) + '\n')
raise SystemExit(any(row['status'] != 'passed' for row in rows))
