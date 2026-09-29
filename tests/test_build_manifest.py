"""Portable build authority and immutable canonical package inventory schemas."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import unittest

from cellweave.artifacts.manifest import (
    REQUIRED_FILES,
    AcceptedStage,
    BuildManifest,
    PackageFile,
    ReferenceBuildRequest,
    RunMetadata,
    ToolPin,
    validate_package_path,
)
from cellweave.errors import SerializationError
from cellweave.ir.intent import SourceLocation
from cellweave.ir.serialization import fingerprint
from examples.reference_construct import reference_request


def request_fixture(alphabet="DNA"):
    request, _, _ = reference_request(alphabet)
    return ReferenceBuildRequest(request)


def manifest_fixture():
    return BuildManifest(
        request_fingerprint=request_fixture().fingerprint,
        files=tuple(
            PackageFile(path, role, fingerprint(path), 10)
            for path, role in REQUIRED_FILES.items()
        )
        + (
            PackageFile(
                "references/reviewed-cds/manifest.json",
                "reference-input",
                "a" * 64,
                100,
            ),
        ),
        accepted_stages=(
            AcceptedStage(
                "components", "b" * 64, "c" * 64, "cellweave.construct_request.v0.1"
            ),
            AcceptedStage("construct", "d" * 64, "e" * 64, "cellweave.construct.v0.1"),
            AcceptedStage("molecular", "f" * 64, "0" * 64, "cellweave.molecular.v0.1"),
        ),
        toolchain=(ToolPin("compiler", "1", "1" * 64),),
        package_version="0.1.0.dev8",
    )


class BuildManifestTests(unittest.TestCase):
    def test_reference_request_roundtrips_without_inventing_upstream_intent(self):
        for alphabet in ("DNA", "RNA"):
            request = request_fixture(alphabet)
            self.assertEqual(
                ReferenceBuildRequest.from_json(request.to_json()), request
            )
            self.assertEqual(request.profile, "reference_cds")
            self.assertEqual(request.artifact_scope, "exact_cds")
            self.assertEqual(request.construct.target.payload_format.value, alphabet)
            self.assertNotIn("intent", request.to_dict())
            changed = replace(request, fasta_line_width=60)
            self.assertNotEqual(request.fingerprint, changed.fingerprint)
            self.assertEqual(request.construct, changed.construct)
        for change in (
            {"profile": "arbitrary_intent"},
            {"artifact_scope": "complete_payload"},
            {"fasta_line_width": True},
            {"fasta_line_width": 0},
            {"fasta_line_width": 10001},
        ):
            with self.subTest(change=change), self.assertRaises(SerializationError):
                replace(request, **change)

    def test_source_locations_must_be_logical_before_request_is_frozen(self):
        request = request_fixture()
        original = request.construct
        for path in (
            "/Users/someone/project/build.py",
            "C:/project/build.py",
            "C:\\project\\build.py",
            "../build.py",
            "sources/../build.py",
            "sources/./build.py",
            "sources//build.py",
            "sources/build.py/",
            "sources/build\n.py",
            "//host/share/build.py",
        ):
            source = SourceLocation(path, 7, "build")
            changed_placement = replace(original.placements[0], source=source)
            changed_instance = replace(original.composition.instances[0], source=source)
            alternatives = (
                replace(original, placements=(changed_placement,)),
                replace(
                    original,
                    composition=replace(
                        original.composition, instances=(changed_instance,)
                    ),
                ),
            )
            for construct in alternatives:
                with self.subTest(path=path), self.assertRaises(SerializationError):
                    ReferenceBuildRequest(construct)
        with self.assertRaises(SerializationError):
            ReferenceBuildRequest.from_dict(
                request.to_dict() | {"absolute_source_root": "/Users/someone"}
            )

    def test_manifest_inventory_roundtrip_has_no_recursive_or_run_identity(self):
        manifest = manifest_fixture()
        restored = BuildManifest.from_json(manifest.to_json())
        self.assertEqual(manifest, restored)
        self.assertEqual(manifest.build_fingerprint, manifest.fingerprint)
        self.assertEqual(manifest.build_fingerprint, fingerprint(manifest.to_dict()))
        self.assertNotIn("build_fingerprint", manifest.to_dict())
        self.assertNotIn("run_metadata", manifest.to_dict())
        self.assertFalse(
            {"manifest.json", "run.json"} & {f.path for f in manifest.files}
        )
        self.assertEqual(manifest.status, "complete")
        self.assertEqual(manifest.scope, "exact_cds")
        with self.assertRaises(SerializationError):
            BuildManifest.from_dict(
                manifest.to_dict() | {"timestamp": "2026-09-29T00:00:00Z"}
            )

    def test_manifest_identity_changes_for_inventory_stage_tool_or_request_edits(self):
        manifest = manifest_fixture()
        first = manifest.files[0]
        stage = manifest.accepted_stages[0]
        alternatives = (
            replace(manifest, request_fingerprint="2" * 64),
            replace(
                manifest, files=(replace(first, sha256="2" * 64), *manifest.files[1:])
            ),
            replace(
                manifest, files=(replace(first, byte_length=11), *manifest.files[1:])
            ),
            replace(
                manifest,
                accepted_stages=(
                    replace(stage, record_fingerprint="2" * 64),
                    *manifest.accepted_stages[1:],
                ),
            ),
            replace(
                manifest,
                accepted_stages=(
                    replace(stage, artifact_fingerprint="2" * 64),
                    *manifest.accepted_stages[1:],
                ),
            ),
            replace(manifest, toolchain=(replace(manifest.toolchain[0], version="2"),)),
            replace(manifest, package_version="0.1.0.dev9"),
        )
        for changed in alternatives:
            with self.subTest(changed=changed.fingerprint):
                self.assertNotEqual(
                    manifest.build_fingerprint, changed.build_fingerprint
                )

    def test_file_and_tool_declaration_order_is_canonical_but_stage_order_is_fixed(
        self,
    ):
        manifest = manifest_fixture()
        manifest = replace(
            manifest, toolchain=(*manifest.toolchain, ToolPin("another", "1", "2" * 64))
        )
        reversed_declarations = replace(
            manifest,
            files=tuple(reversed(manifest.files)),
            toolchain=tuple(reversed(manifest.toolchain)),
        )
        self.assertEqual(reversed_declarations, manifest)
        self.assertEqual(reversed_declarations.fingerprint, manifest.fingerprint)
        with self.assertRaises(SerializationError):
            replace(manifest, accepted_stages=tuple(reversed(manifest.accepted_stages)))

    def test_required_inventory_roles_and_stage_schemas_are_not_optional(self):
        manifest = manifest_fixture()
        for index in range(len(manifest.files)):
            with self.subTest(index=index), self.assertRaises(SerializationError):
                replace(
                    manifest, files=manifest.files[:index] + manifest.files[index + 1 :]
                )
        for change in (
            {"accepted_stages": manifest.accepted_stages[:2]},
            {"toolchain": ()},
            {"status": "partial"},
            {"scope": "complete_payload"},
            {"profile": "arbitrary_intent"},
        ):
            with self.subTest(change=change), self.assertRaises(SerializationError):
                replace(manifest, **change)
        for stage in manifest.accepted_stages:
            with self.subTest(stage=stage.stage), self.assertRaises(SerializationError):
                replace(stage, artifact_schema="cellweave.behavior.v0.1")
        with self.assertRaises(SerializationError):
            replace(manifest.files[0], role="sequence")
        with self.assertRaises(SerializationError):
            PackageFile("elsewhere/source.json", "reference-input", "a" * 64, 1)

    def test_archive_paths_reject_host_names_traversal_reserved_and_prefix_conflicts(
        self,
    ):
        for path in (
            "/root/file",
            "../file",
            "x/../file",
            "x/./file",
            "x//file",
            "x/",
            "C:/file",
            "x\\file",
            "x\x00file",
            "x\nfile",
            "manifest.json",
            "run.json",
            "",
        ):
            with self.subTest(path=path), self.assertRaises(SerializationError):
                validate_package_path(path)
        self.assertEqual(
            validate_package_path("manifest.json", allow_reserved=True), "manifest.json"
        )
        self.assertEqual(
            validate_package_path("references/ref/manifest.json"),
            "references/ref/manifest.json",
        )
        manifest = manifest_fixture()
        with self.assertRaises(SerializationError):
            replace(manifest, files=(*manifest.files, manifest.files[0]))
        with self.assertRaises(SerializationError):
            replace(
                manifest,
                files=(
                    *manifest.files,
                    PackageFile(
                        "references/reviewed-cds/manifest.json/extra",
                        "reference-input",
                        "a" * 64,
                        1,
                    ),
                ),
            )
        with self.assertRaises(SerializationError):
            replace(manifest, toolchain=manifest.toolchain * 2)

    def test_run_metadata_keeps_machine_paths_out_of_canonical_identity(self):
        manifest = manifest_fixture()
        first = RunMetadata(
            "2026-09-29T12:30:00Z",
            "linux",
            {"sources/reference.py": "/checkout/a/reference.py"},
        )
        second = RunMetadata(
            "2026-09-30T06:10:05.123Z",
            "macOS",
            {"sources/reference.py": "/different/checkout/reference.py"},
        )
        self.assertNotEqual(first.fingerprint, second.fingerprint)
        for metadata in (first, second):
            self.assertEqual(RunMetadata.from_json(metadata.to_json()), metadata)
            self.assertEqual(
                manifest.build_fingerprint, manifest_fixture().build_fingerprint
            )
            self.assertNotIn(metadata.machine_label, manifest.to_json())
        self.assertEqual(
            RunMetadata(
                "2026-09-29T00:00:00Z",
                "windows",
                {"source.py": "C:\\project\\source.py"},
            ).machine_label,
            "windows",
        )
        locations = {"source.py": "/original/source.py"}
        immutable = RunMetadata("2026-09-29T00:00:00Z", "host", locations)
        locations["source.py"] = "/changed/source.py"
        self.assertEqual(immutable.locations["source.py"], "/original/source.py")
        with self.assertRaises(TypeError):
            immutable.locations["new.py"] = "/new.py"

    def test_run_metadata_dates_and_location_types_are_strict(self):
        for value in (
            "2026-02-30T00:00:00Z",
            "2026-09-29",
            "2026-09-29T12:00:00",
            "2026-09-29T12:00:00+00:00",
            "2026-09-29T12:00:00-07:00",
            "2026-09-29T25:00:00Z",
        ):
            with self.subTest(timestamp=value), self.assertRaises(SerializationError):
                RunMetadata(value, "host")
        for value in (
            {"../source.py": "/source.py"},
            {"/source.py": "/source.py"},
            {"source.py": "relative/source.py"},
            {"source.py": None},
        ):
            with self.subTest(locations=value), self.assertRaises(SerializationError):
                RunMetadata("2026-09-29T00:00:00Z", "host", value)

    def test_escaped_surrogates_fail_at_schema_boundary_before_hash_or_export(self):
        malformed = "\ud800"
        for make in (
            lambda: ToolPin(malformed, "1", "a" * 64),
            lambda: RunMetadata("2026-09-29T00:00:00Z", malformed),
            lambda: validate_package_path("references/ref/" + malformed),
        ):
            with self.assertRaisesRegex(SerializationError, "UTF-8"):
                make()
        request = request_fixture()
        source = SourceLocation("logical.py", 1, malformed)
        construct = replace(
            request.construct,
            placements=(replace(request.construct.placements[0], source=source),),
        )
        with self.assertRaisesRegex(SerializationError, "UTF-8"):
            ReferenceBuildRequest(construct)
        data = manifest_fixture().to_dict()
        data["toolchain"][0]["version"] = malformed
        with self.assertRaisesRegex(SerializationError, "UTF-8"):
            BuildManifest.from_dict(data)

    def test_all_public_records_are_frozen_and_malformed_imports_are_consistent(self):
        manifest = manifest_fixture()
        samples = (
            request_fixture(),
            manifest,
            *manifest.files[:1],
            *manifest.accepted_stages[:1],
            *manifest.toolchain,
            RunMetadata("2026-09-29T00:00:00Z", "host"),
        )
        for sample in samples:
            cls = type(sample)
            with (
                self.subTest(schema=cls.__name__),
                self.assertRaises(FrozenInstanceError),
            ):
                sample.schema_version = "future"
            for root in (None, [], 1, True, "bad"):
                with (
                    self.subTest(schema=cls.__name__, root=root),
                    self.assertRaises(SerializationError),
                ):
                    cls.from_dict(root)
            original = sample.to_dict()
            for key in original:
                for bad in (None, True, [], {}):
                    if original[key] == bad:
                        continue
                    data = deepcopy(original)
                    data[key] = bad
                    with (
                        self.subTest(schema=cls.__name__, key=key, bad=bad),
                        self.assertRaises(SerializationError),
                    ):
                        cls.from_dict(data)
            for extra in ({"accepted": True}, {"schema_version": "future"}):
                with (
                    self.subTest(schema=cls.__name__, extra=extra),
                    self.assertRaises(SerializationError),
                ):
                    cls.from_dict(original | extra)
        text = manifest.to_json(indent=None)
        with self.assertRaisesRegex(SerializationError, "Duplicate JSON"):
            BuildManifest.from_json(text[:-1] + ',"files":[]}')


if __name__ == "__main__":
    unittest.main()
