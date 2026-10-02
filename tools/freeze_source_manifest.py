"""Freeze complete historical manifests and independent source-check expectations.

No native executable runs here. Python outputs are retained separately from
literal record expectations and source-preserving mutations. Native lowering
failure keys explicitly use the already-versioned native diagnostic code.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys

import biocompiler as bc
from biocompiler.errors import SerializationError
from biocompiler.ir.implementation_requirements import source_request_from_dict
from biocompiler.ir.serialization import fingerprint
from biocompiler.semantics.payload_execution import SourceExecutionManifest, derive_source_execution
from biocompiler.semantics.payload_requirements import PayloadDiagnostic, PayloadOutputRequirement
from biocompiler.verification.payload_architecture import _source_manifest_checks

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from examples.payload_architectures import _freeze, source_program
from tools.freeze_human_wrappers import portable
from tests.test_payload_execution import model, source

CORPUS = ROOT / "tests/conformance/source-manifest-v1.json"
SCHEMA = "biocompiler.source_manifest_conformance.v1"
PARSERS = {"manifest": SourceExecutionManifest, "output": PayloadOutputRequirement, "diagnostic": PayloadDiagnostic}
LITERAL_DIAGNOSTIC = {"code": "unresolved", "category": "missing_refinement", "source_node_ids": ["a", "a"], "message": "Declared only."}
LITERAL_OUTPUT = {"id": "output:r:a", "rule_id": "r", "action_id": "a", "guard_id": "g", "role_id": "role", "action_kind": "supplied.kind", "lineage": ["z", "", "z"], "trigger": "event", "activation": "explicit_duration", "product": "", "semantics": {"amount": 9007199254740993, "fraction": -0.0, "empty": None}}

def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()

def edited(raw, edits):
    raw = deepcopy(raw)
    for edit in edits:
        current = raw
        for key in edit["path"][:-1]: current = current[key]
        key = edit["path"][-1]
        if edit.get("delete"):
            del current[key]
        else:
            current[key] = deepcopy(edit["value"])
    return raw

def inventory(corpus):
    return fingerprint({key:corpus[key] for key in ("records", "rejections", "checks", "literal_expectations", "compatibility")})

def build_corpus():
    documents, records, rejections, checks = {}, [], [], []
    def document(raw):
        digest = fingerprint(raw); documents[digest] = deepcopy(raw); return digest
    def retain(identity, kind, value):
        raw = value.to_dict() if hasattr(value, "to_dict") else value
        result = PARSERS[kind].from_dict(raw)
        item = {"id": identity, "kind": kind, "document": document(raw), "normalized": document(result.to_dict()), "fingerprint":result.fingerprint}
        if kind == "manifest": item.update(complete=result.complete, source_fingerprint=result.source_fingerprint)
        records.append(item); return raw
    def reject(identity, kind, raw, edits, code):
        bad = edited(raw, edits)
        try: PARSERS[kind].from_dict(bad)
        except SerializationError: pass
        else: raise AssertionError("accepted rejection " + identity)
        rejections.append({"id":identity,"kind":kind,"document":document(raw),"edits":edits,"expected_code":code})
    def check(identity, manifest, authority=None, edits=(), native=None):
        raw = manifest.to_dict() if hasattr(manifest,"to_dict") else manifest
        authority = raw["source"] if authority is None else authority
        value = SourceExecutionManifest.from_dict(edited(raw, edits))
        expected = source_request_from_dict(authority)
        failures, unresolved, _ = _source_manifest_checks(value,expected)
        checks.append({"id":identity,"manifest":document(raw),"authority":document(authority),"edits":list(edits),
                       "legacy_expected":{"failures":failures,"unresolved":unresolved},
                       "expected":{"failures":failures if native is None else native,"unresolved":unresolved},
                       "mutated_fingerprint":value.fingerprint})
        return value
    diag=retain("literal/diagnostic","diagnostic",LITERAL_DIAGNOSTIC)
    output=retain("literal/output","output",LITERAL_OUTPUT)
    for category in ("unsupported_semantics","missing_refinement","contradiction"):
        retain("diagnostic/"+category,"diagnostic",dict(diag,category=category))
    for trigger in ("condition","event"):
        for activation in ("level","event","onset","explicit_duration"):
            retain("output/"+trigger+"/"+activation,"output",dict(output,trigger=trigger,activation=activation,product=None))
    retain("diagnostic/max_ids","diagnostic",dict(diag,source_node_ids=["x"]*1024))
    for case in "ABCDEF":
        manifest=derive_source_execution(portable(_freeze(source_program(case),case)))
        retain("architecture/"+case,"manifest",manifest);check("architecture/"+case,manifest)
    for variant in ("base","parameter-default","parameter-override"):
        root=ROOT/"tests/conformance/case-b"/variant
        candidate=json.loads((root/"candidate.json").read_bytes())
        request=json.loads((root/"request.json").read_bytes())
        raw=retain("case_b/"+variant,"manifest",candidate["execution"])
        check("case_b/"+variant,raw,request["circuit"]["profile"]["source_request"])
    wrappers=json.loads((ROOT/"tests/conformance/human-wrappers-v1.json").read_bytes())
    for kind in ("behavior_request","deployment_request","acceptance_request"):
        record=next(x for x in wrappers["records"] if x["id"]=="base/"+kind)
        manifest=derive_source_execution(source_request_from_dict(record["normalized"]))
        retain("wrapped/"+kind,"manifest",manifest);check("wrapped/"+kind,manifest)
    therapy,cells=model();build=portable(source(therapy))
    manifest=derive_source_execution(build)
    base=retain("empty_role","manifest",manifest);check("empty_role",base)
    # Full literal manifest assembled from a single original source declaration;
    # it intentionally has no Behavior and must retain an unresolved outcome.
    node=build.intent.nodes[0].to_dict(include_source=False)
    literal={"schema_version":"biocompiler.source_execution_manifest.v0.1",
        "claim_scope":"exact_declared_source_execution_no_empirical_function","source":build.to_dict(),"behavior":None,
        "roles":["n000001"],"outputs":[],"ledger":[{"id":"source:n000001","kind":"role","source_node_ids":["n000001"],"semantics":node},
        {"id":"source:complete_authority","kind":"source_authority","source_node_ids":["n000001"],"semantics":build.to_dict()}],
        "role_nodes":{"n000001":["n000001"]},"states":[],"channels":[],"diagnostics":[]}
    retain("literal/unavailable","manifest",literal);check("literal/unavailable",literal)
    retain("historical/arbitrary_inventories","manifest",dict(base,roles=["", "same","same"],role_nodes={"":"arbitrary", "also":[False,1,1.0]},ledger=[{"declared":True}],states=[{}],channels=[{}],outputs=[output],diagnostics=[diag]))
    retain("historical/max_roles","manifest",dict(base,roles=[""]*1024))
    retain("historical/max_ledger","manifest",dict(base,ledger=[{}]*1025))
    for name,changes in (("constraints",{"implementation_constraints":{"uninterpreted":True}}), ("preferences",{"preferences":{"rank":1}})):
        changed=bc.BuildRequest.from_dict(dict(build.to_dict(),**changes));m=derive_source_execution(changed)
        retain("unresolved/"+name,"manifest",m);check("unresolved/"+name,m)
    therapy,cells=model();therapy.goal("retained unsupported source")
    m=derive_source_execution(portable(source(therapy)));retain("unsupported/goal","manifest",m);check("unsupported/goal",m)
    for kind,raw in (("diagnostic",diag),("output",output),("manifest",base)):
        for key in raw: reject(kind+"/missing/"+key,kind,raw,[{"path":[key],"delete":True}],"missing_field")
        reject(kind+"/extra",kind,raw,[{"path":["unexpected"],"value":True}],"unknown_field")
    for key in ("code","message"):
        for label,value,code in (("empty","","invalid_source_manifest"),("null",None,"invalid_type")):
            reject("diagnostic/"+key+"/"+label,"diagnostic",diag,[{"path":[key],"value":value}],code)
    for key,value,code in (("category","future","invalid_source_manifest"),("source_node_ids",[""] ,"invalid_source_manifest"),("source_node_ids",["x"]*1025,"invalid_source_manifest"),("source_node_ids",None,"invalid_type")):
        reject("diagnostic/reject/"+str(len(rejections)),"diagnostic",diag,[{"path":[key],"value":value}],code)
    for key in ("id","rule_id","action_id","guard_id","role_id","action_kind"):
        reject("output/empty/"+key,"output",output,[{"path":[key],"value":""}],"invalid_source_manifest")
    for key,value,code in (("trigger","future","invalid_source_manifest"),("activation","future","invalid_source_manifest"),("lineage",[1],"invalid_type"),("product",False,"invalid_type"),("semantics",[],"invalid_type")):
        reject("output/reject/"+key,"output",output,[{"path":[key],"value":value}],code)
    for key,value,code in (("schema_version","future","unsupported_schema"),("claim_scope","verified","unsupported_schema"),("roles",[""]*1025,"invalid_source_manifest"),("roles",[False],"invalid_type"),("role_nodes",[],"invalid_type"),("ledger",[{}]*1026,"invalid_source_manifest"),("states",[False],"invalid_type"),("channels",None,"invalid_type")):
        reject("manifest/reject/"+key+"/"+str(len(rejections)),"manifest",base,[{"path":[key],"value":value}],code)
    base_b=documents[next(x["document"] for x in records if x["id"]=="case_b/base")]
    base_d=documents[next(x["document"] for x in records if x["id"]=="architecture/D")]
    changes=[("roles",["roles"],[]),("ledger",["ledger"],[]),("role_nodes",["role_nodes"],{}),("outputs",["outputs"],[]),("states",["states"],[]),
        ("output_guard",["outputs",0,"guard_id"],"changed"),("output_lineage",["outputs",0,"lineage"],[]),("output_primitive",["outputs",0,"semantics","primitive_action","attributes"],{}),
        ("ledger_authority",["ledger",len(base_b["ledger"])-1,"semantics"],{}),("state_assignment",["states",0,"assignments"],[])]
    for name,path,value in changes: check("mutation/"+name,base_b,edits=[{"path":path,"value":value}])
    for name,path,value in (("channels",["channels"],[]),("channel_transport",["channels",0,"transport"],"inferred"),("channel_receivers",["channels",0,"receivers"],[]),("channel_senders",["channels",0,"senders"],[])):
        check("mutation/"+name,base_d,edits=[{"path":path,"value":value}])
    check("mutation/source_authority",base_b,authority=documents[next(x["document"] for x in records if x["id"]=="case_b/parameter-default")]["source"], native=["source_authority","source_manifest_ledger","source_behavior:lowering_source_identity"])
    check("mutation/behavior_missing",base_b,edits=[{"path":["behavior"],"value":None}])
    check("mutation/behavior_identity",base_b,edits=[{"path":["behavior","name"],"value":"changed"}],native=["source_behavior:lowering_source_identity"])
    check("historical/diagnostics_are_not_authority",base_b,edits=[{"path":["diagnostics"],"value":[diag]}])
    literals=[{"id":"literal/diagnostic","kind":"diagnostic","expected":diag},{"id":"literal/output","kind":"output","expected":output},{"id":"literal/unavailable","kind":"manifest","expected":literal}]
    result={"schema_version":SCHEMA,"claim_scope":"Historical structural imports and independent source correspondence only; no candidate behavior, construction, empirical validation or admission.",
        "documents":documents,"records":records,"rejections":rejections,"checks":checks,"literal_expectations":literals,
        "compatibility":{"native_boundary":"biocompiler.native_source_manifest.v0.1","checker_version":"biocompiler.ocaml.source_manifest_check.v0.1","lowering_failure_exception":"source_behavior:<native code> replaces Python prose; separately retained and tested","diagnostics":"Historical manifest diagnostics cannot supply expected source authority."}}
    result["inventory_sha256"]=inventory(result)
    return result

def check_corpus(corpus):
    assert corpus["schema_version"]==SCHEMA
    assert corpus["inventory_sha256"]==inventory(corpus)
    for group in ("records","rejections","checks"):
        assert len({x["id"] for x in corpus[group]})==len(corpus[group]), "duplicate IDs"
    for key,raw in corpus["documents"].items(): assert fingerprint(raw)==key
    for item in corpus["records"]:
        actual=PARSERS[item["kind"]].from_dict(corpus["documents"][item["document"]])
        assert actual.fingerprint==item["fingerprint"] and actual.to_dict()==corpus["documents"][item["normalized"]]
    for item in corpus["checks"]:
        raw=edited(corpus["documents"][item["manifest"]],item["edits"])
        value=SourceExecutionManifest.from_dict(raw)
        failure,unresolved,_=_source_manifest_checks(value,source_request_from_dict(corpus["documents"][item["authority"]]))
        assert {"failures":failure,"unresolved":unresolved}==item["legacy_expected"]
        assert value.fingerprint==item["mutated_fingerprint"]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--write",action="store_true");args=parser.parse_args()
    corpus=build_corpus();check_corpus(corpus);content=encoded(corpus)
    if args.write: CORPUS.write_bytes(content)
    else: assert CORPUS.read_bytes()==content,"Source manifest corpus is stale"
    print(json.dumps({"records":len(corpus["records"]),"rejections":len(corpus["rejections"]),"checks":len(corpus["checks"]),"documents":len(corpus["documents"]),"bytes":len(content),"inventory":corpus["inventory_sha256"]}))
if __name__=="__main__":main()
