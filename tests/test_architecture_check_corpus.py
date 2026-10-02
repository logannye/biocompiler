"""Independent integrity checks for complete architecture checker evidence.

The delta format is fixture storage only. Each replay uses the full original
request and complete candidate; stored reports never supply acceptance authority.
"""
from collections import Counter
from copy import deepcopy
import importlib
import json
import sys
import unittest

from tools import freeze_architecture_check as campaign

INVENTORY = "bb1e0c3de0eaa45e11513b73379d35e6fd6180cac1d19fa9cec41e13ce96d213"


def stored_bytes(raw, format_):
    if format_ == "full":
        return campaign.encoded(raw)
    return (json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                       allow_nan=False) + "\n").encode()


def independent_resolve(index, documents, identity):
    """Replay the one-level fixture format independently of its generator."""
    metadata = {entry["id"]: entry for entry in index["documents"]}
    entry = metadata[identity]
    if entry["format"] == "full":
        return deepcopy(documents[identity])
    value = deepcopy(documents[entry["base"]])
    for edit in documents[identity]["edits"]:
        parent = value
        for key in edit["path"][:-1]:
            parent = parent[key]
        if edit["op"] == "remove":
            del parent[edit["path"][-1]]
        else:
            parent[edit["path"][-1]] = deepcopy(edit["value"])
    return value


class ArchitectureCheckCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index, cls.documents = campaign.load()
        cls.cases = {case["id"]: case for case in cls.index["cases"]}
        cls.metadata = {entry["id"]: entry for entry in cls.index["documents"]}

    def resolved(self, identity):
        return independent_resolve(self.index, self.documents, identity)

    def rejected_index(self, changed, documents=None, message=None):
        changed["inventory_fingerprint"] = campaign.inventory(changed)
        manager = (self.assertRaises(AssertionError) if message is None else
                   self.assertRaisesRegex(AssertionError, message))
        with manager:
            campaign.check_corpus(changed, self.documents if documents is None else documents)

    def test_exact_full_inventory_and_census(self):
        self.assertEqual(campaign.inventory(self.index), INVENTORY)
        self.assertEqual(self.index["inventory_fingerprint"], INVENTORY)
        self.assertEqual((len(self.cases), len(self.documents)), (293, 463))
        coverage = self.index["coverage"]
        self.assertEqual(coverage["formats"], {"delta": 409, "full": 54})
        self.assertEqual(coverage["outcomes"], {"fail": 76, "pass": 217})
        self.assertEqual(coverage["captured_calls"], 277)
        self.assertEqual(coverage["resolved_document_bytes"], 63_103_498)
        self.assertEqual(coverage["stored_document_bytes"] + len(campaign.CORPUS.read_bytes()), 13_996_600)

    def test_complete_documents_have_exact_bytes_and_independent_resolution(self):
        self.assertEqual(campaign.encoded(self.index), campaign.CORPUS.read_bytes())
        self.assertEqual(campaign.inventory(self.index), self.index["inventory_fingerprint"])
        self.assertEqual({path.name for path in campaign.DOCUMENTS.glob("*.json")},
                         {identity + ".json" for identity in self.documents})
        stored_total = len(campaign.CORPUS.read_bytes())
        resolved_total = 0
        for identity, entry in self.metadata.items():
            with self.subTest(identity=identity):
                stored = self.documents[identity]
                data = (campaign.DOCUMENTS / (identity + ".json")).read_bytes()
                self.assertEqual(data, stored_bytes(stored, entry["format"]))
                self.assertEqual(len(data), entry["bytes"])
                self.assertEqual(campaign.fingerprint(stored), entry["stored_fingerprint"])
                complete = self.resolved(identity)
                self.assertEqual(campaign.encoded(complete),
                                 campaign.encoded(campaign.resolve(self.index, self.documents, identity)))
                self.assertEqual(campaign.fingerprint(complete), identity)
                self.assertEqual(len(campaign.encoded(complete)), entry["resolved_bytes"])
                campaign.bounds(complete)
                stored_total += len(data)
                resolved_total += entry["resolved_bytes"]
                if entry["format"] == "delta":
                    self.assertEqual(self.metadata[entry["base"]]["format"], "full")
                    self.assertEqual(self.metadata[entry["base"]]["kind"], entry["kind"])
                else:
                    self.assertIsNone(entry["base"])
        self.assertLessEqual(stored_total, 16 * 1024 * 1024)
        self.assertLessEqual(resolved_total, 512 * 1024 * 1024)
        self.assertEqual(self.index["coverage"]["resolved_document_bytes"], resolved_total)

    def test_complete_retained_corpus_passes_structural_checks(self):
        campaign.check_corpus(self.index, self.documents, fresh=False)

    def test_original_case_b_authority_and_full_installed_scope(self):
        expected_installed = {"installed/" + name for name in (
            "A", "B", "C", "D", "E", "F", "automatic_timing", "automatic_b", "automatic_f",
            "memory_reset", "state_reset", "production_adjustment", "activity_control")}
        self.assertEqual(set(self.index["coverage"]["installed"]), expected_installed)
        for identity in expected_installed:
            case = self.cases[identity]
            self.assertEqual(case["origin"], "complete_installed_api_fixture")
            report = self.resolved(case["assessment"])
            self.assertEqual(report["outcome"], "pass")
            self.assertTrue(report["translation_complete"])
            self.assertTrue(report["construction_complete"])
        expected_case_b = {"case_b/" + variant for variant in
                           ("base", "parameter-default", "parameter-override")}
        self.assertEqual(set(self.index["coverage"]["case_b"]), expected_case_b)
        for identity in expected_case_b:
            case = self.cases[identity]
            directory = campaign.ROOT / "tests/conformance/case-b" / identity.split("/")[1]
            self.assertEqual(case["origin"], "complete_retained_case_b")
            for kind, filename in (("request", "request.json"), ("build", "candidate.json")):
                complete = json.loads((directory / filename).read_bytes())
                self.assertEqual(campaign.encoded(self.resolved(case[kind])), campaign.encoded(complete))
                self.assertEqual(self.metadata[case[kind]]["format"], "full")

    def test_source_assertion_ledger_matches_actual_test_inventory(self):
        expected = set()
        test_directory = str(campaign.ROOT / "tests")
        if test_directory not in sys.path:
            sys.path.insert(0, test_directory)
        for module_name, class_name in campaign.MODULES:
            cls = getattr(importlib.import_module(module_name), class_name)
            prefix = module_name + "." + class_name + "."
            expected.add(prefix + "setUpClass")
            expected.update(prefix + method for method in dir(cls) if method.startswith("test_"))
        ledger = self.index["coverage"]["methods"]
        self.assertEqual(len(ledger), 84)
        self.assertEqual(len(expected), 84)
        self.assertEqual({entry["method"] for entry in ledger}, expected)
        self.assertEqual(self.index["coverage"]["exclusions"], [])
        actual = Counter(case["id"].rsplit("/", 1)[0] for case in self.cases.values()
                         if case["origin"] == "existing_python_assertion")
        for entry in ledger:
            self.assertEqual(entry["status"], "source_assertions_executed")
            self.assertEqual(entry["retained_calls"], actual[entry["method"]])
        self.assertEqual(sum(actual.values()), self.index["coverage"]["captured_calls"])

    def test_exact_diagnostic_exception_scopes_and_report_authority(self):
        declared_sites = {
            "_refinement_checks.owned": "executable_material_model_missing:",
            "_refinement_checks.binding_roles": "material_recipient_missing:",
            "_refinement_checks.controlled_actions": "activity_control_not_realized:",
            "_delivery_dependency_checks.component_placements": "helper_",
        }
        self.assertEqual(campaign.ORDER_SITES, declared_sites)
        outcomes = Counter()
        for case in self.cases.values():
            report = self.resolved(case["assessment"])
            outcomes[report["outcome"]] += 1
            self.assertEqual(report["request_fingerprint"], case["request"])
            self.assertEqual(report["build_fingerprint"], case["build"])
            self.assertFalse(report["search_verified"])
            self.assertEqual(report["empirical_validation"], "unknown")
            self.assertEqual(report["human_therapeutic_admission"], "not_admitted")
            codes = [item["code"] for item in report["diagnostics"]]
            self.assertEqual(case["diagnostic_order_sites"], campaign.diagnostic_sites(report))
            for replacement in case["native_diagnostic_replacements"]:
                self.assertEqual(set(replacement), {"python", "native"})
                self.assertIn(replacement["python"], codes)
                if replacement["python"].startswith("malformed_architecture:"):
                    self.assertEqual(replacement, {
                        "python": "malformed_architecture:Implemented source requirements need supplied realizations.",
                        "native": "malformed_architecture:invalid_architecture_build",
                    })
                    continue
                prefix = (replacement["python"].split(":", 1)[0] + ":" if
                          replacement["python"].startswith("source_behavior:") else
                          ":".join(replacement["python"].split(":", 2)[:2]) + ":")
                self.assertTrue(replacement["native"].startswith(prefix))
                self.assertIn(replacement["native"][len(prefix):], {
                    "lowering_execution_profile", "lowering_source_identity", "lowering_complete_graph",
                    "lowering_parameter_inventory", "lowering_authoritative_bindings",
                    "lowering_requirements_and_lineage", "lowering_identity_binding",
                    "lowering_operation", "lowering_semantics", "lowering_source_location",
                })
        self.assertEqual(dict(sorted(outcomes.items())), self.index["coverage"]["outcomes"])

    def test_diagnostic_order_exception_preserves_other_sites_and_fields(self):
        codes = ["refinement:r:executable_material_model_missing:z", "fixed:first",
                 "refinement:s:executable_material_model_missing:z",
                 "refinement:r:executable_material_model_missing:a", "fixed:second",
                 "refinement:s:executable_material_model_missing:a"]
        report = {"outcome": "fail", "unresolved": ["z", "a"],
                  "diagnostics": [{"code": code, "message": code} for code in codes]}
        original = deepcopy(report)
        result = campaign.normalize_diagnostic_order(report, ["_refinement_checks.owned"])
        self.assertEqual([item["code"] for item in result["diagnostics"]],
                         [codes[3], codes[1], codes[5], codes[0], codes[4], codes[2]])
        self.assertEqual(result["unresolved"], ["z", "a"])
        self.assertEqual(result["outcome"], "fail")
        self.assertEqual(report, original)
        self.assertEqual(campaign.diagnostic_sites({"diagnostics": [
            {"code": codes[0]}, {"code": codes[2]}]}), [])
        with self.assertRaisesRegex(AssertionError, "Unknown diagnostic order site"):
            campaign.normalize_diagnostic_order(report, ["all_diagnostics"])
        with self.assertRaisesRegex(AssertionError, "Unclassified"):
            campaign.native_replacements({"diagnostics": [{"code": "source_behavior:forged PASS"}]})

    def test_fresh_checks_and_historical_replay_bind_full_external_request(self):
        from biocompiler.verification.payload_architecture import verify_payload_architecture
        from biocompiler.errors import SerializationError

        seen = set()
        for case in self.cases.values():
            expected = self.resolved(case["assessment"])
            category = (expected["outcome"], bool(case["native_diagnostic_replacements"]))
            if category in seen or case["diagnostic_order_sites"]:
                continue
            seen.add(category)
            request = campaign.PayloadArchitectureRequest.from_dict(self.resolved(case["request"]))
            build = campaign.PayloadArchitectureBuild.from_dict(self.resolved(case["build"]))
            fresh = campaign.bc.check_payload_architecture(build, expected_request=request)
            self.assertEqual(campaign.encoded(fresh.to_dict()), campaign.encoded(expected))
            verify_payload_architecture(fresh, build, expected_request=request)
        self.assertEqual({outcome for outcome, _ in seen}, set(self.index["coverage"]["outcomes"]))
        self.assertEqual(len(self.index["replay_rejections"]), 2)
        for replay in self.index["replay_rejections"]:
            source = self.cases[replay["source"]]
            request = campaign.PayloadArchitectureRequest.from_dict(self.resolved(source["request"]))
            build = campaign.PayloadArchitectureBuild.from_dict(self.resolved(source["build"]))
            historical = campaign.PayloadArchitectureVerification.from_dict(self.resolved(replay["assessment"]))
            with self.assertRaises(SerializationError):
                verify_payload_architecture(historical, build, expected_request=request)

    def test_missing_extra_duplicate_and_rehashed_inventory_corruption_rejects(self):
        documents = dict(self.documents)
        documents.pop(next(iter(documents)))
        self.rejected_index(deepcopy(self.index), documents, "Missing/extra/duplicate")
        documents = dict(self.documents)
        documents["0" * 64] = {}
        self.rejected_index(deepcopy(self.index), documents, "Missing/extra/duplicate")
        changed = deepcopy(self.index)
        changed["documents"].append(deepcopy(changed["documents"][0]))
        self.rejected_index(changed, message="Missing/extra/duplicate")
        changed = deepcopy(self.index)
        changed["cases"][1]["id"] = changed["cases"][0]["id"]
        self.rejected_index(changed, message="Duplicate architecture case")

    def test_rehashed_stale_census_and_broader_diagnostic_exceptions_reject(self):
        changed = deepcopy(self.index)
        changed["coverage"]["cases"] += 1
        self.rejected_index(changed, message="Stale architecture case census")
        changed = deepcopy(self.index)
        changed["cases"][0]["diagnostic_order_sites"] = ["all_diagnostics"]
        self.rejected_index(changed, message="Undeclared diagnostic order exception")
        changed = deepcopy(self.index)
        changed["cases"][0]["native_diagnostic_replacements"] = [
            {"python": "fail", "native": "pass"}]
        self.rejected_index(changed, message="Undeclared native diagnostic replacement")

    def test_omitted_case_leaves_detectable_unreferenced_full_evidence(self):
        references = Counter(case[kind] for case in self.index["cases"]
                             for kind in ("request", "build", "assessment"))
        references.update(case["assessment"] for case in self.index["replay_rejections"])
        references.update(entry["base"] for entry in self.metadata.values() if entry["base"] is not None)
        chosen = next(case for case in self.index["cases"]
                      if any(references[case[kind]] == 1 for kind in ("request", "build", "assessment")))
        changed = deepcopy(self.index)
        changed["cases"] = [case for case in changed["cases"] if case["id"] != chosen["id"]]
        changed["coverage"]["cases"] -= 1
        self.rejected_index(changed, message="Unused architecture fixture documents")

    def changed_delta(self, mutate):
        index = deepcopy(self.index)
        documents = dict(self.documents)
        entry = next(item for item in index["documents"] if item["format"] == "delta")
        stored = deepcopy(documents[entry["id"]])
        mutate(entry, stored)
        entry["stored_fingerprint"] = campaign.fingerprint(stored)
        entry["bytes"] = len(stored_bytes(stored, entry["format"]))
        documents[entry["id"]] = stored
        return index, documents, entry["id"]

    def test_delta_hash_kind_chains_and_paths_cannot_bypass_full_authority(self):
        identity = next(item["id"] for item in self.index["documents"] if item["format"] == "delta")
        documents = dict(self.documents)
        documents[identity] = dict(documents[identity], edits=[])
        with self.assertRaisesRegex(AssertionError, "Stored document identity"):
            campaign.resolve(self.index, documents, identity)

        def invalid_base(entry, stored):
            base = next(item for item in self.index["documents"]
                        if item["format"] == "delta" and item["id"] != entry["id"])
            entry["base"] = stored["base"] = base["id"]
        index, docs, identity = self.changed_delta(invalid_base)
        with self.assertRaisesRegex(AssertionError, "complete same-kind"):
            campaign.resolve(index, docs, identity)

        def wrong_kind(entry, stored):
            base = next(item for item in self.index["documents"]
                        if item["format"] == "full" and item["kind"] != entry["kind"])
            entry["base"] = stored["base"] = base["id"]
        index, docs, identity = self.changed_delta(wrong_kind)
        with self.assertRaisesRegex(AssertionError, "complete same-kind"):
            campaign.resolve(index, docs, identity)

        for edit, message in (
            ({"op": "set", "path": [], "value": 0}, "Invalid delta path"),
            ({"op": "set", "path": ["absent", "nested"], "value": 0}, "Missing delta descent"),
            ({"op": "set", "path": [False], "value": 0}, "Invalid delta terminal"),
            ({"op": "set", "path": ["schema_version", 0], "value": 0}, "Invalid delta terminal"),
            ({"op": "remove", "path": ["absent"]}, "Only existing object fields"),
            ({"op": "add", "path": ["schema_version"], "value": 0}, "Unknown delta operation"),
            ({"op": "set", "path": ["schema_version"], "value": 0, "extra": True}, "Unknown delta fields"),
        ):
            with self.subTest(edit=edit):
                index, docs, identity = self.changed_delta(
                    lambda _entry, stored: stored.update(edits=[edit]))
                with self.assertRaisesRegex(AssertionError, message):
                    campaign.resolve(index, docs, identity)


if __name__ == "__main__":
    unittest.main()
