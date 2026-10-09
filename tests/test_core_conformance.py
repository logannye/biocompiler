"""Pure-Python checks of the hosted native campaign's authority and coverage."""

from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import re
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


_PATH = Path(__file__).resolve().parents[1] / "tools/check_core_conformance.py"
_SPEC = importlib.util.spec_from_file_location("core_conformance_under_test", _PATH)
campaign = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(campaign)


_SELECTION_OPERATIONS = ["check-policy-component-selection", "replay-policy-component-selection",
                         "export-policy-component-selection", "compile-policy-component-selection"]


def without_selection(capabilities):
    """Project only the additive selection contract out of a complete census."""
    result = deepcopy(capabilities)
    result["operations"] = [name for name in result["operations"] if name not in _SELECTION_OPERATIONS]
    result["validation_scopes"] = [scope for scope in result["validation_scopes"]
                                   if scope != "policy-component-selection-mrna-v0.1"]
    for key in ("policy_component_selection", "policy_component_selection_producer"):
        result["profiles"].pop(key, None)
    return result


def without_instance(capabilities):
    """Project the instance profile out; it shares the existing operation routes."""
    result = deepcopy(capabilities)
    result["validation_scopes"] = [scope for scope in result["validation_scopes"]
                                   if scope != "policy-instance-component-mrna-v0.1"]
    for key in ("policy_instance_material", "policy_instance_material_producer"):
        result["profiles"].pop(key, None)
    return result


def without_prerequisites(capabilities):
    """Remove only the reviewed prerequisite addition from historical hashes."""
    result = deepcopy(capabilities)
    result["validation_scopes"] = [scope for scope in result["validation_scopes"]
                                   if scope != "policy-instance-prerequisite-mrna-v0.1"]
    for key in ("policy_prerequisite_material", "policy_prerequisite_material_producer"):
        result["profiles"].pop(key, None)
    return result


def without_two_observations(capabilities):
    """Remove only the reviewed two-observation addition from historical hashes."""
    result = deepcopy(capabilities)
    result["validation_scopes"] = [scope for scope in result["validation_scopes"]
                                   if scope != "policy-instance-two-observation-prerequisite-mrna-v0.1"]
    for key in ("policy_two_observation_material", "policy_two_observation_material_producer"):
        result["profiles"].pop(key, None)
    return result


def without_multi_member(capabilities):
    """Remove only the reviewed multi-member addition from historical hashes."""
    result = deepcopy(capabilities)
    result["validation_scopes"] = [scope for scope in result["validation_scopes"]
                                   if scope != "policy-multi-member-prerequisite-mrna-v0.1"]
    for key in ("policy_multi_member_material", "policy_multi_member_material_producer"):
        result["profiles"].pop(key, None)
    return result


def without_grounded_helper(capabilities):
    """Remove only the reviewed grounded-helper addition from historical hashes."""
    result = deepcopy(capabilities)
    result["validation_scopes"] = [scope for scope in result["validation_scopes"]
                                   if scope != "policy-grounded-helper-prerequisite-mrna-v0.1"]
    for key in ("policy_grounded_helper_material", "policy_grounded_helper_material_producer"):
        result["profiles"].pop(key, None)
    return result


class CoreConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = campaign.load_corpus()
        cls.programs = campaign.source_programs()

    def test_producer_scope_order_matches_native_declaration_not_json_key_order(self):
        source = (campaign.ROOT / "core/lib/producer_service/synthetic_producer_service.ml").read_text()
        declaration = json.loads(re.search(r"\{profiles\|(.*?)\|profiles\}", source, re.S).group(1))
        self.assertEqual(set(declaration), set(campaign.SYNTHETIC_PRODUCER_PROFILES))
        for family, profile in declaration.items():
            for field, value in profile.items():
                self.assertEqual(campaign.SYNTHETIC_PRODUCER_PROFILES[family][field], value)
        self.assertIn("let families = [Generation;Selection;Components]", source)
        expected = [
            "deterministic-synthetic-proposal-only-v1",
            "two-strategy-synthetic-selection-finite-history-v1",
            "fresh-synthetic-component-adaptation-only-v1",
        ]
        self.assertEqual(campaign.synthetic_producer_scopes(), expected)
        json_key_order = [profile["validation_scope"] for profile in declaration.values()]
        self.assertNotEqual(json_key_order, expected)
        # Changes to JSON object insertion order cannot change the wire array.
        with patch.object(campaign, "SYNTHETIC_PRODUCER_PROFILES", dict(reversed(list(declaration.items())))):
            self.assertEqual(campaign.synthetic_producer_scopes(), expected)

    def test_capability_fields_preserve_exact_scope_order_and_field_diagnostics(self):
        scopes = campaign.synthetic_producer_scopes()
        profiles = deepcopy(campaign.SYNTHETIC_PRODUCER_PROFILES)
        actual = {
            "canonicalization": "python-json-v1",
            "intent_schemas": ["biocompiler.intent.v0.1"],
            "validation_scopes": list(scopes),
            "limits": deepcopy(campaign.LIMITS),
            "schema_version": "biocompiler.core_capabilities.v1",
            "profiles": deepcopy(profiles),
        }
        campaign.check_capability_fields(actual, scopes, profiles)
        changed_profiles = deepcopy(profiles)
        changed_profiles["synthetic_generation"]["claim_scope"] = "empirical function"
        changes = (
            ("canonicalization", "other-json"),
            ("intent_schemas", []),
            ("validation_scopes", scopes[1:] + scopes[:1]),
            ("validation_scopes", scopes[:-1]),
            ("limits", {}),
            ("schema_version", "biocompiler.core_capabilities.v2"),
            ("profiles", changed_profiles),
        )
        for field, value in changes:
            with self.subTest(field=field, value=value), self.assertRaisesRegex(
                    AssertionError, "Capability contract differs: " + field):
                campaign.check_capability_fields({**actual, field: value}, scopes, profiles)

    def test_literal_expectations_retain_independent_bytes_and_digests(self):
        by_id = {value["id"]: value for value in self.corpus["literal_vectors"]}
        self.assertEqual(by_id["null"]["sha256"], "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b")
        self.assertIn("1.0", by_id["integer-and-float-spelling"]["canonical_json"])
        self.assertIn("-0.0", by_id["integer-and-float-spelling"]["canonical_json"])
        self.assertIn("9007199254740993", by_id["large-exact-integers"]["canonical_json"])
        self.assertIn("é", by_id["unicode-not-normalized"]["canonical_json"])
        self.assertEqual(by_id["asymmetric-binary-rounding-interval"]["canonical_json"],
                         "[6.617444900424222e-24,-6.617444900424222e-24]")

    def test_changed_expected_literal_cannot_be_repaired_by_core_output(self):
        corpus = deepcopy(self.corpus)
        corpus["literal_vectors"][0]["canonical_json"] = "false"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "corpus.json"
            path.write_text(json.dumps(corpus))
            with self.assertRaisesRegex(AssertionError, "Stale literal fingerprint"):
                campaign.load_corpus(path)

    def test_bit_pattern_oracle_is_seeded_broad_finite_and_exact(self):
        settings = self.corpus["python_oracle"]
        first = campaign.float_patterns(settings["seed"], settings["finite_float_count"])
        self.assertEqual(first, campaign.float_patterns(settings["seed"], settings["finite_float_count"]))
        self.assertGreaterEqual(len(first), 2048)
        self.assertGreater(len({(bits >> 52) & 0x7ff for bits, _ in first}), 1000)
        self.assertEqual({bits >> 63 for bits, _ in first}, {0, 1})
        for bits, value in first:
            self.assertTrue(math.isfinite(value))
            self.assertEqual(struct.pack(">d", value), bits.to_bytes(8, "big"))
        with self.assertRaisesRegex(AssertionError, "2048"):
            campaign.float_patterns(1, 20)

    def test_decimal_boundaries_cover_both_signed_zero_and_extremes(self):
        values = campaign.boundary_floats()
        self.assertGreater(len(values), 3000)
        self.assertTrue(all(math.isfinite(value) for value in values))
        self.assertIn(struct.pack(">d", -0.0), [struct.pack(">d", value) for value in values])
        self.assertIn(5e-324, values)

    def test_binary_boundaries_include_asymmetric_intervals_and_four_ulps(self):
        values = campaign.binary_boundary_floats(**self.corpus["python_oracle"]["binary_boundaries"])
        patterns = {int.from_bytes(struct.pack(">d", value), "big") for value in values}
        self.assertEqual(len(values), len(patterns))
        self.assertGreater(len(values), 37000)
        self.assertTrue(all(math.isfinite(value) for value in values))
        self.assertTrue({0, 1 << 63, 1, (1 << 63) | 1}.issubset(patterns))
        for center in (0x0010000000000000, 0x3b20000000000000, 0x7fe0000000000000):
            for offset in range(-4, 5):
                self.assertIn(center + offset, patterns)
                self.assertIn((center + offset) | (1 << 63), patterns)
        # Literal decimal expected at 2**-77; the old nearest-only formatter
        # incorrectly continued to 17 significant digits at this boundary.
        self.assertEqual(campaign.canonical(math.ldexp(1.0, -77)), "6.617444900424222e-24")
        self.assertEqual(float("6.6174449004242214e-24"), math.ldexp(1.0, -77))

    def test_every_authored_example_keeps_source_location_invariance(self):
        self.assertGreaterEqual(len(self.programs), 6)
        for name, program in self.programs.items():
            for variant, document in campaign.source_variants(program.to_dict()).items():
                with self.subTest(example=name, variant=variant):
                    restored = campaign.IntentProgram.from_dict(document)
                    self.assertEqual(restored.summary(), program.summary())
                    self.assertNotEqual(restored.to_dict(), program.to_dict())

    def test_typed_positive_cases_retain_optional_field_identity(self):
        values = campaign.typed_programs()
        fingerprints = {name: campaign.IntentProgram.from_dict(value).fingerprint for name, value in values.items()}
        self.assertNotEqual(fingerprints["scalar-zero"], fingerprints["scalar-negative-zero"])
        self.assertNotEqual(fingerprints["scalar-zero"], fingerprints["optional-type-fields-omitted"])
        self.assertNotEqual(fingerprints["scalar-zero"], fingerprints["declared-zero-dimension-retained"])

    def test_mutations_are_invalid_and_have_specific_rejection_signatures(self):
        cases = campaign.intent_mutations(self.programs)
        self.assertGreaterEqual(len(cases), 25)
        self.assertEqual(len(cases), len({name for name, _, _ in cases}))
        for name, code, document in cases:
            with self.subTest(case=name):
                self.assertNotIn(code, {"internal_error", "resource_exhausted", "invalid_json"})
                with self.assertRaises(Exception):
                    campaign.IntentProgram.from_dict(document)

    def test_summary_comparison_cannot_promote_scope_or_drop_obligations(self):
        program = next(iter(self.programs.values()))
        correct = {"validation_scope": campaign.SCOPE, "summary": program.summary(),
                   "unimplemented_obligations": campaign.OBLIGATIONS}
        client = SimpleNamespace(role="core", validate_intent=lambda _: SimpleNamespace(result=correct))
        runner = campaign.Campaign({"checks": []})
        runner.intent(client, "positive", program.to_dict(), program.summary())
        self.assertEqual(len(runner.receipt["checks"]), 1)
        for key, value in (("validation_scope", "whole-therapy-verified"), ("unimplemented_obligations", [])):
            forged = {**correct, key: value}
            client.validate_intent = lambda _, result=forged: SimpleNamespace(result=result)
            with self.assertRaisesRegex(AssertionError, "promoted its scope"):
                runner.intent(client, "forged", program.to_dict(), program.summary())
        self.assertEqual(len(runner.receipt["checks"]), 1)

    def test_raw_requests_retain_lexical_numbers_and_invalid_bytes(self):
        request = campaign.request_bytes(b'{"x":-0,"x":1.0,"bad":"\xff"}')
        self.assertIn(b'{"x":-0,"x":1.0,"bad":"\xff"}', request)
        self.assertTrue(request.endswith(b"}}"))

    def test_wrong_native_rejection_never_counts_as_mutant_detection(self):
        runner = campaign.Campaign({"checks": []})
        client = SimpleNamespace(role="core")
        crash = {"status": "error", "result": None, "diagnostics": [{"code": "internal_error"}],
                 "request_id": None, "operation": None}
        with patch.object(campaign, "raw_response", return_value=crash):
            with self.assertRaisesRegex(AssertionError, "wrong rejection signature"):
                runner.rejection(client, "duplicate", b"invalid", "duplicate_key")
        self.assertEqual(runner.receipt["checks"], [])

    def test_lowering_authorities_cover_both_profiles_and_every_operation(self):
        from biocompiler.compiler.behavior import verify_lowering
        from biocompiler.ir.behavior import SUPPORTED_KINDS, EXTENSION_KINDS

        cases = campaign.lowering_cases()
        kinds = set()
        profiles = set()
        for _, request, behavior in cases:
            source = campaign.BuildRequest.from_dict(request)
            candidate = campaign.BehaviorProgram.from_dict(behavior)
            self.assertTrue(verify_lowering(source, candidate).passed)
            kinds.update(node.kind for node in candidate.nodes)
            profiles.add(candidate.schema_version)
        self.assertEqual(kinds, SUPPORTED_KINDS | EXTENSION_KINDS)
        self.assertEqual(profiles, {"biocompiler.behavior.v0.1", "biocompiler.behavior.v0.2"})
        self.assertEqual(len(cases), 10)

    def test_lowering_mutants_reach_preservation_not_schema_failure(self):
        from biocompiler.compiler.behavior import verify_lowering
        from biocompiler.errors import LoweringVerificationError

        cases = campaign.lowering_mutations(campaign.lowering_cases())
        for name, code, request, behavior in cases:
            with self.subTest(case=name):
                source = campaign.BuildRequest.from_dict(request)
                candidate = campaign.BehaviorProgram.from_dict(behavior)
                self.assertTrue(code.startswith("lowering_"))
                with self.assertRaises(LoweringVerificationError):
                    verify_lowering(source, candidate)

    def test_lowering_report_cannot_drop_identity_obligations_or_checks(self):
        _, request, behavior = campaign.lowering_cases()[0]
        expected = campaign.lowering_expectation(request, behavior)
        properties = expected.pop("check_properties")
        correct = {**expected, "checks": [{"property": name, "passed": True, "detail": "Checked"}
                                         for name in properties]}
        client = SimpleNamespace(role="verify", verify_lowering=lambda **_: SimpleNamespace(result=correct))
        runner = campaign.Campaign({"checks": []})
        runner.lowering(client, "positive", request, behavior)
        self.assertEqual(len(runner.receipt["checks"]), 1)
        alterations = (
            ("request_fingerprint", "0" * 64), ("request_artifact_fingerprint", "0" * 64),
            ("behavior_fingerprint", "0" * 64), ("behavior_artifact_fingerprint", "0" * 64),
            ("unimplemented_obligations", []), ("validation_scope", "architecture-accepted"),
            ("passed", 1), ("checks", correct["checks"][:-1]),
            ("checks", [{"property": "source_identity", "passed": False, "detail": "Failed"}]),
        )
        for key, value in alterations:
            client.verify_lowering = lambda result={**correct, key: value}, **_: SimpleNamespace(result=result)
            with self.subTest(field=key), self.assertRaises(AssertionError):
                runner.lowering(client, "forged", request, behavior)
        self.assertEqual(len(runner.receipt["checks"]), 1)

    def test_lowering_crash_or_unsupported_cannot_count_as_mutant_detection(self):
        from biocompiler.core_client import CoreRejected, CoreUnsupported, Diagnostic

        runner = campaign.Campaign({"checks": []})
        client = SimpleNamespace(role="verify")
        for status, code, exception in (("error", "internal_error", CoreRejected),
                                        ("unsupported", "lowering_operation", CoreUnsupported)):
            response = SimpleNamespace(status=status, result=None,
                                       diagnostics=(Diagnostic(code, "Failure", None),))
            def reject(**_):
                raise exception(response)
            client.verify_lowering = reject
            with self.assertRaises(AssertionError):
                runner.lowering_rejection(client, "changed-operator", {}, {}, "lowering_operation")
        self.assertEqual(runner.receipt["checks"], [])


class ComponentCapabilityConformanceTests(unittest.TestCase):
    """Exact additive transport contract; no native invocation or policy evaluation."""

    @staticmethod
    def capabilities(role):
        operations, scopes, profiles, claim = campaign.capability_contract(role)
        return {"operations": operations, "validation_scopes": scopes, "profiles": profiles,
                "claim_scope": claim, "canonicalization": "python-json-v1",
                "intent_schemas": ["biocompiler.intent.v0.1"], "limits": deepcopy(campaign.LIMITS),
                "schema_version": "biocompiler.core_capabilities.v1"}

    def test_component_operations_are_additive_to_exact_legacy_contract(self):
        import hashlib
        # Canonical complete legacy contracts reviewed from the unmodified
        # capability-construction block at 5a45; ordered scopes/operations kept.
        legacy = {"verify": "68aa0fd8f135229fa8d680ffa34e20279269fa1c79462a2c72573308144c8bd5",
                  "core": "ffab38b0ce113569e5926e038eed09b110f785c812d1fd16a31cab1e345d2d3e"}
        component = ["check-policy-component-material", "replay-policy-component-material", "export-policy-component-material"]
        self.assertEqual(campaign.COMPONENT_MATERIAL_PROFILE["operations"], component)
        for role in ("verify", "core"):
            actual = self.capabilities(role)
            campaign.check_capabilities(actual, role)
            actual = without_grounded_helper(without_multi_member(without_two_observations(without_prerequisites(without_instance(without_selection(actual))))))
            self.assertEqual([name for name in actual["operations"] if "policy-component-material" in name],
                             component + (["compile-policy-component-material"] if role == "core" else []))
            reduced = {"operations": [name for name in actual["operations"] if name not in component + ["compile-policy-component-material"]],
                       "scopes": [value for value in actual["validation_scopes"] if value != "policy-component-mrna-v0.1"],
                       "profiles": {key: value for key, value in actual["profiles"].items()
                                    if key not in {"policy_component_material", "policy_component_material_producer"}},
                       "claim": actual["claim_scope"]}
            self.assertEqual(hashlib.sha256(campaign.canonical(reduced).encode()).hexdigest(), legacy[role])
            self.assertEqual(actual["validation_scopes"].count("policy-component-mrna-v0.1"), 1)
            self.assertEqual("policy_component_material_producer" in actual["profiles"], role == "core")

    def test_missing_duplicate_extra_or_wrong_role_operation_rejects(self):
        for role in ("verify", "core"):
            original = self.capabilities(role)
            mutations = [lambda row: row["operations"].remove("check-policy-component-material"),
                         lambda row: row["operations"].append("export-policy-component-material"),
                         lambda row: row["operations"].append("unreviewed-component-route")]
            mutations.append((lambda row: row["operations"].append("compile-policy-component-material")) if role == "verify"
                             else (lambda row: row["operations"].remove("compile-policy-component-material")))
            for mutation in mutations:
                changed = deepcopy(original)
                mutation(changed)
                with self.subTest(role=role), self.assertRaisesRegex(AssertionError, "Missing or untested advertised operation"):
                    campaign.check_capabilities(changed, role)

    def test_profile_scope_and_verify_producer_mutants_reject(self):
        for role in ("verify", "core"):
            for mutation, reason in (
                (lambda row: row["profiles"].pop("policy_component_material"), "profiles"),
                (lambda row: row["profiles"]["policy_component_material"].update(artifact="accepted"), "profiles"),
                (lambda row: row["validation_scopes"].remove("policy-component-mrna-v0.1"), "validation_scopes"),
                (lambda row: row["validation_scopes"].reverse(), "validation_scopes"),
            ):
                changed = deepcopy(self.capabilities(role)); mutation(changed)
                with self.subTest(role=role, reason=reason), self.assertRaisesRegex(AssertionError, "Capability contract differs: " + reason):
                    campaign.check_capabilities(changed, role)
        changed = self.capabilities("verify")
        changed["profiles"]["policy_component_material_producer"] = deepcopy(campaign.COMPONENT_MATERIAL_PRODUCER_PROFILE)
        with self.assertRaisesRegex(AssertionError, "profiles"):
            campaign.check_capabilities(changed, "verify")
        changed = self.capabilities("core")
        changed["profiles"].pop("policy_component_material_producer")
        with self.assertRaisesRegex(AssertionError, "profiles"):
            campaign.check_capabilities(changed, "core")
        with self.assertRaisesRegex(AssertionError, "Unknown native executable role"):
            campaign.capability_contract("foreign")


class SelectionCapabilityConformanceTests(unittest.TestCase):
    capabilities = staticmethod(ComponentCapabilityConformanceTests.capabilities)

    def test_selection_is_additive_to_complete_prior_contract(self):
        # Exact ordered complete contracts immediately before this additive
        # correction at 3b679; no prior operation, profile or claim is repinned.
        previous = {"core": "e8caf4569a5e5d5358896c2883115e5d7a7a99e90e5df32add6eb5c28b2a6931",
                    "verify": "48dc126316ae17f2ee26dedf1c3d07eeb7b27fa79af6e0173f47eb4a087db5bb"}
        self.assertEqual(campaign.COMPONENT_SELECTION_PROFILE["operations"], _SELECTION_OPERATIONS[:3])
        self.assertEqual(campaign.COMPONENT_SELECTION_PRODUCER_PROFILE,
                         {**campaign.COMPONENT_SELECTION_PROFILE, "operations": _SELECTION_OPERATIONS[3:],
                          "artifact": "withheld", "generation_work": "shared_original_scope"})
        for role in ("core", "verify"):
            actual = self.capabilities(role)
            campaign.check_capabilities(actual, role)
            self.assertEqual([name for name in actual["operations"] if name in _SELECTION_OPERATIONS],
                             _SELECTION_OPERATIONS if role == "core" else _SELECTION_OPERATIONS[:3])
            self.assertEqual(actual["validation_scopes"].count("policy-component-selection-mrna-v0.1"), 1)
            self.assertEqual("policy_component_selection_producer" in actual["profiles"], role == "core")
            reduced = without_grounded_helper(without_multi_member(without_two_observations(without_prerequisites(without_instance(without_selection(actual))))))
            old = {"operations": reduced["operations"], "scopes": reduced["validation_scopes"],
                   "profiles": reduced["profiles"], "claim": reduced["claim_scope"]}
            self.assertEqual(campaign.digest(campaign.canonical(old)), previous[role])

    def test_selection_capability_omissions_duplicates_promotions_and_wrong_role_reject(self):
        for role in ("core", "verify"):
            changes = [
                lambda row: row["operations"].remove("check-policy-component-selection"),
                lambda row: row["operations"].append("export-policy-component-selection"),
                lambda row: row["profiles"].pop("policy_component_selection"),
                lambda row: row["profiles"]["policy_component_selection"].update(empirical="assessed"),
                lambda row: row["validation_scopes"].remove("policy-component-selection-mrna-v0.1"),
            ]
            changes += ([lambda row: row["operations"].remove("compile-policy-component-selection"),
                         lambda row: row["profiles"].pop("policy_component_selection_producer"),
                         lambda row: row["profiles"]["policy_component_selection_producer"].update(artifact="accepted")]
                        if role == "core" else
                        [lambda row: row["operations"].append("compile-policy-component-selection"),
                         lambda row: row["profiles"].update(policy_component_selection_producer=
                                                          deepcopy(campaign.COMPONENT_SELECTION_PRODUCER_PROFILE))])
            for index, change in enumerate(changes):
                value = deepcopy(self.capabilities(role))
                change(value)
                with self.subTest(role=role, change=index), self.assertRaises(AssertionError):
                    campaign.check_capabilities(value, role)

    @staticmethod
    def response(role, operation):
        unsupported = role == "verify" and operation == "compile-policy-component-selection"
        return {"protocol": campaign.PROTOCOL, "request_id": "conformance", "operation": operation,
                "core": {"implementation": "ocaml", "version": campaign.CORE_VERSION,
                         "protocol": campaign.PROTOCOL, "executable": role},
                "status": "unsupported" if unsupported else "error", "result": None,
                "diagnostics": [{"code": "unsupported_operation" if unsupported else "missing_field",
                                 "message": "Rejected", "path": "/operation" if unsupported else "/payload"}]}

    def test_all_selection_routes_use_raw_native_dispatch_with_exact_rejections(self):
        receipt = {"checks": []}
        runner = campaign.Campaign(receipt)
        calls = []
        def exchange(executable, request, timeout, cancelled):
            value = json.loads(request)
            self.assertEqual(value["payload"], {})
            self.assertEqual(value["protocol"], campaign.PROTOCOL)
            self.assertEqual(value["request_id"], "conformance")
            self.assertIsNone(cancelled)
            calls.append((executable, value["operation"]))
            response = self.response(executable, value["operation"])
            return campaign.canonical(response).encode(), 3 if response["status"] == "unsupported" else 2
        with patch.object(campaign, "_exchange", side_effect=exchange):
            for role in ("core", "verify"):
                # No SDK call method is provided: the producer rejection must
                # come from the native protocol, not local role negotiation.
                runner.component_selection_routes(SimpleNamespace(role=role, executable=role, timeout_seconds=60))
        self.assertEqual(calls, [(role, operation) for role in ("core", "verify") for operation in _SELECTION_OPERATIONS])
        self.assertEqual(receipt["checks"], [
            {"role": role, "group": "selection_route_rejection", "case": operation, "status": "pass",
             "error_code": "unsupported_operation" if role == "verify" and operation == _SELECTION_OPERATIONS[-1]
             else "missing_field"}
            for role, operation in calls])

    def test_wrong_selection_native_status_result_diagnostic_identity_or_exit_never_passes(self):
        changes = [lambda row: row.update(status="ok"), lambda row: row.update(result={"accepted": True}),
                   lambda row: row.update(request_id="other"), lambda row: row.update(operation="other"),
                   lambda row: row["diagnostics"][0].update(code="internal_error"),
                   lambda row: row["diagnostics"][0].update(path="/other"),
                   lambda row: row["diagnostics"].append(deepcopy(row["diagnostics"][0])),
                   lambda row: row["core"].update(executable="other"),
                   lambda row: row.update(status="unsupported"),
                   lambda row: None]
        for role in ("core", "verify"):
            for failed_operation in _SELECTION_OPERATIONS:
                for index, change in enumerate(changes):
                    receipt = {"checks": []}
                    def exchange(executable, request, timeout, cancelled):
                        operation = json.loads(request)["operation"]
                        response = self.response(role, operation)
                        exit_code = 3 if response["status"] == "unsupported" else 2
                        if operation == failed_operation:
                            change(response)
                            if index == 8 and response["status"] == "unsupported" and exit_code == 3:
                                response["status"] = "error"
                            if index == 9:
                                exit_code = 0
                        return campaign.canonical(response).encode(), exit_code
                    with self.subTest(role=role, operation=failed_operation, change=index), \
                            patch.object(campaign, "_exchange", side_effect=exchange), self.assertRaises(AssertionError):
                        campaign.Campaign(receipt).component_selection_routes(
                            SimpleNamespace(role=role, executable=role, timeout_seconds=60))
                    self.assertEqual(len(receipt["checks"]), _SELECTION_OPERATIONS.index(failed_operation))


class InstanceCapabilityConformanceTests(unittest.TestCase):
    """Compare the additive expectation with reviewed native source declarations."""

    capabilities = staticmethod(ComponentCapabilityConformanceTests.capabilities)

    def test_instance_profile_is_exact_and_preserves_shared_operation_routes(self):
        expected = {**campaign.COMPONENT_MATERIAL_PROFILE,
                    "request_schema": "biocompiler.policy_component_material_request.v0.2",
                    "implementation": "biocompiler.ocaml.policy_instance_component_material.v0.1",
                    "validation_scope": "policy-instance-component-mrna-v0.1"}
        producer = {"operations": ["compile-policy-component-material"],
                    "implementation": expected["implementation"],
                    "validation_scope": expected["validation_scope"]}
        for role in ("core", "verify"):
            actual = self.capabilities(role)
            campaign.check_capabilities(actual, role)
            self.assertEqual(actual["profiles"]["policy_instance_material"], expected)
            if role == "core":
                self.assertEqual(actual["profiles"]["policy_instance_material_producer"], producer)
            else:
                self.assertNotIn("policy_instance_material_producer", actual["profiles"])
            start = actual["validation_scopes"].index("policy-component-mrna-v0.1")
            self.assertEqual(actual["validation_scopes"][start:start + 7], [
                "policy-component-mrna-v0.1", "policy-instance-component-mrna-v0.1",
                "policy-instance-prerequisite-mrna-v0.1", "policy-instance-two-observation-prerequisite-mrna-v0.1", "policy-multi-member-prerequisite-mrna-v0.1", "policy-grounded-helper-prerequisite-mrna-v0.1", "policy-component-selection-mrna-v0.1"])
            self.assertEqual(actual["validation_scopes"].count(expected["validation_scope"]), 1)
            self.assertEqual(actual["operations"], without_instance(actual)["operations"])
            self.assertEqual(actual["operations"].count("check-policy-component-material"), 1)
            self.assertEqual(actual["operations"].count("compile-policy-component-material"), role == "core")

    def test_reviewed_native_component_advertisement_matches_campaign_census(self):
        # This is a closed source-shape check, not an OCaml evaluator. Any new
        # component scope/profile must update this independently reviewed set.
        service = (campaign.ROOT / "core/lib/service/service.ml").read_text().split("type scoped_reply", 1)[0]
        producer = (campaign.ROOT / "core/lib/producer_service/producer_service.ml").read_text()
        producer = producer.split("let capabilities executable request =", 1)[1].split("let handle executable", 1)[0]
        material = (campaign.ROOT / "core/lib/service/policy_component_material_service.ml").read_text()
        request = (campaign.ROOT / "core/lib/domain/policy_component_material_request.ml").read_text()
        scopes = service.split('"validation_scopes",', 1)[1].split('"profiles",', 1)[0]
        scope_refs = re.findall(r"Policy_component_(?:material|selection)_service\.\w+", scopes)
        historical_scope_refs = [
            "Policy_component_material_service.validation_scope",
            "Policy_component_material_service.instance_validation_scope",
            "Policy_component_material_service.prerequisite_validation_scope",
            "Policy_component_material_service.two_observation_validation_scope",
            "Policy_component_material_service.multi_member_validation_scope",
            "Policy_component_material_service.grounded_helper_validation_scope",
            "Policy_component_selection_service.validation_scope"]
        new_scope_refs = [
            "Policy_component_material_service.step_quantitative_validation_scope",
            "Policy_component_material_service.transfer_pair_validation_scope",
            "Policy_component_material_service.transfer_network_validation_scope",
            "Policy_component_material_service.composition_validation_scope",
            "Policy_component_material_service.network_validation_scope",
            "Policy_component_material_service.finite_machine_validation_scope",
            "Policy_component_material_service.quantitative_validation_scope"]
        self.assertEqual(scope_refs, new_scope_refs[:4] + historical_scope_refs[:-1]
                         + new_scope_refs[4:] + historical_scope_refs[-1:])
        self.assertEqual([name for name in scope_refs if name not in new_scope_refs], historical_scope_refs)
        pattern = r'"(policy_[a-z_]+)",\s*(?:Bioc_service\.)?(Policy_component_(?:material|selection)_service)\.(\w+)'
        base = re.findall(pattern, service)
        additions = re.findall(pattern, producer)
        historical_profiles = {
            "policy_component_material": ("Policy_component_material_service", "profile"),
            "policy_instance_material": ("Policy_component_material_service", "instance_profile"),
            "policy_prerequisite_material": ("Policy_component_material_service", "prerequisite_profile"),
            "policy_two_observation_material": ("Policy_component_material_service", "two_observation_profile"),
            "policy_multi_member_material": ("Policy_component_material_service", "multi_member_profile"),
            "policy_grounded_helper_material": ("Policy_component_material_service", "grounded_helper_profile"),
            "policy_component_selection": ("Policy_component_selection_service", "profile")}
        new_profiles = {
            "policy_finite_machine_material": ("Policy_component_material_service", "finite_machine_profile"),
            "policy_network_material": ("Policy_component_material_service", "network_profile"),
            "policy_quantitative_material": ("Policy_component_material_service", "quantitative_profile"),
            "policy_step_quantitative_material": ("Policy_component_material_service", "step_quantitative_profile"),
            "policy_transfer_pair_material": ("Policy_component_material_service", "transfer_pair_profile"),
            "policy_transfer_network_material": ("Policy_component_material_service", "transfer_network_profile"),
            "policy_coupled_quantitative_material": ("Policy_component_material_service", "composition_profile")}
        historical_producers = {
            "policy_component_material_producer": ("Policy_component_material_service", "producer_profile"),
            "policy_instance_material_producer": ("Policy_component_material_service", "instance_producer_profile"),
            "policy_prerequisite_material_producer": ("Policy_component_material_service", "prerequisite_producer_profile"),
            "policy_two_observation_material_producer": ("Policy_component_material_service", "two_observation_producer_profile"),
            "policy_multi_member_material_producer": ("Policy_component_material_service", "multi_member_producer_profile"),
            "policy_grounded_helper_material_producer": ("Policy_component_material_service", "grounded_helper_producer_profile"),
            "policy_component_selection_producer": ("Policy_component_selection_service", "producer_profile")}
        new_producers = {
            "policy_finite_machine_material_producer": ("Policy_component_material_service", "finite_machine_producer_profile"),
            "policy_network_material_producer": ("Policy_component_material_service", "network_producer_profile"),
            "policy_quantitative_material_producer": ("Policy_component_material_service", "quantitative_producer_profile"),
            "policy_step_quantitative_material_producer": ("Policy_component_material_service", "step_quantitative_producer_profile"),
            "policy_transfer_pair_material_producer": ("Policy_component_material_service", "transfer_pair_producer_profile"),
            "policy_transfer_network_material_producer": ("Policy_component_material_service", "transfer_network_producer_profile"),
            "policy_coupled_quantitative_material_producer": ("Policy_component_material_service", "composition_producer_profile")}
        self.assertEqual(dict((name, (module, value)) for name, module, value in base), historical_profiles | new_profiles)
        self.assertEqual(dict((name, (module, value)) for name, module, value in additions), historical_producers | new_producers)
        self.assertEqual((len(historical_profiles), len(historical_producers), len(new_profiles), len(new_producers)), (7, 7, 7, 7))
        self.assertEqual(len(base), 14)
        self.assertEqual(len(additions), 14)
        for role in ("core", "verify"):
            # The independently retained old campaign still checks exactly its
            # original seven families. The complete native inventory above also
            # rejects missing, duplicated or unreviewed newer declarations.
            expected_keys = set(historical_profiles) | (set(historical_producers) if role == "core" else set())
            actual = self.capabilities(role)
            actual_keys = {name for name in actual["profiles"]
                           if name.startswith(("policy_component_", "policy_instance_", "policy_prerequisite_", "policy_two_observation_", "policy_multi_member_", "policy_grounded_helper_"))}
            self.assertEqual(actual_keys, expected_keys)
            start = actual["validation_scopes"].index(campaign.COMPONENT_MATERIAL_SCOPE)
            self.assertEqual(actual["validation_scopes"][start:start + len(historical_scope_refs)], [
                "policy-component-mrna-v0.1", "policy-instance-component-mrna-v0.1",
                "policy-instance-prerequisite-mrna-v0.1", "policy-instance-two-observation-prerequisite-mrna-v0.1", "policy-multi-member-prerequisite-mrna-v0.1", "policy-grounded-helper-prerequisite-mrna-v0.1", "policy-component-selection-mrna-v0.1"])
        for name, expected in (("instance_implementation", campaign.INSTANCE_MATERIAL_PROFILE["implementation"]),
                               ("instance_validation_scope", campaign.INSTANCE_MATERIAL_PROFILE["validation_scope"]),
                               ("prerequisite_implementation", campaign.PREREQUISITE_MATERIAL_PROFILE["implementation"]),
                               ("prerequisite_validation_scope", campaign.PREREQUISITE_MATERIAL_PROFILE["validation_scope"]),
                               ("two_observation_implementation", campaign.TWO_OBSERVATION_MATERIAL_PROFILE["implementation"]),
                               ("two_observation_validation_scope", campaign.TWO_OBSERVATION_MATERIAL_PROFILE["validation_scope"]),
                               ("multi_member_implementation", campaign.MULTI_MEMBER_MATERIAL_PROFILE["implementation"]),
                               ("multi_member_validation_scope", campaign.MULTI_MEMBER_MATERIAL_PROFILE["validation_scope"]),
                               ("grounded_helper_implementation", campaign.GROUNDED_HELPER_MATERIAL_PROFILE["implementation"]),
                               ("grounded_helper_validation_scope", campaign.GROUNDED_HELPER_MATERIAL_PROFILE["validation_scope"])):
            self.assertEqual(re.findall(r"let " + name + r'\s*=\s*"([^"]+)"', material), [expected])
        self.assertEqual(re.findall(r'let instance_schema_version\s*=\s*"([^"]+)"', request),
                         [campaign.INSTANCE_MATERIAL_PROFILE["request_schema"]])
        self.assertEqual(re.findall(r'let prerequisite_schema_version\s*=\s*"([^"]+)"', request),
                         [campaign.PREREQUISITE_MATERIAL_PROFILE["request_schema"]])
        self.assertEqual(re.findall(r'let two_observation_schema_version\s*=\s*"([^"]+)"', request),
                         [campaign.TWO_OBSERVATION_MATERIAL_PROFILE["request_schema"]])
        self.assertEqual(re.findall(r'let multi_member_schema_version\s*=\s*"([^\"]+)"', request),
                         [campaign.MULTI_MEMBER_MATERIAL_PROFILE["request_schema"]])

    def test_instance_omissions_wrong_roles_and_scope_order_reject(self):
        for role in ("core", "verify"):
            changes = [
                lambda row: row["profiles"].pop("policy_instance_material"),
                lambda row: row["profiles"]["policy_instance_material"].update(request_schema=campaign.COMPONENT_MATERIAL_PROFILE["request_schema"]),
                lambda row: row["profiles"]["policy_instance_material"].update(empirical="assessed"),
                lambda row: row["validation_scopes"].remove("policy-instance-component-mrna-v0.1"),
                lambda row: row["validation_scopes"].append("policy-instance-component-mrna-v0.1"),
            ]
            def move_scope(row):
                row["validation_scopes"].remove("policy-instance-component-mrna-v0.1")
                row["validation_scopes"].append("policy-instance-component-mrna-v0.1")
            changes.append(move_scope)
            if role == "core":
                changes += [lambda row: row["profiles"].pop("policy_instance_material_producer"),
                            lambda row: row["profiles"]["policy_instance_material_producer"].update(
                                operations=["check-policy-component-material"])]
            else:
                changes.append(lambda row: row["profiles"].update(policy_instance_material_producer=
                               deepcopy(campaign.INSTANCE_MATERIAL_PRODUCER_PROFILE)))
            for index, change in enumerate(changes):
                actual = deepcopy(self.capabilities(role))
                change(actual)
                with self.subTest(role=role, mutation=index), self.assertRaisesRegex(AssertionError, "Capability contract differs:"):
                    campaign.check_capabilities(actual, role)


class PrerequisiteCapabilityConformanceTests(unittest.TestCase):
    capabilities = staticmethod(ComponentCapabilityConformanceTests.capabilities)

    def test_prerequisite_profile_is_exact_and_keeps_the_shared_routes(self):
        expected = {**campaign.COMPONENT_MATERIAL_PROFILE,
                    "request_schema": "biocompiler.policy_component_material_request.v0.3",
                    "implementation": "biocompiler.ocaml.policy_instance_prerequisite_material.v0.1",
                    "validation_scope": "policy-instance-prerequisite-mrna-v0.1"}
        producer = {"operations": ["compile-policy-component-material"],
                    "implementation": expected["implementation"],
                    "validation_scope": expected["validation_scope"]}
        for role in ("core", "verify"):
            actual = self.capabilities(role)
            campaign.check_capabilities(actual, role)
            self.assertEqual(actual["profiles"]["policy_prerequisite_material"], expected)
            if role == "core":
                self.assertEqual(actual["profiles"]["policy_prerequisite_material_producer"], producer)
            else:
                self.assertNotIn("policy_prerequisite_material_producer", actual["profiles"])
            self.assertEqual(actual["operations"], without_prerequisites(actual)["operations"])
            self.assertEqual(actual["validation_scopes"].count(expected["validation_scope"]), 1)

    def test_prerequisite_omissions_wrong_roles_and_scope_order_reject(self):
        for role in ("core", "verify"):
            changes = [
                lambda row: row["profiles"].pop("policy_prerequisite_material"),
                lambda row: row["profiles"].update(policy_prerequisite_material=deepcopy(campaign.INSTANCE_MATERIAL_PROFILE)),
                lambda row: row["profiles"]["policy_prerequisite_material"].update(empirical="assessed"),
                lambda row: row["validation_scopes"].remove("policy-instance-prerequisite-mrna-v0.1"),
                lambda row: row["validation_scopes"].append("policy-instance-prerequisite-mrna-v0.1"),
            ]
            def move_scope(row):
                row["validation_scopes"].remove("policy-instance-prerequisite-mrna-v0.1")
                row["validation_scopes"].append("policy-instance-prerequisite-mrna-v0.1")
            changes.append(move_scope)
            if role == "core":
                changes += [lambda row: row["profiles"].pop("policy_prerequisite_material_producer"),
                            lambda row: row["profiles"]["policy_prerequisite_material_producer"].update(
                                operations=["check-policy-component-material"])]
            else:
                changes.append(lambda row: row["profiles"].update(policy_prerequisite_material_producer=
                               deepcopy(campaign.PREREQUISITE_MATERIAL_PRODUCER_PROFILE)))
            for index, change in enumerate(changes):
                actual = deepcopy(self.capabilities(role))
                change(actual)
                with self.subTest(role=role, mutation=index), self.assertRaisesRegex(AssertionError, "Capability contract differs:"):
                    campaign.check_capabilities(actual, role)


class TwoObservationCapabilityConformanceTests(unittest.TestCase):
    capabilities = staticmethod(ComponentCapabilityConformanceTests.capabilities)

    def test_two_observation_profile_is_exact_and_keeps_the_shared_routes(self):
        expected = {**campaign.COMPONENT_MATERIAL_PROFILE,
                    "request_schema": "biocompiler.policy_component_material_request.v0.4",
                    "implementation": "biocompiler.ocaml.policy_instance_two_observation_prerequisite_material.v0.1",
                    "validation_scope": "policy-instance-two-observation-prerequisite-mrna-v0.1"}
        producer = {"operations": ["compile-policy-component-material"],
                    "implementation": expected["implementation"],
                    "validation_scope": expected["validation_scope"]}
        for role in ("core", "verify"):
            actual = self.capabilities(role)
            campaign.check_capabilities(actual, role)
            self.assertEqual(actual["profiles"]["policy_two_observation_material"], expected)
            if role == "core":
                self.assertEqual(actual["profiles"]["policy_two_observation_material_producer"], producer)
            else:
                self.assertNotIn("policy_two_observation_material_producer", actual["profiles"])
            self.assertEqual(actual["operations"], without_two_observations(actual)["operations"])
            self.assertEqual(actual["validation_scopes"].count(expected["validation_scope"]), 1)

    def test_two_observation_omissions_wrong_roles_and_scope_order_reject(self):
        for role in ("core", "verify"):
            changes = [
                lambda row: row["profiles"].pop("policy_two_observation_material"),
                lambda row: row["profiles"].update(policy_two_observation_material=deepcopy(campaign.INSTANCE_MATERIAL_PROFILE)),
                lambda row: row["profiles"]["policy_two_observation_material"].update(empirical="assessed"),
                lambda row: row["validation_scopes"].remove("policy-instance-two-observation-prerequisite-mrna-v0.1"),
                lambda row: row["validation_scopes"].append("policy-instance-two-observation-prerequisite-mrna-v0.1"),
            ]
            def move_scope(row):
                row["validation_scopes"].remove("policy-instance-two-observation-prerequisite-mrna-v0.1")
                row["validation_scopes"].append("policy-instance-two-observation-prerequisite-mrna-v0.1")
            changes.append(move_scope)
            if role == "core":
                changes += [lambda row: row["profiles"].pop("policy_two_observation_material_producer"),
                            lambda row: row["profiles"]["policy_two_observation_material_producer"].update(
                                operations=["check-policy-component-material"])]
            else:
                changes.append(lambda row: row["profiles"].update(policy_two_observation_material_producer=
                               deepcopy(campaign.TWO_OBSERVATION_MATERIAL_PRODUCER_PROFILE)))
            for index, change in enumerate(changes):
                actual = deepcopy(self.capabilities(role))
                change(actual)
                with self.subTest(role=role, mutation=index), self.assertRaisesRegex(AssertionError, "Capability contract differs:"):
                    campaign.check_capabilities(actual, role)


class MultiMemberCapabilityConformanceTests(unittest.TestCase):
    capabilities = staticmethod(ComponentCapabilityConformanceTests.capabilities)

    def test_multi_member_profile_is_exact_and_keeps_the_shared_routes(self):
        expected = {**campaign.COMPONENT_MATERIAL_PROFILE,
                    "request_schema": "biocompiler.policy_component_material_request.v0.5",
                    "implementation": "biocompiler.ocaml.policy_multi_member_prerequisite_material.v0.1",
                    "validation_scope": "policy-multi-member-prerequisite-mrna-v0.1"}
        producer = {"operations": ["compile-policy-component-material"],
                    "implementation": expected["implementation"],
                    "validation_scope": expected["validation_scope"]}
        for role in ("core", "verify"):
            actual = self.capabilities(role)
            campaign.check_capabilities(actual, role)
            self.assertEqual(actual["profiles"]["policy_multi_member_material"], expected)
            if role == "core":
                self.assertEqual(actual["profiles"]["policy_multi_member_material_producer"], producer)
            else:
                self.assertNotIn("policy_multi_member_material_producer", actual["profiles"])
            self.assertEqual(actual["operations"], without_multi_member(actual)["operations"])
            self.assertEqual(actual["validation_scopes"].count(expected["validation_scope"]), 1)

    def test_multi_member_omissions_wrong_roles_and_scope_order_reject(self):
        for role in ("core", "verify"):
            changes = [
                lambda row: row["profiles"].pop("policy_multi_member_material"),
                lambda row: row["profiles"].update(policy_multi_member_material=deepcopy(campaign.INSTANCE_MATERIAL_PROFILE)),
                lambda row: row["profiles"]["policy_multi_member_material"].update(empirical="assessed"),
                lambda row: row["validation_scopes"].remove("policy-multi-member-prerequisite-mrna-v0.1"),
                lambda row: row["validation_scopes"].append("policy-multi-member-prerequisite-mrna-v0.1"),
            ]
            def move_scope(row):
                row["validation_scopes"].remove("policy-multi-member-prerequisite-mrna-v0.1")
                row["validation_scopes"].append("policy-multi-member-prerequisite-mrna-v0.1")
            changes.append(move_scope)
            if role == "core":
                changes += [lambda row: row["profiles"].pop("policy_multi_member_material_producer"),
                            lambda row: row["profiles"]["policy_multi_member_material_producer"].update(
                                operations=["check-policy-component-material"])]
            else:
                changes.append(lambda row: row["profiles"].update(policy_multi_member_material_producer=
                               deepcopy(campaign.MULTI_MEMBER_MATERIAL_PRODUCER_PROFILE)))
            for index, change in enumerate(changes):
                actual = deepcopy(self.capabilities(role))
                change(actual)
                with self.subTest(role=role, mutation=index), self.assertRaisesRegex(AssertionError, "Capability contract differs:"):
                    campaign.check_capabilities(actual, role)


class GroundedHelperCapabilityConformanceTests(unittest.TestCase):
    capabilities = staticmethod(ComponentCapabilityConformanceTests.capabilities)

    def test_grounded_helper_profile_is_exact_and_keeps_the_shared_routes(self):
        expected = {**campaign.COMPONENT_MATERIAL_PROFILE,
                    "request_schema": "biocompiler.policy_component_material_request.v0.6",
                    "implementation": "biocompiler.ocaml.policy_grounded_helper_prerequisite_material.v0.1",
                    "validation_scope": "policy-grounded-helper-prerequisite-mrna-v0.1"}
        producer = {"operations": ["compile-policy-component-material"],
                    "implementation": expected["implementation"],
                    "validation_scope": expected["validation_scope"]}
        for role in ("core", "verify"):
            actual = self.capabilities(role)
            campaign.check_capabilities(actual, role)
            self.assertEqual(actual["profiles"]["policy_grounded_helper_material"], expected)
            if role == "core":
                self.assertEqual(actual["profiles"]["policy_grounded_helper_material_producer"], producer)
            else:
                self.assertNotIn("policy_grounded_helper_material_producer", actual["profiles"])
            self.assertEqual(actual["operations"], without_grounded_helper(actual)["operations"])
            self.assertEqual(actual["validation_scopes"].count(expected["validation_scope"]), 1)

    def test_grounded_helper_omissions_wrong_roles_and_scope_order_reject(self):
        for role in ("core", "verify"):
            changes = [
                lambda row: row["profiles"].pop("policy_grounded_helper_material"),
                lambda row: row["profiles"].update(policy_grounded_helper_material=deepcopy(campaign.INSTANCE_MATERIAL_PROFILE)),
                lambda row: row["profiles"]["policy_grounded_helper_material"].update(empirical="assessed"),
                lambda row: row["validation_scopes"].remove("policy-grounded-helper-prerequisite-mrna-v0.1"),
                lambda row: row["validation_scopes"].append("policy-grounded-helper-prerequisite-mrna-v0.1"),
            ]
            def move_scope(row):
                row["validation_scopes"].remove("policy-grounded-helper-prerequisite-mrna-v0.1")
                row["validation_scopes"].append("policy-grounded-helper-prerequisite-mrna-v0.1")
            changes.append(move_scope)
            if role == "core":
                changes += [lambda row: row["profiles"].pop("policy_grounded_helper_material_producer"),
                            lambda row: row["profiles"]["policy_grounded_helper_material_producer"].update(
                                operations=["check-policy-component-material"])]
            else:
                changes.append(lambda row: row["profiles"].update(policy_grounded_helper_material_producer=
                               deepcopy(campaign.GROUNDED_HELPER_MATERIAL_PRODUCER_PROFILE)))
            for index, change in enumerate(changes):
                actual = deepcopy(self.capabilities(role))
                change(actual)
                with self.subTest(role=role, mutation=index), self.assertRaisesRegex(AssertionError, "Capability contract differs:"):
                    campaign.check_capabilities(actual, role)


if __name__ == "__main__":
    unittest.main()
