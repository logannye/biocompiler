"""Expression-project orchestration with inert peers, never native acceptance."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from biocompiler.core_client import (
    CORE_VERSION, PROTOCOL, CoreCancelled, CoreClient, CoreProtocolError,
    CoreTransportError, encode_json,
)
from biocompiler.policy import research_project as project_api
from biocompiler.policy.expression_material import ExpressionMaterialRequest
from biocompiler.policy import car_reference, project_sources
from tests import test_core_policy_component_material as old_peer
from tests import test_core_policy_expression_material as peer


class ExpressionResearchProjectTests(unittest.TestCase):
    def setUp(self):
        self.request = peer.original()
        self.build = ExpressionMaterialRequest.from_request(self.request)
        self.project = project_api.ResearchProject.from_expression(self.build)
        self.core = CoreClient(Path(sys.executable), role="core")
        self.verify = CoreClient(Path("/usr/bin/true"), role="verify")
        self.calls = []
        guard = patch("subprocess.Popen", side_effect=AssertionError("Native execution forbidden in inert tests"))
        guard.start()
        self.addCleanup(guard.stop)

    def exchange(self, *, on_operation=None, fail_export=False, response_role=None):
        def respond(binary, encoded, timeout, cancelled):
            invocation = json.loads(encoded)
            self.assertIn(binary, (self.core.executable, self.verify.executable))
            role = "core" if binary == self.core.executable else "verify"
            operation = invocation["operation"]
            self.calls.append((role, deepcopy(invocation)))
            if operation == "capabilities":
                value = peer.capabilities(role)
            else:
                if fail_export and operation == "export-policy-expression-material":
                    raise CoreTransportError("Inert Verify transport failure")
                value = peer.result(invocation["payload"], operation)
            if on_operation:
                on_operation(operation, value)
            return encode_json({
                "protocol": PROTOCOL, "request_id": invocation["request_id"],
                "operation": operation, "status": "ok", "result": value,
                "diagnostics": [], "core": {"implementation": "ocaml", "version": CORE_VERSION,
                    "protocol": PROTOCOL, "executable": response_role or role},
            }), 0
        return patch("biocompiler.core_client._exchange", side_effect=respond)

    def test_typed_roundtrip_and_canonical_load_save_preserve_complete_static_authority(self):
        original = deepcopy(self.project.data)
        self.assertEqual(original["schema_version"], "biocompiler.research_project.v0.2")
        self.assertEqual(original["route"], "expression_material")
        self.assertIsNone(original["limits"])
        self.assertIsInstance(self.project.expression, ExpressionMaterialRequest)
        self.assertEqual(self.project.expression.to_request(), self.build.to_request())
        self.request["project_context"]["sources"][0]["sha256"] = "0" * 64
        self.build.to_request()["project_context"].clear()
        self.project.request.clear()
        self.project.data["sources"].clear()
        self.assertEqual(self.project.data, original)
        with self.assertRaises(FrozenInstanceError):
            self.project._json = b"{}"
        with self.assertRaises(project_api.ResearchProjectError):
            project_api.ResearchProject.from_expression(self.request)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.json"
            self.project.dump(path)
            loaded = project_api.ResearchProject.load(path)
            self.assertEqual(path.read_bytes(), encode_json(original))
            self.assertEqual(loaded.expression.to_request(), original["request"])
            self.assertEqual(loaded.digest, hashlib.sha256(encode_json(original)).hexdigest())
            with self.assertRaisesRegex(project_api.ResearchProjectError, "original"):
                loaded.dump(path, replace=True)
        ready = self.project.preflight()
        self.assertEqual((ready.native_status, ready.biological_status, ready.provenance_status),
                         ("not_run", "unassessed", "caller_declared"))

    def test_every_project_context_field_and_source_record_is_original_authority(self):
        changes = [("project_id", "foreign.id"), ("title", "Foreign title"),
                   ("assumptions", ["Changed applicability premise"])]
        for key, value in changes:
            data = self.project.data
            data[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(project_api.ResearchProjectError, "metadata"):
                project_api.ResearchProject.from_data(data)
        for key in ("id", "locator", "version", "sha256", "role", "reuse_terms"):
            data = self.project.data
            data["sources"][0][key] = "0" * 64 if key == "sha256" else "foreign"
            with self.subTest(source_key=key), self.assertRaisesRegex(project_api.ResearchProjectError, "metadata"):
                project_api.ResearchProject.from_data(data)
        request = self.project.request
        request["project_context"]["sources"][0]["sha256"] = "0" * 64
        changed = project_api.ResearchProject.from_expression(ExpressionMaterialRequest.from_request(request))
        self.assertNotEqual(changed.digest, self.project.digest)
        self.assertEqual(changed.data["sources"], request["project_context"]["sources"])

    def test_schema_route_and_timeless_limits_are_closed_without_legacy_conversion(self):
        for change in ({"schema_version": project_api.SCHEMA}, {"route": "component_material"},
                       {"limits": {}}, {"limits": {"max_work": 1}}, {"limits": []}, {"limits": False}):
            with self.subTest(change=change), self.assertRaises(project_api.ResearchProjectError):
                project_api.ResearchProject.from_data({**self.project.data, **change})
        old = self.project.data
        old.update(request=old_peer.original(), route="component_material", limits={"max_work": 1})
        with self.assertRaisesRegex(project_api.ResearchProjectError, "v0.1"):
            project_api.ResearchProject.from_data(old)
        with self.assertRaisesRegex(project_api.ResearchProjectError, "temporal"):
            _ = self.project.limits
        with self.assertRaisesRegex(project_api.ResearchProjectError, "finite-machine"):
            _ = self.project.build

    def test_core_compile_fresh_verify_paired_export_and_reopen_use_exact_originals(self):
        with tempfile.TemporaryDirectory() as directory, self.exchange():
            output = Path(directory) / "expression.zip"
            built = self.project.compile(output=output, core=self.core, verify=self.verify)
            original_bytes = output.read_bytes()
            reopened = self.project.verify_bundle(output, verify=self.verify)
            self.assertEqual((built.compiled.executable, built.verified.executable, reopened.executable),
                             ("core", "verify", "verify"))
            self.assertEqual(reopened.artifact, built.verified.artifact)
            self.assertEqual(built.project_sha256, self.project.digest)
            self.assertEqual(output.read_bytes(), original_bytes)
            self.assertEqual([(role, call["operation"]) for role, call in self.calls], [
                ("core", "capabilities"), ("core", "compile-policy-expression-material"),
                ("verify", "capabilities"), ("verify", "export-policy-expression-material"),
                ("verify", "capabilities"), ("verify", "export-policy-expression-material"),
            ])
            for _, call in self.calls:
                if call["operation"] == "capabilities":
                    continue
                self.assertEqual(call["payload"]["request"], self.project.request)
                self.assertNotIn("limits", call["payload"])
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.namelist(), ["program.fasta", "manifest.json"])
                manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(manifest["request"]["project_context"], self.project.request["project_context"])
                self.assertNotIn("limits", manifest)
                self.assertEqual(manifest["empirical"], "unassessed")

    def test_explicit_roles_and_installed_resolution_keep_producer_and_verifier_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "expression.zip"
            with patch.object(CoreClient, "call", side_effect=AssertionError("Role error must precede transport")):
                for core, verify in ((self.verify, self.verify), (self.core, self.core)):
                    with self.subTest(core=core.role, verify=verify.role), self.assertRaisesRegex(project_api.ResearchProjectError, "role"):
                        self.project.compile(output=output, core=core, verify=verify)
            def installed(**kwargs):
                return self.core if kwargs["role"] == "core" else self.verify
            with self.exchange(), patch.object(project_api, "installed_core", side_effect=installed) as resolve:
                self.project.compile(output=output, timeout_seconds=29)
            self.assertEqual([call.kwargs for call in resolve.call_args_list], [
                {"role": "core", "operation": "compile-policy-expression-material", "timeout_seconds": 29},
                {"role": "verify", "operation": "export-policy-expression-material", "timeout_seconds": 29},
            ])
            with self.exchange(response_role="core"), self.assertRaises(CoreProtocolError):
                self.project.verify_bundle(output, verify=self.verify)

    def test_changed_metadata_on_both_sides_cannot_reopen_old_bundle(self):
        with tempfile.TemporaryDirectory() as directory, self.exchange():
            output = Path(directory) / "expression.zip"
            self.project.compile(output=output, core=self.core, verify=self.verify)
            for field in ("title", "sources", "assumptions"):
                raw = self.project.request
                if field == "sources":
                    raw["project_context"][field][0]["sha256"] = "0" * 64
                elif field == "assumptions":
                    raw["project_context"][field].append("Another supplied premise")
                else:
                    raw["project_context"][field] = "Changed research project"
                changed = project_api.ResearchProject.from_expression(ExpressionMaterialRequest.from_request(raw))
                with self.subTest(field=field), patch.object(CoreClient, "call", side_effect=AssertionError("Original authority mismatch must precede native transport")), self.assertRaisesRegex(project_api.ResearchProjectError, "authority"):
                    changed.verify_bundle(output, verify=self.verify)

    def test_changed_maximum_rna_length_returns_diagnostics_and_no_output(self):
        request = self.project.request
        next(item for item in request["document"]["program"]["declarations"] if item["id"] == "maximum_rna_nt")["value"] = 1
        changed = project_api.ResearchProject.from_expression(ExpressionMaterialRequest.from_request(request))
        with tempfile.TemporaryDirectory() as directory, self.exchange():
            output = Path(directory) / "expression.zip"
            with self.assertRaises(project_api.ResearchProjectRejected) as caught:
                changed.compile(output=output, core=self.core, verify=self.verify)
            self.assertEqual(caught.exception.status, "not_accepted")
            self.assertEqual(caught.exception.compiled.executable, "core")
            self.assertEqual(caught.exception.report["requirements"][0]["maximum_rna_nt"], 1)
            self.assertEqual(caught.exception.report["requirements"][0]["length_status"], "fail")
            self.assertIsNone(caught.exception.compiled.artifact)
            self.assertFalse(output.exists())
            self.assertFalse(any(role == "verify" for role, _ in self.calls))

    def test_cancellation_after_core_and_verify_failure_preserve_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "expression.zip"
            output.write_bytes(b"owned previous result")
            cancelled = [False]
            def after_compile(operation, _value):
                if operation == "compile-policy-expression-material":
                    cancelled[0] = True
            with self.exchange(on_operation=after_compile), self.assertRaises(CoreCancelled):
                self.project.compile(output=output, core=self.core, verify=self.verify,
                                     replace=True, cancelled=lambda: cancelled[0])
            self.assertEqual(output.read_bytes(), b"owned previous result")
            self.assertFalse(any(role == "verify" for role, _ in self.calls))
            with self.exchange(fail_export=True), self.assertRaises(CoreTransportError):
                self.project.compile(output=output, core=self.core, verify=self.verify, replace=True)
            self.assertEqual(output.read_bytes(), b"owned previous result")
            self.assertFalse(list(Path(directory).glob(".policy-material-*")))

    def test_expression_bundle_cannot_add_temporal_limits_or_replace_source_context(self):
        with tempfile.TemporaryDirectory() as directory, self.exchange():
            source = Path(directory) / "expression.zip"
            self.project.compile(output=source, core=self.core, verify=self.verify)
            with zipfile.ZipFile(source) as archive:
                members = [(entry, archive.read(entry)) for entry in archive.infolist()]
            for mutation in ("limits", "context", "fasta"):
                target = Path(directory) / (mutation + ".zip")
                with zipfile.ZipFile(target, "w") as archive:
                    for entry, content in deepcopy(members):
                        if entry.filename == "manifest.json" and mutation in ("limits", "context"):
                            manifest = json.loads(content)
                            if mutation == "limits":
                                manifest["limits"] = {}
                            else:
                                manifest["request"]["project_context"]["title"] = "Saved foreign authority"
                                manifest["bindings"]["request_fingerprint"] = peer.digest(manifest["request"])
                            content = encode_json(manifest)
                        elif entry.filename == "program.fasta" and mutation == "fasta":
                            content += b"A\n"
                        archive.writestr(entry, content)
                with self.subTest(mutation=mutation), self.assertRaises((project_api.ResearchProjectError, CoreProtocolError)):
                    self.project.verify_bundle(target, verify=self.verify)

    def test_real_reference_starter_keeps_independent_bases_product_parts_and_double_stop(self):
        with patch.object(CoreClient, "call", side_effect=AssertionError("Authoring cannot run native checking")):
            build = car_reference.rm61461_request(maximum_rna_nt=1776,
                three_prime_end="designer_supplied_hydroxyl")
        request = build.to_request()
        authority = request["structure_authority"]
        self.assertEqual(len(authority["template"]["sources"]), 1)
        self.assertEqual(authority["template"]["steps"], [])
        molecule = authority["template"]["sources"][0]["molecule"]
        rna = molecule["sequence"]
        self.assertEqual((len(rna), hashlib.sha256(rna.encode()).hexdigest()),
                         (1776, "7a0e872d51987d1c0064accb5197e605943d90ea2c20104d86e9f41f12617335"))
        protein = authority["members"][0]["product"]["sequence"]
        self.assertEqual((len(protein), hashlib.sha256(protein.encode()).hexdigest()),
                         (485, "833bd17e675e9595d01865a0109c9c795d2ba8b78481ab06f12da043019e404d"))
        intervals = {feature["id"]: [(span["start"], span["end"]) for span in feature["path"]["spans"]]
                     for feature in molecule["features"]}
        self.assertEqual(intervals, {"utr5": [(0, 79)], "cds": [(79, 1540)],
                                     "utr3": [(1540, 1666)], "poly_a": [(1666, 1776)]})
        self.assertEqual(request["expression_contract"]["body"]["translation"]["terminal_stop_codons"], 2)
        self.assertEqual(molecule["chemistry"]["terminal_tail"]["length"]["exact"], 110)
        self.assertEqual(rna[1666:], "A" * 110)
        self.assertEqual(len(rna) - len(rna.rstrip("A")), 111)
        records = car_reference.reference_data()["source_records"]
        for identity, start, end in ((11, 0, 79), (101, 79, 1534), (65, 79, 1540), (34, 1540, 1666)):
            self.assertEqual(rna[start:end], records[str(identity)]["rna_sequence"])

    def test_real_reference_chemistry_keeps_source_and_explicit_designer_authorities_distinct(self):
        request = car_reference.rm61461_request(maximum_rna_nt=1776,
            three_prime_end="designer_supplied_hydroxyl").to_request()
        molecule = request["structure_authority"]["template"]["sources"][0]["molecule"]
        chemistry = molecule["chemistry"]
        self.assertEqual(molecule["sequence"][:2], "AG")
        self.assertEqual(chemistry["cap"]["identity"]["accession"], "m7G_5prime_ppp_5prime_2primeOMeA_pG")
        self.assertEqual(chemistry["cap"]["provenance"]["authority"][0]["content_fingerprint"],
                         "e95bc99f5cc4f9c69d4ca4a40590fb437b17980b93f5a2f7a18e794ca5b9b2da")
        modifications = {item["id"]: item for item in chemistry["modifications"]}
        self.assertEqual(set(modifications), {"all_uridines", "cap_adjacent_adenosine"})
        uridines = modifications["all_uridines"]
        first = modifications["cap_adjacent_adenosine"]
        self.assertEqual((uridines["canonical_base"], uridines["scope"], uridines["positions"], uridines["identity"]["accession"]),
                         ("U", "all_matching_bases", [], "n1_methylpseudouridine"))
        self.assertEqual((first["canonical_base"], first["scope"], first["positions"], first["identity"]["accession"]),
                         ("A", "positions", [0], "2prime_O_methyladenosine"))
        self.assertEqual(first["provenance"], uridines["provenance"])
        finish = chemistry["finish_end"]
        self.assertEqual(finish["identity"]["accession"], "3prime_hydroxyl")
        terminal = next(item for item in request["document"]["program"]["semantics"]["definitions"]
                        if item["id"] == "car.rm61461.terminal_design")
        self.assertEqual(finish["provenance"]["authority"][0]["content_fingerprint"], peer.digest(terminal))
        self.assertNotEqual(finish["provenance"]["authority"], chemistry["cap"]["provenance"]["authority"])
        self.assertIn("designer-supplied", finish["provenance"]["reason"])
        self.assertIsNone(car_reference.reference_data()["nominal_chemistry"]["three_prime_end"]["identity"])
        class PretendChoice:
            def __eq__(self, other):
                return True
        for invalid in (None, True, "source_verified_hydroxyl", PretendChoice()):
            with self.subTest(choice=invalid), self.assertRaises(ValueError):
                car_reference.rm61461_request(maximum_rna_nt=1776, three_prime_end=invalid)
        with self.assertRaises(TypeError):
            car_reference.rm61461_request(maximum_rna_nt=1776)

    def test_real_bound_edit_changes_source_identity_without_rewriting_material_or_adding_runtime(self):
        first = car_reference.rm61461_request(maximum_rna_nt=1776,
            three_prime_end="designer_supplied_hydroxyl").to_request()
        lower = car_reference.rm61461_request(maximum_rna_nt=1775,
            three_prime_end="designer_supplied_hydroxyl").to_request()
        self.assertEqual(first["structure_authority"], lower["structure_authority"])
        self.assertEqual(first["expression_contract"], lower["expression_contract"])
        self.assertEqual(first["project_context"], lower["project_context"])
        self.assertNotEqual(peer.digest(first), peer.digest(lower))
        for request, bound in ((first, 1776), (lower, 1775)):
            declarations = request["document"]["program"]["declarations"]
            self.assertEqual([item["$type"] for item in declarations],
                             ["Role", "Parameter", "Parameter", "Parameter", "Parameter", "Parameter", "Requirement"])
            self.assertEqual(next(item for item in declarations if item["id"] == "maximum_rna_nt")["value"], bound)
            self.assertIsNone(declarations[-1]["trigger"])
            self.assertIsNone(declarations[-1]["condition"])
            self.assertIsNone(declarations[-1]["response"])
            self.assertEqual(request["document"]["assurance"]["horizon"], "not_applicable")

    def test_real_project_pins_complete_context_and_source_budget_fits_known_pdf_without_loading_it(self):
        build = car_reference.rm61461_request(maximum_rna_nt=1776,
            three_prime_end="designer_supplied_hydroxyl")
        project = project_api.ResearchProject.from_expression(build)
        request = build.to_request()
        self.assertEqual({key: project.data[key] for key in ("project_id", "title", "sources", "assumptions")},
                         request["project_context"])
        sources = {row["id"]: row for row in project.data["sources"]}
        self.assertEqual(set(sources), {"car.rm61461.reference_pack", "WO2025096878.sequence-listing",
                                        "WO2025096878A9", "car.rm61461.terminal_design"})
        self.assertEqual(sources["car.rm61461.reference_pack"]["sha256"],
                         "dcf0b3fe174ee48f68623785663b16ce96ce87ad2bbacbd851369e9ba1b46079")
        self.assertEqual(sources["WO2025096878.sequence-listing"]["sha256"],
                         "7df4fd171f285adc6e5d0b37442a8bc77ab1b28c275b04a52c822ed15e7b938e")
        factual = car_reference.reference_data()
        self.assertEqual(factual["sources"]["pdf"]["bytes"], 17_210_052)
        self.assertLessEqual(17_210_052, project_sources.MAX_SOURCE_BYTES)
        self.assertLessEqual(17_210_052 + 669_450 + 131_072 + 4096,
                             project_sources.MAX_TOTAL_SOURCE_BYTES)
        self.assertEqual(factual["applicability"]["human_in_vivo_delivery"], "unassessed")
        self.assertEqual(factual["access_and_reuse"]["patent_permission"], "not_assessed")


if __name__ == "__main__":
    unittest.main()
