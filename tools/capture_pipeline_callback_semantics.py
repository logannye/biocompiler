"""Capture actual original Python callback-comparison and reentrancy semantics.

The fixtures use the existing constant-value pipeline and structural admission
setups. No expected decision or accepted record is used as an execution input.
Native replay must execute these small, source-pinned comparison recipes.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass, replace
from enum import Enum
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from biocompiler.compiler.pipeline import CheckSpec
from biocompiler.ir.serialization import fingerprint
from biocompiler.verification.evidence import EvidenceKind
from test_pipeline import PipelineTests, accepted
from test_component_admission import ComponentAdmissionTests

OUTPUT = ROOT / 'tests/conformance/pipeline-callback-semantics-v1.json'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def sha(value):
    return hashlib.sha256(value).hexdigest()


def plain(value):
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, 'to_dict'):
        return plain(value.to_dict())
    if is_dataclass(value):
        return {item.name: plain(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    if value is None or type(value) in (str, bool, int, float):
        return value
    raise TypeError('Uncaptured original value: ' + type(value).__qualname__)


def failure(error):
    return {'module': type(error).__module__, 'type': type(error).__name__, 'message': str(error)}


class IdentityOnly:
    """Callable with ordinary object equality, which is identity-only."""
    def __call__(self, context):
        return accepted(context)


class Comparable:
    def __init__(self, capture, label):
        self.capture = capture
        self.label = label

    def __call__(self, context):
        return accepted(context)

    def __eq__(self, other):
        return self.capture.compare(self, other)

    def __ne__(self, other):
        raise AssertionError('Validator dictionary comparison unexpectedly used __ne__')


class ComparableSubclass(Comparable):
    """A distinct right-hand subtype exercises Python reflected precedence."""
    def __eq__(self, other):
        return self.capture.compare(self, other)


class MethodOwner:
    def __init__(self, producer):
        self.producer = producer

    def validate(self, context):
        return accepted(context)

    def produce(self, context):
        return self.producer(context)


class Capture:
    def __init__(self, mode, name):
        self.mode = mode
        self.name = name
        self.events = []
        self.stack = []
        self.providers = {}
        self.objects = []
        self.owners = {}
        self.actions = []
        if mode == 'pass':
            fixture = PipelineTests('test_scope_complete_keeps_unresolved_biological_obligation')
            fixture.setUp()
            self.manager = fixture.manager
            self.contracts = {'first': fixture.first, 'version2': replace(fixture.first, version='2')}
            self.primary_check = 'identity_check'
            producer = fixture.producer(fixture.first)
            self.setup = {'target': plain(fixture.target),
                'dependencies': {'request': fingerprint(fixture.input), 'registry': fingerprint('v1')},
                'profiles': [plain(item) for item in self.manager._profiles.values()],
                'input': fixture.input, 'input_id': 'input', 'requirements': ['r'],
                'obligations': plain((fixture.exact, fixture.biological))}
        else:
            fixture = ComponentAdmissionTests('test_structural_root_records_real_checks_and_discharge')
            fixture.setUp()
            self.manager = fixture.manager
            self.contracts = {'first': fixture.policy, 'version2': replace(fixture.policy, version='2')}
            self.primary_check = 'selection'
            producer = accepted
            self.setup = {'target': plain(fixture.target),
                'dependencies': {'request': fingerprint(fixture.payload), 'registry': fingerprint('registry')},
                'profiles': [], 'input': None, 'input_id': None, 'requirements': [], 'obligations': [],
                'admission_payload': plain(fixture.payload)}
        self.add('producer', producer, {'kind': 'producer', 'recipe': 'original_pipeline_constant_producer' if mode == 'pass' else 'original_accepted'})
        self.base_producer = producer
        self.initial = self.snapshot()

    def add(self, label, value, descriptor):
        if label in self.providers or any(previous is value for previous, _ in self.objects):
            raise AssertionError('Each registered fixture label must denote one distinct retained object')
        self.providers[label] = descriptor
        self.objects.append((value, label))
        return value

    def label(self, value):
        for previous, label in self.objects:
            if previous is value:
                return label
        raise AssertionError('Original manager retained an uninventoried provider')

    def value(self, label):
        for value, identity in self.objects:
            if identity == label:
                return value
        raise AssertionError('Unknown fixture provider ' + label)

    def comparable(self, label, equality='true', actions=(), *, subclass=False):
        cls = ComparableSubclass if subclass else Comparable
        return self.add(label, cls(self, label), {'kind': 'comparable_subclass' if subclass else 'comparable',
            'equality': equality, 'actions': list(actions)})

    def identity(self, label):
        return self.add(label, IdentityOnly(), {'kind': 'identity_only'})

    def method(self, label, *, owner='owner', method='validate'):
        if owner not in self.owners:
            self.owners[owner] = MethodOwner(self.base_producer)
        return self.add(label, getattr(self.owners[owner], method),
                        {'kind': 'bound_method', 'owner': owner, 'method': method})

    def snapshot(self):
        manager = self.manager
        def validators(items):
            return {key: self.label(value) for key, value in items.items()}
        def registration(value):
            contract, producer, checks = value
            return {'contract': plain(contract), 'producer': self.label(producer), 'validators': validators(checks)}
        def admission(value):
            contract, checks = value
            return {'contract': plain(contract), 'validators': validators(checks)}
        pass_history = {key: registration(value) for key, value in manager._provider_history.items() if type(key) is str}
        input_history = {key[1]: admission(value) for key, value in manager._provider_history.items() if type(key) is tuple}
        expected = {'_target', '_dependencies', '_passes', '_component_inputs', '_provider_history', '_records', '_profiles'}
        if set(vars(manager)) != expected:
            raise AssertionError('Original manager state shape changed')
        state = {'target': plain(manager._target), 'dependencies': plain(manager._dependencies),
            'passes': {key: registration(value) for key, value in manager._passes.items()},
            'component_inputs': {key: admission(value) for key, value in manager._component_inputs.items()},
            'provider_history': pass_history, 'component_input_history': input_history,
            'records': {key: plain(value) for key, value in manager._records.items()},
            'profiles': {key: plain(value) for key, value in manager._profiles.items()}}
        order = {key: list(state[key]) for key in state if key != 'target'}
        order['combined_provider_history'] = [list(key) if type(key) is tuple else key for key in manager._provider_history]
        order['validators'] = {field: {key: list(value['validators']) for key, value in state[field].items()}
                               for field in ('passes', 'component_inputs', 'provider_history', 'component_input_history')}
        return {'state': state, 'order': order}

    def observe(self, kind, recipe, action):
        event = {'id': len(self.events), 'parent': self.stack[-1] if self.stack else None,
                 'kind': kind, 'recipe': recipe, 'before': self.snapshot()}
        self.events.append(event)
        self.stack.append(event['id'])
        try:
            result = action()
        except Exception as error:
            event.update(outcome='raised', error=failure(error))
            raise
        else:
            event.update(outcome='returned', result={'python_singleton': 'NotImplemented'} if result is NotImplemented else plain(result))
            return result
        finally:
            event['after'] = self.snapshot()
            assert self.stack.pop() == event['id']

    def compare(self, left, right):
        recipe = {'left': self.label(left), 'right': self.label(right)}
        def evaluate():
            descriptor = self.providers[recipe['left']]
            for action in descriptor['actions']:
                self.operation(action)
            result = descriptor['equality']
            if result == 'raise':
                raise ValueError('Original comparator rejected ' + recipe['left'])
            if result == 'not_implemented':
                return NotImplemented
            if result not in ('true', 'false'):
                raise AssertionError('Unknown comparison recipe')
            return result == 'true'
        return self.observe('comparison', recipe, evaluate)

    def registration(self, validator, *, contract='first', producer='producer', validators=None):
        return {'operation': 'register' if self.mode == 'pass' else 'register_component_input',
            'contract': contract, 'producer': producer if self.mode == 'pass' else None,
            'validators': validators if validators is not None else [[self.primary_check, validator]]}

    def operation(self, recipe):
        def invoke():
            op = recipe['operation']
            if op in ('register', 'register_component_input'):
                contract = self.contracts[recipe['contract']]
                validators = {key: self.value(value) for key, value in recipe['validators']}
                if op == 'register':
                    return self.manager.register(contract, self.value(recipe['producer']), validators)
                return self.manager.register_component_input(contract, validators)
            if op == 'set_dependency':
                return self.manager.set_dependency(recipe['key'], recipe['identity'])
            if op == 'get':
                return self.manager.get(recipe['identity'])
            if op == 'target':
                return self.manager.target
            raise AssertionError('Unknown original manager recipe ' + op)
        return self.observe('manager', recipe, invoke)

    def step(self, recipe):
        self.actions.append(recipe)
        try:
            self.operation(recipe)
        except Exception:
            # The exact original error and all preceding effects are retained.
            pass

    def finish(self):
        return {'id': self.mode + ':' + self.name, 'mode': self.mode,
            'setup': {**self.setup, 'contracts': {key: plain(value) for key, value in self.contracts.items()}},
            'providers': self.providers, 'actions': self.actions, 'initial_state': self.initial,
            'events': self.events, 'final_state': self.snapshot()}


def ordinary_case(mode, name):
    case = Capture(mode, name)
    mutation = {'operation': 'set_dependency', 'key': 'registry', 'identity': fingerprint('comparison mutation')}
    if name == 'identity_shortcut':
        case.comparable('old', 'raise')
        old, new = 'old', 'old'
    elif name == 'default_identity_distinct':
        case.identity('old'); case.identity('new')
        old, new = 'old', 'new'
    elif name == 'bound_method_equivalent':
        case.method('old'); case.method('new')
        old, new = 'old', 'new'
    else:
        equality = {'unequal': 'false', 'raises': 'raise', 'reflected_not_implemented': 'not_implemented',
                    'subclass_reflection': 'raise', 'mutation_raises': 'raise'}.get(name, 'true')
        actions = []
        if name in ('mutation_true', 'mutation_raises'):
            actions = [mutation]
        elif name == 'reentrant_reads':
            actions = [{'operation': 'target'}]
            if mode == 'pass':
                actions.append({'operation': 'get', 'identity': 'input'})
        elif name == 'reentrant_registration':
            actions = [case.registration('old', contract='version2')]
        case.comparable('old', equality, actions)
        case.comparable('new', subclass=name == 'subclass_reflection')
        old, new = 'old', 'new'
    case.step(case.registration(old))
    if name == 'history_restore':
        case.identity('version2_validator')
        case.step(case.registration('version2_validator', contract='version2'))
    case.step(case.registration(new))
    if name in ('mutation_true', 'mutation_raises') and mode == 'pass':
        case.step({'operation': 'get', 'identity': 'input'})
    return case.finish()


def ordered_case(mode, short_circuit):
    case = Capture(mode, 'comparison_short_circuit' if short_circuit else 'comparison_order')
    original = case.contracts['first']
    second = CheckSpec('second_check', EvidenceKind.EXACT, original.checks[0].discharges)
    case.contracts['first'] = replace(original, checks=(*original.checks, second))
    case.comparable('old_first')
    case.comparable('old_second', 'false' if short_circuit else 'true')
    case.comparable('new_first'); case.comparable('new_second')
    # Deliberately neither the contract order nor the replacement-map order.
    case.step(case.registration(None, validators=[['second_check', 'old_second'], [case.primary_check, 'old_first']]))
    case.step(case.registration(None, validators=[[case.primary_check, 'new_first'], ['second_check', 'new_second']]))
    return case.finish()


def producer_case(name):
    case = Capture('pass', name)
    if name == 'same_callable_cannot_self_certify':
        case.step(case.registration('producer'))
    elif name == 'distinct_callable_roles_skip_equality':
        case.comparable('left', 'raise'); case.comparable('right', 'raise')
        case.step(case.registration('right', producer='left'))
    elif name == 'distinct_equal_bound_method_roles':
        case.method('left', method='produce'); case.method('right', method='produce')
        case.step(case.registration('right', producer='left'))
    elif name == 'bound_producer_identity_change':
        case.method('left', method='produce'); case.method('right', method='produce')
        case.comparable('old', 'raise'); case.comparable('new', 'raise')
        case.step(case.registration('old', producer='left'))
        case.step(case.registration('new', producer='right'))
    else:
        raise AssertionError(name)
    return case.finish()


def capture():
    ordinary = ['identity_shortcut', 'default_identity_distinct', 'bound_method_equivalent',
        'equal', 'unequal', 'raises', 'reflected_not_implemented', 'subclass_reflection',
        'mutation_true', 'mutation_raises', 'reentrant_reads', 'reentrant_registration', 'history_restore']
    cases = []
    for mode in ('pass', 'admission'):
        cases.extend(ordinary_case(mode, name) for name in ordinary)
        cases.extend(ordered_case(mode, flag) for flag in (False, True))
    cases.extend(producer_case(name) for name in ('same_callable_cannot_self_certify',
        'distinct_callable_roles_skip_equality', 'distinct_equal_bound_method_roles', 'bound_producer_identity_change'))
    sources = ['tools/capture_pipeline_callback_semantics.py', 'tests/test_pipeline.py', 'tests/test_component_admission.py',
        'src/biocompiler/compiler/pipeline.py', 'src/biocompiler/compiler/passes.py',
        'src/biocompiler/artifacts/provenance.py', 'src/biocompiler/ir/intent.py',
        'src/biocompiler/ir/serialization.py', 'src/biocompiler/ir/stages.py',
        'src/biocompiler/semantics/context.py', 'src/biocompiler/verification/evidence.py']
    result = {'schema_version': 'biocompiler.pipeline_callback_semantics.v1',
        'claim_scope': 'actual_original_python_comparisons_and_live_manager_effects_no_native_acceptance',
        'source_files': {path: sha((ROOT / path).read_bytes()) for path in sources},
        'cases': cases, 'coverage': {'cases': len(cases),
            'manager_events': sum(event['kind'] == 'manager' for case in cases for event in case['events']),
            'comparison_events': sum(event['kind'] == 'comparison' for case in cases for event in case['events']),
            'raised_events': sum(event['outcome'] == 'raised' for case in cases for event in case['events'])}}
    result['inventory_fingerprint'] = sha(canonical(result))
    return result


if __name__ == '__main__':
    if OUTPUT.exists():
        raise SystemExit('Refusing to overwrite the captured original comparison oracle')
    value = capture()
    OUTPUT.write_bytes(canonical(value) + b'\n')
    print(json.dumps({'inventory_fingerprint': value['inventory_fingerprint'], **value['coverage']}, sort_keys=True))
