"""Pure installed receipt controls; synthetic records never establish native proof."""
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from tools import check_researcher_alpha_installed as installed
from tests.test_researcher_alpha_witness import inert_result

IDENTITY = {"revision": "a" * 40, "head_revision": "b" * 40, "run_id": "1234", "run_attempt": "3"}
BINARIES = {"biocompiler-core": "c" * 64, "biocompiler-verify": "d" * 64}
SOURCES = {"inert-source-only": {"sha256": "e" * 64}}


def write_pair(path, exported):
    from biocompiler.core_client import encode_json
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name, raw in (("program.fasta", exported["artifact"]["fasta"].encode()),
                          ("manifest.json", encode_json(exported["artifact"]["manifest"]))):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)); info.create_system = 3; info.external_attr = 0o100644 << 16
            archive.writestr(info, raw)
    path.write_bytes(buffer.getvalue())


class ResearcherInstalledTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.expected = installed.ROOT / installed.EXPECTED
        self.packet = installed.checked_inputs()
        self.addCleanup(patch.stopall)
        patch("subprocess.Popen", side_effect=AssertionError("No processes in pure installed tests")).start()
        patch("subprocess.run", side_effect=AssertionError("No processes in pure installed tests")).start()

    def receipt(self):
        # Explicitly incomplete metadata peers; check_observations rejects these
        # unless mocked for testing only the independent packaging/receipt layer.
        values = {name: {"synthetic_metadata_only": True} for name in installed.researcher.OBSERVATIONS}
        folder = self.root / installed.FOLDER; folder.mkdir()
        projects, publications = {}, []
        authored_case = {**self.packet["expected"]["cases"][0], "id": "authored",
                         "originals_sha256": installed.canonical_digest(installed.researcher.authored_original(self.packet))}
        for case in [*self.packet["expected"]["cases"], authored_case]:
            identity = case["id"]
            project = (installed.researcher.expected_authored_project(self.packet) if identity == "authored"
                       else installed.expected_project(case, self.packet))
            path = folder / (identity + "-project.json"); path.write_text(json.dumps(project))
            project_digest = installed.canonical_digest(project)
            projects[identity] = {"path": path.name, "sha256": installed.pin(path)["sha256"],
                "project_sha256": project_digest, "originals_sha256": case["originals_sha256"]}
            values[identity + "-preflight"] = {"project_sha256": project_digest}
            changed_originals = deepcopy(project)
            changed_originals["request"]["implementation_request"]["document"]["program"]["source_map"][0]["file"] += ".changed"
            values[identity + "-changed-originals"] = {"changed_project_sha256": installed.canonical_digest(changed_originals)}
            original = installed.researcher.authored_original(self.packet) if identity == "authored" else self.packet["inputs"][identity]
            exported = inert_result(case, original, exported=True)
            values[identity + "-export-verify"] = exported
            path = folder / (identity + ".zip"); write_pair(path, exported)
            publication = {**installed.archive_receipt(exported, path), "path": path.name}
            publications.append(publication); values[identity + "-paired-publication"] = publication
            for kind in (() if identity == "authored" else ("candidate", "fasta")):
                changed = folder / (identity + "-changed-" + kind + ".zip")
                installed.researcher.changed_bundle(path, changed, kind)
                values[identity + "-changed-" + kind] = {"bundle_sha256": installed.pin(changed)["sha256"]}
        rows = []
        for name, value in values.items():
            path = folder / (name + ".json"); path.write_text(json.dumps(value))
            rows.append({"name": name, "path": str(path.relative_to(self.root)), **installed.pin(path)})
        modules = installed.component.installed_source_modules(installed.ROOT)
        package = "/hosted/env/site-packages/biocompiler"
        required = installed.component.REQUIRED_MODULES | {"biocompiler.core_distribution", "biocompiler.core_policy_component_selection",
            "biocompiler.policy.component_selection", "biocompiler.policy.research_project", "biocompiler.policy.component_inputs"}
        origins = {}
        for name in required:
            relative = name.removeprefix("biocompiler").lstrip(".").replace(".", "/")
            options = (relative + ".py", relative + "/__init__.py") if relative else ("__init__.py",)
            origins[name] = str(Path(package) / next(name for name in options if name in modules))
        originals = installed.input_pins(); cwd = "/hosted/session/cwd"
        receipt = {"schema_version": installed.SCHEMA, "status": "pass", **IDENTITY,
            "system": "Linux", "machine": "x86_64", "python_version": "3.11.15", "scope": installed.SCOPE,
            "inputs": originals, "binary_sha256": BINARIES, "package": package, "installed_modules": modules,
            "parent_imports": origins, "source_snapshot_sha256": installed.canonical_digest(SOURCES),
            "working_directory": cwd, "resolution": "owned_installed_defaults",
            "runtime_inputs": {name: {"path": str(Path(cwd) / "researcher-inputs" / name), **originals[name]} for name in installed.COPY_INPUTS},
            "observations": rows, "observations_fingerprint": installed.canonical_digest([{"name": name, "result": result} for name, result in values.items()]),
            "projects": projects, "publications": publications,
            "files": {str(path.relative_to(self.root)): installed.pin(path) for path in folder.iterdir()},
            "python_semantic_authority": "forbidden", "empirical": "unassessed", "real_researcher_project_qualified": False}
        self.assertEqual(len(receipt["files"]), 40)
        return receipt, values

    def validate(self, receipt):
        return installed.validate_installed(receipt, self.root, self.expected, IDENTITY, BINARIES, expected_sources=SOURCES,
                                            expected_slot=("Linux", "x86_64", "3.11"))

    def test_hosted_gate_and_complete_input_packet_precede_execution(self):
        with patch.dict(installed.os.environ, {}, clear=True), self.assertRaisesRegex(AssertionError, "hosted-only"):
            installed.run(SimpleNamespace())
        self.assertEqual(len(installed.input_pins()), 10)
        self.assertEqual(len(installed.COPY_INPUTS), 8)
        with self.assertRaisesRegex(AssertionError, "exact independent"):
            installed.checked_inputs(installed.ROOT, self.root / "foreign.json")

    def test_complete_sidecars_projects_pairs_and_native_check_are_mandatory(self):
        receipt, values = self.receipt()
        with patch.object(installed.researcher, "check_observations", return_value=values) as checked:
            self.assertEqual(self.validate(receipt), values)
            checked.assert_called_once_with(values, self.packet)
        with self.assertRaises((AssertionError, KeyError)):
            self.validate(receipt)
        with patch.object(installed.researcher, "check_observations", side_effect=AssertionError("mandatory independent native result validation")):
            with self.assertRaisesRegex(AssertionError, "mandatory"):
                self.validate(receipt)

    def test_rehashed_identity_origin_census_and_scope_mutations_fail(self):
        receipt, values = self.receipt()
        mutations = [lambda r: r.update(run_id="foreign"), lambda r: r.update(run_attempt="4"),
            lambda r: r.update(resolution="explicit_test_double"), lambda r: r.update(empirical="validated"),
            lambda r: r.update(real_researcher_project_qualified=True), lambda r: r.update(python_version="3.12.1"),
            lambda r: r.update(working_directory=str(installed.ROOT)),
            lambda r: r.update(package=str(installed.ROOT / "src/biocompiler")),
            lambda r: r["runtime_inputs"][installed.EXAMPLE].update(path=str(installed.ROOT / installed.EXAMPLE)),
            lambda r: r["inputs"][installed.EXAMPLE].update(sha256="0" * 64),
            lambda r: r["binary_sha256"].update({"biocompiler-core": "0" * 64}),
            lambda r: r["installed_modules"].pop("policy/research_project.py"),
            lambda r: r["parent_imports"].pop("biocompiler.policy.research_project"),
            lambda r: r["parent_imports"].pop("biocompiler.policy.component_inputs"),
            lambda r: r["parent_imports"].update({"biocompiler.core_client": "/foreign/core_client.py"}),
            lambda r: r["parent_imports"].update({"biocompiler.behavior_runtime": "/foreign/behavior_runtime.py"}),
            lambda r: r["observations"].pop(), lambda r: r["observations"].reverse(),
            lambda r: r["observations"][0].update(path="../foreign.json"),
            lambda r: r["projects"]["staged"].update(path="../project.json"),
            lambda r: r["projects"].pop("authored"),
            lambda r: r["publications"].clear(), lambda r: r["files"].pop(next(iter(r["files"])))]
        with patch.object(installed.researcher, "check_observations", return_value=values):
            for index, mutate in enumerate(mutations):
                changed = deepcopy(receipt); mutate(changed)
                with self.subTest(index=index), self.assertRaises(AssertionError):
                    self.validate(changed)
            extra = self.root / installed.FOLDER / "unexpected.json"; extra.write_text("{}")
            with self.assertRaisesRegex(AssertionError, "extra"):
                self.validate(receipt)

    def test_self_consistent_project_or_pair_rehash_cannot_change_external_authority(self):
        receipt, values = self.receipt()
        with patch.object(installed.researcher, "check_observations", return_value=values):
            path = self.root / installed.FOLDER / "staged-project.json"
            original = path.read_bytes(); changed = json.loads(original); changed["title"] += " changed"
            path.write_text(json.dumps(changed)); receipt["projects"]["staged"]["sha256"] = installed.pin(path)["sha256"]
            with self.assertRaisesRegex(AssertionError, "independent originals"):
                self.validate(receipt)
            path.write_bytes(original); receipt["projects"]["staged"]["sha256"] = installed.pin(path)["sha256"]
            path = self.root / installed.FOLDER / "staged.zip"; path.write_bytes(b"self-consistent but wrong archive")
            receipt["files"][installed.FOLDER + "/staged.zip"] = installed.pin(path)
            with self.assertRaisesRegex(AssertionError, "publication|archive"):
                self.validate(receipt)

    def test_self_rehashed_authored_source_map_cannot_replace_independent_source_authority(self):
        receipt, values = self.receipt()
        path = self.root / installed.FOLDER / "authored-project.json"
        project = json.loads(path.read_bytes())
        document = project["request"]["implementation_request"]["document"]
        document["program"]["source_map"][0]["line"] += 1
        digest = installed.canonical_digest(document)
        project["sources"][-1].update(sha256=digest, locator="urn:biocompiler:canonical-policy:" + digest)
        path.write_text(json.dumps(project))
        project_digest = installed.canonical_digest(project)
        receipt["projects"]["authored"].update(sha256=installed.pin(path)["sha256"], project_sha256=project_digest,
            originals_sha256=installed.canonical_digest({key: project[key] for key in ("request", "limits")}))
        values["authored-preflight"]["project_sha256"] = project_digest
        sidecar = self.root / installed.FOLDER / "authored-preflight.json"
        sidecar.write_text(json.dumps(values["authored-preflight"]))
        next(row for row in receipt["observations"] if row["name"] == "authored-preflight").update(installed.pin(sidecar))
        receipt["observations_fingerprint"] = installed.canonical_digest([{"name": key, "result": value} for key, value in values.items()])
        receipt["files"].update({str(file.relative_to(self.root)): installed.pin(file) for file in (path, sidecar)})
        with patch.object(installed.researcher, "check_observations", return_value=values), self.assertRaisesRegex(AssertionError, "independent originals"):
            self.validate(receipt)

    def test_mutation_archive_must_be_the_declared_single_change(self):
        receipt, values = self.receipt()
        name = "staged-changed-candidate"
        path = self.root / installed.FOLDER / (name + ".zip")
        wrong = inert_result(self.packet["expected"]["cases"][0], self.packet["inputs"]["staged"], exported=True)
        wrong["artifact"]["manifest"]["unexpected"] = True
        write_pair(path, wrong)
        values[name]["bundle_sha256"] = installed.pin(path)["sha256"]
        sidecar = self.root / installed.FOLDER / (name + ".json"); sidecar.write_text(json.dumps(values[name]))
        next(row for row in receipt["observations"] if row["name"] == name).update(installed.pin(sidecar))
        receipt["observations_fingerprint"] = installed.canonical_digest([{"name": key, "result": value} for key, value in values.items()])
        receipt["files"].update({str(file.relative_to(self.root)): installed.pin(file) for file in (path, sidecar)})
        from biocompiler.core_client import CoreProtocolError
        with patch.object(installed.researcher, "check_observations", return_value=values), self.assertRaises(CoreProtocolError):
            self.validate(receipt)

    def test_independent_mutation_reconstruction_rejects_stale_or_substituted_role_pins(self):
        from biocompiler.core_client import CoreProtocolError
        for case in self.packet["expected"]["cases"]:
            exported = inert_result(case, self.packet["inputs"][case["id"]], exported=True)
            source, target = self.root / (case["id"] + ".zip"), self.root / (case["id"] + "-changed.zip")
            write_pair(source, exported)
            installed.researcher.changed_bundle(source, target, "candidate")
            # The comparator must reconstruct independently of the producing recipe.
            with patch.object(installed.researcher, "changed_material_candidate", side_effect=AssertionError("Producer must not authorize comparison")):
                installed.check_mutant(target, exported, "candidate")
                for kind in ("stale", "substituted", "unrelated"):
                    changed = deepcopy(exported)
                    inventory = changed["artifact"]["manifest"]["candidate"]["construction"]["inventory"]
                    molecule = inventory["molecules"][0]
                    molecule["sequence"] = "G" + molecule["sequence"][1:]
                    if kind != "stale":
                        inventory["role_instances"][0]["subject_fingerprint"] = ("0" * 64 if kind == "substituted"
                            else installed.canonical_digest(molecule))
                    if kind == "unrelated":
                        changed["artifact"]["manifest"]["limits"]["max_output_bytes"] = 1
                    write_pair(target, changed)
                    with self.subTest(kind=kind), self.assertRaises(CoreProtocolError):
                        installed.check_mutant(target, exported, "candidate")

    def test_four_distinct_slots_use_full_results_and_exact_platform_authorities(self):
        paths = []
        for index, slot in enumerate(sorted(installed.component.SLOTS)):
            path = self.root / str(index) / installed.RECEIPT; path.parent.mkdir()
            path.write_text(json.dumps({"system": slot[0], "machine": slot[1], "python_version": slot[2] + ".6", "run_attempt": "2"}))
            paths.append(path)
        authorities = {platform: dict(BINARIES) for platform in (("Linux", "x86_64"), ("Darwin", "arm64"))}
        with patch.object(installed, "validate_installed", return_value={"all30": "complete identical observations"}) as checked:
            result = installed.compare_installed(paths, self.expected, IDENTITY, authorities, expected_sources=SOURCES)
            self.assertEqual(result["status"], "pass"); self.assertEqual(checked.call_count, 4)
            self.assertFalse(result["real_researcher_project_qualified"])
            self.assertEqual([row["run_attempt"] for row in result["attempts"]], ["2"] * 4)
            for call in checked.call_args_list:
                self.assertIs(call.args[4], authorities[(call.args[0]["system"], call.args[0]["machine"])])
                self.assertEqual(call.kwargs["expected_sources"], SOURCES)
            with self.assertRaisesRegex(AssertionError, "four slots"):
                installed.compare_installed(paths[:3], self.expected, IDENTITY, authorities, expected_sources=SOURCES)
            with self.assertRaisesRegex(AssertionError, "Duplicate"):
                installed.compare_installed(paths[:3] + paths[:1], self.expected, IDENTITY, authorities, expected_sources=SOURCES)
        with patch.object(installed, "validate_installed", side_effect=[{"full": 1}, {"full": 2}]), self.assertRaisesRegex(AssertionError, "differ"):
            installed.compare_installed(paths, self.expected, IDENTITY, authorities, expected_sources=SOURCES)
        with patch.object(installed, "validate_installed", side_effect=AssertionError("mandatory slot check")), self.assertRaisesRegex(AssertionError, "mandatory"):
            installed.compare_installed(paths, self.expected, IDENTITY, authorities, expected_sources=SOURCES)


if __name__ == "__main__":
    unittest.main()
