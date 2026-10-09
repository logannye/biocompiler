"""Inert target-planning transport adversaries; never native acceptance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from biocompiler import core_policy_planning as planning
from biocompiler.core_client import CORE_VERSION, CoreProtocolError, CoreRejected, CoreResponse, Diagnostic, encode_json
from biocompiler.policy import planning as public
from biocompiler.policy.examples import build_request
from biocompiler.policy.serialization import from_data, to_data
from biocompiler.policy.model import BuildRequest
from tests.test_core_policy import assessment

ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(encode_json(value)).hexdigest()


def catalog():
    return json.loads((ROOT / 'protocol/policy-target-capabilities-v0.1.json').read_text())


def descriptor(target):
    return next(row for row in catalog()['targets'] if row['target'] == target)


def request():
    return public.prepare_request(build_request('context_gated_response'), target='implementation')


def inert_result(original, *, planned=False, invalid=False):
    """An explicit nonexecuting source-only peer, not a target eligibility oracle."""
    target = descriptor(original['target'])
    source = assessment(original['document']) if isinstance(original['document'], dict) else None
    if invalid and source:
        source['status'] = 'invalid'
        source['diagnostics'] = [{'code': 'fixture_source_invalid', 'message': 'Original source rejected.', 'path': '/document'}]
    stages = [{'stage': stage, 'status': 'not_run'} for stage in planning.STAGES]
    if invalid:
        status, missing, blocked = 'invalid_source', [], 'source_contracts'
    elif planned:
        status, missing, blocked = 'planned', [], None
        for row in stages:
            row['status'] = 'not_applicable' if row['stage'] in ('component_arrangement', 'provider_dependencies') else 'completed'
    else:
        status, missing, blocked = 'missing_inputs', ['definitions'], 'operational_admission'
        stages[0]['status'] = 'completed'
    if blocked:
        next(row for row in stages if row['stage'] == blocked)['status'] = 'blocked'
    rows = source['declarations'] if source else []
    report = {'schema_version': planning.REPORT_SCHEMA, 'status': status, 'target': target,
        'catalog_fingerprint': planning.CATALOG_FINGERPRINT, 'request_fingerprint': digest(original),
        'document_fingerprint': digest(original['document']),
        'realization_request_fingerprint': digest(original['realization_request']) if original['realization_request'] is not None else None,
        'material_request_fingerprint': digest(original['material_request']) if original['material_request'] is not None else None,
        'source_assessment': source,
        'declarations': [{key: row[key] for key in ('id', 'kind', 'path')} for row in rows],
        'requirements': [{'id': row['id'], 'path': row['path'], 'source': row['value'], 'status': 'unassessed'}
                         for row in rows if row['kind'] == 'Requirement'],
        'obligations': [{'id': name, 'status': 'required', 'stage': 'full_pipeline'} for name in target['deferred_stages']],
        'missing_inputs': missing, 'stages': stages, 'selected_models': [], 'selected_components': [],
        'provider_dependencies': None, 'diagnostics': [] if not blocked else [{'category': status, 'stage': blocked,
            'code': 'fixture_first_blocker', 'message': 'Inert first-blocker fixture.', 'path': '/document', 'declaration_id': None}],
        'claims': deepcopy(planning.CLAIMS), 'usage': {'work': 1, 'max_work': original['limits']['max_work']}}
    if planned:
        model = original['realization_request']['implementation_library']['models'][0]
        report['selected_models'] = [{'node': 'original-node', 'model': deepcopy(model['identity']),
            'configuration_digest': model['configuration_digest'], 'primitive': model['body']['primitive']}]
    return {'schema_version': planning.RESULT_SCHEMA, 'implementation': planning.IMPLEMENTATION,
        'validation_scope': planning.VALIDATION_SCOPE, 'resource_profile': planning.RESOURCE_PROFILE,
        'request_fingerprint': digest(original), 'report_fingerprint': digest(report), 'report': report}


class InertTransport:
    role = 'core'

    def __init__(self):
        self.calls = []
        self.mutate = self.on_negotiate = self.error = None
        self.planned = self.invalid = False
        self.capabilities = SimpleNamespace(profiles={'policy_target_planning': deepcopy(planning.PROFILE)},
            validation_scopes=[planning.VALIDATION_SCOPE])

    def negotiate(self, operation, *, cancelled=None):
        self.calls.append(('negotiate', operation))
        if self.on_negotiate:
            self.on_negotiate()
        return self.capabilities

    def call(self, operation, payload, *, cancelled=None):
        self.calls.append((operation, deepcopy(payload)))
        if self.error:
            raise self.error
        value = inert_result(payload['request'], planned=self.planned, invalid=self.invalid)
        if self.mutate:
            self.mutate(value['report'])
            value['report_fingerprint'] = digest(value['report'])
        return CoreResponse('inert-plan', operation, 'ok', value, (), self.role, CORE_VERSION)


class TargetPlanningTransportTests(unittest.TestCase):
    def setUp(self):
        self.raw = request()
        self.transport = InertTransport()
        self.client = planning.PolicyTargetPlanningClient(self.transport)

    def reject(self, mutate):
        self.transport.mutate = mutate
        with self.assertRaises(CoreProtocolError):
            self.client.plan(self.raw)

    def test_embedded_target_descriptor_pins_bind_complete_catalog(self):
        full = catalog()
        self.assertEqual(digest(full), planning.CATALOG_FINGERPRINT)
        self.assertEqual({row['target']: digest(row) for row in full['targets']}, planning.TARGET_FINGERPRINTS)
        self.assertEqual(len(full['targets']), 16)
        self.assertEqual(set(planning.PROFILE['operations']), {'plan-policy-target', 'replay-policy-target-plan'})

    def test_multisite_and_sampled_step_targets_retain_explicit_nonaccepting_plans(self):
        for target, request_schema in (
            ('multi_site_implementation', 'biocompiler.policy_realization_request.v0.7'),
            ('step_quantitative_material', 'biocompiler.policy_component_material_request.v0.10'),
        ):
            with self.subTest(target=target):
                raw = public.prepare_request(build_request('context_gated_response'), target=target)
                result = self.client.plan(raw)
                self.assertEqual(result.status, 'missing_inputs')
                self.assertEqual(result.report['target'], descriptor(target))
                self.assertEqual(result.report['target']['request_schema'], request_schema)
                self.assertEqual(result.report['claims'], planning.CLAIMS)
                self.assertTrue(result.report['obligations'])
                self.assertTrue(all(row['status'] == 'required' for row in result.report['obligations']))
                self.assertEqual(result.report['selected_models'], [])
                self.assertEqual(result.report['selected_components'], [])

    def test_source_only_plan_retains_requirements_and_first_blocker_without_acceptance(self):
        result = self.client.plan(self.raw)
        self.assertEqual(result.status, 'missing_inputs')
        self.assertEqual(result.report['missing_inputs'], ['definitions'])
        self.assertEqual(result.report['claims'], planning.CLAIMS)
        self.assertEqual([row['source'] for row in result.report['requirements']],
                         [row for row in self.raw['document']['program']['declarations'] if row['$type'] == 'Requirement'])
        self.assertEqual([call[0] for call in self.transport.calls], ['negotiate', 'plan-policy-target'])

    def test_retained_report_is_immutable_and_freshly_replayed(self):
        first = self.client.plan(self.raw)
        first.report['obligations'].clear()
        self.assertTrue(first.report['obligations'])
        with self.assertRaises(FrozenInstanceError):
            first.status = 'planned'
        replayed = public.replay(self.raw, report=first, client=self.client)
        self.assertEqual(first.result, replayed.result)
        stale = first.result
        stale['report']['usage']['work'] = 2
        stale['report_fingerprint'] = digest(stale['report'])
        with self.assertRaises(CoreProtocolError):
            self.client.replay(self.raw, report=stale)

    def test_mutation_during_negotiation_cannot_change_authority(self):
        original = deepcopy(self.raw)
        self.transport.on_negotiate = lambda: self.raw['document'].update(profile='changed')
        result = self.client.plan(self.raw)
        self.assertEqual(self.transport.calls[-1][1]['request'], original)
        self.assertEqual(result.request_fingerprint, digest(original))

    def test_verify_executable_cannot_negotiate_a_planner(self):
        self.transport.role = 'verify'
        with self.assertRaises(CoreProtocolError):
            self.client.plan(self.raw)
        self.assertEqual(self.transport.calls, [])

    def test_negotiation_requires_exact_catalog_and_limits(self):
        for field, value in [('catalog_fingerprint', '0' * 64), ('max_result_bytes', planning.MAX_RESULT_BYTES + 1)]:
            with self.subTest(field=field):
                self.transport.capabilities.profiles['policy_target_planning'] = {**planning.PROFILE, field: value}
                with self.assertRaises(CoreProtocolError):
                    self.client.plan(self.raw)

    def test_original_source_and_optional_authorities_are_pinned(self):
        for field in ('request_fingerprint', 'document_fingerprint', 'realization_request_fingerprint', 'material_request_fingerprint'):
            with self.subTest(field=field):
                self.reject(lambda row, field=field: row.update({field: '0' * 64}))

    def test_target_profile_counts_and_limitations_cannot_be_rewritten(self):
        self.reject(lambda row: row['target']['limitations'].clear())
        self.reject(lambda row: row['target'].update(target='network_implementation'))
        self.reject(lambda row: row.update(catalog_fingerprint='0' * 64))

    def test_every_nonaccepting_claim_is_closed(self):
        for field in planning.CLAIMS:
            with self.subTest(field=field):
                self.reject(lambda row, field=field: row['claims'].update({field: 'passed'}))
        self.reject(lambda row: row.update(candidate={}))

    def test_complete_source_occurrences_and_requirements_cannot_be_dropped_or_rebound(self):
        self.reject(lambda row: row['declarations'].pop())
        self.reject(lambda row: row['declarations'][0].update(path='/document/program/declarations/9'))
        self.reject(lambda row: row['requirements'].clear())
        self.reject(lambda row: row['requirements'][0].update(status='passed'))
        self.reject(lambda row: row['requirements'][0]['source'].update(id='changed'))

    def test_required_full_pipeline_obligations_cannot_be_discharged_or_omitted(self):
        self.reject(lambda row: row['obligations'].pop())
        self.reject(lambda row: row['obligations'][0].update(status='completed'))
        self.reject(lambda row: row['obligations'].reverse())

    def test_diagnostic_categories_missing_inputs_and_stage_census_are_consistent(self):
        self.reject(lambda row: row.update(status='planned'))
        self.reject(lambda row: row['missing_inputs'].clear())
        self.reject(lambda row: row['diagnostics'][0].update(category='requirements_failed'))
        self.reject(lambda row: row['diagnostics'][0].update(declaration_id='absent'))
        self.reject(lambda row: row['stages'].pop())
        self.reject(lambda row: row['stages'].reverse())
        self.reject(lambda row: row['diagnostics'][0].update(stage='source_binding'))
        self.reject(lambda row: row['stages'][2].update(status='completed'))
        self.reject(lambda row: row['diagnostics'].append(deepcopy(row['diagnostics'][0])))

    def test_invalid_source_stays_a_native_diagnostic_outcome(self):
        self.transport.invalid = True
        self.raw['document']['program']['declarations'][0]['id'] = 'native-rejected-source'
        result = self.client.plan(self.raw)
        self.assertEqual(result.status, 'invalid_source')
        self.raw['document'] = 'malformed-source'
        malformed = self.client.plan(self.raw)
        self.assertEqual(malformed.report['source_assessment'], None)
        self.assertEqual(malformed.report['declarations'], [])

    def test_request_limits_reject_bool_unknown_fields_and_implicit_optional_inputs(self):
        for field in ('max_work', 'max_report_bytes', 'max_report_nodes'):
            for value in (True, 0):
                with self.subTest(field=field, value=value):
                    raw = deepcopy(self.raw)
                    raw['limits'][field] = value
                    with self.assertRaises(CoreProtocolError):
                        self.client.plan(raw)
        raw = deepcopy(self.raw)
        raw['extra'] = 'unreviewed'
        with self.assertRaises(CoreProtocolError):
            self.client.plan(raw)
        raw = deepcopy(self.raw)
        del raw['definitions']
        with self.assertRaises(CoreProtocolError):
            self.client.plan(raw)

    def test_usage_and_publication_stay_within_original_limits(self):
        self.reject(lambda row: row['usage'].update(work=True))
        self.reject(lambda row: row['usage'].update(work=self.raw['limits']['max_work'] + 1))
        self.reject(lambda row: row['usage'].update(max_work=self.raw['limits']['max_work'] + 1))
        self.raw['limits']['max_report_nodes'] = 1
        with self.assertRaises(CoreProtocolError):
            self.client.plan(self.raw)

    def test_native_resource_exhaustion_produces_no_partial_plan(self):
        self.transport.error = CoreRejected(CoreResponse('inert-plan', 'plan-policy-target', 'error', None,
            (Diagnostic('policy_target_plan_resource_limit', 'Planning work exhausted.', None),), 'core', CORE_VERSION))
        with self.assertRaisesRegex(CoreRejected, 'policy_target_plan_resource_limit'):
            self.client.plan(self.raw)
        self.assertEqual([call[0] for call in self.transport.calls], ['negotiate', 'plan-policy-target'])

    def test_explicit_complete_network_authority_and_selected_model_membership(self):
        material = json.loads((ROOT / 'core/test/data/policy_machine_network_v01.json').read_text())['request']
        original = material['implementation_request']
        self.raw = public.prepare_request(from_data(original['document'], BuildRequest), target='network_implementation',
                                         definitions=original['definitions'], realization_request=original)
        self.transport.planned = True
        self.assertEqual(self.client.plan(self.raw).status, 'planned')
        self.reject(lambda row: row['selected_models'][0].update(configuration_digest='0' * 64))
        self.reject(lambda row: row['selected_models'][0]['model'].update(id='absent'))
        self.reject(lambda row: row['selected_models'][0].update(primitive='made_up'))
        self.reject(lambda row: row['selected_models'].clear())
        self.reject(lambda row: row['stages'][4].update(status='not_run'))
        self.reject(lambda row: row['stages'][6].update(status='completed'))

    def test_typed_facade_snapshots_material_nested_authority_without_validation(self):
        material = json.loads((ROOT / 'core/test/data/policy_machine_network_v01.json').read_text())['request']
        document = from_data(material['implementation_request']['document'], BuildRequest)
        raw = public.prepare_request(document, target='network_material', material_request=material,
                                     limits=public.PlanningLimits(max_work=100))
        self.assertEqual(raw['realization_request'], material['implementation_request'])
        self.assertEqual(raw['material_request'], material)
        material['implementation_request']['profile'] = 'changed'
        self.assertNotEqual(raw['realization_request']['profile'], 'changed')
        for field in ('max_work', 'max_report_bytes', 'max_report_nodes'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                public.PlanningLimits(**{field: True})
        with self.assertRaises(TypeError):
            public.prepare_request(to_data(document), target='network_material')


class TargetPlanningProviderTransportTests(unittest.TestCase):
    def records(self):
        from tests.test_policy_prerequisite_evidence import records
        material, report = records()
        graph = report['prerequisites']['graph']
        for provider in material['context']['providers']:
            provider['identity']['content_fingerprint'] = digest(provider['body'])
            for node in graph['nodes']:
                if node['provider']['id'] == provider['identity']['id']:
                    node['provider'] = deepcopy(provider['identity'])
        return {'target': 'prerequisite_material', 'realization_request': material['implementation_request'],
                'material_request': material}, graph

    def test_complete_provider_occurrences_are_bound_without_claiming_capacity_or_closure(self):
        raw, graph = self.records()
        planning._provider_graph(graph, raw)
        missing = graph['nodes'][2]
        raw['material_request']['context']['providers'] = [row for row in raw['material_request']['context']['providers']
            if row['body']['definition'] != missing['definition']]
        missing['provider'] = None
        graph['issues'] = [{'kind': 'missing', 'code': 'prerequisite_provider_missing', 'references': [missing['definition']]}]
        planning._provider_graph(graph, raw)
        self.assertNotIn('complete', graph)
        self.assertNotIn('capacity', graph)

    def test_repinned_provider_roots_edges_definition_bodies_and_issue_categories_reject(self):
        mutations = [lambda graph: graph['roots'].pop(), lambda graph: graph['edges'].pop(),
            lambda graph: graph['nodes'][0]['provider'].update(content_fingerprint='0' * 64),
            lambda graph: graph['nodes'][0]['definition'].update(digest='0' * 64),
            lambda graph: graph.update(issues=[{'kind': 'passed', 'code': 'safe', 'references': []}])]
        for mutate in mutations:
            raw, graph = self.records()
            mutate(graph)
            with self.subTest(mutate=mutate), self.assertRaises(CoreProtocolError):
                planning._provider_graph(graph, raw)


if __name__ == '__main__':
    unittest.main()
