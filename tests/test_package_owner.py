"""Private ownership lane controls use Python peers only, no native execution."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler import core_package_owner as owner_module
from biocompiler.core_client import CoreClient,CoreProtocolError
from biocompiler.core_reference_manager import ReferenceCorePassManager
from biocompiler.core_pipeline_manager import capability_profile
from biocompiler.pipeline_callback_objects import CallbackObjects


class PackageOwnerTests(unittest.TestCase):
    def owner(self):
        owner=object.__new__(owner_module.PackageOwner)
        owner.core=CoreClient('/unused/explicit/core')
        owner.objects=CallbackObjects()
        self.addCleanup(owner.objects.close)
        owner.manager=owner._requested=None
        owner._active=0
        owner.session=object()
        return owner

    def test_exact_existing_objects_session_and_single_initializer(self):
        owner=self.owner()
        manager=object.__new__(ReferenceCorePassManager)
        with owner.initialize():
            self.assertIs(owner.objects_for(manager,owner.core,capability_profile()),owner.objects)
            self.assertIs(owner.bind(manager),owner.session)
            self.assertIs(owner.manager,manager)
            with self.assertRaises(CoreProtocolError):
                owner.bind(manager)
        self.assertIsNone(owner_module.current())
        with self.assertRaises(CoreProtocolError):
            with owner.initialize():
                pass

    def test_wrong_class_core_declaration_or_outside_scope(self):
        for changed in ('class','core','declaration','outside'):
            owner=self.owner()
            manager=object.__new__(ReferenceCorePassManager)
            def attempt():
                return owner.objects_for(object() if changed=='class' else manager,
                    CoreClient('/unused/explicit/core') if changed=='core' else owner.core,
                    None if changed=='declaration' else capability_profile())
            with self.subTest(changed=changed),self.assertRaises(CoreProtocolError):
                if changed=='outside':
                    attempt()
                else:
                    with owner.initialize():
                        attempt()
            self.assertIsNone(owner.manager)
            self.assertIsNone(owner_module.current())

    def test_nested_owner_and_original_exception_restore_scope(self):
        outer,inner=self.owner(),self.owner()
        marker=RuntimeError('same callback')
        with self.assertRaises(RuntimeError) as raised:
            with outer.initialize():
                with self.assertRaises(CoreProtocolError):
                    with inner.initialize():
                        pass
                self.assertIs(owner_module.current(),outer)
                raise marker
        self.assertIs(raised.exception,marker)
        self.assertIsNone(owner_module.current())

    def test_missing_bind_or_foreign_manager_cannot_take_session(self):
        owner=self.owner()
        one,two=object.__new__(ReferenceCorePassManager),object.__new__(ReferenceCorePassManager)
        with owner.initialize():
            with self.assertRaises(CoreProtocolError):
                owner.bind(one)
            owner.objects_for(one,owner.core,capability_profile())
            with self.assertRaises(CoreProtocolError):
                owner.bind(two)
            with self.assertRaises(CoreProtocolError):
                owner.objects_for(two,owner.core,capability_profile())
            self.assertIs(owner.bind(one),owner.session)

    def test_callback_protocol_named_exception_retains_original_identity(self):
        owner = self.owner()
        owner.actions = frozenset(('public-callback',))
        marker = CoreProtocolError('raised by the actual public callback')
        def callback(action, arguments):
            raise marker
        owner.handler = callback
        completion = owner._invoke('public-callback', None)
        self.assertEqual(completion.status, 'exception')
        with self.assertRaises(CoreProtocolError) as raised:
            owner.objects.rethrow(completion.value['exception_token'])
        self.assertIs(raised.exception, marker)

    def test_private_boundary_failure_is_not_an_opaque_callback_result(self):
        owner = self.owner()
        owner.actions = frozenset(('private-action',))
        marker = owner_module.PackageBoundaryError('invalid private capability')
        def callback(action, arguments):
            raise marker
        owner.handler = callback
        with self.assertRaises(owner_module.PackageBoundaryError) as raised:
            owner._invoke('private-action', None)
        self.assertIs(raised.exception, marker)

    def test_callback_non_json_result_is_a_protocol_failure(self):
        owner = self.owner()
        owner.actions = frozenset(('private-action',))
        owner.handler = lambda action, arguments: object()
        with self.assertRaises(CoreProtocolError):
            owner._invoke('private-action', None)


if __name__=='__main__':
    unittest.main()
