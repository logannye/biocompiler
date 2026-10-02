"""Immutable original manager observations; no captured record grants acceptance."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.pipeline_historical_source_integrity import verify_source_identity

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "tests/conformance/checked-pipeline-v1.json"
MANIFEST = INDEX.with_name("checked-pipeline-full-v1.json")
INVENTORY_PIN = "1b8ce09b5bb39e9bec43dae64c00291716a5971349eafd14c1f9f7e2a6bb6117"
MANIFEST_PIN = "8c9702c131e19af9a9950402c06a554cb531d81789cd83f51a23f0e5ba0fac44"
PROJECTION_PIN = "1c9391db642c9375cc73cd2e28fc49cc6fb5966e0c30d6e430cfe49946e0dcb6"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_inventory(value, pin=INVENTORY_PIN):
    actual = sha(canonical({key: item for key, item in value.items() if key != "inventory_fingerprint"}))
    if value.get("inventory_fingerprint") != pin or actual != pin:
        raise AssertionError("Original pipeline inventory changed")
    return value


def load_index():
    manifest_raw = MANIFEST.read_bytes()
    manifest = json.loads(manifest_raw)
    if manifest_raw != canonical(manifest) + b"\n" or sha(manifest_raw) != MANIFEST_PIN:
        raise AssertionError("Complete pipeline archive manifest changed")
    descriptor = manifest["archive"]
    raw = (MANIFEST.parent / descriptor["path"]).read_bytes()
    if len(raw) != descriptor["bytes"] or sha(raw) != descriptor["sha256"]:
        raise AssertionError("Complete pipeline compressed index changed")
    raw = gzip.decompress(raw)
    if len(raw) != descriptor["uncompressed_bytes"] or sha(raw) != descriptor["uncompressed_sha256"]:
        raise AssertionError("Complete pipeline expanded index changed")
    value = json.loads(raw)
    if raw != canonical(value) + b"\n":
        raise AssertionError("Original pipeline index bytes are not canonical")
    return validate_inventory(value)


def read_document(directory, descriptor):
    path = directory / (descriptor["id"] + ".json")
    if not path.is_file() or path.is_symlink():
        raise AssertionError("Unsafe original pipeline document")
    raw = path.read_bytes()
    value = json.loads(raw)
    if len(raw) != descriptor["bytes"] or raw != canonical(value) + b"\n" or sha(canonical(value)) != descriptor["id"]:
        raise AssertionError("Complete original pipeline document bytes changed")
    return value


class CheckedPipelineCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = load_index()
        cls.directory = INDEX.parent / cls.index["document_directory"]
        cls.manifest = json.loads(MANIFEST.read_bytes())

    def test_original_full_cohort_and_zero_observation_methods_remain_accounted(self):
        value = self.index
        self.assertEqual(value["capture_mode"], "full")
        self.assertEqual(value["coverage"]["original_methods"], 467)
        self.assertEqual(len(value["original_methods"]), 467)
        self.assertEqual(len(set(value["original_methods"])), 467)
        contexts = [item for item in value["contexts"] if item["kind"] == "original_method"]
        self.assertEqual([item["id"] for item in contexts], value["original_methods"])
        self.assertTrue(any(not item["events"] for item in contexts))
        self.assertTrue(all(item["assertion_status"] == "passed" for item in value["contexts"]))
        counts = value["coverage"]["per_module_methods"]
        self.assertEqual(counts["tests/test_pipeline.py"], 21)
        self.assertEqual(counts["tests/test_checked_pipeline.py"], 6)
        self.assertEqual(counts["tests/test_component_admission.py"], 10)
        self.assertEqual(counts["tests/test_component_pipeline_manager.py"], 2)
        self.assertEqual(len(value["subprocesses"]), 2)
        for baseline, observed in zip(value["baseline_subprocesses"], value["subprocesses"]):
            self.assertEqual(baseline, {key: observed[key] for key in baseline})

    def test_every_complete_document_source_and_generator_has_its_original_identity(self):
        value = self.index
        self.assertEqual({path.name for path in self.directory.iterdir()}, {item["id"] + ".json" for item in value["documents"]})
        self.assertEqual(len({item["id"] for item in value["documents"]}), len(value["documents"]))
        self.assertEqual(sum(item["bytes"] for item in value["documents"]), value["coverage"]["document_bytes"])
        for item in value["documents"]:
            read_document(self.directory, item)
        for path, pin in value["source_files"].items():
            proof = verify_source_identity(ROOT, path, pin)
            self.assertEqual(proof["historical_sha256"], pin, path)
        self.assertEqual(sha((ROOT / value["capture_tool"]["path"]).read_bytes()), value["capture_tool"]["sha256"])
        packager = self.manifest["packager"]
        self.assertEqual(sha((ROOT / packager["path"]).read_bytes()), packager["sha256"])

    def test_complete_archive_and_all_documents_reconstruct_exact_original_capture_bytes(self):
        value = {key: item for key, item in self.index.items() if key not in
                 ("inventory_fingerprint", "document_directory", "original_capture_fingerprint")}
        value["schema_version"] = "biocompiler.checked_pipeline_original_capture.v1"
        hasher, size = hashlib.sha256(), 0
        def retain(raw):
            nonlocal size
            hasher.update(raw)
            size += len(raw)
        retain(b"{")
        for offset, key in enumerate(sorted(value)):
            if offset:
                retain(b",")
            retain(canonical(key) + b":")
            if key != "documents":
                retain(canonical(value[key]))
                continue
            retain(b"{")
            for index, item in enumerate(self.index["documents"]):
                if index:
                    retain(b",")
                raw = (self.directory / (item["id"] + ".json")).read_bytes()
                self.assertEqual(len(raw), item["bytes"])
                self.assertTrue(raw.endswith(b"\n"))
                self.assertEqual(sha(raw[:-1]), item["id"])
                retain(canonical(item["id"]) + b":" + raw[:-1])
            retain(b"}")
        retain(b"}")
        self.assertEqual(hasher.hexdigest(), self.index["original_capture_fingerprint"])
        self.assertEqual(hasher.hexdigest(), self.manifest["original_capture_fingerprint"])
        retain(b"\n")
        self.assertEqual(hasher.hexdigest(), self.manifest["original_capture_sha256"])
        self.assertEqual(size, self.manifest["original_capture_bytes"])

    def test_events_preserve_complete_inputs_outputs_state_errors_and_callback_parentage(self):
        value = self.index
        events = {event["id"]: event for event in value["events"]}
        self.assertEqual(len(events), value["coverage"]["events"])
        self.assertEqual(Counter(event["api"] for event in events.values()), value["coverage"]["api_census"])
        self.assertEqual(Counter(event["outcome"] for event in events.values()), value["coverage"]["outcomes"])
        documents = {item["id"] for item in value["documents"]}
        for event in events.values():
            self.assertIn(event["arguments"], documents)
            self.assertIn(event["source"]["file"], value["source_files"])
            if event["parent"] is not None:
                self.assertIn(event["parent"], events)
            if event["outcome"] == "returned":
                self.assertIn(event["result"], documents)
                self.assertNotIn("error", event)
            else:
                self.assertTrue({"module", "type", "message"} <= set(event["error"]))
                self.assertNotIn("result", event)
            if event["manager"] is not None:
                self.assertIn(event["state_before"], documents)
                self.assertIn(event["state_after"], documents)
            if event["api"] == "callback.invoke":
                self.assertIn(event["provider"], value["providers"])
                self.assertIn(events[event["parent"]]["api"], ("PassManager.run", "PassManager.admit_component_input"))
        self.assertTrue(any(event["api"] == "PassManager.set_dependency" and event["parent"] is not None and
            events[event["parent"]]["api"] == "callback.invoke" for event in events.values()))
        no_candidates = [event for event in events.values() if event.get("error", {}).get("type") == "NoCandidateFound"]
        self.assertTrue(no_candidates)
        self.assertTrue(all(set(event["error"]["attributes"]) == {"pass_id", "configuration", "dependencies"} for event in no_candidates))

    def test_all_provider_objects_keep_source_and_explicit_unported_callback_obligations(self):
        providers = self.index["providers"]
        self.assertEqual(len(providers), self.index["coverage"]["providers"])
        self.assertTrue(any(item["origin"] == "original_product_provider" for item in providers.values()))
        self.assertTrue(any(item["origin"] == "original_test_provider" for item in providers.values()))
        self.assertTrue(any(item["origin"] == "original_test_mock" for item in providers.values()))
        for identity, value in providers.items():
            self.assertEqual(identity, value["id"])
            self.assertEqual(value["native_recipe"]["status"], "pending_review")
            if value["origin"] in ("original_product_provider", "original_test_provider"):
                self.assertIn(value["file"], self.index["source_files"])
                self.assertTrue(value["source"])
                self.assertEqual(set(value["closure"]), set(value["freevars"]))
        self.assertEqual(self.index["native_replay"]["real_callback_pipeline_parity"],
                         "pending_native_producer_and_checker_execution")

    def test_rehashed_missing_context_or_accepted_output_cannot_replace_original_evidence(self):
        changes = ({"contexts": self.index["contexts"][:-1]}, {"events": self.index["events"][:-1]},
            {"providers": dict(list(self.index["providers"].items())[1:])},
            {"native_replay": {**self.index["native_replay"], "real_callback_pipeline_parity": "pass"}})
        for change in changes:
            value = {**self.index, **change}
            value["inventory_fingerprint"] = sha(canonical({key: item for key, item in value.items() if key != "inventory_fingerprint"}))
            with self.assertRaisesRegex(AssertionError, "inventory changed"):
                validate_inventory(value)

    def test_native_projection_is_exactly_derived_from_every_retained_pilot_observation(self):
        from tools.package_checked_pipeline_corpus import derive_projection
        raw = INDEX.read_bytes()
        value = json.loads(raw)
        self.assertEqual(raw, canonical(value) + b"\n")
        self.assertEqual(sha(raw), self.manifest["projection"]["sha256"])
        validate_inventory(value, PROJECTION_PIN)
        expected = derive_projection(self.index, lambda item: read_document(self.directory, item))
        self.assertEqual(value, expected)
        self.assertEqual(value["coverage"]["events"], 1738)
        self.assertEqual(value["coverage"]["api_census"]["callback.invoke"], 57)
        self.assertEqual(value["full_corpus"]["inventory_fingerprint"], INVENTORY_PIN)
        self.assertEqual(value["full_corpus"]["original_methods"], 467)
        self.assertEqual(value["full_corpus"]["contexts"], 476)
        forged = {**value, "events": value["events"][:-1]}
        forged["inventory_fingerprint"] = sha(canonical({key: item for key, item in forged.items() if key != "inventory_fingerprint"}))
        with self.assertRaisesRegex(AssertionError, "inventory changed"):
            validate_inventory(forged, PROJECTION_PIN)

    def test_equal_json_with_different_bytes_is_rejected(self):
        descriptor = self.index["documents"][0]
        value = read_document(self.directory, descriptor)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / (descriptor["id"] + ".json")
            raw = canonical(value) + b" \n"
            path.write_bytes(raw)
            changed = {**descriptor, "bytes": len(raw)}
            with self.assertRaisesRegex(AssertionError, "document bytes changed"):
                read_document(Path(directory), changed)


if __name__ == "__main__":
    unittest.main()
