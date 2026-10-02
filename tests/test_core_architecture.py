"""Boundary checks for experimental architecture calls; no native build."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler.core_architecture import (
    ASSESSMENT_SCHEMA, CHECKER_POLICY, CLAIM_SCOPE, IMPLEMENTATION, PROFILE,
    RESOURCE_PROFILE, RESULT_SCHEMA, VALIDATION_SCOPE, ArchitectureClient,
)
from biocompiler.core_client import (
    CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL, CoreCancelled, CoreClient,
    CoreProtocolError, CoreRejected, CoreUnsupported, encode_json,
)


def fingerprint(value):
    return hashlib.sha256(encode_json(value)).hexdigest()


def capabilities():
    return {"schema_version": CAPABILITIES_SCHEMA, "operations": ["capabilities", "verify-architecture", "replay-architecture"],
            "intent_schemas": ["biocompiler.intent.v0.1"], "canonicalization": "python-json-v1",
            "validation_scopes": [VALIDATION_SCOPE], "profiles": {"architecture": deepcopy(PROFILE)},
            "limits": dict(LIMITS), "claim_scope": "Supplied contracts only."}


def result(payload):
    assessment = {"schema_version": ASSESSMENT_SCHEMA, "request_fingerprint": "a" * 64,
                  "build_fingerprint": "b" * 64, "outcome": "pass", "translation_complete": False,
                  "construction_complete": False, "diagnostics": [], "unresolved": ["unimplemented"],
                  "assumptions": ["supplied model"], "checker_version": CHECKER_POLICY, "claim_scope": CLAIM_SCOPE,
                  "search_verified": False, "empirical_validation": "unknown", "human_therapeutic_admission": "not_admitted"}
    return {"schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION, "resource_profile": RESOURCE_PROFILE,
            "validation_scope": VALIDATION_SCOPE, "supplied_request_fingerprint": fingerprint(payload["expected_request"]),
            "supplied_build_fingerprint": fingerprint(payload["build"]),
            "assessment_fingerprint": fingerprint(assessment), "assessment": assessment}


class ArchitectureTransportTests(unittest.TestCase):
    def setUp(self):
        self.client = ArchitectureClient(CoreClient(Path(sys.executable), role="verify"))
        self.calls = []
        self.authority = {"source": "original", "values": [9007199254740993, -0.0]}
        self.build = {"member": "candidate"}

    def exchange(self, transform=None, capability_transform=None, rejection=None, on_negotiate=None):
        def invoke(_executable, encoded, _timeout, _cancelled):
            request = json.loads(encoded)
            self.calls.append(request)
            operation = request["operation"]
            if operation == "capabilities":
                value = capabilities()
                if capability_transform:
                    capability_transform(value)
                if on_negotiate:
                    on_negotiate()
            else:
                value = result(request["payload"])
                if transform:
                    transform(value)
            status = rejection if operation != "capabilities" and rejection else "ok"
            response = {"protocol": PROTOCOL, "request_id": request["request_id"], "operation": operation,
                        "status": status, "result": value if status == "ok" else None,
                        "diagnostics": [] if status == "ok" else [{"code": "independent_rejection", "message": "Rejected", "path": None}],
                        "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": "verify"}}
            return encode_json(response), {"ok": 0, "error": 2, "unsupported": 3}[status]
        return patch("biocompiler.core_client._exchange", side_effect=invoke)

    def verify(self):
        return self.client.verify(expected_request=self.authority, build=self.build)

    def test_scoped_result_is_bound_to_exact_supplied_bytes_and_defensively_copied(self):
        with self.exchange():
            checked = self.verify()
        self.assertEqual([call["operation"] for call in self.calls], ["capabilities", "verify-architecture"])
        self.assertEqual(checked.supplied_request_fingerprint, fingerprint(self.authority))
        self.assertEqual(checked.outcome, "pass")
        self.assertFalse(checked.translation_complete)
        self.assertFalse(checked.construction_complete)
        self.assertEqual(checked.unresolved, ("unimplemented",))
        checked.assessment["unresolved"].clear()
        self.assertEqual(checked.assessment["unresolved"], ["unimplemented"])
        with self.assertRaises(AttributeError):
            checked.outcome = "fail"

    def test_caller_mutation_during_negotiation_cannot_change_operation_authority(self):
        original = deepcopy(self.authority)
        with self.exchange(on_negotiate=lambda: self.authority["values"].append(5)):
            checked = self.verify()
        self.assertEqual(self.calls[1]["payload"]["expected_request"], original)
        self.assertEqual(checked.supplied_request_fingerprint, fingerprint(original))

    def test_replay_transports_full_external_authority_and_full_report(self):
        supplied = {"retained": "complete report"}
        with self.exchange():
            checked = self.client.replay(expected_request=self.authority, build=self.build, assessment=supplied)
        self.assertEqual(checked.operation, "replay-architecture")
        self.assertEqual(self.calls[1]["payload"], {"expected_request": self.authority, "build": self.build, "assessment": supplied})

    def test_negotiation_rejects_changed_limits_profiles_and_unadvertised_operations_before_call(self):
        changes = [
            lambda c: c.update(schema_version="unknown"),
            lambda c: c.update(canonicalization="other"),
            lambda c: c["operations"].remove("verify-architecture"),
            lambda c: c["operations"].append("capabilities"),
            lambda c: c["limits"].update(max_depth=True),
            lambda c: c["limits"].update(max_request_bytes=LIMITS["max_request_bytes"] + 1),
            lambda c: c["profiles"]["architecture"].update(implementation="other"),
            lambda c: c["profiles"]["architecture"].update(resource_profile="unbounded"),
            lambda c: c["profiles"]["architecture"].update(request_schema="unknown"),
            lambda c: c["profiles"]["architecture"].update(operations=[]),
            lambda c: c.update(validation_scopes=[]),
        ]
        for change in changes:
            self.calls.clear()
            with self.subTest(change=changes.index(change)), self.exchange(capability_transform=change), self.assertRaises(CoreProtocolError):
                self.verify()
            self.assertEqual(len(self.calls), 1)

    def test_result_cannot_change_profile_authority_fingerprint_or_claim_scope(self):
        changes = [
            lambda r: r.update(implementation="python"),
            lambda r: r.update(resource_profile="unbounded"),
            lambda r: r.update(supplied_request_fingerprint="f" * 64),
            lambda r: r.update(supplied_build_fingerprint="f" * 64),
            lambda r: r.update(assessment_fingerprint="f" * 64),
            lambda r: r["assessment"].update(search_verified=True),
            lambda r: r["assessment"].update(empirical_validation="pass"),
            lambda r: r["assessment"].update(human_therapeutic_admission="admitted"),
            lambda r: r["assessment"].update(translation_complete=True),
            lambda r: r["assessment"].update(construction_complete=1),
            lambda r: r["assessment"].update(outcome="accepted"),
            lambda r: r["assessment"].update(diagnostics=[{}]),
        ]
        for change in changes:
            with self.subTest(change=changes.index(change)), self.exchange(transform=change), self.assertRaises(CoreProtocolError):
                self.verify()

    def test_each_outcome_is_preserved_without_promoting_incomplete_claims(self):
        for outcome in ("pass", "fail", "unknown", "unsupported"):
            def change(value):
                value["assessment"]["outcome"] = outcome
                value["assessment_fingerprint"] = fingerprint(value["assessment"])
            with self.subTest(outcome=outcome), self.exchange(transform=change):
                checked = self.verify()
                self.assertEqual(checked.outcome, outcome)
                self.assertFalse(checked.translation_complete)

    def test_rejection_and_unsupported_have_no_retry_or_partial_result(self):
        for status, error in (("error", CoreRejected), ("unsupported", CoreUnsupported)):
            self.calls.clear()
            with self.subTest(status=status), self.exchange(rejection=status), self.assertRaises(error):
                self.verify()
            self.assertEqual(len(self.calls), 2)

    def test_cancellation_is_forwarded_to_negotiation_and_semantic_call(self):
        cancelled = lambda: True
        with patch("biocompiler.core_client._exchange", side_effect=CoreCancelled("cancelled")) as exchange:
            with self.assertRaises(CoreCancelled):
                self.client.verify(expected_request=self.authority, build=self.build, cancelled=cancelled)
        self.assertIs(exchange.call_args.args[3], cancelled)
        self.assertEqual(exchange.call_count, 1)

    def test_capabilities_are_defensively_copied(self):
        with self.exchange():
            negotiated = self.client.transport.negotiate("verify-architecture")
        negotiated.profiles["architecture"]["implementation"] = "mutated"
        self.assertEqual(negotiated.profiles["architecture"]["implementation"], IMPLEMENTATION)
