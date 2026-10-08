"""Pure fixture/receipt boundary controls; never launch Core, Verify or an exporter."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import check_policy_component_selection as witness


class PolicyComponentSelectionWitnessTests(unittest.TestCase):
    def packet(self):
        implementation = {"document": {"literal": "same A original"}}
        original = {"alternatives": [{"id": "short", "rank": 1, "request": {"implementation_request": deepcopy(implementation)}},
                                     {"id": "long", "rank": 0, "request": {"implementation_request": deepcopy(implementation)}}],
                    "predicate": {"max_total_nt": 17}, "budgets": {
                        "profile": "biocompiler.policy_component_selection_resources.v0.2", "max_work": 17000000000,
                        "max_report_bytes": 8323072, "max_report_nodes": 1000000}}
        packet = {"schema_version": "biocompiler.policy_component_selection_original_fixture.v0.1",
                  "status": "source_declarations_only", "acceptance": False,
                  "source_sha256": {name: "a" * 64 for name in witness.INPUTS},
                  "request": original, "limits": {"literal": "original bounds"},
                  "expected": {"short_rna": "CCAUGGCUUAAGGAAAA", "long_rna": "CGCAUGGCUUAAGGAAAA",
                               "histories": 9, "transitions": 47, "prefixes_started": 48, "obligations": witness.OBLIGATIONS}}
        source = {"request": {"implementation_request": implementation}, "limits": packet["limits"]}
        return packet, source

    def checked(self, packet, source):
        with patch.object(witness, "read_json", side_effect=[packet, source]), patch.object(witness, "digest_file", return_value="a" * 64):
            return witness.checked_fixture(Path("/literal"), Path("/literal/fixture.json"))

    def test_source_packet_is_only_declarations_and_exact_current_pins(self):
        packet, source = self.packet()
        self.assertIs(self.checked(packet, source), packet)
        for mutate in (lambda p: p.update(acceptance=True), lambda p: p.update(status="accepted"),
                       lambda p: p["source_sha256"].pop(next(iter(p["source_sha256"]))),
                       lambda p: p["source_sha256"].update(extra="a" * 64),
                       lambda p: p["expected"].update(histories=8),
                       lambda p: p["request"]["alternatives"][1]["request"].update(implementation_request={"other": "program"}),
                       lambda p: p["request"]["alternatives"][1].update(rank=2),
                       lambda p: p["request"]["budgets"].update(profile="biocompiler.policy_component_selection_resources.v0.1")):
            bad = deepcopy(packet)
            mutate(bad)
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError):
                self.checked(bad, source)

    def test_observation_census_is_closed_and_prior_campaign_unchanged(self):
        self.assertEqual(witness.OBSERVATIONS, (
            "child-short-compile", "child-long-compile", "check-core", "check-verify", "replay-core", "replay-verify",
            "export-core", "paired-core", "export-verify", "paired-verify", "long-check", "long-export", "long-paired",
            "no-eligible-check", "no-eligible-export", "loser-rank-check", "loser-rank-export", "loser-rank-paired", "stale-replay",
            "verify-no-selection-producer", "selection-compile", "selection-compile-check", "selection-compile-replay",
            "selection-long-compile", "selection-long-compile-check", "selection-no-eligible-compile", "selection-no-eligible-compile-check",
            "selection-permuted-compile", "selection-permuted-compile-check", "selection-permuted-stale-replay",
            "selection-loser-rank-compile", "selection-loser-rank-compile-check", "selection-loser-stale-replay",
            "selection-corrupt-loser-check", "selection-corrupt-loser-export"))
        self.assertEqual(len(set(witness.OBSERVATIONS)), 35)
        self.assertEqual(witness.INPUTS, ("core/test/data/policy_material_request_v01.json", "core/test/policy_component_support/literals.ml",
            "core/test/policy_component_support/requests.ml", "core/test/policy_component_support/selection_requests.ml"))

    def test_local_host_rejects_before_native_or_source_snapshot(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(witness, "source_snapshot", side_effect=AssertionError("No later acquisition")), \
                self.assertRaisesRegex(ValueError, "GitHub-hosted"):
            witness.run(SimpleNamespace())

    def test_import_boundary_allows_transport_but_no_semantic_fallback(self):
        for name in ("biocompiler.core_client", "biocompiler.core_policy_component_selection", "biocompiler.core_policy_component_material",
                     "biocompiler.policy.component_selection"):
            self.assertTrue(witness.SelectionBoundary.allowed(name), name)
        for name in ("biocompiler.compiler", "biocompiler.semantics", "biocompiler.verification", "_biocompiler_core"):
            self.assertFalse(witness.SelectionBoundary.allowed(name), name)

    def result(self):
        rows = []
        for name, sequence in (("long", "CGCAUGGCUUAAGGAAAA"), ("short", "CCAUGGCUUAAGGAAAA")):
            inner = {"status": "checked_component_material", "all_original_obligations_discharged": True,
                     "obligations": [{"obligation": name, "status": "discharged"} for name in witness.OBLIGATIONS],
                     "preservation": {"coverage": {"complete": True, "histories": 9, "transitions": 47, "prefixes_started": 48, "matched_prefixes": 48},
                         "requirements": [{"id": name, "status": "pass", "histories": {"pass": 9}}
                                          for name in ("request_progress", "initiation_progress", "exclusive_selection")]}}
            rows.append({"id": name, "total_nt": len(sequence), "sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest(),
                         "eligible": name == "short", "inner": inner})
        return {"report": {"status": "checked_selection", "selected_id": "short", "winner_matches": True, "census_complete": True,
            "all_inner_accepted": True, "empirical": "unassessed", "artifact": "withheld", "export": "withheld", "alternatives": rows}, "artifact": None}

    def test_both_children_keep_literal_rna_and_complete_domain_obligations(self):
        value = self.result()
        witness.checked_result(value, winner="short", maximum=17)
        for mutate in (lambda v: v["report"]["alternatives"][0].update(total_nt=17),
                       lambda v: v["report"]["alternatives"][0].update(eligible=True),
                       lambda v: v["report"]["alternatives"][0]["inner"]["obligations"].pop(),
                       lambda v: v["report"]["alternatives"][0]["inner"]["preservation"]["coverage"].update(histories=8),
                       lambda v: v["report"]["alternatives"][0]["inner"]["preservation"]["requirements"][0].update(status="unknown"),
                       lambda v: v["report"].update(selected_id="long")):
            altered = deepcopy(value)
            mutate(altered)
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError):
                witness.checked_result(altered, winner="short", maximum=17)

    def test_wrong_or_unpaired_literal_rna_is_rejected(self):
        value = self.result()
        value["artifact"] = {"fasta": ">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n",
                             "manifest": {"request": {"alternatives": [{"id": "short"}, {"id": "long"}]},
                                          "candidate": {}, "assessment": deepcopy(value["report"]),
                                          "selected": {"id": "short"}, "members": [{}]}}
        value["candidate"] = {}
        witness.checked_result(value, winner="short", maximum=17)
        value["artifact"]["fasta"] = ">rna_0001 alphabet=RNA\nCGCAUGGCUUAAGGAAAA\n"
        with self.assertRaises(AssertionError):
            witness.checked_result(value, winner="short", maximum=17)
