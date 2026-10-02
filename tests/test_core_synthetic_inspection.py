"""Strict helper transport with complete original literals and Python children."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.core_client import CoreClient, CoreProtocolError, CoreRejected
from biocompiler.core_synthetic_inspection import (
    OPERATIONS, SyntheticInspectionClient, capability_profile, effective_resources,
)
from test_core_synthetic_producer import capabilities as producer_capabilities, encoded, envelope, fixture
from tools.synthetic_inspection_corpus import Corpus

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def cases():
    original = Corpus()
    selected = {}
    for case in original.cases:
        key = (case["api"], "error" if case["error"] else encoded(case["expected_public"].get("properties",{})))
        # Keep original fresh/stale and native Boolean outcomes as distinct cases.
        if case["api"] in ("CheckResult.is_fresh","DependencySnapshot.changed","ComponentRegistry.verify_selection"):
            key = (case["api"], encoded(case["expected_public"]))
        selected.setdefault(key,case)
    # Explicit order over complete nodes from the immutable original generator
    # fixture. This literal is independent of any current Python graph routine.
    mechanism = fixture("generate-synthetic")[1]["mechanism"]
    order = ("active:response.rest","inactive:response.rest","input:n000003:present","input:n000004:present",
             "expression:n000008","aggregate:response.rest","select:response.rest","output:response.rest")
    known = {node["id"]:node for node in mechanism["nodes"]}
    selected["topology",None] = {"id":"original-candidate-topology-literal","api":"MechanismProgram.topological_nodes",
        "operation":"inspect-synthetic-mechanism","payload":{"profile":capability_profile()["profile"],"limits":None,"mechanism":mechanism},
        "expected_value":{"nodes":[known[key] for key in order]},"error":None,
        "expected_public":{"value":[known[key] for key in order],"properties":{}}}
    return tuple(selected.values())


def representative(operation):
    return next(case for case in cases() if case["operation"]==operation and case["error"] is None)


def capabilities():
    result=producer_capabilities()
    result["operations"].extend(OPERATIONS)
    result["profiles"]["synthetic_inspection"]=capability_profile()
    result["validation_scopes"].append(capability_profile()["validation_scope"])
    return result


def receipt(case,payload=None):
    payload=case["payload"] if payload is None else payload
    profile=capability_profile();value=deepcopy(case["expected_value"])
    return {"schema_version":profile["result_schema"],"profile":profile["profile"],"service_implementation":profile["implementation"],
        "operation":case["operation"],"resources":effective_resources(payload["limits"]),"validation_scope":profile["validation_scope"],
        "claim_scope":profile["claim_scope"],"supplied_authority_fingerprint":hashlib.sha256(encoded(payload)).hexdigest(),
        "input_fingerprints":{key:hashlib.sha256(encoded(value)).hexdigest() for key,value in payload.items() if key not in ("profile","limits")},
        "value":value,"value_fingerprint":hashlib.sha256(encoded(value)).hexdigest()}


def fixture_executable(directory,selected=None):
    selected=cases() if selected is None else selected
    table={}
    for case in selected:
        error=case["error"]
        table[hashlib.sha256(encoded(case["payload"])).hexdigest()]={"status":"error" if error else "ok",
            "result":None if error else receipt(case),"diagnostics":[error] if error else [],"exit_code":2 if error else 0}
    data=directory/"inspection-fixture.json";data.write_bytes(encoded({"capabilities":capabilities(),"table":table}))
    executable=directory/"python-inspection-fixture"
    executable.write_text("#!"+sys.executable+"\nimport hashlib,json,pathlib,sys\n"+
        "data=json.loads(pathlib.Path("+repr(str(data))+").read_bytes());request=json.load(sys.stdin)\n"+
        "def encoded(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()\n"+
        "row={'status':'ok','result':data['capabilities'],'diagnostics':[],'exit_code':0} if request['operation']=='capabilities' else data['table'][hashlib.sha256(encoded(request['payload'])).hexdigest()]\n"+
        "response={'protocol':'biocompiler.core.v1','request_id':request['request_id'],'operation':request['operation'],'status':row['status'],'result':row['result'],'diagnostics':row['diagnostics'],'core':{'implementation':'ocaml','version':'0.1.0','protocol':'biocompiler.core.v1','executable':'core'}}\n"+
        "sys.stdout.buffer.write(encoded(response)+b'\\n');sys.exit(row['exit_code'])\n")
    executable.chmod(0o700)
    return executable


class SyntheticInspectionClientTests(unittest.TestCase):
    def setUp(self):
        self.client=SyntheticInspectionClient(CoreClient(Path(sys.executable)))
        self.calls=[]

    def exchange(self,case,*,mutate=None,capability_mutate=None,on_negotiate=None):
        def invoke(_executable,raw,_timeout,_cancelled):
            request=json.loads(raw);self.calls.append(request)
            if request["operation"]=="capabilities":
                value=capabilities()
                if capability_mutate:capability_mutate(value)
                if on_negotiate:on_negotiate()
                return encoded(envelope(request,value)),0
            self.assertEqual(encoded(request["payload"]),encoded(case["payload"]))
            if case["error"]:
                response=envelope(request,None);response.update(status="error",diagnostics=[case["error"]])
                return encoded(response),2
            value=receipt(case)
            if mutate:mutate(value)
            return encoded(envelope(request,value)),0
        return patch("biocompiler.core_client._exchange",side_effect=invoke)

    def test_all_eight_operations_complete_receipts_and_defensive_views(self):
        self.assertEqual(encoded(capability_profile()),encoded(json.loads((ROOT/"protocol/synthetic-inspection-v1.json").read_bytes())))
        for operation in OPERATIONS:
            case=representative(operation);raw=b" \n"+encoded(case["payload"])+b"\t"
            with self.subTest(operation=operation),self.exchange(case):
                result=self.client.call_document(operation,raw)
            self.assertEqual(result.input_document,raw)
            self.assertEqual(result.authority_json,encoded(case["payload"]))
            self.assertEqual(result.receipt_json,encoded(receipt(case)))
            self.assertEqual(result.value_json,encoded(case["expected_value"]))
            result.value.clear();result.receipt.clear();result.input_fingerprints.clear()
            self.assertEqual(result.value,case["expected_value"])
            with self.assertRaises(FrozenInstanceError):result.value_json=b"{}"

    def test_complete_input_is_frozen_before_capability_negotiation(self):
        case=representative("inspect-synthetic-mechanism");mechanism=deepcopy(case["payload"]["mechanism"])
        with self.exchange(case,on_negotiate=mechanism.clear):
            result=self.client.call(case["operation"],mechanism=mechanism)
        self.assertEqual(result.authority_json,encoded(case["payload"]))

    def test_wrong_role_limits_and_incompatible_capabilities_fail_closed(self):
        case=representative("inspect-synthetic-mechanism")
        with patch("biocompiler.core_client._exchange") as exchange:
            with self.assertRaises(CoreProtocolError):SyntheticInspectionClient(CoreClient(Path(sys.executable),role="verify")).call_document(case["operation"],encoded(case["payload"]))
            for bad in (True,0,1.5):
                payload=deepcopy(case["payload"]);payload["limits"]={**capability_profile()["default_limits"],"max_work":bad}
                with self.assertRaises(CoreProtocolError):self.client.call_document(case["operation"],encoded(payload))
            exchange.assert_not_called()
        for mutate in (lambda x:x["operations"].remove(OPERATIONS[-1]),
                       lambda x:x["profiles"]["synthetic_inspection"].update(claim_scope="unbounded"),
                       lambda x:x["profiles"]["synthetic_inspection"]["resources"]["protocol"].update(max_work=50000000.0)):
            self.calls=[]
            with self.exchange(case,capability_mutate=mutate),self.assertRaises(CoreProtocolError):
                self.client.call_document(case["operation"],encoded(case["payload"]))
            self.assertEqual(len(self.calls),1)

    def test_rehashed_scope_resource_input_and_numeric_value_forgeries_rejected(self):
        case=representative("verify-synthetic-registry-selection")
        def number(value):
            value["value"]["valid"]=1
            value["value_fingerprint"]=hashlib.sha256(encoded(value["value"])).hexdigest()
        for mutate in (lambda x:x.update(extra=True),lambda x:x.update(operation="lock-synthetic-registry"),
                       lambda x:x.update(claim_scope="universal acceptance"),
                       lambda x:x["resources"]["protocol"].update(max_work=50000000.0),
                       lambda x:x.update(supplied_authority_fingerprint="0"*64),
                       lambda x:x["input_fingerprints"].update(request="0"*64),
                       lambda x:x.update(value_fingerprint="0"*64),number):
            with self.exchange(case,mutate=mutate),self.assertRaises(CoreProtocolError):
                self.client.call_document(case["operation"],encoded(case["payload"]))
        coverage=next(x for x in cases() if x["api"]=="CheckResult.exercised_requirement_ids")
        def forged_freshness(value):
            value["value"]["freshness"]={"changed_dependencies":[],"fresh":True,"status":"fresh"}
            value["value_fingerprint"]=hashlib.sha256(encoded(value["value"])).hexdigest()
        with self.exchange(coverage,mutate=forged_freshness),self.assertRaises(CoreProtocolError):
            self.client.call_document(coverage["operation"],encoded(coverage["payload"]))

    def test_rehashed_incomplete_nested_records_and_wrong_numeric_kinds_rejected(self):
        probes = (
            ("inspect-synthetic-mechanism", ("nodes", 0, "output", "dtype"), "name", None),
            ("inspect-synthetic-mechanism", ("nodes", 0, "output"), "schema_version", None),
            ("lock-synthetic-registry", ("lock", "components", 0), "content_fingerprint", None),
            ("resolve-synthetic-registry", ("instances",), None, None),
            ("select-synthetic-registry", ("selection", "alternatives", 0), "preference_rank", None),
            ("select-synthetic-registry", ("selection", "alternatives", 0), "preference_rank", True),
            ("select-synthetic-registry", ("selection", "admission"), "evidence", None),
        )
        for operation, path, key, replacement in probes:
            case = representative(operation)
            def mutate(result):
                record = result["value"]
                for item in path:
                    record = record[item]
                if key is None:
                    record = next(iter(record.values()))["ports"][0]
                    del record["domain"]
                elif replacement is None:
                    del record[key]
                else:
                    record[key] = replacement
                result["value_fingerprint"] = hashlib.sha256(encoded(result["value"])).hexdigest()
            with self.subTest(operation=operation, path=path, key=key), self.exchange(case, mutate=mutate):
                with self.assertRaises(CoreProtocolError):
                    self.client.call_document(operation, encoded(case["payload"]))

    def test_complete_native_rejection_is_preserved(self):
        case=next(x for x in cases() if x["error"])
        with self.exchange(case),self.assertRaises(CoreRejected) as caught:
            self.client.call_document(case["operation"],encoded(case["payload"]))
        self.assertEqual(caught.exception.response.diagnostics[0].message,case["error"]["message"])
        self.assertEqual(caught.exception.response.diagnostics[0].code,case["error"]["code"])

    def test_actual_python_protocol_children_all_eight_operations_and_original_rejection(self):
        selected=[representative(operation) for operation in OPERATIONS]+[next(x for x in cases() if x["error"])]
        with tempfile.TemporaryDirectory() as directory:
            executable=fixture_executable(Path(directory),selected)
            client=SyntheticInspectionClient(CoreClient(executable,expected_sha256=hashlib.sha256(executable.read_bytes()).hexdigest()))
            for case in selected:
                with self.subTest(operation=case["operation"],error=case["error"]):
                    if case["error"]:
                        with self.assertRaises(CoreRejected):client.call_document(case["operation"],encoded(case["payload"]))
                    else:
                        result=client.call_document(case["operation"],encoded(case["payload"]))
                        self.assertEqual(result.value,case["expected_value"])


if __name__=="__main__":unittest.main()
