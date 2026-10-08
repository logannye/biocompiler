"""Every original workflow CLI observation, actual children and exact bytes."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import freeze_workflow_cli as frozen

PIN = "a67edb95f75aa011ed5c059fe8cbe578fbe118d056931e3992f73775e8951da7"


class WorkflowCliCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document, cls.blobs = frozen.load()
        cls.rows = {row["id"]: row for row in cls.document["cases"]}

    def raw(self, reference):
        return frozen.restore(reference, self.blobs)

    def summary(self, name):
        return json.loads(self.raw(self.rows[name]["stdout"]))

    def test_complete_census_full_original_occurrences_and_source_lineage(self):
        self.assertEqual(self.document["inventory_fingerprint"], PIN)
        self.assertEqual(self.document["schema_version"], frozen.SCHEMA)
        self.assertEqual(self.document["original_corpus_pin"], frozen.CORPUS_PIN)
        self.assertEqual(self.document["supplement_pin"], frozen.SUPPLEMENT_PIN)
        self.assertEqual(self.document["coverage"], {
            "actual_children": 70, "original_occurrences": 16,
            "commands": {"inspect": 6, "synthetic-check": 30, "synthetic-explore": 7,
                         "synthetic-reduce": 5, "synthetic-replay": 22},
            "entrypoints": {"console": 66, "module": 4}, "exits": {"0": 29, "1": 11, "2": 30}})
        original = frozen.Corpus()
        expected = frozen.original_cases(original)
        observed = [row for row in self.document["cases"] if row["origin"] == "original_occurrence"]
        self.assertEqual([row["id"] for row in observed], [row["id"] for row in expected])
        self.assertEqual(len(self.rows), 70)
        for row, case in zip(observed, expected):
            with self.subTest(case=row["id"]):
                self.assertTrue(row["original_full_observation_equal"])
                self.assertEqual(row["lineage"], case["lineage"])
                self.assertEqual(row["argv"], case["argv"])
                self.assertEqual(row["fault"], case["fault"])
                expected_output = case["original_expected"]
                self.assertEqual(row["exit_code"], expected_output["exit_code"])
                self.assertEqual(self.raw(row["stdout"]), expected_output["stdout"])
                self.assertEqual(self.raw(row["stderr"]), expected_output["stderr"])
                for name, raw in case["files"].items():
                    self.assertEqual(self.raw(row["files_before"][name]["content"]), raw)
                for name, value in expected_output["files_after"].items():
                    raw = self.raw(row["files_after"][name]["content"])
                    self.assertEqual(raw, value["text"].encode())
                    self.assertEqual((len(raw), frozen.sha(raw)), (value["bytes"], value["sha256"]))
        self.assertEqual(self.document["source_scope"]["historical_sources"], original.index["source_files"])

    def test_all_six_operations_modes_and_full_supplemental_records(self):
        pairs = set()
        original = frozen.Corpus()
        for item in original.supplement["cases"]:
            expected = (json.dumps(item["expected"], sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
            request = item["expected"]["request"]
            pairs.add((request["operation"], request["mode"]))
            for phase in ("run", "replay"):
                row = self.rows[item["name"] + "-" + phase]
                output = row["argv"][row["argv"].index("--output") + 1]
                self.assertEqual(self.raw(row["files_after"][output]["content"]), expected)
                self.assertEqual(self.raw(row["stderr"]), b"")
                self.assertEqual(row["lineage"]["full_record_sha256"], frozen.digest(item["expected"]))
                summary = self.summary(row["id"])
                self.assertEqual((summary["operation"], summary["mode"]), (request["operation"], request["mode"]))
                if phase == "replay": self.assertEqual(row["exit_code"], 0)
        self.assertEqual(pairs, {(operation, mode) for operation in ("check", "explore", "reduce")
                                for mode in ("candidate", "model")})

    def test_replay_does_not_turn_fail_unknown_or_nonminimal_into_pass(self):
        for name, outcome in (("candidate_fail", "fail"), ("candidate_unknown", "unknown"),
                              ("candidate_unsupported", "unsupported")):
            self.assertEqual(self.rows[name + "-run"]["exit_code"], 1)
            self.assertEqual(self.rows[name + "-replay"]["exit_code"], 0)
            for phase in ("run", "replay"):
                self.assertEqual(self.summary(name + "-" + phase)["outcome"], outcome)
        for phase, code in (("run", 1), ("replay", 0)):
            self.assertEqual(self.rows["nonminimal-" + phase]["exit_code"], code)
            self.assertFalse(self.summary("nonminimal-" + phase)["one_minimal"])
            self.assertEqual(self.summary("nonminimal-" + phase)["evaluations"], 1)
            self.assertEqual(self.summary("nonminimal-" + phase)["outcome"], "fail")
        for name in ("candidate_explore", "model_explore"):
            self.assertFalse(self.summary(name + "-run")["complete"])
            self.assertFalse(self.summary(name + "-run")["all_passed"])
            self.assertEqual(self.rows[name + "-run"]["exit_code"], 1)
            self.assertEqual(self.rows[name + "-replay"]["exit_code"], 0)

    def test_summary_order_indentation_scope_and_newline_are_retained(self):
        expected_prefix = ["record_fingerprint", "request_fingerprint", "operation", "mode",
                           "intended_use", "human_therapeutic_admission", "claim_scope"]
        for row in self.document["cases"]:
            raw = self.raw(row["stdout"])
            if not raw or row["argv"][0] == "inspect": continue
            summary = json.loads(raw)
            self.assertEqual(raw, (json.dumps(summary, indent=2) + "\n").encode())
            self.assertEqual(list(summary)[:7], expected_prefix)
            self.assertEqual(summary["intended_use"], "software_test")
            self.assertEqual(summary["human_therapeutic_admission"], "not_admitted")
            if row["argv"][0] == "synthetic-replay":
                self.assertEqual(summary["replay"], "Fresh execution reproduced the declared outcome; "
                    "this does not turn a failure or unknown into PASS.")
            if "--output" in row["argv"]:
                self.assertEqual(summary["output"], row["argv"][row["argv"].index("--output") + 1])
            else: self.assertNotIn("output", summary)
        row = self.rows["noncanonical-request-whitespace-and-order"]
        summary = self.summary(row["id"])
        self.assertEqual(list(summary["bounds"]["fixed_suffix"][0]["contacts"]["x"]), ["n000004", "n000003"])
        expected = next(item["expected"] for item in frozen.Corpus().supplement["cases"] if item["name"] == "candidate_explore")
        self.assertEqual(self.raw(row["files_after"][row["argv"][-1]]["content"]),
                         (json.dumps(expected, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode())

    def test_every_error_preserves_all_inputs_prior_output_and_removes_temporary(self):
        failures = [row for row in self.document["cases"] if row["exit_code"] == 2]
        self.assertEqual(len(failures), 30)
        for row in failures:
            with self.subTest(case=row["id"]):
                self.assertEqual(row["files_before"], row["files_after"])
                self.assertEqual(self.raw(row["stdout"]), b"")
                self.assertTrue(self.raw(row["stderr"]).endswith(b"\n"))
        for row in self.document["cases"]:
            self.assertFalse(any(Path(name).name.startswith(".") and name.endswith(".tmp")
                                 for name in row["files_after"]))
        self.assertEqual(self.raw(self.rows["publication-short-write"]["stderr"]),
                         b"biocompiler: Incomplete verification report write.\n")
        self.assertEqual(self.raw(self.rows["publication-fsync"]["stderr"]),
                         b"biocompiler: capture fsync unavailable\n")
        self.assertEqual(self.raw(self.rows["replay-authority-before-record-error"]["stderr"]),
                         b"biocompiler: Invalid fields in SyntheticVerificationRequest.\n")

    def test_actual_input_and_publication_size_boundaries_are_lossless(self):
        for name, length in (("input-at-limit", frozen.MAX_INPUT),
                             ("input-one-over", frozen.MAX_INPUT + 1),
                             ("replay-input-one-over", frozen.MAX_OUTPUT + 1)):
            row = self.rows[name]
            path = next(name for name in row["files_before"] if name.endswith(
                "/record.json" if row["argv"][0] == "synthetic-replay" else "/request.json"))
            reference = row["files_before"][path]["content"]
            self.assertEqual(reference["kind"], "repeat")
            raw = self.raw(reference)
            self.assertEqual(raw, b" " * length)
        self.assertEqual(self.raw(self.rows["input-one-over"]["stderr"]),
                         b"biocompiler: Input JSON exceeds the size limit.\n")
        self.assertIn(b"Invalid artifact JSON", self.raw(self.rows["input-at-limit"]["stderr"]))
        accepted = self.rows["publication-size-at-limit"]
        self.assertEqual(accepted["fault"], {"kind": "serialized_length", "bytes": frozen.MAX_OUTPUT - 1})
        output = accepted["argv"][-1]
        self.assertEqual(self.raw(accepted["files_after"][output]["content"]), b" " * (frozen.MAX_OUTPUT - 1) + b"\n")
        self.assertEqual(accepted["exit_code"], 0)
        self.assertEqual(self.raw(self.rows["publication-size-one-over"]["stderr"]),
                         b"biocompiler: Verification report exceeds the 64 MiB size limit.\n")

    def test_each_child_import_audit_and_entrypoint_have_exact_pinned_sources(self):
        scope = self.document["source_scope"]
        pins = {row["path"]: row["sha256"] for row in scope["actual_sources"]}
        for row in self.document["cases"]:
            audit = row["import_audit"]
            self.assertTrue(audit["guard_active"])
            self.assertTrue(audit["denied_absent"])
            self.assertIn("biocompiler.cli", audit["modules"])
            self.assertTrue(set(scope["denied_modules"]).isdisjoint(audit["modules"]))
            for item in audit["modules"].values(): self.assertEqual(pins[item["path"]], item["sha256"])
        environment = self.document["capture_environment"]
        self.assertEqual(self.raw(environment["entrypoint_source"]), frozen.ENTRYPOINT.encode())
        self.assertEqual(self.raw(environment["startup"]), frozen.STARTUP.encode())
        self.assertEqual(environment["declared_console_entrypoint"], "biocompiler.cli:main")
        self.assertEqual(Counter(row["entrypoint"] for row in self.document["cases"]), {"console": 66, "module": 4})
        self.assertEqual({row["argv"][0] for row in self.document["cases"] if row["entrypoint"] == "module"},
                         {"synthetic-check", "synthetic-explore", "synthetic-reduce", "synthetic-replay"})
        for name, ref in self.document["retained_source_bytes"].items():
            if name in pins: self.assertEqual(frozen.sha(self.raw(ref)), pins[name])

    def test_lossless_recipe_rejects_tampered_bytes_lengths_or_amplification(self):
        store = frozen.Store()
        for raw in (b"", b"literal\x00\xff", b" " * (1024 * 1024) + b"\n"):
            ref = store.retain(raw)
            self.assertEqual(frozen.restore(ref, store.blobs), raw)
            for field, value in (("sha256", "0" * 64), ("bytes", len(raw) + 1)):
                with self.assertRaises(AssertionError):
                    frozen.restore({**ref, field: value}, store.blobs)
        ref = store.retain(b" " * (1024 * 1024 + 1))
        for changed in ({"count": frozen.MAX_OUTPUT + 2}, {"byte": 0}, {"suffix_hex": "ffff"}):
            with self.assertRaises(AssertionError): frozen.restore({**ref, **changed}, store.blobs)

    def test_namespace_collisions_and_escaping_paths_preserve_existing_data(self):
        with tempfile.TemporaryDirectory(prefix="workflow-cli-owned-test-") as directory:
            base = Path(directory)
            existing = base / "existing"; existing.mkdir()
            sentinel = existing / "user-data"; sentinel.write_bytes(b"preserve")
            first = base / "first"
            with patch.object(frozen, "ORIGINAL_ROOT", first), patch.object(frozen, "CLI_ROOT", existing):
                with self.assertRaises(FileExistsError):
                    with frozen.owned_directories(): self.fail("Collision was accepted")
            self.assertFalse(first.exists())
            self.assertEqual(sentinel.read_bytes(), b"preserve")
            with patch.object(frozen, "ORIGINAL_ROOT", base / "owned"), patch.object(frozen, "CLI_ROOT", base / "cli"):
                with self.assertRaises(AssertionError): frozen.safe_path(str(base / "owned/../outside"))
                with self.assertRaises(AssertionError): frozen.safe_path(str(base / "cli/config.json"))
                (base / "owned").mkdir()
                (base / "owned/escape").symlink_to(existing, target_is_directory=True)
                with self.assertRaises(AssertionError): frozen.safe_path(str(base / "owned/escape/user-data"))
                self.assertEqual(sentinel.read_bytes(), b"preserve")

    def test_store_rejects_corruption_missing_or_unreferenced_full_content(self):
        with tempfile.TemporaryDirectory(prefix="workflow-cli-store-test-") as directory:
            target = Path(directory) / "corpus.json"
            store = frozen.Store()
            ref = store.retain(b"full exact bytes")
            document = {"data": ref}
            document["inventory_fingerprint"] = frozen.digest(document)
            frozen.write(document, store.blobs, target)
            self.assertEqual(frozen.load(target), (document, store.blobs))
            path = target.with_suffix("") / (ref["sha256"] + ".bin")
            path.write_bytes(b"corrupt")
            with self.assertRaises(AssertionError): frozen.load(target)
            path.write_bytes(b"full exact bytes")
            other = target.with_suffix("") / (frozen.sha(b"unused") + ".bin")
            other.write_bytes(b"unused")
            with self.assertRaises(AssertionError): frozen.load(target)
            other.unlink(); path.unlink()
            with self.assertRaises((AssertionError, KeyError)): frozen.load(target)

    def test_independent_complete_seventy_child_recapture_is_byte_exact(self):
        from tools.check_workflow_cli_corpus import verify_recapture
        from tools.workflow_cli_policy_capture import capture
        actual, blobs = capture()
        evidence = verify_recapture(actual, blobs)
        self.assertEqual(evidence["status"], "complete_original_cli_recapture_equal")
        self.assertEqual(evidence["baseline_inventory_fingerprint"], PIN)
        self.assertEqual(evidence["projected_inventory_fingerprint"], PIN)
        self.assertEqual(evidence["actual_inventory_fingerprint"], actual["inventory_fingerprint"])
        self.assertEqual(evidence["actual_source_scope"], actual["source_scope"])
        # The exact witnessed route source members have current bytes. The
        # bridge compares every other full blob and retains all actual content.
        self.assertEqual(evidence["content_documents"], len(blobs))
        self.assertEqual(evidence["actual_capture"], actual)


if __name__ == "__main__": unittest.main()
