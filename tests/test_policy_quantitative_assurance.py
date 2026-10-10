"""Inert authority/transport mutations; these tests do not execute native proofs."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler import core_policy_quantitative_assurance as api
from biocompiler.core_client import CoreClient, CoreProtocolError, CoreResponse, CORE_VERSION, PROTOCOL, encode_json
from tests import test_core_policy_component_material as peer
from tests import test_policy_refinement as refinement

digest = peer.digest


def request(original):
    return {"schema_version": api.REQUEST_SCHEMA, "profile": api.REQUEST_PROFILE, "material_request": deepcopy(original),
            "approximation": None, "realization_evidence": None, "max_work": api.MAX_WORK}


def result(payload, *, accepted=True, export=False):
    authority = payload["request"]
    original = authority["material_request"]
    child = peer.result({"request": original, "candidate": payload.get("candidate"), "limits": payload["limits"]},
                        accepted=accepted, export=export)
    candidate, material = child["candidate"], child["report"]
    invocation = {"request": authority, "candidate": candidate, "limits": payload["limits"]}
    report = {"schema_version": api.REPORT_SCHEMA, "request_fingerprint": digest(authority),
        "candidate_fingerprint": digest(candidate), "invocation_fingerprint": digest(invocation), "material": material,
        "exact_refinement": refinement.evidence(original, candidate, material, payload["limits"]) if accepted else None,
        "approximation": None, "realization_evidence": None, "export_permitted": accepted, "empirical_function": "unassessed"}
    artifact = None
    if export:
        old = child["artifact"]
        manifest = {"schema_version": "biocompiler.policy_quantitative_assurance_manifest.v0.1", "request": authority,
            "limits": payload["limits"], "assessment": report, "assessment_fingerprint": digest(report),
            "material_manifest": old["manifest"], "material_manifest_sha256": old["manifest_sha256"],
            "fasta_sha256": old["fasta_sha256"],
            "claim_scope": "exact_material_and_scoped_mathematical_assurance_with_separate_supplied_evidence",
            "empirical_function": "unassessed", "original_authority": "retain_original_inputs_separately"}
        artifact = {"schema_version": "biocompiler.policy_quantitative_assurance_export.v0.1", "fasta": old["fasta"],
            "fasta_sha256": old["fasta_sha256"], "manifest": manifest, "manifest_sha256": digest(manifest)}
    return {"schema_version": api.RESULT_SCHEMA, "implementation": api.IMPLEMENTATION, "validation_scope": api.VALIDATION_SCOPE,
        "request_fingerprint": digest(authority), "candidate_fingerprint": digest(candidate), "invocation_fingerprint": digest(invocation),
        "report_fingerprint": digest(report), "candidate": candidate, "report": report, "artifact": artifact}


class QuantitativeAssuranceTests(unittest.TestCase):
    def setUp(self):
        self.legacy = peer.old.PolicyMaterialTransportTests()
        self.addCleanup(self.legacy.doCleanups)
        self.legacy.setUp()
        self.request = request(peer.original())
        self.candidate = peer.candidate(self.request["material_request"])
        self.limits = peer.old.fixture()["limits"]
        self.client = api.PolicyQuantitativeAssuranceClient(CoreClient(Path(sys.executable)))

    def payload(self):
        return {"request": self.request, "candidate": self.candidate, "limits": self.limits}

    def validate(self, value, operation="check-policy-quantitative-assurance", payload=None):
        return api._result(CoreResponse("assurance-test", operation, "ok", value, (), "verify", CORE_VERSION), payload or self.payload())

    def test_exact_material_and_named_relations_remain_unchanged(self):
        value = result(self.payload())
        response = self.validate(value)
        self.assertTrue(response.export_permitted)
        self.assertEqual(value["report"]["material"], peer.report(self.request["material_request"], self.candidate, self.limits))
        self.assertEqual(len(value["report"]["exact_refinement"]["claims"]), 10)
        snapshot = response.report
        snapshot["export_permitted"] = False
        self.assertTrue(response.export_permitted)
        with self.assertRaises(FrozenInstanceError):
            response.operation = "export-policy-quantitative-assurance"

    def test_fresh_replay_requires_complete_saved_equality(self):
        value = result(self.payload())
        payload = self.payload() | {"report": deepcopy(value)}
        self.validate(value, "replay-policy-quantitative-assurance", payload)
        payload["report"]["artifact"] = {}
        with self.assertRaisesRegex(CoreProtocolError, "replay"):
            self.validate(value, "replay-policy-quantitative-assurance", payload)

    def test_withheld_material_cannot_acquire_optional_evidence(self):
        value = result(self.payload(), accepted=False)
        self.assertFalse(self.validate(value).export_permitted)
        value["report"]["approximation"] = {"outcome": "pass"}
        value["report_fingerprint"] = digest(value["report"])
        with self.assertRaises(CoreProtocolError):
            self.validate(value)

    def test_rehashed_mutations_cannot_promote_or_replace_authority(self):
        mutations = [lambda r: r.update(empirical_function="demonstrated"),
            lambda r: r.update(export_permitted=False), lambda r: r.update(exact_refinement=None),
            lambda r: r["material"].update(request_fingerprint="0" * 64),
            lambda r: r.update(approximation={"outcome": "pass"}),
            lambda r: r.update(realization_evidence={"status": "supported"})]
        for mutate in mutations:
            value = result(self.payload())
            mutate(value["report"])
            value["report_fingerprint"] = digest(value["report"])
            with self.subTest(mutate=mutate), self.assertRaises(CoreProtocolError):
                self.validate(value)

    def test_export_binds_unchanged_rna_and_complete_assurance(self):
        value = result(self.payload(), export=True)
        self.validate(value, "export-policy-quantitative-assurance")
        self.assertEqual(value["artifact"]["manifest"]["material_manifest"]["assessment"], value["report"]["material"])
        for mutate in (lambda v: v.update(fasta="AAAA"),
                       lambda v: v["manifest"]["request"].update(max_work=1),
                       lambda v: v["manifest"]["material_manifest"].update(empirical="demonstrated")):
            altered = deepcopy(value)
            mutate(altered["artifact"])
            altered["artifact"]["manifest_sha256"] = digest(altered["artifact"]["manifest"])
            with self.subTest(mutate=mutate), self.assertRaises(CoreProtocolError):
                self.validate(altered, "export-policy-quantitative-assurance")

    def test_check_cannot_publish_export_even_with_valid_bases(self):
        with self.assertRaises(CoreProtocolError):
            self.validate(result(self.payload(), export=True))

    def test_request_limits_and_closed_envelope_reject(self):
        for field, value in (("max_work", 0), ("max_work", True), ("max_work", api.MAX_WORK + 1),
                             ("schema_version", "unknown"), ("approximation", {})):
            with self.subTest(field=field, value=value), self.assertRaises(CoreProtocolError):
                api._request(self.request | {field: value})
        with self.assertRaises(CoreProtocolError):
            api._request(self.request | {"saved_pass": True})

    def test_transport_negotiates_and_retains_full_originals(self):
        calls = []
        def exchange(_binary, encoded, _timeout, _cancelled):
            invocation = json.loads(encoded)
            calls.append(invocation)
            if invocation["operation"] == "capabilities":
                value = peer.capabilities("core")
                value.update(operations=["capabilities", *api.PROFILE["operations"], "compile-policy-quantitative-assurance"],
                    profiles={"policy_quantitative_assurance": deepcopy(api.PROFILE),
                              "policy_quantitative_assurance_producer": deepcopy(api.PRODUCER_PROFILE)},
                    validation_scopes=[api.VALIDATION_SCOPE])
            else:
                value = result(invocation["payload"])
            return encode_json({"protocol": PROTOCOL, "request_id": invocation["request_id"], "operation": invocation["operation"],
                "status": "ok", "result": value, "diagnostics": [],
                "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": "core"}}), 0
        with patch("biocompiler.core_client._exchange", side_effect=exchange):
            compiled = self.client.compile(self.request, self.limits)
            checked = self.client.check(self.request, compiled.candidate, self.limits)
        self.assertTrue(checked.export_permitted)
        self.assertEqual(calls[-1]["payload"]["request"], self.request)


if __name__ == "__main__":
    unittest.main()
