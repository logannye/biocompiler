"""Complete workflow capture integrity, including original callback invocation order."""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class RealizationWorkflowInstrumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools import freeze_realization_workflow as capture
        cls.capture = capture
        cls.scratch = tempfile.TemporaryDirectory(prefix="workflow-instrumentation-test-")
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.observations = []
        for number in range(2):
            with patch.dict("os.environ", {"PYTHONHASHSEED": "0"}), \
                    patch.object(capture, "FILES", ("tests/test_verification_exploration.py",)), \
                    patch.object(capture, "METHOD_COUNTS", [14]), \
                    patch.object(capture, "OUT", Path(cls.scratch.name) / str(number)), \
                    redirect_stdout(io.StringIO()), capture.portable_sources():
                cls.observations.append(capture.capture())
        cls.document = cls.observations[0]
        cls.calls = {item["id"]: item for item in cls.document["api_calls"]}

    def test_independent_focused_capture_is_byte_identical(self):
        self.assertEqual(self.capture.canonical(self.observations[0]),
                         self.capture.canonical(self.observations[1]))
        self.assertEqual(self.document["coverage"]["original_methods"], 14)
        self.assertEqual(self.document["coverage"]["api_calls"], 379)
        self.assertEqual(self.document["coverage"]["api_outcomes"],
                         {"iterator": 10, "raised": 36, "returned": 333})
        self.assertTrue(all(item["assertion_status"] == "passed" for item in self.document["contexts"]))

    def test_every_callback_has_complete_parented_input_and_outcome(self):
        callbacks = [item for item in self.calls.values() if item["api"] == "workflow.callback"]
        self.assertEqual(len(callbacks), 62)
        for call in callbacks:
            parent = self.calls[call["callback_parent"]]
            self.assertIn(parent["api"], {"explore_boolean_histories", "reduce_counterexample"})
            self.assertEqual(call["parent_call"], parent["id"])
            self.assertIn(call["id"], parent["callback_calls"])
            identity = self.document["documents"][call["callback_identity"]]["value"]
            self.assertEqual(self.capture.digest(identity["source"].encode()), identity["source_sha256"])
            self.assertTrue((ROOT / identity["file"]).is_file())
            raw = json.loads(self.document["documents"][call["input"]]["value"])
            self.assertEqual(set(raw), {"args", "kwargs"})
            self.assertEqual(len(raw["args"]), 1)
            self.assertEqual(set(raw["kwargs"]), {"until"})
            self.assertIn(call["outcome"], {"returned", "raised"})
            self.assertIn("result" if call["outcome"] == "returned" else "error", call)
        for parent in self.calls.values():
            if "callback_calls" in parent:
                self.assertEqual(parent["callback_calls"], [item["id"] for item in callbacks
                    if item["callback_parent"] == parent["id"]])

    def test_generators_retain_actual_yields_and_terminal_state(self):
        iterators = [call for call in self.calls.values() if call["outcome"] == "iterator"]
        self.assertEqual(len(iterators), 10)
        for item in iterators:
            self.assertIn(item["iterator_state"], {"created", "suspended", "exhausted", "closed", "raised"})
            for identity in item["yields"]:
                frames = self.document["documents"][identity]["value"]
                self.assertIsInstance(frames, list)
                self.assertTrue(all(set(frame) == {"time", "signals", "contacts"} for frame in frames))
            if item["iterator_state"] == "exhausted": self.assertIn("return_value", item)

    def test_profile_does_not_mutate_immutable_prior_capture(self):
        from tools import freeze_synthetic_producers as previous
        self.assertEqual(sum(previous.foundation.METHOD_COUNTS), 373)
        self.assertEqual(len(previous.foundation.CLASSES), 6)
        self.assertEqual(sum(self.capture.METHOD_COUNTS), 376)
        self.assertEqual(len(self.capture.WORKFLOW_CLASSES), 11)
        self.assertEqual(self.capture.verify_prior_projection(self.document, complete=False), {})

    def test_portable_directory_collision_preserves_existing_contents(self):
        with tempfile.TemporaryDirectory(prefix="workflow-collision-test-") as root:
            directory = Path(root) / "existing"
            directory.mkdir()
            sentinel = directory / "user-file"
            sentinel.write_bytes(b"preserve")
            with patch.object(self.capture, "PORTABLE_TEMP", directory):
                with self.assertRaises(FileExistsError):
                    with self.capture.portable_temporary_directories():
                        self.fail("Collision must reject before changing the directory")
            self.assertEqual(sentinel.read_bytes(), b"preserve")



PIN = "2f5e7636977f559e046776c1bb92bebf67c8f0e733ca463927f8d3a1aee3d77b"
CAPTURE_PIN = "5e7b74bd456a554dd3b1e3661f25ec42ff00a719b114d19cdd474d9c014b1015"
CORPUS = ROOT / "tests/conformance/realization-workflow-v1.json"


def load_corpus():
    from tools.freeze_component_runtime import canonical, digest, require
    payload = CORPUS.read_bytes(); index = json.loads(payload)
    require(canonical(index) + b"\n" == payload, "Noncanonical workflow inventory")
    require(index["inventory_fingerprint"] == PIN and digest(canonical(
        {key: value for key, value in index.items() if key != "inventory_fingerprint"})) == PIN,
        "Workflow corpus identity differs")
    descriptors = {row["id"]: row for row in index["documents"]}
    directory = CORPUS.with_suffix("")
    require(len(descriptors) == len(index["documents"]) and
        {path.name for path in directory.iterdir()} == {key + ".json" for key in descriptors},
        "Incomplete workflow document inventory")
    docs = {}; total = len(payload)
    for identity, descriptor in descriptors.items():
        require(len(identity) == 64 and all(c in "0123456789abcdef" for c in identity), "Unsafe workflow content address")
        payload = (directory / (identity + ".json")).read_bytes(); total += len(payload)
        value = json.loads(payload)
        require(len(payload) == descriptor["bytes"] <= 64 * 1024 * 1024 and
            canonical(value) + b"\n" == payload and digest(canonical(value)) == identity,
            "Complete workflow document bytes changed")
        docs[identity] = value
    require(total == 188830976 and total < 512 * 1024 * 1024, "Complete workflow storage census differs")
    calls = {}; contexts = []
    for context in index["contexts"]:
        rows = docs[context["ledger"]]
        require(len(rows) == context["api_calls"], "Workflow context is incomplete")
        identities = []
        for number, row in enumerate(rows):
            identity = context["id"] + "/api/" + str(number)
            call = {key: value for key, value in row.items() if key != "native"}
            call.update(id=identity, source_test=context["id"],
                source=index["source_locations"][row["source"]], python_types=docs[row["python_types"]])
            for key in ("parent_call", "callback_parent"):
                if key in call and call[key] is not None:
                    require(0 <= call[key] < number, "Invalid workflow call parent")
                    call[key] = context["id"] + "/api/" + str(call[key])
            if "callback_calls" in call:
                require(all(number < value < len(rows) for value in call["callback_calls"]), "Invalid callback ordering")
                call["callback_calls"] = [context["id"] + "/api/" + str(value) for value in call["callback_calls"]]
            require(identity not in calls, "Duplicate workflow observation")
            calls[identity] = call; identities.append(identity)
        contexts.append({**{key: value for key, value in context.items() if key != "ledger"}, "api_calls": identities})
    order = docs[index["capture_call_order"]]
    ordered = [contexts[context]["api_calls"][number] for context, number in order]
    require(len(ordered) == len(set(ordered)) == len(calls), "Complete workflow order differs")
    capture = {"schema_version": "biocompiler.realization_workflow_baseline_capture.v1",
        "source_files": index["source_files"], "contexts": contexts, "subprocesses": index["subprocesses"],
        "api_calls": [calls[identity] for identity in ordered],
        "documents": {identity: {"kind": descriptors[identity]["kind"], "value": docs[identity]}
            for identity in index["original_documents"]},
        "coverage": {key: value for key, value in index["coverage"].items()
            if key not in {"native_stages", "preserved_prior_occurrences", "unclassified_observations"}},
        "capture_environment": index["original_capture_environment"]}
    require(digest(canonical(capture)) == index["original_capture_fingerprint"] == CAPTURE_PIN,
        "Packed workflow corpus did not reconstruct the complete original capture")
    return index, docs, capture


class RealizationWorkflowCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index, cls.docs, cls.capture = load_corpus()

    def test_complete_original_contexts_calls_sources_and_error_census(self):
        from collections import Counter
        import ast
        from tools import freeze_realization_workflow as f
        coverage = self.index["coverage"]
        self.assertEqual((coverage["original_methods"], coverage["contexts"], coverage["api_calls"]), (376, 385, 69236))
        expected = []
        for path, count in zip(f.FILES, f.METHOD_COUNTS):
            tree = ast.parse((ROOT / path).read_text())
            methods = [path + "::" + kind.name + "." + method.name
                for kind in sorted((node for node in tree.body if isinstance(node, ast.ClassDef)), key=lambda node: node.name)
                for method in sorted((node for node in kind.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")), key=lambda node: node.name)]
            self.assertEqual(len(methods), count); expected.extend(methods)
        self.assertEqual([row["id"] for row in self.capture["contexts"] if row["kind"] == "original_method"], expected)
        self.assertTrue(all(row["assertion_status"] == "passed" for row in self.capture["contexts"]))
        self.assertEqual(Counter(row["api"] for row in self.capture["api_calls"]), coverage["api_census"])
        self.assertEqual(Counter(row["outcome"] for row in self.capture["api_calls"]),
            {"iterator": 24, "raised": 166, "returned": 69046})
        self.assertEqual(self.index["source_files"], f.source_inventory())

    def test_every_immutable_prior_observation_survives_in_order(self):
        from tools import freeze_realization_workflow as f
        self.assertEqual(len(f.verify_prior_projection(self.capture)), 47901)
        self.assertEqual(len(self.capture["subprocesses"]), 2)
        self.assertEqual({child["invocation"]["hash_seed"] for child in self.capture["subprocesses"]}, {"1", "37"})

    def test_every_new_domain_and_kernel_observation_replays_completely(self):
        from tools import freeze_realization_workflow as f
        self.assertEqual(f.verify_replay(self.capture), 874)

    def test_complete_625_history_campaign_and_all_callback_invocations(self):
        calls = self.capture["api_calls"]
        callbacks = [row for row in calls if row["api"] == "workflow.callback"]
        self.assertEqual(len(callbacks), 1030)
        for parent in calls:
            if "callback_calls" in parent:
                self.assertEqual(parent["callback_calls"], [row["id"] for row in callbacks if row["callback_parent"] == parent["id"]])
        campaigns = [row for row in calls if row["api"] == "explore_boolean_histories"
            and row["source_test"].startswith("tests/test_verification_campaign.py::")]
        self.assertEqual(len(campaigns), 1)
        campaign = campaigns[0]
        self.assertEqual(len(campaign["callback_calls"]), 625)
        report = self.docs[campaign["result"]]
        self.assertEqual((report["state_count"], report["possible_histories"], report["evaluated_histories"]), (25,625,625))
        self.assertEqual(len(report["results"]), 625)
        self.assertTrue(report["complete"] and report["all_passed"])

    def test_all_original_cli_bytes_and_publication_mutant_are_retained(self):
        rows = [row for row in self.capture["api_calls"] if row["api"] == "workflow.cli"]
        self.assertEqual(len(rows), 16)
        commands = {json.loads(self.docs[row["input"]])["args"][0][0] for row in rows}
        self.assertEqual(commands, {"synthetic-check", "synthetic-explore", "synthetic-reduce", "synthetic-replay", "inspect"})
        failures = [row for row in rows if "publication_override" in row]
        self.assertEqual(len(failures), 1)
        failed = failures[0]
        self.assertEqual(self.docs[failed["result"]], 2)
        self.assertEqual(self.docs[failed["files_before"]], self.docs[failed["files_after"]])
        self.assertIn("disk unavailable", self.docs[failed["stderr"]])
        for row in rows:
            for key in ("stdout", "stderr", "files_before", "files_after"): self.assertIn(row[key], self.docs)
            self.assertIn(self.docs[row["result"]], (0,1,2))

    def test_complete_independent_capture_matches_frozen_bytes(self):
        import os
        import subprocess
        import sys
        with tempfile.TemporaryDirectory(prefix="workflow-independent-recapture-") as directory:
            log = Path(directory) / "recapture.log"
            with log.open("w") as output:
                result = subprocess.run([sys.executable, str(ROOT / "tools/freeze_realization_workflow.py"), "--check"],
                    cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONHASHSEED": "0"},
                    stdout=output, stderr=subprocess.STDOUT, timeout=600)
            self.assertEqual(result.returncode, 0, log.read_text()[-4000:])


if __name__ == "__main__":
    unittest.main()
