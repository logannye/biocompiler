"""Strict realization transport contracts; all exchanges are Python test doubles."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler.core_client import (
    CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL, CoreCancelled, CoreClient,
    CoreProtocolError, CoreRejected, CoreUnsupported, encode_json,
)
from biocompiler.core_realization import (
    OPERATIONS, PROFILES, VALIDATION_SCOPES, RealizationClient, effective_resources, encode_report,
)


def family_for(operation):
    return next(key for key, value in PROFILES.items() if operation in value["operations"])


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def capabilities():
    return {"schema_version": CAPABILITIES_SCHEMA, "operations": ["capabilities", *OPERATIONS],
            "intent_schemas": ["biocompiler.intent.v0.1"], "canonicalization": "python-json-v1",
            "validation_scopes": list(VALIDATION_SCOPES), "profiles": deepcopy(PROFILES),
            "limits": dict(LIMITS), "claim_scope": "Supplied declarations only."}


def fixture():
    from test_synthetic_generation import fixture as authored, exercised_history
    from biocompiler.synthesis.synthetic import generate_synthetic, check_synthetic_candidate
    from biocompiler.synthesis.components import adapt_synthetic_components
    from biocompiler.compiler.components import check_component_behavior, check_component_assembly
    from biocompiler.verification.realization import check_realization, realization_dependencies
    request, sample = authored()
    history = exercised_history(sample)
    candidate = generate_synthetic(request)
    from biocompiler.ir.component_assembly import ComponentAssembly
    adapted = adapt_synthetic_components(request, candidate, history, until=7)
    assembly = ComponentAssembly(adapted.registry, adapted.composition, request.fingerprint, candidate.fingerprint,
                                 candidate.source_map, candidate.observation_map)
    direct = dict(behavior=request.behavior, contract=request.contract, domain=request.domain, target=request.target,
                  mechanism=candidate.mechanism, observation_map=candidate.observation_map)
    reports = {
        "realization-dependencies": realization_dependencies(**direct, history=history, until=7),
        "realization": check_realization(**direct, history=history, until=7),
        "synthetic_candidate": check_synthetic_candidate(request, candidate, history, until=7),
        "component_behavior": check_component_behavior(request, assembly, history, until=7),
        "component_assembly": check_component_assembly(request, candidate, assembly, history, until=7),
    }
    docs = {key: json.loads(value.to_json(indent=None)) for key, value in direct.items()}
    docs.update(expected_request=request.to_dict(), candidate=candidate.to_dict(), assembly=assembly.to_dict(),
                history=[frame.to_dict() for frame in history], until=7)
    docs = json.loads(canonical(docs))
    deps = reports["realization-dependencies"].to_dict()
    direct_ids = {key: deps[value] for key, value in {
        "behavior_fingerprint": "behavior", "behavior_artifact_ascii_fingerprint": "behavior_artifact",
        "contract_fingerprint": "contract", "domain_fingerprint": "domain", "target_fingerprint": "target",
        "mechanism_fingerprint": "mechanism", "observation_map_fingerprint": "observation_map", "history_ascii_fingerprint": "history"}.items()}
    ids = {**direct_ids, "request_fingerprint": request.fingerprint, "request_artifact_fingerprint": sha(docs["expected_request"]),
           "candidate_fingerprint": candidate.fingerprint, "assembly_fingerprint": assembly.fingerprint}
    return request, candidate, assembly, history, docs, reports, ids


def payload_for(operation, docs, reports):
    profile = PROFILES[family_for(operation)]
    payload = {key: deepcopy(docs[key]) for key in profile["payload_fields"][operation] if key not in ("profile", "limits", "assessment")}
    payload.update(profile=profile["profile"], limits=None)
    if operation.startswith("replay-"):
        payload["assessment"] = reports[family_for(operation)].to_dict()
    return payload


def result_for(operation, payload, reports, identities):
    family = family_for(operation); profile = PROFILES[family]
    dependency = operation == "realization-dependencies"
    label = "dependencies" if dependency else "assessment"
    report = deepcopy(reports[operation if dependency else family].to_dict())
    # Independent Python historical fingerprint; no client hash helper involved.
    fingerprint = reports[operation if dependency else family].fingerprint
    return {"schema_version": profile["result_schemas"][operation], "profile": profile["profile"],
            "implementation": profile["implementation"], "service_implementation": profile["service_implementation"],
            "resource_profile": profile["resources"]["protocol"]["profile"],
            "resources": effective_resources(profile, payload["limits"]),
            "validation_scope": profile["dependency_validation_scope" if dependency else "validation_scope"],
            "claim_scope": profile["dependency_claim_scope" if dependency else "claim_scope"],
            "supplied_authority_fingerprint": sha({key: value for key, value in payload.items() if key != "assessment"}),
            "authority_identities": {key: identities[key] for key in profile["authority_identity_fields"]},
            label: report, label + "_fingerprint": fingerprint}


class RealizationTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = fixture()

    def setUp(self):
        self.request, self.candidate, self.assembly, self.history, self.docs, self.reports, self.ids = self.fixture
        self.docs = deepcopy(self.docs)
        self.core = CoreClient(Path(sys.executable), role="verify")
        self.client = RealizationClient(self.core)
        self.calls = []

    def exchange(self, transform=None, capability_transform=None, rejection=None, on_negotiate=None):
        def invoke(_executable, encoded, _timeout, _cancelled):
            request = json.loads(encoded); self.calls.append(request); operation = request["operation"]
            if operation == "capabilities":
                value = capabilities()
                if capability_transform: capability_transform(value)
                if on_negotiate: on_negotiate()
            else:
                value = result_for(operation, request["payload"], self.reports, self.ids)
                if transform: transform(value)
            status = rejection if operation != "capabilities" and rejection else "ok"
            response = {"protocol": PROTOCOL, "request_id": request["request_id"], "operation": operation,
                        "status": status, "result": value if status == "ok" else None,
                        "diagnostics": [] if status == "ok" else [{"code": "realization_work_limit", "message": "Exhausted", "path": None}],
                        "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": "verify"}}
            return encode_json(response, limit=LIMITS["max_response_bytes"]), {"ok": 0, "error": 2, "unsupported": 3}[status]
        return patch("biocompiler.core_client._exchange", side_effect=invoke)

    def call(self, operation="verify-realization", **options):
        return self.client.call(operation, payload_for(operation, self.docs, self.reports), **options)

    def test_all_nine_operations_preserve_complete_independent_historical_results(self):
        for operation in OPERATIONS:
            with self.subTest(operation=operation), self.exchange():
                result = self.call(operation)
            original = self.reports[operation if operation == "realization-dependencies" else family_for(operation)]
            self.assertEqual(result.report, original.to_dict())
            self.assertEqual(result.report_fingerprint, original.fingerprint)
            result.report.clear(); result.envelope.clear(); result.authority_identities.clear()
            self.assertEqual(result.report, original.to_dict())
            if operation == "realization-dependencies":
                self.assertIsNone(result.outcome)
                self.assertIsNone(result.assessment_fingerprint)
                with self.assertRaises(CoreProtocolError): _ = result.assessment
            else:
                self.assertEqual(result.outcome, original.outcome.value)
        self.assertEqual([call["operation"] for call in self.calls], [item for op in OPERATIONS for item in ("capabilities", op)])

    def test_capability_profiles_are_exact_pinned_installed_contract(self):
        path = Path(__file__).resolve().parents[1] / "docs/migration-realization-protocol-profiles.json"
        self.assertEqual(PROFILES, json.loads(path.read_text())["capability_profiles"])
        self.assertEqual(len(OPERATIONS), 9)
        changes = [lambda c: c["profiles"]["realization"]["default_limits"].update(max_work=50_000_000.0),
                   lambda c: c["profiles"]["component_behavior"]["resources"]["checker"].pop("composition"),
                   lambda c: c["profiles"]["synthetic_candidate"]["semantic_versions"].update(synthetic_acceptance="stale"),
                   lambda c: c["operations"].remove("replay-component-assembly"),
                   lambda c: c["validation_scopes"].remove(VALIDATION_SCOPES[0])]
        for change in changes:
            self.calls.clear()
            with self.exchange(capability_transform=change), self.assertRaises(CoreProtocolError): self.call()
            self.assertEqual(len(self.calls), 1)

    def test_payload_and_replay_report_are_frozen_before_negotiation(self):
        payload = payload_for("replay-realization", self.docs, self.reports)
        original = deepcopy(payload)
        def mutate():
            payload["history"].clear(); payload["assessment"]["coverage"].clear(); payload["until"] = 9
        with self.exchange(on_negotiate=mutate):
            result = self.client.call("replay-realization", payload)
        self.assertEqual(self.calls[1]["payload"], original)
        self.assertEqual(result.supplied_authority_fingerprint, sha({k: v for k, v in original.items() if k != "assessment"}))

    def test_limits_are_exact_positive_reductions_and_nested_resources_are_bound(self):
        defaults = PROFILES["realization"]["default_limits"]
        for limits in ({}, {**defaults, "max_work": True}, {**defaults, "max_work": 0}, {**defaults, "max_work": 1.0},
                       {**defaults, "max_work": defaults["max_work"] + 1}, {**defaults, "extra": 1}):
            self.calls.clear(); payload = payload_for("verify-realization", self.docs, self.reports); payload["limits"] = limits
            with self.exchange(), self.assertRaises(CoreProtocolError): self.client.call("verify-realization", payload)
            self.assertEqual(self.calls, [])
        reduced = {key: value - 1 for key, value in defaults.items()}
        for operation in OPERATIONS:
            payload = payload_for(operation, self.docs, self.reports); payload["limits"] = reduced
            with self.exchange(): result = self.client.call(operation, payload)
            resources = result.envelope["resources"]
            self.assertEqual(resources["protocol"]["max_work"], reduced["max_work"])
        with self.exchange(transform=lambda r: r["resources"]["checker"].update(max_work=1)), self.assertRaises(CoreProtocolError):
            self.call()

    def test_response_rejects_changed_authority_claims_policy_and_replay_details(self):
        changes = [lambda r: r.update(profile="other"), lambda r: r.update(service_implementation="python"),
                   lambda r: r.update(claim_scope="empirically verified"), lambda r: r.update(extra=True),
                   lambda r: r.update(supplied_authority_fingerprint="0" * 64),
                   lambda r: r.update(assessment_fingerprint="0" * 64),
                   lambda r: r["authority_identities"].update(history_ascii_fingerprint="0" * 64),
                   lambda r: r["assessment"].update(evidence_kind="empirical"),
                   lambda r: r["assessment"]["dependencies"].update(checker="stale"),
                   lambda r: r["assessment"]["dependencies"]["horizon"].update(until=0),
                   lambda r: r["assessment"].update(coverage=[]),
                   lambda r: r["resources"]["protocol"].update(max_request_nodes=True)]
        for change in changes:
            with self.subTest(change=changes.index(change)), self.exchange(transform=change), self.assertRaises(CoreProtocolError): self.call()
        payload = payload_for("replay-realization", self.docs, self.reports)
        payload["assessment"]["coverage"][0]["activation_deadlines_checked"] += 1
        with self.exchange(), self.assertRaisesRegex(CoreProtocolError, "historical report"):
            self.client.call("replay-realization", payload)

    def test_report_encoding_preserves_unicode_numeric_and_ascii_family_distinctions(self):
        value = {"é": [1, 1.0, -0.0, "🧬"]}
        ascii_bytes = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
        self.assertEqual(encode_report(value, "python-json-ascii-v1"), ascii_bytes)
        self.assertEqual(encode_report(value, "python-json-v1"), canonical(value))
        self.assertNotEqual(ascii_bytes, canonical(value))
        for number in (1, 1.0, -0.0, 0):
            self.assertIn(str(number).encode(), encode_report([number], "python-json-ascii-v1"))
        with self.assertRaises(CoreProtocolError): encode_report(value, "unknown")

    def test_nominal_payload_and_nonfinite_numbers_fail_before_io(self):
        for mutation in (lambda p: p.update(until=True), lambda p: p.update(until=float("nan")),
                         lambda p: p.update(history={}), lambda p: p.pop("profile"), lambda p: p.update(extra=None)):
            self.calls.clear(); payload = payload_for("verify-realization", self.docs, self.reports); mutation(payload)
            with self.exchange(), self.assertRaises(CoreProtocolError): self.client.call("verify-realization", payload)
            self.assertEqual(self.calls, [])

    def test_rejection_cancellation_and_unsupported_never_retry(self):
        for status, error in (("error", CoreRejected), ("unsupported", CoreUnsupported)):
            self.calls.clear()
            with self.exchange(rejection=status), self.assertRaises(error): self.call()
            self.assertEqual(len(self.calls), 2)
        callback = lambda: True
        with patch("biocompiler.core_client._exchange", side_effect=CoreCancelled("cancelled")) as exchange:
            with self.assertRaises(CoreCancelled): self.call(cancelled=callback)
        self.assertIs(exchange.call_args.args[3], callback)
        self.assertEqual(exchange.call_count, 1)
