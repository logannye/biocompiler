"""Adversarial acceptance and transitive freshness tests for the pass manager."""

from dataclasses import replace
import unittest

from cellweave.artifacts.provenance import SourceLink
from cellweave.compiler.passes import PassResult
from cellweave.compiler.pipeline import (
    ArtifactStatus,
    CheckDecision,
    CheckSpec,
    CompletionProfile,
    NoCandidateFound,
    PassContract,
    PassManager,
    PipelineError,
    ScopedObligation,
)
from cellweave.errors import SerializationError
from cellweave.ir.serialization import fingerprint
from cellweave.ir.stages import Stage
from cellweave.semantics.context import PayloadFormat, TargetContext
from cellweave.verification.evidence import CheckOutcome, EvidenceKind, Obligation


def document(schema, value=1, kind="constant"):
    return {
        "schema_version": schema,
        "nodes": [{"id": "n", "kind": kind, "value": value}],
    }


def accepted(context):
    return CheckDecision(CheckOutcome.PASS, "Independently matched the expected value.")


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.target = TargetContext("synthetic", "1", PayloadFormat.RNA)
        self.input = document("intent.v1")
        self.exact = ScopedObligation(
            "identity", "synthetic", EvidenceKind.EXACT, "Preserve value."
        )
        self.behavioral = ScopedObligation(
            "response",
            "synthetic",
            EvidenceKind.MODEL_CONDITIONAL,
            "Exercise the required response.",
        )
        self.biological = ScopedObligation(
            "biology",
            "full_payload",
            EvidenceKind.EMPIRICAL,
            "Establish biological applicability.",
        )
        self.manager = PassManager(
            target=self.target,
            dependencies={
                "request": fingerprint(self.input),
                "registry": fingerprint("v1"),
            },
            completion_profiles=(
                CompletionProfile(
                    "synthetic",
                    Stage.MECHANISM,
                    "mechanism.v1",
                    ("identity", "response"),
                ),
            ),
        )
        self.manager.add_input(
            "input",
            self.input,
            requirements=("r",),
            obligations=(self.exact, self.biological),
        )
        self.first = PassContract(
            "lower",
            "1",
            Stage.INTENT,
            Stage.BEHAVIOR,
            "intent.v1",
            "behavior.v1",
            "bounded",
            "1",
            ("constant",),
            (CheckSpec("identity_check", EvidenceKind.EXACT, ("identity",)),),
        )
        self.second = PassContract(
            "generate",
            "1",
            Stage.BEHAVIOR,
            Stage.MECHANISM,
            "behavior.v1",
            "mechanism.v1",
            "bounded",
            "1",
            ("constant",),
            (
                CheckSpec(
                    "response_check", EvidenceKind.MODEL_CONDITIONAL, ("response",)
                ),
            ),
            dependency_keys=("registry",),
            introduces=(self.behavioral,),
            requires_observation_map=True,
        )

    def producer(
        self,
        contract,
        value=1,
        kind="constant",
        links=True,
        obligations=(),
        mapping=None,
    ):
        def produce(context):
            return PassResult(
                document(contract.output_schema, value, kind),
                obligations,
                (SourceLink("r", "n", "n", contract.id),) if links else (),
                {"output": "n"} if mapping is None else mapping,
            )

        return produce

    def install_first(self, validator=accepted, **kwargs):
        self.manager.register(
            self.first,
            self.producer(self.first, **kwargs),
            {"identity_check": validator},
        )
        return self.manager.run("lower", "input", "behavior")

    def install_both(self):
        self.install_first()
        self.manager.register(
            self.second, self.producer(self.second), {"response_check": accepted}
        )
        return self.manager.run(
            "generate",
            "behavior",
            "mechanism",
            configuration={"seed": 7, "tie_break": "id"},
        )

    def test_scope_complete_keeps_unresolved_biological_obligation(self):
        record = self.install_both()
        result = self.manager.result("mechanism", scope="synthetic")
        self.assertEqual(result.status, ArtifactStatus.COMPLETE)
        self.assertEqual([x.id for x in result.unresolved], ["biology"])
        self.assertEqual(record.provenance["configuration"]["seed"], 7)
        self.assertEqual(
            set(record.checks["response_check"]["dependencies"]),
            {"request", "registry", "target"},
        )

    def test_scope_requires_final_stage_and_explicit_obligations(self):
        self.install_first()
        self.assertEqual(
            self.manager.result("behavior", scope="synthetic").status,
            ArtifactStatus.PARTIAL,
        )
        with self.assertRaisesRegex(PipelineError, "Unsupported completion"):
            self.manager.result("behavior", scope="full_payload")

    def test_transitive_invalidation_reaches_multiple_stages(self):
        self.install_both()
        self.manager.set_dependency("request", fingerprint("new_request"))
        for identity in ("input", "behavior", "mechanism"):
            with (
                self.subTest(identity=identity),
                self.assertRaisesRegex(PipelineError, "Stale"),
            ):
                self.manager.get(identity)

    def test_registry_model_and_context_changes_invalidate_evidence(self):
        self.manager.set_dependency("model", fingerprint("model1"))
        self.install_both()
        self.manager.set_dependency("model", fingerprint("model2"))
        with self.assertRaisesRegex(PipelineError, "model"):
            self.manager.result("mechanism", scope="synthetic")
        with self.assertRaisesRegex(PipelineError, "Target dependency"):
            self.manager.set_dependency("target", fingerprint("changed_context"))

    def test_changed_pass_invalidates_descendants(self):
        self.install_both()
        changed = replace(self.first, version="2")
        self.manager.register(
            changed, self.producer(changed), {"identity_check": accepted}
        )
        with self.assertRaisesRegex(PipelineError, "pass contract"):
            self.manager.get("mechanism")

    def test_provider_changes_require_version_bump(self):
        self.install_first()
        with self.assertRaisesRegex(PipelineError, "increment"):
            self.manager.register(
                self.first, self.producer(self.first), {"identity_check": accepted}
            )

    def test_failed_unknown_and_unsupported_checks_never_accept(self):
        for outcome in (
            CheckOutcome.FAIL,
            CheckOutcome.UNKNOWN,
            CheckOutcome.UNSUPPORTED,
        ):
            self.setUp()
            record = self.install_first(
                lambda _: CheckDecision(outcome, "Unestablished preservation.")
            )
            self.assertFalse(record.accepted)
            self.assertEqual(record.checks["identity_check"]["outcome"], outcome.value)
            with self.assertRaisesRegex(PipelineError, "not passed"):
                self.manager.get("behavior")

    def test_independent_checker_rejects_internally_consistent_wrong_value(self):
        def verify(context):
            valid = (
                context.output["nodes"][0]["value"]
                == context.input["nodes"][0]["value"]
            )
            return CheckDecision(
                CheckOutcome.PASS if valid else CheckOutcome.FAIL,
                "Checked input value.",
            )

        self.assertFalse(self.install_first(verify, value=9).accepted)

    def test_candidate_cannot_weaken_obligation_or_certify_itself(self):
        forged = Obligation(
            "identity",
            "Only check something easier.",
            EvidenceKind.EXACT,
            ("self_reported_pass",),
        )
        with self.assertRaisesRegex(PipelineError, "authoritative obligation"):
            self.install_first(obligations=(forged,))

    def test_missing_check_provider_and_same_function_are_rejected(self):
        producer = self.producer(self.first)
        with self.assertRaisesRegex(PipelineError, "provider"):
            self.manager.register(self.first, producer, {})
        with self.assertRaisesRegex(PipelineError, "certify itself"):
            self.manager.register(self.first, producer, {"identity_check": producer})

    def test_source_correspondence_does_not_discharge_model_obligation(self):
        self.install_first()
        bad = replace(
            self.second,
            checks=(CheckSpec("response_check", EvidenceKind.EXACT, ("response",)),),
        )
        self.manager.register(bad, self.producer(bad), {"response_check": accepted})
        with self.assertRaisesRegex(PipelineError, "evidence kind"):
            self.manager.run("generate", "behavior", "mechanism")

    def test_missing_source_and_observation_maps_are_rejected(self):
        with self.assertRaisesRegex(PipelineError, "every input requirement"):
            self.install_first(links=False)
        self.setUp()
        self.install_first()
        self.manager.register(
            self.second,
            self.producer(self.second, mapping={}),
            {"response_check": accepted},
        )
        with self.assertRaisesRegex(PipelineError, "observation mapping"):
            self.manager.run("generate", "behavior", "mechanism")

    def test_unknown_source_nodes_are_rejected(self):
        def produce(_):
            return PassResult(
                document("behavior.v1"), (), (SourceLink("r", "wrong", "n", "lower"),)
            )

        self.manager.register(self.first, produce, {"identity_check": accepted})
        with self.assertRaisesRegex(PipelineError, "unknown requirement or node"):
            self.manager.run("lower", "input", "behavior")

    def test_missing_pass_missing_dependencies_order_and_unsupported_operations(self):
        with self.assertRaisesRegex(PipelineError, "Missing pass"):
            self.manager.run("missing", "input", "out")
        self.manager.register(
            self.second, self.producer(self.second), {"response_check": accepted}
        )
        with self.assertRaisesRegex(PipelineError, "ordering"):
            self.manager.run("generate", "input", "out")
        with self.assertRaisesRegex(PipelineError, "Unsupported destination"):
            self.install_first(kind="unimplemented")
        self.setUp()
        self.first = replace(self.first, dependency_keys=("absent_model",))
        with self.assertRaisesRegex(PipelineError, "absent_model"):
            self.install_first()

    def test_skip_stage_and_wrong_target_are_rejected(self):
        with self.assertRaisesRegex(SerializationError, "exactly one"):
            replace(self.first, output_stage=Stage.CONSTRUCT)
        self.first = replace(self.first, targets=(PayloadFormat.DNA,))
        with self.assertRaisesRegex(PipelineError, "requested target"):
            self.install_first()

    def test_deeply_frozen_input_output_configuration_and_records(self):
        record = self.install_both()
        self.input["nodes"][0]["value"] = 9
        self.assertEqual(self.manager.get("input").payload["nodes"][0]["value"], 1)
        with self.assertRaises(TypeError):
            record.payload["nodes"][0]["value"] = 9
        exported = record.to_dict()
        exported["payload"]["nodes"][0]["value"] = 9
        self.assertEqual(record.payload["nodes"][0]["value"], 1)

    def test_root_payload_must_match_request_identity(self):
        with self.assertRaisesRegex(PipelineError, "request identity"):
            self.manager.add_input("wrong", document("intent.v1", 9))

    def test_changed_properties_invalidate_prior_discharges(self):
        self.install_first()
        changed = replace(
            self.second,
            changed_properties=("layout",),
            invalidated_analyses=("identity",),
        )
        self.manager.register(
            changed, self.producer(changed), {"response_check": accepted}
        )
        self.manager.run("generate", "behavior", "mechanism")
        result = self.manager.result("mechanism", scope="synthetic")
        self.assertEqual(result.status, ArtifactStatus.PARTIAL)
        self.assertIn("identity", [x.id for x in result.unresolved])

    def test_dependency_change_during_check_cannot_be_accepted(self):
        def changed(_):
            self.manager.set_dependency("registry", fingerprint("v2"))
            return CheckDecision(
                CheckOutcome.PASS, "Passed before a concurrent change."
            )

        with self.assertRaisesRegex(PipelineError, "Stale"):
            self.install_first(changed)

    def test_no_candidate_is_not_infeasibility_and_has_no_accepted_output(self):
        def no_candidate(_):
            return PassResult(None, (), (), search_status="no_candidate_found")

        self.manager.register(self.first, no_candidate, {"identity_check": accepted})
        with self.assertRaisesRegex(
            NoCandidateFound, "infeasibility is not established"
        ) as raised:
            self.manager.run(
                "lower", "input", "behavior", configuration={"seed": 1, "budget": 2}
            )
        self.assertEqual(raised.exception.configuration["seed"], 1)
        with self.assertRaisesRegex(PipelineError, "Missing artifact"):
            self.manager.get("behavior")

    def test_repeated_runs_have_identical_records(self):
        first = self.install_both().fingerprint
        self.setUp()
        self.assertEqual(first, self.install_both().fingerprint)


if __name__ == "__main__":
    unittest.main()
