"""Inert CAR campaign peers and byte-audit controls; no native acceptance."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from biocompiler import core_policy_expression_material as api
from biocompiler.core_client import CORE_VERSION, PROTOCOL, CoreClient, CoreProtocolError, encode_json
from tests import test_core_policy_expression_material as peer
from tests.test_core_policy import assessment, digest, semantic
from tools import check_car_payload as car

ROOT = Path(__file__).resolve().parents[1]
pin = peer.pin


def fixture_packet():
    return car.checked_assets(ROOT, ROOT / car.EXPECTED)


def literal_candidate(request):
    """An inert complete data record, copied from declared literals, never compiled."""
    authority = request["structure_authority"]
    template = authority["template"]
    molecule = deepcopy(template["sources"][0]["molecule"])
    def output_frame(value):
        if type(value) is dict:
            return {k: output_frame(v) for k, v in value.items()}
        if type(value) is list:
            return [output_frame(v) for v in value]
        return "rm61461.output.frame" if value == "rm61461.root.frame" else value
    molecule = output_frame(molecule)
    molecule["id"] = "payload"
    role = deepcopy(template["requirements"][0]["roles"][0])
    role.update(schema_version="biocompiler.molecule_role_instance.v0.1",subject_id="payload",subject_fingerprint=digest(molecule))
    return {"schema_version": api.CANDIDATE_SCHEMA, "construction": {
        "schema_version": "biocompiler.construction_content.v0.1",
        "authority_fingerprint": digest(template), "diagnostics": [], "experimental_amounts": [],
        "inventory": {"schema_version": "biocompiler.molecular_content_inventory.v0.1",
            "id": template["id"] + ".molecules", "molecules": [molecule], "complexes": [], "form_mappings": [], "role_instances": [role]},
        "member_order": ["payload"], "missing_members": [], "values": []}}


def structure(request, actual):
    leaf = peer.structure(request, actual)
    leaf["terminal_stop_codons"] = 2
    protein = request["structure_authority"]["members"][0]["product"]["sequence"]
    leaf["members"][0].update(expected_product=protein,translated_product=protein)
    # The peer independently compares complete retained original literal records.
    # It simulates a response only; production never executes this test helper.
    if actual != literal_candidate(request):
        leaf.update(content_outcome="fail",outcome="fail")
        leaf["content_reconstruction"].update(outcome="fail",reconstructed_fingerprint=None,
            diagnostics=[{"code":"inert_content_mismatch","path":"/construction","message":"Inert original differs"}])
        leaf["diagnostics"] = [{"code":"inert_content_mismatch","path":"/construction","message":"Inert original differs"}]
    return leaf


def report(request, actual):
    doc = request["document"]
    assessed = assessment(doc)
    definitions = doc["program"]["semantics"]["definitions"]
    assessed["unresolved_obligations"] = sorted(["policy_execution_and_lowering", "temporal_and_uncertainty_semantics", "persistent_encounter_identity_lifetime", "state_lifetime_capacity_and_inheritance", "effect_authorization_feedback_and_cancellation", "arbitration_fairness_and_conflict_resolution", "safety_and_progress_satisfaction", "requested_assurance_not_established", "realizability_and_target_suitability", "implementation_catalog_applicability", "chassis_capability_and_delivery_suitability", "requirement_satisfaction:" + request["selection"]["objective"], "implementation_applicability:" + request["selection"]["implementation"]["id"], *["semantic_definition:" + value["id"] for value in definitions]])
    max_nt = next(value["value"] for value in doc["program"]["declarations"] if value["id"] == "maximum_rna_nt")
    body = request["expression_contract"]["body"]
    admission = {"schema_version": "biocompiler.policy_expression_source_admission.v0.1", "status": "admitted_static_expression_source", "request_fingerprint": digest(request), "source_artifact_digest": digest(doc), "source_semantic_digest": digest(semantic(doc)), "objective": request["selection"]["objective"], "objective_path": "/document/program/declarations/6", "product": body["product"], "maximum_rna_nt": max_nt,
        "unresolved_obligations": sorted([*assessed["unresolved_obligations"], "expression_material_correspondence"]), "source_assessment": assessed, "temporal_execution": "not_requested_by_supported_objective", "expression_claim": "withheld", "empirical_realization": "unassessed", "human_use": "unassessed", "export": "withheld"}
    leaf = structure(request, actual)
    length = len(actual["construction"]["inventory"]["molecules"][0]["sequence"])
    bound_ok = length <= max_nt
    passed = bound_ok and leaf["outcome"] == "pass"
    pins = {"source": digest(admission), "structure": digest(leaf), "contract": request["expression_contract"]["identity"]}
    rows = []
    for name in admission["unresolved_obligations"]:
        if name in {"policy_execution_and_lowering", "temporal_and_uncertainty_semantics", "persistent_encounter_identity_lifetime", "state_lifetime_capacity_and_inheritance", "effect_authorization_feedback_and_cancellation", "arbitration_fairness_and_conflict_resolution"}:
            status, stage, evidence = "not_applicable", "closed_static_source_admission", {"source": digest(admission)}
        elif name.startswith("semantic_definition:"):
            definition_value = next(value for value in definitions if value["id"] == name.split(":", 1)[1])
            interpreted = digest(definition_value) in api._NORMATIVE_DEFINITION_DIGESTS
            status = "discharged" if interpreted else "conditional"
            stage = "closed_normative_static_interpretation" if interpreted else "resolved_original_context_or_component_premise"
            evidence = {"source": digest(admission), "definition": pin(definition_value), "body": definition_value, "contract": request["expression_contract"]["identity"]}
        elif name in {"realizability_and_target_suitability", "implementation_catalog_applicability", "chassis_capability_and_delivery_suitability"}:
            status, stage, evidence = "conditional" if passed else "unresolved", "supplied_expression_localization_and_recipient_premises", pins
        elif name.startswith("implementation_applicability:"):
            status, stage, evidence = "conditional" if passed else "unresolved", "complete_supplied_implementation_contract", pins
        else:
            status, stage, evidence = "discharged" if passed else "unresolved", "exact_static_encoding_and_length", pins
        rows.append({"obligation": name, "status": status, "stage": stage, "evidence": evidence})
    requirement = {"id": request["selection"]["objective"], "path": admission["objective_path"], "status": "pass" if passed else "fail", "product": body["product"], "member": "payload", "cds": "cds", "maximum_rna_nt": max_nt, "actual_rna_nt": length, "length_status": "pass" if bound_ok else "fail", "localization": body["localization"], "localization_status": "supplied_premise", "diagnostics": [] if bound_ok else [{"code": "expression_rna_length_requirement", "path": admission["objective_path"], "message": "RNA exceeds source bound."}]}
    return {"schema_version": api.REPORT_SCHEMA, "profile": api.REQUEST_PROFILE, "implementation": "biocompiler.ocaml.policy_expression_material_check.v0.1", "resource_profile": api.RESOURCE_PROFILE, "request_fingerprint": digest(request), "candidate_fingerprint": digest(actual), "invocation_fingerprint": digest({"request": request, "candidate": actual}), "status": "checked_expression_material" if passed else "not_accepted", "claim_scope": api.CLAIM, "premise": api.PREMISE,
        "source_admission": admission, "structure": leaf, "requirements": [requirement], "obligations": rows, "all_original_obligations_dispositioned": passed, "budgets": request["budgets"], "empirical": "unassessed", "human_use": "unassessed", "artifact": "withheld", "export": "withheld", "usage": {"unit": "logical_data_visits_and_child_semantic_work", "charged_work": 10000, "request_decoding_work": 2000}}



def mock_result(payload, operation):
    request = deepcopy(payload["request"])
    actual = deepcopy(payload.get("candidate", literal_candidate(request)))
    checked = report(request, actual)
    return {"schema_version": api.RESULT_SCHEMA, "implementation": api.IMPLEMENTATION, "resource_profile": api.RESOURCE_PROFILE,
        "validation_scope": api.VALIDATION_SCOPE, "request_fingerprint": digest(request), "candidate_fingerprint": digest(actual),
        "invocation_fingerprint": digest({"request": request,"candidate": actual}), "report_fingerprint": digest(checked),
        "candidate": actual,"report": checked,
        "artifact": peer.artifact(request,actual,checked) if operation == "export-policy-expression-material" else None,
        "usage": {"unit":"logical_data_visits_and_child_semantic_work","total_charged_work":20000,"checker_charged_work":10000}}


def make_evidence(folder, *, installed=False):
    """Real public orchestration/transport validation against explicitly inert peers.

    Returns (packet, ordered values, exercise fields). Every retained byte is
    published by the public project path; no native process is executable.
    """
    folder = Path(folder)
    folder.mkdir(exist_ok=True)
    packet = fixture_packet()
    core = CoreClient(Path(sys.executable), role="core")
    verify = CoreClient(Path("/usr/bin/true"), role="verify")
    def exchange(binary, encoded, timeout, cancelled):
        raw = json.loads(encoded)
        role = "core" if binary == core.executable else "verify"
        assert binary in (core.executable, verify.executable)
        op, payload = raw["operation"], raw["payload"]
        status, diagnostics = "ok", []
        if op == "capabilities":
            value = peer.capabilities(role)
        else:
            code = None
            if payload["request"]["budgets"]["max_work"] == 1:
                code = "policy_expression_material_work_limit"
            elif op == "replay-policy-expression-material":
                code = "policy_expression_replay"
            elif op == "export-policy-expression-material" and payload["candidate"] != literal_candidate(payload["request"]):
                code = "policy_expression_export_not_accepted"
            if code:
                status, value = "error", None
                diagnostics = [{"code":code,"path":"/inert","message":"Explicit inert negative; not native acceptance"}]
            else:
                value = mock_result(payload, op)
        return encode_json({"protocol": PROTOCOL,"request_id":raw["request_id"],"operation":op,"status":status,
            "result":value,"diagnostics":diagnostics,"core":{"implementation":"ocaml","version":CORE_VERSION,
                "protocol":PROTOCOL,"executable":role}}), (0 if status == "ok" else 2)
    def resolve(**kwargs):
        client = core if kwargs["role"] == "core" else verify
        client.negotiate(kwargs["operation"])
        return client
    values = {}
    def retain(name,value):
        values[name] = deepcopy(value)
        (folder/(name+".json")).write_bytes(encode_json(value))
    with patch("subprocess.Popen",side_effect=AssertionError("Native execution forbidden in inert CAR controls")), \
            patch("biocompiler.core_client._exchange",side_effect=exchange), \
            patch("biocompiler.policy.research_project.installed_core",side_effect=resolve):
        fields = car.exercise(packet, car.load_example(ROOT/car.EXAMPLE), core, verify, retain, folder,
            use_installed_defaults=installed)
        car.validate_files(values,packet,folder,**fields)
    return packet,values,fields


class CarPayloadCampaignTests(unittest.TestCase):
    def test_complete_public_path_joins_twenty_two_observations_and_all_twenty_nine_files(self):
        with tempfile.TemporaryDirectory() as d:
            packet,values,fields = make_evidence(d)
            self.assertEqual(tuple(values),car.OBSERVATIONS)
            self.assertEqual(len(values),22)
            self.assertEqual(len(list(Path(d).iterdir())),29)
            self.assertEqual(values["compile-core"]["candidate"],values["tight-compile-core"]["candidate"])
            self.assertFalse((Path(d)/"short.zip").exists())
            self.assertEqual(values["short-compile-core"]["report"]["requirements"][0]["id"],"encode_car")
            self.assertTrue(all(x["response"]["executable"] == x["role"] for x in fields["native_actions"]["actions"]))
            self.assertEqual(len(fields["native_actions"]["actions"]),22)

    def test_installed_resolution_negotiations_are_complete_without_path_or_timing_variability(self):
        with tempfile.TemporaryDirectory() as d:
            packet,values,fields = make_evidence(d,installed=True)
            self.assertEqual(fields["native_actions"]["resolution"],"owned_installed_defaults")
            self.assertEqual(len(fields["native_actions"]["actions"]),31)
            self.assertNotIn("/usr/bin",encode_json(fields["native_actions"]).decode())

    def test_oracle_and_reference_bytes_are_not_selected_by_changed_self_pins(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in car.COPY_INPUTS:
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
            car.checked_assets(root,root/car.EXPECTED)
            expected=json.loads((root/car.EXPECTED).read_bytes());expected["material"]["rna_sha256"]="0"*64
            (root/car.EXPECTED).write_bytes(encode_json(expected))
            with self.assertRaisesRegex(AssertionError,"literals"): car.checked_assets(root,root/car.EXPECTED)

    def test_all_observation_and_action_censuses_roles_originals_and_outputs_are_closed(self):
        with tempfile.TemporaryDirectory() as d:
            packet,values,_=make_evidence(d)
            edits = [lambda v:v.pop("short-no-publication"),lambda v:v.update(extra={}),
                lambda v:v["native-actions"]["actions"].pop(),
                lambda v:v["native-actions"]["actions"].append(deepcopy(v["native-actions"]["actions"][0])),
                lambda v:v["native-actions"]["actions"][1].update(role="verify"),
                lambda v:v["native-actions"]["actions"][1]["payload"]["request"]["project_context"].update(title="forged"),
                lambda v:v["native-actions"]["actions"][1]["response"].update(result=None),
                lambda v:v["native-actions"]["actions"][0]["response"]["result"]["profiles"].pop("policy_expression_material"),
                lambda v:v["native-actions"]["actions"].reverse()]
            for edit in edits:
                value=deepcopy(values);edit(value)
                with self.subTest(edit=edit), self.assertRaises((AssertionError,CoreProtocolError)):
                    car.check_observations(value,packet)

    def test_complete_source_metadata_and_conditional_scope_cannot_be_relabelled(self):
        with tempfile.TemporaryDirectory() as d:
            packet,values,_=make_evidence(d)
            edits=[lambda v:v["originals"]["sources"][0].update(role="clinical proof"),
                lambda v:v["typed-roundtrip"].update(native_status="pass"),
                lambda v:v["compile-core"]["report"].update(empirical="proven"),
                lambda v:v["short-compile-core"]["report"]["requirements"][0].update(id="another"),
                lambda v:v["changed-metadata"].update(changed_project_sha256="0"*64)]
            for edit in edits:
                value=deepcopy(values);edit(value)
                with self.subTest(edit=edit),self.assertRaises((AssertionError,CoreProtocolError)):
                    car.check_observations(value,packet)

    def test_repinning_observation_project_export_or_mutant_bytes_does_not_change_original_authority(self):
        with tempfile.TemporaryDirectory() as d:
            packet,values,fields=make_evidence(d);folder=Path(d)
            for filename in ("originals.json","base-project.json","base.zip","base-changed-candidate.zip","base-changed-fasta.zip"):
                path=folder/filename;original=path.read_bytes();path.write_bytes(original+b" ")
                with self.subTest(file=filename),self.assertRaises((AssertionError,ValueError,CoreProtocolError)):
                    car.validate_files(values,packet,folder,**fields)
                path.write_bytes(original)
            (folder/"extra.json").write_text("{}")
            with self.assertRaisesRegex(AssertionError,"census"):car.validate_files(values,packet,folder,**fields)

    def test_missing_or_symlinked_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            packet,values,fields=make_evidence(d);folder=Path(d);path=folder/"originals.json";raw=path.read_bytes();path.unlink()
            with self.assertRaisesRegex(AssertionError,"census"):car.validate_files(values,packet,folder,**fields)
            target=folder.parent/(folder.name+"-outside.json");target.write_bytes(raw)
            try:
                path.symlink_to(target)
                with self.assertRaisesRegex(AssertionError,"regular|observation"):car.validate_files(values,packet,folder,**fields)
            finally:target.unlink()

    def test_source_and_material_mutations_are_exact_single_changes_with_full_repins(self):
        packet=fixture_packet();request=packet["request"];candidate=literal_candidate(request)
        changed=car.changed_candidate(candidate);m=changed["construction"]["inventory"]["molecules"][0]
        self.assertNotEqual(candidate,changed)
        self.assertEqual(m["sequence"][:8],packet["expected"]["material"]["rna"][:8])
        self.assertEqual(m["sequence"][9:],packet["expected"]["material"]["rna"][9:])
        self.assertEqual((packet["expected"]["material"]["rna"][8],m["sequence"][8]),("A","G"))
        self.assertEqual(changed["construction"]["inventory"]["role_instances"][0]["subject_fingerprint"],digest(m))
        authority=car.changed_authority(request)
        self.assertEqual(authority["expression_contract"]["identity"]["content_fingerprint"],digest(authority["expression_contract"]["body"]))
        self.assertEqual(authority["expression_contract"]["body"]["material"]["structure_sha256"],digest(authority["structure_authority"]))
        self.assertEqual(car.request_for(packet,"tight")["structure_authority"],request["structure_authority"])
        from biocompiler.ir.circuit_molecules import CircuitMolecule
        # Domain serialization alone, never construction or acceptance.
        CircuitMolecule.from_dict(m)
        CircuitMolecule.from_dict(authority["structure_authority"]["template"]["sources"][0]["molecule"])
        missing=car.changed_candidate(candidate,"chemistry")
        CircuitMolecule.from_dict(missing["construction"]["inventory"]["molecules"][0])

    def test_native_rejection_codes_complete_responses_and_verify_producer_denial_are_not_labels(self):
        with tempfile.TemporaryDirectory() as d:
            packet,values,_=make_evidence(d)
            edits=[lambda v:v["forged-replay"].update(diagnostics=[]),
                lambda v:v["work-exhaustion"]["diagnostics"][0].update(code="unrelated_failure"),
                lambda v:v["changed-candidate"].update(bundle_sha256="not-a-digest"),
                lambda v:v["changed-fasta"].update(bundle_sha256=None),
                lambda v:v["native-actions"]["actions"][2]["response"]["result"]["operations"].append("compile-policy-expression-material")]
            for edit in edits:
                value=deepcopy(values);edit(value)
                with self.subTest(edit=edit),self.assertRaises((AssertionError,CoreProtocolError)):
                    car.check_observations(value,packet)

    def test_exact_json_action_and_project_authority_reject_bool_integer_aliases(self):
        with tempfile.TemporaryDirectory() as d:
            packet,values,_=make_evidence(d)
            changed=deepcopy(values)
            source=changed["native-actions"]["actions"][1]["payload"]["request"]["structure_authority"]["template"]["sources"][0]["molecule"]
            next(feature for feature in source["features"] if feature["id"]=="cds")["reading_frame"]=False
            with self.assertRaisesRegex(AssertionError,"payload"):
                car.check_observations(changed,packet)
            changed=deepcopy(values)
            source=changed["originals"]["request"]["structure_authority"]["template"]["sources"][0]["molecule"]
            next(feature for feature in source["features"] if feature["id"]=="cds")["reading_frame"]=False
            changed["typed-roundtrip"]["project_sha256"]=digest(changed["originals"])
            changed["typed-roundtrip"]["request_sha256"]=digest(changed["originals"]["request"])
            with self.assertRaisesRegex(AssertionError,"original project"):
                car.check_observations(changed,packet)
            changed=deepcopy(values)
            changed["native-actions"]["actions"][1]["response"]["result"]["candidate"]["construction"]["inventory"]["molecules"][0]["features"][0]["reading_frame"]=False
            with self.assertRaisesRegex(AssertionError,"complete retained result"):
                car.check_observations(changed,packet)

    def test_development_entrypoint_rejects_offline_identity_before_any_native_operation(self):
        from argparse import Namespace
        with patch.dict("os.environ",{},clear=True),patch("subprocess.Popen",side_effect=AssertionError("No native or Git invocation")):
            with self.assertRaisesRegex(ValueError,"hosted|GITHUB"):
                car.run(Namespace(core=Path("/none"),verify=Path("/none"),expected=ROOT/car.EXPECTED,output=ROOT/car.OUTPUT))

    def test_fresh_import_guard_permits_public_preparation_and_denies_python_semantic_execution(self):
        code = r"""
from pathlib import Path
import sys,tempfile
from unittest.mock import patch
root=Path(sys.argv[1]).resolve()
sys.path[:0]=[str(root/'src'),str(root)]
from tools import check_car_payload as c
assert not any(name=='biocompiler' or name.startswith('biocompiler.') for name in sys.modules)
guard=c.CarBoundary(root/'src/biocompiler')
sys.meta_path.insert(0,guard);sys.setprofile(guard.trace)
try:
 with patch('subprocess.Popen',side_effect=AssertionError('no native')):
  example=c.load_example(root/c.EXAMPLE)
  with tempfile.TemporaryDirectory() as d:example.prepare(Path(d)/'p.json',maximum_rna_nt=1800,three_prime_end='designer_supplied_hydroxyl')
  assert sys.getprofile() == guard.trace
  assert c.REQUIRED_MODULES <= set(guard.origins())
  from biocompiler.compiler.request import _mapping
  try:_mapping({},'forbidden')
  except AssertionError:pass
  else:raise AssertionError('Python compiler call escaped')
finally:sys.setprofile(None);sys.meta_path.remove(guard)
assert len(guard.denied)==1
"""
        with tempfile.TemporaryDirectory() as directory:
            completed=subprocess.run([sys.executable,"-I","-B","-c",code,str(ROOT)],cwd=directory,capture_output=True,text=True,timeout=30)
        self.assertEqual(completed.returncode,0,completed.stderr)


if __name__ == "__main__":unittest.main()
