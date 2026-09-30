"""Independent import audit for rehashed reference-package payloads."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from biocompiler.artifacts.archive import assemble_archive, read_archive
from biocompiler.artifacts.manifest import PackageFile
from biocompiler.compiler.reference import (
    build_reference_package,
    prepare_reference_build,
    verify_reference_package,
)
from biocompiler.errors import SerializationError
from biocompiler.registry.reference_builds import MANIFEST_PIN


REFERENCE = Path(__file__).resolve().parents[1] / "data/references/fap_car"


class ReferencePackageAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = prepare_reference_build("DNA", REFERENCE)
        cls.package = build_reference_package(cls.request, REFERENCE)

    def rehash(self, path, data):
        manifest, original, metadata = read_archive(self.package.data)
        files = dict(original)
        files[path] = data
        entries = []
        for item in manifest.files:
            content = files[item.path]
            entries.append(
                replace(
                    item,
                    sha256=hashlib.sha256(content).hexdigest(),
                    byte_length=len(content),
                )
            )
        if path not in original:
            entries.append(
                PackageFile(
                    path, "reference-input", hashlib.sha256(data).hexdigest(), len(data)
                )
            )
        return assemble_archive(
            replace(manifest, files=tuple(entries)), files, metadata
        )

    def test_retained_source_and_review_tampering_survives_inventory_but_not_recheck(
        self,
    ):
        _, files, _ = read_archive(self.package.data)
        prefix = f"references/{MANIFEST_PIN.id}/"
        for name in ("source-excerpts.html", "independent-audit.json"):
            path = prefix + name
            data = self.rehash(path, files[path] + b"\nchanged evidence")
            # Declared archive byte hashes are correct: semantic source pins
            # must independently reject the substituted evidence.
            read_archive(data)
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(SerializationError, "hash mismatch"),
            ):
                verify_reference_package(data, expected_request=self.request)

    def test_reference_manifest_cannot_choose_its_own_new_trust_pin(self):
        _, files, _ = read_archive(self.package.data)
        path = f"references/{MANIFEST_PIN.id}/manifest.json"
        reference = json.loads(files[path])
        reference["redistribution"]["note"] += " alternate unreviewed snapshot"
        altered = self.rehash(path, json.dumps(reference).encode("utf-8"))
        read_archive(altered)
        with self.assertRaisesRegex(SerializationError, "reviewed pin"):
            verify_reference_package(altered, expected_request=self.request)

    def test_non_utf8_and_unknown_request_fields_are_strict_import_errors(self):
        _, files, _ = read_archive(self.package.data)
        unknown = json.loads(files["request.json"])
        unknown["accepted"] = True
        for content in (b"\xff", json.dumps(unknown).encode("utf-8")):
            altered = self.rehash("request.json", content)
            read_archive(altered)
            with (
                self.subTest(content=content[:12]),
                self.assertRaises(SerializationError),
            ):
                verify_reference_package(altered, expected_request=self.request)

    def test_extra_authoring_payload_never_executes_and_cannot_enter_accepted_package(
        self,
    ):
        path = f"references/{MANIFEST_PIN.id}/author.py"
        data = self.rehash(
            path, b"raise AssertionError('untrusted package code executed')\n"
        )
        read_archive(data)
        with (
            patch("runpy.run_path", side_effect=AssertionError("authoring prohibited")),
            patch(
                "socket.create_connection",
                side_effect=AssertionError("network prohibited"),
            ),
        ):
            verified = verify_reference_package(
                self.package.data, expected_request=self.request
            )
            self.assertEqual(verified.data, self.package.data)
            with self.assertRaisesRegex(
                SerializationError, "stale|altered|unsupported"
            ):
                verify_reference_package(data, expected_request=self.request)


if __name__ == "__main__":
    unittest.main()
