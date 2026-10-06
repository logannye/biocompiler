"""Component installation must keep all four existing slots and original data."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def jobs(text):
    return {match[1]: match[2] for match in re.finditer(
        r"^  ([a-z][a-z0-9-]*):\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)",
        text.split("\njobs:\n", 1)[1], re.M | re.S)}


class ComponentInstallWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / ".github/workflows/ci.yml").read_text()

    def assert_component_path(self, text):
        workflow = jobs(text)
        for name in ("component_fixture", "component_install", "component_material_campaign", "material_consumer", "material_prebuilt"):
            self.assertIn("tests.test_policy_" + name, workflow["ci-preflight"])
        native = workflow["ocaml-build"]
        command = "python -B tools/check_policy_component_fixture.py emit"
        self.assertEqual(text.count(command), 1)
        self.assertLess(native.index("opam exec -- dune build --root core @all"), native.index(command))
        cleanup = "git clean -fdX -- src/biocompiler.egg-info"
        self.assertEqual(text.count(cleanup), 2)
        self.assertLess(native.index("python -m pip install ."), native.index(cleanup))
        self.assertLess(native.index(cleanup), native.index(command))
        self.assertLess(native.index(command), native.index("python tools/collect_prebuilt_materials.py"))
        self.assertIn("name: core-${{ matrix.platform }}\n          path: generated/core/", native)
        installed = workflow["policy-prebuilt-installed"]
        slots = re.findall(r'platform: ([a-z0-9_-]+)\n            python-version: "([0-9.]+)"', installed)
        self.assertEqual(slots, [("linux-x86_64", "3.11"), ("linux-x86_64", "3.14"),
                                 ("macos-arm64", "3.11"), ("macos-arm64", "3.14")])
        self.assertIn("needs: policy-prebuilt-sdk", installed)
        self.assertIn("name: core-${{ matrix.platform }}\n          path: artifacts/core-${{ matrix.platform }}", installed)
        self.assertEqual(installed.count("--component-fixture "), 1)
        self.assertEqual(installed.count("--component-provenance "), 1)
        self.assertIn('--fixture "$GITHUB_WORKSPACE/core/test/data/policy_material_request_v01.json"', installed)
        for flag, name in (("fixture", "originals.json"), ("provenance", "provenance.json")):
            self.assertIn('--component-' + flag + ' "$GITHUB_WORKSPACE/artifacts/core-${{ matrix.platform }}/component-originals/' + name + '"', installed)
        comparison = workflow["policy-prebuilt-reproducibility"]
        self.assertLess(comparison.index("python -m pip install ."), comparison.index(cleanup))
        self.assertLess(comparison.index(cleanup), comparison.index("python tools/check_policy_material_prebuilt.py"))
        self.assertIn("needs: [policy-prebuilt-sdk, policy-prebuilt-installed]", comparison)
        self.assertEqual(comparison.count("--component-fixture "), 2)
        self.assertEqual(comparison.count("--component-provenance "), 2)
        for target in ("linux-x86_64", "macos-arm64"):
            self.assertIn("name: core-" + target + "\n          path: artifacts/component-originals/core-" + target, comparison)
            for flag, name in (("fixture", "originals.json"), ("provenance", "provenance.json")):
                self.assertIn("--component-" + flag + " artifacts/component-originals/core-" + target
                              + "/component-originals/" + name, comparison)
        for minor in ("3.11", "3.14"):
            for target in ("linux-x86_64", "macos-arm64"):
                self.assertIn("--compare artifacts/installed/policy-prebuilt-" + target + "-py" + minor, comparison)
        self.assertNotIn("component_fixture_export", installed + comparison)
        self.assertNotIn("check_policy_component_fixture.py emit", installed + comparison)
        self.assertNotIn("--component-fixture", workflow["architecture-sdk"])

    def test_complete_component_originals_flow_uses_the_existing_four_slots(self):
        self.assert_component_path(self.text)

    def test_missing_provenance_slot_or_build_order_cannot_satisfy_the_contract(self):
        mutations = [
            self.text.replace("git clean -fdX -- src/biocompiler.egg-info", "true", 1),
            self.text.replace(" tests.test_policy_component_fixture", "", 1),
            self.text.replace("python -B tools/check_policy_component_fixture.py emit", "true", 1),
            self.text.replace("--component-provenance ", "--unreviewed-provenance ", 1),
            self.text.replace("name: core-${{ matrix.platform }}\n          path: artifacts/core-${{ matrix.platform }}",
                              "name: stale-core\n          path: artifacts/core-${{ matrix.platform }}", 1),
            self.text.replace("--component-fixture artifacts/component-originals/core-macos-arm64/", "--component-fixture stale/", 1),
            self.text.replace("--compare artifacts/installed/policy-prebuilt-macos-arm64-py3.14", "--compare absent", 1),
            self.text.replace("opam exec -- dune build --root core @all", "echo build omitted", 1),
        ]
        for index, text in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises((AssertionError, ValueError)):
                self.assert_component_path(text)


if __name__ == "__main__":
    unittest.main()
