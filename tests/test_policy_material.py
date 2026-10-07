"""Material request snapshots and atomic publication of fresh native bytes."""
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from biocompiler.core_client import CoreCancelled, CoreProtocolError, CoreTransportError, encode_json
from biocompiler.policy import material as sdk
from tests import test_core_policy_material as peer


class PolicyMaterialSdkTests(unittest.TestCase):
    def setUp(self):
        self.peer = peer.PolicyMaterialTransportTests()
        self.addCleanup(self.peer.doCleanups)
        self.peer.setUp()

    def export(self, output, **kwargs):
        return sdk.export(self.peer.request, candidate=self.peer.candidate, limits=self.peer.limits,
                          client=self.peer.client, output=output, **kwargs)

    def test_complete_request_snapshot_preserves_external_authority(self):
        original = deepcopy(self.peer.request)
        fields = {key: deepcopy(original[key]) for key in ("implementation_request", "material_contract", "context", "catalog_binding", "budgets")}
        with patch("biocompiler.policy.validation.check", side_effect=AssertionError("No Python admission")):
            request = sdk.prepare_request(**fields)
        self.assertEqual(request, original)
        fields["material_contract"]["body"]["carriers"].clear()
        fields["implementation_request"]["document"]["program"]["declarations"].clear()
        self.assertEqual(request, original)
        for malformed in (original["implementation_request"]["document"], lambda: original, object()):
            with self.assertRaises(CoreProtocolError):
                sdk.prepare_request(**{**fields, "implementation_request": malformed})

    def test_all_nonpublication_routes_use_native_original_inputs(self):
        with self.peer.exchange(), patch("biocompiler.policy.validation.check", side_effect=AssertionError("No fallback")):
            compiled = sdk.compile(self.peer.request, limits=self.peer.limits, client=self.peer.client)
            checked = sdk.check(self.peer.request, candidate=compiled.candidate, limits=self.peer.limits, client=self.peer.client)
            replayed = sdk.replay(self.peer.request, candidate=compiled.candidate, limits=self.peer.limits,
                                  report=checked.result, client=self.peer.client)
        self.assertEqual(compiled.result, replayed.result)
        self.assertEqual(self.peer.calls[-1]["payload"]["report"], checked.result)

    def test_deterministic_archive_carries_exact_fresh_native_pair(self):
        with tempfile.TemporaryDirectory() as directory, self.peer.exchange():
            first, second = (Path(directory) / name for name in ("one.zip", "two.zip"))
            exported = self.export(first)
            self.export(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), ["program.fasta", "manifest.json"])
                self.assertEqual(archive.read("program.fasta"), exported.artifact["fasta"].encode())
                self.assertEqual(archive.read("manifest.json"), encode_json(exported.artifact["manifest"]))
                for item in archive.infolist():
                    self.assertEqual(item.compress_type, zipfile.ZIP_STORED)
                    self.assertEqual(item.date_time, (1980, 1, 1, 0, 0, 0))
            self.assertEqual([row["operation"] for row in self.peer.calls], ["capabilities", "export-policy-material"] * 2)
            self.assertFalse(list(Path(directory).glob(".policy-material-*")))

    def test_publication_requires_explicit_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.zip"
            output.write_bytes(b"original")
            with patch.object(type(self.peer.client), "export", side_effect=AssertionError("Fail before native")), self.assertRaises(FileExistsError):
                self.export(output)
            self.assertEqual(output.read_bytes(), b"original")
            with self.peer.exchange():
                self.export(output, replace=True)
            self.assertTrue(zipfile.is_zipfile(output))

    def test_input_aliases_symlinks_and_hardlinks_are_rejected_before_native(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "request.zip"
            source.write_bytes(b"original")
            link, hard = root / "link.zip", root / "hard.zip"
            link.symlink_to(source)
            os.link(source, hard)
            for destination in (source, link, hard, root / "sub" / ".." / "request.zip"):
                with self.subTest(destination=destination), patch.object(type(self.peer.client), "export", side_effect=AssertionError("No export")), self.assertRaises(ValueError):
                    self.export(destination, input_paths=[source], replace=True)
            self.assertEqual(source.read_bytes(), b"original")
            with patch.object(type(self.peer.client), "export", side_effect=AssertionError("No export")), self.assertRaises(ValueError):
                self.export(root / "not-a-pair.fasta")

    def test_failed_check_and_incomplete_pair_preserve_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.zip"
            output.write_bytes(b"original")
            for options, exception in (({"failure": CoreTransportError("crash")}, CoreTransportError),
                                       ({"mutate": lambda v: v.update(artifact=None)}, CoreProtocolError),
                                       ({"status": "not_accepted"}, CoreProtocolError)):
                with self.subTest(options=options), self.peer.exchange(**options), self.assertRaises(exception):
                    self.export(output, replace=True)
                self.assertEqual(output.read_bytes(), b"original")
                self.assertFalse(list(Path(directory).glob(".policy-material-*")))

    def test_write_fsync_and_replace_failures_preserve_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.zip"
            output.write_bytes(b"original")
            for target in ("biocompiler.policy.material.zipfile.ZipFile.writestr", "biocompiler.policy.material.os.fsync", "biocompiler.policy.material.os.replace"):
                with self.subTest(target=target), self.peer.exchange(), patch(target, side_effect=OSError("disk failure")), self.assertRaises(OSError):
                    self.export(output, replace=True)
                self.assertEqual(output.read_bytes(), b"original")
                self.assertFalse(list(Path(directory).glob(".policy-material-*")))

    def test_corrupt_or_short_staged_bytes_fail_before_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.zip"
            output.write_bytes(b"original")
            original_fsync = os.fsync
            for mode in ("truncate", "corrupt"):
                def corrupt_after_flush(fd):
                    original_fsync(fd)
                    if mode == "truncate":
                        os.ftruncate(fd, os.fstat(fd).st_size - 1)
                    else:
                        # A byte in program.fasta, after its fixed local header.
                        os.lseek(fd, 30 + len("program.fasta"), os.SEEK_SET)
                        os.write(fd, b"!")
                with self.subTest(mode=mode), self.peer.exchange(), patch("biocompiler.policy.material.os.fsync", side_effect=corrupt_after_flush), self.assertRaises(CoreProtocolError):
                    self.export(output, replace=True)
                self.assertEqual(output.read_bytes(), b"original")
                self.assertFalse(list(Path(directory).glob(".policy-material-*")))

    def test_local_header_metadata_corruption_preserves_prior_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.zip"
            output.write_bytes(b"original")
            original_fsync = os.fsync
            for field, member, offset in (("timestamp", 0, 10), ("version", 1, 4), ("crc", 0, 14)):
                def changed_header(fd):
                    original_fsync(fd)
                    os.lseek(fd, 0, os.SEEK_SET)
                    raw = os.read(fd, os.fstat(fd).st_size)
                    start = 0 if member == 0 else raw.index(b"PK\x03\x04", 1)
                    os.lseek(fd, start + offset, os.SEEK_SET)
                    os.write(fd, bytes([raw[start + offset] ^ 1]))
                with self.subTest(field=field), self.peer.exchange(), patch("biocompiler.policy.material.os.fsync", side_effect=changed_header), self.assertRaises(CoreProtocolError):
                    self.export(output, replace=True)
                self.assertEqual(output.read_bytes(), b"original")
                self.assertFalse(list(Path(directory).glob(".policy-material-*")))

    def test_valid_zip_with_changed_member_bytes_or_metadata_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "result.zip"
            output.write_bytes(b"original")
            original_write = zipfile.ZipFile.writestr
            for mode in ("bytes", "metadata"):
                def changed_write(archive, info, data):
                    if info.filename == "program.fasta":
                        if mode == "bytes":
                            data = b"!" + data[1:]
                        else:
                            info.external_attr = 0o100600 << 16
                    return original_write(archive, info, data)
                with self.subTest(mode=mode), self.peer.exchange(), patch("biocompiler.policy.material.zipfile.ZipFile.writestr", new=changed_write), self.assertRaises(CoreProtocolError):
                    self.export(output, replace=True)
                self.assertEqual(output.read_bytes(), b"original")
                self.assertFalse(list(Path(directory).glob(".policy-material-*")))

    def test_exclusive_publication_race_never_overwrites_other_writer(self):
        with tempfile.TemporaryDirectory() as directory, self.peer.exchange():
            output = Path(directory) / "result.zip"
            original_link = os.link
            def racing_link(source, destination):
                Path(destination).write_bytes(b"other-writer")
                return original_link(source, destination)
            with patch("biocompiler.policy.material.os.link", side_effect=racing_link), self.assertRaises(FileExistsError):
                self.export(output)
            self.assertEqual(output.read_bytes(), b"other-writer")
            self.assertFalse(list(Path(directory).glob(".policy-material-*")))

    def test_path_replacement_during_native_check_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "request.json", root / "result.zip"
            source.write_bytes(b"original")
            def replace_path(value):
                output.symlink_to(source)
            with self.peer.exchange(mutate=replace_path), self.assertRaises(ValueError):
                self.export(output, input_paths=[source], replace=True)
            self.assertEqual(source.read_bytes(), b"original")
            self.assertTrue(output.is_symlink())

    def test_cancellation_before_atomic_publication_preserves_existing_output(self):
        with tempfile.TemporaryDirectory() as directory, self.peer.exchange():
            output = Path(directory) / "result.zip"
            output.write_bytes(b"original")
            with self.assertRaises(CoreCancelled):
                self.export(output, replace=True, cancelled=lambda: True)
            self.assertEqual(output.read_bytes(), b"original")
            self.assertFalse(list(Path(directory).glob(".policy-material-*")))


class PolicyMaterialIsolationTests(unittest.TestCase):
    def test_outer_cleanup_restores_manually_owned_peer_patches(self):
        prior_assessment = peer.peer.assessment
        prior_source_assessment = peer.peer.source_peer.source_assessment
        outer = PolicyMaterialSdkTests("test_complete_request_snapshot_preserves_external_authority")
        self.addCleanup(outer.doCleanups)
        outer.setUp()
        self.assertIsNot(peer.peer.assessment, prior_assessment)
        self.assertIsNot(peer.peer.source_peer.source_assessment, prior_source_assessment)
        outer.doCleanups()
        self.assertIs(peer.peer.assessment, prior_assessment)
        self.assertIs(peer.peer.source_peer.source_assessment, prior_source_assessment)


if __name__ == "__main__":
    unittest.main()
