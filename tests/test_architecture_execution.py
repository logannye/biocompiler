"""Coupled source execution uses checked transport, never hand-authored receiver values."""
from dataclasses import replace
import unittest

import biocompiler as bc
from biocompiler.compiler.payload_architecture import compile_payload_architecture
from biocompiler.errors import EvaluationError
from biocompiler.ir.intent import thaw_json
from biocompiler.semantics.architecture_execution import evaluate_payload_architecture
from biocompiler.semantics.evaluator import InputFrame, SignalSample
from examples.payload_architectures import make_architecture_request


def histories(request, *, combined=False):
    nodes=request.source.intent.nodes
    roles={node.attributes["name"]:node.id for node in nodes if node.kind=="role"}
    observations={(node.role,node.attributes["name"]):node.id for node in nodes if node.kind=="signal"}
    sender=roles["sender"]
    receiver=roles["receiver"]
    def sent(time,present):
        return InputFrame(time,{observations[(sender,"context")]:SignalSample(present=present)})
    def received(time,*,reset=False,stop=False):
        values={observations[(receiver,"shutdown")]:SignalSample(present=stop)}
        if combined:
            values.update({observations[(receiver,"reset")]:SignalSample(present=reset),
                           observations[(receiver,"measured_activity")]:3})
        return InputFrame(time,values)
    return {sender:(sent(0,True),sent(2,False)) if not combined else (sent(0,True),),
            receiver:(received(0),) if not combined else
            (received(0),received(4,reset=True),received(5),received(6,stop=True))}


def receiver_frames(result,build):
    role=build.plan.channels[0]["receiver_role"]
    return {frame.time:frame for frame in result.results[role].frames}


def output_active(frame):
    return any(item.kind=="action.secrete" for item in frame.actions)


class CoupledArchitectureExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request=make_architecture_request("D")
        cls.build=compile_payload_architecture(cls.request)
        assert cls.build.status=="compiled",cls.build.diagnostics

    def run_trace(self,*,build=None,request=None,failed=None,until=5,step=1,history=None,max_samples=1000):
        request=request or self.request
        build=build or self.build
        return evaluate_payload_architecture(build,request,history or histories(request),until=until,
                                             step=step,failed_channels=failed,max_samples=max_samples)

    def test_numeric_emission_delay_persistence_and_expiry_drive_receiver_actions(self):
        result=self.run_trace(step=bc.Duration(1))
        frames=receiver_frames(result,self.build)
        self.assertEqual([time for time,frame in frames.items() if output_active(frame)],[1,2,3])
        self.assertFalse(output_active(frames[0]))
        self.assertFalse(output_active(frames[4]))
        channel=self.build.plan.channels[0]
        received=result.histories[channel["receiver_role"]]
        self.assertEqual([frame.signals[channel["receiver_node_id"]].value for frame in received],[0,1,1,1,0,0])
        self.assertEqual(result.to_dict()["channels"],[thaw_json(channel)])
        self.assertEqual(result.to_dict()["policies"]["channel_sampling"],"settled_action_requests_at_declared_grid_only")
        self.assertIn("no_physiological_prediction",result.to_dict()["policies"]["claim_scope"])

    def test_clear_failure_discards_delivery_and_remaining_persistence(self):
        channel=self.build.plan.channels[0]["id"]
        result=self.run_trace(failed={channel:(2,)})
        self.assertEqual([time for time,frame in receiver_frames(result,self.build).items() if output_active(frame)],[1])
        self.assertEqual(result.channel_frames[2]["failed_channel_ids"],(channel,))

    def test_retain_last_failure_freezes_expiring_contribution_for_failed_tick(self):
        refinement=self.request.library.refinements[0]
        channel=replace(refinement.channels[0],failure_mode="retain_last")
        request=replace(self.request,library=replace(self.request.library,refinements=(replace(refinement,channels=(channel,)),)))
        build=compile_payload_architecture(request)
        self.assertEqual(build.status,"compiled",build.diagnostics)
        result=self.run_trace(build=build,request=request,failed={build.plan.channels[0]["id"]:(4,)})
        frames=receiver_frames(result,build)
        self.assertTrue(output_active(frames[4]))
        self.assertFalse(output_active(frames[5]))

    def test_role_evaluation_order_cannot_turn_delayed_transport_into_same_tick(self):
        original=histories(self.request)
        forward=self.run_trace(history=original)
        reversed_input=self.run_trace(history=dict(reversed(tuple(original.items()))))
        self.assertEqual(forward.to_dict(),reversed_input.to_dict())
        self.assertFalse(output_active(receiver_frames(forward,self.build)[0]))

    def test_receiver_values_cannot_be_overridden_and_roles_must_be_complete(self):
        original=histories(self.request)
        channel=self.build.plan.channels[0]
        bad=dict(original)
        receiver=channel["receiver_role"]
        bad[receiver]=(InputFrame(0,{**bad[receiver][0].signals,channel["receiver_node_id"]:999}),)
        with self.assertRaisesRegex(EvaluationError,"override"):
            self.run_trace(history=bad)
        with self.assertRaisesRegex(EvaluationError,"every source role"):
            self.run_trace(history={receiver:original[receiver]})

    def test_fresh_authority_check_rejects_tampered_transport(self):
        bad=dict(self.build.plan.channels[0])
        bad["latency_seconds"]=2
        build=replace(self.build,plan=replace(self.build.plan,channels=(bad,)))
        with self.assertRaisesRegex(EvaluationError,"fresh complete independent"):
            self.run_trace(build=build)

    def test_explicit_execution_bounds_and_offgrid_failure_flags(self):
        with self.assertRaisesRegex(EvaluationError,"max_samples"):
            self.run_trace(max_samples=5)
        with self.assertRaisesRegex(EvaluationError,"grid"):
            self.run_trace(step=2,until=6)
        with self.assertRaisesRegex(EvaluationError,"integer"):
            self.run_trace(step=.5)
        with self.assertRaisesRegex(EvaluationError,"selected channels"):
            self.run_trace(failed={"invented":(1,)})
        with self.assertRaisesRegex(EvaluationError,"integer"):
            self.run_trace(failed={self.build.plan.channels[0]["id"]:(.5,)})

    def test_zero_latency_is_rejected_even_when_declared_architecture_is_valid(self):
        refinement=self.request.library.refinements[0]
        channel=replace(refinement.channels[0],latency_seconds=0)
        request=replace(self.request,library=replace(self.request.library,refinements=(replace(refinement,channels=(channel,)),)))
        build=compile_payload_architecture(request)
        self.assertEqual(build.status,"compiled",build.diagnostics)
        with self.assertRaisesRegex(EvaluationError,"Zero-delay"):
            self.run_trace(build=build,request=request)

    def test_combined_state_channel_budget_and_shutdown_are_one_source_execution(self):
        request=make_architecture_request("F")
        build=compile_payload_architecture(request)
        self.assertEqual(build.status,"compiled",build.diagnostics)
        result=self.run_trace(build=build,request=request,history=histories(request,combined=True),until=7)
        frames=receiver_frames(result,build)
        state=request.source.intent.find(kind="state")[0].id
        self.assertEqual([time for time,frame in frames.items() if output_active(frame)],[1])
        self.assertEqual([frames[t].states[state] for t in (0,1,2,3,4,5,6,7)],
                         ["prime","act","act","recover","prime","act","recover","recover"])
        self.assertTrue(all(frame.signals[build.plan.channels[0]["receiver_node_id"]].value==1
                            for frame in result.histories[build.plan.channels[0]["receiver_role"]][1:]))


if __name__=="__main__":
    unittest.main()
