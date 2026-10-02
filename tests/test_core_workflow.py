"""Opaque workflow adapter tests use full original records and Python children.

The children implement transport fixtures only. Native semantics and the full
original corpus remain separate mandatory hosted checks.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import FrozenInstanceError
import builtins
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from biocompiler import core_artifacts as artifacts
from biocompiler.core_client import (
    CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL, CoreCancelled, CoreClient,
    CoreProtocolError, CoreRejected, CoreUnsupported, encode_json,
)
from biocompiler.core_workflow import (
    OPERATIONS, WorkflowClient, capability_profile, default_limits, effective_resources,
)

ROOT = Path(__file__).resolve().parents[1]
FROZEN_RECORDS = (
    "9b5811a05e9a5d4d83ee19ffef622e8214f077455e0a30600cf88092736d53fb",
    "897cecc35c9714960b9b99970f7d86f18661316ecf2bd0881efd59f7cf5e6343",
    "db68cc8fb08d3116c032cb679fea607be7cf1ddfe27e3b03157b0d02071722b9",
    "1c61b99d138c439a5866b462180d3ebb139bf49c7a7ab92a509942de49b8a574",
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture_records():
    directory = ROOT / "tests/conformance/realization-workflow-v1"
    records = []
    for identity in FROZEN_RECORDS:
        payload = (directory / (identity + ".json")).read_bytes()
        if not payload.endswith(b"\n") or sha(payload[:-1]) != identity:
            raise AssertionError("Full immutable workflow fixture changed")
        records.append(json.loads(payload))
    # Two operation/mode combinations are absent from original successful calls.
    # Independently execute the original Python oracle in a fixture-only child,
    # before the adapter's no-semantics guard. Pin both complete results.
    script = r'''
import json,sys
from biocompiler.compiler.verification_workflow import SyntheticVerificationRequest,run_synthetic_verification
values=json.load(sys.stdin)
explore=values[0]['request'];explore['mode']='model'
reduce=values[1]['request'];reduce['mode']='candidate'
reduce['signature']={'schema_version':'biocompiler.failure_signature.v0.1','kind':'diagnostic',
 'requirement_id':None,'code':'candidate_lineage','rule_id':None,'specification_id':None,
 'contact_id':None,'state':None,'node_id':None}
print(json.dumps([run_synthetic_verification(SyntheticVerificationRequest.from_dict(raw)).to_dict()
 for raw in (explore,reduce)],sort_keys=True,separators=(',',':'),ensure_ascii=False))
'''
    output = subprocess.run([sys.executable, "-c", script], input=canonical(records[2:]),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30,
        cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    additional = json.loads(output.stdout)
    expected = ("2f9006dfb440a86062e606146c7240b61e1b1a1cfa3f92cf00e8de1815094ce5",
                "a16a92cc61d605134081e581ff77e5c2ed758b0f2b78cb922dbad4fd08e18a4c")
    if tuple(sha(canonical(value)) for value in additional) != expected:
        raise AssertionError("Independent complete workflow counterparts changed")
    return records + additional


def capabilities():
    return {"schema_version": CAPABILITIES_SCHEMA, "operations": ["capabilities", *OPERATIONS],
        "intent_schemas": [], "canonicalization": "python-json-v1",
        "validation_scopes": [capability_profile()["validation_scope"]],
        "profiles": {"artifact_transport": deepcopy(artifacts.TRANSPORT_PROFILE),
                     "verification_workflow": capability_profile()},
        "limits": dict(LIMITS), "claim_scope": "Transport fixture only."}


def receipt_for(control, authority, retained, record, role):
    profile = capability_profile()
    request, normalized = json.loads(authority), json.loads(record)["request"]
    return {"schema_version": "biocompiler.core.verification_workflow_result.v1",
        "profile": profile["profile"], "operation": control["operation"], "executable": role,
        "request_id": control["request_id"], "validation_scope": profile["validation_scope"],
        "implementation_version": profile["implementation_version"], "workflow_version": profile["workflow_version"],
        "workflow_operation": request["operation"], "mode": request["mode"],
        "authority_fingerprint": sha(canonical(request)), "request_fingerprint": sha(canonical(normalized)),
        "retained_record_fingerprint": None if retained is None else sha(canonical(json.loads(retained))),
        "record_fingerprint": sha(record),
        "resources": effective_resources(control["payload"]["operation_payload"]["limits"])}


@contextmanager
def no_semantics():
    original = builtins.__import__
    forbidden = ("biocompiler.compiler", "biocompiler.ir", "biocompiler.synthesis", "biocompiler.models",
                 "biocompiler.semantics", "biocompiler.verification", "biocompiler.registry")

    def guarded(name, *args, **kwargs):
        if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden):
            raise AssertionError("Workflow adapter imported Python semantics: " + name)
        return original(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=guarded):
        yield


class WorkflowTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = fixture_records()

    def setUp(self):
        self.calls = []
        self.record = self.records[0]
        self.core = CoreClient(Path(sys.executable), role="verify")
        self.client = WorkflowClient(self.core)

    @contextmanager
    def exchange(self, *, mutate=None, capability_mutation=None, record_mutation=None,
                 rejected=None, after_negotiation=None):
        def response(request, result, status="ok"):
            return encode_json({"protocol": PROTOCOL, "request_id": request["request_id"],
                "operation": request["operation"], "status": status, "result": result if status == "ok" else None,
                "diagnostics": [] if status == "ok" else [{"code": "workflow_work_limit", "message": "Exhausted", "path": "authority"}],
                "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL,
                         "executable": self.core.role}}), {"ok": 0, "error": 2, "unsupported": 3}[status]

        def negotiate(_executable, raw, _timeout, _cancelled):
            request = json.loads(raw); self.calls.append(request)
            self.assertEqual(request["operation"], "capabilities")
            value = capabilities()
            if capability_mutation: capability_mutation(value)
            if after_negotiation: after_negotiation()
            return response(request, value)

        def artifact(_core, raw, arguments, files, output, output_limit, cancelled):
            if cancelled is not None and cancelled(): raise CoreCancelled("Fixture cancellation")
            request = json.loads(raw); self.calls.append(request)
            source = files[0]; source.seek(0); authority = source.read()
            self.assertEqual(source.mode, "rb")
            retained = None
            if arguments[2] != "-":
                files[1].seek(0); retained = files[1].read()
                self.assertEqual(files[1].mode, "rb")
            self.assertEqual(request["payload"]["authority"], artifacts._descriptor(authority))
            self.assertEqual(request["payload"]["retained_record"], None if retained is None else artifacts._descriptor(retained))
            if rejected:
                return response(request, None, rejected)
            value = deepcopy(self.record)
            if record_mutation: record_mutation(value)
            record = canonical(value); self.assertLessEqual(len(record), output_limit)
            output.write(record); output.flush()
            semantic = receipt_for(request, authority, retained, record, self.core.role)
            if mutate: mutate(semantic)
            return response(request, {"schema_version": "biocompiler.core.artifact_response.v1",
                "transport": "biocompiler.core.artifact_transport.v1", "authority": artifacts._descriptor(authority),
                "retained_record": None if retained is None else artifacts._descriptor(retained),
                "artifact": artifacts._descriptor(record), "result": semantic}, rejected or "ok")

        with patch("biocompiler.core_client._exchange", side_effect=negotiate), \
                patch("biocompiler.core_artifacts._exchange_artifacts", side_effect=artifact), no_semantics():
            yield

    def call(self, *, replay=False, **kwargs):
        request = canonical(self.record["request"])
        return (self.client.replay(request, canonical(self.record), **kwargs) if replay
                else self.client.run(request, **kwargs))

    def test_all_six_modes_both_operations_full_original_bytes_and_defensive_access(self):
        for value in self.records:
            self.record = value
            for replay in (False, True):
                with self.subTest(operation=value["request"]["operation"], mode=value["request"]["mode"], replay=replay), self.exchange():
                    result = self.call(replay=replay)
                    self.assertEqual(result.record_json, canonical(value))
                    self.assertEqual(result.record_fingerprint, sha(canonical(value)))
                    self.assertEqual(result.record, value)
                    result.record.clear(); result.receipt.clear(); result.envelope.clear()
                    self.assertEqual(result.record, value)
                    with self.assertRaises(FrozenInstanceError): result.mode = "other"
        self.assertEqual(len(self.calls), 24)
        self.assertEqual({(x["request"]["operation"], x["request"]["mode"]) for x in self.records},
                         {(op, mode) for op in ("check", "explore", "reduce") for mode in ("candidate", "model")})

    def test_exact_profile_mutations_fail_during_same_negotiation(self):
        self.assertEqual(sha(canonical(capability_profile())),
            "6961059d7eb2dc55cef1ede11b09faf37043e9c7cb040da90f6a09f95fa38643")
        changes = [lambda c: c["profiles"].pop("verification_workflow"),
            lambda c: c["profiles"]["verification_workflow"].update(engine_version="changed"),
            lambda c: c["profiles"]["verification_workflow"]["resources"]["workflow"].update(max_work=float(default_limits()["max_work"])),
            lambda c: c["profiles"]["verification_workflow"]["resources"]["synthetic"].pop("realization"),
            lambda c: c["validation_scopes"].clear(), lambda c: c["operations"].remove(OPERATIONS[1])]
        for change in changes:
            self.calls.clear()
            with self.subTest(change=change), self.exchange(capability_mutation=change), self.assertRaises(CoreProtocolError): self.call()
            self.assertEqual(len(self.calls), 1)
        mutable = capability_profile(); mutable.clear()
        self.assertIn("resources", capability_profile())

    def test_full_receipt_and_authority_identity_mutations_fail(self):
        changes = [lambda r: r.update(extra=True), lambda r: r.update(profile="wrong"),
            lambda r: r.update(implementation_version="python"), lambda r: r.update(workflow_version="changed"),
            lambda r: r.update(validation_scope="empirical"), lambda r: r.update(executable="core"),
            lambda r: r.update(request_id="other"), lambda r: r.update(operation=OPERATIONS[1]),
            lambda r: r.update(workflow_operation="reduce"), lambda r: r.update(mode="candidate"),
            lambda r: r.update(authority_fingerprint="0" * 64), lambda r: r.update(request_fingerprint="0" * 64),
            lambda r: r.update(retained_record_fingerprint="0" * 64), lambda r: r.update(record_fingerprint="0" * 64),
            lambda r: r["resources"]["realization"].update(max_work=1),
            lambda r: r["resources"]["workflow"].update(max_report_nodes=1_000_000.0)]
        for change in changes:
            with self.subTest(change=change), self.exchange(mutate=change), self.assertRaises(CoreProtocolError): self.call()

    def test_record_schema_claim_and_replay_complete_content_are_checked(self):
        changes = [lambda r: r.update(extra=True), lambda r: r.update(claim_scope="empirical"),
            lambda r: r.update(workflow_version="changed"), lambda r: r["result"].update(schema_version=[]),
            lambda r: r["request"].update(mode="candidate"), lambda r: r["result"].update(schema_version="biocompiler.history_reduction.v0.1")]
        for change in changes:
            with self.subTest(change=change), self.exchange(record_mutation=change), self.assertRaises(CoreProtocolError): self.call()
        with self.exchange(record_mutation=lambda r: r["result"].update(coverage=[])), self.assertRaisesRegex(CoreProtocolError, "complete retained"):
            self.call(replay=True)

    def test_raw_bytes_and_numeric_identity_preserved_without_semantic_hydration(self):
        request = json.dumps(self.record["request"], ensure_ascii=True, indent=2).encode()
        retained = json.dumps(self.record, ensure_ascii=True, indent=2).encode()
        with self.exchange():
            result = self.client.replay(request, retained)
        self.assertEqual(result.record_json, canonical(self.record))
        self.assertEqual(self.calls[-1]["payload"]["authority"], artifacts._descriptor(request))
        self.assertEqual(self.calls[-1]["payload"]["retained_record"], artifacts._descriptor(retained))
        for value in (0, 0.0, -0.0, 1, 1.0):
            raw = deepcopy(self.record["request"]); raw["until"] = value
            with self.exchange(): result = self.client.run(canonical(raw))
            self.assertEqual(result.authority_fingerprint, sha(canonical(raw)))
        for value in (0.0, -0.0):
            altered = deepcopy(self.record)
            altered["request"]["history"][0]["time"] = value
            with self.exchange(), self.assertRaisesRegex(CoreProtocolError, "complete retained"):
                self.client.replay(canonical(self.record["request"]), canonical(altered))

    def test_exact_limit_reductions_are_frozen_and_leaf_ceilings_remain_fixed(self):
        defaults = default_limits()
        invalid = [{}, True, {**defaults, "extra": 1}, {**defaults, "max_work": True},
                   {**defaults, "max_work": 0}, {**defaults, "max_work": 1.0},
                   {**defaults, "max_work": defaults["max_work"] + 1}]
        for value in invalid:
            self.calls.clear()
            with self.subTest(limits=value), self.exchange(), self.assertRaises(CoreProtocolError): self.call(limits=value)
            self.assertEqual(self.calls, [])
        limits = {key: value - 1 for key, value in defaults.items()}; original = dict(limits)
        with self.exchange(after_negotiation=lambda: limits.update(max_work=1)):
            result = self.call(limits=limits)
        self.assertEqual(self.calls[-1]["payload"]["operation_payload"]["limits"], original)
        self.assertEqual(result.receipt["resources"]["workflow"]["max_work"], original["max_work"])
        self.assertEqual(result.receipt["resources"]["realization"]["max_work"], 50_000_000)
        self.assertEqual(effective_resources({**defaults, "max_work": 7})["synthetic"]["realization"]["max_work"], 7)
        with self.exchange(), self.assertRaisesRegex(CoreProtocolError, "node"):
            self.call(limits={**defaults, "max_report_nodes": 1})

    def test_native_rejections_and_transport_cancellation_do_not_fallback(self):
        for status, error in (("error", CoreRejected), ("unsupported", CoreUnsupported)):
            with self.exchange(rejected=status), self.assertRaises(error) as caught: self.call()
            self.assertEqual(caught.exception.response.diagnostics[0].code, "workflow_work_limit")
        with self.exchange(), self.assertRaises(CoreCancelled): self.call(cancelled=lambda: True)
        for raw in (bytearray(b"{}"), b'{"x":1,"x":2}'):
            self.calls.clear()
            with self.exchange(), self.assertRaises(CoreProtocolError): self.client.run(raw)
            self.assertEqual(self.calls, [])

    def test_native_authority_rejection_precedes_malformed_retained_record_decode(self):
        with self.exchange(rejected="error"), self.assertRaises(CoreRejected) as caught:
            self.client.replay(canonical(self.record["request"]), b'{"unfinished":')
        self.assertEqual(caught.exception.response.diagnostics[0].code, "workflow_work_limit")
        self.assertEqual([call["operation"] for call in self.calls], ["capabilities", OPERATIONS[1]])


CHILD = r'''
import hashlib,json,os,sys
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def descriptor(raw):return {'bytes':len(raw),'sha256':sha(raw)}
control=json.load(sys.stdin)
response={'protocol':'biocompiler.core.v1','request_id':control['request_id'],'operation':control['operation'],
 'status':'ok','diagnostics':[],'core':{'implementation':'ocaml','version':'0.1.0','protocol':'biocompiler.core.v1','executable':ROLE}}
if control['operation']=='capabilities':response['result']=CAPABILITIES
else:
 assert sys.argv[1]=='--artifact-fds-v1'
 with os.fdopen(os.dup(int(sys.argv[2])),'rb') as f:authority=f.read()
 retained=None
 if sys.argv[3]!='-':
  with os.fdopen(os.dup(int(sys.argv[3])),'rb') as f:retained=f.read()
 request=json.loads(authority);record=RECORDS[(request['operation'],request['mode'])]
 doc=json.loads(record);profile=CAPABILITIES['profiles']['verification_workflow']
 assert control['payload']['operation_payload']=={'profile':profile['profile'],'limits':None}
 assert control['payload']['authority']==descriptor(authority)
 assert control['payload']['retained_record']==(None if retained is None else descriptor(retained))
 receipt={'schema_version':'biocompiler.core.verification_workflow_result.v1','profile':profile['profile'],
  'operation':control['operation'],'executable':ROLE,'request_id':control['request_id'],
  'validation_scope':profile['validation_scope'],'implementation_version':profile['implementation_version'],
  'workflow_version':profile['workflow_version'],'workflow_operation':request['operation'],'mode':request['mode'],
  'authority_fingerprint':sha(canonical(request)),'request_fingerprint':sha(canonical(doc['request'])),
  'retained_record_fingerprint':None if retained is None else sha(canonical(json.loads(retained))),
  'record_fingerprint':sha(record),'resources':profile['resources']}
 with os.fdopen(os.dup(int(sys.argv[4])),'wb') as f:f.write(record)
 response['result']={'schema_version':'biocompiler.core.artifact_response.v1','transport':'biocompiler.core.artifact_transport.v1',
  'authority':descriptor(authority),'retained_record':None if retained is None else descriptor(retained),
  'artifact':descriptor(record),'result':receipt}
print(json.dumps(response))
'''


@unittest.skipUnless(os.name == "posix", "Artifact channel uses POSIX file descriptors")
class WorkflowProcessTests(unittest.TestCase):
    def test_both_roles_complete_six_mode_run_and_replay_using_actual_children(self):
        values = fixture_records()
        records = {(value["request"]["operation"], value["request"]["mode"]): canonical(value) for value in values}
        with tempfile.TemporaryDirectory() as directory:
            for role in ("core", "verify"):
                path = Path(directory) / role
                path.write_text(f"#!{sys.executable}\nROLE={role!r}\nCAPABILITIES={capabilities()!r}\nRECORDS={records!r}\n" + CHILD)
                path.chmod(0o755)
                client = WorkflowClient(CoreClient(path, role=role, expected_sha256=sha(path.read_bytes())))
                for value in values:
                    request, record = canonical(value["request"]), canonical(value)
                    with self.subTest(role=role, operation=value["request"]["operation"], mode=value["request"]["mode"]), no_semantics():
                        self.assertEqual(client.run(request).record_json, record)
                        self.assertEqual(client.replay(request, record).record_json, record)
