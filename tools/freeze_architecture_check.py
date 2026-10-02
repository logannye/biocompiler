"""Retain full architecture authority and fresh checker reports using test-only deltas.

Every retained case resolves to complete independently bounded JSON. Deltas are
one-level storage compression only; no product protocol or checker accepts them.
Full records retain pretty JSON; delta files use compact canonical JSON spelling.
The generator runs existing Python assertions and all thirteen installed API
fixtures. PYTHONHASHSEED=0 freezes legacy set-derived diagnostic ordering.
"""
from __future__ import annotations
import argparse
from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import biocompiler as bc
from biocompiler.ir.serialization import fingerprint, parse_json
from biocompiler.ir.architecture_build import PayloadArchitectureRequest
from biocompiler.ir.architecture_build import PayloadArchitectureBuild
from biocompiler.verification.payload_architecture import PayloadArchitectureVerification

ROOT=Path(__file__).resolve().parents[1]
CORPUS=ROOT/'tests/conformance/architecture-check-v1.json'
DOCUMENTS=CORPUS.with_suffix('')
SCHEMA='biocompiler.architecture_check_conformance.v1'
DELTA_SCHEMA='biocompiler.test_document_delta.v1'
CLASSES={'request':PayloadArchitectureRequest,'build':PayloadArchitectureBuild,'assessment':PayloadArchitectureVerification}
MODULES=(('test_payload_architecture_verification','PayloadArchitectureVerificationTests'),
 ('test_payload_architecture','PayloadArchitectureTests'),
 ('test_architecture_match_verification','IndependentMatchTests'),
 ('test_architecture_control_pipeline','ArchitectureControlPipelineTests'),
 ('test_architecture_control_causality','ArchitectureChannelControlCausalityTests'),
 ('test_architecture_deployment','DeploymentWindowTests'))
ORDER_SITES={
 '_refinement_checks.owned':'executable_material_model_missing:',
 '_refinement_checks.binding_roles':'material_recipient_missing:',
 '_refinement_checks.controlled_actions':'activity_control_not_realized:',
 '_delivery_dependency_checks.component_placements':'helper_',
}
MAX_STORED_BYTES=16*1024*1024
MAX_RESOLVED_BYTES=512*1024*1024
MAX_CASES=2048

def require(condition,message):
    if not condition:raise AssertionError(message)
def encoded(raw):return (json.dumps(raw,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
def canonical(raw):return json.dumps(raw,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def stored_encoded(raw,format_):return encoded(raw) if format_=='full' else (canonical(raw)+'\n').encode()
def inventory(index):return fingerprint({k:v for k,v in index.items() if k!='inventory_fingerprint'})
def bounds(raw,maximum=4_000_000,nodes=100_000,depth=96):
    pending=[(raw,0)];count=0
    while pending:
        value,level=pending.pop();count+=1
        require(count<=nodes and level<=depth,'Architecture fixture node/depth budget')
        if isinstance(value,dict):pending.extend((v,level+1) for pair in value.items() for v in pair)
        elif isinstance(value,list):pending.extend((v,level+1) for v in value)
    data=encoded(raw)
    require(len(data)<=maximum,'Architecture fixture byte budget')
    require(b'/Users/' not in data and b'/home/runner/' not in data,'Machine-specific architecture authority')
    return len(data)

def apply_edits(raw,edits):
    value=deepcopy(raw)
    for edit in edits:
        require(isinstance(edit,dict) and edit.get('op') in ('set','remove'),'Unknown delta operation')
        require(set(edit)==({'op','path','value'} if edit['op']=='set' else {'op','path'}),'Unknown delta fields')
        path=edit['path'];require(isinstance(path,list) and 0<len(path)<=96,'Invalid delta path')
        target=value
        for key in path[:-1]:
            require((isinstance(target,dict) and isinstance(key,str) and key in target) or
                    (isinstance(target,list) and type(key) is int and 0<=key<len(target)),'Missing delta descent')
            target=target[key]
        key=path[-1]
        require((isinstance(target,dict) and isinstance(key,str)) or
                (isinstance(target,list) and type(key) is int and 0<=key<len(target)),'Invalid delta terminal')
        if edit['op']=='remove':
            require(isinstance(target,dict) and key in target,'Only existing object fields may be removed')
            del target[key]
        else:target[key]=deepcopy(edit['value'])
    return value

def difference(base,wanted,path=()):
    result=None
    if type(base) is type(wanted):
        if isinstance(base,dict):
            result=[{'op':'remove','path':[*path,key]} for key in sorted(base.keys()-wanted.keys())]
            for key in sorted(wanted):
                if key not in base:result.append({'op':'set','path':[*path,key],'value':wanted[key]})
                else:result.extend(difference(base[key],wanted[key],(*path,key)))
        elif isinstance(base,list) and len(base)==len(wanted):
            result=[edit for i,(a,b) in enumerate(zip(base,wanted)) for edit in difference(a,b,(*path,i))]
        elif not isinstance(base,(dict,list)) and canonical(base)==canonical(wanted):return []
    if result is None:
        require(bool(path),'Root delta replacement is forbidden')
        return [{'op':'set','path':list(path),'value':wanted}]
    if path and len(result)>1:
        replacement=[{'op':'set','path':list(path),'value':wanted}]
        if len(encoded(replacement))<len(encoded(result)):return replacement
    return result

def resolve(index,documents,identity):
    metadata={item['id']:item for item in index['documents']}
    require(identity in metadata and identity in documents,'Missing complete document')
    descriptor=metadata[identity];stored=documents[identity]
    require(fingerprint(stored)==descriptor['stored_fingerprint'],'Stored document identity mismatch')
    bounds(stored)
    require(len(stored_encoded(stored,descriptor['format']))==descriptor['bytes'],'Stored byte census mismatch')
    if descriptor['format']=='full':
        require(descriptor['base'] is None,'Full document cannot have a baseline');raw=deepcopy(stored)
    else:
        require(descriptor['format']=='delta','Unknown test document format')
        require(isinstance(stored,dict) and set(stored)=={'schema_version','base','edits'} and stored['schema_version']==DELTA_SCHEMA,'Invalid delta schema')
        base=descriptor['base']
        require(stored['base']==base and base!=identity and base in metadata and base in documents,'Missing or cyclic delta baseline')
        baseline=metadata[base]
        require(baseline['format']=='full' and baseline['base'] is None and baseline['kind']==descriptor['kind'],'Delta baseline must be a complete same-kind document')
        require(fingerprint(documents[base])==base==baseline['stored_fingerprint'],'Invalid full baseline identity')
        require(bounds(documents[base])==baseline['bytes']==baseline['resolved_bytes'],'Invalid baseline byte census')
        raw=apply_edits(documents[base],stored['edits'])
    require(fingerprint(raw)==identity,'Resolved complete document identity mismatch')
    require(bounds(raw)==descriptor['resolved_bytes'],'Resolved document byte census mismatch')
    return raw

def native_replacements(report):
    replacements=[]
    for gap in report['diagnostics']:
        code=gap['code']
        if code.startswith('source_behavior:') or code.startswith('supplementary_source_behavior:'):
            message=code.split(':',1)[1] if code.startswith('source_behavior:') else code.split(':',2)[2]
            # These exact legacy messages are a finite compatibility ledger, not
            # fuzzy exception-string rewriting or acceptance normalization.
            mapping={
                'execution_profile: Execution profile and sampled-integration policy must match frozen source authority.':'lowering_execution_profile',
                'source_identity: The source fingerprint and program identity must match.':'lowering_source_identity',
                'complete_graph: Every source node and root must be retained in deterministic order.':'lowering_complete_graph',
                'parameter_inventory: Bindings must cover exactly the declared design parameters.':'lowering_parameter_inventory',
                'authoritative_bindings: Output bindings must exactly match the frozen input defaults and explicit overrides.':'lowering_authoritative_bindings',
                'requirements_and_lineage: All rule/state/memory requirements and ancestor source links must survive.':'lowering_requirements_and_lineage',
                'identity_binding: Contact-object correlation and cell-local state boundaries must be retained.':'lowering_identity_binding',
            }
            for label,detail,native in (
                ('operation','Operation, dependencies, role and semantic type must be preserved.','lowering_operation'),
                ('semantics','Only declared parameter binding and execution-policy normalization may change attributes.','lowering_semantics'),
                ('source','Authoring source location must be retained.','lowering_source_location')):
                if message.startswith(label+':') and message.endswith(': '+detail):
                    identity=message[len(label)+1:-len(': '+detail)]
                    require(bool(identity) and ':' not in identity,'Unclassified source identity in diagnostic')
                    mapping[message]=native
            require(message in mapping,'Unclassified native lowering diagnostic: '+code)
            prefix=code[:-len(message)]
            replacements.append({'python':code,'native':prefix+mapping[message]})
        elif code.startswith('malformed_architecture:'):
            mapping={'malformed_architecture:Implemented source requirements need supplied realizations.':'malformed_architecture:invalid_architecture_build'}
            require(code in mapping,'Unclassified native malformed diagnostic: '+code)
            replacements.append({'python':code,'native':mapping[code]})
    return replacements

def diagnostic_group(site,code):
    if site=='_refinement_checks.owned' and 'executable_material_model_missing:' in code:
        return code.split('executable_material_model_missing:',1)[0]
    if site=='_refinement_checks.binding_roles' and 'material_recipient_missing:' in code:
        return code.rsplit(':',1)[0]
    if site=='_refinement_checks.controlled_actions' and 'activity_control_not_realized:' in code:
        return code
    if site=='_delivery_dependency_checks.component_placements' and code.startswith(('helper_cross_recipient_supply:','helper_co_delivery_missing:')):
        return code.split(':',1)[1]
    return None

def diagnostic_sites(report):
    result=[]
    for site in ORDER_SITES:
        groups=Counter(diagnostic_group(site,item['code']) for item in report['diagnostics'])
        if any(key is not None and count>1 for key,count in groups.items()):result.append(site)
    return result

def normalize_diagnostic_order(report,sites):
    result=deepcopy(report)
    for site in sites:
        require(site in ORDER_SITES,'Unknown diagnostic order site')
        groups={}
        for i,item in enumerate(result['diagnostics']):
            key=diagnostic_group(site,item['code'])
            if key is not None:groups.setdefault(key,[]).append(i)
        for positions in groups.values():
            values=sorted((result['diagnostics'][i] for i in positions),key=canonical)
            for i,value in zip(positions,values):result['diagnostics'][i]=value
    return result

def build_corpus():
    require(os.environ.get('PYTHONHASHSEED')=='0','Generator requires deterministic legacy hash seed')
    for directory in (str(ROOT),str(ROOT/'tests')):
        if directory not in sys.path:sys.path.insert(0,directory)
    verifier=importlib.import_module('biocompiler.verification.payload_architecture')
    graph=importlib.import_module('biocompiler.frontend.graph')
    original=verifier.check_payload_architecture;location=graph.SourceLocation
    modules=[(importlib.import_module(name),getattr(importlib.import_module(name),cls)) for name,cls in MODULES]
    raw_documents={};kinds={};cases=[];ledger=[];counts=Counter();current=[''];force_full=set();capture_calls=0;captured_bytes=0
    def portable(file,line,function):
        path=Path(file)
        if path.is_absolute():file=path.resolve().relative_to(ROOT).as_posix()
        return location(file,line,function)
    def retain(kind,value):
        nonlocal captured_bytes
        raw=value.to_dict();identity=fingerprint(raw)
        if identity not in raw_documents:
            size=bounds(raw)
            require(captured_bytes+size<=MAX_RESOLVED_BYTES,'Complete capture aggregate byte budget')
            require(CLASSES[kind].from_dict(raw).fingerprint==identity,'Complete typed normalization drift')
            captured_bytes+=size
            raw_documents[identity]=raw;kinds[identity]=kind
        require(kinds[identity]==kind,'Conflicting complete document kind')
        return identity
    def capture(identity,request,build,report,origin):
        require(len(cases)<MAX_CASES,'Architecture case ceiling exceeded')
        case=dict(id=identity,request=retain('request',request),build=retain('build',build),assessment=retain('assessment',report),origin=origin,
                  diagnostic_order_sites=[],native_diagnostic_replacements=[])
        cases.append(case);return case
    def checker(build,*,expected_request):
        nonlocal capture_calls
        result=original(build,expected_request=expected_request)
        number=counts[current[0]];counts[current[0]]+=1;capture_calls+=1
        capture(current[0]+'/'+str(number),expected_request,build,result,'existing_python_assertion')
        return result
    with ExitStack() as stack:
        stack.enter_context(patch.object(graph,'SourceLocation',portable))
        stack.enter_context(patch.object(verifier,'check_payload_architecture',checker))
        stack.enter_context(patch.object(verifier,'check_payload_architecture_build',checker))
        stack.enter_context(patch.object(bc,'check_payload_architecture',checker))
        for module,_ in modules:
            if hasattr(module,'check_payload_architecture'):stack.enter_context(patch.object(module,'check_payload_architecture',checker))
            for item in vars(module).values():
                if callable(getattr(item,'cache_clear',None)):item.cache_clear()
        for module,cls in modules:
            label=module.__name__+'.'+cls.__name__
            current[0]=label+'.setUpClass';cls.setUpClass()
            ledger.append(dict(method=current[0],status='source_assertions_executed',retained_calls=counts[current[0]]))
            for method in sorted(name for name in dir(cls) if name.startswith('test_')):
                current[0]=label+'.'+method
                print('Running '+current[0],flush=True)
                cls(method).debug()
                ledger.append(dict(method=current[0],status='source_assertions_executed',retained_calls=counts[current[0]]))
            cls.tearDownClass()
            print('Captured '+label+': '+str(sum(item['retained_calls'] for item in ledger if item['method'].startswith(label))),flush=True)
        from examples.payload_architectures import make_architecture_request
        from examples.architecture_automation import make_automatic_case,make_automation_request
        from examples.architecture_control_designs import make_control_request
        installed=[(name,make_architecture_request(name,variants=('one_rna','many_components_one_rna','two_rna','one_rna_helper'),independent_shutdown=True) if name=='A' else make_architecture_request(name)) for name in 'ABCDEF']
        installed += [('automatic_timing',make_automation_request())]
        installed += [('automatic_'+name.lower(),make_automatic_case(name)) for name in 'BF']
        installed += [(name,make_control_request(name)) for name in ('memory_reset','state_reset','production_adjustment','activity_control')]
        installed_ids=[]
        for name,request in installed:
            current[0]='installed/'+name+'/search'
            build=bc.compile(request)
            report=original(build,expected_request=request)
            require(build.status=='compiled' and report.passed and report.translation_complete and report.construction_complete,'Installed architecture acceptance changed: '+name)
            identity='installed/'+name;capture(identity,request,build,report,'complete_installed_api_fixture');installed_ids.append(identity)
    case_b=[]
    for variant in ('base','parameter-default','parameter-override'):
        directory=ROOT/'tests/conformance/case-b'/variant
        request=PayloadArchitectureRequest.from_dict(json.loads((directory/'request.json').read_bytes()))
        build=PayloadArchitectureBuild.from_dict(json.loads((directory/'candidate.json').read_bytes()))
        case=capture('case_b/'+variant,request,build,original(build,expected_request=request),'complete_retained_case_b')
        force_full.update((case['request'],case['build']));case_b.append(case['id'])
    # Extra exact historical replay fields are independently supplied reports.
    replay=[];base=next(item for item in cases if item['id']=='case_b/base')
    for field in ('request_fingerprint','build_fingerprint'):
        raw=deepcopy(raw_documents[base['assessment']]);raw[field]='0'*64
        record=PayloadArchitectureVerification.from_dict(raw)
        replay.append(dict(id='replay/'+field,source=base['id'],assessment=retain('assessment',record),expected_code='architecture_assessment_mismatch'))
    originals=dict(raw_documents=raw_documents,kinds=kinds,cases=cases,ledger=ledger,capture_calls=capture_calls,
        force_full=sorted(force_full),installed_ids=installed_ids,case_b=case_b,replay=replay)
    checkpoint=ROOT/'generated/migration-next/architecture-check-originals.json'
    checkpoint.parent.mkdir(parents=True,exist_ok=True)
    checkpoint_data=encoded(originals)
    require(len(checkpoint_data)<=MAX_RESOLVED_BYTES,'Original capture checkpoint byte budget')
    checkpoint.write_bytes(checkpoint_data)
    return pack_corpus(originals)

def pack_corpus(originals):
    raw_documents=originals['raw_documents'];kinds=originals['kinds'];cases=deepcopy(originals['cases'])
    ledger=originals['ledger'];capture_calls=originals['capture_calls'];force_full=set(originals['force_full'])
    installed_ids=originals['installed_ids'];case_b=originals['case_b'];replay=originals['replay']
    for case in cases:
        report=raw_documents[case['assessment']]
        case['diagnostic_order_sites']=diagnostic_sites(report)
        case['native_diagnostic_replacements']=native_replacements(report)
    documents={};metadata=[];full={kind:[] for kind in CLASSES}
    order=sorted(raw_documents,key=lambda identity:(identity not in force_full,kinds[identity],identity))
    for identity in order:
        raw=raw_documents[identity];kind=kinds[identity];size=len(encoded(raw));best=None;best_size=size
        if identity not in force_full:
            for baseline in full[kind]:
                edits=difference(raw_documents[baseline],raw)
                delta=dict(schema_version=DELTA_SCHEMA,base=baseline,edits=edits)
                delta_size=len(encoded(delta))
                if delta_size<best_size:
                    try:bounds(delta)
                    except AssertionError:continue
                if delta_size<best_size:best=(baseline,delta);best_size=delta_size
        if best is None or best_size>size*0.72:
            stored=raw;format_='full';base_id=None;full[kind].append(identity)
        else:
            base_id,stored=best;format_='delta'
            require(canonical(apply_edits(raw_documents[base_id],stored['edits']))==canonical(raw),'Delta changed complete Python original')
        documents[identity]=stored
        metadata.append(dict(id=identity,kind=kind,format=format_,stored_fingerprint=fingerprint(stored),bytes=len(stored_encoded(stored,format_)),resolved_bytes=size,base=base_id))
    coverage=dict(methods=ledger,installed=installed_ids,case_b=case_b,cases=len(cases),documents=len(documents),
        captured_calls=capture_calls,replay_rejections=len(replay),outcomes=dict(sorted(Counter(raw_documents[c['assessment']]['outcome'] for c in cases).items())),
        formats=dict(sorted(Counter(item['format'] for item in metadata).items())),
        stored_document_bytes=sum(item['bytes'] for item in metadata),resolved_document_bytes=sum(item['resolved_bytes'] for item in metadata),
        diagnostic_order_sites=sorted(ORDER_SITES),diagnostic_order_cases=[c['id'] for c in cases if c['diagnostic_order_sites']],
        native_replacement_cases=[c['id'] for c in cases if c['native_diagnostic_replacements']],
        exclusions=[])
    index=dict(schema_version=SCHEMA,delta_schema=DELTA_SCHEMA,
        claim_scope='Independent software architecture correspondence under supplied contracts only; empirical behavior and human admission remain unresolved.',
        resource_limits=dict(stored_bytes=MAX_STORED_BYTES,resolved_bytes=MAX_RESOLVED_BYTES,cases=MAX_CASES,document_bytes=4_000_000,document_nodes=100_000,document_depth=96),
        documents=sorted(metadata,key=lambda item:item['id']),cases=cases,replay_rejections=replay,coverage=coverage)
    index['inventory_fingerprint']=inventory(index)
    print('Packed '+str(len(cases))+' cases / '+str(len(documents))+' documents / '+str(coverage['stored_document_bytes']+len(encoded(index)))+' stored bytes',flush=True)
    print('Storage by format/kind: '+str({(form,kind):sum(item['bytes'] for item in metadata if item['format']==form and item['kind']==kind) for form in ('full','delta') for kind in CLASSES}),flush=True)
    check_corpus(index,documents,fresh=False)
    # Explicit independent comparison to every complete original, with no cache
    # of resolved deltas in the consumer path.
    for identity,raw in raw_documents.items():require(canonical(resolve(index,documents,identity))==canonical(raw),'Retained delta differs from complete Python original')
    return index,documents

def check_corpus(index,documents,*,fresh=False):
    require(index['schema_version']==SCHEMA and index['delta_schema']==DELTA_SCHEMA,'Wrong architecture checker fixture schema')
    require(index['inventory_fingerprint']==inventory(index),'Architecture campaign inventory drift')
    bounds(index,16*1024*1024,250_000,128)
    require(index['resource_limits']==dict(stored_bytes=MAX_STORED_BYTES,resolved_bytes=MAX_RESOLVED_BYTES,cases=MAX_CASES,document_bytes=4_000_000,document_nodes=100_000,document_depth=96),'Changed campaign resource bounds')
    for item in index['documents']:
        require(set(item)=={'id','kind','format','stored_fingerprint','bytes','resolved_bytes','base'},'Unexpected document metadata fields')
        require(isinstance(item['id'],str) and len(item['id'])==64 and all(c in '0123456789abcdef' for c in item['id']),'Invalid document identity')
    declared={item['id']:item for item in index['documents']}
    require(len(declared)==len(index['documents']) and set(declared)==set(documents),'Missing/extra/duplicate architecture documents')
    require(len({case['id'] for case in index['cases']})==len(index['cases']),'Duplicate architecture case')
    require(len(index['cases'])<=MAX_CASES,'Architecture case budget')
    require(sum(item['bytes'] for item in declared.values())+len(encoded(index))<=MAX_STORED_BYTES,'Stored architecture campaign byte budget')
    require(sum(item['resolved_bytes'] for item in declared.values())<=MAX_RESOLVED_BYTES,'Resolved architecture campaign byte budget')
    referenced=set();outcomes=Counter();case_by_id={case['id']:case for case in index['cases']}
    for case in index['cases']:
        for kind in ('request','build','assessment'):
            identity=case[kind];referenced.add(identity);require(identity in declared and declared[identity]['kind']==kind,'Case document kind mismatch')
        report=resolve(index,documents,case['assessment']);outcomes[report['outcome']]+=1
        require(case['diagnostic_order_sites']==diagnostic_sites(report),'Undeclared diagnostic order exception')
        require(case['native_diagnostic_replacements']==native_replacements(report),'Undeclared native diagnostic replacement')
        if fresh:
            request=PayloadArchitectureRequest.from_dict(resolve(index,documents,case['request']))
            build=PayloadArchitectureBuild.from_dict(resolve(index,documents,case['build']))
            result=bc.check_payload_architecture(build,expected_request=request).to_dict()
            if case['diagnostic_order_sites']:
                result=normalize_diagnostic_order(result,case['diagnostic_order_sites']);report=normalize_diagnostic_order(report,case['diagnostic_order_sites'])
            require(canonical(result)==canonical(report),'Fresh full architecture report differs: '+case['id'])
    for case in index['replay_rejections']:
        require(case['source'] in case_by_id and case['expected_code']=='architecture_assessment_mismatch','Invalid replay authority')
        referenced.add(case['assessment']);require(case['assessment'] in declared and declared[case['assessment']]['kind']=='assessment','Invalid replay report kind')
        baseline=case_by_id[case['source']]
        require(case['assessment']!=baseline['assessment'],'Unchanged replay mutation')
    referenced.update(item['base'] for item in declared.values() if item['base'] is not None)
    require(referenced==set(declared),'Unused architecture fixture documents')
    coverage=index['coverage']
    require(coverage['cases']==len(index['cases']) and coverage['documents']==len(documents) and coverage['replay_rejections']==len(index['replay_rejections']),'Stale architecture case census')
    require(coverage['outcomes']==dict(sorted(outcomes.items())),'Stale architecture outcome census')
    require(coverage['formats']==dict(sorted(Counter(item['format'] for item in declared.values()).items())),'Stale storage format census')
    require(coverage['stored_document_bytes']==sum(item['bytes'] for item in declared.values()) and coverage['resolved_document_bytes']==sum(item['resolved_bytes'] for item in declared.values()),'Stale architecture byte census')
    require(coverage['diagnostic_order_sites']==sorted(ORDER_SITES) and coverage['diagnostic_order_cases']==[c['id'] for c in index['cases'] if c['diagnostic_order_sites']] and coverage['native_replacement_cases']==[c['id'] for c in index['cases'] if c['native_diagnostic_replacements']],'Stale architecture diagnostic census')
    require(len(coverage['installed'])==13 and len(coverage['case_b'])==3,'Missing complete vertical authorities')
    for identity in (*coverage['installed'],*coverage['case_b']):require(identity in case_by_id,'Missing required vertical case')
    for identity in coverage['case_b']:
        require(all(declared[case_by_id[identity][key]]['format']=='full' for key in ('request','build')),'Case B original authority must remain complete')
    require(len(coverage['methods'])==84 and all(item['status']=='source_assertions_executed' for item in coverage['methods']) and coverage['exclusions']==[],'Incomplete original assertion campaign')
    require(sum(item['retained_calls'] for item in coverage['methods'])<=coverage['captured_calls'],'Invalid capture call census')
    if str(ROOT/'tests') not in sys.path:sys.path.insert(0,str(ROOT/'tests'))
    expected_methods=[]
    for name,class_name in MODULES:
        module=importlib.import_module(name);cls=getattr(module,class_name);prefix=name+'.'+class_name+'.'
        expected_methods.append(prefix+'setUpClass')
        expected_methods.extend(prefix+name for name in sorted(dir(cls)) if name.startswith('test_'))
    require([item['method'] for item in coverage['methods']]==expected_methods,'Changed original method inventory')
    require(coverage['captured_calls']==sum(case['origin']=='existing_python_assertion' for case in index['cases']),'Missing captured fresh report')
    for item in coverage['methods']:
        require(item['retained_calls']==sum(case['id'].startswith(item['method']+'/') for case in index['cases']),'Stale per-method capture ledger')
    # Cheap malformed inventory/exception checks precede full record decoding.
    # Valid campaigns still independently decode every complete authority.
    for identity,item in declared.items():
        require(item['kind'] in CLASSES,'Unknown architecture document kind')
        raw=resolve(index,documents,identity)
        require(CLASSES[item['kind']].from_dict(raw).fingerprint==identity,'Unnormalized complete architecture document')

def load():
    require(CORPUS.stat().st_size<=MAX_STORED_BYTES,'Architecture index file size limit')
    index=parse_json(CORPUS.read_text())
    docs={};loaded_bytes=CORPUS.stat().st_size
    for item in index['documents']:
        identity=item['id']
        require(isinstance(identity,str) and len(identity)==64 and all(c in '0123456789abcdef' for c in identity) and identity not in docs,'Invalid or duplicate document path identity')
        require(type(item['bytes']) is int and 0<item['bytes']<=4_000_000 and loaded_bytes+item['bytes']<=MAX_STORED_BYTES,'Architecture aggregate file byte limit')
        loaded_bytes+=item['bytes']
        path=DOCUMENTS/(identity+'.json')
        require(path.is_file() and path.stat().st_size==item['bytes']<=4_000_000,'Architecture document file size differs')
        docs[item['id']]=parse_json(path.read_text())
    require({p.name for p in DOCUMENTS.glob('*.json')}=={identity+'.json' for identity in docs},'Extra/missing architecture fixture files')
    return index,docs

def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    if os.environ.get('PYTHONHASHSEED')!='0':
        raise SystemExit(subprocess.call([sys.executable,str(Path(__file__).resolve()),*argv],env={**os.environ,'PYTHONHASHSEED':'0'}))
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--write',action='store_true');parser.add_argument('--check',action='store_true')
    args=parser.parse_args(argv);index,documents=build_corpus()
    if args.write:
        DOCUMENTS.mkdir(exist_ok=True)
        for old in DOCUMENTS.glob('*.json'):
            if old.stem not in documents:old.unlink()
        metadata={item['id']:item for item in index['documents']}
        for identity,raw in documents.items():(DOCUMENTS/(identity+'.json')).write_bytes(stored_encoded(raw,metadata[identity]['format']))
        CORPUS.write_bytes(encoded(index))
    else:
        require(CORPUS.read_bytes()==encoded(index),'Architecture checker index drifted')
        require({p.name for p in DOCUMENTS.glob('*.json')}=={identity+'.json' for identity in documents},'Architecture document inventory drifted')
        metadata={item['id']:item for item in index['documents']}
        for identity,raw in documents.items():require((DOCUMENTS/(identity+'.json')).read_bytes()==stored_encoded(raw,metadata[identity]['format']),'Architecture stored document drifted')
    print(json.dumps({key:index['coverage'][key] for key in ('cases','documents','outcomes','formats','stored_document_bytes','resolved_document_bytes')}|{'inventory':index['inventory_fingerprint']},sort_keys=True))
if __name__=='__main__':main()
