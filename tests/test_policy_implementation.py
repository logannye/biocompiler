"""Thin request assembly and routing, without Python policy semantics."""
from copy import deepcopy
import itertools
import json
import unittest
from unittest.mock import patch

from biocompiler.policy import implementation as sdk
from biocompiler.policy import BuildRequest, from_data, check, dumps, loads
from tests import test_core_policy_implementation as peer


class PolicyImplementationSdkTests(unittest.TestCase):
    def setUp(self):
        self.peer = peer.PolicyImplementationTransportTests()
        self.peer.setUp()

    def test_request_assembly_retains_all_original_authority_without_aliases(self):
        original = deepcopy(self.peer.request)
        values = {key: deepcopy(original[key]) for key in (
            "definitions", "operating_domain", "implementation_library", "catalog_bindings", "budgets",
        )}
        document = from_data(original["document"], BuildRequest)
        with patch("biocompiler.policy.validation.check", side_effect=AssertionError("No Python admission")):
            request = sdk.prepare_request(document, **values)
        self.assertEqual(request, original)
        values["catalog_bindings"].clear()
        self.assertEqual(request, original)
        for untrusted in (original["document"], document.program, object(), lambda: document):
            with self.subTest(untrusted=type(untrusted)), self.assertRaises(TypeError):
                sdk.prepare_request(untrusted, **values)

    def test_all_routes_use_native_transport_with_full_original_inputs(self):
        with self.peer.exchange(), patch("biocompiler.policy.validation.check", side_effect=AssertionError("No Python fallback")):
            compiled = sdk.compile(self.peer.request, limits=self.peer.limits, client=self.peer.client)
            checked = sdk.check(self.peer.request, candidate=compiled.candidate, limits=self.peer.limits, client=self.peer.client)
            replayed = sdk.replay(self.peer.request, candidate=compiled.candidate, limits=self.peer.limits,
                                  report=checked.result, client=self.peer.client)
        self.assertEqual(compiled.result, replayed.result)
        self.assertEqual(self.peer.calls[-1]["payload"]["report"], checked.result)
        self.assertEqual(self.peer.calls[-1]["payload"]["request"], self.peer.request)

    def test_installed_campaign_fixture_preserves_original_sources_and_independent_census(self):
        fixture = json.loads((peer.ROOT / "core/test/data/policy_implementation_request_v01.json").read_text())
        originals = json.loads((peer.ROOT / "core/test/data/policy_implementation_binding_v01.json").read_text())["cases"]
        self.assertEqual(set(fixture), {"schema_version", "claim_scope", "request", "limits", "expected", "unknown_control"})
        self.assertEqual(fixture["schema_version"], "biocompiler.policy_implementation_request_fixture.v0.1")
        self.assertNotIn("candidate", fixture)
        self.assertNotIn("report", fixture)
        for supplied, original in ((fixture["request"], originals[1]["request"]),
                                   (fixture["unknown_control"]["request"], originals[0]["request"])):
            for key in ("document", "definitions", "implementation_library", "catalog_bindings"):
                self.assertEqual(supplied[key], original[key])
            document = from_data(supplied["document"], BuildRequest)
            self.assertEqual(check(document).status, "complete")
            self.assertEqual(loads(dumps(document), BuildRequest), document)
        domain = fixture["request"]["operating_domain"]
        self.assertEqual(domain["horizon_ticks"], 6)
        self.assertEqual(domain["observation_factors"], [])
        self.assertEqual(domain["lifecycle_factors"], [])
        self.assertEqual([(row["available_tick"], row["slot"], row["value"]) for row in domain["fixed_observations"]],
                         [(tick, slot, value) for tick, value in ((0, False), (1, True), (2, False)) for slot in ("e1", "e2")])
        self.assertEqual(domain["feedback_factors"], [{"effect": "response", "ticks": [2],
            "attempt_selector": "all_previously_created", "outcomes": ["completed", "failed"],
            "routes": ["correlated"], "max_rows_per_attempt_tick": 1}])
        # This arithmetic enumerates only independently authored feedback labels;
        # it neither executes policies nor derives expected values from a runtime.
        histories = list(itertools.product(("none", "completed", "failed"), repeat=2))
        self.assertEqual((len(histories), 2 + 5 * len(histories), 3 + 5 * len(histories)), (9, 47, 48))
        active_prefixes = 1 + sum("none" in row for row in histories)
        active_samples = 2 * len(histories) + sum(row.count("none") for row in histories)
        self.assertEqual((active_prefixes, active_samples), (6, 24))
        expected = fixture["expected"]
        self.assertEqual((expected["histories"], expected["transitions"], expected["prefixes"]), (9, 47, 48))
        self.assertEqual((expected["active_prefixes"], expected["inactive_prefixes"]), (6, 41))
        self.assertEqual((expected["safety_samples"], expected["safety_active"], expected["safety_inactive"]), (126, 24, 102))
        self.assertEqual(fixture["unknown_control"]["expected"]["requirements"]["scoped_memory"], "unknown")


if __name__ == "__main__":
    unittest.main()
