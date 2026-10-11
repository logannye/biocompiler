"""Pure source-byte inspection controls; no semantic or biological acceptance."""
from collections.abc import Mapping
from dataclasses import FrozenInstanceError, asdict
import hashlib
from types import MappingProxyType
import unittest
from unittest.mock import patch

from biocompiler.core_client import CoreClient
from biocompiler.policy import project_sources as api
from biocompiler.policy.research_project import ResearchProject, ResearchProjectError, SourceRecord


def project_for(sources):
    # Inert transport-shaped authority only. Its empty semantic inputs are not a
    # native-admitted program; source matching must not turn them into one.
    request = {
        "schema_version": "biocompiler.policy_component_material_request.v0.1",
        "profile": "biocompiler.policy_component_mrna.v0.1",
        "implementation_request": {
            "schema_version": "biocompiler.policy_realization_request.v0.1",
            "profile": "biocompiler.policy_realization_inputs.v0.1",
            "document": {"$type": "BuildRequest"}, "definitions": {}, "operating_domain": {},
            "implementation_library": {}, "catalog_bindings": [], "budgets": {},
        },
        "component_library": {"components": []}, "composition_rule": {}, "catalog_binding": {},
        "input_bindings": [], "resource_bindings": [], "context": {}, "budgets": {},
    }
    return ResearchProject.from_request(project_id="source-inspection", title="Inert source-byte control",
        request=request, limits={"test_allowance": 1}, sources=tuple(
            SourceRecord(identity, "urn:test:" + identity, "1", hashlib.sha256(raw).hexdigest(),
                         "caller_supplied_reference", "Unreviewed caller declaration")
            for identity, raw in sources.items()), assumptions=("Biological function is unassessed.",))


class RepeatedKeys(Mapping):
    def __iter__(self):
        return iter(("first", "first"))

    def __len__(self):
        return 2

    def __getitem__(self, key):
        return b"first source"


class ProjectSourceTests(unittest.TestCase):
    def setUp(self):
        self.sources = {"first": b"first source", "second": b"second source\x00\xff"}
        self.project = project_for(self.sources)

    def test_complete_exact_bytes_match_in_project_order_with_narrow_claims(self):
        reversed_sources = MappingProxyType(dict(reversed(tuple(self.sources.items()))))
        result = api.inspect_project_sources(self.project, reversed_sources)
        self.assertEqual(result.project_sha256, self.project.digest)
        self.assertEqual(tuple(row.source_id for row in result.sources), ("first", "second"))
        self.assertEqual(tuple(row.sha256 for row in result.sources),
                         tuple(hashlib.sha256(raw).hexdigest() for raw in self.sources.values()))
        self.assertEqual(result.total_bytes, sum(map(len, self.sources.values())))
        self.assertEqual((result.status, result.publication_authenticity, result.biological_status,
                          result.rights_status, result.native_status),
                         ("source_bytes_matched", "unassessed", "unassessed", "unassessed", "not_run"))
        self.assertEqual(self.project.preflight().native_status, "not_run")

    def test_result_and_caller_snapshots_remain_immutable(self):
        result = api.inspect_project_sources(self.project, self.sources)
        before = asdict(result)
        self.sources.clear()
        self.project.data["sources"].clear()
        detached = asdict(result)
        detached["sources"][0]["sha256"] = "0" * 64
        self.assertEqual(asdict(result), before)
        with self.assertRaises(FrozenInstanceError):
            result.total_bytes = 0
        with self.assertRaises(FrozenInstanceError):
            result.sources[0].sha256 = "0" * 64

    def test_all_source_values_are_snapshotted_before_hashing(self):
        original_hash = hashlib.sha256
        original_second = self.sources["second"]
        def mutate_mapping(raw):
            self.sources["second"] = b"changed after snapshot"
            return original_hash(raw)
        with patch.object(api.hashlib, "sha256", side_effect=mutate_mapping):
            result = api.inspect_project_sources(self.project, self.sources)
        self.assertEqual(result.sources[1].sha256, original_hash(original_second).hexdigest())
        with self.assertRaisesRegex(api.ProjectSourceError, "digest"):
            api.inspect_project_sources(self.project, self.sources)

    def test_metadata_and_assumption_edits_change_complete_project_binding(self):
        original = api.inspect_project_sources(self.project, self.sources)
        for field in ("locator", "version", "role", "reuse_terms"):
            data = self.project.data
            data["sources"][0][field] += ".changed"
            with self.subTest(field=field):
                changed = ResearchProject.from_data(data)
                result = api.inspect_project_sources(changed, self.sources)
                self.assertNotEqual(result.project_sha256, original.project_sha256)
                self.assertEqual(result.sources, original.sources)
        for field, value in (("assumptions", ["Different declared assumption"]),
                             ("title", "Changed title"), ("limits", {"test_allowance": 2})):
            data = self.project.data
            data[field] = value
            with self.subTest(field=field):
                result = api.inspect_project_sources(ResearchProject.from_data(data), self.sources)
                self.assertNotEqual(result.project_sha256, original.project_sha256)

    def test_missing_extra_and_substituted_ids_reject(self):
        for supplied in ({}, {"first": self.sources["first"]},
                         {**self.sources, "extra": b"extra"},
                         {"first": self.sources["first"], "other": self.sources["second"]}):
            with self.subTest(ids=tuple(supplied)), self.assertRaises(api.ProjectSourceError):
                api.inspect_project_sources(self.project, supplied)

    def test_custom_mapping_cannot_hide_duplicate_or_missing_ids(self):
        with self.assertRaisesRegex(api.ProjectSourceError, "repeated"):
            api.inspect_project_sources(self.project, RepeatedKeys())
        class MissingKey(RepeatedKeys):
            def __iter__(self):
                return iter(("first",))
        with self.assertRaisesRegex(api.ProjectSourceError, "exactly"):
            api.inspect_project_sources(self.project, MissingKey())

    def test_mapping_mutation_during_snapshot_rejects(self):
        class ChangingMapping(RepeatedKeys):
            def __getitem__(self, key):
                raise KeyError(key)
        with self.assertRaisesRegex(api.ProjectSourceError, "changed"):
            api.inspect_project_sources(self.project, ChangingMapping())

    def test_malformed_inputs_and_mutable_bytes_reject(self):
        for supplied in (None, [], tuple(self.sources.items()), {1: b"x", "second": b"y"},
                         {"first": bytearray(b"first source"), "second": self.sources["second"]},
                         {"first": memoryview(b"first source"), "second": self.sources["second"]},
                         {"first": "first source", "second": self.sources["second"]}):
            with self.subTest(kind=type(supplied)), self.assertRaises(api.ProjectSourceError):
                api.inspect_project_sources(self.project, supplied)
        with self.assertRaisesRegex(api.ProjectSourceError, "ResearchProject"):
            api.inspect_project_sources(self.project.data, self.sources)

    def test_tampered_stale_and_normalized_bytes_reject_without_cached_pass(self):
        api.inspect_project_sources(self.project, self.sources)
        for raw in (b"FIRST source", b"first source\n", b"first sourcf", b"stale source"):
            self.sources["first"] = raw
            with self.subTest(raw=raw), self.assertRaisesRegex(api.ProjectSourceError, "digest"):
                api.inspect_project_sources(self.project, self.sources)
        data = self.project.data
        data["sources"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(api.ProjectSourceError, "digest"):
            api.inspect_project_sources(ResearchProject.from_data(data), self.sources)

    def test_identical_bytes_under_distinct_declared_ids_are_allowed(self):
        supplied = {"one": b"same bytes", "two": b"same bytes"}
        result = api.inspect_project_sources(project_for(supplied), supplied)
        self.assertEqual(len(result.sources), 2)
        self.assertEqual(result.total_bytes, 2 * len(b"same bytes"))

    def test_empty_source_is_rejected_even_when_its_digest_matches(self):
        supplied = {"empty": b""}
        with self.assertRaisesRegex(api.ProjectSourceError, "nonempty"):
            api.inspect_project_sources(project_for(supplied), supplied)

    def test_source_and_total_bounds_are_inclusive_and_checked_before_hashing(self):
        supplied = {"one": b"1234", "two": b"5678"}
        project = project_for(supplied)
        with patch.object(api, "MAX_SOURCE_BYTES", 4), patch.object(api, "MAX_TOTAL_SOURCE_BYTES", 8):
            self.assertEqual(api.inspect_project_sources(project, supplied).total_bytes, 8)
            with patch.object(api.hashlib, "sha256", side_effect=AssertionError("No hashing past limits")):
                with self.assertRaisesRegex(api.ProjectSourceError, "byte bound"):
                    api.inspect_project_sources(project, {"one": b"12345", "two": b"5678"})
        with patch.object(api, "MAX_SOURCE_BYTES", 4), patch.object(api, "MAX_TOTAL_SOURCE_BYTES", 7), \
             patch.object(api.hashlib, "sha256", side_effect=AssertionError("No hashing past limits")):
            with self.assertRaisesRegex(api.ProjectSourceError, "total byte bound"):
                api.inspect_project_sources(project, supplied)

    def test_source_id_inventory_is_bounded_independently_of_mapping_length(self):
        class ExtraIteration(Mapping):
            def __len__(self):
                return 2
            def __iter__(self):
                yield "first"
                yield "second"
                yield "extra"
                raise AssertionError("Unbounded mapping iteration")
            def __getitem__(self, key):
                return self.sources[key]
        supplied = ExtraIteration()
        supplied.sources = self.sources
        with self.assertRaisesRegex(api.ProjectSourceError, "extra"):
            api.inspect_project_sources(self.project, supplied)

    def test_duplicate_declared_source_ids_are_rejected_by_project_authority(self):
        data = self.project.data
        data["sources"][1]["id"] = data["sources"][0]["id"]
        with self.assertRaisesRegex(ResearchProjectError, "unique"):
            ResearchProject.from_data(data)

    def test_inspection_performs_no_path_network_or_native_io(self):
        with patch("builtins.open", side_effect=AssertionError("No file I/O")), \
             patch("os.open", side_effect=AssertionError("No path I/O")), \
             patch("socket.socket", side_effect=AssertionError("No network I/O")), \
             patch("subprocess.Popen", side_effect=AssertionError("No process")), \
             patch.object(CoreClient, "call", side_effect=AssertionError("No native execution")):
            result = api.inspect_project_sources(self.project, self.sources)
        self.assertEqual(result.status, "source_bytes_matched")


if __name__ == "__main__":
    unittest.main()
