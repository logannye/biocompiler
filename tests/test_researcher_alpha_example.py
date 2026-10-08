"""Standalone example controls; native execution and network access are forbidden."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from biocompiler.core_client import CoreClient, CoreProtocolError, encode_json
from biocompiler.core_policy_material import PolicyMaterialResult
from biocompiler.policy import research_project as api


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/researcher_alpha"
SPEC = importlib.util.spec_from_file_location("researcher_alpha_example", ROOT / "examples/researcher_alpha.py")
assert SPEC is not None and SPEC.loader is not None
example = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(example)


class ResearcherAlphaExampleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.original = self.directory / "original.json"
        self.project_path = self.directory / "project.json"
        self.original.write_bytes((CORPUS / "staged-input.json").read_bytes())
        self.options = {"project_id": "alpha.software", "title": "Artificial engineering reference",
                        "version": "1", "reuse_terms": "Project-owned artificial software declarations"}
        for target in ("subprocess.Popen", "socket.socket", "os.system", "os.posix_spawn"):
            guard = patch(target, side_effect=AssertionError("Pure example tests cannot execute or use the network"))
            guard.start()
            self.addCleanup(guard.stop)

    def prepare(self):
        return example.prepare(self.original, self.project_path, **self.options)

    def test_both_complete_originals_survive_prepare_and_inert_preflight(self):
        for name in ("staged-input.json", "comparison-input.json"):
            with self.subTest(case=name):
                raw = (CORPUS / name).read_bytes()
                self.original.write_bytes(raw)
                destination = self.directory / (name + ".project")
                with patch.object(CoreClient, "call", side_effect=AssertionError("Preflight must be inert")):
                    project = example.prepare(self.original, destination, **self.options)
                    summary = example.preflight(destination)
                expected = json.loads(raw)
                self.assertEqual(project.request, expected["request"])
                self.assertEqual(project.limits, expected["limits"])
                self.assertEqual(project.data["sources"][0]["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(project.data["sources"][0]["locator"], "original.json")
                self.assertEqual(summary["project_sha256"], project.digest)
                self.assertEqual(summary["status"], "structurally_ready")
                self.assertEqual(summary["native_status"], "not_run")
                self.assertEqual(summary["biological_status"], "unassessed")
                self.assertEqual(summary["provenance_status"], "caller_declared")
                self.assertEqual(self.original.read_bytes(), raw)

    def test_prepare_rejects_input_output_aliases_without_changing_original(self):
        original = self.original.read_bytes()
        linked = self.directory / "linked.json"
        os.link(self.original, linked)
        symbolic = self.directory / "symbolic.json"
        symbolic.symlink_to(self.original)
        for destination in (self.original, linked, symbolic):
            with self.subTest(destination=destination.name), self.assertRaisesRegex(ValueError, "overwrite"):
                example.prepare(self.original, destination, **self.options)
        self.assertEqual(self.original.read_bytes(), original)

    def test_prepare_preserves_existing_destination(self):
        self.project_path.write_bytes(b"previous project")
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(self.project_path.read_bytes(), b"previous project")
        self.assertFalse(list(self.directory.glob(".research-project-*")))

    def test_prepare_rejects_nonregular_empty_and_symlink_inputs(self):
        empty = self.directory / "empty.json"
        empty.touch()
        symbolic = self.directory / "symlink.json"
        symbolic.symlink_to(self.original)
        fifo = self.directory / "fifo"
        os.mkfifo(fifo)
        for source in (self.directory, empty, symbolic, fifo):
            with self.subTest(source=source.name), self.assertRaises(ValueError):
                example.prepare(source, self.project_path, **self.options)
        self.assertFalse(self.project_path.exists())

    def test_reader_rejects_a_symlink_swap_at_open(self):
        other = self.directory / "replacement.json"
        other.write_text("{}")
        original_open = os.open

        def swapped(path, flags, *args, **kwargs):
            self.original.unlink()
            self.original.symlink_to(other)
            return original_open(path, flags, *args, **kwargs)

        with patch.object(example.os, "open", side_effect=swapped), self.assertRaises(OSError):
            self.prepare()
        self.assertFalse(self.project_path.exists())

    def test_reader_checks_file_type_after_open_without_blocking_fifo(self):
        fifo = self.directory / "fifo"
        os.mkfifo(fifo)
        with patch.object(Path, "is_file", return_value=True), self.assertRaisesRegex(ValueError, "regular"):
            example.prepare(fifo, self.project_path, **self.options)
        self.assertFalse(self.project_path.exists())

    def test_reader_detects_metadata_change_during_read(self):
        original_fstat = os.fstat
        calls = []

        def changed(descriptor):
            value = original_fstat(descriptor)
            calls.append(descriptor)
            if len(calls) == 2:
                return SimpleNamespace(st_dev=value.st_dev, st_ino=value.st_ino,
                    st_size=value.st_size, st_mtime_ns=value.st_mtime_ns + 1)
            return value

        with patch.object(example.os, "fstat", side_effect=changed), self.assertRaisesRegex(ValueError, "changed during"):
            self.prepare()
        self.assertEqual(len(calls), 2)
        self.assertFalse(self.project_path.exists())

    def test_oversize_is_rejected_before_decoding(self):
        with patch.object(example, "MAX_PROJECT_BYTES", 8), patch.object(example, "decode_json") as decode:
            with self.assertRaisesRegex(ValueError, "bounded"):
                self.prepare()
        decode.assert_not_called()
        self.assertFalse(self.project_path.exists())

    def test_malformed_incomplete_and_unsupported_originals_have_no_output(self):
        invalid = (b'{"request":{},"request":{},"limits":{}}', b'[]', b'null', b'{}',
                   b'{"request":null,"limits":{}}', b'{"request":{"sequence":"AUG"},"limits":{}}',
                   b'{"request":{},"limits":{},"expected":"invented"}', b'{broken')
        for raw in invalid:
            with self.subTest(raw=raw):
                self.original.write_bytes(raw)
                with self.assertRaises((ValueError, CoreProtocolError)):
                    self.prepare()
                self.assertFalse(self.project_path.exists())

    def test_default_compile_resolves_distinct_owned_core_and_verify_roles(self):
        self.prepare()
        core = CoreClient(self.directory / "unexecuted-core", role="core")
        verify = CoreClient(self.directory / "unexecuted-verify", role="verify")
        compiled = SimpleNamespace(executable="core", operation="compile-policy-component-material",
                                   status="checked_component_material", candidate={"untrusted": "candidate"})
        verified = SimpleNamespace(status="checked_component_material")
        producer = Mock()
        producer.compile.return_value = compiled
        destination = self.directory / "bundle.zip"
        with patch.object(api, "installed_core", side_effect=[core, verify]) as installed, \
                patch.object(api, "_client", return_value=producer) as client, \
                patch.object(api.component_material, "export", return_value=verified) as export:
            built = example.compile_project(self.project_path, destination)
        self.assertEqual(installed.call_args_list[0].kwargs,
            {"role": "core", "operation": "compile-policy-component-material", "timeout_seconds": 300.0})
        self.assertEqual(installed.call_args_list[1].kwargs,
            {"role": "verify", "operation": "export-policy-component-material", "timeout_seconds": 300.0})
        client.assert_called_once_with("component_material", core)
        self.assertIs(export.call_args.kwargs["client"].transport, verify)
        self.assertEqual(export.call_args.kwargs["input_paths"], (self.project_path.resolve(),))
        self.assertIs(built.compiled, compiled)
        self.assertIs(built.verified, verified)
        self.assertFalse(destination.exists(), "A mocked export is not real publication evidence")

    def test_verify_delegates_to_current_independent_project_with_owned_default(self):
        self.prepare()
        sentinel = object()
        bundle = self.directory / "bundle.zip"
        with patch.object(api.ResearchProject, "verify_bundle", autospec=True, return_value=sentinel) as verify:
            self.assertIs(example.verify_project(self.project_path, bundle), sentinel)
        project = verify.call_args.args[0]
        self.assertEqual(project._input_paths, (self.project_path.resolve(),))
        self.assertEqual(verify.call_args.args[1], bundle)
        self.assertEqual(verify.call_args.kwargs, {"verify": None})

    def test_cli_prepare_and_preflight_emit_scoped_json(self):
        create = ["prepare", str(self.original), str(self.project_path), "--project-id", self.options["project_id"],
                  "--title", self.options["title"], "--version", "1", "--reuse-terms", self.options["reuse_terms"]]
        for argv in (create, ["preflight", str(self.project_path)]):
            with self.subTest(command=argv[0]), redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(example.main(argv), 0)
            result = json.loads(stdout.getvalue())
            self.assertEqual((result["native_status"], result["biological_status"]), ("not_run", "unassessed"))

    def test_cli_compile_and_verify_keep_roles_and_scope_explicit(self):
        built = SimpleNamespace(project_sha256="a" * 64, output=self.directory / "bundle.zip",
                                verified=SimpleNamespace(status="checked_component_material"))
        verified = SimpleNamespace(status="checked_component_material", operation="export-policy-component-material", executable="verify")
        flags = ["--verify", str(self.directory / "verify"), "--verify-sha256", "b" * 64]
        with patch.object(example, "compile_project", return_value=built) as compile_call, \
                redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(example.main(["compile", str(self.project_path), str(built.output),
                "--core", str(self.directory / "core"), "--core-sha256", "a" * 64, *flags]), 0)
        self.assertEqual(compile_call.call_args.kwargs["core"].role, "core")
        self.assertEqual(compile_call.call_args.kwargs["verify"].role, "verify")
        self.assertEqual(json.loads(stdout.getvalue())["biological_status"], "unassessed")
        with patch.object(example, "verify_project", return_value=verified) as verify_call, \
                redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(example.main(["verify", str(self.project_path), str(built.output), *flags]), 0)
        self.assertEqual(verify_call.call_args.kwargs["verify"].expected_sha256, "b" * 64)
        self.assertEqual(json.loads(stdout.getvalue())["executable"], "verify")

    def test_cli_incomplete_explicit_transport_and_invalid_input_fail_cleanly(self):
        for flags in (["--core", str(self.directory / "core")], ["--core-sha256", "a" * 64]):
            with self.subTest(flags=flags), patch.object(example, "compile_project") as compile_call, \
                    redirect_stderr(io.StringIO()) as stderr, redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(example.main(["compile", "unused.json", "unused.zip", *flags]), 1)
            compile_call.assert_not_called()
            self.assertIn("matching SHA-256", stderr.getvalue())
            self.assertEqual(stdout.getvalue(), "")
        self.project_path.write_text("{}")
        with redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(example.main(["preflight", str(self.project_path)]), 1)
        self.assertIn("ResearchProjectError", stderr.getvalue())

    def test_cli_preserves_rejected_assessment_and_publishes_nothing(self):
        self.prepare()
        report = {"status": "not_accepted", "context_status": "fail", "empirical": "unassessed",
                  "diagnostics": [{"code": "synthetic_capacity_failure", "path": "context.providers",
                                   "message": "Synthetic retained assessment for CLI testing"}]}
        rejected = PolicyMaterialResult("synthetic", "compile-policy-component-material", "core",
            *(["a" * 64] * 4), encode_json({"report": report, "candidate": {}, "artifact": None}))
        producer = Mock()
        producer.compile.return_value = rejected
        transports = [CoreClient(self.directory / "core", role="core"),
                      CoreClient(self.directory / "verify", role="verify")]
        destination = self.directory / "rejected.zip"
        with patch.object(api, "installed_core", side_effect=transports), \
                patch.object(api, "_client", return_value=producer), \
                patch.object(api.component_material, "export") as publish, \
                redirect_stderr(io.StringIO()) as stderr, redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(example.main(["compile", str(self.project_path), str(destination)]), 1)
        self.assertEqual(json.loads(stderr.getvalue()), {"status": "not_accepted", "report": report,
            "artifact": "absent", "biological_status": "unassessed"})
        self.assertEqual(stdout.getvalue(), "")
        producer.compile.assert_called_once()
        publish.assert_not_called()
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
