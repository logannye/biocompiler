"""Inert object-store and workflow fixtures; no Git/native/network execution."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import ci_change_scope as scope


def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


class ChangeScopeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.base, self.source, self.tested = "a" * 40, "b" * 40, "c" * 40
        self.parents = [self.base, self.source]
        common = {path: ("100644", ("inert policy " + path + "\n").encode()) for path in scope.POLICY_FILES}
        self.files = {self.base: {**common, "README.md": ("100644", b"# Before\n")},
                      self.source: {**common, "README.md": ("100644", b"# After\n")},
                      self.tested: {**common, "README.md": ("100644", b"# After\n")}}
        for name, (_, raw) in self.files[self.tested].items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.env = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                    "GITHUB_REPOSITORY": scope.REPOSITORY, "GITHUB_WORKSPACE": str(self.root),
                    "GITHUB_SHA": self.tested, "GITHUB_REF": "refs/pull/99/merge",
                    "GITHUB_WORKFLOW_REF": scope.REPOSITORY + "/" + scope.WORKFLOW + "@refs/pull/99/merge",
                    "GITHUB_WORKFLOW_SHA": self.tested, "GITHUB_EVENT_NAME": "pull_request",
                    "GITHUB_RUN_ID": "1234", "GITHUB_RUN_ATTEMPT": "1"}
        self.event = {"repository": {"full_name": scope.REPOSITORY}, "number": 99,
                      "pull_request": {"base": {"sha": self.base, "repo": {"full_name": scope.REPOSITORY}},
                                       "head": {"sha": self.source}}}
        self.calls, self.diff_override = [], None
        self.nonancestor = False
        self.patch = patch.object(scope, "git_bytes", side_effect=self.git)
        self.patch.start(); self.addCleanup(self.patch.stop)
        process = patch.object(scope.subprocess, "Popen", side_effect=AssertionError("No process allowed"))
        process.start(); self.addCleanup(process.stop)

    def git(self, root, *args, maximum=scope.MAX_DIFF):
        self.assertEqual(root, self.root)
        self.calls.append(args)
        if args == ("rev-parse", "HEAD"):
            return self.tested.encode() + b"\n"
        if args[:2] == ("rev-parse", "--verify"):
            revision = args[2].removesuffix("^{tree}")
            if revision not in self.files:
                raise scope.GitUnavailable("Missing commit")
            return hashlib.sha1(revision.encode()).hexdigest().encode() + b"\n"
        if args[:3] == ("show", "-s", "--format=%P"):
            return " ".join(self.parents).encode() + b"\n"
        if args[:2] == ("merge-base", "--is-ancestor"):
            if self.nonancestor or args[2] not in self.files:
                raise scope.GitUnavailable("Missing or nonancestor base")
            return b""
        if args[0] == "diff-tree":
            self.assertEqual(args[:8], ("diff-tree", "--no-commit-id", "-r", "--raw", "--no-renames",
                                         "--no-ext-diff", "--no-abbrev", "-z"))
            self.assertEqual(args[-1], "--")
            if self.diff_override is not None:
                return self.diff_override
            try:
                before, after = self.files[args[8]], self.files[args[9]]
            except KeyError:
                raise scope.GitUnavailable("Missing commit") from None
            rows = []
            for name in sorted(before.keys() | after.keys()):
                old, new = before.get(name), after.get(name)
                if old == new:
                    continue
                rows.append(self.raw_row(name, old, new))
            return b"".join(rows)
        if args[0] == "ls-tree":
            self.assertEqual(args[:3], ("ls-tree", "-z", "--full-tree"))
            self.assertEqual(args[4], "--")
            value = self.files[args[3]].get(args[5])
            return (f"{value[0]} blob {blob(value[1])}\t{args[5]}\0".encode() if value else b"")
        if args[0] == "cat-file":
            matches = [raw for files in self.files.values() for _, raw in files.values() if blob(raw) == args[2]]
            if not matches:
                raise scope.GitUnavailable("Missing blob")
            raw = matches[0]
            if args[1] == "-s":
                return str(len(raw)).encode() + b"\n"
            self.assertEqual(args[1], "blob")
            return raw
        raise AssertionError("Unexpected Git operation: " + str(args))

    @staticmethod
    def raw_row(name, old, new):
        old_mode, old_blob = (old[0], blob(old[1])) if old else ("000000", scope.ZERO)
        new_mode, new_blob = (new[0], blob(new[1])) if new else ("000000", scope.ZERO)
        status = "A" if old is None else "D" if new is None else "M"
        return f":{old_mode} {new_mode} {old_blob} {new_blob} {status}\0{name}\0".encode()

    def plan(self):
        return scope.derive_plan(self.root, env=self.env, event=self.event)

    def docs(self, plan):
        return scope.derive_docs(self.root, plan, env=self.env, event=self.event)

    def push(self):
        self.env.update(GITHUB_EVENT_NAME="push", GITHUB_REF="refs/heads/main",
                        GITHUB_WORKFLOW_REF=scope.REPOSITORY + "/" + scope.WORKFLOW + "@refs/heads/main")
        self.event = {"repository": {"full_name": scope.REPOSITORY}, "ref": "refs/heads/main",
                      "before": self.base, "after": self.tested, "deleted": False}

    def test_exact_pr_readme_plan_and_bounded_docs_are_distinct_nonacceptance(self):
        plan = self.plan()
        self.assertEqual(plan["scope"], "docs_only")
        self.assertEqual(plan["reasons"], [])
        self.assertEqual([row["kind"] for row in plan["comparisons"]], ["tested", "source"])
        self.assertEqual(plan["comparisons"][0]["changes"], [{"path": "README.md", "old_mode": "100644",
            "new_mode": "100644", "old_blob": blob(b"# Before\n"), "new_blob": blob(b"# After\n"), "status": "M"}])
        self.assertEqual([p["path"] for p in plan["policy"]], list(scope.POLICY_FILES))
        receipt = self.docs(plan)
        self.assertEqual(receipt["schema_version"], scope.DOCS_SCHEMA)
        self.assertEqual(receipt["status"], "pass")
        self.assertEqual(receipt["documents"], [{"path": "README.md", "mode": "100644",
            "git_blob": blob(b"# After\n"), "sha256": hashlib.sha256(b"# After\n").hexdigest(), "size": 8}])
        self.assertIs(receipt["acceptance"], False)
        self.assertIs(receipt["package_release_qualified"], False)
        self.assertEqual(receipt["native_validation"], "not_run")
        self.assertEqual(receipt["installed_validation"], "not_run")
        self.assertEqual(scope.validate_docs(self.root, plan, receipt, env=self.env, event=self.event), receipt)

    def test_main_uses_exact_push_before_not_only_first_parent(self):
        self.push()
        self.parents = ["e" * 40]
        plan = self.plan()
        self.assertEqual(plan["scope"], "docs_only")
        self.assertEqual(len(plan["comparisons"]), 1)
        self.assertEqual(plan["comparisons"][0]["base_revision"], self.base)
        self.assertIn(("merge-base", "--is-ancestor", self.base, self.tested), self.calls)
        self.assertNotIn(("show", "-s", "--format=%P", self.tested), self.calls)

    def test_code_change_cannot_hide_in_a_readme_push(self):
        self.push()
        self.files[self.tested]["src/core.py"] = ("100644", b"changed code\n")
        plan = self.plan()
        self.assertEqual(plan["scope"], "full")
        self.assertEqual([r["path"] for r in plan["comparisons"][0]["changes"]], ["README.md", "src/core.py"])
        with self.assertRaisesRegex(ValueError, "eligible"):
            self.docs(plan)

    def test_conservative_source_comparison_catches_changed_head_even_if_merge_readme_only(self):
        self.files[self.source]["src/not_in_merge.py"] = ("100644", b"source change")
        plan = self.plan()
        self.assertEqual(plan["scope"], "full")
        self.assertIn("source:changed_path_outside_readme_allowlist", plan["reasons"])

    def test_added_deleted_renamed_mode_symlink_and_submodule_readme_select_full(self):
        original = deepcopy(self.files)
        mutations = ("added", "deleted", "renamed", "executable", "symlink", "submodule")
        for mutation in mutations:
            self.files = deepcopy(original)
            for revision in (self.source, self.tested):
                if mutation == "added": self.files[self.base].pop("README.md", None)
                elif mutation == "deleted": self.files[revision].pop("README.md")
                elif mutation == "renamed": self.files[revision]["GUIDE.md"] = self.files[revision].pop("README.md")
                else: self.files[revision]["README.md"] = ({"executable": "100755", "symlink": "120000", "submodule": "160000"}[mutation], b"changed\n")
            with self.subTest(mutation=mutation):
                self.assertEqual(self.plan()["scope"], "full")

    def test_unknown_docs_and_empty_diff_are_full_not_implicitly_safe(self):
        self.files[self.source] = deepcopy(self.files[self.base])
        self.files[self.tested] = deepcopy(self.files[self.base])
        self.assertEqual(self.plan()["reasons"], ["source:empty_diff", "tested:empty_diff"])
        for revision in (self.source, self.tested):
            self.files[revision]["docs/semantic-authority.md"] = ("100644", b"new\n")
        self.assertEqual(self.plan()["scope"], "full")

    def test_missing_new_and_nonancestor_history_fall_back_to_full(self):
        self.push()
        for before in (scope.ZERO, "f" * 40):
            self.event["before"] = before
            with self.subTest(before=before): self.assertEqual(self.plan()["scope"], "full")
        self.event["before"] = self.base
        self.nonancestor = True
        self.assertEqual(self.plan()["scope"], "full")

    def test_manual_dispatch_always_full(self):
        self.env.update(GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_REF="refs/heads/main",
                        GITHUB_WORKFLOW_REF=scope.REPOSITORY + "/" + scope.WORKFLOW + "@refs/heads/main")
        self.assertEqual(self.plan()["reasons"], ["manual_dispatch_requires_full"])

    def test_invalid_identity_hard_fails_before_diff(self):
        original = dict(self.env)
        mutations = {"GITHUB_ACTIONS": "false", "RUNNER_ENVIRONMENT": "self-hosted",
                     "GITHUB_REPOSITORY": "other/repo", "GITHUB_WORKSPACE": "/another",
                     "GITHUB_SHA": "f" * 40, "GITHUB_WORKFLOW_SHA": "f" * 40,
                     "GITHUB_WORKFLOW_REF": "other", "GITHUB_RUN_ID": "0", "GITHUB_RUN_ATTEMPT": "0",
                     "GITHUB_REF": "refs/heads/main", "GITHUB_EVENT_NAME": "unknown"}
        for field, value in mutations.items():
            self.env = {**original, field: value}; self.calls.clear()
            with self.subTest(field=field), self.assertRaises(ValueError): self.plan()
            self.assertFalse(any(call[0] == "diff-tree" for call in self.calls))
        self.env = original

    def test_wrong_event_repository_or_merge_parents_hard_fail(self):
        for parents in ([self.source, self.base], [self.base], [self.base, "e" * 40]):
            self.parents = parents
            with self.assertRaisesRegex(ValueError, "merge parents"): self.plan()
        self.parents = [self.base, self.source]
        self.event["repository"] = {"full_name": "other/repository"}
        with self.assertRaisesRegex(ValueError, "repository"): self.plan()

    def test_malformed_event_and_main_identity_are_hard_failures(self):
        original = deepcopy(self.event)
        for changed in ({**original, "repository": []}, {**original, "number": True},
                        {**original, "pull_request": []},
                        {**original, "pull_request": {"base": [], "head": {}}}):
            self.event = changed
            with self.subTest(event=changed), self.assertRaises(ValueError): self.plan()
        self.push(); original = deepcopy(self.event)
        for field, value in (("after", "f" * 40), ("before", "bad"), ("deleted", True),
                             ("deleted", 0), ("ref", "refs/heads/feature")):
            self.event = {**original, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError): self.plan()

    def test_policy_missing_changed_or_working_bytes_modified_is_never_docs_only(self):
        original = deepcopy(self.files)
        for relative in scope.POLICY_FILES:
            self.files = deepcopy(original)
            del self.files[self.base][relative]
            with self.subTest(path=relative, change="missing"):
                self.assertEqual(self.plan()["scope"], "full")
            self.files = deepcopy(original)
            self.files[self.tested][relative] = ("100644", b"new routing rule\n")
            with self.subTest(path=relative, change="changed"):
                self.assertEqual(self.plan()["scope"], "full")
        self.files = original
        target = self.root / scope.POLICY_FILES[-1]
        target.write_bytes(b"modified working policy\n")
        self.assertEqual(self.plan()["scope"], "full")

    def test_parse_raw_nul_diff_rejects_truncation_duplicate_unbounded_and_rename_encoding(self):
        raw = self.raw_row("README.md", ("100644", b"old"), ("100644", b"new"))
        for changed in (raw[:-1], raw + raw, raw.replace(b" M\0", b" R100\0"), b"not a raw diff\0"):
            with self.assertRaises(ValueError): scope.parse_raw_diff(changed)
        with patch.object(scope, "MAX_ROWS", 0), self.assertRaises(ValueError): scope.parse_raw_diff(raw)
        with patch.object(scope, "MAX_DIFF", 1), self.assertRaises(ValueError): scope.parse_raw_diff(raw)
        # Such a name remains visible and is never in the exact allowlist.
        row = scope.parse_raw_diff(raw.replace(b"README.md\0", b"../README.md\0"))
        self.assertTrue(scope.classify_rows(row))

    def test_unfamiliar_diff_encoding_selects_full(self):
        for raw in (b"invalid\0", self.raw_row("README.md", None, ("100644", b"x")).replace(b"README.md", b"\xff")):
            self.diff_override = raw
            self.assertEqual(self.plan()["scope"], "full")

    def test_docs_reject_working_byte_mode_symlink_and_blob_bound_changes(self):
        plan = self.plan(); target = self.root / "README.md"
        target.write_bytes(b"changed after planning\n")
        with self.assertRaisesRegex(ValueError, "working bytes"): self.docs(plan)
        target.write_bytes(b"# After\n"); target.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "executable"): self.docs(plan)
        target.chmod(0o644); target.unlink(); target.symlink_to(self.root / "other")
        with self.assertRaises(ValueError): self.docs(plan)
        target.unlink(); target.write_bytes(b"# After\n")
        with patch.object(scope, "MAX_DOCUMENT", 7), self.assertRaisesRegex(ValueError, "bound"):
            self.docs(plan)

    def test_text_checks_are_bounded_and_never_evaluate_markdown(self):
        raw = b"# README\nText  \n```sh\n$(do-not-execute)\n```\n[link](https://example.invalid)\n"
        checked = scope.check_document(raw)
        self.assertIs(checked["snippets_executed"], False)
        self.assertIs(checked["network_links_followed"], False)
        for bad in (b"", b"missing newline", b"null\0\n", b"bad\xff\n", b"x\r\n", b"trailing \n", b"   \n"):
            with self.subTest(raw=bad), self.assertRaises(ValueError): scope.check_document(bad)
        with patch.object(scope, "MAX_DOCUMENT", 1), self.assertRaises(ValueError): scope.check_document(b"x\n")

    def test_rehashed_plan_or_docs_cannot_redefine_scope_or_authority(self):
        plan = self.plan(); receipt = self.docs(plan)
        for field, value in (("scope", "full"), ("policy", []), ("comparisons", []), ("acceptance", True)):
            changed = {**plan, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                scope.validate_plan(self.root, changed, env=self.env, event=self.event)
        for field, value in (("documents", []), ("checks", {}), ("package_release_qualified", True), ("native_validation", "pass")):
            changed = {**receipt, field: value}
            with self.subTest(field=field), self.assertRaises(ValueError):
                scope.validate_docs(self.root, plan, changed, env=self.env, event=self.event)

    def test_same_run_prior_attempt_is_retained_without_relabeling(self):
        plan = self.plan(); receipt = self.docs(plan)
        self.env["GITHUB_RUN_ATTEMPT"] = "2"
        self.assertEqual(scope.validate_plan(self.root, plan, env=self.env, event=self.event), plan)
        self.assertEqual(scope.validate_docs(self.root, plan, receipt, env=self.env, event=self.event), receipt)
        self.assertEqual(self.docs(plan)["identity"]["run_attempt"], "2")

    def test_future_cross_run_and_docs_predating_plan_reject(self):
        plan = self.plan(); receipt = self.docs(plan)
        for field, value in (("run_attempt", "2"), ("run_id", "another"), ("revision", "f" * 40)):
            changed = deepcopy(plan); changed["identity"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                scope.validate_plan(self.root, changed, env=self.env, event=self.event)
        self.env["GITHUB_RUN_ATTEMPT"] = "2"
        later_plan = self.plan(); later_docs = self.docs(later_plan)
        later_docs["identity"]["run_attempt"] = "1"
        with self.assertRaisesRegex(ValueError, "predates"):
            scope.validate_docs(self.root, later_plan, later_docs, env=self.env, event=self.event)
        receipt["identity"]["run_attempt"] = "3"
        with self.assertRaisesRegex(ValueError, "future"):
            scope.validate_docs(self.root, plan, receipt, env=self.env, event=self.event)

    def test_late_document_change_prevents_success_receipt(self):
        plan = self.plan(); original = scope.check_document
        def change(raw):
            result = original(raw)
            (self.root / "README.md").write_bytes(b"late changed bytes\n")
            return result
        with patch.object(scope, "check_document", side_effect=change), self.assertRaisesRegex(ValueError, "changed during"):
            self.docs(plan)

    def test_late_policy_change_prevents_document_success(self):
        plan = self.plan(); original = scope.check_document
        def change(raw):
            result = original(raw)
            (self.root / scope.POLICY_FILES[-1]).write_bytes(b"late control change\n")
            return result
        with patch.object(scope, "check_document", side_effect=change), self.assertRaisesRegex(ValueError, "fresh source"):
            self.docs(plan)

    def test_json_duplicate_nonfinite_oversized_and_symlink_reject(self):
        for raw in (b'{"a":1,"a":2}', b'{"x":NaN}'):
            with self.assertRaises(ValueError): scope.document(raw)
        path = self.root / "plan.json"; path.symlink_to(self.root / "other")
        with self.assertRaises(ValueError): scope.read_json(path)
        with patch.object(scope, "MAX_JSON", 1), self.assertRaises(ValueError): scope.document(b"{}")

    def test_cli_publishes_only_exact_scope_output_and_distinct_docs_receipt(self):
        event_path = self.root / "event.json"; event_path.write_text(json.dumps(self.event))
        github_output = self.root / "github-output"; github_output.touch()
        env = {**self.env, "GITHUB_EVENT_PATH": str(event_path), "GITHUB_OUTPUT": str(github_output)}
        plan_path, docs_path = self.root / "plan.json", self.root / "docs.json"
        with patch.dict(scope.os.environ, env, clear=True), patch.object(scope, "__file__", str(self.root / "tools/ci_change_scope.py")):
            self.assertEqual(scope.main(["plan", "--output", str(plan_path), "--github-output", str(github_output)]), 0)
            self.assertEqual(scope.main(["docs", "--plan", str(plan_path), "--output", str(docs_path)]), 0)
        self.assertEqual(github_output.read_text(), "scope=docs_only\n")
        self.assertEqual(scope.read_json(docs_path)["schema_version"], scope.DOCS_SCHEMA)


class BoundedGitTests(unittest.TestCase):
    def test_git_reader_bounds_stdout_kills_process_and_disables_lazy_network_and_replacements(self):
        class Process:
            def __init__(self): self.stdout = io.BytesIO(b"12345"); self.killed = False
            def poll(self): return None if not self.killed else -9
            def wait(self): return 0
            def kill(self): self.killed = True
        process = Process()
        with patch.object(scope.subprocess, "Popen", return_value=process) as launch:
            with self.assertRaises(scope.GitUnavailable): scope.git_bytes(Path("."), "rev-parse", "HEAD", maximum=4)
        self.assertTrue(process.killed)
        self.assertTrue(process.stdout.closed)
        environment = launch.call_args.kwargs["env"]
        self.assertEqual(environment["GIT_NO_LAZY_FETCH"], "1")
        self.assertEqual(environment["GIT_NO_REPLACE_OBJECTS"], "1")
        self.assertEqual(environment["GIT_OPTIONAL_LOCKS"], "0")

    def test_nonzero_git_exit_cannot_supply_comparison_bytes(self):
        class Process:
            stdout = io.BytesIO(b"success shaped but failed")
            def poll(self): return 1
            def wait(self): return 1
        with patch.object(scope.subprocess, "Popen", return_value=Process()):
            with self.assertRaisesRegex(scope.GitUnavailable, "unavailable"):
                scope.git_bytes(Path("."), "rev-parse", "HEAD")


if __name__ == "__main__":
    unittest.main()
