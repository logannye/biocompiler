"""Test-only fully framed source-order hooks; never installed acceptance."""
from tools.pipeline_fixed_initializer_receipts import ROLES, CHECKS


def records(hooks, envelopes):
    """Mirror the source-confirmed native registered-sidecar origin edge."""
    introduced = {value['id']: handle for handle, value in hooks['host_documents'].items()}
    for envelope in envelopes:
        for index, value in enumerate(envelope['value']['obligations']):
            if value['id'] in introduced:
                envelope['bindings']['obligation_objects'][index] = {
                    'kind': 'host', 'object': {'handle': introduced[value['id']]}}


def emit(script, sequence, target, contracts, capabilities, *, count):
    from biocompiler.core_pipeline_manager import _ordered
    from biocompiler.pipeline_callback_objects import CallbackObjects
    broker = CallbackObjects()
    wire, local, serial = {}, {}, 1000000
    def bind(ref, value):
        local[ref['handle']] = broker.retain(value)
        wire[local[ref['handle']]['handle']] = ref
    def inputs(value):
        if type(value) is dict:
            if set(value) == {'handle'}:
                return local[value['handle']]
            return {key: inputs(item) for key, item in value.items()}
        if type(value) is list:
            return [inputs(item) for item in value]
        return value
    def outputs(value):
        nonlocal serial
        if type(value) is dict:
            if set(value) == {'handle'}:
                if value['handle'] not in wire:
                    ref = {'handle': 'object/'+str(serial)}; serial += 1
                    wire[value['handle']] = ref; local[ref['handle']] = value
                return wire[value['handle']]
            return {key: outputs(item) for key, item in value.items()}
        if type(value) is list:
            return [outputs(item) for item in value]
        return value
    def primitive(command, action, arguments):
        if action == 'provider-reference':
            token = next(token for token, _, ref in capabilities if ref == arguments['object'])
            result = {'kind': 'native', 'provider_id': token}
        elif action == 'set-equal':
            result = set(broker.resolve(inputs(arguments['object']))) == set(arguments['values'])
        elif action == 'ordered-json':
            result = _ordered(broker.resolve(inputs(arguments['object'])))
        else:
            completion = broker.execute(action, inputs(arguments))
            assert completion.status == 'ok', (action, completion.value)
            result = outputs(completion.value)
        script.invoke(command, action, arguments, result)
        return result
    script.invoke(sequence, 'manager-created', {'target': target}, None)
    result = {'commands': [], 'minted': [], 'host_documents': {}, 'arguments': {}}
    for index, role in enumerate(ROLES[:count]):
        pairs = [next(item for item in capabilities if item[1] == role+suffix) for suffix in ('.producer', '.validator')]
        for token, fullrole, ref in pairs:
            def capability(*_args):
                raise AssertionError('Fabricated capability is never executed')
            bind(ref, capability)
            script.invoke(sequence, 'native-provider', {'provider_id': token, 'role': fullrole}, ref)
            result['minted'].append(token)
        producer, validator = [item[2] for item in pairs]
        contract = contracts[role]
        obligations = [{'kind': 'native', 'identity': 'value/'+str(900000+index*100+j),
            'tree': _ordered({key: value[key] for key in ('id', 'scope', 'evidence_kind', 'description')})}
            for j, value in enumerate(contract['introduces'])]
        hook = script.begin(sequence, 'register-fixed', {'contract': contract, 'producer': producer,
            'validators': [[CHECKS[index], validator]], 'obligation_objects': obligations})
        mapping = {CHECKS[index]: broker.resolve(inputs(validator))}
        validators = outputs(broker.retain(mapping))
        from biocompiler.core_pipeline_manager import _obligation
        obligation_refs = [outputs(broker.retain(_obligation(value))) for value in contract['introduces']]
        command = script.command('register', {'contract': contract, 'producer': producer,
            'validators': validators, 'obligation_objects': obligation_refs})
        result['commands'].append(command)
        result['host_documents'].update({ref['handle']: value for ref, value in zip(obligation_refs, contract['introduces'])})
        result['arguments'][validators['handle']] = {'kind': 'validators', 'items': [[CHECKS[index], pairs[1][0]]]}
        result['arguments'].update({ref['handle']: {'kind': 'contract_obligation', 'pass_id': role, 'index': j, 'value': value}
            for j, (ref, value) in enumerate(zip(obligation_refs, contract['introduces']))})
        def action(name, args):
            return primitive(command, name, args)
        def each(callback):
            values = action('mapping-values', {'object': validators})
            iterator = action('iter', {'object': values})
            item = action('next', {'object': iterator})
            assert item['exhausted'] is False
            callback(item['object'])
            assert action('next', {'object': iterator}) == {'exhausted': True, 'object': None}
        action('callable', {'object': producer})
        action('is-instance', {'object': validators, 'type': 'Mapping'})
        each(lambda item: action('callable', {'object': item}))
        action('set-equal', {'object': validators, 'values': [CHECKS[index]]})
        each(lambda item: action('compare', {'left': item, 'right': producer, 'operator': 'is'}))
        action('provider-reference', {'object': producer})
        copied = action('dict', {'object': validators})
        items = action('mapping-items', {'object': copied})
        iterator = action('iter', {'object': items})
        item = action('next', {'object': iterator})['object']
        zero = action('literal', {'kind': 'json', 'value': 0})
        key = action('get-item', {'object': item, 'key': zero})
        one = action('literal', {'kind': 'json', 'value': 1})
        value = action('get-item', {'object': item, 'key': one})
        frozen = action('freeze-json', {'object': key})
        action('ordered-json', {'object': frozen})
        action('provider-reference', {'object': value})
        action('next', {'object': iterator})
        script.reply(command, None)
        script.end(hook, None)
    return result
