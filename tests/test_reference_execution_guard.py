"""Source/branch guard controls using an actual bounded Python protocol peer."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import FunctionType
import unittest
from unittest.mock import patch, Mock

from biocompiler.core_client import CoreClient
from biocompiler.core_pipeline_callback_session import capability_profile as channel_profile
from biocompiler.core_pipeline_manager import capability_profile
from biocompiler.core_reference_manager import ReferenceCorePassManager
from biocompiler.reference_backend import reference_core, ReferenceRoute
from biocompiler.compiler.construct import run_construct_pipeline
from examples.reference_construct import reference_request
from tests.test_core_pipeline_callback_session import PEER

from tools import reference_execution_guard as guard


class Artifacts:
    def __init__(self): self.values = {}
    def raw(self, key): return self.values[key]
    def frames(self, session):
        rows = []
        for item in session.traffic:
            key = guard.sha(item.frame)
            self.values[key] = item.frame
            rows.append({'direction':item.direction, 'frame':key})
        return rows


class ReferenceExecutionGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request, manifest, cls.registry = reference_request('RNA')
        cls.manifests = {manifest.reference_set_id:manifest}

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='reference-guard-')
        self.addCleanup(self.directory.cleanup)
        script = PEER.replace('def invoke(command, raw):', 'def invoke(command, raw, action, arguments):')
        script = script.replace("'action': command['arguments']['action'], 'arguments': command['arguments']['arguments']",
            "'action': action, 'arguments': arguments")
        start = script.index("    if operation == 'call-host':")
        end = script.index('    # BEFORE_REPLY', start)
        script = script[:start] + '''    if operation == 'initialize-reference':
        target={'value':value['arguments']['request']['target'],
            'binding':{'kind':'host','object':value['arguments']['target_object']}}
        state[:]=[target]
        answer=invoke(value,raw,'manager-created',{'target':target})
        if CALLBACK:
            document=value['arguments']['request']
            invoke(value,raw,'reference-generate',{'input':document,'argument':document,'tree':ordered(document)})
        assert answer == {'status':'ok','value':None}
        outcome={'status':'ok','value':{'kind':'reference','manager':True,'artifacts':[],'target':target}}
    elif operation=='inspect-ordered-references':
        maps=('dependencies','passes','component_inputs','provider_history','component_input_history','records','profiles')
        snapshot={'target':state[0]['value'],**{key:{} for key in maps}}
        order={key:[] for key in maps}
        order.update(validators={key:{} for key in ('passes','component_inputs','provider_history','component_input_history')},combined_provider_history=[])
        outcome={'status':'ok','value':{'snapshot':snapshot,'order':order,'providers':[],'record_definitions':[]}}
    elif operation in ('register','set-dependency'):
        outcome={'status':'ok','value':None}
    else:
        outcome={'status':'ok','value':value['arguments']}
''' + script[end:]
        path = Path(self.directory.name) / 'python-peer'
        self.path=path
        script = '''CALLBACK=False
def ordered(value):
    if isinstance(value,dict): return ['object',[[key,ordered(item)] for key,item in value.items()]]
    if isinstance(value,list): return ['array',[ordered(item) for item in value]]
    return ['scalar',value]
''' + script
        path.write_text(f'#!{sys.executable}\nDECLARATION={channel_profile()!r}\nAPPLICATION={capability_profile()!r}\n' + script)
        path.chmod(0o700)
        self.core = CoreClient(path, timeout_seconds=3)

    def initialize(self):
        manager = ReferenceCorePassManager._initialize(self.core, self.request, self.registry, self.manifests,
            molecular=False, limits=None, manager_limits=None)
        self.addCleanup(manager.close)
        return manager

    def test_actual_facade_source_serialization_and_complete_command_receipt(self):
        with guard.execution() as proof:
            owner = self.initialize()
            owner.set_dependency('test', 'a'*64)
        artifacts = Artifacts(); frames = [artifacts.frames(owner.session)]
        evidence = proof.evidence()
        self.assertEqual([item['operation'] for item in evidence['commands']], ['initialize-reference','set-dependency'])
        self.assertIs(guard.validate(evidence,frames,artifacts),evidence)
        for mutate in (lambda x:x['commands'].pop(), lambda x:x['commands'].append(x['commands'][0]),
                       lambda x:x['commands'][0].update(operation='run'),
                       lambda x:x['calls'][0]['frame'].update(code_sha256='0'*64),
                       lambda x:x.update(runtime=[3,11] if sys.version_info[:2]==(3,14) else [3,14])):
            altered=deepcopy(evidence); mutate(altered)
            with self.assertRaises(AssertionError): guard.validate(altered,frames,artifacts)

    def test_five_line_public_prefix_and_chained_trace(self):
        observed=[]
        oldtrace=sys.gettrace()
        def trace(frame,event,arg):
            if frame.f_code is run_construct_pipeline.__code__: observed.append(event)
            return trace
        # This fixture returns the initialized manager before any Build phase.
        # The substituted route is test code, not a product permission entry.
        def route(self,request,registry,manifests): return self_test.initialize()
        self_test=self
        with guard.execution() as proof, reference_core(self.core):
            sys.settrace(trace)
            try:
                with patch.object(ReferenceRoute,'construct',route): owner=run_construct_pipeline(self.request,self.registry,self.manifests)
            finally: sys.settrace(oldtrace)
        evidence=proof.evidence()
        self.assertEqual(len(evidence['routes']),1)
        self.assertIn('return',observed)
        self.assertEqual(len(evidence['routes'][0]['lines']),5)
        artifacts=Artifacts(); guard.validate(evidence,[artifacts.frames(owner.session)],artifacts)

    def test_no_selected_context_cannot_enter_old_public_body(self):
        with self.assertRaisesRegex(AssertionError,'original Python body'):
            with guard.execution(): run_construct_pipeline(self.request,self.registry,self.manifests)

    def test_legacy_parser_checker_producer_are_forbidden_inside_actual_operation(self):
        from biocompiler.ir.construct import ConstructRequest
        from biocompiler.synthesis.construct import generate_construct
        from biocompiler.verification.construct import check_construct_request
        from biocompiler.core_reference_host import ReferenceHost
        original=ReferenceHost.origin
        for callback in (lambda:ConstructRequest.from_dict(self.request.to_dict()),
                         lambda:generate_construct(self.request),
                         lambda:check_construct_request(self.request,self.registry,self.manifests)):
            def origin(host,name):
                callback()
                return original(host,name)
            with self.subTest(callback=callback), self.assertRaisesRegex(AssertionError,'Legacy Python reference authority'):
                with guard.execution(), patch.object(ReferenceHost,'origin',origin): self.initialize()

    def test_foreign_globals_and_replaced_module_cannot_use_transport_permission(self):
        from biocompiler import core_reference_host as host
        original=host.ReferenceHost.origin
        clone=FunctionType(original.__code__,dict(original.__globals__),original.__name__,original.__defaults__,original.__closure__)
        clone.__module__=original.__module__
        with self.assertRaisesRegex(AssertionError,'source or globals'):
            with patch.object(host.ReferenceHost,'origin',clone): guard.Policy()
        # Replacement after policy construction must be caught on live entry.
        from types import ModuleType
        fake=ModuleType(host.__name__); fake.__dict__.update(vars(host))
        with self.assertRaisesRegex(AssertionError,'replaced module'):
            with guard.execution(), patch.dict(sys.modules,{host.__name__:fake}): self.initialize()

    def test_disable_or_swallow_guard_failure_cannot_yield_completed_proof(self):
        with self.assertRaisesRegex(AssertionError,'disabled'):
            with guard.execution(): sys.setprofile(None)
        from biocompiler.core_reference_host import ReferenceHost
        from biocompiler.synthesis.construct import generate_construct
        original=ReferenceHost.origin
        def origin(host,name):
            try: generate_construct(self.request)
            except AssertionError: pass
            return original(host,name)
        with self.assertRaisesRegex(AssertionError,'Legacy Python reference authority'):
            with guard.execution(),patch.object(ReferenceHost,'origin',origin): self.initialize()

    def test_explicit_host_replacement_is_proposal_only_including_copied_default(self):
        from biocompiler.synthesis.construct import generate_construct
        self.path.write_text(self.path.read_text().replace('CALLBACK=False','CALLBACK=True'))
        clone=FunctionType(generate_construct.__code__,generate_construct.__globals__,generate_construct.__name__)
        clone.__module__=generate_construct.__module__
        for replacement in (Mock(return_value=object()),clone):
            with self.subTest(replacement=type(replacement).__name__):
                with guard.execution() as proof, patch('biocompiler.compiler.construct.generate_construct',replacement):
                    owner=self.initialize()
                evidence=proof.evidence()
                self.assertEqual(len(evidence['host_overrides']),1)
                self.assertEqual(evidence['host_overrides'][0]['role'],'generate')
                artifacts=Artifacts(); frames=[artifacts.frames(owner.session)]
                guard.validate(evidence,frames,artifacts)
                bad=deepcopy(evidence); bad['host_overrides']=[]
                with self.assertRaisesRegex(AssertionError,'callback execution proof'): guard.validate(bad,frames,artifacts)
                bad=deepcopy(evidence); bad['host_overrides'][0]['command_sequence']+=1
                with self.assertRaisesRegex(AssertionError,'owning command'): guard.validate(bad,frames,artifacts)

    def test_actual_public_registration_delegation_is_not_a_base_frame_allowlist(self):
        from biocompiler.compiler.pipeline import PassManager
        from tests.test_pipeline import PipelineTests
        fixture=PipelineTests(); fixture.setUp()
        original=PassManager.register
        observed=[]
        def wrapped(owner,contract,producer,validators):
            observed.append((owner,contract,producer,validators))
            return original(owner,contract,producer,validators)
        with guard.execution() as proof,patch.object(PassManager,'register',wrapped):
            owner=self.initialize()
            owner.register(fixture.first,lambda context:None,{'behavior':lambda context:None})
        evidence=proof.evidence()
        self.assertEqual(len(observed),1)
        self.assertEqual(len(evidence['delegation']),2)
        artifacts=Artifacts(); frames=[artifacts.frames(owner.session)]
        guard.validate(evidence,frames,artifacts)
        altered=deepcopy(evidence); altered['delegation']=[list(guard.registration.BASE)]
        with self.assertRaisesRegex(AssertionError,'command census'): guard.validate(altered,frames,artifacts)
        # The same real original method on an ordinary manager is forbidden
        # once a selected operation is active; frame spelling confers nothing.
        from biocompiler.core_reference_host import ReferenceHost
        prior=ReferenceHost.origin
        def origin(host,name):
            original(fixture.manager,fixture.first,lambda context:None,{})
            return prior(host,name)
        with self.assertRaisesRegex(AssertionError,'semantic branch'):
            with guard.execution(),patch.object(ReferenceHost,'origin',origin): self.initialize()

    def test_previous_profiler_is_chained_and_restored_on_success_and_failure(self):
        previous=sys.getprofile(); events=[]
        def observer(frame,event,arg):
            if frame.f_code is ReferenceCorePassManager._initialize.__func__.__code__:
                events.append(event)
        sys.setprofile(observer)
        try:
            with guard.execution(): self.initialize()
            self.assertIs(sys.getprofile(),observer)
            self.assertEqual(events.count('call'),1)
            with self.assertRaisesRegex(AssertionError,'disabled'):
                with guard.execution(): sys.setprofile(None)
            self.assertIs(sys.getprofile(),observer)
        finally: sys.setprofile(previous)

    def test_trace_triggered_observation_is_profiled_and_preserves_register_owner(self):
        from biocompiler.core_pipeline_manager import CorePassManager
        from tests.test_pipeline import PipelineTests
        fixture=PipelineTests(); fixture.setUp()
        from tools.check_pipeline_reference_install import observed_inspection
        previous=sys.gettrace()
        seen=[]
        def trace(frame,event,arg):
            if frame.f_code is CorePassManager._native_register.__code__ and event=='return':
                owner=frame.f_locals['self']
                # A source-bound observational command after register replaces
                # last_response. call_tracing makes its real frames visible.
                proof.observation(observed_inspection,(owner,))
                seen.append(owner.session.last_response.operation)
            return trace
        with guard.execution() as proof:
            owner=self.initialize()
            sys.settrace(trace)
            try: owner.register(fixture.first,lambda context:None,{'behavior':lambda context:None})
            finally: sys.settrace(previous)
        self.assertEqual(seen,['inspect-ordered-references'])
        evidence=proof.evidence()
        self.assertEqual([row['operation'] for row in evidence['commands']],
            ['initialize-reference','register','inspect-ordered-references'])
        artifacts=Artifacts(); guard.validate(evidence,[artifacts.frames(owner.session)],artifacts)
        # Leaving the tracer-issued command unprofiled is rejected by the full
        # native census even though all raw frames themselves are valid.
        broken=deepcopy(evidence)
        broken['commands'].pop()
        broken['inspection']={'count':0,'source':None}
        for row in broken['calls']:
            if row['frame']['qualname']=='CorePassManager._call': row['count']-=1
        with self.assertRaisesRegex(AssertionError,'complete native traffic'):
            guard.validate(broken,[artifacts.frames(owner.session)],artifacts)

    def test_observation_helper_cannot_be_cloned_or_replaced_and_owner_slot_restores(self):
        from types import SimpleNamespace
        from tools.check_pipeline_reference_install import observed_inspection
        observer=SimpleNamespace(guarded_observation=None)
        clone=FunctionType(observed_inspection.__code__,dict(observed_inspection.__globals__),observed_inspection.__name__)
        clone.__module__=observed_inspection.__module__
        with guard.execution(observer) as proof:
            owner=self.initialize()
            with self.assertRaisesRegex(AssertionError,'source-bound inspection helper'):
                proof.observation(clone,(owner,))
            with self.assertRaisesRegex(AssertionError,'source-bound inspection helper'):
                proof.observation(lambda x:x,(owner,))
            state=observer.guarded_observation(observed_inspection,(owner,))
            self.assertIs(state['_target'],self.request.target)
        self.assertIsNone(observer.guarded_observation)
        artifacts=Artifacts(); evidence=proof.evidence(); frames=[artifacts.frames(owner.session)]
        guard.validate(evidence,frames,artifacts)
        altered=deepcopy(evidence); altered['inspection']['source']['code_sha256']='0'*64
        with self.assertRaisesRegex(AssertionError,'inspection helper source'):
            guard.validate(altered,frames,artifacts)

    def test_original_authoring_outside_selected_operation_is_available(self):
        from biocompiler.ir.construct import ConstructRequest
        with guard.execution() as proof:
            result=ConstructRequest.from_dict(self.request.to_dict())
        self.assertEqual(result.to_dict(),self.request.to_dict())
        self.assertEqual(proof.evidence()['commands'],[])


if __name__=='__main__': unittest.main()
