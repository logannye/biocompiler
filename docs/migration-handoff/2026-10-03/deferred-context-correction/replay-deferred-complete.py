"""Historical817 receipt replay; no executable native or source authority changes.

Only trace.ROOT is temporarily directed to exact retained source bytes. The
current corrected comparator remains active. Whole restoration proves that the
historical campaign's runtime wrappers are unchanged by the additive proof.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import zipfile

sys.path.insert(0,str(Path.cwd()))
from tools import check_pipeline_manager_install as m

root=Path('generated/migration-next/pr85-sdk-wheel-failure')
receipt=json.loads((root/'fresh-macos-311-pipeline-manager.json').read_bytes())
source_revision='817a8ed1154975befd293327dfabdf7798ed2b4c'
campaign='tools/check_pipeline_manager_install.py'
assert receipt['source_revision']==source_revision
old=subprocess.run(['git','show',source_revision+':'+campaign],check=True,capture_output=True).stdout
assert hashlib.sha256(old).hexdigest()==receipt['campaign_sources'][campaign]
current=(m.ROOT/campaign).read_bytes();lines=current.decode().splitlines(keepends=True)
node=[n for n in ast.parse(current).body if isinstance(n,ast.FunctionDef) and n.name=='deferred_context_document']
assert len(node)==1
n=node[0]
# The complete new function and exactly its two following blank lines are the
# only addition. Every original function, source callpoint and wrapper survives.
assert lines[n.end_lineno:n.end_lineno+2]==['\n','\n']
restored=''.join(lines[:n.lineno-1]+lines[n.end_lineno+2:])
new_call='equal(deferred_context_document(contexts[-1], native), values["context"],\n                '
old_call='equal(contexts[-1]["arguments"]["document"], values["context"], '
assert restored.count(new_call)==1
restored=restored.replace(new_call,old_call)
assert restored.encode()==old
(root/'historical-manager-checker-817.py').write_bytes(old)
started=time.monotonic()
with zipfile.ZipFile(root/'fresh-macos-311.zip') as archive:
 class Artifacts:
  def __init__(self):
   self.declared=receipt['artifacts'];self.used=set()
   names=[n.removeprefix('pipeline-manager-artifacts/') for n in archive.namelist() if n.startswith('pipeline-manager-artifacts/')]
   assert len(names)==len(set(names)) and set(names)=={r['path'] for r in self.declared.values()}
   for identity,row in self.declared.items():
    assert set(row)=={'path','bytes','sha256'} and row['path']==identity+'.bin' and row['sha256']==identity
    raw=archive.read('pipeline-manager-artifacts/'+row['path']);assert 0<len(raw)==row['bytes']<=m.r.MAX_ARTIFACT_BYTES and hashlib.sha256(raw).hexdigest()==identity
  def raw(self,ref,maximum=m.r.MAX_ARTIFACT_BYTES):
   row=self.declared[ref];raw=archive.read('pipeline-manager-artifacts/'+row['path']);assert len(raw)==row['bytes'] and len(raw)<=maximum and hashlib.sha256(raw).hexdigest()==row['sha256']==ref;self.used.add(ref);return raw
  def json(self,ref,maximum=m.r.CONTROL_BYTES):
   raw=self.raw(ref,maximum);value=m.r.decode(raw);assert m.canonical(value)==raw;return value
 artifacts=Artifacts()
 trace_sources={}
 def collect(value):
  if type(value) is dict:
   if set(value)=={'node','source','function','qualname','line','source_sha256','binding'} and value['source'].startswith(('src/','tools/')):
    path=value['source'];pin=value['source_sha256'];assert path not in trace_sources or trace_sources[path]==pin
    trace_sources[path]=pin
   for child in value.values():collect(child)
  elif type(value) is list:
   for child in value:collect(child)
 for row in receipt['deferred_checks']:collect(artifacts.json(row['evidence'],m.r.MAX_ARTIFACT_BYTES))
 assert trace_sources[campaign]==hashlib.sha256(old).hexdigest()
 with tempfile.TemporaryDirectory(prefix='manager-historical-trace-') as directory:
  historical_root=Path(directory)
  for path,pin in trace_sources.items():
   assert not Path(path).is_absolute() and '..' not in Path(path).parts
   raw=old if path==campaign else (m.ROOT/path).read_bytes()
   assert hashlib.sha256(raw).hexdigest()==pin
   target=historical_root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
  original=m.trace.ORIGINAL
  if original not in trace_sources:
   target=historical_root/original;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((m.ROOT/original).read_bytes())
  previous=m.trace.ROOT
  try:
   m.trace.ROOT=historical_root
   projected=m.validate_checks(receipt,m.Corpus(),artifacts)
  finally:m.trace.ROOT=previous
 assert len(projected)==86 and artifacts.used==set(artifacts.declared)
 evidence={'kind':'historical-source-offline-replay-not-fresh-current-source-acceptance','source_revision':source_revision,
  'receipt_status_unchanged':receipt['status'],'hosted_python':receipt['python_version'],'replay_python':sys.version,
  'historical_campaign_sha256':hashlib.sha256(old).hexdigest(),'corrected_campaign_sha256':hashlib.sha256(current).hexdigest(),
  'finite_delta':'one complete deferred_context_document function plus one exact document comparison call substitution; entire original restored byte-for-byte',
  'historical_trace_source_pins':trace_sources,'case_count':len(projected),'identity_cases':5,'comparison_cases':34,
  'deferred_cases':47,'deferred_processes':53,'artifact_count':len(artifacts.used),'duration_seconds':time.monotonic()-started,
  'projected_sha256':hashlib.sha256(m.canonical(projected)).hexdigest(),'native_execution':False,'result':'PASS'}
 out=root/('replay-complete-'+str(sys.version_info.major)+str(sys.version_info.minor)+'.json')
 out.write_text(json.dumps(evidence,sort_keys=True,indent=2)+'\n')
 print(json.dumps(evidence,sort_keys=True,indent=2),flush=True)
