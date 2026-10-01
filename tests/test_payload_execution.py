"""Source execution remains exact, bounded and explicit across richer contracts."""
from __future__ import annotations

import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.compiler.behavior import lower_to_behavior, verify_lowering
from biocompiler.compiler.request import BuildRequest
from biocompiler.errors import BiocompilerError, EvaluationError, LoweringVerificationError, TypeMismatchError
from biocompiler.ir.behavior import BehaviorProgram, BEHAVIOR_V2
from biocompiler.semantics.evaluator import InputFrame, SignalSample, evaluate
from biocompiler.semantics.payload_execution import SourceExecutionManifest, derive_source_execution


def source(therapy, *, step=None):
    constraints = {} if step is None else {"execution": {"integral_step": bc.Duration(step).to_dict()}}
    return BuildRequest.freeze(therapy.freeze(), behavior_profile=BEHAVIOR_V2,
                               implementation_constraints=constraints)


def model():
    therapy = bc.Therapy("execution-contract")
    cells = therapy.engineer("responder", cell_type="abstract_cell")
    return therapy, cells


def at(result, time):
    return next(frame for frame in result.frames if frame.time == time)


def active(frame, action):
    return tuple(item for item in frame.actions if item.action_id == action.node_id)


class ExecutionManifestTests(unittest.TestCase):
    def test_full_ledger_retains_unreachable_source_and_unsupported_obligations(self):
        therapy, cells = model()
        cells.state("unused", values=("idle", "ready"), initial="idle")
        therapy.goal("unimplemented-goal")
        request = source(therapy)
        manifest = derive_source_execution(request)
        self.assertFalse(manifest.complete)
        self.assertIsNone(manifest.behavior)
        self.assertEqual([row["source_node_ids"][0] for row in manifest.ledger[:-1]],
                         [node.id for node in request.intent.nodes])
        self.assertEqual(manifest.to_dict()["ledger"][-1]["semantics"], request.to_dict())
        self.assertTrue(manifest.diagnostics[0].source_node_ids)

    def test_import_is_historical_and_never_calls_the_producer(self):
        therapy, cells = model()
        signal = cells.environment.signal("go")
        cells.when(signal.present()).do(cells.rest())
        manifest = derive_source_execution(source(therapy))
        with patch("biocompiler.semantics.payload_execution.derive_source_execution", side_effect=AssertionError):
            imported = SourceExecutionManifest.from_dict(manifest.to_dict())
        self.assertEqual(imported.to_dict(), manifest.to_dict())
        self.assertTrue(verify_lowering(imported.build_request, imported.behavior).passed)

    def test_state_assignments_are_level_effects_and_preserve_typed_values(self):
        therapy, cells = model()
        signal = cells.environment.signal("go")
        state = cells.state("phase", values=(False, 0, "ready"), initial=False)
        cells.when(signal.present()).do(state.set(0))
        manifest = derive_source_execution(source(therapy))
        self.assertTrue(manifest.complete)
        self.assertEqual(manifest.outputs[0].activation, "level")
        self.assertIs(type(manifest.states[0]["assignments"][0]["value"]), int)
        self.assertEqual(manifest.states[0]["declaration"]["attributes"]["initial"], False)


class StatefulExecutionTests(unittest.TestCase):
    def test_prime_act_recover_timeout_reset_and_shutdown_precedence(self):
        therapy, cells = model()
        phase = cells.state("phase", values=("idle", "primed", "active", "recover", "off"), initial="idle")
        prime, act, reset, stop = (cells.environment.signal("prime"), cells.environment.signal("act"), cells.environment.signal("reset"), cells.environment.signal("stop"))
        permitted = ~stop.present() & ~reset.present()
        cells.when(stop.present()).do(phase.set("off"))
        cells.when(~stop.present() & reset.present()).do(phase.set("idle"))
        cells.when(permitted & phase.is_("idle") & prime.present()).do(phase.set("primed"))
        cells.when(permitted & phase.is_("primed") & act.present()).do(phase.set("active"))
        cells.when(permitted & phase.is_("active").held_for(bc.Duration(2))).do(phase.set("recover"))
        cells.when(permitted & phase.is_("recover").held_for(bc.Duration(3))).do(phase.set("idle"))
        output = cells.present("ARTIFICIAL")
        cells.when(permitted & phase.is_("active")).do(output)
        def sample(time, p=False, a=False, r=False, s=False):
            return InputFrame(time, {ref.node_id: SignalSample(present=value)
                                     for ref, value in zip((prime, act, reset, stop), (p, a, r, s))})
        manifest = derive_source_execution(source(therapy))
        self.assertTrue(manifest.complete)
        result = evaluate(manifest.behavior, [sample(0), sample(1,p=True), sample(2,a=True),
                                             sample(3), sample(8,r=True), sample(9,p=True),
                                             sample(10,a=True), sample(11,r=True,s=True), sample(12)])
        self.assertEqual([at(result,t).states[phase.node_id] for t in (0,1,2,4,7,8,9,10,11,12)],
                         ["idle","primed","active","recover","idle","idle","primed","active","off","off"])
        self.assertTrue(active(at(result,2),output))
        self.assertFalse(active(at(result,11),output))

    def test_concurrent_incompatible_writes_fail_under_declared_policy(self):
        therapy, cells = model()
        signal = cells.environment.signal("go")
        state = cells.state("phase", values=("idle","a","b"), initial="idle")
        cells.when(signal.present()).do(state.set("a"), state.set("b"))
        manifest = derive_source_execution(source(therapy))
        self.assertTrue(manifest.complete)
        with self.assertRaisesRegex(BiocompilerError, "[Cc]onflict"):
            evaluate(manifest.behavior,[InputFrame(0,{signal.node_id:SignalSample(present=True)})])


class IntegralExecutionTests(unittest.TestCase):
    def build_budget(self, *, step=1, window=10):
        therapy, cells = model()
        rate = cells.environment.signal("observed_activity", type=bc.ProductionRate)
        max_rate = therapy.parameter("maximum", type=bc.ProductionRate, default=bc.ProductionRate(2))
        budget_duration = therapy.parameter("budget_duration", type=bc.Duration, default=bc.Duration(2))
        budget = max_rate * budget_duration
        permitted = rate.integrated(over=bc.Duration(window)) < budget
        low, saturated = cells.secrete("ARTIFICIAL", rate=rate), cells.secrete("ARTIFICIAL",rate=max_rate)
        cells.when(permitted & (rate <= max_rate)).do(low)
        cells.when(permitted & (rate > max_rate)).do(saturated)
        return source(therapy,step=step), rate, low, saturated

    def test_integrated_budget_drives_saturated_output_and_rolling_recovery(self):
        request, rate, low, high = self.build_budget(window=3)
        manifest = derive_source_execution(request)
        self.assertTrue(manifest.complete, manifest.diagnostics)
        result = evaluate(manifest.behavior,[InputFrame(0,{rate.node_id:1}),InputFrame(1,{rate.node_id:3}),
                                              InputFrame(2,{rate.node_id:0})],until=5)
        self.assertEqual(active(at(result,0),low)[0].values["rate"],1)
        self.assertEqual(active(at(result,1),high)[0].values["rate"],2)
        self.assertFalse(at(result,2).actions)
        self.assertFalse(at(result,3).actions)
        self.assertTrue(active(at(result,4),low))
        self.assertEqual(manifest.behavior.policies["integral_threshold_claim"],
                         "sampled_events_only_not_continuous_threshold_detection")

    def test_input_and_timer_events_observe_exact_area_between_grid_points(self):
        therapy, cells = model()
        signal = cells.environment.signal("activity")
        gate = cells.environment.signal("gate")
        below = signal.integrated(over=bc.Duration(10)) < bc.Duration(1.5)
        output = cells.rest()
        cells.when(below).do(output)
        cells.when(gate.present().held_for(bc.Duration(1.5))).do(cells.report("timer"))
        behavior = lower_to_behavior(source(therapy,step=2))
        result = evaluate(behavior,[InputFrame(0,{signal.node_id:1,gate.node_id:SignalSample(present=True)}),
                                   InputFrame(.5,{signal.node_id:1,gate.node_id:SignalSample(present=True)})],until=2)
        self.assertEqual([frame.time for frame in result.frames],[0,.5,1.5,2])
        self.assertTrue(active(at(result,.5),output))
        self.assertFalse(active(at(result,1.5),output))

    def test_sampling_policy_never_claims_continuous_threshold_detection(self):
        request, rate, low, high = self.build_budget(step=3)
        result = evaluate(lower_to_behavior(request),[InputFrame(0,{rate.node_id:3})],until=3)
        self.assertEqual([frame.time for frame in result.frames],[0,3])
        self.assertTrue(active(at(result,0),high))
        self.assertFalse(at(result,3).actions)

    def test_grid_is_source_authority_and_tampering_fails_lowering_check(self):
        request, *_ = self.build_budget()
        document = lower_to_behavior(request).to_dict()
        document["policies"]["integral_step"] = bc.Duration(2).to_dict()
        tampered = BehaviorProgram.from_dict(document)
        with self.assertRaises(LoweringVerificationError):
            verify_lowering(request,tampered)

    def test_missing_grid_legacy_profile_negative_values_and_excessive_grid_reject(self):
        request, rate, *_ = self.build_budget()
        old = BuildRequest.freeze(request.intent)
        self.assertFalse(derive_source_execution(old).complete)
        missing = BuildRequest.freeze(request.intent,behavior_profile=BEHAVIOR_V2)
        self.assertFalse(derive_source_execution(missing).complete)
        behavior = lower_to_behavior(request)
        with self.assertRaisesRegex(EvaluationError,"nonnegative"):
            evaluate(behavior,[InputFrame(0,{rate.node_id:-1})])
        with self.assertRaisesRegex(EvaluationError,"10000"):
            evaluate(behavior,[InputFrame(0,{rate.node_id:0})],until=10000)

    def test_units_are_checked_before_execution(self):
        therapy,cells=model()
        rate=cells.environment.signal("activity",type=bc.ProductionRate)
        with self.assertRaises(TypeMismatchError):
            _ = rate.integrated(over=bc.Duration(10)) < bc.Duration(1)

    def test_unimplemented_integral_domains_retain_exact_source_diagnostics(self):
        for contact in (False, True):
            with self.subTest(contact=contact):
                therapy,cells=model()
                quantity = cells.contact.marker("A") if contact else cells.environment.signal("A") + bc.Level(1)
                area = quantity.integrated(over=bc.Duration(2))
                cells.when(area >= area).do(cells.rest())
                manifest = derive_source_execution(source(therapy,step=1))
                self.assertIsNone(manifest.behavior)
                self.assertEqual(manifest.diagnostics[0].category, "unsupported_semantics")
                self.assertEqual(manifest.diagnostics[0].source_node_ids, (area.node_id,))


class ChannelExecutionTests(unittest.TestCase):
    def test_emitter_and_receiver_are_separate_roles_with_explicit_observations(self):
        therapy = bc.Therapy("channels")
        sender = therapy.engineer("sender",cell_type="abstract_cell")
        receiver = therapy.engineer("receiver",cell_type="abstract_cell")
        channel = therapy.channel("ARTIFICIAL",scope="declared_local",type=bc.Level)
        trigger = sender.environment.signal("go")
        emission = sender.emit(channel,value=bc.Level(3))
        sender.when(trigger.present()).do(emission)
        observation=receiver.sense(channel)
        output=receiver.rest()
        receiver.when(observation >= bc.Level(2)).do(output)
        manifest=derive_source_execution(source(therapy))
        self.assertTrue(manifest.complete,manifest.diagnostics)
        self.assertEqual(manifest.channels[0]["transport"],"requires_explicit_architecture_contract")
        self.assertEqual(manifest.channels[0]["receivers"][0]["observation_id"],observation.node_id)
        self.assertIn(observation.node_id,manifest.build_request.runtime_observations)
        emitted=evaluate(manifest.behavior,[InputFrame(0,{trigger.node_id:SignalSample(present=True)})],role="sender")
        self.assertEqual(active(at(emitted,0),emission)[0].values["value"],3)
        self.assertEqual(active(at(emitted,0),emission)[0].attributes["channel_id"],channel.node_id)
        with self.assertRaisesRegex(EvaluationError,"Missing observation"):
            evaluate(manifest.behavior,[InputFrame(0)],role="receiver")
        received=evaluate(manifest.behavior,[InputFrame(0,{observation.node_id:0}),InputFrame(1,{observation.node_id:3})],role="receiver")
        self.assertFalse(at(received,0).actions)
        self.assertTrue(active(at(received,1),output))
        self.assertTrue(verify_lowering(manifest.build_request,manifest.behavior).passed)

    def test_qualitative_channel_presence_is_explicit_not_numeric_inference(self):
        therapy,cells=model()
        channel=therapy.channel("ARTIFICIAL",scope="local")
        condition=cells.receives(channel)
        cells.when(condition).do(cells.rest())
        observation=therapy.freeze().find(kind="channel_observation")[0]
        behavior=lower_to_behavior(source(therapy))
        with self.assertRaisesRegex(EvaluationError,"present"):
            evaluate(behavior,[InputFrame(0,{observation.id:3})])
        result=evaluate(behavior,[InputFrame(0,{observation.id:SignalSample(present=True)})])
        self.assertTrue(result.frames[0].actions)


if __name__ == "__main__":
    unittest.main()
