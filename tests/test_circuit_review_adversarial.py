"""Adversarial software archives do not become independent biological authority."""

from contextlib import ExitStack
from dataclasses import replace
import hashlib
import json
import unittest
from unittest.mock import patch

from biocompiler.artifacts.circuit_construction_build import CircuitConstructionBuild
from biocompiler.artifacts.circuit_review import CircuitReviewAuthority
from biocompiler.artifacts.circuit_review_bundle import create_circuit_review_bundle
from biocompiler.compiler.circuit_construction import build_circuit_construction
from biocompiler.errors import SerializationError
from biocompiler.verification.circuit_bindings import (
    CircuitBindingAssessment,
    check_circuit_bindings,
)
from biocompiler.verification.circuit_evidence import (
    CircuitEvidenceAssessment,
    capture_circuit_evidence,
    check_circuit_evidence,
)
from biocompiler.verification.circuit_review import (
    inspect_circuit_review_bundle,
    verify_circuit_review_bundle,
)
from biocompiler.verification.circuit_sources import (
    CircuitSourcesAssessment,
    check_circuit_sources,
)
from examples.circuit_infrastructure import make_infrastructure_requests
from examples.circuit_sources import make_source_inventory
from test_build_archive import unchecked_zip, zip_entries


def json_bytes(value):
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def rehashed_archive(data, replacements, **manifest_changes):
    """Recompute container hashes independently of the production bundle writer."""
    entries = dict(zip_entries(data))
    entries.update(replacements)
    manifest = json.loads(entries["manifest.json"])
    manifest.update(manifest_changes)
    for record in manifest["files"]:
        payload = entries[record["path"]]
        record["sha256"] = hashlib.sha256(payload).hexdigest()
        record["byte_length"] = len(payload)
    entries["manifest.json"] = json_bytes(manifest)
    return unchecked_zip(sorted(entries.items()))


class CircuitReviewAdversarialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        construction, bindings, evidence = make_infrastructure_requests()
        cls.build = build_circuit_construction(construction)
        cls.sources = make_source_inventory()
        cls.receipt = capture_circuit_evidence(cls.build, expected_request=evidence)
        cls.authority = CircuitReviewAuthority(
            construction,
            sources=cls.sources,
            bindings=bindings,
            evidence=evidence,
            evidence_receipt_fingerprint=cls.receipt.fingerprint,
        )
        cls.bundle = create_circuit_review_bundle(
            cls.build,
            expected_authority=cls.authority,
            source_assessment=check_circuit_sources(cls.sources),
            binding_assessment=check_circuit_bindings(
                cls.build.candidate, expected_request=bindings
            ),
            evidence_receipt=cls.receipt,
            evidence_assessment=check_circuit_evidence(
                cls.receipt, cls.build, expected_request=evidence
            ),
        )

    def verify(self, data=None, *, authority=None):
        return verify_circuit_review_bundle(
            self.bundle.data if data is None else data,
            expected_authority=self.authority if authority is None else authority,
        )

    def test_external_authority_is_required_even_for_self_consistent_archive(self):
        self.verify()
        with self.assertRaises(TypeError):
            verify_circuit_review_bundle(self.bundle.data)
        with self.assertRaises(SerializationError):
            verify_circuit_review_bundle(self.bundle.data, expected_authority=None)
        incomplete = CircuitReviewAuthority(self.authority.construction)
        with self.assertRaises(SerializationError):
            self.verify(authority=incomplete)

    def test_external_source_binding_and_evidence_edits_cannot_reuse_saved_reports(
        self,
    ):
        replacements = (
            {"sources": replace(self.sources, version="corrected-software-metadata")},
            {
                "bindings": replace(
                    self.authority.bindings,
                    assumptions=("Changed nominal software assumption.",),
                )
            },
            {
                "evidence": replace(
                    self.authority.evidence,
                    sources=(replace(self.authority.evidence.sources[0], version="2"),),
                )
            },
            {"evidence_receipt_fingerprint": "f" * 64},
        )
        for fields in replacements:
            with self.subTest(fields=tuple(fields)):
                authority = replace(self.authority, **fields)
                with self.assertRaises(SerializationError):
                    self.verify(authority=authority)

    def test_rehashed_validly_typed_forged_reports_require_fresh_replay(self):
        entries = dict(zip_entries(self.bundle.data))
        construction = json.loads(entries["construction.json"])
        construction["assessment"]["reconstructed_fingerprint"] = "f" * 64
        binding = json.loads(entries["checks/bindings.json"])
        binding["assumptions"] = ["A forged retained assumption."]
        evidence = json.loads(entries["checks/evidence.json"])
        evidence["dependencies"][0]["recorded_fingerprint"] = "f" * 64
        sources = json.loads(entries["checks/sources.json"])
        sources["dependencies"]["checker"] = "forged-current-checker"
        for path, document, record_type, diagnostic in (
            ("construction.json", construction, CircuitConstructionBuild, "fresh"),
            (
                "checks/bindings.json",
                binding,
                CircuitBindingAssessment,
                "fresh complete replay",
            ),
            (
                "checks/evidence.json",
                evidence,
                CircuitEvidenceAssessment,
                "fresh independent replay",
            ),
            (
                "checks/sources.json",
                sources,
                CircuitSourcesAssessment,
                "current independent metadata checks",
            ),
        ):
            with self.subTest(path=path):
                # These mutations reach verification as valid typed records;
                # parse failure is not evidence of independent replay.
                changed_record = record_type.from_dict(document)
                manifest_changes = (
                    {"construction_fingerprint": changed_record.fingerprint}
                    if path == "construction.json"
                    else {}
                )
                changed = rehashed_archive(
                    self.bundle.data, {path: json_bytes(document)}, **manifest_changes
                )
                self.assertEqual(
                    inspect_circuit_review_bundle(changed)["verification"],
                    "historical_unverified",
                )
                # Container integrity alone must not accept these valid JSON edits.
                with self.assertRaisesRegex(SerializationError, diagnostic):
                    self.verify(changed)

    def test_freshly_recomputed_assessment_cannot_replace_frozen_evidence_snapshot(
        self,
    ):
        replacement_receipt = replace(
            self.receipt,
            sources=(replace(self.receipt.sources[0], source_fingerprint="f" * 64),),
        )
        replacement_assessment = check_circuit_evidence(
            replacement_receipt, self.build, expected_request=self.authority.evidence
        )
        self.assertEqual(replacement_assessment.freshness, "stale")
        changed = rehashed_archive(
            self.bundle.data,
            {
                "evidence/receipt.json": json_bytes(replacement_receipt.to_dict()),
                "checks/evidence.json": json_bytes(replacement_assessment.to_dict()),
            },
            authority_fingerprint=replace(
                self.authority,
                evidence_receipt_fingerprint=replacement_receipt.fingerprint,
            ).fingerprint,
        )
        self.assertEqual(
            inspect_circuit_review_bundle(changed)["verification"],
            "historical_unverified",
        )
        with self.assertRaisesRegex(
            SerializationError, "complete independent authority"
        ):
            self.verify(changed)

    def test_removing_whole_optional_cohorts_cannot_silently_reduce_external_authority(
        self,
    ):
        cohorts = (
            ("sources", {"sources/inventory.json", "checks/sources.json"}),
            ("bindings", {"bindings/request.json", "checks/bindings.json"}),
            (
                "evidence",
                {
                    "evidence/request.json",
                    "evidence/receipt.json",
                    "checks/evidence.json",
                },
            ),
        )
        for cohort, removed in cohorts:
            with self.subTest(removed=sorted(removed)):
                entries = {
                    path: payload
                    for path, payload in zip_entries(self.bundle.data)
                    if path not in removed
                }
                manifest = json.loads(entries["manifest.json"])
                manifest["files"] = [
                    item for item in manifest["files"] if item["path"] not in removed
                ]
                authority_changes = {cohort: None}
                if cohort == "evidence":
                    authority_changes["evidence_receipt_fingerprint"] = None
                manifest["authority_fingerprint"] = replace(
                    self.authority, **authority_changes
                ).fingerprint
                entries["manifest.json"] = json_bytes(manifest)
                changed = unchecked_zip(sorted(entries.items()))
                self.assertEqual(
                    inspect_circuit_review_bundle(changed)["verification"],
                    "historical_unverified",
                )
                with self.assertRaisesRegex(
                    SerializationError, "complete independent authority"
                ):
                    self.verify(changed)

    def test_rehashed_stale_tool_and_package_versions_cannot_grant_fresh_acceptance(
        self,
    ):
        original = dict(zip_entries(self.bundle.data))
        for kind in ("tool", "package"):
            with self.subTest(kind=kind):
                entries = dict(original)
                manifest = json.loads(entries["manifest.json"])
                if kind == "tool":
                    manifest["toolchain"][0]["version"] = "obsolete-software-policy"
                else:
                    manifest["package_version"] = "0.0.obsolete"
                entries["manifest.json"] = json_bytes(manifest)
                with self.assertRaises(SerializationError):
                    self.verify(unchecked_zip(sorted(entries.items())))

    def test_duplicate_json_keys_and_nonfinite_numbers_fail_after_rehashing(self):
        entries = dict(zip_entries(self.bundle.data))
        path = "checks/bindings.json"
        original = entries[path]
        duplicates = original.replace(b"{", b'{"outcome":"pass",', 1)
        nonfinite = original.replace(b"{", b'{"unexpected":NaN,', 1)
        for payload in (duplicates, nonfinite, b"\xffnot-utf8"):
            with self.subTest(payload=payload[:40]):
                changed = rehashed_archive(self.bundle.data, {path: payload})
                with self.assertRaises(SerializationError):
                    self.verify(changed)

    def test_bundle_replay_does_not_invoke_a_producer_or_open_external_resources(self):
        expected = self.verify()
        with ExitStack() as stack:
            for target in (
                "biocompiler.backends.circuit_construction.construct_circuit_candidate",
                "biocompiler.compiler.circuit_construction.construct_circuit_candidate",
                "biocompiler.compiler.circuit_construction.build_circuit_construction",
                "biocompiler.build_circuit_construction",
                "pathlib.Path.open",
                "socket.socket",
            ):
                stack.enter_context(
                    patch(target, side_effect=AssertionError("Forbidden: " + target))
                )
            self.assertEqual(self.verify(), expected)
            self.assertIsInstance(inspect_circuit_review_bundle(self.bundle.data), dict)


if __name__ == "__main__":
    unittest.main()
