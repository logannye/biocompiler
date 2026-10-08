"""Inert orchestration and source rejection; never execute CLI or native code."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import workflow_cli_policy_capture as current


class WorkflowCliPolicyCaptureTests(unittest.TestCase):
    def source_copy(self, root):
        names = {current.FREEZER, current.policy.WITNESS, current.packaging.WITNESS,
                 current.policy.ENTRYPOINT, current.packaging.PATH, *current.policy.ROUTES}
        for name in names:
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((current.ROOT / name).read_bytes())

    def test_complete_source_recipe_checks_both_immutable_witnesses(self):
        proof = current.verify_sources()
        self.assertEqual(proof["freezer_sha256"], "a811548539232ee29f8fd1c52620e51778c2bf895df62847db4474591ec89564")
        self.assertEqual(proof["declared_console_entrypoint"], "biocompiler.entrypoint:main")
        self.assertEqual(proof["dispatcher"], {"path": "src/biocompiler/entrypoint.py",
                                             "sha256": current.policy.verify_entrypoint()["sha256"]})
        self.assertEqual({row["path"] for row in proof["routes"]}, set(current.policy.ROUTES))
        self.assertEqual(proof["package_metadata"], current.packaging.counterpart()[1])
        self.assertEqual(current.frozen.ENTRYPOINT, "from biocompiler.cli import main\nraise SystemExit(main())\n")

    def test_source_edits_and_redirected_sources_fail_before_capture(self):
        names = [current.FREEZER, current.policy.WITNESS, current.packaging.WITNESS,
                 current.policy.ENTRYPOINT, current.packaging.PATH, *sorted(current.policy.ROUTES)]
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for index, name in enumerate(names):
                root = base / str(index)
                self.source_copy(root)
                with self.subTest(path=name):
                    path = root / name
                    path.write_bytes(path.read_bytes() + b"\n")
                    with self.assertRaises((AssertionError, ValueError)):
                        current.verify_sources(root)
            for index, name in enumerate([current.FREEZER, current.policy.ENTRYPOINT, *sorted(current.policy.ROUTES)]):
                root = base / ("symlink-" + str(index))
                self.source_copy(root)
                path = root / name
                path.unlink(); path.symlink_to(current.ROOT / name)
                with self.subTest(symlink=name), self.assertRaises((AssertionError, ValueError)):
                    current.verify_sources(root)
        for name, value in (("ENTRYPOINT", current.frozen.ENTRYPOINT),
                            ("DECLARED_ENTRYPOINT", "biocompiler.cli:main")):
            with self.subTest(constant=name), patch.object(current, name, value), self.assertRaises(AssertionError):
                current.verify_sources()
        with patch.object(current, "verify_sources", side_effect=ValueError("source rejected")), \
                patch.object(current.frozen, "Corpus") as corpus, \
                patch.object(current.frozen, "owned_directories") as owned:
            with self.assertRaisesRegex(ValueError, "source rejected"):
                current.capture()
            corpus.assert_not_called(); owned.assert_not_called()

    def test_all_seventy_original_cases_use_unchanged_runner_and_truthful_metadata(self):
        frozen = current.frozen
        original = frozen.Corpus()
        cases = frozen.cases(original)
        expected = deepcopy(cases)
        baseline, _ = frozen.load()
        self.assertEqual([case["id"] for case in cases], [case["id"] for case in baseline["cases"]])
        scope = {"inert_source_scope": True}
        observed = []
        store_ids = set()
        old_shim, old_capture = frozen.ENTRYPOINT, frozen.capture
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            cli_root, original_root = base / "cli", base / "original"
            def execute(case, selected_scope, store):
                self.assertIs(case, cases[len(observed)])
                self.assertIs(selected_scope, scope)
                self.assertEqual((cli_root / "biocompiler").read_bytes(), current.ENTRYPOINT.encode())
                self.assertEqual((cli_root / "startup/sitecustomize.py").read_bytes(), frozen.STARTUP.encode())
                self.assertTrue((cli_root / "cwd").is_dir() and original_root.is_dir())
                observed.append(deepcopy(case)); store_ids.add(id(store))
                # Inert observations are retained verbatim, including failure.
                return {"id": case["id"], "argv": case["argv"], "entrypoint": case["entrypoint"],
                        "exit_code": len(observed) % 3, "stdout": store.retain(case["id"].encode()),
                        "opaque_observation": {"source_index": len(observed)}}
            with patch.object(frozen, "CLI_ROOT", cli_root), patch.object(frozen, "ORIGINAL_ROOT", original_root), \
                    patch.object(frozen, "Corpus", return_value=original), \
                    patch.object(frozen, "cases", return_value=cases) as definitions, \
                    patch.object(frozen, "actual_sources", return_value=scope) as sources, \
                    patch.object(frozen, "run_case", side_effect=execute) as runner:
                document, blobs = current.capture()
            self.assertFalse(cli_root.exists() or original_root.exists())
        self.assertEqual(observed, expected)
        definitions.assert_called_once_with(original)
        self.assertEqual(sources.call_count, 2)
        self.assertEqual(runner.call_count, 70)
        self.assertEqual(len(store_ids), 1)
        self.assertEqual(cases, expected)
        self.assertIs(frozen.capture, old_capture)
        self.assertEqual(frozen.ENTRYPOINT, old_shim)
        self.assertEqual(set(document), set(baseline))
        self.assertEqual(set(document["retained_source_bytes"]), set(baseline["retained_source_bytes"]))
        self.assertEqual(document["coverage"]["actual_children"], 70)
        self.assertEqual(document["coverage"]["entrypoints"], {"console": 66, "module": 4})
        environment = document["capture_environment"]
        self.assertEqual(environment["declared_console_entrypoint"], "biocompiler.entrypoint:main")
        self.assertEqual(frozen.restore(environment["entrypoint_source"], blobs), current.ENTRYPOINT.encode())
        self.assertEqual(frozen.restore(environment["startup"], blobs), frozen.STARTUP.encode())
        path_fields = {"entrypoint", "module_entrypoint", "exclusive_namespaces", "cwd",
                       "entrypoint_source", "declared_console_entrypoint"}
        self.assertEqual({k: v for k, v in environment.items() if k not in path_fields},
                         {k: v for k, v in baseline["capture_environment"].items() if k not in path_fields})
        self.assertEqual(environment["entrypoint"], ["python", str(cli_root / "biocompiler")])
        self.assertEqual(environment["module_entrypoint"], ["python", "-m", "biocompiler"])
        self.assertEqual(environment["exclusive_namespaces"], [str(original_root), str(cli_root)])
        self.assertEqual(environment["cwd"], str(cli_root / "cwd"))
        for name, ref in document["retained_source_bytes"].items():
            self.assertEqual(frozen.restore(ref, blobs), (current.ROOT / name).read_bytes())
        for index, row in enumerate(document["cases"], 1):
            self.assertEqual(row["exit_code"], index % 3)
            self.assertEqual(row["opaque_observation"], {"source_index": index})
            self.assertEqual(frozen.restore(row["stdout"], blobs), row["id"].encode())
        self.assertEqual(document["inventory_fingerprint"],
                         frozen.digest({k: v for k, v in document.items() if k != "inventory_fingerprint"}))

    def test_missing_duplicate_or_changed_entrypoint_census_never_starts_children(self):
        original = current.frozen.Corpus()
        cases = current.frozen.cases(original)
        mutated = deepcopy(cases)
        mutated[-1]["entrypoint"] = "console"
        for variant in (cases[:-1], cases[:-1] + cases[:1], mutated):
            with self.subTest(census=[row["id"] for row in variant]), \
                    patch.object(current.frozen, "Corpus", return_value=original), \
                    patch.object(current.frozen, "actual_sources", return_value={}), \
                    patch.object(current.frozen, "cases", return_value=variant), \
                    patch.object(current.frozen, "owned_directories") as owned, \
                    patch.object(current.frozen, "run_case") as runner:
                with self.assertRaisesRegex(AssertionError, "case census"):
                    current.capture()
                owned.assert_not_called(); runner.assert_not_called()

    def test_source_or_dispatch_changes_during_capture_cannot_produce_a_result(self):
        cases = [{"id": str(index), "entrypoint": "console" if index < 66 else "module", "argv": ["inspect"]}
                 for index in range(70)]
        for changed in ("source", "dispatch"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                sources = [{"original": True}, {"original": changed != "source"}]
                authorities = [{"original": True}, {"original": changed != "dispatch"}]
                with patch.object(current, "verify_sources", side_effect=authorities), \
                        patch.object(current.frozen, "Corpus"), \
                        patch.object(current.frozen, "cases", return_value=cases), \
                        patch.object(current.frozen, "actual_sources", side_effect=sources), \
                        patch.object(current.frozen, "CLI_ROOT", base / "cli"), \
                        patch.object(current.frozen, "ORIGINAL_ROOT", base / "original"), \
                        patch.object(current.frozen, "run_case", return_value={}) as runner:
                    expected = "Product source changed" if changed == "source" else "Reviewed dispatch source changed"
                    with self.assertRaisesRegex(AssertionError, expected):
                        current.capture()
                    self.assertEqual(runner.call_count, 70)
                self.assertFalse((base / "cli").exists() or (base / "original").exists())


if __name__ == "__main__":
    unittest.main()
