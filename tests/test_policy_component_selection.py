"""Selection SDK routes reuse the exact existing fresh atomic pair publisher."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from biocompiler.core_client import CoreProtocolError, encode_json
from biocompiler.policy import component_selection as sdk
from tests import test_core_policy_component_selection as peer


class PolicyComponentSelectionSdkTests(unittest.TestCase):
    def setUp(self):
        self.peer = peer.PolicyComponentSelectionTransportTests()
        self.peer.setUp()
        self.addCleanup(self.peer.doCleanups)

    def export(self, output, **kwargs):
        return sdk.export(self.peer.request, candidate=self.peer.candidate, limits=self.peer.limits,
                          client=self.peer.client, output=output, **kwargs)

    def test_prepare_is_inert_and_never_upgrades_explicit_budgets(self):
        original = deepcopy(self.peer.request)
        supplied = {key: original[key] for key in ("alternatives", "predicate", "budgets")}
        with patch("biocompiler.policy.validation.check", side_effect=AssertionError("No Python admission")):
            prepared = sdk.prepare_request(**supplied)
        original["alternatives"].clear()
        self.assertEqual(prepared, self.peer.request)
        supplied = {key: deepcopy(self.peer.request[key]) for key in ("alternatives", "predicate", "budgets")}
        supplied["budgets"].update(profile=peer.api.RESOURCE_PROFILE, max_report_nodes=249968)
        self.assertEqual(sdk.prepare_request(**supplied)["budgets"], supplied["budgets"])
        supplied["budgets"]["max_report_nodes"] = 249969
        with self.assertRaises(CoreProtocolError):
            sdk.prepare_request(**supplied)

    def test_fresh_pair_is_reproducible_and_retains_full_catalog(self):
        with tempfile.TemporaryDirectory() as directory, self.peer.exchange():
            first, second = (Path(directory) / name for name in ("first.zip", "second.zip"))
            exported = self.export(first)
            self.export(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), ["program.fasta", "manifest.json"])
                self.assertEqual(archive.read("program.fasta"), b">rna_0001 alphabet=RNA\nCCAUGGCUUAAGGAAAA\n")
                self.assertEqual(archive.read("manifest.json"), encode_json(exported.artifact["manifest"]))
                self.assertEqual(len(exported.artifact["manifest"]["request"]["alternatives"]), 2)
            self.assertEqual([call["operation"] for call in self.peer.calls], ["capabilities", "export-policy-component-selection"] * 2)
            self.assertFalse(list(Path(directory).glob(".policy-material-*")))

    def test_check_replay_routes_retain_complete_saved_wrapper(self):
        with self.peer.exchange():
            checked = sdk.check(self.peer.request, candidate=self.peer.candidate, limits=self.peer.limits, client=self.peer.client)
            replayed = sdk.replay(self.peer.request, candidate=self.peer.candidate, limits=self.peer.limits,
                                  report=checked.result, client=self.peer.client)
        self.assertEqual(checked.result, replayed.result)

    def test_compile_uses_explicit_core_without_artifact_or_python_admission(self):
        self.peer.core()
        with self.peer.exchange(), patch("biocompiler.policy.validation.check", side_effect=AssertionError("No Python admission")):
            compiled = sdk.compile(self.peer.request, limits=self.peer.limits, client=self.peer.client)
            checked = sdk.check(self.peer.request, candidate=compiled.candidate, limits=self.peer.limits, client=self.peer.client)
        self.assertEqual(compiled.result, checked.result)
        self.assertIsNone(compiled.artifact)
        self.assertEqual([call["operation"] for call in self.peer.calls],
                         ["capabilities", "compile-policy-component-selection", "capabilities", "check-policy-component-selection"])

    def test_existing_output_is_guarded_before_native_and_bad_export_never_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.zip"
            output.write_bytes(b"original")
            with patch.object(type(self.peer.client), "export", side_effect=AssertionError("Before native")), self.assertRaises(FileExistsError):
                self.export(output)
            with self.peer.exchange(mutate=lambda value: value["artifact"]["manifest"]["selected"].update(id="z-loser")), self.assertRaises(CoreProtocolError):
                self.export(output, replace=True)
            self.assertEqual(output.read_bytes(), b"original")
            self.assertFalse(list(Path(directory).glob(".policy-material-*")))
