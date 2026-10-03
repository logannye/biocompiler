"""Public route mechanics against complete Python wire fixtures, not native acceptance."""
import ast
import asyncio
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import inspect
import json
import os
from pathlib import Path
from types import MappingProxyType
import unittest
from unittest.mock import patch

import biocompiler
from biocompiler.compiler import construct, molecular, reference
from biocompiler.compiler.pipeline import PassManager
from biocompiler.core_client import CoreClient, CoreProtocolError
from biocompiler.core_reference_manager import ReferenceCorePassManager
from biocompiler.errors import SerializationError
from biocompiler.reference_backend import current, reference_core
from biocompiler import core_reference_manager as facade
from tests import test_core_reference_manager as fixture
ReferenceSession = fixture.ReferenceSession

# Capture real SDK/module aliases BEFORE selecting the native context.
SDK_CONSTRUCT = biocompiler.run_construct_pipeline
SDK_MOLECULAR = biocompiler.run_molecular_pipeline
CAPTURED_UPSTREAM = molecular.run_construct_pipeline
ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path(biocompiler.__file__).resolve().parent


class ReferenceRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.ReferenceManagerTests.setUpClass()
        cls.source = fixture.ReferenceManagerTests.source

    setUp = fixture.ReferenceManagerTests.setUp
    context = fixture.ReferenceManagerTests.context

    def args(self):
        return self.source['request'], self.source['registry'], self.source['manifests']

    def test_finite_source_restoration_and_exact_signature(self):
        originals = {'construct': '11cd63df1c3cde2da1deaa334b3d51e57c4d23343e76ebf682aebeb139baad14', 'molecular': 'a6763b804bfc2d691fee05d655d54affd44264994ec8869c8846e6c743aa83be'}
        for name, expected in originals.items():
            path = PACKAGE / 'compiler' / (name + '.py')
            active = path.read_text()
            prefix = ('    from sys import modules\n'
                '    _reference_backend = modules.get("biocompiler.reference_backend")\n'
                '    _reference_route = None if _reference_backend is None else _reference_backend.current()\n'
                '    if _reference_route is not None:\n'
                f'        return _reference_route.{name}(request, registry, manifests)\n')
            self.assertEqual(active.count(prefix), 1)
            original = active.replace(prefix, '', 1)
            self.assertEqual(hashlib.sha256(original.encode()).hexdigest(), expected)
            function = getattr(construct if name == 'construct' else molecular, 'run_' + name + '_pipeline')
            self.assertEqual(Path(function.__code__.co_filename).resolve(), path)
            self.assertIs(function.__globals__, vars(construct if name == 'construct' else molecular))
            before = next(node for node in ast.parse(original).body if isinstance(node, ast.FunctionDef) and node.name == function.__name__)
            after = next(node for node in ast.parse(active).body if isinstance(node, ast.FunctionDef) and node.name == function.__name__)
            self.assertEqual(ast.dump(before.args), ast.dump(after.args))
            self.assertEqual(ast.dump(before.returns), ast.dump(after.returns))

    def test_whole_adaptation_counterpart_restores_reviewed_base_bytes(self):
        raw = (ROOT / 'tests/conformance/reference-public-routing-source-counterpart-v1.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
            '949bd00942bbaa8c6107c490692e38007e41309b0d8f22b0bccd4d8f8514f074')
        witness = json.loads(raw)
        self.assertEqual(witness['base_revision'], 'e73743bc2f17597b57ac15869986255802289615')
        self.assertEqual(set(witness['entrypoint_prefixes']), {
            'src/biocompiler/compiler/construct.py', 'src/biocompiler/compiler/molecular.py'})
        for path, row in witness['entrypoint_prefixes'].items():
            current = (ROOT / path).read_bytes()
            self.assertEqual(hashlib.sha256(current).hexdigest(), row['current_sha256'])
            insertion = row['insertion']; start = insertion['byte_offset']; text = insertion['text'].encode()
            self.assertEqual(current[start:start + len(text)], text)
            self.assertEqual(hashlib.sha256(current[:start] + current[start + len(text):]).hexdigest(), row['original_sha256'])
        self.assertEqual(set(witness['adaptation_changes']), {
            'src/biocompiler/core_reference_manager.py', 'src/biocompiler/core_reference_provider_views.py'})
        for path, row in witness['adaptation_changes'].items():
            current = (ROOT / path).read_bytes()
            self.assertEqual(hashlib.sha256(current).hexdigest(), row['current_sha256'])
            restored = current.decode().splitlines(keepends=True)
            for change in reversed(row['changes']):
                start = change['current_start']; end = start + len(change['current_lines'])
                self.assertEqual(restored[start:end], change['current_lines'])
                restored[start:end] = change['original_lines']
            original = ''.join(restored).encode()
            self.assertEqual(len(original), row['original_bytes'])
            self.assertEqual(hashlib.sha256(original).hexdigest(), row['original_sha256'])
        self.assertEqual(set(witness['addition']), {'src/biocompiler/reference_backend.py'})
        for path, row in witness['addition'].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), row['sha256'])

    def test_default_ordinary_python_body_and_complete_records_unchanged(self):
        self.assertIsNone(current())
        actual = SDK_MOLECULAR(*self.args())
        original = self.source['molecular']
        self.assertIs(type(actual.manager), PassManager)
        self.assertEqual(actual.candidate.to_dict(), original.candidate.to_dict())
        self.assertEqual(actual.check_result.to_dict(), original.check_result.to_dict())
        self.assertEqual(actual.result.artifact.to_dict(), original.result.artifact.to_dict())
        self.assertEqual((actual.result.status, actual.result.scope, actual.result.unresolved),
                         (original.result.status, original.result.scope, original.result.unresolved))
        self.assertEqual(ReferenceSession.instances, [])

    def test_previously_imported_sdk_and_module_aliases_route_without_replacement(self):
        self.assertIs(SDK_CONSTRUCT, construct.run_construct_pipeline)
        self.assertIs(CAPTURED_UPSTREAM, construct.run_construct_pipeline)
        self.assertIs(SDK_MOLECULAR, molecular.run_molecular_pipeline)
        signature = inspect.signature(SDK_MOLECULAR)
        with reference_core(self.core):
            first = SDK_CONSTRUCT(*self.args())
            second = SDK_MOLECULAR(*self.args())
        self.assertIs(type(first.manager), ReferenceCorePassManager)
        self.assertIs(type(second.manager), ReferenceCorePassManager)
        self.assertIs(SDK_MOLECULAR, molecular.run_molecular_pipeline)
        self.assertEqual(inspect.signature(SDK_MOLECULAR), signature)
        self.assertEqual(len(ReferenceSession.instances), 2)

    def test_molecular_calls_actual_upstream_wrapper_and_retains_exact_outer_snapshot(self):
        calls = []
        def wrapper(request, registry, manifests):
            calls.append((request, registry, manifests, current()))
            return CAPTURED_UPSTREAM(request, registry, manifests)
        with patch.object(molecular, 'run_construct_pipeline', wrapper):
            with reference_core(self.core) as selected:
                build = SDK_MOLECULAR(*self.args())
        self.assertEqual(len(calls), 1)
        request, registry, manifests, route = calls[0]
        self.assertIs(request, self.source['request']); self.assertIs(registry, self.source['registry'])
        self.assertIs(type(manifests), MappingProxyType)
        self.assertIs(route, selected)
        host = build.manager._reference_host
        self.assertIs(manifests, host.molecular_manifests)
        self.assertIsNot(manifests, host.construct_manifests)
        for name, manifest in manifests.items():
            self.assertIs(manifest, host.construct_manifests[name])
        self.assertIs(build.construct, build.manager._reference_builds['construct'].candidate)

    def test_current_upstream_exception_is_same_object_without_fallback(self):
        error = KeyboardInterrupt('actual upstream replacement')
        with patch.object(molecular, 'run_construct_pipeline', side_effect=error) as replacement:
            with self.assertRaises(KeyboardInterrupt) as raised:
                with reference_core(self.core):
                    SDK_MOLECULAR(*self.args())
        self.assertIs(raised.exception, error)
        self.assertEqual(replacement.call_count, 1)
        self.assertEqual(ReferenceSession.instances, [])
        self.assertIsNone(current())

    def test_current_producer_and_emitter_overrides_preserve_snapshot_arguments(self):
        with reference_core(self.core):
            build = SDK_MOLECULAR(*self.args())
        manager = build.manager
        output = object(); generated = []; emitted = []
        def generate(parsed):
            generated.append(parsed)
            return output
        def emit(*args):
            emitted.append(args)
            return output
        with patch.object(construct, 'generate_construct', generate), patch.object(molecular, 'emit_reference_sequence', emit):
            for role, source in [('components_to_construct.producer', 'components'),
                                 ('construct_to_molecular.producer', 'construct')]:
                provider = manager._objects.resolve(manager.session.providers[role])
                self.assertIs(provider(self.context(manager, source)).output, output)
        self.assertEqual(len(generated), 1); self.assertEqual(len(emitted), 1)
        self.assertIsNot(generated[0], self.source['request'])
        self.assertIs(emitted[0][0], self.source['request'])
        self.assertIs(emitted[0][2], self.source['registry'])
        self.assertIs(emitted[0][3], manager._reference_host.molecular_manifests)

    def test_actual_package_global_slot_stays_dynamic_without_package_authority_claim(self):
        request = reference.ReferenceBuildRequest(self.source['request'])
        error = RuntimeError('actual package upstream slot')
        with patch.object(reference, 'run_molecular_pipeline', side_effect=error) as replacement:
            with reference_core(self.core):
                with self.assertRaises(RuntimeError) as raised:
                    reference.build_reference_package(request, ROOT / 'data/references/fap_car')
        self.assertIs(raised.exception, error)
        self.assertEqual(replacement.call_count, 1)
        self.assertEqual(ReferenceSession.instances, [])

    def test_selected_failure_and_context_exit_never_invoke_python_fallback_or_close_retained_manager(self):
        with reference_core(self.core):
            build = SDK_CONSTRUCT(*self.args())
        self.assertIsNone(current())
        self.assertFalse(build.manager.session.closed)
        self.assertIs(build.manager.get('construct'), build.result.artifact)
        error = CoreProtocolError('selected native transport failed')
        with patch.object(ReferenceCorePassManager, 'from_construct', side_effect=error) as native:
            with self.assertRaises(CoreProtocolError) as raised:
                with reference_core(self.core):
                    SDK_CONSTRUCT(*self.args())
        self.assertIs(raised.exception, error); self.assertEqual(native.call_count, 1)
        self.assertIsNone(current())

    def test_context_nested_restore_task_isolation_and_no_thread_implicit_selection(self):
        second = CoreClient(Path('/fixture/second-core'))
        with reference_core(self.core) as first:
            with reference_core(second) as nested:
                self.assertIs(current(), nested)
            self.assertIs(current(), first)
            with ThreadPoolExecutor(max_workers=1) as pool:
                self.assertIsNone(pool.submit(current).result())
        async def task(client):
            with reference_core(client) as selected:
                await asyncio.sleep(0)
                self.assertIs(current(), selected)
                return current().core
        async def run():
            return await asyncio.gather(task(self.core), task(second))
        self.assertEqual(asyncio.run(run()), [self.core, second])
        self.assertIsNone(current())

    def test_options_snapshot_and_explicit_client_are_required(self):
        limits = {'max_commands': 123}
        with reference_core(self.core, limits=limits):
            limits['max_commands'] = 999
            with patch.object(ReferenceCorePassManager, 'from_construct', return_value=object()) as native:
                SDK_CONSTRUCT(*self.args())
            self.assertEqual(native.call_args.kwargs['limits'], {'max_commands': 123})
        with self.assertRaises(TypeError):
            with reference_core('/fixture/not-a-client'):
                self.fail('invalid selection entered')

    def test_changed_upstream_map_and_copied_build_preserve_actual_native_owner(self):
        from dataclasses import replace
        saved = []
        def changed(request, registry, manifests):
            original = CAPTURED_UPSTREAM(request, registry, dict(manifests))
            saved.append(original)
            return replace(original)
        with patch.object(molecular, 'run_construct_pipeline', changed), reference_core(self.core):
            result = SDK_MOLECULAR(*self.args())
        self.assertIs(result.manager, saved[0].manager)
        self.assertIs(result.construct, saved[0].candidate)
        self.assertIsNot(result.manager._reference_host.construct_manifests,
                         result.manager._reference_molecular_host.molecular_manifests)
        with patch.object(molecular, 'run_construct_pipeline', return_value=self.source['construct']), reference_core(self.core):
            with self.assertRaisesRegex(CoreProtocolError, 'Python-manager continuation remains unsupported'):
                SDK_MOLECULAR(*self.args())

    def test_duck_build_reads_manager_once_and_candidates_at_final_source_boundaries(self):
        events, saved = [], []
        returned = object()
        def wrapper(*args):
            original = CAPTURED_UPSTREAM(*args)
            saved.append(original)
            class Duck:
                @property
                def manager(self):
                    events.append(('manager', tuple(original.manager._records)))
                    return original.manager
                @property
                def candidate(self):
                    events.append(('candidate', tuple(original.manager._records),
                        len([event for event in original.manager.session.events if event[0] == 'fixture-check'])))
                    return original.candidate if len(events) == 2 else returned
                def __getattr__(self, key):
                    raise AssertionError('Unused upstream field: ' + key)
            return Duck()
        with patch.object(molecular, 'run_construct_pipeline', wrapper), reference_core(self.core):
            result = SDK_MOLECULAR(*self.args())
        self.assertEqual(events, [('manager', ('components', 'construct')),
            ('candidate', ('components', 'construct', 'molecular'), 0),
            ('candidate', ('components', 'construct', 'molecular'), 1)])
        self.assertIs(result.construct, returned)
        self.assertIs(result.manager._objects.resolve(result.manager.session.checked_construct['object']), saved[0].candidate)
        self.assertIs(result.manager.reference_build_result('molecular'), result)

    def test_changed_check_candidate_document_is_not_replaced_by_upstream_cached_candidate(self):
        from dataclasses import replace
        saved = []
        def wrapper(*args):
            original = CAPTURED_UPSTREAM(*args)
            changed = replace(original.candidate, assumptions=original.candidate.assumptions + ('changed checker input',))
            saved.append((original, changed))
            class Duck:
                manager = original.manager
                candidate = changed
            return Duck()
        with patch.object(molecular, 'run_construct_pipeline', wrapper), reference_core(self.core):
            actual = SDK_MOLECULAR(*self.args())
        original, changed = saved[0]
        checked = actual.manager.session.checked_construct
        self.assertEqual(checked['value'], changed.to_dict())
        self.assertEqual(checked['tree'], facade._ordered(changed.to_dict()))
        self.assertNotEqual(checked['value'], original.candidate.to_dict())
        self.assertIs(actual.construct, changed)
        # The fixture returns a pre-recorded report; only hosted native replay
        # can prove that this changed document changes independent acceptance.

    def test_source_manager_and_either_candidate_exception_keep_exact_object_and_partial_state(self):
        for failed in ('manager', 'check', 'return'):
            with self.subTest(failed=failed):
                error = KeyboardInterrupt(failed)
                saved, events = [], []
                def wrapper(*args):
                    original = CAPTURED_UPSTREAM(*args)
                    saved.append(original)
                    class Duck:
                        @property
                        def manager(self):
                            events.append('manager')
                            if failed == 'manager':
                                raise error
                            return original.manager
                        @property
                        def candidate(self):
                            phase = 'check' if events[-1] == 'manager' else 'return'
                            events.append(phase)
                            if failed == phase:
                                raise error
                            return original.candidate
                    return Duck()
                with patch.object(molecular, 'run_construct_pipeline', wrapper), reference_core(self.core):
                    with self.assertRaises(KeyboardInterrupt) as raised:
                        SDK_MOLECULAR(*self.args())
                self.assertIs(raised.exception, error)
                manager = saved[0].manager
                self.assertEqual(events, ['manager'] if failed == 'manager' else
                    ['manager', 'check'] if failed == 'check' else ['manager', 'check', 'return'])
                self.assertEqual(tuple(manager._records), ('components', 'construct') if failed == 'manager' else
                    ('components', 'construct', 'molecular'))
                self.assertFalse(manager.session.closed)
                self.assertIsNone(manager._reference_final)
                self.assertEqual(sum(event[0] == 'fixture-check' for event in manager.session.events), int(failed == 'return'))

    def test_invalid_check_candidate_reports_original_serialization_error_without_second_read(self):
        saved, reads = [], []
        def wrapper(*args):
            original = CAPTURED_UPSTREAM(*args)
            saved.append(original)
            class Duck:
                manager = original.manager
                @property
                def candidate(self):
                    reads.append('candidate')
                    return object()
            return Duck()
        with patch.object(molecular, 'run_construct_pipeline', wrapper), reference_core(self.core):
            with self.assertRaisesRegex(SerializationError, 'Invalid molecular checker artifacts.'):
                SDK_MOLECULAR(*self.args())
        self.assertEqual(reads, ['candidate'])
        manager = saved[0].manager
        self.assertIn('molecular', manager._records)
        self.assertFalse(manager.session.closed)
        self.assertEqual(manager.session.checked_construct['tree'], ['scalar', None])
        self.assertIsNone(manager.session.returned_construct)

    def test_foreign_native_manager_uses_current_outer_authority_for_emitter(self):
        from dataclasses import replace
        request, registry, manifests = self.args()
        with reference_core(self.core):
            foreign = SDK_CONSTRUCT(request, registry, manifests)
        outer_request, outer_registry = replace(request), replace(registry)
        seen = []
        def wrapper(given_request, given_registry, snapshot):
            seen.append(snapshot)
            return foreign
        with patch.object(molecular, 'run_construct_pipeline', wrapper), reference_core(self.core):
            actual = SDK_MOLECULAR(outer_request, outer_registry, manifests)
        manager = actual.manager
        self.assertIs(manager, foreign.manager)
        self.assertIs(manager._reference_host.request, request)
        self.assertIs(manager._reference_molecular_host.request, outer_request)
        self.assertIs(manager._reference_molecular_host.registry, outer_registry)
        self.assertIs(manager._reference_molecular_host.molecular_manifests, seen[0])
        command = next(args for name, args in manager.session.requests if name == 'prepare-reference-molecular-public')
        self.assertIs(manager._objects.resolve(command['request_object']), outer_request)
        self.assertIs(manager._objects.resolve(command['registry_object']), outer_registry)
        self.assertEqual(command['manifests_tree'], facade._ordered(command['manifests']))
        calls, output = [], object()
        def emit(*args):
            calls.append(args)
            return output
        provider = manager._objects.resolve(manager.session.providers['construct_to_molecular.producer'])
        with patch.object(molecular, 'emit_reference_sequence', emit):
            self.assertIs(provider(self.context(manager, 'construct')).output, output)
        self.assertIs(calls[0][0], outer_request)
        self.assertIs(calls[0][2], outer_registry)
        self.assertIs(calls[0][3], seen[0])

    def test_returned_opaque_root_is_never_observed_or_serialized(self):
        class Opaque:
            def __getattribute__(self, name):
                raise AssertionError('Opaque returned root was inspected: ' + name)
        output = Opaque()
        def wrapper(*args):
            original = CAPTURED_UPSTREAM(*args)
            class Duck:
                manager = original.manager
                reads = 0
                @property
                def candidate(self):
                    self.reads += 1
                    return original.candidate if self.reads == 1 else output
            return Duck()
        with patch.object(molecular, 'run_construct_pipeline', wrapper), reference_core(self.core):
            actual = SDK_MOLECULAR(*self.args())
        self.assertIs(actual.construct, output)
        self.assertIs(actual.manager.reference_build_result('molecular').construct, output)

    def test_original_preflight_order_and_mapping_effects_before_selected_process(self):
        events = []
        class ObservedMapping(Mapping):
            def __iter__(self):
                events.append('iter'); return iter(self_outer.source['manifests'])
            def __len__(self):
                events.append('len'); return len(self_outer.source['manifests'])
            def __getitem__(self, key):
                events.append(('get', key)); return self_outer.source['manifests'][key]
        self_outer = self
        for selected in (False, True):
            events.clear()
            if selected:
                with reference_core(self.core):
                    with self.assertRaisesRegex(SerializationError, 'frozen ConstructRequest'):
                        SDK_MOLECULAR(object(), self.source['registry'], ObservedMapping())
            else:
                with self.assertRaisesRegex(SerializationError, 'frozen ConstructRequest'):
                    SDK_MOLECULAR(object(), self.source['registry'], ObservedMapping())
                expected = list(events)
            self.assertEqual(events, expected)
        self.assertEqual(ReferenceSession.instances, [])
        with reference_core(self.core):
            events.clear()
            with self.assertRaisesRegex(SerializationError, 'frozen ConstructRequest'):
                SDK_CONSTRUCT(object(), self.source['registry'], ObservedMapping())
            self.assertEqual(events, [])


if __name__ == '__main__':
    unittest.main()
