"""Complete original reference-manager behavior and physical-origin controls."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('capture_reference_pipeline_semantics', ROOT / 'tools/capture_reference_pipeline_semantics.py')
oracle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oracle)


def view(index, docs, event, phase='after'):
    graph = docs[event[phase]]
    return graph, dict(graph['roots'])


def node(docs, graph, ref):
    return docs[graph['nodes'][ref['ref']]]


def field(docs, graph, ref, name):
    return dict(node(docs, graph, ref)['fields'])[name]


def mapping(docs, graph, ref):
    return {key['value']: value for key, value in node(docs, graph, ref)['items']}


class ReferencePipelineSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index, cls.docs = oracle.load()
        cls.fresh_index, cls.fresh_docs = oracle.capture()

    def test_complete_original_test_and_operation_census(self):
        self.assertEqual(self.index['inventory_fingerprint'], 'e5ce05abcd7645854f4ca2daf46632cc5871f9ed301c283220b018709991d417')
        self.assertEqual(len(self.index['test_ids']), 18)
        self.assertEqual(self.index['coverage']['managers'], 27)
        self.assertEqual(self.index['coverage']['top_level_operations'], 439)
        self.assertEqual(self.index['coverage']['events'], 2220)
        self.assertEqual(self.index['baseline']['results'], self.index['observed_results'])
        self.assertEqual({row['class'] for row in self.index['observed_results']}, {
            'test_construct_pipeline.ConstructPipelineTests', 'test_molecular_pipeline.MolecularPipelineTests'})
        self.assertEqual(self.index['source_substitutions'][0]['sha256'],
            '2b1dea35ac3c861f1e933cf7808a241f1f6596e59cc04ceb0ec32e4a54d27331')

    def test_fresh_isolated_originals_match_every_complete_byte_value(self):
        self.assertEqual(self.fresh_index, self.index)
        self.assertEqual(self.fresh_docs, self.docs)

    def test_linkage_callable_is_shared_between_admission_and_pass(self):
        linkage, compared = {}, 0
        for event in self.index['events']:
            if event['kind'] not in ('manager.register_component_input', 'manager.register'):
                continue
            graph, roots = view(self.index, self.docs, event, 'before')
            validators = mapping(self.docs, graph, roots['argument:validators'])
            if 'component_linkage' in validators:
                linkage[event['manager']] = validators['component_linkage']
            if 'layout_composition' in validators:
                self.assertEqual(validators['layout_composition'], linkage[event['manager']])
                compared += 1
        self.assertEqual(compared, 23)

    def test_public_build_records_and_fresh_imported_candidates(self):
        constructs, candidates, compared = {}, {}, 0
        for event in self.index['events']:
            if event['kind'] not in ('pipeline.construct', 'pipeline.molecular') or event['outcome'] != 'return':
                continue
            graph, roots = view(self.index, self.docs, event)
            build = roots['return']
            manager = field(self.docs, graph, build, 'manager')
            result = field(self.docs, graph, build, 'result')
            record = field(self.docs, graph, result, 'artifact')
            records = mapping(self.docs, graph, field(self.docs, graph, manager, '_records'))
            stage = 'construct' if event['kind'] == 'pipeline.construct' else 'molecular'
            self.assertEqual(record, records[stage])
            candidate = field(self.docs, graph, build, 'candidate')
            producer_name = 'callback.assemble' if stage == 'construct' else 'callback.emit'
            provider = [row for row in self.index['events'] if row['kind'] == producer_name and row['test'] == event['test']
                and row['id'] > event['id'] and row['outcome'] == 'return']
            # Only the actual same manager's enclosing pipeline subtree applies.
            descendants = []
            for row in provider:
                parent = row['parent']
                while parent is not None and parent != event['id']:
                    parent = self.index['events'][parent]['parent']
                if parent == event['id']:
                    descendants.append(row)
            self.assertEqual(len(descendants), 1)
            provider_graph, provider_roots = view(self.index, self.docs, descendants[0])
            output = field(self.docs, provider_graph, provider_roots['return'], 'output')
            self.assertNotEqual(candidate, output)
            if stage == 'construct':
                constructs[manager['ref']] = candidate
            else:
                # Row order is entry order, so the upstream Construct return row
                # occurs after the enclosing Molecular entry; find it directly.
                upstream = next(row for row in self.index['events'] if row['kind'] == 'pipeline.construct' and row['parent'] == event['id'])
                upstream_graph, upstream_roots = view(self.index, self.docs, upstream)
                wanted = field(self.docs, upstream_graph, upstream_roots['return'], 'candidate')
                self.assertEqual(field(self.docs, graph, build, 'construct'), wanted)
                self.assertEqual(field(self.docs, upstream_graph, upstream_roots['return'], 'manager'), manager)
            candidates[candidate['ref']] = True
            compared += 1
        self.assertEqual(compared, 30)
        self.assertEqual(len(candidates), 30)

    def test_real_overrides_and_register_wrappers_preserve_calls_and_failures(self):
        events = self.index['events']
        overrides = [row for row in events if row['kind'].startswith('override.')]
        self.assertEqual(len(overrides), 2)
        for event in overrides:
            before, roots = view(self.index, self.docs, event, 'before')
            after, returned = view(self.index, self.docs, event)
            self.assertEqual(node(self.docs, before, roots['callable'])['call_count'], 0)
            self.assertEqual(node(self.docs, after, returned['callable'])['call_count'], 1)
            self.assertEqual(node(self.docs, after, returned['callable'])['return_value'], returned['return'])
        wrappers = [row for row in events if row['kind'] == 'registration.wrapper']
        self.assertEqual(len(wrappers), 5)
        failing_roots = [row for row in events if row['kind'].startswith('pipeline.') and 'bad_authority' in row['test'] or
                         row['kind'].startswith('pipeline.') and 'failed_authority' in row['test']]
        self.assertTrue(failing_roots)
        for event in failing_roots:
            self.assertEqual(event['outcome'], 'raise')
            graph, roots = view(self.index, self.docs, event)
            mocks = [node(self.docs, graph, ref) for key, ref in roots.items() if key.startswith('global:') and 'ref' in ref
                     and node(self.docs, graph, ref)['kind'] == 'mock']
            self.assertTrue(mocks)
            self.assertTrue(all(value['call_count'] == 0 for value in mocks))

    def test_repaired_census_document_and_source_mutations_reject(self):
        value = deepcopy(self.index)
        value['events'][0]['test'] = 'forged.Test.test_missing'
        value['inventory_fingerprint'] = oracle.fingerprint(value)
        with self.assertRaisesRegex(AssertionError, 'ownership'):
            oracle.validate(value, self.docs, sources=False)
        value = deepcopy(self.index)
        value['observed_results'][0]['outcomes'][0]['status'] = 'failure'
        value['baseline']['results'] = deepcopy(value['observed_results'])
        value['inventory_fingerprint'] = oracle.fingerprint(value)
        with self.assertRaisesRegex(AssertionError, 'outcome'):
            oracle.validate(value, self.docs, sources=False)
        value = deepcopy(self.index)
        value['source_substitutions'].append(dict(value['source_substitutions'][0]))
        value['inventory_fingerprint'] = oracle.fingerprint(value)
        with self.assertRaisesRegex(AssertionError, 'substitution'):
            oracle.validate(value, self.docs)
        docs = dict(self.docs)
        docs.pop(next(iter(docs)))
        with self.assertRaisesRegex(AssertionError, 'document inventory'):
            oracle.validate(self.index, docs, sources=False)

    def test_raw_exception_frames_and_physical_tail_identity_are_complete(self):
        path = ROOT / ('generated/migration-next/reference-pipeline-runtime-' + str(sys.version_info.major) + '.' + str(sys.version_info.minor) + '.json')
        runtime = json.loads(path.read_bytes())
        oracle.validate_runtime(runtime, self.index, self.docs)
        self.assertEqual(len(runtime['original_tracebacks']), 116)
        for mutate in ('omit', 'site', 'exception', 'tail'):
            wrong = deepcopy(runtime)
            row = wrong['original_tracebacks'][-1]
            if mutate == 'omit':
                row['frames'].pop()
            elif mutate == 'site':
                row['frames'][0]['line'] += 1
            elif mutate == 'exception':
                row['exception'] = 'object/0'
            else:
                row['frames'][0]['next'] = row['frames'][0]['node']
            with self.assertRaisesRegex(AssertionError, 'raw original traceback|source frame|exception identity|traceback node|traceback tail'):
                oracle.validate_runtime(wrong, self.index, self.docs)

    def test_actual_code_and_canonical_function_namespace_required(self):
        with oracle.paths():
            from biocompiler.compiler.construct import run_construct_pipeline
        oracle.verify_function(run_construct_pipeline)
        clone = types.FunctionType(run_construct_pipeline.__code__, dict(run_construct_pipeline.__globals__),
            run_construct_pipeline.__name__, run_construct_pipeline.__defaults__, run_construct_pipeline.__closure__)
        with self.assertRaisesRegex(AssertionError, 'namespace'):
            oracle.verify_function(clone)

    def test_authority_documents_are_full_original_inputs_only(self):
        for alphabet, slots in self.index['authorities'].items():
            self.assertEqual(set(slots), {'request', 'registry', 'manifests'})
            request = self.docs[slots['request']]
            self.assertEqual(request['schema_version'], 'biocompiler.construct_request.v0.1')
            self.assertEqual(request['molecules'][0]['alphabet'], alphabet)
            self.assertEqual(self.docs[slots['registry']]['schema_version'], 'biocompiler.component_registry.v0.2')
            self.assertTrue(self.docs[slots['manifests']])


if __name__ == '__main__':
    unittest.main()
