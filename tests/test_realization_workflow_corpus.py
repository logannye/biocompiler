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


class RealizationWorkflowSourceScopeTests(unittest.TestCase):
    OPERATIONAL_MODULES = {
        "src/biocompiler/core_policy_operational.py": "biocompiler.core_policy_operational",
        "src/biocompiler/policy/operational.py": "biocompiler.policy.operational",
        "src/biocompiler/core_policy_implementation.py": "biocompiler.core_policy_implementation",
        "src/biocompiler/policy/implementation.py": "biocompiler.policy.implementation",
        "src/biocompiler/core_policy_material.py": "biocompiler.core_policy_material",
        "src/biocompiler/core_policy_component_material.py": "biocompiler.core_policy_component_material",
        "src/biocompiler/policy/component_material.py": "biocompiler.policy.component_material",
        "src/biocompiler/policy/material.py": "biocompiler.policy.material",
        "src/biocompiler/policy/cli.py": "biocompiler.policy.cli",
    }

    def setUp(self):
        from tools import check_realization_workflow_corpus as authority
        from tools.freeze_realization_workflow import source_inventory
        self.authority = authority
        self.actual = source_inventory()

    def test_operational_transport_is_exactly_pinned_and_excluded_from_original_authority(self):
        scope = self.authority.source_scope(self.actual)
        historical = {row["path"] for row in scope["historical_sources"]}
        additions = {row["path"]: row["sha256"] for row in scope["reviewed_additions"]}
        self.assertEqual(scope["historical_corpus_pin"], PIN)
        self.assertEqual(len(additions), 58)
        self.assertEqual(additions["src/biocompiler/core_workflow.py"],
                         "43b57b87a2d89db200463d8aed8b7eea7e262cf1c4ea02c772843598dbda90df")
        self.assertEqual(additions["src/biocompiler/core_artifacts.py"],
                         "77cf4dc31efb782c7fbb44fe8e79714a60e2e20374f9e7569fdce8f70d8ec59a")
        for path, module in self.OPERATIONAL_MODULES.items():
            with self.subTest(path=path):
                self.assertNotIn(path, historical)
                self.assertEqual(additions[path], self.authority.digest((ROOT / path).read_bytes()))
                self.assertIn(module, scope["denied_modules"])
        document = {"source_files": self.actual, "observations": [{"id": "preserved", "result": False}]}
        projected = self.authority.historical_projection(document, scope)
        self.assertEqual(projected["source_files"], scope["historical_sources"])
        self.assertIs(projected["observations"], document["observations"])
        self.assertEqual(document["source_files"], self.actual)

    def test_each_operational_source_pin_rejects_changed_inventory_and_changed_bytes(self):
        read_bytes = Path.read_bytes
        for path in self.OPERATIONAL_MODULES:
            with self.subTest(path=path):
                changed = [{**row, "sha256": "0" * 64} if row["path"] == path else row
                           for row in self.actual]
                with self.assertRaisesRegex(AssertionError, "Unreviewed workflow source addition"):
                    self.authority.source_scope(changed)

                def altered_bytes(actual_path):
                    raw = read_bytes(actual_path)
                    return raw + b"\n# unreviewed edit\n" if actual_path == ROOT / path else raw

                with patch.object(Path, "read_bytes", altered_bytes):
                    with self.assertRaisesRegex(AssertionError, "Reviewed addition bytes changed"):
                        self.authority.source_scope(self.actual)

    def test_registration_preserves_missing_duplicate_and_unreviewed_source_rejection(self):
        historical = self.authority.historical_sources()[0]["path"]
        with self.assertRaisesRegex(AssertionError, "Historical workflow authority source is missing"):
            self.authority.source_scope([row for row in self.actual if row["path"] != historical])
        with self.assertRaisesRegex(AssertionError, "Duplicate current workflow source"):
            self.authority.source_scope([*self.actual, self.actual[0]])
        for path in ("src/biocompiler/core_policy_operational_extra.py",
                     "src/biocompiler/policy/operational_extra.py"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(AssertionError, "Unreviewed workflow source addition"):
                    self.authority.source_scope([*self.actual, {"path": path, "sha256": "1" * 64}])

    def test_actual_operational_modules_remain_forbidden_before_during_and_after_capture(self):
        import os
        import subprocess
        import sys
        script = '''
import importlib
import sys
from tools.check_realization_workflow_corpus import deny_added_modules, source_scope
from tools.freeze_realization_workflow import source_inventory
scope = source_scope(source_inventory())
names = ("biocompiler.core_policy_operational", "biocompiler.policy.operational",
         "biocompiler.core_policy_implementation", "biocompiler.policy.implementation",
         "biocompiler.core_policy_material", "biocompiler.policy.material", "biocompiler.policy.cli",
         "biocompiler.core_policy_component_material", "biocompiler.policy.component_material")
for name in names:
    assert name in scope["denied_modules"]
    for attempted in (name, name + ".unreviewed"):
        with deny_added_modules(scope):
            try:
                importlib.import_module(attempted)
            except AssertionError as error:
                assert "tried to import" in str(error), error
            else:
                raise AssertionError("Excluded operational code ran: " + attempted)
    sys.modules[name] = object()
    try:
        try:
            with deny_added_modules(scope):
                raise RuntimeError("Preloaded excluded module was admitted")
        except AssertionError as error:
            assert "imported before" in str(error), error
    finally:
        del sys.modules[name]
    try:
        try:
            with deny_added_modules(scope):
                sys.modules[name] = object()
        except AssertionError as error:
            assert "Original cohort imported" in str(error), error
        else:
            raise AssertionError("Inserted operational module escaped capture")
    finally:
        del sys.modules[name]
'''
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
            text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)


class RealizationWorkflowInstrumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools import freeze_realization_workflow as capture
        import os
        import subprocess
        import sys
        cls.capture = capture
        cls.scratch = tempfile.TemporaryDirectory(prefix="workflow-instrumentation-test-")
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.observations = []
        for number in range(2):
            output = Path(cls.scratch.name) / str(number)
            script = (
                "from pathlib import Path\n"
                "from tools import freeze_realization_workflow as f\n"
                "f.FILES=('tests/test_verification_exploration.py',)\n"
                "f.METHOD_COUNTS=[14]\n"
                f"f.OUT=Path({str(output)!r})\n"
                "with f.portable_sources(): f.capture()\n"
            )
            result = subprocess.run([sys.executable, "-c", script], cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONHASHSEED": "0"},
                text=True, capture_output=True, timeout=60)
            if result.returncode:
                raise AssertionError(result.stderr[-4000:] + result.stdout[-4000:])
            cls.observations.append(json.loads((output / "capture.json").read_bytes()))
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

    def test_reviewed_addition_scope_rejects_changed_originals_and_unreviewed_additions(self):
        from copy import deepcopy
        from tools.check_realization_workflow_corpus import source_scope
        actual = self.capture.source_inventory()
        scope = source_scope(actual)
        self.assertEqual(scope["actual_sources"], actual)
        changed = deepcopy(actual)
        changed[0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "source bytes changed"):
            source_scope(changed)
        with self.assertRaisesRegex(AssertionError, "Unreviewed workflow source addition"):
            source_scope([*actual, {"path": "src/biocompiler/unreviewed.py", "sha256": "1" * 64}])

    def test_added_module_import_guard_denies_execution_and_preloaded_modules(self):
        import importlib
        import sys
        from tools.check_realization_workflow_corpus import deny_added_modules
        name = "_biocompiler_workflow_source_addition_guard_test"
        scope = {"denied_modules": [name]}
        with deny_added_modules(scope):
            with self.assertRaisesRegex(AssertionError, "tried to import"):
                importlib.import_module(name)
        with patch.dict(sys.modules, {name: object()}):
            with self.assertRaisesRegex(AssertionError, "imported before"):
                with deny_added_modules(scope):
                    self.fail("Preloaded excluded module must reject")



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
        from tools.check_realization_workflow_corpus import source_scope
        scope = source_scope(f.source_inventory())
        self.assertEqual(scope["historical_sources"], self.index["source_files"])
        self.assertEqual(scope["actual_sources"], f.source_inventory())

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

    def test_fixed_current_wholeworkflow_and_exact_original_version_mutants(self):
        from tools import freeze_realization_workflow as f
        calls = {row["id"]: row for row in self.capture["api_calls"]}
        prefix = f.previous.VERSION_MUTATION_CONTEXT
        run = calls[prefix + "/api/135"]
        replay = calls[prefix + "/api/134"]
        self.assertEqual(run["policy_override"], {"checker_version": "changed.v999"})
        raw = f.hydrate_arguments(run, self.capture["documents"])
        current = f.workflow.run_synthetic_verification(*raw["args"], **raw["kwargs"])
        actual = current.to_dict()
        historical_mutant = self.docs[run["result"]]
        expected = {**historical_mutant, "result": {**historical_mutant["result"],
            "dependencies": {**historical_mutant["result"]["dependencies"],
                             "checker": f.previous.CHECKER_VERSION}}}
        self.assertEqual(f.canonical(actual), f.canonical(expected))
        replay_args = f.hydrate_arguments(replay, self.capture["documents"])
        unchanged = f.workflow.replay_synthetic_verification(*replay_args["args"], **replay_args["kwargs"])
        self.assertEqual(unchanged.to_dict(), actual)
        stale = f.workflow.SyntheticVerificationRecord.from_dict(historical_mutant)
        with self.assertRaisesRegex(f.exploration.SerializationError, "stale, altered"):
            f.workflow.replay_synthetic_verification(stale, expected_request=current.request)

    def test_complete_independent_capture_matches_frozen_bytes(self):
        import os
        import subprocess
        import sys
        with tempfile.TemporaryDirectory(prefix="workflow-independent-recapture-") as directory:
            log = Path(directory) / "recapture.log"
            with log.open("w") as output:
                result = subprocess.run([sys.executable, str(ROOT / "tools/check_workflow_routed_recapture.py"), "--check"],
                    cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONHASHSEED": "0"},
                    stdout=output, stderr=subprocess.STDOUT, timeout=600)
            self.assertEqual(result.returncode, 0, log.read_text()[-4000:])


if __name__ == "__main__":
    unittest.main()
