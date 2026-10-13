"""Pure campaign authority, edit and invocation-plan checks; no native simulation."""
from copy import deepcopy
from dataclasses import asdict
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import subprocess
import sys
import unittest
import zipfile
from unittest.mock import patch

from tools import check_controlled_car_reference as campaign

PROJECT = campaign.ROOT / "data/car_controlled_reference/project.json"


class ControlledCarReferenceCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = campaign.checked_project(PROJECT)
        cls.cases = campaign.cases(cls.packet["project"])

    def test_original_authority_has_independent_complete_sequence_and_source_pins(self):
        packet = self.packet
        self.assertEqual(packet["pins"]["project"]["sha256"], campaign.PROJECT_SHA256)
        self.assertEqual([len(value) for value in packet["sequences"]], [1830, 2097])
        self.assertEqual([row["protein_aa"] for row in packet["expected"]["members"]], [504, 593])
        self.assertEqual(len(packet["project"].data["sources"]), 13)
        self.assertEqual(set(packet["pins"]["local_sources"]), {"controlled.acquisition.inventory",
            "car.rm61461.reference_pack", "controlled.car197206.adaptation", "controlled.car197206.contract"})
        self.assertEqual(packet["project"].preflight().native_status, "not_run")
        self.assertEqual(packet["project"].controlled.native_status, "not_performed")

    def test_identity_join_accepts_richer_native_authority_and_rejects_stale_source_or_run(self):
        revision = "35deebfc5f8842bb33f80323e953627737af26b2"
        identity = {"revision": revision, "head_revision": revision,
                    "run_id": "38333487924", "run_attempt": "1"}
        authority = {"revision": revision, "tree": "a" * 40,
                     "run_id": "38333487924", "run_attempt": "1", "event": "push",
                     "ref": "refs/heads/codex/dev-policy/public-reference-readiness",
                     "repository": "example/biocompiler",
                     "workflow_ref": "example/biocompiler/.github/workflows/policy-development.yml@refs/heads/codex/dev-policy/public-reference-readiness",
                     "system": "Linux", "machine": "x86_64"}
        before = deepcopy(authority)
        campaign.check_native_identity(identity, authority)
        self.assertEqual(authority, before)
        self.assertNotEqual(set(identity), set(authority))
        for field, value in (("revision", "b" * 40), ("head_revision", "b" * 40),
                             ("run_id", "38333487925"), ("run_attempt", "2")):
            with self.subTest(side="campaign", field=field), self.assertRaisesRegex(AssertionError, "identity differ"):
                campaign.check_native_identity({**identity, field: value}, authority)
            if field != "head_revision":
                with self.subTest(side="native", field=field), self.assertRaisesRegex(AssertionError, "identity differ"):
                    campaign.check_native_identity(identity, {**authority, field: value})
        with self.assertRaisesRegex(AssertionError, "identity differ"):
            campaign.check_native_identity(identity, {**authority, "event": "pull_request"})

    def test_changed_original_oracle_contract_or_local_source_cannot_enter_native(self):
        with tempfile.TemporaryDirectory() as directory:
            changed = Path(directory) / "project.json"
            changed.write_bytes(PROJECT.read_bytes() + b"\n")
            with self.assertRaisesRegex(AssertionError, "authority changed"):
                campaign.checked_project(changed)
        original_pin = campaign.file_pin
        for changed_path in (campaign.EXPECTED, campaign.CONTRACT,
                             campaign.ROOT / "data/car_controlled_reference/source-inventory.json"):
            def changed_pin(path, *args):
                value = original_pin(path, *args)
                if Path(path) == changed_path:
                    value["sha256"] = "0" * 64
                return value
            with self.subTest(path=changed_path), patch.object(campaign, "file_pin", changed_pin), self.assertRaises(AssertionError):
                campaign.checked_project(PROJECT)

    def test_public_edits_preserve_actual_delays_complete_material_and_project_sources(self):
        original = self.cases["baseline"].request["behavior_request"]["original"]
        for name, project in self.cases.items():
            changed = project.request["behavior_request"]["original"]
            with self.subTest(name=name):
                self.assertEqual(changed["material_authority"], original["material_authority"])
                self.assertEqual(changed["mechanism_model"], original["mechanism_model"])
                self.assertEqual(project.data["sources"], self.packet["project"].data["sources"])
                self.assertEqual(changed["source_authority"]["control_contract"]["actual_delays"],
                                 {"onset_ticks": 1, "cessation_ticks": 1, "reactivation_ticks": 1})
        deadlines = self.cases["tight-deadlines"].request["behavior_request"]["original"]["source_authority"]["control_contract"]["requested_deadlines"]
        self.assertEqual(set(deadlines.values()), {1})
        for name, member, total in (("short-member", 2096, 3927), ("short-total", 2097, 3926)):
            resources = self.cases[name].limits["resources"]
            self.assertEqual((resources["max_member_rna_nt"], resources["max_total_rna_nt"]), (member, total))

    def test_horizon_edit_requires_explicit_original_domain_and_readout_samples(self):
        for name, horizon in (("horizon-eleven", 11), ("short-horizon", 9)):
            request = self.cases[name].request
            original = request["behavior_request"]["original"]
            domain = original["operating_domain"]
            self.assertEqual(domain["horizon_tick"], horizon)
            self.assertEqual([row["tick"] for row in domain["fixed_inputs"]], [tick for tick in range(horizon + 1) if tick != 2])
            self.assertEqual(request["behavior_request"]["readout_evidence"]["samples"],
                             [{"tick": tick, "observed_tick": tick, "status": "valid"} for tick in range(horizon + 1)])
            self.assertEqual(domain["physical_factors"], [{"input": "controller", "ticks": [2], "values": ["disabled"]}])
            self.assertEqual(domain["intervention_cutoff_tick"], 6)
            oracle = campaign.expected_case(name, request, self.packet["sequences"])
            self.assertEqual((oracle["histories"], oracle["prefixes"], oracle["transitions"]), (2, horizon * 2 + 1, horizon * 2))

    def test_controller_tampering_changes_body_without_repairing_independent_definition_pin(self):
        baseline = self.cases["baseline"].request["behavior_request"]["original"]
        changed = self.cases["stale-controller-contract"].request["behavior_request"]["original"]
        identifier = baseline["source_authority"]["control_contract"]["controller"]["definition"]["id"]
        definitions = lambda original: original["source_authority"]["document"]["program"]["semantics"]["definitions"]
        before = next(row for row in definitions(baseline) if row["id"] == identifier)
        after = next(row for row in definitions(changed) if row["id"] == identifier)
        self.assertNotEqual(before["meaning"], after["meaning"])
        self.assertEqual(baseline["source_authority"]["control_contract"], changed["source_authority"]["control_contract"])
        self.assertEqual({key: value for key, value in before.items() if key != "meaning"},
                         {key: value for key, value in after.items() if key != "meaning"})

    def test_rejection_diagnostics_cannot_be_replaced_by_unrelated_failure_or_pass(self):
        for name, (code, message) in campaign.REJECTION.items():
            value = {"status": "error", "diagnostics": [{"code": code, "message": message, "path": None}]}
            campaign.check_rejection(value, name)
            for mutate in (lambda row: row.update(status="ok"),
                           lambda row: row["diagnostics"][0].update(code="transport_timeout"),
                           lambda row: row["diagnostics"][0].update(message="unrelated"),
                           lambda row: row["diagnostics"].clear()):
                changed = deepcopy(value); mutate(changed)
                with self.subTest(name=name), self.assertRaises(AssertionError):
                    campaign.check_rejection(changed, name)

    def test_invocation_plan_includes_all_handshakes_roles_and_mutation_payloads(self):
        # Deliberately nonaccepted placeholders only exercise an invocation plan.
        # No report checker is called and no fake native PASS is manufactured.
        candidate = {"material_candidate": {"construction": {"inventory": {
            "molecules": [{"id": "car197", "sequence": "AAAAAAAAA"}, {"id": "car206", "sequence": "AAAAAAAAA"}],
            "role_instances": []}}}}
        values = {name + "-prepared": {"project": project.data, "preflight": asdict(project.preflight())}
                  for name, project in self.cases.items()}
        values.update({name + "-compile": {"candidate": candidate, "report": {"test_only": "not_native_evidence"}}
                       for name in campaign.ACCEPTED})
        actions = campaign.expected_actions(values)
        self.assertEqual(len(actions), 41)
        self.assertEqual(sum(row["operation"] == "capabilities" for row in actions), 20)
        self.assertEqual(actions[-1]["role"], "verify")
        self.assertEqual(actions[-1]["operation"], "compile-policy-controlled-workflow")
        for name in ("changed-candidate-a", "changed-candidate-b"):
            action = next(row for row in actions if row.get("name") == name)
            molecules = action["payload"]["candidate"]["material_candidate"]["construction"]["inventory"]["molecules"]
            self.assertEqual(molecules[0 if name.endswith("a") else 1]["sequence"][8], "C")
            self.assertEqual(molecules[0 if name.endswith("a") else 1]["sequence"][0], "A")
        self.assertEqual(candidate["material_candidate"]["construction"]["inventory"]["molecules"][0]["sequence"], "AAAAAAAAA")
        self.assertEqual(len(campaign.OBSERVATIONS), 32)
        self.assertEqual(len(set(campaign.OBSERVATIONS)), 32)

    def test_check_inputs_cli_is_inert_and_native_run_refuses_local_host(self):
        with patch("subprocess.Popen", side_effect=AssertionError("No native execution during original checks")), patch("sys.stdout", new_callable=io.StringIO) as output:
            campaign.main(["--project", str(PROJECT), "--check-inputs"])
        self.assertIn('"native_status": "not_run"', output.getvalue())
        self.assertIn("separately_audited_not_replayed_hosted", output.getvalue())
        with patch.dict(campaign.os.environ, {"GITHUB_ACTIONS": "false", "RUNNER_ENVIRONMENT": "local"}), self.assertRaisesRegex(AssertionError, "hosted-only"):
            campaign.run(SimpleNamespace(project=PROJECT, core="unused", verify="unused", output="unused"))

    def test_exact_hosted_input_cli_works_with_source_only_pythonpath(self):
        environment = dict(os.environ, PYTHONPATH="src", PYTHONDONTWRITEBYTECODE="1")
        # This child only performs Python original-input inspection. It receives
        # neither executable paths nor native-run flags and cannot select them.
        result = subprocess.run([sys.executable, "-B", "tools/check_controlled_car_reference.py",
            "--project", "data/car_controlled_reference/project.json", "--check-inputs"],
            cwd=campaign.ROOT, env=environment, text=True, capture_output=True, timeout=30, check=True)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["status"], "original_inputs_checked")
        self.assertEqual(receipt["native_status"], "not_run")
        self.assertEqual(receipt["inputs"]["project"]["sha256"], campaign.PROJECT_SHA256)

    def test_candidate_mutation_keeps_cap_and_modified_u_sites_decodable(self):
        originals = self.packet["project"].request["behavior_request"]["original"]["material_authority"]["template"]["sources"]
        molecules = [deepcopy(row["molecule"]) for row in originals]
        candidate = {"material_candidate": {"construction": {"inventory": {
            "molecules": molecules, "role_instances": [{"subject_id": row["id"], "subject_fingerprint": campaign.digest(row)} for row in molecules]}}}}
        for name, index in (("changed-candidate-a", 0), ("changed-candidate-b", 1)):
            changed = campaign.changed_candidate(candidate, name)
            inventory = changed["material_candidate"]["construction"]["inventory"]
            before, after = molecules[index], inventory["molecules"][index]
            self.assertEqual([(offset, a, b) for offset, (a, b) in enumerate(zip(before["sequence"], after["sequence"], strict=True)) if a != b], [(8, "A", "C")])
            self.assertEqual(before["chemistry"], after["chemistry"])
            self.assertEqual(inventory["molecules"][1 - index], molecules[1 - index])
            self.assertEqual(inventory["role_instances"][index]["subject_fingerprint"], campaign.digest(after))
            with tempfile.TemporaryDirectory() as directory:
                source, target = Path(directory) / "source.zip", Path(directory) / "changed.zip"
                with zipfile.ZipFile(source, "x") as archive:
                    archive.writestr("program.fasta", b"unchanged-export-bytes")
                    archive.writestr("manifest.json", campaign.encode_json({"candidate": candidate}))
                campaign.changed_bundle(source, target, name)
                with zipfile.ZipFile(target) as archive:
                    self.assertEqual(archive.read("program.fasta"), b"unchanged-export-bytes")
                    self.assertEqual(campaign.decode_json(archive.read("manifest.json"))["candidate"], changed)

    def test_real_fasta_oracle_wraps_at_eighty_and_preserves_both_complete_sequences(self):
        fasta = campaign.expected_fasta(self.packet["sequences"])
        records = fasta.rstrip("\n").split(">")
        self.assertEqual(records[0], "")
        self.assertEqual(len(records), 3)
        for index, (record, sequence) in enumerate(zip(records[1:], self.packet["sequences"], strict=True)):
            lines = record.splitlines()
            self.assertEqual(lines[0], "rna_%04d alphabet=RNA" % (index + 1))
            self.assertEqual("".join(lines[1:]), sequence)
            self.assertEqual(len(lines) - 1, (len(sequence) + 79) // 80)
            self.assertTrue(all(len(line) == 80 for line in lines[1:-1]))
            self.assertEqual(len(lines[-1]), len(sequence) % 80)
        self.assertTrue(fasta.endswith("\n"))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pair.zip"
            artifact = {"fasta": fasta, "manifest": {"test_scope": "representation_only_not_native_acceptance"}}
            with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("program.fasta", fasta)
                archive.writestr("manifest.json", campaign.encode_json(artifact["manifest"]))
            observed = campaign.check_pair(path, {"artifact": artifact}, self.packet["sequences"])
            self.assertEqual(observed["fasta_sha256"], campaign.hashlib.sha256(fasta.encode()).hexdigest())
            artifact["fasta"] = ">rna_0001 alphabet=RNA\n" + self.packet["sequences"][0] + "\n>rna_0002 alphabet=RNA\n" + self.packet["sequences"][1] + "\n"
            with self.assertRaises(AssertionError):
                campaign.check_pair(path, {"artifact": artifact}, self.packet["sequences"])

    def test_wrapped_fasta_mutations_target_distinct_exact_member_headers(self):
        original = campaign.expected_fasta(self.packet["sequences"]).encode()
        def sequences(raw):
            return [b"".join(record.splitlines()[1:]) for record in raw.split(b">")[1:]]
        for name, index in (("changed-fasta-a", 0), ("changed-fasta-b", 1)):
            changed = campaign.changed_fasta(original, name)
            before_members, after_members = sequences(original), sequences(changed)
            self.assertEqual(after_members[index], b"G" + before_members[index][1:])
            self.assertEqual(after_members[1 - index], before_members[1 - index])
            self.assertEqual(sum(a != b for a, b in zip(original, changed, strict=True)), 1)
            with tempfile.TemporaryDirectory() as directory:
                source, target = Path(directory) / "source.zip", Path(directory) / "changed.zip"
                manifest = {"test_scope": "representation_only_not_native_acceptance"}
                with zipfile.ZipFile(source, "x") as archive:
                    archive.writestr("program.fasta", original)
                    archive.writestr("manifest.json", campaign.encode_json(manifest))
                campaign.changed_bundle(source, target, name)
                with zipfile.ZipFile(target) as archive:
                    self.assertEqual(archive.read("program.fasta"), changed)
                    self.assertEqual(campaign.decode_json(archive.read("manifest.json")), manifest)
        with self.assertRaises(AssertionError):
            campaign.changed_fasta(original.replace(b">rna_0002 alphabet=RNA", b">rna_0001 alphabet=RNA"), "changed-fasta-b")


if __name__ == "__main__":
    unittest.main()
