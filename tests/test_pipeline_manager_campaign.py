"""Pure-Python integrity controls for the installed native manager gate.

The fabricated frames below test a comparator, never acceptance or native
parity. Actual pinned native execution is required separately in hosted CI.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from uuid import uuid4

from tools import check_pipeline_manager_install as campaign


def fake_frames(receipt, *, admission=False):
    channel, application = campaign.declarations()
    nonce = str(uuid4())
    rows, sequence, event = [], 0, 0
    input_bytes = output_bytes = nodes = count = commands = pending = 0
    bodies = {}
    put = lambda raw: campaign.artifact(receipt, raw)
    def client(kind, fields):
        nonlocal sequence, input_bytes, nodes, count, commands, pending
        value = {"protocol": channel["protocol"], "profile": channel["profile"], "session_id": nonce,
            "kind": kind, "sequence": sequence, **fields}
        body = campaign.canonical(value)
        raw = campaign.frame(value)
        bodies[sequence] = body
        rows.append({"direction": "client", "index": sequence, "frame": put(raw)})
        sequence += 1
        input_bytes += len(raw)
        nodes += campaign.json_nodes(value)
        count += 1
        if kind == "continue":
            pending -= 1
        else:
            commands += 1
        return sequence - 1
    def server(kind, fields):
        nonlocal event, output_bytes, nodes, count, pending
        if kind == "invoke":
            pending += 1
        value = {"protocol": channel["protocol"], "profile": channel["profile"], "session_id": nonce,
            "kind": kind, "event_id": event, **fields, "usage": {key: 0 for key in channel["usage_fields"]}}
        count += 1
        nodes += campaign.json_nodes(value)
        value["usage"].update(input_bytes=input_bytes, output_bytes=output_bytes, frames=count,
            commands=commands, json_nodes=nodes, pending_invocations=pending, retained_bytes=10_000+count,
            work_charged=1_000_000+count*100, work_remaining=10**12-1_000_000-count*100)
        while True:
            raw = campaign.frame(value)
            expected = output_bytes + len(raw)
            if value["usage"]["output_bytes"] == expected:
                break
            value["usage"]["output_bytes"] = expected
        rows.append({"direction": "server", "index": event, "frame": put(raw)})
        output_bytes += len(raw)
        event += 1
        return value, raw[9:]
    def reply(sequence, value=None, *, closed=False):
        return server("reply", {"sequence": sequence, "request_sha256": campaign.sha(bodies[sequence]),
            "outcome": {"status": "ok", "value": value}, "closed": closed})
    seq = client("hello", {"declaration": channel, "application": application, "limits": None})
    reply(seq, {"declaration": channel, "application": application, "limits": channel["limits"]})
    operations = ["initialize-empty", "register-component-input", "admit-component-input"] if admission else ["initialize-empty", "add-input", "register", "run"]
    for operation in operations:
        seq = client("command", {"parent_invocation": None, "operation": operation,
            "arguments": {field: None for field in application["operations"][operation]["fields"]}})
        if operation == operations[-1]:
            invocation, body = server("invoke", {"invocation_id": event, "parent_invocation": None,
                "command_sequence": seq, "command_sha256": campaign.sha(bodies[seq]),
                "action": "call-provider", "arguments": {"provider_id": "provider/1", "context": {"handle": "object/1"}}})
            client("continue", {"invocation_id": invocation["invocation_id"], "invocation_sha256": campaign.sha(body),
                "outcome": {"status": "return", "value": {"handle": "object/2"}}})
        reply(seq)
    seq = client("close", {"parent_invocation": None})
    reply(seq, closed=True)
    return rows


def fixture(directory, corpus):
    path = directory / campaign.ARTIFACT_DIRECTORY
    path.mkdir(parents=True)
    receipt = {"_artifact_directory": str(path), "artifacts": {}, "checks": [],
        "native_inputs": {"sha256": {"biocompiler-core": "a"*64, "biocompiler-verify": "b"*64}},
        "executables": {"core": "/native/biocompiler-core", "verify": "/native/biocompiler-verify"},
        "completed_checks": 5}
    put = lambda value: campaign.artifact(receipt, campaign.canonical(value))
    channel, application = campaign.declarations()
    stdout = {"protocol": "biocompiler.core.v1", "request_id": None, "operation": None, "status": "error", "result": None,
        "diagnostics": [{"code": "unexpected_arguments", "message": "Expected standard JSON input or the exact inherited artifact descriptor arguments.", "path": None}],
        "core": {**campaign.fixed.CORE, "executable": "verify"}}
    receipt["verify_rejection"] = {"argv": [receipt["executables"]["verify"], campaign.ARGUMENT], "executable_sha256": "b"*64,
        "returncode": 2, "request": campaign.artifact(receipt, campaign.frame(campaign.verify_request(channel, application, str(uuid4())))),
        "stdout": campaign.artifact(receipt, campaign.canonical(stdout)+b"\n"), "stderr": put({"hex": ""})}
    guard = sorted([["biocompiler.core_pipeline_manager", "CorePassManager.__init__"],
        ["biocompiler.core_pipeline_callback_session", "CorePipelineCallbackSession.__init__"],
        ["biocompiler.core_pipeline_callback_session", "CorePipelineCallbackSession.call"],
        ["biocompiler.pipeline_callback_objects", "CallbackObjects.execute"]])
    for case in corpus.cases:
        receipt["checks"].append({"id": case["case"], "original": put(case), "actual": put(case),
            "pid": 123, "returncode": 0, "closed": True, "invalidated": False, "executable_sha256": "a"*64,
            "stderr": put({"hex": ""}), "guard": put(guard),
            "after_close": put({"type": "CoreProtocolError", "message": "Callback session is closed; it cannot reconnect",
                "traffic_unchanged": True, "pid_unchanged": True}),
            "frames": fake_frames(receipt, admission=case["case"].startswith("admission:"))})
    receipt["pending"] = put(corpus.pending)
    return receipt


def validate(receipt, corpus):
    return campaign.validate_checks(receipt, corpus,
        campaign.Artifacts(Path(receipt["_artifact_directory"]), receipt["artifacts"]))


def edit_artifact(receipt, row, field, mutate, *, framed=False):
    old = row[field]
    path = Path(receipt["_artifact_directory"]) / (old + ".bin")
    value = campaign.frame_body(path.read_bytes()) if framed else json.loads(path.read_bytes())
    mutate(value)
    row[field] = campaign.artifact(receipt, campaign.frame(value) if framed else campaign.canonical(value))
    # Old evidence may still be referenced (original=actual); keep it only when
    # some other current receipt field refers to the old identity.
    control = {key: value for key, value in receipt.items() if key not in ("artifacts", "_artifact_directory")}
    if old not in campaign.canonical(control).decode():
        del receipt["artifacts"][old]
        path.unlink()


def matrix_fixture(root, corpus):
    revision, source_revision, run_id = "a"*40, "b"*40, "manager-test-run"
    native_root, runtime_root = root/"native", root/"realization"
    native_root.mkdir(); runtime_root.mkdir()
    for target, (system, machine) in campaign.r.PLATFORMS.items():
        native_path = native_root/target
        native_path.mkdir()
        pins = {}
        for role in ("core", "verify"):
            path = native_path/("biocompiler-"+role)
            path.write_bytes(("NONEXECUTABLE UNIT FIXTURE " + target + " " + role).encode())
            pins[path.name] = campaign.sha(path.read_bytes())
        (native_path/"binaries.json").write_bytes(campaign.canonical({"revision": revision,
            "system": system, "machine": machine, "sha256": pins})+b"\n")
        native = campaign.r.verify_binaries(native_path, revision, target)
        for python in campaign.r.PYTHONS:
            directory = runtime_root/("realization-"+target+"-py"+python)
            receipt = fixture(directory, corpus)
            receipt.update(schema_version=campaign.SCHEMA, status="success", scope=campaign.SCOPE,
                revision=revision, source_revision=source_revision, run_id=run_id,
                python_version=python+".9", system=system, machine=machine, native_platform=target,
                artifact_directory=campaign.ARTIFACT_DIRECTORY, native_inputs=native,
                python_sources=campaign.python_sources(), campaign_sources=campaign.r.source_pins(campaign.SOURCES),
                package_path="/installed/site-packages/biocompiler/__init__.py", **campaign.metadata(corpus))
            receipt["executables"] = {role: str(native_path/("biocompiler-"+role)) for role in ("core", "verify")}
            receipt["verify_rejection"]["argv"][0] = receipt["executables"]["verify"]
            receipt["verify_rejection"]["executable_sha256"] = pins["biocompiler-verify"]
            for row in receipt["checks"]:
                row["executable_sha256"] = pins["biocompiler-core"]
            del receipt["_artifact_directory"]
            (directory/campaign.RECEIPT_FILE).write_bytes(campaign.canonical(receipt)+b"\n")
            (directory/"native-inputs.json").write_bytes(campaign.canonical({**native, "run_id": run_id,
                "source_revision": source_revision, "python_version": python+".9"})+b"\n")
    return runtime_root, native_root, dict(revision=revision, source_revision=source_revision, run_id=run_id)


class PipelineManagerCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.corpus = campaign.Corpus()

    def test_full_original_and_pending_census(self):
        self.assertEqual(tuple(case["case"] for case in self.corpus.cases), campaign.CASES)
        pending = self.corpus.pending
        self.assertEqual(len(pending["original_contexts"]), 476)
        self.assertEqual(pending["original_event_count"], 91566)
        self.assertEqual(pending["fixed_unreplayed_observations"], 287)
        self.assertEqual(pending["fixed_census"]["excluded_calls"], 10)
        self.assertEqual(len(pending["callback_cases"]), 34)
        self.assertEqual(len(pending["deferred_cases"]), 47)

    def test_complete_comparator_fixture_and_nonce_projection(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first, second = fixture(Path(a), self.corpus), fixture(Path(b), self.corpus)
            self.assertEqual(validate(first, self.corpus), validate(second, self.corpus))
            self.assertEqual(len(validate(first, self.corpus)), 5)

    def test_complete_case_mutations_are_rejected_even_with_new_content_hash(self):
        mutations = [lambda value: value["events"][0].update(target_is_supplied=False),
            lambda value: value["records"].pop(), lambda value: value["events"].pop(),
            lambda value: value.update(retained_objects=value["retained_objects"]+1)]
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                receipt = fixture(Path(directory), self.corpus)
                edit_artifact(receipt, receipt["checks"][0], "actual", mutation)
                with self.assertRaises(AssertionError):
                    validate(receipt, self.corpus)

    def test_session_binding_usage_and_lifo_mutations_are_rejected(self):
        changes = [("invoke", lambda value: value.update(command_sha256="0"*64)),
            ("invoke", lambda value: value.update(invocation_id=999)),
            ("invoke", lambda value: value.update(parent_invocation=0)),
            ("continue", lambda value: value.update(invocation_sha256="0"*64)),
            ("continue", lambda value: value.update(sequence=0)),
            ("reply", lambda value: value.update(request_sha256="0"*64)),
            ("reply", lambda value: value["usage"].update(json_nodes=value["usage"]["json_nodes"]+1)),
            ("reply", lambda value: value["usage"].update(frames=value["usage"]["frames"]-1)),
            ("reply", lambda value: value.update(event_id=100)),
            ("reply", lambda value: value.update(extra=None))]
        for kind, mutation in changes:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                receipt = fixture(Path(directory), self.corpus)
                row = next(row for row in receipt["checks"][0]["frames"] if campaign.frame_body(
                    (Path(receipt["_artifact_directory"]) / (row["frame"]+".bin")).read_bytes())["kind"] == kind)
                edit_artifact(receipt, row, "frame", mutation, framed=True)
                with self.assertRaises(AssertionError):
                    validate(receipt, self.corpus)

    def test_missing_duplicate_cases_and_pending_claim_changes_fail(self):
        for mutation in (lambda receipt: receipt["checks"].pop(),
                lambda receipt: receipt["checks"].__setitem__(1, receipt["checks"][0]),
                lambda receipt: receipt.update(completed_checks=4),
                lambda receipt: receipt["checks"][0].update(invalidated=True),
                lambda receipt: receipt["checks"][0].update(executable_sha256="c"*64)):
            with tempfile.TemporaryDirectory() as directory:
                receipt = fixture(Path(directory), self.corpus)
                mutation(receipt)
                with self.assertRaises(AssertionError):
                    validate(receipt, self.corpus)
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(Path(directory), self.corpus)
            edit_artifact(receipt, receipt, "pending", lambda value: value.update(fixed_unreplayed_observations=0))
            with self.assertRaises(AssertionError):
                validate(receipt, self.corpus)

    def test_whole_byte_inventory_and_actual_verify_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(Path(directory), self.corpus)
            identity = receipt["checks"][0]["frames"][0]["frame"]
            path = Path(receipt["_artifact_directory"]) / (identity+".bin")
            path.write_bytes(path.read_bytes()+b" ")
            with self.assertRaises(AssertionError):
                validate(receipt, self.corpus)
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(Path(directory), self.corpus)
            receipt["verify_rejection"]["argv"][-1] = "--pipeline-session-v1"
            with self.assertRaises(AssertionError):
                validate(receipt, self.corpus)
        with tempfile.TemporaryDirectory() as directory:
            receipt = fixture(Path(directory), self.corpus)
            campaign.artifact(receipt, b"unreferenced")
            with self.assertRaises(AssertionError):
                validate(receipt, self.corpus)

    def test_guard_forbids_original_manager_and_native_semantic_fallback(self):
        from biocompiler.compiler.pipeline import PassManager
        for module, name in (("biocompiler.compiler.pipeline", "PassManager.run"),
                ("biocompiler.compiler.pipeline", "PassManager.get"),
                ("biocompiler.compiler.synthetic", "run_synthetic_pipeline"),
                ("biocompiler.synthesis.generator", "generate"),
                ("biocompiler.verification.realization", "check")):
            self.assertFalse(campaign.permitted(module, name))
        seen = set()
        with self.assertRaisesRegex(AssertionError, "semantic authority"):
            with campaign.guarded_execution(seen):
                PassManager.__init__(object(), target=None, dependencies={})
        self.assertIsNone(sys.getprofile())

    def test_frozen_oracle_loading_restores_import_path(self):
        before = list(sys.path)
        oracle = campaign.load_oracle(installed=False)
        self.assertEqual(sys.path, before)
        self.assertEqual(oracle.capture()["cases"], self.corpus.cases)
        with self.assertRaisesRegex(AssertionError, "Source-tree product"):
            campaign.installed_modules()

    def test_complete_four_runtime_matrix_rehashes_receipts_and_binaries(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime, native, authority = matrix_fixture(Path(directory), self.corpus)
            result = campaign.compare(runtime, native, **authority)
            self.assertEqual(result["status"], "success")
            self.assertEqual(len(result["receipts"]), 4)
            path = native/"linux-x86_64"/"biocompiler-core"
            path.write_bytes(path.read_bytes()+b" changed")
            with self.assertRaises(ValueError):
                campaign.compare(runtime, native, **authority)
        with tempfile.TemporaryDirectory() as directory:
            runtime, native, authority = matrix_fixture(Path(directory), self.corpus)
            path = runtime/"realization-macos-arm64-py3.14"/campaign.RECEIPT_FILE
            receipt = json.loads(path.read_bytes())
            receipt["run_id"] = "older-run"
            path.write_bytes(campaign.canonical(receipt)+b"\n")
            with self.assertRaisesRegex(AssertionError, "mixed manager"):
                campaign.compare(runtime, native, **authority)

    def test_python_only_role_probe_fixture_uses_actual_flag_and_bounded_io(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"python-probe-fixture"
            path.write_text("#!"+sys.executable+"\nimport sys\nprint(sys.argv[1])\nprint(sys.stdin.read())\nraise SystemExit(2)\n")
            path.chmod(0o755)
            code, stdout, stderr = campaign.raw_exchange(path, b"original input")
            self.assertEqual((code, stdout, stderr), (2, (campaign.ARGUMENT+"\noriginal input\n").encode(), b""))
            path.write_text("#!"+sys.executable+"\nprint('x'*70000)\n")
            with self.assertRaisesRegex(AssertionError, "output exceeded"):
                campaign.raw_exchange(path, b"x")

    def test_four_runtime_comparison_rejects_incomplete_or_stale_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/"realization").mkdir()
            (root/"native").mkdir()
            with self.assertRaisesRegex(AssertionError, "four-runtime"):
                campaign.compare(root/"realization", root/"native", revision="a"*40, source_revision="b"*40, run_id="123")
            with self.assertRaisesRegex(AssertionError, "current manager"):
                campaign.compare(root/"realization", root/"native", revision="a"*40, source_revision="b"*40, run_id="")


if __name__ == "__main__":
    unittest.main()
