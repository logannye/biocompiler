"""Inert installed-campaign boundary controls; never native admission evidence.

Synthetic protocol bodies deliberately mock the already separately tested SDK
representation checker and independent material literals. Actual file, slot,
origin, publication, identity and complete observation-census checks run here.
"""
from copy import deepcopy
import ast
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from tools import check_policy_component_material as campaign

IDENTITY = {"revision": "1" * 40, "head_revision": "2" * 40, "run_id": "1234", "run_attempt": "2"}
BINARIES = {"biocompiler-core": "3" * 64, "biocompiler-verify": "4" * 64}
SOURCES = {"reviewed-source.py": {"sha256": "5" * 64}}


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def observations(fixture):
    """Independently spelled inert rows; no candidate/expectation producer."""
    rows = []
    for case in fixture["cases"]:
        label = case["id"]
        compiled = {"candidate": {"case": label}, "report": {"fixture": label}, "artifact": None}
        exported = deepcopy(compiled)
        exported["artifact"] = {"fasta": ">payload\n" + campaign.EXPECTED[label]["sequence"] + "\n", "manifest": {"case": label}}
        failed = {"candidate": {"case": label, "changed": "material"}, "artifact": None,
                  "report": {"status": "not_accepted", "assembly_status": "fail", "context_status": "unassessed",
                             "assembly": {"structure": {"content_outcome": "fail"}},
                             "obligations": [{"obligation": name, "status": "unresolved"} for name in campaign.OBLIGATIONS]}}
        values = {"compile": compiled, "check-verify": deepcopy(compiled), "replay-verify": deepcopy(compiled),
                  "export-verify": exported, "paired-publication": campaign.archive_receipt(exported), "changed-material": failed}
        for name, code in (("changed-guard", "policy_implementation_source_binding"), ("changed-state", "policy_implementation_source_binding"),
                           ("changed-feedback", "policy_implementation_source_binding"), ("changed-configuration", "policy_implementation_contract"),
                           ("rejected-export", "policy_component_material_export_not_accepted"),
                           ("verify-has-no-producer", "unsupported_operation"), ("stale-source", "policy_correspondence")):
            values[name] = {"status": "unsupported" if name == "verify-has-no-producer" else "error",
                            "diagnostics": [{"code": code, "message": "Literal inert rejection", "path": None}]}
        for name in ("compile", "check-verify", "replay-verify", "export-verify", "paired-publication", "changed-guard", "changed-state",
                     "changed-feedback", "changed-configuration", "changed-material", "rejected-export", "verify-has-no-producer", "stale-source"):
            rows.append({"case": label, "name": name, "result": deepcopy(values[name])})
    return rows


def publish(path, result):
    from biocompiler.core_client import encode_json
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name, raw in (("program.fasta", result["artifact"]["fasta"].encode()), ("manifest.json", encode_json(result["artifact"]["manifest"]))):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3; info.external_attr = 0o100644 << 16; archive.writestr(info, raw)
    path.write_bytes(stream.getvalue())


class InstalledComponentCampaignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup); self.root = Path(self.temp.name).resolve()
        self.fixture_path = self.root / "originals.json"; self.provenance = self.root / "provenance.json"
        self.fixture = {"cases": [{"id": label, "request": {"case": label, "component_library": {"components": [{"decision": label}, {"driver": "unchanged"}]}},
                                  "limits": {"original": label}, "expected": {}} for label in ("A", "B")]}
        write(self.fixture_path, self.fixture); write(self.provenance, {"original": "source-only provenance tested independently"})
        for name in ("stdout.log","stderr.log"):(self.root/name).write_bytes(b"")
        self.modules = {}
        self.origins = {}
        for name in campaign.REQUIRED_MODULES:
            relative = "__init__.py" if name == "biocompiler" else name.removeprefix("biocompiler.").replace(".", "/") + ".py"
            self.modules[relative] = {"sha256": "6" * 64, "bytes": 10}; self.origins[name] = "/installed/biocompiler/" + relative
        self.author = lambda request, state: (deepcopy(request), {"request_digest": campaign.canonical_digest(request), "state": state})
        for name, value in (("checked_fixture", lambda root, path: deepcopy(self.fixture)),
                            ("validate_fixture_provenance", lambda *args: {"independently_checked": True}),
                            ("installed_source_modules", lambda root: deepcopy(self.modules)), ("author_request", self.author),
                            ("checked_result", lambda *args: None),
                            ("changed_candidate", lambda candidate, kind: {**candidate, "changed": kind})):
            patcher = patch.object(campaign, name, side_effect=value); patcher.start(); self.addCleanup(patcher.stop)
        from biocompiler import core_policy_component_material
        self.protocol_payloads=[]
        def representation(response,payload):
            self.protocol_payloads.append((response.operation,response.executable,deepcopy(payload)))
            return SimpleNamespace(result=response.result)
        patcher = patch.object(core_policy_component_material, "_result", side_effect=representation)
        patcher.start(); self.addCleanup(patcher.stop)
        self.complete = observations(self.fixture)
        self.receipt_path = self.make_receipt(self.root / "slot", ("Linux", "x86_64", "3.11"))

    def make_receipt(self, directory, slot):
        directory.mkdir(); artifacts = directory / "component-material"; artifacts.mkdir()
        value = {"schema_version": campaign.INSTALLED_SCHEMA, "status": "pass", **IDENTITY,
                 "system": slot[0], "machine": slot[1], "python_version": slot[2] + ".15", "scope": campaign.INSTALLED_SCOPE,
                 "fixture_sha256": campaign.bounded_pin(self.fixture_path)["sha256"],
                 "fixture_provenance_sha256": campaign.bounded_pin(self.provenance)["sha256"], "binary_sha256": deepcopy(BINARIES),
                 "package": "/installed/biocompiler", "installed_modules": deepcopy(self.modules), "parent_imports": deepcopy(self.origins),
                 "source_snapshot_sha256": campaign.canonical_digest(SOURCES),
                 "authoring": [{"case": case["id"], **self.author(case["request"], case["id"] == "B")[1]} for case in self.fixture["cases"]],
                 "shared_driver_fingerprint": campaign.canonical_digest({"driver": "unchanged"}),
                 "observations": [], "publications": [], "observations_fingerprint": campaign.canonical_digest(self.complete), "python_semantic_authority": "forbidden"}
        for row in self.complete:
            path = artifacts / (row["case"] + "-" + row["name"] + ".json"); write(path, row["result"])
            value["observations"].append({"case": row["case"], "name": row["name"], "path": str(path.relative_to(directory)), **campaign.bounded_pin(path)})
        for label in ("A", "B"):
            path = artifacts / (label + "-program.zip")
            publish(path, next(row["result"] for row in self.complete if row["case"] == label and row["name"] == "export-verify"))
            value["publications"].append({"case": label, "path": str(path.relative_to(directory)), **campaign.bounded_pin(path)})
        receipt = directory / "component-material.json"; write(receipt, value); return receipt

    def validate(self, value=None):
        return campaign.validate_installed(value or campaign.read_json(self.receipt_path), self.receipt_path.parent, self.fixture,
            self.fixture_path, IDENTITY, BINARIES, expected_sources=SOURCES, fixture_provenance=self.provenance,
            expected_slot=("Linux", "x86_64", "3.11"))

    def test_complete_two_case_inputs_and_actual_zip_pair(self):
        inputs = self.validate()
        self.assertEqual(list(inputs), ["A", "B"])
        for case in self.fixture["cases"]:
            actual = inputs[case["id"]]
            self.assertEqual(actual["request"], case["request"]); self.assertEqual(actual["limits"], case["limits"])
            self.assertEqual(set(actual), {"request", "limits", "candidate", "checked", "exported"})
        self.assertEqual(len(self.complete), 26)

    def test_full_original_and_replay_wrapper_reach_the_independent_sdk_validator(self):
        inputs=self.validate()
        self.assertEqual(len(self.protocol_payloads),10)
        for index,case in enumerate(self.fixture["cases"]):
            calls=self.protocol_payloads[index*5:index*5+5]
            self.assertEqual([row[:2] for row in calls],[(name+"-policy-component-material",role) for name,role in
                (("compile","core"),("check","verify"),("replay","verify"),("export","verify"),("check","verify"))])
            for _,_,payload in calls:
                self.assertEqual(payload["request"],case["request"]);self.assertEqual(payload["limits"],case["limits"])
            self.assertEqual(calls[2][2]["report"],inputs[case["id"]]["checked"])
            self.assertEqual(calls[4][2]["candidate"],{**inputs[case["id"]]["candidate"],"changed":"material"})

    def test_development_and_changed_external_identity_never_pass(self):
        original = campaign.read_json(self.receipt_path)
        mutations = [("schema_version", campaign.SCHEMA), ("status", "passed"), ("run_attempt", "3"), ("revision", "0" * 40),
                     ("head_revision", "0" * 40), ("run_id", "9"), ("system", "Darwin"), ("python_version", "3.11.15\n"),
                     ("scope", "release_accepted"), ("source_snapshot_sha256", "0" * 64), ("fixture_sha256", "0" * 64),
                     ("fixture_provenance_sha256", "0" * 64), ("binary_sha256", {**BINARIES, "biocompiler-core": "0" * 64}),
                     ("python_semantic_authority", "allowed")]
        for key, value in mutations:
            with self.subTest(key=key), self.assertRaises(AssertionError): self.validate({**original, key: value})
        with patch.object(campaign, "validate_fixture_provenance", side_effect=AssertionError("provenance changed")), self.assertRaisesRegex(AssertionError, "provenance changed"):
            self.validate()

    def test_origins_module_census_and_original_authoring_are_exact(self):
        original = campaign.read_json(self.receipt_path)
        for mutate in (lambda r:r["parent_imports"].update({"biocompiler.compiler": "/installed/biocompiler/compiler.py"}),
                       lambda r:r["parent_imports"].update({"biocompiler.core_client": "/foreign/core_client.py"}),
                       lambda r:r["parent_imports"].pop("biocompiler.core_policy_component_material"),
                       lambda r:r["installed_modules"].pop("core_policy_component_material.py"),
                       lambda r:r["authoring"][0].update(state=True),
                       lambda r:r.update(shared_driver_fingerprint="0"*64)):
            changed = deepcopy(original); mutate(changed)
            with self.assertRaises(AssertionError): self.validate(changed)

    def test_missing_duplicate_reordered_and_rehashed_observations_reject(self):
        original = campaign.read_json(self.receipt_path)
        for rows in (original["observations"][:-1], original["observations"] + original["observations"][:1], list(reversed(original["observations"]))):
            with self.assertRaisesRegex(AssertionError, "observation"): self.validate({**original, "observations": rows})
        for mutate in (lambda rows:rows[5]["result"]["diagnostics"][0].update(code="internal_error"),
                       lambda rows:rows[9]["result"]["report"].update(context_status="pass"),
                       lambda rows:rows[1]["result"].update(extra="changed complete evidence"),
                       lambda rows:rows[4]["result"].update(bytes=1)):
            changed_rows=deepcopy(self.complete); mutate(changed_rows); value=deepcopy(original)
            for row, pin in zip(changed_rows,value["observations"]):
                path=self.receipt_path.parent/pin["path"];write(path,row["result"]);pin.update(campaign.bounded_pin(path))
            value["observations_fingerprint"]=campaign.canonical_digest(changed_rows)
            with self.assertRaises(AssertionError):self.validate(value)

    def test_changed_zip_extra_file_and_path_redirect_reject(self):
        original=campaign.read_json(self.receipt_path);row=original["publications"][0];path=self.receipt_path.parent/row["path"]
        raw=path.read_bytes();path.write_bytes(raw+b"extra");row.update(campaign.bounded_pin(path))
        with self.assertRaisesRegex(AssertionError,"publication|archive"):self.validate(original)
        path.write_bytes(raw);extra=path.parent/"unexpected.json";extra.write_text("{}")
        with self.assertRaisesRegex(AssertionError,"extra component evidence"):self.validate()
        extra.unlink();original=campaign.read_json(self.receipt_path);original["observations"][0]["path"]="../escape.json"
        with self.assertRaisesRegex(AssertionError,"Unsafe"):self.validate(original)

    def test_actual_source_or_fixture_change_invalidates_old_pins(self):
        self.fixture_path.write_text('{"changed":true}')
        with self.assertRaisesRegex(AssertionError,"external identity"):self.validate()

    def test_four_slots_compare_complete_evidence_and_keep_attempt_identity(self):
        paths=[self.make_receipt(self.root/f"compare-{i}",slot) for i,slot in enumerate(sorted(campaign.SLOTS))]
        binaries={name:{"sha256":BINARIES} for name in ("linux","darwin")}
        with patch.object(campaign,"source_identity",return_value=IDENTITY), patch.object(campaign,"source_snapshot",return_value=SOURCES), patch.object(campaign,"native_manifests",return_value=binaries):
            result=campaign.compare_installed(paths,self.root,self.fixture_path,{("Linux","x86_64"):self.provenance,("Darwin","arm64"):self.provenance})
            self.assertEqual(result["slots"],sorted(campaign.SLOTS));self.assertEqual([r["run_attempt"] for r in result["attempts"]],["2"]*4)
            for bad in (paths[:-1],paths[:3]+paths[:1]):
                with self.assertRaises(AssertionError):campaign.compare_installed(bad,self.root,self.fixture_path,{("Linux","x86_64"):self.provenance,("Darwin","arm64"):self.provenance})

    def test_self_consistent_cross_slot_change_and_shared_omission_reject(self):
        paths=[self.make_receipt(self.root/f"mutant-{i}",slot) for i,slot in enumerate(sorted(campaign.SLOTS))]
        binaries={name:{"sha256":BINARIES} for name in ("linux","darwin")}
        mapping={("Linux","x86_64"):self.provenance,("Darwin","arm64"):self.provenance}
        with patch.object(campaign,"source_identity",return_value=IDENTITY),patch.object(campaign,"source_snapshot",return_value=SOURCES),patch.object(campaign,"native_manifests",return_value=binaries):
            last=campaign.read_json(paths[-1]);data=deepcopy(self.complete);data[5]["result"]["diagnostics"][0]["message"]="Different retained full diagnostic"
            path=paths[-1].parent/last["observations"][5]["path"];write(path,data[5]["result"])
            last["observations"][5].update(campaign.bounded_pin(path));last["observations_fingerprint"]=campaign.canonical_digest(data);write(paths[-1],last)
            with self.assertRaisesRegex(AssertionError,"outputs differ"):
                campaign.compare_installed(paths,self.root,self.fixture_path,mapping)
            for path in paths:
                value=campaign.read_json(path);value["observations"].pop();value["observations_fingerprint"]=campaign.canonical_digest(self.complete[:-1]);write(path,value)
            with self.assertRaisesRegex(AssertionError,"observation files"):
                campaign.compare_installed(paths,self.root,self.fixture_path,mapping)

    def test_later_slot_cannot_replace_previously_checked_receipt_or_evidence(self):
        paths=[self.make_receipt(self.root/f"lifetime-{i}",slot) for i,slot in enumerate(sorted(campaign.SLOTS))]
        binaries={name:{"sha256":BINARIES} for name in ("linux","darwin")}
        mapping={("Linux","x86_64"):self.provenance,("Darwin","arm64"):self.provenance}
        first=campaign.read_json(paths[0]); evidence=paths[0].parent/first["observations"][0]["path"]
        original_validate=campaign.validate_installed
        for changed in (paths[0],evidence,self.root/"stdout.log",self.root/"stderr.log"):
            raw=changed.read_bytes();calls=[]
            def validate(*args,**kwargs):
                result=original_validate(*args,**kwargs);calls.append(None)
                if len(calls)==2:changed.write_bytes(raw+b" ")
                return result
            with self.subTest(path=changed.name),patch.object(campaign,"validate_installed",side_effect=validate), \
                 patch.object(campaign,"source_identity",return_value=IDENTITY),patch.object(campaign,"source_snapshot",return_value=SOURCES), \
                 patch.object(campaign,"native_manifests",return_value=binaries):
                with self.assertRaisesRegex(AssertionError,"comparison evidence"):
                    campaign.compare_installed(paths,self.root,self.fixture_path,mapping)
            changed.write_bytes(raw)

    def test_run_installed_preserves_pins_and_withholds_on_late_changes(self):
        package=self.root/"installed/biocompiler";package.mkdir(parents=True);(package/"__init__.py").write_text("# inert")
        origins={name:str(package/Path(path).relative_to("/installed/biocompiler")) for name,path in self.origins.items()}
        binary_paths={role:self.root/role for role in ("core","verify")}
        for path in binary_paths.values():path.write_bytes(b"inert native marker");path.chmod(0o700)
        initial_fixture=self.fixture_path.read_bytes()
        changed={"source":False,"origins":False}
        class Boundary(campaign.ComponentBoundary):
            def __init__(self,package):pass
            def find_spec(self,*args):return None
            def trace(self,*args):pass
            def origins(self):return {**origins,**({"biocompiler.compiler":"/foreign.py"} if changed["origins"] else {})}
        def execute(cases,core,transport,verify,sdk,retain,artifacts,input_paths):
            self.assertEqual([case["id"] for case,_ in cases],["A","B"])
            self.assertIn(self.provenance,input_paths)
            for row in self.complete:retain(row["case"],row["name"],deepcopy(row["result"]))
            for label in ("A","B"):
                publish(artifacts/(label+"-program.zip"),next(row["result"] for row in self.complete if row["case"]==label and row["name"]=="export-verify"))
            if mode=="binary":binary_paths["verify"].write_bytes(b"lasting late binary mutation")
            if mode=="fixture":self.fixture_path.write_text("{}")
            if mode=="log":(self.root/"stdout.log").write_bytes(b"lasting log change")
            if mode in changed:changed[mode]=True
        for mode in ("positive","binary","fixture","log","source","origins"):
            with self.subTest(mode=mode):
                changed.update(source=False,origins=False);self.fixture_path.write_bytes(initial_fixture)
                (self.root/"stdout.log").write_bytes(b"")
                for path in binary_paths.values():path.write_bytes(b"inert native marker")
                args=SimpleNamespace(core=binary_paths["core"],verify=binary_paths["verify"],
                    core_sha256=campaign.bounded_pin(binary_paths["core"])["sha256"],verify_sha256=campaign.bounded_pin(binary_paths["verify"])["sha256"],
                    fixture=self.fixture_path,fixture_provenance=self.provenance,output=self.root/(mode+".json"))
                from biocompiler.policy import component_material  # transport/publication import only
                self.assertTrue(callable(component_material.export))
                with patch.dict("os.environ",{"GITHUB_ACTIONS":"true","RUNNER_ENVIRONMENT":"github-hosted"}), \
                     patch.object(campaign,"source_identity",return_value=IDENTITY), patch.object(campaign.Path,"cwd",return_value=self.root), \
                     patch.object(campaign,"source_snapshot",side_effect=lambda root:{**SOURCES,**({"changed":{}} if changed["source"] else {})}), \
                     patch.object(campaign.platform,"system",return_value="Linux"),patch.object(campaign.platform,"machine",return_value="x86_64"), \
                     patch.object(campaign.importlib.util,"find_spec",return_value=SimpleNamespace(origin=str(package/"__init__.py"))), \
                     patch.object(campaign,"installed_package_modules",return_value=self.modules),patch.object(campaign,"ComponentBoundary",Boundary), \
                     patch.object(campaign,"exercise_cases",side_effect=execute):
                    if mode=="positive":
                        result=campaign.run_installed(args);self.assertEqual(result["status"],"pass");self.assertEqual(len(result["publications"]),2)
                    else:
                        with self.assertRaises(AssertionError):campaign.run_installed(args)
                        self.assertEqual(campaign.read_json(args.output)["status"],"failed")

    def test_hosted_guard_precedes_any_native_or_source_process(self):
        with patch.dict("os.environ",{},clear=True), patch.object(campaign,"source_identity",side_effect=AssertionError("must not reach git")):
            with self.assertRaisesRegex(AssertionError,"hosted-only"):campaign.run_installed(SimpleNamespace())


class InstalledSourceBoundaryTests(unittest.TestCase):
    def test_whole_installed_python_inventory_and_no_checkout_alias(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary).resolve();root=base/"checkout";source=root/"src/biocompiler";source.mkdir(parents=True)
            installed=base/"env/biocompiler";installed.mkdir(parents=True)
            for folder in (source,installed):(folder/"__init__.py").write_text("# inert\n")
            self.assertEqual(campaign.installed_package_modules(root,installed),campaign.installed_source_modules(root))
            with self.assertRaisesRegex(AssertionError,"outside checkout"):campaign.installed_package_modules(root,source)
            (installed/"extra.py").write_text("# extra\n")
            with self.assertRaisesRegex(AssertionError,"complete reviewed"):campaign.installed_package_modules(root,installed)
            (installed/"extra.py").unlink();(installed/"__init__.py").write_text("# changed\n")
            with self.assertRaisesRegex(AssertionError,"complete reviewed"):campaign.installed_package_modules(root,installed)
            (installed/"__init__.py").unlink();(installed/"__init__.py").symlink_to(source/"__init__.py")
            with self.assertRaisesRegex(AssertionError,"redirected"):campaign.installed_package_modules(root,installed)

    def test_resource_and_symlink_file_boundaries_are_not_stat_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();p=root/"input";p.write_bytes(b"012345")
            with self.assertRaisesRegex(AssertionError,"byte bound"):campaign.bounded_pin(p,5)
            q=root/"alias";q.symlink_to(p)
            with self.assertRaisesRegex(AssertionError,"redirected"):campaign.bounded_pin(q)

    def test_shared_kernel_keeps_closed_literal_case_inventory(self):
        source=Path(campaign.__file__).read_text();tree=ast.parse(source)
        kernel=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="exercise_cases")
        self.assertEqual([n.func.id for n in ast.walk(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="run"))
                          if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="exercise_cases"],["exercise_cases"])
        self.assertIn("input_paths",{n.id for n in ast.walk(kernel) if isinstance(n,ast.Name)})
        self.assertEqual(campaign.CASE_NAMES,("compile","check-verify","replay-verify","export-verify","paired-publication","changed-guard","changed-state","changed-feedback","changed-configuration","changed-material","rejected-export","verify-has-no-producer","stale-source"))


if __name__=="__main__":unittest.main()
