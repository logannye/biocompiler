"""Inert reference observer dispatch keeps every live eligible-frame check."""
import hashlib
import inspect
from pathlib import Path
import tempfile
import textwrap
from types import FunctionType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from biocompiler.compiler.pipeline import PassManager
from tools import check_pipeline_reference_install as campaign


PREFILTER = '''    # Only these original fixture callbacks can match the path-based lane.
    # Keep live path and callable checks for every eligible invocation.
    if code.co_name != 'register' and not (code.co_name in ('forged', 'producer') and 'context' in local):
        return None
'''


def observer():
    value = object.__new__(campaign.Observer)
    for name in ('pipeline_calls', 'authoring_calls', 'methods', 'host_calls', 'imports', 'entry_functions'):
        setattr(value, name, {})
    for name in ('initializer', 'complete_construct', 'native_provider'):
        setattr(value, name, object())
    value.complete_molecular, value.stack = set(), []
    return value


def frame(name, path, local=None, caller=None):
    def inert():
        return None
    code = inert.__code__.replace(co_name=name, co_qualname=name, co_filename=str(path))
    return SimpleNamespace(f_code=code, f_locals={} if local is None else local, f_back=caller)


def previous_describe():
    source = textwrap.dedent(inspect.getsource(campaign.Observer.describe))
    if source.count(PREFILTER) != 1:
        raise AssertionError('Reference dispatch prefilter is not the exact additive span')
    previous = source.replace(PREFILTER, '', 1)
    if hashlib.sha256(previous.encode()).hexdigest() != '7acb8dfb4721a71226d6df5c36a8c990071b40aa4df466c2a0552b90a1fc9f82':
        raise AssertionError('Reference dispatch changed an existing branch')
    namespace = dict(vars(campaign))
    exec(compile(previous, '<exact-previous-reference-dispatch>', 'exec'), namespace)
    return namespace['describe']


class ReferenceObserverDispatchTests(unittest.TestCase):
    def test_unrelated_names_and_context_free_callbacks_never_resolve_paths(self):
        old = previous_describe()
        paths = (campaign.ROOT / 'tests/test_construct_pipeline.py',
                 campaign.ROOT / 'tests/test_molecular_pipeline.py',
                 campaign.ROOT / 'src/biocompiler/ir/serialization.py', '<string>')
        for path in paths:
            for name, local in (('unrelated', {}), ('unrelated', {'context': object()}),
                                ('forged', {}), ('producer', {})):
                current = frame(name, path, local)
                self.assertIsNone(old(observer(), current))
                with self.subTest(name=name, path=path), patch.object(Path, 'resolve',
                        side_effect=AssertionError('Irrelevant frame performed a filesystem lookup')):
                    self.assertIsNone(campaign.Observer.describe(observer(), current))

    def test_eligible_registration_retains_exact_live_function_identity(self):
        old = previous_describe()
        for path in ('tests/test_construct_pipeline.py', 'tests/test_molecular_pipeline.py'):
            owner = object()
            current = frame('register', campaign.ROOT / path, {'manager': owner})
            function = FunctionType(current.f_code, {})
            with patch.object(PassManager, 'register', function):
                for describe in (old, campaign.Observer.describe):
                    watch = observer()
                    self.assertEqual(describe(watch, current), ('registration.wrapper', owner))
                    self.assertIs(watch.entry_functions[id(current)], function)
            with patch.object(PassManager, 'register', lambda: None):
                for describe in (old, campaign.Observer.describe):
                    with self.assertRaisesRegex(AssertionError, 'registration wrapper source identity'):
                        describe(observer(), current)

    def test_eligible_callbacks_recheck_retained_callable_each_time(self):
        old = previous_describe()
        for name in ('forged', 'producer'):
            for path in ('tests/test_construct_pipeline.py', 'tests/test_molecular_pipeline.py'):
                current = frame(name, campaign.ROOT / path, {'context': object()})
                function = FunctionType(current.f_code, {})
                for describe in (old, campaign.Observer.describe):
                    watch = observer()
                    lookup = Mock(return_value=function)
                    watch.corpus = SimpleNamespace(oracle=SimpleNamespace(Observer=SimpleNamespace(callable=lookup)))
                    self.assertEqual(describe(watch, current), ('callback.' + name, None))
                    lookup.assert_called_once_with(watch, current)
                    self.assertIs(watch.entry_functions[id(current)], function)
                    lookup.return_value = None
                    with self.assertRaisesRegex(AssertionError, 'retained callable identity'):
                        describe(watch, current)
                    self.assertEqual(lookup.call_count, 2)

    def test_eligible_path_is_resolved_fresh_after_symlink_retargeting(self):
        with tempfile.TemporaryDirectory() as directory:
            alias = Path(directory) / 'alias.py'
            alias.symlink_to(campaign.ROOT / 'tests/test_construct_pipeline.py')
            current = frame('register', alias, {'manager': object()})
            function = FunctionType(current.f_code, {})
            watch = observer()
            with patch.object(PassManager, 'register', function):
                self.assertEqual(campaign.Observer.describe(watch, current)[0], 'registration.wrapper')
                alias.unlink()
                alias.symlink_to(campaign.ROOT / 'src/biocompiler/ir/serialization.py')
                self.assertIsNone(campaign.Observer.describe(watch, current))
                alias.unlink()
                alias.symlink_to(campaign.ROOT / 'tests/test_molecular_pipeline.py')
                self.assertEqual(campaign.Observer.describe(watch, current)[0], 'registration.wrapper')

    def test_known_source_bound_entries_precede_filter_and_keep_source_check(self):
        old = previous_describe()
        current = frame('unrelated', campaign.ROOT / 'tools/check_pipeline_reference_install.py')
        function = FunctionType(current.f_code, {})
        for describe in (old, campaign.Observer.describe):
            watch = observer()
            watch.pipeline_calls[current.f_code] = ('pipeline.construct', function)
            source = Mock()
            with patch.dict(describe.__globals__, {'source_function': source}):
                self.assertEqual(describe(watch, current), ('pipeline.construct', None))
                source.assert_called_once_with(function)
                self.assertIs(watch.entry_functions[id(current)], function)
                source.side_effect = AssertionError('Changed live module/globals/code/source')
                with self.assertRaisesRegex(AssertionError, 'Changed live'):
                    describe(watch, current)

    def test_mock_override_keeps_actual_module_global_identity_before_filter(self):
        old = previous_describe()
        for describe in (old, campaign.Observer.describe):
            watch = observer()
            caller = frame('generate', '<string>')
            watch.host_calls[caller.f_code] = 'host.generate'
            function = Mock()
            current = frame('__call__', '<string>', {'self': function}, caller)
            watch.construct = SimpleNamespace(generate_construct=function)
            self.assertEqual(describe(watch, current), ('override.generate_construct', None))
            self.assertIs(watch.entry_functions[id(current)], function)
            watch.construct.generate_construct = Mock()
            with self.assertRaisesRegex(AssertionError, 'actual module global'):
                describe(watch, current)

    def test_other_known_entries_and_authoring_rejection_are_identical(self):
        old = previous_describe()
        for kind in ('authoring', 'method', 'initializer', 'construct', 'molecular', 'host', 'provider', 'import'):
            owner = SimpleNamespace(_manager=object())
            current = frame('unrelated', '<string>', {'self': owner, 'cls': PassManager})
            for describe in (old, campaign.Observer.describe):
                watch = observer()
                if kind == 'authoring':
                    watch.authoring_calls[current.f_code] = ('producer.generate_construct', object())
                    expected = ('producer.generate_construct', None)
                elif kind == 'method':
                    watch.methods[current.f_code] = '_native_register'; expected = ('manager.register', owner)
                elif kind == 'initializer':
                    watch.initializer = current.f_code; expected = ('native.initialize', None)
                elif kind == 'construct':
                    watch.complete_construct = current.f_code; expected = ('native.construct-phase', owner)
                elif kind == 'molecular':
                    watch.complete_molecular.add(current.f_code); expected = ('native.molecular-phase', owner)
                elif kind == 'host':
                    watch.host_calls[current.f_code] = 'host.generate'; expected = ('host.generate', None)
                elif kind == 'provider':
                    watch.native_provider = current.f_code; expected = ('native.provider', owner._manager)
                else:
                    watch.imports[current.f_code] = {PassManager: 'from_dict'}
                    expected = ('import.PassManager.from_dict', None)
                with self.subTest(kind=kind), patch.object(Path, 'resolve', side_effect=AssertionError('Late path check')):
                    self.assertEqual(describe(watch, current), expected)
                    if kind in ('authoring', 'import'):
                        watch.stack = [{'kind': 'native.initialize'}]
                        with self.assertRaisesRegex(AssertionError, 'Legacy reference'):
                            describe(watch, current)

    def test_dispatch_control_is_bound_into_complete_campaign_source_closure(self):
        self.assertEqual(campaign.SOURCES.count('tests/test_reference_observer_dispatch.py'), 1)
        previous_describe()


if __name__ == '__main__':
    unittest.main()
