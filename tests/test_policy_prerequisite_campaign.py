"""Inert prerequisite campaign controls; no native acceptance or execution.

Typed source authoring uses original source files. Synthetic result records below
isolate receipt validation; they do not assert native semantics or admissibility.
"""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biocompiler import policy as p
from biocompiler import core_policy_component_material as transport
from tools import check_policy_component_material as shared
from tools import check_policy_prerequisite_material as campaign
from tests import test_policy_component_material_campaign as peer

ROOT = Path(__file__).resolve().parents[1]


def original(case="A"):
    name = "policy_material_request_v01.json" if case == "A" else "policy_material_state_v01.json"
    fixture = json.loads((ROOT / "core/test/data" / name).read_text())
    request = deepcopy(fixture["request"]["implementation_request"])
    request.update(schema_version="biocompiler.policy_realization_request.v0.2",
                   profile="biocompiler.policy_prerequisite_realization_inputs.v0.1")
    definitions = request["document"]["program"]["semantics"]["definitions"]
    definitions.append({"$type": "SemanticDefinition", "id": "fixture.prerequisite_environment", "version": "1",
        "category": "environment", "meaning": "Supplied exact finite environment prerequisite; no new source behavior or empirical evidence.",
        "parameters": [], "result": None, "clauses": [], "assumptions": [], "executor_kind": None, "subject_kind": None})
    entry = request["document"]["implementations"]["implementations"][0]
    entry["dependencies"] = [deepcopy(request["document"]["deployment"]["bindings"][0]["chassis"]["interfaces"][0])]
    request["catalog_bindings"][0]["entry_digest"] = campaign.canonical_digest(entry)
    return request, fixture["limits"]


def outer(case="A"):
    implementation, limits = original(case)
    request = {"schema_version": transport.PREREQUISITE_REQUEST_SCHEMA,
        "profile": transport.PREREQUISITE_REQUEST_PROFILE, "implementation_request": implementation,
        "input_bindings": [], "resource_bindings": [],
        **{key: {"inert_authority": key} for key in
           ("component_library", "composition_rule", "catalog_binding", "context", "budgets")}}
    request["context"]["profile"] = transport.PREREQUISITE_REQUEST_PROFILE
    return request, limits


def packet():
    cases = []
    for label in ("A", "B"):
        request, limits = outer(label)
        cases.append({"id": label, "request": request, "limits": limits,
            "expected": {"sequence": "CCAUGGCUUAAGGAAAA", "molecules": [], "carrier_projections": [],
                "link_projections": [], "histories": 9, "transitions": 47, "prefixes_started": 48,
                "obligations": deepcopy(campaign.OBLIGATIONS), "prerequisite_closure": {"inert": True}}})
    return {"schema_version": campaign.FIXTURE_SCHEMA, "status": "source_declarations_only", "acceptance": False,
            "source_sha256": {name: campaign.digest_file(ROOT / name) for name in campaign.INPUTS}, "cases": cases}


def result_and_case():
    expected = {"molecules": [{"sequence": "CCAUGGCUUAAGGAAAA"}], "carrier_projections": [], "link_projections": [],
                "prerequisite_closure": {"graph": {"roots": ["literal root"], "edges": ["literal edge"]},
                    "pending_dependencies": ["original dependency"], "providers": ["original provider"],
                    "instances": ["select_edge", "control", "exclude_edge"], "input_allocations": ["input"],
                    "resource_allocations": ["reservation"]}}
    assembly = {"carrier_projections": [], "link_projections": []}
    closure = {**deepcopy(expected["prerequisite_closure"]), "assembly_fingerprint": campaign.canonical_digest(assembly)}
    report = {"status": transport.ACCEPTED_STATUS, "profile": transport.PREREQUISITE_REQUEST_PROFILE,
        "claim_scope": transport.CLAIM_SCOPE, "premise": transport.PREMISE, "assembly_status": "pass",
        "context_status": "pass", "prerequisite_status": "pass", "all_original_obligations_discharged": True,
        "empirical": "unassessed", "artifact": "withheld", "export": "withheld", "assembly": assembly,
        "context": {"discharges": [{"id": name} for name in campaign.CONTEXT_DISCHARGES],
                    "prerequisite_closure": deepcopy(closure)}, "prerequisites": closure,
        "obligations": [{"obligation": name, "status": "discharged", "stage": "declared_context",
                         "evidence": {"prerequisites": campaign.canonical_digest(closure)}} for name in campaign.OBLIGATIONS],
        "preservation": {"coverage": {"complete": True, "histories": 9, "transitions": 47, "prefixes_started": 48,
                                      "matched_prefixes": 48},
                         "requirements": [{"id": name, "status": "pass", "histories": {"pass": 9}}
                            for name in ("request_progress", "initiation_progress", "exclusive_selection")]}}
    return {"report": report, "candidate": {"construction": {"inventory": {"molecules": deepcopy(expected["molecules"])}},
                                             "assembly_proposal": {"nodes": []}}}, {"expected": expected}


class PrerequisiteCampaignTests(unittest.TestCase):
    def setUp(self):
        for target in ("subprocess.Popen", "subprocess.run"):
            guard = patch(target, side_effect=AssertionError("No native or process execution"))
            guard.start()
            self.addCleanup(guard.stop)

    def test_typed_recipe_retains_complete_a_b_authority_and_original_source(self):
        for label in ("A", "B"):
            supplied, _ = outer(label)
            before = deepcopy(supplied)
            authored, evidence = campaign.author_request(supplied, label == "B")
            self.assertEqual(authored, before)
            self.assertEqual(supplied, before)
            document, _ = campaign.source_document(supplied["implementation_request"], label == "B")
            self.assertIs(type(document), p.BuildRequest)
            self.assertEqual(p.to_data(document), supplied["implementation_request"]["document"])
            self.assertEqual(evidence["runtime_semantics"], "not_executed")
            self.assertEqual(evidence["source_artifact_digest"], campaign.canonical_digest(p.to_data(document)))
            self.assertEqual(len(document.implementations.implementations[0].dependencies), 1)

    def test_authoring_rejects_other_definition_catalog_edge_and_source_behavior(self):
        mutations = (
            lambda r: r["document"]["program"]["semantics"]["definitions"][-1].update(meaning="different"),
            lambda r: r["document"]["implementations"]["implementations"][0].update(dependencies=[]),
            lambda r: r["document"]["implementations"]["implementations"][0]["dependencies"][0].update(digest="0" * 64),
            lambda r: r["document"]["program"]["source_map"][0].update(file="changed.py"),
        )
        for index, mutate in enumerate(mutations):
            request, _ = original()
            mutate(request)
            with self.subTest(index=index), self.assertRaises(AssertionError):
                campaign.source_document(request, False)

    def test_checked_originals_keep_exact_seven_sources_and_unchanged_realization(self):
        value = packet()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "originals.json"
            path.write_text(json.dumps(value))
            self.assertEqual(campaign.checked_fixture(ROOT, path), value)
            mutations = (
                lambda v: v["source_sha256"].pop(campaign.INPUTS[-1]),
                lambda v: v["cases"][0]["request"]["implementation_request"]["budgets"].update(max_work=1),
                lambda v: v["cases"][0]["expected"].update(obligations=deepcopy(shared.OBLIGATIONS)),
                lambda v: v["cases"][0]["expected"].update(transitions=46),
                lambda v: v["cases"][0]["request"].update(profile=transport.INSTANCE_REQUEST_PROFILE),
                lambda v: v["cases"].reverse(),
            )
            for index, mutate in enumerate(mutations):
                changed = deepcopy(value)
                mutate(changed)
                path.write_text(json.dumps(changed))
                with self.subTest(index=index), self.assertRaises(AssertionError):
                    campaign.checked_fixture(ROOT, path)

    def test_complete_independent_closure_and_obligation_pins_cannot_be_rehashed_away(self):
        result, case = result_and_case()
        campaign.checked_result(result, case)
        for key in ("graph", "pending_dependencies", "providers", "instances", "input_allocations", "resource_allocations"):
            changed = deepcopy(result)
            closure = changed["report"]["prerequisites"]
            closure[key] = []
            changed["report"]["context"]["prerequisite_closure"] = deepcopy(closure)
            for row in changed["report"]["obligations"]:
                row["evidence"]["prerequisites"] = campaign.canonical_digest(closure)
            with self.subTest(key=key), self.assertRaisesRegex(AssertionError, "Complete prerequisite"):
                campaign.checked_result(changed, case)
        changed = deepcopy(result)
        changed["report"]["obligations"][0]["evidence"]["prerequisites"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "closure pin"):
            campaign.checked_result(changed, case)
        changed = deepcopy(result)
        changed["candidate"]["construction"]["inventory"]["molecules"][0]["sequence"] += "A"
        with self.assertRaisesRegex(AssertionError, "Exact molecule"):
            campaign.checked_result(changed, case)

    def test_retained_observation_oracle_is_explicit_and_legacy_default_stays_exact(self):
        fixture = {"cases": [{"id": label, "request": {}, "limits": {}} for label in ("A", "B")]}
        legacy = peer.observations(fixture)
        new = deepcopy(legacy)
        for row in new:
            if row["name"] == "changed-material":
                row["result"]["report"]["obligations"] = [
                    {"obligation": name, "status": "unresolved"} for name in campaign.OBLIGATIONS]
        with patch.object(transport, "_result"), patch.object(shared, "changed_candidate", return_value={}):
            shared.check_observations(legacy, fixture, validate_result=lambda *args: None)
            shared.check_observations(new, fixture, validate_result=lambda *args: None,
                                      expected_obligations=campaign.OBLIGATIONS)
            for rows, kwargs in ((new, {}), (legacy, {"expected_obligations": campaign.OBLIGATIONS})):
                with self.assertRaisesRegex(AssertionError, "original authority"):
                    shared.check_observations(rows, fixture, validate_result=lambda *args: None, **kwargs)


if __name__ == "__main__":
    unittest.main()
