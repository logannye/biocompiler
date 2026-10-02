"""Pure Python fixture-process and complete-byte comparator mutation tests."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from tools import check_native_synthetic_producer as p

REVISION, SOURCE, RUN = "a" * 40, "b" * 40, "77"


class SyntheticProducerCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = p.Corpus()

    def small(self):
        corpus = object.__new__(p.Corpus)
        corpus.profiles = self.full.profiles
        corpus.declaration = self.full.declaration
        # Every service outcome, operation and error attachment gets an actual
        # fixture process; the complete production census has its separate gate.
        conditions = (
            lambda row: row["operation"] == "generate-synthetic" and row["expected"] is not None,
            lambda row: row["operation"] == "select-synthetic" and row["expected"] is not None,
            lambda row: row["operation"] == "adapt-synthetic-components" and row["expected"] is not None,
            lambda row: row["generation_error"] is not None and row["generation_error"]["source"] is not None,
            lambda row: row["operation"] == "select-synthetic" and row["generation_error"] is not None,
            lambda row: row["error"] is not None,
        )
        corpus.cases = [deepcopy(next(row for row in self.full.cases if condition(row))) for condition in conditions]
        corpus.library = [deepcopy(self.full.library[0]), deepcopy(next(row for row in self.full.library if row["reason"] == "injected_producer"))]
        corpus.verify_cases = deepcopy(self.full.verify_cases)
        return corpus

    def test_complete_original_occurrence_and_error_census(self):
        self.assertEqual(len(self.full.cases), 1226)
        self.assertEqual(len(self.full.library), 1146)
        self.assertEqual(Counter(row["operation"] for row in self.full.cases),
            {"generate-synthetic": 1086, "select-synthetic": 36, "adapt-synthetic-components": 104})
        self.assertEqual(Counter(row["reason"] for row in self.full.library), {"private_proposal": 1144, "injected_producer": 2})
        self.assertEqual(sum(row["generation_error"] is not None for row in self.full.cases), 33)
        self.assertEqual(sum(row["error"] is not None for row in self.full.cases), 5)
        self.assertEqual(len(self.full.expected()), 1229)
        for case in self.full.cases:
            if case["error"] is None:
                value = p.expected_semantic(self.full, case)
                self.assertEqual(value["record_fingerprint"], None if case["expected"] is None else p.sha(case["expected"]))

    @staticmethod
    def capabilities(corpus, role):
        from biocompiler.core_client import LIMITS
        profiles = deepcopy(corpus.profiles) if role == "core" else {}
        return {"schema_version": "biocompiler.core_capabilities.v1", "operations": ["capabilities", *(
            p.OPERATIONS.values() if role == "core" else ())], "profiles": profiles,
            "intent_schemas": ["biocompiler.intent.v0.2"], "validation_scopes": [profile["validation_scope"] for profile in profiles.values()],
            "canonicalization": "python-json-v1", "limits": LIMITS, "claim_scope": "Python fixture only"}

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(p.canonical(value) + b"\n")

    def wanted(self, corpus, role, case):
        identity = p.request_identity(role, case)
        if role == "verify":
            return p.envelope(role, identity, case["operation"], "unsupported", None, [p.UNSUPPORTED]), 3
        if case["error"] is not None:
            return p.envelope(role, identity, case["operation"], "error", None, [case["error"]]), 2
        return p.envelope(role, identity, case["operation"], "ok", p.expected_semantic(corpus, case), []), 0

    def base_receipt(self, corpus, directory):
        artifacts = directory / p.ARTIFACT_DIRECTORY
        artifacts.mkdir(parents=True)
        return {"checks": [], "artifacts": {}, "_artifact_directory": str(artifacts),
                "executables": {role: str(directory / ("biocompiler-" + role)) for role in p.ROLES}}

    def fixture(self, directory):
        root, natives = Path(directory) / "realization", Path(directory) / "native"
        corpus = self.small()
        for target, (system, machine) in p.PLATFORMS.items():
            native = natives / target
            native.mkdir(parents=True)
            pins = {}
            for role in p.ROLES:
                name = "biocompiler-" + role
                raw = (target + "/" + name + "/nonexecutable-python-test-data").encode()
                (native / name).write_bytes(raw)
                pins[name] = p.sha(raw)
            self.write(native / "binaries.json", {"revision": REVISION, "system": system, "machine": machine, "sha256": pins})
            inputs = p.verify_binaries(native, REVISION, target)
            for python in p.PYTHONS:
                slot = root / ("realization-" + target + "-py" + python)
                self.write(slot / "native-inputs.json", {**inputs, "run_id": RUN, "source_revision": SOURCE, "python_version": python + ".9"})
                receipt = self.base_receipt(corpus, slot)
                receipt["library_coverage"] = p.artifact(receipt, p.canonical(corpus.library))
                def exchange(role, request, response, exit_code):
                    return {"executable": receipt["executables"][role], "exit_code": exit_code,
                        "request": p.artifact(receipt, p.canonical(request)),
                        "response": p.artifact(receipt, p.canonical(response) + b"\n")}
                for (role, _identity), case in corpus.expected().items():
                    row = {"id": case["id"], "operation": case["operation"], "role": role,
                        "request_id": p.request_identity(role, case), "authority": p.artifact(receipt, case["authority"]),
                        "expected": None if case["expected"] is None else p.artifact(receipt, case["expected"]),
                        "evidence": p.artifact(receipt, p.canonical(case["evidence"])),
                        "guard_modules": sorted(p.TRANSPORT_MODULES if role == "core" else {"biocompiler.core_client"}), "exchanges": []}
                    if role == "core":
                        identity = str(uuid4())
                        request = {"protocol": "biocompiler.core.v1", "request_id": identity, "operation": "capabilities", "payload": {}}
                        row["exchanges"].append(exchange(role, request,
                            p.envelope(role, identity, "capabilities", "ok", self.capabilities(corpus, role), []), 0))
                    wanted, exit_code = self.wanted(corpus, role, case)
                    request = {"protocol": "biocompiler.core.v1", "request_id": row["request_id"], "operation": case["operation"], "payload": p.decode(case["authority"])}
                    row["exchanges"].append(exchange(role, request, wanted, exit_code))
                    receipt["checks"].append(row)
                identity = str(uuid4())
                receipt["verify_capabilities"] = exchange("verify", {"protocol": "biocompiler.core.v1", "request_id": identity, "operation": "capabilities", "payload": {}},
                    p.envelope("verify", identity, "capabilities", "ok", self.capabilities(corpus, "verify"), []), 0)
                receipt.update(schema_version=p.SCHEMA, status="success", scope=p.SCOPE, revision=REVISION, source_revision=SOURCE,
                    run_id=RUN, system=system, machine=machine, native_platform=target, python_version=python + ".9",
                    native_inputs=inputs, package_path="/installed/biocompiler/__init__.py", corpus_pin=p.CORPUS_PIN, capture_pin=p.CAPTURE_PIN,
                    profile_pin=p.digest(corpus.profiles), artifact_directory=p.ARTIFACT_DIRECTORY,
                    transport_sources=p.source_pins("src/" + name.replace(".", "/") + ".py" for name in sorted(p.TRANSPORT_MODULES)),
                    campaign_sources=p.source_pins(p.SOURCES), completed_checks=len(receipt["checks"]))
                del receipt["_artifact_directory"]
                self.write(slot / p.RECEIPT_FILE, receipt)
        return root, natives, corpus

    def compare(self, root, natives, corpus):
        with patch.object(p, "Corpus", return_value=corpus):
            return p.compare(root, natives, revision=REVISION, source_revision=SOURCE, run_id=RUN)

    def test_four_runtime_exact_metadata_and_census_mutations(self):
        with tempfile.TemporaryDirectory() as directory:
            root, natives, corpus = self.fixture(directory)
            self.assertEqual(self.compare(root, natives, corpus)["status"], "success")
            path = root / "realization-linux-x86_64-py3.11" / p.RECEIPT_FILE
            original = json.loads(path.read_bytes())
            changes = (
                lambda x: x.update(revision="c" * 40), lambda x: x.update(source_revision="d" * 40),
                lambda x: x.update(run_id="stale"), lambda x: x.update(status="failure"),
                lambda x: x.update(python_version="3.14.9"), lambda x: x.update(profile_pin="0" * 64),
                lambda x: x["checks"].pop(), lambda x: x["checks"].append(deepcopy(x["checks"][0])),
                lambda x: x["checks"][0].update(unexpected=True), lambda x: x["checks"][0].update(request_id="unbound"),
                lambda x: x["checks"][0].update(guard_modules=["biocompiler.core_client"]),
                lambda x: x["checks"][0]["exchanges"][0].update(executable="biocompiler-core"),
                lambda x: x["checks"][0]["exchanges"][1].update(exit_code=True),
                lambda x: x["verify_capabilities"].update(exit_code=False),
                lambda x: x["checks"][0]["exchanges"].pop(),
                lambda x: x.update(artifact_directory="../escape"),
                lambda x: x["transport_sources"].update({"src/biocompiler/core_client.py": "0" * 64}),
            )
            for change in changes:
                bad = deepcopy(original)
                change(bad)
                self.write(path, bad)
                with self.assertRaises((AssertionError, ValueError)):
                    self.compare(root, natives, corpus)
            self.write(path, original)
            binary = natives / "macos-arm64" / "biocompiler-core"
            binary.write_bytes(b"altered complete binary")
            with self.assertRaises((AssertionError, ValueError)):
                self.compare(root, natives, corpus)

    def test_rehashed_complete_wire_record_error_profile_and_role_forgeries_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root, natives, corpus = self.fixture(directory)
            slot = root / "realization-linux-x86_64-py3.11"
            path = slot / p.RECEIPT_FILE
            original = json.loads(path.read_bytes())
            mutants = (
                (0, 1, lambda x: x["result"].update(record_fingerprint="0" * 64)),
                (0, 1, lambda x: x["result"]["record"].update(intended_use="human_therapeutic")),
                (0, 1, lambda x: x["result"]["resources"]["protocol"].update(max_work=True)),
                (0, 1, lambda x: x["result"]["authority_identities"].update(request_fingerprint="0" * 64)),
                (3, 1, lambda x: x["result"]["generation_error"].update(formatted="hidden failure detail")),
                (5, 1, lambda x: x["diagnostics"][0].update(message="hidden acceptance error")),
                (0, 0, lambda x: x["result"]["profiles"].pop("synthetic_selection")),
                (0, 0, lambda x: x["result"].update(validation_scopes=[])),
                (0, 0, lambda x: x["result"]["limits"].update(max_depth=True)),
                (6, 0, lambda x: x.update(status="ok", diagnostics=[], result={})),
            )
            for row, index, mutate in mutants:
                receipt = deepcopy(original)
                old = receipt["checks"][row]["exchanges"][index]["response"]
                old_path = slot / p.ARTIFACT_DIRECTORY / (old + ".bin")
                old_bytes = old_path.read_bytes()
                wire = json.loads(old_bytes)
                mutate(wire)
                raw = p.canonical(wire) + b"\n"
                pin = p.sha(raw)
                target = slot / p.ARTIFACT_DIRECTORY / (pin + ".bin")
                target.write_bytes(raw)
                receipt["checks"][row]["exchanges"][index]["response"] = pin
                receipt["artifacts"][pin] = {"path": target.name, "bytes": len(raw), "sha256": pin}
                # Every wire response has a unique request ID; keep the forged
                # artifact inventory fully self-consistent so content checks,
                # rather than an unused old file, must reject the forgery.
                self.assertEqual(p.canonical(receipt).count(old.encode()), 3)
                del receipt["artifacts"][old]
                old_path.unlink()
                self.write(path, receipt)
                with self.assertRaisesRegex(AssertionError, "receipt, record, error|capability differs|framing limits differ"):
                    self.compare(root, natives, corpus)
                target.unlink()
                old_path.write_bytes(old_bytes)
            self.write(path, original)
            artifact = next(iter(original["artifacts"]))
            target = slot / p.ARTIFACT_DIRECTORY / (artifact + ".bin")
            target.write_bytes(target.read_bytes() + b" ")
            with self.assertRaises(AssertionError):
                self.compare(root, natives, corpus)

    def test_capability_uuid_and_verifier_scope_forgeries_fail_with_rehashed_inventory(self):
        for mutation in ("non-v4", "reused-uuid", "verifier-scope"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root, natives, corpus = self.fixture(directory)
                slot = root / "realization-linux-x86_64-py3.11"
                path = slot / p.RECEIPT_FILE
                receipt = json.loads(path.read_bytes())
                exchange = (receipt["verify_capabilities"] if mutation == "verifier-scope"
                            else receipt["checks"][1]["exchanges"][0])
                artifacts = slot / p.ARTIFACT_DIRECTORY
                def rewrite(key, value, newline):
                    old = exchange[key]
                    raw = p.canonical(value) + newline
                    identity = p.sha(raw)
                    (artifacts / (old + ".bin")).unlink()
                    del receipt["artifacts"][old]
                    (artifacts / (identity + ".bin")).write_bytes(raw)
                    receipt["artifacts"][identity] = {"path": identity + ".bin", "sha256": identity, "bytes": len(raw)}
                    exchange[key] = identity
                response = json.loads((artifacts / (exchange["response"] + ".bin")).read_bytes())
                if mutation == "verifier-scope":
                    response["result"]["validation_scopes"].append(corpus.profiles["synthetic_selection"]["validation_scope"])
                else:
                    request = json.loads((artifacts / (exchange["request"] + ".bin")).read_bytes())
                    if mutation == "non-v4":
                        identity = "00000000-0000-5000-8000-000000000000"
                    else:
                        first = receipt["checks"][0]["exchanges"][0]
                        identity = json.loads((artifacts / (first["response"] + ".bin")).read_bytes())["request_id"]
                    request["request_id"] = response["request_id"] = identity
                    rewrite("request", request, b"")
                rewrite("response", response, b"\n")
                self.write(path, receipt)
                with self.assertRaisesRegex(AssertionError, "capability identity|Verifier advertised"):
                    self.compare(root, natives, corpus)

    def test_installed_transport_trace_uses_actual_python_fixture_children(self):
        from biocompiler.core_client import CoreClient
        import biocompiler.core_synthetic_producer
        corpus = self.small()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            receipt = self.base_receipt(corpus, folder)
            table = {}
            for (role, _identity), case in corpus.expected().items():
                wanted, exit_code = self.wanted(corpus, role, case)
                table[role + ":" + case["operation"] + ":" + p.sha(case["authority"])] = [wanted, exit_code]
            self.write(folder / "fixture.json", {"table": table, "capabilities": {role: self.capabilities(corpus, role) for role in p.ROLES}})
            script = '''import hashlib,json,pathlib,sys
role=pathlib.Path(sys.argv[0]).name.removeprefix("biocompiler-")
data=json.loads(pathlib.Path(sys.argv[0]).with_name("fixture.json").read_bytes())
request=json.loads(sys.stdin.buffer.read())
def encode(x):return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()
if request["operation"]=="capabilities":
 response={"protocol":"biocompiler.core.v1","request_id":request["request_id"],"operation":"capabilities","status":"ok","diagnostics":[],"result":data["capabilities"][role],"core":{"implementation":"ocaml","version":"0.1.0","protocol":"biocompiler.core.v1","executable":role}}
 code=0
else:
 response,code=data["table"][role+":"+request["operation"]+":"+hashlib.sha256(encode(request["payload"])).hexdigest()]
 response["request_id"]=request["request_id"]
sys.stdout.buffer.write(encode(response)+b"\\n")
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
            checked = p.validate_checks(receipt, corpus, p.Artifacts(folder / p.ARTIFACT_DIRECTORY, receipt["artifacts"]))
            self.assertEqual(len(checked["checks"]), 9)
            self.assertEqual(sum(len(row["exchanges"]) for row in receipt["checks"]) + 1, 16)

    def test_guard_rejects_semantic_execution_and_imports(self):
        scope = {"__name__": "biocompiler.compiler.forbidden_fixture"}
        exec("def forbidden(): return 1", scope)
        with self.assertRaisesRegex(AssertionError, "semantic execution forbidden"):
            with p.transport_only():
                scope["forbidden"]()
        with self.assertRaisesRegex(AssertionError, "semantic import forbidden"):
            with p.transport_only():
                __import__("biocompiler.compiler.synthetic")


if __name__ == "__main__":
    unittest.main()
