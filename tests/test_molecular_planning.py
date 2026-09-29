"""M9 extension requests stay inspectable without being silently approximated."""

import unittest

import cellweave as cw


class MolecularPlanningTests(unittest.TestCase):
    def setUp(self):
        self.therapy = cw.Therapy("extension_obligations")
        self.cells = self.therapy.engineer("responder", cell_type="T_cell")
        self.signal = self.cells.environment.signal("measurement", type=cw.Level)
        self.target = cw.TargetContext("declared_context", "1", cw.PayloadFormat.RNA)
        self.profile = cw.BuildProfile(self.target)

    def test_all_requested_extension_obligations_survive_plan_and_compile(self):
        curve = self.therapy.parameter(
            "response",
            type=cw.Curve[cw.Level, cw.ProductionRate],
            default=cw.Curve(
                points=((0, cw.ProductionRate(0)), (1, cw.ProductionRate(1))),
                input=cw.Level,
                output=cw.ProductionRate,
                interpolation="linear",
                extrapolation="clamp",
            ),
        )
        self.cells.when(self.signal > 0).do(
            self.cells.secrete("requested_product", rate=curve(self.signal))
        )
        output = self.cells.secretion("controlled", product="requested_product")
        self.cells.regulate(
            "controller",
            observed=self.signal,
            target=cw.Interval(0.2, 0.4),
            actuator=output.rate,
            effect="decrease_observed",
        )
        self.cells.when(
            self.signal.integrated(over=cw.Duration(1)) > self.signal * cw.Duration(1)
        ).do(self.cells.rest())
        channel = self.therapy.channel("communication", scope="local")
        self.cells.when(self.cells.receives(channel)).do(
            self.cells.migrate_toward(self.cells.environment.gradient(channel))
        )
        source = self.therapy.freeze()
        before = source.to_json()
        design = cw.plan(source, profile=self.profile)
        required = {
            "quantitative_profile_unavailable",
            "continuous_profile_unavailable",
            "feedback_profile_unavailable",
            "uncertainty_profile_unavailable",
            "spatial_profile_unavailable",
            "population_profile_unavailable",
        }
        choices = [d for d in design.diagnostics if d.code in required]
        self.assertEqual({d.code for d in choices}, required)
        self.assertTrue(all(d.node_id in {n.id for n in source.nodes} for d in choices))
        self.assertEqual(source.to_json(), before)
        with self.assertRaises(cw.CompilationUnavailableError) as captured:
            cw.compile(design)
        self.assertEqual(captured.exception.diagnostics, design.diagnostics)
        request = design.freeze_request(artifact_scope="complete_payload")
        with self.assertRaises(cw.CompilationUnavailableError) as captured:
            cw.compile(cw.BuildRequest.from_json(request.to_json()))
        codes = {d.code for d in captured.exception.diagnostics}
        self.assertTrue(required <= codes)
        self.assertIn("complete_payload_not_promoted", codes)
        self.assertIn("molecular_behavior_unestablished", codes)

    def test_supported_scalar_and_discrete_semantics_are_not_reclassified(self):
        state = self.cells.state("phase", values=("idle", "active"), initial="idle")
        self.cells.when((self.signal + 1 > 2).held_for(cw.Duration(1))).do(
            state.set("active"), self.cells.report("active")
        )
        source = self.therapy.freeze()
        design = cw.plan(source, profile=self.profile)
        self.assertFalse(
            any("profile_unavailable" in d.code for d in design.diagnostics)
        )
        request = design.freeze_request()
        behavior = cw.lower_to_behavior(request)
        cw.verify_lowering(request, behavior)
        with self.assertRaises(cw.CompilationUnavailableError) as captured:
            cw.compile(request)
        self.assertEqual(
            {d.code for d in captured.exception.diagnostics},
            {"molecular_behavior_unestablished"},
        )


if __name__ == "__main__":
    unittest.main()
