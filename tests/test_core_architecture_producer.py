"""Adversarial producer transport checks; no native or Python semantic execution."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler.core_architecture import (
    ASSESSMENT_SCHEMA, CHECKER_POLICY, CLAIM_SCOPE,
    IMPLEMENTATION as CHECKER_IMPLEMENTATION, RESOURCE_PROFILE as CHECKER_RESOURCE_PROFILE,
    RESULT_SCHEMA as ASSESSMENT_RESULT_SCHEMA, VALIDATION_SCOPE as CHECKER_SCOPE,
)
from biocompiler.core_architecture_producer import (
    BUILD_RESULT_SCHEMA, BUILD_SCHEMA, EXPORT_RESULT_SCHEMA, EXPORT_SCHEMA,
    IMPLEMENTATION, PROFILE, RESOURCE_PROFILE, VALIDATION_SCOPE, ArchitectureProducerClient,
)
from biocompiler.core_client import (
    CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL, CoreCancelled, CoreClient,
    CoreProtocolError, CoreRejected, CoreUnsupported, encode_json,
)


def encoded(value):
    return encode_json(value, limit=LIMITS["max_response_bytes"])


def fingerprint(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def capabilities():
    return {"schema_version": CAPABILITIES_SCHEMA,
            "operations": ["capabilities", "compile-architecture", "export-architecture"],
            "intent_schemas": ["biocompiler.intent.v0.1"], "canonicalization": "python-json-v1",
            "validation_scopes": [VALIDATION_SCOPE], "profiles": {"architecture_producer": deepcopy(PROFILE)},
            "limits": dict(LIMITS), "claim_scope": "Supplied contracts only."}


def build_record():
    # Transport-shape fixtures deliberately do not stand in for semantic tests.
    return {"schema_version": BUILD_SCHEMA, "request_fingerprint": "a" * 64,
            "execution": {"source": "complete native source record"}, "plan": {"member": "RNA"},
            "construction": {"inventory": "complete native construction record"},
            "alternatives": [], "diagnostics": [], "status": "compiled", "match_instances": []}


def verification(request, raw_build, normalized_build):
    assessment = {"schema_version": ASSESSMENT_SCHEMA, "request_fingerprint": "a" * 64,
                  "build_fingerprint": fingerprint(normalized_build), "outcome": "pass",
                  "translation_complete": False, "construction_complete": True, "diagnostics": [],
                  "unresolved": ["empirical component function"], "assumptions": ["supplied contracts"],
                  "checker_version": CHECKER_POLICY, "claim_scope": CLAIM_SCOPE, "search_verified": False,
                  "empirical_validation": "unknown", "human_therapeutic_admission": "not_admitted"}
    return {"schema_version": ASSESSMENT_RESULT_SCHEMA, "implementation": CHECKER_IMPLEMENTATION,
            "resource_profile": CHECKER_RESOURCE_PROFILE, "validation_scope": CHECKER_SCOPE,
            "supplied_request_fingerprint": fingerprint(request), "supplied_build_fingerprint": fingerprint(raw_build),
            "assessment_fingerprint": fingerprint(assessment), "assessment": assessment}


def result(operation, payload):
    request = payload["request" if operation == "compile-architecture" else "expected_request"]
    build = build_record()
    value = {"schema_version": BUILD_RESULT_SCHEMA if operation == "compile-architecture" else EXPORT_RESULT_SCHEMA,
             "implementation": IMPLEMENTATION, "resource_profile": RESOURCE_PROFILE, "validation_scope": VALIDATION_SCOPE,
             "supplied_request_fingerprint": fingerprint(request), "request_fingerprint": "a" * 64,
             "build_fingerprint": fingerprint(build),
             "verification": verification(request, build if operation == "compile-architecture" else payload["build"], build)}
    if operation == "compile-architecture":
        value["build_json"] = encoded(build).decode()
    else:
        value["supplied_build_fingerprint"] = fingerprint(payload["build"])
        manifest = {"request_fingerprint": "a" * 64, "build": build,
                    "verification": value["verification"]["assessment"], "delivered_member_ids": ["rna.α"],
                    "source_authority": "Retain the independently supplied request separately."}
        value["fasta"] = ">rna.α alphabet=RNA\nAUGUAA\n"
        set_manifest(value, manifest)
    return value


def set_manifest(value, manifest):
    value["manifest_json"] = encoded(manifest).decode()
    refresh_export(value)


def refresh_export(value):
    value["fasta_sha256"] = hashlib.sha256(value["fasta"].encode()).hexdigest()
    value["manifest_sha256"] = hashlib.sha256(value["manifest_json"].encode()).hexdigest()
    value["export_fingerprint"] = fingerprint({"schema_version": EXPORT_SCHEMA,
        "fasta": value["fasta"], "manifest": json.loads(value["manifest_json"])})


def change_manifest(value, change):
    manifest = json.loads(value["manifest_json"])
    change(manifest)
    set_manifest(value, manifest)


def change_build(value, change):
    build = json.loads(value["build_json"])
    change(build)
    value["build_json"] = encoded(build).decode()
    value["build_fingerprint"] = fingerprint(build)
    receipt = value["verification"]
    receipt["supplied_build_fingerprint"] = fingerprint(build)
    receipt["assessment"]["build_fingerprint"] = fingerprint(build)
    receipt["assessment_fingerprint"] = fingerprint(receipt["assessment"])


class ArchitectureProducerTransportTests(unittest.TestCase):
    def setUp(self):
        self.client = ArchitectureProducerClient(CoreClient(Path(sys.executable)))
        self.calls = []
        self.authority = {"source": "original", "values": [9007199254740993, -0.0], "provenance": "原始"}
        self.build = build_record()

    def exchange(self, transform=None, capability_transform=None, rejection=None, on_negotiate=None):
        def invoke(_executable, data, _timeout, cancelled):
            request = json.loads(data)
            self.calls.append((request, cancelled))
            operation = request["operation"]
            if operation == "capabilities":
                value = capabilities()
                if capability_transform:
                    capability_transform(value)
                if on_negotiate:
                    on_negotiate()
            else:
                value = result(operation, request["payload"])
                if transform:
                    transform(value)
            status = rejection if operation != "capabilities" and rejection else "ok"
            response = {"protocol": PROTOCOL, "request_id": request["request_id"], "operation": operation,
                        "status": status, "result": value if status == "ok" else None,
                        "diagnostics": [] if status == "ok" else [{"code": "independent_rejection", "message": "Rejected", "path": None}],
                        "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": "core"}}
            return encoded(response), {"ok": 0, "error": 2, "unsupported": 3}[status]
        return patch("biocompiler.core_client._exchange", side_effect=invoke)

    def compile(self):
        return self.client.compile(request=self.authority)

    def export(self):
        return self.client.export(expected_request=self.authority, build=self.build)

    def test_compile_keeps_complete_immutable_bytes_and_scoped_verification(self):
        with self.exchange():
            artifact = self.compile()
        self.assertEqual([call[0]["operation"] for call in self.calls], ["capabilities", "compile-architecture"])
        self.assertEqual(artifact.build_json, encoded(build_record()))
        self.assertEqual(artifact.build_fingerprint, fingerprint(artifact.build))
        self.assertEqual(artifact.status, "compiled")
        self.assertEqual(artifact.verification.outcome, "pass")
        self.assertFalse(artifact.verification.translation_complete)
        artifact.build["execution"].clear()
        self.assertEqual(artifact.build, build_record())
        with self.assertRaises(FrozenInstanceError):
            artifact.status = "partial"

    def test_export_preserves_utf8_fasta_full_manifest_and_all_pins(self):
        with self.exchange():
            artifact = self.export()
        self.assertEqual(artifact.fasta_bytes, ">rna.α alphabet=RNA\nAUGUAA\n".encode())
        self.assertEqual(artifact.fasta_sha256, hashlib.sha256(artifact.fasta_bytes).hexdigest())
        self.assertEqual(artifact.manifest_sha256, hashlib.sha256(artifact.manifest_json).hexdigest())
        self.assertEqual(artifact.export_fingerprint, fingerprint(artifact.export))
        self.assertEqual(artifact.manifest["build"], self.build)
        self.assertEqual(artifact.manifest["verification"], artifact.verification.assessment)
        artifact.manifest["build"].clear()
        artifact.export["manifest"].clear()
        self.assertEqual(artifact.manifest["build"], self.build)
        self.assertFalse(artifact.verification.translation_complete)
        with self.assertRaises(FrozenInstanceError):
            artifact.manifest_json = b"{}"

    def test_full_authority_is_frozen_before_negotiation_for_both_operations(self):
        for operation in (self.compile, self.export):
            original_request, original_build = deepcopy(self.authority), deepcopy(self.build)
            def mutate():
                self.authority["values"].append(7)
                self.build["execution"]["changed"] = True
            with self.subTest(operation=operation.__name__), self.exchange(on_negotiate=mutate):
                artifact = operation()
            sent = self.calls[-1][0]["payload"]
            self.assertEqual(sent.get("request", sent.get("expected_request")), original_request)
            self.assertEqual(artifact.supplied_request_fingerprint, fingerprint(original_request))
            if operation.__name__ == "export":
                self.assertEqual(sent["build"], original_build)
                self.assertEqual(artifact.supplied_build_fingerprint, fingerprint(original_build))

    def test_raw_and_normalized_build_authorities_remain_distinct(self):
        self.build["match_instances"] = [{"id": "raw input imports into normalized native record"}]
        with self.exchange():
            artifact = self.export()
        self.assertNotEqual(artifact.supplied_build_fingerprint, artifact.build_fingerprint)
        self.assertEqual(artifact.supplied_build_fingerprint, fingerprint(self.build))
        self.assertEqual(artifact.build_fingerprint, fingerprint(build_record()))

    def test_verify_role_is_rejected_before_any_process_call(self):
        client = ArchitectureProducerClient(CoreClient(Path(sys.executable), role="verify"))
        with self.exchange(), self.assertRaises(CoreProtocolError):
            client.compile(request=self.authority)
        self.assertEqual(self.calls, [])

    def test_every_negotiated_profile_field_is_pinned_before_production(self):
        changes = [lambda c: c.update(validation_scopes=[]),
                   lambda c: c["operations"].remove("compile-architecture"),
                   lambda c: c["limits"].update(max_response_bytes=1),
                   lambda c: c["profiles"]["architecture_producer"].update(extra="authority")]
        for key in PROFILE:
            changes.append(lambda c, key=key: c["profiles"]["architecture_producer"].update({key: [] if key == "operations" else "other"}))
        for index, change in enumerate(changes):
            self.calls.clear()
            with self.subTest(index=index), self.exchange(capability_transform=change), self.assertRaises(CoreProtocolError):
                self.compile()
            self.assertEqual(len(self.calls), 1)

    def test_compile_rejects_changed_profile_census_bytes_hashes_and_nested_authority(self):
        changes = [lambda r: r.update(extra=True), lambda r: r.pop("verification"),
                   lambda r: r.update(schema_version="other"), lambda r: r.update(implementation="python"),
                   lambda r: r.update(resource_profile="unbounded"), lambda r: r.update(validation_scope="accepted"),
                   lambda r: r.update(supplied_request_fingerprint="f" * 64),
                   lambda r: r.update(request_fingerprint="f" * 64), lambda r: r.update(build_fingerprint="f" * 64),
                   lambda r: r.update(build_json=r["build_json"] + "\n"),
                   lambda r: r.update(build_json=json.dumps(json.loads(r["build_json"]), indent=2)),
                   lambda r: r.update(build_json="[]"), lambda r: r.update(build_json={}),
                   lambda r: r.update(build_json='{"duplicate":0,"duplicate":1}'),
                   lambda r: r.update(build_json='{"invalid":NaN}'),
                   lambda r: r["verification"].update(supplied_request_fingerprint="f" * 64),
                   lambda r: r["verification"].update(supplied_build_fingerprint="f" * 64),
                   lambda r: r["verification"]["assessment"].update(human_therapeutic_admission="admitted"),
                   lambda r: change_build(r, lambda b: b.update(schema_version="other")),
                   lambda r: change_build(r, lambda b: b.update(status="accepted")),
                   lambda r: change_build(r, lambda b: b.update(extra="discarded authority")),
                   lambda r: change_build(r, lambda b: b.pop("execution"))]
        for index, change in enumerate(changes):
            with self.subTest(index=index), self.exchange(transform=change), self.assertRaises(CoreProtocolError):
                self.compile()

    def test_nested_assessment_normalized_pins_must_agree_even_when_rehashed(self):
        for key in ("request_fingerprint", "build_fingerprint"):
            def change(value):
                receipt = value["verification"]
                receipt["assessment"][key] = "e" * 64
                receipt["assessment_fingerprint"] = fingerprint(receipt["assessment"])
            for operation in (self.compile, self.export):
                with self.subTest(key=key, operation=operation.__name__), self.exchange(transform=change), self.assertRaises(CoreProtocolError):
                    operation()

    def test_all_build_statuses_and_scoped_outcomes_are_preserved(self):
        for status in ("compiled", "partial", "unsupported", "no_solution", "search_exhausted"):
            for outcome in ("pass", "fail", "unknown", "unsupported"):
                def change(value):
                    change_build(value, lambda build: build.update(status=status))
                    receipt = value["verification"]
                    receipt["assessment"]["outcome"] = outcome
                    receipt["assessment_fingerprint"] = fingerprint(receipt["assessment"])
                with self.subTest(status=status, outcome=outcome), self.exchange(transform=change):
                    artifact = self.compile()
                self.assertEqual(artifact.status, status)
                self.assertEqual(artifact.verification.outcome, outcome)
                self.assertFalse(artifact.verification.translation_complete)

    def test_export_rejects_altered_artifact_bytes_even_if_other_fields_are_valid(self):
        changes = [lambda r: r.update(extra=True), lambda r: r.pop("manifest_sha256"),
                   lambda r: r.update(schema_version=BUILD_RESULT_SCHEMA),
                   lambda r: r.update(supplied_request_fingerprint="e" * 64),
                   lambda r: r.update(supplied_build_fingerprint="e" * 64),
                   lambda r: r.update(export_fingerprint="e" * 64), lambda r: r.update(fasta_sha256="e" * 64),
                   lambda r: r.update(manifest_sha256="e" * 64), lambda r: r.update(fasta=r["fasta"] + "A"),
                   lambda r: r.update(manifest_json=r["manifest_json"] + "\n"),
                   lambda r: r.update(manifest_json='{"duplicate":0,"duplicate":1}'),
                   lambda r: r.update(fasta=None), lambda r: r.update(manifest_json=[])]
        for index, change in enumerate(changes):
            with self.subTest(index=index), self.exchange(transform=change), self.assertRaises(CoreProtocolError):
                self.export()

    def test_rehashed_export_cannot_drop_or_substitute_complete_manifest_authority(self):
        changes = [lambda m: m.update(request_fingerprint="e" * 64), lambda m: m.update(source_authority="build is sufficient"),
                   lambda m: m.update(delivered_member_ids=[]), lambda m: m.update(delivered_member_ids=["rna", "rna"]),
                   lambda m: m.update(extra=True), lambda m: m.pop("build"),
                   lambda m: m["build"].update(execution={}),
                   lambda m: m["verification"].update(assumptions=[]),
                   lambda m: m["verification"].update(search_verified=True),
                   lambda m: m["verification"].pop("claim_scope")]
        for index, change in enumerate(changes):
            with self.subTest(index=index), self.exchange(transform=lambda r: change_manifest(r, change)), self.assertRaises(CoreProtocolError):
                self.export()

    def test_export_requires_fresh_pass_and_complete_construction_but_not_translation(self):
        for change in (lambda a: a.update(outcome="fail"), lambda a: a.update(outcome="unknown"),
                       lambda a: a.update(outcome="unsupported"), lambda a: a.update(construction_complete=False)):
            def transform(value):
                receipt = value["verification"]
                change(receipt["assessment"])
                receipt["assessment_fingerprint"] = fingerprint(receipt["assessment"])
                change_manifest(value, lambda m: m.update(verification=receipt["assessment"]))
            with self.subTest(change=change), self.exchange(transform=transform), self.assertRaises(CoreProtocolError):
                self.export()

    def test_fasta_is_required_even_with_recomputed_hashes(self):
        def transform(value):
            value["fasta"] = "AUGUAA\n"
            refresh_export(value)
        with self.exchange(transform=transform), self.assertRaises(CoreProtocolError):
            self.export()

    def test_failures_return_no_artifact_and_never_retry_or_fall_back(self):
        for operation in (self.compile, self.export):
            for status, error in (("error", CoreRejected), ("unsupported", CoreUnsupported)):
                self.calls.clear()
                with self.subTest(operation=operation.__name__, status=status), self.exchange(rejection=status), self.assertRaises(error):
                    operation()
                self.assertEqual(len(self.calls), 2)

    def test_cancellation_is_forwarded_to_both_calls_and_never_retried(self):
        cancelled = lambda: False
        with self.exchange():
            self.client.compile(request=self.authority, cancelled=cancelled)
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all(call[1] is cancelled for call in self.calls))
        with patch("biocompiler.core_client._exchange", side_effect=CoreCancelled("cancelled")) as exchange:
            with self.assertRaises(CoreCancelled):
                self.client.export(expected_request=self.authority, build=self.build, cancelled=cancelled)
        self.assertEqual(exchange.call_count, 1)
        self.assertIs(exchange.call_args.args[3], cancelled)

    def test_invalid_input_is_rejected_before_negotiation(self):
        self.authority["bad"] = float("nan")
        with self.exchange(), self.assertRaises(CoreProtocolError):
            self.compile()
        self.assertEqual(self.calls, [])
