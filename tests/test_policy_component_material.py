"""Component SDK routing through the shared, freshly checked pair publisher.

Peers are synthetic transport records, not native component admission evidence.
The legacy material publisher suite separately covers all ZIP failure modes.
"""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from biocompiler.core_client import CoreCancelled, CoreProtocolError, CoreTransportError, encode_json
from biocompiler.policy import component_material as sdk
from tests import test_core_policy_component_material as peer


class PolicyComponentMaterialSdkTests(unittest.TestCase):
    def setUp(self):
        self.peer = peer.PolicyComponentMaterialTransportTests()
        self.addCleanup(self.peer.doCleanups)
        self.peer.setUp()

    def export(self, output, **kwargs):
        return sdk.export(self.peer.request, candidate=self.peer.candidate, limits=self.peer.limits,
                          client=self.peer.client, output=output, **kwargs)

    def test_complete_original_request_snapshot_is_inert(self):
        original = deepcopy(self.peer.request)
        fields = {key: deepcopy(value) for key, value in original.items() if key not in ("schema_version", "profile")}
        with patch("biocompiler.policy.validation.check", side_effect=AssertionError("No Python admission")):
            request = sdk.prepare_request(**fields)
        self.assertEqual(request, original)
        for key in fields:
            fields[key].clear()
        self.assertEqual(request, original)
        fields = {key: deepcopy(value) for key, value in original.items() if key not in ("schema_version", "profile")}
        for key in fields:
            for invalid in (lambda: original, object()):
                with self.subTest(key=key, invalid=type(invalid).__name__), self.assertRaises(CoreProtocolError):
                    sdk.prepare_request(**{**fields, key: invalid})

    def test_nonpublication_routes_retain_complete_inputs_and_replay_wrapper(self):
        with self.peer.exchange(), patch("biocompiler.policy.validation.check", side_effect=AssertionError("No fallback")):
            compiled = sdk.compile(self.peer.request, limits=self.peer.limits, client=self.peer.client)
            checked = sdk.check(self.peer.request, candidate=compiled.candidate, limits=self.peer.limits, client=self.peer.client)
            replayed = sdk.replay(self.peer.request, candidate=compiled.candidate, limits=self.peer.limits,
                                  report=checked.result, client=self.peer.client)
        self.assertEqual(compiled.result, replayed.result)
        self.assertEqual(self.peer.calls[-1]["payload"], {"request": self.peer.request, "candidate": compiled.candidate,
                                                       "limits": self.peer.limits, "report": checked.result})

    def test_fresh_component_pair_has_deterministic_archive_and_full_originals(self):
        with tempfile.TemporaryDirectory() as directory, self.peer.exchange():
            first, second = (Path(directory) / name for name in ("one.zip", "two.zip"))
            exported = self.export(first)
            self.export(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(exported.artifact["manifest"]["request"], self.peer.request)
            self.assertEqual(exported.artifact["manifest"]["candidate"], self.peer.candidate)
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), ["program.fasta", "manifest.json"])
                self.assertEqual(archive.read("program.fasta"), exported.artifact["fasta"].encode())
                self.assertEqual(archive.read("manifest.json"), encode_json(exported.artifact["manifest"]))
                for item in archive.infolist():
                    self.assertEqual(item.compress_type, zipfile.ZIP_STORED)
                    self.assertEqual(item.date_time, (1980, 1, 1, 0, 0, 0))
            self.assertEqual([row["operation"] for row in self.peer.calls], ["capabilities", "export-policy-component-material"] * 2)
            self.assertFalse(list(Path(directory).glob(".policy-material-*")))

    def test_output_guards_run_before_component_native_callback(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.zip"
            output.write_bytes(b"original")
            with patch.object(type(self.peer.client), "export", side_effect=AssertionError("Before native")):
                with self.assertRaises(FileExistsError):
                    self.export(output)
                with self.assertRaises(ValueError):
                    self.export(output, replace=True, input_paths=[output])
                with self.assertRaises(ValueError):
                    self.export(Path(directory) / "single.fasta")
            self.assertEqual(output.read_bytes(), b"original")
            with self.peer.exchange():
                self.export(output, replace=True)
            self.assertTrue(zipfile.is_zipfile(output))

    def test_component_failure_or_incomplete_pair_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.zip"
            output.write_bytes(b"original")
            for options, error in (({"failure": CoreTransportError("native failed")}, CoreTransportError),
                                   ({"accepted": False}, CoreProtocolError),
                                   ({"mutate": lambda value: value.update(artifact=None)}, CoreProtocolError)):
                with self.subTest(options=options), self.peer.exchange(**options), self.assertRaises(error):
                    self.export(output, replace=True)
                self.assertEqual(output.read_bytes(), b"original")
                self.assertFalse(list(Path(directory).glob(".policy-material-*")))

    def test_shared_writer_errors_and_cancellation_do_not_publish_component_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.zip"
            output.write_bytes(b"original")
            for target in ("biocompiler.policy.material.os.fsync", "biocompiler.policy.material.os.replace"):
                with self.subTest(target=target), self.peer.exchange(), patch(target, side_effect=OSError("write failed")), self.assertRaises(OSError):
                    self.export(output, replace=True)
                self.assertEqual(output.read_bytes(), b"original")
                self.assertFalse(list(Path(directory).glob(".policy-material-*")))
            with self.peer.exchange(), self.assertRaises(CoreCancelled):
                self.export(output, replace=True, cancelled=lambda: True)
            self.assertEqual(output.read_bytes(), b"original")

    def test_legacy_operation_cannot_be_published_as_component_export(self):
        with tempfile.TemporaryDirectory() as directory, self.peer.exchange():
            output = Path(directory) / "result.zip"
            exported = self.peer.client.export(self.peer.request, self.peer.candidate, self.peer.limits)
            # The shared writer independently binds the callback result's operation.
            from dataclasses import replace
            forged = replace(exported, operation="export-policy-material")
            with patch.object(type(self.peer.client), "export", return_value=forged), self.assertRaises(CoreProtocolError):
                self.export(output)
            self.assertFalse(output.exists())

    def test_outer_cleanup_restores_all_shared_peer_patches(self):
        prior = peer.old.peer.assessment
        prior_source = peer.old.peer.source_peer.source_assessment
        outer = PolicyComponentMaterialSdkTests("test_complete_original_request_snapshot_is_inert")
        self.addCleanup(outer.doCleanups)
        outer.setUp()
        self.assertIsNot(peer.old.peer.assessment, prior)
        self.assertIsNot(peer.old.peer.source_peer.source_assessment, prior_source)
        outer.doCleanups()
        self.assertIs(peer.old.peer.assessment, prior)
        self.assertIs(peer.old.peer.source_peer.source_assessment, prior_source)


if __name__ == "__main__":
    unittest.main()
