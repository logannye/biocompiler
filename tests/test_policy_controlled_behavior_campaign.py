"""Pure source-bound campaign controls; never evidence of native acceptance."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import check_policy_controlled_behavior as campaign
from tests.test_core_policy_controlled_behavior import original, candidate, peer_result
from biocompiler.policy.controlled_behavior import ControlledBehaviorRequest


class ControlledBehaviorCampaignTests(unittest.TestCase):
    def test_fixed_census_and_exact_negative_layers(self):
        self.assertEqual(len(campaign.OBSERVATIONS),26)
        self.assertEqual(len(set(campaign.OBSERVATIONS)),26)
        self.assertEqual(campaign.OBSERVATIONS[:6],('baseline-original','construct-core','check-core','check-verify','replay-core','replay-verify'))
        self.assertEqual(campaign.OBSERVATIONS[12:15],('upper-bound-onset-original','upper-bound-onset-core','upper-bound-onset-verify'))
        self.assertEqual(campaign.OBSERVATIONS[15:-1],tuple(campaign.NEGATIVE_DIAGNOSTICS))
        self.assertEqual(len(campaign.NEGATIVE_DIAGNOSTICS),10)
        self.assertEqual(campaign.OBSERVATIONS[-1],'transport-cancellation')
        self.assertEqual(campaign.NEGATIVE_DIAGNOSTICS['assembly-delay'],'controlled_behavior_assembly_binding')
        self.assertEqual(campaign.NEGATIVE_DIAGNOSTICS['replay-forgery'],'controlled_behavior_assessment_mismatch')

    def test_model_delay_change_preserves_original_source_deadline(self):
        raw=original();before=deepcopy(raw);changed=campaign.late_model(raw)
        self.assertEqual(raw,before)
        authority=changed['original'];contract=authority['source_authority']['control_contract']
        self.assertEqual(contract['actual_delays']['onset_ticks'],3)
        self.assertEqual(contract['requested_deadlines'],raw['original']['source_authority']['control_contract']['requested_deadlines'])
        self.assertEqual(authority['source_authority']['document'],raw['original']['source_authority']['document'])
        body=authority['mechanism_model']['body']
        digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(authority['mechanism_model']['identity']['content_fingerprint'],digest)
        self.assertEqual(authority['catalog_binding']['model_identity'],authority['mechanism_model']['identity'])
        ControlledBehaviorRequest.from_request(changed)

    def test_upper_bound_actual_onset_keeps_complete_source_and_domain(self):
        raw=original();before=deepcopy(raw);changed=campaign.late_model(raw,onset_ticks=10000)
        self.assertEqual(raw,before)
        authority=changed['original'];contract=authority['source_authority']['control_contract']
        self.assertEqual(contract['actual_delays']['onset_ticks'],10000)
        self.assertEqual(authority['mechanism_model']['body']['delays']['onset_ticks'],10000)
        self.assertEqual(contract['requested_deadlines']['onset_ticks'],2)
        self.assertEqual(authority['operating_domain']['horizon_tick'],10)
        self.assertEqual(authority['source_authority']['document'],raw['original']['source_authority']['document'])
        self.assertEqual(authority['operating_domain'],raw['original']['operating_domain'])
        self.assertEqual(changed['readout_evidence'],raw['readout_evidence'])
        body=authority['mechanism_model']['body']
        digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(authority['mechanism_model']['identity']['content_fingerprint'],digest)
        self.assertEqual(authority['catalog_binding']['model_identity'],authority['mechanism_model']['identity'])
        restored=deepcopy(changed)
        restored['original']['mechanism_model']=deepcopy(raw['original']['mechanism_model'])
        restored['original']['source_authority']['control_contract']['actual_delays']['onset_ticks']=raw['original']['source_authority']['control_contract']['actual_delays']['onset_ticks']
        restored['original']['catalog_binding']['model_identity']=deepcopy(raw['original']['catalog_binding']['model_identity'])
        self.assertEqual(restored,raw)
        ControlledBehaviorRequest.from_request(changed)

    def test_readout_unknown_preserves_every_physical_input_and_full_authority(self):
        raw=original();changed=campaign.missing_readout(raw)
        self.assertEqual(changed['original'],raw['original'])
        self.assertEqual(changed['readout_evidence']['samples'][3],{'tick':3,'status':'missing','observed_tick':None})
        self.assertEqual(changed['readout_evidence']['samples'][:3],raw['readout_evidence']['samples'][:3])
        self.assertEqual(changed['readout_evidence']['samples'][4:],raw['readout_evidence']['samples'][4:])
        ControlledBehaviorRequest.from_request(changed)

    def test_negative_mutations_keep_complete_independent_originals(self):
        raw=original();proposal=candidate(raw);report=peer_result(raw,proposal)['report']
        retained=deepcopy((raw,proposal,report));cases=campaign.adversaries(raw,proposal,report)
        self.assertEqual((raw,proposal,report),retained)
        self.assertEqual(tuple(cases),tuple(campaign.NEGATIVE_DIAGNOSTICS))
        request_binding=cases['request-binding'][1]
        self.assertEqual(request_binding['candidate'],proposal)
        self.assertNotEqual(request_binding['request'],raw)
        assembly=cases['assembly-delay'][1]
        self.assertEqual(assembly['request'],raw)
        self.assertEqual(assembly['candidate']['implementation']['primitives'][6]['onset_ticks'],3)
        for key in ('mechanism_model','control_contract','assembly','semantics','context','resources','catalog_binding','wires'):
            self.assertEqual(assembly['candidate']['implementation'][key],proposal['implementation'][key])
        exhausted=cases['domain-work-exhaustion'][1]
        self.assertEqual(exhausted['candidate']['implementation'],proposal['implementation'])
        digest=hashlib.sha256(json.dumps(exhausted['request'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(exhausted['candidate']['request_fingerprint'],digest)
        self.assertEqual(cases['verify-construction'][0],'construct-policy-controlled-behavior')

    def test_hosted_guard_precedes_native_import_or_process(self):
        with patch.dict('os.environ',{},clear=True),self.assertRaisesRegex(AssertionError,'hosted-only'):
            campaign.run(SimpleNamespace())

    def test_campaign_has_no_python_activity_evaluator_or_test_peer(self):
        source=Path(campaign.__file__).read_text()
        self.assertNotIn('tests.test_',source)
        self.assertNotIn('peer_result',source)
        self.assertIn('construct_behavior(typed',source)
        self.assertIn('check_behavior(typed',source)
        self.assertIn('replay_behavior(typed',source)
        self.assertIn('transports["verify"].call(operation, payload)',source)


if __name__=='__main__':unittest.main()
