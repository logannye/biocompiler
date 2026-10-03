"""Original Python-only probe of retained Molecular output identity and closure roots."""
from pathlib import Path
import hashlib,json,sys
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
from biocompiler.compiler import molecular,pipeline
from biocompiler.ir.serialization import fingerprint
from tests.test_molecular_pipeline import MolecularPipelineTests
case=MolecularPipelineTests();case.setUp();build=case.build();manager=build.manager
record=manager.get('molecular');before=record.to_dict();producer=manager._passes['construct_to_molecular'][1]
closure=dict(zip(producer.__code__.co_freevars,(cell.cell_contents for cell in producer.__closure__)))
original_map=closure['references'];writes=[];actual_set=manager.set_dependency
manager.set_dependency('molecular_emitter',fingerprint('stale-before-reentry'))
def observed_set(key,value):
 writes.append([key,value]);return actual_set(key,value)
manager.set_dependency=observed_set
with patch.object(molecular,'run_construct_pipeline',return_value=SimpleNamespace(manager=manager)):
 try:molecular.run_molecular_pipeline(case.request,case.registry,{})
 except pipeline.PipelineError as error:duplicate_profile={'type':type(error).__name__,'message':str(error)}
 else:raise AssertionError('Original duplicate profile accepted')
assert duplicate_profile['message']=="Completion profile 'exact_cds' is already registered."
assert [row[0] for row in writes]==['human_admission_policy','molecular_emitter','molecular_checker','molecular_profile','encoding_policy','molecular_pipeline']
assert manager._passes['construct_to_molecular'][1] is producer
actual_emit=molecular.emit_reference_sequence;calls=[]
def emit(request,construct,registry,manifests):
 calls.append({'request_is_original':request is case.request,'registry_is_original':registry is case.registry,'manifest_map_is_original':manifests is original_map,'manifest_values_are_original':all(manifests[key] is value for key,value in case.manifests.items())})
 return actual_emit(request,construct,registry,manifests)
with patch.object(molecular,'emit_reference_sequence',side_effect=emit):
 try:manager.run('construct_to_molecular','construct','molecular')
 except pipeline.PipelineError as error:duplicate_output={'type':type(error).__name__,'message':str(error),'emitter_calls':len(calls)}
 else:raise AssertionError('Original duplicate artifact accepted')
 assert duplicate_output=={'type':'PipelineError','message':"Artifact 'molecular' already exists; use a new identity.",'emitter_calls':0}
 rerun=manager.run('construct_to_molecular','construct','molecular-rerun')
assert len(calls)==1 and all(calls[0].values())
assert manager.get('molecular') is record and build.result.artifact is record and rerun is not record
assert record.to_dict()==before and rerun.accepted
paths=['src/biocompiler/compiler/pipeline.py','src/biocompiler/compiler/molecular.py','tests/test_molecular_pipeline.py']
result={'schema':'source_original.molecular_duplicate_reuse.v1','python_version':sys.version.split()[0],'source_files':{path:hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths},'dependency_writes':writes,'duplicate_profile':duplicate_profile,'duplicate_output':duplicate_output,'producer_same':manager._passes['construct_to_molecular'][1] is producer,'actual_emitter_calls':calls,'original_stored_record_same':manager.get('molecular') is record,'historical_build_artifact_same':build.result.artifact is record,'original_record':before,'rerun_record':rerun.to_dict(),'native_execution':False}
print(json.dumps(result,sort_keys=True,separators=(',',':')))
