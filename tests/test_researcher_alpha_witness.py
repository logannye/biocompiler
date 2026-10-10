"""Pure corpus/witness checks; incomplete synthetic records are not native proof."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from tools import check_researcher_alpha as witness

ROOT = Path(__file__).resolve().parents[1]


def inert_result(case, original, *, exported=False):
    """Small metadata peer intentionally lacks native transport certification."""
    molecule = {"id": case["molecule_id"], "sequence": case["sequence"],
        "space": {"alphabet": "RNA", "topology": "linear", "length": case["length"]},
        "features": [{"id": region["id"], "path": {"spans": [{"start": region["start"], "end": region["end"]}]}}
                     for region in sorted(case["regions"], key=lambda row: row["id"])],
        "chemistry": {"cap": {"status": "declared", "identity": {"accession": "artificial_cap", "namespace": "software_fixture.chemical"}},
            "modifications": [], "terminal_tail": {"length": {"mode": "exact", "exact": 4}}}}
    candidate = {"construction": {"experimental_amounts": [], "inventory": {"molecules": [molecule],
        "complexes": [], "form_mappings": [], "role_instances": [{"id": "inert-role", "subject_id": molecule["id"],
            "subject_fingerprint": witness.canonical_digest(molecule)}]}},
        "implementation": {"nodes": [None] * case["graph"]["nodes"], "wires": [None] * case["graph"]["wires"]}}
    report = {"status": "checked_component_material", "empirical": "unassessed", "assembly_status": "pass", "context_status": "pass",
        "all_original_obligations_discharged": True, "artifact": "withheld", "export": "withheld", "obligations": [{"status": "discharged"}],
        "preservation": {"preservation": "pass", "coverage": {**case["bounded_domain"], "complete": True,
            "matched_prefixes": case["bounded_domain"]["prefixes_started"]}},
        "assembly": {"link_projections": [None] * case["graph"]["links"]}}
    result = {"candidate": candidate, "report": report, "artifact": None}
    if exported:
        manifest = {**deepcopy(original), "candidate": candidate, "assessment": report}
        result["artifact"] = {"fasta": case["fasta"], "fasta_sha256": case["fasta_sha256"],
            "manifest": manifest, "manifest_sha256": witness.canonical_digest(manifest)}
    return result


class ResearcherAlphaWitnessTests(unittest.TestCase):
    def setUp(self):
        self.packet = witness.checked_assets(ROOT, ROOT / witness.EXPECTED)
        self.addCleanup(patch.stopall)
        patch("subprocess.Popen", side_effect=AssertionError("Pure witness test attempted a process")).start()
        patch("subprocess.run", side_effect=AssertionError("Pure witness test attempted a process")).start()

    def test_independent_corpus_pins_and_complete_cases_are_inert(self):
        self.assertEqual(tuple(self.packet["inputs"]), ("staged", "comparison", "retry_cycle", "guarded_branch"))
        self.assertEqual([case["sequence"] for case in self.packet["expected"]["cases"]], ["CCAUGGCUUAAGGAAAA", "CGCAUGGCUUAAGGAAAA", "CCAUGGCUUAAGGAAAA", "CCAUGGCUUAAGGAAAA"])
        self.assertFalse(self.packet["expected"]["acceptance"])
        self.assertFalse(self.packet["expected"]["claim_scope"]["real_researcher_project_qualified"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / "data/researcher_alpha", root / "data/researcher_alpha")
            source = root / "data/researcher_alpha/staged-input.json"
            source.write_bytes(source.read_bytes() + b"\n")
            with self.assertRaisesRegex(AssertionError, "provenance"):
                witness.checked_assets(root, root / witness.EXPECTED)

    def test_complete_observation_census_is_additive_and_fail_closed(self):
        witness.check_census(witness.OBSERVATIONS)
        self.assertEqual(len(witness.OBSERVATIONS), 38)
        self.assertEqual(len(witness.LEGACY_OBSERVATIONS), 20)
        self.assertEqual(witness.OBSERVATIONS[:20], witness.LEGACY_OBSERVATIONS)
        for names in (witness.LEGACY_OBSERVATIONS, witness.OBSERVATIONS[:-1], witness.OBSERVATIONS[::-1],
                      witness.OBSERVATIONS + (witness.OBSERVATIONS[0],), (witness.OBSERVATIONS[0],) * 20):
            with self.subTest(names=names), self.assertRaisesRegex(AssertionError, "census"):
                witness.check_census(names)

    def test_finite_originals_are_frozen_complete_authority_with_independent_oracles(self):
        fixture = json.loads((ROOT / "core/test/data/policy_finite_machine_v01.json").read_text())
        for native, case in zip(fixture["cases"][:2], self.packet["expected"]["cases"][2:]):
            with self.subTest(case=case["id"]):
                original = self.packet["inputs"][case["id"]]
                self.assertEqual(original, {"request": native["request"], "limits": fixture["limits"]})
                self.assertEqual(case["sequence"], "CC" + "AUGGCUUAA" + "GG" + "AAAA")
                self.assertEqual(case["protein"], "MA*")
                self.assertEqual(case["graph"], {"nodes": native["expected"]["node_count"],
                    "wires": native["expected"]["wire_count"], "links": native["expected"]["link_count"]})
                value = inert_result(case, original)
                value["candidate"]["construction"]["inventory"]["molecules"] = [native["expected"]["molecule"]]
                witness.checked_result(value, case, original)
        self.assertEqual([case["bounded_domain"] for case in self.packet["expected"]["cases"][2:]], [
            {"histories": 36, "transitions": 82, "prefixes_started": 83},
            {"histories": 110, "transitions": 276, "prefixes_started": 277}])

    def test_public_typed_prepare_load_preserves_every_original_without_semantic_execution(self):
        from biocompiler.policy.finite_build import FiniteMachineBuild
        from biocompiler.policy.model import BuildRequest
        from biocompiler.policy.research_project import ResearchProject
        from tools.check_researcher_alpha_installed import expected_project
        example = witness.load_example(ROOT / "examples/researcher_alpha.py")
        with tempfile.TemporaryDirectory() as directory:
            for case in self.packet["expected"]["cases"][2:]:
                destination = Path(directory) / (case["id"] + ".json")
                with patch.object(ResearchProject, "from_build", wraps=ResearchProject.from_build) as create:
                    project = example.prepare(ROOT / "data/researcher_alpha" / case["input"], destination,
                        project_id="software.rehearsal." + case["id"],
                        title="Artificial software rehearsal: " + case["id"], version="1",
                        reuse_terms="Project-authored software test inputs; repository distribution terms remain separate.",
                        typed_finite=True)
                self.assertEqual(create.call_count, 1)
                self.assertIs(type(create.call_args.kwargs["build"]), FiniteMachineBuild)
                self.assertEqual(project.data, expected_project(case, self.packet))
                restored = ResearchProject.load(destination)
                self.assertIs(type(restored.build.document), BuildRequest)
                self.assertEqual(restored.build.to_request(), self.packet["inputs"][case["id"]]["request"])
                self.assertEqual(restored.build.to_limits(), self.packet["inputs"][case["id"]]["limits"])
                self.assertEqual(restored.data, project.data)
                detached = restored.build.to_request()
                detached["profile"] = "changed"
                self.assertEqual(restored.data, project.data)
                self.assertEqual(restored.preflight().native_status, "not_run")

    def test_typed_preparation_rejects_legacy_profile_without_publishing(self):
        example = witness.load_example(ROOT / "examples/researcher_alpha.py")
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "project.json"
            with self.assertRaisesRegex(ValueError, "finite-machine"):
                example.prepare(ROOT / "data/researcher_alpha/staged-input.json", destination,
                    project_id="wrong", title="wrong", version="1", reuse_terms="inert", typed_finite=True)
            self.assertFalse(destination.exists())

    def test_actual_feature_shape_and_coordinate_order_match_independent_oracle(self):
        staged = json.loads((ROOT / "core/test/data/policy_staged_material_v01.json").read_text())
        case = self.packet["expected"]["cases"][0]
        result = inert_result(case, self.packet["inputs"]["staged"])
        result["candidate"]["construction"]["inventory"]["molecules"] = [staged["expected"]["molecule"]]
        witness.checked_result(result, case, self.packet["inputs"]["staged"])
        molecule = result["candidate"]["construction"]["inventory"]["molecules"][0]
        self.assertEqual([row["id"] for row in molecule["features"]], ["cds", "poly_a", "utr3", "utr5"])

    def test_result_metadata_cannot_change_molecule_coordinates_domain_or_claim(self):
        for case in self.packet["expected"]["cases"]:
            original = self.packet["inputs"][case["id"]]
            witness.checked_result(inert_result(case, original), case, original)
            for mutate in (
                lambda value: value["report"].update(empirical="validated"),
                lambda value: value["report"]["preservation"]["coverage"].update(complete=False),
                lambda value: value["report"]["preservation"]["coverage"].update(histories=1),
                lambda value: value["report"]["obligations"].clear(),
                lambda value: value["candidate"]["construction"]["inventory"]["molecules"][0].update(sequence="AAA"),
                lambda value: value["candidate"]["construction"]["inventory"]["molecules"][0]["features"][0]["path"]["spans"][0].update(start=0),
                lambda value: value["candidate"]["construction"]["inventory"]["molecules"][0]["chemistry"]["terminal_tail"]["length"].update(exact=3),
                lambda value: value["candidate"]["implementation"]["wires"].pop(),
            ):
                value = inert_result(case, original)
                mutate(value)
                with self.subTest(case=case["id"], mutate=mutate), self.assertRaises(AssertionError):
                    witness.checked_result(value, case, original)

    def test_export_metadata_binds_both_files_and_complete_originals(self):
        case = self.packet["expected"]["cases"][0]
        original = self.packet["inputs"]["staged"]
        witness.checked_result(inert_result(case, original, exported=True), case, original, exported=True)
        for mutate in (
            lambda value: value["artifact"].update(fasta=">changed\nA\n"),
            lambda value: value["artifact"]["manifest"]["request"].update(profile="changed"),
            lambda value: value["artifact"].update(manifest_sha256="0" * 64),
        ):
            value = inert_result(case, original, exported=True)
            mutate(value)
            with self.subTest(mutate=mutate), self.assertRaises(AssertionError):
                witness.checked_result(value, case, original, exported=True)

    def test_capacity_and_completion_mutations_preserve_originals_and_repin_only_premises(self):
        original = self.packet["inputs"]["staged"]["request"]
        before = deepcopy(original)
        changed = witness.deficient_capacity(original)
        self.assertEqual(changed["implementation_request"], original["implementation_request"])
        capacities = [capacity for provider in changed["context"]["providers"] for capacity in provider["body"]["capacities"]
                      if capacity["unit"] == "machine_state_bits"]
        self.assertEqual([capacity["quantity"] for capacity in capacities], [2])
        for provider in changed["context"]["providers"]:
            self.assertEqual(provider["identity"]["content_fingerprint"], witness.canonical_digest(provider["body"]))
        completion = witness.completion_request(original)
        values = [row["response"]["value"] for row in completion["implementation_request"]["document"]["program"]["declarations"]
                  if row["$type"] == "Requirement" and row["id"] == "second_initiation"]
        self.assertEqual(values, ["completed"])
        self.assertEqual(original, before)

    def test_guard_allows_transport_resolution_and_denies_semantic_execution(self):
        boundary = witness.ResearcherBoundary(ROOT / "src/biocompiler")
        for name in ("biocompiler.core_distribution", "biocompiler.core_policy_component_selection", "biocompiler.policy.research_project"):
            self.assertTrue(boundary.allowed(name))
        for name in ("biocompiler.compiler", "biocompiler.semantics", "biocompiler_core"):
            with self.subTest(name=name), self.assertRaises(ImportError):
                boundary.find_spec(name, None)
        frame = SimpleNamespace(f_globals={"__name__": "biocompiler.policy.validation"}, f_code=SimpleNamespace(co_name="check"))
        with self.assertRaisesRegex(AssertionError, "authoring-check"):
            boundary.trace(frame, "call", None)

    def test_tracked_input_check_rejects_missing_census_and_changed_head_bytes(self):
        rows = []
        for name in witness.INPUTS:
            raw = (ROOT / name).read_bytes()
            blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            rows.append(b"100644 blob " + blob.encode() + b"\t" + name.encode())
        with patch.object(witness, "git", return_value=b"\0".join(rows) + b"\0"):
            self.assertEqual(set(witness.tracked_inputs(ROOT)), set(witness.INPUTS))
        with patch.object(witness, "git", return_value=b"\0".join(rows[:-1]) + b"\0"), self.assertRaisesRegex(AssertionError, "census"):
            witness.tracked_inputs(ROOT)
        rows[0] = b"100644 blob " + b"0" * 40 + b"\t" + witness.INPUTS[0].encode()
        with patch.object(witness, "git", return_value=b"\0".join(rows) + b"\0"), self.assertRaisesRegex(AssertionError, "HEAD"):
            witness.tracked_inputs(ROOT)

    def test_bundle_mutations_preserve_other_bytes_and_fixed_metadata(self):
        from biocompiler.core_client import decode_json, encode_json
        case, original = self.packet["expected"]["cases"][0], self.packet["inputs"]["staged"]
        result = inert_result(case, original, exported=True)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.zip"
            with zipfile.ZipFile(source, "w") as archive:
                for name, raw in (("program.fasta", case["fasta"].encode()), ("manifest.json", encode_json(result["artifact"]["manifest"]))):
                    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type, info.create_system, info.external_attr = zipfile.ZIP_STORED, 3, 0o100644 << 16
                    archive.writestr(info, raw)
            for kind in ("candidate", "fasta"):
                target = Path(directory) / (kind + ".zip")
                witness.changed_bundle(source, target, kind)
                with zipfile.ZipFile(source) as before, zipfile.ZipFile(target) as after:
                    self.assertEqual(before.namelist(), after.namelist())
                    unchanged = "program.fasta" if kind == "candidate" else "manifest.json"
                    self.assertEqual(before.read(unchanged), after.read(unchanged))
                    if kind == "candidate":
                        original_manifest = decode_json(before.read("manifest.json"))
                        changed_manifest = decode_json(after.read("manifest.json"))
                        expected = deepcopy(original_manifest)
                        inventory = expected["candidate"]["construction"]["inventory"]
                        molecule = inventory["molecules"][0]
                        molecule["sequence"] = "G" + molecule["sequence"][1:]
                        inventory["role_instances"][0]["subject_fingerprint"] = witness.canonical_digest(molecule)
                        self.assertEqual(changed_manifest, expected)
                        self.assertEqual(original_manifest, result["artifact"]["manifest"])
                    for entry in after.infolist():
                        self.assertEqual(entry.date_time, (1980, 1, 1, 0, 0, 0))
                        self.assertEqual(entry.compress_type, zipfile.ZIP_STORED)

    def test_candidate_tamper_repins_owned_roles_without_repairing_original_authority(self):
        for case in self.packet["expected"]["cases"]:
            original = self.packet["inputs"][case["id"]]
            candidate = inert_result(case, original)["candidate"]
            roles = candidate["construction"]["inventory"]["role_instances"]
            roles.append({**roles[0], "id": "second-inert-role"})
            before = deepcopy(candidate)
            changed = witness.changed_material_candidate(candidate)
            self.assertEqual(candidate, before)
            inventory = changed["construction"]["inventory"]
            self.assertEqual(inventory["molecules"][0]["sequence"], "G" + case["sequence"][1:])
            digest = witness.canonical_digest(inventory["molecules"][0])
            self.assertTrue(all(row["subject_fingerprint"] == digest for row in inventory["role_instances"]))
            inventory["molecules"][0]["sequence"] = case["sequence"]
            for role, previous in zip(inventory["role_instances"], roles):
                role["subject_fingerprint"] = previous["subject_fingerprint"]
            self.assertEqual(changed, before)
            for mutate in (lambda c: c["construction"]["inventory"]["complexes"].append({}),
                           lambda c: c["construction"]["inventory"]["form_mappings"].append({}),
                           lambda c: c["construction"]["experimental_amounts"].append({}),
                           lambda c: c["construction"]["inventory"]["role_instances"][0].update(subject_id="foreign"),
                           lambda c: c["construction"]["inventory"]["role_instances"][0].update(subject_fingerprint="0" * 64)):
                unsupported = deepcopy(candidate); mutate(unsupported)
                with self.assertRaisesRegex(AssertionError, "mutation requires"):
                    witness.changed_material_candidate(unsupported)

    def test_incomplete_reference_is_structural_qualification_without_native_claim(self):
        from biocompiler.policy.research_project import ResearchProject, ResearchProjectError
        control = self.packet["controls"]["qualification_control"]
        candidate = next(row for row in self.packet["qualification"]["candidates"] if row["id"] == control["source_candidate"])
        self.assertEqual(candidate["missing"], control["required_missing"])
        self.assertEqual(len(candidate["missing"]), 9)
        with self.assertRaisesRegex(ResearchProjectError, "complete versioned fields"):
            ResearchProject.from_data(candidate)

    def test_installed_mode_uses_owned_default_public_arguments_and_checks_resolved_pins(self):
        from biocompiler.core_client import CoreClient
        core = CoreClient(Path("/inert/core"), expected_sha256="1" * 64)
        verify = CoreClient(Path("/inert/verify"), role="verify", expected_sha256="2" * 64)
        example = witness.load_example(ROOT / "examples/researcher_alpha.py")
        resolved = lambda **kwargs: core if kwargs["role"] == "core" else verify
        # Stop at the public Verify call: dummy results test routing only and
        # cannot pass any transport, semantic or artifact-acceptance checker.
        built = SimpleNamespace(compiled=SimpleNamespace(executable="core", result={}),
                                verified=SimpleNamespace(executable="verify", result={}))
        with tempfile.TemporaryDirectory() as directory, patch("biocompiler.core_distribution.installed_core", side_effect=resolved) as resolver, \
                patch.object(example, "compile_project", return_value=built) as compile_project, \
                patch.object(example, "verify_project", side_effect=RuntimeError("routing stop")) as verify_project, \
                patch.object(witness, "checked_result"):
            with self.assertRaisesRegex(RuntimeError, "routing stop"):
                witness.exercise(self.packet, example, core, verify, lambda *args: None, Path(directory), use_installed_defaults=True)
            self.assertEqual(compile_project.call_args.kwargs, {"core": None, "verify": None})
            self.assertEqual(verify_project.call_args.kwargs, {"verify": None})
            self.assertEqual([call.kwargs["role"] for call in resolver.call_args_list], ["core", "verify"])
        with tempfile.TemporaryDirectory() as directory, patch("biocompiler.core_distribution.installed_core", return_value=verify):
            with self.assertRaisesRegex(AssertionError, "resolver differs"):
                witness.exercise(self.packet, example, core, verify, lambda *args: None, Path(directory), use_installed_defaults=True)


if __name__ == "__main__":
    unittest.main()
