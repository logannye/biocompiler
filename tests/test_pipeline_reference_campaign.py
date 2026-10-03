"""Source and observation controls; these do not execute an installed Core."""
from copy import deepcopy
import ast
from pathlib import Path
import tempfile
from types import FunctionType
import unittest

from tools import check_pipeline_reference_install as campaign


class ReferenceCampaignSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = campaign.Corpus()
        cls.archive, cls.blobs = campaign.original.source_archive()

    def test_complete_original_taxonomy_and_genuine_method_census(self):
        self.assertEqual({key: len(value) for key, value in self.corpus.taxonomy.items()}, {
            'public_manager': 412, 'initialization': 27, 'workflow': 41,
            'user_callback': 8, 'host_override': 2, 'authoring': 12, 'native_internal': 1718})
        modules, cases, sources = campaign.load_bodies(self.corpus, installed=False)
        self.assertEqual([case.id() for case in cases], self.corpus.index['test_ids'])
        self.assertEqual(len(sources), 18)
        for case in cases:
            self.assertIs(type(case), vars(next(module for module in modules
                if module.__name__ == type(case).__module__))[type(case).__name__])
        changed = deepcopy(self.corpus.events)
        changed[0]['kind'] = 'unreviewed.new-boundary'
        with self.assertRaisesRegex(AssertionError, 'behavior census'):
            campaign.classify(changed)

    def routed(self, kind):
        name = 'src/biocompiler/compiler/' + kind + '.py'
        raw = self.blobs[self.archive['files'][name]['sha256']]
        function = next(node for node in ast.parse(raw).body
            if isinstance(node, ast.FunctionDef) and node.name == 'run_' + kind + '_pipeline')
        offset = sum(len(line) for line in raw.splitlines(keepends=True)[:function.body[1].lineno - 1])
        prefix = ('    from sys import modules\n'
            '    _reference_backend = modules.get("biocompiler.reference_backend")\n'
            '    _reference_route = None if _reference_backend is None else _reference_backend.current()\n'
            '    if _reference_route is not None:\n'
            '        return _reference_route.' + kind + '(request, registry, manifests)\n').encode()
        return raw, prefix, offset, raw[:offset] + prefix + raw[offset:]

    def test_only_exact_public_prefix_at_the_original_callpoint_is_accepted(self):
        for kind in ('construct', 'molecular'):
            old, prefix, offset, current = self.routed(kind)
            proof = campaign.routed_source(kind, current)
            self.assertEqual(proof['original_sha256'], campaign.sha(old))
            self.assertEqual(proof['current_sha256'], campaign.sha(current))
            self.assertEqual(proof['offset'], offset)
            self.assertTrue(proof['whole_original_restoration'])
            mutants = (old, current + b'\n', current.replace(b' is not None:', b':', 1),
                current.replace(b'(request, registry, manifests)', b'(request, registry, {})', 1),
                old[:offset] + old[offset:].splitlines(keepends=True)[0] + prefix +
                    b''.join(old[offset:].splitlines(keepends=True)[1:]),
                current.replace(b'    require(', b'    print("changed")\n    require(', 1))
            for mutant in mutants:
                self.assertTrue(mutant != current)
                with self.subTest(kind=kind, mutation=campaign.sha(mutant)):
                    with self.assertRaisesRegex(AssertionError, 'exact five-line'):
                        campaign.routed_source(kind, mutant)
        with self.assertRaisesRegex(AssertionError, 'Unknown reference public route'):
            campaign.routed_source('reference-package', b'')

    def test_live_method_code_globals_and_source_origin_are_independent(self):
        modules, cases, _ = campaign.load_bodies(self.corpus, installed=False)
        function = getattr(type(cases[0]), cases[0]._testMethodName)
        source = campaign.source_function(function)
        self.assertEqual(source['file'], 'tests/test_construct_pipeline.py')
        copy = FunctionType(function.__code__, dict(function.__globals__), function.__name__,
                            function.__defaults__, function.__closure__)
        copy.__module__, copy.__qualname__ = function.__module__, function.__qualname__
        with self.assertRaisesRegex(AssertionError, 'foreign globals'):
            campaign.source_function(copy)
        foreign = FunctionType(function.__code__.replace(co_filename='/foreign/unchanged.py'),
            function.__globals__, function.__name__, function.__defaults__, function.__closure__)
        foreign.__module__, foreign.__qualname__ = function.__module__, function.__qualname__
        with self.assertRaisesRegex(AssertionError, 'another file'):
            campaign.source_function(foreign)
        with self.assertRaisesRegex(AssertionError, 'body source changed'):
            campaign.source_function(function, expected='0' * 64)


class ReferenceGraphCorrespondenceTests(unittest.TestCase):
    def graph(self, identity, *, items=None, roots=None):
        node = {'kind': 'sequence', 'class': 'tuple', 'items': items or [
            {'scalar': 'str', 'value': 'original'}]}
        return {identity: {'kind': 'graph', 'roots': roots or [['value', {'ref': identity + '/object'}]],
                'nodes': {identity + '/object': identity + '/node'}}, identity + '/node': node}

    def test_complete_value_kind_order_and_physical_bijection(self):
        left, right = self.graph('old'), self.graph('new')
        checked = campaign.GraphCorrespondence(left, right)
        checked.compare('old', 'new')
        self.assertEqual(checked.forward, {'old/object': 'new/object'})
        mutations = (
            lambda nodes: nodes['new/node'].update(**{'class': 'list'}),
            lambda nodes: nodes['new/node']['items'][0].update(value='changed'),
            lambda nodes: nodes['new/node']['items'].append({'scalar': 'int', 'value': 1}),
            lambda nodes: nodes['new'].update(nodes={}),
        )
        for mutate in mutations:
            changed = deepcopy(right); mutate(changed)
            with self.assertRaises(AssertionError):
                campaign.GraphCorrespondence(left, changed).compare('old', 'new')
        with self.assertRaisesRegex(AssertionError, 'coalesced'):
            checked.bind('second-original', 'new/object')
        with self.assertRaisesRegex(AssertionError, 'identity changed'):
            checked.bind('old/object', 'second-actual')

    def test_callback_role_is_compared_before_native_closure_correspondence(self):
        source = {'module': 'biocompiler.compiler.construct',
            'qualname': 'run_construct_pipeline.<locals>.verify_authority'}
        left, right = self.graph('old'), self.graph('new')
        left['old/node'] = {'kind': 'provider', 'source': source}
        right['new/node'] = {'kind': 'native-provider', 'role': 'reference_components.authority',
            'token': 'native/0', 'manager': {'ref': 'native/manager'}}
        checked = campaign.GraphCorrespondence(left, right)
        checked.compare('old', 'new')
        self.assertEqual(len(checked.provider_correspondence), 1)
        right['new/node']['role'] = 'reference_components.linkage'
        with self.assertRaisesRegex(AssertionError, 'callable slot'):
            campaign.GraphCorrespondence(left, right).compare('old', 'new')


class ReferenceFrameInitializerTests(unittest.TestCase):
    def test_reference_initializer_is_closed_and_counted_exactly_once(self):
        from tests.test_pipeline_fixed_provider_campaign import Script
        manager = campaign.manager
        channel, application = manager.declarations()
        fields = application['operations']['initialize-reference']['fields']
        with tempfile.TemporaryDirectory() as directory:
            receipt = {'_artifact_directory': directory, 'artifacts': {}}
            script = Script(receipt)
            sequence = script.command('initialize-reference', {name: None for name in fields})
            script.reply(sequence, None)
            script.close()
            artifacts = manager.Artifacts(directory, receipt['artifacts'])
            result = manager.validate_frames(script.rows, artifacts, channel, application,
                provider_calls=False, initializer='initialize-reference')
            self.assertEqual(result['operations'], ['initialize-reference'])
            with self.assertRaisesRegex(AssertionError, 'declared initializer'):
                manager.validate_frames(script.rows, artifacts, channel, application, provider_calls=False)
            for name in ('initialize-reference-extra', 'initialize-', 'reference', None):
                with self.assertRaisesRegex(AssertionError, 'Unknown closed manager initializer'):
                    manager.validate_frames(script.rows, artifacts, channel, application,
                        provider_calls=False, initializer=name)
            repeated = Script(receipt)
            for _ in range(2):
                repeated.reply(repeated.command('initialize-reference', {name: None for name in fields}), None)
            repeated.close()
            with self.assertRaisesRegex(AssertionError, 'exactly once'):
                manager.validate_frames(repeated.rows, manager.Artifacts(directory, receipt['artifacts']),
                    channel, application, provider_calls=False, initializer='initialize-reference')


class ReferenceSourceCallpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = campaign.Corpus()

    def fixture(self):
        # This control projects original argument graphs solely to exercise the
        # comparison rule. It is not a native observation or execution receipt.
        documents = dict(self.corpus.docs)
        rows = []
        for old in self.corpus.events:
            if old['parent'] is None or old['kind'] not in ('producer.generate_construct',
                    'override.generate_construct', 'producer.emit_reference_sequence', 'override.emit_reference_sequence'):
                continue
            generate = old['kind'].endswith('generate_construct')
            target = ('bound_request',) if generate else ('request', 'bound_construct', 'registry', 'molecular_manifests')
            row = {'id': len(rows), 'test': old['test'], 'kind': 'host.generate' if generate else 'host.emit',
                'outcome': old['outcome'], 'route': 'host' if old['kind'].startswith('override.') else 'native'}
            for phase in ('before', 'after'):
                graph = deepcopy(self.corpus.docs[old[phase]])
                roots = dict(graph['roots'])
                if old['kind'].startswith('override.'):
                    values = self.corpus.docs[graph['nodes'][roots['argument:args']['ref']]]['items']
                else:
                    source = ('argument:request',) if generate else (
                        'argument:request', 'argument:construct', 'argument:registry', 'argument:manifests')
                    values = [roots[key] for key in source]
                graph['roots'] = list(map(list, zip(target, values)))
                identity = campaign.sha(campaign.canonical(graph))
                documents[identity] = graph
                row[phase] = identity
            rows.append(row)
        return rows, documents

    def test_all_actual_callpoint_inputs_preserve_complete_original_values_and_aliases(self):
        rows, documents = self.fixture()
        graphs = campaign.GraphCorrespondence(self.corpus.docs, documents)
        checked = campaign.validate_source_callpoints(self.corpus, rows, graphs)
        self.assertEqual(len(checked), 36)
        self.assertEqual(sum(row['route'] == 'host' for row in checked), 2)
        self.assertGreater(len(graphs.forward), 300)
        for mutation in ('missing', 'route', 'order', 'value', 'identity'):
            altered = deepcopy(rows)
            changed = dict(documents)
            proof = campaign.GraphCorrespondence(self.corpus.docs, changed)
            if mutation == 'missing':
                altered.pop()
            elif mutation == 'route':
                altered[0]['route'] = 'host'
            elif mutation == 'order':
                altered[0], altered[-1] = altered[-1], altered[0]
            else:
                graph = deepcopy(documents[altered[0]['before']])
                ref = graph['roots'][0][1]['ref']
                if mutation == 'value':
                    graph['roots'][0][1] = {'scalar': 'bool', 'value': False}
                else:
                    # Keep the whole typed document equal, but detach this
                    # actual input from a previously witnessed source object.
                    proof.bind(ref, ref)
                    graph['nodes']['detached-equal-input'] = graph['nodes'][ref]
                    graph['roots'][0][1] = {'ref': 'detached-equal-input'}
                identity = campaign.sha(campaign.canonical(graph))
                changed[identity] = graph
                altered[0]['before'] = identity
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                campaign.validate_source_callpoints(self.corpus, altered, proof)


class ReferenceObservedEvidenceTests(unittest.TestCase):
    def observation(self):
        source='/installed/biocompiler/core_reference_host.py'
        node={'kind':'provider','source':{'path':source,'file':'src/biocompiler/core_reference_host.py'},
            'defaults':{'scalar':'str','value':source}}
        node_pin=campaign.sha(campaign.canonical(node))
        graph={'kind':'graph','roots':[['value',{'ref':'object/0'}]],'nodes':{'object/0':node_pin}}
        graph_pin=campaign.sha(campaign.canonical(graph))
        value={'events':[{'id':0,'source':{'file':source},'before':graph_pin,'after':graph_pin,
            'state_after':{'graph':graph_pin}}],'initializations':[],'raw_tracebacks':[],
            'documents':{node_pin:node,graph_pin:graph},'physical_objects':1,'result':None}
        return value,source

    def test_path_correspondence_rehashes_sources_without_rewriting_user_data(self):
        value,path=self.observation()
        before=deepcopy(value)
        actual=campaign.normalized_observation(value,{path:'src/biocompiler/core_reference_host.py'})
        self.assertEqual(value,before)
        node=next(row for row in actual['documents'].values() if row['kind']=='provider')
        self.assertEqual(node['source']['path'],'src/biocompiler/core_reference_host.py')
        self.assertEqual(node['defaults']['value'],path)
        self.assertNotEqual(actual['events'][0]['after'],value['events'][0]['after'])
        for identity,document in actual['documents'].items():
            self.assertEqual(identity,campaign.sha(campaign.canonical(document)))
        altered=deepcopy(value)
        next(row for row in altered['documents'].values() if row['kind']=='provider')['defaults']['value']='changed'
        self.assertNotEqual(campaign.normalized_observation(altered,{path:'src/biocompiler/core_reference_host.py'}),actual)

    def fixture(self):
        from types import SimpleNamespace
        command=lambda seq,op,start,end:{'sequence':seq,'operation':op,'start_frame':start,'end_frame':end,
            'outcome':{'status':'ok','value':None}}
        details=[{'commands':[command(1,'inspect-ordered-references',0,1),command(2,'get',2,3),
            command(3,'inspect-ordered-references',4,5)],'invocations':{}}]
        state=lambda seq,start,end:{'sequence':seq,'start_frame':start,'end_frame':end,'graph':'graph','reused':False}
        row={'id':0,'entry':0,'exit':1,'test':'case','kind':'manager.get','manager':0,'parent':None,
            'manager_parent':None,'outcome':'return','response_sequence':2,'start_frame':2,'end_frame':4,
            'state_before':state(1,0,2),'state_after':state(3,4,6)}
        observation={'events':[row],'initializations':[],'result':{'results':['complete'],'mode':'public_context'}}
        corpus=SimpleNamespace(index={'test_ids':['case'],'observed_results':['complete']})
        return observation,details,corpus

    def test_full_actual_inspection_command_and_chronology_bindings(self):
        actual,details,corpus=self.fixture()
        self.assertEqual(campaign.validate_observation_links(actual,details,corpus)['compact_inspections'],2)
        mutations=(lambda row:row.update(response_sequence=1),lambda row:row.update(end_frame=6),
            lambda row:row['state_before'].update(reused=True),lambda row:row['state_after'].update(sequence=1),
            lambda row:row.update(parent=0),lambda row:row.update(outcome='raise'))
        for mutate in mutations:
            changed=deepcopy(actual);mutate(changed['events'][0])
            with self.assertRaises(AssertionError):campaign.validate_observation_links(changed,details,corpus)
        changed=deepcopy(details);changed[0]['commands'].append({'sequence':4,'operation':'inspect-ordered-references'})
        with self.assertRaisesRegex(AssertionError,'unclaimed'):
            campaign.validate_observation_links(actual,changed,corpus)

    def test_source_origin_full_bytes_and_relocated_paths_are_not_self_authorized(self):
        import biocompiler
        import platform
        import sysconfig
        actual,path=self.observation()
        with tempfile.TemporaryDirectory() as directory:
            receipt={'_artifact_directory':directory,'artifacts':{}}
            raw=(campaign.ROOT/'src/biocompiler/core_reference_host.py').read_bytes()
            identity=campaign.manager.artifact(receipt,raw)
            proof={'package_root':'/installed/biocompiler','checkout_root':str(campaign.ROOT),
                'stdlib_root':str(Path(sysconfig.get_path('stdlib')).resolve()),'python_version':platform.python_version(),
                'files':{path:{'logical':'src/biocompiler/core_reference_host.py','artifact':identity}}}
            artifacts=campaign.manager.Artifacts(directory,receipt['artifacts'])
            def check(value):return campaign.validate_observation_sources(value,actual,actual['documents'],artifacts,
                package_path='/installed/biocompiler/__init__.py',runtime=platform.python_version())
            self.assertEqual(check(proof),{path:'src/biocompiler/core_reference_host.py'})
            changed=deepcopy(proof);changed['package_root']='/elsewhere/biocompiler'
            with self.assertRaisesRegex(AssertionError,'selected installed package'):check(changed)
            changed=deepcopy(proof);changed['files'][path]['logical']='src/biocompiler/core_reference_views.py'
            with self.assertRaisesRegex(AssertionError,'relocated'):check(changed)
            changed=deepcopy(proof);changed['files']['/extra.py']=deepcopy(changed['files'][path])
            with self.assertRaisesRegex(AssertionError,'census'):check(changed)
