"""Literal synthetic transport peers; no native selection admission is claimed."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from biocompiler import core_policy_component_selection as api
from biocompiler.core_client import CORE_VERSION, PROTOCOL, CoreCancelled, CoreClient, CoreProtocolError, CoreRejected, CoreTimeout, encode_json
from tests import test_core_policy_component_material as child

digest = child.digest


def original():
    # Identical material is legal under different IDs. The complete two-entry
    # census and its declaration order remain original, even for the loser.
    supplied = child.original()
    return {"schema_version": "biocompiler.policy_component_selection_request.v0.1",
        "profile": "biocompiler.policy_component_material_selection.v0.1",
        "alternatives": [{"id": "z-loser", "rank": 2, "request": deepcopy(supplied)},
                         {"id": "a-winner", "rank": 1, "request": deepcopy(supplied)}],
        "predicate": {"max_total_nt": 17}, "budgets": {
            "profile": "biocompiler.policy_component_selection_resources.v0.2", "max_work": 17000000000,
            "max_report_bytes": 8323072, "max_report_nodes": 1000000}}


def candidate(request):
    return {"schema_version": "biocompiler.policy_component_selection_candidate.v0.1",
            "alternatives": [{"id": row["id"], "candidate": child.candidate(row["request"])} for row in request["alternatives"]],
            "selected_id": "a-winner"}


def generated_candidate(request):
    """Literal peer proposal; never a Python implementation of native compilation."""
    proposed = candidate(request)
    proposed["alternatives"].sort(key=lambda row: row["id"])
    proposed["selected_id"] = "a-winner" if request["predicate"]["max_total_nt"] >= 17 else None
    return proposed


def result(payload, *, failed=None, export=False):
    request = deepcopy(payload["request"])
    actual, limits = deepcopy(payload.get("candidate", generated_candidate(request))), deepcopy(payload["limits"])
    by_id = {row["id"]: row["candidate"] for row in actual["alternatives"]}
    rows = []
    eligible = []
    for original_row in sorted(request["alternatives"], key=lambda row: row["id"]):
        identity = original_row["id"]
        inner = child.report(original_row["request"], by_id[identity], limits, accepted=identity != failed)
        sequence = by_id[identity]["construction"]["inventory"]["molecules"][0]["sequence"]
        passes = len(sequence) <= request["predicate"]["max_total_nt"] if identity != failed else None
        if passes:
            eligible.append((original_row["rank"], identity))
        rows.append({"id": identity, "rank": original_row["rank"], "request_fingerprint": digest(original_row["request"]),
            "candidate_fingerprint": digest(by_id[identity]), "inner": inner,
            "total_nt": len(sequence) if identity != failed else None,
            "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest() if identity != failed else None,
            "eligible": passes})
    winner = min(eligible)[1] if eligible and failed is None else None
    matches = actual["selected_id"] == winner if failed is None else None
    status = "inner_not_accepted" if failed else "proposed_winner_mismatch" if not matches else "no_eligible_alternative" if winner is None else "checked_selection"
    invocation = {"request": request, "candidate": actual, "limits": limits}
    report = {"schema_version": "biocompiler.policy_component_selection_assessment.v0.1",
        "profile": "biocompiler.policy_component_material_selection.v0.1",
        "implementation": "biocompiler.ocaml.policy_component_selection_check.v0.1",
        "resource_profile": request["budgets"]["profile"], "common_authority_profile": "biocompiler.policy_decision_leader_variant.v0.1",
        "request_fingerprint": digest(request), "candidate_fingerprint": digest(actual), "invocation_fingerprint": digest(invocation),
        "status": status, "claim_scope": "bounded_complete_supplied_catalog_selection",
        "premise": "supplied_component_composition_and_provider_contracts", "census_complete": True,
        "all_inner_accepted": failed is None, "alternatives": rows, "predicate": deepcopy(request["predicate"]),
        "proposed_selected_id": actual["selected_id"], "selected_id": winner, "winner_matches": matches,
        "limits": limits, "budgets": deepcopy(request["budgets"]), "empirical": "unassessed", "artifact": "withheld", "export": "withheld",
        "usage": {"unit": "logical_data_visits_and_reserved_child_allowances", "charged_work": 2000010000,
                  "reserved_child_work": 2000000000, "original_decoding_work": 10, "candidate_decoding_work": 20}}
    artifact = None
    if export and status == "checked_selection":
        selected_original = next(row["request"] for row in request["alternatives"] if row["id"] == winner)
        selected_report = next(row["inner"] for row in rows if row["id"] == winner)
        artifact = child.old.artifact(selected_original, by_id[winner], limits, selected_report)
        artifact["schema_version"] = "biocompiler.policy_component_selection_mrna_export.v0.1"
        artifact["manifest"] = {"schema_version": "biocompiler.policy_component_selection_mrna_manifest.v0.1",
            "profile": "biocompiler.policy_component_material_selection.v0.1",
            "claim_scope": "bounded_complete_supplied_catalog_selection_to_exact_mrna",
            "premise": "supplied_component_composition_and_provider_contracts", "request": request, "candidate": actual,
            "limits": limits, "assessment": report,
            "bindings": {"request_fingerprint": digest(request), "candidate_fingerprint": digest(actual),
                         "invocation_fingerprint": digest(invocation), "assessment_fingerprint": digest(report)},
            "selected": {"id": winner, "request_fingerprint": digest(selected_original),
                         "candidate_fingerprint": digest(by_id[winner]), "assessment_fingerprint": digest(selected_report)},
            "members": artifact["manifest"]["members"], "fasta_sha256": artifact["fasta_sha256"],
            "empirical": "unassessed", "original_authority": "retain_original_inputs_separately"}
        artifact["manifest_sha256"] = digest(artifact["manifest"])
        artifact = deepcopy(artifact)
    return {"schema_version": "biocompiler.core.policy_component_selection.v1", "implementation": "biocompiler.ocaml.policy_component_selection.v0.1",
        "resource_profile": request["budgets"]["profile"], "validation_scope": "policy-component-selection-mrna-v0.1",
        "request_fingerprint": digest(request), "candidate_fingerprint": digest(actual), "invocation_fingerprint": digest(invocation),
        "report_fingerprint": digest(report), "candidate": actual, "report": report, "artifact": artifact}


def rehash(value):
    value["report_fingerprint"] = digest(value["report"])
    if value["artifact"] is not None:
        value["artifact"]["manifest_sha256"] = digest(value["artifact"]["manifest"])


def nodes(raw):
    if type(raw) is dict:
        return 1 + len(raw) + sum(nodes(value) for value in raw.values())
    if type(raw) is list:
        return 1 + sum(nodes(value) for value in raw)
    return 1


class PolicyComponentSelectionTransportTests(unittest.TestCase):
    def setUp(self):
        self.peer = child.PolicyComponentMaterialTransportTests()
        self.peer.setUp()
        self.addCleanup(self.peer.doCleanups)
        self.request, self.limits = original(), deepcopy(self.peer.limits)
        self.candidate = candidate(self.request)
        self.client = api.PolicyComponentSelectionClient(CoreClient(Path(sys.executable), role="verify"))
        self.calls = []

    def exchange(self, *, mutate=None, negotiate=None, failed=None, failure=None, rejection=False, stale=None):
        def call(_binary, encoded, _timeout, _cancelled):
            invocation = json.loads(encoded)
            self.calls.append(invocation)
            operation = invocation["operation"]
            role = self.client.transport.role
            if operation == "capabilities":
                value = child.capabilities(role)
                value.update(operations=["capabilities", "check-policy-component-selection", "replay-policy-component-selection", "export-policy-component-selection"],
                    validation_scopes=["policy-component-selection-mrna-v0.1"], profiles={"policy_component_selection": {
                        "operations": ["check-policy-component-selection", "replay-policy-component-selection", "export-policy-component-selection"],
                        "request_schema": "biocompiler.policy_component_selection_request.v0.1",
                        "candidate_schema": "biocompiler.policy_component_selection_candidate.v0.1",
                        "schema_version": "biocompiler.core.policy_component_selection.v1",
                        "implementation": "biocompiler.ocaml.policy_component_selection.v0.1",
                        "resource_profiles": ["biocompiler.policy_component_selection_resources.v0.1", "biocompiler.policy_component_selection_resources.v0.2"],
                        "publication_limits": [
                            {"profile": "biocompiler.policy_component_selection_resources.v0.1", "max_report_bytes": 8323072, "max_report_nodes": 249968},
                            {"profile": "biocompiler.policy_component_selection_resources.v0.2", "max_report_bytes": 8323072, "max_report_nodes": 1000000}],
                        "publication_profile": "biocompiler.policy_component_selection_publication.v0.1",
                        "validation_scope": "policy-component-selection-mrna-v0.1", "max_input_bytes": 8388608,
                        "max_result_bytes": 8323072, "max_result_nodes": 249968,
                        "artifact": "on_fresh_export_only", "empirical": "unassessed"}})
                if role == "core":
                    value["operations"].append("compile-policy-component-selection")
                    value["profiles"]["policy_component_selection_producer"] = {
                        **deepcopy(value["profiles"]["policy_component_selection"]),
                        "operations": ["compile-policy-component-selection"], "artifact": "withheld",
                        "generation_work": "shared_original_scope"}
                if negotiate:
                    negotiate(value)
            else:
                if failure:
                    raise failure
                value = deepcopy(stale) if stale is not None else result(invocation["payload"], failed=failed, export=operation == "export-policy-component-selection")
                if mutate:
                    mutate(value)
                    rehash(value)
            bad = rejection and operation != "capabilities"
            return encode_json({"protocol": PROTOCOL, "request_id": invocation["request_id"], "operation": operation,
                "status": "error" if bad else "ok", "result": None if bad else value,
                "diagnostics": [{"code": "selection_rejected", "message": "Rejected", "path": None}] if bad else [],
                "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": role}}), 2 if bad else 0
        return patch("biocompiler.core_client._exchange", side_effect=call)

    def check(self):
        return self.client.check(self.request, self.candidate, self.limits)

    def test_all_three_verification_routes_preserve_complete_originals(self):
        with self.exchange():
            checked = self.check()
            replayed = self.client.replay(self.request, self.candidate, self.limits, checked.result)
            exported = self.client.export(self.request, self.candidate, self.limits)
        self.assertEqual(checked.result, replayed.result)
        self.assertEqual(checked.status, "checked_selection")
        self.assertEqual(exported.artifact["fasta"], ">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n")
        self.assertEqual(exported.artifact["manifest"]["request"], self.request)
        self.assertEqual(exported.artifact["manifest"]["candidate"], self.candidate)
        self.assertEqual(exported.artifact["manifest"]["selected"]["id"], "a-winner")
        self.assertEqual([row["operation"] for row in self.calls], ["capabilities", "check-policy-component-selection", "capabilities", "replay-policy-component-selection", "capabilities", "export-policy-component-selection"])
        self.assertEqual(self.calls[3]["payload"]["report"], checked.result)

    def core(self):
        self.client = api.PolicyComponentSelectionClient(CoreClient(Path(sys.executable), role="core"))

    def test_compile_requires_core_before_any_transport_and_preserves_verification_profile(self):
        with self.exchange(), self.assertRaisesRegex(CoreProtocolError, "explicitly selected Core"):
            self.client.compile(self.request, self.limits)
        self.assertEqual(self.calls, [])
        self.assertEqual(api.OPERATIONS, ("check-policy-component-selection", "replay-policy-component-selection", "export-policy-component-selection"))
        self.assertEqual(api.PRODUCER_PROFILE, {**api.PROFILE, "operations": ["compile-policy-component-selection"],
                                               "artifact": "withheld", "generation_work": "shared_original_scope"})

    def test_compile_candidate_equals_fresh_verify_without_artifact(self):
        self.core()
        before = deepcopy(self.request)
        with self.exchange():
            compiled = self.client.compile(self.request, self.limits)
        self.assertEqual(self.calls[-1]["payload"], {"request": before, "limits": self.limits})
        self.assertEqual([row["id"] for row in compiled.candidate["alternatives"]], ["a-winner", "z-loser"])
        self.assertEqual(compiled.status, "checked_selection")
        self.assertIsNone(compiled.artifact)
        self.client = api.PolicyComponentSelectionClient(CoreClient(Path(sys.executable), role="verify"))
        with self.exchange():
            fresh = self.client.check(self.request, compiled.candidate, self.limits)
            replayed = self.client.replay(self.request, compiled.candidate, self.limits, compiled.result)
        self.assertEqual(compiled.result, fresh.result)
        self.assertEqual(compiled.result, replayed.result)
        compiled.candidate["alternatives"].clear()
        self.assertEqual(len(compiled.candidate["alternatives"]), 2)

    def test_compile_snapshots_originals_before_negotiation(self):
        self.core()
        before = deepcopy(self.request)
        with self.exchange(negotiate=lambda _: self.request["alternatives"].clear()):
            compiled = self.client.compile(self.request, self.limits)
        self.assertEqual(self.calls[-1]["payload"]["request"], before)
        self.assertEqual(compiled.request_fingerprint, digest(before))

    def test_compile_keeps_all_losers_and_permuted_original_authority(self):
        self.core()
        with self.exchange():
            original_result = self.client.compile(self.request, self.limits)
            self.request["alternatives"].reverse()
            permuted_result = self.client.compile(self.request, self.limits)
            self.assertEqual(original_result.candidate, permuted_result.candidate)
            self.assertNotEqual(original_result.request_fingerprint, permuted_result.request_fingerprint)
            self.assertNotEqual(original_result.invocation_fingerprint, permuted_result.invocation_fingerprint)
            with self.assertRaises(CoreProtocolError):
                self.client.replay(self.request, permuted_result.candidate, self.limits, original_result.result)
            next(row for row in self.request["alternatives"] if row["id"] == "z-loser")["rank"] = 3
            edited_result = self.client.compile(self.request, self.limits)
            self.assertEqual(edited_result.candidate, permuted_result.candidate)
            with self.assertRaises(CoreProtocolError):
                self.client.replay(self.request, edited_result.candidate, self.limits, permuted_result.result)
        with self.exchange(failed="z-loser"):
            failed = self.client.compile(self.request, self.limits)
            self.assertEqual(failed.status, "inner_not_accepted")
            self.assertIsNone(failed.artifact)
            self.assertIsNone(failed.report["alternatives"][1]["eligible"])
        self.request["predicate"]["max_total_nt"] = 0
        with self.exchange():
            empty = self.client.compile(self.request, self.limits)
            self.assertEqual(empty.status, "no_eligible_alternative")
            self.assertIsNone(empty.artifact)

    def test_compile_missing_or_changed_profile_never_calls_production(self):
        self.core()
        edits = (lambda value: value["profiles"].pop("policy_component_selection_producer"),
                 lambda value: value["profiles"]["policy_component_selection_producer"].update(generation_work="posthoc_size"),
                 lambda value: value["profiles"]["policy_component_selection_producer"].update(artifact="on_fresh_export_only"),
                 lambda value: value["profiles"]["policy_component_selection_producer"]["operations"].clear(),
                 lambda value: value["profiles"]["policy_component_selection"]["operations"].append("compile-policy-component-selection"),
                 lambda value: value.update(validation_scopes=[]))
        for edit in edits:
            self.calls.clear()
            with self.subTest(edit=edit), self.exchange(negotiate=edit), self.assertRaises(CoreProtocolError):
                self.client.compile(self.request, self.limits)
            self.assertEqual([row["operation"] for row in self.calls], ["capabilities"])

    def test_compile_rejects_incomplete_census_or_artifact_and_has_no_fallback(self):
        self.core()
        for edit in (lambda value: value["candidate"]["alternatives"].pop(),
                     lambda value: value["candidate"]["alternatives"].append(deepcopy(value["candidate"]["alternatives"][0])),
                     lambda value: value.update(artifact={"status": "pass", "manifest": {}}),
                     lambda value: value["report"].update(empirical="validated")):
            with self.subTest(edit=edit), self.exchange(mutate=edit), self.assertRaises(CoreProtocolError):
                self.client.compile(self.request, self.limits)
        for error in (CoreTimeout("literal"), CoreCancelled("literal")):
            with self.subTest(error=error), self.exchange(failure=error), self.assertRaises(type(error)):
                self.client.compile(self.request, self.limits)
        with self.exchange(rejection=True), self.assertRaises(CoreRejected):
            self.client.compile(self.request, self.limits)

    def test_snapshot_and_result_are_immutable(self):
        request_before = deepcopy(self.request)
        with self.exchange():
            checked = self.check()
        self.request["alternatives"].clear()
        self.assertEqual(self.calls[-1]["payload"]["request"], request_before)
        checked.result["candidate"].clear()
        self.assertEqual(checked.candidate, self.candidate)
        with self.assertRaises(FrozenInstanceError):
            checked.operation = "foreign"

    def test_loser_edit_invalidates_replay_even_with_unchanged_selected_rna(self):
        with self.exchange():
            old = self.check()
            self.request["alternatives"][0]["rank"] = 3
            fresh = self.check()
            self.assertEqual(old.report["selected_id"], fresh.report["selected_id"])
            self.assertEqual(old.candidate, fresh.candidate)
            self.assertNotEqual(old.request_fingerprint, fresh.request_fingerprint)
            with self.assertRaises(CoreProtocolError):
                self.client.replay(self.request, self.candidate, self.limits, old.result)
        with self.exchange(stale=old.result), self.assertRaises(CoreProtocolError):
            self.check()

    def test_v1_limits_remain_fixed_and_v2_is_explicit(self):
        v1 = deepcopy(self.request)
        v1["budgets"].update(profile=api.RESOURCE_PROFILE, max_report_nodes=249968)
        self.assertEqual(api._original(v1), v1)
        v1["budgets"]["max_report_nodes"] = 249969
        with self.assertRaises(CoreProtocolError):
            api._original(v1)
        self.assertEqual(api._original(self.request)["budgets"]["max_report_nodes"], 1000000)
        for field, invalid in (("max_report_nodes", 1000001), ("max_report_bytes", 8323073), ("max_work", 17000000001)):
            supplied = deepcopy(self.request)
            supplied["budgets"][field] = invalid
            with self.subTest(field=field), self.assertRaises(CoreProtocolError):
                api._original(supplied)
        self.request = v1
        self.request["budgets"]["max_report_nodes"] = 249968
        with self.exchange():
            self.assertEqual(self.check().result["resource_profile"], api.RESOURCE_PROFILE)

    def test_integer_and_result_preflight_are_exact_and_precede_fingerprints(self):
        for value in ((1 << 4096) - 1, -((1 << 4096) - 1)):
            size, count = api._measure(value)
            self.assertEqual(size, len(str(value)))
            self.assertEqual(count, 1)
        for value in (1 << 4096, -(1 << 4096)):
            with self.subTest(sign=value > 0), self.assertRaisesRegex(CoreProtocolError, "bit profile"):
                api._measure(value)
        # The wire decoder admits this bounded decimal number. The selection
        # result guard must reject it before any expensive evidence walk.
        with self.exchange(mutate=lambda v: v.update(extra=1 << 4096)), \
                patch.object(api, "_pin", side_effect=AssertionError("Fingerprint ran before selection preflight")), \
                self.assertRaisesRegex(CoreProtocolError, "bit profile"):
            self.check()

    def test_original_and_candidate_census_grammar_rejects_before_native(self):
        edits = [lambda v: v["alternatives"].pop(), lambda v: v["alternatives"].append(deepcopy(v["alternatives"][0])),
                 lambda v: v["alternatives"][0].update(id="foreign"), lambda v: v.update(selected_id="missing")]
        for edit in edits:
            actual = deepcopy(self.candidate)
            edit(actual)
            with self.subTest(edit=edit), self.exchange(), self.assertRaises(CoreProtocolError):
                self.client.check(self.request, actual, self.limits)
        self.assertEqual(self.calls, [])
        for value in (True, -1, 2147483648, 1.0):
            supplied = deepcopy(self.request)
            supplied["alternatives"][0]["rank"] = value
            with self.subTest(rank=value), self.assertRaises(CoreProtocolError):
                api._original(supplied)
        for identity in ("", "_x", "é", "a/b", "x" * 129):
            supplied = deepcopy(self.request)
            supplied["alternatives"][0]["id"] = identity
            with self.subTest(identity=identity), self.assertRaises(CoreProtocolError):
                api._original(supplied)

    def test_census_order_rank_length_feedback_and_nested_claim_mutations_reject(self):
        edits = [lambda v: v["report"]["alternatives"].pop(), lambda v: v["report"]["alternatives"].reverse(),
            lambda v: v["report"]["alternatives"][1].update(rank=1),
            lambda v: v["report"]["alternatives"][1].update(total_nt=1),
            lambda v: v["report"]["alternatives"][1].update(eligible=False),
            lambda v: v["report"]["alternatives"][1].update(sequence_sha256="0" * 64),
            lambda v: v["report"]["alternatives"][1]["inner"].update(candidate_fingerprint="0" * 64),
            lambda v: v["report"]["alternatives"][1]["inner"]["context"].update(biological_validity="pass"),
            lambda v: v["report"].update(census_complete=False), lambda v: v["report"].update(empirical="pass"),
            lambda v: v["report"].update(selected_id="z-loser"), lambda v: v["report"].update(winner_matches=1),
            lambda v: v["report"]["usage"].update(reserved_child_work=1), lambda v: v["report"].update(resource_profile=api.RESOURCE_PROFILE)]
        for edit in edits:
            with self.subTest(edit=edit), self.exchange(mutate=edit), self.assertRaises(CoreProtocolError):
                self.check()

    def test_failed_loser_is_not_an_ineligible_success(self):
        with self.exchange(failed="z-loser"):
            checked = self.check()
            self.assertEqual(checked.status, "inner_not_accepted")
            self.assertIsNone(checked.report["alternatives"][1]["eligible"])
            with self.assertRaises(CoreProtocolError):
                self.client.export(self.request, self.candidate, self.limits)
        with self.exchange(failed="z-loser", mutate=lambda v: v["report"].update(status="checked_selection", all_inner_accepted=True)), self.assertRaises(CoreProtocolError):
            self.check()

    def test_rank_tie_predicate_and_proposed_winner_are_bound(self):
        self.request["alternatives"][0]["rank"] = 1
        with self.exchange():
            self.assertEqual(self.check().report["selected_id"], "a-winner")
            self.candidate["selected_id"] = "z-loser"
            self.assertEqual(self.check().status, "proposed_winner_mismatch")
            self.request["predicate"]["max_total_nt"] = 0
            self.candidate["selected_id"] = None
            self.assertEqual(self.check().status, "no_eligible_alternative")

    def test_outer_manifest_retains_losers_selected_child_and_exact_pair(self):
        edits = [lambda v: v["artifact"]["manifest"]["request"]["alternatives"].pop(0),
            lambda v: v["artifact"]["manifest"]["candidate"]["alternatives"].pop(0),
            lambda v: v["artifact"]["manifest"]["selected"].update(id="z-loser"),
            lambda v: v["artifact"]["manifest"]["selected"].update(assessment_fingerprint="0" * 64),
            lambda v: v["artifact"]["manifest"]["bindings"].update(request_fingerprint=v["artifact"]["manifest"]["selected"]["request_fingerprint"]),
            lambda v: v["artifact"]["manifest"]["members"][0]["molecule"].update(sequence="A"),
            lambda v: v["artifact"].update(fasta=">rna_0001 alphabet=RNA\nA\n", fasta_sha256=hashlib.sha256(b">rna_0001 alphabet=RNA\nA\n").hexdigest()),
            lambda v: v["artifact"]["manifest"].update(empirical="pass")]
        for edit in edits:
            with self.subTest(edit=edit), self.exchange(mutate=edit), self.assertRaises(CoreProtocolError):
                self.client.export(self.request, self.candidate, self.limits)

    def test_cumulative_publication_counts_repeated_nested_values(self):
        payload = {"request": self.request, "candidate": self.candidate, "limits": self.limits}
        raw = result(payload, export=True)
        report = raw["report"]
        events = [row["inner"] for row in report["alternatives"]] + [report, raw["artifact"]["manifest"],
            {"protocol": PROTOCOL, "request_id": "literal", "operation": "export-policy-component-selection", "status": "ok",
             "result": raw, "diagnostics": [], "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": "verify"}}]
        sizes = [nodes(value) for value in events]
        self.assertGreater(sum(sizes), max(sizes) + 1)
        self.request["budgets"]["max_report_nodes"] = max(sizes) + 1
        with self.exchange(), self.assertRaisesRegex(CoreProtocolError, "cumulative"):
            self.client.export(self.request, self.candidate, self.limits)
        self.request["budgets"]["max_report_nodes"] = sum(sizes)
        with self.exchange():
            self.client.export(self.request, self.candidate, self.limits)
        self.request["budgets"]["max_report_nodes"] -= 1
        with self.exchange(), self.assertRaisesRegex(CoreProtocolError, "cumulative"):
            self.client.export(self.request, self.candidate, self.limits)

    def test_capability_downgrade_and_native_failures_have_no_fallback(self):
        for edit in (lambda v: v["profiles"]["policy_component_selection"]["resource_profiles"].pop(),
                     lambda v: v["profiles"]["policy_component_selection"]["publication_limits"][0].update(max_report_nodes=1000000),
                     lambda v: v.update(validation_scopes=[])):
            with self.subTest(edit=edit), self.exchange(negotiate=edit), self.assertRaises(CoreProtocolError):
                self.check()
        with self.exchange(failure=CoreTimeout("literal")), self.assertRaises(CoreTimeout):
            self.check()
        with self.exchange(rejection=True), self.assertRaises(CoreRejected):
            self.check()
