"""Original complete build literals through strict transport and Python children."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.core_client import CoreClient, CoreProtocolError, CoreRejected
from biocompiler.core_synthetic_producer_public import (
    OPERATION, SyntheticProducerPublicClient, capability_profile,
)
from test_core_synthetic_producer import capabilities as producer_capabilities, encoded, envelope

ROOT = Path(__file__).resolve().parents[1]
LITERALS_PIN = "4a92853b22aef0ce15264b20fe7c5cc166729061eb5b0eef58117aa2f3e97f6c"


def literals():
    source = (ROOT / "core/test/test_synthetic_producer_public_protocol.ml").read_text()
    values = [json.loads(raw) for raw in re.findall(r"Json.parse \{literal\|(.*?)\|literal\}", source, re.S)]
    if len(values) != 46 or hashlib.sha256(encoded(values)).hexdigest() != LITERALS_PIN:
        raise AssertionError("Complete original public producer literals differ")
    return values[:4], values[4:]


def capabilities():
    value = producer_capabilities()
    value["operations"].append(OPERATION)
    value["profiles"]["synthetic_producer_public"] = capability_profile()
    value["validation_scopes"].append(capability_profile()["validation_scope"])
    return value


def fixture_executable(directory):
    """A Python-only process that returns independently retained full literals."""
    positive, negative = literals()
    table = {}
    for fixture in positive:
        table[hashlib.sha256(encoded(fixture["payload"])).hexdigest()] = {
            "status": "ok", "result": fixture["expected"], "diagnostics": [], "exit_code": 0}
    for fixture in negative:
        payload = {"profile": capability_profile()["profile"], "limits": None, "build_request": fixture["build_request"]}
        table[hashlib.sha256(encoded(payload)).hexdigest()] = {"status": "error", "result": None,
            "diagnostics": [{"code": "synthetic_build_request", "message": fixture["message"], "path": "payload.build_request"}], "exit_code": 2}
    data = directory / "fixture.json"
    data.write_bytes(encoded({"capabilities": capabilities(), "table": table}))
    executable = directory / "python-public-producer"
    executable.write_text("#!" + sys.executable + "\n" +
        "import hashlib,json,pathlib,sys\n" +
        "data=json.loads(pathlib.Path(" + repr(str(data)) + ").read_bytes())\n" +
        "request=json.load(sys.stdin)\n" +
        "def encoded(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()\n" +
        "if request['operation']=='capabilities':\n" +
        " row={'status':'ok','result':data['capabilities'],'diagnostics':[],'exit_code':0}\n" +
        "else: row=data['table'][hashlib.sha256(encoded(request['payload'])).hexdigest()]\n" +
        "response={'protocol':'biocompiler.core.v1','request_id':request['request_id'],'operation':request['operation'],"
        "'status':row['status'],'result':row['result'],'diagnostics':row['diagnostics'],"
        "'core':{'implementation':'ocaml','version':'0.1.0','protocol':'biocompiler.core.v1','executable':'core'}}\n" +
        "sys.stdout.buffer.write(encoded(response)+b'\\n');sys.exit(row['exit_code'])\n")
    executable.chmod(0o700)
    return executable


class PublicSyntheticProducerClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.positive, cls.negative = literals()

    def setUp(self):
        self.client = SyntheticProducerPublicClient(CoreClient(Path(sys.executable)))
        self.calls = []

    def exchange(self, fixture=None, *, mutate=None, capability_mutate=None, on_negotiate=None):
        fixture = self.positive[0] if fixture is None else fixture
        def invoke(_executable, raw, _timeout, _cancelled):
            request = json.loads(raw)
            self.calls.append(request)
            if request["operation"] == "capabilities":
                result = capabilities()
                if capability_mutate:
                    capability_mutate(result)
                if on_negotiate:
                    on_negotiate()
            else:
                self.assertEqual(encoded(request["payload"]), encoded(fixture["payload"]))
                result = deepcopy(fixture["expected"])
                if mutate:
                    mutate(result)
            return encoded(envelope(request, result)), 0
        return patch("biocompiler.core_client._exchange", side_effect=invoke)

    def test_exact_profile_and_four_complete_results_immutable(self):
        self.assertEqual(encoded(capability_profile()), encoded(json.loads((ROOT / "protocol/synthetic-producer-public-v1.json").read_bytes())))
        for fixture in self.positive:
            original = b" \n" + encoded(fixture["payload"]["build_request"]) + b"\t"
            with self.exchange(fixture):
                result = self.client.select_document(original, request_id="public-fixture")
            expected = fixture["expected"]
            self.assertEqual(result.input_build_request, original)
            self.assertEqual(result.authority_json, encoded(fixture["payload"]))
            self.assertEqual(result.receipt_json, encoded(expected))
            self.assertEqual(result.normalized_build_request_json, encoded(expected["normalized_build_request"]))
            self.assertEqual(result.production_payload_json, encoded(expected["production_payload"]))
            self.assertEqual(result.production.receipt_json, encoded(expected["production"]))
            self.assertEqual(result.exit_code, expected["presentation"]["exit_code"])
            self.assertEqual(result.frame_count, expected["presentation"]["frame_count"])
            result.receipt.clear()
            result.normalized_build_request.clear()
            result.production_payload.clear()
            self.assertEqual(result.receipt_json, encoded(expected))
            with self.assertRaises(FrozenInstanceError):
                result.exit_code = 0

    def test_complete_supplied_mapping_is_frozen_before_negotiation(self):
        original = deepcopy(self.positive[0]["payload"]["build_request"])
        with self.exchange(on_negotiate=original.clear):
            result = self.client.select(original)
        self.assertEqual(result.normalized_build_request, self.positive[0]["expected"]["normalized_build_request"])

    def test_forged_outer_nested_authority_and_presentation_are_rejected(self):
        mutations = [
            lambda r: r.update(supplied_authority_fingerprint="0" * 64),
            lambda r: r.update(supplied_build_request_fingerprint="0" * 64),
            lambda r: r.update(build_request_fingerprint="0" * 64),
            lambda r: r.update(claim_scope="biological admission"),
            lambda r: r.update(service_implementation="changed"),
            lambda r: r["resources"]["protocol"].update(max_work=50_000_000.0),
            lambda r: r["presentation"].update(frame_count=True),
            lambda r: r["presentation"].update(frame_count=3.0),
            lambda r: r["presentation"].update(exit_code=False),
            lambda r: r["presentation"].update(exit_code=1),
            lambda r: r["production_payload"]["limits"].update(max_monitor_items=100000),
            lambda r: r["production_payload"].update(until=7.0),
            lambda r: r["production"].update(supplied_authority_fingerprint="0" * 64),
            lambda r: r["production"]["record"]["alternatives"].pop(),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.exchange(mutate=mutate), self.assertRaises(CoreProtocolError):
                self.client.select(self.positive[0]["payload"]["build_request"])
        def rehashed_changed_authority(result):
            result["normalized_build_request"]["until"] = 7.0
            result["build_request_fingerprint"] = hashlib.sha256(encoded(result["normalized_build_request"])).hexdigest()
        with self.exchange(mutate=rehashed_changed_authority), self.assertRaises(CoreProtocolError):
            self.client.select(self.positive[0]["payload"]["build_request"])

    def test_incompatible_capabilities_and_verify_role_stop_before_production(self):
        mutations = (
            lambda c: c["profiles"]["synthetic_producer_public"]["default_limits"].update(max_work=50_000_000.0),
            lambda c: c["profiles"].pop("synthetic_selection"),
            lambda c: c["validation_scopes"].remove(capability_profile()["validation_scope"]),
            lambda c: c["operations"].remove(OPERATION),
        )
        for mutate in mutations:
            self.calls.clear()
            with self.exchange(capability_mutate=mutate), self.assertRaises(CoreProtocolError):
                self.client.select(self.positive[0]["payload"]["build_request"])
            self.assertEqual([r["operation"] for r in self.calls], ["capabilities"])
        client = SyntheticProducerPublicClient(CoreClient(Path(sys.executable), role="verify"))
        with patch("biocompiler.core_client._exchange") as exchange, self.assertRaises(CoreProtocolError):
            client.select_document(b"{}")
        exchange.assert_not_called()
        for value in (b'{"x":1,"x":2}', b'{"x":NaN}', bytearray(b"{}")):
            with patch("biocompiler.core_client._exchange") as exchange, self.assertRaises(CoreProtocolError):
                self.client.select_document(value)
            exchange.assert_not_called()

    def test_all_46_original_positive_and_malformed_authorities_use_actual_python_children(self):
        with tempfile.TemporaryDirectory(prefix="bioc-public-client-") as temporary:
            executable = fixture_executable(Path(temporary))
            client = SyntheticProducerPublicClient(CoreClient(executable,
                expected_sha256=hashlib.sha256(executable.read_bytes()).hexdigest()))
            for fixture in self.positive:
                result = client.select(fixture["payload"]["build_request"])
                self.assertEqual(result.receipt_json, encoded(fixture["expected"]))
            for fixture in self.negative:
                with self.subTest(name=fixture["name"]), self.assertRaises(CoreRejected) as error:
                    client.select(fixture["build_request"])
                self.assertEqual(error.exception.response.diagnostics[0].message, fixture["message"])
                self.assertEqual(error.exception.response.diagnostics[0].path, "payload.build_request")


if __name__ == "__main__":
    unittest.main()
