"""Adversarial inert transport peers; these are not native semantic acceptance."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler.core_client import (
    CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL, CoreCancelled, CoreClient, CoreProtocolError,
    CoreRejected, CoreTimeout, CoreTransportError, CoreUnavailable, CoreUnsupported, encode_json,
)
from biocompiler import core_policy_implementation as api
from tests.test_core_policy import assessment, digest
from tests import test_core_policy_operational as source_peer

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    return json.loads((ROOT / "core/test/data/policy_implementation_binding_v01.json").read_text())["cases"][1]


def limits():
    return {"profile": api.RESOURCE_PROFILE,
            "source": {"max_ticks": 16, "max_inputs": 256, "max_encounters": 4, "max_attempts": 32,
                       "max_work": 100000, "max_trace_items": 2000, "max_microsteps": 32},
            "candidate": {"max_work": 1000000, "max_events": 100000, "max_attempts": 32, "max_microsteps": 32},
            "monitor": {"max_work": 100000, "max_obligations": 1000, "max_samples": 100000},
            "max_step_work": 1000000, "max_step_retained": 100000,
            "max_report_bytes": 8 * 1024 * 1024, "max_report_nodes": 1000000}


def candidate(request):
    literal = fixture()
    actual = deepcopy(literal["implementation"])
    actual["authority"] = {"source_artifact_digest": digest(request["document"]),
                           "descriptors_digest": digest(request["definitions"]),
                           "domain_digest": digest(request["operating_domain"]),
                           "implementation_catalog_digest": digest(request["document"]["implementations"]),
                           "library_digest": digest(request["implementation_library"])}
    return {"schema_version": api.CANDIDATE_SCHEMA,
            "behavior": source_peer.candidate(request["document"], request["definitions"]),
            "implementation": actual, "binding": deepcopy(literal["proposed"])}


def report(request, actual, bounds, *, status="checked_implementation"):
    source = assessment(request["document"])
    pins = []
    for bridge in request["catalog_bindings"]:
        for pin in bridge["models"]:
            if pin not in pins:
                pins.append(deepcopy(pin))
    identities = {"request_fingerprint": digest(request), "source_artifact_digest": digest(request["document"]),
                  "descriptors_digest": digest(request["definitions"]), "operating_domain_digest": digest(request["operating_domain"]),
                  "implementation_catalog_digest": digest(request["document"]["implementations"]),
                  "implementation_library_digest": digest(request["implementation_library"]),
                  "catalog_bindings_digest": digest(request["catalog_bindings"])}
    claims = {"target_status": "unassessed", "material": "unassessed", "artifact": "withheld", "export": "withheld"}
    admission = {"schema_version": "biocompiler.policy_realization_admission.v0.1", "profile": api.REQUEST_PROFILE,
                 "resource_profile": "biocompiler.policy_realization_inputs.resources.v0.1", "status": "admitted_inputs",
                 **identities, "document_digest": source["document_digest"], "source_assessment": source,
                 "source_correspondence": source_peer.report({"document": request["document"], "definitions": request["definitions"],
                                                              "candidate": actual["behavior"]})["correspondence"],
                 "requested_requirements": deepcopy(request["document"]["assurance"]["requirements"]),
                 "authorized_models": pins, "assurance": deepcopy(request["document"]["assurance"]),
                 "budgets": deepcopy(request["budgets"]), "exploration": "not_performed", "preservation": "unassessed",
                 "requirements": "unassessed", "unresolved_obligations": ["material_correspondence"], **claims}
    bridge = request["catalog_bindings"][0]
    binding = {"schema_version": "biocompiler.policy_implementation_binding_report.v0.1",
               "profile": "biocompiler.policy_exclusive_source_graph.v0.1",
               "observable_profile": "biocompiler.policy_truth_observables.v0.1", "status": "source_graph_bound",
               **identities, "catalog_entry": bridge["entry_id"], "catalog_entry_digest": bridge["entry_digest"],
               "implementation_fingerprint": digest(actual["implementation"]), "proposed_binding_fingerprint": digest(actual["binding"]),
               "source_admission": admission, "source_occurrences": deepcopy(actual["implementation"]["occurrences"]),
               "interpreted_outputs": [{"node": row["id"], "operation": "inert_transport_fixture", "outputs": []}
                                       for row in actual["implementation"]["nodes"]],
               "execution": "not_performed", "preservation": "unassessed", "requirements": "unassessed", **claims}
    complete = status != "incomplete"
    rows = [{"id": row["value"]["id"], "kind": row["value"]["kind"], "source": deepcopy(row["value"]),
             "status": "pass" if complete else "unknown", "nonvacuous": complete,
             "histories": {"pass": int(complete), "fail": 0, "unknown": 0, "not_exercised": 0, "unsupported": 0},
             "coverage": {"samples": 14 if complete else 0, "active": 4 if complete else 0,
                          "inactive": 10 if complete else 0, "enabled_triggers": 2 if complete else 0}, "witnesses": {}}
            for row in source["requirements"]]
    if status == "requirements_not_satisfied":
        rows[-1]["status"] = "unknown"
        rows[-1]["histories"]["pass"] = 0
        rows[-1]["histories"]["unknown"] = 1
    return {"schema_version": "biocompiler.policy_preservation_report.v0.1", "profile": api.PRESERVATION_PROFILE,
            "request_fingerprint": digest(request), "binding": binding, "limits": deepcopy(bounds),
            "coverage": {"complete": complete, "prefixes_started": 8 if complete else 1,
                         "matched_prefixes": 8 if complete else 1, "transitions": 7 if complete else 0,
                         "histories": int(complete), "traversal": "exhaustive_depth_first_no_merging", "digest": "a" * 64},
            "program_coverage": {"nonvacuous": complete, "created_attempts": 2 if complete else 0,
                                 "active_prefixes": 2 if complete else 0, "inactive_prefixes": 5 if complete else 0, "witnesses": {}},
            "usage": {"work": 1000, "source_work": 100, "candidate_work": 200, "monitor_work": 100, "peak_retained_trace_items": 100},
            "preservation": "pass" if complete else "unassessed", "requirements": rows,
            "assurance": "bounded_requirements_satisfied" if status == "checked_implementation" else "not_established", "status": status,
            "stopped": None if complete else {"category": "incomplete", "diagnostic": {"code": "policy_preservation_prefix_limit",
                             "message": "Explicit bound", "path": None}, "history": [], "source_execution": None, "candidate_frame": None}, **claims}


def result(payload, *, status="checked_implementation"):
    original = payload["request"]
    actual = deepcopy(payload.get("candidate") or candidate(original))
    checked = report(original, actual, payload["limits"], status=status)
    return {"schema_version": api.RESULT_SCHEMA, "implementation": api.IMPLEMENTATION,
            "resource_profile": api.RESOURCE_PROFILE, "validation_scope": api.VALIDATION_SCOPE,
            "request_fingerprint": digest(original), "candidate_fingerprint": digest(actual),
            "invocation_fingerprint": digest({"request": original, "candidate": actual, "limits": payload["limits"]}),
            "report_fingerprint": digest(checked), "candidate": actual, "report": checked}


def capabilities(role):
    profiles = {"policy_implementation": deepcopy(api.PROFILE)}
    operations = ["capabilities", *api.PROFILE["operations"]]
    if role == "core":
        profiles["policy_implementation_producer"] = deepcopy(api.PRODUCER_PROFILE)
        operations.append("compile-policy-implementation")
    return {"schema_version": CAPABILITIES_SCHEMA, "operations": operations,
            "intent_schemas": ["biocompiler.intent.v0.1"], "canonicalization": "python-json-v1",
            "validation_scopes": [api.VALIDATION_SCOPE], "profiles": profiles,
            "limits": dict(LIMITS), "claim_scope": "Bounded implementation only; no material/export authority."}


class PolicyImplementationTransportTests(unittest.TestCase):
    def test_negotiated_publication_limits_match_wire_reserves(self):
        self.assertEqual(api.MAX_RESULT_BYTES, LIMITS["max_response_bytes"] - 6 * LIMITS["max_string_bytes"] - 65536)
        self.assertEqual(api.MAX_RESULT_NODES, LIMITS["max_json_nodes"] - 32)

    def setUp(self):
        self.request = fixture()["request"]
        self.candidate = candidate(self.request)
        self.limits = limits()
        self.calls = []
        self.client = api.PolicyImplementationClient(CoreClient(Path(sys.executable)))

    def exchange(self, *, mutate=None, mutate_capabilities=None, on_negotiate=None, status="checked_implementation",
                 role="core", rejection=None, failure=None):
        def call(_binary, encoded, _timeout, _cancelled):
            request = json.loads(encoded)
            self.calls.append(request)
            operation = request["operation"]
            if operation == "capabilities":
                value = capabilities(role)
                if mutate_capabilities:
                    mutate_capabilities(value)
                if on_negotiate:
                    on_negotiate()
            else:
                if failure:
                    raise failure
                value = result(request["payload"], status=status)
                if mutate:
                    mutate(value)
            native_status = rejection if operation != "capabilities" and rejection else "ok"
            response = {"protocol": PROTOCOL, "request_id": request["request_id"], "operation": operation,
                        "status": native_status, "result": value if native_status == "ok" else None,
                        "diagnostics": [] if native_status == "ok" else [{"code": "implementation_rejected", "message": "Rejected", "path": "/request"}],
                        "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": role}}
            return encode_json(response), {"ok": 0, "error": 2, "unsupported": 3}[native_status]
        return patch("biocompiler.core_client._exchange", side_effect=call)

    def check(self):
        return self.client.check(self.request, self.candidate, self.limits)

    def test_compile_check_and_full_wrapper_replay_share_exact_check_invocation(self):
        with self.exchange():
            compiled = self.client.compile(self.request, self.limits)
            checked = self.client.check(self.request, compiled.candidate, self.limits)
            replayed = self.client.replay(self.request, compiled.candidate, self.limits, checked.result)
        self.assertEqual(compiled.result, checked.result)
        self.assertEqual(checked.result, replayed.result)
        self.assertNotEqual(checked.request_fingerprint, checked.invocation_fingerprint)
        self.assertEqual(checked.request_fingerprint, digest(self.request))
        self.assertEqual([call["operation"] for call in self.calls][::2], ["capabilities"] * 3)

    def test_incomplete_and_unsatisfied_native_results_are_visible_without_acceptance(self):
        for status in ("incomplete", "requirements_not_satisfied"):
            with self.subTest(status=status), self.exchange(status=status):
                actual = self.check()
            self.assertEqual(actual.status, status)
            self.assertEqual(actual.report["assurance"], "not_established")
            self.assertEqual(actual.report["export"], "withheld")

    def test_missing_wrong_and_overclaimed_profiles_fail_before_operation(self):
        for mutate in (
            lambda value: value["profiles"].pop("policy_implementation"),
            lambda value: value["profiles"]["policy_implementation"].update(artifact="produced"),
            lambda value: value["profiles"]["policy_implementation"].update(max_result_nodes=True),
            lambda value: value["validation_scopes"].clear(),
        ):
            self.calls.clear()
            with self.subTest(mutate=mutate), self.exchange(mutate_capabilities=mutate), self.assertRaises(CoreProtocolError):
                self.check()
            self.assertEqual(len(self.calls), 1)
        with self.exchange(mutate_capabilities=lambda value: value["profiles"].pop("policy_implementation_producer")), self.assertRaises(CoreProtocolError):
            self.client.compile(self.request, self.limits)

    def test_verify_never_produces_but_checks_and_replays(self):
        verify = api.PolicyImplementationClient(CoreClient(Path(sys.executable), role="verify"))
        with patch("subprocess.Popen", side_effect=AssertionError("Producer must not start")), self.assertRaises(CoreProtocolError):
            verify.compile(self.request, self.limits)
        with self.exchange(role="verify"):
            checked = verify.check(self.request, self.candidate, self.limits)
            self.assertEqual(verify.replay(self.request, self.candidate, self.limits, checked.result).result, checked.result)

    def test_nested_snapshots_are_immutable_and_input_is_frozen_before_negotiation(self):
        original = deepcopy(self.request)
        with self.exchange(on_negotiate=lambda: self.request["budgets"].update(max_work=1)):
            checked = self.check()
        self.assertEqual(self.calls[-1]["payload"]["request"], original)
        snapshot = checked.result
        snapshot["report"]["status"] = "forged"
        checked.candidate["behavior"]["nodes"].clear()
        self.assertEqual(checked.status, "checked_implementation")
        self.assertTrue(checked.candidate["behavior"]["nodes"])
        with self.assertRaises(FrozenInstanceError):
            checked.request_fingerprint = "forged"

    def test_changed_rehashed_identity_ledgers_statuses_and_claims_are_rejected(self):
        mutations = (
            lambda v: v.update(implementation="foreign"),
            lambda v: v.update(request_fingerprint="0" * 64),
            lambda v: v.update(invocation_fingerprint="0" * 64),
            lambda v: v["candidate"]["behavior"]["source_document"]["program"]["source_map"][0].update(file="changed.py"),
            lambda v: v["report"].update(material="produced"),
            lambda v: v["report"]["requirements"].pop(),
            lambda v: v["report"]["requirements"].reverse(),
            lambda v: v["report"]["requirements"][0]["source"].update(description="changed"),
            lambda v: v["report"]["requirements"][0]["histories"].update(unknown=1),
            lambda v: v["report"]["coverage"].update(complete=1),
            lambda v: v["report"]["coverage"].update(histories=True),
            lambda v: v["report"]["program_coverage"].update(created_attempts=0),
            lambda v: v["report"]["usage"].update(work=True),
            lambda v: v["report"]["limits"]["source"].update(max_work=1),
            lambda v: v["report"]["binding"]["source_admission"]["authorized_models"].clear(),
            lambda v: v["report"]["binding"]["source_admission"]["assurance"]["requirements"].clear(),
            lambda v: v["report"]["binding"]["source_occurrences"].pop(),
            lambda v: v["report"]["binding"]["interpreted_outputs"].pop(),
            lambda v: v["report"]["binding"].update(catalog_entry_digest="0" * 64),
        )
        for mutation in mutations:
            def altered(value):
                mutation(value)
                value["candidate_fingerprint"] = digest(value["candidate"])
                value["report_fingerprint"] = digest(value["report"])
            with self.subTest(mutation=mutation), self.exchange(mutate=altered), self.assertRaises(CoreProtocolError):
                self.check()

    def test_replay_validates_entire_retained_wrapper_even_with_rehashed_inner_report(self):
        saved = result({"request": self.request, "candidate": self.candidate, "limits": self.limits})
        for retained in (saved["report"], {**saved, "implementation": "foreign"},
                         {**saved, "invocation_fingerprint": "0" * 64}, {**saved, "extra": "forged"}):
            with self.subTest(retained=retained.keys()), self.exchange(), self.assertRaises(CoreProtocolError):
                self.client.replay(self.request, self.candidate, self.limits, retained)
        forged = deepcopy(saved)
        forged["report"]["coverage"]["complete"] = 1
        forged["report_fingerprint"] = digest(forged["report"])
        with self.exchange(), self.assertRaises(CoreProtocolError):
            self.client.replay(self.request, self.candidate, self.limits, forged)

    def test_timeout_crash_cancel_rejection_and_unavailable_have_no_fallback(self):
        for error in (CoreTimeout("timeout"), CoreTransportError("crash"), CoreCancelled("cancelled")):
            with self.subTest(error=type(error)), self.exchange(failure=error), self.assertRaises(type(error)), patch(
                "biocompiler.policy.validation.check", side_effect=AssertionError("Python semantic fallback")
            ):
                self.check()
        for status, error in (("error", CoreRejected), ("unsupported", CoreUnsupported)):
            with self.exchange(rejection=status), self.assertRaises(error):
                self.check()
        unavailable = api.PolicyImplementationClient(CoreClient(ROOT / "absent-policy-native"))
        with self.assertRaises(CoreUnavailable):
            unavailable.compile(self.request, self.limits)

    def test_publication_checks_complete_nodes_and_bytes(self):
        with self.exchange(), patch.object(api, "MAX_RESULT_NODES", 100), self.assertRaises(CoreProtocolError):
            self.check()
        with self.exchange(), patch.object(api, "MAX_RESULT_BYTES", 100), self.assertRaises(CoreProtocolError):
            self.check()

    def test_input_accepts_only_literal_json_and_complete_source_authority(self):
        for value in (lambda: self.request, object(), {**self.request, "document": self.request["document"]["program"]}):
            with patch("subprocess.Popen", side_effect=AssertionError("No generated code execution")), self.assertRaises(CoreProtocolError):
                self.client.compile(value, self.limits)


if __name__ == "__main__":
    unittest.main()
