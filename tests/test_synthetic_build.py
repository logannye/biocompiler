"""Synthetic packages bind independent inputs and rerun current offline checks."""

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import biocompiler as bc
from biocompiler.artifacts.archive import assemble_archive, read_archive, _canonical_zip
from biocompiler.artifacts.manifest import RunMetadata
from biocompiler.artifacts.synthetic_build import (
    SyntheticBuildRequest,
    SyntheticHistory,
)
from biocompiler.cli import main
from biocompiler.compiler.pipeline import PipelineError
from biocompiler.compiler.synthetic_build import (
    build_synthetic_package,
    publish_synthetic_package,
    verify_synthetic_package,
)
from biocompiler.errors import SerializationError
from biocompiler.registry.synthetic import TEMPORAL_PROFILE_VERSION
from biocompiler.synthesis.synthetic import SyntheticGeneratorConfig
from examples.checked_pipeline import build_request


def portable_request():
    request, history = build_request()
    intent = replace(
        request.build_request.intent,
        nodes=tuple(
            replace(
                node, source=replace(node.source, file="examples/checked_pipeline.py")
            )
            if node.source
            else node
            for node in request.build_request.intent.nodes
        ),
    )
    build = replace(request.build_request, intent=intent)
    realization = bc.RealizationRequest.freeze(
        build,
        bc.lower_to_behavior(build),
        request.contract,
        request.domain,
    )
    return SyntheticBuildRequest(realization, SyntheticHistory(history), 7)


class SyntheticBuildTests(unittest.TestCase):
    def setUp(self):
        self.request = portable_request()

    def build(self, **kwargs):
        return build_synthetic_package(self.request, **kwargs)

    def mutate(self, package, path, change):
        manifest, files, metadata = read_archive(package.data)
        content = dict(files)
        value = json.loads(content[path])
        change(value)
        content[path] = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
        inventory = tuple(
            replace(
                item,
                sha256=hashlib.sha256(content[item.path]).hexdigest(),
                byte_length=len(content[item.path]),
            )
            for item in manifest.files
        )
        return assemble_archive(replace(manifest, files=inventory), content, metadata)

    def test_roundtrip_reproduces_all_inputs_and_independent_stage_evidence(self):
        package = self.build()
        manifest, files, _ = read_archive(package.data)
        self.assertEqual(manifest.scope, "synthetic_realization")
        self.assertEqual(manifest.intended_use, "software_test")
        self.assertEqual(
            json.loads(files["checks/realization.json"])["outcome"], "pass"
        )
        summary = json.loads(files["result.json"])
        self.assertEqual(
            [item["id"] for item in summary["stages"]],
            ["request", "behavior", "mechanism"],
        )
        self.assertEqual(
            [item["id"] for item in summary["unresolved"]], ["molecular_behavior"]
        )
        self.assertEqual(
            json.loads(files["inputs/history.json"]), self.request.history.to_dict()
        )
        self.assertEqual(
            json.loads(files["inputs/config.json"]), self.request.config.to_dict()
        )
        self.assertEqual(
            verify_synthetic_package(package.data, expected_request=self.request).data,
            package.data,
        )
        restored = SyntheticBuildRequest.from_json(self.request.to_json())
        self.assertEqual(build_synthetic_package(restored).data, package.data)

    def test_temporal_package_keeps_selected_config_and_reconstructs_timers(self):
        from examples.synthetic_build import prepare_request

        request = prepare_request()
        package = build_synthetic_package(request)
        _, files, _ = read_archive(package.data)
        candidate = json.loads(files["candidate.json"])
        self.assertEqual(candidate["generator_config"], request.config.to_dict())
        operations = {node["kind"] for node in candidate["mechanism"]["nodes"]}
        self.assertTrue({"held_for", "onset", "pulse", "memory"} <= operations)
        self.assertEqual(
            verify_synthetic_package(package.data, expected_request=request).data,
            package.data,
        )

    def test_human_target_cannot_be_packaged_or_relabelled_as_software(self):
        from examples.human_target import make_human_target

        target = replace(make_human_target(), capabilities=("synthetic_signal_graph",))
        build = replace(self.request.realization.build_request, target=target)
        request = replace(
            self.request,
            realization=replace(self.request.realization, build_request=build),
        )
        with self.assertRaisesRegex(
            SerializationError, "Human therapeutic use is not admitted"
        ):
            build_synthetic_package(request)

    def test_relocation_and_run_metadata_leave_canonical_identity_unchanged(self):
        first = self.build(
            run_metadata=RunMetadata(
                "2026-09-29T00:00:00Z", "first", {"design": "/one/design.py"}
            )
        )
        second = self.build(
            run_metadata=RunMetadata(
                "2026-09-30T00:00:00Z", "second", {"design": "/two/design.py"}
            )
        )
        self.assertEqual(first.build_fingerprint, second.build_fingerprint)
        self.assertNotEqual(first.archive_sha256, second.archive_sha256)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "moved.bcb"
            path.write_bytes(second.data)
            self.assertEqual(
                verify_synthetic_package(
                    path.read_bytes(),
                    expected_build_fingerprint=first.build_fingerprint,
                ).data,
                second.data,
            )
        self.assertEqual(self.build().data, self.build().data)

    def test_independent_authority_is_required_and_binds_full_request(self):
        package = self.build()
        with self.assertRaisesRegex(SerializationError, "independently trusted"):
            verify_synthetic_package(package.data)
        with self.assertRaisesRegex(
            SerializationError, "complete SyntheticBuildRequest"
        ):
            verify_synthetic_package(
                package.data, expected_request=self.request.realization
            )
        with self.assertRaisesRegex(
            SerializationError, "independently trusted identity"
        ):
            verify_synthetic_package(package.data, expected_build_fingerprint="0" * 64)
        changed_realization = replace(
            self.request.realization,
            contract=replace(self.request.realization.contract, id="different"),
        )
        changed_history = replace(
            self.request.history,
            frames=(
                self.request.history.frames[0],
                replace(self.request.history.frames[1], time=2),
                self.request.history.frames[2],
            ),
        )
        for changed in (
            replace(self.request, realization=changed_realization),
            replace(self.request, history=changed_history),
            replace(self.request, until=8),
            # Python equality considers 7 and 7.0 equal; frozen artifact
            # authority must still bind their different canonical identities.
            replace(self.request, until=7.0),
            replace(
                self.request,
                config=SyntheticGeneratorConfig(
                    profile_version=TEMPORAL_PROFILE_VERSION
                ),
            ),
        ):
            with self.subTest(authority=changed.fingerprint):
                other = build_synthetic_package(changed)
                self.assertNotEqual(other.build_fingerprint, package.build_fingerprint)
                with self.assertRaisesRegex(
                    SerializationError, "independent authority"
                ):
                    verify_synthetic_package(other.data, expected_request=self.request)

    def test_rehashed_candidate_or_claim_tampering_fails_current_reconstruction(self):
        package = self.build()
        for path, change in (
            ("candidate.json", lambda doc: doc.update(request_fingerprint="0" * 64)),
            (
                "checks/realization.json",
                lambda doc: doc.update(claim_scope="Universal guarantee"),
            ),
            ("result.json", lambda doc: doc.update(unresolved=[])),
            ("stages/mechanism.json", lambda doc: doc.update(accepted=False)),
            ("inputs/history.json", lambda doc: doc["frames"][1].update(time=2)),
            (
                "inputs/config.json",
                lambda doc: doc.update(generator_version="forged.v999"),
            ),
            ("inputs/catalog.json", lambda doc: doc.update(id="forged")),
        ):
            with self.subTest(path=path):
                data = self.mutate(package, path, change)
                # Inspection can verify self-consistent byte identities only.
                read_archive(data)
                with self.assertRaisesRegex(
                    SerializationError, "stale|altered|unsupported"
                ):
                    verify_synthetic_package(data, expected_request=self.request)

    def test_current_model_and_distribution_versions_are_pinned(self):
        package = self.build()
        for name in (
            "biocompiler.compiler.synthetic_build.MODEL_RUNNER_VERSION",
            "biocompiler.__version__",
        ):
            with self.subTest(name=name), patch(name, "changed.v999"):
                with self.assertRaisesRegex(
                    SerializationError, "stale|altered|unsupported"
                ):
                    verify_synthetic_package(
                        package.data, expected_request=self.request
                    )
        with patch(
            "biocompiler.compiler.synthetic_build.run_synthetic_pipeline",
            side_effect=PipelineError("fresh execution rejected"),
        ):
            with self.assertRaisesRegex(PipelineError, "fresh execution rejected"):
                verify_synthetic_package(package.data, expected_request=self.request)

    def test_failed_checks_cannot_publish_and_prior_archive_survives(self):
        package = self.build()
        inactive = replace(
            self.request, history=SyntheticHistory((self.request.history.frames[0],))
        )
        with self.assertRaises(PipelineError):
            build_synthetic_package(inactive)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "accepted.bcb"
            publish_synthetic_package(package, path)
            altered = replace(
                package,
                data=self.mutate(
                    package, "result.json", lambda doc: doc.update(unresolved=[])
                ),
            )
            with self.assertRaises(SerializationError):
                publish_synthetic_package(altered, path)
            self.assertEqual(path.read_bytes(), package.data)
            with patch(
                "biocompiler.artifacts.archive.os.replace",
                side_effect=OSError("unavailable"),
            ):
                with self.assertRaises(OSError):
                    publish_synthetic_package(package, path)
            self.assertEqual(path.read_bytes(), package.data)
            self.assertEqual(
                [item.name for item in path.parent.iterdir()], ["accepted.bcb"]
            )

    def test_request_import_rejects_nonportable_unbounded_and_unknown_inputs(self):
        for change in (
            lambda doc: doc.update(until=None),
            lambda doc: doc.update(until=True),
            lambda doc: doc.update(until=4),
            lambda doc: doc.update(extra="ignored?"),
            lambda doc: doc.update(intended_use="human_therapeutic"),
            lambda doc: doc.update(profile="complete_payload"),
            lambda doc: doc["history"].update(frames=[]),
            lambda doc: doc["history"]["frames"][0].update(time=1),
            lambda doc: doc["history"]["frames"][1].update(time=0),
            lambda doc: doc["history"]["frames"][0].update(unknown=[]),
            lambda doc: next(
                iter(doc["history"]["frames"][0]["contacts"]["x"].values())
            ).update(present="true"),
            lambda doc: doc["realization"]["build_request"]["provenance"].update(
                locations={"source": "/host/source.py"}
            ),
        ):
            doc = self.request.to_dict()
            change(doc)
            with self.subTest(doc=doc["until"]), self.assertRaises(SerializationError):
                SyntheticBuildRequest.from_dict(doc)
        original, history = build_request()
        with self.assertRaisesRegex(SerializationError, "relative POSIX"):
            SyntheticBuildRequest(original, SyntheticHistory(history), 7)
        with self.assertRaisesRegex(SerializationError, "Duplicate JSON"):
            SyntheticBuildRequest.from_json(
                '{"schema_version": "first", "schema_version": "second"}'
            )

    def test_archive_dispatch_rejects_malformed_schema_and_extra_executable(self):
        package = self.build()
        manifest, files, _ = read_archive(package.data)
        for schema in ([], {}, None, 1, "unsupported.schema"):
            document = manifest.to_dict()
            document["schema_version"] = schema
            entries = {**files, "manifest.json": json.dumps(document).encode()}
            with self.subTest(schema=schema), self.assertRaises(SerializationError):
                read_archive(_canonical_zip(entries))
        with self.assertRaisesRegex(SerializationError, "inventory"):
            assemble_archive(
                manifest,
                {**files, "authoring.py": b"raise AssertionError('must not execute')"},
            )

    def test_cli_build_inspect_verify_and_historical_labels(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            request, path = root / "request.json", root / "software.bcb"
            request.write_text(self.request.to_json())
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    main(
                        [
                            "synthetic-build",
                            "--request",
                            str(request),
                            "--output",
                            str(path),
                        ]
                    ),
                    0,
                )
            identity = json.loads(output.getvalue())["build_fingerprint"]
            for command, label in (
                (["synthetic-inspect", str(path)], "Historical content"),
                (
                    ["synthetic-verify", str(path), "--expected-build", identity],
                    "fresh independent",
                ),
                (
                    ["synthetic-verify", str(path), "--expected-request", str(request)],
                    "fresh independent",
                ),
                (["inspect", str(request)], "Historical content"),
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(command), 0)
                self.assertIn(label, output.getvalue())
                self.assertNotIn(
                    'human_therapeutic_admission": "admitted', output.getvalue()
                )
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                self.assertEqual(
                    main(["synthetic-verify", str(path), "--expected-build", "bad"]), 2
                )
                self.assertEqual(main(["reference-inspect", str(path)]), 2)
            self.assertIn("identity", stderr.getvalue())
            self.assertIn("Expected a reference package", stderr.getvalue())
            self.assertEqual(path.read_bytes(), self.build().data)


if __name__ == "__main__":
    unittest.main()
