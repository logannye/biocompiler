"""Transport adversaries use Python peers; these tests are not native acceptance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from biocompiler.core_client import (
    CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL, CoreClient,
    CoreProtocolError, CoreRejected, CoreUnsupported, encode_json,
)
from biocompiler.core_policy import (
    ASSESSMENT_SCHEMA, IMPLEMENTATION, PROFILE, RESOURCE_PROFILE, RESULT_SCHEMA,
    VALIDATION_SCOPE, PolicyClient,
)
from biocompiler.policy.examples import build_request
from biocompiler.policy.handoff import prepare_submission
from biocompiler.policy.serialization import document_digest, dump, to_data


def digest(value):
    return hashlib.sha256(encode_json(value)).hexdigest()


def semantic(value):
    if isinstance(value, dict):
        return {key: semantic(item) for key, item in value.items() if key not in ("source_map", "provenance")}
    if isinstance(value, list):
        return [semantic(item) for item in value]
    return value


def assessment(raw):
    selected = raw["request"] if raw["$type"] == "CompilationSubmission" else raw
    program = selected["program"] if selected["$type"] == "BuildRequest" else selected
    path = "/document" + ("/request" if raw["$type"] == "CompilationSubmission" else "")
    path += "/program" if selected["$type"] == "BuildRequest" else ""
    rows = [{"id": value["id"], "kind": value["$type"], "path": f"{path}/declarations/{index}",
             "value": deepcopy(value), "sources": [deepcopy(source) for source in program["source_map"]
                                                   if source["declaration_id"] == value["id"]]}
            for index, value in enumerate(program["declarations"])]
    return {"schema_version": ASSESSMENT_SCHEMA, "status": "valid",
            "document_digest": digest(semantic(selected)), "program_digest": digest(semantic(program)),
            "artifact_digest": digest(raw), "declarations": rows,
            "requirements": [deepcopy(row) for row in rows if row["kind"] == "Requirement"],
            "required_features": ["source.declarations"], "dependencies": [], "assumptions": [],
            "unresolved_obligations": ["execution_and_lowering_unimplemented"], "diagnostics": [],
            "semantic_status": "unresolved", "target_status": "unassessed",
            "lowering": "unsupported", "artifact": "withheld"}


def capabilities():
    return {"schema_version": CAPABILITIES_SCHEMA,
            "operations": ["capabilities", "assess-policy", "replay-policy-assessment"],
            "intent_schemas": ["biocompiler.intent.v0.1"], "canonicalization": "python-json-v1",
            "validation_scopes": [VALIDATION_SCOPE], "profiles": {"policy_frontend": deepcopy(PROFILE)},
            "limits": dict(LIMITS), "claim_scope": "Native source contracts only."}


class PolicyTransportTests(unittest.TestCase):
    def setUp(self):
        self.authoring = build_request("context_gated_response")
        self.raw = to_data(self.authoring)
        self.client = PolicyClient(CoreClient(Path(sys.executable), role="verify"))
        self.calls = []

    def exchange(self, *, mutate=None, mutate_capabilities=None, on_negotiate=None, rejection=None):
        def call(_executable, encoded, _timeout, _cancelled):
            request = json.loads(encoded)
            self.calls.append(request)
            operation = request["operation"]
            if operation == "capabilities":
                value = capabilities()
                if mutate_capabilities:
                    mutate_capabilities(value)
                if on_negotiate:
                    on_negotiate()
            else:
                raw = request["payload"]["document" if operation == "assess-policy" else "expected_document"]
                report = assessment(raw)
                value = {"schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION,
                         "resource_profile": RESOURCE_PROFILE, "validation_scope": VALIDATION_SCOPE,
                         "supplied_document_fingerprint": digest(raw), "assessment_fingerprint": digest(report),
                         "assessment": report}
                if mutate:
                    mutate(value)
            status = rejection if operation != "capabilities" and rejection else "ok"
            response = {"protocol": PROTOCOL, "request_id": request["request_id"], "operation": operation,
                        "status": status, "result": value if status == "ok" else None,
                        "diagnostics": [] if status == "ok" else [{"code": "policy_rejected", "message": "Rejected", "path": "/document"}],
                        "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL,
                                 "executable": "verify"}}
            return encode_json(response), {"ok": 0, "error": 2, "unsupported": 3}[status]
        return patch("biocompiler.core_client._exchange", side_effect=call)

    def assert_report_rejected(self, mutate):
        def changed(result):
            mutate(result["assessment"])
            result["assessment_fingerprint"] = digest(result["assessment"])
        with self.exchange(mutate=changed), self.assertRaises(CoreProtocolError):
            self.client.assess(self.raw)

    def test_complete_frozen_source_and_scope_are_retained(self):
        with self.exchange():
            result = self.client.assess(self.raw)
        self.assertEqual([call["operation"] for call in self.calls], ["capabilities", "assess-policy"])
        self.assertEqual(result.document_digest, document_digest(self.authoring))
        self.assertEqual(result.program_digest, document_digest(self.authoring.program))
        self.assertEqual(result.artifact_digest, digest(self.raw))
        self.assertEqual(result.assessment["lowering"], "unsupported")
        result.assessment["declarations"].clear()
        self.assertTrue(result.assessment["declarations"])
        with self.assertRaises(FrozenInstanceError):
            result.status = "invalid"

    def test_program_and_submission_have_separate_input_artifact_identities(self):
        program = to_data(self.authoring.program)
        submission = to_data(prepare_submission(self.authoring))
        with self.exchange():
            first = self.client.assess(program)
            second = self.client.assess(submission)
        self.assertEqual(first.program_digest, second.program_digest)
        self.assertNotEqual(first.document_digest, second.document_digest)
        self.assertNotEqual(first.artifact_digest, second.artifact_digest)

    def test_source_paths_must_bind_exact_declaration_occurrences(self):
        self.assert_report_rejected(lambda report: report["declarations"][0].update(path="/document/program/declarations/1"))
        self.assert_report_rejected(lambda report: report["requirements"][0].update(path="/document/declarations/0"))

    def test_caller_mutation_during_negotiation_cannot_change_sent_authority(self):
        before = deepcopy(self.raw)
        with self.exchange(on_negotiate=lambda: self.raw["program"].update(name="changed")):
            result = self.client.assess(self.raw)
        self.assertEqual(self.calls[-1]["payload"]["document"], before)
        self.assertEqual(result.artifact_digest, digest(before))

    def test_each_negotiated_profile_field_is_authoritative(self):
        for field in PROFILE:
            with self.subTest(field=field), self.exchange(
                mutate_capabilities=lambda value: value["profiles"]["policy_frontend"].pop(field)
            ), self.assertRaises(CoreProtocolError):
                self.client.assess(self.raw)

    def test_claim_upgrade_is_rejected_even_with_recomputed_report_digest(self):
        for key, value in (("semantic_status", "proved"), ("target_status", "supported"),
                           ("lowering", "complete"), ("artifact", "produced")):
            with self.subTest(key=key):
                self.assert_report_rejected(lambda report: report.update({key: value}))

    def test_any_source_identity_change_is_rejected(self):
        for key in ("document_digest", "program_digest", "artifact_digest"):
            with self.subTest(key=key):
                self.assert_report_rejected(lambda report: report.update({key: "0" * 64}))

    def test_declaration_omission_reordering_and_mutation_are_rejected(self):
        self.assert_report_rejected(lambda report: report["declarations"].pop())
        self.assert_report_rejected(lambda report: report["declarations"].reverse())
        self.assert_report_rejected(lambda report: report["declarations"][0]["value"].update(id="different"))
        self.assert_report_rejected(lambda report: report["declarations"][0].update(kind="Effect"))

    def test_requirement_omission_is_rejected(self):
        self.assertTrue(assessment(self.raw)["requirements"])
        self.assert_report_rejected(lambda report: report["requirements"].clear())

    def test_source_correspondence_is_not_lost_when_semantic_digest_ignores_it(self):
        from biocompiler.policy.model import SourceSpan
        source = SourceSpan(self.authoring.program.declarations[0].id, "author.py", 9, pattern="pattern")
        program = replace(self.authoring.program, source_map=(source,))
        changed = replace(self.authoring, program=program)
        self.assertEqual(document_digest(changed), document_digest(self.authoring))
        self.raw = to_data(changed)
        self.assert_report_rejected(lambda report: report["declarations"][0]["sources"].clear())

    def test_invalid_status_requires_diagnostics_and_valid_status_prohibits_them(self):
        self.assert_report_rejected(lambda report: report.update(status="invalid"))
        self.assert_report_rejected(lambda report: report["diagnostics"].append(
            {"code": "bad", "message": "Contradiction", "path": "/document/program"}))

    def test_malformed_diagnostics_and_duplicate_inventory_are_rejected(self):
        self.assert_report_rejected(lambda report: report.update(required_features=["same", "same"]))
        self.assert_report_rejected(lambda report: report.update(dependencies=[{"$type": "callback"}]))
        self.assert_report_rejected(lambda report: report.update(status="invalid", diagnostics=[
            {"code": "bad", "message": "Contradiction", "path": None}]))

    def test_native_rejection_and_unsupported_never_fall_back(self):
        for status, error in (("error", CoreRejected), ("unsupported", CoreUnsupported)):
            with self.subTest(status=status), self.exchange(rejection=status), self.assertRaises(error):
                self.client.assess(self.raw)

    def test_fresh_replay_requires_identical_complete_assessment(self):
        original = assessment(self.raw)
        with self.exchange():
            result = self.client.replay(expected_document=self.raw, assessment=original)
        self.assertEqual(result.assessment, original)
        original["unresolved_obligations"].clear()
        with self.exchange(), self.assertRaises(CoreProtocolError):
            self.client.replay(expected_document=self.raw, assessment=original)

    def test_authoring_adapter_does_not_run_python_validation(self):
        from biocompiler.policy.native import assess
        with self.exchange(), patch("biocompiler.policy.validation.check", side_effect=AssertionError("Python semantic authority")):
            result = assess(self.authoring, client=self.client)
        self.assertEqual(result.status, "valid")

    def test_cli_requires_explicit_backend_and_returns_native_assessment(self):
        from biocompiler.policy.cli import main
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "request.json"
            dump(self.authoring, document)
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(["assess-native", str(document)])
            self.assertEqual(error.exception.code, 2)
            stdout = io.StringIO()
            with self.exchange(), redirect_stdout(stdout):
                code = main(["assess-native", str(document), "--verify", sys.executable, "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(stdout.getvalue())["artifact"], "withheld")


if __name__ == "__main__":
    unittest.main()
