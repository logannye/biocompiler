"""Inert installed CAR receipt controls; synthetic records cannot grant acceptance."""
import base64
from copy import deepcopy
import csv
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from tools import check_car_payload_installed as installed

IDENTITY = {"revision": "a" * 40, "head_revision": "b" * 40, "run_id": "1234", "run_attempt": "3"}
BINARIES = {"biocompiler-core": "c" * 64, "biocompiler-verify": "d" * 64}
SOURCES = {"inert-source-only": {"sha256": "e" * 64}}


def rehearsal():
    """Synthetic timing metadata only; never an actual timed native rehearsal."""
    return {**installed.REHEARSAL_SCOPE, "manual_interventions": [],
        "milestones": [{"name": name, "elapsed_ns": index + 1}
                       for index, name in enumerate(installed.REHEARSAL_MILESTONES)],
        "total_elapsed_ns": 4}


def record_for(package, modules, data):
    path = Path(package).parent / "biocompiler-0.0.0.dist-info/RECORD"
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    for name, value in sorted({**modules, **data}.items()):
        digest = base64.urlsafe_b64encode(bytes.fromhex(value["sha256"])).rstrip(b"=").decode()
        writer.writerow(["biocompiler/" + name, "sha256=" + digest, str(value["bytes"])])
    writer.writerow([path.relative_to(Path(package).parent).as_posix(), "", ""])
    text = stream.getvalue()
    return {"path": str(path), "text": text, **installed._raw_pin(text.encode())}


def write_pair(path, exported):
    from biocompiler.core_client import encode_json
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        for name, raw in (("program.fasta", exported["artifact"]["fasta"].encode()),
                          ("manifest.json", encode_json(exported["artifact"]["manifest"]))):
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, raw)


class CarPayloadInstalledTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.expected = installed.ROOT / installed.EXPECTED
        self.packet = installed.checked_inputs()
        for target in ("subprocess.Popen", "subprocess.run", "socket.socket"):
            guard = patch(target, side_effect=AssertionError("No processes or network in pure installed controls"))
            guard.start()
            self.addCleanup(guard.stop)

    def receipt(self):
        # These peers deliberately lack native evidence. Only metadata-layer
        # tests may mock the mandatory semantic and actual-artifact validators.
        folder = self.root / installed.FOLDER
        folder.mkdir()
        values = {name: {"synthetic_metadata_only": True} for name in installed.car.OBSERVATIONS}
        values["native-actions"] = {"resolution": "owned_installed_defaults", "synthetic_metadata_only": True}
        rows = []
        for name in installed.car.EVIDENCE_FILES:
            path = folder / name
            value = values[name.removesuffix(".json")] if name.removesuffix(".json") in values else {"synthetic_artifact_only": True}
            path.write_text(json.dumps(value))
        for name, value in values.items():
            path = folder / (name + ".json")
            rows.append({"name": name, "path": str(path.relative_to(self.root)), **installed.pin(path)})
        modules, data = installed.component.installed_source_modules(installed.ROOT), installed.source_data()
        package = "/hosted/env/site-packages/biocompiler"
        origins = {}
        for name in installed.REQUIRED_MODULES:
            relative = name.removeprefix("biocompiler").lstrip(".").replace(".", "/")
            options = (relative + ".py", relative + "/__init__.py") if relative else ("__init__.py",)
            origins[name] = str(Path(package) / next(name for name in options if name in modules))
        originals, cwd = installed.input_pins(), "/hosted/session/cwd"
        return {"schema_version": installed.SCHEMA, "status": "pass", **IDENTITY,
            "system": "Linux", "machine": "x86_64", "python_version": "3.11.15", "scope": installed.SCOPE,
            "inputs": originals, "binary_sha256": BINARIES.copy(), "package": package, "installed_modules": modules,
            "installed_data": data, "sdk_record": record_for(package, modules, data), "parent_imports": origins,
            "source_snapshot_sha256": installed.canonical_digest(SOURCES), "working_directory": cwd,
            "resolution": "owned_installed_defaults", "runtime_inputs": {name: {"path": str(Path(cwd) / "car-inputs" / name), **originals[name]} for name in installed.COPY_INPUTS},
            "observations": rows, "observations_fingerprint": installed.canonical_digest([{"name": name, "result": value} for name, value in values.items()]),
            "projects": {}, "publications": [], "native_actions": {key: rows[-1][key] for key in ("path", "sha256", "bytes")},
            "files": {str(path.relative_to(self.root)): installed.pin(path) for path in folder.iterdir()},
            "python_semantic_authority": "forbidden", "empirical": "unassessed", "human_use": "unassessed", "real_researcher_project_qualified": False,
            "rehearsal": rehearsal()}, values

    def validate(self, receipt):
        return installed.validate_installed(receipt, self.root, self.expected, IDENTITY, BINARIES,
            expected_sources=SOURCES, expected_slot=("Linux", "x86_64", "3.11"))

    def artifact_peers(self):
        """Actual files with inert literal peers, deliberately not native CAR proof."""
        from biocompiler.core_client import encode_json
        from tests.test_car_payload_campaign import mock_result
        receipt, values = self.receipt()
        folder = self.root / installed.FOLDER
        for case in installed.car.CASE_IDS:
            original = installed.car.expected_project(self.packet, case)
            path = folder / (case + "-project.json")
            path.write_bytes(encode_json(original))
            receipt["projects"][case] = {"path": path.name, "sha256": installed.pin(path)["sha256"],
                "project_sha256": installed.canonical_digest(original),
                "request_sha256": installed.canonical_digest(original["request"])}
        for case, export_name, publication_name in (("base", "export-verify", "paired-publication"),
                                                   ("tight", "tight-export-verify", "tight-paired-publication")):
            exported = mock_result({"request": installed.car.request_for(self.packet, case)},
                "export-policy-expression-material")
            values[export_name] = exported
            path = folder / (case + ".zip")
            write_pair(path, exported)
            publication = {**installed.car.archive_receipt(exported, path), "path": path.name}
            values[publication_name] = publication
            receipt["publications"].append(publication)
        for kind in ("candidate", "fasta"):
            path = folder / ("base-changed-" + kind + ".zip")
            path.unlink()
            installed.car.write_mutant(path, values["export-verify"], kind)
            values["changed-" + kind] = {"bundle_sha256": installed.pin(path)["sha256"]}
        self.repin(receipt, values)
        return receipt, values

    def repin(self, receipt, values):
        from biocompiler.core_client import encode_json
        folder = self.root / installed.FOLDER
        for row in receipt["observations"]:
            path = self.root / row["path"]
            path.write_bytes(encode_json(values[row["name"]]))
            row.update(installed.pin(path))
        receipt["observations_fingerprint"] = installed.canonical_digest([{"name": name, "result": value} for name, value in values.items()])
        receipt["files"] = {str(path.relative_to(self.root)): installed.pin(path) for path in folder.iterdir()}
        receipt["native_actions"] = {key: receipt["observations"][-1][key] for key in ("path", "sha256", "bytes")}

    def test_hosted_gate_original_oracle_and_data_copy_precede_execution(self):
        with patch.dict(installed.os.environ, {}, clear=True), self.assertRaisesRegex(AssertionError, "hosted-only"):
            installed.run(SimpleNamespace())
        self.assertEqual(installed.COPY_INPUTS, installed.car.COPY_INPUTS)
        self.assertIn(installed.REFERENCE, installed.COPY_INPUTS)
        self.assertEqual(len(installed.car.OBSERVATIONS), 22)
        self.assertEqual(len(installed.car.EVIDENCE_FILES), 29)
        with self.assertRaisesRegex(AssertionError, "exact CAR oracle"):
            installed.checked_inputs(installed.ROOT, self.root / "foreign.json")

    def test_rehearsal_clock_records_only_ordered_public_workflow_milestones(self):
        with patch.object(installed.time, "monotonic_ns", side_effect=[100, 150, 160, 200, 250]) as clock:
            timer = installed._RehearsalTimer()
            for name in installed.car.OBSERVATIONS:
                timer.observe(name)
            measured = timer.finish()
        self.assertEqual(clock.call_count, 5)
        self.assertEqual(measured["milestones"], [
            {"name": "paired-publication", "elapsed_ns": 50},
            {"name": "tight-paired-publication", "elapsed_ns": 60},
            {"name": "short-no-publication", "elapsed_ns": 100}])
        self.assertEqual(measured["total_elapsed_ns"], 150)
        self.assertEqual(measured["installation_timing"], "excluded")
        self.assertEqual(measured["human_usability"], "unassessed")
        self.assertEqual(measured["external_researcher_review"], "not_performed")
        self.assertEqual(measured["manual_interventions"], [])
        measured["milestones"][0]["elapsed_ns"] = 0
        self.assertEqual(timer.milestones[0]["elapsed_ns"], 50)

    def test_rehearsal_timer_rejects_missing_duplicate_reordered_and_backward_events(self):
        with patch.object(installed.time, "monotonic_ns", return_value=100):
            timer = installed._RehearsalTimer()
            with self.assertRaisesRegex(AssertionError, "milestones"):
                timer.finish()
            with self.assertRaisesRegex(AssertionError, "reordered"):
                timer.observe("tight-paired-publication")
            timer.observe("paired-publication")
            with self.assertRaisesRegex(AssertionError, "duplicated"):
                timer.observe("paired-publication")
        with patch.object(installed.time, "monotonic_ns", side_effect=[100, 110, 109, 120, 130]):
            timer = installed._RehearsalTimer()
            for name in installed.REHEARSAL_MILESTONES:
                timer.observe(name)
            with self.assertRaisesRegex(AssertionError, "nonmonotonic"):
                timer.finish()

    def test_rehearsal_scope_complete_census_and_integer_timings_are_required(self):
        receipt, values = self.receipt()
        mutations = [lambda r: r.pop("rehearsal"), lambda r: r.update(rehearsal=None),
            lambda r: r["rehearsal"].update(unexpected=True),
            lambda r: r["rehearsal"].pop("total_elapsed_ns"),
            lambda r: r["rehearsal"]["milestones"].pop(),
            lambda r: r["rehearsal"]["milestones"].reverse(),
            lambda r: r["rehearsal"]["milestones"].append(deepcopy(r["rehearsal"]["milestones"][0])),
            lambda r: r["rehearsal"]["milestones"][0].update(unexpected=True),
            lambda r: r["rehearsal"]["milestones"][1].update(elapsed_ns=0),
            lambda r: r["rehearsal"].update(total_elapsed_ns=2),
            lambda r: r["rehearsal"].update(manual_interventions=["undocumented manual repair"]),
            lambda r: r["rehearsal"].update(manual_interventions=())]
        for key in installed.REHEARSAL_SCOPE:
            mutations.append(lambda r, key=key: r["rehearsal"].update({key: "promoted_or_foreign"}))
        for value in (-1, True, 1.0, "1", None, 2**63):
            mutations.append(lambda r, value=value: r["rehearsal"].update(total_elapsed_ns=value))
            mutations.append(lambda r, value=value: r["rehearsal"]["milestones"][0].update(elapsed_ns=value))
        with patch.object(installed.car, "check_observations", return_value=values), patch.object(installed.car, "validate_files"):
            self.assertEqual(self.validate(receipt), values)
            for index, mutate in enumerate(mutations):
                changed = deepcopy(receipt)
                mutate(changed)
                with self.subTest(index=index), self.assertRaises(AssertionError):
                    self.validate(changed)
            zero = deepcopy(receipt)
            for row in zero["rehearsal"]["milestones"]:
                row["elapsed_ns"] = 0
            zero["rehearsal"]["total_elapsed_ns"] = 0
            self.assertEqual(self.validate(zero), values)
            # Runtime timings are not an independent source of semantic PASS.
        with self.assertRaises((AssertionError, KeyError)):
            self.validate(receipt)

    def test_metadata_controls_cannot_bypass_native_envelopes_or_actual_file_validation(self):
        receipt, values = self.receipt()
        with patch.object(installed.car, "check_observations", return_value=values) as semantic, \
                patch.object(installed.car, "validate_files") as files:
            self.assertEqual(self.validate(receipt), values)
            semantic.assert_called_once_with(values, self.packet)
            files.assert_called_once_with(values, self.packet, self.root / installed.FOLDER,
                projects={}, publications=[], native_actions=values["native-actions"])
        with self.assertRaises((AssertionError, KeyError)):
            self.validate(receipt)
        with patch.object(installed.car, "check_observations", return_value=values), \
                self.assertRaises((AssertionError, KeyError)):
            self.validate(receipt)
        with patch.object(installed.car, "check_observations", side_effect=AssertionError("mandatory native evidence")), \
                self.assertRaisesRegex(AssertionError, "mandatory native"):
            self.validate(receipt)

    def test_complete_inert_public_campaign_joins_every_original_file_and_native_action(self):
        from biocompiler.core_client import CoreProtocolError
        from tests.test_car_payload_campaign import make_evidence
        receipt, _ = self.receipt()
        self.root = self.root / "full-inert-campaign"
        self.root.mkdir()
        packet, values, fields = make_evidence(self.root / installed.FOLDER, installed=True)
        self.assertEqual(packet, self.packet)
        receipt.update(projects=fields["projects"], publications=fields["publications"])
        self.repin(receipt, values)
        # Real Python transport and byte validators run; _exchange alone supplied
        # the conspicuously inert test responses. No native acceptance is claimed.
        self.assertEqual(self.validate(receipt), values)
        self.assertEqual(len(values["native-actions"]["actions"]), 31)
        self.assertLess(len(json.dumps(receipt, sort_keys=True, indent=2).encode()), installed.component.MAX_RECEIPT)
        altered = deepcopy(values)
        altered["compile-core"]["report"]["human_use"] = "accepted"
        altered["compile-core"]["report_fingerprint"] = installed.canonical_digest(altered["compile-core"]["report"])
        self.repin(receipt, altered)
        with self.assertRaises((AssertionError, CoreProtocolError)):
            self.validate(receipt)

    def test_original_source_attempt_binary_scope_and_origin_mutants_fail(self):
        receipt, values = self.receipt()
        changes = [lambda r: r.update(revision="0" * 40), lambda r: r.update(head_revision="0" * 40),
            lambda r: r.update(run_id="foreign"), lambda r: r.update(run_attempt="4"), lambda r: r.update(run_attempt="0"),
            lambda r: r.update(run_attempt=1), lambda r: r.update(python_version="3.12.1"),
            lambda r: r.update(scope="clinical_acceptance"), lambda r: r.update(empirical="proven"),
            lambda r: r.update(human_use="accepted"), lambda r: r.update(real_researcher_project_qualified=True),
            lambda r: r.update(python_semantic_authority="permitted"), lambda r: r.update(resolution="explicit_pinned"),
            lambda r: r.update(source_snapshot_sha256="0" * 64), lambda r: r.update(working_directory=str(installed.ROOT)),
            lambda r: r.update(package=str(installed.ROOT / "src/biocompiler")),
            lambda r: r["binary_sha256"].update({"biocompiler-verify": "0" * 64}),
            lambda r: r["inputs"][installed.REFERENCE].update(sha256="0" * 64),
            lambda r: r["runtime_inputs"][installed.EXAMPLE].update(path=str(installed.ROOT / installed.EXAMPLE)),
            lambda r: r["installed_modules"].pop("policy/car_reference.py"),
            lambda r: r["installed_data"]["policy/data/car_rm61461_reference_v01.json"].update(sha256="0" * 64),
            lambda r: r["installed_data"]["py.typed"].update(bytes=False),
            lambda r: r["parent_imports"].pop("biocompiler.policy.car_reference"),
            lambda r: r["parent_imports"].update({"biocompiler.core_client": "/foreign/core_client.py"}),
            lambda r: r["parent_imports"].update({"biocompiler.behavior_runtime": "/foreign/behavior_runtime.py"})]
        with patch.object(installed.car, "check_observations", return_value=values), patch.object(installed.car, "validate_files"):
            for index, change in enumerate(changes):
                bad = deepcopy(receipt)
                change(bad)
                with self.subTest(index=index), self.assertRaises(AssertionError):
                    self.validate(bad)

    def test_full_sidecar_file_census_and_independent_native_log_are_required(self):
        receipt, values = self.receipt()
        changes = [lambda r: r["observations"].pop(), lambda r: r["observations"].reverse(),
            lambda r: r["observations"].append(deepcopy(r["observations"][0])),
            lambda r: r["observations"][0].update(path="../elsewhere.json"),
            lambda r: r["observations"][0].update(sha256="0" * 64),
            lambda r: r["files"].pop(installed.FOLDER + "/base.zip"),
            lambda r: r["files"].update({installed.FOLDER + "/foreign.zip": {"sha256": "f" * 64, "bytes": 1}}),
            lambda r: r["native_actions"].update(sha256="0" * 64)]
        with patch.object(installed.car, "check_observations", return_value=values), patch.object(installed.car, "validate_files"):
            for index, change in enumerate(changes):
                bad = deepcopy(receipt)
                change(bad)
                with self.subTest(index=index), self.assertRaises(AssertionError):
                    self.validate(bad)
            extra = self.root / installed.FOLDER / "extra.json"
            extra.write_text("{}")
            with self.assertRaisesRegex(AssertionError, "extra"):
                self.validate(receipt)

    def test_rehashed_sidecar_cannot_replace_fresh_semantic_comparison(self):
        receipt, values = self.receipt()
        name = "compile-core"
        path = self.root / installed.FOLDER / (name + ".json")
        counterfeit = {"status": "pass", "claimed_accepted": True}
        path.write_text(json.dumps(counterfeit))
        next(row for row in receipt["observations"] if row["name"] == name).update(installed.pin(path))
        receipt["files"][installed.FOLDER + "/" + name + ".json"] = installed.pin(path)
        values[name] = counterfeit
        receipt["observations_fingerprint"] = installed.canonical_digest([{"name": name, "result": value} for name, value in values.items()])
        with self.assertRaises((AssertionError, KeyError)):
            self.validate(receipt)

    def test_record_binds_every_original_python_and_data_row_even_when_rehashed(self):
        receipt, values = self.receipt()
        source = receipt["sdk_record"]
        installed.check_record(source, receipt["package"], receipt["installed_modules"], receipt["installed_data"])
        parsed = list(csv.reader(io.StringIO(source["text"])))
        reference = "biocompiler/policy/data/car_rm61461_reference_v01.json"
        variants = []
        removed = deepcopy(parsed); removed[:] = [row for row in removed if row[0] != reference]; variants.append(removed)
        duplicate = deepcopy(parsed); duplicate.append(deepcopy(duplicate[0])); variants.append(duplicate)
        for column, new in ((1, "sha256=" + "A" * 43), (2, "1"), (0, "biocompiler/policy/data/foreign.json")):
            rows = deepcopy(parsed)
            next(row for row in rows if row[0] == reference)[column] = new
            variants.append(rows)
        for rows in variants:
            stream = io.StringIO(newline=""); csv.writer(stream, lineterminator="\n").writerows(rows)
            bad = deepcopy(receipt)
            raw = stream.getvalue().encode()
            bad["sdk_record"].update(text=raw.decode(), **installed._raw_pin(raw))
            with self.subTest(rows=len(rows)), patch.object(installed.car, "check_observations", return_value=values), \
                    patch.object(installed.car, "validate_files"), self.assertRaises(AssertionError):
                self.validate(bad)
        for path in ("/foreign/RECORD", "/hosted/env/site-packages/other-0.0.dist-info/RECORD"):
            bad = deepcopy(source); bad["path"] = path
            with self.assertRaisesRegex(AssertionError, "Foreign"):
                installed.check_record(bad, receipt["package"], receipt["installed_modules"], receipt["installed_data"])

    def test_rehashed_actual_project_and_zip_cannot_replace_independent_file_authority(self):
        from biocompiler.core_client import encode_json
        receipt, values = self.artifact_peers()
        with patch.object(installed.car, "check_observations", return_value=values):
            # Only native semantics is mocked here; all 29 file comparisons run.
            self.assertEqual(self.validate(receipt), values)
            path = self.root / installed.FOLDER / "base-project.json"
            original = path.read_bytes()
            altered = json.loads(original)
            altered["title"] += " changed"
            altered["request"]["project_context"]["title"] = altered["title"]
            path.write_bytes(encode_json(altered))
            receipt["projects"]["base"].update(sha256=installed.pin(path)["sha256"],
                project_sha256=installed.canonical_digest(altered), request_sha256=installed.canonical_digest(altered["request"]))
            self.repin(receipt, values)
            with self.assertRaisesRegex(AssertionError, "project differs"):
                self.validate(receipt)
            path.write_bytes(original)
            restored = json.loads(original)
            receipt["projects"]["base"].update(sha256=installed.pin(path)["sha256"],
                project_sha256=installed.canonical_digest(restored), request_sha256=installed.canonical_digest(restored["request"]))
            path = self.root / installed.FOLDER / "base.zip"
            changed_export = deepcopy(values["export-verify"])
            changed_export["artifact"]["manifest"]["unexpected"] = "self-consistent counterfeit"
            write_pair(path, changed_export)
            self.repin(receipt, values)
            with self.assertRaisesRegex(AssertionError, "publication|archive"):
                self.validate(receipt)
        with self.assertRaises((AssertionError, KeyError)):
            self.validate(receipt)

    def test_rehashed_actual_mutant_must_be_exactly_the_declared_change(self):
        from biocompiler.core_client import CoreProtocolError
        receipt, values = self.artifact_peers()
        path = self.root / installed.FOLDER / "base-changed-candidate.zip"
        altered = deepcopy(values["export-verify"])
        altered["artifact"]["manifest"]["unexpected"] = True
        write_pair(path, altered)
        values["changed-candidate"]["bundle_sha256"] = installed.pin(path)["sha256"]
        self.repin(receipt, values)
        with patch.object(installed.car, "check_observations", return_value=values), self.assertRaises(CoreProtocolError):
            self.validate(receipt)

    def test_installed_package_data_and_record_are_read_and_revalidated(self):
        source = self.root / "source"
        package = self.root / "environment/biocompiler"
        source_package = source / "src/biocompiler"
        relative = "policy/data/car_rm61461_reference_v01.json"
        for base in (source_package, package):
            (base / relative).parent.mkdir(parents=True)
            (base / relative).write_bytes(b'{"test_only":"source-owned"}')
            (base / "py.typed").write_bytes(b"")
        modules = {"__init__.py": installed._raw_pin(b"# inert\n")}
        with patch.object(installed, "ROOT", source):
            data = installed.source_data(source)
            record = record_for(package, modules, data)
            record_path = Path(record["path"]); record_path.parent.mkdir()
            record_path.write_text(record["text"])
            distribution = SimpleNamespace(metadata={"Name": "biocompiler"}, files=[record_path.relative_to(package.parent)],
                locate_file=lambda entry: package.parent / entry)
            with patch.object(installed.component, "installed_package_modules", return_value=modules), \
                    patch.object(installed.metadata, "distributions", return_value=[distribution]):
                self.assertEqual(installed.installed_package(package), (modules, data, record))
                (package / relative).write_bytes(b'{"test_only":"counterfeit"}')
                with self.assertRaisesRegex(AssertionError, "package data"):
                    installed.installed_package(package)
                (package / relative).write_bytes((source_package / relative).read_bytes())
                record_path.write_text(record["text"].replace("sha256=", "sha512=", 1))
                with self.assertRaisesRegex(AssertionError, "RECORD differs"):
                    installed.installed_package(package)

    def test_four_distinct_slots_bind_actual_attempts_and_complete_results(self):
        paths = []
        for index, slot in enumerate(sorted(installed.component.SLOTS)):
            path = self.root / str(index) / installed.RECEIPT
            path.parent.mkdir()
            measured = rehearsal()
            measured["total_elapsed_ns"] += index
            path.write_text(json.dumps({"system": slot[0], "machine": slot[1], "python_version": slot[2] + ".6", "run_attempt": "2",
                                       "rehearsal": measured}))
            paths.append(path)
        binaries = {platform: BINARIES.copy() for platform in (("Linux", "x86_64"), ("Darwin", "arm64"))}
        with patch.object(installed, "validate_installed", return_value={"all22": "complete inert projection"}) as checked:
            result = installed.compare_installed(paths, self.expected, IDENTITY, binaries, expected_sources=SOURCES)
            self.assertEqual(checked.call_count, 4)
            self.assertEqual([row["run_attempt"] for row in result["attempts"]], ["2"] * 4)
            self.assertEqual(result["human_use"], "unassessed")
            self.assertFalse(result["real_researcher_project_qualified"])
            self.assertNotIn("rehearsal", result)
            self.assertEqual(result["observations_fingerprint"], installed.canonical_digest({"all22": "complete inert projection"}))
            for call in checked.call_args_list:
                self.assertIs(call.args[4], binaries[(call.args[0]["system"], call.args[0]["machine"])])
                self.assertEqual(call.kwargs["expected_sources"], SOURCES)
            with self.assertRaisesRegex(AssertionError, "four slots"):
                installed.compare_installed(paths[:3], self.expected, IDENTITY, binaries, expected_sources=SOURCES)
            with self.assertRaisesRegex(AssertionError, "Duplicate"):
                installed.compare_installed(paths[:3] + paths[:1], self.expected, IDENTITY, binaries, expected_sources=SOURCES)
        for pair in (({"full": 1}, {"full": 2}), ({"full": 1}, {"full": True})):
            with patch.object(installed, "validate_installed", side_effect=pair), self.assertRaisesRegex(AssertionError, "differ"):
                installed.compare_installed(paths, self.expected, IDENTITY, binaries, expected_sources=SOURCES)


if __name__ == "__main__":
    unittest.main()
