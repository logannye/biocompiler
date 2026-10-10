"""Inert protocol peers for descriptive named evidence, never native proof tests."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler import core_policy_refinement as api
from biocompiler import policy
from biocompiler.core_client import CoreClient, CoreProtocolError, CORE_VERSION, PROTOCOL, encode_json
from tests import test_core_policy_component_material as peer

digest = peer.digest


def evidence(request, candidate, report, limits):
    """Independent literal wire fixture; child hashes deliberately grant no proof."""
    original = request["implementation_request"]
    source, behavior, graph, content, context = (
        {"stage": stage, "fingerprint": digest(value)} for stage, value in (
            ("source_document", original["document"]), ("operational_behavior", candidate["behavior"]),
            ("implementation_graph", candidate["implementation"]), ("construction_content", candidate["construction"]),
            ("deployment_context", request["context"])))
    base = {"implementation_request_fingerprint": digest(original), "operating_domain_fingerprint": digest(original["operating_domain"]),
            "limits_fingerprint": None, "material_request_fingerprint": None}
    bounded = base | {"limits_fingerprint": digest(limits)}
    material = bounded | {"material_request_fingerprint": digest(request)}
    claims = [{"relation": relation, "source": deepcopy(left), "target": deepcopy(right), "scope": deepcopy(scope)}
              for relation, left, right, scope in (
        ("exact_source_occurrence", source, behavior, base), ("source_graph_binding", behavior, graph, base),
        ("bounded_observable_correspondence", behavior, graph, bounded), ("original_hard_requirements", behavior, graph, bounded),
        ("supplied_component_material_correspondence", graph, content, bounded), ("conditional_deployment_context", content, context, material),
        ("complete_original_obligations", source, content, material), ("exact_source_graph_correspondence", source, graph, base),
        ("bounded_source_observable_correspondence", source, graph, bounded), ("conditional_source_material_correspondence", source, content, material))]
    preservation = report["preservation"]
    binding = preservation["binding"]
    premises = [{"kind": kind, "fingerprint": digest(value)} for kind, value in (
        ("original_source", original["document"]), ("semantic_definitions", original["definitions"]),
        ("operating_domain", original["operating_domain"]), ("implementation_catalog", original["document"]["implementations"]),
        ("implementation_models", original["implementation_library"]), ("checker_limits", limits),
        ("component_library", request["component_library"]), ("composition_rule", request["composition_rule"]),
        ("material_authority", request["composition_rule"]["body"]["material_authority"]), ("deployment_context", request["context"]),
        ("material_request", request), ("source_admission", binding["source_admission"]), ("implementation_binding", binding),
        ("bounded_preservation", preservation), ("component_assembly", report["assembly"]),
        ("mrna_structure", report["assembly"]["structure"]), ("component_context", report["context"]), ("complete_material_check", report))]
    return {"schema_version": api.EVIDENCE_SCHEMA, "claims": claims, "premises": premises,
            "derivation": {"rule": "conjunction", "inputs": ["a" * 64, "b" * 64]}}


def result(payload, accepted=True):
    request, actual, limits = (payload[key] for key in ("request", "candidate", "limits"))
    report = peer.report(request, actual, limits, accepted=accepted)
    return {"schema_version": api.RESULT_SCHEMA, "implementation": api.IMPLEMENTATION, "validation_scope": api.VALIDATION_SCOPE,
        "request_fingerprint": digest(request), "candidate_fingerprint": digest(actual),
        "invocation_fingerprint": digest({"request": request, "candidate": actual, "limits": limits}),
        "material_report_fingerprint": digest(report), "material_report": report,
        "evidence": evidence(request, actual, report, limits) if accepted else None}


class PolicyRefinementTests(unittest.TestCase):
    def setUp(self):
        self.legacy = peer.old.PolicyMaterialTransportTests()
        self.addCleanup(self.legacy.doCleanups)
        self.legacy.setUp()
        self.request = peer.original()
        self.candidate = peer.candidate(self.request)
        self.limits = peer.old.fixture()["limits"]
        self.client = api.PolicyRefinementClient(CoreClient(Path(sys.executable)))
        self.calls = []

    def exchange(self, *, mutate=None, negotiate=None, role="core", accepted=True):
        def call(_binary, encoded, _timeout, _cancelled):
            invocation = json.loads(encoded)
            self.calls.append(invocation)
            if invocation["operation"] == "capabilities":
                value = peer.capabilities(role)
                value.update(operations=["capabilities", *api.PROFILE["operations"]],
                             profiles={"policy_refinement": deepcopy(api.PROFILE)}, validation_scopes=[api.VALIDATION_SCOPE])
                if negotiate:
                    negotiate(value)
            else:
                value = result(invocation["payload"], accepted)
                if mutate:
                    mutate(value)
            return encode_json({"protocol": PROTOCOL, "request_id": invocation["request_id"], "operation": invocation["operation"],
                "status": "ok", "result": value, "diagnostics": [],
                "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": role}}), 0
        return patch("biocompiler.core_client._exchange", side_effect=call)

    def check(self):
        return self.client.check(self.request, self.candidate, self.limits)

    def test_fresh_check_and_replay_preserve_complete_inputs_and_material_report(self):
        with self.exchange():
            checked = self.check()
            replayed = self.client.replay(self.request, self.candidate, self.limits, checked.result)
        self.assertEqual(checked.result, replayed.result)
        self.assertEqual(checked.material_status, "checked_component_material")
        self.assertEqual(checked.material_report, peer.report(self.request, self.candidate, self.limits))
        self.assertEqual(checked.request_fingerprint, digest(self.request))
        self.assertEqual(checked.candidate_fingerprint, digest(self.candidate))
        self.assertEqual(checked.material_report_fingerprint, digest(checked.material_report))
        self.assertEqual(self.calls[1]["payload"], {"request": self.request, "candidate": self.candidate, "limits": self.limits})
        self.assertEqual(self.calls[-1]["payload"]["report"], checked.result)
        self.assertEqual([call["operation"] for call in self.calls][1::2], ["check-policy-refinement", "replay-policy-refinement"])

    def test_immutable_typed_views_roundtrip_and_snapshots_are_independent(self):
        with self.exchange():
            checked = self.check()
        named = checked.evidence
        self.assertIsInstance(named, api.RefinementEvidence)
        self.assertEqual(named.to_data(), checked.result["evidence"])
        self.assertEqual(len(named.claims), 10)
        self.assertEqual(len(named.premises), 18)
        self.assertEqual(named.claims[0].source, api.StageIdentity("source_document", digest(self.request["implementation_request"]["document"])))
        for value, field, replacement in ((checked, "request_fingerprint", "0" * 64), (named, "claims", ()),
                (named.claims[0], "relation", "source_graph_binding"), (named.claims[0].scope, "limits_fingerprint", "0" * 64),
                (named.claims[0].source, "stage", "construction_content"), (named.premises[0], "kind", "checker_limits"),
                (named.derivation, "inputs", ())):
            with self.subTest(field=field), self.assertRaises(FrozenInstanceError):
                setattr(value, field, replacement)
        checked.result["evidence"]["claims"].clear()
        checked.material_report.clear()
        named.to_data()["premises"].clear()
        self.assertEqual(len(checked.evidence.claims), 10)
        self.assertEqual(len(checked.result["evidence"]["premises"]), 18)

    def test_rejection_retains_full_report_and_has_no_named_evidence(self):
        with self.exchange(accepted=False):
            checked = self.check()
            replayed = self.client.replay(self.request, self.candidate, self.limits, checked.result)
        self.assertIsNone(checked.evidence)
        self.assertEqual(checked.material_status, "not_accepted")
        self.assertEqual(checked.material_report, peer.report(self.request, self.candidate, self.limits, accepted=False))
        self.assertEqual(replayed.result, checked.result)

    def test_namespace_verify_routes_are_fresh_and_have_no_fallback_or_export(self):
        client = api.PolicyRefinementClient(CoreClient(Path(sys.executable), role="verify"))
        cancelled = lambda: False
        with self.exchange(role="verify"), patch("biocompiler.policy.validation.check", side_effect=AssertionError("No semantic fallback")):
            checked = policy.refinement.check(self.request, candidate=self.candidate, limits=self.limits, client=client, cancelled=cancelled)
            replayed = policy.refinement.replay(self.request, candidate=self.candidate, limits=self.limits, report=checked.result, client=client)
        self.assertEqual(replayed.executable, "verify")
        for name in ("compile", "export", "compose", "from_data", "accept"):
            self.assertFalse(hasattr(client, name))
            self.assertFalse(hasattr(policy.refinement, name))
        self.assertFalse(hasattr(checked, "artifact"))

    def test_capability_drift_rejects_before_check_dispatch(self):
        for mutate in (lambda value: value["profiles"]["policy_refinement"].update(empirical="established"),
                       lambda value: value["profiles"]["policy_refinement"].update(relation_profile="unreviewed"),
                       lambda value: value.update(validation_scopes=[])):
            self.calls.clear()
            with self.exchange(negotiate=mutate), self.assertRaises(CoreProtocolError):
                self.check()
            self.assertEqual([value["operation"] for value in self.calls], ["capabilities"])

    def test_request_candidate_and_limits_snapshot_precedes_negotiation(self):
        original = deepcopy((self.request, self.candidate, self.limits))
        def mutate(_value):
            self.request.clear()
            self.candidate.clear()
            self.limits.clear()
        with self.exchange(negotiate=mutate):
            checked = self.check()
        self.assertEqual(checked.request_fingerprint, digest(original[0]))
        self.assertEqual(self.calls[1]["payload"], dict(zip(("request", "candidate", "limits"), original)))

    def test_all_wrapper_identities_and_closed_fields_reject_tampering(self):
        mutations = [lambda value, key=key: value.update({key: "0" * 64}) for key in
                     ("request_fingerprint", "candidate_fingerprint", "invocation_fingerprint", "material_report_fingerprint")]
        mutations += [lambda value: value.update(artifact={}), lambda value: value.update(implementation="wrong"),
                      lambda value: value.update(evidence=None)]
        for mutate in mutations:
            with self.subTest(mutation=mutate), self.exchange(mutate=mutate), self.assertRaises(CoreProtocolError):
                self.check()

    def test_claim_census_stages_and_stage_local_scopes_are_exact(self):
        mutations = [lambda rows: rows.reverse(), lambda rows: rows.pop(), lambda rows: rows.append(deepcopy(rows[0])),
            lambda rows: rows[0].update(relation="biological_efficacy"), lambda rows: rows[0]["source"].update(stage="implementation_graph"),
            lambda rows: rows[0]["source"].update(fingerprint="0" * 64),
            lambda rows: rows[0]["scope"].update(limits_fingerprint=digest(self.limits)),
            lambda rows: rows[2]["scope"].update(limits_fingerprint=None),
            lambda rows: rows[-1]["scope"].update(material_request_fingerprint=None),
            lambda rows: rows[0]["scope"].update(operating_domain_fingerprint="0" * 64),
            lambda rows: rows[0].update(empirical=True)]
        mutations += [lambda rows, index=index, endpoint=endpoint: rows[index][endpoint].update(fingerprint="0" * 64)
                      for index, endpoint in ((0, "source"), (0, "target"), (1, "target"), (4, "target"), (5, "target"))]
        mutations += [lambda rows, field=field: rows[6]["scope"].update({field: "0" * 64})
                      for field in ("implementation_request_fingerprint", "operating_domain_fingerprint", "limits_fingerprint", "material_request_fingerprint")]
        for mutate in mutations:
            with self.subTest(mutation=mutate), self.exchange(mutate=lambda value: mutate(value["evidence"]["claims"])), self.assertRaises(CoreProtocolError):
                self.check()

    def test_every_premise_is_bound_to_exact_original_or_fresh_report(self):
        for index in range(18):
            def mutate(value):
                value["evidence"]["premises"][index]["fingerprint"] = "0" * 64
            with self.subTest(index=index), self.exchange(mutate=mutate), self.assertRaises(CoreProtocolError):
                self.check()
        for mutate in (lambda rows: rows.reverse(), lambda rows: rows.pop(),
                       lambda rows: rows[0].update(kind="empirical_confirmation")):
            with self.exchange(mutate=lambda value: mutate(value["evidence"]["premises"])), self.assertRaises(CoreProtocolError):
                self.check()

    def test_derivation_is_closed_bounded_description_and_not_a_proof_constructor(self):
        mutations = [lambda value: value.update(rule="transitivity"), lambda value: value.update(inputs=[]),
                     lambda value: value.update(inputs=["a" * 64] * 2), lambda value: value.update(inputs=["a" * 64] * 17),
                     lambda value: value.update(inputs=[False, "b" * 64]), lambda value: value.update(authority="accepted")]
        for mutate in mutations:
            with self.exchange(mutate=lambda value: mutate(value["evidence"]["derivation"])), self.assertRaises(CoreProtocolError):
                self.check()
        with self.exchange(mutate=lambda value: value["evidence"]["derivation"].update(inputs=["c" * 64, "d" * 64])):
            checked = self.check()
        self.assertEqual(checked.evidence.derivation.inputs, ("c" * 64, "d" * 64))
        # These are opaque child identifiers. Only the fresh native peer can establish them.
        with self.assertRaises(CoreProtocolError):
            self.client.check(checked.evidence, self.candidate, self.limits)

    def test_nested_material_failure_rejects_even_with_refreshed_hashes(self):
        def mutate(value):
            value["material_report"]["preservation"]["coverage"]["complete"] = False
            value["material_report_fingerprint"] = digest(value["material_report"])
            value["evidence"] = evidence(self.request, self.candidate, value["material_report"], self.limits)
        with self.exchange(mutate=mutate), self.assertRaises(CoreProtocolError):
            self.check()
        with self.exchange(accepted=False, mutate=lambda value: value.update(evidence={})), self.assertRaises(CoreProtocolError):
            self.check()

    def test_replay_compares_entire_saved_wrapper_and_performs_fresh_call(self):
        with self.exchange():
            checked = self.check()
            saved = checked.result
            saved["evidence"]["derivation"]["inputs"][0] = "f" * 64
            with self.assertRaises(CoreProtocolError):
                self.client.replay(self.request, self.candidate, self.limits, saved)
        self.assertEqual(self.calls[-1]["operation"], "replay-policy-refinement")

    def test_descriptive_view_constructors_reject_wrong_categories_and_mutable_arrays(self):
        for create in (lambda: api.StageIdentity("unknown", "a" * 64), lambda: api.StageIdentity("source_document", True),
                lambda: api.RefinementScope("a" * 64, "b" * 64, 0, None),
                lambda: api.RefinementPremise("empirical", "a" * 64),
                lambda: api.RefinementDerivation("conjunction", ["a" * 64, "b" * 64]),
                lambda: api.RefinementDerivation("checked_binding", ("a" * 64,) * 17),
                lambda: api.RefinementEvidence([], (), api.RefinementDerivation("checked_binding", ())),
                lambda: api.RefinementClaim("source_graph_binding", {}, {}, {})):
            with self.subTest(create=create), self.assertRaises(CoreProtocolError):
                create()


if __name__ == "__main__":
    unittest.main()
