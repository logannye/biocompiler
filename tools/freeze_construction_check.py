"""Retain complete independent construction-checker cases and fresh reports.

Existing artificial regression assertions run before their checker calls are
retained. Large repeated authority documents are stored by content hash, with
an independently bounded index and independently bounded complete documents.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import importlib
import json
from pathlib import Path
import sys
from unittest.mock import patch
from biocompiler.ir.circuit_construction import CircuitConstructionRequest, OPERATION_TYPES
from biocompiler.artifacts.circuit_construction import ConstructionCandidate
from biocompiler.verification.circuit_construction import CircuitConstructionAssessment, check_circuit_construction, reconstruct_for_check
from biocompiler.ir.serialization import fingerprint
from biocompiler.errors import SerializationError
ROOT=Path(__file__).resolve().parents[1]
CORPUS=ROOT/"tests/conformance/construction-check-v1.json"
DOCUMENTS=CORPUS.with_suffix("")
SCHEMA="biocompiler.construction_check_conformance.v1"
CLASSES={"request":CircuitConstructionRequest,"candidate":ConstructionCandidate,"assessment":CircuitConstructionAssessment}
EXCLUDED={
 "test_output_budget_is_checked_before_any_residue_reconstruction":"Monkeypatches a private Python residue budget and allocation helper; retained native default-budget preflight literals cover this obligation.",
 "test_processing_budget_counts_all_products_before_reconstruction":"Monkeypatches a private Python residue budget; retained native default-budget atomicity literals cover this obligation.",
 "test_assessment_diagnostic_limit_preserves_omitted_failure_severity":"Monkeypatches reporting limits and the payload checker result; native bounded reporting needs separate literal coverage.",
 "test_assessment_diagnostic_byte_limit_rejects_large_reports_before_encoding":"Monkeypatches reporting limits and the payload checker result; native bounded reporting needs separate literal coverage.",
}
def require(value,message):
    if not value: raise AssertionError(message)
def encoded(value): return (json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode()
def relocate(value):
    if isinstance(value,list): return [relocate(v) for v in value]
    if isinstance(value,dict):
        result={k:relocate(v) for k,v in value.items()}
        if set(result)=={"file","line","function"} and Path(result["file"]).is_absolute():
            result["file"]=Path(result["file"]).resolve().relative_to(ROOT).as_posix()
        return result
    return value

def bounds(value,maximum_bytes=16*1024*1024):
    pending=[(value,0)];count=0
    while pending:
        v,d=pending.pop();count+=1
        require(count<=250_000 and d<=128,"Construction checker fixture wire budget")
        if isinstance(v,dict): pending.extend((v,d+1) for pair in v.items() for v in pair)
        elif isinstance(v,list): pending.extend((v,d+1) for v in v)
    require(len(encoded(value))<=maximum_bytes,"Construction checker fixture byte budget")
    require(b"/Users/" not in encoded(value),"Machine-specific fixture authority")

def build_corpus():
    for directory in (str(ROOT),str(ROOT/"tests")):
        if directory not in sys.path: sys.path.insert(0,directory)
    f=importlib.import_module("test_circuit_construction_checking")
    documents={}; kinds={};cases=[];ledger=[]; counters=Counter(); expected_cache={}
    def retain(kind,value):
        raw=value.to_dict(); identity=fingerprint(raw)
        if identity not in documents:
            require(CLASSES[kind].from_dict(raw).fingerprint==identity,"Retained construction authority is not normalized")
            bounds(raw,4_000_000)
        documents[identity]=raw
        require(identity not in kinds or kinds[identity]==kind,"Conflicting retained document kind")
        kinds[identity]=kind
        return identity
    def capture(identity,request,candidate,assessment=None,origin="existing_python_assertion"):
        # A separately reconstructed fingerprint is part of each complete report.
        assessment=assessment or check_circuit_construction(candidate,expected_request=request)
        request_pin=request.fingerprint
        if request_pin not in expected_cache: expected_cache[request_pin]=reconstruct_for_check(request)
        expected=expected_cache[request_pin]
        require(expected.fingerprint==assessment.reconstructed_fingerprint,"Independent expected candidate pin differs")
        cases.append(dict(id=identity,request=retain("request",request),candidate=retain("candidate",candidate),
                          assessment=retain("assessment",assessment),reconstructed=retain("candidate",expected),origin=origin))
    current=[""]
    original=f.check_circuit_construction
    def checker(candidate,*,expected_request):
        result=original(candidate,expected_request=expected_request)
        index=counters[current[0]];counters[current[0]]+=1
        capture(current[0]+"/"+str(index),expected_request,candidate,result)
        return result
    original_fixture=f.fixture_request
    def fixture(*args,**kwargs):
        value=original_fixture(*args,**kwargs)
        return CircuitConstructionRequest.from_dict(relocate(value.to_dict()))
    methods=sorted(name for name in dir(f.CircuitConstructionCheckingTests) if name.startswith("test_"))
    with patch.object(f,"fixture_request",fixture),patch.object(f,"check_circuit_construction",checker):
        for method in methods:
            if method in EXCLUDED:
                ledger.append(dict(method=method,status="separate_budget_literal",reason=EXCLUDED[method],retained_calls=0));continue
            current[0]=method
            instance=f.CircuitConstructionCheckingTests(method)
            getattr(instance,method)()
            ledger.append(dict(method=method,status="source_assertions_executed",retained_calls=counters[method]))
    case_b=[]
    for variant in ("base","parameter-default","parameter-override"):
        full=json.loads((ROOT/"tests/conformance/case-b"/variant/"candidate.json").read_bytes())["construction"]
        request=CircuitConstructionRequest.from_dict(full["request"]);candidate=ConstructionCandidate.from_dict(full["candidate"])
        identity="case_b/"+variant;capture(identity,request,candidate,origin="complete_retained_case_b")
        case_b.append(dict(id=identity,variant=variant,path=["construction"]))
    # Report replay must bind each complete historical field, not a saved PASS.
    replay=[]
    baseline=next(item for item in cases if item["id"]=="test_literal_whole_copy_preserves_source_request_and_checked_derivation/0")
    for field in ("request_fingerprint","candidate_fingerprint","reconstructed_fingerprint"):
        raw=deepcopy(documents[baseline["assessment"]]);raw[field]="0"*64
        historical=CircuitConstructionAssessment.from_dict(raw)
        replay.append(dict(id="replay/"+field,source=baseline["id"],assessment=retain("assessment",historical),expected_code="construction_assessment_mismatch"))
    # Typed historical-report imports exercise every required field and claim.
    report_rejections=[]
    for field in documents[baseline["assessment"]]:
        report_rejections.append(dict(id="assessment/missing/"+field,source=baseline["assessment"],
                                      edits=[dict(op="remove",path=[field])],expected_code="missing_field"))
    for field,value,code in [("outcome","accepted","invalid_construction_assessment"),("complete",1,"invalid_type"),
          ("complete",False,"invalid_construction_assessment"),("diagnostics",["fail:forged"],"invalid_construction_assessment"),
          ("checker_version","old","invalid_construction_assessment"),("capability_version","old","invalid_construction_assessment"),
          ("construction_profile","old","invalid_construction_assessment"),("admission_policy","old","invalid_construction_assessment"),
          ("claim_scope","empirical","invalid_construction_assessment"),("biological_function","verified","invalid_construction_assessment"),
          ("empirical_validation","verified","invalid_construction_assessment"),("human_therapeutic_admission","admitted","invalid_construction_assessment"),
          ("candidate_fingerprint","A"*64,"invalid_construction_assessment")]:
        report_rejections.append(dict(id="assessment/change/"+field,source=baseline["assessment"],
            edits=[dict(op="set",path=[field],value=value)],expected_code=code))
    coverage=dict(methods=ledger,case_b=case_b,operations=sorted({step.operation.schema_version for item in cases
        for step in CircuitConstructionRequest.from_dict(documents[item["request"]]).steps}),
        outcomes=dict(sorted(Counter(documents[item["assessment"]]["outcome"] for item in cases).items())),
        cases=len(cases),documents=len(documents),replay_rejections=len(replay),assessment_rejections=len(report_rejections))
    require(coverage["operations"]==sorted(cls.schema_version for cls in OPERATION_TYPES),"Missing construction operation coverage")
    index=dict(schema_version=SCHEMA,claim_scope="Independent exact software construction correspondence only; no biological or human admission claim.",
               documents=[dict(id=k,kind=kinds[k],bytes=len(encoded(documents[k]))) for k in sorted(documents)],
               cases=cases,replay_rejections=replay,assessment_rejections=report_rejections,coverage=coverage)
    return index,documents

def apply_edits(raw,edits):
    value=deepcopy(raw)
    for edit in edits:
        target=value
        for key in edit["path"][:-1]:target=target[key]
        key=edit["path"][-1]
        if edit["op"]=="remove":del target[key]
        elif edit["op"]=="set":target[key]=deepcopy(edit["value"])
        else:raise AssertionError("Unknown checker corpus edit")
    return value

def check_corpus(index,documents):
    require(index["schema_version"]==SCHEMA,"Wrong checker corpus schema");bounds(index)
    declared={item["id"]:item for item in index["documents"]}
    require(set(declared)==set(documents),"Missing or extra construction fixture documents")
    require(index["coverage"]["documents"]==len(documents),"Stale document census")
    require(index["coverage"]["cases"]==len(index["cases"]),"Stale construction case census")
    require(index["coverage"]["replay_rejections"]==len(index["replay_rejections"]),"Stale replay census")
    require(index["coverage"]["assessment_rejections"]==len(index["assessment_rejections"]),"Stale report import census")
    require(len({case["id"] for case in index["cases"]})==len(index["cases"]),"Duplicate checker case")
    for identity,raw in documents.items():
        bounds(raw,4_000_000)
        require(fingerprint(raw)==identity and len(encoded(raw))==declared[identity]["bytes"],"Stale construction document identity")
        require(CLASSES[declared[identity]["kind"]].from_dict(raw).fingerprint==identity,"Invalid complete document")
    requests={}; candidates={}; expected_cache={}; assessment_cache={}
    for case in index["cases"]:
        request_pin=case["request"];candidate_pin=case["candidate"]
        if request_pin not in requests:requests[request_pin]=CircuitConstructionRequest.from_dict(documents[request_pin])
        if candidate_pin not in candidates:candidates[candidate_pin]=ConstructionCandidate.from_dict(documents[candidate_pin])
        request=requests[request_pin];candidate=candidates[candidate_pin]
        if request_pin not in expected_cache:expected_cache[request_pin]=reconstruct_for_check(request)
        if (request_pin,candidate_pin) not in assessment_cache:assessment_cache[request_pin,candidate_pin]=check_circuit_construction(candidate,expected_request=request)
        expected=expected_cache[request_pin];assessment=assessment_cache[request_pin,candidate_pin]
        require(encoded(expected.to_dict())==encoded(documents[case["reconstructed"]]),"Complete reconstruction differs")
        require(encoded(assessment.to_dict())==encoded(documents[case["assessment"]]),"Complete fresh assessment differs")
    for case in index["assessment_rejections"]:
        try:CircuitConstructionAssessment.from_dict(apply_edits(documents[case["source"]],case["edits"]))
        except SerializationError:pass
        else:raise AssertionError("Accepted historical assessment mutation")
    require(set(index["coverage"]["outcomes"])=={"pass","fail","unknown","unsupported"},"Missing checker outcome category")

def load():
    index=json.loads(CORPUS.read_bytes())
    docs={item["id"]:json.loads((DOCUMENTS/(item["id"]+".json")).read_bytes()) for item in index["documents"]}
    return index,docs

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--write",action="store_true");parser.add_argument("--check",action="store_true")
    args=parser.parse_args(argv);index,documents=build_corpus();check_corpus(index,documents)
    if args.write:
        DOCUMENTS.mkdir(exist_ok=True)
        expected={identity+".json" for identity in documents}
        for old in DOCUMENTS.glob("*.json"):
            if old.name not in expected:old.unlink()
        for identity,raw in documents.items():(DOCUMENTS/(identity+".json")).write_bytes(encoded(raw))
        CORPUS.write_bytes(encoded(index))
    else:
        require(CORPUS.read_bytes()==encoded(index),"Construction checker index drifted")
        require({p.name for p in DOCUMENTS.glob("*.json")}=={key+".json" for key in documents},"Construction document inventory drifted")
        for identity,raw in documents.items():require((DOCUMENTS/(identity+".json")).read_bytes()==encoded(raw),"Construction authority document drifted")
    print(json.dumps(dict(cases=len(index["cases"]),documents=len(documents),outcomes=index["coverage"]["outcomes"],
                         bytes=sum(len(encoded(v)) for v in documents.values())+len(encoded(index))),sort_keys=True))
if __name__=="__main__":main()
