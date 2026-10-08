"""Complete evidence comparator tests: no native program is executed."""
from copy import deepcopy
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import check_native_workflow_presentation as r

REVISION = "a" * 40
SOURCE = "b" * 40
RUN = "77"


class WorkflowPresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = r.Golden()
        cls.corpus = object.__new__(r.Corpus)
        cls.corpus.profile, cls.corpus._cases = cls.full.profile, cls.full.cases
        cls.cases = cls.full.cases

    def test_production_matrix_retains_every_original_occurrence_and_both_roles(self):
        self.assertEqual(len(self.full.cases), 137)
        expected = self.full.expected()
        self.assertEqual(len(expected), 274)
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
        selected.extend(case for case in self.full.cases if case["origin"] in ("command_success", "command_precedence", "presentation_resource"))
        golden.cases = deepcopy(selected)
        return golden

    def fixture_presentation(self, case, record):
        outcome = record["result"]
        operation = record["request"]["operation"]
        value = {"profile": "biocompiler.core.verification_workflow.presentation.v1",
                 "command_exit_code": 0, "original_frames": None, "reduced_frames": None}
        if operation == "reduce":
            value["original_frames"] = len(outcome["original_history"])
            value["reduced_frames"] = len(outcome["history"])
        if case["operation"] == "run-verification-workflow":
            verdict = {"check": lambda: outcome["outcome"] == "pass",
                       "explore": lambda: outcome["all_passed"],
                       "reduce": lambda: outcome["one_minimal"]}[operation]()
            value["command_exit_code"] = int(not verdict)
        return value

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
                artifact_directory = slot / r.ARTIFACT_DIRECTORY
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
                    item = {key: case[key] for key in ("id", "phase", "origin", "operation", "limits", "command")}
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
                            "schema_version": "biocompiler.core.verification_workflow_result.v2",
                            "profile": golden.profile["profile"], "operation": case["operation"],
                            "request_id": request_id, "executable": role,
                            "validation_scope": "complete_fresh_verification_workflow",
                            "implementation_version": "biocompiler.ocaml.verification_workflow_service.v0.2",
                            "workflow_version": "biocompiler.synthetic_verification_workflow.v0.1",
                            "workflow_operation": authority["operation"], "mode": authority["mode"],
                            "authority_fingerprint": r.digest(authority), "request_fingerprint": r.digest(record["request"]),
                            "retained_record_fingerprint": None if case["retained"] is None else r.digest(r.decode(case["retained"])),
                            "record_fingerprint": hashlib.sha256(case["expected"]).hexdigest(),
                            "resources": r.r.effective_resources(golden.profile, case["limits"]),
                            "command": case["command"], "presentation": self.fixture_presentation(case, record)}
                        result = {"schema_version": "biocompiler.core.artifact_response.v1",
                            "transport": "biocompiler.core.artifact_transport.v1", "authority": r.descriptor(case["authority"]),
                            "retained_record": r.descriptor(case["retained"]), "artifact": r.descriptor(case["expected"]), "result": receipt}
                        item.update(status="ok", diagnostic=None, record=artifact(case["expected"]),
                                    semantic_receipt=artifact(r.canonical(receipt)))
                        envelope.update(status="ok", diagnostics=[], result=result)
                    item["envelope"] = artifact(r.canonical(envelope))
                    checks.append(item)
                receipt = {"schema_version": r.SCHEMA, "status": "success",
                    "scope": r.SCOPE,
                    "revision": REVISION, "source_revision": SOURCE, "run_id": RUN, "system": system, "machine": machine,
                    "native_platform": target, "python_version": python + ".9", "native_inputs": inputs,
                    "package_path": "/installed/site-packages/biocompiler/__init__.py", "corpus_pin": r.CORPUS_PIN,
                    "supplemental_pin": r.SUPPLEMENTAL_PIN, "profile_pin": r.PROFILE_PIN,
                    "transport_sources": r.source_pins("src/" + name.replace(".", "/") + ".py" for name in sorted(r.TRANSPORT_MODULES)),
                    "campaign_sources": r.source_pins(r.SOURCES),
                    "checks": checks, "completed_checks": len(checks), "artifacts": values, "artifact_directory": r.ARTIFACT_DIRECTORY}
                self.write(slot / r.RECEIPT_FILE, receipt)
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
            path = root / "realization-linux-x86_64-py3.11" / r.RECEIPT_FILE
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
                lambda value: value["checks"][0].update(command="forged"),
                lambda value: value.update(profile_pin="0" * 64),
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
            path = slot / r.RECEIPT_FILE
            original = json.loads(path.read_bytes())
            for kind in ("record", "semantic_receipt", "envelope", "presentation", "command_binding"):
                receipt = deepcopy(original)
                item = next(check for check in receipt["checks"] if check["status"] == "ok")
                artifact_kind = "semantic_receipt" if kind in ("presentation", "command_binding") else kind
                old = item[artifact_kind]
                old_path = slot / r.ARTIFACT_DIRECTORY / (old + ".bin")
                original_bytes = old_path.read_bytes()
                document = json.loads(original_bytes)
                if kind == "record":
                    document["claim_scope"] = "forged universal acceptance"
                elif kind == "semantic_receipt":
                    document["resources"]["workflow"]["max_work"] -= 1
                elif kind == "presentation":
                    document["presentation"]["command_exit_code"] = 1 - document["presentation"]["command_exit_code"]
                elif kind == "command_binding":
                    document["command"] = "synthetic-reduce"
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
            receipt = json.loads((slot / r.RECEIPT_FILE).read_bytes())
            identity = next(iter(receipt["artifacts"]))
            path = slot / r.ARTIFACT_DIRECTORY / (identity + ".bin")
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with self.assertRaisesRegex(AssertionError, "bytes differ"):
                self.compare(root, natives, golden)
            path.unlink()
            path.symlink_to(slot / r.RECEIPT_FILE)
            with self.assertRaisesRegex(AssertionError, "symlinked"):
                self.compare(root, natives, golden)
            path.unlink()
            path.write_bytes(original)
            extra = slot / r.ARTIFACT_DIRECTORY / ("0" * 64 + ".bin")
            extra.write_bytes(b"{}")
            with self.assertRaisesRegex(AssertionError, "extra"):
                self.compare(root, natives, golden)
            extra.unlink()
            binary = natives / "macos-arm64" / "biocompiler-verify"
            binary.write_bytes(binary.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "bytes differ"):
                self.compare(root, natives, golden)


    @contextmanager
    def exchanges(self, corrupt=False):
        from biocompiler.core_client import CAPABILITIES_SCHEMA, CORE_VERSION, LIMITS, PROTOCOL
        from biocompiler.core_artifacts import TRANSPORT_PROFILE
        by_id = {r.request_identity(role, case): (role, case) for role in ("core", "verify") for case in self.cases}
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
        def exchange(core, raw, arguments, files, output, _limit, _cancelled):
            request = json.loads(raw); role, case = by_id[request["request_id"]]
            self.assertEqual(role, core.role)
            self.assertEqual(request["payload"]["operation_payload"], {"profile": self.corpus.profile["profile"],
                "limits": case["limits"], "command": case["command"]})
            self.assertEqual(files[0].read(), case["authority"])
            if case["retained"] is not None: self.assertEqual(files[1].read(), case["retained"])
            if case["error"] is not None: return response(request, role, None, case["error"])
            record = case["expected"]
            if corrupt:
                value = json.loads(record); value["result"]["corrupted_complete_field"] = True
                record = r.canonical(value)
            output.write(record); output.flush()
            def descriptor(raw): return {"bytes": len(raw), "sha256": r.c.sha(raw)}
            profile = self.corpus.profile
            authority = json.loads(case["authority"])
            receipt = {"schema_version": "biocompiler.core.verification_workflow_result.v2", "profile": profile["profile"],
                "operation": case["operation"], "executable": role, "request_id": request["request_id"],
                "validation_scope": profile["validation_scope"], "implementation_version": profile["implementation_version"],
                "workflow_version": profile["workflow_version"], "workflow_operation": authority["operation"], "mode": authority["mode"],
                "authority_fingerprint": r.digest(authority), "request_fingerprint": r.digest(json.loads(record)["request"]),
                "retained_record_fingerprint": None if case["retained"] is None else r.digest(json.loads(case["retained"])),
                "record_fingerprint": r.c.sha(record), "resources": r.r.effective_resources(profile, case["limits"]),
                "command": case["command"], "presentation": self.fixture_presentation(case, json.loads(record))}
            value = {"schema_version": "biocompiler.core.artifact_response.v1", "transport": "biocompiler.core.artifact_transport.v1",
                "authority": descriptor(case["authority"]), "retained_record": None if case["retained"] is None else descriptor(case["retained"]),
                "artifact": descriptor(record), "result": receipt}
            return response(request, role, value)
        with patch("biocompiler.core_client._exchange", side_effect=negotiate), \
             patch("biocompiler.core_artifacts._exchange_artifacts", side_effect=exchange):
            yield

    def test_complete_two_role_campaign_publishes_every_full_artifact_and_error(self):
        from biocompiler.core_client import CoreClient
        with tempfile.TemporaryDirectory() as directory, self.exchanges():
            root = Path(directory)
            receipt = {"_artifact_directory": str(root), "checks": [], "artifacts": {}}
            for role in ("core", "verify"):
                (root / role).write_bytes(b"transport test double; never executed")
                (root / role).chmod(0o755)
            clients = [CoreClient(root / role, role=role) for role in ("core", "verify")]
            r.campaign(clients, self.corpus, receipt)
            self.assertEqual(len(receipt["checks"]), 274)
            self.assertEqual(Counter(row["role"] for row in receipt["checks"]), {"core": 137, "verify": 137})
            for role in ("core", "verify"):
                rows = [row for row in receipt["checks"] if row["role"] == role]
                self.assertEqual([(row["id"], row["phase"]) for row in rows], [(case["id"], case["phase"]) for case in self.cases])
                for case, row in zip(self.cases, rows, strict=True):
                    self.assertEqual(row["guard_modules"], sorted(r.TRANSPORT_MODULES))
                    self.assertEqual((root / receipt["artifacts"][row["authority"]]["path"]).read_bytes(), case["authority"])
                    wire = json.loads((root / receipt["artifacts"][row["envelope"]]["path"]).read_bytes())
                    self.assertEqual(wire["request_id"], r.request_identity(role, case))
                    self.assertEqual(wire["core"]["executable"], role)
                    if case["expected"] is not None:
                        self.assertEqual((root / receipt["artifacts"][row["record"]]["path"]).read_bytes(), case["expected"])
                        self.assertIsNone(row["diagnostic"])
                    else:
                        self.assertEqual(wire["diagnostics"], [case["error"]])
            for identity, descriptor in receipt["artifacts"].items():
                raw = (root / descriptor["path"]).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), identity)
                self.assertEqual(len(raw), descriptor["bytes"])

    def test_changed_full_record_is_not_accepted_even_with_matching_native_hashes(self):
        from biocompiler.core_client import CoreClient
        with tempfile.TemporaryDirectory() as directory, self.exchanges(corrupt=True):
            receipt = {"_artifact_directory": directory, "checks": [], "artifacts": {}}
            (Path(directory) / "core").write_bytes(b"transport test double; never executed")
            (Path(directory) / "core").chmod(0o755)
            with self.assertRaisesRegex(AssertionError, "Complete original presentation output differs"):
                r.campaign([CoreClient(Path(directory) / "core")], self.corpus, receipt)
            self.assertEqual(receipt["checks"], [])

    def test_guard_forbids_semantic_imports_and_preloaded_functions(self):
        namespace = {"__name__": "biocompiler.compiler.forbidden"}
        exec("def semantic(): return 1", namespace)
        with self.assertRaisesRegex(AssertionError, "semantic execution"), r.c.transport_only():
            namespace["semantic"]()
        with self.assertRaisesRegex(AssertionError, "semantic import"), r.c.transport_only():
            __import__("biocompiler.compiler.verification_workflow")

    def test_presentation_status_and_counts_use_complete_original_records_only(self):
        counts = Counter()
        for case in self.cases:
            if case["expected"] is None:
                continue
            expected = self.fixture_presentation(case, json.loads(case["expected"]))
            self.assertEqual(r.expected_presentation(case), expected)
            if case["operation"] == "replay-verification-workflow":
                self.assertEqual(expected["command_exit_code"], 0)
            counts[(json.loads(case["expected"])["request"]["operation"], expected["command_exit_code"])] += 1
        self.assertEqual(set(counts), {(operation, status) for operation in ("check", "explore", "reduce") for status in (0, 1)})
        original = r.r.Golden().cases
        self.assertEqual([{key: value for key, value in case.items() if key != "command"} for case in self.cases[:112]], original)
        self.assertTrue(all(case["command"] is None for case in self.cases[:112]))
        self.assertEqual(Counter(case["origin"] for case in self.cases), {
            "original": 89, "supplemental": 18, "normalization": 2, "resource": 2, "authority_precedence": 1,
            "command_success": 18, "command_precedence": 6, "presentation_resource": 1})

if __name__ == "__main__":
    unittest.main()
