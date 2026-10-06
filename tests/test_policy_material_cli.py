"""Material CLI routing and publication boundaries without native execution."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from biocompiler.core_client import CoreProtocolError
from biocompiler.core_policy_material import RESULT_SCHEMA
from biocompiler.entrypoint import main


class PolicyMaterialCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.request = {"schema_version": "test.original.realization", "untouched": [True, 1]}
        self.limits = {"explicit": 100}
        self.candidate = {"schema_version": "test.untrusted.candidate", "body": [1, False]}
        self.saved = {"schema_version": RESULT_SCHEMA, "candidate": self.candidate,
                      "report": {"status": "checked_material"}, "original": "complete-wrapper"}
        self.paths = {}
        for name, value in (("request", self.request), ("limits", self.limits),
                            ("candidate", self.saved), ("report", self.saved)):
            path = self.root / (name + ".json")
            path.write_text(json.dumps(value))
            self.paths[name] = path

    def invoke(self, command, *, status="checked_material", error=None, output=None):
        arguments = ["policy", command, str(self.paths["request"]), "--json",
                     "--limits", str(self.paths["limits"])]
        compile_operation = command == "compile-material-native"
        arguments += ["--core" if compile_operation else "--verify", "/explicit/native"]
        if not compile_operation:
            arguments += ["--candidate", str(self.paths["candidate"])]
        if command == "replay-material-native":
            arguments += ["--report", str(self.paths["report"])]
        if output is not None:
            arguments += ["--output", str(output), "--replace"]
        out, err = io.StringIO(), io.StringIO()
        with patch("biocompiler.core_client.CoreClient") as transport, \
             patch("biocompiler.core_policy_material.PolicyMaterialClient") as adapter, \
             patch("biocompiler.policy.serialization.load", side_effect=AssertionError("Envelope is not an authoring document")), \
             redirect_stdout(out), redirect_stderr(err):
            method = {"compile-material-native": "compile", "check-material-native": "check",
                      "replay-material-native": "replay"}[command]
            call = getattr(adapter.return_value, method)
            call.return_value = SimpleNamespace(result=self.saved, status=status)
            call.side_effect = error
            code = main(arguments)
        return code, out.getvalue(), err.getvalue(), transport, call

    def test_original_envelope_reaches_compile_without_authoring_or_execution(self):
        code, output, error, transport, call = self.invoke("compile-material-native")
        self.assertEqual((code, error), (0, ""))
        self.assertEqual(json.loads(output), self.saved)
        call.assert_called_once_with(self.request, self.limits)
        self.assertEqual(transport.call_args.kwargs["role"], "core")

    def test_verify_extracts_candidate_but_replays_entire_saved_wrapper(self):
        for command in ("check-material-native", "replay-material-native"):
            with self.subTest(command=command):
                code, output, error, transport, call = self.invoke(command)
                self.assertEqual((code, error), (0, ""), output)
                expected = (self.request, self.candidate, self.limits)
                if command == "replay-material-native":
                    expected += (self.saved,)
                call.assert_called_once_with(*expected)
                self.assertEqual(transport.call_args.kwargs["role"], "verify")

    def test_returned_nonacceptance_has_nonzero_exit_and_keeps_evidence(self):
        for status in ("incomplete", "requirements_not_satisfied"):
            with self.subTest(status=status):
                code, output, error, _, _ = self.invoke("check-material-native", status=status)
                self.assertEqual((code, error), (1, ""))
                self.assertEqual(json.loads(output), self.saved)

    def test_transport_failure_preserves_prior_output_and_has_no_fallback(self):
        destination = self.root / "prior.json"
        destination.write_text("preserve this evidence")
        code, output, error, _, call = self.invoke("compile-material-native",
            error=CoreProtocolError("native response refused"), output=destination)
        self.assertEqual((code, output), (2, ""))
        self.assertEqual(json.loads(error)["status"], "error")
        self.assertEqual(destination.read_text(), "preserve this evidence")
        self.assertEqual(call.call_count, 1)

    def test_malformed_or_duplicate_inputs_never_reach_native_operation(self):
        for text in ('{"schema_version":"' + RESULT_SCHEMA + '"}', '{"x":1,"x":2}'):
            with self.subTest(text=text):
                self.paths["candidate"].write_text(text)
                code, output, error, _, call = self.invoke("check-material-native")
                self.assertEqual((code, output), (2, ""))
                self.assertEqual(json.loads(error)["status"], "error")
                call.assert_not_called()

    def test_complete_result_publication_cannot_replace_original_authority(self):
        original = self.paths["request"].read_bytes()
        code, output, error, _, _ = self.invoke("compile-material-native", output=self.paths["request"])
        self.assertEqual((code, output), (2, ""))
        self.assertIn("must not replace an input", json.loads(error)["message"])
        self.assertEqual(self.paths["request"].read_bytes(), original)

    def test_export_uses_fresh_helper_and_never_rewrites_archive_as_json(self):
        destination = self.root / "rna.zip"
        out, err = io.StringIO(), io.StringIO()
        arguments = ["policy", "export-material-native", str(self.paths["request"]), "--json",
                     "--verify", "/explicit/native", "--limits", str(self.paths["limits"]),
                     "--candidate", str(self.paths["candidate"]), "--output", str(destination), "--replace"]

        def publish(request, **kwargs):
            self.assertEqual(request, self.request)
            self.assertEqual(kwargs["candidate"], self.candidate)
            self.assertEqual(kwargs["limits"], self.limits)
            self.assertEqual(kwargs["input_paths"], (self.paths["request"], self.paths["limits"], self.paths["candidate"]))
            self.assertTrue(kwargs["replace"])
            kwargs["output"].write_bytes(b"native-checked-paired-archive")
            return SimpleNamespace(result=self.saved, status="checked_material")

        with patch("biocompiler.core_client.CoreClient"), \
             patch("biocompiler.core_policy_material.PolicyMaterialClient"), \
             patch("biocompiler.policy.material.export", side_effect=publish) as exporter, \
             patch("biocompiler.policy.serialization.load", side_effect=AssertionError("No authoring fallback")), \
             patch("biocompiler.policy.cli._write", side_effect=AssertionError("Archive was replaced with JSON")), \
             redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(main(arguments), 0)
        self.assertEqual(destination.read_bytes(), b"native-checked-paired-archive")
        self.assertEqual(exporter.call_count, 1)
        self.assertEqual(json.loads(out.getvalue())["format"], "RNA_FASTA_and_canonical_manifest_zip")
        self.assertEqual(err.getvalue(), "")

    def test_export_requires_companion_archive_destination(self):
        arguments = ["policy", "export-material-native", str(self.paths["request"]),
                     "--verify", "/explicit/native", "--limits", str(self.paths["limits"]),
                     "--candidate", str(self.paths["candidate"])]
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            main(arguments)
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
