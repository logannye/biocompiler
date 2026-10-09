"""Artificial partitioned reservoir components with explicit supplied Boolean coupling.

The 24 expected flow rows and schedule come from the separately written network
literal oracle. No native compiler, runtime or checker is executed here.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from biocompiler import policy as p
from tools import generate_policy_quantitative_network_fixture as network

shared, finite = network.shared, network.finite
ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'core/test/data/policy_quantitative_composition_v01.json'
PROFILE = 'biocompiler.policy_coupled_transfer_network_component_mrna.v0.1'
SLOTS = ('control', 'owner_a', 'owner_b', 'owner_c')
FEATURES = ('utr5', 'cds', 'utr3', 'poly_a')
SEQUENCES = ('CC', 'AUGGCUUAA', 'GG', 'AAAA')


def source():
    original = network.build()['request']['implementation_request']
    document = p.from_data(original['document'], p.BuildRequest)
    machine = next(r for r in document.program.declarations if isinstance(r, p.Machine))
    observation = next(r for r in document.program.declarations if isinstance(r, p.Observation))
    stores = tuple(p.StateStore('amount_' + name, p.TRUTH, machine.scope, initial, 2, 'reject', 'encounter', None, 'not_applicable')
                   for name, initial in (('a', True), ('b', True), ('c', False)))
    a, b, c = (r.expression for r in stores)
    # Explicit independent source equations. No law evaluator generates these.
    sense = observation.expression
    ab = p.all_of(sense, a, p.not_(b))
    bc = p.all_of(sense, b, p.not_(c))
    ac = p.all_of(sense, a, p.not_(c), p.not_(p.any_of(ab, bc)))
    ba = p.all_of(p.not_(sense), b, p.not_(a), p.not_(p.any_of(bc)))
    ca = p.all_of(p.not_(sense), c, p.not_(a), p.not_(p.any_of(ba)))
    nexts = (p.any_of(p.all_of(a, p.not_(p.any_of(ab, ac))), ba, ca),
             p.any_of(p.all_of(b, p.not_(p.any_of(bc, ba))), ab),
             p.any_of(p.all_of(c, p.not_(p.any_of(ca))), bc, ac))
    assignments = tuple(p.Assignment(p.ref(store), value) for store, value in zip(stores, nexts))
    declarations = tuple(r for r in document.program.declarations if not isinstance(r, p.Transition)) + stores + tuple(
        replace(r, assignments=assignments) for r in document.program.declarations if isinstance(r, p.Transition))
    document = replace(document, program=replace(document.program, id='coupled_binary_reservoirs', declarations=declarations,
        source_map=tuple(p.SourceSpan(row.id, 'coupled_binary_reservoirs.py', i + 1) for i, row in enumerate(declarations))))
    original.update(schema_version='biocompiler.policy_realization_request.v0.8',
                    profile='biocompiler.policy_coupled_state_inputs.v0.1', document=p.to_data(document))
    return original, stores, (ab, bc, ac, ba, ca), nexts


def graph(original, stores, flow_exprs, next_exprs):
    models, nodes, wires, memo = {}, {}, [], {}
    transitions = [r for r in original['document']['program']['declarations'] if r['$type'] == 'Transition']
    def add(slot, identity, primitive, configuration, executor=False):
        key = shared.digest([primitive, configuration, executor])
        if key not in models:
            model = shared.model('coupled.' + str(len(models)), primitive, configuration, executor=executor)
            if primitive == 'attempt_bank_sites':
                model['body']['profile'] = network.PRIMITIVE
                model['identity']['content_fingerprint'] = shared.digest(model['body'])
            models[key] = model
        node = {'id': identity, 'model': deepcopy(models[key])}
        nodes[(slot, identity)] = node
        return slot, identity
    def ep(node, port): return node[0], node[1], port
    def connect(producer, consumer): wires.append((producer, consumer))
    evidence = add('control', 'evidence', 'evidence_bank', {'freshness_ticks': 1})
    machine = add('control', 'machine', 'machine_bank', {'states': network.STATES, 'initial': 'q110', 'terminal': [], 'writers': len(transitions), 'retained_capacity': 1})
    arbiter = add('control', 'arbiter', 'exclusive_arbiter', {'lanes': len(transitions)})
    registers = {store.id: add('owner_' + name, 'amount', 'truth_register', {'initial': 'true' if store.initial else 'false', 'writers': len(transitions)})
                 for name, store in zip(('a', 'b', 'c'), stores)}
    attempt = add('owner_a', 'response', 'attempt_bank_sites', {'sites': 2, 'capacity': 6, 'timeout_ticks': 2,
                  'authorization': 'continuous', 'on_loss': 'continue', 'on_unknown': 'defer'})
    product = add('owner_a', 'product', 'product_constant', {'product': 'fixture.product.alpha'}, True)
    def emit(expr, slot):
        raw = p.to_data(expr) if isinstance(expr, p.Expr) else expr
        key = shared.digest(raw)
        if key in memo: return memo[key]
        if raw['op'] == 'state': result = ep(registers[raw['ref']['id']], 'value')
        elif raw['op'] == 'observe': result = ep(evidence, 'value')
        elif raw['op'] == 'not':
            child = emit(raw['args'][0], slot)
            node = add(slot, 'expr' + str(len(memo)), 'truth_not', {})
            connect(child, ep(node, 'in')); result = ep(node, 'out')
        elif raw['op'] in ('all', 'any'):
            children = [emit(arg, slot) for arg in raw['args']]
            node = add(slot, 'expr' + str(len(memo)), 'truth_' + raw['op'], {'arity': len(children)})
            for index, child in enumerate(children): connect(child, ep(node, 'in' + str(index)))
            result = ep(node, 'out')
        else: raise AssertionError(raw['op'])
        memo[key] = result
        return result
    flows = [emit(expr, 'control') for expr in flow_exprs]
    nexts = [emit(expr, 'owner_' + name) for name, expr in zip(('a','b','c'), next_exprs)]
    request_index = 0
    for index, transition in enumerate(transitions):
        gate = add('control', f'gate{index}', 'transition_gate', {'source': transition['source'], 'correlation': 'unbound'})
        commit = add('control', f'commit{index}', 'transition_commit', {'destination': transition['destination'], 'writes': 3, 'requests': int(bool(transition['effects']))})
        guard = emit(transition['when'], 'control')
        for producer, consumer in ((ep(machine,'snapshot'), ep(gate,'machine')), (ep(evidence,'updated'),ep(gate,'on')),
                                  (guard,ep(gate,'guard')), (ep(gate,'candidate'),ep(arbiter,f'in{index}')),
                                  (ep(arbiter,f'out{index}'),ep(commit,'grant')), (ep(commit,'machine_write'),ep(machine,f'write{index}'))):
            connect(producer, consumer)
        for ordinal, (store, value) in enumerate(zip(stores, nexts)):
            connect(value, ep(commit, f'value{ordinal}'))
            connect(ep(commit,f'write{ordinal}'), ep(registers[store.id],f'write{index}'))
        if transition['effects']:
            connect(ep(product,'out'),ep(commit,'product0'))
            connect(ep(commit,'request0'),ep(attempt,f'request{request_index}'))
            connect(guard,ep(attempt,f'authorization{request_index}'));request_index += 1
    def ports(node):
        prim, config = node['model']['body']['primitive'], node['model']['body']['configuration']
        if prim == 'truth_register': return ['value']
        if prim in ('truth_not','truth_all','truth_any'): return ['out']
        if prim == 'attempt_bank_sites': return ['events','snapshot']
        if prim == 'transition_commit': return [f'write{i}' for i in range(config['writes'])] + [f'request{i}' for i in range(config['requests'])] + ['machine_write']
        return shared.output_ports(node['model'])
    fragments = {slot: {'schema_version':'biocompiler.policy_component_fragment.v0.1', 'profile':'biocompiler.policy_multi_site_fragment.v0.1',
        'primitive_profile':network.PRIMITIVE,'observable_profile':network.OBSERVABLE,'phase_profile':network.PHASE,
        'id':'coupled.'+slot,'version':'1','slot_layout':{'id':'encounters','slots':2},
        'nodes':[node for (owner,_),node in nodes.items() if owner==slot], 'wires':[], 'boundary_ports':[], 'external_slots':[], 'atomic_groups':[], 'semantic_exports':[]}
        for slot in SLOTS}
    fragments['control']['external_slots']=[{'id':'condition','kind':'evidence','consumer':shared.endpoint('evidence','samples')}]
    fragments['owner_a']['external_slots']=[{'id':'response_feedback','kind':'feedback','consumer':shared.endpoint('response','feedback')}]
    fragments['control']['atomic_groups']=[{'id':'selection','arbiter':'arbiter','commits':[f'commit{i}'for i in range(len(transitions))]}]
    boundaries, links = {}, []
    def boundary(endpoint,direction,signal):
        if endpoint not in boundaries:
            slot,node,port=endpoint;identity=('out/' if direction=='output' else 'in/')+node+'/'+port
            fragments[slot]['boundary_ports'].append(shared.boundary(identity,direction,signal,node,port));boundaries[endpoint]=identity
        return {'slot':endpoint[0],'boundary':boundaries[endpoint]}
    for producer, consumer in wires:
        if producer[0] == consumer[0]: fragments[producer[0]]['wires'].append(shared.wire(*producer[1:], *consumer[1:]));continue
        signal = ('truth_write' if producer[2].startswith('write') else 'effect_request' if producer[2].startswith('request') else
                  'product_symbol' if producer[1]=='product' else 'truth_value')
        links.append({'id':f'coupling{len(links)}','producer':boundary(producer,'output',signal),'consumer':boundary(consumer,'input',signal),
                      'signal_type':signal,'scope':'immutable_executor_broadcast' if signal=='product_symbol' else 'same_encounter_slot'})
    for fragment in fragments.values(): fragment['semantic_exports']=[shared.endpoint(node['id'],port)for node in fragment['nodes'] for port in ports(node)]
    assert len(nodes)<=64
    library={'schema_version':'biocompiler.policy_implementation_library.v0.1','profile':network.PRIMITIVE,
             'id':'coupled.supplied.library','version':'1','models':list(models.values())}
    return library,fragments,links,boundaries,flows,nexts


def material_roots(seed):
    result={}
    originals={f['id']:f for root in seed['roots'].values()for f in root['molecule']['features']}
    for slot,feature,sequence in zip(SLOTS,FEATURES,SEQUENCES):
        root=deepcopy(seed['roots']['decision']);identity='coupled.'+slot;space=identity+'.frame'
        root['id']=identity;mol=root['molecule'];mol.update(id=identity+'.molecule',sequence=sequence,coding_status='coding' if feature=='cds' else 'noncoding')
        mol['space'].update(id=space,length=len(sequence))
        path=deepcopy(originals[feature]['path']);path.update(space_id=space);path['spans'][0].update(start=0,end=len(sequence))
        f=deepcopy(originals[feature]);f['path']=deepcopy(path);mol['features']=[f]
        origin=mol['assembly'][0];origin.update(id=identity+'.self',source_space=deepcopy(mol['space']),source_path=deepcopy(path),destination=deepcopy(path))
        if feature=='poly_a':
            mol['chemistry']['terminal_tail']=deepcopy(seed['roots']['driver']['molecule']['chemistry']['terminal_tail'])
            mol['chemistry']['terminal_tail']['path']=deepcopy(path)
        result[slot]=root
    return result


def build():
    prior=network.build();original,stores,flow_exprs,next_exprs=source()
    library,fragments,links,boundaries,flows,nexts=graph(original,stores,flow_exprs,next_exprs)
    original['implementation_library']=library
    original['catalog_bindings'][0]['models']=[m['identity']for m in library['models']]
    seed=json.loads((shared.DATA/'policy_staged_material_seed_v01.json').read_text())
    roots=material_roots(seed);components={}
    for slot,feature in zip(SLOTS,FEATURES):
        component=shared.component('decision',fragments[slot],seed)
        component.update(schema_version='biocompiler.policy_component_material.v0.6',profile='biocompiler.policy_coupled_quantitative_local_material.v0.1')
        body=component['body'];body['root']=roots[slot]
        site={'root':roots[slot]['id'],'feature':feature,'path':roots[slot]['molecule']['features'][0]['path']}
        for carrier in body['carriers']:carrier['sites']=[deepcopy(site)]
        if slot=='owner_a':
            product=deepcopy(seed['products'][0]);product['root']=roots[slot]['id'];body['products']=[product]
        for node in fragments[slot]['nodes']:
            primitive=node['model']['body']['primitive']
            if primitive=='truth_register':
                body['provider_requirements'].append({'kind':'capacity','id':'amount.truth_cells.per_encounter_slot','owner':{'kind':'node','id':'amount'},
                    'unit':'truth_cells','scope':'per_encounter_slot','minimum':1})
            if primitive=='attempt_bank_sites':
                for unit,scope,n in (('active_attempt_records','per_encounter_slot',6),('retained_correlation_records','per_executor',1),('timer_cells','per_encounter_slot',6)):
                    body['provider_requirements'].append({'kind':'capacity','id':'response.'+unit+'.'+scope,'owner':{'kind':'node','id':'response'},'unit':unit,'scope':scope,'minimum':n})
        local={node['id']:node['model']['identity']for node in fragments[slot]['nodes']}
        if slot=='control':
            oldlocal=deepcopy(prior['request']['component_library']['components'][0]['body']['quantitative_contracts'][0])
            oldlocal['state']['model']=local['machine'];oldlocal['input']['model']=local['evidence']
            for index,output in zip((4,5),oldlocal['outputs']):
                output.update(boundary=boundaries[('control',f'commit{index}','request0')],model=local[f'commit{index}'])
            contract={'role':'coordinator','id':'network','network':oldlocal,'flows':[
                {'transfer':identity,'boundary':boundaries[endpoint],'model':local[endpoint[1]]}for identity,endpoint in zip(network.EDGE_IDS,flows)]}
        else:
            name=slot[-1];coordinate=('a','b','c').index(name);next_ep=nexts[coordinate]
            incident=[]
            for edge,flow in zip(network.law()['transfers'],flows):
                if name not in (edge['source'],edge['destination']):continue
                matches=[link['consumer']['boundary']for link in links if link['producer']=={'slot':'control','boundary':boundaries[flow]} and link['consumer']['slot']==slot]
                assert len(matches)==1,(edge,matches)
                incident.append({'transfer':edge['id'],'boundary':matches[0]})
            contract={'role':'owner','id':'reservoir_'+name,'compartment':name,'state':{'node':'amount','model':local['amount']},
                'snapshot_boundary':boundaries[(slot,'amount','value')], 'next':{'boundary':boundaries[next_ep],'model':local[next_ep[1]]},
                'writes':[{'transition':r[0],'boundary':boundaries[(slot,'amount',f'write{i}')]}for i,r in enumerate(network.SPEC['transitions'])], 'flows':incident}
        body['quantitative_contracts']=[contract];component['identity']=shared.pin('model','coupled.'+slot,body);components[slot]=component
    # Assemble the same exact four literal regions from four selected roots.
    authority=deepcopy(seed['material_authority']);template=authority['template'];template['id']='coupled.payload'
    template['sources']=sorted(deepcopy(list(roots.values())),key=lambda r:r['id'])
    step=template['steps'][0];choice=step['operation']['inputs'][0]
    step['operation']['inputs']=[{**deepcopy(choice),'value':{**deepcopy(choice['value']),'id':roots[slot]['id']}}for slot in SLOTS]
    port=step['ports'][0];old_dispositions=port['feature_transition']['dispositions'];old_chem=port['chemistry_transition']['dispositions']
    dispositions=[];chem=[]
    qualified={feature:json.dumps([slot,feature],separators=(',',':'))for slot,feature in zip(SLOTS,FEATURES)}
    for slot,feature in zip(SLOTS,FEATURES):
        disposition=deepcopy(next(d for d in old_dispositions if d['feature_id']==feature));disposition['source_id']=roots[slot]['id']
        for output in disposition['outputs']:output['id']=qualified[feature]
        dispositions.append(disposition)
        for facet in ('cap','start_end','finish_end','terminal_tail','modification_inventory'):
            wanted='leader_A' if slot=='control' else 'driver_body'
            d=deepcopy(next(d for d in old_chem if d['source_id']==wanted and d['component']==facet));d['source_id']=roots[slot]['id']
            carry=facet=='modification_inventory' or slot=='control' and facet in ('cap','start_end') or slot=='owner_c' and facet in ('finish_end','terminal_tail')
            d.update(decision='mapped_copy'if carry else 'not_carried',destination_components=[facet]if carry else []);chem.append(d)
    port['feature_transition']['dispositions']=sorted(dispositions,key=lambda row:(row['source_id'],row['feature_id']))
    # These inventories have canonical identity order in the typed material IR.
    port['chemistry_transition']['dispositions']=sorted(chem,key=lambda row:(row['source_id'],row['component']))
    for member in authority['members']:member['regions']={key:qualified[value]for key,value in member['regions'].items()}
    for structure in template['payload_structures']:
        for region in structure['regions']:region['feature_id']=qualified[region['feature_id']]
        structure['regions'].sort(key=lambda row:row['feature_id'])
    joins=[{'id':f'join{i}','step':'join','port':'joined','left':left,'right':right,'offset':sum(map(len,SEQUENCES[:i+1]))}
           for i,(left,right)in enumerate(zip(SLOTS,SLOTS[1:]))]
    body={'primitive_profile':network.PRIMITIVE,'observable_profile':network.OBSERVABLE,'phase_profile':network.PHASE,
        'transport_profile':'biocompiler.policy_identity_transport.v0.1','slot_layout':{'id':'encounters','slots':2},
        'components':[{'slot':slot,'component':c['identity']}for slot,c in components.items()],'links':links,
        'node_order':[{'slot':slot,'node':n['id']}for slot,f in fragments.items()for n in f['nodes']],
        'wire_order':[{'kind':'local','slot':slot,'index':i}for slot,f in fragments.items()for i in range(len(f['wires']))]+[{'kind':'link','id':l['id']}for l in links],
        'input_order':[{'slot':slot,'external_slot':r['id'],'id':r['id']}for slot,f in fragments.items()for r in f['external_slots']],
        'group_order':[{'slot':'control','group':'selection'}], 'export_order':[{'slot':slot,**r}for slot,f in fragments.items()for r in f['semantic_exports']],
        'root_bindings':[{'slot':slot,'source':root['id']}for slot,root in roots.items()], 'joins':joins,
        'link_carriers':[{'link':l['id'],'producer_site':0,'consumer_site':0,'joins':[j['id']for j in joins[min(SLOTS.index(l['producer']['slot']),SLOTS.index(l['consumer']['slot'])):max(SLOTS.index(l['producer']['slot']),SLOTS.index(l['consumer']['slot']))]]}for l in links],
        'material_authority':authority}
    rule={'schema_version':'biocompiler.policy_component_assembly_rule.v0.5','profile':'biocompiler.policy_multi_site_component_assembly.v0.1',
          'identity':shared.pin('model','coupled.assembly',body),'body':body}
    def resolve(ref):return {'slot':ref['slot'],**next(b['endpoint']for b in fragments[ref['slot']]['boundary_ports']if b['id']==ref['boundary'])}
    union={'schema_version':'biocompiler.policy_instance_ordered_union.v0.1',**{k:deepcopy(body[k])for k in ('primitive_profile','observable_profile','phase_profile','transport_profile','slot_layout','links')},
        'nodes':[{'slot':slot,'node':n['id'],'model':n['model']}for slot,f in fragments.items()for n in f['nodes']],
        'wires':[{'producer':{'slot':slot,**w['producer']},'consumer':{'slot':slot,**w['consumer']}}for slot,f in fragments.items()for w in f['wires']]+[{k:resolve(l[k])for k in ('producer','consumer')}for l in links],
        'inputs':[{'id':r['id'],'kind':r['kind'],'consumer':{'slot':slot,**r['consumer']}}for slot,f in fragments.items()for r in f['external_slots']],
        'atomic_groups':[{'slot':'control','id':'selection','arbiter':{'slot':'control','node':'arbiter'},'commits':[{'slot':'control','node':f'commit{i}'}for i in range(7)]}], 'semantic_exports':body['export_order']}
    context,inputs,resources=finite.context(network.SPEC,original,components,rule,union)
    context['record_layout'].update(horizon_ticks=12,maximum_tick=14,attempts=6)
    def extend(value):
        if isinstance(value,dict):
            if 'duration_min'in value:value.update(duration_min='12',duration_max='12')
            for child in value.values():extend(child)
        elif isinstance(value,list):
            for child in value:extend(child)
    for provider in context['providers']:
        extend(provider['body'])
        for capacity in provider['body']['capacities']:
            capacity['record_layout_digest']=shared.digest(context['record_layout'])
            if capacity['unit']=='evidence_records':capacity['quantity']=13
        provider['identity']['content_fingerprint']=shared.digest(provider['body'])
    bridge=original['catalog_bindings'][0]
    selected=deepcopy(prior['request']['quantitative']);selected['selection']['component']=components['control']['identity']
    request={'schema_version':'biocompiler.policy_component_material_request.v0.13','profile':PROFILE,'implementation_request':original,
        'component_library':{'schema_version':'biocompiler.policy_component_library.v0.1','profile':'biocompiler.policy_exact_component_library.v0.1','components':list(components.values())},
        'composition_rule':rule,'catalog_binding':{**{k:bridge[k]for k in ('entry_id','entry_version','entry_digest','operation','realization')},'components':body['components'],'rule':rule['identity']},
        'input_bindings':inputs,'resource_bindings':resources,'context':context,'budgets':deepcopy(prior['request']['budgets']),
        'quantitative':{'network':selected,'owners':[{'instance':slot,'component':components[slot]['identity'],'contract':'reservoir_'+slot[-1],'compartment':slot[-1],'state':'amount_'+slot[-1]}for slot in SLOTS[1:]],'synchronization':'one_prestate_one_atomic_commit'}}
    expected=deepcopy(prior['expected']);expected.update(ordered_union=union,sequence=''.join(SEQUENCES),owner_count=3,
        node_count=len(union['nodes']),component_sequences=list(SEQUENCES))
    # Molecular expected identity is compared by sequence and exact source-derived
    # construction checks; the prior two-root assembly record is not reused.
    expected.pop('molecule')
    # The hosted coupled check exhausted the inherited 1M monitor allowance
    # while hashing its complete checked binding, before the first transition.
    # Retain that exact invocation as an incomplete/no-export control. Only
    # this fixture's allowance changes, within the unchanged public 10M cap.
    limits=deepcopy(prior['limits'])
    expected['insufficient_monitor']={'request_fingerprint':shared.digest(request),
        'limits':deepcopy(limits),'status':'incomplete','transitions':0,
        'diagnostic':'policy_requirement_monitor_work_limit',
        'export_diagnostic':'policy_quantitative_assurance_export_not_accepted'}
    limits['monitor']['max_work']=5_000_000
    return {'schema_version':'biocompiler.policy_quantitative_composition_literals.v0.1','notice':__doc__,
            'request':request,'limits':limits,'expected':expected}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    text=json.dumps(build(),sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n'
    assert len(text.encode())<2_000_000
    if args.check:assert PATH.read_text()==text,'Review changed coupled original authority'
    else:PATH.write_text(text)

if __name__=='__main__':main()
