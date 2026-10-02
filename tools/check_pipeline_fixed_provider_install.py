"""Installed fixed-provider typed return and physical origin replay.

The complete original supplement remains expected-only. Actual selected native
executables produce every candidate and perform every manager acceptance check.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import importlib
import importlib.util
import os
from pathlib import Path
import platform
import re
import sys
import time
from types import FunctionType

if __package__:
    from . import check_pipeline_manager_install as manager
else:
    import check_pipeline_manager_install as manager

r = manager.r
ROOT = manager.ROOT
canonical, sha, require, equal = manager.canonical, manager.sha, manager.require, manager.equal
artifact, Artifacts = manager.artifact, manager.Artifacts
SCHEMA = 'biocompiler.installed_fixed_provider_views.v1'
SCOPE = 'three_source_bound_fixed_provider_families_complete_typed_returns_and_aliases_not_full_fixed_interception'
RECEIPT_FILE = 'pipeline-fixed-providers.json'
ARTIFACT_DIRECTORY = 'pipeline-fixed-providers-artifacts'
ORACLE_PATH = 'tests/conformance/pipeline-fixed-provider-semantics-v1.json'
ORACLE_TOOL = 'tools/capture_pipeline_fixed_provider_semantics.py'
VIEW_MODULE = 'biocompiler.core_pipeline_provider_views'
SOURCES = (ORACLE_TOOL, 'tests/test_pipeline_fixed_provider_semantics.py',
    'tools/check_pipeline_fixed_provider_install.py', 'tests/test_pipeline_fixed_provider_campaign.py',
    'src/biocompiler/core_pipeline_provider_views.py', 'tests/test_core_pipeline_provider_views.py', *manager.SOURCES)
CASES = ('static:requested', 'static:selected_equal', 'temporal:requested')
COVERAGE = {'cases': 3, 'providers': 9, 'returns': 18}
ORACLE_SHA256 = '1f25d16d8fa9688ea34b4937f1d4a2c10fdf44d862daf8990168247758a019e7'


class Corpus:
    def __init__(self):
        self.value, self.pin = r.read(ROOT / ORACLE_PATH)
        require(self.pin == ORACLE_SHA256, 'Frozen original fixed-provider file changed')
        require(self.value['schema_version'] == 'biocompiler.pipeline_fixed_provider_semantics.v1', 'Unknown fixed-provider original schema')
        equal(self.value['coverage'], COVERAGE, 'Original fixed-provider census changed')
        require(tuple(case['id'] for case in self.value['cases']) == CASES, 'Original fixed-provider cases reordered or missing')
        equal(self.value['inventory_fingerprint'], sha(canonical({key: value for key, value in self.value.items()
            if key != 'inventory_fingerprint'})), 'Original fixed-provider inventory changed')
        for path, identity in self.value['source_files'].items():
            require(not Path(path).is_absolute() and '..' not in Path(path).parts and r.pin(identity)
                and sha(r.raw_file(ROOT / path)) == identity, 'Original fixed-provider source changed: '+path)
        self.cases = self.value['cases']
        # Retain the pre-existing full inventories, source pins and exclusions.
        self.previous = manager.Corpus()

    def metadata(self):
        return {'oracle': {'path': ORACLE_PATH, 'sha256': self.pin, 'inventory_fingerprint': self.value['inventory_fingerprint']},
            'coverage': COVERAGE, 'original_sources': self.value['source_files'], 'pending': self.value['pending'],
            'prior_campaign_authority': manager.metadata(self.previous), 'prior_pending': self.previous.pending,
            'declarations': r.source_pins((manager.CHANNEL_PATH, manager.APPLICATION_PATH))}


def load_oracle(*, installed=True):
    if installed:
        installed_modules()
    paths = list(sys.path)
    spec = importlib.util.spec_from_file_location('fixed_provider_original', ROOT / ORACLE_TOOL)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = paths
    require(sys.path == paths, 'Original fixed-provider loader changed import authority')
    if installed:
        installed_modules()
    return module


def product_sources(corpus):
    paths = {path for path in corpus.value['source_files'] if path.startswith('src/')}
    paths.update(manager.python_sources())
    paths.add('src/' + VIEW_MODULE.replace('.', '/') + '.py')
    return r.source_pins(paths)


def installed_modules():
    manager.installed_modules()
    for name, module in tuple(sys.modules.items()):
        if name == 'biocompiler' or name.startswith('biocompiler.'):
            path = getattr(module, '__file__', None)
            require(path and not Path(path).resolve().is_relative_to(ROOT), 'Source-tree product module in installed fixed-provider replay: '+name)


def raw_manager(value):
    return value.manager if type(value) is manager.GuardedManager else value


class Witness:
    def __init__(self):
        self.request = self.config = self.manager = None
        self.calls, self.pending = [], None
        self.inspection = None
        self.providers = {}
        self.contracts = {}
        self.proposals = []

    def observe(self, phase, instance, role, ordinal, context, proposal):
        live = raw_manager(instance)
        if phase == 'before':
            require(self.pending is None, 'Overlapping fixed producer observations')
            self.pending = {'pass_id': role, 'ordinal': ordinal, 'before_frames': len(live.session.traffic),
                'context': context}
            return
        require(phase == 'after' and self.pending is not None, 'Unpaired fixed producer observation')
        row = self.pending
        require(row['pass_id'] == role and row['ordinal'] == ordinal and row.pop('context') is context,
            'Fixed producer changed its actual callback context')
        row.update(after_frames=len(live.session.traffic), sequence=live.session.last_response.sequence)
        self.calls.append(row)
        self.proposals.append(proposal)
        self.pending = None

    def registrations(self, instance):
        live = raw_manager(instance)
        state = instance.inspection_state()
        self.inspection = live.session.last_response.sequence
        for pass_id, (_, provider, validators) in state['_passes'].items():
            self.contracts[pass_id] = state['_passes'][pass_id][0]
            for slot, actual in [('producer', provider), *validators.items()]:
                tokens = [token for token, value in live._inspection_providers.items() if value is actual]
                require(len(tokens) == 1, 'Fixed provider lacks exact native inspection identity')
                self.providers[tokens[0]] = {'pass_id': pass_id, 'slot': slot, 'object': actual}
        return state['_passes']

    def evidence(self, oracle):
        require(self.pending is None and self.manager is not None, 'Incomplete fixed producer witness')
        live = self.manager
        roots = [('target', self.request.target), ('config', self.config), ('request', self.request),
            *oracle.source_origins(self.request)]
        objects, providers = {}, {}
        for handle, value in live._objects._objects.items():
            names = [name for name, root in roots if value is root]
            if names:
                objects[handle] = {'kind': 'source', 'names': names}
            matches = [token for token, item in self.providers.items() if value is item['object']]
            if matches:
                require(len(matches) == 1 and handle not in objects, 'Fixed provider aliased a source object')
                providers[matches[0]] = {'object': handle, 'pass_id': self.providers[matches[0]]['pass_id'],
                    'slot': self.providers[matches[0]]['slot']}
            if type(value) is FunctionType and value.__module__ == oracle.__name__ and value.__qualname__ == 'run_case.<locals>.wrapper':
                objects[handle] = {'kind': 'wrapper', 'pass_id': value.__defaults__[2]}
        require(set(providers) == set(self.providers), 'Fixed provider host-reference census changed')
        arguments = {}
        for entry in live.session.traffic:
            document = manager.frame_body(entry.frame)
            if document['kind'] != 'command':
                continue
            operation, args = document['operation'], document['arguments']
            if operation == 'register':
                value = live._objects.resolve(args['validators'])
                require(type(value) is dict, 'Original fixed validator mapping changed type')
                items = []
                for key, provider in value.items():
                    tokens = [token for token, item in self.providers.items() if item['object'] is provider]
                    require(len(tokens) == 1, 'Original fixed validator mapping has a foreign provider')
                    items.append([key, tokens[0]])
                arguments[args['validators']['handle']] = {'kind': 'validators', 'items': items}
                pass_id = args['contract']['id']
                for index, ref in enumerate(args['obligation_objects']):
                    value = live._objects.resolve(ref)
                    require(value is self.contracts[pass_id].introduces[index], 'Introduced obligation lost inspected contract object identity')
                    arguments[ref['handle']] = {'kind': 'contract_obligation', 'pass_id': pass_id, 'index': index,
                        'value': {name: object.__getattribute__(value, name) for name in ('id', 'scope', 'description')} |
                            {'evidence_kind': object.__getattribute__(value, 'evidence_kind').value}}
            elif operation == 'run':
                if args['configuration'] is None:
                    continue
                value = live._objects.resolve(args['configuration'])
                arguments[args['configuration']['handle']] = {'kind': 'configuration', 'value': oracle.plain(value)}
        for row, proposal in zip(self.calls, self.proposals):
            handles = [handle for handle, value in live._objects._objects.items() if value is proposal]
            require(len(handles) <= 1, 'Proposal had multiple physical host references')
            row['returned_object'] = handles[0] if handles else None
        return {'inspection': self.inspection, 'calls': self.calls, 'objects': objects, 'providers': providers,
            'arguments': arguments}


def campaign(core, corpus, receipt):
    from biocompiler.core_pipeline_manager import CorePassManager
    from biocompiler.core_client import CoreProtocolError
    oracle = load_oracle()
    fresh = oracle.capture()
    equal(fresh, corpus.value, 'Fresh original fixed-provider behavior changed')
    receipt['fresh_original'] = artifact(receipt, canonical(fresh))
    for expected in corpus.cases:
        witness, seen = Witness(), set()
        row = {'id': expected['id']}
        receipt['checks'].append(row)
        def factory(request, history, *, until, config):
            witness.request, witness.config = request, config
            with manager.guarded_execution(seen):
                actual = CorePassManager.from_components(core, request, history, until=until, config=config)
            witness.manager = actual
            return manager.GuardedManager(actual, seen)
        try:
            result = oracle.run_case(expected['id'], manager_factory=factory, registrations=witness.registrations,
                observe=witness.observe)
            row['actual'] = artifact(receipt, canonical(result))
            row['evidence'] = artifact(receipt, canonical(witness.evidence(oracle)))
        finally:
            if witness.manager is not None:
                with manager.guarded_execution(seen):
                    witness.manager.close()
                session = witness.manager.session
                row.update(pid=session.pid, returncode=session.returncode, closed=session.closed, invalidated=session.invalidated,
                    executable_sha256=session.executable_sha256, stderr=artifact(receipt, canonical({'hex': session.stderr_bytes.hex()})),
                    frames=[{'direction': entry.direction, 'index': entry.index, 'frame': artifact(receipt, entry.frame)} for entry in session.traffic])
                before = len(session.traffic)
                try:
                    with manager.guarded_execution(seen):
                        witness.manager.get('request')
                except CoreProtocolError as error:
                    row['after_close'] = artifact(receipt, canonical({'type': type(error).__name__, 'message': str(error),
                        'traffic_unchanged': len(session.traffic) == before, 'pid_unchanged': session.pid == row['pid']}))
                else:
                    raise AssertionError('Closed fixed-provider manager resumed')
            row['guard'] = artifact(receipt, canonical([list(item) for item in sorted(seen)]))
    installed_modules()


def reference(value):
    require(type(value) is dict and set(value) == {'handle'} and type(value['handle']) is str
        and re.fullmatch(r'object/[0-9]+', value['handle']), 'Malformed fixed-provider object reference')
    return value['handle']


def returned(invocation):
    require(invocation['outcome']['status'] == 'return', 'Fixed-provider host operation failed')
    return invocation['outcome']['value']


def succeeded(command):
    require(command['outcome']['status'] == 'ok', 'Fixed-provider native command failed')
    return command['outcome']['value']


class BindingCensus:
    """Validate every wire view against its document and lifetime identity."""
    def __init__(self, details, source_documents):
        from biocompiler.core_pipeline_provider_views import checked_ordered
        self.checked_ordered = checked_ordered
        self.native, self.records, self.record_ids = {}, {}, {}
        self.contexts, self.context_objects = set(), set()
        self.host = {handle: [positioned] for handle, positioned in source_documents.items()}
        for invocation in details['invocations'].values():
            if invocation['action'] == 'ordered-json':
                tree = returned(invocation)
                # Reuse the closed tree parser, then retain the complete
                # projection together with its actual continuation position.
                from biocompiler.core_pipeline_manager import _unordered
                from biocompiler.ir.intent import thaw_json
                value = thaw_json(_unordered(tree))
                self.checked_ordered(tree, value)
                handle = reference(invocation['arguments']['object'])
                self.host.setdefault(handle, []).append((invocation['end_frame'], value))

    @staticmethod
    def identity(value, label):
        require(type(value) is str and re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*/[0-9]+', value),
            'Malformed '+label+' lifetime identity')
        return value

    def binding(self, binding, value, frame, *, flavor='json'):
        require(type(binding) is dict and binding.get('kind') in ('host', 'native'), 'Malformed complete view binding')
        if binding['kind'] == 'host':
            require(set(binding) == {'kind', 'object'}, 'Malformed host view binding')
            handle = reference(binding['object'])
            candidates = sorted((position, document) for position, document in self.host.get(handle, ()) if position < frame)
            require(candidates, 'Host view binding lacks its preceding actual source or ordered JSON observation')
            equal(candidates[-1][1], value, 'Host view binding projection differs from its complete document')
            return ('host', handle)
        require(set(binding) == {'kind', 'identity', 'tree'}, 'Malformed native view binding')
        token = self.identity(binding['identity'], 'native view')
        try:
            self.checked_ordered(binding['tree'], value)
        except Exception as error:
            raise AssertionError('Native view binding projection differs from its complete document') from error
        signature = (canonical(binding['tree']), flavor)
        require(token not in self.native or self.native[token] == signature,
            'Native view lifetime identity was rebound to another value or flavor')
        self.native[token] = signature
        return ('native', token)

    def record(self, envelope, frame):
        require(type(envelope) is dict and set(envelope) == {'value', 'bindings'}, 'Incomplete native record envelope')
        value, bindings = envelope['value'], envelope['bindings']
        require(type(value) is dict and set(value) == {'schema_version', 'id', 'stage', 'payload', 'requirements',
            'obligations', 'discharged', 'dependencies', 'parent', 'pass_id', 'pass_identity', 'checks', 'provenance', 'accepted'}
            and value['schema_version'] == 'biocompiler.stage_record.v0.1' and type(value['id']) is str
            and type(value['accepted']) is bool, 'Malformed complete native record document')
        require(type(bindings) is dict and set(bindings) == {'record_id', 'payload', 'dependencies', 'requirements',
            'obligations', 'obligation_objects', 'checks', 'provenance'}, 'Incomplete native record binding fields')
        token = self.identity(bindings['record_id'], 'record')
        signature = canonical(envelope)
        require(value['id'] not in self.records or self.records[value['id']] == (token, signature), 'Stored native record identity was rebound')
        require(token not in self.record_ids or self.record_ids[token] == value['id'], 'Different records reused one lifetime identity')
        self.records[value['id']] = (token, signature); self.record_ids[token] = value['id']
        for name in ('payload', 'dependencies', 'requirements', 'checks', 'provenance'):
            self.binding(bindings[name], value[name], frame)
        require(type(value['obligations']) is list and type(bindings['obligation_objects']) is list
            and len(bindings['obligation_objects']) == len(value['obligations']), 'Native obligation element binding census differs')
        self.binding(bindings['obligations'], value['obligations'], frame, flavor='obligations')
        for binding, obligation in zip(bindings['obligation_objects'], value['obligations']):
            self.binding(binding, obligation, frame, flavor='obligation')

    def context(self, invocation):
        args = invocation['arguments']; document, bindings = args['document'], args['bindings']
        fields = {'input', 'output', 'target', 'configuration', 'dependencies', 'requirements', 'source_links', 'observation_map'}
        require(type(document) is dict and set(document) == fields and type(bindings) is dict and set(bindings) == fields,
            'Incomplete native context binding fields')
        token = self.identity(args['context_id'], 'context')
        handle = reference(returned(invocation))
        require(token not in self.contexts and handle not in self.context_objects, 'Distinct producer contexts reused a lifetime token or host object')
        self.contexts.add(token); self.context_objects.add(handle)
        frame = invocation['start_frame']
        for name in ('input', 'target', 'configuration', 'dependencies', 'requirements'):
            self.binding(bindings[name], document[name], frame, flavor='target' if name == 'target' else 'json')
        require(bindings['output'] is None and document['output'] is None and bindings['source_links'] is None
            and document['source_links'] == [], 'Producer context contains output or source-link bindings')
        self.binding(bindings['observation_map'], document['observation_map'], frame, flavor='default-observation')


def validate_case(expected, actual, evidence, details, oracle):
    """Rebuild every typed return from its bound native reply, then observe it.

    Source-owned request objects are authored afresh. They are never accepted
    outputs. The structural decoder cannot call the original compiler/checkers.
    """
    from biocompiler.core_pipeline_provider_views import ProviderViewStore, origin_reference
    equal(actual, expected, 'Complete actual fixed-provider observation differs from original')
    require(type(evidence) is dict and set(evidence) == {'inspection', 'calls', 'objects', 'providers', 'arguments'},
        'Incomplete fixed-provider evidence')
    commands = {item['sequence']: item for item in details['commands']}
    requests = sorted(commands.values(), key=lambda item: item['start_frame'])
    expected_operations = ['initialize-components', 'inspect-ordered']
    for _ in expected['events']:
        expected_operations.extend(['register', 'run', 'call-native-provider', 'call-native-provider'])
    equal([item['operation'] for item in requests], expected_operations, 'Fixed-provider operation census/order changed')
    initialization, inspection = requests[:2]
    require(evidence['inspection'] == inspection['sequence'] and initialization['parent_invocation'] is None
        and inspection['parent_invocation'] is None, 'Fixed inspection is detached from its native command')
    args = initialization['arguments']
    for name in ('request', 'history', 'until', 'config'):
        equal(args[name], expected['authority'][name], 'Fixed initialization changed original authoring authority: '+name)
    from biocompiler.core_pipeline_manager import _ordered
    require(args['manager_limits'] is None, 'Fixed campaign changed manager limits')
    initial_result = succeeded(initialization)
    require(type(initial_result) is dict and set(initial_result) == {'kind', 'manager', 'artifacts', 'target'}
        and initial_result['kind'] == 'components' and initial_result['manager'] is True,
        'Fixed initializer did not construct a real component manager')
    equal(initial_result['artifacts'], ['candidate', 'pipeline_result', 'selection_result', 'assembly', 'link_result', 'behavior_result'],
        'Fixed initializer omitted completed native artifacts')
    request, history, until, config = oracle.authority(expected['id'])
    equal({'request': request.to_dict(), 'history': [item.to_dict() for item in history], 'until': until, 'config': config.to_dict()},
        expected['authority'], 'Fresh original source authoring differs')
    equal(args['request_tree'], _ordered(request.to_dict()), 'Fixed initialization changed authored request insertion order')
    source_values = {'target': request.target, 'config': config, 'request': request, **dict(oracle.source_origins(request))}
    objects = evidence['objects']
    require(type(objects) is dict and type(evidence['providers']) is dict and type(evidence['arguments']) is dict,
        'Malformed fixed-provider source identity tables')
    host = {}
    names_seen = set()
    wrappers = {}
    for handle, entry in objects.items():
        reference({'handle': handle})
        require(type(entry) is dict, 'Malformed fixed-provider object witness')
        if entry.get('kind') == 'source':
            require(set(entry) == {'kind', 'names'} and type(entry['names']) is list and entry['names']
                and len(entry['names']) == len(set(entry['names'])) and all(name in source_values for name in entry['names']),
                'Unknown fixed-provider source origin')
            values = [source_values[name] for name in entry['names']]
            require(all(value is values[0] for value in values), 'Different source objects were physically aliased')
            require(all(previous is not values[0] for previous in host.values()), 'One source object has duplicate host handles')
            require(not names_seen.intersection(entry['names']), 'Source origin appeared twice')
            names_seen.update(entry['names']); host[handle] = values[0]
        else:
            require(set(entry) == {'kind', 'pass_id'} and entry['kind'] == 'wrapper'
                and entry['pass_id'] in dict(oracle.PROVIDERS) and entry['pass_id'] not in wrappers,
                'Unknown or duplicate original wrapper')
            wrappers[entry['pass_id']] = handle
    require(set(wrappers) == set(dict(oracle.PROVIDERS)), 'Original wrapper census differs')
    for name in ('target', 'config', 'request'):
        require(host.get(reference(args[name+'_object'])) is source_values[name], 'Fixed initializer lost authored '+name+' identity')
    equal(initial_result['target'], {'value': request.target.to_dict(),
        'binding': {'kind': 'host', 'object': args['target_object']}}, 'Fixed manager did not retain target identity')
    # Every externally anchored alias must arise at a real native origin request.
    origin_handles = {reference(args[name+'_object']) for name in ('target', 'config', 'request')}
    for invocation in details['invocations'].values():
        if invocation['action'] == 'origin-reference':
            params = invocation['arguments']
            value = origin_reference(request, params['root'], params['path'])
            handle = reference(returned(invocation))
            require(handle in host and host[handle] is value, 'Native origin action changed its actual source object')
            owner = commands[invocation['command_sequence']]
            require(owner['operation'] == 'call-native-provider', 'Source origin is outside its actual producer call')
            origin_handles.add(handle)
    require(set(host) == origin_handles, 'Source object witness lacks its native origin invocation')
    source_documents = {reference(args['target_object']): (0, request.target.to_dict())}
    for handle, entry in evidence['arguments'].items():
        if entry['kind'] == 'contract_obligation':
            positions = [command['start_frame'] for command in requests if command['operation'] == 'register'
                and {'handle': handle} in command['arguments']['obligation_objects']]
            require(positions, 'Introduced obligation has no actual authoring command')
            source_documents[handle] = (min(positions), entry['value'])
    bindings = BindingCensus(details, source_documents)
    providers = evidence['providers']
    raw_inspection = succeeded(inspection)
    inspected = manager.comparison_snapshot(raw_inspection, {token: token for token in providers})
    for envelope in raw_inspection['snapshot']['records'].values():
        bindings.record(envelope, inspection['end_frame'])
    require(set(inspected['state']['passes']) == set(dict(oracle.PROVIDERS)), 'Fixed native registration inventory changed')
    roles, provider_handles = {}, set()
    minted = {}
    for invocation in details['invocations'].values():
        if invocation['action'] == 'native-provider':
            params = invocation['arguments']
            token, handle = params['provider_id'], reference(returned(invocation))
            require(token not in minted and invocation['command_sequence'] == inspection['sequence'],
                'Fixed provider proxy was duplicated or minted outside inspection')
            minted[token] = (handle, params['role'])
    require(set(minted) == set(providers), 'Fixed native proxy census differs')
    for token, entry in providers.items():
        require(type(entry) is dict and set(entry) == {'object', 'pass_id', 'slot'} and entry['pass_id'] in dict(oracle.PROVIDERS),
            'Malformed actual fixed-provider identity')
        handle = entry['object']; reference({'handle': handle})
        require(handle not in provider_handles and handle not in objects, 'Fixed providers are not physically distinct')
        provider_handles.add(handle)
        registration = inspected['state']['passes'][entry['pass_id']]
        slot = entry['slot']
        require(token == (registration['producer'] if slot == 'producer' else registration['validators'].get(slot)),
            'Provider role differs from actual native registration')
        role = entry['pass_id'] + ('.producer' if slot == 'producer' else '.validator')
        equal(minted[token], (handle, role), 'Native provider proxy role or actual object differs')
        roles[token] = role
    equal({entry['provider_id']: entry['object']['handle'] for entry in raw_inspection['providers']},
        {token: entry['object'] for token, entry in providers.items()}, 'Inspection provider objects differ from retained source')
    ledger = oracle.Ledger()
    ledger.semantics(request.target, ['target']); ledger.semantics(config, ['requested_config'])
    roots = {'target': ledger.ref(request.target), 'manager_target': ledger.ref(request.target), 'requested_config': ledger.ref(config)}
    equal(roots, actual['roots'], 'Actual authored root identities differ')
    origins = []
    for name, value in oracle.source_origins(request):
        ledger.semantics(value, ['source_origins', name])
        origins.append({'origin': name, 'ref': ledger.ref(value), 'value': oracle.plain(value)})
    equal(origins, actual['source_origins'], 'Complete original source roots differ')
    def resolve(value):
        handle = reference(value)
        require(handle in host, 'Typed reply references an unproven host origin')
        return host[handle]
    store = ProviderViewStore(resolve)
    calls = evidence['calls']
    require(type(calls) is list and len(calls) == 6, 'Original repeated provider call census changed')
    used_arguments, used_callbacks = set(), set()
    for index, event in enumerate(actual['events']):
        pass_id = event['pass_id']
        register, run, first, second = requests[2+4*index:6+4*index]
        require(register['parent_invocation'] is None and run['parent_invocation'] is None
            and register['end_frame'] < run['start_frame'], 'Original registration/run chronology differs')
        equal(succeeded(register), None, 'Fixed wrapper registration failed')
        equal(register['arguments']['contract'], event['contract'], 'Wrapper changed original fixed contract')
        original_contract = deepcopy(event['contract'])
        original_contract['version'] = original_contract['version'].removesuffix('.fixed_view_witness')
        equal(inspected['state']['passes'][pass_id]['contract'], original_contract, 'Actual retained fixed contract differs')
        require(reference(register['arguments']['producer']) == wrappers[pass_id], 'Registration lost original wrapper')
        obligations = register['arguments']['obligation_objects']
        require(type(obligations) is list and len(obligations) == len(event['contract']['introduces']),
            'Registration changed introduced obligation census')
        for offset, (ref, wanted) in enumerate(zip(obligations, event['contract']['introduces'])):
            handle = reference(ref); used_arguments.add(handle)
            equal(evidence['arguments'].get(handle), {'kind': 'contract_obligation', 'pass_id': pass_id, 'index': offset, 'value': wanted},
                'Registration changed actual inspected obligation slot or value')
        validator_ref = reference(register['arguments']['validators']); used_arguments.add(validator_ref)
        wanted_validators = [[key, inspected['state']['passes'][pass_id]['validators'][key]]
            for key in raw_inspection['order']['validators']['passes'][pass_id]]
        equal(evidence['arguments'].get(validator_ref), {'kind': 'validators', 'items': wanted_validators},
            'Registration changed actual retained validator objects or order')
        # Every old validator is reused through the actual native capability.
        validator_tokens = {token for _, token in wanted_validators}
        observed_native = set()
        for invocation in details['invocations'].values():
            if invocation['command_sequence'] == register['sequence'] and invocation['action'] == 'provider-reference':
                value = returned(invocation)
                handle = reference(invocation['arguments']['object'])
                if handle in provider_handles:
                    token = next(token for token, item in providers.items() if item['object'] == handle)
                    equal(value, {'kind': 'native', 'provider_id': token}, 'Validator ceased to be its native fixed capability')
                    observed_native.add(token)
        require(observed_native == validator_tokens, 'Actual fixed validator reuse was omitted')
        for name in ('pass_id', 'input_id', 'output_id'):
            equal(run['arguments'][name], event[name], 'Run changed original fixed call argument: '+name)
        configured = config.to_dict() if pass_id == 'behavior_to_synthetic' else None
        if configured is None:
            require(run['arguments']['configuration'] is None, 'Run replaced original absent configuration')
        else:
            config_ref = reference(run['arguments']['configuration']); used_arguments.add(config_ref)
            equal(evidence['arguments'].get(config_ref), {'kind': 'configuration', 'value': oracle.plain(configured)},
                'Run changed original configuration object')
        result = succeeded(run)
        require(type(result) is dict and set(result) == {'value', 'bindings'}, 'Run omitted complete native accepted record')
        equal(result['value'], event['record'], 'Native accepted record differs from actual original observation')
        bindings.record(result, run['end_frame'])
        callbacks = [(identity, invocation) for identity, invocation in details['invocations'].items()
            if invocation['command_sequence'] == run['sequence'] and invocation['action'] == 'call-provider']
        require(len(callbacks) == 1, 'Original wrapper was not invoked exactly once')
        identity, callback = callbacks[0]; used_callbacks.add(identity)
        binds = [invocation for invocation in details['invocations'].values() if invocation['action'] == 'bind-provider'
            and invocation['command_sequence'] == register['sequence']
            and invocation['arguments'] == {'provider_id': callback['arguments']['provider_id'], 'object': {'handle': wrappers[pass_id]}}]
        require(len(binds) == 1 and returned(binds[0]) is None, 'Wrapper callback lost its actual registered callable')
        context_ref = callback['arguments']['context']
        contexts = [invocation for invocation in details['invocations'].values() if invocation['action'] == 'hydrate-context'
            and invocation['command_sequence'] == run['sequence'] and returned(invocation) == context_ref]
        require(len(contexts) == 1, 'Producer callback lacks its actual native context')
        context = contexts[0]['arguments']
        bindings.context(contexts[0])
        require(contexts[0]['end_frame'] < callback['start_frame'] and context['document']['output'] is None,
            'Producer was given a validator context')
        equal(context['document'], {'input': expected['authority']['request']['build_request'] if index == 0
            else actual['events'][index-1]['record']['payload'], 'output': None, 'target': request.target.to_dict(),
            'configuration': {} if configured is None else configured, 'dependencies': inspected['state']['dependencies'],
            'requirements': event['record']['requirements'], 'source_links': [], 'observation_map': {}},
            'Producer context differs from actual preceding native state and original call')
        equal(context['bindings']['target'], {'kind': 'host', 'object': args['target_object']}, 'Producer context lost target identity')
        equal(ledger.ref(request.target), event['context_target'], 'Producer target observation changed')
        for ordinal, command in enumerate((first, second)):
            link = calls[2*index+ordinal]
            require(type(link) is dict and set(link) == {'pass_id', 'ordinal', 'before_frames', 'after_frames', 'sequence', 'returned_object'}
                and link['pass_id'] == pass_id and type(link['ordinal']) is int and link['ordinal'] == ordinal
                and type(link['sequence']) is int and link['sequence'] == command['sequence']
                and link['before_frames'] == command['start_frame'] and link['after_frames'] == command['end_frame']+1,
                'Original provider observation is detached from its exact reply interval')
            equal(command['arguments'], {'provider_id': inspected['state']['passes'][pass_id]['producer'],
                'context_id': context['context_id']}, 'Provider command changed closure or live context')
            require(command['parent_invocation'] == identity and callback['start_frame'] < command['start_frame']
                < command['end_frame'] < callback['end_frame'], 'Direct producer call lost its actual enclosing wrapper')
            envelope = succeeded(command)
            require(envelope['kind'] == 'proposal', 'Fixed producer did not return a proposal')
            proposal = store.decode(envelope, role=roles[command['arguments']['provider_id']], target=request.target,
                target_document=request.target.to_dict(), requested_config=config)
            ledger.semantics(proposal, ['calls', pass_id, ordinal])
            equal(ledger.proposal(proposal), event['calls'][ordinal], 'Native reply typed fields or physical aliases differ from actual observation')
            if ordinal == 0:
                require(link['returned_object'] is not None and reference(returned(callback)) == link['returned_object'],
                    'Wrapper did not return the first actual native proposal')
            else:
                require(link['returned_object'] is None, 'Unreturned repeated proposal acquired an unexplained host handle')
    require(set(evidence['arguments']) == used_arguments, 'Unclaimed original fixed call argument evidence')
    require(used_callbacks == {identity for identity, item in details['invocations'].items() if item['action'] == 'call-provider'},
        'Extra original wrapper invocation')
    require(len(bindings.contexts) == 3 and len(bindings.context_objects) == 3,
        'Complete live producer context census differs')
    require(not set(bindings.native).intersection(store.native), 'Typed provider and ordinary view identities collide')
    equal(len(ledger.retained), actual['retained_objects'], 'Native reply root identity census differs')
    equal(ledger.graph(), actual['semantic_alias_groups'], 'Native reply complete typed identity graph differs')
    return {'id': expected['id'], 'complete_case_sha256': sha(canonical(actual)), 'returns': len(calls)}


def validate_checks(receipt, corpus, artifacts):
    require(type(receipt.get('completed_checks')) is int and receipt['completed_checks'] == 3
        and type(receipt.get('checks')) is list and len(receipt['checks']) == 3,
        'Incomplete installed fixed-provider campaign')
    equal(artifacts.json(receipt['fresh_original'], r.MAX_ARTIFACT_BYTES), corpus.value,
        'Fresh original fixed-provider authority changed')
    channel, application = manager.declarations()
    manager.validate_verify(receipt, artifacts, channel, application)
    oracle = load_oracle(installed=False)
    sessions, pids, projected = set(), set(), []
    for expected, row in zip(corpus.cases, receipt['checks']):
        require(type(row) is dict and set(row) == {'id', 'actual', 'evidence', 'pid', 'returncode', 'closed', 'invalidated',
            'executable_sha256', 'stderr', 'frames', 'after_close', 'guard'} and row['id'] == expected['id'],
            'Missing or reordered fixed-provider case')
        require(type(row['pid']) is int and row['pid'] > 0 and row['pid'] not in pids
            and type(row['returncode']) is int and row['returncode'] == 0 and row['closed'] is True
            and row['invalidated'] is False and row['executable_sha256'] == receipt['native_inputs']['sha256']['biocompiler-core'],
            'Fixed-provider process authority or lifecycle differs')
        pids.add(row['pid'])
        equal(artifacts.json(row['stderr']), {'hex': ''}, 'Fixed-provider process wrote stderr')
        equal(artifacts.json(row['after_close']), {'type': 'CoreProtocolError',
            'message': 'Callback session is closed; it cannot reconnect', 'traffic_unchanged': True, 'pid_unchanged': True},
            'Closed fixed-provider manager resumed')
        guard = artifacts.json(row['guard'], r.MAX_ARTIFACT_BYTES)
        manager.check_guard(guard, initializer='initialize-components')
        for name in ('CorePassManager.inspection_state', 'CorePassManager._call_native', 'CorePassManager._native_return'):
            require(['biocompiler.core_pipeline_manager', name] in guard, 'Missing actual typed native-provider execution: '+name)
        details = {}
        traffic = manager.validate_frames(row['frames'], artifacts, channel, application, sessions=sessions,
            details=details, provider_calls=True, initializer='initialize-components')
        result = validate_case(expected, artifacts.json(row['actual'], r.MAX_ARTIFACT_BYTES),
            artifacts.json(row['evidence'], r.MAX_ARTIFACT_BYTES), details, oracle)
        projected.append({**result, **traffic})
    require(artifacts.used == set(artifacts.declared), 'Unreferenced complete fixed-provider evidence')
    return projected


def compare(root, native_root, *, revision, source_revision, run_id):
    require(type(revision) is str and re.fullmatch(r'[0-9a-f]{40}', revision)
        and type(source_revision) is str and re.fullmatch(r'[0-9a-f]{40}', source_revision)
        and type(run_id) is str and run_id, 'Missing current fixed-provider validation authority')
    root, native_root = Path(root), Path(native_root)
    names = {'realization-'+target+'-py'+python for target in r.PLATFORMS for python in r.PYTHONS}
    require(root.is_dir() and not root.is_symlink() and native_root.is_dir() and not native_root.is_symlink()
        and {path.name for path in root.iterdir() if path.name.startswith('realization-')} == names,
        'Incomplete four-runtime fixed-provider matrix')
    corpus, receipts, binaries, reference_projection = Corpus(), {}, {}, None
    for target, (system, machine) in r.PLATFORMS.items():
        native = r.verify_binaries(native_root / target, revision, target)
        binaries[target] = native
        for python in r.PYTHONS:
            name = 'realization-'+target+'-py'+python
            directory = root / name
            require(directory.is_dir() and not directory.is_symlink(), 'Unsafe fixed-provider runtime slot')
            inputs, inputs_pin = r.read(directory / 'native-inputs.json', r.CONTROL_BYTES)
            require(all(inputs.get(key) == value for key, value in native.items()) and inputs.get('run_id') == run_id
                and inputs.get('source_revision') == source_revision and type(inputs.get('python_version')) is str
                and inputs['python_version'].startswith(python+'.'), 'Stale fixed-provider native inputs')
            receipt, receipt_pin = r.read(directory / RECEIPT_FILE)
            wanted = {'schema_version': SCHEMA, 'status': 'success', 'scope': SCOPE, 'revision': revision,
                'source_revision': source_revision, 'run_id': run_id, 'python_version': inputs['python_version'],
                'system': system, 'machine': machine, 'native_platform': target,
                'artifact_directory': ARTIFACT_DIRECTORY, 'native_inputs': native,
                'python_sources': product_sources(corpus), 'campaign_sources': r.source_pins(SOURCES), **corpus.metadata()}
            for key, value in wanted.items():
                equal(receipt.get(key), value, 'Stale or mixed fixed-provider receipt: '+key)
            require(type(receipt.get('package_path')) is str and Path(receipt['package_path']).is_absolute()
                and not Path(receipt['package_path']).is_relative_to(ROOT), 'Fixed-provider package was not installed')
            require(type(receipt.get('executables')) is dict and set(receipt['executables']) == {'core', 'verify'}
                and all(type(path) is str and Path(path).is_absolute() and Path(path).name == 'biocompiler-'+role
                    for role, path in receipt['executables'].items())
                and Path(receipt['executables']['core']).parent == Path(receipt['executables']['verify']).parent,
                'Exact fixed-provider binary selection absent')
            artifacts = Artifacts(directory / ARTIFACT_DIRECTORY, receipt['artifacts'])
            projected = canonical(validate_checks(receipt, corpus, artifacts))
            require(reference_projection is None or projected == reference_projection,
                'Complete fixed-provider observations differ across four runtimes')
            reference_projection = projected
            receipts[name] = {'receipt_sha256': receipt_pin, 'native_inputs_sha256': inputs_pin, 'complete_artifacts': artifacts.verified}
    return {'schema_version': 'biocompiler.pipeline_fixed_provider_reproducibility.v1', 'status': 'success', 'scope': SCOPE,
        'revision': revision, 'source_revision': source_revision, 'run_id': run_id, **corpus.metadata(),
        'receipts': receipts, 'native_inputs': binaries, 'complete_results_sha256': sha(reference_projection),
        'projection': 'validated_unique_session_UUID4_and_process_PID_only;exact_command_invocation_hash_bindings_verified_before_projection;complete_frames_retained'}


def campaign_main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    for role in ('core', 'verify'):
        parser.add_argument('--'+role, required=True, type=Path)
        parser.add_argument('--'+role+'-sha256', required=True)
    parser.add_argument('--native-root', required=True, type=Path)
    parser.add_argument('--platform', required=True, choices=r.PLATFORMS)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    import biocompiler
    from biocompiler.core_client import CoreClient
    for name in sorted(manager.TRANSPORT_MODULES | manager.LITERAL_MODULES | {VIEW_MODULE}):
        importlib.import_module(name)
    # Preload every source-owned class before loading authoring-only recipes.
    corpus, directory = Corpus(), args.output.with_name(ARTIFACT_DIRECTORY)
    for path in product_sources(corpus):
        importlib.import_module(path.removeprefix('src/').removesuffix('.py').replace('/', '.'))
    directory.mkdir(parents=True, exist_ok=True)
    require(not directory.is_symlink() and not any(directory.iterdir()), 'Unsafe or nonempty fixed-provider artifact directory')
    started = time.monotonic()
    receipt = {'schema_version': SCHEMA, 'status': 'running', 'scope': SCOPE, **corpus.metadata(),
        'revision': os.environ.get('GITHUB_SHA'), 'source_revision': os.environ.get('GITHUB_HEAD_SHA', os.environ.get('GITHUB_SHA')),
        'run_id': os.environ.get('GITHUB_RUN_ID'), 'python_version': platform.python_version(), 'system': platform.system(),
        'machine': platform.machine(), 'native_platform': args.platform, 'package_path': str(Path(biocompiler.__file__).resolve()),
        'checks': [], 'artifacts': {}, 'artifact_directory': ARTIFACT_DIRECTORY, '_artifact_directory': str(directory)}
    code = 1
    try:
        require(not Path.cwd().resolve().is_relative_to(ROOT), 'Run installed fixed-provider campaign outside checkout')
        require(receipt['run_id'] and receipt['source_revision']
            and (platform.system(), platform.machine()) == r.PLATFORMS[args.platform], 'Missing or mismatched hosted fixed-provider authority')
        installed_modules()
        native = r.verify_binaries(args.native_root, receipt['revision'], args.platform)
        receipt['native_inputs'], receipt['executables'] = native, {}
        for role in ('core', 'verify'):
            path, pin = getattr(args, role), getattr(args, role+'_sha256')
            require(path.is_absolute() and path.resolve() == (args.native_root / ('biocompiler-'+role)).resolve()
                and not path.is_symlink() and os.access(path, os.X_OK) and pin == native['sha256'][path.name], 'Unbound fixed-provider binary')
            receipt['executables'][role] = str(path)
        receipt['python_sources'] = product_sources(corpus)
        for relative, pin in receipt['python_sources'].items():
            name = relative.removeprefix('src/').removesuffix('.py').replace('/', '.')
            require(sha(r.raw_file(Path(sys.modules[name].__file__))) == pin, 'Installed fixed-provider source differs: '+name)
        receipt['campaign_sources'] = r.source_pins(SOURCES)
        client = CoreClient(args.core, role='core', expected_sha256=args.core_sha256, timeout_seconds=300)
        manager.verify_rejection(args.verify, args.verify_sha256, receipt)
        campaign(client, corpus, receipt)
        receipt['completed_checks'] = len(receipt['checks'])
        validate_checks(receipt, corpus, Artifacts(directory, receipt['artifacts']))
        equal(r.verify_binaries(args.native_root, receipt['revision'], args.platform), native, 'Fixed-provider binaries changed during execution')
        receipt['status'], code = 'success', 0
    except Exception as error:
        receipt['status'], receipt['error'] = 'failure', type(error).__name__+': '+str(error)
        print(receipt['error'], file=sys.stderr)
    receipt['completed_checks'], receipt['duration_seconds'] = len(receipt['checks']), round(time.monotonic()-started, 6)
    del receipt['_artifact_directory']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(receipt)+b'\n')
    print('Installed fixed-provider views:', receipt['status'], receipt['completed_checks'], 'cases, 9 providers, 18 returns')
    return code


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    if '--compare' not in arguments:
        return campaign_main(arguments)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compare', required=True, action='store_true')
    for name in ('root', 'native-root', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args(arguments)
    result = compare(args.root, args.native_root, revision=os.environ.get('GITHUB_SHA'),
        source_revision=os.environ.get('GITHUB_HEAD_SHA', os.environ.get('GITHUB_SHA')), run_id=os.environ.get('GITHUB_RUN_ID'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result)+b'\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
