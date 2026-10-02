"""Complete evidence comparator tests: no native program is executed."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import check_workflow_reproducibility as r

REVISION = "a" * 40
SOURCE = "b" * 40
RUN = "77"


class WorkflowReproducibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = r.Golden()

    def test_production_matrix_retains_every_original_occurrence_and_both_roles(self):
        self.assertEqual(len(self.full.cases), 112)
        expected = self.full.expected()
        self.assertEqual(len(expected), 224)
        self.assertEqual({key[0] for key in expected}, {"core", "verify"})
        original = [case for case in self.full.cases if case["origin"] == "original"]
        self.assertEqual(len(original), 89)
        self.assertEqual(len({case["id"] for case in original}), 52)
        self.assertEqual({(r.decode(case["authority"])["operation"], r.decode(case["authority"])["mode"])
                          for case in self.full.cases if case["origin"] == "supplemental"},
                         {(operation, mode) for operation in ("check", "explore", "reduce")
                          for mode in ("candidate", "model")})

    def small(self):
        # Mutation tests keep full independently captured reports for every
        # operation/mode pair. The production census above covers every call.
        golden = object.__new__(r.Golden)
        golden.profile = deepcopy(self.full.profile)
        selected = []
        for operation in ("check", "explore", "reduce"):
            for mode in ("candidate", "model"):
                selected.append(next(case for case in self.full.cases if case["origin"] == "supplemental" and
                    case["phase"] == "run" and r.decode(case["authority"])["operation"] == operation and
                    r.decode(case["authority"])["mode"] == mode))
        selected.append(next(case for case in self.full.cases if case["origin"] == "original" and case["error"] is not None))
        selected.extend(case for case in self.full.cases if case["origin"] in ("normalization", "resource", "authority_precedence"))
        # A successful reduction is independently checked through the receipt,
        # not just through expected resource failures.
        reduced = deepcopy(selected[0])
        reduced.update(id="focused/all-five-reductions", phase="run", origin="resource", limits={
            "max_work": 1_000_000_000_000, "max_monitor_items": 7_000_000,
            "max_request_bytes": 16_777_216, "max_report_bytes": 1_048_576, "max_report_nodes": 100_000})
        selected.append(reduced)
        golden.cases = deepcopy(selected)
        return golden

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.canonical(value) + b"\n")

    def fixture(self, directory):
        root, natives = Path(directory) / "realization", Path(directory) / "native"
        golden = self.small()
        for target, (system, machine) in r.PLATFORMS.items():
            native = natives / target
            native.mkdir(parents=True)
            pins = {}
            for role in r.ROLES:
                name = "biocompiler-" + role
                raw = (target + "/" + name + "/nonexecutable-test-bytes").encode()
                (native / name).write_bytes(raw)
                pins[name] = hashlib.sha256(raw).hexdigest()
            self.write(native / "binaries.json", {"revision": REVISION, "system": system, "machine": machine, "sha256": pins})
            inputs = r.verify_binaries(native, REVISION, target)
            for python in r.PYTHONS:
                slot = root / ("realization-" + target + "-py" + python)
                self.write(slot / "native-inputs.json", {**inputs, "run_id": RUN, "source_revision": SOURCE,
                                                         "python_version": python + ".9"})
                artifact_directory = slot / "workflow-artifacts"
                artifact_directory.mkdir()
                values, checks = {}, []

                def artifact(raw):
                    if raw is None:
                        return None
                    identity = hashlib.sha256(raw).hexdigest()
                    (artifact_directory / (identity + ".bin")).write_bytes(raw)
                    values[identity] = {"path": identity + ".bin", "bytes": len(raw), "sha256": identity}
                    return identity

                for (role, _identity, _phase, _operation), case in golden.expected().items():
                    request_id = r.request_identity(role, case)
                    item = {key: case[key] for key in ("id", "phase", "origin", "operation", "limits")}
                    item.update(role=role, request_id=request_id, guard_modules=sorted(r.TRANSPORT_MODULES),
                        authority=artifact(case["authority"]), retained=artifact(case["retained"]),
                        expected=artifact(case["expected"]),
                        source_evidence=artifact(None if case["source_evidence"] is None else r.canonical(case["source_evidence"])))
                    envelope = {"protocol": "biocompiler.core.v1", "request_id": request_id,
                        "operation": case["operation"], "core": {"implementation": "ocaml", "version": "0.1.0",
                        "protocol": "biocompiler.core.v1", "executable": role}}
                    if case["error"] is not None:
                        item.update(status="error", diagnostic=case["error"], record=None, semantic_receipt=None)
                        envelope.update(status="error", diagnostics=[case["error"]], result=None)
                    else:
                        authority, record = r.decode(case["authority"]), r.decode(case["expected"])
                        receipt = {
                            "schema_version": "biocompiler.core.verification_workflow_result.v1",
                            "profile": golden.profile["profile"], "operation": case["operation"],
                            "request_id": request_id, "executable": role,
                            "validation_scope": "complete_fresh_verification_workflow",
                            "implementation_version": "biocompiler.ocaml.verification_workflow_service.v0.1",
                            "workflow_version": "biocompiler.synthetic_verification_workflow.v0.1",
                            "workflow_operation": authority["operation"], "mode": authority["mode"],
                            "authority_fingerprint": r.digest(authority), "request_fingerprint": r.digest(record["request"]),
                            "retained_record_fingerprint": None if case["retained"] is None else r.digest(r.decode(case["retained"])),
                            "record_fingerprint": hashlib.sha256(case["expected"]).hexdigest(),
                            "resources": r.effective_resources(golden.profile, case["limits"])}
                        result = {"schema_version": "biocompiler.core.artifact_response.v1",
                            "transport": "biocompiler.core.artifact_transport.v1", "authority": r.descriptor(case["authority"]),
                            "retained_record": r.descriptor(case["retained"]), "artifact": r.descriptor(case["expected"]), "result": receipt}
                        item.update(status="ok", diagnostic=None, record=artifact(case["expected"]),
                                    semantic_receipt=artifact(r.canonical(receipt)))
                        envelope.update(status="ok", diagnostics=[], result=result)
                    item["envelope"] = artifact(r.canonical(envelope))
                    checks.append(item)
                receipt = {"schema_version": "biocompiler.native_workflow_conformance.v1", "status": "success",
                    "scope": "complete_native_workflow_sdk_run_replay_only_public_cli_and_pipeline_unmigrated",
                    "revision": REVISION, "source_revision": SOURCE, "run_id": RUN, "system": system, "machine": machine,
                    "native_platform": target, "python_version": python + ".9", "native_inputs": inputs,
                    "package_path": "/installed/site-packages/biocompiler/__init__.py", "corpus_pin": r.CORPUS_PIN,
                    "supplemental_pin": r.SUPPLEMENTAL_PIN, "profile_pin": r.PROFILE_PIN,
                    "transport_sources": r.source_pins("src/" + name.replace(".", "/") + ".py" for name in sorted(r.TRANSPORT_MODULES)),
                    "campaign_sources": r.source_pins(("tools/check_native_workflow.py", "tests/test_native_workflow_campaign.py")),
                    "checks": checks, "completed_checks": len(checks), "artifacts": values, "artifact_directory": "workflow-artifacts"}
                self.write(slot / "workflow.json", receipt)
        return root, natives, golden

    def compare(self, root, natives, golden):
        with patch.object(r, "Golden", return_value=golden):
            return r.compare(root, natives, revision=REVISION, source_revision=SOURCE, run_id=RUN)

    def test_complete_four_way_records_and_exact_metadata_reject_stale_missing_or_weakened_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root, natives, golden = self.fixture(directory)
            result = self.compare(root, natives, golden)
            self.assertEqual(result["status"], "success")
            self.assertEqual(len(result["receipts"]), 4)
            path = root / "realization-linux-x86_64-py3.11" / "workflow.json"
            original = json.loads(path.read_bytes())
            mutations = (
                lambda value: value.update(revision="c" * 40),
                lambda value: value.update(source_revision="d" * 40),
                lambda value: value.update(run_id="stale"),
                lambda value: value.update(python_version="3.14.9"),
                lambda value: value.update(native_platform="macos-arm64"),
                lambda value: value.update(status="failure"),
                lambda value: value["checks"].pop(),
                lambda value: value["checks"].append(deepcopy(value["checks"][0])),
                lambda value: value["checks"][0].update(request_id="unbound"),
                lambda value: value["checks"][0].update(guard_modules=["biocompiler.core_client"]),
                lambda value: value["checks"][0].update(phase="missing-original"),
                lambda value: value.update(artifact_directory="../outside"),
                lambda value: value["native_inputs"]["sha256"].update({"biocompiler-verify": "0" * 64}),
                lambda value: value["transport_sources"].update({"src/biocompiler/core_workflow.py": "0" * 64}),
            )
            for mutation in mutations:
                changed = deepcopy(original)
                mutation(changed)
                self.write(path, changed)
                with self.assertRaises(AssertionError):
                    self.compare(root, natives, golden)
            self.write(path, original)
            fourth = root / "realization-macos-arm64-py3.14" / "native-inputs.json"
            fourth.unlink()
            with self.assertRaises(AssertionError):
                self.compare(root, natives, golden)

    def test_full_rehashed_forgeries_and_changed_error_signatures_do_not_become_original_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root, natives, golden = self.fixture(directory)
            slot = root / "realization-linux-x86_64-py3.11"
            path = slot / "workflow.json"
            original = json.loads(path.read_bytes())
            for kind in ("record", "semantic_receipt", "envelope"):
                receipt = deepcopy(original)
                item = next(check for check in receipt["checks"] if check["status"] == "ok")
                old = item[kind]
                old_path = slot / "workflow-artifacts" / (old + ".bin")
                original_bytes = old_path.read_bytes()
                document = json.loads(original_bytes)
                if kind == "record":
                    document["claim_scope"] = "forged universal acceptance"
                elif kind == "semantic_receipt":
                    document["resources"]["workflow"]["max_work"] -= 1
                else:
                    document["core"]["executable"] = "verify"
                raw = r.canonical(document)
                new = hashlib.sha256(raw).hexdigest()
                new_path = old_path.with_name(new + ".bin")
                new_path.write_bytes(raw)
                for check in receipt["checks"]:
                    for field in ("record", "retained", "expected", "semantic_receipt", "envelope"):
                        if check[field] == old:
                            check[field] = new
                del receipt["artifacts"][old]
                old_path.unlink()
                receipt["artifacts"][new] = {"path": new + ".bin", "bytes": len(raw), "sha256": new}
                self.write(path, receipt)
                with self.assertRaises(AssertionError):
                    self.compare(root, natives, golden)
                new_path.unlink()
                old_path.write_bytes(original_bytes)
            receipt = deepcopy(original)
            next(check for check in receipt["checks"] if check["status"] == "error")["diagnostic"]["message"] += " changed"
            self.write(path, receipt)
            with self.assertRaisesRegex(AssertionError, "rejection"):
                self.compare(root, natives, golden)

    def test_rehashes_actual_binary_and_artifact_bytes_rejecting_symlinks_and_extra_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root, natives, golden = self.fixture(directory)
            slot = root / "realization-linux-x86_64-py3.11"
            receipt = json.loads((slot / "workflow.json").read_bytes())
            identity = next(iter(receipt["artifacts"]))
            path = slot / "workflow-artifacts" / (identity + ".bin")
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with self.assertRaisesRegex(AssertionError, "bytes differ"):
                self.compare(root, natives, golden)
            path.unlink()
            path.symlink_to(slot / "workflow.json")
            with self.assertRaisesRegex(AssertionError, "symlinked"):
                self.compare(root, natives, golden)
            path.unlink()
            path.write_bytes(original)
            extra = slot / "workflow-artifacts" / ("0" * 64 + ".bin")
            extra.write_bytes(b"{}")
            with self.assertRaisesRegex(AssertionError, "extra"):
                self.compare(root, natives, golden)
            extra.unlink()
            binary = natives / "macos-arm64" / "biocompiler-verify"
            binary.write_bytes(binary.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "bytes differ"):
                self.compare(root, natives, golden)


if __name__ == "__main__":
    unittest.main()
