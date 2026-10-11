"""Standalone CAR CLI orchestration only; no native or biological acceptance."""
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.core_client import CoreClient, CoreTransportError, encode_json
from biocompiler.core_policy_material import PolicyMaterialResult
from biocompiler.policy.car_reference import rm61461_request
from biocompiler.policy import research_project as api


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("car_payload_example", ROOT / "examples/car_payload.py")
assert SPEC is not None and SPEC.loader is not None
example = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(example)


class CarPayloadExampleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.project_path = self.directory / "car.project.json"
        self.output = self.directory / "car.payload.zip"
        for target in ("subprocess.Popen", "socket.socket", "os.system", "os.posix_spawn"):
            guard = patch(target, side_effect=AssertionError("Pure CLI controls cannot execute or use the network"))
            guard.start()
            self.addCleanup(guard.stop)

    def prepare(self, maximum=1776, destination=None):
        return example.prepare(destination or self.project_path, maximum_rna_nt=maximum,
                               three_prime_end="designer_supplied_hydroxyl")

    def test_prepare_preserves_complete_typed_reference_and_preflight_is_inert(self):
        expected = rm61461_request(maximum_rna_nt=1776, three_prime_end="designer_supplied_hydroxyl")
        with patch.object(CoreClient, "call", side_effect=AssertionError("Preparation and preflight must be inert")):
            project = self.prepare()
            summary = example.preflight(self.project_path)
        loaded = api.ResearchProject.load(self.project_path)
        self.assertEqual(loaded.expression.to_request(), expected.to_request())
        self.assertEqual(self.project_path.read_bytes(), encode_json(project.data))
        self.assertEqual(loaded.data["schema_version"], "biocompiler.research_project.v0.2")
        self.assertIsNone(loaded.data["limits"])
        self.assertEqual(summary, {
            "project_sha256": project.digest, "route": "expression_material", "source_count": 4,
            "status": "structurally_ready", "native_status": "not_run",
            "biological_status": "unassessed", "provenance_status": "caller_declared",
        })

    def test_prepare_requires_explicit_end_and_bound_and_rejects_invalid_choices(self):
        for flags in ([], ["--max-rna-nt", "1776"],
                      ["--three-prime-end", "designer_supplied_hydroxyl"],
                      ["--max-rna-nt", "1776", "--three-prime-end", "source_verified_hydroxyl"],
                      ["--max-rna-nt", "1.5", "--three-prime-end", "designer_supplied_hydroxyl"]):
            with self.subTest(flags=flags), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as rejected:
                example.main(["prepare", str(self.project_path), *flags])
            self.assertEqual(rejected.exception.code, 2)
            self.assertFalse(self.project_path.exists())
        for maximum in (0, -1, 1_000_001, True):
            with self.subTest(maximum=maximum), self.assertRaises(ValueError):
                self.prepare(maximum)
        with self.assertRaises(TypeError):
            example.prepare(self.project_path, maximum_rna_nt=1776)

    def test_changed_bound_changes_original_authority_without_rewriting_material(self):
        original = self.prepare()
        changed = self.prepare(1775, self.directory / "short.project.json")
        self.assertNotEqual(original.digest, changed.digest)
        left, right = original.request, changed.request
        self.assertEqual(left["structure_authority"], right["structure_authority"])
        self.assertEqual(left["expression_contract"], right["expression_contract"])
        self.assertEqual(left["project_context"], right["project_context"])
        self.assertNotEqual(left["document"], right["document"])
        self.assertEqual(changed.preflight().native_status, "not_run")

    def test_existing_project_and_one_sided_metadata_edits_are_preserved_or_rejected(self):
        self.prepare()
        before = self.project_path.read_bytes()
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.assertEqual(self.project_path.read_bytes(), before)
        data = json.loads(before)
        data["sources"][0]["sha256"] = "0" * 64
        self.project_path.write_bytes(encode_json(data))
        with redirect_stderr(io.StringIO()) as stderr, redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(example.main(["preflight", str(self.project_path)]), 1)
        self.assertIn("metadata", stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "")

    def test_temporal_project_cannot_silently_select_a_different_route(self):
        original = json.loads((ROOT / "data/researcher_alpha/staged-input.json").read_bytes())
        project = api.ResearchProject.from_request(project_id="inert.legacy", title="Legacy software control",
            request=original["request"], limits=original["limits"], sources=[api.SourceRecord(
                "inert", "unused", "1", "a" * 64, "artificial_control", "test-owned")], assumptions=[])
        project.dump(self.project_path)
        with patch.object(api.ResearchProject, "compile") as compile_call, \
                patch.object(api.ResearchProject, "verify_bundle") as verify_call:
            for operation in (lambda: example.preflight(self.project_path),
                              lambda: example.compile_project(self.project_path, self.output),
                              lambda: example.verify_project(self.project_path, self.output)):
                with self.assertRaises(api.ResearchProjectError):
                    operation()
        compile_call.assert_not_called()
        verify_call.assert_not_called()

    def test_compile_and_verify_delegate_current_expression_originals_and_roles(self):
        original = self.prepare()
        core = CoreClient(self.directory / "core", role="core", expected_sha256="a" * 64)
        verify = CoreClient(self.directory / "verify", role="verify", expected_sha256="b" * 64)
        sentinel = object()
        with patch.object(api.ResearchProject, "compile", autospec=True, return_value=sentinel) as compile_call:
            self.assertIs(example.compile_project(self.project_path, self.output, core=core, verify=verify), sentinel)
        loaded = compile_call.call_args.args[0]
        self.assertEqual(loaded.data, original.data)
        self.assertEqual(compile_call.call_args.kwargs, {"output": self.output, "core": core, "verify": verify})
        with patch.object(api.ResearchProject, "verify_bundle", autospec=True, return_value=sentinel) as verify_call:
            self.assertIs(example.verify_project(self.project_path, self.output), sentinel)
        self.assertEqual(verify_call.call_args.args[0].data, original.data)
        self.assertEqual(verify_call.call_args.args[1], self.output)
        self.assertEqual(verify_call.call_args.kwargs, {"verify": None})
        self.assertFalse(self.output.exists(), "Delegation mocks cannot establish publication")

    def test_cli_prepare_and_preflight_report_scoped_readiness(self):
        for argv in (["prepare", str(self.project_path), "--max-rna-nt", "1776",
                      "--three-prime-end", "designer_supplied_hydroxyl"],
                     ["preflight", str(self.project_path)]):
            with self.subTest(command=argv[0]), redirect_stdout(io.StringIO()) as stdout:
                self.assertEqual(example.main(argv), 0)
            self.assertEqual(json.loads(stdout.getvalue())["native_status"], "not_run")
            self.assertEqual(json.loads(stdout.getvalue())["biological_status"], "unassessed")

    def test_cli_compile_and_verify_keep_exact_explicit_roles_and_unassessed_scope(self):
        built = SimpleNamespace(project_sha256="c" * 64, output=self.output,
                                verified=SimpleNamespace(status="checked_expression_material"))
        verified = SimpleNamespace(status="checked_expression_material", operation="export-policy-expression-material", executable="verify")
        flags = ["--verify", str(self.directory / "verify"), "--verify-sha256", "b" * 64]
        with patch.object(example, "compile_project", return_value=built) as compile_call, redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(example.main(["compile", str(self.project_path), str(self.output),
                "--core", str(self.directory / "core"), "--core-sha256", "a" * 64, *flags]), 0)
        self.assertEqual((compile_call.call_args.kwargs["core"].role, compile_call.call_args.kwargs["verify"].role), ("core", "verify"))
        self.assertEqual(compile_call.call_args.kwargs["core"].expected_sha256, "a" * 64)
        self.assertEqual(json.loads(stdout.getvalue())["biological_status"], "unassessed")
        with patch.object(example, "verify_project", return_value=verified) as verify_call, redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(example.main(["verify", str(self.project_path), str(self.output), *flags]), 0)
        self.assertEqual(verify_call.call_args.kwargs["verify"].expected_sha256, "b" * 64)
        self.assertEqual(json.loads(stdout.getvalue()), {"status": "checked_expression_material",
            "operation": "export-policy-expression-material", "executable": "verify", "biological_status": "unassessed"})

    def test_cli_default_resolution_and_partial_explicit_selections_are_closed(self):
        built = SimpleNamespace(project_sha256="c" * 64, output=self.output,
                                verified=SimpleNamespace(status="checked_expression_material"))
        with patch.object(example, "compile_project", return_value=built) as compile_call, redirect_stdout(io.StringIO()):
            self.assertEqual(example.main(["compile", str(self.project_path), str(self.output)]), 0)
        self.assertEqual(compile_call.call_args.kwargs, {"core": None, "verify": None})
        for command, flag in (("compile", "core"), ("compile", "verify"), ("verify", "verify")):
            for selection in (["--" + flag, "unused"], ["--" + flag + "-sha256", "a" * 64]):
                with self.subTest(command=command, selection=selection), \
                        patch.object(example, "compile_project") as compile_call, \
                        patch.object(example, "verify_project") as verify_call, \
                        redirect_stderr(io.StringIO()) as stderr, redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(example.main([command, str(self.project_path), str(self.output), *selection]), 1)
                compile_call.assert_not_called()
                verify_call.assert_not_called()
                self.assertIn("matching SHA-256", stderr.getvalue())
                self.assertEqual(stdout.getvalue(), "")

    def test_cli_nonaccepted_assessment_retains_diagnostics_without_publication(self):
        report = {"status": "not_accepted", "empirical": "unassessed", "diagnostics": [
            {"code": "synthetic_length_failure", "path": "document.maximum_rna_nt", "message": "Inert CLI control"}]}
        result = PolicyMaterialResult("synthetic", "compile-policy-expression-material", "core",
            *(["a" * 64] * 4), encode_json({"report": report, "candidate": {}, "artifact": None}))
        with patch.object(example, "compile_project", side_effect=api.ResearchProjectRejected(result)), \
                redirect_stderr(io.StringIO()) as stderr, redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(example.main(["compile", str(self.project_path), str(self.output)]), 1)
        self.assertEqual(json.loads(stderr.getvalue()), {"status": "not_accepted", "report": report,
            "artifact": "absent", "biological_status": "unassessed"})
        self.assertEqual(stdout.getvalue(), "")
        self.assertFalse(self.output.exists())

    def test_cli_transport_failure_does_not_report_success_or_overwrite_files(self):
        self.prepare()
        before = self.project_path.read_bytes()
        self.output.write_bytes(b"existing caller artifact")
        with patch.object(example, "verify_project", side_effect=CoreTransportError("Inert Verify failure")), \
                redirect_stderr(io.StringIO()) as stderr, redirect_stdout(io.StringIO()) as stdout:
            self.assertEqual(example.main(["verify", str(self.project_path), str(self.output)]), 1)
        self.assertIn("Inert Verify failure", stderr.getvalue())
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(self.project_path.read_bytes(), before)
        self.assertEqual(self.output.read_bytes(), b"existing caller artifact")


if __name__ == "__main__":
    unittest.main()
