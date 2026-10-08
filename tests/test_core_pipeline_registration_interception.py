"""Real Python subprocess protocol controls; no native semantic acceptance."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import FunctionType
import unittest
from unittest.mock import patch

from biocompiler.compiler.pipeline import PassManager, PipelineError
from biocompiler.core_client import CoreClient, CoreProtocolError
from biocompiler.core_pipeline_callback_session import capability_profile as channel_profile
from biocompiler.core_pipeline_manager import CorePassManager, _ordered, capability_profile
from tests.test_core_pipeline_callback_session import PEER
from tests.test_core_pipeline_manager import FixtureSession
from tests import test_pipeline as authoring
from tools import check_pipeline_manager_install as campaign
from tools import manager_registration_source_lineage as lineage
from tools import pipeline_registration_guard as route


class RegistrationInterceptionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = authoring.PipelineTests()
        self.fixture.setUp()
        self.contract = replace(self.fixture.first, id='intent_to_behavior')
        self.temp = tempfile.TemporaryDirectory(prefix='registration-route-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.saved = []
        from tools.capture_pipeline_fixed_provider_semantics import authority
        self.authored = authority('static:requested')

    def peer(self, mode='ok'):
        script = PEER.replace('def invoke(command, raw):', 'def invoke(command, raw, action, arguments):')
        script = script.replace("'action': command['arguments']['action'], 'arguments': command['arguments']['arguments']",
            "'action': action, 'arguments': arguments")
        start = script.index('    if operation == \'call-host\':')
        end = script.index('    # BEFORE_REPLY', start)
        script = script[:start] + '''    if operation in ('initialize-synthetic','initialize-components'):
        target={'value':value['arguments']['request']['build_request']['target'],
            'binding':{'kind':'host','object':value['arguments']['target_object']}}
        initialization={'kind':operation.removeprefix('initialize-'),'manager':True,'artifacts':[],'target':target}
        if MODE != 'missing-publication':
            published=invoke(value,raw,'manager-created',{'target':target})
            assert published == {'status':'ok','value':None}
        if MODE == 'duplicate-publication':
            invoke(value,raw,'manager-created',{'target':target})
        if MODE == 'missing-publication':
            outcome={'status':'ok','value':initialization}
        else:
            producer=invoke(value,raw,'native-provider',{'provider_id':'provider/producer','role':'intent_to_behavior.producer'})['value']
            validator=invoke(value,raw,'native-provider',{'provider_id':'provider/validator','role':'intent_to_behavior.validator'})['value']
            registration={'contract':CONTRACT,'producer':producer,
                'validators':[[item['id'],validator] for item in CONTRACT['checks']],
                'obligation_objects':OBLIGATIONS}
            if MODE == 'wrong-role':
                registration['producer']=validator
            outcome=invoke(value,raw,'register-fixed',registration)
            if MODE == 'rejected' and outcome['status']=='ok':
                outcome={'status':'rejected','value':REJECTION}
            elif outcome['status']=='ok':
                if MODE == 'changed-target':
                    initialization['target']['value']={'schema_version':'changed'}
                outcome={'status':'ok','value':initialization}
    elif operation in ('register','set-dependency'):
        outcome={'status':'ok','value':None}
    elif operation == 'target':
        outcome={'status':'ok','value':target}
    else:
        outcome={'status':'ok','value':value['arguments']}
''' + script[end:]
        path = self.directory / ('peer-'+mode)
        rejection = {'module':'biocompiler.compiler.pipeline','type':'PipelineError',
            'message':'scripted logical initializer rejection','attributes':{},'attributes_tree':['object',[]]}
        obligations = [{'kind':'native','identity':'value/'+str(index),'tree':_ordered(item.to_dict())}
            for index,item in enumerate(self.contract.introduces)]
        path.write_text(f'#!{sys.executable}\nDECLARATION={channel_profile()!r}\nAPPLICATION={capability_profile()!r}\n'
            f'MODE={mode!r}\nCONTRACT={self.contract.to_dict()!r}\nOBLIGATIONS={obligations!r}\nREJECTION={rejection!r}\n'+script)
        path.chmod(0o700)
        return CoreClient(path, timeout_seconds=3)

    def initialize(self, core):
        request, history, until, config = self.authored
        return CorePassManager.from_synthetic(core, request, history, until=until, config=config)

    def test_public_wrapper_captured_original_and_nested_registration_route(self):
        captured = PassManager.register
        seen, observed = set(), []
        def wrapper(manager, contract, producer, validators):
            self.saved.append(manager)
            observed.append((manager, contract, producer, validators))
            captured(manager, contract, producer, validators)
            captured(manager, contract, producer, validators)
            manager.set_dependency('wrapper', 'a'*64)
        with patch.object(PassManager, 'register', wrapper):
            with campaign.guarded_execution(seen):
                manager = self.initialize(self.peer())
        self.addCleanup(manager.close)
        self.assertIs(manager, self.saved[0])
        self.assertEqual(len(observed), 1)
        commands = [item.value for item in manager.session.traffic if item.direction=='client' and item.value['kind']=='command']
        self.assertEqual([item['operation'] for item in commands], ['initialize-synthetic','register','register','set-dependency'])
        proofs = [json.loads(value) for module,value in seen if module==route.TAG]
        self.assertEqual(len(proofs),2)
        self.assertEqual({item['sequence'] for item in proofs}, {item['sequence'] for item in commands if item['operation']=='register'})
        self.assertFalse(campaign.permitted(*route.BASE))
        for command in commands:
            if command['operation']=='register':
                args=command['arguments']
                self.assertIs(manager._objects.resolve(args['producer']),observed[0][2])
                self.assertIs(manager._objects.resolve(args['validators']),observed[0][3])
                self.assertEqual(args['contract'],observed[0][1].to_dict())

    def test_actual_delegation_receipt_requires_complete_command_and_branch_bindings(self):
        seen=set()
        with campaign.guarded_execution(seen): manager=self.initialize(self.peer())
        manager.close()
        directory=self.directory/'receipts';directory.mkdir()
        receipt={'_artifact_directory':str(directory),'artifacts':{}}
        frames=[{'direction':item.direction,'index':item.index,
            'frame':campaign.artifact(receipt,item.frame)} for item in manager.session.traffic]
        artifacts=campaign.Artifacts(directory,receipt['artifacts'])
        campaign.validate_frames(frames,artifacts,*campaign.declarations(),
            initializer='initialize-synthetic',provider_calls=False)
        baseline=sorted(map(list,seen))
        route.validate(baseline,frames,artifacts)
        offset=next(index for index,item in enumerate(baseline) if item[0]==route.TAG)
        for kind in ('omitted','duplicate','source','receiver','count','request','reply','sequence','pre-command'):
            changed=deepcopy(baseline)
            value=json.loads(changed[offset][1])
            if kind=='omitted': changed.pop(offset)
            elif kind=='duplicate': changed.append(deepcopy(changed[offset]))
            else:
                if kind=='source': value['base_sha256']='0'*64
                if kind=='receiver': value['receiver']='copied.CorePassManager'
                if kind=='count': value['immediate_entry_count']=2
                if kind=='request': value['request_sha256']='0'*64
                if kind=='reply': value['reply_sha256']='0'*64
                if kind=='sequence': value['sequence']-=1
                if kind=='pre-command':
                    for key in ('sequence','request_sha256','reply_sha256'):value.pop(key)
                    runtime=route.runtime_authority(list(sys.version_info[:2]))
                    site=next(item for item in runtime['sites'] if item['opcode'].startswith('CALL'))
                    value.update(kind='pre-command-exception',frame_offset=2,frame_end=2,
                        site=site,runtime=list(sys.version_info[:2]))
                changed[offset][1]=route.canonical(value).decode()
            with self.subTest(kind=kind),self.assertRaisesRegex(AssertionError,'delegation|Delegation|Pre-command'):
                route.validate(changed,frames,artifacts)

    def test_opaque_initializer_errors_keep_same_published_manager_and_trace_tail(self):
        for error in (ValueError('callback'), KeyboardInterrupt('cancel from callback'), SystemExit('callback exit'),
                CoreProtocolError('user chosen protocol-looking error')):
            captured=PassManager.register
            cause=RuntimeError('cause'); error.__cause__=cause
            def wrapper(manager, contract, producer, validators):
                self.saved.append(manager)
                captured(manager,contract,producer,validators)
                manager.set_dependency('partial','b'*64)
                raise error
            with self.subTest(error=type(error).__name__), patch.object(PassManager,'register',wrapper):
                with self.assertRaises(type(error)) as raised:
                    self.initialize(self.peer())
            manager=self.saved[-1]; self.addCleanup(manager.close)
            self.assertIs(raised.exception,error); self.assertIs(error.__cause__,cause)
            self.assertFalse(manager.session.closed); self.assertFalse(manager.session.invalidated)
            self.assertEqual(manager.session.last_response.operation,'initialize-synthetic')
            self.assertEqual(manager.session.last_response.status,'raise')
            self.assertIsNone(manager._fixed_initialization)
            proxy=manager._native_providers['provider/producer']
            pid=manager.session.pid
            manager.set_dependency('after','c'*64)
            self.assertEqual(manager.session.pid,pid)
            self.assertIs(manager._native_providers['provider/producer'],proxy)
            self.assertEqual(manager._objects._exceptions, {})

    def test_return_is_ignored_and_logical_failure_retains_owner_without_fallback(self):
        class Hostile:
            def __repr__(self): raise AssertionError('repr called')
            def __bool__(self): raise AssertionError('truth called')
            def to_dict(self): raise AssertionError('conversion called')
        def wrapper(manager,*args):
            self.saved.append(manager)
            return Hostile()
        with patch.object(PassManager,'register',wrapper):
            with self.assertRaisesRegex(PipelineError,'scripted logical'):
                self.initialize(self.peer('rejected'))
        manager=self.saved[-1]; self.addCleanup(manager.close)
        self.assertFalse(manager.session.closed)
        self.assertEqual([item.value['operation'] for item in manager.session.traffic
            if item.direction=='client' and item.value['kind']=='command'],['initialize-synthetic'])
        manager.set_dependency('after','d'*64)

    def test_structural_and_uncertain_initializer_failures_close_published_manager(self):
        captured=PassManager.register
        for mode in ('wrong-role','changed-target','duplicate-publication','missing-publication'):
            local=[]
            original_prepare=CorePassManager._prepare
            def prepare(manager,*args,**kwargs):
                original_prepare(manager,*args,**kwargs);local.append(manager)
            def wrapper(manager,*args):
                return captured(manager,*args)
            with self.subTest(mode=mode), patch.object(CorePassManager,'_prepare',prepare), patch.object(PassManager,'register',wrapper):
                with self.assertRaises(CoreProtocolError): self.initialize(self.peer(mode))
            manager=local[0]
            self.assertTrue(manager.session.closed); self.assertTrue(manager.session.invalidated)
            self.assertIsNotNone(manager.session.returncode)
            before=len(manager.session.traffic)
            with self.assertRaisesRegex(CoreProtocolError,'cannot reconnect'): manager.set_dependency('after','e'*64)
            self.assertEqual(len(manager.session.traffic),before)

    def test_authoring_rejection_preserves_original_error_before_any_command(self):
        from biocompiler.compiler.pipeline import PassContract
        from biocompiler.errors import SerializationError
        manager=self.initialize(self.peer())
        self.addCleanup(manager.close)
        class ContractSubclass(PassContract): pass
        for invalid,exception in ((object(),SerializationError),(object.__new__(ContractSubclass),CoreProtocolError)):
            seen=set();before=len(manager.session.traffic); previous=manager.session.last_response
            with self.subTest(kind=type(invalid).__name__):
                with self.assertRaises(exception):
                    with campaign.guarded_execution(seen): manager.register(invalid,None,{})
                self.assertEqual(len(manager.session.traffic),before)
                self.assertIs(manager.session.last_response,previous)
                proofs=[json.loads(value) for module,value in seen if module==route.TAG]
                self.assertEqual(len(proofs),1)
                self.assertEqual(proofs[0]['kind'],'pre-command-exception')
                self.assertEqual(proofs[0]['frame_offset'],proofs[0]['frame_end'])
                self.assertNotIn('sequence',proofs[0])

    def test_ordinary_route_does_not_import_core_and_native_subclasses_fail_closed(self):
        script='''import sys
from test_pipeline import PipelineTests, accepted
fixture=PipelineTests();fixture.setUp()
assert 'biocompiler.core_pipeline_manager' not in sys.modules
before={key for key in sys.modules if key.startswith('biocompiler')}
fixture.manager.register(fixture.first,lambda context:None,{check.id:accepted for check in fixture.first.checks})
assert before=={key for key in sys.modules if key.startswith('biocompiler')}
assert 'biocompiler.core_pipeline_manager' not in sys.modules
'''
        result=subprocess.run([sys.executable,'-c',script],cwd=lineage.ROOT,env={**__import__('os').environ,
            'PYTHONPATH':str(lineage.ROOT/'src')+':'+str(lineage.ROOT/'tests')},capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        class Unsupported(CorePassManager): pass
        value=object.__new__(Unsupported)
        with self.assertRaisesRegex(CoreProtocolError,'subclasses'): value.register(self.contract,None,{})
        with self.assertRaisesRegex(CoreProtocolError,'subclasses'): PassManager.register(value,self.contract,None,{})

    def test_guard_rejects_ordinary_receiver_cloned_globals_and_private_bypass(self):
        from tools.check_pipeline_deferred_runtime import same_code
        with self.assertRaisesRegex(AssertionError,'semantic branch'):
            with campaign.guarded_execution(set()):
                PassManager.register(self.fixture.manager,self.contract,None,{})
        with patch('biocompiler.core_pipeline_manager.CorePipelineCallbackSession',FixtureSession):
            manager=CorePassManager(CoreClient(Path('/fixture/core')),target=self.fixture.target,dependencies={})
        self.addCleanup(manager.close)
        with self.assertRaisesRegex(AssertionError,'bypassed public'):
            with campaign.guarded_execution(set()): manager._native_register(self.contract,None,{})
        actual=PassManager.register
        copied=FunctionType(actual.__code__,dict(actual.__globals__))
        with self.assertRaisesRegex(AssertionError,'foreign source or globals'):
            with campaign.guarded_execution(set()): copied(manager,self.contract,None,{})
        altered=actual.__code__.replace(co_stacksize=actual.__code__.co_stacksize+1)
        forged=FunctionType(altered,actual.__globals__)
        with self.assertRaisesRegex(AssertionError,'foreign source or globals'):
            with campaign.guarded_execution(set()): forged(manager,self.contract,None,{})

    def test_guard_rejects_same_named_module_or_class_replacement(self):
        import types
        import biocompiler.core_pipeline_manager as core_module
        fake=types.ModuleType(core_module.__name__)
        fake.__dict__.update(vars(core_module))
        with patch.dict(sys.modules,{core_module.__name__:fake}):
            with self.assertRaisesRegex(ValueError,'foreign globals'):
                with campaign.guarded_execution(set()): pass
        substitute=type('CorePassManager',(PassManager,),{
            '__module__':core_module.__name__,'_native_register':CorePassManager._native_register})
        with patch.object(core_module,'CorePassManager',substitute):
            with self.assertRaisesRegex(AssertionError,'class was replaced'):
                with campaign.guarded_execution(set()): pass
        altered=FunctionType(CorePassManager._native_register.__code__,dict(vars(core_module)))
        with patch.object(CorePassManager,'_native_register',altered):
            with self.assertRaisesRegex(ValueError,'foreign globals'):
                with campaign.guarded_execution(set()): pass


if __name__=='__main__': unittest.main()
