"""M10.6 examples retain independent scope, outcomes and refusal to compile."""

from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.cli import main as cli_main
from biocompiler.ir.serialization import fingerprint
from examples.human_profile_cases import (
    assess_case,
    explain_healthy_rate_conflict,
    explore_traces,
    generate_artifacts,
    main,
    make_cases,
    portable_request,
    verify_saved,
)
from examples.human_acceptance import make_human_acceptance
from examples.human_deployment import PLATFORM_SOURCE


class HumanProfileCaseTests(unittest.TestCase):
    def setUp(self):
        self.cases = {case.id: case for case in make_cases()}
        self.positive = self.cases["positive"]

    def check(self, name):
        case = self.cases[name]
        return bc.check_human_acceptance(case.request, case.trace)

    def test_all_categories_and_independently_expected_outcomes(self):
        expected = {
            "positive": "pass",
            "negative_silent": "fail",
            "negative_peak": "fail",
            "negative_expression_window": "fail",
            "conflicting_healthy": "fail",
            "underspecified_deployment": "unknown",
            "underspecified_observations": "unknown",
            "unsupported_co_payload": "unsupported",
            "unsupported_destination": "unsupported",
            "failure_with_unknown": "fail",
        }
        self.assertEqual(set(self.cases), set(expected))
        self.assertEqual(
            {case.category for case in self.cases.values()},
            {"positive", "negative", "conflicting", "underspecified", "unsupported"},
        )
        for name, outcome in expected.items():
            with self.subTest(name=name):
                self.assertEqual(self.check(name).outcome, outcome)

    def test_requests_and_traces_roundtrip_without_mutation(self):
        for case in self.cases.values():
            before = case.request.to_json()
            restored = bc.HumanAcceptanceRequest.from_json(before)
            samples = tuple(
                bc.AcceptanceSample.from_json(item.to_json()) for item in case.trace
            )
            self.assertEqual(
                restored.artifact_fingerprint, case.request.artifact_fingerprint
            )
            self.assertEqual(
                bc.check_human_acceptance(restored, samples), self.check(case.id)
            )
            self.assertEqual(case.request.to_json(), before)

    def test_logical_source_paths_preserve_semantics_and_authored_lines(self):
        original, portable = make_human_acceptance(), portable_request()
        self.assertEqual(original.fingerprint, portable.fingerprint)
        for before, after in zip(
            original.build_request.intent.nodes, portable.build_request.intent.nodes
        ):
            self.assertEqual(after.source.file, "examples/human_behavior.py")
            self.assertEqual(
                (before.source.line, before.source.function),
                (after.source.line, after.source.function),
            )
        self.assertNotIn(str(Path.cwd()), portable.to_json())

    def test_positive_is_complete_finite_coverage_but_no_biological_admission(self):
        row, artifacts = assess_case(self.positive)
        self.assertEqual(
            set(row["coverage"]),
            {
                "active",
                "inactive",
                "recovered",
                "healthy",
                "input_loss_recovered",
                "shutdown",
            },
        )
        self.assertEqual(row["acceptance"], "pass")
        self.assertTrue(row["unresolved_evidence"])
        self.assertEqual(row["admission"], "not_admitted")
        self.assertEqual(
            artifacts["acceptance.json"]["biological_applicability"], "unestablished"
        )
        self.assertEqual(
            artifacts["acceptance.json"]["actuator_support"], "unimplemented"
        )

    def test_silent_candidate_does_not_pass_just_by_obeying_prohibitions(self):
        result = self.check("negative_silent")
        self.assertIn("active_range_violation_at:3", result.diagnostics)
        self.assertIn("healthy", result.coverage)

    def test_peak_violation_checked_before_activation_deadline(self):
        result = self.check("negative_peak")
        self.assertIn("peak_ceiling_exceeded_at:2", result.diagnostics)
        self.assertNotIn("active_range_violation_at:2", result.diagnostics)

    def test_missing_readout_is_distinct_from_zero_and_compliant_measurement(self):
        case = self.cases["underspecified_observations"]
        outcomes = []
        for rate in (
            None,
            bc.ProductionRate(0),
            bc.ProductionRate(2.5, unit="molecules/s"),
        ):
            trace = list(case.trace)
            trace[2] = replace(trace[2], output_value=rate)
            outcomes.append(
                bc.check_human_acceptance(case.request, tuple(trace)).outcome
            )
        self.assertEqual(outcomes, ["unknown", "fail", "pass"])

    def test_underspecified_request_preserves_each_missing_deployment_bound(self):
        result = self.check("underspecified_deployment")
        self.assertIn("expression_window_unknown", result.diagnostics)
        self.assertIn("deployment_exposure_bounds_unknown", result.diagnostics)
        self.assertEqual(result.outcome, "unknown")

    def test_known_short_expression_window_is_request_failure_not_unknown(self):
        case = self.cases["negative_expression_window"]
        self.assertNotEqual(case.request.fingerprint, self.positive.request.fingerprint)
        self.assertEqual(case.trace, self.positive.trace)
        result = bc.check_deployment(case.request.deployment_request)
        self.assertEqual(result.compatibility, "fail")
        self.assertIn("expression_duration_does_not_cover_behavior", result.diagnostics)
        self.assertEqual(self.check(case.id).outcome, "fail")

    def test_known_failure_keeps_unknown_diagnostic(self):
        result = self.check("failure_with_unknown")
        self.assertEqual(result.outcome, "fail")
        self.assertIn("peak_ceiling_exceeded_at:2", result.diagnostics)
        self.assertIn("output_unobserved_at:3", result.diagnostics)

    def test_unsupported_dependencies_are_not_observed_failures(self):
        for name, code in (
            ("unsupported_co_payload", "same_cell_co_payload_delivery_unsupported"),
            ("unsupported_destination", "deployment_destination_profile_unsupported"),
        ):
            result = self.check(name)
            self.assertEqual(result.outcome, "unsupported")
            self.assertIn(code, result.diagnostics)

    def test_conflict_survives_output_missingness_and_every_candidate_rate(self):
        case = self.cases["conflicting_healthy"]
        for rate in (None, 0, 0.1, 2, 2.5, 5):
            trace = list(case.trace)
            trace[2] = replace(
                trace[2],
                output_value=None
                if rate is None
                else bc.ProductionRate(rate, unit="molecules/s"),
            )
            result = bc.check_human_acceptance(case.request, tuple(trace))
            self.assertEqual(result.outcome, "fail")
            self.assertIn(
                "required_active_conflicts_with_healthy_at:3", result.diagnostics
            )

    def test_conflict_request_change_invalidates_identity_without_rewriting_source(
        self,
    ):
        case = self.cases["conflicting_healthy"]
        self.assertNotEqual(case.request.fingerprint, self.positive.request.fingerprint)
        self.assertEqual(
            case.request.build_request, self.positive.request.build_request
        )
        trace = list(case.trace)
        trace[2] = replace(
            trace[2], output_value=bc.ProductionRate(2.5, unit="molecules/s")
        )
        self.assertEqual(
            bc.check_human_acceptance(self.positive.request, tuple(trace)).outcome,
            "pass",
        )
        self.assertFalse(self.check("positive").is_current(case.request, case.trace))

    def test_rate_contradiction_is_a_conditional_bound_proof_not_biological_infeasibility(
        self,
    ):
        case = self.cases["conflicting_healthy"]
        proof = explain_healthy_rate_conflict(case.request)
        self.assertEqual(proof["request_fingerprint"], case.request.fingerprint)
        contract = case.request.behavior_request.contract
        self.assertGreater(
            contract.response.active_range.lower.canonical_value,
            case.request.acceptance.background_ceiling.canonical_value,
        )
        self.assertEqual(
            proof["formal_feasibility"], "infeasible_under_stated_condition"
        )
        self.assertEqual(proof["reachability"], "not_proved")
        self.assertEqual(proof["biological_feasibility"], "unestablished")
        self.assertEqual(proof["scope"], "simultaneous_output_rate_constraints_only")

    def test_every_case_stays_unavailable_to_compile(self):
        for case in self.cases.values():
            with (
                self.subTest(case=case.id),
                self.assertRaises(bc.CompilationUnavailableError) as caught,
            ):
                bc.compile(case.request)
            codes = {item.code for item in caught.exception.diagnostics}
            self.assertIn("human_profile_unavailable", codes)
            self.assertIn("complete_payload_not_promoted", codes)
            self.assertIn("external_shutdown_actuator_unimplemented", codes)

    def test_expected_outcome_label_cannot_override_checker(self):
        with self.assertRaises(bc.SerializationError):
            assess_case(replace(self.cases["negative_silent"], expected_outcome="pass"))

    def test_unexpected_compile_enablement_fails_suite(self):
        with patch("examples.human_profile_cases.bc.compile", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "must not enable"):
                assess_case(self.positive)


class TraceSearchDistinctionTests(unittest.TestCase):
    def setUp(self):
        self.cases = {case.id: case for case in make_cases()}
        self.request = self.cases["positive"].request
        self.candidates = tuple(
            (name, self.cases[name].trace)
            for name in ("negative_silent", "underspecified_observations", "positive")
        )

    def search(self, candidates=None, budget=3):
        return explore_traces(
            self.request,
            self.candidates if candidates is None else candidates,
            budget=budget,
        )

    def test_candidate_set_exhaustion_retains_failed_and_unknown_results(self):
        result = self.search(self.candidates[:2])
        self.assertEqual(result["outcome"], "candidate_set_exhausted")
        self.assertEqual(
            [entry["result"]["outcome"] for entry in result["checked"]],
            ["fail", "unknown"],
        )
        self.assertEqual(result["unchecked_count"], 0)
        self.assertEqual(result["infeasibility"], "not_established")

    def test_budget_exhaustion_does_not_claim_to_cover_the_candidate_set(self):
        result = self.search(budget=1)
        self.assertEqual(result["outcome"], "budget_exhausted")
        self.assertEqual(result["unchecked_count"], 2)
        self.assertIsNone(result["witness"])
        self.assertEqual(result["infeasibility"], "not_established")

    def test_expanding_the_exhausted_candidate_set_can_find_a_witness(self):
        exhausted = self.search(self.candidates[:2])
        result = self.search()
        self.assertEqual(result["outcome"], "witness_found")
        self.assertEqual(result["witness"], "positive")
        self.assertNotEqual(
            result["candidate_set_fingerprint"], exhausted["candidate_set_fingerprint"]
        )
        self.assertEqual(result["human_therapeutic_admission"], "not_admitted")
        self.assertEqual(result["mechanism_search"], "not_performed")

    def test_empty_set_and_zero_budget_do_not_prove_infeasibility(self):
        for candidates, outcome in (
            ((), "candidate_set_exhausted"),
            (self.candidates, "budget_exhausted"),
        ):
            result = self.search(candidates, budget=0)
            self.assertEqual(result["outcome"], outcome)
            self.assertEqual(result["checked"], [])
            self.assertEqual(result["infeasibility"], "not_established")

    def test_candidate_order_and_budget_remain_explicit(self):
        result = self.search(tuple(reversed(self.candidates)), budget=1)
        self.assertEqual(result["outcome"], "witness_found")
        self.assertEqual(result["unchecked_count"], 2)
        self.assertEqual(
            result["candidate_set_fingerprint"], fingerprint(result["candidates"])
        )
        self.assertNotEqual(
            result["candidate_set_fingerprint"],
            self.search(budget=1)["candidate_set_fingerprint"],
        )

    def test_invalid_budget_and_duplicate_ids_are_rejected(self):
        for budget in (-1, True, 1.5):
            with self.assertRaises(bc.SerializationError):
                self.search(budget=budget)
        with self.assertRaises(bc.SerializationError):
            self.search((self.candidates[0], self.candidates[0]))


class ProfileEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifacts = generate_artifacts()

    def write(self, directory):
        for name, content in self.artifacts.items():
            path = Path(directory) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

    def test_generation_is_deterministic_and_retains_pinned_fixture_source(self):
        self.assertEqual(generate_artifacts(), self.artifacts)
        self.assertEqual(self.artifacts["platform-fixture.txt"], PLATFORM_SOURCE)
        summary = json.loads(self.artifacts["summary.json"])
        self.assertEqual(len(summary["cases"]), 10)
        self.assertEqual(summary["human_therapeutic_admission"], "not_admitted")
        self.assertEqual(summary["compilation"], "unavailable")
        for row in summary["cases"]:
            self.assertEqual(row["mechanism_search"], "not_performed")
            request = bc.HumanAcceptanceRequest.from_json(
                self.artifacts[f"{row['id']}/request.json"].decode()
            )
            self.assertEqual(request.fingerprint, row["request_fingerprint"])
            self.assertEqual(
                request.artifact_fingerprint, row["request_artifact_fingerprint"]
            )

    def test_saved_records_verify_after_relocation(self):
        with tempfile.TemporaryDirectory() as directory:
            first, relocated = Path(directory) / "first", Path(directory) / "second"
            self.write(first)
            first.rename(relocated)
            verify_saved(relocated, generate_artifacts())

    def test_altered_results_requests_search_or_proof_cannot_be_reused(self):
        names = (
            "summary.json",
            "positive/request.json",
            "negative_silent/acceptance.json",
            "search/candidate_set_exhausted.json",
            "conflicting_healthy/rate-conflict.json",
        )
        for name in names:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                self.write(directory)
                path = Path(directory) / name
                data = json.loads(path.read_bytes())
                data["biological_applicability"] = "validated"
                path.write_text(json.dumps(data))
                with self.assertRaisesRegex(bc.SerializationError, "Stale or altered"):
                    verify_saved(directory, generate_artifacts())

    def test_missing_extra_or_linked_evidence_is_rejected(self):
        for mutation in ("missing", "extra", "symlink"):
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as directory,
            ):
                self.write(directory)
                file = Path(directory) / "summary.json"
                if mutation == "missing":
                    file.unlink()
                elif mutation == "extra":
                    (Path(directory) / "unlisted.json").write_text("{}")
                else:
                    file.unlink()
                    file.symlink_to("positive/request.json")
                with self.assertRaises(bc.SerializationError):
                    verify_saved(directory, self.artifacts)

    def test_example_cli_emits_and_freshly_verifies_evidence(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            redirect_stdout(io.StringIO()) as output,
        ):
            main(["--output", directory])
            main(["--verify", directory])
            self.assertIn("matches fresh current fixture checks", output.getvalue())
            self.assertIn("human compilation unavailable", output.getvalue())

    def test_core_cli_inspects_saved_authority_and_results(self):
        with tempfile.TemporaryDirectory() as directory:
            self.write(directory)
            for name in (
                "positive/request.json",
                "positive/acceptance.json",
                "conflicting_healthy/acceptance.json",
                "underspecified_deployment/deployment.json",
                "unsupported_co_payload/admission.json",
            ):
                with self.subTest(name=name), redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(
                        cli_main(["inspect", str(Path(directory) / name)]), 0
                    )
                    self.assertIn("schema_version", output.getvalue())


if __name__ == "__main__":
    unittest.main()
