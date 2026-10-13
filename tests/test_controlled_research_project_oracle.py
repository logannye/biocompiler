"""Inert assertion controls only: these documents are not native evidence."""
from copy import deepcopy
from collections import Counter
import json
from pathlib import Path
import unittest
from tools import check_controlled_research_project as campaign

KINDS=('no_unauthorized_activation','initial_activation','controller_cessation',
       'antigen_cessation','component_cessation','reactivation')

def document(packet, name):
    case=next(row for row in packet['expected']['cases'] if row['id']==name)
    original=packet['inputs'][name]; resources=original['limits']['resources']
    status=case['status']; outcome={'accepted':'pass','behavior_fail':'fail','unknown':'unknown'}[status]
    counts=[]
    for kind in KINDS:
        if name=='missing-readout':c=(0,0,2,0)
        elif name=='slow-onset' and kind=='initial_activation':c=(0,2,0,0)
        elif name in ('slow-onset','relaxed-onset'):
            c=(2,0,0,0) if kind in KINDS[:2] else (0,0,0,2) if kind=='controller_cessation' else (1,0,0,1)
        else:c=(1,0,0,1) if kind=='controller_cessation' else (2,0,0,0)
        counts.append({'kind':kind,**dict(zip(('pass','fail','unknown','not_exercised'),c))})
    behavior={'outcome':'unknown' if status=='unknown' else 'fail' if status=='behavior_fail' else 'pass',
        'model_correspondence':'pass','evidence_status':'unknown' if status=='unknown' else 'resolved',
        'domain':{'completion':'complete','assessed_histories':2,'pending_at_horizon':False,
            'counters':{key:case[key] for key in ('histories','prefixes','transitions')}},
        'requirements':counts,'coverage':{key:True for key in ('active','background','antigen_absent_controller_enabled','controller_disabled_antigen_present','reversible_cycle')}}
    if status in ('behavior_fail','unknown'):
        bands=('BBBAAABAAAAA' if status=='behavior_fail' else 'BAAAAABAAAA')
        trace=[];history=[]
        for tick,band in enumerate(bands):
            sample={'tick':tick,'band':'active' if band=='A' else 'background','activation_generation':1 if band=='A' else None}
            original_domain=original['behavior_request']['original']['operating_domain']
            row=next(r for r in original_domain['fixed_inputs'] if r['tick']==(1 if tick==2 else tick))
            inputs={'tick':tick,'event':'start' if tick==0 else 'none','live':True,'generation':1,'generation_started_tick':0,'physical':row['physical'],'evidence':row['evidence']}
            trace.append({'input':inputs,'candidate':sample,'model_reference':deepcopy(sample),'corresponds':True})
            history.append({'input':inputs,'activity':sample,'readout_evidence':'missing' if status=='unknown' and tick==3 else 'valid','qualified_gate':tick!=5,'inputs_required':True})
        actions=[('triggered',0),('deadline_missed',2),('discharged',3)] if status=='behavior_fail' else [('triggered',0),('discharged',1)]
        monitor={'complete':True,'outcome':outcome,'pending':False,'history':history,
            'requirements':[{'kind':'initial_activation','status':'fail' if status=='behavior_fail' else 'unknown',
                'events':[{'tick':tick,'action':action,'trigger_tick':0,'deadline_tick':2,'generation':1} for action,tick in actions]}],
            'evidence_gaps':[{'tick':3,'channel':'activity','status':'missing'}] if status=='unknown' else []}
        behavior['counterexample']={'history_index':1,'reduction':'none_complete_original_history',
            'model_correspondence':True,'pending_at_horizon':False,'deployment_evidence_unknown':False,'trace':trace,'source_monitor':monitor}
    material={'structure':{'outcome':'pass'},'outcome':'pass',
        'material_limits':{'member_order':case['member_order'],'expected_member_order':case['member_order'],
            'members':[{'member_id':member,'rna_nt':len(sequence),'within_limit':len(sequence)<=resources['max_member_rna_nt']} for member,sequence in zip(case['member_order'],case['sequences'])],
            'max_member_rna_nt':resources['max_member_rna_nt'],'max_total_rna_nt':resources['max_total_rna_nt'],
            'total_rna_nt':sum(map(len,case['sequences'])),'outcome':'pass'}}
    result={'request_fingerprint':campaign.digest(original),'artifact':None,'report':{
        'outcome':outcome,'status':'controlled_workflow_accepted' if outcome=='pass' else 'not_accepted',
        'project_context':original['behavior_request']['original']['source_authority']['project_context'],
        'limits':original['limits'],'empirical_status':'unassessed','human_use':'unassessed','therapeutic_export':'withheld',
        'material':material,'behavior':behavior}}
    return case,original,result

class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.packet=campaign.checked_assets()

    def check(self, name, mutation=None):
        case,original,result=document(self.packet,name)
        if mutation is None:campaign.check_result(result,case,original)
        else:
            mutation(result)
            with self.assertRaises(AssertionError):campaign.check_result(result,case,original)

    def test_eight_assessments_and_three_original_admission_rejections(self):
        for name in campaign.CASE_IDS:
            if name not in campaign.REJECTED:
                with self.subTest(name=name):self.check(name)
            else:
                case=next(row for row in self.packet['expected']['cases'] if row['id']==name)
                rejection={'status':'error','diagnostics':[{
                    'code':'policy_controlled_domain' if name=='short-horizon' else 'controlled_authority_admission',
                    'message':'Hold suffix cannot cover every original source deadline.' if name=='short-horizon' else 'Original RNA length exceeds supplied per-member/total resources.',
                    'path':None}]}
                with self.subTest(name=name):campaign.check_rejection(rejection,case)

    def test_wrong_specific_failure(self):
        def mutate(result):
            rows=result['report']['behavior']['requirements'];rows[0].update({'pass':0,'fail':2});rows[1].update({'pass':2,'fail':0})
        self.check('slow-onset',mutate)

    def test_wrong_missingness_and_physical_false(self):
        self.check('missing-readout',lambda r:r['report']['behavior']['counterexample']['source_monitor']['evidence_gaps'][0].update(status='invalid'))
        def mutate(result):
            row=result['report']['behavior']['counterexample']['trace'][3]
            for key in ('candidate','model_reference'):row[key].update(band='background',activation_generation=None)
        self.check('missing-readout',mutate)

    def test_wrong_bound_and_deadline(self):
        self.check('tight',lambda r:r['report']['material']['material_limits']['members'][0].update(within_limit=False))
        self.check('tight',lambda r:r['report']['material']['material_limits'].update(max_total_rna_nt=33))
        self.check('slow-onset',lambda r:r['report']['behavior']['counterexample']['source_monitor']['requirements'][0]['events'][1].update(deadline_tick=3))

    def test_relaxed_original_does_not_invent_exercised_controller_stop(self):
        self.check('relaxed-onset',lambda r:r['report']['behavior']['requirements'][2].update({'pass':1,'not_exercised':1}))

    def test_complete_native_action_plan_and_mutation_locality(self):
        candidate={'material_candidate':{'construction':{'inventory':{'molecules':[{'id':'a','sequence':'CC'},{'id':'b','sequence':'CA'}],
            'role_instances':[{'subject_id':'a','subject_fingerprint':'old-a'},{'subject_id':'b','subject_fingerprint':'old-b'}]}}}}
        values={name+'-compile':{'candidate':deepcopy(candidate),'report':{'opaque':'not-native-evidence'}} for name in campaign.CASE_IDS}
        actions=campaign.expected_actions(self.packet,values)
        self.assertEqual(len(actions),63)
        self.assertEqual(Counter(row['role'] for row in actions),{'core':24,'verify':39})
        self.assertEqual(sum(row['operation']=='capabilities' for row in actions),31)
        self.assertEqual(Counter(row['operation'].split('-')[0] for row in actions),{'capabilities':31,'compile':12,'export':17,'check':2,'replay':1})
        self.assertFalse(any(row.get('observation') in ('stale-project','changed-limits','transport-cancellation') for row in actions))
        for suffix,index in (('a',0),('b',1)):
            changed=next(row for row in actions if row.get('observation')=='changed-candidate-'+suffix)['payload']['candidate']
            molecules=changed['material_candidate']['construction']['inventory']['molecules']
            self.assertEqual(molecules[index]['sequence'],'G'+candidate['material_candidate']['construction']['inventory']['molecules'][index]['sequence'][1:])
            self.assertEqual(molecules[1-index],candidate['material_candidate']['construction']['inventory']['molecules'][1-index])
        self.assertEqual(values['baseline-compile']['candidate'],candidate)

if __name__=='__main__':unittest.main(verbosity=2)
