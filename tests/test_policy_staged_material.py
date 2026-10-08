"""Pure original-authority and adversarial transport checks; no native acceptance."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from biocompiler import policy as p
from biocompiler import core_policy_implementation as implementation
from biocompiler import core_policy_material as material
from biocompiler.core_client import CORE_VERSION, CoreProtocolError, CoreResponse
from biocompiler.policy.component_material import prepare_request
from tools import generate_policy_staged_material_fixture as generator
from tests import test_core_policy_implementation as peer

ROOT = Path(__file__).resolve().parents[1]


def inert_staged_response():
    """An inert peer retains packets; it does not lower or execute a graph."""
    request = generator.realization()
    candidate = peer.candidate(request)
    candidate["implementation"].update(profile="biocompiler.policy_staged_primitives.v0.1",
                                       observable_profile="biocompiler.policy_staged_observables.v0.1")
    candidate["binding"].update(schema_version="biocompiler.policy_implementation_binding.v0.2",
        profile="biocompiler.policy_staged_source_graph.v0.1", catalog_entry=request["catalog_bindings"][0]["entry_id"],
        rules=[], states=[], machines=[{"source": "regimen/stages", "bank": "machine/0"}],
        transitions=[{"source": "regimen/" + row[0], "gate": f"transition/{index}/gate", "arbiter": "arbiter/0",
                      "lane": index, "commit": f"transition/{index}/commit"} for index, row in enumerate(generator.TRANSITIONS)])
    payload = {"request": request, "candidate": candidate, "limits": peer.limits()}
    result = peer.result(payload)
    result["report"]["binding"].update(schema_version="biocompiler.policy_implementation_binding_report.v0.2",
        profile="biocompiler.policy_staged_source_graph.v0.1", observable_profile="biocompiler.policy_staged_observables.v0.1",
        state_encoding="exact_ordered_source_labels")
    result["report_fingerprint"] = peer.digest(result["report"])
    return payload, result


def response(result):
    return CoreResponse("inert-staged-peer", "check-policy-implementation", "ok", result, (), "verify", CORE_VERSION)


class StagedMaterialOriginalTests(unittest.TestCase):
    def test_complete_fixture_is_reproducible_from_declared_premises(self):
        expected = json.loads(generator.OUTPUT.read_text())
        self.assertEqual(generator.build(), expected)
        self.assertEqual(generator.realization(), json.loads(generator.REALIZATION.read_text()))
        original = expected["request"]
        self.assertEqual(p.to_data(generator.build_request()), original["implementation_request"]["document"])
        self.assertEqual(p.check(generator.build_request()).diagnostics, ())
        prepared = prepare_request(**{key: value for key, value in original.items() if key not in ("schema_version", "profile")})
        self.assertEqual(prepared, original)

    def test_independent_two_stage_premises_preserve_product_and_scope(self):
        packet = generator.build()
        request = packet["request"]
        declarations = {row["id"]: row for row in request["implementation_request"]["document"]["program"]["declarations"]}
        self.assertEqual(declarations["stage_one"]["contract"], declarations["stage_two"]["contract"])
        self.assertEqual(declarations["stage_one"]["parameters"], declarations["stage_two"]["parameters"])
        self.assertEqual(declarations["regimen/handoff"]["when"], p.to_data(p.TRUE))
        models = {row["identity"]["id"]: row for row in request["implementation_request"]["implementation_library"]["models"]}
        self.assertEqual(models["staged.primitive.true"]["body"]["replication"]["kind"], "encounter_slots")
        self.assertEqual(models["staged.primitive.product"]["body"]["replication"], {"kind": "executor"})
        links = request["composition_rule"]["body"]["links"]
        self.assertEqual(len(links), 12)
        self.assertEqual(links[0]["producer"], links[6]["producer"])
        self.assertNotEqual(links[2]["producer"], links[8]["producer"])

    def test_all_supplied_original_pins_and_immutable_material_are_complete(self):
        packet = generator.build()
        request = packet["request"]
        for value in [*request["component_library"]["components"], request["composition_rule"], *request["context"]["providers"],
                      *request["implementation_request"]["implementation_library"]["models"]]:
            self.assertEqual(value["identity"]["content_fingerprint"], generator.digest(value["body"]))
        self.assertEqual(request["context"]["record_layout"]["union_digest"], generator.digest(packet["expected"]["ordered_union"]))
        self.assertEqual(packet["expected"]["molecule"]["sequence"], "CCAUGGCUUAAGGAAAA")
        self.assertEqual(packet["expected"]["fasta"], ">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n")
        self.assertEqual(packet["expected"]["histories"], 5 ** 2)
        self.assertEqual(packet["expected"]["transitions"], sum([1, 1, 9, 25, 25, 25]))


class StagedComponentContextTransportTests(unittest.TestCase):
    def test_context_profile_is_bound_to_original_authority(self):
        # Inert transport packets only: no biological or native admission claim.
        from biocompiler import core_policy_component_material as component
        from tests import test_core_policy_component_material as packets
        original = packets.original()
        actual = packets.candidate(original)
        profile = "biocompiler.policy_staged_component_mrna.v0.1"
        original["context"]["profile"] = profile
        report = packets.report(original, actual, peer.limits())
        report["context"]["profile"] = profile
        component._leaves(original, actual, report)
        for changed_profile in (component.REQUEST_PROFILE, "unsupported"):
            changed = deepcopy(report)
            changed["context"]["profile"] = changed_profile
            with self.subTest(profile=changed_profile), self.assertRaises(CoreProtocolError):
                component._leaves(original, actual, changed)
        changed = deepcopy(original)
        changed["context"]["profile"] = "unsupported"
        report["context"]["profile"] = "unsupported"
        with self.assertRaisesRegex(CoreProtocolError, "unsupported profile"):
            component._leaves(changed, actual, report)


class StagedImplementationTransportTests(unittest.TestCase):
    def test_closed_staged_packet_retains_original_immutable_authority(self):
        payload, result = inert_staged_response()
        checked = implementation._result(response(result), payload)
        self.assertEqual(checked.result, result)
        checked.report["binding"]["state_encoding"] = "forged"
        self.assertEqual(checked.report["binding"]["state_encoding"], "exact_ordered_source_labels")

    def test_rehashed_mixed_profiles_or_incomplete_anchor_packets_are_rejected(self):
        mutations = [
            lambda result: result["report"]["binding"].update(profile="biocompiler.policy_exclusive_source_graph.v0.1"),
            lambda result: result["report"]["binding"].update(observable_profile="biocompiler.policy_truth_observables.v0.1"),
            lambda result: result["report"]["binding"].update(state_encoding="opaque_integer_states"),
            lambda result: result["candidate"]["implementation"].update(profile="biocompiler.policy_truth_primitives.v0.1"),
            lambda result: result["candidate"]["binding"].update(schema_version="biocompiler.policy_implementation_binding.v0.1"),
            lambda result: result["candidate"]["binding"]["machines"].clear(),
            lambda result: result["candidate"]["binding"]["transitions"].pop(),
            lambda result: result["candidate"]["binding"]["transitions"][0].update(source="foreign"),
            lambda result: result["candidate"]["binding"]["transitions"][0].update(lane=True),
            lambda result: result["candidate"]["binding"]["transitions"][0].update(lane=7),
            lambda result: result["candidate"]["binding"]["transitions"][0].update(extra="not_closed"),
        ]
        for mutate in mutations:
            payload, result = inert_staged_response()
            mutate(result)
            payload["candidate"] = deepcopy(result["candidate"])
            result["candidate_fingerprint"] = peer.digest(result["candidate"])
            result["invocation_fingerprint"] = peer.digest(payload)
            result["report"]["binding"]["implementation_fingerprint"] = peer.digest(result["candidate"]["implementation"])
            result["report"]["binding"]["proposed_binding_fingerprint"] = peer.digest(result["candidate"]["binding"])
            result["report_fingerprint"] = peer.digest(result["report"])
            with self.subTest(mutate=mutate), self.assertRaises(CoreProtocolError):
                implementation._result(response(result), payload)

    def test_legacy_packet_cannot_silently_represent_original_machines(self):
        payload, result = inert_staged_response()
        binding = result["report"]["binding"]
        binding.update(schema_version="biocompiler.policy_implementation_binding_report.v0.1",
            profile="biocompiler.policy_exclusive_source_graph.v0.1", observable_profile="biocompiler.policy_truth_observables.v0.1")
        del binding["state_encoding"]
        result["report_fingerprint"] = peer.digest(result["report"])
        with self.assertRaisesRegex(CoreProtocolError, "explicit staged"):
            implementation._result(response(result), payload)

    def test_machine_discharge_retains_exact_bounded_claim_and_fresh_pins(self):
        _, value = inert_staged_response()
        preservation = value["report"]
        binding = preservation["binding"]
        binding["source_admission"]["source_assessment"]["unresolved_obligations"] = ["machine_reachability_termination_and_progress"]
        evidence = {"preservation": peer.digest(preservation), "machine_binding": peer.digest(binding),
            "state_and_terminal_semantics": "exact_bounded_source_correspondence", "prefixes": "complete_original_domain",
            "retained_attempt_identity": "creation_fixed_injective", "universal_termination": "not_claimed", "progress": "declared_requirements_only"}
        report = {"preservation": preservation, "catalog": {}, "assembly_status": "pass", "context_status": "pass",
            "status": "checked_component_material", "all_original_obligations_discharged": True,
            "obligations": [{"obligation": "machine_reachability_termination_and_progress", "status": "discharged",
                "stage": "bounded_machine_semantics_and_declared_requirements", "evidence": evidence}]}
        def check(value):
            return material._obligations(value, material_key="assembly", accepted_status="checked_component_material",
                conjunction_stage="conditional_component_context_conjunction")
        check(report)
        for key, replacement in (("universal_termination", "proved"), ("progress", "all_transitions_terminate"),
                                 ("machine_binding", "0" * 64), ("preservation", "0" * 64)):
            changed = deepcopy(report)
            changed["obligations"][0]["evidence"][key] = replacement
            with self.subTest(key=key), self.assertRaises(CoreProtocolError):
                check(changed)
        changed = deepcopy(report)
        changed["obligations"][0].update(stage="bounded_implementation_preservation", evidence={"preservation": peer.digest(preservation)})
        with self.assertRaisesRegex(CoreProtocolError, "explicit bounded"):
            check(changed)
        changed = deepcopy(report)
        changed["obligations"][0]["obligation"] = "unrelated"
        changed["preservation"]["binding"]["source_admission"]["source_assessment"]["unresolved_obligations"] = ["unrelated"]
        with self.assertRaises(CoreProtocolError):
            check(changed)


if __name__ == "__main__":
    unittest.main()
