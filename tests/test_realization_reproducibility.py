"""Fail-closed receipt comparison tests; full expected matrix remains pinned."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import check_realization_reproducibility as r

REVISION = "a" * 40
SOURCE = "b" * 40
RUN = "77"


class RealizationReproducibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = r.Golden()

    def test_complete_production_expected_matrix_has_all_original_occurrences_and_roles(self):
        self.assertEqual(len(self.full.expected("protocol")), 13438)
        self.assertEqual(len(self.full.expected("routing")), 8314)
        for kind in ("protocol","routing"):
            expected = self.full.expected(kind)
            self.assertEqual({key[0] for key in expected}, {"core","verify"})
            self.assertEqual(len({key[2] for key in expected}), 9 if kind == "protocol" else 5)
        self.assertEqual(len(self.full.index["cases"]),4119)
        self.assertEqual(len(self.full.index["baseline"]["subprocesses"]),2)

    def golden_small(self):
        # These focused comparator mutation tests retain real complete original
        # reports. Production matrix census is tested separately above.
        golden = r.Golden()
        selected = [next(case for case in golden.cases if case["api"] == api and case["result"] is not None)
                    for api in r.APIS]
        selected.append(next(case for case in golden.cases if case["error"] is not None))
        golden.cases = selected
        golden.index = deepcopy(golden.index)
        golden.index["boundary_cases"] = []
        golden.index["coverage"].update(protocol_checks_per_role=10,sdk_checks_per_role=6)
        return golden

    def write(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(r.canonical(value) + b"\n")

    def fixture(self,directory):
        root,natives = Path(directory)/"realization",Path(directory)/"native"
        golden = self.golden_small()
        for target,(system,machine) in r.PLATFORMS.items():
            native = natives/target
            native.mkdir(parents=True)
            pins = {}
            for role in ("core","verify"):
                name = "biocompiler-" + role
                data = (target + "/" + name).encode()
                (native/name).write_bytes(data)
                pins[name] = hashlib.sha256(data).hexdigest()
            self.write(native/"binaries.json",{"revision":REVISION,"system":system,"machine":machine,"sha256":pins})
            inputs = r.verify_binaries(native,REVISION,target)
            for version in r.PYTHONS:
                slot = root/("realization-" + target + "-py" + version)
                self.write(slot/"native-inputs.json",{**inputs,"run_id":RUN,"source_revision":SOURCE,"python_version":version + ".9"})
                for kind in ("protocol","routing"):
                    checks,values = [],{}
                    for (role,identity,operation),(case,error,replay) in golden.expected(kind).items():
                        item = {"role":role,"id":identity,"operation":operation}
                        if error:
                            value = {"status":"error","result":None,"diagnostics":[
                                {"code":error["code"],"message":error.get("message","Explicit rejection."),"path":None}]}
                            item["error"] = error["code"]
                        else:
                            report = golden.document(case["result"])
                            profile = golden.profiles[r.APIS[case["api"]][0]]
                            dependency = operation == "realization-dependencies"
                            encoding = profile["dependency_encoding" if dependency else "assessment_encoding"]
                            report_pin = r.digest(report,ascii=encoding == "python-json-ascii-v1")
                            outcome = None if dependency else report["outcome"]
                            if kind == "routing":
                                value = report
                                item.update(report=report_pin,outcome=outcome)
                            else:
                                _,payload = golden.payload(case,replay)
                                authority = r.digest({k:v for k,v in payload.items() if k != "assessment"})
                                label = "dependencies" if dependency else "assessment"
                                value = {key:profile["dependency_" + key if dependency and key in ("validation_scope","claim_scope") else key]
                                         for key in ("profile","implementation","service_implementation","validation_scope","claim_scope")}
                                value.update(schema_version=profile["result_schemas"][operation],
                                    resource_profile=profile["resources"]["protocol"]["profile"],resources=profile["resources"],
                                    supplied_authority_fingerprint=authority,authority_identities=case["authority_identities"])
                                value.update({label:report,label + "_fingerprint":report_pin})
                                item.update(authority=authority,outcome=outcome)
                                item[label] = report_pin
                        identity_pin = r.digest(value)
                        values[identity_pin] = value
                        item["artifact"] = identity_pin
                        checks.append(item)
                    artifact_dir = slot/(kind + "-reports")
                    for identity,value in values.items():
                        self.write(artifact_dir/(identity + ".json"),value)
                    receipt = {"schema_version":"biocompiler.realization_" + kind + "_conformance.v1","status":"success",
                        "revision":REVISION,"source_revision":SOURCE,"run_id":RUN,"platform":system + "-fixture-" + machine,
                        "system":system,"machine":machine,
                        "python_version":version + ".9","package_path":"/installed/site-packages/biocompiler",
                        "corpus_pin":r.CORPUS_PIN,"baseline_pin":r.BASE_PIN,
                        "scope":"direct_operations_only_no_workflow_archive_or_export_migration",
                        "executables":{role:{"path":"/installed/biocompiler-" + role,"sha256":pins["biocompiler-" + role]}
                                       for role in ("core","verify")},
                        "checks":checks,"completed_checks":len(checks),"artifact_directory":kind + "-reports",
                        "artifacts":{identity:{"path":identity + ".json","bytes":len(r.canonical(value))+1,"canonical_sha256":identity}
                                     for identity,value in values.items()}}
                    if kind == "routing":
                        receipt["guard"] = {"status":"passed","input_hydration":"outside_guard_before_native_call",
                            "snapshot_request_rehydration":"forbidden_during_native_call",
                            "allowed_executed_functions":sorted(r.REQUIRED_ROUTES)}
                    self.write(slot/(kind + ".json"),receipt)
        return root,natives,golden

    def compare(self,root,natives,golden):
        with patch.object(r,"Golden",return_value=golden):
            return r.compare(root,natives,revision=REVISION,source_revision=SOURCE,run_id=RUN)

    def test_complete_full_records_compare_and_fail_closed_for_stale_missing_or_forged_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            root,natives,golden = self.fixture(directory)
            result = self.compare(root,natives,golden)
            self.assertEqual(result["status"],"success")
            self.assertEqual(len(result["receipts"]),4)
            slot = root/"realization-linux-x86_64-py3.11"
            path = slot/"protocol.json"
            original = json.loads(path.read_text())
            mutations = (
                lambda v:v.update(revision="c"*40),
                lambda v:v.update(source_revision="d"*40),
                lambda v:v.update(run_id="stale"),
                lambda v:v.update(python_version="3.14.9"),
                lambda v:v.update(status="failure"),
                lambda v:v["checks"].pop(),
                lambda v:v["checks"].append(deepcopy(v["checks"][0])),
                lambda v:v["checks"][0].update(operation="unknown"),
                lambda v:v.update(artifact_directory="../outside"),
                lambda v:v["executables"]["core"].update(sha256="0"*64),
            )
            for mutation in mutations:
                changed = deepcopy(original); mutation(changed); self.write(path,changed)
                with self.assertRaises(AssertionError): self.compare(root,natives,golden)
            self.write(path,original)
            routing = slot/"routing.json"; saved = json.loads(routing.read_text())
            changed = deepcopy(saved); changed["guard"]["status"] = "missing"; self.write(routing,changed)
            with self.assertRaisesRegex(AssertionError,"guard"): self.compare(root,natives,golden)
            self.write(routing,saved)
            fourth = root/"realization-macos-arm64-py3.14"/"native-inputs.json"
            fourth.unlink()
            with self.assertRaises(AssertionError): self.compare(root,natives,golden)

    def test_rehashed_forged_full_report_cannot_replace_original_golden_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root,natives,golden = self.fixture(directory)
            slot = root/"realization-linux-x86_64-py3.11"
            path = slot/"routing.json"; receipt = json.loads(path.read_text())
            item = next(c for c in receipt["checks"] if "report" in c)
            old_pin = item["artifact"]; old_path = slot/"routing-reports"/(old_pin + ".json")
            value = json.loads(old_path.read_text()); value["forged"] = True
            new_pin = r.digest(value); self.write(old_path.with_name(new_pin + ".json"),value)
            for check in receipt["checks"]:
                if check["artifact"] == old_pin: check["artifact"] = new_pin
            del receipt["artifacts"][old_pin]; old_path.unlink()
            receipt["artifacts"][new_pin] = {"path":new_pin + ".json","bytes":len(r.canonical(value))+1,"canonical_sha256":new_pin}
            self.write(path,receipt)
            with self.assertRaisesRegex(AssertionError,"original oracle"): self.compare(root,natives,golden)
            report = slot/"routing-reports"/(new_pin + ".json")
            report.unlink(); report.symlink_to(path)
            with self.assertRaisesRegex(AssertionError,"symlinked"): self.compare(root,natives,golden)


if __name__ == "__main__": unittest.main()
