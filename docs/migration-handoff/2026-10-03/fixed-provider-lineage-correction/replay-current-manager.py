"""Read the actual current-source manager receipt; never execute a native binary."""
import hashlib,json,sys,time,zipfile
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
from tools import check_pipeline_manager_install as m
p=Path('generated/migration-next/pr85-current-fresh-failure');started=time.monotonic()
with zipfile.ZipFile(p/'macos314.zip') as archive:
 raw=archive.read('pipeline-manager.json');receipt=json.loads(raw)
 assert receipt['status']=='success' and receipt['source_revision']=='0dd0fe54f3d1f0e502b30188f096cb5387fbb9b2' and receipt['run_id']=='37121925726'
 class Artifacts:
  def __init__(self):
   self.declared=receipt['artifacts'];self.used=set()
   names=[n.removeprefix('pipeline-manager-artifacts/') for n in archive.namelist() if n.startswith('pipeline-manager-artifacts/')]
   assert len(names)==len(set(names)) and set(names)=={r['path'] for r in self.declared.values()}
   for identity,row in self.declared.items():
    assert set(row)=={'path','bytes','sha256'} and row['path']==identity+'.bin' and row['sha256']==identity
    value=archive.read('pipeline-manager-artifacts/'+row['path']);assert 0<len(value)==row['bytes']<=m.r.MAX_ARTIFACT_BYTES and hashlib.sha256(value).hexdigest()==identity
  def raw(self,ref,maximum=m.r.MAX_ARTIFACT_BYTES):
   row=self.declared[ref];value=archive.read('pipeline-manager-artifacts/'+row['path']);assert len(value)==row['bytes'] and len(value)<=maximum and hashlib.sha256(value).hexdigest()==row['sha256']==ref;self.used.add(ref);return value
  def json(self,ref,maximum=m.r.CONTROL_BYTES):
   value=self.raw(ref,maximum);document=m.r.decode(value);assert m.canonical(document)==value;return document
 artifacts=Artifacts();projected=m.validate_checks(receipt,m.Corpus(),artifacts)
 assert len(projected)==86 and artifacts.used==set(artifacts.declared)
 result={'scope':'Complete current-source offline validation of actual freshly installed native manager receipt; other16campaigns separate',
  'source_revision':receipt['source_revision'],'tested_revision':receipt['revision'],'run_id':receipt['run_id'],'native_platform':receipt['native_platform'],
  'hosted_python':receipt['python_version'],'replay_python':sys.version,'receipt_status':receipt['status'],'receipt_sha256':hashlib.sha256(raw).hexdigest(),
  'checker_sha256':hashlib.sha256((m.ROOT/'tools/check_pipeline_manager_install.py').read_bytes()).hexdigest(),
  'identity_cases':5,'comparison_cases':34,'deferred_cases':47,'deferred_processes':53,'case_count':len(projected),
  'artifact_count':len(artifacts.used),'all_artifacts_hash_verified_and_consumed':True,'historical_source_overlay':False,
  'local_native_execution':False,'status':'PASS','duration_seconds':time.monotonic()-started,'projected_sha256':hashlib.sha256(m.canonical(projected)).hexdigest()}
 (p/'current-manager-validation.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result,sort_keys=True,indent=2))
