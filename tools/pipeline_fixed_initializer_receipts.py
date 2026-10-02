"""Closed receipt proof for the source-ordered fixed registration hook.

This validates an already framed transcript. Only finite structural values and
the actual broker's ordinary mapping primitives are reconstructed. No compiler,
manager registration, producer, or validator is executed by this checker.
"""
from __future__ import annotations

import re

if __package__:
    from . import check_pipeline_manager_install as manager
else:
    import check_pipeline_manager_install as manager

require, equal = manager.require, manager.equal
ROLES = ('intent_to_behavior', 'behavior_to_synthetic', 'synthetic_to_components')
CHECKS = ('preservation', 'finite_history', 'composition')


def reference(value):
    require(type(value) is dict and set(value) == {'handle'} and type(value['handle']) is str
        and re.fullmatch(r'object/[0-9]+', value['handle']), 'Invalid fixed initializer host reference')
    return value['handle']


def returned(invocation):
    value = invocation['outcome']
    require(type(value) is dict and set(value) == {'status', 'value'} and value['status'] == 'return',
        'Fixed initializer primitive did not complete normally')
    return value['value']


class _Capability:
    def __call__(self, *_args, **_kwargs):
        raise AssertionError('Receipt checker cannot execute a native capability')


class PrimitiveReplay:
    """Physical host bijection for a closed, non-user-code registration graph."""
    def __init__(self):
        from biocompiler.pipeline_callback_objects import CallbackObjects
        self.objects = CallbackObjects()
        self.host, self.refs = {}, {}

    def bind(self, wire, value):
        name = reference(wire)
        if name in self.host:
            require(self.host[name] is value, 'Fixed registration rebound a host object')
        require(all(other == name or prior is not value for other, prior in self.host.items()),
            'Fixed registration split one physical object into multiple host handles')
        self.host[name] = value
        self.refs[name] = self.objects.retain(value)

    def inputs(self, value):
        if type(value) is dict:
            if set(value) == {'handle'}:
                name = reference(value)
                require(name in self.refs, 'Fixed registration primitive used an unpublished object')
                return self.refs[name]
            return {key: self.inputs(item) for key, item in value.items()}
        if type(value) is list:
            return [self.inputs(item) for item in value]
        return value

    def outputs(self, actual, expected):
        if type(actual) is dict and set(actual) == {'handle'}:
            self.bind(expected, self.objects.resolve(actual))
        elif type(actual) is dict:
            require(type(expected) is dict and set(expected) == set(actual), 'Fixed registration primitive result shape differs')
            for key in actual:
                self.outputs(actual[key], expected[key])
        elif type(actual) is list:
            require(type(expected) is list and len(actual) == len(expected), 'Fixed registration primitive result census differs')
            for left, right in zip(actual, expected):
                self.outputs(left, right)
        else:
            equal(actual, expected, 'Fixed registration primitive returned a different value')

    def execute(self, invocation):
        completion = self.objects.execute(invocation['action'], self.inputs(invocation['arguments']))
        require(completion.status == 'ok', 'Closed fixed registration replay raised unexpectedly')
        self.outputs(completion.value, returned(invocation))


def registration_primitives(invocations, command, producer, validators, tokens, replay, *, host_provider=None):
    """Exact first-registration source recipe, including both mapping traversals."""
    position = 0
    def take(action, arguments, result=...):
        nonlocal position
        require(position < len(invocations), 'Fixed registration primitive trace ended early')
        invocation = invocations[position]; position += 1
        require(invocation['action'] == action and invocation['command_sequence'] == command['sequence']
            and invocation['parent_invocation'] == command['parent_invocation'],
            'Fixed registration primitive action or owner differs')
        equal(invocation['arguments'], arguments, 'Fixed registration primitive arguments differ')
        value = returned(invocation)
        if action == 'provider-reference':
            name = reference(arguments['object'])
            require(name in tokens or host_provider is not None and name == host_provider[0],
                'Fixed registration supplied a foreign provider capability')
            wanted = {'kind': 'native', 'provider_id': tokens[name]} if name in tokens else {
                'kind': 'host', 'object': arguments['object']}
            equal(value, wanted, 'Fixed registration changed native provider identity')
        elif action == 'set-equal':
            equal(value, set(replay.host[reference(arguments['object'])]) == set(arguments['values']),
                'Fixed registration key set differs')
        elif action == 'ordered-json':
            from biocompiler.core_pipeline_manager import _ordered
            equal(value, _ordered(replay.host[reference(arguments['object'])]),
                'Fixed registration key ordered view differs')
        else:
            replay.execute(invocation)
        if result is not ...:
            equal(value, result, 'Fixed registration primitive result differs')
        return value
    registration_actions(take, producer, validators,
        names=[item['id'] for item in command['arguments']['contract']['checks']], host_provider=host_provider)
    require(position == len(invocations), 'Fixed registration contains an extra host action')

def registration_actions(take, producer, validators, *, names, host_provider=None):
    """One closed source-ordered registration observation recipe."""
    def each_values(callback):
        values = take('mapping-values', {'object': validators})
        cursor = take('iter', {'object': values})
        # Every fixed contract in this closed profile has exactly one checker.
        value = take('next', {'object': cursor})
        require(value['exhausted'] is False, 'Fixed registration lost its validator')
        callback(value['object'])
        take('next', {'object': cursor}, {'exhausted': True, 'object': None})
    take('callable', {'object': producer}, True)
    take('is-instance', {'object': validators, 'type': 'Mapping'}, True)
    each_values(lambda value: take('callable', {'object': value}, True))
    require(len(names) == 1, 'Fixed initialization contract changed checker cardinality')
    take('set-equal', {'object': validators, 'values': names}, True)
    each_values(lambda value: take('compare', {'left': value, 'right': producer, 'operator': 'is'}, False))
    take('provider-reference', {'object': producer})
    if host_provider is not None:
        require(reference(producer) == host_provider[0], 'Wrapped registration producer identity differs')
        take('bind-provider', {'provider_id': host_provider[1], 'object': producer}, None)
    copied = take('dict', {'object': validators})
    items = take('mapping-items', {'object': copied})
    cursor = take('iter', {'object': items})
    item = take('next', {'object': cursor})
    require(item['exhausted'] is False, 'Fixed registration dictionary omitted its validator')
    zero = take('literal', {'kind': 'json', 'value': 0})
    key = take('get-item', {'object': item['object'], 'key': zero})
    one = take('literal', {'kind': 'json', 'value': 1})
    value = take('get-item', {'object': item['object'], 'key': one})
    frozen = take('freeze-json', {'object': key})
    take('ordered-json', {'object': frozen}, ['scalar', names[0]])
    take('provider-reference', {'object': value})
    take('next', {'object': cursor}, {'exhausted': True, 'object': None})



def validate(details, initialization, *, contracts, views=None):
    """Return proven nested commands/proxies/host origins for the enclosing gate.

    ``contracts`` comes from a full original-checked native manager snapshot.
    Supplying ``views`` seeds that same offline structural decoder's retained
    native obligation objects before later historical records are decoded.
    """
    from biocompiler.core_pipeline_manager import _obligation, _unordered
    from biocompiler.ir.intent import thaw_json
    require(initialization['operation'] in ('initialize-synthetic', 'initialize-components')
        and initialization['parent_invocation'] is None, 'Invalid fixed initializer for registration proof')
    count = 2 if initialization['operation'] == 'initialize-synthetic' else 3
    roles = ROLES[:count]
    root = sorted(({**entry, 'invocation_id': identity} for identity, entry in details['invocations'].items()
        if entry['command_sequence'] == initialization['sequence']), key=lambda item: item['start_frame'])
    equal([entry['action'] for entry in root], ['manager-created']+
        ['native-provider', 'native-provider', 'register-fixed']*count,
        'Fixed initializer omitted, repeated, or reordered publication/registration callbacks')
    require(all(item['parent_invocation'] is None for item in root), 'Fixed initializer callback belongs to another invocation')
    target = {'value': initialization['arguments']['request']['build_request']['target'],
        'binding': {'kind': 'host', 'object': initialization['arguments']['target_object']}}
    equal(root[0]['arguments'], {'target': target}, 'Fixed publication changed authored target authority')
    equal(returned(root[0]), None, 'Fixed publication returned replacement manager authority')
    require(initialization['start_frame'] < root[0]['start_frame'], 'Manager publication preceded its initialization')
    replay = PrimitiveReplay()
    source_refs = [initialization['arguments'][name+'_object'] for name in ('request', 'target', 'config')]
    require(len({reference(ref) for ref in source_refs}) == 3, 'Fixed initializer authored objects physically aliased')
    for ref in source_refs:
        replay.bind(ref, object() if views is None else views.host[reference(ref)])
    minted, nested, host_documents, registrations, argument_evidence = {}, [], {}, [], {}
    obligation_tokens = set()
    last = root[0]['end_frame']
    for index, role in enumerate(roles):
        producer_call, validator_call, hook = root[1+index*3:4+index*3]
        require(last < producer_call['start_frame'] < producer_call['end_frame'] < validator_call['start_frame']
            < validator_call['end_frame'] < hook['start_frame'] < hook['end_frame'],
            'Fixed registration moved across publication or another registration')
        last = hook['end_frame']
        refs = []
        for invocation, suffix in ((producer_call, '.producer'), (validator_call, '.validator')):
            arguments = invocation['arguments']
            require(set(arguments) == {'provider_id', 'role'} and arguments['role'] == role+suffix
                and type(arguments['provider_id']) is str and re.fullmatch(r'provider/[0-9]+', arguments['provider_id'])
                and arguments['provider_id'] not in minted, 'Fixed initializer proxy role differs: provider role or physical handle has a wrong or repeated closure role')
            token, ref = arguments['provider_id'], returned(invocation)
            reference(ref)
            capability = _Capability()
            if views is not None:
                views.provider(token, role+suffix, ref)
                capability = views.host[reference(ref)]
            replay.bind(ref, capability)
            minted[token] = (ref, role+suffix, invocation['end_frame'])
            refs.append(ref)
        raw = hook['arguments']
        require(type(raw) is dict and set(raw) == {'contract', 'producer', 'validators', 'obligation_objects'},
            'Fixed registration action fields differ')
        require(role in contracts, 'Fixed registration contract is absent from its checked snapshot')
        equal(raw['contract'], contracts[role], 'Fixed registration contract differs from retained actual state')
        equal(raw['producer'], refs[0], 'Fixed registration changed its actual producer')
        equal(raw['validators'], [[CHECKS[index], refs[1]]], 'Fixed registration changed its validator identity or order')
        children = sorted((item for item in details['commands'] if item['parent_invocation'] == hook['invocation_id']),
            key=lambda item: item['start_frame'])
        require(len(children) == 1 and children[0]['operation'] == 'register',
            'Unmodified fixed registration must dispatch exactly one actual register command')
        command = children[0]
        require(hook['start_frame'] < command['start_frame'] < command['end_frame'] < hook['end_frame'],
            'Nested register escaped its exact current fixed callback')
        args = command['arguments']
        require(set(args) == {'contract', 'producer', 'validators', 'obligation_objects'}, 'Nested fixed register fields differ')
        equal(args['contract'], raw['contract'], 'Nested registration changed native contract authority')
        equal(args['producer'], refs[0], 'Nested registration changed physical producer identity')
        validators = {CHECKS[index]: replay.host[reference(refs[1])]}
        replay.bind(args['validators'], validators)
        argument_evidence[reference(args['validators'])] = {'kind': 'validators',
            'items': [[CHECKS[index], validator_call['arguments']['provider_id']]]}
        declared = raw['contract']['introduces']
        require(type(raw['obligation_objects']) is list and type(args['obligation_objects']) is list
            and len(raw['obligation_objects']) == len(args['obligation_objects']) == len(declared),
            'Fixed introduced obligation identity census differs')
        for offset, (binding, ref, document) in enumerate(zip(raw['obligation_objects'], args['obligation_objects'], declared)):
            require(type(binding) is dict and set(binding) == {'kind', 'identity', 'tree'} and binding['kind'] == 'native'
                and re.fullmatch(r'value/[0-9]+', binding['identity']), 'Invalid fixed native obligation binding')
            require(binding['identity'] not in obligation_tokens, 'Fixed introduced obligation native identity was reused')
            obligation_tokens.add(binding['identity'])
            equal(thaw_json(_unordered(binding['tree'])), document, 'Fixed obligation binding projection differs')
            value = _obligation(document) if views is None else views.value._binding(binding, flavor='obligation')
            replay.bind(ref, value)
            if views is not None:
                views.bind(ref, value)
            host_documents[reference(ref)] = (command['start_frame']-1, document)
            argument_evidence[reference(ref)] = {'kind': 'contract_obligation', 'pass_id': role,
                'index': offset, 'value': document}
        tokens = {reference(ref): token for token, (ref, _, _) in minted.items()}
        primitives = sorted((item for item in details['invocations'].values()
            if item['command_sequence'] == command['sequence']), key=lambda item: item['start_frame'])
        registration_primitives(primitives, command, args['producer'], args['validators'], tokens, replay)
        equal(command['outcome'], {'status': 'ok', 'value': None}, 'Fixed nested registration did not complete successfully')
        equal(returned(hook), None, 'Fixed callback leaked a registration return value')
        nested.append(command['sequence']); registrations.append(raw)
    require(last < initialization['end_frame'], 'Fixed initialization replied before its final registration completed')
    actual_nested = [item['sequence'] for item in sorted(details['commands'], key=lambda item: item['start_frame'])
        if initialization['start_frame'] < item['start_frame'] < initialization['end_frame']]
    equal(actual_nested, nested, 'Unclaimed or reordered command inside fixed initialization')
    if initialization['outcome']['status'] == 'ok':
        equal(initialization['outcome']['value']['target'], target, 'Final initialization changed published target')
    return {'commands': nested, 'minted': minted, 'host_documents': host_documents,
        'registrations': registrations, 'publication': root[0]['invocation_id'], 'arguments': argument_evidence}
