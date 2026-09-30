"""The rename must not relabel historical artifact authority or biological pins."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import unittest

import biocompiler as bc
from biocompiler.cli import main as cli_main
from biocompiler.registry.reference_builds import MANIFEST_PIN, REFERENCE_PINS
from biocompiler.registry.references import load_reference_manifest
from examples.human_acceptance import make_human_acceptance


class NamespaceMigrationTests(unittest.TestCase):
    def test_cli_and_base_exception_use_current_name(self):
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as result:
            cli_main(["--version"])
        self.assertEqual(result.exception.code, 0)
        self.assertEqual(output.getvalue().strip(), f"biocompiler {bc.__version__}")
        self.assertTrue(issubclass(bc.SerializationError, bc.BiocompilerError))

    def test_historical_namespace_rejected_at_outer_and_nested_boundaries(self):
        request = make_human_acceptance()
        for keys in (
            (),
            ("deployment_request",),
            ("deployment_request", "behavior_request", "build_request", "target"),
        ):
            data = request.to_dict()
            node = data
            for key in keys:
                node = node[key]
            node["schema_version"] = node["schema_version"].replace(
                "biocompiler.", "cellweave."
            )
            with self.assertRaises(bc.SerializationError):
                bc.HumanAcceptanceRequest.from_dict(data)

    def test_migrated_manifest_retains_independent_sequence_record_identities(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "data/references/fap_car/manifest.json"
        )
        manifest = load_reference_manifest(
            path, expected_fingerprint=MANIFEST_PIN.content_fingerprint
        )
        for pin in REFERENCE_PINS.values():
            self.assertEqual(
                manifest.record(pin.id).fingerprint, pin.content_fingerprint
            )
        with self.assertRaisesRegex(bc.SerializationError, "lock mismatch"):
            load_reference_manifest(
                path,
                expected_fingerprint="8d26e8d3e960d8dc0996e1f0582372ddfc9685795ed54131557f101be8849a41",
            )


if __name__ == "__main__":
    unittest.main()
