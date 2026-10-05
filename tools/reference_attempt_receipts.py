"""Attempt lifecycle proof over already validated complete callback frames.

This is an additional receipt linkage check, not a native acceptance oracle.
Original public operations and complete object graphs remain independently bound.
"""
from __future__ import annotations

if __package__:
    from . import check_pipeline_manager_install as manager
else:
    import check_pipeline_manager_install as manager

require, equal = manager.require, manager.equal
PREPARE = ('prepare-reference-molecular', 'prepare-reference-molecular-public')
ROLES = ('construct_to_molecular.producer', 'construct_to_molecular.sequence',
         'construct_to_molecular.composition')
LEAVE = 'leave-reference-molecular-attempt'


def reference(value):
    require(type(value) is dict and set(value) == {'handle'} and type(value['handle']) is str,
            'Molecular attempt requires an actual opaque host reference')
    return value['handle']


def validate(details):
    """Validate each real process independently; never normalize its raw frames."""
    all_lifecycle = []
    all_attempts = []
    for process, detail in enumerate(details):
        commands = {row['sequence']: row for row in detail['commands']}
        events = []
        for row in commands.values():
            events.extend(((row['start_frame'], 'command', row), (row['end_frame'], 'reply', row)))
        for identity, invocation in detail['invocations'].items():
            row = {**invocation, 'invocation_id': identity}
            events.extend(((row['start_frame'], 'invoke', row), (row['end_frame'], 'continue', row)))
        attempts, providers, handles, outputs, builds = {}, {}, {}, {}, {}
        scope, captured, pending, lifecycle = [], {}, {}, []
        roots = set()
        latest_build = {'construct': None, 'molecular': None}
        for _, phase, row in sorted(events, key=lambda value: value[0]):
            if phase in ('command', 'reply'):
                op, args, sequence = row['operation'], row['arguments'], row['sequence']
                if phase == 'command':
                    captured[sequence] = scope[-1] if scope else None
                    if op in ('initialize-reference', 'prepare-reference-molecular-public'):
                        for key in ('target_object', 'request_object', 'registry_object',
                                    'construct_manifests_object', 'molecular_manifests_object'):
                            if key in args and args[key] is not None: roots.add(reference(args[key]))
                        for value in args.get('policy_objects', {}).values(): roots.add(reference(value))
                    if op in ('reference-molecular-profile', 'reference-molecular-registration',
                              'finish-reference-molecular', LEAVE):
                        require(scope and args['preparation_id'] == scope[-1],
                                'Molecular command changed its active attempt capability')
                    continue
                outcome = row['outcome']
                if op in PREPARE and outcome['status'] == 'ok':
                    value = outcome['value']; token = value['preparation_id']
                    require(type(token) is str and token not in attempts,
                            'Molecular preparation capability was reused')
                    dependencies = value['dependencies']
                    require(type(dependencies) is list and len(dependencies) == 6 and all(
                        type(pair) is list and len(pair) == 2 and all(type(item) is str for item in pair)
                        for pair in dependencies) and len({pair[0] for pair in dependencies}) == 6,
                        'Molecular preparation omitted its six ordered dependencies')
                    require(captured[sequence] == (scope[-1] if scope else None),
                            'Molecular preparation changed its parent execution scope')
                    attempts[token] = {'process': process, 'preparation': token, 'prepare_sequence': sequence,
                        'parent': captured[sequence], 'dependencies': dependencies, 'writes': [],
                        'providers': [], 'leave_sequence': None, 'builds': []}
                    scope.append(token)
                elif op == LEAVE:
                    require(outcome == {'status': 'ok', 'value': None},
                            'Molecular leave did not complete as an exact lifecycle operation')
                    require(scope and scope[-1] == captured[sequence] == args['preparation_id'],
                            'Molecular leave changed or replayed its original scope')
                    token = scope.pop()
                    require(attempts[token]['leave_sequence'] is None, 'Molecular attempt left twice')
                    attempts[token]['leave_sequence'] = sequence
                    lifecycle.append({'process': process, 'sequence': sequence, 'operation': op,
                        'preparation': token, 'start_frame': row['start_frame'], 'end_frame': row['end_frame'],
                        'classification': 'nonsemantic_native_attempt_scope_cleanup'})
                else:
                    token = captured[sequence]
                    if op == 'set-dependency' and token is not None and outcome['status'] == 'ok':
                        attempt = attempts[token]
                        pair = [args['key'], args['identity']]
                        count = len(attempt['writes'])
                        if count < 6:
                            equal(pair, attempt['dependencies'][count], 'Molecular attempt dependency write order or identity changed')
                            attempt['writes'].append(sequence)
                    if op == 'reference-molecular-profile':
                        require(token is not None and len(attempts[token]['writes']) == 6,
                                'Molecular profile preceded its six original dependency writes')
                    if op == 'reference-molecular-registration' and outcome['status'] == 'ok':
                        require(token is not None, 'Molecular registration has no active attempt')
                        value = outcome['value']; identities = attempts[token]['providers']
                        require(len(identities) == 3 and all(identity in providers for identity in identities),
                                'Molecular registration omitted actual provider publication')
                        equal(value['producer'], {'handle': providers[identities[0]][2]},
                              'Molecular registration substituted its producer capability')
                        equal(value['validators'], [[name, {'handle': providers[identity][2]}] for name, identity in
                            zip(('sequence_identity', 'encoding_composition'), identities[1:])],
                            'Molecular registration substituted its validator capabilities')
                    if op.startswith('finish-reference-') and outcome['status'] == 'ok':
                        value = outcome['value']; kind = op.removeprefix('finish-reference-')
                        require(value['kind'] == kind and value['build_id'] not in builds,
                                'Molecular historical Build identity was rebound')
                        if kind == 'molecular':
                            require(token is not None and token == args['preparation_id'],
                                    'Molecular completed Build changed its original attempt')
                            attempts[token]['builds'].append(value['build_id'])
                        builds[value['build_id']] = value
                        latest_build[kind] = value['build_id']
                    if op == 'reference-build-result' and outcome['status'] == 'ok':
                        expected = latest_build[args['kind']]
                        require(expected is not None and outcome['value']['build_id'] == expected,
                                'Kind-only reference Build did not select the last completed capability')
                        equal(outcome['value'], builds[expected], 'Historical reference Build content was rebound')
                continue
            action, args = row['action'], row['arguments']
            command = commands[row['command_sequence']]
            if phase == 'invoke':
                if action == 'reference-molecular-provider':
                    token = args['preparation_id']; identity = args['provider_id']
                    require(token in attempts and identity not in providers and args['role'] in ROLES,
                            'Molecular provider identity or attempt was rebound')
                    require(command['operation'] == 'reference-molecular-registration'
                        and command['arguments']['preparation_id'] == token
                        and captured[command['sequence']] == token,
                        'Molecular provider publication belongs to another registration attempt')
                    attempt = attempts[token]
                    require(len(attempt['providers']) < 3 and args['role'] == ROLES[len(attempt['providers'])],
                            'Molecular provider publication order or role differs')
                    attempt['providers'].append(identity)
                    pending[row['invocation_id']] = (token, identity, args['role'])
                elif action == 'reference-emit':
                    token, identity = args['preparation_id'], args['provider_id']
                    require(identity in providers and providers[identity][:2] == (token, ROLES[0]),
                            'Molecular emitter changed its captured provider attempt origin')
                    if command['operation'] == 'call-native-provider':
                        require(command['arguments']['provider_id'] == identity,
                                'Molecular emission belongs to another direct provider command')
                    else:
                        require(command['operation'] == 'run' and command['arguments']['pass_id'] == 'construct_to_molecular',
                                'Molecular emission has no actual native run or direct provider owner')
                elif action in ('reference-proposal', 'reference-molecular-proposal'):
                    token = args.get('preparation_id'); key = row['command_sequence'], reference(args['output'])
                    require(key in outputs and outputs.pop(key) == token,
                            'Reference paired proposal changed its output attempt, source action or command')
                continue
            outcome = row['outcome']
            if action == 'reference-molecular-provider':
                require(outcome['status'] == 'return', 'Molecular provider publication failed')
                token, identity, role = pending.pop(row['invocation_id'])
                handle = reference(outcome['value'])
                require(handle not in handles and handle not in roots,
                        'Molecular provider handle aliases another provider or source authority')
                handles[handle] = identity; providers[identity] = (token, role, handle)
            elif action == 'native-provider' and outcome['status'] == 'return':
                handle = reference(outcome['value'])
                require(handle not in handles and handle not in roots, 'Provider handle aliases another source capability')
                handles[handle] = args['provider_id']
            elif action in ('reference-generate', 'reference-emit') and outcome['status'] == 'return':
                value = outcome['value']
                require(value['kind'] in ('native','host'), 'Unknown Molecular source route')
                if value['kind'] == 'host':
                    output = reference(value['output'])
                    key = row['command_sequence'], output
                    require(key not in outputs, 'Opaque reference output was rebound within its command')
                    outputs[key] = args.get('preparation_id')
        require(not pending and not scope, 'Completed reference process omitted an attempt leave command')
        for attempt in attempts.values():
            require(attempt['leave_sequence'] is not None, 'Molecular attempt omitted complete cleanup evidence')
        all_lifecycle.extend(lifecycle); all_attempts.extend(attempts.values())
    return {'attempts': all_attempts, 'lifecycle_commands': all_lifecycle,
        'scope': 'additional complete transport lifecycle evidence; original439operation correspondence remains unchanged'}
