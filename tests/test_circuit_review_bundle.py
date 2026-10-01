"""Portable review software contracts over explicitly artificial records."""

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.artifacts.archive import read_archive
from biocompiler.artifacts.circuit_review import (
    CircuitReviewAuthority,
    CircuitReviewManifest,
)
from biocompiler.artifacts.circuit_review_bundle import (
    CircuitReviewBundle,
    create_circuit_review_bundle,
    publish_circuit_review_bundle,
)
from biocompiler.artifacts.manifest import RunMetadata
from biocompiler.compiler.circuit_construction import build_circuit_construction
from biocompiler.errors import SerializationError
from biocompiler.verification.circuit_bindings import check_circuit_bindings
from biocompiler.verification.circuit_construction import check_circuit_construction
from biocompiler.verification.circuit_evidence import (
    capture_circuit_evidence,
    check_circuit_evidence,
)
from biocompiler.verification.circuit_review import (
    inspect_circuit_review_bundle,
    verify_circuit_review_bundle,
)
from biocompiler.verification.circuit_sources import check_circuit_sources
from examples.circuit_infrastructure import make_infrastructure_requests
from examples.circuit_sources import make_source_inventory


class CircuitReviewBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        construction, cls.bindings, cls.evidence = make_infrastructure_requests()
        cls.build = build_circuit_construction(construction)
        cls.authority = CircuitReviewAuthority(construction)
        cls.bundle = create_circuit_review_bundle(
            cls.build, expected_authority=cls.authority
        )
        cls.inventory = make_source_inventory()
        cls.source_assessment = check_circuit_sources(cls.inventory)
        cls.binding_assessment = check_circuit_bindings(
            cls.build.candidate, expected_request=cls.bindings
        )
        cls.receipt = capture_circuit_evidence(cls.build, expected_request=cls.evidence)
        cls.evidence_assessment = check_circuit_evidence(
            cls.receipt, cls.build, expected_request=cls.evidence
        )
        cls.full_authority = replace(
            cls.authority,
            sources=cls.inventory,
            bindings=cls.bindings,
            evidence=cls.evidence,
            evidence_receipt_fingerprint=cls.receipt.fingerprint,
        )

    def full_bundle(self, **changes):
        return create_circuit_review_bundle(
            self.build,
            expected_authority=self.full_authority,
            source_assessment=self.source_assessment,
            binding_assessment=self.binding_assessment,
            evidence_receipt=self.receipt,
            evidence_assessment=self.evidence_assessment,
            **changes,
        )

    def test_canonical_reproduction_and_three_acceptance_tracks(self):
        repeated = create_circuit_review_bundle(
            self.build, expected_authority=self.authority
        )
        self.assertEqual(repeated, self.bundle)
        inspected = inspect_circuit_review_bundle(self.bundle.data)
        self.assertEqual(inspected["verification"], "historical_unverified")
        fresh = verify_circuit_review_bundle(
            self.bundle.data, expected_authority=self.authority
        )
        self.assertEqual(fresh["verification"], "fresh_independent_replay")
        self.assertEqual(fresh["software_implementation"]["construction"], "pass")
        for key in ("sources", "bindings", "evidence"):
            self.assertEqual(fresh["software_implementation"][key], "missing")
        self.assertEqual(fresh["reviewed_reference_correspondence"], "not_established")
        self.assertEqual(fresh["human_biological_applicability"], "unassessed")
        self.assertEqual(fresh["human_therapeutic_admission"], "not_admitted")

    def test_every_retained_typed_field_survives_portable_archive(self):
        bundle = self.full_bundle()
        manifest, files, metadata = read_archive(bundle.data)
        self.assertEqual(manifest, bundle.manifest)
        self.assertEqual(len(files), 9)
        self.assertIsNone(metadata)
        for path, record in (
            ("request.json", self.authority.construction),
            ("construction.json", self.build),
            ("sources/inventory.json", self.inventory),
            ("checks/sources.json", self.source_assessment),
            ("bindings/request.json", self.bindings),
            ("checks/bindings.json", self.binding_assessment),
            ("evidence/request.json", self.evidence),
            ("evidence/receipt.json", self.receipt),
            ("checks/evidence.json", self.evidence_assessment),
        ):
            self.assertEqual(files[path], (record.to_json() + "\n").encode())
        verified = verify_circuit_review_bundle(
            bundle.data, expected_authority=self.full_authority
        )
        self.assertEqual(verified["software_implementation"]["evidence"], "current")
        self.assertEqual(
            verified["source_metadata_construction_correspondence"], "not_established"
        )

    def test_run_metadata_changes_outer_bytes_without_identity_or_core_changes(self):
        first = self.full_bundle(
            run_metadata=RunMetadata(
                "2026-09-30T01:00:00Z",
                "linux",
                {"design/request.py": "/tmp/one/request.py"},
            )
        )
        second = self.full_bundle(
            run_metadata=RunMetadata(
                "2026-09-30T02:00:00Z",
                "windows",
                {"design/request.py": "C:\\two\\request.py"},
            )
        )
        self.assertNotEqual(first.data, second.data)
        self.assertEqual(
            first.manifest.build_fingerprint, second.manifest.build_fingerprint
        )
        self.assertEqual(read_archive(first.data)[1], read_archive(second.data)[1])
        for bundle in (first, second):
            verify_circuit_review_bundle(
                bundle.data, expected_authority=self.full_authority
            )

    def test_separately_retained_authority_json_is_strict_and_complete(self):
        restored = CircuitReviewAuthority.from_json(self.full_authority.to_json())
        self.assertEqual(restored, self.full_authority)
        for key in self.full_authority.to_dict():
            data = self.full_authority.to_dict()
            del data[key]
            with self.subTest(missing=key), self.assertRaises(SerializationError):
                CircuitReviewAuthority.from_dict(data)
        with self.assertRaises(SerializationError):
            CircuitReviewAuthority.from_json(
                '{"construction":null,"construction":null}'
            )
        with patch("biocompiler.artifacts.circuit_review.MAX_AUTHORITY_BYTES", 20):
            with self.assertRaises(SerializationError):
                self.full_authority.to_json()
            with self.assertRaises(SerializationError):
                CircuitReviewAuthority.from_json(" " * 21)

    def test_optional_assessments_and_authorities_are_all_or_none(self):
        for kwargs in (
            {"source_assessment": self.source_assessment},
            {"binding_assessment": self.binding_assessment},
            {"evidence_receipt": self.receipt},
            {"evidence_assessment": self.evidence_assessment},
        ):
            with (
                self.subTest(extra=tuple(kwargs)),
                self.assertRaises(SerializationError),
            ):
                create_circuit_review_bundle(
                    self.build, expected_authority=self.authority, **kwargs
                )
        with self.assertRaises(SerializationError):
            create_circuit_review_bundle(
                self.build, expected_authority=self.full_authority
            )
        with self.assertRaises(SerializationError):
            replace(self.authority, evidence=self.evidence)
        with self.assertRaises(SerializationError):
            replace(
                self.authority, evidence_receipt_fingerprint=self.receipt.fingerprint
            )

    def test_cross_cohort_construction_edits_are_rejected(self):
        changed = replace(self.authority.construction, id="changed-original-authority")
        for key, value in (
            ("bindings", replace(self.bindings, construction=changed)),
            ("evidence", replace(self.evidence, construction=changed)),
        ):
            with self.subTest(key=key), self.assertRaises(SerializationError):
                replace(self.full_authority, **{key: value})

    def test_honest_binding_failure_is_retained_without_promotion(self):
        bindings = replace(self.bindings, bindings=())
        assessment = check_circuit_bindings(
            self.build.candidate, expected_request=bindings
        )
        self.assertFalse(assessment.passed)
        authority = replace(self.authority, bindings=bindings)
        bundle = create_circuit_review_bundle(
            self.build, expected_authority=authority, binding_assessment=assessment
        )
        result = verify_circuit_review_bundle(bundle.data, expected_authority=authority)
        self.assertEqual(result["software_implementation"]["bindings"], "fail")
        self.assertEqual(result["verification"], "fresh_independent_replay")

    def test_honest_failed_construction_is_preserved_for_review(self):
        original = self.build.candidate.values[0]
        candidate = replace(
            self.build.candidate,
            values=(
                replace(original, sequence="CCCCCC"),
                *self.build.candidate.values[1:],
            ),
        )
        assessment = check_circuit_construction(
            candidate, expected_request=self.authority.construction
        )
        self.assertFalse(assessment.passed)
        build = replace(self.build, candidate=candidate, assessment=assessment)
        bundle = create_circuit_review_bundle(build, expected_authority=self.authority)
        result = verify_circuit_review_bundle(
            bundle.data, expected_authority=self.authority
        )
        self.assertEqual(result["software_implementation"]["construction"], "fail")
        self.assertFalse(result["software_implementation"]["construction_complete"])

    def test_stale_evidence_snapshot_is_retained_with_external_history_pin(self):
        receipt = replace(
            self.receipt,
            sources=(replace(self.receipt.sources[0], source_fingerprint="f" * 64),),
        )
        assessment = check_circuit_evidence(
            receipt, self.build, expected_request=self.evidence
        )
        authority = replace(
            self.authority,
            evidence=self.evidence,
            evidence_receipt_fingerprint=receipt.fingerprint,
        )
        bundle = create_circuit_review_bundle(
            self.build,
            expected_authority=authority,
            evidence_receipt=receipt,
            evidence_assessment=assessment,
        )
        result = verify_circuit_review_bundle(bundle.data, expected_authority=authority)
        self.assertEqual(result["software_implementation"]["evidence"], "stale")
        self.assertEqual(result["software_implementation"]["prediction"], "unsupported")

    def test_manifest_versions_and_claim_scope_are_closed(self):
        for changes in (
            {"human_therapeutic_admission": "admitted"},
            {"status": "complete"},
            {"profile": "reference_cds"},
            {"reviewed_reference_correspondence": "pass"},
            {"family_semantics": "implemented"},
        ):
            with self.subTest(changes=changes), self.assertRaises(SerializationError):
                replace(self.bundle.manifest, **changes)
        document = self.bundle.manifest.to_dict()
        document["schema_version"] = "biocompiler.circuit_review_manifest.v0.0"
        with self.assertRaises(SerializationError):
            CircuitReviewManifest.from_dict(document)

    def test_publication_is_atomic_relocatable_and_replayed_before_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            one = root / "one.bcb"
            two = root / "relocated" / "two.bcb"
            two.parent.mkdir()
            for path in (one, two):
                publish_circuit_review_bundle(
                    self.bundle, path, expected_authority=self.authority
                )
                verify_circuit_review_bundle(
                    path.read_bytes(), expected_authority=self.authority
                )
            self.assertEqual(one.read_bytes(), two.read_bytes())
            with patch(
                "biocompiler.artifacts.archive_container.os.replace",
                side_effect=OSError("interrupted"),
            ):
                with self.assertRaises(OSError):
                    publish_circuit_review_bundle(
                        self.bundle, one, expected_authority=self.authority
                    )
            self.assertEqual(one.read_bytes(), self.bundle.data)
            self.assertEqual(
                sorted(path.name for path in root.iterdir()), ["one.bcb", "relocated"]
            )
            wrong = replace(
                self.authority,
                construction=replace(self.authority.construction, id="different"),
            )
            with patch(
                "biocompiler.artifacts.archive_container.tempfile.mkstemp",
                side_effect=AssertionError("must not start publication"),
            ):
                with self.assertRaises(SerializationError):
                    publish_circuit_review_bundle(
                        self.bundle, one, expected_authority=wrong
                    )
            mismatch = CircuitReviewBundle(
                self.bundle.data, replace(self.bundle.manifest, package_version="other")
            )
            with self.assertRaises(SerializationError):
                publish_circuit_review_bundle(
                    mismatch, one, expected_authority=self.authority
                )
