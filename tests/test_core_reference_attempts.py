"""Pure Python draft controls; fixture orchestration is not native acceptance."""
from pathlib import Path
import sys
from types import SimpleNamespace, MappingProxyType
import unittest
from unittest.mock import patch

from biocompiler import core_pipeline_manager as base
from biocompiler.core_client import CoreClient, CoreProtocolError
from biocompiler.core_reference_host import ReferenceHost
from biocompiler.core_reference_views import ReferenceViews
from biocompiler.core_pipeline_manager import _ordered
from biocompiler.compiler.pipeline import PipelineError
from biocompiler.compiler import molecular
from examples.reference_construct import reference_request
from biocompiler.compiler.construct import run_construct_pipeline
from tests.test_core_reference_manager import ReferenceSession

from biocompiler import core_reference_manager as mod

class Session(ReferenceSession):
 def _invalidate(self): self.invalidated=True;self.closed=True

class Attempts(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.request,manifest,cls.registry=reference_request('RNA')
  cls.manifests={manifest.reference_set_id:manifest}
  # Actual original authoring result supplies structural input to callback controls.
  # It is never an accepted expected response for a native execution.
  cls.original=run_construct_pipeline(cls.request,cls.registry,cls.manifests)
 def manager(self):
  manager=object.__new__(mod.ReferenceCorePassManager)
  host=ReferenceHost.for_molecular(self.request,self.registry,self.manifests)
  with patch.object(base,'CorePipelineCallbackSession',Session):
   manager._reference_prepare(CoreClient(Path('/fixture/core')),host=host)
  return manager
 def attempt(self,manager,number,host=None):
  return manager._remember_molecular_attempt({'preparation_id':f'reference-preparation/{number}',
    'dependencies':[[f'dep{i}',str(i)] for i in range(6)]}, host or manager._reference_host)
 def primitive_runtime(self,manager):
  events=[]
  manager.set_dependency=lambda *v:events.append(('dependency',*v))
  manager.reference_molecular_profile=lambda p:events.append(('profile-prepare',p.identity)) or object()
  manager.register_completion_profile=lambda p:events.append(('profile-register',))
  manager.reference_molecular_registration=lambda p:events.append(('registration-prepare',p.identity)) or SimpleNamespace(contract=SimpleNamespace(id='construct_to_molecular'),producer=object(),validators={})
  manager.register=lambda *v:events.append(('register',))
  record,result,built=object(),object(),object()
  manager.run=lambda *v:events.append(('run',)) or record
  manager.result=lambda *a,**k:events.append(('result',)) or result
  manager.finish_reference_molecular=lambda p,r,s,**k:events.append(('finish',p.identity)) or built
  def unit(operation,args):
   events.append((operation,args['preparation_id']))
  manager._unit=unit
  return events,built
 def test_six_writes_before_duplicate_and_old_roots_stay_owned(self):
  manager=self.manager();first=self.attempt(manager,1);events,built=self.primitive_runtime(manager)
  self.assertIs(manager._continue_molecular(first,object()),built)
  first_state=manager._reference_attempts[first.identity]
  self.assertFalse(first_state.entered)
  marker=PipelineError("Completion profile 'exact_cds' is already registered.")
  second=self.attempt(manager,2,ReferenceHost.for_molecular(self.request,self.registry,dict(self.manifests)))
  events.clear()
  def fail(profile):events.append(('profile-register',));raise marker
  manager.register_completion_profile=fail
  with self.assertRaises(PipelineError) as caught: manager._continue_molecular(second,object())
  self.assertIs(caught.exception,marker)
  self.assertEqual([x[0] for x in events],['dependency']*6+['profile-prepare','profile-register','leave-reference-molecular-attempt'])
  self.assertIs(manager._reference_attempts[first.identity],first_state)
  self.assertIs(first_state.host,manager._reference_host)
  self.assertIsNot(manager._reference_attempts[second.identity].host.molecular_manifests,first_state.host.molecular_manifests)
  self.assertEqual(manager._reference_scopes,[])
 def test_failure_cleanup_never_replaces_original_object(self):
  for closed,cleanup_failure in [(True,False),(False,True),(False,False)]:
   with self.subTest(closed=closed,cleanup_failure=cleanup_failure):
    manager=self.manager();attempt=self.attempt(manager,1);events,_=self.primitive_runtime(manager)
    marker=RuntimeError('actual callback marker')
    def fail(*args):
     manager.session.closed=closed
     raise marker
    manager.run=fail
    def leave(*args):
     events.append(('cleanup',))
     if cleanup_failure:raise ValueError('secondary cleanup')
    manager._unit=leave
    with self.assertRaises(RuntimeError) as caught:manager._continue_molecular(attempt,object())
    self.assertIs(caught.exception,marker)
    self.assertEqual(sum(x[0]=='cleanup' for x in events),int(not closed))
    self.assertEqual(manager.session.invalidated,cleanup_failure)
 def test_cleanup_disposal_error_does_not_replace_active_exception(self):
  manager=self.manager();attempt=self.attempt(manager,1);self.primitive_runtime(manager)
  original=RuntimeError('original callback')
  def failure(*args,**kw):raise original
  manager.run=failure
  def cleanup(*args):raise ValueError('cleanup failed')
  manager._unit=cleanup
  def dispose():
   manager.session.closed=manager.session.invalidated=True
   raise OSError('child disposal failed')
  manager.session._invalidate=dispose
  with self.assertRaises(RuntimeError) as caught:manager._continue_molecular(attempt,object())
  self.assertIs(caught.exception,original)
  self.assertTrue(manager.session.closed and manager.session.invalidated)
 def test_nested_failure_restores_outer_scope_and_finishes_actual_outer(self):
  manager=self.manager();outer=self.attempt(manager,1);events,built=self.primitive_runtime(manager)
  original=manager.register_completion_profile;first=True
  def reenter(profile):
   nonlocal first
   if first:
    first=False;inner=self.attempt(manager,2)
    marker=RuntimeError('inner profile callback')
    def fail(_):raise marker
    manager.register_completion_profile=fail
    try:
     with self.assertRaises(RuntimeError) as caught:manager._continue_molecular(inner,object())
     self.assertIs(caught.exception,marker)
    finally:manager.register_completion_profile=original
    self.assertIs(manager._reference_scopes[-1].preparation,outer)
   original(profile)
  manager.register_completion_profile=reenter
  self.assertIs(manager._continue_molecular(outer,object()),built)
  self.assertEqual(manager._reference_scopes,[])
  self.assertEqual([x for x in events if x[0]=='finish'],[('finish',outer.identity)])
 def test_capability_lifo_foreign_replayed_and_same_budget_cap(self):
  manager=self.manager();a=self.attempt(manager,1);b=self.attempt(manager,2)
  manager._unit=lambda *args:None
  with self.assertRaisesRegex(CoreProtocolError,'active continuation'):manager.leave_reference_molecular_attempt(a)
  manager.leave_reference_molecular_attempt(b);manager.leave_reference_molecular_attempt(a)
  with self.assertRaisesRegex(CoreProtocolError,'active continuation'):manager.leave_reference_molecular_attempt(a)
  with self.assertRaisesRegex(CoreProtocolError,'Unknown Molecular'):manager._molecular_attempt('reference-preparation/foreign')
  manager.session._limits['max_retained_bytes']=manager._reference_origin_bytes+1023
  with self.assertRaisesRegex(CoreProtocolError,'Invalid native reference Molecular attempt'):self.attempt(manager,3)
  self.assertNotIn('reference-preparation/3',manager._reference_attempts)
 def test_old_provider_callback_uses_old_snapshot_after_new_attempt(self):
  manager=self.manager();a=self.attempt(manager,1)
  manager._unit=lambda *args:None;manager.leave_reference_molecular_attempt(a)
  new_host=ReferenceHost.for_molecular(self.request,self.registry,dict(self.manifests))
  b=self.attempt(manager,2,new_host)
  manager.session._handlers=[SimpleNamespace(sequence=77)]
  def publish(token,preparation):
   completion=manager._invoke('reference-molecular-provider',{'preparation_id':preparation.identity,'provider_id':token,'role':'construct_to_molecular.producer'})
   return manager._objects.resolve(completion.value)
  old_provider=publish('provider/old',a);new_provider=publish('provider/new',b)
  self.assertIsNot(old_provider,new_provider)
  document=self.original.candidate.to_dict();observed=[];opaque=object()
  def replacement(request,construct,registry,manifests):
   observed.append((request,construct,registry,manifests));return opaque
  def invoke(preparation,token):
   return manager._invoke('reference-emit',{'preparation_id':preparation.identity,'provider_id':token,
    'input':document,'argument':document,'tree':_ordered(document)})
  with patch.object(molecular,'emit_reference_sequence',replacement):
   old=invoke(a,'provider/old');new=invoke(b,'provider/new')
  self.assertIs(observed[0][3],manager._reference_attempts[a.identity].host.molecular_manifests)
  self.assertIs(observed[1][3],new_host.molecular_manifests)
  self.assertIsNot(observed[0][3],observed[1][3])
  self.assertIsNot(observed[0][1],observed[1][1])
  proposal=manager._invoke('reference-molecular-proposal',{'preparation_id':a.identity,'output':old.value['output'],'source_links':[]})
  self.assertIs(manager._objects.resolve(proposal.value).output,opaque)
  with self.assertRaisesRegex(CoreProtocolError,'captured attempt'):
   manager._invoke('reference-molecular-proposal',{'preparation_id':b.identity,'output':old.value['output'],'source_links':[]})
  with self.assertRaisesRegex(CoreProtocolError,'provider attempt origin'):invoke(b,'provider/old')
  with self.assertRaisesRegex(CoreProtocolError,'rebound'):
   publish('provider/old',b)
  self.assertEqual(new.status,'ok')
 def test_native_default_is_marker_never_legacy_emitter(self):
  manager=self.manager();a=self.attempt(manager,1)
  manager.session._handlers=[SimpleNamespace(sequence=5)]
  manager._invoke('reference-molecular-provider',{'preparation_id':a.identity,'provider_id':'provider/1','role':'construct_to_molecular.producer'})
  document=self.original.candidate.to_dict();calls=[];previous=sys.getprofile()
  def watch(frame,event,arg):
   if event=='call' and frame.f_code is molecular.emit_reference_sequence.__code__:calls.append(frame)
  sys.setprofile(watch)
  try:
   result=manager._invoke('reference-emit',{'preparation_id':a.identity,'provider_id':'provider/1','input':document,'argument':document,'tree':_ordered(document)})
  finally:sys.setprofile(previous)
  self.assertEqual(result.value['kind'],'native');self.assertEqual(calls,[])

if __name__=='__main__':unittest.main()
