"""Independent source relocation and unchanged artificial RNA material premises.

No native evaluator, compiler result, or accepted linkage is used as an oracle.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from biocompiler import policy as p
from biocompiler.policy import modules as mod, module_linking as ml

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'core/test/data/policy_module_linking_v01.json'
SEED = ROOT / 'core/test/data/policy_finite_machine_v01.json'
RELOCATIONS = {'condition': 'sense/condition', 'machine': 'control/machine',
    'launch': 'control/launch', 'complete': 'control/complete', 'retry_failure': 'control/retry_failure',
    'retry_timeout': 'control/retry_timeout', 'response': 'actuator/response',
    'response_initiation': 'actuator/response_initiation'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def original_bundle(program):
    source = p.from_data(program, p.PolicyProgram)
    rows = {row.id: row for row in source.declarations}
    context_ids = ('executor', 'encounter/target', 'encounter', 'clock', 'product')
    context_rows = tuple(rows[key] for key in context_ids)
    spans = {row.declaration_id: row for row in source.source_map}
    context = p.PolicyProgram('module_retry', source.semantics, context_rows, tuple(spans[key] for key in context_ids))
    ports = tuple(mod.InputPort('subject' if key == 'encounter/target' else key, rows[key],
        'read' if key == 'product' else 'context') for key in context_ids)
    bindings = tuple(mod.ModuleBinding(port.name, p.ref(port.declaration)) for port in ports)
    sensor = mod.ModuleTemplate('sensor', '1', source.semantics, ports,
        (mod.OutputPort('condition', rows['condition'], 'read'),), (rows['condition'],),
        source_map=(spans['condition'],))
    control_ids = ('machine', 'launch', 'complete', 'retry_failure', 'retry_timeout')
    controller = mod.ModuleTemplate('controller', '1', source.semantics,
        ports + (mod.InputPort('condition', rows['condition'], 'read'), mod.InputPort('response', rows['response'], 'request')),
        (), tuple(rows[key] for key in control_ids), private=(p.ref(rows['machine']),),
        source_map=tuple(spans[key] for key in control_ids))
    effector = mod.ModuleTemplate('effector', '1', source.semantics, ports,
        (mod.OutputPort('response', rows['response'], 'request'),), (rows['response'],),
        guarantees=(rows['response_initiation'],), source_map=(spans['response'], spans['response_initiation']))
    return ml.ModuleBundle(context, (mod.instantiate(sensor, 'sense', bindings=bindings),
        mod.instantiate(controller, 'control', bindings=bindings + (
            mod.ModuleBinding('condition', mod.ModuleOutput('sense', 'condition')),
            mod.ModuleBinding('response', mod.ModuleOutput('actuator', 'response')))),
        mod.instantiate(effector, 'actuator', bindings=bindings)))


def literal_program(program):
    """Explicit fixture oracle: only source references/owned IDs are relocated."""
    def relocate(value):
        if type(value) is list:
            return [relocate(item) for item in value]
        if type(value) is not dict:
            return value
        result = {key: relocate(item) for key, item in value.items()}
        if result.get('$type') == 'Ref':
            result['id'] = RELOCATIONS.get(result['id'], result['id'])
        elif result.get('$type') == 'SourceSpan':
            result['declaration_id'] = RELOCATIONS.get(result['declaration_id'], result['declaration_id'])
        return result
    source = relocate(program)
    rows = {row['id']: row for row in source['declarations']}
    order = ('executor', 'encounter/target', 'encounter', 'clock', 'product', 'condition',
        'machine', 'launch', 'complete', 'retry_failure', 'retry_timeout', 'response', 'response_initiation')
    source['id'] = 'module_retry'
    source['declarations'] = []
    for key in order:
        row = rows[key]
        row['id'] = RELOCATIONS.get(key, key)
        source['declarations'].append(row)
    spans = {row['declaration_id']: row for row in source['source_map']}
    source['source_map'] = [spans[RELOCATIONS.get(key, key)] for key in order]
    return source


def build():
    seed = json.loads(SEED.read_text())
    case = seed['cases'][0]
    request = deepcopy(case['request'])
    original = request['implementation_request']
    old_program = deepcopy(original['document']['program'])
    modules = original_bundle(old_program).to_data()
    program = literal_program(old_program)
    original['document']['program'] = deepcopy(program)
    original['document']['assurance']['requirements'] = ['actuator/response_initiation']
    domain = original['operating_domain']
    for key in ('fixed_observations', 'observation_factors'):
        for row in domain[key]:
            row['observation'] = 'sense/condition'
    for row in domain['feedback_factors']:
        row['effect'] = 'actuator/response'
    context = request['context']
    context['record_layout']['domain_digest'] = digest(domain)
    layout_digest = digest(context['record_layout'])
    for row in context['providers']:
        body = row['body']
        if body['kind'] == 'environment':
            body['grammar'] = deepcopy(domain)
        for channel in body.get('channels', []):
            if channel.get('source') in RELOCATIONS:
                channel['source'] = RELOCATIONS[channel['source']]
        for capacity in body.get('capacities', []):
            capacity['record_layout_digest'] = layout_digest
        row['identity']['content_fingerprint'] = digest(body)
    for row in request['input_bindings']:
        if row['source'] in RELOCATIONS:
            row['source'] = RELOCATIONS[row['source']]
    expected = deepcopy(case['expected'])
    expected['program'] = deepcopy(program)
    return {'schema_version': 'biocompiler.policy_module_linking_fixture.v0.1',
        'notice': 'Artificial supplied software premises only. Native validation pending; no empirical claim.',
        'seed_sha256': hashlib.sha256(SEED.read_bytes()).hexdigest(), 'modules': modules,
        'program': program, 'request': request, 'limits': deepcopy(seed['limits']), 'expected': expected}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    arguments = parser.parse_args()
    content = json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=False) + '\n'
    if arguments.check:
        if PATH.read_text() != content:
            raise SystemExit('Module-linking fixture drift')
    else:
        PATH.write_text(content)


if __name__ == '__main__':
    main()
