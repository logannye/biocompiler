"""Independent literal/census controls, never fabricated native acceptance."""
from copy import deepcopy
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import check_controlled_research_project as campaign

class ControlledResearchProjectCampaignTests(unittest.TestCase):
    def test_complete_literal_census_and_scope(self):
        packet=campaign.checked_assets()
        self.assertEqual(len(campaign.CASE_IDS),11);self.assertEqual(len(campaign.ACCEPTED),6)
        self.assertEqual(len(campaign.OBSERVATIONS),63);self.assertEqual(len(set(campaign.OBSERVATIONS)),63)
        self.assertEqual(tuple(row['id'] for row in packet['expected']['cases']),campaign.CASE_IDS)
        self.assertEqual(packet['inputs']['baseline']['behavior_request']['original']['budgets']['max_work'],100_000_000)
        for case in packet['expected']['cases']:
            self.assertEqual(case['products'],['MA','MG']);self.assertEqual(case['member_order'],['rna-a','rna-b'])
            self.assertEqual(case['sequences'],['CCAUGGCUUAAGGAAAA','CCAUGGGUUAAGGGAAAA' if case['id']=='material-longer' else 'CCAUGGGUUAAGGAAAA'])
            self.assertEqual(case['transitions'],2*case['horizon_tick']);self.assertEqual(case['prefixes'],2*case['horizon_tick']+1)
            self.assertEqual(campaign.digest(packet['inputs'][case['id']]),case['request_sha256'])

    def test_material_edit_is_one_supplied_utr_extension_with_complete_coordinates(self):
        packet=campaign.checked_assets();before=packet['inputs']['baseline']['behavior_request']['original'];after=packet['inputs']['material-longer']['behavior_request']['original']
        for key in set(before)-{'material_authority'}:self.assertEqual(before[key],after[key])
        authority=after['material_authority'];molecule=authority['template']['sources'][1]['molecule']
        self.assertEqual(molecule['sequence'],'CCAUGGGUUAAGGGAAAA');self.assertEqual(molecule['space']['length'],18)
        self.assertEqual(molecule['features'][1],before['material_authority']['template']['sources'][1]['molecule']['features'][1])
        self.assertEqual(molecule['features'][2]['path']['spans'][0]['end'],14)
        for chemistry in (molecule['chemistry'],authority['members'][1]['chemistry']):
            self.assertEqual(chemistry['terminal_tail']['path']['spans'][0],{'schema_version':'biocompiler.molecule_index_span.v0.1','start':14,'end':18})
        self.assertEqual(authority['members'][1]['product'],before['material_authority']['members'][1]['product'])

    def test_deadline_and_horizon_literals_are_source_demands_not_model_rewrites(self):
        packet=campaign.checked_assets();slow=packet['inputs']['slow-onset']['behavior_request']['original'];relaxed=packet['inputs']['relaxed-onset']['behavior_request']['original']
        self.assertEqual(slow['mechanism_model'],relaxed['mechanism_model']);self.assertEqual(slow['material_authority'],relaxed['material_authority'])
        self.assertEqual(slow['source_authority']['control_contract']['actual_delays']['onset_ticks'],3)
        self.assertEqual(slow['source_authority']['control_contract']['requested_deadlines']['onset_ticks'],2)
        self.assertEqual(relaxed['source_authority']['control_contract']['requested_deadlines']['onset_ticks'],3)
        self.assertEqual(slow['operating_domain']['horizon_tick'],11)
        for name,horizon in (('horizon-eleven',11),('short-horizon',9)):
            request=packet['inputs'][name]['behavior_request'];self.assertEqual(request['original']['operating_domain']['horizon_tick'],horizon)
            self.assertEqual([row['tick'] for row in request['readout_evidence']['samples']],list(range(horizon+1)))
        missing=packet['inputs']['missing-readout']['behavior_request'];base=packet['inputs']['baseline']['behavior_request']
        self.assertEqual(missing['original'],base['original']);self.assertEqual(missing['readout_evidence']['samples'][3],{'tick':3,'status':'missing','observed_tick':None})

    def test_native_run_requires_hosted_authority(self):
        with patch.dict('os.environ',{},clear=True),self.assertRaisesRegex(AssertionError,'hosted-only'):
            campaign.run(object())

    def test_original_admission_rejections_require_exact_diagnostics(self):
        packet=campaign.checked_assets()
        for name in campaign.REJECTED:
            case=next(row for row in packet['expected']['cases'] if row['id']==name)
            expected={'status':'error','diagnostics':[{'code':'policy_controlled_domain' if name=='short-horizon' else 'controlled_authority_admission',
                'message':'Hold suffix cannot cover every original source deadline.' if name=='short-horizon' else 'Original RNA length exceeds supplied per-member/total resources.','path':None}]}
            with self.subTest(case=name):
                campaign.check_rejection(expected,case)
                mutations=[{'status':'ok'},{'status':'unsupported'},{'report':{'outcome':'pass'}},{'result':None}]
                for change in mutations:
                    with self.subTest(change=change),self.assertRaises(AssertionError):
                        campaign.check_rejection({**deepcopy(expected),**change},case)
                for key,value in (('code','controlled_workflow_work_limit'),('message','Another limit failed.'),('path','/resources')):
                    changed=deepcopy(expected);changed['diagnostics'][0][key]=value
                    with self.subTest(diagnostic=key),self.assertRaises(AssertionError):campaign.check_rejection(changed,case)
                for diagnostics in ([],expected['diagnostics']*2):
                    with self.subTest(diagnostics=diagnostics),self.assertRaises(AssertionError):
                        campaign.check_rejection({**expected,'diagnostics':diagnostics},case)

    def test_admission_rejection_cannot_replace_an_assessment_or_positive_case(self):
        packet=campaign.checked_assets()
        rejection={'status':'error','diagnostics':[{'code':'controlled_authority_admission',
            'message':'Original RNA length exceeds supplied per-member/total resources.','path':None}]}
        for case in packet['expected']['cases']:
            with self.subTest(case=case['id']):
                if case['id'] in campaign.REJECTED:
                    with self.assertRaisesRegex(AssertionError,'cannot be replaced'):
                        campaign.check_result({'report':{'outcome':'pass'}},case,packet['inputs'][case['id']])
                else:
                    with self.assertRaisesRegex(AssertionError,'Unexpected admission rejection'):
                        campaign.check_rejection(rejection,case)

    def test_complete_action_plan_retains_rejections_and_local_only_controls(self):
        packet=campaign.checked_assets()
        # Opaque proposals exercise routing only and are not native evidence.
        candidate={'material_candidate':{'construction':{'inventory':{
            'molecules':[{'id':'a','sequence':'CC'},{'id':'b','sequence':'CA'}],
            'role_instances':[{'subject_id':'a','subject_fingerprint':'old-a'},
                              {'subject_id':'b','subject_fingerprint':'old-b'}]}}}}
        values={name+'-compile':{'candidate':deepcopy(candidate),'report':{'opaque':'inert'}} for name in campaign.ACCEPTED}
        actions=campaign.expected_actions(packet,values)
        self.assertEqual(len(actions),63)
        self.assertEqual(Counter(row['role'] for row in actions),{'core':24,'verify':39})
        self.assertEqual(Counter(row['operation'].split('-')[0] for row in actions),{'capabilities':31,'compile':12,'export':17,'check':2,'replay':1})
        by_observation={row['observation']:row for row in actions if 'observation' in row}
        for name in campaign.REJECTED:
            self.assertEqual(by_observation[name+'-compile']['payload'],{'request':packet['inputs'][name]})
            self.assertEqual(by_observation[name+'-compile']['role'],'core')
            self.assertNotIn(name+'-export',by_observation)
        self.assertFalse(set(('stale-project','changed-limits','transport-cancellation')) & set(by_observation))
        for suffix,index in (('a',0),('b',1)):
            changed=by_observation['changed-candidate-'+suffix]['payload']['candidate']['material_candidate']['construction']['inventory']
            before=candidate['material_candidate']['construction']['inventory']
            self.assertEqual(changed['molecules'][index]['sequence'],'G'+before['molecules'][index]['sequence'][1:])
            self.assertEqual(changed['molecules'][1-index],before['molecules'][1-index])
            self.assertEqual(changed['role_instances'][index]['subject_fingerprint'],campaign.digest(changed['molecules'][index]))
            self.assertEqual(changed['role_instances'][1-index],before['role_instances'][1-index])
        self.assertEqual(values['baseline-compile']['candidate'],candidate)

if __name__=='__main__':unittest.main()
