"""Independent source packets and inert network transport; no native acceptance."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from biocompiler import policy as p
from biocompiler.policy import implementation as public, component_material as material_public, module_linking
from biocompiler import core_policy_implementation as implementation, core_policy_component_material as material
from biocompiler import core_policy_module_linking as linked, core_policy_refinement as refinement
from biocompiler.core_client import CORE_VERSION, CoreProtocolError, CoreResponse
from tests import test_core_policy_implementation as peer
from tests import test_policy_module_linking as linking_peer
from tools import generate_policy_machine_network_fixture as generator


def fixture():
    return json.loads(generator.PATH.read_text())


def inert_candidate(request):
    """Only source/endpoint identity ledgers; not an executable graph oracle."""
    declarations = request['document']['program']['declarations']
    kinds = lambda kind: [row for row in declarations if row['$type'] == kind]
    binding = {'schema_version': implementation.NETWORK_BINDING_SCHEMA, 'profile': implementation.NETWORK_BINDING_PROFILE,
        'catalog_entry': request['catalog_bindings'][0]['entry_id'], 'rules': [],
        'observations': [{'source': row['id'], 'bank': f'observation/{i}', 'input': f'evidence/{i}'} for i, row in enumerate(kinds('Observation'))],
        'states': [{'source': row['id'], 'register': f'state/{i}'} for i, row in enumerate(kinds('StateStore'))],
        'effects': [{'source': row['id'], 'bank': f'attempt/{i}', 'feedback': f'feedback/{i}'} for i, row in enumerate(kinds('Effect'))],
        'machines': [{'source': row['id'], 'bank': f'machine/{i}'} for i, row in enumerate(kinds('Machine'))], 'transitions': []}
    policies, groups = [], []
    for machine in kinds('Machine'):
        if machine['arbitration'] not in policies: policies.append(machine['arbitration']); groups.append([])
    machines = {row['id']: row for row in kinds('Machine')}
    for i, row in enumerate(kinds('Transition')):
        group = policies.index(machines[row['machine']['id']]['arbitration'])
        lane = len(groups[group]); groups[group].append(i)
        binding['transitions'].append({'source': row['id'], 'gate': f'transition/{i}/gate', 'commit': f'transition/{i}/commit',
            'arbiter': f'arbitration/{group}', 'lane': lane})
    node_ids = [row['bank'] for key in ('observations', 'effects', 'machines') for row in binding[key]]
    node_ids += [row['register'] for row in binding['states']] + [f'arbitration/{i}' for i in range(len(groups))]
    node_ids += [row[key] for row in binding['transitions'] for key in ('gate', 'commit')]
    graph = {'schema_version': 'biocompiler.policy_implementation.v0.1', 'profile': 'biocompiler.policy_staged_primitives.v0.1',
        'observable_profile': 'biocompiler.policy_staged_observables.v0.1',
        'authority': {'source_artifact_digest': peer.digest(request['document']), 'descriptors_digest': peer.digest(request['definitions']),
            'domain_digest': peer.digest(request['operating_domain']), 'implementation_catalog_digest': peer.digest(request['document']['implementations']),
            'library_digest': peer.digest(request['implementation_library'])}, 'slot_layout': {'id': 'encounters', 'slots': 2},
        'nodes': [{'id': identity, 'model': request['implementation_library']['models'][0]['identity']} for identity in node_ids],
        'wires': [], 'atomic_groups': [], 'semantic_exports': [], 'occurrences': [],
        'inputs': [{'id': row['input'], 'kind': 'evidence', 'consumer': {'node': row['bank'], 'port': 'samples'}} for row in binding['observations']]
            + [{'id': row['feedback'], 'kind': 'feedback', 'consumer': {'node': row['bank'], 'port': 'feedback'}} for row in binding['effects']]}
    return {'schema_version': implementation.CANDIDATE_SCHEMA, 'behavior': peer.source_peer.candidate(request['document'], request['definitions']),
        'implementation': graph, 'binding': binding}


def inert_result(payload):
    request = payload['request']; actual = deepcopy(payload.get('candidate') or inert_candidate(request))
    report = peer.report(request, actual, payload['limits'])
    report['binding'].update(schema_version=implementation.NETWORK_BINDING_REPORT_SCHEMA, profile=implementation.NETWORK_BINDING_PROFILE,
        observable_profile='biocompiler.policy_staged_observables.v0.1', state_encoding='exact_ordered_source_labels')
    report['binding']['source_admission'].update(schema_version='biocompiler.policy_realization_admission.v0.2',
        profile=implementation.NETWORK_REQUEST_PROFILE, pending_dependencies=implementation._pending_dependencies(request))
    return {'schema_version': implementation.RESULT_SCHEMA, 'implementation': implementation.NETWORK_IMPLEMENTATION,
        'resource_profile': implementation.RESOURCE_PROFILE, 'validation_scope': implementation.NETWORK_VALIDATION_SCOPE,
        'request_fingerprint': peer.digest(request), 'candidate_fingerprint': peer.digest(actual),
        'invocation_fingerprint': peer.digest({'request': request, 'candidate': actual, 'limits': payload['limits']}),
        'report_fingerprint': peer.digest(report), 'candidate': actual, 'report': report}


class InertTransport:
    role = 'core'
    def __init__(self, component=False):
        self.component, self.calls, self.mutate = component, [], None
        api = material if component else implementation
        key = 'policy_network_material' if component else 'policy_network_implementation'
        self.capabilities = SimpleNamespace(profiles={key: deepcopy(api.NETWORK_PROFILE), key + '_producer': deepcopy(api.NETWORK_PRODUCER_PROFILE)},
            validation_scopes=[api.NETWORK_VALIDATION_SCOPE])
    def negotiate(self, operation, *, cancelled=None):
        self.calls.append(('negotiate', operation)); return self.capabilities
    def call(self, operation, payload, *, cancelled=None):
        self.calls.append((operation, deepcopy(payload)))
        value = None if self.component else inert_result(payload)
        if self.mutate: self.mutate(value)
        return CoreResponse('inert-network', operation, 'ok', value, (), self.role, CORE_VERSION)


class NetworkFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.packet = fixture()

    def test_independent_fixture_and_literal_module_expansion_are_source_complete(self):
        self.assertEqual(generator.build(), self.packet)
        self.assertLess(generator.PATH.stat().st_size, 2_000_000)
        for raw in (self.packet['request']['implementation_request'], self.packet['shared']['request']):
            document = p.from_data(raw['document'], p.BuildRequest)
            self.assertEqual(p.check(document).status, 'complete')
            self.assertEqual(p.to_data(document), raw['document'])
        bundle = module_linking.bundle_from_data(self.packet['modules'])
        proposed = module_linking.prepare(bundle)
        self.assertEqual(p.to_data(proposed.program), self.packet['expected']['program'])
        self.assertEqual(self.packet['program'], self.packet['request']['implementation_request']['document']['program'])

    def test_original_communication_unknown_async_reset_and_priority_contracts(self):
        request = self.packet['request']['implementation_request']
        rows = request['document']['program']['declarations']
        observations = [row for row in rows if row['$type'] == 'Observation']
        self.assertEqual([row['coherence'] for row in observations], ['stream_a', 'stream_b'])
        self.assertEqual([row['freshness']['amount'] for row in observations], ['2', '3'])
        machines = [row for row in rows if row['$type'] == 'Machine']
        self.assertNotEqual(machines[0]['arbitration'], machines[1]['arbitration'])
        assignments = [(row['machine']['id'], item['state']['id']) for row in rows if row['$type'] == 'Transition' for item in row['assignments']]
        self.assertEqual(assignments, [('alpha/machine_a', 'alpha/permit')] * 4)
        domain = request['operating_domain']
        self.assertEqual(domain['lifecycle_factors'], [{'slots': ['e1'], 'ticks': [7], 'actions': ['keep', 'reset']}])
        self.assertTrue(any(row['available_tick'] > row['observed_tick'] for row in domain['fixed_observations']))
        self.assertTrue(any(row['status'] == 'missing' and row['observation'] == 'sense/condition_a' for row in domain['fixed_observations']))
        self.assertTrue(all(row['value'] is False for row in domain['fixed_observations'] if row['slot'] == 'e2'))
        self.assertEqual([row['ticks'] for row in domain['feedback_factors']], [[3], [3], [5]])
        self.assertTrue(all(row['attempt_selector'] == 'all_previously_created' for row in domain['feedback_factors']))
        self.assertGreaterEqual(self.packet['limits']['candidate']['max_work'], 10_000_000)

    def test_shared_policy_has_one_logical_owner_and_original_safety_obligation(self):
        shared = self.packet['shared']; rows = shared['request']['document']['program']['declarations']
        machines = [row for row in rows if row['$type'] == 'Machine']
        self.assertEqual(machines[0]['arbitration'], machines[1]['arbitration'])
        transitions = [row for row in rows if row['$type'] == 'Transition']
        self.assertEqual(machines[0]['arbitration']['order'], [row['id'] for row in transitions])
        launch = [row for row in transitions if row['source'] == 'ready']
        self.assertEqual([row['when']['args'][1]['op'] for row in launch], ['not', 'not'])
        self.assertEqual([row['when']['args'][1]['args'][0]['op'] for row in launch], ['any', 'any'])
        safety = next(row for row in rows if row['id'] == shared['expected']['safety_requirement'])
        self.assertEqual((safety['kind'], safety['condition']['op']), ('safety', 'not'))
        self.assertIn(safety['id'], shared['request']['document']['assurance']['requirements'])
        self.assertTrue(any(row['available_tick'] == 4 and row['observation'] == 'sense/condition_b' and row['value'] is True
            for row in shared['request']['operating_domain']['fixed_observations']))

    def test_components_all_pins_carriers_exact_rna_and_shared_static_reservation(self):
        request, expected = self.packet['request'], self.packet['expected']
        rule = request['composition_rule']
        self.assertEqual(peer.digest(rule['body']), rule['identity']['content_fingerprint'])
        control = request['component_library']['components'][0]['body']
        self.assertEqual([row['id'] for row in control['provider_requirements']], [
            'condition_a.input', 'condition_b.input',
            'condition_a.input_rows_per_tick.per_encounter_slot',
            'condition_b.input_rows_per_tick.per_encounter_slot',
            'evidence_a.evidence_records.per_encounter_slot', 'evidence_a.timer_cells.per_encounter_slot',
            'evidence_b.evidence_records.per_encounter_slot', 'evidence_b.timer_cells.per_encounter_slot',
            'permit.truth_cells.per_encounter_slot',
            'machine_a.machine_state_bits.per_encounter_slot', 'machine_a.machine_correlation_records.per_encounter_slot',
            'machine_b.machine_state_bits.per_encounter_slot', 'machine_b.machine_correlation_records.per_encounter_slot',
        ])
        for component in request['component_library']['components']:
            self.assertEqual(peer.digest(component['body']), component['identity']['content_fingerprint'])
            carriers = [row['target'] for row in component['body']['carriers']]
            boundaries = component['body']['fragment']['boundary_ports']
            endpoints = [(row['endpoint']['node'], row['endpoint']['port']) for row in boundaries]
            self.assertEqual(len(endpoints), len(set(endpoints)))
            for node in component['body']['fragment']['nodes']:
                self.assertEqual(peer.digest(node['model']['body']), node['model']['identity']['content_fingerprint'])
                for kind in ('primitive', 'configuration', 'replication'): self.assertIn({'kind': kind, 'id': node['id']}, carriers)
        layout = request['context']['record_layout']
        self.assertEqual(layout['union_digest'], peer.digest(expected['ordered_union']))
        self.assertEqual(layout['domain_digest'], peer.digest(request['implementation_request']['operating_domain']))
        capacities = []
        for provider in request['context']['providers']:
            self.assertEqual(peer.digest(provider['body']), provider['identity']['content_fingerprint'])
            for row in provider['body'].get('capacities', []):
                self.assertEqual(row['record_layout_digest'], peer.digest(layout))
                if row['unit'] == 'active_attempt_records': capacities.append(row)
        self.assertEqual(len(capacities), 1)
        self.assertEqual({row['pool_id'] for row in capacities}, {'network.shared_attempt_capacity'})
        self.assertEqual({row['quantity'] for row in capacities}, {24})
        all_capacities = [row for provider in request['context']['providers'] for row in provider['body'].get('capacities', [])]
        self.assertEqual(len(all_capacities), len({row['pool_id'] for row in all_capacities}))
        attempt_allocations = [row for row in request['resource_bindings'] if row['unit'] == 'active_attempt_records']
        self.assertEqual([row['owner'] for row in attempt_allocations], [
            {'kind': 'node', 'slot': 'actuator', 'node': 'response_a'},
            {'kind': 'node', 'slot': 'actuator', 'node': 'response_b'},
        ])
        self.assertEqual([row['capacity'] for row in attempt_allocations], [capacities[0]['id']] * 2)
        self.assertEqual(attempt_allocations[0]['provider'], attempt_allocations[1]['provider'])
        attempt_requirements = [row for component in request['component_library']['components']
            for row in component['body']['provider_requirements'] if row.get('unit') == 'active_attempt_records']
        self.assertEqual([row['minimum'] for row in attempt_requirements], [12, 12])
        self.assertEqual(sum(row['minimum'] for row in attempt_requirements), capacities[0]['quantity'])
        self.assertEqual((len(expected['ordered_union']['nodes']), expected['node_count']), (35, 35))
        self.assertEqual(expected['sequence'], 'CCAUGGCUUAAGGAAAA')
        self.assertEqual(expected['molecule']['sequence'], expected['sequence'])
        self.assertEqual(len(expected['ordered_union']['atomic_groups']), 2)
        product_links = [row for row in rule['body']['links'] if row['signal_type'] == 'product_symbol']
        self.assertEqual([(row['id'], row['producer'], row['consumer']) for row in product_links], [
            ('response_a.product', {'slot': 'actuator', 'boundary': 'response_a.product'},
                {'slot': 'control', 'boundary': 'response_a.product'}),
            ('response_b.product', {'slot': 'actuator', 'boundary': 'response_a.product'},
                {'slot': 'control', 'boundary': 'response_b.product'}),
        ])
        product_wires = [row for row in expected['ordered_union']['wires']
            if row['producer'] == {'slot': 'actuator', 'node': 'product', 'port': 'out'}]
        self.assertEqual([row['consumer'] for row in product_wires], [
            {'slot': 'control', 'node': 'commit0', 'port': 'product0'},
            {'slot': 'control', 'node': 'commit4', 'port': 'product0'},
        ])

    def test_legacy_finite_fixture_bytes_are_unchanged(self):
        self.assertEqual(hashlib.sha256(generator.finite.PATH.read_bytes()).hexdigest(),
            'bdd3d516b36dd69ecf70e91ab81e006abc89f33b11c5639a68d1e2f08c9383b6')


class NetworkTransportTests(unittest.TestCase):
    def setUp(self):
        self.packet = fixture(); self.request = self.packet['request']['implementation_request']; self.limits = self.packet['limits']

    def test_explicit_network_builders_snapshot_and_reject_mixed_profiles(self):
        args = {key: value for key, value in self.request.items() if key not in ('schema_version', 'profile', 'document')}
        document = p.from_data(self.request['document'], p.BuildRequest)
        prepared = public.prepare_request(document, **args, prerequisites=True, network=True)
        self.assertEqual(prepared, self.request)
        prepared['operating_domain'].clear(); self.assertTrue(self.request['operating_domain'])
        for flags in ({'network': True}, {'network': True, 'prerequisites': True, 'finite_machine': True},
                      {'network': True, 'prerequisites': True, 'two_observations': True}, {'network': True, 'prerequisites': True, 'multi_product': True}):
            with self.assertRaises(ValueError): public.prepare_request(document, **args, **flags)
        supplied = self.packet['request']; args = {key: value for key, value in supplied.items() if key not in ('schema_version', 'profile')}
        self.assertEqual(material_public.prepare_request(**args, instanced=True, prerequisites=True, network=True), supplied)
        for flags in ({'network': True}, {'network': True, 'instanced': True, 'prerequisites': True, 'finite_machine': True},
                      {'network': True, 'instanced': True, 'prerequisites': True, 'quantitative': {}},
                      {'network': True, 'instanced': True, 'prerequisites': True, 'two_observations': True}):
            with self.assertRaises(ValueError): material_public.prepare_request(**args, **flags)

    def test_exact_network_profiles_cannot_enter_legacy_decoders(self):
        for decoder in (implementation._original, implementation._finite_machine_original, implementation._two_observation_original):
            with self.assertRaises(CoreProtocolError): decoder(self.request)
        for key, value in (('schema_version', implementation.FINITE_MACHINE_REQUEST_SCHEMA), ('profile', implementation.FINITE_MACHINE_REQUEST_PROFILE)):
            changed = deepcopy(self.request); changed[key] = value
            with self.assertRaises(CoreProtocolError): implementation._request(changed)
        for key, value in (('schema_version', material.FINITE_MACHINE_REQUEST_SCHEMA), ('profile', material.FINITE_MACHINE_REQUEST_PROFILE)):
            changed = deepcopy(self.packet['request']); changed[key] = value
            with self.assertRaises(CoreProtocolError): material._original(changed)
        self.assertFalse(material._finite_machine(self.packet['request']))
        self.assertFalse(material._two_observations(self.packet['request']))
        self.assertTrue(material._network(self.packet['request']))

    def test_standalone_network_compile_check_replay_validate_complete_inert_evidence(self):
        for request in (self.request, self.packet['shared']['request']):
            transport = InertTransport(); client = implementation.PolicyImplementationClient(transport)
            with patch('biocompiler.policy.validation.check', side_effect=AssertionError('No Python fallback')):
                compiled = client.compile(request, self.limits)
                checked = client.check(request, compiled.candidate, self.limits)
                replayed = client.replay(request, compiled.candidate, self.limits, checked.result)
            self.assertEqual(compiled.result, replayed.result)
            self.assertEqual(checked.report['binding']['profile'], implementation.NETWORK_BINDING_PROFILE)
            self.assertEqual(checked.report['material'], 'unassessed')
            changed = checked.result; changed['implementation'] = implementation.FINITE_MACHINE_IMPLEMENTATION
            with self.assertRaises(CoreProtocolError): client.replay(request, compiled.candidate, self.limits, changed)

    def test_rehashed_network_anchor_inventory_alias_and_lane_mutations_reject(self):
        client = implementation.PolicyImplementationClient(InertTransport()); actual = inert_candidate(self.request)
        mutations = [lambda x: x['binding']['states'].clear(), lambda x: x['binding']['machines'].reverse(),
            lambda x: x['binding']['observations'][1].update(bank=x['binding']['observations'][0]['bank']),
            lambda x: x['binding']['effects'][0].update(feedback='wrong'),
            lambda x: x['binding']['transitions'][4].update(lane=4),
            lambda x: x['binding']['transitions'][4].update(arbiter=x['binding']['transitions'][0]['arbiter']),
            lambda x: x['binding']['transitions'][0].update(commit=x['binding']['transitions'][1]['commit']),
            lambda x: x['binding']['transitions'].reverse(), lambda x: x['implementation']['nodes'].pop(),
            lambda x: x['implementation']['nodes'].extend([{'id': f'extra{i}'} for i in range(65)])]
        for mutate in mutations:
            changed = deepcopy(actual); mutate(changed)
            with self.subTest(mutate=mutate), self.assertRaises(CoreProtocolError): client.check(self.request, changed, self.limits)
        request = self.packet['shared']['request']; changed = inert_candidate(request)
        changed['binding']['transitions'][4]['arbiter'] = 'separate'
        with self.assertRaises(CoreProtocolError): client.check(request, changed, self.limits)

    def test_network_negotiation_rejects_old_profile_before_dispatch(self):
        for component in (False, True):
            transport = InertTransport(component); transport.capabilities.profiles = {}
            client = material.PolicyComponentMaterialClient(transport) if component else implementation.PolicyImplementationClient(transport)
            with self.assertRaises(CoreProtocolError): client.compile(self.packet['request'] if component else self.request, self.limits)
            self.assertEqual(len(transport.calls), 1)
            transport.role = 'verify'; transport.calls.clear()
            with self.assertRaises(CoreProtocolError): client.compile(self.packet['request'] if component else self.request, self.limits)
            self.assertFalse(transport.calls)

    def test_component_four_operations_route_originals_under_explicit_network_capability(self):
        transport = InertTransport(True); client = material.PolicyComponentMaterialClient(transport); sentinel = object()
        for operation, invoke in (('compile', lambda: client.compile(self.packet['request'], self.limits)),
            ('check', lambda: client.check(self.packet['request'], {}, self.limits)),
            ('replay', lambda: client.replay(self.packet['request'], {}, self.limits, {})),
            ('export', lambda: client.export(self.packet['request'], {}, self.limits))):
            with patch.object(material, '_result', return_value=sentinel) as decode:
                self.assertIs(invoke(), sentinel)
            self.assertEqual(transport.calls[-1][0], operation + '-policy-component-material')
            self.assertEqual(transport.calls[-1][1]['request'], self.packet['request'])
            self.assertEqual(decode.call_count, 1)

    def test_network_report_checker_profile_and_machine_obligations_remain_closed(self):
        report = {key: None for key in material._REPORT_FIELDS | {'prerequisites', 'prerequisite_status'}}
        report.update(schema_version='biocompiler.policy_component_material_assessment.v0.2', profile=material.NETWORK_REQUEST_PROFILE,
            implementation='biocompiler.ocaml.policy_component_material_check.v0.9', resource_profile=material.RESOURCE_PROFILE,
            claim_scope=material.CLAIM_SCOPE, premise=material.PREMISE, empirical='unassessed', artifact='withheld', export='withheld')
        self.assertEqual(material._report(report, instanced=True, prerequisites=True, network=True), report)
        for key, value in (('implementation', 'biocompiler.ocaml.policy_component_material_check.v0.7'), ('profile', material.FINITE_MACHINE_REQUEST_PROFILE)):
            changed = deepcopy(report); changed[key] = value
            with self.assertRaises(CoreProtocolError): material._report(changed, instanced=True, prerequisites=True, network=True)
        with self.assertRaises(CoreProtocolError): material._report(report, instanced=True, prerequisites=True, network=True, finite_machine=True)
        binding = {'schema_version': implementation.NETWORK_BINDING_REPORT_SCHEMA, 'profile': implementation.NETWORK_BINDING_PROFILE,
            'source_admission': {'source_assessment': {'unresolved_obligations': ['machine_reachability_termination_and_progress']}}}
        preservation = {'status': 'checked_implementation', 'binding': binding}
        report = {'preservation': preservation, 'assembly_status': 'pass', 'context_status': 'pass', 'catalog': {},
            'prerequisites': {'status': 'pass'}, 'prerequisite_status': 'pass', 'all_original_obligations_discharged': True,
            'status': material.ACCEPTED_STATUS, 'obligations': [{'obligation': 'machine_reachability_termination_and_progress', 'status': 'discharged',
                'stage': 'bounded_machine_semantics_and_declared_requirements', 'evidence': {'preservation': peer.digest(preservation), 'machine_binding': peer.digest(binding),
                    'state_and_terminal_semantics': 'exact_bounded_source_correspondence', 'prefixes': 'complete_original_domain',
                    'retained_attempt_identity': 'creation_fixed_injective', 'universal_termination': 'not_claimed', 'progress': 'declared_requirements_only'}}]}
        material.material._obligations(report, material_key='assembly', prerequisite_key='prerequisites', accepted_status=material.ACCEPTED_STATUS, network=True)
        with self.assertRaises(CoreProtocolError): material.material._obligations(report, material_key='assembly', prerequisite_key='prerequisites', accepted_status=material.ACCEPTED_STATUS, finite_machine=True)
        report['obligations'][0]['evidence']['universal_termination'] = 'proved'
        with self.assertRaises(CoreProtocolError): material.material._obligations(report, material_key='assembly', prerequisite_key='prerequisites', accepted_status=material.ACCEPTED_STATUS, network=True)

    def test_shared_preservation_plumbing_passes_only_network_authority_flag(self):
        actual = inert_candidate(self.request); report = inert_result({'request': self.request, 'candidate': actual, 'limits': self.limits})['report']
        response = CoreResponse('mock-network', 'check-policy-component-material', 'ok', None, (), 'verify', CORE_VERSION)
        with patch.object(implementation, '_authority') as authority, patch.object(implementation, '_evidence'):
            material.material._preservation(response, self.packet['request'], actual, {'preservation': report}, self.limits, prerequisites=True, network=True)
        self.assertTrue(authority.call_args.kwargs['network'])
        self.assertFalse(authority.call_args.kwargs['finite_machine'])

    def test_refinement_uses_network_material_report_without_new_relation_vocabulary(self):
        request = self.packet['request']; candidate = {'wire': 'candidate'}; report = {'status': 'not_accepted'}
        payload = {'request': request, 'candidate': candidate, 'limits': self.limits}
        raw = {'schema_version': refinement.RESULT_SCHEMA, 'implementation': refinement.IMPLEMENTATION,
            'validation_scope': refinement.VALIDATION_SCOPE, 'request_fingerprint': peer.digest(request),
            'candidate_fingerprint': peer.digest(candidate), 'invocation_fingerprint': peer.digest(payload),
            'material_report_fingerprint': peer.digest(report), 'material_report': report, 'evidence': None}
        response = CoreResponse('mock-network-refinement', 'check-policy-refinement', 'ok', raw, (), 'verify', CORE_VERSION)
        with patch.object(material, '_candidate', return_value=candidate), patch.object(material, '_report', return_value=report) as decode, \
                patch.object(material, '_assessment'):
            result = refinement._result(response, payload)
        self.assertTrue(decode.call_args.kwargs['network'])
        self.assertFalse(decode.call_args.kwargs['finite_machine'])
        self.assertIsNone(result.evidence)
        self.assertEqual(result.material_report, report)

    def test_linked_material_delegates_unchanged_network_child_to_existing_validator(self):
        modules = self.packet['modules']; request = self.packet['request']; candidate = {'original': 'mock'}
        linkage = linking_peer.lineage(modules, self.packet['program'])
        child = {'network_child': 'retained'}
        raw = {'schema_version': linked.MATERIAL_SCHEMA, 'implementation': linked.MATERIAL_IMPLEMENTATION,
            'validation_scope': linked.MATERIAL_SCOPE, 'modules': modules, 'linkage': linkage, 'material': child, 'artifact': None,
            'invocation_fingerprint': peer.digest({'modules': modules, 'request': request, 'candidate': candidate, 'limits': self.limits})}
        response = CoreResponse('mock-linked-network', 'check-policy-module-material', 'ok', raw, (), 'verify', CORE_VERSION)
        # Only child routing is asserted here; the mock does not mint acceptance.
        sentinel = SimpleNamespace(candidate=candidate, artifact=None, request_fingerprint=peer.digest(request),
            candidate_fingerprint=peer.digest(candidate), report_fingerprint=peer.digest({}))
        with patch.object(material, '_result', return_value=sentinel) as decode:
            result = linked._material_result(response, {'modules': modules, 'request': request, 'candidate': candidate, 'limits': self.limits})
        self.assertEqual(decode.call_args.args[0].operation, 'check-policy-component-material')
        self.assertEqual(decode.call_args.args[0].result, child)
        self.assertEqual(decode.call_args.args[1]['request'], request)
        self.assertEqual(result.result['material'], child)


if __name__ == '__main__': unittest.main()
