"""Inert supplied-authority authoring controls; these tests do not run native code."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from biocompiler import policy as p
from biocompiler.policy.component_inputs import ComponentMaterialInputs
from biocompiler.policy.research_project import ResearchProject, ResearchProjectError, SourceRecord
from biocompiler.core_client import CoreClient, CoreProtocolError, encode_json
from biocompiler.policy import component_inputs as api

ROOT = Path(__file__).resolve().parents[1]


class ComponentInputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet = json.loads((ROOT / "data/researcher_alpha/staged-input.json").read_text())

    def setUp(self):
        self.original = deepcopy(self.packet["request"])
        self.document = p.from_data(self.original["implementation_request"]["document"], p.BuildRequest)
        self.inputs = ComponentMaterialInputs.from_request(self.original)

    def project(self):
        return ResearchProject.from_build_request(project_id="authored.test", title="Authored software test",
            document=self.document, inputs=self.inputs, limits=self.packet["limits"],
            sources=(SourceRecord("input", "urn:test:inputs", "1", self.inputs.digest, "supplied_contracts", "Artificial test"),),
            assumptions=("Supplied contracts are unassessed premises.",))

    def test_extraction_and_preparation_preserve_all_original_authority(self):
        with patch.object(CoreClient, "call", side_effect=AssertionError("No native execution")):
            self.assertEqual(self.inputs.prepare(self.document), self.original)
            self.assertEqual(self.project().request, self.original)
            self.assertEqual(self.project().preflight().native_status, "not_run")
        data = self.inputs.data
        self.assertNotIn("document", data["implementation"])
        self.assertEqual(set(data["implementation"]), set(self.original["implementation_request"]) - {"schema_version", "profile", "document"})
        self.assertEqual(set(data["material"]), set(self.original) - {"schema_version", "profile", "implementation_request"})

    def test_snapshots_and_returned_views_are_independent_and_frozen(self):
        before = self.inputs.data
        self.original["context"].clear()
        self.inputs.data["implementation"].clear()
        self.inputs.prepare(self.document)["component_library"].clear()
        self.assertEqual(self.inputs.data, before)
        with self.assertRaises(FrozenInstanceError):
            self.inputs._json = b"{}"
        self.assertEqual(ComponentMaterialInputs.from_data(before).digest, self.inputs.digest)

    def test_changed_source_never_repins_supplied_authority(self):
        entry = self.document.implementations.implementations[0]
        changed = replace(self.document, implementations=replace(self.document.implementations,
            implementations=(replace(entry, version="2"),)))
        prepared = self.inputs.prepare(changed)
        self.assertEqual(prepared["implementation_request"]["document"], p.to_data(changed))
        self.assertEqual(ComponentMaterialInputs.from_request(prepared).data, self.inputs.data)
        self.assertEqual(prepared["catalog_binding"]["entry_version"], "1")
        self.assertEqual(prepared["implementation_request"]["catalog_bindings"],
                         self.original["implementation_request"]["catalog_bindings"])

    def test_changed_requirement_is_retained_for_native_assessment(self):
        declarations = tuple(replace(row, response=replace(row.response, value="completed"))
            if isinstance(row, p.Requirement) else row for row in self.document.program.declarations)
        changed = replace(self.document, program=replace(self.document.program, declarations=declarations))
        prepared = self.inputs.prepare(changed)
        self.assertEqual(prepared["implementation_request"]["document"], p.to_data(changed))
        self.assertEqual(ComponentMaterialInputs.from_request(prepared).data, self.inputs.data)

    def test_supplied_body_changes_are_not_automatically_rehashed(self):
        data = self.inputs.data
        model = data["implementation"]["implementation_library"]["models"][0]
        original_pin = deepcopy(model["identity"])
        model["body"]["configuration"]["freshness_ticks"] = 11
        inputs = ComponentMaterialInputs.from_data(data)
        prepared = inputs.prepare(self.document)
        retained = prepared["implementation_request"]["implementation_library"]["models"][0]
        self.assertEqual(retained["identity"], original_pin)
        self.assertEqual(retained["body"]["configuration"]["freshness_ticks"], 11)

    def test_closed_package_fields_and_explicit_records_are_required(self):
        good = self.inputs.data
        invalid = [{}, {**good, "schema_version": "future"}, {**good, "candidate": {}},
                   {**good, "material": None}, {**good, "implementation": {}}]
        for section, field, replacement in (("implementation", "catalog_bindings", {}),
                                            ("material", "context", []),
                                            ("material", "resource_bindings", [True])):
            changed = deepcopy(good)
            changed[section][field] = replacement
            invalid.append(changed)
        for data in invalid:
            with self.subTest(data=data), self.assertRaises((api.ComponentInputsError, CoreProtocolError)):
                ComponentMaterialInputs.from_data(data)
        for field in good["material"]:
            changed = deepcopy(good)
            del changed["material"][field]
            with self.subTest(missing=field), self.assertRaises(api.ComponentInputsError):
                ComponentMaterialInputs.from_data(changed)

    def test_wrong_request_or_untyped_source_is_rejected(self):
        for request in ({"candidate": self.original}, {**self.original, "profile": "future"},
                        {key: value for key, value in self.original.items() if key != "context"}):
            with self.subTest(request=request), self.assertRaises(CoreProtocolError):
                ComponentMaterialInputs.from_request(request)
        with self.assertRaises(api.ComponentInputsError):
            self.inputs.prepare(p.to_data(self.document))
        with self.assertRaises(ResearchProjectError):
            ResearchProject.from_build_request(project_id="x", title="x", document=self.document,
                inputs=self.inputs.data, limits=self.packet["limits"], sources=(), assumptions=())

    def test_load_dump_round_trip_and_original_alias_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "inputs.json"
            self.inputs.dump(source)
            loaded = ComponentMaterialInputs.load(source)
            self.assertEqual(loaded.data, self.inputs.data)
            with self.assertRaises(FileExistsError):
                self.inputs.dump(source)
            for alias in (source, Path(directory) / "hardlink.json"):
                if alias != source:
                    os.link(source, alias)
                with self.assertRaises(ResearchProjectError):
                    loaded.dump(alias, replace=True)
            copy = Path(directory) / "copy.json"
            loaded.dump(copy)
            self.assertEqual(copy.read_bytes(), source.read_bytes())

    def test_load_is_bounded_duplicate_safe_and_rejects_symlinks_and_fifos(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for raw in (b'{"schema_version":"x","schema_version":"y"}', b'{}'):
                path.write_bytes(raw)
                with self.assertRaises((CoreProtocolError, api.ComponentInputsError)):
                    ComponentMaterialInputs.load(path)
            path.write_bytes(self.inputs._json)
            with patch.object(api, "MAX_INPUT_BYTES", 32), self.assertRaises(ResearchProjectError):
                ComponentMaterialInputs.load(path)
            link = Path(directory) / "link.json"
            link.symlink_to(path)
            with self.assertRaises(ResearchProjectError):
                ComponentMaterialInputs.load(link)
            fifo = Path(directory) / "fifo.json"
            os.mkfifo(fifo)
            with self.assertRaises(ResearchProjectError):
                ComponentMaterialInputs.load(fifo)

    def test_noncanonical_bytes_and_mutable_path_metadata_are_rejected(self):
        with self.assertRaises(api.ComponentInputsError):
            ComponentMaterialInputs(json.dumps(self.inputs.data, indent=2).encode())
        with self.assertRaises(api.ComponentInputsError):
            ComponentMaterialInputs(self.inputs._json, [])
        self.assertEqual(self.inputs._json, encode_json(self.inputs.data))

    def test_project_bridge_carries_loaded_input_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "reference.json"
            self.project().dump(source)
            original = ResearchProject.load(source)
            extracted = original.component_inputs
            authored = ResearchProject.from_build_request(project_id="new", title="new", document=self.document,
                inputs=extracted, limits=original.limits,
                sources=(SourceRecord("input", "urn:test", "1", extracted.digest, "contracts", "Artificial test"),), assumptions=())
            self.assertEqual(authored.request, original.request)
            with self.assertRaises(ResearchProjectError):
                authored.dump(source, replace=True)
            with patch.object(CoreClient, "call", side_effect=AssertionError("No native execution")):
                with self.assertRaises((ValueError, CoreProtocolError)):
                    authored.compile(output=source, replace=True)
            with self.assertRaises(ResearchProjectError):
                extracted.dump(source, replace=True)

    def test_selection_project_cannot_be_silently_reduced_to_component_inputs(self):
        with patch.object(ResearchProject, "route", property(lambda _: "component_selection")):
            with self.assertRaisesRegex(ResearchProjectError, "original component-material"):
                self.project().component_inputs


if __name__ == "__main__":
    unittest.main()
