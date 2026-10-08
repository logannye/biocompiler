"""Exact draft CI/source topology; no hosted or native operations execute."""
import ast
import hashlib
import importlib.util
from importlib.machinery import SourceFileLoader
import os
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from tools.pipeline_occurrence_source import restore as restore_occurrence_source
from tools.native_cli_dispatch_source import restore as restore_native_cli_dispatch_source

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'tests/conformance/prebuilt-source-v1'
CONTEXT_DELTA=ROOT/'tests/conformance/deferred-context-checker-source-delta-v1.json'
CONTEXT_DELTA_SHA256='c052ed313423f5b4a016b8f8474d50a9364e278904983f3d139eb9e1ca8e4253'
PROVIDER_DELTA=ROOT/'tests/conformance/fixed-provider-checker-source-delta-v1.json'
PROVIDER_DELTA_SHA256='67c11513477659bb81c2e9a0cfb87191fd669cf2caf2acce0962e77f54a50b8b'
PROVIDER_RECORD_DELTA=ROOT/'tests/conformance/fixed-provider-record-observation-source-delta-v1.json'
PROVIDER_RECORD_DELTA_SHA256='c9640228aa97f42321ed6182d4559d305f03be863da8252aac9b86ac7a7357bb'
BUDGET_DELTA=ROOT/'tests/conformance/callback-budget-checker-source-delta-v1.json'
BUDGET_DELTA_SHA256='6cb03e6dfa5c76528bf9370be992634b6a9fbad5219a1e43c042090abd48ff8b'
REFERENCE_DELTA=ROOT/'tests/conformance/reference-distribution-source-delta-v1.json'
REFERENCE_DELTA_SHA256='06475b6327dac7dc67187956e14abb3a0771574307e4fbf460795c49ab905a06'
REFERENCE_PARALLEL_DELTA=ROOT/'tests/conformance/reference-parallel-source-delta-v1.json'
REFERENCE_PARALLEL_DELTA_SHA256='96f5803d6f66fa6dc5e6088a5ed7d5cf8f217fd93ee5266b04fc533f01882bb7'
REFERENCE_TIMEOUT_DELTA=ROOT/'tests/conformance/reference-timeout-source-delta-v1.json'
REFERENCE_TIMEOUT_DELTA_SHA256='f2c1e1ee1ac95a091caec48465f595304828b4bc685bc0ea5f7b6ed8101617a9'
MANAGER_INVENTORY_DELTA=ROOT/'tests/conformance/manager-source-inventory-delta-v1.json'
MANAGER_INVENTORY_DELTA_SHA256='8eb6ba9af872a61a3749244d835fa434ea0f131efade5da16e10a01b59316999'
AUTHORING_DELTA=ROOT/'tests/conformance/installed-authoring-source-delta-v1.json'
AUTHORING_DELTA_SHA256='9903d8be3224513c3bf260ae9cbe2dcd13cb65f9d4f7132313c1fb374d8896dd'
GRAPH_DIAGNOSTIC_DELTA=ROOT/'tests/conformance/public-graph-diagnostic-source-delta-v1.json'
GRAPH_DIAGNOSTIC_DELTA_SHA256='28b90d52d30d291ad1aeee4dad62c35ce012c6f209b02dd4c7972320530ed4c3'
INSPECTION_DELTA=ROOT/'tests/conformance/synthetic-inspection-checker-source-delta-v1.json'
INSPECTION_DELTA_SHA256='dcb1015d864e1acad4202763ce24a7896ae924951d90c302dc4e89c3211a0e1c'


def restore_synthetic_inspection_source(current, proof_bytes):
    """Restore both reviewed additions before the immutable installed-path gate."""
    def require(condition,message):
        if not condition:raise AssertionError(message)
    def pin(raw):
        return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    require(hashlib.sha256(proof_bytes).hexdigest()==INSPECTION_DELTA_SHA256,
        'Unreviewed inspection checker source witness')
    proof=json.loads(proof_bytes)
    require(set(proof)=={'schema','path','base_revision','stages'}
        and proof['schema']=='biocompiler.synthetic_inspection_checker_source_delta.v1'
        and proof['path']=='tools/check_native_synthetic_inspection.py'
        and proof['base_revision']=='45476d61e5d85d9d042c17e9fd0797f03bb90c1e',
        'Inspection source witness shape differs')
    historical={'bytes':31602,'sha256':'b8a2e7f79e5540ac41ef84060fe8f05d157234882bf5d5f4f2148160dcf2ed62'}
    boundary={'bytes':38222,'sha256':'beefdeb218dbb39e92afce0e2b0325edf718313468360f7e45e4c3d6d4dbf6ab'}
    parallel={'bytes':41413,'sha256':'5dbefdf1b4439138ba9ebeccd99457031b6c0df5e0f42d671949341e69218015'}
    expected=(('explicit_frozen_wire_boundaries',historical,boundary,16),
              ('isolated_occurrence_workers',boundary,parallel,18))
    require(type(proof['stages']) is list and len(proof['stages'])==2,
        'Inspection source stage census differs')
    restored=current
    for stage,(name,before_pin,after_pin,count) in reversed(list(zip(proof['stages'],expected))):
        require(type(stage) is dict and set(stage)=={'name','historical','current','spans'}
            and stage['name']==name and stage['historical']==before_pin and stage['current']==after_pin
            and pin(restored)==after_pin, 'Inspection exact source stage differs')
        spans=stage['spans']
        require(type(spans) is list and len(spans)==count,
            'Inspection source span census differs')
        end=0
        for row in spans:
            require(type(row) is dict and set(row)=={'offset','before','after'}
                and type(row['offset']) is int and row['offset']>=end
                and type(row['before']) is str and type(row['after']) is str
                and row['before']!=row['after'], 'Inspection source span shape differs')
            end=row['offset']+len(row['before'].encode())
        newer=restored
        for index,row in reversed(list(enumerate(spans))):
            offset=row['offset']+sum(len(prior['after'].encode())-len(prior['before'].encode())
                for prior in spans[:index])
            before,after=row['before'].encode(),row['after'].encode()
            require(restored[offset:offset+len(after)]==after,'Inspection source span bytes differ')
            restored=restored[:offset]+before+restored[offset+len(after):]
        require(pin(restored)==before_pin,'Complete historical inspection source differs')
        if name=='isolated_occurrence_workers':
            def functions(raw):
                return {node.name:node for node in ast.parse(raw).body
                    if isinstance(node,(ast.FunctionDef,ast.ClassDef))}
            old,new=functions(restored),functions(newer)
            require(set(old)==set(new) and {key for key in old if ast.dump(old[key])!=ast.dump(new[key])}
                =={'campaign','campaign_main','compare','validate_checks'},
                'Inspection worker changed an unrelated function')
            old_loop=next(node for node in old['campaign'].body if isinstance(node,ast.For))
            new_loop=next(node for node in new['campaign'].body if isinstance(node,ast.For))
            require([ast.dump(node) for node in old_loop.body]==[ast.dump(node) for node in new_loop.body[1:]],
                'Inspection worker changed a complete per-case execution body')
            old_loop=next(node for node in old['validate_checks'].body if isinstance(node,ast.For))
            new_loop=next(node for node in new['validate_checks'].body if isinstance(node,ast.For))
            require(ast.dump(old_loop)==ast.dump(new_loop),'Inspection worker changed complete per-row validation')
    return restored


def restore_public_graph_diagnostic_source(current, proof_bytes):
    """Remove only the reviewed failure detail before all earlier source proofs."""
    def require(condition,message):
        if not condition:raise AssertionError(message)
    require(hashlib.sha256(proof_bytes).hexdigest()==GRAPH_DIAGNOSTIC_DELTA_SHA256,
        'Unreviewed public-graph diagnostic source witness')
    proof=json.loads(proof_bytes)
    require(set(proof)=={'schema','path','historical','current','spans'}
        and proof['schema']=='biocompiler.public_graph_diagnostic_source_delta.v1'
        and proof['path']=='tools/check_pipeline_fixed_continuation_install.py',
        'Public-graph diagnostic witness shape differs')
    require(proof['current']=={'bytes':len(current),'sha256':hashlib.sha256(current).hexdigest()},
        'Current continuation driver differs from the reviewed graph diagnostic')
    spans=proof['spans']
    require(type(spans) is list and len(spans)==3 and all(set(row)=={'offset','before','after'}
        and type(row['offset']) is int and row['offset']>=0
        and type(row['before']) is str and type(row['after']) is str for row in spans)
        and spans[0]['offset']<spans[1]['offset']<spans[2]['offset'],
        'Public-graph diagnostic source span census differs')
    addition=ast.parse(spans[0]['after'])
    require(spans[0]['before']=='' and len(addition.body)==2
        and all(isinstance(node,ast.FunctionDef) for node in addition.body)
        and [node.name for node in addition.body]==['public_graph_difference','equal_public_graph'],
        'Public-graph diagnostic additions differ')
    require(spans[1]['before']=="        equal(case['graph'], public_graph(self.corpus.authorities[expected['authority']]),\n"
            "            'Complete public native build values or physical identities differ')\n"
        and spans[1]['after']=="        equal_public_graph(case['graph'], public_graph(self.corpus.authorities[expected['authority']]))\n"
        and spans[2]['before']=='' and spans[2]['after']=="    'tests/test_pipeline_graph_diagnostics.py',\n",
        'Public-graph diagnostic call or control source differs')
    restored=current
    for index,row in reversed(list(enumerate(spans))):
        offset=row['offset']+sum(len(prior['after'].encode())-len(prior['before'].encode()) for prior in spans[:index])
        before,after=row['before'].encode(),row['after'].encode()
        require(restored[offset:offset+len(after)]==after,'Public-graph diagnostic source span bytes differ')
        restored=restored[:offset]+before+restored[offset+len(after):]
    require(proof['historical']=={'revision':'2cf35b440ce9fca6dc951709b27f8122f00b81f7',
        'bytes':len(restored),'sha256':hashlib.sha256(restored).hexdigest()},
        'Complete historical continuation driver source differs')
    return restored


def restore_installed_authoring_source(current, proof_bytes):
    """Retain the complete original installed-path proof before this adapter."""
    def require(condition,message):
        if not condition:raise AssertionError(message)
    require(hashlib.sha256(proof_bytes).hexdigest()==AUTHORING_DELTA_SHA256,
        'Unreviewed installed-authoring source witness')
    proof=json.loads(proof_bytes)
    require(set(proof)=={'schema','path','historical','current','spans'}
        and proof['schema']=='biocompiler.installed_authoring_source_delta.v1'
        and proof['path']=='tools/check_pipeline_fixed_continuation_install.py',
        'Installed-authoring witness shape differs')
    require(proof['current']=={'bytes':len(current),'sha256':hashlib.sha256(current).hexdigest()},
        'Current continuation driver differs from the reviewed authoring correction')
    additions=(
        '    from . import pipeline_authoring_sources as authoring_sources\n',
        '    import pipeline_authoring_sources as authoring_sources\n',
        "    'tools/pipeline_authoring_sources.py', 'tests/test_pipeline_authoring_sources.py',\n",
        '        oracle.portable_sources = authoring_sources.bind_portable_sources(oracle.portable_sources, ROOT)\n')
    spans=proof['spans']
    require(type(spans) is list and len(spans)==len(additions)
        and all(set(row)=={'offset','before','after'} and type(row['offset']) is int
            and row['offset']>=0 and row['before']=='' and row['after']==after
            for row,after in zip(spans,additions)), 'Installed-authoring source span census differs')
    restored=current
    end=len(current)
    for row in reversed(spans):
        offset=row['offset'];after=row['after'].encode()
        require(offset+len(after)<=end and restored[offset:offset+len(after)]==after,
            'Installed-authoring source span bytes differ')
        restored=restored[:offset]+restored[offset+len(after):]
        end=offset
    require(proof['historical']=={'revision':'705480688a7e37e6c0f03447226350684512342f',
        'bytes':len(restored),'sha256':hashlib.sha256(restored).hexdigest()},
        'Complete historical continuation driver source differs')
    return restored


def restore_reference_timeout_source(current, proof_bytes):
    """Restore the exact finite worker allowance before all frozen source proofs."""
    def require(condition,message):
        if not condition:raise AssertionError(message)
    def pin(raw):
        return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    require(hashlib.sha256(proof_bytes).hexdigest()==REFERENCE_TIMEOUT_DELTA_SHA256,
        'Unreviewed reference timeout source witness')
    proof=json.loads(proof_bytes)
    historical={'revision':'db38364eb9ea1fcfa57c8754a790c9e27eb40726','bytes':17918,
        'sha256':'8316869ed38ed7a5173c959a4995c2f00b0b5b70e8170675876f01a56e770e1c'}
    bounded={'bytes':17919,'sha256':'636feb7b10e0c0e95ddbd015c4b66ebdfef0578b284c0d4526e0555f7cfc9715'}
    span={'offset':14880,'before':'timeout=1800','after':'timeout=10800'}
    require(type(proof) is dict and proof=={
        'schema':'biocompiler.reference_timeout_source_delta.v1',
        'path':'tools/pipeline_reference_runtime.py','historical':historical,
        'current':bounded,'spans':[span]}
        and type(proof['historical']['bytes']) is int
        and type(proof['current']['bytes']) is int
        and type(proof['spans'][0]['offset']) is int and pin(current)==bounded,
        'Reference timeout exact source authority differs')
    offset=span['offset'];before=span['before'].encode();after=span['after'].encode()
    require(current[offset:offset+len(after)]==after,'Reference timeout source span bytes differ')
    restored=current[:offset]+before+current[offset+len(after):]
    require(pin(restored)=={key:historical[key] for key in ('bytes','sha256')},
        'Complete historical reference timeout source differs')
    return restored


def restore_reference_parallel_source(current, proof_bytes):
    """Restore exact serial scheduling before the immutable distribution proof."""
    def require(condition,message):
        if not condition:raise AssertionError(message)
    def pin(raw):
        return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    require(hashlib.sha256(proof_bytes).hexdigest()==REFERENCE_PARALLEL_DELTA_SHA256,
        'Unreviewed reference parallel source witness')
    proof=json.loads(proof_bytes)
    historical={'revision':'ce744f6afccae3014b21bf0a876d54858764b321','bytes':17333,
        'sha256':'2038afce45cd6f0490957370286a0a3ba8fc0fca402c0daf30b2bede1d67d70e'}
    parallel={'bytes':17918,'sha256':'8316869ed38ed7a5173c959a4995c2f00b0b5b70e8170675876f01a56e770e1c'}
    require(type(proof) is dict and set(proof)=={'schema','path','historical','current','spans'}
        and proof['schema']=='biocompiler.reference_parallel_source_delta.v1'
        and proof['path']=='tools/pipeline_reference_runtime.py'
        and proof['historical']==historical and proof['current']==parallel
        and type(proof['historical']['bytes']) is int and type(proof['current']['bytes']) is int
        and pin(current)==parallel, 'Reference parallel exact source authority differs')
    spans=proof['spans']
    require(type(spans) is list and len(spans)==3,'Reference parallel source span census differs')
    end=0
    for row in spans:
        require(type(row) is dict and set(row)=={'offset','before','after'}
            and type(row['offset']) is int and row['offset']>=end
            and type(row['before']) is str and type(row['after']) is str
            and row['before']!=row['after'], 'Reference parallel source span shape differs')
        end=row['offset']+len(row['before'].encode())
    restored=current
    for index,row in reversed(list(enumerate(spans))):
        offset=row['offset']+sum(len(prior['after'].encode())-len(prior['before'].encode())
            for prior in spans[:index])
        before,after=row['before'].encode(),row['after'].encode()
        require(restored[offset:offset+len(after)]==after,'Reference parallel source span bytes differ')
        restored=restored[:offset]+before+restored[offset+len(after):]
    require(pin(restored)=={key:historical[key] for key in ('bytes','sha256')},
        'Complete historical reference parallel source differs')
    def functions(raw):
        return {node.name:ast.dump(node) for node in ast.parse(raw).body
            if isinstance(node,(ast.FunctionDef,ast.ClassDef))}
    old,new=functions(restored),functions(current)
    require(set(old)==set(new) and {key for key in old if old[key]!=new[key]}=={'compare'},
        'Reference parallel scheduling changed a worker or semantic body')
    return restored


def restore_reference_distribution_source(current, proof_bytes):
    """Restore the complete reference runtime before its explicit source pin."""
    def require(condition,message):
        if not condition:raise AssertionError(message)
    require(hashlib.sha256(proof_bytes).hexdigest()==REFERENCE_DELTA_SHA256,
        'Unreviewed reference-distribution source witness')
    proof=json.loads(proof_bytes)
    require(set(proof)=={'schema','path','historical','current','spans'}
        and proof['schema']=='biocompiler.reference_distribution_source_delta.v1'
        and proof['path']=='tools/pipeline_reference_runtime.py',
        'Reference-distribution witness shape differs')
    require(proof['current']=={'bytes':len(current),'sha256':hashlib.sha256(current).hexdigest()},
        'Current reference runtime differs from the reviewed distribution correction')
    spans=proof['spans']
    require(type(spans) is list and len(spans)==1 and set(spans[0])=={'offset','before','after'}
        and type(spans[0]['offset']) is int and spans[0]['offset']>=0
        and spans[0]['before']==''
        and spans[0]['after']=="    # Installed-layout discovery is current campaign authority, not frozen semantics.\n"
            "    paths.add('src/biocompiler/core_distribution.py')\n",
        'Reference-distribution source span census differs')
    row=spans[0];offset=row['offset'];after=row['after'].encode()
    require(current[offset:offset+len(after)]==after,'Reference-distribution source span bytes differ')
    restored=current[:offset]+current[offset+len(after):]
    require(proof['historical']=={'revision':'d3bef33bf45e0e80797cb30956fc8dc02e58b8eb',
        'bytes':len(restored),'sha256':hashlib.sha256(restored).hexdigest()},
        'Complete historical reference runtime source differs')
    return restored


def restore_manager_inventory_source(current, proof_bytes):
    """Remove only two reviewed source witnesses before all prior manager proofs."""
    def require(condition,message):
        if not condition:raise AssertionError(message)
    require(hashlib.sha256(proof_bytes).hexdigest()==MANAGER_INVENTORY_DELTA_SHA256,
        'Unreviewed manager source inventory witness')
    proof=json.loads(proof_bytes)
    historical={'bytes':171939,'sha256':'da71eecb632c740ba8e5c8fd5ccf85d6174d71c901ec70cbc041ce5adb1c63a6'}
    added={'bytes':172077,'sha256':'72cbd6bf9487f9c17e67f2d4dcd87cc0feab119ea11e75aee9a514a4a56a472a'}
    require(type(proof) is dict and set(proof)=={'schema','path','historical','current','addition'}
        and proof['schema']=='biocompiler.manager_source_inventory_delta.v1'
        and proof['path']=='tools/check_pipeline_manager_install.py'
        and proof['historical']==historical and proof['current']==added
        and type(proof['historical']['bytes']) is int and type(proof['current']['bytes']) is int
        and added=={'bytes':len(current),'sha256':hashlib.sha256(current).hexdigest()},
        'Manager source inventory exact authority differs')
    row=proof['addition']
    addition=('    "tests/conformance/manager-registration-runtime-sites-v6.json",\n'
        '    "tests/conformance/reference-manager-source-counterpart-v5.json",\n').encode()
    require(type(row) is dict and set(row)=={'offset','bytes'} and type(row['offset']) is int
        and row['offset']>=0 and row['bytes']==addition.decode() and current.count(addition)==1,
        'Manager source inventory addition differs')
    offset=row['offset']
    require(current[offset:offset+len(addition)]==addition,'Manager source inventory exact span differs')
    restored=current[:offset]+current[offset+len(addition):]
    require(historical=={'bytes':len(restored),'sha256':hashlib.sha256(restored).hexdigest()},
        'Complete previous manager source differs')
    return restored


def restore_callback_budget_source(current, proof_bytes):
    """Restore the exact checker before the separate per-frame node bound."""
    def require(condition,message):
        if not condition:raise AssertionError(message)
    require(hashlib.sha256(proof_bytes).hexdigest()==BUDGET_DELTA_SHA256,
        'Unreviewed callback-budget source witness')
    proof=json.loads(proof_bytes)
    require(set(proof)=={'schema','path','historical','current','spans'}
        and proof['schema']=='biocompiler.callback_budget_checker_source_delta.v1'
        and proof['path']=='tools/check_pipeline_manager_install.py',
        'Callback-budget witness shape differs')
    require(proof['current']=={'bytes':len(current),'sha256':hashlib.sha256(current).hexdigest()},
        'Current checker differs from the reviewed callback-budget correction')
    spans=proof['spans']
    require(type(spans) is list and len(spans)==1 and set(spans[0])=={'offset','before','after'}
        and type(spans[0]['offset']) is int and spans[0]['offset']>=0
        and spans[0]['before']=='        nodes += json_nodes(value)\n'
        and type(spans[0]['after']) is str and spans[0]['after'],
        'Callback-budget source span census differs')
    row=spans[0];offset=row['offset'];before=row['before'].encode();after=row['after'].encode()
    require(current[offset:offset+len(after)]==after,'Callback-budget source span bytes differ')
    restored=current[:offset]+before+current[offset+len(after):]
    require(proof['historical']=={'revision':'b27f52447f49c749d33cac17f3bbb6fe772cbc24',
        'bytes':len(restored),'sha256':hashlib.sha256(restored).hexdigest()},
        'Complete historical callback checker source differs')
    return restored


def restore_deferred_context_source(current, proof_bytes):
    """Recover the exact installed-path checkpoint before its later proof fix."""
    def require(condition,message):
        if not condition:raise AssertionError(message)
    require(hashlib.sha256(proof_bytes).hexdigest()==CONTEXT_DELTA_SHA256,
        'Unreviewed deferred-context source witness')
    proof=json.loads(proof_bytes)
    require(set(proof)=={'schema','path','historical','current','spans'}
        and proof['schema']=='biocompiler.deferred_context_checker_source_delta.v1'
        and proof['path']=='tools/check_pipeline_manager_install.py',
        'Deferred-context witness shape differs')
    require(proof['current']=={'bytes':len(current),'sha256':hashlib.sha256(current).hexdigest()},
        'Current checker differs from the reviewed deferred-context correction')
    spans=proof['spans']
    require(type(spans) is list and len(spans)==2 and all(set(row)=={'offset','before','after'}
        and type(row['offset']) is int and row['offset']>=0
        and type(row['before']) is str and type(row['after']) is str for row in spans),
        'Deferred-context source span census differs')
    addition=ast.parse(spans[0]['after'])
    require(spans[0]['before']=='' and len(addition.body)==1
        and isinstance(addition.body[0],ast.FunctionDef)
        and addition.body[0].name=='deferred_context_document',
        'Deferred-context source addition is not its single proof function')
    require(spans[1]['before']=='equal(contexts[-1]["arguments"]["document"], values["context"], "Deferred callback read a context different from native authority")'
        and spans[1]['after']=='equal(deferred_context_document(contexts[-1], native), values["context"],\n                "Deferred callback read a context different from native authority")'
        and spans[0]['offset']<spans[1]['offset'],
        'Deferred-context comparison call is not the single reviewed substitution')
    restored=current
    for index,row in reversed(list(enumerate(spans))):
        offset=row['offset']+sum(len(prior['after'].encode())-len(prior['before'].encode()) for prior in spans[:index])
        before,after=row['before'].encode(),row['after'].encode()
        require(restored[offset:offset+len(after)]==after,'Deferred-context source span bytes differ')
        restored=restored[:offset]+before+restored[offset+len(after):]
    require(proof['historical']=={'revision':'817a8ed1154975befd293327dfabdf7798ed2b4c',
        'bytes':len(restored),'sha256':hashlib.sha256(restored).hexdigest()},
        'Complete historical installed-path checker source differs')
    return restored


def restore_fixed_provider_record_source(current, proof_bytes=None):
    """Remove only the reviewed retention of already inspected record objects."""
    def require(condition,message):
        if not condition:raise AssertionError(message)
    raw=PROVIDER_RECORD_DELTA.read_bytes() if proof_bytes is None else proof_bytes
    require(hashlib.sha256(raw).hexdigest()==PROVIDER_RECORD_DELTA_SHA256,
        'Unreviewed fixed-provider record observation witness')
    proof=json.loads(raw)
    require(set(proof)=={'schema','path','historical','current','spans'}
        and proof['schema']=='biocompiler.fixed_provider_record_observation_source_delta.v1'
        and proof['path']=='tools/check_pipeline_fixed_provider_install.py',
        'Fixed-provider record observation witness shape differs')
    require(proof['current']=={'bytes':len(current),'sha256':hashlib.sha256(current).hexdigest()},
        'Current fixed-provider checker differs from reviewed record observation')
    spans=proof['spans']
    require(type(spans) is list and len(spans)==2 and all(set(row)=={'offset','before','after'}
        and type(row['offset']) is int and row['offset']>=0 and row['before']==''
        and type(row['after']) is str and row['after'] for row in spans)
        and spans[0]['offset']<spans[1]['offset'], 'Fixed-provider record observation span census differs')
    restored=current
    for index,row in reversed(list(enumerate(spans))):
        offset=row['offset']+sum(len(prior['after'].encode()) for prior in spans[:index])
        after=row['after'].encode()
        require(restored[offset:offset+len(after)]==after, 'Fixed-provider record observation span differs')
        restored=restored[:offset]+restored[offset+len(after):]
    require(proof['historical']=={'revision':'7b953c27e165be6389747a6f7c03a50465622e72',
        'bytes':len(restored),'sha256':hashlib.sha256(restored).hexdigest()},
        'Complete prior fixed-provider checker differs after record restoration')
    return restored


def restore_fixed_provider_source(current, proof_bytes):
    """Recover the complete installed-path checker before its lineage fix."""
    def require(condition,message):
        if not condition:raise AssertionError(message)
    require(hashlib.sha256(proof_bytes).hexdigest()==PROVIDER_DELTA_SHA256,
        'Unreviewed fixed-provider source witness')
    proof=json.loads(proof_bytes)
    require(set(proof)=={'schema','path','historical','current','spans'}
        and proof['schema']=='biocompiler.fixed_provider_checker_source_delta.v1'
        and proof['path']=='tools/check_pipeline_fixed_provider_install.py',
        'Fixed-provider witness shape differs')
    current=restore_fixed_provider_record_source(current)
    require(proof['current']=={'bytes':len(current),'sha256':hashlib.sha256(current).hexdigest()},
        'Current fixed-provider checker differs from the reviewed lineage correction')
    spans=proof['spans']
    require(type(spans) is list and len(spans)==1
        and set(spans[0])=={'offset','before','after'}
        and type(spans[0]['offset']) is int and spans[0]['offset']>=0
        and all(type(spans[0][name]) is str and spans[0][name] for name in ('before','after')),
        'Fixed-provider source span census differs')
    row=spans[0];offset=row['offset'];before=row['before'].encode();after=row['after'].encode()
    require(current[offset:offset+len(after)]==after,'Fixed-provider source span bytes differ')
    restored=current[:offset]+before+current[offset+len(after):]
    require(proof['historical']=={'revision':'0dd0fe54f3d1f0e502b30188f096cb5387fbb9b2',
        'bytes':len(restored),'sha256':hashlib.sha256(restored).hexdigest()},
        'Complete historical fixed-provider checker source differs')
    return restored


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path,loader=SourceFileLoader(name,str(path)))
    module=importlib.util.module_from_spec(spec)
    # Current direct-script tools resolve their sibling imports without relying
    # on another test module having imported those siblings earlier.
    with patch.object(sys,'path',[str(ROOT/'tools'),*sys.path]):
        spec.loader.exec_module(module)
    return module


class HostedCiPlanTests(unittest.TestCase):
    def setUp(self):
        import hashlib,json
        raw=(ROOT/'tests/conformance/prebuilt-source-v1.json').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),'d679ec6aaf09cb0fc1ba56c42bf72b85b3184b37f34456633f76139b4274363d')
        for name,pin in json.loads(raw)['files'].items():
            content=Path(str(SOURCE/name)+'.source').read_bytes()
            self.assertEqual({'sha256':hashlib.sha256(content).hexdigest(),'size':len(content)},pin)
        self.old=(SOURCE/'.github/workflows/ci.yml.source').read_text()
        self.new=(ROOT/'.github/workflows/ci.yml').read_text()

    def test_every_previous_required_job_and_variant_remains_with_reviewed_additions(self):
        old=load('old_ci_validation',SOURCE/'tools/ci_validation.py.source');new=load('draft_ci_validation',ROOT/'tools/ci_validation.py')
        self.assertEqual(new.REQUIRED_NEEDS-old.REQUIRED_NEEDS,{'prebuilt-core-assembly','prebuilt-core-validation','ci-preflight','ocaml-build','ocaml-native-tests','architecture-sdk','installed-campaigns','policy-prebuilt-sdk','policy-prebuilt-installed','policy-prebuilt-reproducibility'})
        self.assertEqual(old.REQUIRED_NEEDS-new.REQUIRED_NEEDS,set())
        self.assertEqual(old.EXPECTED_RECEIPTS-new.EXPECTED_RECEIPTS,set())
        self.assertEqual(len(new.EXPECTED_RECEIPTS-old.EXPECTED_RECEIPTS),38)
        self.assertEqual(new.REALIZATION_VARIANTS,old.REALIZATION_VARIANTS)
        self.assertEqual(new.workflow_jobs(ROOT/'.github/workflows/ci.yml'),new.WORKFLOW_NEEDS|{'validation'})

    def test_every_native_test_command_survives_and_static_preparation_precedes_dependencies(self):
        from tools.ci_core_groups import load_plan
        before=re.findall(r'core/_build/default/test/[^\n]+',self.old)
        after=re.findall(r'core/_build/default/test/[^\n]+',
            '\n'.join(group['run'] for group in load_plan(ROOT)))
        self.assertEqual(after,before)
        native=self.new.split('\n  ocaml-core:\n',1)[1].split('\n  architecture-sdk:\n',1)[0]
        run='python tools/ci_core_groups.py run --output generated/core/command-groups --workers 2'
        check='python tools/ci_core_groups.py check --output generated/core/command-groups'
        self.assertEqual(native.count(run),1);self.assertEqual(native.count(check),1)
        self.assertLess(native.index(run),native.index(check))
        self.assertLess(native.index(check),native.index('Record successful complete ocaml-core'))
        self.assertLess(self.new.index('tools/prebuilt_sources.py static-build'),self.new.index('opam install core/biocompiler_core.opam'))
        self.assertIn('opam reinstall zarith.1.14 --yes --no-depexts',self.new)
        self.assertLess(self.new.index('Retain revision-bound native executables'),self.new.index('tools/build_prebuilt_core.py wheel'))
        self.assertIn('native_build',self.new)

    def test_fresh_four_runtime_slots_have_no_source_install_or_dynamic_gmp_fallback(self):
        block=self.new.split('  installed-campaigns:',1)[1].split('  realization-conformance:',1)[0]
        self.assertEqual(block.count('python-version: "3.11"'),10);self.assertEqual(block.count('python-version: "3.14"'),10)
        self.assertIn('needs: [ocaml-build, prebuilt-core-assembly]',block)
        self.assertIn('tools/prebuilt_release_pipeline.py installed',block)
        self.assertNotIn('pip install .',block);self.assertNotIn('brew install',block);self.assertNotIn('--prepare',block)
        self.assertIn('$RUNNER_TEMP/biocompiler-fresh-',block)

    def test_hosted_audit_selection_resolves_tool_symlinks_without_relaxing_release_inputs(self):
        lines=self.new.splitlines()
        index=next(i for i,line in enumerate(lines) if 'audit_tool="$(command -v otool)"' in line)
        selection=lines[index].strip();resolution=lines[index+1].strip()
        self.assertEqual(resolution,
            'audit_tool="$(python -c \'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve(strict=True))\' "$audit_tool")"')
        release=load('hosted_audit_release',ROOT/'tools/build_prebuilt_core.py')
        policy=load('hosted_audit_policy',ROOT/'tests/test_prebuilt_core_release.py')
        bash=shutil.which('bash');self.assertIsNotNone(bash)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve();bin_path=root/'bin';bin_path.mkdir()
            (bin_path/'python').symlink_to(Path(sys.executable).resolve())
            artifact=root/'artifact';artifact.write_bytes(b'nonexecuted native-byte fixture')
            for runner_os,name,target,output in (
                    ('Linux','readelf','linux-x86_64',policy.ELF),
                    ('macOS','otool','macos-arm64',policy.MACHO)):
                with self.subTest(runner_os=runner_os):
                    actual=root/(name+'-actual');actual.write_bytes(b'nonexecuted audit fixture: '+name.encode());actual.chmod(0o755)
                    selected=bin_path/name;selected.symlink_to(actual)
                    script='\n'.join((selection.replace('${{ runner.os }}',runner_os),resolution,'printf \'%s\\n\' "$audit_tool"'))
                    resolved=subprocess.run([bash,'-e','-c',script],env={**os.environ,'PATH':str(bin_path)},
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=10)
                    self.assertEqual(resolved.stderr,b'')
                    canonical=Path(resolved.stdout.decode().rstrip('\n'))
                    self.assertEqual(canonical,actual);self.assertFalse(canonical.is_symlink())
                    completed=subprocess.CompletedProcess([],0,stdout=output.encode(),stderr=b'')
                    with patch.object(release.subprocess,'run',return_value=completed) as invoked:
                        with self.assertRaisesRegex(ValueError,'symlinked'):
                            release.audit(selected,artifact,target)
                        receipt=release.audit(canonical,artifact,target)
                    self.assertEqual(receipt['argv'][0],str(actual))
                    self.assertEqual(receipt['tool_sha256'],release.sha(actual.read_bytes()))
                    self.assertEqual(invoked.call_args.args[0],receipt['argv'])
                    artifact_link=root/(name+'-artifact-link');artifact_link.symlink_to(artifact)
                    with self.assertRaisesRegex(ValueError,'symlinked'):
                        release.regular(artifact_link,1024)

    def test_sdk_assembly_pins_build_tools_and_both_material_companions(self):
        block=self.new.split('  prebuilt-core-assembly:',1)[1].split('  prebuilt-core-validation:',1)[0]
        self.assertIn('needs: ocaml-build',block)
        self.assertEqual(block.count('tools/check_prebuilt_core_release.py'),2)
        self.assertIn('--only-binary=:all: --require-hashes',block)
        self.assertIn('prebuilt-linux-x86_64',block);self.assertIn('prebuilt-macos-arm64',block)
        self.assertIn('--sdk generated/prebuilt-wheelhouse/',block)
        requirements=(ROOT/'tools/prebuilt-build-requirements.txt').read_text().splitlines()
        self.assertEqual(len(requirements),5)
        self.assertTrue(all(re.fullmatch(r'[a-z-]+==[0-9.]+ --hash=sha256:[0-9a-f]{64}',line) for line in requirements))

    def test_installed_path_edits_are_finite_and_no_semantic_case_body_is_changed(self):
        import json,hashlib
        proof=json.loads((ROOT/'tests/conformance/prebuilt-installed-path-delta-v1.json').read_bytes())
        self.assertEqual(len(proof),14)
        for name,row in proof.items():
            old=Path(str(SOURCE/name)+'.source').read_text();new=(ROOT/name).read_bytes()
            if name=='tools/check_native_synthetic_inspection.py':
                new=restore_synthetic_inspection_source(new,INSPECTION_DELTA.read_bytes())
            elif name in ('tools/check_native_workflow_cli.py','tools/check_native_synthetic_selection_cli.py'):
                new=restore_native_cli_dispatch_source(name,new)
            elif name=='tools/check_pipeline_manager_install.py':
                new=restore_manager_inventory_source(new,MANAGER_INVENTORY_DELTA.read_bytes())
                new=restore_callback_budget_source(new,BUDGET_DELTA.read_bytes())
                new=restore_deferred_context_source(new,CONTEXT_DELTA.read_bytes())
            elif name=='tools/check_pipeline_fixed_provider_install.py':
                new=restore_fixed_provider_source(new,PROVIDER_DELTA.read_bytes())
            elif name=='tools/pipeline_reference_runtime.py':
                new=restore_reference_timeout_source(new,REFERENCE_TIMEOUT_DELTA.read_bytes())
                new=restore_reference_parallel_source(new,REFERENCE_PARALLEL_DELTA.read_bytes())
                new=restore_reference_distribution_source(new,REFERENCE_DELTA.read_bytes())
            elif name=='tools/check_pipeline_fixed_continuation_install.py':
                new=restore_occurrence_source(name,new)
                new=restore_public_graph_diagnostic_source(new,GRAPH_DIAGNOSTIC_DELTA.read_bytes())
                new=restore_installed_authoring_source(new,AUTHORING_DELTA.read_bytes())
            new=new.decode()
            self.assertEqual(hashlib.sha256(new.encode()).hexdigest(),row['current_sha256'])
            old_ast=ast.parse(old);new_ast=ast.parse(new)
            old_functions={n.name:n for n in old_ast.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
            new_functions={n.name:n for n in new_ast.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
            self.assertEqual(set(old_functions),set(new_functions))
            changed=[name for name,node in old_functions.items() if ast.dump(node)!=ast.dump(new_functions[name])]
            self.assertEqual(len(changed),1,name)
            self.assertIn(changed[0],('campaign_main','main'),name)
        self.assertIn('  prebuilt-core-validation:',self.new)
        block=self.new.split('  prebuilt-core-validation:',1)[1].split('  validation:',1)[0]
        self.assertIn('realization-core-reproducibility',block)
        self.assertEqual(block.count('name: realization-'),4)

    def test_dispatch_guard_restoration_retains_complete_original_installed_path_proof(self):
        from tools import native_cli_dispatch_source as dispatch
        witness=(ROOT/dispatch.WITNESS).read_bytes()
        manifest=json.loads((ROOT/'tests/conformance/prebuilt-installed-path-delta-v1.json').read_bytes())
        proof=json.loads(witness)
        for name in dispatch.HISTORICAL:
            current=(ROOT/name).read_bytes()
            restored=dispatch.restore(name,current,witness)
            self.assertEqual(hashlib.sha256(restored).hexdigest(),manifest[name]['current_sha256'])
            for changed in (restored,current+b'\n',current.replace(b'phase != "output"',b'phase != "input"'),
                            current.replace(b'def run_case(',b'def unchecked_case(')):
                with self.subTest(path=name,current=hashlib.sha256(changed).hexdigest()), self.assertRaises(AssertionError):
                    dispatch.restore(name,changed,witness)
            for mutation in ('missing','order','offset','before','after','current','historical','base','policy'):
                changed=json.loads(witness)
                row=changed['files'][name]
                if mutation=='missing': row['spans'].pop()
                elif mutation=='order': row['spans'].reverse()
                elif mutation=='offset': row['spans'][0]['offset']+=1
                elif mutation in ('before','after'): row['spans'][0][mutation]+='\n'
                elif mutation in ('current','historical'): row[mutation]['sha256']='0'*64
                elif mutation=='base': changed['base_revision']='0'*40
                else: changed['policy_witness_sha256']='0'*64
                raw=(json.dumps(changed,sort_keys=True,indent=2)+'\n').encode()
                with self.subTest(path=name,witness=mutation), self.assertRaisesRegex(AssertionError,'Unreviewed'):
                    dispatch.restore(name,current,raw)
        self.assertEqual(set(proof['files']),set(dispatch.HISTORICAL))

    def test_inspection_restoration_preserves_both_reviewed_stages_and_rejects_forgery(self):
        current=(ROOT/'tools/check_native_synthetic_inspection.py').read_bytes()
        witness=INSPECTION_DELTA.read_bytes();proof=json.loads(witness)
        restored=restore_synthetic_inspection_source(current,witness)
        original=json.loads((ROOT/'tests/conformance/prebuilt-installed-path-delta-v1.json').read_bytes())
        self.assertEqual(hashlib.sha256(restored).hexdigest(),
            original['tools/check_native_synthetic_inspection.py']['current_sha256'])
        for mutant in (restored,current+b'\n',current.replace(b'byte:1303',b'byte:1304'),
                current.replace(b'ordinal not in selected',b'ordinal in selected'),
                current.replace(b'def invoke_public(',b'def unchecked_public(')):
            with self.subTest(source_sha256=hashlib.sha256(mutant).hexdigest()),self.assertRaises(AssertionError):
                restore_synthetic_inspection_source(mutant,witness)
        for mutation in ('revision','order','missing','current','historical','offset','before','after','overlap'):
            changed=json.loads(witness)
            if mutation=='revision':changed['base_revision']='0'*40
            elif mutation=='order':changed['stages'].reverse()
            elif mutation=='missing':changed['stages'].pop()
            elif mutation in ('current','historical'):changed['stages'][1][mutation]['sha256']='0'*64
            elif mutation=='overlap':changed['stages'][1]['spans'][1]['offset']=0
            elif mutation=='offset':changed['stages'][1]['spans'][0]['offset']+=1
            else:changed['stages'][1]['spans'][0][mutation]+=' '
            encoded=json.dumps(changed,sort_keys=True,indent=2).encode()+b'\n'
            with self.subTest(witness_mutation=mutation),patch.dict(globals(),
                    INSPECTION_DELTA_SHA256=hashlib.sha256(encoded).hexdigest()),self.assertRaises(AssertionError):
                restore_synthetic_inspection_source(current,encoded)
        with self.assertRaises(AssertionError):
            restore_synthetic_inspection_source(current,witness+b'\n')

    def test_deferred_context_restoration_rejects_unreviewed_or_extra_source_changes(self):
        current=restore_manager_inventory_source((ROOT/'tools/check_pipeline_manager_install.py').read_bytes(),
            MANAGER_INVENTORY_DELTA.read_bytes())
        current=restore_callback_budget_source(current,
            BUDGET_DELTA.read_bytes())
        witness=CONTEXT_DELTA.read_bytes();proof=json.loads(witness)
        restored=restore_deferred_context_source(current,witness)
        self.assertEqual(hashlib.sha256(restored).hexdigest(),
            'd12f67bf4080b15a96856342e87e8678007e6093188b1a36540c7f337f6463b7')
        mutants={
            'stale historical bytes':restored,
            'added proof body':current.replace(b'and outcome["value"] is True',b'and outcome["value"] == True'),
            'comparison call':current.replace(proof['spans'][1]['after'].encode(),proof['spans'][1]['before'].encode()),
            'outside original body':current.replace(b'def validate_deferred_accesses(',b'def unchecked_accesses('),
            'extra function':current+b'\ndef unreviewed():\n    return True\n',
            'newline normalization':current.replace(b'\n',b'\r\n'),
        }
        for name,mutant in mutants.items():
            with self.subTest(change=name):
                self.assertNotEqual(mutant,current)
                with self.assertRaisesRegex(AssertionError,'Current checker differs'):
                    restore_deferred_context_source(mutant,witness)
                # Rehashing the source or editing a span cannot turn new bytes
                # into a newly approved witness; its complete pin is separate.
                changed=json.loads(witness)
                changed['current']={'bytes':len(mutant),'sha256':hashlib.sha256(mutant).hexdigest()}
                with self.assertRaisesRegex(AssertionError,'Unreviewed deferred-context source witness'):
                    restore_deferred_context_source(mutant,json.dumps(changed,sort_keys=True,indent=2).encode()+b'\n')
        changed=json.loads(witness);changed['spans'][0]['offset']+=1
        with self.assertRaisesRegex(AssertionError,'Unreviewed deferred-context source witness'):
            restore_deferred_context_source(current,json.dumps(changed,sort_keys=True,indent=2).encode()+b'\n')

    def test_manager_inventory_restoration_preserves_exact_prior_chain_and_rejects_forgery(self):
        current=(ROOT/'tools/check_pipeline_manager_install.py').read_bytes()
        witness=MANAGER_INVENTORY_DELTA.read_bytes()
        restored=restore_manager_inventory_source(current,witness)
        self.assertEqual({'bytes':len(restored),'sha256':hashlib.sha256(restored).hexdigest()},
            json.loads(BUDGET_DELTA.read_bytes())['current'])
        complete=restore_deferred_context_source(restore_callback_budget_source(restored,BUDGET_DELTA.read_bytes()),
            CONTEXT_DELTA.read_bytes())
        self.assertEqual(hashlib.sha256(complete).hexdigest(),
            'd12f67bf4080b15a96856342e87e8678007e6093188b1a36540c7f337f6463b7')
        for mutant in (restored,current+b'\n',current.replace(b'runtime-sites-v6.json',b'runtime-sites-v7.json'),
                current.replace(b'def validate_frames(',b'def changed_frames(')):
            with self.subTest(source_sha256=hashlib.sha256(mutant).hexdigest()):
                self.assertNotEqual(mutant,current)
                with self.assertRaises(AssertionError):restore_manager_inventory_source(mutant,witness)
        for mutation in ('schema','path','historical','current','offset','bool_offset','bytes','float_bytes'):
            forged=json.loads(witness)
            if mutation=='schema':forged['schema']+='x'
            elif mutation=='path':forged['path']='tools/unreviewed.py'
            elif mutation in ('historical','current'):forged[mutation]['sha256']='0'*64
            elif mutation=='float_bytes':forged['current']['bytes']=float(forged['current']['bytes'])
            elif mutation=='offset':forged['addition']['offset']+=1
            elif mutation=='bool_offset':forged['addition']['offset']=True
            else:forged['addition']['bytes']+=' '
            encoded=json.dumps(forged,sort_keys=True,indent=2).encode()+b'\n'
            with self.subTest(witness_mutation=mutation),patch.dict(globals(),
                    MANAGER_INVENTORY_DELTA_SHA256=hashlib.sha256(encoded).hexdigest()),self.assertRaises(AssertionError):
                restore_manager_inventory_source(current,encoded)
        with self.assertRaisesRegex(AssertionError,'Unreviewed manager source inventory'):
            restore_manager_inventory_source(current,witness+b'\n')

    def test_callback_budget_restoration_preserves_prior_source_proofs(self):
        current=(ROOT/'tools/check_pipeline_manager_install.py').read_bytes()
        current=restore_manager_inventory_source(current,MANAGER_INVENTORY_DELTA.read_bytes())
        witness=BUDGET_DELTA.read_bytes();proof=json.loads(witness)
        restored=restore_callback_budget_source(current,witness)
        self.assertEqual(hashlib.sha256(restored).hexdigest(),
            '59f94bb142d7097160dd08fef700f458a362865fb6b6ad8142c530fac5fe0edb')
        self.assertEqual(hashlib.sha256(restore_deferred_context_source(restored,CONTEXT_DELTA.read_bytes())).hexdigest(),
            'd12f67bf4080b15a96856342e87e8678007e6093188b1a36540c7f337f6463b7')
        for label,mutant in {
                'historical source':restored,
                'comparison boundary':current.replace(b'frame_nodes <= min(',b'frame_nodes < min('),
                'unrelated body':current.replace(b'def validate_deferred_accesses(',b'def unchecked_accesses('),
                'additional function':current+b'\ndef unreviewed():\n    return True\n',
                'newline normalization':current.replace(b'\n',b'\r\n')}.items():
            with self.subTest(change=label):
                self.assertNotEqual(mutant,current)
                with self.assertRaises(AssertionError):restore_callback_budget_source(mutant,witness)
                forged=json.loads(witness)
                forged['current']={'bytes':len(mutant),'sha256':hashlib.sha256(mutant).hexdigest()}
                with self.assertRaisesRegex(AssertionError,'Unreviewed callback-budget source witness'):
                    restore_callback_budget_source(mutant,json.dumps(forged,sort_keys=True,indent=2).encode()+b'\n')
        proof['spans'][0]['offset']+=1
        with self.assertRaisesRegex(AssertionError,'Unreviewed callback-budget source witness'):
            restore_callback_budget_source(current,json.dumps(proof,sort_keys=True,indent=2).encode()+b'\n')


    def test_fixed_provider_record_observation_restoration_is_exact_and_rejects_forgery(self):
        current=(ROOT/'tools/check_pipeline_fixed_provider_install.py').read_bytes()
        witness=PROVIDER_RECORD_DELTA.read_bytes();proof=json.loads(witness)
        restored=restore_fixed_provider_record_source(current,witness)
        prior=json.loads(PROVIDER_DELTA.read_bytes())['current']
        self.assertEqual({'bytes':len(restored),'sha256':hashlib.sha256(restored).hexdigest()},prior)
        with self.assertRaisesRegex(AssertionError,'Current fixed-provider checker differs'):
            restore_fixed_provider_record_source(current+b'\n',witness)
        proof['spans'][0]['offset']+=1
        with self.assertRaisesRegex(AssertionError,'Unreviewed fixed-provider record observation witness'):
            restore_fixed_provider_record_source(current,json.dumps(proof,sort_keys=True,indent=2).encode()+b'\n')

    def test_fixed_provider_restoration_rejects_unreviewed_source_changes(self):
        current=(ROOT/'tools/check_pipeline_fixed_provider_install.py').read_bytes()
        witness=PROVIDER_DELTA.read_bytes();proof=json.loads(witness)
        restored=restore_fixed_provider_source(current,witness)
        original=json.loads((ROOT/'tests/conformance/prebuilt-installed-path-delta-v1.json').read_bytes())
        self.assertEqual(hashlib.sha256(restored).hexdigest(),
            original['tools/check_pipeline_fixed_provider_install.py']['current_sha256'])
        mutants={
            'stale historical bytes':restored,
            'changed lineage target':current.replace(b'src/biocompiler/compiler/pipeline.py',b'src/biocompiler/compiler/unreviewed.py'),
            'extra function':current+b'\ndef unreviewed():\n    return True\n',
            'newline normalization':current.replace(b'\n',b'\r\n'),
        }
        for name,mutant in mutants.items():
            with self.subTest(change=name):
                self.assertNotEqual(mutant,current)
                with self.assertRaisesRegex(AssertionError,'Current fixed-provider checker differs'):
                    restore_fixed_provider_source(mutant,witness)
                changed=json.loads(witness)
                changed['current']={'bytes':len(mutant),'sha256':hashlib.sha256(mutant).hexdigest()}
                with self.assertRaisesRegex(AssertionError,'Unreviewed fixed-provider source witness'):
                    restore_fixed_provider_source(mutant,json.dumps(changed,sort_keys=True,indent=2).encode()+b'\n')
        changed=json.loads(witness);changed['spans'][0]['offset']+=1
        with self.assertRaisesRegex(AssertionError,'Unreviewed fixed-provider source witness'):
            restore_fixed_provider_source(current,json.dumps(changed,sort_keys=True,indent=2).encode()+b'\n')

    def test_installed_authoring_restoration_rejects_unreviewed_source_changes(self):
        current=(ROOT/'tools/check_pipeline_fixed_continuation_install.py').read_bytes()
        current=restore_occurrence_source('tools/check_pipeline_fixed_continuation_install.py',current)
        current=restore_public_graph_diagnostic_source(current,GRAPH_DIAGNOSTIC_DELTA.read_bytes())
        witness=AUTHORING_DELTA.read_bytes()
        restored=restore_installed_authoring_source(current,witness)
        original=json.loads((ROOT/'tests/conformance/prebuilt-installed-path-delta-v1.json').read_bytes())
        self.assertEqual(hashlib.sha256(restored).hexdigest(),
            original['tools/check_pipeline_fixed_continuation_install.py']['current_sha256'])
        mutants={
            'stale historical bytes':restored,
            'different binding':current.replace(b'bind_portable_sources(oracle.portable_sources, ROOT)',
                b'bind_portable_sources(oracle.portable_sources, Path.cwd())'),
            'extra function':current+b'\ndef unreviewed():\n    return True\n',
            'newline normalization':current.replace(b'\n',b'\r\n'),
        }
        for label,mutant in mutants.items():
            with self.subTest(change=label):
                self.assertNotEqual(mutant,current)
                with self.assertRaisesRegex(AssertionError,'Current continuation driver differs'):
                    restore_installed_authoring_source(mutant,witness)
                forged=json.loads(witness)
                forged['current']={'bytes':len(mutant),'sha256':hashlib.sha256(mutant).hexdigest()}
                with self.assertRaisesRegex(AssertionError,'Unreviewed installed-authoring source witness'):
                    restore_installed_authoring_source(mutant,json.dumps(forged,sort_keys=True,indent=2).encode()+b'\n')
        forged=json.loads(witness);forged['spans'][0]['offset']+=1
        with self.assertRaisesRegex(AssertionError,'Unreviewed installed-authoring source witness'):
            restore_installed_authoring_source(current,json.dumps(forged,sort_keys=True,indent=2).encode()+b'\n')

    def test_reference_timeout_restoration_preserves_exact_full_chain_and_rejects_forgery(self):
        current=(ROOT/'tools/pipeline_reference_runtime.py').read_bytes()
        witness=REFERENCE_TIMEOUT_DELTA.read_bytes()
        restored=restore_reference_timeout_source(current,witness)
        self.assertEqual({'bytes':len(restored),'sha256':hashlib.sha256(restored).hexdigest()},
            json.loads(REFERENCE_PARALLEL_DELTA.read_bytes())['current'])
        parallel=restore_reference_parallel_source(restored,REFERENCE_PARALLEL_DELTA.read_bytes())
        complete=restore_reference_distribution_source(parallel,REFERENCE_DELTA.read_bytes())
        original=json.loads((ROOT/'tests/conformance/prebuilt-installed-path-delta-v1.json').read_bytes())
        self.assertEqual(hashlib.sha256(complete).hexdigest(),
            original['tools/pipeline_reference_runtime.py']['current_sha256'])
        for mutant in (restored,current+b'\n',current.replace(b'max_workers=4',b'max_workers=3'),
                current.replace(b'timeout=10800',b'timeout=10801'),
                current.replace(b'capture_output=True',b'capture_output=False'),
                current.replace(b'check=False',b'check=True'),current.replace(b'\n',b'\r\n')):
            with self.subTest(source_sha256=hashlib.sha256(mutant).hexdigest()):
                self.assertNotEqual(mutant,current)
                with self.assertRaises(AssertionError):restore_reference_timeout_source(mutant,witness)
                forged=json.loads(witness)
                forged['current']={'bytes':len(mutant),'sha256':hashlib.sha256(mutant).hexdigest()}
                encoded=json.dumps(forged,sort_keys=True,indent=2).encode()+b'\n'
                with patch.dict(globals(),REFERENCE_TIMEOUT_DELTA_SHA256=hashlib.sha256(encoded).hexdigest()), \
                        self.assertRaisesRegex(AssertionError,'exact source authority'):
                    restore_reference_timeout_source(mutant,encoded)
        for mutation in ('schema','path','revision','prior','historical_float_bytes','float_bytes',
                'missing','extra','offset','float_offset','bool_offset','before','after'):
            forged=json.loads(witness)
            if mutation=='schema':forged['schema']+='x'
            elif mutation=='path':forged['path']='tools/check_pipeline_reference_install.py'
            elif mutation=='revision':forged['historical']['revision']='0'*40
            elif mutation=='prior':forged['historical']['sha256']='0'*64
            elif mutation=='historical_float_bytes':forged['historical']['bytes']=float(forged['historical']['bytes'])
            elif mutation=='float_bytes':forged['current']['bytes']=float(forged['current']['bytes'])
            elif mutation=='missing':forged['spans'].clear()
            elif mutation=='extra':forged['spans'].append(dict(forged['spans'][0]))
            elif mutation=='offset':forged['spans'][0]['offset']+=1
            elif mutation=='float_offset':forged['spans'][0]['offset']=float(forged['spans'][0]['offset'])
            elif mutation=='bool_offset':forged['spans'][0]['offset']=True
            else:forged['spans'][0][mutation]+=' '
            encoded=json.dumps(forged,sort_keys=True,indent=2).encode()+b'\n'
            with self.subTest(witness_mutation=mutation),patch.dict(globals(),
                    REFERENCE_TIMEOUT_DELTA_SHA256=hashlib.sha256(encoded).hexdigest()),self.assertRaises(AssertionError):
                restore_reference_timeout_source(current,encoded)
        with self.assertRaisesRegex(AssertionError,'Unreviewed reference timeout'):
            restore_reference_timeout_source(current,witness+b'\n')

    def test_reference_parallel_restoration_preserves_exact_full_chain_and_rejects_forgery(self):
        current=(ROOT/'tools/pipeline_reference_runtime.py').read_bytes()
        current=restore_reference_timeout_source(current,REFERENCE_TIMEOUT_DELTA.read_bytes())
        witness=REFERENCE_PARALLEL_DELTA.read_bytes()
        restored=restore_reference_parallel_source(current,witness)
        self.assertEqual({'bytes':len(restored),'sha256':hashlib.sha256(restored).hexdigest()},
            json.loads(REFERENCE_DELTA.read_bytes())['current'])
        complete=restore_reference_distribution_source(restored,REFERENCE_DELTA.read_bytes())
        original=json.loads((ROOT/'tests/conformance/prebuilt-installed-path-delta-v1.json').read_bytes())
        self.assertEqual(hashlib.sha256(complete).hexdigest(),
            original['tools/pipeline_reference_runtime.py']['current_sha256'])
        for mutant in (restored,current+b'\n',current.replace(b'max_workers=4',b'max_workers=3'),
                current.replace(b'timeout=1800',b'timeout=1801'),current.replace(b'\n',b'\r\n')):
            with self.subTest(source_sha256=hashlib.sha256(mutant).hexdigest()):
                self.assertNotEqual(mutant,current)
                with self.assertRaises(AssertionError):restore_reference_parallel_source(mutant,witness)
                forged=json.loads(witness)
                forged['current']={'bytes':len(mutant),'sha256':hashlib.sha256(mutant).hexdigest()}
                encoded=json.dumps(forged,sort_keys=True,indent=2).encode()+b'\n'
                with patch.dict(globals(),REFERENCE_PARALLEL_DELTA_SHA256=hashlib.sha256(encoded).hexdigest()), \
                        self.assertRaisesRegex(AssertionError,'exact source authority'):
                    restore_reference_parallel_source(mutant,encoded)
        for mutation in ('schema','path','revision','prior','float_bytes','order','missing','offset','before','after','overlap','bool_offset'):
            forged=json.loads(witness)
            if mutation=='schema':forged['schema']+='x'
            elif mutation=='path':forged['path']='tools/check_pipeline_reference_install.py'
            elif mutation=='revision':forged['historical']['revision']='0'*40
            elif mutation=='prior':forged['historical']['sha256']='0'*64
            elif mutation=='float_bytes':forged['current']['bytes']=float(forged['current']['bytes'])
            elif mutation=='order':forged['spans'].reverse()
            elif mutation=='missing':forged['spans'].pop()
            elif mutation=='overlap':forged['spans'][1]['offset']=0
            elif mutation=='bool_offset':forged['spans'][0]['offset']=True
            elif mutation=='offset':forged['spans'][0]['offset']+=1
            else:forged['spans'][0][mutation]+=' '
            encoded=json.dumps(forged,sort_keys=True,indent=2).encode()+b'\n'
            with self.subTest(witness_mutation=mutation),patch.dict(globals(),
                    REFERENCE_PARALLEL_DELTA_SHA256=hashlib.sha256(encoded).hexdigest()),self.assertRaises(AssertionError):
                restore_reference_parallel_source(current,encoded)
        with self.assertRaisesRegex(AssertionError,'Unreviewed reference parallel'):
            restore_reference_parallel_source(current,witness+b'\n')

    def test_reference_distribution_restoration_retains_the_complete_original_path_proof(self):
        current=(ROOT/'tools/pipeline_reference_runtime.py').read_bytes()
        current=restore_reference_timeout_source(current,REFERENCE_TIMEOUT_DELTA.read_bytes())
        current=restore_reference_parallel_source(current,REFERENCE_PARALLEL_DELTA.read_bytes())
        witness=REFERENCE_DELTA.read_bytes();proof=json.loads(witness)
        restored=restore_reference_distribution_source(current,witness)
        original=json.loads((ROOT/'tests/conformance/prebuilt-installed-path-delta-v1.json').read_bytes())
        self.assertEqual(hashlib.sha256(restored).hexdigest(),
            original['tools/pipeline_reference_runtime.py']['current_sha256'])
        mutants={
            'stale historical bytes':restored,
            'different current source':current.replace(b"paths.add('src/biocompiler/core_distribution.py')",
                b"paths.add('src/biocompiler/core_client.py')"),
            'weakened installed byte guard':current.replace(b'logical in sources and sha(',b'logical in sources or sha('),
            'extra function':current+b'\ndef unreviewed():\n    return True\n',
            'newline normalization':current.replace(b'\n',b'\r\n'),
        }
        for label,mutant in mutants.items():
            with self.subTest(change=label):
                self.assertNotEqual(mutant,current)
                with self.assertRaisesRegex(AssertionError,'Current reference runtime differs'):
                    restore_reference_distribution_source(mutant,witness)
                forged=json.loads(witness)
                forged['current']={'bytes':len(mutant),'sha256':hashlib.sha256(mutant).hexdigest()}
                with self.assertRaisesRegex(AssertionError,'Unreviewed reference-distribution source witness'):
                    restore_reference_distribution_source(mutant,json.dumps(forged,sort_keys=True,indent=2).encode()+b'\n')
        proof['spans'][0]['offset']+=1
        with self.assertRaisesRegex(AssertionError,'Unreviewed reference-distribution source witness'):
            restore_reference_distribution_source(current,json.dumps(proof,sort_keys=True,indent=2).encode()+b'\n')


if __name__=='__main__':unittest.main()
