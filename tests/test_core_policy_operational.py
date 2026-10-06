"""Adversarial Python transport peers are not native execution acceptance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler.core_client import (
    CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL, CoreClient, CoreProtocolError,
    CoreRejected, CoreTimeout, CoreTransportError, CoreUnavailable, CoreUnsupported, encode_json,
)
from biocompiler.core_policy_operational import (
    CANDIDATE_SCHEMA, EXECUTION_SCHEMA, IMPLEMENTATION, OPERATIONAL_PROFILE, PROFILE,
    PRODUCER_PROFILE, REPORT_SCHEMA, RESOURCE_PROFILE, RESULT_SCHEMA, VALIDATION_SCOPE,
    OperationalPolicyClient,
)
from biocompiler.policy.examples import build_request
from biocompiler.policy.serialization import to_data
from tests.test_core_policy import assessment as source_assessment, digest


def definitions():
    return {"schema_version": "biocompiler.policy_operational_definitions.v0.1",
            "profile": OPERATIONAL_PROFILE, "definitions": []}


def timeline():
    return {"profile": "biocompiler.policy_timeline.v0.1", "executor": "executor", "horizon": "3",
            "encounters": [], "observations": [], "feedback": [],
            "bounds": {"max_ticks": 5, "max_inputs": 10, "max_encounters": 4, "max_attempts": 10,
                       "max_work": 1000, "max_trace_items": 100, "max_microsteps": 5}}


def candidate(document, descriptors):
    assessment = source_assessment(document)
    return {"schema_version": CANDIDATE_SCHEMA, "profile": OPERATIONAL_PROFILE,
            "source_document": deepcopy(document), "descriptor_bundle": deepcopy(descriptors),
            "source_artifact_digest": digest(document), "descriptors_digest": digest(descriptors),
            "source_ledger": assessment["declarations"], "requirements_ledger": assessment["requirements"],
            "assumptions": assessment["assumptions"], "unresolved_obligations": assessment["unresolved_obligations"],
            "nodes": [{"id": row["id"], "kind": row["kind"], "source_path": row["path"],
                       "data": {key: value for key, value in row["value"].items() if key != "$type"}}
                      for row in assessment["declarations"]]}


def report(payload, *, executing=False):
    lowered = payload.get("candidate") or candidate(payload["document"], payload["definitions"])
    assessment = source_assessment(payload["document"])
    admission = {"schema_version": "biocompiler.policy_operational_admission.v0.1", "status": "admitted",
                 "profile": OPERATIONAL_PROFILE, "document_artifact_digest": digest(payload["document"]),
                 "descriptors_digest": digest(payload["definitions"]), "source_assessment": deepcopy(assessment),
                 "target_status": "unassessed", "artifact": "withheld"}
    result = {"schema_version": REPORT_SCHEMA, "source_assessment": source_assessment(payload["document"]),
              "correspondence": {"schema_version": "biocompiler.policy_correspondence.v0.1", "status": "valid",
                                 "profile": OPERATIONAL_PROFILE,
                                 "candidate_fingerprint": digest(lowered),
                                 "document_artifact_digest": digest(payload["document"]),
                                 "descriptors_digest": digest(payload["definitions"]),
                                 "source_assessment": deepcopy(assessment), "admission": admission,
                                 "requirements": deepcopy(assessment["requirements"]),
                                 "assumptions": deepcopy(assessment["assumptions"]),
                                 "unresolved_obligations": deepcopy(assessment["unresolved_obligations"]),
                                 "target_status": "unassessed", "artifact": "withheld"},
              "artifact": "withheld", "target_status": "unassessed", "realization": "unassessed"}
    if executing:
        result["execution"] = {
            "schema_version": EXECUTION_SCHEMA, "profile": OPERATIONAL_PROFILE,
            "behavior_digest": digest(lowered), "timeline_digest": digest(payload["timeline"]),
            "horizon": payload["timeline"]["horizon"], "executor": payload["timeline"]["executor"],
            "status": "complete", "frames": [{"time": str(tick)} for tick in range(4)], "attempts": [],
            "requirements": [
                {"id": row["id"], "kind": row["value"]["kind"], "status": "unknown", "source": deepcopy(row["value"]),
                 "assumptions": deepcopy(row["value"]["assumptions"]),
                 "conditional": bool(row["value"]["assumptions"] or assessment["assumptions"]),
                 "coverage": {"samples": 0, "true": 0, "false": 0, "unknown": 0, "triggers": 0,
                              "active": 0, "inactive": 0, "horizon_complete": True}, "obligations": []}
                for row in assessment["requirements"]],
            "usage": {"ticks": 4, "work": 20, "trace_items": 0, "attempts": 0},
            "claim": "bounded_supplied_timeline_only",
        }
    return result


def result(payload, operation):
    lowered = deepcopy(payload.get("candidate") or candidate(payload["document"], payload["definitions"]))
    checked = report(payload, executing=operation in ("execute-policy", "replay-policy-execution"))
    return {"schema_version": RESULT_SCHEMA, "implementation": IMPLEMENTATION,
            "resource_profile": RESOURCE_PROFILE, "validation_scope": VALIDATION_SCOPE,
            "request_fingerprint": digest({key: value for key, value in payload.items() if key != "report"}),
            "candidate_fingerprint": digest(lowered), "report_fingerprint": digest(checked),
            "candidate": lowered, "report": checked}


def capabilities(*, role="core"):
    profiles = {"policy_operational": deepcopy(PROFILE)}
    operations = ["capabilities", *PROFILE["operations"]]
    if role == "core":
        profiles["policy_operational_producer"] = deepcopy(PRODUCER_PROFILE)
        operations.append("compile-policy")
    return {"schema_version": CAPABILITIES_SCHEMA, "operations": operations,
            "intent_schemas": ["biocompiler.intent.v0.1"], "canonicalization": "python-json-v1",
            "validation_scopes": [VALIDATION_SCOPE], "profiles": profiles,
            "limits": dict(LIMITS), "claim_scope": "Bounded supplied policy timeline only; no realization."}


class OperationalPolicyTransportTests(unittest.TestCase):
    def setUp(self):
        self.authoring = build_request("context_gated_response")
        self.document = to_data(self.authoring)
        self.definitions = definitions()
        self.candidate = candidate(self.document, self.definitions)
        self.timeline = timeline()
        self.client = OperationalPolicyClient(CoreClient(Path(sys.executable), role="core"))
        self.calls = []

    def payload(self):
        return {"document": self.document, "definitions": self.definitions,
                "candidate": self.candidate, "timeline": self.timeline}

    def exchange(self, *, mutate=None, mutate_capabilities=None, on_negotiate=None,
                 rejection=None, role="core", failure=None):
        def call(_executable, encoded, _timeout, _cancelled):
            request = json.loads(encoded)
            self.calls.append(request)
            operation = request["operation"]
            if operation == "capabilities":
                value = capabilities(role=role)
                if mutate_capabilities:
                    mutate_capabilities(value)
                if on_negotiate:
                    on_negotiate()
            else:
                if failure:
                    raise failure
                value = result(request["payload"], operation)
                if mutate:
                    mutate(value)
            status = rejection if operation != "capabilities" and rejection else "ok"
            response = {"protocol": PROTOCOL, "request_id": request["request_id"], "operation": operation,
                        "status": status, "result": value if status == "ok" else None,
                        "diagnostics": [] if status == "ok" else [{"code": "policy_rejected", "message": "Rejected", "path": "/document"}],
                        "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL,
                                 "executable": role}}
            return encode_json(response), {"ok": 0, "error": 2, "unsupported": 3}[status]
        return patch("biocompiler.core_client._exchange", side_effect=call)

    def execute(self):
        return self.client.execute(self.document, self.definitions, self.candidate, self.timeline)

    def assert_changed_rejected(self, mutate, *, compile=False):
        def changed(value):
            mutate(value)
            value["candidate_fingerprint"] = digest(value["candidate"])
            value["report_fingerprint"] = digest(value["report"])
        with self.exchange(mutate=changed), self.assertRaises(CoreProtocolError):
            if compile:
                self.client.compile(self.document, self.definitions)
            else:
                self.execute()

    def test_compile_and_checked_execution_retain_complete_authority(self):
        with self.exchange():
            compiled = self.client.compile(self.document, self.definitions)
            checked = self.client.check_lowering(self.document, self.definitions, compiled.candidate)
            executed = self.execute()
            replayed = self.client.replay(self.document, self.definitions, self.candidate,
                                          self.timeline, executed.report)
        self.assertEqual(compiled.candidate, self.candidate)
        self.assertEqual(checked.report, compiled.report)
        self.assertEqual(executed.report, replayed.report)
        self.assertEqual(executed.request_fingerprint, replayed.request_fingerprint)
        self.assertNotEqual(compiled.request_fingerprint, checked.request_fingerprint)
        self.assertEqual(executed.report["artifact"], "withheld")
        self.assertEqual(executed.report["target_status"], "unassessed")
        self.assertEqual([call["operation"] for call in self.calls][::2], ["capabilities"] * 4)

    def test_result_is_frozen_and_all_json_reads_are_independent_snapshots(self):
        with self.exchange():
            value = self.execute()
        value.candidate["nodes"].clear()
        value.report["source_assessment"]["declarations"].clear()
        value.result.clear()
        self.assertEqual(value.candidate, self.candidate)
        self.assertTrue(value.report["source_assessment"]["declarations"])
        with self.assertRaises(FrozenInstanceError):
            value.report_fingerprint = "0" * 64

    def test_negotiation_caller_mutations_cannot_change_any_supplied_authority(self):
        original = deepcopy(self.payload())
        retained = report(self.payload(), executing=True)
        before_report = deepcopy(retained)
        def mutate():
            self.document["program"]["name"] = "changed"
            self.definitions["definitions"].append("changed")
            self.candidate["nodes"].clear()
            self.timeline["bounds"]["max_work"] += 1
            retained["execution"]["frames"].append("changed")
        with self.exchange(on_negotiate=mutate):
            replayed = self.client.replay(self.document, self.definitions, self.candidate, self.timeline, retained)
        self.assertEqual(self.calls[-1]["payload"], {**original, "report": before_report})
        self.assertEqual(replayed.report, before_report)

    def test_missing_and_each_wrong_negotiated_profile_field_are_rejected(self):
        for field in PROFILE:
            with self.subTest(field=field), self.exchange(mutate_capabilities=lambda value: value["profiles"]["policy_operational"].pop(field)), self.assertRaises(CoreProtocolError):
                self.execute()
        with self.exchange(mutate_capabilities=lambda value: value["profiles"].clear()), self.assertRaises(CoreProtocolError):
            self.execute()
        with self.exchange(mutate_capabilities=lambda value: value.update(validation_scopes=[])), self.assertRaises(CoreProtocolError):
            self.execute()

    def test_compile_requires_core_role_and_exact_producer_negotiation(self):
        client = OperationalPolicyClient(CoreClient(Path(sys.executable), role="verify"))
        with self.exchange(role="verify"), self.assertRaises(CoreProtocolError):
            client.compile(self.document, self.definitions)
        self.assertEqual(self.calls, [])
        for field in PRODUCER_PROFILE:
            with self.subTest(field=field), self.exchange(mutate_capabilities=lambda value: value["profiles"]["policy_operational_producer"].pop(field)), self.assertRaises(CoreProtocolError):
                self.client.compile(self.document, self.definitions)

    def test_verifier_can_check_and_execute_without_producer_capability(self):
        client = OperationalPolicyClient(CoreClient(Path(sys.executable), role="verify"))
        with self.exchange(role="verify"):
            self.assertEqual(client.check_lowering(self.document, self.definitions, self.candidate).executable, "verify")
            self.assertEqual(client.execute(self.document, self.definitions, self.candidate, self.timeline).executable, "verify")

    def test_each_result_identity_and_closed_envelope_field_is_checked(self):
        for field in ("request_fingerprint", "candidate_fingerprint", "report_fingerprint"):
            with self.subTest(field=field), self.exchange(mutate=lambda value: value.update({field: "0" * 64})), self.assertRaises(CoreProtocolError):
                self.execute()
        for field in ("schema_version", "implementation", "resource_profile", "validation_scope"):
            with self.subTest(field=field):
                self.assert_changed_rejected(lambda value: value.update({field: "wrong"}))
        self.assert_changed_rejected(lambda value: value.update(added="unnegotiated"))

    def test_every_external_input_including_bounds_is_bound_to_request_identity(self):
        for field in ("document", "definitions", "candidate", "timeline"):
            def changed(value):
                forged = deepcopy(self.payload())
                forged[field] = None
                value["request_fingerprint"] = digest(forged)
            with self.subTest(field=field):
                self.assert_changed_rejected(changed)
        def changed_bound(value):
            forged = deepcopy(self.payload())
            forged["timeline"]["bounds"]["max_work"] += 1
            value["request_fingerprint"] = digest(forged)
        self.assert_changed_rejected(changed_bound)

    def test_changed_candidate_or_omitted_source_obligations_cannot_be_rehashed_away(self):
        for field in ("source_ledger", "requirements_ledger", "unresolved_obligations", "nodes"):
            with self.subTest(field=field):
                self.assert_changed_rejected(lambda value: value["candidate"][field].clear())
        for field in ("source_document", "descriptor_bundle"):
            with self.subTest(field=field):
                self.assert_changed_rejected(lambda value: value["candidate"].update({field: {}}), compile=True)
        self.assert_changed_rejected(lambda value: value["candidate"]["descriptor_bundle"].update(extra=1), compile=True)
        self.assert_changed_rejected(lambda value: value["candidate"].update(source_artifact_digest="0" * 64), compile=True)

    def test_claim_upgrades_and_source_ledger_mutations_reject_even_after_rehash(self):
        for field in ("artifact", "target_status", "realization"):
            with self.subTest(field=field):
                self.assert_changed_rejected(lambda value: value["report"].update({field: "accepted"}))
        self.assert_changed_rejected(lambda value: value["report"]["source_assessment"]["declarations"].pop())
        self.assert_changed_rejected(lambda value: value["report"]["source_assessment"]["requirements"].clear())
        self.assert_changed_rejected(lambda value: value["report"].update(unexpected=True))

    def test_execution_keeps_every_requirement_and_exact_trace_bounds(self):
        self.assert_changed_rejected(lambda value: value["report"]["execution"]["requirements"].clear())
        self.assert_changed_rejected(lambda value: value["report"]["execution"]["requirements"][0].update(source={}))
        self.assert_changed_rejected(lambda value: value["report"]["execution"]["requirements"][0].update(conditional="unconditional"))
        self.assert_changed_rejected(lambda value: value["report"]["execution"]["frames"].pop())
        for field in ("timeline_digest", "behavior_digest"):
            with self.subTest(field=field):
                self.assert_changed_rejected(lambda value: value["report"]["execution"].update({field: "0" * 64}))
        self.assert_changed_rejected(lambda value: value["report"]["execution"]["usage"].update(work=1001))
        self.assert_changed_rejected(lambda value: value["report"]["execution"].update(claim="universal"))

    def test_replay_rejects_any_complete_report_mutation_including_frames(self):
        retained = report(self.payload(), executing=True)
        for mutate in (
            lambda value: value["execution"]["frames"].append({"altered": True}),
            lambda value: value["execution"]["usage"].update(work=21),
            lambda value: value["source_assessment"]["unresolved_obligations"].clear(),
            lambda value: value["correspondence"].update(status="invalid"),
        ):
            supplied = deepcopy(retained)
            mutate(supplied)
            with self.subTest(supplied=supplied["execution"]["usage"]), self.exchange(), self.assertRaises(CoreProtocolError):
                self.client.replay(self.document, self.definitions, self.candidate, self.timeline, supplied)

    def test_native_rejection_timeout_crash_and_absence_never_fall_back(self):
        for status, error in (("error", CoreRejected), ("unsupported", CoreUnsupported)):
            with self.subTest(status=status), self.exchange(rejection=status), self.assertRaises(error):
                self.execute()
        for failure in (CoreTimeout("timeout"), CoreTransportError("crashed")):
            with self.subTest(failure=type(failure)), self.exchange(failure=failure), self.assertRaises(type(failure)):
                self.execute()
        client = OperationalPolicyClient(CoreClient(Path("/does/not/exist/biocompiler-core")))
        with patch("biocompiler.core_client._exchange", side_effect=AssertionError("no process may run")), self.assertRaises(CoreUnavailable):
            client.compile(self.document, self.definitions)


if __name__ == "__main__":
    unittest.main()
