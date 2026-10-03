"""Authority transport fixtures never execute native or Python workflow checks."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler import core_artifacts as artifacts
from biocompiler.core_client import (
    CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL, CoreCancelled, CoreClient,
    CoreProtocolError, CoreRejected, CoreUnavailable, CoreUnsupported, encode_json,
)
from biocompiler.core_workflow import default_limits, effective_resources
from biocompiler.core_workflow_authority import AuthorityClient, OPERATIONS, capability_profile
from test_core_workflow import canonical, fixture_records, no_semantics, sha


def capabilities():
    profile = capability_profile()
    return {"schema_version": CAPABILITIES_SCHEMA, "operations": ["capabilities", *OPERATIONS],
        "intent_schemas": [], "canonicalization": "python-json-v1",
        "validation_scopes": [profile["validation_scope"]],
        "profiles": {"artifact_transport_authority": deepcopy(artifacts.AUTHORITY_TRANSPORT_PROFILE),
                     "verification_workflow_authority": profile},
        "limits": dict(LIMITS), "claim_scope": "Authority transport fixture only; no acceptance."}


class WorkflowAuthorityTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.requests = [record["request"] for record in fixture_records()]

    def setUp(self):
        self.calls = []
        self.authority = self.requests[0]
        self.core = CoreClient(Path(sys.executable), role="verify")
        self.client = AuthorityClient(self.core)

    @contextmanager
    def exchange(self, *, mutate=None, capability_mutation=None, request_mutation=None,
                 outer_mutation=None, rejected=None, after_negotiation=None, raw_output=None):
        def response(request, result, status="ok"):
            return encode_json({"protocol": PROTOCOL, "request_id": request["request_id"],
                "operation": request["operation"], "status": status, "result": result if status == "ok" else None,
                "diagnostics": [] if status == "ok" else [{"code": "lowering_source_identity",
                    "message": "Source semantic fingerprint and program identity match.", "path": "authority"}],
                "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL,
                         "executable": self.core.role}}), {"ok": 0, "error": 2, "unsupported": 3}[status]

        def negotiate(_executable, raw, _timeout, _cancelled):
            request = json.loads(raw)
            self.calls.append(request)
            self.assertEqual(request["operation"], "capabilities")
            value = capabilities()
            if capability_mutation:
                capability_mutation(value)
            if after_negotiation:
                after_negotiation()
            return response(request, value)

        def artifact(_core, raw, arguments, files, output, output_limit, cancelled):
            if cancelled is not None and cancelled():
                raise CoreCancelled("Fixture cancellation")
            request = json.loads(raw)
            self.calls.append(request)
            self.assertEqual(request["operation"], OPERATIONS[0])
            self.assertEqual(request["payload"]["transport"], artifacts.AUTHORITY_TRANSPORT_PROFILE["profile"])
            self.assertEqual(arguments[2], "-")
            self.assertEqual(len(files), 2)
            self.assertIsNone(request["payload"]["retained_record"])
            source = files[0]
            source.seek(0)
            authority = source.read()
            self.assertEqual(source.mode, "rb")
            self.assertEqual(request["payload"]["authority"], artifacts._descriptor(authority))
            if rejected:
                return response(request, None, rejected)
            document = deepcopy(self.authority)
            if request_mutation:
                request_mutation(document)
            returned = canonical(document) if raw_output is None else raw_output
            output.write(returned)
            output.flush()
            supplied = json.loads(authority)
            profile = capability_profile()
            receipt = {
                "schema_version": "biocompiler.core.verification_workflow_authority_result.v1",
                "profile": profile["profile"], "operation": OPERATIONS[0],
                "executable": self.core.role, "request_id": request["request_id"],
                "validation_scope": profile["validation_scope"],
                "implementation_version": profile["implementation_version"],
                "workflow_version": profile["workflow_version"],
                "workflow_operation": supplied.get("operation"), "mode": supplied.get("mode"),
                "authority_fingerprint": sha(canonical(supplied)), "request_fingerprint": sha(returned),
                "resources": effective_resources(request["payload"]["operation_payload"]["limits"]),
            }
            if mutate:
                mutate(receipt)
            envelope = {"schema_version": "biocompiler.core.artifact_response.v1",
                "transport": artifacts.AUTHORITY_TRANSPORT_PROFILE["profile"],
                "authority": artifacts._descriptor(authority), "retained_record": None,
                "artifact": artifacts._descriptor(returned), "result": receipt}
            if outer_mutation:
                outer_mutation(envelope)
            return response(request, envelope)

        with patch("biocompiler.core_client._exchange", side_effect=negotiate), \
             patch("biocompiler.core_artifacts._exchange_artifacts", side_effect=artifact), no_semantics():
            yield

    def call(self, **options):
        return self.client.validate(canonical(self.authority), **options)

    def test_full_six_pairs_both_roles_and_defensive_access(self):
        self.assertEqual({(r["operation"], r["mode"]) for r in self.requests},
                         {(op, mode) for op in ("check", "explore", "reduce") for mode in ("candidate", "model")})
        for role in ("core", "verify"):
            self.core = CoreClient(Path(sys.executable), role=role)
            self.client = AuthorityClient(self.core)
            for self.authority in self.requests:
                with self.subTest(role=role, operation=self.authority["operation"], mode=self.authority["mode"]), self.exchange():
                    value = self.call(request_id="authority-fixture")
                self.assertEqual(value.request_json, canonical(self.authority))
                self.assertEqual(value.request, self.authority)
                self.assertEqual(value.request_fingerprint, sha(value.request_json))
                self.assertEqual(value.authority_fingerprint, sha(canonical(self.authority)))
                self.assertEqual(value.workflow_operation, self.authority["operation"])
                self.assertEqual(value.mode, self.authority["mode"])
                self.assertEqual(value.request_id, "authority-fixture")
                self.assertEqual(value.executable, role)
                self.assertEqual(value.receipt["validation_scope"], "fresh_source_authority_only")
                self.assertNotIn("result", value.request)
                self.assertNotIn("record_fingerprint", value.receipt)
                self.assertFalse(hasattr(value, "passed"))
                value.request.clear(); value.receipt.clear(); value.envelope.clear()
                self.assertEqual(value.request, self.authority)
                with self.assertRaises(FrozenInstanceError):
                    value.mode = "changed"
        self.assertEqual(len(self.calls), 24)

    def test_exact_separate_profile_and_defensive_copy(self):
        self.assertEqual(sha(canonical(capability_profile())),
                         "3f2328785095df64e4eee9f4210eebb8282be8b68d3594bd2bdaa1e92a611e2e")
        profile = capability_profile()
        self.assertNotIn("record_schema", profile)
        profile["resources"].clear()
        self.assertTrue(capability_profile()["resources"])
        # This separate operation requires neither run/replay nor their profile.
        with self.exchange():
            self.call()

    def test_exact_profile_and_scope_mutations_fail_before_artifact_io(self):
        changes = [
            lambda c: c["profiles"].pop("verification_workflow_authority"),
            lambda c: c["profiles"]["verification_workflow_authority"].update(profile="changed"),
            lambda c: c["profiles"]["verification_workflow_authority"].update(record_schema="unexpected"),
            lambda c: c["profiles"]["verification_workflow_authority"].update(implementation_version="changed"),
            lambda c: c["profiles"]["verification_workflow_authority"]["resources"]["workflow"].update(
                max_work=float(default_limits()["max_work"])),
            lambda c: c["profiles"]["artifact_transport_authority"].update(profile="changed"),
            lambda c: c["profiles"].pop("artifact_transport_authority"),
            lambda c: c["validation_scopes"].clear(),
        ]
        for change in changes:
            self.calls.clear()
            with self.subTest(change=change), self.exchange(capability_mutation=change), self.assertRaises(CoreProtocolError):
                self.call()
            self.assertEqual(len(self.calls), 1)
        self.calls.clear()
        with self.exchange(capability_mutation=lambda c: c["operations"].remove(OPERATIONS[0])), \
             self.assertRaises(CoreProtocolError):
            self.call()
        self.assertEqual(len(self.calls), 1)

    def test_every_receipt_identity_and_version_is_bound(self):
        fields = ("schema_version", "profile", "operation", "executable", "request_id", "validation_scope",
                  "implementation_version", "workflow_version", "workflow_operation", "mode",
                  "authority_fingerprint", "request_fingerprint")
        for field in fields:
            with self.subTest(field=field), self.exchange(mutate=lambda r: r.update({field: "changed"})), \
                 self.assertRaises(CoreProtocolError):
                self.call()
        for mutation in (lambda r: r.pop("resources"), lambda r: r.update(extra=True),
                         lambda r: r.update(record_fingerprint="0" * 64),
                         lambda r: r["resources"]["realization"].update(max_request_bytes=True)):
            with self.exchange(mutate=mutation), self.assertRaises(CoreProtocolError):
                self.call()

    def test_complete_normalized_request_schema_and_header_are_checked(self):
        mutations = (lambda r: r.update(schema_version="changed"), lambda r: r.update(mode="candidate"),
                     lambda r: r.update(operation="reduce"), lambda r: r.pop("history"),
                     lambda r: r.update(result={}), lambda r: r.update(mode=True))
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.exchange(request_mutation=mutation), self.assertRaises(CoreProtocolError):
                self.call()

    def test_normalized_request_and_supplied_authority_have_separate_identities(self):
        # A transport-only normalized-artifact witness. The client preserves the
        # returned complete data; it does not attempt Python semantic normalization.
        def normalize(value):
            value["realization"]["behavior"]["name"] = "normalized fixture"
        with self.exchange(request_mutation=normalize):
            result = self.call()
        self.assertNotEqual(result.authority_fingerprint, result.request_fingerprint)
        self.assertEqual(result.request_fingerprint, sha(canonical(result.request)))
        self.assertEqual(result.request["realization"]["behavior"]["name"], "normalized fixture")

    def test_transport_descriptor_and_canonical_output_are_bound(self):
        for mutation in (lambda e: e["artifact"].update(sha256="0" * 64),
                         lambda e: e["authority"].update(bytes=1),
                         lambda e: e.update(retained_record={"bytes": 1, "sha256": "0" * 64}),
                         lambda e: e.update(transport="biocompiler.core.artifact_transport.v1")):
            with self.exchange(outer_mutation=mutation), self.assertRaises(CoreProtocolError):
                self.call()
        with self.exchange(raw_output=canonical(self.authority) + b"\n"), self.assertRaises(CoreProtocolError):
            self.call()

    def test_five_reductions_exact_resources_and_mutation_freeze(self):
        for key in default_limits():
            limits = default_limits()
            limits[key] -= 1
            with self.subTest(key=key), self.exchange():
                result = self.call(limits=limits)
            self.assertEqual(result.receipt["resources"], effective_resources(limits))
            self.assertEqual(self.calls[-1]["payload"]["operation_payload"]["limits"], limits)
        limits = default_limits()
        expected = deepcopy(limits)
        with self.exchange(after_negotiation=lambda: limits.update(max_work=1)):
            result = self.call(limits=limits)
        self.assertEqual(result.receipt["resources"], effective_resources(expected))

    def test_malformed_limits_are_rejected_before_negotiation(self):
        for value in (True, 1, {}, {**default_limits(), "extra": 1},
                      {**default_limits(), "max_work": 0}, {**default_limits(), "max_report_nodes": 1.0},
                      {**default_limits(), "max_work": default_limits()["max_work"] + 1}):
            with self.subTest(value=value), self.exchange(), self.assertRaises(CoreProtocolError):
                self.call(limits=value)
        self.assertEqual(self.calls, [])

    def test_output_exact_byte_and_node_limits(self):
        limits = default_limits()
        limits["max_report_bytes"] = len(canonical(self.authority))
        with self.exchange():
            self.call(limits=limits)
        limits["max_report_bytes"] -= 1
        with self.exchange(), self.assertRaises(CoreProtocolError):
            self.call(limits=limits)
        limits = default_limits()
        limits["max_report_nodes"] = 1
        with self.exchange(), self.assertRaises(CoreProtocolError):
            self.call(limits=limits)

    def test_supplied_unicode_numbers_and_noncanonical_format_are_preserved(self):
        self.authority = deepcopy(self.requests[0])
        self.authority["realization"]["behavior"]["name"] = "RNA α 细胞 🧬"
        self.authority["history"][0]["time"] = -0.0
        supplied = json.dumps(self.authority, indent=2, ensure_ascii=True).encode()
        with self.exchange():
            result = self.client.validate(supplied)
        self.assertEqual(result.authority_fingerprint, sha(canonical(self.authority)))
        self.assertEqual(result.request_json, canonical(self.authority))
        self.assertIn("细胞".encode(), result.request_json)
        self.assertIn(b'"time":-0.0', result.request_json)

    def test_native_rejections_and_cancellation_never_fall_back(self):
        for status, error in (("error", CoreRejected), ("unsupported", CoreUnsupported)):
            with self.exchange(rejected=status), self.assertRaises(error) as caught:
                self.call()
            self.assertEqual(caught.exception.response.diagnostics[0].code, "lowering_source_identity")
        with self.exchange(), self.assertRaises(CoreCancelled):
            self.call(cancelled=lambda: True)
        unavailable = CoreUnavailable("Fixture missing executable")
        with patch("biocompiler.core_client._exchange", side_effect=unavailable), no_semantics(), \
             self.assertRaises(CoreUnavailable) as caught:
            self.call()
        self.assertIs(caught.exception, unavailable)

    def test_raw_shape_and_immutable_byte_contract_fail_before_io(self):
        for raw in (bytearray(canonical(self.authority)), b"", b'{"x":1,"x":2}', b'{"unfinished":'):
            with self.exchange(), self.assertRaises(CoreProtocolError):
                self.client.validate(raw)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
