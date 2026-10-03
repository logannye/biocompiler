"""Installed SDK campaign and evidence comparator tests use Python fixtures only."""
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from tools import check_native_workflow_public_sdk as r

REVISION, SOURCE, RUN = "a" * 40, "b" * 40, "77"


class WorkflowPublicSdkCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = r.Golden()
        cls.corpus = object.__new__(r.Corpus)
        cls.corpus.profile, cls.corpus._cases = cls.full.profile, cls.full.cases
        cls.cache_directory = tempfile.TemporaryDirectory()
        cls.cached = None

    @classmethod
    def tearDownClass(cls):
        cls.cache_directory.cleanup()

    def test_every_original_occurrence_and_all_input_forms_are_explicit(self):
        cases = self.full.cases
        self.assertEqual(len(cases), 164)
        self.assertEqual(len(self.full.expected()), 328)
        original = [case for case in cases if case["origin"] == "original"]
        self.assertEqual(len(original), 89)
        self.assertEqual(len({case["id"] for case in original}), 52)
        self.assertEqual(Counter(case["input_kind"] for case in cases),
                         {"bytes": 110, "mapping": 18, "typed": 18, "native": 18})
        self.assertTrue(all(case["limits"] is None for case in cases))
        for kind in ("mapping", "typed", "native"):
            selected = [case for case in cases if case["input_kind"] == kind]
            self.assertEqual({(r.decode(case["authority"])["operation"], r.decode(case["authority"])["mode"])
                              for case in selected}, {(op, mode) for op in ("check", "explore", "reduce")
                                                     for mode in ("candidate", "model")})

    @contextmanager
    def exchanges(self, corrupt=False):
        from biocompiler.core_client import CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL
        from biocompiler.core_artifacts import TRANSPORT_PROFILE
        positions = Counter()
        def response(request, role, value, diagnostic=None):
            return r.canonical({"protocol": PROTOCOL, "request_id": request["request_id"], "operation": request["operation"],
                "status": "ok" if diagnostic is None else "error", "result": value,
                "diagnostics": [] if diagnostic is None else [diagnostic],
                "core": {"implementation": "ocaml", "version": CORE_VERSION, "protocol": PROTOCOL, "executable": role}}), (0 if diagnostic is None else 2)
        def negotiate(path, raw, _timeout, _cancelled):
            role = "verify" if str(path).endswith("verify") else "core"
            request = json.loads(raw)
            value = {"schema_version": CAPABILITIES_SCHEMA, "operations": ["capabilities", *r.c.OPERATIONS.values()],
                "intent_schemas": [], "canonicalization": "python-json-v1", "limits": LIMITS,
                "validation_scopes": [self.corpus.profile["validation_scope"]], "claim_scope": "Transport fixture only.",
                "profiles": {"artifact_transport": TRANSPORT_PROFILE, "verification_workflow_presentation": self.corpus.profile}}
            return response(request, role, value)
        def exchange(core, raw, _arguments, files, output, _limit, _cancelled):
            request = json.loads(raw)
            case = self.full.cases[positions[core.role]]
            positions[core.role] += 1
            self.assertEqual(request["operation"], case["operation"])
            self.assertEqual(request["payload"]["operation_payload"], {"profile": self.corpus.profile["profile"],
                "limits": None, "command": None})
            authority = files[0].read()
            retained = None if case["retained"] is None else files[1].read()
            self.assertEqual(r.canonical(r.decode(authority)), r.canonical(r.decode(case["authority"])))
            self.assertEqual(retained is None, case["retained"] is None)
            if retained is not None:
                if case["input_kind"] == "typed":
                    self.assertEqual(r.canonical(r.decode(retained)), r.canonical(r.decode(case["retained"])))
                else:
                    self.assertEqual(retained, case["retained"])
            if case["error"] is not None:
                return response(request, core.role, None, case["error"])
            record = case["expected"]
            if corrupt:
                value = json.loads(record); value["claim_scope"] += " changed"
                record = r.canonical(value)
            output.write(record); output.flush()
            receipt = r.expected_semantic(self.corpus.profile, core.role, case, case["expected"], request["request_id"])
            receipt["record_fingerprint"] = r.c.sha(record)
            value = {"schema_version": "biocompiler.core.artifact_response.v1", "transport": "biocompiler.core.artifact_transport.v1",
                "authority": r.descriptor(authority), "retained_record": r.descriptor(retained),
                "artifact": r.descriptor(record), "result": receipt}
            return response(request, core.role, value)
        with patch("biocompiler.core_client._exchange", side_effect=negotiate), \
             patch("biocompiler.core_artifacts._exchange_artifacts", side_effect=exchange):
            yield

    def generate(self, directory):
        from biocompiler.core_client import CoreClient
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        cache = Path(self.cache_directory.name)
        if self.cached is not None:
            shutil.copytree(cache, root, dirs_exist_ok=True)
            return deepcopy(self.cached)
        receipt = {"_artifact_directory": str(root), "checks": [], "artifacts": {}}
        with tempfile.TemporaryDirectory() as binary_directory, self.exchanges():
            binaries = Path(binary_directory)
            for role in r.ROLES:
                (binaries / role).write_bytes(b"transport test double, never executed")
                (binaries / role).chmod(0o755)
            r.campaign([CoreClient(binaries / role, role=role) for role in r.ROLES], self.corpus, receipt)
        receipt["completed_checks"] = len(receipt["checks"])
        del receipt["_artifact_directory"]
        shutil.copytree(root, cache, dirs_exist_ok=True)
        type(self).cached = deepcopy(receipt)
        return receipt

    def test_actual_public_routes_all328_complete_occurrences_and_strict_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = self.generate(directory)
            self.assertEqual(receipt["completed_checks"], 328)
            self.assertEqual(len({row["request_id"] for row in receipt["checks"]}), 328)
            artifacts = r.Artifacts(Path(directory), receipt["artifacts"])
            checked = r.validate_checks(receipt, self.full, artifacts)
            self.assertEqual(len(checked), 328)
            for case, check in zip(self.full.cases, receipt["checks"][:164], strict=True):
                r.check_guard(check["guard_frames"], case)
                if check["status"] == "ok":
                    self.assertEqual(check["view_type"], "NativeWorkflowRecord")
                    self.assertEqual(check["view_fingerprint"], r.c.sha(case["expected"]))

    def test_guard_rejects_semantic_execution_and_post_input_properties(self):
        import biocompiler.workflow_backend as backend
        from biocompiler.compiler import verification_workflow as workflow
        from biocompiler.verification.exploration import BooleanContactConfig
        with self.assertRaisesRegex(AssertionError, "semantic fallback"):
            with r.routed_execution():
                workflow._checker(None)
        with self.assertRaisesRegex(AssertionError, "semantic fallback"):
            with r.routed_execution():
                workflow.SyntheticVerificationRequest.from_dict({})
        with self.assertRaisesRegex(AssertionError, "semantic fallback"):
            with r.routed_execution():
                BooleanContactConfig.state_count.fget(None)
        self.assertFalse(backend.serializing_legacy_input())
        self.assertFalse(r.allowed_call("biocompiler.verification.exploration", "_Record.from_dict", "output", "ExplorationReport"))
        self.assertFalse(r.allowed_call("biocompiler.verification.exploration", "reduce_counterexample", "input", ""))
        self.assertFalse(r.allowed_call("biocompiler.semantics.evaluator", "evaluate", "input", ""))

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(r.canonical(value) + b"\n")

    def fixture(self, directory):
        root, natives = Path(directory) / "realization", Path(directory) / "native"
        raw_receipt = self.generate(Path(directory) / "source-artifacts")
        # Comparator mutations keep all original164 occurrences, not a sample.
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
                self.write(slot / "native-inputs.json", {**inputs, "run_id": RUN, "source_revision": SOURCE, "python_version": python + ".9"})
                artifact_directory = slot / r.ARTIFACT_DIRECTORY
                artifact_directory.mkdir()
                receipt = deepcopy(raw_receipt)
                receipt.update(schema_version=r.SCHEMA, status="success", scope=r.SCOPE,
                    revision=REVISION, source_revision=SOURCE, run_id=RUN, system=system, machine=machine,
                    native_platform=target, python_version=python + ".9", native_inputs=inputs,
                    package_path="/installed/site-packages/biocompiler/__init__.py", corpus_pin=r.CORPUS_PIN,
                    supplemental_pin=r.SUPPLEMENTAL_PIN, profile_pin=r.PROFILE_PIN,
                    transport_sources=r.source_pins("src/" + name.replace(".", "/") + ".py" for name in sorted(r.SOURCE_MODULES)),
                    campaign_sources=r.source_pins(r.SOURCES), artifact_directory=r.ARTIFACT_DIRECTORY)
                # Give every runtime distinct UUIDs; retain each full envelope
                # before the comparator's only explicit identity projection.
                all_bytes = {identity: (Path(directory) / "source-artifacts" / item["path"]).read_bytes()
                             for identity, item in receipt["artifacts"].items()}
                for check in receipt["checks"]:
                    identity = str(uuid4())
                    check["request_id"] = identity
                    for field in ("envelope", "semantic_receipt"):
                        if check[field] is None:
                            continue
                        document = json.loads(all_bytes[check[field]])
                        document["request_id"] = identity
                        if field == "envelope" and document["status"] == "ok":
                            document["result"]["result"]["request_id"] = identity
                        encoded = r.canonical(document)
                        new = r.c.sha(encoded)
                        all_bytes[new] = encoded
                        check[field] = new
                used = {check[field] for check in receipt["checks"] for field in ("authority", "retained", "wire_authority",
                    "wire_retained", "expected", "source_evidence", "record", "semantic_receipt", "envelope", "view_json")
                    if check[field] is not None}
                receipt["artifacts"] = {}
                for identity in used:
                    raw = all_bytes[identity]
                    (artifact_directory / (identity + ".bin")).write_bytes(raw)
                    receipt["artifacts"][identity] = {"path": identity + ".bin", "bytes": len(raw), "sha256": identity}
                self.write(slot / r.RECEIPT_FILE, receipt)
        return root, natives

    def compare(self, root, natives):
        with patch.object(r, "Golden", return_value=self.full):
            return r.compare(root, natives, revision=REVISION, source_revision=SOURCE, run_id=RUN)

    def test_full_four_way_comparator_rejects_stale_missing_duplicate_and_forged_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root, natives = self.fixture(directory)
            result = self.compare(root, natives)
            self.assertEqual(len(result["receipts"]), 4)
            path = root / "realization-linux-x86_64-py3.11" / r.RECEIPT_FILE
            original = json.loads(path.read_bytes())
            mutations = (
                lambda value: value.update(revision="c" * 40),
                lambda value: value.update(run_id="stale"),
                lambda value: value.update(python_version="3.14.9"),
                lambda value: value["checks"].pop(),
                lambda value: value["checks"].append(deepcopy(value["checks"][0])),
                lambda value: value["checks"][0].update(request_id="not-a-uuid"),
                lambda value: value["checks"][1].update(request_id=value["checks"][0]["request_id"]),
                lambda value: value["checks"][0].update(guard_frames=[]),
                lambda value: value["checks"][0].update(input_kind="native"),
                lambda value: value.update(artifact_directory="../outside"),
                lambda value: value["transport_sources"].update({"src/biocompiler/workflow_backend.py": "0" * 64}),
            )
            for mutation in mutations:
                changed = deepcopy(original); mutation(changed); self.write(path, changed)
                with self.assertRaises(AssertionError):
                    self.compare(root, natives)
            self.write(path, original)
            fourth = root / "realization-macos-arm64-py3.14" / "native-inputs.json"
            fourth.unlink()
            with self.assertRaises(AssertionError):
                self.compare(root, natives)

    def test_full_artifact_forgeries_guard_weakening_and_binary_changes_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root, natives = self.fixture(directory)
            slot = root / "realization-linux-x86_64-py3.11"
            path = slot / r.RECEIPT_FILE
            original = json.loads(path.read_bytes())
            for field in ("record", "view_json", "semantic_receipt"):
                receipt = deepcopy(original)
                check = receipt["checks"][0]
                identity = check[field]
                artifact = slot / r.ARTIFACT_DIRECTORY / (identity + ".bin")
                value = json.loads(artifact.read_bytes())
                value["forged_complete_field"] = True
                raw = r.canonical(value)
                changed = r.c.sha(raw)
                new_path = artifact.parent / (changed + ".bin")
                new_path.write_bytes(raw)
                receipt["artifacts"][changed] = {"path": changed + ".bin", "bytes": len(raw), "sha256": changed}
                check[field] = changed
                self.write(path, receipt)
                with self.assertRaises(AssertionError):
                    self.compare(root, natives)
                new_path.unlink()
            receipt = deepcopy(original)
            row = next(item for item in receipt["checks"] if item["status"] == "error")
            row["diagnostic"]["message"] += " changed"
            self.write(path, receipt)
            with self.assertRaises(AssertionError):
                self.compare(root, natives)
            receipt = deepcopy(original)
            receipt["checks"][0]["guard_frames"].append(
                ["biocompiler.verification.exploration", "reduce_counterexample", "output", ""])
            receipt["checks"][0]["guard_frames"].sort()
            self.write(path, receipt)
            with self.assertRaisesRegex(AssertionError, "Unreviewed executed"):
                self.compare(root, natives)
            self.write(path, original)
            binary = natives / "linux-x86_64" / "biocompiler-verify"
            binary.write_bytes(binary.read_bytes() + b" changed")
            with self.assertRaisesRegex(ValueError, "bytes differ"):
                self.compare(root, natives)

    def test_rehashed_full_envelope_uuid_forgery_is_not_projected_away(self):
        with tempfile.TemporaryDirectory() as directory:
            root, natives = self.fixture(directory)
            slot = root / "realization-linux-x86_64-py3.11"
            path = slot / r.RECEIPT_FILE
            receipt = json.loads(path.read_bytes())
            check = receipt["checks"][0]
            identity = check["envelope"]
            artifact = slot / r.ARTIFACT_DIRECTORY / (identity + ".bin")
            value = json.loads(artifact.read_bytes())
            value["result"]["result"]["request_id"] = str(uuid4())
            raw = r.canonical(value)
            changed = r.c.sha(raw)
            (artifact.parent / (changed + ".bin")).write_bytes(raw)
            artifact.unlink()
            del receipt["artifacts"][identity]
            receipt["artifacts"][changed] = {"path": changed + ".bin", "bytes": len(raw), "sha256": changed}
            check["envelope"] = changed
            self.write(path, receipt)
            with self.assertRaisesRegex(AssertionError, "UUID/wire binding"):
                self.compare(root, natives)


if __name__ == "__main__":
    unittest.main()
