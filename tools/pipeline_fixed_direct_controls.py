"""Six additive actual-proxy controls for complete fixed build identity graphs.

These controls supplement the unchanged original workflow cohort. They do not
replace any original command, assertion, case, or installed release gate.
"""
from __future__ import annotations

from copy import deepcopy

if __package__:
    from . import check_pipeline_fixed_provider_install as providers
else:
    import check_pipeline_fixed_provider_install as providers

manager = providers.manager
r, canonical, sha, equal, require = manager.r, manager.canonical, manager.sha, manager.equal, manager.require
ROLES = ('intent_to_behavior', 'behavior_to_synthetic', 'synthetic_to_components')
NAMES = ('lower', 'generate', 'components')
OUTPUTS = ('direct_behavior', 'direct_mechanism', 'direct_components')
VERSION_SUFFIX = '.fixed_build_direct'


def continuation():
    if __package__:
        from . import check_pipeline_fixed_continuation_install as module
    else:
        import check_pipeline_fixed_continuation_install as module
    return module


class Witness(providers.Witness):
    def __init__(self):
        super().__init__()
        self.wrappers = {}

    def evidence(self, oracle):
        value = super().evidence(oracle.providers)
        for pass_id, wrapper in self.wrappers.items():
            handles = [handle for handle, actual in self.manager._objects._objects.items() if actual is wrapper]
            require(len(handles) == 1, 'Direct wrapper lacks its exact retained host identity')
            require(handles[0] not in value['objects'], 'Direct wrapper aliases a source capability')
            value['objects'][handles[0]] = {'kind': 'wrapper', 'pass_id': pass_id}
        return value


def run(core, corpus, oracle, receipt, originals):
    from biocompiler.core_pipeline_manager import CorePassManager
    from biocompiler.core_pipeline_provider_views import allocate
    from biocompiler.compiler.pipeline import PassContract
    require(len(originals) == len(corpus.build['cases']) == 6, 'Direct control source-authority census differs')
    receipt['direct_checks'] = []
    for expected, original in zip(corpus.build['cases'], originals):
        authority = original['authority_objects']
        request, history, until, config = (authority[key] for key in ('request', 'history', 'until', 'config'))
        row, seen, witness = {'id': expected['id']}, set(), Witness()
        receipt['direct_checks'].append(row)
        actual = None
        try:
            with manager.guarded_execution(seen):
                actual = CorePassManager.from_components(core, request, history, until=until, config=config)
                upstream = actual.build_result('synthetic')
                upstream_sequence = actual.session.last_response.sequence
                completed = actual.build_result('components')
                component_sequence = actual.session.last_response.sequence
            witness.manager, witness.request, witness.config = actual, request, actual._provider_config
            inspected = witness.registrations(manager.GuardedManager(actual, seen))
            records = dict(witness.records)
            require(tuple(records) == ('request', 'behavior', 'mechanism', 'components'), 'Direct initial record census differs')
            source_id = 'request'
            proposals = []
            for pass_id, name, output_id in zip(ROLES, NAMES, OUTPUTS):
                contract, producer, validators = inspected[pass_id]
                contract = allocate(PassContract, {**vars(contract), 'version': contract.version + VERSION_SUFFIX})
                def wrapper(context, producer=producer, pass_id=pass_id):
                    witness.observe('before', actual, pass_id, 0, context, None)
                    proposal = producer(context)
                    witness.observe('after', actual, pass_id, 0, context, proposal)
                    proposals.append((name_by_role[pass_id], proposal))
                    return proposal
                witness.wrappers[pass_id] = wrapper
                configuration = dict(records['mechanism'].provenance['configuration']) if pass_id == ROLES[1] else None
                with manager.guarded_execution(seen):
                    actual.register(contract, wrapper, validators)
                    actual.run(pass_id, source_id, output_id, configuration=configuration)
                source_id = output_id
            selected = proposals[1][1].output.generator_config
            observed = {'authority_objects': authority, 'requested_config': actual._provider_config,
                'selected_config': selected, 'producer_returns': proposals, 'synthetic': upstream,
                'component': completed, 'synthetic_records': tuple((key, records[key]) for key in ('request', 'behavior', 'mechanism')),
                'component_records': tuple(records.items())}
            graph = oracle.observe_case(expected['id'], observed, manager_type=CorePassManager)
            graph['original_cases'] = expected['original_cases']
            equal(graph, expected, 'Actual direct-proxy full object graph differs from original')
            row['actual'] = manager.artifact(receipt, canonical(graph))
            row['evidence'] = manager.artifact(receipt, canonical({**witness.evidence(oracle),
                'build_sequences': [upstream_sequence, component_sequence]}))
        finally:
            if actual is not None:
                continuation().close_receipt(actual, row, seen, receipt)
    providers.installed_modules()


name_by_role = dict(zip(ROLES, NAMES))


def _check_build(raw, frame, bindings):
    require(type(raw) is dict and set(raw) == {'kind', 'identity', 'result', 'artifacts', 'sources', 'view'},
        'Incomplete direct build envelope')
    require(type(raw['sources']) is dict and set(raw['sources']) == {'candidate'}, 'Direct build source census differs')
    bindings.record(raw['sources']['candidate'], frame)
    result = raw['result']
    require(type(result) is dict and set(result) == {'value', 'artifact'}, 'Incomplete direct build result')
    bindings.record(result['artifact'], frame)
    equal(result['value']['artifact'], result['artifact']['value'], 'Direct build result lost its actual record')


def validate_case(expected, actual, evidence, details, oracle, original, application):
    """Reconstruct the full observed graph from independently checked replies."""
    from biocompiler.core_pipeline_manager import CorePassManager, _ordered, _unordered
    from biocompiler.core_pipeline_provider_views import StructuralViews, origin_reference
    equal(actual, expected, 'Complete actual direct graph differs from original')
    require(type(evidence) is dict and set(evidence) == {'inspection', 'calls', 'objects', 'providers', 'arguments', 'build_sequences'},
        'Incomplete direct control evidence')
    commands = sorted(details['commands'], key=lambda item: item['start_frame'])
    init = commands[0]
    initializer_commands = {item['sequence'] for item in commands if init['start_frame'] < item['start_frame'] < init['end_frame']}
    commands = [item for item in commands if item['sequence'] not in initializer_commands]
    expected_operations = ['initialize-components', 'build-result', 'build-result', 'inspect-ordered']
    for _ in ROLES:
        expected_operations.extend(('register', 'run', 'call-native-provider'))
    equal([item['operation'] for item in commands], expected_operations, 'Direct control command census or order differs')
    require(len({item['sequence'] for item in commands}) == len(commands), 'Direct commands reused a sequence')
    by_sequence = {item['sequence']: item for item in commands}
    init, synthetic_reply, component_reply, inspection = commands[:4]
    for command in (init, synthetic_reply, component_reply, inspection):
        require(command['parent_invocation'] is None, 'Direct setup command has an enclosing callback')
    equal(evidence['build_sequences'], [synthetic_reply['sequence'], component_reply['sequence']], 'Direct builds detached from their actual commands')
    equal(synthetic_reply['arguments'], {'kind': 'synthetic'}, 'Direct synthetic build request differs')
    equal(component_reply['arguments'], {'kind': 'components'}, 'Direct component build request differs')
    require(evidence['inspection'] == inspection['sequence'] and inspection['arguments'] == {}, 'Direct inspection lost its actual receipt')
    source = original['authority_objects']
    request, config_argument = source['request'], source['config']
    config = config_argument if config_argument is not None else StructuralViews().config(application['default_generator_config'])
    args = init['arguments']
    equal({key: args[key] for key in ('request', 'history', 'until')},
        {key: expected['authority'][key] for key in ('request', 'history', 'until')}, 'Direct initialization changed original source authority')
    equal(args['config'], config.to_dict(), 'Direct initialization changed requested/default config')
    equal(args['request_tree'], _ordered(request.to_dict()), 'Direct initialization changed source field order')
    require(args['manager_limits'] is None, 'Direct control changed manager resource limits')
    views = continuation().ReceiptViews(request, config, application)
    roots = {'target': request.target, 'config': config, 'request': request,
        **dict(oracle.providers.source_origins(request)),
        'constant:synthetic_capabilities': origin_reference(request, 'syntheticCapabilities', [])}
    wrappers, source_handles, seen_names = {}, set(), set()
    for handle, entry in evidence['objects'].items():
        providers.reference({'handle': handle})
        if entry.get('kind') == 'source':
            require(set(entry) == {'kind', 'names'} and type(entry['names']) is list and entry['names']
                and len(entry['names']) == len(set(entry['names'])) and all(name in roots for name in entry['names'])
                and not seen_names.intersection(entry['names']), 'Direct source origin census differs')
            value = roots[entry['names'][0]]
            require(all(roots[name] is value for name in entry['names']), 'Direct source identities were merged by equal value')
            views.bind({'handle': handle}, value)
            source_handles.add(handle); seen_names.update(entry['names'])
        else:
            require(set(entry) == {'kind', 'pass_id'} and entry['kind'] == 'wrapper' and entry['pass_id'] in ROLES
                and entry['pass_id'] not in wrappers, 'Unknown direct wrapper capability')
            wrappers[entry['pass_id']] = handle
    require(set(wrappers) == set(ROLES), 'Direct wrapper census differs')
    for name in ('target', 'config', 'request'):
        require(views.host.get(providers.reference(args[name+'_object'])) is roots[name], 'Direct initializer lost actual '+name)
    initial = providers.succeeded(init)
    equal(initial, {'kind': 'components', 'manager': True,
        'artifacts': ['candidate', 'pipeline_result', 'selection_result', 'assembly', 'link_result', 'behavior_result'],
        'target': {'value': request.target.to_dict(), 'binding': {'kind': 'host', 'object': args['target_object']}}},
        'Direct initialization did not produce its actual complete native state')
    views.value._initialization(initial, 'components')
    hooks = providers.initializers.validate(details, init,
        contracts={key: value['contract'] for key, value in providers.succeeded(inspection)['snapshot']['passes'].items()}, views=views)
    equal(sorted(initializer_commands), sorted(hooks['commands']), 'Direct initializer nested-command census differs')
    for handle, value in hooks['arguments'].items():
        equal(evidence['arguments'].get(handle), value, 'Direct initializer argument observation differs')
    source_documents = {providers.reference(args['target_object']): (-1, request.target.to_dict()),
        providers.reference(args['config_object']): (-1, config.to_dict())}
    source_documents.update(hooks['host_documents'])
    bindings = providers.BindingCensus(details, source_documents)
    bindings.initialization(hooks)
    invocations = details['invocations']
    anchored = {providers.reference(args[name+'_object']) for name in ('target', 'config', 'request')}
    origin_positions = {handle: -1 for handle in anchored}
    minted = {}
    for invocation in sorted(invocations.values(), key=lambda item: item['start_frame']):
        action, arguments = invocation['action'], invocation['arguments']
        if action == 'origin-reference':
            require(set(arguments) == {'root', 'path'} and by_sequence[invocation['command_sequence']]['operation']
                in ('build-result', 'call-native-provider'), 'Direct origin action left its build/provider command')
            value = origin_reference(request, arguments['root'], arguments['path'])
            handle = providers.reference(providers.returned(invocation))
            require(views.host.get(handle) is value, 'Direct origin action lost its exact authoring/global object')
            anchored.add(handle)
            origin_positions.setdefault(handle, invocation['end_frame'])
        elif action == 'native-provider':
            require(invocation['command_sequence'] == init['sequence'], 'Direct native proxy minted outside actual initialization')
            token, role = arguments['provider_id'], arguments['role']
            require(token not in minted and role in {name+suffix for name in ROLES for suffix in ('.producer', '.validator')},
                'Unknown or repeated direct native provider')
            reference = providers.returned(invocation)
            equal(hooks['minted'][token][:2], (reference, role), 'Direct initialization lost its actual native proxy')
            minted[token] = (reference, role)
    require(anchored == source_handles, 'Direct source witness has no owning native origin request')
    require(len(minted) == 6, 'Direct six native proxy census differs')
    def preceding_origins(value, frame):
        if type(value) is dict:
            if value.get('kind') == 'host':
                handle = providers.reference(value['object'])
                require(handle in origin_positions and origin_positions[handle] < frame,
                    'Typed direct view used a source capability before its actual native origin return')
            for item in value.values(): preceding_origins(item, frame)
        elif type(value) is list:
            for item in value: preceding_origins(item, frame)
    synthetic_raw, component_raw = providers.succeeded(synthetic_reply), providers.succeeded(component_reply)
    for raw, command in ((synthetic_raw, synthetic_reply), (component_raw, component_reply)):
        preceding_origins(raw['view'], command['end_frame'])
    _check_build(synthetic_raw, synthetic_reply['end_frame'], bindings)
    _check_build(component_raw, component_reply['end_frame'], bindings)
    upstream = views.value._build_value(synthetic_raw, kind='synthetic', result=views.value._result_value)
    completed = views.value._build_value(component_raw, kind='components', result=views.value._result_value)
    raw_inspection = providers.succeeded(inspection)
    provider_evidence = evidence['providers']
    require(set(provider_evidence) == set(minted), 'Direct provider evidence omitted a native closure')
    for token, entry in provider_evidence.items():
        require(set(entry) == {'object', 'pass_id', 'slot'} and entry['pass_id'] in ROLES,
            'Malformed direct provider role observation')
        role = entry['pass_id'] + ('.producer' if entry['slot'] == 'producer' else '.validator')
        equal(minted[token], ({'handle': entry['object']}, role), 'Direct provider role or physical handle differs')
        registered = raw_inspection['snapshot']['passes'][entry['pass_id']]
        require(token == (registered['producer'] if entry['slot'] == 'producer' else registered['validators'].get(entry['slot'])),
            'Direct provider evidence differs from its actual registered slot')
    bound = {token: reference for token, (reference, _) in minted.items()}
    manager.comparison_snapshot(raw_inspection, {token: token for token in minted}, bound=bound)
    for envelope in raw_inspection['snapshot']['records'].values():
        bindings.record(envelope, inspection['end_frame'])
    inspected = views.value._inspection_state(views.value._ordered_inspection(raw_inspection))
    records = dict(inspected['_records'])
    require(tuple(records) == ('request', 'behavior', 'mechanism', 'components') and tuple(inspected['_passes']) == ROLES,
        'Direct initial records or passes differ')
    for pass_id in ROLES:
        equal(inspected['_passes'][pass_id][0].to_dict(), original['component'].manager._passes[pass_id][0].to_dict(),
            'Direct retained contract differs from source-owned fixed declaration')
    equal(dict(inspected['_dependencies']), dict(original['component'].manager._dependencies), 'Direct initial dependency state differs')
    source_manager = original['component'].manager
    for field in ('dependencies', 'passes', 'component_inputs', 'records', 'profiles', 'provider_history'):
        equal(raw_inspection['order'][field], list(getattr(source_manager, '_'+field)), 'Direct initial manager order differs: '+field)
    equal(raw_inspection['order']['component_input_history'], [], 'Direct manager invented admission history')
    equal(raw_inspection['order']['combined_provider_history'], list(source_manager._provider_history), 'Direct provider-history chronology differs')
    for field in ('passes', 'provider_history'):
        equal(raw_inspection['order']['validators'][field], {key: list(value[2]) for key, value in getattr(source_manager, '_'+field).items()},
            'Direct initial validator order differs')
    require(type(evidence['calls']) is list and len(evidence['calls']) == 3, 'Direct producer call observation census differs')
    proposals, used_arguments, used_callbacks = [], set(hooks['arguments']), set()
    inputs = ('request', OUTPUTS[0], OUTPUTS[1])
    for index, (pass_id, name, output_id, input_id) in enumerate(zip(ROLES, NAMES, OUTPUTS, inputs)):
        register, run_command, direct = commands[4+3*index:7+3*index]
        contract, producer, validators = inspected['_passes'][pass_id]
        original_contract = contract.to_dict()
        wanted_contract = {**original_contract, 'version': original_contract['version'] + VERSION_SUFFIX}
        require(register['parent_invocation'] is None and run_command['parent_invocation'] is None
            and register['end_frame'] < run_command['start_frame'], 'Direct registration/run order differs')
        equal(register['arguments']['contract'], wanted_contract, 'Direct wrapper changed more than its version')
        equal(providers.succeeded(register), None, 'Direct wrapper registration failed')
        require(providers.reference(register['arguments']['producer']) == wrappers[pass_id], 'Direct register changed wrapper capability')
        token = raw_inspection['snapshot']['passes'][pass_id]['producer']
        validator_ids = raw_inspection['snapshot']['passes'][pass_id]['validators']
        pairs = [[key, validator_ids[key]] for key in raw_inspection['order']['validators']['passes'][pass_id]]
        validator_ref = providers.reference(register['arguments']['validators']); used_arguments.add(validator_ref)
        equal(evidence['arguments'][validator_ref], {'kind': 'validators', 'items': pairs}, 'Direct validator identity/order differs')
        refs = register['arguments']['obligation_objects']
        require(len(refs) == len(contract.introduces), 'Direct introduced obligation census differs')
        for offset, (reference, item) in enumerate(zip(refs, contract.introduces)):
            handle = providers.reference(reference); used_arguments.add(handle)
            document = item.to_dict()
            equal(evidence['arguments'][handle], {'kind': 'contract_obligation', 'pass_id': pass_id,
                'index': offset, 'value': document}, 'Direct introduced object differs from actual inspected slot')
            views.bind(reference, item); bindings.host[handle] = [(register['start_frame']-1, document)]
        bindings.registration(wanted_contract, refs, register['end_frame'])
        observed_validators = set()
        for invocation in invocations.values():
            if invocation['command_sequence'] == register['sequence'] and invocation['action'] == 'provider-reference':
                handle = providers.reference(invocation['arguments']['object'])
                for validator_token, (reference, _) in minted.items():
                    if providers.reference(reference) == handle:
                        equal(providers.returned(invocation), {'kind': 'native', 'provider_id': validator_token},
                            'Direct registration replaced an actual native validator')
                        observed_validators.add(validator_token)
        require(observed_validators == {value for _, value in pairs}, 'Direct validator reuse census differs')
        for key, value in (('pass_id', pass_id), ('input_id', input_id), ('output_id', output_id)):
            equal(run_command['arguments'][key], value, 'Direct run changed its chained source argument')
        configured = dict(records['mechanism'].provenance['configuration']) if index == 1 else None
        if configured is None:
            require(run_command['arguments']['configuration'] is None, 'Direct run changed absent configuration')
        else:
            handle = providers.reference(run_command['arguments']['configuration']); used_arguments.add(handle)
            equal(evidence['arguments'][handle], {'kind': 'configuration', 'value': oracle.providers.plain(configured)},
                'Direct configuration differs from actual native selected configuration snapshot')
        callbacks = [(identifier, item) for identifier, item in invocations.items()
            if item['command_sequence'] == run_command['sequence'] and item['action'] == 'call-provider']
        require(len(callbacks) == 1, 'Direct run invoked its wrapper another number of times')
        invocation_id, callback = callbacks[0]; used_callbacks.add(invocation_id)
        bound_wrapper = [item for item in invocations.values() if item['command_sequence'] == register['sequence']
            and item['action'] == 'bind-provider' and item['arguments'] == {'provider_id': callback['arguments']['provider_id'],
                'object': {'handle': wrappers[pass_id]}}]
        require(len(bound_wrapper) == 1 and providers.returned(bound_wrapper[0]) is None, 'Direct callback detached from its registered wrapper')
        contexts = [item for item in invocations.values() if item['command_sequence'] == run_command['sequence']
            and item['action'] == 'hydrate-context' and providers.returned(item) == callback['arguments']['context']]
        require(len(contexts) == 1 and contexts[0]['end_frame'] < callback['start_frame'], 'Direct callback lacks its actual preceding context')
        context = contexts[0]
        bindings.context(context)
        document = context['arguments']['document']
        equal(document['input'], records[input_id].to_dict()['payload'], 'Direct callback input differs from actual chained record')
        equal(document['configuration'], configured or {}, 'Direct callback configuration differs from actual run')
        equal(document['dependencies'], dict(inspected['_dependencies']), 'Direct callback dependency snapshot differs')
        equal(document['requirements'], list(records[input_id].requirements), 'Direct callback lost source requirement identity')
        equal(document['target'], request.target.to_dict(), 'Direct callback changed actual target context')
        equal(context['arguments']['bindings']['target'], {'kind': 'host', 'object': args['target_object']},
            'Direct callback changed actual target capability')
        equal(context['arguments']['bindings']['input'], (raw_inspection['snapshot']['records'][input_id]
            if index == 0 else providers.succeeded(commands[4+3*(index-1)+1]))['bindings']['payload'],
            'Direct context changed actual source payload capability')
        # Bind only exact already-checked ordered JSON observations, preserving
        # repeated handles. This reconstructs transport values, not semantics.
        for item in sorted(invocations.values(), key=lambda x: x['end_frame']):
            if item['action'] == 'ordered-json' and item['end_frame'] < callback['start_frame']:
                reference = item['arguments']['object']; handle = providers.reference(reference)
                if handle not in views.host:
                    views.bind(reference, _unordered(providers.returned(item)))
        live_input = views.value._binding(context['arguments']['bindings']['input'])
        require(live_input is records[input_id].payload, 'Direct decoded context lost its actual source payload object')
        link = evidence['calls'][index]
        require(set(link) == {'pass_id', 'ordinal', 'before_frames', 'after_frames', 'sequence', 'returned_object'}
            and link['pass_id'] == pass_id and type(link['ordinal']) is int and link['ordinal'] == 0
            and link['sequence'] == direct['sequence'] and link['before_frames'] == direct['start_frame']
            and link['after_frames'] == direct['end_frame']+1, 'Direct call observation detached from exact reply interval')
        equal(direct['arguments'], {'provider_id': token, 'context_id': context['arguments']['context_id']},
            'Direct call changed its actual fixed provider or live context')
        require(direct['parent_invocation'] == invocation_id and callback['start_frame'] < direct['start_frame']
            < direct['end_frame'] < callback['end_frame'], 'Direct call escaped its actual owning wrapper')
        equal(providers.returned(callback), {'handle': link['returned_object']}, 'Direct wrapper returned another proposal object')
        native_result = providers.succeeded(direct)
        preceding_origins(native_result['view'], direct['end_frame'])
        require(native_result['kind'] == 'proposal', 'Direct fixed producer did not return a proposal')
        proposal = views.value._native_return(native_result, role=pass_id+'.producer', input_payload=live_input)
        proposals.append((name, proposal))
        accepted = providers.succeeded(run_command)
        bindings.record(accepted, run_command['end_frame'])
        equal(accepted['value']['payload'], native_result['value']['output'], 'Accepted direct record differs from actual returned proposal')
        # These fixed closures repeat the same original decisions and payloads.
        # The source-pinned PassManager.run record construction changes only
        # version/identity and the current dependency/configuration snapshots.
        # Compare every field; this is observation of the closed rerun recipe,
        # not execution of Python acceptance or import of an accepted record.
        original_record = records[('behavior', 'mechanism', 'components')[index]].to_dict()
        wanted_record = deepcopy(original_record)
        wanted_record.update(id=output_id, parent=input_id, pass_identity=sha(canonical(wanted_contract)),
            dependencies=dict(inspected['_dependencies']))
        for check in wanted_record['checks'].values():
            check['dependencies'] = dict(inspected['_dependencies'])
        wanted_record['provenance'].update(contract=wanted_contract, configuration=configured or {},
            source_links=native_result['value']['source_links'], observation_map=native_result['value']['observation_map'])
        equal(accepted['value'], wanted_record, 'Complete accepted direct record differs from its original fixed rerun recipe')
        # Freeze-json host values used by the returned record are retained only
        # after their actual ordered-json continuation, before publication.
        for item in sorted(invocations.values(), key=lambda x: x['end_frame']):
            if item['action'] == 'ordered-json' and item['end_frame'] < run_command['end_frame']:
                reference = item['arguments']['object']; handle = providers.reference(reference)
                if handle not in views.host:
                    views.bind(reference, _unordered(providers.returned(item)))
        records[output_id] = views.value._record(accepted)
    require(set(evidence['arguments']) == used_arguments, 'Unclaimed direct authoring argument evidence')
    require(used_callbacks == {identity for identity, item in invocations.items() if item['action'] == 'call-provider'},
        'Extra direct wrapper callback')
    require(len(bindings.contexts) == 3 and len(bindings.context_objects) == 3, 'Direct live context census differs')
    require(not set(bindings.native).intersection(views.value._provider_views.native), 'Typed and ordinary direct view namespaces collided')
    observed = {'authority_objects': source, 'requested_config': config, 'selected_config': proposals[1][1].output.generator_config,
        'producer_returns': proposals, 'synthetic': upstream, 'component': completed,
        'synthetic_records': tuple((key, records[key]) for key in ('request', 'behavior', 'mechanism')),
        'component_records': tuple((key, records[key]) for key in ('request', 'behavior', 'mechanism', 'components'))}
    projected = oracle.observe_case(expected['id'], observed, manager_type=CorePassManager)
    projected['original_cases'] = expected['original_cases']
    equal(projected, actual, 'Native direct replies do not reconstruct the complete observed object graph')
    return {'id': expected['id'], 'complete_case_sha256': sha(canonical(projected)), 'returns': 3}


def validate(receipt, corpus, oracle, artifacts, sessions, pids, *, originals=None):
    if originals is None:
        originals = []
        equal(oracle.capture(retain=originals), corpus.build, 'Fresh source-owned direct authority changed')
    require(type(receipt.get('direct_checks')) is list and len(receipt['direct_checks']) == len(originals) == 6,
        'Incomplete six direct fixed-provider controls')
    channel, application = manager.declarations()
    projected = []
    for expected, original, row in zip(corpus.build['cases'], originals, receipt['direct_checks']):
        require(type(row) is dict and set(row) == {'id', 'actual', 'evidence', 'pid', 'returncode', 'closed', 'invalidated',
            'executable_sha256', 'stderr', 'frames', 'after_close', 'guard'} and row['id'] == expected['id'],
            'Direct control row census or order differs')
        require(type(row['pid']) is int and row['pid'] > 0 and row['pid'] not in pids
            and type(row['returncode']) is int and row['returncode'] == 0 and row['closed'] is True
            and row['invalidated'] is False and row['executable_sha256'] == receipt['native_inputs']['sha256']['biocompiler-core'],
            'Direct native process authority or lifecycle differs')
        pids.add(row['pid'])
        equal(artifacts.json(row['stderr']), {'hex': ''}, 'Direct process wrote stderr')
        equal(artifacts.json(row['after_close']), {'type': 'CoreProtocolError',
            'message': 'Callback session is closed; it cannot reconnect', 'traffic_unchanged': True, 'pid_unchanged': True},
            'Closed direct manager resumed')
        guard = artifacts.json(row['guard'], r.MAX_ARTIFACT_BYTES)
        manager.check_guard(guard, initializer='initialize-components', frames=row['frames'], artifacts=artifacts)
        for method in ('CorePassManager.build_result', 'CorePassManager.inspection_state', 'CorePassManager._native_return'):
            require(['biocompiler.core_pipeline_manager', method] in guard, 'Direct control omitted actual '+method)
        details = {}
        traffic = manager.validate_frames(row['frames'], artifacts, channel, application, sessions=sessions,
            details=details, provider_calls=True, initializer='initialize-components')
        result = validate_case(expected, artifacts.json(row['actual'], r.MAX_ARTIFACT_BYTES),
            artifacts.json(row['evidence'], r.MAX_ARTIFACT_BYTES), details, oracle, original, application)
        projected.append({**result, **traffic})
    return projected
