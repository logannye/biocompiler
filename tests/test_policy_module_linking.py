"""Pure authoring and inert protocol peers; native module assurance is untested here."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from biocompiler import policy as p, core_policy_module_linking as api
from biocompiler.policy import module_linking as public, modules as mod
from biocompiler.core_client import CoreClient, CoreProtocolError, CoreRejected, CoreTimeout, CORE_VERSION, PROTOCOL, encode_json
from tests import test_core_policy_component_material as peer
from tools import generate_policy_module_linking_fixture as generator

digest = generator.digest


def lineage(modules, program):
    # Independent literal fixture ledger. No client lineage helper or composer.
    rows = []
    for i, declaration in enumerate(modules['context']['declarations']):
        rows.append({'source_path': f'/modules/context/declarations/{i}', 'flat_path': f'/program/declarations/{i}',
            'instance': None, 'template': None, 'declaration': declaration['id'], 'expanded': declaration['id']})
    for instance in modules['instances']:
        index, template = next((i, row) for i, row in enumerate(modules['templates']) if row['id'] == instance['template']['id'])
        for field in ('declarations', 'assumptions', 'guarantees'):
            for position, declaration in enumerate(template[field]):
                rows.append({'source_path': f'/modules/templates/{index}/{field}/{position}',
                    'flat_path': f'/program/declarations/{len(rows)}', 'instance': instance['name'],
                    'template': deepcopy(instance['template']), 'declaration': declaration['id'],
                    'expanded': instance['name'] + '/' + declaration['id']})
    return {'schema_version': api.LINKAGE_SCHEMA, 'implementation': api.LINKAGE_IMPLEMENTATION,
        'relation': 'exact_module_elaboration', 'bundle_fingerprint': digest(modules), 'program_fingerprint': digest(program),
        'lineage': rows, 'usage': {'unit': 'logical_module_work', 'charged_work': 1000, 'scanned_bytes': 1000},
        'behavior': 'unassessed', 'empirical': 'unassessed'}


def response(payload):
    modules, program = payload['modules'], payload['program']
    return {'schema_version': api.RESULT_SCHEMA, 'implementation': api.IMPLEMENTATION, 'validation_scope': api.VALIDATION_SCOPE,
        'modules': deepcopy(modules), 'program': deepcopy(program), 'linkage': lineage(modules, program),
        'invocation_fingerprint': digest({'modules': modules, 'program': program})}


def material_response(payload, *, accepted=True, export=False):
    child = peer.result(payload, accepted=accepted, export=export)
    modules = payload['modules']
    program = payload['request']['implementation_request']['document']['program']
    links = lineage(modules, program)
    artifact = None
    if child['artifact'] is not None:
        exported = child['artifact']
        manifest = {'schema_version': 'biocompiler.policy_module_mrna_manifest.v0.1', 'modules': deepcopy(modules),
            'linkage': deepcopy(links), 'material_manifest': deepcopy(exported['manifest']), 'material_manifest_sha256': exported['manifest_sha256'],
            'fasta_sha256': exported['fasta_sha256'], 'claim_scope': 'exact_module_elaboration_and_bounded_conditional_component_material', 'empirical': 'unassessed'}
        artifact = {'schema_version': 'biocompiler.policy_module_mrna_export.v0.1', 'fasta': exported['fasta'],
            'fasta_sha256': exported['fasta_sha256'], 'manifest': manifest, 'manifest_sha256': digest(manifest)}
    return {'schema_version': api.MATERIAL_SCHEMA, 'implementation': api.MATERIAL_IMPLEMENTATION, 'validation_scope': api.MATERIAL_SCOPE,
        'modules': deepcopy(modules), 'linkage': links, 'material': child,
        'invocation_fingerprint': digest({'modules': modules, 'request': payload['request'], 'candidate': child['candidate'], 'limits': payload['limits']}),
        'artifact': artifact}


class ModuleBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(generator.PATH.read_text())

    def test_three_modules_equal_independent_source_and_preserve_material_authority(self):
        self.assertEqual(generator.build(), self.packet)
        self.assertLess(generator.PATH.stat().st_size, 1_000_000)
        proposed = public.prepare(public.bundle_from_data(self.packet['modules']))
        self.assertEqual(p.to_data(proposed.program), self.packet['expected']['program'])
        self.assertEqual(proposed.to_data(), {'modules': self.packet['modules'], 'program': self.packet['program']})
        self.assertEqual(p.check(p.from_data(self.packet['request']['implementation_request']['document'], p.BuildRequest)).status, 'complete')
        seed = json.loads(generator.SEED.read_text())['cases'][0]
        for key in ('component_library', 'composition_rule', 'catalog_binding', 'resource_bindings'):
            self.assertEqual(self.packet['request'][key], seed['request'][key])
        self.assertEqual(self.packet['expected']['sequence'], 'CCAUGGCUUAAGGAAAA')
        self.assertEqual(self.packet['expected']['ordered_union'], seed['expected']['ordered_union'])
        self.assertEqual(hashlib.sha256(generator.SEED.read_bytes()).hexdigest(), self.packet['seed_sha256'])
        context = self.packet['request']['context']
        domain = self.packet['request']['implementation_request']['operating_domain']
        self.assertEqual(context['record_layout']['domain_digest'], digest(domain))
        for provider in context['providers']:
            self.assertEqual(provider['identity']['content_fingerprint'], digest(provider['body']))
            for capacity in provider['body']['capacities']:
                self.assertEqual(capacity['record_layout_digest'], digest(context['record_layout']))
            if provider['body']['kind'] == 'environment':
                self.assertEqual(provider['body']['grammar'], domain)
            if provider['body']['kind'] == 'interface':
                self.assertEqual([row['source'] for row in provider['body']['channels']], ['sense/condition', 'actuator/response'])

    def test_codec_retains_template_order_and_full_source_maps_with_isolated_snapshots(self):
        raw = deepcopy(self.packet['modules'])
        raw['templates'].reverse()
        decoded = public.bundle_from_data(raw)
        self.assertEqual(decoded.to_data(), raw)
        proposal = public.prepare(decoded)
        raw['templates'].clear()
        proposal.modules['templates'].clear()
        object.__setattr__(decoded.context, 'id', 'changed_after_preparation')
        self.assertEqual(proposal.program.id, 'module_retry')
        self.assertEqual(len(proposal.modules['templates']), 3)
        self.assertEqual(proposal.program.source_map[-1].declaration_id, 'actuator/response_initiation')
        with self.assertRaises(FrozenInstanceError):
            proposal._json = b'{}'

    def test_closed_codec_rejects_unknown_fields_stale_pins_and_kind_confusion(self):
        mutations = [lambda x: x.update(extra=True), lambda x: x.update(profile='future'),
            lambda x: x['templates'][0].update(extra=True), lambda x: x['templates'][0]['inputs'][0].update(extra=True),
            lambda x: x['templates'][1]['private'][0].update(extra=True),
            lambda x: x['instances'][0]['template'].update(content_fingerprint='0'*64),
            lambda x: x['instances'][0]['template'].update(extra=True),
            lambda x: x['instances'][0]['bindings'][0]['target'].update(extra=True),
            lambda x: x['instances'][0]['bindings'][0]['target'].update(kind='output'),
            lambda x: x['instances'].pop(), lambda x: x['templates'].append(deepcopy(x['templates'][0])),
            lambda x: x['instances'][0].update(assumptions=[{'$type': 'Ref', 'id': 'x', 'kind': 'Role'}]),
            lambda x: x['limits'].update(max_work=True), lambda x: x['limits'].update(max_depth=65)]
        for mutate in mutations:
            raw = deepcopy(self.packet['modules']); mutate(raw)
            with self.subTest(mutation=mutate), self.assertRaises((ValueError, TypeError)):
                public.bundle_from_data(raw)

    def test_pure_codec_preflight_rejects_cycles_depth_bytes_nodes_and_callbacks(self):
        raw = deepcopy(self.packet['modules']); raw['cycle'] = raw
        with self.assertRaisesRegex(mod.ModuleError, 'Cyclic'):
            public.bundle_from_data(raw)
        for key, number in (('max_depth', 1), ('max_bytes', 1), ('max_work', 1), ('max_ports', 1), ('max_instances', 1)):
            raw = deepcopy(self.packet['modules']); raw['limits'][key] = number
            with self.subTest(key=key), self.assertRaises((ValueError, TypeError)):
                public.bundle_from_data(raw)
        class Trap:
            def __iter__(self):
                raise AssertionError('No user callback may execute')
        with self.assertRaises(mod.ModuleError):
            public.bundle_from_data({'templates': Trap()})
        raw = {str(i): None for i in range(126000)}
        with self.assertRaises(mod.ModuleError):
            public.bundle_from_data(raw)

    def test_original_template_collision_and_forged_structure_reject_before_expansion(self):
        bundle = public.bundle_from_data(self.packet['modules'])
        altered = replace(bundle.instances[0].template, source_map=(p.SourceSpan('condition', 'different.py', 1),))
        duplicate = mod.instantiate(altered, 'other', bindings=bundle.instances[0].bindings)
        with self.assertRaisesRegex(mod.ModuleError, 'distinct original bodies'):
            public.ModuleBundle(bundle.context, bundle.instances + (duplicate,)).to_data()
        object.__setattr__(bundle.instances[0], 'template', 'not a template')
        with self.assertRaises(mod.ModuleError):
            bundle.to_data()

    def test_repinned_signature_and_hidden_reference_errors_are_local_authoring_errors(self):
        for change in ('binding', 'private', 'output'):
            raw = deepcopy(self.packet['modules'])
            if change == 'binding':
                raw['instances'][1]['bindings'][-1]['target']['port'] = 'private_response'
            elif change == 'private':
                raw['templates'][1]['private'].clear()
            else:
                raw['templates'][0]['outputs'][0]['declaration']['freshness']['amount'] = '1'
            for instance in raw['instances']:
                template = next(row for row in raw['templates'] if row['id'] == instance['template']['id'])
                instance['template']['content_fingerprint'] = digest(template)
            with self.subTest(change=change), self.assertRaises(mod.ModuleError):
                public.prepare(public.bundle_from_data(raw))

    def test_schema_is_closed_and_uses_independent_source_schema(self):
        schema = json.loads((generator.ROOT/'protocol/policy-module-bundle-v0.1.schema.json').read_text())
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(set(schema['required']), set(self.packet['modules']))
        self.assertEqual(schema['properties']['context']['$ref'], 'policy-language-v0.1.schema.json#/$defs/PolicyProgram')
        for key in ('template', 'template_pin', 'instance', 'port', 'limits'):
            self.assertFalse(schema['$defs'][key]['additionalProperties'])
        self.assertEqual(schema['$defs']['limits']['properties']['max_work']['maximum'], 16_000_000)
        self.assertEqual(len(p.model.REGISTRY), 45)


class ModuleTransportTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads(generator.PATH.read_text())
        self.modules, self.program = self.packet['modules'], self.packet['program']
        self.calls = []
        self.client = api.PolicyModuleLinkingClient(CoreClient(Path(sys.executable)))

    def exchange(self, *, mutate=None, negotiate=None, failure=None, reject=False, role='core', material=False, accepted=True):
        def call(_binary, encoded, _timeout, _cancelled):
            invocation = json.loads(encoded); self.calls.append(invocation)
            if invocation['operation'] == 'capabilities':
                result = peer.capabilities(role)
                result.update(operations=['capabilities', *api.PROFILE['operations'], *api.MATERIAL_PROFILE['operations']],
                    profiles={'policy_module_linking': deepcopy(api.PROFILE), 'policy_module_material': deepcopy(api.MATERIAL_PROFILE)},
                    validation_scopes=[api.VALIDATION_SCOPE, api.MATERIAL_SCOPE])
                if role == 'core':
                    result['operations'] += api.PRODUCER_PROFILE['operations']
                    result['profiles']['policy_module_material_producer'] = deepcopy(api.PRODUCER_PROFILE)
                if negotiate: negotiate(result)
            else:
                if failure: raise failure
                result = material_response(invocation['payload'], accepted=accepted, export=invocation['operation'].startswith('export')) if material else response(invocation['payload'])
                if mutate: mutate(result)
            rejected = reject and invocation['operation'] != 'capabilities'
            return encode_json({'protocol': PROTOCOL, 'request_id': invocation['request_id'], 'operation': invocation['operation'],
                'status': 'error' if rejected else 'ok', 'result': None if rejected else result,
                'diagnostics': [{'code': 'module_linkage', 'message': 'Expected exact local Effect, got different source',
                    'path': '/modules/instances/1/bindings/6'}] if rejected else [],
                'core': {'implementation': 'ocaml', 'version': CORE_VERSION, 'protocol': PROTOCOL, 'executable': role}}), 2 if rejected else 0
        return patch('biocompiler.core_client._exchange', side_effect=call)

    def check(self):
        return self.client.check(self.modules, self.program)

    def test_fresh_standalone_check_replay_and_public_proposal_namespace(self):
        proposal = public.prepare(public.bundle_from_data(self.modules))
        with self.exchange():
            checked = public.check(proposal, client=self.client)
            replayed = public.replay(proposal, client=self.client, report=checked.result)
        self.assertEqual(checked.result, replayed.result)
        self.assertEqual(p.to_data(checked.program), self.program)
        self.assertEqual(checked.modules, self.modules)
        self.assertEqual(checked.linkage['lineage'][-1]['source_path'], '/modules/templates/2/guarantees/0')
        self.assertEqual(checked.linkage['lineage'][-1]['expanded'], 'actuator/response_initiation')
        self.assertEqual([row['operation'] for row in self.calls][1::2], ['check-policy-module-linking', 'replay-policy-module-linking'])
        checked.modules.clear(); checked.linkage['lineage'].clear()
        self.assertEqual(len(checked.linkage['lineage']), 13)
        with self.assertRaises(FrozenInstanceError): checked.invocation_fingerprint = 'x'

    def test_lineage_pins_paths_order_semantic_claim_and_usage_tampering_reject(self):
        mutations = [lambda x: x.update(extra=True), lambda x: x.update(invocation_fingerprint='0'*64),
            lambda x: x['modules']['context'].update(id='changed'), lambda x: x['program']['source_map'].clear(),
            lambda x: x['linkage'].update(bundle_fingerprint='0'*64), lambda x: x['linkage'].update(program_fingerprint='0'*64),
            lambda x: x['linkage'].update(relation='behavioral_equivalence'), lambda x: x['linkage'].update(empirical='verified'),
            lambda x: x['linkage']['lineage'].reverse(), lambda x: x['linkage']['lineage'].pop(),
            lambda x: x['linkage']['lineage'][0].update(instance='sense'),
            lambda x: x['linkage']['lineage'][-1].update(source_path='/modules/templates/0/declarations/0'),
            lambda x: x['linkage']['lineage'][-1]['template'].update(content_fingerprint='0'*64),
            lambda x: x['linkage']['usage'].update(charged_work=True), lambda x: x['linkage']['usage'].update(scanned_bytes=8388609)]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.exchange(mutate=mutate), self.assertRaises(CoreProtocolError): self.check()
        with self.exchange():
            saved = self.check().result; saved['linkage']['usage']['charged_work'] += 1
            with self.assertRaises(CoreProtocolError): self.client.replay(self.modules, self.program, saved)

    def test_negotiation_rejection_and_diagnostic_paths_have_no_semantic_fallback(self):
        with self.exchange(negotiate=lambda x: x['profiles']['policy_module_linking'].update(bundle_schema='future')), self.assertRaises(CoreProtocolError):
            self.check()
        self.assertEqual([row['operation'] for row in self.calls], ['capabilities'])
        with self.exchange(reject=True), self.assertRaises(CoreRejected) as failure:
            self.check()
        self.assertEqual(failure.exception.response.diagnostics[0].path, '/modules/instances/1/bindings/6')
        with self.exchange(failure=CoreTimeout('timeout')), patch.object(mod, 'compose_modules', side_effect=AssertionError('No fallback')), self.assertRaises(CoreTimeout):
            self.check()

    def test_snapshot_precedes_native_negotiation_and_verify_check_is_supported(self):
        before = deepcopy(self.modules)
        with self.exchange(negotiate=lambda _: self.modules['templates'].clear()):
            checked = self.check()
        self.assertEqual(checked.modules, before)
        self.assertEqual(self.calls[-1]['payload']['modules'], before)
        self.modules = before
        with self.exchange(role='verify'):
            value = api.PolicyModuleLinkingClient(CoreClient(Path(sys.executable), role='verify')).check(self.modules, self.program)
        self.assertEqual(value.executable, 'verify')


class ModuleMaterialTransportTests(unittest.TestCase):
    exchange = ModuleTransportTests.exchange
    def setUp(self):
        ModuleTransportTests.setUp(self)
        self.legacy = peer.old.PolicyMaterialTransportTests(); self.legacy.setUp(); self.addCleanup(self.legacy.doCleanups)
        self.request = peer.original(); self.candidate = peer.candidate(self.request); self.limits = peer.old.fixture()['limits']
        # Empty template census is a legitimate context-only linkage; nested material
        # acceptance is still supplied solely by the inert existing transport peer.
        self.modules = public.ModuleBundle(p.from_data(self.request['implementation_request']['document']['program'], p.PolicyProgram), ()).to_data()
        self.material_client = api.PolicyModuleMaterialClient(CoreClient(Path(sys.executable)))

    def test_material_four_fresh_operations_retain_exact_child_wrapper(self):
        with self.exchange(material=True):
            compiled = public.compile_material(self.modules, self.request, limits=self.limits, client=self.material_client)
            checked = public.check_material(self.modules, self.request, candidate=compiled.candidate, limits=self.limits, client=self.material_client)
            replayed = public.replay_material(self.modules, self.request, candidate=compiled.candidate, limits=self.limits, report=checked.result, client=self.material_client)
            exported = self.material_client.export(self.modules, self.request, compiled.candidate, self.limits)
        self.assertEqual(compiled.result, replayed.result)
        self.assertEqual(exported.report, checked.report)
        self.assertEqual(exported.artifact['manifest']['material_manifest'], exported.material['artifact']['manifest'])
        self.assertEqual(exported.artifact['fasta'], exported.material['artifact']['fasta'])
        self.assertIsNone(checked.artifact)
        exported.candidate.clear(); exported.report.clear(); exported.linkage.clear()
        self.assertTrue(exported.candidate); self.assertTrue(exported.report); self.assertTrue(exported.linkage)

    def test_material_rejection_preserves_original_linkage_without_export(self):
        with self.exchange(material=True, accepted=False):
            rejected = self.material_client.check(self.modules, self.request, self.candidate, self.limits)
            with self.assertRaises(CoreProtocolError):
                self.material_client.export(self.modules, self.request, self.candidate, self.limits)
        self.assertEqual(rejected.status, 'not_accepted')
        self.assertEqual(rejected.report, peer.report(self.request, self.candidate, self.limits, accepted=False))
        self.assertEqual(rejected.linkage['relation'], 'exact_module_elaboration')
        self.assertIsNone(rejected.artifact)

    def test_material_nested_validation_root_lineage_and_export_hash_tampering_reject(self):
        mutations = [lambda x: x.update(invocation_fingerprint='0'*64), lambda x: x['linkage']['lineage'].pop(),
            lambda x: x['material'].update(request_fingerprint='0'*64), lambda x: x['material']['report'].update(empirical='verified'),
            lambda x: x['artifact'].update(fasta='>other\nAAAA\n'), lambda x: x['artifact'].update(manifest_sha256='0'*64),
            lambda x: x['artifact']['manifest'].update(material_manifest_sha256='0'*64),
            lambda x: x['artifact']['manifest']['modules']['context'].update(id='forged')]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.exchange(material=True, mutate=mutate), self.assertRaises(CoreProtocolError):
                self.material_client.export(self.modules, self.request, self.candidate, self.limits)

    def test_material_producer_negotiates_exact_profile_and_verify_cannot_compile(self):
        verify = api.PolicyModuleMaterialClient(CoreClient(Path(sys.executable), role='verify'))
        with self.assertRaises(CoreProtocolError): verify.compile(self.modules, self.request, self.limits)
        self.assertFalse(self.calls)
        with self.exchange(material=True, negotiate=lambda x: x['profiles']['policy_module_material_producer'].update(artifact='none')), self.assertRaises(CoreProtocolError):
            self.material_client.compile(self.modules, self.request, self.limits)
        self.assertEqual([row['operation'] for row in self.calls], ['capabilities'])
        with self.exchange(material=True, role='verify'):
            self.assertEqual(verify.check(self.modules, self.request, self.candidate, self.limits).status, 'checked_component_material')

    def test_material_publication_writes_exact_nested_manifest_and_fasta_atomically(self):
        with tempfile.TemporaryDirectory() as folder, self.exchange(material=True):
            path = Path(folder)/'linked.zip'
            exported = public.export_material(self.modules, self.request, candidate=self.candidate, limits=self.limits,
                client=self.material_client, output=path)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(archive.namelist(), ['program.fasta', 'manifest.json'])
                self.assertEqual(archive.read('program.fasta'), exported.artifact['fasta'].encode())
                self.assertEqual(archive.read('manifest.json'), encode_json(exported.artifact['manifest']))
            self.assertEqual(self.calls[-1]['operation'], 'export-policy-module-material')
            with self.assertRaises(FileExistsError):
                public.export_material(self.modules, self.request, candidate=self.candidate, limits=self.limits,
                    client=self.material_client, output=path)
