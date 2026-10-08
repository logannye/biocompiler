"""Actual Python protocol children and strict rich-helper evidence mutations.

These fixtures validate the installed-campaign machinery, not OCaml execution.
The production campaign still enumerates every original occurrence on hosted CI.
"""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from tools import check_native_synthetic_inspection as p

REVISION, SOURCE, RUN = "a" * 40, "b" * 40, "inspection-fixture-run"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(p.canonical(value) + b"\n")


class SyntheticInspectionCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = p.Corpus()
        supplement = p.decode((p.ROOT / "tests/conformance/synthetic-inspection-supplemental-v1.json").read_bytes())
        cls.small = SimpleNamespace(cases=deepcopy(supplement["cases"]), pins=deepcopy(cls.full.pins),
            census=deepcopy(cls.full.census), original_count=cls.full.original_count)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.actual_directory = Path(cls.temporary.name) / "actual"
        cls.actual = cls.run_actual(cls.actual_directory, cls.small)

    @staticmethod
    def capabilities(role):
        from biocompiler.core_client import LIMITS
        declaration = p.declaration()
        return {"schema_version": "biocompiler.core_capabilities.v1",
            "operations": ["capabilities", *(declaration["operations"] if role == "core" else [])],
            "profiles": {"synthetic_inspection": declaration} if role == "core" else {},
            "intent_schemas": ["biocompiler.intent.v0.2"], "canonicalization": "python-json-v1",
            "validation_scopes": [declaration["validation_scope"]] if role == "core" else [],
            "limits": LIMITS, "claim_scope": "Python protocol fixture; no native execution or acceptance"}

    @classmethod
    def run_actual(cls, directory, corpus):
        from biocompiler.core_client import CoreClient
        for module in p.SOURCE_MODULES:
            p.importlib.import_module(module)
        artifacts = directory / p.ARTIFACT_DIRECTORY
        artifacts.mkdir(parents=True)
        receipt = {"checks": [], "artifacts": {}, "_artifact_directory": str(artifacts),
            "executables": {role: str(directory / ("biocompiler-" + role)) for role in p.ROLES}}
        table = {}
        for (role, _), case in p.expected_cases(corpus).items():
            if role == "verify":
                response, code = p.envelope(role, "replaced", case["operation"], "unsupported", None, [p.UNSUPPORTED]), 3
            elif case["error"] is not None:
                response, code = p.envelope(role, "replaced", case["operation"], "error", None, [case["error"]]), 2
            else:
                response, code = p.envelope(role, "replaced", case["operation"], "ok", p.expected_semantic(case), []), 0
            table[role + ":" + case["operation"] + ":" + p.digest(case["payload"])] = [response, code]
        write(directory / "fixture.json", {"table": table, "capabilities": {role: cls.capabilities(role) for role in p.ROLES}})
        script = '''import hashlib,json,pathlib,sys
role=pathlib.Path(sys.argv[0]).name.removeprefix("biocompiler-")
data=json.loads(pathlib.Path(sys.argv[0]).with_name("fixture.json").read_bytes())
request=json.loads(sys.stdin.buffer.read())
def enc(x):return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
if request["operation"]=="capabilities":
 response={"protocol":"biocompiler.core.v1","request_id":request["request_id"],"operation":"capabilities","status":"ok","diagnostics":[],"result":data["capabilities"][role],"core":{"implementation":"ocaml","version":"0.1.0","protocol":"biocompiler.core.v1","executable":role}}
 code=0
else:
 response,code=data["table"][role+":"+request["operation"]+":"+hashlib.sha256(enc(request["payload"])).hexdigest()]
 response["request_id"]=request["request_id"]
sys.stdout.buffer.write(enc(response)+b"\\n")
sys.exit(code)
'''
        clients = []
        for role in p.ROLES:
            path = Path(receipt["executables"][role])
            path.write_text("#!" + sys.executable + "\n" + script)
            path.chmod(0o700)
            clients.append(CoreClient(path, role=role, expected_sha256=p.sha(path.read_bytes())))
        p.campaign(clients, corpus, receipt)
        receipt["completed_checks"] = len(receipt["checks"])
        p.validate_checks(receipt, corpus, p.Artifacts(artifacts, receipt["artifacts"]))
        return receipt

    def test_full_original_census_and_complete_public_method_bindings(self):
        self.assertEqual(self.full.original_count, 9632)
        self.assertEqual(len(self.full.cases), 9660)
        original = self.full.cases[:9632]
        self.assertEqual(sum(case["error"] is not None for case in original), 13)
        self.assertEqual(Counter(case["api"] for case in original), {
            "ComponentRegistry.lock": 926, "ComponentRegistry.resolve": 724,
            "ComponentRegistry.select": 35, "ComponentRegistry.verify_selection": 8,
            "CheckResult.freshness": 42, "CheckResult.is_fresh": 4,
            "CheckResult.exercised_requirement_ids": 7781, "DependencySnapshot.changed": 42,
            "SelectionResult.outcome": 70})
        self.assertEqual(len(p.expected_cases(self.full)), 9668)
        for case in self.full.cases:
            self.assertIn(case["api"], p.PUBLIC_METHODS)
            self.assertEqual(set(case["payload"]), set(p.declaration()["payload_fields"][case["operation"]]))
            if case["error"] is None:
                value = p.expected_semantic(case)
                self.assertEqual(value["value"], case["expected_value"])
                self.assertEqual(value["supplied_authority_fingerprint"], p.digest(case["payload"]))
                self.assertEqual(value["input_fingerprints"], {key: p.digest(item) for key, item in case["payload"].items()
                    if key not in ("profile", "limits")})

    def test_actual_public_helpers_full_values_properties_and_error_causes(self):
        self.assertEqual(len(self.actual["checks"]), 36)
        self.assertEqual(sum(len(row["exchanges"]) for row in self.actual["checks"]) + 1, 65)
        self.assertEqual({row["operation"] for row in self.actual["checks"] if row["role"] == "verify"},
                         set(p.declaration()["operations"]))
        self.assertEqual(sum(case["error"] is not None for case in self.small.cases), 8)
        artifacts = p.Artifacts(self.actual_directory / p.ARTIFACT_DIRECTORY, self.actual["artifacts"])
        for row in self.actual["checks"]:
            p.check_guard(artifacts.json(row["guard"]), p.expected_cases(self.small)[row["role"], row["id"]], row["role"])

    def matrix(self, directory):
        root, natives = Path(directory) / "realization", Path(directory) / "native"
        for target, (system, machine) in p.PLATFORMS.items():
            native = natives / target
            native.mkdir(parents=True)
            pins = {}
            for role in p.ROLES:
                path = native / ("biocompiler-" + role)
                path.write_bytes((target + role + "nonexecutable-fixture-data").encode())
                pins[path.name] = p.sha(path.read_bytes())
            write(native / "binaries.json", dict(revision=REVISION, system=system, machine=machine, sha256=pins))
            inputs = p.verify_binaries(native, REVISION, target)
            for python in p.PYTHONS:
                slot = root / ("realization-" + target + "-py" + python)
                slot.mkdir(parents=True)
                artifacts = slot / p.ARTIFACT_DIRECTORY
                shutil.copytree(self.actual_directory / p.ARTIFACT_DIRECTORY, artifacts)
                receipt = deepcopy(self.actual)
                del receipt["_artifact_directory"]
                old_pins = set()
                for exchange in [item for row in receipt["checks"] for item in row["exchanges"]] + [receipt["verify_capabilities"]]:
                    identity = str(uuid4())
                    for key, newline in (("request", b""), ("response", b"\n")):
                        previous = exchange[key]
                        raw = p.decode((artifacts / (previous + ".bin")).read_bytes())
                        raw["request_id"] = identity
                        value = p.canonical(raw) + newline
                        pin = p.sha(value)
                        (artifacts / (pin + ".bin")).write_bytes(value)
                        receipt["artifacts"][pin] = {"path": pin + ".bin", "sha256": pin, "bytes": len(value)}
                        exchange[key] = pin
                        old_pins.add(previous)
                remaining = p.canonical(receipt["checks"]) + p.canonical(receipt["verify_capabilities"])
                for pin in old_pins:
                    if pin.encode() not in remaining:
                        del receipt["artifacts"][pin]
                        (artifacts / (pin + ".bin")).unlink()
                receipt["executables"] = {role: str(native / ("biocompiler-" + role)) for role in p.ROLES}
                for row in receipt["checks"]:
                    for item in row["exchanges"]:
                        item["executable"] = receipt["executables"][row["role"]]
                receipt["verify_capabilities"]["executable"] = receipt["executables"]["verify"]
                write(slot / "native-inputs.json", dict(inputs, run_id=RUN, source_revision=SOURCE, python_version=python + ".9"))
                receipt.update(schema_version=p.SCHEMA, status="success", scope=p.SCOPE, revision=REVISION,
                    execution=p.PARALLEL_EXECUTION,
                    source_revision=SOURCE, run_id=RUN, system=system, machine=machine, native_platform=target,
                    python_version=python + ".9", native_inputs=inputs, package_path="/installed/biocompiler/__init__.py",
                    artifact_directory=p.ARTIFACT_DIRECTORY, **p.metadata(self.small),
                    transport_sources=p.source_pins("src/" + name.replace(".", "/") + ".py" for name in sorted(p.SOURCE_MODULES)),
                    campaign_sources=p.source_pins(p.SOURCES))
                # Current acceptance requires both complete raw worker proofs,
                # even when this small fixture starts from one serial peer run.
                from tools import synthetic_inspection_workers as workers
                worker_root = slot / workers.ROOT_NAME
                for index in (0, 1):
                    folder = worker_root / str(index)
                    worker_artifacts = folder / p.ARTIFACT_DIRECTORY
                    worker_artifacts.mkdir(parents=True)
                    part = deepcopy(receipt)
                    part.update(schema_version=workers.SCHEMA, worker_index=index, worker_count=2,
                                execution={"mode":"occurrence_worker","workers":2,"index":index})
                    part["checks"] = [part["checks"][ordinal] for ordinal in workers.ordinals(self.small, index)]
                    part["completed_checks"] = len(part["checks"])
                    if index:
                        part.pop("verify_capabilities"); part.pop("verify_capability_guard")
                    referenced = p.canonical(part["checks"]) + p.canonical({key:part[key] for key in
                        ("verify_capabilities","verify_capability_guard") if key in part})
                    part["artifacts"] = {identity:entry for identity,entry in part["artifacts"].items()
                                         if identity.encode() in referenced}
                    for entry in part["artifacts"].values():
                        shutil.copyfile(artifacts / entry["path"], worker_artifacts / entry["path"])
                    write(folder / "receipt.json", part)
                    (folder / "worker.log").write_text("complete inert worker diagnostics\n")
                _, _, receipt["occurrence_workers"] = workers.collect(worker_root, receipt, self.small)
                write(slot / p.RECEIPT_FILE, receipt)
        return root, natives

    def compare(self, root, natives):
        with patch.object(p, "Corpus", return_value=self.small):
            return p.compare(root, natives, revision=REVISION, source_revision=SOURCE, run_id=RUN)

    def test_four_runtime_matrix_binds_sources_run_binary_inventory_and_occurrences(self):
        with tempfile.TemporaryDirectory() as directory:
            root, natives = self.matrix(directory)
            self.assertEqual(self.compare(root, natives)["status"], "success")
            path = root / "realization-linux-x86_64-py3.11" / p.RECEIPT_FILE
            original = p.decode(path.read_bytes())
            changes = (
                lambda x: x.update(source_revision="c" * 40),
                lambda x: x.update(run_id="stale"),
                lambda x: x.update(completed_checks=True),
                lambda x: x.update(original_occurrences=9631),
                lambda x: x["checks"].pop(),
                lambda x: x["checks"].__setitem__(1, deepcopy(x["checks"][0])),
                lambda x: x["checks"][0].update(api="CheckResult.is_fresh"),
                lambda x: x["checks"][0]["exchanges"][1].update(executable="biocompiler-core"),
                lambda x: x["transport_sources"].pop(next(iter(x["transport_sources"]))),
                lambda x: x["native_inputs"]["sha256"].update({"biocompiler-core": "0" * 64}),
                lambda x: x["verify_capabilities"].update(exit_code=False),
            )
            for mutate in changes:
                receipt = deepcopy(original)
                mutate(receipt)
                write(path, receipt)
                with self.assertRaises(AssertionError):
                    self.compare(root, natives)
            write(path, original)
            missing = root / "realization-linux-x86_64-py3.14"
            renamed = missing.with_name("unclaimed-runtime")
            missing.rename(renamed)
            with self.assertRaisesRegex(AssertionError, "four-runtime"):
                self.compare(root, natives)
            renamed.rename(missing)
            executable = natives / "linux-x86_64" / "biocompiler-core"
            executable.write_bytes(b"different complete executable")
            with self.assertRaises((AssertionError, ValueError)):
                self.compare(root, natives)

    def test_rehashed_full_wire_public_evidence_and_guard_forgeries_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root, natives = self.matrix(directory)
            slot = root / "realization-linux-x86_64-py3.11"
            path, artifacts = slot / p.RECEIPT_FILE, slot / p.ARTIFACT_DIRECTORY
            original = p.decode(path.read_bytes())
            error_index = next(i for i, row in enumerate(original["checks"]) if row["role"] == "core" and
                p.expected_cases(self.small)["core", row["id"]]["error"] is not None)
            def forge_value(wire):
                wire["result"]["value"] = {"nodes": []}
                wire["result"]["value_fingerprint"] = p.digest(wire["result"]["value"])
            cases = (
                (lambda r: r["checks"][0]["exchanges"][1], "response", forge_value, "native receipt"),
                (lambda r: r["checks"][0]["exchanges"][1], "response", lambda x: x["result"].update(claim_scope="human-use admitted"), "native receipt"),
                (lambda r: r["checks"][0]["exchanges"][1], "response", lambda x: x["result"]["input_fingerprints"].update(mechanism="0" * 64), "native receipt"),
                (lambda r: r["checks"][0]["exchanges"][1], "response", lambda x: x["core"].update(executable="verify"), "native receipt"),
                (lambda r: r["checks"][error_index]["exchanges"][1], "response", lambda x: x["diagnostics"][0].update(message="changed"), "native receipt"),
                (lambda r: r["checks"][0]["exchanges"][1], "request", lambda x: x["payload"]["mechanism"].update(name="changed"), "helper request"),
                (lambda r: r["checks"][0], "public", lambda x: x.update(value=[]), "public presentation"),
                (lambda r: r["checks"][0], "evidence", lambda x: x.update(case="different original"), "original.*evidence"),
                (lambda r: r["checks"][0], "guard", lambda x: x.__setitem__(slice(None), sorted(x + [
                    ["biocompiler.semantics.evaluator", "evaluate", "output", ""]])), "Forbidden.*guard"),
                (lambda r: r["checks"][0]["exchanges"][0], "response", lambda x: x["result"]["profiles"]["synthetic_inspection"]["resources"]["protocol"].update(max_work=True), "capability"),
                (lambda r: r["verify_capabilities"], "response", lambda x: x["result"]["validation_scopes"].append(p.declaration()["validation_scope"]), "Verifier advertised"),
            )
            for locate, key, mutate, message in cases:
                receipt = deepcopy(original)
                entry = locate(receipt)
                previous = entry[key]
                previous_path = artifacts / (previous + ".bin")
                previous_bytes = previous_path.read_bytes()
                value = p.decode(previous_bytes)
                mutate(value)
                raw = p.canonical(value) + (b"\n" if key == "response" else b"")
                pin = p.sha(raw)
                target = artifacts / (pin + ".bin")
                target_previous = target.read_bytes() if target.exists() else None
                target.write_bytes(raw)
                entry[key] = pin
                receipt["artifacts"][pin] = {"path": pin + ".bin", "sha256": pin, "bytes": len(raw)}
                # Keep the inventory fully coherent so only content validation
                # can reject a rehashed counterfeit, never an orphaned old file.
                remaining = p.canonical(receipt["checks"]) + p.canonical(receipt["verify_capabilities"])
                removed = previous.encode() not in remaining
                if removed:
                    del receipt["artifacts"][previous]
                    previous_path.unlink()
                write(path, receipt)
                with self.assertRaisesRegex(AssertionError, "(?i)" + message):
                    self.compare(root, natives)
                if target_previous is None:
                    target.unlink()
                else:
                    target.write_bytes(target_previous)
                if removed:
                    previous_path.write_bytes(previous_bytes)
            write(path, original)

    def test_extra_missing_symlinked_and_corrupted_complete_artifacts_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root, natives = self.matrix(directory)
            slot = root / "realization-linux-x86_64-py3.11"
            receipt = p.decode((slot / p.RECEIPT_FILE).read_bytes())
            artifacts = slot / p.ARTIFACT_DIRECTORY
            extra = artifacts / ("f" * 64 + ".bin")
            extra.write_bytes(b"extra evidence")
            with self.assertRaisesRegex(AssertionError, "artifact"):
                self.compare(root, natives)
            extra.unlink()
            pin = receipt["checks"][0]["authority"]
            path = artifacts / (pin + ".bin")
            original = path.read_bytes()
            path.write_bytes(original + b" ")
            with self.assertRaisesRegex(AssertionError, "bytes differ"):
                self.compare(root, natives)
            path.unlink()
            with self.assertRaisesRegex(AssertionError, "artifact"):
                self.compare(root, natives)
            outside = Path(directory) / "same-authority.bin"
            outside.write_bytes(original)
            path.symlink_to(outside)
            with self.assertRaisesRegex(AssertionError, "[Ss]ymlink|artifact"):
                self.compare(root, natives)

    def test_uuid_projection_rejects_reuse_noncanonical_ids_and_response_mismatch(self):
        identity, seen = str(uuid4()), set()
        p.uuid4_identity(identity, seen)
        for value in (identity, identity.upper(), "00000000-0000-1000-8000-000000000000", True, None):
            with self.assertRaises(AssertionError):
                p.uuid4_identity(value, seen)
        with tempfile.TemporaryDirectory() as directory:
            root, natives = self.matrix(directory)
            slot = root / "realization-linux-x86_64-py3.11"
            path = slot / p.RECEIPT_FILE
            receipt = p.decode(path.read_bytes())
            exchange = receipt["checks"][0]["exchanges"][1]
            old = exchange["response"]
            old_path = slot / p.ARTIFACT_DIRECTORY / (old + ".bin")
            wire = p.decode(old_path.read_bytes())
            wire["request_id"] = str(uuid4())
            raw = p.canonical(wire) + b"\n"
            pin = p.sha(raw)
            old_path.unlink()
            del receipt["artifacts"][old]
            (slot / p.ARTIFACT_DIRECTORY / (pin + ".bin")).write_bytes(raw)
            receipt["artifacts"][pin] = {"path": pin + ".bin", "sha256": pin, "bytes": len(raw)}
            exchange["response"] = pin
            write(path, receipt)
            with self.assertRaisesRegex(AssertionError, "native receipt"):
                self.compare(root, natives)

    def test_python_semantic_fallback_and_unreviewed_import_are_denied(self):
        for module, name in (("biocompiler.ir.mechanism", "MechanismProgram.topological_nodes"),
            ("biocompiler.verification.evidence", "CheckResult.freshness"),
            ("biocompiler.registry.components", "ComponentRegistry.resolve"),
            ("biocompiler.ir.components", "Component.to_dict")):
            scope = {"__name__": module}
            exec("def forbidden(): return None", scope)
            scope["forbidden"].__code__ = scope["forbidden"].__code__.replace(co_qualname=name)
            with self.assertRaisesRegex(AssertionError, "semantic fallback"):
                with p.guarded_execution():
                    scope["forbidden"]()
        with self.assertRaisesRegex(AssertionError, "Unreviewed"):
            with p.guarded_execution():
                __import__("biocompiler.registry.components")


if __name__ == "__main__":
    unittest.main()
