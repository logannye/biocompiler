"""Delivery authority, independent clocks and conservative dependency checks."""

from contextlib import redirect_stdout
from dataclasses import FrozenInstanceError, replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import cellweave as cw
from cellweave.cli import main as cli_main
from examples.human_deployment import (
    PLATFORM_SOURCE,
    co_payload_fixture,
    make_human_deployment,
    seconds,
    with_fixture_bounds,
)


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.unknown = make_human_deployment()
        self.request = with_fixture_bounds(self.unknown)
        self.contract = self.request.deployment

    def change(self, **changes):
        return replace(self.request, deployment=replace(self.contract, **changes))

    def timing(self, **changes):
        return self.change(timing=replace(self.contract.timing, **changes))

    def test_roundtrip_preserves_target_behavior_source_and_platform_pin(self):
        restored = cw.HumanDeploymentRequest.from_json(self.request.to_json())
        self.assertEqual(restored.fingerprint, self.request.fingerprint)
        self.assertEqual(
            restored.behavior_request.to_dict(), self.request.behavior_request.to_dict()
        )
        self.assertEqual(
            restored.deployment.platform.identity.content_fingerprint,
            hashlib.sha256(PLATFORM_SOURCE).hexdigest(),
        )
        artifacts = (
            self.contract,
            self.contract.platform,
            self.contract.exposures[0],
            self.contract.timing,
            co_payload_fixture(),
        )
        for item in artifacts:
            with self.subTest(item=type(item)):
                self.assertEqual(type(item).from_json(item.to_json()), item)

    def test_required_fields_unknown_versions_and_self_certification_rejected(self):
        artifacts = (
            self.request,
            self.contract,
            self.contract.platform,
            self.contract.exposures[0],
            self.contract.timing,
            co_payload_fixture(),
        )
        for artifact in artifacts:
            for key in artifact.to_dict():
                data = artifact.to_dict()
                del data[key]
                with (
                    self.subTest(artifact=type(artifact), missing=key),
                    self.assertRaises(cw.SerializationError),
                ):
                    type(artifact).from_dict(data)
            for mutation in ({"schema_version": "future"}, {"validated": True}):
                with (
                    self.subTest(mutation=mutation),
                    self.assertRaises(cw.SerializationError),
                ):
                    type(artifact).from_dict({**artifact.to_dict(), **mutation})

    def test_duplicate_json_nonfinite_and_invalid_unicode_fail(self):
        document = self.request.to_json()
        with self.assertRaises(cw.SerializationError):
            cw.HumanDeploymentRequest.from_json(
                document.replace(
                    '"intracellular_destination": "cytoplasm"',
                    '"intracellular_destination": "cytoplasm", "intracellular_destination": "nucleus"',
                )
            )
        with self.assertRaises(cw.SerializationError):
            replace(self.contract, id="bad\ud800")
        data = self.contract.timing.to_dict()
        data["behavior_start"]["value"] = float("nan")
        with self.assertRaises(cw.SerializationError):
            cw.ExpressionTiming.from_dict(data)

    def test_delivery_targeting_cannot_be_relabelled_as_recognition(self):
        data = self.contract.to_dict()
        data["delivery_targeting_is_disease_recognition"] = True
        with self.assertRaises(cw.SerializationError):
            cw.DeploymentContract.from_dict(data)
        changed = self.change(
            platform=replace(
                self.contract.platform,
                recipient_targeting=replace(
                    self.contract.platform.recipient_targeting,
                    description="Different delivery target declaration",
                ),
            )
        )
        self.assertEqual(
            changed.behavior_request.contract.predicate,
            self.request.behavior_request.contract.predicate,
        )
        self.assertNotEqual(changed.fingerprint, self.request.fingerprint)
        self.assertIn(
            "deployment.platform.recipient_targeting",
            cw.check_deployment(changed).unresolved_evidence,
        )

    def test_target_role_and_modality_must_match(self):
        for changes in (
            {"target_fingerprint": "0" * 64},
            {"recipient_role": "unrelated"},
            {
                "platform": replace(
                    self.contract.platform, payload_format=cw.PayloadFormat.DNA
                )
            },
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises(cw.SerializationError),
            ):
                self.change(**changes)

    def test_population_inclusion_and_exclusion_cannot_drift(self):
        for key in ("intended_population", "excluded_population"):
            with self.subTest(key=key), self.assertRaises(cw.SerializationError):
                self.change(
                    **{
                        key: replace(
                            getattr(self.contract, key),
                            description="A different population",
                        )
                    }
                )

    def test_undeclared_compartments_fail_in_every_inventory(self):
        variants = (
            {"intracellular_destination": "nucleus"},
            {
                "exposures": (
                    replace(self.contract.exposures[0], compartment="unknown"),
                )
            },
            {"co_payloads": (replace(co_payload_fixture(), destination="unknown"),)},
        )
        for changes in variants:
            with (
                self.subTest(changes=changes),
                self.assertRaises(cw.SerializationError),
            ):
                self.change(**changes)

    def test_declared_but_unimplemented_destination_is_unsupported(self):
        request = self.change(intracellular_destination="extracellular")
        result = cw.check_deployment(request)
        self.assertEqual(result.compatibility, "unsupported")
        self.assertIn("deployment_destination_profile_unsupported", result.diagnostics)

    def test_dna_nuclear_profile_is_distinct_from_rna_cytoplasmic(self):
        target = replace(
            self.request.target,
            payload_format=cw.PayloadFormat.DNA,
            compartments=(*self.request.target.compartments, "nucleus"),
        )
        behavior = replace(
            self.request.behavior_request,
            build_request=replace(self.request.build_request, target=target),
        )
        contract = replace(
            self.contract,
            target_fingerprint=target.fingerprint,
            platform=replace(
                self.contract.platform, payload_format=cw.PayloadFormat.DNA
            ),
            intracellular_destination="nucleus",
        )
        request = cw.HumanDeploymentRequest(behavior, contract)
        self.assertEqual(cw.check_deployment(request).compatibility, "pass")
        wrong = replace(
            request, deployment=replace(contract, intracellular_destination="cytoplasm")
        )
        self.assertEqual(cw.check_deployment(wrong).compatibility, "unsupported")

    def test_missing_and_negative_exposure_are_not_unlimited(self):
        with self.assertRaises(cw.SerializationError):
            self.change(exposures=())
        with self.assertRaises(cw.SerializationError):
            replace(self.contract.exposures[0], domain=cw.ValueDomain.interval(-1, 1))
        with self.assertRaises(cw.SerializationError):
            replace(self.contract.exposures[0], domain=cw.ValueDomain.boolean())
        result = cw.check_deployment(
            replace(
                self.request,
                deployment=replace(
                    self.contract, exposures=self.unknown.deployment.exposures
                ),
            )
        )
        self.assertEqual(result.compatibility, "unknown")
        self.assertIn("deployment_exposure_bounds_unknown", result.diagnostics)

    def test_exposure_window_has_explicit_origin_and_extent(self):
        for window in (seconds(1, 2), seconds(0, 0), seconds(-1, 2)):
            with self.subTest(window=window), self.assertRaises(cw.SerializationError):
                self.change(exposure_window=window)
        # Expression may outlast extracellular exposure; the schema infers no decay law.
        self.assertEqual(cw.check_deployment(self.request).compatibility, "pass")

    def test_unknown_expression_is_not_zero_or_unbounded(self):
        self.assertEqual(cw.check_deployment(self.unknown).compatibility, "unknown")
        for key in ("onset", "duration"):
            with self.subTest(key=key):
                result = cw.check_deployment(
                    self.timing(**{key: None, "unknown_reason": "Data absent"})
                )
                self.assertEqual(result.compatibility, "unknown")
                self.assertIn("expression_window_unknown", result.diagnostics)
        with self.assertRaises(cw.SerializationError):
            replace(self.contract.timing, onset=None)
        with self.assertRaises(cw.SerializationError):
            replace(self.contract.timing, unknown_reason="unexplained")

    def test_timing_requires_typed_nonnegative_onset_and_positive_duration(self):
        for changes in (
            {"onset": seconds(-1, 2)},
            {"duration": seconds(0, 5)},
            {"behavior_start": cw.Duration(-1)},
            {"behavior_start": cw.Level(2)},
            {"duration": cw.Interval(1, 2)},
        ):
            with (
                self.subTest(changes=changes),
                self.assertRaises(cw.SerializationError),
            ):
                self.timing(**changes)

    def test_latest_onset_must_precede_behavior_zero(self):
        result = cw.check_deployment(self.timing(onset=seconds(1, 3)))
        self.assertEqual(result.compatibility, "fail")
        self.assertIn("expression_onset_after_behavior_start", result.diagnostics)

    def test_earliest_loss_not_best_case_duration_must_cover_horizon(self):
        result = cw.check_deployment(self.timing(duration=seconds(10, 100)))
        self.assertEqual(result.compatibility, "fail")
        self.assertIn("expression_duration_does_not_cover_behavior", result.diagnostics)
        self.assertEqual(cw.check_deployment(self.request).compatibility, "pass")

    def test_expression_delay_is_not_secretion_activation_delay(self):
        behavior = self.request.behavior_request
        slowed = replace(
            behavior,
            contract=replace(
                behavior.contract,
                response=replace(
                    behavior.contract.response, max_activation_delay=cw.Duration(4)
                ),
            ),
        )
        late = replace(self.timing(onset=seconds(1, 3)), behavior_request=slowed)
        result = cw.check_deployment(late)
        self.assertEqual(result.compatibility, "fail")
        self.assertIn("expression_onset_after_behavior_start", result.diagnostics)

    def test_longer_behavior_horizon_invalidates_old_assessment(self):
        old = cw.check_deployment(self.request)
        behavior = replace(
            self.request.behavior_request,
            contract=replace(
                self.request.behavior_request.contract, horizon=cw.Duration(11)
            ),
        )
        changed = replace(self.request, behavior_request=behavior)
        self.assertFalse(old.is_current(changed))
        self.assertEqual(cw.check_deployment(changed).compatibility, "fail")

    def test_unknown_duration_cannot_hide_known_late_onset(self):
        result = cw.check_deployment(
            self.timing(
                onset=seconds(3, 4), duration=None, unknown_reason="Unknown duration"
            )
        )
        self.assertEqual(result.compatibility, "fail")
        self.assertIn("expression_window_unknown", result.diagnostics)

    def test_closed_boundary_and_explicit_unit_conversions(self):
        timing = replace(
            self.contract.timing,
            onset=cw.Interval(
                cw.Duration(1 / 60, unit="min"),
                cw.Duration(2 / 60, unit="min"),
                type=cw.Duration,
            ),
        )
        result = cw.check_deployment(self.change(timing=timing))
        self.assertEqual(result.compatibility, "pass")
        shifted = cw.check_deployment(self.timing(behavior_start=cw.Duration(2.1)))
        self.assertEqual(shifted.compatibility, "fail")

    def test_every_co_payload_remains_unsupported_even_when_cited(self):
        request = self.change(co_payloads=(co_payload_fixture(),))
        result = cw.check_deployment(request)
        self.assertEqual(result.compatibility, "unsupported")
        self.assertIn("same_cell_co_payload_delivery_unsupported", result.diagnostics)
        self.assertEqual(
            request.deployment.co_payloads[0].to_dict()["recipient_scope"],
            "same_selected_recipient_cell",
        )
        with self.assertRaises(cw.CompilationUnavailableError) as error:
            cw.compile(request)
        self.assertIn(
            "same_cell_co_payload_delivery_unsupported",
            {item.code for item in error.exception.diagnostics},
        )

    def test_co_payload_cannot_be_downgraded_to_optional_or_same_patient(self):
        item = co_payload_fixture()
        for change in ({"required": False}, {"recipient_scope": "same_patient"}):
            with self.assertRaises(cw.SerializationError):
                cw.CoPayloadRequirement.from_dict({**item.to_dict(), **change})
        for overlap in (seconds(-1, 1), seconds(1, 1)):
            with self.assertRaises(cw.SerializationError):
                replace(item, required_overlap=overlap)

    def test_conflict_precedes_unsupported_but_all_diagnostics_survive(self):
        request = self.change(
            co_payloads=(co_payload_fixture(),),
            timing=replace(self.contract.timing, duration=seconds(1, 2)),
            exposures=self.unknown.deployment.exposures,
        )
        result = cw.check_deployment(request)
        self.assertEqual(result.compatibility, "fail")
        self.assertEqual(len(result.diagnostics), 3)

    def test_collections_are_frozen_canonical_and_unique(self):
        exposures = [
            self.contract.exposures[0],
            replace(
                self.contract.exposures[0], id="another", observable="another_exposure"
            ),
        ]
        co_payloads = [co_payload_fixture()]
        contract = replace(self.contract, exposures=exposures, co_payloads=co_payloads)
        expected = contract.fingerprint
        reverse = replace(contract, exposures=list(reversed(exposures)))
        exposures.clear()
        co_payloads.clear()
        self.assertEqual(contract.fingerprint, expected)
        self.assertEqual(reverse.fingerprint, expected)
        with self.assertRaises(FrozenInstanceError):
            contract.id = "changed"
        with self.assertRaises(cw.SerializationError):
            self.change(
                exposures=(
                    self.contract.exposures[0],
                    replace(self.contract.exposures[0], id="alias"),
                )
            )
        for key, items in (
            ("exposures", contract.exposures),
            ("co_payloads", contract.co_payloads),
        ):
            with self.assertRaises(cw.SerializationError):
                replace(contract, **{key: items * 2})

    def test_platform_exposure_destination_and_evidence_changes_change_identity(self):
        variants = (
            {
                "platform": replace(
                    self.contract.platform,
                    identity=replace(
                        self.contract.platform.identity, content_fingerprint="d" * 64
                    ),
                )
            },
            {"exposure_window": seconds(0, 2)},
            {
                "exposures": (
                    replace(
                        self.contract.exposures[0], domain=cw.ValueDomain.interval(0, 2)
                    ),
                )
            },
            {
                "unintended_recipients": replace(
                    self.contract.unintended_recipients,
                    limitations="Another uncertainty",
                )
            },
            {"timing": replace(self.contract.timing, duration=seconds(12, 15))},
            {"co_payloads": (co_payload_fixture(),)},
        )
        result = cw.check_deployment(self.request)
        for change in variants:
            with self.subTest(change=change):
                changed = self.change(**change)
                self.assertNotEqual(changed.fingerprint, self.request.fingerprint)
                self.assertFalse(result.is_current(changed))

    def test_unknown_evidence_references_rejected_without_promoting_citations(self):
        claim = replace(
            self.contract.unintended_recipients,
            basis="cited",
            evidence_ids=("delivery_source",),
        )
        with self.assertRaises(cw.SerializationError):
            self.change(unintended_recipients=claim)
        evidence = cw.TargetEvidence(
            "delivery_source",
            self.contract.platform.identity,
            9606,
            "human_in_vivo",
            "Caller-declared fixture context, not an experiment",
            "fixture",
            "Unvalidated",
        )
        target = replace(
            self.request.target,
            human_target=replace(
                self.request.target.human_target, evidence=(evidence,)
            ),
        )
        behavior = replace(
            self.request.behavior_request,
            build_request=replace(self.request.build_request, target=target),
        )
        contract = replace(
            self.contract,
            target_fingerprint=target.fingerprint,
            unintended_recipients=claim,
            co_payloads=(replace(co_payload_fixture(), support=claim),),
        )
        request = cw.HumanDeploymentRequest(behavior, contract)
        result = cw.check_deployment(request)
        self.assertEqual(result.compatibility, "unsupported")
        self.assertIn("deployment.unintended_recipients", result.unresolved_evidence)
        self.assertEqual(result.to_dict()["biological_applicability"], "unestablished")

    def test_changed_target_cannot_reuse_delivery_authority(self):
        target = replace(self.request.target, context_version="new")
        behavior = replace(
            self.request.behavior_request,
            build_request=replace(self.request.build_request, target=target),
        )
        with self.assertRaises(cw.SerializationError):
            replace(self.request, behavior_request=behavior)

    def test_missing_delivery_is_reported_before_human_compilation(self):
        behavior = self.request.behavior_request
        plan = cw.plan(
            behavior.build_request.intent, profile=cw.BuildProfile(behavior.target)
        )
        self.assertIn(
            "deployment_contract_missing", {item.code for item in plan.diagnostics}
        )
        for design in (behavior, behavior.build_request):
            with self.assertRaises(cw.CompilationUnavailableError) as error:
                cw.compile(design)
            self.assertIn(
                "deployment_contract_missing",
                {item.code for item in error.exception.diagnostics},
            )

    def test_compatible_declarations_still_block_human_mechanism_selection(self):
        result = cw.check_deployment(self.request)
        self.assertEqual(result.compatibility, "pass")
        self.assertEqual(result.to_dict()["mechanism_selection"], "blocked")
        with self.assertRaises(cw.CompilationUnavailableError) as error:
            cw.compile(self.request)
        codes = {item.code for item in error.exception.diagnostics}
        self.assertNotIn("deployment_contract_missing", codes)
        self.assertIn("deployment_empirical_support_unestablished", codes)
        self.assertIn("human_behavior_empirical_support_unestablished", codes)

    def test_imported_assessment_is_not_independent_authority(self):
        result = cw.check_deployment(self.request)
        self.assertEqual(cw.DeploymentAssessment.from_json(result.to_json()), result)
        for changes in (
            {"mechanism_selection": "admitted"},
            {"biological_applicability": "validated"},
            {"scope": "human_delivery"},
            {"checker": "custom"},
        ):
            with self.assertRaises(cw.SerializationError):
                cw.DeploymentAssessment.from_dict({**result.to_dict(), **changes})
        with self.assertRaises(cw.SerializationError):
            cw.check_deployment(result)

    def test_cli_reports_compatibility_separately_from_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "deployment.json"
            for artifact in (self.request, cw.check_deployment(self.request)):
                path.write_text(artifact.to_json())
                stream = io.StringIO()
                with redirect_stdout(stream):
                    self.assertEqual(cli_main(["inspect", str(path)]), 0)
                summary = json.loads(stream.getvalue())
                self.assertEqual(summary["fingerprint"], artifact.fingerprint)
                self.assertTrue(summary["unresolved_evidence"])
                if isinstance(artifact, cw.DeploymentAssessment):
                    self.assertIn("blocked", summary["inspection"])


if __name__ == "__main__":
    unittest.main()
