"""Fabricated protocol peer for original metadata-failure receipt controls.

These frames are test data, never installed native acceptance evidence. Their
objects come from fresh unchanged original executions, including the actual
upstream build and component producer closure origins.
"""
from copy import deepcopy
import json

from biocompiler.core_pipeline_manager import _ordered
from biocompiler.core_pipeline_provider_views import origin_reference
from biocompiler.compiler.pipeline import SourceLink
from tests.pipeline_fixed_initializer_fixture import emit, records as initializer_records
from tests.test_core_pipeline_build_views import BuildEnvelopeFixture
from tests.test_pipeline_fixed_provider_campaign import Script
from tools import check_pipeline_fixed_registration_install as gate


def framed_fixture(receipt, corpus, expected, retained, original, oracle):
    helper = BuildEnvelopeFixture({'authority_objects': {'request': retained['request'], 'config': None},
        'requested_config': retained['requested_config'], 'synthetic': retained['upstream']})
    broker, script = helper.callbacks, Script(receipt)
    source, config = retained['request'], retained['requested_config']
    refs = {name: broker.retain(value) for name, value in
        (('request', source), ('target', source.target), ('config', config))}
    wrapper = retained['wrapper']
    captured = dict(zip(wrapper.__code__.co_freevars, (cell.cell_contents for cell in wrapper.__closure__)))
    providers, roles = {}, {}
    for index, (pass_id, slot) in enumerate(gate.fixed.SLOTS):
        entry = retained['manager']._passes[pass_id]
        value = (captured['source_producer'] if pass_id == 'synthetic_to_components' else entry[1]) \
            if slot == 'producer' else entry[2][slot]
        token = 'provider/'+str(index)
        providers[pass_id, slot] = token, broker.retain(value)
        roles[token] = pass_id+('.producer' if slot == 'producer' else '.validator')
    wrapper_token, wrapper_ref = 'provider/6', broker.retain(wrapper)
    native = {ref['handle']: token for token, ref in providers.values()}
    values = []
    def binding(value, document, flavor='json'):
        index = next((i for i, (old, kind) in enumerate(values) if old is value and kind == flavor), None)
        if index is None:
            index = len(values); values.append((value, flavor))
        return {'kind': 'native', 'identity': 'view/'+str(index), 'tree': _ordered(document)}
    envelopes = {}
    for index, (key, record) in enumerate(retained['manager']._records.items()):
        raw = record.to_dict()
        envelopes[key] = {'value': raw, 'bindings': {'record_id': 'record/'+str(index),
            **{name: binding(getattr(record, name), raw[name]) for name in
                ('payload', 'dependencies', 'requirements', 'checks', 'provenance')},
            'obligations': binding(record.obligations, raw['obligations'], 'obligations'),
            'obligation_objects': [binding(value, item, 'obligation') for value, item in
                zip(record.obligations, raw['obligations'])]}}
    evidence = {'events': [], 'inspections': [], 'providers':
        {**{token: ref['handle'] for token, ref in providers.values()}, wrapper_token: wrapper_ref['handle']},
        'record_identities': {value['bindings']['record_id']: key for key, value in envelopes.items()},
        'outer_error': deepcopy(gate.ERROR)}
    published, last_inspection = set(), None
    def inspect(raw):
        nonlocal last_inspection
        sequence = script.command('inspect-ordered-references', {})
        evidence['inspections'].append(sequence)
        state = gate.fixed.snapshot(raw)
        tokens = set()
        for group in ('passes', 'provider_history'):
            for entry in state[group].values():
                key = entry['contract']['id']
                token = wrapper_token if key == 'synthetic_to_components' else providers[key, 'producer'][0]
                entry['producer'] = token; tokens.add(token)
                for slot in entry['validators']:
                    token = providers[key, slot][0]; entry['validators'][slot] = token; tokens.add(token)
        definitions = []
        for key in gate.continuation.original_order(raw)['records']:
            gate.equal(state['records'][key], envelopes[key]['value'], 'Fabricated historical record differs from original')
            token = envelopes[key]['bindings']['record_id']
            if token not in published:
                definitions.append(envelopes[key]); published.add(token)
            state['records'][key] = {'record_id': token}
        script.reply(sequence, {'snapshot': state, 'order': gate.continuation.original_order(raw),
            'providers': [{'provider_id': token, 'object': {'handle': evidence['providers'][token]}}
                for token in sorted(tokens)], 'record_definitions': definitions})
        last_inspection = sequence, len(script.rows)
        return sequence
    authority = corpus.fixed.document('fixed', expected['authority'])
    sequence = script.command('initialize-synthetic', {**authority, 'config': config.to_dict(),
        'request_tree': _ordered(source.to_dict()), 'manager_limits': None,
        **{name+'_object': ref for name, ref in refs.items()}})
    target = {'value': source.target.to_dict(), 'binding': {'kind': 'host', 'object': refs['target']}}
    initial_state = corpus.fixed.document('fixed', expected['manager_state'])
    hooks = emit(script, sequence, target,
        {key: entry['contract'] for key, entry in gate.fixed.snapshot(initial_state)['passes'].items()},
        [(token, roles[token], ref) for token, ref in providers.values()], count=2)
    initializer_records(hooks, envelopes.values())
    script.reply(sequence, {'kind': 'synthetic', 'manager': True,
        'artifacts': ['candidate', 'pipeline_result', 'selection_result'], 'target': target})
    upstream = helper.envelope('synthetic')
    result = retained['upstream'].result
    upstream['result'] = {'value': gate.continuation.ordinary_value(result), 'artifact': envelopes[result.artifact.id]}
    upstream['sources']['candidate'] = envelopes['mechanism']
    roots = gate.continuation.source_roots(oracle, source, config)
    specs = [(name, []) for name in ('BOOLEAN', 'LEVEL', 'DURATION', 'defaultLifecycle', 'syntheticCapabilities')]
    for collection, name, items in (('domain', 'inputs', source.domain.inputs), ('contract', 'requirements', source.contract.requirements)):
        for index in range(len(items)):
            path = [collection, name, index, 'observable']
            specs.extend([('request', path), ('request', path+['dtype'])])
    for index, node in enumerate(source.behavior.nodes):
        if node.source is not None: specs.append(('request', ['behavior', 'nodes', index, 'source']))
    origin_handles = set(ref['handle'] for ref in refs.values())
    def origins(sequence):
        for root, path in specs:
            value = origin_reference(source, root, path)
            handles = [name for name, old in broker._objects.items() if old is value]
            if handles and handles[0] not in origin_handles:
                script.invoke(sequence, 'origin-reference', {'root': root, 'path': path}, {'handle': handles[0]})
                origin_handles.add(handles[0])
    sequence = script.command('build-result', {'kind': 'synthetic'}); evidence['upstream_sequence'] = sequence
    origins(sequence); script.reply(sequence, upstream)
    evidence['initial'] = inspect(initial_state)
    events = corpus.fixed.continuations[expected['id']]['events']
    prep = {'preparation_id': 'preparation/0'}
    sequence = script.command('prepare-components', {}); evidence['prepare_sequence'] = sequence
    script.reply(sequence, {**prep, 'dependencies': [[gate.fixed.unpack(corpus.fixed.document('continuation', event['arguments']))['bound'][key]
        for key in ('key', 'identity')] for event in events[:8]]})
    contract = retained['manager']._passes['synthetic_to_components'][0]
    source_role, source_proposal = helper.provider('components', retained['source'])
    assert source_role == 'synthetic_to_components.producer'
    def step(command, action, arguments, wanted=...):
        if action == 'provider-reference':
            handle = arguments['object']['handle']
            value = {'kind': 'native', 'provider_id': native[handle]} if handle in native else {
                'kind': 'host', 'object': arguments['object']}
        elif action == 'ordered-json': value = _ordered(broker.resolve(arguments['object']))
        elif action == 'set-equal': value = set(broker.resolve(arguments['object'])) == set(arguments['values'])
        elif action == 'source-link-set-equal':
            value = set(broker.resolve(ref) for ref in arguments['objects']) == set(SourceLink(**item) for item in arguments['expected'])
        else:
            completion = broker.execute(action, arguments)
            assert completion.status == 'ok', (action, completion.value)
            value = completion.value
        if wanted is not ...: assert value == wanted, (action, value, wanted)
        script.invoke(command, action, arguments, value)
        return value
    for index, event in enumerate(events):
        wanted = gate.fixed.unpack(corpus.fixed.document('continuation', event['arguments']))['bound']
        if index == 8:
            sequence = script.command('component-profile', prep); evidence['profile_sequence'] = sequence
            script.reply(sequence, wanted['profile'])
        if index == 9:
            sequence = script.command('component-registration', prep); evidence['registration_sequence'] = sequence
            for token, reference in (providers['synthetic_to_components', 'producer'], providers['synthetic_to_components', 'composition']):
                script.invoke(sequence, 'native-provider', {'provider_id': token, 'role': roles[token]}, reference)
            script.reply(sequence, {'contract': wanted['contract'],
                'producer': providers['synthetic_to_components', 'producer'][1],
                'validators': [['composition', providers['synthetic_to_components', 'composition'][1]]],
                'obligation_objects': [binding(item, item.to_dict(), 'obligation') for item in contract.introduces]})
        reused = last_inspection is not None and last_inspection[1] == len(script.rows)
        before = last_inspection[0] if reused else inspect(corpus.fixed.document('continuation', event['state_before']))
        row = {key: event[key] for key in ('api', 'context', 'outcome', 'error') if key in event}
        row.update(before=before, before_reused=reused, start_frame=len(script.rows))
        operation = event['api'].split('.')[-1].replace('_', '-')
        arguments = deepcopy(wanted)
        if operation == 'register':
            validators = broker.retain({'composition': broker.resolve(providers['synthetic_to_components', 'composition'][1])})
            arguments = {'contract': wanted['contract'], 'producer': wrapper_ref, 'validators': validators,
                'obligation_objects': [broker.retain(item) for item in contract.introduces]}
        sequence = script.command(operation, arguments); row['sequence'] = sequence
        if operation == 'register':
            gate.providers.initializers.registration_actions(lambda action, args, result=...: step(sequence, action, args, result),
                wrapper_ref, validators, names=['composition'], host_provider=(wrapper_ref['handle'], wrapper_token))
        if operation == 'run':
            context = retained['context_object']
            raw = {'input': envelopes['mechanism']['value']['payload'], 'output': None, 'target': source.target.to_dict(),
                'configuration': {}, 'dependencies': dict(context.dependencies), 'requirements': list(context.requirements),
                'source_links': [], 'observation_map': {}}
            context_ref = broker.retain(context)
            script.invoke(sequence, 'hydrate-context', {'context_id': 'context/0', 'document': raw, 'bindings': {
                'input': envelopes['mechanism']['bindings']['payload'], 'output': None,
                'target': target['binding'], 'configuration': binding(context.configuration, {}),
                'dependencies': binding(context.dependencies, raw['dependencies']),
                'requirements': envelopes['mechanism']['bindings']['requirements'], 'source_links': None,
                'observation_map': binding(context.observation_map, {}, 'default-observation')}}, context_ref)
            callback = script.begin(sequence, 'call-provider', {'provider_id': wrapper_token, 'context': context_ref})
            token, reference = providers['synthetic_to_components', 'producer']
            producer_sequence = script.command('call-native-provider', {'provider_id': token, 'context_id': 'context/0'})
            evidence['producer_sequence'] = producer_sequence
            origins(producer_sequence); script.reply(producer_sequence, source_proposal)
            # The actual callback receives structurally hydrated wire values,
            # not the original constructor's interned scalar objects. Preserve
            # the real transport boundary before executing the unchanged body.
            hydrated = helper.providers.decode(json.loads(gate.canonical(source_proposal)),
                role=source_role, target=source.target, target_document=source.target.to_dict(),
                requested_config=config, input_payload=context.input)
            changed = gate.mutation_recipe(gate.load_body_module(), expected['context'])(hydrated, context)
            changed_ref = broker.retain(changed); script.end(callback, changed_ref)
            gate.proposal_actions(lambda action, args: step(sequence, action, args), changed_ref,
                changed=changed, context=context, contract=contract, source_links=hydrated.source_links)
            evidence['wrapper'] = {'object': wrapper_ref['handle'], 'context': context_ref['handle'],
                'source_proposal': None, 'mutated_proposal': changed_ref['handle'], 'source_provider': reference['handle'],
                'wrapper_qualname': wrapper.__qualname__, 'mutation_qualname': captured['mutation'].__qualname__, 'context_same': True}
            script.server('reply', {'sequence': sequence, 'request_sha256': gate.sha(script.bodies[sequence]),
                'outcome': {'status': 'rejected', 'value': {**gate.ERROR, 'attributes': {}, 'attributes_tree': ['object', []]}}, 'closed': False})
        else:
            row['value'] = None; script.reply(sequence, None)
        row['end_frame'] = len(script.rows)
        row['after'] = inspect(corpus.fixed.document('continuation', event['state_after']))
        evidence['events'].append(row)
    evidence['sources'] = {name: [key for key, root in roots.items() if root is value]
        for name, value in broker._objects.items() if any(root is value for root in roots.values())}
    evidence['completed'] = evidence['events'][-1]['after']
    script.close()
    return script.rows, deepcopy(original['graph']), evidence
