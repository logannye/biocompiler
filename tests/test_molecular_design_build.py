"""Portable nominal designs require complete authority and current reconstruction."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.artifacts.archive import _canonical_zip, assemble_archive, read_archive
from biocompiler.artifacts.manifest import RunMetadata
from biocompiler.artifacts.molecular_design import (
    REQUIRED_FILES,
    MolecularDesignBuildManifest,
    MolecularDesignHandoff,
)
from biocompiler.compiler.molecular_design_build import (
    _verify_fasta,
    build_molecular_design_package,
    publish_molecular_design_package,
    verify_molecular_design_package,
)
from biocompiler.compiler.pipeline import PipelineError
from biocompiler.errors import SerializationError
from biocompiler.ir.molecular_design import (
    FragmentPlacement,
    MolecularDesignArtifact,
    MolecularDesignRequest,
    SequenceFragment,
)
from biocompiler.ir.payload import PayloadFeature, PayloadMolecule
from biocompiler.ir.serialization import fingerprint
from biocompiler.semantics.coordinates import SequenceRange


def design_request(utr="GG", molecule_id="nonfunctional fixture"):
    """Literal invented fragments; no emitted output supplies the expected spelling."""
    words = (
        ("five_prime_utr", utr),
        ("cds", "AUGGCUUAA"),
        ("three_prime_utr", "CC"),
        ("poly_a", "AAAA"),
    )
    fragments = tuple(
        SequenceFragment(
            kind,
            sequence,
            hashlib.sha256(sequence.encode("ascii")).hexdigest(),
            "invented-test-fragment:" + kind,
        )
        for kind, sequence in words
    )
    placements = []
    start = 0
    for item in fragments:
        end = start + len(item.sequence)
        placements.append(
            FragmentPlacement(
                item.id,
                item.id,
                item.id,
                item.fingerprint,
                SequenceRange(0, len(item.sequence)),
                SequenceRange(start, end),
                "MA*" if item.id == "cds" else None,
            )
        )
        start = end
    features = tuple(
        PayloadFeature(key, "known", "invented-test-feature:" + key, value)
        for key, value in (
            ("cap", "cap1"),
            ("poly_a_tail", "exact:4"),
            ("nucleotide_modifications", "none"),
            ("end_structure", "single_strand"),
            ("five_prime_end", "capped"),
            ("three_prime_end", "hydroxyl"),
        )
    )
    return MolecularDesignRequest(
        "software_design_package", molecule_id, fragments, tuple(placements), features
    )


class MolecularDesignPackageTests(unittest.TestCase):
    def setUp(self):
        self.request = design_request()

    def build(self, **kwargs):
        return build_molecular_design_package(self.request, **kwargs)

    def mutate(self, package, path, change, *, raw=False):
        manifest, files, metadata = read_archive(package.data)
        files = dict(files)
        if raw:
            files[path] = change(files[path])
        else:
            document = json.loads(files[path])
            change(document)
            files[path] = (
                json.dumps(document, sort_keys=True, indent=2, ensure_ascii=False)
                + "\n"
            ).encode("utf-8")
        entries = tuple(
            replace(
                item,
                sha256=hashlib.sha256(files[item.path]).hexdigest(),
                byte_length=len(files[item.path]),
            )
            for item in manifest.files
        )
        return assemble_archive(replace(manifest, files=entries), files, metadata)

    def test_exact_inventory_retains_complete_design_and_independent_evidence(self):
        package = self.build()
        manifest, files, metadata = read_archive(package.data)
        self.assertIsNone(metadata)
        self.assertIsInstance(manifest, MolecularDesignBuildManifest)
        self.assertEqual(set(files), set(REQUIRED_FILES))
        self.assertEqual(manifest.scope, "software_molecular_design")
        self.assertEqual(manifest.reference_promotion, "not_promoted")
        self.assertEqual(manifest.human_therapeutic_admission, "not_admitted")
        candidate = MolecularDesignArtifact.from_json(files["candidate.json"].decode())
        molecule = PayloadMolecule.from_json(files["molecular.json"].decode())
        self.assertEqual(candidate.molecule, molecule)
        self.assertEqual(molecule.sequence, "GGAUGGCUUAACCAAAA")
        self.assertEqual(
            files["sequence.fasta"],
            b">nonfunctional%20fixture alphabet=RNA scope=software_molecular_design "
            b"use=software_test human_admission=not_admitted\nGGAUGGCUUAACCAAAA\n",
        )
        self.assertEqual(
            json.loads(files["inputs/fragments.json"])["fragments"],
            [item.to_dict() for item in self.request.fragments],
        )
        self.assertEqual(
            json.loads(files["inputs/layout.json"])["placements"],
            [item.to_dict() for item in self.request.placements],
        )
        self.assertEqual(
            json.loads(files["source-map.json"])["placements"],
            [item.to_dict() for item in self.request.placements],
        )
        for stage in ("request", "construct", "molecular"):
            self.assertEqual(
                json.loads(files[f"checks/{stage}.json"])["outcome"], "pass"
            )
        summary = json.loads(files["result.json"])
        self.assertEqual(summary["fasta_line_width"], 80)
        self.assertEqual(
            [item["id"] for item in summary["stages"]],
            ["components", "construct", "molecular"],
        )
        self.assertIn("material_quality", summary["unresolved_handoff_claims"])
        self.assertIn("material_potency", summary["unresolved_handoff_claims"])
        self.assertEqual(
            verify_molecular_design_package(
                package.data, expected_request=self.request
            ).data,
            package.data,
        )

    def test_handoff_records_nominal_identity_without_inventing_material_evidence(self):
        package = self.build()
        _, files, _ = read_archive(package.data)
        handoff = MolecularDesignHandoff.from_json(files["handoff.json"].decode())
        molecule = PayloadMolecule.from_json(files["molecular.json"].decode())
        self.assertEqual(handoff.request_fingerprint, self.request.fingerprint)
        self.assertEqual(handoff.molecule_fingerprint, molecule.fingerprint)
        self.assertEqual(handoff.features, molecule.features)
        self.assertEqual(handoff.sequence_length, 17)
        self.assertEqual(handoff.identity_kind, "nominal_design")
        self.assertEqual(handoff.actual_material_identity, "unestablished")
        for key, value in (
            ("actual_material_identity", "lot_1"),
            ("material_quality", "pass"),
            ("material_potency", "pass"),
            ("clinical_use", "authorized"),
            ("human_therapeutic_admission", "admitted"),
            ("reference_promotion", "promoted"),
            ("unresolved_claims", []),
            ("topology", "circular"),
        ):
            document = handoff.to_dict()
            document[key] = value
            with self.subTest(key=key), self.assertRaises(SerializationError):
                MolecularDesignHandoff.from_dict(document)

    def test_repeated_roundtrip_and_relocated_builds_are_byte_identical(self):
        package = self.build()
        restored = MolecularDesignRequest.from_json(self.request.to_json())
        self.assertEqual(build_molecular_design_package(restored).data, package.data)
        self.assertEqual(self.build().data, package.data)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "relocated.bcb"
            path.write_bytes(package.data)
            self.assertEqual(
                verify_molecular_design_package(
                    path.read_bytes(),
                    expected_build_fingerprint=package.build_fingerprint,
                ).data,
                package.data,
            )

    def test_run_metadata_changes_archive_but_not_design_identity(self):
        first = self.build(
            run_metadata=RunMetadata(
                "2026-09-30T00:00:00Z", "first", {"design": "/one/design.json"}
            )
        )
        second = self.build(
            run_metadata=RunMetadata(
                "2026-09-30T01:00:00Z", "second", {"design": "/two/design.json"}
            )
        )
        self.assertEqual(first.build_fingerprint, second.build_fingerprint)
        self.assertNotEqual(first.archive_sha256, second.archive_sha256)
        self.assertEqual(read_archive(first.data)[1], read_archive(second.data)[1])
        self.assertEqual(
            verify_molecular_design_package(
                second.data, expected_build_fingerprint=first.build_fingerprint
            ).data,
            second.data,
        )

    def test_fresh_verification_requires_full_independent_authority(self):
        package = self.build()
        with self.assertRaisesRegex(SerializationError, "independently trusted"):
            verify_molecular_design_package(package.data)
        with self.assertRaisesRegex(SerializationError, "independent authority"):
            verify_molecular_design_package(
                package.data,
                expected_request=replace(self.request, id="different_design"),
            )
        for identity in ("bad", "0" * 64):
            with (
                self.subTest(identity=identity),
                self.assertRaisesRegex(SerializationError, "build identity"),
            ):
                verify_molecular_design_package(
                    package.data, expected_build_fingerprint=identity
                )
        # An authority edit that produces another valid design still cannot be
        # substituted under the independent original request or build identity.
        different = build_molecular_design_package(design_request(utr="AA"))
        with self.assertRaisesRegex(SerializationError, "independent authority"):
            verify_molecular_design_package(
                different.data, expected_request=self.request
            )
        with self.assertRaisesRegex(SerializationError, "build identity"):
            verify_molecular_design_package(
                different.data, expected_build_fingerprint=package.build_fingerprint
            )

    def test_unknown_chemistry_and_human_target_cannot_produce_a_success_package(self):
        from examples.human_target import make_human_target

        unknown = replace(
            self.request,
            features=tuple(
                replace(item, status="unknown", value=None)
                if item.feature == "cap"
                else item
                for item in self.request.features
            ),
        )
        with self.assertRaises(PipelineError):
            build_molecular_design_package(unknown)
        human = replace(self.request, target=make_human_target())
        with self.assertRaisesRegex(SerializationError, "Human therapeutic use"):
            build_molecular_design_package(human)

    def test_rehashed_sequence_layout_mapping_checks_and_obligations_fail_reconstruction(
        self,
    ):
        package = self.build()
        edits = (
            ("candidate.json", lambda doc: doc["molecule"].update(sequence="A" * 17)),
            ("molecular.json", lambda doc: doc.update(sequence="A" * 17)),
            (
                "construct.json",
                lambda doc: doc["placements"][0]["molecule_range"].update(end=1),
            ),
            (
                "inputs/fragments.json",
                lambda doc: doc["fragments"][0].update(sequence="AA"),
            ),
            (
                "inputs/layout.json",
                lambda doc: doc["features"][0].update(value="none"),
            ),
            ("source-map.json", lambda doc: doc.update(placements=[])),
            ("checks/request.json", lambda doc: doc.update(outcome="unknown")),
            (
                "checks/construct.json",
                lambda doc: doc.update(diagnostics=[], outcome="fail"),
            ),
            ("checks/molecular.json", lambda doc: doc.update(unresolved_claims=[])),
            ("stages/molecular.json", lambda doc: doc.update(evidence=[])),
            ("result.json", lambda doc: doc.update(unresolved=[])),
            ("handoff.json", lambda doc: doc.update(material_quality="pass")),
        )
        for path, edit in edits:
            data = self.mutate(package, path, edit)
            self.assertNotEqual(data, package.data)
            with self.subTest(path=path), self.assertRaises(SerializationError):
                verify_molecular_design_package(data, expected_request=self.request)
        for edit in (
            lambda data: data.replace(b"GGAUG", b"AGAUG"),
            lambda data: data.replace(
                b"scope=software_molecular_design", b"scope=complete_payload"
            ),
        ):
            data = self.mutate(package, "sequence.fasta", edit, raw=True)
            with self.assertRaises(SerializationError):
                verify_molecular_design_package(data, expected_request=self.request)

    def test_stale_toolchain_and_strict_inventory_cannot_be_relabelled(self):
        package = self.build()
        manifest, files, metadata = read_archive(package.data)
        tool = manifest.toolchain[0]
        changed = replace(tool, version="stale", content_fingerprint=fingerprint("stale"))
        stale = replace(manifest, toolchain=(changed,) + manifest.toolchain[1:])
        data = assemble_archive(stale, files, metadata)
        with self.assertRaisesRegex(SerializationError, "stale"):
            verify_molecular_design_package(data, expected_request=self.request)
        for change in (
            lambda doc: doc.update(scope="complete_payload"),
            lambda doc: doc.update(intended_use="human_therapeutic"),
            lambda doc: doc.update(human_therapeutic_admission="admitted"),
            lambda doc: doc.update(files=doc["files"][:-1]),
            lambda doc: doc.update(extra="ignored"),
        ):
            document = manifest.to_dict()
            change(document)
            with self.assertRaises(SerializationError):
                MolecularDesignBuildManifest.from_dict(document)
        with self.assertRaisesRegex(SerializationError, "inventory"):
            assemble_archive(
                manifest, {**files, "authoring.py": b"raise AssertionError"}
            )
        for schema in ("unsupported", [], None):
            document = manifest.to_dict()
            document["schema_version"] = schema
            data = _canonical_zip(
                {**files, "manifest.json": json.dumps(document).encode()}
            )
            with self.assertRaises(SerializationError):
                read_archive(data)

    def test_publication_rechecks_before_atomic_replace_and_preserves_accepted_bytes(
        self,
    ):
        package = self.build()
        corrupted = self.mutate(
            package, "result.json", lambda doc: doc.update(status="failed")
        )
        altered_manifest = read_archive(corrupted)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "accepted.bcb"
            self.assertEqual(publish_molecular_design_package(package, path), path)
            with self.assertRaises(SerializationError):
                publish_molecular_design_package(
                    replace(package, manifest=altered_manifest, data=corrupted), path
                )
            self.assertEqual(path.read_bytes(), package.data)
            with patch(
                "biocompiler.artifacts.archive.os.replace",
                side_effect=OSError("write unavailable"),
            ):
                with self.assertRaisesRegex(OSError, "write unavailable"):
                    publish_molecular_design_package(package, path)
            self.assertEqual(path.read_bytes(), package.data)
            self.assertEqual(list(root.iterdir()), [path])

    def test_fasta_wraps_exactly_and_encodes_ids_without_altering_symbols(self):
        package = build_molecular_design_package(
            design_request("G" * 83, "fixture/α %")
        )
        _, files, _ = read_archive(package.data)
        molecule = PayloadMolecule.from_json(files["molecular.json"].decode())
        self.assertEqual(molecule.sequence, "G" * 83 + "AUGGCUUAACCAAAA")
        lines = files["sequence.fasta"].decode("ascii").splitlines()
        self.assertTrue(lines[0].startswith(">fixture%2F%CE%B1%20%25 "))
        self.assertEqual([len(line) for line in lines[1:]], [80, 18])
        _verify_fasta(files["sequence.fasta"], molecule)
        for data in (
            files["sequence.fasta"].replace(b"\n", b"\r\n"),
            files["sequence.fasta"].rstrip(b"\n"),
            files["sequence.fasta"].replace(b"alphabet=RNA", b"alphabet=DNA"),
            files["sequence.fasta"].replace(b"AUGGCUUAA", b"AUGGCCUAA"),
        ):
            with self.assertRaises(SerializationError):
                _verify_fasta(data, molecule)


if __name__ == "__main__":
    unittest.main()
