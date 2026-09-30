"""Auditable cross-layer mutations with positive controls and intended evidence.

The inventory below names each obligation and its expected rejection signature;
the tests do not count arbitrary exceptions or unrelated failures as detection.
"""

import ast
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.compiler.behavior import lower_to_behavior, verify_lowering
from biocompiler.compiler.request import BuildRequest
from biocompiler.compiler.synthetic import run_synthetic_pipeline
from biocompiler.errors import LoweringVerificationError, SerializationError
from biocompiler.ir.behavior import BehaviorProgram
from biocompiler.semantics.types import BOOLEAN
from biocompiler.verification.construct import check_construct
from biocompiler.verification.evidence import CheckOutcome, CheckResult, EvidenceKind
from biocompiler.verification.molecular import check_molecular
from biocompiler.verification.realization import (
    check_realization,
    realization_dependencies,
)
from examples.realization_check import build_example, with_delay
from test_build_request import inputs as binding_inputs
from test_construct_checker import candidate_for, fixture as construct_fixture
from test_molecular_checker import fixture as molecular_fixture, with_sequence
from test_realization_checker import fixture as realization_fixture
from test_synthetic_generation import exercised_history, fixture as synthetic_fixture


MUTATION_MATRIX = (
    ("binding", "verify_lowering", "authoritative_bindings"),
    ("observation_swap", "check_realization", "input_endpoint"),
    ("cross_contact_scope", "check_realization", "response_violation:inactive@0.5"),
    ("silent_response", "check_realization", "response_violation:active@1.5"),
    ("shifted_deadline", "check_realization", "response_violation:active@1.5"),
    ("stale_dependency", "CheckResult.freshness", "stale:mechanism"),
    ("component_order", "check_construct", "component_order"),
    (
        "synonymous_nucleotide",
        "check_molecular",
        "exact_reference:fail;translation_reference:pass",
    ),
)


def _aggregate_before_conjunction(args):
    candidate, mapping, domain = args[4], args[5], args[2]
    first, second = (item.mechanism_input_id for item in mapping.inputs)
    aggregate = candidate.find("any_contact")[0].id
    boolean = bc.Observable("aggregated_a", BOOLEAN, domain.role)
    extra = (
        bc.MechanismNode("any_a", "any_contact", boolean, (first,)),
        bc.MechanismNode(
            "any_b", "any_contact", replace(boolean, id="aggregated_b"), (second,)
        ),
    )
    return replace(
        candidate,
        nodes=tuple(
            replace(node, kind="and", inputs=("any_a", "any_b"))
            if node.id == aggregate
            else node
            for node in candidate.nodes
        )
        + extra,
    )


class VerificationMutationCampaignTests(unittest.TestCase):
    def test_mutation_inventory_matches_executed_obligation_campaign(self):
        detected = set()
        request = BuildRequest.freeze(binding_inputs())
        behavior = lower_to_behavior(request)
        self.assertTrue(verify_lowering(request, behavior).passed)
        altered = behavior.to_dict()
        parameter = next(
            item for item in altered["nodes"] if item["kind"] == "parameter"
        )
        parameter["attributes"]["default"].update(value=9, canonical_value=9)
        altered["parameter_bindings"]["amount"].update(value=9, canonical_value=9)
        with self.assertRaisesRegex(
            LoweringVerificationError, "authoritative_bindings"
        ):
            verify_lowering(request, BehaviorProgram.from_dict(altered))
        detected.add("binding")

        args = build_example()
        baseline = check_realization(*args, until=7)
        self.assertEqual(baseline.outcome, CheckOutcome.PASS)
        original, mapping = args[4], args[5]
        swapped = replace(
            mapping,
            inputs=(
                replace(
                    mapping.inputs[0],
                    mechanism_input_id=mapping.inputs[1].mechanism_input_id,
                ),
                replace(
                    mapping.inputs[1],
                    mechanism_input_id=mapping.inputs[0].mechanism_input_id,
                ),
            ),
        )
        result = check_realization(*args[:5], swapped, args[6], until=7)
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertEqual(
            tuple(item.code for item in result.diagnostics), ("input_endpoint",)
        )
        self.assertFalse(result.counterexamples)
        detected.add("observation_swap")

        silent = replace(
            original,
            nodes=tuple(
                replace(node, inputs=("inactive:response.rest",))
                if node.id in original.outputs
                else node
                for node in original.nodes
            ),
        )
        variants = (
            (
                "cross_contact_scope",
                _aggregate_before_conjunction(args),
                "inactive",
                0.5,
                0.9,
            ),
            ("silent_response", silent, "active", 1.5, 0),
            ("shifted_deadline", with_delay(original, 2), "active", 1.5, 0),
        )
        for name, candidate, state, time, actual in variants:
            result = check_realization(*args[:4], candidate, *args[5:], until=7)
            with self.subTest(mutation=name):
                self.assertEqual(result.outcome, CheckOutcome.FAIL)
                self.assertIn(
                    "response_violation", {item.code for item in result.diagnostics}
                )
                first = result.counterexamples[0]
                self.assertEqual(
                    (first.expected["state"], first.time, first.actual),
                    (state, time, actual),
                )
                self.assertEqual(first.requirement_id, "response.rest")
                self.assertIsNotNone(first.source)
            detected.add(name)
        changed = realization_dependencies(
            *args[:4], with_delay(original, 2), *args[5:], until=7
        )
        freshness = baseline.freshness(changed)
        self.assertEqual(freshness.status, "stale")
        self.assertEqual(freshness.changed_dependencies, ("mechanism",))
        detected.add("stale_dependency")

        construct_request, construct, registry, manifests = construct_fixture()
        self.assertTrue(
            check_construct(construct_request, construct, registry, manifests).passed
        )
        # Also update the candidate's request identity: the independent layout
        # rule, rather than merely an old fingerprint, must reject this order.
        changed_request = replace(
            construct_request,
            molecules=(
                replace(
                    construct_request.molecules[0], component_order=("other", "cds")
                ),
            ),
        )
        result = check_construct(
            changed_request, candidate_for(changed_request), registry, manifests
        )
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        self.assertEqual(
            {item.code for item in result.diagnostics}, {"component_order"}
        )
        detected.add("component_order")

        molecule_request, construct, artifact, registry, manifests = molecular_fixture()
        self.assertTrue(
            check_molecular(
                molecule_request, construct, artifact, registry, manifests
            ).passed
        )
        sequence = artifact.records[0].sequence
        self.assertEqual(sequence[3:6], "GCC")
        changed = with_sequence(artifact, sequence[:5] + "T" + sequence[6:])
        result = check_molecular(
            molecule_request, construct, changed, registry, manifests
        )
        self.assertEqual(result.outcome, CheckOutcome.FAIL)
        checks = {item.check: item.outcome for item in result.checks}
        self.assertEqual(checks["exact_reference"], CheckOutcome.FAIL)
        self.assertEqual(checks["translation_reference"], CheckOutcome.PASS)
        self.assertEqual(checks["canonical_hash"], CheckOutcome.PASS)
        detected.add("synonymous_nucleotide")
        self.assertEqual(detected, {row[0] for row in MUTATION_MATRIX})

    def test_behavior_runtime_and_model_runner_have_separate_execution_dependencies(
        self,
    ):
        root = Path(__file__).resolve().parents[1] / "src/biocompiler"
        restrictions = {
            "models/synthetic.py": (
                "biocompiler.semantics.evaluator",
                "biocompiler.synthesis",
            ),
            "semantics/evaluator.py": ("biocompiler.models", "biocompiler.synthesis"),
        }
        for relative, forbidden in restrictions.items():
            tree = ast.parse((root / relative).read_text(encoding="utf-8"))
            imports = [
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            ]
            imports.extend(
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            )
            with self.subTest(module=relative):
                self.assertFalse(
                    any(
                        name.startswith(prefix)
                        for name in imports
                        for prefix in forbidden
                    )
                )

    def test_acceptance_entry_points_work_without_lowerer_assembler_or_emitter(self):
        finite = realization_fixture()
        construct = construct_fixture()
        molecular = molecular_fixture()
        with ExitStack() as stack:
            for symbol in (
                "biocompiler.compiler.behavior.lower_to_behavior",
                "biocompiler.synthesis.synthetic.generate_synthetic",
                "biocompiler.synthesis.construct.generate_construct",
                "biocompiler.backends.reference.emit_reference_sequence",
            ):
                stack.enter_context(
                    patch(
                        symbol,
                        side_effect=AssertionError(
                            "producer cannot be acceptance authority"
                        ),
                    )
                )
            self.assertTrue(check_realization(*finite).passed)
            self.assertTrue(check_construct(*construct).passed)
            self.assertTrue(check_molecular(*molecular).passed)


class EvidenceCoverageAuditTests(unittest.TestCase):
    def history(self, args, events):
        signal = args[2].inputs[0].signal_id
        return tuple(
            bc.InputFrame(time, {signal: bc.SignalSample(present=value)})
            for time, value in events
        )

    def test_active_and_inactive_deadlines_and_unfinished_episodes_are_separate(self):
        args = list(realization_fixture(delay=0))
        self.assertTrue(check_realization(*args).passed)
        scenarios = (
            (
                "active_only",
                ((0, True), (10, True)),
                10,
                "unexercised_inactive_response",
                (1, 0, 0),
            ),
            (
                "inactive_only",
                ((0, False), (10, False)),
                10,
                "unexercised_response",
                (0, 1, 0),
            ),
            (
                "pending_activation",
                ((0, False), (2, True)),
                2.5,
                "incomplete_episode",
                (0, 1, 1),
            ),
            (
                "pending_deactivation",
                ((0, False), (2, True), (9.75, False)),
                10,
                "incomplete_episode",
                (1, 1, 1),
            ),
        )
        for name, events, horizon, code, counts in scenarios:
            result = check_realization(
                *args[:6], self.history(args, events), until=horizon
            )
            with self.subTest(scenario=name):
                self.assertEqual(result.outcome, CheckOutcome.UNKNOWN)
                self.assertIn(code, {item.code for item in result.diagnostics})
                coverage = result.coverage[0]
                self.assertEqual(
                    (
                        coverage.activation_deadlines_checked,
                        coverage.inactive_deadlines_checked,
                        coverage.incomplete_episode_count,
                    ),
                    counts,
                )
                self.assertEqual(result.evidence_kind, EvidenceKind.MODEL_CONDITIONAL)
                if 0 in counts[:2]:
                    self.assertEqual(result.exercised_requirement_ids, ())

    def test_incomplete_inputs_do_not_create_response_coverage(self):
        args = realization_fixture(delay=0)
        scenarios = (
            ((), "empty_history"),
            ((bc.InputFrame(1),), "invalid_history"),
            ((bc.InputFrame(0), bc.InputFrame(10)), "outside_domain"),
        )
        for history, code in scenarios:
            result = check_realization(*args[:6], history, until=10)
            with self.subTest(code=code):
                self.assertEqual(result.outcome, CheckOutcome.UNKNOWN)
                self.assertEqual(
                    tuple(item.code for item in result.diagnostics), (code,)
                )
                self.assertEqual(result.coverage, ())

    def test_serialized_pass_cannot_drop_inactive_coverage_or_promote_evidence(self):
        result = check_realization(*realization_fixture())
        self.assertTrue(result.passed)
        self.assertIn("v0.3", result.dependencies.values["checker"])
        missing = result.to_dict()
        missing["coverage"][0]["inactive_deadlines_checked"] = 0
        with self.assertRaisesRegex(SerializationError, "active and inactive"):
            CheckResult.from_dict(missing)
        for kind in ("exact", "empirical", "unresolved"):
            changed = result.to_dict()
            changed["evidence_kind"] = kind
            with (
                self.subTest(kind=kind),
                self.assertRaisesRegex(SerializationError, "model-conditional"),
            ):
                CheckResult.from_dict(changed)

    def test_pipeline_keeps_exact_model_conditional_and_empirical_obligations_distinct(
        self,
    ):
        request, sample = synthetic_fixture()
        build = run_synthetic_pipeline(request, exercised_history(sample), until=7)
        record = build.manager.get("mechanism")
        evidence = {item.id: item.evidence_kind for item in record.obligations}
        self.assertEqual(evidence["behavior_preservation"], EvidenceKind.EXACT)
        self.assertEqual(
            evidence["finite_history_response"], EvidenceKind.MODEL_CONDITIONAL
        )
        self.assertEqual(evidence["molecular_behavior"], EvidenceKind.EMPIRICAL)
        self.assertEqual(
            set(record.discharged), {"behavior_preservation", "finite_history_response"}
        )
        self.assertEqual(
            tuple(item.id for item in build.result.unresolved), ("molecular_behavior",)
        )
        finite = record.checks["finite_history"]["evidence"]
        self.assertEqual(finite["evidence_kind"], "model_conditional")
        self.assertGreater(finite["coverage"][0]["activation_deadlines_checked"], 0)
        self.assertGreater(finite["coverage"][0]["inactive_deadlines_checked"], 0)


if __name__ == "__main__":
    unittest.main()
