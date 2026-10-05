"""Original default ownership at fixed reference registration, without native IO."""
import ast
from contextlib import contextmanager
from copy import deepcopy
import hashlib
from pathlib import Path
import unittest
from unittest.mock import patch

from biocompiler import core_pipeline_manager as base
from biocompiler import core_reference_manager as facade
from biocompiler.compiler.pipeline import PassContract, PassManager
from biocompiler.core_client import CoreProtocolError
from biocompiler.semantics.context import PayloadFormat
from tests import test_core_reference_manager as fixtures


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def changed_attribute(owner, name, value):
    original = getattr(owner, name)
    try:
        setattr(owner, name, value)
        yield
    finally:
        setattr(owner, name, original)


class ReferenceContractTargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.ReferenceManagerTests.setUpClass()
        cls.source = fixtures.ReferenceManagerTests.source

    def setUp(self):
        self.fixture = fixtures.ReferenceManagerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def view(self, name='components_to_construct'):
        return base._contract_view(self.source['contracts'][name].to_dict(), admission=False)

    def test_original_source_calls_omit_targets_and_retain_the_same_default(self):
        pins = {
            'construct.py': '9a4220e6ffea941703e5177cfa639f5b2ed02e14ecbffe4a6dfb442b8bcdd0ee',
            'molecular.py': '040d85262f0b96f00e20276237a42bba9f68de8bd61e06148621432417ce4166',
            'pipeline.py': 'dccba32618ecc7923b8a02ff54f114d515ff4e50908f45e27a8cda0a3f531be0',
        }
        for name, expected in pins.items():
            raw = (ROOT / 'src/biocompiler/compiler' / name).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), expected)
            if name == 'pipeline.py':
                continue
            calls = [node for node in ast.walk(ast.parse(raw)) if isinstance(node, ast.Call)
                     and isinstance(node.func, ast.Name) and node.func.id == 'PassContract']
            self.assertEqual(len(calls), 1)
            self.assertEqual(len(calls[0].args), 10)
            self.assertNotIn('targets', [item.arg for item in calls[0].keywords])
            self.assertNotIn(None, [item.arg for item in calls[0].keywords])
        default = PassContract.__init__.__defaults__[1]
        self.assertIs(default, PassContract.targets)
        self.assertIs(default, PassContract.__dataclass_fields__['targets'].default)
        for contract in self.source['contracts'].values():
            self.assertIs(contract.targets, default)

    def test_actual_reference_methods_share_original_default_across_fresh_contracts(self):
        captured = []
        original = PassManager.register
        def register(manager, contract, producer, validators):
            captured.append(contract)
            return original(manager, contract, producer, validators)
        with patch.object(PassManager, 'register', register):
            self.fixture.build()
            self.fixture.build()
        self.assertEqual([item.id for item in captured],
                         ['components_to_construct', 'construct_to_molecular'] * 2)
        self.assertEqual(len({id(item) for item in captured}), 4)
        for contract in captured:
            self.assertIs(contract.targets, PassContract.targets)
            self.assertEqual(contract.to_dict(), self.source['contracts'][contract.id].to_dict())

    def test_generic_views_with_equal_values_keep_distinct_target_tuples(self):
        first, second = self.view(), self.view()
        self.assertEqual(first.targets, PassContract.targets)
        self.assertEqual(first.targets, second.targets)
        self.assertIsNot(first.targets, second.targets)
        self.assertIsNot(first.targets, PassContract.targets)
        facade._reference_contract_targets(first, expected=first.id)
        self.assertIs(first.targets, PassContract.targets)
        self.assertIsNot(second.targets, PassContract.targets)

    def test_changed_native_target_values_fail_before_registration(self):
        for targets in (['RNA'], ['RNA', 'DNA'], ['DNA', 'RNA', 'DNA']):
            with self.subTest(targets=targets):
                original = fixtures.ReferenceSession.registration
                def registration(session, name):
                    value = deepcopy(original(session, name))
                    value['contract']['targets'] = targets
                    return value
                with patch.object(fixtures.ReferenceSession, 'registration', registration):
                    with self.assertRaisesRegex(CoreProtocolError, 'Invalid native reference registration') as caught:
                        self.fixture.build(molecular=False)
                    self.assertIsInstance(caught.exception.__cause__, CoreProtocolError)
                    self.assertIn('Native reference contract targets', str(caught.exception.__cause__))
                session = fixtures.ReferenceSession.instances[-1]
                self.assertNotIn('register', [name for name, _ in session.requests])
                self.assertTrue(session.invalidated)

    def test_replaced_default_provenance_is_rejected_even_when_values_match(self):
        original = PassContract.targets
        copied = tuple(list(original))
        self.assertIsNot(copied, original)
        field = PassContract.__dataclass_fields__['targets']
        initializer = PassContract.__init__
        defaults = initializer.__defaults__
        mutations = (
            patch.object(PassContract, 'targets', copied),
            patch.object(field, 'default', copied),
            changed_attribute(initializer, '__defaults__', (defaults[0], copied, *defaults[2:])),
            changed_attribute(initializer, '__code__', initializer.__code__.replace()),
            patch.object(PassContract, '__init__', lambda *args, **kwargs: None),
        )
        for mutation in mutations:
            contract = self.view()
            with mutation:
                with self.assertRaisesRegex(CoreProtocolError, 'target default changed'):
                    facade._reference_contract_targets(contract, expected=contract.id)
                self.assertIsNot(contract.targets, original)
        self.assertIs(PassContract.targets, original)
        self.assertIs(initializer.__defaults__, defaults)

    def test_unknown_origin_and_non_enum_lookalikes_are_rejected(self):
        for expected in ('custom', 'construct_to_molecular'):
            with self.assertRaisesRegex(CoreProtocolError, 'target origin'):
                facade._reference_contract_targets(self.view(), expected=expected)
        contract = self.view()
        object.__setattr__(contract, 'targets', ('DNA', 'RNA'))
        self.assertEqual(contract.targets, (PayloadFormat.DNA, PayloadFormat.RNA))
        with self.assertRaisesRegex(CoreProtocolError, 'Native reference contract targets'):
            facade._reference_contract_targets(contract, expected=contract.id)
