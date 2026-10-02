"""Integrity and mutation checks for the installed persistent-session campaign.

Python subprocesses below are transport stimuli only. They do not establish
native semantic parity; hosted runs must execute the pinned OCaml binaries.
"""
from collections import Counter
from copy import deepcopy
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from tools import check_pipeline_session_install as campaign


def frame(value):
    body = campaign.canonical(value)
    return f"{len(body):08x}\n".encode() + body


class SmallCorpus:
    """One complete real occurrence, only to bound validator mutation tests."""

    def __init__(self, full, case):
        self.cases = [case]
        self.continuations = full.continuations
        self.indexes = full.indexes
        self.pins = full.pins
        self.census = full.census
        self.original_sources = full.original_sources
        self.provider_records = full.provider_records
        self.steps = full.steps
        self.pending = full.pending


def native_state(expected, slots):
    result = deepcopy(expected)
    for field in ("passes", "provider_history"):
        for registration in result[field].values():
            identity = registration["contract"]["id"]
            for slot in ("producer", *registration["validators"]):
                key = identity, slot
                if key not in slots:
                    slots[key] = "provider/" + str(901 + len(slots))
                if slot == "producer":
                    registration["producer"] = slots[key]
                else:
                    registration["validators"][slot] = slots[key]
    return result


def response_for(step, request, sequence, input_bytes, output_bytes, slots):
    profile = campaign.declaration()
    exception, diagnostics, result = None, [], step["value"]
    if step["error"] is not None:
        if step["error"] == {"native_state_unavailable": True}:
            diagnostics = [{"code": "pipeline_session_state", "message": "This session has no live manager.", "path": None}]
        else:
            exception = {**step["error"], "attributes": step["error"].get("attributes", {})}
            diagnostics = [{"code": "pipeline_error", "message": exception["message"], "path": None}]
    elif step["state"] is not None:
        result = native_state(step["state"], slots)
    value = {"protocol": profile["protocol"], "profile": profile["profile"], "session_id": request["session_id"],
        "sequence": sequence, "operation": step["operation"], "request_sha256": campaign.digest(request),
        "status": "error" if step["error"] is not None else "ok", "result": result,
        "diagnostics": diagnostics, "exception": exception, "closed": step["operation"] == "close",
        "usage": {"work_charged": 1000000 + sequence * 100, "work_remaining": profile["limits"]["max_work"] - 1000000 - sequence * 100,
            "input_bytes": input_bytes, "output_bytes": output_bytes, "commands": sequence + 1, "retained_bytes": 0},
        "core": campaign.CORE}
    while True:
        encoded = frame(value)
        wanted = output_bytes + len(encoded)
        if value["usage"]["output_bytes"] == wanted:
            return encoded
        value["usage"]["output_bytes"] = wanted


def verify_output():
    return campaign.canonical({"protocol": campaign.CORE["protocol"], "request_id": None, "operation": None,
        "status": "error", "result": None, "diagnostics": [{"code": "unexpected_arguments",
            "message": "Expected standard JSON input or the exact inherited artifact descriptor arguments.", "path": None}],
        "core": {**campaign.CORE, "executable": "verify"}}) + b"\n"


def make_protocol_evidence(receipt):
    """Fabricated byte fixtures exercise the comparator, never native parity."""
    receipt["protocol_checks"] = []
    put = lambda value: campaign.artifact(receipt, value)
    profile = campaign.declaration()
    for ordinal in range(len(campaign.protocol_probes("00000000-0000-4000-8000-000000000000"))):
        nonce = str(uuid4())
        probe = campaign.protocol_probes(nonce)[ordinal]
        output = b""
        for number, request in enumerate(probe["prior"]):
            step = campaign.hello_step() if request["operation"] == "hello" else {
                "operation": "close", "value": None, "state": None, "error": None}
            encoded = response_for(step, request, number,
                sum(len(frame(value)) for value in probe["prior"][:number + 1]), len(output), {})
            output += encoded
        if probe["terminal"]:
            request = probe["binding"]
            value = {"protocol": profile["protocol"], "profile": profile["profile"], "session_id": probe["session_id"],
                "sequence": None if request is None else request["sequence"], "operation": None if request is None else request["operation"],
                "request_sha256": None if request is None else campaign.digest(request), "status": "error", "result": None,
                "diagnostics": [{"code": "pipeline_session_fatal", "message": "Session closed after a framing, identity, resource or internal failure.", "path": None}],
                "exception": None, "closed": True, "core": campaign.CORE,
                "usage": {"commands": probe["commands"], "input_bytes": probe["input_bytes"], "output_bytes": len(output),
                    "work_charged": 2000000, "work_remaining": 10**12 - 2000000, "retained_bytes": 0}}
            while True:
                encoded = frame(value)
                if value["usage"]["output_bytes"] == len(output) + len(encoded):
                    break
                value["usage"]["output_bytes"] = len(output) + len(encoded)
            output += encoded
        receipt["protocol_checks"].append({"id": probe["id"], "session_id": nonce,
            "argv": [receipt["executables"]["core"], profile["argument"]],
            "executable_sha256": receipt["native_inputs"]["sha256"]["biocompiler-core"], "returncode": 0,
            "stdin": put(probe["stdin"]), "stdout": put(output), "stderr": put(campaign.canonical({"hex": ""}))})


def make_receipt(directory, corpus):
    artifacts = directory / campaign.ARTIFACT_DIRECTORY
    artifacts.mkdir(parents=True)
    receipt = {"_artifact_directory": str(artifacts), "artifacts": {}, "checks": [],
        "native_inputs": {"sha256": {"biocompiler-core": "a" * 64, "biocompiler-verify": "b" * 64}},
        "executables": {"core": "/native/biocompiler-core", "verify": "/native/biocompiler-verify"}}
    put = lambda value: campaign.artifact(receipt, value)
    profile = campaign.declaration()
    verify_request = {"protocol": profile["protocol"], "session_id": str(uuid4()), "sequence": 0,
        "operation": "hello", "payload": campaign.hello_step()["payload"]}
    receipt["verify_rejection"] = {"argv": [receipt["executables"]["verify"], profile["argument"]],
        "executable_sha256": "b" * 64, "returncode": 2, "request": put(frame(verify_request)),
        "stdout": put(verify_output()), "stderr": put(campaign.canonical({"hex": ""}))}
    make_protocol_evidence(receipt)
    for case in corpus.cases:
        nonce, slots = str(uuid4()), {}
        row = {"id": case["id"], "case": put(campaign.canonical(case)),
            "continuation": put(campaign.canonical(corpus.continuations[case["id"]])), "frames": [], "pids": [],
            "pid": 123, "returncode": 0, "closed": True, "invalidated": False, "executable_sha256": "a" * 64,
            "stderr": put(campaign.canonical({"hex": ""})), "guard": put(campaign.canonical([
                ["biocompiler.core_pipeline_session", "CorePipelineSession.__init__"],
                ["biocompiler.core_pipeline_session", "CorePipelineSession.call"]]))}
        input_bytes = output_bytes = 0
        for sequence, step in enumerate([campaign.hello_step(), *corpus.steps(case)]):
            request = {"protocol": profile["protocol"], "session_id": nonce, "sequence": sequence,
                "operation": step["operation"], "payload": step["payload"]}
            raw = frame(request)
            input_bytes += len(raw)
            response = response_for(step, request, sequence, input_bytes, output_bytes, slots)
            output_bytes += len(response)
            row["frames"].append({"label": step["label"], "request": put(raw), "response": put(response)})
            row["pids"].append(row["pid"])
        receipt["checks"].append(row)
    receipt["completed_checks"] = len(receipt["checks"])
    receipt["pending"] = put(campaign.canonical(corpus.pending()))
    return receipt


def validate(receipt, corpus):
    return campaign.validate_checks(receipt, corpus,
        campaign.Artifacts(Path(receipt["_artifact_directory"]), receipt["artifacts"]))


def replace_artifact(receipt, owner, key, raw):
    previous = owner[key]
    owner[key] = campaign.artifact(receipt, raw)
    del receipt["artifacts"][previous]
    (Path(receipt["_artifact_directory"]) / (previous + ".bin")).unlink()


class PipelineSessionCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = campaign.Corpus()
        cls.small = SmallCorpus(cls.full, cls.full.cases[0])

    def test_complete_original_recipe_census_and_authority(self):
        operations, error_types, continuation_apis = Counter(), Counter(), Counter()
        observations = 0
        for case in self.full.cases:
            steps = self.full.steps(case)
            operations.update(step["operation"] for step in steps)
            self.assertEqual(steps[0]["payload"], self.full.document("fixed", case["authority"]))
            self.assertEqual(steps[-1]["operation"], "close")
            for step in steps:
                if step["error"] and "type" in step["error"]:
                    error_types[step["error"]["type"]] += 1
            entry = self.full.continuations[case["id"]]
            observed = entry.get("supported_prefix_events", [])
            observations += len(observed)
            continuation_apis.update(event["api"] for event in entry["events"][:len(observed)])
            self.assertEqual(len([step for step in steps if step["family"] == "continuation"]),
                3 * (len(observed) + int(entry["boundary"] is not None)))
            self.assertFalse(any(step["operation"] in ("register", "admit", "import") for step in steps))
        self.assertEqual(len(self.full.cases), 126)
        self.assertEqual(observations, 563)
        self.assertEqual(continuation_apis, {"PassManager.set_dependency": 333, "PassManager.get": 159, "PassManager.result": 71})
        self.assertEqual(error_types, {"PipelineError": 27})
        self.assertEqual(operations["initialize-synthetic"], 86)
        self.assertEqual(operations["initialize-components"], 40)
        self.assertEqual(operations["close"], 126)
        self.assertEqual(self.full.census["pending_callback_suffix"] + self.full.census["excluded_prefix"] +
            self.full.census["excluded_suffix"], 287)
        self.assertEqual(len(self.full.excluded), 10)
        self.assertEqual(len(self.full.provider_records), 841)
        self.assertEqual(len(self.full.original_sources), 267)

    def test_original_failure_keeps_real_nested_partial_state_and_missing_state_error(self):
        failures = [case for case in self.full.cases if case["outcome"] == "raised"]
        component = next(case for case in failures if case["api"] == "run_component_pipeline")
        self.assertIsNone(component["manager_state"])
        steps = self.full.steps(component)
        self.assertIsNotNone(steps[1]["state"])
        self.assertIn("mechanism", steps[1]["state"]["records"])
        missing = [self.full.steps(case)[1] for case in failures if self.full.steps(case)[1]["state"] is None]
        self.assertEqual(len(missing), 1)
        self.assertEqual(missing[0]["error"], {"native_state_unavailable": True})

    def test_every_original_state_and_error_has_a_complete_comparison_recipe(self):
        states = 0
        errors = Counter()
        observed_slots = set()
        for case in self.full.cases:
            aliases, slots = campaign.Providers(), {}
            for step in self.full.steps(case):
                request = {"session_id": str(uuid4())}
                encoded = response_for(step, request, 0, 0, 0, slots)
                response = campaign.frame_body(encoded)
                campaign.check_response(response, step, self.full, aliases)
                states += step["state"] is not None
                if step["error"] is not None:
                    errors[step["error"].get("type", "missing manager")] += 1
            observed_slots.update(aliases.slots)
        self.assertEqual(states, 1493)
        self.assertEqual(errors, {"PipelineError": 27, "missing manager": 1})
        self.assertEqual(observed_slots, set(campaign.SLOTS))

    def test_provider_identity_is_bijective_and_persists_across_original_captures(self):
        states = [step for step in self.small.steps(self.small.cases[0]) if step["state"] is not None]
        first = states[0]
        continuation = next(step for step in states if step["family"] == "continuation")
        aliases, slots = campaign.Providers(), {}
        for step in (first, continuation):
            campaign.check_response({"status": "ok", "exception": None, "diagnostics": [], "closed": False,
                "result": native_state(step["state"], slots)}, step, self.full, aliases)
        changed = native_state(continuation["state"], slots)
        for field in ("passes", "provider_history"):
            next(entry for entry in changed[field].values() if entry["contract"]["id"] == "intent_to_behavior")["producer"] = "provider/999"
        with self.assertRaisesRegex(AssertionError, "physical identity|between original captures"):
            aliases.align(changed, continuation["state"], self.full.indexes["continuation"]["providers"], "continuation")
        changed = native_state(first["state"], slots)
        for field in ("passes", "provider_history"):
            entry = next(entry for entry in changed[field].values() if entry["contract"]["id"] == "intent_to_behavior")
            entry["validators"]["preservation"] = entry["producer"]
        with self.assertRaisesRegex(AssertionError, "aliased"):
            campaign.Providers().align(changed, first["state"], self.full.indexes["fixed"]["providers"], "fixed")

    def test_complete_frames_validate_and_forged_state_usage_binding_or_scope_fails(self):
        mutations = {
            "request binding": lambda value: value.update(request_sha256="f" * 64),
            "reply sequence": lambda value: value.update(sequence=value["sequence"] + 1),
            "old output accounting": lambda value: value["usage"].update(output_bytes=0),
            "command reset": lambda value: value["usage"].update(commands=1),
            "resource reset": lambda value: value["usage"].update(work_charged=1, work_remaining=10**12 - 1),
            "accepted substituted state": lambda value: value["result"]["dependencies"].update(catalog="corrupted"),
            "dropped state": lambda value: value["result"].pop("records"),
            "aliased provider": lambda value: value["result"]["passes"]["behavior_to_synthetic"].update(producer="provider/901"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                receipt = make_receipt(Path(temporary), self.small)
                self.assertEqual(len(validate(receipt, self.small)["original_calls"]), 1)
                row = receipt["checks"][0]["frames"][2]
                raw = (Path(receipt["_artifact_directory"]) / (row["response"] + ".bin")).read_bytes()
                response = campaign.frame_body(raw)
                mutate(response)
                replace_artifact(receipt, row, "response", frame(response))
                with self.assertRaises(AssertionError):
                    validate(receipt, self.small)

    def test_missing_occurrences_pending_evidence_process_reuse_and_fallback_are_rejected(self):
        mutations = [lambda r: r.update(completed_checks=0), lambda r: r["checks"][0]["pids"].__setitem__(1, 999),
            lambda r: r["checks"][0].update(invalidated=True), lambda r: r["checks"][0].update(returncode=2),
            lambda r: r["checks"][0]["frames"].pop(), lambda r: r["verify_rejection"].update(returncode=0)]
        for mutate in mutations:
            with tempfile.TemporaryDirectory() as temporary:
                receipt = make_receipt(Path(temporary), self.small)
                mutate(receipt)
                with self.assertRaises(AssertionError):
                    validate(receipt, self.small)
        with tempfile.TemporaryDirectory() as temporary:
            receipt = make_receipt(Path(temporary), self.small)
            replace_artifact(receipt, receipt, "pending", b"[]")
            with self.assertRaisesRegex(AssertionError, "Excluded original"):
                validate(receipt, self.small)
        namespace = {"__name__": "biocompiler.compiler.pipeline"}
        exec("def semantic_fallback(): return None", namespace)
        previous = sys.getprofile()
        with self.assertRaisesRegex(AssertionError, "semantic fallback"):
            with campaign.guarded_execution():
                namespace["semantic_fallback"]()
        self.assertIs(sys.getprofile(), previous)

    def test_all_artifact_bytes_are_rehashed_even_after_inventory_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            receipt = make_receipt(Path(temporary), self.small)
            directory = Path(receipt["_artifact_directory"])
            artifacts = campaign.Artifacts(directory, receipt["artifacts"])
            pin = receipt["checks"][0]["frames"][-1]["response"]
            path = directory / (pin + ".bin")
            raw = path.read_bytes()
            path.write_bytes(raw[:-1] + b" ")
            with self.assertRaisesRegex(AssertionError, "changed after inventory"):
                campaign.validate_checks(receipt, self.small, artifacts)
            with self.assertRaisesRegex(AssertionError, "declared identity"):
                campaign.Artifacts(directory, receipt["artifacts"])

    def test_protocol_probes_reject_missing_extra_unbound_or_nonterminal_replies(self):
        for mutation in ("extra frame", "not closed", "wrong binding", "accepted", "wrong input", "missing case"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as temporary:
                receipt = make_receipt(Path(temporary), self.small)
                artifacts = campaign.Artifacts(Path(receipt["_artifact_directory"]), receipt["artifacts"])
                self.assertEqual(len(campaign.validate_protocol_checks(receipt, artifacts)), 17)
                row = receipt["protocol_checks"][0]
                if mutation == "missing case":
                    receipt["protocol_checks"].pop()
                elif mutation == "wrong input":
                    replace_artifact(receipt, row, "stdin", b"0001")
                else:
                    raw = artifacts.raw(row["stdout"])
                    if mutation == "extra frame":
                        changed = raw + raw
                    else:
                        response = campaign.frame_body(raw)
                        if mutation == "not closed":
                            response["closed"] = False
                        elif mutation == "wrong binding":
                            response["sequence"] = 0
                        else:
                            response["status"] = "ok"
                        changed = frame(response)
                    replace_artifact(receipt, row, "stdout", changed)
                artifacts = campaign.Artifacts(Path(receipt["_artifact_directory"]), receipt["artifacts"])
                with self.assertRaises(AssertionError):
                    campaign.validate_protocol_checks(receipt, artifacts)

    def test_raw_probe_driver_executes_each_complete_byte_recipe_in_a_python_child(self):
        # A source fixture child proves byte collection and process selection.
        # The same campaign runs against actual OCaml executables only in CI.
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            receipt = make_receipt(directory, self.small)
            artifacts = campaign.Artifacts(Path(receipt["_artifact_directory"]), receipt["artifacts"])
            nonces = [row["session_id"] for row in receipt["protocol_checks"]]
            fixtures = {artifacts.raw(row["stdin"]).hex(): artifacts.raw(row["stdout"]).hex()
                for row in receipt["protocol_checks"]}
            (directory / "probe-stimuli.json").write_text(json.dumps(fixtures), encoding="utf-8")
            script = directory / "biocompiler-core"
            script.write_text("#!" + sys.executable + "\n" + '''import json,sys
from pathlib import Path
assert sys.argv[1:]==['--pipeline-session-v1']
fixtures=json.loads(Path(__file__).with_name('probe-stimuli.json').read_text())
raw=sys.stdin.buffer.read()
output=bytes.fromhex(fixtures[raw.hex()])
sys.stdout.buffer.write(output[:5]);sys.stdout.buffer.flush()
sys.stdout.buffer.write(output[5:]);sys.stdout.buffer.flush()
''', encoding="utf-8")
            script.chmod(0o700)
            pin = campaign.sha(script.read_bytes())
            receipt["executables"]["core"] = str(script)
            receipt["native_inputs"]["sha256"]["biocompiler-core"] = pin
            with patch.object(campaign, "uuid4", side_effect=nonces), \
                    patch.object(campaign.subprocess, "Popen", wraps=campaign.subprocess.Popen) as launched:
                campaign.protocol_campaign(script, pin, receipt)
            self.assertEqual(launched.call_count, 17)
            artifacts = campaign.Artifacts(Path(receipt["_artifact_directory"]), receipt["artifacts"])
            self.assertEqual(len(campaign.validate_protocol_checks(receipt, artifacts)), 17)

    def test_real_python_child_stays_live_through_complete_original_continuation(self):
        # This deliberately emits fixture responses from a Python executable.
        # Only framing, recipe authority, process lifetime and the harness are
        # under test; an installed native campaign must still prove semantics.
        from biocompiler.core_client import CoreClient
        importlib.import_module("biocompiler.core_pipeline_session")
        case = next(case for case in self.full.cases if case["outcome"] == "returned" and
            any(step["error"] is not None for step in self.full.steps(case)))
        corpus = SmallCorpus(self.full, case)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            receipt = make_receipt(directory, corpus)
            prepared = receipt["checks"][0]["frames"]
            recipes = [{"request": campaign.frame_body((directory / campaign.ARTIFACT_DIRECTORY / (entry["request"] + ".bin")).read_bytes()),
                "response": campaign.frame_body((directory / campaign.ARTIFACT_DIRECTORY / (entry["response"] + ".bin")).read_bytes())}
                for entry in prepared]
            fixture = directory / "transport-stimulus.json"
            fixture.write_text(json.dumps(recipes), encoding="utf-8")
            script = directory / "biocompiler-core"
            script.write_text("#!" + sys.executable + "\n" + '''import hashlib,json,sys
from pathlib import Path
assert sys.argv[1:]==['--pipeline-session-v1']
recipes=json.loads(Path(__file__).with_name('transport-stimulus.json').read_text())
for recipe in recipes:
 header=sys.stdin.buffer.read(9)
 assert len(header)==9
 raw=sys.stdin.buffer.read(int(header[:8],16))
 request=json.loads(raw)
 expected=recipe['request'];expected['session_id']=request['session_id']
 assert request==expected
 response=recipe['response'];response['session_id']=request['session_id']
 response['request_sha256']=hashlib.sha256(raw).hexdigest()
 body=json.dumps(response,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
 framed=f'{len(body):08x}\\n'.encode()+body
 for part in (framed[:3],framed[3:9],framed[9:]):
  sys.stdout.buffer.write(part);sys.stdout.buffer.flush()
''', encoding="utf-8")
            script.chmod(0o700)
            # Remove prebuilt evidence: the campaign must capture new live I/O.
            for path in (directory / campaign.ARTIFACT_DIRECTORY).iterdir():
                path.unlink()
            receipt["checks"], receipt["artifacts"] = [], {}
            verify = directory / "biocompiler-verify"
            verify.write_text("#!" + sys.executable + "\nimport sys\nassert sys.argv[1:]==['--pipeline-session-v1']\n"
                + "sys.stdout.buffer.write(" + repr(verify_output()) + ")\nraise SystemExit(2)\n", encoding="utf-8")
            verify.chmod(0o700)
            core_pin, verify_pin = campaign.sha(script.read_bytes()), campaign.sha(verify.read_bytes())
            receipt["native_inputs"]["sha256"] = {"biocompiler-core": core_pin, "biocompiler-verify": verify_pin}
            receipt["executables"] = {"core": str(script), "verify": str(verify)}
            campaign.verify_rejection(verify, verify_pin, receipt)
            make_protocol_evidence(receipt)
            campaign.campaign(CoreClient(script, expected_sha256=core_pin), corpus, receipt)
            receipt["completed_checks"] = len(receipt["checks"])
            self.assertEqual(len(validate(receipt, corpus)["original_calls"]), 1)
            self.assertEqual(len(set(receipt["checks"][0]["pids"])), 1)

    def test_four_runtime_comparison_binds_complete_receipts_binary_bytes_and_current_authority(self):
        revision, source_revision, run_id = "1" * 40, "2" * 40, "42"
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            root, native_root = directory / "receipts", directory / "native"
            root.mkdir()
            native_root.mkdir()
            for platform, (system, machine) in campaign.PLATFORMS.items():
                native = native_root / platform
                native.mkdir()
                pins = {}
                for role in ("core", "verify"):
                    path = native / ("biocompiler-" + role)
                    path.write_bytes((platform + role + " unit-test bytes, never executed").encode())
                    pins[path.name] = campaign.sha(path.read_bytes())
                (native / "binaries.json").write_bytes(campaign.canonical({"revision": revision,
                    "system": system, "machine": machine, "sha256": pins}) + b"\n")
                inputs = campaign.verify_binaries(native, revision, platform)
                for python in campaign.PYTHONS:
                    slot = root / ("realization-" + platform + "-py" + python)
                    receipt = make_receipt(slot, self.small)
                    receipt.update(schema_version=campaign.SCHEMA, status="success", scope=campaign.SCOPE,
                        revision=revision, source_revision=source_revision, run_id=run_id, python_version=python + ".9",
                        system=system, machine=machine, native_platform=platform, artifact_directory=campaign.ARTIFACT_DIRECTORY,
                        native_inputs=inputs, package_path=str(directory / "installed" / "__init__.py"),
                        transport_sources=campaign.source_pins("src/" + name.replace(".", "/") + ".py" for name in sorted(campaign.TRANSPORT_MODULES)),
                        campaign_sources=campaign.source_pins(campaign.SOURCES), **campaign.metadata(self.small))
                    for row in receipt["checks"]:
                        row["executable_sha256"] = pins["biocompiler-core"]
                    for row in receipt["protocol_checks"]:
                        row["executable_sha256"] = pins["biocompiler-core"]
                    receipt["verify_rejection"]["executable_sha256"] = pins["biocompiler-verify"]
                    del receipt["_artifact_directory"]
                    (slot / campaign.RECEIPT_FILE).write_bytes(campaign.canonical(receipt) + b"\n")
                    (slot / "native-inputs.json").write_bytes(campaign.canonical({**inputs, "run_id": run_id,
                        "source_revision": source_revision, "python_version": python + ".9"}) + b"\n")
            with patch.object(campaign, "Corpus", return_value=self.small):
                result = campaign.compare(root, native_root, revision=revision, source_revision=source_revision, run_id=run_id)
                self.assertEqual(len(result["receipts"]), 4)
                self.assertTrue(all(item["complete_artifacts"] for item in result["receipts"].values()))
                with self.assertRaisesRegex(AssertionError, "Stale session native inputs"):
                    campaign.compare(root, native_root, revision=revision, source_revision=source_revision, run_id="43")
                path = native_root / "linux-x86_64" / "biocompiler-core"
                path.write_bytes(b"substituted executable")
                with self.assertRaisesRegex(ValueError, "executable bytes differ"):
                    campaign.compare(root, native_root, revision=revision, source_revision=source_revision, run_id=run_id)


if __name__ == "__main__":
    unittest.main()
