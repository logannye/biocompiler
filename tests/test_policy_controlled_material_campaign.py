"""Pure campaign census/original-mutation checks; no native invocation."""
import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import check_policy_controlled_material as campaign
from biocompiler import core_policy_controlled_material as api

ROOT=Path(__file__).resolve().parents[1]


class ControlledMaterialCampaignTests(unittest.TestCase):
    def test_fixed_complete_census_and_hosted_guard(self):
        self.assertEqual(len(campaign.OBSERVATIONS),23)
        self.assertEqual(len(set(campaign.OBSERVATIONS)),23)
        self.assertEqual(set(campaign.NEGATIVE_DIAGNOSTICS),{'foreign-original','request-work-exhaustion','domain-work-exhaustion','report-byte-exhaustion','verifier-production-role'})
        with patch.dict(campaign.os.environ,{'GITHUB_ACTIONS':'false','RUNNER_ENVIRONMENT':'local'}):
            with self.assertRaisesRegex(AssertionError,'hosted-only'):campaign.run(SimpleNamespace())

    def test_original_literals_and_mutants_retain_complete_independent_input(self):
        request=json.loads((ROOT/campaign.FIXTURES['request']).read_text())
        fixture=json.loads((ROOT/campaign.FIXTURES['material']).read_text())
        candidate=fixture['literal_candidate']; before=deepcopy(candidate)
        mutants=campaign.candidates(request,candidate)
        self.assertEqual(candidate,before)
        self.assertEqual(tuple(mutants),campaign.MUTATIONS)
        self.assertEqual(campaign.digest(request),fixture['request_sha256'])
        self.assertEqual(campaign.digest(candidate),fixture['candidate_sha256'])
        for name,mutant in mutants.items():
            with self.subTest(name=name):
                api._candidate(mutant)
                content=api._normalized_content(mutant['construction'])
                self.assertEqual(content['member_order'],[row['id'] for row in content['inventory']['molecules']])
                for role in content['inventory']['role_instances']:
                    molecule=next(row for row in content['inventory']['molecules'] if row['id']==role['subject_id'])
                    self.assertEqual(role['subject_fingerprint'],campaign.digest(molecule))
                self.assertEqual(mutant['request_fingerprint'],fixture['request_sha256'])
                self.assertNotEqual(mutant,candidate)
        self.assertEqual(mutants['foreign-repinned']['construction']['authority_fingerprint'],fixture['construction_authority_sha256'])
        foreign_request,foreign_candidate=campaign.foreign_pair(request,candidate)
        self.assertNotEqual(campaign.digest(foreign_request),fixture['request_sha256'])
        self.assertNotEqual(foreign_candidate['construction']['authority_fingerprint'],fixture['construction_authority_sha256'])
        self.assertEqual(mutants['foreign-repinned']['construction']['inventory'],foreign_candidate['construction']['inventory'])

    def test_campaign_retains_legacy_census_and_adds_separate_workflow_step(self):
        from tools.check_policy_controlled_composition import OBSERVATIONS
        self.assertEqual(len(OBSERVATIONS),14)
        source=(ROOT/'tools/check_policy_controlled_material.py').read_text()
        ast.parse(source)
        workflow=(ROOT/'.github/workflows/policy-development.yml').read_text()
        self.assertEqual(workflow.count('python -B tools/check_policy_controlled_material.py'),1)
        self.assertIn('python -B tools/check_policy_controlled_composition.py',workflow)
        self.assertIn('python -B tools/check_policy_development.py sdk-all',workflow)


if __name__=='__main__':unittest.main()
