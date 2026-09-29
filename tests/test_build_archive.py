"""Reference containers preserve bytes without trusting archived success labels."""

from dataclasses import replace
import hashlib
import io
import os
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from cellweave.artifacts.archive import (
    MAX_ENTRIES,
    MAX_MEMBER_BYTES,
    assemble_archive,
    read_archive,
    write_archive_atomic,
)
from cellweave.artifacts.manifest import (
    REQUIRED_FILES,
    AcceptedStage,
    BuildManifest,
    PackageFile,
    RunMetadata,
    ToolPin,
)
from cellweave.errors import SerializationError


def archive_fixture():
    # These are intentionally arbitrary bytes behind structurally valid archived
    # claims. Archive inspection must never be mistaken for pipeline acceptance.
    files = {path: ("opaque:" + path).encode("utf-8") for path in REQUIRED_FILES}
    files["references/example/manifest.json"] = b"{}\n"
    inventory = tuple(
        PackageFile(
            path,
            REQUIRED_FILES.get(path, "reference-input"),
            hashlib.sha256(payload).hexdigest(),
            len(payload),
        )
        for path, payload in files.items()
    )
    stages = tuple(
        AcceptedStage(stage, "1" * 64, "2" * 64, schema)
        for stage, schema in (
            ("components", "cellweave.construct_request.v0.1"),
            ("construct", "cellweave.construct.v0.1"),
            ("molecular", "cellweave.molecular.v0.1"),
        )
    )
    manifest = BuildManifest(
        "0" * 64, inventory, stages, (ToolPin("fixture", "1", "3" * 64),), "test"
    )
    return manifest, files


def zip_entries(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return [(item.filename, archive.read(item)) for item in archive.infolist()]


def unchecked_zip(
    entries,
    *,
    compression=zipfile.ZIP_STORED,
    mode=stat.S_IFREG | 0o644,
    timestamp=(1980, 1, 1, 0, 0, 0),
    comment=b"",
    extra=b"",
):
    """Construct adversarial containers independently of archive policy code."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=compression) as archive:
        archive.comment = comment
        for path, payload in entries:
            info = zipfile.ZipInfo(path, timestamp)
            info.create_system = 3
            info.external_attr = mode << 16
            info.compress_type = compression
            info.extra = extra
            archive.writestr(info, payload)
    return buffer.getvalue()


class BuildArchiveTests(unittest.TestCase):
    def test_sorted_fixed_metadata_roundtrip_is_deterministic_and_immutable(self):
        manifest, files = archive_fixture()
        encoded = assemble_archive(manifest, files)
        reverse = dict(reversed(tuple(files.items())))
        self.assertEqual(encoded, assemble_archive(manifest, reverse))
        imported, payloads, metadata = read_archive(encoded)
        self.assertEqual(imported, manifest)
        self.assertEqual(dict(payloads), files)
        self.assertIsNone(metadata)
        with self.assertRaises(TypeError):
            payloads["request.json"] = b"changed"
        with zipfile.ZipFile(io.BytesIO(encoded)) as archive:
            self.assertEqual(archive.namelist(), sorted([*files, "manifest.json"]))
            for item in archive.infolist():
                self.assertEqual(item.compress_type, zipfile.ZIP_STORED)
                self.assertEqual(item.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(item.external_attr >> 16, stat.S_IFREG | 0o644)
                self.assertFalse(item.extra or item.comment or item.is_dir())
            self.assertEqual(
                archive.read("manifest.json"),
                (manifest.to_json(indent=2) + "\n").encode("utf-8"),
            )

    def test_optional_run_metadata_changes_archive_bytes_but_not_build_identity(self):
        manifest, files = archive_fixture()
        first = RunMetadata(
            "2026-09-29T20:00:00Z", "machine-a", {"build.py": "/workspace/a/build.py"}
        )
        second = RunMetadata(
            "2026-09-30T20:00:00Z", "machine-b", {"build.py": "/relocated/build.py"}
        )
        no_metadata = assemble_archive(manifest, files)
        first_archive = assemble_archive(manifest, files, first)
        second_archive = assemble_archive(manifest, files, second)
        self.assertEqual(len({no_metadata, first_archive, second_archive}), 3)
        self.assertEqual(first_archive, assemble_archive(manifest, files, first))
        for encoded, expected in (
            (no_metadata, None),
            (first_archive, first),
            (second_archive, second),
        ):
            imported, _, metadata = read_archive(encoded)
            self.assertEqual(imported.build_fingerprint, manifest.build_fingerprint)
            self.assertEqual(metadata, expected)

    def test_assembler_rejects_missing_extra_changed_and_mutable_payloads(self):
        manifest, files = archive_fixture()
        for changed in (
            {key: value for key, value in files.items() if key != "request.json"},
            {**files, "unexpected.json": b"extra"},
            {**files, "request.json": b"changed"},
            {**files, "request.json": bytearray(files["request.json"])},
            {**files, "manifest.json": b"{}"},
            {**files, "run.json": b"{}"},
        ):
            with (
                self.subTest(paths=tuple(changed)),
                self.assertRaises(SerializationError),
            ):
                assemble_archive(manifest, changed)

    def test_import_rejects_declared_inventory_content_size_and_hash_mismatches(self):
        manifest, files = archive_fixture()
        entries = zip_entries(assemble_archive(manifest, files))
        for changed in (
            [(name, payload) for name, payload in entries if name != "request.json"],
            entries + [("unexpected.json", b"extra")],
            [
                (name, b"changed" if name == "request.json" else payload)
                for name, payload in entries
            ],
        ):
            with (
                self.subTest(names=[name for name, _ in changed]),
                self.assertRaises(SerializationError),
            ):
                read_archive(unchecked_zip(changed))
        for key, value in (("byte_length", 999), ("sha256", "f" * 64)):
            declared = replace(manifest.files[0], **{key: value})
            modified = replace(manifest, files=(declared, *manifest.files[1:]))
            changed = [
                (
                    name,
                    (modified.to_json(indent=2) + "\n").encode()
                    if name == "manifest.json"
                    else payload,
                )
                for name, payload in entries
            ]
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(SerializationError, "mismatch"),
            ):
                read_archive(unchecked_zip(changed))

    def test_traversal_absolute_backslash_empty_and_directory_names_are_rejected(self):
        manifest, files = archive_fixture()
        entries = zip_entries(assemble_archive(manifest, files))
        for path in (
            "../escape",
            "/absolute",
            "folder/../escape",
            "folder//file",
            "folder\\file",
            "C:/drive",
            "folder/./file",
            "folder/",
            "bad\nname",
        ):
            with self.subTest(path=path), self.assertRaises(SerializationError):
                read_archive(unchecked_zip([*entries, (path, b"untrusted")]))

    def test_duplicate_and_nul_truncated_names_are_rejected(self):
        manifest, files = archive_fixture()
        encoded = assemble_archive(manifest, files)
        entries = zip_entries(encoded)
        with self.assertWarns(UserWarning):
            duplicate = unchecked_zip([*entries, entries[0]])
        with self.assertRaisesRegex(SerializationError, "Duplicate"):
            read_archive(duplicate)
        with self.assertRaises(SerializationError):
            read_archive(encoded.replace(b"request.json", b"request\x00json"))

    def test_symlinks_executable_modes_and_noncanonical_container_metadata_fail(self):
        manifest, files = archive_fixture()
        entries = zip_entries(assemble_archive(manifest, files))
        for options in (
            {"mode": stat.S_IFLNK | 0o777},
            {"mode": stat.S_IFREG | 0o755},
            {"compression": zipfile.ZIP_DEFLATED},
            {"timestamp": (2000, 1, 1, 0, 0, 0)},
            {"comment": b"not canonical"},
            {"extra": b"\x01\x00\x00\x00"},
        ):
            with self.subTest(options=options), self.assertRaises(SerializationError):
                read_archive(unchecked_zip(entries, **options))

    def test_trailing_prefix_truncated_and_reordered_container_bytes_are_rejected(self):
        manifest, files = archive_fixture()
        encoded = assemble_archive(manifest, files)
        for changed in (
            encoded + b"trailing",
            b"prefix" + encoded,
            encoded[:-1],
            unchecked_zip(list(reversed(zip_entries(encoded)))),
        ):
            with (
                self.subTest(length=len(changed)),
                self.assertRaises(SerializationError),
            ):
                read_archive(changed)

    def test_noncanonical_metadata_json_cannot_masquerade_as_canonical_archive_bytes(
        self,
    ):
        manifest, files = archive_fixture()
        entries = zip_entries(assemble_archive(manifest, files))
        for content in (
            manifest.to_json(indent=None).encode(),
            manifest.to_json(indent=2).encode(),
            b"\xffinvalid",
        ):
            modified = [
                (name, content if name == "manifest.json" else payload)
                for name, payload in entries
            ]
            with (
                self.subTest(length=len(content)),
                self.assertRaises(SerializationError),
            ):
                read_archive(unchecked_zip(modified))

    def test_corrupt_crc_is_rejected_instead_of_returning_partial_files(self):
        manifest, files = archive_fixture()
        encoded = assemble_archive(manifest, files)
        corrupted = encoded.replace(b"opaque:request.json", b"tamper:request.json")
        self.assertEqual(len(corrupted), len(encoded))
        with self.assertRaises(SerializationError):
            read_archive(corrupted)

    def test_declared_zip_bomb_size_is_rejected_before_payload_reads(self):
        manifest, files = archive_fixture()
        encoded = bytearray(assemble_archive(manifest, files))
        first_directory = encoded.index(b"PK\x01\x02")
        struct.pack_into(
            "<II",
            encoded,
            first_directory + 20,
            MAX_MEMBER_BYTES + 1,
            MAX_MEMBER_BYTES + 1,
        )
        with patch(
            "cellweave.artifacts.archive.zipfile.ZipFile.read",
            side_effect=AssertionError("payload read before bound"),
        ):
            with self.assertRaisesRegex(SerializationError, "size limit"):
                read_archive(bytes(encoded))

    def test_unsupported_zip_reader_versions_report_a_serialization_error(self):
        manifest, files = archive_fixture()
        encoded = bytearray(assemble_archive(manifest, files))
        first_directory = encoded.index(b"PK\x01\x02")
        struct.pack_into("<H", encoded, first_directory + 6, 99)
        with self.assertRaises(SerializationError):
            read_archive(bytes(encoded))

    def test_lying_or_excessive_directory_counts_fail_before_zipfile_allocation(self):
        manifest, files = archive_fixture()
        encoded = assemble_archive(manifest, files)
        for count in (1, MAX_ENTRIES + 1):
            changed = bytearray(encoded)
            struct.pack_into("<HH", changed, len(changed) - 22 + 8, count, count)
            with patch(
                "cellweave.artifacts.archive.zipfile.ZipFile",
                side_effect=AssertionError("ZipFile opened before count validation"),
            ):
                with self.subTest(count=count), self.assertRaises(SerializationError):
                    read_archive(bytes(changed))

    def test_member_archive_metadata_and_path_limits_are_bounded(self):
        manifest, files = archive_fixture()
        encoded = assemble_archive(manifest, files)
        with patch("cellweave.artifacts.archive.MAX_ARCHIVE_BYTES", len(encoded) - 1):
            with self.assertRaises(SerializationError):
                read_archive(encoded)
        with patch("cellweave.artifacts.archive.MAX_METADATA_BYTES", 1):
            with self.assertRaises(SerializationError):
                assemble_archive(manifest, files)
        with patch("cellweave.artifacts.archive.MAX_MEMBER_BYTES", 1):
            with self.assertRaises(SerializationError):
                assemble_archive(manifest, files)
        with patch("cellweave.artifacts.archive.MAX_ENTRIES", 1):
            with self.assertRaises(SerializationError):
                assemble_archive(manifest, files)
        with self.assertRaises(SerializationError):
            read_archive(unchecked_zip([*zip_entries(encoded), ("x" * 1025, b"")]))


class ArchivePublicationTests(unittest.TestCase):
    def setUp(self):
        manifest, files = archive_fixture()
        self.original = assemble_archive(manifest, files)
        self.updated = assemble_archive(
            replace(manifest, package_version="updated"), files
        )

    def test_atomic_creation_and_replacement_publish_only_complete_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.cwb"
            self.assertEqual(write_archive_atomic(path, self.original), path)
            self.assertEqual(path.read_bytes(), self.original)
            self.assertEqual(write_archive_atomic(path, self.updated), path)
            self.assertEqual(path.read_bytes(), self.updated)
            self.assertEqual(
                read_archive(path.read_bytes())[0].package_version, "updated"
            )
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_failed_validation_preserves_existing_archive_without_creating_temporary_files(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.cwb"
            path.write_bytes(self.original)
            with patch("cellweave.artifacts.archive.tempfile.mkstemp") as temporary:
                with self.assertRaises(SerializationError):
                    write_archive_atomic(path, self.updated + b"invalid")
                temporary.assert_not_called()
            self.assertEqual(path.read_bytes(), self.original)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_write_sync_replace_and_interrupt_failures_preserve_existing_archive(self):
        for operation, error in (
            ("os.fdopen", OSError("write failed")),
            ("os.fsync", OSError("sync failed")),
            ("os.replace", OSError("replace failed")),
            ("os.fsync", KeyboardInterrupt()),
        ):
            with (
                self.subTest(operation=operation, error=type(error).__name__),
                tempfile.TemporaryDirectory() as directory,
            ):
                path = Path(directory) / "reference.cwb"
                path.write_bytes(self.original)
                with patch(
                    "cellweave.artifacts.archive." + operation, side_effect=error
                ):
                    with self.assertRaises(type(error)):
                        write_archive_atomic(path, self.updated)
                self.assertEqual(path.read_bytes(), self.original)
                self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_partial_write_cannot_replace_previous_archive(self):
        fdopen = os.fdopen

        class PartialWriter:
            def __init__(self, descriptor, mode):
                self.output = fdopen(descriptor, mode)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return self.output.__exit__(*args)

            def write(self, data):
                return self.output.write(data[: len(data) // 2])

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.cwb"
            path.write_bytes(self.original)
            with patch("cellweave.artifacts.archive.os.fdopen", PartialWriter):
                with self.assertRaisesRegex(OSError, "Incomplete"):
                    write_archive_atomic(path, self.updated)
            self.assertEqual(path.read_bytes(), self.original)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_failed_initial_publication_leaves_no_success_artifact_or_temporary_file(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.cwb"
            with patch(
                "cellweave.artifacts.archive.os.replace", side_effect=OSError("failed")
            ):
                with self.assertRaises(OSError):
                    write_archive_atomic(path, self.original)
            self.assertFalse(path.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_publication_refuses_symlinks_directories_and_wrong_extensions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "accepted.cwb"
            target.write_bytes(self.original)
            symlink = root / "linked.cwb"
            symlink.symlink_to(target)
            folder = root / "folder.cwb"
            folder.mkdir()
            for path in (
                symlink,
                folder,
                root / "wrong.zip",
                root / "missing/parent.cwb",
            ):
                with self.subTest(path=path), self.assertRaises(SerializationError):
                    write_archive_atomic(path, self.updated)
            self.assertEqual(target.read_bytes(), self.original)
            self.assertTrue(symlink.is_symlink())
            self.assertTrue(folder.is_dir())


if __name__ == "__main__":
    unittest.main()
