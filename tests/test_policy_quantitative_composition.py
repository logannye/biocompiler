"""Partitioned source/selected-circuit witnesses; no native acceptance is simulated."""
from copy import deepcopy
from dataclasses import replace
import json
import unittest

from biocompiler import policy as p
from biocompiler import core_policy_component_material as api, core_policy_implementation as implementation
from biocompiler.core_client import CoreProtocolError
from biocompiler.policy import component_material as public, quantitative_composition as coupled, quantitative as q, implementation as source_api
from tests import test_policy_quantitative_network as network, test_policy_quantitative_step as step
from tools import generate_policy_quantitative_composition_fixture as generator


def candidate(packet):
    value = step.candidate(packet)
    value['binding'].update(schema_version=implementation.COUPLED_BINDING_SCHEMA, profile=implementation.COUPLED_BINDING_PROFILE)
    value['binding']['states'] = [{'source': 'amount_' + name, 'register': 'owner_' + name + '.amount'} for name in ('a', 'b', 'c')]
    value['binding']['effects'][0]['bank'] = 'owner_a.response'
    return value


def boundary(fragment, identity, instance):
    endpoint = next(row['endpoint'] for row in fragment['boundary_ports'] if row['id'] == identity)
    return {'node': instance + '.' + endpoint['node'], 'port': endpoint['port']}


def leaf(request, actual, table):
    temporary = deepcopy(request); temporary['quantitative'] = request['quantitative']['network']
    value = network.leaf(temporary, actual, table)
    value.update(schema_version='biocompiler.policy_quantitative_assessment.v0.5',
        profile='biocompiler.policy_atomic_component_transfer_network.v0.1',
        implementation='biocompiler.ocaml.policy_quantitative_check.v0.5',
        claim_scope='exact_atomic_component_transfer_network_under_supplied_coordination_contract',
        request_fingerprint=generator.shared.digest(request), composition=deepcopy(request['quantitative']),
        ownership='partitioned_reservoir_storage_single_atomic_writer', synchronization='one_prestate_one_atomic_commit',
        transport_scope='selected_boolean_allocation_signals_under_supplied_component_contracts')
    value['bindings']['attempt_bank'] = 'owner_a.response'
    components = request['component_library']['components']; owners = []
    for selected in request['quantitative']['owners']:
        body = next(row['body'] for row in components if row['identity'] == selected['component'])
        contract = body['quantitative_contracts'][0]
        owners.append({key: selected[key] for key in ('instance', 'component', 'contract', 'compartment')} | {
            'source_state': selected['state'], 'register': selected['instance'] + '.amount',
            'next': boundary(body['fragment'], contract['next']['boundary'], selected['instance'])})
    control = components[0]['body']
    value['bindings'].update(owners=owners, transfers=[{'transfer': flow['transfer'],
        'endpoint': boundary(control['fragment'], flow['boundary'], 'control')}
        for flow in control['quantitative_contracts'][0]['flows']])
    return value


class CompositionQuantitativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads(generator.PATH.read_text())

    def setUp(self):
        self.request = deepcopy(self.packet['request']); self.candidate = candidate(self.packet)
        self.document = p.from_data(self.request['implementation_request']['document'], p.BuildRequest)
        self.machine = next(row for row in self.document.program.declarations if isinstance(row, p.Machine))
        self.observation = next(row for row in self.document.program.declarations if isinstance(row, p.Observation))
        self.effect = next(row for row in self.document.program.declarations if isinstance(row, p.Effect))
        self.stores = tuple(row for row in self.document.program.declarations if isinstance(row, p.StateStore))
        self.law = coupled.CoupledTransferNetwork(network.law(), tuple(coupled.ReservoirStateOwner(name, store)
            for name, store in zip(('a', 'b', 'c'), self.stores)))
        self.leaf = leaf(self.request, self.candidate, self.packet['expected']['table'])

    def validate(self, value):
        api._quantitative_evidence(self.request, self.candidate, {'quantitative': value, 'quantitative_status': value['outcome'],
            'status': api.ACCEPTED_STATUS if value['outcome'] == 'pass' else 'not_accepted'})

    def test_partitioned_source_and_selected_circuit_match_complete_independent_table(self):
        transitions = self.law.transitions(self.machine, self.observation, self.effect, prefix='network')
        original = tuple(replace(row, id='network/' + row.id) for row in self.document.program.declarations if isinstance(row, p.Transition))
        self.assertEqual(transitions, original)
        self.assertTrue(all(len(row.assignments) == 3 for row in original))
        union = self.packet['expected']['ordered_union']
        key = lambda endpoint: (endpoint['slot'], endpoint['node'], endpoint['port'])
        nodes = {(row['slot'], row['node']): row['model']['body'] for row in union['nodes']}
        inputs = {key(row['consumer']): key(row['producer']) for row in union['wires']}
        self.assertEqual(len(inputs), len(union['wires']))
        def endpoint(item):
            node, port = item['node'].split('.', 1); return node, port, item['port']
        for row in self.packet['expected']['table']:
            memo = {}; bits = dict(zip(('owner_a','owner_b','owner_c'), map(bool, row['before'])))
            truth = {'true': True, 'false': False, 'unknown': None}[row['input']]
            def evaluate(ep):
                if ep in memo: return memo[ep]
                slot, node, _ = ep; model = nodes[(slot,node)]; primitive = model['primitive']
                def incoming(port): return evaluate(inputs[(slot,node,port)])
                if primitive == 'truth_register': result = bits[slot]
                elif primitive == 'evidence_bank': result = truth
                elif primitive == 'truth_not':
                    child = incoming('in'); result = None if child is None else not child
                else:
                    self.assertIn(primitive, ('truth_all','truth_any'))
                    children = [incoming('in'+str(i)) for i in range(model['configuration']['arity'])]
                    result = (False if False in children else None if None in children else True) if primitive == 'truth_all' else (True if True in children else None if None in children else False)
                memo[ep] = result; return result
            flows = [evaluate(endpoint(flow['endpoint'])) for flow in self.leaf['bindings']['transfers']]
            if truth is None: self.assertNotIn(True, flows)
            else:
                self.assertEqual(list(map(int,flows)), [flow['quanta'] for flow in row['flows']])
                self.assertEqual([int(evaluate(endpoint(owner['next']))) for owner in self.leaf['bindings']['owners']], row['after'])

    def test_four_selected_roots_exact_construction_and_complete_pins(self):
        self.assertEqual(generator.build(), self.packet)
        self.assertEqual(p.check(self.document).status, 'complete')
        self.assertEqual(len(self.candidate['implementation']['nodes']), 49)
        components = self.request['component_library']['components']
        self.assertEqual(len(components), 4)
        self.assertEqual(''.join(row['body']['root']['molecule']['sequence'] for row in components), self.packet['expected']['sequence'])
        self.assertEqual([row['body']['quantitative_contracts'][0]['role'] for row in components], ['coordinator','owner','owner','owner'])
        for component in components:
            self.assertEqual(generator.shared.digest(component['body']), component['identity']['content_fingerprint'])
            self.assertEqual(len(component['body']['root']['molecule']['features']), 1)
        for item in [self.request['composition_rule'], *self.request['context']['providers']]:
            self.assertEqual(generator.shared.digest(item['body']), item['identity']['content_fingerprint'])
        self.assertEqual(generator.shared.digest(self.packet['expected']['ordered_union']), self.request['context']['record_layout']['union_digest'])
        self.assertGreater(self.packet['limits']['source']['max_ticks'], self.request['implementation_request']['operating_domain']['horizon_ticks'])
        self.assertEqual(len(self.packet['expected']['keep_trajectory']), 13)
        authority = self.request['composition_rule']['body']['material_authority']['template']
        self.assertEqual(len(authority['sources']), 4)
        self.assertEqual(len(authority['steps'][0]['operation']['inputs']), 4)
        for port in authority['steps'][0]['ports']:
            for field, identity in (('chemistry_transition', 'component'), ('feature_transition', 'feature_id')):
                dispositions = port[field]['dispositions']
                keys = [(row['source_id'], row[identity]) for row in dispositions]
                self.assertEqual(keys, sorted(set(keys)))
        for structure in authority['payload_structures']:
            identities = [row['feature_id'] for row in structure['regions']]
            self.assertEqual(identities, sorted(set(identities)))
        self.assertEqual(len(self.request['composition_rule']['body']['link_carriers']), 66)

    def test_monitor_allowance_retains_complete_old_incomplete_invocation(self):
        control = self.packet['expected']['insufficient_monitor']
        self.assertEqual(control['request_fingerprint'], generator.shared.digest(self.request))
        previous_limits = deepcopy(self.packet['limits'])
        self.assertEqual(previous_limits['monitor']['max_work'], 5_000_000)
        previous_limits['monitor']['max_work'] = 1_000_000
        self.assertEqual(control['limits'], previous_limits)
        self.assertEqual(control['limits'], generator.network.build()['limits'])
        self.assertEqual(control['status'], 'incomplete')
        self.assertEqual(control['transitions'], 0)
        self.assertEqual(control['diagnostic'], 'policy_requirement_monitor_work_limit')
        self.assertEqual(control['export_diagnostic'], 'policy_quantitative_assurance_export_not_accepted')
        self.assertLessEqual(self.packet['limits']['monitor']['max_work'], 10_000_000)

    def test_explicit_private_ownership_and_binary_shape_reject_aliasing(self):
        owners = self.law.owners
        for changed in (owners[::-1], owners[:2], (replace(owners[0], state=owners[1].state),)+owners[1:]):
            with self.assertRaises(ValueError): replace(self.law, owners=changed)
        for changes in ({'initial':False},{'capacity':3},{'lifetime':'persistent'},{'overflow':'evict_oldest'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(self.law, owners=(replace(owners[0],state=replace(owners[0].state,**changes)),)+owners[1:])
        expanded = replace(network.law(), reservoirs=(replace(network.law().reservoirs[0],capacity=p.quantity(2,p.COUNT)),)+network.law().reservoirs[1:])
        with self.assertRaises(ValueError): replace(self.law, network=expanded)

    def test_complete_owner_edge_and_original_contract_transport_rejects_forgery(self):
        self.validate(self.leaf)
        for path, replacement in ((('bindings','owners'),self.leaf['bindings']['owners'][:-1]),
                (('bindings','transfers'),self.leaf['bindings']['transfers'][::-1]),
                (('synchronization',),'distributed_eventual_commit'), (('composition','owners'),[]),
                (('bindings','owners',0,'register'),'owner_b.amount'),
                (('bindings','owners',0,'next'),self.leaf['bindings']['owners'][1]['next']),
                (('bindings','transfers',0,'endpoint'),self.leaf['bindings']['transfers'][1]['endpoint']),
                (('table',12,'flows',0,'quanta'),0), (('table',),self.leaf['table'][:-1])):
            value=deepcopy(self.leaf); target=value
            for part in path[:-1]: target=target[part]
            target[path[-1]]=replacement
            with self.subTest(path=path), self.assertRaises(CoreProtocolError): self.validate(value)

    def test_failure_withholds_table_bindings_and_conservation(self):
        value=deepcopy(self.leaf); value.update(outcome='fail',bindings=None,table=[],conservation=None,
            issues=['artificial selected owner mismatch'])
        self.validate(value)
        for key in ('bindings','table','conservation'):
            changed=deepcopy(value);changed[key]=self.leaf[key]
            with self.assertRaises(CoreProtocolError): self.validate(changed)

    def test_two_and_four_private_owner_shapes_keep_oldstate_transfer_semantics(self):
        for names in (('a','b'),('a','b','c','d')):
            law=replace(network.law(),reservoirs=tuple(q.ReservoirCompartment(name,p.quantity(1,p.COUNT),p.quantity(int(index==0),p.COUNT))
                for index,name in enumerate(names)),transfers=tuple(q.TransferEdge(left+right,left,right,p.quantity(1,p.COUNT),True)
                for left,right in zip(names,names[1:])),threshold_compartment=names[-1])
            stores=tuple(replace(self.stores[0],id='store_'+name,initial=index==0) for index,name in enumerate(names))
            spec=coupled.CoupledTransferNetwork(law,tuple(coupled.ReservoirStateOwner(name,store) for name,store in zip(names,stores)))
            machine=replace(self.machine,states=tuple('s'+str(i) for i in range(2**len(names))),initial='s'+str(2**(len(names)-1)))
            transitions=spec.transitions(machine,self.observation,self.effect,prefix='shape')
            first=next(row for row in transitions if row.source==machine.initial)
            self.assertEqual(first.destination,'s'+str(2**(len(names)-2)))
            self.assertTrue(all(len(row.assignments)==len(names) for row in transitions))
            self.assertEqual(tuple(row.state.id for row in first.assignments),tuple(store.id for store in stores))

    def test_installed_planning_vocabulary_exposes_bounded_private_owners(self):
        from biocompiler import core_policy_planning as planning
        from tests.test_policy_target_planning import catalog, digest
        rows={row['target']:row for row in catalog()['targets']}
        for name in ('coupled_implementation','coupled_quantitative_material'):
            descriptor=rows[name]
            self.assertEqual(digest(descriptor),planning.TARGET_FINGERPRINTS[name])
            self.assertEqual(descriptor['realization_schema'],implementation.COUPLED_REQUEST_SCHEMA)
            self.assertEqual(descriptor['limits']['implementation_nodes'],64)
            self.assertEqual(descriptor['source_shapes'][0]['counts']['truth_stores'],{'minimum':2,'maximum':4})
        self.assertIn('quantitative',rows['coupled_quantitative_material']['required_inputs'])
        self.assertIn('selected_boolean_allocation_signals',rows['coupled_quantitative_material']['features'])
        self.assertNotIn('partitioned_reservoir_storage',rows['transfer_network_material']['features'])

    def test_complete_planning_envelope_uses_declared_bound_without_trimming_originals(self):
        from biocompiler import core_policy_planning as planning
        from biocompiler.policy import planning as facade
        realization = self.request['implementation_request']
        raw = facade.prepare_request(self.document, target='coupled_quantitative_material',
            definitions=realization['definitions'], material_request=self.request)
        self.assertEqual(raw['document'], realization['document'])
        self.assertEqual(raw['realization_request'], realization)
        self.assertEqual(raw['material_request'], self.request)
        self.assertEqual(planning._original(raw), raw)
        # The complete duplicated authority exceeds the legacy material framing
        # bound. Planning already declares a larger, still bounded envelope.
        with self.assertRaises(CoreProtocolError):
            planning._measure({'request': raw}, max_bytes=planning.MAX_INPUT_BYTES, max_nodes=100_000)
        self.assertEqual(planning.MAX_INPUT_NODES, 250_000)
        planning._measure({'request': raw}, max_bytes=planning.MAX_INPUT_BYTES,
                          max_nodes=planning.MAX_INPUT_NODES)

    def test_standalone_coupled_source_route_is_explicit(self):
        raw=self.request['implementation_request']
        fields={key:value for key,value in raw.items() if key not in ('schema_version','profile','document')}
        prepared=source_api.prepare_request(document=self.document,**fields,prerequisites=True,finite_machine=True,multi_site=True,coupled=True)
        self.assertEqual(prepared,raw)
        self.assertEqual(implementation._request(prepared),raw)
        self.assertEqual(implementation._profile_settings(prepared)[0],'policy_coupled_implementation')
        with self.assertRaises(ValueError):source_api.prepare_request(document=self.document,**fields,coupled=True)

    def test_original_snapshot_and_profile_isolation(self):
        fields={key:value for key,value in self.request.items() if key not in ('schema_version','profile')}
        self.assertEqual(public.prepare_request(**fields,instanced=True,prerequisites=True,finite_machine=True,multi_site=True,composition=True),self.request)
        selected=self.request['quantitative'];pins=tuple((row['instance'],row['component'],row['contract']) for row in selected['owners'])
        self.assertEqual(self.law.bind(coordinator_instance='control',coordinator_component=selected['network']['selection']['component'],
            coordinator_contract='network',owners=pins,machine=self.machine,observation=self.observation,effect=self.effect),selected)
        with self.assertRaises(ValueError): self.law.bind(coordinator_instance='owner_a',coordinator_component=selected['network']['selection']['component'],
            coordinator_contract='network',owners=pins,machine=self.machine,observation=self.observation,effect=self.effect)
        wrong=deepcopy(self.request);wrong.update(schema_version=api.TRANSFER_NETWORK_REQUEST_SCHEMA,profile=api.TRANSFER_NETWORK_REQUEST_PROFILE)
        with self.assertRaises(CoreProtocolError):api._original(wrong)


if __name__ == '__main__': unittest.main()
