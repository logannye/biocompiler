"""Intent planning and CLI inspection must not masquerade as sequence generation."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

import biocompiler as bc
from biocompiler.cli import main


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        therapy = bc.Therapy("planning")
        self.cells = therapy.engineer("responders", cell_type="T_cell")
        self.threshold = therapy.parameter("threshold", type=bc.Level, default=0.25)
        window = therapy.parameter("window", type=bc.Duration)
        active = self.cells.internal.signal("activation") > self.threshold
        self.cells.when(active.held_for(window)).do(self.cells.rest())
        therapy.goal("support_recovery")
        self.program = therapy.freeze()
        self.target = bc.TargetContext("symbolic_context", "1", bc.PayloadFormat.RNA)

    def profile(self, **parameters):
        return bc.BuildProfile(target=self.target, parameters=parameters)

    def test_plan_retains_intent_and_reports_remaining_design_choices(self):
        design = bc.plan(self.program, profile=self.profile())
        self.assertIs(design.program, self.program)
        self.assertFalse(design.ready)
        self.assertEqual(design.bindings["threshold"]["canonical_value"], 0.25)
        self.assertEqual(design.diagnostics, design.unresolved)
        codes = {choice.code for choice in design.unresolved}
        self.assertTrue(
            {
                "unbound_parameter",
                "observation_binding",
                "goal_refinement",
                "molecular_backend_unavailable",
            }.issubset(codes)
        )
        node_ids = {node.id for node in self.program.nodes}
        self.assertTrue(
            all(
                choice.node_id in node_ids
                for choice in design.unresolved
                if choice.node_id
            )
        )

    def test_profile_bindings_override_defaults_without_mutating_intent(self):
        before = self.program.to_json()
        design = bc.plan(
            self.program,
            profile=self.profile(threshold=0.75, window=bc.Duration(2, unit="min")),
        )
        self.assertEqual(design.bindings["threshold"]["canonical_value"], 0.75)
        self.assertEqual(design.bindings["window"]["canonical_value"], 120)
        self.assertEqual(self.program.to_json(), before)
        self.assertFalse(
            any(choice.code == "unbound_parameter" for choice in design.unresolved)
        )
        with self.assertRaises(TypeError):
            design.bindings["threshold"]["canonical_value"] = 0.1

    def test_unknown_and_incompatible_bindings_are_rejected(self):
        with self.assertRaises(ValueError):
            bc.plan(self.program, profile=self.profile(unknown=1))
        with self.assertRaises(TypeError):
            bc.plan(self.program, profile=self.profile(window=5))
        with self.assertRaises(TypeError):
            bc.plan(
                self.program,
                profile=self.profile(threshold=bc.Concentration(1, unit="nM")),
            )

    def test_duration_bindings_must_be_positive_when_used_as_windows(self):
        for value in (0, -1):
            with self.subTest(value=value), self.assertRaises((TypeError, ValueError)):
                bc.plan(
                    self.program,
                    profile=self.profile(window=bc.Duration(value, unit="s")),
                )

    def test_temporal_defaults_are_rechecked_after_override(self):
        therapy = bc.Therapy("late_binding")
        cells = therapy.engineer("responders", cell_type="T_cell")
        duration = therapy.parameter(
            "window", type=bc.Duration, default=bc.Duration(2, unit="s")
        )
        cells.when(cells.internal.signal("activation").high().held_for(duration)).do(
            cells.rest()
        )
        program = therapy.freeze()
        with self.assertRaises((TypeError, ValueError)):
            bc.plan(program, profile=self.profile(window=bc.Duration(0, unit="s")))
        design = bc.plan(program, profile=self.profile(window=bc.Duration(1, unit="s")))
        self.assertEqual(design.bindings["window"]["canonical_value"], 1)

    def test_derived_duration_is_checked_after_binding(self):
        therapy = bc.Therapy("derived_window")
        cells = therapy.engineer("responders", cell_type="T_cell")
        duration = therapy.parameter("window", type=bc.Duration)
        factor = therapy.parameter("factor", type=bc.Level)
        condition = cells.internal.signal("activation").high()
        cells.when(condition.held_for(duration * factor)).do(cells.rest())
        program = therapy.freeze()
        with self.assertRaises((TypeError, ValueError)):
            bc.plan(
                program,
                profile=self.profile(window=bc.Duration(1, unit="s"), factor=-1),
            )
        design = bc.plan(
            program, profile=self.profile(window=bc.Duration(1, unit="s"), factor=2)
        )
        self.assertFalse(design.ready)

    def test_division_by_zero_from_parameter_binding_is_rejected(self):
        therapy = bc.Therapy("divided_window")
        cells = therapy.engineer("responders", cell_type="T_cell")
        duration = therapy.parameter("window", type=bc.Duration)
        factor = therapy.parameter("factor", type=bc.Level)
        condition = cells.internal.signal("activation").high()
        cells.when(condition.held_for(duration / factor)).do(cells.rest())
        with self.assertRaises((TypeError, ValueError)):
            bc.plan(
                therapy.freeze(),
                profile=self.profile(window=bc.Duration(1, unit="s"), factor=0),
            )

    def test_dna_and_rna_target_identity_survive_plan_serialization(self):
        for modality in (bc.PayloadFormat.DNA, bc.PayloadFormat.RNA):
            with self.subTest(modality=modality):
                target = bc.TargetContext("symbolic_context", "7", modality)
                design = bc.plan(self.program, profile=bc.BuildProfile(target=target))
                saved = json.loads(design.to_json())
                self.assertEqual(
                    saved["target"],
                    {
                        "schema_version": "biocompiler.target.v0.1",
                        "context_id": "symbolic_context",
                        "context_version": "7",
                        "payload_format": modality.value,
                        "capabilities": [],
                        "compartments": ["abstract"],
                        "resources": {},
                    },
                )
                self.assertEqual(saved["schema_version"], "biocompiler.plan.v0.3")
                self.assertEqual(saved["program_fingerprint"], self.program.fingerprint)
                self.assertEqual(saved["status"], "unresolved")

    def test_build_profile_copies_parameter_dictionary(self):
        parameters = {"threshold": 0.5}
        profile = bc.BuildProfile(target=self.target, parameters=parameters)
        parameters["threshold"] = 0.9
        self.assertEqual(profile.parameters["threshold"], 0.5)
        with self.assertRaises(TypeError):
            profile.parameters["threshold"] = 0.9

    def test_compile_explains_the_unimplemented_boundary(self):
        design = bc.plan(
            self.program, profile=self.profile(window=bc.Duration(1, unit="s"))
        )
        with self.assertRaisesRegex(bc.CompilationUnavailableError, "not implemented"):
            bc.compile(design)
        with self.assertRaises(TypeError):
            bc.compile(self.program)

    def test_cli_inspects_saved_program_without_executing_authoring_code(self):
        with tempfile.TemporaryDirectory(prefix="biocompiler-test-") as directory:
            path = Path(directory) / "intent.json"
            path.write_text(self.program.to_json(), encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["inspect", str(path)])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue()), self.program.summary())
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["inspect", str(path), "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(
                bc.IntentProgram.from_json(output.getvalue()).fingerprint,
                self.program.fingerprint,
            )

    def test_cli_rejects_invalid_or_missing_artifacts_with_useful_error(self):
        with tempfile.TemporaryDirectory(prefix="biocompiler-test-") as directory:
            path = Path(directory) / "intent.json"
            path.write_text("not json", encoding="utf-8")
            for candidate in (path, path.with_name("missing.json")):
                error = io.StringIO()
                with self.subTest(path=candidate), redirect_stderr(error):
                    code = main(["inspect", str(candidate)])
                self.assertEqual(code, 2)
                self.assertIn("biocompiler:", error.getvalue())


if __name__ == "__main__":
    unittest.main()
