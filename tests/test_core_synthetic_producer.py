"""Strict producer transport, using frozen originals and Python child fixtures.

These tests execute no native binaries and confer no native semantic parity.
"""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.core_client import (
    CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL, CoreClient,
    CoreProtocolError, CoreRejected, CoreUnavailable, CoreUnsupported, encode_json,
)
from biocompiler.core_synthetic_producer import (
    OPERATIONS, RESULT_SCHEMA, SyntheticProducerClient, capability_profile,
    default_limits, effective_resources,
)

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/conformance/synthetic-producers-v1"
# Complete original producer inputs and results; no output is synthesized by a
# production implementation, and none of the historical corpus is rewritten.
FIXTURES = (
    ("979b81cb4bd0e8313109190be23e6f8b1f03997455337145558ee97bbf19ba5e",
     "960639e1dd392602b52ac6e9dabe2598f3b041aeffd6670c1abd9267cb646d19"),
    ("3ee991259475003a2ea793987d4126a6d228831bcae1a58819edb7bb5d062896",
     "ad895daadf5dce515b6519892cc17b2cf3857d7093d921599664a607b8499996"),
    ("1fd3668669a56d7a42bc494836c3fc67aa9294accced5156f2d6f37dc6057948",
     "659ba171adb4736c3844b1dd8f8b9a610308cc3719a962271c190aa8e513ad14"),
)


def encoded(value):
    return encode_json(value, limit=LIMITS["max_response_bytes"])


def fingerprint(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def load_document(identity):
    raw = (CORPUS / (identity + ".json")).read_bytes()
    document = json.loads(raw)
    if encoded(document) + b"\n" != raw or fingerprint(document) != identity:
        raise AssertionError("Original producer corpus content address differs")
    return document


def fixture(operation):
    source, target = FIXTURES[OPERATIONS.index(operation)]
    payload = json.loads(load_document(source))
    payload.update(profile=capability_profile(operation)["profile"], limits=None)
    return payload, load_document(target)


def receipt(operation, payload, record):
    profile = capability_profile(operation)
    result = {key: deepcopy(profile[key]) for key in (
        "profile", "implementation", "service_implementation", "resource_profile", "validation_scope", "claim_scope")}
    request = (record["acceptance"]["dependencies"]["settings"]["realization_request"]
               if operation == OPERATIONS[2] else record["request_fingerprint"])
    identities = {"request_fingerprint": request, "request_artifact_fingerprint": fingerprint(payload["request"])}
    if operation == OPERATIONS[0]:
        identities["config_fingerprint"] = fingerprint(record["generator_config"])
    if operation == OPERATIONS[1]:
        identities.update(config_fingerprint=fingerprint(record["config"]),
                          history_ascii_fingerprint=record["history_fingerprint"])
    if operation == OPERATIONS[2]:
        identities.update(candidate_fingerprint=fingerprint(payload["candidate"]),
                          history_ascii_fingerprint=record["acceptance"]["dependencies"]["history"])
    result.update(schema_version=RESULT_SCHEMA, resources=effective_resources(operation, payload["limits"]),
                  supplied_authority_fingerprint=fingerprint(payload), authority_identities=identities,
                  outcome="produced", record=deepcopy(record), record_fingerprint=fingerprint(record), generation_error=None)
    return result


def capabilities():
    return {"schema_version": CAPABILITIES_SCHEMA, "operations": ["capabilities", *OPERATIONS],
            "intent_schemas": ["biocompiler.intent.v0.1"], "canonicalization": "python-json-v1",
            "validation_scopes": [capability_profile(op)["validation_scope"] for op in OPERATIONS],
            "profiles": dict(zip(("synthetic_generation", "synthetic_selection", "synthetic_components"),
                                  (capability_profile(op) for op in OPERATIONS))),
            "limits": dict(LIMITS), "claim_scope": "Supplied software contracts only."}


def envelope(request, result, *, status="ok"):
    return {"protocol": PROTOCOL, "request_id": request["request_id"], "operation": request["operation"],
            "status": status, "result": result if status == "ok" else None,
            "diagnostics": [] if status == "ok" else [{"code": "original_failure", "message": "Complete rejection", "path": "$.request"}],
            "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": "core"}}


class SyntheticProducerTransportTests(unittest.TestCase):
    def setUp(self):
        self.client = SyntheticProducerClient(CoreClient(Path(sys.executable)))
        self.calls = []

    def exchange(self, *, transform=None, capability_transform=None, during_negotiation=None, status="ok"):
        def invoke(_executable, raw, _timeout, cancelled):
            request = json.loads(raw)
            self.calls.append((request, cancelled))
            operation = request["operation"]
            if operation == "capabilities":
                result = capabilities()
                if capability_transform:
                    capability_transform(result)
                if during_negotiation:
                    during_negotiation()
            else:
                _, record = fixture(operation)
                result = receipt(operation, request["payload"], record)
                if transform:
                    transform(result)
            outcome = "ok" if operation == "capabilities" else status
            return encoded(envelope(request, result, status=outcome)), {"ok": 0, "error": 2, "unsupported": 3}[outcome]
        return patch("biocompiler.core_client._exchange", side_effect=invoke)

    def call(self, operation, payload=None):
        if payload is None:
            payload, _ = fixture(operation)
        method = (self.client.generate_document, self.client.select_document, self.client.adapt_document)[OPERATIONS.index(operation)]
        return method(encoded(payload), request_id="fixture-identity")

    def test_installed_metadata_matches_exact_declaration(self):
        declaration = json.loads((ROOT / "protocol/synthetic-producer-v1.json").read_bytes())
        for family, operation in zip(("synthetic_generation", "synthetic_selection", "synthetic_components"), OPERATIONS):
            self.assertEqual(encoded(capability_profile(operation)), encoded(declaration[family]))
            mutated = capability_profile(operation)
            mutated["resources"].clear()
            self.assertTrue(capability_profile(operation)["resources"])

    def test_three_complete_original_records_and_immutable_defensive_views(self):
        for operation in OPERATIONS:
            with self.subTest(operation=operation), self.exchange():
                result = self.call(operation)
                payload, original = fixture(operation)
                self.assertEqual(result.record_json, encoded(original))
                self.assertEqual(result.record_fingerprint, fingerprint(original))
                self.assertEqual(result.authority_json, encoded(payload))
                self.assertEqual(result.input_document, encoded(payload))
                self.assertEqual(result.request_id, "fixture-identity")
                self.assertEqual(result.outcome, "produced")
                self.assertIsNone(result.generation_error)
                result.record.clear()
                result.receipt.clear()
                result.authority_identities.clear()
                self.assertEqual(result.record_json, encoded(original))
                self.assertTrue(result.authority_identities)
                with self.assertRaises(FrozenInstanceError):
                    result.outcome = "unsupported"

    def test_mapping_authority_freezes_before_negotiation_and_raw_bytes_are_preserved(self):
        for operation in OPERATIONS:
            payload, _ = fixture(operation)
            original = deepcopy(payload)
            arguments = {key: value for key, value in payload.items() if key != "profile"}
            method = (self.client.generate, self.client.select, self.client.adapt)[OPERATIONS.index(operation)]
            with self.exchange(during_negotiation=lambda: payload["request"].clear()):
                result = method(**arguments)
            self.assertEqual(result.authority_json, encoded(original))
        payload, _ = fixture(OPERATIONS[0])
        raw = b" \n" + encoded(payload) + b"\t"
        with self.exchange():
            result = self.client.generate_document(raw)
        self.assertEqual(result.input_document, raw)
        self.assertEqual(result.authority_json, encoded(payload))

    def test_rejects_profile_scope_resource_and_complete_identity_forgeries(self):
        mutations = [
            lambda r: r.update(supplied_authority_fingerprint="0" * 64),
            lambda r: r.update(record_fingerprint="0" * 64),
            lambda r: r.update(validation_scope="biological_validation"),
            lambda r: r.update(claim_scope="Universal evidence"),
            lambda r: r.update(service_implementation="changed"),
            lambda r: r["authority_identities"].update(request_fingerprint="0" * 64),
            lambda r: r["authority_identities"].update(request_artifact_fingerprint="not-a-hash"),
            lambda r: r["resources"]["protocol"].update(max_work=50_000_000.0),
            lambda r: r.update(outcome="pass"),
            lambda r: r.update(extra=True),
            lambda r: r.update(generation_error={}),
        ]
        for operation in OPERATIONS:
            for mutation in mutations:
                with self.subTest(operation=operation, mutation=mutation), self.exchange(transform=mutation):
                    with self.assertRaises(CoreProtocolError):
                        self.call(operation)

    def test_rehashed_incomplete_records_and_numeric_kind_changes_are_rejected(self):
        def rehash(mutation):
            def apply(result):
                mutation(result["record"])
                result["record_fingerprint"] = fingerprint(result["record"])
            return apply
        cases = [
            (OPERATIONS[0], lambda r: r.update(human_therapeutic_admission="admitted")),
            (OPERATIONS[0], lambda r: r["generator_config"].update(conjunction_strategy="de_morgan")),
            (OPERATIONS[1], lambda r: r["alternatives"].pop()),
            (OPERATIONS[1], lambda r: r.update(checked_candidates=True)),
            (OPERATIONS[1], lambda r: r.update(until=9.0)),
            (OPERATIONS[1], lambda r: r.update(history_fingerprint="0" * 64)),
            (OPERATIONS[2], lambda r: r["acceptance"].update(outcome="unknown")),
            (OPERATIONS[2], lambda r: r["acceptance"]["dependencies"]["settings"].update(synthetic_candidate="0" * 64)),
        ]
        for operation, mutation in cases:
            with self.subTest(operation=operation, mutation=mutation), self.exchange(transform=rehash(mutation)):
                with self.assertRaises(CoreProtocolError):
                    self.call(operation)

    def test_capability_negotiation_is_exact_and_precedes_production(self):
        mutations = [
            lambda c: c["profiles"]["synthetic_generation"]["default_limits"].update(max_work=50_000_000.0),
            lambda c: c["profiles"]["synthetic_generation"].update(role="bioc-verify"),
            lambda c: c["validation_scopes"].clear(),
            lambda c: c["operations"].remove(OPERATIONS[2]),
        ]
        for mutation in mutations:
            self.calls.clear()
            with self.exchange(capability_transform=mutation), self.assertRaises(CoreProtocolError):
                self.call(OPERATIONS[0])
            self.assertEqual([call[0]["operation"] for call in self.calls], ["capabilities"])

    def test_reduced_limits_require_exact_positive_integers_and_bind_every_resource(self):
        operation = OPERATIONS[2]
        payload, _ = fixture(operation)
        reduced = {key: value - 1 for key, value in default_limits(operation).items()}
        payload["limits"] = reduced
        with self.exchange():
            result = self.call(operation, payload)
        resources = result.receipt["resources"]
        self.assertEqual(resources["protocol"]["max_work"], reduced["max_work"])
        self.assertEqual(resources["producer"]["acceptance"]["shared"]["max_report_bytes"], reduced["max_report_bytes"])
        for bad in (True, 1.0, 0, -1, 50_000_001):
            payload["limits"] = {**reduced, "max_work": bad}
            with patch("biocompiler.core_client._exchange") as exchange, self.assertRaises(CoreProtocolError):
                self.call(operation, payload)
            exchange.assert_not_called()

    def test_complete_unsupported_details_remain_distinct_from_transport_unsupported(self):
        detail = {"message": "Original unsupported behavior", "node_id": "node.α",
                  "source": {"file": "source.py", "line": 17, "function": "program"},
                  "formatted": "Original unsupported behavior [node.α] at source.py:17"}
        def unsupported(result):
            result.update(outcome="unsupported", record=None, record_fingerprint=None, generation_error=deepcopy(detail))
        with self.exchange(transform=unsupported):
            result = self.call(OPERATIONS[0])
        self.assertEqual(result.generation_error, detail)
        self.assertIsNone(result.record)
        result.generation_error["source"].clear()
        self.assertEqual(result.generation_error, detail)
        for mutate in (lambda r: r["generation_error"].update(formatted="Truncated"),
                       lambda r: r["generation_error"]["source"].update(line=True),
                       lambda r: r.update(record={})):
            def corrupt(result):
                unsupported(result)
                mutate(result)
            with self.exchange(transform=corrupt), self.assertRaises(CoreProtocolError):
                self.call(OPERATIONS[0])
        for status, exception in (("unsupported", CoreUnsupported), ("error", CoreRejected)):
            with self.exchange(status=status), self.assertRaises(exception) as error:
                self.call(OPERATIONS[0])
            self.assertEqual(error.exception.response.diagnostics[0].path, "$.request")

    def test_verify_role_missing_binary_and_malformed_wire_never_fall_back(self):
        client = SyntheticProducerClient(CoreClient(Path(sys.executable), role="verify"))
        payload, _ = fixture(OPERATIONS[0])
        with patch("biocompiler.core_client._exchange") as exchange, self.assertRaises(CoreProtocolError):
            client.generate_document(encoded(payload))
        exchange.assert_not_called()
        with self.assertRaises(CoreUnavailable):
            SyntheticProducerClient(CoreClient(Path("/nonexistent/biocompiler-producer"))).generate_document(encoded(payload))
        for raw in (b'{"profile":"a","profile":"b"}', b"{", b'{"value":NaN}', bytearray(b"{}")):
            with patch("biocompiler.core_client._exchange") as exchange, self.assertRaises(CoreProtocolError):
                self.client.generate_document(raw)
            exchange.assert_not_called()

    def test_actual_python_child_fixture_transports_all_three_complete_originals(self):
        with tempfile.TemporaryDirectory(prefix="bioc-producer-client-") as temporary:
            directory = Path(temporary)
            responses = {}
            for operation in OPERATIONS:
                payload, record = fixture(operation)
                responses[operation] = {"payload": payload, "result": receipt(operation, payload, record)}
            fixture_path = directory / "fixture.json"
            fixture_path.write_bytes(encoded({"capabilities": capabilities(), "responses": responses}))
            executable = directory / "python-protocol-fixture"
            executable.write_text("#!" + sys.executable + "\n" +
                "import json,sys,pathlib\n" +
                "d=json.loads(pathlib.Path(" + repr(str(fixture_path)) + ").read_bytes())\n" +
                "q=json.load(sys.stdin); op=q['operation']\n" +
                "canonical=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)\n" +
                "if op=='capabilities': result=d['capabilities']\n" +
                "else:\n" +
                " assert canonical(q['payload'])==canonical(d['responses'][op]['payload'])\n" +
                " result=d['responses'][op]['result']\n" +
                "r={'protocol':" + repr(PROTOCOL) + ",'request_id':q['request_id'],'operation':op,'status':'ok','result':result,'diagnostics':[],"
                "'core':{'implementation':'ocaml','version':" + repr(CORE_VERSION) + ",'protocol':" + repr(PROTOCOL) + ",'executable':'core'}}\n" +
                "sys.stdout.write(canonical(r))\n")
            executable.chmod(0o700)
            self.client = SyntheticProducerClient(CoreClient(executable, expected_sha256=hashlib.sha256(executable.read_bytes()).hexdigest()))
            for operation in OPERATIONS:
                result = self.call(operation)
                self.assertEqual(result.record_json, encoded(responses[operation]["result"]["record"]))


if __name__ == "__main__":
    unittest.main()
