"""Campaign source/host guards, with no native execution."""
from copy import deepcopy
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import check_policy_controlled_composition as campaign


class ControlledCampaignTests(unittest.TestCase):
    def test_local_execution_rejects_before_any_binary_access(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(AssertionError, 'hosted-only'):
            campaign.run(SimpleNamespace())

    def test_complete_independent_literals_and_case_census(self):
        fixtures={name:json.loads((campaign.ROOT/path).read_text()) for name,path in campaign.FIXTURES.items()}
        request=fixtures['request']; before=deepcopy(request)
        self.assertEqual(request['source_authority']['document'],fixtures['source'])
        self.assertEqual(request['operating_domain'],fixtures['domain'])
        cross=campaign.cartesian(request)
        self.assertEqual(len(cross['operating_domain']['physical_factors']),2)
        self.assertEqual(len(cross['operating_domain']['evidence_factors']),1)
        self.assertEqual(request,before)
        self.assertEqual(tuple(campaign.adversaries(request)),tuple(campaign.NEGATIVE_DIAGNOSTICS))
        self.assertEqual(len(campaign.OBSERVATIONS),14)
        self.assertEqual(len(set(campaign.OBSERVATIONS)),14)
        self.assertEqual(campaign.OBSERVATIONS[6:-1],tuple(campaign.NEGATIVE_DIAGNOSTICS))
        workflow=(campaign.ROOT/'.github/workflows/policy-development.yml').read_text()
        self.assertIn('tools/check_policy_controlled_composition.py',workflow)
        self.assertIn('tools/check_policy_development.py sdk-all',workflow)
        self.assertIn('tools/check_policy_development.py car-payload-sdk',workflow)

if __name__ == '__main__': unittest.main()
