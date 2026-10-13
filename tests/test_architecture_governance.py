"""Adversarial documentation drift controls; no compiler or native execution."""
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from tools import check_architecture_governance as gate


class ArchitectureGovernanceTests(unittest.TestCase):
    def altered(self, relative, transform):
        read = Path.read_text
        target = gate.ROOT / relative

        def replacement(path, *args, **kwargs):
            text = read(path, *args, **kwargs)
            return transform(text) if path == target else text

        return patch.object(Path, "read_text", replacement)

    def test_current_guidance_is_connected_without_claiming_compiler_acceptance(self):
        result = gate.check()
        self.assertEqual(result["status"], "documentation_integrity_checked")
        self.assertIn("not semantic compliance", result["claim_scope"])
        self.assertGreater(result["capability_rows"], 0)

    def test_deleted_duplicate_and_unknown_principles_fail(self):
        changes = (
            (gate.CHARTER, lambda text: text.replace("### AC-01", "### Removed", 1)),
            (gate.CHARTER, lambda text: text + "\n### AC-01 — Duplicate\n"),
            (gate.ROADMAP, lambda text: text + "\nAC-99 is undefined.\n"),
            (gate.REVIEW, lambda text: text.replace("AC-09", "AC-08")),
        )
        for relative, transform in changes:
            with self.subTest(relative=relative), self.altered(relative, transform):
                with self.assertRaises(gate.GovernanceError):
                    gate.check()

    def test_missing_and_outside_repository_targets_fail(self):
        for target in ("does-not-exist.md", "../../outside-project.md"):
            with self.subTest(target=target), self.altered(
                gate.REVIEW, lambda text: text + f"\n[broken]({target})\n"
            ), self.assertRaisesRegex(gate.GovernanceError, "link"):
                gate.check()

    def test_dangling_heading_reference_fails(self):
        with self.altered(gate.MATRIX, lambda text: text.replace(
            "#cap-01-policy-source", "#cap-01-missing-heading"
        )), self.assertRaisesRegex(gate.GovernanceError, "heading anchor"):
            gate.check()

    def test_valid_anchored_entrypoint_remains_connected(self):
        with self.altered("README.md", lambda text: text.replace(
            "(docs/architecture-charter.md)", "(docs/architecture-charter.md#product-contract)"
        )):
            self.assertEqual(gate.check()["status"], "documentation_integrity_checked")

    def test_commented_or_example_links_do_not_replace_required_navigation(self):
        original = next(line for line in (gate.ROOT / "README.md").read_text().splitlines()
                        if "docs/architecture-charter.md" in line)
        for wrapper in ("<!-- {} -->", "```md\n{}\n```", "~~~md\n{}\n~~~"):
            with self.subTest(wrapper=wrapper), self.altered("README.md", lambda _: wrapper.format(original)):
                with self.assertRaisesRegex(gate.GovernanceError, "navigation"):
                    gate.check()

    def test_duplicate_capability_id_and_removed_runtime_catalog_link_fail(self):
        duplicate = re.search(r"^#{2,3} CAP-\d{2}.*$", (gate.ROOT / gate.MATRIX).read_text(), re.M).group()
        for transform in (
            lambda text: text + "\n" + duplicate + "\n",
            lambda text: text.replace("../" + gate.CATALOG, "../README.md"),
        ):
            with self.altered(gate.MATRIX, transform), self.assertRaises(gate.GovernanceError):
                gate.check()

    def test_commented_out_ci_hooks_fail(self):
        for relative in gate.WORKFLOWS:
            with self.subTest(relative=relative), self.altered(
                relative, lambda text: text.replace(
                    "python -B tools/check_architecture_governance.py",
                    "# python -B tools/check_architecture_governance.py"
                )
            ), self.assertRaisesRegex(gate.GovernanceError, "preflight command"):
                gate.check()

    def test_cli_failure_is_nonzero_with_actionable_diagnostic(self):
        error = io.StringIO()
        with patch.object(gate.sys, "argv", ["check"]), redirect_stderr(error), \
                redirect_stdout(io.StringIO()), patch.object(gate, "check", side_effect=gate.GovernanceError("missing required file")):
            self.assertEqual(gate.main(), 1)
        self.assertIn("missing required file", error.getvalue())


if __name__ == "__main__":
    unittest.main()
