"""Full CLI evidence mutations and actual children using Python byte fixtures.

No native binary is built or executed. Synthetic comparator receipts are clearly
test fixtures; the production campaign requires the separately pinned binaries.
"""
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
from uuid import uuid4

from tools import check_native_workflow_cli as c

REVISION, SOURCE, RUN = "a" * 40, "b" * 40, "77"


class NativeWorkflowCliCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original, cls.old_blobs = c.baseline()
        cls.oracle = c.Oracle()

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(c.canonical(value) + b"\n")

    def fixture_receipt(self, *, native=None, platform="linux-x86_64", python="3.11"):
        store = c.f.Store()
        # Copy complete independently captured streams and filesystem bytes.
        def copy_content(value):
            if type(value) is dict:
                if value.get("kind") in ("blob", "repeat"):
                    return store.retain(c.f.restore(value, self.old_blobs))
                return {key: copy_content(item) for key, item in value.items()}
            if type(value) is list: return [copy_content(item) for item in value]
            return value
        if native is None:
            native = {"sha256": {"biocompiler-" + role: ("c" if role == "core" else "d") * 64 for role in c.ROLES}}
        sources = c.product_sources()
        rows = []
        for role in c.ROLES:
            for old in self.original["cases"]:
                scope = "historical_inspection" if old["argv"][0] == "inspect" else "native_workflow"
                flags = [] if scope == "historical_inspection" else ["--core-executable" if role == "core" else
                    "--verify-executable", "/installed/biocompiler-" + role, "--core-sha256",
                    native["sha256"]["biocompiler-" + role], "--core-timeout", "300"]
                row = {key: copy_content(old[key]) for key in ("id", "entrypoint", "fault", "lineage",
                    "files_before", "files_after", "exit_code", "stdout", "stderr")}
                row.update(role=role, scope=scope, argv=[old["argv"][0], *flags, *old["argv"][1:]],
                    console_path="/installed/bin/biocompiler", python_executable="/installed/bin/python3",
                    native_artifacts={})
                audit = {"scope": scope, "guard_active": scope == "native_workflow", "functions": [],
                    "modules": {"biocompiler.cli": {"path": "src/biocompiler/cli.py", "sha256": sources["src/biocompiler/cli.py"]}},
                    "package_path": "/installed/site-packages/biocompiler", "responses": [],
                    "native_artifacts": {}, "wire_responses": {}}
                if scope == "native_workflow": audit["functions"].append(["biocompiler.cli", "main", "output", ""])
                trace = self.oracle.trace(old["id"])
                if trace:
                    audit["functions"].extend([[module, name, "output", ""] for module, name in (
                        ("biocompiler.cli", "_verification_command"), ("biocompiler.workflow_cli", "selected_core_command"),
                        ("biocompiler.core_client", "_response"), ("biocompiler.core_artifacts", "call_artifact"))])
                audit["functions"].sort()
                for module, _name, _phase, _owner in audit["functions"]:
                    source = "src/" + module.replace(".", "/") + ".py"
                    audit["modules"][module] = {"path": source, "sha256": sources[source]}
                authority, retained = self.oracle.inputs(self.oracle.cases[old["id"]])
                for operation, status, diagnostic, artifact in trace:
                    identifier = str(uuid4())
                    value = {"protocol": "biocompiler.core.v1", "request_id": identifier, "operation": operation,
                        "status": status, "result": None, "diagnostics": [] if status == "ok" else [diagnostic],
                        "core": {"implementation": "ocaml", "version": "0.1.0", "protocol": "biocompiler.core.v1", "executable": role}}
                    if status == "ok":
                        body = c.r.descriptor(artifact)
                        audit["native_artifacts"][identifier] = body
                        row["native_artifacts"][body["sha256"]] = store.retain(artifact)
                        value["result"] = {"schema_version": "biocompiler.core.artifact_response.v1",
                            "transport": "biocompiler.core.artifact_transport.authority.v1" if operation ==
                                "validate-verification-workflow-authority" else "biocompiler.core.artifact_transport.v1",
                            "authority": c.r.descriptor(authority), "retained_record": c.r.descriptor(retained) if operation ==
                                "replay-verification-workflow" else None, "artifact": body,
                            "result": self.oracle.semantic(role, old["id"], operation, identifier, artifact)}
                    wire = c.canonical(value) + b"\n"
                    descriptor = c.r.descriptor(wire)
                    audit["wire_responses"][identifier] = {"content": descriptor, "exit_code": 0 if status == "ok" else 2}
                    row["native_artifacts"][descriptor["sha256"]] = store.retain(wire)
                    audit["responses"].append(value)
                row["audit"] = store.retain(c.canonical(audit))
                rows.append(row)
        system, machine = c.PLATFORMS[platform]
        return {"schema_version": c.SCHEMA, "scope": c.SCOPE, "status": "success", "baseline_pin": c.BASELINE_PIN,
            "revision": REVISION, "source_revision": SOURCE, "run_id": RUN, "python_version": python + ".9",
            "system": system, "machine": machine, "native_platform": platform, "native_inputs": native,
            "product_sources": sources, "campaign_sources": c.r.source_pins(c.SOURCES),
            "executables": {role: "/installed/biocompiler-" + role for role in c.ROLES},
            "checks": rows, "completed_checks": 140}, store.blobs

    def validate(self, receipt, blobs):
        return c.validate(receipt, blobs, self.original, self.old_blobs, oracle=self.oracle)

    def fixture_matrix(self, directory):
        root, natives = Path(directory) / "realization", Path(directory) / "native"
        for target, (system, machine) in c.PLATFORMS.items():
            native = natives / target
            native.mkdir(parents=True)
            pins = {}
            for role in c.ROLES:
                name = "biocompiler-" + role
                raw = (target + name + " nonexecutable comparator fixture bytes").encode()
                (native / name).write_bytes(raw)
                pins[name] = c.f.sha(raw)
            self.write(native / "binaries.json", {"revision": REVISION, "system": system, "machine": machine, "sha256": pins})
            inputs = c.r.verify_binaries(native, REVISION, target)
            for python in c.PYTHONS:
                slot = root / ("realization-" + target + "-py" + python)
                self.write(slot / "native-inputs.json", {**inputs, "run_id": RUN, "source_revision": SOURCE,
                    "python_version": python + ".9"})
                receipt, blobs = self.fixture_receipt(native=inputs, platform=target, python=python)
                receipt.update(artifact_directory=c.ARTIFACT_DIRECTORY, artifacts={})
                for identity, raw in blobs.items():
                    path = slot / c.ARTIFACT_DIRECTORY / (identity + ".bin")
                    path.parent.mkdir(exist_ok=True)
                    path.write_bytes(raw)
                    receipt["artifacts"][identity] = {"path": path.name, **c.r.descriptor(raw)}
                self.write(slot / c.RECEIPT_FILE, receipt)
        return root, natives

    def compare(self, root, natives):
        with patch.object(c, "Oracle", return_value=self.oracle):
            return c.compare(root, natives, revision=REVISION, source_revision=SOURCE, run_id=RUN)

    def test_full_140_census_all_original_cases_and_expected_operation_sequences(self):
        receipt, blobs = self.fixture_receipt()
        projected = self.validate(receipt, blobs)
        self.assertEqual(len(projected), 140)
        self.assertEqual(Counter(row["role"] for row in projected), {"core": 70, "verify": 70})
        self.assertEqual(Counter(row["entrypoint"] for row in receipt["checks"]), {"console": 132, "module": 8})
        self.assertEqual(Counter(row["exit_code"] for row in projected), {0: 58, 1: 22, 2: 60})
        self.assertEqual(Counter(len(self.oracle.trace(case["id"])) for case in self.original["cases"]), {0: 14, 1: 40, 2: 16})
        for mutate in (lambda value: value["checks"].pop(), lambda value: value["checks"].append(deepcopy(value["checks"][0])),
                       lambda value: value.update(completed_checks=139), lambda value: value["checks"][0].update(extra=True),
                       lambda value: value["checks"][0].update(role="other"), lambda value: value.update(baseline_pin="0" * 64),
                       lambda value: value["executables"].update(core="relative-native-path"),
                       lambda value: value["product_sources"].update({"src/biocompiler/cli.py": "0" * 64})):
            value = deepcopy(receipt); mutate(value)
            with self.assertRaises(AssertionError): self.validate(value, blobs)

    def test_all_four_variants_rehash_binaries_and_reject_stale_or_missing_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root, natives = self.fixture_matrix(directory)
            result = self.compare(root, natives)
            self.assertEqual(result["status"], "success")
            self.assertEqual(len(result["receipts"]), 4)
            path = root / "realization-linux-x86_64-py3.11" / c.RECEIPT_FILE
            original = c.r.decode(path.read_bytes())
            for field, value in (("run_id", "stale"), ("source_revision", "c" * 40), ("revision", "d" * 40),
                                 ("python_version", "3.14.9"), ("native_platform", "macos-arm64"), ("artifact_directory", "../outside")):
                changed = deepcopy(original); changed[field] = value; self.write(path, changed)
                with self.assertRaises(AssertionError): self.compare(root, natives)
            self.write(path, original)
            binary = natives / "linux-x86_64/biocompiler-core"
            original_bytes = binary.read_bytes(); binary.write_bytes(b"forged native bytes")
            with self.assertRaises(ValueError): self.compare(root, natives)
            binary.write_bytes(original_bytes)
            (root / "realization-macos-arm64-py3.14/native-inputs.json").unlink()
            with self.assertRaises(AssertionError): self.compare(root, natives)

    def test_rehashed_semantic_artifact_and_native_wire_forgeries_fail_against_original_bytes(self):
        receipt, blobs = self.fixture_receipt()
        original_row = receipt["checks"][0]
        original_audit = c.r.decode(c.f.restore(original_row["audit"], blobs))
        for kind in ("artifact", "semantic", "authority", "diagnostic", "guard", "phase", "missing_trace", "order", "wire",
                     "unpinned_frame", "uuid_version"):
            row, audit, changed_blobs = deepcopy(original_row), deepcopy(original_audit), dict(blobs)
            envelope = audit["responses"][0]
            if kind == "artifact":
                identifier = envelope["request_id"]
                raw = c.r.decode(c.f.restore(row["native_artifacts"][audit["native_artifacts"][identifier]["sha256"]], blobs))
                raw["claim_scope"] = "forged expanded acceptance"
                body = c.canonical(raw); descriptor = c.r.descriptor(body)
                changed_blobs[descriptor["sha256"]] = body
                row["native_artifacts"][descriptor["sha256"]] = {"kind": "blob", **descriptor}
                audit["native_artifacts"][identifier] = descriptor
                envelope["result"]["artifact"] = descriptor
                envelope["result"]["result"]["record_fingerprint"] = descriptor["sha256"]
            elif kind == "semantic": envelope["result"]["result"]["presentation"]["command_exit_code"] = 1
            elif kind == "authority": envelope["result"]["authority"]["sha256"] = "0" * 64
            elif kind == "diagnostic": envelope["diagnostics"] = [{"code": "forged", "message": "invented", "path": None}]
            elif kind == "guard": audit["functions"].append(["biocompiler.compiler.verification_workflow", "run_synthetic_verification", "output", ""]); audit["functions"].sort()
            elif kind == "phase": audit["functions"][0][2] = "input"
            elif kind == "missing_trace": audit["responses"].clear()
            elif kind == "order": envelope["operation"] = "replay-verification-workflow"
            elif kind == "wire": audit["wire_responses"][envelope["request_id"]]["exit_code"] = 2
            elif kind == "unpinned_frame": audit["modules"].pop("biocompiler.core_artifacts")
            elif kind == "uuid_version":
                old = envelope["request_id"]; new = "00000000-0000-0000-0000-000000000000"
                envelope["request_id"] = new; envelope["result"]["result"]["request_id"] = new
                audit["wire_responses"][new] = audit["wire_responses"].pop(old)
                audit["native_artifacts"][new] = audit["native_artifacts"].pop(old)
            if kind in ("artifact", "semantic", "authority", "diagnostic", "order", "uuid_version"):
                wire = c.canonical(envelope) + b"\n"; descriptor = c.r.descriptor(wire)
                changed_blobs[descriptor["sha256"]] = wire
                row["native_artifacts"][descriptor["sha256"]] = {"kind": "blob", **descriptor}
                audit["wire_responses"][envelope["request_id"]]["content"] = descriptor
            with self.subTest(kind=kind), self.assertRaises(AssertionError):
                c.validate_audit(row, audit, changed_blobs, receipt["product_sources"], self.oracle)

    def test_exact_output_and_lossless_boundary_recipes_are_never_normalized(self):
        receipt, blobs = self.fixture_receipt()
        row, old = deepcopy(receipt["checks"][0]), self.original["cases"][0]
        raw = c.f.restore(row["stdout"], blobs) + b" "
        changed = dict(blobs); changed[c.f.sha(raw)] = raw
        row["stdout"] = {"kind": "blob", **c.r.descriptor(raw)}
        with self.assertRaises(AssertionError): c.equal_observations(row, old, changed, self.old_blobs)
        recipe_row = next(item for item in receipt["checks"] if item["id"] == "publication-size-at-limit")
        recipe = next(value["content"] for value in recipe_row["files_after"].values()
                      if value.get("content", {}).get("kind") == "repeat")
        self.assertEqual(recipe["bytes"], 64 * 1024 * 1024)
        self.assertEqual(len(c.f.restore(recipe, blobs)), recipe["bytes"])
        forged = deepcopy(recipe); forged["count"] -= 1
        with self.assertRaises(AssertionError): c.f.restore(forged, blobs)
        with tempfile.TemporaryDirectory() as directory:
            empty = b""; identity = c.f.sha(empty); path = Path(directory) / (identity + ".bin"); path.write_bytes(empty)
            declared = {identity: {"path": path.name, **c.r.descriptor(empty)}}
            self.assertEqual(c.read_artifacts(directory, declared), {identity: empty})
            path.write_bytes(b"forged")
            with self.assertRaises(AssertionError): c.read_artifacts(directory, declared)

    def test_actual_installed_fixture_children_observe_guard_transport_order_and_publication(self):
        # A copied pure-Python tree and explicit script are test setup only. The
        # production campaign separately requires installed release packaging.
        from test_workflow_native_cli import CHILD
        from test_core_workflow import capabilities as workflow_caps
        from test_core_workflow_authority import capabilities as authority_caps
        from biocompiler.core_workflow import effective_resources, presentation_capability_profile
        from biocompiler.core_workflow_authority import capability_profile
        with tempfile.TemporaryDirectory() as directory, c.f.owned_directories():
            root = Path(directory)
            site = root / "site"; site.mkdir()
            shutil.copytree(c.ROOT / "src/biocompiler", site / "biocompiler", ignore=shutil.ignore_patterns("__pycache__"))
            binary = root / "fixture-core"; binary.write_text(f"#!{sys.executable}\n" + CHILD); binary.chmod(0o700)
            console = root / "biocompiler"; console.write_text(f"#!{sys.executable}\n" + c.f.ENTRYPOINT); console.chmod(0o700)
            for name in ("startup", "cwd", "native-artifacts"): (c.f.CLI_ROOT / name).mkdir()
            startup = "import sys\nsys.path.insert(0, " + repr(str(site)) + ")\n" + c.STARTUP
            (c.f.CLI_ROOT / "startup/sitecustomize.py").write_text(startup)
            for role, identifier in (("core", "module-entry-check"), ("verify", "module-entry-replay"),
                                     ("core", "module-entry-explore"), ("verify", "publication-short-write")):
                case = self.oracle.cases[identifier]
                trace = self.oracle.trace(identifier)
                record = c.r.decode(trace[-1][3])
                caps = workflow_caps(); authority = authority_caps()
                caps["operations"].extend(authority["operations"][1:]); caps["profiles"].update(authority["profiles"])
                caps["validation_scopes"].extend(authority["validation_scopes"])
                semantic = self.oracle.semantic(role, identifier, trace[-1][0], str(uuid4()), trace[-1][3])
                config = {"role": role, "capabilities": caps, "authority_profile": capability_profile(),
                    "presentation_profile": presentation_capability_profile(), "record": record,
                    "resources": effective_resources(), "log": str(root / "calls.jsonl"), "presentation": semantic["presentation"]}
                binary.with_suffix(".json").write_bytes(c.canonical(config))
                store = c.f.Store()
                with patch.dict(os.environ, {"PATH": str(root) + os.pathsep + os.environ["PATH"]}):
                    row = c.run_case(case, role, binary, c.f.sha(binary.read_bytes()), store)
                old = next(value for value in self.original["cases"] if value["id"] == identifier)
                c.equal_observations(row, old, store.blobs, self.old_blobs)
                audit = c.r.decode(c.f.restore(row["audit"], store.blobs))
                c.validate_audit(row, audit, store.blobs, c.product_sources(), self.oracle)


if __name__ == "__main__": unittest.main()
